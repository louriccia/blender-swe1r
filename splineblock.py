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
from .readwrite import *
from .modelblock import DataStruct, FloatPosition, FloatVector
from .popup import show_custom_popup

class SplinePoint(DataStruct):
    def __init__(self):
        super().__init__('>8h48x10h')
        self.next_count = 1
        self.previous_count = 1
        self.next1 = -1
        self.next2 = -1
        self.previous1 = -1
        self.previous2 = -1
        self.unknown1 = 0
        self.unknown2 = 0
        self.position = FloatPosition()
        self.rotation = FloatVector()
        self.handle1 = FloatPosition()
        self.handle2 = FloatPosition()
        self.progress = -1
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
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, self.next_count, self.previous_count, self.next1, self.next2, self.previous1, self.previous2, self.unknown1, self.unknown2, self.progress, *self.unk_set, self.unk) 
        self.position.write(buffer, cursor + 16)
        self.rotation.write(buffer, cursor + 28)
        self.handle1.write(buffer, cursor + 40)
        self.handle2.write(buffer, cursor + 52)
    
    def make(self, polyline):
        polyline.bezier_points[-1].handle_left_type = 'FREE'
        polyline.bezier_points[-1].handle_right_type = 'FREE'
        polyline.bezier_points[-1].co = tuple([p for p in self.position.to_array()])
        polyline.bezier_points[-1].handle_left =  tuple([p for p in self.handle1.to_array()])
        polyline.bezier_points[-1].handle_right =  tuple([p for p in self.handle2.to_array()])
    
    def unmake(self, point):
        self.position = FloatPosition().from_array([c for c in point.co])
        self.rotation = FloatVector().from_array([0, 0, 1])
        self.handle1 = FloatPosition().from_array([c for c in point.handle_left])
        self.handle2 = FloatPosition().from_array([c for c in point.handle_right])
        return self
    
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
    def __init__(self, id = None):
        super().__init__('>2H2I4B')
        self.id = id
        self.unk = 1 # always 1
        self.unk1 = 0
        self.point_count = 0
        self.segment_count = 0
        self.unk2 = 1 # always 1
        self.unk3 = 0
        self.unk4 = 0
        self.unk5 = 0
        self.points = []
        
    def read(self, buffer):
        if self.id is None:
            return
        cursor = 0
        self.unk, self.unk1, self.point_count, self.segment_count, self.unk2, self.unk3, self.unk4, self.unk5 = struct.unpack_from(self.format_string, buffer, cursor)
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
            
            if point.previous1 in already and new:
                #the point that is included with the new polyline is made
                # a dup of the point where this path branches off of main spline
                self.points[point.previous1].make(polyline) 
                new = False
                polyline.bezier_points.add(1) #add a new slot for the unique point
                
            point.make(polyline)
            already.append(i)
            
            if point.next1 in already: #we have reached the end of a path
                if point.next1 == 0: #main spline should always close with 0... hopefully...
                    polyline.use_cyclic_u = True #close main spline
                else: #dup the point where the path rejoins main spline
                    polyline.bezier_points.add(1)
                    self.points[point.next1].make(polyline)
                if i < len(self.points) - 1:
                    polyline = curveData.splines.new('BEZIER') #start a new path
                    new = True
                continue #skip adding a new point since a new polyline comes with a point already
                    
            polyline.bezier_points.add(1)
        
        curveOB = bpy.data.objects.new("spline", curveData)
        curveOB.scale = (scale, scale, scale)
        curveOB['id'] = self.id
        return curveOB
    
    def unmake(self, collection):
        spline_objects = [obj for obj in collection.objects if obj.type == 'CURVE']
        
        if len(spline_objects) < 1:
            show_custom_popup(bpy.context, "No Spline", "No spline object found in the selected collection.")
            return
        if len(spline_objects) > 1:
            show_custom_popup(bpy.context, "Too Many Splines", "Multiple splines found in the selected collection. Only one spline can be exported.")
            return
        
        spline_object = spline_objects[0]
        self.id = spline_object['id']
        splines = spline_object.data.splines
        main_paths = [spline for spline in splines if spline.use_cyclic_u and spline.type == 'BEZIER']
        alt_paths = [spline for spline in splines if spline.use_cyclic_u is False and spline.type == 'BEZIER']
        
        if len(main_paths) < 1:
            show_custom_popup(bpy.context, "No Main Spline", "You must create a closed bezier spline using Active Spline > Cyclic U")
            return
        if len(main_paths) > 1:
            show_custom_popup(bpy.context, "Too Many Closed Splines", "Multiple closed bezier splines found in the spline object. Only one closed spline can be the main spline.")
            return
        
        main_path = main_paths[0]
        segment_count = 0
        point_count = 0
        #add all points from main_path
        for i, point in enumerate(main_path.bezier_points):
            p = SplinePoint().unmake(point)
            p.id = point_count
            p.previous1 = point_count - 1
            p.next1 = point_count + 1
            if i == 0:
                p.previous1 = len(main_path.bezier_points) - 1
            if i == len(main_path.bezier_points) - 1:
                p.next1 = 0
                
            self.points.append(p)
            point_count += 1
            segment_count += 1
            
        for path in alt_paths:
            
            #first and last points will be dups of main spline or existing path
            first = path.bezier_points[0]
            last = path.bezier_points[-1]
            
            #find index of existing points
            start = self.find_closest(first.co, 'start')
            end = self.find_closest(last.co, 'end')
            
            #loop through and add points of path
            points = path.bezier_points[1:-1]
            for i, point in enumerate(points):
                p = SplinePoint().unmake(point)
                p.id = point_count
                p.previous1 = point_count - 1
                p.next1 = point_count + 1
                if i == 0:
                    p.previous1 = start
                    self.points[start].next_count += 1
                    self.points[start].next2 = point_count
                if i == len(points) - 1:
                    p.next1 = end
                    self.points[end].previous_count += 1
                    self.points[end].previous2 = point_count
                self.points.append(p)
                point_count += 1
                segment_count += 1
            
            segment_count += 1
    
        
        # calculate progress/indexing
        path_list = []
        current = [0]
        end = False
        while end is False:
            next = []
            for i in list(set(current)):
                point = self.points[i]
                if point.previous_count == 2 and current.count(point.id) < 2:
                    next.append(point.id)
                    continue 
                next.append(self.points[point.next1].id)
                if point.next_count == 2:
                    next.append(self.points[point.next2].id)
                    
            if 0 in next:
                end = True
            
            path_list.append(list(set(current)))
            current = next
        
        for i, path in enumerate(path_list):
            for p in path:
                point = self.points[p]
                point.progress = i
                
        splits = 0
        for i, point in enumerate(self.points):
            point.unk_set[0] = i
            if point.next_count == 2:
                point.unk_set[1] = len(self.points) + splits
                splits += 1
        
        # LIMITATIONS:
        # cannot split or join more than 2 times on any point
        # cannot have alt paths that start before and end after the finish line on main spline
                   
        self.point_count = len(self.points)
        self.segment_count = segment_count
        
        return self
        
    def find_closest(self, co, cap = 'start'):
        closest_index = None
        closest_distance = float('inf')
        
        for i, point in enumerate(self.points):
            if cap is "start" and point.next_count == 2:
                continue
            if cap is "end" and point.previous_count == 2:
                continue
            distance_vec = (d - co[j] for j, d in enumerate(point.position.to_array()))
            distance = math.sqrt(sum([d**2 for d in distance_vec]))
            
            if distance < closest_distance:
                closest_index = i
                closest_distance = distance
        return closest_index
    
    def write(self):
        buffer = bytearray(8000000)
        cursor = 0
        struct.pack_into(self.format_string, buffer, cursor, self.unk, self.unk1, self.point_count, self.segment_count, self.unk2, self.unk3, self.unk4, self.unk5)
        cursor += self.size
        for point in self.points:
            point.write(buffer, cursor)
            cursor += point.size
        return buffer[:cursor]
    
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

