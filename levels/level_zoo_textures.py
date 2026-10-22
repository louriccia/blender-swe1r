"""Zoo, textures: every stock texture the game's models use, on labelled tiles.

    levels/build.py --level zoo_textures_<part>      (part 1..PARTS)

The 1573 textures (levels/data/stock_textures.json, from scan_textures.py) don't fit one track:
vertices are int16, so a loop of tiles has to stay within +-32767. Each part shows a slice of
them, in id order, on walls either side of both straights, three rows high, the id under each tile.

The tiles reference the stock textures: the images come from importing a model that uses each one,
so they carry the importer's id, format, hashes and mip-chain notes, and export writes the stock
texture index rather than re-encoding the pixels (MaterialTexture.unmake: an unchanged image with
an id below 1648). That also keeps the new-texture budget for the levels' own textures.
Each tile has a plain material (default combiner), translucent when the texture has alpha.
"""
import json
import math
import os

import bpy
from mathutils import Vector

import course as C
import lib
import signs

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = 4
TILE = 240.0
PITCH = 300.0
ROWS = 3
ROAD = 600.0
WALL = ROAD / 2 + 200.0     # tile faces this far from the centre line


def stock_textures():
    with open(os.path.join(HERE, "data", "stock_textures.json")) as f:
        return {int(k): v for k, v in json.load(f).items()}


def gather_images(addon, wanted):
    """Import the models that use the wanted texture ids and keep one image per id."""
    imp = lib.addon_module(addon, "swr_import")
    table = stock_textures()
    by_model = {}
    for tid in wanted:
        by_model.setdefault(table[tid]["models"][0], []).append(tid)
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp()
    for name, src in lib.stock_blocks().items():
        shutil.copy(src, os.path.join(tmp, name))
    kept = {}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for model_id, ids in sorted(by_model.items()):
        imp.import_model(tmp + os.sep, [model_id], lambda *a, **k: None)
        for image in bpy.data.images:
            tid = int(image["id"]) if "id" in image else None
            if tid in ids and tid not in kept:
                image.use_fake_user = True
                image.name = f"tex_{tid:04d}"
                kept[tid] = image
        # drop the imported model; the kept images stay (fake user)
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj)
        for col in list(bpy.data.collections):
            bpy.data.collections.remove(col)
        bpy.data.orphans_purge(do_recursive=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return kept


def has_alpha(image):
    px = list(image.pixels)
    return any(a < 0.99 for a in px[3::4])


def build(addon, part=1):
    table = stock_textures()
    ids = sorted(table)
    per = math.ceil(len(ids) / PARTS)
    wanted = ids[(part - 1) * per: part * per]
    images = gather_images(addon, wanted)
    missing = [t for t in wanted if t not in images]

    model, track, sky = lib.new_track_scene(addon, reset=False)
    road_mat = lib.material(addon, f"zoo{part}_road", lib.checker_image(f"zoo{part}_checker"))
    sign_mat = lib.material(addon, f"zoo{part}_signs", signs.atlas_image(f"zoo{part}_atlas"))

    per_column = 4 * ROWS               # a column position on each straight, both walls, ROWS high
    columns = math.ceil(len(wanted) / per_column)
    length = columns * PITCH + PITCH
    course = C.exhibit_loop([("hall_a", length), ("hall_b", length)], gap=600.0)
    for objs in course.road(track, road_mat).values():
        for obj in objs:
            lib.shade(obj)

    labels, tiles = [], {}
    slots = []
    for hall in ("hall_a", "hall_b"):
        s0, s1 = course.station_range(hall)
        for c in range(columns):
            smp = course.frame(s0 + PITCH / 2 + c * PITCH)
            h = smp['heading']
            fwd = Vector((math.cos(h), math.sin(h), 0))
            left = Vector((-fwd.y, fwd.x, 0))
            for side in (1, -1):
                for row in range(ROWS):
                    slots.append((smp['pos'] + left * side * WALL, fwd, left * side, row))
    for tid, (base, fwd, out, row) in zip(wanted, slots):
        image = images.get(tid)
        bottom = 120 + row * PITCH
        # the tile faces the road (-out); right as a reader on the road sees it (as signs.sign)
        right = Vector((out.y, -out.x, 0))
        c0 = base - right * TILE / 2 + Vector((0, 0, bottom))
        corners = [c0, c0 + right * TILE, c0 + right * TILE + Vector((0, 0, TILE)), c0 + Vector((0, 0, TILE))]
        if image is None:
            continue
        mat = lib.material(addon, f"zoo_{tid:04d}", image)
        mat.use_backface_culling = False
        if has_alpha(image):
            mat.transparent = True
        tile = lib.quad(f"tile_{tid:04d}", [tuple(c) for c in corners], track, mat, collidable=False)
        tiles[tid] = [round(v, 1) for v in (base + Vector((0, 0, bottom + TILE / 2)))]
        labels.append((str(tid), tuple(base + Vector((0, 0, bottom - 70))), (-out.x, -out.y)))
    signs.labels(f"zoo{part}_labels", labels, track, sign_mat, char=45.0)
    signs.station_sign(course, "hall_a", [f"TEXTURES {wanted[0]}-{wanted[-1]}", f"PART {part}/{PARTS}"],
                       track, sign_mat)
    lib.spline("spline", course.spline_points(), model)
    return model, {"level": f"zoo_textures_{part}", "length": round(course.length, 1),
                   "centerline": course.describe(),
                   "stations": [{"name": n, "s": list(course.station_range(n)), "measure": [], "predict": {},
                                 "source": "visual"} for n in ("hall_a", "hall_b")],
                   "tiles": tiles, "missing": missing, "lap": {"finishes": True}}
