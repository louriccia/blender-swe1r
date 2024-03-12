import sys
import os
import bpy
import struct
import json
import math
from .swe1r_import import read_block
from .popup import show_custom_popup
from .modelblock import Model
    
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
            'co': [round(co) for co in vert.co], 
            } for vert in mesh.data.vertices]
    
    color_layer = mesh.data.vertex_colors.active.data
    uv_layer = mesh.data.uv_layers.active.data
    
    if color_layer == None or uv_layer == None:
        return vert_buffer    
    
    for poly in mesh.data.polygons:
        for p in range(len(poly.vertices)):
            uv = [round(u*4096) for u in uv_layer[poly.loop_indices[p]].uv]
            vert_buffer[poly.vertices[p]]['uv'] = uv
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
        'id': mesh['id'],
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
        'children': [],
        'obj': obj
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
        cursor = writeUInt32BE(buffer, len(model['Data']['LStr']), cursor)

        for lstr in model['Data']['LStr']:
            cursor += buffer.write(b'LStr', cursor)
            for value in lstr:
                cursor = writeFloatBE(buffer, value, cursor)
    else:
        # Write size
        cursor = writeUInt32BE(buffer, len(model['Data']['other']), cursor)

        for value in model['Data']['other']:
            cursor = writeUInt32BE(buffer, value, cursor)

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
            writeUInt32BE(buffer, alt_n_value, cursor)
            
        cursor += 4

    highlight(cursor, hl)
    cursor += 4

    return cursor

def writeBulk(buffer, cursor, format_string, arr):
    print(arr)
    struct.pack_into(format_string, buffer, cursor, *arr)
    return cursor + struct.calcsize(format_string)

def writeString(buffer,  string, cursor):
    struct.pack_into('4s', buffer, cursor, string.encode('utf-8'))
    return cursor + struct.calcsize('4s')

def writeInt8(buffer, num, cursor):
    struct.pack_into('b', buffer, cursor, num)
    return cursor + struct.calcsize('b')

def writeUInt8(buffer, num, cursor):
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

def writeFloatBE(buffer, num, cursor):
    struct.pack_into('f', buffer, cursor, num)
    return cursor + struct.calcsize('f')



def write_header(buffer, cursor,  hl, model):
    cursor = writeString(buffer,  model['ext'], cursor)

    for header_value in model['header']:
        outside_ref(cursor, header_value, model)
        highlight(cursor, hl)
        cursor += 4  # writeInt32BE(buffer, header_value, cursor)

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

    cursor = writeInt32BE(buffer, mat['format'], cursor)

    # Handling format-specific data
    cursor += 12

    if mat['texture']:
        tex_id = mat['texture']
        highlight(mat_addr + 8, hl)

        if model['textures'][tex_id]['write']:
            writeUInt32BE(buffer, model['textures'][tex_id]['write'], mat_addr + 8)
        else:
            writeUInt32BE(buffer, cursor, mat_addr + 8)
            cursor = write_mat_texture(buffer, cursor, tex_id, hl, model)

    if mat['unk']:
        highlight(mat_addr + 12, hl)
        writeUInt32BE(buffer, cursor, mat_addr + 12)
        cursor = write_mat_unk(buffer, cursor, unk=mat['unk'])

    return cursor

def write_mat_texture(buffer, cursor, tex_id, hl, model):
    texture = model['textures'][tex_id]
    if not texture:
        return cursor

    model['textures'][tex_id]['write'] = cursor
    map_ref(cursor, tex_id, model)

    cursor = writeInt32BE(buffer, texture['unk0'], cursor)
    cursor = writeInt16BE(buffer, texture['unk1'], cursor)
    cursor = writeInt16BE(buffer, texture['unk2'], cursor)
    cursor = writeInt32BE(buffer, texture['unk3'], cursor)
    cursor = writeInt16BE(buffer, texture['format'], cursor)
    cursor = writeInt16BE(buffer, texture['unk4'], cursor)
    cursor = writeInt16BE(buffer, texture['width'], cursor)
    cursor = writeInt16BE(buffer, texture['height'], cursor)
    cursor = writeInt16BE(buffer, texture['unk5'], cursor)
    cursor = writeInt16BE(buffer, texture['unk6'], cursor)
    cursor = writeInt16BE(buffer, texture['unk7'], cursor)
    cursor = writeInt16BE(buffer, texture['unk8'], cursor)

    unk_pointer = cursor
    cursor += 28
    highlight(cursor, hl)
    cursor = writeInt16BE(buffer, texture['unk9'], cursor)
    cursor = writeInt16BE(buffer, texture['tex_index'], cursor)
    cursor += 4

    for unk_pointer_value in texture['unk_pointers']:
        highlight(unk_pointer, hl)
        writeUInt32BE(buffer, cursor, unk_pointer)
        cursor = writeInt32BE(buffer, unk_pointer_value['unk0'], cursor)
        cursor = writeInt32BE(buffer, unk_pointer_value['unk1'], cursor)
        cursor = writeInt32BE(buffer, unk_pointer_value['unk2'], cursor)
        cursor = writeInt16BE(buffer, unk_pointer_value['unk3'], cursor)
        cursor = writeInt16BE(buffer, unk_pointer_value['unk4'], cursor)

    return cursor

def write_mat_unk(buffer, cursor, unk):
    cursor = writeInt16BE(buffer, unk['unk0'], cursor)  # always 0
    cursor = writeInt16BE(buffer, unk['unk1'], cursor)  # 0, 1, 8, 9
    cursor = writeInt16BE(buffer, unk['unk2'], cursor)  # 1, 2
    cursor = writeInt16BE(buffer, unk['unk3'], cursor)  # 287, 513, 799, 1055, 1537, 7967
    cursor = writeInt16BE(buffer, unk['unk4'], cursor)  # 287, 799, 1055, 3329, 7939, 7940
    cursor = writeInt16BE(buffer, unk['unk5'], cursor)  # 263, 513, 775, 1031, 1537, 1795, 1799
    cursor = writeInt16BE(buffer, unk['unk6'], cursor)  # 1, 259, 263, 775, 1031, 1793, 1795, 1796, 1798
    cursor = writeInt16BE(buffer, unk['unk7'], cursor)  # 31, 287, 799, 1055, 7967
    cursor = writeInt16BE(buffer, unk['unk8'], cursor)  # 31, 799, 1055, 7936, 7940
    cursor = writeInt16BE(buffer, unk['unk9'], cursor)  # 7, 1799
    cursor = writeInt16BE(buffer, unk['unk10'], cursor)  # 775, 1031, 1792, 1796, 1798
    cursor = writeInt16BE(buffer, unk['unk11'], cursor)  # always 0
    cursor = writeInt16BE(buffer, unk['unk12'], cursor)  # -14336, 68, 3080
    cursor = writeInt16BE(buffer, unk['unk13'], cursor)  # 0, 1, 8200, 8312
    cursor = writeInt16BE(buffer, unk['unk14'], cursor)  # 16, 17, 770
    cursor = writeInt16BE(buffer, unk['unk15'], cursor)  # 120, 8200, 8248, 8296, 8312, 16840, 16856, 16960, 17216, 18760, 18768, 18808, 18809, 18888, 18904, 18936, 19280, 20048
    cursor = writeInt16BE(buffer, unk['unk16'], cursor)  # probably 0?
    cursor = writeUInt8(buffer, unk['r'], cursor)
    cursor = writeUInt8(buffer, unk['g'], cursor)
    cursor = writeUInt8(buffer, unk['b'], cursor)
    cursor = writeUInt8(buffer, unk['t'], cursor)
    cursor = writeInt16BE(buffer, unk['unk17'], cursor)
    cursor = writeInt16BE(buffer, unk['unk18'], cursor)
    cursor = writeInt16BE(buffer, unk['unk19'], cursor)
    cursor = writeInt16BE(buffer, unk['unk20'], cursor)
    cursor = writeInt16BE(buffer, unk['unk21'], cursor)
    cursor = writeInt16BE(buffer, unk['unk22'], cursor)
    cursor = writeInt16BE(buffer, unk['unk23'], cursor)

    return cursor

def write_animation(buffer, cursor, animation, hl, model):
    cursor += 61 * 4
    cursor = writeFloatBE(buffer, animation['float1'], cursor)
    cursor = writeFloatBE(buffer, animation['float2'], cursor)
    cursor = writeFloatBE(buffer, animation['float3'], cursor)
    cursor = writeInt16BE(buffer, animation['flag1'], cursor)
    cursor = writeInt16BE(buffer, animation['flag2'], cursor)
    cursor = writeInt32BE(buffer, animation['num_keyframes'], cursor)
    cursor = writeFloatBE(buffer, animation['float4'], cursor)
    cursor = writeFloatBE(buffer, animation['float5'], cursor)
    cursor = writeFloatBE(buffer, animation['float6'], cursor)
    cursor = writeFloatBE(buffer, animation['float7'], cursor)
    cursor = writeFloatBE(buffer, animation['float8'], cursor)
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
    cursor = writeInt32BE(buffer, animation['unk32'], cursor)

    # Write keyframe times
    writeInt32BE(buffer, cursor, keyframe_times)
    for k in range(len(animation['keyframe_times'])):
        cursor = writeFloatBE(buffer, animation['keyframe_times'][k], cursor)

    if flag in [2, 18]:
        # Write target list
        writeInt32BE(buffer, cursor, anim_target)
        highlight(cursor, hl)
        cursor = writeInt32BE(buffer, model['mats'][animation['target']]['write'], cursor)
        highlight(cursor, hl)
        cursor += 4

    # Write keyframe poses
    writeInt32BE(buffer, cursor, keyframe_poses)

    for p in range(len(animation['keyframe_poses'])):
        if flag in [8, 24, 40, 56, 4152]:  # rotation (4)
            for f in range(4):
                cursor = writeFloatBE(buffer, animation['keyframe_poses'][p][f], cursor)
        elif flag in [25, 41, 57, 4153]:  # position (3)
            for f in range(3):
                cursor = writeFloatBE(buffer, animation['keyframe_poses'][p][f], cursor)
        elif flag in [27, 28]:  # uv_x/uv_y (1)
            cursor = writeFloatBE(buffer, animation['keyframe_poses'][p], cursor)

    if flag in [2, 18]:  # texture
        texturelist = cursor
        for k in range(len(animation['keyframe_poses'])):
            highlight(cursor, hl)
            cursor += 4
        for k in range(len(animation['keyframe_poses'])):
            tex_id = animation['keyframe_poses'][k]
            if model['textures'][tex_id]['write']:
                writeUInt32BE(buffer, model['textures'][tex_id]['write'], texturelist + k * 4)
            else:
                writeUInt32BE(buffer, cursor, texturelist + k * 4)
                cursor = write_mat_texture(buffer, cursor, tex_id, hl, model)

    return cursor

def write_collision_vert_strips(buffer, cursor, vert_strips):
    if not vert_strips or not vert_strips:
        return cursor

    for v in range(len(vert_strips)):
        cursor = writeInt32BE(buffer, vert_strips[v], cursor)

    return cursor

def write_collision_vert_buffer(buffer, cursor, vert_buffer):
    if not vert_buffer or not vert_buffer:
        return cursor

    for v in range(len(vert_buffer)):
        vert = vert_buffer[v]
        for i in range(len(vert)):
            cursor = writeInt16BE(buffer, vert[i], cursor)

    return cursor if cursor % 4 == 0 else cursor + 2

def write_collision_triggers(buffer, cursor, triggers, hl, model):
    for i in range(len(triggers)):
        trigger = triggers[i]
        highlight(cursor, hl)
        cursor = writeInt32BE(buffer, cursor + 4, cursor)
        cursor = writeFloatBE(buffer, trigger['x'], cursor)
        cursor = writeFloatBE(buffer, trigger['y'], cursor)
        cursor = writeFloatBE(buffer, trigger['z'], cursor)
        cursor = writeFloatBE(buffer, trigger['vx'], cursor)
        cursor = writeFloatBE(buffer, trigger['vy'], cursor)
        cursor = writeFloatBE(buffer, trigger['vz'], cursor)
        cursor = writeFloatBE(buffer, trigger['width'], cursor)
        cursor = writeFloatBE(buffer, trigger['height'], cursor)
        outside_ref(cursor, trigger['target'], model)
        highlight(cursor, hl)
        cursor += 4
        cursor = writeInt16BE(buffer, trigger['flag'], cursor)
        cursor += 2

    highlight(cursor, hl)  # end with blank pointer to mark the end of the linked list
    cursor += 4
    return cursor

def write_collision_data(buffer, cursor, data, hl, model):
    print(data)
    cursor = writeBulk(buffer, cursor, 'H4B3H8B6f2I2i', [
        data['unk'],
        data['fog']['flag'],
        *data['fog']['color'][:3],
        data['fog']['start'],
        data['fog']['end'],
        data['lights']['flag'],
        *data['lights']['ambient_color'][:3],
        *data['lights']['color'][:3],
        data['lights']['unk1'],
        data['lights']['unk2'],
        *data['lights']['pos'],
        *data['lights']['rot'],
        data['flags'],
        data['unk2'],
        int(data['unload'], 2),
        int(data['load'], 2)
    ])
    
    cursor = write_collision_triggers(buffer, cursor, data.get('triggers', []), hl, model)

    return cursor

def write_visual_index_buffer(buffer, cursor, index_buffer, hl):
    if not index_buffer or not index_buffer:
        return cursor

    v = 0
    for i in range(len(index_buffer)):
        index = index_buffer[i]
        type_ = index['type']
        writeUInt8(buffer, type_, cursor + v)

        if type_ == 1:
            writeUInt8(buffer, index['unk1'], cursor + v + 1)
            writeUInt8(buffer, index['unk2'], cursor + v + 2)
            writeUInt8(buffer, index['size'], cursor + v + 3)
            highlight(cursor + v + 4, hl)
            # writeUInt32BE(buffer, index['start'], cursor + v + 4)

        elif type_ == 3:
            writeUInt8(buffer, index['unk'], cursor + v + 7)

        elif type_ == 5:
            writeUInt8(buffer, index['x'], cursor + v + 1)
            writeUInt8(buffer, index['y'], cursor + v + 2)
            writeUInt8(buffer, index['z'], cursor + v + 3)

        elif type_ == 6:
            writeUInt8(buffer, index['x1'], cursor + v + 1)
            writeUInt8(buffer, index['y1'], cursor + v + 2)
            writeUInt8(buffer, index['z1'], cursor + v + 3)
            writeUInt8(buffer, index['x2'], cursor + v + 5)
            writeUInt8(buffer, index['y2'], cursor + v + 6)
            writeUInt8(buffer, index['z2'], cursor + v + 7)

        v += 8

    cursor += v
    cursor = writeUInt8(buffer, 223, cursor)
    cursor += 7
    return cursor

def write_visual_vert_buffer(buffer, cursor, vert_buffer, index_buffer, index_buffer_addr):
    vert_buffer_addr = cursor

    # Write buffer
    for i in range(len(vert_buffer)):
        x, y, z = vert_buffer[i]['x'], vert_buffer[i]['y'], vert_buffer[i]['z']
        cursor = writeInt16BE(buffer, x, cursor)
        cursor = writeInt16BE(buffer, y, cursor)
        cursor = writeInt16BE(buffer, z, cursor)
        cursor += 2

        cursor = writeInt16BE(buffer, vert_buffer[i]['uv_x'], cursor)
        cursor = writeInt16BE(buffer, vert_buffer[i]['uv_y'], cursor)

        cursor = writeUInt8(buffer, vert_buffer[i]['v_color'][0], cursor)
        cursor = writeUInt8(buffer, vert_buffer[i]['v_color'][1], cursor)
        cursor = writeUInt8(buffer, vert_buffer[i]['v_color'][2], cursor)
        cursor = writeUInt8(buffer, vert_buffer[i]['v_color'][3], cursor)

    # Write references in index_buffer to this section
    total = 0
    for i, index in enumerate(index_buffer):
        if index['type'] == 1:
            writeUInt32BE(buffer, vert_buffer_addr + index['start'] * 16, index_buffer_addr + i * 8 + 4)

    return cursor

def write_mesh_group(buffer, cursor, mesh, hl, model):
    headstart = cursor
    bb = mesh_bounding_box(mesh)
    writeFloatBE(buffer, bb['min'][0], cursor + 8)
    writeFloatBE(buffer, bb['min'][1], cursor + 12)
    writeFloatBE(buffer, bb['min'][2], cursor + 16)
    writeFloatBE(buffer, bb['max'][0], cursor + 20)
    writeFloatBE(buffer, bb['max'][1], cursor + 24)
    writeFloatBE(buffer, bb['max'][2], cursor + 28)
    writeInt16BE(buffer, mesh.get('vert_strip_count', 0), cursor + 32)
    writeInt16BE(buffer, mesh.get('vert_strip_default', 0), cursor + 34)
    highlight(cursor + 40,  hl)
    outside_ref( cursor + 40, mesh['visuals'].get('group_parent', 0),model)
    writeInt16BE(buffer, len(mesh['collision'].get('vert_buffer', [])), cursor + 56)
    writeInt16BE(buffer, len(mesh['visuals'].get('vert_buffer', [])), cursor + 58)
    writeInt16BE(buffer, mesh['visuals'].get('group_count', 0), cursor + 62)
    cursor += 64

    if mesh['collision']['vert_strips']:
        highlight(headstart + 36,  hl)
        writeUInt32BE(buffer, cursor, headstart + 36)
        cursor = write_collision_vert_strips( buffer, cursor,  mesh['collision']['vert_strips'])

    if mesh['collision']['vert_buffer']:
        highlight(headstart + 44,  hl)
        writeUInt32BE(buffer, cursor, headstart + 44)
        cursor = write_collision_vert_buffer( buffer,  cursor, mesh['collision']['vert_buffer'])

    if mesh['visuals']['material']:
        highlight(headstart, hl)
        mat_id = mesh['visuals']['material']
        if model['mats'][mat_id]['write']:
            writeUInt32BE(buffer, model['mats'][mat_id]['write'], headstart)
        else:
            writeUInt32BE(buffer, cursor, headstart)
            cursor = write_mat(buffer,  cursor, mat_id,  hl, model)

    index_buffer_addr = None
    if mesh['visuals']['index_buffer']:
        highlight(headstart + 48,  hl)
        index_buffer_addr = cursor if cursor % 8 == 0 else cursor + 4
        writeInt32BE(buffer, index_buffer_addr, headstart + 48)
        cursor = write_visual_index_buffer(buffer,  index_buffer_addr, mesh['visuals']['index_buffer'], hl)

    if mesh['visuals']['vert_buffer'] and len(mesh['visuals']['vert_buffer']):
        highlight(headstart + 52,  hl)
        writeUInt32BE(buffer, cursor, headstart + 52)
        cursor = write_visual_vert_buffer( buffer, cursor,  mesh['visuals']['vert_buffer'], mesh['visuals']['index_buffer'],  index_buffer_addr)

    if mesh['collision']['data']:
        highlight(headstart + 4, hl)
        writeUInt32BE(buffer, cursor, headstart + 4)
        cursor = write_collision_data(buffer,  cursor, mesh['collision']['data'], hl,  model)

    return cursor

def node_bounding_box(node):
    bbs = [mesh_bounding_box(child) for child in node['children']]
    bb = {
        'min': [
            float(min([b['min'][0] for b in bbs])),
            float(min([b['min'][1] for b in bbs])),
            float(min([b['min'][2] for b in bbs]))
        ],
        'max': [
            float(max([b['min'][0] for b in bbs])),
            float(max([b['min'][1] for b in bbs])),
            float(max([b['min'][2] for b in bbs]))
        ]
    }
    return bb
    
def mesh_bounding_box(mesh):
    verts = []
    if 'vert_buffer' in mesh['visuals']:
        verts.extend(vert['co'] for vert in mesh['visuals']['vert_buffer'])
    if 'vert_buffer' in mesh['collision'] and mesh['collision']['vert_buffer'] != 0:
        verts.extend(mesh['collision']['vert_buffer'])
    bb = {
        'min': [
            min([vert[0] for vert in verts]), 
            min([vert[1] for vert in verts]), 
            min([vert[2] for vert in verts])],
        'max': [
            max([vert[0] for vert in verts]), 
            max([vert[1] for vert in verts]), 
            max([vert[2] for vert in verts])
            ]
    }
    return bb
            

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
    switch_val = int(node['head'][0])
    if switch_val == 12388:
        print('found a mesh_group at', cursor)
        mesh_group = True
        bb = node_bounding_box(node)
        cursor = writeBulk(buffer, cursor, '6f', [
            bb['min'][0], 
            bb['min'][1], 
            bb['min'][2], 
            bb['max'][0], 
            bb['max'][1], 
            bb['max'][2], 
        ])
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
        matrix = node['obj'].matrix_world
        cursor = writeBulk(buffer, cursor, '15f', [
        matrix[0][0], 
        matrix[0][1], 
        matrix[0][2], 
        matrix[1][0], 
        matrix[1][1], 
        matrix[1][2], 
        matrix[2][0], 
        matrix[2][1], 
        matrix[2][2], 
        matrix[3][0], 
        matrix[3][1], 
        matrix[3][2], 
        0,
        0,
        0
        ])
        
    elif switch_val == 53350:
        cursor = writeBulk(buffer, cursor, '3if', [
            node['obj']['53350_unk1'],
            node['obj']['53350_unk2'], 
            node['obj']['53350_unk3'], 
            node['obj']['53350_unk4'],
        ])
        
    if not len(node['children']):
        return cursor
    print(mesh_group, len(node['children']))
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
            print('altn child')
            map_ref(child_list_addr + c * 4, child['id'],  model)
            continue

        if not 'id' in child:
            print('id child')
            writeUInt32BE(buffer, 0, child_list_addr + c * 4)
            continue

        if child['id'] in model['ref_map']:
            print('already written child')
            writeUInt32BE(buffer, model['ref_map'][child['id']], child_list_addr + c * 4)
            continue

        writeUInt32BE(buffer, cursor, child_list_addr + c * 4)
        if mesh_group:
            print('making a mesh_group child at', cursor)
            cursor = write_mesh_group( buffer,  cursor,  child, hl,  model)
        else:
            print('making a child at ', cursor)
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
    model = Model(col['ind']).unmake(col)
    offset_buffer, model_buffer = model.write()
    
    with open(file_path + str(col['ind'])+'.bin', 'wb') as file:
        file.write(model_buffer)
    block = inject_model(offset_buffer, model_buffer, col['ind'], file_path)
    with open(file_path + 'out_modelblock.bin', 'wb') as file:
        file.write(block)
        
    show_custom_popup(bpy.context, "Exported!", f"Model {col['ind']} was successfully exported")
    
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