"""Identify which game shader each ENB ``shaderinput`` file replaces.

    python match_enb.py <enb-shaderinput-dir> <set.json> [--top 3] [--json out.json]

ENBSeries recognises a game shader by hashing its bytecode and, on a match,
substitutes the assembly in ``shaderinput/psh<HASH>.txt`` (or ``vsh<HASH>.txt``).
The hash function is internal to the closed-source binary, but the substitute
assembly is the *original shader with ENB's edits spliced in*, so the original
can be recovered by similarity instead: strip both sides down to their
instruction lines, drop ``def`` (which is exactly what both ENB and FusionFix
rewrite), and look for the game shader whose body is closest to a subsequence
of the ENB file.

``<set.json>`` must come from ``dump_fxc.py --asm``, since the comparison runs
on disassembly.

The result is the ENB-hash to game-shader mapping needed before any claim about
which render pass an ENB preset is actually changing.
"""

import argparse
import difflib
import json
import os
import re
import sys

import d3d9bc

NAME_RE = re.compile(r"^(psh|vsh)([0-9A-Fa-f]{8})\.txt$")


def load_enb(directory):
    out = []
    for name in sorted(os.listdir(directory)):
        m = NAME_RE.match(name)
        if not m:
            continue
        with open(os.path.join(directory, name), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        inputs, samplers = d3d9bc.declarations(text)
        out.append({
            "file": name,
            "stage": "ps" if m.group(1) == "psh" else "vs",
            "hash": m.group(2).upper(),
            "lines": d3d9bc.normalise_asm(text),
            "inputs": inputs,
            "samplers": samplers,
        })
    return out


def compatible(enb, inputs, samplers):
    """Could this game shader be the one the ENB file replaces?

    ENB edits a shader in place: it may add a sampler for its own textures, but
    it does not change what the shader receives from the vertex stage. So the
    inputs have to match exactly and the game's samplers have to be a subset of
    the ENB file's.
    """
    return inputs == enb["inputs"] and samplers <= enb["samplers"]


def score(enb_lines, game_lines):
    """Score a candidate pairing, returning (similarity, coverage).

    ENB only ever inserts into the original, so a correct pairing keeps nearly
    all of the original's instruction lines -- that is ``coverage``. Coverage
    alone rewards any short shader that happens to be swallowed by a long ENB
    file, so ranking uses the symmetric ``similarity`` (matched lines over the
    combined length), which penalises a length mismatch in either direction.
    """
    if not game_lines or not enb_lines:
        return 0.0, 0.0
    matcher = difflib.SequenceMatcher(None, game_lines, enb_lines, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    similarity = 2.0 * matched / float(len(game_lines) + len(enb_lines))
    return similarity, matched / float(len(game_lines))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("enb_dir", help="an ENB preset's shaderinput/ directory")
    ap.add_argument("set_json", help="index written by dump_fxc.py --asm")
    ap.add_argument("--top", type=int, default=3, help="candidates to print per ENB shader")
    ap.add_argument("--match-decls", action="store_true",
                    help="only consider shaders whose declaration signature is compatible: "
                         "identical inputs, samplers a subset of the ENB file's. Much stronger "
                         "than similarity alone when several shaders in a family do nearly the "
                         "same thing")
    ap.add_argument("--json", dest="out_json", default=None)
    args = ap.parse_args(argv)

    with open(args.set_json, encoding="utf-8") as fh:
        index = json.load(fh)
    asm_root = os.path.join(os.path.dirname(os.path.abspath(args.set_json)), index["label"])

    candidates = []
    for rec in index["shaders"]:
        if "asm" not in rec:
            continue
        with open(os.path.join(asm_root, rec["asm"]), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        inputs, samplers = d3d9bc.declarations(text)
        candidates.append((rec, d3d9bc.normalise_asm(text), inputs, samplers))
    if not candidates:
        print("no disassembly in %s -- re-run dump_fxc.py with --asm" % args.set_json)
        return 1

    results = []
    for enb in load_enb(args.enb_dir):
        pool = [(r, l, i, s) for r, l, i, s in candidates if r["stage"] == enb["stage"]]
        if args.match_decls:
            filtered = [(r, l) for r, l, i, s in pool if compatible(enb, i, s)]
        else:
            filtered = [(r, l) for r, l, _, _ in pool]
        scored = [(score(enb["lines"], lines), rec) for rec, lines in filtered]
        ranked = sorted(scored, key=lambda t: t[0][0], reverse=True)[:args.top]
        results.append({
            "enb_file": enb["file"],
            "enb_hash": enb["hash"],
            "stage": enb["stage"],
            "enb_instructions": len(enb["lines"]),
            "declaration_matched": bool(args.match_decls),
            "pool_size": len(filtered),
            "candidates": [{"similarity": round(s, 4), "coverage": round(c, 4),
                            "name": r["name"], "container": r["container"],
                            "index": r["index"], "instructions": r["instructions"]}
                           for (s, c), r in ranked],
        })
        for n, ((s, c), r) in enumerate(ranked):
            head = "%-16s %-3s %4d/%-4d" % (enb["file"], enb["stage"],
                                            len(enb["lines"]), len(filtered)) if n == 0 \
                else "%-16s %-3s %9s" % ("", "", "")
            print("%s  sim %.3f  cov %.3f  %s (%s#%d, %d instr)"
                  % (head, s, c, r["name"], r["container"], r["index"], r["instructions"]))
        if not ranked:
            print("%-16s %-3s %4d/%-4d  no candidate with a matching declaration signature"
                  % (enb["file"], enb["stage"], len(enb["lines"]), len(filtered)))

    if args.out_json:
        os.makedirs(os.path.dirname(os.path.abspath(args.out_json)), exist_ok=True)
        with open(args.out_json, "w", encoding="utf-8") as fh:
            json.dump({"enb_dir": os.path.abspath(args.enb_dir),
                       "shader_set": index["label"], "matches": results}, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
