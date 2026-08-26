#!/usr/bin/env python3
"""Verify the current Rad Dad v9 release without third-party dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from typing import Iterable
import xml.etree.ElementTree as ET
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from bambu_project_v7 import inspect_bambu_project_3mf  # noqa: E402
from build_three_device_plate_v9 import (  # noqa: E402
    build as build_three_device_plate,
    write_support_ready_project,
)


DEFAULT_RELEASE = REPO_ROOT / "release" / "v9"
DESTINATION_URL = "https://raddadband.com/qr/"
ALL_FOUR_PROJECT = "3mf/Rad_Dad_Retro_Riot_v9_ALL_FOUR_A1_MINI_0.4_PROJECT.3mf"
TREE_SUPPORT_PROJECT = (
    "3mf/Rad_Dad_Retro_Riot_v9_ALL_FOUR_A1_MINI_0.4_TREE_SUPPORT_PROJECT.3mf"
)
CURRENT_THREE = (
    "3mf/Rad_Dad_Retro_Riot_v9_CURRENT_THREE_CASSETTE_FLOPPY_VHS_"
    "A1_MINI_0.4_PROJECT.3mf"
)
FLOPPY_MODEL = "3mf/Rad_Dad_Floppy_v22_MODEL_ONLY.3mf"
CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PRODUCTION_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
EXPECTED_CURRENT_THREE = {
    "Rad_Dad_Cassette_v38_BINARY.stl",
    "Rad_Dad_Floppy_v22_BINARY.stl",
    "Rad_Dad_Mini_VHS_v5_BINARY.stl",
}
EXPECTED_ALL_FOUR = EXPECTED_CURRENT_THREE | {
    "Trailer_Swift_v16_Strat_Style_Punk_QR_BINARY.stl"
}
TARGET_CENTERS_MM = {
    "Rad_Dad_Cassette_v38_BINARY.stl": (48.1, 55.0),
    "Rad_Dad_Floppy_v22_BINARY.stl": (90.0, 120.0),
    "Rad_Dad_Mini_VHS_v5_BINARY.stl": (128.1, 55.0),
}
EXPECTED_BOUNDS_MM = {
    "Rad_Dad_Cassette_v38_BINARY.stl": (19.018, 77.182, 39.870, 70.130),
    "Rad_Dad_Floppy_v22_BINARY.stl": (67.820, 112.180, 101.542, 138.458),
    "Rad_Dad_Mini_VHS_v5_BINARY.stl": (95.200, 161.000, 39.050, 70.950),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    require(header[:8] == b"\x89PNG\r\n\x1a\n", f"Invalid PNG: {path.name}")
    return struct.unpack(">II", header[16:24])


def verify_required(root: Path, paths: Iterable[str]) -> None:
    for relative in paths:
        require((root / relative).is_file(), f"Missing required file: {relative}")


def verify_manifest(root: Path) -> None:
    manifest = read_json(root / "MANIFEST.json")
    require(manifest.get("release", "").startswith("Rad Dad Retro Riot v9"), "Wrong release identity")
    require(manifest.get("metadata", {}).get("destination_url") == DESTINATION_URL, "Manifest URL mismatch")
    records = manifest.get("files", [])
    require(records, "Manifest has no files")
    for record in records:
        path = root / record["path"]
        require(path.is_file(), f"Manifest file missing: {record['path']}")
        require(path.stat().st_size == record["bytes"], f"Manifest size mismatch: {record['path']}")
        require(sha256(path) == record["sha256"], f"Manifest hash mismatch: {record['path']}")


def verify_sha256s(root: Path) -> None:
    rows = (root / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines()
    require(rows, "SHA256SUMS.txt is empty")
    for row in rows:
        expected, relative = row.split("  ", 1)
        path = root / relative
        require(path.is_file(), f"Checksum file missing: {relative}")
        require(sha256(path) == expected, f"Checksum mismatch: {relative}")


def verify_archive(root: Path) -> None:
    archive = root / "Rad_Dad_Retro_Riot_v9_Authenticity_QR_Print_Pack.zip"
    sidecar = archive.with_name(archive.name + ".sha256")
    expected = sidecar.read_text(encoding="ascii").split()[0]
    require(sha256(archive) == expected, "Print-pack sidecar checksum mismatch")
    with ZipFile(archive) as bundle:
        require(bundle.testzip() is None, "Print-pack ZIP contains a corrupt member")
        names = bundle.namelist()
        for relative in (CURRENT_THREE, FLOPPY_MODEL, "README.md", "qa/AUTHENTICITY_SPEC.json"):
            require(any(name.endswith("/" + relative) for name in names), f"Print pack omits {relative}")


def verify_3mf(path: Path) -> None:
    with ZipFile(path) as project:
        require(project.testzip() is None, f"Corrupt 3MF: {path.name}")
        names = project.namelist()
        require(len(names) == len(set(names)), f"Duplicate 3MF members: {path.name}")
        require("3D/3dmodel.model" in names, f"3MF model missing: {path.name}")


def verify_bambu_profile(
    path: Path, expected_names: set[str], support_mode: str
) -> None:
    report = inspect_bambu_project_3mf(path)
    errors = "; ".join(report.get("errors", [])) or "unknown project error"
    require(report.get("is_bambu_project") is True, f"{path.name}: {errors}")
    require(
        report.get("matches_rad_dad_v7_base_profile") is True,
        f"{path.name}: profile mismatch {report.get('profile_mismatches', {})}",
    )
    require(
        report.get("support_mode") == support_mode,
        f"{path.name}: wrong support mode {report.get('support_mode')!r}",
    )
    names = report.get("object_names", [])
    require(
        len(names) == len(expected_names) and set(names) == expected_names,
        f"{path.name}: wrong object set",
    )
    require(report.get("plate_count") == 1, f"{path.name}: expected one plate")
    require(
        report.get("model_instance_count") == len(expected_names),
        f"{path.name}: wrong plate-instance count",
    )
    require(
        len(report.get("build_items", [])) == len(expected_names),
        f"{path.name}: wrong build-item count",
    )


IDENTITY_TRANSFORM = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)


def parse_transform(value: str | None, label: str) -> tuple[float, ...]:
    values = IDENTITY_TRANSFORM if not value else tuple(float(part) for part in value.split())
    require(len(values) == 12, f"{label}: transform must have 12 values")
    return values


def apply_transform(
    point: tuple[float, float, float], values: tuple[float, ...]
) -> tuple[float, float, float]:
    x, y, z = point
    return (
        x * values[0] + y * values[3] + z * values[6] + values[9],
        x * values[1] + y * values[4] + z * values[7] + values[10],
        x * values[2] + y * values[5] + z * values[8] + values[11],
    )


def metadata_value(element: ET.Element, key: str) -> str:
    return next(
        (
            metadata.attrib.get("value", "")
            for metadata in element.findall("metadata")
            if metadata.attrib.get("key") == key
        ),
        "",
    )


def verify_current_three_bambu_project(path: Path) -> None:
    """Verify Bambu cross-links and the transformed three-object plate layout."""
    required_members = {
        "[Content_Types].xml",
        "_rels/.rels",
        "3D/3dmodel.model",
        "3D/_rels/3dmodel.model.rels",
        "Metadata/project_settings.config",
        "Metadata/model_settings.config",
        "Metadata/cut_information.xml",
        "Metadata/slice_info.config",
        "Metadata/filament_sequence.json",
        "Metadata/plate_1.png",
        "Metadata/plate_1_small.png",
    }
    with ZipFile(path) as project:
        member_list = project.namelist()
        require(len(member_list) == len(set(member_list)), "Current-three has duplicate members")
        names = set(member_list)
        missing = sorted(required_members - names)
        require(not missing, "Current-three Bambu project is incomplete: " + ", ".join(missing))

        settings = json.loads(project.read("Metadata/project_settings.config"))
        require(isinstance(settings, dict), "Current-three project settings are not an object")
        require(settings.get("printer_model") == "Bambu Lab A1 mini", "Wrong current-three printer")
        require(settings.get("printer_variant") == "0.4", "Wrong current-three nozzle")
        require(settings.get("layer_height") == "0.16", "Wrong current-three layer height")
        require(settings.get("enable_support") == "0", "Current-three media plate must not enable support")
        require(
            settings.get("support_on_build_plate_only") == "0",
            "Current-three build-plate-only support flag must be off",
        )
        require(settings.get("raft_layers") == "0", "Current-three media plate must not enable a raft")

        model_settings_payload = project.read("Metadata/model_settings.config")
        model_settings = ET.fromstring(model_settings_payload)
        object_names: dict[str, str] = {}
        for config_object in model_settings.findall("object"):
            object_id = config_object.attrib.get("id", "")
            name = metadata_value(config_object, "name")
            object_names[object_id] = name
        require(
            len(object_names) == 3
            and set(object_names.values()) == EXPECTED_CURRENT_THREE,
            "Wrong current-three object set",
        )

        plate = model_settings.find("plate")
        require(plate is not None, "Current-three Bambu project has no plate metadata")
        plate_instances = plate.findall("model_instance")
        plate_ids = [metadata_value(instance, "object_id") for instance in plate_instances]
        require(
            len(plate_ids) == 3 and set(plate_ids) == set(object_names),
            "Current-three plate instances do not match objects",
        )
        require(
            not any(
                metadata.attrib.get("key") == "pick_file"
                for metadata in plate.findall("metadata")
            )
            and "Metadata/pick_1.png" not in names,
            "Current-three contains a stale Bambu object-pick mask",
        )

        q = lambda tag: f"{{{CORE_NS}}}{tag}"
        p_path = f"{{{PRODUCTION_NS}}}path"
        model_payload = project.read("3D/3dmodel.model")
        model = ET.fromstring(model_payload)
        resources = model.find(q("resources"))
        build = model.find(q("build"))
        require(resources is not None and build is not None, "Current-three core model is incomplete")
        resource_objects = resources.findall(q("object"))
        build_items = build.findall(q("item"))
        resource_ids = {obj.attrib.get("id", "") for obj in resource_objects}
        build_ids = {item.attrib.get("objectid", "") for item in build_items}
        require(resource_ids == set(object_names), "Current-three resources do not match metadata")
        require(
            len(build_items) == 3 and build_ids == resource_ids,
            "Current-three build items do not match resources",
        )

        component_targets: set[str] = set()
        bounds_by_name: dict[str, tuple[float, float, float, float]] = {}
        build_by_id = {item.attrib.get("objectid", ""): item for item in build_items}
        config_by_id = {
            config_object.attrib.get("id", ""): config_object
            for config_object in model_settings.findall("object")
        }
        for obj in resource_objects:
            object_id = obj.attrib.get("id", "")
            components = obj.findall(f"./{q('components')}/{q('component')}")
            require(len(components) == 1, f"Object {object_id}: expected one component")
            component = components[0]
            target = component.attrib.get(p_path, "").lstrip("/")
            child_id = component.attrib.get("objectid", "")
            require(target in names, f"Object {object_id}: missing component {target}")
            component_targets.add(target)

            child_model = ET.fromstring(project.read(target))
            child_resources = child_model.find(q("resources"))
            require(child_resources is not None, f"Object {object_id}: child resources missing")
            child_objects = child_resources.findall(q("object"))
            require(
                len(child_objects) == 1 and child_objects[0].attrib.get("id") == child_id,
                f"Object {object_id}: component child ID is stale",
            )
            config_object = config_by_id[object_id]
            parts = config_object.findall("part")
            require(
                len(parts) == 1 and parts[0].attrib.get("id") == child_id,
                f"Object {object_id}: Bambu part ID is stale",
            )
            vertices = child_objects[0].findall(f".//{q('vertex')}")
            require(vertices, f"Object {object_id}: component has no vertices")
            component_transform = parse_transform(
                component.attrib.get("transform"), f"Object {object_id} component"
            )
            build_item = build_by_id[object_id]
            require(
                build_item.attrib.get("printable") == "1",
                f"Object {object_id}: build item is not printable",
            )
            build_transform = parse_transform(
                build_item.attrib.get("transform"), f"Object {object_id} build item"
            )
            points = [
                apply_transform(
                    apply_transform(
                        tuple(float(vertex.attrib[axis]) for axis in ("x", "y", "z")),
                        component_transform,
                    ),
                    build_transform,
                )
                for vertex in vertices
            ]
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            bounds = (min(xs), max(xs), min(ys), max(ys))
            name = object_names[object_id]
            bounds_by_name[name] = bounds
            expected_x, expected_y = TARGET_CENTERS_MM[name]
            actual_x = (bounds[0] + bounds[1]) / 2.0
            actual_y = (bounds[2] + bounds[3]) / 2.0
            require(
                abs(actual_x - expected_x) <= 0.02
                and abs(actual_y - expected_y) <= 0.02,
                f"{name}: wrong plate center {(actual_x, actual_y)}",
            )
            expected_bounds = EXPECTED_BOUNDS_MM[name]
            require(
                all(
                    abs(actual - expected) <= 0.03
                    for actual, expected in zip(bounds, expected_bounds)
                ),
                f"{name}: wrong plate orientation or bounds {bounds}",
            )
            require(
                bounds[0] >= 0
                and bounds[1] <= 180
                and bounds[2] >= 0
                and bounds[3] <= 180,
                f"{name}: outside the A1 Mini plate",
            )

        ordered_bounds = list(bounds_by_name.items())
        for index, (left_name, left) in enumerate(ordered_bounds):
            for right_name, right in ordered_bounds[index + 1 :]:
                separated = (
                    left[1] <= right[0]
                    or right[1] <= left[0]
                    or left[3] <= right[2]
                    or right[3] <= left[2]
                )
                require(separated, f"Plate objects overlap: {left_name}, {right_name}")

        object_members = {
            name for name in names if name.startswith("3D/Objects/") and name.endswith(".model")
        }
        require(component_targets == object_members, "Current-three object relationships are stale")

        relationships_payload = project.read("3D/_rels/3dmodel.model.rels")
        require(
            b"<Relationship " in relationships_payload
            and b":Relationship" not in relationships_payload,
            "Current-three relationships must use Bambu-compatible unprefixed tags",
        )
        relationships = ET.fromstring(relationships_payload)
        relationship_targets = {
            relationship.attrib.get("Target", "").lstrip("/") for relationship in relationships
        }
        require(relationship_targets == component_targets, "Current-three relationship file is stale")

        cut_information = ET.fromstring(project.read("Metadata/cut_information.xml"))
        cut_ids = [
            element.attrib.get("id", "")
            for element in cut_information.findall("object")
        ]
        require(cut_ids == ["1", "2", "3"], "Current-three cut metadata is stale")
        require(
            b"Trailer_Swift" not in model_settings_payload
            and b"Trailer_Swift" not in model_payload,
            "Trailer Swift remains in current-three metadata",
        )


def verify_derived_projects_rebuild(root: Path) -> None:
    """Require deterministic, up-to-date derived Bambu projects in one process."""

    source_snapshot = root / "source" / "build_three_device_plate_v9.py"
    require(
        source_snapshot.read_bytes()
        == (REPO_ROOT / "src" / "build_three_device_plate_v9.py").read_bytes(),
        "V9 three-device source snapshot is stale",
    )
    with tempfile.TemporaryDirectory(prefix="rad-dad-v9-derived-") as temporary:
        output = Path(temporary)
        current_a = build_three_device_plate(
            source=root / ALL_FOUR_PROJECT, output=output / "current-a.3mf"
        )
        current_b = build_three_device_plate(
            source=root / ALL_FOUR_PROJECT, output=output / "current-b.3mf"
        )
        require(
            sha256(current_a) == sha256(current_b),
            "Current-three project is not repeatable in one process",
        )
        require(
            sha256(current_a) == sha256(root / CURRENT_THREE),
            "Committed current-three project is stale",
        )

        support_a = write_support_ready_project(
            root / ALL_FOUR_PROJECT, output / "support-a.3mf"
        )
        support_b = write_support_ready_project(
            root / ALL_FOUR_PROJECT, output / "support-b.3mf"
        )
        require(
            sha256(support_a) == sha256(support_b),
            "Tree-support project is not repeatable in one process",
        )
        require(
            sha256(support_a) == sha256(root / TREE_SUPPORT_PROJECT),
            "Committed tree-support project is stale",
        )


def verify_geometry(root: Path) -> None:
    status = read_json(root / "qa/GEOMETRY_BUILD_STATUS.json")
    require(status.get("bambu_required_satisfied") is True, "Configured Bambu projects were not generated")
    qa = read_json(root / "qa/geometry_evidence/MODEL_QA.json")
    require(qa.get("mesh_qa_pass") is True, "Mesh QA did not pass")
    models = {model["name"]: model for model in qa.get("models", [])}
    floppy = models.get("Rad_Dad_Floppy_v22")
    require(floppy is not None, "V21 floppy is absent from model QA")
    require(floppy.get("digital_qa_pass") is True, "V21 floppy digital QA failed")
    require(all(floppy.get("checks", {}).values()), "V21 floppy has a failed geometry check")
    expected = (44.36, 36.916, 4.13)
    actual = tuple(float(value) for value in floppy["dimensions_mm"])
    require(all(abs(a - e) <= 0.001 for a, e in zip(actual, expected)), f"V21 floppy envelope changed: {actual}")


def verify_qr(root: Path) -> None:
    spec = read_json(root / "qa/AUTHENTICITY_SPEC.json")
    require(spec.get("destination_url") == DESTINATION_URL, "Authenticity-spec URL mismatch")
    qr = spec.get("qr", {})
    require(qr.get("error_correction") == "Q", "QR error correction must be Q")
    require(qr.get("quiet_zone_modules") == 4, "QR quiet zone must be four modules")
    require(qr.get("label_diameter_mm") == 25.4, "QR sticker diameter changed")
    module_pitch = float(qr.get("render_square_mm", 0.0)) / 37.0
    require(module_pitch >= 0.44, "QR module pitch is too small")
    artwork = root / "guides/qr_stickers/Rad_Dad_QR_1IN_VENDOR_MASTER_600DPI.png"
    sheet = root / "guides/qr_stickers/Rad_Dad_QR_AVERY_6450_OL1025_63UP_US_LETTER_600DPI.png"
    require(png_size(artwork) == (600, 600), "Vendor QR PNG is not 600 x 600")
    require(png_size(sheet) == (5100, 6600), "63-up QR sheet is not US Letter at 600 DPI")


def verify(root: Path) -> None:
    required = (
        "README.md",
        "MANIFEST.json",
        "SHA256SUMS.txt",
        "qa/AUTHENTICITY_SPEC.json",
        "qa/GEOMETRY_BUILD_STATUS.json",
        "qa/geometry_evidence/MODEL_QA.json",
        ALL_FOUR_PROJECT,
        TREE_SUPPORT_PROJECT,
        CURRENT_THREE,
        FLOPPY_MODEL,
        "3mf/Rad_Dad_Floppy_v22_A1_MINI_0.4_PROJECT.3mf",
        "stl/Rad_Dad_Floppy_v22_BINARY.stl",
        "source/media_micro_v7.py",
        "source/media_micro_v9.py",
        "source/build_three_device_plate_v9.py",
        "guides/qr_stickers/Rad_Dad_QR_1IN_VENDOR_MASTER_600DPI.png",
        "Rad_Dad_Retro_Riot_v9_Authenticity_QR_Print_Pack.zip",
        "Rad_Dad_Retro_Riot_v9_Authenticity_QR_Print_Pack.zip.sha256",
    )
    verify_required(root, required)
    verify_manifest(root)
    verify_sha256s(root)
    verify_archive(root)
    verify_geometry(root)
    verify_qr(root)
    for relative in (
        ALL_FOUR_PROJECT,
        TREE_SUPPORT_PROJECT,
        CURRENT_THREE,
        FLOPPY_MODEL,
        "3mf/Rad_Dad_Floppy_v22_A1_MINI_0.4_PROJECT.3mf",
    ):
        verify_3mf(root / relative)
    verify_bambu_profile(
        root / ALL_FOUR_PROJECT, EXPECTED_ALL_FOUR, "organic_build_plate_only"
    )
    verify_bambu_profile(
        root / TREE_SUPPORT_PROJECT,
        EXPECTED_ALL_FOUR,
        "organic_build_plate_only",
    )
    verify_bambu_profile(root / CURRENT_THREE, EXPECTED_CURRENT_THREE, "off")
    verify_current_three_bambu_project(root / CURRENT_THREE)
    verify_derived_projects_rebuild(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    args = parser.parse_args()
    release = args.release.expanduser().resolve()
    verify(release)
    print(f"V9 release verification passed: {release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
