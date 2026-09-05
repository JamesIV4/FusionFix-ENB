"""Map shader slots by named technique/pass, then audit transplant boundaries.

Inputs are RageShaderEditor .fxc.xml exports (including their assembly files).
No game files are changed. Register compatibility is NOT rendering compatibility:
depth encoding, other stages, pass state and resource contents also matter.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def read_export(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    # RSE emits several top-level elements and a nonstandard encoding label.
    text = re.sub(r"<\?xml.*?\?>", "", text, count=1)
    root = ET.fromstring("<root>" + text + "</root>")
    effect = root.find("Effect")
    if effect is None:
        raise ValueError(f"No Effect in {path}")
    shaders = []
    for stage, group in (("vs", "VertexShaders"), ("ps", "PixelShaders")):
        for local, item in enumerate(effect.findall(f"Shaders/{group}/Item")):
            variables = {}
            for v in item.findall("Variables/Item"):
                name = v.findtext("Name")
                if name in variables:
                    raise ValueError(f"Duplicate variable {name}")
                variables[name] = [v.findtext("Type"), int(v.find("Index").get("value"))]
            filename = item.findtext("File")
            if not filename:
                raise ValueError("Shader has no assembly File")
            asm_path = (path.parent / filename.replace("\\", "/")).resolve()
            if not asm_path.is_relative_to(path.parent.resolve()):
                raise ValueError("Assembly path escapes export directory")
            assembly = asm_path.read_text(encoding="utf-8-sig").replace("\0", "")
            code = "\n".join(line.split("//", 1)[0] for line in assembly.splitlines())
            shaders.append({"stage": stage, "local_index": local,
                            "bindings": variables,
                            "writes_depth": bool(re.search(r"\boDepth\b", code)),
                            "declarations": sorted(line.strip() for line in code.splitlines()
                                                   if line.strip().startswith("dcl"))})
    nvs = sum(s["stage"] == "vs" for s in shaders)
    passes = {}
    for tech in effect.findall("Techniques/Item"):
        name = tech.findtext("Name")
        for ordinal, p in enumerate(tech.findall("Passes/Item")):
            key = f"{name}/{ordinal}"
            if key in passes:
                raise ValueError(f"Duplicate technique/pass {key}")
            # RAGE exports vertex indices from zero, pixel indices from one.
            vs = int(p.findtext("VertexShader"))
            ps = nvs + int(p.findtext("PixelShader")) - 1
            if not (0 <= vs < nvs and nvs <= ps < len(shaders)):
                raise ValueError(f"Invalid shader reference at {key}")
            passes[key] = {"vs": vs, "ps": ps, "state": [
                [int(v.find("Type").get("value")), int(v.find("Value").get("value"))]
                for v in p.findall("Params/Item")]}
    return {"xml_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "shaders": shaders, "passes": passes}


def audit(source, target, slots):
    rows = []
    for slot in slots:
        if not 0 <= slot < len(source["shaders"]):
            raise ValueError(f"Source slot {slot} out of range")
        shader = source["shaders"][slot]
        stage = shader["stage"]
        roles = [key for key, p in source["passes"].items() if p[stage] == slot]
        missing = [key for key in roles if key not in target["passes"]]
        mapped = sorted({target["passes"][key][stage] for key in roles if key not in missing})
        row = {"source_slot": slot, "stage": stage, "roles": roles,
               "missing_roles": missing, "target_slots": mapped, "candidates": []}
        for dst in mapped:
            other = target["shaders"][dst]
            changed = {name: {"source": binding, "target": other["bindings"].get(name)}
                       for name, binding in shader["bindings"].items()
                       if other["bindings"].get(name) != binding}
            pass_changes = [key for key in roles if key in target["passes"]
                            and target["passes"][key][stage] == dst
                            and source["passes"][key]["state"] != target["passes"][key]["state"]]
            row["candidates"].append({"target_slot": dst,
                "changed_bindings": changed,
                "target_extra_bindings": {k: v for k, v in other["bindings"].items()
                                          if k not in shader["bindings"]},
                "source_writes_depth": shader["writes_depth"],
                "target_writes_depth": other["writes_depth"],
                "declarations_equal": shader["declarations"] == other["declarations"],
                "changed_pass_states": pass_changes,
                "source_bindings_preserved": not changed})
        row["mapping_unambiguous"] = bool(roles) and not missing and len(mapped) == 1
        rows.append(row)
    return {"source_xml_sha256": source["xml_sha256"],
            "target_xml_sha256": target["xml_sha256"],
            "method": "named technique/pass and stage; never assume equal slot numbers",
            "rendering_validated": False, "entries": rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source_xml", type=Path)
    ap.add_argument("target_xml", type=Path)
    ap.add_argument("--slots", nargs="+", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = audit(read_export(args.source_xml), read_export(args.target_xml), args.slots)
    with args.out.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(f"Audited {len(result['entries'])} slots; rendering remains unverified: {args.out}")


if __name__ == "__main__":
    main()
