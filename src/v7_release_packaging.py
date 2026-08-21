"""Reusable packaging for Rad Dad Retro Riot v7: Micro Replica Edition.

This module intentionally does not build model geometry. It accepts finished
``trimesh``-compatible meshes from a separate orchestrator and handles stable
release artifacts: model-only Core 3MF, binary STL, previews, NFC artwork,
handoff cards, release documentation, checksums, archives, and digital QA.

Important manufacturing distinction
------------------------------------
``write_core_3mf`` writes standards-based geometry packages only. Core 3MF
does not contain a Bambu printer, filament, process, support, or plate profile.
A file may be called a Bambu project only after an external Bambu-specific
postprocessor has embedded and verified those settings. The postprocessor hook
in this module makes that boundary explicit instead of pretending that a
geometry-only 3MF is print-ready.

Runtime dependencies are limited to Python's standard library, NumPy, Pillow,
and a mesh object exposing the usual trimesh ``vertices`` and ``faces`` API.
The default QR matrix is embedded for https://raddadband.com/tap/ so release
artwork does not depend on a network service or an optional QR package.
"""

from __future__ import annotations

import hashlib
import html
import importlib
import io
import json
import math
import os
import struct
import tempfile
import zipfile
import zlib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np
from PIL import Image, ImageDraw, ImageFont


DEFAULT_TAP_URL = "https://raddadband.com/tap/"
ROOT_TAGLINE = "Old media. Loud band. One tap."
MODEL_ONLY_3MF_WARNING = (
    "MODEL-ONLY CORE 3MF: geometry and thumbnail only. This file does not "
    "contain Bambu printer, nozzle, filament, process, support, or plate settings."
)
NON_METALLIC_STOCK_WARNING = (
    "PRINT NFC OVERLAYS ONLY ON NON-METALLIC PAPER OR VINYL. NEVER USE FOIL, "
    "METALLIC INK, OR METAL-BACKED LABEL STOCK."
)

BRAND = {
    "ink": "#050B12",
    "panel": "#0C1722",
    "cream": "#F5F1E8",
    "lime": "#A6EF12",
    "blue": "#1CB5F4",
    "pink": "#FF3476",
    "amber": "#FFB000",
    "steel": "#A9B1B8",
    "steel_dark": "#555E68",
}

ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
OVERLAY_DIAMETER_MM = 25.0
OVERLAY_BLEED_MM = 1.0
OVERLAY_SAFE_RADIUS_MM = 10.95
OVERLAY_TEXT_SAFE_RADIUS_MM = 11.35
OVERLAY_CUT_GUIDE_WIDTH_MM = 0.15
HANDOFF_TRIM_WIDTH_MM = 88.9
HANDOFF_TRIM_HEIGHT_MM = 50.8
HANDOFF_BLEED_MM = 3.175
HANDOFF_ART_WIDTH_MM = HANDOFF_TRIM_WIDTH_MM + 2 * HANDOFF_BLEED_MM
HANDOFF_ART_HEIGHT_MM = HANDOFF_TRIM_HEIGHT_MM + 2 * HANDOFF_BLEED_MM
HANDOFF_SAFE_INSET_MM = 3.2


@dataclass(frozen=True)
class ThreeMFObject:
    """One named mesh in a Core 3MF package.

    ``transform`` is an optional conventional 4 x 4 homogeneous transform. It
    is baked into a private vertex copy before serialization so the generated
    package does not depend on slicer-specific transform interpretation.
    """

    name: str
    mesh: Any
    transform: Any | None = None


@dataclass(frozen=True)
class ThreeMFPackageResult:
    path: Path
    package_kind: str
    object_count: int
    warning: str | None = None
    postprocessor: str | None = None


@dataclass(frozen=True)
class BambuPrintIntent:
    slug: str
    display_name: str
    printer: str = "Bambu Lab A1 mini"
    nozzle_mm: float = 0.4
    layer_height_mm: float = 0.16
    initial_layer_height_mm: float = 0.20
    wall_loops: int = 4
    top_layers: int = 5
    bottom_layers: int = 5
    infill_percent: int = 30
    infill_pattern: str = "gyroid"
    supports: str = "off"
    support_on_build_plate_only: bool = False
    orientation: str = "flat"
    profile_status: str = "intent-only-until-postprocessed"


DEFAULT_PRINT_INTENTS: dict[str, BambuPrintIntent] = {
    "cassette": BambuPrintIntent(
        slug="cassette",
        display_name="Rad Dad Micro Cassette",
        supports="off",
        orientation="front-up-flat",
    ),
    "floppy": BambuPrintIntent(
        slug="floppy",
        display_name="Rad Dad Micro 3.5-inch Floppy",
        supports="off",
        orientation="front-up-flat",
    ),
    "vhs": BambuPrintIntent(
        slug="vhs",
        display_name="Rad Dad Micro VHS",
        supports="off",
        orientation="front-up-flat",
    ),
    "trailer_swift": BambuPrintIntent(
        slug="trailer_swift",
        display_name="Trailer Swift Micro Figure",
        supports="organic",
        support_on_build_plate_only=True,
        orientation="base-down-upright",
    ),
}


@dataclass(frozen=True)
class OverlaySpec:
    key: str
    title: str
    subtitle: str
    accent: str
    motif: str


OVERLAY_SPECS: dict[str, OverlaySpec] = {
    "cassette": OverlaySpec(
        key="cassette",
        title="C-69 // SIDE A",
        subtitle="RAD DAD",
        accent=BRAND["lime"],
        motif="cassette",
    ),
    "floppy": OverlaySpec(
        key="floppy",
        title="3.69 MB",
        subtitle="RAD DAD",
        accent=BRAND["blue"],
        motif="floppy",
    ),
    "vhs": OverlaySpec(
        key="vhs",
        title="T-369",
        subtitle="RAD DAD VIDEO",
        accent=BRAND["pink"],
        motif="vhs",
    ),
    "trailer_swift": OverlaySpec(
        key="trailer_swift",
        title="TRAILER SWIFT",
        subtitle="TAP THE BASE",
        accent=BRAND["amber"],
        motif="trailer",
    ),
    "generic": OverlaySpec(
        key="generic",
        title="RAD DAD",
        subtitle="TAP TO PLAY",
        accent=BRAND["lime"],
        motif="generic",
    ),
}


@dataclass(frozen=True)
class ReleaseLayout:
    root: Path
    models_3mf: Path
    models_stl: Path
    previews: Path
    guides: Path
    qa: Path


@runtime_checkable
class BambuProjectPostprocessor(Protocol):
    """Adapter contract for producing a true Bambu project 3MF.

    Implementations belong in a separate Bambu-aware module. They must start
    with ``core_3mf``, embed an explicit profile matching ``intent``, write
    ``output_3mf``, and return the resulting path. The implementation should
    also verify the project in Bambu Studio or an equivalent Bambu parser.
    """

    name: str

    def create_project(
        self,
        *,
        core_3mf: Path,
        output_3mf: Path,
        intent: BambuPrintIntent,
        metadata: Mapping[str, Any],
    ) -> Path:
        ...


@dataclass(frozen=True)
class ModuleBambuPostprocessor:
    module_name: str
    function_name: str = "create_bambu_project"

    @property
    def name(self) -> str:
        return f"{self.module_name}.{self.function_name}"

    def create_project(
        self,
        *,
        core_3mf: Path,
        output_3mf: Path,
        intent: BambuPrintIntent,
        metadata: Mapping[str, Any],
    ) -> Path:
        module = importlib.import_module(self.module_name)
        function = getattr(module, self.function_name, None)
        if not callable(function):
            raise AttributeError(
                f"{self.module_name!r} must expose callable {self.function_name!r}"
            )
        result = function(
            core_3mf=core_3mf,
            output_3mf=output_3mf,
            intent=intent,
            metadata=dict(metadata),
        )
        return Path(result) if result is not None else output_3mf


def create_release_layout(root: str | Path) -> ReleaseLayout:
    root_path = Path(root)
    layout = ReleaseLayout(
        root=root_path,
        models_3mf=root_path / "3mf",
        models_stl=root_path / "stl",
        previews=root_path / "previews",
        guides=root_path / "guides",
        qa=root_path / "qa",
    )
    for directory in (
        layout.root,
        layout.models_3mf,
        layout.models_stl,
        layout.previews,
        layout.guides,
        layout.qa,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return layout


def _atomic_write_bytes(path: str | Path, data: bytes) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def _atomic_write_text(path: str | Path, text: str) -> Path:
    return _atomic_write_bytes(path, text.encode("utf-8"))


def _format_float(value: float) -> str:
    value = 0.0 if abs(float(value)) < 5e-13 else float(value)
    return format(value, ".9g")


def _mesh_arrays(
    mesh: Any,
    transform: Any | None = None,
    *,
    strict: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    if not hasattr(mesh, "vertices") or not hasattr(mesh, "faces"):
        raise TypeError("mesh must expose trimesh-compatible vertices and faces")
    vertices = np.asarray(mesh.vertices, dtype=np.float64).copy()
    faces = np.asarray(mesh.faces, dtype=np.int64).copy()
    if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) == 0:
        raise ValueError("mesh vertices must have shape (n, 3) and cannot be empty")
    if faces.ndim != 2 or faces.shape[1] != 3 or len(faces) == 0:
        raise ValueError("Core 3MF and STL output require triangular faces")
    if not np.isfinite(vertices).all():
        raise ValueError("mesh contains non-finite vertex coordinates")
    if faces.min() < 0 or faces.max() >= len(vertices):
        raise ValueError("mesh faces reference invalid vertex indexes")

    if transform is not None:
        matrix = np.asarray(transform, dtype=np.float64)
        if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
            raise ValueError("transform must be a finite 4 x 4 matrix")
        homogeneous = np.column_stack((vertices, np.ones(len(vertices))))
        vertices = (homogeneous @ matrix.T)[:, :3]

    repeated_index = (
        (faces[:, 0] == faces[:, 1])
        | (faces[:, 1] == faces[:, 2])
        | (faces[:, 2] == faces[:, 0])
    )
    cross = np.cross(
        vertices[faces[:, 1]] - vertices[faces[:, 0]],
        vertices[faces[:, 2]] - vertices[faces[:, 0]],
    )
    degenerate = repeated_index | (np.linalg.norm(cross, axis=1) <= 1e-12)
    canonical_faces = np.sort(faces, axis=1)
    _, first_indexes = np.unique(canonical_faces, axis=0, return_index=True)
    duplicate = np.ones(len(faces), dtype=bool)
    duplicate[np.sort(first_indexes)] = False
    invalid = degenerate | duplicate
    if invalid.any():
        if strict:
            raise ValueError(
                f"mesh contains {int(degenerate.sum())} degenerate and "
                f"{int(duplicate.sum())} duplicate triangles"
            )
        faces = faces[~invalid]
        if len(faces) == 0:
            raise ValueError("mesh contains no usable triangles")

    used = np.unique(faces.reshape(-1))
    remap = np.full(len(vertices), -1, dtype=np.int64)
    remap[used] = np.arange(len(used), dtype=np.int64)
    return vertices[used], remap[faces]


def _coerce_3mf_objects(
    objects: Any,
) -> list[ThreeMFObject]:
    if isinstance(objects, ThreeMFObject):
        return [objects]
    if hasattr(objects, "vertices") and hasattr(objects, "faces"):
        return [ThreeMFObject("Model", objects)]
    if isinstance(objects, Mapping):
        return [
            ThreeMFObject(str(name), objects[name])
            for name in sorted(objects, key=lambda item: str(item))
        ]
    result: list[ThreeMFObject] = []
    for index, item in enumerate(objects, start=1):
        if isinstance(item, ThreeMFObject):
            result.append(item)
        elif isinstance(item, Sequence) and len(item) in (2, 3):
            name, mesh = item[0], item[1]
            transform = item[2] if len(item) == 3 else None
            result.append(ThreeMFObject(str(name), mesh, transform))
        elif hasattr(item, "vertices") and hasattr(item, "faces"):
            result.append(ThreeMFObject(f"Model {index}", item))
        else:
            raise TypeError(f"unsupported 3MF object at index {index}")
    if not result:
        raise ValueError("at least one mesh is required")
    return result


def _core_model_xml(
    objects: Sequence[ThreeMFObject],
    *,
    title: str,
    metadata: Mapping[str, Any],
    strict: bool,
) -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
        f'  <metadata name="Title">{html.escape(title)}</metadata>',
    ]
    for key in sorted(metadata):
        value = metadata[key]
        if value is None:
            continue
        lines.append(
            f'  <metadata name="{html.escape(str(key), quote=True)}">'
            f"{html.escape(str(value))}</metadata>"
        )
    lines.append("  <resources>")
    object_ids: list[int] = []
    for object_id, item in enumerate(objects, start=1):
        vertices, faces = _mesh_arrays(item.mesh, item.transform, strict=strict)
        object_ids.append(object_id)
        lines.append(
            f'    <object id="{object_id}" type="model" '
            f'name="{html.escape(item.name, quote=True)}">'
        )
        lines.append("      <mesh>")
        lines.append("        <vertices>")
        lines.extend(
            "          <vertex x=\"{}\" y=\"{}\" z=\"{}\"/>".format(
                _format_float(vertex[0]),
                _format_float(vertex[1]),
                _format_float(vertex[2]),
            )
            for vertex in vertices
        )
        lines.append("        </vertices>")
        lines.append("        <triangles>")
        lines.extend(
            f'          <triangle v1="{int(face[0])}" v2="{int(face[1])}" '
            f'v3="{int(face[2])}"/>'
            for face in faces
        )
        lines.append("        </triangles>")
        lines.append("      </mesh>")
        lines.append("    </object>")
    lines.append("  </resources>")
    lines.append("  <build>")
    lines.extend(f'    <item objectid="{item_id}"/>' for item_id in object_ids)
    lines.append("  </build>")
    lines.append("</model>")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _thumbnail_png_bytes(thumbnail: Any) -> bytes:
    if isinstance(thumbnail, Image.Image):
        image = thumbnail.copy()
    elif isinstance(thumbnail, (str, Path)):
        with Image.open(thumbnail) as source:
            image = source.copy()
    elif isinstance(thumbnail, (bytes, bytearray)):
        with Image.open(io.BytesIO(bytes(thumbnail))) as source:
            image = source.copy()
    else:
        raise TypeError("thumbnail must be a Pillow image, path, or image bytes")
    image = image.convert("RGB")
    image.thumbnail((512, 512), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.flag_bits |= 0x800
    return info


def write_core_3mf(
    path: str | Path,
    objects: Any,
    *,
    title: str,
    thumbnail: Any | None = None,
    metadata: Mapping[str, Any] | None = None,
    strict: bool = True,
) -> ThreeMFPackageResult:
    """Write a deterministic, model-only Core 3MF package.

    This function never claims to embed slicer settings. Use
    ``apply_bambu_postprocessor`` to produce a separately named true project
    3MF after a Bambu-aware adapter is available.
    """

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized_objects = _coerce_3mf_objects(objects)
    package_metadata = {
        "Application": "Rad Dad Micro Replicas v7 packaging",
        "Description": MODEL_ONLY_3MF_WARNING,
        **dict(metadata or {}),
    }
    model_xml = _core_model_xml(
        normalized_objects,
        title=title,
        metadata=package_metadata,
        strict=strict,
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        + (
            '<Default Extension="png" ContentType="image/png"/>'
            if thumbnail is not None
            else ""
        )
        + "</Types>"
    ).encode("utf-8")
    relationships = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>',
    ]
    thumbnail_bytes = None
    if thumbnail is not None:
        thumbnail_bytes = _thumbnail_png_bytes(thumbnail)
        relationships.append(
            '<Relationship Target="/Metadata/thumbnail.png" Id="rel1" '
            'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"/>'
        )
    relationships.append("</Relationships>")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            archive.writestr(_zip_info("[Content_Types].xml"), content_types)
            archive.writestr(
                _zip_info("_rels/.rels"), ("\n".join(relationships) + "\n").encode("utf-8")
            )
            archive.writestr(_zip_info("3D/3dmodel.model"), model_xml)
            if thumbnail_bytes is not None:
                archive.writestr(
                    _zip_info("Metadata/thumbnail.png"), thumbnail_bytes
                )
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return ThreeMFPackageResult(
        path=destination,
        package_kind="model-only-core-3mf",
        object_count=len(normalized_objects),
        warning=MODEL_ONLY_3MF_WARNING,
    )


def load_bambu_postprocessor(
    module_name: str,
    function_name: str = "create_bambu_project",
) -> ModuleBambuPostprocessor:
    """Return a lazy adapter for a separate Bambu-specific module."""

    return ModuleBambuPostprocessor(module_name, function_name)


def apply_bambu_postprocessor(
    core_3mf: str | Path,
    output_3mf: str | Path,
    *,
    intent: BambuPrintIntent,
    postprocessor: BambuProjectPostprocessor,
    metadata: Mapping[str, Any] | None = None,
) -> ThreeMFPackageResult:
    """Create a true Bambu project through an explicit external adapter."""

    source = Path(core_3mf)
    destination = Path(output_3mf)
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.resolve() == destination.resolve():
        raise ValueError("Bambu project output must not overwrite the Core 3MF")
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = postprocessor.create_project(
        core_3mf=source,
        output_3mf=destination,
        intent=intent,
        metadata=dict(metadata or {}),
    )
    result_path = Path(result)
    if not result_path.is_file() or result_path.stat().st_size == 0:
        raise RuntimeError(
            f"Bambu postprocessor {postprocessor.name!r} did not create a project file"
        )
    return ThreeMFPackageResult(
        path=result_path,
        package_kind="bambu-project-3mf",
        object_count=1,
        warning=None,
        postprocessor=postprocessor.name,
    )


def export_binary_stl(
    mesh: Any,
    path: str | Path,
    *,
    transform: Any | None = None,
    solid_name: str = "Rad Dad Micro Replica",
    strict: bool = True,
) -> Path:
    """Export a deterministic binary STL without relying on trimesh exporters."""

    vertices, faces = _mesh_arrays(mesh, transform, strict=strict)
    if len(faces) > 0xFFFFFFFF:
        raise ValueError("binary STL cannot store more than 2^32 - 1 triangles")
    header_text = solid_name.encode("ascii", errors="replace")[:80]
    payload = bytearray(header_text.ljust(80, b"\0"))
    payload.extend(struct.pack("<I", len(faces)))
    for face in faces:
        triangle = vertices[face].astype(np.float64, copy=False)
        normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
        length = float(np.linalg.norm(normal))
        normal = normal / length if length > 0.0 else np.zeros(3)
        payload.extend(
            struct.pack(
                "<12fH",
                float(normal[0]),
                float(normal[1]),
                float(normal[2]),
                *(float(value) for value in triangle.reshape(-1)),
                0,
            )
        )
    return _atomic_write_bytes(path, bytes(payload))


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _release_files(
    root: Path,
    *,
    excluded: Iterable[Path] = (),
) -> list[Path]:
    excluded_resolved = {item.resolve() for item in excluded}
    files: list[Path] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ValueError(f"release archives do not accept symlinks: {path}")
        if path.is_file() and path.resolve() not in excluded_resolved:
            files.append(path)
    return files


def create_deterministic_zip(
    source_root: str | Path,
    output_zip: str | Path,
    *,
    archive_prefix: str | None = None,
    exclude: Iterable[str | Path] = (),
) -> Path:
    """Create a reproducible ZIP with sorted paths and fixed metadata."""

    root = Path(source_root).resolve()
    destination = Path(output_zip)
    destination.parent.mkdir(parents=True, exist_ok=True)
    excluded = [Path(item).resolve() for item in exclude]
    excluded.append(destination.resolve())
    files = _release_files(root, excluded=excluded)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    prefix = (archive_prefix or "").strip("/")
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for path in files:
                relative = path.relative_to(root).as_posix()
                arcname = f"{prefix}/{relative}" if prefix else relative
                info = _zip_info(arcname)
                with path.open("rb") as source, archive.open(info, "w") as target:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        target.write(chunk)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def write_release_manifest(
    release_root: str | Path,
    *,
    release_name: str = "Rad Dad Micro Replicas v7",
    output_path: str | Path | None = None,
    exclude: Iterable[str | Path] = (),
    metadata: Mapping[str, Any] | None = None,
) -> Path:
    root = Path(release_root).resolve()
    destination = Path(output_path) if output_path else root / "MANIFEST.json"
    excluded = [Path(item).resolve() for item in exclude]
    excluded.append(destination.resolve())
    records = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in _release_files(root, excluded=excluded)
    ]
    document = {
        "schema": "rad-dad-release-manifest-v1",
        "release": release_name,
        "metadata": dict(metadata or {}),
        "files": records,
    }
    return _atomic_write_text(
        destination, json.dumps(document, indent=2, sort_keys=True) + "\n"
    )


def write_sha256_sidecar(path: str | Path) -> Path:
    target = Path(path)
    sidecar = target.with_name(target.name + ".sha256")
    return _atomic_write_text(sidecar, f"{sha256_file(target)}  {target.name}\n")


def _hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _mix_rgb(
    first: tuple[int, int, int], second: tuple[int, int, int], amount: float
) -> tuple[int, int, int]:
    amount = float(np.clip(amount, 0.0, 1.0))
    return tuple(
        int(round(a + (b - a) * amount)) for a, b in zip(first, second)
    )


def _font_candidates(*, bold: bool, condensed: bool) -> tuple[str, ...]:
    if condensed and bold:
        return (
            "/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
            "DejaVuSansCondensed-Bold.ttf",
            "DejaVuSans-Bold.ttf",
        )
    if bold:
        return (
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "DejaVuSans-Bold.ttf",
        )
    return (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans.ttf",
    )


def _load_font(size: int, *, bold: bool = True, condensed: bool = False):
    for candidate in _font_candidates(bold=bold, condensed=condensed):
        try:
            return ImageFont.truetype(candidate, max(1, int(size)))
        except OSError:
            continue
    return ImageFont.load_default()


def _camera_basis(
    view: str,
    orientation: str,
    *,
    camera_direction: Any | None = None,
    up_direction: Any | None = None,
):
    if view not in {"front", "back", "detail"}:
        raise ValueError("view must be front, back, or detail")
    if orientation not in {"flat", "upright"}:
        raise ValueError("orientation must be flat or upright")
    if camera_direction is not None:
        camera = np.asarray(camera_direction, dtype=np.float64).reshape(3)
        up_guess = (
            np.asarray(up_direction, dtype=np.float64).reshape(3)
            if up_direction is not None
            else np.array((0.0, 0.0, 1.0))
        )
    elif orientation == "flat":
        camera = {
            # These remain orthographic, but a modest compound angle exposes
            # raised lettering, grooves, windows, and the rear landing ring.
            "front": np.array((0.18, -0.25, 1.0)),
            "back": np.array((-0.18, -0.25, -1.0)),
            "detail": np.array((1.0, -1.15, 0.90)),
        }[view]
        up_guess = (
            np.array((0.0, 1.0, 0.0))
            if view != "detail"
            else np.array((0.0, 0.0, 1.0))
        )
    else:
        camera = {
            "front": np.array((0.18, -1.0, 0.10)),
            "back": np.array((-0.18, 1.0, 0.10)),
            "detail": np.array((1.0, -1.15, 0.62)),
        }[view]
        up_guess = np.array((0.0, 0.0, 1.0))
    if not np.isfinite(camera).all() or np.linalg.norm(camera) <= 1e-12:
        raise ValueError("camera direction must be a finite nonzero vector")
    if not np.isfinite(up_guess).all() or np.linalg.norm(up_guess) <= 1e-12:
        raise ValueError("camera up direction must be a finite nonzero vector")
    camera = camera / np.linalg.norm(camera)
    up_guess = up_guess / np.linalg.norm(up_guess)
    if abs(float(camera @ up_guess)) > 0.97:
        up_guess = np.array((0.0, 1.0, 0.0))
    right = np.cross(up_guess, camera)
    right = right / np.linalg.norm(right)
    up = np.cross(camera, right)
    up = up / np.linalg.norm(up)
    return camera, right, up


def _preview_crease_edges(
    faces: np.ndarray,
    face_normals: np.ndarray,
    facing: np.ndarray,
    *,
    max_edges: int = 18000,
) -> np.ndarray:
    """Return real mesh creases without exposing every triangulation edge."""

    edges = np.vstack(
        (faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)])
    )
    owners = np.tile(np.arange(len(faces), dtype=np.int64), 3)
    canonical = np.sort(edges, axis=1)
    order = np.lexsort((canonical[:, 1], canonical[:, 0]))
    canonical = canonical[order]
    owners = owners[order]
    paired = np.flatnonzero(
        np.all(canonical[1:] == canonical[:-1], axis=1)
    )
    if not len(paired):
        return np.empty((0, 2), dtype=np.int64)
    first_faces = owners[paired]
    second_faces = owners[paired + 1]
    normal_similarity = np.einsum(
        "ij,ij->i", face_normals[first_faces], face_normals[second_faces]
    )
    showcase_facing = (
        (facing[first_faces] > 0.02) & (facing[second_faces] > 0.02)
    )
    selected = canonical[paired[showcase_facing & (normal_similarity < 0.90)]]
    if len(selected):
        selected = np.unique(selected, axis=0)
    if len(selected) > max_edges:
        sample = np.linspace(0, len(selected) - 1, max_edges, dtype=np.int64)
        selected = selected[sample]
    return selected


def render_mesh_preview(
    mesh: Any,
    path: str | Path,
    *,
    title: str,
    view: str = "front",
    orientation: str = "flat",
    accent: str = BRAND["lime"],
    size: tuple[int, int] = (1400, 1000),
    max_faces: int = 70000,
    camera_direction: Any | None = None,
    camera_up: Any | None = None,
    reported_extents_mm: Sequence[float] | None = None,
    dimension_label: str = "MODEL SIZE",
    preview_note: str | None = None,
) -> Path:
    """Render an honest orthographic showcase preview entirely in software."""

    vertices, faces = _mesh_arrays(mesh, strict=False)
    triangle_vertices = vertices[faces]
    face_normals = np.cross(
        triangle_vertices[:, 1] - triangle_vertices[:, 0],
        triangle_vertices[:, 2] - triangle_vertices[:, 0],
    )
    lengths = np.linalg.norm(face_normals, axis=1)
    face_normals = face_normals / np.maximum(lengths[:, None], 1e-12)
    camera, right, up = _camera_basis(
        view,
        orientation,
        camera_direction=camera_direction,
        up_direction=camera_up,
    )
    facing = face_normals @ camera
    visible = np.flatnonzero(facing > 0.02)
    if len(visible) > max_faces:
        sample = np.linspace(0, len(visible) - 1, max_faces, dtype=np.int64)
        visible = visible[sample]
    screen_x = vertices @ right
    screen_y = vertices @ up
    depth = vertices @ camera
    width, height = size
    image = Image.new("RGB", size, BRAND["ink"])
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (36, 104, width - 36, height - 40),
        radius=28,
        fill=BRAND["panel"],
        outline="#263746",
        width=3,
    )
    draw.text(
        (width // 2, 50),
        title.upper(),
        font=_load_font(42, condensed=True),
        fill=BRAND["cream"],
        anchor="mm",
    )
    draw.text(
        (width - 58, 54),
        view.upper(),
        font=_load_font(22, condensed=True),
        fill=accent,
        anchor="rm",
    )
    u_min, u_max = float(screen_x.min()), float(screen_x.max())
    v_min, v_max = float(screen_y.min()), float(screen_y.max())
    draw_box = (85, 145, width - 85, height - (165 if preview_note else 115))
    scale = min(
        (draw_box[2] - draw_box[0]) / max(u_max - u_min, 1e-6),
        (draw_box[3] - draw_box[1]) / max(v_max - v_min, 1e-6),
    ) * 0.92
    offset_x = (draw_box[0] + draw_box[2]) / 2 - (u_min + u_max) * scale / 2
    offset_y = (draw_box[1] + draw_box[3]) / 2 + (v_min + v_max) * scale / 2
    face_depth = depth[faces].mean(axis=1)
    order = visible[np.argsort(face_depth[visible])]
    base = _hex_rgb(accent)
    light = camera + up * 0.45 - right * 0.25
    light = light / np.linalg.norm(light)
    relief_level = None
    if orientation == "flat" and view in {"front", "back"}:
        face_z = triangle_vertices[:, :, 2].mean(axis=1)
        surface_sign = 1.0 if view == "front" else -1.0
        surface_faces = visible[(face_normals[visible, 2] * surface_sign) > 0.80]
        surface_z = face_z[surface_faces]
        if len(surface_z):
            relief_low = float(surface_z.min())
            relief_high = float(surface_z.max())
            relief_span = max(relief_high - relief_low, 1e-6)
            if view == "front":
                relief_level = np.clip(
                    (face_z - relief_low) / relief_span,
                    0.0,
                    1.0,
                )
            else:
                relief_level = np.clip(
                    (relief_high - face_z) / relief_span,
                    0.0,
                    1.0,
                )
    for face_index in order:
        normal = face_normals[face_index]
        directional = max(0.0, float(normal @ light))
        if relief_level is not None:
            grazing = 1.0 - abs(float(normal @ camera))
            illumination = float(
                np.clip(
                    0.17
                    + 0.40 * directional
                    + 0.32 * relief_level[face_index]
                    + 0.11 * grazing,
                    0.18,
                    0.96,
                )
            )
        else:
            illumination = 0.20 + 0.68 * directional
        color = _mix_rgb(_hex_rgb(BRAND["panel"]), base, illumination)
        points = [
            (
                offset_x + screen_x[vertex] * scale,
                offset_y - screen_y[vertex] * scale,
            )
            for vertex in faces[face_index]
        ]
        draw.polygon(points, fill=color)
    # Oblique rear lighting already reveals the real locator ring, eyelet, and
    # silhouette. Internal crease overlays on broad rear planes can expose
    # harmless tessellation as black specks, so reserve them for showcase
    # views where they clarify front relief rather than misrepresent geometry.
    if view != "back":
        crease_color = _mix_rgb(_hex_rgb(BRAND["ink"]), base, 0.24)
        for edge in _preview_crease_edges(faces, face_normals, facing):
            points = [
                (
                    offset_x + screen_x[vertex] * scale,
                    offset_y - screen_y[vertex] * scale,
                )
                for vertex in edge
            ]
            draw.line(points, fill=crease_color, width=2)
    if preview_note:
        note_font = _load_font(18, condensed=True)
        note_width = min(width - 250, max(520, len(preview_note) * 10))
        note_left = (width - note_width) / 2
        note_top = height - 142
        draw.rounded_rectangle(
            (note_left, note_top, note_left + note_width, note_top + 36),
            radius=18,
            fill="#09131D",
            outline=accent,
            width=2,
        )
        draw.ellipse(
            (note_left + 14, note_top + 10, note_left + 30, note_top + 26),
            outline=accent,
            width=3,
        )
        draw.text(
            (width / 2 + 10, note_top + 19),
            preview_note,
            font=note_font,
            fill=BRAND["cream"],
            anchor="mm",
        )
    if reported_extents_mm is None:
        extents = vertices.max(axis=0) - vertices.min(axis=0)
    else:
        extents = np.asarray(reported_extents_mm, dtype=np.float64).reshape(3)
        if not np.isfinite(extents).all() or (extents < 0.0).any():
            raise ValueError("reported extents must contain three finite values")
    dimensions = (
        f"{dimension_label}: "
        + " x ".join(f"{value:.1f}" for value in extents)
        + " mm"
    )
    draw.text(
        (width // 2, height - 68),
        dimensions,
        font=_load_font(20, bold=False, condensed=True),
        fill="#9FB0BE",
        anchor="mm",
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=False, compress_level=9)
    return destination


def render_preview_set(
    mesh: Any,
    output_directory: str | Path,
    *,
    stem: str,
    title: str,
    orientation: str = "flat",
    accent: str = BRAND["lime"],
) -> dict[str, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    vertices, _ = _mesh_arrays(mesh, strict=False)
    physical_extents = vertices.max(axis=0) - vertices.min(axis=0)
    identity = f"{stem} {title}".lower().replace("-", "_")
    all_four = any(
        marker in identity
        for marker in ("all_four", "all four", "all4", "all 4")
    )
    all_four_cameras = {
        # One orthographic camera must see flat media faces and the upright
        # figure together. These compound angles preserve both silhouettes.
        "front": np.array((0.16, -0.72, 0.82)),
        "back": np.array((-0.16, 0.72, -0.82)),
        "detail": np.array((0.88, -1.0, 0.76)),
    }

    def options(view: str) -> dict[str, Any]:
        if all_four:
            note = (
                "SHOWCASE ANGLE | TRUE PHYSICAL PLATE SIZE BELOW"
                if view != "back"
                else "CENTER 25 MM NFC TAGS ON MARKED MEDIA RINGS + FIGURE BASE"
            )
            return {
                "camera_direction": all_four_cameras[view],
                "camera_up": np.array((0.0, 0.0, 1.0)),
                "reported_extents_mm": physical_extents,
                "dimension_label": "PHYSICAL PLATE LAYOUT",
                "preview_note": note,
            }
        note = None
        if view == "back":
            note = (
                "CENTER 25 MM ADHESIVE NFC TAG UNDER BASE"
                if orientation == "upright"
                else "CENTER 25 MM ADHESIVE NFC TAG ON REAR LANDING"
            )
        return {
            "reported_extents_mm": physical_extents,
            "dimension_label": "MODEL SIZE",
            "preview_note": note,
        }

    return {
        view: render_mesh_preview(
            mesh,
            output / f"{stem}_{view.upper()}.png",
            title=title,
            view=view,
            orientation=orientation,
            accent=accent,
            **options(view),
        )
        for view in ("front", "back", "detail")
    }


class _SVGCanvas:
    def __init__(self, width: float, height: float, background: str | None = None):
        self.width = width
        self.height = height
        self.elements: list[str] = []
        if background:
            self.rect(0, 0, width, height, fill=background)

    def circle(self, x, y, radius, *, fill="none", stroke=None, width=0.0):
        stroke_part = f' stroke="{stroke}" stroke-width="{width}"' if stroke else ""
        self.elements.append(
            f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}"{stroke_part}/>'
        )

    def rect(self, x, y, width, height, *, fill="none", stroke=None, line_width=0.0, radius=0.0):
        stroke_part = f' stroke="{stroke}" stroke-width="{line_width}"' if stroke else ""
        radius_part = f' rx="{radius}"' if radius else ""
        self.elements.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{fill}"'
            f"{stroke_part}{radius_part}/>"
        )

    def line(self, points, *, fill, width=0.5, closed=False):
        point_text = " ".join(f"{x},{y}" for x, y in points)
        tag = "polygon" if closed else "polyline"
        fill_value = fill if closed else "none"
        self.elements.append(
            f'<{tag} points="{point_text}" fill="{fill_value}" stroke="{fill}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    def arc(self, x, y, radius, start, end, *, stroke, width=0.5):
        start_radians = math.radians(start)
        end_radians = math.radians(end)
        x1 = x + radius * math.cos(start_radians)
        y1 = y + radius * math.sin(start_radians)
        x2 = x + radius * math.cos(end_radians)
        y2 = y + radius * math.sin(end_radians)
        large = 1 if abs(end - start) > 180 else 0
        self.elements.append(
            f'<path d="M {x1} {y1} A {radius} {radius} 0 {large} 1 {x2} {y2}" '
            f'fill="none" stroke="{stroke}" stroke-width="{width}" stroke-linecap="round"/>'
        )

    def text(self, value, x, y, size, *, fill, anchor="center", bold=True, condensed=True, max_width=None):
        text_anchor = {"center": "middle", "left": "start", "right": "end"}[anchor]
        weight = "900" if bold else "400"
        stretch = "condensed" if condensed else "normal"
        length = (
            f' textLength="{max_width}" lengthAdjust="spacingAndGlyphs"'
            if max_width
            else ""
        )
        self.elements.append(
            f'<text x="{x}" y="{y}" text-anchor="{text_anchor}" '
            f'dominant-baseline="middle" font-family="DejaVu Sans, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" font-stretch="{stretch}" '
            f'fill="{fill}"{length}>{html.escape(str(value))}</text>'
        )

    def document(self, *, width_mm: float, height_mm: float, title: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" '
            f'height="{height_mm}mm" viewBox="0 0 {self.width} {self.height}">\n'
            f"<title>{html.escape(title)}</title>\n"
            f"<metadata>{html.escape(NON_METALLIC_STOCK_WARNING)}</metadata>\n"
            + "\n".join(self.elements)
            + "\n</svg>\n"
        )


class _PillowCanvas:
    def __init__(
        self,
        width: float,
        height: float,
        *,
        dpi: int,
        background: str | None = None,
        transparent: bool = False,
    ):
        self.width = width
        self.height = height
        self.dpi = dpi
        self.scale = dpi / 25.4
        mode = "RGBA" if transparent else "RGB"
        base = (0, 0, 0, 0) if transparent else (255, 255, 255)
        if background:
            base = _hex_rgb(background) + ((255,) if transparent else ())
        self.image = Image.new(
            mode,
            (max(1, round(width * self.scale)), max(1, round(height * self.scale))),
            base,
        )
        self.draw = ImageDraw.Draw(self.image)

    def _p(self, value):
        return round(float(value) * self.scale)

    def circle(self, x, y, radius, *, fill="none", stroke=None, width=0.0):
        box = tuple(self._p(value) for value in (x - radius, y - radius, x + radius, y + radius))
        self.draw.ellipse(
            box,
            fill=None if fill == "none" else fill,
            outline=stroke,
            width=max(1, self._p(width)) if stroke else 1,
        )

    def rect(self, x, y, width, height, *, fill="none", stroke=None, line_width=0.0, radius=0.0):
        box = tuple(self._p(value) for value in (x, y, x + width, y + height))
        self.draw.rounded_rectangle(
            box,
            radius=self._p(radius),
            fill=None if fill == "none" else fill,
            outline=stroke,
            width=max(1, self._p(line_width)) if stroke else 1,
        )

    def line(self, points, *, fill, width=0.5, closed=False):
        pixels = [(self._p(x), self._p(y)) for x, y in points]
        if closed:
            self.draw.polygon(pixels, fill=fill)
        else:
            self.draw.line(
                pixels,
                fill=fill,
                width=max(1, self._p(width)),
                joint="curve",
            )

    def arc(self, x, y, radius, start, end, *, stroke, width=0.5):
        box = tuple(self._p(value) for value in (x - radius, y - radius, x + radius, y + radius))
        self.draw.arc(
            box,
            start=start,
            end=end,
            fill=stroke,
            width=max(1, self._p(width)),
        )

    def text(self, value, x, y, size, *, fill, anchor="center", bold=True, condensed=True, max_width=None):
        pixel_size = max(1, self._p(size))
        font = _load_font(pixel_size, bold=bold, condensed=condensed)
        if max_width:
            target = self._p(max_width)
            while pixel_size > 4:
                bounds = self.draw.textbbox((0, 0), str(value), font=font)
                if bounds[2] - bounds[0] <= target:
                    break
                pixel_size -= 1
                font = _load_font(pixel_size, bold=bold, condensed=condensed)
        pillow_anchor = {"center": "mm", "left": "lm", "right": "rm"}[anchor]
        self.draw.text(
            (self._p(x), self._p(y)),
            str(value),
            font=font,
            fill=fill,
            anchor=pillow_anchor,
        )


def _draw_nfc_waves(canvas, x: float, y: float, color: str, scale: float = 1.0):
    canvas.circle(x, y, 0.65 * scale, fill=color)
    for radius in (2.0, 3.35, 4.75):
        canvas.arc(x, y, radius * scale, -52, 52, stroke=color, width=0.70 * scale)


def _overlay_text(
    canvas,
    value: str,
    x: float,
    y: float,
    size: float,
    *,
    fill: str,
    max_width: float,
    anchor: str = "center",
    bold: bool = True,
    condensed: bool = True,
):
    """Draw overlay text only when its conservative box clears the cut edge."""

    width = float(max_width)
    half_height = float(size) * 0.62
    if anchor == "center":
        center_x = float(x)
    elif anchor == "left":
        center_x = float(x) + width / 2
    elif anchor == "right":
        center_x = float(x) - width / 2
    else:
        raise ValueError(f"unsupported overlay text anchor: {anchor!r}")
    corners = (
        (center_x - width / 2, float(y) - half_height),
        (center_x + width / 2, float(y) - half_height),
        (center_x - width / 2, float(y) + half_height),
        (center_x + width / 2, float(y) + half_height),
    )
    furthest = max(
        math.hypot(px - 12.5, py - 12.5) for px, py in corners
    )
    if furthest > OVERLAY_TEXT_SAFE_RADIUS_MM + 1e-9:
        raise ValueError(
            f"overlay text {value!r} exceeds the circular safe inset: "
            f"{furthest:.3f} mm > {OVERLAY_TEXT_SAFE_RADIUS_MM:.3f} mm"
        )
    canvas.text(
        value,
        x,
        y,
        size,
        fill=fill,
        anchor=anchor,
        bold=bold,
        condensed=condensed,
        max_width=max_width,
    )


def _draw_overlay(canvas, spec: OverlaySpec):
    canvas.circle(12.5, 12.5, 12.5, fill=BRAND["ink"])
    # The edge remains solid full-bleed ink. Moving the identity ring inward
    # prevents a slightly off-center 25 mm cut from leaving an uneven border.
    canvas.circle(
        12.5,
        12.5,
        OVERLAY_SAFE_RADIUS_MM,
        fill="none",
        stroke=spec.accent,
        width=0.48,
    )
    if spec.motif == "cassette":
        _overlay_text(canvas, spec.title, 12.5, 3.60, 1.70, fill=spec.accent, max_width=10.8)
        _overlay_text(canvas, spec.subtitle, 12.5, 6.25, 2.20, fill=BRAND["cream"], max_width=15.0)
        canvas.rect(3.5, 7.8, 18.0, 9.1, fill=BRAND["panel"], stroke=BRAND["cream"], line_width=0.48, radius=1.0)
        for x in (7.7, 17.3):
            canvas.circle(x, 12.05, 2.55, fill="none", stroke=spec.accent, width=0.88)
            canvas.circle(x, 12.05, 1.0, fill=BRAND["cream"])
            canvas.circle(x, 12.05, 0.42, fill=BRAND["ink"])
        canvas.rect(10.3, 10.25, 4.4, 3.55, fill=BRAND["cream"], radius=0.45)
        canvas.rect(11.2, 10.78, 2.6, 2.5, fill=BRAND["panel"], radius=0.25)
        _overlay_text(canvas, "TAP", 12.5, 19.35, 3.00, fill=spec.accent, max_width=8.4)
        _overlay_text(canvas, "TO PLAY", 12.5, 22.10, 1.55, fill=BRAND["cream"], max_width=7.6)
    elif spec.motif == "floppy":
        _overlay_text(canvas, spec.title, 12.5, 3.80, 1.75, fill=spec.accent, max_width=9.8)
        # A printed gray, explicitly non-metal ink illusion of the real rear
        # drive hub: one central clamp opening and one offset engagement slot.
        canvas.circle(12.5, 11.7, 5.75, fill=BRAND["steel"], stroke=BRAND["cream"], width=0.35)
        canvas.circle(12.5, 11.7, 4.45, fill=BRAND["steel_dark"])
        canvas.circle(12.5, 11.7, 3.95, fill=BRAND["steel"], stroke=BRAND["steel_dark"], width=0.28)
        canvas.circle(12.5, 11.7, 1.38, fill=BRAND["ink"])
        canvas.rect(15.15, 10.75, 2.30, 1.90, fill=BRAND["ink"], radius=0.30)
        canvas.arc(12.5, 11.7, 4.85, 205, 326, stroke=BRAND["cream"], width=0.30)
        canvas.arc(12.5, 11.7, 4.85, 24, 146, stroke=BRAND["steel_dark"], width=0.30)
        _overlay_text(canvas, spec.subtitle, 12.5, 18.80, 1.95, fill=BRAND["cream"], max_width=13.2)
        _overlay_text(canvas, "TAP", 12.5, 21.45, 2.80, fill=spec.accent, max_width=7.4)
    elif spec.motif == "vhs":
        _overlay_text(canvas, spec.title, 12.5, 3.35, 1.78, fill=spec.accent, max_width=7.8)
        _overlay_text(canvas, "RAD DAD", 12.5, 5.25, 1.92, fill=BRAND["cream"], max_width=12.8)
        # A VHS-specific shell: full-width hinged flap, two rectangular reel
        # windows, circular hubs, and the tapered bottom loading edge.
        canvas.rect(2.95, 6.25, 19.10, 11.85, fill=BRAND["panel"], stroke=BRAND["cream"], line_width=0.48, radius=0.85)
        canvas.rect(3.45, 6.80, 18.10, 2.20, fill=BRAND["steel_dark"], stroke=spec.accent, line_width=0.38, radius=0.35)
        _overlay_text(canvas, "VHS", 12.5, 7.92, 1.58, fill=BRAND["cream"], max_width=5.0)
        for x in (4.15, 13.25):
            canvas.rect(x, 9.50, 7.60, 5.55, fill=BRAND["ink"], stroke=BRAND["cream"], line_width=0.34, radius=0.50)
            canvas.circle(x + 3.80, 12.28, 2.00, fill="none", stroke=spec.accent, width=0.62)
            canvas.circle(x + 3.80, 12.28, 0.67, fill=BRAND["cream"])
        canvas.line(
            ((3.85, 15.65), (21.15, 15.65), (19.70, 17.35), (5.30, 17.35)),
            fill=BRAND["cream"],
            width=0.34,
            closed=True,
        )
        canvas.line(((6.15, 16.50), (18.85, 16.50)), fill=BRAND["panel"], width=0.40)
        _overlay_text(canvas, "TAP", 12.5, 19.55, 3.10, fill=spec.accent, max_width=7.5)
        _overlay_text(canvas, "TO PLAY", 12.5, 22.10, 1.60, fill=BRAND["cream"], max_width=8.0)
    elif spec.motif == "trailer":
        _overlay_text(canvas, "TRAILER", 12.5, 3.60, 1.80, fill=BRAND["cream"], max_width=10.2)
        _overlay_text(canvas, "SWIFT", 12.5, 6.35, 2.60, fill=spec.accent, max_width=9.8)
        left_bolt = ((5.2, 8.4), (9.2, 8.4), (7.5, 12.2), (10.2, 12.2), (5.5, 18.0), (6.9, 13.7), (4.5, 13.7))
        right_bolt = tuple((25.0 - x, y) for x, y in left_bolt)
        canvas.line(left_bolt, fill=BRAND["pink"], closed=True)
        canvas.line(right_bolt, fill=BRAND["pink"], closed=True)
        _overlay_text(canvas, "TAP", 12.5, 13.1, 4.0, fill=BRAND["cream"], max_width=8.2)
        _overlay_text(canvas, "THE BASE", 12.5, 18.0, 2.20, fill=spec.accent, max_width=13.0)
        _overlay_text(canvas, "RAD DAD", 12.5, 21.75, 1.65, fill=BRAND["blue"], max_width=8.4)
    else:
        _draw_nfc_waves(canvas, 6.0, 12.5, BRAND["blue"], 0.82)
        _overlay_text(canvas, "RAD DAD", 16.0, 7.8, 2.25, fill=BRAND["cream"], max_width=12.0)
        _overlay_text(canvas, "TAP", 16.0, 12.5, 4.0, fill=spec.accent, max_width=8.8)
        _overlay_text(canvas, "TO PLAY", 16.0, 17.0, 1.95, fill=BRAND["cream"], max_width=9.8)
        _overlay_text(canvas, "NFC", 16.0, 20.4, 1.62, fill=BRAND["blue"], max_width=5.5)


def _image_pdf_bytes(
    images: Sequence[Image.Image],
    page_sizes_mm: Sequence[tuple[float, float]],
    *,
    trim_boxes_mm: Sequence[tuple[float, float, float, float] | None] | None = None,
) -> bytes:
    if len(images) != len(page_sizes_mm) or not images:
        raise ValueError("PDF images and page sizes must have the same nonzero length")
    if trim_boxes_mm is not None and len(trim_boxes_mm) != len(images):
        raise ValueError("PDF trim boxes must match the image count")
    object_count = 2 + 3 * len(images)
    objects: list[bytes] = [b""] * object_count
    page_ids = [3 + index * 3 for index in range(len(images))]
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(images)} >>".encode("ascii")
    for index, (source, page_mm) in enumerate(zip(images, page_sizes_mm)):
        page_id = page_ids[index]
        image_id = page_id + 1
        content_id = page_id + 2
        image = source.convert("RGBA")
        flattened = Image.new("RGB", image.size, "white")
        flattened.paste(image, mask=image.getchannel("A"))
        raw = flattened.tobytes()
        compressed = zlib.compress(raw, level=9)
        width_pt = page_mm[0] * 72.0 / 25.4
        height_pt = page_mm[1] * 72.0 / 25.4
        name = f"Im{index}"
        page_boxes = ""
        trim_box = trim_boxes_mm[index] if trim_boxes_mm is not None else None
        if trim_box is not None:
            left, bottom, right, top = (float(value) for value in trim_box)
            if not (
                0.0 <= left < right <= float(page_mm[0])
                and 0.0 <= bottom < top <= float(page_mm[1])
            ):
                raise ValueError("PDF trim box must fit inside its page")
            trim_points = tuple(value * 72.0 / 25.4 for value in trim_box)
            page_boxes = (
                f" /BleedBox [0 0 {_format_float(width_pt)} {_format_float(height_pt)}]"
                f" /TrimBox [{_format_float(trim_points[0])} {_format_float(trim_points[1])} "
                f"{_format_float(trim_points[2])} {_format_float(trim_points[3])}]"
            )
        objects[page_id - 1] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_format_float(width_pt)} {_format_float(height_pt)}] "
            f"{page_boxes} "
            f"/Resources << /XObject << /{name} {image_id} 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")
        image_header = (
            f"<< /Type /XObject /Subtype /Image /Width {flattened.width} /Height {flattened.height} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(compressed)} >>\nstream\n"
        ).encode("ascii")
        objects[image_id - 1] = image_header + compressed + b"\nendstream"
        stream = (
            f"q {_format_float(width_pt)} 0 0 {_format_float(height_pt)} 0 0 cm /{name} Do Q\n"
        ).encode("ascii")
        objects[content_id - 1] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"endstream"
        )
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def _write_png(path: Path, image: Image.Image, dpi: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        path,
        format="PNG",
        dpi=(dpi, dpi),
        optimize=False,
        compress_level=9,
    )
    return path


def write_overlay_assets(
    output_directory: str | Path,
    *,
    specs: Mapping[str, OverlaySpec] = OVERLAY_SPECS,
    dpi: int = 600,
) -> dict[str, dict[str, Path]]:
    """Write 25 mm PNG, SVG, and deterministic PDF overlays."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, Path]] = {}
    for key, spec in specs.items():
        stem = f"Rad_Dad_25MM_{key.upper()}_TAP_NFC_OVERLAY_LABEL"
        svg_canvas = _SVGCanvas(25.0, 25.0)
        _draw_overlay(svg_canvas, spec)
        svg_path = _atomic_write_text(
            output / f"{stem}.svg",
            svg_canvas.document(
                width_mm=25.0,
                height_mm=25.0,
                title=f"{spec.title} 25 mm non-metal NFC overlay",
            ),
        )
        png_canvas = _PillowCanvas(
            25.0, 25.0, dpi=dpi, transparent=True
        )
        _draw_overlay(png_canvas, spec)
        png_path = _write_png(output / f"{stem}.png", png_canvas.image, dpi)
        pdf_path = _atomic_write_bytes(
            output / f"{stem}.pdf",
            _image_pdf_bytes([png_canvas.image], [(25.0, 25.0)]),
        )
        results[key] = {"svg": svg_path, "png": png_path, "pdf": pdf_path}
    return results


def _sheet_image(
    specs: Sequence[OverlaySpec],
    *,
    copies_each: int,
    dpi: int,
    title: str,
) -> Image.Image:
    width_mm, height_mm = 215.9, 279.4
    canvas = _PillowCanvas(width_mm, height_mm, dpi=dpi, background="#FFFFFF")
    canvas.text(title, width_mm / 2, 9.0, 5.0, fill=BRAND["ink"], max_width=180.0)
    columns = len(specs)
    if columns < 1:
        raise ValueError("at least one overlay specification is required")
    x_centers = np.linspace(29.5, width_mm - 29.5, columns)
    y_centers = np.linspace(35.0, 235.0, copies_each)
    label_pixels = round(OVERLAY_DIAMETER_MM * dpi / 25.4)
    for column, spec in enumerate(specs):
        overlay = _PillowCanvas(25.0, 25.0, dpi=dpi, transparent=True)
        _draw_overlay(overlay, spec)
        resized = overlay.image.resize((label_pixels, label_pixels), Image.Resampling.LANCZOS)
        for center_y in y_centers:
            canvas.circle(
                x_centers[column],
                center_y,
                OVERLAY_DIAMETER_MM / 2 + OVERLAY_BLEED_MM,
                fill=BRAND["ink"],
            )
            x = round((x_centers[column] - 12.5) * dpi / 25.4)
            y = round((center_y - 12.5) * dpi / 25.4)
            canvas.image.paste(resized, (x, y), resized)
            canvas.circle(
                x_centers[column],
                center_y,
                OVERLAY_DIAMETER_MM / 2,
                fill="none",
                stroke="#B9C0C6",
                width=OVERLAY_CUT_GUIDE_WIDTH_MM,
            )
        canvas.text(
            spec.key.replace("_", " ").upper(),
            x_centers[column],
            253.0,
            2.8,
            fill=BRAND["ink"],
            max_width=36.0,
        )
    canvas.text(
        "PRINT AT 100% | EACH CIRCLE IS 25 MM",
        width_mm / 2,
        262.0,
        2.70,
        fill=BRAND["ink"],
        max_width=170.0,
    )
    canvas.text(
        "CUT ON 25 MM HAIRLINE | 1 MM BLEED PROTECTS SMALL REGISTRATION ERRORS",
        width_mm / 2,
        267.5,
        2.35,
        fill=BRAND["ink"],
        max_width=190.0,
    )
    canvas.text(
        "NON-METALLIC PAPER OR VINYL ONLY | NO FOIL | NO METAL-BACKED STOCK",
        width_mm / 2,
        273.0,
        2.35,
        fill=BRAND["pink"],
        max_width=190.0,
    )
    return canvas.image


def _sheet_svg(
    specs: Sequence[OverlaySpec],
    *,
    copies_each: int,
    title: str,
) -> str:
    width_mm, height_mm = 215.9, 279.4
    groups = []
    bleeds = []
    uses = []
    cut_guides = []
    x_centers = np.linspace(29.5, width_mm - 29.5, len(specs))
    y_centers = np.linspace(35.0, 235.0, copies_each)
    for column, spec in enumerate(specs):
        art = _SVGCanvas(25.0, 25.0)
        _draw_overlay(art, spec)
        groups.append(f'<g id="overlay-{spec.key}">' + "".join(art.elements) + "</g>")
        for center_y in y_centers:
            bleeds.append(
                f'<circle cx="{x_centers[column]}" cy="{center_y}" '
                f'r="{OVERLAY_DIAMETER_MM / 2 + OVERLAY_BLEED_MM}" fill="{BRAND["ink"]}"/>'
            )
            uses.append(
                f'<use href="#overlay-{spec.key}" x="{x_centers[column] - 12.5}" y="{center_y - 12.5}"/>'
            )
            cut_guides.append(
                f'<circle cx="{x_centers[column]}" cy="{center_y}" '
                f'r="{OVERLAY_DIAMETER_MM / 2}" fill="none" stroke="#B9C0C6" '
                f'stroke-width="{OVERLAY_CUT_GUIDE_WIDTH_MM}"/>'
            )
    labels = "".join(
        f'<text x="{x_centers[index]}" y="253" text-anchor="middle" '
        f'font-family="DejaVu Sans, sans-serif" font-size="2.8" font-weight="bold">'
        f'{html.escape(spec.key.replace("_", " ").upper())}</text>'
        for index, spec in enumerate(specs)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" height="{height_mm}mm" '
        f'viewBox="0 0 {width_mm} {height_mm}">\n'
        f"<metadata>{html.escape(NON_METALLIC_STOCK_WARNING)}</metadata>"
        '<rect width="100%" height="100%" fill="white"/>'
        f'<text x="107.95" y="9" text-anchor="middle" font-family="DejaVu Sans, sans-serif" '
        f'font-size="5" font-weight="900">{html.escape(title)}</text>'
        "<defs>" + "".join(groups) + "</defs>" + "".join(bleeds) + "".join(uses)
        + "".join(cut_guides) + labels
        + '<text x="107.95" y="262" text-anchor="middle" font-family="DejaVu Sans, sans-serif" '
        'font-size="2.7" font-weight="bold">PRINT AT 100% | EACH FINISHED CIRCLE IS 25 MM</text>'
        '<text x="107.95" y="267.5" text-anchor="middle" font-family="DejaVu Sans, sans-serif" '
        'font-size="2.35" font-weight="bold">CUT ON 25 MM HAIRLINE | 1 MM BLEED PROTECTS SMALL REGISTRATION ERRORS</text>'
        '<text x="107.95" y="273" text-anchor="middle" font-family="DejaVu Sans, sans-serif" '
        'font-size="2.35" font-weight="bold" fill="#FF3476">NON-METALLIC PAPER OR VINYL ONLY | NO FOIL | NO METAL-BACKED STOCK</text>'
        "</svg>\n"
    )


def write_overlay_sheets(
    output_directory: str | Path,
    *,
    dpi: int = 300,
) -> dict[str, dict[str, Path]]:
    """Write a mixed 20-up sheet and a generic 20-up backup sheet."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    configurations = {
        "mixed": (
            [
                OVERLAY_SPECS["cassette"],
                OVERLAY_SPECS["floppy"],
                OVERLAY_SPECS["vhs"],
                OVERLAY_SPECS["trailer_swift"],
            ],
            5,
            "RAD DAD MICRO REPLICAS v7 | MIXED 20-UP",
        ),
        "generic_backup": (
            [OVERLAY_SPECS["generic"]] * 4,
            5,
            "RAD DAD MICRO REPLICAS v7 | GENERIC BACKUP 20-UP",
        ),
    }
    results: dict[str, dict[str, Path]] = {}
    for key, (specs, copies_each, title) in configurations.items():
        stem = f"Rad_Dad_25MM_{key.upper()}_TAP_LABEL_SHEET_20UP_US_LETTER"
        image = _sheet_image(specs, copies_each=copies_each, dpi=dpi, title=title)
        png_path = _write_png(output / f"{stem}.png", image, dpi)
        svg_path = _atomic_write_text(
            output / f"{stem}.svg",
            _sheet_svg(specs, copies_each=copies_each, title=title),
        )
        pdf_path = _atomic_write_bytes(
            output / f"{stem}.pdf",
            _image_pdf_bytes([image], [(215.9, 279.4)]),
        )
        results[key] = {"svg": svg_path, "png": png_path, "pdf": pdf_path}
    return results


def write_nfc_placement_guide(output_directory: str | Path) -> Path:
    """Write a one-page SVG showing the marked-circle location on all products."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    panels = (
        ("CASSETTE", "FLAT REAR", 250, 315, BRAND["lime"]),
        ("FLOPPY", "REAR HUB LANDING", 850, 315, BRAND["blue"]),
        ("VHS", "FLAT REAR", 250, 650, BRAND["pink"]),
        ("TRAILER SWIFT", "UNDER THE BASE", 850, 650, BRAND["amber"]),
    )
    body = []
    for title, location, x, y, accent in panels:
        body.extend(
            (
                f'<rect x="{x - 225}" y="{y - 125}" width="450" height="250" rx="22" fill="#0C1722" stroke="{accent}" stroke-width="6"/>',
                f'<circle cx="{x}" cy="{y}" r="66" fill="none" stroke="{accent}" stroke-width="12"/>',
                f'<circle cx="{x}" cy="{y}" r="10" fill="{accent}"/>',
                f'<text x="{x}" y="{y - 78}" text-anchor="middle" font-family="sans-serif" font-size="32" font-weight="bold" fill="#F5F1E8">{title}</text>',
                f'<text x="{x}" y="{y + 108}" text-anchor="middle" font-family="sans-serif" font-size="24" font-weight="bold" fill="{accent}">{location}</text>',
            )
        )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="279.4mm" height="215.9mm" viewBox="0 0 1100 850">'
        '<rect width="1100" height="850" fill="#050B12"/>'
        '<text x="550" y="72" text-anchor="middle" font-family="sans-serif" font-size="46" font-weight="bold" fill="#F5F1E8">FIND THE MARKED CIRCLE</text>'
          '<text x="550" y="116" text-anchor="middle" font-family="sans-serif" font-size="25" fill="#A6EF12">TOUCH YOUR UNLOCKED PHONE TO IT</text>'
          + "".join(body)
          + f'<text x="550" y="808" text-anchor="middle" font-family="sans-serif" font-size="20" font-weight="bold" fill="#F5F1E8">{html.escape(ROOT_TAGLINE)}</text>'
          + '<text x="550" y="834" text-anchor="middle" font-family="sans-serif" font-size="17" fill="#FF3476">NON-METALLIC PAPER, VINYL, AND INK ONLY.</text></svg>\n'
    )
    return _atomic_write_text(output / "Rad_Dad_NFC_Placement_Guide.svg", svg)


# Core Image-generated QR, error correction Q, for DEFAULT_TAP_URL. The outer
# one-module white border is removed below; renderers add the standard four.
_DEFAULT_QR_WITH_ONE_MODULE_BORDER = (
    "0000000000000000000000000000000",
    "0111111100101011011111011111110",
    "0100000101110010100010010000010",
    "0101110100000011100101010111010",
    "0101110101101010001011010111010",
    "0101110101111001110110010111010",
    "0100000100000100000001010000010",
    "0111111101010101010101011111110",
    "0000000001011000011111000000000",
    "0010111101110000100010110110100",
    "0001010010110111110111000111100",
    "0010001100100001001001110101000",
    "0100100001011000011100000000010",
    "0101110111010111100011110010100",
    "0110010001010101100100010101010",
    "0101100100101100110110001010010",
    "0011101010111000110011100111000",
    "0101000111110000101100001010010",
    "0101001001110100001011100111000",
    "0111000111000000011110000010010",
    "0110001010011001110011111001110",
    "0111111101010111011011111111100",
    "0000000001111100101111000111000",
    "0111111100000101100011010101000",
    "0100000101010001110111000110110",
    "0101110101010010101011111100110",
    "0101110101000101000100001011100",
    "0101110100100001100001101101110",
    "0100000101000000010100110111010",
    "0111111100011111100011101100000",
    "0000000000000000000000000000000",
)


def qr_matrix(
    url: str = DEFAULT_TAP_URL,
    *,
    encoder: Callable[[str], Sequence[Sequence[bool]]] | None = None,
) -> list[list[bool]]:
    """Return a QR module matrix without a quiet zone.

    The default URL has an embedded, offline matrix. A custom URL requires an
    injected encoder so this module never silently substitutes a fake QR code.
    """

    if encoder is not None:
        matrix = [[bool(value) for value in row] for row in encoder(url)]
        if not matrix or any(len(row) != len(matrix) for row in matrix):
            raise ValueError("QR encoder must return a nonempty square matrix")
        return matrix
    if url != DEFAULT_TAP_URL:
        raise ValueError(
            "custom QR URLs require an encoder callable; the bundled matrix is "
            f"only for {DEFAULT_TAP_URL}"
        )
    rows = _DEFAULT_QR_WITH_ONE_MODULE_BORDER[1:-1]
    return [[value == "1" for value in row[1:-1]] for row in rows]


def _draw_qr(canvas, matrix, x: float, y: float, size: float, quiet: int = 4):
    count = len(matrix)
    module = size / (count + quiet * 2)
    canvas.rect(x, y, size, size, fill="#FFFFFF")
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            if value:
                canvas.rect(
                    x + (column_index + quiet) * module,
                    y + (row_index + quiet) * module,
                    module,
                    module,
                    fill="#000000",
                )


def _draw_handoff_crop_marks(canvas, *, stroke: str):
    """Draw trim-only crop guidance entirely outside the finished card."""

    left = HANDOFF_BLEED_MM
    top = HANDOFF_BLEED_MM
    right = left + HANDOFF_TRIM_WIDTH_MM
    bottom = top + HANDOFF_TRIM_HEIGHT_MM
    outer = 0.35
    gap = 0.60
    width = 0.22
    segments = (
        ((outer, top), (left - gap, top)),
        ((left, outer), (left, top - gap)),
        ((right + gap, top), (HANDOFF_ART_WIDTH_MM - outer, top)),
        ((right, outer), (right, top - gap)),
        ((outer, bottom), (left - gap, bottom)),
        ((left, bottom + gap), (left, HANDOFF_ART_HEIGHT_MM - outer)),
        ((right + gap, bottom), (HANDOFF_ART_WIDTH_MM - outer, bottom)),
        ((right, bottom + gap), (right, HANDOFF_ART_HEIGHT_MM - outer)),
    )
    for start, end in segments:
        canvas.line((start, end), fill=stroke, width=width)


def _draw_handoff_front(canvas, *, offset_x: float = 0.0, offset_y: float = 0.0):
    canvas.rect(
        offset_x,
        offset_y,
        HANDOFF_TRIM_WIDTH_MM,
        HANDOFF_TRIM_HEIGHT_MM,
        fill=BRAND["ink"],
        radius=3.0,
    )
    canvas.rect(
        offset_x + HANDOFF_SAFE_INSET_MM,
        offset_y + HANDOFF_SAFE_INSET_MM,
        HANDOFF_TRIM_WIDTH_MM - 2 * HANDOFF_SAFE_INSET_MM,
        HANDOFF_TRIM_HEIGHT_MM - 2 * HANDOFF_SAFE_INSET_MM,
        fill="none",
        stroke=BRAND["lime"],
        line_width=0.8,
        radius=2.0,
    )
    _draw_nfc_waves(canvas, offset_x + 10.0, offset_y + 25.4, BRAND["blue"], 1.45)
    canvas.text("RAD DAD // MICRO REPLICAS", offset_x + 54.0, offset_y + 7.7, 3.4, fill=BRAND["pink"], max_width=61.0)
    canvas.text(ROOT_TAGLINE, offset_x + 54.0, offset_y + 17.2, 3.65, fill=BRAND["cream"], max_width=62.0)
    canvas.text("FIND THE MARKED CIRCLE.", offset_x + 54.0, offset_y + 29.7, 3.3, fill=BRAND["lime"], max_width=63.0)
    canvas.text("TOUCH YOUR UNLOCKED PHONE TO IT.", offset_x + 54.0, offset_y + 36.5, 2.55, fill=BRAND["blue"], max_width=65.0)
    canvas.text("RADDADBAND.COM/TAP", offset_x + 54.0, offset_y + 44.4, 2.7, fill=BRAND["cream"], max_width=42.0)


def _draw_handoff_back(
    canvas,
    matrix,
    *,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
):
    canvas.rect(
        offset_x,
        offset_y,
        HANDOFF_TRIM_WIDTH_MM,
        HANDOFF_TRIM_HEIGHT_MM,
        fill=BRAND["cream"],
        radius=3.0,
    )
    canvas.rect(
        offset_x + HANDOFF_SAFE_INSET_MM,
        offset_y + HANDOFF_SAFE_INSET_MM,
        HANDOFF_TRIM_WIDTH_MM - 2 * HANDOFF_SAFE_INSET_MM,
        HANDOFF_TRIM_HEIGHT_MM - 2 * HANDOFF_SAFE_INSET_MM,
        fill="none",
        stroke=BRAND["ink"],
        line_width=0.8,
        radius=2.0,
    )
    _draw_qr(canvas, matrix, offset_x + 5.0, offset_y + 8.0, 34.8)
    canvas.text("SCAN BACKUP", offset_x + 22.4, offset_y + 45.2, 2.5, fill=BRAND["ink"], max_width=29.0)
    canvas.text("TAP IT", offset_x + 63.5, offset_y + 9.0, 5.2, fill=BRAND["pink"], max_width=30.0)
    canvas.text("HOLD FOR 1-2 SECONDS", offset_x + 63.5, offset_y + 17.0, 2.7, fill=BRAND["ink"], max_width=39.0)
    canvas.text("THEN TAP THE POP-UP", offset_x + 63.5, offset_y + 22.1, 2.7, fill=BRAND["ink"], max_width=39.0)
    canvas.text("NO POP-UP?", offset_x + 63.5, offset_y + 30.0, 2.8, fill=BRAND["blue"], max_width=25.0)
    canvas.text("MOVE THE PHONE SLOWLY", offset_x + 63.5, offset_y + 35.0, 2.25, fill=BRAND["ink"], max_width=39.0)
    canvas.text("OR REMOVE A THICK/METAL CASE", offset_x + 63.5, offset_y + 39.0, 1.85, fill=BRAND["ink"], max_width=40.0)
    canvas.text("RADDADBAND.COM/TAP", offset_x + 63.5, offset_y + 45.0, 2.4, fill=BRAND["ink"], max_width=35.0)


def write_handoff_card_assets(
    output_directory: str | Path,
    *,
    url: str = DEFAULT_TAP_URL,
    dpi: int = 600,
    qr_encoder: Callable[[str], Sequence[Sequence[bool]]] | None = None,
) -> dict[str, Path]:
    """Write two-sided business-card-size PNG/SVG and a two-page PDF."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    matrix = qr_matrix(url, encoder=qr_encoder)
    front_svg = _SVGCanvas(HANDOFF_ART_WIDTH_MM, HANDOFF_ART_HEIGHT_MM, background=BRAND["ink"])
    back_svg = _SVGCanvas(HANDOFF_ART_WIDTH_MM, HANDOFF_ART_HEIGHT_MM, background=BRAND["cream"])
    _draw_handoff_front(front_svg, offset_x=HANDOFF_BLEED_MM, offset_y=HANDOFF_BLEED_MM)
    _draw_handoff_back(back_svg, matrix, offset_x=HANDOFF_BLEED_MM, offset_y=HANDOFF_BLEED_MM)
    _draw_handoff_crop_marks(front_svg, stroke=BRAND["cream"])
    _draw_handoff_crop_marks(back_svg, stroke=BRAND["ink"])
    front_png = _PillowCanvas(HANDOFF_ART_WIDTH_MM, HANDOFF_ART_HEIGHT_MM, dpi=dpi, background=BRAND["ink"])
    back_png = _PillowCanvas(HANDOFF_ART_WIDTH_MM, HANDOFF_ART_HEIGHT_MM, dpi=dpi, background=BRAND["cream"])
    _draw_handoff_front(front_png, offset_x=HANDOFF_BLEED_MM, offset_y=HANDOFF_BLEED_MM)
    _draw_handoff_back(back_png, matrix, offset_x=HANDOFF_BLEED_MM, offset_y=HANDOFF_BLEED_MM)
    _draw_handoff_crop_marks(front_png, stroke=BRAND["cream"])
    _draw_handoff_crop_marks(back_png, stroke=BRAND["ink"])
    trim_box = (
        HANDOFF_BLEED_MM,
        HANDOFF_BLEED_MM,
        HANDOFF_BLEED_MM + HANDOFF_TRIM_WIDTH_MM,
        HANDOFF_BLEED_MM + HANDOFF_TRIM_HEIGHT_MM,
    )
    paths = {
        "front_svg": _atomic_write_text(
            output / "Rad_Dad_NFC_HANDOFF_CARD_FRONT.svg",
            front_svg.document(
                width_mm=HANDOFF_ART_WIDTH_MM,
                height_mm=HANDOFF_ART_HEIGHT_MM,
                title="Rad Dad NFC handoff card front, 3.5 x 2 inch trim plus 0.125 inch bleed",
            ),
        ),
        "back_svg": _atomic_write_text(
            output / "Rad_Dad_NFC_HANDOFF_CARD_BACK.svg",
            back_svg.document(
                width_mm=HANDOFF_ART_WIDTH_MM,
                height_mm=HANDOFF_ART_HEIGHT_MM,
                title="Rad Dad NFC handoff card back, 3.5 x 2 inch trim plus 0.125 inch bleed",
            ),
        ),
        "front_png": _write_png(
            output / "Rad_Dad_NFC_HANDOFF_CARD_FRONT.png", front_png.image, dpi
        ),
        "back_png": _write_png(
            output / "Rad_Dad_NFC_HANDOFF_CARD_BACK.png", back_png.image, dpi
        ),
        "pdf": _atomic_write_bytes(
            output / "Rad_Dad_NFC_HANDOFF_CARD_FRONT_BACK.pdf",
            _image_pdf_bytes(
                [front_png.image, back_png.image],
                [
                    (HANDOFF_ART_WIDTH_MM, HANDOFF_ART_HEIGHT_MM),
                    (HANDOFF_ART_WIDTH_MM, HANDOFF_ART_HEIGHT_MM),
                ],
                trim_boxes_mm=[trim_box, trim_box],
            ),
        ),
    }
    return paths


def mesh_qa_record(
    name: str,
    mesh: Any,
    *,
    build_volume_mm: tuple[float, float, float] = (180.0, 180.0, 180.0),
) -> dict[str, Any]:
    vertices, faces = _mesh_arrays(mesh, strict=False)
    edges = np.sort(
        np.vstack((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)])),
        axis=1,
    )
    _, edge_counts = np.unique(edges, axis=0, return_counts=True)
    boundary_edges = int((edge_counts == 1).sum())
    non_manifold_edges = int((edge_counts > 2).sum())
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    areas = np.linalg.norm(cross, axis=1) * 0.5
    minimum = vertices.min(axis=0)
    maximum = vertices.max(axis=0)
    extents = maximum - minimum
    body_count = int(getattr(mesh, "body_count", 0) or 0)
    watertight = bool(getattr(mesh, "is_watertight", boundary_edges == 0 and non_manifold_edges == 0))
    winding = bool(getattr(mesh, "is_winding_consistent", False))
    volume = float(getattr(mesh, "volume", 0.0))
    center_mass_value = getattr(mesh, "center_mass", None)
    center_mass = (
        [round(float(value), 6) for value in np.asarray(center_mass_value).reshape(3)]
        if center_mass_value is not None
        else None
    )
    fits = bool(np.all(extents <= np.asarray(build_volume_mm) + 1e-9))
    checks = {
        "finite_vertices": bool(np.isfinite(vertices).all()),
        "triangles_present": bool(len(faces) > 0),
        "watertight": watertight,
        "winding_consistent": winding,
        "single_body": body_count == 1,
        "zero_boundary_edges": boundary_edges == 0,
        "zero_non_manifold_edges": non_manifold_edges == 0,
        "zero_degenerate_faces": bool((areas <= 1e-12).sum() == 0),
        "fits_a1_mini_build_volume": fits,
    }
    return {
        "name": name,
        "vertices": int(len(vertices)),
        "faces": int(len(faces)),
        "body_count": body_count,
        "watertight": watertight,
        "winding_consistent": winding,
        "boundary_edges": boundary_edges,
        "non_manifold_edges": non_manifold_edges,
        "degenerate_faces": int((areas <= 1e-12).sum()),
        "bounds_mm": {
            "minimum": [round(float(value), 6) for value in minimum],
            "maximum": [round(float(value), 6) for value in maximum],
        },
        "dimensions_mm": [round(float(value), 6) for value in extents],
        "surface_area_mm2": round(float(areas.sum()), 6),
        "volume_mm3": round(volume, 6),
        "center_mass_mm": center_mass,
        "checks": checks,
        "digital_qa_pass": all(checks.values()),
        "physical_validation": "required-before-batch-production",
    }


def write_mesh_qa_json(
    path: str | Path,
    models: Mapping[str, Any],
    *,
    release_name: str = "Rad Dad Micro Replicas v7",
    build_volume_mm: tuple[float, float, float] = (180.0, 180.0, 180.0),
    print_intents: Mapping[str, BambuPrintIntent] = DEFAULT_PRINT_INTENTS,
) -> Path:
    records = [
        mesh_qa_record(name, models[name], build_volume_mm=build_volume_mm)
        for name in sorted(models)
    ]
    document = {
        "schema": "rad-dad-mesh-qa-v1",
        "release": release_name,
        "build_volume_mm": list(build_volume_mm),
        "models": records,
        "mesh_qa_pass": all(record["digital_qa_pass"] for record in records),
        "physical_validation": "required-before-batch-production",
        "print_intents": {
            key: asdict(value) for key, value in sorted(print_intents.items())
        },
        "three_mf_policy": {
            "core_3mf": "model-only",
            "bambu_project_3mf": "requires-external-verified-postprocessor",
        },
    }
    return _atomic_write_text(path, json.dumps(document, indent=2, sort_keys=True) + "\n")


def write_release_documents(
    release_root: str | Path,
    *,
    release_name: str = "Rad Dad Micro Replicas v7",
    tap_url: str = DEFAULT_TAP_URL,
    print_intents: Mapping[str, BambuPrintIntent] = DEFAULT_PRINT_INTENTS,
    bambu_project_files: Mapping[str, str | Path] | None = None,
) -> dict[str, Path]:
    """Generate release, NFC, print-profile, and physical-QC documentation."""

    layout = create_release_layout(release_root)
    projects = {
        key: Path(value).name for key, value in (bambu_project_files or {}).items()
    }
    status_lines = []
    for key, intent in sorted(print_intents.items()):
        if key in projects:
            status = f"true Bambu project: `{projects[key]}`"
        else:
            status = "model-only Core 3MF; explicit Bambu project not yet generated"
        status_lines.append(f"- **{intent.display_name}:** {status}.")
    profile_rows = [
        "| Model | Printer/nozzle | Layer | Supports | Orientation |",
        "|---|---|---:|---|---|",
    ]
    for _, intent in sorted(print_intents.items()):
        support = intent.supports
        if intent.support_on_build_plate_only:
            support += ", build plate only"
        profile_rows.append(
            f"| {intent.display_name} | {intent.printer}, {intent.nozzle_mm:.1f} mm | "
            f"{intent.layer_height_mm:.2f} mm | {support} | {intent.orientation} |"
        )

    readme = f"""# {release_name}

**{ROOT_TAGLINE}**

This release contains pocket-size media relics: a compact cassette, a
3.5-inch floppy disk, a VHS cassette, and the Trailer Swift desk figure. Every
piece is designed around a visible 25 mm NFC interaction.

## Start with one test print

Print one individual model before using a combined plate. Confirm visual
identity, key-ring fit where applicable, NFC scanning, sticker protection, and
drop durability before batch production.

## 3MF status

Core 3MF files are **model-only geometry packages**. They do not contain a
printer, nozzle, filament, process, support, or plate profile. A file is a true
Bambu project only when it is explicitly named as a project and listed below as
created by the separate Bambu postprocessor.

{chr(10).join(status_lines)}

Never infer print settings from a filename. Open each file in Bambu Studio,
select the A1 Mini and 0.4 mm nozzle profile, and review the sliced preview.

## NFC interaction

Program each non-metal 25 mm tag with `{tap_url}`. Apply the programmed 25 mm
tag ONTO the marked landing. Apply the matching media overlay on top, then use
the handoff card: **Find the marked circle. Touch your unlocked phone to it.**

{NON_METALLIC_STOCK_WARNING}
"""

    printing = f"""# Printing and 3MF package status

## Model-only Core 3MF

The Core writer in `src/v7_release_packaging.py` packages meshes, object names,
metadata, and an optional thumbnail. It does **not** embed Bambu printer or
process settings. Model-only files should include `MODEL_ONLY` in their names.

## True Bambu project 3MF

A true project file must be generated through a separate Bambu-specific
postprocessor implementing `BambuProjectPostprocessor`. The postprocessor must
embed an explicit A1 Mini / 0.4 mm nozzle profile and verify the resulting file.
Only those files should include `A1_MINI_0.4_PROJECT` in their names.

## Required v7 print intents

{chr(10).join(profile_rows)}

The individual cassette, floppy, and VHS projects use supports off. The
individual Trailer Swift project uses organic supports restricted to the build
plate. The all-four combined Bambu project uses global `tree(auto)` supports,
restricted to the build plate, so Trailer Swift can print on the same plate.
Before printing the combined project, open Preview and confirm that no
unnecessary support is generated beneath or around the cassette, floppy, or
VHS. If media support appears, correct the object-level support assignment and
slice again. These are explicit intents, not proof that a Core 3MF contains
those settings. Review every sliced layer, especially eyelets, blind recesses,
the VHS door, the figure neck, guitar, flames, feet, and underside NFC landing.
"""

    nfc = f"""# NFC setup and overlay production

1. Use a genuine, non-metal, peel-and-stick 25 mm NFC tag.
2. Encode the HTTPS address `{tap_url}`.
3. Test the loose tag on iPhone and Android before locking it.
4. Apply the programmed 25 mm tag ONTO the marked landing.
5. Apply the matching non-metal overlay on top of the programmed tag.
6. Scan again after the printed overlay is installed.
7. Apply a clear, non-metal self-adhesive vinyl or PET overlaminate over the
   printed overlay. Burnish from the center outward without trapping bubbles.
   Do not use foil, holographic, metallized, metal-backed, or metallic-ink film.
8. **Mandatory final gate:** scan the completed piece again on iPhone and
   Android after the overlaminate is installed. Do not distribute a piece that
   fails this final scan.
9. Scan once more after the adhesive has cured for 24 hours.

## Artwork production

- Individual 25 mm PNG, SVG, and PDF overlay files are finished trim-size
  assets for precut 25 mm stock or vendor workflows that request trim artwork.
- The 20-up PDF sheets are the hand-cut and print-and-cut masters. They retain
  a true 25 mm finished cut circle plus 1 mm bleed around every label.
- PDF files are the vendor-print masters. Send the PDF rather than a screenshot
  or resaved raster image, print at 100%, and prohibit automatic scaling.
- Cut on the 25 mm hairline. The surrounding 1 mm bleed is sacrificial and is
  not part of the finished label.

## Handoff card commercial printing

- Finished trim size: 3.5 x 2 inches (88.9 x 50.8 mm).
- Supplied artwork includes 0.125 inch (3.175 mm) bleed on all four sides,
  external crop marks, and an embedded PDF TrimBox at the finished size.
- Print duplex at 100% and **flip on the short edge**. Confirm front/back
  orientation on one proof before ordering or producing the full quantity.
- Keep crop marks and bleed in the submitted master; the printer trims them
  away. Do not fit or scale the artwork to the sheet.

## Placement

- Cassette: marked circle on the flat rear landing; use the `C-69 // SIDE A` overlay.
- Floppy: marked rear circle; the 25 mm overlay contains an approximately
  11-12 mm faux gray hub.
- VHS: marked flat rear landing; use the `T-369` video-label overlay.
- Trailer Swift: underside of the circular base; use `TAP THE BASE`.

The printed overlay does not replace the NFC tag. {NON_METALLIC_STOCK_WARNING}
Printed gray on the floppy label is an ink illusion, not metal.

The handoff card includes a QR fallback to `{tap_url}` for phones that do not
read the NFC tag immediately.
"""

    qc = """# Micro Replicas v7 physical quality-control checklist

Record printer, nozzle, filament, plate, slicer version, profile, date, tag
vendor/SKU/lot, overlay stock, split ring, phone models, and operator.

## Identity and finish

- [ ] Cassette reads immediately as a compact cassette at arm's length.
- [ ] Floppy front and rear read immediately as a 3.5-inch disk.
- [ ] VHS reads immediately as VHS, not as an audio cassette.
- [ ] Trailer Swift reads as a three-dimensional bobblehead-style punk figure.
- [ ] RAD DAD, C-69, 3.69 MB, T-369, and TRAILER SWIFT are readable.
- [ ] No strings, gaps, unsupported damage, loose details, or sharp scars.

## Mechanical function

- [ ] Every media eyelet accepts the thickest production split ring easily.
- [ ] Every eyelet survives a 2 kg static load for 60 seconds.
- [ ] Every eyelet survives 25 firm pull-and-twist cycles.
- [ ] Each media piece survives one-meter drops in six orientations.
- [ ] Each media piece completes at least 72 hours of representative key carry.
- [ ] Trailer Swift stands without rocking and survives normal desk handling.

## NFC function

- [ ] Loose tag scans before encoding and after encoding.
- [ ] Installed tag scans ten consecutive times on iPhone.
- [ ] Installed tag scans ten consecutive times on Android.
- [ ] Tag scans after the overlay is applied and after 24-hour adhesive cure.
- [ ] Tag scans with a normal phone case and with the production split ring fitted.
- [ ] Overlay remains fully adhered and does not rub directly on a tabletop.

## Slicer and release gate

- [ ] File type is recorded as model-only Core 3MF or true Bambu project 3MF.
- [ ] A1 Mini and 0.4 mm nozzle profiles are explicitly selected.
- [ ] Individual cassette, floppy, and VHS projects have supports off.
- [ ] The individual Trailer Swift project uses organic build-plate-only supports.
- [ ] The all-four project uses global `tree(auto)`, build-plate-only supports.
- [ ] Combined-project Preview confirms no unnecessary cassette, floppy, or VHS supports.
- [ ] Every sliced layer is reviewed before printing.
- [ ] PASS: approved for batch production.
- [ ] HOLD: defect documented and corrected before reprint.
"""

    paths = {
        "readme": _atomic_write_text(layout.root / "README.md", readme),
        "printing": _atomic_write_text(
            layout.guides / "PRINTING_AND_3MF_STATUS.md", printing
        ),
        "nfc": _atomic_write_text(layout.guides / "NFC_SETUP.md", nfc),
        "physical_qc": _atomic_write_text(
            layout.qa / "PHYSICAL_QC_CHECKLIST.md", qc
        ),
        "print_intents": _atomic_write_text(
            layout.qa / "PRINT_INTENTS.json",
            json.dumps(
                {
                    "schema": "rad-dad-print-intent-v1",
                    "warning": MODEL_ONLY_3MF_WARNING,
                    "intents": {
                        key: asdict(value)
                        for key, value in sorted(print_intents.items())
                    },
                    "bambu_projects": projects,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        ),
    }
    return paths


def write_model_artifacts(
    layout: ReleaseLayout,
    models: Mapping[str, Any],
    *,
    display_names: Mapping[str, str] | None = None,
    thumbnails: Mapping[str, Any] | None = None,
    print_intents: Mapping[str, BambuPrintIntent] = DEFAULT_PRINT_INTENTS,
    bambu_postprocessor: BambuProjectPostprocessor | None = None,
) -> dict[str, dict[str, Any]]:
    """Write STL/Core 3MF and optionally true Bambu project 3MF artifacts."""

    display_names = dict(display_names or {})
    thumbnails = dict(thumbnails or {})
    results: dict[str, dict[str, Any]] = {}
    for key in sorted(models):
        mesh = models[key]
        display_name = display_names.get(key, key.replace("_", " ").title())
        stl_path = export_binary_stl(
            mesh,
            layout.models_stl / f"{key}_BINARY.stl",
            solid_name=display_name,
        )
        core_result = write_core_3mf(
            layout.models_3mf / f"{key}_MODEL_ONLY.3mf",
            ThreeMFObject(display_name, mesh),
            title=display_name,
            thumbnail=thumbnails.get(key),
            metadata={"PackageKind": "model-only-core-3mf"},
        )
        record: dict[str, Any] = {
            "stl": stl_path,
            "core_3mf": core_result,
            "bambu_project_3mf": None,
        }
        if bambu_postprocessor is not None:
            if key not in print_intents:
                raise KeyError(f"missing Bambu print intent for {key!r}")
            record["bambu_project_3mf"] = apply_bambu_postprocessor(
                core_result.path,
                layout.models_3mf / f"{key}_A1_MINI_0.4_PROJECT.3mf",
                intent=print_intents[key],
                postprocessor=bambu_postprocessor,
                metadata={"display_name": display_name},
            )
        results[key] = record
    return results


def finalize_release(
    release_root: str | Path,
    *,
    archive_path: str | Path,
    release_name: str = "Rad Dad Retro Riot v7: Micro Replica Edition",
    archive_prefix: str = "Rad_Dad_Retro_Riot_v7_Micro_Replica_Edition",
    manifest_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Path]:
    """Write manifest, deterministic ZIP, and an external ZIP checksum."""

    root = Path(release_root)
    archive = Path(archive_path)
    manifest = write_release_manifest(
        root,
        release_name=release_name,
        exclude=(archive, archive.with_name(archive.name + ".sha256")),
        metadata=manifest_metadata,
    )
    create_deterministic_zip(
        root,
        archive,
        archive_prefix=archive_prefix,
        exclude=(archive, archive.with_name(archive.name + ".sha256")),
    )
    checksum = write_sha256_sidecar(archive)
    return {"manifest": manifest, "archive": archive, "archive_checksum": checksum}


__all__ = [
    "BambuPrintIntent",
    "BambuProjectPostprocessor",
    "BRAND",
    "DEFAULT_PRINT_INTENTS",
    "DEFAULT_TAP_URL",
    "MODEL_ONLY_3MF_WARNING",
    "ModuleBambuPostprocessor",
    "NON_METALLIC_STOCK_WARNING",
    "OVERLAY_SPECS",
    "OverlaySpec",
    "ReleaseLayout",
    "ThreeMFObject",
    "ThreeMFPackageResult",
    "apply_bambu_postprocessor",
    "create_deterministic_zip",
    "create_release_layout",
    "export_binary_stl",
    "finalize_release",
    "load_bambu_postprocessor",
    "mesh_qa_record",
    "qr_matrix",
    "render_mesh_preview",
    "render_preview_set",
    "sha256_file",
    "write_core_3mf",
    "write_handoff_card_assets",
    "write_nfc_placement_guide",
    "write_mesh_qa_json",
    "write_model_artifacts",
    "write_overlay_assets",
    "write_overlay_sheets",
    "write_release_documents",
    "write_release_manifest",
    "write_sha256_sidecar",
]
