"""Actual common scheduler entry to native debug-menu construction.

Optional local EU executable. Retail input dispatch, action 0, root/menu-row
constructors, vector insertion and menu update execute as native instructions.
Heap allocation and the optional level-title accessor are engine boundaries;
the actual Scene getters return the current World and player Entity.
No game assets are bundled and this is not an Xemu gameplay assertion.
"""
import os
from pathlib import Path
import struct

import pytest
from unicorn import UC_HOOK_CODE
from unicorn import x86_const as r

import test_x86 as native
from freecam import laboratory


CATALOG = [
    dict(label='Text boxes', children=[dict(label='Training', kind=laboratory.POPUP,
                                          key='loc/english/popups/training1')]),
    dict(label='Oracles', children=[dict(label='Eldwin', kind=laboratory.VOICE,
                                       key='loc/english/speech/eld_level_intros/eld_w1_hint1')]),
]


@pytest.fixture(scope='module')
def activation_image():
    path = os.environ.get('AZURIK_XBE')
    if not path:
        pytest.skip('Optional native EU audit; provide your own pristine executable.')
    return laboratory.patch_xbe(Path(path).read_bytes(), CATALOG)


@pytest.mark.parametrize('initial_state,chord,buttons,latches', [
    (0,'white-a-b',(0x2C,0x18,0x1C),(0x4D,0x48,0x49)),
    (1,'white-a-b',(0x2C,0x18,0x1C),(0x4D,0x48,0x49)),
    (0,'l3-start',(0x40,0x38),(0x52,0x50)),
    (1,'l3-start',(0x40,0x38),(0x52,0x50)),
    (0,'timed-white-a-b',(0x2C,0x18,0x1C),(0x4D,0x48,0x49)),
])
def test_common_native_scheduler_opens_complete_menu_once_per_press(
        activation_image, monkeypatch, chord, buttons, latches, initial_state):
    image, metadata = activation_image
    assert {'hotkeyPoll', 'hotkeyDispatch'} <= metadata['routines'].keys()
    assert metadata['hotkeyStateVA'] > 0
    assert metadata['activation']['reuseRetainedMenu'] is True
    monkeypatch.setattr(native, 'ROOT_MENU_TITLE', 'Debug Menu - ' + laboratory.VERSION)
    u = native.machine(image)
    u.mem_map(0x720000, 0x10000)
    world, actor, interface_vtable = 0x70A000, 0x70B000, 0x70E000
    stack = native.STACK + 0x1000
    next_heap = [0x720000]
    allocations, entered = [], []

    def reserve(size):
        assert 0 < size <= 0x1000
        address = next_heap[0]
        next_heap[0] += (size + 15) & ~15
        assert next_heap[0] < 0x730000
        return address

    def heap(uc):
        uc.reg_write(r.UC_X86_REG_EAX, native.HEAP)
        native.return_from(uc)

    def allocate(uc):
        sp = uc.reg_read(r.UC_X86_REG_ESP)
        assert native.get(uc, sp + 4) == native.HEAP
        assert native.get(uc, sp + 8) == 0
        size = native.get(uc, sp + 12)
        allocations.append(size)
        uc.reg_write(r.UC_X86_REG_EAX, reserve(size))
        native.return_from(uc, 12)

    def vector(uc):
        uc.reg_write(r.UC_X86_REG_EAX, reserve(uc.reg_read(r.UC_X86_REG_EAX)))
        native.return_from(uc)

    def level_name(uc):
        uc.reg_write(r.UC_X86_REG_EAX, 0)
        native.return_from(uc)

    handlers = {0xE67CD: heap, 0xE4C9F: allocate,
                0x185E0: vector, 0x8D960: level_name}
    # Real Scene vtable/getters: 513A0 reads +2C; 513B0 reads +30.
    native.put(u,native.INTERFACE,0x1A0E58)
    native.put(u,native.INTERFACE+0x2C,world)
    native.put(u,native.INTERFACE+0x30,actor)
    native.put(u,native.INTERFACE+0x40,native.OWNER)
    native.put(u, world + 0xCC, actor)
    native.put(u, native.OWNER + 0x1C, initial_state)
    native.put(u, native.OWNER + 0x20, native.VECTOR)
    native.put(u, native.OWNER + 0x24, native.VECTOR)
    native.put(u, native.OWNER + 0x28, native.VECTOR + 0x40)
    if initial_state:
        native.put(u, native.OWNER + 0x2C, native.CAMERA)
        native.put(u, native.CAMERA, 0x19E3D0)
    native.put(u, 0x1A9A64, 0)
    native.put(u, 0x38EA10, native.HUD)
    native.put(u, native.HUD + 4, 0)
    preserved = {r.UC_X86_REG_EBX: 0x11223344,
                 r.UC_X86_REG_EBP: native.INTERFACE,
                 r.UC_X86_REG_ESI: 0x3C23D70A,
                 r.UC_X86_REG_ECX: 0x55667788}

    def trace(uc, address, size, data):
        if address in (0x16610, 0x138D0):
            entered.append(address)
            if address == 0x16610:
                sp = uc.reg_read(r.UC_X86_REG_ESP)
                assert [native.get(uc, sp + 4 + i * 4) for i in range(3)] == [
                    native.OWNER, 0, native.INTERFACE]

    u.hook_add(UC_HOOK_CODE, trace)

    def frame(pressed):
        held=set(buttons) if pressed is True else (set() if pressed is False else set(pressed))
        u.mem_write(native.CONTROLLER, b'\0' * 0x48)
        # The native input manager keeps consumed edges while a button is
        # held, then clears them on release. Do not fabricate fresh edges.
        for button,latch in zip(buttons,latches):
            if button not in held:u.mem_write(native.CONTROLLER+latch,b'\0')
        # Nonzero unrelated analog axes must survive the complete opening.
        u.mem_write(native.CONTROLLER, struct.pack('<2f', 0.125, -0.25))
        if held:
            for field in held:
                native.put(u, native.CONTROLLER + field, 0x3F800000)
        pressure = bytes(u.mem_read(native.CONTROLLER, 0x48))
        native.put(u, stack, native.EXIT)
        u.reg_write(r.UC_X86_REG_ESP, stack)
        for register, value in preserved.items():
            u.reg_write(register, value)
        # Execute the real caller's owner lookup and pushes, not a synthetic
        # direct emitter call. 55BB9 calls 15DA0 and RET 8 rejoins at 55BBE.
        native.run_until(u, 0x55BB4, handlers, targets=(0x55BBE,), count=50000)
        assert u.reg_read(r.UC_X86_REG_ESP) == stack
        assert u.reg_read(r.UC_X86_REG_EDI) == native.OWNER
        assert all(u.reg_read(reg) == value for reg, value in preserved.items())
        assert bytes(u.mem_read(native.CONTROLLER, 0x48)) == pressure

    if chord=='timed-white-a-b':
        for held in [{0x2C},set(),{0x18},set()]:
            frame(held)
            assert not entered and not allocations
        frame({0x1C})
    else:frame(True)
    assert entered == [0x16610, 0x138D0]
    assert native.get(u, native.OWNER + 0x1C) == 2
    assert native.get(u, native.OWNER + 0x24) == native.VECTOR + 4
    assert all(bytes(u.mem_read(native.CONTROLLER + field, 1)) == b'\1'
               for field in latches)
    assert native.get(u, native.OWNER + 0x2C) == (native.CAMERA if initial_state else 0)
    context = native.get(u, native.VECTOR)
    assert native.get(u, context + 0xB4) == native.OWNER
    assert native.get(u, context + 0xB8) == native.INTERFACE
    parent = native.get(u, context + 4)
    title = bytes(u.mem_read(parent + 0x1C, 100)).split(b'\0')[0].decode('ascii')
    assert title == 'Debug Menu - ' + laboratory.VERSION
    begin, end = native.get(u, parent + 0x10), native.get(u, parent + 0x14)
    labels = [bytes(u.mem_read(native.get(u, at) + 0x1C, 100)).split(b'\0')[0].decode('ascii')
              for at in range(begin, end, 4)]
    assert labels == ['Change level...', 'Play Movie...', 'Game state...',
                      'Freecam', 'Text boxes', 'Oracles']
    count = len(allocations)
    assert count == 8
    frame(True)
    assert len(allocations) == count and entered == [0x16610, 0x138D0]

    # Execute the actual ordinary close callback: it hides the root and retains
    # its vector entry. Reopening must use that same root, not allocate/stack.
    for _ in range(4):
        native.put(u, stack, native.EXIT)
        u.reg_write(r.UC_X86_REG_ESP, stack)
        u.reg_write(r.UC_X86_REG_ECX, context)
        native.run_until(u, 0x13870, handlers, count=50000)
        assert u.reg_read(r.UC_X86_REG_ESP) == stack + 4
        assert native.get(u, native.OWNER + 0x1C) == initial_state
        assert native.get(u, native.OWNER + 0x24) == native.VECTOR + 4
        calls = len(entered)
        frame(True)
        assert len(entered) == calls and len(allocations) == count
        frame(False)
        assert len(entered) == calls and len(allocations) == count
        if chord == 'timed-white-a-b':
            for held in [{0x2C}, set(), {0x18}, set()]:
                frame(held)
                assert len(entered) == calls
            frame({0x1C})
        else:
            frame(True)
        assert entered[-1] == 0x16610 and len(entered) == calls + 1
        assert len(allocations) == count
        assert native.get(u, native.VECTOR) == context
        assert native.get(u, native.OWNER + 0x24) == native.VECTOR + 4
        assert native.get(u, native.OWNER + 0x1C) == 2

    # A genuinely removed vector entry must still permit a fresh allocation.
    # Destruction itself is outside this activation test's engine boundaries.
    native.put(u, native.OWNER + 0x1C, initial_state)
    native.put(u, native.OWNER + 0x24, native.VECTOR)
    frame(True)
    assert len(allocations) == count
    frame(False)
    assert len(allocations) == count
    frame(True)
    assert len(allocations) == count * 2
    assert entered == [0x16610, 0x138D0] + [0x16610] * 4 + [0x16610, 0x138D0]
