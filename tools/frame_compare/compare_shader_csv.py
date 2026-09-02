"""Diff the shaders.csv files two configurations produced at runtime.

    python compare_shader_csv.py <a/shaders.csv> <b/shaders.csv> [--label-a ..] [--label-b ..]

The in-game tracer writes one row per distinct shader the game creates, with
both the raw and comment-stripped CRC32 of its bytecode. Comparing two runs
answers the question that matters for ENB compatibility directly: how many of
the shaders present in configuration A still have the same bytecode -- and so
the same hash, and so still match an ENB ``shaderinput`` file -- in B.

Typical pairs:
    CE stock  vs  CE + FusionFix                 (what FusionFix changes)
    CE stock  vs  old 1.0.x reference install    (what Complete Edition changed)
"""

import argparse
import csv
import sys


def load(path):
    rows = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            rows[row["crc32_stripped"]] = row
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    args = ap.parse_args(argv)

    a, b = load(args.a), load(args.b)
    shared = set(a) & set(b)
    only_a = set(a) - set(b)
    only_b = set(b) - set(a)

    def fusion_count(rows, keys):
        return sum(1 for k in keys if rows[k].get("fusion_signature") == "1")

    print("%s: %d distinct shaders (%d carry the FusionShader marker)"
          % (args.label_a, len(a), fusion_count(a, a)))
    print("%s: %d distinct shaders (%d carry the FusionShader marker)"
          % (args.label_b, len(b), fusion_count(b, b)))
    print("")
    print("  %d shared (identical bytecode -- an ENB hash match survives)" % len(shared))
    print("  %d only in %s" % (len(only_a), args.label_a))
    print("  %d only in %s" % (len(only_b), args.label_b))
    if a:
        print("  %.1f%% of %s's shaders survive unchanged into %s"
              % (100.0 * len(shared) / len(a), args.label_a, args.label_b))
    return 0


if __name__ == "__main__":
    sys.exit(main())
