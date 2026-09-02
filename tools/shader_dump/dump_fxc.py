"""Dump and fingerprint every shader in a set of RAGE ``.fxc`` containers.

    python dump_fxc.py <fxc-dir-or-file> --out <dir> [--label ce-vanilla] [--asm]

Writes ``<out>/<label>.json`` -- one record per shader blob with its container,
offset, model, size and hashes -- and, with ``--asm``, the ``.cso`` blob plus
its disassembly under ``<out>/<label>/``.

Produce one of these per configuration (vanilla CE, CE+FusionFix, an old 1.0.x
reference install) and feed them to ``compare_sets.py``; that pair of steps is
the static half of the shader fingerprinting described in the project plan.
"""

import argparse
import json
import os
import subprocess
import sys

import d3d9bc

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FXC = os.path.normpath(os.path.join(HERE, "..", "..", "source", "dxsdk", "lib", "x86", "fxc.exe"))


def disassemble(fxc_exe, cso_path):
    """Run ``fxc /dumpbin`` and return the assembly text, or None."""
    try:
        res = subprocess.run(
            [fxc_exe, "/nologo", "/dumpbin", cso_path],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return res.stdout


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="directory of .fxc files, or a single .fxc")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--label", default=None, help="name for this shader set (default: source dir name)")
    ap.add_argument("--asm", action="store_true", help="also write .cso blobs and disassembly")
    ap.add_argument("--fxc", default=DEFAULT_FXC, help="path to fxc.exe (for --asm)")
    args = ap.parse_args(argv)

    label = args.label or os.path.basename(os.path.normpath(args.source))
    os.makedirs(args.out, exist_ok=True)
    asm_dir = os.path.join(args.out, label)
    if args.asm:
        os.makedirs(asm_dir, exist_ok=True)

    records = []
    containers = 0
    for path in d3d9bc.iter_fxc(args.source):
        containers += 1
        rel = os.path.relpath(path, args.source if os.path.isdir(args.source) else os.path.dirname(args.source))
        for index, shader in enumerate(d3d9bc.extract_file(path)):
            name = "%s_%03d_%s" % (os.path.splitext(os.path.basename(path))[0], index, shader.model)
            rec = {
                "name": name,
                "container": rel.replace("\\", "/"),
                "index": index,
                "model": shader.model,
                "stage": shader.stage,
                "offset": shader.offset,
                "size": shader.size,
                "instructions": len(shader.opcodes()),
                "hashes": shader.hashes(),
            }
            if args.asm:
                cso = os.path.join(asm_dir, name + ".cso")
                with open(cso, "wb") as fh:
                    fh.write(shader.data)
                text = disassemble(args.fxc, cso)
                if text is not None:
                    with open(os.path.join(asm_dir, name + ".asm"), "w", encoding="utf-8") as fh:
                        fh.write(text)
                    rec["asm"] = name + ".asm"
            records.append(rec)

    index_path = os.path.join(args.out, label + ".json")
    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump({"label": label, "source": os.path.abspath(args.source),
                   "containers": containers, "shaders": records}, fh, indent=2)

    ps = sum(1 for r in records if r["stage"] == "ps")
    print("%s: %d containers, %d shaders (%d ps / %d vs) -> %s"
          % (label, containers, len(records), ps, len(records) - ps, index_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
