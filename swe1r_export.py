import sys
import os
import bpy
import struct
import json
    
scale = 100
    
def unmake_LStr(objects, model):
    model['Data'] = {'LStr': [], 'other': []}
    for obj in objects:
        if obj.type != 'LIGHT': continue
        model['Data']['LStr'].append([l*scale for l in obj.location])
    
def find_topmost_parent(obj):
    while obj.parent is not None:
        obj = obj.parent
    return obj

def unmake_collision_data(mesh):
    
    if not 'unk' in mesh:
        return 0
    return {
        'unk': mesh['unk'],
        'fog': {
            'flag': mesh['fog_flag'],
            'color': [round(c*255) for c in mesh['fog_color']],
            'start': mesh['fog_start'],
            'end': mesh['fog_stop']
        },
        'lights': {
            'flag': mesh['lights_flag'],
            'ambient_color': [round(c*255) for c in mesh['lights_ambient_color']],
            'color': [round(c*255) for c in mesh['lights_color']],
            'unk1': mesh['unk1'],
            'unk2': mesh['unk2'],
            'pos': [p for p in mesh['lights_pos']],
            'rot': [r for r in mesh['lights_rot']]
        },
        'flags': mesh['flags'],
        'unk2': mesh['unk3'],
        'unload': mesh['unload'],
        'load': mesh['load']
    }

def unmake_collision_vert_buffer(mesh):
    return [[round(co) for co in vert.co] for vert in mesh.data.vertices]

def unmake_collision_vert_strips(mesh):
    #this doesn't stripify the mesh but it is able to recognize existing strips in the faces' vertex indices
    face_buffer = [[v for v in face.vertices] for face in mesh.data.polygons]
    last_face = face_buffer[0]
    strips = []
    strip = 3
    for i, face in enumerate(face_buffer):
        if i == 0:
            continue
        last_face = face_buffer[i-1]
        if strip % 2 == 1 and face[0] == last_face[2] and face[1] == last_face[1]:
            strip+=1
        elif strip % 2 == 0 and face[0] == last_face[0] and face[1] == last_face[2]:
            strip+=1
        else:
            strips.append(strip)
            strip = 3
        
        if i == len(face_buffer) - 1:
            strips.append(strip)
            
    return strips
    
def unmake_visual_vert_buffer(mesh):
    vert_buffer =  [{
            'x': round(vert.co[0]), 
            'y': round(vert.co[1]), 
            'z': round(vert.co[2])
            } for i, vert in enumerate(mesh.data.vertices)]
    
    color_layer = mesh.data.vertex_colors.active.data
    uv_layer = mesh.data.uv_layers.active.data
    
    if color_layer == None or uv_layer == None:
        return vert_buffer    
    
    for poly in mesh.data.polygons:
        for p in range(len(poly.vertices)):
            uv = [round(u*4096) for u in uv_layer[poly.loop_indices[p]].uv]
            vert_buffer[poly.vertices[p]]['uv_x'] = uv[0]
            vert_buffer[poly.vertices[p]]['uv_y'] = uv[1]
            vert_buffer[poly.vertices[p]]['v_color'] = [round(c*255) for c in color_layer[poly.loop_indices[p]].color]
            
    return vert_buffer

def unmake_visual_index_buffer(mesh):
    face_buffer = [[v for v in face.vertices] for face in mesh.data.polygons]
    start = 0
    index_buffer = []
    index_buffer.append({'type': 1, 'start': start})
    i = 0
    #chew through the face buffer and check for 6 chunks because I hate efficiency
    chunk_1_index = 0
    while len(face_buffer):
        if i > 0 and i %30 == 0:
            start += 30
            index_buffer[chunk_1_index]['size'] = i*2
            index_buffer.append({'type': 1, 'start': start})
            chunk_1_index = len(index_buffer) -1
        
        index = face_buffer.pop(0)
        
        if len(face_buffer) and (
            (index[0] == face_buffer[0][1] and index[2] == face_buffer[0][2] and index[1] + 3 == face_buffer[0][0]) or 
            (index[0] == face_buffer[0][0] and index[2] == face_buffer[0][1] and index[1] + 2 == face_buffer[0][2])
            ):
            index_2 = face_buffer.pop(0)
            index.extend(index_2)
            index_buffer.append({
                    'type': 6,
                    'indices': [(f-start)*2 for f in index]
                })
            i += 2
        else:
            index_buffer.append({
                'type': 5,
                'indices': [(f-start)*2 for f in index]
            })
            i+=1
    if chunk_1_index == 0:
        index_buffer[0]['size'] = i*2
    return index_buffer
    
def unmake_material(material):
    format = 4 #all textures have this flag
    backface_culling = material.use_backface_culling #material.use_nodes and material.node_tree.nodes["Principled BSDF"].inputs["Backface Culling"].default_value
    if backface_culling:
        format = format & 8 #this flag is used for single-sidedness
    #if not skybox or effect
    format = format & 2 #most materials use this flag
    
    
    
    
def unmake_mesh_group(mesh):
    mesh_group = {
        'collision': {
            'data': {},
            'vert_buffer': 0,
            'vert_strips': 0,
            'strip_count': 0,
            'strip_size': 3
        },
        'visuals': {
            'material': 0,
            'index_buffer': [],
            'vert_buffer': [],
            'group_parent': 0,
            'group_count': 0
        }
    }
    if mesh['type'] == 'COL':
        mesh_group['collision']['vert_buffer'] = unmake_collision_vert_buffer(mesh)
        mesh_group['collision']['data'] = unmake_collision_data(mesh)
        vert_strips = unmake_collision_vert_strips(mesh)
        if len(vert_strips):
            mesh_group['collision']['strip_count'] = len(vert_strips)
            if all(strip == vert_strips[0] for strip in vert_strips):
                mesh_group['collision']['strip_size'] = vert_strips[0]
            else:
                mesh_group['collision']['vert_strips'] = vert_strips
    elif mesh['type'] == 'VIS':
        mesh_group['visuals']['vert_buffer'] = unmake_visual_vert_buffer(mesh)
        mesh_group['visuals']['index_buffer'] = unmake_visual_index_buffer(mesh)

    return mesh_group
    
def unmake_node(obj):
    node = {
        'id': obj.name,
        'head': [obj['head0'], obj['head1'], obj['head2'], obj['head3'], 0],
        'children': []
    }
    
    if not obj.children:
        return node
    
    mesh_group = (obj.children[0].type == 'MESH')
    
    for child in obj.children:
        if mesh_group: 
            node['children'].append(unmake_mesh_group(child))
        else: 
            node['children'].append(unmake_node(child))
            
    return node
    
def unmake_model(collection):
    
    model = {
        'ext': collection['ext'],
        'id': collection['ind'],
        'header': [h for h in collection['header']],
        'nodes': []
    }
    if 'parent' in col: return
    for child in col.children:
        if 'lightstreaks' in child.name:
            unmake_LStr(child.objects, {})
    
    top_nodes = [] 
    for obj in col.objects:
        if obj.type != 'MESH': continue
        top = find_topmost_parent(obj)
        if top not in top_nodes: top_nodes.append(top)
    
    for node in top_nodes:
        model['nodes'].append(unmake_node(node))
        
    with open('C:/Users/louri/Documents/GitHub/SWE1R-Mods/tools/models/blender/' + str(collection['ind']) + '.json', 'w') as json_file:
        json.dump(model, json_file, indent=2)


def unmake_image(image):
    if not image:
        print("Invalid image provided.")
        return None

    format = image['format']
    width = image.size[0]
    height = image.size[1]
    index = int(image.name)  # Assuming the name represents the index

    pixels = []
    palette = []

    for i in range(height):
        for j in range(width):
            pixel_index = (i * width + j) * 4  # Each pixel has 4 components (RGBA)
            color = image.pixels[pixel_index:pixel_index + 4]
            pixels.extend(color)

            # Assuming format 512 or 513 corresponds to a palette
            if format in [512, 513] and color not in palette:
                palette.append(color)

    return pixels, palette, index


for col in bpy.data.collections:
    if col['type'] == 'MODEL':
        unmake_model(col)
        
        
for img in bpy.data.images:
    print(img.name, img['format'])