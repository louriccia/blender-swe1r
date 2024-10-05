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
 
    bpy.types.Scene.import_folder = bpy.props.StringProperty(subtype='DIR_PATH', update=utils.save_settings, default =utils.get_setting('import_folder', ""), description="Select the lev01 folder (or any folder containing the .bin files)")
    bpy.types.Scene.import_type = bpy.props.EnumProperty(
        items=utils.model_types,
        name="Model Type",
        description="Select model type",
        default=utils.get_setting('import_type', 0), 
        update=utils.update_model_dropdown
    )
    import_items = [(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(swe1r.model_list.model_list) if model['extension'] == utils.model_types[int(utils.get_setting('import_type', 0))][1]]
    if not len(import_items):
        import_items = [(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(swe1r.model_list.model_list)]
    bpy.types.Scene.import_model = bpy.props.EnumProperty(
        items=import_items,
        name="Model",
        description="Select model",
        default=0, #utils.get_setting('import_model', 0), 
        update=utils.save_settings
    )
    bpy.types.Scene.export_folder = bpy.props.StringProperty(subtype='DIR_PATH', update=utils.save_settings, default=utils.get_setting('export_folder', ""), description="Select the lev01 folder (or any folder you wish to export to)")
    bpy.types.Scene.export_model = bpy.props.BoolProperty(name="Model", update=utils.save_settings, default=utils.get_setting('export_model', True))
    bpy.types.Scene.export_texture = bpy.props.BoolProperty(name="Texture", update=utils.save_settings, default=utils.get_setting('export_texture', True))
    bpy.types.Scene.export_spline = bpy.props.BoolProperty(name="Spline", update=utils.save_settings, default=utils.get_setting('export_spline', True))
    bpy.types.Scene.export_spawn = bpy.props.BoolProperty(name="Spawn", update=utils.save_settings, default=utils.get_setting('export_spawn', True))
   
    bpy.types.Scene.collision_visible = bpy.props.BoolProperty(name = 'collision_visible', update =utils.UpdateVisibleSelectable, default=True)
    bpy.types.Scene.collision_selectable = bpy.props.BoolProperty(name = 'collision_selectable', update =utils.UpdateVisibleSelectable, default=True)
    bpy.types.Scene.visuals_visible = bpy.props.BoolProperty(name = 'visuals_visible', update =utils.UpdateVisibleSelectable, default=True)
    bpy.types.Scene.visuals_selectable = bpy.props.BoolProperty(name = 'visuals_selectable', update =utils.UpdateVisibleSelectable, default=True)
    bpy.types.Scene.spline_cyclic = bpy.props.BoolProperty(name = 'cyclic', update =utils.save_settings, default=utils.get_setting('spline_cyclic', True))
    
    bpy.types.Scene.light_falloff = bpy.props.FloatProperty(name = 'falloff', min=0.0, max=10.0, update =utils.save_settings, default=utils.get_setting('light_falloff', 1.0))
    bpy.types.Scene.ambient_light = bpy.props.FloatVectorProperty(name = 'Ambient Light', subtype='COLOR', min=0.0, max=1.0, description="Tweak visibility and shading in dark areas", update =utils.save_settings, default=utils.get_setting('ambient_light', (0.0, 0.0, 0.0)))
    bpy.types.Scene.ambient_light_intensity = bpy.props.FloatProperty(name = 'ambient_light_intensity', min=0.0, max=1.0, update =utils.save_settings, default=utils.get_setting('ambient_light_intensity', 0.1))
    
    bpy.types.Scene.flags_expanded = bpy.props.BoolProperty(name = 'flags_expanded', default=False)
    bpy.types.Scene.fog_expanded = bpy.props.BoolProperty(name = 'fog_expanded', default=False)
    bpy.types.Scene.lighting_expanded = bpy.props.BoolProperty(name = 'lighting_expanded', default=False)
    bpy.types.Scene.trigger_expanded = bpy.props.BoolProperty(name = 'trigger_expanded', default=False)
    bpy.types.Scene.lights_expanded = bpy.props.BoolProperty(name = 'lights_expanded', default=False)
    bpy.types.Scene.textures_expanded = bpy.props.BoolProperty(name = 'texture_expanded', default=False)
    
    bpy.types.Object.visible = bpy.props.BoolProperty(name ='visible', default=False, update = utils.create_update_function("visible"))
    bpy.types.Object.collidable = bpy.props.BoolProperty(name ='collidable', default=False, update = utils.create_update_function("collidable"))
    
    for flag in dir(swe1r.modelblock.SurfaceEnum):
        if not flag.startswith("__"):
            setattr(bpy.types.Object, flag, bpy.props.BoolProperty(name = flag, default=False, update = utils.create_update_function(flag)))
            
    bpy.types.Object.magnet = bpy.props.BoolProperty(name ='magnet', default=False, update = utils.create_update_function("magnet"))
    
    bpy.types.Object.lighting_light = bpy.props.PointerProperty(type=bpy.types.Light, name="lighting_light", update = utils.create_update_function("lighting_light"))
    bpy.types.Object.lighting_color = bpy.props.FloatVectorProperty(name="lighting_color", subtype='COLOR', size=3, default=(0.0, 0.0, 0.0), min=0, max=1, description="Ambient Color", update = utils.create_update_function("lighting_color"))
    bpy.types.Object.lighting_invert = bpy.props.BoolProperty(name = 'lighting_invert', default=False, update = utils.create_update_function("lighting_invert"))
    bpy.types.Object.lighting_flicker = bpy.props.BoolProperty(name = 'lighting_flicker', default=False, update = utils.create_update_function("lighting_flicker"))
    bpy.types.Object.lighting_persistent = bpy.props.BoolProperty(name = 'lighting_persistent', default=False, update = utils.create_update_function("lighting_persistent"))
    
    bpy.types.Object.fog_color_update = bpy.props.BoolProperty(name = 'fog_color_update', default=False, update = utils.create_update_function("fog_color_update"))
    bpy.types.Object.fog_color = bpy.props.FloatVectorProperty(name="fog_color", subtype='COLOR', size=3, default=(0.0, 0.0, 0.0), min=0, max=1, description="Fog color", update = utils.create_update_function("fog_color"))
    bpy.types.Object.fog_range_update = bpy.props.BoolProperty(name = 'fog_range_update', default=False, update = utils.create_update_function("fog_range_update"))
    bpy.types.Object.fog_min = bpy.props.IntProperty(name="fog_min", default=1000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Fog min", subtype = 'DISTANCE', update = utils.create_update_function("fog_min"))
    bpy.types.Object.fog_max = bpy.props.IntProperty(name="fog_max", default=5000, min=1, max=30000, soft_min = 100, soft_max = 10000, description="Fog min", subtype = 'DISTANCE', update = utils.create_update_function("fog_max"))
    bpy.types.Object.fog_clear = bpy.props.BoolProperty(name = 'fog_clear', default=False, update = utils.create_update_function("fog_clear"))
    bpy.types.Object.skybox_show = bpy.props.BoolProperty(name ='skybox_show', default=False, update = utils.create_update_function("skybox_show"))
    bpy.types.Object.skybox_hide = bpy.props.BoolProperty(name ='skybox_hide', default=False, update = utils.create_update_function("skybox_hide"))
    
    bpy.types.Object.load_trigger = bpy.props.EnumProperty(
        name="View Layer",
        items= utils.populate_enum
    )
    
    bpy.types.Light.LStr = bpy.props.BoolProperty(name = 'Light Streak', default=False, update = utils.create_update_function("LStr"))
    
    operators.register()
    panels.register()
    
def unregister():
 
    panels.unregister()
    operators.unregister()
    props.unregister

if __name__ == "__main__":
    register()
