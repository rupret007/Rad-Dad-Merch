# NFC workflow: legacy archive

NFC is not part of the recommended Rad Dad Retro Riot v9 production workflow.
V9 uses a visible, strictly black-and-white 25.4 mm / 1-inch QR sticker that a
recipient can recognize and scan with the normal phone camera.

## Why NFC became legacy

Real-world testing exposed too many dependencies for a giveaway or keychain
product:

- Chip provenance and inconsistent tag quality.
- Correct NDEF formatting and write completion.
- Differences in iPhone and Android background scanning.
- Antenna coupling, phone position, and installation tolerance.
- Potential interference from nearby material or hardware.
- A second overlay or instruction needed to explain where to tap.

The QR workflow makes the action visible, removes programming, and allows every
finished piece to be tested with the same camera behavior the recipient will
use.

## Historical releases

The final NFC-oriented release remains available under
[`release/v7`](../release/v7) for reference and experimentation. The first
QR-first transition remains under [`release/v8`](../release/v8).

Do not use the v7 NFC instructions as the current batch-production procedure.
V9 is the recommended release and its generated pack is:

```text
release/v9/Rad_Dad_Retro_Riot_v9_Authenticity_QR_Print_Pack.zip
```

The supported sticker process is documented in
[QR_STICKERS.md](QR_STICKERS.md).

## Compatibility with existing prints

Existing v7 and v8 prints do not need to be discarded. Their protected 26-27 mm
interaction landings accept the v9 25.4 mm QR sticker directly.

The v9 models are still recommended for new prints because they add the latest
authenticity work:

- Cassette v38 directly preserves the audited narrow tape-entry edge and its
  asymmetric real-cassette transport apertures.
- Floppy v20 deepens rear and device-specific cues around the same QR landing.
- VHS v5 deepens rear and VHS-specific cues around the same QR landing.
- Trailer Swift v6 uses a friendly, funny expression while retaining the same
  QR-ready base envelope.

External envelopes and media-keychain dimensions remain unchanged. The v9
upgrade improves recognizability without increasing the products' size.
