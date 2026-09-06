# Changelog

## Digital merch desk

- Added **Your holds** navigation with the current session's receipts, newest
  first, and explicit confirmed withdrawal from each active receipt. Withdrawn
  status is shared with the admin desk; retries keep the first withdrawal time.
- Kept receipt details after withdrawal and stated the in-memory/session access
  limits. Added owner-isolation, CSRF, confirmation, retry, and lifecycle tests.

- Catalog cards and product pages now serve leftover-#8 crops of the Current
  Three study so cassette, floppy, and mini VHS are visually distinct on a
  phone. Combined study stays the original render bytes.
- Checkout requires an explicit digital-hold confirmation and redirects to a
  session-owned receipt. Empty carts still have no checkout. Nothing is priced,
  charged, printed, shipped, or posted.
- Hold-cart quantity uses 44 px steppers instead of a cramped number field.

- Added a shopper catalog, cart, and request-hold flow bound to the leftover
  Current Three PETG material study.
- Added an admin publish/hold desk with token auth, CSRF, and rate-limited
  sign-in. Unpublished cards leave the public catalog and cannot enter a cart.
- Locked the public merch path to an allowlist so STL, 3MF, renderer, and
  release files are not served as shop assets. Checkout rejects shipping,
  payment, printer, and pitch fields.
- Added `tools/serve_digital_merch.py`, `tools/verify_digital_merch.py`, and a
  release-integrity CI step. No prices, print jobs, QR destination change, or
  merch auto-post.

## Current Three material-study preview

- Added a dedicated cassette v38, floppy v22, and mini VHS v5 overview rendered
  directly from the current sealed STL files at true relative scale.
- Reused the existing software-rendering conventions while adding restrained
  satin-PETG shading, specular response, grounded shadows, and a 25 mm reference
  without altering printable geometry or the sealed v9 package.
- Added machine-readable source/output/renderer provenance and a CI smoke render
  that fails closed if the preview loses its digital-only disclaimer.

## Trailer Swift v16 Strat-style guitar rebuild

- Replaced the generic double-cutaway with a rounded Strat-style perimeter:
  long upper horn, short lower horn, narrow waist, offset shoulder, and broad
  lower bout.
- Rebuilt the front as a recognizable SSS layout with an angled bridge pickup,
  full pickguard, synchronized tremolo block and arm, three knobs, five-way
  blade switch, jack cup, bridge saddles, position dots, and strap buttons.
- Replaced the generic three-per-side headstock with an asymmetric six-inline
  profile, six same-side tuners, string tree, tapered neck, nut, and two durable
  representative strings.
- Kept the design unbranded while preserving the v15 face, clean jeans, exact
  45 x 45 x 64.4 mm envelope, one-piece construction, and 27 mm QR landing.

## Trailer Swift v15 expression and instrument refinement

- Opened the eyes, thinned and raised the lids, and reduced the brows so the
  expression reads alert and musical rather than sleepy.
- Replaced the mustache-like split tooth bars with one recessed curved tooth
  mass and simplified the tongue and lower lip inside the singing mouth.
- Rounded the guitar body perimeter, added a printable fretboard nut, preserved
  its aligned hardware and strap, and removed the unrealistic external flame
  tabs while retaining the flame relief on the body.
- Preserved the clean jeans, exact 45 x 45 x 64.4 mm envelope, one-piece
  construction, and full 27 mm underside QR landing.

## Trailer Swift v14 face and guitar realism pass

- Rebuilt the eyes as inset eyeballs with raised irises and printable upper lids
  instead of empty sockets with floating dots.
- Reshaped the nose and singing mouth with a smaller cavity, sloped upper teeth,
  recessed tongue, lower lip, and cheek creases.
- Broadened the double-cutaway guitar body, added a connected shoulder strap,
  retained aligned strings and hardware, and reduced the rear flames from three
  spikes to two smoother attached flame forms.
- Preserved the clean v13 jeans, exact 45 x 45 x 64.4 mm envelope, one-piece
  construction, and full 27 mm underside QR landing.

## Trailer Swift v13 source-level jeans rebuild

- Removed the complete three-stroke plaid generator responsible for the star
  shapes instead of attempting to filter its geometry after assembly.
- Rebuilt each pant leg with one stance-following outside seam and one durable
  molded cuff line above the boot.
- Retained the v11 retail-style face, hair, flaming guitar, two-line nameplate,
  exact 45 x 45 x 64.4 mm envelope, and full 27 mm underside QR landing.

## Trailer Swift v12 retail cleanup

- Removed the crossed star stitching from both jean legs so the clothing reads
  as a clean molded toy rather than a themed costume.
- Preserved the smoother expressive head, asymmetric punk hair, flaming guitar,
  two-line display name, exact 45 x 45 x 64.4 mm envelope, and 27 mm QR landing.
- Kept the figurine as one connected, watertight, support-ready collectible.

## 2026-08-11 - Trailer Swift retail-toy redesign

- Advanced Trailer Swift to v11 with a smoother designer-toy head, asymmetric
  upward flame hair, narrower expressive eye sockets, a simplified singing
  face, and a two-line retail nameplate that can be read in one color.
- Added three structural flame tongues to the electric-guitar silhouette and
  retained the large shirt bolt, plaid pants, punk stance, and album-character
  cues so the result feels like Jeff without becoming a literal portrait.
- Kept the exact 45 x 45 x 64.4 mm envelope and protected 27 mm underside QR
  landing. Cassette, floppy, VHS, keyring, and plate geometry are unchanged.

## 2026-08-11 - Physical-readability pass

- Advanced the floppy to v22 after PETG testing showed the v21 `3.69 MB`
  mark was still too small. The mark is now centered, 20.00 x 4.00 mm, and uses
  substantially heavier stroke geometry without changing the disk envelope.
- Advanced Trailer Swift to v10 with deep eye and mouth shadows, anchored inset
  pupils, simplified plaid, a larger shirt bolt, stronger guitar relief, and a
  heavier base name so the character reads clearly as a punk guitarist.
- Preserved the 45 x 45 x 64.4 mm figurine envelope, 27 mm underside QR landing,
  floppy keyring bore, cassette/VHS geometry, and all established plate layouts.

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
# Repository rename and authenticity micro-refinement pass

- Refined Trailer Swift v16 with a slimmer cocked head, layered eyelids, smile and ear folds, a broad singing grin, molded boot laces, pickup pole pieces, and pickguard fasteners while retaining the exact envelope, pose, base, and underside QR landing.
- Moved the full `3.69 MB` marking into the clear shell field directly below the floppy label while preserving its high-contrast size and stroke weight.
- Added shallow, asymmetric write-protect and density-detection recesses to the floppy front without opening the shell or disturbing its rear QR landing.
- Renamed the project from `Rad-Dad-NFC-Tags` to `Rad-Dad-QR-Merch` so the repository identity matches the current QR-first merchandise collection.
- Kept the approved cassette geometry unchanged, including its audited tape-transport edge, proportions, QR land, and compact eyelet.
- Added subtle stamped shutter lips and a slide-direction mark to the floppy without changing its dimensions, label, `3.69 MB` marking, QR land, or key-ring geometry.
- Added molded concentric reel rings and restrained flip-up door ribs to the VHS without changing its dimensions, larger `RAD DAD` label, QR land, or key-ring geometry.
- Preserved Trailer Swift's established collectible silhouette, clean jeans, Strat-style guitar, base, and underside QR land rather than risking another broad redesign.
