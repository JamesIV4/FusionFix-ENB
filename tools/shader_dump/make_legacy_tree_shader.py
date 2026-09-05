"""Build FusionFix's required extended-tree container for the stock depth path.

The FusionFix content package names gta_trees_extended, so the otherwise-stock
ENB overlay must retain it. Modern versions explicitly write logarithmic depth
using c209, which is incompatible with stock deferred/postfx depth readers.
This tool copies the authored XML/assembly to a new directory, removes only the
five marked LogDepth Write blocks and unused pixel v9 declarations, then asks
RageShaderEditor to build a new container. Source files are never modified.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_XML = REPO / "shaders/GTAIV.EFLC.FusionShaders/win32_30_nv8/gta_trees_extended.fxc.xml"
DEFAULT_RSE = REPO / "tools/RageShaderEditor/RageShaderEditor.exe"

DEPTH_BLOCK = re.compile(
    r"(?ms)^[ \t]*// LogDepth Write[ \t]*\r?\n"
    r".*?^[ \t]*cmp oDepth,[^\r\n]*(?:\r?\n)")
PIXEL_V9 = re.compile(r"(?m)^[ \t]*dcl_texcoord9[ \t]+v9[^\r\n]*(?:\r?\n)")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source_xml, output):
    source_xml, output = Path(source_xml).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Output must be a new directory")
    source_dir = source_xml.parent / "gta_trees_extended"
    if not source_xml.is_file() or not source_dir.is_dir():
        raise ValueError("Extended-tree XML/assembly source is incomplete")
    if output == source_xml.parent or output.is_relative_to(source_xml.parent):
        raise ValueError("Output must be separate from authored shader source")

    output.mkdir(parents=True)
    copied_xml = output / source_xml.name
    shutil.copy2(source_xml, copied_xml)
    copied_dir = output / source_dir.name
    shutil.copytree(source_dir, copied_dir)

    modified = []
    for path in sorted(copied_dir.glob("*PS*.asm")):
        text = path.read_text(encoding="utf-8-sig")
        text, blocks = DEPTH_BLOCK.subn("", text)
        text, declarations = PIXEL_V9.subn("", text)
        if blocks:
            if blocks != 1 or declarations != 1:
                raise ValueError(f"Unexpected depth structure in {path.name}")
            modified.append(path.name)
        elif declarations:
            raise ValueError(f"Removed v9 without a depth block in {path.name}")
        path.write_text(text, encoding="utf-8", newline="")

    if len(modified) != 5:
        raise ValueError(f"Expected five depth-writing pixel shaders, found {len(modified)}")
    for path in copied_dir.glob("*PS*.asm"):
        code = "\n".join(line.split("//", 1)[0] for line in path.read_text(encoding="utf-8").splitlines())
        if re.search(r"\b(?:c209(?:_abs)?|oDepth|v9)\b", code):
            raise ValueError(f"Stock-depth pixel source still uses log-depth inputs: {path.name}")
    return copied_xml, modified


def build(source_xml, output, rse=DEFAULT_RSE):
    copied_xml, modified = prepare(source_xml, output)
    rse = Path(rse).resolve()
    if not rse.is_file():
        raise ValueError(f"RageShaderEditor not found: {rse}")
    result = subprocess.run([str(rse), str(copied_xml)], cwd=rse.parent,
                            capture_output=True, text=True, timeout=120)
    compiled = copied_xml.with_suffix("")
    if result.returncode or not compiled.is_file():
        raise ValueError("RageShaderEditor failed: " + (result.stdout + result.stderr).strip())

    # RAGE container extraction is the independent boundary check: the output
    # must retain all eleven programs and cannot contain c209/oDepth bytecode.
    import d3d9bc
    shaders = d3d9bc.extract_file(compiled)
    if len(shaders) != 11:
        raise ValueError(f"Compiled container has {len(shaders)} shaders, expected 11")
    manifest = {
        "format": 1,
        "source_xml": str(Path(source_xml).resolve()),
        "source_xml_sha256": sha(Path(source_xml)),
        "modified_pixel_assemblies": modified,
        "transformation": "remove five marked LogDepth Write blocks and now-unused pixel v9 declarations",
        "compiled_file": compiled.name,
        "compiled_bytes": compiled.stat().st_size,
        "compiled_sha256": sha(compiled),
        "shader_count": len(shaders),
        "requires_constant_provider": {"pixel": [221], "vertex": [233]},
        "requires_c209": False,
        "writes_explicit_depth": False,
        "rendering_validated": False,
    }
    (Path(output) / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return compiled, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_XML)
    parser.add_argument("--rse", type=Path, default=DEFAULT_RSE)
    parser.add_argument("--out", type=Path, required=True, help="new scratch directory")
    args = parser.parse_args()
    compiled, manifest = build(args.source, args.out, args.rse)
    print(f"Built stock-depth extended tree: {compiled} ({manifest['compiled_sha256']})")


if __name__ == "__main__":
    main()
