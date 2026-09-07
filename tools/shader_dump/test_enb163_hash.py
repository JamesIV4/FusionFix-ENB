import struct
import unittest

from enb163_hash import filename, hashed_length, shader_hash


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


if __name__ == "__main__":
    unittest.main()
