# Copyright (C) 2021-2023
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

import bpy
import sys
sys.path += [r"C:\Users\louri\Documents\GitHub\SWE1R-Mods\tools\blender_addon"]
from .swe1r_import import *
from .popup import show_custom_popup
from .model_list import model_list

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

# Callback function to dynamically update the items of the first dropdown based on the second dropdown selection
def update_model_dropdown(self, context):
    model_type = model_types[int(context.scene.import_type)][1]
    
    if model_type == 'All':
        items_for_selected_category = [(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(model_list)]
    else:
        items_for_selected_category = [(str(i), f"{model['name']}", f"Import model {model['name']}") for i, model in enumerate(model_list) if model['extension'] == model_type]
        
    print(items_for_selected_category)
    bpy.types.Scene.import_model = bpy.props.EnumProperty(
        items=items_for_selected_category,
        name="Model Selection",
        description="Select models to import",
    )

# Define the second dropdown and set the update callback
bpy.types.Scene.import_type = bpy.props.EnumProperty(
    items=[("0", "All", "Select from all models of this type")],
    name="Model Type",
    description="Select model type",
)

bpy.types.Scene.import_model = bpy.props.EnumProperty(
    items=models,
    name="Model Selection",
    description="Select models to import",
)

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

        box.prop(context.scene, "import_folder_path", text="",   full_event=False)
        box.prop(context.scene, "import_type", text="Type")
        box.prop(context.scene, "import_model", text="Model")
        box.operator("import.export_operator", text="Import")

        # Section 2: Export
        box = layout.box()
        box.label(text="Export")

        box.prop(context.scene, "export_folder_path", text="",  full_event=False)
           # Checkboxes on the same row
        row = box.row()
        row.prop(context.scene, "export_model", text="Model", icon='MESH_CUBE', toggle=True, icon_only=True)
        row.prop(context.scene, "export_texture", text="Texture", icon='MATERIAL', toggle=True, icon_only=True)
        row.prop(context.scene, "export_spline", text="Spline", icon='CURVE_BEZCURVE', toggle=True, icon_only=True)

        box.operator("import.export_operator", text="Export")


class ImportExportOperator(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "import.export_operator"

    def execute(self, context):
        folder_path = context.scene.import_folder_path
        if folder_path == "":
            show_custom_popup(bpy.context, "No set import folder", "Select your folder containing the .bin files")
            return {'CANCELLED'}
        file_path = folder_path + 'out_modelblock.bin'
        print(file_path, [int(context.scene.import_model)])
        import_model(file_path, [int(context.scene.import_model)])

        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(ImportExportOperator.bl_idname)

def register():
    bpy.utils.register_class(ImportExportExamplePanel)
    bpy.utils.register_class(ImportExportOperator)
    bpy.types.TOPBAR_MT_file.append(menu_func)
    bpy.types.Scene.import_folder_path = bpy.props.StringProperty(subtype='DIR_PATH', description="Select the lev01 folder (or any folder containing the .bin files)")
    # Register the EnumProperty (dropdown)
    bpy.types.Scene.import_type = bpy.props.EnumProperty(
        items=model_types,
        name="Model Type",
        description="Select model type",
        update=update_model_dropdown
    )

    bpy.types.Scene.import_model = bpy.props.EnumProperty(
        items=models,
        name="Model",
        description="Select model"
    )

    bpy.types.Scene.export_folder_path = bpy.props.StringProperty(subtype='DIR_PATH', description="Select the lev01 folder (or any folder you wish to export to)")
    bpy.types.Scene.export_model = bpy.props.BoolProperty(name="Model", default=True)
    bpy.types.Scene.export_texture = bpy.props.BoolProperty(name="Texture", default=True)
    bpy.types.Scene.export_spline = bpy.props.BoolProperty(name="Spline", default=True)


def unregister():
    bpy.utils.unregister_class(ImportExportExamplePanel)
    bpy.utils.unregister_class(ImportExportOperator)
    bpy.types.TOPBAR_MT_file.remove(menu_func)
    del bpy.types.Scene.import_folder_path
    del bpy.types.Scene.import_type
    del bpy.types.Scene.import_model
    del bpy.types.Scene.export_folder_path
    del bpy.types.Scene.export_model
    del bpy.types.Scene.export_texture
    del bpy.types.Scene.export_spline
