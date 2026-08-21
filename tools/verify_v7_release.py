#!/usr/bin/env python3
"""Strict release gate for the Rad Dad Micro Replica v7 collection.

Human-readable results are written to stderr. A deterministic JSON report is
written to stdout by default, or to the path supplied with --json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:
    import numpy as np
    import trimesh
except ImportError as exc:  # Reported as a normal validation failure in main().
    np = None
    trimesh = None
    MESH_IMPORT_ERROR: Exception | None = exc
else:
    MESH_IMPORT_ERROR = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = ROOT / "release" / "v7"
MANIFEST_NAME = "MANIFEST.json"
JSON_SCHEMA = "rad-dad-micro-replica-v7-validation-1"
ENVELOPE_TOLERANCE_MM = 0.02
PAIR_EXTENT_TOLERANCE_MM = 0.03
PAIR_VOLUME_RELATIVE_TOLERANCE = 0.005
NFC_DIAMETER_MM = 25.0
NFC_DIAMETER_TOLERANCE_MM = 0.50
KEYRING_DIAMETER_MM = 6.0
KEYRING_DIAMETER_TOLERANCE_MM = 0.25


@dataclass(frozen=True)
class ProductSpec:
    product_id: str
    display_name: str
    filename_tokens: tuple[str, ...]
    max_extent_mm: tuple[float, float, float]
    keyring_required: bool


class ArtifactCardinality(str, Enum):
    """Expected number of files selected by an artifact rule."""

    SINGLE = "single"
    COLLECTION = "collection"


PRODUCTS: dict[str, ProductSpec] = {
    "cassette": ProductSpec(
        "cassette",
        "Cassette",
        ("cassette",),
        (60.324, 30.260, 6.685),
        True,
    ),
    "floppy": ProductSpec(
        "floppy",
        "Floppy disk",
        ("floppy",),
        (46.560, 36.920, 4.130),
        True,
    ),
    "vhs": ProductSpec(
        "vhs",
        "VHS tape",
        ("vhs",),
        (70.000, 31.900, 7.000),
        True,
    ),
    "trailer_swift": ProductSpec(
        "trailer_swift",
        "Trailer Swift",
        ("trailer", "swift"),
        (46.000, 46.000, 65.000),
        False,
    ),
}


@dataclass
class Check:
    check_id: str
    status: str
    message: str
    critical: bool = True
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class MeshMetrics:
    path: str
    file_type: str
    product_id: str | None
    expected_bodies: int
    vertices: int
    faces: int
    bodies: int
    boundary_edges: int
    nonmanifold_edges: int
    inconsistent_edges: int
    degenerate_faces: int
    watertight: bool
    consistently_wound: bool
    positive_volume: bool
    signed_volume_mm3: float
    component_volumes_mm3: list[float]
    extents_mm: list[float]


@dataclass(frozen=True)
class ThreeMFComponent:
    target_part: str
    object_id: str
    transform: tuple[float, ...]


@dataclass(frozen=True)
class ThreeMFObject:
    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]
    components: tuple[ThreeMFComponent, ...]


@dataclass(frozen=True)
class ThreeMFModelPart:
    objects: dict[str, ThreeMFObject]
    build_items: tuple[ThreeMFComponent, ...]


@dataclass
class ValidationContext:
    release: Path
    json_output: Path | None
    checks: list[Check] = field(default_factory=list)
    meshes: dict[str, MeshMetrics] = field(default_factory=dict)
    mesh_objects: dict[str, Any] = field(default_factory=dict, repr=False)
    bambu_results: list[dict[str, Any]] = field(default_factory=list)
    manifest_sha256: str | None = None
    manifest_data: dict[str, Any] | None = None

    def pass_check(
        self, check_id: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self.checks.append(Check(check_id, "pass", message, True, details or {}))

    def fail(
        self, check_id: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self.checks.append(Check(check_id, "fail", message, True, details or {}))

    def warn(
        self, check_id: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self.checks.append(Check(check_id, "warn", message, False, details or {}))


class DuplicateJsonKey(ValueError):
    pass


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def no_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKey(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_json_keys
    )
    if not isinstance(value, dict):
        raise ValueError("top-level JSON value must be an object")
    return value


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def safe_manifest_path(raw_path: str, release: Path) -> Path:
    if not raw_path or "\\" in raw_path:
        raise ValueError("path must be a nonempty POSIX path")
    pure = PurePosixPath(raw_path)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise ValueError("path must be normalized and relative")
    candidate = (release / Path(*pure.parts)).resolve()
    if not is_within(candidate, release):
        raise ValueError("path escapes the selected release directory")
    return candidate


def validate_manifest(ctx: ValidationContext) -> dict[str, Any] | None:
    manifest = ctx.release / MANIFEST_NAME
    if not manifest.is_file():
        ctx.fail("manifest.exists", f"Missing {repo_path(manifest)}")
        return None

    try:
        data = read_json(manifest)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        ctx.fail("manifest.readable", f"Unreadable manifest: {exc}")
        return None

    ctx.manifest_sha256 = sha256(manifest)
    release_name = str(data.get("release", ""))
    if re.search(r"(?<![A-Za-z0-9])v7(?![A-Za-z0-9])", release_name, re.IGNORECASE):
        ctx.pass_check("manifest.release", f"Manifest identifies {release_name}")
    else:
        ctx.fail(
            "manifest.release",
            "Manifest release field must identify v7",
            {"actual": release_name},
        )

    items = data.get("files")
    if not isinstance(items, list) or not items:
        ctx.fail("manifest.files", "Manifest files must be a nonempty list")
        return data

    raw_paths: list[str] = []
    valid_items: list[tuple[dict[str, Any], Path]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            ctx.fail("manifest.entry", f"Manifest entry {index} is not an object")
            continue
        raw_path = item.get("path")
        if not isinstance(raw_path, str):
            ctx.fail("manifest.entry.path", f"Manifest entry {index} has no string path")
            continue
        raw_paths.append(raw_path)
        try:
            path = safe_manifest_path(raw_path, ctx.release)
        except ValueError as exc:
            ctx.fail("manifest.entry.path", f"Unsafe manifest path {raw_path}: {exc}")
            continue
        valid_items.append((item, path))

    if len(raw_paths) != len(set(raw_paths)):
        duplicates = sorted(path for path in set(raw_paths) if raw_paths.count(path) > 1)
        ctx.fail("manifest.unique", "Manifest paths are not unique", {"paths": duplicates})
    else:
        ctx.pass_check("manifest.unique", "Manifest paths are unique")

    if raw_paths == sorted(raw_paths):
        ctx.pass_check("manifest.order", "Manifest paths are deterministically sorted")
    else:
        ctx.fail("manifest.order", "Manifest paths must be sorted lexicographically")

    verified = 0
    for item, path in valid_items:
        raw_path = str(item["path"])
        expected_size = item.get("bytes")
        expected_hash = item.get("sha256")
        if not isinstance(expected_size, int) or expected_size < 0:
            ctx.fail("manifest.entry.bytes", f"Invalid byte count for {raw_path}")
            continue
        if not isinstance(expected_hash, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected_hash
        ):
            ctx.fail("manifest.entry.sha256", f"Invalid SHA-256 for {raw_path}")
            continue
        if not path.is_file():
            ctx.fail("manifest.entry.exists", f"Missing manifest file {raw_path}")
            continue
        if path.is_symlink():
            ctx.fail("manifest.entry.symlink", f"Release artifact may not be a symlink: {raw_path}")
            continue
        actual_size = path.stat().st_size
        actual_hash = sha256(path)
        if actual_size != expected_size:
            ctx.fail(
                "manifest.entry.bytes",
                f"Size mismatch for {raw_path}",
                {"expected": expected_size, "actual": actual_size},
            )
            continue
        if actual_hash != expected_hash:
            ctx.fail(
                "manifest.entry.sha256",
                f"Checksum mismatch for {raw_path}",
                {"expected": expected_hash, "actual": actual_hash},
            )
            continue
        verified += 1

    if verified == len(items):
        ctx.pass_check(
            "manifest.hashes",
            f"Verified all {verified} deterministic SHA-256 entries",
        )

    excluded = {manifest.resolve()}
    excluded.update(
        path.resolve()
        for path in ctx.release.iterdir()
        if path.is_file()
        and (path.suffix.lower() == ".zip" or path.name.lower().endswith(".zip.sha256"))
    )
    if ctx.json_output is not None and is_within(ctx.json_output, ctx.release):
        excluded.add(ctx.json_output.resolve())
    actual_files = {
        path.relative_to(ctx.release).as_posix()
        for path in ctx.release.rglob("*")
        if path.is_file() and path.resolve() not in excluded
    }
    listed_files = set(raw_paths)
    missing_from_manifest = sorted(actual_files - listed_files)
    nonexistent_listings = sorted(listed_files - actual_files)
    if missing_from_manifest or nonexistent_listings:
        ctx.fail(
            "manifest.coverage",
            "Manifest must cover every release file except itself and the selected JSON report",
            {
                "missing_from_manifest": missing_from_manifest,
                "nonexistent_listings": nonexistent_listings,
            },
        )
    else:
        ctx.pass_check("manifest.coverage", "Manifest coverage is complete")

    ctx.manifest_data = data
    return data


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def validate_svg(ctx: ValidationContext, path: Path, check_id: str) -> None:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        ctx.fail(check_id, f"Unreadable SVG {repo_path(path)}: {exc}")
        return
    if local_name(root.tag).lower() != "svg":
        ctx.fail(check_id, f"Not an SVG document: {repo_path(path)}")
        return
    ctx.pass_check(check_id, f"Readable SVG: {repo_path(path)}")


def validate_png(ctx: ValidationContext, path: Path, check_id: str) -> None:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
    except OSError as exc:
        ctx.fail(check_id, f"Unreadable PNG {repo_path(path)}: {exc}")
        return
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        ctx.fail(check_id, f"Invalid PNG header: {repo_path(path)}")
        return
    width, height = struct.unpack(">II", header[16:24])
    if width < 300 or height < 300:
        ctx.fail(
            check_id,
            f"Preview is too small: {repo_path(path)}",
            {"width": width, "height": height},
        )
        return
    ctx.pass_check(
        check_id,
        f"Readable preview: {repo_path(path)}",
        {"width": width, "height": height},
    )


def files_matching(
    files: Iterable[Path],
    directory: str,
    required_tokens: Iterable[str],
    any_tokens: Iterable[str] = (),
    suffixes: Iterable[str] = (),
) -> list[Path]:
    required = tuple(token.lower() for token in required_tokens)
    alternatives = tuple(token.lower() for token in any_tokens)
    allowed_suffixes = {suffix.lower() for suffix in suffixes}
    matches: list[Path] = []
    for path in files:
        try:
            relative = path.relative_to(path.parents[len(path.parts) - 1])
        except (ValueError, IndexError):
            relative = path
        lower_name = path.name.lower()
        parent_names = {part.lower() for part in path.parts}
        if directory.lower() not in parent_names:
            continue
        if allowed_suffixes and path.suffix.lower() not in allowed_suffixes:
            continue
        if not all(token in lower_name for token in required):
            continue
        if alternatives and not any(token in lower_name for token in alternatives):
            continue
        matches.append(path)
    return sorted(matches)


def require_artifact(
    ctx: ValidationContext,
    files: list[Path],
    check_id: str,
    label: str,
    directory: str,
    required_tokens: Iterable[str],
    any_tokens: Iterable[str] = (),
    suffixes: Iterable[str] = (),
    cardinality: ArtifactCardinality = ArtifactCardinality.SINGLE,
) -> list[Path]:
    matches = files_matching(
        files, directory, required_tokens, any_tokens=any_tokens, suffixes=suffixes
    )
    if not matches:
        ctx.fail(check_id, f"Missing required {label}")
        return []
    if len(matches) > 1 and cardinality is ArtifactCardinality.SINGLE:
        ctx.warn(
            f"{check_id}.multiple",
            f"Multiple files satisfy canonical {label}; using all matches",
            {"paths": [repo_path(path) for path in matches]},
        )
    if cardinality is ArtifactCardinality.COLLECTION:
        message = f"Found {len(matches)} files in {label} collection"
    else:
        message = f"Found {label}"
    ctx.pass_check(
        check_id,
        message,
        {
            "cardinality": cardinality.value,
            "paths": [repo_path(path) for path in matches],
        },
    )
    return matches


def validate_required_artifacts(ctx: ValidationContext) -> None:
    if not ctx.release.is_dir():
        return
    files = sorted(path for path in ctx.release.rglob("*") if path.is_file())

    readme = ctx.release / "README.md"
    if readme.is_file() and readme.stat().st_size > 0:
        ctx.pass_check("artifact.readme", f"Found {repo_path(readme)}")
    else:
        ctx.fail("artifact.readme", "Missing nonempty release/v7/README.md")

    guide_specs = (
        (
            "artifact.guide.placement",
            "NFC placement guide",
            ("nfc", "placement", "guide"),
            (),
            ArtifactCardinality.SINGLE,
        ),
        (
            "artifact.guide.handoff",
            "NFC handoff card",
            ("handoff", "card"),
            (),
            ArtifactCardinality.COLLECTION,
        ),
        (
            "artifact.label.universal",
            "25 mm tap label",
            ("25mm", "tap", "label"),
            (),
            ArtifactCardinality.COLLECTION,
        ),
        (
            "artifact.label.sheet",
            "printable tap-label sheet",
            ("tap", "label"),
            ("20up", "sheet"),
            ArtifactCardinality.COLLECTION,
        ),
    )
    svg_paths: set[Path] = set()
    for check_id, label, required, alternatives, cardinality in guide_specs:
        svg_paths.update(
            require_artifact(
                ctx,
                files,
                check_id,
                label,
                "guides",
                required,
                any_tokens=alternatives,
                suffixes=(".svg",),
                cardinality=cardinality,
            )
        )

    for product_id, spec in PRODUCTS.items():
        product_tokens = spec.filename_tokens
        svg_paths.update(
            require_artifact(
                ctx,
                files,
                f"artifact.label.{product_id}",
                f"{spec.display_name} NFC overlay label",
                "guides",
                (*product_tokens, "label"),
                any_tokens=("tap", "nfc"),
                suffixes=(".svg",),
            )
        )

    for index, path in enumerate(sorted(svg_paths)):
        validate_svg(ctx, path, f"artifact.svg.{index:02d}")

    preview_paths: set[Path] = set()
    preview_paths.update(
        require_artifact(
            ctx,
            files,
            "artifact.preview.collection",
            "collection preview",
            "previews",
            (),
            any_tokens=("collection", "all_four", "all-four"),
            suffixes=(".png",),
            cardinality=ArtifactCardinality.COLLECTION,
        )
    )
    for product_id, spec in PRODUCTS.items():
        preview_paths.update(
            require_artifact(
                ctx,
                files,
                f"artifact.preview.{product_id}",
                f"{spec.display_name} preview",
                "previews",
                spec.filename_tokens,
                suffixes=(".png",),
                cardinality=ArtifactCardinality.COLLECTION,
            )
        )
    for index, path in enumerate(sorted(preview_paths)):
        validate_png(ctx, path, f"artifact.png.{index:02d}")

    qa_requirements = (
        (ctx.release / "qa" / "MODEL_QA.json", "artifact.qa.model"),
        (ctx.release / "qa" / "PHYSICAL_QC_CHECKLIST.md", "artifact.qa.physical"),
    )
    for path, check_id in qa_requirements:
        if path.is_file() and path.stat().st_size > 0:
            ctx.pass_check(check_id, f"Found {repo_path(path)}")
        else:
            ctx.fail(check_id, f"Missing required QA file {repo_path(path)}")

    print_packs = [
        path
        for path in files
        if path.parent == ctx.release
        and path.suffix.lower() == ".zip"
        and "print" in path.name.lower()
        and "pack" in path.name.lower()
        and "v7" in path.name.lower()
    ]
    if len(print_packs) != 1:
        ctx.fail(
            "artifact.print_pack",
            "Release must contain exactly one v7 print-pack ZIP",
            {"paths": [repo_path(path) for path in print_packs]},
        )
    else:
        validate_general_zip(ctx, print_packs[0], "artifact.print_pack")


def safe_zip_names(archive: zipfile.ZipFile) -> tuple[bool, list[str]]:
    errors: list[str] = []
    names = archive.namelist()
    if len(names) != len(set(names)):
        errors.append("duplicate ZIP member names")
    total_size = 0
    for info in archive.infolist():
        name = info.filename
        pure = PurePosixPath(name)
        if not name or name.startswith("/") or "\\" in name or ".." in pure.parts:
            errors.append(f"unsafe ZIP member: {name!r}")
        if info.flag_bits & 0x1:
            errors.append(f"encrypted ZIP member: {name}")
        total_size += info.file_size
        if info.file_size > 350 * 1024 * 1024:
            errors.append(f"oversized ZIP member: {name}")
        if info.compress_size and info.file_size / info.compress_size > 1500:
            errors.append(f"unsafe compression ratio: {name}")
    if total_size > 750 * 1024 * 1024:
        errors.append("ZIP uncompressed size exceeds 750 MiB")
    return not errors, errors


def validate_general_zip(ctx: ValidationContext, path: Path, check_id: str) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            safe, errors = safe_zip_names(archive)
            corrupt = archive.testzip()
    except (OSError, zipfile.BadZipFile) as exc:
        ctx.fail(check_id, f"Unreadable ZIP {repo_path(path)}: {exc}")
        return
    if corrupt:
        errors.append(f"corrupt member: {corrupt}")
    if not safe or errors:
        ctx.fail(check_id, f"Unsafe or corrupt ZIP {repo_path(path)}", {"errors": errors})
        return
    ctx.pass_check(check_id, f"Readable print pack: {repo_path(path)}")


def xml_attribute(node: ET.Element, name: str) -> str | None:
    for key, value in node.attrib.items():
        if local_name(key) == name:
            return value
    return None


def direct_xml_children(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in node if local_name(child.tag) == name]


def parse_3mf_transform(raw: str | None) -> tuple[float, ...]:
    if raw is None or not raw.strip():
        return (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
    try:
        values = tuple(float(value) for value in raw.split())
    except ValueError as exc:
        raise ValueError(f"invalid 3MF transform {raw!r}") from exc
    if len(values) != 12 or not all(math.isfinite(value) for value in values):
        raise ValueError(f"invalid 3MF transform {raw!r}")
    return values


def resolve_3mf_model_part(source_part: str, raw_target: str | None) -> str:
    if raw_target is None:
        return source_part
    if not raw_target or "\\" in raw_target or "?" in raw_target or "#" in raw_target:
        raise ValueError(f"unsafe 3MF component path {raw_target!r}")
    rooted = raw_target.startswith("/")
    pure = PurePosixPath(raw_target.lstrip("/"))
    if not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"unsafe 3MF component path {raw_target!r}")
    if not rooted:
        pure = PurePosixPath(source_part).parent / pure
    target = pure.as_posix()
    if PurePosixPath(target).suffix.lower() != ".model":
        raise ValueError(f"3MF component target is not a model part: {raw_target!r}")
    return target


def read_3mf_model_parts(
    archive: zipfile.ZipFile, model_members: Iterable[str]
) -> dict[str, ThreeMFModelPart]:
    parts: dict[str, ThreeMFModelPart] = {}
    for member in sorted(model_members):
        root = ET.fromstring(archive.read(member))
        if local_name(root.tag) != "model":
            raise ValueError(f"{member} has the wrong XML root")
        if root.attrib.get("unit") != "millimeter":
            raise ValueError(f"{member} must explicitly use millimeter units")

        resources = direct_xml_children(root, "resources")
        if len(resources) != 1:
            raise ValueError(f"{member} must contain exactly one resources element")
        objects: dict[str, ThreeMFObject] = {}
        for object_node in direct_xml_children(resources[0], "object"):
            object_id = object_node.attrib.get("id", "")
            try:
                valid_object_id = int(object_id) > 0
            except ValueError:
                valid_object_id = False
            if not valid_object_id:
                raise ValueError(f"{member} contains an invalid object id {object_id!r}")
            if object_id in objects:
                raise ValueError(f"{member} contains duplicate object id {object_id}")

            mesh_nodes = direct_xml_children(object_node, "mesh")
            component_groups = direct_xml_children(object_node, "components")
            if len(mesh_nodes) + len(component_groups) != 1:
                raise ValueError(
                    f"{member} object {object_id} must contain exactly one mesh or components element"
                )

            vertices: list[tuple[float, float, float]] = []
            triangles: list[tuple[int, int, int]] = []
            components: list[ThreeMFComponent] = []
            if mesh_nodes:
                vertex_groups = direct_xml_children(mesh_nodes[0], "vertices")
                triangle_groups = direct_xml_children(mesh_nodes[0], "triangles")
                if len(vertex_groups) != 1 or len(triangle_groups) != 1:
                    raise ValueError(
                        f"{member} object {object_id} must contain vertices and triangles"
                    )
                for vertex in direct_xml_children(vertex_groups[0], "vertex"):
                    try:
                        coordinates = tuple(float(vertex.attrib[key]) for key in ("x", "y", "z"))
                    except (KeyError, ValueError) as exc:
                        raise ValueError(
                            f"{member} object {object_id} contains an invalid vertex"
                        ) from exc
                    if not all(math.isfinite(value) for value in coordinates):
                        raise ValueError(
                            f"{member} object {object_id} contains a non-finite vertex"
                        )
                    vertices.append(coordinates)  # type: ignore[arg-type]
                for triangle in direct_xml_children(triangle_groups[0], "triangle"):
                    try:
                        indices = tuple(int(triangle.attrib[key]) for key in ("v1", "v2", "v3"))
                    except (KeyError, ValueError) as exc:
                        raise ValueError(
                            f"{member} object {object_id} contains an invalid triangle"
                        ) from exc
                    if not vertices or min(indices) < 0 or max(indices) >= len(vertices):
                        raise ValueError(
                            f"{member} object {object_id} contains an out-of-range triangle"
                        )
                    triangles.append(indices)  # type: ignore[arg-type]
                if not vertices or not triangles:
                    raise ValueError(f"{member} object {object_id} contains no mesh geometry")
            else:
                for component in direct_xml_children(component_groups[0], "component"):
                    target_id = component.attrib.get("objectid", "")
                    try:
                        valid_target_id = int(target_id) > 0
                    except ValueError:
                        valid_target_id = False
                    if not valid_target_id:
                        raise ValueError(
                            f"{member} object {object_id} contains an invalid component object id"
                        )
                    components.append(
                        ThreeMFComponent(
                            target_part=resolve_3mf_model_part(
                                member, xml_attribute(component, "path")
                            ),
                            object_id=target_id,
                            transform=parse_3mf_transform(xml_attribute(component, "transform")),
                        )
                    )
                if not components:
                    raise ValueError(f"{member} object {object_id} contains no components")

            objects[object_id] = ThreeMFObject(
                vertices=tuple(vertices),
                triangles=tuple(triangles),
                components=tuple(components),
            )

        builds = direct_xml_children(root, "build")
        if len(builds) > 1:
            raise ValueError(f"{member} contains multiple build elements")
        build_items: list[ThreeMFComponent] = []
        if builds:
            for item in direct_xml_children(builds[0], "item"):
                object_id = item.attrib.get("objectid", "")
                try:
                    valid_object_id = int(object_id) > 0
                except ValueError:
                    valid_object_id = False
                if not valid_object_id:
                    raise ValueError(f"{member} contains an invalid build object id")
                build_items.append(
                    ThreeMFComponent(
                        target_part=member,
                        object_id=object_id,
                        transform=parse_3mf_transform(xml_attribute(item, "transform")),
                    )
                )
        parts[member] = ThreeMFModelPart(objects=objects, build_items=tuple(build_items))
    return parts


def validate_3mf_references(
    parts: dict[str, ThreeMFModelPart], root_part: str
) -> tuple[set[tuple[str, str]], int]:
    if root_part not in parts:
        raise ValueError(f"missing root model part {root_part}")
    root_build = parts[root_part].build_items
    if not root_build:
        raise ValueError("3MF root model contains no build items")

    for part_name, part in parts.items():
        for item in part.build_items:
            if item.object_id not in part.objects:
                raise ValueError(
                    f"{part_name} build item references missing object {item.object_id}"
                )
        for object_id, object_record in part.objects.items():
            for component in object_record.components:
                target = parts.get(component.target_part)
                if target is None:
                    raise ValueError(
                        f"{part_name} object {object_id} references missing model part "
                        f"{component.target_part}"
                    )
                if component.object_id not in target.objects:
                    raise ValueError(
                        f"{part_name} object {object_id} references missing object "
                        f"{component.object_id} in {component.target_part}"
                    )

    reachable: set[tuple[str, str]] = set()
    active: set[tuple[str, str]] = set()

    def visit(part_name: str, object_id: str) -> None:
        key = (part_name, object_id)
        if key in active:
            raise ValueError(f"cyclic 3MF component reference at {part_name} object {object_id}")
        if key in reachable:
            return
        active.add(key)
        record = parts[part_name].objects[object_id]
        for component in record.components:
            visit(component.target_part, component.object_id)
        active.remove(key)
        reachable.add(key)

    for item in root_build:
        visit(root_part, item.object_id)
    mesh_count = sum(
        1 for part_name, object_id in reachable if parts[part_name].objects[object_id].triangles
    )
    if mesh_count == 0:
        raise ValueError("3MF build graph reaches no mesh geometry")
    return reachable, mesh_count


def validate_3mf_core(ctx: ValidationContext, path: Path) -> bool:
    check_prefix = f"3mf.{path.name}"
    required_parts = {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"}
    is_bambu_project = "_PROJECT" in path.stem.upper() and "_MODEL_ONLY" not in path.stem.upper()
    try:
        with zipfile.ZipFile(path) as archive:
            safe, errors = safe_zip_names(archive)
            names = set(archive.namelist())
            missing = sorted(required_parts - names)
            if is_bambu_project:
                project_parts = {
                    "Metadata/model_settings.config",
                    "Metadata/project_settings.config",
                }
                missing.extend(sorted(project_parts - names))
            corrupt = archive.testzip()
            if corrupt:
                errors.append(f"corrupt member: {corrupt}")
            if missing:
                errors.append(f"missing core parts: {', '.join(missing)}")
            if not safe or errors:
                ctx.fail(
                    f"{check_prefix}.package",
                    f"Invalid 3MF package {repo_path(path)}",
                    {"errors": errors},
                )
                return False
            content_types = ET.fromstring(archive.read("[Content_Types].xml"))
            relationships = ET.fromstring(archive.read("_rels/.rels"))
            model_members = sorted(name for name in names if name.lower().endswith(".model"))
            if not is_bambu_project and model_members != ["3D/3dmodel.model"]:
                errors.append(
                    "model-only 3MF must contain exactly one model document at 3D/3dmodel.model"
                )
            if errors:
                ctx.fail(
                    f"{check_prefix}.package",
                    f"Invalid 3MF package {repo_path(path)}",
                    {"errors": errors},
                )
                return False
            model_parts = read_3mf_model_parts(archive, model_members)
            if is_bambu_project:
                ET.fromstring(archive.read("Metadata/model_settings.config"))
                project_settings = json.loads(
                    archive.read("Metadata/project_settings.config").decode("utf-8"),
                    object_pairs_hook=no_duplicate_json_keys,
                )
                if not isinstance(project_settings, dict):
                    raise ValueError("Bambu project settings must be a JSON object")
    except (
        OSError,
        UnicodeError,
        zipfile.BadZipFile,
        KeyError,
        ET.ParseError,
        json.JSONDecodeError,
        DuplicateJsonKey,
        ValueError,
    ) as exc:
        ctx.fail(
            f"{check_prefix}.package",
            f"Unreadable 3MF package {repo_path(path)}: {exc}",
        )
        return False

    if local_name(content_types.tag) != "Types":
        ctx.fail(f"{check_prefix}.content_types", "Invalid [Content_Types].xml root")
        return False
    model_content_type = "application/vnd.ms-package.3dmanufacturing-3dmodel+xml"
    default_model_type = any(
        local_name(node.tag) == "Default"
        and node.attrib.get("Extension", "").lower() == "model"
        and node.attrib.get("ContentType") == model_content_type
        for node in content_types
    )
    override_model_parts = {
        node.attrib.get("PartName", "").lstrip("/")
        for node in content_types
        if local_name(node.tag) == "Override"
        and node.attrib.get("ContentType") == model_content_type
    }
    missing_content_types = sorted(
        member
        for member in model_parts
        if not default_model_type and member not in override_model_parts
    )
    if missing_content_types:
        ctx.fail(
            f"{check_prefix}.content_types",
            "3MF model content type is missing or incorrect",
            {"model_parts": missing_content_types},
        )
        return False

    model_relationships = [
        node
        for node in relationships
        if local_name(node.tag) == "Relationship"
        and node.attrib.get("Type", "").rstrip("/").endswith("/3dmodel")
    ]
    if len(model_relationships) != 1:
        ctx.fail(
            f"{check_prefix}.relationships",
            "3MF must contain exactly one root model relationship",
            {"count": len(model_relationships)},
        )
        return False
    relationship = model_relationships[0]
    if relationship.attrib.get("Target", "").lstrip("/") != "3D/3dmodel.model":
        ctx.fail(f"{check_prefix}.relationships", "3MF root relationship targets the wrong part")
        return False
    if relationship.attrib.get("TargetMode", "").lower() == "external":
        ctx.fail(f"{check_prefix}.relationships", "External 3MF model targets are forbidden")
        return False

    try:
        reachable, mesh_count = validate_3mf_references(model_parts, "3D/3dmodel.model")
    except ValueError as exc:
        ctx.fail(
            f"{check_prefix}.references",
            f"Invalid 3MF object graph: {exc}",
        )
        return False

    reachable_records = [model_parts[part].objects[object_id] for part, object_id in reachable]
    vertex_count = sum(len(record.vertices) for record in reachable_records)
    triangle_count = sum(len(record.triangles) for record in reachable_records)

    ctx.pass_check(
        f"{check_prefix}.core",
        (
            f"Valid package-aware Bambu 3MF project: {repo_path(path)}"
            if is_bambu_project
            else f"Valid single-document core 3MF package: {repo_path(path)}"
        ),
        {
            "model_parts": len(model_parts),
            "objects": sum(len(part.objects) for part in model_parts.values()),
            "build_items": len(model_parts["3D/3dmodel.model"].build_items),
            "meshes": mesh_count,
            "vertices": vertex_count,
            "triangles": triangle_count,
        },
    )
    return True


def classify_model(path: Path) -> str | None:
    name = path.stem.lower().replace("-", "_")
    if any(token in name for token in ("all_four", "all4", "collection")):
        return "collection"
    if "retro_riot" in name and path.suffix.lower() == ".3mf":
        return "collection"
    for product_id, spec in PRODUCTS.items():
        if all(token in name for token in spec.filename_tokens):
            return product_id
    return None


def transform_3mf_vertices(vertices: Any, transform: tuple[float, ...]) -> Any:
    values = np.asarray(transform, dtype=np.float64)
    source = np.asarray(vertices, dtype=np.float64)
    result = np.empty_like(source)
    result[:, 0] = (
        values[0] * source[:, 0]
        + values[3] * source[:, 1]
        + values[6] * source[:, 2]
        + values[9]
    )
    result[:, 1] = (
        values[1] * source[:, 0]
        + values[4] * source[:, 1]
        + values[7] * source[:, 2]
        + values[10]
    )
    result[:, 2] = (
        values[2] * source[:, 0]
        + values[5] * source[:, 1]
        + values[8] * source[:, 2]
        + values[11]
    )
    return result


def concatenate_3mf_geometry(chunks: Iterable[tuple[Any, Any]]) -> tuple[Any, Any]:
    vertex_chunks: list[Any] = []
    face_chunks: list[Any] = []
    offset = 0
    for vertices, faces in chunks:
        vertex_array = np.asarray(vertices, dtype=np.float64)
        face_array = np.asarray(faces, dtype=np.int64)
        if len(vertex_array) == 0 or len(face_array) == 0:
            continue
        vertex_chunks.append(vertex_array)
        face_chunks.append(face_array + offset)
        offset += len(vertex_array)
    if not vertex_chunks:
        raise ValueError("3MF build graph contains no triangle geometry")
    return np.vstack(vertex_chunks), np.vstack(face_chunks)


def load_3mf_mesh(path: Path) -> Any:
    try:
        with zipfile.ZipFile(path) as archive:
            safe, errors = safe_zip_names(archive)
            if not safe:
                raise ValueError("; ".join(errors))
            model_members = sorted(
                name for name in archive.namelist() if name.lower().endswith(".model")
            )
            parts = read_3mf_model_parts(archive, model_members)
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError, ValueError) as exc:
        raise ValueError(f"invalid 3MF package: {exc}") from exc
    validate_3mf_references(parts, "3D/3dmodel.model")

    cache: dict[tuple[str, str], tuple[Any, Any]] = {}
    active: set[tuple[str, str]] = set()

    def resolve_object(part_name: str, object_id: str) -> tuple[Any, Any]:
        key = (part_name, object_id)
        if key in cache:
            return cache[key]
        if key in active:
            raise ValueError(f"cyclic 3MF component reference at {part_name} object {object_id}")
        active.add(key)
        record = parts[part_name].objects[object_id]
        if record.triangles:
            geometry = (
                np.asarray(record.vertices, dtype=np.float64),
                np.asarray(record.triangles, dtype=np.int64),
            )
        else:
            chunks = []
            for component in record.components:
                vertices, faces = resolve_object(component.target_part, component.object_id)
                chunks.append((transform_3mf_vertices(vertices, component.transform), faces))
            geometry = concatenate_3mf_geometry(chunks)
        active.remove(key)
        cache[key] = geometry
        return geometry

    build_chunks = []
    for item in parts["3D/3dmodel.model"].build_items:
        vertices, faces = resolve_object(item.target_part, item.object_id)
        build_chunks.append((transform_3mf_vertices(vertices, item.transform), faces))
    vertices, faces = concatenate_3mf_geometry(build_chunks)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False, validate=False)


def load_mesh(path: Path) -> Any:
    if trimesh is None:
        raise RuntimeError("trimesh is unavailable")
    if path.suffix.lower() == ".3mf":
        return load_3mf_mesh(path)
    loaded = trimesh.load(str(path), process=False)
    if isinstance(loaded, trimesh.Scene):
        if not loaded.geometry:
            raise ValueError("scene contains no geometry")
        dumped = loaded.dump(concatenate=True)
        if isinstance(dumped, trimesh.Trimesh):
            mesh = dumped
        else:
            meshes = [item for item in dumped if isinstance(item, trimesh.Trimesh)]
            if not meshes:
                raise ValueError("scene contains no triangle mesh")
            mesh = trimesh.util.concatenate(meshes)
    elif isinstance(loaded, trimesh.Trimesh):
        mesh = loaded.copy()
    else:
        raise ValueError(f"unsupported mesh type: {type(loaded).__name__}")
    if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        raise ValueError("mesh contains no vertices or faces")
    mesh.merge_vertices()
    mesh.remove_unreferenced_vertices()
    return mesh


def component_face_groups(mesh: Any) -> list[Any]:
    nodes = np.arange(len(mesh.faces), dtype=np.int64)
    groups = trimesh.graph.connected_components(
        mesh.face_adjacency, nodes=nodes, min_len=1
    )
    return [np.asarray(group, dtype=np.int64) for group in groups]


def signed_volume_for_faces(vertices: Any, faces: Any) -> float:
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1], triangles[:, 2])
    return float(np.einsum("ij,ij->i", triangles[:, 0], cross).sum() / 6.0)


def inspect_mesh(path: Path, product_id: str | None, expected_bodies: int) -> tuple[Any, MeshMetrics]:
    mesh = load_mesh(path)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if not np.isfinite(vertices).all():
        raise ValueError("mesh contains non-finite coordinates")
    if faces.ndim != 2 or faces.shape[1] != 3:
        raise ValueError("mesh is not triangulated")
    if faces.min(initial=0) < 0 or faces.max(initial=-1) >= len(vertices):
        raise ValueError("mesh contains out-of-range face indices")

    directed = np.concatenate(
        (faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)]), axis=0
    )
    undirected = np.sort(directed, axis=1)
    _, inverse, counts = np.unique(
        undirected, axis=0, return_inverse=True, return_counts=True
    )
    boundary_edges = int(np.count_nonzero(counts == 1))
    nonmanifold_edges = int(np.count_nonzero(counts > 2))
    directions = np.where(directed[:, 0] < directed[:, 1], 1, -1)
    orientation_sums = np.bincount(inverse, weights=directions)
    inconsistent_edges = int(
        np.count_nonzero((counts == 2) & (np.abs(orientation_sums) > 0.5))
    )

    repeated_indices = (
        (faces[:, 0] == faces[:, 1])
        | (faces[:, 1] == faces[:, 2])
        | (faces[:, 2] == faces[:, 0])
    )
    triangles = vertices[faces]
    doubled_area = np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]),
        axis=1,
    )
    degenerate_faces = int(np.count_nonzero(repeated_indices | (doubled_area <= 1e-10)))

    groups = component_face_groups(mesh)
    component_volumes = [signed_volume_for_faces(vertices, faces[group]) for group in groups]
    signed_volume = float(sum(component_volumes))
    extents = np.ptp(vertices, axis=0)
    watertight = boundary_edges == 0 and nonmanifold_edges == 0
    consistently_wound = inconsistent_edges == 0 and nonmanifold_edges == 0
    positive_volume = bool(component_volumes) and all(volume > 1e-6 for volume in component_volumes)
    metrics = MeshMetrics(
        path=repo_path(path),
        file_type=path.suffix.lower().lstrip("."),
        product_id=product_id,
        expected_bodies=expected_bodies,
        vertices=int(len(vertices)),
        faces=int(len(faces)),
        bodies=int(len(groups)),
        boundary_edges=boundary_edges,
        nonmanifold_edges=nonmanifold_edges,
        inconsistent_edges=inconsistent_edges,
        degenerate_faces=degenerate_faces,
        watertight=watertight,
        consistently_wound=consistently_wound,
        positive_volume=positive_volume,
        signed_volume_mm3=round(signed_volume, 6),
        component_volumes_mm3=[round(value, 6) for value in component_volumes],
        extents_mm=[round(float(value), 6) for value in extents],
    )
    return mesh, metrics


def record_mesh_checks(ctx: ValidationContext, path: Path, metrics: MeshMetrics) -> None:
    prefix = f"mesh.{path.name}"
    ctx.pass_check(
        f"{prefix}.readable",
        f"Readable triangle mesh: {repo_path(path)}",
        {"vertices": metrics.vertices, "faces": metrics.faces},
    )
    if metrics.bodies == metrics.expected_bodies:
        ctx.pass_check(
            f"{prefix}.bodies",
            f"Expected connected-body count: {metrics.bodies}",
        )
    else:
        ctx.fail(
            f"{prefix}.bodies",
            f"Expected {metrics.expected_bodies} connected bodies, found {metrics.bodies}",
        )
    if metrics.watertight:
        ctx.pass_check(f"{prefix}.watertight", "Mesh is watertight")
    else:
        ctx.fail(
            f"{prefix}.watertight",
            "Mesh is not watertight",
            {
                "boundary_edges": metrics.boundary_edges,
                "nonmanifold_edges": metrics.nonmanifold_edges,
            },
        )
    if metrics.boundary_edges == 0:
        ctx.pass_check(f"{prefix}.boundary", "Boundary edge count is zero")
    else:
        ctx.fail(
            f"{prefix}.boundary",
            f"Mesh has {metrics.boundary_edges} boundary edges",
        )
    if metrics.nonmanifold_edges == 0:
        ctx.pass_check(f"{prefix}.nonmanifold", "Non-manifold edge count is zero")
    else:
        ctx.fail(
            f"{prefix}.nonmanifold",
            f"Mesh has {metrics.nonmanifold_edges} non-manifold edges",
        )
    if metrics.consistently_wound:
        ctx.pass_check(f"{prefix}.winding", "Mesh winding is consistent")
    else:
        ctx.fail(
            f"{prefix}.winding",
            f"Mesh has {metrics.inconsistent_edges} inconsistently oriented shared edges",
        )
    if metrics.positive_volume:
        ctx.pass_check(
            f"{prefix}.volume",
            "Every connected body has positive signed volume",
            {"component_volumes_mm3": metrics.component_volumes_mm3},
        )
    else:
        ctx.fail(
            f"{prefix}.volume",
            "Every connected body must have positive signed volume",
            {"component_volumes_mm3": metrics.component_volumes_mm3},
        )
    if metrics.degenerate_faces == 0:
        ctx.pass_check(f"{prefix}.degenerate", "Degenerate face count is zero")
    else:
        ctx.fail(
            f"{prefix}.degenerate",
            f"Mesh has {metrics.degenerate_faces} degenerate faces",
        )


def validate_models(ctx: ValidationContext) -> dict[str, dict[str, Path]]:
    product_files: dict[str, dict[str, Path]] = {product_id: {} for product_id in PRODUCTS}
    if MESH_IMPORT_ERROR is not None:
        ctx.fail(
            "dependency.mesh",
            "Mesh validation requires numpy and trimesh",
            {"error": str(MESH_IMPORT_ERROR)},
        )
        return product_files

    stl_files = sorted(ctx.release.rglob("*.stl")) if ctx.release.is_dir() else []
    three_mf_files = sorted(ctx.release.rglob("*.3mf")) if ctx.release.is_dir() else []
    if not stl_files:
        ctx.fail("models.stl", "No STL files found in release/v7")
    if not three_mf_files:
        ctx.fail("models.3mf", "No 3MF files found in release/v7")

    classified: dict[str, dict[str, list[Path]]] = {
        product_id: {"stl": [], "3mf": []} for product_id in PRODUCTS
    }
    collection_files: list[Path] = []
    for path in (*stl_files, *three_mf_files):
        product_id = classify_model(path)
        if product_id == "collection":
            if path.suffix.lower() != ".3mf":
                ctx.fail("models.collection.type", f"Collection model must be 3MF: {repo_path(path)}")
            collection_files.append(path)
        elif product_id in PRODUCTS:
            classified[product_id][path.suffix.lower().lstrip(".")].append(path)
        else:
            ctx.fail("models.classification", f"Unrecognized model artifact: {repo_path(path)}")

    for product_id, spec in PRODUCTS.items():
        for file_type in ("stl", "3mf"):
            matches = classified[product_id][file_type]
            minimum_count = 1
            if len(matches) < minimum_count or (file_type == "stl" and len(matches) != 1):
                ctx.fail(
                    f"models.{product_id}.{file_type}.count",
                    (
                        f"{spec.display_name} requires exactly one STL"
                        if file_type == "stl"
                        else f"{spec.display_name} requires at least one 3MF"
                    ),
                    {"paths": [repo_path(path) for path in matches]},
                )
            else:
                product_files[product_id][file_type] = matches[0]
                ctx.pass_check(
                    f"models.{product_id}.{file_type}.count",
                    f"Found {len(matches)} {spec.display_name} {file_type.upper()} artifact(s)",
                )

    if len(collection_files) < 1:
        ctx.fail(
            "models.collection.count",
            "Release requires at least one all-four collection 3MF",
            {"paths": [repo_path(path) for path in collection_files]},
        )
    else:
        ctx.pass_check(
            "models.collection.count",
            f"Found {len(collection_files)} all-four collection 3MF artifact(s)",
        )

    for path in three_mf_files:
        validate_3mf_core(ctx, path)

    for path in (*stl_files, *three_mf_files):
        classification = classify_model(path)
        expected_bodies = len(PRODUCTS) if classification == "collection" else 1
        product_id = classification if classification in PRODUCTS else None
        try:
            mesh, metrics = inspect_mesh(path, product_id, expected_bodies)
        except Exception as exc:  # Trimesh loaders expose several format-specific exceptions.
            ctx.fail(
                f"mesh.{path.name}.readable",
                f"Unreadable mesh {repo_path(path)}: {exc}",
            )
            continue
        key = repo_path(path)
        ctx.mesh_objects[key] = mesh
        ctx.meshes[key] = metrics
        record_mesh_checks(ctx, path, metrics)

    for product_id, spec in PRODUCTS.items():
        product_records: dict[str, MeshMetrics] = {}
        for file_type, path in product_files[product_id].items():
            record = ctx.meshes.get(repo_path(path))
            if record is None:
                continue
            product_records[file_type] = record
            actual = record.extents_mm
            maximum = spec.max_extent_mm
            over = [
                actual[index] - maximum[index]
                for index in range(3)
                if actual[index] > maximum[index] + ENVELOPE_TOLERANCE_MM
            ]
            if not over:
                ctx.pass_check(
                    f"envelope.{product_id}.{file_type}",
                    f"{spec.display_name} {file_type.upper()} fits its required envelope",
                    {"actual_mm": actual, "maximum_mm": list(maximum)},
                )
            else:
                ctx.fail(
                    f"envelope.{product_id}.{file_type}",
                    f"{spec.display_name} {file_type.upper()} exceeds its required envelope",
                    {
                        "actual_mm": actual,
                        "maximum_mm": list(maximum),
                        "tolerance_mm": ENVELOPE_TOLERANCE_MM,
                    },
                )
        if set(product_records) == {"stl", "3mf"}:
            stl = product_records["stl"]
            three_mf = product_records["3mf"]
            extent_delta = [
                abs(stl.extents_mm[index] - three_mf.extents_mm[index]) for index in range(3)
            ]
            volume_scale = max(abs(stl.signed_volume_mm3), abs(three_mf.signed_volume_mm3), 1.0)
            volume_delta = abs(stl.signed_volume_mm3 - three_mf.signed_volume_mm3) / volume_scale
            if max(extent_delta) <= PAIR_EXTENT_TOLERANCE_MM and volume_delta <= PAIR_VOLUME_RELATIVE_TOLERANCE:
                ctx.pass_check(
                    f"pair.{product_id}",
                    f"{spec.display_name} STL and 3MF describe the same geometry",
                    {
                        "maximum_extent_delta_mm": round(max(extent_delta), 6),
                        "relative_volume_delta": round(volume_delta, 8),
                    },
                )
            else:
                ctx.fail(
                    f"pair.{product_id}",
                    f"{spec.display_name} STL and 3MF geometry do not match",
                    {
                        "extent_delta_mm": [round(value, 6) for value in extent_delta],
                        "relative_volume_delta": round(volume_delta, 8),
                    },
                )
    return product_files


def canonical_product_id(value: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    aliases = {
        "cassette": "cassette",
        "compact_cassette": "cassette",
        "floppy": "floppy",
        "floppy_disk": "floppy",
        "vhs": "vhs",
        "vhs_tape": "vhs",
        "trailer_swift": "trailer_swift",
        "trailerswift": "trailer_swift",
    }
    return aliases.get(normalized)


def normalize_product_metadata(
    value: Any,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    warnings: list[str] = []
    result: dict[str, dict[str, Any]] = {}

    def add_item(raw_key: str, item: Any) -> None:
        if not isinstance(item, dict):
            raise ValueError(f"metadata product {raw_key!r} must be an object")
        product_id = canonical_product_id(raw_key)
        if product_id is None:
            product_id = canonical_product_id(str(item.get("key", "")))
            if product_id is not None:
                warnings.append(
                    f"legacy product key {raw_key!r}; use stable key {product_id!r}"
                )
        elif raw_key != product_id:
            warnings.append(f"legacy product key {raw_key!r}; use stable key {product_id!r}")
        if product_id is None:
            raise ValueError(f"unrecognized product metadata key {raw_key!r}")
        declared_key = item.get("key")
        if declared_key is not None and canonical_product_id(str(declared_key)) != product_id:
            raise ValueError(
                f"metadata product {raw_key!r} declares conflicting key {declared_key!r}"
            )
        if product_id in result:
            raise ValueError(f"duplicate metadata product {product_id!r}")
        result[product_id] = item

    if isinstance(value, dict):
        for key, item in value.items():
            add_item(str(key), item)
        return result, warnings
    if isinstance(value, list):
        warnings.append("legacy product list; use an object keyed by stable product ids")
        for item in value:
            if not isinstance(item, dict):
                raise ValueError("metadata product list entries must be objects")
            raw_id = item.get("id", item.get("product_id", item.get("name", "")))
            add_item(str(raw_id), item)
        return result, warnings
    raise ValueError("products metadata must be an object keyed by stable product ids")


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def metadata_value(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def measure_keyring_diameter(mesh: Any, keyring: dict[str, Any]) -> float | None:
    center_value = metadata_value(keyring, "center_mm", "center")
    if not isinstance(center_value, (list, tuple)) or len(center_value) not in (2, 3):
        return None
    center_numbers = [numeric(value) for value in center_value]
    if any(value is None for value in center_numbers):
        return None
    axis = str(keyring.get("axis", "z")).lower()
    axis_index = {"x": 0, "y": 1, "z": 2}.get(axis)
    if axis_index is None:
        return None
    plane_indices = [index for index in range(3) if index != axis_index]
    if len(center_numbers) == 2:
        center_plane = np.asarray(center_numbers, dtype=np.float64)
    else:
        center_plane = np.asarray([center_numbers[index] for index in plane_indices])
    points = np.asarray(mesh.vertices, dtype=np.float64)[:, plane_indices]
    radial = np.linalg.norm(points - center_plane, axis=1)
    nominal_radius = KEYRING_DIAMETER_MM / 2.0
    candidate = radial[(radial >= nominal_radius - 1.0) & (radial <= nominal_radius + 1.0)]
    if len(candidate) < 12:
        return None
    bins = np.arange(nominal_radius - 1.0, nominal_radius + 1.02, 0.02)
    counts, edges = np.histogram(candidate, bins=bins)
    if counts.max(initial=0) < 8:
        return None
    index = int(np.argmax(counts))
    mode = (edges[index] + edges[index + 1]) / 2.0
    ring = candidate[np.abs(candidate - mode) <= 0.06]
    if len(ring) < 8:
        return None
    return float(2.0 * np.median(ring))


def load_release_product_metadata(
    ctx: ValidationContext, manifest_data: dict[str, Any] | None
) -> tuple[dict[str, dict[str, Any]], str | None]:
    candidates = [
        path
        for path in (
            ctx.release / "PRODUCT_METADATA.json",
            ctx.release / "RELEASE_METADATA.json",
            ctx.release / "qa" / "PRODUCT_METADATA.json",
        )
        if path.is_file()
    ]
    if len(candidates) > 1:
        ctx.fail(
            "metadata.source",
            "Use only one release metadata sidecar",
            {"paths": [repo_path(path) for path in candidates]},
        )
        return {}, None
    if candidates:
        path = candidates[0]
        try:
            data = read_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            ctx.fail("metadata.readable", f"Unreadable product metadata: {exc}")
            return {}, repo_path(path)
        try:
            products, schema_warnings = normalize_product_metadata(data.get("products"))
        except ValueError as exc:
            ctx.fail("metadata.schema", f"Invalid product metadata schema: {exc}")
            return {}, repo_path(path)
        ctx.pass_check("metadata.source", f"Using product metadata from {repo_path(path)}")
        for index, warning in enumerate(schema_warnings):
            ctx.warn(
                f"metadata.schema.legacy.{index:02d}",
                warning,
                {"source": repo_path(path)},
            )
        return products, repo_path(path)
    if manifest_data is not None and "products" in manifest_data:
        try:
            products, schema_warnings = normalize_product_metadata(manifest_data.get("products"))
        except ValueError as exc:
            ctx.fail("metadata.schema", f"Invalid manifest product metadata schema: {exc}")
            return {}, f"{repo_path(ctx.release / MANIFEST_NAME)}#products"
        ctx.pass_check("metadata.source", "Using product metadata embedded in MANIFEST.json")
        for index, warning in enumerate(schema_warnings):
            ctx.warn(f"metadata.schema.legacy.{index:02d}", warning)
        return products, f"{repo_path(ctx.release / MANIFEST_NAME)}#products"
    ctx.fail(
        "metadata.source",
        "Missing product metadata; add PRODUCT_METADATA.json or MANIFEST.json#products",
    )
    return {}, None


def validate_product_metadata(
    ctx: ValidationContext,
    manifest_data: dict[str, Any] | None,
    product_files: dict[str, dict[str, Path]],
) -> None:
    metadata, source = load_release_product_metadata(ctx, manifest_data)
    for product_id, spec in PRODUCTS.items():
        item = metadata.get(product_id)
        if item is None:
            ctx.fail(
                f"metadata.{product_id}",
                f"Missing metadata for {spec.display_name}",
                {"source": source},
            )
            continue

        nfc = item.get("nfc_landing")
        if nfc is None and "nfc" in item:
            nfc = item.get("nfc")
            ctx.warn(
                f"metadata.{product_id}.nfc.legacy",
                f"{spec.display_name} uses legacy 'nfc'; rename it to 'nfc_landing'",
            )
        elif nfc is None and any(
            key in item
            for key in ("nfc_tag_diameter_mm", "nfc_protected_zone_diameter_mm", "nfc_location")
        ):
            ctx.warn(
                f"metadata.{product_id}.nfc.legacy_flat",
                f"{spec.display_name} flat NFC fields are legacy and do not replace nfc_landing",
            )
        if not isinstance(nfc, dict):
            ctx.fail(
                f"metadata.{product_id}.nfc",
                f"{spec.display_name} requires nfc_landing metadata",
            )
        else:
            diameter_value = nfc.get("diameter_mm")
            if diameter_value is None:
                diameter_value = metadata_value(nfc, "flat_diameter_mm", "nominal_diameter_mm")
                if diameter_value is not None:
                    ctx.warn(
                        f"metadata.{product_id}.nfc.diameter.legacy",
                        f"{spec.display_name} NFC landing should use 'diameter_mm'",
                    )
            diameter = numeric(diameter_value)
            flat = nfc.get("flat")
            if diameter is None or abs(diameter - NFC_DIAMETER_MM) > NFC_DIAMETER_TOLERANCE_MM:
                ctx.fail(
                    f"metadata.{product_id}.nfc.diameter",
                    f"{spec.display_name} NFC landing must be nominally 25 mm",
                    {
                        "actual_mm": diameter,
                        "nominal_mm": NFC_DIAMETER_MM,
                        "tolerance_mm": NFC_DIAMETER_TOLERANCE_MM,
                    },
                )
            else:
                ctx.pass_check(
                    f"metadata.{product_id}.nfc.diameter",
                    f"{spec.display_name} declares a {diameter:g} mm NFC landing",
                )
            if flat is not True:
                ctx.fail(
                    f"metadata.{product_id}.nfc.flat",
                    f"{spec.display_name} NFC landing metadata must declare flat: true",
                )
            else:
                ctx.pass_check(
                    f"metadata.{product_id}.nfc.flat",
                    f"{spec.display_name} declares a flat NFC landing",
                )

        if not spec.keyring_required:
            continue
        keyring = item.get("keyring")
        if keyring is None and "eyelet" in item:
            keyring = item.get("eyelet")
            ctx.warn(
                f"metadata.{product_id}.keyring.legacy",
                f"{spec.display_name} uses legacy 'eyelet'; rename it to 'keyring'",
            )
        elif keyring is None and "eyelet_opening_mm" in item:
            ctx.warn(
                f"metadata.{product_id}.keyring.legacy_flat",
                f"{spec.display_name} eyelet_opening_mm is legacy and does not replace keyring",
            )
        if not isinstance(keyring, dict):
            ctx.fail(
                f"metadata.{product_id}.keyring",
                f"{spec.display_name} requires keyring metadata",
            )
            continue
        diameter_value = keyring.get("inner_diameter_mm")
        if diameter_value is None:
            diameter_value = metadata_value(
                keyring, "hole_diameter_mm", "diameter_mm", "nominal_inner_diameter_mm"
            )
            if diameter_value is not None:
                ctx.warn(
                    f"metadata.{product_id}.keyring.diameter.legacy",
                    f"{spec.display_name} keyring should use 'inner_diameter_mm'",
                )
        diameter = numeric(diameter_value)
        if diameter is None or abs(diameter - KEYRING_DIAMETER_MM) > KEYRING_DIAMETER_TOLERANCE_MM:
            ctx.fail(
                f"metadata.{product_id}.keyring.intent",
                f"{spec.display_name} keyring intent must be 6.0 mm",
                {
                    "actual_mm": diameter,
                    "nominal_mm": KEYRING_DIAMETER_MM,
                    "tolerance_mm": KEYRING_DIAMETER_TOLERANCE_MM,
                },
            )
        else:
            ctx.pass_check(
                f"metadata.{product_id}.keyring.intent",
                f"{spec.display_name} declares a {diameter:g} mm keyring opening",
            )

        stl_path = product_files.get(product_id, {}).get("stl")
        mesh = None if stl_path is None else ctx.mesh_objects.get(repo_path(stl_path))
        measured = None if mesh is None else measure_keyring_diameter(mesh, keyring)
        if measured is None:
            ctx.warn(
                f"metadata.{product_id}.keyring.measurement",
                f"{spec.display_name} keyring geometry was not measurable; add center_mm and axis metadata",
            )
        elif abs(measured - KEYRING_DIAMETER_MM) <= KEYRING_DIAMETER_TOLERANCE_MM:
            ctx.pass_check(
                f"metadata.{product_id}.keyring.measurement",
                f"{spec.display_name} measured keyring opening is {measured:.3f} mm",
            )
        else:
            ctx.fail(
                f"metadata.{product_id}.keyring.measurement",
                f"{spec.display_name} measured keyring opening is not 6.0 mm",
                {
                    "actual_mm": round(measured, 6),
                    "nominal_mm": KEYRING_DIAMETER_MM,
                    "tolerance_mm": KEYRING_DIAMETER_TOLERANCE_MM,
                },
            )


def resolve_bambu(value: str) -> Path | None:
    candidate = Path(value).expanduser()
    if candidate.suffix.lower() == ".app" and candidate.is_dir():
        candidate = candidate / "Contents" / "MacOS" / "BambuStudio"
    if candidate.is_file():
        return candidate.resolve()
    located = shutil.which(value)
    return None if located is None else Path(located).resolve()


def run_bambu_checks(ctx: ValidationContext, bambu_value: str, timeout: int) -> None:
    executable = resolve_bambu(bambu_value)
    if executable is None:
        ctx.fail("bambu.executable", f"Bambu Studio executable not found: {bambu_value}")
        return
    ctx.pass_check("bambu.executable", f"Using Bambu Studio at {executable}")
    models = sorted(ctx.release.rglob("*.3mf"))
    critical_log_patterns = (
        re.compile(r"loading of a model file failed", re.IGNORECASE),
        re.compile(
            r"(?:slic(?:e|ing)|slicer)[^\n]{0,80}(?:failed\b|error_message=(?!success\b))",
            re.IGNORECASE,
        ),
        re.compile(r"floating cantilever", re.IGNORECASE),
        re.compile(r"segmentation fault", re.IGNORECASE),
        re.compile(r"non[- ]?manifold.*(?:error|failed)", re.IGNORECASE),
    )
    for model in models:
        with tempfile.TemporaryDirectory(prefix="rad-dad-v7-bambu-") as temp_dir:
            output_dir = Path(temp_dir)
            command = [
                str(executable),
                "--debug",
                "5",
                "--slice",
                "0",
                "--outputdir",
                str(output_dir),
                str(model.resolve()),
            ]
            try:
                completed = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                result = {
                    "model": repo_path(model),
                    "command": shlex.join(command),
                    "returncode": None,
                    "timed_out": True,
                    "output_tail": (exc.stdout or "")[-4000:],
                }
                ctx.bambu_results.append(result)
                ctx.fail(
                    f"bambu.{model.name}",
                    f"Bambu Studio timed out slicing {repo_path(model)}",
                    {"timeout_seconds": timeout},
                )
                continue
            log = completed.stdout or ""
            critical_hits = sorted(
                {
                    pattern.pattern
                    for pattern in critical_log_patterns
                    if pattern.search(log)
                }
            )
            outputs = sorted(
                path.relative_to(output_dir).as_posix()
                for path in output_dir.rglob("*")
                if path.is_file()
                and (
                    path.suffix.lower() in {".gcode", ".bgcode"}
                    or path.name.lower().endswith(".gcode.3mf")
                )
            )
            result = {
                "model": repo_path(model),
                "command": shlex.join(command),
                "returncode": completed.returncode,
                "timed_out": False,
                "critical_log_patterns": critical_hits,
                "slice_outputs": outputs,
                "output_tail": log[-4000:],
            }
            ctx.bambu_results.append(result)
            if completed.returncode != 0 or critical_hits or not outputs:
                ctx.fail(
                    f"bambu.{model.name}",
                    f"Bambu Studio slice gate failed for {repo_path(model)}",
                    {
                        "returncode": completed.returncode,
                        "critical_log_patterns": critical_hits,
                        "slice_outputs": outputs,
                    },
                )
            else:
                ctx.pass_check(
                    f"bambu.{model.name}",
                    f"Bambu Studio sliced {repo_path(model)}",
                    {"slice_outputs": outputs},
                )


def build_report(ctx: ValidationContext) -> dict[str, Any]:
    failures = [check for check in ctx.checks if check.status == "fail" and check.critical]
    warnings = [check for check in ctx.checks if check.status == "warn"]
    passes = [check for check in ctx.checks if check.status == "pass"]
    return {
        "schema": JSON_SCHEMA,
        "release": repo_path(ctx.release),
        "ok": not failures,
        "summary": {
            "critical_failures": len(failures),
            "warnings": len(warnings),
            "passes": len(passes),
            "checks": len(ctx.checks),
        },
        "manifest_sha256": ctx.manifest_sha256,
        "envelope_limits_mm": {
            product_id: list(spec.max_extent_mm) for product_id, spec in PRODUCTS.items()
        },
        "meshes": {
            path: asdict(metrics) for path, metrics in sorted(ctx.meshes.items())
        },
        "bambu": ctx.bambu_results,
        "checks": [asdict(check) for check in ctx.checks],
    }


def write_report(report: dict[str, Any], destination: str) -> Path | None:
    payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if destination == "-":
        sys.stdout.write(payload)
        return None
    path = Path(destination).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="ascii")
    return path.resolve()


def print_summary(report: dict[str, Any], json_path: Path | None) -> None:
    summary = report["summary"]
    status = "PASS" if report["ok"] else "FAIL"
    print(
        f"{status}: {summary['passes']} passed, "
        f"{summary['warnings']} warnings, "
        f"{summary['critical_failures']} critical failures.",
        file=sys.stderr,
    )
    failed_checks = [check for check in report["checks"] if check["status"] == "fail"]
    warning_checks = [check for check in report["checks"] if check["status"] == "warn"]
    for check in failed_checks[:20]:
        print(f"FAIL {check['check_id']}: {check['message']}", file=sys.stderr)
    if len(failed_checks) > 20:
        print(f"... {len(failed_checks) - 20} more failures in JSON report", file=sys.stderr)
    for check in warning_checks[:8]:
        print(f"WARN {check['check_id']}: {check['message']}", file=sys.stderr)
    if len(warning_checks) > 8:
        print(f"... {len(warning_checks) - 8} more warnings in JSON report", file=sys.stderr)
    if json_path is not None:
        print(f"JSON: {json_path}", file=sys.stderr)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Strictly validate the Rad Dad Micro Replica v7 release."
    )
    parser.add_argument(
        "--release",
        default=str(DEFAULT_RELEASE),
        help="Release directory (default: release/v7).",
    )
    parser.add_argument(
        "--json",
        default="-",
        metavar="PATH|-",
        help="Write deterministic JSON to PATH, or stdout with '-' (default).",
    )
    parser.add_argument(
        "--bambu",
        metavar="EXECUTABLE",
        help="Also slice every 3MF with this Bambu Studio executable or .app path.",
    )
    parser.add_argument(
        "--bambu-timeout",
        type=int,
        default=300,
        metavar="SECONDS",
        help="Per-file Bambu Studio timeout (default: 300).",
    )
    args = parser.parse_args(argv)
    if args.bambu_timeout <= 0:
        parser.error("--bambu-timeout must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    release = Path(args.release).expanduser()
    if not release.is_absolute():
        release = ROOT / release
    json_output = None
    if args.json != "-":
        json_output = Path(args.json).expanduser()
        if not json_output.is_absolute():
            json_output = ROOT / json_output
    ctx = ValidationContext(release=release.resolve(), json_output=json_output)

    if ctx.release.is_dir():
        ctx.pass_check("release.exists", f"Found {repo_path(ctx.release)}")
    else:
        ctx.fail("release.exists", f"Missing release directory {repo_path(ctx.release)}")

    manifest_data = validate_manifest(ctx) if ctx.release.is_dir() else None
    validate_required_artifacts(ctx)
    product_files = validate_models(ctx)
    validate_product_metadata(ctx, manifest_data, product_files)
    if args.bambu:
        run_bambu_checks(ctx, args.bambu, args.bambu_timeout)
    else:
        ctx.warn("bambu.skipped", "Bambu Studio slice checks were not requested")

    report = build_report(ctx)
    try:
        json_path = write_report(report, args.json)
    except OSError as exc:
        print(f"FAIL: could not write JSON report: {exc}", file=sys.stderr)
        return 2
    print_summary(report, json_path)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
