import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from report_runtime_aliases import report


class RuntimeAliasReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "shaders").mkdir()
        self.dump = b"synthetic shader"
        self.contract = {"entries": [{
            "preset_file": "pshOLD.txt", "ce_alias": "pshNEW.txt", "stage": "ps",
            "container": "terrain.fxc", "index": 5, "group": "terrain",
            "assembled": {"bytes": len(self.dump),
                          "sha256": hashlib.sha256(self.dump).hexdigest(),
                          "crc32": "12345678", "crc32_stripped": "12345678"},
        }]}
        (self.root / "shaders.csv").write_text(
            "stage,crc32,crc32_stripped,tokens,bytes,fusion_signature,frame\n"
            "ps,12345678,12345678,4,16,0,0\n", encoding="utf-8")
        (self.root / "d3d9_trace.log").write_text("trace installed\n", encoding="utf-8")

    def test_exact_created_and_bound(self):
        (self.root / "shaders/ps_12345678.cso").write_bytes(self.dump)
        (self.root / "shader_first_binds.csv").write_text(
            "stage,crc32,crc32_stripped,first_frame\nps,12345678,12345678,42\n",
            encoding="utf-8")
        result = report(self.root, self.contract)
        self.assertEqual(result["aliases"][0]["status"], "bound_exact")
        self.assertEqual(result["aliases"][0]["first_bound_frame"], 42)

    def test_created_without_bind_data(self):
        result = report(self.root, self.contract)
        self.assertEqual(result["aliases"][0]["status"], "created_hash_match")
        self.assertFalse(result["first_bind_data_available"])

    def test_dump_mismatch_is_visible(self):
        (self.root / "shaders/ps_12345678.cso").write_bytes(b"wrong")
        result = report(self.root, self.contract)
        self.assertEqual(result["aliases"][0]["status"], "created_dump_mismatch")

    def test_not_created(self):
        (self.root / "shaders.csv").write_text(
            "stage,crc32,crc32_stripped,tokens,bytes,fusion_signature,frame\n",
            encoding="utf-8")
        result = report(self.root, self.contract)
        self.assertEqual(result["aliases"][0]["status"], "not_created")

    def test_session_distinguishes_not_installed(self):
        (self.root / "trace-session.json").write_text(
            json.dumps({"aliases": [{"file": "pshSOMETHINGELSE.txt"}]}), encoding="utf-8")
        result = report(self.root, self.contract)
        self.assertEqual(result["aliases"][0]["status"], "not_installed")
        self.assertFalse(result["aliases"][0]["installed"])

    def test_rejects_bad_csv(self):
        (self.root / "shaders.csv").write_text("stage,crc32\nps,12345678\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "lacks"):
            report(self.root, self.contract)


if __name__ == "__main__":
    unittest.main()
