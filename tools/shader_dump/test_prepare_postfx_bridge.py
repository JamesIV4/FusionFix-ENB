import math
import unittest

from prepare_postfx_bridge import fnv64, legacy_depth


class DepthBridgeTests(unittest.TestCase):
    def test_clip_endpoints(self):
        for near, far in ((0.1, 1000), (0.5, 5000), (1, 2)):
            self.assertAlmostEqual(legacy_depth(0, near, far), 0)
            self.assertAlmostEqual(legacy_depth(1, near, far), 1)

    def test_stock_shader_reconstructs_modern_view_depth(self):
        for near, far in ((0.1, 1000), (0.5, 5000), (1, 2)):
            for distance in (near, math.sqrt(near * far), far * 0.1, far):
                if distance < near:
                    continue
                # Same log encoding as FusionFix's vertex/pixel programs.
                modern = math.log2(distance / near) / math.log2(far / near)
                converted = legacy_depth(modern, near, far)
                # Same projection inversion as stock rage_postfx#13.
                reconstructed = (-far * near / (far - near)) / (converted - far / (far - near))
                self.assertAlmostEqual(reconstructed / distance, 1, places=9)

    def test_monotonic_and_clamped(self):
        values = [legacy_depth(i / 100, 0.1, 1000) for i in range(-10, 111)]
        self.assertEqual(values, sorted(values))
        self.assertEqual(values[0], 0)
        self.assertEqual(values[-1], 1)

    def test_invalid_projection_rejected(self):
        for near, far in ((0, 100), (10, 1), (1, 1), (-1, 5)):
            with self.assertRaises(ValueError):
                legacy_depth(0.5, near, far)

    def test_fingerprint_reference_vector(self):
        self.assertEqual(fnv64(b"hello"), 0xA430D84680AABD0B)


if __name__ == "__main__":
    unittest.main()
