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

import struct
import bpy
import bmesh
import math
import mathutils
from .general import RGB3Bytes, FloatPosition, FloatVector, DataStruct, RGBA4Bytes, ShortPosition, FloatMatrix, writeFloatBE, writeInt32BE, writeString, writeUInt32BE, writeUInt8, readString, readInt32BE, readUInt32BE, readUInt8, readFloatBE
from .textureblock import Texture, compute_image_hash, compute_hash
from ..utils import show_custom_popup, model_types, header_sizes, showbytes, Podd_MAlt

def find_existing_light(objects, color, location, rotation):
    for light in objects:
        if light.type == 'LIGHT' and light.data.color == color and (light.location - location).length < 0.001 and light.users:
            # Check rotation (convert both to Euler for comparison)
            existing_rotation = light.rotation_euler
            if existing_rotation == rotation:
                return light
    return None

def get_model_type(name):
    for code, model_name, description in model_types:
        if model_name == name:
            return code
    return None 

class Lights(DataStruct):
    def __init__(self, model):
        super().__init__('>h8b6f')
        self.model = model
        self.flag = 0
        # 00100 = invert affected?
        # 01000 = flicker?
        # 10000 = persistent lighting
        self.ambient = RGB3Bytes()
        self.color = RGB3Bytes()
        self.unk1 = 0
        self.unk2 = 0
        self.pos = FloatPosition()
        self.rot = FloatVector()
        
    def read(self, buffer, cursor):
        self.flag, ambient_r, ambient_g, ambient_b, color_r, color_g, color_b, self.unk1, self.unk2, x, y, z, rx, ry, rz = struct.unpack_from(self.format_string, buffer, cursor)
        self.ambient.from_array([ambient_r, ambient_g, ambient_b])
        self.color.from_array([color_r, color_g, color_b])
        self.pos.from_array([x, y, z])
        self.rot.from_array([rx, ry, rz])
        return self
    
    def make(self, obj):
        
        if self.flag & 0x3 > 0:
            objects = get_all_objects_in_collection(self.model.collection)
            existing_light = find_existing_light(objects, mathutils.Color(self.color.make()), mathutils.Vector([a * self.model.scale for a in self.pos.make()]),  mathutils.Euler(self.rot.make()))
            if existing_light is None:
                # Create a new light if no existing light is found
                
                new_light = bpy.data.lights.new(type='POINT', name='pod_lighting')
                new_light.color = self.color.make()
                
                light_object = bpy.data.objects.new(name="pod_lighting", object_data=new_light)
                self.model.collection.objects.link(light_object)

                # Set the location and rotation
                light_object.location = [a * self.model.scale for a in self.pos.make()]
                light_object.rotation_euler = self.rot.make()
                
                obj.lighting_light = new_light
            else: 
                obj.lighting_light = existing_light.data
        obj.lighting_color = self.ambient.make()
        obj.lighting_invert = self.flag & 0x4 > 0
        obj.lighting_flicker = self.flag & 0x8 > 0
        obj.lighting_persistent = self.flag & 0x10 > 0
        
    def unmake(self, obj):
        if obj.lighting_light is not None:
            light_object = bpy.data.objects.get(obj.lighting_light.name)
            self.flag |= 0x3
            
            if light_object:
                self.color.unmake(light_object.data.color)
                self.pos.from_array([round(a/self.model.scale) for a in light_object.location])
                self.rot.from_array(light_object.rotation_euler)
        
        self.ambient.unmake(obj.lighting_color)
        
        if obj.lighting_invert:
            self.flag |= 0x4
        if obj.lighting_flicker:
            self.flag |= 0x8
        if obj.lighting_persistent:
                self.flag |= 0x10
        
        return self
    
    def to_array(self):
        return [self.flag, *self.ambient.to_array(), *self.color.to_array(), self.unk1, self.unk2, *self.pos.to_array(), *self.rot.to_array()]
        
    def from_array(self, arr):
        self.flag, ambient_r, ambient_g, ambient_b,color_r, color_g, color_b, self.unk1, self.unk2, x, y, z, a, b, c = arr
        self.ambient.from_array([ambient_r, ambient_g, ambient_b])
        self.color.from_array([color_r, color_g, color_b])
        self.pos.from_array([x, y, z])
        self.rot.from_array([a, b, c])
        return self

class Fog(DataStruct):
    def __init__(self):
        super().__init__('>4B2H')
        self.flag = 0
        #0001 = Update color
        #0010 = Update distance
        self.color = RGB3Bytes()
        self.start = 0
        self.end = 0
    
    def make(self, obj): 
        obj.fog_color_update = self.flag & 0x01 > 0
        obj.fog_color = self.color.make()
        obj.fog_range_update = self.flag & 0x02 > 0
        obj.fog_min = self.start
        obj.fog_max = self.end
        obj.fog_clear = self.flag & 0x02 and self.start == 0
        
    def unmake(self, obj):
        if obj.fog_color_update:
            self.flag |= 0x01
        if obj.fog_range_update or obj.fog_clear:
            self.flag |= 0x02
            
        self.color.unmake(obj.fog_color)
        self.start = 0 if obj.fog_clear else obj.fog_min
        self.end = obj.fog_max
            
        return self
    
    def read(self, buffer, cursor):
        self.flag, r, g, b, self.start, self.end = struct.unpack_from(self.format_string, buffer, cursor)
        self.color.from_array([r, g, b])
        return self
        
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, self.flag, *self.color.to_array(), self.start, self.end)
        return cursor + self.size
    
    def to_array(self):
        return [self.flag, *self.color.to_array(), self.start, self.end]
        
    def from_array(self, arr):
        self.flag, r, g, b, self.start, self.end = arr
        self.color = RGB3Bytes().from_array([r, g, b])
        return self

class TriggerFlagEnum():
    Disabled = (1 << 0)
    SpeedCheck150 = (1 << 1)
    SkipLap1 = (1 << 2)
    SkipLap2 = (1 << 3)
    SkipLap3 = (1 << 4)
    IgnoreAI = (1 << 5)
    
class TriggerFlag(DataStruct):
    def __init__(self):
        super().__init__('>H')
        # These flags are set in the exe for the tracks, not in modelblock
        self.flags = ['Disabled', 'SpeedCheck150', 'SkipLap1', 'SkipLap2', 'SkipLap3', 'IgnoreAI']
        self.data = 0
        self.settings = 0
        for attr in self.flags:
            setattr(self, attr, False)

    def read(self, buffer, cursor):
        data = struct.unpack_from(self.format_string, buffer, cursor)
        data = data[0]
        self.settings = data >> 6
        for attr in self.flags:
            setattr(self, attr, bool(getattr(TriggerFlagEnum, attr) & data))
            
        return self
    
    def make(self, obj):
        obj.trigger_settings = self.settings
        for attr in self.flags:
            obj[attr] = getattr(self, attr)
    
    def unmake(self, obj):
        if 'settings' in obj:
            self.settings = obj.trigger_settings
        for attr in self.flags:
            if attr in obj:
                setattr(self, attr, obj[attr])
        return self
    
    def write(self, buffer, cursor):
        data = self.settings << 6
        for attr in self.flags:
            data |= (getattr(TriggerFlagEnum, attr) * int(getattr(self, attr)))
        
        struct.pack_into(self.format_string, buffer, cursor, data)

class CollisionTrigger(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>8fI2hI')
        self.parent = parent
        self.model = model
        self.position = FloatPosition()
        self.rotation = FloatVector()
        self.width = 100 # FIX: Not scale dependant 
        self.height = 100
        self.target = 0
        self.id = 0
        self.flags = TriggerFlag()
        self.next = 0
    
    def to_array(self):
        return [*self.position.to_array(), *self.rotation.to_array(), self.width, self.height, self.target, self.id, self.flags.data, self.next]
    
    def read(self, buffer, cursor):
        x, y, z, rx, ry, rz, self.width, self.height, self.target, self.id, flags, self.next = struct.unpack_from(self.format_string, buffer, cursor)
        self.position.from_array([x, y, z])
        self.rotation.from_array([rx, ry, rz])
        self.flags.read(buffer, cursor + 38)
        return self
        
    def make(self, parent = None, collection = None):
        trigger_empty = bpy.data.objects.new("trigger_" + str(self.id), None)
        trigger_empty.empty_display_type = 'CUBE'
        trigger_empty.location = self.position.data
        trigger_empty.rotation_euler = [math.asin(self.rotation.data[2]), 0, math.atan2(self.rotation.data[1], self.rotation.data[0])]
        trigger_empty.scale = [self.width/2, self.width/2, self.height/2]
        trigger_empty['trigger_id'] = self.id
        
        
        self.flags.make(trigger_empty)
        # store a ref to the target id so we can properly connect it later
        # we store as string because the int is too large for c
        trigger_empty['target_id'] = str(self.target)
        
        if parent is not None:
            trigger_empty.parent = parent
        if collection is not None:
            collection.objects.link(trigger_empty)
            
        self.model.triggers.append(trigger_empty)
            
        return trigger_empty
    
    def unmake(self, node):
        if node.type != 'EMPTY' or node.empty_display_type != 'CUBE':
            return None
        
        if node.trigger_id is None:
            return None
        
        location, rot, scale = node.matrix_world.decompose()
        rotation = node.matrix_world.to_euler('XYZ')
        
        self.id = node.trigger_id
        self.flags.unmake(node)
        self.position.from_array([x/self.model.scale for x in node.matrix_world.to_translation()])
        self.rotation.from_array([ math.cos(rotation[2]), math.sin(rotation[2]), math.sin(rotation[0])])
        self.width = scale[0]*2/self.model.scale
        self.height = scale[2]*2/self.model.scale
        if node.target:
            self.target = node.target
            
        self.model.triggers.append(self)
        return self
    
    def write(self, buffer, cursor):
        self.write_location = cursor
        struct.pack_into(self.format_string, buffer, cursor, *self.position.to_array(), *self.rotation.to_array(), self.width, self.height, 0, self.id, 0, 0)
        self.flags.write(buffer, cursor + 38)
        self.model.highlight(cursor + 32)
        return cursor + self.size
    
    def write_target(self, buffer):
        if self.target:
            struct.pack_into('>I', buffer, self.write_location + 32, self.target.write_location)

class SurfaceEnum():
    ZOn = (1 << 0)
    ZOff = (1 << 1)
    Fast = (1 << 2)
    Slow = (1 << 3)
    Swst = (1 << 4)
    Slip = (1 << 5)
    Dust = (1 << 6)
    Snow = (1 << 7)
    Wet = (1 << 8)
    Ruff = (1 << 9)
    Swmp = (1 << 10)
    NSnw = (1 << 11)
    Mirr = (1 << 12)
    Lava = (1 << 13)
    Fall = (1 << 14)
    Soft = (1 << 15)
    NRsp = (1 << 16)
    Flat = (1 << 17)
    Surface18 = (1 << 18)
    Surface19 = (1 << 19)
    Surface20 = (1 << 20)
    Surface21 = (1 << 21)
    Surface22 = (1 << 22)
    Surface23 = (1 << 23)
    Surface24 = (1 << 24)
    Surface25 = (1 << 25)
    Surface26 = (1 << 26)
    Surface27 = (1 << 27)
    Surface28 = (1 << 28)
    Side = (1 << 29)
    Surface30 = (1 << 30)
    Surface31 = (1 << 31)
    
class SpecialSurfaceEnum():
    Unk0 = (1 << 0)
    Unk1 = (1 << 1) #hide skybox
    Unk2 = (1 << 2) #show skybox
    Unk3 = (1 << 3) #strict spline
    Unk4 = (1 << 4) #elevation?
    Unk5 = (1 << 5) #magnet mode

class SpecialSurfaceFlags(DataStruct):
    def __init__(self):
        super().__init__('>H')
        self.flags = ['Unk0', 'Unk1', 'Unk2', 'Unk3', 'Unk4', 'Unk5']
        for attr in self.flags:
            setattr(self, attr, False)
            
    def read(self, buffer, cursor):
        data = struct.unpack_from(self.format_string, buffer, cursor)
        data = data[0]
        for attr in self.flags:
            setattr(self, attr, bool(getattr(SpecialSurfaceEnum, attr) & data))
            
    def make(self, obj):
        obj.skybox_hide = self.Unk1
        obj.skybox_show = self.Unk2
        obj.strict_spline = self.Unk3
        obj.elevation = self.Unk4
        obj.magnet = self.Unk5
        
            
    def unmake(self, obj):
        self.Unk1 = obj.skybox_hide
        self.Unk2 = obj.skybox_show
        self.Unk3 = obj.strict_spline
        self.Unk4 = obj.elevation
        self.Unk5 = obj.magnet
    
    def write(self, buffer, cursor):
        data = 0
        for attr in self.flags:
            if getattr(self, attr):
                data |= (getattr(SpecialSurfaceEnum, attr) * int(getattr(self, attr)))
        struct.pack_into(self.format_string, buffer, cursor, data)
        return cursor + self.size

class SurfaceFlags(DataStruct):
    def __init__(self):
        super().__init__('>I')
        self.flags = ['ZOn', 'ZOff', 'Fast', 'Slow', 'Swst', 'Slip', 'Dust', 'Snow', 'Wet', 'Ruff', 'Swmp', 'NSnw', 'Mirr', 'Lava', 'Fall', 'Soft', 'NRsp', 'Flat', 'Side', 'Surface18', 'Surface19', 'Surface20', 'Surface21', 'Surface22', 'Surface23', 'Surface24', 'Surface25', 'Surface26', 'Surface27', 'Surface28',  'Surface30', 'Surface31']
        for attr in self.flags:
            setattr(self, attr, False)

    def read(self, buffer, cursor):
        data = struct.unpack_from(self.format_string, buffer, cursor)
        data = data[0]
        for attr in self.flags:
            setattr(self, attr, bool(getattr(SurfaceEnum, attr) & data))
    
    def make(self, obj):
        for attr in self.flags:
            obj[attr] = getattr(self, attr)
    
    def unmake(self, obj):
        for attr in self.flags:
            if attr in obj:
                setattr(self, attr, obj[attr])
    
    def write(self, buffer, cursor):
        data = 0
        for attr in self.flags:
            data |= (getattr(SurfaceEnum, attr) * int(getattr(self, attr)))
        struct.pack_into(self.format_string, buffer, cursor, data)

    def is_set(self, flag):
        return bool(self.value & flag)

    def set_flag(self, flag):
        self.value |= flag

    def clear_flag(self, flag):
        self.value &= ~flag

class CollisionTags(DataStruct):
    def __init__(self, parent, model):
        
        super().__init__('>H4B3H8B6fI2H3I')
        self.parent = parent
        self.model = model
        self.unk = SpecialSurfaceFlags()
        self.fog = Fog()
        self.lights = Lights(self.model)
        self.flags = SurfaceFlags()
        self.unk1 = 0
        self.unk2 = 0
        self.unload = 0
        self.load = 0
        self.triggers = []

    def read(self, buffer, cursor):
        data = struct.unpack_from(self.format_string, buffer, cursor)
        self.unk.read(buffer, cursor)
        self.fog.from_array(data[1:7])
        self.lights.from_array(data[7:22])
        flags, self.unk1, self.unk2, self.unload, self.load = data[22:27]
        self.flags.read(buffer, cursor + 44)
        
        #get triggers
        trigger_pointer = data[-1]
        while trigger_pointer:
            trigger = CollisionTrigger(self, self.model).read(buffer, trigger_pointer)
            self.triggers.append(trigger)
            trigger_pointer = trigger.next
        return self
        
    def make(self, obj, collection = None):
        self.unk.make(obj)
        self.flags.make(obj)
        self.fog.make(obj)
        self.lights.make(obj)
        obj['collision_data'] = True
        
        obj.load_trigger = [0 for i in range(24)]
        for i in range(24):
            u_val = bool(self.unload & (1 << (i + 8)))
            l_val = bool(self.load & (1 << (i + 8)))
            if l_val:
                obj.load_trigger[i] = 1
            elif u_val:
                obj.load_trigger[i] = 2
            else:
                obj.load_trigger[i] = 0
        
        for trigger in self.triggers:
            trigger.make(obj, collection)
        
    def unmake(self, mesh):
        self.unk.unmake(mesh)
        self.flags.unmake(mesh)
        self.fog.unmake(mesh)
        self.lights.unmake(mesh)
        
        for i, val in enumerate(mesh.load_trigger):
            if val == 1:
                self.load |= (1 << (i + 8))
            elif val == 2:
                self.unload |= (1 << (i + 8))
        
        for child in mesh.children:
            trigger = CollisionTrigger(self, self.model).unmake(child)
            if trigger:
                self.triggers.append(trigger)
        
        return self
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, *[0, *self.fog.to_array(), *self.lights.to_array(), 0, self.unk1, self.unk2, self.unload, self.load, 0])
        self.unk.write(buffer, cursor)
        self.flags.write(buffer, cursor + 44)
        cursor += self.size
        for trigger in self.triggers:
            #write pointer to next trigger
            self.model.highlight(cursor - 4)
            writeUInt32BE(buffer, cursor, cursor - 4)
            cursor = trigger.write(buffer, cursor)
        return cursor

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
            co = vert.co #mesh.matrix_world @ 
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
    
    # recognizes strips in the pattern of the faces' vertex indices
    def unmake(self, mesh):
        face_buffer = [[v for v in face.vertices] for face in mesh.data.polygons]
        if not len(face_buffer):
            return self
        
        while len(face_buffer):
            end_strip = 1
            for i in range(1, len(face_buffer)):
                last = face_buffer[i - 1]
                
                # this detects cases where the strip buffer needs to be written.
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
        self.unmade = False
    def read(self, buffer, cursor):
        x, y, z, uv_x, uv_y, r, g, b, a = struct.unpack_from(self.format_string, buffer, cursor)
        self.co = [x, y, z]
        self.uv = [uv_x, uv_y]
        self.color.from_array([r, g, b, a])
        return cursor + self.size
    def to_array(self):
        return [*self.co, *self.uv, *self.color.to_array()]
    
    def verts_to_array(self):
        return self.co
    
    def __eq__(self, other):
        return self.co == other.co and self.uv == other.uv and self.color == other.color
    
    def clone(self, other):
        self.co = other.co
        self.uv = other.uv
        self.color = other.color
        return self
    
    def unmake(self, co = None, uv = None, color = None):
        
        if co:
            self.co = [round(c/self.model.scale) for c in co]
        if uv:
            new_uv = [round(c*4096) for c in uv]
            if self.unmade and self.uv != new_uv:
                # if the uvs don't match, we need to make a new vertex
                return False
            self.uv = new_uv
        if color:
            self.color.unmake(color)
        self.unmade = True
        return self
    def write(self, buffer, cursor):
        co =  [min(32767, max(-32768, c)) for c in self.co]
        self.co = co
        uv =[min(32767, max(-32768, c)) for c in self.uv]
        self.uv = uv
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
        d = mesh.data
        if d is None:
            return
        
        if d.uv_layers and d.uv_layers.active:
            uv_data = d.uv_layers.active.data
        if d.vertex_colors and d.vertex_colors.active:
            color_data = d.vertex_colors.active.data
        
        # if d.uv_layers and d.uv_layers.active:
        #     uv_data = d.uv_layers.active.data
        # if d.color_attributes and len(d.color_attributes):
        #     if d.attributes.get(name_attr_baked) is not None:
        #         color_data = d.attributes[name_attr_baked].data
        #     else:
        #         color_data = d.attributes[d.attributes.default_color_name].data
        for vert in d.vertices:
            self.data.append(VisualsVertChunk(self, self.model))
            
        #there's probably a better way to do this but this works for now
        #https://docs.blender.org/api/current/bpy.types.Mesh.html

        for poly in d.polygons:
            for loop_index in poly.loop_indices:
                vert_index = d.loops[loop_index].vertex_index
                uv = None if not uv_data else uv_data[loop_index].uv
                color = None if not color_data else color_data[loop_index].color
                self.data[vert_index].unmake(d.vertices[vert_index].co, uv, color) #mesh.matrix_world @ 
                
        self.length = len(self.data)
        return self
    
    def to_array(self):
        return [d.to_array() for d in self.data]
    
    def write(self, buffer, cursor, index_buffer):
        assert index_buffer.offset, "Index buffer must be written before vertex buffer"
        
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
            assert chunk_class, f"Invalid index chunk type {chunk_type}"
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
        # TODO: this should not pair faces that have indices more than 63 apart in the same chunk
        while len(faces) > 1:
            chunk_type = 6
            chunk_class = self.map.get(chunk_type)
            chunk = chunk_class(self, self.model, chunk_type)
            face_chunk = [f for face in faces[:2] for f in face]
            assert len(face_chunk) == 6, f"Invalid face chunk length in {self.parent.original_object.name} {face_chunk}"
            chunk.from_array(face_chunk)
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
            if max_index - min_index > 39:
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
        self.unk1 = 1280
        self.unk2 = 0
        self.unk3 = 0
        self.unk4 = 292
        self.unk5 = 184
        self.model = model
        
    def read(self, buffer, cursor):
        if cursor > len(buffer):
            return self
        self.unk0, self.unk1, self.unk2, self.unk3, self.unk4, self.unk5 = struct.unpack_from(self.format_string, buffer, cursor)
        return self
        
    def unmake(self, texture):
        return self
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, self.unk0, self.unk1, self.unk2, self.unk3, self.unk4, self.unk5)
        return cursor + self.size
    
    def to_array(self):
        return [self.unk0, self.unk1, self.unk2, self.unk3, self.unk4, self.unk5]
    
class MaterialTexture(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>I2H4x8H6I4xHH4x')

        self.parent = parent
        self.model = model
        self.unk0 = 1 #0, 1, 65, 73 
        self.format = 513
        self.unk4 = 0 #0, 4
        self.width = 0
        self.height = 0
        self.unk7 = 0
        self.unk8 = 0
        self.chunks = []
        self.unk9 = 2560 #this is a required value
        self.id = 0

    def read(self, buffer, cursor):
        if cursor == 0:
            return None

        if cursor in self.model.textures:
            return self.model.textures[cursor]

        unk_pointers = []
        self.id = cursor
        self.unk0, unk1, unk3, self.format, self.unk4, self.width, self.height, unk5, unk6, self.unk7, self.unk8, *unk_pointers, self.unk9, self.id = struct.unpack_from(self.format_string, buffer, cursor)
        for pointer in unk_pointers:
            if pointer:
                chunk = MaterialTextureChunk(self, self.model)
                chunk.read(buffer, pointer)
                self.chunks.append(chunk)

        self.model.textures[cursor] = self

        return self.model.textures[cursor]

    def to_array(self):
        return [self.unk0, 0, 0, self.format, self.unk4, self.width, self.height, 0, 0, self.unk7, self.unk8, *[0,0,0,0,0,0], self.unk9, self.id]

    def make(self):
        if self.id == 65535:
            return
        textureblock = self.model.modelblock.textureblock
        self.texture = Texture(self.id, self.format, self.width, self.height)
        pixel_buffer, palette_buffer = textureblock.fetch(self.id)
        self.texture.read(pixel_buffer, palette_buffer)
        return self.texture.make()

    def unmake(self, image):
        if image is None:
            print('image is None')
            return self

        if 'id' in image:
            self.id = int(image['id'])

        if 'format' in image:
            self.format = int(image['format'])

        print(image.name, self.id, self.format)
        
        self.width, self.height = image.size
        self.chunks.append(MaterialTextureChunk(self, self.model).unmake(self)) #this struct is required

        if self.model is None:
            return self

        #check if we already wrote this image
        if image.name in self.model.image_map:
            self.id = self.model.image_map[image.name]
            print(image.name,'already written as', self.id)
        elif self.model.texture_export:
            hash = compute_image_hash(image)
            
            #if user has made no changes
            if hash == image.get('internal_hash'):
                if self.id < 1648: #do nothing for vanilla
                    return self  
                
                # textureblock may have changed so we need to check
                id = self.model.textureblock.fetch_by_hash(image.get('external_hash'))
                if id is not None:
                    self.id = id
                    image['id'] = id
                    print('found', image.name, 'already in modelblock as', id)
                    return self
            
            image['internal_hash'] = hash
            id = len(self.model.textureblock.data)
            self.id = id
            image['id'] = id
            texture = Texture(id, self.format).unmake(image, self.format)
            self.format = texture.format
            if self.format in [512, 513]:
                self.unk0 = 1
            self.width = texture.width
            self.height = texture.height
            pixel_buffer = texture.pixels.write()
            palette_buffer = texture.palette.write()
            self.model.image_map[image.name] = id
            
            #see if this texture is already in block
            buffer = pixel_buffer + palette_buffer
            buffer_hash = compute_hash(buffer)
            image['external_hash'] = buffer_hash
            id = self.model.textureblock.fetch_by_hash(image.get('external_hash'))
            
            if id is not None:
                self.id = id
                image['id'] = id
                print('found', image.name, 'already in modelblock as', id)
                return self
            
            id = len(self.model.textureblock.data)
            self.model.textureblock.inject([pixel_buffer, palette_buffer], id)
            

        return self

    def write(self, buffer, cursor):
        chunk_addr = cursor + 28
        self.model.highlight(cursor + 56)
        #struct.pack_into(self.format_string, buffer, cursor, self.unk0, min(self.width*4, 65535), min(self.height*4, 65535), self.format, self.unk4, self.width, self.height, min(self.width*512, 65535), min(self.height*512, 65535), self.unk7, self.unk8, *[0, 0, 0, 0, 0, 0], self.unk9, self.id)
        struct.pack_into(self.format_string, buffer, cursor, 0, min(self.width*4, 65535), min(self.height*8, 65535), self.format, 3, self.width, self.height, min(self.width*512, 65535), min(self.height*512, 65535), 683, 503, *[3, 3, 3, 3, 3, 3], self.unk9, self.id)
        cursor += self.size

        for i, chunk in enumerate(self.chunks):
            self.model.highlight(chunk_addr + i * 4)
            writeUInt32BE(buffer, cursor, chunk_addr + i*4)
            cursor = chunk.write(buffer, cursor)
        return cursor

class MaterialShader(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>IH4I2x2I6x7H')
        
        self.parent = parent
        # this whole struct can be 0
        # notes from tilman https://discord.com/channels/441839750555369474/441842584592056320/1222313834425876502
        self.model = model
        self.unk1 = 0
        self.combiner_cycle_type = 2 # maybe "combiner cycle type"
        
        # combine mode: http://n64devkit.square7.ch/n64man/gdp/gDPSetCombineLERP.htm
        # these values seem to be unused by the pc version
        self.color_combine_mode_cycle1 = 0# 0b1000111110000010000011111
        #self.color_combine_mode_cycle1 = 3 use base color?
        self.alpha_combine_mode_cycle1 = 0#0b111000001110000011100000100
        #self.alpha_combine_mode_cycle1 = 0x03000000
        self.color_combine_mode_cycle2 = 0#0b11111000111110001111100000000
        self.alpha_combine_mode_cycle2 = 0#0b111000001110000011100000000
        # render mode: http://n64devkit.square7.ch/n64man/gdp/gDPSetRenderMode.htm
        self.render_mode_1 = 0x18 #initialize with zcmp and aa
        self.render_mode_2 = 0
        # 0b11001000000100000100100101111000	1	    weird material in bwr ice reflection
        # 0b11001000000100000100101101010000	1	    transparent death beam on oovo
        # 0b11001000000100010010000001111000	15	    broken textures
        # 0b11001000000100000100100111011000	113	    reserved for semi-transparent textures (format 3)
        # 0b11001000000100000100100101111001	225	    textures with transparency (format 513)
        #     0b1100000110000100100101001000    6	    transparent skybox (oovo asteroids)
        #     0b1111000010100010000000001000    342	    skybox materials
        # 0b11001000000100010010000000111000	2246	everything else
        #                       100000000000 transparency
        #  0b1100 0000 1000 0010 0000 0000 1000
        #    0b11 0000 0010 0010 0000 0000 1000
        #http://n64devkit.square7.ch/header/gbi.htm
        #	AA_EN		0x8
        #	Z_CMP		0x10 skybox does not use zcmp, all other meshes do
        #	Z_UPD		0x20
        #	IM_RD		0x40
        #	CLR_ON_CVG	0x80
        #	CVG_DST_CLAMP	0
        #	CVG_DST_WRAP	0x100
        #	CVG_DST_FULL	0x200
        #	CVG_DST_SAVE	0x300
        #	ZMODE_OPA	0
        #	ZMODE_INTER	0x400
        #	ZMODE_XLU	0x800 use alpha
        #	ZMODE_DEC	0xc00
        #	CVG_X_ALPHA	0x1000
        #	ALPHA_CVG_SEL	0x2000
        #	FORCE_BL	0x4000
        #	TEX_EDGE	0x0000 /* used to be 0x8000 */
        # 0x8000000 Do not tile
        self.color = RGBA4Bytes()
        self.unk = []
    def read(self, buffer, cursor):
        self.unk1, self.combiner_cycle_type, self.color_combine_mode_cycle1, self.alpha_combine_mode_cycle1, self.color_combine_mode_cycle2, self.alpha_combine_mode_cycle2, self.render_mode_1, self.render_mode_2, *self.unk = struct.unpack_from(self.format_string, buffer, cursor)
        self.color.read(buffer, cursor + 34)
    
    def make(self, material):
        material['unk1'] = self.unk1
        material['combiner_cycle_type'] = self.combiner_cycle_type
        
        material['color_combine_mode_cycle1'] = str(self.color_combine_mode_cycle1)
        material['alpha_combine_mode_cycle1'] = str(self.alpha_combine_mode_cycle1)
        material['color_combine_mode_cycle2'] = str(self.color_combine_mode_cycle2)
        material['alpha_combine_mode_cycle2'] = str(self.alpha_combine_mode_cycle2)
        
        material['render_mode_1'] = str(self.render_mode_1)
        material['render_mode_2'] = str(self.render_mode_2)
        
        if self.unk1 == 8 or self.render_mode_1 & 0x800 or self.render_mode_2 & 0x800:
            material.show_transparent_back = True
            material.blend_method = 'BLEND'
            material['transparent'] = True
    
    def unmake(self, material):
        if material is not None:
            if material.transparent:
                self.unk1 = 8
                self.render_mode_1 |= 0x800
            self.unk1 = material.get('unk1', 0)
            self.combiner_cycle_type = material.get('combiner_cycle_type', 0)
            self.color.unmake(material.material_color)
            
            self.color_combine_mode_cycle1 = int(material.get('color_combine_mode_cycle1', 0))
            self.alpha_combine_mode_cycle1 = int(material.get('alpha_combine_mode_cycle1', 0))
            self.color_combine_mode_cycle2 = int(material.get('color_combine_mode_cycle2', 0))
            self.alpha_combine_mode_cycle2 = int(material.get('alpha_combine_mode_cycle2', 0))
    
        # alternate way to detect if this material is on a skybox mesh
        mat = self.parent
        mesh = mat.parent
        if mat.parent:
            obj = mesh.original_object
            for collection in obj.users_collection:
                if collection.collection_type == '1':
                    # render modes have to be these exact values to fix small stitching issues
                    if mat.scroll_x or mat.scroll_y:
                        self.render_mode_1 &= 0xFFFFFFEF
                        self.render_mode_2 &= 0xFFFFFFEF
                    else:
                        self.render_mode_1 = 0b1100000010000010000000001000 
                        self.render_mode_2 = 0b11000000100010000000001000
                    break
        
        
        
        return self
    
    def to_array(self):
        return [self.unk1, self.combiner_cycle_type, self.color_combine_mode_cycle1, self.alpha_combine_mode_cycle1, self.color_combine_mode_cycle2, self.alpha_combine_mode_cycle2, self.render_mode_1, self.render_mode_2, self.color.to_array(), self.unk]
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, self.unk1, self.combiner_cycle_type, self.color_combine_mode_cycle1, self.alpha_combine_mode_cycle1, self.color_combine_mode_cycle2, self.alpha_combine_mode_cycle2, self.render_mode_1, self.render_mode_2, 0, 0, 0, 0, 0, 0, 0)
        self.color.write(buffer, cursor + 34)
        return cursor + self.size
    

# MARK: MATERIAL

class Material(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>I4xII')
        self.parent = parent
        self.id = None
        self.model = model
        self.format = 14
        self.name = ""
        #00000001   1   254 1 = lightmap
        #00000010   2   253
        #00000100   4   251 this is on for all formats
        #00001000   8   247 0 = draw backface, 1 = do not draw backface
        #00010000   16  239 1 = lightmap
        #00100000   32  223 
        #01000000   64  191 0 = draw frontface, 1 = do not draw frontface
        #10000000   128     1 = if texture offset is set https://github.com/tim-tim707/SW_RACER_RE/blob/fa8787540055d0bdf422b42e72ccf50cd3d72a07/src/types.h#L1410

        # 0000100 format 4 is only used for engine trail, binder, and flame effects
        # 0000110 format 6 seems to indicate doublesidedness
        # 0000111 format 7
        # 0001100 format 12 is for any kind of skybox material
        # 0001110 14/15/71 are used for a majority
        # 0001111 15
        # 1000110 70
        # 1000111 71
        # 0010111 23/31/87 are used exclusively with texture 35 possibly for sheen
        # 0011111
        # 1010111
        self.texture = None
        self.texture_image = None
        self.write_location = None
        self.scroll_x = 0
        self.scroll_y = 0
        self.clip_x = 0
        self.clip_y = 0
        self.texture_anim = False
        self.shader = MaterialShader(self, self.model)
        
    def read(self, buffer, cursor):
        self.id = cursor
        self.format, texture_addr, shader_addr = struct.unpack_from(self.format_string, buffer, cursor)
            
        self.texture = MaterialTexture(self, self.model).read(buffer, texture_addr)
        
        # there should always be a shader_addr otherwise game will crash
        assert shader_addr > 0, "Material should have shader"
        self.shader.read(buffer, shader_addr)
        return self
        
    def to_array(self):
        return [self.format, 0, 0]
        
    def make(self, remake = False, tex_name = None, mat_name = "Unnamed Material"):
        material = None
        if self.id is not None:
            mat_name = str(self.id)
            material = bpy.data.materials.get(mat_name)
        if material is not None and not remake:
            return material
        if not remake or material is None:
            material = bpy.data.materials.new(mat_name)
            
        material.use_nodes = True
        material.node_tree.nodes.clear()
        output_node = material.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
        node_0 = material.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        node_0.inputs[0].default_value = [c/255 for c in self.shader.color.to_array()]
        material.material_color = [c/255 for c in self.shader.color.to_array()]
        material.node_tree.links.new(node_0.outputs['BSDF'], output_node.inputs['Surface'])
        material['id'] = self.id
        material['format'] = self.format
        
        if (self.texture is not None or tex_name is not None):
            tex_name = tex_name if tex_name is not None else str(self.texture.id)

            material['scroll_x'] = self.scroll_x
            material['scroll_y'] = self.scroll_y
            material['clip_x'] = self.clip_x
            material['clip_y'] = self.clip_y
            
            material.blend_method = 'OPAQUE'
            self.shader.make(material)
            
            if self.texture and self.texture.format == 3:
                material.blend_method = 'BLEND'
            if (self.format & 8):
                material.use_backface_culling = True
            
            node_1 = material.node_tree.nodes.new("ShaderNodeTexImage")
            node_2 = material.node_tree.nodes.new("ShaderNodeVertexColor")
            node_3 = material.node_tree.nodes.new("ShaderNodeMixRGB")
            node_3.blend_type = 'MULTIPLY'
            node_3.inputs['Fac'].default_value = 1
            material.node_tree.links.new(node_1.outputs["Color"], node_3.inputs["Color2"])
            material.node_tree.links.new(node_2.outputs["Color"], node_3.inputs["Color1"])
            material.node_tree.links.new(node_3.outputs["Color"], node_0.inputs["Base Color"])
            material.node_tree.links.new(node_1.outputs["Alpha"], node_0.inputs["Alpha"])
            node_0.inputs["Specular IOR Level"].default_value = 0

            if self.scroll_x != 0 or self.scroll_y != 0:
                shader_node = material.node_tree.nodes.new("ShaderNodeTexCoord")
                mapping_node = material.node_tree.nodes.new("ShaderNodeMapping")
                material.node_tree.links.new(shader_node.outputs["UV"], mapping_node.inputs["Vector"])
                material.node_tree.links.new(mapping_node.outputs["Vector"], node_1.inputs["Vector"])
                
                keyframes = [0, abs(self.scroll_x) if self.scroll_x != 0 else abs(self.scroll_y)]
                poses = [0, 1]
                
                if self.scroll_x < 0 or self.scroll_y < 0:
                    poses.reverse()
                
                for i, time in enumerate(keyframes):
                    default_value = [0, 0, 0]
                    if self.scroll_x: 
                        default_value[0] = poses[i]
                    elif self.scroll_y: 
                        default_value[1] = poses[i]
                        
                    mapping_node.inputs[1].default_value = default_value
                    mapping_node.inputs[1].keyframe_insert(data_path="default_value", frame = time * (bpy.context.scene.render.fps if remake else self.model.fps))
                
                if material.node_tree.animation_data is not None and material.node_tree.animation_data.action is not None:
                    for fcurves_f in material.node_tree.animation_data.action.fcurves:
                        for k in fcurves_f.keyframe_points:
                            k.interpolation = 'LINEAR'
            
            # NOTE: probably shouldn't do it this way
            # TODO: find specific tag
            if tex_name in ["1167", "1077", "1461", "1596"]:
                material.blend_method = 'BLEND'
                material.node_tree.links.new(node_1.outputs["Color"], node_0.inputs["Alpha"])
            
            if self.format in [31, 15, 7]:
                material.node_tree.links.new(node_2.outputs["Color"], node_0.inputs["Normal"])
                material.node_tree.links.new(node_1.outputs["Color"], node_0.inputs["Base Color"])
            
            chunk_tag = self.texture.chunks[0].unk1 if self.texture and len(self.texture.chunks) else 0
            if(self.texture and self.texture.chunks and chunk_tag & 0x11 != 0):
                node_4 = material.node_tree.nodes.new("ShaderNodeUVMap")
                node_5 = material.node_tree.nodes.new("ShaderNodeSeparateXYZ")
                node_6 = material.node_tree.nodes.new("ShaderNodeCombineXYZ")
                material.node_tree.links.new(node_4.outputs["UV"], node_5.inputs["Vector"])
                material.node_tree.links.new(node_6.outputs["Vector"], node_1.inputs["Vector"])

                if self.scroll_x or self.scroll_y:
                    material.node_tree.links.new(mapping_node.outputs["Vector"], node_5.inputs["Vector"])

                if(chunk_tag & 0x1):
                    material.flip_x = True
                if(chunk_tag & 0x10):
                    material.flip_y = True
                if(chunk_tag & 0x2):
                    material.clip_x = True
                if(chunk_tag & 0x20):
                    material.clip_y = True
                    
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

            b_tex = bpy.data.images.get(tex_name)
            if b_tex is None and self.texture:
                b_tex = self.texture.make()
            
            image_node = material.node_tree.nodes["Image Texture"]
            image_node.image = b_tex
            
            if self.texture_anim: # TODO
                bpy.data.images.load("C:/Users/louri/Documents/Github/test/textures/0.png", check_existing=True)
                image_node.image = bpy.data.images.get('0.png')
                bpy.data.images["0.png"].source = 'SEQUENCE'
                node_1.image_user.use_auto_refresh = True
                node_1.image_user.frame_duration = 1
                for f in range(anim[child]['num_keyframes']):
                    node_1.image_user.frame_offset = anim[child]['keyframe_poses'][f] - 1
                    node_1.image_user.keyframe_insert(data_path="frame_offset", frame = round(anim[child]['keyframe_times'][f] * (bpy.context.scene.render.fps if remake else self.model.fps)))
                if material.node_tree.animation_data is not None and material.node_tree.animation_data.action is not None:
                    for fcurves_f in material.node_tree.animation_data.action.fcurves:
                        #new_modifier = fcurves_f.modifiers.new(type='CYCLES')
                        for k in fcurves_f.keyframe_points:
                            k.interpolation = 'CONSTANT'
            material.preview_render_type = 'FLAT'
            return material
        else:
            node_1 = material.node_tree.nodes.new("ShaderNodeVertexColor")
            node_0.inputs["Specular IOR Level"].default_value = 0
            material.node_tree.links.new(node_1.outputs["Color"], node_0.inputs["Base Color"])
            material.preview_render_type = 'FLAT'
            return material

    def unmake(self, material):
        material_name: str = ""
        
        self.shader.unmake(material)
        if material:
            self.name = material.name
            
            material_name = material.name #.split(".")[0]
            self.id = material_name
            if self.model and material_name in self.model.materials:
                return self.model.materials[material_name]
            
            self.scroll_x = material.get('scroll_x', 0.0)
            self.scroll_y = material.get('scroll_y', 0.0)
            self.clip_x = material.get('clip_x', False)
            self.clip_y = material.get('clip_y', False)
            
            # if material.node_tree:
            for node in material.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    self.texture = MaterialTexture(self, self.model).unmake(node.image)

            if hasattr(material, 'id') and material['id']:
                self.id = material.get('id')

            if material.flip_x:
                self.texture.chunks[0].unk1 |= 0x01
            if material.flip_y:
                self.texture.chunks[0].unk1 |= 0x10
            if material.clip_x:
                self.texture.chunks[0].unk1 |= 0x02
            if material.clip_y:
                self.texture.chunks[0].unk1 |= 0x20

            # get animations
            if self.model:
                if material.scroll_x:
                    poses = [0, 1] if material.scroll_x < 0 else [1, 0]
                    times = [0, abs(material.scroll_x) * self.model.fps]
                    self.model.animations.append(Anim(self, self.model).unmake(times, poses, 'uv_x', loop = True))
                if material.scroll_y:
                    poses = [0, 1] if material.scroll_y < 0 else [1, 0]
                    times = [0, abs(material.scroll_y) * self.model.fps]
                    self.model.animations.append(Anim(self, self.model).unmake(times, poses, 'uv_y', loop = True))
        
            self.format = material.get('format')
            if self.format is None:
                self.format = 14
                
            if material.use_backface_culling == False:
                self.format &= 0b11110111
        
        if self.model: 
            self.model.materials[material_name] = self
            return self.model.materials[material_name]
        else:
            return self

    def write(self, buffer, cursor):
        material_start = cursor
        self.write_location = cursor
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
    def remake(self, material, tex_name = None):
        self.unmake(material)
        material = self.make(remake = True, tex_name = tex_name)
        return material

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
    
def get_uv_bounds(uv_coords):
    if not uv_coords or len(uv_coords) == 0:
        return 0, 0, 0, 0
    
    """Calculate the bounding box of UV coordinates."""
    min_u = min(uv[0] for uv in uv_coords)
    max_u = max(uv[0] for uv in uv_coords)
    min_v = min(uv[1] for uv in uv_coords)
    max_v = max(uv[1] for uv in uv_coords)
    return min_u, max_u, min_v, max_v

def is_within_bounds(uv_coords, max_tile_size):
    """Check if UV bounding box is within the size limit."""
    min_u, max_u, min_v, max_v = get_uv_bounds(uv_coords)
    return (max_u - min_u <= max_tile_size) and (max_v - min_v <= max_tile_size)

def subdivide_face(bm, face, uv_layer, max_tile_size):
    """Subdivide a single face until it fits within the UV bounds."""
    while True:
        uv_coords = [loop[uv_layer].uv for loop in face.loops]
        if is_within_bounds(uv_coords, max_tile_size):
            break
        bmesh.ops.subdivide_edges(
            bm,
            edges=face.edges,
            cuts=1,
            use_grid_fill=True
        )

def subdivide_face_to_tris(bm, face, cuts=1):
    """
    Subdivide 'face' by splitting its boundary edges, without grid fill,
    then triangulate only the faces impacted by the split.

    Returns:
        set[BMFace]: the set of faces affected by the operation (post-op objects).
    """
    if not face.is_valid:
        return set()

    # Subdivide only the face’s boundary edges; avoid spreading quads/ngons
    res = bmesh.ops.subdivide_edges(
        bm,
        edges=list(face.edges),
        cuts=cuts,
        use_grid_fill=False,
        use_only_quads=False,
        use_single_edge=False,
    )

    # Collect affected faces from the op result
    affected = set()
    for key in ("geom", "geom_inner", "geom_split"):
        if key in res and res[key]:
            for elem in res[key]:
                if isinstance(elem, bmesh.types.BMFace) and elem.is_valid:
                    affected.add(elem)
                elif isinstance(elem, bmesh.types.BMEdge) and elem.is_valid:
                    # include neighbors touched by newly split edges
                    for lf in elem.link_faces:
                        if lf.is_valid:
                            affected.add(lf)

    # If the result dict didn't include much, fall back to faces around the original boundary
    if not affected and face.is_valid:
        for e in face.edges:
            for lf in e.link_faces:
                if lf.is_valid:
                    affected.add(lf)

    # Triangulate only the local region
    if affected:
        bmesh.ops.triangulate(
            bm,
            faces=list(affected),
            quad_method='BEAUTY',
            ngon_method='BEAUTY'
        )

    # Refresh lookup tables after topology ops
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Filter to valid faces after triangulation (in case any handles changed)
    return {f for f in affected if f.is_valid}

def get_uv_islands(obj, max_tile_size=16):
    """Retrieve UV islands while limiting their size to max_tile_size, including vertex color data.
       Ensures triangles by locally triangulating regions affected by subdivision (Option A)."""
    if obj.type != 'MESH' or not obj.data.uv_layers.active:
        return []

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Lookup tables for safe indexed access
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv.active

    # Verify the active vertex color layer (if present)
    color_layer = None
    if obj.data.vertex_colors:
        # verify() will create if missing; safe for reading loop colors
        color_layer = bm.loops.layers.color.verify()

    islands = []

    # IMPORTANT: snapshot of faces; we will manage newly created faces by seeding DFS manually
    original_faces = list(bm.faces)

    # Use object references (BMFace) for visited to avoid brittle index-tracking across topology changes
    visited_faces = set()

    for face in original_faces:
        # Skip if the face got invalidated by earlier ops
        if not face.is_valid or face in visited_faces:
            continue

        # Determine seed set for DFS (either the face itself, or the affected region if subdivided)
        seed_faces = {face}

        # Subdivide if UV bounds exceed tile size; then seed with affected faces
        uv_coords = [loop[uv_layer].uv.copy() for loop in face.loops]
        if not is_within_bounds(uv_coords, max_tile_size):
            affected = subdivide_face_to_tris(bm, face, cuts=1)
            seed_faces = affected or {face}

        # Start a new island group
        stack = list(seed_faces)
        current_island = []
        island_uvs = []

        while stack:
            current_face = stack.pop()

            # Validity + visited checks
            if not current_face.is_valid or current_face in visited_faces:
                continue

            # Enforce triangulation invariant
            assert len(current_face.verts) == 3, (
                f"Non-triangular face found after subdivision/triangulation in object "
                f"{obj.name}, face index {current_face.index} with {len(current_face.verts)} vertices."
            )

            visited_faces.add(current_face)

            # UV bound check for island growth
            current_uv_coords = [loop[uv_layer].uv.copy() for loop in current_face.loops]
            combined_uvs = island_uvs + current_uv_coords

            if not is_within_bounds(combined_uvs, max_tile_size):
                # Commit the current island and start a new one
                if current_island:
                    islands.append(current_island)
                current_island = []
                island_uvs = []

            # Add the current face data
            face_data = {
                "face_index": current_face.index,
                "vertices": [v.co.copy() for v in current_face.verts],
                "uvs": current_uv_coords,
                "colors": [
                    [] if not color_layer else tuple(loop[color_layer])
                    for loop in current_face.loops
                ],
            }
            current_island.append(face_data)
            island_uvs.extend(current_uv_coords)

            # Traverse adjacent faces (topological neighbors); your comment says "shared UVs"
            # but the original code used edge adjacency, so we keep that behavior.
            for edge in current_face.edges:
                for linked_face in edge.link_faces:
                    if linked_face.is_valid and linked_face not in visited_faces:
                        # Sanity: ensure neighbor remains triangulated
                        assert len(linked_face.verts) == 3, (
                            f"Non-triangular linked face in object {obj.name}, "
                            f"face index {linked_face.index} with {len(linked_face.verts)} vertices."
                        )
                        stack.append(linked_face)

        # Commit island at the end of this region
        if current_island:
            islands.append(current_island)

    # Write back and free
    bm.to_mesh(mesh)
    bm.free()
    return islands
    
def get_object_view_layer_visibility(obj):
    if obj is None or not isinstance(obj, bpy.types.Object):
        return None

    visibility = 0
    
    for i, view_layer in enumerate(bpy.context.scene.view_layers):
        if i == 0: #skip working layer
            continue
        if not obj.hide_get(view_layer = view_layer):
            visibility = visibility | (1 << (i - 1 + 8))
    
    return visibility
    
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
    
# MARK: MESH
    
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
        self.write_location = None
        self.original_object = None
        self.layers = 0xFFFFFF00
        
    def has_visuals(self):
        return self.visuals_vert_buffer is not None and self.visuals_index_buffer is not None
    
    def has_collision(self):
        return self.collision_vert_buffer is not None and self.collision_vert_buffer.length >= 3
    
    def has_trigger(self):
        return self.collision_tags is not None and len(self.collision_tags.triggers)
    
    def has_transparency(self):
        return self.material is not None and self.material.shader.render_mode_1 & 0x800 > 0
    

    
    def split(self):
        vis = Mesh(self.parent, self.model)
        col = Mesh(self.parent, self.model)
        
        vis.material = self.material
        vis.group_parent_id = self.group_parent_id
        vis.visuals_index_buffer = self.visuals_index_buffer
        vis.visuals_vert_buffer = self.visuals_vert_buffer
        vis.group_count = self.group_count
        
        col.collision_tags = self.collision_tags
        col.strip_count = self.strip_count
        col.strip_size = self.strip_size
        col.vert_strips = self.vert_strips
        col.collision_vert_buffer = self.collision_vert_buffer
        
        vis.original_object = self.original_object
        vis.bounding_box = MeshBoundingBox(self, self.model).unmake(vis)
        
        col.original_object = self.original_object
        col.bounding_box = MeshBoundingBox(self, self.model).unmake(col)
        return [vis, col]
        
    def join(self, vis, col):
        self.material = vis.material
        self.collision_tags = col.collision_tags
        self.strip_count = col.strip_count
        self.strip_size = col.strip_size
        self.vert_strips = col.vert_strips
        self.group_parent_id = vis.group_parent_id
        self.collision_vert_buffer = col.collision_vert_buffer
        self.visuals_index_buffer = vis.visuals_index_buffer
        self.visuals_vert_buffer = vis.visuals_vert_buffer
        self.group_count = vis.group_count
        
        self.original_object = vis.original_object
        self.bounding_box = MeshBoundingBox(self, self.model).unmake(self)
        return self
    
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
            b_obj = bpy.data.objects.new(mesh_name, mesh)
            
            b_obj.collidable = True   
            b_obj.id = str(self.id)
            b_obj.scale = [self.model.scale, self.model.scale, self.model.scale]

            collection.objects.link(b_obj)
            mesh.from_pydata(verts, edges, faces)
            b_obj.parent = parent

            if(self.collision_tags is not None): 
                self.collision_tags.make(b_obj, collection)
                
            for i in range(24):
                view_layer = bpy.context.scene.view_layers[i + 1]
                if 'col_flags' in parent or parent.col_flags:
                    b_obj.hide_set(not bool(int(parent['col_flags']) & (1 << (i + 8))), view_layer = view_layer)            
                
        if self.has_visuals():
            
            verts = self.visuals_vert_buffer.make()
           
            edges = []
            faces = self.visuals_index_buffer.make()
            mesh_name = '{:07d}'.format(self.id) + "_" + "visuals"
            mesh = bpy.data.meshes.new(mesh_name)
            b_obj = bpy.data.objects.new(mesh_name, mesh)
            b_obj.visible = True
            b_obj.id = str(self.id)
            b_obj.scale = [self.model.scale, self.model.scale, self.model.scale]

            collection.objects.link(b_obj)
            mesh.from_pydata(verts, edges, faces)
            mesh.validate() #clean_customdata=False
            b_obj.parent = parent
            
            if self.material:
                mat = self.material.make()
                mesh.materials.append(mat)
            
            #set vector colors / uv coords
            uv_layer = mesh.uv_layers.new(name = 'uv')
            color_layer = mesh.vertex_colors.new(name = 'colors') #color layer has to come after uv_layer
            
            mesh.attributes.render_color_index = b_obj.data.attributes.active_color_index
            # no idea why but 4.0 requires I do this:
            uv_layer = b_obj.data.uv_layers.active.data
            color_layer = b_obj.data.vertex_colors.active.data                
            for poly in mesh.polygons:
                for p in range(len(poly.vertices)):
                    v = self.visuals_vert_buffer.data[poly.vertices[p]]
                    uv_layer[poly.loop_indices[p]].uv = [u/4096 for u in v.uv]
                    color_layer[poly.loop_indices[p]].color = [a/255 for a in v.color.to_array()]
                    
            for i in range(24):
                view_layer = bpy.context.scene.view_layers[i + 1]
                if 'vis_flags' in parent or parent.vis_flags:
                    b_obj.hide_set(not bool(int(parent['vis_flags']) & (1 << (i+8))), view_layer = view_layer)
    

        
    
    def unmake(self, node, unmake_anim = True):
        self.original_object = node
        
        if node.get('visible') is None and node.get('collidable') is None:
            if self.model.type == '7':
                node.collidable = True
            node.visible = True        

        self.id = node.name
        self.layers = get_object_view_layer_visibility(node) & 0xFFFFFF00
        
        # ensure mesh is triangulated
        triangulate_mesh([node])
        
        if unmake_anim:
            get_animations(node, self.model, self)

        if node.visible:
            
            #find material
            material = None
            for slot in node.material_slots:
                material = slot.material
                if material:
                    self.material = Material(self, self.model).unmake(material)
                    break
                
            if material is None:
                self.material = Material(self, self.model).unmake(None)
            
            self.visuals_vert_buffer = VisualsVertBuffer(self, self.model).unmake(node)
            verts = self.visuals_vert_buffer.data
            faces = [[v for v in face.vertices] for face in node.data.polygons]
            
            if not len(faces) or not len(verts):
                return None

            print('raw faces', [len(face) for face in faces])

            # fix uvs
            if self.material and self.material.texture:
                uv_islands = get_uv_islands(node)
                new_faces = []
                
                for i, island in enumerate(uv_islands):
                    #shift uvs back in bounds
                    uvs = [uv for face in island for uv in face["uvs"]]
                    min_u, max_u, min_v, max_v = get_uv_bounds(uvs)
                    UV_MAX_SIZE = 8
                    UV_MIN_SIZE = -8
                    uv_min = [min_u, min_v]
                    uv_max = [max_u, max_v]
                    uv_offset = [0, 0]
                    for i in range(2):
                        if uv_min[i] < UV_MIN_SIZE:
                            uv_offset[i] += math.ceil(UV_MIN_SIZE - uv_min[i])
                        if uv_max[i] > UV_MAX_SIZE:
                            uv_offset[i] -= math.ceil(uv_max[i] - UV_MAX_SIZE)
                    
                                                
                    # reindex verts and faces
                    for face in island:
                        new_face = []
                        #create vertices
                        
                        if len(face['vertices']) > 3:
                            raise Exception(f"Failed to correct vertices for UVs in {node.name}")
                        
                        for j, index in enumerate(face['vertices']):
                            uv = [x + y for x, y in zip(uv_offset, face['uvs'][j])]
                            vert = VisualsVertChunk(self.visuals_vert_buffer, self.model).unmake(
                                co = face['vertices'][j], 
                                uv = uv,
                                color = face['colors'][j]
                                )
                            new_face.append(vert)
                        new_faces.append(new_face)
                faces = new_faces
            else:
                # replace each index with its vert
                faces = [[verts[i] for i in face] for face in faces]
            
            #TODO: Automatically split meshes?
            assert len(faces) <= 2048, f"Max faces reached in {node.name} {len(new_faces)}/2048"
            
            print('uv_corrected_faces', [len(face) for face in faces])
            
            # reorder faces to maximize shared edges
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
                    
            # relist vertices so indices aren't too far apart    
            new_verts = []
            new_faces = []
            for face in ordered_faces:
                new_face = []
                for vert in face:
                    current_index = len(new_verts)
                    index = -1
                    # find last instance of vert
                    try:
                        index = current_index - new_verts[::-1].index(vert) - 1
                    except ValueError:
                        index = -1

                    if index > -1 and current_index - index < 60: #FIXME figure out what value this should be
                        new_face.append(index)
                    else: 
                        new_verts.append(vert)
                        new_face.append(current_index)

                new_faces.append(new_face)
                
            # TODO: check if node has vertex group
            if False:
                r_mesh.group_parent = None
                r_mesh.group_count = None

            self.visuals_vert_buffer.data = new_verts
            
            self.visuals_index_buffer = VisualsIndexBuffer(self, self.model).unmake(new_faces)
            #return True

        if node.collidable:
            
            if node.collision_data:
                self.collision_tags = CollisionTags(self, self.model).unmake(node)
            
            self.collision_vert_buffer = CollisionVertBuffer(self, self.model).unmake(node)
            self.vert_strips = CollisionVertStrips(self, self.model).unmake(node)
            
            faces = [[v for v in face.vertices] for face in node.data.polygons]
            verts = self.collision_vert_buffer.data

            if len(faces) == 0:
                return None

            # replace each index with its vert
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

            # restrip mesh
            strips = []
            new_verts = []
            strip = []
            strip.append(faces.pop(0))
            strip_verts = []
            while len(faces):
                last_face = strip[-1]
                shared = None

                # search for a suitable adjacent face to continue strip
                for f, face in enumerate(faces):
                    # ignore faces with less than 2 shared verts
                    if len([i for i in face if i in last_face]) < 2:
                        continue

                    # the faces mush share an edge, and it must run opposite to ensure same normals
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

                    # additionally, we need to check that the shared edge is opposite the third to last vert
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
        self.write_location = cursor
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
            #byte align (otherwise game will crash)
            cursor += 4 - (cursor % 4)
                
        if self.material:
            self.model.highlight(mesh_start)
            if self.material.write_location:
                mat_addr = self.material.write_location
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
    assert node_class, f"Invalid node type {node_type}"    
    return node_class(parent, model, node_type)
    
# MARK: NODE
    
class Node(DataStruct):
    
    def __init__(self, parent, model, type, header = []):
        super().__init__('>7I')
        self.parent = parent
        self.type = type
        self.id = None
        self.head = []
        self.children = []
        self.AltN = []
        self.header = []
        if len(header):
            self.header.extend(header)
        self.node_type = type
        self.vis_flags = 0xFF
        self.col_flags = 0xFF
        self.flags_set = False
        self.unk1 = 0
        self.unk2 = 0
        self.model = model
        self.child_count = 0
        self.child_start = None
        self.original_object = None
        self.write_location = None
        
    def read(self, buffer, cursor):
        self.id = cursor
        self.node_type, self.vis_flags, self.col_flags, self.unk1, self.unk2, self.child_count, self.child_start = struct.unpack_from(self.format_string, buffer, cursor)
        
        if self.model.AltN and cursor in self.model.AltN:
            self.AltN = [i for i, h in enumerate(self.model.AltN) if h == cursor]
        
        if cursor in self.model.header.offsets:
            self.header = [i for i, h in enumerate(self.model.header.offsets) if h == cursor]
            if self.model.type == '7' and 2 in self.header:
                self.skybox = True

        if not self.model.ref_map.get(self.id):
            self.model.ref_map[self.id] = True
        
        for i in range(self.child_count):
            child_address = readUInt32BE(buffer, self.child_start + i * 4)
            if not child_address:
                #print('no child adress for child', i, 'on node', self.id)
                if (self.child_start + i * 4) in self.model.AltN:
                    self.children.append({'id': self.child_start + i * 4, 'AltN': True})
                else:
                    self.children.append({'id': None})  # remove later
                continue

            # if child_address < self.id:
            #     print('reference to previous node', child_address, 'on child', i, 'for node', self.id)

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
        
        if self.model.type == '7':
            if 0 in self.header:
                track_collection = bpy.data.collections.new('Track')
                track_collection.collection_type = "0"
                collection.children.link(track_collection)
                collection = track_collection
            elif 2 in self.header:
                skybox_collection = bpy.data.collections.new('Skybox')
                skybox_collection.collection_type = "1"
                collection.children.link(skybox_collection)
                collection = skybox_collection
        # elif self.model.type == "4":
        #     if self.header:
        #         header_id = self.header[0]
        #         podd_collection = bpy.data.collections.new(str(header_id))
        #         #podd_collection.collection_type = str(2 + header_id)
        #         collection.children.link(podd_collection)
        #         collection = podd_collection
        
        if self.type in [53349, 53350]:
            b_node = bpy.data.objects.new(name, None)
            collection.objects.link(b_node)
            #new_empty.empty_display_size = 2
            if self.unk1 &  1048576 != 0:
                b_node.empty_display_type = 'ARROWS'
                b_node.empty_display_size = 0.5
                
            elif self.unk1 & 524288 != 0:
                b_node.empty_display_type = 'CIRCLE'
                b_node.empty_display_size = 0.5
            else:
                b_node.empty_display_type = 'PLAIN_AXES'

                 
        else:
            b_node = bpy.data.objects.new(name, None)
            #new_empty.empty_display_type = 'PLAIN_AXES'
            b_node.empty_display_size = 0
            collection.objects.link(b_node)

        #set group tags
        b_node.id  = str(self.id)
        b_node['node_type'] = self.node_type
        b_node['vis_flags'] = str(self.vis_flags)
        b_node['col_flags'] = str(self.col_flags)
        b_node['unk1'] = self.unk1
        b_node['unk2'] = self.unk2
            
        #assign parent
        if parent is not None:
            b_node.parent = parent
                
        
        for node in self.children :
            if not isinstance(node, dict):
                node.make(b_node, collection)
            
        if self.id in self.model.header.offsets:
            b_node['header'] = [i for i, e in enumerate(self.model.header.offsets) if e == self.id]
            
        for i in range(24):
            view_layer = bpy.context.scene.view_layers.get(f"VisLayer_{i}")
            b_node.hide_set(not bool(self.vis_flags & (1 << (i + 8))), view_layer = view_layer)
            
        return b_node
    def unmake(self, node, unmake_children = False):
        self.id = node.name
        self.original_object = node
            
        if node.type == 'EMPTY':
            self.node_type = 53349
            
        get_animations(node, self.model, self)
            
        if 'unk1' in node:
            self.unk1 =  node['unk1']
        if 'unk2' in node:
            self.unk2 = node['unk2']
        # if 'header' in node:
        #     self.header = node['header']
        
        if self.model.type == '7' and 2 in self.header:
            self.skybox = True
        
        if not unmake_children:
            return self
        
        if self.node_type == 12388:
            for child in node.children:
                self.children.extend(Mesh(self, self.model).unmake(child))
        else:
            for child in node.children:
                n = create_node(child['node_type'], self, self.model)
                self.children.append(n.unmake(child))
        
        return self
    
    def write(self, buffer, cursor):
        self.write_location = cursor
        
        #write references to this node in the model header
        for i in self.header:
            struct.pack_into(f">{len(self.header)}I", buffer, 4 + 4*i, *[cursor]*len(self.header))
             
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
            if child is None:
                continue
            #check if child is already written
            if child.write_location:
                writeUInt32BE(buffer, child.write_location, child_ptr)
            else:
                writeUInt32BE(buffer, cursor, child_ptr)
                cursor = child.write(buffer, cursor)
            
        return cursor
    
    def set_flags(self, vis_flags = None, col_flags = None, unk1 = None):
        
        if unk1 is not None:
            self.unk1 = unk1
        if vis_flags is not None or col_flags is not None:
            if vis_flags is not None:
                self.vis_flags = vis_flags
            if col_flags is not None:
                self.col_flags = col_flags
            self.flags_set = True
            return self
        
        if self.type == 12388 and len(self.children):
            has_vis = False
            has_col = False
            for mesh in self.children:
                if mesh.has_collision():
                    has_col = True
                if mesh.has_visuals():
                    has_vis = True
            if not has_col:
                self.col_flags &= 0b11111111111111111111111111111001
            if not has_vis:
                self.vis_flags &= 0b11111111111111111111111111111011
        else:
            self.vis_flags = 0xFFFFFFFF
            self.col_flags = 0xFFFFFFFF
            for child in self.children:
                child.set_flags()
                if self.node_type == [12388]:
                    self.col_flags &= (child.col_flags & 0x000000FF)
                    self.vis_flags &= (child.vis_flags & 0x000000FF)
        return self

class MeshGroup12388(Node):
    
    def __init__(self, parent, model, type, header = []):
        super().__init__( parent,model, type, header)
        self.parent = parent
        self.bounding_box = None
        
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        return self
    
    def make(self, parent = None, collection = None):
        #avoid making visuals and collision that is not used in game
        if str(self.model.id) in showbytes:
            showbyte = showbytes[str(self.model.id)]
            unused = showbyte != None and (showbyte & self.col_flags == 0)
            
            if unused:
                return None
        
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
    #NodeTransformed  https://github.com/tim-tim707/SW_RACER_RE/blob/fa8787540055d0bdf422b42e72ccf50cd3d72a07/src/types.h#L1290
    def __init__(self, parent, model, type, header = []):
        super().__init__(parent, model, type, header)
        self.parent = parent
        self.matrix = FloatMatrix()
        self.matrix.data[0].data[0] = 1.0
        self.matrix.data[1].data[1] = 1.0
        self.matrix.data[2].data[2] = 1.0
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.matrix = FloatMatrix(struct.unpack_from(">12f", buffer, cursor+28))
        return self
    def make(self, parent = None, collection = None):
        empty = super().make(parent, collection)
        empty.matrix_world = self.matrix.make(self.model.scale)
        return empty
    def unmake(self, node):
        super().unmake(node)
        matrix = node.matrix_local
        #need to transpose the matrix
        matrix = list(map(list, zip(*matrix)))
        self.matrix.unmake(matrix, self.model.scale)
        return self
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_info_start = cursor - 8
        cursor = self.matrix.write(buffer, cursor)
        cursor = super().write_children(buffer, cursor, child_info_start)
        return cursor
        
class Group53349(Node):
    #NodeTransformedWithPivot https://github.com/tim-tim707/SW_RACER_RE/blob/fa8787540055d0bdf422b42e72ccf50cd3d72a07/src/types.h#L1296
    def __init__(self, parent, model, type, header = []):
        super().__init__(parent, model, type, header)
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
    def unmake(self, node, make_children = False):
        super().unmake(node, False)
        matrix = node.matrix_local
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
    # NodeTransformedComputed https://github.com/tim-tim707/SW_RACER_RE/blob/fa8787540055d0bdf422b42e72ccf50cd3d72a07/src/types.h#L1304
    # parents to camera
    def __init__(self, parent, model, type, header = []):
        super().__init__(parent, model, type, header)
        self.parent = parent
        self.follow_position = 0
        # 1 = follow camera
        self.track_position = 0
        # 0 = disabled
        # 1 = z (yaw)
        # 2 = z + x + y (yaw + pitch+ roll)
        # 3 = z + x (yaw + pitch)
        self.up_vector = FloatVector([0.0,0.0,1.0])

    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.follow_position, self.track_position = struct.unpack_from(">hh12x", buffer, cursor+28)
        self.up_vector.read(buffer, cursor + 32)
        return self
    def make(self, parent = None, collection = None):
        new_empty = super().make(parent, collection)
        new_empty['follow_position'] = self.follow_position
        new_empty['track_position'] = self.track_position
        return new_empty
    def unmake(self, node):
        super().unmake(node)
        self.node_type = 53350
        if 'follow_position' in node:
            self.follow_position = node['follow_position']
        if 'track_position' in node:
            self.track_position = node['track_position']
        return self
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_data_start = cursor - 8
        struct.pack_into('>hh12x', buffer, cursor, self.follow_position, self.track_position)
        self.up_vector.write(buffer, cursor+4)
        cursor += struct.calcsize('>hh12x')
        
        cursor = super().write_children(buffer, cursor, child_data_start)
        
        return cursor
  
class Group20580(Node):
    
    def __init__(self, parent, model, type, header = []):
        super().__init__(parent, model, type, header)
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
    #NodeSelector https://github.com/tim-tim707/SW_RACER_RE/blob/fa8787540055d0bdf422b42e72ccf50cd3d72a07/src/types.h#L1273
    def __init__(self, parent, model, type, header = []):
        super().__init__(parent, model, type, header)
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
    #NodeLODSelector https://github.com/tim-tim707/SW_RACER_RE/blob/fa8787540055d0bdf422b42e72ccf50cd3d72a07/src/types.h#L1283
    def __init__(self, parent, model, type, header = []):
        super().__init__( parent,model, type, header)
        self.floats = [] #LOD distances
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
        cursor += 11*4
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
        light.LStr = True
        light_object = bpy.data.objects.new(name = "lightstreak", object_data = light)
        self.model.collection.objects.link(light_object)
        light_object.location = (self.data.data[0]*self.model.scale, self.data.data[1]*self.model.scale, self.data.data[2]*self.model.scale)
        
    def unmake(self, obj):
        self.data.from_array([x/self.model.scale for x in obj.matrix_world.to_translation()])
        return self    

    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, *self.data.to_array())
        writeString(buffer, "LStr", cursor)
        return cursor + self.size
        
class ModelData():
    def __init__(self, parent, model):
        self.parent = parent
        self.data = []
        self.model = model
    def read(self, buffer, cursor):
        cursor += 4
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
        # TODO: only get objects from collection
        for obj in bpy.data.objects:
            if obj.type == 'LIGHT' and obj.data.LStr:
                self.data.append(LStr(self, self.model).unmake(obj))
        return self
    def write(self, buffer, cursor):
        
        if not len(self.data):
            return cursor
        
        
        cursor = writeString(buffer, "Data", cursor)
        sizeAddress = cursor
        cursor += 4
        for thing in self.data:
            cursor = thing.write(buffer, cursor)
        size = int((cursor - (sizeAddress+4))/4)
        writeUInt32BE(buffer, size, sizeAddress)
        
        return cursor
    

class LocationPose(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>3f')
        
        self.parent = parent
        self.model = model
        self.data = FloatPosition()
        
    def read(self, buffer, cursor):
        x, y, z = struct.unpack_from(self.format_string, buffer, cursor)
        self.data.from_array([x, y, z])
        return self
    
    def make(self, target, time):
        target.location = [x*self.model.scale for x in self.data.to_array()]
        target.keyframe_insert(data_path="location", frame = round(time * self.model.fps))
    
    def unmake(self, pose):
        self.data.from_array([x/self.model.scale for x in pose])
        return self
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, *self.data.to_array())
        return cursor + self.size
    
    def to_array(self):
        return self.data.to_array()
    
class RotationPose(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>4f')
        
        self.parent = parent
        self.model = model
        self.data = []
        self.previous = None
        self.R = None
    
    def make(self, target, time):
        axis = self.data[:3]
        angle = self.data[3]*math.pi/180
        R = mathutils.Matrix.Rotation(angle, 4, axis)
        R = R.to_quaternion()
        self.R = R
        
        if self.previous is not None and self.previous.R is not None:
            R.make_compatible(self.previous)
            
        target.rotation_quaternion = R
        target.keyframe_insert(data_path="rotation_quaternion", frame = round(time * self.model.fps))
    
    def unmake(self, pose):
        q = mathutils.Quaternion(pose)
        axis, angle = q.to_axis_angle()    
        self.data = [*axis, angle*180/math.pi]
    
        return self
    
class UVPose(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>f')
        
        self.parent = parent
        self.model = model
        self.data = []
    
    def make(self, target, time):
        add_nodes = False
        
        for node in target.node_tree.nodes:
            if isinstance(node, bpy.types.ShaderNodeTexImage):
                node_1 = node
            elif isinstance(node, bpy.types.ShaderNodeTexCoord):
                add_nodes = True
                shader_node = node
            elif isinstance(node, bpy.types.ShaderNodeMapping):
                add_nodes = True
                mapping_node = node
                
        if add_nodes:
            shader_node = target.node_tree.nodes.new("ShaderNodeTexCoord")
            mapping_node = target.node_tree.nodes.new("ShaderNodeMapping")
            target.node_tree.links.new(shader_node.outputs["UV"], mapping_node.inputs["Vector"])
            target.node_tree.links.new(mapping_node.outputs["Vector"], node_1.inputs["Vector"])
        
        if self.parent.flag2 == 27: #x animation
            mapping_node.inputs[1].default_value = [1-self.data, 0, 0]
        elif self.parent.flag2 == 28: #y animation
            mapping_node.inputs[1].default_value = [0, 1-self.data, 0]
            
        mapping_node.inputs[1].keyframe_insert(data_path="default_value", frame = time * self.model.fps)
        
        if target.node_tree.animation_data is not None and target.node_tree.animation_data.action is not None:
            for fcurves_f in target.node_tree.animation_data.action.fcurves:
                for k in fcurves_f.keyframe_points:
                    k.interpolation = 'LINEAR'
    
    def unmake(self, pose):
        self.data = [pose]
        return self

    
class TexturePose(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>I')
        
        self.parent = parent
        self.model = model
        
    def read(self, buffer, cursor):
        #self.data = MaterialTexture(self, self.model).read(buffer, cursor)
        return self
    
    def make(self, target):
        pass
    
    def unmake(self, obj):
        pass
        return self
    
    def write(self, buffer, cursor):
        pass
    
    
def get_animations(obj, model, entity):
    if not obj.animation_data:
        return None
    
    if not obj.animation_data.action:
        return None
    
    obj.rotation_mode = 'QUATERNION'
    
    #get all unique keyframes for each fcurve and data path
    keyframes = {}
    for fcurve in obj.animation_data.action.fcurves:
        array_index = fcurve.array_index
        data_path = fcurve.data_path
        
        if data_path not in  keyframes:
            keyframes[data_path] = {"times": [], "poses": {}, "loop": False}
        
        if fcurve.modifiers:
            for mod in fcurve.modifiers:
                if mod.type == 'CYCLES':
                    keyframes[data_path]["loop"] = True
         
        for keyframe in fcurve.keyframe_points:
            frame, value = keyframe.co
            if frame not in keyframes[data_path]['times']: 
                keyframes[data_path]['times'].append(frame)
                if data_path == 'location':
                    keyframes[data_path]['poses'][frame] = [None, None, None]
                elif data_path == 'rotation_quaternion':
                    keyframes[data_path]['poses'][frame] = [None, None, None, None]
                
    # for each keyframe, evaluate values
    for fcurve in obj.animation_data.action.fcurves:
        array_index = fcurve.array_index
        data_path = fcurve.data_path
        for keyframe in keyframes[data_path]['times']:
            if data_path in ['location', 'rotation_quaternion']:
                keyframes[data_path]['poses'][keyframe][array_index] = fcurve.evaluate(keyframe)
                
    # unmake animations
    for path in keyframes:
        times = keyframes[path]['times']
        poses = keyframes[path]['poses'].values()
        if path in ['location', 'rotation_quaternion']:
            model.animations.append(Anim(entity, model).unmake(times, poses, path, loop = keyframes[path]['loop']))
    
class Anim(DataStruct):
    def __init__(self, parent, model):
        super().__init__('>244x3f2HI5f4I')
        
        self.parent = parent
        self.model = model
        self.float1 = 0.0 # floats 1, 2, 3, 5 always match
        self.float2 = 0.0
        self.float3 = 0.0
        self.flag1 = 4352 # always 4352
        self.flag2 = 0
        self.num_keyframes = 0
        self.float4 = 0.0
        self.float5 = 0.0
        self.float6 = 1.0 # always 1
        self.float7 = 0.0 # always 0
        self.float8 = 0.0 # always 0
        self.keyframes = []
        self.keyframe_times = []
        self.keyframe_poses = []
        self.target = 0
        self.unk32 = 1 #1, 4, 5, 6, 34, 52, 58
        
    def to_array(self):
        return [self.float1,self.float2,self.float3,self.flag1,self.flag2,self.num_keyframes,self.float4,self.float5,self.float6,self.float7,self.float8,self.keyframes,self.keyframe_times,self.keyframe_poses,self.target,self.unk32]
    
    def read(self, buffer, cursor):
        self.float1, self.float2, self.float3, self.flag1, self.flag2, self.num_keyframes, self.float4, self.float5, self.float6, self.float7, self.float8, keyframe_times_addr, keyframe_poses_addr, self.target, self.unk2 = struct.unpack_from(self.format_string, buffer, cursor)
        if self.flag2 in [2, 18]:
            self.target = readUInt32BE(buffer, self.target)

        if not keyframe_poses_addr or not keyframe_times_addr:
                return self

        cursor = keyframe_poses_addr
        #get keyframes
        for f in range(self.num_keyframes):
            self.keyframe_times.append(readFloatBE(buffer, keyframe_times_addr + f * 4))
            pose = None
            if self.flag2 & 0b111 == 0b000:  # rotation (4)
                pose = RotationPose(self, self.model).read(buffer, cursor)
            elif self.flag2 & 0b111 == 0b001:  # position (3)
                pose = LocationPose(self, self.model).read(buffer, cursor)
            elif self.flag2 & 0b111 == 0b010:  # texture
                pose = TexturePose(self, self.model).read(buffer, cursor)
            elif self.flag2 & 0b111 == 0b011 or self.flag2 & 0b111 == 0b100:  # uv_x/uv_y (1)
                pose = UVPose(self, self.model).read(buffer, cursor)
            
            if pose is not None:
                self.keyframe_poses.append(pose)
                cursor += pose.size
            else:
                print('unk anim', self.flag2)

        return self
                    
    def make(self):
        #assume we have an object or material to apply animations to
        
        self.loop = self.flag2 & 0x10 > 0
        target = None
        if self.flag2 in [27, 28]: #uv
            target = get_mat_by_id(self.target)
            if target is None:
                return
            
            scroll = self.keyframe_times[1]
            poses = [pose.data for pose in self.keyframe_poses]
            if poses[0] < poses[1]:
                scroll = scroll * -1
            
            if self.flag2 == 27:
                target['scroll_x'] = scroll
            if self.flag2 == 28:
                target['scroll_y'] = scroll
            
            #remake material
            material = Material(None, None).unmake(target)
            material.make(remake = True)

        elif self.flag2 in [2, 18]: #texture
            target = get_mat_by_id(self.target)
            if target is None:
                return
            
            
        elif self.flag2 in [56, 8, 24, 40, 4152]: #rotation
            target = get_obj_by_id(self.target)
            if target is None:
                return
            
            target.rotation_mode = 'QUATERNION'
            previous_q = None
            for i, time in enumerate(self.keyframe_times):
                pose = self.keyframe_poses[i]
                axis = pose.data[:3]
                angle = pose.data[3]*math.pi/180
                R = mathutils.Matrix.Rotation(angle, 4, axis)
                R = R.to_quaternion()
                self.R = R
                
                if previous_q is not None:
                    R.make_compatible(previous_q)
                    
                target.rotation_quaternion = R
                target.keyframe_insert(data_path="rotation_quaternion", frame = round(time * self.model.fps))
                previous_q = R
        
        elif self.flag2 in [57, 41, 25, 4153]: #location
            target = get_obj_by_id(self.target)
            if target is None:
                return

            for i, time in enumerate(self.keyframe_times):
                self.keyframe_poses[i].make(target, time)
            
        if target is None:
            return
        #make linear
        if target.animation_data is not None and target.animation_data.action is not None:
            for fcurve in target.animation_data.action.fcurves:
                if self.loop:
                    fcurve.modifiers.new(type='CYCLES')
                for keyframe in fcurve.keyframe_points:
                    keyframe.interpolation = 'LINEAR'
    
        
    
    
    def unmake(self, times, poses, path, loop = True):
        if self.parent is None:
            return None
        self.target = self.parent
        
        self.keyframe_times = [x/self.model.fps for x in times]
        anim_length = self.keyframe_times[-1]
        
        self.float1 = anim_length
        self.float2 = anim_length
        self.float3 = anim_length
        self.float4 = anim_length
        self.float5 = anim_length
        
        if path == 'location':
            self.flag2 |= 0b1001
            self.keyframe_poses = [LocationPose(self, self.model).unmake(pose) for pose in poses]
        elif path == 'rotation_quaternion':
            self.flag2 |= 0b1000
            self.keyframe_poses = [RotationPose(self, self.model).unmake(pose) for pose in poses] 
        elif path in ['uv_x', 'uv_y']:
            self.flag2 |= 0b1011 if path == 'uv_x' else 0b1100
            self.keyframe_poses = [UVPose(self, self.model).unmake(pose) for pose in poses]
            
        if loop:
            self.flag2 |= 0x10
            
        return self
    
    def write(self, buffer, cursor):
        anim_addr = cursor
        cursor += self.size
        
        self.model.highlight(cursor - 8)
        self.model.highlight(cursor - 12)
        self.model.highlight(cursor - 16)
        
        keyframe_times_addr = cursor
        for time in self.keyframe_times:
            cursor = writeFloatBE(buffer, time, cursor)
        
        keyframe_poses_addr = cursor
        for pose in self.keyframe_poses:
            cursor = pose.write(buffer, cursor)
        struct.pack_into(self.format_string, buffer, anim_addr, self.float1, self.float2, self.float3, self.flag1, self.flag2, len(self.keyframe_times), self.float4, self.float5, self.float6, self.float7, self.float8, keyframe_times_addr, keyframe_poses_addr, self.target.write_location, self.unk32)
        return cursor
    
    def to_array(self):
        return [self.float1, self.float2, self.float3, self.flag1, self.flag2, self.num_keyframes, self.float4, self.float5, self.float6, self.float7, self.float8, self.keyframe_times, *[pose.to_array() for pose in self.keyframe_poses], self.target, self.unk32]
    
class AnimList():
    def __init__(self, parent, model):
        self.parent = parent
        self.data = []
        self.model = model
    def read(self, buffer, cursor):
        cursor += 4
        anim = readUInt32BE(buffer, cursor)
        while anim:
            self.data.append(Anim(self, self.model).read(buffer, anim))
            cursor += 4
            anim = readUInt32BE(buffer, cursor)
        return cursor + 4
    def make(self):
        for anim in self.data:
            anim.make()
    def unmake(self):
        for anim in self.model.animations:
            self.data.append(anim)
        return self    
    
    def write(self, buffer, cursor):
        
        if not len(self.data):
            return cursor
        
        cursor = writeString(buffer, "Anim", cursor)
        self.model.anim_list = cursor
        for anim in self.data:
            self.model.highlight(cursor)
            cursor += 4
        self.model.highlight(cursor)
        return cursor + 4

class ModelHeader():
    def __init__(self, parent, model):
        self.parent = parent
        self.offsets = []
        self.AltN = []
        self.model = model

    def read(self, buffer, cursor):
        type = readString(buffer, cursor)
        self.model.type = get_model_type(type)
        assert self.model.type, f"This model extension was not recognized: {type}"
        
        cursor = 4
        header = readInt32BE(buffer, cursor)

        while header != -1:
            self.offsets.append(header)
            cursor += 4
            header = readInt32BE(buffer, cursor)

        cursor += 4
        header_string = readString(buffer, cursor)
        
        while header_string != 'HEnd':
            assert header_string in ['Data', 'Anim', 'AltN'], f"unexpected header string, {header_string}"
            
            if header_string == 'Data':
                self.model.Data = ModelData(self, self.model)
                cursor = self.model.Data.read(buffer, cursor)
                header_string = readString(buffer, cursor)
            elif header_string == 'Anim':
                self.model.Anim = AnimList(self, self.model)
                cursor = self.model.Anim.read(buffer, cursor)
                header_string = readString(buffer, cursor)
            elif header_string == 'AltN':
                cursor += 4
                AltN = readInt32BE(buffer, cursor)
                while AltN:
                    self.AltN.append(AltN)
                    cursor += 4
                    AltN = readInt32BE(buffer, cursor)
                cursor += 4
                header_string = readString(buffer, cursor)

        return cursor + 4
    
    def make(self):
        self.model.collection['header'] = self.offsets
        self.model.collection.export_type = self.model.type
        self.model.collection.export_model = str(self.model.id)
        
        if self.model.Data:
            self.model.Data.make()
        
        if self.model.Anim:
            self.model.Anim.make()    
        
        return
    
    def unmake(self, collection):
        self.model.id = collection.export_model
        self.model.type = collection.export_type
        if self.model.type == "7":
            self.model.Data = ModelData(self, self.model).unmake()
        self.model.Anim = AnimList(self, self.model).unmake()
    
    def write(self, buffer, cursor):
        cursor = writeString(buffer,  model_types[int(self.model.type)][1], cursor)

        for header_value in range(header_sizes[int(self.model.type)]):
            self.model.highlight(cursor)
            cursor += 4  # writeInt32BE(buffer, header_value, cursor)

        cursor = writeInt32BE(buffer, -1, cursor)

        if self.model.type == "7" and self.model.Data:
            cursor = self.model.Data.write(buffer, cursor)

        if self.model.Anim:
            cursor = self.model.Anim.write(buffer, cursor)

        if self.model.AltN:
            cursor = self.model.ref_map['AltN'] = cursor + 4
            #cursor = write_altn(buffer, cursor, model, hl)0

        cursor = writeString(buffer, 'HEnd', cursor)
        self.model.ref_map['HEnd'] = cursor

        return cursor

def find_topmost_parent(obj):
    while obj.parent is not None:
        obj = obj.parent
    return obj

def b_get_family(obj):
    objects = []
    if obj.type == 'MESH':
        objects.append(obj)
    for child in obj.children:
        if child.type == 'MESH':
            objects.append(child)
        if len(child.children):
            objects.extend(b_get_family(child))
    return objects

def r_get_family(node):
    objects = []
    for child in node.children:
        if len(child.children):
            objects.extend(r_get_family(child))
        else:
            objects.append(child)
    return objects

def assign_objs_to_node_by_layer(objects, root, model):
    
    layers = {}
    #get unique layer ids from objects
    for obj in objects:
        if hasattr(obj, 'layers'):
            if obj.layers in layers:
                layers[obj.layers].append(obj)
                continue
            layers[obj.layers] = [obj]
        else: 
            raise Exception('Object has no layers attribute')
    
    for id, meshes in layers.items():
        mesh_group = MeshGroup12388(root, model, 12388)
        mesh_group.vis_flags |= id
        mesh_group.col_flags |= id
        for child in meshes: 
            child.parent = mesh_group
            mesh_group.children.append(child)
            mesh_group.calc_bounding()
        root.children.append(mesh_group)
    
def assign_objs_to_node_by_type(objects, root, model):
    # TODO: Make a way for this to respect the shown order in the outliner for the sake of depth order in some cases (like skyboxes)
    viscol = []
    col = []
    vis = []
    tpt = []
    other = []
    
    for obj in objects:
        if obj is None:
            continue
        if isinstance(obj, Node):
            other.append(obj)
        elif obj.has_collision() and obj.has_visuals():
            if obj.has_transparency():
                obj_vis, obj_col = obj.split()
                tpt.append(obj_vis)
                col.append(obj_col)
            else:
                viscol.append(obj)
        elif obj.has_collision():
            col.append(obj)
        elif obj.has_visuals():
            if obj.has_transparency():
                tpt.append(obj)
            else:
                vis.append(obj)
        
    for arr in [viscol, vis, col, tpt]:
        if len(arr):
            assign_objs_to_node_by_layer(arr, root, model)
            # mesh_group = MeshGroup12388(root, model, 12388)
            # for child in arr: 
            #     child.parent = mesh_group
            #     mesh_group.children.append(child)
            # mesh_group.calc_bounding()
            # root.children.append(mesh_group)
            
    # this is added last as a hack since hierarchies sometimes need to be drawn last (oovo skybox)
    for node in other:
        root.children.append(node) 
        

def get_obj_by_id(id):
    for obj in bpy.data.objects:
        if obj.id == str(id):
            return obj
    return None

def get_mat_by_id(id):
    for mat in bpy.data.materials:
        if 'id' in mat and mat['id'] is not None and int(mat['id']) == int(id):
            return mat
    return None

def deep_select_objects(collection):
    for obj in collection.objects:
        if obj.type == 'MESH':
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
    for sub_collection in collection.children:
        deep_select_objects(sub_collection)

def get_immediate_children(collection):
    immediate_children = []
    for obj in collection.objects:
        # Include the object if it has no parent or its parent is not in the collection
        if obj.parent is None or obj.parent.name not in collection.objects:
            immediate_children.append(obj)
    return immediate_children

def deep_unmake(obj, parent, model, target_map, skybox = False):
    if obj is None:
        return []
    
    children = []
    
    if (obj.get('node_type') == 53349) or (obj.get('node_type') == 53350 and not skybox)  or obj.animation_data or obj.name in target_map.keys(): # cases in which we need to retain hierarchy
        # empty = create_node(obj['node_type'] if 'node_type' in obj else 53349, parent, model)
        # empty.unmake(obj)
        if obj.get('node_type') == 53350 and not skybox:
            empty = Group53350(parent, model, 53350).unmake(obj)
        else:
            empty = Group53349(parent, model, 53349).unmake(obj)
        empty.unk1 = 196608 #TODO:what the heck
        # empty.matrix = FloatMatrix()
        # empty.matrix.data[0].data[0] = 1.0
        # empty.matrix.data[1].data[1] = 1.0
        # empty.matrix.data[2].data[2] = 1.0
        
        empty_children = []
        
        if obj.name in target_map.keys():
            target_map[obj.name] = empty
        
        if obj.type == 'MESH': 
            mesh = Mesh(empty, model).unmake(obj)
            empty_children.append(mesh)
        
        for child in obj.children:
            empty_children = empty_children + deep_unmake(child, empty, model, target_map)
        assign_objs_to_node_by_type(empty_children, empty, model)
        children.append(empty)
            
        return children # early return since we've already dealt with descendants
    
    elif obj.type == 'MESH':
        children.append(Mesh(parent, model).unmake(obj))
    
    for child in obj.children:
        children.extend(deep_unmake(child, parent, model, target_map))
            
    return children

def get_all_objects_in_collection(collection):
    """Recursively get all objects in a collection and its subcollections."""
    objects = set(collection.objects)  # Start with objects directly in the collection
    for child_collection in collection.children:
        objects.update(get_all_objects_in_collection(child_collection))  # Add objects from subcollections
    return objects

def split_meshes_by_material(collection):
    bpy.ops.object.select_all(action='DESELECT')
    
    deep_select_objects(collection)
    
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.separate(type='MATERIAL')
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    
def split_mesh_by_loose_parts(mesh):
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    
def apply_scale(collection):
    bpy.ops.object.select_all(action = 'DESELECT')
    
    deep_select_objects(collection)
    
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.select_all(action='DESELECT')
    
def triangulate_mesh(obj_list):
    for obj in obj_list:
        if obj.type == 'MESH':
            mesh = obj.data
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])  # Triangulate all faces
            bm.to_mesh(mesh)
            bm.free()
    
def ensure_24_view_layers():
    """Ensure that at least 24 view layers exist in the scene."""
    scene = bpy.context.scene
    gap = len(scene.view_layers) - 1
    for i in range(gap, 24):
        new_layer = scene.view_layers.new(name=f"VisLayer_{i}")

def link_nodes(parent, children):
    for child in children:
        parent.children.append(child)
        if child is not None:
            child.parent = parent

# MARK: MODEL

class Model():    
    def __init__(self, id):
        self.parent = None
        self.modelblock = None
        self.collection = None
        self.type = None
        self.id = id
        self.scale = 0.01
        self.fps = bpy.context.scene.render.fps
        
        self.ref_map = {} # where we'll map node ids to their written locations
        self.ref_keeper = {} # where we'll remember locations of node refs to go back and update with the ref_map at the end
        self.hl = None
        
        self.header = ModelHeader(self, self)
        self.Data = None
        self.AltN = []
        self.Anim = None
        
        self.animations = []
        self.materials = {}
        self.textures = {}
        self.nodes = []
        self.triggers = []

    def read(self, buffer):
        if self.id is None:
            return
        cursor = 0
        cursor = self.header.read(buffer, cursor)
        if cursor is None:
            show_custom_popup(bpy.context, "Unrecognized Model Extension", f"This model extension was not recognized: {self.header.model.type}")
            return None
        
        if self.type == "4":
            
            #get MAlt
            MAlt_id = Podd_MAlt[str(self.id)]
            MAlt_buffer = self.modelblock.fetch(MAlt_id)[1]
            MAlt = Model(MAlt_id).read(MAlt_buffer)
            
            for i, offset in enumerate(self.header.offsets):
                if offset:
                    node_type = readUInt32BE(buffer, offset)
                    node = create_node(node_type, self, self)
                    self.nodes.append(node.read(buffer, offset))
                elif MAlt.header.offsets[i]:
                    MAlt_offset = MAlt.header.offsets[i]
                    node_type = readUInt32BE(MAlt_buffer, MAlt_offset)
                    node = create_node(node_type, self, self)
                    self.nodes.append(node.read(MAlt_buffer, MAlt_offset))
        elif readUInt32BE(buffer, cursor):
            node_type = readUInt32BE(buffer, cursor)
            node = create_node(node_type, self, self)
            self.nodes = [node.read(buffer, cursor)]
            
        return self

    def make(self):
        ensure_24_view_layers()
        collection = bpy.data.collections.new(f"model_{self.id}_{self.type}")
        collection.export_type = self.type
        collection.collection_type = "MODEL"
        
        bpy.context.scene.collection.children.link(collection)
        self.collection = collection
        
        for node in self.nodes:
            self.modelblock.update_progress(f"Making node {node.id}")
            node.make(None, collection)

        # update trigger targets
        for trigger in self.triggers:
            if 'target_id' in trigger and trigger['target_id']:
                target = get_obj_by_id(trigger['target_id'])
                trigger.target = target
                
        #header should be made last for the animations
        self.header.make()

        return collection

    def unmake(self, collection, texture_export, textureblock):
        self.textureblock = textureblock
        self.image_map = {}
        self.type = collection.export_type
        self.id = collection.export_model
        self.nodes = []
        self.texture_export = texture_export
        
        root = Group20580(self, self, 20580)
        
        if self.type == '3':
            root = Group53349(self, self, 53349)
            root.header = [0]
            root.col_flags &= 0xFFFFFFFD
        
        
        
        target_map = {}
        
        #TODO: Resolve multi-user objects
        
        split_meshes_by_material(collection)
        apply_scale(collection)
        objects = get_all_objects_in_collection(collection)
        triangulate_mesh(objects)
        
        # check for too many faces
        for obj in objects:
            if obj.type == 'MESH' and (obj.visible or (not obj.visible and not obj.collidable)):
                faces = [[v for v in face.vertices] for face in obj.data.polygons]
                if len(faces) > 2048:
                    bpy.ops.object.select_all(action='DESELECT')
                    obj.select_set(True)
                    raise ValueError(f"Max faces reached in {obj.name} {len(faces)}/2048")
        
        # get all target objects
        target_map = {b_obj.target.name: None for b_obj in objects if b_obj.trigger_id and b_obj.target}
        
        if self.type == '7':
            for child_collection in collection.children:
                r_root_node = Group20580(root, self, 20580)
                
                if child_collection.collection_type == '0': #Track
                    r_root_node.header = [0, 1]
                    append_root = r_root_node
                    root.children.append(r_root_node)
                
                elif child_collection.collection_type == '1': #skybox
                    sky_empty = Group53349(r_root_node, self, 53349)
                    sky_empty.header = [2]
                    sky_to_camera = Group53350(sky_empty, self, 53350)
                    sky_to_camera.follow_position = 1
                    append_root = sky_to_camera
                    
                    sky_empty.children.append(sky_to_camera)
                    r_root_node.children.append(sky_empty)
                    root.children.append(r_root_node)
                else:
                    root.children.append(r_root_node)
                    append_root = r_root_node
                
                # get immediate children and traverse hierarchy
                immediate_children = get_immediate_children(child_collection)
                unmade = []
                for obj in immediate_children:
                    unmade.extend(deep_unmake(obj, append_root, self, target_map, skybox = (child_collection.collection_type == '1')))
                assign_objs_to_node_by_type(unmade, append_root, self)
                #r_root_node.set_flags()
            
        elif self.type == '3': #part
            for o in collection.objects:
                if o.type == 'MESH':
                    immediate_children = get_immediate_children(collection)
                    unmade = []
                    for obj in immediate_children:
                        unmade.extend(deep_unmake(obj, root, self, target_map))
                    assign_objs_to_node_by_type(unmade, root, self)
                    
        elif self.type == '4':
            def create_podd_component(mesh, type):
                comp_a = Group53349(None, self, 53349)
                comp_b = Group53348(None, self, 53348)
                comp_b.matrix.data[0].data[0] = 0.016
                comp_b.matrix.data[1].data[1] = 0.016
                comp_b.matrix.data[2].data[2] = 0.016
                link_nodes(comp_a, [comp_b])
                comp_d = Group20580(None, self, 20580)
                link_nodes(comp_b, [comp_d])
                if len(mesh):
                    assign_objs_to_node_by_type([Mesh(None, self).unmake(obj) for obj in mesh], comp_d, self)
                return comp_a
            
            def create_air_stream(mesh, top_header, bottom_header):
                air_a = Group53349(None, self, 53349, header = [top_header])
                air_b = Group53350(None, self, 53350)
                link_nodes(air_a, [air_b])
                air_c = Group53349(None, self, 53349, header = [bottom_header])
                link_nodes(air_b, [air_c])
                air_d = Group53349(None, self, 53349)
                link_nodes(air_c, [air_d])
                if len(mesh):
                    assign_objs_to_node_by_type([Mesh(None, self).unmake(obj) for obj in mesh], air_d, self)
                return air_a
            
            root = Group20581(root, self, 20581, header = [0])
            
            podd_a_node = Group20580(None, self, 20580)
            podd_74_node = Group53349(None, self, 53349, header = [74])
            link_nodes(root, [podd_a_node, podd_74_node])
            
            podd_shadows_node = Group20580(None, self, 20580)
            podd_engine_r_shadow = Group53349(None, self, 53349, header = [62])
            podd_engine_l_shadow = Group53349(None, self, 53349, header = [63])
            podd_cockpit_shadow = Group53349(None, self, 53349, header = [64])
            link_nodes(podd_shadows_node, [podd_engine_r_shadow, podd_engine_l_shadow, podd_cockpit_shadow])
            
            podd_b_node = Group20580(None, self, 20580)
            
            podd_71_node = Group20580(None, self, 20580, header = [71])
            link_nodes(podd_b_node, [podd_71_node])
            
            podd_sparks = Group53349(None, self, 53349, header = [65])
            podd_sparks_ai = Group53349(None, self, 53349, header = [66])
            podd_72_node = Group53349(None, self, 53349, header = [72])
            podd_73_node = Group53349(None, self, 53349, header = [73])
            podd_binder1 = Group53349(None, self, 53349, header = [6])
            podd_binder2 = Group53349(None, self, 53349, header = [7])
            link_nodes(podd_binder1, [podd_binder2])
            podd_airsream_right = create_air_stream([], 67, 69)
            podd_airsream_left = create_air_stream([], 68, 70)
            
            
            podd_engine_r = None
            podd_engine_l = None
            podd_cockpit = None
            podd_cable1 = None
            podd_cable2 = None
            
            for child_collection in collection.children:
                if child_collection.collection_type == '2':
                    right_engine_mesh = get_all_objects_in_collection(child_collection)
                    right_engine = create_podd_component(right_engine_mesh, 'engine_r')
                    link_nodes(podd_71_node, [right_engine])
                    podd_engine_r = Group53349(None, self, 53349, header = [1])
                    link_nodes(podd_engine_r, right_engine.children)
                    right_engine.header = [14]
                elif child_collection.collection_type == '3':
                    left_engine_mesh = get_all_objects_in_collection(child_collection)
                    left_engine = create_podd_component(left_engine_mesh, 'engine_l')
                    link_nodes(podd_71_node, [left_engine])
                    podd_engine_l = Group53349(None, self, 53349, header = [2])
                    link_nodes(podd_engine_l, left_engine.children)
                    left_engine.header = [15]
                elif child_collection.collection_type == '4':
                    cockpit_mesh = get_all_objects_in_collection(child_collection)
                    cockpit = create_podd_component(cockpit_mesh, 'cockpit')
                    link_nodes(podd_71_node, [cockpit])
                    podd_cockpit = Group53349(None, self, 53349, header = [5])
                    link_nodes(podd_cockpit, cockpit.children)
                    link_nodes(podd_a_node, [podd_cockpit])
                    cockpit.header = [16]
                elif child_collection.collection_type == '5':
                    cable_mesh = get_all_objects_in_collection(child_collection)
                    podd_cable1 = Group53349(None, self, 53349, header = [10])
                    podd_cable2 = Group53349(None, self, 53349, header = [11])
                    assign_objs_to_node_by_type([Mesh(podd_cable1, self).unmake(obj) for obj in cable_mesh], podd_cable1, self)
                    assign_objs_to_node_by_type([Mesh(podd_cable2, self).unmake(obj) for obj in cable_mesh], podd_cable2, self)
                    link_nodes(podd_a_node, [podd_cable1, podd_cable2])
            
            
            link_nodes(podd_a_node, [podd_shadows_node, podd_b_node])
            
            if podd_engine_r:
                link_nodes(podd_a_node, [podd_engine_r])
            if podd_engine_l:
                link_nodes(podd_a_node, [podd_engine_l])
            if podd_cable1:
                link_nodes(podd_a_node, [podd_cable1, podd_cable2])
            
            link_nodes(podd_a_node, [podd_sparks, podd_sparks_ai, podd_72_node, podd_73_node, podd_binder1, podd_airsream_right, podd_airsream_left])
            
            if podd_cockpit:
                link_nodes(podd_a_node, [podd_cockpit])
            # !0 (20581) 1111(on) 1101(collision off)
            #   (20580) 1111(on) 1101(collision off)
            #       (20580) 1111(on) 1101(collision off)
            #           62 (53349) 1100(vis off) 1101(collision off)
            #               right engine shadow 1111(on) 1101(collision off)
            #           63 (53349) 1100(vis off) 1101(collision off)
            #               left engine shadow 1111(on) 1101(collision off)
            #           64 (53349) 1100(vis off) 1101(collision off)
            #               cockpit shadow 1111(on) 1101(collision off)
            #       (20580) 0 1101(collision off)
            #           !71 (20580)   1111(on) 1101(collision off)
            #               14/15/16 (53349) 1111(on) 1101(collision off)
            #                   (53348) 1111(on) 1101(collision off) (also child of 1) (scales to 0.016)
            #                       (53349) 1111(on) 1101(collision off) (optional mirror node with -1 scale and 180* rotation)
            #                           (20580) 1111(on) 1101(collision off)
            #                               31/17/45 (53349) 1111(on) 1101(collision off)
            #                                   (20582) lod selector 1111(on) 1101(collision off)
            #                                       (blank child, 2 for cockpit)
            #                                       (12388) 1111(on) 1101(collision off) unk1 = 2097152
            #                                           32-36/18-22
            #                                           high LOD engines
            #                                       (12388)
            #                                           37-41/23-27
            #                                           med LOD engines
            #                                       (12388)
            #                                           med LOD engines (no anims)
            #                                       (12388)
            #                                           low LOD engines
            #                                   (53349)
            #                                       43/29 (53349)
            #                                           (20580)
            #                                               jet trail tube
            #                                   (53349)
            #                                       42/28 (53349)
            #                                           (20580)
            #                                               jet trail flat
            #       !1 (53349) 1111(on) 1101(collision off) (also parent of 53348 node under 14)
            #       !2 (53349) 1111(on) 1101(collision off)  (also parent of 53348 node under 15)
            #       !10 (53349) 1111(on) 1101(collision off)
            #           cable 1111(on) 1101(collision off)
            #       !11 (53349) 1111(on) 1101(collision off)
            #           cable
            #       !65 (53349) 1100(vis off) 1101(collision off) track sparks
            #       !66 (53349) 1100(vis off) 1101(collision off) ai sparks
            #       72 (53349) 1100(vis off) 1101(collision off)
            #       73 (53349) 1100(vis off) 1101(collision off)
            #       !6 (53349) 1111(on) 1101(collision off)
            #           !7 (53349) 1111(on) 1101(collision off)
            #       67/68 (53349) 1100(vis off) 1101(collision off)
            #           (53350) 1111(on) 1101(collision off)
            #               69/70 (53349) 1111(on) 1101(collision off)
            #                   (53349) 1111(on) 1101(collision off)
            #       !5 (53349) 1111(on) 1101(collision off)   (also parent of 53348 node under 16)
            #       
            #   74 (53349) 1111(on) 1101(collision off)
            #       entire low LOD pod 1111(on) 1101(collision off)
            
            # 14/53348 is child of 1
            # 15/53348 is child of 2
            # 16/53348 is child of 5
        
        
        root.set_flags()
        root.vis_flags = 0xFFFFFFFF
        root.col_flags = 0xFFFFFFFF
        self.nodes.append(root)
                
        #update trigger targets
        for trigger in self.triggers:
            if trigger.target:
                trigger.target = target_map[trigger.target.name]
        
        self.header.unmake(collection)
            
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
        if self.Anim:
            for i, anim in enumerate(self.Anim.data):
                writeUInt32BE(buffer, cursor, self.anim_list + i*4)
                cursor = anim.write(buffer, cursor)
            
        # write trigger targets
        for trigger in self.triggers:
            trigger.write_target(buffer)
                
        crop = math.ceil(cursor / (32 * 4)) * 4
        
        return [self.hl[:crop], buffer[:cursor]]
            
    def highlight(self, cursor):
        # This function is called whenever an address needs to be 'highlighted' because it is a pointer
        # Every model begins with a pointer map where each bit represents 4 bytes in the following model
        # If the bit is 1, that corresponding DWORD is to be read as a pointer

        highlight_offset = cursor // 32
        bit = 2 ** (7 - ((cursor % 32) // 4))
        highlight = self.hl[highlight_offset]
        self.hl[highlight_offset] = highlight | bit
