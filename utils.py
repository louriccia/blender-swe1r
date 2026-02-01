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
import json
import os
import math
import webbrowser
import bpy
import mathutils
import copy

from .swe1r.model_list import *

# 'bswe1r' for 'blender swe1r'
# NOTE: use 3-letter code for data_type and group_id
data_name_prefix_short = 'bswe1r_'
data_name_format_short = 'bswe1r_{label}'
data_name_prefix_short_len = 7
data_name_format = 'bswe1r_{data_type}_{label}'
data_name_prefix_len = 11
data_name_format_long = 'bswe1r_{data_type}_{group_id}_{label}'
data_name_format_long_len = 15

model_types = [
    ('0', 'All', 'View all models'),
    ('1', 'MAlt', 'High LOD Pod Models'),
    ('2', 'Modl', 'Misc animated elements'),
    ('3', 'Part', 'Misc props'),
    ('4', 'Podd', 'Pod models'),
    ('5', 'Pupp', 'Animated characters'),
    ('6', 'Scen', 'Animated scenes'),
    ('7', 'Trak', 'Tracks'),
    ]

header_sizes = [-1,75, 1,2,75,9, 83,6]

Podd_MAlt = {
    "2": 0,
    "4": 3,
    "6": 5,
    "8": 7,
    "9": 10,
    "12": 11,
    "14": 13,
    "17": 15,
    "16": 18,
    "20": 19,
    "22": 21,
    "24": 23,
    "26": 25,
    "28": 27,
    "30": 29,
    "32": 31,
    "34": 33,
    "36": 35,
    "38": 37,
    "40": 39,
    "42": 41,
    "44": 43,
    "46": 45,
    "299": 298,
    "301": 300
}

showbytes = {
    "115": 16,
    "142": 16,
    "130": 16,
    "133": 16,
    "232": 16,
    "145": 16,
    "143": 32,
    "134": 32,
    "131": 32,
    "233": 32,
    "136": 16,
    "144": 64,
    "139": 16,
    "135": 64,
    "148": 32,
    "315": 64,
    "140": 16,
    "132": 64,
    "137": 32,
    "141": 16,
    "1": 16,
    "128": 16,
    "138": 64,
    "231": 64,
    "129": 16
}

SETTINGS_FILE = os.path.join(bpy.utils.user_resource('CONFIG'), "blender_swe1r_settings.json")

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
    
def export_model_items(self, context):
    model_type = model_types[int(self.export_type)][1]
    items_for_selected_category = [(str(i), f"{model['name']}", f"Import model {model['name']}") for i, model in enumerate(model_list) if model['extension'] == model_type]
    return items_for_selected_category

def update_selected(prop_name, update_mat = False, update_tex = False):
    def update_function(self, context):
        if context.scene.podblock_syncing:
            return
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                if update_mat:
                    from .swe1r.modelblock import Material
                    mats = [slot.material for slot in obj.material_slots]
                    for mat in mats:
                        if mat is None: continue
                        # if update_tex and mat.node_tree:
                        #     for node in mat.node_tree.nodes:
                        #         if node.type == 'TEX_IMAGE':
                        #             node.image = context.scene[prop_name]
                        elif update_tex is False:
                            if hasattr(mat, prop_name):
                                setattr(mat, prop_name, getattr(context.scene, prop_name))
                            elif hasattr(mat.data, prop_name):
                                setattr(mat.data, prop_name, getattr(context.scene, prop_name))
                                
                        if len(mats):
                            mat = mats[0]
                            if prop_name == 'texture' and context.scene[prop_name]:
                                mat = Material(None, None).remake(mat, tex_name = context.scene[prop_name].name)
                            else:
                                mat = Material(None, None).remake(mat)
                            obj.material_slots[0].material = mat
                else:
                    if hasattr(obj, prop_name):
                        setattr(obj, prop_name, getattr(context.scene, prop_name))
                    elif hasattr(obj.data, prop_name):
                        setattr(obj.data, prop_name, getattr(context.scene, prop_name))
    return update_function
    
def SplineVis(self, context = None):
    for obj in bpy.context.scene.objects:
        if obj.type == "CURVE":
            obj.hide_viewport = not context.scene.spline_visible

def ColVis(self, context = None):
    for obj in bpy.context.scene.objects:
        if obj.collidable:
            obj.hide_viewport = not context.scene.collision_visible
            
def ShoVis(self, context = None):
    for obj in bpy.context.scene.objects:
        if obj.visible:
            obj.hide_viewport = not context.scene.visuals_visible
                
def EmptyVis(self, context):
    for obj in bpy.context.scene.objects:
        if obj.type == "EMPTY" or obj.type == "LIGHT":
            obj.hide_viewport = not context.scene.emptyvis
            
def UpdateVisibleSelectable(self, context = None):
    if context is None:
        context = bpy.context
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        if obj.collidable:
            obj.hide_viewport = not context.scene.collision_visible
            obj.hide_select = not context.scene.collision_selectable
            obj.hide_set(not context.scene.collision_visible, view_layer=context.view_layer)
            
        if obj.visible:
            obj.hide_viewport =  not context.scene.visuals_visible
            obj.hide_select = not context.scene.visuals_selectable
            obj.hide_set(not context.scene.visuals_visible, view_layer=context.view_layer)
            
            
    
def save_settings(self, context):
    keys = ['import_folder', 'import_type', 'import_model', 'export_folder', 'is_export_model', 'is_export_texture', 'is_export_spline']
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

def euclidean_distance(color1, color2):
    return math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color1, color2)))

def blend_multiply(a: float, b: float) -> float:
    return a*b 

def blend_overlay(a: float, b: float) -> float:
    return 2.0*a*b if a < 0.5 else 1.0-2.0*(1.0-a)*(1.0-b) 

def calculate_point_light_contribution(light, vertex_position, vertex_normal, depsgraph, falloff_factor):
    light_position = light.matrix_world.to_translation()
    light_color =light.data.color
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
    
    # Calculate the normal transformation matrix
    normal_matrix = world_matrix.to_3x3().inverted().transposed()
    
    # Iterate over all lights in the scene
    for light in bpy.context.scene.objects:
        if light.type == 'LIGHT':
            for vertex in mesh.vertices:
                # Transform vertex coordinates and normal to world space
                vertex_world_co = world_matrix @ vertex.co
                vertex_normal_world = world_matrix.to_3x3() @ vertex.normal
                if light.data.type == 'POINT':
                    light_contribution = calculate_point_light_contribution(light, vertex_world_co, vertex.normal, depsgraph, falloff_factor)
                    total_lights[vertex.index] = light_contribution + total_lights[vertex.index]
                elif light.data.type == 'SUN':
                    light_contribution = calculate_sun_light_contribution(light, vertex_world_co, vertex.normal, depsgraph)
                    total_lights[vertex.index] = light_contribution + total_lights[vertex.index] 

    return total_lights

updating_objects = set()

def create_update_function(prop_name):
    def update_function(self, context):
        global updating_objects
        
        # Check if the current object is already being updated
        if self in updating_objects:
            return
        
        try:
            # Add the current object to the set of updating objects
            updating_objects.add(self)
            
            # Update the property for all selected objects except the current one
            for obj in context.selected_objects:
                if obj != self and hasattr(obj, prop_name):
                    setattr(obj, prop_name, getattr(self, prop_name))
                elif hasattr(obj.data, prop_name):
                    setattr(obj.data, prop_name, getattr(self, prop_name))
                    
        finally:
            # Remove the current object from the updating set after updating
            updating_objects.discard(self)
    return update_function

name_attr_colors = data_name_format_short.format(label='colors')
name_attr_baked = data_name_format_short.format(label='colors_baked')

def init_vertex_colors(b_obj):
    if b_obj.type != 'MESH' or not b_obj.get('visible', False):
        return

    if not hasattr(b_obj.data, 'color_attributes') or len(b_obj.data.color_attributes) == 0:
        b_obj.data.color_attributes.new(name_attr_colors, 'BYTE_COLOR', 'CORNER')
        b_obj.data.attributes.render_color_index = b_obj.data.attributes.active_color_index

        for color in b_obj.data.attributes[name_attr_colors].data:
            color.color = [1.0, 1.0, 1.0, 1.0]

def reset_vertex_colors(b_obj):
    if b_obj.type != 'MESH' or not b_obj.get('visible', False):
        return

    if not hasattr(b_obj.data, 'color_attributes') or len(b_obj.data.color_attributes) == 0:
        b_obj.data.color_attributes.new(name_attr_colors, 'BYTE_COLOR', 'CORNER')
        b_obj.data.attributes.render_color_index = b_obj.data.attributes.active_color_index

        for color in b_obj.data.attributes[name_attr_colors].data:
            color.color = [1.0, 1.0, 1.0, 1.0]

    #use first color layer if no active layer
    if b_obj.data.vertex_colors.active is None:
        b_obj.data.vertex_colors.active_index = 0

    color_layer = b_obj.data.vertex_colors.active.data
    for loop in color_layer:
        loop.color = [1.0, 1.0, 1.0, 1.0]

    color_baked = b_obj.data.attributes.get(name_attr_baked)
    if color_baked is not None and b_obj.data.attributes.default_color_name != name_attr_baked:
        b_obj.data.attributes.remove(color_baked)
            
def populate_enum(scene, context):

    current_view_layers = [None]

    for view_layer in bpy.context.scene.view_layers.items():
        current_view_layers.append((view_layer[0],view_layer[0], ""),)
 
    return current_view_layers


# checks if normals will be flipped after applying scale due to object-parent 
# chain resolving to negative scale
def check_flipped(o):
    flipped = False
    while o.parent is not None:
        flipped = not(flipped) if [n < 0 for n in o.scale].count(True) % 2 else flipped
        o = o.parent
    return flipped

def center_of_mass(o):
    mesh = o.data
    total = mathutils.Vector((0, 0, 0))
    num_verts = len(mesh.vertices)

    # Sum all vertex coordinates
    for vert in mesh.vertices:
        total += o.matrix_world @ vert.co

    # Average the positions to get the center of mass in local coordinates
    center_of_mass_local = total / num_verts

    # Convert to world coordinates
    return [mass / o.scale[i] for i, mass in enumerate(center_of_mass_local)]
    
def show_custom_popup(context, title, message):
    def draw(self, context):
        layout = self.layout
        layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon='INFO')
    
def reselect_obj(obj):
    obj.select_set(False)
    obj.select_set(True)
    
    
def validate_folder_path(folder_path, file_name):
    if folder_path == "":
        show_custom_popup(bpy.context, "No set import folder", "Select your folder containing the .bin files")
        return {'CANCELLED'}
    if folder_path[:2] == '//':
        folder_path = os.path.join(os.path.dirname(bpy.data.filepath), folder_path[2:])
    if not os.path.exists(folder_path  + file_name):
        show_custom_popup(bpy.context, "Missing required files", f"No {file_name} found in the selected folder.")
        return {'CANCELLED'}
    return folder_path

def get_material_hash(material):
    """
    Generate a hash representing the material's properties for deduplication.
    This compares node tree structure and key properties.
    
    Returns:
        str: Hash string representing the material
    """
    if not material.use_nodes:
        return None
    
    hash_parts = []
    nodes = material.node_tree.nodes
    
    # Sort nodes by type and location for consistent ordering
    sorted_nodes = sorted(nodes, key=lambda n: (n.type, n.location.x, n.location.y))
    
    for node in sorted_nodes:
        # Add node type
        hash_parts.append(node.type)
        
        # For image texture nodes, hash the image filepath
        if node.type == 'TEX_IMAGE' and node.image:
            hash_parts.append(node.image.filepath or node.image.name)
        
        # For value/color nodes, hash the values
        elif node.type == 'VALUE':
            hash_parts.append(str(node.outputs[0].default_value))
        elif node.type == 'RGB':
            hash_parts.append(str(node.outputs[0].default_value[:]))
        
        # For BSDF nodes, hash key input values
        elif 'BSDF' in node.type:
            for input in node.inputs:
                if not input.is_linked:
                    hash_parts.append(f"{input.name}:{input.default_value}")
    
    # Hash the connections
    links = material.node_tree.links
    for link in sorted(links, key=lambda l: (l.from_node.name, l.to_node.name)):
        hash_parts.append(f"{link.from_socket.name}->{link.to_socket.name}")
    
    # Create hash from all parts
    import hashlib
    hash_string = "|".join(str(p) for p in hash_parts)
    return hashlib.md5(hash_string.encode()).hexdigest()

import bpy
import os
import hashlib
import traceback

def create_material_from_image(image_path, material_name):
    """
    Create a material with an image texture and return the material.
    
    Args:
        image_path: Full path to the image file
        material_name: Name for the material
    
    Returns:
        bpy.types.Material: The created material
    """
    # Create new material
    mat = bpy.data.materials.new(name=material_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Clear default nodes
    nodes.clear()
    
    # Create nodes
    node_tex = nodes.new(type='ShaderNodeTexImage')
    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    
    # Load image
    if os.path.exists(image_path):
        img = bpy.data.images.load(image_path)
        node_tex.image = img
    
    # Position nodes for cleaner node tree
    node_tex.location = (-300, 0)
    node_bsdf.location = (0, 0)
    node_output.location = (300, 0)
    
    # Link nodes
    links.new(node_tex.outputs['Color'], node_bsdf.inputs['Base Color'])
    links.new(node_bsdf.outputs['BSDF'], node_output.inputs['Surface'])
    
    return mat


def mark_material_as_asset(material, catalog_id=None, tags=None):
    """
    Mark a material as an asset and optionally assign it to a catalog.
    
    Args:
        material: The material to mark as asset
        catalog_id: UUID string of the catalog (e.g., "a8e1a507-d4e9-4f8f-a7e7-5e6f7d8e9f0a")
        tags: List of tag strings to add to the asset
    """
    # Mark as asset
    material.asset_mark()
    
    # Set catalog if provided (must be a valid UUID)
    if catalog_id:
        material.asset_data.catalog_id = catalog_id
    
    # Add tags if provided
    if tags:
        for tag in tags:
            material.asset_data.tags.new(tag)
    
    # Generate preview (this will use default material preview)
    material.asset_generate_preview()


def get_material_hash(material):
    """
    Generate a hash representing the material's properties for deduplication.
    This compares node tree structure and key properties.
    
    Returns:
        str: Hash string representing the material
    """
    if not material.use_nodes:
        return None
    
    hash_parts = []
    nodes = material.node_tree.nodes
    
    # Sort nodes by type and location for consistent ordering
    sorted_nodes = sorted(nodes, key=lambda n: (n.type, n.location.x, n.location.y))
    
    for node in sorted_nodes:
        # Add node type
        hash_parts.append(node.type)
        
        # For image texture nodes, hash the image filepath
        if node.type == 'TEX_IMAGE' and node.image:
            hash_parts.append(node.image.filepath or node.image.name)
        
        # For value/color nodes, hash the values
        elif node.type == 'VALUE':
            hash_parts.append(str(node.outputs[0].default_value))
        elif node.type == 'RGB':
            hash_parts.append(str(node.outputs[0].default_value[:]))
        
        # For BSDF nodes, hash key input values
        elif 'BSDF' in node.type:
            for input in node.inputs:
                if not input.is_linked:
                    hash_parts.append(f"{input.name}:{input.default_value}")
    
    # Hash the connections
    links = material.node_tree.links
    for link in sorted(links, key=lambda l: (l.from_node.name, l.to_node.name)):
        hash_parts.append(f"{link.from_socket.name}->{link.to_socket.name}")
    
    # Create hash from all parts
    import hashlib
    hash_string = "|".join(str(p) for p in hash_parts)
    return hashlib.md5(hash_string.encode()).hexdigest()


def deduplicate_materials(materials):
    """
    Remove duplicate materials based on their properties.
    
    Args:
        materials: List of materials to deduplicate
    
    Returns:
        list: Deduplicated list of materials
    """
    # Filter out any materials that have already been removed
    valid_materials = []
    for mat in materials:
        try:
            # Try to access a property to check if material still exists
            _ = mat.name
            valid_materials.append(mat)
        except ReferenceError:
            # Material was already removed, skip it
            continue
    
    # First, compute all hashes before removing anything
    material_hashes = []
    for mat in valid_materials:
        mat_hash = get_material_hash(mat)
        material_hashes.append((mat, mat_hash))
    
    # Now deduplicate based on hashes
    seen_hashes = {}
    unique_materials = []
    duplicates_to_remove = []
    
    for mat, mat_hash in material_hashes:
        if mat_hash is None:
            # Can't hash this material, keep it
            unique_materials.append(mat)
            continue
        
        if mat_hash in seen_hashes:
            # Duplicate found - mark for removal
            duplicates_to_remove.append(mat)
        else:
            # New unique material
            seen_hashes[mat_hash] = mat
            unique_materials.append(mat)
    
    # Remove duplicates after processing
    for mat in duplicates_to_remove:
        try:
            bpy.data.materials.remove(mat)
        except ReferenceError:
            # Material was already removed elsewhere
            pass
    
    print(f"Started with {len(materials)} materials, {len(valid_materials)} were valid")
    print(f"Removed {len(duplicates_to_remove)} duplicate materials")
    print(f"Final unique materials: {len(unique_materials)}")
    return unique_materials