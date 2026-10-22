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
    'light_falloff', 'ambient_light', 'ambient_light_intensity',
]

def save_settings(self, context):
    # getattr, not scene.get(): since Blender 5.0 registered properties are not ID properties
    settings = load_settings()
    for key in SETTINGS_KEYS:
        if not hasattr(context.scene, key):
            continue
        value = getattr(context.scene, key)
        settings[key] = value if isinstance(value, (str, int, float, bool)) else list(value)
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

def bake_lights(scene):
    """(kind, color, position or direction toward the light) of every point and sun light: the
    kinds the bake uses (spot and area lights are ignored)."""
    lights = []
    for light in scene.objects:
        if light.type != 'LIGHT' or light.data.type not in ('POINT', 'SUN'):
            continue
        color = np.array(light.data.color, dtype=np.float64)
        if light.data.type == 'POINT':
            lights.append(('POINT', color, np.array(light.matrix_world.to_translation())))
        else:
            # toward the sun: its world +Z (a sun shines along its -Z), so parents and any rotation mode count
            direction = light.matrix_world.to_3x3() @ mathutils.Vector((0, 0, 1))
            lights.append(('SUN', color, np.array(direction.normalized())))
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
    for kind, color, where in lights:
        if kind == 'POINT':
            to_light = where - co
            distance = np.linalg.norm(to_light, axis=1)
            direction = np.divide(to_light, distance[:, None], out=np.zeros_like(to_light), where=distance[:, None] > 0)
        else:
            direction = np.broadcast_to(where, co.shape)
            distance = np.full(n, np.inf)
        cos = np.einsum('ij,ij->i', normals, direction)
        lit = cos > 0
        if tree is not None:
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
    if b_obj.type != 'MESH' or not b_obj.visible:
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