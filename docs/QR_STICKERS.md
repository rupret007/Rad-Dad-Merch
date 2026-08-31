# V9 QR sticker production

## Production decision

Rad Dad Retro Riot v9 uses one visible 25.4 mm / 1-inch QR sticker as the
supported handoff mechanism. The models remain durable one-color prints; the
separate label provides the contrast a camera needs without an AMS, filament
change, or unreliable shadow-based 3D code.

Preferred production is pure black modules on matte white. The same v9 pack
also ships an official pure process-red (`#FF0000`) on white fallback, generated
by the existing `qr_artwork_v9` path, for printers that are out of black ink.
That fallback is not a second destination, a decorative color treatment, or a
second merch app.

NFC is now a legacy experiment, not a production dependency.

## Permanent destination

```text
https://raddadband.com/qr/
```

The code is static and the route is controlled by Rad Dad. Update shows, music,
videos, and campaigns on the landing page instead of replacing distributed
stickers.

## Fit across all four products

V9 deepens authentic device details without changing the proven sticker fit:

| Product | Model revision | Protected landing | Sticker | Radial clearance |
|---|---|---:|---:|---:|
| Compact cassette | v38 | 26.0 mm | 25.4 mm | 0.3 mm |
| 3.5-inch floppy | v22 | 26.0 mm | 25.4 mm | 0.3 mm |
| Mini VHS | v5 | 26.0 mm | 25.4 mm | 0.3 mm |
| Trailer Swift | v16 | 27.0 mm | 25.4 mm | 0.8 mm |

Cassette v38 directly preserves the audited narrow tape-entry edge from the
successful earlier body, including its stepped shell and asymmetric transport
apertures. Floppy v22 retains its developed rear cues and adds a larger,
heavier `3.69 MB` front capacity mark. VHS v5 deepens its rear and
device-specific cues around, not through, the unchanged QR landing. Trailer
Swift v16 retains the protected pocket beneath the solid circular base.

## Non-negotiable artwork rules

Preferred black masters:

- Use pure black modules on a solid white field.
- Use no gray, tint, gradient, texture, transparency, or decorative color.
- Keep any `RAD DAD` or `SCAN ME` wording outside the protected QR field and
  render it in the same ink as the modules.

Official red fallback, only when black ink is unavailable:

- Use the supplied `Rad_Dad_QR_RED_` files. Do not pick a different red.
- Modules and cut guides are pure process red `#FF0000` on solid white.
- Print as color, never grayscale or a printer-selected red.
- Approve only after the red calibration page scans from two phones.

Shared rules for both colors:

- Preserve a four-module white quiet zone on every side.
- Keep the printed QR square at 16.5 mm. Never make it smaller.
- Keep every module square, crisp, separated, and approximately 0.446 mm wide.
- Put no logo, lightning bolt, text, border, or artwork inside the QR square or
  quiet zone.
- Do not round, invert, distress, stylize, or partially cover modules.
- Use matte white adhesive stock to reduce glare.

The QR is intentionally plain. At this physical size, scan reliability is more
important than decorative customization.

## Generated production files

The completed v9 pack is generated at:

```text
release/v9/Rad_Dad_Retro_Riot_v9_Authenticity_QR_Print_Pack.zip
```

The pack includes three print layouts. A layout proves geometry, not adhesive
durability; qualify the stock separately before installing a label on a
finished piece.

| Route | Preferred black file | Official red fallback |
|---|---|---|
| Individual vendor | `Rad_Dad_QR_1IN_VENDOR_MASTER.svg`, PNG, and PDF | `Rad_Dad_QR_RED_1IN_VENDOR_MASTER.svg`, PNG, and PDF |
| Precut 63-up geometry | `Rad_Dad_QR_AVERY_6450_OL1025_63UP_US_LETTER.pdf` | `Rad_Dad_QR_RED_AVERY_6450_OL1025_63UP_US_LETTER.pdf` |
| FedEx Office full sheet | `Rad_Dad_QR_FEDEX_OFFICE_FULL_SHEET_48UP_US_LETTER.pdf` | `Rad_Dad_QR_RED_FEDEX_OFFICE_FULL_SHEET_48UP_US_LETTER.pdf` |
| Calibration | `Rad_Dad_QR_PRINT_CALIBRATION_US_LETTER.pdf` | `Rad_Dad_QR_RED_PRINT_CALIBRATION_US_LETTER.pdf` |

The release also includes a placement guide and physical QC checklist. Send a
vendor the SVG or PDF master, never a screenshot. Black remains the preferred
production color. Use the red files only when black ink is unavailable.

Avery 6450 is removable-adhesive proof-only matte paper. Every giveaway,
keychain, or carry-production piece requires permanent adhesive. Use the same
63-up geometry for a finished piece only with a documented permanent,
weatherproof matte-white OL1025-compatible material, or have the individual
master professionally printed on permanent matte-white vinyl. Confirm the
actual material and adhesive specification before printing: layout compatibility
does not make removable stock permanent.

## Home-printer workflow

1. Confirm that the label stock matches the printer technology.
2. Choose stock for the job. Avery 6450 removable labels are proof-only; an
   installed or carried piece requires permanent, weatherproof matte-white
   stock.
3. Print the calibration page on ordinary paper first.
4. Open the supplied PDF in a PDF reader.
5. Choose **Actual Size**, **100%**, or **No Scaling**.
6. Disable fit-to-page, shrink, enlargement, borderless scaling, and photo
   enhancement.
7. Select the highest available monochrome or black-text quality for preferred
   black masters. If printing a `Rad_Dad_QR_RED_` file, select color rather
   than grayscale.
8. Print one proof and let the ink or toner settle completely.
9. Measure the 25.4 mm circle and the calibration reference.
10. Scan the proof before committing sticker stock.

The 63-up file is only for the specified precut geometry. Avery 6450 may prove
alignment and scanning, but its removable adhesive is not production stock.
Use a permanent, weatherproof OL1025-compatible material for finished pieces,
or use the dedicated full-sheet file for uncut permanent adhesive stock.

## FedEx Office workflow

Provide the dedicated FedEx Office full-sheet PDF and these written
instructions:

```text
Print US Letter at Actual Size / 100%.
Do not fit, shrink, enlarge, crop, or use borderless scaling.
Print solid black on matte white adhesive stock.
If black ink is unavailable, use the official Rad_Dad_QR_RED_ full-sheet file
and print as color, not grayscale.
Do not laminate or apply a gloss coating.
Produce one proof sheet before the full order.
```

Ask the associate to confirm the final stock before printing. If the location
does not carry matte white full-sheet adhesive material, ask whether it accepts
customer-supplied laser-safe label stock. Do not substitute glossy photo paper,
clear labels, metallic stock, colored stock, or textured material.

Before leaving the counter:

1. Measure one finished 25.4 mm circle.
2. Scan QR codes from the top, center, and bottom of the proof sheet.
3. Confirm that each opens exactly `https://raddadband.com/qr/`.
4. Reject scaling, clipped circles, broken modules, banding, weak black, or
   excessive toner shine.

## Cutting and installation

1. Scan the sheet before cutting.
2. Cut on the circular guide without entering the white QR quiet zone.
3. Inspect the model landing for ridges, loose filament, oil, or dust.
4. Clean the landing with 70% isopropyl alcohol and let it dry completely.
5. Center the sticker inside the registration landing without stretching it.
6. Press from the center outward to avoid wrinkles or bubbles.
7. Hold firm pressure for 30 seconds.
8. Scan immediately after installation.
9. Let the adhesive cure for 24 hours.
10. Carry-test the finished item and scan again.

| Product | Sticker location |
|---|---|
| Cassette | Centered on the protected flat rear landing |
| Floppy | Centered inside the rear faux-hub registration ring |
| VHS | Centered inside the rear registration ring |
| Trailer Swift | Centered inside the pocket beneath the circular base |

## Mandatory physical scan QC

A valid digital QR does not guarantee a valid physical sticker. Every
production batch must pass all of the following:

- The finished circle measures 25.4 mm.
- The QR square remains 16.5 mm and the quiet zone is intact.
- Black modules are dense, square, and free of gaps or toner flaking. If using
  the official red fallback, modules are solid `#FF0000` with no gray or mixed
  red, and the red calibration page has already scanned from two phones.
- White areas are clean and free of background pattern or adhesive show-through.
- Top, center, and bottom sheet samples scan before cutting.
- Every installed product scans after application.
- Finished pieces scan on at least one current iPhone and Android phone.
- Scans succeed in normal indoor light and from multiple approach angles.
- Every scan resolves to `https://raddadband.com/qr/`.
- Finished pieces still scan after 24-hour cure and carry testing.

Quarantine and replace any label that scans slowly or inconsistently. Do not
assume another person's phone will compensate for a marginal print.

## Material recommendations

| Stage | Stock | Notes |
|---|---|---|
| Fit proof | Ordinary white paper | Confirm size and scan behavior before using adhesive stock |
| Precut proof | Avery 6450 removable matte-white paper labels | Confirm 63-up alignment and scanning only; do not install on a carry piece |
| Home prototype | Matte white full-sheet adhesive paper | Protect only after scanning; clear tape is a temporary proof method |
| Home batch | Weatherproof matte white adhesive stock | Better abrasion and moisture resistance with lower glare |
| Production batch | Professionally printed matte white vinyl | Request crisp black output, permanent adhesive, and a physical proof |

Clear tape may protect an ordinary-paper prototype, but it can introduce glare,
bubbles, edge lift, and adhesive creep. It is not the recommended finish for
giveaways or keychain carry.

## Release compatibility

V9 is the recommended release. Existing v7 NFC-era and v8 QR-era prints can use
the v9 sticker artwork because their 26-27 mm interaction landings share the
same 25.4 mm label fit. They do not gain the v9 authenticity improvements unless
the models themselves are reprinted.
