import bpy
from .utils import save_settings, get_setting, model_types, update_model_dropdown, export_model_items, update_selected, populate_enum, create_update_function, UpdateVisibleSelectable
from .swe1r.model_list import model_list
from .swe1r.modelblock import SurfaceEnum, TriggerFlagEnum

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
    bpy.types.Scene.import_folder = bpy.props.StringProperty(subtype='DIR_PATH', update=save_settings, default = get_setting('import_folder', ""), description="Select the lev01 folder in Star Wars Episode I Racer/data/lev01 (or any folder containing the .bin files)")
    bpy.types.Scene.import_type = bpy.props.EnumProperty(
        items=model_types,
        name="Model Type",
        description="Filter model selection by model type",
        default=get_setting('import_type', 0), 
        update=update_model_dropdown
    )
    
    bpy.types.Scene.new_type = bpy.props.EnumProperty(
        items=model_types[1:],
        name="New Model Type",
        description="Create a new template for the selected model type",
        default=get_setting('new_type', 0)
    )
    
    import_items = [(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(model_list) if model['extension'] == model_types[int(get_setting('import_type', 0))][1]]
    if not len(import_items):
        import_items = [(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(model_list)]
    import_items.append(("-1", "All", "Import all models of this type"))
    bpy.types.Scene.import_model = bpy.props.EnumProperty(
        items=import_items,
        name="Model",
        description="Select a model to import",
        default=0, #get_setting('import_model', 0), 
        update=save_settings
    )
    bpy.types.Scene.export_folder = bpy.props.StringProperty(subtype='DIR_PATH', update=save_settings, default=get_setting('export_folder', ""), description="Select the lev01 folder in Star Wars Episode I Racer/data/lev01 (or any folder you wish to export to)")
    bpy.types.Scene.is_export_model = bpy.props.BoolProperty(name="Model", update=save_settings, default=get_setting('is_export_model', True))
    bpy.types.Scene.is_export_texture = bpy.props.BoolProperty(name="Texture", update=save_settings, default=get_setting('is_export_texture', True))
    bpy.types.Scene.is_export_spline = bpy.props.BoolProperty(name="Spline", update=save_settings, default=get_setting('is_export_spline', True))
    bpy.types.Scene.is_export_separate = bpy.props.BoolProperty(name ="Separate", update =save_settings, default=get_setting('export_separate', False), description = "Save a copy of the exported elements as individual .bin files")
    
    bpy.types.Scene.flags_expanded = bpy.props.BoolProperty(name = 'flags_expanded', update=save_settings, default=get_setting('flags_expanded', False))
    bpy.types.Scene.fog_expanded = bpy.props.BoolProperty(name = 'fog_expanded', update=save_settings, default=get_setting('fog_expanded', False))
    bpy.types.Scene.lighting_expanded = bpy.props.BoolProperty(name = 'lighting_expanded', update=save_settings, default=get_setting('lighting_expanded', False))
    bpy.types.Scene.trigger_expanded = bpy.props.BoolProperty(name = 'trigger_expanded', update=save_settings, default=get_setting('trigger_expanded', False))
    bpy.types.Scene.lights_expanded = bpy.props.BoolProperty(name = 'lights_expanded', update=save_settings, default=get_setting('lights_expanded', False))
    bpy.types.Scene.textures_expanded = bpy.props.BoolProperty(name = 'texture_expanded', update=save_settings, default=get_setting('texture_expanded', False))
    bpy.types.Scene.new_expanded = bpy.props.BoolProperty(name = 'new_expanded', update=save_settings, default=get_setting('new_expanded', False))
    bpy.types.Scene.visuals_expanded = bpy.props.BoolProperty(name = 'visuals_expanded', update=save_settings, default=get_setting('visuals_expanded', False))
    bpy.types.Scene.collision_expanded = bpy.props.BoolProperty(name = 'collision_expanded', update=save_settings, default=get_setting('collision_expanded', False))
    
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
        description = "The model this collection will be exported as",
        default = 0
    )
    
    bpy.types.Collection.export_type = bpy.props.EnumProperty(
        items=[i for i in model_types[1:]],
        name="Model Type",
        description="The type of model to export",
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
            ("5", "Cable", "The Podd's Cable")
        ],
        name = "Collection Type",
        description="The type of collection",
        default = "NONE"
    )
   
    # MARK: obj state
    bpy.types.Object.id = bpy.props.StringProperty(name = "id", default = "")
    
    bpy.types.Object.visible = bpy.props.BoolProperty(name ='visible', default=False)
    bpy.types.Object.collidable = bpy.props.BoolProperty(name ='collidable', default=False)
    bpy.types.Object.collision_data = bpy.props.BoolProperty(name ='collision_data', default=False)
    
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
    bpy.types.Object.fog_min = bpy.props.IntProperty(name="fog_min", default=1000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Fog min", subtype = 'DISTANCE')
    bpy.types.Object.fog_max = bpy.props.IntProperty(name="fog_max", default=5000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Fog min", subtype = 'DISTANCE')
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
    bpy.types.Material.transparent = bpy.props.BoolProperty(name = 'transparent', default = False)
    bpy.types.Material.material_color = bpy.props.FloatVectorProperty(name = 'Color', subtype='COLOR', size = 4, min=0.0, max=1.0)
    
    
    #light state
    bpy.types.Light.LStr = bpy.props.BoolProperty(name = 'LStr', default=False, update = create_update_function("LStr"))
    
    # MARK: Trigger State
    bpy.types.Object.trigger_id = bpy.props.IntProperty(name='trigger_id', update = create_update_function("trigger_id"))
    bpy.types.Object.trigger_settings = bpy.props.IntProperty(name='trigger_settings', update = create_update_function("trigger_settings"))
    for flag in dir(TriggerFlagEnum):
        if not flag.startswith("__"):
            setattr(bpy.types.Object, flag, bpy.props.BoolProperty(name = flag, default=False, update = create_update_function(flag)))
    bpy.types.Object.target = bpy.props.PointerProperty(type=bpy.types.Object)
   
    # MARK: UI State
    
    # visuals
    bpy.types.Scene.visible = bpy.props.BoolProperty(name = 'visible', update = update_selected('visible'), default = False)
    
    bpy.types.Scene.texture = bpy.props.PointerProperty(type = bpy.types.Image, name="texture", update = update_selected("texture", update_mat = True, update_tex = True))
    bpy.types.Scene.material_color = bpy.props.FloatVectorProperty(name = 'Color', subtype='COLOR', size = 4, default=(1.0, 1.0, 1.0, 1.0), min=0.0, max=1.0, description="Set base material color", update =update_selected("material_color", update_mat = True))
    bpy.types.Scene.transparent = bpy.props.BoolProperty(name = 'transparent', default = False, update = update_selected("transparent", update_mat = True))
    bpy.types.Scene.use_backface_culling = bpy.props.BoolProperty(name = 'use_backface_culling', default = False, update = update_selected("use_backface_culling", update_mat = True))
    bpy.types.Scene.scroll_x = bpy.props.FloatProperty(name = 'scroll_x', default = 0.0, update = update_selected("scroll_x", update_mat = True))
    bpy.types.Scene.scroll_y = bpy.props.FloatProperty(name = 'scroll_y', default = 0.0, update = update_selected("scroll_y", update_mat = True))
    bpy.types.Scene.flip_x = bpy.props.BoolProperty(name = 'flip_x', default = False, update = update_selected("flip_x", update_mat = True))
    bpy.types.Scene.flip_y = bpy.props.BoolProperty(name = 'flip_y', default = False, update = update_selected("flip_y", update_mat = True))
    bpy.types.Scene.clip_x = bpy.props.BoolProperty(name = 'clip_x', default = False, update = update_selected("clip_x", update_mat = True))
    bpy.types.Scene.clip_y = bpy.props.BoolProperty(name = 'clip_y', default = False, update = update_selected("clip_y", update_mat = True))
    
    bpy.types.Scene.light_falloff = bpy.props.FloatProperty(name = 'falloff', min=0.0, max=10.0, update =save_settings, default=get_setting('light_falloff', 1.0))
    bpy.types.Scene.ambient_light = bpy.props.FloatVectorProperty(name = 'Ambient Light', subtype='COLOR', min=0.0, max=1.0, description="Tweak visibility and shading in dark areas", update =save_settings, default=get_setting('ambient_light', (1.0, 1.0, 1.0)))
    bpy.types.Scene.ambient_light_intensity = bpy.props.FloatProperty(name = 'ambient_light_intensity', min=0.0, max=1.0, update =save_settings, default=get_setting('ambient_light_intensity', 0.1))
    
    # collision
    bpy.types.Scene.collision_visible = bpy.props.BoolProperty(name = 'collision_visible', update =UpdateVisibleSelectable, default=True, description = "Show/hide all collidable mesh")
    bpy.types.Scene.collision_selectable = bpy.props.BoolProperty(name = 'collision_selectable', update =UpdateVisibleSelectable, default=True, description = "Set all collidable mesh as selectable/unselectable")
    bpy.types.Scene.visuals_visible = bpy.props.BoolProperty(name = 'visuals_visible', update =UpdateVisibleSelectable, default=True, description = "Set all visible mesh as selectable/unselectable")
    bpy.types.Scene.visuals_selectable = bpy.props.BoolProperty(name = 'visuals_selectable', update =UpdateVisibleSelectable, default=True, description = "Set all visible mesh as selectable/unselectable")
    
    bpy.types.Scene.collidable = bpy.props.BoolProperty(name = 'collidable', update = update_selected('collidable'), default = False)
    bpy.types.Scene.collision_data = bpy.props.BoolProperty(name ='collision_data', update = update_selected('collision_data'), default = False)
    
    # terrain
    for flag in dir(SurfaceEnum):
        if not flag.startswith("__"):
            setattr(bpy.types.Scene, flag, bpy.props.BoolProperty(name = flag, default=False, update = update_selected(flag)))
    
    bpy.types.Scene.magnet = bpy.props.BoolProperty(name ='magnet', default=False, update = update_selected("magnet"), description = "Disable tilting and climbing")
    bpy.types.Scene.strict_spline = bpy.props.BoolProperty(name ='strict_spline', default=False, update = update_selected("strict_spline"), description = "Make lap progress stricter")
    bpy.types.Scene.elevation = bpy.props.BoolProperty(name ='elevation', default=False, update = update_selected("elevation"), description = "Prevent pod getting stuck on overlapping collisions (MFG)")
    
    # lighting
    bpy.types.Scene.lighting_light = bpy.props.PointerProperty(type=bpy.types.Light, name="lighting_light", update = update_selected("lighting_light"))
    bpy.types.Scene.lighting_color = bpy.props.FloatVectorProperty(name="lighting_color", subtype='COLOR', size=3, default=(1.0, 1.0, 1.0), min=0, max=1, description="Ambient Color", update = update_selected("lighting_color"))
    bpy.types.Scene.lighting_invert = bpy.props.BoolProperty(name = 'lighting_invert', default=False, update = update_selected("lighting_invert"))
    bpy.types.Scene.lighting_flicker = bpy.props.BoolProperty(name = 'lighting_flicker', default=False, update = update_selected("lighting_flicker"))
    bpy.types.Scene.lighting_persistent = bpy.props.BoolProperty(name = 'lighting_persistent', default=False, update = update_selected("lighting_persistent"))
    
    # fog
    bpy.types.Scene.fog_color = bpy.props.FloatVectorProperty(name="fog_color", subtype='COLOR', size=3, default=(1.0, 1.0, 1.0), min=0, max=1, description="Fog color", update = update_selected("fog_color"))
    bpy.types.Scene.fog_range_update = bpy.props.BoolProperty(name = 'fog_range_update', default=False, update = update_selected("fog_range_update"))
    bpy.types.Scene.fog_color_update = bpy.props.BoolProperty(name = 'fog_color_update', default=False, update = update_selected("fog_color_update"))
    bpy.types.Scene.fog_min = bpy.props.IntProperty(name="fog_min", default=1000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Fog min", subtype = 'DISTANCE', update = update_selected("fog_min"))
    bpy.types.Scene.fog_max = bpy.props.IntProperty(name="fog_max", default=5000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Fog min", subtype = 'DISTANCE', update = update_selected("fog_max"))
    bpy.types.Scene.fog_clear = bpy.props.BoolProperty(name = 'fog_clear', default=False, update = update_selected("fog_clear"))
    bpy.types.Scene.skybox_show = bpy.props.BoolProperty(name ='skybox_show', default=False, update = update_selected("skybox_show"))
    bpy.types.Scene.skybox_hide = bpy.props.BoolProperty(name ='skybox_hide', default=False, update = update_selected("skybox_hide"))
    
    # trigger
    bpy.types.Scene.target = bpy.props.PointerProperty(type=bpy.types.Object, update = update_selected('target'))
    
    # view layer
    bpy.utils.register_class(MY_ListItem)
    bpy.types.Scene.load_trigger = bpy.props.CollectionProperty(type=MY_ListItem)
    bpy.types.Scene.load_trigger_index = bpy.props.IntProperty(default=0)
    
def unregister():
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
   
    bpy.types.Object.load_trigger = bpy.props.EnumProperty(
        name="View Layer",
        items= populate_enum
    )