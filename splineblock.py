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
import math
import os
from .readwrite import *
from .modelblock import DataStruct, FloatPosition, FloatVector

class SplinePoint(DataStruct):
    def __init__(self):
        super().__init__('>8h12x10h')
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
        
    
    def read(self, buffer, cursor):
        self.next_count, self.previous_count, self.next1, self.next2, self.previous1, self.previous2, self.unknown1, self.unknown2, self.progress, *self.unk_set, self.unk = struct.unpack_from(self.format_string, buffer, cursor)
        self.position.read(buffer, cursor + 16)
        self.rotation.read(buffer, cursor + 20)
        self.handle1.read(buffer, cursor + 24)
        self.handle2.read(buffer, cursor + 28)
        
        return self
    
    def make(self):
        pass
    
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
    def __init__(self):
        super().__init__('>4I')
        self.unk = None
        self.point_count = 0
        self.segment_count = 0
        self.unk2 = None
        self.points = []
        
    def read(self, buffer, cursor):
        self.unk, self.point_count, self.segment_count, self.unk2 = struct.unpack_from(self.format_string, buffer, cursor)
        for i in range(self.point_count):
            point = SplinePoint().read(buffer, cursor)
            self.points.append(point)
            cursor += point.size
        return self
    
    def make(self):
        scale = 0.01
        
        curveData = bpy.data.curves.new("name", type='CURVE')
        curveData.dimensions = '3D'
        curveData.resolution_u = 10
        
        polyline = curveData.splines.new('BEZIER')
        already = []
        for i, point in enumerate(self.points):
            #TODO test if curve can contain both a closed and open spline
            
            #detect main spline and create loop
            #if next is 0 (or one we have previously added)
            if point.next == 0:
                #cycle found
                continue
            
            polyline.bezier_points.add(1)
            polyline.bezier_points[index].handle_left_type = 'FREE'
            polyline.bezier_points[index].handle_right_type = 'FREE'
            polyline.bezier_points[index].co = tuple[point.position.to_array()*scale]
            polyline.bezier_points[index].handle_left =  tuple[point.handle1.to_array()*scale]
            polyline.bezier_points[index].handle_right =  tuple[point.handle2.to_array()*scale]
            already.append(i)
            #add alternate paths as disjoint curves
            #they will reproduce the points at which they split and rejoin the main spline
                    
            #previous point
            # previous = point.previous1
            # offset = -1
            # index = 0
            # if previous < self.point_count and previous >= 0:
            #     polyline.bezier_points.add(1)
            #     polyline.bezier_points[index].handle_left_type = 'FREE'
            #     polyline.bezier_points[index].handle_right_type = 'FREE'
            #     polyline.bezier_points[index].co = tuple[self.points[previous].position.to_array()*scale]
            #     polyline.bezier_points[index].handle_left =  tuple[self.points[previous].handle1.to_array()*scale]
            #     polyline.bezier_points[index].handle_right =  tuple[self.points[previous].handle2.to_array()*scale]
            #     index += 1
            # #current point
            # polyline.bezier_points[index].handle_left_type = 'FREE'
            # polyline.bezier_points[index].handle_right_type = 'FREE'
            # polyline.bezier_points[index].co = (float(row[9])*scale, float(row[10])*scale, float(row[11])*scale)
            # polyline.bezier_points[index].handle_left = (float(row[15])*scale, float(row[16])*scale, float(row[17])*scale)
            # polyline.bezier_points[index].handle_right = (float(row[18])*scale, float(row[19])*scale, float(row[20])*scale)
            # index += 1
            # #next point
            # next = point.next1
            # if next < self.point_count and next >= 0:
            #     polyline.bezier_points.add(1)
            #     polyline.bezier_points[index].handle_left_type = 'FREE'
            #     polyline.bezier_points[index].handle_right_type = 'FREE'
            #     polyline.bezier_points[index].co = (float(list_data[next][9])*scale, float(list_data[next][10])*scale, float(list_data[next][11])*scale)
            #     polyline.bezier_points[index].handle_left = (float(list_data[next][15])*scale, float(list_data[next][16])*scale, float(list_data[next][17])*scale)
            #     polyline.bezier_points[index].handle_right = (float(list_data[next][18])*scale, float(list_data[next][19])*scale, float(list_data[next][20])*scale)
                
        curveOB = bpy.data.objects.new("spline", curveData)
        curveOB.data.bevel_depth = 0.06
        curveOB.data.bevel_resolution = 10
        curveOB.data.resolution_u = 50
        material = bpy.data.materials.new('material_blank')
        material.use_nodes = True
        material.node_tree.nodes["Principled BSDF"].inputs[0].default_value = [0, 1, 0, 1]
        curveOB.data.materials.append(material)
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

