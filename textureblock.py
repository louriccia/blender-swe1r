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
import bpy
from .readwrite import *

class Texture():
    def __init__(self, id, format, width, height):
        self.id = id
        self.format = format
        self.width = width
        self.height = height
        self.palette = None
        self.pixels = None
    def read(self, textureblock):
        if self.id is None:
            return
        pixel_buffers, palette_buffers = textureblock.read([self.id])
        if self.format in [512, 513]:
            self.palette = Palette(self)
            self.palette.read(palette_buffers[0])
            
        self.pixels = Pixels(self)
        self.pixels.read(pixel_buffers[0])
    def make(self):
        if self.pixels is None:
            print(f"Texture {self.id} does not have any pixels")
            return

        if None in [self.format, self.width, self.height]:
            print(f"Texture {self.id} is missing width/height/format data")
            return

        new_image = bpy.data.images.new(str(self.id), self.width, self.height)
        image_pixels = []    
        pixels = self.pixels.data
        palette = None if self.palette.data is None else self.palette.data
        for i in range(self.height):
            for j in range(self.width):
                ind = i * self.width + j
                p = None
                color = None

                if self.format in [512, 513]:
                    p = palette[pixels[ind]]
                    color = [p[0] if p else 0, p[1] if p else 0, p[2] if p else 0, p[3] if p else 0]

                elif self.format in [1024, 1025]:
                    p = pixels[ind]
                    color = [p if p else 0, p if p else 0, p if p else 0, 255]

                elif self.format == 3:
                    p = pixels[ind]
                    color = [p[0] if p else 0, p[1] if p else 0, p[2] if p else 0, p[3] if p else 0]
                    
                image_pixels.extend(color)
        new_image.pixels = [p/255 for p in image_pixels]
        new_image['format'] = self.format

        return new_image
    
class Palette():
    def __init__(self, texture):
        self.texture = texture
        self.data = []
    
    def read(self, buffer):
        format = self.texture.format
        format_map = {
            512: 16,
            513: 256
        }

        if not buffer:
            return []

        for cursor in range(0, format_map.get(format, 0) * 2, 2):
            color = readInt16BE(buffer, cursor)
            a = ((color >> 0) & 0x1) * 0xFF
            b = round((((color >> 1) & 0x1F) / 0x1F) * 255)
            g = round((((color >> 6) & 0x1F) / 0x1F) * 255)
            r = round((((color >> 11) & 0x1F) / 0x1F) * 255)
            if (r + g + b) > 0 and a == 0:
                a = 255
            self.data.append([r, g, b, a])

        return self.data
    
    def write(palette):
        if not palette:
            return bytearray()

        buffer = bytearray(len(palette) * 2)
        cursor = 0

        for p in palette:
            r = int((p[0] / 255) * 0x1F) << 11
            g = int((p[1] / 255) * 0x1F) << 6
            b = int((p[2] / 255) * 0x1F) << 1
            a = int(p[3] / 255)
            pal = (((r | g) | b) | a)
            buffer[cursor:cursor + 2] = pal.to_bytes(2, 'big')
            cursor += 2

        return bytes(buffer)
    
class Pixels():
    def __init__(self, texture):
        self.texture = texture
        self.data = []
    def read(self, buffer):
        cursor = 0
        pixel_count = self.texture.width * self.texture.height
        if self.texture.format == 3:
            for i in range(pixel_count):
                r, g, b, a = struct.unpack('>BBBB', buffer[cursor:cursor + 4])
                self.data.append([r, g, b, a])
                cursor += 4

        elif self.texture.format == 512:
            for i in range(round(pixel_count/2)):
                p = buffer[cursor]
                pixel_0 = (p >> 4) & 0xF
                pixel_1 = p & 0xF
                self.data.extend([pixel_0, pixel_1])
                cursor += 1

        elif self.texture.format == 513:
            for i in range(pixel_count):
                pixel = buffer[cursor]
                self.data.append(pixel)
                cursor += 1

        elif self.texture.format == 1024:
            for i in range(round(pixel_count/2)):
                p = buffer[cursor]
                pixel_0 = ((p >> 4) & 0xF) * 0x11
                pixel_1 = (p & 0xF) * 0x11
                self.data.extend([pixel_0, pixel_1])
                cursor += 1

        elif self.texture.format == 1025:
            for i in range(pixel_count):
                pixel = buffer[cursor]
                self.data.append(pixel)
                cursor += 1

        return self.data

    def write(self):
        formatmap = {
            3: 4,
            512: 0.5,
            513: 1,
            1024: 0.5,
            1025: 1
        }

        buffer = bytearray(len(self.data) * int(formatmap[format]))
        cursor = 0
        format = self.texture.format
        if format in [512, 1024]:
            for i in range(0, len(self.data) // 2):
                if format == 512:
                    buffer[cursor] = (self.data[i * 2] << 4) | self.data[i * 2 + 1]
                elif format == 1024:
                    buffer[cursor] = (self.data[i * 2] // 0x11 << 4) | (self.data[i * 2 + 1] // 0x11)
                cursor += 1

        elif format in [513, 1025, 3]:
            for i in range(len(self.data)):
                pixel = self.data[i]
                if format == 3:
                    for j in range(4):
                        buffer[cursor] = pixel[j]
                        cursor += 1
                else:
                    buffer[cursor] = pixel
                    cursor += 1

        return bytes(buffer)

def make_texture(texture, folder_path):
    file_path = folder_path + 'out_textureblock.bin'
    selector = [texture['tex_index']]

    with open(file_path, 'rb') as file:
        file = file.read()
        read_block_result = read_block(file, [[], []], selector)

    pixel_buffers, palette_buffers = read_block_result
    tex = None
    for i, buffer in enumerate(pixel_buffers):
        pixels = read_pixels(buffer, texture['format'], texture['width']*texture['height'])
        palette = read_palette(palette_buffers[i], texture['format'])
        tex = draw_texture(pixels, palette, texture['width'], texture['height'], texture['format'], str(selector[i]) + '.png',  str(selector[i]))
        
    return tex

def draw_texture(pixels, palette, width, height, format, path, index):
    
    if not pixels:
        print(f"Texture {index} does not have any pixels")
        return

    if None in [format, width, height]:
        print(f"Texture {index} is missing width/height/format data")
        return

    new_image = bpy.data.images.new(name=str(index), width=width, height=height)
    image_pixels = []    

    for i in range(height):
        for j in range(width):
            ind = i * width + j
            p = None
            color = None

            if format in [512, 513]:
                p = palette[pixels[ind]]
                color = [p[0] if p else 0, p[1] if p else 0, p[2] if p else 0, p[3] if p else 0]

            elif format in [1024, 1025]:
                p = pixels[ind]
                color = [p if p else 0, p if p else 0, p if p else 0, 255]

            elif format == 3:
                p = pixels[ind]
                color = [p[0] if p else 0, p[1] if p else 0, p[2] if p else 0, p[3] if p else 0]

            x = 0

            image_pixels.extend(color)
           
    new_image.pixels = [p/255 for p in image_pixels]
    new_image['format'] = format

    return new_image







def unmake_image(image):
    if not image:
        print("Invalid image provided.")
        return None

    format = image['format']
    width = image.size[0]
    height = image.size[1]
    index = int(image.name)  # Assuming the name represents the index

    pixels = []
    palette = []

    for i in range(height):
        for j in range(width):
            pixel_index = (i * width + j) * 4  # Each pixel has 4 components (RGBA)
            color = image.pixels[pixel_index:pixel_index + 4]
            pixels.extend(color)

            # Assuming format 512 or 513 corresponds to a palette
            if format in [512, 513] and color not in palette:
                palette.append(color)

    return pixels, palette, index