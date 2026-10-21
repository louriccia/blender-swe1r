"""Building blocks for the generated gym, zoo and museum tracks.

Everything here runs inside Blender with the add-on registered (see build.py). Positions and sizes
are in game units: the add-on exports Blender units x100 (swr_export.scale), so a 400-unit road is
4 Blender units wide. Expected values in the level descriptions cite the SW_RACER_RE decomp.
"""
import json
import math
import os
import shutil

import bpy
import bmesh
from mathutils import Vector

GAME = 0.01                     # Blender units per game unit
BLOCK_FILES = ("out_modelblock.bin", "out_splineblock.bin", "out_textureblock.bin")


def g(*values):
    """Game units -> Blender units."""
    if len(values) == 1:
        return values[0] * GAME
    return Vector(values) * GAME


# MARK: scene

def new_track_scene(addon, model_id=1):
    """An empty scene holding a Trak model collection with Track and Skybox children, as
    view3d.new_model makes, plus the 24 game view layers (import makes those; new_model does not,
    and without them every mesh exports on no layer)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 60
    model = bpy.data.collections.new("Level")
    model.collection_type = "MODEL"
    model.export_type = "7"
    model.export_model = str(model_id)
    scene.collection.children.link(model)
    track = bpy.data.collections.new("Track")
    track.collection_type = "0"
    sky = bpy.data.collections.new("Skybox")
    sky.collection_type = "1"
    model.children.link(track)
    model.children.link(sky)
    modelblock = addon_module(addon, "swe1r.modelblock")
    modelblock.ensure_24_view_layers()
    return model, track, sky


def addon_module(addon, name):
    import importlib
    return importlib.import_module(f"{addon.__name__}.{name}")


# MARK: textures and materials

def checker_image(name, size=64, a=(0.85, 0.85, 0.85, 1), b=(0.35, 0.35, 0.35, 1), cells=8):
    image = bpy.data.images.new(name, size, size, alpha=True)
    cell = size // cells
    pixels = []
    for y in range(size):
        for x in range(size):
            pixels.extend(a if ((x // cell) + (y // cell)) % 2 == 0 else b)
    image.pixels = pixels
    image.pack()
    return image


def flat_image(name, color, size=16):
    image = bpy.data.images.new(name, size, size, alpha=True)
    image.pixels = list(color) * (size * size)
    image.pack()
    return image


def material(addon, name, image):
    modelblock = addon_module(addon, "swe1r.modelblock")
    mat = modelblock.Material(None, None).make(tex_name=image.name, mat_name=name)
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE':
            node.image = image
    return mat


# MARK: meshes

def mesh_object(name, verts, faces, uvs=None, collection=None, mat=None,
                visible=True, collidable=True):
    """A mesh from game-unit vertices. uvs: one (u, v) per face corner, in face order."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([g(*v) for v in verts], [], faces)
    if uvs is not None:
        layer = mesh.uv_layers.new(name="UVMap")
        for i, uv in enumerate(uvs):
            layer.data[i].uv = uv
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    (collection or bpy.context.scene.collection).objects.link(obj)
    if mat is not None:
        mesh.materials.append(mat)
    obj.visible = visible
    obj.collidable = collidable
    return obj


def set_surface(obj, *flags, **behavior):
    """Give a collision mesh a CollisionTags struct with the named surface flags (props.py
    SurfaceEnum names) and any other behavior properties (fog_*, lighting_*, magnet, ...)."""
    obj.collision_data = True
    for flag in flags:
        setattr(obj, flag, True)
    for key, value in behavior.items():
        setattr(obj, key, value)
    return obj


def ribbon(name, centerline, width, collection, mat, tile=None, closed=False, bank=None,
           segments_per_mesh=None, **kwargs):
    """A road surface along centerline (list of game-unit (x, y, z)). The road's left/right edges
    are offset horizontally; bank(i) gives a roll in degrees per point. UVs repeat every `tile`
    game units along the road (default: one road width), 0..1 across it."""
    tile = tile or width
    points = [Vector(p) for p in centerline]
    n = len(points)
    left, right = [], []
    for i, p in enumerate(points):
        prev_p = points[i - 1] if (i > 0 or closed) else p
        next_p = points[(i + 1) % n] if (i < n - 1 or closed) else p
        forward = (next_p - prev_p)
        forward.z = 0
        forward.normalize()
        side = Vector((-forward.y, forward.x, 0))
        roll = math.radians(bank(i)) if bank else 0.0
        offset = side * (width / 2) * math.cos(roll)
        lift = (width / 2) * math.sin(roll)
        left.append(p + offset + Vector((0, 0, lift)))
        right.append(p - offset - Vector((0, 0, lift)))
    distance = [0.0]
    for i in range(1, n + (1 if closed else 0)):
        distance.append(distance[-1] + (points[i % n] - points[i - 1]).length)
    verts, faces, uvs = [], [], []
    count = n if closed else n - 1
    for i in range(count):
        j = (i + 1) % n
        base = len(verts)
        verts.extend([tuple(left[i]), tuple(right[i]), tuple(right[j]), tuple(left[j])])
        faces.append((base, base + 1, base + 2, base + 3))
        v0, v1 = distance[i] / tile, distance[i + 1] / tile
        # keep UVs small: the add-on shifts islands into [-8, 8], one quad is one island
        shift = math.floor(v0)
        uvs.extend([(0, v0 - shift), (1, v0 - shift), (1, v1 - shift), (0, v1 - shift)])
    return mesh_object(name, verts, faces, uvs, collection, mat, **kwargs)


def box(name, center, size, collection, mat, **kwargs):
    """An axis-aligned box (game units), all six faces, UVs one tile per face."""
    cx, cy, cz = center
    sx, sy, sz = (s / 2 for s in size)
    corners = [(cx + dx * sx, cy + dy * sy, cz + dz * sz)
               for dz in (-1, 1) for dy in (-1, 1) for dx in (-1, 1)]
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    uvs = [(0, 0), (1, 0), (1, 1), (0, 1)] * 6
    return mesh_object(name, corners, faces, uvs, collection, mat, **kwargs)


def quad(name, corners, collection, mat, uv=((0, 0), (1, 0), (1, 1), (0, 1)), **kwargs):
    return mesh_object(name, corners, [(0, 1, 2, 3)], list(uv), collection, mat, **kwargs)


# MARK: spline

def spline(name, points, model_collection, cyclic=True, lift=10.0):
    """The track spline through game-unit points, point 0 first (the start/finish line and the
    grid, swrObjJdge GetSpawnTransform). lift raises it above the road: the game bakes the track
    mesh under it by raycasting down then up 5000 units (swrSpline BakeSampleTrackMesh 0x47ea20)."""
    curve = bpy.data.curves.new(name, type='CURVE')
    curve.dimensions = '3D'
    s = curve.splines.new('BEZIER')
    s.bezier_points.add(len(points) - 1)
    for bp, p in zip(s.bezier_points, points):
        bp.co = g(p[0], p[1], p[2] + lift)
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    s.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, curve)
    model_collection.objects.link(obj)
    return obj


# MARK: layouts

def stadium(straight, radius, step=500.0, z=0.0, start=(0.0, 0.0)):
    """A closed stadium loop (two straights joined by half circles), counter-clockwise, starting
    at the middle of the bottom straight heading +X. Returns points every ~step game units."""
    sx, sy = start
    pts = []
    half = straight / 2
    n_straight = max(1, int(round(straight / step)))
    n_arc = max(4, int(round(math.pi * radius / step)))
    # bottom straight, from the middle to the right end
    for i in range(n_straight // 2):
        pts.append((sx + i * straight / n_straight, sy, z))
    # right half circle
    for i in range(n_arc):
        a = -math.pi / 2 + math.pi * i / n_arc
        pts.append((sx + half + radius * math.cos(a), sy + radius + radius * math.sin(a), z))
    # top straight, right to left
    for i in range(n_straight):
        pts.append((sx + half - i * straight / n_straight, sy + 2 * radius, z))
    # left half circle
    for i in range(n_arc):
        a = math.pi / 2 + math.pi * i / n_arc
        pts.append((sx - half + radius * math.cos(a), sy + radius + radius * math.sin(a), z))
    # bottom straight, left end back to the middle
    for i in range(n_straight - n_straight // 2):
        pts.append((sx - half + i * straight / n_straight, sy, z))
    return pts


# MARK: export

def stock_blocks():
    """The game's data/lev01, preferring the add-on's pristine .bak backups."""
    path = os.environ.get("SWE1R_GAME_DATA", r"C:\Program Files (x86)\Steam\steamapps\common\Star Wars Episode I Racer\data\lev01")
    return {f: (os.path.join(path, f + ".bak") if os.path.exists(os.path.join(path, f + ".bak"))
                else os.path.join(path, f)) for f in BLOCK_FILES}


def export_level(addon, model_collection, out_dir, expectations=None):
    """Copy stock blocks to out_dir and export the level into them, as a custom_tracks folder the
    SW_RACER_RE hook loads (dinput_hook/custom_tracks.cpp). Writes expectations.json beside them."""
    os.makedirs(out_dir, exist_ok=True)
    for name, src in stock_blocks().items():
        shutil.copy(src, os.path.join(out_dir, name))
    exporter = addon_module(addon, "swr_export")
    bpy.context.scene.is_export_separate = False
    bpy.context.scene.is_export_debug = False
    exporter.export_model(model_collection, out_dir + os.sep, [True, True, True], lambda *a, **k: None)
    for name in BLOCK_FILES:
        # the exporter keeps a backup of the file it overwrote; the hook only reads out_*.bin
        for leftover in (name + ".bak",):
            p = os.path.join(out_dir, leftover)
            if os.path.exists(p):
                os.remove(p)
    if expectations is not None:
        with open(os.path.join(out_dir, "expectations.json"), "w") as f:
            json.dump(expectations, f, indent=2)
