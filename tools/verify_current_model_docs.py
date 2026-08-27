#!/usr/bin/env python3
"""Fail if current merch/QR docs still name superseded production models."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
METADATA = (
    REPO_ROOT
    / "release"
    / "v9"
    / "qa"
    / "geometry_evidence"
    / "PRODUCT_METADATA.json"
)
QR_STICKERS = REPO_ROOT / "docs" / "QR_STICKERS.md"
DESIGN = REPO_ROOT / "docs" / "DESIGN.md"
PRINTING = REPO_ROOT / "docs" / "PRINTING.md"
TRAILER_PROJECT_DIR = REPO_ROOT / "release" / "v9" / "3mf"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def revision_from_stem(stem: str) -> str:
    match = re.search(r"_v(\d+)", stem)
    require(match is not None, f"No revision in artifact stem: {stem}")
    return f"v{match.group(1)}"


def table_revision(text: str, product: str) -> str | None:
    match = re.search(
        rf"^\| {re.escape(product)} \| (v\d+) \|",
        text,
        flags=re.MULTILINE,
    )
    return match.group(1) if match else None


def _self_check() -> None:
    stale = (
        "| 3.5-inch floppy | v21 | 26.0 mm |\n"
        "| Trailer Swift | v9 | 27.0 mm |\n"
    )
    require(table_revision(stale, "3.5-inch floppy") == "v21", "self-check missed stale floppy")
    require(table_revision(stale, "Trailer Swift") == "v9", "self-check missed stale Trailer Swift")
    require(table_revision("| Mini VHS | v5 | 26.0 mm |", "Mini VHS") == "v5", "self-check missed VHS")


def main() -> int:
    _self_check()
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    products = metadata["products"]
    floppy_rev = revision_from_stem(products["floppy"]["artifact_stem"])
    trailer_rev = revision_from_stem(products["trailer_swift"]["artifact_stem"])
    cassette_rev = revision_from_stem(products["cassette"]["artifact_stem"])
    vhs_rev = revision_from_stem(products["vhs"]["artifact_stem"])
    trailer_project = (
        f"{products['trailer_swift']['artifact_stem']}_A1_MINI_0.4_PROJECT.3mf"
    )

    qr = QR_STICKERS.read_text(encoding="utf-8")
    design = DESIGN.read_text(encoding="utf-8")
    printing = PRINTING.read_text(encoding="utf-8")

    require(
        table_revision(qr, "3.5-inch floppy") == floppy_rev,
        f"QR sticker fit table still names floppy {table_revision(qr, '3.5-inch floppy')}, not {floppy_rev}",
    )
    require(
        table_revision(qr, "Trailer Swift") == trailer_rev,
        f"QR sticker fit table still names Trailer Swift {table_revision(qr, 'Trailer Swift')}, not {trailer_rev}",
    )
    require(
        table_revision(qr, "Compact cassette") == cassette_rev,
        "QR sticker fit table cassette revision drifted",
    )
    require(
        table_revision(qr, "Mini VHS") == vhs_rev,
        "QR sticker fit table VHS revision drifted",
    )

    require(
        table_revision(design, "Compact cassette") == cassette_rev,
        "Design current-model table cassette revision drifted",
    )
    require(
        table_revision(design, "3.5-inch floppy") == floppy_rev,
        f"Design current-model table still names floppy {table_revision(design, '3.5-inch floppy')}, not {floppy_rev}",
    )
    require(
        table_revision(design, "Mini VHS") == vhs_rev,
        "Design current-model table VHS revision drifted",
    )
    require(
        table_revision(design, "Trailer Swift") == trailer_rev,
        f"Design current-model table still names Trailer Swift {table_revision(design, 'Trailer Swift')}, not {trailer_rev}",
    )
    cassette_envelope = products["cassette"]["exact_envelope_mm"]
    cassette_exact = (
        f"{cassette_envelope[0]:.3f} x {cassette_envelope[1]:.3f} x "
        f"{cassette_envelope[2]:.3f} mm"
    )
    require(
        f"| Compact cassette | {cassette_rev} | {cassette_exact} |" in design,
        f"Design current-model table does not use exact cassette envelope {cassette_exact}",
    )

    require(
        f"`{trailer_project}`" in printing,
        f"Printing guide does not name current Trailer Swift project {trailer_project}",
    )
    require(
        "Trailer_Swift_v9_Signature" not in printing,
        "Printing guide still names the retired Trailer Swift v9 project file",
    )
    require(
        (TRAILER_PROJECT_DIR / trailer_project).is_file(),
        f"Current Trailer Swift project is missing: {trailer_project}",
    )
    require(
        f"Confirm {floppy_rev}" in printing,
        f"Printing troubleshooting does not confirm current floppy {floppy_rev}",
    )

    print(
        "Current merch/QR model docs match "
        f"cassette {cassette_rev}, floppy {floppy_rev}, "
        f"VHS {vhs_rev}, Trailer Swift {trailer_rev}."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
