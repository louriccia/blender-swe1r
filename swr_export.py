import bpy
from .popup import show_custom_popup
from .modelblock import Model
from .splineblock import Spline
from .textureblock import Texture
from .block import Block
    
scale = 100

def export_model(col, file_path, exports):
    types = [obj.type for obj in col.objects]
    model_export, texture_export, spline_export = exports
    
    if not len(exports):
        show_custom_popup(bpy.context, "No Export", f"Please select an element to export")
        
    
    if 'MESH' in types and model_export:
        model = Model(col['ind']).unmake(col)
        # #inject data and write to modelblock file    
        # block = inject_model(offset_buffer, model_buffer, col['ind'], file_path)
        # with open(file_path + 'out_modelblock.bin', 'wb') as file:
        #     file.write(block)
    
    if 'CURVE' in types and spline_export:
        splineblock = Block(file_path + 'out_splineblock.bin', [[]]).read()
        spline = Spline().unmake(col)
        spline_buffer = spline.write()
        splineblock.inject([spline_buffer], spline.id)
        
        with open(file_path + 'out_splineblock.bin', 'wb') as file:
            file.write(splineblock.write())
        
        #debug write
        with open(file_path + 'spline_' + str(spline.id)+'.bin', 'wb') as file:
            file.write(spline_buffer)
    
    if texture_export:
        textureblock = Block(file_path + 'out_textureblock.bin', [[], []]).read()
        for image in bpy.data.images:
            id = int(image['id'])
            texture = Texture(id).unmake(image)
            pixel_buffer = texture.pixels.write()
            palette_buffer = texture.palette.write()
            textureblock.inject([pixel_buffer, palette_buffer], id)
        with open(file_path + 'out_textureblock.bin', 'wb') as file:
            file.write(textureblock.write())
            
    show_custom_popup(bpy.context, "Exported!", f"Model {col['ind']} was successfully exported")
    