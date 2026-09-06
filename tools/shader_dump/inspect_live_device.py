"""Read GTAIV's device pointer and vtable ownership; no writes or remote calls.

Uses the same on-disk pointer-reference patterns as comvars.ixx. Emits only
module names and device/method addresses, not arbitrary process memory.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path
import re
import struct


def inspect(pid):
    kernel, psapi = c.WinDLL("kernel32", use_last_error=True), c.WinDLL("psapi", use_last_error=True)
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.ReadProcessMemory.argtypes = [w.HANDLE, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
    kernel.ReadProcessMemory.restype = w.BOOL
    psapi.EnumProcessModulesEx.argtypes = [w.HANDLE, c.POINTER(c.c_void_p), w.DWORD, c.POINTER(w.DWORD), w.DWORD]
    psapi.EnumProcessModulesEx.restype = w.BOOL
    psapi.GetModuleFileNameExW.argtypes = [w.HANDLE, c.c_void_p, w.LPWSTR, w.DWORD]
    class ModuleInfo(c.Structure):
        _fields_ = [("base", c.c_void_p), ("size", w.DWORD), ("entry", c.c_void_p)]
    psapi.GetModuleInformation.argtypes = [w.HANDLE, c.c_void_p, c.POINTER(ModuleInfo), w.DWORD]
    psapi.GetModuleInformation.restype = w.BOOL
    handle = kernel.OpenProcess(0x410, False, pid)  # QUERY_INFORMATION | VM_READ
    if not handle:
        raise OSError(c.get_last_error(), "OpenProcess failed")
    try:
        array, needed = (c.c_void_p * 1024)(), w.DWORD()
        if not psapi.EnumProcessModulesEx(handle, array, c.sizeof(array), c.byref(needed), 3) or needed.value > c.sizeof(array):
            raise OSError(c.get_last_error(), "Module enumeration failed")
        modules = []
        for module in array[:needed.value // c.sizeof(c.c_void_p)]:
            name, info = c.create_unicode_buffer(32768), ModuleInfo()
            if not psapi.GetModuleFileNameExW(handle, module, name, len(name)) or not psapi.GetModuleInformation(handle, module, c.byref(info), c.sizeof(info)):
                raise OSError(c.get_last_error(), "Module query failed")
            modules.append((module, info.size, Path(name.value)))
        games = [m for m in modules if m[2].name.lower() == "gtaiv.exe"]
        if len(games) != 1:
            raise ValueError("Target must contain exactly one GTAIV.exe")
        gamebase, _, path = games[0]
        data = path.read_bytes()
        pe = struct.unpack_from("<I", data, 60)[0]
        if struct.unpack_from("<H", data, pe + 24)[0] != 0x10B:
            raise ValueError("Expected 32-bit GTAIV.exe")
        preferred = struct.unpack_from("<I", data, pe + 24 + 28)[0]
        refs = set()
        for pattern in (rb"\x83\x3d.....\x74\x17\x8b\x4d\x14",
                        rb"\x83\x3d.....\x74\x15\x8b\x44\x24\x1c",
                        rb"\x83\x3d.....\x74\xef"):
            refs.update(struct.unpack_from("<I", data, m.start() + 2)[0] for m in re.finditer(pattern, data, re.S))
        if len(refs) != 1:
            raise ValueError(f"Ambiguous device-pointer references: {len(refs)}")
        def read(address, size):
            buf, count = c.create_string_buffer(size), c.c_size_t()
            if not kernel.ReadProcessMemory(handle, address, buf, size, c.byref(count)) or count.value != size:
                raise OSError(c.get_last_error(), "ReadProcessMemory failed")
            return buf.raw
        def u32(address):
            return struct.unpack("<I", read(address, 4))[0]
        pointer = refs.pop() - preferred + gamebase
        device = u32(pointer)
        if not device:
            # The launcher can relocate/unpack references differently from the
            # disk image. Scan only the live executable code sections, using
            # the same signatures; never scan arbitrary process data.
            count = struct.unpack_from("<H", data, pe + 6)[0]
            optional_size = struct.unpack_from("<H", data, pe + 20)[0]
            live_by_pattern = [set(), set(), set()]
            for index in range(count):
                section = pe + 24 + optional_size + 40 * index
                if not struct.unpack_from("<I", data, section + 36)[0] & 0x20000000:
                    continue
                _, rva, size, _ = struct.unpack_from("<4I", data, section + 8)
                if not size:
                    continue
                code = read(gamebase + rva, size)
                for pattern_index, pattern in enumerate((rb"\x83\x3d.....\x74\x17\x8b\x4d\x14",
                                rb"\x83\x3d.....\x74\x15\x8b\x44\x24\x1c",
                                rb"\x83\x3d.....\x74\xef")):
                    live_by_pattern[pattern_index].update(struct.unpack_from("<I", code, m.start() + 2)[0] for m in re.finditer(pattern, code, re.S))
            # common.ixx find_pattern chooses the first nonempty signature.
            live_refs = next((values for values in live_by_pattern if values), set())
            if len(live_refs) != 1:
                raise ValueError(f"Ambiguous live device references: {len(live_refs)}")
            pointer = live_refs.pop()
            device = u32(pointer)
            if not device:
                raise ValueError("Live device pointer is null")
        table = u32(device)
        rows = []
        for slot in (0, 81, 82, 106, 107, 108, 109, 110):
            address = u32(table + slot * 4)
            owner = next((m for m in modules if m[0] <= address < m[0] + m[1]), None)
            rows.append({"slot": slot, "address": f"{address:08X}",
                         "module": owner[2].name if owner else None,
                         "module_rva": f"{address - owner[0]:X}" if owner else None,
                         "code_prefix": read(address, 96).hex() if owner and slot in (81, 108, 110) else None})
        result = {"pid": pid, "read_only": True, "device": f"{device:08X}", "vtable": f"{table:08X}", "methods": rows}
        getter = next(m for m in rows if m["slot"] == 110)
        if getter["code_prefix"].startswith("8b4424048b80ac1100008b0889442404ffa1b8010000"):
            inner = u32(device + 0x11AC)
            inner_table = u32(inner)
            inner_methods = []
            for slot in (81, 108, 110):
                address = u32(inner_table + slot * 4)
                owner = next((m for m in modules if m[0] <= address < m[0] + m[1]), None)
                inner_methods.append({"slot": slot, "module": owner[2].name if owner else None,
                                      "module_rva": f"{address - owner[0]:X}" if owner else None})
            result["verified_facade_inner"] = {"device": f"{inner:08X}", "vtable": f"{inner_table:08X}", "methods": inner_methods}
        return result
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pid", type=int)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    report = inspect(args.pid)
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        with args.out.open("x", encoding="utf-8") as stream:
            stream.write(text)
    print(text)
