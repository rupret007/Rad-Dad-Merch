"""In-memory merch desk state for sessions, catalog overrides, and requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import hmac
from secrets import compare_digest
from threading import RLock
from typing import Any

from .cart import Cart
from .catalog import DigitalCatalog
from .security import RateLimit, Session, json_bytes, new_session


@dataclass
class StudyRequest:
    request_id: str
    created_at: str
    contact: str
    note: str
    items: dict[str, int]
    session_sid: str
    digital_only: bool = True
    status: str = "held"
    withdrawn_at: str | None = None


@dataclass
class MerchStore:
    secret: bytes
    admin_token: str
    catalog: DigitalCatalog
    sessions: dict[str, Session] = field(default_factory=dict)
    carts: dict[str, Cart] = field(default_factory=dict)
    published_overrides: dict[str, bool] = field(default_factory=dict)
    requests: list[StudyRequest] = field(default_factory=list)
    login_limits: dict[str, RateLimit] = field(default_factory=dict)
    # The desk is in-memory and single-process. Its WSGI boundary holds this
    # lock across review generation or validation and the resulting mutation.
    lock: Any = field(default_factory=RLock, repr=False, compare=False)

    def session(self, sid: str | None) -> Session:
        if sid and sid in self.sessions:
            return self.sessions[sid]
        session = new_session()
        self.sessions[session.sid] = session
        self.carts[session.sid] = Cart()
        return session

    def cart_for(self, session: Session) -> Cart:
        return self.carts.setdefault(session.sid, Cart())

    def replace_cart(self, session: Session, cart: Cart) -> Cart:
        self.carts[session.sid] = cart
        session.cart_revision += 1
        return cart

    def checkout_review(self, session: Session) -> str:
        cart = self.cart_for(session)
        snapshot = {
            "purpose": "digital-hold-review-v1",
            "session": session.sid,
            "revision": session.cart_revision,
            "items": [
                [sku, qty, self.catalog.require_sku(sku).public_dict()]
                for sku, qty in sorted(cart.items.items())
            ],
        }
        # No optional contact/note, private asset paths or signing material is
        # exposed. A cleared/refilled identical cart has a different revision.
        return hmac.new(self.secret, json_bytes(snapshot), sha256).hexdigest()

    def review_matches(self, session: Session, submitted: str | None) -> bool:
        if (not isinstance(submitted, str) or len(submitted) != 64
                or any(char not in "0123456789abcdef" for char in submitted)):
            return False
        return compare_digest(self.checkout_review(session), submitted)

    def set_published(self, sku_id: str, published: bool) -> None:
        self.catalog.require_sku(sku_id)
        self.published_overrides[sku_id] = published
        self.catalog.apply_overrides({sku_id: published})

    def add_request(self, request: StudyRequest) -> StudyRequest:
        self.requests.append(request)
        return request

    def owned_request(self, session: Session, request_id: str) -> StudyRequest | None:
        for request in self.requests:
            if request.request_id == request_id and request.session_sid == session.sid:
                return request
        return None

    def owned_requests(self, session: Session) -> list[StudyRequest]:
        return [request for request in reversed(self.requests) if request.session_sid == session.sid]

    def withdraw_owned_request(self, session: Session, request_id: str) -> StudyRequest | None:
        request = self.owned_request(session, request_id)
        if request is None:
            return None
        if request.status == "held":
            request.status = "withdrawn"
            request.withdrawn_at = datetime.now(timezone.utc).isoformat()
        return request

    def login_allowed(self, client_key: str, now: float | None = None) -> bool:
        bucket = self.login_limits.setdefault(client_key, RateLimit())
        stamp = now if now is not None else datetime.now(timezone.utc).timestamp()
        return bucket.allow(stamp)

    def public_snapshot(self) -> dict[str, Any]:
        return {
            "disclaimer": self.catalog.disclaimer,
            "physical_proof": False,
            "digital_only": True,
            "items": self.catalog.public_catalog(),
        }
