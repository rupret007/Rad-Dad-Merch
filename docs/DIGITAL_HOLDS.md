# Digital holds

The digital merch desk lets a shopper hold a study for admin review. A hold
does not reserve a physical item or create a purchase, print, shipment, or
message.

## Find and withdraw a hold

1. Start `python3 tools/serve_digital_merch.py`, open the local `/catalog`, add a
   digital study to the cart, and explicitly confirm the digital hold at checkout.
2. Open **Your holds** from navigation to find this browser session's receipts,
   newest first. Each entry shows the study names, quantities, requested time,
   and status; contact information and notes appear only on its receipt.
3. Open a receipt. To withdraw it, check the confirmation and select
   **Withdraw digital hold**. The receipt and admin desk show **Withdrawn** and
   the receipt records the withdrawal time in UTC.

Withdrawal stops that request from waiting for admin review. It preserves the
receipt ID, study quantities, original request time, contact information, and
note. Retrying the withdrawal leaves the first withdrawal time intact. It does
not change the cart or catalog. To request a study again, create a new hold.
The complete flow works without JavaScript.

## Session limits

Holds and sessions are stored in the running server's memory. Restarting the
server clears them. Access requires the same session cookie; clearing it,
losing it, or using another browser removes access to those receipts. This is
temporary session history, not durable order history or a data-erasure feature.

Only the owning session can view or withdraw its receipt. An admin can review
all requests but does not gain permission to withdraw another session's hold.
Withdrawal requires a POST, the current session's CSRF token, and explicit
confirmation. Missing and foreign receipts use the same not-found response.
The public route allowlist still excludes physical release and generator files.

## Verification

```bash
python3 tools/verify_digital_merch.py
```

The verifier covers receipt creation, history ordering and isolation, confirmed
withdrawal, request-method and CSRF rejection, repeat submissions, catalog
unpublication, retained cart and receipt details, admin status, HTML escaping,
and lost-session/server-restart behavior. Existing release-integrity checks
continue to verify the sealed physical files and material-study provenance.
