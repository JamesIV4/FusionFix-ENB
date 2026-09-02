"""Rewrite a RAGE ``.fxc`` so several shader slots carry the same bytecode.

    python splice_fxc.py <in.fxc> <out.fxc> --source 13 --targets 15 17 19
    python splice_fxc.py <in.fxc> --list

Why this exists
---------------
ENBSeries recognises a game shader by hashing its bytecode, and it has exactly
one hash per shader it replaces. GTA IV's ``rage_postfx.fxc`` holds 28 passes,
and the final composite exists as four near-identical variants -- they differ
only in whether near-field depth of field is computed and in one conditional
select. The game picks between them per scene, so ENB's single hash matches in
some scenes and not others, and where it does not match the game's own tone
mapping runs while ENB still stacks its bloom and adaptation on top.

Pointing the other variants at the same bytecode as the one ENB recognises
makes the substitution fire everywhere. What the game loses is real but small,
and mostly moot: ENB replaces the shader with its own code anyway, so the
distinction between the variants stops mattering the moment it matches.

Container format
----------------
``rgxa``, a u16, then a flat sequence of ``[u16 size][u16 size][bytecode]``.
There is no offset table -- the trailing records are fixed-size and hold no
offsets -- so a slot can be replaced with a blob of a different size as long as
both size fields are rewritten. Verified against CE 1.2.0.59: all 30 blobs in
``rage_postfx.fxc`` have headers matching their measured length.

Nothing is written in place; give an output path.
"""

import argparse
import os
import struct
import sys

import d3d9bc


def blob_header(data, offset):
    """The two u16 size fields immediately before a blob, or None."""
    if offset < 4:
        return None
    a, b = struct.unpack_from("<HH", data, offset - 4)
    return a, b


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source_fxc")
    ap.add_argument("out_fxc", nargs="?")
    ap.add_argument("--list", action="store_true", help="list the slots and exit")
    ap.add_argument("--source", type=int, help="slot whose bytecode should be copied")
    ap.add_argument("--targets", type=int, nargs="+", help="slots to overwrite with it")
    args = ap.parse_args(argv)

    with open(args.source_fxc, "rb") as fh:
        data = fh.read()

    shaders = d3d9bc.extract(data, os.path.basename(args.source_fxc))

    if args.list:
        print("%s: %d shader slots" % (os.path.basename(args.source_fxc), len(shaders)))
        for i, s in enumerate(shaders):
            head = blob_header(data, s.offset)
            flag = "" if head == (s.size, s.size) else "   HEADER MISMATCH %s" % (head,)
            print("  #%-3d %-8s offset %6d  size %5d  %4d instr  crc %s%s"
                  % (i, s.model, s.offset, s.size, len(s.opcodes()),
                     s.hashes()["crc32_stripped"], flag))
        return 0

    if args.source is None or not args.targets or not args.out_fxc:
        ap.error("--source, --targets and an output path are required unless --list")

    for i, s in enumerate(shaders):
        if blob_header(data, s.offset) != (s.size, s.size):
            print("slot #%d has an unexpected size header; refusing to splice" % i)
            return 1

    if not 0 <= args.source < len(shaders):
        print("source slot %d out of range (0..%d)" % (args.source, len(shaders) - 1))
        return 1

    src = shaders[args.source]
    targets = sorted(set(args.targets))
    for t in targets:
        if not 0 <= t < len(shaders):
            print("target slot %d out of range" % t)
            return 1
        if shaders[t].model != src.model:
            print("slot #%d is %s but the source is %s; refusing to splice"
                  % (t, shaders[t].model, src.model))
            return 1
        if t == args.source:
            print("slot #%d is the source; skipping" % t)

    # Rebuild the file in one pass, replacing each target's header and blob.
    # Working back to front would also work, but a single forward pass keeps
    # every unrelated byte -- including the trailing records -- exactly as it
    # was, which is what makes this safe without understanding the whole format.
    out = bytearray()
    cursor = 0
    replaced = 0
    for i, s in enumerate(shaders):
        if i not in targets or i == args.source:
            continue
        out += data[cursor:s.offset - 4]
        out += struct.pack("<HH", src.size, src.size)
        out += src.data
        cursor = s.offset + s.size
        replaced += 1
    out += data[cursor:]

    with open(args.out_fxc, "wb") as fh:
        fh.write(out)

    print("wrote %s" % args.out_fxc)
    print("  source slot #%d (%s, %d bytes, crc %s)"
          % (args.source, src.model, src.size, src.hashes()["crc32_stripped"]))
    print("  replaced %d slot(s): %s" % (replaced, ", ".join("#%d" % t for t in targets)))
    print("  size %d -> %d bytes" % (len(data), len(out)))

    # Re-parse the result: if the sizes were rewritten correctly the extractor
    # finds the same number of slots and the targets now carry the source hash.
    with open(args.out_fxc, "rb") as fh:
        check = d3d9bc.extract(fh.read())
    print("  verify: %d slots after splice (was %d)" % (len(check), len(shaders)))
    want = src.hashes()["crc32_stripped"]
    for t in targets:
        if t >= len(check):
            print("  verify: slot #%d missing" % t)
            continue
        got = check[t].hashes()["crc32_stripped"]
        print("  verify: #%-3d crc %s  %s" % (t, got, "OK" if got == want else "MISMATCH"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
