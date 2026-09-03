#!/usr/bin/env python3
"""Render and verify an honest material study of the current three media models.

The preview is derived directly from the sealed v9 STL files. It is a digital
visualization, not a photograph, slicer result, print-quality claim, or physical
acceptance artifact. No release package is modified by this tool.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, PngImagePlugin
import trimesh


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from v7_release_packaging import (  # noqa: E402
    BRAND,
    _camera_basis,
    _hex_rgb,
    _mix_rgb,
    _preview_crease_edges,
)


OUTPUT_PATH = REPO_ROOT / "docs" / "previews" / "Rad_Dad_Current_Three_PETG_Material_Study.png"
METADATA_PATH = OUTPUT_PATH.with_suffix(".json")
RENDER_SIZE = (1800, 1100)
CAMERA_DIRECTION = (0.38, -0.78, 1.28)
CAMERA_UP = (0.0, 0.0, 1.0)
DISCLAIMER = (
    "DIGITAL RENDER — NOT A PHOTO OR PHYSICAL PRINT. "
    "COLOR, LAYER LINES, AND FINISH WILL VARY."
)


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    revision: str
    source: str
    color: str
    x_mm: float
    y_mm: float
    rotation_degrees: float
    expected_extents_mm: tuple[float, float, float]


MODELS = (
    ModelSpec(
        key="cassette",
        label="COMPACT CASSETTE",
        revision="V38",
        source="release/v9/stl/Rad_Dad_Cassette_v38_BINARY.stl",
        color="#A6EF12",
        x_mm=-66.0,
        y_mm=-1.5,
        rotation_degrees=-4.0,
        expected_extents_mm=(58.162, 30.260, 6.685),
    ),
    ModelSpec(
        key="floppy",
        label="3.5-INCH FLOPPY",
        revision="V22",
        source="release/v9/stl/Rad_Dad_Floppy_v22_BINARY.stl",
        color="#1CB5F4",
        x_mm=0.0,
        y_mm=4.0,
        rotation_degrees=3.0,
        expected_extents_mm=(44.360, 36.916, 4.130),
    ),
    ModelSpec(
        key="vhs",
        label="MINI VHS",
        revision="V5",
        source="release/v9/stl/Rad_Dad_Mini_VHS_v5_BINARY.stl",
        color="#FF3476",
        x_mm=65.0,
        y_mm=-1.0,
        rotation_degrees=-3.0,
        expected_extents_mm=(65.800, 31.900, 7.000),
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    return resolved.relative_to(REPO_ROOT).as_posix() if resolved.is_relative_to(REPO_ROOT) else str(resolved)


def _font(size: int, *, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ("DejaVuSans-Bold.ttf", "Arial Bold.ttf") if bold else ("DejaVuSans.ttf", "Arial.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, max(1, int(size)))
        except OSError:
            continue
    return ImageFont.load_default()


def _unit(vector: np.ndarray) -> np.ndarray:
    return vector / max(float(np.linalg.norm(vector)), 1.0e-12)


def _load_scene() -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for spec in MODELS:
        source = REPO_ROOT / spec.source
        mesh = trimesh.load_mesh(source, file_type="stl", process=True)
        if isinstance(mesh, trimesh.Scene):
            mesh = mesh.dump(concatenate=True)
        if not isinstance(mesh, trimesh.Trimesh):
            raise RuntimeError(f"Could not load a triangle mesh: {spec.source}")
        mesh.remove_unreferenced_vertices()
        extents = np.asarray(mesh.extents, dtype=np.float64)
        if not np.allclose(extents, spec.expected_extents_mm, rtol=0.0, atol=0.003):
            raise RuntimeError(f"{spec.label} envelope drifted: {extents.tolist()}")
        if not mesh.is_watertight:
            raise RuntimeError(f"{spec.label} STL is not watertight after normal processing")

        centered = mesh.copy()
        center_xy = (centered.bounds[0, :2] + centered.bounds[1, :2]) / 2.0
        centered.apply_translation((-center_xy[0], -center_xy[1], -centered.bounds[0, 2]))
        rotation = trimesh.transformations.rotation_matrix(
            np.deg2rad(spec.rotation_degrees),
            (0.0, 0.0, 1.0),
        )
        centered.apply_transform(rotation)
        centered.apply_translation((spec.x_mm, spec.y_mm, 0.0))
        loaded.append(
            {
                "spec": spec,
                "mesh": centered,
                "source_sha256": sha256(source),
                "source_bytes": source.stat().st_size,
                "source_extents_mm": [round(float(value), 3) for value in extents],
            }
        )
    return loaded


def _background(size: tuple[int, int], seed: int = 369) -> Image.Image:
    width, height = size
    yy, xx = np.mgrid[0:height, 0:width]
    x = xx / max(width - 1, 1)
    y = yy / max(height - 1, 1)
    spotlight = np.exp(-(((x - 0.50) / 0.47) ** 2 + ((y - 0.53) / 0.58) ** 2) * 2.1)
    lower_glow = np.exp(-(((x - 0.52) / 0.62) ** 2 + ((y - 0.88) / 0.23) ** 2) * 2.7)
    base = np.zeros((height, width, 3), dtype=np.float64)
    base[:] = np.array((5.0, 11.0, 18.0))
    base += spotlight[..., None] * np.array((11.0, 21.0, 20.0))
    base += lower_glow[..., None] * np.array((14.0, 7.0, 3.0))
    base -= (np.abs(x - 0.5) * 12.0 + np.abs(y - 0.5) * 5.0)[..., None]
    rng = np.random.default_rng(seed)
    base += rng.normal(0.0, 0.85, base.shape[:2])[..., None]
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))


def _scaled_font(size: float, render_scale: float, *, bold: bool = True):
    return _font(round(size * render_scale), bold=bold)


def render_material_study(
    path: Path,
    *,
    size: tuple[int, int] = RENDER_SIZE,
    supersample: int = 2,
) -> tuple[Path, list[dict[str, Any]]]:
    if size[0] * 11 != size[1] * 18:
        raise ValueError("material study must use the 18:11 aspect ratio")
    if supersample < 1:
        raise ValueError("supersample must be at least one")

    items = _load_scene()
    render_size = (size[0] * supersample, size[1] * supersample)
    render_scale = render_size[0] / RENDER_SIZE[0]
    image = _background(render_size)
    draw = ImageDraw.Draw(image)
    width, height = render_size

    camera, right, up = _camera_basis(
        "detail",
        "flat",
        camera_direction=CAMERA_DIRECTION,
        up_direction=CAMERA_UP,
    )
    all_vertices = np.vstack([np.asarray(item["mesh"].vertices) for item in items])
    projected_x = all_vertices @ right
    projected_y = all_vertices @ up
    draw_box = (
        92 * render_scale,
        245 * render_scale,
        width - 92 * render_scale,
        height - 245 * render_scale,
    )
    scale = min(
        (draw_box[2] - draw_box[0]) / max(float(np.ptp(projected_x)), 1.0e-6),
        (draw_box[3] - draw_box[1]) / max(float(np.ptp(projected_y)), 1.0e-6),
    ) * 0.94
    offset_x = (draw_box[0] + draw_box[2]) / 2.0 - float(projected_x.min() + projected_x.max()) * scale / 2.0
    offset_y = (draw_box[1] + draw_box[3]) / 2.0 + float(projected_y.min() + projected_y.max()) * scale / 2.0

    # Product-photo floor: a soft pool of light and a restrained horizon line.
    floor_layer = Image.new("RGBA", render_size, (0, 0, 0, 0))
    floor_draw = ImageDraw.Draw(floor_layer)
    floor_draw.ellipse(
        (100 * render_scale, 420 * render_scale, width - 100 * render_scale, height - 115 * render_scale),
        fill=(25, 46, 42, 42),
    )
    floor_layer = floor_layer.filter(ImageFilter.GaussianBlur(42 * render_scale))
    image = Image.alpha_composite(image.convert("RGBA"), floor_layer).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.line(
        (110 * render_scale, 820 * render_scale, width - 110 * render_scale, 820 * render_scale),
        fill=(88, 112, 109),
        width=max(1, round(render_scale)),
    )

    model_masks: list[Image.Image] = []
    render_records: list[dict[str, Any]] = []
    for item_index, item in enumerate(items):
        spec: ModelSpec = item["spec"]
        mesh: trimesh.Trimesh = item["mesh"]
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces, dtype=np.int64)
        triangles = vertices[faces]
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1.0e-12)
        facing = normals @ camera
        visible = np.flatnonzero(facing > 0.015)
        screen_x = vertices @ right
        screen_y = vertices @ up
        depth = vertices @ camera
        face_depth = depth[faces].mean(axis=1)
        order = visible[np.argsort(face_depth[visible], kind="stable")]
        pixel_x = offset_x + screen_x * scale
        pixel_y = offset_y - screen_y * scale

        mask = Image.new("L", render_size, 0)
        mask_draw = ImageDraw.Draw(mask)
        for face_index in order:
            mask_draw.polygon(
                [(pixel_x[vertex], pixel_y[vertex]) for vertex in faces[face_index]],
                fill=255,
            )
        model_masks.append(mask)

        # Two shadows anchor the real silhouette without pretending to be a photo.
        for shift_x, shift_y, opacity, blur in (
            (17, 28, 100, 22),
            (5, 10, 78, 7),
        ):
            shifted = Image.new("L", render_size, 0)
            shifted.paste(mask, (round(shift_x * render_scale), round(shift_y * render_scale)))
            shifted = shifted.filter(ImageFilter.GaussianBlur(blur * render_scale))
            shadow = Image.new("RGB", render_size, (0, 0, 0))
            image.paste(shadow, mask=shifted.point(lambda value: value * opacity // 255))

        draw = ImageDraw.Draw(image)
        base = np.asarray(_hex_rgb(spec.color), dtype=np.float64)
        panel = np.asarray(_hex_rgb(BRAND["panel"]), dtype=np.float64)
        cream = np.asarray(_hex_rgb(BRAND["cream"]), dtype=np.float64)
        key_light = _unit(camera + up * 0.72 - right * 0.72)
        fill_light = _unit(camera + up * 0.12 + right * 0.92)
        half_vector = _unit(key_light + camera)
        centroids = triangles.mean(axis=1)
        local_height = centroids[:, 2]
        local_height = (local_height - local_height.min()) / max(float(np.ptp(local_height)), 1.0e-6)

        for face_index in order:
            normal = normals[face_index]
            key = max(0.0, float(normal @ key_light))
            fill = max(0.0, float(normal @ fill_light))
            edge = max(0.0, 1.0 - float(normal @ camera))
            specular = max(0.0, float(normal @ half_vector)) ** 24
            grain = 0.018 * np.sin(float(centroids[face_index, 0]) * 0.74 + item_index * 1.9)
            illumination = float(
                np.clip(
                    0.20 + 0.48 * key + 0.14 * fill + 0.10 * local_height[face_index] + 0.06 * edge + grain,
                    0.18,
                    0.98,
                )
            )
            color = panel * (1.0 - illumination) + base * illumination
            color = color * (1.0 - 0.34 * specular) + cream * (0.34 * specular)
            draw.polygon(
                [(pixel_x[vertex], pixel_y[vertex]) for vertex in faces[face_index]],
                fill=tuple(np.clip(color, 0, 255).astype(np.uint8)),
            )

        # Real mesh creases stay subtle; there is no wireframe over every triangle.
        crease_color = _mix_rgb(_hex_rgb(BRAND["ink"]), _hex_rgb(spec.color), 0.42)
        for edge in _preview_crease_edges(faces, normals, facing, max_edges=12000):
            draw.line(
                [(pixel_x[vertex], pixel_y[vertex]) for vertex in edge],
                fill=crease_color,
                width=max(1, round(0.75 * render_scale)),
            )

        bounds = (
            float(pixel_x.min()),
            float(pixel_y.min()),
            float(pixel_x.max()),
            float(pixel_y.max()),
        )
        render_records.append({**item, "pixel_bounds": bounds})

    # A fine satin grain is clipped to the actual projected model silhouettes.
    union_mask = Image.new("L", render_size, 0)
    for mask in model_masks:
        union_mask = Image.fromarray(np.maximum(np.asarray(union_mask), np.asarray(mask)).astype(np.uint8))
    rng = np.random.default_rng(369)
    grain = rng.normal(128.0, 8.0, (height, width)).clip(0, 255).astype(np.uint8)
    grain_rgb = Image.merge("RGB", (Image.fromarray(grain),) * 3)
    textured = Image.blend(image, grain_rgb, 0.035)
    image.paste(textured, mask=union_mask)
    draw = ImageDraw.Draw(image)

    # Header and product labels turn the scene into a useful handoff artifact.
    draw.text(
        (92 * render_scale, 60 * render_scale),
        "RAD DAD  /  RETRO RIOT V9",
        font=_scaled_font(21, render_scale),
        fill=BRAND["lime"],
        anchor="lm",
    )
    draw.text(
        (92 * render_scale, 130 * render_scale),
        "THE CURRENT THREE",
        font=_scaled_font(58, render_scale),
        fill=BRAND["cream"],
        anchor="lm",
    )
    draw.text(
        (94 * render_scale, 184 * render_scale),
        "CASSETTE  •  FLOPPY  •  VHS   /   TRUE RELATIVE SIZE",
        font=_scaled_font(22, render_scale, bold=False),
        fill="#A9BAC4",
        anchor="lm",
    )
    badge_right = width - 92 * render_scale
    badge_width = 370 * render_scale
    draw.rounded_rectangle(
        (badge_right - badge_width, 50 * render_scale, badge_right, 91 * render_scale),
        radius=20 * render_scale,
        fill="#111D26",
        outline=BRAND["blue"],
        width=max(1, round(2 * render_scale)),
    )
    draw.text(
        (badge_right - badge_width / 2, 71 * render_scale),
        "DIGITAL PETG MATERIAL STUDY",
        font=_scaled_font(16, render_scale),
        fill=BRAND["cream"],
        anchor="mm",
    )

    for record in render_records:
        spec = record["spec"]
        x0, _, x1, y1 = record["pixel_bounds"]
        label_y = min(y1 + 27 * render_scale, 842 * render_scale)
        center_x = (x0 + x1) / 2.0
        label = f"{spec.label}  {spec.revision}"
        text_box = draw.textbbox((0, 0), label, font=_scaled_font(15, render_scale))
        label_width = text_box[2] - text_box[0] + 46 * render_scale
        draw.rounded_rectangle(
            (
                center_x - label_width / 2,
                label_y - 18 * render_scale,
                center_x + label_width / 2,
                label_y + 18 * render_scale,
            ),
            radius=18 * render_scale,
            fill="#09131D",
            outline=spec.color,
            width=max(1, round(2 * render_scale)),
        )
        draw.ellipse(
            (
                center_x - label_width / 2 + 12 * render_scale,
                label_y - 5 * render_scale,
                center_x - label_width / 2 + 22 * render_scale,
                label_y + 5 * render_scale,
            ),
            fill=spec.color,
        )
        draw.text(
            (center_x + 7 * render_scale, label_y),
            label,
            font=_scaled_font(15, render_scale),
            fill=BRAND["cream"],
            anchor="mm",
        )

    # The shared projection allows an honest 25 mm reference bar.
    bar_x = 100 * render_scale
    bar_y = 930 * render_scale
    bar_length = 25.0 * scale
    draw.line((bar_x, bar_y, bar_x + bar_length, bar_y), fill=BRAND["cream"], width=max(2, round(3 * render_scale)))
    for x_tick in (bar_x, bar_x + bar_length):
        draw.line((x_tick, bar_y - 8 * render_scale, x_tick, bar_y + 8 * render_scale), fill=BRAND["cream"], width=max(2, round(3 * render_scale)))
    draw.text(
        (bar_x + bar_length / 2, bar_y + 27 * render_scale),
        "25 MM REFERENCE",
        font=_scaled_font(13, render_scale),
        fill="#A9BAC4",
        anchor="mm",
    )
    draw.text(
        (width - 92 * render_scale, 920 * render_scale),
        "EXAMPLE SATIN PETG COLORS  •  ONE COLOR PER MODEL",
        font=_scaled_font(17, render_scale),
        fill="#D7E1E5",
        anchor="rm",
    )
    draw.text(
        (width - 92 * render_scale, 953 * render_scale),
        "GENERATED DIRECTLY FROM THE CURRENT SEALED V9 STL GEOMETRY",
        font=_scaled_font(14, render_scale, bold=False),
        fill="#8FA2AE",
        anchor="rm",
    )
    draw.rounded_rectangle(
        (72 * render_scale, 994 * render_scale, width - 72 * render_scale, 1056 * render_scale),
        radius=18 * render_scale,
        fill="#2B111A",
        outline=BRAND["pink"],
        width=max(1, round(2 * render_scale)),
    )
    draw.text(
        (width / 2, 1025 * render_scale),
        DISCLAIMER,
        font=_scaled_font(17, render_scale),
        fill="#FFE8EF",
        anchor="mm",
    )

    if supersample > 1:
        image = image.resize(size, Image.Resampling.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("Title", "Rad Dad Current Three PETG Material Study")
    png_info.add_text("Source", "Current sealed v9 STL geometry")
    png_info.add_text("PhysicalProof", "false")
    png_info.add_text("Disclaimer", DISCLAIMER)
    image.save(path, format="PNG", optimize=False, compress_level=9, pnginfo=png_info)
    return path, items


def metadata_for(output: Path, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "title": "Rad Dad Current Three PETG Material Study",
        "render_type": "digital_material_study",
        "physical_proof": False,
        "disclaimer": DISCLAIMER,
        "relative_scale": True,
        "camera": {
            "projection": "orthographic",
            "direction": list(CAMERA_DIRECTION),
            "up": list(CAMERA_UP),
        },
        "renderer": {
            "path": repo_path(Path(__file__)),
            "sha256": sha256(Path(__file__).resolve()),
        },
        "models": [
            {
                "key": item["spec"].key,
                "label": item["spec"].label,
                "revision": item["spec"].revision,
                "source": item["spec"].source,
                "source_sha256": item["source_sha256"],
                "source_bytes": item["source_bytes"],
                "source_extents_mm": item["source_extents_mm"],
                "material_visualization": "single-color satin PETG",
                "preview_color": item["spec"].color,
            }
            for item in items
        ],
        "output": {
            "path": repo_path(output),
            "sha256": sha256(output),
            "width": RENDER_SIZE[0],
            "height": RENDER_SIZE[1],
        },
    }


def write_metadata(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def check_committed_preview() -> None:
    if not OUTPUT_PATH.is_file() or not METADATA_PATH.is_file():
        raise RuntimeError("Current-three preview or provenance metadata is missing")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if (
        metadata.get("schema_version") != 1
        or metadata.get("render_type") != "digital_material_study"
        or metadata.get("relative_scale") is not True
        or metadata.get("physical_proof") is not False
        or metadata.get("disclaimer") != DISCLAIMER
    ):
        raise RuntimeError("Preview metadata must fail closed as digital-only")
    renderer = metadata.get("renderer", {})
    if (
        renderer.get("path") != repo_path(Path(__file__))
        or renderer.get("sha256") != sha256(Path(__file__).resolve())
    ):
        raise RuntimeError("Renderer changed without regenerating preview provenance")
    output = metadata.get("output", {})
    if (
        output.get("path") != repo_path(OUTPUT_PATH)
        or output.get("width") != RENDER_SIZE[0]
        or output.get("height") != RENDER_SIZE[1]
        or output.get("sha256") != sha256(OUTPUT_PATH)
    ):
        raise RuntimeError("Preview image hash does not match provenance")
    with Image.open(OUTPUT_PATH) as image:
        if image.size != RENDER_SIZE or image.format != "PNG":
            raise RuntimeError(f"Preview must be a {RENDER_SIZE[0]} x {RENDER_SIZE[1]} PNG")
        if image.info.get("PhysicalProof") != "false" or image.info.get("Disclaimer") != DISCLAIMER:
            raise RuntimeError("Preview PNG is missing its digital-only truth metadata")

    current = _load_scene()
    expected_models = metadata.get("models", [])
    if len(expected_models) != len(MODELS):
        raise RuntimeError("Preview provenance must name exactly the current three models")
    for item, recorded in zip(current, expected_models):
        spec: ModelSpec = item["spec"]
        if recorded.get("key") != spec.key or recorded.get("revision") != spec.revision:
            raise RuntimeError(f"Preview model identity drifted for {spec.key}")
        if (
            recorded.get("source") != spec.source
            or recorded.get("source_bytes") != item["source_bytes"]
        ):
            raise RuntimeError(f"Preview source receipt drifted for {spec.key}")
        if recorded.get("source_sha256") != item["source_sha256"]:
            raise RuntimeError(f"Preview source hash drifted for {spec.key}")
        if recorded.get("source_extents_mm") != item["source_extents_mm"]:
            raise RuntimeError(f"Preview source dimensions drifted for {spec.key}")

    # Exercise the renderer in CI without rewriting the reviewed 1800px asset.
    with tempfile.TemporaryDirectory(prefix="rad-dad-material-study-") as temporary:
        smoke = Path(temporary) / "smoke.png"
        render_material_study(smoke, size=(900, 550), supersample=1)
        with Image.open(smoke) as image:
            colors = image.convert("RGB").resize((180, 110)).getcolors(maxcolors=180 * 110)
            if image.size != (900, 550) or colors is None or len(colors) < 250:
                raise RuntimeError("Material-study smoke render lacks expected visual depth")

    print(
        "Current-three material study verified: three sealed STL sources, "
        "digital-only provenance, output hash, dimensions, and smoke render pass."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the committed image and run a smoke render")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="PNG output path")
    parser.add_argument("--metadata", type=Path, default=METADATA_PATH, help="JSON provenance output path")
    args = parser.parse_args()

    if args.check:
        check_committed_preview()
        return 0

    output = args.output.expanduser().resolve()
    metadata_path = args.metadata.expanduser().resolve()
    rendered, items = render_material_study(output)
    write_metadata(metadata_path, metadata_for(rendered, items))
    print(f"Wrote digital material study: {rendered}")
    print(f"Wrote provenance: {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
