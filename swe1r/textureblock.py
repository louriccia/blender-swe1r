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
import hashlib
import numpy as np
import math
import bpy
from ..utils import euclidean_distance, data_name_format
from .modelblock import DataStruct

format_map = {
    3: 4,
    512: 0.5,
    513: 1,
    1024: 0.5,
    1025: 1
}

def compute_hash(buffer):
    return hashlib.md5(buffer).hexdigest()

def compute_image_hash(image):
    # Assume 'image' is a Blender image object
    pixels = image.pixels[:]  # Get pixel data
    pixel_bytes = bytes([int(p * 255) for p in pixels])  # Convert to 0-255 range
    return compute_hash(pixel_bytes)

def reduce_colors(image_array, num_colors=255, max_iter=3):
    """
    Reduce the number of colors in an image to a specified number using k-means clustering.
    
    Parameters:
    - image_array: numpy array of shape (height, width, 4) or (num_pixels, 4)
    - num_colors: number of colors to reduce to (default 255)
    - max_iter: maximum number of iterations for convergence
    
    Returns:
    - reduced_image: numpy array of the same shape as image_array with reduced colors
    """
    # Reshape image to (num_pixels, 4)
    pixels = image_array.reshape(-1, 4).astype(np.float32)  # Ensure float for computations
    # Handle small images by limiting num_colors
    unique_pixels = np.unique(pixels, axis=0)
    actual_num_colors = min(len(unique_pixels), num_colors)
    
    if len(unique_pixels) < num_colors:
        centroids = unique_pixels
    else:
        np.random.seed(42)
        centroids = pixels[np.random.choice(pixels.shape[0], actual_num_colors, replace=False)]

    for iteration in range(max_iter):
        distances = np.linalg.norm(pixels[:, None, :] - centroids[None, :, :], axis=2)
        labels = np.argmin(distances, axis=1)
        
        new_centroids = np.array([
            pixels[labels == k].mean(axis=0) if np.any(labels == k) else centroids[k]
            for k in range(actual_num_colors)
        ])
        
        if np.allclose(centroids, new_centroids, atol=1e-4):
            break
        
        centroids = new_centroids

    indices = labels
    # Convert centroids to uint8 for palette
    palette = centroids
    
    return indices, palette


def page_width_padding(width, format):
    assert format in [3, 512, 513, 1024, 1025], f"Unexpected texture format {format}"
    
    if format in [513, 1025]:
        return (width + 0x7) & 0xFFFFFFF8
    elif format in [512, 1024]:
        return (width + 0xF) & 0xFFFFFFF0
    elif format == 3:
        return (width + 0x1) & 0xFFFFFFFE

def next_power_of_2(value):
    next = 16
    
    while next < value:
        next = next << 1
    return next

class Texture():
    def __init__(self, id, format = 513, width = 32, height = 32):
        assert int(id) != 65535, f"Unexpected texture index {id}"
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
        #TODO: Detect broken PC textures via hash and correct them automatically
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
        
        #make image
        for i in range(self.height):
            for j in range(self.width):
                ind = i * self.width + j
                p = None
                color = None

                if self.format in [512, 513]:
                    color = palette[pixels[ind]].to_array()

                elif self.format in [1024, 1025]:
                    p = pixels[ind]
                    color = [p, p, p, 1.0]

                elif self.format == 3:
                    p = pixels[ind]
                    color = [i / 255 for i in p]
                    
                image_pixels.extend(color)
                
        if len(image_pixels):
            new_image.pixels = [p for p in image_pixels]
        new_image['format'] = self.format
        new_image['id'] = self.id

        hash = compute_image_hash(new_image)
        new_image['internal_hash'] = hash
        
        return new_image

    def unmake(self, image, override_format = None):
        
        #resize image if needed
        TEXTURE_MAX_SIZE = 128
        width, height = image.size
        if width > TEXTURE_MAX_SIZE and width > height:
            height = int(height*TEXTURE_MAX_SIZE/width)
            width = TEXTURE_MAX_SIZE
        elif height > TEXTURE_MAX_SIZE:
            height = int(width*TEXTURE_MAX_SIZE/height)
            width = TEXTURE_MAX_SIZE
            
        width = next_power_of_2(width)
        height = next_power_of_2(height)
            
        if width != image.size[0] or height != image.size[1]:
            image.scale(width, height)
        
        self.width, self.height = image.size
        
        
        #check if we need format 3
        image_data = np.array(image.pixels[:])  # Convert pixel data to a NumPy array
        pixels = image_data.reshape(-1, 4)
        palette = np.unique(pixels, axis=0)
        greyscale = True
        for color in palette:
            if color[3] < 1.0 and color[3] > 0:
                self.format = 3
                image['format'] = 3
                self.palette = Palette(self)
                self.pixels = Pixels(self).unmake(image, override_format = 3)
                return self
            if not np.all(color[:3] == color[0]):
                greyscale = False
            
        if greyscale:    
            self.format = 1024   
            self.pixels = Pixels(self).unmake(image, self.format)
            self.palette = Palette(self)
            return self
            
        if len(palette > 255): #check if we need palettization
            reduced_image, palette = reduce_colors(image_data, num_colors=255, max_iter = 1)
            self.format = 513
            image['format'] = self.format
            self.pixels = Pixels(self)
            self.pixels.data = reduced_image
            self.palette = Palette(self)
            self.palette.data = [RGBA5551().from_array(color) for color in palette]
            return self
        elif len(palette) <= 16: #check if we can optimize for smaller palettes
            self.format = 512
            
        
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
        self.a = ((pallete_color >> 0) & 0x1) * 1.0
        self.b = (((pallete_color >> 1) & 0x1F) / 0x1F)
        self.g = (((pallete_color >> 6) & 0x1F) / 0x1F)
        self.r = (((pallete_color >> 11) & 0x1F) / 0x1F)
        if (self.r + self.g + self.b) > 0 and self.a == 0:
            self.a = 1.0
        return self
    def to_array(self):
        return [self.r, self.g, self.b, self.a]
    def from_array(self, arr):
        if len(arr) == 3:
            arr.append(1.0)
        self.r, self.g, self.b, self.a = arr
        return self
    def write(self, buffer, cursor):
        r = int(self.r * 0x1F) << 11
        g = int(self.g * 0x1F) << 6
        b = int(self.b * 0x1F) << 1
        a = int(self.a)
        color = (((r | g) | b) | a)
        struct.pack_into(self.format_string, buffer, cursor, color)
        return cursor + self.size
    def distance(self, other):
        return sum([abs(self.r - other.r), abs(self.g - other.g), abs(self.b - other.b)])
    def __eq__(self, other):
        return self.r == other.r and self.g == other.g and self.b == other.b and self.a == other.a
    
class Palette():
    def __init__(self, texture):
        self.texture = texture
        self.data = []
        self.map = {}
    
    def read(self, buffer):
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
    
        image_data = np.array(image.pixels[:])  # Convert pixel data to a NumPy array
    
        pixels = image_data.reshape(-1, 4)
        palette = np.unique(pixels, axis=0)
        for pixel in palette[:threshold]:
            color = RGBA5551().from_array([ max(0, min(j, 1.0)) for j in pixel])
            self.data.append(color)
        
        return self
    
    def write(self):
        buffer = bytearray(len(self.data) * 2)
        cursor = 0

        for color in self.data:
            cursor = color.write(buffer, cursor)

        return buffer
    
    def closest(self, target):
        
        closest_color = None
        closest_distance = 0
        for i, color in enumerate(self.data):
            if color == target:
                return i
            distance = target.distance(color)
            if closest_color is None or distance < closest_distance:
                closest_color = i
                closest_distance = distance
        
        return closest_color
    
class Pixels():
    def __init__(self, texture):
        self.texture = texture
        self.data = []
        
    def read(self, buffer):
        if buffer is None:
            return self.data
        
        cursor = 0
        pixel_count = self.texture.width * self.texture.height
        padded_width = page_width_padding(self.texture.width, self.texture.format)
        
        # if self.texture.format == 3:
        #     for i in range(pixel_count):
        #         r, g, b, a = struct.unpack('>BBBB', buffer[cursor:cursor + 4])
        #         self.data.append([r, g, b, a])
        #         cursor += 4

        # elif self.texture.format == 512:
        #     for i in range(min(round(pixel_count/2), len(buffer))):
        #         p = buffer[cursor]
        #         pixel_0 = (p >> 4) & 0xF
        #         pixel_1 = p & 0xF
        #         self.data.extend([pixel_0, pixel_1])
        #         cursor += 1

        # elif self.texture.format == 513:
        #     for i in range(pixel_count):
        #         pixel = buffer[cursor]
        #         self.data.append(pixel)
        #         cursor += 1

        # elif self.texture.format == 1024:
        #     for i in range(round(pixel_count/2)):
        #         p = buffer[cursor]
        #         pixel_0 = ((p >> 4) & 0xF) * 0x11
        #         pixel_1 = (p & 0xF) * 0x11
        #         self.data.extend([pixel_0, pixel_1])
        #         cursor += 1

        # elif self.texture.format == 1025:
        #     for i in range(pixel_count):
        #         pixel = buffer[cursor]
        #         self.data.append(pixel)
        #         cursor += 1


        #for each row in the pixel buffer
        for r in range(self.texture.height):

            cursor = r * padded_width * format_map[self.texture.format]
            #for each pixel in a row
            for p in range(self.texture.width):
                if cursor >= len(buffer) :
                    print("buffer was shorter than expected")
                    return self.data
                
                p8 = buffer[math.floor(cursor)]
                
                if self.texture.format == 3:
                    r = p8
                    g = buffer[int(cursor) + 1]
                    b = buffer[int(cursor) + 2]
                    a = buffer[int(cursor) + 3]
                    self.data.append([r, g, b, a])
                    cursor += 4
                    
                elif self.texture.format in [512, 1024]:
                    p4 = (p8 >> 4) & 0xF
                    if cursor % 1:
                        p4 = (p8) & 0xF
                    self.data.append(p4)
                    cursor += 0.5
                    
                elif self.texture.format in [513, 1025]:
                    self.data.append(p8)
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
        
        if format == 3:
            self.data = image.pixels    
        elif format in [1024, 1025]:
            for i in range(0, len(image.pixels), 4):
                pixel = image.pixels[i: i+4]
                self.data.append(sum(pixel[:3])/3)
        elif format in [512, 513]:
            for i in range(0, len(image.pixels), 4):
                pixel = image.pixels[i: i+4]
                color = RGBA5551().from_array([int(p*255) for p in pixel])
                closest = palette.closest(color)
                self.data.append(closest)
                
        return self

    def write(self):

        padded_width = page_width_padding(self.texture.width, self.texture.format)
        format = int(self.texture.format)
        buffer = bytearray(int(self.texture.height * self.texture.width * format_map[format]))
        
        cursor = 0
        i = 0
        
        # if format in [512, 1024]:
        #     for i in range(0, len(self.data), 2):
        #         if format == 512:
        #             struct.pack_into('>B', buffer, cursor, (self.data[i] << 4) | self.data[i + 1])
        #         elif format == 1024:
        #             struct.pack_into('>B', buffer, cursor, (self.data[i] // 0x11 << 4) | (self.data[i + 1] // 0x11))
        #         cursor += 1
        # elif format == 3:
        #     for pixel in self.data:
        #         struct.pack_into('>B', buffer, cursor, int(pixel*255))
        #         cursor += 1
        # elif format in [513, 1025]:
        #     for i in range(len(self.data)):
        #         pixel = self.data[i]
        #         buffer[cursor] = pixel
        #         cursor += 1
                
        print('writing', self.texture.id, self.texture.height, self.texture.width, self.texture.format)
        
        data = np.array(self.data, dtype=np.float32)  # Convert to NumPy array for faster processing
        buffer = np.array(buffer, dtype=np.uint8)    # Use NumPy for the buffer
        height, width = self.texture.height, self.texture.width
        padded_width_format = padded_width * format_map[format]
        #for each row in the pixel buffer
        cursor_increment = format_map[format]
        for r in range(height):
            #cursor = r * width # padded_width_format
            row_start = r * width  # Avoid computing `i` in every iteration

            for p in range(width):
                if cursor >= len(buffer):
                    print("buffer was shorter than expected")
                    return buffer

                pixel = data[row_start + p]
                if format in [512, 1024]:
                    p8 = buffer[int(cursor)]
                    if cursor % 1 == 0:
                        p8 |= int(pixel) << 4
                    else:
                        p8 |= int(pixel)
                    buffer[int(cursor)] = p8
                elif format in [513, 1025]:
                    buffer[cursor] = int(pixel)
                elif format == 3:
                    pixel_data = (np.clip(data[row_start * 4 + p * 4: row_start * 4 + (p + 1) * 4], 0.0, 1.0) * 255).astype(np.uint8)
                    buffer[cursor:cursor + 4] = pixel_data
                cursor += cursor_increment

        return bytearray(buffer.tobytes())
