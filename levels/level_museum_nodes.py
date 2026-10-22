"""Museum, nodes wing: the Node panel's node types, beside the road.

Each exhibit is an empty set to a node type with coloured boxes under it (swe1r/modelblock.py
Group20581 / Group20582 / Group53350; SW_RACER_RE src/types.h swrModel_NodeSelector,
swrModel_NodeLODSelector, swrModel_NodeTransformed...). Children export in name order.
- sel_1: a Selector drawing child 1 of a red (0) / blue (1) pair: only blue shows.
- sel_all: a Selector drawing -1, all: both show.
- sel_none: a Selector drawing -2, none: nothing shows.
- lod: an LOD Selector, green first child, yellow second. The replacement renderer always draws
  the first child (green); the original renderer switches by distance.
- facing: a Camera-facing node holding a white quad (Face Camera): it turns toward the camera.
The look in game is in the screenshots; verify() re-imports the export and reads the settings back.
"""
import math
import os

import bpy
from mathutils import Vector

import course as C
import lib
import signs

LENGTH = 1500.0
COLORS = {"red": (1, 0, 0, 1), "blue": (0, 0, 1, 1), "green": (0, 1, 0, 1), "yellow": (1, 1, 0, 1),
          "white": (1, 1, 1, 1)}
SELECTORS = [("sel_1", 1, ["SELECTOR", "CHILD 1: BLUE"]), ("sel_all", -1, ["SELECTOR", "-1: ALL"]),
             ("sel_none", -2, ["SELECTOR", "-2: NONE"])]


def build(addon):
    model, track, sky = lib.new_track_scene(addon)
    road_mat = lib.material(addon, "nodes_road", lib.checker_image("nodes_checker"))
    sign_mat = lib.material(addon, "nodes_signs", signs.atlas_image())
    mats = {n: lib.material(addon, f"node_{n}", lib.flat_image(f"node_{n}", c)) for n, c in COLORS.items()}
    names = [n for n, _, _ in SELECTORS] + ["lod", "facing"]
    course = C.exhibit_line([(n, LENGTH) for n in names], gap=300.0)
    for objs in course.road(track, road_mat).values():
        for obj in objs:
            lib.shade(obj)

    def beside(station, up=200):
        s0, s1 = course.station_range(station)
        mid = course.frame((s0 + s1) / 2)
        h = mid['heading']
        return mid['pos'] + Vector((-math.sin(h), math.cos(h), 0)) * 500 + Vector((0, 0, up))

    def empty(name, kind):
        e = bpy.data.objects.new(name, None)
        track.objects.link(e)
        e.location = lib.g(*beside(name))
        e.swr_node_type = kind
        return e

    def child(name, offset, color, parent):
        b = lib.box(name, offset, (150, 150, 150), track, mats[color], collidable=False)
        b.parent = parent
        return b

    for name, selected, lines in SELECTORS:
        sel = empty(name, 'SELECTOR')
        sel.swr_selected_child = selected
        child(f"{name}_0_red", (0, -120, 0), "red", sel)
        child(f"{name}_1_blue", (0, 120, 0), "blue", sel)
        signs.station_sign(course, name, lines, track, sign_mat)
    lod = empty("lod", 'LOD')
    child("lod_0_green", (0, -120, 0), "green", lod)
    child("lod_1_yellow", (0, 120, 0), "yellow", lod)
    signs.station_sign(course, "lod", ["LOD SELECTOR", "FIRST: GREEN"], track, sign_mat)
    facing = empty("facing", 'CAMERA')
    facing.swr_face_camera = True
    quad = lib.quad("facing_quad", [(-150, 0, -150), (150, 0, -150), (150, 0, 150), (-150, 0, 150)], track,
                    mats["white"], collidable=False)
    quad.parent = facing
    signs.station_sign(course, "facing", ["CAMERA-FACING", "QUAD"], track, sign_mat)

    course.spline(model)
    stations = [{"name": n, "s": [round(x, 1) for x in course.station_range(n)], "measure": [], "predict": {},
                 "source": "visual: screenshots"} for n in names]
    return model, {"level": "museum_nodes", "length": round(course.length, 1), "centerline": course.describe(),
                   "stations": stations, "lap": {"finishes": True},
                   "nodes": {"selected": sorted(s for _, s, _ in SELECTORS),
                             "lod_distances": [round(x) for x in lod.swr_lod_distances]}}


def verify(addon, out_dir, expectations):
    """Re-import the export: each node comes back as the type it was set to, with its settings and children."""
    imp = lib.addon_module(addon, "swr_import")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imp.import_model(out_dir + os.sep, [1], lambda *a, **k: None)
    empties = [o for o in bpy.data.objects if o.type == 'EMPTY']
    problems = []
    selectors = [o for o in empties if o.swr_node_type == 'SELECTOR']
    have = sorted(o.swr_selected_child for o in selectors)
    if have != expectations["nodes"]["selected"]:
        problems.append(f"selectors: expected draws {expectations['nodes']['selected']}, got {have}")
    for o in selectors:
        if len(o.children) != 2:
            problems.append(f"selector {o.name}: expected 2 children, got {len(o.children)}")
    lods = [o for o in empties if o.swr_node_type == 'LOD']
    have = [[round(x) for x in o.swr_lod_distances] for o in lods]
    if have != [expectations["nodes"]["lod_distances"]] or any(len(o.children) != 2 for o in lods):
        problems.append(f"LOD selector: expected one with {expectations['nodes']['lod_distances']} and 2 children, "
                        f"got {have}")
    facing = [o for o in empties if o.swr_node_type == 'CAMERA' and o.swr_face_camera]
    if len(facing) != 1:
        problems.append(f"camera-facing: expected one facing the camera, got {len(facing)}")
    return problems
