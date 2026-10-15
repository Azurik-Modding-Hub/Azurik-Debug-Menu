"""Timed WHITE -> A -> B gesture for the native debug menu.

Each controller uses 16 bytes: mode, seconds remaining, previous raw-button
mask and a reserved word. Only input-edge flags are consumed, not analog data.
"""
from .patch import Code, dword

ENTRY = 0x15DA0
STOLEN = bytes.fromhex('518b471c83f804')
CONTROLLER_STATE_BYTES = 16
WINDOW_SECONDS = 1.0


def emit_poll(va, state):
    """stdcall(owner, Scene interface, delta seconds) -> handled; RET 12.

    Modes: idle=0, wait A=1, wait B=2, opened/wait release=3, legacy held=4.
    WHITE starts one second for A and B, including gaps between released keys.
    Overlapping presses and all three on one frame also complete the gesture.
    Pending steps return normally, so WHITE alone still exits Freecam.
    """
    c = Code(va)
    c.emit('558bec83ec105356578b7d088b750c')
    c.emit(b'\xA1' + dword(0x1A9A64))
    c.emit('83f804');c.branch('0f87', 'normal')
    c.branch('0f85', 'index');c.emit('33c0')
    c.label('index')
    c.emit('8bd0c1e204');c.emit(b'\x81\xC2' + dword(state))
    c.emit('8955fc6bc054');c.emit(b'\x8D\x98' + dword(0x37DE38))
    c.emit('33c9')
    for button, bit in [(0x2C,1),(0x18,2),(0x1C,4),(0x40,8),(0x38,16)]:
        label='mask_'+str(bit)
        c.emit(bytes([0x83,0x7B,button,0]));c.branch('0f8e',label)
        c.emit(bytes([0x83,0xC9,bit]));c.label(label)
    c.emit('894df88b4208f7d023c18945f4894a08')
    c.emit('833a03');c.branch('0f84','held_white')
    c.emit('833a04');c.branch('0f84','held_legacy')
    c.emit('8bc183e01883f818');c.branch('0f85','gesture')
    c.emit('f745f418000000');c.branch('0f84','gesture')
    c.emit('c70204000000c745f001000000');c.branch('e9','validate')
    c.label('held_white');c.emit('f7c107000000');c.branch('0f85','held')
    c.branch('e9','reset')
    c.label('held_legacy');c.emit('f7c118000000');c.branch('0f84','reset')
    c.label('held');c.emit('c745f002000000');c.branch('e9','validate')
    c.label('gesture')
    c.emit('f745f401000000');c.branch('0f84','countdown')
    c.emit('c70201000000c742040000803f');c.branch('e9','pending')
    c.label('countdown')
    c.emit('833a01');c.branch('0f84','tick')
    c.emit('833a02');c.branch('0f85','normal')
    c.label('tick')
    c.emit('8b451085c0');c.branch('0f88','reset')
    c.emit('3d0000803f');c.branch('0f87','reset')
    c.emit('d94204d86510d95a04837a0400');c.branch('0f8c','reset')
    c.label('pending');c.emit('c745f000000000')
    c.label('validate')
    c.emit('85ff');c.branch('0f84','reset')
    c.emit('837f1c04');c.branch('0f87','reset')
    c.emit('85f6');c.branch('0f84','reset')
    c.emit('8bce8b0685c0');c.branch('0f84','reset')
    c.emit('8b0085c0');c.branch('0f84','reset')
    c.emit('ffd085c0');c.branch('0f84','reset')
    # Scene virtual 0 returns World; virtual 4 returns the current player.
    # World+CC is a controls object, not proof that the player has spawned.
    c.emit('8bce8b068b400485c0');c.branch('0f84','reset')
    c.emit('ffd085c0');c.branch('0f84','reset')
    c.emit('8b55fc837df000');c.branch('0f85','consume')
    c.emit('833a01');c.branch('0f85','step_b')
    c.emit('f745f402000000');c.branch('0f84','normal')
    c.emit('c70202000000c6434801')
    c.label('step_b');c.emit('833a02');c.branch('0f85','normal')
    c.emit('f745f404000000');c.branch('0f84','normal')
    c.emit('c70203000000c7420400000000')
    c.label('consume')
    c.emit('833a04');c.branch('0f84','consume_legacy')
    c.emit('66c743480101c6434d01');c.branch('e9','open')
    c.label('consume_legacy');c.emit('c6435001c6435201')
    c.label('open')
    c.emit('837df002');c.branch('0f84','handled')
    c.emit('837f1c01');c.branch('0f87','handled')
    # Native close (13870) hides the menu but retains its vector entry.
    # Action 0 reuses that root; only an empty vector allocates a new one.
    c.emit('566a0057');c.branch('e8',0x16610)
    c.label('handled');c.emit('b801000000');c.branch('e9','done')
    c.label('reset');c.emit('8b55fcc70200000000c7420400000000')
    c.label('normal');c.emit('33c0')
    c.label('done');c.emit('5f5e5b8be55dc20c00')
    return c.finish()


def emit_dispatch(va, poll):
    """Preserve the native two arguments and forward its delta to the poll."""
    c = Code(va);c.emit('9c608b4424288b54242c525057')
    c.branch('e8',poll);c.emit('85c0');c.branch('0f85','handled')
    c.emit('619d');c.emit(STOLEN);c.branch('e9',ENTRY+len(STOLEN))
    c.label('handled');c.emit('619dc20800')
    return c.finish()
