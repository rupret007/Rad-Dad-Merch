"""Authentic, one-piece micro media models for the Rad Dad NFC collection.

The three public builders return connected, watertight ``trimesh.Trimesh``
objects in millimeters.  Each model prints flat, keeps a continuous rear NFC
landing, and uses blind front recesses instead of unsupported through-holes.
"""

from __future__ import annotations

import argparse as _argparse
import math as _math
from pathlib import Path as _Path

import numpy as _np
import trimesh as _trimesh
from shapely.geometry import Point as _Point
from shapely.geometry import Polygon as _Polygon
from shapely.ops import unary_union as _unary_union

import cad_primitives_v7 as _v6


__all__ = ["build_cassette_v7", "build_floppy_v7", "build_vhs_v7"]


def _extrude(shape, z0: float, z1: float) -> _trimesh.Trimesh:
    return _v6.extrude_shape(shape, z0, z1)


def _annulus(cx: float, cy: float, inner: float, outer: float):
    return _v6.annulus_shape(cx, cy, inner, outer)


def _frustum(
    radius_bottom: float,
    radius_top: float,
    z0: float,
    z1: float,
    cx: float,
    cy: float,
    sections: int = 96,
) -> _trimesh.Trimesh:
    angles = _np.linspace(0.0, 2.0 * _math.pi, sections, endpoint=False)
    bottom = _np.column_stack(
        (
            cx + radius_bottom * _np.cos(angles),
            cy + radius_bottom * _np.sin(angles),
            _np.full(sections, z0),
        )
    )
    top = _np.column_stack(
        (
            cx + radius_top * _np.cos(angles),
            cy + radius_top * _np.sin(angles),
            _np.full(sections, z1),
        )
    )
    vertices = _np.vstack((bottom, top, ((cx, cy, z0), (cx, cy, z1))))
    bottom_center = sections * 2
    top_center = bottom_center + 1
    faces: list[tuple[int, int, int]] = []
    for index in range(sections):
        nxt = (index + 1) % sections
        faces.extend(
            (
                (index, nxt, sections + nxt),
                (index, sections + nxt, sections + index),
                (bottom_center, nxt, index),
                (top_center, sections + index, sections + nxt),
            )
        )
    return _trimesh.Trimesh(vertices=vertices, faces=_np.asarray(faces), process=True)


def _vhs_six_rib_hub(cx: float, cy: float):
    """Return a coarse, printable VHS reel hub with six positive ribs."""

    core = _Point(cx, cy).buffer(1.55, quad_segs=48)
    rim = _annulus(cx, cy, 3.15, 3.95)
    ribs = []
    for angle in range(0, 360, 60):
        radians = _math.radians(angle)
        ribs.append(
            _v6.rotated_rect(
                2.55,
                0.95,
                float(angle),
                cx + 2.30 * _math.cos(radians),
                cy + 2.30 * _math.sin(radians),
            )
        )
    return _unary_union((core, rim, *ribs)).buffer(0)


def _eyelet_cutters(
    cx: float,
    cy: float,
    top: float,
    chamfer_depth: float = 0.68,
) -> tuple[_trimesh.Trimesh, ...]:
    """Return a 6 mm bore with 7 mm lead-ins on both eyelet faces."""

    return (
        _extrude(_Point(cx, cy).buffer(3.00, quad_segs=64), -0.25, top + 0.25),
        _frustum(3.50, 3.00, -0.10, chamfer_depth, cx, cy),
        _frustum(3.00, 3.50, top - chamfer_depth, top + 0.10, cx, cy),
    )


def _finalize(mesh: _trimesh.Trimesh, name: str) -> _trimesh.Trimesh:
    result = _v6.bed_normalized(mesh)
    result.merge_vertices()
    result.remove_unreferenced_vertices()
    vertices = _np.asarray(result.vertices)
    faces = _np.asarray(result.faces)
    parent = _np.arange(len(vertices), dtype=_np.int64)
    rank = _np.zeros(len(vertices), dtype=_np.uint8)

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = int(parent[index])
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if rank[left_root] < rank[right_root]:
            parent[left_root] = right_root
        elif rank[left_root] > rank[right_root]:
            parent[right_root] = left_root
        else:
            parent[right_root] = left_root
            rank[left_root] += 1

    for a, b, c in faces:
        union(int(a), int(b))
        union(int(b), int(c))
    component_count = len({find(int(face[0])) for face in faces})
    if component_count != 1:
        raise RuntimeError(f"{name} produced {component_count} connected bodies")
    if not result.is_watertight:
        raise RuntimeError(f"{name} is not watertight")
    return result


def _screw_cutters(
    positions: tuple[tuple[float, float], ...],
    z0: float,
    z1: float,
) -> list[_trimesh.Trimesh]:
    cutters: list[_trimesh.Trimesh] = []
    for index, (x, y) in enumerate(positions):
        cutters.append(_extrude(_Point(x, y).buffer(0.86, quad_segs=24), z0, z1))
        cutters.append(
            _extrude(
                _v6.rotated_rect(1.28, 0.58, 24.0 if index % 2 == 0 else -24.0, x, y),
                z0 - 0.08,
                z1,
            )
        )
    return cutters


def build_cassette_v7() -> _trimesh.Trimesh:
    """Build the v36-size cassette with more authentic tape mechanics."""

    body_width = 50.324
    body_height = 30.260
    shell_top = 5.850
    eyelet_center = (27.000, 0.300)

    body = _v6.rounded_shape(body_width, body_height, 1.55)
    # The scallop terminates at x=21.20 while the bore begins at x=24.00,
    # leaving a 2.80 mm straight approach for a split ring.  Two broad roots
    # restore the material above and below that approach.
    shell_scallop = _Point(26.20, eyelet_center[1]).buffer(5.00, quad_segs=48)
    body = body.difference(shell_scallop)
    eyelet = _Point(*eyelet_center).buffer(6.00, quad_segs=64)
    # Two broad roots preserve more than 2.5 mm of structure above and below
    # the scallop while leaving the central threading approach unobstructed.
    connector = _unary_union(
        (
            _v6.rounded_bounds(20.70, 2.65, 27.80, 6.10, 1.15),
            _v6.rounded_bounds(20.70, -5.50, 27.80, -2.05, 1.15),
            eyelet,
        )
    ).buffer(0)
    shell_plan = _unary_union((body, connector, eyelet)).buffer(0)
    shell = _extrude(shell_plan, 0.0, shell_top)

    reel_y = 1.10
    reel_xs = (-10.70, 10.70)
    reel_radii = (6.40, 5.40)
    window_inner = _v6.rounded_shape(7.45, 5.90, 0.68, 0.0, reel_y)
    transport_shapes = (
        _Point(-15.40, -10.65).buffer(1.60, quad_segs=32),
        _v6.rounded_shape(2.90, 3.25, 0.55, -7.55, -10.65),
        _v6.rounded_shape(5.20, 2.85, 0.58, 0.0, -10.65),
        _v6.rounded_shape(2.90, 3.25, 0.55, 7.55, -10.65),
        _Point(15.40, -10.65).buffer(1.60, quad_segs=32),
    )
    # Every visible mechanism is a top-open blind recess.  The reel/window
    # floors retain 4.72 mm and the transport floors retain 4.98 mm of solid
    # shell, so there are no hidden ceilings or bridges over the NFC back.
    blind_recesses = [
        _extrude(_Point(x, reel_y).buffer(radius + 0.20, quad_segs=48), 4.72, 7.0)
        for x, radius in zip(reel_xs, reel_radii)
    ]
    blind_recesses.append(_extrude(window_inner, 4.72, 7.0))
    blind_recesses.extend(_extrude(shape, 4.98, 7.0) for shape in transport_shapes)
    shell = _v6.difference_mesh(shell, blind_recesses)

    details: list[_trimesh.Trimesh] = [
        _v6.shell_ring(48.20, 28.10, 1.25, 0.60, 5.70, 6.30),
        _extrude(_annulus(*eyelet_center, 3.50, 5.58), 5.72, 6.34),
    ]

    # Keep the label above the reel pockets instead of capping their upper
    # edges.  Every raised label surface is therefore supported by solid shell.
    label_outer = _v6.rounded_shape(43.20, 6.10, 0.85, 0.0, 10.75)
    label_inner = _v6.rounded_shape(41.50, 4.50, 0.55, 0.0, 10.75)
    details.extend(
        (
            _extrude(label_outer, 5.72, 6.15),
            _extrude(label_outer.difference(label_inner), 6.08, 6.48),
            _v6.raised_text(
                "RAD DAD",
                34.80,
                4.70,
                0.0,
                10.75,
                5.78,
                6.685,
                _v6.FONT_ITALIC,
                0.14,
            ),
        )
    )

    for x, radius in zip(reel_xs, reel_radii):
        tape_pack = _annulus(x, reel_y, 3.52, radius)
        hub = _Point(x, reel_y).buffer(3.62, quad_segs=64)
        details.extend(
            (
                _extrude(tape_pack, 4.64, 6.18),
                _extrude(hub, 4.64, 6.42),
                _extrude(_annulus(x, reel_y, radius - 1.05, radius - 0.50), 6.10, 6.52),
            )
        )

    window_outer = _v6.rounded_shape(9.05, 7.45, 0.92, 0.0, reel_y)
    window_frame = window_outer.difference(window_inner)
    details.extend(
        (
            _extrude(window_frame, 5.70, 6.42),
            _extrude(_v6.rounded_shape(1.35, 5.15, 0.28, 0.0, reel_y), 4.64, 5.58),
            _extrude(_v6.rounded_shape(6.30, 0.60, 0.20, 0.0, reel_y + 1.62), 4.64, 5.45),
            _extrude(_v6.rounded_shape(6.30, 0.60, 0.20, 0.0, reel_y - 1.62), 4.64, 5.45),
        )
    )

    transport_outer = _Polygon(
        ((-19.10, -8.05), (19.10, -8.05), (16.85, -13.75), (-16.85, -13.75))
    )
    transport_inner = _Polygon(
        ((-17.55, -8.80), (17.55, -8.80), (15.70, -12.95), (-15.70, -12.95))
    )
    details.extend(
        (
            _extrude(transport_outer.difference(transport_inner), 5.72, 6.38),
            _extrude(_v6.rounded_shape(2.80, 1.10, 0.26, 0.0, -10.65), 4.90, 5.58),
            _v6.raised_text(
                "90",
                3.45,
                2.15,
                -20.55,
                -6.45,
                5.75,
                6.48,
                _v6.FONT_BOLD,
                0.15,
            ),
            _v6.raised_text(
                "C-69",
                4.80,
                1.90,
                19.35,
                -6.45,
                5.75,
                6.46,
                _v6.FONT_CONDENSED,
                0.17,
            ),
        )
    )

    model = _v6.union_meshes([shell] + details)
    hub_recesses = [
        _extrude(_v6.star_shape(x, reel_y, 3.00, 2.30, teeth=6, phase=90.0), 5.15, 7.0)
        for x in reel_xs
    ]
    screw_positions = (
        (-22.15, 12.20),
        (22.15, 12.20),
        (-22.15, -12.15),
        (22.15, -12.15),
        (0.0, -7.20),
    )
    model = _v6.difference_mesh(
        model,
        list(_eyelet_cutters(*eyelet_center, 6.34))
        + hub_recesses
        + _screw_cutters(screw_positions, 5.24, 7.0),
    )
    return _finalize(model, "cassette v7")


def build_floppy_v7(
    *,
    capacity_width: float = 10.20,
    capacity_height: float = 2.30,
    capacity_center: tuple[float, float] = (8.15, -10.45),
    capacity_pixel: float = 0.22,
) -> _trimesh.Trimesh:
    """Build a v18-size floppy with configurable capacity-mark geometry.

    Defaults preserve the historical v7 model. Later wrappers can strengthen
    the capacity mark without duplicating or post-processing the full solid.
    """

    x0, x1 = -18.060, 18.500
    y0, y1 = -18.458, 18.458
    shell_top = 3.450
    eyelet_center = (20.300, 0.000)

    body = _Polygon(
        (
            (x0 + 2.35, y1),
            (x1 - 1.05, y1),
            (x1, y1 - 1.05),
            (x1, y0 + 1.05),
            (x1 - 1.05, y0),
            (x0 + 1.05, y0),
            (x0, y0 + 1.05),
            (x0, y1 - 2.35),
        )
    )
    eyelet = _Point(*eyelet_center).buffer(6.00, quad_segs=64)
    connector = _unary_union(
        (
            _Point(16.80, 0.0).buffer(4.70, quad_segs=48),
            eyelet,
        )
    ).convex_hull
    shell_plan = _unary_union((body, connector, eyelet)).buffer(0)
    shell = _extrude(shell_plan, 0.0, shell_top)
    nfc_center = (-0.04, 1.80)
    registration = _annulus(*nfc_center, 12.75, 13.12)
    write_outer = _v6.rounded_shape(3.80, 3.20, 0.48, -14.25, -14.35)
    write_inner = _v6.rounded_shape(2.30, 1.70, 0.32, -14.25, -14.35)
    write_protect = write_outer.difference(write_inner)
    density_outer = _Polygon(
        ((14.65, -12.75), (16.25, -14.35), (14.65, -15.95), (13.05, -14.35))
    )
    density_inner = _Polygon(
        ((14.65, -13.55), (15.45, -14.35), (14.65, -15.15), (13.85, -14.35))
    )
    density_window = density_outer.difference(density_inner)
    shell = _v6.difference_mesh(
        shell,
        (
            # These are narrow 0.10 mm outline engravings, not pockets.  The
            # first structural layer and the broad NFC landing stay continuous.
            _extrude(registration, -0.10, 0.10),
            _extrude(write_protect, -0.10, 0.10),
            _extrude(density_window, -0.10, 0.10),
        ),
    )

    details: list[_trimesh.Trimesh] = [
        _extrude(body.difference(body.buffer(-0.72)), 3.34, 3.95),
        _extrude(_annulus(*eyelet_center, 3.00, 5.58), 3.32, 3.98),
    ]

    shutter_outer = _v6.rounded_shape(18.00, 12.40, 0.98, -1.00, 12.05)
    shutter_inner = _v6.rounded_shape(16.30, 10.70, 0.64, -1.00, 12.05)
    shutter_panel = _extrude(shutter_outer, 3.34, 3.96)
    shutter_fold = _extrude(shutter_outer.difference(shutter_inner), 3.90, 4.13)
    details.extend((shutter_panel, shutter_fold))

    label_outer = _v6.rounded_shape(29.00, 16.20, 1.20, -0.75, -4.10)
    label_inner = _v6.rounded_shape(27.40, 14.60, 0.78, -0.75, -4.10)
    details.extend(
        (
            _extrude(label_outer, 3.33, 3.70),
            _extrude(label_outer.difference(label_inner), 3.64, 4.06),
            _v6.raised_text(
                "RAD DAD",
                24.20,
                4.55,
                -0.75,
                1.05,
                3.56,
                4.13,
                _v6.FONT_ITALIC,
                0.15,
            ),
        )
    )
    for line_y in (-2.15, -4.95, -7.75):
        details.append(
            _extrude(_v6.rounded_shape(25.20, 0.58, 0.22, -0.75, line_y), 3.54, 4.06)
        )
    details.append(
        _v6.raised_text(
            "3.69 MB",
            capacity_width,
            capacity_height,
            capacity_center[0],
            capacity_center[1],
            3.54,
            4.13,
            _v6.FONT_BOLD,
            capacity_pixel,
        )
    )

    model = _v6.union_meshes([shell] + details)
    shutter_slot = _v6.rounded_shape(3.55, 8.20, 0.42, -1.00, 12.05)
    model = _v6.difference_mesh(
        model,
        list(_eyelet_cutters(*eyelet_center, 3.98))
        + [_extrude(shutter_slot, 3.57, 4.40)],
    )
    return _finalize(model, "floppy v7")


def build_vhs_v7() -> _trimesh.Trimesh:
    """Build a miniature VHS whose first-read features are VHS-specific."""

    body_width = 58.00
    body_height = 31.90
    shell_top = 6.20
    eyelet_center = (30.80, -7.00)

    body = _v6.rounded_shape(body_width, body_height, 1.50)
    eyelet = _Point(*eyelet_center).buffer(6.00, quad_segs=64)
    connector = _unary_union(
        (
            _Point(27.00, -7.00).buffer(4.85, quad_segs=48),
            eyelet,
        )
    ).convex_hull
    shell_plan = _unary_union((body, connector, eyelet)).buffer(0)
    shell = _extrude(shell_plan, 0.0, shell_top)

    reel_y = -1.20
    reel_xs = (-17.00, 17.00)
    window_inners = [
        _v6.rounded_shape(13.60, 14.60, 1.15, x, reel_y) for x in reel_xs
    ]
    shell = _v6.difference_mesh(
        shell,
        [_extrude(window, 4.85, 7.40) for window in window_inners],
    )

    # The 25.4 mm NFC land remains completely flat.  Its narrow surrounding
    # groove is two 0.16 mm layers deep so it survives slicing without forming
    # a broad early bridge ceiling.
    rear_registration = _annulus(0.0, 0.0, 12.70, 13.35)
    shell = _v6.difference_mesh(shell, [_extrude(rear_registration, -0.10, 0.29)])

    details: list[_trimesh.Trimesh] = [
        _v6.shell_ring(56.20, 30.10, 1.25, 0.62, 6.08, 6.68),
        _extrude(_annulus(*eyelet_center, 3.50, 5.58), 6.08, 7.00),
    ]

    door = _v6.rounded_shape(56.80, 6.30, 0.90, 0.0, 12.25)
    front_lip = _v6.rounded_shape(56.80, 1.15, 0.28, 0.0, 15.32)
    hinge_bosses = (
        _Point(-26.50, 8.95).buffer(1.35, quad_segs=40),
        _Point(26.50, 8.95).buffer(1.35, quad_segs=40),
    )
    details.extend(
        (
            _extrude(door, 6.10, 6.85),
            _extrude(front_lip, 6.10, 7.00),
            _extrude(hinge_bosses[0], 6.10, 7.00),
            _extrude(hinge_bosses[1], 6.10, 7.00),
            _extrude(_v6.rounded_shape(53.80, 0.62, 0.22, 0.0, 14.35), 6.72, 7.00),
        )
    )

    for x, inner, tape_radius in zip(reel_xs, window_inners, (6.20, 5.10)):
        outer = _v6.rounded_shape(15.00, 16.00, 1.45, x, reel_y)
        tape_pack = _annulus(x, reel_y, 3.88, tape_radius)
        tape_edge = _annulus(x, reel_y, tape_radius - 0.58, tape_radius - 0.16)
        details.extend(
            (
                _extrude(outer.difference(inner), 6.08, 6.82),
                _extrude(tape_pack, 4.78, 6.25),
                _extrude(tape_edge, 6.16, 6.52),
                _extrude(_vhs_six_rib_hub(x, reel_y), 4.78, 6.55),
            )
        )

    label_outer = _v6.rounded_shape(18.00, 11.00, 0.90, 0.0, reel_y)
    label_inner = _v6.rounded_shape(16.45, 9.45, 0.55, 0.0, reel_y)
    details.extend(
        (
            _extrude(label_outer, 6.08, 6.55),
            _extrude(label_outer.difference(label_inner), 6.48, 6.88),
            _v6.raised_text(
                "RAD DAD",
                15.20,
                2.95,
                0.0,
                -0.20,
                6.42,
                7.00,
                _v6.FONT_ITALIC,
                0.15,
            ),
            _v6.raised_text(
                "T-369",
                8.20,
                2.10,
                0.0,
                -4.35,
                6.42,
                7.00,
                _v6.FONT_CONDENSED,
                0.20,
            ),
        )
    )

    insertion_arrow = _unary_union(
        (
            _Polygon(((-1.95, -11.65), (1.95, -11.65), (0.0, -9.15))),
            _v6.rounded_shape(0.92, 2.40, 0.24, 0.0, -12.40),
        )
    )
    details.extend(
        (
            _v6.raised_text(
                "VHS",
                6.10,
                2.05,
                22.10,
                -12.70,
                6.15,
                7.00,
                _v6.FONT_BOLD,
                0.17,
            ),
            _extrude(insertion_arrow, 6.10, 6.88),
        )
    )

    model = _v6.union_meshes([shell] + details)
    door_seam = _v6.rounded_shape(55.20, 0.72, 0.24, 0.0, 8.72)
    lip_seam = _v6.rounded_shape(54.80, 0.55, 0.20, 0.0, 14.65)
    latch = _v6.rounded_shape(2.60, 1.70, 0.38, 24.70, 10.65)
    write_protect = _v6.rounded_shape(2.70, 2.10, 0.36, -25.15, -8.55)
    hinge_dimples = (
        _extrude(_Point(-26.50, 8.95).buffer(0.48, quad_segs=32), 6.52, 7.20),
        _extrude(_Point(26.50, 8.95).buffer(0.48, quad_segs=32), 6.52, 7.20),
    )
    model = _v6.difference_mesh(
        model,
        list(_eyelet_cutters(*eyelet_center, 7.00))
        + [
            _extrude(door_seam, 5.74, 7.20),
            _extrude(lip_seam, 6.62, 7.20),
            _extrude(latch, 6.30, 7.20),
            _extrude(write_protect, 5.92, 7.20),
            *hinge_dimples,
        ],
    )
    return _finalize(model, "VHS v7")


def _main() -> None:
    parser = _argparse.ArgumentParser(
        description="Export the three Rad Dad media micro v7 models as STL files."
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        type=_Path,
        default=_Path("media_micro_v7_stl"),
        help="directory for the exported STL files",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    exports = (
        ("Rad_Dad_Cassette_v7.stl", build_cassette_v7()),
        ("Rad_Dad_Floppy_v7.stl", build_floppy_v7()),
        ("Rad_Dad_Mini_VHS_v7.stl", build_vhs_v7()),
    )
    for filename, mesh in exports:
        destination = args.output_dir / filename
        mesh.export(destination)
        print(destination)


if __name__ == "__main__":
    _main()
