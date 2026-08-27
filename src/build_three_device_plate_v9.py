#!/usr/bin/env python3
"""Build the current cassette, floppy, and VHS as one balanced A1 Mini plate."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "release/v9/3mf/"
    "Rad_Dad_Retro_Riot_v9_ALL_FOUR_A1_MINI_0.4_PROJECT.3mf"
)
OUTPUT = (
    ROOT
    / "release/v9/3mf/"
    "Rad_Dad_Retro_Riot_v9_CURRENT_THREE_CASSETTE_FLOPPY_VHS_"
    "A1_MINI_0.4_PROJECT.3mf"
)

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PRODUCTION_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
ET.register_namespace("", CORE_NS)
ET.register_namespace("p", PRODUCTION_NS)
Q = lambda tag: f"{{{CORE_NS}}}{tag}"
P = lambda tag: f"{{{PRODUCTION_NS}}}{tag}"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

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


IDENTITY_TRANSFORM = (
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
)


def parse_transform(value: str | None) -> list[float]:
    values = (
        list(IDENTITY_TRANSFORM)
        if not value
        else [float(part) for part in value.split()]
    )
    if len(values) != 12:
        raise RuntimeError(f"Invalid 3MF transform: {value!r}")
    return values


def format_transform(values: list[float]) -> str:
    return " ".join(fmt(value) for value in values)


def apply_transform(
    point: tuple[float, float, float], values: list[float]
) -> tuple[float, float, float]:
    """Apply a 3MF affine transform (3x3 matrix followed by XYZ translation)."""
    x, y, z = point
    return (
        x * values[0] + y * values[3] + z * values[6] + values[9],
        x * values[1] + y * values[4] + z * values[7] + values[10],
        x * values[2] + y * values[5] + z * values[8] + values[11],
    )


def object_bounds(
    payload: bytes,
    component_transform: list[float],
    build_transform: list[float],
) -> tuple[float, float, float, float]:
    root = ET.fromstring(payload)
    vertices = root.findall(f".//{Q('vertex')}")
    if not vertices:
        raise RuntimeError("Referenced Bambu object has no mesh vertices")
    points = []
    for vertex in vertices:
        point = tuple(float(vertex.attrib[axis]) for axis in ("x", "y", "z"))
        points.append(
            apply_transform(
                apply_transform(point, component_transform), build_transform
            )
        )
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), max(xs), min(ys), max(ys)


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def zip_info(name: str) -> ZipInfo:
    info = ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o644 << 16
    return info


def make_thumbnail(bounds: dict[str, tuple[float, ...]], size: int = 512) -> bytes:
    """Create a simple, accurate top-down plate thumbnail without dependencies."""
    width = height = size
    pixels = bytearray((13, 18, 24, 255) * (width * height))

    def scaled(value: int) -> int:
        return max(1, round(value * size / 512))

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

    margin = scaled(36)
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
    border_width = scaled(2)
    rect(
        margin - border_width,
        margin - border_width,
        width - margin + border_width,
        margin,
        border,
    )
    rect(
        margin - border_width,
        height - margin,
        width - margin + border_width,
        height - margin + border_width,
        border,
    )
    rect(margin - border_width, margin, margin, height - margin, border)
    rect(width - margin, margin, width - margin + border_width, height - margin, border)

    fill = (35, 169, 103, 255)
    edge = (125, 255, 187, 255)
    dark = (8, 65, 44, 255)
    for kind, (x0, x1, y0, y1) in bounds.items():
        left, right = px(x0), px(x1)
        top, bottom = py(y1), py(y0)
        rect(left, top, right, bottom, fill)
        edge_width = scaled(2)
        rect(left, top, right, top + edge_width, edge)
        rect(left, bottom - edge_width, right, bottom, edge)
        rect(left, top, left + edge_width, bottom, edge)
        rect(right - edge_width, top, right, bottom, edge)
        if kind in {"cassette", "vhs"}:
            cy = (top + bottom) // 2
            ring(left + (right - left) // 3, cy, scaled(11), dark)
            ring(left + 2 * (right - left) // 3, cy, scaled(11), dark)
        else:
            rect(
                left + scaled(8),
                top + scaled(8),
                right - scaled(8),
                top + scaled(18),
                dark,
            )
            rect(
                left + scaled(12),
                bottom - scaled(24),
                right - scaled(12),
                bottom - scaled(9),
                dark,
            )

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


def write_support_ready_project(source: Path, target: Path) -> Path:
    """Copy a real Bambu project and apply the approved organic-support profile."""

    if not source.is_file():
        raise FileNotFoundError(source)
    with ZipFile(source) as source_zip:
        files = {name: source_zip.read(name) for name in source_zip.namelist()}
    required_members = {
        "3D/3dmodel.model",
        "Metadata/model_settings.config",
        "Metadata/project_settings.config",
    }
    missing = sorted(required_members - set(files))
    if missing:
        raise RuntimeError(
            "All-four source is not a configured Bambu project; missing: "
            + ", ".join(missing)
        )

    settings_name = "Metadata/project_settings.config"
    settings = json.loads(files[settings_name].decode("utf-8"))
    settings.update(
        {
            "default_print_profile": "Rad Dad v7 0.16 mm A1 Mini - Organic Support",
            "enable_support": "1",
            "print_settings_id": "Rad Dad v7 0.16 mm A1 Mini - Organic Support",
            "support_on_build_plate_only": "1",
            "support_remove_small_overhang": "1",
            "support_critical_regions_only": "0",
            "support_threshold_angle": "30",
            "support_top_z_distance": "0.2",
            "support_bottom_z_distance": "0.2",
            "support_type": "tree(auto)",
            "support_style": "default",
            "raft_layers": "0",
        }
    )
    files[settings_name] = (
        json.dumps(settings, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        with ZipFile(
            temporary, "w", compression=ZIP_DEFLATED, compresslevel=9
        ) as target_zip:
            for name, payload in sorted(files.items()):
                target_zip.writestr(zip_info(name), payload)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def build(source: Path = SOURCE, output: Path = OUTPUT) -> Path:
    """Build and return the balanced current-media Bambu project."""

    if not source.exists():
        raise FileNotFoundError(source)

    with ZipFile(source, "r") as source_zip:
        files = {name: source_zip.read(name) for name in source_zip.namelist()}

    required_members = {
        "3D/3dmodel.model",
        "3D/_rels/3dmodel.model.rels",
        "Metadata/project_settings.config",
        "Metadata/model_settings.config",
        "Metadata/cut_information.xml",
        "Metadata/slice_info.config",
        "Metadata/plate_1.png",
        "Metadata/plate_1_small.png",
    }
    missing_members = sorted(required_members - set(files))
    if missing_members:
        raise RuntimeError(
            "Source is not a configured Bambu project; missing: "
            + ", ".join(missing_members)
        )

    root = ET.fromstring(files["3D/3dmodel.model"])
    resources = root.find(Q("resources"))
    build_node = root.find(Q("build"))
    if resources is None or build_node is None:
        raise RuntimeError("Source 3MF is missing resources or build data")

    model_settings = ET.fromstring(files["Metadata/model_settings.config"])
    kind_by_id: dict[str, str] = {}
    for config_object in model_settings.findall("object"):
        name = next(
            (
                metadata.attrib.get("value", "")
                for metadata in config_object.findall("metadata")
                if metadata.attrib.get("key") == "name"
            ),
            "",
        )
        kind = model_kind(name)
        if kind is None:
            continue
        if kind in kind_by_id.values():
            raise RuntimeError(f"Duplicate {kind} object in Bambu metadata")
        kind_by_id[config_object.attrib["id"]] = kind

    if set(kind_by_id.values()) != set(TARGET_CENTERS_MM):
        missing = set(TARGET_CENTERS_MM) - set(kind_by_id.values())
        raise RuntimeError(f"Missing current models: {sorted(missing)}")

    build_items = {
        item.attrib["objectid"]: item for item in build_node.findall(Q("item"))
    }
    keep_ids = set(kind_by_id)
    removed_paths: set[str] = set()
    retained_cut_ordinals: list[int] = []
    arranged_bounds: dict[str, tuple[float, ...]] = {}
    resource_objects = list(resources.findall(Q("object")))
    for ordinal, obj in enumerate(resource_objects, start=1):
        object_id = obj.attrib["id"]
        kind = kind_by_id.get(object_id)
        if kind is None:
            for component in obj.findall(f".//{Q('component')}"):
                path = component.attrib.get(P("path"), "").lstrip("/")
                if path:
                    removed_paths.add(path)
            resources.remove(obj)
            continue
        retained_cut_ordinals.append(ordinal)

        components = obj.findall(f".//{Q('component')}")
        if len(components) != 1:
            raise RuntimeError(
                f"Expected one component for {kind}, found {len(components)}"
            )
        component = components[0]
        model_path = component.attrib.get(P("path"), "").lstrip("/")
        if model_path not in files:
            raise RuntimeError(f"Missing referenced object model for {kind}: {model_path}")
        item = build_items.get(object_id)
        if item is None:
            raise RuntimeError(f"Missing build item for {kind}")

        component_transform = parse_transform(component.attrib.get("transform"))
        # Normalize the auto-arranger's rotation so clean builds always place
        # each device in its native landscape orientation.
        build_transform = list(IDENTITY_TRANSFORM)
        bounds = object_bounds(files[model_path], component_transform, build_transform)
        center_x = (bounds[0] + bounds[1]) / 2.0
        center_y = (bounds[2] + bounds[3]) / 2.0
        target_x, target_y = TARGET_CENTERS_MM[kind]
        dx = target_x - center_x
        dy = target_y - center_y
        build_transform[9] += dx
        build_transform[10] += dy
        item.set("transform", format_transform(build_transform))
        arranged_bounds[kind] = (
            bounds[0] + dx,
            bounds[1] + dx,
            bounds[2] + dy,
            bounds[3] + dy,
        )

    for item in list(build_node.findall(Q("item"))):
        if item.attrib.get("objectid") not in keep_ids:
            build_node.remove(item)

    for config_object in list(model_settings.findall("object")):
        if config_object.attrib.get("id") not in keep_ids:
            model_settings.remove(config_object)
    plate = model_settings.find("plate")
    if plate is None:
        raise RuntimeError("Bambu project is missing plate metadata")
    for metadata in list(plate.findall("metadata")):
        if metadata.attrib.get("key") == "pick_file":
            plate.remove(metadata)
    for instance in list(plate.findall("model_instance")):
        object_id = next(
            (
                metadata.attrib.get("value")
                for metadata in instance.findall("metadata")
                if metadata.attrib.get("key") == "object_id"
            ),
            None,
        )
        if object_id not in keep_ids:
            plate.remove(instance)

    for path in removed_paths:
        files.pop(path, None)
    # Bambu's pick mask encodes per-object identify IDs in its pixels. Once the
    # plate is rearranged, a stale mask is worse than no mask; Studio can
    # regenerate it when the project is saved again.
    files.pop("Metadata/pick_1.png", None)

    cut_information = ET.fromstring(files["Metadata/cut_information.xml"])
    cut_objects = list(cut_information.findall("object"))
    if len(cut_objects) != len(resource_objects):
        raise RuntimeError("Bambu cut metadata does not match top-level objects")
    retained_cut_objects = [cut_objects[index - 1] for index in retained_cut_ordinals]
    for cut_object in cut_objects:
        cut_information.remove(cut_object)
    for cut_object in retained_cut_objects:
        cut_information.append(cut_object)
    for index, cut_object in enumerate(cut_information.findall("object"), start=1):
        # These IDs follow top-level model object order, not object_N filenames.
        cut_object.set("id", str(index))

    relationships_name = "3D/_rels/3dmodel.model.rels"
    relationships = ET.fromstring(files[relationships_name])
    for relationship in list(relationships):
        if relationship.attrib.get("Target", "").lstrip("/") in removed_paths:
            relationships.remove(relationship)

    files["3D/3dmodel.model"] = ET.tostring(
        root, encoding="utf-8", xml_declaration=True
    )
    files["Metadata/model_settings.config"] = ET.tostring(
        model_settings, encoding="utf-8", xml_declaration=True
    )
    files["Metadata/cut_information.xml"] = ET.tostring(
        cut_information, encoding="utf-8", xml_declaration=True
    )
    # Bambu's relationship parser expects unprefixed Relationship element
    # names. Use the OPC namespace as the default only for this payload, then
    # restore the Core namespace so repeat builds remain byte-identical.
    ET.register_namespace("", RELATIONSHIPS_NS)
    try:
        files[relationships_name] = ET.tostring(
            relationships,
            encoding="utf-8",
            xml_declaration=True,
        )
    finally:
        ET.register_namespace("", CORE_NS)

    preview = make_thumbnail(arranged_bounds)
    for preview_name in (
        "Metadata/plate_1.png",
        "Metadata/plate_no_light_1.png",
        "Metadata/top_1.png",
    ):
        if preview_name in files:
            files[preview_name] = preview
    files["Metadata/plate_1_small.png"] = make_thumbnail(arranged_bounds, size=128)

    settings_name = "Metadata/project_settings.config"
    settings = json.loads(files[settings_name].decode("utf-8"))
    settings["enable_support"] = "0"
    settings["support_on_build_plate_only"] = "0"
    settings["raft_layers"] = "0"
    settings["print_sequence"] = "by layer"
    settings["default_print_profile"] = "Rad Dad v7 0.16 mm A1 Mini - No Support"
    settings["print_settings_id"] = "Rad Dad v7 0.16 mm A1 Mini - No Support"
    files[settings_name] = json.dumps(
        settings, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as output_zip:
        for name, payload in sorted(files.items()):
            output_zip.writestr(zip_info(name), payload)

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
