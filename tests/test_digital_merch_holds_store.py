"""Session-owned hold history and withdrawal with synthetic desk state."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from digital_merch.catalog import DigitalCatalog
from digital_merch.store import MerchStore, StudyRequest


class HoldStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = MerchStore(
            secret=b"synthetic-hold-store-secret",
            admin_token="synthetic-admin-token",
            catalog=DigitalCatalog(),
        )
        self.owner = self.store.session(None)
        self.other = self.store.session(None)

    def add_hold(self, request_id="0123456789abcdef", *, session=None, created_at="2026-09-05T18:00:00+00:00"):
        request = StudyRequest(
            request_id=request_id,
            created_at=created_at,
            contact="Synthetic contact",
            note="Keep this digital study for review.",
            items={"digital-cassette-v38": 2, "digital-floppy-v22": 1},
            session_sid=(session or self.owner).sid,
        )
        return self.store.add_request(request)

    def test_existing_request_constructor_starts_with_a_held_receipt(self):
        request = self.add_hold()
        self.assertEqual(request.status, "held")
        self.assertIsNone(request.withdrawn_at)
        self.assertTrue(request.digital_only)

    def test_history_is_newest_inserted_first_and_only_for_the_owning_session(self):
        first = self.add_hold("1111111111111111")
        self.add_hold("2222222222222222", session=self.other)
        last = self.add_hold("3333333333333333", created_at="2026-09-04T18:00:00+00:00")
        self.assertEqual(self.store.owned_requests(self.owner), [last, first])
        self.assertEqual(
            [request.request_id for request in self.store.owned_requests(self.other)],
            ["2222222222222222"],
        )
        self.assertEqual(self.store.owned_requests(self.store.session(None)), [])

    def test_withdrawal_preserves_the_original_receipt_and_records_a_utc_time(self):
        request = self.add_hold()
        original = (
            request.request_id, request.created_at, request.contact, request.note,
            dict(request.items), request.session_sid, request.digital_only,
        )
        before = datetime.now(timezone.utc)
        result = self.store.withdraw_owned_request(self.owner, request.request_id)
        after = datetime.now(timezone.utc)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "withdrawn")
        self.assertIsNotNone(result.withdrawn_at)
        withdrawn_at = datetime.fromisoformat(result.withdrawn_at)
        self.assertEqual(withdrawn_at.utcoffset().total_seconds(), 0)
        self.assertLessEqual(before, withdrawn_at)
        self.assertLessEqual(withdrawn_at, after)
        self.assertEqual(
            (
                result.request_id, result.created_at, result.contact, result.note,
                result.items, result.session_sid, result.digital_only,
            ),
            original,
        )
        self.assertEqual(self.store.owned_request(self.owner, request.request_id), result)
        self.assertEqual(self.store.owned_requests(self.owner), [result])

    def test_duplicate_withdrawal_keeps_one_receipt_and_the_first_withdrawal_time(self):
        request = self.add_hold()
        self.store.withdraw_owned_request(self.owner, request.request_id)
        first_withdrawn_at = request.withdrawn_at
        replay = self.store.withdraw_owned_request(self.owner, request.request_id)
        self.assertEqual(replay.status, "withdrawn")
        self.assertEqual(replay.withdrawn_at, first_withdrawn_at)
        self.assertEqual(len(self.store.requests), 1)
        self.assertEqual(self.store.owned_requests(self.owner), [request])

    def test_other_sessions_and_unknown_ids_cannot_withdraw_an_existing_hold(self):
        request = self.add_hold()
        self.assertIsNone(self.store.withdraw_owned_request(self.other, request.request_id))
        self.assertIsNone(self.store.withdraw_owned_request(self.owner, "ffffffffffffffff"))
        self.assertEqual(request.status, "held")
        self.assertIsNone(request.withdrawn_at)
        self.assertEqual(self.store.owned_requests(self.other), [])

    def test_admin_session_does_not_gain_ownership_of_another_shoppers_hold(self):
        request = self.add_hold()
        self.other.admin = True
        self.assertEqual(self.store.owned_requests(self.other), [])
        self.assertIsNone(self.store.withdraw_owned_request(self.other, request.request_id))
        self.assertEqual(request.status, "held")

    def test_withdrawal_does_not_change_the_current_cart_or_catalog(self):
        request = self.add_hold()
        cart = self.store.cart_for(self.owner)
        cart.add(self.store.catalog, "digital-vhs-v5", 1)
        original_catalog = self.store.public_snapshot()
        self.store.withdraw_owned_request(self.owner, request.request_id)
        self.assertEqual(self.store.cart_for(self.owner).items, {"digital-vhs-v5": 1})
        self.assertEqual(self.store.public_snapshot(), original_catalog)

    def test_an_unpublished_study_can_still_be_withdrawn_without_losing_the_receipt(self):
        request = self.add_hold()
        self.store.set_published("digital-cassette-v38", False)
        result = self.store.withdraw_owned_request(self.owner, request.request_id)
        self.assertEqual(result.status, "withdrawn")
        self.assertEqual(result.items, {"digital-cassette-v38": 2, "digital-floppy-v22": 1})
        self.assertFalse(self.store.catalog.require_sku("digital-cassette-v38").published)


if __name__ == "__main__":
    unittest.main()
