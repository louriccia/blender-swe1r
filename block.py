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
import os
from .readwrite import *

class Block():
    def __init__(self, path, arr):
        self.asset_count = 0
        self.buffers = []
        self.data = arr
        self.sub_chunks = len(arr)
        self.path = path
        self.dir = os.path.dirname(self.path)
        
    def read(self):
        with open(self.path, 'rb') as file:
            file = file.read()
        asset_count = readUInt32BE(file, 0)
        cursor = 4
        self.data = [[] for f in range(self.sub_chunks)]
        addresses = []
        for i in range(asset_count):
            for j in range(self.sub_chunks):
                offset = i*4*self.sub_chunks + j * 4
                asset_start = readUInt32BE(file, 4 + offset)
                cursor += 4

                asset_end = readUInt32BE(file, 4 + offset + 4)
                if not asset_end:
                    asset_end = readUInt32BE(file, 4 + offset + 8)
                    
                asset = file[asset_start:asset_end] if asset_start else None
                addresses.append(asset_start)
                self.data[j].append(asset)
        return self
    
    def write(self):
        asset_count = len(self.data[0])
        header = bytearray((asset_count * self.sub_chunks + 2) * 4)
        block = []
        block.append(header)

        struct.pack_into('>I', header, 0, asset_count)  # write total number of assets
        cursor = len(header)
        for i in range(asset_count):
            for j in range(self.sub_chunks):
                struct.pack_into('>I', header, 4 + (i * self.sub_chunks + j) * 4, cursor if (self.data[j][i] and len(self.data[j][i])) else 0)
                cursor += len(self.data[j][i])
                block.append(self.data[j][i])
        struct.pack_into('>I', header, (asset_count * self.sub_chunks + 1) * 4, cursor)  # end of block offset

        return b''.join(block)
    
    def inject(self, data, index):
        for j in range(self.sub_chunks):
            self.data[j][index] = data[j]
        return self
            
    def fetch(self, index):
        return [self.data[j][index] for j in range(self.sub_chunks)]


