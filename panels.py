
from .swr_import import *
from .swr_export import *
from .popup import *
import bpy
from .swe1r.model_list import model_list
from .swe1r.modelblock import SurfaceEnum
from .operators import *
from .constants import *
from . import bl_info
import os
from bpy.utils import previews

models = [(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(model_list)]
classes = []    
    
bpy.types.Object.target = bpy.props.PointerProperty(type=bpy.types.Object)

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
        layout.label(text = bl_info['name'])
        layout.label(text = "Version: " + ".".join(map(str, bl_info['version'])))
        row = layout.row(align=True)
        row.operator("view3d.open_url", text="Discord", icon_value=preview_collections["main"]["discord"].icon_id).url = URL_DISCORD
        row.operator("view3d.open_url", text="Github", icon_value=preview_collections["main"]["github"].icon_id).url = URL_GITHUB
        row.operator("view3d.open_url", text="ko-fi", icon_value=preview_collections["main"]["kofi"].icon_id).url = URL_KOFI

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
            
        # Export
        layout.prop(context.scene, "export_folder", text="",  full_event=False)
        row = layout.row(align=True)
        row.prop(context.scene, "export_model", text="Model", icon='MESH_CUBE', toggle=True, icon_only=True)
        row.prop(context.scene, "export_texture", text="Texture", icon='MATERIAL', toggle=True, icon_only=True)
        row.prop(context.scene, "export_spline", text="Spline", icon='CURVE_BEZCURVE', toggle=True, icon_only=True)
        # row = layout.row()
        # row.prop(context.scene, "export_spawn", text="Spawn at cursor", icon='CURSOR')
        row = layout.row()
        row.scale_y = 1.5
        row.operator("view3d.export_operator", text="Export")
        
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
        
        row = layout.row(align=True)
        row.label(text = "Visuals")
        row.operator("view3d.select_visible", text = "Select", icon = 'SELECT_SET')
        row.prop(context.scene, "visuals_visible", toggle=True, text = "", icon = 'HIDE_OFF' if context.scene.visuals_visible else 'HIDE_ON')
        row.prop(context.scene, "visuals_selectable", toggle =True, text = "", icon = 'RESTRICT_SELECT_OFF' if context.scene.visuals_selectable else 'RESTRICT_SELECT_ON') 
        
        row = layout.row(align=True)
        row.label(text = "Collision")
        row.operator("view3d.select_collidable", text = "Select", icon = 'SELECT_SET')
        row.prop(context.scene, "collision_visible", toggle=True, text = "", icon = 'HIDE_OFF' if context.scene.collision_visible else 'HIDE_ON')
        row.prop(context.scene, "collision_selectable", toggle =True, text = "", icon = 'RESTRICT_SELECT_OFF' if context.scene.collision_selectable else 'RESTRICT_SELECT_ON') 
        
        
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
        collidable = True
        collidable_data = True
        visible = True
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                if 'collidable'  not in obj or not obj['collidable']:
                    collidable = False
                if 'collision_data' not in obj or not obj['collision_data']:
                    collidable_data = False
                if 'visible'  not in obj or not obj['visible']:
                    visible = False
                mesh = True
            if obj.type == 'CURVE':
                spline = obj.data.splines.active
            if obj.type == 'LIGHT':
                light = obj.data
                
        if mesh:

            if not visible:
                row = layout.row()
                row.operator("view3d.set_visible", text= "Add visuals", icon = 'ADD')
                row.scale_y = 1.5
            else:
                parent_box = layout.box()
                col = parent_box.column(align=True)
                
                row = col.row(align=True)
                row.scale_y = 1.5
                row.label(text = 'Visuals', icon = 'MATERIAL_DATA')
                row.operator("view3d.v_color", text="Reset", emboss=False) # TODO: formalize reset fn
                row.operator("view3d.set_nonvisible", text = "", icon = "TRASH", emboss = False)

                # baked lighting panel

                box = parent_box.box()
                row = box.row()
                row.label(text='Baked Lighting', icon='LIGHT_SUN')
                icon = 'DOWNARROW_HLT' if context.scene.lights_expanded else 'RIGHTARROW'
                #row.operator('view3d.bake_vcolors', text='', emboss=False, icon='FILE_REFRESH')
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
                    row.operator('view3d.bake_vcolors_clear', text='', icon='TRASH', emboss=False)

                # texture panel

                box = parent_box.box()
                row = box.row()
                row.label(text = "Texture", icon = "TEXTURE")
                icon = "DOWNARROW_HLT" if context.scene.textures_expanded else "RIGHTARROW"
                #row.operator('', text='', emboss=False, icon='FILE_REFRESH')
                row.prop(context.scene, "textures_expanded", icon = icon, text = "", emboss = False)
                if context.scene.textures_expanded:
                    row = box.row()
                    row.label(text = 'Scroll animation')
                    row= box.row()
                    row.label(text = 'Flip X/Y')
            
            if not collidable:
                row = layout.row()
                row.operator("view3d.set_collidable", text= "Add collision", icon = 'ADD')
                row.scale_y = 1.5
            else:

                parent_box = layout.box()
                row = parent_box.row(align=True)
                row.scale_y = 1.5
                row.label(text = 'Collision', icon = 'MOD_PHYSICS')
                row.operator("view3d.reset_collision_data", text = "Reset", emboss = False)
                row.operator("view3d.set_noncollidable", text = "", icon = "TRASH", emboss = False)
                
                if not collidable_data:
                    row = parent_box.row()
                    row.operator("view3d.add_collision_data", text= "Add surface tags, fog, etc.", icon = "ADD")
                elif collidable:
                    
                    box = parent_box.box()
                    row = box.row()
                    row.label(text = "Terrain Flags", icon = "AUTO")
                    icon = "DOWNARROW_HLT" if context.scene.flags_expanded else "RIGHTARROW"
                    row.operator("view3d.bake_vcolors", text = "", emboss = False, icon = 'FILE_REFRESH')
                    row.prop(context.scene, "flags_expanded", icon = icon, text = "", emboss = False)
                    
                    if context.scene.flags_expanded:
                        # surfaces = [f for f in dir(SurfaceEnum) if not f.startswith("__") and not f.startswith("Surface")]
                        # flag_count = len(surfaces)
                        # row = box.row()
                        # for i in range(2):
                        #     col = row.column()
                        #     for j in range(int(i*flag_count/2), (i+1)*int(flag_count/2)):
                        #         col.prop(context.active_object, surfaces[j])
                        # row = box.row()
                        
                        gameplay = ["Fast", "Slow", "Swst", "Slip", "Lava", "ZOn", "ZOff", "Fall", "NRsp"]
                        effects = ["Dust", "Wet", "Swmp", "Snow", "NSnw", "Mirr", "Side"]
                        feedback = ["Ruff", "Soft", "Flat"]
                        
                        row = box.row()
                        col = row.column()
                        for flag in gameplay:
                            col.prop(context.active_object, flag)
                        
                        r = col.row()
                        r.label(text = "")
                        r.scale_y = 0.5
                        r = col.row()
                        r.prop(context.active_object, "magnet", text = '', icon = 'SNAP_ON')
                            
                        col = row.column()
                        for flag in effects:
                            col.prop(context.active_object, flag)
                            
                        r = col.row()
                        r.label(text = "")
                        r.scale_y = 0.5
                        for flag in feedback:
                            col.prop(context.active_object, flag)
                        
                        
                        
                    
                    box = parent_box.box()
                    row = box.row()
                    row.label(text = "Fog", icon = "FORCE_FORCE")
                    icon = "DOWNARROW_HLT" if context.scene.fog_expanded else "RIGHTARROW"
                    row.operator("view3d.bake_vcolors", text = "", emboss = False, icon = 'FILE_REFRESH')
                    row.prop(context.scene, "fog_expanded", icon = icon, text = "", emboss = False)
                    
                    if context.scene.fog_expanded:
                        row = box.row()
                        col = row.column()
                        col.prop(context.active_object, 'fog_color_update', text = 'Set color')
                        col = row.column()
                        col.prop(context.active_object, 'fog_color', text = '')
                        col.enabled = context.active_object.fog_color_update
                        row.enabled = not context.active_object.fog_clear
                        row = box.row()
                        col = row.column()
                        col.prop(context.active_object, 'fog_range_update', text = 'Set range')
                        col = row.column()
                        col.prop(context.active_object, 'fog_min', text = 'Min', slider = True)
                        col.prop(context.active_object, 'fog_max', text = 'Max', slider = True)
                        col.enabled = context.active_object.fog_range_update
                        row.enabled = not context.active_object.fog_clear
                        row = box.row()
                        row.prop(context.active_object, 'fog_clear', text = 'Clear Fog', icon = 'SHADERFX')
                        row = box.row()
                        row.prop(context.active_object, 'skybox_show', text = 'Show Skybox', icon = 'HIDE_OFF')
                        row.prop(context.active_object, 'skybox_hide', text = 'Hide Skybox', icon = 'HIDE_ON')
                        
                    
                    box = parent_box.box()
                    row = box.row()
                    row.label(text = "Lighting", icon = "LIGHT_SUN")
                    icon = "DOWNARROW_HLT" if context.scene.lighting_expanded else "RIGHTARROW"
                    row.operator("view3d.bake_vcolors", text = "", emboss = False, icon = 'FILE_REFRESH')
                    row.prop(context.scene, "lighting_expanded", icon = icon, text = "", emboss = False)
                    
                    if context.scene.lighting_expanded:
                        row = box.row()
                        row.prop(context.active_object, 'lighting_light', text = '')
                        row = box.row()
                        row.prop(context.active_object, 'lighting_color', text = 'Ambient Color')
                        row = box.row()
                        row.prop(context.active_object, 'lighting_flicker', text = 'Flicker', toggle = True)
                        row.prop(context.active_object, 'lighting_invert', text = 'Invert', toggle = True)
                        row.prop(context.active_object, 'lighting_persistent', text = 'Persist', toggle = True)
                    
                    box = parent_box.box()
                    row = box.row()
                    row.label(text = "Load Trigger", icon = "MOD_BUILD")
                    icon = "DOWNARROW_HLT" if context.scene.trigger_expanded else "RIGHTARROW"
                    row.operator("view3d.bake_vcolors", text = "", emboss = False, icon = 'FILE_REFRESH')
                    row.prop(context.scene, "trigger_expanded", icon = icon, text = "", emboss = False)
                    
                    if context.scene.trigger_expanded:
                        row = box.row()
                        row.prop(context.active_object, 'load_trigger', text = '', icon = 'RENDERLAYERS')
                    
                    row = parent_box.row()
                    row.operator("view3d.add_trigger", text = "Add trigger", icon = 'ADD')
                
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
    
        

def register():
    # Load custom icons
    pcoll = previews.new()
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    icon_files = [
        ("discord", "discord.png"),
        ("github", "github.png"),
        ("kofi", "kofi.png"),
    ]
    
    for name, file in icon_files:
        pcoll.load(name, os.path.join(icons_dir, file), 'IMAGE')
    preview_collections["main"] = pcoll

    bpy.utils.register_class(InfoPanel)
    bpy.utils.register_class(ImportPanel)
    bpy.utils.register_class(ExportPanel)
    bpy.utils.register_class(ToolPanel)
    bpy.utils.register_class(SelectedPanel)
    
def unregister():
    bpy.utils.unregister_class(InfoPanel)
    bpy.utils.unregister_class(ImportPanel)
    bpy.utils.unregister_class(ExportPanel)
    bpy.utils.unregister_class(ToolPanel)
    bpy.utils.unregister_class(SelectedPanel)
    
    # Remove icons
    for pcoll in preview_collections.values():
        previews.remove(pcoll)
    preview_collections.clear()
