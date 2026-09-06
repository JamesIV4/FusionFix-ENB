"""Stage the runtime composite bridge assets; no installation or D3D device.

The canonical shader retains its exact stock bytes so ENB recognizes AA1C0C36.
Only modern passes with the reviewed complete legacy binding set are admitted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import d3d9bc
from audit_shader_pair import read_export

ROOT = Path(__file__).resolve().parents[2]
STOCK_SHA = "2780e157105840b1226fff8ca72b5729652e75bc29fe3aa5f053ce9b9b8b96b9"
ICE_EFFECT_SHA = "da7f697611c62dded78ca347965bc60cdd0377d762fb5be96a9b6c36d95f74ee"
SLOTS = (13, 15, 25, 27, 29)
TARGETS = {13: (2880, 0x0F8207935837F1E8), 15: (2880, 0x1908E3196DA19522),
           25: (3024, 0x082BA71FB2BFA6A6), 27: (3024, 0x57B281F0F252D6D8),
           29: (2584, 0x84F21E21C975D165)}


def fnv64(data):
    h = 14695981039346656037
    for value in data:
        h = ((h ^ value) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h


def legacy_depth(value, near, far):
    if not 0 < near < far:
        raise ValueError("Invalid clip planes")
    eye = near * (far / near) ** value
    return max(0., min(1., far / (far - near) - far * near / ((far - near) * eye)))


def build(stock, modern, out, fxc, effect=None):
    stock, modern, out, fxc = map(lambda p: Path(p).resolve(), (stock, modern, out, fxc))
    if out.exists() or any(out.is_relative_to(p) for p in (stock, modern)):
        raise ValueError("Output must be new and separate from inputs")
    if any((p / "GTAIV.exe").exists() for p in (out, *out.parents)):
        raise ValueError("Stage outside the game")
    effect_data = Path(effect).read_bytes() if effect else None
    if effect_data is not None and hashlib.sha256(effect_data).hexdigest() != ICE_EFFECT_SHA:
        raise ValueError("The iCEnhancer main effect differs from the inspected original")
    legacy = d3d9bc.extract_file(stock / "rage_postfx.fxc")[13]
    if hashlib.sha256(legacy.data).hexdigest() != STOCK_SHA or legacy.hashes()["enb163"] != "AA1C0C36":
        raise ValueError("Canonical stock shader changed")
    reference = read_export(stock / "rage_postfx.fxc.xml")
    target = read_export(modern / "rage_postfx.fxc.xml")
    modern_blobs = d3d9bc.extract_file(modern / "rage_postfx.fxc")
    rows = []
    for slot in SLOTS:
        role = f"GTACompositePostFx/{slot - 2}"
        if reference["passes"][role]["ps"] != slot or target["passes"][role]["ps"] != slot:
            raise ValueError("Pass identity changed")
        expected = {k: list(v) for k, v in reference["shaders"][13]["bindings"].items()}
        for name in ("BloomSampler", "AdapLumSampler", "JitterSampler", "StencilCopySampler", "PLAYER_MASK"):
            expected[name][1] += 1
        actual = target["shaders"][slot]["bindings"]
        if any(actual.get(k) != v for k, v in expected.items()):
            raise ValueError(f"Modern named interface changed: {slot}")
        shader = modern_blobs[slot]
        if (len(shader.data), fnv64(shader.data)) != TARGETS[slot]:
            raise ValueError(f"Modern program is outside the runtime whitelist: {slot}")
        rows.append({"slot": slot, "role": role, "bytes": len(shader.data),
                     "fnv64": f"{fnv64(shader.data):016X}",
                     "program_bytes": len(shader.stripped()), "program_fnv64": f"{fnv64(shader.stripped()):016X}",
                     "sha256": hashlib.sha256(shader.data).hexdigest(),
                     "bindings": actual})
    with tempfile.TemporaryDirectory(prefix="postfx-bridge-") as work:
        output = Path(work) / "legacy_depth.cso"
        result = subprocess.run([str(fxc), "/nologo", "/T", "ps_3_0", "/E", "main", "/Fo", str(output),
                                 str(ROOT / "source/resources/ENBLegacyDepth.hlsl")], capture_output=True, text=True)
        if result.returncode:
            raise ValueError(result.stdout + result.stderr)
        depth = output.read_bytes()
        if (len(depth), fnv64(depth)) != (456, 0x81BC637FB46B15D2):
            raise ValueError("Depth compiler output differs from the runtime whitelist")
    report = {"format": 1, "runtime_validated": False, "game_modified": False,
              "modern_container_sha256": hashlib.sha256((modern / "rage_postfx.fxc").read_bytes()).hexdigest(),
              "canonical": {"bytes": len(legacy.data), "fnv64": f"{fnv64(legacy.data):016X}", "sha256": STOCK_SHA},
              "depth_conversion": {"bytes": len(depth), "fnv64": f"{fnv64(depth):016X}",
                                   "sha256": hashlib.sha256(depth).hexdigest()},
              "modern_passes": rows}
    out.mkdir(parents=True)
    if effect_data is not None:
        (out / "icenhancer_enbeffect.fx").write_bytes(effect_data)
        report["icenhancer_effect"] = {"sha256": ICE_EFFECT_SHA, "bytes": len(effect_data),
                                      "modified": False, "runtime_validated": False}
    (out / "legacy_composite.cso").write_bytes(legacy.data)
    (out / "legacy_depth.cso").write_bytes(depth)
    (out / "references").mkdir()
    for slot in SLOTS:
        (out / "references" / f"modern{slot}.cso").write_bytes(modern_blobs[slot].data)
    (out / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stock-exports", required=True, type=Path)
    ap.add_argument("--modern-exports", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--fxc", type=Path, default=ROOT / "source/dxsdk/lib/x86/fxc.exe")
    ap.add_argument("--effect", type=Path, help="optional original iCEnhancer enbeffect.fx for the separate effect test")
    args = ap.parse_args()
    report = build(args.stock_exports, args.modern_exports, args.out, args.fxc, args.effect)
    print(json.dumps({"canonical": report["canonical"], "depth": report["depth_conversion"],
                      "targets": [{k: p[k] for k in ("slot", "bytes", "fnv64")} for p in report["modern_passes"]]}, indent=2))
