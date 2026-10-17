"""Reviewed-cart security and recovery through actual local WSGI requests."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import escape
from html.parser import HTMLParser
import json
from threading import Barrier
import unittest

from test_digital_merch import Client, app_with_token


CASS = 'digital-cassette-v38'
FLOPPY = 'digital-floppy-v22'
CONTACT = 'Synthetic <bandmate> & "friend"'
NOTE = 'Keep <script>fixture</script> & this unsent note.'


class Forms(HTMLParser):
    """Inspect real form controls without depending on attribute order."""

    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.current = None
        self.textarea = None
        self.feed(body.decode('utf-8'))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = {'attrs': attrs, 'inputs': [], 'textareas': {}}
            self.forms.append(self.current)
        elif self.current is not None and tag == 'input':
            self.current['inputs'].append(attrs)
        elif self.current is not None and tag == 'textarea':
            self.textarea = attrs.get('name')
            self.current['textareas'][self.textarea] = ''

    def handle_data(self, data):
        if self.current is not None and self.textarea is not None:
            self.current['textareas'][self.textarea] += data

    def handle_endtag(self, tag):
        if tag == 'textarea':
            self.textarea = None
        elif tag == 'form':
            self.current = None
            self.textarea = None

    def checkout(self):
        return [form for form in self.forms if form['attrs'].get('action') == '/checkout']


class CheckoutReviewSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = app_with_token()
        self.owner = Client(self.app)
        self.csrf = self.owner.csrf_from(self.owner.get('/catalog')[2])
        self.edit('add', CASS, 1)

    def edit(self, action, sku=CASS, qty=1, client=None, csrf=None):
        status, _, body = (client or self.owner).post('/api/cart', {
            'action': action, 'sku': sku, 'qty': str(qty),
        }, csrf or self.csrf)
        self.assertEqual(status, '200 OK', body)
        return json.loads(body)

    def review(self, client=None):
        status, headers, body = (client or self.owner).get('/api/cart')
        self.assertEqual(status, '200 OK')
        self.assertEqual(headers['cache-control'], 'no-store')
        payload = json.loads(body)
        self.assertIsInstance(payload['checkout_review'], str)
        self.assertTrue(payload['checkout_review'])
        return payload

    def fields(self, reviewed=None, **changes):
        fields = {
            'action': 'request', 'confirm_digital_hold': '1',
            'contact': CONTACT, 'note': NOTE,
        }
        if reviewed is not None:
            fields['checkout_review'] = reviewed['checkout_review']
        fields.update(changes)
        return fields

    def assert_api_refused(self, fields, client=None, csrf=None, *,
                           expected_status='409 Conflict', expected_code='cart_review_required'):
        client = client or self.owner
        before = self.review(client)
        requests_before = list(self.app.store.requests)
        status, headers, body = client.post('/api/checkout', fields, csrf or self.csrf)
        self.assertEqual(status, expected_status, body)
        self.assertEqual(headers['content-type'], 'application/json')
        self.assertEqual(headers['cache-control'], 'no-store')
        payload = json.loads(body)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['code'], expected_code)
        self.assertEqual(payload['review_path'], '/cart')
        self.assertNotIn('contact', payload)
        self.assertNotIn('note', payload)
        self.assertNotIn('checkout_review', payload)
        for submitted in (fields.get('contact'), fields.get('note')):
            if submitted:
                self.assertNotIn(submitted, body.decode('utf-8'))
                self.assertNotIn(submitted, json.dumps(payload, ensure_ascii=False))
        self.assertEqual(self.app.store.requests, requests_before)
        self.assertEqual(self.review(client), before)
        return payload

    def assert_retained(self, body):
        html = body.decode('utf-8')
        self.assertIn(escape(CONTACT), html)
        self.assertIn(escape(NOTE), html)
        self.assertNotIn('<script>fixture</script>', html)
        self.assertNotIn('<bandmate>', html)
        self.assertNotIn('{{', html)

    def unpublish(self):
        admin = Client(self.app)
        csrf = admin.csrf_from(admin.get('/admin/login')[2])
        self.assertEqual(admin.post('/admin/login', {
            'token': 'admin-test-token',
        }, csrf)[0], '303 See Other')
        self.assertEqual(admin.post(f'/admin/sku/{CASS}/unpublish', {}, csrf)[0],
                         '303 See Other')

    def test_html_and_api_expose_same_explicit_hidden_review(self):
        reviewed = self.review()
        for path in ['/cart', '/checkout']:
            with self.subTest(path=path):
                status, headers, body = self.owner.get(path)
                self.assertEqual(status, '200 OK')
                self.assertEqual(headers['cache-control'], 'no-store')
                checkout = Forms(body).checkout()
                self.assertEqual(len(checkout), 1)
                controls = [item for item in checkout[0]['inputs']
                            if item.get('name') == 'checkout_review']
                self.assertEqual(len(controls), 1)
                self.assertEqual(controls[0].get('type'), 'hidden')
                self.assertEqual(controls[0]['value'], reviewed['checkout_review'])
                self.assertEqual(self.owner.review_from(body), reviewed['checkout_review'])
        self.assertNotIn(CONTACT, json.dumps(reviewed))
        self.assertNotIn(NOTE, json.dumps(reviewed))

    def test_missing_empty_tampered_and_malformed_review_are_not_authority(self):
        reviewed = self.review()
        original = reviewed['checkout_review']
        tampered = ('a' if original[0] != 'a' else 'b') + original[1:]
        candidates = [None, '', tampered, 'not-a-review', '雪', '<img src=x>', 'x' * 512]
        for candidate in candidates:
            with self.subTest(candidate=repr(candidate)[:60]):
                fields = self.fields()
                if candidate is not None:
                    fields['checkout_review'] = candidate
                self.assert_api_refused(fields)

    def test_oversized_review_preserves_existing_form_size_guard(self):
        reviewed = self.review()
        for path in ['/checkout', '/api/checkout']:
            with self.subTest(path=path):
                status, _, body = self.owner.post(path, self.fields(
                    checkout_review='x' * 4096,
                ), self.csrf)
                self.assertEqual(status, '403 Forbidden')
                self.assertIn(b'Form is too large.', body)
                self.assertEqual(self.app.store.requests, [])
                self.assertEqual(self.review(), reviewed)

    def test_foreign_review_is_refused_even_with_own_valid_csrf_and_same_cart(self):
        reviewed = self.review()
        other = Client(self.app)
        csrf = other.csrf_from(other.get('/catalog')[2])
        self.edit('add', client=other, csrf=csrf)
        self.assertNotEqual(self.review(other)['checkout_review'], reviewed['checkout_review'])
        self.assert_api_refused(self.fields(reviewed), other, csrf)

    def test_quantity_and_contents_changes_require_new_review_without_mutating_cart(self):
        for action, sku, qty in [('set', CASS, 2), ('add', FLOPPY, 1), ('remove', CASS, 0)]:
            reviewed = self.review()
            self.edit(action, sku, qty)
            with self.subTest(action=action):
                self.assert_api_refused(self.fields(reviewed))

    def test_cart_revision_changes_on_mutation_and_clear_but_not_reads(self):
        reviewed = self.review()
        for path in ['/cart', '/checkout', '/catalog', '/holds', '/api/cart']:
            self.owner.get(path)
        self.assertEqual(self.review()['checkout_review'], reviewed['checkout_review'])
        changed = self.edit('set', qty=2)
        self.assertNotEqual(changed['checkout_review'], reviewed['checkout_review'])
        self.assertEqual(self.review()['checkout_review'], changed['checkout_review'])
        self.assertEqual(self.owner.post('/api/checkout', self.fields(changed), self.csrf)[0],
                         '200 OK')
        empty = self.review()
        self.assertEqual(empty['count'], 0)
        self.assertNotEqual(empty['checkout_review'], changed['checkout_review'])
        self.assertEqual(len(self.app.store.requests), 1)

    def test_rejected_cart_mutations_do_not_rotate_review_or_change_contents(self):
        reviewed = self.review()
        for fields in [
            {'action': 'add', 'sku': CASS, 'qty': '4'},
            {'action': 'set', 'sku': CASS, 'qty': '-1'},
            {'action': 'set', 'sku': CASS, 'qty': 'not-a-number'},
            {'action': 'add', 'sku': 'missing-study', 'qty': '1'},
        ]:
            with self.subTest(fields=fields):
                self.assertEqual(self.owner.post('/api/cart', fields, self.csrf)[0],
                                 '400 Bad Request')
                self.assertEqual(self.review(), reviewed)
        self.assertEqual(self.owner.post('/api/cart', {
            'action': 'set', 'sku': CASS, 'qty': '2',
        }, 'wrong-csrf')[0], '403 Forbidden')
        self.assertEqual(self.review(), reviewed)

    def test_replaying_consumed_review_cannot_hold_identical_refill(self):
        reviewed = self.review()
        self.assertEqual(self.owner.post('/api/checkout', self.fields(reviewed), self.csrf)[0],
                         '200 OK')
        self.edit('add')
        self.assertNotEqual(self.review()['checkout_review'], reviewed['checkout_review'])
        self.assert_api_refused(self.fields(reviewed))
        self.assertEqual(len(self.app.store.requests), 1)

    def test_public_reviewed_details_changes_invalidate_old_review(self):
        sku = self.app.store.catalog.get(CASS)
        for field, changed in [
            ('title', 'Changed synthetic title'), ('identity', 'Changed identity'),
            ('revision', 'V-next-fixture'), ('color', 'Different fixture color'),
            ('material', 'Different fixture description'),
            ('description', 'A different synthetic study description'),
            ('study_frame', 'current-three'),
        ]:
            with self.subTest(field=field):
                reviewed = self.review()
                original = getattr(sku, field)
                try:
                    setattr(sku, field, changed)
                    self.assertNotEqual(self.review()['checkout_review'], reviewed['checkout_review'])
                    self.assert_api_refused(self.fields(reviewed))
                finally:
                    setattr(sku, field, original)

    def test_admin_unpublication_invalidates_review_without_hiding_cart_line(self):
        reviewed = self.review()
        self.unpublish()
        self.assert_api_refused(self.fields(reviewed))
        status, _, body = self.owner.get('/cart')
        self.assertEqual(status, '200 OK')
        self.assertIn(b'Unavailable', body)
        self.assertIn(CASS.encode(), body)
        forms = Forms(body)
        self.assertEqual(forms.checkout(), [])
        removes = [form for form in forms.forms if any(
            item.get('name') == 'action' and item.get('value') == 'remove'
            for item in form['inputs'])]
        self.assertTrue(any(any(item.get('name') == 'sku' and item.get('value') == CASS
                                for item in form['inputs']) for form in removes))

    def test_fresh_review_does_not_override_unavailable_or_nondigital_sku(self):
        sku = self.app.store.catalog.get(CASS)
        for field, disallowed in [
            ('published', False), ('digital_only', False), ('physical_proof', True),
            ('kind', 'unsupported'), ('fulfillment', 'unsupported'),
        ]:
            with self.subTest(field=field):
                original = getattr(sku, field)
                try:
                    setattr(sku, field, disallowed)
                    self.assert_api_refused(self.fields(self.review()),
                                            expected_status='400 Bad Request',
                                            expected_code='checkout_rejected')
                finally:
                    setattr(sku, field, original)

    def test_stale_html_preserves_escaped_details_and_requires_fresh_confirmation(self):
        reviewed = self.review()
        self.edit('set', qty=2)
        status, _, body = self.owner.post('/checkout', self.fields(reviewed), self.csrf)
        self.assertEqual(status, '409 Conflict')
        self.assert_retained(body)
        forms = Forms(body).checkout()
        self.assertEqual(len(forms), 1)
        inputs = {item.get('name'): item for item in forms[0]['inputs']}
        self.assertEqual(inputs['contact']['value'], CONTACT)
        self.assertEqual(forms[0]['textareas']['note'], NOTE)
        self.assertNotIn('checked', inputs['confirm_digital_hold'])
        self.assertIn('required', inputs['confirm_digital_hold'])
        self.assertEqual(inputs['checkout_review']['value'], self.review()['checkout_review'])
        self.assertNotEqual(inputs['checkout_review']['value'], reviewed['checkout_review'])
        self.assertEqual(self.app.store.requests, [])
        # Seeing the refreshed form does not request anything; a second explicit
        # confirmation is the only action that can create this reviewed hold.
        fresh = {'checkout_review': inputs['checkout_review']['value']}
        status, headers, _ = self.owner.post('/checkout', self.fields(fresh), self.csrf)
        self.assertEqual(status, '303 See Other')
        self.assertTrue(headers['location'].startswith('/hold/'))
        self.assertEqual(self.app.store.requests[0].items, {CASS: 2})
        self.assertEqual(self.app.store.requests[0].contact, CONTACT)
        self.assertEqual(self.app.store.requests[0].note, NOTE)

    def test_stale_html_sanitizes_whitespace_before_retaining_fields(self):
        reviewed = self.review()
        self.edit('set', qty=2)
        status, _, body = self.owner.post('/checkout', self.fields(
            reviewed, contact='  Synthetic\r\n  bandmate\t ', note='  Keep\x00\n this\t note.  ',
        ), self.csrf)
        self.assertEqual(status, '409 Conflict')
        form = Forms(body).checkout()[0]
        inputs = {item.get('name'): item for item in form['inputs']}
        self.assertEqual(inputs['contact']['value'], 'Synthetic bandmate')
        self.assertEqual(form['textareas']['note'], 'Keep this note.')
        self.assertEqual(self.app.store.requests, [])

    def test_stale_html_keeps_literal_placeholders_and_special_text_exactly(self):
        examples = [
            ('literal {{note}} {{csrf}}', 'literal {{contact}} {{disclaimer}}'),
            ('literal {{note}} {{csrf}} & "<bandmate>"',
             'literal {{contact}} {{disclaimer}} </textarea><script>fixture</script> & "'),
        ]
        for contact, note in examples:
            with self.subTest(contact=contact):
                reviewed = self.review()
                self.edit('set', qty=2 if reviewed['count'] == 1 else 1)
                current = self.review()
                status, _, body = self.owner.post('/checkout', self.fields(
                    reviewed, contact=contact, note=note,
                ), self.csrf)
                self.assertEqual(status, '409 Conflict')
                forms = Forms(body).checkout()
                self.assertEqual(len(forms), 1)
                inputs = {item.get('name'): item for item in forms[0]['inputs']}
                self.assertEqual(inputs['contact']['value'], contact)
                self.assertEqual(forms[0]['textareas']['note'], note)
                self.assertEqual(inputs['csrf']['value'], self.csrf)
                self.assertEqual(inputs['checkout_review']['value'], current['checkout_review'])
                self.assertNotIn('checked', inputs['confirm_digital_hold'])
                html = body.decode('utf-8')
                self.assertIn(escape(contact), html)
                self.assertIn(escape(note), html)
                self.assertNotIn('<bandmate>', html)
                self.assertNotIn('<script>fixture</script>', html)
                self.assertEqual(self.app.store.requests, [])
                self.assertEqual(self.review(), current)

    def test_successful_receipt_preserves_literal_fields_and_escapes_special_text(self):
        contact = 'literal {{note}} {{csrf}}'
        note = 'literal {{contact}} {{disclaimer}} </textarea><script>fixture</script>'
        _, _, cart_page = self.owner.get('/cart')
        reviewed = {'checkout_review': self.owner.review_from(cart_page)}
        status, headers, _ = self.owner.post('/checkout', self.fields(
            reviewed, contact=contact, note=note,
        ), self.csrf)
        self.assertEqual(status, '303 See Other')
        self.assertTrue(headers['location'].startswith('/hold/'))
        status, _, body = self.owner.get(headers['location'])
        self.assertEqual(status, '200 OK')
        self.assertIn(f'<dd>{escape(contact)}</dd>'.encode(), body)
        self.assertIn(f'<dd>{escape(note)}</dd>'.encode(), body)
        self.assertNotIn(b'<script>fixture</script>', body)
        self.assertNotIn(b'</textarea><script>', body)
        self.assertEqual(len(self.app.store.requests), 1)
        self.assertEqual(self.app.store.requests[0].contact, contact)
        self.assertEqual(self.app.store.requests[0].note, note)
        self.assertEqual(self.app.store.requests[0].items, {CASS: 1})
        self.assertEqual(self.review()['count'], 0)

    def test_empty_stale_html_keeps_unsent_details_but_cannot_checkout(self):
        reviewed = self.review()
        self.edit('remove', qty=0)
        status, _, body = self.owner.post('/checkout', self.fields(reviewed), self.csrf)
        self.assertEqual(status, '409 Conflict')
        self.assert_retained(body)
        self.assertIn(b'Your unsent details', body)
        self.assertIn(b'The hold cart is empty', body)
        self.assertEqual(Forms(body).checkout(), [])
        self.assertNotIn(b'confirm_digital_hold', body)
        self.assertEqual(self.app.store.requests, [])
        self.assertEqual(self.review()['count'], 0)

    def test_unavailable_stale_html_keeps_unsent_details_without_confirmation(self):
        reviewed = self.review()
        self.unpublish()
        status, _, body = self.owner.post('/checkout', self.fields(reviewed), self.csrf)
        self.assertEqual(status, '409 Conflict')
        self.assert_retained(body)
        self.assertIn(b'Your unsent details', body)
        self.assertIn(b'Unavailable', body)
        self.assertEqual(Forms(body).checkout(), [])
        self.assertNotIn(b'confirm_digital_hold', body)
        self.assertEqual(self.app.store.requests, [])
        self.assertEqual(self.review()['count'], 1)

    def test_json_rejection_never_echoes_private_submitted_text(self):
        self.assert_api_refused(self.fields(
            checkout_review='invalid', contact='private-contact-marker',
            note='private-note-marker',
        ))

    def test_csrf_and_forbidden_fields_still_precede_review_checks(self):
        reviewed = self.review()
        for path in ['/checkout', '/api/checkout']:
            for token in [None, 'wrong-csrf']:
                with self.subTest(path=path, csrf=token):
                    status, _, _ = self.owner.post(path, self.fields(), token)
                    self.assertEqual(status, '403 Forbidden')
            for forbidden in ['shipping_address', 'payment', 'pitch', 'unknown_field']:
                with self.subTest(path=path, forbidden=forbidden):
                    status, _, _ = self.owner.post(path, self.fields(**{
                        forbidden: 'fixture',
                    }), self.csrf)
                    self.assertEqual(status, '403 Forbidden')
        self.assertEqual(self.review(), reviewed)
        self.assertEqual(self.app.store.requests, [])

    def test_oversized_details_fail_security_without_retention_or_hold(self):
        reviewed = self.review()
        for field, value in [('contact', 'contact-marker-' * 10), ('note', 'note-marker-' * 30)]:
            for path in ['/checkout', '/api/checkout']:
                with self.subTest(field=field, path=path):
                    status, _, body = self.owner.post(path, self.fields(**{field: value}), self.csrf)
                    self.assertEqual(status, '403 Forbidden')
                    self.assertNotIn(value.encode(), body)
                    self.assertEqual(self.app.store.requests, [])
                    self.assertEqual(self.review(), reviewed)

    def test_fresh_html_review_and_explicit_native_confirmation_create_exact_hold(self):
        self.edit('add', FLOPPY, 2)
        _, _, body = self.owner.get('/cart')
        reviewed = {'checkout_review': self.owner.review_from(body)}
        status, headers, _ = self.owner.post('/checkout', self.fields(reviewed), self.csrf)
        self.assertEqual(status, '303 See Other')
        self.assertTrue(headers['location'].startswith('/hold/'))
        self.assertEqual(len(self.app.store.requests), 1)
        self.assertEqual(self.app.store.requests[0].items, {CASS: 1, FLOPPY: 2})
        self.assertEqual(self.review()['count'], 0)

    def test_fresh_api_review_and_header_csrf_create_exact_hold(self):
        reviewed = self.review()
        status, _, body = self.owner.post('/api/checkout', self.fields(reviewed), self.csrf,
                                          header_csrf=True)
        self.assertEqual(status, '200 OK')
        payload = json.loads(body)
        self.assertTrue(payload['ok'])
        self.assertFalse(payload['charged'])
        self.assertTrue(payload['digital_only'])
        self.assertEqual(self.app.store.requests[0].items, {CASS: 1})
        self.assertEqual(self.review()['count'], 0)

    def test_two_submissions_of_one_review_create_only_one_hold(self):
        reviewed = self.review()
        cookie = self.owner.cookie
        ready = Barrier(2, timeout=5)

        def submit():
            tab = Client(self.app)
            tab.cookie = cookie
            ready.wait()
            return tab.post('/api/checkout', self.fields(reviewed), self.csrf)

        with ThreadPoolExecutor(max_workers=2) as pool:
            attempts = [pool.submit(submit) for _ in range(2)]
            results = [attempt.result(timeout=10) for attempt in attempts]
        self.assertEqual(sorted(result[0] for result in results), ['200 OK', '409 Conflict'])
        refused = next(result for result in results if result[0] == '409 Conflict')
        self.assertEqual(json.loads(refused[2])['code'], 'cart_review_required')
        self.assertEqual(len(self.app.store.requests), 1)
        self.assertEqual(self.app.store.requests[0].items, {CASS: 1})
        self.assertEqual(self.review()['count'], 0)


if __name__ == '__main__':
    unittest.main()
