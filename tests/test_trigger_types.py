"""The trigger type table covers every type the game's enum names. Runs without Blender."""
import importlib.util
import os
import re
import unittest

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    spec = importlib.util.spec_from_file_location("trigger_types", os.path.join(ADDON_DIR, "swe1r", "trigger_types.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# swrModel_TriggerType in SW_RACER_RE src/types_enums.h, plus 0 (no handler)
DECOMP_TYPES = {0, 100, 101, 102, 103, 104, 105, 106, 107, 108, 201, 202, 203, 208, 211, 212, 213, 301, 304,
                306, 307, 308, 310, 312, 314, 501, 503, 900}


class TriggerTypesTest(unittest.TestCase):
    def test_every_game_type_listed(self):
        self.assertEqual(set(load().TRIGGER_TYPES), DECOMP_TYPES)

    def test_effect_slots_known(self):
        m = load()
        for type_id, entry in m.TRIGGER_TYPES.items():
            if entry[3] is not None:
                self.assertIn(entry[3], m.EFFECT_SLOT_PLANETS, type_id)

    def test_warnings(self):
        m = load()
        self.assertIn("Crashes off Baroonda", m.type_warnings(501))
        self.assertIn("Custom-folder tracks count as Ando Prime", m.type_warnings(501))
        self.assertTrue(any(w.startswith("Keep out of bounds") for w in m.type_warnings(900)))
        self.assertEqual(m.type_warnings(12345), ["Not a known trigger type"])


if __name__ == "__main__":
    unittest.main()
