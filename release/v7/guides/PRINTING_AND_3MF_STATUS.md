# Printing and 3MF package status

## Model-only Core 3MF

The Core writer in `src/v7_release_packaging.py` packages meshes, object names,
metadata, and an optional thumbnail. It does **not** embed Bambu printer or
process settings. Model-only files should include `MODEL_ONLY` in their names.

## True Bambu project 3MF

A true project file must be generated through a separate Bambu-specific
postprocessor implementing `BambuProjectPostprocessor`. The postprocessor must
embed an explicit A1 Mini / 0.4 mm nozzle profile and verify the resulting file.
Only those files should include `A1_MINI_0.4_PROJECT` in their names.

## Required v7 print intents

| Model | Printer/nozzle | Layer | Supports | Orientation |
|---|---|---:|---|---|
| Rad Dad Compact Cassette v37 | Bambu Lab A1 mini, 0.4 mm | 0.16 mm | off | flat |
| Rad Dad 3.5-Inch Floppy v19 | Bambu Lab A1 mini, 0.4 mm | 0.16 mm | off | flat |
| Rad Dad Mini VHS v4 | Bambu Lab A1 mini, 0.4 mm | 0.16 mm | off | flat |
| Rad Dad Micro Replicas v7 All-Four Plate | Bambu Lab A1 mini, 0.4 mm | 0.16 mm | organic, build plate only | mixed |
| Trailer Swift v5 Punk Desk Toy | Bambu Lab A1 mini, 0.4 mm | 0.16 mm | organic, build plate only | upright |

The individual cassette, floppy, and VHS projects use supports off. The
individual Trailer Swift project uses organic supports restricted to the build
plate. The all-four combined Bambu project uses global `tree(auto)` supports,
restricted to the build plate, so Trailer Swift can print on the same plate.
Before printing the combined project, open Preview and confirm that no
unnecessary support is generated beneath or around the cassette, floppy, or
VHS. If media support appears, correct the object-level support assignment and
slice again. These are explicit intents, not proof that a Core 3MF contains
those settings. Review every sliced layer, especially eyelets, blind recesses,
the VHS door, the figure neck, guitar, flames, feet, and underside NFC landing.
