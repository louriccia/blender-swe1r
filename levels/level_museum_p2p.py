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
import course as C
import lib
import signs


def build(addon):
    model, track, sky = lib.new_track_scene(addon)
    road_mat = lib.material(addon, "p2p_road", lib.checker_image("p2p_checker"))
    sign_mat = lib.material(addon, "p2p_signs", signs.atlas_image())
    APRON = C.APRON
    segs = [C.straight(APRON, "grid"), C.straight(1500, "start"), C.straight(3000, "run1"), C.arc(2500, 90, "left"),
            C.straight(3000, "run2"), C.arc(2500, -90, "right"), C.straight(3000, "run3"),
            C.straight(1500, "finish"), C.straight(C.OVERRUN, "overrun")]
    course = C.Course(segs, origin=(-8000.0 - APRON, -4000.0), start_s=APRON, overrun=C.OVERRUN)
    assert course.extent() < 32000
    roads = course.road(track, road_mat, colors={"finish": (1.0, 0.6, 0.6), "start": (0.6, 1.0, 0.6)})
    for objs in roads.values():
        for obj in objs:
            lib.set_surface(obj)
            lib.shade(obj)
    # the spline runs from the end of the grid apron (point 0, the start line) to the end of
    # "finish"; the road goes on past it, or a pod that overshoots falls before the race ends
    course.spline(model)
    signs.station_sign(course, "start", ["POINT TO POINT", "OPEN SPLINE", "ONE LAP"], track, sign_mat)
    signs.station_sign(course, "finish", ["FINISH AT", "THE DEAD END"], track, sign_mat)
    stations = [{"name": n, "s": list(course.station_range(n)), "measure": ["route"], "predict": {},
                 "source": "SW_RACER_RE swrSpline_Build 0x47f6f0, swrObjJdge_SetupStartingGrid 0x465d50"}
                for n in ("start", "run1", "left", "run2", "right", "run3", "finish")]
    return model, {"level": "museum_p2p", "length": round(course.length, 1), "centerline": course.describe(),
                   "stations": stations, "lap": {"finishes": True}, "racers": 6,
                   "grid": {"start": [-8000.0, -4000.0], "forward": [1.0, 0.0], "racers": 6}}
