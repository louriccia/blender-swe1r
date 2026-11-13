"""Builds bake_demo.blend: one labelled station per vertex color baking and pod lighting feature.

    "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" -b --factory-startup ^
        --python scripts/bake_demo.py -- scripts/out/bake_demo.blend

Every station is baked when the file is built, so it opens ready to look at. Open it with the
viewport in Material Preview (it is saved that way) to see the colors the game would draw. Re-bake
any station by selecting its meshes and clicking Selected > Visible > Vertex Colors > Bake. The
README text block in the file says what each station shows and what to try.
"""
import importlib.util
import math
import os
import sys

import bpy

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = "swe1r_addon"
SPACING = 40.0  # Blender units between stations, far enough that one station's lights barely reach the next

README = """SWE1R vertex color bake demo
============================
Each station is labelled on the ground. All were baked when the file was built. To re-bake one,
select its meshes and click Selected > Visible > Vertex Colors > Bake. Bake only changes the
selected meshes; the lights and settings are shared by the whole scene. View in Material Preview
with the Standard view transform (both are set) to see the colors the game would draw.

1  SIMPLE vs CYCLES: the same pillar and sun, baked with each Method. Simple: one hard shadow per
   vertex. Cycles: soft shadows and bounce light, per face corner.
2  CAST SHADOWS: the left pane has Cast Shadows off (glass), the right one on. Only the right one
   shadows the floor.
3  SKIP IN BAKE: the red block has hand-painted vertex colors and Skip in Bake on. It was selected
   for the bake with its floor and kept its red.
4  SKYBOX: the blue dome around the whole scene is in a Skybox collection. It never casts
   shadows (the sun still reaches every station) and Bake never changes its colors, even when
   it is selected.
5  EMISSION: a dark hut with no light inside except its ceiling lamp. The lamp's material has
   Emission (Cycles bake) 1.5 in the Material panel, so it lights the floor in a Cycles bake. The
   lamp itself has Skip in Bake on, so it stays white.
6  CUTOUT: a fence with a Cutout material. In a Cycles bake light passes through the holes, so its
   shadow is striped.
7  POD LIGHTS: the red point light and the amber sun are Pod Lighting lights on the collision
   floor (look at Selected > Collidable > Pod Lighting). Bake leaves pod lights out unless Include
   Pod Lights is on: the left floor was baked without (ambient only), the right one with. The
   scene's main sun was left out of these two bakes so the pod lights' colors show. The sun is a Sun light,
   so it exports as a direction (no Point flag); the red light is a Point light at its position.
   The right floor also has Flicker on, with its Flicker Axis along X.
8  GAME COLORS: texture brightness rises front to back, vertex color brightness left to right.
   In Material Preview with Standard every point shows texture x vertex color the way the game
   multiplies them (within 1-2 of 255). Try AgX (Render Properties > Color Management) to see
   how much darker Blender's default makes the dark corner.
"""


def load_addon():
    if PACKAGE in sys.modules:
        return sys.modules[PACKAGE]
    spec = importlib.util.spec_from_file_location(
        PACKAGE, os.path.join(ADDON_DIR, "__init__.py"), submodule_search_locations=[ADDON_DIR])
    package = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = package
    spec.loader.exec_module(package)
    package.register()
    return package


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)


def collection(name, parent=None):
    coll = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def link(obj, coll):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    coll.objects.link(obj)
    return obj


def mesh(op, coll, name, cuts=0, **kwargs):
    op(**kwargs)
    obj = bpy.context.object
    obj.name = name
    if cuts:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=cuts)
        bpy.ops.object.mode_set(mode='OBJECT')
    obj.visible = True
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name='uv')
    obj.data.vertex_colors.new(name='colors')
    return link(obj, coll)


def floor(coll, x, name='floor', size=16, y=0.0, cuts=24):
    return mesh(bpy.ops.mesh.primitive_plane_add, coll, name, cuts=cuts, size=size, location=(x, y, 0))


def box(coll, name, location, scale, cuts=3):
    obj = mesh(bpy.ops.mesh.primitive_cube_add, coll, name, cuts=cuts, size=1, location=location)
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def label(coll, text, x, y=-10.5):
    curve = bpy.data.curves.new(f"label {text}", 'FONT')
    curve.body = text
    curve.size = 1.4
    curve.align_x = 'CENTER'
    obj = bpy.data.objects.new(f"label {text}", curve)
    obj.location = (x, y, 0.02)
    coll.objects.link(obj)
    return obj


def select(objs):
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def game_materials(objs):
    select(objs)
    bpy.ops.view3d.remake_materials()


def set_material(obj, image=None, blend=None, emission=None):
    from swe1r_addon.swe1r.modelblock import Material
    material = obj.material_slots[0].material.copy()
    material.name = f"{obj.name} material"
    obj.material_slots[0].material = material
    if blend:
        material.blend_mode = blend
    if emission is not None:
        material.bake_emission = emission
    obj.material_slots[0].material = Material(None, None).remake(material, tex_name=image.name if image else None)


def paint(obj, color):
    data = obj.data.vertex_colors.active.data
    data.foreach_set('color', [*color, 1.0] * len(data))


def bake(objs, method='CYCLES', lights=None, **settings):
    """Bake objs with the given Method; lights, when given, are the only lights that count."""
    scene = bpy.context.scene
    scene.bake_method = method
    for key, value in settings.items():
        setattr(scene, key, value)
    hidden = []
    if lights is not None:
        for obj in scene.objects:
            if obj.type == 'LIGHT' and obj not in lights and not obj.hide_render:
                obj.hide_render = True
                hidden.append(obj)
    select(objs)
    result = bpy.ops.view3d.bake_vcolors()
    for obj in hidden:
        obj.hide_render = False
    scene.bake_pod_lights = False
    print(f"baked {[o.name for o in objs]} with {method}: {result}")


def image(name, width, height, pixel):
    img = bpy.data.images.new(name, width, height, alpha=True)
    pixels = []
    for y in range(height):
        for x in range(width):
            pixels.extend(pixel(x, y))
    img.pixels = pixels
    img.pack()
    return img


def build():
    scene = bpy.context.scene
    scene.ambient_light = (1.0, 1.0, 1.0)
    scene.ambient_light_intensity = 0.12
    scene.bake_samples = 512
    scene.light_falloff = 1.0
    scene.view_settings.view_transform = 'Standard'

    sun_data = bpy.data.lights.new("sun", 'SUN')
    sun_data.energy = 1.0
    sun = bpy.data.objects.new("sun", sun_data)
    sun.rotation_euler = (math.radians(40), math.radians(20), math.radians(30))
    scene.collection.objects.link(sun)
    sky_light = [sun]

    track = collection("Demo track")

    # 1 Simple vs Cycles
    x = 0.0
    s1 = collection("1 Simple vs Cycles", track)
    a = floor(s1, x - 9, 'simple floor', size=16)
    a_pillar = box(s1, 'simple pillar', (x - 9, 0, 2.5), (2, 2, 5))
    b = floor(s1, x + 9, 'cycles floor', size=16)
    b_pillar = box(s1, 'cycles pillar', (x + 9, 0, 2.5), (2, 2, 5))
    label(s1, "1 SIMPLE  |  CYCLES", x)
    game_materials([a, a_pillar, b, b_pillar])
    bake([a, a_pillar], 'SIMPLE', lights=sky_light)
    bake([b, b_pillar], 'CYCLES', lights=sky_light)

    # 2 Cast Shadows
    x += SPACING + 9
    s2 = collection("2 Cast Shadows", track)
    f = floor(s2, x)
    glass = box(s2, 'glass pane (Cast Shadows off)', (x - 3.5, 0, 3), (5, 0.3, 6), cuts=1)
    wall = box(s2, 'wall (Cast Shadows on)', (x + 3.5, 0, 3), (5, 0.3, 6), cuts=1)
    glass.visible_shadow = False
    label(s2, "2 CAST SHADOWS: off | on", x)
    game_materials([f, glass, wall])
    paint(glass, (0.6, 0.85, 1.0))
    glass.bake_skip = True
    bake([f, wall, glass], lights=sky_light)

    # 3 Skip in Bake
    x += SPACING
    s3 = collection("3 Skip in Bake", track)
    f = floor(s3, x)
    red = box(s3, 'hand painted (Skip in Bake)', (x, 0, 1.5), (3, 3, 3))
    label(s3, "3 SKIP IN BAKE", x)
    game_materials([f, red])
    paint(red, (1.0, 0.15, 0.1))
    red.bake_skip = True
    bake([f, red], lights=sky_light)

    # 4 Skybox: a dome around everything; selected with this station's floor when baking
    x += SPACING
    sky = collection("Skybox", track)
    sky.collection_type = '1'
    dome = mesh(bpy.ops.mesh.primitive_uv_sphere_add, sky, 'sky dome', radius=400, location=(140, 0, 0),
                segments=32, ring_count=16)
    # seen from inside: face the normals inward, or backface culling hides it
    select([dome])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode='OBJECT')
    s4 = collection("4 Skybox", track)
    f = floor(s4, x)
    label(s4, "4 SKYBOX: no shadow, never baked", x)
    game_materials([f, dome])
    paint(dome, (0.35, 0.55, 0.95))
    bake([f, dome], lights=sky_light)

    # 5 Emission: a closed hut lit only by its ceiling lamp
    x += SPACING
    s5 = collection("5 Emission", track)
    f = floor(s5, x, 'hut floor', size=10)
    walls = [
        box(s5, 'hut roof', (x, 0, 4.1), (10, 10, 0.2)),
        box(s5, 'hut wall back', (x, 4.9, 2), (10, 0.2, 4)),
        box(s5, 'hut wall left', (x - 4.9, 0, 2), (0.2, 10, 4)),
        box(s5, 'hut wall right', (x + 4.9, 0, 2), (0.2, 10, 4)),
    ]
    lamp = mesh(bpy.ops.mesh.primitive_plane_add, s5, 'ceiling lamp (Emission 1.5)', size=2, location=(x, 0, 3.95))
    lamp.rotation_euler = (math.pi, 0, 0)
    label(s5, "5 EMISSION: lamp lights the hut", x)
    game_materials([f, lamp, *walls])
    set_material(lamp, emission=1.5)
    lamp.bake_skip = True
    bake([f, *walls], lights=[])

    # 6 Cutout fence
    x += SPACING
    s6 = collection("6 Cutout", track)
    # vertex colors only resolve a shadow as fine as the vertex spacing: a dense floor here
    f = floor(s6, x, cuts=60)
    fence = mesh(bpy.ops.mesh.primitive_plane_add, s6, 'cutout fence', size=8, location=(x, 0, 4))
    fence.rotation_euler = (math.radians(90), 0, 0)
    bars = image("demo fence", 16, 16, lambda px, py: (0.55, 0.45, 0.3, 1.0 if px % 4 < 2 or py % 8 < 2 else 0.0))
    label(s6, "6 CUTOUT: light through the holes", x)
    game_materials([f, fence])
    set_material(fence, image=bars, blend='CUTOUT')
    bake([f, fence], lights=sky_light)

    # 7 Pod lights
    x += SPACING + 9
    s7 = collection("7 Pod lights", track)
    left = floor(s7, x - 9, 'collision floor, baked without pod lights', size=16)
    right = floor(s7, x + 9, 'collision floor, baked with pod lights', size=16)
    red_data = bpy.data.lights.new('pod_lighting red (Point)', 'POINT')
    red_data.color = (1.0, 0.1, 0.05)
    red_data.energy = 150
    red_light = bpy.data.objects.new('pod_lighting red (Point)', red_data)
    red_light.location = (x + 9, -3, 3)
    s7.objects.link(red_light)
    amber_data = bpy.data.lights.new('pod_lighting amber (Sun)', 'SUN')
    amber_data.color = (1.0, 0.6, 0.2)
    amber_data.energy = 0.35
    amber = bpy.data.objects.new('pod_lighting amber (Sun)', amber_data)
    amber.rotation_euler = (math.radians(-35), 0, 0)
    amber.location = (x, -6, 6)
    s7.objects.link(amber)
    for obj, light in ((left, red_data), (right, amber_data)):
        obj.collidable = True
        obj.collision_data = True
        obj.lighting_light = light
        obj.lighting_invert = light.type != 'SUN'
        obj.lighting_color = (0.4, 0.4, 0.45)
    right.lighting_flicker = True
    right.lighting_flicker_axis = (1.0, 0.0, 0.0)
    label(s7, "7 POD LIGHTS: excluded | included", x)
    game_materials([left, right])
    # the station's sun is left out so the pod lights are the only light here
    bake([left], lights=[red_light, amber])
    bake([right], lights=[red_light, amber], bake_pod_lights=True)

    # 8 Game colors: texture brightness x vertex color brightness
    x += SPACING + 9
    s8 = collection("8 Game colors", track)
    grid = mesh(bpy.ops.mesh.primitive_plane_add, s8, 'texture x vertex color', size=12, location=(x, 0, 0.01))
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=7)
    bpy.ops.object.mode_set(mode='OBJECT')
    ramp = image("demo ramp", 8, 8, lambda px, py: ((py + 0.5) / 8, (py + 0.5) / 8, (py + 0.5) / 8, 1.0))
    label(s8, "8 GAME COLORS: texture x vertex color", x)
    game_materials([grid])
    set_material(grid, image=ramp)
    data = grid.data
    colors = []
    for loop in data.loops:
        v = (data.vertices[loop.vertex_index].co.x / 12 + 0.5)
        colors.extend((v, v, v, 1.0))
    data.vertex_colors.active.data.foreach_set('color', colors)
    grid.bake_skip = True

    cam_data = bpy.data.cameras.new('overview')
    cam = bpy.data.objects.new('overview', cam_data)
    cam.location = (150, -150, 120)
    cam.rotation_euler = (math.radians(55), 0, math.radians(45))
    cam_data.clip_end = 2000
    scene.collection.objects.link(cam)
    scene.camera = cam

    text = bpy.data.texts.new("README")
    text.write(README)

    # open in Material Preview, looking at the stations
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'
                        space.clip_end = 3000
                        region = space.region_3d
                        region.view_location = (150, 0, 0)
                        region.view_distance = 220
            elif area.type == 'TEXT_EDITOR':
                area.spaces[0].text = text
    select([sun])


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[0] if argv else os.path.join(ADDON_DIR, "scripts", "out", "bake_demo.blend"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    load_addon()
    clear_scene()
    build()
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
