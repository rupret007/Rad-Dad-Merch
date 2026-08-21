"""Self-contained CAD primitives used by the v7 micro-replica builders.

The release must rebuild from a clean clone, so this module intentionally has
no dependency on the historical sibling ``work`` directory.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from shapely import affinity
from shapely.geometry import Point, Polygon, box as sbox
from shapely.ops import unary_union


def _font(candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    return candidates[-1]


FONT_BOLD = _font(
    (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "DejaVuSans-Bold.ttf",
    )
)
FONT_ITALIC = _font(
    (
        "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        "DejaVuSans-BoldOblique.ttf",
    )
)
FONT_CONDENSED = _font(
    (
        "/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        "DejaVuSansCondensed-Bold.ttf",
    )
)


def polygons(shape):
    if shape.is_empty:
        return []
    if shape.geom_type == "Polygon":
        return [shape]
    if shape.geom_type == "MultiPolygon":
        return list(shape.geoms)
    result = []
    for geometry in getattr(shape, "geoms", []):
        result.extend(polygons(geometry))
    return result


def extrude_shape(shape, z0: float, z1: float) -> trimesh.Trimesh:
    meshes = []
    for polygon in polygons(shape.buffer(0)):
        mesh = trimesh.creation.extrude_polygon(
            polygon, height=z1 - z0, engine="earcut"
        )
        mesh.apply_translation((0.0, 0.0, z0))
        meshes.append(mesh)
    if not meshes:
        raise ValueError("Cannot extrude an empty shape")
    return meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)


def rounded_shape(
    width: float,
    height: float,
    radius: float,
    center_x: float = 0.0,
    center_y: float = 0.0,
):
    core = sbox(
        center_x - width / 2 + radius,
        center_y - height / 2 + radius,
        center_x + width / 2 - radius,
        center_y + height / 2 - radius,
    )
    return core.buffer(radius, quad_segs=8)


def rounded_bounds(
    x0: float, y0: float, x1: float, y1: float, radius: float
):
    return sbox(x0 + radius, y0 + radius, x1 - radius, y1 - radius).buffer(
        radius, quad_segs=24
    )


def annulus_shape(cx: float, cy: float, inner: float, outer: float):
    return Point(cx, cy).buffer(outer, quad_segs=48).difference(
        Point(cx, cy).buffer(inner, quad_segs=48)
    )


def rotated_rect(
    width: float, height: float, angle: float, center_x: float, center_y: float
):
    shape = sbox(
        center_x - width / 2,
        center_y - height / 2,
        center_x + width / 2,
        center_y + height / 2,
    )
    return affinity.rotate(
        shape, angle, origin=(center_x, center_y), use_radians=False
    )


def star_shape(
    cx: float,
    cy: float,
    outer_radius: float,
    inner_radius: float,
    teeth: int = 9,
    phase: float = 90.0,
):
    points = []
    for index in range(teeth * 2):
        angle = math.radians(phase + index * 180.0 / teeth)
        radius = outer_radius if index % 2 == 0 else inner_radius
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return Polygon(points)


def union_meshes(parts) -> trimesh.Trimesh:
    valid = [part for part in parts if part is not None and len(part.faces)]
    if not valid:
        raise ValueError("Cannot union an empty mesh collection")
    if len(valid) == 1:
        return valid[0]
    result = trimesh.boolean.union(valid, engine="manifold")
    if result is None:
        raise RuntimeError("Manifold union failed")
    return result


def difference_mesh(base: trimesh.Trimesh, cutters) -> trimesh.Trimesh:
    result = trimesh.boolean.difference([base] + list(cutters), engine="manifold")
    if result is None:
        raise RuntimeError("Manifold difference failed")
    return result


def raised_text(
    text: str,
    target_w: float,
    target_h: float,
    cx: float,
    cy: float,
    z0: float,
    z1: float,
    font_path: str = FONT_BOLD,
    pixel: float = 0.14,
) -> trimesh.Trimesh:
    canvas = Image.new("L", (2200, 520), 0)
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(font_path, 380)
    bounds = draw.textbbox((0, 0), text, font=font)
    draw.text(
        (
            (2200 - (bounds[2] - bounds[0])) / 2 - bounds[0],
            (520 - (bounds[3] - bounds[1])) / 2 - bounds[1],
        ),
        text,
        fill=255,
        font=font,
    )
    crop_box = canvas.getbbox()
    if crop_box is None:
        raise ValueError(f"No glyphs rendered for {text!r}")
    glyphs = canvas.crop(crop_box)
    width = max(1, round(target_w / pixel))
    height = max(1, round(target_h / pixel))
    glyphs.thumbnail((width, height), Image.Resampling.LANCZOS)
    mask = Image.new("L", (width, height), 0)
    mask.paste(glyphs, ((width - glyphs.width) // 2, (height - glyphs.height) // 2))
    pixels = mask.load()
    x_base = cx - width * pixel / 2
    y_base = cy - height * pixel / 2
    overlap = min(0.025, pixel * 0.18)
    runs = []
    for row in range(height):
        column = 0
        while column < width:
            while column < width and pixels[column, row] < 128:
                column += 1
            start = column
            while column < width and pixels[column, row] >= 128:
                column += 1
            if column <= start:
                continue
            x0 = x_base + start * pixel - overlap
            x1 = x_base + column * pixel + overlap
            y0 = y_base + (height - row - 1) * pixel - overlap
            y1 = y0 + pixel + 2 * overlap
            run = trimesh.creation.box(extents=(x1 - x0, y1 - y0, z1 - z0))
            run.apply_translation(
                ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
            )
            runs.append(run)
    return union_meshes(runs)


def shell_ring(
    outer_w: float,
    outer_h: float,
    outer_r: float,
    inset: float,
    z0: float,
    z1: float,
    cx: float = 0.0,
    cy: float = 0.0,
) -> trimesh.Trimesh:
    outer = rounded_shape(outer_w, outer_h, outer_r, cx, cy)
    inner = rounded_shape(
        outer_w - 2 * inset,
        outer_h - 2 * inset,
        max(0.2, outer_r - inset),
        cx,
        cy,
    )
    return extrude_shape(outer.difference(inner), z0, z1)


def bed_normalized(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    result = mesh.copy()
    result.apply_translation((0.0, 0.0, -float(result.bounds[0, 2])))
    result.remove_unreferenced_vertices()
    return result
