"""The gym: the pod's physical limits as measured geometry you can drive.

A point-to-point track, driven start to finish by the test runner's autopilot. Each station is a stretch of it
with a sign and an entry in expectations.json: what the decomp predicts there (with the source) and
what the checker (levels/check.py) measures from the test runner's telemetry.

Bottom straight (+X): start, slopes 5-20 deg, jump gaps, slopes 25-45 deg.
Back straight (-X): drops of 100 / 300 / 600, the climb back up, width gates, then the finish at
the end of the road.
"""
import math

from mathutils import Vector

import course as C
import lib
import signs

R = 2500.0          # turn radius
SLOPES_EASY = (5, 10, 15, 20)       # 500 long
SLOPES_HARD = (25, 30, 35, 40, 45)  # 150 high
GAPS = (200, 400, 600, 800)
KICKER_DEG, KICKER_RUN = 10.0, 300.0
DROPS = (100, 300, 600)
GATES = (60, 30, 20, 14, 11)   # the pod's wall sphere is 5 units (telemetry wr)
CLIMB_DEG = 12.0
CLIMB_LIMIT = 20.3  # deg: vz^2 > 0.1369 hz^2 -> clamped (swrRace.c:4509)
WALL_LIMIT = math.degrees(math.acos(0.7))   # 45.57 deg: wall severity (0.7 - n.up)/0.7 > 0

ROAD = (0.85, 0.85, 0.85)
TINTS = {"slope": (0.55, 0.75, 1.0), "gap": (1.0, 0.7, 0.4), "drop": (1.0, 0.55, 0.55),
         "gate": (0.6, 1.0, 0.6), "climb": (0.8, 0.8, 1.0), "turn": (1.0, 1.0, 0.6)}


def tint(station):
    for prefix, color in TINTS.items():
        if station.startswith(prefix):
            return color
    return ROAD


def slope_station(deg):
    name = f"slope{deg}"
    run = 500.0 if deg <= 20 else 150.0 / math.tan(math.radians(deg))
    # after a steep one, room to recover (a crash there spins the pod on for seconds)
    recover = 300 if deg <= 20 else 1500
    return [C.straight(300, name), C.ramp(run, deg, name), C.straight(300, name),
            C.ramp(run, -deg, name), C.straight(recover, name)]


def gap_station(gap):
    name = f"gap{gap}"
    rise = KICKER_RUN * math.tan(math.radians(KICKER_DEG))
    # landing as high as the lip, then back down at the kicker's slope
    return [C.straight(300, name), C.ramp(KICKER_RUN, KICKER_DEG, name),
            C.straight(gap, name, solid=False), C.straight(600, name),
            C.ramp(KICKER_RUN, -KICKER_DEG, name), C.straight(300, name)]


def layout():
    bottom = [C.straight(C.APRON, "grid"), C.straight(1000, "start")]
    for deg in SLOPES_EASY:
        bottom += slope_station(deg)
    for gap in GAPS:
        bottom += gap_station(gap)
    for deg in SLOPES_HARD:
        bottom += slope_station(deg)
    bottom += [C.straight(600, "runout")]
    a = sum(seg.length for seg in bottom)

    turn1 = [C.arc(R, 90, "turn_flat"), C.arc(R, 90, "turn_bank20", bank=20)]

    back = [C.straight(600, "drops")]
    for h in DROPS:
        back += [C.straight(800, f"drop{h}", drop=h)]
    climb_run = (sum(DROPS) / 2) / math.tan(math.radians(CLIMB_DEG))
    for i in range(2):
        back += [C.straight(400, "climb"), C.ramp(climb_run, CLIMB_DEG, "climb")]
    back += [C.straight(400, "gates")]
    for w in GATES:
        back += [C.straight(800, f"gate{w}")]
    back += [C.straight(C.RUNOUT, "finish"), C.straight(C.OVERRUN, "overrun")]

    # centred on the origin: vertices are int16
    course = C.Course(bottom + turn1 + back, origin=(-a / 2, -R), start_s=C.APRON, overrun=C.OVERRUN)
    assert course.extent() < 32000, f"course reaches {course.extent():.0f}, past the int16 vertex range"
    return course


def gate_walls(course, collection, mat):
    """Walls either side of each gate, 150 high: the road is 600 wide; the gap between the walls
    is the gate's width."""
    for w in GATES:
        s0, s1 = course.station_range(f"gate{w}")
        a, b = course.frame(s0), course.frame(s1)
        mid = (a['pos'] + b['pos']) / 2
        length = (b['pos'] - a['pos']).length
        heading = a['heading']
        side = Vector((-math.sin(heading), math.cos(heading), 0))
        thickness = (600 - w) / 2 + 50
        for k in (1, -1):
            center = mid + side * k * (w / 2 + thickness / 2) + Vector((0, 0, 75))
            obj = lib.box(f"gate{w}_wall_{'L' if k > 0 else 'R'}", (0, 0, 0), (length, thickness, 150),
                          collection, mat)
            # placed by object transform: exercises the add-on keeping it on export
            obj.location = lib.g(*center)
            obj.rotation_euler = (0, 0, heading)
            lib.set_surface(obj)
            lib.shade(obj, tint=TINTS["gate"])


def stations():
    out = {"start": dict(title="START", lines=["HOVER HEIGHT"], measure=["hover", "radius"], predict={})}
    for d in SLOPES_EASY + SLOPES_HARD:
        rise = 500 * math.tan(math.radians(d)) if d <= 20 else 150
        out[f"slope{d}"] = dict(
            title=f"SLOPE {d}^", lines=[f"RISE {rise:.0f}", "CLAMP > 20.3^", "WALL > 45.6^"],
            measure=["climb"], predict={"climbs": d < WALL_LIMIT, "slows": d > CLIMB_LIMIT},
            source="climb clamp: SW_RACER_RE src/Swr/swrRace.c:4509-4514 (vertical speed clamped to "
                   "0.2 x horizontal above ~20.3 deg); wall: swrRace_ApplyWallCollision 0x479920 "
                   "(severity (0.7 - n.up)/0.7: steeper than 45.6 deg is a wall)")
    for gap in GAPS:
        out[f"gap{gap}"] = dict(title=f"GAP {gap}", lines=[f"KICKER {KICKER_DEG:.0f}^", "AIR > 30"],
                                measure=["air"], predict={},
                                source="airborne above 30 units; respawn after >3 s with no ground "
                                       "(SW_RACER_RE src/Swr/swrRace.c:3410-3507, 3439-3448)")
    for h in DROPS:
        out[f"drop{h}"] = dict(title=f"DROP {h}", lines=["FALL"], measure=["air"],
                               predict={"respawns": False},
                               source="respawn only after >3 s with no ground below "
                                      "(SW_RACER_RE src/Swr/swrRace.c:3439-3448)")
    out["climb"] = dict(title=f"CLIMB {CLIMB_DEG:.0f}^", lines=["UP 1000"], measure=["climb"],
                        predict={"climbs": True})
    for w in GATES:
        out[f"gate{w}"] = dict(title=f"WIDTH {w}", lines=["POD WALL", "RADIUS 5"], measure=["speed"],
                               predict={"slows": w < 2 * 5},
                               source="the pod stops at walls as a sphere of swrRace +0xa8 (5.0 here) "
                                      "x (1 - 0.75 tilt) (dinput_hook/collision_viewer.cpp "
                                      "append_pod_hitboxes, swrRace_UpdateWallContact)")
    out["turn_flat"] = dict(title="TURN R2500", lines=["FLAT"], measure=["speed"], predict={})
    out["turn_bank20"] = dict(title="TURN R2500", lines=["BANK 20^"], measure=["speed"], predict={})
    return out


def build(addon):
    model, track, sky = lib.new_track_scene(addon)
    road_mat = lib.material(addon, "gym_road", lib.checker_image("gym_checker"))
    white_mat = lib.material(addon, "gym_white", lib.flat_image("gym_white", (1, 1, 1, 1)))
    sign_mat = lib.material(addon, "gym_signs", signs.atlas_image())

    course = layout()

    names = {smp['station'] for smp in course.samples}
    roads = course.road(track, road_mat, colors={n: tint(n) for n in names})
    for objs in roads.values():
        for obj in objs:
            lib.shade(obj)
    gate_walls(course, track, white_mat)
    course.spline(model)

    entries = []
    for name, info in stations().items():
        s0, s1 = course.station_range(name)
        smp = course.frame(s0)
        h = smp['heading']
        fwd = Vector((math.cos(h), math.sin(h), 0))
        left = Vector((-fwd.y, fwd.x, 0))
        at = smp['pos'] + left * (smp['width'] / 2 + 200) + fwd * 100
        signs.sign(f"sign_{name}", [info["title"], *info["lines"]], tuple(at), (-fwd.x, -fwd.y),
                   track, sign_mat)
        entries.append({"name": name, "s": [round(s0, 1), round(s1, 1)], "measure": info["measure"],
                        "predict": info["predict"], "source": info.get("source", "")})

    expectations = {
        "level": "gym",
        "length": round(course.length, 1),
        "centerline": course.describe(),
        "stations": entries,
        "lap": {"finishes": True},
    }
    return model, expectations
