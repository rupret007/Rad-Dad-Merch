"""A hold must match the cart actually reviewed, through the real WSGI app."""
from __future__ import annotations

import json
import unittest

from test_digital_merch import Client, app_with_token


CASS = 'digital-cassette-v38'
FLOPPY = 'digital-floppy-v22'


class ReviewedHoldTests(unittest.TestCase):
    def setUp(self):
        self.app = app_with_token()
        self.owner = Client(self.app)
        self.csrf = self.owner.csrf_from(self.owner.get('/catalog')[2])
        self.edit('add', CASS, 1)

    def edit(self, action, sku, qty):
        status, _, _ = self.owner.post('/api/cart', {
            'action': action, 'sku': sku, 'qty': str(qty),
        }, self.csrf)
        self.assertEqual(status, '200 OK')

    def review(self):
        return json.loads(self.owner.get('/api/cart')[2])

    def fields(self, review):
        fields = {'action': 'request', 'confirm_digital_hold': '1',
                  'contact': 'Synthetic bandmate', 'note': 'Keep my reviewed studies'}
        # On unchanged main the missing field must not mask the actual bug:
        # submit the ordinary form and observe it hold the wrong cart.
        if 'checkout_review' in review:
            fields['checkout_review'] = review['checkout_review']
        return fields

    def test_old_page_cannot_hold_quantity_changed_in_another_tab(self):
        reviewed = self.review()
        self.assertEqual(reviewed['items'][0]['qty'], 1)
        self.edit('set', CASS, 3)
        status, _, _ = self.owner.post('/checkout', self.fields(reviewed), self.csrf)
        self.assertEqual(status, '409 Conflict',
                         f'Unreviewed hold created: {[r.items for r in self.app.store.requests]}')
        self.assertEqual(self.app.store.requests, [])
        self.assertEqual(self.review()['items'][0]['qty'], 3)

    def test_api_cannot_substitute_a_different_study_after_review(self):
        reviewed = self.review()
        self.edit('remove', CASS, 0)
        self.edit('add', FLOPPY, 1)
        status, _, body = self.owner.post('/api/checkout', self.fields(reviewed), self.csrf)
        self.assertEqual(status, '409 Conflict',
                         f'Unreviewed hold created: {[r.items for r in self.app.store.requests]}')
        self.assertEqual(json.loads(body)['code'], 'cart_review_required')
        self.assertEqual(self.app.store.requests, [])
        self.assertEqual(self.review()['items'][0]['sku'], FLOPPY)

    def test_used_review_cannot_repeat_after_identical_cart_is_refilled(self):
        reviewed = self.review()
        self.assertEqual(self.owner.post('/checkout', self.fields(reviewed), self.csrf)[0],
                         '303 See Other')
        self.edit('add', CASS, 1)
        status, _, _ = self.owner.post('/checkout', self.fields(reviewed), self.csrf)
        self.assertEqual(status, '409 Conflict',
                         f'Stale form created duplicate holds: {len(self.app.store.requests)}')
        self.assertEqual(len(self.app.store.requests), 1)
        self.assertEqual(self.review()['count'], 1)


if __name__ == '__main__':
    unittest.main()
