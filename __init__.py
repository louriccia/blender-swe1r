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

bl_info = {
    "name": "SWE1R Import/Export",
    "author": "LightningPirate",
    "blender": (4, 0, 0),
    "version": (0, 9, 0),
    "location": "View3D > Tool Shelf > SWE1R Import/Export",
    "warning": "",
    "category": "Generic",
}

if "bpy" in locals():
    import importlib
    importlib.reload(constants)
    importlib.reload(panels)
    importlib.reload(operators)
    importlib.reload(swr_import)
    importlib.reload(swr_export)
    importlib.reload(popup)
    importlib.reload(swe1r)
    importlib.reload(utils)
    importlib.reload(props)
else:
    import bpy
    from . import constants
    from . import swr_import
    from . import swr_export
    from . import popup
    from . import swe1r
    from . import panels
    from . import operators
    from . import utils
    from . import props

import bpy



def register():
 
    bpy.types.Scene.import_folder = bpy.props.StringProperty(subtype='DIR_PATH', update=utils.save_settings, default =utils.get_setting('import_folder', ""), description="Select the lev01 folder in Star Wars Episode I Racer/data/lev01 (or any folder containing the .bin files)")
    bpy.types.Scene.import_type = bpy.props.EnumProperty(
        items=utils.model_types,
        name="Model Type",
        description="Filter model selection by model type",
        default=utils.get_setting('import_type', 0), 
        update=utils.update_model_dropdown
    )
    
    bpy.types.Scene.new_type = bpy.props.EnumProperty(
        items=utils.model_types[1:],
        name="New Model Type",
        description="Create a new template for the selected model type",
        default=utils.get_setting('new_type', 0)
    )
    
    import_items = [(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(swe1r.model_list.model_list) if model['extension'] == utils.model_types[int(utils.get_setting('import_type', 0))][1]]
    if not len(import_items):
        import_items = [(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(swe1r.model_list.model_list)]
    bpy.types.Scene.import_model = bpy.props.EnumProperty(
        items=import_items,
        name="Model",
        description="Select a model to import",
        default=0, #utils.get_setting('import_model', 0), 
        update=utils.save_settings
    )
    bpy.types.Scene.export_folder = bpy.props.StringProperty(subtype='DIR_PATH', update=utils.save_settings, default=utils.get_setting('export_folder', ""), description="Select the lev01 folder in Star Wars Episode I Racer/data/lev01 (or any folder you wish to export to)")
    bpy.types.Scene.is_export_model = bpy.props.BoolProperty(name="Model", update=utils.save_settings, default=utils.get_setting('is_export_model', True))
    bpy.types.Scene.is_export_texture = bpy.props.BoolProperty(name="Texture", update=utils.save_settings, default=utils.get_setting('is_export_texture', True))
    bpy.types.Scene.is_export_spline = bpy.props.BoolProperty(name="Spline", update=utils.save_settings, default=utils.get_setting('is_export_spline', True))
    bpy.types.Scene.is_export_separate = bpy.props.BoolProperty(name ="Separate", update =utils.save_settings, default=utils.get_setting('export_separate', False), description = "Save a copy of the exported elements as individual .bin files")
    
    bpy.types.Collection.export_model = bpy.props.EnumProperty(
        items = utils.export_model_items,
        name = "Model",
        description = "The model this collection will be exported as",
        default = 0
    )
    bpy.types.Collection.export_type = bpy.props.EnumProperty(
        items=[i for i in utils.model_types[1:]],
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
   
    #obj state
    bpy.types.Object.id = bpy.props.StringProperty(name = "id", default = "")
    
    bpy.types.Scene.visible = bpy.props.BoolProperty(name = 'visible', update = utils.update_selected('visible'), default = False)
    bpy.types.Object.visible = bpy.props.BoolProperty(name ='visible', default=False)
    bpy.types.Scene.collidable = bpy.props.BoolProperty(name = 'collidable', update = utils.update_selected('collidable'), default = False)
    bpy.types.Object.collidable = bpy.props.BoolProperty(name ='collidable', default=False)
    bpy.types.Scene.collision_data = bpy.props.BoolProperty(name ='collision_data', update = utils.update_selected('collision_data'), default = False)
    bpy.types.Object.collision_data = bpy.props.BoolProperty(name ='collision_data', default=False)
    
    for flag in dir(swe1r.modelblock.SurfaceEnum):
        if not flag.startswith("__"):
            setattr(bpy.types.Scene, flag, bpy.props.BoolProperty(name = flag, default=False, update = utils.update_selected(flag)))
            setattr(bpy.types.Object, flag, bpy.props.BoolProperty(name = flag, default=False))
    bpy.types.Scene.magnet = bpy.props.BoolProperty(name ='magnet', default=False, update = utils.update_selected("magnet"), description = "Disable tilting and climbing")
    bpy.types.Object.magnet = bpy.props.BoolProperty(name ='magnet', default=False)
    bpy.types.Scene.strict_spline = bpy.props.BoolProperty(name ='strict_spline', default=False, update = utils.update_selected("strict_spline"), description = "Make lap progress stricter")
    bpy.types.Object.strict_spline = bpy.props.BoolProperty(name ='strict_spline', default=False)
    bpy.types.Scene.elevation = bpy.props.BoolProperty(name ='elevation', default=False, update = utils.update_selected("elevation"), description = "Prevent pod getting stuck on overlapping collisions (MFG)")
    bpy.types.Object.elevation = bpy.props.BoolProperty(name ='elevation', default=False)
    
    bpy.types.Scene.lighting_light = bpy.props.PointerProperty(type=bpy.types.Light, name="lighting_light", update = utils.update_selected("lighting_light"))
    bpy.types.Object.lighting_light = bpy.props.PointerProperty(type=bpy.types.Light, name="lighting_light")
    bpy.types.Scene.lighting_color = bpy.props.FloatVectorProperty(name="lighting_color", subtype='COLOR', size=3, default=(0.0, 0.0, 0.0), min=0, max=1, description="Ambient Color", update = utils.update_selected("lighting_color"))
    bpy.types.Object.lighting_color = bpy.props.FloatVectorProperty(name="lighting_color", subtype='COLOR', size=3, default=(0.0, 0.0, 0.0), min=0, max=1, description="Ambient Color")
    bpy.types.Scene.lighting_invert = bpy.props.BoolProperty(name = 'lighting_invert', default=False, update = utils.update_selected("lighting_invert"))
    bpy.types.Object.lighting_invert = bpy.props.BoolProperty(name = 'lighting_invert', default=False)
    bpy.types.Scene.lighting_flicker = bpy.props.BoolProperty(name = 'lighting_flicker', default=False, update = utils.update_selected("lighting_flicker"))
    bpy.types.Object.lighting_flicker = bpy.props.BoolProperty(name = 'lighting_flicker', default=False)
    bpy.types.Scene.lighting_persistent = bpy.props.BoolProperty(name = 'lighting_persistent', default=False, update = utils.update_selected("lighting_persistent"))
    bpy.types.Object.lighting_persistent = bpy.props.BoolProperty(name = 'lighting_persistent', default=False)
    
    bpy.types.Scene.fog_color_update = bpy.props.BoolProperty(name = 'fog_color_update', default=False, update = utils.update_selected("fog_color_update"))
    bpy.types.Object.fog_color_update = bpy.props.BoolProperty(name = 'fog_color_update', default=False)
    bpy.types.Scene.fog_color = bpy.props.FloatVectorProperty(name="fog_color", subtype='COLOR', size=3, default=(0.0, 0.0, 0.0), min=0, max=1, description="Fog color", update = utils.update_selected("fog_color"))
    bpy.types.Object.fog_color = bpy.props.FloatVectorProperty(name="fog_color", subtype='COLOR', size=3, default=(0.0, 0.0, 0.0), min=0, max=1, description="Fog color")
    bpy.types.Scene.fog_range_update = bpy.props.BoolProperty(name = 'fog_range_update', default=False, update = utils.update_selected("fog_range_update"))
    bpy.types.Object.fog_range_update = bpy.props.BoolProperty(name = 'fog_range_update', default=False)
    bpy.types.Scene.fog_min = bpy.props.IntProperty(name="fog_min", default=1000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Fog min", subtype = 'DISTANCE', update = utils.update_selected("fog_min"))
    bpy.types.Object.fog_min = bpy.props.IntProperty(name="fog_min", default=1000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Fog min", subtype = 'DISTANCE')
    bpy.types.Scene.fog_max = bpy.props.IntProperty(name="fog_max", default=5000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Fog min", subtype = 'DISTANCE', update = utils.update_selected("fog_max"))
    bpy.types.Object.fog_max = bpy.props.IntProperty(name="fog_max", default=5000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Fog min", subtype = 'DISTANCE')
    bpy.types.Scene.fog_clear = bpy.props.BoolProperty(name = 'fog_clear', default=False, update = utils.update_selected("fog_clear"))
    bpy.types.Object.fog_clear = bpy.props.BoolProperty(name = 'fog_clear', default=False)
    bpy.types.Scene.skybox_show = bpy.props.BoolProperty(name ='skybox_show', default=False, update = utils.update_selected("skybox_show"))
    bpy.types.Object.skybox_show = bpy.props.BoolProperty(name ='skybox_show', default=False)
    bpy.types.Scene.skybox_hide = bpy.props.BoolProperty(name ='skybox_hide', default=False, update = utils.update_selected("skybox_hide"))
    bpy.types.Object.skybox_hide = bpy.props.BoolProperty(name ='skybox_hide', default=False)
   
    bpy.types.Object.load_trigger = bpy.props.EnumProperty(
        name="View Layer",
        items= utils.populate_enum
    )
    
    #material state
    bpy.types.Scene.texture = bpy.props.PointerProperty(type = bpy.types.Image, name="texture", update = utils.update_selected("texture", update_mat = True, update_tex = True))
    bpy.types.Scene.use_backface_culling = bpy.props.BoolProperty(name = 'use_backface_culling', default = False, update = utils.update_selected("use_backface_culling", update_mat = True))
    bpy.types.Scene.scroll_x = bpy.props.FloatProperty(name = 'scroll_x', default = 0.0, update = utils.update_selected("scroll_x", update_mat = True))
    bpy.types.Scene.scroll_y = bpy.props.FloatProperty(name = 'scroll_y', default = 0.0, update = utils.update_selected("scroll_y", update_mat = True))
    bpy.types.Scene.flip_x = bpy.props.BoolProperty(name = 'flip_x', default = False, update = utils.update_selected("flip_x", update_mat = True))
    bpy.types.Scene.flip_y = bpy.props.BoolProperty(name = 'flip_y', default = False, update = utils.update_selected("flip_y", update_mat = True))
    bpy.types.Material.scroll_x = bpy.props.FloatProperty(name = 'scroll_x', default = 0.0)
    bpy.types.Material.scroll_y = bpy.props.FloatProperty(name = 'scroll_y', default = 0.0)
    bpy.types.Material.flip_x = bpy.props.BoolProperty(name = 'flip_x', default = False)
    bpy.types.Material.flip_y = bpy.props.BoolProperty(name = 'flip_y', default = False)
    bpy.types.Scene.transparent = bpy.props.BoolProperty(name = 'transparent', default = False, update = utils.update_selected("transparent", update_mat = True))
    bpy.types.Material.transparent = bpy.props.BoolProperty(name = 'transparent', default = False)
    
    #light state
    bpy.types.Light.LStr = bpy.props.BoolProperty(name = 'LStr', default=False, update = utils.create_update_function("LStr"))
    
    #trigger state
    bpy.types.Object.trigger_id = bpy.props.IntProperty(name='trigger_id', update = utils.create_update_function("trigger_id"))
    bpy.types.Object.trigger_settings = bpy.props.IntProperty(name='trigger_settings', update = utils.create_update_function("trigger_settings"))
    for flag in dir(swe1r.modelblock.TriggerFlagEnum):
        if not flag.startswith("__"):
            setattr(bpy.types.Object, flag, bpy.props.BoolProperty(name = flag, default=False, update = utils.create_update_function(flag)))
    bpy.types.Scene.target = bpy.props.PointerProperty(type=bpy.types.Object, update = utils.update_selected('target'))
    bpy.types.Object.target = bpy.props.PointerProperty(type=bpy.types.Object)
   
    #ui
    bpy.types.Scene.collision_visible = bpy.props.BoolProperty(name = 'collision_visible', update =utils.UpdateVisibleSelectable, default=True, description = "Show/hide all collidable mesh")
    bpy.types.Scene.collision_selectable = bpy.props.BoolProperty(name = 'collision_selectable', update =utils.UpdateVisibleSelectable, default=True, description = "Set all collidable mesh as selectable/unselectable")
    bpy.types.Scene.visuals_visible = bpy.props.BoolProperty(name = 'visuals_visible', update =utils.UpdateVisibleSelectable, default=True, description = "Set all visible mesh as selectable/unselectable")
    bpy.types.Scene.visuals_selectable = bpy.props.BoolProperty(name = 'visuals_selectable', update =utils.UpdateVisibleSelectable, default=True, description = "Set all visible mesh as selectable/unselectable")
    
    bpy.types.Scene.light_falloff = bpy.props.FloatProperty(name = 'falloff', min=0.0, max=10.0, update =utils.save_settings, default=utils.get_setting('light_falloff', 1.0))
    bpy.types.Scene.ambient_light = bpy.props.FloatVectorProperty(name = 'Ambient Light', subtype='COLOR', min=0.0, max=1.0, description="Tweak visibility and shading in dark areas", update =utils.save_settings, default=utils.get_setting('ambient_light', (0.0, 0.0, 0.0)))
    bpy.types.Scene.ambient_light_intensity = bpy.props.FloatProperty(name = 'ambient_light_intensity', min=0.0, max=1.0, update =utils.save_settings, default=utils.get_setting('ambient_light_intensity', 0.1))
    
    bpy.types.Scene.flags_expanded = bpy.props.BoolProperty(name = 'flags_expanded', update=utils.save_settings, default=utils.get_setting('flags_expanded', False))
    bpy.types.Scene.fog_expanded = bpy.props.BoolProperty(name = 'fog_expanded', update=utils.save_settings, default=utils.get_setting('fog_expanded', False))
    bpy.types.Scene.lighting_expanded = bpy.props.BoolProperty(name = 'lighting_expanded', update=utils.save_settings, default=utils.get_setting('lighting_expanded', False))
    bpy.types.Scene.trigger_expanded = bpy.props.BoolProperty(name = 'trigger_expanded', update=utils.save_settings, default=utils.get_setting('trigger_expanded', False))
    bpy.types.Scene.lights_expanded = bpy.props.BoolProperty(name = 'lights_expanded', update=utils.save_settings, default=utils.get_setting('lights_expanded', False))
    bpy.types.Scene.textures_expanded = bpy.props.BoolProperty(name = 'texture_expanded', update=utils.save_settings, default=utils.get_setting('texture_expanded', False))
    bpy.types.Scene.new_expanded = bpy.props.BoolProperty(name = 'new_expanded', update=utils.save_settings, default=utils.get_setting('new_expanded', False))
    bpy.types.Scene.visuals_expanded = bpy.props.BoolProperty(name = 'visuals_expanded', update=utils.save_settings, default=utils.get_setting('visuals_expanded', False))
    bpy.types.Scene.collision_expanded = bpy.props.BoolProperty(name = 'collision_expanded', update=utils.save_settings, default=utils.get_setting('collision_expanded', False))
    
    bpy.types.Scene.import_progress = bpy.props.FloatProperty(name="Import Progress", default=0.0, min=0.0, max=1.0)
    bpy.types.Scene.import_status = bpy.props.StringProperty(name="Import Status", default="")
    bpy.types.Scene.export_progress = bpy.props.FloatProperty(name="Export Progress", default=0.0, min=0.0, max=1.0)
    bpy.types.Scene.export_status = bpy.props.StringProperty(name="Export Status", default="")
    
    bpy.types.Scene.indeterminates = bpy.props.StringProperty(name = "Indeterminates", default = "")
    
    operators.register()
    panels.register()
    
def unregister():
 
    panels.unregister()
    operators.unregister()
    props.unregister

if __name__ == "__main__":
    register()
