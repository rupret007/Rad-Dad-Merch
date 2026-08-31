#!/usr/bin/env python3
"""Fail if current merch/QR docs drift on models, color, or label durability."""

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
AUTHENTICITY = REPO_ROOT / "release" / "v9" / "qa" / "AUTHENTICITY_SPEC.json"
QR_STICKERS = REPO_ROOT / "docs" / "QR_STICKERS.md"
DESIGN = REPO_ROOT / "docs" / "DESIGN.md"
PRINTING = REPO_ROOT / "docs" / "PRINTING.md"
README = REPO_ROOT / "README.md"
NFC = REPO_ROOT / "docs" / "NFC.md"
VALIDATION = REPO_ROOT / "docs" / "VALIDATION.md"
TRAILER_PROJECT_DIR = REPO_ROOT / "release" / "v9" / "3mf"
QR_ART_DIR = REPO_ROOT / "release" / "v9" / "guides" / "qr_stickers"
RED_FALLBACK_FILES = (
    "Rad_Dad_QR_RED_1IN_VENDOR_MASTER.svg",
    "Rad_Dad_QR_RED_AVERY_6450_OL1025_63UP_US_LETTER.pdf",
    "Rad_Dad_QR_RED_FEDEX_OFFICE_FULL_SHEET_48UP_US_LETTER.pdf",
    "Rad_Dad_QR_RED_PRINT_CALIBRATION_US_LETTER.pdf",
)


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


def exact_envelope(values: list[float]) -> str:
    return f"{values[0]:.3f} x {values[1]:.3f} x {values[2]:.3f} mm"


def documents_red_fallback(text: str) -> bool:
    lowered = text.lower()
    return (
        "Rad_Dad_QR_RED_" in text
        and "fallback" in lowered
        and ("#ff0000" in lowered or "process red" in lowered or "process-red" in lowered)
    )


def mentions_red_fallback(text: str) -> bool:
    lowered = text.lower()
    return "fallback" in lowered and "red" in lowered


def documents_removable_proof_boundary(text: str) -> bool:
    normalized = " ".join(text.lower().replace("-", " ").split())
    sentences = re.split(r"(?<=[.!?])\s+", normalized)

    def is_positive(pattern: str, sentence: str) -> bool:
        return (
            "?" not in sentence
            and re.search(pattern, sentence) is not None
            and re.search(
                r"\b(?:cannot|could|may|might|no|not|never|optional(?:ly)?|"
                r"perhaps|possibly|should)\b|n['’]t\b",
                sentence,
            )
            is None
        )

    proof_only = any(
        is_positive(
            r"\bavery 6450 is removable adhesive proof only\b",
            sentence,
        )
        for sentence in sentences
    )
    permanent_finished_stock = any(
        is_positive(
            r"\b(?:finished|giveaway|keychain|carry|installed|carried|production)"
            r"[^.?!]{0,120}\brequires? permanent adhesive\b",
            sentence,
        )
        for sentence in sentences
    )
    return proof_only and permanent_finished_stock


def _self_check() -> None:
    stale = (
        "| 3.5-inch floppy | v21 | 26.0 mm |\n"
        "| Trailer Swift | v9 | 27.0 mm |\n"
    )
    require(table_revision(stale, "3.5-inch floppy") == "v21", "self-check missed stale floppy")
    require(table_revision(stale, "Trailer Swift") == "v9", "self-check missed stale Trailer Swift")
    require(table_revision("| Mini VHS | v5 | 26.0 mm |", "Mini VHS") == "v5", "self-check missed VHS")
    require(table_revision("| Rad Dad 3.5-Inch Floppy | v22 | 44.360 x 36.916 x 4.130 mm |", "Rad Dad 3.5-Inch Floppy") == "v22", "self-check missed README floppy")
    exclusive_bw = (
        "The interaction layer is a separate, strictly black-and-white "
        "1-inch QR sticker.\n"
    )
    require(not documents_red_fallback(exclusive_bw), "self-check treated exclusive B&W as documented fallback")
    require(not mentions_red_fallback(exclusive_bw), "self-check treated exclusive B&W as a red mention")
    documented = (
        "Preferred production is pure black. The official fallback is "
        "pure process red `#FF0000` from `Rad_Dad_QR_RED_1IN_VENDOR_MASTER`.\n"
    )
    require(documents_red_fallback(documented), "self-check missed documented red fallback")
    require(mentions_red_fallback(documented), "self-check missed red fallback mention")
    removable_proof = (
        "Avery 6450 is removable-adhesive proof-only stock. Finished pieces require "
        "permanent adhesive.\n"
    )
    require(
        documents_removable_proof_boundary(removable_proof),
        "self-check missed removable proof-stock boundary",
    )
    require(
        not documents_removable_proof_boundary(
            "Avery 6450 is removable, but it is not proof-only; permanent "
            "finished stock is optional.\n"
        ),
        "self-check accepted guidance that hides removable proof stock",
    )
    require(
        not documents_removable_proof_boundary(
            "Avery 6450 is removable-adhesive proof-only stock. Finished "
            "pieces do not require permanent adhesive.\n"
        ),
        "self-check accepted a negated permanent-stock requirement",
    )
    require(
        not documents_removable_proof_boundary(
            "Avery 6450 removable proof-only? No. Permanent stock is not "
            "required for finished pieces.\n"
        ),
        "self-check accepted question-and-negation guidance",
    )
    require(
        not documents_removable_proof_boundary(
            "Avery 6450 is removable-adhesive proof-only stock. Finished "
            "pieces don't require permanent adhesive.\n"
        ),
        "self-check accepted a contracted stock-requirement negation",
    )
    require(
        not documents_removable_proof_boundary(
            "Avery 6450 is removable-adhesive proof-only? Finished pieces "
            "require permanent adhesive?\n"
        ),
        "self-check accepted questions as affirmative requirements",
    )
    require(
        not documents_removable_proof_boundary(
            "Avery 6450 is removable-adhesive proof-only stock. Finished "
            "pieces optionally require permanent adhesive.\n"
        ),
        "self-check accepted an optional permanent-stock requirement",
    )
    require(
        exact_envelope([58.162, 30.26, 6.685]) == "58.162 x 30.260 x 6.685 mm",
        "self-check formatted cassette envelope incorrectly",
    )


def main() -> int:
    _self_check()
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    authenticity = json.loads(AUTHENTICITY.read_text(encoding="utf-8"))
    products = metadata["products"]
    floppy_rev = revision_from_stem(products["floppy"]["artifact_stem"])
    trailer_rev = revision_from_stem(products["trailer_swift"]["artifact_stem"])
    cassette_rev = revision_from_stem(products["cassette"]["artifact_stem"])
    vhs_rev = revision_from_stem(products["vhs"]["artifact_stem"])
    trailer_project = (
        f"{products['trailer_swift']['artifact_stem']}_A1_MINI_0.4_PROJECT.3mf"
    )
    envelopes = {
        "cassette": exact_envelope(products["cassette"]["exact_envelope_mm"]),
        "floppy": exact_envelope(products["floppy"]["exact_envelope_mm"]),
        "vhs": exact_envelope(products["vhs"]["exact_envelope_mm"]),
        "trailer_swift": exact_envelope(products["trailer_swift"]["exact_envelope_mm"]),
    }

    qr = QR_STICKERS.read_text(encoding="utf-8")
    design = DESIGN.read_text(encoding="utf-8")
    printing = PRINTING.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    nfc = NFC.read_text(encoding="utf-8")
    validation = VALIDATION.read_text(encoding="utf-8")

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
    require(
        f"| Compact cassette | {cassette_rev} | {envelopes['cassette']} |" in design,
        f"Design current-model table does not use exact cassette envelope {envelopes['cassette']}",
    )
    require(
        f"| 3.5-inch floppy | {floppy_rev} | {envelopes['floppy']} |" in design,
        f"Design current-model table does not use exact floppy envelope {envelopes['floppy']}",
    )
    require(
        f"| Mini VHS | {vhs_rev} | {envelopes['vhs']} |" in design,
        f"Design current-model table does not use exact VHS envelope {envelopes['vhs']}",
    )
    require(
        f"| Trailer Swift | {trailer_rev} | {envelopes['trailer_swift']} |" in design,
        f"Design current-model table does not use exact Trailer Swift envelope {envelopes['trailer_swift']}",
    )

    require(
        table_revision(readme, "Rad Dad Compact Cassette") == cassette_rev,
        "README current-model table cassette revision drifted",
    )
    require(
        table_revision(readme, "Rad Dad 3.5-Inch Floppy") == floppy_rev,
        f"README current-model table still names floppy {table_revision(readme, 'Rad Dad 3.5-Inch Floppy')}, not {floppy_rev}",
    )
    require(
        table_revision(readme, "Rad Dad Mini VHS") == vhs_rev,
        "README current-model table VHS revision drifted",
    )
    require(
        table_revision(readme, "Trailer Swift") == trailer_rev,
        f"README current-model table still names Trailer Swift {table_revision(readme, 'Trailer Swift')}, not {trailer_rev}",
    )
    require(
        f"| Rad Dad Compact Cassette | {cassette_rev} | {envelopes['cassette']} |" in readme,
        f"README current-model table does not use exact cassette envelope {envelopes['cassette']}",
    )
    require(
        f"| Rad Dad 3.5-Inch Floppy | {floppy_rev} | {envelopes['floppy']} |" in readme,
        f"README current-model table does not use exact floppy envelope {envelopes['floppy']}",
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

    fallback = authenticity.get("qr", {}).get("color_cartridge_fallback", [])
    require(
        "#FF0000" in fallback and "#FFFFFF" in fallback,
        "Authenticity spec no longer records the official red-on-white fallback",
    )
    for name in RED_FALLBACK_FILES:
        require((QR_ART_DIR / name).is_file(), f"Official red fallback file is missing: {name}")

    require(
        documents_red_fallback(qr),
        "QR sticker guide still omits the official Rad_Dad_QR_RED_ process-red fallback",
    )
    require(
        documents_red_fallback(readme),
        "Root README still omits the official Rad_Dad_QR_RED_ process-red fallback",
    )
    require(
        mentions_red_fallback(design),
        "Design QR standard still describes only a solid-black sticker",
    )
    require(
        mentions_red_fallback(nfc),
        "NFC legacy notice still describes v9 stickers as exclusively black-and-white",
    )
    require(
        mentions_red_fallback(printing),
        "Printing guide QR installation still omits the official red fallback",
    )
    require(
        mentions_red_fallback(validation),
        "Validation QR gate still omits official red-fallback scan checks",
    )
    require(
        "strictly black-and-white" not in qr.lower(),
        "QR sticker guide still claims exclusive black-and-white production",
    )
    require(
        "strictly black-and-white" not in readme.lower(),
        "Root README still claims exclusive black-and-white production",
    )
    require(
        "strictly black-and-white" not in nfc.lower(),
        "NFC legacy notice still claims exclusive black-and-white production",
    )
    require(
        documents_removable_proof_boundary(qr),
        "QR sticker guide does not mark Avery 6450 removable stock as proof-only",
    )
    require(
        documents_removable_proof_boundary(printing),
        "Printing guide does not reject Avery 6450 removable stock for production",
    )

    print(
        "Current merch/QR model docs match "
        f"cassette {cassette_rev}, floppy {floppy_rev}, "
        f"VHS {vhs_rev}, Trailer Swift {trailer_rev}, "
        "document the official red QR fallback, and keep removable Avery 6450 "
        "stock proof-only."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
