# Rad Dad Retro Riot v7 production guide

> Old media. Loud band. One tap.

## Scope

This guide applies only to cassette v37, floppy v19, Mini VHS v4, and Trailer
Swift v5 in `release/v7`.

Use an individual configured Bambu project for the first print of every model.
The model-only 3MF files contain geometry but do not guarantee printer,
filament, plate, process, or support settings.

## Supplied project files

| Product | Configured Bambu project | Model-only fallback |
| --- | --- | --- |
| Cassette v37 | `Rad_Dad_Cassette_v37_A1_MINI_0.4_PROJECT.3mf` | `Rad_Dad_Cassette_v37_MODEL_ONLY.3mf` |
| Floppy v19 | `Rad_Dad_Floppy_v19_A1_MINI_0.4_PROJECT.3mf` | `Rad_Dad_Floppy_v19_MODEL_ONLY.3mf` |
| Mini VHS v4 | `Rad_Dad_Mini_VHS_v4_A1_MINI_0.4_PROJECT.3mf` | `Rad_Dad_Mini_VHS_v4_MODEL_ONLY.3mf` |
| Trailer Swift v5 | `Trailer_Swift_v5_Bobblehead_NFC_A1_MINI_0.4_PROJECT.3mf` | `Trailer_Swift_v5_Bobblehead_NFC_MODEL_ONLY.3mf` |
| All four | `Rad_Dad_Retro_Riot_v7_ALL_FOUR_A1_MINI_0.4_PROJECT.3mf` | `Rad_Dad_Retro_Riot_v7_ALL_FOUR_MODEL_ONLY.3mf` |

A configured project is still unsliced and contains no G-code. Opening
successfully is not the same as passing Preview or physical validation.

## Exact 100% model extents

| Product | Actual/source extent |
| --- | ---: |
| Cassette v37 | 58.162 x 30.260 x 6.685 mm |
| Floppy v19 | 44.360 x 36.916 x 4.130 mm |
| Mini VHS v4 | 65.800 x 31.900 x 7.000 mm |
| Trailer Swift v5 | 45.000 x 45.000 x 64.400 mm measured; 46.000 x 46.000 x 65.000 mm maximum envelope |

These are the 100% production extents. Do not scale a model to solve text,
eyelet, NFC, support, or fit problems.

## Exact supplied Bambu profile

The v7 project generator uses these source profiles:

| Profile type | Supplied profile |
| --- | --- |
| Machine | `Bambu Lab A1 mini 0.4 nozzle` |
| Process base | `0.16mm Optimal @BBL A1M` |
| Filament base | `Bambu PLA Basic @BBL A1M` |

The generator flattens those profiles and applies the following final intended
embedded v7 overrides:

| Setting | Supplied value |
| --- | ---: |
| Printer | Bambu Lab A1 mini |
| Nozzle diameter | 0.40 mm |
| Layer height | 0.16 mm |
| Initial layer height | 0.20 mm |
| Build plate | Textured PEI Plate |
| Wall generator | Arachne |
| Wall loops | 4 |
| Top shell layers | 5 |
| Bottom shell layers | 5 |
| Sparse infill | 30% gyroid |
| Elephant-foot compensation | 0.15 mm |
| Outer wall speed | 30 mm/s |
| Top surface speed | 30 mm/s |
| Small perimeter speed | 25 mm/s |
| Initial layer speed | 30 mm/s |
| Bridge speed | 25 mm/s |
| Bridge flow | 0.93 |
| Seam position | Rear |
| Print sequence | By layer |

The generated project validates the printer, nozzle, profile overrides, object
names, plate count, and support mode. Confirm them again after opening because
Bambu Studio may offer to substitute local profiles.

The source profile requires `Textured PEI Plate`. If a supplied project opens
with another plate selected, treat it as stale and do not print until the
project is regenerated or deliberately converted to a calibrated plate
profile.

## Materials

### Supplied baseline

Bambu PLA Basic is the filament profile embedded in the supplied projects and
is the baseline for the first dimensional and visual proof.

### Carried media

PLA Tough or PLA+ is optional after calibration and can improve impact tolerance
for the cassette, floppy, and VHS eyelets. Select a matching filament profile,
calibrate it, and repeat the complete proof protocol rather than printing a
different material under the embedded PLA Basic settings.

PETG may be used only with a calibrated PETG profile and a fresh proof print.
Its additional stringing can obscure the cassette transport recesses, floppy
text, VHS window edges, and Trailer Swift face.

Avoid brittle decorative or silk filament for production eyelets, hair,
angular instrument details, and thin raised lettering unless physical
qualification proves it survives the required tests.

### NFC materials

Use a genuine 25.0 mm peel-and-stick NFC tag. Use ordinary nonmetal paper or
vinyl overlays and nonmetal ink. Do not use foil, metallic ink, conductive ink,
metal-backed label stock, or a metal-containing laminate.

## Orientation and support policy

| Product/project | Orientation | Support policy |
| --- | --- | --- |
| Individual cassette | Rear NFC landing on plate, detailed front up | Off |
| Individual floppy | Rear faux-hub landing on plate, detailed front up | Off |
| Individual VHS | Rear NFC landing on plate, detailed front up | Off |
| Individual Trailer Swift | Circular base down, figure upright | `tree(auto)`, build plate only |
| All-four project | Three media rear-down plus Trailer Swift base-down | Global `tree(auto)`, build plate only |

The all-four project uses global `tree(auto)`, build-plate-only support and
contains no serialized object-level support overrides. Preview is mandatory for
every combined slice. Confirm that Trailer Swift receives only necessary
support and that no unnecessary support is generated under or around the
cassette, floppy, or VHS. If unnecessary media support appears, use support
blockers or manually add an object override only when the installed Bambu Studio
version can serialize it, then preview again. If the result remains uncertain,
print the individual supports-off media projects instead.

## First-print protocol

1. Open the configured individual Bambu project, not the model-only 3MF.
2. Confirm A1 Mini, 0.40 mm nozzle, Textured PEI Plate, 0.16 mm layer height,
   0.20 mm initial layer, four walls, five top layers, five bottom layers, and
   30% gyroid.
   Confirm 30 mm/s outer walls, 30 mm/s top surfaces, 25 mm/s small perimeters,
   30 mm/s initial layer, 25 mm/s bridges, 0.93 bridge flow, and a rear seam.
3. Confirm the orientation and support mode against the table above.
4. Slice the project and open Preview before sending it to the printer.
5. Inspect every layer containing an eyelet, blind recess, small marking, VHS
   dust cover, Trailer Swift neck, angular instrument, flame hair, or base
   pocket.
6. Print one proof at 100% scale with no NFC tag or overlay installed.
7. Let the part cool before removal so the rear landing and eyelet are not
   distorted.
8. Remove only brim or support material. Do not drill, melt, or scale a failed
   production feature to force acceptance.
9. Complete visual, dimensional, mechanical, and handling inspection.
10. Program the tag for exactly `https://raddadband.com/tap/` and test it loose
    before installation.
11. Apply the programmed 25.0 mm tag onto the marked landing, apply the matching
    overlay, then apply the clear nonmetal overlaminate.
12. Allow the completed adhesive stack to cure for 24 hours and repeat NFC
    testing after every application stage, after curing, after drop testing,
    and after the 72-hour carry test.
13. Print the all-four project only after all four individual proofs pass.

## Required sliced-Preview inspection

### Cassette

- Confirm `RAD DAD`, `90`, and `C-69` form continuous toolpaths.
- Confirm unequal tape packs and six-lobe hubs remain distinct.
- Confirm the center tape window, pressure pad, and five transport recesses are
  open from the detailed face and closed toward the NFC rear.
- Confirm no support is generated.
- Confirm the 6.0 mm keyring bore, 12.0 mm outside diameter, and 2.8 mm straight
  lateral shell-to-bore threading approach remain open and unobstructed.
- Confirm the separate lead-ins on both faces widen the bore entrance to 7.0 mm
  and remain 0.68 mm deep.

### Floppy

- Confirm the shutter is at the top and the `RAD DAD` label is beneath it.
- Confirm every character of the 10.2 x 2.3 mm `3.69 MB` marking survives
  slicing.
- Confirm the write-protect and density-control recesses remain distinct.
- Confirm the rear NFC landing is broad and flat.
- Confirm no support is generated.
- Confirm the 6.0 mm eyelet bore remains open.

### Mini VHS

- Confirm the full-width dust cover, two independent reel windows, six-rib
  hubs, central label, insertion cue, `T-369`, and `VHS` mark remain distinct.
- Reject a slice that visually collapses into an audio-cassette-style shared
  reel bay.
- Confirm no support is generated.
- Confirm the 6.0 mm eyelet bore and broad root remain clear.

### Trailer Swift

- Confirm organic support is restricted to the build plate.
- Inspect support beneath the arms, angular instrument, flames, hair, and
  projecting face details.
- Inspect the 26.2 mm internal NFC pocket roof and 27.0 mm pocket mouth for
  bridging or trapped support.
- Confirm the 5.8 mm solid neck core and three faux spring rings remain
  continuous.
- Confirm both shoes remain fused into the 45.0 mm base.
- Confirm all `TRAILER SWIFT` nameplate strokes remain continuous.

## Physical inspection criteria

### Identity and finish

- Present each media piece at arm's length to five unbriefed participants. At
  least four of five must identify it correctly within two seconds without
  relying on its name.
- `RAD DAD`, `C-69`, `3.69 MB`, `T-369`, and `TRAILER SWIFT` must be
  readable at normal viewing distance appropriate to each marking.
- Recesses must be clean, not bridged with loose filament or exposed infill.
- Rear NFC landings must be flat enough for complete adhesive contact.
- No sharp scars, loose details, open seams, strings, or missing surfaces are
  acceptable.

### Keyring function

- Each cassette, floppy, and VHS opening must measure and function as a 6.0 mm
  bore.
- The thickest production split ring must install without cracking or visibly
  shaving the eyelet, without a drill, knife, or forced prying, and in 30 seconds
  or less.
- Each eyelet must hold a 2 kg static load for 60 seconds without whitening,
  cracking, permanent deformation, or layer separation.
- Each eyelet must survive 25 firm pull-and-twist cycles without whitening,
  cracking, permanent deformation, or layer separation.
- Remove and reinstall the production ring once after cycling, then reject any
  notch growth, whitening, cracking, permanent deformation, root separation,
  or layer separation.
- Each carried media piece must survive six one-meter drops in distinct
  orientations without functional damage.
- Each carried media piece must complete 72 hours of normal key carry without
  an eyelet crack, detached detail, or unreadable primary mark.

### Trailer Swift function

- The figure must stand without rocking before and after NFC installation.
- The figure must remain standing on a 10-degree incline.
- The 45.0 mm solid base must remain flat around its continuous annular contact
  surface and must have no perimeter feet.
- The tag and overlay must remain protected inside the 0.80 mm underside pocket.
- Select and document a separate Trailer Swift drop height and orientation plan,
  then inspect the neck, angular instrument, hair, arms, shoes, and base after
  every impact.
- Never infer Trailer Swift's drop or stability result from the six-orientation
  media keychain test.

### NFC function

- Verify that every tag contains exactly `https://raddadband.com/tap/`.
- Test the loose programmed tag before installation.
- Require ten consecutive successful scans on at least one current iPhone.
- Require ten consecutive successful scans on at least one current Android
  phone.
- Repeat ten scans per phone after tag installation.
- Repeat ten scans per phone after overlay installation.
- Repeat ten scans per phone after clear nonmetal overlaminate installation.
- Repeat ten scans per phone after the 24-hour adhesive cure, after the drop
  sequence, and after the 72-hour carry test.
- Repeat with a normal phone case and the production split ring or key bundle
  attached.
- After the 72-hour carry test, reject any tag or overlay with edge lift,
  bubbles, rotation, delamination, or loss of scan reliability.

### Adhesion and abrasion

- After the 24-hour cure, rub the completed TAP surface firmly 100 times with a
  clean dry cloth and inspect ink and edge retention.
- Attempt a light fingernail lift at four quadrants without cutting the film.
- Reject spontaneous edge lift, sliding, exposed adhesive, bubbles, wrinkles,
  delamination, overhang, or tag movement.
- Repeat adhesion inspection after drop and 72-hour carry testing.

### User tap discovery

- Give the completed product without verbal instructions to five unbriefed
  participants.
- Require at least four of five to attempt the marked NFC area within ten
  seconds.
- Then provide the production handoff card without coaching and require all five
  to locate the marked circle, obtain the notification, and open the page.
- Test the handoff card's QR fallback and printed URL at final physical size.
- Revise the overlay or handoff card and repeat the five-person test if any
  acceptance threshold is missed.

## NFC and overlay installation

1. Encode exactly `https://raddadband.com/tap/` and verify it before locking the
   tag.
2. Test the loose programmed tag on both phone platforms.
3. Clean and dry the marked plastic landing without leaving residue.
4. Apply the programmed 25.0 mm tag onto the marked landing.
5. Center the matching 25.0 mm nonmetal overlay over the tag.
6. Apply a clear nonmetal overlaminate over the printed overlay.
7. Press the complete adhesive stack for 20-30 seconds without crushing raised
   plastic details.
8. Keep the item out of pocket and key use during the 24-hour adhesive cure.
9. Repeat the complete NFC scan sequence after each layer is installed, after
   curing, after drop testing, and after the 72-hour carry test.

The floppy overlay contains an approximately 11-12 mm faux gray hub printed
with ordinary nonmetal ink. It uses a central clamping opening and one offset
rectangular drive-engagement slot. The printed hub is an optical illusion, not
metal hardware.

Trailer Swift's tag and overlay belong inside the underside pocket. Neither
should project below the surrounding annular base.

## All-four project protocol

The all-four project contains exactly four objects arranged with at least
10.0 mm spacing on the A1 Mini plate.

Before printing:

1. Confirm all four named objects are present.
2. Confirm the three media pieces are detailed-face up.
3. Confirm Trailer Swift is upright on its base.
4. Confirm global `tree(auto)`, build-plate-only support is enabled and that no
   object-level support overrides are serialized.
5. Open Preview and confirm no unnecessary cassette, floppy, or VHS support was
   generated.
6. Confirm Trailer Swift support is reachable and removable.
7. Print by layer, not sequentially by object.
8. Stop and return to individual projects if the mixed plate introduces a
   support, clearance, or surface-quality regression.

## Troubleshooting

| Symptom | Likely cause | Required response |
| --- | --- | --- |
| Bambu project opens with the wrong plate | Stale project or local profile substitution | Select the source-required Textured PEI Plate profile or regenerate the project; then reslice |
| Media receives support in its individual project | Support mode is not the approved media mode | Disable support and confirm the configured project reports support off |
| Media receives support on the all-four plate | Global Trailer Swift support reached flat-media detail | Add support blockers or object overrides, reslice, and verify Preview; otherwise print individually |
| `3.69 MB`, `C-69`, or `T-369` disappears | Scaling, wrong nozzle/profile, or insufficient toolpath resolution | Return to 100% scale and confirm the supplied 0.40 mm nozzle, 0.16 mm Arachne profile, 25 mm/s small-perimeter speed, and 30 mm/s top-surface speed; hold the print if the text remains incomplete |
| Eyelet is tight | Brim, seam, or first-layer expansion obstructs the bore | Confirm 0.15 mm elephant-foot compensation, remove loose brim by hand, and reject cracked or undersized parts |
| Rear tag will not adhere | Dirty, warped, or heavily scarred landing | Clean the surface and reprint if complete adhesive contact is not possible |
| NFC scans before installation but not afterward | Metal stock, phone-case interference, key proximity, or misaligned tag | Remove metal-containing material, move keys away, test without the case, and reinstall only after the loose tag passes |
| Overlay edge lifts | Contamination, misalignment, or use before adhesive cure | Replace the overlay, press the full surface, and allow the documented 24-hour cure |
| Trailer Swift pocket roof sags | Unsupported pocket bridge or unsuitable support result | Inspect Preview, correct support, and reprint before installing the tag |
| Trailer Swift rocks | Base warp, trapped support, or tag protrusion | Remove trapped support, verify the 0.80 mm pocket, and reject any part that still rocks |
| Fine Trailer Swift details snap | Brittle material or damaged support removal | Use the supplied PLA proof first, remove support gradually, and requalify any alternate material |
| Cassette lower details look stringy | Wrong orientation, support, or incomplete top surfaces | Print rear-down with supports off and inspect all blind recess layers before reprinting |

## Digital QA and release status

`release/v7/qa/MODEL_QA.json` records mesh integrity only. A
`mesh_qa_pass` means the STLs are connected, watertight, consistently wound,
free of boundary and non-manifold edges, free of degenerate faces, and inside
the 180.0 x 180.0 x 180.0 mm build volume.

It does not prove that:

- Bambu Studio generated acceptable toolpaths.
- Small text is printable.
- Supports are removable.
- Eyelets fit the production ring.
- The NFC tag scans through the final material stack.
- Adhesive survives carry.
- Trailer Swift stands correctly.
- The parts survive drops and handling.

The separate release validator, sliced Preview, individual proof prints, and
physical checklist remain mandatory.

**Batch production remains on hold until every applicable digital release,
slicing, ring, load, pull/twist, drop, 72-hour carry, stability, adhesion,
overlay, NFC, and user-discovery gate passes.**
