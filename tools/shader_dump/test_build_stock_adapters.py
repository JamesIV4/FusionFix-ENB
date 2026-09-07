import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from build_stock_adapters import (RECIPES, apply_edits, collision_scan,
                                   free_registers, verify_fixture, verify_variant)
from shader_edits import instructions
from shader_files import sha


class PresetAdapterTests(unittest.TestCase):
    def test_exact_edit_preserves_coverage_and_depth_instructions(self):
        source = 'ps_3_0\ntexld r0, v0, s0\ntexkill r20\nmov oDepth, r19.x\n'
        delta = [{'before': ['texld r0, v0, s0'],
                  'after': ['texld r0, v0, s0', 'mul r0.xyz, r0, c177.x']}]
        self.assertEqual(instructions(apply_edits(source, delta)),
                         ['ps_3_0', 'texld r0, v0, s0', 'mul r0.xyz, r0, c177.x',
                          'texkill r20', 'mov oDepth, r19.x'])

    def test_missing_duplicate_or_unnormalized_anchor_rejected(self):
        delta = [{'before': ['mov r0, c0'], 'after': ['mov r0, c1']}]
        for source in ('mov r0, c2', 'mov r0, c0\nmov r0, c0'):
            with self.assertRaisesRegex(ValueError, 'exact edit anchor'):
                apply_edits(source, delta)
        for before in ([], [' mov r0, c0'], ['// comment']):
            with self.assertRaises(ValueError):
                apply_edits('mov r0, c0', [{'before': before, 'after': []}])

    def test_scratch_collision_in_source_operands_and_declarations(self):
        for source in ('def c175, 0, 0, 0, 0', 'mov r0, r11.w', 'mov r0, r11_abs', 'dcl_2d s13'):
            with self.assertRaisesRegex(ValueError, 'already used'):
                free_registers(source, [175], [11], [13])
        free_registers('// r11 c175 s13\nmov r110, c1750\ndcl_texcoord9 v9', [175], [11], [13])
        with self.assertRaisesRegex(ValueError, 'Relative constant'):
            free_registers('mov r0, c0[aL]', [175], [], [])

    def test_variant_requires_complete_exact_container_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'one.fxc').write_bytes(b'one')
            expected = {'one.fxc': sha(b'one'), 'two.fxc': sha(b'two')}
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                verify_variant(directory, expected)
            (directory / 'two.fxc').write_bytes(b'two')
            self.assertEqual(set(verify_variant(directory, expected)), set(expected))
            (directory / 'two.fxc').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                verify_variant(directory, expected)

    def test_arithmetic_fixture_must_match_the_actual_shader_and_stay_in_the_fixture_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            relative = 'tools/shader_dump/fixtures/check.ps'
            fixture = directory / relative
            fixture.parent.mkdir(parents=True)
            fixture.write_text('ps_3_0\nmov oC0, c0\n', encoding='utf-8')
            with patch('build_stock_adapters.ROOT', directory):
                verify_fixture(relative, '// metadata\nps_3_0\nmov oC0, c0\n')
                with self.assertRaisesRegex(ValueError, 'differs'):
                    verify_fixture(relative, 'ps_3_0\nmov oC0, c1')
                with self.assertRaisesRegex(ValueError, 'inside'):
                    verify_fixture('../outside.ps', 'ps_3_0')

    def test_collisions_are_checked_against_actual_program_bytes(self):
        class Shader:
            stage = 'ps'
            def __init__(self, data): self.data = data
        outputs = {'psh11111111.txt': {'original_sha256': sha(b'expected')}}
        with patch('build_stock_adapters.filename', return_value='psh11111111.txt'), \
             patch('build_stock_adapters.d3d9bc.extract_file', return_value=[Shader(b'changed')]):
            with self.assertRaisesRegex(ValueError, 'collision'):
                collision_scan({'one.fxc': Path('one.fxc')}, outputs)
        with self.assertRaisesRegex(ValueError, 'no target'):
            collision_scan({}, outputs)

    def test_checked_in_contract_accounts_for_all_twelve_inputs(self):
        contract = json.loads(RECIPES.read_text(encoding='utf-8'))
        self.assertEqual(len(contract['entries']), 12)
        self.assertEqual(len(contract['stock_corpus']), 102)
        self.assertEqual(sum(e['status'] == 'built_offline' for e in contract['entries']), 11)
        self.assertFalse(any(e['status'] == 'pending_translation' for e in contract['entries']))
        grass = next(e for e in contract['entries'] if e['preset_file'] == 'psh71CC11CF.txt')
        self.assertEqual((grass['legacy_edits'], grass['targets']), ([], []))

    def test_normal_translation_preserves_live_stock_coverage_register(self):
        contract = json.loads(RECIPES.read_text(encoding='utf-8'))
        normal = next(e for e in contract['entries'] if e['preset_file'] == 'psh8DB4CDB2.txt')
        target = normal['targets'][0]
        # These extra registers must be unused before patching. In particular,
        # r1.x carries stock coverage through all new normal/specular work.
        self.assertNotIn(1, target['scratch']['temporaries'])
        for edit in target['edits']:
            for line in edit['after']:
                self.assertNotRegex(line, r'^\w+\s+r1(?:\.|,)')

    def test_billboard_changes_only_wd_draw_and_matches_legacy_wind_ratio(self):
        contract = json.loads(RECIPES.read_text(encoding='utf-8'))
        billboard = next(e for e in contract['entries'] if e['preset_file'] == 'psh46A43A9F.txt')
        self.assertEqual([(t['slot'], t['roles']) for t in billboard['targets']], [(4, ['wd_draw/0'])])
        # Stock VS supplies 16*color+8; the preset uses 32*color+16. Its
        # offset changes from 1/640 to .001, preserving stock size scaling.
        for color in (0., .25, .5, 1.):
            wind = 16 * color + 8
            self.assertEqual(2 * wind, 32 * color + 16)
            for noise in (0., .4, 1.):
                legacy_offset = (32 * color + 16) * noise * .001
                translated = 2 * wind * noise * (1 / 128) * .128
                self.assertAlmostEqual(legacy_offset, translated)

    def test_specular_register_relocation_keeps_shininess_and_coverage(self):
        # Old r2.w and stock r2.x carry shininess; old r2.x and stock r2.w
        # carry specularity. Exercise both recipes with a nonconstant detail
        # signal so a mistaken component mapping cannot hide in a zero delta.
        contract = json.loads(RECIPES.read_text(encoding='utf-8'))
        recipes = {}
        for name in ('pshF5256B40.txt', 'psh8DB4CDB2.txt'):
            entry = next(e for e in contract['entries'] if e['preset_file'] == name)
            recipes[name] = next(edit['after'] for edit in entry['targets'][0]['edits']
                                 if edit['before'][0].startswith('texld r3, v0, s') and len(edit['before']) == 3)
        def execute(code, registers):
            # Interpret the actual checked-in scalar instructions, independently
            # of the recipe builder and its pinned assembler-output hashes.
            for line in code:
                opcode, operands = line.split(' ', 1)
                destination, *sources = operands.split(', ')
                values = [registers[s] for s in sources]
                op = opcode.removesuffix('_sat')
                if op == 'mov': result = values[0]
                elif op == 'mul': result = values[0] * values[1]
                elif op == 'add': result = values[0] + values[1]
                elif op == 'lrp': result = values[0] * values[1] + (1 - values[0]) * values[2]
                else: self.fail('Unexpected opcode in specular recipe: ' + opcode)
                registers[destination] = min(1., max(0., result)) if opcode.endswith('_sat') else result
        for spec in (0., .1, .6, 2.):
            for detail in (-.7, .25, 1.):
                for shininess in (.03, 4., 80.):
                    for name, code in recipes.items():
                        normal = name == 'psh8DB4CDB2.txt'
                        weight = min(1., max(0., spec if normal else 2 * spec))
                        expected = min(1., max(0., weight * spec + (1 - weight) * spec * detail))
                        stock = {'r12.w': shininess, 'r12.x': spec, 'r11.w': detail,
                                  'c177.z': 1., 'r1.x': .37}
                        execute(code, stock)
                        self.assertAlmostEqual(stock['r2.w'], expected)
                        self.assertEqual(stock['r2.x'], shininess)
                        self.assertEqual(stock['r1.x'], .37)


if __name__ == '__main__':
    unittest.main()
