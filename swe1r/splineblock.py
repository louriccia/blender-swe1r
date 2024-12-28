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
from .general import *
from .modelblock import DataStruct, FloatPosition, FloatVector
from ..popup import show_custom_popup
from .spline_map import spline_map

class SplinePoint(DataStruct):
    def __init__(self):
        super().__init__('>8h48x10h')
        self.next = []
        self.previous = []
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
        next_count, previous_count, next1, next2, previous1, previous2, previous3, previous4, self.progress, *self.unk_set, self.unk = struct.unpack_from(self.format_string, buffer, cursor)
        self.next = [next1, next2][:next_count]
        self.previous = [previous1, previous2, previous3, previous4][:previous_count]
        self.position.read(buffer, cursor + 16)
        self.rotation.read(buffer, cursor + 28)
        self.handle1.read(buffer, cursor + 40)
        self.handle2.read(buffer, cursor + 52)
        
        return self
    
    def write(self, buffer, cursor):
        next_count = len(self.next)
        previous_count = len(self.previous)
        self.next = self.next + [-1] * (2 - len(self.next))
        self.previous = self.previous + [-1] * (4 - len(self.previous))
        struct.pack_into(self.format_string, buffer, cursor, next_count, previous_count, *self.next, *self.previous, self.progress, *self.unk_set, self.unk) 
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
    
    def unmake(self, point, object):
        co = object.matrix_world @ point.co
        handle_left = object.matrix_world @ point.handle_left
        handle_right = object.matrix_world @ point.handle_right
        self.position = FloatPosition().from_array([c/.01 for c in co])
        self.rotation = FloatVector().from_array([0, 0, 1])
        self.handle1 = FloatPosition().from_array([c/.01 for c in handle_left])
        self.handle2 = FloatPosition().from_array([c/.01 for c in handle_right])
        return self
    
    def to_array(self):
        return [*self.next, 
                *self.previous, 
                *self.position.to_array(),
                *self.rotation.to_array(),
                *self.handle1.to_array(),
                *self.handle2.to_array(),
                self.progress,
                *self.unk_set,
                self.unk]
    
    def from_array(self, data):
        self.next, self.previous = data[:8]
        self.position.from_array(data[8:11])
        self.rotation.from_array(data[11:14])
        self.handle1.from_array(data[14:17])
        self.handle2.from_array(data[17:20])
        self.progress, *self.unk_set, self.unk = data[20:]
    
class Spline(DataStruct):
    def __init__(self, id = None):
        super().__init__('>2H2I4B')
        self.id = id
        self.unk = 1 # always 1 spline visibility?
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
            previous = None if len(point.previous) == 0 else point.previous[0]
            next = None if len(point.next) == 0 else point.next[0]
            
            if previous in already and new:
                #the point that is included with the new polyline is made
                # a dup of the point where this path branches off of main spline
                self.points[previous].make(polyline) 
                new = False
                polyline.bezier_points.add(1) #add a new slot for the unique point
                
            point.make(polyline)
            already.append(i)
            
            if next in already or len(point.next) == 0: #we have reached the end of a path
                if 0 in point.next:
                    polyline.use_cyclic_u = True #close main spline
                else: #dup the point where the path rejoins main spline
                    polyline.bezier_points.add(1)
                    self.points[next].make(polyline)
                if i < len(self.points) - 1:
                    polyline = curveData.splines.new('BEZIER') #start a new path
                    new = True
                continue #skip adding a new point since a new polyline comes with a point already
                    
            polyline.bezier_points.add(1)
        
        curveOB = bpy.data.objects.new("spline", curveData)
        curveOB.scale = (scale, scale, scale)
        curveOB['id'] = self.id
        return curveOB
    
    def calculate_progress(self, loop):
        # calculate progress/indexing
        path_list = []
        current = [0]
        end = False
        while end is False:
            
            next = []
            current_unique = list(set(current))
            for i in current_unique:
                point = self.points[i]
                if len(point.previous) > current.count(point.id):
                    next.extend([point.id]*current.count(point.id))
                    continue 
                if len(point.next) == 0:
                    end = True
                else:
                    next.extend(point.next)

            if 0 in next:
                if len(next) > 1:
                    raise ValueError("All paths must join before and split after starting line! You cannot have shortcuts that go around the finish line.")
                end = True

            path_list.append(current_unique)
            current = next

        for i, path in enumerate(path_list):
            for p in path:
                point = self.points[p]
                point.progress = i
                if i == len(path_list) - 1 and not loop:
                    point.progress = 0
    
    def unmake(self, collection):
        spline_objects = [obj for obj in collection.objects if obj.type == 'CURVE']
        
        if len(spline_objects) < 1:
            show_custom_popup(bpy.context, "No Spline Object", "No spline object found in the selected collection.")
            return
        if len(spline_objects) > 1:
            show_custom_popup(bpy.context, "Too Many Splines", "Multiple splines found in the selected collection. Only one spline can be exported.")
            return
        
        spline_object = spline_objects[0]
        # if 'id' in spline_object:
        #     self.id = spline_object['id']
        # else:
        self.id = spline_map[int(collection.export_model)]
        splines = spline_object.data.splines
        
        #find bezier splines
        paths = [spline for spline in splines if spline.type == 'BEZIER'] # and len(spline.bezier_points)>=2
        
        if len(paths) == 0:
            show_custom_popup(bpy.context, "No bezier splines", "No bezier splines were found in the selected collection")
            return
        
        #sort descending by number of points
        longest_paths = sorted(paths, key = lambda spline: len(spline.bezier_points), reverse=True)
        looped_paths = sorted(paths, key = lambda spline: spline.use_cyclic_u, reverse=True)
        alt_paths = []
        main_path = None
        loop = False
        
        #find main path
        if looped_paths[0].use_cyclic_u:
            main_path = looped_paths[0]  
            if len(looped_paths) > 1:
                alt_paths = [spline for spline in longest_paths[1:] if spline.use_cyclic_u is False]
            loop = True
        else:
            main_path = longest_paths[0]
            if len(longest_paths) > 1:
                alt_paths = longest_paths[1:]

        #begin deconstruction        
        segment_count = 0
        point_count = 0
        
        main_len = len(main_path.bezier_points)
        count = main_len + sum([len(path.bezier_points) - 2 for path in alt_paths])
        if count > 255:
            raise ValueError(f"Too many spline points. Splines that contain more than 255 points are not supported. This scene contains {count} points.")
        
        
        #add all points from main_path
        for i, point in enumerate(main_path.bezier_points):
            p = SplinePoint().unmake(point, spline_object)
            p.id = point_count
            
            if i == 0 and loop:
                p.previous.append(main_len - 1)
            elif i != 0: 
                p.previous.append(point_count - 1)
                
            if i == main_len - 1 and loop:
                p.next.append(0)
            elif i != main_len - 1:
                p.next.append(point_count + 1)
                
            self.points.append(p)
            point_count += 1
            segment_count += 1
        
        self.calculate_progress(loop)
        
        for k, path in enumerate(alt_paths):
            
            # first and last points will be dups of main spline or existing path
            first = path.bezier_points[0]
            last = path.bezier_points[-1]
            
            # find index of existing points
            start = self.find_closest(first.co, 'start')
            end = self.find_closest(last.co, 'end')
            points = path.bezier_points[1:-1]
             
            # check if path needs to be inverted
            # this prevents a path from ending on an earlier point than where it started
            if self.points[start].progress > self.points[end].progress:
                tmp = start
                start = end
                end = tmp
                points.reverse()
            
            # loop through and add points of path
            for i, point in enumerate(points):
                p = SplinePoint().unmake(point, spline_object)
                p.id = point_count
                
                if i == 0: # start of path connects to existing point
                    p.previous.append(start)
                    self.points[start].next.append(point_count)
                if i == len(points) - 1: # end of path connects to existing point
                    p.next.append(end)
                    self.points[end].previous.append(point_count)
                    
                if not len(p.previous):
                    p.previous.append(point_count - 1)
                if not len(p.next):
                    p.next.append(point_count + 1)
                
                self.points.append(p)
                point_count += 1
                segment_count += 1
            
            segment_count += 1
            self.calculate_progress(loop)
            
        splits = 0
        for i, point in enumerate(self.points):
            point.unk_set[0] = i
            if len(point.next) == 2:
                point.unk_set[1] = len(self.points) + splits
                splits += 1
            if i == len(self.points) - 1 and not loop:
                point.unk_set[0] = 0
            
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
            if cap is "start" and len(point.next) >= 2:
                continue
            if cap is "end" and len(point.previous) >= 4:
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


