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
from .general import *
from .textureblock import Texture
from .popup import show_custom_popup

class Lights(Data):
    def __init__(self):
        self.flag = 0
        self.ambient = Color()
        self.color = Color()
        self.unk1 = 0
        self.unk2 = 0
        self.pos = FloatPosition()
        self.rot = FloatVector()
    
    def to_array(self):
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
    def __init__(self, parent, model):
        
        super().__init__('>H4B3H8B6f2I2i')
        self.parent = parent
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
        struct.pack_into(self.format_string, buffer, cursor, *[self.unk, *self.fog.get(), *self.lights.get(), self.flags, self.unk2, self.unload, self.load])
        return cursor + self.size 

class CollisionVertBuffer(DataStruct):
    def __init__(self, parent, model, length = 0):
        
        super().__init__(f'>{length*3}h')
        self.parent = parent
        self.length = length
        self.model = model
        self.data = []

    def __str__(self):
        return str(self.data)

    def read(self, buffer, cursor):
        for i in range(self.length):
            xyz = ShortPosition().read(buffer, cursor)
            self.data.append(xyz)
            cursor += xyz.size
        
        return self

    def make(self):
        return [vert.make() for vert in self.data]
    
    def to_array(self):
        return [a for d in self.data for a in d.to_array()]
    
    def unmake(self, mesh):
        self.length = len(mesh.data.vertices)
        for vert in mesh.data.vertices:
            co = mesh.matrix_world @ vert.co
            co = [round(c/self.model.scale) for c in co]
            self.data.append(ShortPosition().from_array(co))
        super().__init__(f'>{len(self.data)*3}h')
        return self
    
class CollisionVertStrips(DataStruct):
    def __init__(self, parent, model, count = 0):
        
        super().__init__(f'>{count}I')
        self.parent = parent
        self.model = model
        self.data = []
        self.strip_count = count
        self.strip_size = 3
        self.include_buffer = False
    
    def unmake(self, mesh):
        #recognizes strips in the pattern of the faces' vertex indices
        face_buffer = [[v for v in face.vertices] for face in mesh.data.polygons]
        if not len(face_buffer):
            return self
        
        while len(face_buffer):
            end_strip = 1
            for i in range(1, len(face_buffer)):
                last = face_buffer[i - 1]
                
                # this detects cases where the strip buffer needs to be written
                # the index pattern is different depending on whether the strip buffer is provided or not
                if last[0] % 2 == 0 and last[0] + 1 == last[1] and last[1] + 1 == last[2]:
                    self.include_buffer = True
                
                # a strip continues as long as there are 2 shared indices between adjacent faces
                shared = [j for j in face_buffer[i] if j in last]
                if len(shared) == 0:
                    break
                end_strip += 1
                
            # push strip size and process remaining faces
            face_buffer = face_buffer[end_strip:]
            self.data.append(end_strip + 2)
            
        self.strip_count = len(self.data)
        # if all the strips are the same, update strip_size, otherwise we need to write this buffer
        if all(strip == self.data[0] for strip in self.data):
            self.strip_size = self.data[0]
            if self.data[0] == 3:
                self.include_buffer = False
        else:
            self.include_buffer = True
                
        if self.include_buffer:
            self.strip_size = 5
        super().__init__(f'>{len(self.data)}I')
        return self
    
class VisualsVertChunk(DataStruct):
    def __init__(self, parent, model):
       
        super().__init__('>hhh2xhhBBBB')
        self.parent = parent
        self.model = model
        self.co = []
        self.uv = [0, 0]
        self.color = RGBA4Bytes()
    def read(self, buffer, cursor):
        x, y, z, uv_x, uv_y, r, g, b, a = struct.unpack_from(self.format_string, buffer, cursor)
        self.co = [x, y, z]
        self.uv = [uv_x, uv_y]
        self.color = RGBA4Bytes(r, g, b, a)
        return cursor + self.size
    def to_array(self):
        return [*self.co, *self.uv, *self.color.to_array()]
    
    def verts_to_array(self):
        return self.co
    
    def __eq__(self, other):
        return self.co == other.co and self.uv == other.uv and self.color == other.color
    
    def unmake(self, co, uv, color):
        self.co = [round(c/self.model.scale) for c in co]
        if uv:
            self.uv = [round(c*4096) for c in uv]
        if color:
            self.color = RGBA4Bytes().unmake(color)
        if self.parent.parent.id == 'Royal_Raceway.065':
            print(self.uv)
        return self
    def write(self, buffer, cursor):
        co =  [min(32767, max(-32768, c)) for c in self.co]
        self.co = co
        uv =[min(32767, max(-32768, c)) for c in self.uv]
        self.uv = uv
        if self.parent.parent.id == 'Royal_Raceway.065':
            print(uv)
        struct.pack_into(self.format_string, buffer, cursor, *self.co, *self.uv, *self.color.make())
        return cursor + self.size
    
class VisualsVertBuffer():
    def __init__(self, parent, model, length = 0):
        self.parent = parent
        self.model = model
        self.data = []
        self.length = length
        
    def read(self, buffer, cursor):
        for i in range(self.length):
            vert = VisualsVertChunk(self, self.model)
            cursor = vert.read(buffer, cursor)
            self.data.append(vert)
        return self
    
    def make(self):
        return [v.co for v in self.data]
    
    def unmake(self, mesh):
        uv_data = None
        color_data = None
        
        if mesh.data.uv_layers.active:
            uv_data = mesh.data.uv_layers.active.data
        if mesh.data.vertex_colors.active:
            color_data = mesh.data.vertex_colors.active.data
        
        for vert in mesh.data.vertices:
            self.data.append(VisualsVertChunk(self, self.model))
            
        #there's probably a better way to do this but this works for now
        #https://docs.blender.org/api/current/bpy.types.Mesh.html
        for poly in mesh.data.polygons:
            for loop_index in poly.loop_indices:
                vert_index = mesh.data.loops[loop_index].vertex_index
                uv = None if not uv_data else uv_data[loop_index].uv
                if self.parent.id == 'Royal_Raceway.065':
                    print('unmaking', uv)
                color = None if not color_data else color_data[loop_index].color
                self.data[vert_index].unmake(mesh.matrix_world @ mesh.data.vertices[vert_index].co, uv, color)
                
        self.length = len(self.data)
        return self
    
    def to_array(self):
        return [d.to_array() for d in self.data]
    
    def write(self, buffer, cursor, index_buffer):
        if not index_buffer.offset:
            raise AttributeError(index_buffer, "Index buffer must be written before vertex buffer")
        
        vert_buffer_addr = cursor
        for vert in self.data:
            cursor = vert.write(buffer, cursor)
        
        #we write the references within index buffer to this vert buffer
        for i, chunk in enumerate(index_buffer.data):
            if chunk.type == 1:
                writeUInt32BE(buffer, vert_buffer_addr + chunk.start * 16, index_buffer.offset + i * 8 + 4)
            
        return cursor
    
class VisualsIndexChunk1(DataStruct):
    # http://n64devkit.square7.ch/n64man/gsp/gSPVertex.htm
    def __init__(self, parent, model, type):
        super().__init__('>BBBBI')
        
        self.parent = parent
        self.model = model
        self.type = type
        self.unk1 = 0
        self.unk2 = 0
        self.start = 0 #we'll write this value in VisualsVertexBuffer.write()
        self.max = 0 #we'll set this in VisualsIndexBuffer.unmake()
        
    def read(self, buffer, cursor, vert_buffer_addr):
        self.type, self.unk1, self.unk2, self.max, start = struct.unpack_from(self.format_string, buffer, cursor)
        self.start = round((start - vert_buffer_addr)/16)
        return cursor + self.size
    
    def to_array(self):
        return [self.type, self.unk1, self.unk2, self.max, self.start]
    
    def write(self, buffer, cursor):
        self.model.highlight(cursor + 4)
        struct.pack_into(self.format_string, buffer, cursor, self.type, self.unk1, self.unk2, self.max*2, self.start)
        return cursor + self.size
      
class VisualsIndexChunk3(DataStruct):
    # http://n64devkit.square7.ch/n64man/gsp/gSPCullDisplayList.htm
    def __init__(self, parent, model, type):
        super().__init__('>B6xB')
        
        self.parent = parent
        self.model = model
        self.type = type
        self.unk = None
        
    def to_array(self):
        return [self.type, self.unk]
    
    def read(self, buffer, cursor, vert_buffer_addr):
        self.type, self.unk = struct.unpack_from(self.format_string, buffer, cursor)
        
        return cursor + self.size
        
class VisualsIndexChunk5(DataStruct):
    # http://n64devkit.square7.ch/n64man/gsp/gSP1Triangle.htm
    def __init__(self, parent, model, type):
        super().__init__('>BBBB4x')
        
        self.parent = parent
        self.model = model
        self.type = type
        self.base = 0
        self.f1 = 0
        self.f2 = 0
        self.f3 = 0
        
    def from_array(self, data):
        self.f1, self.f2, self.f3 = data
        return self
    
    def to_array(self):
        return [self.f1, self.f2, self.f3]
        
    def min_index(self):
        return min(self.to_array())
    
    def max_index(self):
        return max(self.to_array())
    
    def adjust_indices(self, offset):
        self.f1 = self.f1 - offset
        self.f2 = self.f2 - offset
        self.f3 = self.f3 - offset
        
    def read(self, buffer, cursor, vert_buffer_addr):
        self.type, f1, f2, f3 = struct.unpack_from(self.format_string, buffer, cursor)
        self.f1 = round(f1/2)
        self.f2 = round(f2/2)
        self.f3 = round(f3/2)
        return cursor + self.size
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, self.type, *[(i-self.base)*2 for i in self.to_array()])
        return cursor + self.size
        
class VisualsIndexChunk6(DataStruct):
    # http://n64devkit.square7.ch/n64man/gsp/gSP2Triangles.htm
    def __init__(self, parent, model, type):
        super().__init__('>BBBBxBBB')
        
        self.parent = parent
        self.model = model
        self.type = type
        self.base = 0
        self.f1 = 0
        self.f2 = 0
        self.f3 = 0
        self.f4 = 0
        self.f5 = 0
        self.f6 = 0
    
    def from_array(self, data):
        self.f1, self.f2, self.f3, self.f4, self.f5, self.f6 = data
        return self
    
    def to_array(self):
        return [self.f1, self.f2, self.f3, self.f4, self.f5, self.f6]
    
    def min_index(self):
        return min(self.to_array())
    
    def max_index(self):
        return max(self.to_array())
        
    def read(self, buffer, cursor, vert_buffer_addr):
        self.type, f1, f2, f3, f4, f5, f6 = struct.unpack_from(self.format_string, buffer, cursor)
        self.f1 = round(f1/2)
        self.f2 = round(f2/2)
        self.f3 = round(f3/2)
        self.f4 = round(f4/2)
        self.f5 = round(f5/2)
        self.f6 = round(f6/2)
        return cursor + self.size
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, self.type, *[(i-self.base)*2 for i in self.to_array()])
        return cursor + self.size
            
class VisualsIndexBuffer():
    def __init__(self, parent, model):
        self.parent = parent
        self.model = model
        self.offset = 0
        self.data = []
        self.map = {
            1: VisualsIndexChunk1,
            3: VisualsIndexChunk3,
            5: VisualsIndexChunk5,
            6: VisualsIndexChunk6,
        }
    def read(self, buffer, cursor, vert_buffer_addr):
        chunk_type = readUInt8(buffer, cursor)
        
        while(chunk_type != 223):
            chunk_class = self.map.get(chunk_type)
            if chunk_class is None:
                raise ValueError(f"Invalid index chunk type {chunk_type}")
            chunk = chunk_class(self, self.model, chunk_class)
            chunk.read(buffer, cursor, vert_buffer_addr)
            self.data.append(chunk)
            cursor += 8
            chunk_type = readUInt8(buffer, cursor)
            
        return self
            
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
    
    def to_array(self):
        return [d.to_array() for d in self.data]
    
    def unmake(self, faces):
        #grab the base index buffer data from mesh.data.polygons and construct initial chunk list
        
        index_buffer = []
        while len(faces) > 1:
            chunk_type = 6
            chunk_class = self.map.get(chunk_type)
            chunk = chunk_class(self, self.model, chunk_type)
            chunk.from_array([f for face in faces[:2] for f in face])
            index_buffer.append(chunk)
            faces = faces[2:]
                
        #push the last chunk if there is one
        if len(faces):
            index_buffer.append(VisualsIndexChunk5(self, self.model, 5).from_array(faces[0]))    
        #partition chunk list
        partitions = []
        partition = []
        for chunk in index_buffer:
            min_index = chunk.min_index()
            if len(partition):
                min_index = min([chunk.min_index() for chunk in partition])
            max_index = chunk.max_index()
            if max_index - min_index > 40:
                partition_push = partition[:]
                partitions.append(partition_push)
                partition = []
            partition.append(chunk)
        partitions.append(partition)
        #add each partition and chunk1 to reset base for each one
        for partition in partitions:
            min_index = min([chunk.min_index() for chunk in partition]) 
            max_index = max([chunk.max_index() for chunk in partition])
            index_range = max_index - min_index
            chunk1 = VisualsIndexChunk1(self, self.model, 1)
            chunk1.start = min_index
            chunk1.max = index_range + 1
            self.data.append(chunk1)
            for chunk in partition:
                chunk.base = min_index
                self.data.append(chunk)
        
        return self

    def write(self, buffer, cursor):
        self.offset = cursor
        for chunk in self.data:
            cursor = chunk.write(buffer, cursor)
            
        #write end chunk
        writeUInt8(buffer, 223, cursor)
        return cursor + 8
    
class MaterialTextureChunk(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>4H4x2H')
        
        self.parent = parent
        self.data = []
        self.unk0 = 0 #sets uv mirroring
        self.unk1 = 0
        self.unk2 = 0
        self.unk3 = 0
        self.unk4 = 0
        self.unk5 = 0
        self.model = model
        
    def read(self, buffer, cursor):
        self.unk0, self.unk1, self.unk2, self.unk3, self.unk4, self.unk5 = struct.unpack_from(self.format_string, buffer, cursor)
        
    def unmake(self, texture):
        return self
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, self.unk0, self.unk1, self.unk2, self.unk3, self.unk4, self.unk5)
        return cursor + self.size
    
class MaterialTexture(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>I2H4x8H6I4xHH4x')
        
        self.parent = parent
        self.model = model
        self.id = None
        self.unk0 = 0 #0, 1, 65, 73 
        self.format = 0
        self.unk4 = 0 #0, 4
        self.width = 0
        self.height = 0
        self.unk7 = 0
        self.unk8 = 0
        self.chunks = []
        self.unk9 = 2560 #this is a required value
        self.tex_index = 0
        
    def read(self, buffer, cursor):
        unk_pointers = []
        self.id = cursor
        self.unk0, unk1, unk3, self.format, self.unk4, self.width, self.height, unk5, unk6, self.unk7, self.unk8, *unk_pointers, self.unk9, self.tex_index = struct.unpack_from(self.format_string, buffer, cursor)
        for pointer in unk_pointers:
            if pointer:
                chunk = MaterialTextureChunk(self, self.model)
                chunk.read(buffer, pointer)
                self.chunks.append(chunk)
            
    def make(self):
        if self.tex_index == 65535:
            return
        textureblock = self.model.modelblock.textureblock
        self.texture = Texture(self.tex_index, self.format, self.width, self.height)
        pixel_buffer, palette_buffer = textureblock.fetch(self.tex_index)
        self.texture.read(pixel_buffer, palette_buffer)
        return self.texture.make()
    
    def unmake(self, image):
        if image.name == '448F972_c.png' or image.name == '31A2D889_c.png':
            print('GOT IT', image.name)
            image['format'] = 3
        if image is None:
            return self
        self.width, self.height = image.size
        if 'id' in image and False:
            self.tex_index = int(image['id'])
        else:
            self.format = 513
            self.tex_index = self.model.texture_index
            self.id = self.model.texture_index
            self.model.texture_index += 1
            
        self.unk1 = min(self.width * 4, 65535)
        self.unk2 = min(self.height * 4, 65535)
        self.format = int(image['format']) if 'format' in image else 513
        self.unk5 = min(65535, self.width * 512)
        self.unk6 = min(65535, self.height * 512)
        self.chunks.append(MaterialTextureChunk(self, self.model).unmake(self)) #this struct is required
        
        if image.name in self.model.written_textures:
            self.tex_index = self.model.written_textures[image.name]
            self.id = self.model.written_textures[image.name]
        elif self.model.texture_export:
            texture = Texture(self.id).unmake(image)
            pixel_buffer = texture.pixels.write()
            palette_buffer = texture.palette.write()
            self.model.textureblock.inject([pixel_buffer, palette_buffer], self.id)
            self.model.written_textures[image.name] = self.tex_index
        
        return self
    
    def write(self, buffer, cursor):
        chunk_addr = cursor + 28
        self.model.highlight(cursor + 56)
        struct.pack_into(self.format_string, buffer, cursor, self.unk0, min(self.width*4, 32768), min(self.height*4, 32768), self.format, self.unk4, self.width, self.height, min(self.width*512, 32768), min(self.height*512, 32768), self.unk7, self.unk8, *[0, 0, 0, 0, 0, 0], self.unk9, self.tex_index)
        cursor += self.size
        
        for i, chunk in enumerate(self.chunks):
            self.model.highlight(chunk_addr + i * 4)
            writeUInt32BE(buffer, cursor, chunk_addr + i*4)
            cursor = chunk.write(buffer, cursor)
        return cursor
        
class MaterialShader(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>IH4IH2IH4x7H')
        
        self.parent = parent
        # this whole struct can be 0
        # notes from tilman https://discord.com/channels/441839750555369474/441842584592056320/1222313834425876502
        self.model = model
        self.unk1 = 0
        self.unk2 = 2 # maybe "combiner cycle type"
        # combine mode: http://n64devkit.square7.ch/n64man/gdp/gDPSetCombineLERP.htm
        self.color_combine_mode_cycle1 = 0# 0b1000111110000010000011111
        self.alpha_combine_mode_cycle1 = 0#0b111000001110000011100000100
        self.color_combine_mode_cycle2 = 0#0b11111000111110001111100000000
        self.alpha_combine_mode_cycle2 = 0#0b111000001110000011100000000
        self.unk5 = 0
        # render mode: http://n64devkit.square7.ch/n64man/gdp/gDPSetRenderMode.htm
        self.render_mode_1 = 0# 0b11001000000000000000000000000000
        self.render_mode_2 = 0b10000 # 0b100010010000000111000
        self.unk8 = 0
        self.color = RGBA4Bytes()
        self.unk = []
    def read(self, buffer, cursor):
        self.unk1, self.unk2, self.color_combine_mode_cycle1, self.alpha_combine_mode_cycle1, self.color_combine_mode_cycle2, self.alpha_combine_mode_cycle2, self.unk5, self.render_mode_1, self.render_mode_2, self.unk8, *self.unk = struct.unpack_from(self.format_string, buffer, cursor)
        self.color.read(buffer, cursor + 34)
    
    def make(self, material):
        if self.unk1 == 8:
            material.show_transparent_back = True
            material.blend_method = 'BLEND'
    
    def unmake(self, material):
        if material.blend_method == 'BLEND':
            self.unk1 = 8
            self.render_mode_2 =  0b000000000100000011000   #0b100000100100101111001
            #use alpha bit                   100000000000
            #goes from alpha blend to alpha clip    10000
        if hasattr(self.parent, 'skybox') and self.parent.skybox:
            self.render_mode_1 = 0b1100000010000010000000001000 #fixes small stitching issues
            self.render_mode_2 = 0b11000000100010000000001000
            
        return self
    
    def to_array(self):
        return [self.unk1, self.unk2, self.color_combine_mode_cycle1, self.alpha_combine_mode_cycle1, self.color_combine_mode_cycle2, self.alpha_combine_mode_cycle2, self.unk5, self.render_mode_1, self.render_mode_2, self.unk8, self.color.to_array(), self.unk]
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, self.unk1, self.unk2, self.color_combine_mode_cycle1, self.alpha_combine_mode_cycle1, self.color_combine_mode_cycle2, self.alpha_combine_mode_cycle2, self.unk5, self.render_mode_1, self.render_mode_2, self.unk8, 0, 0, 0, 0, 0, 0, 0)
        self.color.write(buffer, cursor + 34)
        return cursor + self.size
    
class Material(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>I4xII')
        self.parent = parent
        self.id = None
        self.model = model
        self.format = 14
        #0000001   1   254 1 = lightmap
        #0000010   2   253 no apparent changes
        #0000100   4   251 
        #0001000   8   247 0 = double sided, 1 = single sided
        #0010000   16  239 1 = weird lighting
        #0100000   32  223 
        #1000000   64  191 1 =  breaking change

        #0000100 format 4 is only used for engine trail, binder, and flame effects
        #0000110 format 6 seems to indicate doublesidedness
        #0000111 format 7
        #0001100 format 12 is for any kind of skybox material
        #0001110 14/15/71 are used for a majority
        #0001111 15
        #1000110 70
        #1000111 71
        #0010111 23/31/87 are used exclusively with texture 35 possibly for sheen
        #0011111
        #1010111
        self.texture = None
        self.written = None
        self.shader = MaterialShader(self, self.model)
        
    def detect_skybox(self):
        
        parent = self.parent
        while parent is not None:
            if hasattr(parent, 'skybox'):
                self.skybox = True 
            parent = parent.parent
        
    def read(self, buffer, cursor):
        self.id = cursor
        self.format, texture_addr, shader_addr = struct.unpack_from(self.format_string, buffer, cursor)
        if texture_addr:
            if texture_addr in self.model.textures:
                self.texture = self.model.textures[texture_addr]
            else:
                self.model.textures[texture_addr] = MaterialTexture(self, self.model)
                self.model.textures[texture_addr].read(buffer, texture_addr)
                self.texture = self.model.textures[texture_addr]
            
        # there should always be a shader_addr
        assert shader_addr > 0, "Material should have shader"
        self.shader.read(buffer, shader_addr)
        
        self.detect_skybox()
        return self
        
    def make(self):
        mat_name = str(self.id)
        if (self.texture is not None):
            material = bpy.data.materials.get(mat_name)
            if material is not None:
                return material
            
            material = bpy.data.materials.new(mat_name)
            material.use_nodes = True
            #material.blend_method = 'BLEND' #use for transparency
            material.blend_method = 'OPAQUE'
            
            self.shader.make(material)
            
            if self.texture.format == 3:
                material.blend_method = 'BLEND'
            if (self.format & 8):
                material.use_backface_culling = True
            
            node_1 = material.node_tree.nodes.new("ShaderNodeTexImage")
            node_2 = material.node_tree.nodes.new("ShaderNodeVertexColor")
            node_3 = material.node_tree.nodes.new("ShaderNodeMixRGB")
            node_3.blend_type = 'MULTIPLY'
            node_3.inputs['Fac'].default_value = 1
            material.node_tree.links.new(node_1.outputs["Color"], node_3.inputs["Color1"])
            material.node_tree.links.new(node_2.outputs["Color"], node_3.inputs["Color2"])
            material.node_tree.links.new(node_3.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Base Color"])
            material.node_tree.links.new(node_1.outputs["Alpha"], material.node_tree.nodes['Principled BSDF'].inputs["Alpha"])
            material.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0
            image = str(self.texture.tex_index)
            if image in ["1167", "1077", "1461", "1596"]: #probably shouldn't do it this way; TODO find specific tag
                material.blend_method = 'BLEND'
                material.node_tree.links.new(node_1.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Alpha"])
            
            if self.format in [31, 15, 7]:
                material.node_tree.links.new(node_2.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Normal"])
                material.node_tree.links.new(node_1.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Base Color"])
            
            chunk_tag = self.texture.chunks[0].unk1 if len(self.texture.chunks) else 0
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
            return material
        else:
            material = bpy.data.materials.new(mat_name)
            material.use_nodes = True
            # material.node_tree.nodes["Principled BSDF"].inputs[5].default_value = 0
            # colors = [0, 0, 0, 0] if self.unk is None else self.unk.color
            # material.node_tree.nodes["Principled BSDF"].inputs[0].default_value = [c/255 for c in colors]
            node_1 = material.node_tree.nodes.new("ShaderNodeVertexColor")
            material.node_tree.links.new(node_1.outputs["Color"], material.node_tree.nodes['Principled BSDF'].inputs["Base Color"])
            return material
    
    def unmake(self, mesh):
        #find if the mesh has an image texture
        self.detect_skybox()
        material_name = ""
        for slot in mesh.material_slots:
            material = slot.material
            if material:
                material_name = material.name #.split(".")[0]
                self.id = material_name
                if material_name in self.model.materials:
                    return self.model.materials[material_name]
                
                if material.use_backface_culling == False:
                    self.format &= 0b11110111
                
                self.shader.unmake(material)
                
                for node in material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE':
                        self.texture = MaterialTexture(self, self.model).unmake(node.image)
                break
        self.model.materials[material_name] = self
        
        return self.model.materials[material_name]
        
    def write(self, buffer, cursor):
        material_start = cursor
        self.written = cursor
        cursor += self.size
        tex_addr = 0
        if self.texture:
            self.model.highlight(material_start + 8)
            tex_addr = cursor
            cursor = self.texture.write(buffer, cursor)
        
        self.model.highlight(material_start + 12)
        shader_addr = cursor
        cursor = self.shader.write(buffer, cursor)
        
        struct.pack_into(self.format_string, buffer, material_start, self.format, tex_addr, shader_addr)
        return cursor
    
class MeshBoundingBox(DataStruct):
    """Defines the minimum and maximum bounds of a mesh"""
    
    #only need to calculate bounding box for export workflow
    def __init__(self, parent, model):
        super().__init__('>6f')
        
        self.parent = parent
        self.model = model
        self.min_x = 0
        self.min_y = 0
        self.min_z = 0
        self.max_x = 0
        self.max_y = 0
        self.max_z = 0
    def unmake(self, mesh):
        verts = []
        if mesh is None:
            return self
        
        
        if mesh.collision_vert_buffer:
            verts.extend(mesh.collision_vert_buffer.make())
            
        # on meshes with both collision and visuals, collision takes precedence
        if mesh.visuals_vert_buffer and len(verts) == 0:
            verts.extend(mesh.visuals_vert_buffer.make())
        
        if len(verts) == 0:
            return self
        self.min_x = min([vert[0] for vert in verts])
        self.min_y = min([vert[1] for vert in verts])
        self.min_z = min([vert[2] for vert in verts])
        self.max_x = max([vert[0] for vert in verts])
        self.max_y = max([vert[1] for vert in verts])
        self.max_z = max([vert[2] for vert in verts])
        return self
    def to_array(self):
        return [self.min_x, self.min_y, self.min_z, self.max_x, self.max_y, self.max_z]
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, *self.to_array())
        return self.size + cursor
    
class MeshGroupBoundingBox(MeshBoundingBox):
    def unmake(self, meshgroup):
        bb = []
        for child in meshgroup.children:
            bb.append(child.bounding_box.to_array())
        self.min_x = min([b[0] for b in bb])
        self.min_y = min([b[1] for b in bb])
        self.min_z = min([b[2] for b in bb])
        self.max_x = max([b[3] for b in bb])
        self.max_y = max([b[4] for b in bb])
        self.max_z = max([b[5] for b in bb])
        return self
    
class Mesh(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>2I6f2H5I2H2xH')
        
        self.parent = parent
        self.model = model
        
        self.material = None
        self.collision_tags = None
        self.bounding_box = None
        self.strip_count = 0
        self.strip_size = 3
        self.vert_strips = None
        self.group_parent_id = 0
        self.collision_vert_buffer = None
        self.visuals_index_buffer = None
        self.visuals_vert_buffer = None
        self.group_count = 0
        
    def has_visuals(self):
        return self.visuals_vert_buffer is not None and self.visuals_index_buffer is not None
    
    def has_collision(self):
        return self.collision_vert_buffer is not None and self.collision_vert_buffer.length >= 3
    
    def read(self, buffer, cursor):
        self.id = cursor
        mat_addr, collision_tags_addr, min_x, min_y, min_z, max_x, max_y, max_z, self.strip_count, self.strip_size, vert_strips_addr, self.group_parent_id, collision_vert_buffer_addr, visuals_index_buffer_addr, visuals_vert_buffer_addr, collision_vert_count, visuals_vert_count, self.group_count = struct.unpack_from(self.format_string, buffer, cursor)
        
        
        if mat_addr:
            if mat_addr not in self.model.materials:
                self.model.materials[mat_addr] = Material(self, self.model).read(buffer, mat_addr)
            self.material = self.model.materials[mat_addr]
                
        if collision_tags_addr:
            self.collision_tags = CollisionTags(self, self.model).read(buffer, collision_tags_addr)
                
        #we can ignore saving bounding box data (min_x, min_y...) upon read, we'll just calculate it during unmake
                    
        if vert_strips_addr:
            self.vert_strips = CollisionVertStrips(self, self.model, self.strip_count).read(buffer, vert_strips_addr)
                    
        if visuals_index_buffer_addr:
            self.visuals_index_buffer = VisualsIndexBuffer(self, self.model).read(buffer, visuals_index_buffer_addr, visuals_vert_buffer_addr)
        
        if visuals_vert_buffer_addr:
            self.visuals_vert_buffer = VisualsVertBuffer(self, self.model, visuals_vert_count).read(buffer, visuals_vert_buffer_addr)
            
        if collision_vert_buffer_addr:
            self.collision_vert_buffer = CollisionVertBuffer(self, self.model, collision_vert_count).read(buffer, collision_vert_buffer_addr)
                    
        return self
    
    def make(self, parent, collection):
        if self.has_collision():
            verts = self.collision_vert_buffer.make()
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
                        elif (s % 2) == 0:
                            faces.append( [start+s, start+s+1, start+s+3])
                        else:
                            faces.append( [start+s, start+s+1, start+s+2])
                    start += strip
            mesh_name = '{:07d}'.format(self.id) + "_" + "collision"
            mesh = bpy.data.meshes.new(mesh_name)
            obj = bpy.data.objects.new(mesh_name, mesh)
            
            obj['type'] = 'COL'   
            obj['id'] = self.id
            obj.scale = [self.model.scale, self.model.scale, self.model.scale]

            collection.objects.link(obj)
            mesh.from_pydata(verts, edges, faces)
            obj.parent = parent

            if(self.collision_tags is not None): 
                self.collision_tags.make(obj)
                
        if self.has_visuals():
            
            verts = self.visuals_vert_buffer.make()
           
            edges = []
            faces = self.visuals_index_buffer.make()
            mesh_name = '{:07d}'.format(self.id) + "_" + "visuals"
            mesh = bpy.data.meshes.new(mesh_name)
            obj = bpy.data.objects.new(mesh_name, mesh)
            obj['type'] = 'VIS'
            obj['id'] = self.id
            obj.scale = [self.model.scale, self.model.scale, self.model.scale]

            collection.objects.link(obj)
            mesh.from_pydata(verts, edges, faces)
            mesh.validate() #clean_customdata=False
            obj.parent = parent
            
            
            if self.material:
                mat = self.material.make()
                mesh.materials.append(mat)
            
            
            #set vector colors / uv coords
            uv_layer = mesh.uv_layers.new(name = 'uv')
            color_layer = mesh.vertex_colors.new(name = 'colors') #color layer has to come after uv_layer
            # no idea why but 4.0 requires I do this:
            uv_layer = obj.data.uv_layers.active.data
            color_layer = obj.data.vertex_colors.active.data                                           
            
            for poly in mesh.polygons:
                for p in range(len(poly.vertices)):
                    v = self.visuals_vert_buffer.data[poly.vertices[p]]
                    uv_layer[poly.loop_indices[p]].uv = [u/4096 for u in v.uv]
                    color_layer[poly.loop_indices[p]].color = [a/255 for a in v.color.to_array()]
    
    def unmake(self, node):
        self.id = node.name
        if 'type' not in node:
            node['type'] = 'VISCOL'
        
        print(self.id, node['type'])    
        
        if 'VIS' in node['type']:
            self.material = Material(self, self.model).unmake(node)
            self.visuals_vert_buffer = VisualsVertBuffer(self, self.model).unmake(node)
            verts = self.visuals_vert_buffer.data
            faces = [[v for v in face.vertices] for face in node.data.polygons]            
            
            #tesselate faces
            t_faces = []
            for face in faces:
                if len(face) > 4:
                    raise ValueError("Polygon with more than 4 vertices detected")
                if len(face) == 4:
                    t_faces.append([face[0], face[1], face[2]])
                    t_faces.append([face[0], face[2], face[3]])
                else:
                    t_faces.append(face)
            faces = t_faces
            
            #replace each index with its vert
            faces = [[verts[i] for i in face] for face in faces]
            
            #reorder faces to maximize shared edges
            ordered_faces = []
            ordered_faces.append(faces.pop(0))
            while len(faces):
                last_face = ordered_faces[-1]
                shared = None
                for f, face in enumerate(faces):
                    if len([i for i in face if i in last_face]) > 1:
                        shared = f
                        break
                if shared != None:
                    ordered_faces.append(faces.pop(shared))
                else:
                    ordered_faces.append(faces.pop(0))
                
            #relist vertices so indices aren't too far apart    
            new_verts = []
            new_faces = []
            for face in ordered_faces:
                new_face = []
                for vert in face:
                    current_index = len(new_verts)
                    index = -1
                    #find last instance of vert
                    try:
                        index = current_index - new_verts[::-1].index(vert) - 1
                    except ValueError:
                        index = -1
                    
                    if index > -1 and current_index - index < 64:
                        new_face.append(index)
                    else: 
                        new_verts.append(vert)
                        new_face.append(current_index)
                        
                new_faces.append(new_face)

            #TODO check if node has vertex group
            if False:
                self.group_parent = None
                self.group_count = None
                
            self.visuals_vert_buffer.data = new_verts
            self.visuals_index_buffer = VisualsIndexBuffer(self, self.model).unmake(new_faces)
                
        if 'COL' in node['type']:
            self.collision_tags = CollisionTags(self, self.model).unmake(node)
            self.collision_vert_buffer = CollisionVertBuffer(self, self.model).unmake(node)
            self.vert_strips = CollisionVertStrips(self, self.model).unmake(node)
            
            faces = [[v for v in face.vertices] for face in node.data.polygons]            
            verts = self.collision_vert_buffer.data
            
            #tesselate/validate faces
            t_faces = []
            for face in faces:
                for vert in face:
                    if len([v for v in face if v == vert]) > 1:
                        print("DOUBLE VERT")
                if len(face) > 4:
                    raise ValueError("Polygon with more than 4 vertices detected")
                if len(face) == 4:
                    t_faces.append([face[0], face[1], face[2]])
                    t_faces.append([face[0], face[2], face[3]])
                else:
                    t_faces.append(face)
            faces = t_faces
            
            #replace each index with its vert
            faces = [[verts[i] for i in face] for face in faces]
            
            def unshared_vert(list1, list2):
                for i, index in enumerate(list1):
                    if index not in list2:
                        return i
                return None
            
            def get_edge(list1, list2):
                nonshared = unshared_vert(list1, list2)
                if nonshared is None:
                    return None
                    
                edge = list1[:]
                edge.pop(nonshared)
                
                if nonshared == 1:
                    edge = edge[::-1]
                    
                return edge

            
            #restrip mesh
            strips = []
            new_verts = []
            strip = []
            strip.append(faces.pop(0))
            strip_verts = []
            while len(faces):
                last_face = strip[-1]
                shared = None
                
                #search for a suitable adjacent face to continue strip
                for f, face in enumerate(faces):
                    #ignore faces with less than 2 shared verts
                    if len([i for i in face if i in last_face]) < 2:
                        continue
                    
                    #not only must the faces share an edge, the edge must run opposite to ensure they have same normals
                    edge1 = get_edge(last_face, face)
                    edge2 = get_edge(face, last_face) 
                    if edge1 is None or edge2 is None:
                        continue
                    if edge1 != edge2[::-1]:
                        continue
                    
                    if len(strip_verts) == 0:
                        unshared = unshared_vert(last_face, face)
                        strip_verts.append(last_face[unshared])
                        strip_verts.extend(edge1)
                        
                    #additionally, we need to check that the shared edge is opposite the third to last vert
                    if strip_verts[-3] in face:  
                        continue
                    
                    next_unshared = unshared_vert(face, last_face)
                    strip_verts.append(face[next_unshared])
                    shared = f
                    break
                        
                if shared is not None:
                    strip.append(faces.pop(shared))
                else:
                    if len(strip_verts) == 0:
                        strip_verts.extend(last_face)
                    strips.append(strip[:])
                    new_verts.extend(strip_verts[:])
                    strip_verts = []
                    strip = []
                    strip.append(faces.pop(0))
                    
            if len(strip):
                new_verts.extend(strip_verts[:])
                strips.append(strip)
                new_verts.extend([s for s in strip[0]])
            
            strip_list = [2+ len(strip) for strip in strips]
            self.collision_vert_buffer.data = new_verts
            self.collision_vert_buffer.format_string = f'>{len(new_verts)*3}h'
            self.collision_vert_buffer.size = struct.calcsize(f'>{len(new_verts)*3}h')
            self.strip_count = len(strip_list)
            self.vert_strips.strip_count = len(strip_list)
            self.vert_strips.data = strip_list
            self.vert_strips.format_string = f'>{len(strip_list)}I'
            self.vert_strips.size = struct.calcsize(f'>{len(strip_list)}I')
            self.vert_strips.strip_size = 5
            self.vert_strips.include_buffer = True
            
        self.bounding_box = MeshBoundingBox(self, self.model).unmake(self)
        return self
    
    def write(self, buffer, cursor):
        print('writing mesh', self.id)
        #initialize addresses
        mat_addr = 0
        collision_tags_addr = 0
        vert_strips_addr = 0
        collision_vert_buffer_addr = 0
        visuals_index_buffer_addr = 0
        visuals_vert_buffer_addr = 0
        collision_vert_count = 0
        visuals_vert_count = 0
        strip_count = 0
        strip_size = 3
        #save mesh location and move cursor to end of mesh header (that we haven't written yet)
        mesh_start = cursor
        cursor += self.size
        
        #group parent
        self.model.highlight(mesh_start + 40)
        
        #write each section
        if self.vert_strips:
            
            strip_count = self.vert_strips.strip_count
            strip_size = self.vert_strips.strip_size
            if self.vert_strips.include_buffer:
                self.model.highlight(mesh_start + 36)
                vert_strips_addr = cursor
                cursor = self.vert_strips.write(buffer, cursor)
                
        if self.collision_vert_buffer:
            self.model.highlight(mesh_start + 44)
            collision_vert_buffer_addr = cursor
            cursor = self.collision_vert_buffer.write(buffer, cursor)
            collision_vert_count = len(self.collision_vert_buffer.data)
            if cursor % 4 is not 0:
                cursor += cursor % 4
                
        if self.material:
            self.model.highlight(mesh_start)
            if self.material.written:
                mat_addr = self.material.written
            else:
                mat_addr = cursor
                cursor = self.material.write(buffer, cursor)
            
        if self.visuals_index_buffer:
            self.model.highlight(mesh_start + 48)
            cursor = (cursor + 0x7) & 0xFFFFFFF8 #this section must be aligned to an address divisible by 8
            visuals_index_buffer_addr = cursor
            cursor = self.visuals_index_buffer.write(buffer, cursor)
            
            
        if self.visuals_vert_buffer:
            self.model.highlight(mesh_start + 52)
            visuals_vert_buffer_addr = cursor
            cursor = self.visuals_vert_buffer.write(buffer, cursor, self.visuals_index_buffer)
            visuals_vert_count = len(self.visuals_vert_buffer.data)
            
        if self.collision_tags:
            self.model.highlight(mesh_start + 4)
            collision_tags_addr = cursor
            cursor = self.collision_tags.write(buffer, cursor)
        
        #finally, write mesh header
        struct.pack_into(self.format_string, buffer, mesh_start, mat_addr, collision_tags_addr, *self.bounding_box.to_array(), strip_count, strip_size, vert_strips_addr, self.group_parent_id, collision_vert_buffer_addr, visuals_index_buffer_addr, visuals_vert_buffer_addr, collision_vert_count, visuals_vert_count, self.group_count)
        return cursor
            
def create_node(node_type, parent, model):
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
        return node_class(parent, model, node_type)
    else:
        raise ValueError(f"Invalid node type {node_type}")
    
class Node(DataStruct):
    
    def __init__(self, parent, model, type):
        super().__init__('>7I')
        self.parent = parent
        self.type = type
        self.id = None
        self.head = []
        self.children = []
        self.AltN = []
        self.header = []
        self.node_type = type
        self.vis_flags = 0b11111111111111111111111111111111
        self.col_flags = 0b11111111111111111111111111111111
        self.unk1 = 0
        self.unk2 = 0
        self.model = model
        self.child_count = 0
        self.child_start = None
        
    def read(self, buffer, cursor):
        self.id = cursor
        self.node_type, self.vis_flags, self.col_flags, self.unk1, self.unk2, self.child_count, self.child_start = struct.unpack_from(self.format_string, buffer, cursor)
        
        if self.model.AltN and cursor in self.model.AltN:
            self.AltN = [i for i, h in enumerate(self.model.AltN) if h == cursor]
        
        if cursor in self.model.header.offsets:
            self.header = [i for i, h in enumerate(self.model.header.offsets) if h == cursor]
            if self.model.ext == 'Trak' and 2 in self.header:
                self.skybox = True

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
                self.children.append(Mesh(self, self.model).read(buffer, child_address))
            else:
                node = create_node(readUInt32BE(buffer, child_address), self, self.model)
                self.children.append(node.read(buffer, child_address))
 
        return self
    
    def make(self, parent=None, collection = None):
        name = '{:07d}'.format(self.id)
        
        if self.model.ext == 'Trak':
            if 0 in self.header:
                track_collection = bpy.data.collections.new('Track')
                collection.children.link(track_collection)
                collection = track_collection
            elif 2 in self.header:
                skybox_collection = bpy.data.collections.new('Skybox')
                collection.children.link(skybox_collection)
                collection = skybox_collection
        
        if self.type in [53349, 53350]:
            new_node = bpy.data.objects.new(name, None)
            collection.objects.link(new_node)
            #new_empty.empty_display_size = 2
            if self.unk1 &  1048576 != 0:
                new_node.empty_display_type = 'ARROWS'
                new_node.empty_display_size = 0.5
                
            elif self.unk1 & 524288 != 0:
                new_node.empty_display_type = 'CIRCLE'
                new_node.empty_display_size = 0.5
            else:
                new_node.empty_display_type = 'PLAIN_AXES'

                 
        else:
            new_node = bpy.data.objects.new(name, None)
            #new_empty.empty_display_type = 'PLAIN_AXES'
            new_node.empty_display_size = 0
            collection.objects.link(new_node)

        #set group tags
        new_node['node_type'] = self.node_type
        new_node['vis_flags'] = str(self.vis_flags)
        new_node['col_flags'] = str(self.col_flags)
        new_node['unk1'] = self.unk1
        new_node['unk2'] = self.unk2
            
        #assign parent
        if parent is not None:
            new_node.parent = parent
                
        
        for node in self.children :
            if not isinstance(node, dict):
                node.make(new_node, collection)
            
        if self.id in self.model.header.offsets:
            new_node['header'] = [i for i, e in enumerate(self.model.header.offsets) if e == self.id]
            
        return new_node
    def unmake(self, node):
        self.id = node.name
        self.node_type = node['node_type']
        self.vis_flags = int(node['vis_flags'])
        self.col_flags = int(node['col_flags'])
        self.unk1 =  node['unk1']
        self.unk2 = node['unk2']
        if 'header' in node:
            self.header = node['header']
        
        if self.model.ext == 'Trak' and 2 in self.header:
            self.skybox = True
        
        if self.node_type == 12388:
            for child in node.children:
                self.children.append(Mesh(self, self.model).unmake(child))
        else:
            for child in node.children:
                n = create_node(child['node_type'], self, self.model)
                self.children.append(n.unmake(child))
        
        return self
    
    def write(self, buffer, cursor):
        #write references to this node in the model header
        for i in self.header:
            struct.pack_into(f">{len(self.header)}I", buffer, 4 + 4*i, *[cursor]*len(self.header))
            
        #check if this node has collision or visuals
        has_vis = False
        has_col = False
        if self.type == 12388 and len(self.children):
            for mesh in self.children:
                if mesh.has_collision():
                    has_col = True
                if mesh.has_visuals():
                    has_vis = True
            if not has_col:
                self.col_flags &= 0b11111111111111111111111111111001
            if not has_vis:
                self.vis_flags &= 0b11111111111111111111111111111011
            
        struct.pack_into(self.format_string, buffer, cursor, self.node_type, self.vis_flags, self.col_flags, self.unk1, self.unk2, 0, 0)
        return cursor + self.size
    
    def write_children(self, buffer, cursor, child_data_addr):
        num_children = len(self.children)
        
        
        
        #write child count and child list pointer
        writeUInt32BE(buffer, num_children, child_data_addr)
        self.model.highlight(child_data_addr + 4)
        
        
        if not len(self.children):
            return cursor
        
        writeUInt32BE(buffer, cursor, child_data_addr + 4)
        
        #write child ptr list
        child_list_addr = cursor
        cursor += num_children * 4
        
        #write children        
        for index, child in enumerate(self.children):
            
            child_ptr = child_list_addr + 4*index
            self.model.highlight(child_ptr)
            writeUInt32BE(buffer, cursor, child_ptr)
            self.model.highlight(child_ptr)
            cursor = child.write(buffer, cursor)
            
        return cursor

class MeshGroup12388(Node):
    
    def __init__(self, parent, model, type):
        super().__init__( parent,model, type)
        self.parent = parent
        self.bounding_box = None
        
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        return self
    
    def make(self, parent = None, collection = None):
        return super().make(parent, collection)
    
    def unmake(self, node):
        super().unmake(node)
        self.bounding_box = MeshGroupBoundingBox(self, self.model).unmake(self)
        return self
    
    def calc_bounding(self):
        self.bounding_box = MeshGroupBoundingBox(self, self.model).unmake(self)
        
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_info_start = cursor - 8
        cursor = self.bounding_box.write(buffer, cursor)
        cursor += 8
        cursor = super().write_children(buffer, cursor, child_info_start)
        return cursor
        
class Group53348(Node):
    def __init__(self, parent, model, type):
        super().__init__(parent, model, type)
        self.parent = parent
        self.matrix = FloatMatrix()
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.matrix = FloatMatrix(struct.unpack_from(">12f", buffer, cursor+28))
        return self
    def make(self, parent = None, collection = None):
        empty = super().make(parent, collection)
        empty.matrix_world = self.matrix.get()
        return empty
    def unmake(self, node):
        return super().unmake(node)
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_info_start = cursor - 8
        cursor = super().write_children(buffer, cursor, child_info_start)
        return cursor
        
class Group53349(Node):
    def __init__(self, parent, model, type):
        super().__init__(parent, model, type)
        self.parent = parent
        self.matrix = FloatMatrix()
        self.matrix.data[0].data[0] = 1.0
        self.matrix.data[1].data[1] = 1.0
        self.matrix.data[2].data[2] = 1.0
        self.bonus = FloatPosition()
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.matrix.read(buffer, cursor+28)
        self.bonus.read(buffer, cursor+76)
        return self
    def make(self, parent = None, collection = None):
        empty = super().make(parent, collection)
        if not isinstance(empty, bpy.types.Collection):
            empty.matrix_world = self.matrix.make(self.model.scale)
        
        empty['bonus'] = self.bonus.to_array()
        return empty
    def unmake(self, node):
        super().unmake(node)
        matrix = node.matrix_world
        #need to transpose the matrix
        matrix = list(map(list, zip(*matrix)))
        self.matrix.unmake(matrix, self.model.scale)
        if 'bonus' in node:
            self.bonus.from_array(node['bonus'])
        return self
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_data_start = cursor - 8
        cursor = self.matrix.write(buffer, cursor)
        cursor = self.bonus.write(buffer, cursor)
        cursor = super().write_children(buffer, cursor, child_data_start)
        return cursor
        
class Group53350(Node):
    # parents to camera
    def __init__(self, parent, model, type):
        super().__init__(parent, model, type)
        self.parent = parent
        self.unk1 = 65536
        self.unk2 = 0
        self.unk3 = 0
        self.unk4 = 1.0
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.unk1, self.unk2, self.unk3, self.unk4 = struct.unpack_from(">3if", buffer, cursor+28)
        return self
    def make(self, parent = None, collection = None):
        new_empty = super().make(parent, collection)
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
        return self
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_data_start = cursor - 8
        struct.pack_into('>3if', buffer, cursor, self.unk1, self.unk2, self.unk3, self.unk4)
        cursor += struct.calcsize('>3if')
        
        cursor = super().write_children(buffer, cursor, child_data_start)
        
        return cursor
  
class Group20580(Node):
    def __init__(self, parent, model, type):
        super().__init__(parent, model, type)
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        return self
    def make(self, parent = None, collection = None):
        return super().make(parent, collection)
    def unmake(self, node):
        return super().unmake(node)
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_data_start = cursor - 8
        cursor = super().write_children(buffer, cursor, child_data_start)
        return cursor
      
class Group20581(Node):
    def __init__(self, parent, model, type):
        super().__init__(parent, model, type)
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        return self
    def make(self, parent = None, collection = None):
        return super().make(parent, collection)
    def unmake(self, node):
        return super().unmake(node)
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_data_start = cursor - 8
        if len(self.children):
            cursor += 4
        cursor = super().write_children(buffer, cursor, child_data_start)
        return cursor
    
class Group20582(Node):
    def __init__(self, parent, model, type):
        super().__init__( parent,model, type)
        self.floats = []
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.floats = struct.unpack_from(">11f", buffer, cursor+28)
        return self
    def make(self, parent = None, collection = None):
        empty = super().make(parent, collection)
        empty['floats'] = self.floats
        return self
    def unmake(self, node):
        super().unmake(node)
        self.floats = node['floats']
        return self
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_data_start = cursor - 8
        struct.pack_into(">11f", buffer, cursor, *self.floats)
        cursor += self.size
        cursor = super().write_children(buffer, cursor, child_data_start)
        return cursor
      
class LStr(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>4x3f')
        
        self.parent = parent
        self.data = FloatPosition()
        self.model = model
    def read(self, buffer, cursor):
        x, y, z = struct.unpack_from(self.format_string, buffer, cursor)
        self.data.from_array([x, y , z])
        return self
    def make(self):
        light = bpy.data.lights.new(name = "lightstreak", type = 'POINT')
        light_object = bpy.data.objects.new(name = "lightstreak", object_data = light)
        self.model.collection.objects.link(light_object)
        light_object.location = (self.data.data[0]*self.model.scale, self.data.data[1]*self.model.scale, self.data.data[2]*self.model.scale)
        
    def unmake(self):
        return self
    def write(self, buffer, cursor):
        return cursor
        
class ModelData():
    def __init__(self, parent, model):
        self.parent = parent
        self.data = []
        self.model = model
    def read(self, buffer, cursor):
        size = readUInt32BE(buffer, cursor)
        cursor += 4
        i = 0
        while i < size:
            if readString(buffer, cursor) == 'LStr':
                self.data.append(LStr(self, self.model).read(buffer, cursor))
                cursor += 16
                i+=4
            else:
                self.data.append(readUInt32BE(buffer,cursor))
                cursor += 4
                i+=1
        return cursor
    def make(self):
        for d in self.data:
            d.make()
    def unmake(self):
        pass
    def write(self, buffer, cursor):
        
        return cursor
    
class Anim(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>244x3f2HI5f4I')
        
        self.parent = parent
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
    
class AnimList():
    def __init__(self, parent, model):
        self.parent = parent
        self.data = []
        self.model = model
    def read(self, buffer, cursor):
        anim = readUInt32BE(buffer, cursor)
        while anim:
            self.data.append(Anim(self, self.model).read(buffer, anim))
            cursor += 4
            anim = readUInt32BE(buffer, cursor)
        return cursor + 4
    def make(self):
        pass
    def unmake(self):
        pass
    def write(self, buffer, cursor):
        cursor = writeString(buffer, "Anim", cursor)
        for anim in self.data:
            self.model.highlight(cursor)
            cursor += 4
        self.model.highlight(cursor)
        return cursor + 4

class ModelHeader():
    def __init__(self, parent, model):
        self.parent = parent
        self.offsets = []
        self.model = model

    def read(self, buffer, cursor):
        self.model.ext = readString(buffer, cursor)
        if self.model.ext not in ['Podd', 'MAlt', 'Trak', 'Part', 'Modl', 'Pupp', 'Scen']:
            show_custom_popup(bpy.context, "Unrecognized Model Extension", f"This model extension was not recognized: {self.model.ext}")
            raise ValueError("Unexpected model extension", self.model.ext)
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
                self.model.Data = ModelData(self, self.model)
                cursor = self.model.Data.read(buffer, cursor + 4)
                header_string = readString(buffer, cursor)
            elif header_string == 'Anim':
                self.model.Anim = AnimList(self, self.model)
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
        self.parent = None
        self.modelblock = None
        self.collection = None
        self.texture_index = 800#1648
        self.ext = None
        self.id = id
        self.scale = 0.01
        
        self.ref_map = {} # where we'll map node ids to their written locations
        self.ref_keeper = {} # where we'll remember locations of node refs to go back and update with the ref_map at the end
        self.hl = None
        
        self.header = ModelHeader(self, self)
        self.Data = []
        self.AltN = []
        self.Anim = []
        
        self.materials = {}
        self.textures = {}
        self.nodes = []

    def read(self, buffer):
        if self.id is None:
            return
        cursor = 0
        cursor = self.header.read(buffer, cursor)
        if cursor is None:
            show_custom_popup(bpy.context, "Unrecognized Model Extension", f"This model extension was not recognized: {self.header.model.ext}")
            return None
        if self.AltN and self.ext != 'Podd':
            AltN = list(set(self.header.AltN))
            for i in range(len(AltN)):
                node_type = readUInt32BE(buffer, cursor)
                node = create_node(node_type, self, self)
                self.nodes.append(node.read(buffer, AltN[i]))
        else:
            node_type = readUInt32BE(buffer, cursor)
            node = create_node(node_type, self, self)
            self.nodes = [node.read(buffer, cursor)]
            
        return self

    def make(self):
        collection = bpy.data.collections.new(f"model_{self.id}_{self.ext}")
        
        collection['type'] = 'MODEL'
        bpy.context.scene.collection.children.link(collection)
        self.collection = collection
        
        self.header.make()
        for node in self.nodes:
            node.make(None, collection)

        return collection

    def unmake(self, collection, texture_export, textureblock):
        self.textureblock = textureblock
        self.written_textures = {}
        self.ext = collection['ext']
        self.id = collection['ind']
        self.header.unmake(collection)
        self.nodes = []
        self.texture_export = texture_export
        #if 'parent' in collection: return
        
        viscol = []
        vis = []
        col = []
        
        root = Group20580(self, self, 20580)
        
        self.nodes.append(root)
        
        for child_collection in collection.children:
            if child_collection.name == 'Track':
                for obj in [obj for obj in child_collection.objects if obj.type == 'MESH']:
                    mesh = Mesh(None, self).unmake(obj)
                    if mesh.has_collision() and mesh.has_visuals():
                        viscol.append(mesh)
                    elif mesh.has_collision():
                        col.append(mesh)
                    elif mesh.has_visuals():
                        vis.append(mesh)
                trak_group = Group20580(root, self, 20580)
        
                if len(viscol):
                    node = MeshGroup12388(trak_group, self, 12388)
                    for child in viscol: 
                        child.parent = node
                        node.children.append(child)
                    node.calc_bounding()
                    trak_group.children.append(node)
                
                if len(vis):
                    node = MeshGroup12388(trak_group, self, 12388)
                    for child in vis: 
                        child.parent = node
                        node.children.append(child)
                    node.calc_bounding()
                    trak_group.children.append(node)
                    
                if len(col):
                    node = MeshGroup12388(trak_group, self, 12388)
                    for child in col: 
                        child.parent = node
                        node.children.append(child)
                    node.calc_bounding()
                    trak_group.children.append(node)
        
                trak_group.header = [0, 1]         
                
                root.children.append(trak_group)
                
            if child_collection.name == 'Skybox':
                sky_group = Group20580(root, self, 20580)
                sky_empty = Group53349(sky_group, self, 53349)
                sky_empty.header = [2]
                sky_to_camera = Group53350(sky_empty, self, 53350)
                sky_mesh = MeshGroup12388(sky_to_camera, self, 12388)
                
                for obj in [obj for obj in child_collection.objects if obj.type == 'MESH']:
                    mesh = Mesh(sky_mesh, self).unmake(obj)
                    mesh.material.shader.render_mode_1 = 0b1100000010000010000000001000
                    mesh.material.shader.render_mode_2 = 0b11000000100010000000001000
                    sky_mesh.children.append(mesh)
                    mesh.parent = sky_mesh
                sky_mesh.calc_bounding()
                sky_to_camera.children.append(sky_mesh)
                sky_empty.children.append(sky_to_camera)
                sky_group.children.append(sky_empty)
                root.children.append(sky_group)
        
            
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
        bit = 2 ** (7 - ((cursor % 32) // 4))
        highlight = self.hl[highlight_offset]
        self.hl[highlight_offset] = highlight | bit