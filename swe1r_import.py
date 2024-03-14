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

import sys
import os
import bpy
import struct
from .modelblock import Model
from .splineblock import Spline
from .spline_map import spline_map
from .block import Block

# for material in bpy.data.materials:
#     material.user_clear()
#     bpy.data.materials.remove(material)

# for obj in bpy.data.objects:
#     bpy.data.objects.remove(obj)
    
# for col in bpy.data.collections:
#     bpy.data.collections.remove(col)
    
# for img in bpy.data.images:
#     bpy.data.images.remove(img)

scale = 0.01

def import_model(file_path, selector=None):
    for image in bpy.data.images:
        bpy.data.images.remove(image)
        
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)
    
    modelblock = Block(file_path + 'out_modelblock.bin', [[], []]).read()
    textureblock = Block(file_path + 'out_textureblock.bin', [[], []]).read()
    splineblock = Block(file_path + 'out_splineblock.bin', [[]]).read()

    modelblock.textureblock = textureblock
    modelblock.splineblock = splineblock

    if selector is None:
        selector = range(324)
        
    for model_id in selector:
        model_buffer = modelblock.fetch(model_id)[0]
        model = Model(model_id).read(model_buffer)
        model.modelblock = modelblock
        if spline_map[model_id]:
            spline_id = spline_map[model_id]
            spline_buffer = splineblock.fetch(spline_id)[0]
            spline = Spline(spline_id).read(spline_buffer)
            collection = model.make()
            collection.objects.link(spline.make(model.scale))
    print(f'Successfully unpacked {len(selector)} models')