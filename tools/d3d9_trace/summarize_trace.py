"""Summarise a d3d9_trace.log written by the in-game tracer.

    python summarize_trace.py <ENBCompat/d3d9_trace.log> [--frame N]

Turns the raw call log into the shape the investigation actually asks
questions of: which render targets and depth surfaces exist, which sampler
stages get bound, which constant registers get written, and how that differs
between frames. Pass ``--frame`` to restrict to one frame.

Pair with ``compare_traces.py`` to diff two configurations.
"""

import argparse
import collections
import re
import sys

LINE_RE = re.compile(r"^\[(\d+)\]\s+(.*)$")


def parse(path):
    """Yield (frame, call, rest) for each trace line."""
    # utf-8-sig: the tracer writes no BOM, but a log that has been through an
    # editor may have picked one up, and a BOM silently breaks the first line.
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            m = LINE_RE.match(line.rstrip("\n"))
            if not m:
                continue
            frame = int(m.group(1))
            body = m.group(2)
            parts = body.split(None, 1)
            yield frame, parts[0], (parts[1] if len(parts) > 1 else "")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--frame", type=int, default=None, help="only this frame")
    args = ap.parse_args(argv)

    calls = collections.Counter()
    render_targets = collections.Counter()
    depth_targets = collections.Counter()
    created = collections.Counter()
    stages = collections.Counter()
    frames = set()

    for frame, call, rest in parse(args.log):
        if args.frame is not None and frame != args.frame:
            continue
        frames.add(frame)
        calls[call] += 1
        if call == "SetRenderTarget":
            render_targets[rest] += 1
        elif call == "SetDepthStencilSurface":
            depth_targets[rest] += 1
        elif call.startswith("Create"):
            created["%s %s" % (call, rest)] += 1
        elif call == "SetTexture":
            stages[rest.split(None, 1)[0]] += 1

    if not frames:
        print("no trace lines found in %s" % args.log)
        return 1

    print("frames %d..%d  (%d distinct)" % (min(frames), max(frames), len(frames)))

    def section(title, counter, limit=40):
        if not counter:
            return
        print("\n%s" % title)
        for name, count in counter.most_common(limit):
            print("  %7d  %s" % (count, name))
        if len(counter) > limit:
            print("  ... and %d more" % (len(counter) - limit))

    section("calls", calls)
    section("render targets bound (index + surface)", render_targets)
    section("depth surfaces bound", depth_targets)
    section("resources created", created)
    section("sampler stages bound", stages)
    return 0


if __name__ == "__main__":
    sys.exit(main())
