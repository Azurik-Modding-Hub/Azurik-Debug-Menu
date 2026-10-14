"""Gate only native player controls; keep the PAL physics/animation tick live."""
import struct

PLAYER_VTABLE_VA = 0x19DE24
PLAYER_TICK_VA = 0x8C1E0
CAMERA_VTABLE_VA = 0x19E3D0
PLAYER_INPUT_HOOK_VA = 0x8500D
PLAYER_INPUT_BLOCKED_VA = 0x84FFE
PLAYER_INPUT_RESUME_VA = 0x85013
MAX_INPUT_GATE_BYTES = 176


def emit_input_gate(va):
    """Return a trampoline to the retail blocked-input or normal-input path.

    EBP is PlayerPhysics, ESI its per-frame input packet, EDI the retail zero.
    Entity +0x154 -> GameWorld, then +0xA8 -> native camera stack. Its last
    entity is the active camera, as in the retail activation/rendering code.
    GameWorld is not the scene controller: its +0x40 is not a cheat manager.
    The camera must be the native detached-camera class and belong to this
    same GameWorld. No cached owner/global pointer survives level transitions.
    Camera +0x195 must still be enabled. WHITE clears it before deferred delete,
    so an old camera pointer still present in the vector cannot trap controls.
    All registers/flags are preserved before entering an existing retail path.
    The player tick, scheduling, physics and animation are never short-circuited.
    """
    if not isinstance(va, int) or not 0 < va <= 0xFFFFFFFF - MAX_INPUT_GATE_BYTES:
        raise ValueError('Input-gate address is outside 32-bit address space')
    code = bytearray(b'\x9C\x60')  # PUSHFD; PUSHAD.
    replay_branches = []

    def replay_if(opcode):
        code.extend(b'\x0F' + bytes((opcode,)) + b'\0' * 4)
        replay_branches.append(len(code) - 4)

    code.extend(b'\x81\x7D\x00' + struct.pack('<I', PLAYER_VTABLE_VA))
    replay_if(0x85)
    code.extend(b'\x8B\x55\x20\x85\xD2')
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
    code.extend(b'\x80\xB8\x95\x01\x00\x00\x01')  # Live native camera flag.
    replay_if(0x85)
    code.extend(b'\x61\x9D')
    def jump(target):
        distance = target - (va + len(code) + 5)
        if not -(1 << 31) <= distance < (1 << 31):
            raise ValueError('Native input branch is outside rel32 reach')
        code.extend(b'\xE9' + struct.pack('<i', distance))
    jump(PLAYER_INPUT_BLOCKED_VA)
    replay_va = va + len(code)
    for displacement in replay_branches:
        struct.pack_into('<i', code, displacement, replay_va - (va + displacement + 4))
    code.extend(b'\x61\x9D\x8B\x0D' + struct.pack('<I', 0x1A9A64))
    jump(PLAYER_INPUT_RESUME_VA)
    if len(code) > MAX_INPUT_GATE_BYTES:
        raise AssertionError('Player input gate exceeds its reserved area')
    return bytes(code)
