import copy
import json
import math
from pathlib import Path
import unittest

from build_preset_adapters import RECIPES, apply_edits
from build_shader_adapter import instructions
from shader_arithmetic import Machine, f32, saturate

FIXTURES = Path(__file__).parent / 'fixtures/remaining_translations'
CONTRACT = json.loads(RECIPES.read_text(encoding='utf-8'))
ENTRIES = {e['preset_file']: e for e in CONTRACT['entries']}
VOLUME_NAMES = {7: 'vsh54F25463.txt', 8: 'vshC35A5E05.txt'}


def programs(slot):
    source = (FIXTURES / f'modern_volume{slot}.vs').read_text(encoding='utf-8')
    preset = (FIXTURES / f'preset_volume{slot}.vs').read_text(encoding='utf-8')
    target = ENTRIES[VOLUME_NAMES[slot]]['targets'][0]
    return source, preset, apply_edits(source, target['edits'])


def volume_inputs(slot, kind, vertex, smooth=0, fog=0):
    data = {'v0': [*vertex, 1.], 'c236': [1., fog, smooth, 0.], 'c235': [.08, .01, 1.3, .2]}
    for start in (8, 12):
        for i in range(4):
            data[f'c{start+i}'] = [float(i == j) for j in range(4)]
    if slot == 8:
        for i in range(4):
            data[f'c{208+i}'] = [float(i == j) for j in range(4)]
        data.update(c212=[0., 0., 0., -1.], c213=[0., 0., .1, 0.], c214=[.1, .2, 0., .7])
    offset = 0 if slot == 7 else 7
    values = {208: [kind, 0, 0, 0], 209: [3, 4, 5, 0], 210: [0, 0, 1, 0],
              211: [1, 0, 0, 0], 212: [8, 0, 0, 0], 213: [.9, 0, 0, 0],
              214: [.4, 0, 0, 0], 215: [1.1, 0, 0, 0],
              216: [.7, .5, .3, 1.2], 217: [.8, 0, 0, 0]}
    data.update({f'c{k+offset}': v for k, v in values.items()})
    return data


def occlusion(sampler, coordinate, lod):
    if sampler != 's0' or lod is None:
        raise AssertionError('Unexpected volume sampler or implicit LOD')
    x, y = coordinate[:2]
    return [.6 + .1*x + .02*lod, .3 + .07*y, 0., 1.]


class ArithmeticTests(unittest.TestCase):
    def test_masks_scalar_replication_swizzle_and_sm3_sincos(self):
        machine = Machine({'r0': [2., 3., 4., 5.], 'v0': [0., 1., 2., 3.]},
                          lambda *args: [.1, .2, .3, .4])
        machine.run('ps_3_0\ntexld r0.xyz, v0, s0\nmov r1, -r0_abs.wzyx\nsincos r0.x, v0.x\npow r2.y, r1.x, v0.z')
        self.assertEqual(machine.registers['r0'], [1., .2, .3, 5.])
        self.assertEqual(machine.registers['r1'], [-5., -.3, -.2, -.1])
        self.assertEqual(machine.registers['r2'][1], 25.)
        self.assertTrue(math.isnan(machine.registers['r2'][0]))

    def test_nested_branch_and_unsupported_program_rejection(self):
        result = Machine({'c0': [0., 1., 2., 3.]}).run(
            'if_eq c0.x, c0.y\nif_ne c0.x, c0.y\nmov r0, c0.z\nendif\nelse\nmov r0, c0.w\nendif')
        self.assertEqual(result.registers['r0'], [3.] * 4)
        for code in ('endif', 'if_eq c0.x, c0.x', 'unknown r0, c0'):
            with self.assertRaises(ValueError): Machine({'c0': [0.]*4}).run(code)


class VolumeTranslationTests(unittest.TestCase):
    def assertLanes(self, a, b, count=4):
        for actual, expected in zip(a[:count], b[:count]):
            self.assertTrue(math.isfinite(actual) and math.isfinite(expected))
            self.assertAlmostEqual(actual, expected, delta=max(1e-8, abs(expected) * 1e-7))

    def test_complete_preset_programs_with_neutral_modern_extensions(self):
        vertices = [(x, y, z) for x, y in ((.3, .4), (-.8, .1), (0., 0.)) for z in (-.7, 0., .6)]
        for slot in (7, 8):
            _, preset, translated = programs(slot)
            for kind in (0., 2., 4.):
                for vertex in vertices:
                    if (slot, kind, vertex) == (8, 2., (0., 0., 0.)):
                        continue  # Singular original geometry is tested explicitly below.
                    with self.subTest(slot=slot, kind=kind, vertex=vertex):
                        registers = volume_inputs(slot, kind, vertex)
                        expected = Machine(registers, occlusion).run(preset)
                        actual = Machine(registers, occlusion).run(translated)
                        for output, count in (('o0', 4), ('o1', 4), ('o2', 3), ('o3', 3)):
                            self.assertLanes(actual.registers[output], expected.registers[output], count)
                        self.assertEqual(len(actual.samples), len(expected.samples))
                        for (sa, uv, lod), (sb, euv, elod) in zip(actual.samples, expected.samples):
                            self.assertEqual((sa, lod), (sb, elod))
                            self.assertLanes(uv, euv, 2)
                        self.assertLanes(actual.registers['o10'][2:], actual.registers['o0'][2:], 2)

    def test_original_singular_vertex_is_not_misreported_as_valid_rendering(self):
        _, preset, translated = programs(8)
        registers = volume_inputs(8, 2., (0., 0., 0.))
        expected = Machine(registers, occlusion).run(preset)
        actual = Machine(registers, occlusion).run(translated)
        # Both programs divide by the zero-length displacement for this input.
        # Keep its undefined arithmetic visible; do not silently clamp it away.
        self.assertTrue(all(math.isnan(v) for v in expected.registers['o0']))
        self.assertTrue(all(math.isnan(v) for v in actual.registers['o0']))
        self.assertEqual(expected.samples, actual.samples)
        self.assertLanes(actual.registers['o3'], expected.registers['o3'], 3)

    def test_smooth_volume_ratio_and_fog_survive_the_preset_change(self):
        for slot in (7, 8):
            _, _, translated = programs(slot)
            for kind in (0., 2., 4.):
                base_data = volume_inputs(slot, kind, (.3, .4, .6))
                base = Machine(base_data, occlusion).run(translated)
                smooth_data = volume_inputs(slot, kind, (.3, .4, .6), smooth=1)
                smooth = Machine(smooth_data, occlusion).run(translated)
                # VS7 has no occlusion rescaling: its displacement has exactly
                # the modern smooth radius ratio on top of the preset radius.
                if slot == 7:
                    origin = base_data['c209']
                    for i in range(3):
                        self.assertAlmostEqual(smooth.registers['o0'][i] - origin[i],
                            (base.registers['o0'][i] - origin[i]) * f32(.85) / f32(.662), places=6)
                fog_data = volume_inputs(slot, kind, (.3, .4, .6), smooth=1, fog=1)
                fog = Machine(fog_data, occlusion).run(translated)
                for output, count in (('o0', 4), ('o1', 4), ('o2', 3), ('o10', 4)):
                    self.assertLanes(fog.registers[output], smooth.registers[output], count)
                for i in range(3):
                    self.assertGreater(fog.registers['o3'][i], 0.)
                    self.assertLess(fog.registers['o3'][i], smooth.registers['o3'][i])

    def test_modern_sampler_declarations_fog_and_depth_output_blocks_are_untouched(self):
        for slot in (7, 8):
            source, _, translated = programs(slot)
            a, b = instructions(source), instructions(translated)
            self.assertEqual([line for line in a if line.startswith('dcl')],
                             [line for line in b if line.startswith('dcl')])
            start = a.index('if_ne -c236_abs.y, c236_abs.y')
            end = a.index('endif', start) + 1
            new_start = b.index(a[start])
            self.assertEqual(a[start:end], b[new_start:new_start + end - start])
            self.assertEqual(a[a.index('mov o0, r1'):], b[b.index('mov o0, r1'):])
        shader = next(s for s in CONTRACT['entries'] if s['preset_file'] == 'vshC35A5E05.txt')
        self.assertIn('gDeferredLightSampler1', shader['translation']['occlusion'])


class CompositeTranslationTests(unittest.TestCase):
    def setUp(self):
        self.source = (FIXTURES / 'modern_composite12.ps').read_text(encoding='utf-8')
        self.target = ENTRIES['psh22DCDB69.txt']['targets'][0]
        self.translated = apply_edits(self.source, self.target['edits'])

    def inputs(self, depth, luma, hdr):
        return {'v0': [.51, .48, 0., 0.], 'c44': [0., 16/9, 1., 0.], 'c66': [1.4, 0., 0., 0.],
                'c76': [1/1280, 1/720, 0., 0.], 'c77': [.1, 1000., 0., 0.],
                'c78': [0., 2., 60., 5.], 'c79': [0., .1, .9, 0.],
                'c81': [.8, .7, 4., 0.], 'c82': [.2, 0., 1.3, 0.],
                'c83': [.8, .6, .4, 0.], 'c84': [.1, .2, .3, .4],
                'c209': [10., 1/math.log2(10000), 10000., .1], 'c217': [0., 0., hdr, luma]}

    def sampler(self, depth, level, bloom):
        def sample(name, uv, lod):
            x, y = uv[:2]
            if name == 's1': return [depth, 0., 0., 0.]
            if name == 's2': return [level*(.4 + x*x), level*(.8 + y), level*(.7 + x*y), .91]
            if name == 's4': return [bloom*.4, bloom*.6, bloom*.7, .3]
            if name == 's5': return [.3, 0., 0., 1.]
            if name == 's10': return [x + y*.1, y + x*.2, x*.3 + y*.4, 1.]
            raise AssertionError('Unexpected composite resource: ' + name)
        return sample

    def reference(self, registers, sample):
        # Direct equations for the modern filter with the preset's revised
        # weights, signed bloom and tone response, independent of register code.
        values = Machine(registers, sample).run('\n'.join(line for line in instructions(self.source)
            if line.startswith('def '))).registers
        c = lambda n: values[f'c{n}']
        x = (registers['v0'][0]*c(7)[0] + c(7)[1]) * c(44)[1]*c(44)[2] + c(7)[2]
        y = registers['v0'][1]
        uv = [x, y, 0., 0.]
        eye = abs(c(209)[2]) ** sample('s1', uv, None)[0] * c(209)[3]
        offsets = [(c(4)[0], c(4)[1]), (c(4)[2], c(4)[0]),
                   (c(4)[3], c(4)[2]), (c(4)[1], c(4)[3])]
        neighbours = [sample('s2', [x+dx*c(76)[0], y+dy*c(76)[1]], None)[:3] for dx, dy in offsets]
        center = sample('s2', uv, None)[:3]
        weights = c(1)[1:]
        lum = lambda rgb: sum(v*w for v, w in zip(rgb, weights))
        mean = sum(lum(rgb) for rgb in neighbours) * f32(.1)
        variance = sum((lum(rgb) - mean)**2 for rgb in neighbours)
        t = max(eye - c(78)[3] - c(78)[1]*c(4)[3], 0.) / c(78)[2]
        coc = min(c(79)[2], t*c(79)[2] + (1-t)*c(79)[1])**2
        blend = 1. if (lum(center)-mean)**2 >= variance else coc
        colour = [blend*sum(p[i] for p in neighbours)*f32(.1) + (1-blend)*center[i] for i in range(3)]
        adaptation = c(81)[1] / sample('s5', [0., 0.], None)[0]
        threshold = c(81)[0] / adaptation
        bloom = sample('s4', uv, None)[:3]
        if c(217)[3] == 0:
            extra = [(v*c(66)[0] - threshold)*f32(.1) for v in bloom]
        else:
            length = math.sqrt(lum([v*v for v in bloom]))
            extra = [v*(length*c(66)[0] - threshold)/length*f32(.1) for v in bloom]
        colour = [v*c(66)[0] + e for v, e in zip(colour, extra)]
        gamma = saturate(lum([v*adaptation for v in colour])) ** (c(82)[2] - 1)
        colour = [abs(v)**f32(.45)*gamma for v in colour]
        if c(217)[2]:
            def pq(v):
                value = (v**c(13)[1] * c(20)[0])**c(20)[1]
                return saturate(((value*c(20)[2]+c(20)[3]) / (value*c(21)[0]+c(21)[1]))**c(21)[2])
            r, g, b = [pq(v) for v in colour]
            z = b*c(10)[0]
            fraction = z - math.floor(z)
            u = (r*c(10)[0]+c(10)[1])*c(10)[2] + math.floor(z)*c(10)[3]
            v = (g*c(10)[0]+c(10)[1])*c(10)[3]
            a, b = sample('s10', [u, v], 0), sample('s10', [u+c(10)[3], v], 0)
            colour = [(1-fraction)*x + fraction*y for x, y in zip(a[:3], b[:3])]
        return [*colour, 1.]

    def test_complete_modern_composite_matches_independent_effect_equations(self):
        for depth in (0., .25, .6, .9, 1.):
            for level in (.03, .5, 3.):
                for bloom in (.1, 2.):
                    for luma in (0, 1):
                        for hdr in (0, 1):
                            with self.subTest(depth=depth, level=level, bloom=bloom, luma=luma, hdr=hdr):
                                registers = self.inputs(depth, luma, hdr)
                                sample = self.sampler(depth, level, bloom)
                                output = Machine(registers, sample).run(self.translated).registers['oC0']
                                for actual, expected in zip(output, self.reference(registers, sample)):
                                    self.assertTrue(math.isfinite(actual))
                                    self.assertAlmostEqual(actual, expected, delta=max(2e-6, abs(expected)*2e-6))

    def test_colour_controls_and_bloom_scale_removed_but_adaptation_retained(self):
        data = self.inputs(.6, 0, 0)
        sample = self.sampler(.6, .5, 2.)
        output = Machine(data, sample).run(self.translated).registers['oC0']
        altered = copy.deepcopy(data)
        altered.update(c83=[50., 20., 10., 4.], c84=[9., 8., 7., 6.])
        altered['c82'][0] = 10.
        altered['c81'][2] = 500.
        self.assertEqual(output, Machine(altered, sample).run(self.translated).registers['oC0'])
        altered['c81'][1] = .2
        self.assertNotEqual(output, Machine(altered, sample).run(self.translated).registers['oC0'])

    def test_modern_depth_coordinates_bindings_and_hdr_tail_preserved(self):
        original, translated = instructions(self.source), instructions(self.translated)
        self.assertEqual([s for s in original if s.startswith('dcl')], [s for s in translated if s.startswith('dcl')])
        start, end = original.index('mov r20.xy, v0'), original.index('dp3 r0.x, r7, c1.yzww')
        begin = translated.index(original[start])
        self.assertEqual(original[start:end], translated[begin:begin+end-start])
        tail = 'if_ne -c217_abs.z, c217_abs.z'
        self.assertEqual(original[original.index(tail):], translated[translated.index(tail):])
        self.assertIn('def c4, -0.5, -1.5, 1.5, 0.5', translated)
        self.assertIn('pow r0.x, r0.x, c18.y', translated)
        self.assertEqual(f32(.449999988), f32(.45))


if __name__ == '__main__':
    unittest.main()
