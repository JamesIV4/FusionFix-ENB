"""Read an existing x86 minidump exception and compare code with an on-disk PE.

No process attachment or execution. Emits only fault registers, module-relative
addresses, and 16 code bytes; no general memory/stack dump or private file paths.
Instruction differences alone do not identify the writer or prove a bad patch.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct


def inspect(dump_path, exe_path):
    data, disk = Path(dump_path).read_bytes(), Path(exe_path).read_bytes()

    def read(offset, size):
        if offset < 0 or size < 0 or offset + size > len(data):
            raise ValueError("Minidump range outside file")
        return data[offset:offset + size]

    def unpack(fmt, offset):
        return struct.unpack(fmt, read(offset, struct.calcsize(fmt)))

    if read(0, 4) != b"MDMP":
        raise ValueError("Expected Windows minidump")
    count, directory = unpack("<II", 8)
    if count > 10000:
        raise ValueError("Excessive stream count")
    streams = {}
    for index in range(count):
        kind, size, offset = unpack("<III", directory + index * 12)
        read(offset, size)
        streams[kind] = (offset, size)
    system, _ = streams[7]
    if unpack("<H", system)[0] != 0:
        raise ValueError("Expected x86 context")
    modlist, _ = streams[4]
    modules = []
    for index in range(unpack("<I", modlist)[0]):
        offset = modlist + 4 + index * 108
        base, size, _, _, name = unpack("<QIIII", offset)
        text = read(name + 4, unpack("<I", name)[0]).decode("utf-16-le")
        modules.append({"name": text.replace("\\", "/").split("/")[-1],
                        "base": base, "size": size})
    memory = []
    if 5 in streams:
        offset, _ = streams[5]
        for index in range(unpack("<I", offset)[0]):
            address, size, rva = unpack("<QII", offset + 4 + index * 16)
            memory.append((address, size, rva))
    if 9 in streams:
        offset, _ = streams[9]
        count, rva = unpack("<QQ", offset)
        for index in range(count):
            address, size = unpack("<QQ", offset + 16 + index * 16)
            memory.append((address, size, rva))
            rva += size

    def runtime(address, size):
        for base, length, offset in memory:
            if base <= address and address + size <= base + length:
                return read(offset + address - base, size)
        return None

    offset, _ = streams[6]
    code = unpack("<I", offset + 8)[0]
    address = unpack("<Q", offset + 24)[0]
    param_count = min(unpack("<I", offset + 32)[0], 2)
    params = unpack("<" + "Q" * param_count, offset + 40)
    context_size, context = unpack("<II", offset + 160)
    if context_size < 200:
        raise ValueError("Truncated x86 context")
    registers = {name: unpack("<I", context + position)[0] for name, position in
                 [("edi", 156), ("esi", 160), ("ebx", 164), ("edx", 168),
                  ("ecx", 172), ("eax", 176), ("ebp", 180), ("eip", 184), ("esp", 196)]}
    module = next((m for m in modules if m["base"] <= address < m["base"] + m["size"]), None)
    live = runtime(address, 16)
    comparison = None
    if module and module["name"].lower() == Path(exe_path).name.lower():
        pe = struct.unpack_from("<I", disk, 60)[0]
        if disk[:2] != b"MZ" or disk[pe:pe + 4] != b"PE\0\0":
            raise ValueError("Invalid comparison PE")
        count = struct.unpack_from("<H", disk, pe + 6)[0]
        size = struct.unpack_from("<H", disk, pe + 20)[0]
        rva = address - module["base"]
        for i in range(count):
            section = pe + 24 + size + i * 40
            _, start, length, raw = struct.unpack_from("<IIII", disk, section + 8)
            if start <= rva and rva + 16 <= start + length:
                original = disk[raw + rva - start:raw + rva - start + 16]
                comparison = {"module": module["name"], "rva": f"{rva:08X}",
                              "disk_bytes": original.hex(),
                              "runtime_bytes": live.hex() if live else None,
                              "differing_rvas": [f"{rva + j:08X}" for j in range(16)
                                                 if live and live[j] != original[j]]}
                break
    return {"dump_file": Path(dump_path).name,
            "dump_sha256": hashlib.sha256(data).hexdigest(),
            "exe_sha256": hashlib.sha256(disk).hexdigest(),
            "exception_code": f"{code:08X}", "exception_address": f"{address:08X}",
            "exception_information": [f"{p:08X}" for p in params],
            "registers": {k: f"{v:08X}" for k, v in registers.items()},
            "instruction_comparison": comparison,
            "relevant_modules": [{**m, "base": f"{m['base']:08X}"} for m in modules
                                 if m["name"].lower() in ("gtaiv.exe", "d3d9.dll", "icenhancer.enbcompat", "icenhancer.asi", "gtaiv.eflc.fusionfix.asi")],
            "writer_identified": False, "process_started_or_attached": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dump", type=Path)
    ap.add_argument("--exe", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = inspect(args.dump, args.exe)
    with args.out.open("x", encoding="utf-8") as out:
        out.write(json.dumps(report, indent=2) + "\n")
    print(f"Read existing crash, exception {report['exception_code']} -> {args.out}")


if __name__ == "__main__":
    main()
