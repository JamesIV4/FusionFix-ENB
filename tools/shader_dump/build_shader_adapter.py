"""Build guarded iCEnhancer deltas on modern FusionFix shaders, offline.

This first backend supports the three audited terrain DEF deltas. It does not
transplant legacy programs into the modern renderer. Original modern bytecode
is the reference; assembled output must equal it except for one float literal.
Generated shaderinput aliases require the matching FULL modern shader pipeline.
No game files are installed and no D3D device is created.
"""

import argparse
import difflib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from audit_shader_pair import audit, read_export
import d3d9bc
from enb163_hash import filename
from make_shader_aliases import leaf, sha

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECIPES = ROOT / "research/contracts/modern-shader-deltas.json"
DEFAULT_ALIASES = ROOT / "research/contracts/ce-shader-aliases.json"


def instructions(text):
    return [re.sub(r"\s+", " ", code.strip()) for line in text.replace("\0", "").splitlines()
            if (code := line.split("//", 1)[0]).strip()]


def edit_def(text, register, component, before, after):
    """Edit one audited full-vector float DEF, never register uses or comments."""
    if register < 0 or register >= 224 or component not in range(4):
        raise ValueError("Unsupported pixel constant component")
    rows = instructions(text)
    matches = [i for i, line in enumerate(rows) if re.match(rf"^def c{register},", line)]
    if len(matches) != 1:
        raise ValueError("Expected exactly one local DEF")
    i = matches[0]
    values = rows[i].split(",")[1:]
    if len(values) != 4 or struct.pack("<f", float(values[component])) != struct.pack("<f", before):
        raise ValueError("DEF literal differs from audited recipe")
    values[component] = format(after, ".9g")
    rows[i] = f"def c{register}, " + ", ".join(v.strip() for v in values)
    return "\n".join(rows) + "\n"


def patch_literal(data, register, component, before, after):
    """Patch the literal token, independently of the assembly text editor."""
    if data[:4] != struct.pack("<I", 0xFFFF0300):
        raise ValueError("Expected ps_3_0")
    if register not in range(224) or component not in range(4):
        raise ValueError("Invalid constant component")
    offset, found, ended = 4, [], False
    while offset + 4 <= len(data):
        token = struct.unpack_from("<I", data, offset)[0]
        if token == 0xFFFF:
            ended = offset + 4 == len(data)
            break
        count = ((token >> 16) & 0x7FFF) if token & 0xFFFF == 0xFFFE else ((token >> 24) & 15)
        end = offset + 4 * (count + 1)
        if end > len(data) or (count == 0 and token & 0xFFFF != 0xFFFE):
            raise ValueError("Malformed or unsupported shader token")
        if token == 0x05000051 and struct.unpack_from("<I", data, offset + 4)[0] == 0xA00F0000 | register:
            found.append(offset + 8 + 4 * component)
        offset = end
    if not ended or len(found) != 1:
        raise ValueError("Expected complete bytecode with one matching DEF")
    at = found[0]
    if data[at:at + 4] != struct.pack("<f", before):
        raise ValueError("Bytecode literal differs from audited recipe")
    result = data[:at] + struct.pack("<f", after) + data[at + 4:]
    return result, at


def assembly_at(xml_path, slot):
    text = re.sub(r"<\?xml.*?\?>", "", xml_path.read_text(encoding="utf-8-sig"), count=1)
    root = ET.fromstring("<root>" + text + "</root>")
    items = root.findall("Effect/Shaders/VertexShaders/Item") + root.findall("Effect/Shaders/PixelShaders/Item")
    path = (xml_path.parent / items[slot].findtext("File").replace("\\", "/")).resolve()
    if not path.is_relative_to(xml_path.parent.resolve()):
        raise ValueError("Assembly path escapes export directory")
    return path.read_text(encoding="utf-8-sig")


def assemble(exe, text, directory, name):
    source, target = directory / (name + ".txt"), directory / (name + ".cso")
    source.write_text(text, encoding="utf-8")
    subprocess.run([str(exe), str(source), str(target)], check=True, capture_output=True, text=True)
    data = target.read_bytes()
    shaders = d3d9bc.extract(data)
    if len(shaders) != 1 or shaders[0].data != data:
        raise ValueError("Assembler did not produce exactly one shader")
    return shaders[0]


def build(stock, modern, preset, output, assembler, aliases, recipes, corpus):
    stock, modern, preset, output, assembler, corpus = [Path(p).resolve() for p in (stock, modern, preset, output, assembler, corpus)]
    if output.exists():
        raise ValueError("Output must be a new directory")
    if any(output == p or output.is_relative_to(p) for p in (stock, modern, preset, corpus)):
        raise ValueError("Output must be separate from input directories")
    if any((p / "GTAIV.exe").exists() for p in (output, *output.parents)):
        raise ValueError("Build outside the game directory")
    rules = {r["preset_file"]: r for r in recipes["entries"]}
    if len(rules) != len(recipes["entries"]):
        raise ValueError("Duplicate recipe")
    files, rows = {}, []
    with tempfile.TemporaryDirectory(prefix="enb-delta-") as temp:
        work = Path(temp)
        for e in aliases["entries"]:
            name, container = leaf(e["preset_file"]), leaf(e["container"])
            source_xml, target_xml = stock / (container + ".xml"), modern / (container + ".xml")
            source, target = read_export(source_xml), read_export(target_xml)
            report = audit(source, target, [e["index"]])["entries"][0]
            original = d3d9bc.extract_file(stock / container)[e["index"]]
            replacement = (preset / name).read_bytes()
            if sha(original.data) != e["shader_sha256"] or sha(replacement) != e["replacement_sha256"]:
                raise ValueError(f"Source/preset identity changed: {name}")
            source_asm = assembly_at(source_xml, e["index"])
            row = {"preset_file": name, "container": container, "source_sha256": sha(original.data),
                   "preset_sha256": sha(replacement), "interface_audit": report,
                   "delta": list(difflib.unified_diff(instructions(source_asm),
                                 instructions(replacement.decode("utf-8-sig")), lineterm="", n=0)),
                   "status": "requires_custom_adapter"}
            rows.append(row)
            if name not in rules:
                row["reason"] = "No reviewed semantic recipe; legacy program is not copied into modern shaders."
                continue
            rule = rules[name]
            if not report["mapping_unambiguous"] or report["roles"] != rule["roles"]:
                raise ValueError(f"Technique/pass mapping changed: {name}")
            slot = report["target_slots"][0]
            if sha((corpus / container).read_bytes()) != sha((modern / container).read_bytes()):
                raise ValueError(f"Modern export/corpus containers differ: {container}")
            blob = d3d9bc.extract_file(modern / container)[slot]
            if sha(blob.data) != rule["modern_shader_sha256"] or blob.stage != "ps":
                raise ValueError(f"Modern shader identity changed: {name}")
            if report["candidates"][0]["changed_bindings"]:
                raise ValueError(f"Legacy named bindings changed: {name}")
            args = (rule["register"], rule["component"], rule["before"], rule["after"])
            # Prove that this is the entire preset delta, not merely a likely match.
            if instructions(edit_def(source_asm, *args)) != instructions(replacement.decode("utf-8-sig")):
                raise ValueError(f"Recipe does not cover the entire preset delta: {name}")
            source_compiled = assemble(assembler, source_asm.replace("\0", ""), work, name + "-stock")
            if source_compiled.stripped() != original.stripped():
                raise ValueError("Stock export does not reproduce stock program")
            target_asm = assembly_at(target_xml, slot)
            target_compiled = assemble(assembler, target_asm.replace("\0", ""), work, name + "-modern")
            if target_compiled.stripped() != blob.stripped():
                raise ValueError("Modern export does not reproduce modern program")
            adapted_asm = edit_def(target_asm, *args)
            adapted = assemble(assembler, adapted_asm, work, name + "-adapted")
            expected, offset = patch_literal(blob.data, *args)
            expected_shader = d3d9bc.Shader("expected", 0, blob.model, expected)
            if adapted.stripped() != expected_shader.stripped():
                raise ValueError("Adapted program changed more than the approved literal")
            alias = filename(blob.data, blob.stage)
            if alias in files:
                raise ValueError(f"Duplicate modern alias: {alias}")
            files[alias] = (adapted_asm, adapted.data, sha(blob.data))
            row.update(status="built_offline", modern_slot=slot, alias=alias,
                       modern_sha256=sha(blob.data), adapted_sha256=sha(adapted.data),
                       adapted_crc32=adapted.hashes()["crc32"], literal_byte_offset=offset,
                       delta_recipe=rule, retained="All modern instructions, declarations and other literal tokens",
                       rendering_validated=False)
        if set(rules) != {r["preset_file"] for r in rows if r["status"] == "built_offline"}:
            raise ValueError("An approved recipe was not built")
        # Guard the 32-bit routing identity against unrelated shaders sharing it.
        affected = {name: [] for name in files}
        for path in sorted(corpus.glob("*.fxc")):
            for index, shader in enumerate(d3d9bc.extract_file(path)):
                alias = filename(shader.data, shader.stage)
                if alias in files:
                    if sha(shader.data) != files[alias][2]:
                        raise ValueError(f"Modern alias collision: {alias}")
                    affected[alias].append({"container": path.name, "index": index})
        result = {"format": 1, "backend": "reviewed_local_def_delta", "rendering_validated": False,
                  "requires": "matching full modern FusionFix shader/resource/depth pipeline; not FixedBaseline",
                  "effect_bridge_complete": False, "game_modified": False,
                  "collision_scan_containers": len(list(corpus.glob("*.fxc"))),
                  "affected_slots": affected, "entries": rows}
        # Publish only after every shader has passed all validation steps.
        output.mkdir(parents=True)
        (output / "shaderinput").mkdir()
        (output / "assembled").mkdir()
        for name, (assembly, binary, _) in files.items():
            (output / "shaderinput" / name).write_text(assembly, encoding="utf-8")
            (output / "assembled" / (name[:-4] + ".cso")).write_bytes(binary)
        (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stock-exports", type=Path, required=True)
    ap.add_argument("--modern-exports", type=Path, required=True)
    ap.add_argument("--modern-corpus", type=Path, required=True, help="complete matching shader variant for alias collision checks")
    ap.add_argument("--preset", type=Path, required=True)
    ap.add_argument("--assembler", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--aliases", type=Path, default=DEFAULT_ALIASES)
    ap.add_argument("--recipes", type=Path, default=DEFAULT_RECIPES)
    args = ap.parse_args()
    report = build(args.stock_exports, args.modern_exports, args.preset, args.out, args.assembler,
                   json.loads(args.aliases.read_text()), json.loads(args.recipes.read_text()), args.modern_corpus)
    ready = sum(e["status"] == "built_offline" for e in report["entries"])
    print(f"Built {ready} modern adapters; {len(report['entries']) - ready} mapped inputs need custom translation. No installation.")


if __name__ == "__main__":
    main()
