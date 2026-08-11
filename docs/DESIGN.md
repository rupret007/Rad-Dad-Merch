# Rad Dad Retro Riot v7 design specification

> Old media. Loud band. One tap.

## Scope and sources of truth

This document describes the final v7 line only:

- Rad Dad Compact Cassette v37
- Rad Dad 3.5-Inch Floppy v19
- Rad Dad Mini VHS v4
- Trailer Swift v5 Punk Desk Toy

Dimensions and functional interfaces come from
`release/v7/qa/PRODUCT_METADATA.json`,
`release/v7/qa/MODEL_QA.json`, `src/media_micro_v7.py`, and
`src/trailer_swift_v7_sculpt.py`. Print behavior comes from
`src/bambu_project_v7.py`.

The models are pocket-size caricatures of recognizable hardware. They are not
literal scale reproductions. Real identifying features are preserved and made
strong enough to survive one-color FDM printing, key carry, and normal
handling.

## Final product matrix

| Product | Shipped release dimensions | Source envelope | Intended use | Print orientation | NFC location | Keyring opening |
| --- | ---: | ---: | --- | --- | --- | ---: |
| Cassette v37 | 58.162 x 30.260 x 6.685 mm | 58.162 x 30.260 x 6.685 mm | Keychain | Rear down, detailed front up | Flat rear landing | 6.0 mm |
| Floppy v19 | 44.360 x 36.916 x 4.130 mm | 44.360 x 36.916 x 4.130 mm | Keychain | Rear down, detailed front up | Rear faux-hub landing | 6.0 mm |
| Mini VHS v4 | 65.800 x 31.900 x 7.000 mm | 65.800 x 31.900 x 7.000 mm | Keychain | Rear down, detailed front up | Flat rear landing | 6.0 mm |
| Trailer Swift v5 | 45.000 x 45.000 x 64.400 mm | 46.000 x 46.000 x 65.000 mm maximum | Desk collectible | Circular base down | Pocket under the base | None |

The three media designs reserve a 26.0 mm protected NFC zone for a 25.0 mm
tag. Trailer Swift uses a 45.0 mm diameter solid circular base with a protected
underside pocket described below.

## Shared design standard

### Authenticity before branding

Each object must be identifiable before its text is read. `RAD DAD` belongs
inside the object-specific label architecture rather than replacing the
hardware that makes the object recognizable.

### Deliberate miniature stylization

Small details are simplified into broad, printable forms. Moving mechanisms
become fixed relief. Openings that would expose unsupported spans become deep
blind recesses. Thin stamped parts become stepped surfaces that produce clear
shadows in one filament color.

This is deliberate product engineering, not missing detail. The goal is the
instant recognition of a real cassette, floppy, or VHS combined with the
durability expected from carried band merchandise.

### One-color hierarchy

The models use three visual levels:

| Level | Purpose |
| --- | --- |
| Recessed | Tape windows, access openings, seams, control windows, and hardware shadows |
| Shell surface | The structural body and NFC-bearing rear |
| Raised | Labels, hubs, borders, markings, and high-priority character details |

Color changes are not required. The supplied previews and Bambu projects use
geometry, light, and shadow to reveal the hierarchy.

### Punk character without careless construction

The visual language is loud, compressed, and slightly irreverent. The
construction remains disciplined: one connected body, broad roots, useful
clearances, protected tag areas, and no decorative moving parts.

## Cassette v37

### Authentic cues

- A compact rectangular shell with a visible perimeter seam.
- Large uppercase `RAD DAD` lettering in the cassette label zone.
- Unequal tape packs so the two reels do not look like decorative matching
  circles.
- Broad six-lobe drive hubs.
- A recessed center tape window with a visible leader or tape band.
- Five cassette transport recesses and a central pressure-pad illusion.
- Five shell fasteners.
- A large `90` marking and discreet `C-69` Easter egg.

### Durability decisions

The reel and transport features are blind recesses instead of rear-opening
holes. This keeps the NFC side continuous, removes the failed unsupported
ceilings seen in earlier prototypes, and preserves a strong shell around the
lower tape path.

The source retains a 6.0 mm keyring bore, a 12.0 mm outside diameter, and a
2.8 mm straight lateral shell-to-bore threading approach. Separate lead-ins on
both eyelet faces widen the bore entrance to 7.0 mm and are 0.68 mm deep. The
eyelet is blended into the shell rather than attached as a thin post. Its
3.0 mm radial wall protects the bore while the face lead-ins help a split ring
enter from either side. These dimensions must not be reduced to improve
appearance.

### NFC integration

The programmed 25.0 mm tag is applied onto the marked flat rear landing. The
matching 25.0 mm nonmetal overlay identifies `C-69 // SIDE A` and supplies the
tap instruction without crowding the cassette front.

## Floppy v19

### Authentic cues

- A rigid, nearly square 3.5-inch shell with an asymmetric orientation chamfer.
- The shutter at the top and the writable label beneath it.
- An 18.00 x 12.40 mm shutter panel with a protected head-slot impression.
- A 29.00 x 16.20 mm writable label field.
- Raised `RAD DAD` artwork sized 24.20 x 4.55 mm.
- A small but deliberately legible `3.69 MB` capacity joke sized
  10.2 x 2.3 mm.
- Shallow 0.10 mm control outlines: a 3.80 x 3.20 mm write-protect outline and
  a separately shaped density-control diamond.
- Rear registration geometry outside the 25.0 mm NFC tag.

The `3.69 MB` marking is intentionally small. It remains a mandatory sliced
Preview and physical-print inspection item because a successful mesh check
does not prove that every character will resolve with the supplied nozzle.

### Deliberate rear treatment

A correctly scaled real floppy hub would be much smaller than the required
25.0 mm NFC tag. The plastic rear therefore stays broadly flat and lets the
overlay complete the illusion.

The 25.0 mm floppy overlay contains an approximately 11-12 mm faux gray metal
hub drawn with ordinary nonmetal ink. Its hardware graphic uses one central
clamping opening and one offset rectangular drive-engagement slot. It must not
use foil, metallic ink, conductive ink, or metal-backed stock.

### Keyring construction

The eyelet has a 6.0 mm bore inside a 12.0 mm outside ring. Its convex blended
root overlaps the shell, preventing the ring from hanging from a narrow neck.
The design favors split-ring access and durability over literal floppy
silhouette purity.

## Mini VHS v4

### Authentic cues

- A 65.8 mm complete keychain envelope, 31.9 mm high and 7.0 mm thick.
- A wide shell proportion that remains recognizable at miniature scale.
- Two independent reel windows rather than one audio-cassette-style bay.
- Smaller six-rib drive hubs and visible tape-coil arcs.
- A central paper-label zone carrying `RAD DAD`.
- A dominant full-width hinged dust-cover treatment.
- Asymmetric latch and insertion-direction details.
- Discreet `T-369` and `VHS` markings.

The dust cover, separate reel windows, and central label must identify the
object before the `VHS` text is noticed.

### Durability decisions

The VHS mechanisms are fixed relief rather than moving parts. Windows and tape
details do not open through the flat NFC rear. The 6.0 mm keyring opening is
joined through a broad corner root so carried loads transfer into the shell.

### NFC integration

The programmed 25.0 mm tag is applied onto the marked rear landing. The VHS
overlay centers `T-369`, `RAD DAD VIDEO`, and `TAP TO PLAY` inside the
circular border. The overlay is a video-label treatment, not another pair of
audio-cassette reels.

## Trailer Swift v5

### Collectible direction

Trailer Swift is a one-piece punk desk toy, not a keychain and not a functional
spring bobblehead. The design preserves the album character through:

- An oversized angry head measuring 26.0 mm across its primary head volume.
- Seven broad flame-hair locks.
- Large eyes, brows, open mouth, teeth, nose, and tongue in deep relief.
- A compact torso, short wide legs, and broad shoes fused into the base.
- Crossed bands that suggest plaid pants without fragile fine lines.
- A bold shirt lightning bolt instead of unreadable miniature shirt text.
- A durable angular punk electric-guitar form integrated with the body, leg,
  and hands; its fine styling may continue to evolve without changing the
  structural requirement.
- A two-line `TRAILER SWIFT` plaque with source strokes kept at or above
  0.60 mm.

### Solid faux spring and structural body

The neck is a solid 5.8 mm diameter core running from 33.0 to 41.0 mm above the
build plane. Three overlapping torus rings at 35.8, 37.5, and 39.2 mm create
the bobblehead spring appearance without creating a breakable or moving joint.

The arms use broad 2.3-2.4 mm radii, the legs use 3.15 mm radii, and the
instrument neck uses a 2.05 mm radius. These are structural volumes as well as
visual forms.

### Base and NFC pocket

The base is a solid 45.0 mm diameter structure with a 5.75 mm structural
height. Its underside pocket has a 27.0 mm mouth, a 26.2 mm internal diameter,
a 0.40 mm tapered entry, and a total depth of 0.80 mm. The continuous annular
underside contacts the bed and finished display surface; there are no perimeter
feet.

The pocket protects the programmed 25.0 mm tag and matching overlay below the
table-contacting annulus. It replaces the earlier flat sticker pad and
prototype perimeter feet. The printed base must stand without rocking after
the tag and overlay are installed.

## Keyring and carry standard

Cassette, floppy, and VHS each use a 6.0 mm opening. Trailer Swift intentionally
has no eyelet.

A release candidate is not approved merely because the bore measures 6.0 mm in
CAD. The physical print must accept the thickest production split ring without
forcing, cracking, or shaving the eyelet. Every root must remain free of seams,
support scars, brim remnants, and elephant-foot closure that obstructs ring
installation.

The production ring must install by hand in 30 seconds or less. After the
2 kg/60-second load and 25 pull-and-twist cycles, remove and reinstall the ring
once and inspect the bore and root for notch growth, whitening, cracking,
permanent deformation, or layer separation.

Scaling a model changes the eyelet, NFC landing, text, and mechanical
clearances together. Do not scale a production file to solve a ring-fit or text
problem.

## NFC and overlay standard

| Product | Tag | Plastic interface | Overlay identity |
| --- | ---: | --- | --- |
| Cassette | 25.0 mm | Marked flat rear landing inside a 26.0 mm protected zone | `C-69 // SIDE A` |
| Floppy | 25.0 mm | Marked rear faux-hub landing inside a 26.0 mm protected zone | `3.69 MB` and approximately 11-12 mm gray hub |
| VHS | 25.0 mm | Marked flat rear landing inside a 26.0 mm protected zone | `T-369 // RAD DAD VIDEO` |
| Trailer Swift | 25.0 mm | 27.0 mm mouth, 26.2 mm internal pocket under the base | `TRAILER SWIFT // TAP THE BASE` |

Program and verify the tag for exactly `https://raddadband.com/qr/`. Apply the
programmed 25.0 mm tag onto the marked landing, apply the matching 25.0 mm
overlay on top of the tag, then apply a clear nonmetal overlaminate over the
overlay. All tag, overlay, ink, overlaminate, and adhesive materials near the
antenna must be nonmetallic. Retest the completed stack after each application
stage, after the 24-hour adhesive cure, after drop testing, and after the
72-hour carry test.

## Recurring 3.69 joke

The media line carries one restrained capacity-format joke:

| Product | Marking | Location |
| --- | --- | --- |
| Cassette | `C-69` | Small cassette grade/capacity marking |
| Floppy | `3.69 MB` | Writable front label and overlay |
| VHS | `T-369` | Small video-length marking and overlay |
| Trailer Swift | None | The character joke already carries the concept |

The markings should reward a closer look without competing with `RAD DAD` or
the authentic hardware.

## Digital QA versus physical validation

### What digital mesh QA proves

The current v7 release metadata reports all four STLs as:

- One connected body.
- Watertight.
- Consistently wound.
- Free of boundary edges.
- Free of non-manifold edges.
- Free of degenerate faces.
- Inside the 180.0 x 180.0 x 180.0 mm A1 Mini build volume.

The packaging generator reports this aggregate state as `mesh_qa_pass`.
That field means the mesh checks passed. It does not mean the complete release,
sliced toolpaths, materials, NFC behavior, or printed products passed.

### What still requires validation

The Bambu projects are editable, unsliced project files and contain no embedded
G-code. Every project still requires slicing and Preview inspection.

Physical validation remains required before batch production. Each applicable
eyelet must hold 2 kg for 60 seconds and survive 25 pull-and-twist cycles. Each
carried media piece must survive six one-meter drops in distinct orientations
and 72 hours of normal carry. Trailer Swift uses a separately selected and
recorded drop plan; its result must never be inferred from the media tests. It
must stand without rocking on a level surface and remain standing on a
10-degree incline.

Recognition testing uses five unbriefed participants and requires at least four
of five to identify each media object within two seconds. Tap discovery uses
five unbriefed participants and requires at least four of five to attempt the
marked NFC area within ten seconds, followed by successful handoff-card use by
all five and a working QR fallback. Adhesion acceptance includes 100 firm rubs
with a clean dry cloth, light fingernail-lift checks at four quadrants, and
repeat inspection after drop and carry testing. Reliable completed-stack NFC
scanning on representative phones with final hardware attached remains
mandatory.

The separate release validator and the physical checklist are independent of
mesh QA. No product is final for batch distribution until all applicable gates
pass.
