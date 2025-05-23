# Copyright (C) 2021-2024
# lightningpirate@gmail.com

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
from .utils import UpdateVisibleSelectable, show_custom_popup

scale = 0.01

def import_model(file_path, selector=None, update_progress=None):
    if selector is None:
        selector = range(324)
        
    # cleanup

    mats_removed = 0
    # update_progress("Deleting unused materials")    
    # for mat in bpy.data.materials:
    #     if mat.name.startswith(data_name_prefix_short) and (mat.users == 0 or int(mat.name[11:14]) in selector):
    #         bpy.data.materials.remove(mat)
    #         mats_removed += 1

    # if mats_removed > 0:
    #     print(f'Removed {mats_removed} unused materials.')


    # update_progress("Deleting unused images")    

    # imgs_removed = 0
    # for img in bpy.data.images:
    #     if img.name.startswith(data_name_prefix_short) and img.users == 0:
    #         bpy.data.images.remove(img)
    #         imgs_removed += 1

    # if imgs_removed > 0:
    #     print(f'Removed {imgs_removed} unused images.')
        
    # setup
    
    update_progress("Parsing .bin files")
    
    modelblock = Block(file_path + 'out_modelblock.bin', 2, update_progress).read()
    textureblock = Block(file_path + 'out_textureblock.bin', 2, update_progress).read()
    splineblock = Block(file_path + 'out_splineblock.bin', 1, update_progress).read()

    modelblock.textureblock = textureblock
    modelblock.splineblock = splineblock

    # unpacking

    for model_id in selector:
        update_progress(f'Reading model {model_id}')

        model_buffer = modelblock.fetch(model_id)[1]
        model = Model(model_id)
        model.modelblock = modelblock
        model = model.read(model_buffer)
        if model is None:
            print("There was an error while parsing the model")
            return 
        update_progress(f'Making model {model_id}')

        collection = model.make()
        if model_id in spline_map:
            spline_id = spline_map[model_id]
            spline_buffer = splineblock.fetch(spline_id)[0]
            update_progress(f'Reading spline {spline_id}')
            
            spline = Spline(spline_id).read(spline_buffer)
            update_progress(f'Making spline {spline_id}')
            collection.objects.link(spline.make(model.scale))
            
    # reset view layer
    view_layer = bpy.context.scene.view_layers.get("ViewLayer")
    bpy.context.window.view_layer = view_layer
    # toggle visible/selectable
    UpdateVisibleSelectable(None)

    # reporting

    print(f'Successfully unpacked {len(selector)} models')

    show_custom_popup(bpy.context, "IMPORTED!", f"Successfully unpacked {len(selector)} models.")
    
