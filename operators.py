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
import sys
import importlib
import traceback
from bpy_extras.io_utils import ImportHelper
from .swe1r.modelblock import SurfaceEnum

modules = [
    'swr_import',
    'swr_export',
    'operators',
    'swe1r.model_list',
    'swe1r.modelblock',
    'swe1r.block',
    'swe1r.textureblock',
    'swe1r.splineblock',
    'swe1r.general',
]

for m in modules: 
    module_name = f"{__package__}.{m}"
    if m in sys.modules:
        module = sys.modules[module_name]
        importlib.reload(module)
    else:
        module = importlib.import_module(module_name)
        sys.modules[module_name] = module

from .swe1r.model_list import *
from .swe1r.modelblock import *
from .swe1r.block import *
from .swe1r.textureblock import *
from .swe1r.splineblock import *
from .swe1r.general import *
#from .panels import *
from .swr_import import *
from .swr_export import *
from .utils import *

class ImportOperator(bpy.types.Operator):
    """Import the selected model to the Blender scene"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.import_operator"
    bl_info = "Import the selected model"
    

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

        context.scene.import_progress = 0.01
        context.scene.import_status = 'Importing...'

        def update_progress(status):
            context.scene.import_progress = context.scene.import_progress + 0.1*(1.0 - context.scene.import_progress)
            context.scene.import_status = status
            
            # manually redraw since blender doesn't while in operation
            # this is not recommended according to https://docs.blender.org/api/current/info_gotcha.html
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
           
        try: 
            id = int(context.scene.import_model)
            import_type = next((item[1] for item in model_types if item[0] == context.scene.import_type), None)
            if id == -1:
                selector = [model["index"] for model in model_list if model['extension'] == import_type]
            else:
                selector = [int(context.scene.import_model)]
            import_model(folder_path, selector, update_progress)
        except Exception as e:
            context.scene.import_progress = 1.0
            context.scene.import_status = ""
            print("Complete exception details:")
            traceback.print_exception(type(e), e, e.__traceback__)
            show_custom_popup(bpy.context, "An error occurred during import", str(e))
            return {'CANCELLED'}
            
        context.scene.import_progress = 1.0
        context.scene.import_status = ""
        
        return {'FINISHED'}
    

class ExportOperator(bpy.types.Operator):
    """Export the selected collection to the game files"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.export_operator"

    def execute(self, context):
        selected_objects = context.selected_objects
        selected_collection = context.view_layer.active_layer_collection.collection
        if selected_objects:
            selected_collection = selected_objects[0].users_collection[0]
            
        if selected_collection is None:
            show_custom_popup(bpy.context, "No collection", "Exported items must be part of a collection")
            return {'CANCELLED'}
                
        folder_path = context.scene.export_folder if context.scene.export_folder else context.scene.import_folder
        
        if selected_collection.export_model is None:
            show_custom_popup(bpy.context, "Invalid collection selected", "Please select a model collection to export")
            return {'CANCELLED'}
        if folder_path == "":
            show_custom_popup(bpy.context, "No set export folder", "Select your folder containing the .bin files")
            return {'CANCELLED'}
        if not os.path.exists(folder_path  + 'out_modelblock.bin'):
            show_custom_popup(bpy.context, "Missing required files", "No out_modelblock.bin found in the selected folder.")
            return {'CANCELLED'}
        
        context.scene.export_progress = 0.01
        context.scene.export_status = 'Importing...'
        
        def update_progress(status):
            context.scene.export_progress = context.scene.export_progress + 0.1*(1.0 - context.scene.export_progress)
            context.scene.export_status = status
            
            # manually redraw since blender doesn't while in operation
            # this is not recommended according to https://docs.blender.org/api/current/info_gotcha.html
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            
        try:
            export_model(selected_collection, folder_path, [context.scene.is_export_model, context.scene.is_export_texture, context.scene.is_export_spline], update_progress)
        except Exception as e:
            print("Complete exception details:")
            traceback.print_exception(type(e), e, e.__traceback__)
            show_custom_popup(bpy.context, "An error occurred during export", str(e))
            context.scene.export_progress = 1.0
            context.scene.export_status = ""
            return {'CANCELLED'}
        
        context.scene.export_progress = 1.0
        context.scene.export_status = ""
        
        return {'FINISHED'}
    
class NewModelOperator(bpy.types.Operator):
    """Create a new model"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.new_model"
    
    def execute(self, context):
        type = context.scene.new_type
        type_name = model_types[int(type)][1]
        main_collection = bpy.data.collections.new("New " + type_name + " Model")
        main_collection.collection_type = "MODEL"
        
        valid_models = [model for model in model_list if model['extension'] == type_name]
        
        if type_name == 'Trak':
            track_collection = bpy.data.collections.new("Track")
            track_collection.collection_type = "0"
            skybox_collection = bpy.data.collections.new("Skybox")
            skybox_collection.collection_type = "1"
            main_collection.children.link(track_collection)
            main_collection.children.link(skybox_collection)
            
            curve_data = bpy.data.curves.new("SplineCurve", type="CURVE")
            curve_data.dimensions = '3D'
            curve_data.splines.new('BEZIER')
            spline_object = bpy.data.objects.new("spline", curve_data)
            
            main_collection.objects.link(spline_object)
        
        elif type_name == 'Podd':
            right_engine_collection = bpy.data.collections.new("Right Engine")
            right_engine_collection.collection_type = "2"
            left_engine_collection = bpy.data.collections.new("Left Engine")
            left_engine_collection.collection_type = "3"
            cockpit_collection = bpy.data.collections.new("Cockpit")
            cockpit_collection.collection_type = "4"
            cable_collection = bpy.data.collections.new("Cable")
            cable_collection.collection_type = "5"
            
            main_collection.children.link(right_engine_collection)
            main_collection.children.link(left_engine_collection)
            main_collection.children.link(cockpit_collection)
            main_collection.children.link(cable_collection)
            
        main_collection.export_type = type
        main_collection.export_model = str(valid_models[0]['index'])
        
        context.scene.collection.children.link(main_collection)
        
        return {'FINISHED'}

# TOOLS
    
class SelectByProperty(bpy.types.Operator):
    """Select mesh objects based on a specified property"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.select_by_property"

    property_name: bpy.props.StringProperty()
    selectable_flag: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')

        # Make selectable if needed
        if not getattr(context.scene, self.selectable_flag, False):
            setattr(context.scene, self.selectable_flag, True)

        # Select objects based on property
        for obj in bpy.context.scene.objects:
            if self.property_name in obj and obj[self.property_name]:
                obj.hide_select = False
                obj.select_set(True)

        return {'FINISHED'}

# MARK: RESET

    
class ResetVisuals(bpy.types.Operator):
    """Reset visual data"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.reset_visuals"
    
    def execute(self, context):
        bpy.ops.view3d.reset_v_color()
        bpy.ops.view3d.reset_texture()
        
        return {'FINISHED'}

class ResetVColor(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.reset_v_color"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            reset_vertex_colors(obj)

        return {'FINISHED'}
    
class ResetTexture(bpy.types.Operator):
    """Reset texture data"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.reset_texture"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            mats = [slot.material for slot in obj.material_slots]
            if not len(mats): continue
            mats[0].use_backface_culling = False
            mats[0].transparent = False
            mats[0].scroll_x = False
            mats[0].scroll_y = False
            mats[0].flip_x = False
            mats[0].flip_y = False
            mats[0].clip_x = False
            mats[0].clip_y = False
        return {'FINISHED'}

class ResetCollidable(bpy.types.Operator):
    """Reset collidable data"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.reset_collidable"
    
    def execute(self, context):
        bpy.ops.view3d.reset_terrain()
        bpy.ops.view3d.reset_lighting()
        bpy.ops.view3d.reset_fog()
        bpy.ops.view3d.reset_loading()
        selected_objects = context.selected_objects
        for obj in selected_objects:
            obj.collision_data = False
            
            reselect_obj(obj)
        return {'FINISHED'}
    

class ResetTerrain(bpy.types.Operator):
    """Reset terrain data"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.reset_terrain"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            for flag in dir(SurfaceEnum):
                if not flag.startswith("__"):
                    obj[flag] = False
                    context.scene[flag] = False
            for flag in ['magnet', 'strict_spline', 'elevation']:
                obj[flag] = False
                context.scene[flag] = False
            reselect_obj(obj)
        return {'FINISHED'}
    
class ResetLighting(bpy.types.Operator):
    """Reset lighting data"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.reset_lighting"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            obj.lighting_light = None
            obj.lighting_color = (1.0, 1.0, 1.0)
            obj.lighting_invert = False
            obj.lighting_flicker = False
            obj.lighting_persistent = False
            reselect_obj(obj)
        return {'FINISHED'}
    
class ResetFog(bpy.types.Operator):
    """Reset lighting data"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.reset_fog"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            obj.fog_color = (1.0, 1.0, 1.0)
            obj.fog_color_update = False
            obj.fog_range_update = False 
            obj.fog_min = 1000
            obj.fog_max = 30000
            obj.fog_clear = False
            obj.skybox_show = False
            obj.skybox_hide = False
            reselect_obj(obj)
        return {'FINISHED'}
    
class ResetLoading(bpy.types.Operator):
    """Reset loading data"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.reset_loading"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            for i, val in enumerate(obj.load_trigger):
                obj.load_trigger[i] = 0
            reselect_obj(obj)
        return {'FINISHED'}
    
# MARK: VISUALS

# Custom operator to load and assign an image
class OpenImageTexture(bpy.types.Operator, ImportHelper):
    """Open Image and Assign to Texture Node"""
    bl_idname = "view3d.open_image"
    bl_label = "Open Image"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".png;.jpg;.jpeg;.bmp;.tiff;.tga;.exr;.hdr"
    filter_glob: bpy.props.StringProperty(
        default="*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.tga;*.exr;*.hdr;*.gif",
        options={'HIDDEN'},
        maxlen=255
    )
    
    def invoke(self, context, event):
        # Open the file browser
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        print("Selected file:", self.filepath)
        # Validate the file path
        if not self.filepath:
            self.report({'WARNING'}, "No file selected.")
            return {'CANCELLED'}
        
        image = bpy.data.images.load(self.filepath, check_existing=True)
        for obj in context.selected_objects:
            if obj and obj.type == 'MESH':
                mats = [slot.material for slot in obj.material_slots]
                if mats[0] is not None:
                    obj.material_slots[0].material = Material(None, None).remake(mats[0], tex_name = image.name)
                # if len(mats) and mats[0].node_tree:
                #     for node in mats[0].node_tree.nodes:
                #         if node.type == 'TEX_IMAGE':
                #             node.image = image
                #             self.report({'INFO'}, f"Assigned {image.name} to {node.name}")
        return {'FINISHED'}
    
class RemakeMaterials(bpy.types.Operator):
    bl_idname = "view3d.remake_materials"
    bl_label = "Remake Materials"
    bl_description = "Remake materials for all selected objects"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            if obj.type != 'MESH' or obj.material_slots is None:
                continue
            mats = [slot.material for slot in obj.material_slots]
            if len(mats):
                obj.material_slots[0].material = Material(None, None).remake(mats[0])
            else:
                remake = Material(None, None).make()
                obj.data.materials.append(remake)
        return {"FINISHED"}

class BakeVColors(bpy.types.Operator):
    bl_idname = "view3d.bake_vcolors"
    bl_label = "Bake Vertex Colors"
    bl_description = "Bake lighting into dedicated color map, while preserving Render Color"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            # Calculate the total light for each vertex of the selected object
            total_lights = calculate_total_light_for_object(obj, context.scene.light_falloff, context.scene.ambient_light_intensity, context.scene.ambient_light)
               
            reset_vertex_colors(obj)
            
            color_layer = obj.data.vertex_colors.active.data   
                
            for poly in obj.data.polygons:
                for p in range(len(poly.vertices)):
                    color = total_lights[poly.vertices[p]]
                    color_layer[poly.loop_indices[p]].color = [*color, 1.0]

        bpy.ops.view3d.remake_materials()

        return {"FINISHED"}
    
# MARK: COLLISION
    
class PreviewLoadTrigger(bpy.types.Operator):
    """Preview load trigger"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.preview_load"
    
    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        selected_obj = selected_meshes[0]
        layers = selected_obj.load_trigger
        collections = [col for col in bpy.data.collections if selected_obj.name in col.objects]
        selected_collection = collections[0]
        objs = get_all_objects_in_collection(selected_collection)
        working_layer = context.scene.view_layers[0]
        for i, val in enumerate(layers):
            if not val:
                continue
            view_layer = context.scene.view_layers[i + 1]
            for obj in objs:
                active = not obj.hide_get(view_layer = view_layer)
                if not active:
                    continue
                obj.hide_set(False if val == 1 else True, view_layer = working_layer)
        return {'FINISHED'}
    
class ToggleViewLayerState(bpy.types.Operator):
    """Cycles through Unchecked → Checked → Exed → Unchecked"""
    bl_idname = "my_list.toggle_state"
    bl_label = "Toggle State"
    
    item_index: bpy.props.IntProperty()  # Stores index of the clicked item

    def execute(self, context):
        scene = context.scene
        item = scene.load_trigger[self.item_index]

        # Cycle through the three states
        states = ["UNCHECKED", "CHECKED", "EXED"]
        current_index = states.index(item.toggle_state)
        item.toggle_state = states[(current_index + 1) % len(states)]
        
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']        
        for obj in selected_meshes:
            obj.load_trigger[self.item_index] = (current_index + 1) % len(states)
            reselect_obj(obj)
        return {'FINISHED'}
    
class AddTrigger(bpy.types.Operator):
    """Add a gameplay trigger to the selected collision"""
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.add_trigger"

    def execute(self, context):
        selected_object = context.active_object
        selected_collection = None
        for collection in bpy.data.collections:
        # Check if the object is in the collection
            if selected_object.name in collection.objects:
                selected_collection = collection
        
        trigger = CollisionTrigger(None, None)
        
        # find center of mass
        center = center_of_mass(selected_object)
        trigger.position.data = center
        new_empty = trigger.make(selected_object, selected_collection)
        bpy.ops.object.select_all(action='DESELECT')
        new_empty.select_set(True)
        bpy.context.view_layer.objects.active = new_empty
        return {'FINISHED'}
    
# MARK: SPLINE

class InvertSpline(bpy.types.Operator):
    """Invert the selected spline"""
    bl_label = "Invert Spline"
    bl_idname = "view3d.invert_spline"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'CURVE':
            self.report({'ERROR'}, "No active curve object")
            return {'CANCELLED'}
        
        curve = obj.data

        # Ensure we're in Object Mode to modify splines safely
        bpy.ops.object.mode_set(mode='OBJECT')

        for spline in curve.splines:
            if spline.type == 'BEZIER':
                num_points = len(bezier_points)
                bezier_points = list(spline.bezier_points)  # Convert to a list

                # Reverse the order of points
                new_points = [bezier_points[i] for i in range(num_points - 1, -1, -1)]

                # Swap handle positions to maintain curve shape
                for i in range(num_points):
                    new_points[i].co, bezier_points[i].co = bezier_points[i].co, new_points[i].co
                    new_points[i].handle_left, bezier_points[i].handle_left = bezier_points[i].handle_right, new_points[i].handle_right
                    new_points[i].handle_right, bezier_points[i].handle_right = bezier_points[i].handle_left, new_points[i].handle_right

        # Return to Edit Mode
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}
  
class SplineCyclic(bpy.types.Operator):
    """Toggle the selected spline between open (rally) and closed (circuit)"""
    bl_idname = "view3d.toggle_cyclic"
    bl_label = "Toggle Spline Cyclic"
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'CURVE' and obj.data.splines.active

    def execute(self, context):
        obj = context.active_object
        spline = obj.data.splines.active
        
        if spline:
            spline.use_cyclic_u = not spline.use_cyclic_u
            
        return {'FINISHED'}
    
class ReconstructSpline(bpy.types.Operator):
    """Set selected point as start/finish line"""
    bl_idname = "view3d.reconstruct_spline"
    bl_label = "Reconstruct Spline with Selected Point as First"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'CURVE' and obj.data.splines.active and len(obj.data.splines.active.bezier_points) > 1

    def execute(self, context):
        obj = context.active_object
        spline = obj.data.splines.active

        if spline and len(spline.bezier_points) > 1:
            selected_point_index = None

            # Find selected point
            for i, point in enumerate(spline.bezier_points):
                if point.select_control_point:
                    selected_point_index = i
                    break

            if selected_point_index is not None:
                # Reconstruct the spline with the selected point as the first point
                new_points = spline.bezier_points[selected_point_index:] + spline.bezier_points[:selected_point_index]

                # Create a new list for control points, handles, and tilts
                new_coords = [p.co.copy() for p in new_points]
                new_handles_left = [p.handle_left.copy() for p in new_points]
                new_handles_right = [p.handle_right.copy() for p in new_points]
                new_radii = [p.radius for p in new_points]
                new_tilts = [p.tilt for p in new_points]

                # Assign new values to the original points
                for i, point in enumerate(spline.bezier_points):
                    point.co = new_coords[i]
                    point.handle_left = new_handles_left[i]
                    point.handle_right = new_handles_right[i]
                    point.radius = new_radii[i]
                    point.tilt = new_tilts[i]
                
                bpy.ops.curve.select_all(action='DESELECT')
                obj.data.splines.active.bezier_points[0].select_control_point = True

        return {'FINISHED'}
    
class SelectFirstSplinePointOperator(bpy.types.Operator):
    """Select First Point (Spawn Point) of Spline"""
    bl_idname = "curve.select_first_spline_point"
    bl_label = "Select First Spline Point"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object

        if obj is None or obj.type != 'CURVE':
            self.report({'ERROR'}, "Active object is not a curve")
            return {'CANCELLED'}
            
        # Enter edit mode if not already in edit mode
        if bpy.context.mode != 'EDIT_CURVE':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Deselect all points first
        bpy.ops.curve.select_all(action='DESELECT')
        
        # Access the curve data in edit mode
        curve_data = obj.data

        if not curve_data.splines:
            self.report({'WARNING'}, "No splines found in the curve")
            return {'CANCELLED'}            
            
        active_spline = curve_data.splines.active

        # Select the first point depending on spline type
        if active_spline.bezier_points:
            active_spline.bezier_points[0].select_control_point = True
        elif active_spline.points:
            active_spline.points[0].select_control_point = True
        
        # Update the view with the selection
        context.view_layer.update()
        return {'FINISHED'}
    
# MARK: MISC
    
class OpenUrl(bpy.types.Operator):
    """Open link"""
    bl_idname = "view3d.open_url"
    bl_description = "Open URL"
    bl_label = "Open URL"

    url: bpy.props.StringProperty("")
        
    def execute(self, context):
        open_url(self.url)
        return {"FINISHED"}

class AddImageTexture(bpy.types.Operator):
    """Open link"""
    bl_idname = "view3d.open_url"
    bl_description = "Open URL"
    bl_label = "Open URL"

    def execute(self, context):
        open_url(self.url)
        return {"FINISHED"}

# MARK: REGISTER

register_classes = (
    RemakeMaterials,
    ResetTexture,
    ResetVisuals,
    ResetTerrain,
    ResetFog,
    ResetLighting,
    ResetLoading,
    ResetCollidable,
    ImportOperator,
    ExportOperator,
    NewModelOperator,
    ResetVColor,
    PreviewLoadTrigger,
    SelectByProperty,
    AddTrigger,
    InvertSpline,
    SplineCyclic,
    ReconstructSpline,
    OpenUrl,
    BakeVColors,
    OpenImageTexture,
    SelectFirstSplinePointOperator,
    ToggleViewLayerState
)

def register():
    for c in register_classes:
        bpy.utils.register_class(c)
    
def unregister():
    for c in register_classes:
        bpy.utils.unregister_class(c)
