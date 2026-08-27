# Rad Dad Retro Riot v9 design specification

## Product intent

The collection turns recognizable music-media hardware into durable,
single-color punk-rock keepsakes. Each object must read as its real-world
inspiration before the viewer notices the Rad Dad branding or capacity joke.
The models are designed at 100% scale for a Bambu Lab A1 mini with a 0.4 mm
nozzle. Do not scale them to solve text, eyelet, or sticker-fit problems.

## Current production models

| Product | Revision | Exact envelope | Use | Keyring bore | QR landing |
|---|---:|---:|---|---:|---:|
| Compact cassette | v38 | 58.162 x 30.260 x 6.685 mm | Keychain | 6.0 mm | 26.0 mm rear |
| 3.5-inch floppy | v22 | 44.360 x 36.916 x 4.130 mm | Keychain | 6.0 mm | 26.0 mm rear |
| Mini VHS | v5 | 65.800 x 31.900 x 7.000 mm | Keychain | 6.0 mm | 26.0 mm rear |
| Trailer Swift | v16 | 45.000 x 45.000 x 64.400 mm | Desk collectible | None | 27.0 mm underside |

The cassette, floppy, and VHS eyelets use two-sided lead-ins around a nominal
6.0 mm cylindrical opening. The reinforced neck must remain thick enough for
split-ring installation and normal key carry. The media products print flat
with their detailed faces up. Trailer Swift prints upright with tree support.

## Shared design hierarchy

Every media replica follows the same priority order:

1. Recognizable device silhouette and device-specific mechanical hardware.
2. Durable shell, eyelet, and protected sticker landing.
3. Readable `RAD DAD` branding.
4. A restrained `369` capacity-format joke.
5. Fine molded seams, screws, tracks, and registration cues.

Branding must never replace the hardware that identifies the object. Raised
features must be positively joined to the shell, and recessed details must not
break through a sticker landing or structural skin.

## Compact cassette v38

The cassette uses the audited v36 body that produced the successful physical
reference print. V38 moves only the eyelet zone inward while preserving the
complete lower transport edge.

Required recognition cues:

- Unequal tape packs and two six-lobe reel-drive hubs.
- Central tape window and pressure-pad cue.
- Raised `RAD DAD`, `90`, and the small `C-69` easter egg.
- Molded perimeter, screw, and label geometry.
- Five open lower-edge transport bays aligned with the front transport path.
- Stepped, asymmetric head, capstan, guide, and pinch-roller openings.

The transport edge is intentionally real geometry, not decorative rectangles
on the front face. It must remain open and visible from the physical bottom of
the printed cassette. The rear stays continuous for durability and QR sticker
adhesion.

## 3.5-inch floppy v22

Required recognition cues:

- Nearly square shell with asymmetric orientation chamfer.
- Top shutter panel, shutter fold, and protected head-slot impression.
- Asymmetric lower-corner write-protect and density-detection shell recesses.
- Writable front label with raised `RAD DAD` and three ruled lines.
- Centered, high-contrast `3.69 MB` capacity mark.
- Rear spindle witness ring, radial ribs, shutter tracks, shell seam, and
  write-protect treatment around the QR landing.

The physical v20 print showed that the original 10.20 x 2.30 mm capacity mark
was too difficult to read. V22 uses a 20.00 x 4.00 mm bold mark centered in the
clear shell field directly below the writable label. It is built into the original Boolean assembly,
not stacked onto a finished mesh. Its top remains at the established 4.130 mm
maximum, so the improvement does not increase the product envelope.

## Mini VHS v5

Required recognition cues:

- Wide VHS proportions that cannot be confused with an audio cassette.
- Full-width tape-door treatment and independent reel windows.
- Asymmetric tape packs with six-rib reel hubs.
- Central label with large, readable `RAD DAD` branding.
- `VHS` identity mark and restrained `T-369` running-time joke.
- Rear reel-drive rings, loading-door tracks, shell seam, screws, latch, and
  write-protect cues.

The rear cues surround the protected circular sticker landing. They must not
reduce adhesive contact or open through the shell.

## Trailer Swift v16

Trailer Swift is a funny, friendly punk-rock micro-collectible inspired by the
album persona, not a realistic portrait and not a frightening caricature.

Required cues:

- Slim, slightly cocked stylized head with layered eyelids, smile creases,
  broad singing expression, inner-ear detail, and energetic punk hair.
- Strat-style guitar with double cutaways, three pickups, pole pieces,
  pickguard fasteners, tremolo hardware, controls, and six-inline tuners.
- Stage stance, clean jeans, laced boots, and readable `TRAILER SWIFT` nameplate.
- Solid circular display base that supports the figure like a compact toy.
- Protected 27.0 mm underside landing for the 25.4 mm QR sticker.

The base, feet, neck, guitar, hair, and hands must form one connected,
watertight body. Supports must be removable without breaking the character.

## QR interaction standard

The current production interaction is a visible 25.4 mm / 1-inch matte-white
sticker. Preferred artwork is a solid-black QR. The official fallback, when
black ink is unavailable, is pure process red `#FF0000` on white from the
existing `Rad_Dad_QR_RED_` files. NFC hardware is not installed.

- Canonical destination: `https://raddadband.com/qr/`
- Legacy ordered stickers using `/tap/` remain valid through a permanent
  website redirect.
- QR matrix: 29 x 29 modules, error correction Q.
- Quiet zone: four complete white modules on all sides.
- QR field: 16.5 mm square inside the 25.4 mm circular sticker.
- Media landing: 26.0 mm minimum protected diameter.
- Trailer Swift landing: 27.0 mm protected diameter.

The sticker belongs on the rear or underside landing only. It must not cover
the device-defining front details or any keyring opening. Use no metallic,
holographic, transparent, dark, or reflective stock.

## Digital and physical acceptance

Digital acceptance requires one connected watertight body, zero boundary,
non-manifold, and degenerate edges, consistent winding, exact envelope, and fit
inside the 180 mm A1 Mini volume. Physical acceptance additionally requires a
sliced Preview review, one proof print, dimensional checks, text readability,
split-ring installation, drop/carry testing, sticker adhesion, and camera scans
on iPhone and Android. See [VALIDATION.md](VALIDATION.md).
