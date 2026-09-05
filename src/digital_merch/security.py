"""Public merch-path security: allowlists, sessions, CSRF, and sanitizing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import re
from secrets import compare_digest, token_hex, token_urlsafe
from typing import Iterable
from urllib.parse import unquote


SESSION_COOKIE = "rdm_session"
CSRF_HEADER = "HTTP_X_CSRF_TOKEN"
MAX_NOTE_CHARS = 280
MAX_CONTACT_CHARS = 120
LOGIN_WINDOW_SECONDS = 60
LOGIN_ATTEMPT_LIMIT = 5

BLOCKED_PATH_FRAGMENTS = (
    "..",
    "\\",
    "\x00",
    "release/",
    "/src/",
    "tools/",
    ".stl",
    ".3mf",
    ".zip",
    "bambu",
    "py_compile",
)

PUBLIC_EXACT_PATHS = {
    "/",
    "/catalog",
    "/cart",
    "/checkout",
    "/api/catalog",
    "/api/cart",
    "/api/checkout",
    "/assets/app.css",
    "/assets/app.js",
    "/assets/material-study.png",
}

ADMIN_EXACT_PATHS = {
    "/admin",
    "/admin/login",
    "/admin/logout",
}

PRODUCT_PATH = re.compile(r"^/product/([a-z0-9-]{3,64})$")
HOLD_PATH = re.compile(r"^/hold/([a-f0-9]{16})$")
STUDY_CROP_PATH = re.compile(r"^/assets/study/(cassette|floppy|vhs|current-three)\.png$")
ADMIN_SKU_PATH = re.compile(r"^/admin/sku/([a-z0-9-]{3,64})/(publish|unpublish)$")
ALLOWED_CHECKOUT_FIELDS = {"csrf", "note", "contact", "action", "confirm_digital_hold"}
DIGITAL_HOLD_CONFIRM_VALUES = {"1", "on", "yes"}

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self'; style-src 'self'; "
        "script-src 'self'; form-action 'self'; frame-ancestors 'none'; "
        "base-uri 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "interest-cohort=()",
    "Cache-Control": "no-store",
}

FORBIDDEN_CHECKOUT_FIELDS = (
    "shipping",
    "address",
    "printer",
    "bambu",
    "3mf",
    "stl",
    "price",
    "payment",
    "card",
    "stripe",
    "paypal",
    "pitch",
    "tweet",
    "post",
)


class SecurityError(ValueError):
    """Rejected public merch-path request."""


@dataclass
class Session:
    sid: str
    csrf: str
    admin: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RateLimit:
    hits: list[float] = field(default_factory=list)

    def allow(self, now: float, limit: int = LOGIN_ATTEMPT_LIMIT, window: int = LOGIN_WINDOW_SECONDS) -> bool:
        self.hits = [stamp for stamp in self.hits if now - stamp <= window]
        if len(self.hits) >= limit:
            return False
        self.hits.append(now)
        return True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_request_path(raw_path: str) -> str:
    if not isinstance(raw_path, str) or not raw_path:
        raise SecurityError("Missing path.")
    if any(fragment in raw_path for fragment in ("\x00", "\\")):
        raise SecurityError("Illegal path.")
    path = unquote(raw_path)
    if unquote(path) != path:
        raise SecurityError("Encoded path traversal is not allowed.")
    if not path.startswith("/") or path.startswith("//") or "/." in path or ".." in path:
        raise SecurityError("Path traversal is not allowed.")
    lowered = path.lower()
    if any(fragment in lowered for fragment in BLOCKED_PATH_FRAGMENTS):
        raise SecurityError("That merch path is not public.")
    return path


def classify_path(path: str) -> str:
    if (
        path in PUBLIC_EXACT_PATHS
        or PRODUCT_PATH.match(path)
        or HOLD_PATH.match(path)
        or STUDY_CROP_PATH.match(path)
    ):
        return "public"
    if path in ADMIN_EXACT_PATHS or ADMIN_SKU_PATH.match(path):
        return "admin"
    raise SecurityError("Unknown merch path.")


def product_sku_from_path(path: str) -> str | None:
    match = PRODUCT_PATH.match(path)
    return match.group(1) if match else None


def hold_id_from_path(path: str) -> str | None:
    match = HOLD_PATH.match(path)
    return match.group(1) if match else None


def study_frame_from_path(path: str) -> str | None:
    match = STUDY_CROP_PATH.match(path)
    return match.group(1) if match else None


def admin_sku_action_from_path(path: str) -> tuple[str, str] | None:
    match = ADMIN_SKU_PATH.match(path)
    if not match:
        return None
    return match.group(1), match.group(2)


def new_session() -> Session:
    return Session(sid=token_urlsafe(24), csrf=token_hex(16))


def sign_session_id(secret: bytes, sid: str) -> str:
    digest = hmac.new(secret, sid.encode("utf-8"), sha256).hexdigest()
    return f"v1.{sid}.{digest}"


def read_signed_session_id(secret: bytes, value: str | None) -> str | None:
    if not value or not value.startswith("v1."):
        return None
    try:
        _, sid, digest = value.split(".", 2)
    except ValueError:
        return None
    expected = hmac.new(secret, sid.encode("utf-8"), sha256).hexdigest()
    if not compare_digest(expected, digest):
        return None
    return sid


def parse_cookies(header: str | None) -> dict[str, str]:
    cookies: dict[str, str] = {}
    if not header:
        return cookies
    for part in header.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


def session_cookie(secret: bytes, sid: str) -> str:
    return (
        f"{SESSION_COOKIE}={sign_session_id(secret, sid)}; Path=/; HttpOnly; "
        "SameSite=Strict; Max-Age=43200"
    )


def expired_session_cookie() -> str:
    return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"


def require_csrf(session: Session, submitted: str | None) -> None:
    if not submitted or not compare_digest(session.csrf, submitted):
        raise SecurityError("CSRF token was missing or invalid.")


def admin_token_ok(configured: str, submitted: str | None) -> bool:
    if not configured:
        return False
    return bool(submitted) and compare_digest(configured, submitted)


def sanitize_text(value: object, *, max_chars: int, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SecurityError(f"{field} must be text.")
    cleaned = "".join(ch for ch in value.replace("\r", "").strip() if ch == "\n" or (ch.isprintable() and ch != "\x7f"))
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_chars:
        raise SecurityError(f"{field} is too long.")
    return cleaned


def reject_forbidden_fields(fields: Iterable[str]) -> None:
    lowered = {name.lower() for name in fields}
    for name in lowered:
        for banned in FORBIDDEN_CHECKOUT_FIELDS:
            if banned in name:
                raise SecurityError("Physical, payment, or pitch fields are not accepted.")


def checkout_fields(form: dict[str, str]) -> tuple[str, str, str]:
    reject_forbidden_fields(form)
    extra = set(form) - ALLOWED_CHECKOUT_FIELDS
    if extra:
        raise SecurityError("Unexpected checkout fields.")
    contact = sanitize_text(form.get("contact"), max_chars=MAX_CONTACT_CHARS, field="Contact")
    note = sanitize_text(form.get("note"), max_chars=MAX_NOTE_CHARS, field="Note")
    confirm = sanitize_text(form.get("confirm_digital_hold"), max_chars=8, field="Hold confirmation")
    return contact, note, confirm.lower()


def json_bytes(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
