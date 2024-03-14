import sys
import os
import bpy
import struct
import json
import math
from .swe1r_import import read_block
from .popup import show_custom_popup
from .modelblock import Model
from .splineblock import Spline
from .block import Block
    
scale = 100

def export_model(col, file_path):
    
    # model = Model(col['ind']).unmake(col)
    splineblock = Block(file_path + 'out_splineblock.bin', [[]]).read()
    spline = Spline().unmake(col)
    spline_buffer = spline.write()
    splineblock.inject([spline_buffer], spline.id)
    splineblock.write(file_path + 'out_splineblock.bin')
    
    #debug write
    with open(file_path + str(spline.id)+'.bin', 'wb') as file:
        file.write(spline_buffer)
    
    # #inject data and write to modelblock file    
    # block = inject_model(offset_buffer, model_buffer, col['ind'], file_path)
    # with open(file_path + 'out_modelblock.bin', 'wb') as file:
    #     file.write(block)
        
    # show_custom_popup(bpy.context, "Exported!", f"Model {col['ind']} was successfully exported")
    