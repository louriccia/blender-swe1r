"""Zoo, materials: what the add-on makes of authored images and material settings.

Two walls of labelled tiles along a loop:
- Formats: images built to land on each texture format the add-on picks from the pixels
  (swe1r/textureblock.py: grey -> I4/I8, few colours -> CI4/CI8, partial alpha -> RGBA32), and
  the size rules (longest side scaled to at most 128, sides rounded up to a power of two, at least
  16). verify() re-imports the export and checks each tile's format and size.
- Settings: one orientation texture (an arrow, numbered quadrants) under every material setting:
  flip and clip (UVs run 0..2, so the repeat shows), UV scroll, transparency, backface culling
  (the tile's back faces the road), vertex colours.
The look in game is in the test runner's screenshots.
"""
import math
import os

import bpy
from mathutils import Vector

import course as C
import lib
import signs

TILE = 300.0
PITCH = 420.0
WALL = 500.0

# (name, label, image factory, expected format, expected size)
I4, I8, CI4, CI8, RGBA32 = 1024, 1025, 512, 513, 3


def pixels(w, h, fn):
    out = []
    for y in range(h):
        for x in range(w):
            out.extend(fn(x, y))
    return out


def make_image(name, w, h, fn, alpha=False):
    image = bpy.data.images.new(name, w, h, alpha=alpha)
    image.pixels = pixels(w, h, fn)
    image.pack()
    return image


def grey16(x, y):
    v = (x // 4) / 15.0
    return (v, v, v, 1.0)


def grey256(x, y):
    v = ((x + y * 64) % 256) / 255.0
    return (v, v, v, 1.0)


def four_colors(x, y):
    return [(1, 0, 0, 1), (0, 1, 0, 1), (0, 0, 1, 1), (1, 1, 0, 1)][(x // 16 + y // 16) % 4]


def colors(n):
    def fn(x, y):
        i = (x + y * 64) % n
        return (((i * 37) % 256) / 255.0, ((i * 91) % 256) / 255.0, ((i * 53) % 256) / 255.0, 1.0)
    return fn


def alpha_ramp(x, y):
    return (1.0, 0.6, 0.2, x / 63.0)


def arrow(x, y):
    """64x64: quadrants coloured and numbered by colour, an arrow pointing to +V (up)."""
    q = (x >= 32) + 2 * (y >= 32)
    base = [(0.9, 0.2, 0.2, 1), (0.2, 0.8, 0.2, 1), (0.2, 0.3, 0.9, 1), (0.9, 0.9, 0.2, 1)][q]
    in_arrow = (28 <= x < 36 and 8 <= y < 44) or (44 <= y < 58 and abs(x - 31.5) < (58 - y) * 0.9)
    return (1, 1, 1, 1) if in_arrow else base


FORMATS = [
    ("grey16", "16 GREYS", lambda: make_image("zoo_grey16", 64, 64, grey16), I4, (64, 64)),
    ("grey256", "256 GREYS", lambda: make_image("zoo_grey256", 64, 64, grey256), I8, (64, 64)),
    ("four", "4 COLOURS", lambda: make_image("zoo_four", 64, 64, four_colors), CI4, (64, 64)),
    ("c200", "200 COLOURS", lambda: make_image("zoo_c200", 64, 64, colors(200)), CI8, (64, 64)),
    ("c1000", "1000 COLOURS", lambda: make_image("zoo_c1000", 64, 64, colors(1000)), CI8, (64, 64)),
    ("alpha", "ALPHA RAMP", lambda: make_image("zoo_alpha", 64, 64, alpha_ramp, alpha=True), RGBA32, (64, 64)),
    # resized (filtered) to powers of two, not padded: the blend adds colours, so 4 colours -> CI8
    ("odd", "100X40", lambda: make_image("zoo_odd", 100, 40, four_colors), CI8, (128, 64)),
    ("big", "256X256", lambda: make_image("zoo_big", 256, 256, four_colors), CI4, (128, 128)),
]

SETTINGS = [
    ("plain", "PLAIN", {}),
    ("flip_x", "FLIP_X", {"flip_x": True}),
    ("flip_y", "FLIP_Y", {"flip_y": True}),
    ("clip_x", "CLIP_X", {"clip_x": True}),
    ("clip_y", "CLIP_Y", {"clip_y": True}),
    ("scroll_x", "SCROLL_X 2", {"scroll_x": 2.0}),
    ("scroll_y", "SCROLL_Y -2", {"scroll_y": -2.0}),
    ("transparent", "TRANSPARENT", {"transparent": True}),
    ("backface", "CULL (BACK)", {"use_backface_culling": True}),
    ("vcolor", "VERTEX COLOUR", {}),
]


def build(addon):
    model, track, sky = lib.new_track_scene(addon)
    road_mat = lib.material(addon, "zoom_road", lib.checker_image("zoom_checker"))
    sign_mat = lib.material(addon, "zoom_signs", signs.atlas_image())
    arrow_image = make_image("zoo_arrow", 64, 64, arrow)

    n = max(len(FORMATS), len(SETTINGS))
    length = n * PITCH + PITCH
    course = C.exhibit_loop([("formats", length), ("settings", length)], gap=600.0)
    for objs in course.road(track, road_mat).values():
        for obj in objs:
            lib.shade(obj)

    def slot(hall, i):
        s0, _ = course.station_range(hall)
        smp = course.frame(s0 + PITCH / 2 + i * PITCH)
        h = smp['heading']
        fwd = Vector((math.cos(h), math.sin(h), 0))
        out = Vector((-fwd.y, fwd.x, 0))         # the left wall
        return smp['pos'] + out * WALL, out

    labels, tiles = [], {}

    def tile(name, mat, base, out, uv_max=1.0, back=False, vcolor=False):
        right = Vector((out.y, -out.x, 0))
        if back:
            right = -right                         # wind it the other way: its back faces the road
        c0 = base - right * TILE / 2 + Vector((0, 0, 150))
        corners = [c0, c0 + right * TILE, c0 + right * TILE + Vector((0, 0, TILE)), c0 + Vector((0, 0, TILE))]
        uv = ((0, 0), (uv_max, 0), (uv_max, uv_max), (0, uv_max))
        cols = [(1, 0.2, 0.2), (0.2, 1, 0.2), (0.2, 0.2, 1), (1, 1, 1)] if vcolor else None
        obj = lib.mesh_object(f"tile_{name}", [tuple(c) for c in corners], [(0, 1, 2, 3)], list(uv), track, mat,
                              collidable=False, colors=cols)
        tiles[name] = [round(v, 1) for v in (base + Vector((0, 0, 150 + TILE / 2)))]
        return obj

    for i, (name, text, factory, fmt, size) in enumerate(FORMATS):
        base, out = slot("formats", i)
        mat = lib.material(addon, f"zoom_{name}", factory())
        if name == "alpha":
            mat.transparent = True
        tile(name, mat, base, out)
        labels.append((text, tuple(base + Vector((0, 0, 70))), (-out.x, -out.y)))
    for i, (name, text, settings) in enumerate(SETTINGS):
        base, out = slot("settings", i)
        mat = lib.material(addon, f"zoom_set_{name}", arrow_image)
        mat.use_backface_culling = False
        for key, value in settings.items():
            setattr(mat, key, value)
        tile(f"set_{name}", mat, base, out, uv_max=2.0, back=(name == "backface"), vcolor=(name == "vcolor"))
        labels.append((text, tuple(base + Vector((0, 0, 70))), (-out.x, -out.y)))
    signs.labels("zoom_labels", labels, track, sign_mat, char=40.0)
    signs.station_sign(course, "formats", ["TEXTURE FORMATS", "AS THE ADD-ON", "PICKS THEM"], track, sign_mat)
    signs.station_sign(course, "settings", ["MATERIAL", "SETTINGS"], track, sign_mat)
    lib.spline("spline", course.spline_points(), model)
    return model, {"level": "zoo_materials", "length": round(course.length, 1), "centerline": course.describe(),
                   "stations": [{"name": n, "s": list(course.station_range(n)), "measure": [], "predict": {},
                                 "source": "visual"} for n in ("formats", "settings")],
                   "tiles": tiles, "formats": {name: [fmt, list(size)] for name, _, _, fmt, size in FORMATS},
                   "lap": {"finishes": True}}


def verify(addon, out_dir, expectations):
    """Re-import the export; each format tile's texture must have the expected format and size."""
    imp = lib.addon_module(addon, "swr_import")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imp.import_model(out_dir + os.sep, [1], lambda *a, **k: None)
    problems = []
    for name, (fmt, size) in expectations["formats"].items():
        want = Vector(expectations["tiles"][name])
        found = None
        for obj in bpy.data.objects:
            if obj.type != 'MESH' or len(obj.data.vertices) > 8 or not obj.material_slots:
                continue
            center = sum((obj.matrix_world @ v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices)
            if (center - want).length < 30:     # import places geometry in game units
                found = obj
                break
        image = None
        if found is not None:
            for node in found.material_slots[0].material.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    image = node.image
        have = (int(image.get("format", -1)), list(image.size)) if image else None
        if have != (fmt, size):
            problems.append(f"{name}: expected format {fmt} size {size}, got {have}")
    return problems
