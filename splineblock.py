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
import math
import os
from .readwrite import *

def write_spline(spline):
    buffer = bytearray(16 + len(spline['points']) * 84)
    cursor = 0
    struct.pack_into('>iiii', buffer, cursor, spline['unknown'], spline['point_count'], spline['segment_count'], spline['unknown2'])
    cursor += 16

    for point in spline['points']:
        cursor = write_spline_point(buffer, cursor, point)

    return bytes(buffer[:cursor])

def invert_spline(spline):
    inverted_points = []
    double_count = 0
    biggest_num0 = 0

    for point in spline['points']:
        if point['point_num0'] > biggest_num0:
            biggest_num0 = point['point_num0']

    for i, point in enumerate(spline['points']):
        inverted_point = {
            'previous_count': point['next_count'],
            'next_count': point['previous_count'],
            'next1': point['previous1'],
            'next2': point['previous2'],
            'previous1': point['next1'],
            'previous2': point['next2'],
            'unknown1': point['unknown1'],
            'unknown2': point['unknown2'],
            'point_x': point['point_x'],
            'point_y': point['point_y'],
            'point_z': point['point_z'],
            'rotation_x': point['rotation_x'],
            'rotation_y': point['rotation_y'],
            'rotation_z': point['rotation_z'],
            'handle1_x': point['handle2_x'],
            'handle1_y': point['handle2_y'],
            'handle1_z': point['handle2_z'],
            'handle2_x': point['handle1_x'],
            'handle2_y': point['handle1_y'],
            'handle2_z': point['handle1_z'],
            'point_num0': 0 if point['point_num0'] == 0 else biggest_num0 - point['point_num0'] + 1,
            'point_num1': i,
            'point_num2': spline['point_count'] + double_count if point['splits'] == 2 else -1,
            'point_num3': -1,
            'point_num4': -1,
            'point_num5': -1,
            'point_num6': -1,
            'point_num7': -1,
            'point_num8': -1,
            'point_unk': point['point_unk']
        }

        if point['splits'] == 2:
            double_count += 1

        inverted_points.append(inverted_point)

    spline['points'] = inverted_points
    return spline

def write_spline_point(buffer, cursor, point):
    cursor = struct.pack_into('>hhhhhhhhfff fff fff hhhh hhhh hhhh hhhh hhhh hhhh hhhh hhhh hhhh hhh', buffer, cursor,
                              point.next_count, point.previous_count,
                              point.next1, point.next2,
                              point.previous1, point.previous2,
                              point.unknown1, point.unknown2,
                              point.point_x, point.point_y, point.point_z,
                              point.rotation_x, point.rotation_y, point.rotation_z,
                              point.handle1_x, point.handle1_y, point.handle1_z,
                              point.handle2_x, point.handle2_y, point.handle2_z,
                              point.point_num0,
                              point.point_num1,
                              point.point_num2,
                              point.point_num3,
                              point.point_num4,
                              point.point_num5,
                              point.point_num6,
                              point.point_num7,
                              point.point_num8,
                              point.point_unk)
    return cursor
