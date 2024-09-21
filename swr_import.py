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
from .popup import show_custom_popup
from .swe1r.modelblock import Model
from .swe1r.splineblock import Spline
from .swe1r.spline_map import spline_map
from .swe1r.block import Block
from .utils import UpdateVisibleSelectable, data_name_prefix_short

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
    if selector is None:
        selector = range(324)
        
    # cleanup

    mats_removed = 0
    for mat in bpy.data.materials:
        if mat.name.startswith(data_name_prefix_short) and (mat.users == 0 or int(mat.name[11:14]) in selector):
            bpy.data.materials.remove(mat)
            mats_removed += 1

    if mats_removed > 0:
        print(f'Removed {mats_removed} unused materials.')

    imgs_removed = 0
    for img in bpy.data.images:
        if img.name.startswith(data_name_prefix_short) and img.users == 0:
            bpy.data.images.remove(img)
            imgs_removed += 1

    if imgs_removed > 0:
        print(f'Removed {imgs_removed} unused images.')
        
    # setup

    modelblock = Block(file_path + 'out_modelblock.bin', [[], []]).read()
    textureblock = Block(file_path + 'out_textureblock.bin', [[], []]).read()
    splineblock = Block(file_path + 'out_splineblock.bin', [[]]).read()

    modelblock.textureblock = textureblock
    modelblock.splineblock = splineblock

    # unpacking

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
            
    # toggle visible/selectable
    UpdateVisibleSelectable(None)

    # reporting

    print(f'Successfully unpacked {len(selector)} models')

    show_custom_popup(bpy.context, "IMPORTED!", f"Successfully unpacked {len(selector)} models. Removed {mats_removed} unused materials and {imgs_removed} unused images.")
    
