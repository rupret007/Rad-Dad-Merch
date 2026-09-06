"""Session-owned receipt recovery and explicit withdrawal through real WSGI."""
from __future__ import annotations

import unittest
from test_digital_merch import Client, app_with_token


class HoldLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.app = app_with_token()
        self.owner = Client(self.app)
        self.other = Client(self.app)
        _, _, page = self.owner.get('/holds')
        self.csrf = self.owner.csrf_from(page)

    def checkout(self, client=None, sku='digital-cassette-v38', note='Synthetic receipt note'):
        client = client or self.owner
        _, _, page = client.get('/catalog')
        csrf = client.csrf_from(page)
        client.post('/cart', {'action': 'add', 'sku': sku, 'qty': '1'}, csrf)
        status, headers, _ = client.post('/checkout', {
            'action': 'request', 'confirm_digital_hold': '1',
            'contact': 'Synthetic contact', 'note': note,
        }, csrf)
        self.assertEqual(status, '303 See Other')
        return headers['location']

    def test_history_empty_navigation_and_session_limit_notice(self):
        status, headers, body = self.owner.get('/holds')
        self.assertEqual(status, '200 OK')
        self.assertEqual(headers['cache-control'], 'no-store')
        self.assertIn(b'No digital holds in this session yet', body)
        self.assertIn(b'Clearing cookies or restarting the desk removes access', body)
        self.assertIn(b'href="/holds">Your holds', body)
        self.assertEqual(len(self.app.store.requests), 0)

    def test_reopen_then_withdraw_keeps_receipt_and_updates_admin(self):
        path = self.checkout()
        before = self.app.store.requests[0]
        original = (before.request_id, before.created_at, before.contact, before.note, dict(before.items))
        _, _, history = self.owner.get('/holds')
        self.assertIn(path.encode(), history)
        self.assertIn(b'Cassette', history)
        self.assertNotIn(b'Synthetic contact', history)
        self.assertNotIn(b'Synthetic receipt note', history)
        _, _, receipt = self.owner.get(path)
        self.assertIn(b'Held for admin review', receipt)
        self.assertIn(b'confirm_withdraw', receipt)
        status, headers, _ = self.owner.post(path + '/withdraw', {'confirm_withdraw': '1'}, self.csrf)
        self.assertEqual(status, '303 See Other')
        self.assertEqual(headers['location'], path)
        _, _, receipt = self.owner.get(path)
        self.assertIn(b'Withdrawn', receipt)
        self.assertIn(b'Synthetic receipt note', receipt)
        self.assertIn(b'qty 1', receipt)
        self.assertNotIn(b'confirm_withdraw', receipt)
        self.assertNotIn(b'This request is held for admin review', receipt)
        self.assertEqual(original, (before.request_id, before.created_at, before.contact, before.note, dict(before.items)))
        self.assertEqual(before.status, 'withdrawn')
        _, _, history = self.owner.get('/holds')
        self.assertIn(b'Withdrawn', history)
        # Test-local admin view reports state but has no shopper withdrawal authority.
        _, _, page = self.other.get('/admin/login')
        admin_csrf = self.other.csrf_from(page)
        self.other.post('/admin/login', {'token': 'admin-test-token'}, admin_csrf)
        _, _, admin = self.other.get('/admin')
        self.assertIn(b'Withdrawn', admin)
        self.assertIn(before.request_id.encode(), admin)
        _, _, other_holds = self.other.get('/holds')
        self.assertNotIn(before.request_id.encode(), other_holds)

    def test_foreign_and_unknown_holds_are_indistinguishable(self):
        path = self.checkout()
        _, _, other = self.other.get('/holds')
        csrf = self.other.csrf_from(other)
        for method in ['GET', 'POST']:
            suffix = '/withdraw' if method == 'POST' else ''
            results = []
            for target in [path, '/hold/0123456789abcdef']:
                results.append(self.other.request(method, target + suffix, {'csrf': csrf, 'confirm_withdraw': '1'}))
            self.assertEqual(results[0][0], '404 Not Found')
            self.assertEqual(results[0][0], results[1][0])
            self.assertEqual(results[0][2], results[1][2])
            self.assertNotIn(b'Synthetic contact', results[0][2])
        self.assertEqual(self.app.store.requests[0].status, 'held')

    def test_csrf_confirmation_methods_and_extra_fields_cannot_withdraw(self):
        path = self.checkout()
        for csrf, data, expected in [
            (None, {'confirm_withdraw': '1'}, '403 Forbidden'),
            ('bad-token', {'confirm_withdraw': '1'}, '403 Forbidden'),
            (self.csrf, {}, '400 Bad Request'),
            (self.csrf, {'confirm_withdraw': '0'}, '400 Bad Request'),
            (self.csrf, {'confirm_withdraw': '1', 'status': 'held'}, '403 Forbidden'),
        ]:
            status, _, _ = self.owner.post(path + '/withdraw', data, csrf)
            self.assertEqual(status, expected)
            self.assertEqual(self.app.store.requests[0].status, 'held')
        for method in ['GET', 'HEAD', 'PUT', 'DELETE']:
            status, _, _ = self.owner.request(method, path + '/withdraw', {'csrf': self.csrf, 'confirm_withdraw': '1'})
            self.assertEqual(status, '403 Forbidden')
            self.assertEqual(self.app.store.requests[0].status, 'held')

    def test_repeated_withdrawal_is_idempotent_and_does_not_change_cart(self):
        path = self.checkout()
        self.owner.post('/cart', {'action': 'add', 'sku': 'digital-floppy-v22', 'qty': '2'}, self.csrf)
        self.owner.post(path + '/withdraw', {'confirm_withdraw': '1'}, self.csrf)
        stamp = self.app.store.requests[0].withdrawn_at
        self.owner.post(path + '/withdraw', {'confirm_withdraw': '1'}, self.csrf)
        self.assertEqual(self.app.store.requests[0].withdrawn_at, stamp)
        self.assertEqual(len(self.app.store.requests), 1)
        _, _, cart = self.owner.get('/api/cart')
        self.assertIn(b'"count":2', cart)
        self.assertTrue(self.app.store.catalog.get('digital-floppy-v22').published)

    def test_history_is_newest_first_and_survives_unpublication(self):
        first = self.checkout()
        second = self.checkout(sku='digital-floppy-v22')
        self.app.store.set_published('digital-cassette-v38', False)
        _, _, history = self.owner.get('/holds')
        self.assertLess(history.index(second.encode()), history.index(first.encode()))
        status, _, receipt = self.owner.get(first)
        self.assertEqual(status, '200 OK')
        self.assertIn(b'Cassette', receipt)
        self.assertEqual(self.owner.post(first + '/withdraw', {'confirm_withdraw': '1'}, self.csrf)[0], '303 See Other')

    def test_html_escaping_and_private_file_boundaries(self):
        path = self.checkout(note='<script>alert("fixture")</script>')
        _, _, receipt = self.owner.get(path)
        self.assertIn(b'&lt;script&gt;', receipt)
        self.assertNotIn(b'<script>alert', receipt)
        for path in ['/holds/../release/v9/model.stl', '/hold/0123456789abcdef/withdraw/extra', '/hold/0123456789abcdef/withdraw%252f..', '/api/holds']:
            self.assertEqual(self.owner.get(path)[0], '403 Forbidden')

    def test_new_browser_or_restarted_desk_cannot_recover_other_session_holds(self):
        path = self.checkout()
        self.assertNotIn(path.encode(), self.other.get('/holds')[2])
        self.assertEqual(self.other.get(path)[0], '404 Not Found')
        self.owner.app = app_with_token()
        self.assertIn(b'No digital holds in this session yet', self.owner.get('/holds')[2])
        self.assertEqual(self.owner.get(path)[0], '404 Not Found')


if __name__ == '__main__':
    unittest.main()
