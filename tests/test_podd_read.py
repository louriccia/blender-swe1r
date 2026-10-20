import os
import struct
import unittest

from addon_loader import load_modelblock

modelblock = load_modelblock()
from swe1r_addon.swe1r.block import Block
from swe1r_addon.utils import Podd_MAlt

NODE = ">3I2H3I"
HEADER_SLOTS = 75


class FakeBlock:
    def __init__(self, models):
        self.models = models
        self.textureblock = None

    def fetch(self, index):
        return [None, self.models[index]]


def build_model(tag, slots, alt_entries, nodes):
    """nodes: list of (type, child_names, extra_bytes) keyed by name, laid out after the header.
    slots/alt_entries reference node names, or ('child', name, index) for the address of a child pointer."""
    header_size = 4 + HEADER_SLOTS * 4 + 4 + 4 + (len(alt_entries) + 1) * 4 + 4
    layout = {}
    cursor = header_size
    for name, (node_type, children, extra) in nodes.items():
        layout[name] = cursor
        cursor += struct.calcsize(NODE) + extra
        layout[name, "children"] = cursor
        cursor += 4 * len(children)
    buffer = bytearray(cursor)

    def resolve(ref):
        if isinstance(ref, tuple):
            _, name, index = ref
            return layout[name, "children"] + 4 * index
        return layout[ref]

    buffer[0:4] = tag.encode()
    for index, ref in slots.items():
        struct.pack_into(">I", buffer, 4 + index * 4, resolve(ref))
    cursor = 4 + HEADER_SLOTS * 4
    struct.pack_into(">i", buffer, cursor, -1)
    buffer[cursor + 4:cursor + 8] = b"AltN"
    cursor += 8
    for ref in alt_entries:
        struct.pack_into(">I", buffer, cursor, resolve(ref))
        cursor += 4
    cursor += 4
    buffer[cursor:cursor + 4] = b"HEnd"

    for name, (node_type, children, extra) in nodes.items():
        struct.pack_into(NODE, buffer, layout[name], node_type, 0xFFFFFFFF, 0xFFFFFFFD, 0, 0, 0, len(children), layout[name, "children"])
        for i, child in enumerate(children):
            if child is not None:
                struct.pack_into(">I", buffer, layout[name, "children"] + 4 * i, layout[child])
    return bytes(buffer), layout


def walk(node, seen=None):
    seen = [] if seen is None else seen
    if not isinstance(node, modelblock.Node):
        return seen
    seen.append(node)
    for child in node.children:
        walk(child, seen)
    return seen


class SyntheticPoddTest(unittest.TestCase):
    def setUp(self):
        # Podd: root selector with a real child and an empty child pointer listed in AltN
        self.podd, self.podd_layout = build_model("Podd", {0: "root", 5: "part"}, [("child", "root", 1)], {
            "root": (20581, ["part", None], 4),
            "part": (20580, [], 0),
        })
        # MAlt: its AltN node sits at the same offset as the Podd's "part" node, and fills header slot 46
        self.malt, self.malt_layout = build_model("MAlt", {46: "detail"}, ["alt_root"], {
            "padding": (20580, [], 12),
            "alt_root": (20580, ["detail"], 4),
            "detail": (20580, [], 0),
        })
        self.assertEqual(self.podd_layout["part"], self.malt_layout["alt_root"])

    def read(self):
        model = modelblock.Model(2)
        model.modelblock = FakeBlock({2: self.podd, Podd_MAlt["2"]: self.malt})
        return model.read(self.podd)

    def test_alt_node_is_grafted_into_empty_child(self):
        model = self.read()
        self.assertEqual(len(model.nodes), 1)
        root = model.nodes[0]
        part, alt_root = root.children
        self.assertIs(part.model, model)
        self.assertIs(alt_root.model, model.alt_model)
        self.assertEqual(alt_root.id, self.malt_layout["alt_root"])
        self.assertEqual(alt_root.AltN, [0])
        detail = alt_root.children[0]
        self.assertEqual(detail.model.header.offsets[46], detail.id)

    def test_nodes_are_read_once(self):
        nodes = walk(self.read().nodes[0])
        self.assertEqual(len(nodes), 4)
        self.assertEqual(len({(id(n.model), n.id) for n in nodes}), 4)

    def test_object_keys_do_not_collide(self):
        model = self.read()
        part, alt_root = model.nodes[0].children
        self.assertEqual(part.id, alt_root.id)
        self.assertNotEqual(model.obj_key(part.id), alt_root.model.obj_key(alt_root.id))

    def test_standalone_malt_reads_every_alt_node(self):
        model = modelblock.Model(Podd_MAlt["2"])
        model.read(self.malt)
        self.assertEqual([n.id for n in model.nodes], [self.malt_layout["alt_root"]])


MODELBLOCK = os.environ.get("SWE1R_MODELBLOCK")


@unittest.skipUnless(MODELBLOCK, "set SWE1R_MODELBLOCK to the game's out_modelblock.bin to test against real pods")
class GamePoddTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.block = Block(MODELBLOCK, 2).read()

    def test_every_pod_merges_its_malt(self):
        for podd_id, malt_id in Podd_MAlt.items():
            with self.subTest(podd=podd_id):
                model = modelblock.Model(int(podd_id))
                model.modelblock = self.block
                model.read(self.block.fetch(int(podd_id))[1])
                self.assertEqual(len(model.nodes), 1)
                nodes = walk(model.nodes[0])
                keys = [(n.model.id, n.id) for n in nodes]
                self.assertEqual(len(keys), len(set(keys)), "a node was read twice")

                alt = model.alt_model
                read_alt = {n.id for n in nodes if n.model is alt}
                for slot, offset in enumerate(alt.header.offsets):
                    if offset:
                        self.assertIn(offset, read_alt, f"MAlt slot {slot} missing")
                for offset in alt.AltN:
                    self.assertIn(offset, read_alt)

                podd_slots = {n.id for n in nodes if n.model is model}
                for slot, offset in enumerate(model.header.offsets):
                    if offset:
                        self.assertIn(offset, podd_slots, f"Podd slot {slot} missing")

                # materials of the two models never share an id
                self.assertFalse({m.id for m in model.materials.values()} & {m.id for m in alt.materials.values()})


if __name__ == "__main__":
    unittest.main()
