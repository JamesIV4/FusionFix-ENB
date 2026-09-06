"""Read-only comparison of a downloaded legacy GTAIV depot with a CE install.

Compares raw containers and extracted programs directly, not just CRCs. Equal
container bytes prove metadata/pass-state equality too. Unequal containers are
reported conservatively; slot comparisons alone do not prove role equivalence.
"""

import argparse
import hashlib
import json
from pathlib import Path

import d3d9bc
from enb163_hash import filename


def digest(data):
    return hashlib.sha256(data).hexdigest()


def compare(old_root, ce_root):
    old_root, ce_root = Path(old_root), Path(ce_root)
    aroot, broot = old_root / "common/shaders", ce_root / "common/shaders"
    if not aroot.is_dir() or not broot.is_dir():
        raise ValueError("Both inputs must have common/shaders")
    aa = {p.relative_to(aroot).as_posix(): p for p in aroot.rglob("*.fxc")}
    bb = {p.relative_to(broot).as_posix(): p for p in broot.rglob("*.fxc")}
    if not aa or not bb:
        raise ValueError("Empty shader input")
    variants, changed, identical = {}, [], []
    for name in sorted(aa.keys() & bb.keys()):
        a, b = aa[name].read_bytes(), bb[name].read_bytes()
        variant = name.split("/")[0]
        counts = variants.setdefault(variant, {
            "containers": 0, "raw_equal_containers": 0, "changed_containers": 0,
            "old_shaders": 0, "ce_shaders": 0, "same_slot_raw_equal": 0,
            "same_slot_comment_only": 0, "same_slot_program_changed": 0,
            "old_unpaired_slots": 0, "ce_unpaired_slots": 0})
        x, y = d3d9bc.extract(a), d3d9bc.extract(b)
        counts["containers"] += 1
        counts["old_shaders"] += len(x)
        counts["ce_shaders"] += len(y)
        changes = []
        for index, (left, right) in enumerate(zip(x, y)):
            if left.data == right.data:
                counts["same_slot_raw_equal"] += 1
            else:
                comment_only = left.stripped() == right.stripped()
                counts["same_slot_comment_only" if comment_only else "same_slot_program_changed"] += 1
                changes.append({"index": index, "stage_old": left.stage,
                                "stage_ce": right.stage, "comment_only": comment_only,
                                "old_enb_filename": filename(left.data, left.stage),
                                "ce_enb_filename": filename(right.data, right.stage)})
        counts["old_unpaired_slots"] += max(0, len(x) - len(y))
        counts["ce_unpaired_slots"] += max(0, len(y) - len(x))
        if a == b:
            counts["raw_equal_containers"] += 1
            identical.append({"file": name, "sha256": digest(a), "shaders": len(x)})
        else:
            counts["changed_containers"] += 1
            changed.append({"file": name, "old_sha256": digest(a), "ce_sha256": digest(b),
                            "old_shaders": len(x), "ce_shaders": len(y),
                            "same_slot_changes": changes})
    auxiliary = []
    for name in ["pc/data/timecyc.dat", "common/data/visualsettings.dat",
                 "common/shaders/db/gta_trees.sps", "common/shaders/dcl/gta_trees.dcl"]:
        a, b = old_root / name, ce_root / name
        if a.is_file() and b.is_file():
            x, y = a.read_bytes(), b.read_bytes()
            auxiliary.append({"file": name, "raw_equal": x == y,
                              "old_sha256": digest(x), "ce_sha256": digest(y)})
    return {"method": "raw byte equality; unequal containers additionally compare extracted same-index raw/comment-stripped programs",
            "old_exe_sha256": digest((old_root / "GTAIV.exe").read_bytes()) if (old_root / "GTAIV.exe").is_file() else None,
            "ce_exe_sha256": digest((ce_root / "GTAIV.exe").read_bytes()) if (ce_root / "GTAIV.exe").is_file() else None,
            "old_container_count": len(aa), "ce_container_count": len(bb),
            "old_only_containers": sorted(aa.keys() - bb.keys()),
            "ce_only_containers": sorted(bb.keys() - aa.keys()),
            "variants": variants, "identical_containers": identical,
            "changed_containers": changed, "auxiliary_files": auxiliary,
            "runtime_validated": False, "inputs_modified": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("legacy", type=Path)
    ap.add_argument("ce", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = compare(args.legacy, args.ce)
    with args.out.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(f"Equal containers: {len(result['identical_containers'])}; changed: {len(result['changed_containers'])}")
    for name, row in result["variants"].items():
        print(name, row)


if __name__ == "__main__":
    main()
