import bpy
import sys
import importlib

modules = [
    'swr_import',
    'swr_export',
    'popup',
    'panels',
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

from .popup import *
from .swe1r.model_list import *
from .swe1r.modelblock import *
from .swe1r.block import *
from .swe1r.textureblock import *
from  .swe1r.splineblock import *
from .swe1r.general import *
from .panels import *
from .swr_import import *
from .swr_export import *
from .utils import *

class ImportOperator(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.import_operator"
    

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
    
class VertexColorOperator(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.v_color"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            reset_vertex_colors(obj)

        return {'FINISHED'}
  
class VisibleOperator(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.set_visible"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            obj['visible'] = True
            reset_vertex_colors(obj)
        return {'FINISHED'}
    
class NonVisibleOperator(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.set_nonvisible"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            obj['visible'] = False
        return {'FINISHED'}

class CollidableOperator(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.set_collidable"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            obj['collidable'] = True
        return {'FINISHED'}    

class NonCollidableOperator(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.set_noncollidable"
    
    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            obj['collidable'] = False
        return {'FINISHED'}
    
class VisibleSelect(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.select_visible"
    
    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        
        #make selectable
        if not context.scene.visuals_selectable:
            context.scene.visuals_selectable = True
        
        for obj in bpy.context.scene.objects:
            if 'visible' in obj and obj['visible']:
                obj.hide_select = False
                obj.select_set(True)
                
        return {'FINISHED'}
    
class CollidableSelect(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.select_collidable"
    
    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        
        #make selectable
        if not context.scene.collision_selectable:
            context.scene.collision_selectable = True
        
        for obj in  bpy.context.scene.objects:
            if 'collidable' in obj and obj['collidable']:
                obj.hide_select = False
                obj.select_set(True)
        return {'FINISHED'}
    
class AddCollisionData(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.add_collision_data"

    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            if 'collision_data' not in obj or not obj['collision_data']:
                CollisionTags(None, None).make(obj)
        return {'FINISHED'}
    
class ResetCollisionData(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.reset_collision_data"

    def execute(self, context):
        selected_objects = context.selected_objects
        for obj in selected_objects:
            CollisionTags(None, None).make(obj)
        return {'FINISHED'}
    
class AddTrigger(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.add_trigger"

    def execute(self, context):
        selected_object = context.active_object
        selected_collection = None
        for collection in bpy.data.collections:
        # Check if the object is in the collection
            if selected_object.name in collection.objects:
                selected_collection = collection
        
        trigger = CollisionTrigger(None, None).make(selected_object, selected_collection)
        return {'FINISHED'}
    

class InvertSpline(bpy.types.Operator):
    bl_label = "SWE1R Import/Export"
    bl_idname = "view3d.invert_spline"

    def execute(self, context):
        for spline in context.active_object.data.splines:
            if spline.type == 'BEZIER':
                points = spline.bezier_points
                n = len(points)
                
                # Swap control points to reverse the curve
                for i in range(n // 2):
                    points[i].co, points[n - i - 1].co = points[n - i - 1].co.copy(), points[i].co.copy()
                    points[i].handle_left, points[n - i - 1].handle_right = points[n - i - 1].handle_right.copy(), points[i].handle_left.copy()
                    points[i].handle_right, points[n - i - 1].handle_left = points[n - i - 1].handle_left.copy(), points[i].handle_right.copy()

                if n % 2 == 1:
                    points[n // 2].handle_right, points[n // 2].handle_left = points[n // 2].handle_left.copy(), points[n // 2].handle_right.copy()

                # Flip the handles direction for the first and last points after reversal
                #points[0].handle_left, points[0].handle_right = points[0].handle_right.copy(), points[0].handle_left.copy()
                #points[-1].handle_left, points[-1].handle_right = points[-1].handle_right.copy(), points[-1].handle_left.copy()
        return {"FINISHED"}
    
class SplineCyclic(bpy.types.Operator):
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

        return {'FINISHED'}
    
class OpenUrl(bpy.types.Operator):
    bl_idname = "view3d.open_url"
    bl_description = "Open URL"
    bl_label = "Open URL"

    url: bpy.props.StringProperty("")
        
    def execute(self, context):
        open_url(self.url)
        return {"FINISHED"}
    
class BakeVColors(bpy.types.Operator):
    bl_idname = "view3d.bake_vcolors"
    bl_label = "Bake Vertex Colors"
    
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
                
        return {"FINISHED"}
    
def register():
    bpy.utils.register_class(ImportOperator)
    bpy.utils.register_class(ExportOperator)
    bpy.utils.register_class(VertexColorOperator)
    bpy.utils.register_class(VisibleOperator)
    bpy.utils.register_class(CollidableOperator)
    bpy.utils.register_class(VisibleSelect)
    bpy.utils.register_class(CollidableSelect)
    bpy.utils.register_class(AddCollisionData)
    bpy.utils.register_class(ResetCollisionData)
    bpy.utils.register_class(NonVisibleOperator)
    bpy.utils.register_class(NonCollidableOperator)
    bpy.utils.register_class(AddTrigger)
    bpy.utils.register_class(InvertSpline)
    bpy.utils.register_class(SplineCyclic)
    bpy.utils.register_class(ReconstructSpline)
    bpy.utils.register_class(OpenUrl)
    bpy.utils.register_class(BakeVColors)
    
def unregister():
    bpy.utils.unregister_class(ImportOperator)
    bpy.utils.unregister_class(ExportOperator)
    bpy.utils.unregister_class(VertexColorOperator)
    bpy.utils.unregister_class(VisibleOperator)
    bpy.utils.unregister_class(CollidableOperator)
    bpy.utils.unregister_class(VisibleSelect)
    bpy.utils.unregister_class(CollidableSelect)
    bpy.utils.unregister_class(AddCollisionData)
    bpy.utils.unregister_class(ResetCollisionData)
    bpy.utils.unregister_class(NonVisibleOperator)
    bpy.utils.unregister_class(NonCollidableOperator)
    bpy.utils.unregister_class(AddTrigger)
    bpy.utils.unregister_class(InvertSpline)
    bpy.utils.unregister_class(SplineCyclic)
    bpy.utils.unregister_class(ReconstructSpline)
    bpy.utils.unregister_class(OpenUrl)
    bpy.utils.unregister_class(BakeVColors)