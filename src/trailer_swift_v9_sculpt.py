#!/usr/bin/env python3
"""Build the Trailer Swift v9 friendly punk bobblehead collectible.

Version 9 preserves the proven v7 body, guitar, spiky-hair silhouette, solid
base, support intent, and 27 mm protected underside landing.  It replaces the
angry face with a mischievous, approachable singing expression and gives the
top-front name plaque stronger, more legible relief.  All additions are broad,
fused features intended for a one-color 0.4 mm-nozzle print.

The public API is ``build_trailer_swift_v9()``.  Running this module directly
exports the same single connected watertight body as an STL file.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon

from trailer_swift_v7_sculpt import (
    _boolean_difference,
    _boolean_union,
    _build_body,
    _build_guitar,
    _capsule,
    _cylinder_between,
    _ellipsoid,
    _pixel_text_polygon,
    _tapered_blob,
    _top_relief,
)


EXACT_ENVELOPE_MM = np.array([45.0, 45.0, 64.4], dtype=float)
QR_LANDING_DIAMETER_MM = 27.0


def _build_base_v9() -> list[trimesh.Trimesh]:
    """Return the v7 base geometry with clearer toy and record cues."""
    parts: list[trimesh.Trimesh] = []

    # Preserve the exact v7 base and underside profile.  The 27 mm opening
    # steps inward to a protected 26.2 mm adhesive landing, keeping a standard
    # 1-inch QR sticker recessed while the full perimeter rests on the plate.
    base = trimesh.creation.cylinder(radius=22.5, height=5.75, sections=128)
    base.apply_translation([0.0, 0.0, 2.875])
    pocket_profile = np.asarray(
        (
            (0.0, 0.0),
            (QR_LANDING_DIAMETER_MM * 0.5, 0.0),
            (13.1, 0.4),
            (13.1, 0.8),
            (0.0, 0.8),
        ),
        dtype=float,
    )
    pocket = trimesh.creation.revolve(pocket_profile, cap=True, sections=128)
    parts.append(_boolean_difference(base, pocket))

    # Low, fused rings read as a tiny vinyl-record display base without
    # introducing separate parts, support islands, or snag-prone decoration.
    for radius in (14.7, 17.5, 20.2):
        groove = trimesh.creation.torus(
            major_radius=radius,
            minor_radius=0.28,
            major_sections=96,
            minor_sections=10,
        )
        groove.apply_translation([0.0, 0.0, 5.64])
        parts.append(groove)

    # Keep the proven two-line composition, but enlarge the glyphs and deepen
    # their overlap with the plaque so TRAILER SWIFT survives real-world FDM.
    plaque_shape = Polygon(
        [(-19.2, -6.4), (19.2, -6.4), (11.0, -19.4), (-11.0, -19.4)]
    )
    parts.append(_top_relief(plaque_shape, bottom_z=5.43, height=1.55))
    trailer = _pixel_text_polygon("TRAILER", width=31.2, center_y=-9.7)
    swift = _pixel_text_polygon("SWIFT", width=23.4, center_y=-15.7)
    parts.extend(
        [
            _top_relief(trailer, bottom_z=6.65, height=1.15),
            _top_relief(swift, bottom_z=6.65, height=1.15),
        ]
    )
    return parts


def _build_friendly_head_v9() -> list[trimesh.Trimesh]:
    """Return a goofy, confident singing face under the v7 punk hair."""
    parts: list[trimesh.Trimesh] = []

    head = _ellipsoid([0.0, 0.0, 49.0], [13.0, 9.2, 13.5], subdivisions=3)

    # A wide rounded opening reads as singing or grinning.  It deliberately
    # replaces the v7 yelling cavity, individual teeth, and fang-like shapes.
    smile_cutter = _ellipsoid(
        [0.0, -8.75, 45.0], [4.9, 2.8, 2.55], subdivisions=2
    )
    head = _boolean_difference(head, smile_cutter)
    parts.append(head)

    # Preserve the seven broad v7 locks exactly, maintaining the recognizable
    # album-cover silhouette and the established 64.4 mm overall height.
    flame_specs = (
        ([-9.8, 0.7, 56.0], [-15.0, 0.7, 62.0]),
        ([-6.8, 0.4, 58.4], [-9.2, 0.4, 63.1]),
        ([-2.6, 0.2, 60.2], [-3.0, 0.2, 63.4]),
        ([2.2, 0.2, 60.2], [4.0, 0.2, 63.2]),
        ([6.5, 0.4, 58.5], [9.8, 0.4, 62.7]),
        ([9.8, 0.7, 55.8], [15.2, 0.7, 61.2]),
        ([11.1, 0.9, 52.5], [16.0, 0.9, 57.6]),
    )
    for root, tip in flame_specs:
        middle = (np.asarray(root) * 0.46 + np.asarray(tip) * 0.54).tolist()
        parts.append(
            _tapered_blob(
                [root, middle, tip],
                [[3.5, 2.9, 3.5], [2.3, 2.0, 2.4], [1.0, 0.9, 1.0]],
                subdivisions=2,
            )
        )

    # Round eyes and a shared sideways glance make the character playful.  The
    # pupils remain chunky relief rather than tiny holes that could print shut.
    parts.extend(
        [
            _ellipsoid([-4.2, -7.45, 51.25], [2.75, 1.5, 2.4]),
            _ellipsoid([4.2, -7.45, 51.25], [2.75, 1.5, 2.4]),
            _ellipsoid([-3.8, -8.55, 51.0], [0.95, 0.75, 1.05], 1),
            _ellipsoid([4.6, -8.55, 51.0], [0.95, 0.75, 1.05], 1),
        ]
    )

    # Soft two-segment arches replace the sharply down-slanted angry brows.
    # Every segment overlaps both the head and its neighbor for durability.
    brow_specs = (
        ([-6.8, -7.45, 54.85], [-4.4, -7.72, 55.45]),
        ([-4.4, -7.72, 55.45], [-2.0, -7.62, 55.15]),
        ([2.0, -7.62, 55.15], [4.4, -7.72, 55.45]),
        ([4.4, -7.72, 55.45], [6.8, -7.45, 54.85]),
    )
    for start, end in brow_specs:
        parts.append(_capsule(start, end, 0.76, subdivisions=1))

    # A compact rounded nose, raised smile corners, and a broad lower tongue
    # complete a confident open singing grin without teeth or sharp points.
    parts.extend(
        [
            _tapered_blob(
                [[0.0, -7.95, 50.1], [0.15, -8.75, 48.3]],
                [[1.15, 1.1, 1.45], [1.45, 0.95, 0.9]],
                subdivisions=1,
            ),
            _ellipsoid([-5.25, -7.65, 46.15], [0.88, 0.72, 0.82], 1),
            _ellipsoid([5.25, -7.65, 46.15], [0.88, 0.72, 0.82], 1),
            _ellipsoid([0.0, -7.65, 42.75], [3.15, 1.55, 0.85], 2),
        ]
    )

    return parts


def _validate_v9(mesh: trimesh.Trimesh) -> None:
    bodies = mesh.split(only_watertight=False)
    if len(bodies) != 1:
        raise RuntimeError(f"Expected one connected body, found {len(bodies)}")
    if not mesh.is_watertight:
        raise RuntimeError("Trailer Swift v9 mesh is not watertight")
    if not mesh.is_winding_consistent:
        raise RuntimeError("Trailer Swift v9 mesh winding is inconsistent")
    if not np.allclose(mesh.extents, EXACT_ENVELOPE_MM, atol=0.02, rtol=0.0):
        raise RuntimeError(
            "Trailer Swift v9 must retain the exact 45 x 45 x 64.4 mm envelope; "
            f"received {np.round(mesh.extents, 3).tolist()}"
        )
    if mesh.bounds[0, 2] < -1e-3:
        raise RuntimeError("Trailer Swift v9 extends below the build plane")


def build_trailer_swift_v9() -> trimesh.Trimesh:
    """Return the one-piece, friendly Trailer Swift v9 collectible mesh."""
    parts: list[trimesh.Trimesh] = []
    parts.extend(_build_base_v9())
    parts.extend(_build_body())
    parts.extend(_build_friendly_head_v9())
    parts.extend(_build_guitar())
    sculpture = _boolean_union(parts)
    sculpture.apply_translation([0.0, 0.0, -sculpture.bounds[0, 2]])
    _validate_v9(sculpture)
    return sculpture


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the one-piece Trailer Swift v9 QR collectible STL."
    )
    parser.add_argument("output", type=Path, help="Destination STL path")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    mesh = build_trailer_swift_v9()
    mesh.export(args.output, file_type="stl")
    dimensions = " x ".join(f"{value:.2f}" for value in mesh.extents)
    print(f"Wrote {args.output} ({dimensions} mm, watertight one-piece mesh)")


if __name__ == "__main__":
    _main()
