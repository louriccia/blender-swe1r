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
from ..utils import euclidean_distance, data_name_format
from .modelblock import DataStruct

class Texture():
    def __init__(self, id, format = 513, width = 32, height = 32):
        if(int(id) == 65535):
            raise ValueError(f"Unexpected texture index {id}")
        self.id = id
        self.format = format
        self.width = width
        self.height = height
        self.palette = None
        self.pixels = None
    def read(self, pixel_buffer, palette_buffer):
        if self.id is None or self.id < 0:
            return
        if self.format in [512, 513]:
            self.palette = Palette(self)
            self.palette.read(palette_buffer)
            
        self.pixels = Pixels(self)
        self.pixels.read(pixel_buffer)
    def make(self):
        if int(self.id) < 0:
            return
        if self.pixels is None or not self.pixels:
            print(f"Texture {self.id} does not have any pixels")
            return

        if None in [self.format, self.width, self.height]:
            print(f"Texture {self.id} is missing width/height/format data")
            return
        tex_name = data_name_format.format(data_type = 'tex', label = str(self.id))
        new_image = bpy.data.images.new(tex_name, self.width, self.height)
        image_pixels = []    
        pixels = self.pixels.data
        palette = None if self.palette is None or self.palette.data is None else self.palette.data
        for i in range(self.height):
            for j in range(self.width):
                ind = i * self.width + j
                p = None
                color = None

                if self.format in [512, 513]:
                    color = palette[pixels[ind]].to_array()

                elif self.format in [1024, 1025]:
                    p = pixels[ind]
                    color = [p, p, p, 255]

                elif self.format == 3:
                    p = pixels[ind]
                    color = [p[0], p[1], p[2], p[3]]
                    
                image_pixels.extend(color)
                
        if len(image_pixels):
            new_image.pixels = [p/255 for p in image_pixels]
        new_image['format'] = self.format
        new_image['id'] = self.id

        return new_image

    def unmake(self, image, override_format = None):
        self.width, self.height = image.size
        self.palette = Palette(self).unmake(image, override_format)
        self.pixels = Pixels(self).unmake(image, override_format)
        return self
    
class RGBA5551(DataStruct):
    def __init__(self):
        super().__init__('>H')
        self.r = 0
        self.g = 0
        self.b = 0
        self.a = 0
    def read(self, buffer, cursor):
        pallete_color = struct.unpack_from(self.format_string, buffer, cursor)[0]
        self.a = ((pallete_color >> 0) & 0x1) * 0xFF
        self.b = round((((pallete_color >> 1) & 0x1F) / 0x1F) * 255)
        self.g = round((((pallete_color >> 6) & 0x1F) / 0x1F) * 255)
        self.r = round((((pallete_color >> 11) & 0x1F) / 0x1F) * 255)
        if (self.r + self.g + self.b) > 0 and self.a == 0:
            self.a = 255
        return self
    def to_array(self):
        return [self.r, self.g, self.b, self.a]
    def from_array(self, arr):
        if len(arr) == 3:
            arr.append(1.0)
        self.r, self.g, self.b, self.a = arr
        return self
    def write(self, buffer, cursor):
        r = int((self.r / 255) * 0x1F) << 11
        g = int((self.g / 255) * 0x1F) << 6
        b = int((self.b / 255) * 0x1F) << 1
        a = int(self.a / 255)
        color = (((r | g) | b) | a)
        struct.pack_into(self.format_string, buffer, cursor, color)
        return cursor + self.size
    def __eq__(self, other):
        return self.r == other.r and self.g == other.g and self.b == other.b and self.a == other.a
    
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

        for cursor in range(0, len(buffer), 2):
            self.data.append(RGBA5551().read(buffer, cursor))

        return self.data
    
    def to_array(self):
        return [c.to_array() for c in self.data]
    
    def unmake(self, image, override_format = None):
        if override_format is not None:
            threshold = 16 if int(override_format) == 512 else 256
        elif 'format' not in image:
            threshold = 256
        else:
            threshold = 16 if int(image['format']) == 512 else 256
        pixels = image.pixels
        
        # TODO: replace with color quantization solution
        for i in range(0, len(pixels), 4):
            color = RGBA5551().from_array([ int(j*255) for j in pixels[i: i+4]])
            if not color in self.data:
                self.data.append(color)
            if len(self.data) == threshold:
                break
        return self
    
    def write(self):
        buffer = bytearray(len(self.data) * 2)
        cursor = 0

        for color in self.data:
            cursor = color.write(buffer, cursor)

        return buffer
    
    def closest(self, target):
        
        
        min_distance = float('inf')
        closest = None
        for i, color in enumerate(self.data):
            distance = euclidean_distance(target.to_array()[:3], color.to_array()[:3])  # Consider only RGB components for distance calculation
            if distance < min_distance:
                min_distance = distance
                closest = i
        return closest
    
class Pixels():
    def __init__(self, texture):
        self.texture = texture
        self.data = []
    def read(self, buffer):
        if buffer is None:
            return self.data
        cursor = 0
        pixel_count = self.texture.width * self.texture.height
        if self.texture.format == 3:
            for i in range(pixel_count):
                r, g, b, a = struct.unpack('>BBBB', buffer[cursor:cursor + 4])
                self.data.append([r, g, b, a])
                cursor += 4

        elif self.texture.format == 512:
            for i in range(min(round(pixel_count/2), len(buffer))):
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

    def unmake(self, image, override_format = None):
        if override_format is not None:
            self.texture.format = int(override_format)
        elif 'format' not in image:
            self.texture.format = 513
        else:
            self.texture.format = int(image['format'])
        format = self.texture.format
        palette = None
        if format in [512, 513]:
            palette = self.texture.palette
            
        for i in range(0, len(image.pixels), 4):
            pixel = image.pixels[i: i+4]
            if format == 3:
                self.data.append([c for c in pixel])
            elif format in [512, 513]:
                color = RGBA5551().from_array([int(p*255) for p in pixel])
                closest = palette.closest(color)
                self.data.append(closest)
            elif format in [1024, 1025]:
                self.data.append(sum(pixel[:3])/3)
        return self

    def write(self):
        formatmap = {
            3: 4,
            512: 0.5,
            513: 1,
            1024: 0.5,
            1025: 1
        }
        format = int(self.texture.format)
        buffer = bytearray(int(len(self.data) * formatmap[format]))
        cursor = 0
        if format in [512, 1024]:
            for i in range(0, len(self.data), 2):
                if format == 512:
                    struct.pack_into('>B', buffer, cursor, (self.data[i] << 4) | self.data[i + 1])
                elif format == 1024:
                    struct.pack_into('>B', buffer, cursor, (self.data[i] // 0x11 << 4) | (self.data[i + 1] // 0x11))
                cursor += 1
        elif format in [513, 1025, 3]:
            for i in range(len(self.data)):
                pixel = self.data[i]
                if format == 3:
                    struct.pack_into('>4B', buffer, cursor, *[int(p*255) for p in pixel])
                    cursor += 4
                else:
                    buffer[cursor] = pixel
                    cursor += 1

        return buffer
