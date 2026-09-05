import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

from enb163_hash import filename, hashed_length, shader_hash
from make_shader_aliases import stage


def words(*values):
    return struct.pack("<" + "I" * len(values), *values)


def bitwise_crc(data):
    value = 0xFFFFFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xEDB88320 if value & 1 else 0)
    return value


class HashTests(unittest.TestCase):
    def test_reflected_crc_without_final_xor(self):
        self.assertEqual(bitwise_crc(b"123456789"), 0x340BC6D9)
        for model in (0xFFFF0300, 0xFFFE0300):
            data = words(model, 0x0000FFFF)
            self.assertEqual(shader_hash(data), bitwise_crc(data[:4]))

    def test_comment_payload_end_stops_enb_scan(self):
        data = words(0xFFFF0300, 0x0002FFFE, 0x0000FFFF, 123, 0x0000FFFF)
        self.assertEqual(hashed_length(data), 8)
        self.assertEqual(shader_hash(data), bitwise_crc(data[:8]))

    def test_comments_are_hashed(self):
        a = words(0xFFFF0300, 0x0001FFFE, 123, 0x0000FFFF)
        b = words(0xFFFF0300, 0x0001FFFE, 456, 0x0000FFFF)
        self.assertNotEqual(shader_hash(a), shader_hash(b))

    def test_rejects_missing_end_and_partial_words(self):
        for data in (b"", b"\xff", words(0xFFFF0300, 0)):
            with self.assertRaises(ValueError):
                shader_hash(data)

    def test_stage_prefix(self):
        data = words(0xFFFF0300, 0x0000FFFF)
        self.assertTrue(filename(data, "ps").startswith("psh"))
        with self.assertRaises(ValueError):
            filename(data, "cs")


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.preset = self.root / "source", self.root / "preset"
        self.source.mkdir()
        self.preset.mkdir()
        self.blob = words(0xFFFF0300, 0x0002FFFE, 0x0000FFFF, 123, 0x0000FFFF)
        (self.source / "test.fxc").write_bytes(self.blob)
        self.replacement = b"ps_3_0\nmov oC0, c0\n"
        (self.preset / "psh01234567.txt").write_bytes(self.replacement)
        self.contract = {"mapping_evidence": "synthetic", "entries": [{
            "group": "terrain", "container": "test.fxc", "index": 0, "stage": "ps",
            "shader_sha256": hashlib.sha256(self.blob).hexdigest(),
            "preset_file": "psh01234567.txt",
            "replacement_sha256": hashlib.sha256(self.replacement).hexdigest()}]}

    def run_stage(self, output=None):
        return stage(self.source, self.preset, self.contract, ["terrain"], output or self.root / "out")

    def test_alias_is_exact_copy_and_records_duplicate_slots(self):
        (self.source / "duplicate.fxc").write_bytes(self.blob)
        report = self.run_stage()
        alias = filename(self.blob, "ps")
        self.assertEqual((self.root / "out/shaderinput" / alias).read_bytes(), self.replacement)
        self.assertEqual(len(report["affected_slots"][alias]), 2)
        self.assertFalse(report["rendering_validated"])

    def test_rejects_modified_shader_before_writing(self):
        (self.source / "test.fxc").write_bytes(words(0xFFFF0300, 0x0000FFFF))
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            self.run_stage()
        self.assertFalse((self.root / "out").exists())

    def test_probe_changes_only_explicit_diagnostic_output(self):
        report = stage(self.source, self.preset, self.contract, ["terrain"], self.root / "probe", probe=True)
        text = (self.root / "probe/shaderinput" / filename(self.blob, "ps")).read_text()
        self.assertIn("def c223, 1, 0, 1, 1", text)
        self.assertIn("mov oC0, c0", text)
        self.assertTrue(text.endswith("    mov oC0.xyz, c223\n"))
        self.assertEqual(report["probe"], "terrain_diffuse_magenta")
        self.assertEqual((self.preset / "psh01234567.txt").read_bytes(), self.replacement)

    def test_rejects_changed_preset(self):
        (self.preset / "psh01234567.txt").write_bytes(b"different preset")
        with self.assertRaisesRegex(ValueError, "Preset file differs"):
            self.run_stage()

    def test_rejects_crc_collision_with_different_bytecode(self):
        (self.source / "collision.fxc").write_bytes(
            words(0xFFFF0300, 0x0002FFFE, 0x0000FFFF, 456, 0x0000FFFF))
        with self.assertRaisesRegex(ValueError, "hash collision"):
            self.run_stage()
        self.assertFalse((self.root / "out").exists())

    def test_rejects_game_output_and_overwrite(self):
        game = self.root / "game"
        game.mkdir()
        (game / "GTAIV.exe").touch()
        with self.assertRaisesRegex(ValueError, "installed game"):
            self.run_stage(game / "stage")
        self.run_stage()
        with self.assertRaisesRegex(ValueError, "new directory"):
            self.run_stage()


if __name__ == "__main__":
    unittest.main()
