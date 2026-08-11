# Validation and release qualification

Validation has two independent layers:

- Digital validation proves that release files are internally consistent,
  parseable, dimensionally bounded, and sliceable by the configured software.
- Physical validation proves that real prints are recognizable, durable,
  attachable to keys, readable by phones, adhesive-stable, and understandable
  to a person who has not seen the project before.

A digital pass never implies a physical pass. Do not write "physically tested,"
"drop tested," "NFC verified," or "batch ready" unless the corresponding test
was actually performed on an identified physical sample and the result was
recorded.

## Release states

| State | Meaning |
| --- | --- |
| HOLD | A required gate is missing, failed, or has not been reviewed |
| Digital candidate | Automated critical checks pass; warnings are reviewed; physical work remains |
| Physical candidate | Proof prints exist and are assigned sample IDs for qualification |
| Batch-ready | Every applicable digital and physical gate has a dated, attributable pass |

Unchecked, blank, unknown, and "not tested" all mean not passed. A release stays
on HOLD until required evidence exists.

## Automated gate overview

The strict validator is `tools/verify_v7_release.py`. It writes a deterministic
JSON report, prints a short human-readable summary, and exits nonzero when a
critical gate fails.

### Release and manifest gates

The validator checks:

- The release directory exists.
- `MANIFEST.json` is readable JSON and uses the expected schema and v7 release identity.
- Every manifest path is a safe relative path contained inside the release directory.
- Manifest paths are unique and required artifacts are present.
- Recorded byte sizes and SHA-256 hashes match the files on disk.
- Manifest and checksum coverage do not silently omit required release assets.
- Required STL, 3MF, guide, preview, QA, metadata, and NFC handoff artifacts exist.

A hash failure means the release changed after packaging, was corrupted, or was
assembled from mismatched outputs. Regenerate the release rather than editing a
hash by hand.

### Mesh gates

For STL and 3MF geometry, the validator checks:

- The file can be parsed and contains triangles.
- Vertices and dimensions are finite.
- Expected body count is present: one body for each individual model and four instances for the all-four collection.
- Every individual product is positive-volume, watertight, and consistently wound.
- Boundary edges, non-manifold edges, inconsistent edges, and degenerate faces are zero.
- Product envelopes remain within their approved limits with the configured tolerance.
- STL and corresponding 3MF geometry agree within 0.03 mm per extent and 0.5 percent relative volume.
- Collection spacing and build-volume intent remain valid.

A slicer successfully opening a broken mesh does not override a failed topology
gate. Repair or regenerate the source geometry.

### 3MF package and project gates

The validator distinguishes model-only 3MF geometry packages from true Bambu
Studio project files. It checks package relationships, model parts, build items,
component transforms, units, object counts, and parseable metadata. A Bambu
project is additionally expected to carry the intended A1 Mini / 0.4 mm nozzle
profile, placement, process intent, filament metadata, and support mode.

The intended v7 base process is 0.16 mm layers, 0.20 mm initial layer, Arachne
wall generation, four walls, five top and bottom layers, 30 percent gyroid
infill, and 0.15 mm elephant-foot compensation. Flat cassette, floppy, and VHS
individual projects use support off. Trailer Swift and the mixed plate use
organic or tree support from the build plate only. Preview the mixed plate to
confirm that support is not generated unnecessarily under the flat media.

`qa/BAMBU_PROJECT_STATUS.json` is packaging evidence, not physical evidence. It
must identify five verified Bambu projects, their Bambu Studio version, plate
and instance counts, profile match, and support mode. The model-only files
remain the authoritative geometry fallback.

### Product metadata gates

The product metadata checks include:

- Stable product identifiers for cassette, floppy disk, VHS, and Trailer Swift.
- A nominal 25 mm flat NFC landing for every product, within the validator's 0.50 mm tolerance.
- A nominal 6.0 mm keyring opening for cassette, floppy, and VHS, within the 0.25 mm tolerance.
- Keyring center and axis metadata sufficient to measure the opening from the mesh.
- Trailer Swift classified as a desk collectible rather than a keychain.
- Declared dimensions, support intent, and product files associated with the correct product.

A metadata declaration does not prove a physical diameter. Measure printed
samples separately.

## Ten Bambu CLI slice targets

The full gate slices every `*.3mf` under `release/v7`. There are ten targets:
five true A1 Mini projects and five corresponding model-only packages.

| Product set | True Bambu project | Model-only 3MF |
| --- | --- | --- |
| Cassette | `Rad_Dad_Cassette_v37_A1_MINI_0.4_PROJECT.3mf` | `Rad_Dad_Cassette_v37_MODEL_ONLY.3mf` |
| Floppy disk | `Rad_Dad_Floppy_v19_A1_MINI_0.4_PROJECT.3mf` | `Rad_Dad_Floppy_v19_MODEL_ONLY.3mf` |
| VHS | `Rad_Dad_Mini_VHS_v4_A1_MINI_0.4_PROJECT.3mf` | `Rad_Dad_Mini_VHS_v4_MODEL_ONLY.3mf` |
| All four | `Rad_Dad_Retro_Riot_v7_ALL_FOUR_A1_MINI_0.4_PROJECT.3mf` | `Rad_Dad_Retro_Riot_v7_ALL_FOUR_MODEL_ONLY.3mf` |
| Trailer Swift | `Trailer_Swift_v5_Bobblehead_NFC_A1_MINI_0.4_PROJECT.3mf` | `Trailer_Swift_v5_Bobblehead_NFC_MODEL_ONLY.3mf` |

For each target the validator runs Bambu Studio in CLI mode with `--slice 0` and
a temporary output directory. A target passes only when:

- The process completes before the per-file timeout.
- The return code is zero.
- At least one G-code, BG-code, or G-code 3MF output is produced.
- The log does not contain a model-load failure, slicing failure, floating-cantilever warning treated as critical, segmentation fault, or non-manifold failure.

All ten targets must have a successful Bambu result in the JSON report. Five
successful A1 projects plus five untested model-only files is not a complete
slice gate.

## Commands

Run commands from the repository root.

### Prepare the local validation environment

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-v7.txt
```

On Windows, use the equivalent `.venv\\Scripts\\python.exe` and
`.venv\\Scripts\\pip.exe` paths.

### Digital validation without slicing

```bash
.venv/bin/python tools/verify_v7_release.py \\
  --release release/v7 \\
  --json /tmp/rad-dad-v7-validation.json
```

This performs release, manifest, artifact, mesh, 3MF, and metadata checks. It
also emits a `bambu.skipped` warning. It is useful for fast geometry work but is
not the complete release gate.

### Complete validation with all ten Bambu slices on macOS

```bash
.venv/bin/python tools/verify_v7_release.py \\
  --release release/v7 \\
  --json /tmp/rad-dad-v7-validation.json \\
  --bambu /Applications/BambuStudio.app \\
  --bambu-timeout 300
```

The `--bambu` value may instead be the complete path to the Bambu Studio
executable. Increase the timeout only when the machine is demonstrably slow;
do not use a larger timeout to hide a repeatable hang.

### Inspect the report

```bash
jq '.ok, .summary, (.bambu | length)' /tmp/rad-dad-v7-validation.json
jq '[.checks[] | select(.status != "pass")]' /tmp/rad-dad-v7-validation.json
jq '[.bambu[] | select(.timed_out or .returncode != 0 or (.slice_outputs | length) == 0)]' \\
  /tmp/rad-dad-v7-validation.json
```

If `jq` is unavailable, open the JSON report in a text editor and inspect
`ok`, `summary`, `checks`, and all ten `bambu` entries.

Do not write the transient validation report inside `release/v7` unless the
release builder is designed to add it to the manifest. Adding an unmanifested
file changes release coverage.

## Interpreting results

A complete digital PASS requires all of the following:

- Process exit status is zero.
- Top-level JSON field `ok` is `true`.
- `summary.critical_failures` is zero.
- Every warning has been read and dispositioned.
- The `bambu` array contains ten entries when `--bambu` was requested.
- Every Bambu entry has return code zero, is not timed out, has no critical log pattern, and lists slice output.
- Project-status metadata reports all five true Bambu projects verified.

Exit status 1 means at least one critical validation failure. Exit status 2
normally indicates command usage or report-writing failure. Neither is a pass.

Warnings are deliberately noncritical, but they are not meaningless. Common
examples include:

- `bambu.skipped`: no CLI slicing was requested, so the full gate is incomplete.
- Legacy metadata field: the current release may parse, but the metadata should be migrated.
- Geometry measurement unavailable: declared keyring intent was found, but the opening could not be measured automatically.
- Optional artifact ambiguity: multiple handoff, label, or preview assets require human review.

Record each warning as accepted with rationale, corrected, or escalated. Never
convert a warning to a pass merely to make the summary cleaner.

A digital PASS changes the release only to Digital candidate. It does not prove
print quality, keyring fit, impact durability, RF range, adhesion, or customer
discovery.

## Physical QA record

Assign every proof print a sample ID before testing. Record:

- Product and source file.
- Sample ID and print date.
- Filament brand, material, color, and lot.
- Printer, firmware, nozzle, plate, and process profile.
- Operator and test location.
- Tag manufacturer, seller, SKU, lot, stated chip, measured diameter, and thickness.
- Overlay stock, ink or printer, clear nonmetal overlaminate, and adhesive lot.
- Phone models, operating-system versions, case types, and NFC settings.
- Split-ring outside diameter and measured wire thickness.
- Each test result as PASS, FAIL, or NOT RUN, with notes and photographs where useful.

Do not reuse a destructive-test result from an earlier geometry revision. A
change to an eyelet, floor, hub, base, tag landing, overlay stack, print profile,
or material requires the affected physical tests to be repeated.

## Physical QA checklist

### A. Print integrity and dimensional checks

- [ ] Print one individual proof of all four products using the intended production profile.
- [ ] Inspect first layers for gaps, lifted corners, elephant foot, missing rear pieces, or unintended bridge ceilings.
- [ ] Confirm the cassette, floppy disk, and VHS backs are continuous and their NFC lands are flat.
- [ ] Measure overall X, Y, and Z dimensions and record actual values.
- [ ] Measure every media keyring opening in two directions and record the minimum diameter.
- [ ] Confirm the 25 mm tag sits flat without rocking, folding, or overlapping an edge.
- [ ] Inspect raised text, blind recess floors, flap, shutter, hubs, reel bores, guitar, hair, feet, and base for fused or missing detail.
- [ ] Confirm there are no sharp cleanup scars, loose strands, cracks, or delaminated walls.

### B. Recognition and readability

- [ ] Present each unlabelled sample at arm's length in ordinary indoor light to at least five people who were not briefed on its identity.
- [ ] Record the first object each participant names and the time to identification.
- [ ] Require at least four of five participants to identify cassette, floppy disk, and VHS correctly within two seconds without reading text.
- [ ] Confirm Trailer Swift reads as a funny punk-rock toy or bobblehead-style character rather than an unexplained support structure.
- [ ] Confirm `RAD DAD` is readable at arm's length on all three media keychains.
- [ ] Confirm `90`, `C-69`, `3.69 MB`, `T-369`, and `VHS` are readable at normal handheld distance where applicable.
- [ ] Confirm cassette tape packs are visibly unequal, reel bores show six lobes, VHS packs are asymmetric, and the floppy shutter sits above the label.

### C. Keyring installation and retention

Applies to cassette, floppy disk, and VHS only.

- [ ] Measure and record the thickest intended production split-ring wire.
- [ ] Install that ring through each eyelet by hand without a drill, knife, or forced prying.
- [ ] Require installation in 30 seconds or less without cracking, whitening, gouging, or peeling the eyelet.
- [ ] Confirm the two-sided entrance chamfers guide the ring from either face.
- [ ] Apply a 2 kg static hanging load for 60 seconds and inspect the eyelet and both roots.
- [ ] Complete 25 firm pull-and-twist cycles through the expected keychain directions.
- [ ] Remove and reinstall the production ring once, then inspect for notch growth or layer separation.
- [ ] Reject any visible crack, permanent opening distortion, root separation, or sharp damaged edge.

### D. Drop and carry durability

- [ ] Drop each media keychain from 1.0 m onto the intended hard test surface in six orientations: front, back, eyelet-first, long edge, short edge, and corner.
- [ ] Record the surface material and inspect after every impact.
- [ ] Repeat dimensional, keyring, and NFC checks after the drop sequence.
- [ ] Carry one completed media unit with an ordinary production-like key bundle for at least 72 hours.
- [ ] Inspect raised lettering, flap or shutter details, eyelet bore, TAP overlay, overlaminate, and adhesive edges after carry.
- [ ] Test Trailer Swift separately for base stability, head and neck integrity, hair, guitar, feet, and nameplate retention.
- [ ] Confirm Trailer Swift stands without rocking on a level surface and remains standing on a 10 degree incline.
- [ ] Record any Trailer Swift drop height and orientation actually tested; do not infer a pass from the media keychain results.

### E. NFC range and completed-stack behavior

- [ ] Program and read-test the loose tag before installation.
- [ ] Complete ten consecutive reads on at least one current iPhone and one current Android phone.
- [ ] Repeat ten reads per phone after installing the tag on the printed landing.
- [ ] Repeat after applying the printed 25 mm TAP overlay.
- [ ] Repeat after applying the clear nonmetal overlaminate.
- [ ] Repeat with ordinary nonmetal phone cases installed.
- [ ] Repeat media tests with the production split ring and a representative metal key bundle attached.
- [ ] Confirm every successful read offers exactly `https://raddadband.com/qr/`.
- [ ] Record tag-detection success separately from browser, network, DNS, or website-load success.
- [ ] Measure and record the maximum repeatable read distance and phone orientation for each phone; contact-level reliability at the marked surface is mandatory.
- [ ] Retest after 24-hour adhesive cure, the drop sequence, and the 72-hour carry period.
- [ ] Reject a completed stack that is less reliable than the qualified baseline or requires an undocumented special angle.

### F. Sticker, overlay, and overlaminate adhesion

- [ ] Confirm the landing was cleaned, dried, and free of dust before installation.
- [ ] Confirm the tag remained flat during application and was pressed for 20 to 30 seconds.
- [ ] Allow the production adhesive stack to cure for 24 hours before destructive or carry testing.
- [ ] Inspect the tag, overlay, and clear overlaminate for bubbles, wrinkles, contamination, or edge overhang.
- [ ] Rub the finished TAP surface firmly 100 times with a clean dry cloth and inspect ink and edge retention.
- [ ] Attempt a light fingernail lift at four quadrants without intentionally cutting the film.
- [ ] Require no spontaneous edge lift, sliding, exposed adhesive, delamination, or tag movement.
- [ ] Repeat adhesion inspection after drop and carry testing.
- [ ] Quarantine the material lot if the same failure appears on more than one sample.

### G. User tap discovery and handoff

- [ ] Give the completed product without verbal instructions to at least five unbriefed participants.
- [ ] Record whether each person notices the TAP cue and where they first place the phone.
- [ ] Require at least four of five participants to attempt the marked NFC area within ten seconds.
- [ ] Then provide the production handoff card without coaching.
- [ ] Require all five participants to locate the marked circle, obtain a notification, and open the page using the card instructions.
- [ ] Test the handoff-card QR fallback and printed URL from the final physical card size.
- [ ] Record confusion about antenna position, phone unlocking, notification handling, or whether the item contains NFC.
- [ ] Revise the overlay or card and repeat the discovery test if the acceptance threshold is missed.

## Batch decision

Batch production may be approved only when:

- The complete digital gate passes with all ten Bambu slice results.
- Every warning has a documented disposition.
- At least one identified proof sample of every product passes every applicable nondestructive gate.
- Destructive and durability samples pass the recorded test plan.
- The exact production NFC tag, overlay, clear nonmetal overlaminate, filament, process, and split ring were used.
- Failed samples were corrected and every affected test was repeated.
- The approver, date, release identity, sample IDs, and evidence location are recorded.

If any required physical test has not been performed, report the release as
Digital candidate or Physical candidate as appropriate. Never describe it as
batch-ready.
