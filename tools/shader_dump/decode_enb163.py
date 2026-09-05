"""Decode the supplied ENB 0.163 wrapper for OFFLINE inspection only.

An independent translation of its packing stub, not a DLL loader or runnable
PE rebuilder. Never executes the input. The resulting blob starts at RVA 1000
and has relocations applied for preferred base 10000000; imports are unresolved.
Accepts only the exact researched binary. Outputs must be outside the game.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct

INPUT_SHA256 = "280e2bc15485bb7b944d47bad9e7d553b6e63eba3afb97bdbc546d45fcc203c4"


def decode(data):
    if hashlib.sha256(data).hexdigest() != INPUT_SHA256:
        raise ValueError("Unsupported input: expected the researched ENB 0.163 wrapper")
    packed = bytearray(data[0x400:])
    packed[0] ^= 0xAB
    pos, bits, distance = 0, 0, -1
    out = bytearray()

    def byte():
        nonlocal pos
        if pos >= len(packed):
            raise ValueError("Truncated packed input")
        value = packed[pos]
        pos += 1
        return value

    def bit():
        nonlocal pos, bits
        carry = bits >> 31
        bits = (bits << 1) & 0xFFFFFFFF
        if not bits:
            word = struct.unpack_from("<I", packed, pos)[0]
            pos += 4
            carry = word >> 31
            bits = ((word << 1) | 1) & 0xFFFFFFFF
        return carry

    while True:
        while bit():
            out.append(byte())
            if len(out) > 0x200000:
                raise ValueError("Output exceeds expected image size")
        offset = 1
        while True:
            offset = offset * 2 + bit()
            if bit():
                break
            offset = (offset - 1) * 2 + bit()
        offset -= 3
        if offset >= 0:
            offset = ((offset << 8) | byte()) ^ 0xFFFFFFFF
            if offset == 0:
                break
            carry = offset & 1
            distance = (offset - 0x100000000) >> 1
        else:
            carry = bit()
        if carry:
            length = bit()
        else:
            length = 1
            if bit():
                length = length * 2 + bit()
            else:
                while True:
                    length = length * 2 + bit()
                    if bit():
                        break
                length += 2
        length += 2 + (distance < -0x500)
        if not -len(out) <= distance < 0 or len(out) + length > 0x200000:
            raise ValueError("Invalid back-reference")
        for _ in range(length):
            out.append(out[len(out) + distance])
    if len(out) != 1850794 or pos != 763217:
        raise ValueError("Decompression extent differs from verified input")

    i, branches = 0, 0
    while i + 5 <= len(out) and branches < 0x26D0:
        if out[i] in (0xE8, 0xE9) and out[i + 1] == 9:
            j = i + 1
            value = (int.from_bytes(out[j:j + 4], "big") & 0xFFFFFF) - j
            struct.pack_into("<I", out, j, value & 0xFFFFFFFF)
            branches += 1
            i += 5
        else:
            i += 1
    if branches != 0x26D0:
        raise ValueError("Branch filter count mismatch")

    cursor, imports = 0x1BF000, []
    while struct.unpack_from("<I", out, cursor)[0]:
        name_offset, iat = struct.unpack_from("<II", out, cursor)
        cursor += 8
        names = []
        while out[cursor]:
            cursor += 1  # The researched image uses named imports only.
            end = out.index(0, cursor)
            names.append({"iat_rva": f"{iat + 0x1000:08X}",
                          "name": out[cursor:end].decode("ascii")})
            cursor, iat = end + 1, iat + 4
        cursor += 1
        imports.append({"packed_library_name_offset": name_offset, "symbols": names})
    cursor += 4
    index, relocations = -4, 0
    while out[cursor]:
        delta = out[cursor]
        cursor += 1
        if delta > 0xEF:
            delta = ((delta & 15) << 16) | struct.unpack_from("<H", out, cursor)[0]
            cursor += 2
        index += delta
        if not 0 <= index <= len(out) - 4:
            raise ValueError("Relocation outside image")
        value = int.from_bytes(out[index:index + 4], "big") + 0x10001000
        struct.pack_into("<I", out, index, value & 0xFFFFFFFF)
        relocations += 1
    if relocations != 15832 or cursor != 0x1C3BD6:
        raise ValueError("Relocation filter extent mismatch")
    return bytes(out), {"input_sha256": INPUT_SHA256,
                       "output_sha256": hashlib.sha256(out).hexdigest(),
                       "output_bytes": len(out), "first_rva": "00001000",
                       "preferred_image_base": "10000000",
                       "packed_bytes_consumed": pos, "branches": branches,
                       "relocations": relocations, "imports": imports,
                       "input_executed": False, "runnable_pe": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dll", type=Path)
    ap.add_argument("--out", type=Path, required=True, help="new scratch directory")
    args = ap.parse_args()
    blob, report = decode(args.dll.read_bytes())
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "image-rva1000.bin").write_bytes(blob)
    (args.out / "decode.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Decoded {len(blob)} bytes without executing the input -> {args.out}")


if __name__ == "__main__":
    main()
