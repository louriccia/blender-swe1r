import sys
import os
import bpy
import struct
import json
import math
from .swe1r_import import read_block
from .popup import show_custom_popup
    
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
    if str(ref) not in model['ref_keeper']:
        model['ref_keeper'][str(ref)] = []
    model['ref_keeper'][str(ref)].append(cursor)
    
def map_ref(cursor, id, model):
    # Used when writing modelblock to map original ids of nodes to their new ids
    if str(id) not in model['ref_map']:
        model['ref_map'][str(id)] = cursor
        
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
        
        if model['ext'] == 'Podd':
            buffer.writeUInt32BE(alt_n_value, cursor)
            
        cursor += 4

    highlight(cursor, hl)
    cursor += 4

    return cursor

def writeBulk(buffer, cursor, format_string, arr):
    struct.pack_into(format_string, buffer, cursor, *arr)
    return cursor + struct.calcsize(format_string)

def writeString(buffer,  string, cursor):
    struct.pack_into('4s', buffer, cursor, string.encode('utf-8'))
    return cursor + struct.calcsize('4s')

def writeInt8BE(buffer, num, cursor):
    struct.pack_into('b', buffer, cursor, num)
    return cursor + struct.calcsize('b')

def writeUInt8BE(buffer, num, cursor):
    struct.pack_into('B', buffer, cursor, num)
    return cursor + struct.calcsize('B')

def writeInt16BE(buffer, num, cursor):
    struct.pack_into('h', buffer, cursor, num)
    return cursor + struct.calcsize('h')

def writeUInt16BE(buffer, num, cursor):
    struct.pack_into('H', buffer, cursor, num)
    return cursor + struct.calcsize('H')

def writeInt32BE(buffer, num, cursor):
    struct.pack_into('i', buffer, cursor, num)
    return cursor + struct.calcsize('i')

def writeUInt32BE(buffer, num, cursor):
    struct.pack_into('I', buffer, cursor, num)
    return cursor + struct.calcsize('I')

def write_header(buffer, cursor,  hl, model):
    cursor = writeString(buffer,  model['ext'], cursor)

    for header_value in model['header']:
        outside_ref(cursor, header_value, model)
        highlight(cursor, hl)
        cursor += 4  # buffer.writeInt32BE(header_value, cursor)

    cursor = writeInt32BE(buffer, -1, cursor)

    header_offsets = {
        'Anim': None,
        'AltN': None,
        'HEnd': None
    }

    if 'Data' in model:
        cursor = write_data(buffer, cursor, model, hl)

    if 'Anim' in model:
        header_offsets['Anim'] = cursor + 4
        cursor = write_anim(buffer, cursor, model, hl)

    if 'AltN' in model:
        header_offsets['AltN'] = cursor + 4
        cursor = write_altn(buffer, cursor, model, hl)

    cursor = writeString(buffer, 'HEnd', cursor)
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
    texture = model['textures'][tex_id]
    if not texture:
        return cursor

    model['textures'][tex_id]['write'] = cursor
    map_ref(cursor, tex_id, model)

    cursor = buffer.writeInt32BE(texture['unk0'], cursor)
    cursor = buffer.writeInt16BE(texture['unk1'], cursor)
    cursor = buffer.writeInt16BE(texture['unk2'], cursor)
    cursor = buffer.writeInt32BE(texture['unk3'], cursor)
    cursor = buffer.writeInt16BE(texture['format'], cursor)
    cursor = buffer.writeInt16BE(texture['unk4'], cursor)
    cursor = buffer.writeInt16BE(texture['width'], cursor)
    cursor = buffer.writeInt16BE(texture['height'], cursor)
    cursor = buffer.writeInt16BE(texture['unk5'], cursor)
    cursor = buffer.writeInt16BE(texture['unk6'], cursor)
    cursor = buffer.writeInt16BE(texture['unk7'], cursor)
    cursor = buffer.writeInt16BE(texture['unk8'], cursor)

    unk_pointer = cursor
    cursor += 28
    highlight(cursor, hl)
    cursor = buffer.writeInt16BE(texture['unk9'], cursor)
    cursor = buffer.writeInt16BE(texture['tex_index'], cursor)
    cursor += 4

    for unk_pointer_value in texture['unk_pointers']:
        highlight(unk_pointer, hl)
        buffer.writeUInt32BE(cursor, unk_pointer)
        cursor = buffer.writeInt32BE(unk_pointer_value['unk0'], cursor)
        cursor = buffer.writeInt32BE(unk_pointer_value['unk1'], cursor)
        cursor = buffer.writeInt32BE(unk_pointer_value['unk2'], cursor)
        cursor = buffer.writeInt16BE(unk_pointer_value['unk3'], cursor)
        cursor = buffer.writeInt16BE(unk_pointer_value['unk4'], cursor)

    return cursor

def write_mat_unk(buffer, cursor, unk):
    cursor = buffer.writeInt16BE(unk['unk0'], cursor)  # always 0
    cursor = buffer.writeInt16BE(unk['unk1'], cursor)  # 0, 1, 8, 9
    cursor = buffer.writeInt16BE(unk['unk2'], cursor)  # 1, 2
    cursor = buffer.writeInt16BE(unk['unk3'], cursor)  # 287, 513, 799, 1055, 1537, 7967
    cursor = buffer.writeInt16BE(unk['unk4'], cursor)  # 287, 799, 1055, 3329, 7939, 7940
    cursor = buffer.writeInt16BE(unk['unk5'], cursor)  # 263, 513, 775, 1031, 1537, 1795, 1799
    cursor = buffer.writeInt16BE(unk['unk6'], cursor)  # 1, 259, 263, 775, 1031, 1793, 1795, 1796, 1798
    cursor = buffer.writeInt16BE(unk['unk7'], cursor)  # 31, 287, 799, 1055, 7967
    cursor = buffer.writeInt16BE(unk['unk8'], cursor)  # 31, 799, 1055, 7936, 7940
    cursor = buffer.writeInt16BE(unk['unk9'], cursor)  # 7, 1799
    cursor = buffer.writeInt16BE(unk['unk10'], cursor)  # 775, 1031, 1792, 1796, 1798
    cursor = buffer.writeInt16BE(unk['unk11'], cursor)  # always 0
    cursor = buffer.writeInt16BE(unk['unk12'], cursor)  # -14336, 68, 3080
    cursor = buffer.writeInt16BE(unk['unk13'], cursor)  # 0, 1, 8200, 8312
    cursor = buffer.writeInt16BE(unk['unk14'], cursor)  # 16, 17, 770
    cursor = buffer.writeInt16BE(unk['unk15'], cursor)  # 120, 8200, 8248, 8296, 8312, 16840, 16856, 16960, 17216, 18760, 18768, 18808, 18809, 18888, 18904, 18936, 19280, 20048
    cursor = buffer.writeInt16BE(unk['unk16'], cursor)  # probably 0?
    cursor = buffer.writeUInt8(unk['r'], cursor)
    cursor = buffer.writeUInt8(unk['g'], cursor)
    cursor = buffer.writeUInt8(unk['b'], cursor)
    cursor = buffer.writeUInt8(unk['t'], cursor)
    cursor = buffer.writeInt16BE(unk['unk17'], cursor)
    cursor = buffer.writeInt16BE(unk['unk18'], cursor)
    cursor = buffer.writeInt16BE(unk['unk19'], cursor)
    cursor = buffer.writeInt16BE(unk['unk20'], cursor)
    cursor = buffer.writeInt16BE(unk['unk21'], cursor)
    cursor = buffer.writeInt16BE(unk['unk22'], cursor)
    cursor = buffer.writeInt16BE(unk['unk23'], cursor)

    return cursor

def write_animation(buffer, cursor, animation, hl, model):
    cursor += 61 * 4
    cursor = buffer.writeFloatBE(animation['float1'], cursor)
    cursor = buffer.writeFloatBE(animation['float2'], cursor)
    cursor = buffer.writeFloatBE(animation['float3'], cursor)
    cursor = buffer.writeInt16BE(animation['flag1'], cursor)
    cursor = buffer.writeInt16BE(animation['flag2'], cursor)
    cursor = buffer.writeInt32BE(animation['num_keyframes'], cursor)
    cursor = buffer.writeFloatBE(animation['float4'], cursor)
    cursor = buffer.writeFloatBE(animation['float5'], cursor)
    cursor = buffer.writeFloatBE(animation['float6'], cursor)
    cursor = buffer.writeFloatBE(animation['float7'], cursor)
    cursor = buffer.writeFloatBE(animation['float8'], cursor)
    highlight(cursor, hl)
    keyframe_times = cursor
    cursor += 4
    highlight(cursor, hl)
    keyframe_poses = cursor
    cursor += 4
    anim_target = None
    flag = animation['flag2']
    highlight(cursor, hl)
    if flag in [2, 18]:
        anim_target = cursor
    else:
        outside_ref(cursor, animation['target'], model)
    cursor += 4
    cursor = buffer.writeInt32BE(animation['unk32'], cursor)

    # Write keyframe times
    buffer.writeInt32BE(cursor, keyframe_times)
    for k in range(len(animation['keyframe_times'])):
        cursor = buffer.writeFloatBE(animation['keyframe_times'][k], cursor)

    if flag in [2, 18]:
        # Write target list
        buffer.writeInt32BE(cursor, anim_target)
        highlight(cursor, hl)
        cursor = buffer.writeInt32BE(model['mats'][animation['target']]['write'], cursor)
        highlight(cursor, hl)
        cursor += 4

    # Write keyframe poses
    buffer.writeInt32BE(cursor, keyframe_poses)

    for p in range(len(animation['keyframe_poses'])):
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
        for k in range(len(animation['keyframe_poses'])):
            highlight(cursor, hl)
            cursor += 4
        for k in range(len(animation['keyframe_poses'])):
            tex_id = animation['keyframe_poses'][k]
            if model['textures'][tex_id]['write']:
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
        outside_ref(cursor, trigger['target'], model)
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
            highlight(cursor + v + 4, hl)
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
    highlight(cursor + 40,  hl)
    outside_ref( cursor + 40, mesh['visuals']['group_parent'],model)
    buffer.writeInt16BE(len(mesh['collision']['vert_buffer']), cursor + 56)
    buffer.writeInt16BE(len(mesh['visuals']['vert_buffer']), cursor + 58)
    buffer.writeInt16BE(mesh['visuals']['group_count'], cursor + 62)
    cursor += 64

    if mesh['collision']['vert_strips']:
        highlight(headstart + 36,  hl)
        buffer.writeUInt32BE(cursor, headstart + 36)
        cursor = write_collision_vert_strips( buffer, cursor,  mesh['collision']['vert_strips'])

    if mesh['collision']['vert_buffer']:
        highlight(headstart + 44,  hl)
        buffer.writeUInt32BE(cursor, headstart + 44)
        cursor = write_collision_vert_buffer( buffer,  cursor, mesh['collision']['vert_buffer'])

    if mesh['visuals']['material']:
        highlight(headstart, hl)
        mat_id = mesh['visuals']['material']
        if model['mats'][mat_id]['write']:
            buffer.writeUInt32BE(model['mats'][mat_id]['write'], headstart)
        else:
            buffer.writeUInt32BE(cursor, headstart)
            cursor = write_mat(buffer,  cursor, mat_id,  hl, model)

    index_buffer_addr = None
    if mesh['visuals']['index_buffer']:
        highlight(headstart + 48,  hl)
        index_buffer_addr = cursor if cursor % 8 == 0 else cursor + 4
        buffer.writeInt32BE(index_buffer_addr, headstart + 48)
        cursor = write_visual_index_buffer(buffer,  index_buffer_addr, mesh['visuals']['index_buffer'], hl)

    if mesh['visuals']['vert_buffer'] and len(mesh['visuals']['vert_buffer']):
        highlight(headstart + 52,  hl)
        buffer.writeUInt32BE(cursor, headstart + 52)
        cursor = write_visual_vert_buffer( buffer, cursor,  mesh['visuals']['vert_buffer'], mesh['visuals']['index_buffer'],  index_buffer_addr)

    if mesh['collision']['data']:
        highlight(headstart + 4, hl)
        buffer.writeUInt32BE(cursor, headstart + 4)
        cursor = write_collision_data(buffer,  cursor, mesh['collision']['data'], hl,  model)

    return cursor

def write_node(buffer, cursor, node, hl, model, header_offsets):
    if 'header' in node:
        for i in range(len(node['header'])):
            writeUInt32BE(buffer, cursor, 4 + node['header'][i] * 4)

    if 'AltN' in node:
        for i in range(len(node['AltN'])):
            writeUInt32BE(buffer, cursor, header_offsets['AltN'] + node['AltN'][i] * 4)

    map_ref(cursor, node['id'],model)
    header_vals = node['head']
    header_vals.append(len(node['children']))
    cursor = writeBulk(buffer, cursor, '6I', [int(i) for i in header_vals]) 
    highlight(cursor, hl)
    child_list_addr_addr = cursor
    cursor += 4

    mesh_group = False
    switch_val = node['head'][0]
    if switch_val == 12388:
        mesh_group = True
        cursor = writeBulk(buffer, cursor, '6f', [node['min_x'], node['min_y'], node['min_z'], node['max_x'], node['max_y'], node['max_z']])
        cursor += 8
    elif switch_val == 20581:
        if 'children' in node and len(node['children']):
            cursor += 4
    elif switch_val == 20582:
        cursor = writeBulk(buffer, cursor, '11f', [
        node['xyz']['f1'], 
        node['xyz']['f2'], 
        node['xyz']['f3'], 
        node['xyz']['f4'], 
        node['xyz']['f5'], 
        node['xyz']['f6'], 
        node['xyz']['f7'], 
        node['xyz']['f8'], 
        node['xyz']['f9'], 
        node['xyz']['f10'], 
        node['xyz']['f11']
        ])
        
    elif switch_val == 53348:
        cursor = writeBulk(buffer, cursor, '12f', [
            node['xyz']['ax'], 
            node['xyz']['ay'], 
            node['xyz']['az'], 
            node['xyz']['bx'], 
            node['xyz']['by'], 
            node['xyz']['bz'], 
            node['xyz']['cx'], 
            node['xyz']['cy'], 
            node['xyz']['cz'], 
            node['xyz']['x'], 
            node['xyz']['y'], 
            node['xyz']['z']
        ])
        
    elif switch_val == 53349:
        cursor = writeBulk(buffer, cursor, '15f', [
        node['xyz']['ax'], 
        node['xyz']['ay'], 
        node['xyz']['az'], 
        node['xyz']['bx'], 
        node['xyz']['by'], 
        node['xyz']['bz'], 
        node['xyz']['cx'], 
        node['xyz']['cy'], 
        node['xyz']['cz'], 
        node['xyz']['x'], 
        node['xyz']['y'], 
        node['xyz']['z'], 
        node['xyz']['x1'], 
        node['xyz']['y1'], 
        node['xyz']['z1']
        ])
        
    elif switch_val == 53350:
        cursor = writeBulk(buffer, cursor, '3if', [
            node['53350']['unk1'],
            node['53350']['unk2'], 
            node['53350']['unk3'], 
            node['53350']['unk4'],
        ])
        
    if not len(node['children']):
        return cursor

    # write offset to this child list
    writeInt32BE(buffer, cursor, child_list_addr_addr)

    # child list
    child_list_addr = cursor
    for c in range(len(node['children'])):
        highlight(cursor, hl)
        cursor += 4

    # write children
    for c in range(len(node['children'])):
        child = node['children'][c]

        if 'AltN' in child:
            map_ref(child_list_addr + c * 4, child['id'],  model)
            continue

        if not 'id' in child:
            writeUInt32BE(buffer, 0, child_list_addr + c * 4)
            continue

        if child['id'] in model['ref_map']:
            writeUInt32BE(buffer, model['ref_map'][child['id']], child_list_addr + c * 4)
            continue

        writeUInt32BE(buffer, cursor, child_list_addr + c * 4)
        if mesh_group:
            cursor = write_mesh_group( buffer,  cursor,  child, hl,  model)
        else:
            cursor = write_node( buffer,  cursor, child, hl,  model,  header_offsets)

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
        cursor = write_node(buffer, cursor, model['nodes'][i],  hl,model, header_offsets)

    # write all animations
    if 'Anim' in model:
        for i in range(len(model['Anim'])):
            writeUInt32BE(buffer, cursor, header_offsets['Anim'] + i * 4)
            cursor = write_animation( buffer, cursor, model['Anim'][i], hl, model)

    # write all outside references
    refs = [ref for ref in model['ref_keeper'] if ref != '0']
    for ref in refs:
        for offset in model['ref_keeper'][ref]:
            writeUInt32BE(buffer, model['ref_map'][str(ref)], offset)

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
    print(ind, file_path)
    with open(file_path + '/out_modelblock.bin', 'rb') as file:
        file = file.read()
        read_block_result = read_block(file, [[], []], [])

    offset_buffers, model_buffers = read_block_result
    
    offset_buffers[ind] = offset_buffer
    model_buffers[ind] = model_buffer
    
    block = write_block([offset_buffers, model_buffers])
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
    with open(file_path + str(col['ind'])+'.bin', 'wb') as file:
        file.write(model_buffer)
    block = inject_model(offset_buffer, model_buffer, col['ind'], file_path)
    print(len(block), file_path + 'out_modelblock2.bin')
    with open(file_path + 'out_modelblock.bin', 'wb') as file:
        file.write(block)
    show_custom_popup(bpy.context, "Exported!", f"Model {col['ind']} was successfully exported")
    

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