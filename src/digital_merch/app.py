"""WSGI merch desk: shopper catalog/cart plus a locked admin."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from secrets import token_hex
from typing import Callable, Iterable
from urllib.parse import parse_qs

from .cart import CartError
from .catalog import CatalogError, DigitalCatalog, STUDY_IMAGE_PATH
from .security import (
    CSRF_HEADER,
    DIGITAL_HOLD_CONFIRM_VALUES,
    SECURITY_HEADERS,
    SESSION_COOKIE,
    SecurityError,
    admin_sku_action_from_path,
    admin_token_ok,
    checkout_fields,
    classify_path,
    expired_session_cookie,
    hold_id_from_path,
    json_bytes,
    normalize_request_path,
    parse_cookies,
    product_sku_from_path,
    read_signed_session_id,
    require_csrf,
    session_cookie,
)
from .store import MerchStore, StudyRequest


WEB_ROOT = Path(__file__).resolve().parent / "web"
STATIC_ROOT = WEB_ROOT / "static"
TEMPLATE_ROOT = WEB_ROOT / "templates"


class MerchApp:
    def __init__(self, store: MerchStore) -> None:
        self.store = store

    def __call__(self, environ: dict, start_response: Callable) -> Iterable[bytes]:
        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        if method == "HEAD":
            method = "GET"
            environ = dict(environ)
            environ["_HEAD"] = True
        try:
            path = normalize_request_path(environ.get("PATH_INFO") or "/")
            kind = classify_path(path)
        except SecurityError as exc:
            return self._send(start_response, "403 Forbidden", "text/plain; charset=utf-8", str(exc).encode("utf-8"))

        session = self.store.session(
            read_signed_session_id(self.store.secret, parse_cookies(environ.get("HTTP_COOKIE")).get(SESSION_COOKIE))
        )
        try:
            status, content_type, body, extra_headers = self._dispatch(method, path, kind, session, environ)
        except SecurityError as exc:
            status, content_type, body, extra_headers = (
                "403 Forbidden",
                "text/html; charset=utf-8",
                self._html_error(session, "Request blocked", str(exc)),
                [],
            )
        except CartError as exc:
            if path.startswith("/api/"):
                status, content_type, body, extra_headers = (
                    "400 Bad Request",
                    "application/json",
                    json_bytes({"ok": False, "error": str(exc)}),
                    [],
                )
            else:
                status, content_type, body, extra_headers = (
                    "400 Bad Request",
                    "text/html; charset=utf-8",
                    self._render_cart(session, error=str(exc)),
                    [],
                )
        except CatalogError as exc:
            status, content_type, body, extra_headers = (
                "400 Bad Request",
                "text/plain; charset=utf-8",
                str(exc).encode("utf-8"),
                [],
            )

        headers = [("Content-Type", content_type), ("Content-Length", str(len(body)))]
        headers.extend((key, value) for key, value in SECURITY_HEADERS.items())
        headers.append(("Set-Cookie", session_cookie(self.store.secret, session.sid)))
        headers.extend(extra_headers)
        if environ.get("_HEAD"):
            body = b""
        start_response(status, headers)
        return [body]

    def _dispatch(self, method: str, path: str, kind: str, session, environ):
        if kind == "admin" and path != "/admin/login" and not session.admin:
            if path.startswith("/api/") or method != "GET":
                raise SecurityError("Admin authentication is required.")
            return (
                "401 Unauthorized",
                "text/html; charset=utf-8",
                self._render_admin_login(session, error="Sign in to manage the digital merch desk."),
                [],
            )

        if method == "GET" and path in {"/", "/catalog"}:
            return "200 OK", "text/html; charset=utf-8", self._render_catalog(session), []
        if method == "GET" and path in {"/cart", "/checkout"}:
            return "200 OK", "text/html; charset=utf-8", self._render_cart(session), []
        if method == "GET" and path.startswith("/product/"):
            return self._product_page(session, product_sku_from_path(path) or "")
        if method == "GET" and path.startswith("/hold/"):
            return self._hold_page(session, hold_id_from_path(path) or "")
        if method == "GET" and path == "/assets/app.css":
            return self._static("app.css", "text/css; charset=utf-8")
        if method == "GET" and path == "/assets/app.js":
            return self._static("app.js", "text/javascript; charset=utf-8")
        if method == "GET" and path == "/assets/material-study.png":
            return self._study_image()
        if method == "GET" and path == "/api/catalog":
            return "200 OK", "application/json", json_bytes(self.store.public_snapshot()), []
        if method == "GET" and path == "/api/cart":
            return "200 OK", "application/json", json_bytes(self._cart_payload(session)), []
        if method == "GET" and path == "/admin":
            return "200 OK", "text/html; charset=utf-8", self._render_admin(session), []
        if method == "GET" and path == "/admin/login":
            if session.admin:
                return self._redirect("/admin")
            return "200 OK", "text/html; charset=utf-8", self._render_admin_login(session), []

        form = _read_form(environ) if method == "POST" else {}
        submitted_csrf = form.get("csrf") or environ.get(CSRF_HEADER)
        if method == "POST":
            require_csrf(session, submitted_csrf)

        if method == "POST" and path in {"/cart", "/api/cart"}:
            return self._mutate_cart(session, form, json_mode=path.startswith("/api/"))
        if method == "POST" and path in {"/checkout", "/api/checkout"}:
            return self._checkout(session, form, json_mode=path.startswith("/api/"))
        if method == "POST" and path == "/admin/login":
            return self._admin_login(session, form, environ)
        if method == "POST" and path == "/admin/logout":
            session.admin = False
            return self._redirect("/admin/login")
        action = admin_sku_action_from_path(path)
        if method == "POST" and action:
            sku_id, verb = action
            self.store.set_published(sku_id, verb == "publish")
            return self._redirect("/admin")

        raise SecurityError("Method not allowed on this merch path.")

    def _mutate_cart(self, session, form: dict[str, str], *, json_mode: bool):
        cart = self.store.cart_for(session)
        action = form.get("action") or "add"
        sku_id = form.get("sku") or ""
        qty = _parse_qty(form.get("qty") or "1")
        if action == "add":
            cart.add(self.store.catalog, sku_id, qty)
        elif action == "set":
            cart.set_qty(self.store.catalog, sku_id, qty)
        elif action == "remove":
            cart.remove(sku_id)
        else:
            raise SecurityError("Unknown cart action.")
        self.store.replace_cart(session, cart)
        if json_mode:
            return "200 OK", "application/json", json_bytes(self._cart_payload(session)), []
        return self._redirect("/cart")

    def _checkout(self, session, form: dict[str, str], *, json_mode: bool):
        cart = self.store.cart_for(session)
        cart.checkoutable(self.store.catalog)
        contact, note, confirm = checkout_fields(form)
        if confirm not in DIGITAL_HOLD_CONFIRM_VALUES:
            raise CartError("Confirm this is a digital study hold, not a purchase.")
        request = StudyRequest(
            request_id=token_hex(8),
            created_at=datetime.now(timezone.utc).isoformat(),
            contact=contact,
            note=note,
            items=dict(cart.items),
            session_sid=session.sid,
        )
        self.store.add_request(request)
        self.store.replace_cart(session, cart.__class__())
        receipt_path = f"/hold/{request.request_id}"
        payload = {
            "ok": True,
            "request_id": request.request_id,
            "receipt_path": receipt_path,
            "digital_only": True,
            "physical_proof": False,
            "charged": False,
        }
        if json_mode:
            return "200 OK", "application/json", json_bytes(payload), []
        return self._redirect(receipt_path)

    def _admin_login(self, session, form: dict[str, str], environ):
        client = str(environ.get("REMOTE_ADDR") or "unknown")
        if not self.store.login_allowed(client):
            raise SecurityError("Too many admin sign-in attempts.")
        if not admin_token_ok(self.store.admin_token, form.get("token")):
            return (
                "401 Unauthorized",
                "text/html; charset=utf-8",
                self._render_admin_login(session, error="Admin token rejected."),
                [],
            )
        session.admin = True
        return self._redirect("/admin")

    def _product_page(self, session, sku_id: str):
        sku = self.store.catalog.get(sku_id)
        if sku is None or not sku.published:
            return (
                "404 Not Found",
                "text/html; charset=utf-8",
                self._html_error(session, "Study not available", "That digital study is not on the public merch desk."),
                [],
            )
        return "200 OK", "text/html; charset=utf-8", self._render_product(session, sku), []

    def _hold_page(self, session, request_id: str):
        request = self.store.owned_request(session, request_id)
        if request is None:
            return (
                "404 Not Found",
                "text/html; charset=utf-8",
                self._html_error(
                    session,
                    "Hold not on this desk",
                    "That digital study hold is not available in this merch session. Nothing was charged.",
                ),
                [],
            )
        return "200 OK", "text/html; charset=utf-8", self._render_hold(session, request), []

    def _static(self, name: str, content_type: str):
        path = (STATIC_ROOT / name).resolve()
        if not str(path).startswith(str(STATIC_ROOT.resolve())) or not path.is_file():
            raise SecurityError("Static merch asset is not public.")
        return "200 OK", content_type, path.read_bytes(), [("Cache-Control", "no-store")]

    def _study_image(self):
        path = STUDY_IMAGE_PATH.resolve()
        if path != STUDY_IMAGE_PATH.resolve() or not path.is_file():
            raise SecurityError("Material study image is not available.")
        return "200 OK", "image/png", path.read_bytes(), [("Cache-Control", "no-store")]

    def _redirect(self, location: str):
        return "303 See Other", "text/plain; charset=utf-8", b"", [("Location", location)]

    def _cart_payload(self, session) -> dict:
        cart = self.store.cart_for(session)
        return {
            "items": cart.lines(self.store.catalog),
            "count": cart.line_count(),
            "empty": cart.is_empty(),
            "csrf": session.csrf,
            "digital_only": True,
        }

    def _page(self, session, title: str, body: str, *, flash: str = "", error: str = "") -> bytes:
        cart_count = self.store.cart_for(session).line_count()
        admin_nav = '<a href="/admin">Admin</a>' if session.admin else ""
        template = (TEMPLATE_ROOT / "base.html").read_text(encoding="utf-8")
        html = (
            template.replace("{{title}}", escape(title))
            .replace("{{csrf}}", escape(session.csrf))
            .replace("{{cart_count}}", str(cart_count))
            .replace("{{admin_nav}}", admin_nav)
            .replace("{{flash}}", _banner(flash, "notice") + _banner(error, "error"))
            .replace("{{body}}", body)
            .replace("{{disclaimer}}", escape(self.store.catalog.disclaimer))
        )
        return html.encode("utf-8")

    def _render_catalog(self, session) -> bytes:
        cards = "".join(_sku_card(sku, session.csrf) for sku in self.store.catalog.published_skus())
        empty = ""
        if not cards:
            empty = (
                '<p class="empty-state" role="status">No digital studies are published. '
                "The merch desk is not pitching or selling a physical print.</p>"
            )
        body = (TEMPLATE_ROOT / "catalog.html").read_text(encoding="utf-8")
        body = body.replace("{{cards}}", cards or empty)
        body = body.replace("{{study_title}}", escape(self.store.catalog.study_title))
        return self._page(session, "Digital merch desk", body)

    def _render_product(self, session, sku) -> bytes:
        body = (TEMPLATE_ROOT / "product.html").read_text(encoding="utf-8")
        body = (
            body.replace("{{sku}}", escape(sku.sku))
            .replace("{{title}}", escape(sku.title))
            .replace("{{identity}}", escape(sku.identity))
            .replace("{{revision}}", escape(sku.revision))
            .replace("{{color}}", escape(sku.color))
            .replace("{{material}}", escape(sku.material))
            .replace("{{description}}", escape(sku.description))
            .replace("{{extents}}", escape(_extents_label(sku.extents_mm)))
            .replace("{{study_crop}}", _study_crop(sku, kind="product"))
            .replace("{{csrf}}", escape(session.csrf))
        )
        return self._page(session, sku.title, body)

    def _render_cart(self, session, error: str = "", notice: str = "") -> bytes:
        cart = self.store.cart_for(session)
        if cart.is_empty():
            rows = (
                '<p class="empty-state" role="status">The hold cart is empty. Add a published '
                "digital study to request a hold. Checkout stays disabled until then.</p>"
            )
            checkout = (
                '<p><a class="button-link" href="/catalog">Browse published studies</a></p>'
            )
        else:
            rows = "".join(_cart_row(line, session.csrf) for line in cart.lines(self.store.catalog))
            checkout = (TEMPLATE_ROOT / "checkout_form.html").read_text(encoding="utf-8")
            checkout = checkout.replace("{{csrf}}", escape(session.csrf))
        body = (TEMPLATE_ROOT / "cart.html").read_text(encoding="utf-8")
        body = (
            body.replace("{{rows}}", rows)
            .replace("{{checkout_block}}", checkout)
            .replace("{{disabled_class}}", "is-empty" if cart.is_empty() else "")
        )
        return self._page(session, "Digital merch cart", body, flash=notice, error=error)

    def _render_hold(self, session, request: StudyRequest) -> bytes:
        lines = []
        for sku_id, qty in request.items.items():
            sku = self.store.catalog.get(sku_id)
            identity = sku.identity if sku else sku_id
            title = sku.title if sku else sku_id
            lines.append(
                f"<li class='hold-line'><strong>{escape(identity)}</strong>"
                f"<p>{escape(title)} · {escape(sku_id)} · qty {int(qty)}</p></li>"
            )
        contact = escape(request.contact) if request.contact else "not given"
        note = escape(request.note) if request.note else "none"
        body = (TEMPLATE_ROOT / "hold.html").read_text(encoding="utf-8")
        body = (
            body.replace("{{request_id}}", escape(request.request_id))
            .replace("{{created_at}}", escape(request.created_at))
            .replace("{{lines}}", "".join(lines))
            .replace("{{contact}}", contact)
            .replace("{{note}}", note)
        )
        return self._page(session, "Digital study hold", body)

    def _render_admin_login(self, session, error: str = "") -> bytes:
        body = (TEMPLATE_ROOT / "admin_login.html").read_text(encoding="utf-8")
        body = body.replace("{{csrf}}", escape(session.csrf))
        return self._page(session, "Merch admin", body, error=error)

    def _render_admin(self, session) -> bytes:
        sku_rows = "".join(_admin_sku_row(sku, session.csrf) for sku in self.store.catalog.all_skus())
        if self.store.requests:
            requests = "".join(_admin_request_row(request) for request in reversed(self.store.requests))
        else:
            requests = '<p class="empty-state" role="status">No digital study requests yet.</p>'
        body = (TEMPLATE_ROOT / "admin.html").read_text(encoding="utf-8")
        body = body.replace("{{sku_rows}}", sku_rows).replace("{{requests}}", requests).replace("{{csrf}}", escape(session.csrf))
        return self._page(session, "Merch admin", body)

    def _html_error(self, session, title: str, message: str) -> bytes:
        body = f"<section class='panel'><h1>{escape(title)}</h1><p>{escape(message)}</p></section>"
        return self._page(session, title, body, error=message)

    def _send(self, start_response, status, content_type, body, extra_headers=None):
        headers = [("Content-Type", content_type), ("Content-Length", str(len(body)))]
        headers.extend((key, value) for key, value in SECURITY_HEADERS.items())
        headers.extend(extra_headers or [])
        start_response(status, headers)
        return [body]


def create_app(
    *,
    secret: bytes | None = None,
    admin_token: str = "",
    catalog: DigitalCatalog | None = None,
) -> MerchApp:
    store = MerchStore(
        secret=secret or token_hex(32).encode("utf-8"),
        admin_token=admin_token,
        catalog=catalog or DigitalCatalog(),
    )
    return MerchApp(store)


def _read_form(environ: dict) -> dict[str, str]:
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError as exc:
        raise SecurityError("Invalid form length.") from exc
    if length < 0 or length > 4096:
        raise SecurityError("Form is too large.")
    raw = environ["wsgi.input"].read(length) if length else b""
    parsed = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _parse_qty(raw: str) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise CartError("Quantity must be a whole number.") from exc


def _banner(message: str, kind: str) -> str:
    if not message:
        return ""
    return f'<p class="banner banner-{kind}" role="status">{escape(message)}</p>'


def _extents_label(extents: list[float] | None) -> str:
    if not extents:
        return "Combined Current Three study — not a production envelope"
    return f"{extents[0]:.3f} x {extents[1]:.3f} x {extents[2]:.3f} mm study envelope"


def _study_crop(sku, *, kind: str) -> str:
    zoom = "is-full" if sku.study_frame == "current-three" else "is-object"
    caption = (
        "Shared Current Three study at true relative size."
        if sku.study_frame == "current-three"
        else f"Cropped leftover Current Three study so this listing is the {escape(sku.identity)}."
    )
    alt = (
        "Digital PETG material study of the current Rad Dad cassette, floppy, and mini VHS at true relative size"
        if sku.study_frame == "current-three"
        else (
            f"{escape(sku.identity)} digital study cropped from the shared Current Three "
            "PETG material render"
        )
    )
    return f"""
<figure class="study-crop {zoom} study-crop-{kind}" style="--pos:{escape(sku.study_position)}; --accent:{escape(sku.color)}">
  <div class="study-crop-window">
    <img src="/assets/material-study.png" width="1800" height="1100" alt="{alt}">
  </div>
  <figcaption>{caption} Digital render only.</figcaption>
</figure>
"""


def _sku_card(sku, csrf: str) -> str:
    return f"""
<article class="card" style="--accent:{escape(sku.color)}; --pos:{escape(sku.study_position)}">
  {_study_crop(sku, kind="card")}
  <p class="eyebrow">{escape(sku.identity)} · {escape(sku.revision)}</p>
  <h2><a href="/product/{escape(sku.sku)}">{escape(sku.title)}</a></h2>
  <p class="chip">Digital study hold · no charge</p>
  <p>{escape(sku.description)}</p>
  <p class="meta">{escape(_extents_label(sku.extents_mm))}</p>
  <form method="post" action="/cart" class="stack add-form">
    <input type="hidden" name="csrf" value="{escape(csrf)}">
    <input type="hidden" name="action" value="add">
    <input type="hidden" name="sku" value="{escape(sku.sku)}">
    <input type="hidden" name="qty" value="1">
    <button type="submit">Add {escape(sku.identity)} study</button>
  </form>
</article>
"""


def _cart_row(line: dict[str, object], csrf: str) -> str:
    sku = escape(str(line["sku"]))
    qty = int(line["qty"])
    minus = max(qty - 1, 0)
    plus = min(qty + 1, 3)
    plus_disabled = " disabled" if qty >= 3 else ""
    minus_label = "Remove" if qty == 1 else "Decrease quantity"
    return f"""
<li class="cart-line">
  <div>
    <p class="eyebrow">{escape(str(line["identity"]))} · digital hold</p>
    <strong>{escape(str(line["title"]))}</strong>
    <p>{escape(str(line["revision"]))} · {sku} · no charge</p>
  </div>
  <div class="cart-actions">
    <form method="post" action="/cart" class="qty-stepper">
      <input type="hidden" name="csrf" value="{escape(csrf)}">
      <input type="hidden" name="action" value="set">
      <input type="hidden" name="sku" value="{sku}">
      <button type="submit" name="qty" value="{minus}" aria-label="{minus_label}">−</button>
      <span aria-live="polite">{qty}</span>
      <button type="submit" name="qty" value="{plus}" aria-label="Increase quantity"{plus_disabled}>+</button>
    </form>
    <form method="post" action="/cart">
      <input type="hidden" name="csrf" value="{escape(csrf)}">
      <input type="hidden" name="action" value="remove">
      <input type="hidden" name="sku" value="{sku}">
      <button type="submit" class="ghost">Remove</button>
    </form>
  </div>
</li>
"""


def _admin_sku_row(sku, csrf: str) -> str:
    verb = "unpublish" if sku.published else "publish"
    label = "Unpublish" if sku.published else "Publish"
    state = "published" if sku.published else "unpublished"
    return f"""
<tr>
  <td>{escape(sku.sku)}</td>
  <td>{escape(sku.title)}</td>
  <td>{escape(sku.revision)}</td>
  <td><span class="state state-{state}">{state}</span></td>
  <td>
    <form method="post" action="/admin/sku/{escape(sku.sku)}/{verb}">
      <input type="hidden" name="csrf" value="{escape(csrf)}">
      <button type="submit">{label}</button>
    </form>
  </td>
</tr>
"""


def _admin_request_row(request: StudyRequest) -> str:
    items = ", ".join(f"{escape(sku)} × {qty}" for sku, qty in request.items.items())
    contact = escape(request.contact) if request.contact else "not given"
    note = escape(request.note) if request.note else "—"
    return f"""
<article class="request">
  <p class="eyebrow">{escape(request.request_id)} · {escape(request.created_at)}</p>
  <p>Contact: {contact}</p>
  <p>Items: {items}</p>
  <p>Note: {note}</p>
</article>
"""
