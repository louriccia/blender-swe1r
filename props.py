import bpy
from . import utils
from . import swe1r


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
    bpy.types.Scene.export_model = bpy.props.EnumProperty(
        items=[(str(i), f"{model['extension']} {model['name']}", f"Import model {model['name']}") for i, model in enumerate(swe1r.model_list.model_list)],
        name="Model",
        description="Select model",
        default=utils.get_setting('export_model', 0), 
        update=utils.save_settings
    )
    bpy.types.Scene.export_folder = bpy.props.StringProperty(subtype='DIR_PATH', update=utils.save_settings, default=utils.get_setting('export_folder', ""), description="Select the lev01 folder (or any folder you wish to export to)")
    bpy.types.Scene.is_export_model = bpy.props.BoolProperty(name="Model", update=utils.save_settings, default=utils.get_setting('is_export_model', True))
    bpy.types.Scene.is_export_texture = bpy.props.BoolProperty(name="Texture", update=utils.save_settings, default=utils.get_setting('is_export_texture', True))
    bpy.types.Scene.is_export_spline = bpy.props.BoolProperty(name="Spline", update=utils.save_settings, default=utils.get_setting('is_export_spline', True))
    bpy.types.Scene.export_separate = bpy.props.BoolProperty(name="export_separate", update=utils.save_settings, default=utils.get_setting('export_separate', True))
    
    bpy.types.Scene.collision_visible = bpy.props.BoolProperty(name = 'collision_visible', update =utils.ColVis, default=True)
    bpy.types.Scene.collision_selectable = bpy.props.BoolProperty(name = 'collision_selectable', update =utils.SelCol, default=True)
    bpy.types.Scene.visuals_visible = bpy.props.BoolProperty(name = 'visuals_visible', update =utils.ShoVis, default=True)
    bpy.types.Scene.visuals_selectable = bpy.props.BoolProperty(name = 'visuals_selectable', update =utils.SelVis, default=True)
    bpy.types.Scene.visible = bpy.props.BoolProperty(name = 'visible', default=False)
    bpy.types.Scene.collidable = bpy.props.BoolProperty(name = 'collidable', default=False)
    
def unregister():
    del bpy.types.Scene.import_folder
    del bpy.types.Scene.import_type
    del bpy.types.Scene.import_model
    del bpy.types.Scene.export_folder
    del bpy.types.Scene.export_model
    del bpy.types.Scene.is_export_model
    del bpy.types.Scene.is_export_texture
    del bpy.types.Scene.is_export_spline
    del bpy.types.Scene.export_separate
    del bpy.types.Scene.collision_visible
    del bpy.types.Scene.collision_selectable
    del bpy.types.Scene.visuals_visible
    del bpy.types.Scene.visuals_selectable
    del bpy.types.Scene.visible
    del bpy.types.Scene.collidable