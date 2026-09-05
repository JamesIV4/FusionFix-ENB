"""Minimal Direct3D 9 shader-bytecode reader.

Everything in this package needs the same three things: pull the shader blobs
out of a RAGE ``.fxc`` container, hash them the way an external tool such as
ENBSeries would, and normalise the disassembly so two shaders can be compared
without tripping over register allocation noise.

Reference for the token stream: "Direct3D Shader Codes" (D3D9 SM1-SM3).
    * version token     0xFFFFxxyy (pixel) / 0xFFFExxyy (vertex)
    * comment token     low word == 0xFFFE, length in bits 16..30
    * end token         0x0000FFFF
    * instruction token low word == opcode, length in bits 24..27
"""

import os
import re
import struct
import zlib

from enb163_hash import shader_hash

END_TOKEN = 0x0000FFFF
COMMENT_MASK = 0x0000FFFF
COMMENT_ID = 0x0000FFFE

VERSION_TOKENS = {
    0xFFFF0300: "ps_3_0",
    0xFFFF0201: "ps_2_x",
    0xFFFF0200: "ps_2_0",
    0xFFFF0104: "ps_1_4",
    0xFFFF0103: "ps_1_3",
    0xFFFE0300: "vs_3_0",
    0xFFFE0200: "vs_2_0",
    0xFFFE0101: "vs_1_1",
}


class Shader:
    """One extracted shader blob."""

    def __init__(self, source, offset, model, data):
        self.source = source        # container file the blob came from
        self.offset = offset        # byte offset inside that container
        self.model = model          # "ps_3_0", "vs_3_0", ...
        self.data = data            # full blob, version token .. end token

    @property
    def stage(self):
        return "ps" if self.model.startswith("ps") else "vs"

    @property
    def size(self):
        return len(self.data)

    def stripped(self):
        """The blob with every comment block (CTAB, source names) removed.

        Two shaders that differ only in the compiler version stamped into their
        CTAB are the same shader for our purposes, so most comparisons should
        use this rather than the raw blob.
        """
        out = bytearray(self.data[:4])
        for kind, tok, payload in self._walk():
            if kind == "comment":
                continue
            out += struct.pack("<I", tok) + payload
            if kind == "end":
                break
        return bytes(out)

    def _walk(self):
        """Yield (kind, token, payload_bytes) for each token group."""
        data = self.data
        n = len(data)
        i = 4
        while i + 4 <= n:
            tok = struct.unpack_from("<I", data, i)[0]
            if tok == END_TOKEN:
                yield "end", tok, b""
                return
            if (tok & COMMENT_MASK) == COMMENT_ID:
                length = (tok >> 16) & 0x7FFF
                payload = data[i + 4:i + 4 + length * 4]
                yield "comment", tok, payload
                i += 4 + length * 4
                continue
            length = (tok >> 24) & 0x0F
            payload = data[i + 4:i + 4 + length * 4]
            yield "instruction", tok, payload
            i += 4 + length * 4
        return

    def opcodes(self):
        """The opcode sequence, ignoring operands entirely.

        A coarse fingerprint: robust against register renumbering and constant
        edits, so it survives the changes ENB and FusionFix both make.
        """
        return [tok & 0xFFFF for kind, tok, _ in self._walk() if kind == "instruction"]

    def hashes(self):
        raw = self.data
        clean = self.stripped()
        return {
            "enb163": "%08X" % shader_hash(raw),
            "crc32": "%08X" % (zlib.crc32(raw) & 0xFFFFFFFF),
            "crc32_stripped": "%08X" % (zlib.crc32(clean) & 0xFFFFFFFF),
            "fnv1a_stripped": "%08X" % fnv1a32(clean),
            "opcode_crc32": "%08X" % (zlib.crc32(
                b"".join(struct.pack("<H", o) for o in self.opcodes())) & 0xFFFFFFFF),
        }


def fnv1a32(buf):
    h = 0x811C9DC5
    for c in buf:
        h = ((h ^ c) * 0x01000193) & 0xFFFFFFFF
    return h


def _blob_end(data, start):
    """Walk tokens from ``start`` and return the offset just past the end token.

    Returns None when the stream runs off the end of the buffer or hits a token
    group whose declared length would overrun it, which is how a false-positive
    version token inside some unrelated payload gets rejected.
    """
    n = len(data)
    i = start + 4
    while i + 4 <= n:
        tok = struct.unpack_from("<I", data, i)[0]
        if tok == END_TOKEN:
            return i + 4
        if (tok & COMMENT_MASK) == COMMENT_ID:
            length = (tok >> 16) & 0x7FFF
        else:
            length = (tok >> 24) & 0x0F
        i += 4 + length * 4
    return None


def extract(data, source=""):
    """Extract every well-formed shader blob from ``data``.

    Scans byte by byte for a version token, then validates the candidate by
    walking its token stream to an end token. Byte-by-byte matters: RAGE ``.fxc``
    containers do not align their shader blobs, and a 4-byte-aligned scan misses
    roughly nine out of ten of them.

    Advancing past a validated match, rather than past its first byte, is what
    keeps the copy of the version token inside each shader's CTAB block from
    being reported as a second shader.
    """
    out = []
    n = len(data)
    i = 0
    while i + 4 <= n:
        tok = struct.unpack_from("<I", data, i)[0]
        model = VERSION_TOKENS.get(tok)
        if model is not None:
            end = _blob_end(data, i)
            if end is not None:
                out.append(Shader(source, i, model, data[i:end]))
                i = end
                continue
        i += 1
    return out


def extract_file(path):
    with open(path, "rb") as fh:
        return extract(fh.read(), os.path.basename(path))


def iter_fxc(root):
    """Yield every ``.fxc`` path under ``root`` (or ``root`` itself if a file)."""
    if os.path.isfile(root):
        yield root
        return
    for dirpath, _, filenames in os.walk(root):
        for name in sorted(filenames):
            if name.lower().endswith(".fxc"):
                yield os.path.join(dirpath, name)


# --- disassembly normalisation -------------------------------------------

def normalise_asm(text):
    """Reduce fxc/ENB shader assembly to a comparable instruction list.

    Drops comments, blank lines and ``def``/``defi``/``defb`` constant
    declarations, then collapses whitespace. ``def`` goes because that is
    precisely what both ENB and FusionFix edit, and what we want to compare is
    the *body* underneath those edits.
    """
    lines = []
    for line in text.splitlines():
        line = line.split("//", 1)[0].strip()
        if not line:
            continue
        head = line.split(None, 1)[0]
        if head in ("def", "defi", "defb"):
            continue
        lines.append(" ".join(line.split()))
    return lines


SAMPLER_DCL = re.compile(r"^dcl_(?:2d|cube|volume)\s+s(\d+)")


def declarations(text):
    """The shader's interface signature: (input declarations, sampler indices).

    Inputs are the ``dcl_*`` lines that bind varyings and ``vPos``/``vFace``;
    samplers are the texture stages it declares. Together these describe what a
    shader consumes without saying anything about what it computes, which makes
    them a much stronger discriminator than instruction similarity when several
    shaders in a family do nearly the same thing.

    ENB only ever *adds* to a shader it replaces -- an extra sampler for its
    detail texture, never a removed varying -- so for a correct pairing the
    game shader's inputs match exactly and its samplers are a subset.
    """
    inputs, samplers = [], set()
    for line in text.splitlines():
        line = line.split("//", 1)[0].strip()
        if not line.startswith("dcl"):
            continue
        line = " ".join(line.split())
        m = SAMPLER_DCL.match(line)
        if m:
            samplers.add(int(m.group(1)))
        else:
            inputs.append(line)
    return sorted(inputs), samplers
