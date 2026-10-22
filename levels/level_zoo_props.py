"""Zoo, props: the game's own models (Part, Scen, Modl) on labelled pedestals.

    levels/build.py --level zoo_props_<part>      (part 1..PARTS)

Each model is imported with the add-on and its meshes copied into the zoo track as they look at
frame 0 (the evaluated mesh: hooks and the node transforms baked in), scaled to fit a pedestal.
Their materials and stock textures come along unchanged, so export references the stock
textures. This re-exports stock geometry from inside a track, which no stock round-trip does.

verify() re-imports the export and counts each prop's visual triangles: they must all be there.
"""
import math
import os
import shutil
import tempfile

import bpy
from mathutils import Matrix, Vector

import course as C
import lib
import signs

PARTS = 4
BOX = 500.0         # a prop is scaled to fit a cube this size
PITCH = 900.0
WALL = 900.0        # pedestal centre from the road's centre line
TYPES = ("Part", "Scen", "Modl")


def models():
    ns = {}
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "swe1r",
                           "model_list.py")) as f:
        exec(f.read(), ns)
    return [m for m in ns["model_list"] if m["extension"] in TYPES]


def copy_model(addon, folder, model_id, collection, name):
    """Import model_id, copy its meshes (evaluated, world space) into collection; drop the import.
    Returns the copies, or [] if the import failed."""
    imp = lib.addon_module(addon, "swr_import")
    before_cols = set(bpy.data.collections)
    before_objs = set(bpy.data.objects)
    try:
        imp.import_model(folder, [model_id], lambda *a, **k: None)
    except Exception as e:
        print(f"[zoo_props] model {model_id} import failed: {e}")
        return []
    bpy.context.scene.frame_set(0)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    copies = []
    # bpy.data.objects order (by name), not set order: the copies' names set the export order
    for obj in [o for o in bpy.data.objects if o not in before_objs]:
        if obj.type != 'MESH' or not obj.visible or not len(obj.data.polygons):
            continue
        mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), depsgraph=depsgraph)
        copy = bpy.data.objects.new(f"{name}_{len(copies):03d}", mesh)
        copy.matrix_world = obj.matrix_world.copy()
        collection.objects.link(copy)
        copy.visible = True
        copy.collidable = False
        copies.append(copy)
    for obj in [o for o in bpy.data.objects if o not in before_objs and o not in copies]:
        bpy.data.objects.remove(obj)
    for col in [c for c in bpy.data.collections if c not in before_cols]:
        bpy.data.collections.remove(col)
    return copies


def place(copies, center):
    """Scale and move the copies (game-unit model coordinates) to sit in a BOX cube on center."""
    pts = [c.matrix_world @ v.co for c in copies for v in c.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    size = max((hi - lo).x, (hi - lo).y, (hi - lo).z, 1e-6)
    k = lib.g(BOX) / size
    pivot = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    m = Matrix.Translation(lib.g(*center)) @ Matrix.Scale(k, 4) @ Matrix.Translation(-pivot)
    for c in copies:
        # into the mesh: the add-on applies an object's scale itself, but keep these plain
        c.data.transform(m @ c.matrix_world)
        c.matrix_world = Matrix.Identity(4)
    return k / lib.GAME


def build(addon, part=1):
    model, track, sky = lib.new_track_scene(addon)
    road_mat = lib.material(addon, f"zp{part}_road", lib.checker_image(f"zp{part}_checker"))
    white_mat = lib.material(addon, f"zp{part}_white", lib.flat_image(f"zp{part}_white", (1, 1, 1, 1)))
    sign_mat = lib.material(addon, f"zp{part}_signs", signs.atlas_image(f"zp{part}_atlas"))
    everything = models()
    per = math.ceil(len(everything) / PARTS)
    wanted = everything[(part - 1) * per: part * per]

    columns = math.ceil(len(wanted) / 4)            # both sides of both straights
    length = columns * PITCH + PITCH
    course = C.exhibit_loop([("hall_a", length), ("hall_b", length)], gap=600.0)
    for objs in course.road(track, road_mat).values():
        for obj in objs:
            lib.shade(obj)
    slots = []
    for hall in ("hall_a", "hall_b"):
        s0, _ = course.station_range(hall)
        for c in range(columns):
            smp = course.frame(s0 + PITCH / 2 + c * PITCH)
            h = smp['heading']
            left = Vector((-math.sin(h), math.cos(h), 0))
            for side in (1, -1):
                slots.append((smp['pos'] + left * side * WALL, left * side))

    tmp = tempfile.mkdtemp()
    for name, src in lib.stock_blocks().items():
        shutil.copy(src, os.path.join(tmp, name))
    props, labels = {}, []
    for m, (center, out) in zip(wanted, slots):
        copies = copy_model(addon, tmp + os.sep, m["index"], track, f"prop{m['index']:03d}")
        if not copies:
            continue
        scale = place(copies, tuple(center + Vector((0, 0, 60))))
        # the pedestal's top (z 50) stays under verify()'s counting window (z >= 55)
        pedestal = lib.box(f"pedestal_{m['index']:03d}", tuple(center + Vector((0, 0, 25))), (BOX + 60, BOX + 60, 50),
                           track, white_mat, collidable=False)
        lib.shade(pedestal, tint=(0.5, 0.5, 0.6))
        tris = sum(len(p.vertices) - 2 for c in copies for p in c.data.polygons)
        # vertices are written as whole game units: a triangle that the scaling made smaller than
        # that collapses to nothing
        collapsed = 0
        for c in copies:
            co = [tuple(round(x / lib.GAME) for x in v.co) for v in c.data.vertices]
            for poly in c.data.polygons:
                vs = [Vector(co[i]) for i in poly.vertices]
                for i in range(1, len(vs) - 1):
                    if (vs[i] - vs[0]).cross(vs[i + 1] - vs[0]).length == 0:
                        collapsed += 1
        props[str(m["index"])] = {"name": m["name"], "center": [round(v, 1) for v in center], "tris": tris,
                                  "collapsed": collapsed,
                                  "scale": round(scale, 3)}
        label = f"{m['index']} {m['name'][:14]}"
        labels.append((label, tuple(center - out * (BOX / 2 + 60) + Vector((0, 0, 10))), (-out.x, -out.y)))
    shutil.rmtree(tmp, ignore_errors=True)
    signs.labels(f"zp{part}_labels", labels, track, sign_mat, char=40.0)
    signs.station_sign(course, "hall_a", [f"PROPS PART {part}/{PARTS}", f"MODELS {wanted[0]['index']}-{wanted[-1]['index']}"],
                       track, sign_mat)
    lib.spline("spline", course.spline_points(), model)
    return model, {"level": f"zoo_props_{part}", "length": round(course.length, 1), "centerline": course.describe(),
                   "stations": [{"name": n, "s": list(course.station_range(n)), "measure": [], "predict": {},
                                 "source": "visual"} for n in ("hall_a", "hall_b")],
                   "props": props, "lap": {"finishes": True}}


def verify(addon, out_dir, expectations):
    """Re-import the export: every prop's visual triangles are there (counted in its pedestal box)."""
    imp = lib.addon_module(addon, "swr_import")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imp.import_model(out_dir + os.sep, [1], lambda *a, **k: None)
    tris_at = []
    for obj in bpy.data.objects:
        if obj.type != 'MESH' or not obj.visible:
            continue
        mw = obj.matrix_world
        for poly in obj.data.polygons:
            c = mw @ poly.center    # game units
            tris_at.append((c, len(poly.vertices) - 2))
    problems = []
    for index, prop in expectations["props"].items():
        center = Vector(prop["center"])
        have = sum(n for c, n in tris_at
                   if abs(c.x - center.x) <= BOX / 2 + 5 and abs(c.y - center.y) <= BOX / 2 + 5
                   and 55 <= c.z <= 60 + BOX + 5)
        if not prop["tris"] - prop["collapsed"] <= have <= prop["tris"]:
            problems.append(f"prop {index} {prop['name']}: {prop['tris']} triangles placed "
                            f"({prop['collapsed']} collapse at whole units), {have} after export")
    return problems
