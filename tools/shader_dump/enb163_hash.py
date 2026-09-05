"""ENBSeries GTA IV 0.163 shader identity, recovered from its x86 wrapper.

RVA 0x1230 (PS) / 0x2400 (VS) scans DWORDs for 0x0000FFFF (including comments), then
RVA 0x226E0 hashes bytes preceding it: reflected CRC32, initial FFFFFFFF,
polynomial EDB88320, no final XOR. This is NOT crc32_stripped from the tracer.
Only validated for the wrapper SHA256 recorded in decode_enb163.py.
"""

import struct
import zlib


def hashed_length(data):
    if len(data) % 4:
        raise ValueError("Shader must contain complete DWORDs")
    model = struct.unpack_from("<I", data)[0] if len(data) >= 4 else 0
    scan_limit = 200000 if model >> 16 == 0xFFFE else 100000
    for offset in range(0, min(len(data), scan_limit * 4), 4):
        if struct.unpack_from("<I", data, offset)[0] == 0x0000FFFF:
            return offset
    # The DLL stops after 100000 PS / 200000 VS DWORDs; reject missing END here.
    raise ValueError("No aligned END word within ENB's scan limit")


def shader_hash(data):
    return (zlib.crc32(data[:hashed_length(data)]) ^ 0xFFFFFFFF) & 0xFFFFFFFF


def filename(data, stage):
    if stage not in ("ps", "vs"):
        raise ValueError("Expected ps or vs stage")
    return f"{stage}h{shader_hash(data):08X}.txt"
