"""Stage exact CE shader files, stock-targeted aliases and the current ASI.

No installation or game launch. The native ASI embeds the same baseline hashes.
"""
import argparse
import json
from pathlib import Path
import re
import shutil

from shader_files import sha, leaf

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / 'research/contracts/stock-ce-baseline.json'


def baseline_files():
    files = json.loads(BASELINE.read_text(encoding='utf-8'))['files']
    compiled = dict(re.findall(r'\{L"([^"]+)", "([0-9a-f]{64})"\}',
                              (ROOT / 'source/enb_compat/stockfiles.inc').read_text()))
    if compiled != files or len(files) != 339:
        raise ValueError('Runtime and offline stock CE whitelists disagree')
    return files


def build(stock, adapters, asi, out):
    stock, adapters, asi, out = [Path(p).resolve() for p in (stock, adapters, asi, out)]
    if out.exists() or any(out.is_relative_to(p) or p.is_relative_to(out) for p in (stock, adapters)):
        raise ValueError('Output must be new and separate from inputs')
    if any((p / 'GTAIV.exe').exists() for p in (out, *out.parents)):
        raise ValueError('Stage outside the game directory')
    files = baseline_files()
    for relative, digest in files.items():
        if sha((stock / relative).read_bytes()) != digest:
            raise ValueError('Stock CE baseline changed: ' + relative)
    manifest = json.loads((adapters / 'manifest.json').read_text(encoding='utf-8'))
    recipes = json.loads((ROOT / 'research/contracts/stock-ce-adapters.json').read_text(encoding='utf-8'))
    approved_aliases = {t['stock_alias']: t['assembly_sha256'] for e in recipes['entries'] for t in e['targets']}
    if manifest['backend'] != 'exact_1040_to_stock_ce_delta':
        raise ValueError('Only stock CE adapters are supported')
    expected_corpus = {Path(p).name: h for p, h in files.items() if p.startswith('win32_30_nv8/')}
    if manifest['stock_corpus'] != expected_corpus:
        raise ValueError('Adapter corpus differs from the exact stock baseline')
    aliases = {}
    for entry in manifest['entries']:
        if entry['status'] not in ('built_offline', 'no_preset_delta'):
            raise ValueError('Incomplete translation set')
        for target in entry['targets']:
            name = leaf(target['alias'])
            if not re.fullmatch(r'[pv]sh[0-9A-F]{8}\.txt', name):
                raise ValueError('Invalid alias name')
            if sha((adapters / 'shaderinput' / name).read_bytes()) != target['assembly_sha256']:
                raise ValueError('Alias assembly changed: ' + name)
            if sha((adapters / 'assembled' / (name[:-4] + '.cso')).read_bytes()) != target['adapted_sha256']:
                raise ValueError('Assembled alias changed: ' + name)
            if name in aliases and aliases[name] != target['assembly_sha256']:
                raise ValueError('Conflicting stock alias')
            aliases[name] = target['assembly_sha256']
    if aliases != approved_aliases:
        raise ValueError('Aliases differ from the reviewed stock CE recipes')
    binary = asi.read_bytes()
    if binary[:2] != b'MZ' or b'exact stock CE shaders' not in binary:
        raise ValueError('Build the new stock-only ASI before staging')
    retired = json.loads((ROOT / 'tools/gamesetup/retired-shader-paths.json').read_text())
    report = {'format': 1, 'profile': 'stock-ce-only', 'baseline_files': files,
              'aliases': aliases, 'asi_sha256': sha(binary), 'retired_paths': retired,
              'game_modified': False, 'rendering_validated': False}
    out.mkdir(parents=True)
    for relative in files:
        target = out / 'StockCE' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(stock / relative, target)
    (out / 'shaderinput').mkdir()
    for name in aliases:
        shutil.copyfile(adapters / 'shaderinput' / name, out / 'shaderinput' / name)
    (out / 'GTAIV.EFLC.FusionFix.asi').write_bytes(binary)
    (out / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock', type=Path, required=True, help='Original game common/shaders directory')
    parser.add_argument('--adapters', type=Path, required=True)
    parser.add_argument('--asi', type=Path, default=ROOT / 'bin/GTAIV.EFLC.FusionFix.asi')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = build(args.stock, args.adapters, args.asi, args.out)
    print(f"Staged {len(report['baseline_files'])} exact stock files and {len(report['aliases'])} stock aliases. No installation.")
