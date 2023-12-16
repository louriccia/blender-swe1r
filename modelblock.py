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
    def __init__(self, data):
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
                raise ValueError("Vec3 is not normalized")
        self.data = data
        return self
    
    def get(self):
        return self.data
    
class FloatPosition(Data):
    def __init__(self, data):
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
                raise ValueError("Vec3 is not normalized")
        self.data = data
        return self
    
    def get(self):
        return self.data

    
class FloatMatrix(Data):
    def __init__(self, data):
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
    def __init__(self, data):
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
    def __init__(self, hl):
        super().__init__('>H4B3H8B6f2I2i')
        self.hl = hl
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
        self.fog = Fog().set(data[1:7])
        self.lights = Lights().set(data[7:22])
        self.flags, self.unk2, self.unload, self.load = data[22:]
        return self
        
    def make(self, obj):
        for key in mesh_node['collision']['data']:
            obj[key] = mesh_node['collision']['data'][key]
        
        obj.id_properties_ui('fog_color').update(subtype='COLOR')
        obj.id_properties_ui('lights_ambient_color').update(subtype='COLOR')
        obj.id_properties_ui('lights_color').update(subtype='COLOR')
    
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
    def __init__(self, hl, length):
        super().__init__(f'>{length*3}h')
        self.hl = hl
        self.data = None

    def read(self, buffer, cursor):
        self.data = struct.unpack_from(self.format_string, buffer, cursor)
        return self

    def make(self):
        return self.data
    
    def unmake(self, mesh):
        self.data = [round(co) for vert in mesh.data.vertices for co in vert.co]
        return self
    
    def write(self, buffer, cursor):
        return struct.pack_into(self.format_string, buffer, cursor, *self.data)
    
class CollisionVertStrips(DataStruct):
    def __init__(self, hl, count):
        super().__init__(f'>{count}I')
        self.hl = hl
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
        super().__init__('>4_I24_HHI8_I8_H')
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
            self.tags = CollisionTags(self.hl).read(buffer, tags_addr)
        if vert_strips_addr:
            self.vert_strips = CollisionVertStrips(self.hl, strip_count).read(buffer, vert_strips_addr)
        if vert_buffer_addr:
            self.vert_buffer = CollisionVertBuffer(self.hl, vert_count).read(buffer, vert_buffer_addr)
        self.strip_size = strip_size
        self.strip_count = strip_count

    def make(self, parent):
        
        if (self.vert_buffer is None or len(mesh_node['collision']['vert_buffer']) < 3):
            return
                
        verts = self.vert_buffer.make()
        edges = []
        faces = []
        start = 0
        vert_strips = [self.strip_size for s in range(self.strip_count)]
        
        if(self.vert_strips is not None): 
            vert_strips = self.vert_strips
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
                
        mesh_name = self.id + "_" + "collision"
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
    
class Mesh():
    def __init__(self, model):
        return
    def read(self):
        return
    def make(self):
        return
    def unmake(self):
        return
    def write(self):
        return
    

    
class Node(DataStruct):
    def __init__(self, model):
        super().__init__('>7I')
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
    def read(self, buffer, cursor):
        self.id = cursor
        self.node_type, self.load_group1, self.load_group2, self.unk1, self.unk2, child_count, child_start = struct.unpack_from(self.format_string, buffer, cursor)
        
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


        if self.model.AltN and cursor in self.model.AltN:
            node.AltN = [i for i, h in enumerate(self.model.AltN) if h == cursor]
        
        if cursor in self.model.header:
            node.header = [i for i, h in enumerate(self.model.header) if h == cursor]

        if not self.model.node_map.get(self.id):
            self.model.node_map[self.id] = True

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
        
        node_empty = make_node(node, model, parent)
 
        return node
    def make(self):
        return
    def unmake(self):
        return
    def write(self):
        return

class MeshGroup12388(Node):
    def __init__(self, model):
        super().__init__(model)
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
    def make(self):
        return
    def unmake(self):
        return
    def write(self, buffer, cursor):
        return
        
class Group53348(Node):
    def __init__(self, model):
        super().__init__(model)
        self.matrix = FloatMatrix()
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.matrix = FloatMatrix(struct.unpack_from("12f", buffer, cursor+28))
    def make(self):
        return
    def unmake(self):
        return
    def write(self, buffer, cursor):
        return
        
class Group53349(Node):
    def __init__(self, model):
        super().__init__(model)
        self.matrix = FloatMatrix()
        self.bonus = FloatPosition()
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.matrix = FloatMatrix(struct.unpack_from("12f", buffer, cursor+28))
        self.bonus = FloatPosition(struct.unpack_from("3f", buffer, cursor+76))
    def make(self):
        return
    def unmake(self):
        return
    def write(self, buffer, cursor):
        return
        
class Group53350(Node):
    def __init__(self, model):
        super().__init__(model)
        self.unk1 = None
        self.unk2 = None
        self.unk3 = None
        self.unk4 = None
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.unk1, self.unk2, self.unk3, self.unk4 = struct.unpack_from("3If", buffer, cursor+28)
    def make(self):
        return
    def unmake(self):
        return
    def write(self, buffer, cursor):
        return
      
class Group20581(Node):
    def __init__(self, model):
        super().__init__(model)
    
class Group20582(Node):
    def __init__(self, model):
        super().__init__(model)
        self.floats = []
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.floats = struct.unpack_from("11f", buffer, cursor+28)
    def make(self):
        return
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
        print(self.float1, self.float2, self.float3, self.flag1, self.flag2, self.num_keyframes, self.float4, self.fllat5, self.float6, self.float7, self.float8, keyframe_times_addr, keyframe_poses_addr, self.target, self.unk2)
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
        
        print(header_string)
        

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
        self.model.collection['ind'] = self.model.index
        self.model.collection['ext'] = self.model.ext
        
        lightstreaks_col = bpy.data.collections.new(f"{index}_lightstreaks")
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

class Model():
    def __init__(self, id):
        self.collection = None
        self.ext = None
        self.id = id
        
        self.ref_map = {} # where we'll map node ids to their written locations
        self.ref_keeper = {} # where we'll remember locations of node offsets to go back and update with the offset_map at the end
        self.hl = None
        
        self.header = ModelHeader(self)
        self.Data = []
        self.AltN = []
        self.Anim = []
        
        self.mats = []
        self.textures = []
        self.nodes = []

    def read(self, buffer, cursor):
        self.header = ModelHeader(self)
        cursor = self.header.read(buffer, cursor)
        
        if self.AltN and self.ext != 'Podd':
            AltN = list(set(self.header.AltN))
            for i in range(len(AltN)):
                self.nodes.append(Node(self).read(buffer, AltN[i]))
        else:
            self.nodes = [Node(self).read(buffer, cursor)]

    def make(self):
        collection = bpy.data.collections.new(f"model_{self.index}_{self.ext}")
        
        collection['type'] = 'MODEL'
        bpy.context.scene.collection.children.link(collection)
        self.collection = collection

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