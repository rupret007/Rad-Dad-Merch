#!/usr/bin/env python3
"""Verify digital merch catalog, cart, admin, and public-path security."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def extra_gates() -> None:
    from digital_merch.catalog import (
        FORBIDDEN_PUBLIC_FRAGMENTS,
        DigitalCatalog,
        assert_public_payload_safe,
        load_study_metadata,
    )
    from digital_merch.security import (
        ALLOWED_CHECKOUT_FIELDS,
        FORBIDDEN_CHECKOUT_FIELDS,
        HOLD_PATH,
        PUBLIC_EXACT_PATHS,
        STUDY_CROP_PATH,
    )

    metadata = load_study_metadata()
    if metadata.get("physical_proof") is not False:
        raise RuntimeError("digital merch must stay bound to a digital-only study")
    catalog = DigitalCatalog(metadata)
    public = catalog.public_catalog()
    assert_public_payload_safe(public)
    blob = str(public).lower()
    for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        if fragment in blob:
            raise RuntimeError(f"public catalog leaked {fragment}")
    if any(path.endswith((".stl", ".3mf")) or "release/" in path for path in PUBLIC_EXACT_PATHS):
        raise RuntimeError("public merch path allowlist includes print files")
    if "confirm_digital_hold" not in ALLOWED_CHECKOUT_FIELDS:
        raise RuntimeError("checkout dropped the digital-hold confirmation field")
    if HOLD_PATH.match("/hold/0123456789abcdef") is None:
        raise RuntimeError("hold receipt path is not allowlisted")
    if HOLD_PATH.match("/hold/../release/v9/stl/x.stl") is not None:
        raise RuntimeError("hold receipt path accepted a traversal")
    if STUDY_CROP_PATH.match("/assets/study/cassette.png") is None:
        raise RuntimeError("study crop path is not allowlisted")
    if STUDY_CROP_PATH.match("/assets/study/../release/v9/stl/x.stl") is not None:
        raise RuntimeError("study crop path accepted a traversal")
    if "stripe" in FORBIDDEN_CHECKOUT_FIELDS and "shipping" in FORBIDDEN_CHECKOUT_FIELDS:
        return
    raise RuntimeError("checkout still accepts spend or shipping fields")


def main() -> int:
    extra_gates()
    suite = unittest.defaultTestLoader.discover(
        str(REPO_ROOT / "tests"),
        pattern="test_digital_merch*.py",
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    node = shutil.which("node")
    if node is None:
        print("Digital merch verification requires Node.js 18+ for offline cart transport tests.", file=sys.stderr)
        return 1
    transport = subprocess.run(
        [node, str(REPO_ROOT / "tests" / "test_cart_transport.js")],
        cwd=REPO_ROOT,
        check=False,
        timeout=30,
    )
    if transport.returncode != 0:
        return 1
    print(
        "Digital merch verified: leftover #8 catalog identity, hold receipts, "
        "cart rules, browser transport, admin lock, and public-path security passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
