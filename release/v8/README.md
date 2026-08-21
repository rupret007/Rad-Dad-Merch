# Rad Dad Retro Riot v8: QR Edition

**OLD MEDIA. LOUD BAND. ONE SCAN.**

This is the complete QR-first release of the Rad Dad cassette, floppy disk,
mini VHS, and Trailer Swift desk collectible. The proven v7 geometry is reused
byte-for-byte. A single visible 1-inch QR sticker now replaces the NFC tag,
programming step, and separate NFC overlay.

## Start here

| Need | File |
|---|---|
| Print on Avery 6450 or OnlineLabels OL1025 | [63-up PDF](guides/qr_stickers/Rad_Dad_QR_STICKERS_AVERY_6450_OL1025_63UP_US_LETTER.pdf) |
| Print on full-sheet sticker paper and hand cut | [35-up PDF](guides/qr_stickers/Rad_Dad_QR_STICKERS_HAND_CUT_35UP_US_LETTER.pdf) |
| Send artwork to a sticker vendor | [Individual SVG](guides/qr_stickers/Rad_Dad_1IN_QR_STICKER_VENDOR_MASTER.svg) |
| Check printer scaling first | [Calibration PDF](guides/qr_stickers/Rad_Dad_QR_STICKER_PRINT_CALIBRATION.pdf) |
| Install the labels | [QR setup guide](guides/QR_STICKER_SETUP.md) |
| Buy suitable stock | [Sticker sourcing guide](guides/STICKER_SOURCING.md) |
| Find each placement area | [Placement guide](guides/Rad_Dad_QR_STICKER_PLACEMENT_GUIDE.svg) |
| Print the models | Open the `3mf/` directory or use the universal files in `stl/` |

## QR specification

- Destination: `https://raddadband.com/tap/`
- Finished label: 25.4 mm / 1 inch round
- QR matrix: 29 x 29 modules, error correction Q
- Quiet zone: 4 modules on every side
- Printed QR square: 16.5 mm
- Module pitch: 0.446 mm
- Minimum model landing: 26.0 mm
- Artwork: black QR on white, 600 DPI and vector masters included

## Model geometry

V8 does not resize or remodel the collectibles. The copied STL and 3MF hashes
are recorded in `qa/MODEL_REUSE_PROVENANCE.json`; the v7 digital geometry
evidence is retained under `qa/v7_geometry_evidence/`.

## Distribution gate

Do not hand out a piece until its installed QR code opens the Rad Dad tap page
from the normal camera on both iPhone and Android. Repeat the scan after the
adhesive has cured for 24 hours.
