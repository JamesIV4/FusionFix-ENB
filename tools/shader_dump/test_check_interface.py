from pathlib import Path
import tempfile
import unittest

from check_interface import parse_asm


class InterfaceParserTests(unittest.TestCase):
    def test_abs_source_modifier_keeps_constant_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            shader = Path(temp) / "shader.asm"
            shader.write_text(
                "ps_3_0\n"
                "def c209, 1, 2, 3, 4\n"
                "mul r0, c221_abs.w, c209_abs.z\n"
                "mov oC0, r0\n",
                encoding="utf-8")
            _, constants, _, _ = parse_asm(shader)
            self.assertEqual(constants, {221})


if __name__ == "__main__":
    unittest.main()
