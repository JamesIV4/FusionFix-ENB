"""Decode the bridge's PFX1 texel grids without creating a graphics device.

Values are raw normalized UNORM or linear float values, not screenshot colors.
Statistics cover a uniform sample grid, not every pixel in the source texture.
"""
import argparse
import json
import math
from pathlib import Path
import statistics
import struct

# D3DFORMAT values, component memory order from the D3D9 headers.
FORMATS = {21: ('4B', (2, 1, 0, 3)), 22: ('4B', (2, 1, 0)),
           32: ('4B', (0, 1, 2, 3)), 33: ('4B', (0, 1, 2)),
           111: ('e', (0,)), 112: ('2e', (0, 1)), 113: ('4e', (0, 1, 2, 3)),
           114: ('f', (0,)), 115: ('2f', (0, 1)), 116: ('4f', (0, 1, 2, 3))}


def decode(data):
    if len(data) < 32:
        raise ValueError('Truncated PFX header')
    magic, width, height, fmt, bpp, columns, rows, reserved = struct.unpack('<8I', data[:32])
    if magic != 0x31584650 or reserved or fmt not in FORMATS:
        raise ValueError('Unsupported PFX header')
    layout, order = FORMATS[fmt]
    if (bpp != struct.calcsize('<' + layout) or not width or not height or
            columns != min(64, width) or rows != min(36, height) or
            len(data) != 32 + bpp * columns * rows):
        raise ValueError('Invalid PFX dimensions, format size, or payload length')
    scale = 255.0 if layout.endswith('B') else 1.0
    pixels = [tuple(p[i] / scale for i in order)
              for p in struct.iter_unpack('<' + layout, data[32:])]
    return {'width': width, 'height': height, 'format': fmt,
            'columns': columns, 'rows': rows}, pixels


def summarize(data):
    header, pixels = decode(data)
    channels = []
    for values in zip(*pixels):
        finite = [v for v in values if math.isfinite(v)]
        channels.append({'finite': len(finite), 'nonfinite': len(values) - len(finite),
                         'min': min(finite) if finite else None,
                         'max': max(finite) if finite else None,
                         'mean': statistics.fmean(finite) if finite else None,
                         'median': statistics.median(finite) if finite else None})
    return {**header, 'samples': len(pixels), 'channels': channels}


def report(directory):
    result = {'path': str(directory), 'sampling': 'centered uniform grid, raw channel values', 'captures': {}}
    for sample in sorted(directory.iterdir()):
        if not sample.is_dir() or not sample.name.isdigit():
            continue
        row = {'textures': {p.stem: summarize(p.read_bytes()) for p in sorted(sample.glob('*.pfx'))}}
        for name in ('inputs', 'output'):
            p = sample / (name + '.txt')
            if p.exists():
                row[name] = p.read_text()
        result['captures'][sample.name] = row
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    output = json.dumps(report(args.directory), indent=2, allow_nan=False) + '\n'
    if args.out:
        args.out.write_text(output, encoding='utf-8')
    else:
        print(output, end='')
