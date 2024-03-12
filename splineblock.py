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
from .modelblock import DataStruct, FloatPosition, FloatVector

class SplinePoint(DataStruct):
    def __init__(self):
        super().__init__('>8h48x10h')
        self.next_count = 0
        self.previous_count = 0
        self.next1 = 0
        self.next2 = 0
        self.previous1 = 0
        self.previous2 = 0
        self.unknown1 = 0
        self.unknown2 = 0
        self.position = FloatPosition()
        self.rotation = FloatVector()
        self.handle1 = FloatPosition()
        self.handle2 = FloatPosition()
        self.progress = 0
        self.unk_set = [-1 for i in range(8)]
        self.unk = -1
        
    def __str__(self):
        return str(self.to_array())
    
    def read(self, buffer, cursor):
        self.next_count, self.previous_count, self.next1, self.next2, self.previous1, self.previous2, self.unknown1, self.unknown2, self.progress, *self.unk_set, self.unk = struct.unpack_from(self.format_string, buffer, cursor)
        self.position.read(buffer, cursor + 16)
        self.rotation.read(buffer, cursor + 28)
        self.handle1.read(buffer, cursor + 40)
        self.handle2.read(buffer, cursor + 52)
        
        return self
    
    def make(self, polyline, scale):
        polyline.bezier_points[-1].handle_left_type = 'FREE'
        polyline.bezier_points[-1].handle_right_type = 'FREE'
        polyline.bezier_points[-1].co = tuple([p*scale for p in self.position.to_array()])
        polyline.bezier_points[-1].handle_left =  tuple([p*scale for p in self.handle1.to_array()])
        polyline.bezier_points[-1].handle_right =  tuple([p*scale for p in self.handle2.to_array()])
    
    def unmake(spline):
        pass
    
    def to_array(self):
        return [self.next_count, 
                self.previous_count, 
                self.next1, 
                self.next2, 
                self.previous1, 
                self.previous2, 
                self.unknown1, 
                self.unknown2, 
                *self.position.to_array(),
                *self.rotation.to_array(),
                *self.handle1.to_array(),
                *self.handle2.to_array(),
                self.progress,
                *self.unk_set,
                self.unk]
    
    def from_array(self, data):
        self.next_count, self.previous_count, self.next1, self.next2, self.previous1, self.previous2, self.unknown1, self.unknown2 = data[:8]
        self.position.from_array(data[8:11])
        self.rotation.from_array(data[11:14])
        self.handle1.from_array(data[14:17])
        self.handle2.from_array(data[17:20])
        self.progress, *self.unk_set, self.unk = data[20:]
    
class Spline(DataStruct):
    def __init__(self, id):
        super().__init__('>4I')
        self.id = id
        self.unk = None
        self.point_count = 0
        self.segment_count = 0
        self.unk2 = None
        self.points = []
        
    def read(self, splineblock):
        
        self.splineblock = splineblock
        if self.id is None:
            return
        spline_buffers = splineblock.read([self.id])
        buffer = spline_buffers[0][0]
        cursor = 0
        self.unk, self.point_count, self.segment_count, self.unk2 = struct.unpack_from(self.format_string, buffer, cursor)
        cursor += self.size
        for i in range(self.point_count):
            point = SplinePoint().read(buffer, cursor)
            self.points.append(point)
            cursor += point.size
        return self
    
    def make(self, scale):
        curveData = bpy.data.curves.new("name", type='CURVE')
        curveData.dimensions = '3D'
        curveData.resolution_u = 10
        
        polyline = curveData.splines.new('BEZIER')
        already = []
        new = False
        
        for i, point in enumerate(self.points):
            
            if i is not 0 and new is False:
                polyline.bezier_points.add(1)
            
            if point.previous1 in already and new and i is not 0:
                self.points[point.previous1].make(polyline, scale)
                
            point.make(polyline, scale)
            already.append(i)
            
            if point.next1 == 0:
                polyline.use_cyclic_u = True #close spline
                if i < len(self.points):
                    polyline = curveData.splines.new('BEZIER') #start a new one
                    new = True
            elif point.next1 in already:
                self.points[point.next1].make(polyline, scale)
                if i < len(self.points):
                    polyline = curveData.splines.new('BEZIER') #start a new one
                    new = True
                
        curveOB = bpy.data.objects.new("spline", curveData)
        return curveOB
    
    def unmake(self):
        pass
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, self.unk, self.point_count, self.segment_count, self.unk2)
        cursor += self.size
        for point in self.points:
            point.write(buffer, cursor)
            cursor += point.size
        return cursor
    
    def invert(self):
        inverted_points = []
        double_count = 0
        biggest_num0 = 0

        for point in self.points:
            if point.progress > biggest_num0:
                biggest_num0 = point.progress

        for i, point in enumerate(self.points):
            inverted_point = SplinePoint.from_array(
                [
                    point.next_count,
                    point.previous_count,
                    point.previous1,
                    point.previous2,
                    point.next1,
                    point.next2,
                    point.unknown1,
                    point.unknown2,
                    *point.position.to_array(),
                    *point.rotation.to_array(),
                    *point.handle2.to_array(),
                    *point.handle1.to_array(),
                    0 if point.progress == 0 else biggest_num0 - point.progress + 1,
                    *point.unk_set,
                    point.unk
                ]
            )
            
            if point.next_count == 2:
                double_count += 1

            inverted_points.append(inverted_point)
        self.points = inverted_points
        return self

