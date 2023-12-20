# Copyright (C) 2021-2024
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

import sys
import os
import bpy
import struct
from .modelblock import Model

# for material in bpy.data.materials:
#     material.user_clear()
#     bpy.data.materials.remove(material)

# for obj in bpy.data.objects:
#     bpy.data.objects.remove(obj)
    
# for col in bpy.data.collections:
#     bpy.data.collections.remove(col)
    
# for img in bpy.data.images:
#     bpy.data.images.remove(img)

scale = 0.01

def make_LStr(location, index):
    lightstreak_col = bpy.data.collections.get(f"{index}_lightstreaks")
    light = bpy.data.lights.new(name = "lightstreak",type = 'POINT')
    light_object = bpy.data.objects.new(name = "lightstreak", object_data = light)
    lightstreak_col.objects.link(light_object)
    light_object.location = (location[0]*scale, location[1]*scale, location[2]*scale)

def read_Data(buffer, cursor, model):
    model['Data'] = {'LStr': [], 'other': []}
    size = readUInt32BE(buffer, cursor)
    cursor += 4
    i = 0
    while i < size:
        if readString(buffer, cursor) == 'LStr':
            cursor += 4
            make_LStr(readVec3(buffer, cursor), model["id"])
            cursor += 12
            i += 4
        else:
            model['Data']['other'].append(readUInt32BE(buffer,cursor))
            i+=1
            cursor += 4

    return cursor

def read_Anim(buffer, cursor, model):
    model['Anim'] = []
    anim = readUInt32BE(buffer, cursor)

    while anim:
        model['Anim'].append(read_animation(buffer=buffer, cursor=anim, model=model))
        cursor += 4
        anim = readUInt32BE(buffer, cursor)

    return cursor + 4

def read_AltN(buffer, cursor, model):
    model['AltN'] = []
    altn = readUInt32BE(buffer, cursor)

    while altn:
        model['AltN'].append(altn)
        cursor += 4
        altn = readUInt32BE(buffer, cursor)

    return cursor + 4



def read_mat(buffer, cursor, model):
    if not cursor:
        return 0

    mat = {
        'id': cursor,
        'format': readInt32BE(buffer, cursor),
        'texture': read_mat_texture(buffer=buffer, cursor=readUInt32BE(buffer,cursor + 8), model=model),
        'unk': read_mat_unk(buffer=buffer, cursor=readInt32BE(buffer,cursor + 12))
    }

    if cursor not in model['mats']:
        model['mats'][cursor] = mat

    return cursor

def read_mat_texture(buffer, cursor, model):
    if not cursor:
        return 0

    mat = {
        'id': cursor,
        'unk0': readInt32BE(buffer,cursor),  # 0, 1, 65, 73
        'unk1': readInt16BE(buffer, cursor + 4),  # width * 4
        'unk2': readInt16BE(buffer, cursor + 6),  # height * 4
        'unk3': readInt32BE(buffer,cursor + 8),  # always 0
        'format': readInt16BE(buffer, cursor + 12),  # 3, 512, 513, 1024
        'unk4': readInt16BE(buffer, cursor + 14),  # 0, 4
        'width': readInt16BE(buffer, cursor + 16),  # pixel width
        'height': readInt16BE(buffer, cursor + 18),  # pixel height
        'unk5': readInt16BE(buffer, cursor + 20),  # width * 512 (unsigned)
        'unk6': readInt16BE(buffer, cursor + 22),  # height * 512 (unsigned)
        'unk7': readInt16BE(buffer, cursor + 24),  # 0 when unk4 is 4,
        'unk8': readInt16BE(buffer, cursor + 26),
        'unk_pointers': [],
        'unk9': readInt16BE(buffer, cursor + 56),  # 2560, 2815 is used when cursor index is blank
        'tex_index': readInt16BE(buffer, cursor + 58),
    }

    for i in range(6):
        pointer = readInt32BE(buffer,cursor + 28 + i * 4)
        if pointer:
            mat['unk_pointers'].append({
                'unk0': readInt32BE(buffer,pointer),
                'unk1': readInt32BE(buffer,pointer + 4),
                'unk2': readInt32BE(buffer,pointer + 8),
                'unk3': readInt16BE(buffer, pointer + 12),
                'unk4': readInt16BE(buffer, pointer + 14),
            })
        else:
            break

    if cursor not in model['textures']:
        model['textures'][cursor] = mat

    return cursor

def read_mat_unk(buffer, cursor):
    if not cursor:
        return 0

    return {
        'unk0': readInt16BE(buffer, cursor),  # always 0
        'unk1': readInt16BE(buffer, cursor + 2),  # 0, 1, 8, 9
        'unk2': readInt16BE(buffer, cursor + 4),  # 1, 2
        'unk3': readInt16BE(buffer, cursor + 6),  # 287, 513, 799, 1055, 1537, 7967
        'unk4': readInt16BE(buffer, cursor + 8),  # 287, 799, 1055, 3329, 7939, 7940
        'unk5': readInt16BE(buffer, cursor + 10),  # 263, 513, 775, 1031, 1537, 1795, 1799
        'unk6': readInt16BE(buffer, cursor + 12),  # 1, 259, 263, 775, 1031, 1793, 1795, 1796, 1798,
        'unk7': readInt16BE(buffer, cursor + 14),  # 31, 287, 799, 1055, 7967
        'unk8': readInt16BE(buffer, cursor + 16),  # 31, 799, 1055, 7936, 7940
        'unk9': readInt16BE(buffer, cursor + 18),  # 7, 1799
        'unk10': readInt16BE(buffer, cursor + 20),  # 775, 1031, 1792, 1796, 1798
        'unk11': readInt16BE(buffer, cursor + 22),  # always 0
        'unk12': readInt16BE(buffer, cursor + 24),  # -14336, 68, 3080
        'unk13': readInt16BE(buffer, cursor + 26),  # 0, 1, 8200, 8312
        'unk14': readInt16BE(buffer, cursor + 28),  # 16, 17, 770
        'unk15': readInt16BE(buffer, cursor + 30),  # 120, 8200, 8248, 8296, 8312, 16840, 16856, 16960, 17216, 18760, 18768, 18808, 18809, 18888, 18904, 18936, 19280, 20048
        'unk16': readInt16BE(buffer, cursor + 32),  # probably 0?
        'r': readUInt8(buffer, cursor + 34),
        'g': readUInt8(buffer, cursor + 35),
        'b': readUInt8(buffer, cursor + 36),
        't': readUInt8(buffer, cursor + 37),
        'unk17': readInt16BE(buffer, cursor + 38),
        'unk18': readInt16BE(buffer, cursor + 40),
        'unk19': readInt16BE(buffer, cursor + 42),
        'unk20': readInt16BE(buffer, cursor + 44),
        'unk21': readInt16BE(buffer, cursor + 46),
        'unk22': readInt16BE(buffer, cursor + 48),
        'unk23': readInt16BE(buffer, cursor + 50)
    }

def read_animation(buffer, cursor, model):
    anim = {
        'float1': readFloatBE(buffer, cursor + 61 * 4),
        'float2': readFloatBE(buffer, cursor + 62 * 4),
        'float3': readFloatBE(buffer, cursor + 63 * 4),  # first three floats always match
        'flag1': readInt16BE(buffer, cursor + 64 * 4),  # always 4352
        'flag2': readInt16BE(buffer, cursor + 64 * 4 + 2),
        'num_keyframes': readInt32BE(buffer,cursor + 65 * 4),
        'float4': readFloatBE(buffer, cursor + 66 * 4),
        'float5': readFloatBE(buffer, cursor + 67 * 4),
        'float6': readFloatBE(buffer, cursor + 68 * 4),  # always 1
        'float7': readFloatBE(buffer, cursor + 69 * 4),  # always 0
        'float8': readFloatBE(buffer, cursor + 70 * 4),  # always 0
        'keyframe_times': readInt32BE(buffer,cursor + 71 * 4),
        'keyframe_poses': readInt32BE(buffer,cursor + 72 * 4),
        'target': readInt32BE(buffer,cursor + 73 * 4),
        'unk32': readInt32BE(buffer,cursor + 74 * 4),
    }

    keyframe_times = anim['keyframe_times']
    keyframe_poses = anim['keyframe_poses']
    anim['keyframe_times'] = []
    anim['keyframe_poses'] = []

    if anim['flag2'] in [2, 18]:
        anim['target'] = readUInt32BE(buffer,anim['target'])

    for f in range(anim['num_keyframes']):
        if keyframe_times:
            anim['keyframe_times'].append(readFloatBE(buffer, keyframe_times + f * 4))

        if keyframe_poses:
            if anim['flag2'] in [8, 24, 40, 56, 4152]:  # rotation (4)
                anim['keyframe_poses'].append([
                    readFloatBE(buffer, keyframe_poses + f * 16),
                    readFloatBE(buffer, keyframe_poses + f * 16 + 4),
                    readFloatBE(buffer, keyframe_poses + f * 16 + 8),
                    readFloatBE(buffer, keyframe_poses + f * 16 + 12)
                ])
            elif anim['flag2'] in [25, 41, 57, 4153]:  # position (3)
                anim['keyframe_poses'].append([
                    readFloatBE(buffer, keyframe_poses + f * 12),
                    readFloatBE(buffer, keyframe_poses + f * 12 + 4),
                    readFloatBE(buffer, keyframe_poses + f * 12 + 8)
                ])
            elif anim['flag2'] in [27, 28]:  # uv_x/uv_y (1)
                anim['keyframe_poses'].append([
                    readFloatBE(buffer, keyframe_poses + f * 4)
                ])
            elif anim['flag2'] in [2, 18]:  # texture
                tex = readUInt32BE(buffer,keyframe_poses + f * 4)

                if tex < cursor:
                    anim['keyframe_poses'].append({'repeat': tex})
                else:
                    anim['keyframe_poses'].append(read_mat_texture(buffer=buffer, cursor=tex, model=model))

    return anim

def read_collision_vert_strips(buffer, cursor, count, default):
    if not cursor:
        return 0

    vert_strips = []

    for v in range(count):
        vert_strips.append(readInt32BE(buffer, cursor + v * 4))

    return vert_strips

def read_collision_vert_buffer(buffer, cursor, count):
    if not cursor:
        return 0

    vert_buffer = []

    for v in range(count):
        vert_buffer.append([
            readInt16BE(buffer, cursor + v * 6),
            readInt16BE(buffer, cursor + v * 6 + 2),
            readInt16BE(buffer, cursor + v * 6 + 4)
        ])

    return vert_buffer

def read_collision_triggers(buffer, cursor):
    # reads through a linked list
    next_trigger = cursor
    triggers = []

    while next_trigger:
        trigger = {
            'x': readFloatBE(buffer, next_trigger),
            'y': readFloatBE(buffer, next_trigger + 4),
            'z': readFloatBE(buffer, next_trigger + 8),
            'vx': readFloatBE(buffer, next_trigger + 12),
            'vy': readFloatBE(buffer, next_trigger + 16),
            'vz': readFloatBE(buffer, next_trigger + 20),
            'width': readFloatBE(buffer, next_trigger + 24),
            'height': readFloatBE(buffer, next_trigger + 28),
            'target': readUInt32BE(buffer,next_trigger + 32),
            'flag': readInt16BE(buffer, next_trigger + 36),
        }
        triggers.append(trigger)
        next_trigger = readUInt32BE(buffer,next_trigger + 40)

    return triggers

def read_collision_data(buffer, cursor):
    if not cursor:
        return 0

    data = {
        'unk': readInt16BE(buffer, cursor),  # 2, 4, 16, 18, 20, 32, 36
        'fog_flag': readUInt8(buffer, cursor + 2),  # 0, 1, 2, 3, 4, 5, 7, 11, 12
        'fog_color': [a/255 for a in [readUInt8(buffer, cursor + 3), readUInt8(buffer, cursor + 4), readUInt8(buffer, cursor + 5), 255]],
        'fog_start': readInt16BE(buffer, cursor + 6),
        'fog_stop': readInt16BE(buffer, cursor + 8),  # 1000 - 6000
        'lights_flag': readInt16BE(buffer, cursor + 10),  # 0, 1, 3, 6, 7, 11, 15, 23
        'lights_ambient_color': [a/255 for a in [readUInt8(buffer, cursor + 12),readUInt8(buffer, cursor + 13),readUInt8(buffer, cursor + 14), 255]],
        'lights_color': [a/255 for a in [readUInt8(buffer, cursor + 15), readUInt8(buffer, cursor + 16),  readUInt8(buffer, cursor + 17), 255]],
        'unk1': readUInt8(buffer, cursor + 18),
        'unk2': readUInt8(buffer, cursor + 19),
        'lights_pos': [readFloatBE(buffer, cursor + 20), readFloatBE(buffer, cursor + 24), readFloatBE(buffer, cursor + 28)],
        'lights_rot': [ readFloatBE(buffer, cursor + 32), readFloatBE(buffer, cursor + 36),  readFloatBE(buffer, cursor + 40)],
        'flags': readUInt32BE(buffer,cursor + 44),  # >>> 0).toString(2),
        'unk3': readUInt32BE(buffer,cursor + 48),
        'unload': bin(readUInt32BE(buffer,cursor + 52)),  # >>> 0).toString(2),
        'load': bin(readUInt32BE(buffer,cursor + 56)),  # >>> 0).toString(2),
        'triggers': read_collision_triggers(buffer=buffer, cursor=readUInt32BE(buffer,cursor + 60))
    }

    return data

def read_visual_index_buffer(buffer, cursor, vert_buffer_start):
    if not cursor:
        return 0

    index_buffer = []
    v = 0

    while readUInt8(buffer, cursor + v) != 223:
        type = readUInt8(buffer, cursor + v)

        if type == 1:
            index_buffer.append({
                'type': type,
                'unk1': readUInt8(buffer, cursor + v + 1),
                'unk2': readUInt8(buffer, cursor + v + 2),
                'size': readUInt8(buffer, cursor + v + 3),
                'start': round((readUInt32BE(buffer,cursor + v + 4) - vert_buffer_start) / 16)
            })
        elif type == 3:
            index_buffer.append({
                'type': type,
                'unk': readUInt8(buffer, cursor + v + 7)
            })
        elif type == 5:
            index_buffer.append({
                'type': type,
                'x': round(readUInt8(buffer, cursor + v + 1)/2),
                'y': round(readUInt8(buffer, cursor + v + 2)/2),
                'z': round(readUInt8(buffer, cursor + v + 3)/2)
            })
        elif type == 6:
            index_buffer.append({
                'type': type,
                'x1': round(readUInt8(buffer, cursor + v + 1)/2),
                'y1': round(readUInt8(buffer, cursor + v + 2)/2),
                'z1': round(readUInt8(buffer, cursor + v + 3)/2),
                'x2': round(readUInt8(buffer, cursor + v + 5)/2),
                'y2': round(readUInt8(buffer, cursor + v + 6)/2),
                'z2': round(readUInt8(buffer, cursor + v + 7)/2)
            })

        v += 8

    return index_buffer

def read_visual_vert_buffer(buffer, cursor, count):
    vert_buffer = []
    for v in range(count):
        vert_buffer.append({
            'x': readInt16BE(buffer, cursor + v * 16),
            'y': readInt16BE(buffer, cursor + v * 16 + 2),
            'z': readInt16BE(buffer, cursor + v * 16 + 4),
            'uv_x': readInt16BE(buffer, cursor + v * 16 + 8),
            'uv_y': readInt16BE(buffer, cursor + v * 16 + 10),
            'v_color': [
                readUInt8(buffer, cursor + v * 16 + 12),
                readUInt8(buffer, cursor + v * 16 + 13),
                readUInt8(buffer, cursor + v * 16 + 14),
                readUInt8(buffer, cursor + v * 16 + 15)
            ]
        })
    return vert_buffer

    

        
    

def make_material(mat, tex, file_path):
    offset = str(mat['id'])
    if (mat['texture'] != 0):
        material = bpy.data.materials.get(offset)
        if material is not None:
            return material
        
        material = bpy.data.materials.new(offset)
        material.use_nodes = True
        #material.blend_method = 'BLEND' #use for transparency
        material.blend_method = 'CLIP'
        if tex['format'] == 3:
            material.blend_method = 'BLEND'
        if mat['format'] != 6:
            material.use_backface_culling = True
        if mat['unk']['unk1'] == 8:
            material.show_transparent_back = False
        else:
            material.show_transparent_back = True
         
        node_1 = material.node_tree.nodes.new("ShaderNodeTexImage")
        node_2 = material.node_tree.nodes.new("ShaderNodeVertexColor")
        node_3 = material.node_tree.nodes.new("ShaderNodeMixRGB")
        node_3.blend_type = 'MULTIPLY'
        node_3.inputs[0].default_value = 1
        material.node_tree.links.new(node_1.outputs["Color"], node_3.inputs["Color1"])
        material.node_tree.links.new(node_2.outputs["Color"], node_3.inputs["Color2"])
        material.node_tree.links.new(node_3.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Base Color"])
        material.node_tree.links.new(node_1.outputs["Alpha"], material.node_tree.nodes['Principled BSDF'].inputs["Alpha"])
        material.node_tree.nodes["Principled BSDF"].inputs[5].default_value = 0
        material.node_tree.nodes["Principled BSDF"].inputs[7].default_value = 0 #turn off specular
        
        image = str(tex['tex_index'])
        if image in ["1167", "1077", "1461", "1596"]: #probably shouldn't do it this way; TODO find specific tag
            material.blend_method = 'BLEND'
            material.node_tree.links.new(node_1.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Alpha"])
        
        if mat['format'] in [31, 15, 7]:
            material.node_tree.links.new(node_2.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Normal"])
            material.node_tree.links.new(node_1.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Base Color"])
        
        if(len(tex['unk_pointers']) and tex['unk_pointers'][0]['unk0'] & 0x11 != 0):
            node_4 = material.node_tree.nodes.new("ShaderNodeUVMap")
            node_5 = material.node_tree.nodes.new("ShaderNodeSeparateXYZ")
            node_6 = material.node_tree.nodes.new("ShaderNodeCombineXYZ")
            material.node_tree.links.new(node_4.outputs["UV"], node_5.inputs["Vector"])
            material.node_tree.links.new(node_6.outputs["Vector"], node_1.inputs["Vector"])
            if(tex['unk_pointers'][0]['unk0'] & 0x11 == 0x11):
                node_7 = material.node_tree.nodes.new("ShaderNodeMath")
                node_7.operation = 'PINGPONG'
                node_7.inputs[1].default_value = 1
                material.node_tree.links.new(node_5.outputs["X"], node_7.inputs["Value"])
                material.node_tree.links.new(node_7.outputs["Value"], node_6.inputs["X"])
                node_8 = material.node_tree.nodes.new("ShaderNodeMath")
                node_8.operation = 'PINGPONG'
                node_8.inputs[1].default_value = 1
                material.node_tree.links.new(node_5.outputs["Y"], node_8.inputs["Value"])
                material.node_tree.links.new(node_8.outputs["Value"], node_6.inputs["Y"])
            elif(tex['unk_pointers'][0]['unk0'] & 0x11 == 0x01):
                material.node_tree.links.new(node_5.outputs["X"], node_6.inputs["X"])
                node_7 = material.node_tree.nodes.new("ShaderNodeMath")
                node_7.operation = 'PINGPONG'
                node_7.inputs[1].default_value = 1
                material.node_tree.links.new(node_5.outputs["Y"], node_7.inputs["Value"])
                material.node_tree.links.new(node_7.outputs["Value"], node_6.inputs["Y"])
            elif(tex['unk_pointers'][0]['unk0'] & 0x11 == 0x10):
                node_7 = material.node_tree.nodes.new("ShaderNodeMath")
                node_7.operation = 'PINGPONG'
                node_7.inputs[1].default_value = 1
                material.node_tree.links.new(node_5.outputs["X"], node_7.inputs["Value"])
                material.node_tree.links.new(node_7.outputs["Value"], node_6.inputs["X"])
                material.node_tree.links.new(node_5.outputs["Y"], node_6.inputs["Y"])

        b_tex = bpy.data.images.get(image)
        if b_tex is None:
            b_tex = make_texture(tex, file_path)

        image_node = material.node_tree.nodes["Image Texture"]
        image_node.image = b_tex

    else:
        material = bpy.data.materials.new(offset)
        material.use_nodes = True
        material.node_tree.nodes["Principled BSDF"].inputs[5].default_value = 0
        colors = mat['unk']
        #print(colors)
        material.node_tree.nodes["Principled BSDF"].inputs[0].default_value = [colors["r"]/255, colors["g"]/255, colors["b"]/255, colors["t"]/255]
        node_1 = material.node_tree.nodes.new("ShaderNodeVertexColor")
        material.node_tree.links.new(node_1.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Base Color"])
        
    return material

def make_visuals(mesh_node, model, parent, file_path):
    start = 0
    verts = [[vert['x'], vert['y'], vert['z']] for vert in mesh_node['visuals']['vert_buffer']]
    edges = []
    faces = []

    for index in mesh_node['visuals']['index_buffer']:
        if index['type'] == 1:
            start = index['start']
        elif index['type'] == 5:
            faces.append([start + index['x'], start + index['y'], start + index['z']])
        elif index['type'] == 6:
            faces.append([start + index['x1'], start + index['y1'], start + index['z1']])
            faces.append([start + index['x2'], start + index['y2'], start + index['z2']])
    
    mesh_name = mesh_node['id'] + "_" + "visuals"
    mesh = bpy.data.meshes.new(mesh_name)
    obj = bpy.data.objects.new(mesh_name, mesh)
    
    obj['type'] = 'VIS'    
    obj['id'] = mesh_node['id']
    obj.scale = [scale, scale, scale]

    model['collection'].objects.link(obj)
    mesh.from_pydata(verts, edges, faces)
    obj.parent = parent
    
    mat = model['mats'][mesh_node['visuals']['material']]
    tex = None if mat['texture'] == 0 else model['textures'][mat['texture']]
    mesh.materials.append(
        make_material(mat, tex, file_path)
    )
    
    #set vector colors / uv coords
    uv_layer = mesh.uv_layers.new(name = 'uv')
    color_layer = mesh.vertex_colors.new(name = 'colors') #color layer has to come after uv_layer
    for poly in mesh.polygons:
        for p in range(len(poly.vertices)):
            v = mesh_node['visuals']['vert_buffer'][poly.vertices[p]]
            c = v['v_color']
            color = [c[0]/255, c[1]/255, c[2]/255, c[3]/255]
            uv_layer.data[poly.loop_indices[p]].uv = [v['uv_x']/4096, v['uv_y']/4096]
            color_layer.data[poly.loop_indices[p]].color = color
            if(mesh_name == '1044_visuals'):
                print(p, poly.vertices[p], poly.loop_indices[p], c, [v['uv_x'], v['uv_y']])


    
    return

def make_collision(mesh_node, model, parent):
    if not 'collision' in mesh_node:
        return
    
    if (mesh_node['collision']['vert_buffer'] == 0 or len(mesh_node['collision']['vert_buffer']) < 3):
        return
            
    verts = mesh_node['collision']['vert_buffer']
    edges = []
    faces = []
    start = 0
    vert_strips = [mesh_node['collision']['strip_size'] for s in range(mesh_node['collision']['strip_count'])]
    
    if(mesh_node['collision']['vert_strips'] != 0): #if there is a provided strip buffer
        vert_strips = mesh_node['collision']['vert_strips']
        for strip in vert_strips:
            for s in range(strip -2):
                if (s % 2) == 0:
                    faces.append( [start+s, start+s+1, start+s+2])
                else:
                    faces.append( [start+s+1, start+s, start+s+2])
            start += strip
    else: #if there is no strip buffer
        for strip in vert_strips:
            for s in range(strip -2):
                if (strip == 3):
                    faces.append( [start+s, start+s+1, start+s+2])
                else:
                    if (s % 2) == 0:
                        faces.append( [start+s, start+s+1, start+s+3])
                    else:
                        faces.append( [start+s, start+s+1, start+s+2])
            start += strip
            
    mesh_name = mesh_node['id'] + "_" + "collision"
    mesh = bpy.data.meshes.new(mesh_name)
    obj = bpy.data.objects.new(mesh_name, mesh)
    
    obj['type'] = 'COL'   
    obj['id'] = mesh_node['id'] 
    obj.scale = [scale, scale, scale]

    model['collection'].objects.link(obj)
    mesh.from_pydata(verts, edges, faces)
    obj.parent = parent

    if(mesh_node['collision']['data'] == 0):
        return 
    
    for key in mesh_node['collision']['data']:
        obj[key] = mesh_node['collision']['data'][key]
    
    obj.id_properties_ui('fog_color').update(subtype='COLOR')
    obj.id_properties_ui('lights_ambient_color').update(subtype='COLOR')
    obj.id_properties_ui('lights_color').update(subtype='COLOR')

def make_mesh_group(mesh_node, model, parent, file_path):
    if 'collision' in mesh_node and mesh_node['collision']['vert_buffer'] != 0 and len(mesh_node['collision']['vert_buffer']) > 2:
        make_collision(mesh_node, model, parent)
        
    if 'visuals' in mesh_node and mesh_node['visuals']['index_buffer'] != 0 and mesh_node['visuals']['vert_buffer'] != 0 :
        make_visuals(mesh_node, model, parent, file_path)

def read_mesh_group(buffer, cursor, model, parent, file_path):
    mesh = {
        'id': str(cursor),
        'collision': {
            'data': read_collision_data(buffer=buffer, cursor=readUInt32BE(buffer,cursor + 4)),
            'vert_strips': read_collision_vert_strips(buffer=buffer, cursor=readUInt32BE(buffer,cursor + 36), count=readInt16BE(buffer, cursor + 32), default=readInt16BE(buffer, cursor + 34)),
            'vert_buffer': read_collision_vert_buffer(buffer=buffer, cursor=readUInt32BE(buffer,cursor + 44), count=readInt16BE(buffer, cursor + 56)),
            'strip_count': readInt16BE(buffer, cursor + 32),
            'strip_size': readInt16BE(buffer, cursor + 34)
        },
        'visuals': {
            'material': read_mat(buffer=buffer, cursor=readUInt32BE(buffer,cursor), model=model),
            'index_buffer': read_visual_index_buffer(buffer=buffer, cursor=readUInt32BE(buffer,cursor + 48), vert_buffer_start=readUInt32BE(buffer,cursor + 52)),
            'vert_buffer': read_visual_vert_buffer(buffer=buffer, cursor=readUInt32BE(buffer,cursor + 52), count=readInt16BE(buffer, cursor + 58)),
            'group_parent': readUInt32BE(buffer,cursor + 40),
            'group_count': readInt16BE(buffer, cursor + 62)
        }
    }
    
    make_mesh_group(mesh, model, parent, file_path)

    return mesh

def make_node(node, model, parent):
    node_name = str(node['id'])
    if (node['head'][0] in [53349, 53350]):
        new_empty = bpy.data.objects.new(node_name, None)
        model['collection'].objects.link(new_empty)
        
        #new_empty.empty_display_size = 2
        

        if node['head'][3] &  1048576 != 0:
            new_empty.empty_display_type = 'ARROWS'
            new_empty.empty_display_size = 0.5
            
        elif node['head'][3] & 524288 != 0:
            new_empty.empty_display_type = 'CIRCLE'
            new_empty.empty_display_size = 0.5
        else:
            new_empty.empty_display_type = 'PLAIN_AXES'
        if node['head'][0] ==53349:
            #new_empty.location = [node['xyz']['x']*scale, node['xyz']['y']*scale, node['xyz']['z']*scale]
            if node['head'][3] &  1048576 != 0 and False:
                
                global offsetx
                global offsety
                global offsetz
                offsetx = node['xyz']['x1']
                offsety = node['xyz']['y1']
                offsetz = node['xyz']['z1']
                imparent = None
                if parent != None and False:
                    imparent = parent
                    while imparent != None:
                        #print(imparent, imparent['grouptag0'], imparent['grouptag3'])
                        if int(imparent['grouptag0']) == 53349 and int(imparent['grouptag3']) & 1048576 != 0:
                            #print('found one')
                            offsetx += imparent['x']
                            offsety += imparent['y']
                            offsetz += imparent['z']
                        imparent = imparent.parent
                #print(offsetx, offsety, offsetz)
                new_empty.matrix_world = [
                [node['xyz']['ax'], node['xyz']['ay'], node['xyz']['az'], 0],
                [node['xyz']['bx'], node['xyz']['by'], node['xyz']['bz'], 0],
                [node['xyz']['cx'], node['xyz']['cy'], node['xyz']['cz'], 0],
                [node['xyz']['x']*scale + offsetx*scale,  node['xyz']['y']*scale + offsety*scale, node['xyz']['z']*scale + offsetz*scale, 1],
                ]
            else:
                new_empty.matrix_world = [
                [node['xyz']['ax'], node['xyz']['ay'], node['xyz']['az'], 0],
                [node['xyz']['bx'], node['xyz']['by'], node['xyz']['bz'], 0],
                [node['xyz']['cx'], node['xyz']['cy'], node['xyz']['cz'], 0],
                [node['xyz']['x']*scale, node['xyz']['y']*scale, node['xyz']['z']*scale, 1],
                ]
        elif node['head'][0] == 53350:
            new_empty['53350_unk1'] = node['53350']['unk1']
            new_empty['53350_unk2'] = node['53350']['unk2']
            new_empty['53350_unk3'] = node['53350']['unk3']
            new_empty['53350_unk4'] = node['53350']['unk4']
            
    else:
        new_empty = bpy.data.objects.new(node_name, None)
        #new_empty.empty_display_type = 'PLAIN_AXES'
        new_empty.empty_display_size = 0
        model['collection'].objects.link(new_empty)
        
    #set group tags
    new_empty['head0'] = str(node['head'][0])
    new_empty['head1'] = str(node['head'][1])
    new_empty['head2'] = str(node['head'][2])
    new_empty['head3'] = str(node['head'][3])
    
    if (node['head'][0] in [53349, 53350]):
        new_empty['grouptag3'] = bin(int(node['head'][3]))
        if 'xyz' in node:
            new_empty['x'] = node['xyz']['x']
            new_empty['y'] = node['xyz']['y']
            new_empty['z'] = node['xyz']['z']
            if 'x1' in node['xyz']:
                new_empty['x1'] = node['xyz']['x1']
                new_empty['y1'] = node['xyz']['y1']
                new_empty['z1'] = node['xyz']['z1']
        
    #assign parent
    if parent != None:
        #savedState = new_empty.matrix_world
        if node['head'][0] not in [53349, 53350] or node['head'][3] & 1048576 == 0 and False:
            new_empty.parent = parent
            #if(node['head'][3] & 1048576) == 0:
            #loc = new_empty.constraints.new(type='COPY_LOCATION')
            #loc.target = parent
            #elif(node['head'][3] & 524288) == 0:
                #rot = new_empty.constraints.new(type='COPY_ROTATION')
                #rot.target = parent
            #else:
                #new_empty.parent = parent
                
        else:
            new_empty.parent = parent
        #new_empty.matrix_world = savedState
        
    return new_empty

def read_node(buffer, cursor, model, parent, file_path):
    node = {
        'id': cursor,
        'head': [
            readUInt32BE(buffer, cursor),
            readUInt32BE(buffer, cursor + 4),
            readUInt32BE(buffer, cursor + 8),
            readUInt32BE(buffer, cursor + 12),
            readUInt32BE(buffer, cursor + 16)
        ],
        'children': []
    }

    if model.get('AltN') and cursor in model['AltN']:
        node['AltN'] = [i for i, h in enumerate(model['AltN']) if h == cursor]
    
    if cursor in model['header']:
        node['header'] = [i for i, h in enumerate(model['header']) if h == cursor]

    if not model['node_map'].get(cursor):
        model['node_map'][cursor] = True

    mesh_group = False
    switch_value = readInt32BE(buffer,cursor)
    
    if switch_value == 12388:
        mesh_group = True
        node.update({
            'min_x': readFloatBE(buffer, cursor + 28),
            'min_y': readFloatBE(buffer, cursor + 32),
            'min_z': readFloatBE(buffer, cursor + 36),
            'max_x': readFloatBE(buffer, cursor + 40),
            'max_y': readFloatBE(buffer, cursor + 44),
            'max_z': readFloatBE(buffer, cursor + 48)
        })
    elif switch_value == 53349:
        node['xyz'] = {
            'ax': readFloatBE(buffer, cursor + 28),
            'ay': readFloatBE(buffer, cursor + 32),
            'az': readFloatBE(buffer, cursor + 36),
            'bx': readFloatBE(buffer, cursor + 40),
            'by': readFloatBE(buffer, cursor + 44),
            'bz': readFloatBE(buffer, cursor + 48),
            'cx': readFloatBE(buffer, cursor + 52),
            'cy': readFloatBE(buffer, cursor + 56),
            'cz': readFloatBE(buffer, cursor + 60),
            'x': readFloatBE(buffer, cursor + 64),
            'y': readFloatBE(buffer, cursor + 68),
            'z': readFloatBE(buffer, cursor + 72),
            'x1': readFloatBE(buffer, cursor + 76),
            'y1': readFloatBE(buffer, cursor + 80),
            'z1': readFloatBE(buffer, cursor + 84)
        }
    elif switch_value == 53348:
        node['xyz'] = {
            'ax': readFloatBE(buffer, cursor + 28),
            'ay': readFloatBE(buffer, cursor + 32),
            'az': readFloatBE(buffer, cursor + 36),
            'bx': readFloatBE(buffer, cursor + 40),
            'by': readFloatBE(buffer, cursor + 44),
            'bz': readFloatBE(buffer, cursor + 48),
            'cx': readFloatBE(buffer, cursor + 52),
            'cy': readFloatBE(buffer, cursor + 56),
            'cz': readFloatBE(buffer, cursor + 60),
            'x': readFloatBE(buffer, cursor + 64),
            'y': readFloatBE(buffer, cursor + 68),
            'z': readFloatBE(buffer, cursor + 72),
        }
    elif switch_value == 53350:
        node['53350'] = {
            'unk1': readInt32BE(buffer,cursor + 28),
            'unk2': readInt32BE(buffer,cursor + 32),
            'unk3': readInt32BE(buffer,cursor + 36),
            'unk4': readFloatBE(buffer, cursor + 40)
        }
    elif switch_value == 20582:
        node['xyz'] = {
            'f1': readFloatBE(buffer, cursor + 28),
            'f2': readFloatBE(buffer, cursor + 32),
            'f3': readFloatBE(buffer, cursor + 36),
            'f4': readFloatBE(buffer, cursor + 40),
            'f5': readFloatBE(buffer, cursor + 44),
            'f6': readFloatBE(buffer, cursor + 48),
            'f7': readFloatBE(buffer, cursor + 52),
            'f8': readFloatBE(buffer, cursor + 56),
            'f9': readFloatBE(buffer, cursor + 60),
            'f10': readFloatBE(buffer, cursor + 64),
            'f11': readFloatBE(buffer, cursor + 68)
        }

    child_count = readInt32BE(buffer,cursor + 20)
    child_start = readUInt32BE(buffer,cursor + 24)
    
    
    
    node_empty = make_node(node, model, parent)
        
        
    
    for i in range(child_count):
        child_address = readUInt32BE(buffer,child_start + i * 4)
        if not child_address:
            if model.get('AltN') and (child_start + i * 4) in model['AltN']:
                node['children'].append({'id': child_start + i * 4, 'AltN': True})
            else:
                node['children'].append({'id': None})  # remove later
            continue

        if model['node_map'].get(child_address):
            node['children'].append({'id': child_address})
            continue

        if mesh_group:
            node['children'].append(read_mesh_group(buffer=buffer, cursor=child_address, model=model, parent = node_empty, file_path = file_path))
        else:
            node['children'].append(read_node(buffer=buffer, cursor=child_address, model=model, parent = node_empty, file_path = file_path))

    return node

def readUInt8(buffer, cursor):
    return int.from_bytes(buffer[cursor: cursor+1], byteorder='big')

def readInt8(buffer, cursor):
    return int.from_bytes(buffer[cursor: cursor+1], byteorder='big', signed = True)

def readUInt16BE(buffer, cursor):
    return int.from_bytes(buffer[cursor:cursor + 2], byteorder='big')

def readInt16BE(buffer, cursor):
    return int.from_bytes(buffer[cursor:cursor + 2], byteorder='big', signed = True)

def readUInt32BE(buffer, cursor):
    return int.from_bytes(buffer[cursor:cursor + 4], byteorder='big')

def readInt32BE(buffer, cursor):
    return int.from_bytes(buffer[cursor:cursor + 4], byteorder='big', signed = True)

def readString(buffer, cursor):
    return struct.unpack('4s', buffer[cursor: cursor +4])[0].decode('utf-8', errors='replace')

def readFloatBE(buffer, cursor):
    return struct.unpack('>f', buffer[cursor: cursor +4])[0]

def readVec3(buffer, cursor):
    return struct.unpack('>fff', buffer[cursor: cursor +12])

def read_header(buffer, model, index, collection):
    model['ext'] = readString(buffer, 0)
    model['id'] = index
    model['header'] = []
    cursor = 4
    header = readInt32BE(buffer, cursor)

    while header != -1:
        model['header'].append(header)
        cursor += 4
        header = readInt32BE(buffer, cursor)

    collection['header'] = model['header']
    cursor += 4
    header_string = readString(buffer, cursor)

    while header_string != 'HEnd':
        if header_string == 'Data':
            cursor = read_Data(buffer, cursor + 4, model)
            header_string = readString(buffer, cursor)
        elif header_string == 'Anim':
            cursor = read_Anim(buffer, cursor + 4, model)
            header_string = readString(buffer, cursor)
        elif header_string == 'AltN':
            cursor = read_AltN(buffer, cursor + 4, model)
            header_string = readString(buffer, cursor)

    return cursor + 4

def read_model(buffer, index, file_path):
    print('reading model', index)
    model = {
        'mats': {},        # unique mats
        'textures': {},    # unique textures
        'node_map': {},    # unique node locations
        'nodes': [],
    }
    
    main_collection = bpy.data.collections.new(f"{index}_{readString(buffer, 0)}")
    main_collection['ext'] = readString(buffer, 0)
    main_collection['ind'] = index
    main_collection['type'] = 'MODEL'
    bpy.context.scene.collection.children.link(main_collection)
    model['collection'] = main_collection
    lightstreaks_col = bpy.data.collections.new(f"{index}_lightstreaks")
    lightstreaks_col['type'] = 'LSTR'
    main_collection.children.link(lightstreaks_col)
    
    cursor = read_header(buffer=buffer, model=model, index=index, collection=main_collection)    

    if model.get('AltN') and len(model['AltN']) and model.get('ext') != 'Podd':
        AltN = list(set(model['AltN']))
        for i in range(len(AltN)):
            model['nodes'].append(read_node(buffer=buffer, cursor=AltN[i], model=model, parent = None, file_path=file_path))
    else:
        model['nodes'] = [read_node(buffer=buffer, cursor=cursor, model=model, parent = None, file_path=file_path)]

    return model

def read_block(file, arr, selector):
    asset_count = int.from_bytes(file[0:4], byteorder='big')
    cursor = 4
    chunks = len(arr)
    
    for i in (selector if len(selector) else range(asset_count)):
        for j in range(chunks):
            asset_start = readUInt32BE(file, 4 + i*4*chunks + j * 4)
            cursor += 4

            asset_end = readUInt32BE(file, 4 + i*4*chunks + j * 4 + 4)
            if not asset_end:
                asset_end = readUInt32BE(file, 4 + i*4*chunks + j * 4 + 8)

            asset = file[asset_start:asset_end] if asset_start else None

            arr[j].append(asset)

    return arr


def read_palette(buffer, format):
    format_map = {
        512: 16,
        513: 256
    }

    if not buffer:
        return []

    palette = []
    for cursor in range(0, format_map.get(format, 0) * 2, 2):
        color = readInt16BE(buffer, cursor)
        a = ((color >> 0) & 0x1) * 0xFF
        b = round((((color >> 1) & 0x1F) / 0x1F) * 255)
        g = round((((color >> 6) & 0x1F) / 0x1F) * 255)
        r = round((((color >> 11) & 0x1F) / 0x1F) * 255)
        if (r + g + b) > 0 and a == 0:
            a = 255
        palette.append([r, g, b, a])

    return palette

def read_pixels(buffer, format, pixel_count):
    pixels = []
    cursor = 0
    
    if format == 3:
        for i in range(pixel_count):
            r, g, b, a = struct.unpack('BBBB', buffer[cursor:cursor + 4])
            pixels.append([r, g, b, a])
            cursor += 4

    elif format == 512:
        for i in range(round(pixel_count/2)):
            p = buffer[cursor]
            pixel_0 = (p >> 4) & 0xF
            pixel_1 = p & 0xF
            pixels.extend([pixel_0, pixel_1])
            cursor += 1

    elif format == 513:
        for i in range(pixel_count):
            pixel = buffer[cursor]
            pixels.append(pixel)
            cursor += 1

    elif format == 1024:
        for i in range(round(pixel_count/2)):
            p = buffer[cursor]
            pixel_0 = ((p >> 4) & 0xF) * 0x11
            pixel_1 = (p & 0xF) * 0x11
            pixels.extend([pixel_0, pixel_1])
            cursor += 1

    elif format == 1025:
        for i in range(pixel_count):
            pixel = buffer[cursor]
            pixels.append(pixel)
            cursor += 1

    return pixels


def draw_texture(pixels, palette, width, height, format, path, index):
    
    if not pixels:
        print(f"Texture {index} does not have any pixels")
        return

    if None in [format, width, height]:
        print(f"Texture {index} is missing width/height/format data")
        return

    new_image = bpy.data.images.new(name=str(index), width=width, height=height)
    image_pixels = []    

    for i in range(height):
        for j in range(width):
            ind = i * width + j
            p = None
            color = None

            if format in [512, 513]:
                p = palette[pixels[ind]]
                color = [p[0] if p else 0, p[1] if p else 0, p[2] if p else 0, p[3] if p else 0]

            elif format in [1024, 1025]:
                p = pixels[ind]
                color = [p if p else 0, p if p else 0, p if p else 0, 255]

            elif format == 3:
                p = pixels[ind]
                color = [p[0] if p else 0, p[1] if p else 0, p[2] if p else 0, p[3] if p else 0]

            x = 0

            image_pixels.extend(color)
           
    new_image.pixels = [p/255 for p in image_pixels]
    new_image['format'] = format

    return new_image

def make_texture(texture, folder_path):
    file_path = folder_path + 'out_textureblock.bin'
    selector = [texture['tex_index']]

    with open(file_path, 'rb') as file:
        file = file.read()
        read_block_result = read_block(file, [[], []], selector)

    pixel_buffers, palette_buffers = read_block_result
    tex = None
    for i, buffer in enumerate(pixel_buffers):
        pixels = read_pixels(buffer, texture['format'], texture['width']*texture['height'])
        palette = read_palette(palette_buffers[i], texture['format'])
        tex = draw_texture(pixels, palette, texture['width'], texture['height'], texture['format'], str(selector[i]) + '.png',  str(selector[i]))
        
    return tex

def import_model(file_path, selector=None):
    with open(file_path + 'out_modelblock.bin', 'rb') as file:
        file = file.read()
        read_block_result = read_block(file, [[], []], selector)

    offset_buffers, model_buffers = read_block_result
    if selector is None:
        selector = range(324)
        
    for i, id in enumerate(selector):
        model = Model(id).read(model_buffers[i], 0)
        model.make()
        print("here's the model", model)

    print(f'Successfully unpacked {len(model_buffers)} models')