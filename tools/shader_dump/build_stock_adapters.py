"""Build reviewed iCEnhancer deltas using exact 1.0.4.0 shader identities.

Targets only original Complete Edition programs and their native interfaces.
The recipe pins source programs, exports, preset files and a complete stock
variant. Unreviewed entries stay pending. No game files are installed and no
graphics device is created.
"""
import argparse
import json
from pathlib import Path
import re
import tempfile

from audit_shader_pair import audit, read_export
from shader_edits import assembly_at, assemble, instructions, verify_unchanged_tokens
import d3d9bc
from enb163_hash import filename
from shader_files import leaf, sha

ROOT = Path(__file__).resolve().parents[2]
RECIPES = ROOT / "research/contracts/stock-ce-adapters.json"


def apply_edits(text, edits):
    """Exact, unique instruction blocks; never a fuzzy patch or register replace."""
    rows = instructions(text)
    for edit in edits:
        before, after = edit["before"], edit["after"]
        if not before or instructions("\n".join(before)) != before or instructions("\n".join(after)) != after:
            raise ValueError("Edits must contain normalized instructions and a nonempty anchor")
        matches = [i for i in range(len(rows) - len(before) + 1)
                   if rows[i:i + len(before)] == before]
        if len(matches) != 1:
            raise ValueError("Expected one exact edit anchor")
        at = matches[0]
        rows[at:at + len(before)] = after
    return "\n".join(rows) + "\n"


def verify_variant(corpus, expected):
    paths = {p.name: p for p in corpus.glob("*.fxc")}
    if set(paths) != set(expected):
        raise ValueError("Stock corpus is incomplete or has extra containers")
    for name, digest in expected.items():
        raw = paths[name].read_bytes()
        if b"FusionShader" in raw:
            raise ValueError("FusionFix shader bytecode is forbidden in the stock corpus")
        if sha(raw) != digest:
            raise ValueError(f"Stock corpus changed: {name}")
    return paths


def collision_scan(paths, outputs):
    affected = {name: [] for name in outputs}
    for path in sorted(paths.values()):
        for slot, shader in enumerate(d3d9bc.extract_file(path)):
            name = filename(shader.data, shader.stage)
            if name in outputs:
                if sha(shader.data) != outputs[name]["original_sha256"]:
                    raise ValueError(f"Stock alias collision: {name}")
                affected[name].append({"container": path.name, "slot": slot})
    if any(not slots for slots in affected.values()):
        raise ValueError("Generated alias has no target in the stock corpus")
    return affected


def check_exports(directory, expected):
    for name, digest in expected.items():
        if sha((directory / leaf(name)).read_bytes()) != digest:
            raise ValueError(f"Export identity changed: {name}")


def verify_fixture(relative, text):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT / "tools/shader_dump/fixtures"):
        raise ValueError("Validation fixture must be inside the shader fixtures directory")
    if instructions(path.read_text(encoding="utf-8")) != instructions(text):
        raise ValueError("Validated arithmetic fixture differs from the actual shader source")


def free_registers(text, constants, temporaries, samplers):
    """Reject collisions before injecting the preset's scratch registers."""
    code = "\n".join(instructions(text))
    if constants and re.search(r"\bc\d*\[", code):
        raise ValueError("Relative constant reads cannot prove scratch registers are free")
    for prefix, numbers in (("c", constants), ("r", temporaries), ("s", samplers)):
        for number in numbers:
            if re.search(rf"\b{prefix}{number}(?![A-Za-z0-9])", code):
                raise ValueError(f"Preset register is already used: {prefix}{number}")


def build(legacy, stock, preset, corpus, assembler, output, contract):
    legacy, stock, preset, corpus, assembler, output = [Path(p).resolve() for p in
        (legacy, stock, preset, corpus, assembler, output)]
    if output.exists() or any(output.is_relative_to(p) or p.is_relative_to(output)
                              for p in (legacy, stock, preset, corpus)):
        raise ValueError("Output must be new and separate from inputs")
    if any((p / "GTAIV.exe").exists() for p in (output, *output.parents)):
        raise ValueError("Build outside the game directory")
    if contract.get("format") != 1:
        raise ValueError("Unsupported recipe format")
    entries = contract["entries"]
    names = [leaf(e["preset_file"]) for e in entries]
    if len(set(names)) != len(names) or set(names) != {p.name for p in preset.glob("[pv]sh*.txt")}:
        raise ValueError("Recipe must account for every preset input exactly once")
    paths = verify_variant(corpus, contract["stock_corpus"])
    check_exports(legacy, contract["legacy_exports"])
    check_exports(stock, contract["stock_exports"])
    outputs, reports = {}, []
    with tempfile.TemporaryDirectory(prefix="enb-preset-") as scratch:
        work = Path(scratch)
        for entry in entries:
            name = entry["preset_file"]
            replacement = (preset / name).read_bytes()
            if sha(replacement) != entry["preset_sha256"]:
                raise ValueError(f"Preset changed: {name}")
            preset_asm = replacement.decode("utf-8-sig")
            if entry.get("validation_preset_fixture"):
                verify_fixture(entry["validation_preset_fixture"], preset_asm)
            preset_blob = assemble(assembler, preset_asm, work, name + "-preset")
            row = {"preset_file": name, "preset_sha256": entry["preset_sha256"],
                   "status": entry["status"], "reason": entry["reason"], "sources": [], "targets": []}
            if "translation" in entry:
                row["translation"] = entry["translation"]
            for source in entry["sources"]:
                container, slot = leaf(source["container"]), source["slot"]
                original = d3d9bc.extract_file(legacy / container)[slot]
                if sha(original.data) != source["sha256"] or filename(original.data, original.stage) != name:
                    raise ValueError(f"Original 1.0.4.0 identity changed: {name}")
                text = assembly_at(legacy / (container + ".xml"), slot)
                stem = f"{name}-{container}-{slot}"
                compiled = assemble(assembler, text.replace("\0", ""), work, stem + "-original")
                if compiled.stripped() != original.stripped():
                    raise ValueError("Legacy export does not reproduce the original program")
                translated = apply_edits(text, entry["legacy_edits"])
                proof = assemble(assembler, translated, work, stem + "-legacy-delta")
                if proof.stripped() != preset_blob.stripped():
                    raise ValueError(f"Reviewed delta does not cover the entire preset program: {name}")
                mapping = audit(read_export(legacy / (container + ".xml")),
                                read_export(stock / (container + ".xml")), [slot])["entries"][0]
                if not mapping["mapping_unambiguous"]:
                    raise ValueError(f"Ambiguous named-pass mapping: {name}")
                row["sources"].append({**source, "interface_audit": mapping})
            if not row["sources"]:
                raise ValueError("Recipe has no original reference")
            if entry["status"] == "no_preset_delta":
                if entry["legacy_edits"] or entry["targets"]:
                    raise ValueError("An unchanged preset must not install an alias")
            elif entry["status"] == "pending_translation":
                if entry["targets"]:
                    raise ValueError("Pending translations cannot publish aliases")
            elif entry["status"] == "built_offline":
                if not entry["targets"]:
                    raise ValueError("Adapter has no stock target")
                mapped = {(s["container"], c["target_slot"]) for s in row["sources"]
                          for c in s["interface_audit"]["candidates"]}
                supplied = {(t["container"], t["slot"]) for t in entry["targets"] if not t.get("paired_stage")}
                if supplied != mapped:
                    raise ValueError("Recipe does not cover all mapped stock programs")
                for target in entry["targets"]:
                    container, slot = leaf(target["container"]), target["slot"]
                    if sha((stock / container).read_bytes()) != contract["stock_corpus"][container]:
                        raise ValueError("Stock export and full corpus differ")
                    original = d3d9bc.extract_file(stock / container)[slot]
                    if sha(original.data) != target["sha256"]:
                        raise ValueError("Stock target program changed")
                    export = read_export(stock / (container + ".xml"))
                    roles = [role for role, p in export["passes"].items() if p[original.stage] == slot]
                    if roles != target["roles"]:
                        raise ValueError("Stock target roles changed")
                    if target.get("paired_stage"):
                        pixel_slots = {export["passes"][role]["ps"] for role in roles}
                        if original.stage != "vs" or not pixel_slots or not all((container, p) in supplied for p in pixel_slots):
                            raise ValueError("Paired vertex shader affects an unadapted pass")
                    text = assembly_at(stock / (container + ".xml"), slot)
                    if target.get("validation_stock_fixture"):
                        verify_fixture(target["validation_stock_fixture"], text)
                    stem = f"{name}-{container}-{slot}"
                    free_registers(text, **target.get("scratch", {"constants": [], "temporaries": [], "samplers": []}))
                    compiled = assemble(assembler, text.replace("\0", ""), work, stem + "-stock")
                    if compiled.stripped() != original.stripped():
                        raise ValueError("Stock export does not reproduce the original program")
                    adapted_text = apply_edits(text, target["edits"])
                    adapted = assemble(assembler, adapted_text, work, stem + "-adapted")
                    verify_unchanged_tokens(text, adapted_text, original, adapted, target["edits"])
                    if target.get("require_preset_program") and adapted.stripped() != preset_blob.stripped():
                        raise ValueError("Generated program is not exactly the original preset program")
                    if adapted.stage != original.stage or sha(adapted.data) != target["adapted_sha256"]:
                        raise ValueError("Adapted bytecode differs from the reviewed output")
                    alias = filename(original.data, original.stage)
                    if alias != target["stock_alias"] or sha(adapted_text.encode("utf-8")) != target["assembly_sha256"]:
                        raise ValueError("Stock alias identity or exact assembly bytes changed")
                    item = {"assembly": adapted_text, "binary": adapted.data, "original_sha256": sha(original.data)}
                    if alias in outputs and outputs[alias] != item:
                        raise ValueError(f"Conflicting aliases: {alias}")
                    outputs[alias] = item
                    row["targets"].append({"container": container, "slot": slot, "roles": roles,
                        "stage": original.stage, "alias": alias, "stock_sha256": sha(original.data),
                        "adapted_sha256": sha(adapted.data), "assembly_sha256": sha(adapted_text.encode("utf-8")),
                        "exact_preset_program": adapted.stripped() == preset_blob.stripped(),
                        "unedited_ce_instructions_byte_identical": True,
                        "paired_stage": target.get("paired_stage", False),
                        "edits": target["edits"]})
            else:
                raise ValueError("Unknown recipe status")
            reports.append(row)
        affected = collision_scan(paths, outputs)
        report = {"format": 1, "backend": "exact_1040_to_stock_ce_delta", "game_modified": False,
                  "rendering_validated": False, "requires": contract["requires"],
                  "stock_corpus": contract["stock_corpus"],
                  "collision_scan_containers": len(paths), "affected_slots": affected, "entries": reports}
        # All verification precedes publication. The output is never a game directory.
        output.mkdir(parents=True)
        (output / "shaderinput").mkdir()
        (output / "assembled").mkdir()
        for name, item in outputs.items():
            (output / "shaderinput" / name).write_text(item["assembly"], encoding="utf-8", newline="\n")
            (output / "assembled" / (name[:-4] + ".cso")).write_bytes(item["binary"])
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for option in ("legacy-exports", "stock-exports", "preset", "stock-corpus", "assembler", "out"):
        ap.add_argument("--" + option, type=Path, required=True)
    ap.add_argument("--recipes", type=Path, default=RECIPES)
    args = ap.parse_args()
    report = build(args.legacy_exports, args.stock_exports, args.preset, args.stock_corpus,
                   args.assembler, args.out, json.loads(args.recipes.read_text(encoding="utf-8")))
    counts = {status: sum(e["status"] == status for e in report["entries"])
              for status in ("built_offline", "no_preset_delta", "pending_translation")}
    print(json.dumps({**counts, "aliases": len(report["affected_slots"]), "installed": False}))


if __name__ == "__main__":
    main()
