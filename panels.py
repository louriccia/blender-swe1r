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

from .swr_import import *
from .swr_export import *
import bpy
from .swe1r.modelblock import SurfaceEnum
from .operators import *
from .constants import *
from . import NAME, VERSION
import os
from bpy.utils import previews
import mathutils
import numpy as np
from mathutils import Color, Vector, Euler, Quaternion
from . import utils
from .help_pages import HELP_PAGES, help_url
from .swe1r.trigger_types import TRIGGER_TYPES, type_label, type_warnings
import textwrap


classes = []
_in_selection_sync = False
_msgbus_owner = object()

#https://blenderartists.org/t/bpy-types-pointerproperty-fpr-view-layer/1446387
# For anyone who stumbles upon this topic in the future, you can create a custom enum like this:

#  vl: EnumProperty(
#         name="View Layer",
#         items=populate_enum
#     )
# then create a custom function which checks the current scene and returns a list of the current vlayers:

# def populate_enum(scene, context):

#     current_view_layers = []

#     for view_layer in bpy.context.scene.view_layers.items():
#         current_view_layers.append((view_layer[0],view_layer[0], ""),)
 
#     return current_view_layers

def get_default(holder, prop_name):
    prop = holder.bl_rna.properties[prop_name]
    if hasattr(prop, 'default_array') and prop.default_array:
        return [v for v in prop.default_array]
    elif hasattr(prop, 'default'):
        return prop.default
    return False

def get_frozen_value(value):
    # Check if the value is a mutable Color
    if isinstance(value, Color) and not value.is_frozen:
        frozen_copy = value.copy()
        frozen_copy.freeze()
        return frozen_copy
    return value

def make_hashable(v):
    if isinstance(v, (Color, Vector, Euler, Quaternion)):
        return tuple(v)
    return v

def get_prop_value(prop_name, indeterminates, items):
    if not items:
        return None
    values = set()
    for item in items:
        value = getattr(item, prop_name, None)
        values.add(make_hashable(value))
    if len(values) == 1:
        return values.pop()  # All values are the same
    elif len(values):
        indeterminates.append(prop_name)
    return get_default(bpy.context.scene, prop_name)

obj_props = ['visible',
            'collidable',
            'collision_data',
            'magnet',
            'strict_spline',
            'elevation',
            'lighting_color',
            'lighting_invert',
            'lighting_flicker',
            'lighting_persistent',
            'fog_color_update',
            'fog_color',
            'fog_range_update',
            'fog_min',
            'fog_max',
            'fog_clear',
            'skybox_show',
            'skybox_hide']

for flag in dir(SurfaceEnum):
    if not flag.startswith("__"):
        obj_props.append(flag)
        
mat_props = [
    'material_color',
    'scroll_x',
    'scroll_y',
    'flip_x',
    'flip_y',
    'clip_x',
    'clip_y',
    'use_backface_culling',
]

# The game's four-letter surface codes, spelled out (the tooltip says what each does)
SURFACE_FLAG_LABELS = {
    'Fast': "Fast", 'Slow': "Slow", 'Swst': "Very Slow", 'Slip': "Slippery", 'Lava': "Lava",
    'ZOn': "Zero-g On", 'ZOff': "Zero-g Off", 'Fall': "Fall", 'NRsp': "No Respawn",
    'Dust': "Dust", 'Wet': "Wet", 'Swmp': "Swamp", 'Snow': "Snow", 'NSnw': "No Snow",
    'Mirr': "Mirror", 'Side': "Side",
    'Ruff': "Rough", 'Soft': "Soft", 'Flat': "Flat (AI)",
}

def is_indeterminate(prop, text = ""):
    indeterminates = bpy.context.scene.indeterminates
    is_ind = prop in indeterminates.split(",")
    if not is_ind:
        return ""
    if text:
        return text
    return "*"

def is_v_lighting_default(context): 
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    for obj in selected_meshes:
        if obj.type != 'MESH':
            continue  # Skip non-mesh objects

        mesh = obj.data
        
        if not mesh.vertex_colors:
            continue
        
        # Get the active vertex color layer if it exists
        color_layer = mesh.vertex_colors.active
        if color_layer is None:
            return False

        # Convert to numpy for fast processing
        colors = np.array([loop_col.color[:] for loop_col in color_layer.data])

        # Check if all colors are exactly (1.0, 1.0, 1.0, 1.0)
        if not np.allclose(colors, (1.0, 1.0, 1.0, 1.0)):
            return False

    return True  # All vertex colors are white
    
def is_texture_default(context):
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    for obj in selected_meshes:
        mats = [slot.material for slot in obj.material_slots]
        if not len(mats): continue
        if mats[0] is None: continue
        if mats[0].use_backface_culling:
            return False
        for prop in ['scroll_x', 'scroll_y', 'flip_x', 'flip_y', 'clip_x', 'clip_y']:
            if getattr(mats[0], prop, False):
                return False
        if mats[0].blend_mode not in ('OPAQUE', 'SKY'):
            return False
    return True
        
def is_terrain_default(context):
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']        
    for obj in selected_meshes:
        if not obj.collision_data:
            continue
        for flag in dir(SurfaceEnum):
            if not flag.startswith("__"):
                if getattr(obj, flag, False):
                    return False
        for flag in ['magnet', 'strict_spline', 'elevation']:
            if getattr(obj, flag, False):
                return False
    return True

def is_fog_default(context):
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']        
    target_color = mathutils.Color((1.0, 1.0, 1.0))
    for obj in selected_meshes:
        if not obj.collision_data:
            continue
        
        if obj.fog_color != target_color or obj.fog_color_update or obj.fog_range_update or obj.fog_min != 1000 or obj.fog_max != 30000 or obj.fog_clear or obj.skybox_show or obj.skybox_hide:
            return False
    return True

def is_lighting_default(context):
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']        
    target_color = mathutils.Color((1.0, 1.0, 1.0))
    for obj in selected_meshes:
        if not obj.collision_data:
            continue
        
        if obj.lighting_light or obj.lighting_color != target_color or obj.lighting_invert or obj.lighting_flicker or obj.lighting_persistent:
            return False
    return True

def is_loading_default(context):
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']        
    for obj in selected_meshes:
        for val in obj.load_trigger:
            if val != 0:
                return False
    return True

def is_collision_default(context):
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']        
    for obj in selected_meshes:
        if obj.collision_data:
            return False
    return True

def is_visuals_default(context):
    return context.scene.is_texture_default and context.scene.is_v_lighting_default

def all_equal(lst):
    return all(x == lst[0] for x in lst) if lst and len(lst) else True

# MARK: on select
_last_selection = (None, frozenset())
def on_object_selection(scene = None, depsgraph = None):
    global _last_selection, _in_selection_sync

    if scene is None:
        scene = bpy.context.scene

    view_layer = bpy.context.view_layer
    active = view_layer.objects.active if view_layer else None
    active_name = active.name if active else None
    sel = frozenset(obj.name for obj in bpy.context.selected_objects)
    key = (active_name, sel, utils.panel_sync_generation[0])

    if key == _last_selection:
        return

    if _in_selection_sync:
        return

    _in_selection_sync = True
    scene.podblock_syncing = True
    _last_selection = key
    
    try:
        context = scene
        indeterminates = []
        
        selected_objects = set()
        selected_materials = set()
        selected_textures = set()
        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH':
                selected_objects.add(obj)
                mats = [slot.material for slot in obj.material_slots]
                for mat in mats:
                    if mat is None:
                        continue
                    selected_materials.add(mat)
                    if mat is not None and mat.node_tree:
                        for node in mat.node_tree.nodes:
                            if node.type == 'TEX_IMAGE':
                                if node.image is not None:
                                    selected_textures.add(node.image)
                                break
        
        for prop in obj_props:
            val = get_prop_value(prop, indeterminates, selected_objects)
            if val is not None:
                setattr(context, prop, val)
            elif hasattr(context, prop) and isinstance(getattr(context, prop), int):
                setattr(context, prop, False)
            
        # a pointer has no default to fall back on: show the shared light, or none when mixed
        lights = {obj.lighting_light for obj in selected_objects}
        context.lighting_light = next(iter(lights)) if len(lights) == 1 else None
        if len(lights) > 1:
            indeterminates.append('lighting_light')

        for prop in mat_props:
            val = get_prop_value(prop, indeterminates, selected_materials)
            if val is not None:
                setattr(context, prop, val)
            elif hasattr(context, prop) and isinstance(getattr(context, prop), int):
                setattr(context, prop, False)
        
        if len(selected_textures) == 1:
            val = selected_textures.pop()
            setattr(context, 'texture', val)
        elif len(selected_textures):
            setattr(context, 'texture', None)
            indeterminates.append('texture')
        else:
            setattr(context, 'texture', None)
        bpy.context.scene.indeterminates = ",".join(indeterminates)
        
        #TODO: may be a way to avoid these functions using the indeterminate value
        bpy.context.scene.is_v_lighting_default = is_v_lighting_default(bpy.context)
        bpy.context.scene.is_texture_default = is_texture_default(bpy.context)
        bpy.context.scene.is_terrain_default = is_terrain_default(bpy.context)
        bpy.context.scene.is_fog_default = is_fog_default(bpy.context)
        bpy.context.scene.is_lighting_default = is_lighting_default(bpy.context)
        bpy.context.scene.is_loading_default = is_loading_default(bpy.context)
        
        bpy.context.scene.is_visuals_default = is_visuals_default(bpy.context)
        bpy.context.scene.is_collision_default = is_collision_default(bpy.context)
        
        toggle_map = {
            0: "UNCHECKED",
            1: "CHECKED",
            2: "EXED"
        }
        
        context.load_trigger.clear()
        for i, view_layer in enumerate(context.view_layers):
            if i == 0: # skip the working layer
                continue
            if i > 24:
                break
            item = context.load_trigger.add()
            vals = [obj.load_trigger[i-1] for obj in selected_objects]
            
            item.name = view_layer.name + ("*" if not all_equal(vals) else "")
            item.toggle_state = toggle_map[vals[0] if len(vals) and all_equal(vals) else 0]
            
    finally:
        scene.podblock_syncing = False
        _in_selection_sync = False
        screen = bpy.context.screen
        if screen:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

def _subscribe_selection_msgbus():
    bpy.msgbus.clear_by_owner(_msgbus_owner)
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.LayerObjects, 'active'),
        owner=_msgbus_owner,
        args=(),
        notify=on_object_selection,
    )

@bpy.app.handlers.persistent
def _selection_msgbus_load_post(dummy):
    _subscribe_selection_msgbus()

def find_model_collection(context):
    return utils.find_model_collection(context)

def op_with_props(layout, op, text, props={}):
    """Helper to add an operator with dynamic properties."""
    operator = layout.operator(op, text=text)
    for key, value in props.items():
        setattr(operator, key, value)

def help_button(layout, page):
    """A "?" that opens the panel's wiki page (help_pages.HELP_PAGES; tests/test_help_pages.py
    checks every page used here exists in wiki/)."""
    op = layout.operator("view3d.open_url", text="", icon='QUESTION', emboss=False)
    op.url = help_url(URL_WIKI, page)
    op.tooltip = f"Open the wiki: {HELP_PAGES[page]}"

def selected_meshes(context):
    return [obj for obj in context.selected_objects if obj.type == 'MESH']

def hint(layout, *lines, icon='NONE'):
    """Greyed-out explanatory text."""
    col = layout.column(align=True)
    col.enabled = False
    for i, line in enumerate(lines):
        col.label(text=line, icon=icon if i == 0 else 'NONE')


# Global variable to store icons
preview_collections = {}


class SWRPanel:
    """Shared settings for every sidebar panel. help_page names the wiki page the header's "?"
    opens; reset_operator and reset_default add a reset arrow while the selection differs from
    the defaults."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SWE1R Import/Export'
    help_page = None
    reset_operator = None
    reset_default = None

    def draw_header_preset(self, context):
        row = self.layout.row(align=True)
        if self.reset_operator and not getattr(context.scene, self.reset_default, True):
            row.operator(self.reset_operator, text='', emboss=False, icon='LOOP_BACK')
        if self.help_page:
            help_button(row, self.help_page)


# MARK: Info
class SWR_PT_info(SWRPanel, bpy.types.Panel):
    bl_label = "Info"
    bl_idname = "SWR_PT_info"
    bl_order = 0

    def draw_header(self, context):
        self.layout.label(icon='INFO')

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text = NAME)
        for url, tooltip, icon in [(help_url(URL_WIKI, "Home"), "Open the wiki (how-to guides)", None),
                                   (URL_DISCORD, "Ask for help on the SWE1R Discord", "discord"),
                                   (URL_GITHUB, "Report a bug or read the code on GitHub", "github"),
                                   (URL_KOFI, "Support the project on Ko-fi", "kofi")]:
            if icon is None:
                op = row.operator("view3d.open_url", text="", icon = "QUESTION", emboss = False)
            else:
                op = row.operator("view3d.open_url", text="", icon_value=preview_collections["main"][icon].icon_id, emboss = False)
            op.url = url
            op.tooltip = tooltip

        row = layout.row()
        row.label(text = "Version: " + VERSION)


# MARK: Import
class SWR_PT_import(SWRPanel, bpy.types.Panel):
    bl_label = "Import"
    bl_idname = "SWR_PT_import"
    bl_order = 1
    help_page = "Import"

    def draw_header(self, context):
        self.layout.label(icon='IMPORT')

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "import_folder", text = '', full_event=False)
        layout.prop(context.scene, "import_type", text="Type")
        layout.prop(context.scene, "import_model", text="Model")
        row = layout.row()
        row.scale_y = 1.5
        if context.scene.import_progress > 0.0 and context.scene.import_progress < 1.0:
            row.progress(factor = context.scene.import_progress, type = 'BAR', text = context.scene.import_status)
        else:
            row.operator("view3d.import_operator", text="Import")


# MARK: Export
class SWR_PT_export(SWRPanel, bpy.types.Panel):
    bl_label = "Export"
    bl_idname = "SWR_PT_export"
    bl_order = 2
    help_page = "Export"

    def draw_header(self, context):
        self.layout.label(icon='EXPORT')

    def draw(self, context):
        layout = self.layout
        collection = find_model_collection(context)
        if collection is None:
            hint(layout, "Click a model collection", "(e.g. model_1_Trak) or one of", "its objects in the Outliner,", "or make one with Tools > New", icon='INFO')
            return

        layout.label(text = collection.name, icon = 'OUTLINER_COLLECTION')
        layout.prop(context.scene, "export_folder", text="", full_event=False)
        layout.prop(collection, 'export_model', text = "Replaces")
        row = layout.row(align=True)
        row.prop(context.scene, "is_export_model", text="Model", icon='MESH_CUBE', toggle=True)
        row.prop(context.scene, "is_export_texture", text="Texture", icon='MATERIAL', toggle=True)
        row.prop(context.scene, "is_export_spline", text="Spline", icon='CURVE_BEZCURVE', toggle=True)

        row = layout.row()
        row.scale_y = 1.5
        if context.scene.export_progress > 0.0 and context.scene.export_progress < 1.0:
            row.progress(factor = context.scene.export_progress, type = 'BAR', text = context.scene.export_status)
        else:
            row.operator("view3d.export_operator", text="Export")
        if not any([context.scene.is_export_model, context.scene.is_export_texture, context.scene.is_export_spline]):
            row.enabled = False
            hint(layout, "Turn on Model, Texture or Spline")
        elif context.scene.is_export_texture:
            hint(layout, "New textures may need a game restart")

class SWR_PT_export_advanced(SWRPanel, bpy.types.Panel):
    bl_label = "Advanced"
    bl_idname = "SWR_PT_export_advanced"
    bl_parent_id = "SWR_PT_export"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "is_export_separate", text = "Save copy to individual .bin file(s)")
        layout.prop(context.scene, "is_export_debug", text = "Write model debug dump (.txt)")


# MARK: Tools
class SWR_PT_tools(SWRPanel, bpy.types.Panel):
    bl_label = "Tools"
    bl_idname = "SWR_PT_tools"
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}
    help_page = "Tools"

    def draw_header(self, context):
        self.layout.label(icon='TOOL_SETTINGS')

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text = "New", icon = "FILE_NEW")
        row.prop(context.scene, "new_type", text="")
        row.operator("view3d.new_model", text = "", icon = "ADD")

        layout.operator("object.generate_material_assets", text="Export Asset Library", icon='ASSET_MANAGER')

class SWR_PT_display(SWRPanel, bpy.types.Panel):
    bl_label = "Display"
    bl_idname = "SWR_PT_display"
    bl_parent_id = "SWR_PT_tools"
    help_page = "Display"

    def draw(self, context):
        layout = self.layout
        for label, icon, prop, selectable, visible in [("Visuals", 'MATERIAL_DATA', "visible", "visuals_selectable", "visuals_visible"),
                                                       ("Collision", 'MOD_PHYSICS', "collidable", "collision_selectable", "collision_visible")]:
            row = layout.row(align = True)
            row.label(text = label, icon = icon)
            row.prop(context.scene, selectable, toggle = True, text = "", icon = 'RESTRICT_SELECT_OFF' if getattr(context.scene, selectable) else 'RESTRICT_SELECT_ON')
            row.prop(context.scene, visible, toggle = True, text = "", icon = 'HIDE_OFF' if getattr(context.scene, visible) else 'HIDE_ON')
            op = row.operator("view3d.select_by_property", text="Select")
            op.property_name = prop
            op.selectable_flag = selectable


class SWR_UL_load_zones(bpy.types.UIList):
    """The 24 game view layers (zones) and what touching the selected meshes does to each"""

    ICON_MAP = {
        "UNCHECKED": "DECORATE",
        "CHECKED": "HIDE_OFF",
        "EXED": "HIDE_ON"
    }

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            icon_name = self.ICON_MAP.get(item.toggle_state, "QUESTION")
            op = row.operator("my_list.toggle_state", text="", icon=icon_name, emboss = False)
            op.item_index = index
            row.label(text=item.name)


# MARK: Mesh
class SWR_PT_mesh(SWRPanel, bpy.types.Panel):
    bl_label = "Mesh"
    bl_idname = "SWR_PT_mesh"
    bl_order = 4

    @classmethod
    def poll(cls, context):
        return bool(selected_meshes(context))

    def draw_header(self, context):
        self.layout.label(icon='MESH_DATA')

    def draw(self, context):
        meshes = selected_meshes(context)
        text = meshes[0].name if len(meshes) == 1 else f"{len(meshes)} meshes selected"
        self.layout.label(text = text)
        if context.scene.indeterminates:
            hint(self.layout, "* the selection has mixed values")

class MeshSubPanel(SWRPanel):
    bl_parent_id = "SWR_PT_mesh"

class SWR_PT_visuals(MeshSubPanel, bpy.types.Panel):
    bl_label = "Visuals"
    bl_idname = "SWR_PT_visuals"
    help_page = "Visuals"
    reset_operator = 'view3d.reset_visuals'
    reset_default = 'is_visuals_default'

    def draw_header(self, context):
        self.layout.prop(context.scene, 'visible', text = is_indeterminate("visible"))

    def draw(self, context):
        if not context.scene.visible:
            hint(self.layout, "Not drawn in game")

class VisualsSubPanel(SWRPanel):
    bl_parent_id = "SWR_PT_visuals"

    @classmethod
    def poll(cls, context):
        return context.scene.visible

class SWR_PT_vertex_colors(VisualsSubPanel, bpy.types.Panel):
    bl_label = "Vertex Colors"
    bl_idname = "SWR_PT_vertex_colors"
    bl_options = {'DEFAULT_CLOSED'}
    help_page = "Vertex-Colors"
    reset_operator = 'view3d.reset_v_color'
    reset_default = 'is_v_lighting_default'

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, 'light_falloff', text = 'Falloff', slider = True)
        row = layout.row()
        row.label(text = 'Ambient Light')
        row.prop(context.scene, 'ambient_light', text='')
        layout.prop(context.scene, 'ambient_light_intensity', text = 'Ambient Strength', slider = True)
        row = layout.row()
        row.scale_y = 1.5
        row.operator('view3d.bake_vcolors', text='Bake')

class SWR_PT_material(VisualsSubPanel, bpy.types.Panel):
    bl_label = "Material"
    bl_idname = "SWR_PT_material"
    help_page = "Materials"
    reset_operator = 'view3d.reset_texture'
    reset_default = 'is_texture_default'

    def draw(self, context):
        layout = self.layout
        meshes = selected_meshes(context)
        slot_counts = [len(m.material_slots) for m in meshes]
        if max(slot_counts) > 1:
            layout.label(text = "One material per mesh: export splits it", icon = 'ERROR')
            row = layout.row()
            row.enabled = context.active_object in meshes and len(context.active_object.material_slots) > 1
            row.operator("view3d.split_by_material", text = "Split mesh by material")
            return
        if min(slot_counts) == 0:
            layout.operator('view3d.remake_materials', text = "Add material", icon = 'ADD')
            return

        in_sky = any(c.collection_type == '1' for m in meshes for c in m.users_collection)
        modes = {m.material_slots[0].material.blend_mode for m in meshes if m.material_slots[0].material is not None}
        if in_sky:
            hint(layout, "Blend Mode: Sky (automatic in a", "Skybox collection)")
        else:
            row = layout.row()
            row.prop(context.scene, "blend_mode", text = "Blend" + ("*" if len(modes) > 1 else ""))
        row = layout.row()
        row.prop(context.scene, "material_color", text = f'Color{is_indeterminate("material_color")}')
        # only Tinted, Glow and Flat Color (and some Custom setups) draw with Color
        row.enabled = bool(modes & {'TINTED', 'GLOW', 'FLAT', 'CUSTOM'})
        layout.prop(context.scene, 'use_backface_culling', text = f'Backface Culling{is_indeterminate("use_backface_culling")}')
        row = layout.row(align=True)
        row.prop(context.scene, "texture", text = "", placeholder = is_indeterminate("texture", "Mixed"))
        row.operator("view3d.open_image", text="", icon='FILEBROWSER')
        if not context.scene.texture:
            return
        row = layout.row()
        row.label(text = 'Scroll')
        row.prop(context.scene, 'scroll_x', text = f'x{is_indeterminate("scroll_x")}')
        row.prop(context.scene, 'scroll_y', text = f'y{is_indeterminate("scroll_y")}')
        # flip_y/clip_y are the X (U) axis, flip_x/clip_x the Y (V) axis (see Material.make)
        row = layout.row()
        row.label(text = 'Mirror')
        row.prop(context.scene, 'flip_y', text = f'x{is_indeterminate("flip_y")}')
        row.prop(context.scene, 'flip_x', text = f'y{is_indeterminate("flip_x")}')
        row = layout.row()
        row.label(text = 'Clip')
        row.prop(context.scene, 'clip_y', text = f'x{is_indeterminate("clip_y")}')
        row.prop(context.scene, 'clip_x', text = f'y{is_indeterminate("clip_x")}')

class SWR_PT_collision(MeshSubPanel, bpy.types.Panel):
    bl_label = "Collision"
    bl_idname = "SWR_PT_collision"
    help_page = "Collision"
    reset_operator = 'view3d.reset_collidable'
    reset_default = 'is_collision_default'

    def draw_header(self, context):
        self.layout.prop(context.scene, 'collidable', text = is_indeterminate("collidable"))

    def draw(self, context):
        layout = self.layout
        if not context.scene.collidable:
            hint(layout, "Pods pass through it")
        elif not context.scene.collision_data:
            layout.prop(context.scene, "collision_data", text = f"Add surface flags, fog, etc.{is_indeterminate('collision_data')}", icon = "ADD")

class CollisionSubPanel(SWRPanel):
    bl_parent_id = "SWR_PT_collision"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.collidable and context.scene.collision_data

class SWR_PT_surface_flags(CollisionSubPanel, bpy.types.Panel):
    bl_label = "Surface Flags"
    bl_idname = "SWR_PT_surface_flags"
    help_page = "Surface-Flags"
    reset_operator = 'view3d.reset_terrain'
    reset_default = 'is_terrain_default'

    def draw(self, context):
        gameplay = ["Fast", "Slow", "Swst", "Slip", "Lava", "ZOn", "ZOff", "Fall", "NRsp"]
        effects = ["Dust", "Wet", "Swmp", "Snow", "NSnw", "Mirr", "Side"]
        feedback = ["Ruff", "Soft", "Flat"]
        labels = SURFACE_FLAG_LABELS

        row = self.layout.row()
        col = row.column()
        hint(col, "Gameplay")
        for flag in gameplay:
            col.prop(context.scene, flag, text = f"{labels.get(flag, flag)}{is_indeterminate(flag)}")
        hint(col, "Overrides")
        col.prop(context.scene, "magnet", text = f"Magnet{is_indeterminate('magnet')}")
        col.prop(context.scene, "elevation", text = f"Full Raycast{is_indeterminate('elevation')}")
        col.prop(context.scene, "strict_spline", text = f"Spline Fork{is_indeterminate('strict_spline')}")

        col = row.column()
        hint(col, "Effects")
        for flag in effects:
            col.prop(context.scene, flag, text = f"{labels.get(flag, flag)}{is_indeterminate(flag)}")
        hint(col, "Feedback")
        for flag in feedback:
            col.prop(context.scene, flag, text = f"{labels.get(flag, flag)}{is_indeterminate(flag)}")

class SWR_PT_fog(CollisionSubPanel, bpy.types.Panel):
    bl_label = "Fog & Skybox"
    bl_idname = "SWR_PT_fog"
    help_page = "Fog-and-Skybox"
    reset_operator = 'view3d.reset_fog'
    reset_default = 'is_fog_default'

    def draw(self, context):
        layout = self.layout
        hint(layout, "Set when the pod touches these")
        # the game reads the fog start with the color (fog flag 0x1) and the draw distance alone (0x2)
        row = layout.row()
        row.column().prop(context.scene, 'fog_color_update', text = f'Set fog{is_indeterminate("fog_color_update")}')
        col = row.column()
        col.prop(context.scene, 'fog_color', text = "")
        col.prop(context.scene, 'fog_min', text = f'Start{is_indeterminate("fog_min")}', slider = True)
        col.enabled = context.scene.fog_color_update and not context.scene.fog_clear

        row = layout.row()
        row.column().prop(context.scene, 'fog_range_update', text = f'Set draw{is_indeterminate("fog_range_update")}')
        col = row.column()
        col.prop(context.scene, 'fog_max', text = f'Distance{is_indeterminate("fog_max")}', slider = True)
        col.enabled = context.scene.fog_range_update

        layout.prop(context.scene, 'fog_clear', text = f'Clear Fog{is_indeterminate("fog_clear")}', icon = 'SHADERFX')
        row = layout.row()
        row.prop(context.scene, 'skybox_show', text = f'Show Skybox{is_indeterminate("skybox_show")}', icon = 'HIDE_OFF')
        row.prop(context.scene, 'skybox_hide', text = f'Hide Skybox{is_indeterminate("skybox_hide")}', icon = 'HIDE_ON')

class SWR_PT_pod_lighting(CollisionSubPanel, bpy.types.Panel):
    bl_label = "Pod Lighting"
    bl_idname = "SWR_PT_pod_lighting"
    help_page = "Pod-Lighting"
    reset_operator = 'view3d.reset_lighting'
    reset_default = 'is_lighting_default'

    def draw(self, context):
        layout = self.layout
        hint(layout, "Lights the pod while on these")
        layout.prop(context.scene, 'lighting_light', text = "", placeholder = is_indeterminate("lighting_light", "Mixed"))
        layout.prop(context.scene, 'lighting_color', text = f'Ambient Color{is_indeterminate("lighting_color")}')
        row = layout.row(align = True)
        row.prop(context.scene, 'lighting_flicker', text = f'Flicker{is_indeterminate("lighting_flicker")}', toggle = True)
        row.prop(context.scene, 'lighting_invert', text = f'Point{is_indeterminate("lighting_invert")}', toggle = True)
        row.prop(context.scene, 'lighting_persistent', text = f'Persist{is_indeterminate("lighting_persistent")}', toggle = True)

class SWR_PT_load_zones(CollisionSubPanel, bpy.types.Panel):
    bl_label = "Load Zones"
    bl_idname = "SWR_PT_load_zones"
    help_page = "Load-Zones"
    reset_operator = 'view3d.reset_loading'
    reset_default = 'is_loading_default'

    def draw(self, context):
        layout = self.layout
        hint(layout, "Click a zone to cycle: unchanged,", "load on touch, unload on touch")
        layout.template_list("SWR_UL_load_zones", "", context.scene, "load_trigger", context.scene, "load_trigger_index", rows=4)
        row = layout.row()
        row.enabled = len(context.selected_objects) == 1
        row.operator("view3d.preview_load", text = "Preview", icon = 'HIDE_OFF')

class SWR_PT_event_triggers(CollisionSubPanel, bpy.types.Panel):
    bl_label = "Event Triggers"
    bl_idname = "SWR_PT_event_triggers"
    help_page = "Triggers"

    def draw(self, context):
        layout = self.layout
        meshes = selected_meshes(context)
        triggers = [child for mesh in meshes for child in mesh.children if is_trigger(child)]
        if triggers:
            col = layout.column(align = True)
            for trigger in triggers:
                col.label(text = f"{trigger.name}: {type_label(trigger.trigger_id)}", icon = 'CUBE')
        else:
            hint(layout, "No triggers on these meshes")
        layout.operator("view3d.add_trigger", text = "Add event trigger", icon = 'ADD')


# MARK: Trigger
def is_trigger(obj):
    return obj is not None and obj.type == 'EMPTY' and obj.empty_display_type == 'CUBE'

class SWR_PT_trigger(SWRPanel, bpy.types.Panel):
    bl_label = "Event Trigger"
    bl_idname = "SWR_PT_trigger"
    bl_order = 5
    help_page = "Triggers"

    @classmethod
    def poll(cls, context):
        return is_trigger(context.active_object)

    def draw_header(self, context):
        self.layout.label(icon='CUBE')

    def draw(self, context):
        layout = self.layout
        trigger = context.active_object
        row = layout.row(align = True)
        row.prop(trigger, 'trigger_type', text = '')
        number = row.row(align = True)
        number.scale_x = 0.7
        number.prop(trigger, 'trigger_id', text = '')
        entry = TRIGGER_TYPES.get(trigger.trigger_id)
        if entry is not None:
            hint(layout, *textwrap.wrap(entry[1], 38))
        for warning in type_warnings(trigger.trigger_id):
            if warning == "Needs a Target" and trigger.target is not None:
                continue
            serious = warning.startswith(("Crash", "Can crash", "Keep out", "Explodes", "Needs", "Not a known"))
            col = layout.column(align = True)
            for i, line in enumerate(textwrap.wrap(warning, 36)):
                col.label(text = line, icon = ('ERROR' if serious else 'INFO') if i == 0 else 'BLANK1')
        row = layout.row()
        col = row.column()
        col.prop(trigger, "Disabled", text = 'Disabled')
        col.prop(trigger, "IgnoreAI", text = 'Ignore AI')
        col.prop(trigger, "SpeedCheck150", text = '>150 Speed')
        col = row.column()
        col.prop(trigger, "SkipLap1", text = 'Skip Lap 1')
        col.prop(trigger, "SkipLap2", text = 'Skip Lap 2')
        col.prop(trigger, "SkipLap3", text = 'Skip Lap 3')
        layout.prop(trigger, 'target')
        if trigger.parent is None or trigger.parent.type != 'MESH':
            layout.label(text = "Parent this to a collidable mesh", icon = 'ERROR')
        layout.prop(trigger, 'trigger_settings', text = 'Settings')


# MARK: Spline
class SWR_PT_spline(SWRPanel, bpy.types.Panel):
    bl_label = "Spline"
    bl_idname = "SWR_PT_spline"
    bl_order = 6
    help_page = "Splines"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'CURVE' and obj.data.splines.active is not None

    def draw_header(self, context):
        self.layout.label(icon='CURVE_BEZCURVE')

    def draw(self, context):
        layout = self.layout
        spline = context.active_object.data.splines.active
        row = layout.row()
        row.column().operator("curve.select_first_spline_point", text = "Select spawn", icon = "SELECT_SET")
        column = row.column()
        column.enabled = spline.use_cyclic_u and context.mode == 'EDIT_CURVE'
        column.operator("view3d.reconstruct_spline", text = "Set spawn", icon = "TRACKING")
        if not column.enabled:
            hint(layout, "Set spawn: cyclic spline in Edit Mode")
        layout.operator("view3d.invert_spline", text = "Invert", icon='ARROW_LEFTRIGHT')
        row = layout.row()
        row.prop(spline, 'use_cyclic_u', text = "Cyclic")
        if context.space_data is not None and context.space_data.type == 'VIEW_3D':
            row.prop(context.space_data.overlay, "show_curve_normals", text = "Show direction")
        if not spline.use_cyclic_u:
            hint(layout, "Not cyclic: point-to-point track")


# MARK: Light
class SWR_PT_light(SWRPanel, bpy.types.Panel):
    bl_label = "Light"
    bl_idname = "SWR_PT_light"
    bl_order = 7
    help_page = "Lights"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'LIGHT'

    def draw_header(self, context):
        self.layout.label(icon='LIGHT')

    def draw(self, context):
        layout = self.layout
        light = context.active_object.data
        layout.prop(light, "color", text = "Color")
        layout.prop(light, 'LStr', text = 'Light Streak')
        hint(layout, "Pod lights are set on collision:", "Mesh > Collision > Pod Lighting")


panel_classes = (
    SWR_PT_info,
    SWR_PT_import,
    SWR_PT_export,
    SWR_PT_export_advanced,
    SWR_PT_tools,
    SWR_PT_display,
    SWR_UL_load_zones,
    SWR_PT_mesh,
    SWR_PT_visuals,
    SWR_PT_vertex_colors,
    SWR_PT_material,
    SWR_PT_collision,
    SWR_PT_surface_flags,
    SWR_PT_fog,
    SWR_PT_pod_lighting,
    SWR_PT_load_zones,
    SWR_PT_event_triggers,
    SWR_PT_trigger,
    SWR_PT_spline,
    SWR_PT_light,
)

def register():
    # Load custom icons
    pcoll = previews.new()
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    icon_files = [
        ("discord", "discord.png"),
        ("github", "github.png"),
        ("kofi", "kofi.png"),
        ("indeterminate", "indeterminate.png")
    ]

    for name, file in icon_files:
        pcoll.load(name, os.path.join(icons_dir, file), 'IMAGE')
    preview_collections["main"] = pcoll
    if on_object_selection not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(on_object_selection)
    if _selection_msgbus_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_selection_msgbus_load_post)
    _subscribe_selection_msgbus()
    for cls in panel_classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.podblock_syncing = bpy.props.BoolProperty(name="PodBlock internal syncing", default = False, options={'HIDDEN', 'SKIP_SAVE'})

def unregister():
    if on_object_selection in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(on_object_selection)
    if _selection_msgbus_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_selection_msgbus_load_post)
    bpy.msgbus.clear_by_owner(_msgbus_owner)
    for cls in reversed(panel_classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.podblock_syncing

    # Remove icons
    for pcoll in preview_collections.values():
        previews.remove(pcoll)
    preview_collections.clear()
