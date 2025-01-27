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
from .general import *
from .textureblock import compute_hash

class Block():
    def __init__(self, path, items_per_asset, update_progress):
        self.data = []
        self.hash_table = {}
        self.items_per_asset = items_per_asset
        self.path = path
        self.dir = os.path.dirname(self.path)
        self.update_progress = update_progress
        
    def read(self):
        self.update_progress(f"Reading {self.path}...")
        with open(self.path, 'rb') as file:
            file = file.read()
        
        assert len(file) > 0, f"{self.dir} is an empty file"
        
        asset_count = readUInt32BE(file, 0)
        
        #split into chunks
        self.data = [[] for asset in range(asset_count)]
        for i in range(asset_count):
            for j in range(self.items_per_asset):
                offset = i * 4 * self.items_per_asset + j * 4
                asset_start = readUInt32BE(file, 4 + offset)
                
                if not asset_start:
                    self.data[i].append(None)
                    continue

                asset_end = 0
                while not asset_end and offset < len(file):
                    asset_end = readUInt32BE(file, 4 + offset + 4)
                    offset += 4
                    
                self.data[i].append(file[asset_start:asset_end])
                
            hash = compute_hash(b''.join([item for item in self.data[i] if item]))
            self.hash_table[hash] = i
        
        return self
    
    def write(self):
        asset_count = len(self.data)
        header = bytearray((asset_count * self.items_per_asset + 2) * 4)
        block = [header]

        # start header with total number of assets
        struct.pack_into('>I', header, 0, asset_count)
        cursor = len(header)
        
        for i in range(asset_count):
            for j in range(self.items_per_asset):
                if self.data[i][j] and len(self.data[i][j]):
                    # write pointer in header
                    struct.pack_into('>I', header, 4 + (i * self.items_per_asset + j) * 4, cursor)
                    block.append(self.data[i][j])
                    cursor += len(self.data[i][j])
                    
        # end header with pointer to end of block
        struct.pack_into('>I', header, (asset_count * self.items_per_asset + 1) * 4, cursor)  

        return b''.join(block)
    
    def inject(self, data, index):
        assert len(data) == self.items_per_asset, "Number of items not suitable for this block"
        
        index = int(index)
        
        #pad list if index is out of range
        if index >= len(self.data):
            for i in range(len(self.data)-1, index):
                self.data.append([None for j in range(self.items_per_asset)])
        
        self.data[index] = data
        return self
            
    def fetch(self, index):
        return self.data[index]
    
    def fetch_by_hash(self, hash):
        if hash in self.hash_table:
            return self.hash_table[hash]
        
        return None
        


