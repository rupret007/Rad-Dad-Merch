"""Catalog logic bound to the leftover #8 Current Three material study."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_METADATA_PATH = (
    REPO_ROOT / "docs" / "previews" / "Rad_Dad_Current_Three_PETG_Material_Study.json"
)
STUDY_IMAGE_PATH = STUDY_METADATA_PATH.with_suffix(".png")

PUBLIC_CATALOG_KEYS = (
    "sku",
    "key",
    "title",
    "revision",
    "kind",
    "published",
    "color",
    "extents_mm",
    "material",
    "description",
    "digital_only",
    "physical_proof",
    "fulfillment",
)

FORBIDDEN_PUBLIC_FRAGMENTS = (
    "release/",
    ".stl",
    ".3mf",
    "source_sha256",
    "source_bytes",
    "renderer",
)

REQUIRED_STUDY_MODELS = ("cassette", "floppy", "vhs")
ALLOWED_SKU_KIND = "digital_study"
ALLOWED_FULFILLMENT = "digital_study_request"
SKU_PATTERN_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")


class CatalogError(RuntimeError):
    """Raised when the leftover #8 study cannot back a digital catalog."""


@dataclass(frozen=True)
class SkuSpec:
    sku: str
    key: str
    title: str
    description: str
    revision: str | None = None
    color: str | None = None
    extents_mm: list[float] | None = None
    material: str | None = None


@dataclass
class Sku:
    sku: str
    key: str
    title: str
    revision: str
    kind: str
    published: bool
    color: str
    extents_mm: list[float] | None
    material: str
    description: str
    digital_only: bool = True
    physical_proof: bool = False
    fulfillment: str = ALLOWED_FULFILLMENT

    def public_dict(self) -> dict[str, Any]:
        payload = {
            "sku": self.sku,
            "key": self.key,
            "title": self.title,
            "revision": self.revision,
            "kind": self.kind,
            "published": self.published,
            "color": self.color,
            "extents_mm": list(self.extents_mm) if self.extents_mm is not None else None,
            "material": self.material,
            "description": self.description,
            "digital_only": True,
            "physical_proof": False,
            "fulfillment": ALLOWED_FULFILLMENT,
        }
        serialized = json.dumps(payload, sort_keys=True)
        for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
            if fragment in serialized.lower() or fragment in serialized:
                raise CatalogError(f"public catalog leaked {fragment}")
        return payload


SKU_SPECS: tuple[SkuSpec, ...] = (
    SkuSpec(
        sku="digital-cassette-v38",
        key="cassette",
        title="Compact Cassette digital study",
        description=(
            "Digital study card for Compact Cassette v38. The listing uses the "
            "leftover Current Three PETG material study. It is not a photograph, "
            "slicer preview, or a shippable print."
        ),
    ),
    SkuSpec(
        sku="digital-floppy-v22",
        key="floppy",
        title="3.5-inch Floppy digital study",
        description=(
            "Digital study card for 3.5-inch Floppy v22. The listing uses the "
            "leftover Current Three PETG material study. It is not a photograph, "
            "slicer preview, or a shippable print."
        ),
    ),
    SkuSpec(
        sku="digital-vhs-v5",
        key="vhs",
        title="Mini VHS digital study",
        description=(
            "Digital study card for Mini VHS v5. The listing uses the leftover "
            "Current Three PETG material study. It is not a photograph, slicer "
            "preview, or a shippable print."
        ),
    ),
    SkuSpec(
        sku="digital-current-three-study",
        key="current-three",
        title="Current Three PETG material study",
        revision="STUDY",
        color="#F5F1E8",
        extents_mm=None,
        material="digital PETG material study",
        description=(
            "Combined cassette, floppy, and mini VHS digital study at true "
            "relative size. Color and finish are illustrative. This request "
            "does not start a print, slice, or shipment."
        ),
    ),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CatalogError(message)


def validate_sku_id(sku: str) -> str:
    require(isinstance(sku, str), "SKU must be a string")
    require(3 <= len(sku) <= 64, f"SKU length is invalid: {sku!r}")
    require(set(sku) <= SKU_PATTERN_CHARS, f"SKU has illegal characters: {sku!r}")
    require(sku[0].isalpha() and sku[-1].isalnum(), f"SKU shape is invalid: {sku!r}")
    return sku


def validate_study_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    require(metadata.get("schema_version") == 1, "study schema_version drifted")
    require(metadata.get("render_type") == "digital_material_study", "study render_type drifted")
    require(metadata.get("physical_proof") is False, "study must remain digital-only")
    require(metadata.get("relative_scale") is True, "study must keep true relative scale")
    require(isinstance(metadata.get("disclaimer"), str) and metadata["disclaimer"].strip(), "study disclaimer missing")
    models = metadata.get("models")
    require(isinstance(models, list) and len(models) == 3, "study must name exactly the current three models")
    keys = [model.get("key") for model in models]
    require(tuple(keys) == REQUIRED_STUDY_MODELS, f"study model keys drifted: {keys}")
    return metadata


def load_study_metadata(path: Path | None = None) -> dict[str, Any]:
    metadata_path = path or STUDY_METADATA_PATH
    require(metadata_path.is_file(), f"leftover #8 study metadata missing: {metadata_path}")
    require(STUDY_IMAGE_PATH.is_file(), f"leftover #8 study image missing: {STUDY_IMAGE_PATH}")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CatalogError(f"leftover #8 study metadata is not JSON: {exc}") from exc
    return validate_study_metadata(metadata)


class DigitalCatalog:
    def __init__(
        self,
        metadata: dict[str, Any] | None = None,
        *,
        published_overrides: dict[str, bool] | None = None,
    ) -> None:
        self.metadata = (
            validate_study_metadata(metadata) if metadata is not None else load_study_metadata()
        )
        self.disclaimer = str(self.metadata["disclaimer"])
        self.study_title = str(self.metadata.get("title") or "Current Three PETG Material Study")
        self._skus = {sku.sku: sku for sku in self._build_skus()}
        if published_overrides:
            self.apply_overrides(published_overrides)

    def _models_by_key(self) -> dict[str, dict[str, Any]]:
        return {str(model["key"]): model for model in self.metadata["models"]}

    def _build_skus(self) -> list[Sku]:
        models = self._models_by_key()
        built: list[Sku] = []
        for spec in SKU_SPECS:
            validate_sku_id(spec.sku)
            if spec.key == "current-three":
                built.append(
                    Sku(
                        sku=spec.sku,
                        key=spec.key,
                        title=spec.title,
                        revision=spec.revision or "STUDY",
                        kind=ALLOWED_SKU_KIND,
                        published=True,
                        color=spec.color or "#F5F1E8",
                        extents_mm=spec.extents_mm,
                        material=spec.material or "digital PETG material study",
                        description=spec.description,
                    )
                )
                continue
            model = models.get(spec.key)
            require(model is not None, f"leftover #8 is missing model {spec.key}")
            revision = str(model.get("revision") or "")
            require(revision.startswith("V"), f"{spec.key} revision drifted")
            color = str(model.get("preview_color") or "")
            require(color.startswith("#") and len(color) == 7, f"{spec.key} preview color drifted")
            extents = model.get("source_extents_mm")
            require(isinstance(extents, list) and len(extents) == 3, f"{spec.key} extents drifted")
            built.append(
                Sku(
                    sku=spec.sku,
                    key=spec.key,
                    title=spec.title,
                    revision=revision,
                    kind=ALLOWED_SKU_KIND,
                    published=True,
                    color=color,
                    extents_mm=[float(value) for value in extents],
                    material=str(model.get("material_visualization") or "digital PETG material study"),
                    description=spec.description,
                )
            )
        return built

    def apply_overrides(self, published_overrides: dict[str, bool]) -> None:
        for sku_id, published in published_overrides.items():
            sku = self._skus.get(sku_id)
            require(sku is not None, f"cannot override unknown SKU {sku_id}")
            require(isinstance(published, bool), f"published override for {sku_id} must be bool")
            self._skus[sku_id] = replace(sku, published=published)

    def get(self, sku_id: str) -> Sku | None:
        try:
            validate_sku_id(sku_id)
        except CatalogError:
            return None
        return self._skus.get(sku_id)

    def require_sku(self, sku_id: str) -> Sku:
        sku = self.get(sku_id)
        require(sku is not None, f"unknown digital SKU: {sku_id}")
        return sku

    def all_skus(self) -> list[Sku]:
        return [self._skus[spec.sku] for spec in SKU_SPECS]

    def published_skus(self) -> list[Sku]:
        return [sku for sku in self.all_skus() if sku.published]

    def public_catalog(self) -> list[dict[str, Any]]:
        return [sku.public_dict() for sku in self.published_skus()]

    def admin_catalog(self) -> list[dict[str, Any]]:
        rows = []
        for sku in self.all_skus():
            row = sku.public_dict()
            row["published"] = sku.published
            rows.append(row)
        return rows


def assert_public_payload_safe(payload: Iterable[dict[str, Any]]) -> None:
    blob = json.dumps(list(payload), sort_keys=True)
    lowered = blob.lower()
    for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        if fragment in lowered:
            raise CatalogError(f"public catalog leaked {fragment}")
    extra_keys = set()
    for item in payload:
        extra_keys.update(set(item) - set(PUBLIC_CATALOG_KEYS))
    if extra_keys:
        raise CatalogError(f"public catalog has extra keys: {sorted(extra_keys)}")
