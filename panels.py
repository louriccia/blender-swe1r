
from .swr_import import *
from .swr_export import *
from .popup import *
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
    values = {getattr(mat, prop_name, None) for mat in mats}
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
            'skybox_hide']

for flag in dir(SurfaceEnum):
    if not flag.startswith("__"):
        obj_props.append(flag)
        
mat_props = [
    'use_backface_culling',
    'scroll_x',
    'scroll_y',
    'flip_x',
    'flip_y'
]

def is_indeterminate(prop, text = ""):
    indeterminates = bpy.context.scene.indeterminates
    is_ind = prop in indeterminates.split(",")
    if not is_ind:
        return ""
    if text:
        return text
    return "*"

@bpy.app.handlers.persistent
def on_object_selection(context):
    indeterminates = []
    for prop in obj_props:
        val = get_obj_prop_value(bpy.context, prop, indeterminates)
        context[prop] = val
        
    for prop in mat_props:
        val = get_mat_prop_value(bpy.context, prop, indeterminates)
        context[prop] = val
        
    textures = set()
    for obj in bpy.context.selected_objects:
        if obj.type == 'MESH':
            mats = [slot.material for slot in obj.material_slots]
            for mat in mats:
                if mat.node_tree:
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
        icon = 'DOWNARROW_HLT' if context.scene.new_expanded else 'RIGHTARROW'
        row.prop(context.scene, "new_type", text="")
        row.operator("view3d.new_model", text = "", icon = "ADD")
        
        box = layout.box()
        row = box.row(align = True)
        row.label(text = "Visuals", icon = 'MATERIAL_DATA')
        icon = 'DOWNARROW_HLT' if context.scene.visuals_expanded else 'RIGHTARROW'
        
        # if context.scene.visuals_expanded:
        #     row.prop(context.scene, "visuals_expanded", icon = icon, text = "", emboss = False)
            
        #     row = box.row()
        #     row.prop(context.scene, "visuals_selectable", toggle =True, text = "", icon = 'RESTRICT_SELECT_OFF' if context.scene.visuals_selectable else 'RESTRICT_SELECT_ON') 
        #     row.prop(context.scene, "visuals_visible", toggle=True, text = "", icon = 'HIDE_OFF' if context.scene.visuals_visible else 'HIDE_ON')
        #     row.operator("view3d.select_visible", text = "Select")
        # else:
        row.prop(context.scene, "visuals_selectable", toggle =True, text = "", icon = 'RESTRICT_SELECT_OFF' if context.scene.visuals_selectable else 'RESTRICT_SELECT_ON') 
        row.prop(context.scene, "visuals_visible", toggle=True, text = "", icon = 'HIDE_OFF' if context.scene.visuals_visible else 'HIDE_ON')
        row.operator("view3d.select_visible", text = "Select")
        #row.prop(context.scene, "visuals_expanded", icon = icon, text = "", emboss = False)
            
        box = layout.box()
        row = box.row(align = True)
        icon = 'DOWNARROW_HLT' if context.scene.collision_expanded else 'RIGHTARROW'
        row.label(text = "Collision", icon = 'MOD_PHYSICS')
        
        # if context.scene.collision_expanded:
        #     row.prop(context.scene, "collision_expanded", icon = icon, text = "", emboss = False)
        
        #     row = box.row()
        #     row.prop(context.scene, "collision_selectable", toggle =True, text = "", icon = 'RESTRICT_SELECT_OFF' if context.scene.collision_selectable else 'RESTRICT_SELECT_ON') 
        #     row.prop(context.scene, "collision_visible", toggle=True, text = "", icon = 'HIDE_OFF' if context.scene.collision_visible else 'HIDE_ON')
        #     row.operator("view3d.select_collidable", text = "Select")
        # else:
            
        row.prop(context.scene, "collision_selectable", toggle =True, text = "", icon = 'RESTRICT_SELECT_OFF' if context.scene.collision_selectable else 'RESTRICT_SELECT_ON') 
        row.prop(context.scene, "collision_visible", toggle=True, text = "", icon = 'HIDE_OFF' if context.scene.collision_visible else 'HIDE_ON')
        row.operator("view3d.select_collidable", text = "Select")
            #row.prop(context.scene, "collision_expanded", icon = icon, text = "", emboss = False)
        
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
        
        if not context.selected_objects:
            layout.label(text = "Select an object to edit its properties")
            return

        spline = False
        mesh = False
        light = False
        trigger = False
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
            if context.scene.visible:
                row.operator("view3d.v_color", text="", emboss=False, icon = 'LOOP_BACK') # TODO: formalize reset fn

                # baked lighting panel
                
                box = parent_box.box()
                row = box.row()
                row.label(text='Baked Lighting', icon='LIGHT_SUN')
                icon = 'DOWNARROW_HLT' if context.scene.lights_expanded else 'RIGHTARROW'
                row.operator('view3d.bake_vcolors', text='', emboss=False, icon='LOOP_BACK')
                row.prop(context.scene, 'lights_expanded', icon = icon, text = '', emboss = False)

                if context.scene.lights_expanded:
                    row = box.row()
                    row.prop(context.scene, 'light_falloff', text = 'Falloff', slider = True)
                    row = box.row()
                    row.label(text = 'Ambient Light')
                    row.prop(context.scene, 'ambient_light', text='')
                    row = box.row()
                    row.scale_y = 1.5
                    row.operator('view3d.bake_vcolors', text='Bake')
                    #row.operator('view3d.bake_vcolors_clear', text='', icon='TRASH', emboss=False)

                # texture panel

                box = parent_box.box()
                row = box.row()
                row.label(text = "Texture", icon = "TEXTURE")
                icon = "DOWNARROW_HLT" if context.scene.textures_expanded else "RIGHTARROW"
                #row.operator('', text='', emboss=False, icon='LOOP_BACK')
                row.prop(context.scene, "textures_expanded", icon = icon, text = "", emboss = False)
                mats = [slot.material for slot in obj.material_slots]
                
                if context.scene.textures_expanded:
                    if len(mats):
                        row = box.row(align=True)
                        row.prop(context.scene, "texture", text = "", placeholder = is_indeterminate("texture", "Mixed"))
                        row.operator("view3d.open_image", text="", icon='FILEBROWSER')
                        row = box.row()
                        row.prop(context.scene, 'use_backface_culling', text = f'Backface Culling{is_indeterminate("use_backface_culling")}')
                        row = box.row()
                        row.label(text = 'Scroll')
                        row.prop(context.scene, 'scroll_x', text = f'x{is_indeterminate("scroll_x")}')
                        row.prop(context.scene, 'scroll_y', text = f'y{is_indeterminate("scroll_y")}')
                        row= box.row()
                        row.label(text = 'Flip')
                        row.prop(context.scene, 'flip_x', text = f'x{is_indeterminate("flip_x")}')
                        row.prop(context.scene, 'flip_y', text = f'y{is_indeterminate("flip_y")}')
                        row = box.row()
                        row.operator('view3d.bake_vcolors', text='Apply')
                    else:
                        row = box.row()
                        row.operator('material.new', text = "Add material")
            
            parent_box = layout.box()
            row = parent_box.row()
            row.scale_y = 1.5
            
            row.prop(context.scene, 'collidable', text= f"Collidable{is_indeterminate('collidable')}")
                
            if context.scene.collidable:
                if context.scene.collision_data:
                    row.operator("view3d.remove_collision_data", text = "", emboss = False, icon = 'LOOP_BACK')
               
                if not context.scene.collision_data:
                    row = parent_box.row()
                    row.prop(context.scene, "collision_data", text = f"Add surface tags, fog, etc.{is_indeterminate('collision_data')}",icon = "ADD")
                elif context.scene.collidable:
                    
                    box = parent_box.box()
                    row = box.row()
                    row.label(text = "Terrain Flags", icon = "AUTO")
                    icon = "DOWNARROW_HLT" if context.scene.flags_expanded else "RIGHTARROW"
                    surfaces = [f for f in dir(SurfaceEnum) if not f.startswith("__") and not f.startswith("Surface")]
                    # if any([context.scene[prop] for prop in surfaces]):
                    #     row.operator("view3d.bake_vcolors", text = "", emboss = False, icon = 'LOOP_BACK')
                    row.prop(context.scene, "flags_expanded", icon = icon, text = "", emboss = False)
                    
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
                        r.prop(context.scene, "strict_spline", text = is_indeterminate('strict_spline'), icon = 'CURVE_DATA')
                            
                        col = row.column()
                        for flag in effects:
                            col.prop(context.scene, flag, text = f"{flag}{is_indeterminate(flag)}")
                            
                        r = col.row()
                        r.label(text = "")
                        r.scale_y = 0.5
                        for flag in feedback:
                            col.prop(context.scene, flag, text = f"{flag}{is_indeterminate(flag)}")
                        
                        
                        
                    
                    box = parent_box.box()
                    row = box.row()
                    row.label(text = "Level Fog", icon = "FORCE_FORCE")
                    icon = "DOWNARROW_HLT" if context.scene.fog_expanded else "RIGHTARROW"
                    row.operator("view3d.bake_vcolors", text = "", emboss = False, icon = 'LOOP_BACK')
                    row.prop(context.scene, "fog_expanded", icon = icon, text = "", emboss = False)
                    
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
                        
                    
                    box = parent_box.box()
                    row = box.row()
                    row.label(text = "Pod Lighting", icon = "LIGHT_SUN")
                    icon = "DOWNARROW_HLT" if context.scene.lighting_expanded else "RIGHTARROW"
                    row.operator("view3d.bake_vcolors", text = "", emboss = False, icon = 'LOOP_BACK')
                    row.prop(context.scene, "lighting_expanded", icon = icon, text = "", emboss = False)
                    
                    if context.scene.lighting_expanded:
                        row = box.row()
                        row.prop(context.scene, 'lighting_light', text = "", placeholder = is_indeterminate("lighting_light", "Mixed"))
                        row = box.row()
                        row.prop(context.scene, 'lighting_color', text = f'Ambient Color{is_indeterminate("lighting_color")}')
                        row = box.row(align = True)
                        row.prop(context.scene, 'lighting_flicker', text = f'Flicker{is_indeterminate("lighting_flicker")}', toggle = True)
                        row.prop(context.scene, 'lighting_invert', text = f'Invert{is_indeterminate("lighting_invert")}', toggle = True)
                        row.prop(context.scene, 'lighting_persistent', text = f'Persist{is_indeterminate("lighting_persistent")}', toggle = True)
                    
                    box = parent_box.box()
                    row = box.row()
                    row.label(text = "Load Trigger", icon = "MOD_BUILD")
                    icon = "DOWNARROW_HLT" if context.scene.trigger_expanded else "RIGHTARROW"
                    row.operator("view3d.bake_vcolors", text = "", emboss = False, icon = 'LOOP_BACK')
                    row.prop(context.scene, "trigger_expanded", icon = icon, text = "", emboss = False)
                    
                    # if context.scene.trigger_expanded:
                    #     row = box.row()
                    #     row.prop(context.scene, 'load_trigger', text = '', icon = 'RENDERLAYERS')
                    
                    row = parent_box.row()
                    row.operator("view3d.add_trigger", text = "Add event trigger", icon = 'ADD')
                
            if context.scene.indeterminates:
                row = layout.row()
                row.label(text = "*Selection contains mixed values")
                row.enabled = False
                
        elif spline:
            is_cyclic = spline.use_cyclic_u
            layout.operator("view3d.invert_spline", text = "Invert", icon='ARROW_LEFTRIGHT')
            layout.operator("view3d.reconstruct_spline", text = "Set spawn point", icon='TRACKING')
            icon = "CHECKBOX_HLT" if is_cyclic else "CHECKBOX_DEHLT"
            row = layout.row()
            row.label(text = 'Cyclic')
            row.operator("view3d.toggle_cyclic", emboss = False, icon = icon, text = "")
            
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
    bpy.utils.register_class(ExportPanel)
    bpy.utils.register_class(ToolPanel)
    bpy.utils.register_class(SelectedPanel)
    
def unregister():
    bpy.app.handlers.depsgraph_update_post.remove(on_object_selection)
    bpy.utils.unregister_class(InfoPanel)
    bpy.utils.unregister_class(ImportPanel)
    bpy.utils.unregister_class(ExportPanel)
    bpy.utils.unregister_class(ToolPanel)
    bpy.utils.unregister_class(SelectedPanel)
    
    # Remove icons
    for pcoll in preview_collections.values():
        previews.remove(pcoll)
    preview_collections.clear()
