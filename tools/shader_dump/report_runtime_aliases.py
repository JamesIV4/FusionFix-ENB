"""Report which prepared ENB shader aliases were created and first-bound.

Consumes the CSV/CSO files written by ENBTrace. It does not start or attach to
the game. Exact assembled shader SHA256 is checked when DumpShaders was enabled.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
DEFAULT_CONTRACT = HERE.parents[1] / "research/contracts/ce-shader-aliases.json"


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path, required_columns, optional=False):
    if not path.is_file():
        if optional:
            return []
        raise ValueError(f"Missing trace file: {path.name}")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for key in required_columns:
            if key not in row:
                raise ValueError(f"{path.name} lacks {key}")
    return rows


def report(trace_dir, contract):
    trace_dir = Path(trace_dir).resolve()
    created_rows = read_csv(trace_dir / "shaders.csv",
                            {"stage", "crc32", "crc32_stripped", "bytes", "frame"})
    bind_path = trace_dir / "shader_first_binds.csv"
    bound_rows = read_csv(bind_path,
                          {"stage", "crc32", "crc32_stripped", "first_frame"},
                          optional=True)
    created = {(r["stage"].lower(), r["crc32"].upper()): r for r in created_rows}
    bound = {(r["stage"].lower(), r["crc32"].upper()): r for r in bound_rows}
    session_path = trace_dir / "trace-session.json"
    session = json.loads(session_path.read_text(encoding="utf-8-sig")) if session_path.is_file() else None
    installed_aliases = ({a["file"].lower() for a in session.get("aliases", [])}
                         if session else None)
    results = []
    for entry in contract["entries"]:
        expected = entry.get("assembled")
        alias = entry.get("ce_alias")
        if not expected or not alias:
            raise ValueError(f"Contract lacks assembled identity: {entry['preset_file']}")
        key = (entry["stage"], expected["crc32"])
        created_row = created.get(key)
        bound_row = bound.get(key)
        dump = trace_dir / "shaders" / f"{entry['stage']}_{expected['crc32']}.cso"
        dump_sha = file_sha(dump) if dump.is_file() else None
        dump_exact = dump_sha == expected["sha256"] if dump_sha else None
        installed = alias.lower() in installed_aliases if installed_aliases is not None else None
        if installed is False:
            status = "not_installed"
        elif bound_row and dump_exact is not False:
            status = "bound_exact" if dump_exact else "bound_hash_match"
        elif created_row and dump_exact is not False:
            status = "created_exact" if dump_exact else "created_hash_match"
        elif created_row:
            status = "created_dump_mismatch"
        else:
            status = "not_created"
        results.append({
            "preset_file": entry["preset_file"], "ce_alias": alias,
            "role": f"{entry['container']}#{entry['index']}", "group": entry["group"],
            "expected_assembled": expected, "status": status,
            "installed": installed,
            "created": created_row is not None, "first_bound": bound_row is not None,
            "first_bound_frame": int(bound_row["first_frame"]) if bound_row else None,
            "dump_sha256": dump_sha, "dump_exact": dump_exact,
        })
    counts = {status: sum(r["status"] == status for r in results) for status in
              ("bound_exact", "bound_hash_match", "created_exact", "created_hash_match",
               "created_dump_mismatch", "not_created", "not_installed")}
    return {
        "format": 1,
        "method": "ENBTrace CreateShader dump plus automatic first-bind capture",
        "trace_dir": str(trace_dir),
        "trace_files": {p.name: file_sha(p) for p in
                        (trace_dir / "shaders.csv", bind_path, trace_dir / "d3d9_trace.log", session_path)
                        if p.is_file()},
        "created_shader_count": len(created_rows),
        "first_bound_shader_count": len(bound_rows),
        "first_bind_data_available": bind_path.is_file(),
        "session": session,
        "counts": counts,
        "aliases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_dir", type=Path, help="ENBCompat output directory")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--out", type=Path, required=True, help="new JSON report")
    args = parser.parse_args()
    try:
        result = report(args.trace_dir, json.loads(args.contract.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"runtime alias audit failed: {error}", file=sys.stderr)
        return 2
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(f"Runtime alias audit: {args.out}")
    for row in result["aliases"]:
        print(f"  {row['ce_alias']:16} {row['status']:22} {row['role']}")
    return 2 if any(r["status"] == "created_dump_mismatch" for r in result["aliases"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
