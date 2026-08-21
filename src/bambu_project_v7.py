#!/usr/bin/env python3
"""Create validated Bambu Studio projects for the Rad Dad v7 products.

This module deliberately has no geometry-only 3MF fallback. A successful call
means Bambu Studio wrote the archive and the archive contains parseable printer,
process, filament, object, and plate configuration. If Bambu Studio or its
profiles are unavailable, the caller receives an actionable exception and no
output file is replaced.

The Bambu Studio command line currently exposes process settings globally, but
does not provide a dependable command-line API for creating per-eyelet modifier
meshes. The v7 profile therefore uses four wall loops globally. Combined plates
also receive organic, build-plate-only support globally; flat media normally do
not generate support because they have no qualifying overhangs.
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable, Sequence
from xml.etree import ElementTree


MACHINE_PROFILE_NAME = "Bambu Lab A1 mini 0.4 nozzle"
PROCESS_PROFILE_NAME = "0.16mm Optimal @BBL A1M"
FILAMENT_PROFILE_NAME = "Bambu PLA Basic @BBL A1M"
CUSTOM_PROCESS_PROFILE_BASE_NAME = "Rad Dad v7 0.16 mm A1 Mini"

PROFILE_FILES = {
    "machine": Path("BBL/machine/Bambu Lab A1 mini 0.4 nozzle.json"),
    "process": Path("BBL/process/0.16mm Optimal @BBL A1M.json"),
    "filament": Path("BBL/filament/Bambu PLA Basic @BBL A1M.json"),
}

REQUIRED_PROJECT_MEMBERS = {
    "3D/3dmodel.model",
    "Metadata/model_settings.config",
    "Metadata/project_settings.config",
}

PROCESS_BASE_SETTINGS = {
    "layer_height": "0.16",
    "initial_layer_print_height": "0.2",
    "curr_bed_type": "Textured PEI Plate",
    "wall_generator": "arachne",
    "wall_loops": "4",
    "top_shell_layers": "5",
    "bottom_shell_layers": "5",
    "sparse_infill_density": "30%",
    "sparse_infill_pattern": "gyroid",
    "elefant_foot_compensation": "0.15",
    "outer_wall_speed": "30",
    "top_surface_speed": "30",
    "small_perimeter_speed": "25",
    "seam_position": "back",
    "initial_layer_speed": "30",
    "bridge_speed": "25",
    "bridge_flow": "0.93",
}

NO_SUPPORT_SETTINGS = {
    "enable_support": "0",
    "support_type": "tree(auto)",
    "support_style": "default",
    "support_on_build_plate_only": "0",
}

ORGANIC_SUPPORT_SETTINGS = {
    "enable_support": "1",
    "support_type": "tree(auto)",
    "support_style": "default",
    "support_on_build_plate_only": "1",
}

PRODUCT_ALIASES = {
    "cassette": "cassette",
    "tape": "cassette",
    "floppy": "floppy",
    "floppy_disk": "floppy",
    "floppy-disc": "floppy",
    "vhs": "vhs",
    "mini_vhs": "vhs",
    "trailer": "trailer_swift",
    "trailer_swift": "trailer_swift",
    "trailer-swift": "trailer_swift",
    "figurine": "trailer_swift",
    "combined": "combined",
    "all": "combined",
    "all_four": "combined",
}

CLI_LIMITATIONS = (
    "Bambu Studio CLI does not expose a reliable per-eyelet modifier API; "
    "the generated project uses four wall loops globally.",
    "Support settings are process-global. Combined plates use organic, "
    "build-plate-only support for the entire plate.",
    "Object placement uses Bambu Studio's A1 Mini-aware auto-arranger because "
    "the CLI has no stable, documented arbitrary per-object placement option.",
    "The function exports an unsliced project 3MF. It does not embed G-code, "
    "which avoids version-specific headless slicing failures and keeps the "
    "project editable in Bambu Studio.",
    "Bundled Bambu profiles use inheritance, which some CLI builds do not "
    "resolve correctly. This module flattens each profile before invoking the CLI.",
)


class BambuProjectError(RuntimeError):
    """Base error for Bambu project creation and validation."""


class BambuStudioUnavailableError(BambuProjectError):
    """Raised when Bambu Studio or its bundled profiles cannot be found."""


class BambuStudioCLIError(BambuProjectError):
    """Raised when Bambu Studio fails to export a project."""


class BambuProjectValidationError(BambuProjectError):
    """Raised when the exported archive is not the requested Bambu project."""


def _normalize_product_kind(product_kind: str, combined: bool) -> tuple[str, bool]:
    key = str(product_kind).strip().lower().replace(" ", "_")
    try:
        normalized = PRODUCT_ALIASES[key]
    except KeyError as exc:
        allowed = ", ".join(sorted({"cassette", "floppy", "vhs", "trailer_swift", "combined"}))
        raise ValueError(f"Unknown product_kind {product_kind!r}; expected one of: {allowed}") from exc
    if normalized == "combined":
        combined = True
    return normalized, bool(combined)


def _normalize_stl_paths(input_stls: Iterable[os.PathLike[str] | str]) -> list[Path]:
    if isinstance(input_stls, (str, os.PathLike)):
        raw_paths: Sequence[os.PathLike[str] | str] = [input_stls]
    else:
        raw_paths = list(input_stls)
    if not raw_paths:
        raise ValueError("input_stls must contain at least one STL file")

    paths: list[Path] = []
    seen: set[Path] = set()
    for raw_path in raw_paths:
        path = Path(raw_path).expanduser().resolve()
        if path.suffix.lower() != ".stl":
            raise ValueError(f"Input must be an STL file: {path}")
        if not path.is_file():
            raise FileNotFoundError(path)
        if path in seen:
            raise ValueError(f"Duplicate STL input: {path}")
        seen.add(path)
        paths.append(path)
    return paths


def _binary_from_app(app_path: Path) -> Path:
    if app_path.suffix.lower() == ".app":
        return app_path / "Contents" / "MacOS" / "BambuStudio"
    return app_path


def find_bambu_studio() -> Path:
    """Return the Bambu Studio executable or raise an actionable error.

    Resolution order is ``BAMBU_STUDIO_BIN``, ``BAMBU_STUDIO_APP``, standard
    macOS application locations, and finally executable names on ``PATH``.
    """

    candidates: list[Path] = []
    if os.environ.get("BAMBU_STUDIO_BIN"):
        candidates.append(Path(os.environ["BAMBU_STUDIO_BIN"]).expanduser())
    if os.environ.get("BAMBU_STUDIO_APP"):
        candidates.append(_binary_from_app(Path(os.environ["BAMBU_STUDIO_APP"]).expanduser()))
    candidates.extend(
        (
            Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"),
            Path.home() / "Applications/BambuStudio.app/Contents/MacOS/BambuStudio",
        )
    )
    for executable_name in ("bambu-studio", "BambuStudio"):
        resolved = shutil.which(executable_name)
        if resolved:
            candidates.append(Path(resolved))

    checked: list[str] = []
    for candidate in candidates:
        candidate = candidate.expanduser().resolve()
        checked.append(str(candidate))
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    locations = "\n  - ".join(checked) if checked else "(no candidates)"
    raise BambuStudioUnavailableError(
        "Bambu Studio was not found. Install Bambu Studio or set "
        "BAMBU_STUDIO_BIN to its executable. Checked:\n  - " + locations
    )


def find_profile_root(bambu_binary: os.PathLike[str] | str) -> Path:
    """Locate the profile directory associated with a Bambu Studio executable."""

    candidates: list[Path] = []
    if os.environ.get("BAMBU_PROFILE_ROOT"):
        candidates.append(Path(os.environ["BAMBU_PROFILE_ROOT"]).expanduser())

    binary = Path(bambu_binary).expanduser().resolve()
    candidates.extend(
        (
            binary.parent.parent / "Resources" / "profiles",
            binary.parent / "resources" / "profiles",
            Path("/usr/share/bambu-studio/profiles"),
            Path("/usr/local/share/bambu-studio/profiles"),
        )
    )
    for candidate in candidates:
        if candidate.is_dir() and all((candidate / relative).is_file() for relative in PROFILE_FILES.values()):
            return candidate.resolve()

    locations = "\n  - ".join(str(path) for path in candidates)
    raise BambuStudioUnavailableError(
        "Bambu Studio was found, but its A1 Mini profiles were not. Set "
        "BAMBU_PROFILE_ROOT to the directory containing BBL/machine, "
        "BBL/process, and BBL/filament. Checked:\n  - " + locations
    )


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _profile_index(category_directory: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in sorted(category_directory.rglob("*.json")):
        index.setdefault(path.stem, path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        name = data.get("name")
        if isinstance(name, str) and name:
            index.setdefault(name, path)
    return index


def _flatten_profile(profile_path: Path, category_directory: Path) -> dict[str, Any]:
    """Resolve a bundled Bambu profile inheritance chain into one JSON object."""

    index = _profile_index(category_directory)
    cache: dict[Path, dict[str, Any]] = {}

    def resolve(path: Path, stack: tuple[Path, ...] = ()) -> dict[str, Any]:
        path = path.resolve()
        if path in cache:
            return dict(cache[path])
        if path in stack:
            chain = " -> ".join(item.name for item in (*stack, path))
            raise BambuStudioUnavailableError(f"Cyclic Bambu profile inheritance: {chain}")
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BambuStudioUnavailableError(f"Cannot read Bambu profile {path}: {exc}") from exc

        inherited: dict[str, Any] = {}
        parents = current.get("inherits")
        if isinstance(parents, str) and parents:
            parent_names = [parents]
        elif isinstance(parents, list):
            parent_names = [str(parent) for parent in parents if str(parent)]
        else:
            parent_names = []
        for parent_name in parent_names:
            parent_path = index.get(parent_name)
            if parent_path is None:
                raise BambuStudioUnavailableError(
                    f"Profile {path.name} inherits {parent_name!r}, but that profile "
                    f"was not found under {category_directory}"
                )
            inherited = _deep_merge(inherited, resolve(parent_path, (*stack, path)))

        flattened = _deep_merge(inherited, current)
        flattened.pop("inherits", None)
        cache[path] = flattened
        return dict(flattened)

    return resolve(profile_path)


def _custom_process_profile_name(supports_enabled: bool) -> str:
    support_label = "Organic Support" if supports_enabled else "No Support"
    return f"{CUSTOM_PROCESS_PROFILE_BASE_NAME} - {support_label}"


def _write_flattened_profiles(
    profile_root: Path,
    destination: Path,
    product_kind: str,
    supports_enabled: bool,
) -> tuple[Path, Path, Path]:
    output_paths: dict[str, Path] = {}
    custom_process_name = _custom_process_profile_name(supports_enabled)
    for category, relative_path in PROFILE_FILES.items():
        source = profile_root / relative_path
        flattened = _flatten_profile(source, source.parent)

        if category == "machine":
            flattened["default_print_profile"] = custom_process_name

        if category == "process":
            flattened.update(PROCESS_BASE_SETTINGS)
            flattened.update(ORGANIC_SUPPORT_SETTINGS if supports_enabled else NO_SUPPORT_SETTINGS)
            flattened.update(
                {
                    "name": custom_process_name,
                    "type": "process",
                    "from": "user",
                    "compatible_printers": [MACHINE_PROFILE_NAME],
                    "rad_dad_product_kind": product_kind,
                    "rad_dad_profile_version": "7",
                }
            )

        output = destination / f"rad_dad_v7_{category}.json"
        output.write_text(json.dumps(flattened, indent=2, ensure_ascii=True) + "\n", encoding="ascii")
        output_paths[category] = output

    return output_paths["machine"], output_paths["process"], output_paths["filament"]


def _read_json_member(archive: zipfile.ZipFile, member: str) -> dict[str, Any]:
    payload = archive.read(member).decode("utf-8-sig")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"{member} must contain a JSON object")
    return value


def _metadata_values(element: ElementTree.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for child in element:
        if child.tag.rsplit("}", 1)[-1] != "metadata":
            continue
        key = child.attrib.get("key") or child.attrib.get("name")
        value = child.attrib.get("value")
        if key and value is not None:
            values[key] = value
    return values


def _parse_model_settings(payload: bytes) -> tuple[list[str], int, int]:
    root = ElementTree.fromstring(payload)
    names: list[str] = []
    for object_element in root.findall("./object"):
        metadata = _metadata_values(object_element)
        if metadata.get("name"):
            names.append(metadata["name"])
    plates = root.findall("./plate")
    instance_count = sum(len(plate.findall("./model_instance")) for plate in plates)
    return names, len(plates), instance_count


def _parse_core_model(payload: bytes) -> tuple[str | None, list[dict[str, Any]]]:
    root = ElementTree.fromstring(payload)
    generator: str | None = None
    for metadata in root.findall("./{*}metadata"):
        name = metadata.attrib.get("name", "").lower()
        if name in {"application", "slic3rpe:version3mf", "bambustudio:version"}:
            generator = (metadata.text or metadata.attrib.get("value") or "").strip() or None
            if generator:
                break

    build_items: list[dict[str, Any]] = []
    for item in root.findall("./{*}build/{*}item"):
        transform_text = item.attrib.get("transform", "")
        try:
            transform = [float(value) for value in transform_text.split()] if transform_text else []
        except ValueError:
            transform = []
        build_items.append(
            {
                "object_id": item.attrib.get("objectid"),
                "printable": item.attrib.get("printable", "1"),
                "transform": transform,
            }
        )
    return generator, build_items


def _scalar(value: Any) -> str:
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value).strip().lower()


def _settings_match(settings: dict[str, Any], expected: dict[str, str]) -> tuple[bool, dict[str, Any]]:
    mismatches: dict[str, Any] = {}
    for key, expected_value in expected.items():
        actual = settings.get(key)
        if actual is None or _scalar(actual) != _scalar(expected_value):
            mismatches[key] = {"expected": expected_value, "actual": actual}
    return not mismatches, mismatches


def inspect_bambu_project_3mf(project_3mf: os.PathLike[str] | str) -> dict[str, Any]:
    """Inspect a 3MF and report whether it contains a real Bambu project.

    The returned dictionary is suitable for JSON output. ``is_bambu_project``
    confirms that Bambu project and model configuration members exist and parse.
    ``matches_rad_dad_v7_base_profile`` confirms the requested A1 Mini, layer,
    wall, shell, infill, and elephant-foot settings. ``support_mode`` reports
    whether the embedded project is configured for the supported v7 modes.
    """

    path = Path(project_3mf).expanduser().resolve()
    report: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "zip_valid": False,
        "is_bambu_project": False,
        "matches_rad_dad_v7_base_profile": False,
        "support_mode": "unknown",
        "generator": None,
        "object_names": [],
        "plate_count": 0,
        "model_instance_count": 0,
        "build_items": [],
        "project_settings": {},
        "profile_mismatches": {},
        "missing_members": [],
        "errors": [],
        "warnings": [],
        "cli_limitations": list(CLI_LIMITATIONS),
    }
    if not path.is_file():
        report["errors"].append(f"File does not exist: {path}")
        return report

    try:
        with zipfile.ZipFile(path) as archive:
            report["zip_valid"] = True
            members = set(archive.namelist())
            missing = sorted(REQUIRED_PROJECT_MEMBERS - members)
            report["missing_members"] = missing
            if missing:
                report["errors"].append(
                    "Not a configured Bambu project; missing archive members: " + ", ".join(missing)
                )
                if members == {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model", "Metadata/thumbnail.png"}:
                    report["warnings"].append("This has the repository's old geometry-only 3MF layout.")
                return report

            try:
                project_settings = _read_json_member(archive, "Metadata/project_settings.config")
                object_names, plate_count, instance_count = _parse_model_settings(
                    archive.read("Metadata/model_settings.config")
                )
                generator, build_items = _parse_core_model(archive.read("3D/3dmodel.model"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError, ValueError, ElementTree.ParseError) as exc:
                report["errors"].append(f"Embedded Bambu configuration is unreadable: {exc}")
                return report

            report["project_settings"] = project_settings
            report["object_names"] = object_names
            report["plate_count"] = plate_count
            report["model_instance_count"] = instance_count
            report["generator"] = generator
            report["build_items"] = build_items
            report["is_bambu_project"] = True

            supports_enabled = _scalar(project_settings.get("enable_support")) == "1"
            expected_process_name = _custom_process_profile_name(supports_enabled)
            expected_base = {
                "printer_model": "Bambu Lab A1 mini",
                "printer_variant": "0.4",
                "nozzle_diameter": "0.4",
                "default_print_profile": expected_process_name,
                "print_settings_id": expected_process_name,
                **PROCESS_BASE_SETTINGS,
            }
            base_match, mismatches = _settings_match(project_settings, expected_base)
            report["matches_rad_dad_v7_base_profile"] = base_match
            report["profile_mismatches"] = mismatches

            no_support_match, _ = _settings_match(project_settings, NO_SUPPORT_SETTINGS)
            organic_match, _ = _settings_match(project_settings, ORGANIC_SUPPORT_SETTINGS)
            if organic_match:
                report["support_mode"] = "organic_build_plate_only"
            elif no_support_match:
                report["support_mode"] = "off"
            else:
                report["warnings"].append("Support settings do not match either approved v7 mode.")
            if plate_count < 1 or instance_count < 1 or not build_items:
                report["errors"].append("Bambu project has no usable plate instances or build items.")
    except zipfile.BadZipFile as exc:
        report["errors"].append(f"Unreadable ZIP/3MF package: {exc}")
    except OSError as exc:
        report["errors"].append(f"Cannot inspect project: {exc}")
    return report


def _object_key(value: str) -> str:
    stem = Path(value).stem
    return re.sub(r"[^a-z0-9]+", "", stem.lower())


def _validate_created_project(
    report: dict[str, Any],
    input_stls: Sequence[Path],
    supports_enabled: bool,
) -> None:
    failures = list(report.get("errors", []))
    if not report.get("is_bambu_project"):
        failures.append("Bambu project metadata was not embedded")
    if not report.get("matches_rad_dad_v7_base_profile"):
        failures.append(f"v7 profile mismatch: {report.get('profile_mismatches', {})}")
    expected_support_mode = "organic_build_plate_only" if supports_enabled else "off"
    if report.get("support_mode") != expected_support_mode:
        failures.append(
            f"support mode is {report.get('support_mode')!r}, expected {expected_support_mode!r}"
        )

    actual_keys = [_object_key(name) for name in report.get("object_names", [])]
    missing_names: list[str] = []
    for input_stl in input_stls:
        expected_key = _object_key(input_stl.name)
        if not any(expected_key == actual or expected_key in actual or actual in expected_key for actual in actual_keys):
            missing_names.append(input_stl.name)
    if missing_names:
        failures.append("object names were not preserved: " + ", ".join(missing_names))
    if report.get("model_instance_count", 0) < len(input_stls):
        failures.append(
            f"only {report.get('model_instance_count', 0)} model instances for {len(input_stls)} inputs"
        )

    if failures:
        raise BambuProjectValidationError("Bambu export failed validation:\n- " + "\n- ".join(failures))


def _bambu_version(binary: Path) -> str | None:
    info_plist = binary.parent.parent / "Info.plist"
    if not info_plist.is_file():
        return None
    try:
        with info_plist.open("rb") as handle:
            data = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException):
        return None
    version = data.get("CFBundleShortVersionString")
    return str(version) if version else None


def _log_tail(text: str, limit: int = 5000) -> str:
    text = text.strip()
    return text if len(text) <= limit else "..." + text[-limit:]


def create_bambu_project_3mf(
    input_stls: Iterable[os.PathLike[str] | str],
    output_3mf: os.PathLike[str] | str,
    product_kind: str,
    combined: bool = False,
) -> dict[str, Any]:
    """Create and validate a Bambu Studio A1 Mini 0.4 mm project.

    Parameters
    ----------
    input_stls:
        One or more STL paths. Their filenames become the Bambu object names.
    output_3mf:
        Destination project path. It is replaced only after full validation.
    product_kind:
        ``cassette``, ``floppy``, ``vhs``, ``trailer_swift``, or ``combined``.
    combined:
        Enables the combined-plate support policy. ``product_kind='combined'``
        also enables it automatically.

    Returns
    -------
    dict
        The result of :func:`inspect_bambu_project_3mf`, with CLI provenance.

    Raises
    ------
    BambuStudioUnavailableError
        Bambu Studio or the required bundled profiles cannot be found.
    BambuStudioCLIError
        Bambu Studio exits unsuccessfully or fails to write an output archive.
    BambuProjectValidationError
        The archive is geometry-only, misconfigured, incomplete, or loses an
        input object name.
    """

    stl_paths = _normalize_stl_paths(input_stls)
    normalized_kind, combined = _normalize_product_kind(product_kind, combined)
    supports_enabled = combined or normalized_kind == "trailer_swift"

    output = Path(output_3mf).expanduser().resolve()
    if output.suffix.lower() != ".3mf":
        raise ValueError(f"output_3mf must end in .3mf: {output}")
    if output in stl_paths:
        raise ValueError("output_3mf must not overwrite an input file")

    bambu_binary = find_bambu_studio()
    profile_root = find_profile_root(bambu_binary)
    timeout_seconds = float(os.environ.get("BAMBU_STUDIO_TIMEOUT_SECONDS", "600"))
    if timeout_seconds <= 0:
        raise ValueError("BAMBU_STUDIO_TIMEOUT_SECONDS must be positive")

    with tempfile.TemporaryDirectory(prefix="rad_dad_bambu_v7_") as temporary_directory:
        temporary = Path(temporary_directory)
        machine_profile, process_profile, filament_profile = _write_flattened_profiles(
            profile_root,
            temporary,
            normalized_kind,
            supports_enabled,
        )
        temporary_output = temporary / output.name
        settings_argument = f"{machine_profile};{process_profile}"
        command = [
            str(bambu_binary),
            "--debug",
            "3",
            "--load-settings",
            settings_argument,
            "--load-filaments",
            str(filament_profile),
            "--load-defaultfila",
            "--arrange",
            "1",
            "--ensure-on-bed",
            "--export-3mf",
            str(temporary_output),
            *(str(path) for path in stl_paths),
        ]

        try:
            completed = subprocess.run(
                command,
                cwd=temporary,
                env={**os.environ, "LC_ALL": "C"},
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise BambuStudioCLIError(
                f"Bambu Studio did not finish within {timeout_seconds:g} seconds. "
                "No output was installed."
            ) from exc
        except OSError as exc:
            raise BambuStudioCLIError(f"Could not launch Bambu Studio: {exc}") from exc

        if completed.returncode != 0:
            raise BambuStudioCLIError(
                "Bambu Studio export failed with return code "
                f"{completed.returncode}.\nSTDOUT:\n{_log_tail(completed.stdout)}\n"
                f"STDERR:\n{_log_tail(completed.stderr)}"
            )

        if not temporary_output.is_file():
            generated = sorted(temporary.rglob("*.3mf"))
            if len(generated) == 1:
                temporary_output = generated[0]
            else:
                choices = ", ".join(str(path) for path in generated) or "none"
                raise BambuStudioCLIError(
                    "Bambu Studio reported success but did not create the requested project. "
                    f"Other 3MF candidates: {choices}"
                )

        report = inspect_bambu_project_3mf(temporary_output)
        _validate_created_project(report, stl_paths, supports_enabled)

        output.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary_output, output)

    final_report = inspect_bambu_project_3mf(output)
    _validate_created_project(final_report, stl_paths, supports_enabled)
    final_report.update(
        {
            "bambu_studio_binary": str(bambu_binary),
            "bambu_studio_version": _bambu_version(bambu_binary),
            "profile_root": str(profile_root),
            "product_kind": normalized_kind,
            "combined": combined,
            "supports_enabled": supports_enabled,
            "wall_loops_global": 4,
            "per_eyelet_modifier_applied": False,
            "input_stls": [str(path) for path in stl_paths],
        }
    )
    return final_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or inspect validated Rad Dad v7 Bambu Studio projects."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="create a configured Bambu project")
    create_parser.add_argument("input_stls", nargs="+", type=Path, help="input STL file(s)")
    create_parser.add_argument("--output", "-o", required=True, type=Path, help="output .3mf")
    create_parser.add_argument(
        "--product",
        "-p",
        required=True,
        help="cassette, floppy, vhs, trailer_swift, or combined",
    )
    create_parser.add_argument(
        "--combined",
        action="store_true",
        help="use the combined-plate organic support policy",
    )

    inspect_parser = subparsers.add_parser("inspect", help="inspect embedded Bambu configuration")
    inspect_parser.add_argument("project_3mf", type=Path, help="project .3mf to inspect")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "create":
            report = create_bambu_project_3mf(
                arguments.input_stls,
                arguments.output,
                arguments.product,
                combined=arguments.combined,
            )
        else:
            report = inspect_bambu_project_3mf(arguments.project_3mf)
    except (BambuProjectError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, indent=2, ensure_ascii=True))
    if arguments.command == "inspect":
        return 0 if report.get("is_bambu_project") and not report.get("errors") else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
