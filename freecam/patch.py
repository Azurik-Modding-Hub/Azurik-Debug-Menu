"""PAL/EU patch: native cheat menu, live world, player stasis, Y HUD, WHITE exit."""
import hashlib
import struct
from .xbe import allocate, offset, sections, u32

SOURCE_SHA256 = '72e0cf6af079a4024886d9e94812d87d4a35c177135b6196d215abe138866eab'
SOURCE_SIZE = 1798144
VERSION = '0.1.0'


class Code:
    def __init__(self, va):
        self.va, self.data, self.labels, self.fixups = va, bytearray(), {}, []

    def emit(self, value):
        self.data.extend(bytes.fromhex(value) if isinstance(value, str) else value)

    def label(self, name):
        self.labels[name] = self.va + len(self.data)

    def branch(self, op, target):
        opcode = bytes.fromhex(op)
        self.emit(opcode)
        position = len(self.data)
        self.emit(b'\0' * 4)
        self.fixups.append((position, target))

    def finish(self):
        for at, target in self.fixups:
            dest = self.labels[target] if isinstance(target, str) else target
            struct.pack_into('<i', self.data, at, dest - (self.va + at + 4))
        return bytes(self.data)


def dword(value):
    return struct.pack('<I', value)


def jump(source, target, size):
    return b'\xE9' + struct.pack('<i', target - source - 5) + b'\x90' * (size - 5)


def menu_callback(va):
    c = Code(va)
    c.emit('8b81b400000085c0')  # Menu context -> cheat owner.
    c.branch('0f84', 'done')
    c.emit('8b502c85d2')
    c.branch('0f84', 'create')
    c.emit(b'\x81\x3A' + dword(0x19E3D0))
    c.branch('0f85', 'done')
    c.emit('c7401c01000000')
    c.branch('e9', 'done')
    c.label('create')
    c.emit('8b91b800000085d2')  # Same world interface used by retail callbacks.
    c.branch('0f84', 'done')
    c.emit('526a0350')  # Native action(owner, original-cheat index 3, interface).
    c.branch('e8', 0x16610)
    c.label('done')
    c.emit('c20400')
    return c.finish()


def menu_factory(va, callback):
    c = Code(va)
    c.emit('688c00000053')
    c.branch('e8', 0xE67CD)
    c.emit('50')
    c.branch('e8', 0xE4C9F)
    c.emit('85c0')
    c.branch('0f84', 'end')
    c.branch('e8', 0x1FC40)
    c.emit('8bf0')
    text = b'Free Camera'.ljust(16, b'\0')
    for at in range(0, 16, 4):
        c.emit(b'\xC7\x46' + bytes([0x1C + at]) + text[at:at + 4])
    c.emit(b'\xC7\x86\x84\x00\x00\x00' + dword(callback))
    c.emit('8bbc24e0070000')
    c.branch('e8', 0x1FBB0)
    c.label('end')
    # Entire original epilogue; allocator/callback use native calling conventions.
    c.emit('8b8424e00700005f5e5b81c4d0070000c20c00')
    return c.finish()


def camera_controls(va, state_va):
    c = Code(va)
    saved, value = state_va, state_va + 4
    c.emit('9c5052')  # Keep volatile registers/flags for untouched BACK path.
    c.emit(b'\xA1' + dword(0x3920D0))  # Show UI CVar object.
    c.emit('85c0')
    c.branch('0f84', 'white')
    c.emit(b'\x80\x3D' + dword(saved) + b'\x00')
    c.branch('0f85', 'y')
    c.emit('8b5004')
    c.emit(b'\x89\x15' + dword(value))
    c.emit(b'\xC6\x05' + dword(saved) + b'\x01')
    c.label('y')
    c.emit('83792400')
    c.branch('0f8e', 'white')
    c.emit('80794b00')
    c.branch('0f85', 'white')
    c.emit('c6414b0183700401')  # Consume Y edge; toggle only Show UI.
    c.label('white')
    c.emit('83792c00')
    c.branch('0f8e', 'back')
    c.emit('80794d00')
    c.branch('0f85', 'back')
    c.emit('c6414d01')
    c.branch('e9', 'exit')
    c.label('back')
    c.emit('83794400')
    c.branch('0f8e', 'normal')
    c.emit('80795300')
    c.branch('0f85', 'normal')
    c.emit('c6415301')
    c.label('exit')
    c.emit(b'\x80\x3D' + dword(saved) + b'\x00')
    c.branch('0f84', 'remove')
    c.emit('85c0')
    c.branch('0f84', 'remove')
    c.emit(b'\x8B\x15' + dword(value))
    c.emit('895004')
    c.label('remove')
    c.emit(b'\xC6\x05' + dword(saved) + b'\x00')
    c.emit('5a589d33db')
    c.branch('e9', 0x15E0D)  # Native camera removal, owner clearing, RET 8.
    c.label('normal')
    c.emit('5a589dd94144d81da8471a00')
    c.branch('e9', 0x15DF1)
    return c.finish()


def patch_xbe(source):
    if len(source) != SOURCE_SIZE or hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unsupported executable. This test supports only the pristine PAL/EU build.')
    signatures = {
        0x15F60: '8b401c85c07e0883f8037f03b001c332c0c3',
        0x15F40: '8b401c83f8027c0883f8037f03b001c332c0c3',
        0x13E6D: '8b8424e00700005f5e5b81c4d0070000c20c00',
        0x15DE8: 'd94144d81da8471a00',
        0x1FC40: '33c9894804894808c700083c1a00',
        0x19DE24: 'e0c10800',
    }
    for va, expected in signatures.items():
        at = offset(source, va)
        if source[at:at + len(bytes.fromhex(expected))] != bytes.fromhex(expected):
            raise ValueError(f'Unexpected PAL signature at {va:#x}')
    output, raw, va = allocate(source)
    output[raw:raw + 8] = b'FCDBG01\0'
    used = 32
    routines = {}
    def add(name, builder):
        nonlocal used
        used = (used + 15) & ~15
        target = va + used
        body = builder(target)
        if used + len(body) > 2048:
            raise ValueError('Freecam section overflow')
        output[raw + used:raw + used + len(body)] = body
        routines[name] = {'va': target, 'size': len(body)}
        used += len(body)
        return target
    callback = add('menuCallback', menu_callback)
    factory = add('menuFactory', lambda addr: menu_factory(addr, callback))
    controls = add('cameraControls', lambda addr: camera_controls(addr, va + 8))
    from .player import emit_guard
    player = add('playerStasis', emit_guard)
    edits = [(0x15F60, bytes.fromhex('ebde90')),
             (0x13E6D, jump(0x13E6D, factory, 7)),
             (0x15DE8, jump(0x15DE8, controls, 9)),
             (0x19DE24, dword(player))]
    for address, body in edits:
        at = offset(output, address)
        output[at:at + len(body)] = body
    if source[0xE6717] != 0:
        raise ValueError('Cheat menu default drifted')
    output[0xE6717] = 1  # L3 + START exposes the retail menu. No camera shortcut remap.
    # Verify every original raw section byte outside the explicit hook whitelist.
    ranges = [(offset(source, address), len(body)) for address, body in edits] + [(0xE6717, 1)]
    for item in sections(source)[1]:
        before = bytearray(source[item['raw']:item['raw'] + item['raw_size']])
        for at, size in ranges:
            if item['raw'] <= at < item['raw'] + item['raw_size']:
                local = at - item['raw']
                before[local:local + size] = output[at:at + size]
        if before != output[item['raw']:item['raw'] + item['raw_size']]:
            raise ValueError('Unexpected change outside freecam hooks')
    return bytes(output), dict(version=VERSION, sourceSha256=SOURCE_SHA256,
        outputSha256=hashlib.sha256(output).hexdigest(), sectionRaw=raw, sectionVA=va,
        sectionBytes=2048, routines=routines, hooks=[{'offset': at, 'bytes': size} for at, size in ranges],
        originalCheatPreserved=True, nativeGameTested=False)
