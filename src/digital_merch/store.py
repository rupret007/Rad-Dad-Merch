"""In-memory merch desk state for sessions, catalog overrides, and requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .cart import Cart
from .catalog import DigitalCatalog
from .security import RateLimit, Session, new_session


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
        return cart

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
