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
from bpy_extras import anim_utils
import bmesh
import math
import mathutils
from .general import RGB3Bytes, FloatPosition, FloatVector, DataStruct, RGBA4Bytes, ShortPosition, FloatMatrix, writeFloatBE, writeInt32BE, writeString, writeUInt32BE, writeUInt8, readString, readInt32BE, readUInt16BE, readUInt32BE, readUInt8, readFloatBE
from .textureblock import Texture, compute_image_hash, compute_hash, needed_pixel_bytes, format_map
from ..utils import show_custom_popup, model_types, header_sizes, showbytes, Podd_MAlt

def find_existing_light(objects, color, location, rotation):
    for light in objects:
        if light.type == 'LIGHT' and light.data.color == color and (light.location - location).length < 0.001 and light.users:
            # Check rotation (convert both to Euler for comparison)
            existing_rotation = light.rotation_euler
            if existing_rotation == rotation:
                return light
    return None

def effective_node_flags(obj, key):
    """The node flags (vis_flags or col_flags) a mesh under obj effectively gets, or None if obj has none.

    The renderer skips a node's whole subtree when its flags fail the viewport's masks
    (SW_RACER_RE dinput_hook/renderer_hook.cpp debug_render_node), so a mesh is drawn only where
    every node it is reached through allows. Export writes the flags back on the mesh groups only
    (other nodes get all bits, or are merged into their parent), so the mesh takes the AND of them.

    The game starts drawing at header slot nodes (the track at slots 0/1, the skybox at slot 2, a
    pod's parts), not at the file's top node, so the AND stops at the nearest node holding a slot.
    Stock tracks park the skybox under a group with flags 0 so the track traversal skips it;
    ANDing past slot 2 hid the skybox everywhere, and pod parts the same way.
    """
    flags = None
    while obj is not None:
        if key in obj:
            flags = int(obj[key]) if flags is None else flags & int(obj[key])
        if obj.get('header'):
            break
        obj = obj.parent
    return flags

def set_hidden(model, obj, hidden, view_layer):
    """obj.hide_set(hidden, view_layer=view_layer), deferred to the end of Model.make when importing.

    New objects start shown in every view layer, so only hiding needs doing. Hiding right after
    creating each object makes Blender resync the view layer's object list on every call, which
    grows with the object count and dominated import time on tracks.
    """
    pending = getattr(model, 'pending_hides', None)
    if pending is not None:
        if hidden:
            pending.append((obj, view_layer))
    elif hidden or obj.hide_get(view_layer = view_layer):
        obj.hide_set(hidden, view_layer = view_layer)

_children_map = None

def object_children(obj):
    """obj.children, which scans every object in the file per call; export precomputes it once."""
    if _children_map is not None:
        return _children_map.get(obj.as_pointer(), ())
    return obj.children

def index_children():
    """Until clear_children_index, object_children uses one parent -> children map built now.

    Only valid while no objects are added, removed or reparented.
    """
    global _children_map
    _children_map = {}
    for obj in bpy.data.objects:  # same order as Object.children
        if obj.parent is not None:
            _children_map.setdefault(obj.parent.as_pointer(), []).append(obj)

def clear_children_index():
    global _children_map
    _children_map = None

def object_collections(obj, model = None):
    """obj.users_collection, which scans every collection's objects per call; cached per export model."""
    if model is None:
        return obj.users_collection
    index = getattr(model, 'collections_index', None)
    if index is None:
        index = {}
        for collection in [*bpy.data.collections, *(scene.collection for scene in bpy.data.scenes)]:
            for member in collection.objects:
                index.setdefault(member.as_pointer(), []).append(collection)
        model.collections_index = index
    return index.get(obj.as_pointer(), [])

def basis_values(matrix):
    return [matrix[r][c] for r in range(3) for c in range(4)]

def frame0_basis(obj):
    """obj's basis at frame 0 from its fcurves (channels without one keep their current value)."""
    bag = anim_utils.action_get_channelbag_for_slot(obj.animation_data.action, obj.animation_data.action_slot)
    location, rotation, scale = (list(v) for v in obj.matrix_basis.decompose())
    for fcurve in (bag.fcurves if bag else []):
        target = {'location': location, 'rotation_quaternion': rotation, 'scale': scale}.get(fcurve.data_path)
        if target is not None and fcurve.array_index < len(target):
            target[fcurve.array_index] = fcurve.evaluate(0)
    return mathutils.Matrix.LocRotScale(mathutils.Vector(location), mathutils.Quaternion(rotation), mathutils.Vector(scale))

def set_material_prop(material, name, value):
    """Set a registered Material property (props.py), dropping a custom property of the same name.

    Since Blender 5.0, properties registered with bpy.props are stored apart from custom
    properties: material['scroll_x'] and material.scroll_x are different values. Import wrote
    the custom one and export read the registered one, which was always 0, so imported UV
    scrolling never exported (and the panel showed 0).
    """
    if name in material.keys():
        del material[name]
    setattr(material, name, value)

def get_material_prop(material, name):
    """A registered Material property, or the custom property older imports wrote instead."""
    value = getattr(material, name)
    custom = material.get(name)
    if not value and custom is not None and not hasattr(custom, 'keys'):
        return type(value)(custom)
    return value

def get_model_type(name):
    for code, model_name, description in model_types:
        if model_name == name:
            return code
    return None

def set_material_blend(material, blend):
    """Set a material's transparency mode across Blender versions.

    `blend` is 'OPAQUE' or 'BLEND'. `Material.blend_method` and
    `show_transparent_back` were removed in EEVEE-Next (Blender 4.3+) and
    replaced by `surface_render_method`. Assigning the old attributes on 4.3+
    raises AttributeError, so guard every write with hasattr and set whichever
    API the running Blender exposes."""
    if hasattr(material, 'blend_method'):
        material.blend_method = blend
    if hasattr(material, 'surface_render_method'):
        material.surface_render_method = 'BLENDED' if blend == 'BLEND' else 'DITHERED'
    if blend == 'BLEND' and hasattr(material, 'show_transparent_back'):
        material.show_transparent_back = True

# N64 render mode words (SW_RACER_RE dinput_hook/n64_shader.h RenderMode, n64_shader.cpp
# set_render_mode). The file splits them across render_mode_1 (cycle-1 blender) and render_mode_2
# (cycle-2 blender and flags); the renderer ORs the two.
RM_ZMODE_MASK = 0xC00
RM_ZMODE_XLU = 0x800
RM_CYCLE1_MASK = 0xCCCC0000
# the stock opaque surface (by far the most common pair in the game's own models) and the stock
# translucent surface
RM_OPAQUE = (0xC8000000, 0x00112078)        # AA, z compare + update, IN*A + MEM*A_MEM
RM_TRANSLUCENT = (0xC8000000, 0x001049D8)   # z compare, ZMODE_XLU, IN*A + MEM*(1-A); no alpha compare,
                                            # which the renderer treats as a cutout instead
# old add-on exports wrote these; the replacement renderer aborts on them (rm2 = 0 selects a
# cycle-2 blender it has no mode for, n64_shader.cpp set_render_mode)
RM_LEGACY_DEFAULTS = ((0x18, 0), (0x818, 0))
# TEXEL0*SHADE in cycle 1 and a pass-through cycle 2, so no primitive color is needed
DEFAULT_COMBINERS = (0x011F041F, 0x01070407, 0x1F1F1F00, 0x07070700)


def render_mode_is_alpha_blend(mode):
    """The cycle-2 blender is IN*A + MEM*(1-A) (SW_RACER_RE dinput_hook/n64_shader.cpp)."""
    return (mode >> 28) & 3 == 0 and (mode >> 24) & 3 == 0 and (mode >> 20) & 3 == 1 and (mode >> 16) & 3 == 0


def render_mode_is_translucent(mode):
    return render_mode_is_alpha_blend(mode) or (mode & RM_ZMODE_MASK) == RM_ZMODE_XLU


def render_mode_is_cutout(mode):
    """alpha_compare or cvg_x_alpha: the renderer discards texels below 0.5 alpha (n64_shader.frag)."""
    return bool(mode & 0x3) or bool(mode & 0x1000)


def ensure_cycles_first(fcurve):
    mods = fcurve.modifiers

    # If it already has a Cycles modifier, just make sure it's first.
    idx = next((i for i, m in enumerate(mods) if m.type == 'CYCLES'), None)

    # If it doesn't exist, create one (it will be appended at the end).
    if idx is None:
        m = mods.new('CYCLES')
        idx = len(mods) - 1
    else:
        m = mods[idx]

    # Move Cycles to index 0
    while idx > 0:
        mods.move(idx, idx - 1)
        idx -= 1

    return m

class Lights(DataStruct):
    # RE swrModel_Behavior light region: light_flags(u16), ambient_color[3],
    # light_color[3], unk10(u16 = the two bytes below), light_vector[3] (a
    # direction vector), unk14_node (a swrModel_Node* pointer), unk15, unk16.
    # NOTE: light_vector is a DIRECTION per the RE, but is currently represented
    # in Blender as the position of a point light (unchanged for now to avoid a
    # speculative point->sun conversion). unk14_node/unk15/unk16 are written as
    # 0 on export: unk14_node is a runtime pointer (null on disk) and the two
    # unknowns default to 0, matching how unk10 already exports. This replaces
    # the previous code that misread these 12 bytes as a float "rotation" and
    # wrote Blender rotation values back into the pointer slot.
    def __init__(self, model):
        super().__init__('>h8b3f3I')
        self.model = model
        self.flag = 0
        # 00100 = invert affected?
        # 01000 = flicker?
        # 10000 = persistent lighting
        self.ambient = RGB3Bytes()
        self.color = RGB3Bytes()
        self.unk1 = 0
        self.unk2 = 0
        self.light_vector = FloatPosition()
        self.unk14_node = 0
        self.unk15 = 0
        self.unk16 = 0

    def read(self, buffer, cursor):
        self.flag, ambient_r, ambient_g, ambient_b, color_r, color_g, color_b, self.unk1, self.unk2, x, y, z, self.unk14_node, self.unk15, self.unk16 = struct.unpack_from(self.format_string, buffer, cursor)
        self.ambient.from_array([ambient_r, ambient_g, ambient_b])
        self.color.from_array([color_r, color_g, color_b])
        self.light_vector.from_array([x, y, z])
        return self

    def make(self, obj):

        if self.flag & 0x3 > 0:
            objects = get_all_objects_in_collection(self.model.collection)
            existing_light = find_existing_light(objects, mathutils.Color(self.color.make()), mathutils.Vector([a * self.model.scale for a in self.light_vector.make()]), mathutils.Euler((0, 0, 0)))
            if existing_light is None:
                # Create a new light if no existing light is found

                new_light = bpy.data.lights.new(type='POINT', name='pod_lighting')
                new_light.color = self.color.make()

                light_object = bpy.data.objects.new(name="pod_lighting", object_data=new_light)
                self.model.collection.objects.link(light_object)

                # Set the location (light_vector; see class note re: direction)
                light_object.location = [a * self.model.scale for a in self.light_vector.make()]

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
                self.light_vector.from_array([round(a/self.model.scale) for a in light_object.location])

        self.ambient.unmake(obj.lighting_color)

        if obj.lighting_invert:
            self.flag |= 0x4
        if obj.lighting_flicker:
            self.flag |= 0x8
        if obj.lighting_persistent:
                self.flag |= 0x10

        return self

    def to_array(self):
        return [self.flag, *self.ambient.to_array(), *self.color.to_array(), self.unk1, self.unk2, *self.light_vector.to_array(), self.unk14_node, self.unk15, self.unk16]

    def from_array(self, arr):
        self.flag, ambient_r, ambient_g, ambient_b,color_r, color_g, color_b, self.unk1, self.unk2, x, y, z, self.unk14_node, self.unk15, self.unk16 = arr
        self.ambient.from_array([ambient_r, ambient_g, ambient_b])
        self.color.from_array([color_r, color_g, color_b])
        self.light_vector.from_array([x, y, z])
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
        # the flags are registered Object properties (props.py, the panel's toggles): an
        # obj['Disabled'] custom property is a different value in Blender 5 (set_material_prop)
        for attr in self.flags:
            set_material_prop(obj, attr, bool(getattr(self, attr)))

    def unmake(self, obj):
        # trigger_settings is a registered property, never an ID property named 'settings'
        self.settings = obj.trigger_settings
        # flags set in the panel, or the custom properties older imports wrote. Reading only the
        # custom ones exported every flag the panel set as 0: Disabled and SkipLap triggers fired
        # in game (levels/level_museum_triggers.py)
        for attr in self.flags:
            setattr(self, attr, bool(get_material_prop(obj, attr)))
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
        trigger_empty.trigger_id = self.id
        
        
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
            setattr(obj, attr, getattr(self, attr))
    
    def unmake(self, obj):
        for attr in self.flags:
            if hasattr(obj, attr):
                setattr(self, attr, getattr(obj, attr))
    
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
        
        # The light region's tail is light_vector(3f) + unk14_node(pointer) +
        # unk15 + unk16 (RE swrModel_Behavior), not six floats. Same 24 bytes and
        # same value count, so no field offsets move; the last three are read as
        # uint32 rather than misread as a float "rotation".
        super().__init__('>H4B3H8B3f3II2H3I')
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
        obj.collision_data = True
        
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
        
        for child in object_children(mesh):
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
        if self.co != other.co or self.uv != other.uv or self.color != other.color:
            return False
        # Hooked verts are anchored to a different node than the rest of the mesh;
        # they must not collapse with non-hooked verts at the same position.
        return getattr(self, '_hooked', False) == getattr(other, '_hooked', False)

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
    
def vert_key(vert):
    """A hashable value that is equal for two VisualsVertChunks exactly when they compare equal."""
    return (tuple(vert.co), tuple(vert.uv), tuple(vert.color.to_array()), getattr(vert, '_hooked', False))

def pack_vertex_loads(faces, capacity):
    """Splits faces (lists of VisualsVertChunks) into vertex loads of at most `capacity` verts.

    A gSPVertex loads n consecutive vertex buffer entries into the vertex cache and triangles
    index cache slots, so each face must lie within one load. Returns (verts, loads): the vertex
    buffer, and per load (buffer index of its first vertex, n, its faces as slot indices).

    Each load grows from one face by repeatedly taking the remaining face that needs the fewest
    vertices not yet loaded (lowest index on ties, so the output only depends on the face order).
    A new load starts with the remaining face that best reuses the end of the previous load, and
    reloads that end of the buffer (loads may overlap) instead of duplicating those vertices.
    """
    face_keys = [[vert_key(vert) for vert in face] for face in faces]
    faces_with_key = {}
    for f, keys in enumerate(face_keys):
        for key in keys:
            faces_with_key.setdefault(key, []).append(f)
    remaining = [True] * len(faces)
    first_remaining = 0
    verts = []
    keys_at = []
    loads = []
    slot_of = {}  # key -> buffer index, for the current load
    load_start = 0

    def missing(f, start):
        return len({key for key in face_keys[f] if slot_of.get(key, -1) < start})

    while True:
        while first_remaining < len(faces) and not remaining[first_remaining]:
            first_remaining += 1
        if first_remaining == len(faces):
            break
        current = first_remaining
        new_start = len(verts)
        if slot_of:
            best = None
            for f in sorted({f for key in slot_of for f in faces_with_key[key] if remaining[f]}):
                start = min(slot_of[key] for key in face_keys[f] if key in slot_of)
                score = (missing(f, start), len(verts) - start)
                if score[0] + score[1] <= capacity and (best is None or score < best[0]):
                    best = (score, f, start)
            if best is not None:
                _, current, new_start = best
        slot_of = {keys_at[i]: i for i in range(new_start, len(verts))}
        load_start = new_start
        load_faces = []
        while current is not None:
            remaining[current] = False
            for vert, key in zip(faces[current], face_keys[current]):
                if key not in slot_of:
                    slot_of[key] = len(verts)
                    verts.append(vert)
                    keys_at.append(key)
            load_faces.append([slot_of[key] - load_start for key in face_keys[current]])
            current = None
            fewest = capacity + 1
            for f in sorted({f for key in slot_of for f in faces_with_key[key] if remaining[f]}):
                m = missing(f, load_start)
                if m < fewest and len(slot_of) + m <= capacity:
                    current, fewest = f, m
                    if m == 0:
                        break
            if current is None:
                while first_remaining < len(faces) and not remaining[first_remaining]:
                    first_remaining += 1
                if first_remaining < len(faces) and len(slot_of) + missing(first_remaining, load_start) <= capacity:
                    current = first_remaining
        loads.append((load_start, len(verts) - load_start, load_faces))
    return verts, loads

# Vertex normals.
# A mesh whose material type has bit 0x1 or 0x10 set uses the Vtx_tn vertex format: bytes 12-14 are
# a signed int8 normal (nx, ny, nz) and byte 15 the alpha, instead of Vtx_t's r, g, b, a
# (SW_RACER_RE src/types.h:1579-1585, 1689-1703). The renderer reads them as n / 128, in the mesh's
# own space (the same model matrix as the positions, renderer_hook.cpp:481, 513-521), and lights
# with them (assets/shaders/n64_shader.frag:50). The add-on's mesh space is that space (positions
# are imported unrotated, only scaled by Model.scale), so Blender's corner normals are used as is.
#
# The 4 bytes stay in the 'colors' attribute like Vtx_t colors, so an untouched mesh writes back
# exactly what it read. Import also sets them as the mesh's custom normals, so Blender shows and
# edits the game's normals, and records each corner's resulting normal in NORMAL_ATTR. On export a
# corner whose Blender normal still matches its record keeps its bytes; any other (edited geometry,
# a new face, a new mesh) gets round(normal * 127).
NORMAL_ATTR = 'swe1r_normal'
# how far a corner normal may drift from the recorded one and still count as unchanged. Compared as
# vectors, not angles: Blender gives zero-area faces' corners short or zero normals.
NORMAL_MATCH = 0.01


def uses_normals(material):
    return material is not None and bool(material.format & 0x11)


def object_uses_normals(obj):
    """uses_normals for the Material that Mesh.unmake will make from obj's first material."""
    material = next((slot.material for slot in obj.material_slots if slot.material), None)
    if material is None:
        return False
    return bool((material.get('format') or 14) & 0x11) or bool(material.get('normal_map', False))


def signed_byte(b):
    return b - 256 if b > 127 else b


def make_vertex_normals(mesh):
    """Show a normals-format mesh's stored normals (in its 'colors' bytes) as custom normals."""
    colors = mesh.vertex_colors.active
    if colors is None or not len(mesh.loops):
        return
    values = [0.0] * (4 * len(mesh.loops))
    colors.data.foreach_get('color', values)
    normals = []
    for i in range(len(mesh.loops)):
        n = [signed_byte(round(c * 255)) for c in values[4*i:4*i + 3]]
        length = math.sqrt(n[0]*n[0] + n[1]*n[1] + n[2]*n[2])
        # a zero vector keeps Blender's own normal
        normals.append((n[0]/length, n[1]/length, n[2]/length) if length else (0.0, 0.0, 0.0))
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    mesh.normals_split_custom_set(normals)
    record_vertex_normals(mesh)


def record_vertex_normals(mesh, normals = None):
    if normals is None:
        normals = [0.0] * (3 * len(mesh.loops))
        mesh.corner_normals.foreach_get('vector', normals)
    attr = mesh.attributes.get(NORMAL_ATTR)
    if attr is not None and (attr.domain != 'CORNER' or attr.data_type != 'FLOAT_VECTOR'):
        mesh.attributes.remove(attr)
        attr = None
    if attr is None:
        attr = mesh.attributes.new(NORMAL_ATTR, 'FLOAT_VECTOR', 'CORNER')
    attr.data.foreach_set('vector', normals)


def unmake_vertex_normals(mesh):
    """Write each corner's Vtx_tn normal bytes into the mesh's 'colors' attribute for export.

    Corners whose normal matches the one recorded at import keep their bytes (stock meshes stay
    byte-identical); the rest get Blender's corner normal as round(n * 127), keeping their alpha.
    """
    loop_count = len(mesh.loops)
    if not loop_count:
        return
    normals = [0.0] * (3 * loop_count)
    mesh.corner_normals.foreach_get('vector', normals)
    recorded = None
    attr = mesh.attributes.get(NORMAL_ATTR)
    if attr is not None and attr.domain == 'CORNER' and attr.data_type == 'FLOAT_VECTOR':
        recorded = [0.0] * (3 * loop_count)
        attr.data.foreach_get('vector', recorded)
    colors = mesh.vertex_colors.active
    if colors is None:
        colors = mesh.vertex_colors.new(name = 'colors')
        values = [1.0] * (4 * loop_count)
    elif recorded is None:
        # imported before normals were recorded: nothing tells an edited corner from an untouched
        # one, so keep the bytes as they are (from now on edits are detected)
        record_vertex_normals(mesh, normals)
        return
    else:
        values = [0.0] * (4 * loop_count)
        colors.data.foreach_get('color', values)
    for i in range(loop_count):
        n = normals[3*i:3*i + 3]
        if recorded is not None and sum((a - b) ** 2 for a, b in zip(n, recorded[3*i:3*i + 3])) < NORMAL_MATCH ** 2:
            continue
        length = math.sqrt(n[0]*n[0] + n[1]*n[1] + n[2]*n[2])
        for j in range(3):
            c = round(n[j] / length * 127) if length > 1e-6 else 0
            values[4*i + j] = (max(-127, min(127, c)) & 0xFF) / 255
    colors.data.foreach_set('color', values)
    # the bytes now match the current normals, so exporting again keeps them
    record_vertex_normals(mesh, normals)

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

        # Read everything in bulk; per-element RNA access dominated export time on big meshes.
        loop_count = len(d.loops)
        co = [0.0] * (3 * len(d.vertices))
        d.vertices.foreach_get('co', co)
        loop_verts = [0] * loop_count
        d.loops.foreach_get('vertex_index', loop_verts)
        loop_starts = [0] * len(d.polygons)
        d.polygons.foreach_get('loop_start', loop_starts)
        loop_totals = [0] * len(d.polygons)
        d.polygons.foreach_get('loop_total', loop_totals)
        uvs = None
        if uv_data:
            uvs = [0.0] * (2 * loop_count)
            uv_data.foreach_get('uv', uvs)
        colors = None
        if color_data:
            colors = [0.0] * (4 * loop_count)
            color_data.foreach_get('color', colors)

        # Each vertex takes the uv of its first loop (in polygon order) and the color of the last
        # loop with that same uv, as VisualsVertChunk.unmake does when called once per loop.
        scale = self.model.scale
        for start, total in zip(loop_starts, loop_totals):
            for loop_index in range(start, start + total):
                vert_index = loop_verts[loop_index]
                vert = self.data[vert_index]
                if not vert.unmade:
                    vert.co = [round(c/scale) for c in co[3*vert_index:3*vert_index + 3]]
                if uvs is not None:
                    new_uv = [round(c*4096) for c in uvs[2*loop_index:2*loop_index + 2]]
                    if vert.unmade and vert.uv != new_uv:
                        continue
                    vert.uv = new_uv
                if colors is not None:
                    vert.color.unmake(colors[4*loop_index:4*loop_index + 4])
                vert.unmade = True

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
    
# The F3DEX2 vertex cache: a gSPVertex can load into slots [0, 32) only. SW_RACER_RE
# dinput_hook/renderer_hook.cpp sizes its array at 256 just to draw older add-on exports.
VERTEX_CACHE_SIZE = 32

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
        # vertices loaded (n) and the vertex cache slot they load into (v0); slots below v0 hold
        # the hooked prefix, the v0 vertices stored just before `start` (SW_RACER_RE
        # dinput_hook/renderer_hook.cpp, the gSPVertex case of the display list parse)
        self.n = 0
        self.v0 = 0
        
    def read(self, buffer, cursor, vert_buffer_addr):
        self.type, self.unk1, self.unk2, self.max, start = struct.unpack_from(self.format_string, buffer, cursor)
        self.start = round((start - vert_buffer_addr)/16)
        self.n = ((((self.unk1 << 8) | self.unk2) >> 4) & 0xFF)
        self.v0 = (self.max >> 1) - self.n
        if self.n == 0:
            # older add-on exports left n out and wrote v0 + n with v0 = 0; read them the way
            # SW_RACER_RE's fixup_n64_display_list does
            self.n = self.v0
            self.v0 = self.parent.parent.group_count
        return cursor + self.size
    
    def to_array(self):
        return [self.type, self.unk1, self.unk2, self.max, self.start]
    
    def write(self, buffer, cursor):
        self.model.highlight(cursor + 4)
        n_packed = self.n << 4
        struct.pack_into(self.format_string, buffer, cursor, self.type, n_packed >> 8, n_packed & 0xFF, (self.v0 + self.n) << 1, self.start)
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
                # triangles index vertex cache slots; slot s holds buffer vertex start - v0 + s
                start = chunk.start - chunk.v0
            elif chunk.type == 5:
                faces.append([start + chunk.f1, start + chunk.f2, start + chunk.f3])
            elif chunk.type == 6:
                faces.append([start + chunk.f1, start + chunk.f2, start + chunk.f3])
                faces.append([start + chunk.f4, start + chunk.f5, start + chunk.f6])
        return faces
    
    def to_array(self):
        return [d.to_array() for d in self.data]
    
    def unmake(self, loads):
        """Builds the display list from Mesh.unmake's vertex loads.

        loads: (start, n, faces) per gSPVertex, which loads buffer vertices [start, start + n)
        into cache slots [v0, v0 + n), v0 = vertex_base_offset; faces index cache slots. Every
        load must use that v0 (SW_RACER_RE dinput_hook/renderer_hook.cpp aborts otherwise), and
        triangles are paired into gSP2Triangles only within one load.
        """
        v0 = self.parent.group_count
        for start, n, faces in loads:
            assert v0 + n <= VERTEX_CACHE_SIZE, f"vertex load of {n} at slot {v0} in {self.parent.original_object.name}"
            chunk1 = VisualsIndexChunk1(self, self.model, 1)
            chunk1.v0 = v0
            chunk1.start = start
            chunk1.n = n
            chunk1.max = v0 + n
            self.data.append(chunk1)
            for i in range(0, len(faces) - 1, 2):
                self.data.append(VisualsIndexChunk6(self, self.model, 6).from_array(faces[i] + faces[i + 1]))
            if len(faces) % 2:
                self.data.append(VisualsIndexChunk5(self, self.model, 5).from_array(faces[-1]))
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
    
MAX_TEXTURES = 1700

class MaterialTexture(DataStruct):
    NO_TEXTURE = 65535  # low half of the stock "no texture" word 0x0AFFFFFF
    # Stock textures that some material gives a specs[1] but whose block entry is in plain row
    # order (deswizzling scrambles them): 80, the Boonta crowd (models 1 and 115 use it without a
    # chain, model 127 with 966's chain), and 97/98, the Boonta sand, whose specs[1] is a
    # second full-size tile with num_children 0 rather than a mip level. renderer_hook.cpp:828
    # deswizzles these too; checked by eye against the deswizzled 924, 966, 972, 991, 992,
    # 1000, 1014, 1048 and 1064.
    STORED_UNSWIZZLED = {80, 97, 98}

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
        # unk0 and the four u16s after height (types.h swrModel_MaterialTexture unk2..unk5) as
        # read, written back while the texture keeps its size and format (Material.unmake)
        self.stock_unk0 = None
        self.stock_sizes = None
        self.id = 0
        # specs[1..4] (mip levels) as read, None where null, and the fields that go with them.
        # Stock textures with specs[1] set are stored swizzled (see read, STORED_UNSWIZZLED).
        self.lod_chunks = [None] * 4
        self.lod_fields = None

    @property
    def lod(self):
        return self.lod_chunks[0] is not None

    def image_name(self):
        # a use with a mip chain gets its own image: it is shown deswizzled and carries the chain
        # for export, and stock texture 80 is used both with one (model 127) and without (1, 115)
        if self.lod:
            return f"{self.id}_lod"
        # a use at a larger size than the block entry holds (Pixels.read) is a different image
        # from the texture at its stored size, which other models use under the plain id
        textureblock = getattr(getattr(self.model, 'modelblock', None), 'textureblock', None)
        if textureblock is not None and self.id != MaterialTexture.NO_TEXTURE and self.format in format_map \
                and 0 <= self.id < len(textureblock.data):
            pixel_buffer = textureblock.fetch(self.id)[0]
            if pixel_buffer is not None and \
                    len(pixel_buffer) < needed_pixel_bytes(self.width, self.height, self.format):
                return f"{self.id}_{self.width}x{self.height}"
        return str(self.id)

    def read(self, buffer, cursor):
        if cursor == 0:
            return None

        if cursor in self.model.textures:
            return self.model.textures[cursor]

        unk_pointers = []
        self.id = cursor
        self.unk0, unk1, unk3, self.format, self.unk4, self.width, self.height, unk5, unk6, self.unk7, self.unk8, *unk_pointers, self.unk9, self.id = struct.unpack_from(self.format_string, buffer, cursor)
        # specs[0] is the tile (UV mirror/clamp flags), specs[1..4] mip levels (SW_RACER_RE
        # src/types.h:1592-1624 swrModel_MaterialTexture). A texture with specs[1] set is stored
        # in the N64's swizzled TMEM layout (dinput_hook/renderer_hook.cpp:820-835).
        specs = unk_pointers[:5]
        if specs[0]:
            self.chunks.append(MaterialTextureChunk(self, self.model).read(buffer, specs[0]))
        for i, pointer in enumerate(specs[1:]):
            if pointer:
                self.lod_chunks[i] = MaterialTextureChunk(self, self.model).read(buffer, pointer)
        if self.lod:
            # num_children and the four u16s after height, written back with the chain
            self.lod_fields = [self.unk4, unk5, unk6, self.unk7, self.unk8]
        self.stock_unk0 = self.unk0
        self.stock_sizes = [unk5, unk6, self.unk7, self.unk8]

        self.model.textures[cursor] = self

        return self.model.textures[cursor]

    def to_array(self):
        return [self.unk0, 0, 0, self.format, self.unk4, self.width, self.height, 0, 0, self.unk7, self.unk8, *[0,0,0,0,0,0], self.unk9, self.id]

    def make(self):
        if self.id == MaterialTexture.NO_TEXTURE:
            return
        textureblock = self.model.modelblock.textureblock
        self.texture = Texture(self.id, self.format, self.width, self.height, swizzled = self.lod and self.id not in MaterialTexture.STORED_UNSWIZZLED, name = self.image_name())
        pixel_buffer, palette_buffer = textureblock.fetch(self.id)
        self.texture.read(pixel_buffer, palette_buffer)
        image = self.texture.make()
        if image is not None:
            # the block entry's hash, as Block.read computes it, so an unchanged image re-exports
            # as this entry instead of being re-encoded and appended again
            image['external_hash'] = compute_hash(b''.join(b for b in (pixel_buffer, palette_buffer) if b))
            if self.lod:
                # Only the deswizzled base level is shown. While the image is unchanged it
                # re-exports as the stock entry, which is still swizzled, so it keeps the mip chain
                # that tells the renderer to deswizzle it (keep_lod).
                image['lod_chain'] = {'fields': self.lod_fields,
                                      **{str(i + 1): chunk.to_array() for i, chunk in enumerate(self.lod_chunks) if chunk}}
        return image

    def keep_lod(self, image):
        """Write the image's stock mip chain back: it re-exports as its swizzled stock entry."""
        chain = image.get('lod_chain')
        if chain is None:
            return
        self.lod_fields = [int(v) for v in chain['fields']]
        for i in range(4):
            values = chain.get(str(i + 1))
            if values is None:
                continue
            chunk = MaterialTextureChunk(self, self.model)
            chunk.unk0, chunk.unk1, chunk.unk2, chunk.unk3, chunk.unk4, chunk.unk5 = (int(v) for v in values)
            self.lod_chunks[i] = chunk

    def unmake(self, image, untextured = None):
        if image is None:
            # A texture slot with no texture (an empty image node): write the game's "no texture"
            # index rather than texture 0. The file stores the index as 0x0A000000 | index and
            # stock untextured slots hold 0x0AFFFFFF, i.e. index -1 (SW_RACER_RE src/types.h
            # swrModel_MaterialTexture, src/Swr/swrModel.c texture index patch-up).
            self.id = MaterialTexture.NO_TEXTURE
            self.unk9 = 0x0AFF
            if untextured:
                self.width, self.height, self.format = (int(v) for v in untextured)
            self.chunks.append(MaterialTextureChunk(self, self.model).unmake(self)) #this struct is required
            return self

        if 'id' in image:
            self.id = int(image['id'])

        if 'format' in image:
            self.format = int(image['format'])

        self.width, self.height = image.size
        self.chunks.append(MaterialTextureChunk(self, self.model).unmake(self)) #this struct is required

        if self.model is None:
            return self

        #check if we already wrote this image
        if image.name in self.model.image_map:
            self.id = self.model.image_map[image.name]
            self.keep_lod(image)
            print(image.name,'already written as', self.id)
        elif self.model.texture_export:
            hash = compute_image_hash(image)
            
            #if user has made no changes
            if hash == image.get('internal_hash'):
                if self.id < 1648: #do nothing for vanilla
                    self.keep_lod(image)
                    return self

                # prefer the image's already-assigned id if it still holds matching data,
                # so re-exports stay deterministic even when two textureblock entries are byte-identical
                # (fetch_by_hash returns whichever colliding entry was last loaded into hash_table)
                stored_id = self.id
                tb_data = self.model.textureblock.data
                if 0 <= stored_id < len(tb_data) and tb_data[stored_id] and any(tb_data[stored_id]):
                    stored_buffer = b''.join([item for item in tb_data[stored_id] if item])
                    if compute_hash(stored_buffer) == image.get('external_hash'):
                        self.model.image_map[image.name] = stored_id
                        self.keep_lod(image)
                        print('found', image.name, 'already in modelblock as', stored_id)
                        return self

                # fall back to hash search if the original slot is gone or out of date
                id = self.model.textureblock.fetch_by_hash(image.get('external_hash'))
                if id is not None:
                    self.id = id
                    image['id'] = id
                    self.model.image_map[image.name] = id
                    self.keep_lod(image)
                    print('found', image.name, 'already in modelblock as', id)
                    return self
            
            # Edited: it is encoded as a new single-level texture in plain (unswizzled) row order,
            # as stock single-tile textures are (num_children 0, specs[1..4] null), so the stock
            # mip chain no longer applies and the mip levels are dropped.
            if 'lod_chain' in image:
                del image['lod_chain']
            image['internal_hash'] = hash
            id = len(self.model.textureblock.data)
            self.id = id
            image['id'] = id
            texture = Texture(id, self.format).unmake(image, self.format)
            self.format = texture.format
            image['format'] = self.format
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
            if id >= MAX_TEXTURES:
                raise ValueError(f"Too many textures: the game hangs on load with more than {MAX_TEXTURES} "
                                 f"(SW_RACER_RE src/Swr/swrModel.c swrModel_InitializeTextureBuffer)")
            self.model.textureblock.inject([pixel_buffer, palette_buffer], id)
            

        return self

    def write(self, buffer, cursor):
        chunk_addr = cursor + 28
        self.model.highlight(cursor + 56)
        # NOTE: several fields here (the 2H scale params, unk4, the two mip-size
        # params, and unk7/unk8) are synthesized rather than round-tripped. On
        # export this struct is always built via unmake() from Blender data, so
        # the original values read on import are not available. The constants and
        # width/height-derived formulas below produce files the game loads
        # correctly (verified in-game over long use); making this a true byte
        # round-trip would require persisting the read values on the image's
        # custom properties. See RE swrModel_MaterialTexture for field meanings.
        # res is the texture size in 10.2 fixed point, (w*4, h*4) in every stock texture; the game
        # divides texture offsets and UV scroll by it (SW_RACER_RE src/Swr/swrModel.c
        # swrModel_UpdateTextureScrollAnimation, dinput_hook/renderer_hook.cpp), so h*8 halved any
        # V offset. Only specs[0] (the tile written below) may be set: the replacement renderer
        # treats a non-null specs[1] as a mip chain and unswizzles the texture
        # (renderer_hook.cpp, deswizzle_lod_texture). Stock single-tile textures have
        # num_children 0 and specs[1..4] and unk6 0. The exception is an unedited stock texture
        # that had a mip chain: its entry is still swizzled, so the chain, num_children and the
        # u16s after height are written back as read (keep_lod; renderer_hook.cpp:828).
        if self.lod and self.lod_fields is not None:
            num_children, *sizes = self.lod_fields
        elif self.stock_sizes is not None:
            num_children, sizes = 0, self.stock_sizes
        else:
            num_children, sizes = 0, [min(self.width*512, 65535), min(self.height*512, 65535), 683, 503]
        unk0 = self.stock_unk0 if self.stock_unk0 is not None else 0
        struct.pack_into(self.format_string, buffer, cursor, unk0, min(self.width*4, 32767),min(self.height*4, 32767), self.format, num_children, self.width, self.height, *sizes, *[0, 0, 0, 0, 0, 0], self.unk9, self.id)
        cursor += self.size

        specs = [(0, chunk) for chunk in self.chunks[:1]]
        if self.lod:
            specs += [(i + 1, chunk) for i, chunk in enumerate(self.lod_chunks) if chunk]
        for i, chunk in specs:
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
        # 0x8 = for alpha mask
        self.combiner_cycle_type = 2 
        # 1 for skyboxes + 114, 2 for everything else
        
        # combine mode: http://n64devkit.square7.ch/n64man/gdp/gDPSetCombineLERP.htm
        # these values seem to be unused by the pc version
        self.color_combine_mode_cycle1 = 0# 0b1000111110000010000011111
        #self.color_combine_mode_cycle1 = 3 use base color?
        self.alpha_combine_mode_cycle1 = 0#0b111000001110000011100000100
        #self.alpha_combine_mode_cycle1 = 0x03000000
        self.color_combine_mode_cycle2 = 0#0b11111000111110001111100000000
        self.alpha_combine_mode_cycle2 = 0#0b111000001110000011100000000
        # render mode: http://n64devkit.square7.ch/n64man/gdp/gDPSetRenderMode.htm
        self.render_mode_1 = RM_OPAQUE[0]
        # 0x008 = aa
        # 0x010 = zcm (off for skybox)
        # 0x800 = transparency
        
        self.render_mode_2 = RM_OPAQUE[1]
        self.color_combine_mode_cycle1, self.alpha_combine_mode_cycle1, \
            self.color_combine_mode_cycle2, self.alpha_combine_mode_cycle2 = DEFAULT_COMBINERS
        self.unk5 = 0
        self.unk8 = 0
        # 0b11001000000100000100100101111000	1	    weird material in bwr ice reflection
        # 0b11001000000100000100101101010000	1	    transparent death beam on oovo
        # 0b11001000000100010010000001111000	15	    broken textures
        # 0b11001000000100000100100111011000	113	    reserved for semi-transparent textures (format 3)
        # 0b11001000000100000100100101111001	225	    textures with transparency (format 513)
        #     0b1100000110000100100101001000    6	    transparent skybox (oovo asteroids)
        #     0b1111000010100010000000001000    342	    skybox materials
        # 0b11001000000100010010000000111000	2246	everything else
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
        # u16s at +22 and +32 (SW_RACER_RE src/types.h swrModel_Material unk5, unk8)
        self.unk5 = readUInt16BE(buffer, cursor + 22)
        self.unk8 = readUInt16BE(buffer, cursor + 32)
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
        material['unk5'] = self.unk5
        material['unk8'] = self.unk8

        # Translucent: the cycle-2 blender blends with the framebuffer, or the z mode is XLU. A
        # loose bit test (0x800 in either word, or unk1 == 8) missed stock blend modes with an
        # opaque z mode and kept a toggle that could never be cleared.
        material.transparent = render_mode_is_translucent(self.render_mode_1 | self.render_mode_2)
    
    def unmake(self, material):
        if material is not None:
            
            self.unk1 = material.get('unk1', self.unk1)
            self.combiner_cycle_type = material.get('combiner_cycle_type', self.combiner_cycle_type)
            self.unk5 = material.get('unk5', self.unk5)
            self.unk8 = material.get('unk8', self.unk8)
            self.color.unmake(material.material_color)

            # A material made in Blender has none of these; it keeps the stock defaults set in
            # __init__. All-zero combiners (written by older versions of the add-on) make cycle 1
            # output COMBINED = 0, i.e. black, in the replacement renderer.
            combiners = [int(material.get(key, default)) for key, default in (
                ('color_combine_mode_cycle1', self.color_combine_mode_cycle1),
                ('alpha_combine_mode_cycle1', self.alpha_combine_mode_cycle1),
                ('color_combine_mode_cycle2', self.color_combine_mode_cycle2),
                ('alpha_combine_mode_cycle2', self.alpha_combine_mode_cycle2))]
            if any(combiners):
                self.color_combine_mode_cycle1, self.alpha_combine_mode_cycle1, \
                    self.color_combine_mode_cycle2, self.alpha_combine_mode_cycle2 = combiners

            if 'render_mode_1' in material:
                self.render_mode_1 = int(material['render_mode_1'])
            if 'render_mode_2' in material:
                self.render_mode_2 = int(material['render_mode_2'])
            if (self.render_mode_1, self.render_mode_2) in RM_LEGACY_DEFAULTS:
                self.render_mode_1, self.render_mode_2 = RM_TRANSLUCENT if self.render_mode_1 & RM_ZMODE_XLU else RM_OPAQUE

            # Only rewrite the render mode when the Transparent toggle disagrees with it, so an
            # untouched material exports exactly as imported. 0x8 in unk1 goes with stock
            # translucent mode.
            translucent = render_mode_is_translucent(self.render_mode_1 | self.render_mode_2)
            if material.transparent and not translucent:
                self.render_mode_1 = (self.render_mode_1 & RM_CYCLE1_MASK) | RM_TRANSLUCENT[0]
                self.render_mode_2 = RM_TRANSLUCENT[1]
                self.unk1 |= 8
            elif not material.transparent and translucent:
                self.render_mode_1 = (self.render_mode_1 & RM_CYCLE1_MASK) | RM_OPAQUE[0]
                self.render_mode_2 = RM_OPAQUE[1]
                self.unk1 &= ~8
    
        # alternate way to detect if this material is on a skybox mesh
        mat = self.parent
        mesh = mat.parent
        if mat.parent:
            obj = mesh.original_object
            for collection in object_collections(obj, self.model):
                if collection.collection_type == '1':
                    # render modes have to be these exact values to fix small stitching issues;
                    # scrolling and translucent layers keep theirs without z compare, as stock
                    # translucent sky layers have (e.g. 0x0C184948)
                    if mat.scroll_x or mat.scroll_y or render_mode_is_translucent(self.render_mode_1 | self.render_mode_2):
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
        struct.pack_into('>H', buffer, cursor + 22, self.unk5)
        struct.pack_into('>H', buffer, cursor + 32, self.unk8)
        self.color.write(buffer, cursor + 34)
        return cursor + self.size
    

# MARK: COMBINER

class CombinerValue:
    """A color combiner input or intermediate: a constant, or a node socket in the material."""
    def __init__(self, const = None, socket = None):
        self.const = const
        self.socket = socket

    def is_const(self, value):
        return self.socket is None and self.const == value

def make_combiner_nodes(tree, shader, image_node, normals):
    """Base color and alpha sockets computing the material's N64 color combiner.

    Follows the replacement renderer's fragment shader (SW_RACER_RE assets/shaders/n64_shader.frag,
    dinput_hook/n64_shader.cpp CombineMode): both cycles always run, each (A - B) * C + D on the
    inputs its 4 mux bytes select. TEXEL0 and TEXEL1 are the texture (white without one), SHADE the
    vertex color, PRIMITIVE the material color, ENVIRONMENT and the other constants 1, and cycle 1's
    COMBINED is 0. With a normals vertex format SHADE is the game's lighting, which Blender's
    own shading stands in for, so it is 1 here.
    """
    nodes = tree.nodes
    column = [0]

    def node(kind, operation):
        n = nodes.new(kind)
        n.operation = operation
        n.location = (200 + 150 * (column[0] // 6), 400 - 120 * (column[0] % 6))
        column[0] += 1
        return n

    one, zero = CombinerValue(1.0), CombinerValue(0.0)
    if image_node is not None:
        texel = (CombinerValue(socket = image_node.outputs["Color"]), CombinerValue(socket = image_node.outputs["Alpha"]))
    else:
        texel = (one, one)
    if normals:
        shade = (one, one)
    else:
        shade_node = nodes.new("ShaderNodeVertexColor")
        shade_node.location = (-200, -200)
        shade = (CombinerValue(socket = shade_node.outputs["Color"]), CombinerValue(socket = shade_node.outputs["Alpha"]))
    prim = [c / 255 for c in shader.color.to_array()]
    primitive = (CombinerValue(tuple(prim[:3])), CombinerValue(prim[3]))

    def as_color(value):
        if value.socket is None and not isinstance(value.const, tuple):
            return CombinerValue((value.const,) * 3)
        return value

    def operate(a, b, operation, is_color):
        """a (op) b, folding constants; is_color picks vector or scalar math."""
        if a.socket is None and b.socket is None:
            if is_color:
                a, b = as_color(a), as_color(b)
                return CombinerValue(tuple(operation_py(operation, x, y) for x, y in zip(a.const, b.const)))
            return CombinerValue(operation_py(operation, a.const, b.const))
        n = node("ShaderNodeVectorMath" if is_color else "ShaderNodeMath", operation)
        for i, value in enumerate((a, b)):
            if value.socket is not None:
                tree.links.new(value.socket, n.inputs[i])
            elif is_color:
                n.inputs[i].default_value = as_color(value).const
            else:
                n.inputs[i].default_value = value.const
        return CombinerValue(socket = n.outputs[0])

    def operation_py(operation, x, y):
        return x - y if operation == 'SUBTRACT' else x * y if operation == 'MULTIPLY' else x + y

    def zero_like(value):
        return value.is_const(0.0) or value.is_const((0.0, 0.0, 0.0))

    def one_like(value):
        return value.is_const(1.0) or value.is_const((1.0, 1.0, 1.0))

    def combine(a, b, c, d, is_color):
        # (a - b) * c + d
        if a is b or (a.socket is None and b.socket is None and as_color(a).const == as_color(b).const):
            difference = zero
        elif zero_like(b):
            difference = a
        else:
            difference = operate(a, b, 'SUBTRACT', is_color)
        if zero_like(difference) or zero_like(c):
            product = zero
        elif one_like(c):
            product = difference
        elif one_like(difference):
            product = c
        else:
            product = operate(difference, c, 'MULTIPLY', is_color)
        if zero_like(d):
            return product
        if zero_like(product):
            return d
        return operate(product, d, 'ADD', is_color)

    def color_input(mux, combined):
        # SW_RACER_RE dinput_hook/n64_shader.cpp cc_mode_strings, n64_shader.h G_CCMUX_*
        return {0: combined[0], 1: texel[0], 2: texel[0], 3: primitive[0], 4: shade[0], 5: one, 6: one,
                7: combined[1], 8: texel[1], 9: texel[1], 10: primitive[1], 11: shade[1], 12: one,
                13: one, 14: one, 15: one}.get(mux, zero)

    def alpha_input(mux, combined):
        # ac_mode_strings, G_ACMUX_*: 0 is COMBINED (it shares the value with LOD_FRACTION)
        return {0: combined[1], 1: texel[1], 2: texel[1], 3: primitive[1], 4: shade[1], 5: one, 6: one}.get(mux, zero)

    def muxes(word):
        return [(word >> shift) & 0xFF for shift in (24, 16, 8, 0)]

    combined = (zero, zero)
    for color_word, alpha_word in ((shader.color_combine_mode_cycle1, shader.alpha_combine_mode_cycle1),
                                   (shader.color_combine_mode_cycle2, shader.alpha_combine_mode_cycle2)):
        color = combine(*(color_input(m, combined) for m in muxes(color_word)), True)
        alpha = combine(*(alpha_input(m, combined) for m in muxes(alpha_word)), False)
        combined = (color, alpha)

    def socket(value, is_color):
        if value.socket is not None:
            return value.socket
        n = nodes.new("ShaderNodeRGB" if is_color else "ShaderNodeValue")
        n.location = (900, 200 if is_color else -200)
        if is_color:
            n.outputs[0].default_value = (*as_color(value).const, 1.0)
        else:
            n.outputs[0].default_value = value.const
        return n.outputs[0]

    return socket(combined[0], True), socket(combined[1], False)

# MARK: MATERIAL

class Material(DataStruct):
    def __init__(self, parent, model):
        # Layout per RE swrModel_MeshMaterial: uint32 type, int16 texture_offset[2],
        # MaterialTexture*, Material*. The two shorts after the type were being
        # skipped (4x) and written as zero, dropping any texture offset. They are
        # read/stored/written now so materials with type & 0x80 round-trip.
        super().__init__('>I2hII')
        self.parent = parent
        self.id = None
        self.model = model
        self.format = 14
        self.texture_offset = [0, 0]
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
        # offsets are only unique within one model, so namespace the id by model
        self.id = f"{self.model.id}_{cursor}"
        self.format, off_x, off_y, texture_addr, shader_addr = struct.unpack_from(self.format_string, buffer, cursor)
        self.texture_offset = [off_x, off_y]

        self.texture = MaterialTexture(self, self.model).read(buffer, texture_addr)

        # there should always be a shader_addr otherwise game will crash
        assert shader_addr > 0, "Material should have shader"
        self.shader.read(buffer, shader_addr)
        return self

    def to_array(self):
        return [self.format, self.texture_offset[0], self.texture_offset[1], 0, 0]
        
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
        tree = material.node_tree
        output_node = tree.nodes.new(type='ShaderNodeOutputMaterial')
        output_node.location = (1400, 0)
        node_0 = tree.nodes.new('ShaderNodeBsdfPrincipled')
        node_0.location = (1100, 0)
        node_0.inputs["Specular IOR Level"].default_value = 0
        material.material_color = [c/255 for c in self.shader.color.to_array()]
        # Preserve the texture offset (RE texture_offset[2]) so it survives a
        # round-trip even though it is not exposed in the UI.
        material['texture_offset'] = self.texture_offset
        tree.links.new(node_0.outputs['BSDF'], output_node.inputs['Surface'])
        material['id'] = self.id
        material['format'] = self.format
        # RE: a mesh uses the Vtx_tn (normals) vertex format when the material
        # type has bit 0x1 OR 0x10 set.
        material['normal_map'] = bool(self.format & 0x11)

        self.shader.make(material)
        material.use_backface_culling = bool(self.format & 8)
        material.preview_render_type = 'FLAT'

        image_node = None
        if not (self.texture is None and tex_name is None):
            tex_name = tex_name or self.texture.image_name()

            set_material_prop(material, 'scroll_x', float(self.scroll_x))
            set_material_prop(material, 'scroll_y', float(self.scroll_y))
            set_material_prop(material, 'clip_x', bool(self.clip_x))
            set_material_prop(material, 'clip_y', bool(self.clip_y))

            image_node = tree.nodes.new("ShaderNodeTexImage")
            image_node.location = (-200, 300)
            self.make_uv_nodes(material, image_node, remake)

            b_tex = bpy.data.images.get(tex_name)
            if b_tex is None:
                b_tex = self.texture_image
            if b_tex is None and self.texture and self.model is not None:
                b_tex = self.texture.make()
            image_node.image = b_tex
            if self.texture and self.texture.id == MaterialTexture.NO_TEXTURE:
                # a texture slot without a texture: keep its size and format so export writes it back
                material['untextured_texture'] = [self.texture.width, self.texture.height, self.texture.format]
            if self.texture is not None and self.texture.stock_sizes is not None and self.texture.chunks:
                # The texture struct and tile fields the add-on can't derive (stock tiles hold e.g.
                # log2 sizes and (size - 1) * 4; SW_RACER_RE src/types.h swrModel_MaterialTexture,
                # swrModel_MaterialTextureChild). The game's texture converter isn't decompiled, so
                # export writes them back as read rather than guessing (Material.unmake). They
                # belong to this material's texture slot, not the image: one image is used with
                # different tiles.
                material['texture_fields'] = {
                    'size': [self.texture.width, self.texture.height, self.texture.format],
                    'unk0': self.texture.stock_unk0,
                    'sizes': list(self.texture.stock_sizes),
                    'tile': self.texture.chunks[0].to_array(),
                }
            if b_tex is None:
                image_node = None  # samples as white in game (renderer_hook.cpp default texture)

        # NOTE: texture-swap animation (self.texture_anim) is not implemented.
        # See TexturePose.write, which is likewise a stub, for the export side of this feature.
        color, alpha = make_combiner_nodes(tree, self.shader, image_node, material['normal_map'])
        tree.links.new(color, node_0.inputs["Base Color"])

        render_mode = self.shader.render_mode_1 | self.shader.render_mode_2
        if render_mode_is_cutout(render_mode):
            # the renderer discards texels under 0.5 alpha and draws the rest opaque (n64_shader.frag)
            cutoff = tree.nodes.new("ShaderNodeMath")
            cutoff.operation = 'GREATER_THAN'
            cutoff.inputs[1].default_value = 0.5
            cutoff.location = (900, -300)
            tree.links.new(alpha, cutoff.inputs[0])
            tree.links.new(cutoff.outputs[0], node_0.inputs["Alpha"])
            set_material_blend(material, 'OPAQUE')
        elif render_mode_is_alpha_blend(render_mode):
            tree.links.new(alpha, node_0.inputs["Alpha"])
            set_material_blend(material, 'BLEND')
        else:
            # opaque modes never use alpha, so near-zero texture alpha must not punch holes
            set_material_blend(material, 'OPAQUE')
        return material

    def make_uv_nodes(self, material, image_node, remake):
        """UVs the way the game samples them: scroll, static offset, then per-axis clamp and mirror."""
        tree = material.node_tree
        uv = None
        mapping_node = None
        if self.scroll_x != 0 or self.scroll_y != 0:
            shader_node = tree.nodes.new("ShaderNodeTexCoord")
            shader_node.location = (-1200, 300)
            mapping_node = tree.nodes.new("ShaderNodeMapping")
            mapping_node.location = (-1000, 300)
            tree.links.new(shader_node.outputs["UV"], mapping_node.inputs["Vector"])
            uv = mapping_node.outputs["Vector"]

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

            if tree.animation_data is not None and tree.animation_data.action is not None:
                bag = anim_utils.action_get_channelbag_for_slot(tree.animation_data.action, tree.animation_data.action_slot)
                for fcurves_f in bag.fcurves:
                    ensure_cycles_first(fcurves_f)
                    for k in fcurves_f.keyframe_points:
                        k.interpolation = 'LINEAR'

        # Tile flags (SW_RACER_RE dinput_hook/renderer_hook.cpp): 0x10 mirrors U, 0x01 mirrors V,
        # 0x20 clamps U, 0x02 clamps V. The flip/clip property names don't follow the axes; they
        # are kept as they are for existing files.
        chunk_tag = self.texture.chunks[0].unk1 if self.texture and len(self.texture.chunks) else 0
        if chunk_tag & 0x1:
            material.flip_x = True
        if chunk_tag & 0x10:
            material.flip_y = True
        if chunk_tag & 0x2:
            material.clip_x = True
        if chunk_tag & 0x20:
            material.clip_y = True

        texture = self.texture
        offsets = [0.0, 0.0]
        if texture is not None and texture.width and texture.height:
            # static offset in 1/4 texels over res = (w*4, h*4); the renderer adds -offset/res
            offsets = [self.texture_offset[0] / (texture.width * 4), self.texture_offset[1] / (texture.height * 4)]
        mirror = [bool(chunk_tag & 0x10), bool(chunk_tag & 0x01)]
        clamp = [bool(chunk_tag & 0x20), bool(chunk_tag & 0x02)]
        if not (any(mirror) or any(clamp) or any(offsets)):
            if uv is not None:
                tree.links.new(uv, image_node.inputs["Vector"])
            return

        if uv is None:
            uv_node = tree.nodes.new("ShaderNodeUVMap")
            uv_node.location = (-1000, 300)
            uv = uv_node.outputs["UV"]
        separate = tree.nodes.new("ShaderNodeSeparateXYZ")
        separate.location = (-800, 300)
        combine = tree.nodes.new("ShaderNodeCombineXYZ")
        combine.location = (-400, 300)
        tree.links.new(uv, separate.inputs["Vector"])
        tree.links.new(combine.outputs["Vector"], image_node.inputs["Vector"])
        for axis in range(2):
            value = separate.outputs[axis]
            y = 300 - 150 * axis
            # a mirrored tile is baked to twice its size, so the offset and clamp range double
            scale = 2 if mirror[axis] else 1
            if offsets[axis]:
                shift = tree.nodes.new("ShaderNodeMath")
                shift.operation = 'SUBTRACT'
                shift.inputs[1].default_value = offsets[axis] * scale
                shift.location = (-650, y)
                tree.links.new(value, shift.inputs[0])
                value = shift.outputs[0]
            if clamp[axis]:
                limit = tree.nodes.new("ShaderNodeClamp")
                limit.inputs["Min"].default_value = 0
                limit.inputs["Max"].default_value = scale
                limit.location = (-550, y)
                tree.links.new(value, limit.inputs["Value"])
                value = limit.outputs[0]
            if mirror[axis]:
                pingpong = tree.nodes.new("ShaderNodeMath")
                pingpong.operation = 'PINGPONG'
                pingpong.inputs[1].default_value = 1
                pingpong.location = (-450, y)
                tree.links.new(value, pingpong.inputs[0])
                value = pingpong.outputs[0]
            tree.links.new(value, combine.inputs[axis])

    def unmake(self, material):
        material_name: str = ""

        if material:
            # the shader's skybox handling depends on the scroll
            self.scroll_x = get_material_prop(material, 'scroll_x')
            self.scroll_y = get_material_prop(material, 'scroll_y')
        self.shader.unmake(material)
        if material:
            self.name = material.name
            
            material_name = material.name #.split(".")[0]
            self.id = material_name
            if self.model and material_name in self.model.materials:
                return self.model.materials[material_name]
            
            self.scroll_x = get_material_prop(material, 'scroll_x')
            self.scroll_y = get_material_prop(material, 'scroll_y')
            self.clip_x = get_material_prop(material, 'clip_x')
            self.clip_y = get_material_prop(material, 'clip_y')
            self.texture_offset = list(material.get('texture_offset', [0, 0]))
            
            # if material.node_tree:
            for node in material.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    self.texture = MaterialTexture(self, self.model).unmake(node.image, material.get('untextured_texture'))
                    self.texture_image = node.image

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

            # write the imported texture struct and tile fields back while the texture keeps its
            # size and format; only the mirror/clamp bits (0x33) come from the material settings
            fields = material.get('texture_fields')
            if fields is not None and self.texture is not None and self.texture.chunks and \
                    [self.texture.width, self.texture.height, self.texture.format] == [int(v) for v in fields['size']]:
                self.texture.stock_unk0 = int(fields['unk0'])
                self.texture.stock_sizes = [int(v) for v in fields['sizes']]
                chunk = self.texture.chunks[0]
                bits = chunk.unk1 & 0x33
                chunk.unk0, chunk.unk1, chunk.unk2, chunk.unk3, chunk.unk4, chunk.unk5 = (int(v) for v in fields['tile'])
                chunk.unk1 = (chunk.unk1 & ~0x33) | bits

            # get animations
            if self.model:
                flipbook = material.get('flipbook')
                if flipbook is not None and flipbook.get('frames'):
                    self.model.animations.append(flipbook_anim(self, flipbook.to_dict(), self.model))
                # self.scroll_x/y come from get_material_prop, which also reads older imports
                for axis, scroll in (('uv_x', self.scroll_x), ('uv_y', self.scroll_y)):
                    if not scroll:
                        continue
                    poses = [0, 1] if scroll < 0 else [1, 0]
                    times = [0, abs(scroll) * self.model.fps]
                    anim = Anim(self, self.model).unmake(times, poses, axis, loop = True)
                    index = material.get(f'anim_index_{axis}')
                    if index is not None and index >= 0:
                        anim.index = int(index)
                    self.model.animations.append(anim)
                self.model.animations.extend(raw_anims(self, material, self.model))
        
            self.format = material.get('format')
            if self.format is None:
                self.format = 14

            # Only force the normals bit when the preserved format doesn't
            # already carry one (0x1 or 0x10). This keeps a vanilla 0x10 material
            # from being silently changed to 0x11 on re-export, while still
            # tagging a material the user newly marked as a normal map.
            if material.get('normal_map', False) and not (self.format & 0x11):
                self.format |= 0x01

            # 0x8 culls back faces; 0x40 culls front faces of mirrored geometry instead
            # (SW_RACER_RE src/types.h swrModel_MeshMaterial, renderer_hook.cpp)
            if material.use_backface_culling == False:
                self.format &= 0b11110111
            elif not self.format & 0x40:
                self.format |= 0x8
        
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
        struct.pack_into(self.format_string, buffer, material_start, self.format, self.texture_offset[0], self.texture_offset[1], tex_addr, shader_addr)
        return cursor
    def remake(self, material, tex_name = None):
        self.unmake(material)
        material = self.make(remake = True, tex_name = tex_name)
        return material

def bounding_vertices(mesh):
    """The vertices a mesh's bounding box is computed from: collision ones, else visual ones."""
    if mesh.collision_vert_buffer:
        verts = mesh.collision_vert_buffer.make()
        if len(verts):
            return verts
    if mesh.visuals_vert_buffer:
        return mesh.visuals_vert_buffer.make()
    return []

def identity_vertices(mesh):
    """The vertices that say whether a mesh is still the one imported: its visual ones if it has any.

    Collision vertices change on export even for an untouched mesh (they are re-stripped, and
    import drops faces that index past them), so they only count for collision-only meshes.
    """
    if mesh.visuals_vert_buffer:
        verts = mesh.visuals_vert_buffer.make()
        if len(verts):
            return verts
    return bounding_vertices(mesh)

def vertex_fingerprint(verts):
    return compute_hash(repr(sorted({tuple(int(round(c)) for c in v) for v in verts if len(v) == 3})).encode())

def deformed_vertices(obj, scale):
    """obj's evaluated (modifier-deformed) vertex positions in game units, in the object's space."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        return [[c / scale for c in v.co] for v in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()

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
        if mesh is None:
            return self
        verts = bounding_vertices(mesh)
        if len(verts) == 0:
            return self
        source = getattr(mesh, 'original_object', None)
        if source is not None and source.get('stock_aabb') is not None and                 source.get('stock_aabb_key') == vertex_fingerprint(identity_vertices(mesh)):
            # unchanged vertices: the stock box (see Mesh.keep_stock_aabb)
            self.min_x, self.min_y, self.min_z, self.max_x, self.max_y, self.max_z = (float(v) for v in source['stock_aabb'])
            return self
        if getattr(mesh, 'group_count', 0) and source is not None and source.type == 'MESH':
            # an edited hooked mesh: also cover the prefix where the HOOK modifier puts it
            verts = list(verts) + deformed_vertices(source, self.model.scale)
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
        island_bounds = None  # min_u, max_u, min_v, max_v of the current island's uvs

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
            face_bounds = get_uv_bounds(current_uv_coords)
            if island_bounds is not None:
                combined = (min(island_bounds[0], face_bounds[0]), max(island_bounds[1], face_bounds[1]),
                            min(island_bounds[2], face_bounds[2]), max(island_bounds[3], face_bounds[3]))
            else:
                combined = face_bounds

            if not (combined[1] - combined[0] <= max_tile_size and combined[3] - combined[2] <= max_tile_size):
                # Commit the current island and start a new one
                if current_island:
                    islands.append(current_island)
                current_island = []
                combined = face_bounds

            # Add the current face data
            face_data = {
                "face_index": current_face.index,
                "vertices": [v.co.copy() for v in current_face.verts],
                "vertex_indices": [v.index for v in current_face.verts],
                "uvs": current_uv_coords,
                "colors": [
                    [] if not color_layer else tuple(loop[color_layer])
                    for loop in current_face.loops
                ],
            }
            current_island.append(face_data)
            island_bounds = combined

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
        if not bb:
            # stock empty mesh groups store -1 for every bound (e.g. track 145)
            self.min_x = self.min_y = self.min_z = self.max_x = self.max_y = self.max_z = -1.0
            return self
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
        # import: indices into the collision vertices, when the collision primitives are indexed
        self.collision_indices = None
        # export: the Blender object a HOOK modifier anchors the hooked prefix to
        self.hook_target = None
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
        vis.hook_target = self.hook_target
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
        self.hook_target = vis.hook_target
        self.collision_vert_buffer = col.collision_vert_buffer
        self.visuals_index_buffer = vis.visuals_index_buffer
        self.visuals_vert_buffer = vis.visuals_vert_buffer
        self.group_count = vis.group_count
        
        self.original_object = vis.original_object
        self.bounding_box = MeshBoundingBox(self, self.model).unmake(self)
        return self
    
    def keep_stock_aabb(self, b_obj):
        """Record the mesh's stored bounding box, written back while its vertices are unchanged.

        A hooked mesh's box covers its shape with the hooked prefix where the game draws it,
        which can't be rebuilt from the stored vertices (the prefix is in the referenced node's
        space); computed from them it came out smaller than stock on most pilot meshes, so parts
        of the racers (feet) got culled. See MeshBoundingBox.unmake.
        """
        if getattr(self, 'stock_aabb', None) is None:
            return
        b_obj['stock_aabb'] = list(self.stock_aabb)
        b_obj['stock_aabb_key'] = vertex_fingerprint(identity_vertices(self))

    def read(self, buffer, cursor):
        self.id = cursor
        mat_addr, collision_tags_addr,min_x, min_y, min_z, max_x, max_y, max_z, self.strip_count, self.strip_size, vert_strips_addr, self.group_parent_id, collision_vert_buffer_addr, visuals_index_buffer_addr, visuals_vert_buffer_addr, collision_vert_count, visuals_vert_count, self.group_count = struct.unpack_from(self.format_string, buffer, cursor)
        self.stock_aabb = [min_x, min_y, min_z, max_x, max_y, max_z]
        
        
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
            if self.group_parent_id and not self.group_count:
                # With collision vertices, the word at +40 can be a list of u16 indices into them
                # (SW_RACER_RE src/types.h swrModel_Mesh, src/Swr/swrModel.c byte swap and
                # swrModel_MeshIterateOverCollisionFaces). A mesh with a hooked prefix
                # (vertex_base_offset) uses it for its referenced node instead: all 143 stock meshes
                # with both (cutscenes 149, 152, 289) point it at a mesh group node, and reading it
                # as indices dropped their hooks. No stock mesh has true indexed collision.
                if self.strip_size in (5, 7) and self.vert_strips is not None:
                    count = sum(self.vert_strips.data)
                else:
                    count = self.strip_size * self.strip_count
                self.collision_indices = list(struct.unpack_from(f'>{count}H', buffer, self.group_parent_id))
                self.group_parent_id = 0
                    
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
            if self.collision_indices is not None:
                # the primitives walk the index list, which picks the vertices; indexed strips repeat
                # an index to stitch strips together, and those zero-area faces collide with nothing
                faces = [[self.collision_indices[i] for i in face] for face in faces
                         if all(i < len(self.collision_indices) for i in face)]
                faces = [face for face in faces if len(set(face)) == 3]
            # Keep the faces the vertices can back; out-of-range faces make an invalid mesh that
            # crashes Blender in Edit mode.
            valid_faces = [face for face in faces if all(i < len(verts) for i in face)]
            if len(valid_faces) < len(faces):
                print(f"model {self.model.id} mesh {self.id}: dropped {len(faces) - len(valid_faces)} of {len(faces)} "
                      f"collision faces referencing missing vertices ({len(verts)} vertices)")
                faces = valid_faces
            mesh_name = '{:07d}'.format(self.id) + "_" + "collision"
            mesh = bpy.data.meshes.new(mesh_name)
            b_obj = bpy.data.objects.new(mesh_name, mesh)
            
            b_obj.collidable = True   
            b_obj.id = self.model.obj_key(self.id)
            self.keep_stock_aabb(b_obj)
            b_obj.scale = [self.model.scale, self.model.scale, self.model.scale]

            collection.objects.link(b_obj)
            mesh.from_pydata(verts, edges, faces)
            b_obj.parent = parent

            if(self.collision_tags is not None): 
                self.collision_tags.make(b_obj, collection)
                
            col_flags = effective_node_flags(parent, 'col_flags')
            for i in range(24):
                view_layer = bpy.context.scene.view_layers[i + 1]
                if col_flags is not None:
                    set_hidden(self.model, b_obj, not bool(col_flags & (1 << (i + 8))), view_layer)
                
        if self.has_visuals():
            
            verts = self.visuals_vert_buffer.make()
           
            edges = []
            faces = self.visuals_index_buffer.make()
            # source[i]: the buffer vertex behind mesh vertex i. A face on the same three vertices
            # as an earlier one (the back of a double-sided triangle: the game culls one side per
            # material, SW_RACER_RE dinput_hook/renderer_hook.cpp:901-910, so both windings draw)
            # gets its own copies of them: mesh.validate() deletes faces that repeat another's
            # vertices. Stock models store such pairs on separate vertices; export shares equal ones.
            source = list(range(len(verts)))
            seen_faces = set()
            for face in faces:
                key = frozenset(face)
                if len(key) == 3 and key in seen_faces and all(i < len(verts) for i in face):
                    copies = list(range(len(source), len(source) + 3))
                    source += face
                    verts += [verts[i] for i in face]
                    face[:] = copies
                seen_faces.add(key)
            mesh_name = '{:07d}'.format(self.id) + "_" + "visuals"
            mesh = bpy.data.meshes.new(mesh_name)
            b_obj = bpy.data.objects.new(mesh_name, mesh)
            b_obj.visible = True
            b_obj.id = self.model.obj_key(self.id)
            self.keep_stock_aabb(b_obj)
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
            uv_layer = b_obj.data.uv_layers.active.data
            color_layer = b_obj.data.vertex_colors.active.data                
            
            loop_verts = [0] * len(mesh.loops)
            mesh.loops.foreach_get('vertex_index', loop_verts)
            vert_data = self.visuals_vert_buffer.data
            uv_layer.foreach_set('uv', [u/4096 for i in loop_verts for u in vert_data[source[i]].uv])
            color_layer.foreach_set('color', [a/255 for i in loop_verts for a in vert_data[source[i]].color.to_array()])
            if uses_normals(self.material):
                make_vertex_normals(mesh)
                    
            vis_flags = effective_node_flags(parent, 'vis_flags')
            for i in range(24):
                view_layer = bpy.context.scene.view_layers[i + 1]
                if vis_flags is not None:
                    set_hidden(self.model, b_obj, not bool(vis_flags & (1 << (i+8))), view_layer)
                    
            if self.group_parent_id:
                vg = b_obj.vertex_groups.get(f'{self.id}')
                if vg is None:
                    vg = b_obj.vertex_groups.new(name=f'{self.id}')
                vg.add([i for i, s in enumerate(source) if s < self.group_count], 1.0, 'REPLACE')

                hook = b_obj.modifiers.new(name=f"Hook_{self.id}", type='HOOK')
                hook.vertex_group = vg.name
                hook.object = get_obj_by_id(self.model.obj_key(self.group_parent_id), self.model.collection)
                hook.falloff_type = 'NONE'
                # The game draws the hooked prefix with the referenced node's matrix applied to the
                # raw (game unit) coordinates (SW_RACER_RE dinput_hook/renderer_hook.cpp). The hook
                # gives hook.matrix_world @ matrix_inverse @ co, so the inverse carries the model scale.
                hook.matrix_inverse = mathutils.Matrix.Scale(self.model.scale, 4)

        
    
    def unmake(self, node, unmake_anim = True):
        self.original_object = node

        if not node.visible and not node.collidable:
            if self.model.type == '7':
                node.collidable = True
            node.visible = True

        self.id = node.name
        self.layers = get_object_view_layer_visibility(node) & 0xFFFFFF00

        # ensure mesh is triangulated
        triangulate_mesh([node])

        if unmake_anim:
            get_animations(node, self.model, self)

        # Detect HOOK modifier — the first N output vertices must belong to the
        # hooked vertex group so the game anchors them to group_parent_id at runtime.
        hooked_blender_indices = set()
        if node.type == 'MESH':
            for mod in node.modifiers:
                if mod.type != 'HOOK' or not mod.object or not mod.vertex_group:
                    continue
                # the target's new address is only known once the model is written (Model.write)
                self.hook_target = mod.object
                self.group_parent_id = 1
                vg = node.vertex_groups.get(mod.vertex_group)
                if vg is None:
                    continue
                vg_index = vg.index
                for v in node.data.vertices:
                    for g in v.groups:
                        if g.group == vg_index and g.weight > 0:
                            hooked_blender_indices.add(v.index)
                            break
                break

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

            # the normal bytes are already in 'colors' (Model.unmake, unmake_vertex_normals)
            normals = uses_normals(self.material)
            
            self.visuals_vert_buffer = VisualsVertBuffer(self, self.model).unmake(node)
            verts = self.visuals_vert_buffer.data
            # Tag verts created in Blender-vertex-index order with their hooked status
            # so the dedup pass can keep hooked verts distinct from non-hooked verts at
            # coincident positions (the seam case).
            for i, vc in enumerate(verts):
                vc._hooked = (i in hooked_blender_indices)
            faces = [[v for v in face.vertices] for face in node.data.polygons]

            if not len(faces) or not len(verts):
                return None

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
                            blender_idx = face.get('vertex_indices', [None]*len(face['vertices']))[j]
                            vert._hooked = (blender_idx is not None and blender_idx in hooked_blender_indices)
                            new_face.append(vert)
                        new_faces.append(new_face)
                faces = new_faces
            elif normals:
                # one vert per corner: corners of a vertex can differ in normal (a sharp edge),
                # and the dedup below merges the ones that are equal
                d = node.data
                uv_data = d.uv_layers.active.data if d.uv_layers and d.uv_layers.active else None
                color_data = d.vertex_colors.active.data if d.vertex_colors.active else None
                faces = []
                for poly in d.polygons:
                    face = []
                    for loop_index in poly.loop_indices:
                        vert_index = d.loops[loop_index].vertex_index
                        vert = VisualsVertChunk(self.visuals_vert_buffer, self.model)
                        vert.co = verts[vert_index].co
                        vert.uv = [round(c*4096) for c in uv_data[loop_index].uv] if uv_data else [0, 0]
                        if color_data is not None:
                            vert.color.unmake(color_data[loop_index].color)
                        vert._hooked = verts[vert_index]._hooked
                        face.append(vert)
                    faces.append(face)
            else:
                # replace each index with its vert
                faces = [[verts[i] for i in face] for face in faces]
            
            #TODO: Automatically split meshes?
            assert len(faces) <= 2048, f"Max faces reached in {node.name} {len(new_faces)}/2048"
            
            # Seed the chaining below from an order that depends only on the triangles' data, not
            # on Blender's face/vertex order: that order changes on every re-import, so the vertex
            # packing (and the exported size) would otherwise wander from one export to the next.
            # Each face keeps its own vertex order (winding).
            faces.sort(key=lambda face: [(*vert.to_array(), getattr(vert, '_hooked', False)) for vert in face])

            # reorder faces to maximize shared edges: each next face is the first remaining one that
            # shares two or more verts with the last, else the first remaining one. Verts compare by
            # value (VisualsVertChunk.__eq__), so index the faces by vert key instead of scanning them all.
            face_keys = [[vert_key(vert) for vert in face] for face in faces]
            faces_with_key = {}
            for f, keys in enumerate(face_keys):
                for key in keys:
                    faces_with_key.setdefault(key, []).append(f)
            remaining = [True] * len(faces)
            first_remaining = 0
            order = []
            current = 0
            while True:
                remaining[current] = False
                order.append(current)
                while first_remaining < len(faces) and not remaining[first_remaining]:
                    first_remaining += 1
                if first_remaining == len(faces):
                    break
                last_keys = set(face_keys[current])
                candidates = sorted({f for key in last_keys for f in faces_with_key[key] if remaining[f]})
                current = next((f for f in candidates if sum(key in last_keys for key in face_keys[f]) > 1),
                               first_remaining)
            ordered_faces = [faces[f] for f in order]

            # Pack the faces into vertex loads. Each gSPVertex loads n consecutive buffer vertices
            # into vertex cache slots [v0, v0 + n), and the F3DEX2 cache has VERTEX_CACHE_SIZE
            # slots (SW_RACER_RE dinput_hook/renderer_hook.cpp only accepts more to read older
            # add-on exports). Triangles index cache slots, so every face must lie in one load.
            # loads: (buffer index of the vertex in slot v0, n, faces as slot indices)
            if self.group_parent_id and any(getattr(v, '_hooked', False) for face in ordered_faces for v in face):
                # The runtime draws the buffer's prefix [0, group_count) with group_parent_id's
                # matrix, and slots below v0 = group_count take the v0 vertices just before the
                # load, so a hooked mesh has exactly one load: hooked verts first, then the rest.
                new_verts = []
                index_of = {}
                for face in ordered_faces:
                    for vert in face:
                        key = vert_key(vert)
                        if key not in index_of:
                            index_of[key] = len(new_verts)
                            new_verts.append(vert)
                new_verts = ([v for v in new_verts if getattr(v, '_hooked', False)] +
                             [v for v in new_verts if not getattr(v, '_hooked', False)])
                self.group_count = sum(getattr(v, '_hooked', False) for v in new_verts)
                if len(new_verts) > VERTEX_CACHE_SIZE:
                    raise ValueError(f"{node.name}: a hooked mesh must fit in one vertex load "
                                     f"(it uses {len(new_verts)} vertices, the limit is {VERTEX_CACHE_SIZE})")
                index_of = {vert_key(v): i for i, v in enumerate(new_verts)}
                loads = [(self.group_count, len(new_verts) - self.group_count,
                          [[index_of[vert_key(v)] for v in face] for face in ordered_faces])]
            else:
                self.group_count = 0
                # no hooked vertices left (e.g. the HOOK's group is empty): nothing to anchor
                self.group_parent_id = 0
                self.hook_target = None
                new_verts, loads = pack_vertex_loads(ordered_faces, VERTEX_CACHE_SIZE)

            self.visuals_vert_buffer.data = new_verts

            self.visuals_index_buffer = VisualsIndexBuffer(self, self.model).unmake(loads)
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

            # replace each index with an id shared by equal verts (ShortPosition compares by value),
            # so the strip search below compares ints
            vert_ids = {}
            id_verts = []
            for vert in verts:
                key = tuple(vert.data)
                if key not in vert_ids:
                    vert_ids[key] = len(id_verts)
                    id_verts.append(vert)
            faces = [[vert_ids[tuple(verts[i].data)] for i in face] for face in faces]
            # the strip search only ever continues onto a face sharing a vert with the last one
            faces_with_vert = {}
            for f, face in enumerate(faces):
                for v in face:
                    faces_with_vert.setdefault(v, []).append(f)
            remaining = [True] * len(faces)
            first_remaining = 0

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

            def take_face(f):
                nonlocal first_remaining
                remaining[f] = False
                while first_remaining < len(faces) and not remaining[first_remaining]:
                    first_remaining += 1
                return faces[f]

            # restrip mesh
            strips = []
            new_verts = []
            strip = []
            strip.append(take_face(0))
            strip_verts = []
            while first_remaining < len(faces):
                last_face = strip[-1]
                shared = None

                # search for a suitable adjacent face to continue strip, in face order
                candidates = sorted({f for v in last_face for f in faces_with_vert[v] if remaining[f]})
                for f in candidates:
                    face = faces[f]
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
                    strip.append(take_face(shared))
                else:
                    if len(strip_verts) == 0:
                        strip_verts.extend(last_face)
                    strips.append(strip[:])
                    new_verts.extend(strip_verts[:])
                    strip_verts = []
                    strip = []
                    strip.append(take_face(first_remaining))

            if len(strip):
                new_verts.extend(strip_verts[:])
                strips.append(strip)
                new_verts.extend([s for s in strip[0]])
            new_verts = [id_verts[v] for v in new_verts]
            
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
        
        group_parent_addr = 0
        if self.hook_target is not None and self.group_count:
            # referenced_node: patched in Model.write once every node has an address
            self.model.highlight(mesh_start + 40)
            self.model.hooked_meshes.append((mesh_start, self))

        #finally, write mesh header
        struct.pack_into(self.format_string, buffer, mesh_start, mat_addr, collision_tags_addr, *self.bounding_box.to_array(), strip_count, strip_size, vert_strips_addr, group_parent_addr, collision_vert_buffer_addr, visuals_index_buffer_addr, visuals_vert_buffer_addr, collision_vert_count, visuals_vert_count, self.group_count)
        return cursor
            
def create_node(node_type, parent, model):
    NODE_MAPPING = {
        12388: MeshGroup,
        20580: Group20580,
        20581: Group20581,
        20582: Group20582,
        53348: NodeTransformed,
        53349: NodeTransformedWithPivot,
        53350: Group53350
    }

    node_class = NODE_MAPPING.get(node_type)
    assert node_class, f"Invalid node type {node_type}"    
    return node_class(parent, model, node_type)
    
# MARK: NODE
    
class Node(DataStruct):
    
    def __init__(self, parent, model, type, header = []):
        super().__init__('>3I2H3I')
        self.parent = parent
        self.type = type
        self.id = None
        self.head = []
        self.children = []
        self.AltN = []
        self.header = []
        if len(header):
            self.header.extend(header)
        # header slots this node held in the imported file; Model.resolve_header_slots
        # writes them back unless an export template already fills the slot
        self.imported_header = []
        self.node_type = type
        self.vis_flags = 0xFF
        self.col_flags = 0xFF
        self.flags_set = False
        self.transform_flags = 0x3
        self.light_index = 0
        self.mirror_flags = 0
        self.model = model
        self.child_count = 0
        self.child_start = None
        self.original_object = None
        self.write_location = None
        # child slots import kept on the object (see Node.make): null slot indices, and
        # {slot index: id of a node made under another parent}
        self.null_slots = []
        self.shared_slots = {}
        
    def read(self, buffer, cursor):
        self.id = cursor
        self.node_type, self.vis_flags, self.col_flags, self.transform_flags, self.light_index, self.mirror_flags, self.child_count, self.child_start = struct.unpack_from(self.format_string, buffer, cursor)
        
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
                slot_addr = self.child_start + i * 4
                alt_node = self.model.read_alt_node(slot_addr, self)
                if alt_node is not None:
                    self.children.append(alt_node)
                elif slot_addr in self.model.AltN:
                    self.children.append({'id': slot_addr, 'AltN': True})
                else:
                    self.children.append({'id': None})  # remove later
                continue

            # if child_address < self.id:
            #     print('reference to previous node', child_address, 'on child', i, 'for node', self.id)

            if self.model.ref_map.get(child_address):
                # a node already read under another parent: the file's node graph is a DAG
                # (e.g. Part 251's seven pivots share one child), keep the extra link for export
                self.children.append({'id': child_address, 'shared': self.model.obj_key(child_address)})
                continue

            if isinstance(self, MeshGroup):
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
            if self.transform_flags & 0x10 != 0:
                b_node.empty_display_type = 'ARROWS'
                b_node.empty_display_size = 0.5
                
            elif self.transform_flags & 524288 != 0:
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
        b_node.id  = self.model.obj_key(self.id)
        if self.model.type == '1':
            # node comes from the high detail MAlt overlay of a Podd
            b_node['MAlt'] = True
        if self.AltN:
            b_node['AltN'] = self.AltN
        b_node['node_type'] = self.node_type
        b_node['vis_flags'] = str(self.vis_flags)
        b_node['col_flags'] = str(self.col_flags)
        b_node['transform_flags'] = self.transform_flags
        b_node['light_index'] = self.light_index
        b_node['mirror_flags'] = self.mirror_flags
        b_node['was_transformed'] = self.transform_flags & 3
        b_node['has_transform'] = self.transform_flags & 0x10
        
        if hasattr(self, 'bonus') and self.bonus is not None:
            b_node['bonus'] = self.bonus.to_array()
            
        #assign parent
        if parent is not None:
            b_node.parent = parent
            b_node.matrix_parent_inverse.identity()

        # before the children: their meshes look up which nodes above them hold a slot
        # (effective_node_flags)
        if self.id in self.model.header.offsets:
            b_node['header'] = [i for i, e in enumerate(self.model.header.offsets) if e == self.id]

        for node in self.children:
            if not isinstance(node, dict):
                node.make(b_node, collection)

        if self.node_type != 12388:
            # Child slots that are not objects of their own: null pointers, which selectors and LOD
            # selectors count when they pick a child by index (SW_RACER_RE dinput_hook/renderer_hook.cpp
            # debug_render_node), and links to a node already made under another parent. Export
            # writes both back at the same index (Model.resolve_child_slots).
            null_slots = [i for i, c in enumerate(self.children) if isinstance(c, dict) and not c.get('shared')]
            shared = {str(i): c['shared'] for i, c in enumerate(self.children) if isinstance(c, dict) and c.get('shared')}
            if null_slots:
                b_node['null_slots'] = null_slots
            if shared:
                b_node['shared_children'] = shared
            # Podd child slots the game fills from the MAlt (Model.read_alt_node): the MAlt node is
            # a child object, but its file offset says nothing about its index among the Podd's
            # nodes, so keep the index for export (Model.begin_alt_export)
            alt_children = {str(i): c.model.obj_key(c.id) for i, c in enumerate(self.children)
                            if isinstance(c, Node) and c.model is not self.model}
            if alt_children:
                b_node['alt_children'] = alt_children

        for i in range(24):
            view_layer = bpy.context.scene.view_layers.get(f"VisLayer_{i}")
            set_hidden(self.model, b_node, not bool(self.vis_flags & (1 << (i + 8))), view_layer)
            
        return b_node
    def unmake(self, node, unmake_children = False):
        self.id = node.name
        self.original_object = node
            
        if node.type == 'EMPTY':
            self.node_type = 53349
            
        get_animations(node, self.model, self)
            
        if 'transform_flags' in node:
            self.transform_flags =  node['transform_flags']
        elif 'unk1' in node:
            # backward-compat: legacy import stored the >I packed unk1 (high half = transform_flags, low half = light_index)
            legacy_unk1 = int(node['unk1'])
            self.transform_flags = (legacy_unk1 >> 16) & 0xFFFF
            if 'light_index' not in node:
                self.light_index = legacy_unk1 & 0xFFFF
        if 'light_index' in node:
            self.light_index = node['light_index']
        if 'mirror_flags' in node:
            self.mirror_flags = node['mirror_flags']
        elif 'unk2' in node:
            self.mirror_flags = int(node['unk2'])
        if 'header' in node:
            self.imported_header = [int(slot) for slot in node['header']]
        if 'null_slots' in node:
            self.null_slots = [int(slot) for slot in node['null_slots']]
        if 'shared_children' in node:
            self.shared_slots = {int(slot): str(key) for slot, key in node['shared_children'].items()}
        if 'alt_children' in node and getattr(self.model, 'alt_model', None) is not None:
            # MAlt nodes go back at their index like shared children do (Model.begin_alt_export)
            self.shared_slots.update({int(slot): str(key) for slot, key in node['alt_children'].items()})
        
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
            struct.pack_into(">I", buffer, 4 + 4*i, cursor)
             
        struct.pack_into(self.format_string, buffer, cursor, self.node_type, self.vis_flags, self.col_flags, self.transform_flags, self.light_index, self.mirror_flags, 0, 0)
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
            if isinstance(child, Node) and child.model is not self.model:
                # a high detail node of the Podd's MAlt: the game plugs it into this null pointer
                self.model.write_altn_slot(buffer, self, index, child_ptr)
                continue
            #check if child is already written
            if child.write_location:
                writeUInt32BE(buffer, child.write_location, child_ptr)
            else:
                writeUInt32BE(buffer, cursor, child_ptr)
                cursor = child.write(buffer, cursor)
            
        return cursor
    
    def set_flags(self, vis_flags = None, col_flags = None, transform_flags = None):
        
        if transform_flags is not None:
            self.transform_flags = transform_flags
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
                if child is None:
                    continue
                child.set_flags()
                if self.node_type == [12388]:
                    self.col_flags &= (child.col_flags & 0x000000FF)
                    self.vis_flags &= (child.vis_flags & 0x000000FF)
        return self

class MeshGroup(Node):
    
    def __init__(self, parent, model, type, header = []):
        super().__init__( parent,model, type, header)
        self.parent = parent
        self.bounding_box = None
        # stock mesh groups have flags_3 0 (32 on a few), never the 0x3 Node starts with
        self.transform_flags = 0
        
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
        
class NodeTransformed(Node):
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
        empty.matrix_parent_inverse.identity()
        # make() gives the file's row-vector layout (translation in the last row); Blender is column-vector
        empty.matrix_basis = mathutils.Matrix(self.matrix.make(self.model.scale)).transposed()
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

class NodeTransformedWithPivot(Node):
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
        empty.matrix_parent_inverse.identity()
        # make() gives the file's row-vector layout (translation in the last row); Blender is column-vector
        empty.matrix_basis = mathutils.Matrix(self.matrix.make(self.model.scale)).transposed()
        empty['bonus'] = self.bonus.to_array()
        # the matrix as stored; an animated node's frame 0 pose replaces it in Blender, and the
        # stock rest pose often differs a little from the first key (see Model.record_rest_poses)
        empty['file_matrix'] = self.matrix.to_array()

        # Pivot semantic: with flags_3 & 0x10 the game rotates about the pivot, composing the
        # local transform as T(pivot) · M · T(-pivot), i.e. t += pivot - R·pivot (SW_RACER_RE
        # src/Swr/swrModel.c:1486-1491, dinput_hook/node_utils.cpp:211-221; flag documented in
        # src/types.h:1433). Without the flag the pivot is ignored.
        # The node object keeps basis M, so its location/rotation (and their keyframes) stay the
        # file's translation/rotation; two translation-only helper empties supply the rest:
        # T(+pivot) between the node and its parent, T(-pivot) between the node and its children.
        pivot = self.bonus.to_array()[:3]
        if self.transform_flags & 0x10 and any(abs(p) > 1e-7 for p in pivot):
            scale = self.model.scale
            file_children = [c for c in empty.children]
            # link next to the node, not into `collection`: Node.make may have moved the node into
            # a Track/Skybox sub-collection, and export walks each sub-collection's own objects
            node_collections = list(empty.users_collection)

            def make_helper(name, location, parent):
                helper = bpy.data.objects.new(name, None)
                helper.empty_display_type = 'PLAIN_AXES'
                helper.empty_display_size = 0.25
                for node_collection in node_collections:
                    node_collection.objects.link(helper)
                helper.parent = parent
                helper.matrix_parent_inverse.identity()
                helper.location = [p * scale for p in location]
                helper['pivot_helper'] = True
                return helper

            origin = make_helper(empty.name + "_pivot_origin", pivot, empty.parent)
            empty.parent = origin
            empty.matrix_parent_inverse.identity()
            helper = make_helper(empty.name + "_pivot", [-p for p in pivot], empty)
            for child in file_children:
                child.parent = helper
                child.matrix_parent_inverse.identity()

        return empty
    def unmake(self, node, make_children = False):
        super().unmake(node, False)
        if node.parent is not None and node.parent.get('pivot_helper'):
            # below the T(+pivot) helper import adds, the node's own channels are M; matrix_local
            # would be rebuilt from world matrices and pick up float noise
            matrix = node.matrix_parent_inverse @ node.matrix_basis
        else:
            matrix = node.matrix_local
        #need to transpose the matrix
        matrix = list(map(list, zip(*matrix)))
        self.matrix.unmake(matrix, self.model.scale)
        rest_pose = node.get('frame0_basis')
        if rest_pose is not None and 'file_matrix' in node and                 all(abs(a - b) < 1e-5 for a, b in zip(rest_pose, basis_values(node.matrix_basis))):
            # untouched animated node: write the stored rest matrix, not its frame 0 pose
            self.matrix.from_array([float(v) for v in node['file_matrix']])
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
    # follows (mirrors position) and tracks (rotates to) camera
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
        super().unmake(node)
        self.node_type = 20580  # Node.unmake defaults empties to 53349
        return self
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_data_start = cursor - 8
        cursor = super().write_children(buffer, cursor, child_data_start)
        return cursor
      
class Group20581(Node):
    #NodeSelector https://github.com/tim-tim707/SW_RACER_RE/blob/fa8787540055d0bdf422b42e72ccf50cd3d72a07/src/types.h#L1273
    def __init__(self, parent, model, type, header = []):
        super().__init__(parent, model, type, header)
        self.selected_child = 0 # -2 = none, -1 = all, >= 0 = only that child
    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.selected_child = struct.unpack_from(">i", buffer, cursor + 28)[0]
        return self
    def make(self, parent = None, collection = None):
        empty = super().make(parent, collection)
        empty['selected_child'] = self.selected_child
        return empty
    def unmake(self, node):
        super().unmake(node)
        self.node_type = 20581
        self.selected_child = node.get('selected_child', 0)
        return self
    def write(self, buffer, cursor):
        cursor = super().write(buffer, cursor)
        child_data_start = cursor - 8
        struct.pack_into(">i", buffer, cursor, self.selected_child)
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
        return empty
    def unmake(self, node):
        super().unmake(node)
        self.node_type = 20582
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
            if isinstance(d, LStr):
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
        target.keyframe_insert(data_path="location", frame = time * self.model.fps)
    
    def unmake(self, pose):
        self.data.from_array([x/self.model.scale for x in pose])
        return self
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, *self.data.to_array())
        return cursor + self.size
    
    def to_array(self):
        return self.data.to_array()
    
class ScalePose(LocationPose):
    """Type 0xA keys: a node's scale, 3 floats (SW_RACER_RE src/Swr/swrModel.c swrModel_UpdateScaleAnimation)."""
    def make(self, target, time):
        target.scale = self.data.to_array()
        target.keyframe_insert(data_path="scale", frame = time * self.model.fps)

    def unmake(self, pose):
        self.data.from_array(list(pose))
        return self

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
        if mathutils.Vector(axis).length < 1e-6:
            # files written before the zero-axis fix in unmake hold identity as a zero axis
            R = mathutils.Quaternion()
        else:
            R = mathutils.Matrix.Rotation(angle, 4, axis).to_quaternion()
        self.R = R
        
        if self.previous is not None and self.previous.R is not None:
            R.make_compatible(self.previous)
            
        target.rotation_quaternion = R
        target.keyframe_insert(data_path="rotation_quaternion", frame = time * self.model.fps)
    
    def unmake(self, pose):
        q = mathutils.Quaternion(pose)
        axis, angle = q.to_axis_angle()
        if axis.length < 1e-6:
            # Identity (q = +-1) comes back as a zero axis, with 360 degrees for q = -1. The game
            # builds the matrix with rdMatrix_BuildFromVectorAngle44, which divides by 1 - (1 - x^2 - y^2)
            # and turns a zero axis into NaN, so the node and everything under it stops drawing
            # (SW_RACER_RE src/Primitives/rdMatrix.c). Stock writes identity as (1, 0, 0), 0.
            axis, angle = mathutils.Vector((1.0, 0.0, 0.0)), 0.0
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
            bag = anim_utils.action_get_channelbag_for_slot(target.node_tree.animation_data.action, target.node_tree.animation_data.action_slot)
            for fcurves_f in bag.fcurves:
                ensure_cycles_first(fcurves_f)
                for k in fcurves_f.keyframe_points:
                    k.interpolation = 'LINEAR'
    
    def unmake(self, pose):
        self.data = [pose]
        return self

    
class TexturePose(DataStruct):
    """A texture flipbook (type 0x2) key: a pointer to a whole swrModel_MaterialTexture (tile included).

    The game switches the target mesh material's texture to the frame's struct; that update is
    undecompiled (SW_RACER_RE src/Swr/swrModel.c swrModel_UpdateTextureFlipbookAnimation is a
    stub), but the stock data is unambiguous: the vehicle select flag (Part 48) keys one frame per
    racer, the spark (Part 49) its 11 frames.
    """
    def __init__(self, parent, model):
        super().__init__('>I')

        self.parent = parent
        self.model = model
        self.texture = None

    def read(self, buffer, cursor):
        pointer = readUInt32BE(buffer, cursor)
        if pointer:
            self.texture = MaterialTexture(self, self.model).read(buffer, pointer)
        return self
    
    def make(self, target):
        pass
    
    def unmake(self, obj):
        pass
        return self
    
    def write(self, buffer, cursor):
        pass
    
    
# How far (Blender units for location/scale, radians for rotation) the game's interpolation of the
# exported keys may stray from Blender's evaluated curve before another key is baked in, and how
# finely (in frames) curves are checked for that.
ANIM_BAKE_TOLERANCE = {'location': 1e-3, 'scale': 1e-3, 'rotation': math.radians(0.1)}
ANIM_BAKE_STEP = 0.5
# A rotation error of a radians moves a point r Blender units from the pivot by about a * r, so a
# large rotating part (a whole track section, hundreds of units across) needs a much finer angle
# than ANIM_BAKE_TOLERANCE['rotation'] for its far vertices to stay within this distance.
ANIM_BAKE_ROTATION_DISTANCE = 1e-3
# below this the single-precision quaternions the game stores can't follow (about 6e-8 per
# component, i.e. 2.4e-7 rad), and keys would be added for rounding noise
ANIM_BAKE_MIN_ROTATION = 1e-6

ROTATION_PATHS = ('rotation_quaternion', 'rotation_euler', 'rotation_axis_angle')


def _anim_rotation_path(obj, channels):
    """The rotation fcurves Blender actually plays: the ones matching the object's rotation mode."""
    preferred = {'QUATERNION': 'rotation_quaternion', 'AXIS_ANGLE': 'rotation_axis_angle'}.get(obj.rotation_mode, 'rotation_euler')
    if preferred in channels:
        return preferred
    return next((p for p in ROTATION_PATHS if p in channels), None)


def _anim_is_linear(fcurves):
    """Whether Blender interpolates these curves linearly between their keys (no easing or modifiers
    other than Cycles), which is what the game does for translation and scale."""
    for fcurve in fcurves:
        if any(mod.type != 'CYCLES' for mod in fcurve.modifiers):
            return False
        points = fcurve.keyframe_points
        # the last key's interpolation only applies past it, where both hold the last value
        if any(points[i].interpolation != 'LINEAR' for i in range(len(points) - 1)):
            return False
    return True


def _anim_game_slerp(q0, q1, factor):
    """The game's rotation between two keys: slerp along the shorter arc (SW_RACER_RE
    src/Primitives/rdMath.c:123-161 rdMath_SlerpQuaternions flips q0 when the dot product is negative)."""
    if q0.dot(q1) < 0:
        q0 = -q0
    return q0.slerp(q1, factor)


def _anim_deviation(kind, value, interpolated):
    if kind == 'rotation':
        # angle between the rotations, from the chord between the unit quaternions in doubles
        # (acos of mathutils' single precision dot product can't resolve small angles)
        a, b = list(value.normalized()), list(interpolated.normalized())
        chord = min(math.dist(a, b), math.dist(a, [-x for x in b]))
        return 4 * math.asin(min(1.0, chord / 2))
    return (value - interpolated).length


def _anim_subtree_extent(obj):
    """How far (Blender units, world space) the farthest geometry obj's transform moves is from its origin."""
    origin = obj.matrix_world.translation
    extent = 0.0
    for o in (obj, *obj.children_recursive):
        if o.type != 'MESH':
            continue
        matrix = o.matrix_world
        for corner in o.bound_box:
            extent = max(extent, (matrix @ mathutils.Vector(corner) - origin).length)
    return extent


def _anim_rotation_tolerance(obj):
    """The angle the bake may stray by: ANIM_BAKE_TOLERANCE['rotation'], or finer when that would
    move obj's farthest geometry by more than ANIM_BAKE_ROTATION_DISTANCE."""
    tolerance = ANIM_BAKE_TOLERANCE['rotation']
    extent = _anim_subtree_extent(obj)
    if extent > 0:
        tolerance = min(tolerance, ANIM_BAKE_ROTATION_DISTANCE / extent)
    return max(tolerance, ANIM_BAKE_MIN_ROTATION)


def _anim_bake(kind, knots, evaluate, tolerance=None):
    """Keys that the game's interpolation (linear, or slerp for rotation; SW_RACER_RE
    src/Swr/swrModel.c:648-726) turns into Blender's evaluated curve within tolerance (by default
    ANIM_BAKE_TOLERANCE[kind]).

    knots are the curve's own key frames and are always kept; between them the curve is sampled
    every ANIM_BAKE_STEP frames and the worst-fitting sample is added until every sample fits.
    A finer tolerance samples more finely: the error between two keys grows with the square of
    their spacing, so the step shrinks with the square root of the tolerance, which keeps the
    motion between samples (which is never checked) as small next to the tolerance as it is at
    the default.
    """
    if tolerance is None:
        tolerance = ANIM_BAKE_TOLERANCE[kind]
    step = ANIM_BAKE_STEP * max(1 / 64, min(1.0, math.sqrt(tolerance / ANIM_BAKE_TOLERANCE[kind])))
    times = []
    for t0, t1 in zip(knots, knots[1:]):
        steps = max(1, math.ceil((t1 - t0) / step - 1e-6))
        times += [t0 + (t1 - t0) * i / steps for i in range(steps)]
    times.append(knots[-1])
    values = [evaluate(t) for t in times]
    if kind == 'rotation':
        values = [mathutils.Quaternion(v).normalized() for v in values]
    else:
        values = [mathutils.Vector(v) for v in values]
    knot_set = set(knots)
    keep = {i for i, t in enumerate(times) if t in knot_set}
    stack = sorted(keep)
    segments = list(zip(stack, stack[1:]))
    while segments:
        a, b = segments.pop()
        worst, worst_error = None, tolerance
        for i in range(a + 1, b):
            factor = (times[i] - times[a]) / (times[b] - times[a])
            if kind == 'rotation':
                interpolated = _anim_game_slerp(values[a], values[b], factor)
            else:
                interpolated = values[a].lerp(values[b], factor)
            error = _anim_deviation(kind, values[i], interpolated)
            if error > worst_error:
                worst, worst_error = i, error
        if worst is not None:
            keep.add(worst)
            segments += [(a, worst), (worst, b)]
    indices = sorted(keep)
    return [times[i] for i in indices], [values[i] for i in indices]


def texture_fields(texture):
    """A material texture struct as plain data (see material_texture_from_fields)."""
    if texture is None:
        return {}
    return {
        'id': texture.id, 'format': texture.format, 'size': [texture.width, texture.height],
        'unk0': texture.stock_unk0 if texture.stock_unk0 is not None else 0,
        'sizes': list(texture.stock_sizes or []), 'unk9': texture.unk9,
        'tile': texture.chunks[0].to_array() if texture.chunks else [],
    }

def material_texture_from_fields(parent, model, fields):
    texture = MaterialTexture(parent, model)
    texture.id = int(fields['id'])
    texture.format = int(fields['format'])
    texture.width, texture.height = (int(v) for v in fields['size'])
    texture.unk9 = int(fields['unk9'])
    texture.stock_unk0 = int(fields['unk0'])
    if len(fields['sizes']) == 4:
        texture.stock_sizes = [int(v) for v in fields['sizes']]
    if len(fields['tile']) == 6:
        chunk = MaterialTextureChunk(texture, model)
        chunk.unk0, chunk.unk1, chunk.unk2, chunk.unk3, chunk.unk4, chunk.unk5 = (int(v) for v in fields['tile'])
        texture.chunks = [chunk]
    return texture

class RawPose(DataStruct):
    """A key's values as read, for an animation written back unchanged (raw_anim)."""
    def __init__(self, values):
        super().__init__(f'>{len(values)}f')
        self.data = list(values)

def raw_anim(parent, raw, model):
    """The animation Anim.raw_fields kept, targeting parent (a node, a material or None)."""
    anim = Anim(parent, model)
    anim.target = parent
    (anim.float1, anim.float2, anim.float3, anim.float4, anim.float5,
     anim.float6, anim.float7, anim.float8) = (float(v) for v in raw['floats'])
    anim.flag1, anim.flag2 = (int(v) for v in raw['flags'])
    anim.unk32 = int(raw['unk11'])
    anim.index = int(raw['index']) if int(raw['index']) >= 0 else None
    anim.keyframe_times = [float(t) for t in raw['times']]
    values = [float(v) for v in raw['values']]
    width = len(values) // len(anim.keyframe_times) if anim.keyframe_times else 0
    anim.keyframe_poses = [RawPose(values[i * width:(i + 1) * width]) for i in range(len(anim.keyframe_times))]
    return anim

def raw_anims(parent, holder, model):
    return [raw_anim(parent, raw.to_dict() if hasattr(raw, 'to_dict') else raw, model)
            for raw in holder.get('raw_animations', [])]

def flipbook_anim(material, flipbook, model):
    """The type 0x2 animation a material's imported flipbook writes back as (see TexturePose)."""
    anim = Anim(material, model)
    anim.target = material
    (anim.float1, anim.float2, anim.float3, anim.float4, anim.float5,
     anim.float6, anim.float7, anim.float8) = (float(v) for v in flipbook['floats'])
    anim.flag1, anim.flag2 = (int(v) for v in flipbook['flags'])
    anim.unk32 = int(flipbook['unk11'])
    anim.target_word = int(flipbook.get('target_word', 0))
    anim.index = int(flipbook.get('index', -1)) if int(flipbook.get('index', -1)) >= 0 else None
    anim.keyframe_times = [float(t) for t in flipbook['times']]
    anim.keyframe_poses = []
    for fields in flipbook['frames']:
        pose = TexturePose(anim, model)
        pose.texture = material_texture_from_fields(pose, model, fields) if fields else None
        anim.keyframe_poses.append(pose)
    return anim

def get_animations(obj, model, entity):
    """Turns the object's location, rotation and scale fcurves into the game's key frame animations.

    The game interpolates translation and scale linearly and rotation by slerp between axis-angle
    keys (SW_RACER_RE src/Swr/swrModel.c:648-726). Linear location/scale/quaternion curves, which is
    what import makes, are written key for key; anything else (eased or stepped interpolation,
    modifiers, Euler or axis-angle rotation) is baked into as many keys as the game needs to follow
    Blender's motion. The object's rotation mode is left as the user set it.
    """
    # stock animations import couldn't put on the object (Anim.make), written back unchanged
    model.animations.extend(raw_anims(entity, obj, model))
    if not obj.animation_data:
        return None

    if not obj.animation_data.action:
        return None

    bag = anim_utils.action_get_channelbag_for_slot(obj.animation_data.action, obj.animation_data.action_slot)
    if not bag:
        return None

    # fcurves by data path and array index, in action order
    channels = {}
    for fcurve in bag.fcurves:
        if fcurve.data_path in ('location', 'scale', *ROTATION_PATHS) and len(fcurve.keyframe_points):
            channels.setdefault(fcurve.data_path, {})[fcurve.array_index] = fcurve

    rotation_path = _anim_rotation_path(obj, channels)
    for path in channels:
        if path in ROTATION_PATHS and path != rotation_path:
            continue  # not the rotation Blender plays for this object's rotation mode
        fcurves = channels[path]
        loop = any(mod.type == 'CYCLES' for fcurve in fcurves.values() for mod in fcurve.modifiers)

        # every distinct key frame of the path's channels, in time order
        times = []
        for fcurve in fcurves.values():
            for keyframe in fcurve.keyframe_points:
                frame = keyframe.co[0]
                if frame not in times:
                    times.append(frame)
        times.sort()

        # unkeyed channels hold the object's own value
        static = list(getattr(obj, path))
        def evaluate(frame, fcurves=fcurves, static=static):
            return [fcurves[i].evaluate(frame) if i in fcurves else static[i] for i in range(len(static))]

        if path == 'rotation_euler':
            order = obj.rotation_mode if obj.rotation_mode not in ('QUATERNION', 'AXIS_ANGLE') else 'XYZ'
            channel_values = evaluate
            evaluate = lambda frame: mathutils.Euler(channel_values(frame), order).to_quaternion()
        elif path == 'rotation_axis_angle':
            channel_values = evaluate
            def evaluate(frame):
                angle, *axis = channel_values(frame)
                if mathutils.Vector(axis).length < 1e-12:
                    return mathutils.Quaternion()
                return mathutils.Quaternion(axis, angle)

        kind = 'rotation' if path in ROTATION_PATHS else path
        if path in ('location', 'scale', 'rotation_quaternion') and _anim_is_linear(fcurves.values()):
            # the game interpolates these the way Blender does: keep the keys as they are
            poses = [evaluate(frame) for frame in times]
        else:
            tolerance = _anim_rotation_tolerance(obj) if kind == 'rotation' else None
            times, poses = _anim_bake(kind, times, evaluate, tolerance)
            if kind == 'rotation':
                # keep each key in the previous one's hemisphere, so the arc the game slerps (always
                # the shorter one) is also the one a re-import's quaternion lerp follows
                for i in range(1, len(poses)):
                    if poses[i].dot(poses[i - 1]) < 0:
                        poses[i] = -poses[i]
            poses = [list(p) for p in poses]

        # With one key the game reads past the key arrays: swrModel_AnimationFindKeyFrameIndex
        # returns num_key_frames - 2 = -1 and the interpolators read key_frame_times[index + 1]
        # (SW_RACER_RE src/Swr/swrModel.c:992-1009, 648-650). A second, identical key at the same
        # time gives it a valid segment without changing the motion.
        if len(times) == 1:
            times, poses = times * 2, poses * 2

        stored = 'rotation_quaternion' if kind == 'rotation' else path
        durations = obj.get(f'anim_durations_{stored}')
        anim = Anim(entity, model).unmake(times, poses, stored, loop = loop,
                                          flags = obj.get(f'anim_flags_{stored}'),
                                          durations = list(durations) if durations is not None else None)
        index = obj.get(f'anim_index_{stored}')
        if anim is not None and index is not None and index >= 0:
            anim.index = int(index)
        model.animations.append(anim)

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
        # position in the model's animation list, kept on export (Model.sort_animations)
        self.index = None
        
    def to_array(self):
        return [self.float1,self.float2,self.float3,self.flag1,self.flag2,self.num_keyframes,self.float4,self.float5,self.float6,self.float7,self.float8,self.keyframes,self.keyframe_times,self.keyframe_poses,self.target,self.unk32]
    
    def read(self, buffer, cursor):
        self.float1, self.float2, self.float3, self.flag1, self.flag2, self.num_keyframes, self.float4, self.float5, self.float6, self.float7, self.float8, keyframe_times_addr, keyframe_poses_addr, self.target, self.unk2 = struct.unpack_from(self.format_string, buffer, cursor)

        if self.flag2 & 0xF == 0x2 and self.target:
            # a flipbook targets an 8-byte block (mesh material pointer, then a word that is 0 in
            # stock files) that the file stores between the key times and the frame pointers
            self.target_word = readUInt32BE(buffer, self.target + 4)
            self.target = readUInt32BE(buffer, self.target)

        if not keyframe_poses_addr or not keyframe_times_addr:
                return self

        cursor = keyframe_poses_addr
        #get keyframes
        for f in range(self.num_keyframes):
            self.keyframe_times.append(readFloatBE(buffer, keyframe_times_addr + f * 4))
            pose = None
            # the type is the low 4 bits of the flags (SW_RACER_RE src/types.h swrModel_Animation,
            # value sizes in src/Swr/swrModel.c swrModel_ByteSwapAnimation); masking 3 bits read
            # scale (0xA) as a texture animation
            anim_type = self.flag2 & 0xF
            if anim_type == 0x8:  # axis-angle rotation (4)
                pose = RotationPose(self, self.model).read(buffer, cursor)
            elif anim_type == 0x9:  # translation (3)
                pose = LocationPose(self, self.model).read(buffer, cursor)
            elif anim_type == 0xA:  # scale (3)
                pose = ScalePose(self, self.model).read(buffer, cursor)
            elif anim_type == 0x2:  # texture
                pose = TexturePose(self, self.model).read(buffer, cursor)
            elif anim_type in (0xB, 0xC):  # uv_x/uv_y (1)
                pose = UVPose(self, self.model).read(buffer, cursor)
            
            if pose is not None:
                self.keyframe_poses.append(pose)
                cursor += pose.size
            else:
                print('unk anim', self.flag2)

        return self
                    
    def raw_fields(self):
        """This animation as plain data, written back unchanged by raw_anim."""
        values = []
        for pose in self.keyframe_poses:
            data = pose.data.to_array() if hasattr(pose.data, 'to_array') else pose.data
            values.extend(float(v) for v in (data if isinstance(data, (list, tuple)) else [data]))
        return {
            'index': self.index if self.index is not None else -1,
            'floats': [self.float1, self.float2, self.float3, self.float4, self.float5,
                       self.float6, self.float7, self.float8],
            'flags': [self.flag1, self.flag2], 'unk11': self.unk2,
            'times': list(self.keyframe_times), 'values': values,
        }

    def keep_raw(self, holder):
        """Keep this animation as data on holder (an object, material or the model's collection)."""
        kept = [dict(raw) for raw in holder.get('raw_animations', [])]
        kept.append(self.raw_fields())
        holder['raw_animations'] = kept

    def make(self):
        #assume we have an object or material to apply animations to

        self.loop = self.flag2 & 0x10 > 0
        target = None
        # Some stock animations can't be shown on a Blender object or material, and are kept as
        # data for export instead (raw_anim): one with no target (a null pointer; cutscene models
        # and some Parts have them), a second animation of the same type on the same node or
        # material (cutscene models), and UV scrolls that aren't a plain looping 0..1 ramp.
        anim_type = self.flag2 & 0xF
        path = {0x8: 'rotation_quaternion', 0x9: 'location', 0xA: 'scale', 0xB: 'uv_x', 0xC: 'uv_y'}.get(anim_type)
        if path in ('uv_x', 'uv_y'):
            holder = get_mat_by_id(f"{self.model.id}_{self.target}")
            values = [pose.data[0] if isinstance(pose.data, (list, tuple)) else pose.data for pose in self.keyframe_poses]
            simple = self.flag2 in (27, 28) and len(self.keyframe_times) == 2 and self.keyframe_times[0] == 0 and \
                sorted(values) == [0.0, 1.0]
            if holder is None or not simple or f'anim_index_{path}' in holder:
                self.keep_raw(holder if holder is not None else self.model.collection)
                return
            holder[f'anim_index_{path}'] = self.index if self.index is not None else -1
        elif path is not None:
            holder = get_obj_by_id(self.model.obj_key(self.target), self.model.collection) if self.target else None
            if holder is None or f'anim_flags_{path}' in holder:
                self.keep_raw(holder if holder is not None else self.model.collection)
                return
            holder[f'anim_index_{path}'] = self.index if self.index is not None else -1

        if self.flag2 in [27, 28]: #uv
            target = get_mat_by_id(f"{self.model.id}_{self.target}")
            if target is None:
                return
            
            scroll = self.keyframe_times[1]
            poses = [pose.data for pose in self.keyframe_poses]
            if poses[0] < poses[1]:
                scroll = scroll * -1
            
            if self.flag2 == 27:
                set_material_prop(target, 'scroll_x', scroll)
            if self.flag2 == 28:
                set_material_prop(target, 'scroll_y', scroll)
            
            #remake material
            material = Material(None, None).unmake(target)
            material.make(remake = True)

        elif self.flag2 & 0xF == 0x2: # texture flipbook
            target = get_mat_by_id(f"{self.model.id}_{self.target}")
            if target is None:
                return
            # kept as data for export (Material.unmake); Blender shows the material's own texture
            target['flipbook'] = {
                'floats': [self.float1, self.float2, self.float3, self.float4, self.float5,
                           self.float6, self.float7, self.float8],
                'flags': [self.flag1, self.flag2],
                'unk11': self.unk2,
                'target_word': getattr(self, 'target_word', 0),
                'index': self.index if self.index is not None else -1,
                'times': list(self.keyframe_times),
                'frames': [texture_fields(pose.texture) for pose in self.keyframe_poses],
            }
            return

            
        # The low 4 bits are the animation type (8 rotation, 9 translation); the rest are
        # behaviour flags such as 0x10 loop, so match on the type rather than whole values.
        elif self.flag2 & 0xF == 8: #rotation
            target = get_obj_by_id(self.model.obj_key(self.target), self.model.collection)
            if target is None:
                return
            # keep the game's flags and loop lengths so export can write them back unchanged
            target['anim_flags_rotation_quaternion'] = self.flag2
            target['anim_durations_rotation_quaternion'] = [self.float4, self.float5]

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
                target.keyframe_insert(data_path="rotation_quaternion", frame = time * self.model.fps)
                previous_q = R
        
        elif self.flag2 & 0xF == 9: #location
            target = get_obj_by_id(self.model.obj_key(self.target), self.model.collection)
            if target is None:
                return
            target['anim_flags_location'] = self.flag2
            target['anim_durations_location'] = [self.float4, self.float5]

            for i, time in enumerate(self.keyframe_times):
                self.keyframe_poses[i].make(target, time)

        elif self.flag2 & 0xF == 0xA: #scale
            target = get_obj_by_id(self.model.obj_key(self.target), self.model.collection)
            if target is None:
                return
            target['anim_flags_scale'] = self.flag2
            target['anim_durations_scale'] = [self.float4, self.float5]

            for i, time in enumerate(self.keyframe_times):
                self.keyframe_poses[i].make(target, time)

        if target is None:
            return
        #make linear
        if not target.animation_data or not target.animation_data.action: 
            return
        bag = anim_utils.action_get_channelbag_for_slot(target.animation_data.action, target.animation_data.action_slot)
        if not bag:
            return
        for fcurve in bag.fcurves:
            if self.loop and self.model.type == '7':
                ensure_cycles_first(fcurve)
            for keyframe in fcurve.keyframe_points:
                keyframe.interpolation = 'LINEAR'
    
        
    
    
    def unmake(self, times, poses, path, loop = True, flags = None, durations = None):
        # flags: the game's original flag word, stored on import; its type bits are replaced below
        # durations: the game's original duration4/duration5, stored on import
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
        # The game loops on duration5 when flag 0x20 is set, else duration4 (SW_RACER_RE
        # src/Swr/swrModel.c swrModel_LoadAnimation). Stock animations often loop on a cycle
        # longer than their last key (one length shared by a puppet's limbs), so keep the
        # imported lengths unless the keys now run past them.
        if durations is not None and len(durations) == 2:
            # stock lengths measure from the first key, which isn't always at 0 (Scen 283's
            # keys start at 1.41 s with duration4 9.6)
            span = self.keyframe_times[-1] - self.keyframe_times[0]
            self.float4, self.float5 = (max(float(d), span) for d in durations)

        if path == 'location':
            self.flag2 |= 0b1001
            self.keyframe_poses = [LocationPose(self, self.model).unmake(pose) for pose in poses]
        elif path == 'rotation_quaternion':
            self.flag2 |= 0b1000
            self.keyframe_poses = [RotationPose(self, self.model).unmake(pose) for pose in poses]
        elif path == 'scale':
            self.flag2 |= 0xA
            self.keyframe_poses = [ScalePose(self, self.model).unmake(pose) for pose in poses]
        elif path in ['uv_x', 'uv_y']:
            self.flag2 |= 0b1011 if path == 'uv_x' else 0b1100
            self.keyframe_poses = [UVPose(self, self.model).unmake(pose) for pose in poses]
            
        if flags is not None:
            self.flag2 |= flags & ~0xF
        if loop:
            self.flag2 |= 0x10

        # end time, duration and duration3 hold the loop length the game picks on load (duration5
        # with flag 0x20, else duration4; SW_RACER_RE src/Swr/swrModel.c swrModel_LoadAnimation),
        # as in every stock file; the last key time made a puppet's limbs loop out of step wherever
        # the game runs animations without that reset (the racer select pilots)
        self.float1 = self.float2 = self.float3 = self.float5 if self.flag2 & 0x20 else self.float4

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
        
        target_addr = self.target.write_location if self.target is not None else 0
        if self.flag2 & 0xF == 0x2 and self.target is not None:
            # the target block (mesh material pointer, word), as stock files lay it out
            target_addr = cursor
            self.model.highlight(cursor)
            writeUInt32BE(buffer, self.target.write_location, cursor)
            writeUInt32BE(buffer, getattr(self, 'target_word', 0), cursor + 4)
            cursor += 8
        keyframe_poses_addr = cursor
        if self.flag2 & 0xF == 0x2:
            # a pointer per key, then the frames' texture structs (TexturePose)
            cursor += 4 * len(self.keyframe_poses)
            for i, pose in enumerate(self.keyframe_poses):
                slot = keyframe_poses_addr + 4 * i
                if pose.texture is None:
                    continue
                self.model.highlight(slot)
                writeUInt32BE(buffer, cursor, slot)
                cursor = pose.texture.write(buffer, cursor)
        else:
            for pose in self.keyframe_poses:
                cursor = pose.write(buffer, cursor)
        struct.pack_into(self.format_string, buffer, anim_addr,self.float1, self.float2, self.float3, self.flag1, self.flag2, len(self.keyframe_times), self.float4, self.float5, self.float6, self.float7, self.float8, keyframe_times_addr, keyframe_poses_addr, target_addr, self.unk32)
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
            read = Anim(self, self.model).read(buffer, anim)
            read.index = len(self.data)
            self.data.append(read)
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
        self.size = None
        # {slot: value} for slots holding a plain value rather than a pointer (see read)
        self.values = {}

    def read(self, buffer, cursor):
        type = readString(buffer, cursor)
        self.model.type = get_model_type(type)
        assert self.model.type, f"This model extension was not recognized: {type}"

        # A header entry is a node, an animation or a plain value (SW_RACER_RE src/types.h:1416
        # swrModel_HeaderEntry); the load only relocates the words the model's pointer mask marks
        # (src/Swr/swrModel.c:126-144). Scen 156 (the cutscene) holds unmasked values such as
        # 0x80000002 in slots 5, 19, 33, 47, 61 and 75; keep them to write back as they are.
        mask = None
        modelblock = getattr(self.model, 'modelblock', None)
        if modelblock is not None and self.model.id is not None and buffer is modelblock.fetch(self.model.id)[1]:
            mask = modelblock.fetch(self.model.id)[0]

        cursor = 4
        header = readInt32BE(buffer, cursor)

        while header != -1:
            if header and mask is not None and cursor // 32 < len(mask) and                     not mask[cursor // 32] & (1 << (7 - (cursor % 32) // 4)):
                self.values[len(self.offsets)] = header
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
        if self.values:
            self.model.collection['header_values'] = {str(slot): value for slot, value in self.values.items()}
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
        # Header slot count varies within a type (e.g. pod-part Parts have 5
        # slots, other Parts 2), and the game indexes into it, so preserve the
        # length read on import. Fall back to the per-type default otherwise.
        imported_header = collection.get('header')
        if imported_header is not None and len(imported_header):
            self.size = len(imported_header)
        self.values = {int(slot): int(value) for slot, value in collection.get('header_values', {}).items()}
        if self.model.type == "7":
            self.model.Data = ModelData(self, self.model).unmake()
        self.model.Anim = AnimList(self, self.model).unmake()
    
    def write(self, buffer, cursor):
        cursor = writeString(buffer,  model_types[int(self.model.type)][1], cursor)

        size = self.size if self.size is not None else header_sizes[int(self.model.type)]
        for slot in range(size):
            if slot in self.values:
                writeInt32BE(buffer, self.values[slot], cursor)
            else:
                self.model.highlight(cursor)
            cursor += 4

        cursor = writeInt32BE(buffer, -1, cursor)

        if self.model.type == "7" and self.model.Data:
            cursor = self.model.Data.write(buffer, cursor)

        if self.model.Anim:
            cursor = self.model.Anim.write(buffer, cursor)

        if self.model.altn_count:
            # null terminated list of pointers, filled in once the nodes are written
            # (Model.write_altn_slot for a Podd, Model.write for a MAlt)
            cursor = writeString(buffer, 'AltN', cursor)
            self.model.ref_map['AltN'] = cursor
            for i in range(self.model.altn_count + 1):
                self.model.highlight(cursor)
                cursor += 4

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
        mesh_group = MeshGroup(root, model, 12388)
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
        

def get_obj_by_id(id, collection = None):
    # node offsets repeat between models, so search only the model's own collection when we have it
    objects = collection.all_objects if collection is not None else bpy.data.objects
    for obj in objects:
        if obj.id == str(id):
            return obj
    return None

def get_mat_by_id(id):
    for mat in bpy.data.materials:
        if 'id' in mat and mat['id'] is not None and str(mat['id']) == str(id):
            return mat
    return None

def deep_select_objects(collection):
    for obj in collection.objects:
        if obj.type == 'MESH':
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
    for sub_collection in collection.children:
        deep_select_objects(sub_collection)

def check_pivot_helper(obj):
    """Export skips pivot helpers, so refuse one carrying an animation rather than drop it silently.

    The file has nowhere to keep it: the pivot is a fixed vector on the node (SW_RACER_RE
    src/types.h:1468-1474), and animations target nodes.
    """
    if obj.animation_data and obj.animation_data.action:
        raise ValueError(f"{obj.name} is a pivot helper and cannot be animated; "
                         f"animate the node it belongs to instead")

def through_pivot_helpers(objects):
    """objects, with each pivot helper import inserted replaced by the objects below it (helpers are not file nodes)."""
    found = []
    for obj in objects:
        if obj.get('pivot_helper'):
            check_pivot_helper(obj)
            found.extend(children_through_pivot_helpers(obj))
        else:
            found.append(obj)
    return found

def get_imported_part_root(immediate_children):
    """The empty that held a Part's slot 0 on import, if it is the collection's only top-level object.

    A Part's slot 0 must be a pivot node (0xD065): the game finds environment models by it
    (SW_RACER_RE dinput_hook/renderer_hook.cpp, try_replace_env).
    """
    immediate_children = through_pivot_helpers(immediate_children)
    if len(immediate_children) != 1:
        return None
    obj = immediate_children[0]
    if obj.type == 'EMPTY' and obj.get('node_type') == 53349 and 0 in obj.get('header', []):
        return obj
    return None

def get_imported_slot0_root(immediate_children):
    """The imported node at the top of the collection, if it is the only top-level node or mesh.

    Usually it held slot 0; a header-less basic node is the wrapper older exports put above it,
    which is reused rather than wrapped again. Lights (e.g. the 'pod_lighting' import makes for
    a mesh's lighting tag) are not nodes and don't count.
    """
    candidates = [obj for obj in through_pivot_helpers(immediate_children) if obj.type in ('EMPTY', 'MESH')]
    if len(candidates) != 1:
        return None
    obj = candidates[0]
    if obj.type == 'EMPTY' and obj.get('node_type') is not None and             (0 in obj.get('header', []) or obj.get('node_type') == 20580):
        return obj
    return None

def children_through_pivot_helpers(obj):
    """obj's children, looking through the pivot helpers import inserts (they are not file nodes)."""
    children = []
    for child in object_children(obj):
        if child.get('pivot_helper'):
            check_pivot_helper(child)
            children.extend(children_through_pivot_helpers(child))
        else:
            children.append(child)
    return children

def get_imported_podd_root(collection):
    """The slot 0 node of an imported Podd, if the collection holds one rather than the authoring template.

    The "new pod" template keeps its parts in Right Engine/Left Engine/Cockpit/Cable child
    collections (collection_type '2'..'5'); an imported pod is its node tree, rooted at the
    selector that held header slot 0.
    """
    if any(child.collection_type in ('2', '3', '4', '5') for child in collection.children):
        return None
    immediate_children = through_pivot_helpers(get_immediate_children(collection))
    if len(immediate_children) != 1:
        return None
    obj = immediate_children[0]
    if obj.type == 'EMPTY' and 0 in obj.get('header', []):
        return obj
    return None

def get_imported_skybox_root(immediate_children):
    """(slot-2 pivot, camera-follow node) of an imported skybox, if it is the collection's only top-level object."""
    immediate_children = through_pivot_helpers(immediate_children)
    if len(immediate_children) != 1:
        return None
    sky_obj = immediate_children[0]
    if sky_obj.type != 'EMPTY' or sky_obj.get('node_type') != 53349 or 2 not in sky_obj.get('header', []):
        return None
    children = children_through_pivot_helpers(sky_obj)
    if len(children) != 1 or children[0].type != 'EMPTY' or children[0].get('node_type') != 53350:
        return None
    return sky_obj, children[0]

def get_imported_track_root(immediate_children):
    """The basic node that held a track's slot 0 on import, if it is the Track collection's only top-level object."""
    immediate_children = through_pivot_helpers(immediate_children)
    if len(immediate_children) != 1:
        return None
    obj = immediate_children[0]
    if obj.type == 'EMPTY' and obj.get('node_type') == 20580 and 0 in obj.get('header', []):
        return obj
    return None

def get_immediate_children(collection):
    immediate_children = []
    for obj in collection.objects:
        # Include the object if it has no parent or its parent is not in the collection
        if obj.parent is None or obj.parent.name not in collection.objects:
            immediate_children.append(obj)
    return immediate_children

def imported_mesh_group(mesh):
    """The imported mesh group empty a mesh object sits under, if any."""
    obj = getattr(mesh, 'original_object', None)
    parent = obj.parent if obj is not None else None
    while parent is not None and parent.get('pivot_helper'):
        parent = parent.parent
    if parent is not None and parent.get('node_type') == 12388:
        return parent
    return None

def restore_mesh_group_flags(group):
    """See Model.restore_node_flags."""
    sources = {imported_mesh_group(mesh) for mesh in group.children if mesh is not None}
    if len(sources) != 1 or None in sources:
        return
    source = sources.pop()
    if 'vis_flags' not in source or 'col_flags' not in source:
        return
    vis, col = int(source['vis_flags']), int(source['col_flags'])
    has_col = any(mesh.has_collision() for mesh in group.children if mesh is not None)
    has_vis = any(mesh.has_visuals() for mesh in group.children if mesh is not None)
    if bool(col & 0x2) != has_col or bool(vis & 0x4) != has_vis:
        return
    group.vis_flags = (group.vis_flags & 0xFFFFFF00) | (vis & 0xFF)
    group.col_flags = (group.col_flags & 0xFFFFFF00) | (col & 0xFF)
    if 'transform_flags' in source:
        group.transform_flags = int(source['transform_flags'])

def is_identity(matrix, tolerance = 1e-6):
    return all(abs(matrix[i][j] - (1.0 if i == j else 0.0)) <= tolerance for i in range(4) for j in range(4))

def unmake_mesh_in_frame(obj, parent, model, matrix):
    """Mesh(parent).unmake(obj) with obj's vertices moved by matrix first.

    A mesh that does not become a node of its own is written in its parent node's space, which
    the game draws with that node's matrix (SW_RACER_RE swrModel_Mesh has no transform). Its own
    location/rotation/scale, and those of plain empties above it that are flattened away, would
    otherwise be lost, so they go into the vertices. The data is restored afterwards.
    """
    if is_identity(matrix):
        return Mesh(parent, model).unmake(obj)
    data = obj.data
    mirrored = matrix.determinant() < 0
    lit = (obj.visible or not obj.collidable) and object_uses_normals(obj)
    data.transform(matrix)
    if mirrored:
        # a mirroring transform reverses the winding: keep the faces' front side where it was
        data.flip_normals()
    if lit:
        # Model.unmake wrote the normal bytes before the vertices moved: write them again, turned
        unmake_vertex_normals(data)
    try:
        return Mesh(parent, model).unmake(obj)
    finally:
        if mirrored:
            data.flip_normals()
        data.transform(matrix.inverted())
        if lit:
            unmake_vertex_normals(data)

def deep_unmake(obj, parent, model, target_map, skybox = False, keep = False, carry = None):
    """The exported nodes and meshes for obj and its descendants, to be added under parent.

    keep: obj must come out as exactly one node, as a selector's child does: selectors pick
    children by index (SW_RACER_RE dinput_hook/renderer_hook.cpp:1375-1404).
    carry: the transform of the flattened (not exported) objects between parent's object and
    obj's parent; None when obj's parent is parent's own object.
    """
    if obj is None:
        return []

    if obj.get('MAlt') and model.alt_model is not None:
        # a high detail node import merged in from the Podd's MAlt goes back to the MAlt, as the
        # one node the Podd's AltN slot points at (Model.begin_alt_export). When the Podd parent
        # recorded its index, resolve_child_slots puts it back there.
        nodes = deep_unmake(obj, parent, model.alt_model, target_map, skybox, keep = True)
        file_parent = obj.parent
        while file_parent is not None and file_parent.get('pivot_helper'):
            file_parent = file_parent.parent
        if file_parent is not None and obj.id in file_parent.get('alt_children', {}).values():
            return []
        return nodes

    # Pivot-helper empties are inserted on import to realise T(-pivot) on
    # NodeTransformedWithPivot nodes. They do not correspond to a file node — descend
    # through them transparently so the helper's children attach to the file parent.
    if obj.get('pivot_helper'):
        check_pivot_helper(obj)
        children = []
        for child in object_children(obj):
            children.extend(deep_unmake(child, parent, model, target_map, skybox, keep))
        return children

    children = []

    # The game reads header slots as typed nodes (e.g. a puppet's slot 0 as a transform,
    # SW_RACER_RE swrRace_GetEngineNodeOffsetPos), so a node that held a slot must survive export.
    holds_header_slot = obj.type == 'EMPTY' and bool(obj.get('header'))
    # Selectors draw only their selected child and LOD selectors one child by distance
    # (SW_RACER_RE src/types.h); flattening them would draw every child.
    is_selector = obj.type == 'EMPTY' and obj.get('node_type') in (20581, 20582)
    # null slots and links to a node shared with another parent are written back by index
    # (Model.resolve_child_slots), so the node holding them, and the shared node, must stay nodes
    has_child_slots = obj.type == 'EMPTY' and bool(obj.get('null_slots') or obj.get('shared_children'))
    is_shared = obj.id in model.shared_target_ids
    # an imported pod keeps every node as itself (Model.begin_alt_export): the game flips the
    # flags of pod nodes at run time, e.g. one hidden basic node holds a copy of the engines
    keep_node = model.keep_imported_nodes and obj.type == 'EMPTY' and obj.get('node_type') is not None
    retained_as_transform = (obj.get('node_type') == 53349) or (obj.get('node_type') == 53350 and not skybox) or obj.animation_data or obj.name in target_map.keys() or is_selector or has_child_slots
    retained = retained_as_transform or holds_header_slot or keep_node
    if (keep or is_shared or holds_header_slot or keep_node) and not retained_as_transform and obj.type == 'EMPTY' and obj.get('node_type') == 12388:
        # a mesh group kept as one node: regroup its meshes and keep the single mesh group that
        # gives, rather than wrapping it in a transform (a pod's slot 59 is a mesh group)
        meshes = []
        for child in object_children(obj):
            meshes.extend(deep_unmake(child, parent, model, target_map))
        group = Group20580(parent, model, 20580)
        assign_objs_to_node_by_type(meshes, group, model)
        node = group
        # assign_objs_to_node_by_type gives visual and collision meshes their own groups; import
        # splits a stock mesh holding both (e.g. Modl 176's shared mesh group) into two objects,
        # so put them back in one mesh group when the groups' layers agree
        groups = group.children
        if len(groups) > 1 and all(isinstance(g, MeshGroup) for g in groups) and \
                len({(g.vis_flags, g.col_flags) for g in groups}) == 1:
            merged = groups[0]
            for other in groups[1:]:
                for mesh in other.children:
                    mesh.parent = merged
                    merged.children.append(mesh)
            merged.calc_bounding()
            group.children = [merged]
        if len(group.children) == 1 and isinstance(group.children[0], MeshGroup):
            node = group.children[0]
            node.parent = parent
        elif not group.children:
            # an imported mesh group with no meshes stays an (empty) mesh group, not a basic node
            node = MeshGroup(parent, model, 12388)
            node.calc_bounding()
        if holds_header_slot:
            node.imported_header = [int(slot) for slot in obj['header']]
        model.register_node(obj, node)
        return [node]
    if retained or keep or is_shared: # cases in which we need to retain hierarchy
        if obj.get('node_type') == 53350 and not skybox:
            empty = Group53350(parent, model, 53350).unmake(obj)
        elif obj.get('node_type') in (20580, 20581, 20582):
            # keep group/selector/LOD nodes as themselves rather than as a transform; they have
            # no transform of their own for an animation to drive
            empty = create_node(obj['node_type'], parent, model).unmake(obj)
        elif keep_node and obj.get('node_type') == 53348:
            empty = NodeTransformed(parent, model, 53348).unmake(obj)
            empty.node_type = 53348  # Node.unmake defaults empties to 53349
        else:
            empty = NodeTransformedWithPivot(parent, model, 53349).unmake(obj)

        empty_children = []

        if obj.name in target_map.keys():
            target_map[obj.name] = empty
        model.register_node(obj, empty)

        if obj.type == 'MESH':
            # the node made above already carries the object's animations; animating the mesh
            # too would add a second copy targeting the mesh struct, which the game would treat
            # as a transform node (SW_RACER_RE src/types.h swrModel_Animation node_ptr)
            mesh = Mesh(empty, model).unmake(obj, unmake_anim = False)
            empty_children.append(mesh)

        if is_selector:
            # one node per child, in file order (import names nodes by file offset)
            for child in children_through_pivot_helpers(obj):
                empty_children = empty_children + deep_unmake(child, empty, model, target_map, keep = True)
        else:
            for child in object_children(obj):
                empty_children = empty_children + deep_unmake(child, empty, model, target_map)
        assign_objs_to_node_by_type(empty_children, empty, model)
        children.append(empty)

        return children # early return since we've already dealt with descendants
    
    # obj is flattened: its children and its own mesh are written in parent's space
    frame = obj.matrix_local if carry is None else carry @ obj.matrix_local
    if obj.type == 'MESH':
        children.append(unmake_mesh_in_frame(obj, parent, model, frame))

    for child in object_children(obj):
        children.extend(deep_unmake(child, parent, model, target_map, carry = frame))

    return children

def get_all_objects_in_collection(collection):
    """Recursively get all objects in a collection and its subcollections."""
    objects = set(collection.objects)  # Start with objects directly in the collection
    for child_collection in collection.children:
        objects.update(get_all_objects_in_collection(child_collection))  # Add objects from subcollections
    return objects

def split_meshes_by_material(collection):
    bpy.ops.object.select_all(action='DESELECT')

    # only meshes with faces on more than one material need splitting; entering Edit mode on
    # every mesh of a track takes most of a second
    to_split = []
    for obj in get_all_objects_in_collection(collection):
        if obj.type == 'MESH' and len(obj.data.polygons):
            indices = [0] * len(obj.data.polygons)
            obj.data.polygons.foreach_get('material_index', indices)
            if len(set(indices)) > 1:
                to_split.append(obj)
    if not to_split:
        return
    for obj in to_split:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = to_split[0]

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
        self.hooked_meshes = [] # (mesh address, Mesh) whose referenced node is patched after writing
        self.ref_keeper = {} # where we'll remember locations of node refs to go back and update with the ref_map at the end
        self.hl = None
        
        self.header = ModelHeader(self, self)
        self.Data = None
        self.AltN = []
        self.Anim = None
        
        # Podd models get their high detail parts from a paired MAlt model (see read_alt_model)
        self.alt_model = None
        self.alt_buffer = None
        self.id_prefix = ''
        
        self.animations = []
        self.materials = {}
        self.textures = {}
        self.nodes = []
        self.triggers = []
        # export: ids of objects another node links to as a shared child, and the node each became
        self.shared_target_ids = set()
        self.shared_nodes = {}
        # export of an imported Podd (see begin_alt_export): AltN list length, the AltN index of
        # each Podd child slot holding a MAlt node, and (MAlt) the node behind each index
        self.altn_count = 0
        self.altn_slots = {}
        self.altn_nodes = []
        self.keep_imported_nodes = False

    def read(self, buffer):
        if self.id is None:
            return
        cursor = 0
        cursor = self.header.read(buffer, cursor)
        if cursor is None:
            show_custom_popup(bpy.context, "Unrecognized Model Extension", f"This model extension was not recognized: {self.header.model.type}")
            return None
        self.AltN = self.header.AltN
        
        if self.type == "4":
            self.read_alt_model()
        
        if self.type == "1":
            # a MAlt has no root of its own, its nodes are the AltN entries that get plugged into the Podd
            roots = list(dict.fromkeys(self.AltN))
        elif readUInt32BE(buffer, cursor):
            roots = [cursor]
        else:
            roots = []
            
        for root in roots:
            if self.ref_map.get(root):
                continue
            node = create_node(readUInt32BE(buffer, root), self, self)
            self.nodes.append(node.read(buffer, root))
            
        return self
    
    def read_alt_model(self):
        # The game merges a Podd with its MAlt on load:
        #   - every empty header slot of the Podd takes the MAlt's node in the same slot
        #   - every Podd AltN entry is the address of an empty child pointer, which gets the MAlt AltN node with the same index
        # Every MAlt slot node sits under one of its AltN nodes, so grafting the AltN nodes brings the slots along.
        MAlt_id = Podd_MAlt.get(str(self.id))
        if MAlt_id is None or self.modelblock is None:
            return
        alt_model = Model(MAlt_id)
        alt_model.modelblock = self.modelblock
        alt_model.id_prefix = 'MAlt_'
        self.alt_buffer = self.modelblock.fetch(MAlt_id)[1]
        alt_model.header.read(self.alt_buffer, 0)
        alt_model.AltN = alt_model.header.AltN
        self.alt_model = alt_model
        
    def read_alt_node(self, slot_addr, parent):
        if self.alt_model is None or slot_addr not in self.AltN:
            return None
        index = self.AltN.index(slot_addr)
        if index >= len(self.alt_model.AltN):
            return None
        addr = self.alt_model.AltN[index]
        if self.alt_model.ref_map.get(addr):
            return {'id': addr, 'shared': self.alt_model.obj_key(addr)}
        node = create_node(readUInt32BE(self.alt_buffer, addr), parent, self.alt_model)
        return node.read(self.alt_buffer, addr)
    
    def obj_key(self, offset):
        return f"{self.id_prefix}{offset}"

    def make(self):
        ensure_24_view_layers()
        collection = bpy.data.collections.new(f"model_{self.id}_{self.type}")
        collection.export_type = self.type
        collection.collection_type = "MODEL"
        
        bpy.context.scene.collection.children.link(collection)
        self.collection = collection
        if self.alt_model:
            self.alt_model.collection = collection
        
        self.pending_hides = []
        if self.alt_model:
            self.alt_model.pending_hides = self.pending_hides
        for node in self.nodes:
            self.modelblock.update_progress(f"Making node {node.id}")
            node.make(None, collection)
        for obj, view_layer in self.pending_hides:
            obj.hide_set(True, view_layer = view_layer)
        self.pending_hides = None
        if self.alt_model:
            self.alt_model.pending_hides = None

        # update trigger targets
        for trigger in self.triggers:
            if 'target_id' in trigger and trigger['target_id']:
                target = get_obj_by_id(trigger['target_id'], collection)
                trigger.target = target
                
        # transform parents with transforms
        # bpy.context.scene.tool_settings.use_transform_skip_children = True
        # for obj in collection.objects:
        #     if 'bonus' in obj:
        #         obj.select_set(True)
        #         bpy.ops.transform.translate(value=([v * self.scale for v in obj['bonus']] ))
        #         obj.select_set(False)
        # bpy.context.scene.tool_settings.use_transform_skip_children = False

                
        #header should be made last for the animations
        self.header.make()
        self.record_rest_poses(collection)

        return collection

    def unmake(self, collection, texture_export, textureblock):
        try:
            return self._unmake(collection, texture_export, textureblock)
        finally:
            clear_children_index()

    def _unmake(self, collection, texture_export, textureblock):
        self.textureblock = textureblock
        self.image_map = {}
        self.type = collection.export_type
        self.id = collection.export_model
        self.nodes = []
        self.texture_export = texture_export
        # Nodes that came from an imported file keep their place (deep_unmake keep_node) and their
        # flags (restore_node_flags): game code reaches into models by child index from a header
        # slot (SW_RACER_RE src/Swr/swrModel.c swrModel_NodeGetChild), e.g. to orient the spark
        # (Part 49) or swap the vehicle-select flag's texture (Part 48), and merging a plain group
        # away moved those targets one node down. Nodes made in Blender have no node_type and
        # are still merged into their parent. Podd also turns this on (begin_alt_export).
        self.keep_imported_nodes = str(self.type) in ('2', '3', '5', '6', '7')

        # Guard unsupported model types up front.Previously types 1/2/6 fell
        # through every branch below and silently wrote an EMPTY model over the
        # game file (data loss). Types 2 (Modl) and 6 (Scen) are now handled by
        # the generic branch; type 1 (MAlt) is exported automatically alongside
        # its Podd (see swr_export.py), not on its own.
        supported_types = ('2', '3', '4', '5', '6', '7')
        if str(self.type) not in supported_types:
            try:
                type_name = model_types[int(self.type)][1]
            except (ValueError, IndexError):
                type_name = str(self.type)
            if str(self.type) == '1':
                raise ValueError("MAlt (High-LOD pod) models are exported automatically with their Podd, not on their own.")
            raise ValueError(f"Exporting model type '{type_name}' is not supported.")

        root = Group20580(self, self, 20580)
        
        if self.type == '3':
            root = NodeTransformedWithPivot(self, self, 53349)
            root.header = [0]
            root.col_flags &= 0xFFFFFFFD
        
        
        
        target_map = {}

        #TODO: Resolve multi-user objects

        # Convenience-hidden meshes can't be entered into Edit mode by the mesh
        # operators below (split/scale/triangulate) - Blender refuses to edit a
        # hidden object. Export reads visibility from the game view layers (1..),
        # not the working layer, so force every mesh visible in the working layer
        # first; the exported vis/col flags are unaffected. The operator restores
        # the user's convenience visibility afterward.
        working_layer = bpy.context.scene.view_layers[0]
        if bpy.context.window:
            bpy.context.window.view_layer = working_layer
        for obj in get_all_objects_in_collection(collection):
            if obj.type == 'MESH':
                # only write what changes: each hide_viewport/hide_select write costs ~1ms
                if obj.hide_viewport:
                    obj.hide_viewport = False
                if obj.hide_select:
                    obj.hide_select = False
                obj.hide_set(False, view_layer=working_layer)

        split_meshes_by_material(collection)
        # before apply_scale: Blender's normals on zero-area faces shift when the mesh is rescaled,
        # and unmake_vertex_normals compares them against the ones recorded at import
        for obj in get_all_objects_in_collection(collection):
            if obj.type == 'MESH' and (obj.visible or not obj.collidable) and object_uses_normals(obj):
                unmake_vertex_normals(obj.data)
        apply_scale(collection)
        objects = get_all_objects_in_collection(collection)
        triangulate_mesh(objects)
        # the hierarchy is fixed from here on: walk it with one children map, not obj.children
        index_children()
        
        # check for too many faces
        for obj in objects:
            if obj.type == 'MESH' and (obj.visible or (not obj.visible and not obj.collidable)):
                faces = [[v for v in face.vertices] for face in obj.data.polygons]
                if len(faces) > 2048:
                    bpy.ops.object.select_all(action='DESELECT')
                    obj.select_set(True)
                    raise ValueError(f"Max faces reached in {obj.name} {len(faces)}/2048")
        
        # get all target objects
        # every trigger's target, whatever the trigger's id (0 included): Model.unmake resolves each
        # trigger's target through this map. Only triggers (CUBE empties, CollisionTrigger.unmake):
        # the panel's target field also sets `target` on selected meshes.
        target_map = {b_obj.target.name: None for b_obj in objects
                      if b_obj.target and b_obj.type == 'EMPTY' and b_obj.empty_display_type == 'CUBE'}
        self.shared_target_ids = {str(key) for b_obj in objects for key in b_obj.get('shared_children', {}).values()}
        self.shared_nodes = {}
        
        if self.type == '7': #TRAK
            # meshes and empties placed in the model collection itself are track scenery, exported
            # with the Track collection's slot 0/1 root. Import keeps the model's root node there
            # (its descendants are in Track/Skybox) and the lights: those are not scenery.
            loose = [obj for obj in get_immediate_children(collection)
                     if obj.type in ('MESH', 'EMPTY') and obj.get('node_type') is None]
            for child_collection in collection.children:
                r_root_node = Group20580(root, self, 20580)
                imported_sky = None
                imported_track = None
                
                if child_collection.collection_type == '0': #Track
                    imported_track = get_imported_track_root(get_immediate_children(child_collection))
                    if imported_track is not None:
                        # Re-exporting an imported track: its root already is the slot 0/1 node, so use
                        # it (and the null child slots the game leaves in it) rather than wrapping it
                        r_root_node = Group20580(root, self, 20580).unmake(imported_track)
                        if imported_track.name in target_map.keys():
                            target_map[imported_track.name] = r_root_node
                        self.register_node(imported_track, r_root_node)
                    r_root_node.header = [0, 1]
                    append_root = r_root_node
                    root.children.append(r_root_node)
                
                elif child_collection.collection_type == '1': #skybox
                    imported_sky = get_imported_skybox_root(get_immediate_children(child_collection))
                    if imported_sky is not None:
                        # Re-exporting an imported skybox: reuse its slot-2 pivot and camera-follow
                        # nodes rather than wrapping them in another pair each export.
                        sky_obj, camera_obj = imported_sky
                        sky_empty = NodeTransformedWithPivot(r_root_node, self, 53349).unmake(sky_obj)
                        sky_to_camera = Group53350(sky_empty, self, 53350).unmake(camera_obj)
                        self.register_node(sky_obj, sky_empty)
                        self.register_node(camera_obj, sky_to_camera)
                    else:
                        sky_empty = NodeTransformedWithPivot(r_root_node, self, 53349)
                        sky_to_camera = Group53350(sky_empty, self, 53350)
                        sky_to_camera.follow_position = 1
                    sky_empty.header = [2]
                    append_root = sky_to_camera
                    
                    sky_empty.children.append(sky_to_camera)
                    r_root_node.children.append(sky_empty)
                    root.children.append(r_root_node)
                else:
                    root.children.append(r_root_node)
                    append_root = r_root_node
                
                # get immediate children and traverse hierarchy
                immediate_children = get_immediate_children(child_collection)
                if child_collection.collection_type == '1' and imported_sky is not None:
                    immediate_children = children_through_pivot_helpers(imported_sky[1])
                elif child_collection.collection_type == '0' and imported_track is not None:
                    immediate_children = list(object_children(imported_track))
                if child_collection.collection_type == '0':
                    immediate_children = list(immediate_children) + loose
                    loose = []
                unmade = []
                for obj in immediate_children:
                    unmade.extend(deep_unmake(obj, append_root, self, target_map, skybox = (child_collection.collection_type == '1')))
                assign_objs_to_node_by_type(unmade, append_root, self)
                #r_root_node.set_flags()
            if loose:
                # no Track collection: the loose objects make the slot 0/1 root the game needs
                r_root_node = Group20580(root, self, 20580)
                r_root_node.header = [0, 1]
                root.children.append(r_root_node)
                unmade = []
                for obj in loose:
                    unmade.extend(deep_unmake(obj, r_root_node, self, target_map))
                assign_objs_to_node_by_type(unmade, r_root_node, self)

        elif self.type in ('2', '3', '5', '6'): #Modl / Part / Pupp / Scen
            # All four are plain node/mesh hierarchies rooted at a basic (20580)
            # node, so they share the generic traversal.
            unmade = []
            immediate_children = get_immediate_children(collection)
            imported_root = get_imported_part_root(immediate_children) if self.type in ('2', '3') else None
            slot0_root = get_imported_slot0_root(immediate_children) if imported_root is None else None
            if slot0_root is not None:
                # Stock Modl/Pupp/Scen models start at their slot-0 node, whatever its type
                # (a pivot node, a selector, a basic node), with no group above it. Wrapping it
                # in a new basic node each export made re-imports grow by one node per export,
                # now that imported nodes are kept (keep_imported_nodes).
                root = deep_unmake(slot0_root, None, self, target_map, keep = True)[0]
                immediate_children = []
            elif imported_root is not None:
                # Re-exporting an imported Part: its root already is the slot-0 pivot node the
                # template would create, so use it rather than wrapping it in another one each export.
                # A Modl whose slot 0 is a pivot node (e.g. 176) likewise has it as its first node,
                # with no basic node above it.
                root = NodeTransformedWithPivot(self, self, 53349).unmake(imported_root)
                root.header = [0]
                if imported_root.name in target_map.keys():
                    target_map[imported_root.name] = root
                self.register_node(imported_root, root)
                immediate_children = list(object_children(imported_root))
            for obj in immediate_children:
                unmade.extend(deep_unmake(obj, root, self, target_map))
            assign_objs_to_node_by_type(unmade, root, self)

        elif self.type == '4' and get_imported_podd_root(collection) is not None:
            # Re-exporting an imported pod: write its own node tree back (LODs, animations and
            # every header slot the game looks up), not the authoring template below, and split
            # the high detail nodes import merged in from the MAlt back out (see begin_alt_export).
            imported_root = get_imported_podd_root(collection)
            self.begin_alt_export(objects)
            root = deep_unmake(imported_root, None, self, target_map, keep = True)[0]

        elif self.type == '4': #PODD
            def create_podd_component(mesh, type):
                comp_a = NodeTransformedWithPivot(None, self, 53349)
                comp_b = NodeTransformed(None, self, 53348)
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
                air_a = NodeTransformedWithPivot(None, self, 53349, header = [top_header])
                air_b = Group53350(None, self, 53350)
                link_nodes(air_a, [air_b])
                air_c = NodeTransformedWithPivot(None, self, 53349, header = [bottom_header])
                link_nodes(air_b, [air_c])
                air_d = NodeTransformedWithPivot(None, self, 53349)
                link_nodes(air_c, [air_d])
                if len(mesh):
                    assign_objs_to_node_by_type([Mesh(None, self).unmake(obj) for obj in mesh], air_d, self)
                return air_a
            
            root = Group20581(root, self, 20581, header = [0])
            
            podd_a_node = Group20580(None, self, 20580)
            podd_74_node = NodeTransformedWithPivot(None, self, 53349, header = [74])
            link_nodes(root, [podd_a_node, podd_74_node])
            
            podd_shadows_node = Group20580(None, self, 20580)
            podd_engine_r_shadow = NodeTransformedWithPivot(None, self, 53349, header = [62])
            podd_engine_l_shadow = NodeTransformedWithPivot(None, self, 53349, header = [63])
            podd_cockpit_shadow = NodeTransformedWithPivot(None, self, 53349, header = [64])
            link_nodes(podd_shadows_node, [podd_engine_r_shadow, podd_engine_l_shadow, podd_cockpit_shadow])
            
            podd_b_node = Group20580(None, self, 20580)
            
            podd_71_node = Group20580(None, self, 20580, header = [71])
            link_nodes(podd_b_node, [podd_71_node])
            
            podd_sparks = NodeTransformedWithPivot(None, self, 53349, header = [65])
            podd_sparks_ai = NodeTransformedWithPivot(None, self, 53349, header = [66])
            podd_72_node = NodeTransformedWithPivot(None, self, 53349, header = [72])
            podd_73_node = NodeTransformedWithPivot(None, self, 53349, header = [73])
            podd_binder1 = NodeTransformedWithPivot(None, self, 53349, header = [6])
            podd_binder2 = NodeTransformedWithPivot(None, self, 53349, header = [7])
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
                    podd_engine_r = NodeTransformedWithPivot(None, self, 53349, header = [1])
                    link_nodes(podd_engine_r, right_engine.children)
                    right_engine.header = [14]
                elif child_collection.collection_type == '3':
                    left_engine_mesh = get_all_objects_in_collection(child_collection)
                    left_engine = create_podd_component(left_engine_mesh, 'engine_l')
                    link_nodes(podd_71_node, [left_engine])
                    podd_engine_l = NodeTransformedWithPivot(None, self, 53349, header = [2])
                    link_nodes(podd_engine_l, left_engine.children)
                    left_engine.header = [15]
                elif child_collection.collection_type == '4':
                    cockpit_mesh = get_all_objects_in_collection(child_collection)
                    cockpit = create_podd_component(cockpit_mesh, 'cockpit')
                    link_nodes(podd_71_node, [cockpit])
                    podd_cockpit = NodeTransformedWithPivot(None, self, 53349, header = [5])
                    link_nodes(podd_cockpit, cockpit.children)
                    link_nodes(podd_a_node, [podd_cockpit])
                    cockpit.header = [16]
                elif child_collection.collection_type == '5':
                    cable_mesh = get_all_objects_in_collection(child_collection)
                    podd_cable1 = NodeTransformedWithPivot(None, self, 53349, header = [10])
                    podd_cable2 = NodeTransformedWithPivot(None, self, 53349, header = [11])
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
        self.resolve_child_slots()
        self.resolve_header_slots()
        if self.keep_imported_nodes:
            self.restore_node_flags()
        if self.alt_model is not None:
            self.end_alt_export()

        #update trigger targets
        for trigger in self.triggers:
            if trigger.target:
                trigger.target = target_map[trigger.target.name]

        # stock animations with no target (Anim.make keeps them on the collection)
        self.animations.extend(raw_anims(None, collection, self))
        self.sort_animations()
        self.header.unmake(collection)

        return self

    def sort_animations(self):
        """Imported animations back in their stock list order, new ones after them.

        Game code may pick a model's animations by their position in the header's list (cutscene
        models carry several per node), so the order is kept rather than rebuilt from the scene.
        """
        self.animations = [anim for anim in self.animations if anim is not None]
        self.animations.sort(key = lambda anim: (anim.index is None, anim.index if anim.index is not None else 0))

    def record_rest_poses(self, collection):
        """Remember each animated node's frame 0 basis, so export can tell it was left as imported.

        The game overwrites an animated node's matrix every frame, but the stored rest matrix is
        what the node holds before its animation runs (and what a transition blends from); stock
        rest poses often differ slightly from the first key. NodeTransformedWithPivot.unmake writes
        the stored matrix back while the frame 0 pose is still the one import made.
        """
        for obj in collection.all_objects:
            if 'file_matrix' not in obj or not obj.animation_data or not obj.animation_data.action:
                continue
            obj['frame0_basis'] = basis_values(frame0_basis(obj))

    def begin_alt_export(self, objects):
        """Export the nodes import merged in from this Podd's MAlt into a MAlt model of their own.

        The game loads a Podd with its MAlt and merges them (SW_RACER_RE
        src/Swr/swrModel.h:365-366 swrModel_FixupAltNodePointers, 0x00448c70; the MAlt's AltN
        node list is byte swapped as nodes, src/Swr/swrModel.c:216-228): each Podd AltN entry is
        the address of a null child pointer, which gets the MAlt AltN node with the same index,
        and each empty Podd header slot gets the MAlt's node in that slot. Import grafts the MAlt
        nodes into the Podd tree the same way and tags them 'MAlt' (Model.read_alt_model);
        deep_unmake gives those to self.alt_model, and end_alt_export pairs each graft point with
        an AltN index.
        """
        self.keep_imported_nodes = True
        MAlt_id = Podd_MAlt.get(str(self.id))
        if MAlt_id is None:
            return
        alt = Model(MAlt_id)
        alt.keep_imported_nodes = True
        alt.type = '1'
        alt.id_prefix = 'MAlt_'
        alt.textureblock = self.textureblock
        alt.texture_export = self.texture_export
        alt.image_map = self.image_map  # texture ids are global to the textureblock
        # shared-child keys are namespaced by model ('MAlt_<offset>'), so one registry serves both
        alt.shared_target_ids = self.shared_target_ids
        alt.shared_nodes = self.shared_nodes
        self.shared_target_ids.update(str(key) for obj in objects for key in obj.get('alt_children', {}).values())
        self.alt_model = alt

    def end_alt_export(self):
        """Pair every Podd child slot holding a MAlt node with an AltN index (see begin_alt_export)."""
        alt = self.alt_model
        self.altn_slots = {}
        alt.altn_nodes = []
        roots = []
        seen = set()
        stack = list(self.nodes)
        while stack:
            node = stack.pop(0)
            if not isinstance(node, Node) or id(node) in seen or node.model is not self:
                continue
            seen.add(id(node))
            for index, child in enumerate(node.children):
                if isinstance(child, Node) and child.model is alt:
                    self.altn_slots[(id(node), index)] = len(alt.altn_nodes)
                    alt.altn_nodes.append(child)
                    if child not in roots:
                        roots.append(child)
            stack.extend(child for child in node.children if child is not None)
        alt.nodes = roots
        self.altn_count = alt.altn_count = len(alt.altn_nodes)
        alt.header.size = self.header.size
        alt.Anim = AnimList(alt.header, alt).unmake()

    def restore_node_flags(self):
        """Give the imported nodes back their own vis/col flags.

        The game switches pod parts (shadows, sparks, ...) on and off by setting the low flag bits
        of the node it looks up (SW_RACER_RE src/Swr/swrModel.c:1761 swrModel_NodeModifyFlags), so a
        node the stock pod keeps hidden must stay hidden, rather than get set_flags' all-visible
        flags. A mesh group whose meshes all come from one imported mesh group gets that group's
        flags_3 and low flag bytes back (its layer bits come from the meshes), unless its
        collision/visuals bits (0x2 of col_flags, 0x4 of vis_flags) no longer match its meshes.
        """
        seen = set()
        stack = list(self.nodes)
        while stack:
            node = stack.pop()
            if not isinstance(node, Node) or id(node) in seen:
                continue
            seen.add(id(node))
            source = node.original_object
            if source is not None and not isinstance(node, MeshGroup):
                if 'vis_flags' in source:
                    node.vis_flags = int(source['vis_flags'])
                if 'col_flags' in source:
                    node.col_flags = int(source['col_flags'])
            if isinstance(node, MeshGroup):
                restore_mesh_group_flags(node)
                continue
            stack.extend(child for child in node.children if child is not None)

    def write_altn_slot(self, buffer, node, index, child_ptr):
        """List a null child pointer that the game fills with a MAlt node in the AltN header list."""
        altn_index = self.altn_slots[(id(node), index)]
        writeUInt32BE(buffer, child_ptr, self.ref_map['AltN'] + 4 * altn_index)

    def find_mesh_group(self, obj):
        """The exported mesh group node holding obj's child meshes (export regroups meshes)."""
        stack = list(self.nodes)
        while stack:
            node = stack.pop()
            if not isinstance(node, Node):
                continue
            if node.node_type == 12388:
                for mesh in node.children:
                    source = getattr(mesh, 'original_object', None)
                    if source is not None and (source.parent == obj or source == obj):
                        return node
            stack.extend(child for child in node.children if child is not None)
        return None

    def register_node(self, obj, node):
        """Remember the node obj was exported as, if another node links to it as a shared child."""
        if obj.id in self.shared_target_ids:
            self.shared_nodes.setdefault(obj.id, node)

    def resolve_child_slots(self):
        """Put the null child slots and shared-child links import recorded back at their indices.

        The file's child lists can hold null pointers and point at a node another parent also
        lists; selectors and LOD selectors pick children by index (SW_RACER_RE
        dinput_hook/renderer_hook.cpp:1375-1404), so these keep their slot. write_children writes
        a shared node once and points every later slot at that copy.
        """
        seen = set()
        stack = list(self.nodes)
        while stack:
            node = stack.pop()
            if not isinstance(node, Node) or id(node) in seen:
                continue
            seen.add(id(node))
            fills = [(slot, None) for slot in node.null_slots]
            for slot, key in node.shared_slots.items():
                target = self.shared_nodes.get(key)
                if target is not None and target is not node:
                    fills.append((slot, target))
            for slot, child in sorted(fills, key=lambda fill: fill[0]):
                node.children.insert(min(slot, len(node.children)), child)
            stack.extend(child for child in node.children if child is not None)

    def resolve_header_slots(self):
        """Give imported nodes back the header slots they held, where no export template claims the slot."""
        nodes = []
        stack = list(self.nodes)
        while stack:
            node = stack.pop()
            if isinstance(node, Node):
                nodes.append(node)
                stack.extend(child for child in node.children if child is not None)
        claimed = {slot for node in nodes for slot in node.header}
        for node in nodes:
            for slot in node.imported_header:
                if slot not in claimed:
                    node.header.append(slot)
                    claimed.add(slot)

    def write(self):
        buffer = bytearray(8000000)
        self.hl = bytearray(1000000)
        cursor = 0

        cursor = self.header.write(buffer, cursor)

        # write all nodes
        for node in self.nodes:
            if node.write_location is None:  # a MAlt's AltN nodes can sit under one another
                cursor = node.write(buffer, cursor)
        for i, node in enumerate(self.altn_nodes):
            writeUInt32BE(buffer, node.write_location, self.ref_map['AltN'] + 4 * i)
            
        # write all animations
        if self.Anim:
            for i, anim in enumerate(self.Anim.data):
                writeUInt32BE(buffer, cursor, self.anim_list + i*4)
                cursor = anim.write(buffer, cursor)
            
        # write trigger targets
        for trigger in self.triggers:
            trigger.write_target(buffer)

        # point hooked meshes at their referenced node: the mesh group holding the hook target's
        # meshes, whose matrix the game draws the hooked prefix with (SW_RACER_RE
        # dinput_hook/renderer_hook.cpp reads referenced_node->children.meshes[0]'s matrix)
        for mesh_start, mesh in self.hooked_meshes:
            group = self.find_mesh_group(mesh.hook_target) or mesh.parent
            writeUInt32BE(buffer, group.write_location, mesh_start + 40)
                
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
