import sys
import os
import bpy
import struct
import json
import math
from .swe1r_import import read_block
    
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
    
def highlight(cursor, hl):
    # This function is called whenever an address needs to be 'highlighted' because it is a pointer
    # Every model begins with a pointer map where each bit represents 4 bytes in the following model
    # If the bit is 1, that corresponding DWORD is to be read as a pointer

    highlight_offset = cursor // 32
    bit = 2 ** (7 - (cursor % 32) // 4)
    highlight = hl[highlight_offset]
    hl[highlight_offset] = highlight | bit
    
def outside_ref(cursor, ref, model):
    # Used when writing modelblock to keep track of references to offsets outside of the given section
    if ref not in model['ref_keeper']:
        model['ref_keeper'][ref] = []
    model['ref_keeper'][ref].append(cursor)
    
def map_ref(cursor, id, model):
    # Used when writing modelblock to map original ids of nodes to their new ids
    if id not in model['ref_map']:
        model['ref_map'][id] = cursor
        
def write_data(buffer, cursor, model):
    cursor += buffer.write(b'Data', cursor)

    if model['Data']['LStr']:
        # Write size
        cursor = buffer.writeUInt32BE(len(model['Data']['LStr']), cursor)

        for lstr in model['Data']['LStr']:
            cursor += buffer.write(b'LStr', cursor)
            for value in lstr:
                cursor = buffer.writeFloatBE(value, cursor)
    else:
        # Write size
        cursor = buffer.writeUInt32BE(len(model['Data']['other']), cursor)

        for value in model['Data']['other']:
            cursor = buffer.writeUInt32BE(value, cursor)

    return cursor

def write_anim(buffer, cursor, model, hl):
    cursor += buffer.write(b'Anim', cursor)

    for _ in model['Anim']:
        highlight(cursor, hl)
        cursor += 4

    highlight(cursor, hl)
    cursor += 4

    return cursor


def write_altn(buffer, cursor, model, hl):
    # The length of AltN might need to be asserted based on model extension
    cursor += buffer.write(b'AltN', cursor)

    for alt_n_value in model['AltN']:
        highlight(cursor, hl)
        outside_ref(cursor, alt_n_value, model)
        
        if model.get('ext') == 'Podd':
            buffer.writeUInt32BE(alt_n_value, cursor)
            
        cursor += 4

    highlight(cursor, hl)
    cursor += 4

    return cursor

def writeString(buffer, cursor, string):
    return struct.pack_into('4s', buffer, cursor, string.encode('utf-8'))


def write_header(buffer, cursor, model, hl):
    cursor += buffer.write(model['ext'], cursor)

    for header_value in model.get('header', []):
        outside_ref(cursor, header_value, model)
        highlight(cursor, hl)
        cursor += 4  # buffer.writeInt32BE(header_value, cursor)

    cursor = buffer.writeInt32BE(-1, cursor)

    header_offsets = {
        'Anim': None,
        'AltN': None,
        'HEnd': None
    }

    if model.get('Data'):
        cursor = write_data(buffer, cursor, model, hl)

    if model.get('Anim'):
        header_offsets['Anim'] = cursor + 4
        cursor = write_anim(buffer, cursor, model, hl)

    if model.get('AltN'):
        header_offsets['AltN'] = cursor + 4
        cursor = write_altn(buffer, cursor, model, hl)

    cursor += buffer.write(b'HEnd', cursor)
    header_offsets['HEnd'] = cursor

    return header_offsets

def write_mat(buffer, cursor, mat_id, hl, model):
    if not mat_id:
        return cursor

    mat_addr = cursor
    model['mats'][mat_id]['write'] = mat_addr
    map_ref(cursor, mat_id, model)
    mat = model['mats'][mat_id]

    cursor = buffer.writeInt32BE(mat['format'], cursor)

    # Handling format-specific data
    cursor += 12

    if mat['texture']:
        tex_id = mat['texture']
        highlight(mat_addr + 8, hl)

        if model['textures'][tex_id]['write']:
            buffer.writeUInt32BE(model['textures'][tex_id]['write'], mat_addr + 8)
        else:
            buffer.writeUInt32BE(cursor, mat_addr + 8)
            cursor = write_mat_texture(buffer, cursor, tex_id, hl, model)

    if mat['unk']:
        highlight(mat_addr + 12, hl)
        buffer.writeUInt32BE(cursor, mat_addr + 12)
        cursor = write_mat_unk(buffer, cursor, unk=mat['unk'])

    return cursor

def write_mat_texture(buffer, cursor, tex_id, hl, model):
    texture = model['textures'].get(tex_id, {})
    if not texture:
        return cursor

    model['textures'][tex_id]['write'] = cursor
    map_ref(cursor, tex_id, model)

    cursor = buffer.writeInt32BE(texture.get('unk0', 0), cursor)
    cursor = buffer.writeInt16BE(texture.get('unk1', 0), cursor)
    cursor = buffer.writeInt16BE(texture.get('unk2', 0), cursor)
    cursor = buffer.writeInt32BE(texture.get('unk3', 0), cursor)
    cursor = buffer.writeInt16BE(texture.get('format', 0), cursor)
    cursor = buffer.writeInt16BE(texture.get('unk4', 0), cursor)
    cursor = buffer.writeInt16BE(texture.get('width', 0), cursor)
    cursor = buffer.writeInt16BE(texture.get('height', 0), cursor)
    cursor = buffer.writeInt16BE(texture.get('unk5', 0), cursor)
    cursor = buffer.writeInt16BE(texture.get('unk6', 0), cursor)
    cursor = buffer.writeInt16BE(texture.get('unk7', 0), cursor)
    cursor = buffer.writeInt16BE(texture.get('unk8', 0), cursor)

    unk_pointer = cursor
    cursor += 28
    highlight(cursor, hl)
    cursor = buffer.writeInt16BE(texture.get('unk9', 0), cursor)
    cursor = buffer.writeInt16BE(texture.get('tex_index', 0), cursor)
    cursor += 4

    for unk_pointer_value in texture.get('unk_pointers', []):
        highlight(unk_pointer, hl)
        buffer.writeUInt32BE(cursor, unk_pointer)
        cursor = buffer.writeInt32BE(unk_pointer_value.get('unk0', 0), cursor)
        cursor = buffer.writeInt32BE(unk_pointer_value.get('unk1', 0), cursor)
        cursor = buffer.writeInt32BE(unk_pointer_value.get('unk2', 0), cursor)
        cursor = buffer.writeInt16BE(unk_pointer_value.get('unk3', 0), cursor)
        cursor = buffer.writeInt16BE(unk_pointer_value.get('unk4', 0), cursor)

    return cursor

def write_mat_unk(buffer, cursor, unk):
    cursor = buffer.writeInt16BE(unk.get('unk0', 0), cursor)  # always 0
    cursor = buffer.writeInt16BE(unk.get('unk1', 0), cursor)  # 0, 1, 8, 9
    cursor = buffer.writeInt16BE(unk.get('unk2', 0), cursor)  # 1, 2
    cursor = buffer.writeInt16BE(unk.get('unk3', 0), cursor)  # 287, 513, 799, 1055, 1537, 7967
    cursor = buffer.writeInt16BE(unk.get('unk4', 0), cursor)  # 287, 799, 1055, 3329, 7939, 7940
    cursor = buffer.writeInt16BE(unk.get('unk5', 0), cursor)  # 263, 513, 775, 1031, 1537, 1795, 1799
    cursor = buffer.writeInt16BE(unk.get('unk6', 0), cursor)  # 1, 259, 263, 775, 1031, 1793, 1795, 1796, 1798
    cursor = buffer.writeInt16BE(unk.get('unk7', 0), cursor)  # 31, 287, 799, 1055, 7967
    cursor = buffer.writeInt16BE(unk.get('unk8', 0), cursor)  # 31, 799, 1055, 7936, 7940
    cursor = buffer.writeInt16BE(unk.get('unk9', 0), cursor)  # 7, 1799
    cursor = buffer.writeInt16BE(unk.get('unk10', 0), cursor)  # 775, 1031, 1792, 1796, 1798
    cursor = buffer.writeInt16BE(unk.get('unk11', 0), cursor)  # always 0
    cursor = buffer.writeInt16BE(unk.get('unk12', 0), cursor)  # -14336, 68, 3080
    cursor = buffer.writeInt16BE(unk.get('unk13', 0), cursor)  # 0, 1, 8200, 8312
    cursor = buffer.writeInt16BE(unk.get('unk14', 0), cursor)  # 16, 17, 770
    cursor = buffer.writeInt16BE(unk.get('unk15', 0), cursor)  # 120, 8200, 8248, 8296, 8312, 16840, 16856, 16960, 17216, 18760, 18768, 18808, 18809, 18888, 18904, 18936, 19280, 20048
    cursor = buffer.writeInt16BE(unk.get('unk16', 0), cursor)  # probably 0?
    cursor = buffer.writeUInt8(unk.get('r', 0), cursor)
    cursor = buffer.writeUInt8(unk.get('g', 0), cursor)
    cursor = buffer.writeUInt8(unk.get('b', 0), cursor)
    cursor = buffer.writeUInt8(unk.get('t', 0), cursor)
    cursor = buffer.writeInt16BE(unk.get('unk17', 0), cursor)
    cursor = buffer.writeInt16BE(unk.get('unk18', 0), cursor)
    cursor = buffer.writeInt16BE(unk.get('unk19', 0), cursor)
    cursor = buffer.writeInt16BE(unk.get('unk20', 0), cursor)
    cursor = buffer.writeInt16BE(unk.get('unk21', 0), cursor)
    cursor = buffer.writeInt16BE(unk.get('unk22', 0), cursor)
    cursor = buffer.writeInt16BE(unk.get('unk23', 0), cursor)

    return cursor

def write_animation(buffer, cursor, animation, hl, model):
    cursor += 61 * 4
    cursor = buffer.writeFloatBE(animation.get('float1', 0.0), cursor)
    cursor = buffer.writeFloatBE(animation.get('float2', 0.0), cursor)
    cursor = buffer.writeFloatBE(animation.get('float3', 0.0), cursor)
    cursor = buffer.writeInt16BE(animation.get('flag1', 0), cursor)
    cursor = buffer.writeInt16BE(animation.get('flag2', 0), cursor)
    cursor = buffer.writeInt32BE(animation.get('num_keyframes', 0), cursor)
    cursor = buffer.writeFloatBE(animation.get('float4', 0.0), cursor)
    cursor = buffer.writeFloatBE(animation.get('float5', 0.0), cursor)
    cursor = buffer.writeFloatBE(animation.get('float6', 0.0), cursor)
    cursor = buffer.writeFloatBE(animation.get('float7', 0.0), cursor)
    cursor = buffer.writeFloatBE(animation.get('float8', 0.0), cursor)
    highlight(cursor, hl)
    keyframe_times = cursor
    cursor += 4
    highlight(cursor, hl)
    keyframe_poses = cursor
    cursor += 4
    anim_target = None
    flag = animation.get('flag2', 0)
    highlight(cursor, hl)
    if flag in [2, 18]:
        anim_target = cursor
    else:
        outside_ref(cursor, ref=animation.get('target', ''), model=model)
    cursor += 4
    cursor = buffer.writeInt32BE(animation.get('unk32', 0), cursor)

    # Write keyframe times
    buffer.writeInt32BE(cursor, keyframe_times)
    for k in range(len(animation.get('keyframe_times', []))):
        cursor = buffer.writeFloatBE(animation['keyframe_times'][k], cursor)

    if flag in [2, 18]:
        # Write target list
        buffer.writeInt32BE(cursor, anim_target)
        highlight(cursor, hl)
        cursor = buffer.writeInt32BE(model['mats'][animation.get('target', '')].get('write', 0), cursor)
        highlight(cursor, hl)
        cursor += 4

    # Write keyframe poses
    buffer.writeInt32BE(cursor, keyframe_poses)

    for p in range(len(animation.get('keyframe_poses', []))):
        if flag in [8, 24, 40, 56, 4152]:  # rotation (4)
            for f in range(4):
                cursor = buffer.writeFloatBE(animation['keyframe_poses'][p][f], cursor)
        elif flag in [25, 41, 57, 4153]:  # position (3)
            for f in range(3):
                cursor = buffer.writeFloatBE(animation['keyframe_poses'][p][f], cursor)
        elif flag in [27, 28]:  # uv_x/uv_y (1)
            cursor = buffer.writeFloatBE(animation['keyframe_poses'][p], cursor)

    if flag in [2, 18]:  # texture
        texturelist = cursor
        for k in range(len(animation.get('keyframe_poses', []))):
            highlight(cursor, hl)
            cursor += 4
        for k in range(len(animation.get('keyframe_poses', []))):
            tex_id = animation['keyframe_poses'][k]
            if model['textures'].get(tex_id, {}).get('write', 0):
                buffer.writeUInt32BE(model['textures'][tex_id]['write'], texturelist + k * 4)
            else:
                buffer.writeUInt32BE(cursor, texturelist + k * 4)
                cursor = write_mat_texture(buffer, cursor, tex_id, hl, model)

    return cursor

def write_collision_vert_strips(buffer, cursor, vert_strips):
    if not vert_strips or not vert_strips:
        return cursor

    for v in range(len(vert_strips)):
        cursor = buffer.writeInt32BE(vert_strips[v], cursor)

    return cursor

def write_collision_vert_buffer(buffer, cursor, vert_buffer):
    if not vert_buffer or not vert_buffer:
        return cursor

    for v in range(len(vert_buffer)):
        vert = vert_buffer[v]
        for i in range(len(vert)):
            cursor = buffer.writeInt16BE(vert[i], cursor)

    return cursor if cursor % 4 == 0 else cursor + 2

def write_collision_triggers(buffer, cursor, triggers, hl, model):
    for i in range(len(triggers)):
        trigger = triggers[i]
        highlight(cursor, hl)
        cursor = buffer.writeInt32BE(cursor + 4, cursor)
        cursor = buffer.writeFloatBE(trigger['x'], cursor)
        cursor = buffer.writeFloatBE(trigger['y'], cursor)
        cursor = buffer.writeFloatBE(trigger['z'], cursor)
        cursor = buffer.writeFloatBE(trigger['vx'], cursor)
        cursor = buffer.writeFloatBE(trigger['vy'], cursor)
        cursor = buffer.writeFloatBE(trigger['vz'], cursor)
        cursor = buffer.writeFloatBE(trigger['width'], cursor)
        cursor = buffer.writeFloatBE(trigger['height'], cursor)
        outside_ref(cursor, ref=trigger['target'], model=model)
        highlight(cursor, hl)
        cursor += 4
        cursor = buffer.writeInt16BE(trigger['flag'], cursor)
        cursor += 2

    highlight(cursor, hl)  # end with blank pointer to mark the end of the linked list
    cursor += 4
    return cursor

def write_collision_data(buffer, cursor, data, hl, model):
    cursor = buffer.writeInt16BE(data['unk'], cursor)
    cursor = buffer.writeUInt8(data['fog']['flag'], cursor)
    cursor = buffer.writeUInt8(data['fog']['r'], cursor)
    cursor = buffer.writeUInt8(data['fog']['g'], cursor)
    cursor = buffer.writeUInt8(data['fog']['b'], cursor)
    cursor = buffer.writeInt16BE(data['fog']['start'], cursor)
    cursor = buffer.writeInt16BE(data['fog']['end'], cursor)
    cursor = buffer.writeInt16BE(data['lights']['flag'], cursor)
    cursor = buffer.writeUInt8(data['lights']['ambient_r'], cursor)
    cursor = buffer.writeUInt8(data['lights']['ambient_g'], cursor)
    cursor = buffer.writeUInt8(data['lights']['ambient_b'], cursor)
    cursor = buffer.writeUInt8(data['lights']['r'], cursor)
    cursor = buffer.writeUInt8(data['lights']['g'], cursor)
    cursor = buffer.writeUInt8(data['lights']['b'], cursor)
    cursor = buffer.writeUInt8(data['lights']['unk1'], cursor)
    cursor = buffer.writeUInt8(data['lights']['unk2'], cursor)
    cursor = buffer.writeFloatBE(data['lights']['x'], cursor)
    cursor = buffer.writeFloatBE(data['lights']['y'], cursor)
    cursor = buffer.writeFloatBE(data['lights']['z'], cursor)
    cursor = buffer.writeFloatBE(data['lights']['unk3'], cursor)
    cursor = buffer.writeFloatBE(data['lights']['unk4'], cursor)
    cursor = buffer.writeFloatBE(data['lights']['unk5'], cursor)
    cursor = buffer.writeInt32BE(data['flags'], cursor)
    cursor = buffer.writeInt32BE(data['unk2'], cursor)
    cursor = buffer.writeUInt32BE(data['unload'], cursor)
    cursor = buffer.writeUInt32BE(data['load'], cursor)

    cursor = write_collision_triggers(buffer=buffer, cursor=cursor, triggers=data['triggers'], hl=hl, model=model)

    return cursor

def write_visual_index_buffer(buffer, cursor, index_buffer, hl):
    if not index_buffer or not index_buffer:
        return cursor

    v = 0
    for i in range(len(index_buffer)):
        index = index_buffer[i]
        type_ = index['type']
        buffer.writeUInt8(type_, cursor + v)

        if type_ == 1:
            buffer.writeUInt8(index['unk1'], cursor + v + 1)
            buffer.writeUInt8(index['unk2'], cursor + v + 2)
            buffer.writeUInt8(index['size'], cursor + v + 3)
            exports.highlight({'cursor': cursor + v + 4, 'hl': hl})
            # buffer.writeUInt32BE(index['start'], cursor + v + 4)

        elif type_ == 3:
            buffer.writeUInt8(index['unk'], cursor + v + 7)

        elif type_ == 5:
            buffer.writeUInt8(index['x'], cursor + v + 1)
            buffer.writeUInt8(index['y'], cursor + v + 2)
            buffer.writeUInt8(index['z'], cursor + v + 3)

        elif type_ == 6:
            buffer.writeUInt8(index['x1'], cursor + v + 1)
            buffer.writeUInt8(index['y1'], cursor + v + 2)
            buffer.writeUInt8(index['z1'], cursor + v + 3)
            buffer.writeUInt8(index['x2'], cursor + v + 5)
            buffer.writeUInt8(index['y2'], cursor + v + 6)
            buffer.writeUInt8(index['z2'], cursor + v + 7)

        v += 8

    cursor += v
    cursor = buffer.writeUInt8(223, cursor)
    cursor += 7
    return cursor

def write_visual_vert_buffer(buffer, cursor, vert_buffer, index_buffer, index_buffer_addr):
    vert_buffer_addr = cursor

    # Write buffer
    for i in range(len(vert_buffer)):
        x, y, z = vert_buffer[i]['x'], vert_buffer[i]['y'], vert_buffer[i]['z']
        cursor = buffer.writeInt16BE(x, cursor)
        cursor = buffer.writeInt16BE(y, cursor)
        cursor = buffer.writeInt16BE(z, cursor)
        cursor += 2

        cursor = buffer.writeInt16BE(vert_buffer[i]['uv_x'], cursor)
        cursor = buffer.writeInt16BE(vert_buffer[i]['uv_y'], cursor)

        cursor = buffer.writeUInt8(vert_buffer[i]['v_color'][0], cursor)
        cursor = buffer.writeUInt8(vert_buffer[i]['v_color'][1], cursor)
        cursor = buffer.writeUInt8(vert_buffer[i]['v_color'][2], cursor)
        cursor = buffer.writeUInt8(vert_buffer[i]['v_color'][3], cursor)

    # Write references in index_buffer to this section
    total = 0
    for i, index in enumerate(index_buffer):
        if index['type'] == 1:
            buffer.writeUInt32BE(vert_buffer_addr + index['start'] * 16, index_buffer_addr + i * 8 + 4)

    return cursor

def write_mesh_group(buffer, cursor, mesh, hl, model):
    headstart = cursor
    buffer.writeFloatBE(mesh['min_x'], cursor + 8)
    buffer.writeFloatBE(mesh['min_y'], cursor + 12)
    buffer.writeFloatBE(mesh['min_z'], cursor + 16)
    buffer.writeFloatBE(mesh['max_x'], cursor + 20)
    buffer.writeFloatBE(mesh['max_y'], cursor + 24)
    buffer.writeFloatBE(mesh['max_z'], cursor + 28)
    buffer.writeInt16BE(mesh['vert_strip_count'], cursor + 32)
    buffer.writeInt16BE(mesh['vert_strip_default'], cursor + 34)
    exports.highlight({'cursor': cursor + 40, 'hl': hl})
    exports.outside_ref({'cursor': cursor + 40, 'ref': mesh['visuals']['group_parent'], 'model': model})
    buffer.writeInt16BE(len(mesh['collision']['vert_buffer']), cursor + 56)
    buffer.writeInt16BE(len(mesh['visuals']['vert_buffer']), cursor + 58)
    buffer.writeInt16BE(mesh['visuals']['group_count'], cursor + 62)
    cursor += 64

    if mesh['collision']['vert_strips']:
        exports.highlight({'cursor': headstart + 36, 'hl': hl})
        buffer.writeUInt32BE(cursor, headstart + 36)
        cursor = exports.write_collision_vert_strips({'buffer': buffer, 'cursor': cursor, 'vert_strips': mesh['collision']['vert_strips']})

    if mesh['collision']['vert_buffer']:
        exports.highlight({'cursor': headstart + 44, 'hl': hl})
        buffer.writeUInt32BE(cursor, headstart + 44)
        cursor = exports.write_collision_vert_buffer({'buffer': buffer, 'cursor': cursor, 'vert_buffer': mesh['collision']['vert_buffer']})

    if mesh['visuals']['material']:
        exports.highlight({'cursor': headstart, 'hl': hl})
        mat_id = mesh['visuals']['material']
        if model['mats'][mat_id]['write']:
            buffer.writeUInt32BE(model['mats'][mat_id]['write'], headstart)
        else:
            buffer.writeUInt32BE(cursor, headstart)
            cursor = exports.write_mat({'buffer': buffer, 'cursor': cursor, 'mat_id': mat_id, 'hl': hl, 'model': model})

    index_buffer_addr = None
    if mesh['visuals']['index_buffer']:
        exports.highlight({'cursor': headstart + 48, 'hl': hl})
        index_buffer_addr = cursor if cursor % 8 == 0 else cursor + 4
        buffer.writeInt32BE(index_buffer_addr, headstart + 48)
        cursor = exports.write_visual_index_buffer({'buffer': buffer, 'cursor': index_buffer_addr, 'index_buffer': mesh['visuals']['index_buffer'], 'hl': hl})

    if mesh['visuals']['vert_buffer'] and len(mesh['visuals']['vert_buffer']):
        exports.highlight({'cursor': headstart + 52, 'hl': hl})
        buffer.writeUInt32BE(cursor, headstart + 52)
        cursor = exports.write_visual_vert_buffer({'buffer': buffer, 'cursor': cursor, 'vert_buffer': mesh['visuals']['vert_buffer'], 'index_buffer': mesh['visuals']['index_buffer'], 'index_buffer_addr': index_buffer_addr})

    if mesh['collision']['data']:
        exports.highlight({'cursor': headstart + 4, 'hl': hl})
        buffer.writeUInt32BE(cursor, headstart + 4)
        cursor = exports.write_collision_data({'buffer': buffer, 'cursor': cursor, 'data': mesh['collision']['data'], 'hl': hl, 'model': model})

    return cursor

def write_node(buffer, cursor, node, hl, model, header_offsets):
    if node.get('header'):
        for i in range(len(node['header'])):
            buffer.writeUInt32BE(cursor, 4 + node['header'][i] * 4)

    if node.get('AltN'):
        for i in range(len(node['AltN'])):
            buffer.writeUInt32BE(cursor, header_offsets['AltN'] + node['AltN'][i] * 4)

    map_ref({'cursor': cursor, 'id': node['id'], 'model': model})

    cursor = buffer.writeUInt32BE(node['head'][0], cursor)
    cursor = buffer.writeUInt32BE(node['head'][1], cursor)
    cursor = buffer.writeUInt32BE(node['head'][2], cursor)
    cursor = buffer.writeUInt32BE(node['head'][3], cursor)
    cursor = buffer.writeUInt32BE(node['head'][4], cursor)
    cursor = buffer.writeUInt32BE(len(node['children']), cursor)
    exports.highlight({'cursor': cursor, 'hl': hl})
    child_list_addr_addr = cursor
    cursor += 4

    mesh_group = False
    switch_val = node['head'][0]
    if switch_val == 12388:
        mesh_group = True
        cursor = buffer.writeFloatBE(node['min_x'], cursor)
        cursor = buffer.writeFloatBE(node['min_y'], cursor)
        cursor = buffer.writeFloatBE(node['min_z'], cursor)
        cursor = buffer.writeFloatBE(node['max_x'], cursor)
        cursor = buffer.writeFloatBE(node['max_y'], cursor)
        cursor = buffer.writeFloatBE(node['max_z'], cursor)
        cursor += 8
    elif switch_val == 20581:
        if node.get('children') and len(node['children']):
            cursor += 4
    elif switch_val == 20582:
        cursor = buffer.writeFloatBE(node['xyz']['f1'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['f2'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['f3'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['f4'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['f5'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['f6'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['f7'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['f8'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['f9'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['f10'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['f11'], cursor)
    elif switch_val == 53348:
        cursor = buffer.writeFloatBE(node['xyz']['ax'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['ay'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['az'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['bx'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['by'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['bz'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['cx'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['cy'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['cz'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['x'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['y'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['z'], cursor)
    elif switch_val == 53349:
        cursor = buffer.writeFloatBE(node['xyz']['ax'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['ay'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['az'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['bx'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['by'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['bz'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['cx'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['cy'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['cz'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['x'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['y'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['z'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['x1'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['y1'], cursor)
        cursor = buffer.writeFloatBE(node['xyz']['z1'], cursor)
    elif switch_val == 53350:
        cursor = buffer.writeInt32BE(node['53350']['unk1'], cursor)
        cursor = buffer.writeInt32BE(node['53350']['unk2'], cursor)
        cursor = buffer.writeInt32BE(node['53350']['unk3'], cursor)
        cursor = buffer.writeFloatBE(node['53350']['unk4'], cursor)

    if not len(node['children']):
        return cursor

    # write offset to this child list
    buffer.writeInt32BE(cursor, child_list_addr_addr)

    # child list
    child_list_addr = cursor
    for c in range(len(node['children'])):
        exports.highlight({'cursor': cursor, 'hl': hl})
        cursor += 4

    # write children
    for c in range(len(node['children'])):
        child = node['children'][c]

        if child.get('AltN'):
            map_ref({'cursor': child_list_addr + c * 4, 'id': child['id'], 'model': model})
            continue

        if child['id'] is None:
            buffer.writeUInt32BE(0, child_list_addr + c * 4)
            continue

        if model['ref_map'][child['id']]:
            buffer.writeUInt32BE(model['ref_map'][child['id']], child_list_addr + c * 4)
            continue

        buffer.writeUInt32BE(cursor, child_list_addr + c * 4)
        if mesh_group:
            cursor = write_mesh_group({'buffer': buffer, 'cursor': cursor, 'mesh': child, 'hl': hl, 'model': model})
        else:
            cursor = write_node({'buffer': buffer, 'cursor': cursor, 'node': child, 'hl': hl, 'model': model, 'header_offsets': header_offsets})

    return cursor

def write_model(model):
    buffer = bytearray(8000000)
    hl = bytearray(1000000)
    cursor = 0

    model['ref_map'] = {}  # where we'll map node ids to their written locations
    model['ref_keeper'] = {}  # where we'll remember locations of node offsets to go back and update with the offset_map at the end

    header_offsets = write_header(buffer, cursor, hl,model)
    cursor = header_offsets['HEnd']

    # write all nodes
    for i in range(len(model['nodes'])):
        cursor = write_node(buffer, cursor, hl, model['nodes'][i], model, header_offsets)

    # write all animations
    if model.get('Anim'):
        for i in range(len(model['Anim'])):
            buffer.writeUInt32BE(cursor, header_offsets['Anim'] + i * 4)
            cursor = write_animation( buffer, cursor, model['Anim'][i], hl, model)

    # write all outside references
    refs = [ref for ref in model['ref_keeper'] if ref != 0]
    for ref in refs:
        for offset in model['ref_keeper'][ref]:
            buffer.writeUInt32BE(model['ref_map'][ref], offset)

    return [hl[:math.ceil(cursor / (32 * 4)) * 4], buffer[:cursor]]

def write_block(arr):
    length = len(arr[0])
    index = bytearray((length * len(arr) + 2) * 4)
    block = []
    block.append(index)

    struct.pack_into('>I', index, 0, length)  # write total number of assets
    cursor = len(index)
    for i in range(length):
        for j in range(len(arr)):
            struct.pack_into('>I', index, 4 + (i * len(arr) + j) * 4, cursor if (arr[j][i] and len(arr[j][i])) else 0)
            cursor += len(arr[j][i])
            block.append(arr[j][i])
    struct.pack_into('>I', index, (length * len(arr) + 1) * 4, cursor)  # end of block offset

    return b''.join(block)

def inject_model(offset_buffer, model_buffer, ind, file_path):
    with open(file_path + '/out_modelblock.bin', 'rb') as file:
        file = file.read()
        read_block_result = read_block(file, [[], []], [])

    offset_buffers, model_buffers = read_block_result
    
    offset_buffers[ind] = offset_buffer
    model_buffers[ind] = model_buffer
    
    block = write_block(file_path, [offset_buffers, model_buffers])
    return block
    
def unmake_model(collection):
    model = {
        'ext': collection['ext'],
        'id': collection['ind'],
        'header': [h for h in collection['header']],
        'nodes': []
    }
    if 'parent' in collection: return
    for child in collection.children:
        if 'lightstreaks' in child.name:
            unmake_LStr(child.objects, {})
    
    top_nodes = [] 
    for obj in collection.objects:
        if obj.type != 'MESH': continue
        top = find_topmost_parent(obj)
        if top not in top_nodes: top_nodes.append(top)
    
    for node in top_nodes:
        model['nodes'].append(unmake_node(node))
        
    return model

def export_model(col, file_path):
    model = unmake_model(col)
    offset_buffer, model_buffer = write_model(model)
    block = inject_model(offset_buffer, model_buffer, col['ind'], file_path)
    with open(file_path + 'out_modelblock.bin', 'wb') as file:
        file.write(block)

def write_spline_point(buffer, cursor, point):
    cursor = struct.pack_into('>hhhhhhhhfff fff fff hhhh hhhh hhhh hhhh hhhh hhhh hhhh hhhh hhhh hhh', buffer, cursor,
                              point.next_count, point.previous_count,
                              point.next1, point.next2,
                              point.previous1, point.previous2,
                              point.unknown1, point.unknown2,
                              point.point_x, point.point_y, point.point_z,
                              point.rotation_x, point.rotation_y, point.rotation_z,
                              point.handle1_x, point.handle1_y, point.handle1_z,
                              point.handle2_x, point.handle2_y, point.handle2_z,
                              point.point_num0,
                              point.point_num1,
                              point.point_num2,
                              point.point_num3,
                              point.point_num4,
                              point.point_num5,
                              point.point_num6,
                              point.point_num7,
                              point.point_num8,
                              point.point_unk)
    return cursor

def write_spline(spline):
    buffer = bytearray(16 + len(spline['points']) * 84)
    cursor = 0
    struct.pack_into('>iiii', buffer, cursor, spline['unknown'], spline['point_count'], spline['segment_count'], spline['unknown2'])
    cursor += 16

    for point in spline['points']:
        cursor = write_spline_point(buffer, cursor, point)

    return bytes(buffer[:cursor])

def invert_spline(spline):
    inverted_points = []
    double_count = 0
    biggest_num0 = 0

    for point in spline['points']:
        if point['point_num0'] > biggest_num0:
            biggest_num0 = point['point_num0']

    for i, point in enumerate(spline['points']):
        inverted_point = {
            'previous_count': point['next_count'],
            'next_count': point['previous_count'],
            'next1': point['previous1'],
            'next2': point['previous2'],
            'previous1': point['next1'],
            'previous2': point['next2'],
            'unknown1': point['unknown1'],
            'unknown2': point['unknown2'],
            'point_x': point['point_x'],
            'point_y': point['point_y'],
            'point_z': point['point_z'],
            'rotation_x': point['rotation_x'],
            'rotation_y': point['rotation_y'],
            'rotation_z': point['rotation_z'],
            'handle1_x': point['handle2_x'],
            'handle1_y': point['handle2_y'],
            'handle1_z': point['handle2_z'],
            'handle2_x': point['handle1_x'],
            'handle2_y': point['handle1_y'],
            'handle2_z': point['handle1_z'],
            'point_num0': 0 if point['point_num0'] == 0 else biggest_num0 - point['point_num0'] + 1,
            'point_num1': i,
            'point_num2': spline['point_count'] + double_count if point['splits'] == 2 else -1,
            'point_num3': -1,
            'point_num4': -1,
            'point_num5': -1,
            'point_num6': -1,
            'point_num7': -1,
            'point_num8': -1,
            'point_unk': point['point_unk']
        }

        if point['splits'] == 2:
            double_count += 1

        inverted_points.append(inverted_point)

    spline['points'] = inverted_points
    return spline

def write_palette(palette):
    if not palette:
        return bytearray()

    buffer = bytearray(len(palette) * 2)
    cursor = 0

    for p in palette:
        r = int((p[0] / 255) * 0x1F) << 11
        g = int((p[1] / 255) * 0x1F) << 6
        b = int((p[2] / 255) * 0x1F) << 1
        a = int(p[3] / 255)
        pal = (((r | g) | b) | a)
        buffer[cursor:cursor + 2] = pal.to_bytes(2, 'big')
        cursor += 2

    return bytes(buffer)

def write_pixels(pixels, format):
    formatmap = {
        3: 4,
        512: 0.5,
        513: 1,
        1024: 0.5,
        1025: 1
    }

    buffer = bytearray(len(pixels) * int(formatmap[format]))
    cursor = 0

    if format in [512, 1024]:
        for i in range(0, len(pixels) // 2):
            if format == 512:
                buffer[cursor] = (pixels[i * 2] << 4) | pixels[i * 2 + 1]
            elif format == 1024:
                buffer[cursor] = (pixels[i * 2] // 0x11 << 4) | (pixels[i * 2 + 1] // 0x11)
            cursor += 1

    elif format in [513, 1025, 3]:
        for i in range(len(pixels)):
            pixel = pixels[i]
            if format == 3:
                for j in range(4):
                    buffer[cursor] = pixel[j]
                    cursor += 1
            else:
                buffer[cursor] = pixel
                cursor += 1

    return bytes(buffer)