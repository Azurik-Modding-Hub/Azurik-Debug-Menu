"""Emit the PAL player-component guard; no game files or assets are bundled.

Redirect PlayerPhysics vtable slot 0 to this routine after validating the input
executable. Only an active native detached camera in the player's own world
suppresses the player tick.
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
    Entity +0x154 -> GameWorld, then +0xA8 -> native camera stack. Its last
    entity is the active camera, as in the retail activation/rendering code.
    GameWorld is not the scene controller: its +0x40 is not a cheat manager.
    The camera must be the native detached-camera class and belong to this
    same GameWorld. No cached owner/global pointer survives level transitions.
    Player physics and its own animation pause; no shared input/world state is
    written. The caller must use the exact validated PAL build.
    """
    if not isinstance(va, int) or not 0 < va <= 0xFFFFFFFF - MAX_GUARD_BYTES:
        raise ValueError('Guard address is outside 32-bit address space')
    code = bytearray(b'\x9C\x50\x51\x52')  # Save flags and scratch registers.
    replay_branches = []

    def replay_if(opcode):
        code.extend(b'\x0F' + bytes((opcode,)) + b'\0' * 4)
        replay_branches.append(len(code) - 4)

    code.extend(b'\x81\x39' + struct.pack('<I', PLAYER_VTABLE_VA))
    replay_if(0x85)
    code.extend(b'\x8B\x51\x20\x85\xD2')
    replay_if(0x84)
    code.extend(b'\x8B\x92\x54\x01\x00\x00\x85\xD2')
    replay_if(0x84)
    code.extend(b'\x8B\x82\xA8\x00\x00\x00\x85\xC0')
    replay_if(0x84)
    code.extend(b'\x8B\x08\x8B\x40\x04\x3B\xC1')  # Begin/end, unsigned.
    replay_if(0x86)  # Empty or inverted stack: preserve original player tick.
    code.extend(b'\x85\xC9')
    replay_if(0x84)
    code.extend(b'\x8B\x40\xFC\x85\xC0')
    replay_if(0x84)
    code.extend(b'\x81\x38' + struct.pack('<I', CAMERA_VTABLE_VA))
    replay_if(0x85)
    code.extend(b'\x39\x90\x54\x01\x00\x00')  # Camera's GameWorld.
    replay_if(0x85)
    code.extend(b'\x5A\x59\x58\x9D\xC3')
    replay_va = va + len(code)
    for displacement in replay_branches:
        struct.pack_into('<i', code, displacement, replay_va - (va + displacement + 4))
    code.extend(b'\x5A\x59\x58\x9D')
    distance = PLAYER_TICK_VA - (va + len(code) + 5)
    if not -(1 << 31) <= distance < (1 << 31):
        raise ValueError('Original player tick is outside rel32 reach')
    code.extend(b'\xE9' + struct.pack('<i', distance))
    if len(code) > MAX_GUARD_BYTES:
        raise AssertionError('Player guard exceeds its reserved area')
    return bytes(code)
