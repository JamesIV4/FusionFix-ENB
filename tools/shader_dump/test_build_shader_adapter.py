import struct
import unittest

from build_shader_adapter import edit_def, instructions, patch_literal


def blob(comment=False, tail=b""):
    head = struct.pack("<I", 0xFFFF0300)
    if comment:
        # Includes a fake instruction marker: the walker must skip comments.
        head += struct.pack("<3I", 0x0002FFFE, 0x05000051, 0xA00F0000)
    return head + struct.pack("<2I4fI", 0x05000051, 0xA00F0000,
                              0.5, 0, 1, 0.25, 0xFFFF) + tail


class AdapterTests(unittest.TestCase):
    def test_patch_changes_only_literal_and_preserves_comments(self):
        for comments in (False, True):
            source = blob(comments)
            adapted, offset = patch_literal(source, 0, 3, 0.25, 0)
            self.assertEqual(adapted[:offset], source[:offset])
            self.assertEqual(adapted[offset + 4:], source[offset + 4:])
            self.assertEqual(struct.unpack_from("<f", adapted, offset)[0], 0)

    def test_changed_literal_and_duplicate_defs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "literal"):
            patch_literal(blob(), 0, 3, 0.5, 0)
        duplicate = blob()[:-4] + blob()[4:]
        with self.assertRaisesRegex(ValueError, "one matching DEF"):
            patch_literal(duplicate, 0, 3, 0.25, 0)

    def test_incomplete_or_trailing_bytecode_is_rejected(self):
        for data in (blob()[:-4], blob()[:-9], blob(tail=b"junk"), b"bad"):
            with self.assertRaises(ValueError):
                patch_literal(data, 0, 3, 0.25, 0)

    def test_text_delta_does_not_touch_uses_or_other_constants(self):
        source = "// def c0, bogus\nps_3_0\ndef c0, 0.5, 0, 1, 0.25\ndef c10, 0.25, 0, 0, 0\nmov oC0, c0.w\n"
        expected = source.replace("1, 0.25", "1, 0")
        self.assertEqual(instructions(edit_def(source, 0, 3, 0.25, 0)), instructions(expected))

    def test_text_delta_rejects_missing_ambiguous_or_changed_source(self):
        definition = "def c0, 0.5, 0, 1, 0.25\n"
        for source in ("ps_3_0", definition * 2, definition.replace("0.25", "0.5")):
            with self.assertRaises(ValueError):
                edit_def(source, 0, 3, 0.25, 0)


if __name__ == "__main__":
    unittest.main()
