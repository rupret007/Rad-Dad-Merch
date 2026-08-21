#!/usr/bin/env python3
"""Build Rad Dad Retro Riot v8: QR Edition.

V8 intentionally reuses the exact v7 model geometry. The mechanically proven
25 mm NFC landings are 26-27 mm protected zones, so they also accept standard
1 inch (25.4 mm) QR labels without changing model size, eyelets, or print
profiles. This builder creates the complete QR artwork, aligned label sheets,
documentation, provenance records, checksums, and deterministic release ZIP.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import sys
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path(__file__).resolve().parent
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

import v7_release_packaging as packaging  # noqa: E402


RELEASE_NAME = "Rad Dad Retro Riot v8: QR Edition"
TAP_URL = "https://raddadband.com/tap/"
SOURCE_RELEASE = REPO_ROOT / "release" / "v7"
DEFAULT_OUTPUT = REPO_ROOT / "release" / "v8"
ARCHIVE_NAME = "Rad_Dad_Retro_Riot_v8_QR_Edition_Print_Pack.zip"

LABEL_DIAMETER_MM = 25.4
LANDING_MINIMUM_MM = 26.0
QR_RENDER_SIZE_MM = 16.5
QR_QUIET_ZONE_MODULES = 4
INDIVIDUAL_DPI = 600
SHEET_DPI = 600
LETTER_MM = (215.9, 279.4)

# Avery 6450 and OnlineLabels OL1025 share this 63-up geometry.
SHEET_COLUMNS = 7
SHEET_ROWS = 9
SHEET_LEFT_MM = 9.525
SHEET_TOP_MM = 12.7
SHEET_PITCH_MM = 28.575

BRAND_INK = "#050B12"
BRAND_CREAM = "#F5F1E8"
BRAND_LIME = "#A6EF12"
BRAND_BLUE = "#1CB5F4"
BRAND_PINK = "#FF3476"


def _atomic_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
    return path


def _atomic_bytes(path: Path, value: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(value)
    temporary.replace(path)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _font(size: int, *, bold: bool = True) -> ImageFont.ImageFont:
    candidates = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        "DejaVuSansCondensed-Bold.ttf",
        "DejaVuSans-Bold.ttf",
    ) if bold else (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _matrix() -> list[list[bool]]:
    matrix = packaging.qr_matrix(TAP_URL)
    if len(matrix) != 29 or any(len(row) != 29 for row in matrix):
        raise RuntimeError("The checked-in Rad Dad QR matrix must remain 29 x 29 modules")
    return matrix


def _module_pitch_mm() -> float:
    return QR_RENDER_SIZE_MM / (len(_matrix()) + 2 * QR_QUIET_ZONE_MODULES)


def _draw_qr_pixels(
    draw: ImageDraw.ImageDraw,
    matrix: Sequence[Sequence[bool]],
    box: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = box
    draw.rectangle(box, fill="#FFFFFF")
    total = len(matrix) + 2 * QR_QUIET_ZONE_MODULES
    width = right - left
    height = bottom - top
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            if not value:
                continue
            x0 = round(left + (column_index + QR_QUIET_ZONE_MODULES) * width / total)
            y0 = round(top + (row_index + QR_QUIET_ZONE_MODULES) * height / total)
            x1 = round(left + (column_index + QR_QUIET_ZONE_MODULES + 1) * width / total)
            y1 = round(top + (row_index + QR_QUIET_ZONE_MODULES + 1) * height / total)
            draw.rectangle((x0, y0, max(x0, x1 - 1), max(y0, y1 - 1)), fill="#000000")


def _sticker_image(dpi: int, *, transparent: bool = True) -> Image.Image:
    pixels = round(LABEL_DIAMETER_MM * dpi / 25.4)
    mode = "RGBA" if transparent else "RGB"
    background = (255, 255, 255, 0) if transparent else "#FFFFFF"
    image = Image.new(mode, (pixels, pixels), background)
    draw = ImageDraw.Draw(image)
    edge = pixels - 1
    draw.ellipse((0, 0, edge, edge), fill=BRAND_INK)
    inset = max(2, round(0.55 * dpi / 25.4))
    draw.ellipse(
        (inset, inset, edge - inset, edge - inset),
        outline=BRAND_LIME,
        width=max(2, round(0.35 * dpi / 25.4)),
    )

    qr_pixels = round(QR_RENDER_SIZE_MM * dpi / 25.4)
    qr_left = (pixels - qr_pixels) // 2
    _draw_qr_pixels(
        draw,
        _matrix(),
        (qr_left, qr_left, qr_left + qr_pixels, qr_left + qr_pixels),
    )

    top_font = _font(max(12, round(1.75 * dpi / 25.4)))
    bottom_font = _font(max(12, round(1.85 * dpi / 25.4)))
    draw.text(
        (pixels / 2, round(2.25 * dpi / 25.4)),
        "RAD DAD",
        font=top_font,
        fill=BRAND_LIME,
        anchor="mm",
    )
    draw.text(
        (pixels / 2, round(23.15 * dpi / 25.4)),
        "SCAN ME",
        font=bottom_font,
        fill=BRAND_CREAM,
        anchor="mm",
    )
    return image


def _qr_svg_elements(matrix: Sequence[Sequence[bool]], x: float, y: float, size: float) -> str:
    total = len(matrix) + 2 * QR_QUIET_ZONE_MODULES
    module = size / total
    elements = [f'<rect x="{x:.6f}" y="{y:.6f}" width="{size:.6f}" height="{size:.6f}" fill="#FFFFFF"/>']
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            if value:
                elements.append(
                    f'<rect x="{x + (column_index + QR_QUIET_ZONE_MODULES) * module:.6f}" '
                    f'y="{y + (row_index + QR_QUIET_ZONE_MODULES) * module:.6f}" '
                    f'width="{module:.6f}" height="{module:.6f}" fill="#000000"/>'
                )
    return "".join(elements)


def _sticker_svg_group(group_id: str = "rad-dad-qr-sticker") -> str:
    center = LABEL_DIAMETER_MM / 2
    qr_left = (LABEL_DIAMETER_MM - QR_RENDER_SIZE_MM) / 2
    return (
        f'<g id="{html.escape(group_id)}">'
        f'<circle cx="{center}" cy="{center}" r="{center}" fill="{BRAND_INK}"/>'
        f'<circle cx="{center}" cy="{center}" r="{center - 0.55}" fill="none" '
        f'stroke="{BRAND_LIME}" stroke-width="0.35"/>'
        + _qr_svg_elements(_matrix(), qr_left, qr_left, QR_RENDER_SIZE_MM)
        + f'<text x="{center}" y="2.25" text-anchor="middle" dominant-baseline="middle" '
        f'font-family="DejaVu Sans, sans-serif" font-size="1.75" font-weight="900" '
        f'fill="{BRAND_LIME}">RAD DAD</text>'
        + f'<text x="{center}" y="23.15" text-anchor="middle" dominant-baseline="middle" '
        f'font-family="DejaVu Sans, sans-serif" font-size="1.85" font-weight="900" '
        f'fill="{BRAND_CREAM}">SCAN ME</text>'
        + "</g>"
    )


def _svg_document(width_mm: float, height_mm: float, body: str, title: str) -> str:
    metadata = json.dumps(
        {
            "url": TAP_URL,
            "finished_label_diameter_mm": LABEL_DIAMETER_MM,
            "qr_render_size_mm": QR_RENDER_SIZE_MM,
            "quiet_zone_modules": QR_QUIET_ZONE_MODULES,
            "print_scale": "100 percent",
        },
        sort_keys=True,
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" '
        f'height="{height_mm}mm" viewBox="0 0 {width_mm} {height_mm}">\n'
        f'<title>{html.escape(title)}</title><metadata>{html.escape(metadata)}</metadata>'
        + body
        + "</svg>\n"
    )


def _save_png(path: Path, image: Image.Image, dpi: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", dpi=(dpi, dpi), optimize=False, compress_level=9)
    return path


def write_individual_sticker(output: Path) -> dict[str, Path]:
    output.mkdir(parents=True, exist_ok=True)
    stem = "Rad_Dad_1IN_QR_STICKER_VENDOR_MASTER"
    image = _sticker_image(INDIVIDUAL_DPI, transparent=True)
    png = _save_png(output / f"{stem}.png", image, INDIVIDUAL_DPI)
    svg = _atomic_text(
        output / f"{stem}.svg",
        _svg_document(
            LABEL_DIAMETER_MM,
            LABEL_DIAMETER_MM,
            _sticker_svg_group(),
            "Rad Dad 1 inch QR sticker vendor master",
        ),
    )
    pdf = _atomic_bytes(
        output / f"{stem}.pdf",
        packaging._image_pdf_bytes([image], [(LABEL_DIAMETER_MM, LABEL_DIAMETER_MM)]),
    )
    return {"png": png, "svg": svg, "pdf": pdf}


def _sheet_pixels(dpi: int) -> tuple[int, int]:
    return tuple(round(value * dpi / 25.4) for value in LETTER_MM)


def write_compatible_63up_sheet(output: Path) -> dict[str, Path]:
    output.mkdir(parents=True, exist_ok=True)
    stem = "Rad_Dad_QR_STICKERS_AVERY_6450_OL1025_63UP_US_LETTER"
    page = Image.new("RGB", _sheet_pixels(SHEET_DPI), "#FFFFFF")
    sticker = _sticker_image(SHEET_DPI, transparent=True)
    left_px = round(SHEET_LEFT_MM * SHEET_DPI / 25.4)
    top_px = round(SHEET_TOP_MM * SHEET_DPI / 25.4)
    pitch_px = round(SHEET_PITCH_MM * SHEET_DPI / 25.4)
    for row in range(SHEET_ROWS):
        for column in range(SHEET_COLUMNS):
            position = (left_px + column * pitch_px, top_px + row * pitch_px)
            page.paste(sticker, position, sticker)

    png = _save_png(output / f"{stem}.png", page, SHEET_DPI)
    pdf = _atomic_bytes(
        output / f"{stem}.pdf",
        packaging._image_pdf_bytes([page], [LETTER_MM]),
    )
    uses = []
    for row in range(SHEET_ROWS):
        for column in range(SHEET_COLUMNS):
            x = SHEET_LEFT_MM + column * SHEET_PITCH_MM
            y = SHEET_TOP_MM + row * SHEET_PITCH_MM
            uses.append(f'<use href="#rad-dad-qr-sticker" x="{x}" y="{y}"/>')
    body = (
        '<rect width="100%" height="100%" fill="#FFFFFF"/>'
        '<defs>' + _sticker_svg_group() + '</defs>' + "".join(uses)
    )
    svg = _atomic_text(
        output / f"{stem}.svg",
        _svg_document(
            LETTER_MM[0],
            LETTER_MM[1],
            body,
            "Rad Dad QR stickers, Avery 6450 and OnlineLabels OL1025, 63-up",
        ),
    )
    return {"png": png, "svg": svg, "pdf": pdf}


def write_hand_cut_sheet(output: Path) -> dict[str, Path]:
    output.mkdir(parents=True, exist_ok=True)
    stem = "Rad_Dad_QR_STICKERS_HAND_CUT_35UP_US_LETTER"
    dpi = 300
    page = Image.new("RGB", _sheet_pixels(dpi), "#FFFFFF")
    draw = ImageDraw.Draw(page)
    sticker = _sticker_image(dpi, transparent=True)
    centers_x = (24.0, 66.0, 108.0, 150.0, 192.0)
    centers_y = (31.0, 66.0, 101.0, 136.0, 171.0, 206.0, 241.0)
    for center_y in centers_y:
        for center_x in centers_x:
            left = round((center_x - LABEL_DIAMETER_MM / 2) * dpi / 25.4)
            top = round((center_y - LABEL_DIAMETER_MM / 2) * dpi / 25.4)
            page.paste(sticker, (left, top), sticker)
            radius = round(LABEL_DIAMETER_MM / 2 * dpi / 25.4)
            draw.ellipse(
                (left, top, left + 2 * radius, top + 2 * radius),
                outline="#9AA4AD",
                width=1,
            )
    draw.text(
        (page.width // 2, round(9.0 * dpi / 25.4)),
        "RAD DAD QR STICKERS | PRINT AT 100% | CUT ON GRAY CIRCLE",
        fill=BRAND_INK,
        font=_font(round(3.1 * dpi / 25.4)),
        anchor="mm",
    )
    draw.text(
        (page.width // 2, round(271.0 * dpi / 25.4)),
        "FINISHED DIAMETER 25.4 MM / 1 INCH | DO NOT FIT OR SCALE",
        fill=BRAND_PINK,
        font=_font(round(2.7 * dpi / 25.4)),
        anchor="mm",
    )
    png = _save_png(output / f"{stem}.png", page, dpi)
    pdf = _atomic_bytes(
        output / f"{stem}.pdf",
        packaging._image_pdf_bytes([page], [LETTER_MM]),
    )

    uses = []
    guides = []
    for center_y in centers_y:
        for center_x in centers_x:
            uses.append(
                f'<use href="#rad-dad-qr-sticker" x="{center_x - LABEL_DIAMETER_MM / 2}" '
                f'y="{center_y - LABEL_DIAMETER_MM / 2}"/>'
            )
            guides.append(
                f'<circle cx="{center_x}" cy="{center_y}" r="{LABEL_DIAMETER_MM / 2}" '
                'fill="none" stroke="#9AA4AD" stroke-width="0.12"/>'
            )
    body = (
        '<rect width="100%" height="100%" fill="#FFFFFF"/>'
        '<text x="107.95" y="9" text-anchor="middle" font-family="sans-serif" '
        'font-size="3.1" font-weight="900">RAD DAD QR STICKERS | PRINT AT 100% | CUT ON GRAY CIRCLE</text>'
        '<defs>' + _sticker_svg_group() + '</defs>' + "".join(uses) + "".join(guides)
        + '<text x="107.95" y="271" text-anchor="middle" font-family="sans-serif" '
        f'font-size="2.7" font-weight="900" fill="{BRAND_PINK}">FINISHED DIAMETER 25.4 MM / 1 INCH | DO NOT FIT OR SCALE</text>'
    )
    svg = _atomic_text(
        output / f"{stem}.svg",
        _svg_document(LETTER_MM[0], LETTER_MM[1], body, "Rad Dad QR hand-cut sticker sheet"),
    )
    return {"png": png, "svg": svg, "pdf": pdf}


def write_calibration_page(output: Path) -> dict[str, Path]:
    output.mkdir(parents=True, exist_ok=True)
    stem = "Rad_Dad_QR_STICKER_PRINT_CALIBRATION"
    dpi = 300
    page = Image.new("RGB", _sheet_pixels(dpi), "#FFFFFF")
    draw = ImageDraw.Draw(page)
    title = _font(round(5.0 * dpi / 25.4))
    body_font = _font(round(3.0 * dpi / 25.4), bold=False)
    draw.text((page.width // 2, round(18 * dpi / 25.4)), "RAD DAD QR PRINT CALIBRATION", fill=BRAND_INK, font=title, anchor="mm")
    draw.text((page.width // 2, round(30 * dpi / 25.4)), "PRINT AT ACTUAL SIZE / 100%. TURN OFF FIT, SHRINK, AND SCALE.", fill=BRAND_PINK, font=body_font, anchor="mm")
    sticker = _sticker_image(dpi, transparent=True)
    left = round(35 * dpi / 25.4)
    top = round(50 * dpi / 25.4)
    page.paste(sticker, (left, top), sticker)
    draw.text((round(95 * dpi / 25.4), round(61 * dpi / 25.4)), "1. Measure the circle.", fill=BRAND_INK, font=body_font, anchor="lm")
    draw.text((round(95 * dpi / 25.4), round(70 * dpi / 25.4)), "It must be 25.4 mm / 1.000 inch.", fill=BRAND_INK, font=body_font, anchor="lm")
    draw.text((round(95 * dpi / 25.4), round(79 * dpi / 25.4)), "2. Scan this printed QR before using label stock.", fill=BRAND_INK, font=body_font, anchor="lm")
    square_left = round(35 * dpi / 25.4)
    square_top = round(108 * dpi / 25.4)
    square_size = round(50 * dpi / 25.4)
    draw.rectangle((square_left, square_top, square_left + square_size, square_top + square_size), outline=BRAND_INK, width=2)
    draw.text((round(95 * dpi / 25.4), round(128 * dpi / 25.4)), "50.0 mm reference square", fill=BRAND_INK, font=body_font, anchor="lm")
    draw.text((page.width // 2, round(185 * dpi / 25.4)), "PASS ONLY IF BOTH MEASUREMENTS ARE CORRECT AND THE QR OPENS:", fill=BRAND_INK, font=body_font, anchor="mm")
    draw.text((page.width // 2, round(196 * dpi / 25.4)), TAP_URL, fill=BRAND_BLUE, font=body_font, anchor="mm")
    png = _save_png(output / f"{stem}.png", page, dpi)
    pdf = _atomic_bytes(output / f"{stem}.pdf", packaging._image_pdf_bytes([page], [LETTER_MM]))
    return {"png": png, "pdf": pdf}


def write_preview(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (1400, 1000), BRAND_INK)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((35, 35, 1365, 965), radius=30, fill="#0C1722", outline="#263847", width=3)
    draw.text((700, 88), "RAD DAD QR STICKER SYSTEM", font=_font(54), fill=BRAND_CREAM, anchor="mm")
    draw.text((700, 145), "ONE SCAN. NO APP. NO NFC SETUP.", font=_font(30), fill=BRAND_LIME, anchor="mm")
    sticker = _sticker_image(INDIVIDUAL_DPI, transparent=True).resize((680, 680), Image.Resampling.NEAREST)
    canvas.paste(sticker, (360, 185), sticker)
    draw.text((700, 905), "25.4 MM / 1 INCH | FITS EVERY V7 LANDING", font=_font(28), fill=BRAND_BLUE, anchor="mm")
    return _save_png(output / "Rad_Dad_v8_QR_STICKER_SYSTEM_PREVIEW.png", canvas, 144)


def write_placement_guide(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    panels = (
        ("CASSETTE", "CENTER ON FLAT REAR", 250, 330, BRAND_LIME),
        ("FLOPPY", "CENTER IN REAR HUB RING", 850, 330, BRAND_BLUE),
        ("VHS", "CENTER IN REAR RING", 250, 660, BRAND_PINK),
        ("TRAILER SWIFT", "CENTER UNDER BASE", 850, 660, "#FFB000"),
    )
    body = [f'<rect width="1100" height="850" fill="{BRAND_INK}"/>']
    body.append(f'<text x="550" y="64" text-anchor="middle" font-family="sans-serif" font-size="44" font-weight="900" fill="{BRAND_CREAM}">RAD DAD QR STICKER PLACEMENT</text>')
    body.append(f'<text x="550" y="108" text-anchor="middle" font-family="sans-serif" font-size="24" font-weight="900" fill="{BRAND_LIME}">CENTER ONE 1-INCH STICKER IN THE EXISTING CIRCULAR LANDING</text>')
    for title, location, x, y, accent in panels:
        body.extend(
            (
                f'<rect x="{x - 220}" y="{y - 120}" width="440" height="240" rx="22" fill="#0C1722" stroke="{accent}" stroke-width="5"/>',
                f'<circle cx="{x}" cy="{y}" r="72" fill="{BRAND_CREAM}" stroke="{accent}" stroke-width="8"/>',
                f'<rect x="{x - 47}" y="{y - 47}" width="94" height="94" fill="#FFFFFF" stroke="#000000" stroke-width="4"/>',
                f'<text x="{x}" y="{y - 82}" text-anchor="middle" font-family="sans-serif" font-size="30" font-weight="900" fill="{BRAND_CREAM}">{title}</text>',
                f'<text x="{x}" y="{y + 105}" text-anchor="middle" font-family="sans-serif" font-size="21" font-weight="900" fill="{accent}">{location}</text>',
            )
        )
    body.append(f'<text x="550" y="815" text-anchor="middle" font-family="sans-serif" font-size="20" font-weight="900" fill="{BRAND_CREAM}">CLEAN WITH 70% ISOPROPYL ALCOHOL | DRY | CENTER | PRESS 30 SECONDS | CURE 24 HOURS</text>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="279.4mm" height="215.9mm" viewBox="0 0 1100 850">'
        + "".join(body)
        + "</svg>\n"
    )
    return _atomic_text(output / "Rad_Dad_QR_STICKER_PLACEMENT_GUIDE.svg", svg)


def _copy_geometry(output: Path) -> dict[str, dict[str, str]]:
    if not SOURCE_RELEASE.is_dir():
        raise FileNotFoundError(f"Missing source release: {SOURCE_RELEASE}")
    records: dict[str, dict[str, str]] = {}
    for directory in ("3mf", "stl"):
        destination = output / directory
        destination.mkdir(parents=True, exist_ok=True)
        for source in sorted((SOURCE_RELEASE / directory).glob("*")):
            if not source.is_file() or source.name == ".DS_Store":
                continue
            copied = destination / source.name
            shutil.copyfile(source, copied)
            source_hash = _sha256(source)
            copied_hash = _sha256(copied)
            if source_hash != copied_hash:
                raise RuntimeError(f"Geometry copy hash mismatch: {source.name}")
            records[f"{directory}/{source.name}"] = {
                "source": source.relative_to(REPO_ROOT).as_posix(),
                "source_sha256": source_hash,
                "copied_sha256": copied_hash,
                "geometry_changed": False,
            }

    previews = output / "previews"
    previews.mkdir(parents=True, exist_ok=True)
    for source in sorted((SOURCE_RELEASE / "previews").glob("*.png")):
        if "_BACK" in source.name:
            continue
        shutil.copyfile(source, previews / source.name)
    return records


def _copy_geometry_qa(output: Path) -> None:
    destination = output / "qa" / "v7_geometry_evidence"
    destination.mkdir(parents=True, exist_ok=True)
    for name in (
        "ALL_FOUR_PLATE_LAYOUT.json",
        "BAMBU_PROJECT_STATUS.json",
        "BUILD_INDEX.json",
        "MODEL_QA.json",
        "PRINT_INTENTS.json",
        "PRODUCT_METADATA.json",
    ):
        source = SOURCE_RELEASE / "qa" / name
        if source.is_file():
            shutil.copyfile(source, destination / name)


def _write_json(path: Path, value: object) -> Path:
    return _atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_release_documents(output: Path, geometry_records: dict[str, dict[str, str]]) -> None:
    guides = output / "guides"
    qa = output / "qa"
    guides.mkdir(parents=True, exist_ok=True)
    qa.mkdir(parents=True, exist_ok=True)

    specification = {
        "schema": "rad-dad-qr-sticker-spec-v1",
        "release": RELEASE_NAME,
        "destination_url": TAP_URL,
        "qr_matrix_modules": len(_matrix()),
        "error_correction": "Q",
        "quiet_zone_modules": QR_QUIET_ZONE_MODULES,
        "qr_render_size_mm": QR_RENDER_SIZE_MM,
        "module_pitch_mm": round(_module_pitch_mm(), 6),
        "finished_label_diameter_mm": LABEL_DIAMETER_MM,
        "minimum_model_landing_mm": LANDING_MINIMUM_MM,
        "contrast": "black modules on white quiet zone",
        "artwork_dpi": INDIVIDUAL_DPI,
        "sheet_layout": {
            "compatible_stock": ["Avery 6450", "OnlineLabels OL1025"],
            "page": "US Letter",
            "columns": SHEET_COLUMNS,
            "rows": SHEET_ROWS,
            "labels_per_sheet": SHEET_COLUMNS * SHEET_ROWS,
            "left_margin_mm": SHEET_LEFT_MM,
            "top_margin_mm": SHEET_TOP_MM,
            "pitch_mm": SHEET_PITCH_MM,
        },
        "geometry_policy": "v7 meshes and 3MF projects reused byte-for-byte",
    }
    _write_json(qa / "QR_SPEC.json", specification)
    _write_json(
        qa / "MODEL_REUSE_PROVENANCE.json",
        {
            "schema": "rad-dad-model-reuse-v1",
            "release": RELEASE_NAME,
            "source_release": "release/v7",
            "reason": "Interaction method changed; geometry, dimensions, eyelets, and print profiles did not.",
            "files": geometry_records,
        },
    )

    setup = f"""# QR sticker setup

## What changed

The NFC tag and NFC overlay have been replaced by one visible QR sticker. The
sticker itself tells the recipient what to do, opens with the standard camera,
and does not need NFC programming or a separate `TAP ME` layer.

## Encoded address

`{TAP_URL}`

The QR is static, but the address is controlled by Rad Dad. Keep this route live
and update the landing page behind it rather than changing the printed code.

## Install

1. Print the calibration page at **Actual Size / 100%**. Disable Fit, Shrink,
   Scale to Fit, and borderless enlargement.
2. Confirm the reference circle measures 25.4 mm and the 50 mm square measures
   50 mm.
3. Scan one ordinary-paper proof with an iPhone and Android phone.
4. Print the 63-up file on Avery 6450 or OnlineLabels OL1025 stock, or send the
   individual vendor master to a sticker printer.
5. Scan three labels from different areas of the sheet before peeling them.
6. Clean the model landing with 70% isopropyl alcohol and allow it to dry.
7. Center the sticker in the existing circular landing and press for 30 seconds.
8. Allow the adhesive to cure for 24 hours before keychain carry.
9. Scan every finished piece from the normal camera app before distribution.

## Acceptance rule

A finished piece passes only when the QR opens `{TAP_URL}` with the normal
camera on both iPhone and Android, with an ordinary phone case installed, in
indoor light and bright daylight.
"""
    _atomic_text(guides / "QR_STICKER_SETUP.md", setup)

    sourcing = """# Where to get the 1-inch QR stickers

## Best balance of speed, cost, and durability

**OnlineLabels OL1025WJ weatherproof matte inkjet** is the recommended small-batch
production stock. It is a true 1-inch circle, 63 labels per US Letter sheet,
has a weatherproof matte face, accepts the supplied 63-up file, has no minimum,
and the vendor advertises same-business-day shipping for in-stock orders placed
before 5 p.m. ET.

https://www.onlinelabels.com/products/ol1025wj

## Cheapest immediate proof stock

**Avery 6450** is a widely available 1-inch round sheet with the exact same
63-up layout. It works in laser and inkjet printers and is inexpensive per
label, but it is removable matte paper. Use it for fit and scan proofs, not for
final keychain batches exposed to abrasion or moisture.

https://www.avery.com/products/labels/6450

## Professional finished batch

**Sticker it custom 1-inch round stickers** are laminated, water resistant,
scratch resistant, supplied with a free proof, and advertised to ship in a few
days. Upload the individual SVG or 600 DPI PNG vendor master. Choose white
vinyl, matte or gloss laminate, exact 1-inch circle, and no metallic material.

https://www.stickerit.co/en-us/custom-stickers/custom-1-inch-round-stickers

## Same-day emergency option

Staples offers same-day pickup on select custom labels ordered before noon.
Confirm that the selected store can produce an exact 1-inch circle at 100%
scale before ordering. Upload the vendor PDF and request one physical proof.

https://www.staples.com/services/printing/custom-labels-stickers/

## Purchase rule

Order a small proof quantity first. Do not approve a production batch until
three labels from the top, center, and bottom of the sheet scan correctly and
measure 25.4 mm.
"""
    _atomic_text(guides / "STICKER_SOURCING.md", sourcing)

    printing = """# Printing and 3MF status

V8 changes the interaction layer only. Every STL and 3MF in this pack is an
exact byte-for-byte copy of the v7 Micro Replica Edition file. The cassette,
floppy, VHS, Trailer Swift figure, model dimensions, eyelets, support intents,
and Bambu profiles are unchanged.

Use the `_A1_MINI_0.4_PROJECT.3mf` files for embedded Bambu settings. Use the
`_MODEL_ONLY.3mf` or binary STL files when selecting your own slicer profile.
The all-four Bambu project remains the current combined plate.

Print one of each before batch production and review every sliced layer. The
QR sticker is installed only after the print has cooled, been inspected, and
the landing has been cleaned.
"""
    _atomic_text(guides / "PRINTING_AND_3MF_STATUS.md", printing)

    qc = f"""# V8 QR Edition physical quality-control checklist

Record printer, nozzle, filament, plate, slicer version, sticker stock, printer
used for labels, date, phone models, split ring, and operator.

## Printed object

- [ ] Cassette, floppy, and VHS are recognizable within two seconds.
- [ ] Trailer Swift stands without rocking.
- [ ] `RAD DAD`, `C-69`, `3.69 MB`, `T-369`, and `TRAILER SWIFT` are readable.
- [ ] No gaps, strings, sharp scars, loose details, or underside damage.
- [ ] Every media eyelet accepts the thickest production split ring easily.
- [ ] Required load, twist, drop, and carry tests are complete.

## Sticker production

- [ ] Calibration circle measures 25.4 mm / 1.000 inch.
- [ ] Calibration square measures 50.0 mm.
- [ ] Page was printed at Actual Size / 100% with automatic scaling disabled.
- [ ] Black modules are solid, square, and free of streaks or toner voids.
- [ ] White quiet zone is clean and uninterrupted.
- [ ] Top, center, and bottom sheet samples scan before installation.

## Finished product scan gate

- [ ] Sticker is centered inside the model's circular landing.
- [ ] Sticker edge is fully adhered with no bubbles, wrinkles, or lifted edge.
- [ ] Finished piece opens `{TAP_URL}` on iPhone.
- [ ] Finished piece opens `{TAP_URL}` on Android.
- [ ] Both phones pass with ordinary protective cases installed.
- [ ] Indoor light and bright daylight both pass.
- [ ] Scan passes again after 24-hour adhesive cure.
- [ ] Keychain pieces pass after split-ring installation and representative keys are attached.
- [ ] PASS: approved for distribution.
- [ ] HOLD: defect documented and corrected before rework or reprint.
"""
    _atomic_text(qa / "PHYSICAL_QC_CHECKLIST.md", qc)

    readme = f"""# {RELEASE_NAME}

**OLD MEDIA. LOUD BAND. ONE SCAN.**

This is the complete QR-first release of the Rad Dad cassette, floppy disk,
mini VHS, and Trailer Swift desk collectible. The proven v7 geometry is reused
byte-for-byte. A single visible 1-inch QR sticker now replaces the NFC tag,
programming step, and separate NFC overlay.

## Start here

| Need | File |
|---|---|
| Print on Avery 6450 or OnlineLabels OL1025 | [63-up PDF](guides/qr_stickers/Rad_Dad_QR_STICKERS_AVERY_6450_OL1025_63UP_US_LETTER.pdf) |
| Print on full-sheet sticker paper and hand cut | [35-up PDF](guides/qr_stickers/Rad_Dad_QR_STICKERS_HAND_CUT_35UP_US_LETTER.pdf) |
| Send artwork to a sticker vendor | [Individual SVG](guides/qr_stickers/Rad_Dad_1IN_QR_STICKER_VENDOR_MASTER.svg) |
| Check printer scaling first | [Calibration PDF](guides/qr_stickers/Rad_Dad_QR_STICKER_PRINT_CALIBRATION.pdf) |
| Install the labels | [QR setup guide](guides/QR_STICKER_SETUP.md) |
| Buy suitable stock | [Sticker sourcing guide](guides/STICKER_SOURCING.md) |
| Find each placement area | [Placement guide](guides/Rad_Dad_QR_STICKER_PLACEMENT_GUIDE.svg) |
| Print the models | Open the `3mf/` directory or use the universal files in `stl/` |

## QR specification

- Destination: `{TAP_URL}`
- Finished label: 25.4 mm / 1 inch round
- QR matrix: 29 x 29 modules, error correction Q
- Quiet zone: 4 modules on every side
- Printed QR square: 16.5 mm
- Module pitch: {_module_pitch_mm():.3f} mm
- Minimum model landing: {LANDING_MINIMUM_MM:.1f} mm
- Artwork: black QR on white, 600 DPI and vector masters included

## Model geometry

V8 does not resize or remodel the collectibles. The copied STL and 3MF hashes
are recorded in `qa/MODEL_REUSE_PROVENANCE.json`; the v7 digital geometry
evidence is retained under `qa/v7_geometry_evidence/`.

## Distribution gate

Do not hand out a piece until its installed QR code opens the Rad Dad tap page
from the normal camera on both iPhone and Android. Repeat the scan after the
adhesive has cured for 24 hours.
"""
    _atomic_text(output / "README.md", readme)


def write_sha256s(output: Path, excluded: Iterable[Path]) -> Path:
    excluded_resolved = {path.resolve() for path in excluded}
    records = []
    for path in sorted(output.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file() and path.resolve() not in excluded_resolved:
            records.append(f"{_sha256(path)}  {path.relative_to(output).as_posix()}")
    return _atomic_text(output / "SHA256SUMS.txt", "\n".join(records) + "\n")


def build_release(output: Path) -> dict[str, Path]:
    output.mkdir(parents=True, exist_ok=True)
    qr_output = output / "guides" / "qr_stickers"
    geometry_records = _copy_geometry(output)
    _copy_geometry_qa(output)
    write_individual_sticker(qr_output)
    write_compatible_63up_sheet(qr_output)
    write_hand_cut_sheet(qr_output)
    write_calibration_page(qr_output)
    write_preview(output / "previews")
    write_placement_guide(output / "guides")
    write_release_documents(output, geometry_records)

    archive = output / ARCHIVE_NAME
    sidecar = archive.with_name(archive.name + ".sha256")
    manifest = output / "MANIFEST.json"
    sums = output / "SHA256SUMS.txt"
    write_sha256s(output, (archive, sidecar, manifest, sums))
    packaging.write_release_manifest(
        output,
        release_name=RELEASE_NAME,
        output_path=manifest,
        exclude=(archive, sidecar),
        metadata={
            "interaction": "visible 1-inch QR sticker",
            "destination_url": TAP_URL,
            "source_geometry_release": "v7",
            "geometry_changed": False,
            "printer_target": "Bambu Lab A1 mini / 0.4 mm nozzle",
        },
    )
    packaging.create_deterministic_zip(
        output,
        archive,
        archive_prefix="Rad_Dad_Retro_Riot_v8_QR_Edition",
        exclude=(archive, sidecar),
    )
    packaging.write_sha256_sidecar(archive)
    return {
        "release": output,
        "archive": archive,
        "manifest": manifest,
        "sha256s": sums,
        "sticker_pdf": qr_output / "Rad_Dad_QR_STICKERS_AVERY_6450_OL1025_63UP_US_LETTER.pdf",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Release directory (default: release/v8)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.output.expanduser()
    if not output.is_absolute():
        output = (REPO_ROOT / output).resolve()
    result = build_release(output)
    print(f"Release: {result['release']}")
    print(f"Print pack: {result['archive']}")
    print(f"63-up sticker PDF: {result['sticker_pdf']}")
    print(f"Manifest: {result['manifest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
