# Rad Dad Retro Riot v9 production guide

## Start with the configured projects

Use files under `release/v9/3mf/`. Model-only 3MF and STL files contain valid
geometry but do not carry the complete Bambu printer intent.

| Need | Recommended file |
|---|---|
| Cassette only | `Rad_Dad_Cassette_v38_A1_MINI_0.4_PROJECT.3mf` |
| Floppy only | `Rad_Dad_Floppy_v21_A1_MINI_0.4_PROJECT.3mf` |
| VHS only | `Rad_Dad_Mini_VHS_v5_A1_MINI_0.4_PROJECT.3mf` |
| Trailer Swift only | `Trailer_Swift_v9_Signature_Punk_QR_A1_MINI_0.4_PROJECT.3mf` |
| Current cassette, floppy, and VHS together | `Rad_Dad_Retro_Riot_v9_CURRENT_THREE_CASSETTE_FLOPPY_VHS_A1_MINI_0.4_PROJECT.3mf` |
| All four with Trailer Swift support | `Rad_Dad_Retro_Riot_v9_ALL_FOUR_A1_MINI_0.4_TREE_SUPPORT_PROJECT.3mf` |

All files are unsliced projects. Opening successfully does not replace Preview
inspection or a physical proof print.

## Approved baseline

- Printer: Bambu Lab A1 mini.
- Nozzle: 0.4 mm.
- Material: dry PLA for the qualification print.
- Plate: clean Textured PEI Plate.
- Scale: exactly 100% on all axes.
- Layer height: 0.16 mm.
- Initial layer height: 0.20 mm.
- Wall loops: 4.
- Top layers: 5.
- Bottom layers: 5.
- Infill: 30% gyroid.
- Small perimeters: 25 mm/s.
- Top surfaces: 30 mm/s.
- Elephant-foot compensation: 0.15 mm.

Cassette, floppy, and VHS print flat with supports off. Trailer Swift prints
upright with tree/organic support from the build plate. The current three-device
plate has supports off. Use the all-four support project only when printing the
figure with the media pieces.

## Before every print

1. Confirm the project filename and model revisions.
2. Confirm the A1 Mini, 0.4 mm nozzle, Textured PEI Plate, and 100% scale.
3. Confirm every object is fully inside the 180 x 180 mm build area.
4. Slice at 0.16 mm using Arachne wall generation.
5. Review every layer in Preview, not only the final top view.
6. Confirm the eyelet bores are open and contain no support or brim.
7. Confirm no front lettering becomes an isolated or floating toolpath.
8. Print one proof before starting a batch.

## Device-specific Preview checks

### Cassette v38

- Confirm the complete lower transport edge is present.
- Confirm all five lower-edge transport bays are open at the physical edge.
- Confirm unequal tape packs, six-lobe hubs, center window, and pressure pad.
- Confirm `RAD DAD`, `90`, and `C-69` remain readable.
- Confirm the rear landing stays continuous and supports are off.

### Floppy v21

- Confirm the shutter is above the writable label.
- Confirm `RAD DAD` remains inside the label field.
- Confirm every character of the 12.60 x 2.85 mm bold `3.69 MB` mark has a
  continuous toolpath.
- Confirm the rear spindle, tracks, seam, and write-protect cues remain distinct.
- Confirm the 6.0 mm eyelet is open and supports are off.

### Mini VHS v5

- Confirm two independent reel windows and asymmetric tape packs.
- Confirm the dust cover, tape path, hubs, label, `VHS`, and `T-369` details.
- Confirm `RAD DAD` is large and readable on the label.
- Reject a Preview that reads like a stretched audio cassette.
- Confirm the rear landing is flat and supports are off.

### Trailer Swift v9

- Confirm the figure and base remain one object.
- Confirm feet, guitar, hands, neck, hair, and nameplate are supported.
- Confirm supports begin on the build plate and remain removable.
- Confirm the underside sticker landing is not filled by support or raft.

## Current three-device plate

The current plate contains only the cassette, v21 floppy, and VHS. They are
spaced across the A1 Mini bed with the floppy centered above the longer pair:

- Cassette bounds: X 19.02-77.18 mm, Y 39.87-70.13 mm.
- Floppy bounds: X 67.82-112.18 mm, Y 101.54-138.46 mm.
- VHS bounds: X 95.20-161.00 mm, Y 39.05-70.95 mm.

Print by layer. Do not enable support. Stop before printing if a local profile
substitution changes the plate, scale, orientation, or support state.

## Physical inspection after cooling

- Measure the model envelope and 6.0 mm keyring opening.
- Confirm every model sits flat without rocking.
- Confirm all text is complete and joined to the shell.
- Read `RAD DAD` at arm's length and `3.69 MB` at 30 cm / 12 inches in ordinary
  indoor light.
- Inspect the cassette transport edge from the front and physical bottom.
- Inspect the floppy front and back as separate, developed faces.
- Inspect the VHS from the front, side, and back for VHS-specific hardware.
- Reject cracks, strings, open seams, loose details, sharp cleanup scars,
  delamination, or exposed infill.

## Keyring qualification

Applies to cassette, floppy, and VHS:

1. Measure the thickest intended production split-ring wire.
2. Install it through the eyelet by hand in 30 seconds or less.
3. Use no drill, knife, forced prying, or heat.
4. Reject whitening, cracking, gouging, peeling, or visible bore shaving.
5. Apply a 2 kg static hanging load for 60 seconds.
6. Complete 25 firm pull-and-twist cycles.
7. Reinspect the bore and both eyelet roots.

## QR sticker installation

1. Use a 25.4 mm matte-white permanent-adhesive sticker with a pure-black QR.
2. Confirm it opens `https://raddadband.com/qr/` before installation.
3. Clean and dry the protected rear or underside landing.
4. Center the sticker without covering an edge, opening, or raised detail.
5. Press the full sticker for 20-30 seconds.
6. Allow the adhesive to cure according to the stock manufacturer's guidance.
7. Scan the installed code three times on iPhone and three times on Android.
8. Repeat scans after drop and carry testing.

Previously ordered stickers encoding `https://raddadband.com/tap/` remain valid
through the website's permanent redirect. Do not discard them.

## Troubleshooting

| Symptom | Required response |
|---|---|
| `3.69 MB` is incomplete | Confirm v21, 100% scale, 0.4 mm nozzle, 0.16 mm Arachne profile, and slow detail speeds; hold the batch if any character remains incomplete |
| Eyelet is tight | Confirm elephant-foot compensation, remove loose brim only, and reject cracked or undersized parts |
| Cassette bottom looks solid | Confirm the v38 project and rear-down orientation; do not substitute an earlier simplified cassette |
| VHS resembles an audio cassette | Confirm v5 and inspect the independent reel windows, door, label, and VHS marks |
| QR does not scan | Check lighting, focus distance, quiet zone, print scaling, glare, sticker damage, and destination URL; replace the sticker if needed |
| Sticker edge lifts | Clean the landing, replace the sticker, press the full surface, and allow complete cure time |
| Trailer Swift support damages details | Remove support gradually; reorient or adjust tree support before another print |

## Automated release verification

Run from the repository root after rebuilding:

```bash
python3 tools/verify_v9_release.py
```

Automated success proves file integrity, package consistency, QR specification,
and digital mesh QA. It does not replace the physical proof and acceptance
steps in [VALIDATION.md](VALIDATION.md).
