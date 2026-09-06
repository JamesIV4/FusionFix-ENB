import math
import struct
import unittest

from read_postfx_capture import decode, summarize


def fixture(fmt, bpp, payload):
    return struct.pack('<8I', 0x31584650, 1, 1, fmt, bpp, 1, 1, 0) + payload


class CaptureTests(unittest.TestCase):
    def test_bgra_order_and_unorm(self):
        _, pixels = decode(fixture(21, 4, bytes((51, 102, 204, 255))))
        self.assertEqual(pixels, [(0.8, 0.4, 0.2, 1.0)])

    def test_half_hdr_not_clamped_or_gamma_changed(self):
        _, pixels = decode(fixture(113, 8, struct.pack('<4e', -0.5, 0.125, 20, 1)))
        self.assertEqual(pixels, [(-0.5, 0.125, 20, 1)])

    def test_adaptation_scalar(self):
        result = summarize(fixture(114, 4, struct.pack('<f', 0.25)))
        self.assertEqual(result['channels'][0]['mean'], 0.25)

    def test_nonfinite_reported(self):
        result = summarize(fixture(112, 4, struct.pack('<2e', math.inf, math.nan)))
        self.assertEqual(result['channels'][0]['nonfinite'], 1)
        self.assertIsNone(result['channels'][1]['median'])

    def test_malformed(self):
        valid = fixture(111, 2, struct.pack('<e', 1))
        for data in (valid[:20], valid[:-1], valid + b'x', fixture(111, 4, b'1234'),
                     fixture(999, 2, b'12')):
            with self.assertRaises(ValueError):
                decode(data)


if __name__ == '__main__':
    unittest.main()
