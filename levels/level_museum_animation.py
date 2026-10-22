"""Museum, animation wing: animated geometry the pod drives on, and animated scenery to look at.

The lift is a 1800-long road section animated up and down, between 150 below the road and level
with it, every 2 s (linear keys, a Cycles modifier for the loop). The pod rides it, so its height
shows the animation the game plays. The checker measures the swing and the period, which must be
the ones authored in Blender (the add-on writes key times as frame / fps). Both of the lift's ends
are drops for the pod: the road before it is at the lift's top, and the road after it at the
lift's bottom, then climbs back.

Three more full-raycast lifts check the Animation panel's settings (flags as in SW_RACER_RE
src/types_enums.h swrModel_AnimationFlags, read by swrModel_LoadAnimation):
- lift_once: Loop off (no 0x10). It plays its down-and-up once at the start of the race and stays
  at the top, so by the time the pod gets there it is flat.
- lift_hold: Loop Length 4 s on the same 2 s motion: it rises at the same speed, every 4 s.
- lift_smooth: down only, looping with Smooth Wrap (0x40), which no stock animation uses. Loading
  sets the blend's speed to 0 (SW_RACER_RE swrModel.c:566; only swrModel_AnimationsSetSettings sets
  one), so the first wrap divides by it and the animation time goes NaN: the lift freezes.

The rest (spinner: rotation, pulse: scale, scroll: UV scroll) show in screenshots.
verify() re-imports the export and reads the Animation panel's settings back.
"""
import math
import os
from collections import Counter

import bpy
from mathutils import Vector

import course as C
import lib
import signs

LIFT = 150.0
PERIOD_S = 2.0
FPS = 60


def action_fcurves(obj):
    """Blender 5 keeps fcurves in the action's layers/strips/channelbags."""
    action = obj.animation_data.action
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    out = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def animate(obj, path, values, period_s=PERIOD_S, loop=True):
    n = len(values) - 1
    for i, value in enumerate(values):
        setattr(obj, path, value)
        obj.keyframe_insert(path, frame=i * period_s * FPS / n)
    for fc in action_fcurves(obj):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
        if loop:
            fc.modifiers.new('CYCLES')     # the Animation panel's Loop


def build(addon):
    model, track, sky = lib.new_track_scene(addon)
    bpy.context.scene.render.fps = FPS
    # key times are frames; the add-on turns them into seconds with the scene's fps at export
    assert bpy.context.scene.render.fps == FPS and bpy.context.scene.render.fps_base == 1.0
    road_mat = lib.material(addon, "anim_road", lib.checker_image("anim_checker"))
    white_mat = lib.material(addon, "anim_white", lib.flat_image("anim_white", (1, 1, 1, 1)))
    scroll_mat = lib.material(addon, "anim_scroll", lib.checker_image("anim_scroll_checker",
                                                                      a=(1, 0.8, 0.3, 1), b=(0.3, 0.2, 0.6, 1)))
    scroll_mat.scroll_y = 1.0     # one texture repeat per second (Material.unmake: |scroll| s per loop)
    sign_mat = lib.material(addon, "anim_signs", signs.atlas_image())

    climb = LIFT / math.tan(math.radians(8))
    # two lifts: the second sets the "elevation" flag (behavior unk1 0x10, FULL_RAYCAST), so the pod's
    # ground ray tests the mesh where it is now rather than the track mesh the game cached under the
    # spline at load (swrRace.c:3717, swrSpline BakeSampleTrackMesh 0x47ea20)
    segs = [C.straight(C.APRON, "grid"), C.straight(1000, "start"), C.straight(1500, "before_lift"), C.straight(1800, "lift"),
            C.straight(800, "after_lift", drop=LIFT), C.ramp(climb, 8, "after_lift"),
            C.straight(1500, "before_lift_fr"), C.straight(1800, "lift_fr"),
            C.straight(800, "after_lift_fr", drop=LIFT), C.ramp(climb, 8, "after_lift_fr"),
            C.straight(1500, "before_lift_once"), C.straight(1800, "lift_once"),
            C.straight(800, "after_lift_once", drop=LIFT), C.ramp(climb, 8, "after_lift_once"),
            C.straight(1500, "before_lift_hold"), C.straight(6000, "lift_hold"),
            C.straight(800, "after_lift_hold", drop=LIFT), C.ramp(climb, 8, "after_lift_hold"),
            C.straight(1500, "before_lift_smooth"), C.straight(1800, "lift_smooth"),
            C.straight(800, "after_lift_smooth", drop=LIFT), C.ramp(climb, 8, "after_lift_smooth"),
            C.straight(1500, "spinner"), C.straight(1500, "pulse"), C.straight(1500, "scroll"),
            C.straight(C.RUNOUT, "finish"), C.straight(C.OVERRUN, "overrun")]
    a = sum(s.length for s in segs)
    course = C.Course(segs, origin=(-a / 2, 0.0), start_s=C.APRON, overrun=C.OVERRUN)
    assert course.extent() < 32000
    # the lift segment is laid out at road level; the drop before "after_lift" lowers the rest
    roads = course.road(track, road_mat, colors={"lift": (0.6, 1.0, 0.6), "lift_fr": (0.6, 0.8, 1.0),
                                                 "lift_once": (1.0, 0.8, 0.6), "lift_hold": (1.0, 0.6, 0.9),
                                                 "lift_smooth": (0.9, 0.9, 0.5)})
    for name, objs in roads.items():
        for obj in objs:
            lib.set_surface(obj)
            lib.shade(obj)
    for obj in roads["scroll"]:
        obj.data.materials[0] = scroll_mat
    bpy.context.view_layer.update()

    # the lift: one mesh, its object moved down and back up (relative to where it was built)
    for name in ("lift", "lift_fr"):
        lift = roads[name][0]
        if name == "lift_fr":
            lift.elevation = True
        animate(lift, "location", [Vector((0, 0, 0)), Vector((0, 0, -lib.g(LIFT))), Vector((0, 0, 0))])
    down_up = [Vector((0, 0, 0)), Vector((0, 0, -lib.g(LIFT))), Vector((0, 0, 0))]
    lift = roads["lift_once"][0]
    lift.elevation = True
    animate(lift, "location", down_up, loop=False)
    lift = roads["lift_hold"][0]
    lift.elevation = True
    animate(lift, "location", down_up)
    lift.anim_loop_length = 2 * PERIOD_S
    lift = roads["lift_smooth"][0]
    lift.elevation = True
    animate(lift, "location", [Vector((0, 0, 0)), Vector((0, 0, -lib.g(LIFT)))], period_s=PERIOD_S / 2)
    lift.anim_loop_transition = True

    def beside(station, side=1, up=150):
        s0, s1 = course.station_range(station)
        mid = course.frame((s0 + s1) / 2)
        h = mid['heading']
        return mid['pos'] + Vector((-math.sin(h), math.cos(h), 0)) * 500 * side + Vector((0, 0, up))

    spinner = lib.box("spinner", (0, 0, 0), (600, 60, 60), track, white_mat, collidable=False)
    spinner.location = lib.g(*beside("spinner"))
    lib.shade(spinner, tint=(1, 0.5, 0.3))
    animate(spinner, "rotation_euler", [Vector((0, 0, 0)), Vector((0, 0, math.pi)), Vector((0, 0, 2 * math.pi))])
    pulse = lib.box("pulse", (0, 0, 0), (200, 200, 200), track, white_mat, collidable=False)
    pulse.location = lib.g(*beside("pulse"))
    lib.shade(pulse, tint=(0.4, 0.7, 1))
    animate(pulse, "scale", [Vector((1, 1, 1)), Vector((1.8, 1.8, 1.8)), Vector((1, 1, 1))])

    for name, lines in (("before_lift", ["LIFT AHEAD", "-150 / 2 S"]),
                        ("before_lift_fr", ["LIFT AHEAD", "FULL RAYCAST"]),
                        ("before_lift_once", ["LIFT AHEAD", "LOOP OFF"]),
                        ("before_lift_hold", ["LIFT AHEAD", "LOOP LENGTH 4 S"]),
                        ("before_lift_smooth", ["LIFT AHEAD", "SMOOTH WRAP"]),
                        ("spinner", ["ROTATION", "1 TURN / 2 S"]),
                        ("pulse", ["SCALE", "X1.8 / 2 S"]), ("scroll", ["UV SCROLL", "1 / S"])):
        signs.station_sign(course, name, lines, track, sign_mat)

    course.spline(model)

    stations = []
    for name in ("lift", "lift_fr"):
        s0, s1 = course.station_range(name)
        stations.append({"name": name, "s": [round(s0, 1), round(s1, 1)], "measure": ["lift"],
                         # the lift rises LIFT in half a period; without full raycast the pod
                         # rides the mesh cached at load and doesn't move (measured swing ~4)
                         "predict": {"swing": {"gt": LIFT * 0.6, "lt": LIFT * 1.2},
                                     "rise_rate": {"gt": LIFT / (PERIOD_S / 2) * 0.85,
                                                   "lt": LIFT / (PERIOD_S / 2) * 1.15}}
                         if name == "lift_fr" else {"swing": {"lt": 20}},
                         "source": "authored: z 0 -> -150 -> 0 over 2 s, linear, looping; the add-on writes "
                                   "key times as frame / fps (swe1r/modelblock.py Anim)"})
    rise = {"gt": LIFT / (PERIOD_S / 2) * 0.85, "lt": LIFT / (PERIOD_S / 2) * 1.15}
    for name, predict, source in (
            ("lift_once", {"swing": {"lt": 20}},
             "Loop off: no flag 0x10, so the animation plays once from the race start and holds its last key (the top)"),
            ("lift_hold", {"rise_rate": rise, "period": {"gt": 2 * PERIOD_S * 0.9, "lt": 2 * PERIOD_S * 1.1}},
             "Loop Length 4 s: duration4/5 = 4 on a 2 s down-and-up, so it rises at the same speed every 4 s "
             "(swrModel_LoadAnimation loops on duration4)"),
            ("lift_smooth", {"swing": {"lt": 20}},
             "Smooth Wrap (0x40): swrModel_AnimationHandleLoopTransition 0x426290 divides by "
             "loop_transition_speed, which swrModel_LoadAnimation sets to 0, so the lift freezes at its first wrap")):
        s0, s1 = course.station_range(name)
        stations.append({"name": name, "s": [round(s0, 1), round(s1, 1)], "measure": ["lift"], "predict": predict,
                         "source": source})
    for name in ("spinner", "pulse", "scroll"):
        r = course.station_range(name)
        stations.append({"name": name, "s": [round(r[0], 1), round(r[1], 1)], "measure": [], "predict": {},
                         "source": "visual: screenshots"})
    return model, {"level": "museum_animation", "length": round(course.length, 1),
                   "centerline": course.describe(), "stations": stations, "lap": {"finishes": True}}


def verify(addon, out_dir, expectations):
    """Re-import the export: the Animation panel's Loop, Smooth Wrap and Loop Length come back as set."""
    imp = lib.addon_module(addon, "swr_import")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imp.import_model(out_dir + os.sep, [1], lambda *a, **k: None)
    have = Counter((obj.anim_loop, obj.anim_loop_transition, round(obj.anim_loop_length, 2))
                   for obj in bpy.data.objects if obj.animation_data and obj.animation_data.action)
    # lift, lift_fr, spinner, pulse loop plainly; lift_once doesn't; lift_hold waits; lift_smooth wraps
    want = Counter({(True, False, 0.0): 4, (False, False, 0.0): 1, (True, False, 2 * PERIOD_S): 1,
                    (True, True, 0.0): 1})
    return [f"animation settings: expected {dict(want)}, got {dict(have)}"] if have != want else []
