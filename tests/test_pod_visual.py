"""The pod part table (swe1r/pod_visual.py) read from the game's exe. Runs without Blender."""
import importlib.util
import os
import unittest

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    spec = importlib.util.spec_from_file_location("pod_visual", os.path.join(ADDON_DIR, "swe1r", "pod_visual.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PodVisualTest(unittest.TestCase):
    def test_a_row_per_racer(self):
        m = load()
        self.assertEqual(len(m.POD_VISUAL), 23)
        self.assertEqual(sorted(row['racer'] for row in m.POD_VISUAL.values()), list(range(23)))

    def test_anakin_anchors(self):
        # Anakin (Podd 2): right engine at (2.32, 5.22, -0.44) game units, 1.6 game units per Blender unit
        a = load().pod_anchor_positions(2)
        self.assertAlmostEqual(a['engine_r'][0], 2.32 / 1.6)
        self.assertAlmostEqual(a['engine_l'][0], -2.32 / 1.6)
        self.assertAlmostEqual(a['exhaust_r'][1], (5.22 - 3.5) / 1.6)

    def test_binder_and_cable_anchors(self):
        # Anakin: binder 0.55 inward from each engine; cables from cockpit + (+-0.98, 2.18, 0) to
        # engine + (0, -0.98, 0.76) (PoddAnimateVariousThings, swrRace_BuildStretchedQuad)
        a = load().pod_anchor_positions(2)
        self.assertAlmostEqual(a['binder_r'][0] * 1.6, 2.32 - 0.55)
        self.assertAlmostEqual(a['binder_l'][0] * 1.6, -(2.32 - 0.55))
        self.assertAlmostEqual(a['cable_cockpit_l'][0] * 1.6, -0.98)
        self.assertAlmostEqual(a['cable_cockpit_r'][1] * 1.6, -4.44 + 2.18)
        self.assertAlmostEqual(a['cable_engine_r'][2] * 1.6, -0.44 + 0.76)

    def test_unknown_model(self):
        self.assertIsNone(load().pod_anchor_positions(1))


class PodPartsTest(unittest.TestCase):
    def test_stock_parts(self):
        spec = importlib.util.spec_from_file_location("pod_parts", os.path.join(ADDON_DIR, "swe1r", "pod_parts.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        for part in (m.STOCK_GLOW, m.STOCK_CABLE):
            corners = 3 * len(part['faces'])
            self.assertEqual(len(part['uvs']), corners)
            self.assertEqual(len(part['colors']), corners)
            self.assertTrue(all(0 <= i < len(part['verts']) for face in part['faces'] for i in face))
        # stock aabbs (Anakin, Podd 2): glow x -100..100, z 0..100; cable x 0..10, y -100..0
        xs = [v[0] for v in m.STOCK_GLOW['verts']]
        self.assertEqual((min(xs), max(xs)), (-100, 100))
        ys = [v[1] for v in m.STOCK_CABLE['verts']]
        self.assertEqual((min(ys), max(ys)), (-100, 0))


if __name__ == "__main__":
    unittest.main()
