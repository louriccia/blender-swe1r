import sys
import os
import bpy
import struct
import json
import math
from .popup import show_custom_popup
from .modelblock import Model
from .splineblock import Spline
from .block import Block
    
scale = 100

def export_model(col, file_path, exports):
    types = [obj.type for obj in col.objects]
    model_export, texture_export, spline_export = exports
    print(types)
    
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
        pass
        
    show_custom_popup(bpy.context, "Exported!", f"Model {col['ind']} was successfully exported")
    