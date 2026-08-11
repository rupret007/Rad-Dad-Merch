# Changelog

## v9.1 - Floppy Capacity Legibility - 2026-08-11

- Advanced the 3.5-inch floppy from v20 to v21 after physical-print feedback
  showed that the lower-right `3.69 MB` capacity mark was too difficult to read.
- Increased the mark from 10.20 x 2.30 mm to 12.60 x 2.85 mm, strengthened the
  bold stroke geometry, and moved it slightly inward for cleaner label spacing.
- Kept the exact `44.360 x 36.916 x 4.130 mm` envelope, 6.0 mm keyring bore,
  shutter, label hierarchy, rear mechanics, and 25.4 mm QR landing unchanged.
- Updated the release builder, printing guidance, validation gate, and current
  three-device plate workflow for the v21 floppy.

## v9 - Authenticity + QR Edition - 2026-08-09

### Authenticity restoration

- Promoted v9 as the recommended production release while preserving v8 and v7
  as historical QR and NFC archives.
- Advanced the compact cassette to v38 using the exact watertight v36 body that
  produced the successful physical reference print. Its narrow tape-entry edge,
  stepped shell, and asymmetric head, capstan, guide, and pinch-roller apertures
  are inherited directly rather than reconstructed as face decoration.
- Moved only the cassette eyelet zone inward to the approved compact envelope.
  The deformation is zero at the tape-entry edge, preserving that audited
  transport geometry while retaining the proven 6 mm bore and rear landing.
- Advanced the 3.5-inch floppy to v20 with deeper rear hub, shutter-track,
  shell-seam, write-protect, and density cues around the existing circular QR
  landing.
- Advanced the mini VHS to v5 with stronger reel, tape-path, door, latch,
  insertion, shell, and rear-device cues around the existing circular QR
  landing.
- Advanced Trailer Swift to v6 with friendlier eyes, relaxed brows, and a goofy
  singing grin so the character reads as funny and punk rather than angry or
  scary.
- Preserved the collection details `C-69`, `3.69 MB`, and `T-369` without
  allowing the easter eggs or Rad Dad branding to replace defining hardware.

### Fit and construction

- Kept all four external envelopes unchanged: cassette
  `58.162 x 30.260 x 6.685 mm`, floppy `44.360 x 36.916 x 4.130 mm`, VHS
  `65.800 x 31.900 x 7.000 mm`, and Trailer Swift
  `45.000 x 45.000 x 64.400 mm`.
- Kept the reinforced cassette, floppy, and VHS keyring eyelets and their 6 mm
  openings unchanged.
- Kept the protected 26 mm media landings and 27 mm Trailer Swift base landing
  unchanged for exact 25.4 mm / 1-inch QR stickers.
- Confined the authenticity work to the existing product envelopes so v9 does
  not increase pocket bulk, plate usage, or keyring reach.

### Black-and-white QR production

- Replaced the colored/styled sticker presentation with strictly black-and-white
  QR artwork on matte white adhesive stock.
- Preserved a 29 x 29 error-correction-Q matrix, four-module white quiet zone,
  16.5 mm printed QR square, and approximately 0.446 mm module pitch.
- Added individual vendor masters, an exact 63-up US Letter sheet for Avery
  6450 and OnlineLabels OL1025, and a dedicated FedEx Office full-sheet file.
- Standardized all print instructions on Actual Size / 100% with fit-to-page,
  shrinking, enlargement, and photo optimization disabled.
- Required physical measurement and scan QC before cutting, after installation,
  after adhesive cure, and before distribution.
- Set the generated release archive path to
  `release/v9/Rad_Dad_Retro_Riot_v9_Authenticity_QR_Print_Pack.zip`.
- Retained NFC documentation only as a legacy reference; NFC is not part of the
  recommended v9 production workflow.

## v8 - QR Edition - 2026-08-09

- Replaced the production NFC workflow with one visible 1-inch QR sticker.
- Preserved every v7 STL and 3MF byte-for-byte; no model was resized or remodeled.
- Added a scan-first black-and-white QR for `https://raddadband.com/tap/` with
  error correction Q, four-module quiet zone, and approximately 0.446 mm modules.
- Added vendor-ready SVG, 600 DPI PNG, and exact-size PDF artwork.
- Added an exact 63-up US Letter sheet for Avery 6450 and OnlineLabels OL1025.
- Added a 35-up hand-cut sheet, print calibration page, placement guide,
  sourcing guide, installation guide, and QR-specific physical QC checklist.
- Added model-reuse provenance, v7 geometry evidence, manifest, SHA-256 sums,
  deterministic release ZIP, and automated v8 integrity verification.
- Marked the v7 NFC release as a historical archive rather than deleting it.

## 0.4.0 - 2026-08-09 - Retro Riot v7: Micro Replica Edition

### Final products

- Finalized four one-color micro replicas: Rad Dad Compact Cassette v37, Rad
  Dad 3.5-Inch Floppy v19, Rad Dad Mini VHS v4, and Trailer Swift v5 Punk Desk
  Toy.
- Preserved the compact cassette, floppy, and VHS envelopes while exaggerating
  defining mechanical details enough to remain recognizable at keychain scale.
- Kept `RAD DAD` prominent without replacing the hardware that identifies each
  original format.

### Authenticity and construction

- Rebuilt the cassette face with unequal tape packs, broad six-lobe drive hubs,
  a deeper center tape window, five clean blind transport recesses, a visible
  pressure pad, shell hardware, and a restrained `C-69` marking alongside the
  traditional `90` designation.
- Reworked the floppy with a dominant upper shutter, writable label treatment,
  write-protect and density details, developed front and rear shell features,
  and the readable `3.69 MB` capacity joke.
- Replaced the VHS's cassette-like shared reel treatment with separate reel
  windows, six-rib hubs, visible tape coils, a central label zone, a
  full-width dust cover, latch, insertion arrow, `VHS` mark, and `T-369` detail.
- Rebuilt Trailer Swift as a one-piece, three-dimensional punk collectible with
  an oversized expressive head, flame-shaped hair, short toy proportions,
  broad shoes, faux spring neck, an integrated angular electric guitar, rear
  vest and strap detail, a readable two-line nameplate, and a 45 mm circular
  display base.
- Added a protected 25 mm NFC landing beneath the Trailer Swift base with an
  annular bed-contacting rim, keeping the tag off the table without fragile
  perimeter feet.

### Keyrings and NFC experience

- Standardized the cassette, floppy, and VHS on reinforced integrated eyelets
  with 6 mm openings and substantial material around each bore.
- Preserved flat rear NFC landings on all three media keychains so the 25 mm tag
  does not obscure their authentic front details.
- Standardized all four products on nonmetal 25 mm NFC tags encoded to the live
  `https://raddadband.com/tap/` landing page.
- Added product-specific nonmetal overlays for cassette, floppy, VHS, and
  Trailer Swift, plus mixed and backup 20-up label sheets in PNG, SVG, and PDF
  formats.
- Added front-and-back handoff-card artwork with a marked-circle instruction,
  phone-tapping guidance, and a QR fallback for the live landing page.
- Added the cross-format `C-69`, `3.69 MB`, and `T-369` easter egg while leaving
  Trailer Swift focused on the character and nameplate.

### Print and release tooling

- Generated individual binary STL files, model-only 3MF packages, and true
  Bambu Studio A1 Mini 0.4 mm project 3MF files for all four products.
- Added the one-print Retro Riot v7 all-four A1 Mini project with exactly four
  objects, at least 10 mm spacing, flat media orientation, and upright Trailer
  Swift placement.
- Standardized the starting profile at 0.16 mm layers, four walls, five top and
  bottom layers, 30% gyroid infill, supports off for the media models, and
  build-plate-only organic support for Trailer Swift.
- Added reproducible v7 model, Bambu-project, preview, label, guide, manifest,
  checksum, and release-archive generation from pinned Python dependencies.
- Added structured product metadata, print intents, mesh QA, plate-layout
  records, physical-QC checklists, a strict release validator, and CI coverage
  for automated release-integrity checks.
- Matched every embedded quality profile to the documented 30 mm/s outer and
  top-surface speeds, 25 mm/s small-perimeter speed, and rear seam placement.
- Added oblique product renders, explicit NFC-landing callouts, one-millimeter
  sticker bleed, true 25 mm cut guides, and a VHS-specific overlay treatment.

### Validation boundary

- Digital mesh checks confirm that the four generated models are finite,
  single-body, watertight, consistently wound, manifold, nondegenerate, and
  within the A1 Mini build volume.
- The strict release gate reports 217 passes, zero warnings, and zero critical
  failures, including successful Bambu Studio CLI slicing of all ten 3MF files.
- V7 remains a physical-test release candidate rather than an approved batch
  product. Ring installation, pull and twist, drop, pocket carry, surface
  finish, Trailer Swift stability, sticker adhesion, and repeated iPhone and
  Android NFC tests must pass with the actual production filament, tags,
  overlays, and split rings before batch production.

## 0.3.0 - 2026-08-09

- Rebuilt the mini VHS as v3 with an unmistakable hinged tape-door band,
  framed reel bay, nine-tooth hubs, center tape gauge, five screw positions,
  and restrained label treatment.
- Reworked the floppy as v18 with a developed rear shell seam, hub boundary,
  shutter track, write-protect detail, and preserved 25 mm NFC contact zone.
- Replaced the flat Trailer Swift charm with the v4 upright punk collectible.
- Added a solid stepped circular display base, integrated nameplate, toy-like
  body depth, faux bobble spring, and underside NFC placement guide.
- Added individual test plates and the Retro Riot v6 four-piece A1 Mini plate.
- Added reproducible source, documentation, release checksums, and automated
  repository integrity checks.
- Added a 25 mm `TAP TO PLAY` NFC label, a 20-up letter-size label sheet, and a
  handoff card so tap behavior is obvious without compromising the authentic
  media fronts.
- Added a molded `TAP THE BASE` cue to the Trailer Swift display stand.
