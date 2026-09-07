"""Small SM3 arithmetic model for the audited translation regression tests.

This executes text instructions with caller-supplied texture functions. It is
not a renderer: it does not emulate GPU precision, derivative-based filtering,
or driver behavior outside the instruction specifications. Undefined lanes
start as NaN so a lost write mask or live register is visible to the tests.
"""
import math
import re
import struct

from build_shader_adapter import instructions

LANES = 'xyzw'
OPERAND = re.compile(r'(-?)([A-Za-z][A-Za-z0-9]*?)(_abs)?(?:\.([xyzw]{1,4}))?$')


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def saturate(value):
    return value if math.isnan(value) else min(1., max(0., value))


def reciprocal(value):
    return math.copysign(math.inf, value) if value == 0 else 1 / value


def power(value, exponent):
    try:
        return abs(value) ** exponent
    except ZeroDivisionError:
        return math.inf
    except OverflowError:
        return math.inf


class Machine:
    def __init__(self, registers=None, sample=None):
        self.registers = {name: list(values) for name, values in (registers or {}).items()}
        self.sample = sample
        self.samples = []

    def source(self, operand):
        match = OPERAND.fullmatch(operand)
        if not match:
            raise ValueError('Unsupported source operand: ' + operand)
        negative, name, absolute, swizzle = match.groups()
        values = self.registers.get(name, [math.nan] * 4)
        swizzle = swizzle or LANES
        if len(swizzle) == 1:
            swizzle *= 4
        elif len(swizzle) != 4:
            # D3DX exports explicit four-lane swizzles or scalar replication.
            raise ValueError('Use a normalized source swizzle: ' + operand)
        result = [values[LANES.index(c)] for c in swizzle]
        if absolute:
            result = [abs(v) for v in result]
        return [-v for v in result] if negative else result

    def write(self, destination, values, clamp=False):
        name, _, mask = destination.partition('.')
        target = self.registers.setdefault(name, [math.nan] * 4)
        for component in mask or LANES:
            i = LANES.index(component)
            target[i] = saturate(values[i]) if clamp else values[i]

    def run(self, assembly):
        active, branches = True, []
        for line in instructions(assembly):
            if line in ('ps_3_0', 'vs_3_0') or line.startswith('dcl'):
                continue
            op, _, text = line.partition(' ')
            operands = text.split(', ') if text else []
            if op in ('def', 'defi'):
                self.registers[operands[0]] = [f32(float(v)) for v in operands[1:]]
                continue
            if op.startswith('if_'):
                condition = False
                if active:
                    a, b = (self.source(operand)[0] for operand in operands)
                    if not (math.isfinite(a) and math.isfinite(b)):
                        raise ValueError('Nonfinite branch condition')
                    comparison = op[3:]
                    if comparison == 'ge': condition = a >= b
                    elif comparison == 'eq': condition = a == b
                    elif comparison == 'ne': condition = a != b
                    else: raise ValueError('Unsupported comparison: ' + op)
                branches.append((active, condition))
                active = active and condition
                continue
            if op == 'else':
                if not branches: raise ValueError('Unmatched else')
                parent, condition = branches[-1]
                active = parent and not condition
                continue
            if op == 'endif':
                if not branches: raise ValueError('Unmatched endif')
                active = branches.pop()[0]
                continue
            if not active:
                continue
            clamp = op.endswith('_sat')
            op = op.removesuffix('_sat')
            destination, *sources = operands
            if op in ('texld', 'texldl'):
                if self.sample is None:
                    raise ValueError('A texture function is required')
                coordinate = self.source(sources[0])
                sampler = sources[1]
                lod = coordinate[3] if op == 'texldl' else None
                self.samples.append((sampler, tuple(coordinate[:2]), lod))
                result = list(self.sample(sampler, coordinate, lod))
            else:
                args = [self.source(source) for source in sources]
                if op == 'mov': result = args[0]
                elif op == 'add': result = [a + b for a, b in zip(*args)]
                elif op == 'mul': result = [a * b for a, b in zip(*args)]
                elif op == 'mad': result = [a * b + c for a, b, c in zip(*args)]
                elif op == 'lrp': result = [a * b + (1 - a) * c for a, b, c in zip(*args)]
                elif op in ('min', 'max'):
                    choose = min if op == 'min' else max
                    result = [math.nan if math.isnan(a) or math.isnan(b) else choose(a, b) for a, b in zip(*args)]
                elif op in ('sge', 'slt'):
                    result = [float(a >= b if op == 'sge' else a < b) for a, b in zip(*args)]
                elif op == 'cmp':
                    result = [math.nan if math.isnan(a) else (b if a >= 0 else c) for a, b, c in zip(*args)]
                elif op in ('dp3', 'dp4'):
                    count = int(op[-1])
                    result = [sum(args[0][i] * args[1][i] for i in range(count))] * 4
                elif op == 'frc': result = [v - math.floor(v) if math.isfinite(v) else math.nan for v in args[0]]
                elif op == 'rcp': result = [reciprocal(args[0][0])] * 4
                elif op == 'rsq': result = [reciprocal(math.sqrt(abs(args[0][0])))] * 4
                elif op == 'pow': result = [power(args[0][0], args[1][0])] * 4
                elif op == 'log': result = [math.log2(abs(args[0][0])) if args[0][0] != 0 else -math.inf] * 4
                elif op == 'exp': result = [power(2., args[0][0])] * 4
                elif op == 'sincos': result = [math.cos(args[0][0]), math.sin(args[0][0]), math.nan, math.nan]
                else: raise ValueError('Unsupported arithmetic instruction: ' + op)
            self.write(destination, result, clamp)
        if branches:
            raise ValueError('Unterminated branch')
        return self
