"""Digital merch desk for the leftover #8 Current Three study.

This package is a shopper/admin surface only. It does not print, slice,
ship, price, or post merch.
"""

from .catalog import CatalogError, DigitalCatalog

__all__ = ["CatalogError", "DigitalCatalog"]
