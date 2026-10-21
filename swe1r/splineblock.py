# Copyright (C) 2021-2024
# lightningpirate@gmail.com

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
from ..utils import show_custom_popup
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
    
    def make(self, bezier_point):
        bezier_point.handle_left_type = 'FREE'
        bezier_point.handle_right_type = 'FREE'
        bezier_point.co = tuple([p for p in self.position.to_array()])
        # handle1 is the incoming handle, handle2 the outgoing one: a segment a -> b is drawn
        # from a.position, a.handle2, b.handle1, b.position (swrSpline.c:136-139)
        bezier_point.handle_left =  tuple([p for p in self.handle1.to_array()])
        bezier_point.handle_right =  tuple([p for p in self.handle2.to_array()])
    
    def unmake(self, point, object, scale = 0.01):
        co = object.matrix_world @ point.co
        handle_left = object.matrix_world @ point.handle_left
        handle_right = object.matrix_world @ point.handle_right
        self.position = FloatPosition().from_array([c/scale for c in co])
        self.rotation = FloatVector().from_array([0, 0, 1])
        self.handle1 = FloatPosition().from_array([c/scale for c in handle_left])
        self.handle2 = FloatPosition().from_array([c/scale for c in handle_right])
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
        
        for indices, cyclic in self.decompose():
            polyline = curveData.splines.new('BEZIER') # comes with one point
            polyline.bezier_points.add(len(indices) - 1)
            for bezier_point, index in zip(polyline.bezier_points, indices):
                self.points[index].make(bezier_point)
            polyline.use_cyclic_u = cyclic

        curveOB = bpy.data.objects.new("spline", curveData)
        curveOB.scale = (scale, scale, scale)
        curveOB['id'] = self.id
        return curveOB

    def decompose(self):
        """Split the control point graph into Blender polylines: [(point indices, cyclic)].

        The first polyline is the main path, followed from point 0 along next1 (the main
        continuation at a split, swrSpline.c:335-342). Every other polyline starts and ends with
        a duplicate of the existing point it branches from / rejoins, so a branch can leave or
        join any point, including one on another alternate path. A direct link between two
        existing points (a shortcut with no points of its own) becomes a two-point polyline."""
        count = len(self.points)
        if count == 0:
            return []
        polylines = []
        placed = set()

        # main path
        chain = [0]
        placed.add(0)
        while self.points[chain[-1]].next and self.points[chain[-1]].next[0] not in placed:
            chain.append(self.points[chain[-1]].next[0])
            placed.add(chain[-1])
        last_next = self.points[chain[-1]].next
        cyclic = bool(last_next) and last_next[0] == chain[0]
        if last_next and not cyclic:
            chain.append(last_next[0])
        polylines.append((chain, cyclic))

        # alternate paths, in point order
        while len(placed) < count:
            start = next((i for i in range(count) if i not in placed and any(p in placed for p in self.points[i].previous)), None)
            if start is None: # not reachable from the main path
                start = next(i for i in range(count) if i not in placed)
            chain = []
            branch_from = [p for p in self.points[start].previous if p in placed]
            if branch_from:
                chain.append(branch_from[0])
            chain.append(start)
            placed.add(start)
            while self.points[chain[-1]].next:
                following = self.points[chain[-1]].next[0]
                chain.append(following)
                if following in placed:
                    break
                placed.add(following)
            polylines.append((chain, False))

        # links not drawn by any polyline yet
        drawn = set()
        for chain, cyclic in polylines:
            drawn.update(zip(chain, chain[1:]))
            if cyclic:
                drawn.add((chain[-1], chain[0]))
        for i, point in enumerate(self.points):
            for j in point.next:
                if (i, j) not in drawn:
                    polylines.append(([i, j], False))
                    drawn.add((i, j))
        return polylines
    
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
                assert len(next) <= 1, "All paths must join before and split after starting line! You cannot have shortcuts that go around the finish line."
                end = True

            path_list.append(current_unique)
            current = next

        for i, path in enumerate(path_list):
            for p in path:
                point = self.points[p]
                point.progress = i
                if i == len(path_list) - 1 and not loop:
                    point.progress = 0
    
    def unmake(self, collection, scale = 0.01):
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
        paths = [spline for spline in splines if spline.type == 'BEZIER' and len(spline.bezier_points)>=2]
        
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
            loop = True
        else:
            main_path = longest_paths[0]
        # every other open path is an alternate path, longest first (by identity: the main
        # path is not necessarily the longest one)
        alt_paths = [spline for spline in longest_paths if spline is not main_path and not spline.use_cyclic_u]

        #begin deconstruction
        point_count = 0

        main_len = len(main_path.bezier_points)
        count = main_len + sum([len(path.bezier_points) - 2 for path in alt_paths])
        assert count <= 255, f"Too many spline points. Splines that contain more than 255 points are not supported. This scene contains {count} points."

        #add all points from main_path
        for i, point in enumerate(main_path.bezier_points):
            p = SplinePoint().unmake(point, spline_object, scale)
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

        self.calculate_progress(loop)

        def game_position(co):
            return [c/scale for c in spline_object.matrix_world @ co]

        # An alternate path's first and last points are duplicates of the points it branches
        # from and rejoins, which may lie on another alternate path, so add a path only once
        # both of those exist (ties keep the longest first).
        remaining = list(alt_paths)
        while remaining:
            best = None
            for path in remaining:
                start, start_distance = self.find_closest(game_position(path.bezier_points[0].co))
                end, end_distance = self.find_closest(game_position(path.bezier_points[-1].co), ban = start)
                distance = max(start_distance, end_distance)
                if distance <= 1.0: # game units
                    distance = 0
                if best is None or distance < best[0]:
                    best = (distance, path, start, end)
            _, path, start, end = best
            remaining.remove(path)

            points = [SplinePoint().unmake(point, spline_object, scale) for point in path.bezier_points[1:-1]]
            assert start is not None and end is not None and start != end, "Something went wrong during Spline export"

            # check if path needs to be inverted
            # this prevents a path from ending on an earlier point than where it started
            if self.points[start].progress > self.points[end].progress:
                print('reversed spline')
                start, end = end, start
                points.reverse()
                # walked the other way, each point's incoming and outgoing handles trade places
                # (a segment a -> b uses a.handle2 and b.handle1, swrSpline.c:136-139)
                for p in points:
                    p.handle1, p.handle2 = p.handle2, p.handle1

            # a control point holds at most 2 next and 4 previous links (types.h swrSplineControlPoint)
            assert len(self.points[start].next) < 2, f"Spline point {start} already splits into 2 paths; a point can't split into more."
            assert len(self.points[end].previous) < 4, f"Spline point {end} already joins 4 paths; a point can't join more."

            if not points: # direct shortcut between two existing points
                self.points[start].next.append(end)
                self.points[end].previous.append(start)

            # loop through and add points of path
            for i, p in enumerate(points):
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

            self.calculate_progress(loop)

        # unk_set[slot] is the segment id of the segment that leaves through next<slot+1>
        # (swrSpline.c:394-401): next1 segments are numbered by point, next2 segments follow
        splits = 0
        for i, point in enumerate(self.points):
            point.unk_set[0] = i
            if len(point.next) == 2:
                point.unk_set[1] = len(self.points) + splits
                splits += 1
            if i == len(self.points) - 1 and not loop:
                point.unk_set[0] = 0

        # LIMITATIONS:
        # a point can split into at most 2 paths and join at most 4
        # cannot have alt paths that start before and end after the finish line on main spline

        self.point_count = len(self.points)
        # one segment id per point plus one per split, matching every stock spline
        self.segment_count = len(self.points) + splits

        return self

    def find_closest(self, co, ban = None):
        """Index of and distance to the existing point nearest to co (game units)."""
        closest_index = None
        closest_distance = float('inf')

        for i, point in enumerate(self.points):
            if ban is not None and i == ban:
                continue
            distance = math.dist(point.position.to_array(), co)

            if distance < closest_distance:
                closest_index = i
                closest_distance = distance
        return closest_index, closest_distance
    
    def write(self):
        buffer = bytearray(8000000)
        cursor = 0
        struct.pack_into(self.format_string, buffer, cursor, self.unk, self.unk1, self.point_count, self.segment_count, self.unk2, self.unk3, self.unk4, self.unk5)
        cursor += self.size
        for point in self.points:
            point.write(buffer, cursor)
            cursor += point.size
        return buffer[:cursor]


