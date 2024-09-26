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
from .swe1r.splineblock import *
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

# WARN: the way this is actually used is more like "reset visuals"; could be
# merged with VisibleOperator
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
            init_vertex_colors(obj)
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

# BAKE LIGHTING TO VERTEX COLORS

def bake_vertex_colors(b_context, b_obj_list):
    errlist_mismatch = []
    errlist_nodata = []

    for obj in b_obj_list:
        if obj.type != 'MESH' or not obj.get('visible', False):
            continue

        d = obj.data

        if len(d.color_attributes) == 0:
            reset_vertex_colors(obj)

        if d.attributes.default_color_name == name_attr_baked:
            errlist_mismatch.append(obj.name)
            continue

        color_base = d.attributes[d.attributes.default_color_name].data
        if len(color_base) == 0:
            errlist_nodata.append(obj.name)
            continue

        # Calculate the total light for each vertex of the selected object
        total_lights = calculate_total_light_for_object(obj, b_context.scene.light_falloff, b_context.scene.ambient_light_intensity, b_context.scene.ambient_light)
        
        color_layer = d.attributes.get(name_attr_baked)
        if color_layer is not None:
            color_layer = color_layer.data
        else:
            d.color_attributes.new(name_attr_baked, 'BYTE_COLOR', 'CORNER') 
            color_layer = d.attributes[name_attr_baked].data

        for poly in d.polygons:
            for p in range(len(poly.vertices)):
                color = total_lights[poly.vertices[p]]
                a_col = color_base[poly.loop_indices[p]].color # old color
                for i, b in enumerate([*color, 1.0]):
                    color_layer[poly.loop_indices[p]].color[i] = blend_multiply(a_col[i], b)

    if len(errlist_mismatch) > 0:
        show_custom_popup(bpy.context, 'ERROR', 'Baking target was base color map. Choose another Render Color or rename. Affected objects: {}'.format(', '.join(errlist_mismatch)))

    if len(errlist_nodata) > 0:
        show_custom_popup(bpy.context, 'ERROR', 'Base color map has no color data. Data may have been purged. Affected objects: {}'.format(', '.join(errlist_nodata)))

def bake_vertex_colors_clear(b_context, b_obj_list):
    errlist_mismatch = []
    for obj in b_obj_list:
        if obj.type != 'MESH' or not obj.get('visible', False):
            continue

        color_layer = obj.data.attributes.get(name_attr_baked)
        if color_layer is not None:
            if obj.data.attributes.default_color_name == name_attr_baked:
                errlist_mismatch.append(obj.name)
                continue

            obj.data.attributes.remove(color_layer)

    if len(errlist_mismatch) > 0:
        show_custom_popup(bpy.context, 'ERROR', 'Baked lighting was in base color map. Skipped deleting bake. Affected objects: {}'.format(', '.join(errlist_mismatch)))

class BakeVColors(bpy.types.Operator):
    bl_idname = "view3d.bake_vcolors"
    bl_label = "Bake Vertex Colors"
    bl_description = "Bake lighting into dedicated color map, while preserving Render Color"
    
    def execute(self, context):
        bake_vertex_colors(context, context.selected_objects)
        return {"FINISHED"}
    
class BakeVColorsClear(bpy.types.Operator):
    bl_idname = "view3d.bake_vcolors_clear"
    bl_label = "Clear Baked Lighting"
    bl_description = "Remove baked lighting color map from Color Attributes"

    def execute(self, context):
        bake_vertex_colors_clear(context, context.selected_objects)
        return {"FINISHED"}

class BakeVColorsCollection(bpy.types.Operator):
    bl_idname = "outliner.collection_bake"
    bl_label = "Bake Lighting on Collection"

    @classmethod
    def poll(cls, context):
        return context.collection is not None

    def execute(self, context):
        bake_vertex_colors(context, context.collection.all_objects)
        return {'FINISHED'}

class BakeVColorsCollectionClear(bpy.types.Operator):
    bl_idname = "outliner.collection_bake_clear"
    bl_label = "Remove Baked Lighting from Collection"

    @classmethod
    def poll(cls, context):
        return context.collection is not None

    def execute(self, context):
        bake_vertex_colors_clear(context, context.collection.all_objects)
        return {'FINISHED'}

# OUTLINER > COLLECTION context menu

def draw_OUTLINER_MT_collection(self, context):
    self.layout.separator()
    self.layout.label(text='SWE1R Import/Export')
    self.layout.operator('outliner.collection_bake', text='Bake Lighting', icon='LIGHT_SUN')
    self.layout.operator('outliner.collection_bake_clear', text='Remove Baked Lighting')

# REGISTER

register_classes = (
    ImportOperator,
    ExportOperator,
    VertexColorOperator,
    VisibleOperator,
    CollidableOperator,
    VisibleSelect,
    CollidableSelect,
    AddCollisionData,
    ResetCollisionData,
    NonVisibleOperator,
    NonCollidableOperator,
    AddTrigger,
    InvertSpline,
    SplineCyclic,
    ReconstructSpline,
    OpenUrl,
    BakeVColors,
    BakeVColorsClear,
    BakeVColorsCollection,
    BakeVColorsCollectionClear,
)

def register():
    for c in register_classes:
        bpy.utils.register_class(c)
    bpy.types.OUTLINER_MT_collection.append(draw_OUTLINER_MT_collection)
    
def unregister():
    for c in register_classes:
        bpy.utils.unregister_class(c)
    bpy.types.OUTLINER_MT_collection.remove(draw_OUTLINER_MT_collection)
