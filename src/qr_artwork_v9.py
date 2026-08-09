"""Production QR artwork for the Rad Dad retro keychain collection.

This module deliberately generates only black and white artwork for
https://raddadband.com/tap/.  It reuses the proven 29-module QR matrix and the
pre-cut sheet geometry established by ``build_rad_dad_qr_release_v8``.

Production notes
----------------
* Print every PDF or PNG at 100 percent / Actual Size. Disable Fit, Shrink,
  Scale to Fit, and borderless enlargement.
* The QR field is exactly 16.5 mm square, including a four-module quiet zone.
  Nothing is drawn inside that quiet zone except its white background.
* Raster masters are native 600 DPI, one-bit black and white, with no gray,
  color, transparency, or antialiasing.
* The 63-up sheet uses the exact Avery 6450 / OnlineLabels OL1025 geometry:
  seven columns, nine rows, 0.375-inch left margin, 0.5-inch top margin, and
  1.125-inch horizontal and vertical pitch.
* The FedEx Office / Kinko's sheet uses 48 circles with 0.25-inch gaps and
  external crop ticks for easier hand cutting from full-sheet adhesive stock.
* Measure the calibration targets and test-scan one code before producing a
  full batch. Keep tape seams, glare, folds, and trimming outside the QR field.

Call ``write_qr_artwork_v9(output_dir)`` to create all production files. The
function returns a dictionary whose values are the generated ``Path`` objects.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - reported clearly at runtime
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageFont = None  # type: ignore[assignment]
    _PIL_IMPORT_ERROR: ImportError | None = exc
else:
    _PIL_IMPORT_ERROR = None


TARGET_URL = "https://raddadband.com/tap/"

MM_PER_INCH = 25.4
DPI = 600

STICKER_DIAMETER_MM = 25.4
QR_FIELD_MM = 16.5
QUIET_ZONE_MODULES = 4
EXPECTED_MATRIX_MODULES = 29

LETTER_WIDTH_MM = 215.9
LETTER_HEIGHT_MM = 279.4

# Exact geometry carried forward from build_rad_dad_qr_release_v8.
PRECUT_COLUMNS = 7
PRECUT_ROWS = 9
PRECUT_LEFT_MARGIN_MM = 9.525
PRECUT_TOP_MARGIN_MM = 12.7
PRECUT_PITCH_X_MM = 28.575
PRECUT_PITCH_Y_MM = 28.575

# A roomier layout for full-sheet adhesive paper and hand cutting.
HANDCUT_COLUMNS = 6
HANDCUT_ROWS = 8
HANDCUT_PITCH_MM = 31.75  # 1.25 inches: 1-inch art plus a 0.25-inch gap.
HANDCUT_LEFT_EDGE_MM = 15.875  # 0.625-inch balanced page margin.
HANDCUT_TOP_EDGE_MM = 15.875

_BLACK = 0
_WHITE = 1

__all__ = ["write_qr_artwork_v9"]


def _mm_to_px(value_mm: float) -> int:
    return int(round(value_mm * DPI / MM_PER_INCH))


def _fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _load_v8_module() -> types.ModuleType:
    """Import the v8 builder without reading or duplicating its source text."""

    candidates: list[str] = []
    if __package__:
        candidates.append(f"{__package__}.build_rad_dad_qr_release_v8")
    candidates.append("build_rad_dad_qr_release_v8")

    src_dir = str(Path(__file__).resolve().parent)
    inserted = False
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
        inserted = True

    errors: list[BaseException] = []
    try:
        for module_name in candidates:
            try:
                return importlib.import_module(module_name)
            except (ImportError, ModuleNotFoundError) as exc:
                errors.append(exc)
    finally:
        if inserted:
            try:
                sys.path.remove(src_dir)
            except ValueError:
                pass

    detail = "; ".join(str(error) for error in errors)
    raise RuntimeError(
        "Unable to import build_rad_dad_qr_release_v8, which owns the proven "
        f"QR matrix. Import details: {detail}"
    )


def _bit_row(value: Any) -> tuple[int, ...] | None:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        chars = set(text)
        if chars <= {"0", "1"}:
            return tuple(1 if char == "1" else 0 for char in text)
        if chars <= {"#", "."}:
            return tuple(1 if char == "#" else 0 for char in text)
        if chars <= {"X", "x", "."}:
            return tuple(1 if char in {"X", "x"} else 0 for char in text)
        return None

    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        row: list[int] = []
        for cell in value:
            if isinstance(cell, bool):
                row.append(int(cell))
            elif isinstance(cell, int) and cell in (0, 1):
                row.append(cell)
            else:
                return None
        return tuple(row) if row else None
    return None


def _coerce_matrix(value: Any) -> tuple[tuple[int, ...], ...] | None:
    """Convert a common QR matrix representation into zero/one rows."""

    if hasattr(value, "get_matrix") and callable(value.get_matrix):
        try:
            value = value.get_matrix()
        except Exception:
            return None

    if isinstance(value, str):
        raw_rows: Sequence[Any] = [
            line.strip() for line in value.splitlines() if line.strip()
        ]
    elif isinstance(value, Sequence) and not isinstance(
        value, (bytes, bytearray)
    ):
        raw_rows = value
    else:
        return None

    rows: list[tuple[int, ...]] = []
    for raw_row in raw_rows:
        row = _bit_row(raw_row)
        if row is None:
            return None
        rows.append(row)

    if not rows or len(rows) != len(rows[0]):
        return None
    if any(len(row) != len(rows) for row in rows):
        return None
    return tuple(rows)


def _invert(matrix: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(0 if cell else 1 for cell in row) for row in matrix)


def _trim_white_border(
    matrix: tuple[tuple[int, ...], ...]
) -> tuple[tuple[int, ...], ...]:
    result = matrix
    while len(result) > EXPECTED_MATRIX_MODULES:
        top = result[0]
        bottom = result[-1]
        left = tuple(row[0] for row in result)
        right = tuple(row[-1] for row in result)
        if any(top) or any(bottom) or any(left) or any(right):
            break
        result = tuple(tuple(row[1:-1]) for row in result[1:-1])
    return result


_FINDER = (
    (1, 1, 1, 1, 1, 1, 1),
    (1, 0, 0, 0, 0, 0, 1),
    (1, 0, 1, 1, 1, 0, 1),
    (1, 0, 1, 1, 1, 0, 1),
    (1, 0, 1, 1, 1, 0, 1),
    (1, 0, 0, 0, 0, 0, 1),
    (1, 1, 1, 1, 1, 1, 1),
)


def _finder_matches(
    matrix: tuple[tuple[int, ...], ...], start_x: int, start_y: int
) -> bool:
    return all(
        matrix[start_y + row][start_x + column] == _FINDER[row][column]
        for row in range(7)
        for column in range(7)
    )


def _finder_score(matrix: tuple[tuple[int, ...], ...]) -> int:
    size = len(matrix)
    if size < 21:
        return 0
    return sum(
        (
            _finder_matches(matrix, 0, 0),
            _finder_matches(matrix, size - 7, 0),
            _finder_matches(matrix, 0, size - 7),
        )
    )


def _prepared_candidate(value: Any) -> tuple[tuple[int, ...], ...] | None:
    matrix = _coerce_matrix(value)
    if matrix is None:
        return None

    for candidate in (matrix, _invert(matrix)):
        candidate = _trim_white_border(candidate)
        if (
            len(candidate) == EXPECTED_MATRIX_MODULES
            and _finder_score(candidate) == 3
        ):
            return candidate
    return None


def _local_namespaces(root: types.ModuleType) -> Iterable[types.ModuleType]:
    """Yield the v8 module and local helper modules it imported."""

    src_dir = Path(__file__).resolve().parent
    queue = [root]
    seen: set[int] = set()
    while queue:
        module = queue.pop(0)
        if id(module) in seen:
            continue
        seen.add(id(module))
        yield module
        for value in vars(module).values():
            if not isinstance(value, types.ModuleType):
                continue
            module_file = getattr(value, "__file__", None)
            if module_file is None:
                continue
            try:
                if Path(module_file).resolve().parent == src_dir:
                    queue.append(value)
            except OSError:
                continue


def _matrix_from_v8() -> tuple[tuple[int, ...], ...]:
    """Recover the checked-in, already-proven QR matrix exported through v8."""

    v8 = _load_v8_module()
    namespaces = list(_local_namespaces(v8))

    # Prefer explicitly named QR/matrix values, then inspect other constants.
    for preferred_only in (True, False):
        for module in namespaces:
            for name, value in vars(module).items():
                lowered = name.lower()
                preferred = "qr" in lowered or "matrix" in lowered
                if preferred_only != preferred:
                    continue
                candidate = _prepared_candidate(value)
                if candidate is not None:
                    return candidate

    # Some QR libraries expose a zero-argument or URL-argument matrix helper.
    for module in namespaces:
        for name, value in vars(module).items():
            lowered = name.lower()
            if not callable(value):
                continue
            if "qr" not in lowered or not any(
                token in lowered for token in ("matrix", "rows", "modules")
            ):
                continue
            if any(token in lowered for token in ("write", "build", "draw", "render")):
                continue
            for args in ((), (TARGET_URL,)):
                try:
                    result = value(*args)
                except Exception:
                    continue
                candidate = _prepared_candidate(result)
                if candidate is not None:
                    return candidate

    raise RuntimeError(
        "The proven 29x29 QR matrix could not be recovered from "
        "build_rad_dad_qr_release_v8 or its local packaging module. The v9 "
        "artwork intentionally refuses to substitute a newly generated code."
    )


def _require_pillow() -> None:
    if _PIL_IMPORT_ERROR is not None:
        raise RuntimeError(
            "Pillow is required to write the 600-DPI PNG and PDF masters."
        ) from _PIL_IMPORT_ERROR


def _qr_module_rectangles(
    matrix: tuple[tuple[int, ...], ...]
) -> Iterable[tuple[float, float, float, float]]:
    """Yield compact horizontal black runs in sticker-local millimeters."""

    total_modules = len(matrix) + 2 * QUIET_ZONE_MODULES
    pitch = QR_FIELD_MM / total_modules
    origin = (STICKER_DIAMETER_MM - QR_FIELD_MM) / 2

    for row_index, row in enumerate(matrix):
        column = 0
        while column < len(row):
            if not row[column]:
                column += 1
                continue
            run_start = column
            while column < len(row) and row[column]:
                column += 1
            x = origin + (QUIET_ZONE_MODULES + run_start) * pitch
            y = origin + (QUIET_ZONE_MODULES + row_index) * pitch
            width = (column - run_start) * pitch
            yield x, y, width, pitch


def _sticker_svg_definition(
    matrix: tuple[tuple[int, ...], ...]
) -> str:
    origin = (STICKER_DIAMETER_MM - QR_FIELD_MM) / 2
    radius = STICKER_DIAMETER_MM / 2 - 0.15
    lines = [
        '<g id="radDadQrStickerV9">',
        (
            f'<circle cx="{_fmt(STICKER_DIAMETER_MM / 2)}" '
            f'cy="{_fmt(STICKER_DIAMETER_MM / 2)}" r="{_fmt(radius)}" '
            'fill="#ffffff" stroke="#000000" stroke-width="0.3"/>'
        ),
        (
            f'<rect x="{_fmt(origin)}" y="{_fmt(origin)}" '
            f'width="{_fmt(QR_FIELD_MM)}" height="{_fmt(QR_FIELD_MM)}" '
            'fill="#ffffff"/>'
        ),
        '<g fill="#000000" shape-rendering="crispEdges">',
    ]
    for x, y, width, height in _qr_module_rectangles(matrix):
        lines.append(
            f'<rect x="{_fmt(x)}" y="{_fmt(y)}" '
            f'width="{_fmt(width)}" height="{_fmt(height)}"/>'
        )
    lines.extend(("</g>", "</g>"))
    return "\n".join(lines)


def _svg_document(
    width_mm: float,
    height_mm: float,
    definitions: str,
    body: Iterable[str],
) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{_fmt(width_mm)}mm" height="{_fmt(height_mm)}mm" '
            f'viewBox="0 0 {_fmt(width_mm)} {_fmt(height_mm)}">'
        ),
        (
            f'<rect x="0" y="0" width="{_fmt(width_mm)}" '
            f'height="{_fmt(height_mm)}" fill="#ffffff"/>'
        ),
        "<defs>",
        definitions,
        "</defs>",
    ]
    lines.extend(body)
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _draw_qr_raster(
    draw: Any,
    matrix: tuple[tuple[int, ...], ...],
    left_px: int,
    top_px: int,
    field_px: int,
) -> None:
    total_modules = len(matrix) + 2 * QUIET_ZONE_MODULES
    boundaries = [
        int(round(index * field_px / total_modules))
        for index in range(total_modules + 1)
    ]

    draw.rectangle(
        (left_px, top_px, left_px + field_px - 1, top_px + field_px - 1),
        fill=_WHITE,
    )
    for row_index, row in enumerate(matrix):
        for column_index, cell in enumerate(row):
            if not cell:
                continue
            module_x = column_index + QUIET_ZONE_MODULES
            module_y = row_index + QUIET_ZONE_MODULES
            x0 = left_px + boundaries[module_x]
            y0 = top_px + boundaries[module_y]
            x1 = left_px + boundaries[module_x + 1] - 1
            y1 = top_px + boundaries[module_y + 1] - 1
            draw.rectangle((x0, y0, x1, y1), fill=_BLACK)


def _sticker_tile(matrix: tuple[tuple[int, ...], ...]) -> Any:
    diameter_px = _mm_to_px(STICKER_DIAMETER_MM)
    field_px = _mm_to_px(QR_FIELD_MM)
    field_left = (diameter_px - field_px) // 2
    tile = Image.new("1", (diameter_px, diameter_px), color=_WHITE)
    draw = ImageDraw.Draw(tile)

    outline_px = max(1, _mm_to_px(0.3))
    draw.ellipse(
        (0, 0, diameter_px - 1, diameter_px - 1),
        fill=_WHITE,
        outline=_BLACK,
        width=outline_px,
    )
    _draw_qr_raster(draw, matrix, field_left, field_left, field_px)
    return tile


def _save_png(image: Any, path: Path) -> None:
    image.save(path, format="PNG", dpi=(DPI, DPI), optimize=True)


def _save_pdf(image: Any, path: Path) -> None:
    # One-bit input keeps the PDF strictly black and white without JPEG noise.
    image.save(path, format="PDF", resolution=float(DPI))


def _font(size_px: int, bold: bool = False) -> Any:
    candidates = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size_px)
        except OSError:
            continue
    return ImageFont.load_default()


def _centered_text(draw: Any, center_x: int, y: int, text: str, font: Any) -> None:
    bounds = draw.textbbox((0, 0), text, font=font)
    width = bounds[2] - bounds[0]
    draw.text((center_x - width // 2, y), text, fill=_BLACK, font=font)


def _individual_svg(matrix: tuple[tuple[int, ...], ...]) -> str:
    definition = _sticker_svg_definition(matrix)
    body = (
        '<use href="#radDadQrStickerV9" '
        'xlink:href="#radDadQrStickerV9" x="0" y="0"/>',
    )
    return _svg_document(
        STICKER_DIAMETER_MM, STICKER_DIAMETER_MM, definition, body
    )


def _precut_svg(matrix: tuple[tuple[int, ...], ...]) -> str:
    definition = _sticker_svg_definition(matrix)
    body: list[str] = []
    for row in range(PRECUT_ROWS):
        y = PRECUT_TOP_MARGIN_MM + row * PRECUT_PITCH_Y_MM
        for column in range(PRECUT_COLUMNS):
            x = PRECUT_LEFT_MARGIN_MM + column * PRECUT_PITCH_X_MM
            body.append(
                f'<use href="#radDadQrStickerV9" '
                f'xlink:href="#radDadQrStickerV9" x="{_fmt(x)}" y="{_fmt(y)}"/>'
            )
    return _svg_document(
        LETTER_WIDTH_MM, LETTER_HEIGHT_MM, definition, body
    )


def _handcut_positions_mm() -> Iterable[tuple[float, float]]:
    for row in range(HANDCUT_ROWS):
        top = HANDCUT_TOP_EDGE_MM + row * HANDCUT_PITCH_MM
        for column in range(HANDCUT_COLUMNS):
            left = HANDCUT_LEFT_EDGE_MM + column * HANDCUT_PITCH_MM
            yield left, top


def _handcut_svg(matrix: tuple[tuple[int, ...], ...]) -> str:
    definition = _sticker_svg_definition(matrix)
    body: list[str] = [
        (
            '<text x="107.95" y="5.5" text-anchor="middle" '
            'font-family="Arial,Helvetica,sans-serif" font-size="2.8" '
            'font-weight="700" fill="#000000">'
            'PRINT AT 100% / ACTUAL SIZE - 1 INCH CIRCLES</text>'
        )
    ]
    tick_gap = 1.016  # 0.04 inch outside the circle.
    tick_length = 1.524  # 0.06-inch crop tick.
    radius = STICKER_DIAMETER_MM / 2
    stroke = 0.15

    for left, top in _handcut_positions_mm():
        center_x = left + radius
        center_y = top + radius
        body.append(
            f'<use href="#radDadQrStickerV9" '
            f'xlink:href="#radDadQrStickerV9" x="{_fmt(left)}" '
            f'y="{_fmt(top)}"/>'
        )
        body.extend(
            (
                (
                    f'<line x1="{_fmt(center_x)}" '
                    f'y1="{_fmt(top - tick_gap - tick_length)}" '
                    f'x2="{_fmt(center_x)}" y2="{_fmt(top - tick_gap)}" '
                    f'stroke="#000000" stroke-width="{_fmt(stroke)}"/>'
                ),
                (
                    f'<line x1="{_fmt(center_x)}" '
                    f'y1="{_fmt(top + STICKER_DIAMETER_MM + tick_gap)}" '
                    f'x2="{_fmt(center_x)}" '
                    f'y2="{_fmt(top + STICKER_DIAMETER_MM + tick_gap + tick_length)}" '
                    f'stroke="#000000" stroke-width="{_fmt(stroke)}"/>'
                ),
                (
                    f'<line x1="{_fmt(left - tick_gap - tick_length)}" '
                    f'y1="{_fmt(center_y)}" x2="{_fmt(left - tick_gap)}" '
                    f'y2="{_fmt(center_y)}" stroke="#000000" '
                    f'stroke-width="{_fmt(stroke)}"/>'
                ),
                (
                    f'<line x1="{_fmt(left + STICKER_DIAMETER_MM + tick_gap)}" '
                    f'y1="{_fmt(center_y)}" '
                    f'x2="{_fmt(left + STICKER_DIAMETER_MM + tick_gap + tick_length)}" '
                    f'y2="{_fmt(center_y)}" stroke="#000000" '
                    f'stroke-width="{_fmt(stroke)}"/>'
                ),
            )
        )
    return _svg_document(
        LETTER_WIDTH_MM, LETTER_HEIGHT_MM, definition, body
    )


def _precut_raster(tile: Any) -> Any:
    page = Image.new(
        "1",
        (_mm_to_px(LETTER_WIDTH_MM), _mm_to_px(LETTER_HEIGHT_MM)),
        color=_WHITE,
    )
    left_margin = _mm_to_px(PRECUT_LEFT_MARGIN_MM)
    top_margin = _mm_to_px(PRECUT_TOP_MARGIN_MM)
    pitch_x = _mm_to_px(PRECUT_PITCH_X_MM)
    pitch_y = _mm_to_px(PRECUT_PITCH_Y_MM)
    for row in range(PRECUT_ROWS):
        for column in range(PRECUT_COLUMNS):
            page.paste(
                tile,
                (left_margin + column * pitch_x, top_margin + row * pitch_y),
            )
    return page


def _handcut_raster(tile: Any) -> Any:
    page = Image.new(
        "1",
        (_mm_to_px(LETTER_WIDTH_MM), _mm_to_px(LETTER_HEIGHT_MM)),
        color=_WHITE,
    )
    draw = ImageDraw.Draw(page)
    title_font = _font(42, bold=True)
    _centered_text(
        draw,
        page.width // 2,
        70,
        "PRINT AT 100% / ACTUAL SIZE - 1 INCH CIRCLES",
        title_font,
    )

    tick_gap = _mm_to_px(1.016)
    tick_length = _mm_to_px(1.524)
    tick_width = max(2, _mm_to_px(0.15))
    diameter = tile.width
    radius = diameter // 2

    for left_mm, top_mm in _handcut_positions_mm():
        left = _mm_to_px(left_mm)
        top = _mm_to_px(top_mm)
        center_x = left + radius
        center_y = top + radius
        page.paste(tile, (left, top))
        draw.line(
            (
                center_x,
                top - tick_gap - tick_length,
                center_x,
                top - tick_gap,
            ),
            fill=_BLACK,
            width=tick_width,
        )
        draw.line(
            (
                center_x,
                top + diameter + tick_gap,
                center_x,
                top + diameter + tick_gap + tick_length,
            ),
            fill=_BLACK,
            width=tick_width,
        )
        draw.line(
            (
                left - tick_gap - tick_length,
                center_y,
                left - tick_gap,
                center_y,
            ),
            fill=_BLACK,
            width=tick_width,
        )
        draw.line(
            (
                left + diameter + tick_gap,
                center_y,
                left + diameter + tick_gap + tick_length,
                center_y,
            ),
            fill=_BLACK,
            width=tick_width,
        )
    return page


def _calibration_raster(tile: Any) -> Any:
    page = Image.new(
        "1",
        (_mm_to_px(LETTER_WIDTH_MM), _mm_to_px(LETTER_HEIGHT_MM)),
        color=_WHITE,
    )
    draw = ImageDraw.Draw(page)
    title = _font(92, bold=True)
    heading = _font(52, bold=True)
    body = _font(43)

    draw.text((300, 240), "RAD DAD QR PRINT CALIBRATION", fill=_BLACK, font=title)
    draw.text(
        (300, 390),
        "PRINT AT 100% / ACTUAL SIZE. DISABLE FIT OR SHRINK.",
        fill=_BLACK,
        font=heading,
    )
    draw.text(
        (300, 500),
        "Measure both targets, then scan the sample before printing a full sheet.",
        fill=_BLACK,
        font=body,
    )

    one_inch = DPI
    square_left = 500
    square_top = 1050
    draw.rectangle(
        (
            square_left,
            square_top,
            square_left + one_inch,
            square_top + one_inch,
        ),
        outline=_BLACK,
        width=5,
    )
    draw.text(
        (square_left + one_inch + 100, square_top + 210),
        "OUTSIDE EDGE MUST MEASURE\nEXACTLY 1.000 INCH / 25.4 MM",
        fill=_BLACK,
        font=heading,
        spacing=18,
    )

    bar_left = 500
    bar_y = 2100
    bar_length = _mm_to_px(50.0)
    draw.line(
        (bar_left, bar_y, bar_left + bar_length, bar_y),
        fill=_BLACK,
        width=6,
    )
    draw.line(
        (bar_left, bar_y - 55, bar_left, bar_y + 55),
        fill=_BLACK,
        width=6,
    )
    draw.line(
        (bar_left + bar_length, bar_y - 55, bar_left + bar_length, bar_y + 55),
        fill=_BLACK,
        width=6,
    )
    draw.text(
        (bar_left, bar_y + 100),
        "END TO END MUST MEASURE EXACTLY 50.0 MM",
        fill=_BLACK,
        font=heading,
    )

    sample_left = 2950
    sample_top = 1000
    page.paste(tile, (sample_left, sample_top))
    _centered_text(
        draw,
        sample_left + tile.width // 2,
        sample_top - 120,
        "SCAN TEST",
        heading,
    )
    _centered_text(
        draw,
        sample_left + tile.width // 2,
        sample_top + tile.height + 90,
        "https://raddadband.com/tap/",
        body,
    )

    notes_y = 2850
    notes = (
        "PASS CHECKLIST",
        "1. The 1-inch square measures exactly 1.000 inch / 25.4 mm.",
        "2. The metric bar measures exactly 50.0 mm.",
        "3. The QR opens https://raddadband.com/tap/ from two different phones.",
        "4. Black areas are solid black; white areas are clean white; no scaling or gray.",
        "5. Cut outside the black circle and keep tape seams away from the QR square.",
    )
    for index, line in enumerate(notes):
        draw.text(
            (500, notes_y + index * 125),
            line,
            fill=_BLACK,
            font=heading if index == 0 else body,
        )

    spec_y = 3900
    draw.rectangle((500, spec_y, 4600, spec_y + 600), outline=_BLACK, width=5)
    specs = (
        "PRODUCTION SPECIFICATION",
        "Sticker: 1.000 inch / 25.4 mm round",
        "QR field: 16.5 mm square including four-module quiet zone",
        "Artwork: one-bit black and white at 600 DPI",
        "Destination: https://raddadband.com/tap/",
    )
    for index, line in enumerate(specs):
        draw.text(
            (575, spec_y + 65 + index * 100),
            line,
            fill=_BLACK,
            font=heading if index == 0 else body,
        )
    return page


def write_qr_artwork_v9(output_dir: str | Path) -> dict[str, Path]:
    """Write all v9 QR production masters and return their paths.

    The destination directory is created when needed. Existing files with the
    same names are replaced atomically enough for normal local production use.
    No model geometry or other repository files are modified.
    """

    _require_pillow()
    matrix = _matrix_from_v8()
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    paths = {
        "individual_svg": output / "Rad_Dad_QR_1IN_VENDOR_MASTER.svg",
        "individual_png": output / "Rad_Dad_QR_1IN_VENDOR_MASTER_600DPI.png",
        "individual_pdf": output / "Rad_Dad_QR_1IN_VENDOR_MASTER.pdf",
        "precut_63up_svg": output
        / "Rad_Dad_QR_AVERY_6450_OL1025_63UP_US_LETTER.svg",
        "precut_63up_png": output
        / "Rad_Dad_QR_AVERY_6450_OL1025_63UP_US_LETTER_600DPI.png",
        "precut_63up_pdf": output
        / "Rad_Dad_QR_AVERY_6450_OL1025_63UP_US_LETTER.pdf",
        "fedex_48up_svg": output
        / "Rad_Dad_QR_FEDEX_OFFICE_FULL_SHEET_48UP_US_LETTER.svg",
        "fedex_48up_png": output
        / "Rad_Dad_QR_FEDEX_OFFICE_FULL_SHEET_48UP_US_LETTER_600DPI.png",
        "fedex_48up_pdf": output
        / "Rad_Dad_QR_FEDEX_OFFICE_FULL_SHEET_48UP_US_LETTER.pdf",
        "calibration_png": output
        / "Rad_Dad_QR_PRINT_CALIBRATION_US_LETTER_600DPI.png",
        "calibration_pdf": output
        / "Rad_Dad_QR_PRINT_CALIBRATION_US_LETTER.pdf",
    }

    tile = _sticker_tile(matrix)
    precut = _precut_raster(tile)
    handcut = _handcut_raster(tile)
    calibration = _calibration_raster(tile)

    _write_text(paths["individual_svg"], _individual_svg(matrix))
    _save_png(tile, paths["individual_png"])
    _save_pdf(tile, paths["individual_pdf"])

    _write_text(paths["precut_63up_svg"], _precut_svg(matrix))
    _save_png(precut, paths["precut_63up_png"])
    _save_pdf(precut, paths["precut_63up_pdf"])

    _write_text(paths["fedex_48up_svg"], _handcut_svg(matrix))
    _save_png(handcut, paths["fedex_48up_png"])
    _save_pdf(handcut, paths["fedex_48up_pdf"])

    _save_png(calibration, paths["calibration_png"])
    _save_pdf(calibration, paths["calibration_pdf"])

    return paths
