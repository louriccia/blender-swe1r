import bpy
from .utils import get_anim_loop, set_anim_loop, update_export_model, save_settings, get_setting, model_types, update_model_dropdown, export_model_items, update_selected, populate_enum, create_update_function, UpdateVisibleSelectable, model_enum_item, import_model_items
from .swe1r.model_list import model_list
from .swe1r.modelblock import SurfaceEnum, TriggerFlagEnum
from .swe1r.trigger_types import TRIGGER_TYPES, type_label
from .swe1r.modelblock import apply_blend_preset, detect_blend_preset, material_shader_words, Material

# Blend Mode dropdown entries: (identifier, label, description); the item number is the index
BLEND_MODE_ITEMS = [
    ('OPAQUE', "Opaque", "Solid: texture x vertex color (or the game's lighting on lit meshes). Color is not used"),
    ('TINTED', "Tinted", "Solid, multiplied by Color. Stock pods, characters and scenery use this"),
    ('CUTOUT', "Cutout", "Hard-edged holes where the texture's alpha is under half (fences, foliage). Color is not used"),
    ('TRANSLUCENT', "Translucent", "Blends the texture's alpha with what is behind it (ice, water). Sorted per mesh; Color is not used"),
    ('GLOW', "Glow", "See-through, double-sided effect tinted by Color; Color's alpha is its opacity (energy binders, engine flames)"),
    ('FLAT', "Flat Color", "Solid Color x vertex color; the texture is ignored"),
    ('SHADOW', "Shadow", "A pod shadow: Color, shown where the texture is transparent (stock shadows use a soft blob texture); Color's alpha is its darkness"),
    ('SKY', "Sky", "No depth test and no fog. Set automatically for meshes in a Skybox collection"),
    ('CUSTOM', "Custom", "An imported setup none of the presets matches. It is kept exactly as imported"),
]
BLEND_MODE_IDS = [item[0] for item in BLEND_MODE_ITEMS]
# the sidebar's dropdown: Sky is automatic, so it isn't offered
SCENE_BLEND_MODE_ITEMS = [(*item, i) for i, item in enumerate(BLEND_MODE_ITEMS) if item[0] != 'SKY']


def get_material_blend_mode(self):
    return BLEND_MODE_IDS.index(detect_blend_preset(material_shader_words(self)))


def set_material_blend_mode(self, value):
    apply_blend_preset(self, BLEND_MODE_IDS[value])


def blend_mode_materials(context):
    """The first (exported) material of each selected mesh."""
    return [(obj, obj.material_slots[0].material) for obj in context.selected_objects
            if obj.type == 'MESH' and len(obj.material_slots) and obj.material_slots[0].material is not None]


def get_scene_blend_mode(self):
    context = bpy.context
    materials = blend_mode_materials(context)
    if not materials:
        return BLEND_MODE_IDS.index('OPAQUE')
    active = next((m for o, m in materials if o == context.active_object), materials[0][1])
    name = active.blend_mode
    return BLEND_MODE_IDS.index('CUSTOM' if name == 'SKY' else name)


def set_scene_blend_mode(self, value):
    name = BLEND_MODE_IDS[value]
    if name == 'CUSTOM':
        return
    from .utils import reselect_obj
    for obj, material in blend_mode_materials(bpy.context):
        material.blend_mode = name
        obj.material_slots[0].material = Material(None, None).remake(material)
        reselect_obj(obj)

# the Trigger Type dropdown's entry for a number not in TRIGGER_TYPES
OTHER_TRIGGER_TYPE = 999999

def get_trigger_type(self):
    return self.trigger_id if self.trigger_id in TRIGGER_TYPES else OTHER_TRIGGER_TYPE

def set_trigger_type(self, value):
    if value != OTHER_TRIGGER_TYPE:
        self.trigger_id = value

# Node panel: an empty's node type and settings, read and written as the custom properties
# import stores and export reads (obj['node_type'], ['selected_child'], ['floats'],
# ['follow_position'], ['track_position']; swe1r/modelblock.py Group2058x / Group53350)
NODE_TYPE_ITEMS = [
    ('AUTO', "Automatic", "Kept as a transform when it is animated, a trigger target or holds a slot; otherwise merged into its parent", 0),
    ('GROUP', "Group", "A plain node that draws all its children", 20580),
    ('TRANSFORM', "Transform", "A node with its own position, rotation and scale, kept even when nothing animates it", 53349),
    ('SELECTOR', "Selector", "Draws one chosen child, all of them or none", 20581),
    ('LOD', "LOD Selector", "Draws one child by distance from the camera: the first child is the most detailed", 20582),
    ('CAMERA', "Camera-facing", "Turns to face the camera, or follows the model's position (sky, binders, billboards)", 53350),
    ('TRANSFORM_PLAIN', "Transform (no pivot)", "An imported transform node without a pivot", 53348),
    ('MESH_GROUP', "Mesh Group", "An imported mesh group: the meshes under it", 12388),
]

def get_node_type(self):
    value = self.get('node_type')
    return int(value) if value is not None and int(value) in [i[3] for i in NODE_TYPE_ITEMS] else 0

def set_node_type(self, value):
    if value == 0:
        if 'node_type' in self:
            del self['node_type']
        return
    self['node_type'] = value

def custom_getter(key, default, kind=int):
    def get(self):
        value = self.get(key)
        return kind(value) if value is not None else default
    return get

def custom_setter(key, kind=int):
    def set(self, value):
        self[key] = kind(value)
    return set

def get_lod_distances(self):
    floats = list(self.get('floats', ())) or [0.0, 40.0, 60.0, 100.0, 1000000.0, -1.0, -1.0, -1.0]
    return [float(f) for f in floats[:8]]

def set_lod_distances(self, value):
    floats = list(self.get('floats', ())) or [0.0] * 11
    floats = (floats + [0.0] * 11)[:11]
    floats[:8] = [float(v) for v in value]
    self['floats'] = floats

class SWR_FlipbookFrame(bpy.types.PropertyGroup):
    image: bpy.props.PointerProperty(type=bpy.types.Image, name="Image", description="The texture shown for this frame")

class MY_ListItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()

    # Three-state toggle: Unchecked, Checked, Exed
    toggle_state: bpy.props.EnumProperty(
        items=[
            ("UNCHECKED", "Unchecked", "", "CHECKBOX_DEHLT", 0),
            ("CHECKED", "Checked", "", "CHECKBOX_HLT", 1),
            ("EXED", "Exed", "", "CANCEL", 2)
        ],
        name="Toggle State",
        default="UNCHECKED"
    )

def register():
    bpy.utils.register_class(SWR_FlipbookFrame)
    bpy.types.Scene.import_folder = bpy.props.StringProperty(subtype='DIR_PATH', update=save_settings, default = get_setting('import_folder', ""), description="Select the lev01 folder in Star Wars Episode I Racer/data/lev01 (or any folder containing the .bin files)")
    bpy.types.Scene.import_type = bpy.props.EnumProperty(
        items=model_types,
        name="Model Type",
        description="Filter model selection by model type",
        default=get_setting('import_type', 0), 
        update=update_model_dropdown
    )
    
    # MAlt models are exported with their Podd, never on their own
    new_types = [t for t in model_types[1:] if t[1] != 'MAlt']
    saved_new_type = str(get_setting('new_type', '7'))
    bpy.types.Scene.new_type = bpy.props.EnumProperty(
        items=new_types,
        name="New Model Type",
        description="The type of model New creates",
        default=saved_new_type if saved_new_type in [t[0] for t in new_types] else '7',
        update=save_settings,
    )
    
    bpy.types.Scene.import_model = bpy.props.EnumProperty(
        items=import_model_items(model_types[int(get_setting('import_type', 0))][1]),
        name="Model",
        description="Select a model to import",
        default=0, #get_setting('import_model', 0), 
        update=save_settings
    )
    bpy.types.Scene.export_folder = bpy.props.StringProperty(subtype='DIR_PATH', update=save_settings, default=get_setting('export_folder', ""), description="Select the lev01 folder in Star Wars Episode I Racer/data/lev01 (or any folder you wish to export to)")
    bpy.types.Scene.is_export_model = bpy.props.BoolProperty(name="Model", update=save_settings, default=get_setting('is_export_model', True), description="Export the model (meshes, collision, nodes, animations)")
    bpy.types.Scene.is_export_texture = bpy.props.BoolProperty(name="Texture", update=save_settings, default=get_setting('is_export_texture', True), description="Export the model's textures")
    bpy.types.Scene.is_export_spline = bpy.props.BoolProperty(name="Spline", update=save_settings, default=get_setting('is_export_spline', True), description="Export the track's spline (the racing line, start point and AI path)")
    bpy.types.Scene.is_export_separate = bpy.props.BoolProperty(name ="Separate", update =save_settings, default=get_setting('is_export_separate', False), description = "Also save the exported model and spline as individual .bin files")
    bpy.types.Scene.is_export_debug = bpy.props.BoolProperty(name ="Debug", update =save_settings, default=get_setting('is_export_debug', False), description = "Write a human-readable debug dump of the exported model buffer alongside the .bin files (for troubleshooting only)")

    
    bpy.types.Scene.import_progress = bpy.props.FloatProperty(name="Import Progress", default=0.0, min=0.0, max=1.0)
    bpy.types.Scene.import_status = bpy.props.StringProperty(name="Import Status", default="")
    bpy.types.Scene.export_progress = bpy.props.FloatProperty(name="Export Progress", default=0.0, min=0.0, max=1.0)
    bpy.types.Scene.export_status = bpy.props.StringProperty(name="Export Status", default="")
    
    bpy.types.Scene.indeterminates = bpy.props.StringProperty(name = "Indeterminates", default = "")
    bpy.types.Scene.is_v_lighting_default = bpy.props.BoolProperty(name = 'is_v_lighting_default', default = True)
    bpy.types.Scene.is_texture_default = bpy.props.BoolProperty(name = 'is_texture_default', default = True)
    bpy.types.Scene.is_terrain_default = bpy.props.BoolProperty(name = 'is_terrain_default', default = True)
    bpy.types.Scene.is_fog_default = bpy.props.BoolProperty(name = 'is_fog_default', default = True)
    bpy.types.Scene.is_lighting_default = bpy.props.BoolProperty(name = 'is_lighting_default', default = True)
    bpy.types.Scene.is_loading_default = bpy.props.BoolProperty(name = 'is_loading_default', default = True)
    bpy.types.Scene.is_collision_default = bpy.props.BoolProperty(name = 'is_collision_default', default = True)
    bpy.types.Scene.is_visuals_default = bpy.props.BoolProperty(name = 'is_visuals_default', default = True)
    
    bpy.types.Collection.export_model = bpy.props.EnumProperty(
        items = export_model_items,
        name = "Model",
        description = "The game model this collection replaces on export",
        default = 0,
        update = update_export_model,
    )
    
    bpy.types.Collection.export_type = bpy.props.EnumProperty(
        items=[i for i in model_types[1:]],
        name="Model Type",
        description="The type of game model this collection is",
        default=0,
    )
    bpy.types.Collection.collection_type = bpy.props.EnumProperty(
        items=[
            ("NONE", "None", "Unspecified type"),
            ("MODEL", "Model", "A Model Collection"),
            ("0", "Track", "A Track Model Collection"),
            ("1", "Skybox", "A Track Skybox Collection"),
            ("2", "Right Engine", "The Podd's Right Engine"),
            ("3", "Left Engine", "The Podd's Left Engine"),
            ("4", "Cockpit", "The Podd's Cockpit"),
            ("5", "Cable", "The Podd's Cable"),
            ("6", "Jet Trails", "The Podd's jet trails: each mesh trails from the nearest exhaust anchor"),
            ("7", "Shadows", "The Podd's shadows: each mesh goes under the nearest engine or cockpit anchor"),
            ("8", "Engine Glow", "The Podd's engine glow: a mesh here gives the glow its material; left empty, the stock glow"),
        ],
        name = "Collection Type",
        description="The type of collection",
        default = "NONE"
    )
   
    # MARK: obj state
    bpy.types.Object.id = bpy.props.StringProperty(name = "id", default = "")
    
    bpy.types.Object.visible = bpy.props.BoolProperty(name ='Visible', default=False, description="The mesh is drawn in game")
    bpy.types.Object.collidable = bpy.props.BoolProperty(name ='Collidable', default=False, description="Pods collide with the mesh in game")
    bpy.types.Object.collision_data = bpy.props.BoolProperty(name ='Collision Data', default=False, description="The collision mesh carries surface flags, fog, pod lighting, load triggers and event triggers")
    
    for flag in dir(SurfaceEnum):
        if not flag.startswith("__"):
            setattr(bpy.types.Object, flag, bpy.props.BoolProperty(name = flag, default=False))
            
    bpy.types.Object.magnet = bpy.props.BoolProperty(name ='magnet', default=False)
    bpy.types.Object.strict_spline = bpy.props.BoolProperty(name ='strict_spline', default=False)
    bpy.types.Object.elevation = bpy.props.BoolProperty(name ='elevation', default=False)
    
    bpy.types.Object.lighting_light = bpy.props.PointerProperty(type=bpy.types.Light, name="lighting_light")
    bpy.types.Object.lighting_color = bpy.props.FloatVectorProperty(name="lighting_color", subtype='COLOR', size=3, default=(1.0, 1.0, 1.0), min=0, max=1, description="Ambient Color")
    bpy.types.Object.lighting_invert = bpy.props.BoolProperty(name = 'lighting_invert', default=False)
    bpy.types.Object.lighting_flicker = bpy.props.BoolProperty(name = 'lighting_flicker', default=False)
    bpy.types.Object.lighting_persistent = bpy.props.BoolProperty(name = 'lighting_persistent', default=False)
    
    bpy.types.Object.fog_color_update = bpy.props.BoolProperty(name = 'fog_color_update', default=False)
    bpy.types.Object.fog_color = bpy.props.FloatVectorProperty(name="fog_color", subtype='COLOR', size=3, default=(1.0, 1.0, 1.0), min=0, max=1, description="Fog color")
    bpy.types.Object.fog_range_update = bpy.props.BoolProperty(name = 'fog_range_update', default=False)
    bpy.types.Object.fog_min = bpy.props.IntProperty(name="fog_min", default=1000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Fog min (distance at which fog begins)", subtype = 'DISTANCE')
    bpy.types.Object.fog_max = bpy.props.IntProperty(name="fog_max", default=30000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Fog max (distance at which fog is fully opaque)", subtype = 'DISTANCE')
    bpy.types.Object.fog_clear = bpy.props.BoolProperty(name = 'fog_clear', default=False)
    bpy.types.Object.skybox_show = bpy.props.BoolProperty(name ='skybox_show', default=False)
    bpy.types.Object.skybox_hide = bpy.props.BoolProperty(name ='skybox_hide', default=False)
   
    bpy.types.Object.load_trigger = bpy.props.IntVectorProperty(
        name="load_trigger",
        size=24,  # Number of elements
        default=(0 for i in range(24))  # Optional default values
    )
    
    # MARK: material state
    bpy.types.Material.scroll_x = bpy.props.FloatProperty(name = 'scroll_x', default = 0.0)
    bpy.types.Material.scroll_y = bpy.props.FloatProperty(name = 'scroll_y', default = 0.0)
    bpy.types.Material.flip_x = bpy.props.BoolProperty(name = 'flip_x', default = False)
    bpy.types.Material.flip_y = bpy.props.BoolProperty(name = 'flip_y', default = False)
    bpy.types.Material.clip_x = bpy.props.BoolProperty(name = 'clip_x', default = False)
    bpy.types.Material.clip_y = bpy.props.BoolProperty(name = 'clip_y', default = False)
    # files from older versions chose translucency with this; the Blend Mode dropdown replaces it
    bpy.types.Material.transparent = bpy.props.BoolProperty(name = 'transparent', default = False)
    bpy.types.Material.blend_mode = bpy.props.EnumProperty(name = 'Blend Mode', items = [(*item, i) for i, item in enumerate(BLEND_MODE_ITEMS)], get = get_material_blend_mode, set = set_material_blend_mode, description = "How the game draws the material: a preset copied from stock materials")
    # texture flipbook: the material's texture swaps through these frames in game
    bpy.types.Material.flipbook_frames = bpy.props.CollectionProperty(type=SWR_FlipbookFrame)
    bpy.types.Material.flipbook_index = bpy.props.IntProperty(default=0)
    bpy.types.Material.flipbook_frame_time = bpy.props.FloatProperty(name="Frame Time", default=0.04, min=0.001, soft_max=1.0, precision=3, description="Seconds each frame shows (stock flipbooks use 0.02 to 0.05)")
    bpy.types.Material.flipbook_loop = bpy.props.BoolProperty(name="Loop", default=True, description="Start over after the last frame. Off: play once and hold the last frame")
    bpy.types.Material.material_color = bpy.props.FloatVectorProperty(name = 'Color', subtype='COLOR', size = 4, min=0.0, max=1.0, description="The material's base (primitive) color")
    
    
    #light state
    bpy.types.Light.LStr = bpy.props.BoolProperty(name = 'Light Streak', default=False, update = create_update_function("LStr"), description="Export this light's position as a light streak (LStr), the streaks of light drawn on the camera when it passes. Tracks only")
    
    # MARK: Trigger State
    trigger_flag_descriptions = {
        'Disabled': "The trigger starts disarmed and never fires",
        'IgnoreAI': "Only the local player's pod fires the trigger",
        'SpeedCheck150': "Fires only when the pod is faster than 150",
        'SkipLap1': "Does not fire on lap 1",
        'SkipLap2': "Does not fire on lap 2",
        'SkipLap3': "Does not fire on lap 3",
    }
    bpy.types.Object.trigger_id = bpy.props.IntProperty(name='Type Number', update = create_update_function("trigger_id"), description="The trigger's type number in the game")
    # a named view of trigger_id; the number is what is stored and exported
    trigger_type_items = [(str(t), type_label(t), entry[1], t) for t, entry in TRIGGER_TYPES.items()]
    trigger_type_items.append(('OTHER', "Other", "A type number not in this list: set it in the number field", OTHER_TRIGGER_TYPE))
    bpy.types.Object.trigger_type = bpy.props.EnumProperty(name='Trigger Type', items=trigger_type_items, get=get_trigger_type, set=set_trigger_type, description="What the trigger does in game")
    bpy.types.Object.trigger_settings = bpy.props.IntProperty(name='Settings', update = create_update_function("trigger_settings"), description="Extra flag bits stored with the trigger (bits 6-15). No known effect")
    for flag in dir(TriggerFlagEnum):
        if not flag.startswith("__"):
            setattr(bpy.types.Object, flag, bpy.props.BoolProperty(name = flag, default=False, update = create_update_function(flag), description = trigger_flag_descriptions.get(flag, "")))
    # Animation panel: the game's flags for the object's animations (SW_RACER_RE src/types_enums.h
    # swrModel_AnimationFlags, src/Swr/swrModel.c swrModel_LoadAnimation)
    bpy.types.Object.anim_loop = bpy.props.BoolProperty(name="Loop", get=get_anim_loop, set=set_anim_loop, description="Start the animation over when it reaches its end (flag 0x10). Off: it plays once and stops. Stored as Cycles modifiers on the object's curves, so Blender's timeline loops it too")
    bpy.types.Object.anim_loop_transition = bpy.props.BoolProperty(name="Smooth Wrap", default=False, description="Flag 0x40: when it loops, blend back to the start instead of jumping. Only the game's code gives the blend a speed; set in a file, the animation freezes at its first loop (tested in game). Kept for imports")
    bpy.types.Object.anim_loop_length = bpy.props.FloatProperty(name="Loop Length", default=0.0, min=0.0, soft_max=60.0, unit='TIME_ABSOLUTE', precision=3, description="Seconds before the animation starts over. 0, or anything shorter than the keys: right after the last key. Longer holds the last pose until then (stock puppets share one length across their limbs)")
    bpy.types.Object.swr_node_type = bpy.props.EnumProperty(name="Node Type", items=NODE_TYPE_ITEMS, get=get_node_type, set=set_node_type, description="What kind of node this empty exports as")
    bpy.types.Object.swr_selected_child = bpy.props.IntProperty(name="Selected Child", min=-2, get=custom_getter('selected_child', 0), set=custom_setter('selected_child'), description="Which child the selector draws: its number (0 is the first), -1 for all of them, -2 for none")
    bpy.types.Object.swr_lod_distances = bpy.props.FloatVectorProperty(name="LOD Distances", size=8, get=get_lod_distances, set=set_lod_distances, description="Where each child takes over, by distance from the camera: child 1 from the second value, and so on. The first value is 0, and -1 ends the list")
    bpy.types.Object.swr_face_camera = bpy.props.BoolProperty(name="Face Camera", get=lambda self: bool(self.get('track_position', 0)), set=lambda self, v: self.__setitem__('track_position', 1 if v else 0), description="Turn to face the camera (a billboard)")
    bpy.types.Object.swr_follow_model = bpy.props.BoolProperty(name="Follow Model", get=lambda self: bool(self.get('follow_position', 0)), set=lambda self, v: self.__setitem__('follow_position', 1 if v else 0), description="Move with the model's position (stock sky domes and pod binders)")
    bpy.types.Object.target = bpy.props.PointerProperty(type=bpy.types.Object, name="Target", description="The object the trigger acts on (e.g. the door it opens or the model it animates)")
   
    # MARK: UI State
    
    # visuals
    bpy.types.Scene.visible = bpy.props.BoolProperty(name = 'Visible', update = update_selected('visible'), default = False, description = "The selected meshes are drawn in game. In a track, a mesh that is neither Visible nor Collidable exports as both; in other models, as Visible")
    
    bpy.types.Scene.texture = bpy.props.PointerProperty(type = bpy.types.Image, name="Texture", description="The selected meshes' texture. Exported at up to 128x128", update= update_selected("texture", update_mat = True, update_tex = True))
    bpy.types.Scene.material_color = bpy.props.FloatVectorProperty(name = 'Color', subtype='COLOR', size = 4, default=(1.0, 1.0, 1.0, 1.0), min=0.0, max=1.0, description="Set base material color", update =update_selected("material_color", update_mat = True))
    bpy.types.Scene.blend_mode = bpy.props.EnumProperty(name = 'Blend Mode', items = SCENE_BLEND_MODE_ITEMS, get = get_scene_blend_mode, set = set_scene_blend_mode, description = "How the game draws the selected meshes: a preset copied from stock materials")
    bpy.types.Scene.use_backface_culling = bpy.props.BoolProperty(name = 'Backface Culling', default = False, update = update_selected("use_backface_culling", update_mat = True), description = "Hide faces seen from behind")
    bpy.types.Scene.scroll_x = bpy.props.FloatProperty(name = 'Scroll X', default = 0.0, update = update_selected("scroll_x", update_mat = True), description = "Scroll the texture along X: seconds per full scroll, negative for the other direction, 0 for none")
    bpy.types.Scene.scroll_y = bpy.props.FloatProperty(name = 'Scroll Y', default = 0.0, update = update_selected("scroll_y", update_mat = True), description = "Scroll the texture along Y: seconds per full scroll, negative for the other direction, 0 for none")
    bpy.types.Scene.flip_x = bpy.props.BoolProperty(name = 'Mirror Y', default = False, update = update_selected("flip_x", update_mat = True), description = "Repeat the texture mirrored along Y (V) instead of tiling it. Stored as flip_x for older files")
    bpy.types.Scene.flip_y = bpy.props.BoolProperty(name = 'Mirror X', default = False, update = update_selected("flip_y", update_mat = True), description = "Repeat the texture mirrored along X (U) instead of tiling it. Stored as flip_y for older files")
    bpy.types.Scene.clip_x = bpy.props.BoolProperty(name = 'Clip Y', default = False, update = update_selected("clip_x", update_mat = True), description = "Stretch the texture's edge pixels along Y (V) instead of repeating it. Stored as clip_x for older files")
    bpy.types.Scene.clip_y = bpy.props.BoolProperty(name = 'Clip X', default = False, update = update_selected("clip_y", update_mat = True), description = "Stretch the texture's edge pixels along X (U) instead of repeating it. Stored as clip_y for older files")
    
    bpy.types.Scene.light_falloff = bpy.props.FloatProperty(name = 'Falloff', description = "How fast point lights fade with distance when baking (the power of the distance)", min=0.0, max=10.0,update =save_settings, default=get_setting('light_falloff', 1.0))
    bpy.types.Scene.ambient_light = bpy.props.FloatVectorProperty(name = 'Ambient Light', subtype='COLOR', min=0.0, max=1.0, description="The color added everywhere when baking, so unlit areas are not black", update =save_settings, default=get_setting('ambient_light', (1.0, 1.0, 1.0)))
    bpy.types.Scene.ambient_light_intensity = bpy.props.FloatProperty(name = 'Ambient Strength', description = "How strong the ambient light is when baking", min=0.0, max=1.0, update =save_settings, default=get_setting('ambient_light_intensity', 0.1))
    
    # collision
    bpy.types.Scene.collision_visible = bpy.props.BoolProperty(name = 'Show Collision', update =UpdateVisibleSelectable, default=True, description = "Show or hide every collidable mesh in the viewport (does not change the export)")
    bpy.types.Scene.collision_selectable = bpy.props.BoolProperty(name = 'Select Collision', update =UpdateVisibleSelectable, default=True, description = "Make every collidable mesh selectable or unselectable in the viewport")
    bpy.types.Scene.visuals_visible = bpy.props.BoolProperty(name = 'Show Visuals', update =UpdateVisibleSelectable, default=True, description = "Show or hide every visible mesh in the viewport (does not change the export)")
    bpy.types.Scene.visuals_selectable = bpy.props.BoolProperty(name = 'Select Visuals', update =UpdateVisibleSelectable, default=True, description = "Make every visible mesh selectable or unselectable in the viewport")
    
    bpy.types.Scene.collidable = bpy.props.BoolProperty(name = 'Collidable', update = update_selected('collidable'), default = False, description = "Pods collide with the selected meshes in game. In a track, a mesh that is neither Visible nor Collidable exports as both; in other models, as Visible")
    bpy.types.Scene.collision_data = bpy.props.BoolProperty(name ='Collision Data', update = update_selected('collision_data'), default = False, description = "Give the selected collision meshes surface flags, fog, pod lighting, load triggers and event triggers")
    
    # terrain
    # What each surface flag does, from the decomp (SW_RACER_RE src/Swr/swrRace.c,
    # swrRace_UpdateSurfaceTag) and the museum_surfaces measurements (levels/README.md).
    # Flags with no known reader in the decomp say so.
    surface_flag_descriptions = {
        'ZOn': "Zero-g: the pod floats free of the ground until it touches a ZOff surface",
        'ZOff': "Ends zero-g (ZOn)",
        'Fast': "Speed boost (eases toward +200 speed)",
        'Slow': "Slows the pod (speed x0.75)",
        'Swst': "Heavy slowdown: speed eases toward x0.1 and boost is cancelled. Not a start line",
        'Slip': "Slippery: grip x0.2",
        'Dust': "Dust surface (effect not yet traced in the decomp)",
        'Snow': "Snow surface (effect not yet traced in the decomp)",
        'Wet': "Wet surface (effect not yet traced in the decomp)",
        'Ruff': "Rough surface (effect not yet traced in the decomp)",
        'Swmp': "Swamp: marks the pod as on swamp",
        'NSnw': "No snow (effect not yet traced in the decomp)",
        'Mirr': "Mirror: the surface reflects the pod (only with reflections turned on)",
        'Lava': "Lava: cools the engines (heat drops)",
        'Fall': "Fall: the pod respawns once it is within 30 units of this surface",
        'Soft': "Soft: marks the pod as on a soft surface",
        'NRsp': "No respawn (effect not yet traced in the decomp)",
        'Flat': "Flat: AI pods only, has no effect on the player",
        'Side': "Side: AI pods (and the autopilot) tilt fully onto their side while on this surface",
    }
    for flag in dir(SurfaceEnum):
        if not flag.startswith("__"):
            setattr(bpy.types.Scene, flag, bpy.props.BoolProperty(name = flag, default=False, update = update_selected(flag), description = surface_flag_descriptions.get(flag, f"Terrain surface flag: {flag}")))
    
    bpy.types.Scene.magnet = bpy.props.BoolProperty(name ='Magnet', default=False, update = update_selected("magnet"), description = "Magnet: gravity follows the surface, so the pod sticks to walls, loops and ceilings")
    bpy.types.Scene.strict_spline = bpy.props.BoolProperty(name ='Spline Fork', default=False, update = update_selected("strict_spline"), description = "Behavior bit 0x8: the mesh is shared between spline branches, which pauses spline progress on it. The game also sets this itself at load")
    bpy.types.Scene.elevation = bpy.props.BoolProperty(name ='Full Raycast', default=False, update = update_selected("elevation"), description = "Full raycast: test the pod's ground against this mesh every frame instead of the track cached at load. Needed for collision that moves (animated platforms)")
    
    # lighting
    bpy.types.Scene.lighting_light = bpy.props.PointerProperty(type=bpy.types.Light, name="Light", update = update_selected("lighting_light"), description = "The light that lights the pod while it is on the selected meshes (its color and position are exported)")
    bpy.types.Scene.lighting_color = bpy.props.FloatVectorProperty(name="Ambient Color", subtype='COLOR', size=3, default=(1.0, 1.0, 1.0), min=0, max=1, description="The pod's ambient light color while it is on the selected meshes", update = update_selected("lighting_color"))
    bpy.types.Scene.lighting_invert = bpy.props.BoolProperty(name = 'Point Light', default=False, update = update_selected("lighting_invert"), description = "Light flag 0x4: the game reads the light vector as a position (a point light) instead of a direction")
    bpy.types.Scene.lighting_flicker = bpy.props.BoolProperty(name = 'Flicker', default=False, update = update_selected("lighting_flicker"), description = "Light flag 0x8, named flicker (its effect is not yet traced in the decomp)")
    bpy.types.Scene.lighting_persistent = bpy.props.BoolProperty(name = 'Persist', default=False, update = update_selected("lighting_persistent"), description = "Light flag 0x10, named persist (its effect is not yet traced in the decomp)")
    
    # fog
    bpy.types.Scene.fog_color = bpy.props.FloatVectorProperty(name="Fog Color", subtype='COLOR', size=3, default=(1.0, 1.0, 1.0), min=0, max=1, description="Fog color. It is also the background (sky) color", update = update_selected("fog_color"))
    bpy.types.Scene.fog_range_update = bpy.props.BoolProperty(name = 'Set Draw Distance', default=False, update = update_selected("fog_range_update"), description = "When the pod touches the selected meshes, set the draw distance")
    bpy.types.Scene.fog_color_update = bpy.props.BoolProperty(name = 'Set Fog', default=False, update = update_selected("fog_color_update"), description = "When the pod touches the selected meshes, turn fog on with this color and start")
    bpy.types.Scene.fog_min = bpy.props.IntProperty(name="Fog Start", default=1000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Where fog starts. Not a plain distance: the game uses it as an N64 fog value and clamps it at 996", update = update_selected("fog_min"))
    bpy.types.Scene.fog_max = bpy.props.IntProperty(name="Distance", default=30000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Draw distance: fog is fully opaque here and nothing beyond is drawn", subtype = 'DISTANCE', update = update_selected("fog_max"))
    bpy.types.Scene.fog_clear = bpy.props.BoolProperty(name = 'Clear Fog', default=False, update = update_selected("fog_clear"), description = "When the pod touches the selected meshes, turn fog off (writes a fog start of 0)")
    bpy.types.Scene.skybox_show = bpy.props.BoolProperty(name ='Show Skybox', default=False, update = update_selected("skybox_show"), description = "When the pod touches the selected meshes, show the skybox")
    bpy.types.Scene.skybox_hide = bpy.props.BoolProperty(name ='Hide Skybox', default=False, update = update_selected("skybox_hide"), description = "When the pod touches the selected meshes, hide the skybox")
    
    # trigger
    bpy.types.Scene.target = bpy.props.PointerProperty(type=bpy.types.Object, update = update_selected('target'))
    
    # view layer
    bpy.utils.register_class(MY_ListItem)
    bpy.types.Scene.load_trigger = bpy.props.CollectionProperty(type=MY_ListItem)
    bpy.types.Scene.load_trigger_index = bpy.props.IntProperty(default=0)
    
def unregister():
    for name in ('flipbook_frames', 'flipbook_index', 'flipbook_frame_time', 'flipbook_loop'):
        delattr(bpy.types.Material, name)
    bpy.utils.unregister_class(SWR_FlipbookFrame)
    bpy.utils.unregister_class(MY_ListItem)
    del bpy.types.Scene.import_folder
    del bpy.types.Scene.import_type
    del bpy.types.Scene.new_type
    del bpy.types.Scene.import_model
    del bpy.types.Scene.export_folder
    del bpy.types.Scene.is_export_model
    del bpy.types.Scene.is_export_texture
    del bpy.types.Scene.is_export_spline
    del bpy.types.Scene.is_export_separate
    del bpy.types.Scene.is_export_debug
    del bpy.types.Scene.collision_visible
    del bpy.types.Scene.collision_selectable
    del bpy.types.Scene.visuals_visible
    del bpy.types.Scene.visuals_selectable
    del bpy.types.Scene.visible
    del bpy.types.Scene.collidable
    
    del bpy.types.Collection.export_model
    del bpy.types.Collection.export_type
    del bpy.types.Collection.collection_type
    
    del bpy.types.Object.id
    
    del bpy.types.Object.visible
    del bpy.types.Object.collidable
    del bpy.types.Object.collision_data
    
    for flag in dir(SurfaceEnum):
        if not flag.startswith("__"):
            delattr(bpy.types.Object, flag)
            
    del bpy.types.Object.magnet
    del bpy.types.Object.strict_spline
    del bpy.types.Object.elevation
    
    del bpy.types.Object.lighting_light
    del bpy.types.Object.lighting_color
    del bpy.types.Object.lighting_invert
    del bpy.types.Object.lighting_flicker
    del bpy.types.Object.lighting_persistent
    
    del bpy.types.Object.fog_color_update
    del bpy.types.Object.fog_color
    del bpy.types.Object.fog_range_update
    del bpy.types.Object.fog_min
    del bpy.types.Object.fog_max
    del bpy.types.Object.fog_clear
    del bpy.types.Object.skybox_show
    del bpy.types.Object.skybox_hide

    del bpy.types.Object.load_trigger
    del bpy.types.Scene.load_trigger
    del bpy.types.Scene.load_trigger_index