"""Stage experimental ENB filename aliases; never install or launch anything.

Default: three terrain candidates whose normalized instruction bodies match.
The contract pins actual stock CE bytecode SHA256 values: modern FusionFix or
different shader variants are rejected, rather than silently given unsafe aliases.
The mapping of each legacy filename to a CE role remains a static inference.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re

import d3d9bc
from enb163_hash import filename

DEFAULT_CONTRACT = Path(__file__).resolve().parents[2] / "research/contracts/ce-shader-aliases.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def leaf(value):
    if not value or Path(value).name != value or ":" in value or "\\" in value:
        raise ValueError(f"Expected a leaf filename: {value}")
    return value


def stage(source, preset, contract, groups, output, probe=False):
    source, preset, output = (Path(p).resolve() for p in (source, preset, output))
    if output.exists():
        raise ValueError("Output must be a new directory")
    if any(output == p or output.is_relative_to(p) for p in (source, preset)):
        raise ValueError("Output must be separate from shader and preset inputs")
    if any((p / "GTAIV.exe").exists() for p in (output, *output.parents)):
        raise ValueError("Stage outside the installed game; this tool does not install")
    known = {entry["group"] for entry in contract["entries"]}
    if not set(groups) <= known:
        raise ValueError("Unknown selection group")
    selected = [e for e in contract["entries"] if e["group"] in groups]
    if not selected:
        raise ValueError("No mappings selected")
    if probe and set(groups) != {"terrain"}:
        raise ValueError("The color probe is limited to the audited terrain group")
    files, mappings = {}, []
    for entry in selected:
        container = leaf(entry["container"])
        shaders = d3d9bc.extract_file(source / container)
        shader = shaders[entry["index"]]
        if shader.stage != entry["stage"] or sha(shader.data) != entry["shader_sha256"]:
            raise ValueError(f"Stock shader identity mismatch: {container}#{entry['index']}")
        original = leaf(entry["preset_file"])
        replacement = (preset / original).read_bytes()
        if sha(replacement) != entry["replacement_sha256"]:
            raise ValueError(f"Preset file differs from researched iCEnhancer input: {original}")
        if probe:
            # These three audited terrain programs write diffuse RGB to oC0.
            # Keep alpha and other GBuffer outputs; use an otherwise unused def.
            text = replacement.decode("utf-8")
            if re.search(r"\bc223\b", text, re.I):
                raise ValueError("Probe constant is already used")
            text, edits = re.subn(r"(?m)^(\s*ps_3_0)[ \t]*\r?$",
                                  r"\1\n    def c223, 1, 0, 1, 1", text, count=1)
            if edits != 1 or entry["stage"] != "ps":
                raise ValueError("Expected a terrain ps_3_0 program")
            replacement = (text + "\n// ENBCOMPAT PROBE: force terrain diffuse magenta\n"
                           "    mov oC0.xyz, c223\n").encode("utf-8")
        alias = filename(shader.data, shader.stage)
        if alias in files and files[alias] != replacement:
            raise ValueError(f"Conflicting replacements for {alias}")
        files[alias] = replacement
        mappings.append({**entry, "alias": alias, "source_container_sha256": sha((source / container).read_bytes()),
                         "output_sha256": sha(replacement),
                         "runtime_substitution_verified": False})
    # Detect all shader identities reached by each 32-bit alias, including
    # legitimate duplicate blobs in other containers and unexpected collisions.
    occurrences = {name: [] for name in files}
    expected = {m["alias"]: m["shader_sha256"] for m in mappings}
    for path in sorted(source.glob("*.fxc")):
        for index, shader in enumerate(d3d9bc.extract_file(path)):
            name = filename(shader.data, shader.stage)
            if name in files:
                if sha(shader.data) != expected[name]:
                    raise ValueError(f"Alias hash collision with different bytecode: {path.name}#{index}")
                occurrences[name].append({"container": path.name, "index": index})
    report = {"format": 1, "experimental": True, "rendering_validated": False,
              "probe": "terrain_diffuse_magenta" if probe else None,
              "hash_algorithm": "enb163_raw_crc32_no_final_xor_before_first_aligned_END",
              "groups": sorted(groups), "mapping_evidence": contract["mapping_evidence"],
              "mappings": mappings, "affected_slots": occurrences,
              "excluded_preset_files": sorted(p.name for p in preset.glob("*sh*.txt")
                                              if p.name not in {e["preset_file"] for e in selected}),
              "game_modified": False}
    output.mkdir(parents=True)
    (output / "shaderinput").mkdir()
    for name, data in sorted(files.items()):
        (output / "shaderinput" / name).write_bytes(data)
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shaders", type=Path, required=True, help="stock CE win32_30 folder")
    ap.add_argument("--preset", type=Path, required=True, help="iCEnhancer shaderinput folder")
    ap.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    ap.add_argument("--group", action="append", choices=["terrain", "candidate"],
                    help="repeat to combine; default terrain only")
    ap.add_argument("--out", type=Path, required=True, help="new directory outside game")
    ap.add_argument("--probe", action="store_true", help="terrain only: force diffuse RGB magenta for identification")
    args = ap.parse_args()
    report = stage(args.shaders, args.preset, json.loads(args.contract.read_text(encoding="utf-8")),
                   args.group or ["terrain"], args.out, probe=args.probe)
    print(f"Staged {len(report['mappings'])} experimental aliases -> {args.out}; no game files changed")


if __name__ == "__main__":
    main()
