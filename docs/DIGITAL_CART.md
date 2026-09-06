# Digital cart updates and recovery

An added study or quantity change is a digital cart edit. It does not create a
hold, payment, print job, shipment, or message.

## Review the outcome

With JavaScript available, the desk shows **Updating your hold cart** and pauses
other cart edits and hold submission until the response arrives. Successful
catalog edits update the cart count. Successful edits on `/cart` or `/checkout`
load the current cart so displayed quantities match the server.

A rejected edit, such as exceeding three of one study, shows a visible error
and restores the available controls. The quantity buttons keep the exact value
the shopper selected. Buttons that were already disabled remain disabled.

If the connection fails, the response cannot be read, or the response takes
longer than ten seconds, the desk cannot confirm whether the change happened.
It does not resend the change. Cart edits and hold submission remain paused.
Choose **Review current hold cart** to load the current session's cart, inspect
its quantities, then decide what to do next. That link only reads the cart.
If the connection is still unavailable, return to that link when it recovers.

The status is visible and announced to assistive technology. Errors and
uncertain results move keyboard focus to the status and its recovery link.
Without JavaScript or the required browser APIs, ordinary form navigation
continues to work with the pressed quantity button's value.

## Scope and verification

This prevents automatic retry of an uncertain cart POST in the current page.
It does not promise a transaction across multiple tabs, prevent every manual
repeat, or make the server's in-memory session durable. Creating a digital hold
still requires the existing explicit checkout confirmation; receipt history
and withdrawal are unchanged.

Run `python3 tools/verify_digital_merch.py` with Python 3.9+ and Node.js 18+.
The verifier includes the existing shopper/admin/session/security tests and
dependency-free JavaScript transport tests. Browser verification uses a local
synthetic session and can drop a response after the server applies the edit,
checking that review shows the actual quantity without another POST.

Physical release files, study assets and provenance, QR destination, provider
boundaries, and publication controls are unchanged.
