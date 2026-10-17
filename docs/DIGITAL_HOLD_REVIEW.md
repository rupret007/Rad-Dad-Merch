# Hold exactly the studies you reviewed

The digital merch desk now binds each hold confirmation to the session's
reviewed studies, quantities, cart revision and current catalog details. A
different tab cannot silently substitute a study or change the requested
quantity between review and checkout. An old successful form also cannot
create another hold after an identical cart is refilled.

## Shopper recovery

If the review is missing or out of date, no hold is created and the cart is not
cleared. The existing cart page shows its current contents and a fresh-review
message. Valid optional contact and note text is retained safely on that page;
the confirmation checkbox is reset. Read the current studies and quantities,
then explicitly confirm again if they are right. There is no automatic retry.

If the cart is now empty or contains an unavailable study, checkout is absent.
Unavailable lines remain identifiable and removable. Unsent details stay
visible with an instruction to copy them before leaving the page. They are
not a saved draft: subsequent cart edits, reloads or navigation can discard
them. The existing hold history and withdrawal flow is unchanged.

Native HTML forms work without JavaScript. The cart-update enhancement and
its uncertain-response recovery remain as described in [DIGITAL_CART.md](DIGITAL_CART.md).

## API and security contract

1. Read `/api/cart` and show its `items` to the shopper. Retain the accompanying
   `checkout_review` for that displayed snapshot.
2. Submit that exact field to `/api/checkout` along with the existing valid
   session/CSRF and explicit `confirm_digital_hold` value. Do not fetch a new
   review silently just to submit an old display.
3. HTTP `409` with `code: cart_review_required` means no hold was created.
   `review_path: /cart` is a read-only recovery destination. Show current items
   and require fresh confirmation; do not automatically replay the request.
4. Existing invalid confirmation/eligibility failures remain `400`; CSRF,
   forbidden fields, oversized forms and other security failures remain `403`.
   A valid review never overrides eligibility or authorizes payment/printing.

The opaque review is a purpose-bound HMAC over the session identity, monotonic
cart revision and sorted item/catalog snapshot. It contains no contact/note
text. Successful cart changes and checkout clearing advance the revision;
ordinary reads and rejected mutations do not. All WSGI requests in the current
process share a lock, covering rendered rows/token and checkout validation,
request creation and cart clearing. This is not a multi-worker transaction,
persistent reservation, durable session, payment or fulfillment system.

## Evidence and handoff

Three real-WSGI regressions on unchanged main `fc73aa38` demonstrated an
unreviewed quantity, a different study, and a duplicate hold after refill.
The new review/security tests cover these cases, foreign/tampered/missing
reviews, metadata and availability changes, concurrent submissions, literal
text preservation, native/API success and existing security boundaries.

Run `python3 tools/verify_digital_merch.py` with the existing dependencies.
It includes the Python product/security tests and the unchanged 30-case Node
cart-transport suite. Browser proof exercises synthetic two-tab journeys at
320/390/1280 pixels with JavaScript both enabled and disabled. Exact tested
tip, actual final counts and hosted-run receipts belong in the draft PR and
coordination AFTER; do not infer deployment or physical proof from these tests.

No dependency, workflow, physical generator, sealed study/model/release asset,
QR destination or live service changes. Parked #2 stays untouched. One OPEN
DRAFT for Karen leftover + security; no merge, release, Pages, purchase, print,
post, send or credential action from this slice.

Made-with: Codex Astra Ultra
