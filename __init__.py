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
    bpy.types.Scene.import_model = bpy.props.EnumProperty(
        items=[(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(swe1r.model_list.model_list) if model['extension'] == utils.model_types[int(utils.get_setting('import_type', 0))][1]],
        name="Model",
        description="Select model",
        default=utils.get_setting('import_model', 0), 
        update=utils.save_settings
    )
    bpy.types.Scene.export_folder = bpy.props.StringProperty(subtype='DIR_PATH', update=utils.save_settings, default=utils.get_setting('export_folder', ""), description="Select the lev01 folder (or any folder you wish to export to)")
    bpy.types.Scene.export_model = bpy.props.BoolProperty(name="Model", update=utils.save_settings, default=utils.get_setting('export_model', True))
    bpy.types.Scene.export_texture = bpy.props.BoolProperty(name="Texture", update=utils.save_settings, default=utils.get_setting('export_texture', True))
    bpy.types.Scene.export_spline = bpy.props.BoolProperty(name="Spline", update=utils.save_settings, default=utils.get_setting('export_spline', True))
    bpy.types.Scene.collision_visible = bpy.props.BoolProperty(name = 'collision_visible', update =utils.ColVis, default=True)
    bpy.types.Scene.collision_selectable = bpy.props.BoolProperty(name = 'collision_selectable', update =utils.SelCol, default=True)
    bpy.types.Scene.visuals_visible = bpy.props.BoolProperty(name = 'visuals_visible', update =utils.ShoVis, default=True)
    bpy.types.Scene.visuals_selectable = bpy.props.BoolProperty(name = 'visuals_selectable', update =utils.SelVis, default=True)
    bpy.types.Scene.spline_cyclic = bpy.props.BoolProperty(name = 'cyclic', update =utils.save_settings, default=utils.get_setting('spline_cyclic', True))
    
    # bpy.types.Scene.fog_flag = bpy.props.EnumProperty(items=constants.fog_flag_items, name="Fog Flag", description="Fog flag", default=utils.get_setting('fog_flag', 0), update=utils.save_settings)
    # bpy.types.Scene.fog_color = bpy.props.FloatVectorProperty(name="Fog Color", subtype='COLOR', size=3, default=(0.5, 0.5, 0.5), min=0, max=1, description="Fog color")
    # bpy.types.Scene.fog_start = bpy.props.IntProperty(name="Fog Start", default=utils.get_setting('fog_start', 100), min=0, max=10000, description="Fog start")
    # bpy.types.Scene.fog_end = bpy.props.IntProperty(name="Fog End", default=utils.get_setting('fog_end', 1000), min=0, max=10000, description="Fog end")
    
    # bpy.types.Scene.lights_flag = bpy.props.EnumProperty(items=constants.lights_flag_items, name="Lights Flag", description="Lights flag", default=utils.get_setting('lights_flag', 0), update=utils.save_settings)
    # bpy.types.Scene.lights_ambient = bpy.props.FloatVectorProperty(name="Ambient", subtype='COLOR', size=3, default=(0.5, 0.5, 0.5), min=0, max=1, description="Ambient color")
    # bpy.types.Scene.lights_color = bpy.props.FloatVectorProperty(name="Color", subtype='COLOR', size=3, default=(0.5, 0.5, 0.5), min=0, max=1, description="Color")
    # bpy.types.Scene.lights_unk1 = bpy.props.IntProperty(name="Unk1", default=utils.get_setting('lights_unk1', 0), min=0, max=255, description="Unk1")
    # bpy.types.Scene.lights_unk2 = bpy.props.IntProperty(name="Unk2", default=utils.get_setting('lights_unk2', 0), min=0, max=255, description="Unk2")
    # bpy.types.Scene.lights_position = bpy.props.FloatVectorProperty(name="Position", subtype='TRANSLATION', size=3, default=(0, 0, 0), min=-10000, max=10000, description="Position")
    # bpy.types.Scene.lights_direction = bpy.props.FloatVectorProperty(name="Direction", subtype='TRANSLATION', size=3, default=(0, 0, 0), min=-10000, max=10000, description="Direction")
    
    
    
    operators.register()
    panels.register()
    
def unregister():
    panels.unregister()
    operators.unregister()
    props.unregister

if __name__ == "__main__":
    register()