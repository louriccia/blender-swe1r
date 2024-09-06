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

import bpy
from .swe1r.modelblock import Model
from .swe1r.splineblock import Spline
from .swe1r.spline_map import spline_map
from .swe1r.block import Block
from .swe1r.general import data_name_format

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
    # TODO: remove resources again, but following a pattern so as to avoid clashes with unrelated stuff
    #for image in bpy.data.images:
    #    bpy.data.images.remove(image)
    #    
    #for mat in bpy.data.materials:
    #    bpy.data.materials.remove(mat)
        
    modelblock = Block(file_path + 'out_modelblock.bin', [[], []]).read()
    textureblock = Block(file_path + 'out_textureblock.bin', [[], []]).read()
    splineblock = Block(file_path + 'out_splineblock.bin', [[]]).read()

    modelblock.textureblock = textureblock
    modelblock.splineblock = splineblock

    if selector is None:
        selector = range(324)
        
    for model_id in selector:
        model_buffer = modelblock.fetch(model_id)[1]
        model = Model(model_id).read(model_buffer)
        if model is None:
            print("There was an error while parsing the model")
            return 
        model.modelblock = modelblock
        collection = model.make()
        if model_id in spline_map:
            spline_id = spline_map[model_id]
            spline_buffer = splineblock.fetch(spline_id)[0]
            spline = Spline(spline_id).read(spline_buffer)
            collection.objects.link(spline.make(model.scale))
            
    print(f'Successfully unpacked {len(selector)} models')
    
