import bpy
import json
import os
import math
import webbrowser
import bpy
import mathutils
import copy

from .swe1r.model_list import *


SETTINGS_FILE = os.path.join(bpy.utils.user_resource('CONFIG'), "blender_swe1r_settings.json")

model_types = [
    ('0', 'All', 'View all models'),
    ('1', 'MAlt', 'High LOD pods'),
    ('2', 'Modl', 'Misc animated elements'),
    ('3', 'Part', 'Misc props'),
    ('4', 'Podd', 'Pod models'),
    ('5', 'Pupp', 'Animated racers'),
    ('6', 'Scen', 'Animated scenes'),
    ('7', 'Trak', 'Tracks'),
    ]

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
    
def SplineVis(self, context = None):
    for obj in bpy.context.scene.objects:
        if obj.type == "CURVE":
            obj.hide_viewport = not context.scene.spline_visible

def ColVis(self, context = None):
    for obj in bpy.context.scene.objects:
        if 'collidable' in obj and obj['collidable']:
            obj.hide_viewport = not context.scene.collision_visible
            
def ShoVis(self, context = None):
    for obj in bpy.context.scene.objects:
        if 'visible' in obj and obj['visible']:
            obj.hide_viewport = not context.scene.visuals_visible
                
def EmptyVis(self, context):
    for obj in bpy.context.scene.objects:
        if obj.type == "EMPTY" or obj.type == "LIGHT":
            obj.hide_viewport = not context.scene.emptyvis
    
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

def SelVis(self, context = None):
    for obj in bpy.context.scene.objects:
        if 'visible' in obj and obj['visible']:
            obj.hide_select = not context.scene.visuals_selectable

def SelCol(self, context = None):
    for obj in bpy.context.scene.objects:
        if 'collidable' in obj and obj['collidable']:
            obj.hide_select = not context.scene.collision_selectable
            
def open_url(url: str) -> None:
    webbrowser.open(url)
    
def clamp(value, min_value, max_value):
    return max(min(value, max_value), min_value)

def euclidean_distance(color1, color2):
    return math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color1, color2)))

def calculate_point_light_contribution(light, vertex_position, vertex_normal, depsgraph, falloff_factor):
    light_position = light.location
    light_color = light.data.color

    # Vector from the vertex to the light
    light_direction = light_position - vertex_position
    light_distance = light_direction.length
    light_direction.normalize()

    # Calculate the angle between the vertex normal and the light direction
    angle_cos = vertex_normal.dot(light_direction)

    # Check for occlusion using ray_cast
    hit, location, normal, index, obj, matrix = bpy.context.scene.ray_cast(
        depsgraph,
        vertex_position + vertex_normal * 0.001,  # Move start point slightly off the surface
        light_direction
    )

    if hit and (location - vertex_position).length < light_distance:
        # If hit and the hit location is closer than the light, it's in shadow
        return mathutils.Color((0, 0, 0))

    # Calculate the contribution of the light with adjusted falloff
    if angle_cos > 0:
        return light_color * angle_cos / (light_distance ** falloff_factor)
    else:
        return mathutils.Color((0, 0, 0))

def calculate_sun_light_contribution(light, vertex_position, vertex_normal, depsgraph):
    light_direction = light.rotation_euler.to_matrix().col[2]
    light_color = light.data.color

    # Calculate the angle between the vertex normal and the light direction
    angle_cos = vertex_normal.dot(light_direction)

    # Check for occlusion using ray_cast
    hit, location, normal, index, obj, matrix = bpy.context.scene.ray_cast(
        depsgraph,
        vertex_position + vertex_normal * 0.001,  # Move start point slightly off the surface
        light_direction
    )

    if hit:
        # If hit, it's in shadow
        return mathutils.Color((0, 0, 0))

    # Calculate the contribution of the light
    if angle_cos > 0:
        return light_color * angle_cos
    else:
        return mathutils.Color((0, 0, 0))


def calculate_total_light_for_object(obj, falloff_factor=2.0, ambient_light_intensity=0.1, ambient_light_color=[0, 0, 0]):
    mesh = obj.data
    depsgraph = bpy.context.evaluated_depsgraph_get()
    world_matrix = obj.matrix_world

    # Create a dictionary to store the total light for each vertex
    ambient_light_color_copy = copy.copy(ambient_light_color)
    total_lights = {v.index: ambient_light_color_copy for v in mesh.vertices}
    print(total_lights)
    # Iterate over all lights in the scene
    for light in bpy.context.scene.objects:
        if light.type == 'LIGHT':
            for vertex in mesh.vertices:
                # Transform vertex coordinates and normal to world space
                vertex_world_co = world_matrix @ vertex.co
                vertex_normal_world = world_matrix.to_3x3() @ vertex.normal

                if light.data.type == 'POINT':
                    total_lights[vertex.index] += calculate_point_light_contribution(light, vertex_world_co, vertex_normal_world, depsgraph, falloff_factor)
                elif light.data.type == 'SUN':
                    total_lights[vertex.index] += calculate_sun_light_contribution(light, vertex_world_co, vertex_normal_world, depsgraph)

    return total_lights

updating_objects = set()

def create_update_function(prop_name):
    def update_function(self, context):
        print('Updating property', prop_name)
        global updating_objects
        
        # Check if the current object is already being updated
        if self in updating_objects:
            return
        
        try:
            # Add the current object to the set of updating objects
            updating_objects.add(self)
            
            # Update the property for all selected objects except the current one
            for obj in context.selected_objects:
                if obj != self:
                    setattr(obj, prop_name, getattr(self, prop_name))
                    
        finally:
            # Remove the current object from the updating set after updating
            updating_objects.discard(self)
    return update_function

def reset_vertex_colors(obj):
    if not hasattr(obj.data, 'vertex_colors') or obj.data.vertex_colors.active is None:
        obj.data.vertex_colors.new(name = 'colors')
            
    color_layer = obj.data.vertex_colors.active.data   
    for poly in obj.data.polygons:
        for loop_index in poly.loop_indices:
            color_layer[loop_index].color = [1.0, 1.0, 1.0, 1.0]
            
def populate_enum(scene, context):

    current_view_layers = [None]

    for view_layer in bpy.context.scene.view_layers.items():
        current_view_layers.append((view_layer[0],view_layer[0], ""),)
 
    return current_view_layers