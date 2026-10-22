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

"""Where the game puts each part of a pod. The game overwrites the transforms of a pod's engine
(header slots 1/2), cockpit (5), cable, binder, exhaust and shadow nodes every frame from a table
in its executable, one row per racer, so the model's own node positions there have no effect.

POD_VISUAL is keyed by the Podd model id the row belongs to. Read from SWEP1RCR.EXE (Steam):
swrRacer_PodVisualData 0x004c7088, 23 rows of 0x6c bytes, and swrRacer_PodData 0x004c2700 for the
racer -> Podd id. Positions are game units in the pod's frame (x right, y forward, z up): cockpit
+0x00, right engine +0x0C (the left engine is the same with -x), cable attach points +0x24 / +0x30,
binder +0x3C, exhaust +0x54 (in the engine's frame). Used by swrObjTest_F3 (0x470610),
PoddAnimateEngines (0x470ae0), UpdateEngineExhaust (0x46f2c0).

No bpy, so tests can read it.
"""

POD_VISUAL = {
    2: dict(racer=0, cockpit=(0.0, -4.44, 1.04), engine=(2.32, 5.22, -0.44), cable_cockpit=(0.98, 2.18, 0.0), cable_engine=(0.0, -0.98, 0.76), binder=(0.55, 0.14, 0.0), exhaust=(0.0, -3.5, 0.0)),
    4: dict(racer=1, cockpit=(0.0, -11.5, 4.06), engine=(3.5, 5.64, 0.0), cable_cockpit=(0.42, 4.3, -1.48), cable_engine=(0.0, -1.7, 2.11), binder=(1.94, 0.94, 0.02), exhaust=(0.0, -4.97, 0.0)),
    6: dict(racer=2, cockpit=(0.0, -7.0, 1.5), engine=(3.0, 5.0, 0.0), cable_cockpit=(0.7, 2.3, -0.2), cable_engine=(0.0, -1.6, 1.35), binder=(1.52, 1.42, 0.0), exhaust=(0.0, -5.86, 0.0)),
    8: dict(racer=3, cockpit=(0.0, -5.52, 2.3), engine=(2.53, 5.0, 0.0), cable_cockpit=(0.2, 1.64, -0.1), cable_engine=(0.0, 0.9, 2.01), binder=(1.12, -0.06, 0.0), exhaust=(0.0, -6.32, 0.0)),
    9: dict(racer=4, cockpit=(0.0, -6.0, 3.0), engine=(4.5, 6.4, -0.6), cable_cockpit=(1.1, 1.1, -0.68), cable_engine=(-1.64, -1.4, 1.81), binder=(3.12, 1.1, 1.0), exhaust=(1.14, -5.56, -0.48)),
    12: dict(racer=5, cockpit=(0.0, -4.54, 1.04), engine=(2.76, 3.66, 0.0), cable_cockpit=(1.0, 2.16, -0.26), cable_engine=(0.0, -2.58, 0.57), binder=(1.0, 0.86, 0.0), exhaust=(3.18, 0.88, -1.14)),
    14: dict(racer=6, cockpit=(0.0, -4.46, 1.5), engine=(3.5, 5.0, -0.98), cable_cockpit=(0.58, 1.2, -1.0), cable_engine=(0.0, -2.88, 1.65), binder=(3.08, -0.66, 0.0), exhaust=(0.0, -1.48, 0.0)),
    17: dict(racer=7, cockpit=(0.0, -4.22, 1.5), engine=(3.5, 5.0, 0.0), cable_cockpit=(0.7, -0.66, -0.98), cable_engine=(1.28, -1.52, 1.17), binder=(1.66, 0.0, 0.0), exhaust=(0.0, -3.5, 0.16)),
    16: dict(racer=8, cockpit=(0.0, -6.8, 1.9), engine=(5.27, 7.32, 0.4), cable_cockpit=(1.26, 3.06, -0.74), cable_engine=(-2.32, -3.74, 0.47), binder=(2.38, 0.0, 0.0), exhaust=(0.0, -5.02, 0.0)),
    20: dict(racer=9, cockpit=(0.0, -5.9, 3.04), engine=(2.24, 5.0, 0.0), cable_cockpit=(1.48, 0.66, -0.4), cable_engine=(-0.42, -3.5, 1.13), binder=(1.32, -2.56, 0.06), exhaust=(0.0, -5.74, 0.0)),
    22: dict(racer=10, cockpit=(0.0, -6.52, 1.66), engine=(2.58, 5.0, 0.0), cable_cockpit=(0.5, 2.42, -0.16), cable_engine=(-0.98, -2.76, 0.43), binder=(1.6, -0.46, -0.06), exhaust=(0.0, -4.44, -0.16)),
    24: dict(racer=11, cockpit=(0.0, -3.9, 2.36), engine=(3.15, 5.0, 0.0), cable_cockpit=(1.06, 1.42, 0.04), cable_engine=(0.0, -1.34, 1.87), binder=(1.74, -0.12, -0.08), exhaust=(0.0, -2.54, 0.0)),
    26: dict(racer=12, cockpit=(0.0, -7.36, 3.32), engine=(3.55, 8.74, 0.0), cable_cockpit=(1.12, 2.3, 0.44), cable_engine=(0.0, 2.16, 2.45), binder=(1.0, 0.7, 0.0), exhaust=(0.0, -4.5, 0.0)),
    28: dict(racer=13, cockpit=(0.0, -5.4, 1.7), engine=(3.89, 3.18, 0.0), cable_cockpit=(0.58, -0.06, 0.04), cable_engine=(0.0, -0.8, 1.45), binder=(1.5, 1.0, 0.0), exhaust=(0.0, -2.36, 0.0)),
    30: dict(racer=14, cockpit=(0.0, 0.0, 0.0), engine=(0.0, 0.0, 0.0), cable_cockpit=(0.0, 0.0, 0.0), cable_engine=(0.0, 0.0, 0.0), binder=(0.0, 0.0, 0.0), exhaust=(1.96, -4.48, 0.0)),
    32: dict(racer=15, cockpit=(0.0, -3.16, 1.7), engine=(2.75, 5.0, 0.0), cable_cockpit=(0.78, 1.98, -0.6), cable_engine=(0.0, -2.64, 0.87), binder=(0.82, -2.04, 0.24), exhaust=(0.0, -3.5, 0.0)),
    34: dict(racer=16, cockpit=(0.0, -7.36, 2.64), engine=(3.81, 5.0, 0.0), cable_cockpit=(0.72, 2.84, -0.58), cable_engine=(0.0, -2.72, 1.31), binder=(2.0, 1.0, 0.0), exhaust=(0.0, -3.5, 0.0)),
    36: dict(racer=17, cockpit=(0.0, -9.68, 3.88), engine=(3.55, 7.06, 0.0), cable_cockpit=(2.92, 2.74, -0.82), cable_engine=(0.0, -1.18, 2.57), binder=(2.7, 2.04, 0.14), exhaust=(0.06, -5.0, 0.0)),
    38: dict(racer=18, cockpit=(0.0, -6.08, 1.96), engine=(4.77, 5.96, 0.0), cable_cockpit=(0.84, 1.4, -0.22), cable_engine=(0.0, -4.44, 1.33), binder=(2.82, 1.0, 0.0), exhaust=(0.0, -6.3, -0.24)),
    40: dict(racer=19, cockpit=(0.0, -5.76, 1.9), engine=(2.75, 7.68, -2.22), cable_cockpit=(1.22, 2.28, 0.16), cable_engine=(-0.7, 1.2, 0.83), binder=(1.04, 1.64, 0.0), exhaust=(0.0, -4.34, 0.0)),
    42: dict(racer=20, cockpit=(0.0, -7.68, 1.2), engine=(3.57, 5.96, 0.0), cable_cockpit=(0.84, 2.16, 0.16), cable_engine=(0.0, -2.56, 1.33), binder=(0.88, -1.58, 0.0), exhaust=(0.0, -4.08, 0.0)),
    44: dict(racer=21, cockpit=(0.0, -7.32, 0.9), engine=(2.31, 4.98, 0.08), cable_cockpit=(0.92, 3.2, 0.12), cable_engine=(0.0, -0.92, 1.41), binder=(1.24, -0.52, 0.4), exhaust=(0.0, 0.62, 0.56)),
    46: dict(racer=22, cockpit=(0.0, -4.94, 0.9), engine=(2.07, 5.3, 0.08), cable_cockpit=(0.26, 2.12, -0.1), cable_engine=(0.0, 0.98, 0.93), binder=(1.04, 1.08, 0.1), exhaust=(0.0, -1.34, 0.0)),
}

# A pod's part content sits under a 0.016-scale node, and the add-on writes Blender units at 100 file
# units each (Model.scale 0.01): one Blender unit in a pod template is 1.6 game units.
POD_BLENDER_SCALE = 0.016 / 0.01


def pod_anchor_positions(podd_id):
    """{anchor: (x, y, z) in template Blender units} for the pod replacing Podd model podd_id:
    where the game draws its engines, cockpit and exhausts, and the ends of its energy binder and
    cables (in the pod's frame, without the game's engine tilt and cockpit lag). None if the id has
    no row.

    Binder (PoddAnimateVariousThings 0x471760): each engine's position plus the row's binder offset
    in the engine's frame, its x negated on the right engine. Cables (swrRace_BuildStretchedQuad
    0x46f0e0, called with x sign +1 for the right cable, slot 10, and -1 for the left, slot 11):
    from the cockpit plus the row's cockpit cable offset to the engine plus its engine cable
    offset, both x-signed."""
    row = POD_VISUAL.get(int(podd_id))
    if row is None:
        return None
    s = 1.0 / POD_BLENDER_SCALE
    ex, ey, ez = row['engine']
    xx, xy, xz = row['exhaust']
    bx, by, bz = row['binder']
    cx, cy, cz = row['cable_cockpit']
    kx, ky, kz = row['cable_engine']
    px, py, pz = row['cockpit']
    return {
        'engine_r': (ex * s, ey * s, ez * s),
        'engine_l': (-ex * s, ey * s, ez * s),
        'cockpit': tuple(c * s for c in row['cockpit']),
        'exhaust_r': ((ex + xx) * s, (ey + xy) * s, (ez + xz) * s),
        'exhaust_l': ((-ex - xx) * s, (ey + xy) * s, (ez + xz) * s),
        'binder_r': ((ex - bx) * s, (ey + by) * s, (ez + bz) * s),
        'binder_l': ((-ex + bx) * s, (ey + by) * s, (ez + bz) * s),
        'cable_cockpit_r': ((px + cx) * s, (py + cy) * s, (pz + cz) * s),
        'cable_cockpit_l': ((px - cx) * s, (py + cy) * s, (pz + cz) * s),
        'cable_engine_r': ((ex + kx) * s, (ey + ky) * s, (ez + kz) * s),
        'cable_engine_l': ((-ex - kx) * s, (ey + ky) * s, (ez + kz) * s),
    }
