"""Bounded XBE section reader and isolated section allocation for the PAL build."""
import struct


def u32(data, at):
    return struct.unpack_from('<I', data, at)[0]


def sections(data):
    if len(data) < 0x178 or data[:4] != b'XBEH':
        raise ValueError('Invalid XBE header')
    base, count, table = u32(data, 0x104), u32(data, 0x11C), u32(data, 0x120)
    table -= base
    if not 1 <= count <= 64 or table < 0 or table + count * 56 > len(data):
        raise ValueError('Invalid XBE section table')
    result = []
    for index in range(count):
        off = table + index * 56
        flags, va, size, raw, raw_size, name = struct.unpack_from('<6I', data, off)
        name -= base
        if raw + raw_size > len(data) or name < 0 or name >= len(data):
            raise ValueError('XBE section outside file')
        end = data.find(b'\0', name, min(name + 64, len(data)))
        if end < 0:
            raise ValueError('Unterminated XBE section name')
        result.append(dict(name=data[name:end].decode('ascii'), flags=flags,
                           va=va, size=size, raw=raw, raw_size=raw_size, header=off))
    return base, result


def offset(data, va):
    for item in sections(data)[1]:
        delta = va - item['va']
        if 0 <= delta < min(item['size'], item['raw_size']):
            return item['raw'] + delta
    raise ValueError(f'Unmapped XBE address {va:#x}')


def allocate(data, size=2048):
    """Return a private mutable image, plus raw/VA of a new read/write code section.

    The packed header's tail moves by one 56-byte section entry. Existing raw
    bodies and virtual addresses stay fixed. This policy follows the section
    expansion audited by Elemental Games Modding, with no dependency on it.
    """
    base, old_sections = sections(data)
    old_size = u32(data, 0x108)
    table = u32(data, 0x120) - base
    end = table + len(old_sections) * 56
    label = b'FCDEBUG\0'
    new_size = old_size + 56 + len(label)
    if (end > old_size or new_size > min(s['raw'] for s in old_sections)
            or base + new_size > min(s['va'] for s in old_sections)
            or any(data[old_size:new_size])):
        raise ValueError('No validated header room for freecam section')
    output = bytearray(data)
    output[end + 56:old_size + 56] = data[end:old_size]
    output[end:end + 56] = b'\0' * 56
    output[old_size + 56:new_size] = label
    pointer_fields = (0x118, 0x14C, 0x150, 0x154, 0x15C, 0x160,
                      0x164, 0x168, 0x16C, 0x170)
    for field in pointer_fields:
        value = u32(output, field)
        if base + end <= value < base + old_size:
            struct.pack_into('<I', output, field, value + 56)
    for item in old_sections:
        for relative in (20, 28, 32):
            field = item['header'] + relative
            value = u32(output, field)
            if base + end <= value < base + old_size:
                struct.pack_into('<I', output, field, value + 56)
    raw = (len(output) + 4095) & ~4095
    va = (max(s['va'] + s['size'] for s in old_sections) + 4095) & ~4095
    output.extend(b'\0' * (raw + size - len(output)))
    refs = u32(output, table + 28)
    struct.pack_into('<9I', output, end, 7, va, size, raw, size,
                     base + old_size + 56, 0, refs, refs)
    struct.pack_into('<I', output, 0x108, new_size)
    struct.pack_into('<I', output, 0x10C, ((va + size + 4095) & ~4095) - base)
    struct.pack_into('<I', output, 0x11C, len(old_sections) + 1)
    sections(output)
    return output, raw, va
