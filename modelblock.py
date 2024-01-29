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

import struct
import bpy
import math
from .readwrite import *
from .textureblock import Texture


class Data:
    def get(self):
        pass
    def set(self):
        pass

class DataStruct:
    def __init__(self, format_string):
        self.format_string = format_string
        self.size = struct.calcsize(self.format_string)
    def read(self, buffer, cursor):
        pass
    def make(self):
        pass
    def unmake(self):
        pass
    def write(self, buffer, cursor, hl, model):
        pass
    
    
class FloatVector(Data):
    def __init__(self, data = None):
        if data is not None:
            self.set([0,0,0])
        else:
            self.data = [0,0,0]

    def __str__(self):
        return f"({self.data[0]}, {self.data[1]}, {self.data[2]})"
    
    def set(self, data=None):
        if(len(data) != 3):
            raise ValueError("Vec3 must contain only 3 values")
        for d in data:
            if d > 1.0 or d < -1.0:
                raise ValueError(f"Vec3 {d} in {data} is not normalized")
        self.data = data
        return self
    
    def get(self):
        return self.data
    
class FloatPosition(Data):
    def __init__(self, data = None):
        if data is not None:
            self.set([0,0,0])
        else:
            self.data = [0,0,0]

    def __str__(self):
        return f"({self.data[0]}, {self.data[1]}, {self.data[2]})"
    
    def set(self, data=None):
        if(len(data) != 3):
            raise ValueError(f"Vec3 must contain only 3 values, received {len(data)}")
                
        self.data = data
        return self
    
    def get(self):
        return self.data

class IntPosition(Data):
    def __init__(self, data = None):
        if data is not None:
            self.set([0,0,0])
        else:
            self.data = [0,0,0]

    def __str__(self):
        return f"({self.data[0]}, {self.data[1]}, {self.data[2]})"
    
    def set(self, data=None):
        if(len(data) != 3):
            raise ValueError(f"Vec3 must contain only 3 values, received {len(data)}")
                
        self.data = [round(d) for d in data]
        return self
    
    def get(self):
        return self.data
    
class FloatMatrix(Data):
    def __init__(self, data = None):
        if data is None:
            self.data = [FloatVector(), FloatVector(), FloatVector(), FloatPosition()]
        else:
            self.set([FloatVector(data[:3]), FloatVector(data[3:6]), FloatVector(data[6:9]), FloatPosition(data[9:])])

    def set(self, data=None):
        if(len(data) != 12):
            raise ValueError("Matrix must have 12 values")
        self.data = [FloatVector(data[:3]), FloatVector(data[3:6]), FloatVector(data[6:]), FloatPosition(data[9:])]

    def get(self):
        return [vec.get() for vec in self.data]
    
    def make(self):
        matrix = []
        for i in range(3):
            matrix.append(tuple([*self.data[i].get(), 0.0]))
        matrix.append(tuple([*self.data[3].get(), 1.0]))
        return matrix
    
    def unmake(self, matrix):
        mat = []
        for m in matrix:
            mat.extend(m[:3])
        self.set(mat)    

class Color(Data):
    def __init__(self, data = None):
        if data is None:
            self.data = [0, 0, 0, 255]
        else:
            self.set(data)
        
    def __str__(self):
        return f"r: {self.data[0]} g: {self.data[1]} b: {self.data[2]}"
    
    def set(self, data=None):
        if(len(data) > 4 or len(data) < 3):
            raise ValueError("Color must have 3 or 4 values")
        for c in self.data:
            if c > 255:
                raise ValueError(f"Color values must be < 255, received {c}")
        if len(data) == 3:
            data.append(255)
        self.data = data
        return self
    
    def make(self):
        return [d/255 for d in self.data]
    
    def unmake(self, data):
        self.set([round(d * 255) for d in data])
    
    def get(self):
        return self.data
    
class Lights(Data):
    def __init__(self):
        self.flag = 0
        self.ambient = Color()
        self.color = Color()
        self.unk1 = 0
        self.unk2 = 0
        self.pos = FloatPosition()
        self.rot = FloatVector()
    
    def get(self):
        return [self.flag, *self.ambient.get(), *self.color.get(),self.unk1, self.unk2, *self.pos.get(), *self.rot.get()]
        
    def set(self, flag, ambient_r, ambient_g, ambient_b, color_r, color_g, color_b,unk1, unk2, x, y, z, a, b, c):
        self.flag = flag
        self.ambient = Color().set([ambient_r, ambient_g, ambient_b])
        self.color = Color().set([color_r, color_g, color_b])
        self.unk1 = unk1
        self.unk2 = unk2
        self.pos = FloatPosition([x, y, z])
        self.rot = FloatVector([a, b, c])

class Fog(Data):
    def __init__(self):
        self.flag = 0
        self.color = Color()
        self.start = 0
        self.end = 0
    
    def get(self):
        return [self.flag, *self.color.get(), self.start, self.end]
        
    def set(self, flag, r, g, b, start, end):
        self.flag = flag
        self.color = Color().set([r, g, b])
        self.start = start
        self.end = end

class CollisionTags(DataStruct):
    def __init__(self, model):
        super().__init__('>H4B3H8B6f2I2i')
        self.model = model
        self.unk = 0
        self.fog = Fog()
        self.lights = Lights()
        self.flags = 0
        self.unk2 = 0
        self.unload = 0
        self.load = 0

    def read(self, buffer, cursor):
        # Unpack binary data into object attributes
        data = struct.unpack_from(self.format_string, buffer, cursor)
        self.unk = data[0]
        self.fog = Fog().set(*data[1:7])
        self.lights = Lights().set(*data[7:22])
        self.flags, self.unk2, self.unload, self.load = data[22:]
        return self
        
    def make(self, obj):
        # for key in mesh_node['collision']['data']:
        #     obj[key] = mesh_node['collision']['data'][key]
        
        # obj.id_properties_ui('fog_color').update(subtype='COLOR')
        # obj.id_properties_ui('lights_ambient_color').update(subtype='COLOR')
        # obj.id_properties_ui('lights_color').update(subtype='COLOR')
        pass
    
    def unmake(self, mesh):
        if not 'unk' in mesh:
            return None
        self.unk = mesh['unk']
        self.flags = mesh['flags']
        self.unk2 = mesh['unk3']
        self.unload = mesh['unload']
        self.load = mesh['load']
        # 'fog': {
        #     'flag': mesh['fog_flag'],
        #     'color': [round(c*255) for c in mesh['fog_color']],
        #     'start': mesh['fog_start'],
        #     'end': mesh['fog_stop']
        # }
        # 'lights': {
        #     'flag': mesh['lights_flag'],
        #     'ambient_color': [round(c*255) for c in mesh['lights_ambient_color']],
        #     'color': [round(c*255) for c in mesh['lights_color']],
        #     'unk1': mesh['unk1'],
        #     'unk2': mesh['unk2'],
        #     'pos': [p for p in mesh['lights_pos']],
        #     'rot': [r for r in mesh['lights_rot']]
        # }
        return self
    
    def write(self, buffer, cursor):
        # Pack object attributes into binary data
        return struct.pack_into(self.format_string, buffer, cursor, *[self.unk, *self.fog.get(), *self.lights.get(), self.flags, self.unk2, self.unload, self.load])
    

class CollisionVertBuffer(DataStruct):
    def __init__(self, model, length):
        super().__init__(f'>{length*3}h')
        self.model = model
        self.data = None

    def __str__(self):
        return str(self.data)

    def read(self, buffer, cursor):
        self.data = struct.unpack_from(self.format_string, buffer, cursor)
        
        return self

    def make(self):
        vert_buffer = []
        for i in range(len(self.data)//3):
            vert_buffer.append(self.data[i*3:(i+1)*3])
        return vert_buffer
    
    def unmake(self, mesh):
        self.data = [round(co) for vert in mesh.data.vertices for co in vert.co]
        return self
    
    def write(self, buffer, cursor):
        return struct.pack_into(self.format_string, buffer, cursor, *self.data)
    
class CollisionVertStrips(DataStruct):
    def __init__(self, model, count):
        super().__init__(f'>{count}I')
        self.model = model
        self.data = None

    def read(self, buffer, cursor):
        self.data = struct.unpack_from(self.format_string, buffer, cursor)
        return self

    def make(self):
        return self.data
    
    def unmake(self, mesh):
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
                
        self.data = strips
        return self
    
    def write(self, buffer, cursor):
        return struct.pack_into(self.format_string, buffer, cursor, *self.data)
    

class Collision(DataStruct):
    def __init__(self, model):
        super().__init__('>4xI24xHHI4xI8xH')
        self.model = model
        self.tags = None
        self.vert_strips = None
        self.vert_buffer = None
        self.strip_count = None
        self.strip_size = None
        self.id = None

    def read(self, buffer, cursor):
        self.id = cursor
        tags_addr, strip_count, strip_size, vert_strips_addr, vert_buffer_addr, vert_count = struct.unpack_from(self.format_string, buffer, cursor)
        if tags_addr:
            self.tags = CollisionTags(self.model).read(buffer, tags_addr)
        if vert_strips_addr:
            self.vert_strips = CollisionVertStrips(self.model, strip_count).read(buffer, vert_strips_addr)
        if vert_buffer_addr:
            self.vert_buffer = CollisionVertBuffer(self.model, vert_count).read(buffer, vert_buffer_addr)
        self.strip_size = strip_size
        self.strip_count = strip_count

    def make(self, parent):
        if (self.vert_buffer is None or len(self.vert_buffer.data) < 3):
            return
        
        verts = self.vert_buffer.make()
        edges = []
        faces = []
        start = 0
        vert_strips = [self.strip_size for s in range(self.strip_count)]
        
        if(self.vert_strips is not None): 
            vert_strips = self.vert_strips.make()
            for strip in vert_strips:
                for s in range(strip -2):
                    if (s % 2) == 0:
                        faces.append( [start+s, start+s+1, start+s+2])
                    else:
                        faces.append( [start+s+1, start+s, start+s+2])
                start += strip
        else: 
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
                
        mesh_name = str(self.id) + "_" + "collision"
        mesh = bpy.data.meshes.new(mesh_name)
        obj = bpy.data.objects.new(mesh_name, mesh)
        
        obj['type'] = 'COL'   
        obj['id'] = self.id
        obj.scale = [self.model.scale, self.model.scale, self.model.scale]

        self.model.collection.objects.link(obj)
        mesh.from_pydata(verts, edges, faces)
        obj.parent = parent

        if(self.tags is not None): 
            self.tags.make(obj)

    def unmake(self, mesh):
        self.vert_buffer = CollisionVertBuffer().unmake(mesh)
        self.vert_strips = CollisionVertStrips().unmake(mesh)
        self.tags = CollisionTags().unmake(mesh)

        if len(self.vert_strips.data):
            self.strip_count = len(self.vert_strips.data)
            if all(strip == self.vert_strips.data[0] for strip in self.vert_strips.data):
                self.strip_size = self.vert_strips.data[0]

    def write(self, buffer, cursor):
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
        self.model.highlight(hl)
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
    
class VisualsVertChunk(DataStruct):
    def __init__(self, model):
        self.model = model
        super().__init__('>hhh2xhhBBBB')
        self.co = []
        self.uv = []
        self.color = []
    def read(self, buffer, cursor):
        x, y, z, uv_x, uv_y, r, g, b, a = struct.unpack_from(self.format_string, buffer, cursor)
        self.co = [x, y, z]
        self.uv = [uv_x, uv_y]
        self.color = [r, g, b, a]
        return cursor + self.size
    def make(self):
        pass
    def unmake(self, co, uv, color):
        self.co = co
        self.uv = uv
        self.color = color
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, *self.pos, *self.uv, *self.color)
        return cursor + self.size
    
class VisualsVertBuffer():
    def __init__(self, model, length = 0):
        self.model = model
        self.data = []
        self.length = length
        
    def read(self, buffer, cursor):
        for i in range(self.length):
            vert = VisualsVertChunk(self.model)
            cursor = vert.read(buffer, cursor)
            self.data.append(vert)
    def make(self):
        pass
    def unmake(self, mesh):
        uv_data = None
        color_data = None
        if mesh.data.uv_layers.active:
            uv_data = mesh.data.uv_layers.active.data
        if mesh.data.vertex_colors.active:
            color_data = mesh.data.vertex_colors.active.data
        for poly in mesh.data.polygons:
            for p in range(len(poly.vertices)):
                uv = [0, 0]
                color = [0, 0, 0]
                
                if uv_data:
                    uv = uv_data[poly.loop_indices[p]].uv
                if color_data:
                    color = color_data[poly.loop_indices[p]].color
                v = mesh.data.vertices[poly.vertices[p]]
                
                self.data.append(VisualsVertChunk(self.model).unmake(v.co, uv, [c for c in color]))
                
        self.length = len(self.data)
    def write(self, buffer, cursor):
        for vert in self.data:
            cursor = vert.write(buffer, cursor)
        return cursor
    
class VisualsIndexChunk1(DataStruct):
    def __init__(self, model, type):
        self.model = model
        self.type = type
        super().__init__('>BBBBI')
        self.unk1 = None
        self.unk2 = None
        self.size = None
        self.start = None
        
    def read(self, buffer, cursor, vert_buffer_addr):
        self.type, self.unk1, self.unk2, self.size, start = struct.unpack_from(self.format_string, buffer, cursor)
        self.start = round((start - vert_buffer_addr)/16)
        return cursor + self.size
    
        
class VisualsIndexChunk3(DataStruct):
    def __init__(self, model, type):
        self.model = model
        self.type = type
        super().__init__('>B6xB')
        self.unk = None
        
    def read(self, buffer, cursor, vert_buffer_addr):
        self.type, self.unk = struct.unpack_from(self.format_string, buffer, cursor)
        
        return cursor + self.size
        
class VisualsIndexChunk5(DataStruct):
    def __init__(self, model, type):
        self.model = model
        self.type = type
        super().__init__('>BBBB4x')
        self.f1 = None
        self.f2 = None
        self.f3 = None
        
    def read(self, buffer, cursor, vert_buffer_addr):
        self.type, f1, f2, f3 = struct.unpack_from(self.format_string, buffer, cursor)
        self.f1 = round(f1/2)
        self.f2 = round(f2/2)
        self.f3 = round(f3/2)
        return cursor + self.size
        
class VisualsIndexChunk6(DataStruct):
    def __init__(self, model, type):
        self.model = model
        self.type = type
        super().__init__('>BBBBxBBB')
        self.f1 = None
        self.f2 = None
        self.f3 = None
        self.f4 = None
        self.f5 = None
        self.f6 = None
        
    def read(self, buffer, cursor, vert_buffer_addr):
        self.type, f1, f2, f3, f4, f5, f6 = struct.unpack_from(self.format_string, buffer, cursor)
        self.f1 = round(f1/2)
        self.f2 = round(f2/2)
        self.f3 = round(f3/2)
        self.f4 = round(f4/2)
        self.f5 = round(f5/2)
        self.f6 = round(f6/2)
        return cursor + self.size
            
class VisualsIndexBuffer():
    def __init__(self, model):
        self.model = model
        self.data = []
        
    def read(self, buffer, cursor, vert_buffer_addr):
        chunk_type = readUInt8(buffer, cursor)
        CHUNK_MAPPING = {
            1: VisualsIndexChunk1,
            3: VisualsIndexChunk3,
            5: VisualsIndexChunk5,
            6: VisualsIndexChunk6,
        }
        while(chunk_type != 223):
            chunk_class = CHUNK_MAPPING.get(chunk_type)
            if chunk_class is None:
                raise ValueError(f"Invalid index chunk type {chunk_type}")
            chunk = chunk_class(self.model, chunk_class)
            chunk.read(buffer, cursor, vert_buffer_addr)
            self.data.append(chunk)
            cursor += 8
            chunk_type = readUInt8(buffer, cursor)
            
    def make(self):
        faces = []
        start = 0
        for chunk in self.data:
            if chunk.type == 1:
                start = chunk.start
            elif chunk.type == 5:
                faces.append([start + chunk.f1, start + chunk.f2, start + chunk.f3])
            elif chunk.type == 6:
                faces.append([start + chunk.f1, start + chunk.f2, start + chunk.f3])
                faces.append([start + chunk.f4, start + chunk.f5, start + chunk.f6])
        return faces
    
    def unmake(self, mesh):
        face_buffer = [[v for v in face.vertices] for face in mesh.data.polygons]
        
        
    def write(self):
        pass
    
class MaterialTextureChunk(DataStruct):
    def __init__(self, model):
        super().__init__('>3IHH')
        self.data = []
        self.model = model
    def read(self, buffer, cursor):
        self.data = struct.unpack_from(self.format_string, buffer, cursor)
    
class MaterialTexture(DataStruct):
    def __init__(self, model):
        super().__init__('>Ihh4x8H6I4xhh')
        self.model = model
        self.id = None
        self.unk0 = None
        self.unk1 = None
        self.unk2 = None
        self.unk3 = None
        self.format = None
        self.unk4 = None
        self.width = None
        self.height = None
        self.unk5 = None
        self.unk6 = None
        self.unk7 = None
        self.unk8 = None
        self.chunks = []
        self.unk9 = None
        self.tex_index = None
        
    def read(self, buffer, cursor):
        unk_pointers = []
        self.id = cursor
        self.unk0, self.unk1, self.unk3, self.format, self.unk4, self.width, self.height, self.unk5, self.unk6, self.unk7, self.unk8, *unk_pointers, self.unk9, self.tex_index = struct.unpack_from(self.format_string, buffer, cursor)
        for pointer in unk_pointers:
            chunk = MaterialTextureChunk(self.model)
            chunk.read(buffer, pointer)
            self.chunks.append(chunk)
        
    def make(self):
        if self.tex_index < 0:
            return
        textureblock = self.model.modelblock.textureblock
        self.texture = Texture(self.tex_index, self.format, self.width, self.height)
        self.texture.read(textureblock)
        return self.texture.make()
        
class MaterialUnk(DataStruct):
    def __init__(self, model):
        super().__init__('>17H4B7H')
        self.model = model
        self.data = None
        self.color = []
    def read(self, buffer, cursor):
        data = []
        *data, r, g, b, a, unk17, unk18, unk19, unk20, unk21, unk22, unk23 = struct.unpack_from(self.format_string, buffer, cursor)
        self.color = [r, g, b, a]
        self.data = data.extend([unk17, unk18, unk19, unk20, unk21, unk22, unk23])
    
    def make(self):
        pass
    
class Material(DataStruct):
    def __init__(self, model):
        super().__init__('>I4xII')
        self.id = None
        self.model = model
        self.format = 0
        self.texture = None
        self.unk = None
        
    def read(self, buffer, cursor):
        self.id = cursor
        self.format, texture_addr, unk_addr = struct.unpack_from(self.format_string, buffer, cursor)
        if texture_addr:
            if texture_addr in self.model.textures:
                return self.model.textures[texture_addr]
            else:
                self.model.textures[texture_addr] = MaterialTexture(self.model)
                self.model.textures[texture_addr].read(buffer, texture_addr)
                self.texture = self.model.textures[texture_addr]
            
        if unk_addr:
            self.unk = MaterialUnk(self.model)
            self.unk.read(buffer, unk_addr)
        
    def make(self):
        mat_name = str(self.id)
        if (self.texture is not None):
            material = bpy.data.materials.get(mat_name)
            if material is not None:
                return material
            
            material = bpy.data.materials.new(mat_name)
            material.use_nodes = True
            #material.blend_method = 'BLEND' #use for transparency
            material.blend_method = 'CLIP'
            
            if self.texture.format == 3:
                material.blend_method = 'BLEND'
            if self.texture.format != 6:
                material.use_backface_culling = True
            if self.unk.data is not None and self.unk.data[1] == 8:
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
            
            image = str(self.texture.tex_index)
            if image in ["1167", "1077", "1461", "1596"]: #probably shouldn't do it this way; TODO find specific tag
                material.blend_method = 'BLEND'
                material.node_tree.links.new(node_1.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Alpha"])
            
            if self.format in [31, 15, 7]:
                material.node_tree.links.new(node_2.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Normal"])
                material.node_tree.links.new(node_1.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Base Color"])
            
            chunk_tag = self.texture.chunks[0].data[0] if len(self.texture.chunks) else 0
            if(self.texture.chunks and chunk_tag & 0x11 != 0):
                node_4 = material.node_tree.nodes.new("ShaderNodeUVMap")
                node_5 = material.node_tree.nodes.new("ShaderNodeSeparateXYZ")
                node_6 = material.node_tree.nodes.new("ShaderNodeCombineXYZ")
                material.node_tree.links.new(node_4.outputs["UV"], node_5.inputs["Vector"])
                material.node_tree.links.new(node_6.outputs["Vector"], node_1.inputs["Vector"])
                if(chunk_tag & 0x11 == 0x11):
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
                elif(chunk_tag & 0x11 == 0x01):
                    material.node_tree.links.new(node_5.outputs["X"], node_6.inputs["X"])
                    node_7 = material.node_tree.nodes.new("ShaderNodeMath")
                    node_7.operation = 'PINGPONG'
                    node_7.inputs[1].default_value = 1
                    material.node_tree.links.new(node_5.outputs["Y"], node_7.inputs["Value"])
                    material.node_tree.links.new(node_7.outputs["Value"], node_6.inputs["Y"])
                elif(chunk_tag & 0x11 == 0x10):
                    node_7 = material.node_tree.nodes.new("ShaderNodeMath")
                    node_7.operation = 'PINGPONG'
                    node_7.inputs[1].default_value = 1
                    material.node_tree.links.new(node_5.outputs["X"], node_7.inputs["Value"])
                    material.node_tree.links.new(node_7.outputs["Value"], node_6.inputs["X"])
                    material.node_tree.links.new(node_5.outputs["Y"], node_6.inputs["Y"])

            b_tex = bpy.data.images.get(image)
            if b_tex is None:
                b_tex = self.texture.make()

            image_node = material.node_tree.nodes["Image Texture"]
            image_node.image = b_tex

        else:
            material = bpy.data.materials.new(mat_name)
            material.use_nodes = True
            material.node_tree.nodes["Principled BSDF"].inputs[5].default_value = 0
            colors = [0, 0, 0, 0] if self.unk is None else self.unk.color
            material.node_tree.nodes["Principled BSDF"].inputs[0].default_value = [c/255 for c in colors]
            node_1 = material.node_tree.nodes.new("ShaderNodeVertexColor")
            material.node_tree.links.new(node_1.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Base Color"])
            
        return material
    
    def unmake(self, material):
        pass
    def write(self, buffer, cursor):
        return cursor
    
class Visuals(DataStruct):
    def __init__(self, model):
        super().__init__('>I36xI4xII2xHI')
        self.model = model
        self.material = None
        self.vert_buffer = None
        self.index_buffer = None
        self.group_parent = None
        self.group_count = None
        self.id = None
    
    def read(self, buffer, cursor):
        self.id = cursor
        mat_addr, self.group_parent, index_buffer_addr, vert_buffer_addr, vert_count, self.group_count = struct.unpack_from(self.format_string, buffer, cursor)
        
        if vert_buffer_addr:
            self.vert_buffer = VisualsVertBuffer(self.model, vert_count)
            self.vert_buffer.read(buffer, vert_buffer_addr)
            
        if index_buffer_addr:
            self.index_buffer = VisualsIndexBuffer(self.model)
            self.index_buffer.read(buffer, index_buffer_addr, vert_buffer_addr)
            
        if mat_addr:
            if mat_addr in self.model.materials: #we've already read this material
                self.material = self.model.materials[mat_addr]
            else:
                self.model.materials[mat_addr] = Material(self.model)
                self.model.materials[mat_addr].read(buffer, mat_addr)
                self.material = self.model.materials[mat_addr]
    
    def make(self, parent):
        if self.vert_buffer is None or self.index_buffer is None:
            return
        
        verts = [vert.pos for vert in self.vert_buffer.data]
        edges = []
        faces = self.index_buffer.make()
        mesh_name = str(self.id) + "_" + "visuals"
        mesh = bpy.data.meshes.new(mesh_name)
        obj = bpy.data.objects.new(mesh_name, mesh)
        print(verts, faces)
        obj['type'] = 'VIS'    
        obj['id'] = self.id
        obj.scale = [self.model.scale, self.model.scale, self.model.scale]

        self.model.collection.objects.link(obj)
        mesh.from_pydata(verts, edges, faces)
        obj.parent = parent
        
        mesh.materials.append(
           self.material.make()
        )
        
        #set vector colors / uv coords
        uv_layer = mesh.uv_layers.new(name = 'uv')
        color_layer = mesh.vertex_colors.new(name = 'colors') #color layer has to come after uv_layer
        for poly in mesh.polygons:
            for p in range(len(poly.vertices)):
                v = self.vert_buffer.data[poly.vertices[p]]
                uv_layer.data[poly.loop_indices[p]].uv = [u/4096 for u in v.uv]
                color_layer.data[poly.loop_indices[p]].color = [a/255 for a in v.color]
    def unmake(self, node):
        self.id = node.name
        
        self.material = Material(self.model).unmake(node)
        self.vert_buffer = VisualsVertBuffer(self.model).unmake(node)
        self.index_buffer = VisualsIndexBuffer(self.model).unmake(node)
        
        #TODO check if node has vertex group
        if False:
            self.group_parent = None
            self.group_count = None
        
    def write(self, buffer, cursor):
        mat_addr = 0
        index_buffer_addr = 0
        vert_buffer_addr = 0
        visuals_start = cursor
        print('visuals start', cursor)
        cursor += self.size
        
        mat_addr = cursor
        cursor = self.material.write(buffer, cursor)
        
        #group parent
        
        index_buffer_addr = cursor
        cursor = self.index_buffer.write(buffer, cursor)
        
        vert_buffer_addr = cursor
        cursor = self.vert_buffer.write(buffer, cursor)
        
        vert_count = self.vert_buffer.length
        
        #group count
        print(cursor)
        struct.pack_into(self.format_string, buffer, visuals_start, mat_addr, self.group_parent, index_buffer_addr, vert_buffer_addr, vert_count, self.group_count)
        return cursor
    
class MeshBoundingBox():
    #only need to calculate bounding box for export workflow
    def __init__(self, mesh):
        
    
class Mesh():
    def __init__(self, model):
        self.model = model
        self.collision = Collision(self.model)
        self.visuals = Visuals(self.model)
        self.bounding_box = 
    def read(self, buffer, cursor):
        self.collision.read(buffer, cursor)
        self.visuals.read(buffer, cursor)
        return self
    def make(self, parent):
        self.collision.make(parent)
        self.visuals.make(parent)
        return
    def unmake(self, node):
        if node['type'] == 'VIS':
            self.visuals.unmake(node)
        elif node['type'] == 'COL':
            self.collision.unmake(node)
        return self
    def write(self, buffer, cursor):
        print('writing mesh')
        self.collision.write(buffer, cursor)
        self.visuals.write(buffer, cursor)
    def bounding_box(self):
        
    
def create_node(node_type, model):
    NODE_MAPPING = {
        12388: MeshGroup12388,
        20580: Group20580,
        20581: Group20581,
        20582: Group20582,
        53348: Group53348,
        53349: Group53349,
        53350: Group53350
    }

    node_class = NODE_MAPPING.get(node_type)
    if node_class:
        return node_class(model, node_type)
    else:
        raise ValueError(f"Invalid node type {node_type}")
    
class Node(DataStruct):
    def __init__(self, model, type):
        super().__init__('>7I')
        self.type = type
        self.id = None
        self.head = []
        self.children = []
        self.AltN = []
        self.header = []
        self.node_type = None
        self.load_group1 = None
        self.load_group2 = None
        self.unk1 = None
        self.unk2 = None
        self.model = model
        self.child_count = 0
        self.child_start = None
    def read(self, buffer, cursor):
        self.id = cursor
        self.node_type, self.load_group1, self.load_group2, self.unk1, self.unk2, self.child_count, self.child_start = struct.unpack_from(self.format_string, buffer, cursor)
        
        if self.model.AltN and cursor in self.model.AltN:
            self.AltN = [i for i, h in enumerate(self.model.AltN) if h == cursor]
        
        if cursor in self.model.header.offsets:
            self.header = [i for i, h in enumerate(self.model.header.offsets) if h == cursor]

        if not self.model.ref_map.get(self.id):
            self.model.ref_map[self.id] = True
        
        for i in range(self.child_count):
            child_address = readUInt32BE(buffer, self.child_start + i * 4)
            if not child_address:
                if (self.child_start + i * 4) in self.model.AltN:
                    self.children.append({'id': self.child_start + i * 4, 'AltN': True})
                else:
                    self.children.append({'id': None})  # remove later
                continue

            if self.model.ref_map.get(child_address):
                self.children.append({'id': child_address})
                continue

            if isinstance(self, MeshGroup12388):
                self.children.append(Mesh(self.model).read(buffer, child_address))
            else:
                node = create_node(readUInt32BE(buffer, child_address), self.model)
                self.children.append(node.read(buffer, child_address))
 
        return self
    def make(self, parent=None):
        name = str(self.id)
        if (self.type in [53349, 53350]):
            new_empty = bpy.data.objects.new(name, None)
            self.model.collection.objects.link(new_empty)
            
            #new_empty.empty_display_size = 2
            if self.unk1 &  1048576 != 0:
                new_empty.empty_display_type = 'ARROWS'
                new_empty.empty_display_size = 0.5
                
            elif self.unk1 & 524288 != 0:
                new_empty.empty_display_type = 'CIRCLE'
                new_empty.empty_display_size = 0.5
            else:
                new_empty.empty_display_type = 'PLAIN_AXES'
            # if self.type ==53349:
            #     #new_empty.location = [node['xyz']['x']*scale, node['xyz']['y']*scale, node['xyz']['z']*scale]
            #     if self.unk1 &  1048576 != 0 and False:
                    
            #         global offsetx
            #         global offsety
            #         global offsetz
            #         offsetx = node['xyz']['x1']
            #         offsety = node['xyz']['y1']
            #         offsetz = node['xyz']['z1']
            #         imparent = None
            #         if parent != None and False:
            #             imparent = parent
            #             while imparent != None:
            #                 #print(imparent, imparent['grouptag0'], imparent['grouptag3'])
            #                 if int(imparent['grouptag0']) == 53349 and int(imparent['grouptag3']) & 1048576 != 0:
            #                     #print('found one')
            #                     offsetx += imparent['x']
            #                     offsety += imparent['y']
            #                     offsetz += imparent['z']
            #                 imparent = imparent.parent
            #         #print(offsetx, offsety, offsetz)
            #         new_empty.matrix_world = [
            #         [node['xyz']['ax'], node['xyz']['ay'], node['xyz']['az'], 0],
            #         [node['xyz']['bx'], node['xyz']['by'], node['xyz']['bz'], 0],
            #         [node['xyz']['cx'], node['xyz']['cy'], node['xyz']['cz'], 0],
            #         [node['xyz']['x']*scale + offsetx*scale,  node['xyz']['y']*scale + offsety*scale, node['xyz']['z']*scale + offsetz*scale, 1],
            #         ]
            #     elif False:
            #         new_empty.matrix_world = [
            #         [node['xyz']['ax'], node['xyz']['ay'], node['xyz']['az'], 0],
            #         [node['xyz']['bx'], node['xyz']['by'], node['xyz']['bz'], 0],
            #         [node['xyz']['cx'], node['xyz']['cy'], node['xyz']['cz'], 0],
            #         [node['xyz']['x']*scale, node['xyz']['y']*scale, node['xyz']['z']*scale, 1],
            #         ]
            
                
        else:
            new_empty = bpy.data.objects.new(name, None)
            #new_empty.empty_display_type = 'PLAIN_AXES'
            new_empty.empty_display_size = 0
            self.model.collection.objects.link(new_empty)
            
        #set group tags
        new_empty['node_type'] = self.node_type
        new_empty['load_group1'] = str(self.load_group1)
        new_empty['load_group2'] = str(self.load_group2)
        new_empty['unk1'] = self.unk1
        new_empty['unk2'] = self.unk2
        
        # if False and (self.type in [53349, 53350]):
        #     new_empty['grouptag3'] = bin(int(node['head'][3]))
        #     if 'xyz' in node:
        #         new_empty['x'] = node['xyz']['x']
        #         new_empty['y'] = node['xyz']['y']
        #         new_empty['z'] = node['xyz']['z']
        #         if 'x1' in node['xyz']:
        #             new_empty['x1'] = node['xyz']['x1']
        #             new_empty['y1'] = node['xyz']['y1']
        #             new_empty['z1'] = node['xyz']['z1']
            
        #assign parent
        if parent is not None:
            #savedState = new_empty.matrix_world
            new_empty.parent = parent
            # if self.type not in [53349, 53350] or self.unk1 & 1048576 == 0 and False:
            #     new_empty.parent = parent
            #     #if(node['head'][3] & 1048576) == 0:
            #     #loc = new_empty.constraints.new(type='COPY_LOCATION')
            #     #loc.target = parent
            #     #elif(node['head'][3] & 524288) == 0:
            #         #rot = new_empty.constraints.new(type='COPY_ROTATION')
            #         #rot.target = parent
            #     #else:
            #         #new_empty.parent = parent
                    
            # else:
            #     new_empty.parent = parent
            #new_empty.matrix_world = savedState
        for node in self.children:
            if not isinstance(node, dict):
                node.make(new_empty)
            
        return new_empty
    def unmake(self, node):
        self.id = node.name
        self.node_type = node['node_type']
        self.load_group1 = int(node['load_group1'])
        self.load_group2 = int(node['load_group2'])
        self.unk1 =  node['unk1']
        self.unk2 = node['unk2']
        if self.node_type == 12388:
            for child in node.children:
                self.children.append(Mesh(self.model).unmake(child))
        else:
            for child in node.children:
                n = create_node(child['node_type'], self.model)
                self.children.append(n.unmake(child))
        print(self.id, self.node_type, self.load_group1, self.load_group2, self.unk1, self.unk2)
        return self
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, self.node_type, self.load_group1, self.load_group2, self.unk1, self.unk2, len(self.children), 0)
        cursor += self.size
        
        return cursor
    
    def write_children(self, buffer, cursor):
        if not len(self.children):
            return cursor
        for child in self.children:
            cursor = child.write(buffer, cursor)
        return cursor

class MeshGroup12388(Node):
    def __init__(self, model, type):
        super().__init__(model, type)
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        return self
    def make(self, parent = None):
        return super().make(parent)
    def unmake(self, node):
        return super().unmake(node)
    def write(self, buffer, cursor):
        print('writing 12388')
        cursor = super().write(buffer, cursor)
        child_addr_start = cursor - 4
        writeInt32BE(buffer, cursor, child_addr_start)
        self.model.highlight(child_addr_start)
        cursor = super().write_children(buffer, cursor)
        return cursor
        
class Group53348(Node):
    print('writing 53348')
    
    def __init__(self, model, type):
        super().__init__(model, type)
        self.matrix = FloatMatrix()
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.matrix = FloatMatrix(struct.unpack_from(">12f", buffer, cursor+28))
        return self
    def make(self, parent = None):
        empty = super().make(parent)
        empty.matrix_world = self.matrix.get()
        return empty
    def unmake(self, node):
        return super().unmake(node)
    def write(self, buffer, cursor):
        print('writing 53348')
        cursor = super().write(buffer, cursor)
        child_addr_start = cursor - 4
        writeInt32BE(buffer, cursor, child_addr_start)
        self.model.highlight(child_addr_start)
        cursor = super().write_children(buffer, cursor)
        return cursor
        
class Group53349(Node):
    def __init__(self, model, type):
        super().__init__(model, type)
        self.matrix = FloatMatrix()
        self.bonus = FloatPosition()
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.matrix.set(struct.unpack_from(">12f", buffer, cursor+28))
        self.bonus.set(struct.unpack_from(">3f", buffer, cursor+76))
        return self
    def make(self, parent = None):
        empty = super().make(parent)
        #empty.matrix_world = self.matrix.make()
        empty['bonus'] = self.bonus.get()
        return empty
    def unmake(self, node):
        super().unmake(node)
        self.matrix.unmake(node.matrix_world)
        self.bonus.set(node['bonus'])
        return self
    def write(self, buffer, cursor):
        print('writing 53349')
        cursor = super().write(buffer, cursor)
        child_addr_start = cursor - 4
        writeInt32BE(buffer, cursor, child_addr_start)
        self.model.highlight(child_addr_start)
        cursor = super().write_children(buffer, cursor)
        return cursor
        
class Group53350(Node):
    def __init__(self, model, type):
        super().__init__(model, type)
        self.unk1 = None
        self.unk2 = None
        self.unk3 = None
        self.unk4 = None
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.unk1, self.unk2, self.unk3, self.unk4 = struct.unpack_from(">3If", buffer, cursor+28)
        return self
    def make(self, parent = None):
        new_empty = super().make(parent)
        new_empty['53350_unk1'] = self.unk1
        new_empty['53350_unk2'] = self.unk2
        new_empty['53350_unk3'] = self.unk3
        new_empty['53350_unk4'] = self.unk4
        return new_empty
    def unmake(self, node):
        super().unmake(node)
        self.unk1 = node['53350_unk1']
        self.unk2 = node['53350_unk2']
        self.unk3 = node['53350_unk3']
        self.unk4 = node['53350_unk4']
    def write(self, buffer, cursor):
        print('writing 53350')
        cursor = super().write(buffer, cursor)
        child_addr_start = cursor - 4
        writeInt32BE(buffer, cursor, child_addr_start)
        self.model.highlight(child_addr_start)
        cursor = super().write_children(buffer, cursor)
        return cursor
  
class Group20580(Node):
    def __init__(self, model, type):
        super().__init__(model, type)
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        return self
    def make(self, parent = None):
        return super().make(parent)
    def unmake(self, node):
        return super().unmake(node)
    def write(self, buffer, cursor):
        print('writing 20580')
        cursor = super().write(buffer, cursor)
        child_addr_start = cursor - 4
        writeInt32BE(buffer, cursor, child_addr_start)
        self.model.highlight(child_addr_start)
        cursor = super().write_children(buffer, cursor)
        return cursor
      
class Group20581(Node):
    def __init__(self, model, type):
        super().__init__(model, type)
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        return self
    def make(self, parent = None):
        return super().make(parent)
    def unmake(self, node):
        return super().unmake(node)
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_addr_start = cursor - 4
        if len(self.children):
            cursor += 4
        writeInt32BE(buffer, cursor, child_addr_start)
        self.model.highlight(child_addr_start)
        cursor = super().write_children(buffer, cursor)
        return cursor
    
class Group20582(Node):
    def __init__(self, model, type):
        super().__init__(model, type)
        self.floats = []
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.floats = struct.unpack_from(">11f", buffer, cursor+28)
        return self
    def make(self, parent = None):
        empty = super().make(parent)
        empty['floats'] = self.floats
        return self
    def unmake(self, node):
        super().unmake(node)
        self.floats = node['floats']
        return self
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_addr_start = cursor - 4
        struct.pack_into(">11f", buffer, cursor, *self.floats)
        cursor += self.size
        writeInt32BE(buffer, cursor, child_addr_start)
        self.model.highlight(child_addr_start)
        cursor = super().write_children(buffer, cursor)
        return cursor
      
class LStr(DataStruct):
    def __init__(self, model):
        super().__init__('>4x3f')
        self.data = FloatPosition()
        self.model = model
    def read(self, buffer, cursor):
        x, y, z = struct.unpack_from(self.format_string, buffer, cursor)
        self.data.set([x, y , z])
        return self
    def make(self):
        lightstreak_col = self.model.lightstreaks
        light = bpy.data.lights.new(name = "lightstreak", type = 'POINT')
        light_object = bpy.data.objects.new(name = "lightstreak", object_data = light)
        lightstreak_col.objects.link(light_object)
        print(self.data.data)
        light_object.location = (self.data.data[0]*self.model.scale, self.data.data[1]*self.model.scale, self.data.data[2]*self.model.scale)
        
    def unmake(self):
        return self
    def write(self, buffer, cursor):
        return cursor
        
class ModelData():
    def __init__(self, model):
        self.data = []
        self.model = model
    def read(self, buffer, cursor):
        size = readUInt32BE(buffer, cursor)
        cursor += 4
        i = 0
        while i < size:
            if readString(buffer, cursor) == 'LStr':
                self.data.append(LStr(self.model).read(buffer, cursor))
                cursor += 16
                i += 4
            else:
                self.data.append(readUInt32BE(buffer,cursor))
                i+=1
                cursor += 4
        return cursor
    def make(self):
        for d in self.data:
            d.make()
    def unmake(self):
        pass
    def write(self, buffer, cursor):
        
        return cursor
    
class Anim(DataStruct):
    def __init__(self, model):
        super().__init__('>244x3f2HI5f4I')
        self.model = model
        self.float1 = None
        self.float2 = None
        self.float3 = None
        self.flag1 = None
        self.flag2 = None
        self.num_keyframes = 0
        self.float4 = None
        self.float5 = None
        self.float6 = None
        self.float7 = None
        self.float8 = None
        self.keyframe_times = []
        self.keyframe_poses = []
        self.target = None
        self.unk32 = None
    def read(self, buffer, cursor):
        self.float1, self.float2, self.float3, self.flag1, self.flag2, self.num_keyframes, self.float4, self.fllat5, self.float6, self.float7, self.float8, keyframe_times_addr, keyframe_poses_addr, self.target, self.unk2 = struct.unpack_from(self.format_string, buffer, cursor)
        if self.flag2 in [2, 18]:
            self.target = readUInt32BE(buffer, self.target)

        for f in range(self.num_keyframes):
            if keyframe_times_addr:
                self.keyframe_times.append(readFloatBE(buffer, keyframe_times_addr + f * 4))

            if keyframe_poses_addr:
                if self.flag2 in [8, 24, 40, 56, 4152]:  # rotation (4)
                    self.keyframe_poses.append([
                        readFloatBE(buffer, keyframe_poses_addr + f * 16),
                        readFloatBE(buffer, keyframe_poses_addr + f * 16 + 4),
                        readFloatBE(buffer, keyframe_poses_addr + f * 16 + 8),
                        readFloatBE(buffer, keyframe_poses_addr + f * 16 + 12)
                    ])
                elif self.flag2 in [25, 41, 57, 4153]:  # position (3)
                    self.keyframe_poses.append([
                        readFloatBE(buffer, keyframe_poses_addr + f * 12),
                        readFloatBE(buffer, keyframe_poses_addr + f * 12 + 4),
                        readFloatBE(buffer, keyframe_poses_addr + f * 12 + 8)
                    ])
                elif self.flag2 in [27, 28]:  # uv_x/uv_y (1)
                    self.keyframe_poses.append([
                        readFloatBE(buffer, keyframe_poses_addr + f * 4)
                    ])
                elif self.flag2 in [2, 18]:  # texture
                    tex = readUInt32BE(buffer,keyframe_poses_addr + f * 4)

                    if tex < cursor:
                        self.keyframe_poses.append({'repeat': tex})
                    else:
                        self.keyframe_poses.append(read_mat_texture(buffer=buffer, cursor=tex, model=model))
    
class ModelAnim():
    def __init__(self, model):
        self.data = []
        self.model = model
    def read(self, buffer, cursor):
        anim = readUInt32BE(buffer, cursor)
        while anim:
            self.data.append(Anim(self.model).read(buffer, anim))
            cursor += 4
            anim = readUInt32BE(buffer, cursor)
        return cursor + 4
    def make(self):
        pass
    def unmake(self):
        pass
    def write(self, buffer, cursor):
        return cursor

class ModelHeader():
    def __init__(self, model):
        self.offsets = []
        self.model = model

    def read(self, buffer, cursor):
        self.model.ext = readString(buffer, cursor)
        cursor = 4
        header = readInt32BE(buffer, cursor)

        while header != -1:
            self.offsets.append(header)
            cursor += 4
            header = readInt32BE(buffer, cursor)

        cursor += 4
        header_string = readString(buffer, cursor)
        
        while header_string != 'HEnd':
            if header_string == 'Data':
                self.model.Data = ModelData(self.model)
                cursor = self.model.Data.read(buffer, cursor + 4)
                header_string = readString(buffer, cursor)
            elif header_string == 'Anim':
                self.model.Anim = ModelAnim(self.model)
                cursor = self.model.Anim.read(buffer, cursor + 4)
                header_string = readString(buffer, cursor)
            elif header_string == 'AltN':
                cursor = read_AltN(buffer, cursor + 4, model)
                header_string = readString(buffer, cursor)
            elif header_string != 'HEnd':
                raise ValueError('unexpected header string', header_string)
        return cursor + 4
    
    def make(self):
        self.model.collection['header'] = self.offsets
        self.model.collection['ind'] = self.model.id
        self.model.collection['ext'] = self.model.ext
        
       
        
        lightstreaks_col = bpy.data.collections.new("lightstreaks")
        lightstreaks_col['type'] = 'LSTR'
        self.model.lightstreaks = lightstreaks_col
        self.model.collection.children.link(lightstreaks_col)
        if self.model.Data:
            self.model.Data.make()
        return
    
    def unmake(self, collection):
        self.offsets = collection['header']
        self.model.id = collection['ind']
        self.model.ext = collection['ext']
    
    def write(self, buffer, cursor):
        cursor = writeString(buffer,  self.model.ext, cursor)

        for header_value in self.offsets:
            #self.model.outside_ref(cursor, header_value)
            self.model.highlight(cursor)
            cursor += 4  # writeInt32BE(buffer, header_value, cursor)

        cursor = writeInt32BE(buffer, -1, cursor)

        if self.model.Data:
            pass
            #cursor = write_data(buffer, cursor, model, hl)

        if self.model.Anim:
            self.model.ref_map['Anim'] = cursor + 4
            #cursor = write_anim(buffer, cursor, model, hl)

        if self.model.AltN:
            self.model.ref_map['AltN'] = cursor + 4
            #cursor = write_altn(buffer, cursor, model, hl)

        cursor = writeString(buffer, 'HEnd', cursor)
        self.model.ref_map['HEnd'] = cursor

        return cursor

def find_topmost_parent(obj):
    while obj.parent is not None:
        obj = obj.parent
    return obj

class Model():
    def __init__(self, id):
        self.modelblock = None
        self.collection = None
        self.ext = None
        self.id = id
        self.scale = 0.01
        
        self.ref_map = {} # where we'll map node ids to their written locations
        self.ref_keeper = {} # where we'll remember locations of node refs to go back and update with the ref_map at the end
        self.hl = None
        
        self.header = ModelHeader(self)
        self.Data = []
        self.AltN = []
        self.Anim = []
        
        self.materials = {}
        self.textures = {}
        self.nodes = []

    def read(self, modelblock):
        self.modelblock = modelblock
        if self.id is None:
            return
        offset_buffers, model_buffers = modelblock.read([self.id])
        buffer = model_buffers[0]
        cursor = 0
        cursor = self.header.read(buffer, cursor)
        
        if self.AltN and self.ext != 'Podd':
            AltN = list(set(self.header.AltN))
            for i in range(len(AltN)):
                node_type = readUInt32BE(buffer, cursor)
                node = create_node(node_type, self)
                self.nodes.append(node.read(buffer, AltN[i]))
        else:
            node_type = readUInt32BE(buffer, cursor)
            node = create_node(node_type, self)
            self.nodes = [node.read(buffer, cursor)]
            
        return self

    def make(self):
        collection = bpy.data.collections.new(f"model_{self.id}_{self.ext}")
        
        collection['type'] = 'MODEL'
        bpy.context.scene.collection.children.link(collection)
        self.collection = collection
        
        self.header.make()
        for node in self.nodes:
            node.make()

        return collection

    def unmake(self, collection):
        self.ext = collection['ext']
        self.id = collection['ind']
        self.header.unmake(collection)
        self.nodes = []
        if 'parent' in collection: return
        
        top_nodes = [] 
        for obj in collection.objects:
            if obj.type != 'MESH': continue
            top = find_topmost_parent(obj)
            if top not in top_nodes: top_nodes.append(top)
        
        for node in top_nodes:
            n = create_node(node['node_type'], self)
            self.nodes.append(n.unmake(node))
            
        return self

    def write(self):
        buffer = bytearray(8000000)
        self.hl = bytearray(1000000)
        cursor = 0

        cursor = self.header.write(buffer, cursor)

        # write all nodes
        for node in self.nodes:
            cursor = node.write(buffer, cursor)

        # write all animations
        for anim in self.Anim:
            cursor = anim.write(buffer, cursor)

        # write all outside references
        refs = [ref for ref in self.ref_keeper if ref != '0']
        for ref in self.ref_keeper:
            for offset in self.ref_keeper[ref]:
                writeUInt32BE(buffer, self.ref_map[str(ref)], offset)
        crop = math.ceil(cursor / (32 * 4)) * 4
        return [self.hl[:crop], buffer[:cursor]]
    
    def outside_ref(self, cursor, ref):
        # Used when writing modelblock to keep track of references to offsets outside of the given section
        ref = str(ref)
        if ref not in self.ref_keeper:
            self.ref_keeper[ref] = []
        self.ref_keeper[ref].append(cursor)
        
    def map_ref(self, cursor, id):
        # Used when writing modelblock to map original ids of nodes to their new ids
        id = str(id)
        if id not in self.ref_map:
            self.ref_map[id] = cursor
            
    def highlight(self, cursor):
        # This function is called whenever an address needs to be 'highlighted' because it is a pointer
        # Every model begins with a pointer map where each bit represents 4 bytes in the following model
        # If the bit is 1, that corresponding DWORD is to be read as a pointer

        highlight_offset = cursor // 32
        bit = 2 ** (7 - (cursor % 32) // 4)
        highlight = self.hl[highlight_offset]
        self.hl[highlight_offset] = highlight | bit