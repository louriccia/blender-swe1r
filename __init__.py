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

my_first_dropdown_values = [('0', 'All', 'View all models'),
                            ('1', 'MAlt', 'High LOD pods'),
                            ('2', 'Modl', 'Misc animated elements'),
                            ('3', 'Part', 'Misc props'),
                            ('4', 'Podd', 'Pod models'),
                            ('5', 'Pupp', 'Animated racers'),
                            ('6', 'Scen', 'Animated scenes'),
                            ('7', 'Trak', 'Tracks'),
                            ]
my_dropdown_values = [(str(i), f"Model {i}", f"Select model {i}") for i in range(1, 324)]

bpy.types.Scene.import_category = bpy.props.EnumProperty(
    items=my_first_dropdown_values,
    name="Category Selection",
    description="Select category",
)
bpy.types.Scene.import_numbers = bpy.props.EnumProperty(
    items=my_dropdown_values,
    name="Model Selection",
    description="Select models to import",
)

# Callback function to dynamically update the items of the first dropdown based on the second dropdown selection
def update_model_dropdown(self, context):
    selected_category = context.scene.import_category
    items_for_selected_category = [(str(i), f"Model {i} in Category {selected_category}", f"Select model {i} in Category {selected_category}") for i in range(1, 11)]
    bpy.types.Scene.import_numbers = bpy.props.EnumProperty(
        items=items_for_selected_category,
        name="Model Selection",
        description="Select models to import",
    )

# Define the second dropdown and set the update callback
bpy.types.Scene.import_subcategory = bpy.props.EnumProperty(
    items=[("1", "Subcategory 1", "Select subcategory 1"), ("2", "Subcategory 2", "Select subcategory 2")],
    name="Subcategory Selection",
    description="Select subcategory",
    update=update_model_dropdown,  # Set the update callback
)

class ImportExportExamplePanel(bpy.types.Panel):
    bl_label = "SWE1R Import/Export"
    bl_idname = "PT_ImportExportExamplePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tools'
 
    def draw(self, context):
        layout = self.layout

        # Section 1: Import
        box = layout.box()
        box.label(text="Import")

        box.prop(context.scene, "import_folder_path", text="",   full_event=False)
        box.prop(context.scene, "import_category", text="Type")
        box.prop(context.scene, "import_subcategory", text="Model")
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
        # Accessing the imported functions from the module
       
        folder_path = context.scene.export_folder_path if context.scene.export_folder_path else context.scene.import_folder_path
        if folder_path == "":
            show_custom_popup(bpy.context, "No set import folder", "Select your folder containing the .bin files")
            return {'CANCELLED'}
        file_path = folder_path + 'out_modelblock.bin'
        selector = selector.split(',')
        selector = [int(num_str.strip()) for num_str in selector]
        print(file_path, selector)
        import_model(file_path, selector)
        # import_export_functions.export_data(
        #     folder_path,
        #     context.scene.export_model,
        #     context.scene.export_texture,
        #     context.scene.export_spline
        # )
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(ImportExportOperator.bl_idname)

def register():
    bpy.utils.register_class(ImportExportExamplePanel)
    bpy.utils.register_class(ImportExportOperator)
    bpy.types.TOPBAR_MT_file.append(menu_func)
    bpy.types.Scene.import_folder_path = bpy.props.StringProperty(subtype='DIR_PATH', description="Select the lev01 folder (or any folder containing the .bin files)")
    # Register the EnumProperty (dropdown)
    bpy.types.Scene.import_category = bpy.props.EnumProperty(
        items=my_first_dropdown_values,
        name="Category Selection",
        description="Select category",
    )

    bpy.types.Scene.import_subcategory = bpy.props.EnumProperty(
        items=[("1", "Subcategory 1", "Select subcategory 1"), ("2", "Subcategory 2", "Select subcategory 2")],
        name="Subcategory Selection",
        description="Select subcategory",
        update=update_model_dropdown,
    )

    # Initially set the items for import_numbers based on the default value of import_category
    update_model_dropdown(None, bpy.context)

    bpy.types.Scene.export_folder_path = bpy.props.StringProperty(subtype='DIR_PATH', description="Select the lev01 folder (or any folder you wish to export to)")
    bpy.types.Scene.export_model = bpy.props.BoolProperty(name="Model", default=True)
    bpy.types.Scene.export_texture = bpy.props.BoolProperty(name="Texture", default=True)
    bpy.types.Scene.export_spline = bpy.props.BoolProperty(name="Spline", default=True)


def unregister():
    bpy.utils.unregister_class(ImportExportExamplePanel)
    bpy.utils.unregister_class(ImportExportOperator)
    bpy.types.TOPBAR_MT_file.remove(menu_func)
    del bpy.types.Scene.import_folder_path
    del bpy.types.Scene.import_subcategory
    del bpy.types.Scene.my_first_dropdown_values
    del bpy.types.Scene.export_folder_path
    del bpy.types.Scene.export_model
    del bpy.types.Scene.export_texture
    del bpy.types.Scene.export_spline
