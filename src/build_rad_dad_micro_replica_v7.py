#!/usr/bin/env python3
"""Build the complete Rad Dad Micro Replicas v7 release.

This is the deterministic top-level orchestrator for the v7 product family.
It delegates geometry and release-format concerns to the companion modules,
keeps model-only Core 3MF files unmistakably labeled, and creates verified
Bambu Studio projects only when the optional Bambu helper succeeds.

Public API
----------
``build_release(output=DEFAULT_OUTPUT, bambu_mode="auto")``
    Build the complete release and return a :class:`BuildResult`.

CLI examples
------------
``python3 src/build_rad_dad_micro_replica_v7.py --output release/v7 --bambu``
``python3 src/build_rad_dad_micro_replica_v7.py --skip-bambu``
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import shutil
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import trimesh

from media_micro_v7 import build_cassette_v7, build_floppy_v7, build_vhs_v7
from trailer_swift_v7_sculpt import build_trailer_swift_v7


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "release" / "v7"
RELEASE_NAME = "Rad Dad Retro Riot v7: Micro Replica Edition"
ARCHIVE_NAME = "Rad_Dad_Retro_Riot_v7_Micro_Replica_Print_Pack.zip"
ALL_FOUR_STEM = "Rad_Dad_Retro_Riot_v7_ALL_FOUR"
PLATE_SIZE_MM = (180.0, 180.0)
PLATE_MARGIN_MM = 10.0
MINIMUM_PLATE_SPACING_MM = 10.0
ENVELOPE_TOLERANCE_MM = 0.05


@dataclass(frozen=True)
class ProductSpec:
    key: str
    artifact_stem: str
    display_name: str
    product_version: str
    source_builder: str
    exact_envelope_mm: tuple[float, float, float]
    eyelet_opening_mm: float | None
    nfc_tag_diameter_mm: float
    nfc_protected_zone_diameter_mm: float
    nfc_location: str
    support_intent: str
    orientation: str
    capacity_easter_egg: str | None
    easter_egg_location: str | None
    bambu_product_kind: str
    preview_accent: str


@dataclass(frozen=True)
class BuildResult:
    output: Path
    archive: Path
    archive_checksum: Path
    manifest: Path
    sha256sums: Path
    bambu_status: Path
    bambu_required_satisfied: bool
    packaging_load_mode: str


PRODUCTS: tuple[ProductSpec, ...] = (
    ProductSpec(
        key="cassette",
        artifact_stem="Rad_Dad_Cassette_v37",
        display_name="Rad Dad Compact Cassette v37",
        product_version="v37",
        source_builder="media_micro_v7.build_cassette_v7",
        exact_envelope_mm=(58.162, 30.260, 6.685),
        eyelet_opening_mm=6.0,
        nfc_tag_diameter_mm=25.0,
        nfc_protected_zone_diameter_mm=26.0,
        nfc_location="flat rear landing",
        support_intent="off",
        orientation="flat",
        capacity_easter_egg="C-69",
        easter_egg_location="small lower-right cassette marking",
        bambu_product_kind="cassette",
        preview_accent="#A6EF12",
    ),
    ProductSpec(
        key="floppy",
        artifact_stem="Rad_Dad_Floppy_v19",
        display_name="Rad Dad 3.5-Inch Floppy v19",
        product_version="v19",
        source_builder="media_micro_v7.build_floppy_v7",
        exact_envelope_mm=(44.360, 36.916, 4.130),
        eyelet_opening_mm=6.0,
        nfc_tag_diameter_mm=25.0,
        nfc_protected_zone_diameter_mm=26.0,
        nfc_location="rear faux drive-hub landing",
        support_intent="off",
        orientation="flat",
        capacity_easter_egg="3.69 MB",
        easter_egg_location="front writable label",
        bambu_product_kind="floppy",
        preview_accent="#1CB5F4",
    ),
    ProductSpec(
        key="vhs",
        artifact_stem="Rad_Dad_Mini_VHS_v4",
        display_name="Rad Dad Mini VHS v4",
        product_version="v4",
        source_builder="media_micro_v7.build_vhs_v7",
        exact_envelope_mm=(65.800, 31.900, 7.000),
        eyelet_opening_mm=6.0,
        nfc_tag_diameter_mm=25.0,
        nfc_protected_zone_diameter_mm=26.0,
        nfc_location="flat rear landing",
        support_intent="off",
        orientation="flat",
        capacity_easter_egg="T-369",
        easter_egg_location="lower center label",
        bambu_product_kind="vhs",
        preview_accent="#FF3476",
    ),
    ProductSpec(
        key="trailer_swift",
        artifact_stem="Trailer_Swift_v5_Bobblehead_NFC",
        display_name="Trailer Swift v5 Punk Desk Toy",
        product_version="v5",
        source_builder="trailer_swift_v7_sculpt.build_trailer_swift_v7",
        exact_envelope_mm=(45.000, 45.000, 64.400),
        eyelet_opening_mm=None,
        nfc_tag_diameter_mm=25.0,
        nfc_protected_zone_diameter_mm=27.0,
        nfc_location="underside of circular display base",
        support_intent="organic, build plate only",
        orientation="upright",
        capacity_easter_egg=None,
        easter_egg_location=None,
        bambu_product_kind="trailer_swift",
        preview_accent="#FFB000",
    ),
)

PRODUCT_BY_KEY = {product.key: product for product in PRODUCTS}

# Fixed centers create an intentionally airy 2 x 2 A1 Mini plate. The actual
# mesh bounds are checked after placement, so future geometry drift cannot
# silently reduce spacing below the product requirement.
PLATE_CENTERS_MM: Mapping[str, tuple[float, float]] = {
    "cassette": (45.0, 35.0),
    "vhs": (130.0, 35.0),
    "floppy": (45.0, 110.0),
    "trailer_swift": (125.0, 110.0),
}


def _load_packaging_module() -> tuple[Any, str]:
    """Import the checked-in packaging helpers without source rewriting."""

    return importlib.import_module("v7_release_packaging"), "direct-import"


def _resolve_output(output: str | Path) -> Path:
    candidate = Path(output).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def _reset_output(output: Path) -> None:
    protected = {
        Path("/").resolve(),
        Path.home().resolve(),
        REPO_ROOT.resolve(),
        (REPO_ROOT / "src").resolve(),
        (REPO_ROOT / "release").resolve(),
    }
    if output in protected:
        raise ValueError(f"Refusing to replace protected path: {output}")
    if output.exists():
        if output.is_symlink() or not output.is_dir():
            raise ValueError(f"Release output must be a normal directory: {output}")
        shutil.rmtree(output)


def _build_models() -> dict[str, trimesh.Trimesh]:
    return {
        "cassette": build_cassette_v7(),
        "floppy": build_floppy_v7(),
        "vhs": build_vhs_v7(),
        "trailer_swift": build_trailer_swift_v7(),
    }


def _validate_models(models: Mapping[str, trimesh.Trimesh]) -> None:
    if set(models) != set(PRODUCT_BY_KEY):
        raise RuntimeError("The v7 model set is incomplete or contains unknown products.")
    for key in sorted(models):
        mesh = models[key]
        product = PRODUCT_BY_KEY[key]
        dimensions = np.asarray(mesh.extents, dtype=float)
        expected = np.asarray(product.exact_envelope_mm, dtype=float)
        if not np.isfinite(np.asarray(mesh.vertices)).all():
            raise RuntimeError(f"{product.display_name} contains non-finite vertices.")
        if not bool(mesh.is_watertight):
            raise RuntimeError(f"{product.display_name} is not watertight.")
        if not bool(mesh.is_winding_consistent):
            raise RuntimeError(f"{product.display_name} has inconsistent winding.")
        if len(mesh.split(only_watertight=False)) != 1:
            raise RuntimeError(f"{product.display_name} is not one connected body.")
        if not np.allclose(
            dimensions,
            expected,
            atol=ENVELOPE_TOLERANCE_MM,
            rtol=0.0,
        ):
            raise RuntimeError(
                f"{product.display_name} envelope changed: "
                f"expected {expected.tolist()}, measured {dimensions.tolist()}."
            )
        if product.eyelet_opening_mm is not None and product.eyelet_opening_mm < 6.0:
            raise RuntimeError(f"{product.display_name} eyelet metadata is below 6 mm.")


def _placement_transform(
    mesh: trimesh.Trimesh,
    center_xy: tuple[float, float],
) -> np.ndarray:
    bounds = np.asarray(mesh.bounds, dtype=float)
    current_center = (bounds[0, :2] + bounds[1, :2]) / 2.0
    transform = np.eye(4, dtype=float)
    transform[:3, 3] = (
        center_xy[0] - current_center[0],
        center_xy[1] - current_center[1],
        -bounds[0, 2],
    )
    return transform


def _transformed_copy(mesh: trimesh.Trimesh, transform: np.ndarray) -> trimesh.Trimesh:
    result = mesh.copy()
    result.apply_transform(transform)
    return result


def _bounds_gap_xy(left: np.ndarray, right: np.ndarray) -> float:
    dx = max(float(left[0, 0] - right[1, 0]), float(right[0, 0] - left[1, 0]), 0.0)
    dy = max(float(left[0, 1] - right[1, 1]), float(right[0, 1] - left[1, 1]), 0.0)
    return math.hypot(dx, dy)


def _arrange_all_four(
    models: Mapping[str, trimesh.Trimesh],
) -> tuple[dict[str, np.ndarray], dict[str, trimesh.Trimesh], dict[str, Any]]:
    transforms: dict[str, np.ndarray] = {}
    placed: dict[str, trimesh.Trimesh] = {}
    for key in sorted(models):
        transform = _placement_transform(models[key], PLATE_CENTERS_MM[key])
        transforms[key] = transform
        placed[key] = _transformed_copy(models[key], transform)

    bounds = {key: np.asarray(mesh.bounds, dtype=float) for key, mesh in placed.items()}
    gaps: dict[str, float] = {}
    keys = sorted(placed)
    for index, left_key in enumerate(keys):
        for right_key in keys[index + 1 :]:
            gap = _bounds_gap_xy(bounds[left_key], bounds[right_key])
            gaps[f"{left_key}__{right_key}"] = round(gap, 6)
            if gap + 1e-9 < MINIMUM_PLATE_SPACING_MM:
                raise RuntimeError(
                    f"All-four plate gap is only {gap:.3f} mm between "
                    f"{left_key} and {right_key}."
                )

    all_minimum = np.vstack([item[0] for item in bounds.values()]).min(axis=0)
    all_maximum = np.vstack([item[1] for item in bounds.values()]).max(axis=0)
    if np.any(all_minimum[:2] < PLATE_MARGIN_MM - 1e-9) or np.any(
        all_maximum[:2] > np.asarray(PLATE_SIZE_MM) - PLATE_MARGIN_MM + 1e-9
    ):
        raise RuntimeError("The all-four layout violates the 10 mm plate margin.")

    metadata = {
        "schema": "rad-dad-a1-mini-plate-layout-v1",
        "plate_size_mm": list(PLATE_SIZE_MM),
        "minimum_required_spacing_mm": MINIMUM_PLATE_SPACING_MM,
        "minimum_actual_bounding_box_gap_mm": round(min(gaps.values()), 6),
        "plate_margin_mm": PLATE_MARGIN_MM,
        "combined_bounds_mm": {
            "minimum": [round(float(value), 6) for value in all_minimum],
            "maximum": [round(float(value), 6) for value in all_maximum],
        },
        "placements": {
            key: {
                "center_xy_mm": list(PLATE_CENTERS_MM[key]),
                "bounds_mm": {
                    "minimum": [round(float(value), 6) for value in bounds[key][0]],
                    "maximum": [round(float(value), 6) for value in bounds[key][1]],
                },
            }
            for key in sorted(placed)
        },
        "pairwise_bounding_box_gaps_mm": gaps,
        "note": (
            "The deterministic model-only plate guarantees these placements. "
            "Bambu Studio may auto-arrange a separately generated project."
        ),
    }
    return transforms, placed, metadata


def _build_print_intents(packaging: Any) -> dict[str, Any]:
    common = {
        "printer": "Bambu Lab A1 mini",
        "nozzle_mm": 0.4,
        "layer_height_mm": 0.16,
        "initial_layer_height_mm": 0.20,
        "wall_loops": 4,
        "top_layers": 5,
        "bottom_layers": 5,
        "infill_percent": 30,
        "infill_pattern": "gyroid",
    }
    intents: dict[str, Any] = {}
    for product in PRODUCTS:
        is_figure = product.key == "trailer_swift"
        intents[product.artifact_stem] = packaging.BambuPrintIntent(
            slug=product.artifact_stem,
            display_name=product.display_name,
            supports="organic" if is_figure else "off",
            support_on_build_plate_only=is_figure,
            orientation=product.orientation,
            **common,
        )
    intents[ALL_FOUR_STEM] = packaging.BambuPrintIntent(
        slug=ALL_FOUR_STEM,
        display_name="Rad Dad Micro Replicas v7 All-Four Plate",
        supports="organic",
        support_on_build_plate_only=True,
        orientation="mixed",
        **common,
    )
    return intents


def _finalize_print_intent_statuses(
    print_intents: Mapping[str, Any],
    bambu_status: Mapping[str, Any],
) -> dict[str, Any]:
    project_records = bambu_status.get("projects", {})
    if not isinstance(project_records, Mapping):
        project_records = {}

    finalized: dict[str, Any] = {}
    for stem, intent in print_intents.items():
        record = project_records.get(stem, {})
        if isinstance(record, Mapping):
            profile_status = str(
                record.get("status") or "postprocessing-status-unavailable"
            )
        else:
            profile_status = "postprocessing-status-unavailable"
        finalized[stem] = replace(intent, profile_status=profile_status)
    return finalized


def _write_json(path: Path, value: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="ascii",
    )
    return path


def _relative(path: str | Path, root: Path) -> str:
    return Path(path).resolve().relative_to(root.resolve()).as_posix()


def _product_metadata(models: Mapping[str, trimesh.Trimesh]) -> dict[str, Any]:
    keyring_centers = {
        "cassette": [27.0, 0.3],
        "floppy": [20.3, 0.0],
        "vhs": [30.8, -7.0],
    }
    products: dict[str, Any] = {}
    for product in PRODUCTS:
        measured = [round(float(value), 6) for value in models[product.key].extents]
        record: dict[str, Any] = {
            "artifact_stem": product.artifact_stem,
            "display_name": product.display_name,
            "source_builder": product.source_builder,
            "exact_envelope_mm": list(product.exact_envelope_mm),
            "measured_envelope_mm": measured,
            "one_color_print": True,
            "recognition_goal": "identifiable within two seconds without reading text",
            "nfc_landing": {
                "diameter_mm": product.nfc_tag_diameter_mm,
                "registration_zone_diameter_mm": product.nfc_protected_zone_diameter_mm,
                "flat": True,
                "location": product.nfc_location,
                "abrasion_protection": "clear nonmetal overlaminate required",
            },
            "support_intent": product.support_intent,
            "orientation": product.orientation,
            "capacity_easter_egg": product.capacity_easter_egg,
            "easter_egg_location": product.easter_egg_location,
            "bambu_product_kind": product.bambu_product_kind,
            "physical_validation": "required-before-batch-production",
        }
        if product.eyelet_opening_mm is not None:
            record["keyring"] = {
                "inner_diameter_mm": product.eyelet_opening_mm,
                "outer_diameter_mm": 12.0,
                "center_mm": keyring_centers[product.key],
                "axis": "z",
                "two_sided_entrance_chamfer": True,
                "maximum_protrusion_mm": 7.8,
            }
        products[product.key] = record
    return {
        "schema": "rad-dad-micro-replica-product-metadata-v1",
        "release": RELEASE_NAME,
        "design_language": "One-color, print-safe micro replicas of authentic media hardware",
        "printer_target": "Bambu Lab A1 mini with 0.4 mm nozzle",
        "nfc_overlay_stock": "non-metal paper or vinyl only",
        "nfc_abrasion_protection": "clear nonmetal overlaminate required for key carry",
        "products": products,
    }


def _write_easter_egg_guide(path: Path) -> Path:
    text = """# Capacity easter eggs

The three media replicas share one quiet `369` joke while staying faithful to
the labeling language of the original format.

| Replica | Mark | Why it belongs |
|---|---|---|
| Compact cassette | `C-69` | Styled like a cassette duration designation. |
| 3.5-inch floppy | `3.69 MB` | Styled like a disk capacity marking. |
| VHS | `T-369` | Styled like a VHS running-time or tape-grade mark. |
| Trailer Swift | None | The character and nameplate remain the entire joke. |

The marks are intentionally secondary. `RAD DAD` and the hardware silhouette
must remain readable first. Matching 25 mm NFC overlays repeat each media cue
without using foil, metallic ink, or metal-backed label stock.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")
    return path


def _render_previews(
    packaging: Any,
    layout: Any,
    models: Mapping[str, trimesh.Trimesh],
    placed: Mapping[str, trimesh.Trimesh],
) -> tuple[dict[str, Path], dict[str, Path], trimesh.Trimesh]:
    thumbnails: dict[str, Path] = {}
    preview_index: dict[str, Path] = {}
    for product in PRODUCTS:
        paths = packaging.render_preview_set(
            models[product.key],
            layout.previews,
            stem=product.artifact_stem,
            title=product.display_name,
            orientation=product.orientation,
            accent=product.preview_accent,
        )
        thumbnails[product.artifact_stem] = paths["front"]
        preview_index.update(
            {f"{product.artifact_stem}_{view}": path for view, path in paths.items()}
        )

    combined_mesh = trimesh.util.concatenate(
        tuple(placed[key] for key in sorted(placed))
    )
    all_four = packaging.render_preview_set(
        combined_mesh,
        layout.previews,
        stem=ALL_FOUR_STEM,
        title="Rad Dad Retro Riot v7 All-Four A1 Mini Plate",
        orientation="flat",
        accent="#A6EF12",
    )
    preview_index.update({f"{ALL_FOUR_STEM}_{view}": path for view, path in all_four.items()})
    return thumbnails, all_four, combined_mesh


def _create_bambu_projects(
    layout: Any,
    artifacts: Mapping[str, Mapping[str, Any]],
    output_root: Path,
    mode: str,
) -> tuple[dict[str, Path], dict[str, Any]]:
    project_paths: dict[str, Path] = {}
    status: dict[str, Any] = {
        "schema": "rad-dad-bambu-project-status-v1",
        "requested_mode": mode,
        "helper_importable": False,
        "projects": {},
        "fallback_policy": (
            "MODEL_ONLY files remain authoritative geometry when a verified "
            "Bambu project cannot be created."
        ),
        "determinism_note": (
            "Core 3MF, STL, manifests, and ZIP ordering are deterministic. "
            "Bambu project bytes may vary with the installed Bambu Studio version."
        ),
    }

    requested = [product.artifact_stem for product in PRODUCTS] + [ALL_FOUR_STEM]
    if mode == "skip":
        for stem in requested:
            status["projects"][stem] = {
                "status": "fallback-model-only",
                "reason": "Bambu generation explicitly skipped",
            }
        status["required_satisfied"] = True
        return project_paths, status

    try:
        bambu = importlib.import_module("bambu_project_v7")
        create_project = getattr(bambu, "create_bambu_project_3mf")
        if not callable(create_project):
            raise AttributeError("create_bambu_project_3mf is not callable")
        status["helper_importable"] = True
    except Exception as error:
        for stem in requested:
            status["projects"][stem] = {
                "status": "fallback-model-only",
                "reason": f"Bambu helper unavailable: {type(error).__name__}: {error}",
            }
        status["required_satisfied"] = mode != "required"
        return project_paths, status

    def attempt(
        stem: str,
        input_stls: Sequence[Path],
        product_kind: str,
        *,
        combined: bool = False,
    ) -> None:
        destination = layout.models_3mf / f"{stem}_A1_MINI_0.4_PROJECT.3mf"
        try:
            report = create_project(
                input_stls=input_stls,
                output_3mf=destination,
                product_kind=product_kind,
                combined=combined,
            )
            if not destination.is_file() or not bool(report.get("is_bambu_project")):
                raise RuntimeError("helper did not produce a verified Bambu project")
            project_paths[stem] = destination
            status["projects"][stem] = {
                "status": "verified-bambu-project",
                "file": _relative(destination, output_root),
                "matches_rad_dad_v7_base_profile": bool(
                    report.get("matches_rad_dad_v7_base_profile")
                ),
                "support_mode": report.get("support_mode"),
                "plate_count": report.get("plate_count"),
                "model_instance_count": report.get("model_instance_count"),
                "bambu_studio_version": report.get("bambu_studio_version"),
            }
        except Exception as error:
            destination.unlink(missing_ok=True)
            status["projects"][stem] = {
                "status": "fallback-model-only",
                "reason": f"{type(error).__name__}: {error}",
            }

    for product in PRODUCTS:
        stl_path = Path(artifacts[product.artifact_stem]["stl"])
        attempt(
            product.artifact_stem,
            [stl_path],
            product.bambu_product_kind,
        )

    all_stls = [Path(artifacts[product.artifact_stem]["stl"]) for product in PRODUCTS]
    attempt(ALL_FOUR_STEM, all_stls, "combined", combined=True)
    status["required_satisfied"] = mode != "required" or len(project_paths) == len(requested)
    status["verified_project_count"] = len(project_paths)
    status["requested_project_count"] = len(requested)
    return project_paths, status


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_sha256sums(output_root: Path, archive_path: Path) -> Path:
    destination = output_root / "SHA256SUMS.txt"
    excluded = {
        destination.resolve(),
        (output_root / "MANIFEST.json").resolve(),
        archive_path.resolve(),
        archive_path.with_name(archive_path.name + ".sha256").resolve(),
    }
    files = sorted(
        (
            path
            for path in output_root.rglob("*")
            if path.is_file() and path.resolve() not in excluded
        ),
        key=lambda path: path.relative_to(output_root).as_posix(),
    )
    lines = [
        f"{_sha256(path)}  {path.relative_to(output_root).as_posix()}" for path in files
    ]
    destination.write_text("\n".join(lines) + "\n", encoding="ascii")
    return destination


def build_release(
    output: str | Path = DEFAULT_OUTPUT,
    bambu_mode: str = "auto",
) -> BuildResult:
    """Build the complete v7 release without modifying any source files.

    ``bambu_mode`` accepts ``auto``, ``required``, or ``skip``. Auto mode tries
    the Bambu helper and records model-only fallbacks without failing the rest
    of the release. Required mode still creates the fallback release, but the
    returned result marks the Bambu requirement unsatisfied for the CLI exit.
    """

    if bambu_mode not in {"auto", "required", "skip"}:
        raise ValueError("bambu_mode must be 'auto', 'required', or 'skip'")

    output_root = _resolve_output(output)
    _reset_output(output_root)
    packaging, packaging_load_mode = _load_packaging_module()
    layout = packaging.create_release_layout(output_root)

    models = _build_models()
    _validate_models(models)
    transforms, placed, plate_metadata = _arrange_all_four(models)
    print_intents = _build_print_intents(packaging)

    thumbnails, all_four_previews, _ = _render_previews(
        packaging,
        layout,
        models,
        placed,
    )
    artifact_models = {
        product.artifact_stem: models[product.key] for product in PRODUCTS
    }
    display_names = {
        product.artifact_stem: product.display_name for product in PRODUCTS
    }
    artifacts = packaging.write_model_artifacts(
        layout,
        artifact_models,
        display_names=display_names,
        thumbnails=thumbnails,
        print_intents=print_intents,
        bambu_postprocessor=None,
    )

    all_four_objects = [
        packaging.ThreeMFObject(
            product.display_name,
            models[product.key],
            transforms[product.key],
        )
        for product in PRODUCTS
    ]
    all_four_core = packaging.write_core_3mf(
        layout.models_3mf / f"{ALL_FOUR_STEM}_MODEL_ONLY.3mf",
        all_four_objects,
        title="Rad Dad Retro Riot v7 All-Four A1 Mini Plate",
        thumbnail=all_four_previews["front"],
        metadata={
            "PackageKind": "model-only-core-3mf",
            "MinimumObjectSpacingMM": str(MINIMUM_PLATE_SPACING_MM),
            "Plate": "Bambu Lab A1 mini 180 x 180 mm",
        },
    )

    packaging.write_overlay_assets(layout.guides / "nfc_overlays")
    packaging.write_overlay_sheets(layout.guides / "nfc_overlays")
    packaging.write_nfc_placement_guide(layout.guides)
    packaging.write_handoff_card_assets(layout.guides / "handoff_card")
    _write_json(layout.qa / "PRODUCT_METADATA.json", _product_metadata(models))
    _write_json(layout.qa / "ALL_FOUR_PLATE_LAYOUT.json", plate_metadata)
    _write_easter_egg_guide(layout.guides / "CAPACITY_EASTER_EGGS.md")

    bambu_projects, bambu_status = _create_bambu_projects(
        layout,
        artifacts,
        output_root,
        bambu_mode,
    )
    bambu_status.update(
        {
            "packaging_load_mode": packaging_load_mode,
            "guaranteed_spacing_file": _relative(all_four_core.path, output_root),
            "guaranteed_minimum_spacing_mm": MINIMUM_PLATE_SPACING_MM,
        }
    )
    bambu_status_path = _write_json(
        layout.qa / "BAMBU_PROJECT_STATUS.json",
        bambu_status,
    )
    print_intents = _finalize_print_intent_statuses(print_intents, bambu_status)
    packaging.write_mesh_qa_json(
        layout.qa / "MODEL_QA.json",
        artifact_models,
        release_name=RELEASE_NAME,
        print_intents=print_intents,
    )

    packaging.write_release_documents(
        output_root,
        release_name=RELEASE_NAME,
        tap_url="https://raddadband.com/tap/",
        print_intents=print_intents,
        bambu_project_files=bambu_projects,
    )

    build_index = {
        "schema": "rad-dad-micro-replica-build-index-v1",
        "release": RELEASE_NAME,
        "packaging_load_mode": packaging_load_mode,
        "individual_products": {
            product.artifact_stem: {
                "stl": _relative(artifacts[product.artifact_stem]["stl"], output_root),
                "model_only_core_3mf": _relative(
                    artifacts[product.artifact_stem]["core_3mf"].path,
                    output_root,
                ),
                "bambu_project_3mf": (
                    _relative(bambu_projects[product.artifact_stem], output_root)
                    if product.artifact_stem in bambu_projects
                    else None
                ),
            }
            for product in PRODUCTS
        },
        "all_four_plate": {
            "model_only_core_3mf": _relative(all_four_core.path, output_root),
            "bambu_project_3mf": (
                _relative(bambu_projects[ALL_FOUR_STEM], output_root)
                if ALL_FOUR_STEM in bambu_projects
                else None
            ),
            "minimum_spacing_mm": MINIMUM_PLATE_SPACING_MM,
        },
        "physical_validation": "required-before-batch-production",
    }
    _write_json(layout.qa / "BUILD_INDEX.json", build_index)

    archive_path = output_root / ARCHIVE_NAME
    sha256sums = _write_sha256sums(output_root, archive_path)
    finalized = packaging.finalize_release(
        output_root,
        archive_path=archive_path,
        release_name=RELEASE_NAME,
        archive_prefix="Rad_Dad_Retro_Riot_v7_Micro_Replica_Edition",
        manifest_metadata={
            "collection": "Micro Replica Edition",
            "printer_target": "Bambu Lab A1 mini / 0.4 mm nozzle",
            "minimum_all_four_spacing_mm": MINIMUM_PLATE_SPACING_MM,
            "capacity_easter_eggs": ["C-69", "3.69 MB", "T-369"],
            "bambu_mode": bambu_mode,
            "physical_validation": "required-before-batch-production",
        },
    )

    return BuildResult(
        output=output_root,
        archive=Path(finalized["archive"]),
        archive_checksum=Path(finalized["archive_checksum"]),
        manifest=Path(finalized["manifest"]),
        sha256sums=sha256sums,
        bambu_status=bambu_status_path,
        bambu_required_satisfied=bool(bambu_status["required_satisfied"]),
        packaging_load_mode=packaging_load_mode,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the complete Rad Dad Micro Replicas v7 print release."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="release directory; relative paths are resolved from the repository root",
    )
    bambu_group = parser.add_mutually_exclusive_group()
    bambu_group.add_argument(
        "--bambu",
        dest="bambu_mode",
        action="store_const",
        const="required",
        help="require verified Bambu project 3MFs in addition to model-only files",
    )
    bambu_group.add_argument(
        "--skip-bambu",
        dest="bambu_mode",
        action="store_const",
        const="skip",
        help="build deterministic model-only files without launching Bambu Studio",
    )
    parser.set_defaults(bambu_mode="auto")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = build_release(args.output, args.bambu_mode)
    print(f"Release: {result.output}")
    print(f"Print pack: {result.archive}")
    print(f"Manifest: {result.manifest}")
    print(f"Bambu status: {result.bambu_status}")
    if args.bambu_mode == "required" and not result.bambu_required_satisfied:
        print(
            "Verified Bambu projects were required but at least one fell back "
            "to its clearly labeled MODEL_ONLY Core 3MF.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
