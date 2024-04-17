import bpy
from .popup import show_custom_popup
from .modelblock import Model
from .splineblock import Spline
from .textureblock import Texture
from .block import Block
from .general import *
    
scale = 100

def export_model(col, file_path, exports):
    types = [obj.type for obj in col.objects]
    for child in col.children:
        for obj in child.objects:
            types.append(obj.type)
    model_export, texture_export, spline_export = exports
    
    if not len(exports):
        show_custom_popup(bpy.context, "No Export", f"Please select an element to export")
        
    if 'MESH' in types and model_export:
        modelblock = Block(file_path + 'out_modelblock.bin', [[], []]).read()
        model = Model(col['ind']).unmake(col)
        id = model.id
        if model is None:
            show_custom_popup(bpy.context, "Model Error", "There was an issue while exporting the model")
            return
        
        offset_buffer, model_buffer = model.write()
        modelblock.inject([offset_buffer, model_buffer], id)
        
        with open(file_path + 'out_modelblock.bin', 'wb') as file:
            file.write(modelblock.write())
            
        #debug write
        with open(file_path + 'model_' + str(model.id)+'.bin', 'wb') as file:
            file.write(model_buffer)
            
        with open(file_path + 'offset_' + str(model.id)+'.bin', 'wb') as file:
            file.write(offset_buffer)
            
        debug_text = ["float, int32, int16_1, int16_2, int8_1, int8_2, int8_3, int8_4, local_offset, pointer"]
        for i in range(0, len(model_buffer), 4):
            debug_string = f"{readFloatBE(model_buffer, i)}, {readUInt32BE(model_buffer, i)}, {readUInt16BE(model_buffer, i)}, {readUInt16BE(model_buffer, i+2)}, {readUInt8(model_buffer, i)}, {readUInt8(model_buffer, i + 1)}, {readUInt8(model_buffer, i + 2)}, {readUInt8(model_buffer, i + 3)}, {i}, {readUInt8(offset_buffer, i//32)}, {(readUInt8(offset_buffer, i//32) >> (7-((i//4)%8)) )& 1 }"
            debug_text.append(debug_string)
            
        with open(file_path + 'debug.txt', 'a') as file:
            for string in debug_text:
                file.write(string + '\n')
    
    if 'CURVE' in types and spline_export:
        splineblock = Block(file_path + 'out_splineblock.bin', [[]]).read()
        spline = Spline().unmake(col)
        
        if spline is None:
            show_custom_popup(bpy.context, "Spline Error", "There was an issue while exporting the spline")
            return
        
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
            if not 'format' in image:
                image['format'] = 513
            texture = Texture(id).unmake(image)
            pixel_buffer = texture.pixels.write()
            palette_buffer = texture.palette.write()
            textureblock.inject([pixel_buffer, palette_buffer], id)
        with open(file_path + 'out_textureblock.bin', 'wb') as file:
            file.write(textureblock.write())
            
    show_custom_popup(bpy.context, "Exported!", f"Model {col['ind']} was successfully exported")
    