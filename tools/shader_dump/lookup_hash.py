"""Look up runtime shader hashes in a dumped shader set.

    python lookup_hash.py <set.json> [HASH ...]
    python lookup_hash.py <set.json> --trace <d3d9_trace.log>

The in-game tracer logs shader binds by the comment-stripped CRC32 of the
bytecode each shader was created from -- the same hash ``dump_fxc.py`` records --
so a bind can be traced straight back to a container and index.

With ``--trace`` it reads a trace log, pulls every hash out of it, and reports
them in the order they were first bound. That is how you find out which of a
container's compiled variants a particular pass actually uses, which matters
because a hash-matching tool like ENBSeries can only ever replace one of them.
"""

import argparse
import collections
import json
import re
import sys

HASH_RE = re.compile(r"\b(?:ps|vs)=([0-9A-F]{8})\b|SetPixelShader ([0-9A-F]{8})")


def load(path):
    with open(path, encoding="utf-8") as fh:
        index = json.load(fh)
    table = collections.defaultdict(list)
    for rec in index["shaders"]:
        table[rec["hashes"]["crc32_stripped"]].append(rec)
    return index, table


def describe(table, value):
    recs = table.get(value)
    if not recs:
        return "not in this set"
    where = ", ".join("%s#%d" % (r["container"], r["index"]) for r in recs[:4])
    if len(recs) > 4:
        where += " ... (%d places)" % len(recs)
    return "%s  %s, %d instr" % (where, recs[0]["model"], recs[0]["instructions"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("set_json")
    ap.add_argument("hashes", nargs="*", help="hashes to look up, e.g. 1A2B3C4D")
    ap.add_argument("--trace", help="read hashes out of a d3d9_trace.log instead")
    args = ap.parse_args(argv)

    index, table = load(args.set_json)
    print("set: %s (%d shaders, %d distinct bytecodes)\n"
          % (index["label"], len(index["shaders"]), len(table)))

    wanted = [h.upper() for h in args.hashes]
    if args.trace:
        seen = []
        with open(args.trace, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                for a, b in HASH_RE.findall(line):
                    value = a or b
                    if value and value not in seen:
                        seen.append(value)
        wanted.extend(h for h in seen if h not in wanted)

    if not wanted:
        print("no hashes given")
        return 1

    for value in wanted:
        print("  %s  %s" % (value, describe(table, value)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
