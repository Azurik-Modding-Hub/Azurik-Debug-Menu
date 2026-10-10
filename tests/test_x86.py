"""x86 ABI checks, including optional read-only tests against the retail XBE.

Set AZURIK_XBE to your own pristine PAL/EU default.xbe to enable native tests.
Synthetic emitter tests do not require any game asset. Complex allocation,
camera construction and destruction are intercepted; this is not a game test.
"""
import hashlib
import os
from pathlib import Path
import struct

import pytest
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn import x86_const as r

from freecam.patch import (SOURCE_SHA256, patch_xbe, menu_callback,
                           camera_controls, menu_factory)
from freecam.xbe import sections, u32

CODE, EXIT, STACK = 0x500000, 0x510000, 0x601000
OWNER, CAMERA, HUD, CONTEXT, ROW, PARENT, VECTOR, INTERFACE, HEAP = (
    0x700000 + i * 0x1000 for i in range(9))
STATE = 0x709000
CONTROLLER = 0x37DE38
HUD_GLOBAL = 0x3920D0


def put(u, address, value):
    u.mem_write(address, struct.pack('<I', value))


def get(u, address):
    return struct.unpack('<I', u.mem_read(address, 4))[0]


def machine(image=None):
    u = Uc(UC_ARCH_X86, UC_MODE_32)
    if image is not None:
        base, items = sections(image)
        end = (max(s['va'] + s['size'] for s in items) + 4095) & ~4095
        u.mem_map(base, end - base)
        u.mem_write(base, image[:u32(image, 0x108)])
        for item in items:
            u.mem_write(item['va'], image[item['raw']:item['raw'] + item['raw_size']])
    else:
        # Synthetic only: globals/read-only constants used by emitted controls.
        u.mem_map(0x15000, 0x1000)
        u.mem_map(0x1A4000, 0x1000)
        u.mem_map(0x37D000, 0x2000)
        u.mem_map(0x390000, 0x3000)
        u.mem_map(0x16000, 0x1000)
    for address, size in ((CODE, 0x1000), (EXIT, 0x1000), (0x600000, 0x3000),
                          (OWNER, 0x10000)):
        u.mem_map(address, size)
    return u


def return_from(u, args=0):
    sp = u.reg_read(r.UC_X86_REG_ESP)
    u.reg_write(r.UC_X86_REG_EIP, get(u, sp))
    u.reg_write(r.UC_X86_REG_ESP, sp + 4 + args)


def run_until(u, start, handlers=None, targets=(EXIT,), count=2000):
    routes = []
    handlers = handlers or {}
    def hook(uc, address, size, userdata):
        if address in handlers:
            handlers[address](uc)
        elif address in targets:
            routes.append(address)
            uc.emu_stop()
    handle = u.hook_add(UC_HOOK_CODE, hook)
    try:
        u.emu_start(start, 0, count=count)
    finally:
        u.hook_del(handle)
    assert len(routes) == 1, 'The x86 routine did not reach exactly one expected boundary'
    return routes[0]


@pytest.fixture(scope='module')
def retail():
    value = os.environ.get('AZURIK_XBE')
    if not value:
        pytest.skip('Set AZURIK_XBE to enable the private PAL native executable audit')
    source = Path(value).read_bytes()
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA256, 'AZURIK_XBE must be pristine PAL/EU'
    image, metadata = patch_xbe(source)
    return source, image, metadata


@pytest.mark.parametrize('kind', ['create', 'existing', 'foreign-camera', 'no-owner', 'no-interface'])
def test_synthetic_menu_callback_native_argument_order_and_ret4(kind):
    u = machine()
    u.mem_write(CODE, menu_callback(CODE))
    put(u, CONTEXT + 0xB4, 0 if kind == 'no-owner' else OWNER)
    put(u, CONTEXT + 0xB8, 0 if kind == 'no-interface' else INTERFACE)
    put(u, OWNER + 0x1C, 3)
    if kind in ('existing', 'foreign-camera'):
        put(u, OWNER + 0x2C, CAMERA)
        put(u, CAMERA, 0x19E3D0 if kind == 'existing' else 0x12345678)
    put(u, STACK, EXIT)
    put(u, STACK + 4, 0xA1B2C3D4)
    u.reg_write(r.UC_X86_REG_ESP, STACK)
    u.reg_write(r.UC_X86_REG_ECX, CONTEXT)
    saved = {r.UC_X86_REG_EBX: 0x11223344, r.UC_X86_REG_ESI: 0x22334455,
             r.UC_X86_REG_EDI: 0x33445566, r.UC_X86_REG_EBP: 0x44556677}
    for register, value in saved.items():
        u.reg_write(register, value)
    calls = []
    def action(uc):
        sp = uc.reg_read(r.UC_X86_REG_ESP)
        calls.append(tuple(get(uc, sp + 4 + i * 4) for i in range(3)))
        return_from(uc, 12)
    run_until(u, CODE, {0x16610: action})
    assert calls == ([(OWNER, 3, INTERFACE)] if kind == 'create' else [])
    assert get(u, OWNER + 0x1C) == (1 if kind == 'existing' else 3)
    assert u.reg_read(r.UC_X86_REG_ESP) == STACK + 8
    assert all(u.reg_read(register) == value for register, value in saved.items())


@pytest.mark.parametrize('button,latch', [(0x2C, 0x4D), (0x44, 0x53)])
def test_synthetic_white_back_restore_hud_and_rejoin_same_native_exit(button, latch):
    u = machine()
    u.mem_write(CODE, camera_controls(CODE, STATE))
    put(u, HUD_GLOBAL, HUD)
    put(u, HUD + 4, 0)
    put(u, STATE, 1)
    put(u, STATE + 4, 1)
    put(u, CONTROLLER + button, 0x3F800000)
    put(u, STACK, EXIT)
    u.reg_write(r.UC_X86_REG_ESP, STACK)
    u.reg_write(r.UC_X86_REG_ECX, CONTROLLER)
    saved = {r.UC_X86_REG_EAX: 0x12345678, r.UC_X86_REG_EDX: 0x23456789,
             r.UC_X86_REG_ESI: 0x3456789A, r.UC_X86_REG_EDI: OWNER}
    for register, value in saved.items():
        u.reg_write(register, value)
    assert run_until(u, CODE, targets=(0x15E0D, 0x15DF1)) == 0x15E0D
    assert get(u, HUD + 4) == 1
    assert u.mem_read(STATE, 1) == b'\0'
    assert u.mem_read(CONTROLLER + latch, 1) == b'\x01'
    assert u.reg_read(r.UC_X86_REG_ESP) == STACK
    assert u.reg_read(r.UC_X86_REG_EBX) == 0
    assert all(u.reg_read(register) == value for register, value in saved.items())


@pytest.mark.parametrize('initial', [0, 1])
def test_native_y_edges_and_white_exit_restore_previous_hud(retail, initial):
    source, image, metadata = retail
    u = machine(image)
    put(u, 0x1A9A64, 0)
    put(u, HUD_GLOBAL, HUD)
    put(u, HUD + 4, initial)
    put(u, OWNER + 0x1C, 1)
    put(u, OWNER + 0x2C, CAMERA)
    put(u, CAMERA, 0x19E3D0)
    saved = {r.UC_X86_REG_EBX: 0x11223344, r.UC_X86_REG_ESI: 0x22334455,
             r.UC_X86_REG_EDI: OWNER, r.UC_X86_REG_EBP: 0x33445566,
             r.UC_X86_REG_ECX: 0x44556677}
    removed = []
    def destructor(uc):
        removed.append(uc.reg_read(r.UC_X86_REG_ESI))
        return_from(uc)
    def frame(y=0, y_latch=0, white=0):
        u.mem_write(CONTROLLER, b'\0' * 0x54)
        put(u, CONTROLLER + 0x24, 0x3F800000 if y else 0)
        put(u, CONTROLLER + 0x2C, 0x3F800000 if white else 0)
        u.mem_write(CONTROLLER + 0x4B, bytes([y_latch]))
        before = bytes(u.mem_read(CONTROLLER, 0x54))
        put(u, STACK, EXIT)
        put(u, STACK + 4, 0)
        put(u, STACK + 8, 0)
        u.reg_write(r.UC_X86_REG_ESP, STACK)
        for register, value in saved.items():
            u.reg_write(register, value)
        assert run_until(u, 0x15DA0, {0x82760: destructor}) == EXIT
        assert u.reg_read(r.UC_X86_REG_ESP) == STACK + 12
        assert all(u.reg_read(register) == value for register, value in saved.items())
        after = bytearray(u.mem_read(CONTROLLER, 0x54))
        for at in (0x4B, 0x4D, 0x53):
            after[at] = before[at]
        assert bytes(after) == before, 'Camera controls modified unrelated controller fields'
    frame(y=1)
    assert get(u, HUD + 4) == initial ^ 1
    frame(y=1, y_latch=1)
    assert get(u, HUD + 4) == initial ^ 1, 'Held Y toggled more than once'
    frame(y=0)
    frame(y=1)
    assert get(u, HUD + 4) == initial
    frame(y=1, y_latch=1, white=1)
    assert removed == [CAMERA]
    assert get(u, HUD + 4) == initial
    assert get(u, OWNER + 0x1C) == 0
    assert get(u, OWNER + 0x2C) == 0
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA256


@pytest.mark.parametrize('hud_present', [True, False])
def test_native_back_exit_clears_owner_and_restores_hud(retail, hud_present):
    source, image, metadata = retail
    u = machine(image)
    state = metadata['sectionVA'] + 8
    put(u, 0x1A9A64, 0)
    put(u, HUD_GLOBAL, HUD if hud_present else 0)
    put(u, HUD + 4, 0)
    put(u, state, 1)
    put(u, state + 4, 1)
    put(u, OWNER + 0x1C, 1)
    put(u, OWNER + 0x2C, CAMERA)
    put(u, CONTROLLER + 0x44, 0x3F800000)
    put(u, STACK, EXIT)
    u.reg_write(r.UC_X86_REG_EDI, OWNER)
    u.reg_write(r.UC_X86_REG_ESP, STACK)
    removed = []
    def destructor(uc):
        removed.append(uc.reg_read(r.UC_X86_REG_ESI))
        return_from(uc)
    run_until(u, 0x15DA0, {0x82760: destructor})
    assert removed == [CAMERA]
    assert get(u, OWNER + 0x1C) == get(u, OWNER + 0x2C) == 0
    assert get(u, HUD + 4) == (1 if hud_present else 0)
    assert u.mem_read(state, 1) == b'\0'
    assert u.mem_read(CONTROLLER + 0x53, 1) == b'\x01'
    assert u.reg_read(r.UC_X86_REG_ESP) == STACK + 12


@pytest.mark.parametrize('state', [0, 2, 3, 4, 5, 0xFFFFFFFF])
def test_native_other_states_never_enter_custom_controls(retail, state):
    source, image, metadata = retail
    u = machine(image)
    put(u, OWNER + 0x1C, state)
    put(u, HUD_GLOBAL, HUD)
    put(u, HUD + 4, 1)
    put(u, STACK, EXIT)
    u.reg_write(r.UC_X86_REG_EDI, OWNER)
    u.reg_write(r.UC_X86_REG_ESP, STACK)
    other = {0: 0x15DB6, 2: 0x15E21, 3: 0x15E37, 4: 0x15E7B}
    entered = []
    controls = metadata['routines']['cameraControls']['va']
    def unexpected(uc):
        entered.append(True)
        raise AssertionError('State other than 1 entered custom free-camera controls')
    target = other.get(state, EXIT)
    assert run_until(u, 0x15DA0, {controls: unexpected}, targets=(target,)) == target
    assert not entered
    assert get(u, HUD + 4) == 1


def test_native_original_cheat_case3_dispatch_and_return_contract(retail):
    source, image, metadata = retail
    u = machine(image)
    put(u, STACK, EXIT)
    for index, value in enumerate((OWNER, 3, INTERFACE)):
        put(u, STACK + 4 + index * 4, value)
    u.reg_write(r.UC_X86_REG_ESP, STACK)
    assert run_until(u, 0x16610, targets=(0x16812,)) == 0x16812
    assert u.reg_read(r.UC_X86_REG_ECX) == INTERFACE
    assert u.reg_read(r.UC_X86_REG_EDX) == OWNER
    assert u.reg_read(r.UC_X86_REG_EAX) == 3


def test_native_menu_update_callback_and_postcallback_preserve_freecam_state(retail):
    source, image, metadata = retail
    u = machine(image)
    callback = metadata['routines']['menuCallback']['va']
    put(u, 0x1A9A64, 0)
    put(u, CONTEXT + 0xB4, OWNER)
    put(u, CONTEXT + 0xB8, INTERFACE)
    put(u, CONTEXT + 0x84, 7)  # Retail action executes after START is released.
    put(u, CONTEXT + 0x8C, ROW + 8)
    put(u, ROW, 0x1A3C08)
    put(u, ROW + 0x84, callback)
    put(u, OWNER + 0x1C, 3)
    put(u, STACK, EXIT)
    put(u, STACK + 4, 0x3C23D70A)
    u.reg_write(r.UC_X86_REG_ESP, STACK)
    u.reg_write(r.UC_X86_REG_ESI, CONTEXT)
    u.reg_write(r.UC_X86_REG_EBX, 0x12345678)
    calls = []
    def native_action(uc):
        sp = uc.reg_read(r.UC_X86_REG_ESP)
        calls.append(tuple(get(uc, sp + 4 + i * 4) for i in range(3)))
        # Camera construction is an engine boundary; the real dispatcher is
        # independently tested above. Simulate only its successful result.
        put(uc, OWNER + 0x2C, CAMERA)
        put(uc, CAMERA, 0x19E3D0)
        put(uc, OWNER + 0x1C, 1)
        return_from(uc, 12)
    assert run_until(u, 0x1F590, {0x16610: native_action}) == EXIT
    assert calls == [(OWNER, 3, INTERFACE)]
    assert get(u, OWNER + 0x1C) == 1
    assert get(u, OWNER + 0x2C) == CAMERA
    assert get(u, CONTEXT + 0x84) == 1  # Only the menu's input substate resets.
    assert get(u, CONTEXT + 0x8C) == ROW + 8
    assert u.reg_read(r.UC_X86_REG_ESI) == CONTEXT
    assert u.reg_read(r.UC_X86_REG_EBX) == 0x12345678
    assert u.reg_read(r.UC_X86_REG_ESP) == STACK + 8


@pytest.mark.parametrize('allocation_succeeds', [True, False])
def test_native_menu_factory_constructor_registration_and_original_epilogue(retail, allocation_succeeds):
    source, image, metadata = retail
    u = machine(image)
    factory = metadata['routines']['menuFactory']['va']
    callback = metadata['routines']['menuCallback']['va']
    put(u, CONTEXT + 4, PARENT)
    put(u, PARENT, 0x1A3C08)
    put(u, PARENT + 0x10, VECTOR)
    put(u, PARENT + 0x14, VECTOR)
    put(u, PARENT + 0x18, VECTOR + 0x20)
    # State at the original factory epilogue: locals plus saved EDI/ESI/EBX.
    for index, value in enumerate((0x11223344, 0x22334455, 0x33445566)):
        put(u, STACK + index * 4, value)
    put(u, STACK + 0x7DC, EXIT)
    put(u, STACK + 0x7E0, CONTEXT)
    put(u, STACK + 0x7E4, 0)
    put(u, STACK + 0x7E8, 0)
    u.reg_write(r.UC_X86_REG_ESP, STACK)
    u.reg_write(r.UC_X86_REG_EBX, 0)
    calls = []
    def heap(uc):
        uc.reg_write(r.UC_X86_REG_EAX, HEAP)
        return_from(uc)
    def allocate(uc):
        sp = uc.reg_read(r.UC_X86_REG_ESP)
        calls.append(tuple(get(uc, sp + 4 + i * 4) for i in range(3)))
        uc.reg_write(r.UC_X86_REG_EAX, ROW if allocation_succeeds else 0)
        return_from(uc, 12)
    assert run_until(u, factory, {0xE67CD: heap, 0xE4C9F: allocate}) == EXIT
    assert calls == [(HEAP, 0, 0x8C)]
    assert u.reg_read(r.UC_X86_REG_EAX) == CONTEXT
    assert u.reg_read(r.UC_X86_REG_EDI) == 0x11223344
    assert u.reg_read(r.UC_X86_REG_ESI) == 0x22334455
    assert u.reg_read(r.UC_X86_REG_EBX) == 0x33445566
    assert u.reg_read(r.UC_X86_REG_ESP) == STACK + 0x7EC
    if allocation_succeeds:
        assert get(u, ROW) == 0x1A3C08
        assert bytes(u.mem_read(ROW + 0x1C, 16)) == b'Free Camera'.ljust(16, b'\0')
        assert get(u, ROW + 0x84) == callback
        assert get(u, ROW + 0x88) == 0
        assert get(u, ROW + 0x0C) == PARENT
        assert get(u, VECTOR) == ROW
        assert get(u, PARENT + 0x14) == VECTOR + 4
        assert get(u, CONTEXT + 0x8C) == ROW + 8
    else:
        assert get(u, PARENT + 0x14) == VECTOR


@pytest.mark.parametrize('state,expected', [(0, 0), (1, 0), (2, 1), (3, 1), (4, 0)])
def test_native_world_pause_predicate_only_excludes_original_camera(retail, state, expected):
    source, image, metadata = retail
    u = machine(image)
    put(u, OWNER + 0x1C, state)
    put(u, STACK, EXIT)
    u.reg_write(r.UC_X86_REG_EAX, OWNER)
    u.reg_write(r.UC_X86_REG_ESP, STACK)
    run_until(u, 0x15F60)
    assert u.reg_read(r.UC_X86_REG_EAX) & 0xFF == expected
    assert u.reg_read(r.UC_X86_REG_ESP) == STACK + 4
