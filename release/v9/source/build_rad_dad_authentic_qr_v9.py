"""Build the Rad Dad v9 Authenticity + black-and-white QR release.

V9 keeps the proven product envelopes, attachment openings, and printer intent
from v7 while replacing the model builders with the v9 authenticity pass.  It
then packages those models with high-contrast, one-inch QR sticker artwork.
The historical v7 and v8 release directories are never modified.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Iterable, Sequence
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

import build_rad_dad_micro_replica_v7 as legacy  # noqa: E402
import qr_artwork_v9  # noqa: E402
import v7_release_packaging as packaging  # noqa: E402
from media_micro_v9 import build_cassette_v9, build_floppy_v9, build_vhs_v9  # noqa: E402
from trailer_swift_v9_sculpt import build_trailer_swift_v9  # noqa: E402


RELEASE_NAME = "Rad Dad Retro Riot v9: Authenticity + QR Edition"
DEFAULT_OUTPUT = REPO_ROOT / "release" / "v9"
ARCHIVE_NAME = "Rad_Dad_Retro_Riot_v9_Authenticity_QR_Print_Pack.zip"
ALL_FOUR_STEM = "Rad_Dad_Retro_Riot_v9_ALL_FOUR"
SUPPORT_PROJECT_STEM = f"{ALL_FOUR_STEM}_A1_MINI_0.4_TREE_SUPPORT_PROJECT"
TAP_URL = "https://raddadband.com/tap/"

PRODUCT_UPDATES = {
    "cassette": {
        "artifact_stem": "Rad_Dad_Cassette_v38",
        "display_name": "Rad Dad Compact Cassette v38 Authentic Edge",
        "product_version": "v38",
        "source_builder": "media_micro_v9.build_cassette_v9",
        "nfc_location": "flat rear 1-inch QR sticker landing",
    },
    "floppy": {
        "artifact_stem": "Rad_Dad_Floppy_v20",
        "display_name": "Rad Dad 3.5-Inch Floppy v20 Authentic Rear",
        "product_version": "v20",
        "source_builder": "media_micro_v9.build_floppy_v9",
        "nfc_location": "rear faux-hub 1-inch QR sticker landing",
    },
    "vhs": {
        "artifact_stem": "Rad_Dad_Mini_VHS_v5",
        "display_name": "Rad Dad Mini VHS v5 Authentic Shell",
        "product_version": "v5",
        "source_builder": "media_micro_v9.build_vhs_v9",
        "nfc_location": "central rear 1-inch QR sticker landing",
    },
    "trailer_swift": {
        "artifact_stem": "Trailer_Swift_v9_Signature_Punk_QR",
        "display_name": "Trailer Swift v9 Signature Punk Collectible",
        "product_version": "v9",
        "source_builder": "trailer_swift_v9_sculpt.build_trailer_swift_v9",
        "nfc_location": "underside 1-inch QR sticker landing",
    },
}


def _atomic_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
    return path


def _write_json(path: Path, value: object) -> Path:
    return _atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _configure_geometry_builder() -> None:
    products = tuple(
        replace(product, **PRODUCT_UPDATES[product.key]) for product in legacy.PRODUCTS
    )
    legacy.PRODUCTS = products
    legacy.PRODUCT_BY_KEY = {product.key: product for product in products}
    legacy.RELEASE_NAME = RELEASE_NAME
    legacy.ARCHIVE_NAME = "Rad_Dad_v9_Geometry_Source.zip"
    legacy.ALL_FOUR_STEM = ALL_FOUR_STEM
    legacy.build_cassette_v7 = build_cassette_v9
    legacy.build_floppy_v7 = build_floppy_v9
    legacy.build_vhs_v7 = build_vhs_v9
    legacy.build_trailer_swift_v7 = build_trailer_swift_v9


def _copy_geometry(source: Path, output: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for directory in ("3mf", "stl"):
        target = output / directory
        target.mkdir(parents=True, exist_ok=True)
        for path in sorted((source / directory).glob("*")):
            if not path.is_file() or path.name == ".DS_Store":
                continue
            destination = target / path.name
            shutil.copyfile(path, destination)
            hashes[destination.relative_to(output).as_posix()] = _sha256(destination)

    preview_target = output / "previews"
    preview_target.mkdir(parents=True, exist_ok=True)
    for path in sorted((source / "previews").glob("*.png")):
        # The legacy back cards contain NFC-specific captions. V9 keeps the
        # geometry evidence in QA and ships only caption-correct front/detail
        # cards until a physical QR sticker has been applied.
        if "_BACK" in path.name:
            continue
        shutil.copyfile(path, preview_target / path.name)

    qa_target = output / "qa" / "geometry_evidence"
    qa_target.mkdir(parents=True, exist_ok=True)
    for path in sorted((source / "qa").glob("*.json")):
        shutil.copyfile(path, qa_target / path.name)
    return hashes


def _write_support_ready_project(
    output: Path, geometry_hashes: dict[str, str]
) -> Path:
    """Add the proven A1 mini tree-support profile to the v9 all-four model."""

    source = output / "3mf" / f"{ALL_FOUR_STEM}_MODEL_ONLY.3mf"
    target = output / "3mf" / f"{SUPPORT_PROJECT_STEM}.3mf"
    baseline = (
        REPO_ROOT
        / "release"
        / "v7"
        / "3mf"
        / "Rad_Dad_Retro_Riot_v7_ALL_FOUR_A1_MINI_0.4_PROJECT.3mf"
    )
    if not source.is_file() or not baseline.is_file():
        raise RuntimeError("Support-ready project inputs are missing")

    with zipfile.ZipFile(baseline) as archive:
        settings = json.loads(
            archive.read("Metadata/project_settings.config").decode("utf-8")
        )
    settings.update(
        {
            "enable_support": "1",
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

    shutil.copyfile(source, target)
    with zipfile.ZipFile(target, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=2, sort_keys=True) + "\n",
        )
    geometry_hashes[target.relative_to(output).as_posix()] = _sha256(target)
    return target


def _find_artwork(output: Path, marker: str, suffix: str = ".pdf") -> Path:
    matches = sorted(
        path
        for path in (output / "guides" / "qr_stickers").glob(f"*{suffix}")
        if marker.upper() in path.name.upper()
    )
    if not matches:
        raise RuntimeError(f"QR artwork is missing a {marker!r} {suffix} file")
    return matches[0]


def _write_release_documents(output: Path, geometry_hashes: dict[str, str]) -> None:
    guides = output / "guides"
    qa = output / "qa"
    guides.mkdir(parents=True, exist_ok=True)
    qa.mkdir(parents=True, exist_ok=True)

    vendor_pdf = _find_artwork(output, "VENDOR")
    sheet_63 = _find_artwork(output, "63UP")
    fedex_sheet = _find_artwork(output, "FEDEX")
    calibration = _find_artwork(output, "CALIBRATION")
    red_vendor_pdf = _find_artwork(output, "RED_1IN")
    red_sheet_63 = _find_artwork(output, "RED_AVERY")
    red_fedex_sheet = _find_artwork(output, "RED_FEDEX")
    red_calibration = _find_artwork(output, "RED_PRINT_CALIBRATION")

    rel = lambda path: path.relative_to(output).as_posix()
    readme = f"""# {RELEASE_NAME}

**AUTHENTIC LITTLE OBJECTS. LOUD BAND. ONE EASY SCAN.**

This release restores the physical cues that make the cassette, floppy disk,
and VHS recognizable while keeping the Trailer Swift collectible funny rather
than frightening. Every exterior envelope and attachment opening remains the
same size as v7. The NFC workflow is replaced by a visible, black-and-white,
one-inch QR sticker that opens `{TAP_URL}`.

## Start here

| Need | File |
|---|---|
| Print all four together | `3mf/{ALL_FOUR_STEM}_MODEL_ONLY.3mf` |
| Print all four with Trailer Swift supports preset | `3mf/{SUPPORT_PROJECT_STEM}.3mf` |
| Print on 63-up pre-cut stock | [{sheet_63.name}]({rel(sheet_63)}) |
| Print at FedEx Office on adhesive paper | [{fedex_sheet.name}]({rel(fedex_sheet)}) |
| Send one design to a sticker vendor | [{vendor_pdf.name}]({rel(vendor_pdf)}) |
| Check printer scaling first | [{calibration.name}]({rel(calibration)}) |
| Print without black ink, using pure red | [{red_sheet_63.name}]({rel(red_sheet_63)}) |
| Print a red full sheet for hand cutting | [{red_fedex_sheet.name}]({rel(red_fedex_sheet)}) |
| Send the red master to a vendor | [{red_vendor_pdf.name}]({rel(red_vendor_pdf)}) |
| Calibrate and scan-test red first | [{red_calibration.name}]({rel(red_calibration)}) |
| Follow the physical acceptance gate | [Physical QC checklist](qa/PHYSICAL_QC_CHECKLIST.md) |

## V9 authenticity changes

- Cassette: five real lower-edge transport bays align with the five front
  transport positions. A continuous rear skin and substantial ribs retain
  keychain durability without restoring the previous solid toy-like edge.
- Floppy: rear spindle, shutter-track, shell-seam, and write-protect cues frame
  the functional QR landing; `RAD DAD` and `3.69 MB` remain on the front label.
- VHS: rear reel-drive, shell, door, and fastener cues join the front tape door,
  windows, hubs, `RAD DAD`, and `T-369` details.
- Trailer Swift: the stable solid base and underside QR landing remain, while
  the face reads as a playful singing punk character rather than an angry one.

## QR specification

- Finished sticker: 25.4 mm / 1.000 inch round
- QR field: 16.5 mm, black modules on pure white
- Matrix: 29 x 29 modules with error correction Q
- Quiet zone: four complete modules on every side
- Module pitch: approximately 0.446 mm
- Standard artwork: pure black on white
- Color-cartridge fallback: pure process red `#FF0000` on white
- Artwork: vector plus lossless 600 DPI raster/PDF production files
- Print scaling: Actual Size / 100%; never Fit or Scale to Page

Black remains the preferred production color. Use the red files when black ink
is unavailable, select color printing rather than grayscale, and approve them
only after the red calibration code scans from two phones.

## Physical-production rule

Print one of each model and one ordinary-paper QR proof before producing a
batch. A finished item passes only when the installed QR opens the Rad Dad tap
page with the normal camera on both iPhone and Android in indoor and outdoor
light. The digital files cannot substitute for a physical print and scan test.
"""
    _atomic_text(output / "README.md", readme)

    fedex = f"""# Print the QR stickers at FedEx Office

## File to bring

Use `{rel(fedex_sheet)}` for the standard black full sheet. If black ink is
unavailable, use `{rel(red_fedex_sheet)}` and first print
`{rel(red_calibration)}`. Both layouts cut or punch into one-inch circles.
Bring `{rel(calibration)}` as the standard black proof page.

## Counter instructions

1. Print on US Letter, white matte adhesive label stock.
2. Print black on white, or use the supplied pure-red fallback on white. Do not
   use grayscale, clear, metallic, holographic, or dark stock.
3. Select Actual Size / 100%. Disable Fit, Shrink, Scale to Fit, borderless
   enlargement, and automatic rotation.
4. Keep the PDF at its native resolution. Do not screenshot or resave it.
5. Print one calibration proof before the sticker sheet.
6. Confirm the calibration circle is exactly 25.4 mm and its reference square
   is exactly 50.0 mm.
7. Scan the proof with an iPhone and Android phone before approving the sheet.
8. Ask whether the store can circle-cut at exactly one inch. If not, use a
   one-inch craft punch or cut just outside the supplied circular guide.

Matte stock is preferred because it reduces glare. If only glossy adhesive
stock is available, approve it only after scanning under bright overhead light.
"""
    _atomic_text(guides / "PRINT_AT_FEDEX_OFFICE.md", fedex)

    design_notes = """# V9 authenticity design notes

The visual hierarchy is intentional: each item must read as its real-world
reference before the viewer notices the Rad Dad branding or QR function.

The cassette transport features are open to the top/edge rather than capped by
hidden bridge ceilings. The retained rear skin is divisible into ordinary
0.20 mm layers, and the ribs between transport bays carry edge loads.

The floppy and VHS rear details use shallow engravings outside the QR quiet
landing. They should survive ordinary slicing without making the rear surface
rock on the bed. The QR sticker remains centered and fully supported.

Trailer Swift remains a one-piece desk collectible. Friendly facial changes
avoid thin standalone parts and preserve the support strategy and stable base.
"""
    _atomic_text(guides / "AUTHENTICITY_DESIGN_NOTES.md", design_notes)

    qc = f"""# V9 physical quality-control checklist

## Sliced model

- [ ] Overall dimensions match the prior approved envelope.
- [ ] No unsupported floating islands appear in layer preview.
- [ ] Cassette transport bays are visibly open at the lower edge and align
      with the five front transport positions.
- [ ] Cassette lower ribs and rear skin remain continuous.
- [ ] Floppy reads correctly from front, edge, and rear.
- [ ] VHS reads correctly from front, edge, and rear.
- [ ] Trailer Swift face reads playful, not angry or frightening.
- [ ] Every 6 mm media eyelet accepts the thickest production split ring.

## Printed object

- [ ] First layer is complete with no lifted edge or underside tear-out.
- [ ] Fine text and molded details are readable at normal hand distance.
- [ ] No transport rib, eyelet root, guitar, hair spike, or base feature is loose.
- [ ] Trailer Swift stands without rocking.
- [ ] Representative key carry, twist, and drop checks pass.

## QR print and installation

- [ ] Calibration circle measures 25.4 mm and reference square measures 50 mm.
- [ ] QR modules are square, solid black, and surrounded by uninterrupted white.
- [ ] If using the fallback, modules are solid pure red on clean white and the
      printer is set to color rather than grayscale.
- [ ] Top, center, and bottom sheet samples scan before cutting.
- [ ] Sticker is centered, flat, clean, and fully adhered.
- [ ] Installed QR opens `{TAP_URL}` on iPhone and Android.
- [ ] Indoor light, bright overhead light, and daylight all pass.
- [ ] Final scan passes again after a 24-hour adhesive cure.
"""
    _atomic_text(qa / "PHYSICAL_QC_CHECKLIST.md", qc)

    _write_json(
        qa / "AUTHENTICITY_SPEC.json",
        {
            "schema": "rad-dad-authenticity-v9",
            "release": RELEASE_NAME,
            "tap_url": TAP_URL,
            "printer_target": "Bambu Lab A1 mini / 0.4 mm nozzle",
            "geometry_policy": "same external envelopes and attachment openings as v7",
            "qr": {
                "label_diameter_mm": 25.4,
                "render_square_mm": 16.5,
                "quiet_zone_modules": 4,
                "error_correction": "Q",
                "preferred_colors": ["#000000", "#FFFFFF"],
                "color_cartridge_fallback": ["#FF0000", "#FFFFFF"],
            },
            "geometry_sha256": geometry_hashes,
            "physical_validation": "required before batch production",
        },
    )


def _copy_source_snapshot(output: Path) -> None:
    source_output = output / "source"
    source_output.mkdir(parents=True, exist_ok=True)
    for name in (
        "media_micro_v9.py",
        "trailer_swift_v9_sculpt.py",
        "qr_artwork_v9.py",
        "build_rad_dad_authentic_qr_v9.py",
    ):
        shutil.copyfile(REPO_ROOT / "src" / name, source_output / name)


def _write_sha256s(output: Path, excluded: Iterable[Path]) -> Path:
    excluded_resolved = {path.resolve() for path in excluded}
    rows = []
    for path in sorted(output.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file() and path.resolve() not in excluded_resolved:
            rows.append(f"{_sha256(path)}  {path.relative_to(output).as_posix()}")
    return _atomic_text(output / "SHA256SUMS.txt", "\n".join(rows) + "\n")


def build_release(output: Path = DEFAULT_OUTPUT, bambu_mode: str = "auto") -> dict[str, Path]:
    output = output.expanduser().resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    _configure_geometry_builder()
    with tempfile.TemporaryDirectory(prefix="rad-dad-v9-geometry-") as temporary:
        geometry_root = Path(temporary) / "release"
        geometry_result = legacy.build_release(geometry_root, bambu_mode=bambu_mode)
        geometry_hashes = _copy_geometry(geometry_root, output)
        support_project = _write_support_ready_project(output, geometry_hashes)
        _write_json(
            output / "qa" / "GEOMETRY_BUILD_STATUS.json",
            {
                "bambu_required_satisfied": geometry_result.bambu_required_satisfied,
                "packaging_load_mode": geometry_result.packaging_load_mode,
                "source_build": RELEASE_NAME,
            },
        )

    qr_artwork_v9.write_qr_artwork_v9(output / "guides" / "qr_stickers")
    _write_release_documents(output, geometry_hashes)
    _copy_source_snapshot(output)

    archive = output / ARCHIVE_NAME
    sidecar = archive.with_name(archive.name + ".sha256")
    manifest = output / "MANIFEST.json"
    sums = output / "SHA256SUMS.txt"
    _write_sha256s(output, (archive, sidecar, manifest, sums))
    packaging.write_release_manifest(
        output,
        release_name=RELEASE_NAME,
        output_path=manifest,
        exclude=(archive, sidecar),
        metadata={
            "collection": "Authenticity + QR Edition",
            "interaction": "visible black-and-white 1-inch QR sticker",
            "destination_url": TAP_URL,
            "geometry_changed_from_v7": True,
            "external_envelopes_changed_from_v7": False,
            "printer_target": "Bambu Lab A1 mini / 0.4 mm nozzle",
            "physical_validation": "required before batch production",
        },
    )
    packaging.create_deterministic_zip(
        output,
        archive,
        archive_prefix="Rad_Dad_Retro_Riot_v9_Authenticity_QR_Edition",
        exclude=(archive, sidecar),
    )
    packaging.write_sha256_sidecar(archive)

    return {
        "release": output,
        "archive": archive,
        "all_four": output / "3mf" / f"{ALL_FOUR_STEM}_MODEL_ONLY.3mf",
        "support_project": support_project,
        "sticker_63up": _find_artwork(output, "63UP"),
        "sticker_fedex": _find_artwork(output, "FEDEX"),
        "calibration": _find_artwork(output, "CALIBRATION"),
        "manifest": manifest,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--bambu-mode",
        choices=("auto", "required", "skip"),
        default="auto",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = build_release(args.output, bambu_mode=args.bambu_mode)
    print(f"Release: {result['release']}")
    print(f"Print pack: {result['archive']}")
    print(f"All four: {result['all_four']}")
    print(f"Support-ready project: {result['support_project']}")
    print(f"63-up QR sheet: {result['sticker_63up']}")
    print(f"FedEx QR sheet: {result['sticker_fedex']}")
    print(f"Calibration: {result['calibration']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
