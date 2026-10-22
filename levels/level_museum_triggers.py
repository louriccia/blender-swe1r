"""Museum, triggers wing: every trigger type and every trigger flag, one exhibit each.

A trigger is a CUBE empty parented to the road mesh the pod drives on: the game only tests the
triggers of the collision mesh under the pod (swrRace_ActivateTriggersInRange 0x476ac0). The test
runner logs every trigger the pod fires (it hooks swrRace_TriggerHandler 0x47ce60), so each exhibit
checks that exactly the expected trigger fired, which also checks the add-on wrote the trigger's
type, flags, position and size where the game reads them.

The flag exhibits use type 107, which the handler takes but does nothing with. Exhibits go from
harmless to drastic: animations, destructibles, then effects that rely on planet models, the
kill trigger and the teleport last. Custom folder tracks run as planet 1, so trigger effect models
are planet 1's (swrObjTrig_LoadAndInitializeTriggerModels 0x47ddc0).
"""
import math

import bpy
from mathutils import Vector

import course as C
import lib
import signs

LENGTH = 900.0
SRC = "SW_RACER_RE ghidra swrRace_TriggerHandler 0x47ce60; flags as tested in swrRace_ActivateTriggersInRange 0x476ac0"
FLAGS = {"Disabled": 0x1, "SpeedCheck150": 0x2, "SkipLap1": 0x4, "SkipLap2": 0x8, "SkipLap3": 0x10,
         "IgnoreAI": 0x20}


def ex(name, type_, title, lines, fires=True, flags=(), target=None, offset=0.0, plane=False, extra=None,
       source=SRC):
    return dict(name=name, type=type_, title=title, lines=lines, fires=fires, flags=list(flags),
                target=target, offset=offset, plane=plane, extra=extra or {}, source=source)


EXHIBITS = [
    # flags, on the do-nothing type 107
    ex("t107", 107, "TRIGGER 107", ["NO FLAGS", "FIRES"]),
    ex("t107_disabled", 107, "DISABLED 0X1", ["NEVER FIRES"], fires=False, flags=["Disabled"]),
    ex("t107_speed150", 107, "SPEED > 150", ["0X2: FIRES", "AT 600"], flags=["SpeedCheck150"]),
    ex("t107_skiplap1", 107, "SKIP LAP 1", ["0X4: LAP 1", "NO FIRE"], fires=False, flags=["SkipLap1"]),
    ex("t107_skiplap2", 107, "SKIP LAP 2", ["0X8: FIRES", "ON LAP 1"], flags=["SkipLap2"]),
    ex("t107_ignoreai", 107, "IGNORE AI", ["0X20: LOCAL", "FIRES"], flags=["IgnoreAI"]),
    ex("t107_offpath", 107, "OFF THE PATH", ["400 LEFT", "NO FIRE"], fires=False, offset=400.0),
    ex("t0", 0, "TYPE 0", ["NO HANDLER"]),
    # animations
    ex("t101", 101, "101 DOOR", ["ANIM SPEED", "+-20"], target="spin"),
    ex("t307", 307, "307 DOOR 2", ["LOOP ANIM"], target="spin"),
    ex("t304", 304, "304 TRAM", ["START ANIMS"], target="slide"),
    ex("t105", 105, "105 GLACIER", ["ANIM + SHAKE"], target="slide"),
    ex("t312", 312, "312 PILLAR", ["ANIM + SHAKE"], target="slide"),
    # remove / destroy the target
    ex("t103", 103, "103 TENT", ["HIDE TARGET"], target="box"),
    ex("t100", 100, "100 ICE", ["BREAK TARGET"], target="box"),
    ex("t201", 201, "201 ICE", ["BREAK", "DECEL 25"], target="box"),
    ex("t202", 202, "202 ROCKS", ["BREAK", "DECEL 2.5"], target="box"),
    ex("t212", 212, "212 BRANCHES", ["BREAK"], target="box"),
    ex("t102", 102, "102 ASTEROID", ["PLANE CROSS", "BREAK"], target="box", plane=True),
    # effects that use planet models or sounds
    ex("t203", 203, "203 TUSKENS", ["SOUND + FIRE"]),
    ex("t314", 314, "314 METHANE", ["FX AT TARGET"], target="box"),
    # 501 uses effect slot 5 (fx_lavafoof), which only Baroonda (planet 4) loads: firing it on any
    # other planet reads a null animation list and crashes (swrObjTrig_Handle314Or501Trigger 0x47cd90
    # -> swrObjTrig_AnimationActive 0x47bf20). Shown disarmed.
    ex("t501", 501, "501 LAVA", ["BAROONDA ONLY", "CRASHES ELSEWHERE", "SHOWN DISARMED"], fires=False,
       flags=["Disabled"], target="box",
       source="swrObjTrig_LoadAndInitializeTriggerModels 0x47ddc0 loads effect slot 5 on planet 4 only"),
    ex("t106", 106, "106 ASTEROIDS", ["FIRE FX"]),
    # loading 213 and 306 sets their flags |= 0x24 (SkipLap1 + IgnoreAI), so they never fire on
    # lap 1 (swrObjTrig_AddTriggerDescriptions 0x47d380)
    ex("t213", 213, "213 QUAKE", ["LOAD SETS 0X24", "NOT ON LAP 1"], fires=False, target="box",
       source="swrObjTrig_AddTriggerDescriptions 0x47d380: type 213/306 flags |= 0x24"),
    ex("t306", 306, "306 QUAKE", ["LOAD SETS 0X24", "NOT ON LAP 1"], fires=False, target="box",
       source="swrObjTrig_AddTriggerDescriptions 0x47d380: type 213/306 flags |= 0x24"),
    ex("t108", 108, "108 SLALOM", ["FLAG"], target="box"),
    # drastic: these end with the pod back on the spline
    ex("t104", 104, "104 BINDER", ["PLANE CROSS", "EXPLODE"], plane=True, extra={"explodes": {"gt": 0}}),
    # 900 resets the pod onto the spline at its own progress, at speed 0 (swrRace_ResetToSpline
    # swrObj.c:2379 with t = 0): on the racing line it resets the pod into itself every frame (the
    # first run logged 1790 resets and a stuck pod). Stock tracks put it out of bounds. Shown disarmed.
    ex("t900", 900, "900 RESET", ["KEEP OFF THE LINE", "OR POD STUCK", "SHOWN DISARMED"], fires=False,
       flags=["Disabled"], source="SW_RACER_RE src/Swr/swrObj.c:2379 swrRace_ResetToSpline(pod, 0)"),
]


def make_target(kind, name, at, heading, collection, mat):
    """Beside the road (left), so a target that stays solid doesn't block the path."""
    obj = lib.box(f"target_{name}", (0, 0, 0), (120, 120, 160), collection, mat)
    obj.location = lib.g(*at)
    obj.rotation_euler = (0, 0, heading)
    lib.set_surface(obj)
    if kind == "spin":
        for frame, angle in ((0, 0.0), (60, math.pi / 2), (120, math.pi)):
            obj.rotation_euler = (0, 0, heading + angle)
            obj.keyframe_insert("rotation_euler", frame=frame)
    elif kind == "slide":
        base = obj.location.copy()
        for frame, dz in ((0, 0.0), (60, 2.0), (120, 0.0)):
            obj.location = base + Vector((0, 0, dz))
            obj.keyframe_insert("location", frame=frame)
    lib.shade(obj, tint=(1.0, 0.6, 0.3))
    return obj


def build(addon):
    model, track, sky = lib.new_track_scene(addon)
    road_mat = lib.material(addon, "triggers_road", lib.checker_image("triggers_checker"))
    white_mat = lib.material(addon, "triggers_white", lib.flat_image("triggers_white", (1, 1, 1, 1)))
    sign_mat = lib.material(addon, "triggers_signs", signs.atlas_image())
    course = C.exhibit_line([(e["name"], LENGTH) for e in EXHIBITS], gap=400.0)

    names = {e["name"] for e in EXHIBITS}
    colors = {n: ((0.75, 0.85, 1.0) if n in names else (0.85, 0.85, 0.85)) for n in {s['station'] for s in course.samples}}
    roads = course.road(track, road_mat, colors=colors)
    for objs in roads.values():
        for obj in objs:
            lib.shade(obj)
    bpy.context.view_layer.update()

    entries = []
    for e in EXHIBITS:
        mesh = roads[e["name"]][0]
        s0, s1 = course.station_range(e["name"])
        mid = course.frame((s0 + s1) / 2)
        h = mid['heading']
        fwd = Vector((math.cos(h), math.sin(h), 0))
        left = Vector((-fwd.y, fwd.x, 0))
        target = None
        if e["target"]:
            target = make_target(e["target"], e["name"], tuple(mid['pos'] + left * 450 + Vector((0, 0, 80))), h,
                                 track, white_mat)
        trig = bpy.data.objects.new(f"trigger_{e['name']}", None)
        trig.empty_display_type = 'CUBE'
        track.objects.link(trig)
        trig.parent = mesh
        # the add-on writes position from the world matrix, width from scale.x and height from
        # scale.z (CollisionTrigger.unmake); direction from the z rotation
        trig.location = lib.g(*(mid['pos'] + left * e["offset"] + Vector((0, 0, 50))))
        trig.rotation_euler = (0, 0, h)
        width = 200 if e["offset"] else 300
        trig.scale = (lib.g(width / 2), lib.g(width / 2), lib.g(100))
        trig.trigger_id = e["type"]
        for flag in e["flags"]:
            setattr(trig, flag, True)
        if target is not None:
            trig.target = target
        signs.station_sign(course, e["name"], [e["title"], *e["lines"]], track, sign_mat)
        predict = {"fired": [e["type"]] if e["fires"] else []}
        predict.update(e["extra"])
        entries.append({"name": e["name"], "s": [round(s0, 1), round(s1, 1)], "measure": ["surface"],
                        "predict": predict, "source": e["source"],
                        "trigger": {"type": e["type"], "flags": sum(FLAGS[f] for f in e["flags"]),
                                    "center": [round(v, 1) for v in trig.location / lib.GAME],
                                    "width": width, "height": 200}})

    course.spline(model)
    return model, {"level": "museum_triggers", "length": round(course.length, 1),
                   "centerline": course.describe(), "stations": entries, "lap": {"finishes": True}}
