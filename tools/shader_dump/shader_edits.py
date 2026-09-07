"""Exact SM3 assembly edits and D3DX assembly helpers; no renderer assumptions."""
import re
import struct
import subprocess
import xml.etree.ElementTree as ET
import d3d9bc

def instructions(text):
    return [re.sub(r"\s+", " ", code.strip()) for line in text.replace("\0", "").splitlines()
            if (code := line.split("//", 1)[0]).strip()]


def edit_def(text, register, component, before, after):
    """Edit one audited full-vector float DEF, never register uses or comments."""
    if register < 0 or register >= 224 or component not in range(4):
        raise ValueError("Unsupported pixel constant component")
    rows = instructions(text)
    matches = [i for i, line in enumerate(rows) if re.match(rf"^def c{register},", line)]
    if len(matches) != 1:
        raise ValueError("Expected exactly one local DEF")
    i = matches[0]
    values = rows[i].split(",")[1:]
    if len(values) != 4 or struct.pack("<f", float(values[component])) != struct.pack("<f", before):
        raise ValueError("DEF literal differs from audited recipe")
    values[component] = format(after, ".9g")
    rows[i] = f"def c{register}, " + ", ".join(v.strip() for v in values)
    return "\n".join(rows) + "\n"


def patch_literal(data, register, component, before, after):
    """Patch the literal token, independently of the assembly text editor."""
    if data[:4] != struct.pack("<I", 0xFFFF0300):
        raise ValueError("Expected ps_3_0")
    if register not in range(224) or component not in range(4):
        raise ValueError("Invalid constant component")
    offset, found, ended = 4, [], False
    while offset + 4 <= len(data):
        token = struct.unpack_from("<I", data, offset)[0]
        if token == 0xFFFF:
            ended = offset + 4 == len(data)
            break
        count = ((token >> 16) & 0x7FFF) if token & 0xFFFF == 0xFFFE else ((token >> 24) & 15)
        end = offset + 4 * (count + 1)
        if end > len(data) or (count == 0 and token & 0xFFFF != 0xFFFE):
            raise ValueError("Malformed or unsupported shader token")
        if token == 0x05000051 and struct.unpack_from("<I", data, offset + 4)[0] == 0xA00F0000 | register:
            found.append(offset + 8 + 4 * component)
        offset = end
    if not ended or len(found) != 1:
        raise ValueError("Expected complete bytecode with one matching DEF")
    at = found[0]
    if data[at:at + 4] != struct.pack("<f", before):
        raise ValueError("Bytecode literal differs from audited recipe")
    result = data[:at] + struct.pack("<f", after) + data[at + 4:]
    return result, at


def assembly_at(xml_path, slot):
    text = re.sub(r"<\?xml.*?\?>", "", xml_path.read_text(encoding="utf-8-sig"), count=1)
    root = ET.fromstring("<root>" + text + "</root>")
    items = root.findall("Effect/Shaders/VertexShaders/Item") + root.findall("Effect/Shaders/PixelShaders/Item")
    path = (xml_path.parent / items[slot].findtext("File").replace("\\", "/")).resolve()
    if not path.is_relative_to(xml_path.parent.resolve()):
        raise ValueError("Assembly path escapes export directory")
    return path.read_text(encoding="utf-8-sig")


def assemble(exe, text, directory, name):
    source, target = directory / (name + ".txt"), directory / (name + ".cso")
    source.write_text(text, encoding="utf-8")
    subprocess.run([str(exe), str(source), str(target)], check=True, capture_output=True, text=True)
    data = target.read_bytes()
    shaders = d3d9bc.extract(data)
    if len(shaders) != 1 or shaders[0].data != data:
        raise ValueError("Assembler did not produce exactly one shader")
    return shaders[0]


def instruction_tokens(shader):
    """One byte slice per executable SM3 instruction, excluding only comments."""
    data = shader.stripped()
    if len(data) < 8 or data[-4:] != struct.pack('<I', 0xFFFF):
        raise ValueError('Incomplete shader program')
    result, at = [], 4
    while at < len(data) - 4:
        token = struct.unpack_from('<I', data, at)[0]
        end = at + 4 * (1 + ((token >> 24) & 15))
        if token & 0xffff in (0xfffe, 0xffff) or end > len(data) - 4:
            raise ValueError('Invalid executable token stream')
        result.append(data[at:end])
        at = end
    return result


def verify_unchanged_tokens(before_text, after_text, before, after, edits):
    """Track exact edit provenance and compare every surviving CE instruction.

    No similarity alignment is used. Only uniquely matched, explicitly reviewed
    edit blocks may replace instructions; common boundary anchors keep their
    original token identity. Raw routing hashes are pinned separately.
    """
    a, b = instructions(before_text), instructions(after_text)
    if a[0] != b[0] or before.model != after.model:
        raise ValueError('Shader model changed')
    ta, tb = instruction_tokens(before), instruction_tokens(after)
    if len(ta) != len(a) - 1 or len(tb) != len(b) - 1:
        raise ValueError('Assembly instructions do not map one-to-one to tokens')
    rows = [(line, i) for i, line in enumerate(a)]
    for edit in edits:
        old, new = edit['before'], edit['after']
        if not old:
            raise ValueError('An exact edit anchor is required')
        hits = [i for i in range(len(rows) - len(old) + 1)
                if [line for line, _ in rows[i:i + len(old)]] == old]
        if len(hits) != 1:
            raise ValueError('Reviewed edit has no unique exact match')
        at = hits[0]
        prefix = 0
        while prefix < min(len(old), len(new)) and old[prefix] == new[prefix]:
            prefix += 1
        suffix = 0
        while suffix < min(len(old), len(new)) - prefix and old[-suffix - 1] == new[-suffix - 1]:
            suffix += 1
        replacement = rows[at:at + prefix]
        end = len(new) - suffix
        replacement += [(line, None) for line in new[prefix:end]]
        if suffix:
            replacement += rows[at + len(old) - suffix:at + len(old)]
        rows[at:at + len(old)] = replacement
    if [line for line, _ in rows] != b:
        raise ValueError('Output contains an unreviewed assembly edit')
    for index, (_, original) in enumerate(rows[1:], 1):
        if original is not None and ta[original - 1] != tb[index - 1]:
            raise ValueError('An unedited stock CE instruction changed bytecode')
