"""Museum, splines wing: an alternate path that splits off the main path and joins it again.

The bottom straight forks: the main path runs straight on, and the alternate path swings 1500 out to
the right and back. Both have road. The add-on writes the alternate path's first and last points as
the main points it starts and ends on (a split and a join, swe1r/splineblock.py). The checks:

- the lap completes (lap progress is traced along both paths, swrSpline_TraceProgress 0x47f060);
- the route the autopilot took, kept in the baseline;
- the pod's spline progress never goes backwards on either path.

Point-to-point tracks are level_museum_p2p.
"""
import math

from mathutils import Vector

import course as C
import lib
import signs

R = 2500.0
SPACING = 500.0
OUT = 1500.0


def build(addon):
    model, track, sky = lib.new_track_scene(addon)
    road_mat = lib.material(addon, "splines_road", lib.checker_image("splines_checker"))
    sign_mat = lib.material(addon, "splines_signs", signs.atlas_image())

    segs = [C.straight(1000, "start"), C.straight(1500, "before_fork"), C.straight(6000, "fork"),
            C.straight(1500, "after_fork"), C.arc(R, 180, "turn"), C.straight(10000 + 2000, "back"),
            C.arc(R, 180, "turn_home"), C.straight(2000, "grid")]
    course = C.Course(segs, origin=(-5000.0, -R))
    dist, heading_err, z_err = course.closure_error()
    assert dist < 1 and abs(heading_err) < 0.01, course.closure_error()

    roads = course.road(track, road_mat, colors={"fork": (0.75, 0.85, 1.0)})
    for objs in roads.values():
        for obj in objs:
            lib.set_surface(obj)
            lib.shade(obj)

    main = course.spline_points(SPACING)
    spline = lib.spline("spline", main, model)

    # the fork: from the main point nearest the start of "fork" to the one nearest its end
    f0, f1 = course.station_range("fork")
    a = min(main, key=lambda p: (Vector(p) - course.frame(f0)["pos"]).length)
    b = min(main, key=lambda p: (Vector(p) - course.frame(f1)["pos"]).length)
    a, b = Vector(a), Vector(b)
    right = Vector((0, -1, 0))   # the bottom straight runs +X; the loop is to the left
    length = (b - a).length
    alt = [a]
    steps = 12
    for i in range(1, steps):
        t = i / steps
        bulge = math.sin(math.pi * t) * OUT
        alt.append(a + (b - a) * t + right * bulge)
    alt.append(b)
    lib.spline_path(spline, [tuple(p) for p in alt])
    # road under the alternate path (a ribbon through finely spaced points on the same curve)
    fine = []
    for i in range(0, 121):
        t = i / 120
        fine.append(tuple(a + (b - a) * t + right * math.sin(math.pi * t) * OUT))
    alt_road = lib.ribbon("road_alt", fine, 600, track, road_mat)
    lib.set_surface(alt_road)
    lib.shade(alt_road, tint=(1.0, 0.8, 0.5))

    signs.station_sign(course, "before_fork", ["FORK AHEAD", "SPLIT + JOIN", "ALT PATH: RIGHT"], track, sign_mat)
    stations = []
    for name in ("before_fork", "fork", "after_fork"):
        s0, s1 = course.station_range(name)
        stations.append({"name": name, "s": [round(s0, 1), round(s1, 1)], "measure": ["route"],
                         "predict": {}, "source": "swe1r/splineblock.py alternate paths; "
                                                  "SW_RACER_RE swrSpline_TraceProgress 0x47f060"})
    # the alternate road, sampled for the checker's centre line (its own station)
    centerline = course.describe()
    alt_s0 = course.length + 1000
    for i, p in enumerate(fine[::3]):
        centerline.append([round(alt_s0 + i * 150, 1), round(p[0], 1), round(p[1], 1), round(p[2], 1), "alt_path"])
    stations.append({"name": "alt_path", "s": [alt_s0, alt_s0 + length], "measure": ["route"], "predict": {},
                     "source": "swe1r/splineblock.py alternate paths"})
    # AI pods flip a coin at every fork (swrRace.c:2382-2394); a human pod takes branch 0 unless it
    # drives onto the other road (swrRace.c:2935). Five AI pods: the alternate path should see some.
    for st in stations:
        if st["name"] == "alt_path":
            # the autopilot pod borrows the AI flag while steering, so it flips the coin too
            st["predict"] = {"ai_pods": {"gt": 0}}
            st["source"] += "; AI coin-flip at forks: SW_RACER_RE src/Swr/swrRace.c:2382-2394"
    return model, {"level": "museum_splines", "length": round(course.length, 1), "centerline": centerline,
                   "stations": stations, "lap": {"finishes": True}, "racers": 6}
