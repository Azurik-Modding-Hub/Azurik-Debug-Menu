"""Direct controller chords for the native debug menu, not cheat-sequence input.

Poll from the live cheat-owner dispatcher in normal and Freecam gameplay.
Only consumed-edge flags are written; analog values and the camera stay intact.
"""
from .patch import Code, dword

ENTRY = 0x15DA0
STOLEN = bytes.fromhex('518b471c83f804')


def emit_poll(va, state):
    """stdcall(owner, world_interface) -> bool; state holds four mode bytes.

    Mode 1: WHITE+A+B. Mode 2: original L3+START alternative. A chord is
    rearmed only after all of its buttons are released. The same chord cannot
    stack windows, activate a selected row or immediately exit the Freecam.
    """
    c = Code(va)
    c.emit('558bec83ec085356578b7d088b750c')
    c.emit(b'\xA1' + dword(0x1A9A64))
    c.emit('83f804');c.branch('0f87', 'normal')
    c.branch('0f85', 'index');c.emit('33c0')  # Native index 4 means controller 0.
    c.label('index')
    c.emit(b'\x8D\x90' + dword(state))
    c.emit('8955fc6bc054');c.emit(b'\x8D\x98' + dword(0x37DE38))
    c.emit('c745f800000000803a01');c.branch('0f84', 'held_white')
    c.emit('803a02');c.branch('0f84', 'held_legacy')
    for button in [0x18, 0x1C, 0x2C]:
        c.emit(bytes([0x83, 0x7B, button, 0]));c.branch('0f8e', 'legacy')
    c.emit('c60201');c.branch('e9', 'validate')
    c.label('legacy')
    for button in [0x38, 0x40]:
        c.emit(bytes([0x83, 0x7B, button, 0]));c.branch('0f8e', 'normal')
    c.emit('c60202');c.branch('e9', 'validate')
    c.label('held_white')
    for button in [0x18, 0x1C, 0x2C]:
        c.emit(bytes([0x83, 0x7B, button, 0]));c.branch('0f8f', 'held')
    c.branch('e9', 'release')
    c.label('held_legacy')
    for button in [0x38, 0x40]:
        c.emit(bytes([0x83, 0x7B, button, 0]));c.branch('0f8f', 'held')
    c.label('release');c.emit('c60200');c.branch('e9', 'normal')
    c.label('held');c.emit('c745f801000000')
    c.label('validate')
    c.emit('85ff');c.branch('0f84', 'normal')
    c.emit('837f1c04');c.branch('0f87', 'normal')
    c.emit('85f6');c.branch('0f84', 'normal')
    c.emit('8bce8b0685c0');c.branch('0f84', 'normal')
    c.emit('8b0085c0');c.branch('0f84', 'normal')
    c.emit('ffd085c0');c.branch('0f84', 'normal')
    c.emit('83b8cc00000000');c.branch('0f84', 'normal')
    c.emit('8b55fc803a01');c.branch('0f85', 'consume_legacy')
    c.emit('66c743480101c6434d01');c.branch('e9', 'open')
    c.label('consume_legacy');c.emit('c6435001c6435201')
    c.label('open')
    c.emit('837df800');c.branch('0f85', 'handled')
    c.emit('837f1c01');c.branch('0f87', 'handled')
    c.emit('8b4720394724');c.branch('0f85', 'handled')
    c.emit('566a0057');c.branch('e8', 0x16610)
    c.label('handled');c.emit('b801000000');c.branch('e9', 'done')
    c.label('normal');c.emit('33c0')
    c.label('done');c.emit('5f5e5b8be55dc20800')
    return c.finish()


def emit_dispatch(va, poll):
    """Hook 15DA0 without changing its caller's two-argument stack contract."""
    c = Code(va);c.emit('9c608b4424285057')
    c.branch('e8', poll);c.emit('85c0');c.branch('0f85', 'handled')
    c.emit('619d');c.emit(STOLEN);c.branch('e9', ENTRY + len(STOLEN))
    c.label('handled');c.emit('619dc20800')
    return c.finish()
