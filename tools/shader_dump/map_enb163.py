"""Scan actual ENB 0.163 hashes against shaderinput names and postfx routing.

Reads .fxc containers only; never loads D3D9 or starts the game. Runtime code
may change shader bytes before ENB receives them, so matches are static evidence.
"""

import argparse
import hashlib
import json
from pathlib import Path

import d3d9bc
from decode_enb163 import INPUT_SHA256
from enb163_hash import filename, hashed_length, shader_hash

# Recovered comparison chain at RVA 0x6A1C..0x6A4A, common call RVA 0x6A66.
POSTFX_HASHES = {0x7BC57CE4, 0x7D9A776E, 0xB2497014, 0xC50103F3, 0xAA1C0C36, 0xC215BE6E}


def scan(source, preset):
    source, preset = Path(source), Path(preset)
    targets = {p.name.lower(): [] for p in preset.glob("*sh*.txt")}
    postfx, containers, count = [], [], 0
    for path in sorted(source.rglob("*.fxc")):
        data = path.read_bytes()
        blobs = d3d9bc.extract(data)
        rel = path.relative_to(source).as_posix()
        containers.append({"file": rel, "sha256": hashlib.sha256(data).hexdigest(), "shaders": len(blobs)})
        for index, shader in enumerate(blobs):
            count += 1
            name = filename(shader.data, shader.stage)
            row = {"file": rel, "index": index, "stage": shader.stage,
                   "enb_hash": f"{shader_hash(shader.data):08X}",
                   "size": len(shader.data), "hashed_bytes": hashed_length(shader.data),
                   "shader_sha256": hashlib.sha256(shader.data).hexdigest()}
            if name.lower() in targets:
                targets[name.lower()].append(row)
            if shader.stage == "ps" and shader_hash(shader.data) in POSTFX_HASHES:
                postfx.append(row)
    return {"enb_wrapper_sha256": INPUT_SHA256, "method": "raw container bytes; not runtime capture",
            "containers": containers, "shader_count": count,
            "postfx_recognized_hashes": [f"{h:08X}" for h in sorted(POSTFX_HASHES)],
            "postfx_matches": postfx, "shaderinput_matches": targets,
            "runtime_verified": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path)
    ap.add_argument("--preset", type=Path, required=True, help="shaderinput folder")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = scan(args.source, args.preset)
    with args.out.open("x", encoding="utf-8") as out:
        out.write(json.dumps(report, indent=2) + "\n")
    print(f"Scanned {report['shader_count']} shaders; {sum(bool(v) for v in report['shaderinput_matches'].values())} preset filenames matched; {len(report['postfx_matches'])} postfx matches")


if __name__ == "__main__":
    main()
