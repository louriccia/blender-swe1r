# Copyright (C) 2021-2024
# lightningpirate@gmail.com.com

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

bl_info = {
    "name": "SWE1R Import/Export",
    "blender": (2, 80, 0),
    "category": "Object",
}

import os
import json

if "bpy" in locals(): #means Blender already started once
    print('already loaded in blender')
    import importlib
    importlib.reload(swe1r_import)
    importlib.reload(swe1r_export)
    importlib.reload(block)
    importlib.reload(modelblock)
    importlib.reload(textureblock)
    importlib.reload(splineblock)
    importlib.reload(popup)
else: #start up
    print('starting up for the first time')
    from .swe1r_import import *
    from .swe1r_export import *
    from .popup import *
    from .model_list import *
    from .modelblock import *
    from .block import *
    from .textureblock import *
    from .splineblock import *

import bpy

SETTINGS_FILE = os.path.join(bpy.utils.user_resource('CONFIG'), "blender_swe1r_settings.json")

def save_settings(self, context):
    keys = ['import_folder', 'import_type', 'import_model', 'export_folder', 'export_model', 'export_texture', 'export_spline']
    settings = load_settings()
    for key in [key for key in keys if context.scene.get(key) is not None]:
        settings[key] = context.scene.get(key)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

def load_settings():
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
    return settings

def set_setting(key, value):
    settings = load_settings()
    settings[key] = value
    save_settings(settings)

def get_setting(key, default=None):
    settings = load_settings()
    val = settings.get(key, default)
    return val if val is not None else default

model_types = [('0', 'All', 'View all models'),
                            ('1', 'MAlt', 'High LOD pods'),
                            ('2', 'Modl', 'Misc animated elements'),
                            ('3', 'Part', 'Misc props'),
                            ('4', 'Podd', 'Pod models'),
                            ('5', 'Pupp', 'Animated racers'),
                            ('6', 'Scen', 'Animated scenes'),
                            ('7', 'Trak', 'Tracks'),
                            ]
models = [(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(model_list)]

def update_model_dropdown(self, context):
    model_type = model_types[int(context.scene.import_type)][1]
    
    if model_type == 'All':
        items_for_selected_category = [(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(model_list)]
    else:
        items_for_selected_category = [(str(i), f"{model['name']}", f"Import model {model['name']}") for i, model in enumerate(model_list) if model['extension'] == model_type]
        items_for_selected_category.insert(0, ('-1', 'All', 'Import all models'))
        
    bpy.types.Scene.import_model = bpy.props.EnumProperty(
        items=items_for_selected_category,
        name="Model Selection",
        description="Select models to import",
    )
    save_settings(self, context)

class ImportExportExamplePanel(bpy.types.Panel):
    bl_label = "SWE1R Import/Export"
    bl_idname = "PT_ImportExportExamplePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SWE1R Import/Export'
 
    def draw(self, context):
        layout = self.layout
            
        # Section 1: Import
        box = layout.box()
        box.label(text="Import")

        box.prop(context.scene, "import_folder", full_event=False)
        box.prop(context.scene, "import_type", text="Type")
        box.prop(context.scene, "import_model", text="Model")
        box.operator("import.import_operator", text="Import")

        # Section 2: Export
        box = layout.box()
        box.label(text="Export")

        box.prop(context.scene, "export_folder", text="",  full_event=False)
           # Checkboxes on the same row
        row = box.row()
        row.prop(context.scene, "export_model", text="Model", icon='MESH_CUBE', toggle=True, icon_only=True)
        row.prop(context.scene, "export_texture", text="Texture", icon='MATERIAL', toggle=True, icon_only=True)
        row.prop(context.scene, "export_spline", text="Spline", icon='CURVE_BEZCURVE', toggle=True, icon_only=True)

        box.operator("import.export_operator", text="Export")

class ImportOperator(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "import.import_operator"
    

    def execute(self, context):
        folder_path = context.scene.import_folder
        if folder_path == "":
            show_custom_popup(bpy.context, "No set import folder", "Select your folder containing the .bin files")
            return {'CANCELLED'}
        if folder_path[:2] == '//':
            folder_path = os.path.join(os.path.dirname(bpy.data.filepath), folder_path[2:])
        if not os.path.exists(folder_path  + 'out_modelblock.bin'):
            show_custom_popup(bpy.context, "Missing required files", "No out_modelblock.bin found in the selected folder.")
            return {'CANCELLED'}

        import_model(folder_path, [int(context.scene.import_model)])

        return {'FINISHED'}

class ExportOperator(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "import.export_operator"

    def execute(self, context):
        folder_path = context.scene.export_folder if context.scene.export_folder else context.scene.import_folder
        selected_collection = context.view_layer.active_layer_collection.collection
        if 'ind' not in selected_collection:
            show_custom_popup(bpy.context, "Invalid collection selected", "Please select a model collection to export")
            return {'CANCELLED'}
        if folder_path == "":
            show_custom_popup(bpy.context, "No set export folder", "Select your folder containing the .bin files")
            return {'CANCELLED'}
        if not os.path.exists(folder_path  + 'out_modelblock.bin'):
            show_custom_popup(bpy.context, "Missing required files", "No out_modelblock.bin found in the selected folder.")
            return {'CANCELLED'}
        
        export_model(selected_collection, folder_path, [context.scene.export_model, context.scene.export_texture, context.scene.export_spline])
        
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(ImportOperator.bl_idname)
    self.layout.operator(ExportOperator.bl_idname)

def register():

    bpy.types.Scene.import_folder = bpy.props.StringProperty(subtype='DIR_PATH', update=save_settings, default =get_setting('import_folder', ""), description="Select the lev01 folder (or any folder containing the .bin files)")
    bpy.types.Scene.import_type = bpy.props.EnumProperty(
        items=model_types,
        name="Model Type",
        description="Select model type",
        default=get_setting('import_type', 0), 
        update=update_model_dropdown
    )
    bpy.types.Scene.import_model = bpy.props.EnumProperty(
        items=models,
        name="Model",
        description="Select model",
        default=get_setting('import_model', 0), 
        update=save_settings
    )
    bpy.types.Scene.export_folder = bpy.props.StringProperty(subtype='DIR_PATH', update=save_settings, default=get_setting('export_folder', ""), description="Select the lev01 folder (or any folder you wish to export to)")
    bpy.types.Scene.export_model = bpy.props.BoolProperty(name="Model", update=save_settings, default=get_setting('export_model', True))
    bpy.types.Scene.export_texture = bpy.props.BoolProperty(name="Texture", update=save_settings, default=get_setting('export_texture', True))
    bpy.types.Scene.export_spline = bpy.props.BoolProperty(name="Spline", update=save_settings, default=get_setting('export_spline', True))
    
    bpy.utils.register_class(ImportExportExamplePanel)
    bpy.utils.register_class(ImportOperator)
    bpy.utils.register_class(ExportOperator)
    bpy.types.TOPBAR_MT_file.append(menu_func)

def unregister():
    bpy.utils.unregister_class(ImportExportExamplePanel)
    bpy.utils.unregister_class(ImportOperator)
    bpy.utils.unregister_class(ExportOperator)
    bpy.types.TOPBAR_MT_file.remove(menu_func)
    del bpy.types.Scene.import_folder
    del bpy.types.Scene.import_type
    del bpy.types.Scene.import_model
    del bpy.types.Scene.export_folder
    del bpy.types.Scene.export_model
    del bpy.types.Scene.export_texture
    del bpy.types.Scene.export_spline
