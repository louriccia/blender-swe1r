"""Headless Blender round-trip tests against the game's real .bin files.

Run inside Blender (see tests/blender/run.py, which finds Blender and sets this up):

    blender --background --factory-startup --python tests/blender/roundtrip.py -- [--full] [--models 2,109]

For each model: import it, export it into a scratch copy of the game data, and check that
  - the export doesn't touch any other asset in the blocks,
  - re-importing the export behaves the same in game: the same visual and collision triangles in world
    space (however they are grouped into meshes and nodes), the same materials and surface flags, the same
    animated motion, the same nodes behind each header slot, the same spline,
  - repeated export/import settles: after one round-trip, exporting again gives the same size,
  - every exported display list loads vertices the way the game's renderer requires.
The game's own files are never written; everything happens in a temp copy.
"""
import argparse
import importlib
import importlib.util
import json
import os
import shutil
import struct
import sys
import tempfile
import traceback
import unittest
from collections import Counter
from itertools import permutations

import bpy

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKAGE = "swe1r_addon"
DEFAULT_GAME_DATA = r"C:\Program Files (x86)\Steam\steamapps\common\Star Wars Episode I Racer\data\lev01"
BLOCK_FILES = ["out_modelblock.bin", "out_textureblock.bin", "out_splineblock.bin"]

# One or two of each exportable type, picked for coverage: deep node hierarchies with pivots
# (Pit Droid, Opee Sea Killer), Podd + MAlt merging, a track with a spline, animated scenery.
SMOKE_MODELS = [
    2,    # Podd  Anakin Skywalker
    6,    # Podd  Sebulba
    109,  # Pupp  Pit Droid
    155,  # Pupp  Opee Sea Killer
    1,    # Trak  The Boonta Classic (+ spline 10)
    47,   # Part  Sentry
    197,  # Modl  Flag
    149,  # Scen  Jabba's Spectator Booth
]


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


def game_data_dir():
    path = os.environ.get("SWE1R_GAME_DATA", DEFAULT_GAME_DATA)
    for f in BLOCK_FILES:
        if not (os.path.exists(os.path.join(path, f + ".bak")) or os.path.exists(os.path.join(path, f))):
            return None
    return path


def copy_game_data(src, dst):
    for f in BLOCK_FILES:
        # prefer the add-on's pristine backup in case the live file has been modded
        original = os.path.join(src, f + ".bak")
        shutil.copy(original if os.path.exists(original) else os.path.join(src, f), os.path.join(dst, f))


def no_progress(*args, **kwargs):
    pass


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def model_collection(model_id):
    for col in bpy.context.scene.collection.children:
        if col.get("header") is not None and str(col.export_model) == str(model_id):
            return col
    raise AssertionError(f"import created no collection for model {model_id}")


def read_block(path, items_per_asset):
    block_module = importlib.import_module(f"{PACKAGE}.swe1r.block")
    return block_module.Block(path, items_per_asset).read()


def all_objects(col):
    objs = list(col.objects)
    for child in col.children:
        objs += all_objects(child)
    return objs


TOLERANCE = 0.02  # Blender units, i.e. 2 game units: positions are int16 game units imported at scale 0.01
ANIMATION_SAMPLES = 4
SURFACE_FLAGS = None  # filled from the add-on's SurfaceEnum on first use


def rounded(values, digits=3):
    return tuple(round(v, digits) + 0.0 for v in values)  # + 0.0 folds -0.0 into 0.0


def material_key(obj, index):
    """What the game draws a visual triangle with: texture size and the material's render settings."""
    if index >= len(obj.material_slots) or not obj.material_slots[index].material:
        return None
    mat = obj.material_slots[index].material
    size = None
    if mat.node_tree:
        size = next((tuple(n.image.size) for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None)
    return (size, rounded((mat.scroll_x, mat.scroll_y)), mat.flip_x, mat.flip_y, mat.clip_x, mat.clip_y, mat.transparent)


def collision_key(obj):
    """What the game does when a pod touches a collision triangle."""
    global SURFACE_FLAGS
    if SURFACE_FLAGS is None:
        surface_enum = importlib.import_module(f"{PACKAGE}.swe1r.modelblock").SurfaceEnum
        SURFACE_FLAGS = sorted(f for f in dir(surface_enum) if not f.startswith("__"))
    return (tuple(f for f in SURFACE_FLAGS if getattr(obj, f)), obj.magnet, obj.strict_spline, obj.elevation,
            obj.trigger_id, obj.trigger_settings)


SELECTOR, LOD_SELECTOR = 20581, 20582  # 0x5065 / 0x5066, SW_RACER_RE src/types_enums.h


def drawn(obj):
    """Whether the renderer reaches obj through every selector above it.

    A selector draws only its selected child (-1 all, -2 none) and a LOD selector one child by
    distance (SW_RACER_RE src/types.h swrModel_NodeSelector / swrModel_NodeLODSelector); for LODs
    this counts the highest detail child. Import names nodes by file offset, so sorting children by
    name gives their file order.
    """
    child, parent = obj, obj.parent
    while parent is not None:
        node_type = parent.get('node_type')
        if node_type in (SELECTOR, LOD_SELECTOR):
            index = sorted(parent.children, key=lambda c: c.name).index(child)
            selected = parent.get('selected_child', -1) if node_type == SELECTOR else 0
            if selected == -2 or (selected >= 0 and index != selected):
                return False
        child, parent = parent, parent.parent
    return True


def triangles(col):
    """Every triangle the game would draw or collide with, in world space, keyed by how it behaves.

    Grouping into meshes and nodes is the add-on's choice and may change on export; the triangles
    and what they do are what the game sees.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    tris = []
    for obj in all_objects(col):
        if obj.type != 'MESH' or not (obj.visible or obj.collidable):
            continue
        visible = drawn(obj)  # selectors only gate rendering; collision is checked regardless
        material_keys = {}
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        world = [evaluated.matrix_world @ v.co for v in mesh.vertices]
        collision = collision_key(obj) if obj.collidable else None
        if any(i >= len(world) for tri in mesh.loop_triangles for i in tri.vertices):
            raise ValueError(f"imported mesh {obj.name} has faces referencing missing vertices (invalid mesh)")
        for tri in mesh.loop_triangles:
            if tri.area * obj.matrix_world.median_scale ** 2 < 1e-10:
                continue  # degenerate: nothing to draw or hit
            corners = sorted(tuple(world[i]) for i in tri.vertices)
            if obj.visible and visible:
                if tri.material_index not in material_keys:
                    material_keys[tri.material_index] = material_key(obj, tri.material_index)
                tris.append((("visual", material_keys[tri.material_index]), corners))
            if obj.collidable:
                tris.append((("collision", collision), corners))
        evaluated.to_mesh_clear()
    return tris


def same_corners(a, b, tol):
    # corners are sorted, but near-equal coordinates can sort either way, so try every pairing
    return any(all(abs(x - y) <= tol for p, q in zip(a, perm) for x, y in zip(p, q))
               for perm in permutations(b))


def match_triangles(before, after, tol=TOLERANCE):
    """Pairs up triangles with the same behaviour whose corners are all within tol; returns the leftovers.

    Matches near-exact pairs first: with a single tolerant pass, two nearby sliver triangles can
    grab each other's partners and leave both unmatched.
    """
    lost, gained = before, after
    for pass_tol in (tol / 100, tol):
        lost, gained = _match_pass(lost, gained, pass_tol)
    return lost, gained


def _match_pass(before, after, tol):
    def cell(corners):
        return tuple(int(sum(c[i] for c in corners) / 3 // tol) for i in range(3))

    grid = {}
    for key, corners in after:
        grid.setdefault((key, cell(corners)), []).append(corners)
    neighbours = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)]
    lost = []
    for key, corners in before:
        cx, cy, cz = cell(corners)
        for dx, dy, dz in neighbours:
            bucket = grid.get((key, (cx + dx, cy + dy, cz + dz)), [])
            match = next((i for i, other in enumerate(bucket) if same_corners(corners, other, tol)), None)
            if match is not None:
                bucket.pop(match)
                break
        else:
            lost.append((key, corners))
    gained = [(key, c) for (key, _), bucket in grid.items() for c in bucket]
    return lost, gained


def animation_frames(col):
    ranges = [obj.animation_data.action.frame_range for obj in all_objects(col)
              if obj.animation_data and obj.animation_data.action]
    if not ranges:
        return []
    start, end = min(r[0] for r in ranges), max(r[1] for r in ranges)
    if end <= start:
        return []
    return sorted({round(start + (end - start) * i / (ANIMATION_SAMPLES - 1)) for i in range(ANIMATION_SAMPLES)})


def header_slots(col):
    """The game looks nodes up by header slot (slot 0 is the model root).

    Returns the populated slots, and the world transform of the node behind each slot that import
    turned into an object.
    """
    populated = [i for i, offset in enumerate(col["header"]) if offset]
    transforms = {}
    for obj in all_objects(col):
        for slot in obj.get("header", []):
            m = obj.matrix_world
            transforms[slot] = [m[r][c] for r in range(3) for c in range(4)]
    return populated, transforms


def splines(col):
    points = []
    for obj in all_objects(col):
        if obj.type == 'CURVE':
            for spline in obj.data.splines:
                points += [tuple(obj.matrix_world @ p.co) for p in spline.bezier_points]
                points += [tuple(obj.matrix_world @ p.co.xyz) for p in spline.points]
    return sorted(rounded(p, 2) for p in points)


def set_frame(frame):
    # scene.frame_set also evaluates all 24 game view layers, seconds per call on a track; the
    # snapshot only reads the active one
    bpy.context.scene.frame_current = frame
    bpy.context.view_layer.update()


def snapshot(col):
    """What the game would see of an imported model: geometry and behaviour, not its node layout."""
    set_frame(0)
    snap = {
        "triangles": triangles(col),
        "header_slots": header_slots(col),
        "header_length": len(col["header"]),
        "splines": splines(col),
        "animation": {},
    }
    for frame in animation_frames(col):
        set_frame(frame)
        snap["animation"][frame] = triangles(col)
    set_frame(0)
    return snap


def display_list_problems(buffer, mesh_start, mesh_format):
    """Checks one exported mesh's display list the way the game's renderer reads it.

    SW_RACER_RE dinput_hook/renderer_hook.cpp aborts unless every vertex load (gSPVertex) loads
    into slot v0 == vertex_base_offset; triangles index the slots loaded so far.
    A hooked mesh (vertex_base_offset > 0) draws its prefix with referenced_node's matrix, so that
    pointer must lead to a mesh group node (0x3064).
    """
    fields = struct.unpack_from(mesh_format, buffer, mesh_start)
    referenced_node, display_list, base = fields[11], fields[13], fields[17]
    problems = []
    if not display_list:
        return problems
    if base and (not referenced_node or struct.unpack_from(">I", buffer, referenced_node)[0] != 0x3064):
        problems.append(f"hooked mesh at {mesh_start} does not reference a mesh group node")
    loaded = 0
    cursor = display_list
    while buffer[cursor] != 0xDF:
        kind = buffer[cursor]
        if kind == 1:
            n = (struct.unpack_from(">H", buffer, cursor + 1)[0] >> 4) & 0xFF
            v0 = (buffer[cursor + 3] >> 1) - n
            # n == 0 is only meaningful as a prefix-only load: a mesh whose vertices are all hooked
            if v0 != base or (n == 0 and not base):
                problems.append(f"mesh at {mesh_start}: vertex load n={n} v0={v0}, vertex_base_offset={base}")
            loaded = v0 + n
        elif kind in (5, 6):
            slots = [buffer[cursor + i] // 2 for i in ((1, 2, 3) if kind == 5 else (1, 2, 3, 5, 6, 7))]
            if any(slot >= loaded for slot in slots):
                problems.append(f"mesh at {mesh_start}: triangle uses slot {max(slots)} with {loaded} loaded")
        cursor += 8
    return problems


class RoundTrip:
    """Imports, exports, and re-imports one model, keeping every intermediate for the assertions."""

    def __init__(self, model_id, source_dir, work_root):
        self.model_id = model_id
        self.imp = importlib.import_module(f"{PACKAGE}.swr_import")
        self.exp = importlib.import_module(f"{PACKAGE}.swr_export")
        self.utils = importlib.import_module(f"{PACKAGE}.utils")
        self.original = os.path.join(work_root, "original") + os.sep
        self.first = os.path.join(work_root, "first") + os.sep
        self.second = os.path.join(work_root, "second") + os.sep
        self.third = os.path.join(work_root, "third") + os.sep
        for d in (self.original, self.first, self.second, self.third):
            os.makedirs(d)
        copy_game_data(source_dir, self.original)
        copy_game_data(source_dir, self.first)

    def import_from(self, folder):
        clear_scene()
        self.imp.import_model(folder, [self.model_id], no_progress)
        return model_collection(self.model_id)

    def import_from_recording_meshes(self, folder):
        """import_from, also checking every mesh's display list as it is read."""
        modelblock = importlib.import_module(f"{PACKAGE}.swe1r.modelblock")
        read = modelblock.Mesh.read
        self.display_list_problems = []

        def checking_read(mesh, buffer, cursor):
            self.display_list_problems += display_list_problems(buffer, cursor, mesh.format_string)
            return read(mesh, buffer, cursor)

        modelblock.Mesh.read = checking_read
        try:
            return self.import_from(folder)
        finally:
            modelblock.Mesh.read = read

    def export_to(self, col, folder):
        bpy.context.scene.is_export_separate = False
        bpy.context.scene.is_export_debug = False
        self.exp.export_model(col, folder, [True, True, True], no_progress)

    def run(self):
        col = self.import_from(self.original)
        self.before = snapshot(col)
        self.export_to(col, self.first)

        col = self.import_from_recording_meshes(self.first)
        self.after = snapshot(col)
        # each later export starts from the previous one's blocks, so only the model itself can differ
        for previous, folder in ((self.first, self.second), (self.second, self.third)):
            for f in BLOCK_FILES:
                shutil.copy(previous + f, folder + f)
            self.export_to(col, folder)
            col = self.import_from(folder)


class RoundTripTest(unittest.TestCase):
    model_id = None
    source_dir = None

    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.mkdtemp(prefix=f"swe1r_rt_{cls.model_id}_")
        cls.trip = RoundTrip(cls.model_id, cls.source_dir, cls.work)
        cls.error = None
        try:
            cls.trip.run()
        except Exception:
            cls.error = traceback.format_exc()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def setUp(self):
        # test_round_trip_completes reports the error; the rest have nothing to check
        if self.error and self._testMethodName != "test_round_trip_completes":
            self.skipTest("round-trip raised")

    def test_round_trip_completes(self):
        if self.error:
            self.fail(f"round-trip raised:\n{self.error}")

    def test_export_leaves_other_models_untouched(self):
        trip = self.trip
        before = read_block(trip.original + "out_modelblock.bin", 2)
        after = read_block(trip.first + "out_modelblock.bin", 2)
        self.assertEqual(len(before.data), len(after.data))
        malt = trip.utils.Podd_MAlt.get(str(self.model_id))
        changed = [i for i in range(len(before.data))
                   if i not in (self.model_id, malt) and before.data[i] != after.data[i]]
        self.assertEqual(changed, [], "export modified models it wasn't asked to")

    def test_export_leaves_existing_textures_untouched(self):
        trip = self.trip
        before = read_block(trip.original + "out_textureblock.bin", 2)
        after = read_block(trip.first + "out_textureblock.bin", 2)
        self.assertGreaterEqual(len(after.data), len(before.data))
        changed = [i for i in range(len(before.data)) if before.data[i] != after.data[i]]
        self.assertEqual(changed, [], "export rewrote existing textures")

    def test_export_leaves_other_splines_untouched(self):
        trip = self.trip
        spline_map = importlib.import_module(f"{PACKAGE}.swe1r.spline_map").spline_map
        before = read_block(trip.original + "out_splineblock.bin", 1)
        after = read_block(trip.first + "out_splineblock.bin", 1)
        own = spline_map.get(self.model_id)
        changed = [i for i in range(len(before.data)) if i != own and before.data[i] != after.data[i]]
        self.assertEqual(changed, [], "export modified splines it wasn't asked to")

    def assertSameTriangles(self, before, after, what):
        lost, gained = match_triangles(before, after)
        if lost or gained:
            kinds = Counter(key[0] for key, _ in lost), Counter(key[0] for key, _ in gained)
            self.fail(f"{what}: {len(lost)} of {len(before)} triangles lost {dict(kinds[0])} and {len(gained)} "
                      f"gained {dict(kinds[1])} across the round-trip (tolerance {TOLERANCE})\n"
                      f"  first lost:   {[(k, rounded(sum(c, ()))) for k, c in lost[:2]]}\n"
                      f"  first gained: {[(k, rounded(sum(c, ()))) for k, c in gained[:2]]}")

    def test_geometry_preserved(self):
        """Same visual and collision triangles in the same places, drawn and behaving the same way."""
        self.assertSameTriangles(self.trip.before["triangles"], self.trip.after["triangles"], "frame 0")

    def test_animation_preserved(self):
        """Animated geometry ends up in the same places at sampled frames."""
        before, after = self.trip.before["animation"], self.trip.after["animation"]
        self.assertEqual(sorted(before), sorted(after), "animated frame range changed")
        for frame in before:
            self.assertSameTriangles(before[frame], after[frame], f"frame {frame}")

    def test_header_slots_preserved(self):
        """The game finds attachment points, engines, cameras, etc. by header slot."""
        before, after = self.trip.before, self.trip.after
        self.assertEqual(before["header_length"], after["header_length"], "header slot count changed")
        (populated, transforms), (populated_after, transforms_after) = before["header_slots"], after["header_slots"]
        self.assertEqual(populated, populated_after, "populated header slots changed")
        moved = [slot for slot, m in transforms.items() if slot in transforms_after
                 and any(abs(a - b) > TOLERANCE for a, b in zip(m, transforms_after[slot]))]
        self.assertEqual(moved, [], "nodes behind these header slots moved")

    def test_display_lists_valid(self):
        """Exported display lists are drawable by the game (see display_list_problems)."""
        problems = self.trip.display_list_problems
        self.assertEqual(problems[:5], [], f"{len(problems)} display list problems")

    def test_splines_preserved(self):
        self.assertEqual(self.trip.before["splines"], self.trip.after["splines"], "spline points changed")

    def test_reexport_does_not_keep_growing(self):
        """Repeated export/import must settle rather than keep adding data (e.g. a wrapper node per export).

        A one-off size change on the first re-export is fine (vertex packing can differ); growing again
        on the next one means every export adds something.
        """
        trip = self.trip
        sizes = [sum(map(len, read_block(folder + "out_modelblock.bin", 2).data[self.model_id]))
                 for folder in (trip.first, trip.second, trip.third)]
        self.assertFalse(sizes[0] < sizes[1] < sizes[2], f"model grows on every export: {sizes} bytes")

    def test_reexport_is_stable(self):
        """After one round-trip the export has settled: exporting the re-import again gives the same size."""
        trip = self.trip
        sizes = [sum(map(len, read_block(folder + "out_modelblock.bin", 2).data[self.model_id]))
                 for folder in (trip.first, trip.second, trip.third)]
        self.assertEqual(sizes[1], sizes[2], f"export size still changing after a round-trip: {sizes} bytes")


class ImmediateResult(unittest.TextTestResult):
    """Prints each failure as it happens; a hard Blender crash would otherwise lose the end-of-run report."""

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.stream.writeln(f"\n--- FAIL {test.id()}\n{self._exc_info_to_string(err, test)}")
        self.stream.flush()

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        # known issues stay quiet in the summary, but the log should still say what is wrong
        message = self._exc_info_to_string(err, test).strip().splitlines()
        self.stream.writeln(f"\n--- KNOWN {test.id()}\n{chr(10).join(message[-8:])}")
        self.stream.flush()

    def addError(self, test, err):
        super().addError(test, err)
        self.stream.writeln(f"\n--- ERROR {test.id()}\n{self._exc_info_to_string(err, test)}")
        self.stream.flush()


def exportable_models():
    model_list = importlib.import_module(f"{PACKAGE}.swe1r.model_list").model_list
    return [m["index"] for m in model_list if m["extension"] != "MAlt"]


def known_issues():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_issues.json")) as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def build_suite(model_ids, source_dir):
    model_list = importlib.import_module(f"{PACKAGE}.swe1r.model_list").model_list
    names = {m["index"]: f'{m["extension"]}_{m["name"]}' for m in model_list}
    known = known_issues()
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for model_id in model_ids:
        label = "".join(c if c.isalnum() else "_" for c in names.get(model_id, "unknown"))
        attrs = {"model_id": model_id, "source_dir": source_dir}
        for test_name in known.get(str(model_id), {}):
            if test_name.startswith("test_"):
                attrs[test_name] = unittest.expectedFailure(getattr(RoundTripTest, test_name))
        case = type(f"Model{model_id:03d}_{label}", (RoundTripTest,), attrs)
        suite.addTests(loader.loadTestsFromTestCase(case))
    return suite


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="roundtrip.py")
    parser.add_argument("--full", action="store_true", help="every exportable model instead of the smoke set")
    parser.add_argument("--models", help="comma-separated model ids")
    parser.add_argument("--failfast", action="store_true")
    args = parser.parse_args(argv)

    source_dir = game_data_dir()
    if source_dir is None:
        print("SWE1R game data not found; set SWE1R_GAME_DATA to the game's data/lev01 folder")
        sys.exit(2)

    load_addon()
    if args.models:
        model_ids = [int(m) for m in args.models.split(",")]
    elif args.full:
        model_ids = exportable_models()
    else:
        model_ids = SMOKE_MODELS

    runner = unittest.TextTestRunner(verbosity=2, failfast=args.failfast, resultclass=ImmediateResult)
    result = runner.run(build_suite(model_ids, source_dir))
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
