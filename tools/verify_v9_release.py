#!/usr/bin/env python3
"""Verify the current Rad Dad v9 release without third-party dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Iterable
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = REPO_ROOT / "release" / "v9"
DESTINATION_URL = "https://raddadband.com/qr/"
CURRENT_THREE = (
    "3mf/Rad_Dad_Retro_Riot_v9_CURRENT_THREE_CASSETTE_FLOPPY_VHS_"
    "A1_MINI_0.4_PROJECT.3mf"
)
FLOPPY_MODEL = "3mf/Rad_Dad_Floppy_v22_MODEL_ONLY.3mf"


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
        require("3D/3dmodel.model" in project.namelist(), f"3MF model missing: {path.name}")


def verify_geometry(root: Path) -> None:
    status = read_json(root / "qa/GEOMETRY_BUILD_STATUS.json")
    require(status.get("bambu_required_satisfied") is True, "Configured Bambu projects were not generated")
    qa = read_json(root / "qa/geometry_evidence/MODEL_QA.json")
    require(qa.get("mesh_qa_pass") is True, "Mesh QA did not pass")
    models = {model["name"]: model for model in qa.get("models", [])}
    floppy = models.get("Rad_Dad_Floppy_v22")
    require(floppy is not None, "V22 floppy is absent from model QA")
    require(floppy.get("digital_qa_pass") is True, "V22 floppy digital QA failed")
    require(all(floppy.get("checks", {}).values()), "V22 floppy has a failed geometry check")
    expected = (44.36, 36.916, 4.13)
    actual = tuple(float(value) for value in floppy["dimensions_mm"])
    require(all(abs(a - e) <= 0.001 for a, e in zip(actual, expected)), f"V22 floppy envelope changed: {actual}")


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
    red_artwork = root / "guides/qr_stickers/Rad_Dad_QR_RED_1IN_VENDOR_MASTER_600DPI.png"
    red_sheet = root / "guides/qr_stickers/Rad_Dad_QR_RED_AVERY_6450_OL1025_63UP_US_LETTER_600DPI.png"
    require(png_size(artwork) == (600, 600), "Vendor QR PNG is not 600 x 600")
    require(png_size(sheet) == (5100, 6600), "63-up QR sheet is not US Letter at 600 DPI")
    require(
        qr.get("color_cartridge_fallback") == ["#FF0000", "#FFFFFF"],
        "Authenticity spec no longer records the official red-on-white fallback",
    )
    require(png_size(red_artwork) == (600, 600), "Red vendor QR PNG is not 600 x 600")
    require(png_size(red_sheet) == (5100, 6600), "Red 63-up QR sheet is not US Letter at 600 DPI")


def verify(root: Path) -> None:
    required = (
        "README.md",
        "MANIFEST.json",
        "SHA256SUMS.txt",
        "qa/AUTHENTICITY_SPEC.json",
        "qa/GEOMETRY_BUILD_STATUS.json",
        "qa/geometry_evidence/MODEL_QA.json",
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
    for relative in (CURRENT_THREE, FLOPPY_MODEL, "3mf/Rad_Dad_Floppy_v22_A1_MINI_0.4_PROJECT.3mf"):
        verify_3mf(root / relative)


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
