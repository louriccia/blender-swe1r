import bpy
from .popup import show_custom_popup
from .swe1r.modelblock import Model
from .swe1r.splineblock import Spline
from .swe1r.textureblock import Texture
from .swe1r.block import Block
from .swe1r.general import *
from .swe1r.textureblock import compute_hash
from .utils import Podd_MAlt
from datetime import datetime
    
scale = 100

def export_model(col, file_path, exports, update_progress):
    # prepare blender scene for export
    bpy.context.scene.frame_set(0)
    
    types = [obj.type for obj in col.objects]
    for child in col.children:
        for obj in child.objects:
            types.append(obj.type)
    model_export, texture_export, spline_export = exports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if not len(exports):
        show_custom_popup(bpy.context, "No Export", f"Please select an element to export")
        
    if 'MESH' in types and model_export:
        
        update_progress("Parsing .bin files...")
        
        modelblock = Block(file_path + 'out_modelblock.bin', 2, update_progress).read()
        textureblock = Block(file_path + 'out_textureblock.bin', 2, update_progress).read()

        update_progress(f'Unmaking {col.name}...')
        
        model = Model(col.export_model).unmake(col, texture_export, textureblock)
        id = model.id
        if model is None:
            show_custom_popup(bpy.context, "Model Error", "There was an issue while exporting the model")
            return
        
        update_progress(f'Writing {col.name}...')
        
        offset_buffer, model_buffer = model.write()
        modelblock.inject([offset_buffer, model_buffer], id)
        
        if model.id in Podd_MAlt:
            # If we're exporting a Podd, write a blank MAlt model
            MAlt_id = Podd_MAlt[model.id]
            MAlt = Model(MAlt_id)
            MAlt.type = '1'
            MAlt_offset_buffer, MAlt_model_buffer = MAlt.write()
            modelblock.inject([MAlt_offset_buffer, MAlt_model_buffer], MAlt_id)
        
        with open(file_path + 'out_modelblock.bin', 'wb') as file:
            file.write(modelblock.write())
            
        if texture_export:
            update_progress(f'Writing textures...')
            
            with open(file_path + 'out_textureblock.bin', 'wb') as file:
                file.write(textureblock.write())
            
        if bpy.context.scene.is_export_separate:
            update_progress(f'Writing separate .bin file...')
            
            with open(file_path + 'model_' + str(model.id) + '_' + timestamp +'.bin', 'wb') as file:
                file.write(model_buffer)
            with open(file_path + 'offset_' + str(model.id) + '_' + timestamp +'.bin', 'wb') as file:
                file.write(offset_buffer)
            
        # write debug file
        debug_text = ["float, int32, int16_1, int16_2, int8_1, int8_2, int8_3, int8_4, local_offset, pointer"]
        for i in range(0, len(model_buffer), 4):
            debug_string = f"{readFloatBE(model_buffer, i)}, {readUInt32BE(model_buffer, i)}, {readInt16BE(model_buffer, i)}, {readInt16BE(model_buffer, i+2)}, {readUInt8(model_buffer, i)}, {readUInt8(model_buffer, i + 1)}, {readUInt8(model_buffer, i + 2)}, {readUInt8(model_buffer, i + 3)}, {i}, {readUInt8(offset_buffer, i//32)}, {(readUInt8(offset_buffer, i//32) >> (7-((i//4)%8)) )& 1 }"
            debug_text.append(debug_string)
            
        with open(file_path + 'model_' + str(model.id) + '_' + timestamp + 'debug.txt', 'a') as file:
            for string in debug_text:
                file.write(string + '\n')
    
    if 'CURVE' in types and spline_export:
        update_progress(f'Unmaking spline...')
        
        splineblock = Block(file_path + 'out_splineblock.bin', 1, update_progress).read()
        spline = Spline().unmake(col)
        
        if spline is None:
            show_custom_popup(bpy.context, "Spline Error", "There was an issue while exporting the spline")
            return
        
        update_progress(f'Writing spline...')
        
        spline_buffer = spline.write()
        splineblock.inject([spline_buffer], spline.id)
        
        with open(file_path + 'out_splineblock.bin', 'wb') as file:
            file.write(splineblock.write())
        
        if bpy.context.scene.is_export_separate:
            with open(file_path + 'spline_' + str(spline.id) + '_' + timestamp + '.bin', 'wb') as file:
                file.write(spline_buffer)
            
    show_custom_popup(bpy.context, "Exported!", f"Model {col.export_model} was successfully exported")
    