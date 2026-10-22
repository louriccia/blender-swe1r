"""The Blend Mode presets: each writes a setup it is detected as, no setup belongs to two presets,
and (with SWE1R_MODELBLOCK set to the game's out_modelblock.bin) the presets cover the stock
materials they were built from."""
import os
import unittest

from addon_loader import load_modelblock

modelblock = load_modelblock()


class BlendPresetTest(unittest.TestCase):
    def test_preset_detects_as_itself(self):
        for name, preset in modelblock.BLEND_PRESETS.items():
            self.assertEqual(modelblock.detect_blend_preset(preset['write']), name)

    def test_setups_belong_to_one_preset(self):
        seen = {}
        for name, preset in modelblock.BLEND_PRESETS.items():
            for words in preset['accept']:
                self.assertNotIn(words, seen, f"{name} and {seen.get(words)} both accept {words}")
                seen[words] = name

    def test_only_renderer_blenders(self):
        # n64_shader.cpp set_render_mode: the cycle-2 blender must be opaque, alpha blend or
        # coverage AA (IN*A + MEM*A_MEM), and coverage AA needs ZMODE_OPA, or the game aborts
        for name, preset in modelblock.BLEND_PRESETS.items():
            mode = preset['write'][0] | preset['write'][1]
            p, a, m, b = (mode >> 28) & 3, (mode >> 24) & 3, (mode >> 20) & 3, (mode >> 16) & 3
            blend = (p, a, m, b)
            self.assertIn(blend, [(0, 0, 1, 0), (0, 0, 1, 1), (0, 3, 0, 2)], name)
            if blend == (0, 0, 1, 1):
                self.assertEqual(mode & modelblock.RM_ZMODE_MASK, 0, name)

    def test_unknown_is_custom(self):
        self.assertEqual(modelblock.detect_blend_preset((1, 2, 3, 4, 5, 6)), 'CUSTOM')

    @unittest.skipUnless(os.environ.get('SWE1R_MODELBLOCK'), "set SWE1R_MODELBLOCK to the game's out_modelblock.bin")
    def test_stock_coverage(self):
        from swe1r_addon.swe1r.block import Block
        from swe1r_addon.swe1r.model_list import model_list
        block = Block(os.environ['SWE1R_MODELBLOCK'], 2).read()
        matched = total = 0
        for entry in model_list:
            model = modelblock.Model(entry['index'])
            model.modelblock = block
            model.read(block.fetch(entry['index'])[1])
            for material in model.materials.values():
                s = material.shader
                words = (s.render_mode_1, s.render_mode_2, s.color_combine_mode_cycle1, s.alpha_combine_mode_cycle1,
                         s.color_combine_mode_cycle2, s.alpha_combine_mode_cycle2)
                total += 1
                matched += modelblock.detect_blend_preset(words) != 'CUSTOM'
        self.assertGreater(total, 8000)
        self.assertGreaterEqual(matched / total, 0.97, f"{matched} of {total} stock materials match a preset")


if __name__ == "__main__":
    unittest.main()
