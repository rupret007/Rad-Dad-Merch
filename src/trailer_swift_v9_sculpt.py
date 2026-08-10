#!/usr/bin/env python3
"""Build the highly detailed Trailer Swift punk collectible.

The sculpt translates the Songs You Made Me Ruin cover character into a
one-piece micro-figurine: swept flame hair, angular expressive face, ripped
shirt, plaid pants, studded cuff, performance stance, and a fully developed
offset electric guitar.  The solid display base and protected 27 mm underside
QR landing remain unchanged.  Every feature is broad, fused, and intentionally
exaggerated for a one-color 0.4 mm-nozzle print.

The public API is ``build_trailer_swift_v9()``.  Running this module directly
exports the same single connected watertight body as an STL file.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

from trailer_swift_v7_sculpt import (
    _boolean_difference,
    _boolean_union,
    _build_body,
    _build_guitar,
    _capsule,
    _cylinder_between,
    _ellipsoid,
    _front_relief,
    _pixel_text_polygon,
    _tapered_blob,
    _top_relief,
)


EXACT_ENVELOPE_MM = np.array([45.0, 45.0, 64.4], dtype=float)
QR_LANDING_DIAMETER_MM = 27.0


def _tilted_ellipsoid(
    center: list[float],
    radii: list[float],
    angle_degrees: float,
    subdivisions: int = 2,
) -> trimesh.Trimesh:
    """Return an ellipsoid tilted in the front-view X/Z plane."""
    mesh = _ellipsoid(center, radii, subdivisions)
    transform = trimesh.transformations.rotation_matrix(
        math.radians(angle_degrees), [0.0, 1.0, 0.0], point=center
    )
    mesh.apply_transform(transform)
    return mesh


_COMPACT_FONT_3X5 = {
    "A": ("010", "101", "111", "101", "101"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "I": ("111", "010", "010", "010", "111"),
    "L": ("100", "100", "100", "100", "111"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "W": ("101", "101", "101", "111", "101"),
}


def _compact_text_polygons(
    text: str,
    cell: float,
    center_y: float,
) -> list[Polygon]:
    """Return a one-line 3x5 label with a true nozzle-safe cell width."""
    normalized = text.upper()
    character_columns = [2 if character == " " else 3 for character in normalized]
    total_columns = sum(character_columns) + max(0, len(normalized) - 1)
    cursor_x = -(total_columns * cell) * 0.5
    bottom_y = center_y - 2.5 * cell
    cells: list[Polygon] = []
    for index, character in enumerate(normalized):
        if character != " ":
            pattern = _COMPACT_FONT_3X5[character]
            for row_index, row in enumerate(pattern):
                for column_index, value in enumerate(row):
                    if value != "1":
                        continue
                    x_min = cursor_x + column_index * cell
                    y_min = bottom_y + (4 - row_index) * cell
                    overlap = 0.03
                    cell_shape = Polygon(
                        [
                            (x_min - overlap, y_min - overlap),
                            (x_min + cell + overlap, y_min - overlap),
                            (x_min + cell + overlap, y_min + cell + overlap),
                            (x_min - overlap, y_min + cell + overlap),
                        ]
                    )
                    cells.append(cell_shape)
        cursor_x += character_columns[index] * cell
        if index < len(normalized) - 1:
            cursor_x += cell
    merged = unary_union(cells)
    geometries = merged.geoms if hasattr(merged, "geoms") else [merged]
    return [
        geometry
        for geometry in geometries
        if geometry.geom_type == "Polygon" and not geometry.is_empty
    ]


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

    # Two restrained outer grooves retain the record-base joke without
    # running through the nameplate or turning its lettering into visual noise.
    for radius in (19.3, 20.8):
        groove = trimesh.creation.torus(
            major_radius=radius,
            minor_radius=0.28,
            major_sections=96,
            minor_sections=10,
        )
        groove.apply_translation([0.0, 0.0, 5.64])
        parts.append(groove)

    # One compact full-name line replaces the old overlapping two-line label.
    # Its plaque occupies clear top-front space beyond the boots.
    nameplate = Polygon(
        [(-16.0, -16.4), (16.0, -16.4), (16.0, -10.5), (-16.0, -10.5)]
    )
    parts.append(_top_relief(nameplate, bottom_z=5.43, height=1.25))
    for glyph in _compact_text_polygons(
        "TRAILER SWIFT", cell=0.60, center_y=-13.45
    ):
        parts.append(_top_relief(glyph, bottom_z=6.15, height=1.05))

    return parts


def _build_friendly_head_v9() -> list[trimesh.Trimesh]:
    """Return the angular cover-character face and swept flame hair."""
    parts: list[trimesh.Trimesh] = []

    # Three overlapping facial masses make a cheeky tapered jaw rather than a
    # spherical mascot head.  The convex hull is robust and prints cleanly.
    head = _tapered_blob(
        [[0.0, 0.15, 43.7], [0.0, 0.0, 49.7], [0.0, 0.55, 55.6]],
        [[8.3, 7.0, 5.5], [12.4, 8.8, 7.8], [10.6, 7.8, 5.8]],
        subdivisions=3,
    )
    smile_cutter = _ellipsoid(
        [0.0, -8.15, 46.0], [5.45, 2.75, 3.25], subdivisions=2
    )
    head = _boolean_difference(head, smile_cutter)
    parts.append(head)

    # Broad ears, a compact chin, and sideburns establish the album character's
    # face silhouette.  All overlap deeply with the head and hair.
    parts.extend(
        [
            _ellipsoid([-11.15, 0.0, 49.5], [2.15, 1.8, 3.15], 2),
            _ellipsoid([11.15, 0.0, 49.5], [2.15, 1.8, 3.15], 2),
            _ellipsoid([0.0, -0.2, 41.9], [5.0, 5.8, 2.1], 2),
            _tapered_blob(
                [[-9.2, -0.1, 54.5], [-11.4, -0.3, 51.6]],
                [[2.2, 1.7, 2.7], [1.2, 1.1, 1.6]],
                2,
            ),
            _tapered_blob(
                [[9.2, -0.1, 54.5], [11.4, -0.3, 51.6]],
                [[2.2, 1.7, 2.7], [1.2, 1.1, 1.6]],
                2,
            ),
        ]
    )

    # Asymmetric swept flame locks follow the cover art instead of forming a
    # regular mohawk.  The tallest tip establishes the exact 64.4 mm envelope.
    flame_specs = (
        ([-9.4, 0.9, 56.0], [-10.8, 1.0, 60.0], [3.35, 2.75, 3.1]),
        ([-7.2, 0.7, 58.0], [-5.8, 0.8, 62.0], [3.25, 2.65, 3.2]),
        ([-4.0, 0.5, 59.4], [-0.8, 0.6, 63.4], [3.15, 2.55, 3.0]),
        ([-0.2, 0.5, 60.0], [4.2, 0.5, 63.0], [3.25, 2.55, 3.0]),
        ([3.4, 0.5, 59.5], [8.2, 0.6, 62.2], [3.3, 2.6, 3.1]),
        ([6.6, 0.7, 58.0], [12.0, 0.8, 61.0], [3.4, 2.7, 3.2]),
        ([9.0, 0.9, 56.0], [15.0, 1.0, 59.3], [3.45, 2.75, 3.2]),
        ([9.8, 1.0, 53.7], [16.2, 1.2, 57.0], [3.15, 2.55, 3.0]),
        ([5.8, 2.1, 56.8], [13.0, 3.0, 59.2], [2.85, 2.55, 2.8]),
    )
    for root, tip, root_radius in flame_specs:
        middle = (np.asarray(root) * 0.46 + np.asarray(tip) * 0.54).tolist()
        parts.append(
            _tapered_blob(
                [root, middle, tip],
                [root_radius, [2.0, 1.75, 2.1], [0.9, 0.8, 1.0]],
                subdivisions=2,
            )
        )

    # Two broad forward-swept locks break up the bald dome and make the hair
    # read as windblown flame rather than a regular toy mohawk.
    parts.extend(
        [
            _tapered_blob(
                [[-6.8, -2.0, 57.2], [-1.8, -3.0, 60.0], [4.8, -3.4, 61.5]],
                [[3.0, 2.1, 2.5], [2.1, 1.5, 1.8], [0.85, 0.70, 0.95]],
                subdivisions=2,
            ),
            _tapered_blob(
                [[-3.8, -3.0, 56.7], [1.0, -3.8, 58.8], [6.2, -3.8, 59.5]],
                [[2.4, 1.7, 2.0], [1.65, 1.2, 1.45], [0.70, 0.60, 0.80]],
                subdivisions=2,
            ),
        ]
    )

    # Tilted eyes and off-center pupils capture the cover's performance energy
    # without the staring circular-eyed look of the previous sculpt.
    parts.extend(
        [
            _tilted_ellipsoid([-4.20, -7.65, 52.0], [2.85, 1.30, 1.82], 12.0),
            _tilted_ellipsoid([4.20, -7.65, 52.0], [2.85, 1.30, 1.82], -12.0),
            _tilted_ellipsoid([-3.55, -8.65, 51.65], [0.76, 0.62, 0.82], 12.0, 1),
            _tilted_ellipsoid([4.85, -8.65, 51.65], [0.76, 0.62, 0.82], -12.0, 1),
        ]
    )

    # Upward outer arches read as thrilled and mischievous rather than angry.
    brow_specs = (
        ([-7.2, -7.38, 55.75], [-4.5, -7.82, 55.95]),
        ([-4.5, -7.82, 55.95], [-1.7, -7.70, 55.15]),
        ([1.7, -7.70, 55.15], [4.5, -7.82, 55.95]),
        ([4.5, -7.82, 55.95], [7.2, -7.38, 55.75]),
    )
    for start, end in brow_specs:
        parts.append(_capsule(start, end, 0.72, subdivisions=1))

    # Nose, cheek creases, a backed upper tooth bar, and tongue make the open
    # singing grin readable from normal viewing distance without sharp fangs.
    parts.extend(
        [
            _tapered_blob(
                [[0.0, -7.8, 50.7], [0.2, -8.9, 48.8]],
                [[1.2, 1.1, 1.55], [1.55, 0.95, 0.95]],
                subdivisions=1,
            ),
            _capsule([-6.2, -7.45, 47.1], [-4.7, -8.0, 45.6], 0.55, 1),
            _capsule([6.2, -7.45, 47.1], [4.7, -8.0, 45.6], 0.55, 1),
            _capsule([-3.7, -8.38, 47.75], [3.7, -8.38, 47.75], 0.78, 1),
            _ellipsoid([0.0, -6.60, 44.25], [3.45, 1.70, 1.15], 2),
        ]
    )

    return parts


def _build_detailed_body_v9() -> list[trimesh.Trimesh]:
    """Build the cover pose with plaid pants, punk shirt, boots, and cuff."""
    parts: list[trimesh.Trimesh] = []

    # Wide planted boots and splayed legs create a performance stance while
    # overlapping the base deeply enough for keychain-grade handling.
    parts.extend(
        [
            _ellipsoid([-7.0, -1.1, 7.5], [4.9, 5.0, 2.6]),
            _ellipsoid([7.0, -1.1, 7.5], [4.9, 5.0, 2.6]),
            _capsule([-6.7, 0.0, 8.5], [-4.2, 0.0, 20.7], 3.35),
            _capsule([6.7, 0.0, 8.5], [4.2, 0.0, 20.7], 3.35),
            _capsule([-10.1, -2.9, 7.0], [-4.3, -2.9, 7.0], 0.68, 1),
            _capsule([4.3, -2.9, 7.0], [10.1, -2.9, 7.0], 0.68, 1),
        ]
    )
    parts.extend(
        [
            _capsule([-10.4, -5.15, 6.55], [-3.7, -5.15, 6.55], 0.58, 1),
            _capsule([3.7, -5.15, 6.55], [10.4, -5.15, 6.55], 0.58, 1),
            _capsule([-9.2, -5.25, 8.0], [-5.2, -5.25, 8.0], 0.42, 1),
            _capsule([5.2, -5.25, 8.0], [9.2, -5.25, 8.0], 0.42, 1),
        ]
    )

    # Broad crossed relief survives one-color printing as unmistakable plaid.
    for x_center in (-5.2, 5.2):
        parts.extend(
            [
                _capsule(
                    [x_center - 2.0, -3.05, 11.5],
                    [x_center + 2.0, -3.05, 17.7],
                    0.66,
                    1,
                ),
                _capsule(
                    [x_center + 2.0, -3.05, 11.5],
                    [x_center - 2.0, -3.05, 17.7],
                    0.66,
                    1,
                ),
                _capsule(
                    [x_center - 2.2, -3.10, 14.6],
                    [x_center + 2.2, -3.10, 14.6],
                    0.42,
                    1,
                ),
                _capsule(
                    [x_center, -3.12, 10.8],
                    [x_center, -3.12, 19.0],
                    0.36,
                    1,
                ),
                _capsule(
                    [x_center - 2.2, -3.12, 17.3],
                    [x_center + 2.2, -3.12, 17.3],
                    0.36,
                    1,
                ),
            ]
        )

    torso = _tapered_blob(
        [[0.0, 0.0, 19.0], [0.0, 0.0, 26.0], [0.0, 0.0, 32.0]],
        [[7.0, 4.9, 3.6], [8.2, 5.4, 4.5], [10.0, 5.8, 3.8]],
        subdivisions=2,
    )
    parts.append(torso)

    # Belt, buckle, ripped collar, and a large lightning emblem replace blank
    # torso space without relying on unreadable miniature shirt lettering.
    bolt = Polygon(
        [(-2.0, 22.0), (1.7, 22.0), (-0.2, 26.0), (2.8, 26.0),
         (-2.8, 31.3), (-0.8, 27.4), (-3.4, 27.4)]
    )
    collar_left = Polygon([(-5.2, 31.7), (-0.5, 28.4), (-1.0, 32.6)])
    collar_right = Polygon([(5.2, 31.7), (0.5, 28.4), (1.0, 32.6)])
    parts.extend(
        [
            _capsule([-7.0, -5.0, 20.4], [7.0, -5.0, 20.4], 0.72, 1),
            _front_relief(Polygon([(-2.0, 18.8), (2.0, 18.8), (2.0, 22.1), (-2.0, 22.1)]), rear_y=-5.15, depth=0.95),
            _front_relief(bolt, rear_y=-5.15, depth=1.05),
            _front_relief(collar_left, rear_y=-5.05, depth=0.85),
            _front_relief(collar_right, rear_y=-5.05, depth=0.85),
        ]
    )

    # A solid neck with two broad toy-collar rings suggests a bobblehead
    # connection without resembling an exposed mechanical spring.
    parts.append(_cylinder_between([0.0, 0.0, 32.0], [0.0, 0.0, 41.5], 2.9))
    for z_value in (35.4, 39.0):
        ring = trimesh.creation.torus(
            major_radius=2.85,
            minor_radius=0.58,
            major_sections=40,
            minor_sections=12,
        )
        ring.apply_translation([0.0, 0.0, z_value])
        parts.append(ring)

    # Left hand grips the neck; right hand strums near the bridge.
    parts.extend(
        [
            _capsule([-8.2, 0.0, 31.0], [-11.0, -3.0, 28.0], 2.45),
            _capsule([-11.0, -3.0, 28.0], [-8.0, -5.5, 32.0], 2.25),
            _ellipsoid([-8.2, -5.7, 32.4], [2.35, 1.8, 2.25], 2),
            _capsule([8.2, 0.0, 31.0], [11.5, -3.0, 27.0], 2.45),
            _capsule([11.5, -3.0, 27.0], [8.1, -6.0, 22.2], 2.25),
            _ellipsoid([7.9, -6.2, 21.9], [2.35, 1.8, 2.15], 2),
            _capsule([10.1, -4.0, 24.8], [11.5, -3.0, 27.0], 2.68),
        ]
    )
    for x_offset, z_offset in ((-1.1, -0.5), (0.0, 0.25), (1.1, -0.5)):
        parts.append(
            _ellipsoid([10.9 + x_offset, -5.45, 26.0 + z_offset], [0.62, 0.55, 0.62], 1)
        )
    return parts


def _build_detailed_guitar_v9() -> list[trimesh.Trimesh]:
    """Build an offset punk guitar with readable hardware and flame relief."""
    parts: list[trimesh.Trimesh] = []
    body_shape = Polygon(
        [
            (0.5, 18.1), (3.0, 15.0), (6.0, 16.1), (9.3, 14.7),
            (12.7, 17.3), (10.4, 20.3), (12.3, 23.6), (9.0, 26.5),
            (6.0, 24.8), (3.1, 27.4), (0.4, 24.1), (1.8, 21.0),
        ]
    )
    neck_start = np.asarray([3.4, -5.5, 25.2], dtype=float)
    neck_end = np.asarray([-10.2, -5.25, 38.3], dtype=float)
    headstock_shape = Polygon(
        [(-11.5, 36.0), (-14.2, 37.1), (-13.8, 40.0),
         (-8.4, 39.2), (-7.6, 36.4)]
    )
    parts.extend(
        [
            _front_relief(body_shape, rear_y=-2.9, depth=5.65),
            _capsule(neck_start, neck_end, 2.12),
            _front_relief(headstock_shape, rear_y=-3.55, depth=4.25),
        ]
    )

    pickguard = Polygon(
        [(1.8, 17.3), (5.2, 16.1), (9.9, 18.0), (8.7, 21.8),
         (4.2, 24.0), (1.8, 21.2)]
    )
    flame = Polygon(
        [(5.2, 16.0), (6.0, 19.3), (7.2, 17.8), (8.2, 21.8),
         (9.0, 18.7), (10.2, 22.6), (10.5, 17.0), (8.2, 15.6)]
    )
    parts.extend(
        [
            _front_relief(pickguard, rear_y=-8.18, depth=0.72),
            _front_relief(Polygon([(3.2, 21.7), (8.7, 21.7), (8.7, 23.2), (3.2, 23.2)]), rear_y=-8.42, depth=0.78),
            _front_relief(Polygon([(4.1, 18.3), (9.2, 18.3), (9.2, 19.9), (4.1, 19.9)]), rear_y=-8.42, depth=0.78),
            _capsule([3.2, -8.68, 17.1], [9.5, -8.68, 17.1], 0.55, 1),
            _front_relief(flame, rear_y=-8.55, depth=0.58),
        ]
    )

    # Frets are perpendicular to the neck centerline and backed by the thick
    # neck.  Two broad strings, three knobs, bridge, and tuners finish the read.
    direction_xz = neck_end[[0, 2]] - neck_start[[0, 2]]
    perpendicular = np.asarray([-direction_xz[1], direction_xz[0]], dtype=float)
    perpendicular /= np.linalg.norm(perpendicular)
    for fraction in (0.18, 0.32, 0.46, 0.60, 0.74):
        center = neck_start + (neck_end - neck_start) * fraction
        half = perpendicular * 1.72
        parts.append(
            _capsule(
                [center[0] - half[0], -7.12, center[2] - half[1]],
                [center[0] + half[0], -7.12, center[2] + half[1]],
                0.28,
                1,
            )
        )
    parts.extend(
        [
            _capsule([3.0, -7.15, 25.1], [-11.1, -6.9, 38.8], 0.38, 1),
            _capsule([3.8, -7.15, 24.8], [-10.3, -6.9, 39.0], 0.38, 1),
            _ellipsoid([9.5, -8.75, 22.0], [0.72, 0.62, 0.72], 1),
            _ellipsoid([10.0, -8.75, 20.2], [0.72, 0.62, 0.72], 1),
            _ellipsoid([8.6, -8.75, 16.5], [0.72, 0.62, 0.72], 1),
        ]
    )
    for center in ((-12.8, -5.7, 38.2), (-11.7, -5.7, 39.5), (-9.8, -5.7, 39.3)):
        parts.append(_ellipsoid(center, [0.72, 0.72, 0.72], 1))
    return parts


def _build_readable_guitar_overlay_v9() -> list[trimesh.Trimesh]:
    """Strengthen the electric-guitar silhouette and its printable hardware."""
    parts: list[trimesh.Trimesh] = [
        # A short solid neck core softens the mechanical spring appearance
        # while leaving the outer rings visible as a playful bobblehead collar.
        _capsule([0.0, 0.0, 31.5], [0.0, 0.0, 41.2], 2.15, 2),
        # Offset punk-guitar body with distinct upper and lower horns.
        _ellipsoid([6.0, -6.55, 23.5], [5.8, 1.72, 4.65], 2),
        _tapered_blob(
            [[3.0, -6.50, 26.0], [0.8, -6.45, 30.0]],
            [[3.0, 1.65, 2.55], [0.85, 0.72, 1.0]],
            subdivisions=2,
        ),
        _tapered_blob(
            [[8.2, -6.50, 21.0], [12.0, -6.45, 18.5]],
            [[2.8, 1.60, 2.35], [0.90, 0.74, 1.0]],
            subdivisions=2,
        ),
        # Thick neck and angled headstock remain legible after 0.4 mm slicing.
        _capsule([3.1, -6.55, 27.0], [-11.6, -6.55, 39.0], 1.05, 2),
        _tapered_blob(
            [[-11.4, -6.55, 38.9], [-15.1, -6.50, 41.0]],
            [[1.70, 1.45, 1.55], [1.05, 0.90, 1.05]],
            subdivisions=2,
        ),
        # Raised pickguard, two pickups, and bridge provide strong one-color
        # visual hierarchy instead of relying on hairline decoration.
        _ellipsoid([6.0, -8.05, 23.8], [3.55, 0.56, 2.65], 1),
        _capsule([3.9, -8.52, 22.1], [3.9, -8.52, 25.7], 0.62, 1),
        _capsule([6.5, -8.52, 21.9], [6.5, -8.52, 25.5], 0.62, 1),
        _capsule([9.2, -8.52, 21.1], [9.2, -8.52, 25.2], 0.72, 1),
    ]
    return parts


def _build_signature_guitar_v9() -> list[trimesh.Trimesh]:
    """Build one coherent double-cutaway electric guitar in local space."""
    parts: list[trimesh.Trimesh] = []

    # Every silhouette and hardware feature shares these axes.  This avoids
    # the old stacked-body problem where the pickups, neck, and body each
    # appeared to belong to a different instrument.
    origin_xz = np.asarray([5.8, 21.4], dtype=float)
    axis_xz = np.asarray([-0.720, 0.694], dtype=float)
    axis_xz /= np.linalg.norm(axis_xz)
    across_xz = np.asarray([axis_xz[1], -axis_xz[0]], dtype=float)

    def point(u_value: float, v_value: float) -> np.ndarray:
        return origin_xz + axis_xz * u_value + across_xz * v_value

    def polygon(local_points: list[tuple[float, float]]) -> Polygon:
        return Polygon(
            [point(u_value, v_value) for u_value, v_value in local_points]
        )

    def capsule(
        u_start: float,
        v_start: float,
        u_end: float,
        v_end: float,
        y_value: float,
        radius: float,
        subdivisions: int = 1,
    ) -> trimesh.Trimesh:
        start_xz = point(u_start, v_start)
        end_xz = point(u_end, v_end)
        return _capsule(
            [start_xz[0], y_value, start_xz[1]],
            [end_xz[0], y_value, end_xz[1]],
            radius,
            subdivisions,
        )

    # Exaggerated double cutaways, a pinched waist, offset bouts, and two
    # unmistakable horns make the silhouette read before hardware is added.
    body = polygon(
        [
            (4.8, 1.45),
            (4.2, 4.35),
            (2.4, 3.35),
            (0.8, 5.55),
            (-2.4, 5.85),
            (-5.25, 3.65),
            (-5.85, 0.15),
            (-4.55, -3.75),
            (-1.70, -5.75),
            (1.45, -5.25),
            (2.45, -3.05),
            (4.35, -4.25),
            (3.45, -1.55),
            (4.8, -1.35),
        ]
    )
    neck = polygon(
        [(3.7, -1.45), (19.5, -1.05), (19.5, 1.05), (3.7, 1.45)]
    )
    headstock = polygon(
        [
            (18.9, -1.15),
            (23.0, -1.70),
            (25.0, -0.35),
            (24.25, 2.05),
            (21.7, 2.45),
            (19.0, 1.20),
        ]
    )
    parts.extend(
        [
            _front_relief(body, rear_y=-2.75, depth=5.75),
            _front_relief(neck, rear_y=-3.55, depth=4.65),
            _front_relief(headstock, rear_y=-3.50, depth=4.70),
        ]
    )

    # The pickguard follows the lower bout.  Pickup bars and bridge are all
    # perpendicular to the strings and deeply backed by the solid body.
    pickguard = polygon(
        [
            (3.0, 0.7),
            (2.1, 3.0),
            (-0.5, 4.2),
            (-3.3, 2.6),
            (-3.0, -0.3),
            (-0.6, -2.5),
            (2.2, -2.0),
        ]
    )
    flame = polygon(
        [
            (-4.7, -3.6),
            (-2.9, -2.1),
            (-3.8, -0.5),
            (-1.7, -1.5),
            (-1.8, 0.9),
            (0.2, -0.8),
            (0.8, 1.5),
            (1.8, -2.6),
            (-1.0, -4.6),
        ]
    )
    parts.extend(
        [
            _front_relief(pickguard, rear_y=-8.22, depth=0.72),
            _front_relief(flame, rear_y=-8.52, depth=0.58),
            capsule(0.4, -2.2, 0.4, 2.2, -8.62, 0.58),
            capsule(2.5, -1.95, 2.5, 1.95, -8.62, 0.58),
            capsule(-1.4, -2.55, -1.4, 2.55, -8.64, 0.70),
        ]
    )

    # Two printable strings cross the bridge, both pickups, fretboard, and
    # headstock as continuous lines.  Six broad frets reinforce scale.
    for v_value in (-0.38, 0.38):
        parts.append(capsule(-1.5, v_value, 23.7, v_value, -8.18, 0.27))
    for u_value in (6.0, 8.2, 10.5, 12.8, 15.1, 17.4):
        half_width = 1.35 - (u_value - 6.0) * 0.018
        parts.append(
            capsule(u_value, -half_width, u_value, half_width, -8.22, 0.32)
        )

    # Three controls, six tuning pegs, two strap buttons, and a jack cup finish
    # the instrument without depending on sub-nozzle engraving.
    for u_value, v_value in ((-2.6, -2.9), (-3.8, -1.25), (-0.3, -4.1)):
        center_xz = point(u_value, v_value)
        parts.append(
            _ellipsoid(
                [center_xz[0], -8.74, center_xz[1]],
                [0.70, 0.62, 0.70],
                1,
            )
        )
    for u_value, v_value in (
        (20.4, -1.45),
        (21.9, -1.65),
        (23.4, -1.35),
        (20.6, 1.45),
        (22.1, 1.80),
        (23.6, 1.45),
    ):
        center_xz = point(u_value, v_value)
        parts.append(
            _ellipsoid(
                [center_xz[0], -7.82, center_xz[1]],
                [0.63, 0.58, 0.63],
                1,
            )
        )
    for u_value, v_value in ((-5.15, 2.9), (-4.6, -3.0)):
        center_xz = point(u_value, v_value)
        parts.append(
            _ellipsoid(
                [center_xz[0], -7.92, center_xz[1]],
                [0.60, 0.55, 0.60],
                1,
            )
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
    """Return the one-piece, highly detailed Trailer Swift collectible."""
    parts: list[trimesh.Trimesh] = []
    parts.extend(_build_base_v9())
    parts.extend(_build_detailed_body_v9())
    parts.extend(_build_friendly_head_v9())
    parts.extend(_build_signature_guitar_v9())
    sculpture = _boolean_union(parts)
    sculpture.update_faces(sculpture.nondegenerate_faces())
    sculpture.remove_unreferenced_vertices()
    components = sculpture.split(only_watertight=False)
    if len(components) > 1:
        sculpture = max(components, key=lambda component: len(component.faces))
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
