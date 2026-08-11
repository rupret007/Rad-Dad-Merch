#!/usr/bin/env python3
"""Build the current cassette, floppy, and VHS as one balanced A1 Mini plate."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "release/v9/3mf/"
    "Rad_Dad_Retro_Riot_v9_ALL_FOUR_A1_MINI_0.4_TREE_SUPPORT_PROJECT.3mf"
)
OUTPUT = (
    ROOT
    / "release/v9/3mf/"
    "Rad_Dad_Retro_Riot_v9_CURRENT_THREE_CASSETTE_FLOPPY_VHS_"
    "A1_MINI_0.4_PROJECT.3mf"
)

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
ET.register_namespace("", CORE_NS)
Q = lambda tag: f"{{{CORE_NS}}}{tag}"

# The lower pair is centered as a group. The smaller floppy is centered above it.
TARGET_CENTERS_MM = {
    "cassette": (48.1, 55.0),
    "floppy": (90.0, 120.0),
    "vhs": (128.1, 55.0),
}


def model_kind(name: str) -> str | None:
    lower = name.lower()
    for kind in TARGET_CENTERS_MM:
        if kind in lower:
            return kind
    return None


def fmt(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text not in {"", "-0"} else "0"


def shift_mesh_to_center(obj: ET.Element, target: tuple[float, float]) -> tuple[float, ...]:
    vertices = obj.findall(f".//{Q('vertex')}")
    if not vertices:
        raise RuntimeError(f"Object {obj.attrib.get('name')} has no mesh vertices")

    xs = [float(v.attrib["x"]) for v in vertices]
    ys = [float(v.attrib["y"]) for v in vertices]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    dx = target[0] - cx
    dy = target[1] - cy

    for vertex in vertices:
        vertex.set("x", fmt(float(vertex.attrib["x"]) + dx))
        vertex.set("y", fmt(float(vertex.attrib["y"]) + dy))

    return (
        min(xs) + dx,
        max(xs) + dx,
        min(ys) + dy,
        max(ys) + dy,
    )


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def make_thumbnail(bounds: dict[str, tuple[float, ...]]) -> bytes:
    """Create a simple, accurate top-down plate thumbnail without dependencies."""
    width = height = 512
    pixels = bytearray((13, 18, 24, 255) * (width * height))

    def put(x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            i = (y * width + x) * 4
            pixels[i : i + 4] = bytes(color)

    def rect(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int, int]) -> None:
        x0, x1 = sorted((max(0, x0), min(width - 1, x1)))
        y0, y1 = sorted((max(0, y0), min(height - 1, y1)))
        row = bytes(color) * (x1 - x0 + 1)
        for y in range(y0, y1 + 1):
            i = (y * width + x0) * 4
            pixels[i : i + len(row)] = row

    def ring(cx: int, cy: int, radius: int, color: tuple[int, int, int, int]) -> None:
        for y in range(cy - radius - 1, cy + radius + 2):
            for x in range(cx - radius - 1, cx + radius + 2):
                d2 = (x - cx) ** 2 + (y - cy) ** 2
                if (radius - 2) ** 2 <= d2 <= (radius + 1) ** 2:
                    put(x, y, color)

    margin = 36
    scale = (width - 2 * margin) / 180.0

    def px(x: float) -> int:
        return round(margin + x * scale)

    def py(y: float) -> int:
        return round(height - margin - y * scale)

    grid = (38, 49, 59, 255)
    for mm in range(0, 181, 20):
        gx = px(mm)
        gy = py(mm)
        rect(gx, margin, gx, height - margin, grid)
        rect(margin, gy, width - margin, gy, grid)
    border = (100, 120, 132, 255)
    rect(margin - 2, margin - 2, width - margin + 2, margin, border)
    rect(margin - 2, height - margin, width - margin + 2, height - margin + 2, border)
    rect(margin - 2, margin, margin, height - margin, border)
    rect(width - margin, margin, width - margin + 2, height - margin, border)

    fill = (35, 169, 103, 255)
    edge = (125, 255, 187, 255)
    dark = (8, 65, 44, 255)
    for kind, (x0, x1, y0, y1) in bounds.items():
        left, right = px(x0), px(x1)
        top, bottom = py(y1), py(y0)
        rect(left, top, right, bottom, fill)
        rect(left, top, right, top + 2, edge)
        rect(left, bottom - 2, right, bottom, edge)
        rect(left, top, left + 2, bottom, edge)
        rect(right - 2, top, right, bottom, edge)
        if kind in {"cassette", "vhs"}:
            cy = (top + bottom) // 2
            ring(left + (right - left) // 3, cy, 11, dark)
            ring(left + 2 * (right - left) // 3, cy, 11, dark)
        else:
            rect(left + 8, top + 8, right - 8, top + 18, dark)
            rect(left + 12, bottom - 24, right - 12, bottom - 9, dark)

    raw = b"".join(
        b"\x00" + bytes(pixels[y * width * 4 : (y + 1) * width * 4])
        for y in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )


def build(source: Path = SOURCE, output: Path = OUTPUT) -> Path:
    """Build and return the balanced current-media Bambu project."""

    if not source.exists():
        raise FileNotFoundError(source)

    with ZipFile(source, "r") as source_zip:
        files = {name: source_zip.read(name) for name in source_zip.namelist()}

    root = ET.fromstring(files["3D/3dmodel.model"])
    resources = root.find(Q("resources"))
    build_node = root.find(Q("build"))
    if resources is None or build_node is None:
        raise RuntimeError("Source 3MF is missing resources or build data")

    keep_ids: set[str] = set()
    arranged_bounds: dict[str, tuple[float, ...]] = {}
    for obj in list(resources.findall(Q("object"))):
        kind = model_kind(obj.attrib.get("name", ""))
        if kind is None:
            resources.remove(obj)
            continue
        if kind in arranged_bounds:
            raise RuntimeError(f"Duplicate {kind} object in source 3MF")
        keep_ids.add(obj.attrib["id"])
        arranged_bounds[kind] = shift_mesh_to_center(obj, TARGET_CENTERS_MM[kind])

    if set(arranged_bounds) != set(TARGET_CENTERS_MM):
        missing = set(TARGET_CENTERS_MM) - set(arranged_bounds)
        raise RuntimeError(f"Missing current models: {sorted(missing)}")

    for item in list(build_node.findall(Q("item"))):
        if item.attrib.get("objectid") not in keep_ids:
            build_node.remove(item)
        else:
            item.attrib.pop("transform", None)

    files["3D/3dmodel.model"] = ET.tostring(
        root, encoding="utf-8", xml_declaration=True
    )
    files["Metadata/thumbnail.png"] = make_thumbnail(arranged_bounds)

    settings_name = "Metadata/project_settings.config"
    if settings_name in files:
        settings = json.loads(files[settings_name].decode("utf-8"))
        settings["enable_support"] = "0"
        settings["raft_layers"] = "0"
        settings["print_sequence"] = "by layer"
        files[settings_name] = json.dumps(
            settings, ensure_ascii=True, separators=(",", ":")
        ).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as output_zip:
        for name, payload in files.items():
            output_zip.writestr(name, payload)

    print(output)
    for kind in ("cassette", "floppy", "vhs"):
        x0, x1, y0, y1 = arranged_bounds[kind]
        print(
            f"{kind:8s}: x={x0:.2f}..{x1:.2f} mm, "
            f"y={y0:.2f}..{y1:.2f} mm"
        )
    return output


if __name__ == "__main__":
    build()
