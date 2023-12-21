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

import struct
import math
import os
from .readwrite import *

class Block():
    def __init__(self, path, arr):
        self.asset_count = 0
        self.buffers = []
        self.data = arr
        self.sub_chunks = len(self.data)
        self.path = path
        self.dir = os.path.dirname(self.path)
    def read(self, file, selector):
        with open(self.path, 'rb') as file:
            file = file.read()
        asset_count = readUInt32BE(file, 0)
        cursor = 4        
        for i in (selector if len(selector) else range(asset_count)):
            for j in range(self.sub_chunks):
                asset_start = readUInt32BE(file, 4 + i*4*self.sub_chunks + j * 4)
                cursor += 4

                asset_end = readUInt32BE(file, 4 + i*4*self.sub_chunks + j * 4 + 4)
                if not asset_end:
                    asset_end = readUInt32BE(file, 4 + i*4*self.sub_chunks + j * 4 + 8)

                asset = file[asset_start:asset_end] if asset_start else None

                self.data[j].append(asset)

        return self.data
    
    def write(self, path = None):
        if path is None:
            path = self.path
        length = len(self.data[0])
        index = bytearray((length * self.sub_chunks + 2) * 4)
        block = []
        block.append(index)

        struct.pack_into('>I', index, 0, length)  # write total number of assets
        cursor = len(index)
        for i in range(length):
            for j in range(self.sub_chunks):
                struct.pack_into('>I', index, 4 + (i * self.sub_chunks + j) * 4, cursor if (arr[j][i] and len(arr[j][i])) else 0)
                cursor += len(arr[j][i])
                block.append(arr[j][i])
        struct.pack_into('>I', index, (length * self.sub_chunks + 1) * 4, cursor)  # end of block offset

        return b''.join(block)

def inject_model(offset_buffer, model_buffer, ind, file_path):
    with open(file_path + '/out_modelblock.bin', 'rb') as file:
        file = file.read()
        read_block_result = read_block(file, [[], []], [])

    offset_buffers, model_buffers = read_block_result
    
    offset_buffers[ind] = offset_buffer
    model_buffers[ind] = model_buffer
    
    block = write_block([offset_buffers, model_buffers])
    return block

