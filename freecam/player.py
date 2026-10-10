"""Emit the PAL player-component guard; no game files or assets are bundled.

Redirect PlayerPhysics vtable slot 0 to this routine after validating the input
executable. Only its native detached-camera state suppresses the player tick.
The original tick remains intact and resumes as soon as that state ends.
"""
import struct

PLAYER_VTABLE_VA = 0x19DE24
PLAYER_TICK_VA = 0x8C1E0
CAMERA_VTABLE_VA = 0x19E3D0
MAX_GUARD_BYTES = 128


def emit_guard(va):
    """Return a plain-RET/tail-call guard, preserving registers and flags.

    ECX is the PlayerPhysics component. The guarded tick has no stack arguments.
    Entity +0x154 -> gameplay owner; owner +0x40 -> native cheat manager.
    State 1 plus a live native camera identifies the original free-camera mode.
    Player physics and its own animation pause; no shared input/world state is
    written. The caller must use the exact validated PAL build.
    """
    if not isinstance(va, int) or not 0 < va <= 0xFFFFFFFF - MAX_GUARD_BYTES:
        raise ValueError('Guard address is outside 32-bit address space')
    code = bytearray(b'\x9C\x50')  # PUSHFD; PUSH EAX.
    replay_branches = []

    def replay_if(opcode):
        code.extend(b'\x0F' + bytes((opcode,)) + b'\0' * 4)
        replay_branches.append(len(code) - 4)

    code.extend(b'\x81\x39' + struct.pack('<I', PLAYER_VTABLE_VA))
    replay_if(0x85)
    code.extend(b'\x8B\x41\x20\x85\xC0')
    replay_if(0x84)
    code.extend(b'\x8B\x80\x54\x01\x00\x00\x85\xC0')
    replay_if(0x84)
    code.extend(b'\x8B\x40\x40\x85\xC0')
    replay_if(0x84)
    code.extend(b'\x83\x78\x1C\x01')
    replay_if(0x85)
    code.extend(b'\x8B\x40\x2C\x85\xC0')
    replay_if(0x84)
    code.extend(b'\x81\x38' + struct.pack('<I', CAMERA_VTABLE_VA))
    replay_if(0x85)
    code.extend(b'\x58\x9D\xC3')
    replay_va = va + len(code)
    for displacement in replay_branches:
        struct.pack_into('<i', code, displacement, replay_va - (va + displacement + 4))
    code.extend(b'\x58\x9D')
    distance = PLAYER_TICK_VA - (va + len(code) + 5)
    if not -(1 << 31) <= distance < (1 << 31):
        raise ValueError('Original player tick is outside rel32 reach')
    code.extend(b'\xE9' + struct.pack('<i', distance))
    if len(code) > MAX_GUARD_BYTES:
        raise AssertionError('Player guard exceeds its reserved area')
    return bytes(code)
