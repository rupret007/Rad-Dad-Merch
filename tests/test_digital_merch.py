#!/usr/bin/env python3
"""Digital merch shopper, admin, and public-path security tests."""

from __future__ import annotations

from io import BytesIO
import json
import re
from pathlib import Path
import sys
import unittest
from urllib.parse import urlencode


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (REPO_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from digital_merch.app import create_app
from digital_merch.cart import Cart, CartError
from digital_merch.catalog import CatalogError, DigitalCatalog, load_study_metadata
from digital_merch.security import SECURITY_HEADERS, normalize_request_path, SecurityError


STUDY_PNG = (
    REPO_ROOT / "docs" / "previews" / "Rad_Dad_Current_Three_PETG_Material_Study.png"
)


class Client:
    def __init__(self, app):
        self.app = app
        self.cookie = None

    def request(self, method: str, path: str, data: dict | None = None, headers: dict | None = None):
        encoded = urlencode(data or {}).encode("utf-8")
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "SERVER_NAME": "test",
            "SERVER_PORT": "80",
            "SCRIPT_NAME": "",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": BytesIO(encoded),
            "wsgi.errors": sys.stderr,
            "wsgi.multithread": False,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
            "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": str(len(encoded)),
            "REMOTE_ADDR": "127.0.0.1",
        }
        if self.cookie:
            environ["HTTP_COOKIE"] = self.cookie
        for key, value in (headers or {}).items():
            environ[key] = value
        status_headers = {}

        def start_response(status, response_headers):
            status_headers["status"] = status
            status_headers["headers"] = response_headers

        body = b"".join(self.app(environ, start_response))
        header_map = {key.lower(): value for key, value in status_headers["headers"]}
        if "set-cookie" in header_map:
            self.cookie = header_map["set-cookie"].split(";", 1)[0]
        return status_headers["status"], header_map, body

    def get(self, path: str):
        return self.request("GET", path)

    def post(self, path: str, data: dict, csrf: str | None = None, header_csrf: bool = False):
        payload = dict(data)
        headers = {}
        if csrf and not header_csrf:
            payload["csrf"] = csrf
        if csrf and header_csrf:
            headers["HTTP_X_CSRF_TOKEN"] = csrf
        return self.request("POST", path, payload, headers)

    def csrf_from(self, body: bytes) -> str:
        match = re.search(rb'name="csrf-token" content="([^"]+)"', body)
        if not match:
            raise AssertionError("page is missing a CSRF token")
        return match.group(1).decode("ascii")

    def review_from(self, body: bytes) -> str:
        match = re.search(rb'name="checkout_review"\s+value="([^"]+)"', body)
        if not match:
            raise AssertionError("page is missing an explicit checkout review")
        return match.group(1).decode("ascii")


def app_with_token(token: str = "admin-test-token"):
    return create_app(secret=b"unit-test-secret-value-32bytesxx", admin_token=token)


class CatalogTests(unittest.TestCase):
    def test_catalog_loads_leftover_eight_current_three(self):
        metadata = load_study_metadata()
        catalog = DigitalCatalog(metadata)
        self.assertEqual([sku.key for sku in catalog.published_skus()[:3]], ["cassette", "floppy", "vhs"])
        self.assertEqual(catalog.get("digital-cassette-v38").revision, "V38")
        self.assertEqual(catalog.get("digital-floppy-v22").revision, "V22")
        self.assertEqual(catalog.get("digital-vhs-v5").revision, "V5")
        self.assertTrue(all(sku.kind == "digital_study" for sku in catalog.all_skus()))

    def test_catalog_rejects_physical_proof(self):
        metadata = load_study_metadata()
        metadata["physical_proof"] = True
        with self.assertRaises(CatalogError):
            DigitalCatalog(metadata)

    def test_public_catalog_strips_source_paths_and_hashes(self):
        payload = DigitalCatalog().public_catalog()
        blob = json.dumps(payload)
        for fragment in ("release/", ".stl", ".3mf", "source_sha256", "renderer"):
            self.assertNotIn(fragment, blob)
        by_key = {item["key"]: item for item in payload}
        self.assertEqual(by_key["cassette"]["identity"], "Cassette")
        self.assertEqual(by_key["cassette"]["study_frame"], "cassette")
        self.assertEqual(by_key["cassette"]["study_image"], "/assets/study/cassette.png")
        self.assertEqual(by_key["floppy"]["study_image"], "/assets/study/floppy.png")
        self.assertEqual(by_key["vhs"]["study_image"], "/assets/study/vhs.png")
        self.assertEqual(by_key["current-three"]["study_frame"], "current-three")
        self.assertEqual(by_key["current-three"]["study_image"], "/assets/study/current-three.png")

    def test_unpublished_sku_hidden_from_public_catalog(self):
        catalog = DigitalCatalog()
        catalog.apply_overrides({"digital-floppy-v22": False})
        public_skus = [item["sku"] for item in catalog.public_catalog()]
        self.assertNotIn("digital-floppy-v22", public_skus)
        self.assertIn("digital-cassette-v38", public_skus)


class CartLogicTests(unittest.TestCase):
    def setUp(self):
        self.catalog = DigitalCatalog()
        self.cart = Cart()

    def test_add_merge_and_bounds(self):
        self.cart.add(self.catalog, "digital-cassette-v38", 1)
        self.cart.add(self.catalog, "digital-cassette-v38", 1)
        self.assertEqual(self.cart.items["digital-cassette-v38"], 2)
        with self.assertRaises(CartError):
            self.cart.add(self.catalog, "digital-cassette-v38", 2)
        with self.assertRaises(CartError):
            self.cart.add(self.catalog, "digital-cassette-v38", 0)

    def test_rejects_unpublished_unknown_and_physical(self):
        self.catalog.apply_overrides({"digital-vhs-v5": False})
        with self.assertRaises(CartError):
            self.cart.add(self.catalog, "digital-vhs-v5", 1)
        with self.assertRaises(CartError):
            self.cart.add(self.catalog, "not-a-real-sku", 1)
        physical = self.catalog.get("digital-cassette-v38")
        physical.kind = "physical_print"
        with self.assertRaises(CartError):
            self.cart.add(self.catalog, "digital-cassette-v38", 1)

    def test_remove_and_empty_checkout(self):
        self.cart.add(self.catalog, "digital-current-three-study", 1)
        self.cart.remove("digital-current-three-study")
        self.assertTrue(self.cart.is_empty())
        with self.assertRaises(CartError):
            self.cart.checkoutable(self.catalog)


class MerchPathTests(unittest.TestCase):
    def setUp(self):
        self.client = Client(app_with_token())

    def test_catalog_page_is_useful_and_honest(self):
        status, headers, body = self.client.get("/catalog")
        html = body.decode("utf-8")
        self.assertTrue(status.startswith("200"))
        self.assertIn("skip-link", html)
        self.assertIn("Published digital studies", html)
        self.assertIn("Add Cassette study", html)
        self.assertIn("Add Floppy study", html)
        self.assertIn("Add Mini VHS study", html)
        self.assertIn("Digital study only", html)
        self.assertIn("Digital study hold · no charge", html)
        self.assertIn("visually distinct", html)
        self.assertIn("C-69", html)
        self.assertIn("3.69 MB", html)
        self.assertIn("T-369", html)
        self.assertIn("study-crop is-object", html)
        self.assertIn("study-crop is-full", html)
        self.assertIn("/assets/study/cassette.png", html)
        self.assertIn("/assets/study/floppy.png", html)
        self.assertIn("/assets/study/vhs.png", html)
        self.assertIn("/assets/study/current-three.png", html)
        self.assertNotIn('href="/admin"', html)
        self.assertNotIn("Tweet", html)
        self.assertNotIn("stripe", html.lower())
        self.assertNotIn("Buy now and ship", html)
        self.assertIn("nosniff", headers["x-content-type-options"])
        self.assertIn("frame-ancestors 'none'", headers["content-security-policy"])
        self.assertIn("HttpOnly", headers["set-cookie"])
        self.assertIn("SameSite=Strict", headers["set-cookie"])

    def test_empty_cart_disables_checkout(self):
        status, _, body = self.client.get("/cart")
        html = body.decode("utf-8")
        self.assertTrue(status.startswith("200"))
        self.assertIn("The hold cart is empty", html)
        self.assertIn("Browse published studies", html)
        self.assertNotIn("Request digital hold", html)
        self.assertNotIn("confirm_digital_hold", html)
        self.assertNotIn('href="/admin"', html)

    def test_add_to_cart_and_checkout_without_spend(self):
        _, _, catalog = self.client.get("/catalog")
        csrf = self.client.csrf_from(catalog)
        status, headers, _ = self.client.post(
            "/cart",
            {"action": "add", "sku": "digital-cassette-v38", "qty": "1"},
            csrf=csrf,
        )
        self.assertTrue(status.startswith("303"))
        self.assertEqual(headers["location"], "/cart")
        status, _, cart_page = self.client.get("/cart")
        self.assertTrue(status.startswith("200"))
        cart_html = cart_page.decode("utf-8")
        self.assertIn("digital-cassette-v38", cart_html)
        self.assertIn("Cassette · digital hold", cart_html)
        self.assertIn("qty-stepper", cart_html)
        self.assertIn("This is a digital study hold, not a purchase", cart_html)
        csrf = self.client.csrf_from(cart_page)
        reviewed = self.client.review_from(cart_page)
        status, _, denied = self.client.post(
            "/checkout",
            {"action": "request", "contact": "bandmate", "note": "digital hold only",
             "checkout_review": reviewed},
            csrf=csrf,
        )
        self.assertTrue(status.startswith("400"))
        self.assertIn("not a purchase", denied.decode("utf-8"))
        csrf = self.client.csrf_from(denied)
        status, headers, _ = self.client.post(
            "/checkout",
            {
                "action": "request",
                "contact": "bandmate",
                "note": "digital hold only",
                "confirm_digital_hold": "1",
                "checkout_review": self.client.review_from(denied),
            },
            csrf=csrf,
        )
        self.assertTrue(status.startswith("303"))
        location = headers["location"]
        self.assertTrue(location.startswith("/hold/"))
        status, _, thanks = self.client.get(location)
        receipt = thanks.decode("utf-8")
        self.assertTrue(status.startswith("200"))
        self.assertIn("Nothing was printed, shipped, posted, or charged", receipt)
        self.assertIn("digital-cassette-v38", receipt)
        self.assertIn("Cassette", receipt)
        self.assertIn(location.rsplit("/", 1)[1], receipt)
        _, _, empty = self.client.get("/cart")
        self.assertIn("The hold cart is empty", empty.decode("utf-8"))

    def test_checkout_rejects_shipping_and_csrf_failures(self):
        _, _, catalog = self.client.get("/catalog")
        csrf = self.client.csrf_from(catalog)
        self.client.post("/cart", {"action": "add", "sku": "digital-floppy-v22", "qty": "1"}, csrf=csrf)
        _, _, cart_page = self.client.get("/cart")
        csrf = self.client.csrf_from(cart_page)
        status, _, body = self.client.post(
            "/checkout",
            {"action": "request", "shipping_address": "123 Fake St"},
            csrf=csrf,
        )
        self.assertTrue(status.startswith("403"))
        self.assertIn("Physical, payment, or pitch fields", body.decode("utf-8"))
        status, _, body = self.client.post("/checkout", {"action": "request", "note": "no csrf"})
        self.assertTrue(status.startswith("403"))

    def test_unpublished_product_is_not_public(self):
        admin = Client(self.client.app)
        _, _, login = admin.get("/admin/login")
        csrf = admin.csrf_from(login)
        status, headers, _ = admin.post("/admin/login", {"token": "admin-test-token"}, csrf=csrf)
        self.assertTrue(status.startswith("303"))
        _, _, desk = admin.get("/admin")
        csrf = admin.csrf_from(desk)
        admin.post("/admin/sku/digital-vhs-v5/unpublish", {}, csrf=csrf)
        shopper = Client(self.client.app)
        _, _, catalog = shopper.get("/api/catalog")
        skus = [item["sku"] for item in json.loads(catalog)["items"]]
        self.assertNotIn("digital-vhs-v5", skus)
        status, _, body = shopper.get("/product/digital-vhs-v5")
        self.assertTrue(status.startswith("404"))
        csrf = shopper.csrf_from(shopper.get("/catalog")[2])
        status, _, rejected = shopper.post(
            "/cart",
            {"action": "add", "sku": "digital-vhs-v5", "qty": "1"},
            csrf=csrf,
        )
        self.assertTrue(status.startswith("400"))
        self.assertIn("not available", rejected.decode("utf-8"))

    def test_admin_requires_token_and_csrf(self):
        _, _, login = self.client.get("/admin")
        self.assertIn("Sign in to manage", login.decode("utf-8"))
        csrf = self.client.csrf_from(login)
        status, _, denied = self.client.post("/admin/login", {"token": "wrong"}, csrf=csrf)
        self.assertTrue(status.startswith("401"))
        status, _, missing = self.client.post("/admin/sku/digital-cassette-v38/unpublish", {})
        self.assertTrue(status.startswith("403"))

    def test_empty_admin_token_never_signs_in(self):
        client = Client(app_with_token(""))
        _, _, login = client.get("/admin/login")
        csrf = client.csrf_from(login)
        status, _, body = client.post("/admin/login", {"token": ""}, csrf=csrf)
        self.assertTrue(status.startswith("403") or status.startswith("401"))
        self.assertNotIn("Study requests", body.decode("utf-8"))

    def test_product_pages_use_matching_study_crops(self):
        _, _, cassette = self.client.get("/product/digital-cassette-v38")
        html = cassette.decode("utf-8")
        self.assertIn("Cassette · V38", html)
        self.assertIn("study-crop is-object study-crop-product", html)
        self.assertIn("/assets/study/cassette.png", html)
        self.assertIn("this listing is the Cassette", html)
        self.assertIn("Add Cassette study to hold cart", html)
        _, _, combined = self.client.get("/product/digital-current-three-study")
        combined_html = combined.decode("utf-8")
        self.assertIn("study-crop is-full", combined_html)
        self.assertIn("All three current studies", combined_html)

    def test_hold_receipt_stays_on_the_owning_session(self):
        _, _, catalog = self.client.get("/catalog")
        csrf = self.client.csrf_from(catalog)
        self.client.post(
            "/cart",
            {"action": "add", "sku": "digital-floppy-v22", "qty": "1"},
            csrf=csrf,
        )
        _, _, cart_page = self.client.get("/cart")
        csrf = self.client.csrf_from(cart_page)
        _, headers, _ = self.client.post(
            "/checkout",
            {"action": "request", "confirm_digital_hold": "1",
             "checkout_review": self.client.review_from(cart_page)},
            csrf=csrf,
        )
        receipt = headers["location"]
        stranger = Client(self.client.app)
        status, _, body = stranger.get(receipt)
        self.assertTrue(status.startswith("404"))
        self.assertIn("not available in this merch session", body.decode("utf-8"))
        self.assertNotIn("digital-floppy-v22", body.decode("utf-8"))
        status, _, missing = self.client.get("/hold/0123456789abcdef")
        self.assertTrue(status.startswith("404"))
        self.assertIn("Nothing was charged", missing.decode("utf-8"))

    def test_public_path_blocks_print_files_and_traversal(self):
        blocked = (
            "/release/v9/stl/Rad_Dad_Cassette_v38_BINARY.stl",
            "/docs/previews/Rad_Dad_Current_Three_PETG_Material_Study.json",
            "/src/build_rad_dad_authentic_qr_v9.py",
            "/tools/render_current_three_material_study.py",
            "/assets/../../../release/v9/3mf/secret.3mf",
            "/product/../../admin",
            "/catalog/%2e%2e/release/v9/stl/x.stl",
            "/hold/../release/v9/stl/x.stl",
            "/hold/not-a-real-hold-id",
            "/assets/study/../release/v9/stl/x.stl",
            "/assets/study/cassette.stl",
        )
        for path in blocked:
            status, _, body = self.client.get(path)
            self.assertTrue(status.startswith("403"), path)
            self.assertTrue(body)

    def test_normalize_rejects_traversal(self):
        with self.assertRaises(SecurityError):
            normalize_request_path("/../release/v9/stl/x.stl")
        with self.assertRaises(SecurityError):
            normalize_request_path("/assets/%2e%2e%2fsrc/app.py")

    def test_material_study_image_is_the_leftover_asset(self):
        status, headers, body = self.client.get("/assets/material-study.png")
        self.assertTrue(status.startswith("200"))
        self.assertEqual(headers["content-type"], "image/png")
        self.assertEqual(body, STUDY_PNG.read_bytes())
        status, headers, combined = self.client.get("/assets/study/current-three.png")
        self.assertTrue(status.startswith("200"))
        self.assertEqual(headers["content-type"], "image/png")
        self.assertEqual(combined, STUDY_PNG.read_bytes())

    def test_study_crops_keep_the_named_object_dominant(self):
        from io import BytesIO
        import numpy as np
        from PIL import Image

        def counts(body: bytes) -> dict[str, int]:
            arr = np.asarray(Image.open(BytesIO(body)).convert("RGB"), dtype=np.int16)
            red, green, blue = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            return {
                "lime": int(((green > 140) & (green > red + 40) & (blue < 120)).sum()),
                "blue": int(((blue > 160) & (blue > green) & (red < 80)).sum()),
                "pink": int(((red > 180) & (red > blue + 40) & (green < 100)).sum()),
            }

        winners = {}
        for frame in ("cassette", "floppy", "vhs"):
            status, headers, body = self.client.get(f"/assets/study/{frame}.png")
            self.assertTrue(status.startswith("200"), frame)
            self.assertEqual(headers["content-type"], "image/png")
            tallies = counts(body)
            winners[frame] = max(tallies, key=tallies.get)
            self.assertGreater(tallies[winners[frame]], 8000, frame)
        self.assertEqual(winners, {"cassette": "lime", "floppy": "blue", "vhs": "pink"})

    def test_api_cart_accepts_csrf_header(self):
        _, _, catalog = self.client.get("/catalog")
        csrf = self.client.csrf_from(catalog)
        status, _, body = self.client.post(
            "/api/cart",
            {"action": "add", "sku": "digital-current-three-study", "qty": "1"},
            csrf=csrf,
            header_csrf=True,
        )
        self.assertTrue(status.startswith("200"))
        payload = json.loads(body)
        self.assertEqual(payload["count"], 1)
        self.assertTrue(payload["digital_only"])
        self.assertEqual(payload["items"][0]["identity"], "Current Three")

    def test_api_checkout_requires_hold_confirmation(self):
        _, _, catalog = self.client.get("/catalog")
        csrf = self.client.csrf_from(catalog)
        self.client.post(
            "/api/cart",
            {"action": "add", "sku": "digital-vhs-v5", "qty": "1"},
            csrf=csrf,
            header_csrf=True,
        )
        _, _, cart_page = self.client.get("/api/cart")
        reviewed = json.loads(cart_page)["checkout_review"]
        status, _, body = self.client.post(
            "/api/checkout",
            {"action": "request", "checkout_review": reviewed},
            csrf=csrf,
            header_csrf=True,
        )
        self.assertTrue(status.startswith("400"))
        self.assertIn("not a purchase", json.loads(body)["error"])
        _, _, cart_page = self.client.get("/api/cart")
        status, _, body = self.client.post(
            "/api/checkout",
            {"action": "request", "confirm_digital_hold": "1",
             "checkout_review": json.loads(cart_page)["checkout_review"]},
            csrf=csrf,
            header_csrf=True,
        )
        self.assertTrue(status.startswith("200"))
        payload = json.loads(body)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["digital_only"])
        self.assertFalse(payload["charged"])
        self.assertTrue(payload["receipt_path"].startswith("/hold/"))
        _, _, receipt = self.client.get(payload["receipt_path"])
        self.assertIn("Mini VHS", receipt.decode("utf-8"))

    def test_security_headers_cover_json_too(self):
        _, headers, _ = self.client.get("/api/catalog")
        for name in SECURITY_HEADERS:
            self.assertIn(name.lower(), headers)

    def test_phone_layout_keeps_44px_controls(self):
        status, _, body = self.client.get("/assets/app.css")
        css = body.decode("utf-8")
        self.assertTrue(status.startswith("200"))
        self.assertIn("min-height: 44px", css)
        self.assertIn("grid-template-columns: 1fr;", css)
        self.assertIn(".qty-stepper", css)
        self.assertIn("@media (max-width: 720px)", css)


if __name__ == "__main__":
    unittest.main()
