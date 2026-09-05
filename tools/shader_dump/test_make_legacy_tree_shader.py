import hashlib
from pathlib import Path
import tempfile
import unittest

from make_legacy_tree_shader import DEFAULT_XML, prepare


class LegacyTreeShaderTests(unittest.TestCase):
    def test_prepares_stock_depth_sources_without_touching_authored_input(self):
        before = hashlib.sha256(DEFAULT_XML.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            copied_xml, modified = prepare(DEFAULT_XML, Path(temp) / "prepared")
            self.assertTrue(copied_xml.is_file())
            self.assertEqual(len(modified), 5)
            for path in copied_xml.parent.joinpath("gta_trees_extended").glob("*PS*.asm"):
                code = "\n".join(line.split("//", 1)[0] for line in path.read_text().splitlines())
                self.assertNotIn("oDepth", code)
                self.assertNotIn("c209", code)
        self.assertEqual(hashlib.sha256(DEFAULT_XML.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
