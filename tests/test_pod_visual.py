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

    def test_unknown_model(self):
        self.assertIsNone(load().pod_anchor_positions(1))


if __name__ == "__main__":
    unittest.main()
