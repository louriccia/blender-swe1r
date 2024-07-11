
from .swr_import import *
from .swr_export import *
from .popup import *
import bpy
from .swe1r.model_list import model_list
from .operators import *
from .constants import *


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
            
        layout.operator("view3d.open_url", text="").url = URL_DISCORD

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
                
        if mesh:

            if not visible:
                row = layout.row()
                row.operator("view3d.set_visible", text= "Add visuals", icon = 'ADD')
            else:
                box = layout.box()
                row = box.row(align=True)
                row.label(text = 'Visuals')
                row.operator("view3d.set_nonvisible", text = "", icon = "TRASH")
                row = box.row()
                row.operator("view3d.v_color", text="Set/Reset Vertex Colors")
            
            if not collidable:
                row = layout.row()
                row.operator("view3d.set_collidable", text= "Add collision", icon = 'ADD')
            else:
                box = layout.box()
                row = box.row(align=True)
                row.label(text = 'Collision')
                row.operator("view3d.set_noncollidable", text = "", icon = "TRASH")
                row = box.row()
                if not collidable_data:
                    row.operator("view3d.add_collision_data", text= "Add surface tags, fog, etc.", icon = "ADD")
                elif collidable:
                    row.operator("view3d.reset_collision_data", text = "Reset")
                    row = box.row()
                    row.operator("view3d.add_trigger", text = "Add trigger", icon = 'ADD')
                
        elif spline:
            is_cyclic = spline.use_cyclic_u
            layout.operator("view3d.invert_spline", text = "Invert", icon='ARROW_LEFTRIGHT')
            layout.operator("view3d.reconstruct_spline", text = "Set spawn point", icon='TRACKING')
            label = "Cyclic" if is_cyclic else "Non-cyclic"
            layout.operator("view3d.toggle_cyclic", text=label)
            
        

def register():
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