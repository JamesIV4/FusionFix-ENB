"""Compare two shader sets produced by ``dump_fxc.py``.

    python compare_sets.py <base.json> <other.json> [--json out.json]

Pairs shaders by (container, index) and reports, per container, how many blobs
are byte-identical once comment blocks are stripped. Any shader whose stripped
bytes changed has a different bytecode hash in the new set, so a tool that
recognises game shaders by hash -- ENBSeries does -- stops recognising it.

The summary line at the end is the number that matters: it is the size of the
set of shaders an old ENB preset can no longer match.
"""

import argparse
import json
import os
import sys
from collections import OrderedDict


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def key(rec):
    return (rec["container"], rec["index"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base")
    ap.add_argument("other")
    ap.add_argument("--json", dest="out_json", default=None)
    ap.add_argument("--quiet", action="store_true", help="summary only")
    args = ap.parse_args(argv)

    base, other = load(args.base), load(args.other)
    bmap = OrderedDict((key(r), r) for r in base["shaders"])
    omap = OrderedDict((key(r), r) for r in other["shaders"])

    containers = OrderedDict()
    for k, rec in bmap.items():
        containers.setdefault(k[0], {"same": 0, "changed": 0, "removed": 0, "added": 0,
                                     "changed_names": []})
        slot = containers[k[0]]
        peer = omap.get(k)
        if peer is None:
            slot["removed"] += 1
        elif peer["hashes"]["crc32_stripped"] == rec["hashes"]["crc32_stripped"]:
            slot["same"] += 1
        else:
            slot["changed"] += 1
            slot["changed_names"].append(rec["name"])
    for k, rec in omap.items():
        if k not in bmap:
            containers.setdefault(k[0], {"same": 0, "changed": 0, "removed": 0, "added": 0,
                                         "changed_names": []})
            containers[k[0]]["added"] += 1

    tot = {"same": 0, "changed": 0, "removed": 0, "added": 0}
    if not args.quiet:
        print("%-42s %6s %8s %8s %6s" % ("container", "same", "changed", "removed", "added"))
    for name, slot in containers.items():
        for f in tot:
            tot[f] += slot[f]
        if not args.quiet and (slot["changed"] or slot["removed"] or slot["added"]):
            print("%-42s %6d %8d %8d %6d"
                  % (name, slot["same"], slot["changed"], slot["removed"], slot["added"]))

    total = sum(tot.values())
    print("")
    print("%s -> %s" % (base["label"], other["label"]))
    print("  %d shaders compared" % total)
    print("  %d identical, %d changed, %d removed, %d added"
          % (tot["same"], tot["changed"], tot["removed"], tot["added"]))
    if total:
        print("  %.1f%% of shaders have a different bytecode hash in %s"
              % (100.0 * (tot["changed"] + tot["removed"] + tot["added"]) / total, other["label"]))

    if args.out_json:
        os.makedirs(os.path.dirname(os.path.abspath(args.out_json)), exist_ok=True)
        with open(args.out_json, "w", encoding="utf-8") as fh:
            json.dump({"base": base["label"], "other": other["label"],
                       "totals": tot, "containers": containers}, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
