import copy
import tempfile
from pathlib import Path
import unittest

from audit_shader_pair import audit, read_export


def shader(stage="ps", register=4):
    return {"stage": stage, "bindings": {"Scene": ["sampler", register]},
            "writes_depth": False, "declarations": ["dcl_2d s4"]}


def model():
    return {"xml_sha256": "fixture", "shaders": [shader("vs"), shader()],
            "passes": {"draw/0": {"vs": 0, "ps": 1, "state": [[10, 1]]}}}


class AuditTests(unittest.TestCase):
    def test_maps_by_role_after_slot_reordering(self):
        source, target = model(), model()
        target["shaders"].append(target["shaders"][1])
        target["shaders"][1] = shader(register=8)
        target["passes"]["draw/0"]["ps"] = 2
        row = audit(source, target, [1])["entries"][0]
        self.assertEqual(row["target_slots"], [2])
        self.assertTrue(row["candidates"][0]["source_bindings_preserved"])

    def test_detects_sampler_move_depth_and_state_changes(self):
        source, target = model(), model()
        target["shaders"][1] = shader(register=5)
        target["shaders"][1]["writes_depth"] = True
        target["passes"]["draw/0"]["state"] = []
        result = audit(source, target, [1])
        c = result["entries"][0]["candidates"][0]
        self.assertEqual(c["changed_bindings"]["Scene"]["target"], ["sampler", 5])
        self.assertTrue(c["target_writes_depth"])
        self.assertEqual(c["changed_pass_states"], ["draw/0"])
        self.assertFalse(result["rendering_validated"])

    def test_one_source_can_map_to_multiple_target_variants(self):
        source, target = model(), model()
        source["passes"]["shadow/0"] = copy.deepcopy(source["passes"]["draw/0"])
        target["shaders"].append(shader())
        target["passes"]["shadow/0"] = {"vs": 0, "ps": 2, "state": []}
        row = audit(source, target, [1])["entries"][0]
        self.assertEqual(row["target_slots"], [1, 2])
        self.assertFalse(row["mapping_unambiguous"])

    def test_missing_role_is_not_a_mapping(self):
        target = model()
        target["passes"] = {}
        row = audit(model(), target, [1])["entries"][0]
        self.assertEqual(row["missing_roles"], ["draw/0"])
        self.assertFalse(row["mapping_unambiguous"])

    def test_invalid_slot_rejected(self):
        with self.assertRaises(ValueError):
            audit(model(), model(), [-1])

    def test_rage_shader_index_conventions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "vs.asm").write_text("vs_3_0\nmov o0, v0\n")
            (root / "ps.asm").write_text("ps_3_0\nmov oDepth, c0\n")
            xml = root / "fixture.fxc.xml"
            xml.write_text('''<?xml version="1.0" encoding="UTF - 8"?>
<Game>GTAIV</Game><Effect><Shaders>
<VertexShaders><Item><File>vs.asm</File><Variables /></Item></VertexShaders>
<PixelShaders><Item><File>ps.asm</File><Variables /></Item></PixelShaders>
</Shaders><Techniques><Item><Name>draw</Name><Passes><Item>
<VertexShader>0</VertexShader><PixelShader>1</PixelShader><Params />
</Item></Passes></Item></Techniques></Effect>''')
            result = read_export(xml)
            self.assertEqual(result["passes"]["draw/0"]["ps"], 1)
            self.assertTrue(result["shaders"][1]["writes_depth"])
            xml.write_text(xml.read_text().replace("ps.asm", "../outside.asm"))
            with self.assertRaises(ValueError):
                read_export(xml)


if __name__ == "__main__":
    unittest.main()
