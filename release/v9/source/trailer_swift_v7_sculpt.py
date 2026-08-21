#!/usr/bin/env python3
"""Build the Trailer Swift v7 one-piece NFC desk collectible.

The model is intentionally constructed from broad, overlapping volumes so its
silhouette and punk character survive single-color printing with a 0.4 mm
nozzle.  The public API is ``build_trailer_swift_v7()``; running this module as
a script writes the same watertight mesh to an STL path.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import trimesh
from shapely.geometry import Polygon, box as shapely_box
from shapely.ops import unary_union


MAX_ENVELOPE_MM = np.array([46.0, 46.0, 65.0], dtype=float)


def _ellipsoid(
    center: Sequence[float],
    radii: Sequence[float],
    subdivisions: int = 2,
) -> trimesh.Trimesh:
    mesh = trimesh.creation.icosphere(subdivisions=subdivisions, radius=1.0)
    transform = np.eye(4)
    transform[:3, :3] = np.diag(np.asarray(radii, dtype=float))
    transform[:3, 3] = np.asarray(center, dtype=float)
    mesh.apply_transform(transform)
    return mesh


def _cylinder_between(
    start: Sequence[float],
    end: Sequence[float],
    radius: float,
    sections: int = 32,
) -> trimesh.Trimesh:
    start_v = np.asarray(start, dtype=float)
    end_v = np.asarray(end, dtype=float)
    vector = end_v - start_v
    length = float(np.linalg.norm(vector))
    if length <= 0.0:
        raise ValueError("Cylinder endpoints must be different")
    mesh = trimesh.creation.cylinder(radius=radius, height=length, sections=sections)
    mesh.apply_transform(trimesh.geometry.align_vectors([0.0, 0.0, 1.0], vector))
    mesh.apply_translation((start_v + end_v) * 0.5)
    return mesh


def _capsule(
    start: Sequence[float],
    end: Sequence[float],
    radius: float,
    subdivisions: int = 2,
) -> trimesh.Trimesh:
    """Return a rounded, convex capsule without an internal Boolean seam."""
    start_ball = _ellipsoid(start, [radius, radius, radius], subdivisions)
    end_ball = _ellipsoid(end, [radius, radius, radius], subdivisions)
    points = np.vstack((start_ball.vertices, end_ball.vertices))
    return trimesh.Trimesh(vertices=points, process=False).convex_hull


def _tapered_blob(
    centers: Sequence[Sequence[float]],
    radii: Sequence[Sequence[float] | float],
    subdivisions: int = 2,
) -> trimesh.Trimesh:
    """Create one smooth convex volume through differently sized ellipsoids."""
    if len(centers) != len(radii):
        raise ValueError("Each center needs a matching radius")
    clouds: list[np.ndarray] = []
    for center, radius in zip(centers, radii):
        if isinstance(radius, (float, int)):
            radius_xyz = [float(radius)] * 3
        else:
            radius_xyz = radius
        clouds.append(_ellipsoid(center, radius_xyz, subdivisions).vertices)
    return trimesh.Trimesh(vertices=np.vstack(clouds), process=False).convex_hull


def _top_relief(polygon: Polygon, bottom_z: float, height: float) -> trimesh.Trimesh:
    geometries = [polygon] if polygon.geom_type == "Polygon" else list(polygon.geoms)
    meshes = [
        trimesh.creation.extrude_polygon(geometry, height=height)
        for geometry in geometries
        if geometry.geom_type == "Polygon" and not geometry.is_empty
    ]
    if not meshes:
        raise RuntimeError("Top relief produced no printable polygons")
    mesh = trimesh.util.concatenate(meshes)
    mesh.apply_translation([0.0, 0.0, bottom_z])
    return mesh


def _front_relief(
    polygon_xz: Polygon,
    rear_y: float,
    depth: float,
) -> trimesh.Trimesh:
    """Extrude an X/Z polygon toward the negative-Y front of the figure."""
    mesh = trimesh.creation.extrude_polygon(polygon_xz, height=depth)
    rotate = trimesh.transformations.rotation_matrix(math.pi / 2.0, [1.0, 0.0, 0.0])
    mesh.apply_transform(rotate)
    mesh.apply_translation([0.0, rear_y, 0.0])
    return mesh


def _back_relief(
    polygon_xz: Polygon,
    front_y: float,
    depth: float,
) -> trimesh.Trimesh:
    """Extrude an X/Z polygon toward the positive-Y back of the figure."""
    mesh = _front_relief(polygon_xz, rear_y=-front_y, depth=depth)
    mirror = np.eye(4)
    mirror[1, 1] = -1.0
    mesh.apply_transform(mirror)
    return mesh


def _boolean_union(meshes: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
    parts = [mesh for mesh in meshes if mesh is not None and len(mesh.faces) > 0]
    if not parts:
        raise ValueError("No meshes supplied for union")
    result = trimesh.boolean.union(parts, engine="manifold", check_volume=False)
    if isinstance(result, trimesh.Scene):
        result = result.dump(concatenate=True)
    if not isinstance(result, trimesh.Trimesh):
        raise RuntimeError("Manifold union did not return a mesh")
    result.remove_unreferenced_vertices()
    result.merge_vertices()
    result.process(validate=True)
    if result.volume < 0.0:
        result.invert()
    return result


def _boolean_difference(
    body: trimesh.Trimesh,
    cutter: trimesh.Trimesh,
) -> trimesh.Trimesh:
    result = trimesh.boolean.difference(
        [body, cutter], engine="manifold", check_volume=False
    )
    if not isinstance(result, trimesh.Trimesh):
        raise RuntimeError("Manifold difference did not return a mesh")
    return result


_PIXEL_FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
}


def _pixel_text_polygon(text: str, width: float, center_y: float) -> Polygon:
    total_units = 0
    for character in text:
        total_units += 4 if character == " " else 6
    total_units -= 1
    cell = width / total_units
    if cell < 0.6:
        raise ValueError("Pixel text needs a minimum 0.6 mm printable stroke")
    x_cursor = -width * 0.5
    blocks = []
    cell_overlap = 0.03
    for character in text:
        if character == " ":
            x_cursor += 4.0 * cell
            continue
        glyph = _PIXEL_FONT[character]
        for row, pixels in enumerate(glyph):
            for column, active in enumerate(pixels):
                if active == "1":
                    x0 = x_cursor + column * cell
                    y0 = center_y + (3 - row) * cell
                    blocks.append(
                        shapely_box(
                            x0 - cell_overlap,
                            y0 - cell_overlap,
                            x0 + cell + cell_overlap,
                            y0 + cell + cell_overlap,
                        )
                    )
        x_cursor += 6.0 * cell
    # A 0.06 mm shared area makes adjacent pixels one robust glyph without
    # materially closing the 0.7 mm-class spaces between separate letters.
    polygon = unary_union(blocks).buffer(0)
    if polygon.is_empty:
        raise RuntimeError("Pixel text produced no geometry")
    return polygon


def _build_base() -> list[trimesh.Trimesh]:
    parts: list[trimesh.Trimesh] = []

    # A solid annular base contacts the build plate around its full perimeter.
    # The shallow bottom pocket protects a 25 mm NFC tag without the previous
    # 45 mm floating underside or prototype-looking perimeter feet.
    base = trimesh.creation.cylinder(radius=22.5, height=5.75, sections=128)
    base.apply_translation([0.0, 0.0, 2.875])
    pocket_profile = np.asarray(
        (
            (0.0, 0.0),
            (13.5, 0.0),
            (13.1, 0.4),
            (13.1, 0.8),
            (0.0, 0.8),
        ),
        dtype=float,
    )
    pocket = trimesh.creation.revolve(pocket_profile, cap=True, sections=128)
    parts.append(_boolean_difference(base, pocket))

    # The clean two-line plate keeps both words centered, separated, and clear
    # of the shoes. Each fused pixel stroke is at least 0.73 mm wide.
    plaque_shape = Polygon(
        [(-19.2, -6.4), (19.2, -6.4), (11.0, -19.4), (-11.0, -19.4)]
    )
    parts.append(_top_relief(plaque_shape, bottom_z=5.43, height=1.42))
    trailer = _pixel_text_polygon("TRAILER", width=30.0, center_y=-9.8)
    swift = _pixel_text_polygon("SWIFT", width=22.0, center_y=-15.6)
    parts.extend(
        [
            _top_relief(trailer, bottom_z=6.56, height=0.90),
            _top_relief(swift, bottom_z=6.56, height=0.90),
        ]
    )
    return parts


def _build_body() -> list[trimesh.Trimesh]:
    parts: list[trimesh.Trimesh] = []

    # Shoes and wide legs are fused deeply into the base and torso.
    parts.extend(
        [
            _ellipsoid([-5.1, -0.6, 7.4], [4.1, 4.8, 2.35]),
            _ellipsoid([5.1, -0.6, 7.4], [4.1, 4.8, 2.35]),
            _capsule([-4.8, 0.0, 8.2], [-3.9, 0.0, 20.5], 3.15),
            _capsule([4.8, 0.0, 8.2], [3.9, 0.0, 20.5], 3.15),
        ]
    )

    # Broad crossed bands suggest the album cover's plaid pants at one color.
    for x_center in (-4.2, 4.2):
        parts.append(_capsule([x_center - 1.8, -2.8, 12.3],
                              [x_center + 1.8, -2.8, 17.0], 0.72))
        parts.append(_capsule([x_center + 1.8, -2.8, 11.7],
                              [x_center - 1.8, -2.8, 16.4], 0.72))

    torso = _tapered_blob(
        [[0.0, 0.0, 18.8], [0.0, 0.0, 31.7]],
        [[7.4, 5.1, 4.0], [9.0, 5.7, 4.0]],
        subdivisions=2,
    )
    parts.append(torso)

    # One bold shirt emblem replaces illegible miniature lettering.
    shirt_bolt = Polygon(
        [(-2.0, 22.2), (1.8, 22.2), (-0.2, 26.0),
         (2.7, 26.0), (-2.8, 31.8), (-0.9, 27.5), (-3.3, 27.5)]
    )
    parts.append(_front_relief(shirt_bolt, rear_y=-4.8, depth=1.05))

    # Solid neck plus overlapping torus rings gives a durable faux spring.
    parts.append(_cylinder_between([0.0, 0.0, 33.0], [0.0, 0.0, 41.0], 2.9))
    for z_value in (35.8, 37.5, 39.2):
        ring = trimesh.creation.torus(
            major_radius=2.75,
            minor_radius=0.72,
            major_sections=40,
            minor_sections=12,
        )
        ring.apply_translation([0.0, 0.0, z_value])
        parts.append(ring)

    # Aggressive bent arms connect torso, hands, and guitar in multiple places.
    parts.extend(
        [
            _capsule([-7.8, 0.0, 31.0], [-11.1, -2.7, 26.3], 2.4),
            _capsule([-11.1, -2.7, 26.3], [-7.2, -5.4, 23.8], 2.3),
            _capsule([7.8, 0.0, 31.0], [11.2, -2.7, 27.2], 2.4),
            _capsule([11.2, -2.7, 27.2], [7.6, -5.7, 22.9], 2.3),
        ]
    )

    # A broad cuff and printable studs give one unmistakable punk accessory.
    parts.append(_capsule([9.8, -3.9, 25.4], [11.0, -2.9, 27.0], 2.7))
    for offset in (-1.25, 0.0, 1.25):
        parts.append(_ellipsoid([10.8 + offset, -5.1, 26.4], [0.68, 0.68, 0.68], 1))

    # A shallow vest panel and broad diagonal strap finish the rear while staying
    # completely fused to the torso and clear of the support-critical limbs.
    vest_panel = Polygon(
        [
            (-6.8, 19.6),
            (-8.0, 29.4),
            (-5.0, 32.8),
            (0.0, 31.5),
            (5.0, 32.8),
            (8.0, 29.4),
            (6.8, 19.6),
            (0.0, 18.3),
        ]
    )
    parts.extend(
        [
            _back_relief(vest_panel, front_y=4.45, depth=0.82),
            _capsule([-6.2, 4.95, 30.5], [6.0, 4.95, 20.2], 0.78),
            _capsule([0.0, 4.90, 20.2], [0.0, 4.90, 30.8], 0.48),
        ]
    )

    return parts


def _build_head() -> list[trimesh.Trimesh]:
    parts: list[trimesh.Trimesh] = []

    head = _ellipsoid([0.0, 0.0, 49.0], [13.0, 9.2, 13.5], subdivisions=3)
    mouth_cutter = _ellipsoid([0.0, -8.7, 44.9], [5.3, 3.2, 3.5], subdivisions=2)
    head = _boolean_difference(head, mouth_cutter)
    parts.append(head)

    # Seven broad, rounded flame locks produce the album character silhouette.
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

    # Large eyes, pupils, brows, nose, teeth, and tongue rely on deep relief.
    parts.extend(
        [
            _ellipsoid([-4.3, -7.45, 51.2], [2.8, 1.5, 2.35]),
            _ellipsoid([4.3, -7.45, 51.2], [2.8, 1.5, 2.35]),
            _ellipsoid([-4.0, -8.55, 50.8], [0.95, 0.75, 1.1], 1),
            _ellipsoid([4.0, -8.55, 50.8], [0.95, 0.75, 1.1], 1),
            _capsule([-6.9, -7.55, 55.2], [-2.0, -7.95, 53.7], 0.9),
            _capsule([6.9, -7.55, 55.2], [2.0, -7.95, 53.7], 0.9),
            _tapered_blob([[0.0, -8.0, 50.4], [0.0, -8.9, 48.0]],
                          [[1.25, 1.25, 1.6], [1.6, 1.0, 1.0]], 1),
        ]
    )

    for x_value in (-2.7, -0.9, 0.9, 2.7):
        tooth = trimesh.creation.box(extents=[1.55, 4.6, 1.5])
        tooth.apply_translation([x_value, -7.0, 46.7])
        parts.append(tooth)
    parts.append(_ellipsoid([0.0, -7.5, 43.2], [3.2, 2.0, 1.1], 2))

    return parts


def _build_guitar() -> list[trimesh.Trimesh]:
    parts: list[trimesh.Trimesh] = []

    # A thick offset-body electric guitar replaces the rounded cake/banjo form.
    # Its rear face overlaps the leg and torso; the broad neck also intersects
    # both hands, so the instrument reinforces the figure instead of floating.
    body_shape = Polygon(
        [
            (0.0, 18.6),
            (2.8, 15.2),
            (5.8, 16.2),
            (9.0, 14.8),
            (12.5, 17.6),
            (10.4, 20.4),
            (12.2, 23.5),
            (9.1, 26.2),
            (6.1, 24.7),
            (3.5, 27.0),
            (1.0, 24.0),
            (2.0, 21.3),
        ]
    )
    neck_start = [3.2, -5.5, 24.8]
    neck_end = [-9.6, -5.2, 36.9]
    headstock_shape = Polygon(
        [
            (-10.8, 34.7),
            (-13.8, 36.7),
            (-13.1, 39.2),
            (-8.3, 38.7),
            (-7.4, 35.8),
        ]
    )
    parts.extend(
        [
            _front_relief(body_shape, rear_y=-2.9, depth=5.5),
            _capsule(neck_start, neck_end, 2.05),
            _front_relief(headstock_shape, rear_y=-3.6, depth=4.0),
        ]
    )

    # A backed pickguard, pickup, bridge, and two broad string lines create
    # single-color guitar cues without unsupported wires or decorative slivers.
    pickguard = Polygon(
        [
            (1.7, 17.5),
            (5.3, 16.4),
            (9.8, 18.1),
            (8.5, 21.4),
            (4.3, 23.8),
            (2.1, 21.4),
        ]
    )
    parts.extend(
        [
            _front_relief(pickguard, rear_y=-8.15, depth=0.75),
            _front_relief(
                shapely_box(4.4, 18.5, 9.4, 20.2),
                rear_y=-8.18,
                depth=0.78,
            ),
            _capsule([3.3, -8.55, 17.2], [9.4, -8.55, 17.2], 0.56),
            _capsule([3.0, -7.0, 25.0], [-10.7, -6.7, 38.0], 0.45),
            _capsule([3.8, -7.0, 24.7], [-9.9, -6.7, 38.1], 0.45),
        ]
    )
    return parts


def _validate(mesh: trimesh.Trimesh) -> None:
    bodies = mesh.split(only_watertight=False)
    if len(bodies) != 1:
        raise RuntimeError(f"Expected one connected body, found {len(bodies)}")
    if not mesh.is_watertight:
        raise RuntimeError("Trailer Swift v7 mesh is not watertight")
    if not mesh.is_winding_consistent:
        raise RuntimeError("Trailer Swift v7 mesh winding is inconsistent")
    extents = mesh.extents
    if np.any(extents > MAX_ENVELOPE_MM + 1e-3):
        raise RuntimeError(
            "Trailer Swift v7 exceeds its 46 x 46 x 65 mm envelope: "
            f"{np.round(extents, 3).tolist()}"
        )
    if mesh.bounds[0, 2] < -1e-3:
        raise RuntimeError("Trailer Swift v7 extends below the build plane")


def build_trailer_swift_v7() -> trimesh.Trimesh:
    """Return the one-piece, manifold Trailer Swift v7 collectible mesh."""
    parts: list[trimesh.Trimesh] = []
    parts.extend(_build_base())
    parts.extend(_build_body())
    parts.extend(_build_head())
    parts.extend(_build_guitar())
    sculpture = _boolean_union(parts)
    sculpture.apply_translation([0.0, 0.0, -sculpture.bounds[0, 2]])
    _validate(sculpture)
    return sculpture


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the one-piece Trailer Swift v7 NFC collectible STL."
    )
    parser.add_argument("output", type=Path, help="Destination STL path")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    mesh = build_trailer_swift_v7()
    mesh.export(args.output, file_type="stl")
    dimensions = " x ".join(f"{value:.2f}" for value in mesh.extents)
    print(f"Wrote {args.output} ({dimensions} mm, watertight one-piece mesh)")


if __name__ == "__main__":
    _main()
