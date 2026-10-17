"""Cart rules for digital study requests. No prices, print jobs, or shipping."""

from __future__ import annotations

from dataclasses import dataclass, field

from .catalog import ALLOWED_FULFILLMENT, ALLOWED_SKU_KIND, CatalogError, DigitalCatalog, Sku


MIN_QTY = 1
MAX_QTY = 3
MAX_LINES = 4


class CartError(ValueError):
    """Shopper-facing cart or checkout rejection."""


@dataclass
class Cart:
    items: dict[str, int] = field(default_factory=dict)

    def copy(self) -> "Cart":
        return Cart(items=dict(self.items))

    def line_count(self) -> int:
        return sum(self.items.values())

    def is_empty(self) -> bool:
        return self.line_count() == 0

    def lines(self, catalog: DigitalCatalog) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for sku_id, qty in self.items.items():
            sku = catalog.require_sku(sku_id)
            rows.append(
                {
                    "sku": sku.sku,
                    "title": sku.title,
                    "identity": sku.identity,
                    "revision": sku.revision,
                    "qty": qty,
                    "color": sku.color,
                    "kind": sku.kind,
                    "study_frame": sku.study_frame,
                    "digital_only": True,
                    "fulfillment": sku.fulfillment,
                    "available": (
                        sku.published and sku.digital_only and not sku.physical_proof
                        and sku.kind == ALLOWED_SKU_KIND and sku.fulfillment == ALLOWED_FULFILLMENT
                    ),
                }
            )
        return rows

    def add(self, catalog: DigitalCatalog, sku_id: str, qty: int = 1) -> "Cart":
        sku = _require_purchasable(catalog, sku_id)
        amount = _require_qty(qty)
        current = self.items.get(sku.sku, 0)
        updated = current + amount
        if updated > MAX_QTY:
            raise CartError(f"At most {MAX_QTY} of each digital study can be requested.")
        if sku.sku not in self.items and len(self.items) >= MAX_LINES:
            raise CartError("The cart already holds the current digital studies.")
        self.items[sku.sku] = updated
        return self

    def set_qty(self, catalog: DigitalCatalog, sku_id: str, qty: int) -> "Cart":
        sku = _require_purchasable(catalog, sku_id)
        if qty == 0:
            self.items.pop(sku.sku, None)
            return self
        self.items[sku.sku] = _require_qty(qty)
        return self

    def remove(self, sku_id: str) -> "Cart":
        self.items.pop(sku_id, None)
        return self

    def checkoutable(self, catalog: DigitalCatalog) -> None:
        if self.is_empty():
            raise CartError("The cart is empty.")
        for sku_id in list(self.items):
            _require_purchasable(catalog, sku_id)


def _require_qty(qty: object) -> int:
    if isinstance(qty, bool) or not isinstance(qty, int):
        raise CartError("Quantity must be a whole number.")
    if qty < MIN_QTY or qty > MAX_QTY:
        raise CartError(f"Quantity must be between {MIN_QTY} and {MAX_QTY}.")
    return qty


def _require_purchasable(catalog: DigitalCatalog, sku_id: str) -> Sku:
    try:
        sku = catalog.require_sku(sku_id)
    except CatalogError as exc:
        raise CartError("That digital study is not in the catalog.") from exc
    if sku.kind != ALLOWED_SKU_KIND or sku.fulfillment != ALLOWED_FULFILLMENT:
        raise CartError("Only digital study requests can enter the cart.")
    if sku.physical_proof or not sku.digital_only:
        raise CartError("Physical merch cannot enter this cart.")
    if not sku.published:
        raise CartError("That digital study is not available.")
    return sku
