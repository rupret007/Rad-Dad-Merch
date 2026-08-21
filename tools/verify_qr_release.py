#!/usr/bin/env python3
"""Verify the committed Rad Dad v8 QR release without modifying it."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

import v7_release_packaging as packaging  # noqa: E402


URL = "https://raddadband.com/tap/"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify(root: Path) -> None:
    required = (
        "README.md",
        "MANIFEST.json",
        "SHA256SUMS.txt",
        "qa/QR_SPEC.json",
        "qa/MODEL_REUSE_PROVENANCE.json",
        "qa/PHYSICAL_QC_CHECKLIST.md",
        "guides/QR_STICKER_SETUP.md",
        "guides/STICKER_SOURCING.md",
        "guides/Rad_Dad_QR_STICKER_PLACEMENT_GUIDE.svg",
        "guides/qr_stickers/Rad_Dad_1IN_QR_STICKER_VENDOR_MASTER.svg",
        "guides/qr_stickers/Rad_Dad_1IN_QR_STICKER_VENDOR_MASTER.png",
        "guides/qr_stickers/Rad_Dad_1IN_QR_STICKER_VENDOR_MASTER.pdf",
        "guides/qr_stickers/Rad_Dad_QR_STICKERS_AVERY_6450_OL1025_63UP_US_LETTER.svg",
        "guides/qr_stickers/Rad_Dad_QR_STICKERS_AVERY_6450_OL1025_63UP_US_LETTER.png",
        "guides/qr_stickers/Rad_Dad_QR_STICKERS_AVERY_6450_OL1025_63UP_US_LETTER.pdf",
        "guides/qr_stickers/Rad_Dad_QR_STICKER_PRINT_CALIBRATION.pdf",
        "Rad_Dad_Retro_Riot_v8_QR_Edition_Print_Pack.zip",
        "Rad_Dad_Retro_Riot_v8_QR_Edition_Print_Pack.zip.sha256",
    )
    for relative in required:
        require((root / relative).is_file(), f"Missing required v8 file: {relative}")

    spec = json.loads((root / "qa/QR_SPEC.json").read_text(encoding="utf-8"))
    require(spec["destination_url"] == URL, "QR destination URL changed")
    require(spec["qr_matrix_modules"] == 29, "QR matrix must be 29 x 29")
    require(spec["quiet_zone_modules"] == 4, "QR quiet zone must be four modules")
    require(spec["module_pitch_mm"] >= 0.44, "QR module pitch is too small")
    require(spec["finished_label_diameter_mm"] <= spec["minimum_model_landing_mm"], "Sticker exceeds model landing")
    matrix = packaging.qr_matrix(URL)
    require(len(matrix) == 29 and all(len(row) == 29 for row in matrix), "Bundled QR matrix is malformed")

    individual = root / "guides/qr_stickers/Rad_Dad_1IN_QR_STICKER_VENDOR_MASTER.png"
    sheet = root / "guides/qr_stickers/Rad_Dad_QR_STICKERS_AVERY_6450_OL1025_63UP_US_LETTER.png"
    with Image.open(individual) as image:
        require(image.size == (600, 600), f"Individual PNG must be 600 x 600, got {image.size}")
    with Image.open(sheet) as image:
        require(image.size == (5100, 6600), f"63-up sheet must be 5100 x 6600, got {image.size}")

    provenance = json.loads((root / "qa/MODEL_REUSE_PROVENANCE.json").read_text(encoding="utf-8"))
    require(provenance["files"], "Model reuse provenance is empty")
    for relative, record in provenance["files"].items():
        copied = root / relative
        source = REPO_ROOT / record["source"]
        require(copied.is_file() and source.is_file(), f"Missing source or copied model: {relative}")
        require(sha256(copied) == sha256(source) == record["source_sha256"], f"Model changed during QR conversion: {relative}")

    manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    for record in manifest["files"]:
        path = root / record["path"]
        require(path.is_file(), f"Manifest file is missing: {record['path']}")
        require(path.stat().st_size == record["bytes"], f"Manifest size mismatch: {record['path']}")
        require(sha256(path) == record["sha256"], f"Manifest hash mismatch: {record['path']}")

    archive = root / "Rad_Dad_Retro_Riot_v8_QR_Edition_Print_Pack.zip"
    sidecar = archive.with_name(archive.name + ".sha256")
    expected = sidecar.read_text(encoding="ascii").split()[0]
    require(sha256(archive) == expected, "Release ZIP checksum mismatch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=REPO_ROOT / "release" / "v8")
    args = parser.parse_args()
    verify(args.release.resolve())
    print("Rad Dad v8 QR release integrity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
