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

def image_pixels(image):
    """image.pixels as a flat float32 array; slicing image.pixels in Python is very slow."""
    pixels = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(pixels)
    return pixels

def compute_image_hash(image):
    # each channel truncated to 0..255, as int(p * 255)
    scaled = np.trunc(image_pixels(image).astype(np.float64) * 255)
    if len(scaled) and (scaled.min() < 0 or scaled.max() > 255):
        raise ValueError("bytes must be in range(0, 256)")
    return compute_hash(scaled.astype(np.uint8).tobytes())

def reduce_colors(image_array, num_colors=255, max_iter=3):
    """
    Reduce an image to at most num_colors colors.

    Uses popularity quantization: the most frequently used colors are kept
    EXACTLY and every remaining pixel is mapped to its nearest kept color. This
    preserves solid regions (a large white area stays pure white), unlike the
    previous k-means approach whose cluster means pulled bright colors toward
    grey and made white areas render noticeably darker in game.

    Parameters:
    - image_array: numpy array of shape (height, width, 4) or (num_pixels, 4)
    - num_colors: maximum number of palette colors
    - max_iter: unused, kept for backwards compatibility

    Returns:
    - indices: per-pixel index into the palette
    - palette: (num_colors, 4) array of RGBA colors in 0..1
    """
    pixels = image_array.reshape(-1, 4).astype(np.float32)
    unique_pixels, counts = np.unique(pixels, axis=0, return_counts=True)

    if len(unique_pixels) <= num_colors:
        palette = unique_pixels
    else:
        # keep the num_colors most-used colors, exactly
        top = np.argsort(counts)[::-1][:num_colors]
        palette = unique_pixels[top]

    # map every pixel to its nearest kept color
    distances = np.linalg.norm(pixels[:, None, :] - palette[None, :, :], axis=2)
    indices = np.argmin(distances, axis=1)

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

def deswizzle_tmem(texels, width, height):
    """Undo the N64 TMEM swizzle of a texture tile: on odd rows, swap adjacent 8-texel blocks.

    texels is a row-major (height * width) list of texels (palette indices, intensities or RGBA
    lists); a new list is returned. This is the replacement renderer's deswizzle_lod_texture
    (SW_RACER_RE dinput_hook/renderer_hook.cpp:641-686), which runs on the decoded texels, so the
    blocks are 8 texels whatever the format's bit depth. It skips tiles whose width is not a
    whole number of block pairs, and so does this. The renderer then rebuilds the mirror copies
    the game's converter baked into the upload; images here hold only the tile (mirroring is in
    the material's UV nodes), so there is nothing to rebuild.
    """
    if width <= 0 or height <= 0 or width % 16 or len(texels) < width * height:
        return texels
    out = list(texels)
    for y in range(1, height, 2):
        row = y * width
        for x in range(width):
            out[row + x + (8 if (x // 8) % 2 == 0 else -8)] = texels[row + x]
    return out

class Texture():
    def __init__(self, id, format = 513, width = 32, height = 32, swizzled = False, name = None):
        assert int(id) != 65535, f"Unexpected texture index {id}"
        self.id = id
        self.format = format
        self.width = width
        self.height = height
        self.palette = None
        self.pixels = None
        # stored in the N64's swizzled TMEM layout (a material texture with a mip chain, see
        # MaterialTexture.read); make() shows it deswizzled
        self.swizzled = swizzled
        self.name = name
    def read(self, pixel_buffer, palette_buffer):
        if self.id is None or self.id < 0:
            return
        if self.format in [512, 513]:
            self.palette = Palette(self)
            self.palette.read(palette_buffer)
            
        self.pixels = Pixels(self)
        self.pixels.read(pixel_buffer)
        if self.swizzled:
            self.pixels.data = deswizzle_tmem(self.pixels.data, self.width, self.height)
    def make(self, cache_dir=None):
        """
        Create and save texture image, using cached version if available.
        
        Args:
            cache_dir: Directory to save texture files. If None, creates in-memory only.
        
        Returns:
            bpy.types.Image: The created image (loaded from disk if cache_dir provided)
        """
        import os
        
        if int(self.id) < 0:
            return
        if self.pixels is None or not self.pixels:
            print(f"Texture {self.id} does not have any pixels")
            return

        if None in [self.format, self.width, self.height]:
            print(f"Texture {self.id} is missing width/height/format data")
            return
        
        tex_name = self.name or str(self.id)

        # Check if cached version exists
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
            filepath = os.path.join(cache_dir, f"texture_{self.id:04d}{'_lod' if self.swizzled else ''}.png")

            if os.path.exists(filepath):
                # Load from cache
                new_image = bpy.data.images.load(filepath)
                new_image['format'] = self.format
                new_image['id'] = self.id
                new_image.name = tex_name
                
                # Set proper alpha mode
                new_image.alpha_mode = 'CHANNEL_PACKED'  # or 'STRAIGHT'
                
                # Optionally verify/recompute hash
                hash = compute_image_hash(new_image)
                new_image['internal_hash'] = hash
                
                return new_image
        
        # Cache miss or no cache - generate the image

        # Create image WITH ALPHA CHANNEL
        new_image = bpy.data.images.new(tex_name, self.width, self.height, alpha=True)
        
        # Set the alpha mode BEFORE setting pixels
        new_image.alpha_mode = 'CHANNEL_PACKED'  # Use 'STRAIGHT' if your alpha is not premultiplied
        
        pixels = self.pixels.data
        palette = None if self.palette is None or self.palette.data is None else self.palette.data
        pixel_count = min(len(pixels), self.width * self.height)

        #make image
        if self.format in [512, 513]:
            colors = np.array([color.to_array() for color in palette], dtype=np.float64).reshape(-1, 4)
            image_pixels = colors[np.asarray(pixels[:pixel_count], dtype=np.intp)]
        elif self.format in [1024, 1025]:
            p = np.asarray(pixels[:pixel_count], dtype=np.float64) / (0xF if self.format == 1024 else 255)
            # the game converts intensity texels to 0xVVVV, so alpha is the intensity too (as on the
            # N64); combiners such as the pod shadows' PRIM.a * (1 - TEXEL0.a) depend on it
            image_pixels = np.stack([p, p, p, p], axis=1)
        elif self.format == 3:
            image_pixels = np.asarray(pixels[:pixel_count], dtype=np.float64).reshape(-1, 4) / 255

        if pixel_count:
            new_image.pixels.foreach_set(image_pixels.astype(np.float32).ravel())

        # A generated image only keeps its pixels in an in-memory buffer, which
        # Blender's undo stack does not serialize - after undo/redo the image
        # comes back regenerated as black. Packing embeds the pixels into the
        # datablock so they survive undo/redo (and .blend save/reload).
        new_image.pack()

        new_image['format'] = self.format
        new_image['id'] = self.id

        hash = compute_image_hash(new_image)
        new_image['internal_hash'] = hash
        
        # Save to disk if cache directory provided
        if cache_dir:
            # Important settings for transparency
            new_image.file_format = 'PNG'
            new_image.colorspace_settings.name = 'sRGB'  # or 'Non-Color' for data textures
            
            # Ensure alpha is saved
            new_image.filepath_raw = filepath
            
            # For image settings when saving
            scene = bpy.context.scene
            old_file_format = scene.render.image_settings.file_format
            old_color_mode = scene.render.image_settings.color_mode
            
            # Set PNG with RGBA
            scene.render.image_settings.file_format = 'PNG'
            scene.render.image_settings.color_mode = 'RGBA'
            scene.render.image_settings.color_depth = '8'  # or '16' for higher precision
            scene.render.image_settings.compression = 15  # 0-100, higher = smaller file
            
            new_image.save()
            
            # Restore old settings
            scene.render.image_settings.file_format = old_file_format
            scene.render.image_settings.color_mode = old_color_mode
            
            # Remove the in-memory image and reload from disk
            # This frees up memory while keeping the reference
            bpy.data.images.remove(new_image)
            new_image = bpy.data.images.load(filepath)
            
            # Re-add custom properties and settings to the reloaded image
            new_image['format'] = self.format
            new_image['id'] = self.id
            new_image['internal_hash'] = hash
            new_image.name = tex_name
            new_image.alpha_mode = 'CHANNEL_PACKED'
        
        return new_image

    def unmake(self, image, override_format = None):
        
        #resize image if needed
        TEXTURE_MAX_SIZE = 128
        width, height = image.size
        if width > TEXTURE_MAX_SIZE and width > height:
            height = int(height*TEXTURE_MAX_SIZE/width)
            width = TEXTURE_MAX_SIZE
        elif height > TEXTURE_MAX_SIZE:
            width = int(width*TEXTURE_MAX_SIZE/height)
            height = TEXTURE_MAX_SIZE
            
        width = next_power_of_2(width)
        height = next_power_of_2(height)
            
        if width != image.size[0] or height != image.size[1]:
            image.scale(width, height)
        
        self.width, self.height = image.size
        
        
        image_data = image_pixels(image).astype(np.float64)
        pixels = image_data.reshape(-1, 4)
        palette = np.unique(pixels, axis=0)

        # Intensity formats: the game shows these with alpha = intensity, so use them for grey
        # images whose alpha already is the intensity, or is opaque throughout (opaque render
        # modes ignore alpha). I4 holds exactly the 8-bit levels that are multiples of 17.
        grey = np.all(palette[:, 0] == palette[:, 1]) and np.all(palette[:, 1] == palette[:, 2])
        if grey and (np.all(palette[:, 3] == palette[:, 0]) or np.all(palette[:, 3] == 1.0)):
            levels = np.rint(palette[:, 0] * 255)
            self.format = 1024 if np.all(levels % 17 == 0) else 1025
            image['format'] = self.format
            self.pixels = Pixels(self).unmake(image, self.format)
            self.palette = Palette(self)
            return self

        #check if we need format 3
        if np.any((palette[:, 3] < 1.0) & (palette[:, 3] > 0)):
            self.format = 3
            image['format'] = 3
            self.palette = Palette(self)
            self.pixels = Pixels(self).unmake(image, override_format = 3)
            return self

        if len(palette) > 255: #check if we need palettization
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

        image['format'] = self.format
        self.palette = Palette(self).unmake(image, self.format)
        self.pixels = Pixels(self).unmake(image, self.format)
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
        # round, not truncate: an imported 5-bit level comes back from the 8-bit image a hair low,
        # and truncating dropped about half of all levels by one on every re-export
        r = round(self.r * 0x1F) << 11
        g = round(self.g * 0x1F) << 6
        b = round(self.b * 0x1F) << 1
        a = round(self.a)
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


        fast = self.read_rows(buffer, padded_width)
        if fast is not None:
            self.data = fast
            return self.data

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

    def read_rows(self, buffer, padded_width):
        """The pixels read below, decoded with numpy; None when the buffer is too short for every row."""
        width, height, format = self.texture.width, self.texture.height, self.texture.format
        row_bytes = int(padded_width * format_map[format])
        needed = (height - 1) * row_bytes + math.ceil(width * format_map[format]) if height else 0
        if needed > len(buffer):
            return None
        data = np.frombuffer(bytes(buffer[:height * row_bytes]).ljust(height * row_bytes, b'\0'), dtype=np.uint8)
        rows = data.reshape(height, row_bytes)
        if format == 3:
            return rows[:, :width * 4].reshape(-1, 4).tolist()
        if format in [512, 1024]:
            nibbles = np.stack([rows >> 4, rows & 0xF], axis=2).reshape(height, -1)
            return nibbles[:, :width].ravel().tolist()
        return rows[:, :width].ravel().tolist()

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
            self.data = image_pixels(image)
        elif format in [1024, 1025]:
            # intensity in the format's range (I4 0..15, I8 0..255); Pixels.write packs these
            # as-is, so 0..1 floats came out as 0 or 1, i.e. black
            levels = 0xF if format == 1024 else 0xFF
            pixels = image_pixels(image).reshape(-1, 4).astype(np.float64)
            intensity = np.clip(pixels[:, :3].sum(axis=1) / 3, 0.0, 1.0)
            self.data = np.rint(intensity * levels).astype(np.int64).tolist()
        elif format in [512, 513]:
            # Palette colors are stored as 0..1 floats (see Palette.unmake), so the lookup color
            # uses the same scale. Look each distinct color up once: the first palette entry
            # equal to it, else the nearest (Palette.closest).
            pixels = np.clip(image_pixels(image).reshape(-1, 4).astype(np.float64), 0.0, 1.0)
            colors, inverse = np.unique(pixels, axis=0, return_inverse=True)
            first = {}
            for i, color in enumerate(palette.data):
                first.setdefault(tuple(color.to_array()), i)
            indices = []
            for color in colors.tolist():
                index = first.get(tuple(color))
                if index is None:
                    index = palette.closest(RGBA5551().from_array(color))
                indices.append(index)
            self.data = np.asarray(indices)[np.asarray(inverse).ravel()].tolist()

        return self

    def write(self):

        padded_width = page_width_padding(self.texture.width, self.texture.format)
        format = int(self.texture.format)
        buffer = bytearray(int(self.texture.height * self.texture.width * format_map[format]))
        
        count = self.texture.height * self.texture.width
        data = np.asarray(self.data, dtype=np.float32).ravel()
        if format in [512, 1024]:
            # two 4-bit texels per byte, the first in the high nibble
            values = data[:count].astype(np.int64)
            if len(values) % 2:
                values = np.append(values, 0)
            packed = (values[0::2] << 4) | values[1::2]
        elif format in [513, 1025]:
            packed = data[:count].astype(np.int64)
        else:
            # RGBA32: each channel truncated to 0..255
            packed = (np.clip(data[:count * 4], 0.0, 1.0) * 255)
        packed = packed.astype(np.uint8).tobytes()
        buffer = np.frombuffer(packed.ljust(len(buffer), b'\0')[:len(buffer)], dtype=np.uint8)

        return bytearray(buffer.tobytes())
