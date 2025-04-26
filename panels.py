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
from .swe1r.model_list import model_list
from .swe1r.modelblock import SurfaceEnum, Material
from .operators import *
from .constants import *
from . import bl_info
import os
from bpy.utils import previews

models = [(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(model_list)]
classes = []    

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

def get_obj_prop_value(context, prop_name, indeterminates):
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    if not selected_meshes:
        return None
    values = set()
    for obj in selected_meshes:
        if prop_name in obj:
            if isinstance(obj[prop_name], Color):
                frozen_copy = obj[prop_name].copy()
                frozen_copy.freeze()
                values.add(frozen_copy)
            else:
                values.add(obj[prop_name])
        else:
            values.add(None)
    if len(values) == 1:
        return values.pop()  # All values are the same
    elif len(values):
        indeterminates.append(prop_name)
    return get_default(bpy.context.scene, prop_name)

def get_mat_prop_value(context, prop_name, indeterminates):
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    if not selected_meshes:
        return None
    mats = []
    for obj in selected_meshes:
        if len(obj.material_slots):
            mats.append(obj.material_slots[0].material)
    values = set()
    for mat in mats:
        if prop_name == "use_backface_culling" or prop_name not in mat:
            continue
        if isinstance(mat[prop_name], Color):
            frozen_copy = mat[prop_name].copy()
            frozen_copy.freeze()
            values.add(frozen_copy)
        else:
            values.add(mat[prop_name])
    if len(values) == 1:
        return values.pop()  # All values are the same
    elif len(values):
        indeterminates.append(prop_name)
    return get_default(bpy.context.scene, prop_name)

obj_props = ['visible', 
            'lighting_color', 
            'lighting_light',
            'visible',
            'collidable',
            'collision_data',
            'magnet',
            'strict_spline',
            'elevation',
            'lighting_light',
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
            'skybox_hide',
            'load_trigger']

for flag in dir(SurfaceEnum):
    if not flag.startswith("__"):
        obj_props.append(flag)
        
mat_props = [
    'use_backface_culling',
    'material_color',
    'scroll_x',
    'scroll_y',
    'flip_x',
    'flip_y',
    'clip_x',
    'clip_y',
    'transparent'
]

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
        
        # Get the active vertex color layer
        color_layer = mesh.vertex_colors.active.data

        # Convert to numpy for fast processing
        colors = np.array([loop_col.color[:] for loop_col in color_layer])

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
        for prop in [prop for prop in mat_props if prop != "use_backface_culling"]:
            if prop in mats[0] and mats[0][prop] :
                return False
    return True
        
def is_terrain_default(context):
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']        
    for obj in selected_meshes:
        if not obj.collision_data:
            continue
        for flag in dir(SurfaceEnum):
            if not flag.startswith("__"):
                if flag in obj and obj[flag]:
                    return False
        for flag in ['magnet', 'strict_spline', 'elevation']:
            if flag in obj and obj[flag]:
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
@bpy.app.handlers.persistent
def on_object_selection(context):
    indeterminates = []
    for prop in obj_props:
        val = get_obj_prop_value(bpy.context, prop, indeterminates)
        if val is not None and prop != 'lighting_light':
            context[prop] = val
        elif prop in context and isinstance(context[prop], int):
            context[prop] = False
        
    for prop in mat_props:
        val = get_mat_prop_value(bpy.context, prop, indeterminates)
        if val is not None:
            context[prop] = val
        elif prop in context and isinstance(context[prop], int):
            context[prop] = False
        
    textures = set()
    for obj in bpy.context.selected_objects:
        if obj.type == 'MESH':
            mats = [slot.material for slot in obj.material_slots]
            for mat in mats:
                if mat is not None and mat.node_tree:
                    for node in mat.node_tree.nodes:
                        if node.type == 'TEX_IMAGE':
                            textures.add(node.image)
                            break
    if len(textures) == 1:
        val = textures.pop()
        context['texture'] = val
    elif len(textures):
        context['texture'] = None
        indeterminates.append('texture')
    else:
        context['texture'] = None
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
    
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    context.load_trigger.clear()
    for i, view_layer in enumerate(context.view_layers):
        if i == 0: # skip the working layer
            continue
        if i > 24:
            break
        item = context.load_trigger.add()
        vals = [obj.load_trigger[i-1] for obj in selected_meshes]
        
        item.name = view_layer.name + ("*" if not all_equal(vals) else "")
        item.toggle_state = toggle_map[vals[0] if len(vals) and all_equal(vals) else 0]

def op_with_props(layout, op, text, props={}):
    """Helper to add an operator with dynamic properties."""
    operator = layout.operator(op, text=text)
    for key, value in props.items():
        setattr(operator, key, value)

class InfoPanel(bpy.types.Panel):
    bl_label = "Info"
    bl_idname = "PT_InfoPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    
    bl_category = 'SWE1R Import/Export'
    
    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='INFO')
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text = bl_info['name'])
        row.operator("view3d.open_url", text="", icon = "QUESTION", emboss = False).url = URL_WIKI
        row.operator("view3d.open_url", text="", icon_value=preview_collections["main"]["discord"].icon_id, emboss = False).url = URL_DISCORD
        row.operator("view3d.open_url", text="", icon_value=preview_collections["main"]["github"].icon_id, emboss = False).url = URL_GITHUB
        row.operator("view3d.open_url", text="", icon_value=preview_collections["main"]["kofi"].icon_id, emboss = False).url = URL_KOFI
        
        row = layout.row()
        row.label(text = "Version: " + ".".join(map(str, bl_info['version'])))
        row.operator("view3d.open_url", text="Update").url = ""
        
        
# Global variable to store icons
preview_collections = {}

# MARK: Import
class ImportPanel(bpy.types.Panel):
    bl_label = "Import"
    bl_idname = "PT_ImportPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    
    bl_category = 'SWE1R Import/Export'
    
    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='IMPORT')
    
    def draw(self, context):
        layout = self.layout
        
        # Import
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
class ExportPanel(bpy.types.Panel):
    bl_label = "Export"
    bl_idname = "PT_ExportPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SWE1R Import/Export'
    
    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='EXPORT')
    
    def draw(self, context):
        layout = self.layout
            
        collection = bpy.context.view_layer.active_layer_collection
        if collection:
            collection = collection.collection
            
        # Export
        layout.prop(context.scene, "export_folder", text="", full_event=False)
        layout.prop(collection, 'export_model', text = "Model")
        row = layout.row(align=True)
        row.prop(context.scene, "is_export_model", text="Model", icon='MESH_CUBE', toggle=True, icon_only=True)
        row.prop(context.scene, "is_export_texture", text="Texture", icon='MATERIAL', toggle=True, icon_only=True)
        row.prop(context.scene, "is_export_spline", text="Spline", icon='CURVE_BEZCURVE', toggle=True, icon_only=True)
        
        if context.scene.is_export_texture:
            row = layout.row()
            row.label(text = "New custom textures may require game restart")
            row.enabled = False
            
        layout.prop(context.scene, "is_export_separate", text = "Save copy to individual .bin file(s)")
        row = layout.row()
            
            
        row.scale_y = 1.5
        if context.scene.export_progress > 0.0 and context.scene.export_progress < 1.0:
            row.progress(factor = context.scene.export_progress, type = 'BAR', text = context.scene.export_status)
        else:
            row.operator("view3d.export_operator", text="Export")
        
        
        if not any([context.scene.is_export_model, context.scene.is_export_texture, context.scene.is_export_spline]) or collection.collection_type != "MODEL":
            row.enabled = False
            if collection.collection_type != "MODEL":
                row = layout.row()
                row.label(text = "Please select a model collection")

# MARK: Tools   
class ToolPanel(bpy.types.Panel):
    bl_label = "Tools"
    bl_idname = "PT_ToolPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SWE1R Import/Export'
    
    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='TOOL_SETTINGS')
    
    def draw(self, context):
        layout = self.layout
        box = layout.box()
        
        row = box.row()
        row.label(text = "New", icon = "FILE_NEW")
        row.prop(context.scene, "new_type", text="")
        row.operator("view3d.new_model", text = "", icon = "ADD")
        
        box = layout.box()
        row = box.row(align = True)
        row.label(text = "Visuals", icon = 'MATERIAL_DATA')

        row.prop(context.scene, "visuals_selectable", toggle =True, text = "", icon = 'RESTRICT_SELECT_OFF' if context.scene.visuals_selectable else 'RESTRICT_SELECT_ON') 
        row.prop(context.scene, "visuals_visible", toggle=True, text = "", icon = 'HIDE_OFF' if context.scene.visuals_visible else 'HIDE_ON')
        op = row.operator("view3d.select_by_property", text="Select")
        op.property_name = "visible"
        op.selectable_flag = "visuals_selectable"
            
        box = layout.box()
        row = box.row(align = True)
        row.label(text = "Collision", icon = 'MOD_PHYSICS')
        
        row.prop(context.scene, "collision_selectable", toggle =True, text = "", icon = 'RESTRICT_SELECT_OFF' if context.scene.collision_selectable else 'RESTRICT_SELECT_ON') 
        row.prop(context.scene, "collision_visible", toggle=True, text = "", icon = 'HIDE_OFF' if context.scene.collision_visible else 'HIDE_ON')
        op = row.operator("view3d.select_by_property", text="Select")
        op.property_name = "collidable"
        op.selectable_flag = "collision_selectable"
        

def section_header(context, layout, operator, default, expanded, name, icon):
    row = layout.row()
    subrow = row.row()
    subrow.alignment = 'LEFT'
    subrow.operator("view3d.open_url", text=name, emboss=False, icon = icon)
    subrow = row.row()
    subrow.alignment = 'RIGHT'
    if default not in context.scene or not context.scene[default]:
        subrow.operator(operator, text='', emboss=False, icon='LOOP_BACK')
    
    icon = 'DOWNARROW_HLT' if expanded in context.scene and context.scene[expanded] else 'RIGHTARROW'
    subrow.prop(context.scene, expanded, icon = icon, text = '', emboss = False)
    
    
class MY_UL_CustomList(bpy.types.UIList):
    
    ICON_MAP = {
        "UNCHECKED": "DECORATE",
        "CHECKED": "HIDE_OFF",
        "EXED": "HIDE_ON"
    }
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            
            # Toggle button using the enum's icon
            icon_name = self.ICON_MAP.get(item.toggle_state, "QUESTION")
            op = row.operator("my_list.toggle_state", text="", icon=icon_name, emboss = False)
            op.item_index = index  # Pass index to operator
            
            row.label(text=item.name)  # Display the item name

# MARK: Selected
class SelectedPanel(bpy.types.Panel):
    bl_label = "Selected"
    bl_idname = "PT_SelectedPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SWE1R Import/Export'
 
    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='RESTRICT_SELECT_OFF')
 
    def draw(self, context):
        layout = self.layout

        collection = False
        spline = False
        mesh = False
        light = False
        trigger = False
        
        collection = bpy.context.collection
        
        if not context.selected_objects and not collection:
            layout.label(text = "Select an object/spline to edit its properties")
            layout.label(text = "Select a collection to export it as a model")
            return
        
        # Check if any of them are collections
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                mesh = True
            if obj.type == 'CURVE':
                spline = obj.data.splines.active
            if obj.type == 'LIGHT':
                light = obj.data
            if obj.type == 'EMPTY' and obj.empty_display_type == 'CUBE':
                trigger = obj
                
        if mesh:
            parent_box = layout.box()            
            row = parent_box.row()
            row.scale_y = 1.5
            row.prop(context.scene, 'visible', text = f'Visible{is_indeterminate("visible")}')
            if not context.scene.is_visuals_default:
                row.operator('view3d.reset_visuals', text='', emboss=False, icon='LOOP_BACK')
            if context.scene.visible:
                # MARK: baked lighting
                box = parent_box.box()
                section_header(context, box, 'view3d.reset_v_color', 'is_v_lighting_default', 'lights_expanded', 'Vertex Colors', 'VPAINT_HLT')
                if context.scene.lights_expanded:
                    row = box.row()
                    row.prop(context.scene, 'light_falloff', text = 'Falloff', slider = True)
                    row = box.row()
                    row.label(text = 'Ambient Light')
                    row.prop(context.scene, 'ambient_light', text='')
                    row = box.row()
                    row.scale_y = 1.5
                    row.operator('view3d.bake_vcolors', text='Bake')

                # MARK: material
                box = parent_box.box()
                section_header(context, box, 'view3d.reset_texture', 'is_texture_default', 'textures_expanded', 'Material', 'MATERIAL')                
                mats = [slot.material for slot in obj.material_slots]
                if context.scene.textures_expanded:
                    if len(mats) > 1:
                        row = box.row()
                        row.label("Only one material per mesh is supported")
                        row = box.row()
                        row.operator("view3d.reset_visuals", text = "Split mesh by material")
                    elif len(mats):
                        row = box.row()
                        row.prop(context.scene, "material_color", text = f'Base color{is_indeterminate("material_color")}')
                        row = box.row()
                        row.prop(context.scene, 'use_backface_culling', text = f'Backface Culling{is_indeterminate("use_backface_culling")}')
                        row = box.row(align=True)
                        row.prop(context.scene, "texture", text = "", placeholder = is_indeterminate("texture", "Mixed"))
                        row.operator("view3d.open_image", text="", icon='FILEBROWSER')
                        if context.scene.texture:
                            row = box.row()
                            row.prop(context.scene, 'transparent', text = f'Transparent{is_indeterminate("transparent")}')
                            row = box.row()
                            row.label(text = 'Scroll')
                            row.prop(context.scene, 'scroll_x', text = f'x{is_indeterminate("scroll_x")}')
                            row.prop(context.scene, 'scroll_y', text = f'y{is_indeterminate("scroll_y")}')
                            row= box.row()
                            row.label(text = 'Mirror')
                            row.prop(context.scene, 'flip_x', text = f'x{is_indeterminate("flip_x")}')
                            row.prop(context.scene, 'flip_y', text = f'y{is_indeterminate("flip_y")}')
                            row= box.row()
                            row.label(text = 'Clip')
                            row.prop(context.scene, 'clip_x', text = f'x{is_indeterminate("clip_x")}')
                            row.prop(context.scene, 'clip_y', text = f'y{is_indeterminate("clip_y")}')
                    else:
                        row = box.row()
                        row.operator('view3d.bake_vcolors', text = "Add material")
            
            parent_box = layout.box()
            row = parent_box.row()
            row.scale_y = 1.5
            
            row.prop(context.scene, 'collidable', text= f"Collidable{is_indeterminate('collidable')}")
                
            if context.scene.collidable:
                if not context.scene.is_collision_default:
                    row.operator("view3d.reset_collidable", text = "", emboss = False, icon = 'LOOP_BACK')
               
                if not context.scene.collision_data:
                    row = parent_box.row()
                    row.prop(context.scene, "collision_data", text = f"Add surface tags, fog, etc.{is_indeterminate('collision_data')}",icon = "ADD")
                elif context.scene.collidable:
                    
                    # MARK: terrain
                    
                    box = parent_box.box()
                    section_header(context, box, 'view3d.reset_terrain', 'is_terrain_default', 'flags_expanded', 'Terrain Flags', 'AUTO')                
                    if context.scene.flags_expanded:                        
                        gameplay = ["Fast", "Slow", "Swst", "Slip", "Lava", "ZOn", "ZOff", "Fall", "NRsp"]
                        effects = ["Dust", "Wet", "Swmp", "Snow", "NSnw", "Mirr", "Side"]
                        feedback = ["Ruff", "Soft", "Flat"]
                        
                        row = box.row()
                        col = row.column()
                        for flag in gameplay:
                            col.prop(context.scene, flag, text = f"{flag}{is_indeterminate(flag)}")
                        
                        r = col.row()
                        r.label(text = "")
                        r.scale_y = 0.5
                        r = col.row()
                        r.prop(context.scene, "magnet", text = is_indeterminate('magnet'), icon = 'SNAP_ON')
                        r.prop(context.scene, "strict_spline", text = is_indeterminate('strict_spline'), icon = 'SEQ_LUMA_WAVEFORM')
                        r.prop(context.scene, "elevation", text = is_indeterminate('elevation'), icon = 'MOD_DISPLACE')
                            
                        col = row.column()
                        for flag in effects:
                            col.prop(context.scene, flag, text = f"{flag}{is_indeterminate(flag)}")
                            
                        r = col.row()
                        r.label(text = "")
                        r.scale_y = 0.5
                        for flag in feedback:
                            col.prop(context.scene, flag, text = f"{flag}{is_indeterminate(flag)}")
                    
                    # MARK: fog
                    
                    box = parent_box.box()
                    section_header(context, box, 'view3d.reset_fog', 'is_fog_default', 'fog_expanded', 'Level Fog', 'FORCE_FORCE')
                    if context.scene.fog_expanded:
                        row = box.row()
                        col = row.column()
                        col.prop(context.scene, 'fog_color_update', text = f'Set color{is_indeterminate("fog_color_update")}')
                        col = row.column()
                        col.prop(context.scene, 'fog_color', text = "")
                        col.enabled = context.scene.fog_color_update
                        
                        row = box.row()
                        col = row.column()
                        col.prop(context.scene, 'fog_range_update', text = f'Set range{is_indeterminate("fog_range_update")}')
                        col = row.column()
                        col.prop(context.scene, 'fog_min', text = f'Min{is_indeterminate("fog_min")}', slider = True)
                        col.prop(context.scene, 'fog_max', text = f'Max{is_indeterminate("fog_max")}', slider = True)
                        col.enabled = context.scene.fog_range_update
                        
                        row = box.row()
                        row.prop(context.scene, 'fog_clear', text = f'Clear Fog{is_indeterminate("fog_clear")}', icon = 'SHADERFX')
                        row = box.row()
                        row.prop(context.scene, 'skybox_show', text = f'Show Skybox{is_indeterminate("skybox_show")}', icon = 'HIDE_OFF')
                        row.prop(context.scene, 'skybox_hide', text = f'Hide Skybox{is_indeterminate("skybox_hide")}', icon = 'HIDE_ON')
                        
                    # MARK: lighting
                    
                    box = parent_box.box()
                    section_header(context, box, 'view3d.reset_lighting', 'is_lighting_default', 'lighting_expanded', 'Pod Lighting', 'LIGHT_SUN')                
                    if context.scene.lighting_expanded:
                        row = box.row()
                        row.prop(context.scene, 'lighting_light', text = "", placeholder = is_indeterminate("lighting_light", "Mixed"))
                        row = box.row()
                        row.prop(context.scene, 'lighting_color', text = f'Ambient Color{is_indeterminate("lighting_color")}')
                        row = box.row(align = True)
                        row.prop(context.scene, 'lighting_flicker', text = f'Flicker{is_indeterminate("lighting_flicker")}', toggle = True)
                        row.prop(context.scene, 'lighting_invert', text = f'Invert{is_indeterminate("lighting_invert")}', toggle = True)
                        row.prop(context.scene, 'lighting_persistent', text = f'Persist{is_indeterminate("lighting_persistent")}', toggle = True)
                    
                    # MARK: loading
                    
                    box = parent_box.box()
                    section_header(context, box, 'view3d.reset_loading', 'is_loading_default', 'trigger_expanded', 'Load Trigger', 'MOD_BUILD')                
                    if context.scene.trigger_expanded:
                        row = box.row()
                        # Scrolling list
                        row.template_list("MY_UL_CustomList", "", context.scene, "load_trigger", context.scene, "load_trigger_index", rows=4)
                        row = box.row()
                        row.enabled = len(context.selected_objects) == 1
                        row.operator("view3d.preview_load", text = "Preview", icon = 'HIDE_OFF')
                        
                    row = parent_box.row()
                    row.enabled = len(context.selected_objects) == 1
                    row.operator("view3d.add_trigger", text = "Add event trigger", icon = 'ADD')
                
            if context.scene.indeterminates:
                row = layout.row()
                row.label(text = "*Selection contains mixed values")
                row.enabled = False
                
        elif spline:
            # MARK: spline
            row = layout.row()
            column = row.column()   
            column.operator("curve.select_first_spline_point", text = "Select spawn", icon = "SELECT_SET")
            column = row.column()
            column.enabled = spline.use_cyclic_u and context.mode == 'EDIT_CURVE'
            column.operator("view3d.reconstruct_spline", text = "Set spawn", icon = "TRACKING" )
            layout.operator("view3d.invert_spline", text = "Invert", icon='ARROW_LEFTRIGHT')
            row = layout.row()
            row.prop(spline, 'use_cyclic_u', text = "Cyclic")
            row.prop(context.space_data.overlay, "show_curve_normals", text = "Show direction")
            
        elif light:
            layout.prop(light, "color", text = "Color")
            layout.prop(light, 'LStr', text = 'Light Streak')
            
        elif trigger:
            row = layout.row()
            col = row.column()
            col.prop(trigger, "Disabled", text = 'Disabled')
            col.prop(trigger, "IgnoreAI", text = 'Ignore AI')
            col.prop(trigger, "SpeedCheck150", text = '>150 Speed')
            col = row.column()
            col.prop(trigger, "SkipLap1", text = 'Skip Lap 1')
            col.prop(trigger, "SkipLap2", text = 'Skip Lap 2')
            col.prop(trigger, "SkipLap3", text = 'Skip Lap 3')
            row = layout.row()
            row.prop(trigger, 'trigger_id', text = 'ID')
            row.prop(trigger, 'trigger_settings', text = 'Settings')
            layout.prop(trigger, 'target')
            
        elif collection:
            
            layout = self.layout
            if collection.collection_type != "MODEL":
                row = layout.row()
                row.label(text = "Please select a model collection")
                return
                
            # Export
            layout.prop(context.scene, "export_folder", text="", full_event=False)
            layout.prop(collection, 'export_model', text = "Model")
            row = layout.row(align=True)
            row.prop(context.scene, "is_export_model", text="Model", icon='MESH_CUBE', toggle=True, icon_only=True)
            row.prop(context.scene, "is_export_texture", text="Texture", icon='MATERIAL', toggle=True, icon_only=True)
            row.prop(context.scene, "is_export_spline", text="Spline", icon='CURVE_BEZCURVE', toggle=True, icon_only=True)
            
            if context.scene.is_export_texture:
                row = layout.row()
                row.label(text = "New custom textures may require game restart")
                row.enabled = False
                
            layout.prop(context.scene, "is_export_separate", text = "Save copy to individual .bin file(s)")
            row = layout.row()
                
            row.scale_y = 1.5
            if context.scene.export_progress > 0.0 and context.scene.export_progress < 1.0:
                row.progress(factor = context.scene.export_progress, type = 'BAR', text = context.scene.export_status)
            else:
                row.operator("view3d.export_operator", text="Export")
            
            if not any([context.scene.is_export_model, context.scene.is_export_texture, context.scene.is_export_spline]) or collection.collection_type != "MODEL":
                row.enabled = False
                if collection.collection_type != "MODEL":
                    row = layout.row()
                    row.label(text = "Please select a model collection")

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
    bpy.app.handlers.depsgraph_update_post.append(on_object_selection)
    bpy.utils.register_class(InfoPanel)
    bpy.utils.register_class(ImportPanel)
    bpy.utils.register_class(MY_UL_CustomList)
    bpy.utils.register_class(ToolPanel)
    bpy.utils.register_class(SelectedPanel)
    
def unregister():
    bpy.app.handlers.depsgraph_update_post.remove(on_object_selection)
    bpy.utils.unregister_class(InfoPanel)
    bpy.utils.unregister_class(ImportPanel)
    bpy.utils.unregister_class(MY_UL_CustomList)
    bpy.utils.unregister_class(ToolPanel)
    bpy.utils.unregister_class(SelectedPanel)
    
    # Remove icons
    for pcoll in preview_collections.values():
        previews.remove(pcoll)
    preview_collections.clear()
