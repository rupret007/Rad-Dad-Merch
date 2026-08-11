"""Authenticity-preserving v9 wrappers for the Rad Dad media micros.

The v7 solids remain the dimensional source of truth.  V9 adds or subtracts
only printable detail inside those established envelopes, so the current
dimensions, 6.0 mm eyelet bores, and flat 25.4 mm QR landing surfaces are
preserved exactly.

Nominal source dimensions (millimeters):

* Cassette shell: 50.324 W x 30.260 H; eyelet center (27.000, 0.300).
* Floppy shell: x=-18.060..18.500, y=-18.458..18.458; eyelet center
  (20.300, 0.000).
* VHS shell: 58.000 W x 31.900 H; eyelet center (30.800, -7.000).
* Every eyelet bore is 6.000 mm and every protected QR land is 25.400 mm.

All rear decoration is shallow engraving outside a guarded QR circle.  The
cassette's five transport paths are open both at the front and at the physical
bottom edge, eliminating closed bridge ceilings while retaining a continuous
rear skin.
"""

from __future__ import annotations

import math as _math

import numpy as _np
import trimesh as _trimesh
from shapely.geometry import Point as _Point
from shapely.geometry import Polygon as _Polygon
from shapely.ops import unary_union as _unary_union

import media_micro_v7 as _v7


__all__ = ["build_cassette_v9", "build_floppy_v9", "build_vhs_v9"]


QR_LANDING_DIAMETER_MM = 25.400
EYELET_BORE_DIAMETER_MM = 6.000
REAR_ENGRAVING_DEPTH_MM = 0.160
QR_GUARD_MM = 0.150

MODEL_DIMENSIONS_MM = {
    "cassette": {
        "shell_width": 50.324,
        "shell_height": 30.260,
        "eyelet_center": (27.000, 0.300),
        "eyelet_bore": EYELET_BORE_DIAMETER_MM,
        "qr_landing": QR_LANDING_DIAMETER_MM,
    },
    "floppy": {
        "shell_x": (-18.060, 18.500),
        "shell_y": (-18.458, 18.458),
        "eyelet_center": (20.300, 0.000),
        "eyelet_bore": EYELET_BORE_DIAMETER_MM,
        "qr_landing": QR_LANDING_DIAMETER_MM,
    },
    "vhs": {
        "shell_width": 58.000,
        "shell_height": 31.900,
        "eyelet_center": (30.800, -7.000),
        "eyelet_bore": EYELET_BORE_DIAMETER_MM,
        "qr_landing": QR_LANDING_DIAMETER_MM,
    },
}


def _qr_guard(cx: float, cy: float):
    """Return the protected QR land plus a small manufacturing clearance."""

    radius = QR_LANDING_DIAMETER_MM / 2.0 + QR_GUARD_MM
    return _Point(cx, cy).buffer(radius, quad_segs=96)


def _rear_cutter(shape, depth: float = REAR_ENGRAVING_DEPTH_MM):
    """Create a shallow rear engraving cutter that intersects the z=0 face."""

    return _v7._extrude(shape.buffer(0), -0.080, depth)


def _perimeter_seam(plan, inset: float, width: float):
    """Return a narrow molded shell seam inset from a two-dimensional plan."""

    outer = plan.buffer(-inset)
    inner = plan.buffer(-(inset + width))
    return outer.difference(inner).buffer(0)


def _finish_without_resizing(
    source: _trimesh.Trimesh,
    modified: _trimesh.Trimesh,
    name: str,
) -> _trimesh.Trimesh:
    """Finalize one body and enforce preservation of the v7 outer envelope."""

    source_bounds = _np.asarray(source.bounds, dtype=float).copy()
    result = _v7._finalize(modified, name)
    if not _np.allclose(result.bounds, source_bounds, rtol=0.0, atol=1.0e-5):
        raise RuntimeError(f"{name} changed the v7 outer envelope")
    return result


def _screw_cue(x: float, y: float, angle: float = 0.0):
    """Return a printable recessed screw ring and single driver slot."""

    ring = _v7._annulus(x, y, 0.52, 0.92)
    slot = _v7._v6.rotated_rect(1.18, 0.30, angle, x, y)
    return _unary_union((ring, slot)).buffer(0)


def _radial_hub_cue(
    cx: float,
    cy: float,
    *,
    outer_inner: float,
    outer_outer: float,
    rib_start: float,
    rib_end: float,
    rib_width: float,
    ribs: int,
):
    """Return concentric reel-drive rings joined visually by radial ribs."""

    shapes = [
        _v7._annulus(cx, cy, outer_inner, outer_outer),
        _v7._annulus(cx, cy, 1.12, 1.72),
    ]
    rib_length = rib_end - rib_start
    rib_radius = (rib_start + rib_end) / 2.0
    for index in range(ribs):
        angle = index * 360.0 / ribs
        radians = _math.radians(angle)
        shapes.append(
            _v7._v6.rotated_rect(
                rib_length,
                rib_width,
                angle,
                cx + rib_radius * _math.cos(radians),
                cy + rib_radius * _math.sin(radians),
            )
        )
    return _unary_union(shapes).buffer(0)


def build_cassette_v9() -> _trimesh.Trimesh:
    """Build v9 from the exact audited cassette body shown in the print photos.

    The audited v36 STL supplies the complete lower transport assembly,
    including its stepped shell profile and asymmetric tape-entry apertures,
    plus the proven 6 mm bore and rear landing.  Those triangles are not
    reconstructed or simplified here.  Only vertices in the side-eyelet zone
    are moved inward to match the later compact envelope; the tape-entry edge
    is outside that zone and remains byte-for-byte identical to v36.
    """

    from pathlib import Path as _Path

    asset_path = (
        _Path(__file__).resolve().parents[1]
        / "assets"
        / "cad"
        / "Rad_Dad_Cassette_v36_COMPACT_WIDE_WIRE_EYELET_BODY.stl"
    )
    model = _trimesh.load_mesh(asset_path, file_type="stl", process=True)
    model.remove_unreferenced_vertices()

    # V36's ring ended at x=35.16 mm.  Move the complete ring 2.16 mm inward
    # while smoothly blending its neck into the shell.  All bore vertices are
    # in the full-shift zone, so the opening remains circular and exactly
    # 6.00 mm.  The transport edge sits near y=-15.13 and receives zero shift.
    import numpy as _np_local

    vertices = model.vertices.copy()
    x_weight = _np_local.clip((vertices[:, 0] - 20.70) / (26.00 - 20.70), 0.0, 1.0)
    distance_y = _np_local.abs(vertices[:, 1] - 0.30)
    y_weight = _np_local.where(
        distance_y <= 6.30,
        1.0,
        _np_local.clip((7.50 - distance_y) / 1.20, 0.0, 1.0),
    )
    vertices[:, 0] -= 2.16 * x_weight * y_weight
    model.vertices = vertices
    return _v7._finalize(model, "cassette v9 exact heritage bottom")


def build_floppy_v9() -> _trimesh.Trimesh:
    """Build the v9 floppy with authentic rear mechanics around its QR land.

    The asymmetric 36.56 x 36.916 mm v7 shell, front RAD DAD label, and 6.0 mm
    eyelet are preserved.  The lower-right 3.69 MB mark is rebuilt with larger,
    heavier 0.4 mm-nozzle-safe geometry without increasing the outer envelope.
    A shallow rear spindle witness ring, eight radial ribs, two shutter tracks,
    shell seam, and write-protect outline are clipped to the shell and excluded
    from the guarded 25.4 mm QR landing centered at (-0.04, 1.80) mm.
    """

    # The inherited capacity mark was only 10.20 x 2.30 mm. A physical print
    # showed that its counters and spacing were marginal with a 0.4 mm nozzle.
    # Build the larger mark as part of the original Boolean assembly rather
    # than stacking a second shell onto a finalized mesh. This keeps one
    # watertight body and the exact established 4.130 mm maximum thickness.
    source = _v7.build_floppy_v7(
        capacity_width=12.60,
        capacity_height=2.85,
        capacity_center=(6.45, -10.25),
        capacity_pixel=0.18,
    )

    x0, x1 = -18.060, 18.500
    y0, y1 = -18.458, 18.458
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
    nfc_center = (-0.04, 1.80)

    shell_seam = _perimeter_seam(body, 0.52, 0.34)
    spindle_ring = _v7._annulus(*nfc_center, 13.28, 13.92)
    spindle_ribs = []
    for index in range(8):
        angle = index * 45.0
        radians = _math.radians(angle)
        spindle_ribs.append(
            _v7._v6.rotated_rect(
                2.10,
                0.38,
                angle,
                nfc_center[0] + 15.00 * _math.cos(radians),
                nfc_center[1] + 15.00 * _math.sin(radians),
            )
        )

    shutter_tracks = (
        _v7._v6.rounded_shape(16.20, 0.42, 0.16, -1.00, 16.05),
        _v7._v6.rounded_shape(16.20, 0.42, 0.16, -1.00, 17.15),
        _v7._v6.rounded_shape(0.42, 2.20, 0.16, -9.10, 16.60),
        _v7._v6.rounded_shape(0.42, 2.20, 0.16, 7.10, 16.60),
    )
    write_outer = _v7._v6.rounded_shape(4.90, 4.20, 0.58, -14.10, -14.10)
    write_inner = _v7._v6.rounded_shape(3.25, 2.55, 0.36, -14.10, -14.10)
    write_protect = write_outer.difference(write_inner)

    rear_cues = _unary_union(
        (
            shell_seam,
            spindle_ring,
            *spindle_ribs,
            *shutter_tracks,
            write_protect,
        )
    )
    rear_cues = (
        rear_cues.intersection(body.buffer(-0.24))
        .difference(_qr_guard(*nfc_center))
        .buffer(0)
    )

    modified = _v7._v6.difference_mesh(source, (_rear_cutter(rear_cues),))
    return _finish_without_resizing(source, modified, "floppy v9")


def build_vhs_v9() -> _trimesh.Trimesh:
    """Build the v9 VHS with recognizable rear reel-drive construction.

    The 58.0 x 31.9 mm v7 shell, front RAD DAD and T-369 markings, 6.0 mm
    eyelet, and centered 25.4 mm QR landing remain unchanged.  Rear reel-drive
    rings and six-rib hubs sit at the authentic front-reel axes, accompanied by
    a shell seam, loading-door tracks, corner screws, latch, and write-protect
    cues.  Every cue is a shallow recess outside the QR guard.
    """

    source = _v7.build_vhs_v7()

    body = _v7._v6.rounded_shape(58.00, 31.90, 1.50)
    shell_seam = _perimeter_seam(body, 0.50, 0.34)
    reel_cues = (
        _radial_hub_cue(
            -17.00,
            -1.20,
            outer_inner=3.18,
            outer_outer=4.22,
            rib_start=1.62,
            rib_end=3.50,
            rib_width=0.42,
            ribs=6,
        ),
        _radial_hub_cue(
            17.00,
            -1.20,
            outer_inner=3.18,
            outer_outer=4.22,
            rib_start=1.62,
            rib_end=3.50,
            rib_width=0.42,
            ribs=6,
        ),
    )
    door_tracks = (
        _v7._v6.rounded_shape(53.00, 0.48, 0.17, 0.0, 11.35),
        _v7._v6.rounded_shape(51.20, 0.42, 0.15, 0.0, 13.35),
        _v7._v6.rounded_shape(2.90, 1.50, 0.34, 24.60, 10.05),
    )
    screw_cues = (
        _screw_cue(-25.00, 12.20, 22.0),
        _screw_cue(25.00, 12.20, -22.0),
        _screw_cue(-25.00, -12.20, -22.0),
        _screw_cue(25.00, -12.20, 22.0),
    )
    protect_outer = _v7._v6.rounded_shape(3.55, 2.75, 0.42, -25.00, -8.30)
    protect_inner = _v7._v6.rounded_shape(2.20, 1.40, 0.24, -25.00, -8.30)
    write_protect = protect_outer.difference(protect_inner)

    rear_cues = _unary_union(
        (
            shell_seam,
            *reel_cues,
            *door_tracks,
            *screw_cues,
            write_protect,
        )
    )
    rear_cues = (
        rear_cues.intersection(body.buffer(-0.24))
        .difference(_qr_guard(0.0, 0.0))
        .buffer(0)
    )

    # V7's label lettering is already fused into the source mesh.  Clear only
    # the writable interior of that label down to a uniform z=6.50 mm floor;
    # the 0.30+ mm XY margin keeps the raised label frame untouched.  The new
    # text begins at z=6.48 mm, overlapping the retained floor by 0.02 mm so
    # every glyph is positively supported and joined to the main shell.
    label_text_clear = _v7._v6.rounded_shape(15.75, 8.85, 0.42, 0.0, -1.20)
    label_text_cutter = _v7._extrude(
        label_text_clear,
        6.500,
        float(source.bounds[1, 2]) + 0.300,
    )
    modified = _v7._v6.difference_mesh(
        source,
        (_rear_cutter(rear_cues), label_text_cutter),
    )
    replacement_label_text = (
        _v7._v6.raised_text(
            "RAD DAD",
            16.00,
            4.10,
            0.00,
            -0.35,
            6.480,
            7.000,
            _v7._v6.FONT_BOLD,
            0.10,
        ),
        _v7._v6.raised_text(
            "T-369",
            6.50,
            1.35,
            0.00,
            -4.35,
            6.480,
            7.000,
            _v7._v6.FONT_CONDENSED,
            0.12,
        ),
    )
    modified = _v7._v6.union_meshes([modified, *replacement_label_text])
    return _finish_without_resizing(source, modified, "VHS v9")
