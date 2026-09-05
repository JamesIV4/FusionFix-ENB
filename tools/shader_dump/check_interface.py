"""Check a shader set against a declared interface contract.

    python check_interface.py --contract research/contracts/enb-postfx.json \
                              "CE stock=out/ce-postfx" "FusionFix=out/ff-postfx"

Each argument is ``label=directory``, where the directory holds ``.asm`` files
written by ``dump_fxc.py --asm``.

Two independent checks per shader, because they fail in different ways:

* **by name** -- read the CTAB reflection table in the disassembly header and
  compare each parameter's register to the contract. Catches a moved parameter.
  Silent when a shader has no CTAB at all, which is itself reported, since a
  consumer that looks parameters up by name has nothing to look at.
* **by use** -- read the instruction stream and list which constant registers
  and samplers the shader actually reads, ignoring its own ``def`` constants.
  Works with or without reflection data, and catches a shader that has grown a
  dependency on a register nobody writes.

Written for the question "does this build still present the interface an old
ENB preset expects", but nothing in it is ENB-specific.
"""

import argparse
import json
import os
import re
import sys

DEF_RE = re.compile(r'^\s*def[ib]?\s+c(\d+)', re.I)
CONST_RE = re.compile(r'\bc(\d+)(?:_abs)?\b')
SAMPLER_RE = re.compile(r'\bs(\d+)\b')
# "//   ParamName        c44      1"
CTAB_RE = re.compile(r'^//\s+(\w+)\s+([cs]\d+)\s+\d+\s*$')


def parse_asm(path):
    """Return (ctab_registers, constants_read, samplers_read, has_ctab)."""
    ctab = {}
    defined, used_c, used_s = set(), set(), set()
    has_ctab = False

    with open(path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            line = raw.rstrip('\n')
            if line.lstrip().startswith('//'):
                if 'Parameters:' in line:
                    has_ctab = True
                m = CTAB_RE.match(line)
                if m:
                    ctab[m.group(1)] = m.group(2)
                continue

            code = line.split('//', 1)[0]
            if not code.strip():
                continue
            m = DEF_RE.match(code)
            if m:
                defined.add(int(m.group(1)))
                continue
            head = code.split(None, 1)[0].lower()
            if head.startswith('dcl'):
                used_s.update(int(x) for x in SAMPLER_RE.findall(code))
                continue
            used_c.update(int(x) for x in CONST_RE.findall(code))
            used_s.update(int(x) for x in SAMPLER_RE.findall(code))

    return ctab, used_c - defined, used_s, has_ctab


def ranges(values):
    values = sorted(values)
    if not values:
        return 'none'
    out, i = [], 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[j + 1] == values[j] + 1:
            j += 1
        out.append(str(values[i]) if i == j else '%d-%d' % (values[i], values[j]))
        i = j + 1
    return ','.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--contract', required=True)
    ap.add_argument('sets', nargs='+', metavar='LABEL=DIR')
    ap.add_argument('--anchor', default=None,
                    help='only consider shaders declaring or reading this parameter '
                         '(default: the contract\'s most distinctive constant)')
    args = ap.parse_args(argv)

    with open(args.contract, encoding='utf-8') as fh:
        contract = json.load(fh)

    want = dict(contract.get('constants', {}))
    want.update(contract.get('samplers', {}))
    want_c = set(contract.get('expected_constant_registers', []))
    want_s = set(contract.get('expected_sampler_registers', []))
    anchor = args.anchor or next(iter(contract.get('constants', {})), None)

    print('contract: %s  (%d named parameters)' % (contract.get('name', args.contract), len(want)))
    if anchor:
        print('anchor:   %s\n' % anchor)

    for spec in args.sets:
        if '=' not in spec:
            print('expected LABEL=DIR, got %r' % spec)
            return 2
        label, directory = spec.split('=', 1)
        print('== %s ==' % label)

        candidates = 0
        full = []
        no_ctab = 0
        for name in sorted(os.listdir(directory)):
            if not name.endswith('.asm'):
                continue
            ctab, used_c, used_s, has_ctab = parse_asm(os.path.join(directory, name))

            # A shader is a candidate if it names the anchor, or -- for a build
            # with no reflection data -- if its register use is close enough to
            # the contract to be the same shader.
            is_candidate = anchor in ctab
            if not is_candidate and not has_ctab:
                is_candidate = len(used_c & want_c) >= max(2, len(want_c) // 2)
            if not is_candidate:
                continue

            candidates += 1
            if not has_ctab:
                no_ctab += 1

            matched = sum(1 for k, v in want.items() if ctab.get(k) == v)
            extra_c = ranges(used_c - want_c)
            missing_c = ranges(want_c - used_c)
            extra_s = ranges(used_s - want_s)

            status = 'FULL MATCH' if matched == len(want) else '%d/%d by name' % (matched, len(want))
            if not has_ctab:
                status = 'no reflection data'
            print('  %-34s %-20s c:%-26s s:%s'
                  % (name, status, ranges(used_c), ranges(used_s)))
            if extra_c != 'none' or extra_s != 'none' or missing_c != 'none':
                print('  %-34s %-20s extra c:%s  missing c:%s  extra s:%s'
                      % ('', '', extra_c, missing_c, extra_s))
            if matched == len(want):
                full.append(name)

        print('  -> %d candidate(s), %d honour the contract exactly, %d carry no reflection data\n'
              % (candidates, len(full), no_ctab))

    return 0


if __name__ == '__main__':
    sys.exit(main())
