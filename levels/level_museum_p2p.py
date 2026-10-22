"""Museum: a point-to-point track (an open spline). No stock track is one, but the game supports it.

When spline point 0 has no previous point, swrSpline_Build (0x47f6f0) makes the track point-to-point:
- the race is one lap whatever the lap setting (num_laps forced to 1);
- the finish is the spline's dead end;
- the grid is split, half at the start and half at the end (swrObjJdge_SetupStartingGrid 0x465d50).

The add-on writes an open spline when no spline in the model is cyclic (swe1r/splineblock.py).

The grid is behind spline point 0 (swrObjJdge_GetSpawnTransform 0x465840: 100 back, rows 30 apart),
so the road has to start before point 0. A first version started the road at point 0 and every
pod fell through the countdown and spawned 1260 under the road.
"""
import math

from mathutils import Vector

import course as C
import lib
import signs


def build(addon):
    model, track, sky = lib.new_track_scene(addon)
    road_mat = lib.material(addon, "p2p_road", lib.checker_image("p2p_checker"))
    sign_mat = lib.material(addon, "p2p_signs", signs.atlas_image())
    APRON = 600.0
    segs = [C.straight(APRON, "grid"), C.straight(1500, "start"), C.straight(3000, "run1"), C.arc(2500, 90, "left"),
            C.straight(3000, "run2"), C.arc(2500, -90, "right"), C.straight(3000, "run3"),
            C.straight(1500, "finish")]
    course = C.Course(segs, origin=(-8000.0 - APRON, -4000.0))
    assert course.extent() < 32000
    roads = course.road(track, road_mat, colors={"finish": (1.0, 0.6, 0.6), "start": (0.6, 1.0, 0.6)})
    for objs in roads.values():
        for obj in objs:
            lib.set_surface(obj)
            lib.shade(obj)
    # the spline starts at the end of the grid apron: point 0 is the start line
    points = [p for p in course.spline_points(100.0) if p[0] >= -8000.0 - 1e-6][::5]
    end = course.samples[-1]['pos']
    if (Vector(points[-1]) - end).length > 50:
        points.append(tuple(end))
    lib.spline("spline", points, model, cyclic=False)
    signs.station_sign(course, "start", ["POINT TO POINT", "OPEN SPLINE", "ONE LAP"], track, sign_mat)
    signs.station_sign(course, "finish", ["FINISH AT", "THE DEAD END"], track, sign_mat)
    stations = [{"name": n, "s": list(course.station_range(n)), "measure": ["route"], "predict": {},
                 "source": "SW_RACER_RE swrSpline_Build 0x47f6f0, swrObjJdge_SetupStartingGrid 0x465d50"}
                for n in ("start", "run1", "left", "run2", "right", "run3", "finish")]
    return model, {"level": "museum_p2p", "length": round(course.length, 1), "centerline": course.describe(),
                   "stations": stations, "lap": {"finishes": True}, "racers": 6,
                   "grid": {"start": [-8000.0, -4000.0], "forward": [1.0, 0.0], "racers": 6}}
