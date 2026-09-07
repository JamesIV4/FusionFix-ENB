import json
from pathlib import Path
import struct
import tempfile
import unittest

import d3d9bc
from shader_edits import verify_unchanged_tokens
from prepare_stock_baseline import baseline_files
from build_stock_adapters import RECIPES, verify_variant, apply_edits
from shader_files import sha


def program(literal=.25, source=0):
    data = struct.pack('<3I4f4I', 0xFFFF0300, 0x05000051, 0xA00F0000,
                       .5, 0., 1., literal, 0x02000001, 0x800F0800, 0xA0E40000 | source, 0xFFFF)
    return d3d9bc.extract(data)[0]


class StockBaselineTests(unittest.TestCase):
    def test_runtime_whitelist_is_exact_and_has_no_extended_tree_exception(self):
        files = baseline_files()
        self.assertEqual(len(files), 339)
        self.assertEqual(sum(p.endswith('.fxc') for p in files), 102)
        self.assertTrue(all('extended' not in p for p in files))
        self.assertIn('preload.list', files)

    def test_fusion_bytecode_cannot_be_blessed_by_a_local_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            data = b'file containing FusionShader marker'
            (directory / 'test.fxc').write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'forbidden'):
                verify_variant(directory, {'test.fxc': sha(data)})

    def test_unedited_instruction_tokens_must_remain_exact(self):
        before = 'ps_3_0\ndef c0, 0.5, 0, 1, 0.25\nmov oC0, c0\n'
        after = before.replace('1, 0.25', '1, 0')
        edits = [{'before': ['def c0, 0.5, 0, 1, 0.25'], 'after': ['def c0, 0.5, 0, 1, 0']}]
        verify_unchanged_tokens(before, after, program(), program(0.), edits)
        # Same assembly text, but a changed source register in the unedited MOV.
        with self.assertRaisesRegex(ValueError, 'unedited'):
            verify_unchanged_tokens(before, after, program(), program(0., 1), edits)

    def test_all_translations_target_the_exact_stock_corpus(self):
        recipes = json.loads(RECIPES.read_text(encoding='utf-8'))
        baseline = {Path(p).name: h for p, h in baseline_files().items() if p.endswith('.fxc')}
        self.assertEqual(recipes['stock_corpus'], baseline)
        direct = {e['preset_file'] for e in recipes['entries']
                  if e['targets'] and all(t.get('require_preset_program') for t in e['targets'])}
        self.assertEqual(direct, {'psh0CBF49C5.txt','psh405ABC1B.txt','psh841FD9AE.txt',
                                 'vsh54F25463.txt','vshC35A5E05.txt','psh22DCDB69.txt'})
        for entry in recipes['entries']:
            for target in entry['targets']:
                source = Path(__file__).resolve().parents[2] / target['validation_stock_fixture']
                text = apply_edits(source.read_text(encoding='utf-8'), target['edits'])
                self.assertEqual(sha(text.encode('utf-8')), target['assembly_sha256'])
                self.assertNotIn('FusionShader', text)
                self.assertNotIn('c236', text)
                self.assertNotIn('oDepth', text)


if __name__ == '__main__':
    unittest.main()
