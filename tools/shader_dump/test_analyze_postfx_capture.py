import math
import tempfile
import unittest

from analyze_postfx_capture import analyze, constants, report
from prepare_postfx_bridge import legacy_depth


def texture(pixels, width=None):
    width = width or len(pixels)
    return {'width': width, 'height': 1, 'columns': len(pixels), 'rows': 1}, pixels


class AnalysisTests(unittest.TestCase):
    def test_constant_parser_rejects_duplicates_and_keeps_nonfinite_visible(self):
        self.assertEqual(constants('boundary=test\nc77 0.1 1000 0 0\ns1 srgb=0')['c77'], [.1, 1000, 0, 0])
        self.assertTrue(math.isnan(constants('c82 1 2 nan 4')['c82'][2]))
        for text in ('c77 1 2 3', 'c77 1 2 3 4\nc77 1 2 3 4'):
            with self.assertRaises(ValueError): constants(text)

    def test_depth_conversion_uses_aligned_raw_texels_and_all_provider_components(self):
        values = {'c77': [.1, 1000, 0, 0], 'c209': [10, 1 / math.log2(10000), 10000, .1]}
        samples = [0., .2, .5, .9, 1.]
        textures = {'s1': texture([(v,) for v in samples]),
                    'converted_depth': texture([(legacy_depth(v, .1, 1000),) for v in samples])}
        result = analyze(values, textures)
        self.assertEqual(result['depth_check']['outside_tolerance'], 0)
        self.assertEqual(result['findings'], [])
        textures['converted_depth'][1][2] = (.5,)
        values['c209'][0] = 1
        result = analyze(values, textures)
        self.assertEqual({f['code'] for f in result['findings']},
                         {'projection_constants_disagree', 'depth_conversion_mismatch'})

    def test_unaligned_depth_grids_are_not_compared(self):
        values = {'c77': [.1, 1000, 0, 0], 'c209': [10, 1 / math.log2(10000), 10000, .1]}
        result = analyze(values, {'s1': texture([(.5,)], 100), 'converted_depth': texture([(.5,)], 200)})
        self.assertEqual(result['depth_check']['status'], 'different_sample_grids')

    def test_hdr_ratio_reports_raw_intermediate_without_clamping(self):
        result = analyze({}, {'s2': texture([(2., 4., 20., 1.)]), 's5': texture([(.1,)])})
        ratio = result['hdr_adaptation']['hdr_divided_by_adaptation_times_0_06']
        self.assertAlmostEqual(ratio[0]['mean'], 1.2)
        self.assertAlmostEqual(ratio[2]['mean'], 12.)

    def test_bad_or_spatial_adaptation_does_not_produce_invented_ratios(self):
        for red, status in (([(0.,)], 'invalid_adaptation_samples'),
                            ([(math.nan,)], 'invalid_adaptation_samples'),
                            ([(.1,), (.2,)], 'spatially_varying_adaptation')):
            result = analyze({}, {'s2': texture([(1., 2., 3.)]), 's5': texture(red)})
            self.assertEqual(result['hdr_adaptation']['status'], status)
            self.assertNotIn('hdr_divided_by_adaptation_times_0_06', result['hdr_adaptation'])

    def test_missing_captures_and_nonfinite_output_cannot_look_successful(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'No numbered capture'):
                report(tmp)
        result = analyze({}, {'composite': texture([(0., math.nan, 0.)])})
        self.assertEqual(result['findings'], [{'code': 'nonfinite_composite_samples'}])
        result = analyze({}, {'composite': texture([(0., 0., 0.)])})
        self.assertEqual(result['findings'], [{'code': 'all_sampled_composite_channels_zero'}])


if __name__ == '__main__':
    unittest.main()
