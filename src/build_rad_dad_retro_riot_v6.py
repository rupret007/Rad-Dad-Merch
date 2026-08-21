from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Point, Polygon, box as sbox
from shapely.ops import unary_union


REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO.parent
WORK = WORKSPACE / "work"
sys.path.insert(0, str(WORK))

from build_rad_dad_cassette_v34_easy_thread_eyelet import build_v34, load_v33_body
from build_rad_dad_floppy_authentic_v2 import build_model as build_floppy_v17
from build_rad_dad_vhs_trailer_swift_v1 import (
    FONT_BOLD,
    FONT_CONDENSED,
    FONT_ITALIC,
    difference_mesh,
    ellipse_shape,
    extrude_shape,
    mesh_report,
    raised_text,
    rotated_rect,
    rounded_shape,
    shell_ring,
    star_shape,
    text_shape,
    triangle,
    union_meshes,
    write_3mf,
    build_trailer_swift_figure,
)


RELEASE = REPO / "release" / "v6"
DIR_3MF = RELEASE / "3mf"
DIR_STL = RELEASE / "stl"
DIR_PREVIEWS = RELEASE / "previews"
DIR_GUIDES = RELEASE / "guides"
DIR_QA = RELEASE / "qa"


def rounded_bounds(x0: float, y0: float, x1: float, y1: float, radius: float):
    return sbox(x0 + radius, y0 + radius, x1 - radius, y1 - radius).buffer(
        radius, quad_segs=24
    )


def annulus_shape(cx: float, cy: float, inner: float, outer: float):
    return Point(cx, cy).buffer(outer, quad_segs=48).difference(
        Point(cx, cy).buffer(inner, quad_segs=48)
    )


def bed_normalized(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    result = mesh.copy()
    result.apply_translation((0.0, 0.0, -float(result.bounds[0, 2])))
    result.remove_unreferenced_vertices()
    return result


def build_vhs_v3() -> trimesh.Trimesh:
    width, height, thickness = 58.0, 32.6, 4.40
    eyelet_center = (35.0, 0.0)
    body = rounded_shape(width, height, 1.55)
    bridge = rounded_bounds(26.5, -6.0, 35.0, 6.0, 1.6)
    eyelet = Point(*eyelet_center).buffer(6.0, quad_segs=48)
    shell = extrude_shape(unary_union((body, bridge, eyelet)), 0.0, thickness)

    eyelet_hole = extrude_shape(
        Point(*eyelet_center).buffer(3.0, quad_segs=48), -0.2, thickness + 0.8
    )

    reel_y = -2.15
    reel_xs = (-15.1, 15.1)
    recesses = [ellipse_shape(13.3, 13.3, x, reel_y) for x in reel_xs]
    recesses.append(rounded_shape(12.4, 8.7, 1.0, 0.0, reel_y))
    top_screw_positions = (
        (-25.4, 13.1),
        (25.4, 13.1),
    )
    lower_screw_positions = (
        (-25.4, -13.1),
        (25.4, -13.1),
        (0.0, -13.0),
    )
    recesses.extend(Point(x, y).buffer(0.78, quad_segs=20) for x, y in lower_screw_positions)
    shell = difference_mesh(
        shell,
        [eyelet_hole]
        + [extrude_shape(shape, 3.55, 4.85) for shape in recesses],
    )
    screw_slots = [
        extrude_shape(rotated_rect(1.14, 0.34, -18.0, x, y), 3.12, 3.68)
        for x, y in lower_screw_positions
    ]
    shell = difference_mesh(shell, screw_slots)

    details: list[trimesh.Trimesh] = [
        shell_ring(56.0, 30.6, 1.30, 0.62, 4.12, 4.75),
    ]

    # The hinged tape door is the defining VHS feature and dominates the upper edge.
    door = rounded_shape(56.0, 5.65, 0.90, 0.0, 13.0)
    details.extend(
        (
            extrude_shape(door, 4.14, 5.18),
            extrude_shape(rounded_shape(45.0, 0.58, 0.20, 0.0, 10.45), 4.15, 4.90),
            extrude_shape(rounded_shape(9.0, 1.35, 0.30, 0.0, 11.0), 4.92, 5.42),
            extrude_shape(rounded_shape(7.0, 1.05, 0.26, -20.0, 12.7), 5.02, 5.50),
            extrude_shape(rounded_shape(7.0, 1.05, 0.26, 20.0, 12.7), 5.02, 5.50),
        )
    )

    # A restrained spine label leaves the reel bay as the visual focus.
    label = rounded_shape(34.0, 5.25, 0.75, 0.0, 7.25)
    details.extend(
        (
            extrude_shape(label, 4.12, 4.72),
            raised_text("RAD DAD", 25.8, 3.55, 0.0, 7.25, 4.55, 5.30, FONT_ITALIC, 0.13),
            extrude_shape(rounded_shape(4.8, 4.8, 0.65, -25.0, 7.25), 4.12, 4.82),
            raised_text("A", 2.20, 2.60, -25.0, 7.25, 4.62, 5.25, FONT_BOLD, 0.13),
        )
    )

    # One framed window bay, rather than cassette-style isolated decorations.
    details.append(shell_ring(49.0, 15.8, 1.35, 0.72, 3.45, 4.82, 0.0, reel_y))
    for x in reel_xs:
        roll = annulus_shape(x, reel_y, 5.15, 6.30)
        hub = Point(x, reel_y).buffer(4.15, quad_segs=40).difference(
            star_shape(x, reel_y, 2.75, 1.94, teeth=9, phase=90.0)
        )
        details.extend(
            (
                extrude_shape(roll, 3.46, 4.92),
                extrude_shape(hub, 3.46, 5.12),
                extrude_shape(Point(x, reel_y).buffer(0.88, quad_segs=24), 3.47, 4.40),
            )
        )

    details.extend(
        (
            shell_ring(12.0, 8.4, 1.00, 0.65, 3.45, 4.88, 0.0, reel_y),
            extrude_shape(rounded_shape(1.35, 5.9, 0.30, 0.0, reel_y), 3.46, 4.42),
            extrude_shape(rounded_shape(6.6, 0.62, 0.20, 0.0, reel_y + 1.8), 3.47, 4.30),
            extrude_shape(rounded_shape(6.6, 0.62, 0.20, 0.0, reel_y - 1.8), 3.47, 4.30),
        )
    )

    # Molded lower shell marks remain small and utilitarian, like a real VHS.
    details.extend(
        (
            raised_text("T-120", 6.8, 1.70, -22.0, -12.0, 4.18, 4.82, FONT_CONDENSED, 0.12),
            raised_text("VHS", 5.6, 1.75, 22.4, -12.0, 4.18, 4.86, FONT_BOLD, 0.12),
            raised_text("SP", 3.2, 1.35, 0.0, -12.0, 4.18, 4.76, FONT_CONDENSED, 0.11),
            extrude_shape(triangle((-4.2, -10.0), (-1.4, -10.0), (-2.8, -8.45)), 4.12, 4.70),
            extrude_shape(triangle((1.4, -10.0), (4.2, -10.0), (2.8, -8.45)), 4.12, 4.70),
        )
    )

    model = union_meshes([shell] + details)
    # Cut the two upper door screws only after the hinged door is fused. Doing
    # this earlier would let the door cap the recesses and trap internal voids.
    upper_screw_cutters = []
    for x, y in top_screw_positions:
        upper_screw_cutters.extend(
            (
                extrude_shape(Point(x, y).buffer(0.78, quad_segs=20), 4.72, 5.72),
                extrude_shape(rotated_rect(1.14, 0.34, -18.0, x, y), 4.48, 5.72),
            )
        )
    model = difference_mesh(model, upper_screw_cutters)
    model.remove_unreferenced_vertices()
    return bed_normalized(model)


def build_floppy_v18() -> trimesh.Trimesh:
    model = bed_normalized(build_floppy_v17())
    nfc_center = (-0.04, 1.80)
    protected_nfc = Point(*nfc_center).buffer(12.85, quad_segs=64)

    outer = rounded_bounds(-19.35, -19.15, 19.35, 19.15, 1.35)
    inner = rounded_bounds(-18.45, -18.25, 18.45, 18.25, 0.85)
    shell_seam = outer.difference(inner)
    hub_boundary = annulus_shape(*nfc_center, 13.10, 13.85)

    shutter_outer = rounded_bounds(-10.8, -18.2, 9.4, -5.0, 0.95)
    shutter_inner = rounded_bounds(-9.95, -17.35, 8.55, -5.85, 0.55)
    shutter_track = shutter_outer.difference(shutter_inner)
    shutter_slot = rounded_bounds(-2.0, -15.2, 1.1, -7.2, 0.38)

    protect_outline = rounded_bounds(14.1, 10.4, 17.65, 16.7, 0.45).difference(
        rounded_bounds(14.75, 11.05, 17.0, 16.05, 0.25)
    )
    protect_slider = rounded_bounds(14.8, 12.0, 16.95, 14.15, 0.30)
    orientation_arrow = Polygon(((13.9, -13.6), (17.1, -13.6), (15.5, -17.1)))

    screw_marks = unary_union(
        [
            Point(x, y).buffer(0.68, quad_segs=20)
            for x, y in (
                (-16.8, 16.2),
                (16.8, 16.2),
                (-16.8, -16.2),
                (16.8, -16.2),
            )
        ]
    )

    # Preserve the complete sticker contact zone while restoring recognizable rear hardware.
    rear_marks = unary_union(
        (
            shell_seam,
            hub_boundary,
            shutter_track,
            shutter_slot,
            protect_outline,
            protect_slider,
            orientation_arrow,
            screw_marks,
        )
    ).difference(protected_nfc)
    engraving = extrude_shape(rear_marks, -0.05, 0.30)
    result = difference_mesh(model, [engraving])
    result.remove_unreferenced_vertices()
    return bed_normalized(result)


def ellipsoid(rx: float, ry: float, rz: float, center: tuple[float, float, float]):
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    mesh.apply_scale((rx, ry, rz))
    mesh.apply_translation(center)
    return mesh


def vertical_mesh(mesh: trimesh.Trimesh, front_y: float, center_z: float):
    result = mesh.copy()
    result.apply_transform(
        trimesh.transformations.rotation_matrix(math.pi / 2.0, (1.0, 0.0, 0.0))
    )
    center = result.bounds.mean(axis=0)
    result.apply_translation((-center[0], front_y - result.bounds[1, 1], center_z - center[2]))
    return result


def build_trailer_swift_v4() -> trimesh.Trimesh:
    relief = build_trailer_swift_figure()
    relief.apply_scale(0.79)
    relief.apply_transform(
        trimesh.transformations.rotation_matrix(math.pi / 2.0, (1.0, 0.0, 0.0))
    )
    relief.apply_translation((-relief.bounds.mean(axis=0)[0], 0.0, 6.20 - relief.bounds[0, 2]))

    base = trimesh.creation.cylinder(radius=26.0, height=7.2, sections=128)
    base.apply_translation((0.0, 0.0, 3.6))
    upper = trimesh.creation.cylinder(radius=23.8, height=2.2, sections=128)
    upper.apply_translation((0.0, 0.0, 7.55))
    rim = trimesh.creation.cylinder(radius=26.5, height=0.72, sections=128)
    rim.apply_translation((0.0, 0.0, 6.78))

    # Rounded rear masses make the flat comic relief read as a vinyl desk toy.
    z_shift = 6.20 - (-3.95 * 0.79)
    head_center = (2.5 * 0.79, 2.1, 69.0 * 0.79 + z_shift)
    torso_center = (0.0, 2.0, 44.0 * 0.79 + z_shift)
    head_back = ellipsoid(9.3, 4.5, 10.2, head_center)
    torso_back = ellipsoid(10.2, 3.8, 13.7, torso_center)

    # Three broad collars suggest a bobble spring without introducing a moving failure point.
    spring_parts = []
    for z in (56.0, 57.15, 58.30):
        coil = trimesh.creation.cylinder(radius=3.65, height=0.72, sections=48)
        coil.apply_translation((1.6, 1.4, z))
        spring_parts.append(coil)

    # A real circular base with a thick integrated front nameplate.
    plaque = extrude_shape(rounded_shape(31.0, 5.2, 1.0), 0.0, 6.0)
    plaque.apply_transform(
        trimesh.transformations.rotation_matrix(math.pi / 2.0, (1.0, 0.0, 0.0))
    )
    plaque.apply_translation((0.0, -20.5, 4.25))
    name_cutter = raised_text("TRAILER SWIFT", 27.5, 2.72, 0.0, 0.0, 0.0, 1.20, FONT_CONDENSED, 0.12)
    name_cutter.apply_transform(
        trimesh.transformations.rotation_matrix(math.pi / 2.0, (1.0, 0.0, 0.0))
    )
    name_cutter.apply_translation((0.0, -25.60, 4.25))
    plaque = difference_mesh(plaque, [name_cutter])

    bolt_left = Polygon(((-21.2, -2.0), (-17.8, -2.0), (-19.0, 2.0), (-16.1, 2.0), (-21.0, 8.0), (-19.8, 3.3), (-22.0, 3.3)))
    bolt_right = Polygon(((21.2, -2.0), (17.8, -2.0), (19.0, 2.0), (16.1, 2.0), (21.0, 8.0), (19.8, 3.3), (22.0, 3.3)))
    stage_details = [
        extrude_shape(bolt_left, 8.50, 9.35),
        extrude_shape(bolt_right, 8.50, 9.35),
        raised_text("RAD DAD", 16.0, 2.4, 0.0, 17.1, 8.52, 9.25, FONT_ITALIC, 0.12),
        raised_text("TAP THE BASE", 17.0, 1.78, 0.0, -13.2, 8.52, 9.22, FONT_CONDENSED, 0.11),
    ]
    for angle in (25, 65, 115, 155):
        radians = math.radians(angle)
        stud = trimesh.creation.cylinder(radius=0.92, height=0.72, sections=28)
        stud.apply_translation((19.7 * math.cos(radians), 19.7 * math.sin(radians), 8.78))
        stage_details.append(stud)

    joined = union_meshes(
        [base, upper, rim, relief, head_back, torso_back, plaque]
        + spring_parts
        + stage_details
    )

    # The base remains fully supported and flat. Only a shallow ring marks the tag location.
    nfc_ring = extrude_shape(annulus_shape(0.0, 0.0, 12.90, 13.45), -0.05, 0.16)
    final = difference_mesh(joined, [nfc_ring])
    final.remove_unreferenced_vertices()
    return bed_normalized(final)


def rear_preview(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    copy = mesh.copy()
    copy.apply_transform(
        trimesh.transformations.rotation_matrix(math.pi, (1.0, 0.0, 0.0))
    )
    return bed_normalized(copy)


def draw_projected(draw, mesh, box, mode, accent):
    x0, y0, x1, y1 = box
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    normals = np.asarray(mesh.face_normals)
    if mode == "front":
        u, v, depth = vertices[:, 0], vertices[:, 2], -vertices[:, 1]
        facing = -normals[:, 1]
    elif mode == "side":
        u, v, depth = vertices[:, 1], vertices[:, 2], vertices[:, 0]
        facing = normals[:, 0]
    else:
        u, v, depth = vertices[:, 0], vertices[:, 1], vertices[:, 2]
        facing = normals[:, 2]
    u_min, u_max = float(u.min()), float(u.max())
    v_min, v_max = float(v.min()), float(v.max())
    scale = min((x1 - x0) / max(0.001, u_max - u_min), (y1 - y0) / max(0.001, v_max - v_min)) * 0.90
    ox = (x0 + x1) / 2 - (u_min + u_max) * scale / 2
    oy = (y0 + y1) / 2 + (v_min + v_max) * scale / 2
    face_depth = depth[faces].mean(axis=1)
    order = np.argsort(face_depth)
    depth_min = float(face_depth.min())
    depth_span = max(0.001, float(face_depth.max()) - depth_min)
    rgb = tuple(int(accent[index:index + 2], 16) for index in (1, 3, 5))
    for index in order:
        if facing[index] < 0.10:
            continue
        layer = (float(face_depth[index]) - depth_min) / depth_span
        shade = float(np.clip(0.24 + 0.58 * layer + 0.18 * facing[index], 0.24, 1.0))
        color = tuple(round(channel * shade) for channel in rgb)
        points = [(ox + u[vertex] * scale, oy - v[vertex] * scale) for vertex in faces[index]]
        draw.polygon(points, fill=color)


def collection_preview(path: Path, items, title: str, subtitle: str):
    image = Image.new("RGB", (1800, 1180), "#050b12")
    draw = ImageDraw.Draw(image)
    title_size = 66 if len(title) <= 34 else 54
    title_font = ImageFont.truetype(FONT_CONDENSED, title_size)
    label_font = ImageFont.truetype(FONT_BOLD, 31)
    small_font = ImageFont.truetype(FONT_BOLD, 23)
    draw.text((900, 42), title, font=title_font, fill="#f5f1e8", anchor="ma")
    draw.text((900, 112), subtitle, font=small_font, fill="#1cb5f4", anchor="ma")
    cards = ((60, 170, 870, 640), (930, 170, 1740, 640), (60, 680, 870, 1090), (930, 680, 1740, 1090))
    colors = ("#a6ef12", "#1cb5f4", "#ff3476", "#ffb000")
    for card, item, color in zip(cards, items, colors):
        label, mesh, mode = item
        draw.rounded_rectangle(card, radius=24, fill="#0c1722", outline="#253745", width=3)
        draw.text(((card[0] + card[2]) / 2, card[1] + 24), label, font=label_font, fill="#f5f1e8", anchor="ma")
        draw_projected(draw, mesh, (card[0] + 25, card[1] + 65, card[2] - 25, card[3] - 22), mode, color)
    image.save(path)


def placed_copy(mesh: trimesh.Trimesh, x: float, y: float):
    result = mesh.copy()
    center = result.bounds.mean(axis=0)
    result.apply_translation((x - center[0], y - center[1], -result.bounds[0, 2]))
    return result


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_guides():
    (DIR_GUIDES / "NFC_PLACEMENT_GUIDE.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" viewBox="0 0 1200 760">'
        '<rect width="1200" height="760" fill="#f4f0e8"/><text x="600" y="58" text-anchor="middle" font-family="Arial" font-size="38" font-weight="bold">RAD DAD RETRO RIOT v6 - NFC PLACEMENT</text>'
        '<g fill="#18212a"><rect x="80" y="125" width="430" height="250" rx="20"/><rect x="690" y="125" width="330" height="330" rx="24"/><circle cx="350" cy="585" r="115"/><circle cx="850" cy="585" r="115"/></g>'
        '<g fill="none" stroke="#ff3476" stroke-width="8" stroke-dasharray="16 12"><circle cx="295" cy="250" r="75"/><circle cx="855" cy="290" r="75"/><circle cx="350" cy="585" r="75"/><circle cx="850" cy="585" r="75"/></g>'
        '<g fill="#18212a" font-family="Arial" font-size="24" font-weight="bold" text-anchor="middle"><text x="295" y="420">MEDIA: CENTER ON FLAT REAR</text><text x="855" y="500">FLOPPY: INSIDE REAR HUB RING</text><text x="350" y="735">CASSETTE / VHS REAR</text><text x="850" y="735">TRAILER SWIFT BASE UNDERSIDE</text></g>'
        '<g fill="#f4f0e8" font-family="Arial" font-size="23" font-weight="bold" text-anchor="middle"><text x="295" y="258">25 MM NFC</text><text x="855" y="298">25 MM NFC</text><text x="350" y="593">25 MM NFC</text><text x="850" y="593">25 MM NFC</text></g></svg>',
        encoding="ascii",
    )
    label_art = (
        '<g id="taplabel">'
        '<circle cx="15" cy="15" r="12.5" fill="#050b12"/>'
        '<circle cx="15" cy="15" r="11.7" fill="none" stroke="#a6ef12" stroke-width="0.7"/>'
        '<path d="M7.2 12.2 Q10.1 15 7.2 17.8 M9.3 10.2 Q14.1 15 9.3 19.8 M11.5 8.3 Q18.2 15 11.5 21.7" fill="none" stroke="#1cb5f4" stroke-width="0.9" stroke-linecap="round"/>'
        '<circle cx="5.7" cy="15" r="1.0" fill="#1cb5f4"/>'
        '<text x="20.2" y="12.3" text-anchor="middle" font-family="Arial" font-size="2.4" font-weight="bold" fill="#f5f1e8">RAD DAD</text>'
        '<text x="20.2" y="16.8" text-anchor="middle" font-family="Arial" font-size="4.5" font-weight="900" fill="#a6ef12">TAP</text>'
        '<text x="20.2" y="19.5" text-anchor="middle" font-family="Arial" font-size="1.9" font-weight="bold" fill="#f5f1e8">TO PLAY</text>'
        '</g>'
    )
    (DIR_GUIDES / "Rad_Dad_25MM_TAP_TO_PLAY_LABEL.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="30mm" height="30mm" viewBox="0 0 30 30">'
        + label_art
        + '</svg>',
        encoding="ascii",
    )
    uses = []
    for row in range(5):
        for column in range(4):
            x = 30 + column * 52
            y = 37 + row * 50
            uses.append(f'<use href="#taplabel" transform="translate({x - 15} {y - 15})"/>')
    (DIR_GUIDES / "Rad_Dad_25MM_TAP_LABEL_20UP_US_LETTER.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="216mm" height="279mm" viewBox="0 0 216 279">'
        '<rect width="216" height="279" fill="white"/>'
        '<defs>' + label_art + '</defs>'
        + ''.join(uses)
        + '<text x="108" y="269" text-anchor="middle" font-family="Arial" font-size="3.2" font-weight="bold" fill="#18212a">PRINT AT 100% - EACH BLACK CIRCLE IS 25 MM</text>'
        + '</svg>',
        encoding="ascii",
    )
    (DIR_GUIDES / "Rad_Dad_NFC_HANDOFF_CARD.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="88.9mm" height="50.8mm" viewBox="0 0 88.9 50.8">'
        '<rect width="88.9" height="50.8" rx="3" fill="#050b12"/>'
        '<rect x="2" y="2" width="84.9" height="46.8" rx="2" fill="none" stroke="#a6ef12" stroke-width="0.8"/>'
        '<path d="M7 19 Q11 23 7 27 M10 16 Q17 23 10 30 M13 13 Q23 23 13 33" fill="none" stroke="#1cb5f4" stroke-width="1.5" stroke-linecap="round"/>'
        '<circle cx="4.8" cy="23" r="1.5" fill="#1cb5f4"/>'
        '<text x="52" y="10" text-anchor="middle" font-family="Arial" font-size="4.2" font-weight="bold" fill="#ff3476">RAD DAD // RETRO RIOT</text>'
        '<text x="52" y="20" text-anchor="middle" font-family="Arial" font-size="5.3" font-weight="900" fill="#f5f1e8">THIS IS NOT JUST</text>'
        '<text x="52" y="26" text-anchor="middle" font-family="Arial" font-size="5.3" font-weight="900" fill="#f5f1e8">A KEYCHAIN.</text>'
        '<text x="52" y="35" text-anchor="middle" font-family="Arial" font-size="6.2" font-weight="900" fill="#a6ef12">TAP THE BACK.</text>'
        '<text x="56" y="42" text-anchor="middle" font-family="Arial" font-size="2.35" font-weight="bold" fill="#1cb5f4">HOLD YOUR PHONE OVER THE ROUND TAG</text>'
        '<text x="52" y="47" text-anchor="middle" font-family="Arial" font-size="2.6" font-weight="bold" fill="#f5f1e8">RADDADBAND.COM/TAP</text>'
        '</svg>',
        encoding="ascii",
    )


def write_release_readme():
    (RELEASE / "README.md").write_text(
        "# Rad Dad Retro Riot v6\n\n"
        "**Old media. Loud band. One tap.**\n\n"
        "## Print first\n\n"
        "Use the individual `SINGLE_TEST` 3MF files before the combined plate. "
        "The media pieces print flat without supports. Trailer Swift is an upright "
        "desk collectible and needs organic supports from the build plate.\n\n"
        "## What changed\n\n"
        "- VHS v3 now has a dominant hinged tape door, framed reel bay, authentic hubs, center gauge, five screws, and compact label.\n"
        "- Floppy v18 restores rear shell hardware without reducing the 25 mm NFC contact area.\n"
        "- Trailer Swift v4 is a solid-base collectible with toy-like depth, a faux bobble spring, front nameplate, and underside NFC placement.\n"
        "- Cassette v36 remains unchanged because its current proportions and compact eyelet are already proven.\n\n"
        "## Make the tap obvious\n\n"
        "Use the supplied 25 mm TAP TO PLAY artwork as a non-metal overlay on the programmed rear NFC tag. A 20-up print sheet and handoff card are included in `guides`. Trailer Swift also says TAP THE BASE on the stage top.\n\n"
        "## Batch gate\n\n"
        "Physically test one of each model, every NFC tag, and the thickest intended split ring before producing a batch.\n",
        encoding="ascii",
    )


def build_release():
    if RELEASE.exists():
        shutil.rmtree(RELEASE)
    for directory in (DIR_3MF, DIR_STL, DIR_PREVIEWS, DIR_GUIDES, DIR_QA):
        directory.mkdir(parents=True, exist_ok=True)

    cassette = bed_normalized(build_v34(load_v33_body()))
    floppy = build_floppy_v18()
    vhs = build_vhs_v3()
    trailer = build_trailer_swift_v4()
    models = {
        "Rad_Dad_Cassette_v36": cassette,
        "Rad_Dad_Floppy_v18": floppy,
        "Rad_Dad_Mini_VHS_v3": vhs,
        "Trailer_Swift_v4_Bobblehead_NFC": trailer,
    }

    master_preview = DIR_PREVIEWS / "Rad_Dad_Retro_Riot_v6_COLLECTION_PREVIEW.png"
    collection_preview(
        master_preview,
        (
            ("CASSETTE v36", cassette, "top"),
            ("FLOPPY v18 FRONT", floppy, "top"),
            ("MINI VHS v3", vhs, "top"),
            ("TRAILER SWIFT v4", trailer, "front"),
        ),
        "RAD DAD // RETRO RIOT v6",
        "AUTHENTIC MEDIA | PUNK COLLECTIBLE | NFC READY",
    )
    collection_preview(
        DIR_PREVIEWS / "Rad_Dad_Floppy_v18_FRONT_REAR_PREVIEW.png",
        (
            ("FLOPPY FRONT", floppy, "top"),
            ("DEVELOPED REAR", rear_preview(floppy), "top"),
            ("MINI VHS v3", vhs, "top"),
            ("TRAILER SWIFT v4", trailer, "front"),
        ),
        "RETRO RIOT v6 DETAIL REVIEW",
        "REAR HARDWARE RESTORED | NFC CONTACT ZONES PRESERVED",
    )
    collection_preview(
        DIR_PREVIEWS / "Trailer_Swift_v4_BOBBLEHEAD_DETAIL_PREVIEW.png",
        (
            ("FRONT CHARACTER", trailer, "front"),
            ("TOY DEPTH", trailer, "side"),
            ("SOLID STAGE BASE", trailer, "top"),
            ("25 MM NFC UNDERSIDE", rear_preview(trailer), "top"),
        ),
        "TRAILER SWIFT v4 // PUNK DESK TOY",
        "OVERSIZED COMIC HEAD | SOLID CIRCULAR BASE | NFC UNDERSIDE",
    )

    for index, (name, mesh) in enumerate(models.items(), start=1):
        mesh.export(DIR_STL / f"{name}.stl")
        write_3mf(
            DIR_3MF / f"{name}_SINGLE_TEST_A1_MINI.3mf",
            [(index, name.replace("_", " "), mesh, [(90.0, 90.0)])],
            master_preview,
            f"{name} Single Test",
        )

    positions = {
        "Rad_Dad_Cassette_v36": (128.0, 72.0),
        "Rad_Dad_Floppy_v18": (43.0, 125.0),
        "Rad_Dad_Mini_VHS_v3": (126.0, 128.0),
        "Trailer_Swift_v4_Bobblehead_NFC": (42.0, 43.0),
    }
    objects = [
        (index, name.replace("_", " "), mesh, [positions[name]])
        for index, (name, mesh) in enumerate(models.items(), start=1)
    ]
    write_3mf(
        DIR_3MF / "Rad_Dad_Retro_Riot_v6_ALL_FOUR_A1_MINI.3mf",
        objects,
        master_preview,
        "Rad Dad Retro Riot v6 All Four",
    )

    placed = [placed_copy(mesh, *positions[name]) for name, mesh in models.items()]
    minimum = np.vstack([item.bounds[0] for item in placed]).min(axis=0)
    maximum = np.vstack([item.bounds[1] for item in placed]).max(axis=0)
    qa = ["RAD DAD RETRO RIOT v6 - DIGITAL QA", ""]
    for name, mesh in models.items():
        qa.extend(mesh_report(name.replace("_", " "), mesh))
    qa.extend(
        (
            "Release checks:",
            "  Physical objects on combined plate: 4",
            "  Media keyring openings: 6.00 mm nominal",
            "  Trailer Swift format: upright solid-base desk collectible",
            "  NFC diameter: 25.00 mm nominal on all four designs",
            "  Floppy rear NFC protected radius: 12.85 mm",
            "  Trailer Swift base: 53.00 mm maximum diameter",
            f"  Combined plate footprint: {maximum[0] - minimum[0]:.3f} x {maximum[1] - minimum[1]:.3f} mm",
            f"  Combined plate bounds: X {minimum[0]:.3f} to {maximum[0]:.3f}; Y {minimum[1]:.3f} to {maximum[1]:.3f}",
            f"  Fits A1 Mini XY: {bool(np.all(minimum[:2] >= 0.0) and np.all(maximum[:2] <= 180.0))}",
            "  Physical print validation: REQUIRED BEFORE BATCH PRODUCTION",
        )
    )
    (DIR_QA / "MODEL_QA_REPORT.txt").write_text("\n".join(qa) + "\n", encoding="ascii")
    (DIR_QA / "PHYSICAL_QC_CHECKLIST.md").write_text(
        "# Retro Riot v6 physical quality-control checklist\n\n"
        "Record filament, printer, nozzle, plate, date, and operator for every test batch.\n\n"
        "## Identity and finish\n\n"
        "- [ ] Cassette reads immediately as a compact cassette at arm's length.\n"
        "- [ ] Floppy front and rear read immediately as a 3.5-inch disk.\n"
        "- [ ] VHS reads immediately as VHS, not as a cassette.\n"
        "- [ ] Trailer Swift stands squarely and the front nameplate is readable.\n"
        "- [ ] RAD DAD and 3.69 MB are complete and legible.\n"
        "- [ ] No strings, gaps, elephant foot, loose details, or sharp cleanup scars.\n\n"
        "## Function\n\n"
        "- [ ] Every media eyelet accepts the thickest production split ring.\n"
        "- [ ] Every eyelet survives ten firm pull-and-twist cycles.\n"
        "- [ ] Every programmed NFC tag scans before installation.\n"
        "- [ ] Every installed tag scans three times on iPhone and three times on Android.\n"
        "- [ ] TAP TO PLAY label remains fully adhered around its circumference.\n"
        "- [ ] Trailer Swift base does not rock after the NFC tag is installed.\n\n"
        "## Durability\n\n"
        "- [ ] Each design survives a one-meter drop onto a hard floor three times.\n"
        "- [ ] Media samples complete three days of pocket/key carry without eyelet damage.\n"
        "- [ ] Trailer Swift hair, guitar, feet, and base remain intact after handling.\n\n"
        "## Release decision\n\n"
        "- [ ] PASS: approved for batch production.\n"
        "- [ ] HOLD: defect documented and corrected before reprint.\n",
        encoding="ascii",
    )
    write_guides()
    write_release_readme()

    zip_path = RELEASE / "Rad_Dad_Retro_Riot_v6_Print_Pack.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(RELEASE.rglob("*")):
            if path.is_file() and path != zip_path and path.name != "MANIFEST.json":
                archive.write(path, path.relative_to(RELEASE.parent))

    files = []
    for path in sorted(RELEASE.rglob("*")):
        if path.is_file() and path.name != "MANIFEST.json":
            files.append(
                {
                    "path": str(path.relative_to(REPO)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    manifest = {
        "release": "Retro Riot v6",
        "generated": "2026-08-09",
        "visibility": "private-development-only",
        "files": files,
    }
    (RELEASE / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="ascii"
    )
    print(RELEASE)
    print(master_preview)
    print(DIR_3MF / "Rad_Dad_Retro_Riot_v6_ALL_FOUR_A1_MINI.3mf")


if __name__ == "__main__":
    build_release()
