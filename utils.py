# Copyright (C) 2021-2024
# lightningpirate@gmail.com

# Created by LightningPirate

# This file is part of SWE1R Import/Export.

#     SWE1R Import/Export is free software; you can redistribute it and/or
#     modify it under the terms of the GNU General Public License
#     as published by the Free Software Foundation; either version 3
#     of the License, or (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program; if not, see <https://www.gnu.org
# /licenses>.

import bpy
import json
import os
import math
import webbrowser
import bpy
import mathutils
import copy
import numpy as np
import shutil

from .swe1r.model_list import *

def backup_original(path):
    """Create a one-time pristine backup of a .bin file before it is first
    overwritten. The '.bak' copy is written only if it does not already exist,
    so it always preserves the state of the file before this add-on ever
    modified it — letting the user recover the original game data.
    Returns the backup path if one was created, else None."""
    if not os.path.exists(path):
        return None
    backup_path = path + '.bak'
    if os.path.exists(backup_path):
        return None
    try:
        shutil.copy2(path, backup_path)
        return backup_path
    except OSError as e:
        print(f"Could not back up {path}: {e}")
        return None

# 'bswe1r' for 'blender swe1r'
# NOTE: use 3-letter code for data_type and group_id
data_name_prefix_short = 'bswe1r_'
data_name_format_short = 'bswe1r_{label}'
data_name_prefix_short_len = 7
data_name_format = 'bswe1r_{data_type}_{label}'
data_name_prefix_len = 11
data_name_format_long = 'bswe1r_{data_type}_{group_id}_{label}'
data_name_format_long_len = 15

model_types = [
    ('0', 'All', 'View all models'),
    ('1', 'MAlt', 'High LOD Pod Models'),
    ('2', 'Modl', 'Misc animated elements'),
    ('3', 'Part', 'Misc props'),
    ('4', 'Podd', 'Pod models'),
    ('5', 'Pupp', 'Animated characters'),
    ('6', 'Scen', 'Animated scenes'),
    ('7', 'Trak', 'Tracks'),
    ]

# The Import > Type list. A MAlt is a Podd's high detail parts: importing the Podd merges them in
# and exporting it writes them back, so MAlt is never offered on its own. Each item keeps its
# model_types index as its enum number so .blend files saved with the full list still read right.
import_types = [(code, name, description, 'NONE', int(code)) for code, name, description in model_types if name != 'MAlt']

header_sizes = [-1,75, 1,2,75,9, 83,6]

Podd_MAlt = {
    "2": 0,
    "4": 3,
    "6": 5,
    "8": 7,
    "9": 10,
    "12": 11,
    "14": 13,
    "17": 15,
    "16": 18,
    "20": 19,
    "22": 21,
    "24": 23,
    "26": 25,
    "28": 27,
    "30": 29,
    "32": 31,
    "34": 33,
    "36": 35,
    "38": 37,
    "40": 39,
    "42": 41,
    "44": 43,
    "46": 45,
    "299": 298,
    "301": 300
}

def model_enum_item(i, model):
    """Build a (identifier, label, description) tuple for a model enum.

    The identifier is the model index as a string (unchanged, so saved
    selections keep working). The label includes the name, the extension, and
    the numeric id so otherwise-identical entries (e.g. the several
    "Anakin Skywalker" variants) are distinguishable.
    """
    return (
        str(i),
        f"{model['name']}  ({model['extension']} {i})",
        f"{model['extension']} model '{model['name']}' (id {i})",
    )

showbytes = {
    "115": 16,
    "142": 16,
    "130": 16,
    "133": 16,
    "232": 16,
    "145": 16,
    "143": 32,
    "134": 32,
    "131": 32,
    "233": 32,
    "136": 16,
    "144": 64,
    "139": 16,
    "135": 64,
    "148": 32,
    "315": 64,
    "140": 16,
    "132": 64,
    "137": 32,
    "141": 16,
    "1": 16,
    "128": 16,
    "138": 64,
    "231": 64,
    "129": 16
}

SETTINGS_FILE = os.path.join(bpy.utils.user_resource('CONFIG'), "blender_swe1r_settings.json")

def import_model_items(model_type):
    """Items for the Import > Model dropdown. 'All' (-1) imports every model of the chosen type,
    so it is only offered when a single type is chosen. MAlt models are left out (see import_types)."""
    if model_type == 'All':
        return [model_enum_item(i, model) for i, model in enumerate(model_list) if model['extension'] != 'MAlt']
    items = [model_enum_item(i, model) for i, model in enumerate(model_list) if model['extension'] == model_type]
    items.insert(0, ('-1', 'All', f'Import all {model_type} models'))
    return items

def update_model_dropdown(self, context):
    model_type = model_types[int(context.scene.import_type)][1]
    bpy.types.Scene.import_model = bpy.props.EnumProperty(
        items=import_model_items(model_type),
        name="Model",
        description="Select a model to import",
        update=save_settings,
    )
    save_settings(self, context)
    
def export_model_items(self, context):
    model_type = model_types[int(self.export_type)][1]
    items_for_selected_category = [model_enum_item(i, model) for i, model in enumerate(model_list) if model['extension'] == model_type]
    return items_for_selected_category

def update_selected(prop_name, update_mat = False, update_tex = False):
    def update_function(self, context):
        if context.scene.podblock_syncing:
            return
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                if update_mat:
                    from .swe1r.modelblock import Material
                    mats = [slot.material for slot in obj.material_slots]
                    if not mats or mats[0] is None:
                        continue
                    # getattr, not scene[prop]: since Blender 5.0 registered properties are not ID properties
                    value = getattr(context.scene, prop_name)
                    if not update_tex:
                        for mat in mats:
                            if mat is not None and hasattr(mat, prop_name):
                                setattr(mat, prop_name, value)
                    # only the first material is exported, so only it is rebuilt
                    tex_name = value.name if update_tex and value is not None else None
                    obj.material_slots[0].material = Material(None, None).remake(mats[0], tex_name = tex_name)
                else:
                    if hasattr(obj, prop_name):
                        setattr(obj, prop_name, getattr(context.scene, prop_name))
                    elif hasattr(obj.data, prop_name):
                        setattr(obj.data, prop_name, getattr(context.scene, prop_name))
    return update_function
    
def SplineVis(self, context = None):
    for obj in bpy.context.scene.objects:
        if obj.type == "CURVE":
            obj.hide_viewport = not context.scene.spline_visible

def ColVis(self, context = None):
    for obj in bpy.context.scene.objects:
        if obj.collidable:
            obj.hide_viewport = not context.scene.collision_visible
            
def ShoVis(self, context = None):
    for obj in bpy.context.scene.objects:
        if obj.visible:
            obj.hide_viewport = not context.scene.visuals_visible
                
def EmptyVis(self, context):
    for obj in bpy.context.scene.objects:
        if obj.type == "EMPTY" or obj.type == "LIGHT":
            obj.hide_viewport = not context.scene.emptyvis
            
def UpdateVisibleSelectable(self, context = None):
    if context is None:
        context = bpy.context
    # Convenience show/hide must only ever touch the working view layer (index 0),
    # which the exporter skips. Writing to context.view_layer could land on one of
    # the 23 game/detail view layers and corrupt the vis/col flags read on export
    # (e.g. hiding a collision mesh here would clear its collision in-game).
    working_layer = context.scene.view_layers[0]
    scene = context.scene

    def show(obj, visible, selectable):
        # only write what changes: each hide_viewport/hide_select write costs ~1ms
        if obj.hide_viewport != (not visible):
            obj.hide_viewport = not visible
        if obj.hide_select != (not selectable):
            obj.hide_select = not selectable
        obj.hide_set(not visible, view_layer=working_layer)

    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        if obj.collidable:
            show(obj, scene.collision_visible, scene.collision_selectable)
        if obj.visible:
            show(obj, scene.visuals_visible, scene.visuals_selectable)
            
            
    
# Scene properties remembered between Blender sessions (each is registered with update=save_settings)
SETTINGS_KEYS = [
    'import_folder', 'import_type', 'import_model', 'export_folder', 'new_type',
    'is_export_model', 'is_export_texture', 'is_export_spline', 'is_export_separate', 'is_export_debug',
    'light_falloff', 'ambient_light', 'ambient_light_intensity', 'bake_method', 'bake_samples', 'bake_pod_lights',
    # the Selected panel's open sections
    'lights_expanded', 'textures_expanded', 'flipbook_expanded', 'flags_expanded', 'fog_expanded',
    'lighting_expanded', 'trigger_expanded', 'event_triggers_expanded', 'animation_expanded',
]

def save_settings(self, context):
    # getattr, not scene.get(): since Blender 5.0 registered properties are not ID properties
    settings = load_settings()
    for key in SETTINGS_KEYS:
        if not hasattr(context.scene, key):
            continue
        value = getattr(context.scene, key)
        settings[key] = value if isinstance(value, (str, int, float, bool)) else list(value)
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

def load_settings():
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
    return settings

def get_setting(key, default=None):
    settings = load_settings()
    val = settings.get(key, default)
    return val if val is not None else default

def SelVis(self, context = None):
    for obj in bpy.context.scene.objects:
        if obj.visible:  # registered property; obj['visible'] is a separate custom one since Blender 5.0
            obj.hide_select = not context.scene.visuals_selectable

def SelCol(self, context = None):
    for obj in bpy.context.scene.objects:
        if obj.collidable:
            obj.hide_select = not context.scene.collision_selectable
            
def open_url(url: str) -> None:
    webbrowser.open(url)

def euclidean_distance(color1, color2):
    return math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color1, color2)))

def blend_multiply(a: float, b: float) -> float:
    return a*b 

def blend_overlay(a: float, b: float) -> float:
    return 2.0*a*b if a < 0.5 else 1.0-2.0*(1.0-a)*(1.0-b) 

def occluder_tree(objects):
    """One BVH tree, in world space, of the meshes that cast shadows when baking. Built once per
    bake: scene.ray_cast per vertex and light was most of the old bake's time."""
    from mathutils.bvhtree import BVHTree
    depsgraph = bpy.context.evaluated_depsgraph_get()
    verts, tris = [], []
    offset = 0
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            co = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
            mesh.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            matrix = np.array(obj.matrix_world)
            co = co @ matrix[:3, :3].T + matrix[:3, 3]
            loop_tris = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
            mesh.loop_triangles.foreach_get("vertices", loop_tris)
            verts.append(co)
            tris.append(loop_tris.reshape(-1, 3) + offset)
            offset += len(co)
        finally:
            evaluated.to_mesh_clear()
    if not verts:
        return None
    return BVHTree.FromPolygons(np.concatenate(verts).tolist(), np.concatenate(tris).tolist())

def skybox_objects():
    """Every object in a Skybox collection (or one nested in it)."""
    return {obj for c in bpy.data.collections if getattr(c, 'collection_type', None) == '1' for obj in c.all_objects}

def bake_occluders(scene):
    """The meshes that cast shadows when baking: what the game draws (Visible meshes), minus the
    skybox (a sky dome would shadow everything under it) and meshes with Cast Shadows off."""
    sky = skybox_objects()
    return [obj for obj in scene.objects
            if obj.type == 'MESH' and obj.visible and obj.visible_shadow and obj not in sky]

def pod_lights(scene):
    """Light objects picked as Pod Lighting by a mesh. They hold the game's pod light, a
    direction stored as a position, not a light on the track."""
    used = {obj.lighting_light for obj in scene.objects if obj.type == 'MESH' and getattr(obj, 'lighting_light', None)}
    return {obj for obj in scene.objects if obj.type == 'LIGHT' and obj.data in used}

def bake_light_objects(scene):
    """The light objects a bake uses: every light, minus pod lights unless Include Pod Lights is on,
    and minus lights disabled in renders."""
    skip = set() if scene.bake_pod_lights else pod_lights(scene)
    return [obj for obj in scene.objects if obj.type == 'LIGHT' and obj not in skip and not obj.hide_render]

def bake_lights(scene):
    """(kind, color, position or direction toward the light, casts shadows) of every point and
    sun light: the kinds the Simple bake uses (spot and area lights are ignored). A light with
    Blender's Shadow setting off lights through geometry, as it does in Cycles."""
    lights = []
    for light in bake_light_objects(scene):
        if light.data.type not in ('POINT', 'SUN'):
            continue
        color = np.array(light.data.color, dtype=np.float64)
        if light.data.type == 'POINT':
            lights.append(('POINT', color, np.array(light.matrix_world.to_translation()), light.data.use_shadow))
        else:
            # toward the sun: its world +Z (a sun shines along its -Z), so parents and any rotation mode count
            direction = light.matrix_world.to_3x3() @ mathutils.Vector((0, 0, 1))
            lights.append(('SUN', color, np.array(direction.normalized()), light.data.use_shadow))
    return lights

def calculate_total_light_for_object(obj, lights, tree, falloff_factor=1.0, ambient_light_intensity=0.1, ambient_light_color=(0, 0, 0)):
    """Per vertex of obj: ambient light x strength, plus each light's color x cos(angle to the
    normal), divided by distance^falloff for point lights; nothing from a light the vertex faces
    away from or that geometry in tree hides. Returns an (n, 3) array."""
    mesh = obj.data
    n = len(mesh.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", co)
    normals = np.empty(n * 3, dtype=np.float64)
    mesh.vertex_normals.foreach_get("vector", normals)
    matrix = np.array(obj.matrix_world)
    co = co.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
    # normals transform by the inverse transpose, so non-uniform scale keeps them perpendicular
    normal_matrix = np.array(obj.matrix_world.to_3x3().inverted_safe().transposed())
    normals = normals.reshape(-1, 3) @ normal_matrix.T
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)

    total = np.tile(np.array(ambient_light_color, dtype=np.float64) * ambient_light_intensity, (n, 1))
    # rays start just off the surface, so a vertex doesn't shadow itself
    origins = co + normals * 0.001
    for kind, color, where, casts_shadow in lights:
        if kind == 'POINT':
            to_light = where - co
            distance = np.linalg.norm(to_light, axis=1)
            direction = np.divide(to_light, distance[:, None], out=np.zeros_like(to_light), where=distance[:, None] > 0)
        else:
            direction = np.broadcast_to(where, co.shape)
            distance = np.full(n, np.inf)
        cos = np.einsum('ij,ij->i', normals, direction)
        lit = cos > 0
        if tree is not None and casts_shadow:
            for i in np.flatnonzero(lit):
                limit = distance[i] if kind == 'POINT' else 1.0e9
                if tree.ray_cast(origins[i], direction[i], limit)[0] is not None:
                    lit[i] = False
        if kind == 'POINT':
            strength = np.where(lit, cos / np.power(np.maximum(distance, 1e-9), falloff_factor), 0.0)
        else:
            strength = np.where(lit, cos, 0.0)
        total += strength[:, None] * color
    return total

STOCK_SUN_NAME = 'stock sun'
# the fit must explain at least this share of the vertex colors' brightness variation, or no sun
# is made (an arena lit by tinted floodlights, like Mon Gazza, has no sun to find)
STOCK_SUN_MIN_R2 = 0.1

def fit_stock_sun(collection, scene):
    """Recreate the sun a stock track's vertex colors were baked with, as a Sun light.

    The stock bakes are sun shading with no cast shadows (brightness follows how much each face
    points at one direction), plus per-mesh adjustments and hand painting that no light explains.
    The direction is marked by the track's pod lights: outdoor tracks light the pod from a point
    outside the track, and the direction from the track's center to it matches the best-fitting
    sun within about 15 degrees on Boonta (exactly on the Classic), Aquilaris and Ando Prime. The sun's color and the ambient
    light are then fitted to the vertex colors by least squares, so a Simple bake with this sun
    alone comes close to the stock shading. The sun's Shadow setting is off, like the stock bake.

    Returns (sun object or None, a sentence on what was done)."""
    from .swe1r.modelblock import object_uses_normals
    sky = skybox_objects()
    meshes = [o for o in collection.all_objects if o.type == 'MESH' and o.visible and o not in sky
              and not object_uses_normals(o) and o.data.vertex_colors and o.data.vertex_colors.active]
    if not meshes:
        return None, "no meshes with vertex colors"
    positions, normals, colors = [], [], []
    for obj in meshes:
        me = obj.data
        n = len(me.vertices)
        co = np.empty(n * 3); me.vertices.foreach_get('co', co)
        no = np.empty(n * 3); me.vertex_normals.foreach_get('vector', no)
        m = np.array(obj.matrix_world)
        nm = np.array(obj.matrix_world.to_3x3().inverted_safe().transposed())
        loop_verts = np.empty(len(me.loops), dtype=np.int32); me.loops.foreach_get('vertex_index', loop_verts)
        loop_cols = np.empty(len(me.loops) * 4, dtype=np.float32); me.vertex_colors.active.data.foreach_get('color', loop_cols)
        # each vertex's color: one of its corners (stock vertices have one color)
        per_vertex = np.ones((n, 3))
        per_vertex[loop_verts] = loop_cols.reshape(-1, 4)[:, :3]
        used = np.zeros(n, dtype=bool); used[loop_verts] = True
        positions.append((co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3])[used])
        nn = no.reshape(-1, 3) @ nm.T
        nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
        normals.append(nn[used]); colors.append(per_vertex[used])
    P, N, C = np.concatenate(positions), np.concatenate(normals), np.concatenate(colors)
    center = P.mean(0)
    radius = np.linalg.norm(P - center, axis=1).max()

    luma = np.array([0.299, 0.587, 0.114])
    L = C @ luma

    def fit_direction(toward):
        cos = np.clip(N @ toward, 0.0, None)
        A = np.column_stack([np.ones(len(cos)), cos])
        fit, *_ = np.linalg.lstsq(A, C, rcond=None)
        predicted = (A @ fit) @ luma
        r2 = 1 - ((L - predicted) ** 2).sum() / max(((L - L.mean()) ** 2).sum(), 1e-12)
        return r2, fit

    # Candidates: point pod lights outside the track. Pod lights at one spot often share it with
    # different colors, and the most used one can be a nearby lamp, so the best fit picks.
    used = {obj.lighting_light for obj in collection.all_objects
            if obj.type == 'MESH' and getattr(obj, 'lighting_light', None) is not None}
    best = None
    for obj in sorted(collection.all_objects, key=lambda o: o.name):
        if obj.type != 'LIGHT' or obj.data not in used or obj.data.type != 'POINT':
            continue
        offset = np.array(obj.matrix_world.to_translation()) - center
        distance = np.linalg.norm(offset)
        if distance <= radius:
            continue
        toward = offset / distance
        r2, fit = fit_direction(toward)
        if fit[1] @ luma > 0 and (best is None or r2 > best[0] + 1e-6):
            best = (r2, fit, obj, toward)
    if best is None:
        return None, "no pod light outside the track to take the sun's direction from"
    r2, fit, pod_light, toward = best
    ambient, sun_color = np.clip(fit[0], 0.0, None), fit[1]
    if sun_color @ luma <= 0 or r2 < STOCK_SUN_MIN_R2:
        return None, f"the vertex colors don't follow a sun from {pod_light.name}'s direction (it explains {r2:.0%})"
    sun_color = np.clip(sun_color, 0.0, 1.0)

    data = bpy.data.lights.new(STOCK_SUN_NAME, 'SUN')
    data.color = sun_color.tolist()
    data.energy = 1.0  # Strength 1 gives the color itself in a Cycles bake, as in Simple
    data.use_shadow = False
    sun = bpy.data.objects.new(STOCK_SUN_NAME, data)
    # a sun shines along its -Z: away from the light
    sun.rotation_euler = mathutils.Vector((-toward).tolist()).to_track_quat('-Z', 'Y').to_euler()
    sun.location = (center + toward * radius * 0.5).tolist()
    sun['stock_sun_explains'] = float(round(r2, 3))
    sun['stock_sun_from'] = pod_light.name
    collection.objects.link(sun)
    strength = float(ambient.max())
    scene.ambient_light = (ambient / strength).tolist() if strength > 0 else (1.0, 1.0, 1.0)
    scene.ambient_light_intensity = min(strength, 1.0)
    return sun, (f"made '{sun.name}' from {pod_light.name}; with the fitted ambient light it explains "
                 f"{r2:.0%} of the stock shading's brightness")

def cycles_bake_lighting(context, meshes, samples):
    """Bake the scene's lighting into each mesh with Cycles: (n_loops, 3) arrays of linear light,
    per face corner, keyed by mesh. Soft shadows, bounce light, every light type and its power,
    emissive materials and transparent (alpha) materials all count.

    What casts shadows and what lights the scene match the Simple bake: bake_occluders and
    bake_light_objects; everything else is hidden from the render while baking. The world is
    left out (the Ambient Light settings stand in for it), and the meshes being baked start from
    white vertex colors so their old bake doesn't tint the bounce light. Every scene setting the
    bake changes is restored afterwards."""
    scene = context.scene
    view_layer = context.view_layer
    occluders = set(bake_occluders(scene))
    lights = set(bake_light_objects(scene))
    targets = set(meshes)

    saved_render = {}
    saved_selection = [obj for obj in context.selected_objects]
    saved_active = view_layer.objects.active
    saved_engine = scene.render.engine
    saved_world = scene.world
    saved_samples = None
    temp_name = '_swe1r_bake'
    # The add-on's materials show the camera an unlit color and every other ray a diffuse surface
    # (Material.make). A bake shades the baked surface like a camera ray, so the switch is muted
    # (a muted Mix Shader passes its first input, the diffuse surface) until the bake is done.
    camera_mixes = []
    for material in bpy.data.materials:
        if material.node_tree is not None:
            node = material.node_tree.nodes.get('SWE1R camera mix')
            if node is not None and not node.mute:
                camera_mixes.append(node)
    try:
        for node in camera_mixes:
            node.mute = True
        scene.render.engine = 'CYCLES'
        saved_samples = (scene.cycles.samples, scene.cycles.use_denoising)
        scene.cycles.samples = samples
        # the denoiser works on images; per-vertex results come out of the samples
        scene.cycles.use_denoising = False
        scene.world = None
        for obj in scene.objects:
            if obj.type == 'MESH':
                show = obj in occluders or obj in targets
            elif obj.type == 'LIGHT':
                show = obj in lights
            else:
                continue
            if obj.hide_render == show:
                saved_render[obj] = obj.hide_render
                obj.hide_render = not show

        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in meshes:
            reset_vertex_colors(obj)
            attrs = obj.data.color_attributes
            obj['_swe1r_bake_active'] = attrs.active_color_name or ''
            # a float attribute holds the light exactly; the bake writes to the active one
            attrs.active_color = attrs.new(temp_name, 'FLOAT_COLOR', 'CORNER')
            obj.select_set(True)
        view_layer.objects.active = meshes[0]
        bpy.ops.object.bake(type='DIFFUSE', pass_filter={'DIRECT', 'INDIRECT'}, target='VERTEX_COLORS')

        results = {}
        for obj in meshes:
            data = obj.data.color_attributes[temp_name].data
            values = np.empty(len(data) * 4, dtype=np.float32)
            data.foreach_get('color', values)
            # the diffuse pass is irradiance / pi; x pi makes a Strength 1 sun shining straight on
            # give white, like a white sun in the Simple bake
            results[obj] = values.reshape(-1, 4)[:, :3].astype(np.float64) * math.pi
        return results
    finally:
        for obj in meshes:
            attrs = obj.data.color_attributes
            temp = attrs.get(temp_name)
            if temp is not None:
                attrs.remove(temp)
            previous = obj.pop('_swe1r_bake_active', '')
            if previous and attrs.get(previous) is not None:
                attrs.active_color = attrs[previous]
        for node in camera_mixes:
            node.mute = False
        for obj, hidden in saved_render.items():
            obj.hide_render = hidden
        scene.world = saved_world
        if saved_samples is not None:
            scene.cycles.samples, scene.cycles.use_denoising = saved_samples
        scene.render.engine = saved_engine
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in saved_selection:
            obj.select_set(True)
        view_layer.objects.active = saved_active

# Single re-entrancy flag for the whole selection-sync cascade. Each setattr
# below re-fires this same callback on the target object; a per-object guard
# doesn't stop that (siblings keep re-triggering each other and it blows up
# combinatorially, hanging Blender). One flag makes every nested call no-op.
_syncing_prop = False

def create_update_function(prop_name):
    def update_function(self, context):
        global _syncing_prop

        if _syncing_prop:
            return

        try:
            _syncing_prop = True

            # Update the property for all selected objects except the current one
            for obj in context.selected_objects:
                if obj != self and hasattr(obj, prop_name):
                    setattr(obj, prop_name, getattr(self, prop_name))
                elif hasattr(obj.data, prop_name):
                    setattr(obj.data, prop_name, getattr(self, prop_name))

        finally:
            _syncing_prop = False
    return update_function

name_attr_colors = data_name_format_short.format(label='colors')
name_attr_baked = data_name_format_short.format(label='colors_baked')

def init_vertex_colors(b_obj):
    if b_obj.type != 'MESH' or not b_obj.visible:
        return

    if not hasattr(b_obj.data, 'color_attributes') or len(b_obj.data.color_attributes) == 0:
        b_obj.data.color_attributes.new(name_attr_colors, 'BYTE_COLOR', 'CORNER')
        b_obj.data.attributes.render_color_index = b_obj.data.attributes.active_color_index

        for color in b_obj.data.attributes[name_attr_colors].data:
            color.color = [1.0, 1.0, 1.0, 1.0]

def reset_vertex_colors(b_obj):
    from .swe1r.modelblock import object_uses_normals
    # a Lit mesh's colors hold its normals
    if b_obj.type != 'MESH' or not b_obj.visible or object_uses_normals(b_obj):
        return

    if not hasattr(b_obj.data, 'color_attributes') or len(b_obj.data.color_attributes) == 0:
        b_obj.data.color_attributes.new(name_attr_colors, 'BYTE_COLOR', 'CORNER')
        b_obj.data.attributes.render_color_index = b_obj.data.attributes.active_color_index

        for color in b_obj.data.attributes[name_attr_colors].data:
            color.color = [1.0, 1.0, 1.0, 1.0]

    #use first color layer if no active layer
    if b_obj.data.vertex_colors.active is None:
        b_obj.data.vertex_colors.active_index = 0

    color_layer = b_obj.data.vertex_colors.active.data
    for loop in color_layer:
        loop.color = [1.0, 1.0, 1.0, 1.0]

    color_baked = b_obj.data.attributes.get(name_attr_baked)
    if color_baked is not None and b_obj.data.attributes.default_color_name != name_attr_baked:
        b_obj.data.attributes.remove(color_baked)
            
def populate_enum(scene, context):

    current_view_layers = [None]

    for view_layer in bpy.context.scene.view_layers.items():
        current_view_layers.append((view_layer[0],view_layer[0], ""),)
 
    return current_view_layers


# checks if normals will be flipped after applying scale due to object-parent 
# chain resolving to negative scale
def check_flipped(o):
    flipped = False
    while o.parent is not None:
        flipped = not(flipped) if [n < 0 for n in o.scale].count(True) % 2 else flipped
        o = o.parent
    return flipped

def show_custom_popup(context, title, message):
    def draw(self, context):
        layout = self.layout
        layout.label(text=message)

    # popup_menu crashes Blender when there is no window (--background test runs)
    if bpy.app.background or bpy.context.window is None:
        print(f"{title}: {message}")
        return
    bpy.context.window_manager.popup_menu(draw, title=title, icon='INFO')
    
# Bumped to make the sidebar re-read the selection's properties (panels.on_object_selection only
# re-syncs when the selection changes, so an operator that edits the selected objects bumps this)
panel_sync_generation = [0]

def reselect_obj(obj):
    panel_sync_generation[0] += 1
    obj.select_set(False)
    obj.select_set(True)

# The pod anchors New > Podd adds: (name, display, size). Positions come from the replaced pod's row
# in the game's table (swe1r/pod_visual.py).
POD_ANCHORS = {
    'engine_r': ("Anchor Engine R", 'SPHERE', 0.4),
    'engine_l': ("Anchor Engine L", 'SPHERE', 0.4),
    'cockpit': ("Anchor Cockpit", 'SPHERE', 0.4),
    'exhaust_r': ("Anchor Exhaust R", 'SINGLE_ARROW', 0.6),
    'exhaust_l': ("Anchor Exhaust L", 'SINGLE_ARROW', 0.6),
    'binder_r': ("Anchor Binder R", 'PLAIN_AXES', 0.25),
    'binder_l': ("Anchor Binder L", 'PLAIN_AXES', 0.25),
    'cable_cockpit_r': ("Anchor Cable Cockpit R", 'PLAIN_AXES', 0.2),
    'cable_cockpit_l': ("Anchor Cable Cockpit L", 'PLAIN_AXES', 0.2),
    'cable_engine_r': ("Anchor Cable Engine R", 'PLAIN_AXES', 0.2),
    'cable_engine_l': ("Anchor Cable Engine L", 'PLAIN_AXES', 0.2),
}

def place_pod_anchors(collection):
    """Add or move a pod template's anchors to where the game draws the replaced pod's engines,
    cockpit and exhausts, and the ends of its binder and cables. The game positions those parts itself (swe1r/pod_visual.py), so the
    anchors are locked: model each part around its anchor."""
    from .swe1r.pod_visual import pod_anchor_positions
    positions = pod_anchor_positions(collection.export_model)
    if positions is None:
        return
    existing = {obj.get('pod_anchor'): obj for obj in collection.objects if obj.get('pod_anchor')}
    for key, (name, display, size) in POD_ANCHORS.items():
        obj = existing.get(key)
        if obj is None:
            obj = bpy.data.objects.new(name, None)
            obj['pod_anchor'] = key
            obj.empty_display_type = display
            obj.empty_display_size = size
            collection.objects.link(obj)
            if display == 'SINGLE_ARROW':
                # points back, the way the exhaust blows
                obj.rotation_euler = (math.pi / 2, 0, 0)
            obj.lock_location = obj.lock_rotation = obj.lock_scale = (True, True, True)
        obj.location = positions[key]

def update_export_model(self, context):
    """Replaces changed: a pod template's anchors follow the newly replaced pod."""
    if self.collection_type == "MODEL" and self.export_type == '4' and any(obj.get('pod_anchor') for obj in self.objects):
        place_pod_anchors(self)

def transform_fcurves(obj):
    """The object's location/rotation/scale fcurves (what the game animates), or []."""
    if obj is None or obj.animation_data is None or obj.animation_data.action is None:
        return []
    from bpy_extras import anim_utils
    bag = anim_utils.action_get_channelbag_for_slot(obj.animation_data.action, obj.animation_data.action_slot)
    if not bag:
        return []
    return [f for f in bag.fcurves if f.data_path in ('location', 'scale', 'rotation_quaternion', 'rotation_euler', 'rotation_axis_angle')]

def get_anim_loop(self):
    """An object's animation loops in game when its curves have a Cycles modifier, which also makes
    Blender's timeline loop it (get_animations)."""
    return any(mod.type == 'CYCLES' for fcurve in transform_fcurves(self) for mod in fcurve.modifiers)

def set_anim_loop(self, value):
    from .swe1r.modelblock import ensure_cycles_first
    for fcurve in transform_fcurves(self):
        if value:
            ensure_cycles_first(fcurve)
        else:
            for mod in [m for m in fcurve.modifiers if m.type == 'CYCLES']:
                fcurve.modifiers.remove(mod)
    sync_hold_key(self)

# A Loop Length past the last key holds the last pose until then in game (swrModel_AnimationUpdateTime
# loops at the duration; past the last key the interpolators return its value). Blender's Cycles
# modifier loops at the last key instead, so a key repeating the last pose is put at the Loop Length:
# Blender then plays what the game does (stock puppets' limbs stay in step). Export leaves it out.
HOLD_KEY = 'anim_hold_frame'

def is_hold_key(fcurve, frame):
    """True when the fcurve's last key is the hold key at `frame`: there, and repeating the key before."""
    kps = fcurve.keyframe_points
    return (len(kps) >= 2 and abs(kps[-1].co[0] - frame) < 1e-3 and abs(kps[-1].co[1] - kps[-2].co[1]) < 1e-6)

def hold_key_frame(obj):
    """The frame of the object's hold key, or None."""
    frame = obj.get(HOLD_KEY)
    return float(frame) if frame is not None else None

def sync_hold_key(obj):
    """Put the hold key where the Loop settings say (or remove it): at Loop Length, on every
    transform curve, when Loop is on and the length runs past the last key."""
    frame = hold_key_frame(obj)
    fcurves = transform_fcurves(obj)
    if frame is not None:
        for fcurve in fcurves:
            if is_hold_key(fcurve, frame):
                fcurve.keyframe_points.remove(fcurve.keyframe_points[-1])
                fcurve.update()
        del obj[HOLD_KEY]
    if not fcurves or not get_anim_loop(obj):
        return
    scene = bpy.context.scene
    frame = obj.anim_loop_length * scene.render.fps / scene.render.fps_base
    last = max((k.co[0] for f in fcurves for k in f.keyframe_points), default = None)
    if last is None or frame <= last + 1e-3:
        return
    for fcurve in fcurves:
        key = fcurve.keyframe_points.insert(frame, fcurve.keyframe_points[-1].co[1], options = {'FAST'})
        key.interpolation = 'LINEAR'
        fcurve.update()
    obj[HOLD_KEY] = frame

def update_anim_loop_length(self, context):
    sync_hold_key(self)

def find_model_collection(context):
    """The Model collection (collection_type 'MODEL') the user is working in: the active
    collection or the active object's collection, or the nearest Model collection above either.
    None if there is none."""
    parents = {}
    for collection in bpy.data.collections:
        for child in collection.children:
            parents.setdefault(child.name, collection)

    def climb(collection):
        while collection is not None:
            if collection.collection_type == "MODEL":
                return collection
            collection = parents.get(collection.name)
        return None

    starts = []
    obj = context.active_object
    if obj is not None and obj.select_get():
        starts.extend(obj.users_collection)
    layer_collection = context.view_layer.active_layer_collection
    if layer_collection is not None:
        starts.append(layer_collection.collection)
    for collection in starts:
        found = climb(collection)
        if found is not None:
            return found
    return None
    
    
def validate_folder_path(folder_path, file_name):
    """Validate that folder_path exists and contains the required .bin file(s).

    file_name may be a single filename or a list of filenames; every entry must
    be present. Returns the (possibly resolved) folder path, or {'CANCELLED'}
    with a popup naming exactly which files are missing.
    """
    if folder_path == "":
        show_custom_popup(bpy.context, "No set folder", "Select your folder containing the .bin files")
        return {'CANCELLED'}
    if folder_path[:2] == '//':
        folder_path = os.path.join(os.path.dirname(bpy.data.filepath), folder_path[2:])
    file_names = [file_name] if isinstance(file_name, str) else list(file_name)
    missing = [f for f in file_names if not os.path.exists(folder_path + f)]
    if missing:
        show_custom_popup(bpy.context, "Missing required files", f"The selected folder is missing: {', '.join(missing)}")
        return {'CANCELLED'}
    return folder_path

import bpy
import os
import hashlib
import traceback

def create_material_from_image(image_path, material_name):
    """
    Create a material with an image texture and return the material.
    
    Args:
        image_path: Full path to the image file
        material_name: Name for the material
    
    Returns:
        bpy.types.Material: The created material
    """
    # Create new material
    mat = bpy.data.materials.new(name=material_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Clear default nodes
    nodes.clear()
    
    # Create nodes
    node_tex = nodes.new(type='ShaderNodeTexImage')
    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    
    # Load image
    if os.path.exists(image_path):
        img = bpy.data.images.load(image_path)
        node_tex.image = img
    
    # Position nodes for cleaner node tree
    node_tex.location = (-300, 0)
    node_bsdf.location = (0, 0)
    node_output.location = (300, 0)
    
    # Link nodes
    links.new(node_tex.outputs['Color'], node_bsdf.inputs['Base Color'])
    links.new(node_bsdf.outputs['BSDF'], node_output.inputs['Surface'])
    
    return mat


def mark_material_as_asset(material, catalog_id=None, tags=None):
    """
    Mark a material as an asset and optionally assign it to a catalog.
    
    Args:
        material: The material to mark as asset
        catalog_id: UUID string of the catalog (e.g., "a8e1a507-d4e9-4f8f-a7e7-5e6f7d8e9f0a")
        tags: List of tag strings to add to the asset
    """
    # Mark as asset
    material.asset_mark()
    
    # Set catalog if provided (must be a valid UUID)
    if catalog_id:
        material.asset_data.catalog_id = catalog_id
    
    # Add tags if provided
    if tags:
        for tag in tags:
            material.asset_data.tags.new(tag)
    
    # Generate preview (this will use default material preview)
    material.asset_generate_preview()


def get_material_hash(material):
    """
    Generate a hash representing the material's properties for deduplication.
    This compares node tree structure and key properties.
    
    Returns:
        str: Hash string representing the material
    """
    if not material.use_nodes:
        return None
    
    hash_parts = []
    nodes = material.node_tree.nodes
    
    # Sort nodes by type and location for consistent ordering
    sorted_nodes = sorted(nodes, key=lambda n: (n.type, n.location.x, n.location.y))
    
    for node in sorted_nodes:
        # Add node type
        hash_parts.append(node.type)
        
        # For image texture nodes, hash the image filepath
        if node.type == 'TEX_IMAGE' and node.image:
            hash_parts.append(node.image.filepath or node.image.name)
        
        # For value/color nodes, hash the values
        elif node.type == 'VALUE':
            hash_parts.append(str(node.outputs[0].default_value))
        elif node.type == 'RGB':
            hash_parts.append(str(node.outputs[0].default_value[:]))
        
        # For BSDF nodes, hash key input values
        elif 'BSDF' in node.type:
            for input in node.inputs:
                if not input.is_linked:
                    hash_parts.append(f"{input.name}:{input.default_value}")
    
    # Hash the connections
    links = material.node_tree.links
    for link in sorted(links, key=lambda l: (l.from_node.name, l.to_node.name)):
        hash_parts.append(f"{link.from_socket.name}->{link.to_socket.name}")
    
    # Create hash from all parts
    import hashlib
    hash_string = "|".join(str(p) for p in hash_parts)
    return hashlib.md5(hash_string.encode()).hexdigest()


def deduplicate_materials(materials):
    """
    Remove duplicate materials based on their properties.
    
    Args:
        materials: List of materials to deduplicate
    
    Returns:
        list: Deduplicated list of materials
    """
    # Filter out any materials that have already been removed
    valid_materials = []
    for mat in materials:
        try:
            # Try to access a property to check if material still exists
            _ = mat.name
            valid_materials.append(mat)
        except ReferenceError:
            # Material was already removed, skip it
            continue
    
    # First, compute all hashes before removing anything
    material_hashes = []
    for mat in valid_materials:
        mat_hash = get_material_hash(mat)
        material_hashes.append((mat, mat_hash))
    
    # Now deduplicate based on hashes
    seen_hashes = {}
    unique_materials = []
    duplicates_to_remove = []
    
    for mat, mat_hash in material_hashes:
        if mat_hash is None:
            # Can't hash this material, keep it
            unique_materials.append(mat)
            continue
        
        if mat_hash in seen_hashes:
            # Duplicate found - mark for removal
            duplicates_to_remove.append(mat)
        else:
            # New unique material
            seen_hashes[mat_hash] = mat
            unique_materials.append(mat)
    
    # Remove duplicates after processing
    for mat in duplicates_to_remove:
        try:
            bpy.data.materials.remove(mat)
        except ReferenceError:
            # Material was already removed elsewhere
            pass
    
    print(f"Started with {len(materials)} materials, {len(valid_materials)} were valid")
    print(f"Removed {len(duplicates_to_remove)} duplicate materials")
    print(f"Final unique materials: {len(unique_materials)}")
    return unique_materials