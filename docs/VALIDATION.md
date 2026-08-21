# Rad Dad Retro Riot v9 validation plan

## Release rule

Digital QA, sliced Preview inspection, and physical validation are separate
gates. Do not describe a model as batch-ready until all applicable gates pass.

## Gate 1: automated release verification

Run from the repository root:

```bash
python3 tools/verify_v9_release.py
```

The verifier checks:

- Required v9 source, documents, QR artwork, STL, and 3MF files.
- Canonical `https://raddadband.com/qr/` metadata.
- The v22 floppy and balanced current three-device project.
- Manifest records, SHA256SUMS entries, archive checksum, and ZIP integrity.
- Bambu project generation status.
- One-body, watertight, consistently wound meshes with zero boundary,
  non-manifold, and degenerate edges.
- Exact floppy envelope and A1 Mini build-volume compliance.
- QR artwork dimensions, matrix size, quiet zone, and module pitch.

Any failure blocks release.

## Gate 2: Bambu Studio Preview

Open the configured project, slice it, and inspect every layer.

- Confirm the A1 Mini, 0.4 mm nozzle, 100% scale, and correct plate.
- Confirm media supports are off and Trailer Swift uses build-plate tree support.
- Confirm no floating, detached, or one-layer-only detail.
- Confirm all eyelet openings and QR landings remain unobstructed.
- Confirm the cassette lower transport bays are present and open.
- Confirm every character of `RAD DAD`, `3.69 MB`, `T-369`, and the Trailer
  Swift nameplate receives a continuous toolpath.
- Confirm the current three-device plate contains exactly cassette, floppy, and
  VHS with safe clearance.

Save screenshots or notes with the build record. Any unexpected slicer warning
must be understood and resolved before printing.

## Gate 3: first physical proof

Record printer, nozzle, plate, filament brand/color, drying state, slicer
version, profile, date, operator, and project filename.

### Dimensions and construction

- Measure each exterior envelope at 100% scale.
- Measure each media eyelet in two directions; nominal minimum is 6.0 mm.
- Confirm every model sits flat and every QR landing accepts a centered 25.4 mm
  sticker without edge overhang.
- Reject cracks, loose shells, open seams, exposed infill, sharp scars, strings,
  delamination, or missing details.

### Recognition

- Present each unlabelled media proof at arm's length to five unbriefed people.
- Require at least four of five to identify cassette, floppy, and VHS correctly
  within two seconds without relying on text.
- Require Trailer Swift to read as a funny punk-rock toy, not a frightening or
  unexplained shape.

### Readability

- Confirm `RAD DAD` is readable at arm's length on all media products.
- Confirm `3.69 MB` is readable at 30 cm / 12 inches in ordinary indoor light.
- Confirm `90`, `C-69`, `T-369`, `VHS`, and `TRAILER SWIFT` are complete at a
  normal handheld viewing distance.
- Inspect in bright and dim indoor light and from slight off-axis angles.

### Authentic details

- Cassette: unequal tape packs, six-lobe hubs, center window, pressure pad, and
  five real lower-edge transport bays.
- Floppy: shutter above label, orientation chamfer, front label hierarchy, rear
  spindle, shutter tracks, seam, and write-protect cue.
- VHS: wide proportions, independent reel windows, asymmetric packs, dust door,
  label, VHS marks, and rear reel-drive construction.
- Trailer Swift: friendly face, punk hair, guitar, shoes, nameplate, solid base,
  and protected underside sticker landing.

## Gate 4: keyring durability

For cassette, floppy, and VHS:

1. Install the thickest intended production split ring by hand within 30 seconds.
2. Reject any need for drilling, cutting, heating, or forced prying.
3. Apply a 2 kg static load for 60 seconds.
4. Complete 25 firm pull-and-twist cycles.
5. Drop the assembled keychain from 1 meter onto a hard floor three times in
   varied orientations.
6. Carry it with normal keys for 72 hours.
7. Reinspect bore diameter, eyelet roots, lettering, mechanical details, and
   sticker landing.

Reject whitening, cracks, permanent deformation, layer separation, or sharp
damage.

## Gate 5: QR production and installation

- Print at Actual Size / 100% on matte-white stock.
- Verify the 25.4 mm finished diameter and complete white quiet zone.
- Scan top, center, and bottom samples from every sticker batch before use.
- Require each sample to open `https://raddadband.com/qr/` on iPhone and Android.
- Center one sticker on the clean protected landing.
- Scan the completed item three times on each platform in indoor and outdoor
  light.
- Repeat after the drop sequence and 72-hour carry test.

Existing `/tap/` stickers pass if the permanent redirect lands at `/qr/` and the
page loads normally.

## Gate 6: release decision

Approve batch production only when:

- `tools/verify_v9_release.py` passes.
- Bambu Preview has no unexplained warnings or missing toolpaths.
- At least one current physical proof of each produced model passes.
- All measured values and test observations are recorded.
- The exact production filament, print profile, split ring, and sticker stock
  match the qualified samples.

Otherwise mark the release `HOLD`, document the defect, correct it in source,
rebuild all generated files and checksums, and repeat the affected gates.
