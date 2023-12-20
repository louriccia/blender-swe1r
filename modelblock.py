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
            raise ValueError("Vec3 must contain only 3 values")
                
        self.data = data
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

class Color(Data):
    def __init__(self, data = None):
        if data is None:
            self.data = [0, 0, 0]
        else:
            self.set(data)
        
    def __str__(self):
        return f"r: {self.data[0]} g: {self.data[1]} b: {self.data[2]}"
    
    def set(self, data=None):
        if(len(data) != 3):
            raise ValueError("Color must have 3 values")
        self.data = data
        return self
    
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
    
class Visuals(DataStruct):
    def __init__(self, model):
        super().__init__('>I36xI4xII2xHI')
        self.model = model
        self.material = None
        self.vert_buffer = None
        self.index_buffer = None
        self.id = None
    
    def read(self, buffer, cursor):
        self.id = cursor
        mat_addr, group_parent, index_buffer_addr, vert_buffer_addr, vert_count, group_count = struct.unpack_from(self.format_string, buffer, cursor)
    
    def make(self, parent):
        pass
    
class Mesh():
    def __init__(self, model):
        self.model = model
        self.collision = Collision(self.model)
        self.visuals = Visuals(self.model)
    def read(self, buffer, cursor):
        self.collision.read(buffer, cursor)
        self.visuals.read(buffer, cursor)
        return self
    def make(self, parent):
        self.collision.make(parent)
        return
    def unmake(self):
        return
    def write(self):
        return
    
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
            if self.type ==53349:
                #new_empty.location = [node['xyz']['x']*scale, node['xyz']['y']*scale, node['xyz']['z']*scale]
                if self.unk1 &  1048576 != 0 and False:
                    
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
                elif False:
                    new_empty.matrix_world = [
                    [node['xyz']['ax'], node['xyz']['ay'], node['xyz']['az'], 0],
                    [node['xyz']['bx'], node['xyz']['by'], node['xyz']['bz'], 0],
                    [node['xyz']['cx'], node['xyz']['cy'], node['xyz']['cz'], 0],
                    [node['xyz']['x']*scale, node['xyz']['y']*scale, node['xyz']['z']*scale, 1],
                    ]
            
                
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
        
        if False and (self.type in [53349, 53350]):
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
        if parent is not None:
            #savedState = new_empty.matrix_world
            if self.type not in [53349, 53350] or self.unk1 & 1048576 == 0 and False:
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
        for node in self.children:
            if not isinstance(node, dict):
                node.make(new_empty)
            
        return new_empty
    def unmake(self):
        return
    def write(self):
        return

class MeshGroup12388(Node):
    def __init__(self, model, type):
        super().__init__(model, type)
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        return self
    def make(self, parent = None):
        return super().make(parent)
    def unmake(self):
        return
    def write(self, buffer, cursor):
        return
        
class Group53348(Node):
    def __init__(self, model, type):
        super().__init__(model, type)
        self.matrix = FloatMatrix()
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.matrix = FloatMatrix(struct.unpack_from(">12f", buffer, cursor+28))
        return self
    def make(self, parent = None):
        return super().make(parent)
    def unmake(self):
        return
    def write(self, buffer, cursor):
        return
        
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
        return super().make(parent)
    def unmake(self):
        return
    def write(self, buffer, cursor):
        return
        
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
    def unmake(self):
        return
    def write(self, buffer, cursor):
        return
  
class Group20580(Node):
    def __init__(self, model, type):
        super().__init__(model, type)
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        return self
    def make(self, parent = None):
        return super().make(parent)
      
class Group20581(Node):
    def __init__(self, model, type):
        super().__init__(model, type)
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        return self
    def make(self, parent = None):
        return super().make(parent)
    
class Group20582(Node):
    def __init__(self, model, type):
        super().__init__(model, type)
        self.floats = []
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.floats = struct.unpack_from(">11f", buffer, cursor+28)
        return self
    def make(self, parent = None):
        return super().make(parent)
    def unmake(self):
        return
    def write(self, buffer, cursor):
        return
      
class LStr(DataStruct):
    def __init__(self, model):
        super().__init__('>4_3f')
        self.data = FloatPosition()
        self.model = model
    def read(self, buffer, cursor):
        self.data = FloatPosition(struct.unpack_from(self.format_string, buffer, cursor))

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
                LStr(self.model).read(buffer, cursor)
                cursor += 12
                i += 4
            else:
                self.data.append(readUInt32BE(buffer,cursor))
                i+=1
                cursor += 4

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

        return cursor + 4
    
    def make(self):
        self.model.collection['header'] = self.offsets
        self.model.collection['ind'] = self.model.id
        self.model.collection['ext'] = self.model.ext
        
        lightstreaks_col = bpy.data.collections.new("lightstreaks")
        lightstreaks_col['type'] = 'LSTR'
        self.model.collection.children.link(lightstreaks_col)
        return
    
    def unmake(self, collection):
        return
    
    def write(self, buffer, cursor):
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

        if self.model.Data:
            cursor = write_data(buffer, cursor, model, hl)

        if self.model.Anim:
            self.ref_map['Anim'] = cursor + 4
            cursor = write_anim(buffer, cursor, model, hl)

        if self.model.AltN:
            self.ref_map['AltN'] = cursor + 4
            cursor = write_altn(buffer, cursor, model, hl)

        cursor = writeString(buffer, 'HEnd', cursor)
        self.ref_map['HEnd'] = cursor

        return header_offsets

def find_topmost_parent(obj):
    while obj.parent is not None:
        obj = obj.parent
    return obj

class Model():
    def __init__(self, id):
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
        
        self.mats = []
        self.textures = []
        self.nodes = []

    def read(self, buffer, cursor):
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
        self.header = ModelHeader().unmake(collection)
        self.nodes = []
        if 'parent' in collection: return
        
        top_nodes = [] 
        for obj in collection.objects:
            if obj.type != 'MESH': continue
            top = find_topmost_parent(obj)
            if top not in top_nodes: top_nodes.append(top)
        
        for node in top_nodes:
            self.nodes.append(Node().unmake(node))

    def write(self, buffer, cursor):
        buffer = bytearray(8000000)
        self.hl = bytearray(1000000)
        cursor = 0

        cursor = self.header.write(buffer, cursor)

        # write all nodes
        for node in self.nodes:
            cursor = node.write(buffer, cursor, self)

        # write all animations
        for anim in self.Anim:
            cursor = anim.write(buffer, cursor, self)

        # write all outside references
        refs = [ref for ref in self.ref_keeper if ref != '0']
        for ref in self.ref_keeper:
            for offset in self.ref_keeper[ref]:
                writeUInt32BE(buffer, self.ref_map[str(ref)], offset)

        return [self.hl[:math.ceil(cursor / (32 * 4)) * 4], buffer[:cursor]]