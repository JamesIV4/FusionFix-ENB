"""Read-only scan of executable PE sections for historical hook patterns.

A matching byte sequence is a candidate, not a validated hook or an ENB shader
hash. File RVAs may differ from runtime code in packed or patched executables.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


def scan(path, definitions):
    data = Path(path).read_bytes()
    if len(data) < 64 or data[:2] != b"MZ":
        raise ValueError("Not a PE file")
    pe = struct.unpack_from("<I", data, 60)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Missing PE signature")
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    if struct.unpack_from("<H", data, pe + 24)[0] != 0x10B:
        raise ValueError("Expected 32-bit PE")
    base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    sections = []
    for i in range(count):
        h = pe + 24 + opt_size + 40 * i
        name = data[h:h + 8].rstrip(b"\0").decode("ascii")
        _, rva, size, offset = struct.unpack_from("<IIII", data, h + 8)
        if offset + size > len(data):
            raise ValueError("Section extends beyond file")
        if struct.unpack_from("<I", data, h + 36)[0] & 0x20000000:
            sections.append((name, rva, offset, data[offset:offset + size]))
    rows = []
    for definition in definitions:
        pattern = b"".join(b"." if token == "?" else re.escape(bytes([int(token, 16)]))
                           for token in definition["pattern"].split())
        matches = []
        for name, rva, offset, content in sections:
            for m in re.finditer(b"(?=(" + pattern + b"))", content, re.S):
                matches.append({"section": name, "rva": f"0x{rva + m.start():08X}",
                                "file_offset": f"0x{offset + m.start():08X}"})
        rows.append({**definition, "matches": matches, "runtime_validated": False})
    return {"exe_sha256": hashlib.sha256(data).hexdigest(), "preferred_image_base": hex(base),
            "method": "on-disk executable PE sections only; no patching", "entries": rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("exe", type=Path)
    ap.add_argument("patterns", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    definitions = json.loads(args.patterns.read_text(encoding="utf-8"))["entries"]
    report = scan(args.exe, definitions)
    with args.out.open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2)
        out.write("\n")
    print(f"Scanned {len(report['entries'])} patterns: {args.out}")


if __name__ == "__main__":
    main()
