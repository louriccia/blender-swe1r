"""Zoo, pod pen: a pod made from the template (New > Podd), raced in place of Anakin's.

Not a track: run_level.py writes its blocks over the game's data/lev01 for the race (pods always
load from there), races the stock Boonta Training Course, and puts the stock blocks back.

The pod is a box per part, each a little ahead of and turned from its anchor (where the game puts
the part: swrRacer_PodVisualData 0x004c7088, swe1r/pod_visual.py), with a colour per face (+X red,
-X blue, +Y front green, -Y back yellow, top white, bottom black: from behind, a box drawn the right
way round shows yellow and white). Small markers sit on the binder and cable anchors, a magenta bar
trails each exhaust, a shadow sits under each part, the engine glow has a cyan material of its
own, and the cable is the stock one. Screenshots show the look; verify() re-imports the export and
checks the parts landed on their anchors.
"""
import os

import bmesh
import bpy
from mathutils import Vector

import lib

POD = '2'               # Anakin's: the test runner's profile races it
OFFSET = Vector((0, 0.3, 0))    # each box's offset from its anchor, Blender units
PARTS = {"2": ("engine_r", (0.9, 3.0, 0.9)), "3": ("engine_l", (0.9, 3.0, 0.9)), "4": ("cockpit", (1.2, 2.0, 0.8))}
FACE_COLORS = {(1, 0, 0): (1, 0, 0), (-1, 0, 0): (0, 0, 1), (0, 1, 0): (0, 1, 0),
               (0, -1, 0): (1, 1, 0), (0, 0, 1): (1, 1, 1), (0, 0, -1): (0, 0, 0)}


def add_mesh(addon, name, collection, location, scale, color=None, blend='OPAQUE', image=None, plane=False):
    modelblock = lib.addon_module(addon, "swe1r.modelblock")
    if plane:
        bpy.ops.mesh.primitive_plane_add(size=1)
    else:
        bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.active_object
    for c in obj.users_collection:
        c.objects.unlink(obj)
    collection.objects.link(obj)
    obj.name = name
    obj.location = location
    obj.scale = scale
    obj.visible = True
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.view3d.remake_materials()
    mat = obj.material_slots[0].material
    if color is not None:
        mat.material_color = color
    mat.blend_mode = blend
    obj.material_slots[0].material = modelblock.Material(None, None).remake(mat, tex_name=image.name if image else None)
    return obj


def face_colors(obj):
    """A colour per face; a vertex per face corner, so the colours don't blend."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.split_edges(bm, edges=bm.edges[:])
    bm.to_mesh(obj.data)
    bm.free()
    layer = obj.data.vertex_colors.active or obj.data.vertex_colors.new(name='colors')
    for poly in obj.data.polygons:
        n = tuple(int(round(c)) for c in poly.normal)
        for li in poly.loop_indices:
            layer.data[li].color = (*FACE_COLORS[n], 1.0)


def build(addon):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.new_type = '4'
    bpy.ops.view3d.new_model()
    model = next(c for c in bpy.data.collections if c.collection_type == "MODEL")
    model.export_model = POD
    anchors = {o['pod_anchor']: o for o in model.objects if o.get('pod_anchor')}
    collections = {c.collection_type: c for c in model.children}

    for col_type, (key, size) in PARTS.items():
        box = add_mesh(addon, f"box_{key}", collections[col_type], anchors[key].location + OFFSET, size)
        box.rotation_euler = (0, 0, 0.1)
        face_colors(box)
        box.material_slots[0].material.use_backface_culling = True
    # markers on the binder and cable anchors, in the part the game moves them with
    for key, col_type, color in (('binder_r', '2', (1, 0, 1, 1)), ('binder_l', '3', (1, 0, 1, 1)),
                                 ('cable_engine_r', '2', (0, 1, 1, 1)), ('cable_engine_l', '3', (0, 1, 1, 1)),
                                 ('cable_cockpit_r', '4', (0, 1, 1, 1)), ('cable_cockpit_l', '4', (0, 1, 1, 1))):
        add_mesh(addon, f"marker_{key}", collections[col_type], anchors[key].location.copy(), (0.12, 0.12, 0.12),
                 color=color, blend='FLAT')
    for key in ('exhaust_r', 'exhaust_l'):
        add_mesh(addon, f"trail_{key}", collections['6'], anchors[key].location + Vector((0, -1.0, 0)),
                 (0.15, 2.0, 0.15), color=(1, 0, 1, 1), blend='FLAT')
    # Shadow draws where the texture is transparent: a clear texture is a solid shadow
    clear = bpy.data.images.new("pod_shadow_clear", 8, 8, alpha=True)
    clear.pixels = [0.0] * (8 * 8 * 4)
    clear.pack()
    for key, size in (('engine_r', (1.2, 3.2, 1)), ('engine_l', (1.2, 3.2, 1)), ('cockpit', (1.4, 2.2, 1))):
        a = anchors[key].location
        add_mesh(addon, f"shadow_{key}", collections['7'], Vector((a.x, a.y, -1.0)), size, color=(0, 0, 0, 0.7),
                 blend='SHADOW', image=clear, plane=True)
    # the glow's material comes from a mesh in Engine Glow (its shape is the stock quad's)
    add_mesh(addon, "glow_material", collections['8'], Vector((0, 0, 0)), (0.1, 0.1, 0.1), color=(0, 1, 1, 0.6),
             blend='GLOW', plane=True)

    return model, {"level": "zoo_pod", "pod": int(POD), "stations": [], "lap": {"finishes": False},
                   "offset": [round(c * 100, 1) for c in OFFSET]}


def verify(addon, out_dir, expectations):
    """Re-import the pod: a part's mesh is in its anchor's node space, so each box's centre there
    is its offset from the anchor."""
    imp = lib.addon_module(addon, "swr_import")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imp.import_model(out_dir + os.sep, [expectations["pod"]], lambda *a, **k: None)
    want = Vector(expectations["offset"])
    centres = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.visible and len(obj.data.vertices) == 24:
            centres.append(sum((v.co for v in obj.data.vertices), Vector()) / 24)
    # the box offset turned with the box (0.1 rad), so allow a little
    if len(centres) != 3 or any((c - want).length > 3 for c in centres):
        return [f"pod parts: expected three boxes {list(want)} from their anchors, got "
                f"{[tuple(round(x, 1) for x in c) for c in centres]}"]
    return []
