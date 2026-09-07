"""Check captured postfx inputs against the bridge's numeric contracts, offline.

Reports measured faults and intermediate values, never an inferred final image
or a proven cause of darkening. Input files are not modified.
"""
import argparse
import json
import math
from pathlib import Path
import re
import statistics

from prepare_postfx_bridge import legacy_depth
from read_postfx_capture import decode, report as raw_report


def constants(text):
    result = {}
    for line in text.splitlines():
        if not re.match(r'^c\d+(?:\s|$)', line):
            continue
        key, *tokens = line.split()
        if key in result or len(tokens) != 4:
            raise ValueError('Duplicate or malformed constant row: ' + key)
        result[key] = [float(v) for v in tokens]
    return result


def stats(values):
    finite = [v for v in values if math.isfinite(v)]
    return {'finite': len(finite), 'nonfinite': len(values) - len(finite),
            'min': min(finite) if finite else None,
            'max': max(finite) if finite else None,
            'mean': statistics.fmean(finite) if finite else None,
            'median': statistics.median(finite) if finite else None}


def analyze(values, textures):
    findings = []
    result = {'findings': findings, 'depth_check': {'status': 'missing_inputs'},
              'hdr_adaptation': {'status': 'missing_inputs'}}
    nonfinite = [name for name, row in values.items() if any(not math.isfinite(v) for v in row)]
    if nonfinite:
        findings.append({'code': 'nonfinite_constants', 'registers': nonfinite})
    clip, log = values.get('c77'), values.get('c209')
    projection = None
    if clip is not None and log is not None:
        if all(math.isfinite(v) for v in (*clip[:2], *log)) and 0 < clip[0] < clip[1] and log[3] > 0 and log[2] > 1:
            near, far = clip[:2]
            errors = {'near': abs(log[3] / near - 1), 'far': abs(log[2] * log[3] / far - 1),
                      'inverse_near': abs(log[0] * near - 1),
                      'inverse_log_range': abs(log[1] * math.log2(far / near) - 1)}
            projection = (near, far)
            result['projection'] = {'near': near, 'far': far, 'relative_errors': errors}
            if max(errors.values()) >= .01:
                findings.append({'code': 'projection_constants_disagree', 'relative_errors': errors})
        else:
            findings.append({'code': 'invalid_projection_constants'})
    if projection and 's1' in textures and 'converted_depth' in textures:
        source_header, source = textures['s1']
        target_header, target = textures['converted_depth']
        if any(source_header[k] != target_header[k] for k in ('width', 'height', 'columns', 'rows')):
            result['depth_check'] = {'status': 'different_sample_grids'}
        else:
            errors, invalid = [], 0
            for src, dst in zip(source, target):
                if not (math.isfinite(src[0]) and math.isfinite(dst[0])):
                    invalid += 1
                    continue
                # Depth samples outside [0, 1] are clamped by the conversion's
                # saturate. Avoid exponent overflow in a malformed capture.
                expected = legacy_depth(min(1., max(0., src[0])), *projection)
                errors.append(abs(expected - dst[0]))
            result['depth_check'] = {'status': 'compared', 'samples': len(errors), 'nonfinite_pairs': invalid,
                                     'absolute_error': stats(errors), 'tolerance': 2e-5,
                                     'outside_tolerance': sum(e > 2e-5 for e in errors)}
            if invalid or any(e > 2e-5 for e in errors):
                findings.append({'code': 'depth_conversion_mismatch', 'nonfinite_pairs': invalid,
                                 'outside_tolerance': sum(e > 2e-5 for e in errors)})
    if 's2' in textures and 's5' in textures:
        _, hdr = textures['s2']
        _, adaptation = textures['s5']
        red = [p[0] for p in adaptation]
        invalid = sum(not math.isfinite(v) or v <= 0 for v in red)
        row = {'adaptation_red': stats(red), 'nonpositive_or_nonfinite': invalid}
        if invalid:
            row['status'] = 'invalid_adaptation_samples'
            findings.append({'code': 'nonpositive_or_nonfinite_adaptation', 'samples': invalid})
        elif len(hdr[0]) < 3:
            row['status'] = 'hdr_has_no_rgb_channels'
        elif min(red) != max(red):
            row['status'] = 'spatially_varying_adaptation'
            # Sampling grids do not reproduce D3D filtering across differently
            # sized textures; do not invent per-pixel ratios from their medians.
        else:
            row['status'] = 'uniform_sampled_adaptation'
            row['hdr_divided_by_adaptation_times_0_06'] = [
                stats([p[channel] / red[0] * .06 for p in hdr]) for channel in range(3)]
            row['meaning'] = 'Observed iCEnhancer intermediate only; later effect math and filtering are not evaluated.'
        result['hdr_adaptation'] = row
    if 'composite' in textures:
        _, pixels = textures['composite']
        rgb = [value for p in pixels for value in p[:3]]
        result['composite_channels'] = stats(rgb)
        if any(not math.isfinite(v) for v in rgb):
            findings.append({'code': 'nonfinite_composite_samples'})
        elif all(v == 0 for v in rgb):
            findings.append({'code': 'all_sampled_composite_channels_zero'})
    return result


def report(directory):
    directory = Path(directory)
    result = raw_report(directory)
    if not result['captures']:
        raise ValueError('No numbered capture directories found; an armed request alone is not a capture')
    result['interpretation'] = 'Offline numeric checks; rendering correctness and darkening cause remain unverified.'
    for name, row in result['captures'].items():
        sample = directory / name
        values = constants(row.get('inputs', ''))
        textures = {p.stem: decode(p.read_bytes()) for p in sorted(sample.glob('*.pfx'))}
        row['analysis'] = analyze(values, textures)
        # JSON has no nonfinite numbers; keep those measurements visible as
        # strings here and as counted faults in the numeric analysis.
        row['constants'] = {key: [v if math.isfinite(v) else str(v) for v in data] for key, data in values.items()}
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
