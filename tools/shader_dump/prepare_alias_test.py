"""Prepare the user-run baseline/probe/alias/effect kit without touching GTAIV.

No DLL execution or native testing. The generated kit contains local copies of
the user's preset/game inputs and must not be redistributed as project source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from decode_enb163 import INPUT_SHA256
from make_shader_aliases import DEFAULT_CONTRACT, stage
from make_legacy_tree_shader import build as build_legacy_tree

REPO = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game", type=Path, required=True)
    ap.add_argument("--enb", type=Path, required=True, help="ENB 0.163 Wrapper version")
    ap.add_argument("--ice", type=Path, required=True, help="iCEnhancer preset root")
    ap.add_argument("--out", type=Path, required=True, help="new directory outside game")
    args = ap.parse_args()
    game, enb, ice, out = (p.resolve() for p in (args.game, args.enb, args.ice, args.out))
    if out.exists() or any(out == p or out.is_relative_to(p) for p in (game, enb, ice)):
        raise ValueError("Output must be new and separate from all inputs")
    if hashlib.sha256((enb / "d3d9.dll").read_bytes()).hexdigest() != INPUT_SHA256:
        raise ValueError("Expected researched ENB 0.163 wrapper")
    stock = game / "common/shaders/win32_30"
    contract = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    # The runtime setup selects nv8, so verify actual selected terrain bytes too.
    from d3d9bc import extract_file
    for row in contract["entries"]:
        if row["group"] == "terrain":
            shader = extract_file(game / "common/shaders/win32_30_nv8" / row["container"])[row["index"]]
            if hashlib.sha256(shader.data).hexdigest() != row["shader_sha256"]:
                raise ValueError("Selected stock nv8 shader differs from the audited contract")
    stage(stock, ice / "shaderinput", contract, ["terrain"], out / "alias-report")
    stage(stock, ice / "shaderinput", contract, ["terrain"], out / "probe-report", probe=True)
    base = out / "baseline"
    base.mkdir()
    for path in enb.iterdir():
        if path.is_file() and (path.name == "d3d9.dll" or path.name.startswith("enb")):
            shutil.copy2(path, base / path.name)
    shutil.copytree(enb / "shaderinput", base / "shaderinput")
    for name, report in [("aliases", "alias-report"), ("probe", "probe-report")]:
        shutil.copytree(out / report / "shaderinput", out / name / "shaderinput")
    (out / "effect").mkdir()
    shutil.copy2(ice / "enbeffect.fx", out / "effect/enbeffect.fx")
    (base / "plugins").mkdir()
    shutil.copy2(REPO / "bin/GTAIV.EFLC.FusionFix.asi", base / "plugins/GTAIV.EFLC.FusionFix.asi")
    original_ini = game / "plugins/GTAIV.EFLC.FusionFix.ini"
    text = original_ini.read_text(encoding="utf-8-sig")
    text = re.sub(r"(?ms)^\[ENBCompatibility\][^\r\n]*\r?\n.*?(?=^\[|\Z)", "", text)
    text += "\n[ENBCompatibility]\nMode = 1\nVerboseLogging = 1\n"
    for key in ("ReplacePostFX", "PostProcessAA", "AmbientOcclusion", "ShadowPipelineFixes", "FusionShaderTweaks", "SunShafts",
                "PreAlphaDepthCopy", "SkyDiffuseSplit", "ConsoleGammaBlit",
                "FusionShaderPackage", "D3D9Trace", "DumpShaders"):
        text += f"{key} = 0\n"
    text += "ShaderConstantInjection = 1\n"
    text += "StockShaderFolder = win32_30_nv8\nSpoofGameVersion =\nLoadPluginAfterSpoof =\n"
    (base / "plugins/GTAIV.EFLC.FusionFix.ini").write_text(text, encoding="utf-8")
    (base / "d3d9.cfg").write_text("[MAIN]\nAPI = 0\n", encoding="ascii")
    ini = base / "enbseries.ini"
    text = ini.read_text(encoding="utf-8-sig")
    text = re.sub(r"(?im)^EnableProxyLibrary\s*=.*$", "EnableProxyLibrary=false", text)
    text = re.sub(r"(?im)^KeyUseEffect\s*=.*$", "KeyUseEffect=122", text)
    ini.write_text(text, encoding="utf-8")
    extra = Path("update/common/shaders/win32_30_nv8/gta_trees_extended.fxc")
    (base / extra).parent.mkdir(parents=True)
    compat_tree, tree_manifest = build_legacy_tree(
        REPO / "shaders/GTAIV.EFLC.FusionShaders/win32_30_nv8/gta_trees_extended.fxc.xml",
        out / "legacy-tree-build")
    shutil.copy2(compat_tree, base / extra)
    (out / "fixed").mkdir()
    shutil.copy2(compat_tree, out / "fixed/gta_trees_extended.fxc")
    (out / "fixed/manifest.json").write_text(json.dumps(tree_manifest, indent=2) + "\n", encoding="utf-8")
    expected = [{"path": p.relative_to(game).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in (original_ini, game / "GTAIV.exe", game / "plugins/GTAIV.EFLC.FusionFix.asi")]
    (out / "expected-originals.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(REPO / "tools/gamesetup/Invoke-ShaderAliasTest.ps1", out / "Invoke-ShaderAliasTest.ps1")
    files = [{"path": p.relative_to(out).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(out.rglob("*")) if p.is_file()]
    (out / "kit-files.json").write_text(json.dumps(files, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared user-run kit -> {out}. Game files unchanged; nothing launched.")


if __name__ == "__main__":
    main()
