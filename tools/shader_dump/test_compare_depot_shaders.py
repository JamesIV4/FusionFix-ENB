from pathlib import Path
import struct
import tempfile
import unittest

from compare_depot_shaders import compare


def program(comment, constant):
    # ps_3_0, a one-DWORD comment, def c0, four immediates, END.
    return struct.pack("<10I", 0xFFFF0300, 0x0001FFFE, comment,
                       0x05000051, 0xA00F0000, constant, 0, 0, 0, 0xFFFF)


class DepotComparisonTests(unittest.TestCase):
    def test_raw_comment_and_program_differences_are_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / "old", Path(temp) / "ce"
            for root in (a, b):
                (root / "common/shaders/win32_30").mkdir(parents=True)
            cases = [("equal.fxc", program(1, 0), program(1, 0)),
                     ("comment.fxc", program(1, 0), program(2, 0)),
                     ("code.fxc", program(1, 0), program(1, 1))]
            for name, left, right in cases:
                (a / "common/shaders/win32_30" / name).write_bytes(left)
                (b / "common/shaders/win32_30" / name).write_bytes(right)
            r = compare(a, b)
            counts = r["variants"]["win32_30"]
            self.assertEqual(counts["raw_equal_containers"], 1)
            self.assertEqual(counts["same_slot_raw_equal"], 1)
            self.assertEqual(counts["same_slot_comment_only"], 1)
            self.assertEqual(counts["same_slot_program_changed"], 1)
            self.assertFalse(r["runtime_validated"])
            for name, left, right in cases:
                self.assertEqual((a / "common/shaders/win32_30" / name).read_bytes(), left)
                self.assertEqual((b / "common/shaders/win32_30" / name).read_bytes(), right)

    def test_rejects_missing_input(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                compare(Path(temp) / "absent", Path(temp))


if __name__ == "__main__":
    unittest.main()
