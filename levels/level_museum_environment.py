"""Museum, environment wing: per-surface fog, draw distance and lighting.

Each exhibit is a road mesh whose collision data sets fog or light. The telemetry gets the fog and
light the game read from the mesh under the pod (its behavior struct), which must be the bytes the
add-on wrote for the Blender settings. It also gets the camera's state, which shows what the game
made of them (swrObjcMan_UpdateTerrainVisuals 0x451a80):

- `fog_flags & 1` turns fog on with `fog_start` and the fog colour (which is also the background
  colour). `fog_start` is an N64-style fog value, not a distance: the game clamps it to 996 (the
  literal 0x44790000), and 0 or less turns fog off.
- `fog_flags & 2` sets the draw distance (far clip) to `fog_end`.
- Any non-zero `light_flags` overrides the light (swrObjcMan_LoadLightingFromBehavior 0x451800).

Screenshots show the look. Track geometry with baked vertex colours isn't lit, so lighting shows
on the pod.
"""
import math

import bpy
from mathutils import Vector

import course as C
import lib
import signs

LENGTH = 1500.0     # the camera eases fog colour at 195/s and draw distance at 2000/s
SRC = "SW_RACER_RE ghidra swrObjcMan_UpdateTerrainVisuals 0x451a80"

# camera flag word (stagingTransformFocus.vD.y, mis-typed in src/types.h)
CAM_DRAW = 0x1
CAM_FOG = 0x2
CAM_SKY_HIDDEN = 0x4


def ex(name, title, lines, fog=None, light=None, predict=None, source=SRC):
    return dict(name=name, title=title, lines=lines, fog=fog or {}, light=light, predict=predict or {},
                source=source)


EXHIBITS = [
    # the add-on writes the fog colour/start/end defaults even with no fog flag set (harmless)
    ex("env_plain", "NO FOG / LIGHT", ["FLAGS 0"], predict={"fog": [0, 255, 255, 255, 1000, 30000]}),
    ex("fog_red", "FOG RED", ["START 500"], fog=dict(fog_color_update=True, fog_color=(1, 0, 0), fog_min=500),
       predict={"fog": [1, 255, 0, 0, 500, 30000], "cam_flags": {"bits": CAM_FOG}, "fog_start_target": 500}),
    ex("fog_blue_996", "FOG BLUE", ["START 5000", "GAME CLAMPS 996"],
       fog=dict(fog_color_update=True, fog_color=(0, 0, 1), fog_min=5000),
       predict={"fog": [1, 0, 0, 255, 5000, 30000], "fog_start_target": 996}),
    ex("fog_clear", "FOG CLEAR", ["START 0", "FOG OFF"],
       fog=dict(fog_clear=True),
       predict={"fog": [1, 255, 255, 255, 0, 30000], "cam_flags": {"no_bits": CAM_FOG}}),
    ex("draw_2000", "DRAW 2000", ["FAR CLIP"], fog=dict(fog_range_update=True, fog_max=2000),
       predict={"fog": [2, 255, 255, 255, 1000, 2000], "cam_flags": {"bits": CAM_DRAW}, "draw_set": 2000}),
    ex("draw_30000", "DRAW 30000", ["FAR CLIP"], fog=dict(fog_range_update=True, fog_max=30000),
       predict={"fog": [2, 255, 255, 255, 1000, 30000], "draw_set": 30000}),
    ex("light_red", "LIGHT RED", ["AMBIENT 0.2"], light=dict(color=(1, 0, 0), ambient=(0.2, 0.2, 0.2)),
       predict={"light_flags": 3, "light_rgb": [51, 51, 51, 255, 0, 0]}),
    ex("light_invert", "LIGHT 0X4", ["ADD-ON: INVERT", "GAME: POSITION"],
       light=dict(color=(0, 1, 0), ambient=(0.2, 0.2, 0.2), lighting_invert=True),
       predict={"light_flags": 7}),
    ex("light_flicker", "LIGHT 0X8", ["FLICKER"],
       light=dict(color=(0, 0, 1), ambient=(0.2, 0.2, 0.2), lighting_flicker=True),
       predict={"light_flags": 11}),
    ex("light_persist", "LIGHT 0X10", ["PERSISTENT", "(BASE LIGHT)"],
       light=dict(color=(1, 1, 0), ambient=(0.4, 0.4, 0.4), lighting_persistent=True),
       predict={"light_flags": 19}),
    ex("after_light", "NO LIGHT DATA", ["KEEPS THE LAST?"], predict={"light_flags": 0}),
]


def build(addon):
    model, track, sky = lib.new_track_scene(addon)
    road_mat = lib.material(addon, "env_road", lib.checker_image("env_checker"))
    white_mat = lib.material(addon, "env_white", lib.flat_image("env_white", (1, 1, 1, 1)))
    sign_mat = lib.material(addon, "env_signs", signs.atlas_image())
    course = C.exhibit_loop([(e["name"], LENGTH) for e in EXHIBITS], gap=300.0)
    names = {e["name"] for e in EXHIBITS}
    colors = {n: ((0.8, 0.95, 0.8) if n in names else (0.85, 0.85, 0.85)) for n in {s['station'] for s in course.samples}}
    roads = course.road(track, road_mat, colors=colors)
    for objs in roads.values():
        for obj in objs:
            lib.shade(obj)

    # posts every 500 along both sides, so fog and draw distance show in the screenshots
    for i, smp in enumerate(course.samples[::5]):
        h = smp['heading']
        left = Vector((-math.sin(h), math.cos(h), 0))
        for k in (1, -1):
            post = lib.box(f"post_{i}_{k}", tuple(smp['pos'] + left * k * 400 + Vector((0, 0, 150))),
                           (40, 40, 300), track, white_mat, collidable=False)
            lib.shade(post, tint=(0.9, 0.5, 0.2) if k > 0 else (0.3, 0.6, 0.9))

    entries = []
    for e in EXHIBITS:
        for obj in roads[e["name"]]:
            for key, value in e["fog"].items():
                setattr(obj, key, value)
            if e["light"]:
                light = e["light"]
                data = bpy.data.lights.new(f"light_{e['name']}", 'SUN')
                data.color = light["color"]
                lamp = bpy.data.objects.new(data.name, data)   # same name: the add-on looks it up by name
                track.objects.link(lamp)
                s0, s1 = course.station_range(e["name"])
                lamp.location = lib.g(*(course.frame(s0)['pos'] + Vector((0, 0, 1000))))
                obj.lighting_light = data
                obj.lighting_color = light["ambient"]
                for flag in ("lighting_invert", "lighting_flicker", "lighting_persistent"):
                    setattr(obj, flag, light.get(flag, False))
        signs.station_sign(course, e["name"], [e["title"], *e["lines"]], track, sign_mat)
        s0, s1 = course.station_range(e["name"])
        entries.append({"name": e["name"], "s": [round(s0, 1), round(s1, 1)], "measure": ["env"],
                        "predict": e["predict"], "source": e["source"]})

    lib.spline("spline", course.spline_points(), model)
    return model, {"level": "museum_environment", "length": round(course.length, 1),
                   "centerline": course.describe(), "stations": entries, "lap": {"finishes": True}}
