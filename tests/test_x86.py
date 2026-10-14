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
                           camera_controls, menu_factory, ROOT_MENU_TITLE)
from freecam.xbe import sections, u32, offset

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
        assert bytes(u.mem_read(ROW + 0x1C, 16)) == b'Freecam'.ljust(16, b'\0')
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


def construct_native_root_menu(image, *, fail_freecam_allocation=False, via_native_activation=False):
    """Execute the complete retail root constructor, not only our tail hook.

    Only the allocator and the current-level display-name accessor are engine
    boundaries. The retail base constructor, all three original row
    constructors, vector insertion and selection code execute unchanged.
    """
    u = machine(image)
    u.mem_map(0x720000, 0x10000)
    stack = STACK + 0x1000  # Native activation adds one more 2 KiB stack frame.
    next_heap = 0x720000
    object_allocations = []

    def reserve(size):
        nonlocal next_heap
        assert 0 < size <= 0x1000
        result = next_heap
        next_heap += (size + 15) & ~15
        assert next_heap <= 0x730000
        return result

    def heap(uc):
        uc.reg_write(r.UC_X86_REG_EAX, HEAP)
        return_from(uc)

    def allocate_object(uc):
        sp = uc.reg_read(r.UC_X86_REG_ESP)
        assert get(uc, sp + 4) == HEAP
        assert get(uc, sp + 8) == 0
        size = get(uc, sp + 12)
        object_allocations.append(size)
        final_allocation = 6 if via_native_activation else 5
        fail = fail_freecam_allocation and len(object_allocations) == final_allocation
        uc.reg_write(r.UC_X86_REG_EAX, 0 if fail else reserve(size))
        return_from(uc, 12)

    def allocate_vector(uc):
        uc.reg_write(r.UC_X86_REG_EAX, reserve(uc.reg_read(r.UC_X86_REG_EAX)))
        return_from(uc)

    def level_name(uc):
        # The level title is optional; it does not construct the root rows.
        uc.reg_write(r.UC_X86_REG_EAX, 0)
        return_from(uc)

    put(u, stack, EXIT)
    arguments = (OWNER, INTERFACE, 0) if via_native_activation else (CONTEXT, OWNER, INTERFACE)
    for index, value in enumerate(arguments):
        put(u, stack + 4 + index * 4, value)
    if via_native_activation:
        # Execute the retail L3 + START entry, including its call to the actual
        # root constructor. The separate developer drone shortcut stays off.
        put(u, 0x1A9A64, 0)
        put(u, 0x38EA10, HUD)
        put(u, HUD + 4, 0)
        put(u, CONTROLLER + 0x38, 0x3F800000)  # START
        put(u, CONTROLLER + 0x40, 0x3F800000)  # L3
        put(u, OWNER + 0x20, VECTOR)
        put(u, OWNER + 0x24, VECTOR)
        put(u, OWNER + 0x28, VECTOR + 0x10)
    u.reg_write(r.UC_X86_REG_ESP, stack)
    preserved = {r.UC_X86_REG_EBX: 0x11223344, r.UC_X86_REG_ESI: 0x22334455,
                 r.UC_X86_REG_EDI: 0x33445566, r.UC_X86_REG_EBP: 0x44556677}
    for register, value in preserved.items():
        u.reg_write(register, value)
    run_until(u, 0x17090 if via_native_activation else 0x138D0,
              {0xE67CD: heap, 0xE4C9F: allocate_object,
               0x185E0: allocate_vector, 0x8D960: level_name}, count=20000)
    assert u.reg_read(r.UC_X86_REG_ESP) == stack + 4 + 4 * len(arguments)
    context = get(u, VECTOR) if via_native_activation else CONTEXT
    if via_native_activation:
        assert get(u, OWNER + 0x1C) == 2
        assert get(u, OWNER + 0x24) == VECTOR + 4
        assert u.mem_read(CONTROLLER + 0x52, 1) == b'\x01'
    else:
        assert u.reg_read(r.UC_X86_REG_EAX) == context
    assert all(u.reg_read(register) == value for register, value in preserved.items())
    assert get(u, context + 0xB4) == OWNER
    assert get(u, context + 0xB8) == INTERFACE
    parent = get(u, context + 4)
    assert parent and get(u, parent) == 0x1A3C08
    if image[offset(image, 0x1395F)] == 0xB8:
        assert bytes(u.mem_read(parent + 0x1C, 100)).split(b'\0')[0].decode('ascii') == ROOT_MENU_TITLE
    begin, end = get(u, parent + 0x10), get(u, parent + 0x14)
    assert begin <= end <= get(u, parent + 0x18)
    rows = []
    for address in range(begin, end, 4):
        row = get(u, address)
        rows.append({
            'label': bytes(u.mem_read(row + 0x1C, 100)).split(b'\0')[0].decode('ascii'),
            'class': get(u, row), 'callback': get(u, row + 0x84),
            'owner': get(u, row + 0x0C), 'address': row,
        })
        assert rows[-1]['owner'] == parent
    return u, rows, object_allocations


def test_complete_native_root_menu_preserves_three_rows_and_appends_fourth(retail):
    source, image, metadata = retail
    _, original, original_allocations = construct_native_root_menu(source)
    _, patched, patched_allocations = construct_native_root_menu(image)
    assert [row['label'] for row in original] == [
        'Change level...', 'Play Movie...', 'Game state...']
    assert [row['label'] for row in patched] == [
        'Change level...', 'Play Movie...', 'Game state...', 'Freecam']
    assert [(row['class'], row['callback']) for row in patched[:3]] == [
        (row['class'], row['callback']) for row in original]
    assert original_allocations == [0x8C, 0x90, 0x90, 0x90]
    assert patched_allocations == original_allocations + [0x8C]
    assert patched[-1]['class'] == 0x1A3C08
    assert patched[-1]['callback'] == metadata['routines']['menuCallback']['va']


def test_fourth_row_allocation_failure_preserves_native_three_item_menu(retail):
    source, image, metadata = retail
    _, rows, allocations = construct_native_root_menu(image, fail_freecam_allocation=True)
    assert allocations == [0x8C, 0x90, 0x90, 0x90, 0x8C]
    assert [row['label'] for row in rows] == [
        'Change level...', 'Play Movie...', 'Game state...']


def test_real_l3_start_activation_opens_existing_menu_with_fourth_freecam_row(retail):
    source, image, metadata = retail
    _, original, _ = construct_native_root_menu(source, via_native_activation=True)
    u, patched, allocations = construct_native_root_menu(image, via_native_activation=True)
    assert [row['label'] for row in patched] == [
        'Change level...', 'Play Movie...', 'Game state...', 'Freecam']
    assert [(row['class'], row['callback']) for row in patched[:3]] == [
        (row['class'], row['callback']) for row in original]
    assert allocations == [0x11C, 0x8C, 0x90, 0x90, 0x90, 0x8C]
    assert patched[-1]['callback'] == metadata['routines']['menuCallback']['va']
    assert get(u, OWNER + 0x1C) == 2


@pytest.mark.parametrize('via_native_activation', [False, True])
def test_native_root_copies_version_title_without_changing_retail_build_stamp(retail, via_native_activation):
    source, image, metadata = retail
    u, rows, _ = construct_native_root_menu(image, via_native_activation=via_native_activation)
    context = get(u, VECTOR) if via_native_activation else CONTEXT
    parent = get(u, context + 4)
    assert bytes(u.mem_read(parent + 0x1C, 100)).split(b'\0')[0] == b'Commande menue - 1.0.0'
    assert metadata['nativeRootMenu']['title'] == ROOT_MENU_TITLE
    title_va = metadata['nativeRootMenu']['titleVA']
    assert image[offset(image, 0x1395F):offset(image, 0x1395F) + 5] == b'\xB8' + struct.pack('<I', title_va)
    assert bytes(u.mem_read(title_va, 23)) == b'Commande menue - 1.0.0\0'
    for va, length in ((0x8D960, 0x6D), (0x19DDBC, 0x68)):
        assert image[offset(image, va):offset(image, va) + length] == source[offset(source, va):offset(source, va) + length]
    assert [row['label'] for row in rows] == ['Change level...', 'Play Movie...', 'Game state...', 'Freecam']


@pytest.mark.parametrize('state', [0, 1, 2, 3, 4, 0xFFFFFFFF])
@pytest.mark.parametrize('start,live,paused', [
    (0x54961, 0x5496D, 0x54983),
    (0x55FE0, 0x55FF0, 0x560B9),
    (0x562DB, 0x562E7, 0x56326),
])
def test_actual_native_simulation_callers_continue_in_freecam(retail, state, start, live, paused):
    source, image, metadata = retail
    outcomes = []
    for data, frozen_states in ((source, (1, 2, 3)), (image, (2, 3))):
        u = machine(data)
        put(u, OWNER + 0x1C, state)
        put(u, CONTEXT + 0x40, OWNER)
        u.reg_write(r.UC_X86_REG_EBP, CONTEXT)
        u.reg_write(r.UC_X86_REG_EDX, CONTEXT)
        u.reg_write(r.UC_X86_REG_ESP, STACK)
        destination = run_until(u, start, targets=(live, paused), count=100)
        assert destination == (paused if state in frozen_states else live)
        assert u.reg_read(r.UC_X86_REG_ESP) == STACK
        outcomes.append(destination)
    if state != 1:
        assert outcomes[0] == outcomes[1], 'An unrelated native state changed its simulation path'


def construct_native_player_world(image):
    """Use real Entity/PlayerPhysics constructors and the real camera vector.

    Spatial registration, timing scheduling and animated-body setup are engine
    boundaries. The ownership stores, vtable writes and camera-stack insertion
    execute from retail instructions instead of being forced by the fixture.
    """
    u = machine(image)
    u.mem_map(0x710000, 0x9000)
    world, entity, physics, registry, slots, clock, body, detached = (
        0x710000 + index * 0x1000 for index in range(8))
    stack = STACK + 0x1000
    put(u, world + 0xA4, clock)
    put(u, world + 0xA8, registry)
    put(u, world + 0x40, 0xDEADC000)  # Not the scene's cheat-manager field.
    put(u, registry, slots)
    put(u, registry + 4, slots)
    put(u, registry + 8, slots + 32)
    u.mem_write(clock + 0x10, struct.pack('<d', 0.25))
    boundaries = {0xB7FB0: lambda uc: return_from(uc, 8),
                  0x21CE0: lambda uc: return_from(uc, 8),
                  0x61D60: lambda uc: return_from(uc, 12),
                  0x849F0: lambda uc: return_from(uc, 4),
                  0xAB920: lambda uc: return_from(uc),
                  0xAB9B0: lambda uc: return_from(uc, 12),
                  0x7E290: lambda uc: return_from(uc, 4),
                  0x7E770: lambda uc: return_from(uc)}

    def call(address, registers, arguments=()):
        put(u, stack, EXIT)
        for index, value in enumerate(arguments):
            put(u, stack + 4 + index * 4, value)
        u.reg_write(r.UC_X86_REG_ESP, stack)
        for register, value in registers.items():
            u.reg_write(register, value)
        assert run_until(u, address, boundaries, count=10000) == EXIT
        assert u.reg_read(r.UC_X86_REG_ESP) == stack + 4 + 4 * len(arguments)

    call(0x60DF0, {r.UC_X86_REG_EAX: world, r.UC_X86_REG_EDI: entity})
    assert get(u, entity + 0x154) == world
    assert get(u, entity + 0xE4) == clock
    put(u, entity + 0x178, body)
    # The animator boundary is not used by the input gate; this field is
    # required only to let the real PlayerPhysics constructor complete.
    call(0x84D00, {r.UC_X86_REG_EDI: physics}, (entity,))
    assert get(u, physics) == 0x19DE24
    assert get(u, physics + 0x20) == entity

    # Install a normal camera with the actual vector registration routine.
    call(0x4F510, {r.UC_X86_REG_EAX: registry}, (entity,))
    assert get(u, registry + 4) == slots + 4 and get(u, slots) == entity

    def create_camera():
        call(0x82630, {r.UC_X86_REG_EAX: world, r.UC_X86_REG_ESI: detached})
        assert get(u, detached) == 0x19E3D0
        assert get(u, detached + 0x154) == world
        assert get(u, registry + 4) == slots + 8
        assert get(u, slots + 4) == detached
        assert u.mem_read(detached + 0x195, 1) == b'\x01'

    def player_dispatch():
        # The real vtable slot is read at runtime. This is not a direct call to
        # the emitter, and the normal path executes the original tick prologue
        # until its actual call to the controller-input update at 0x84F40.
        code = b'\xB9' + struct.pack('<I', physics) + b'\x8B\x01\xFF\x10'
        code += b'\xE9' + struct.pack('<i', EXIT - (CODE + len(code) + 5))
        u.mem_write(CODE, code)
        u.reg_write(r.UC_X86_REG_ESP, stack)
        return run_until(u, CODE, targets=(EXIT, 0x84F40), count=1000)

    return u, {'world': world, 'entity': entity, 'physics': physics,
               'registry': registry, 'slots': slots, 'detached': detached,
               'stack': stack, 'body': body}, create_camera, player_dispatch


def test_retail_constructors_and_real_player_vtable_dispatch_use_actual_world_stack(retail):
    source, image, metadata = retail
    u, addresses, create_camera, dispatch = construct_native_player_world(image)
    assert get(u, 0x19DE24) == 0x8C1E0, 'The complete player tick must stay installed'
    assert get(u, addresses['world'] + 0x40) == 0xDEADC000
    assert dispatch() == 0x84F40  # Normal gameplay reaches native input update.
    create_camera()  # Actual retail Entity/camera constructor and registration.
    assert dispatch() == 0x84F40  # Physics/animation tick still reaches its input update.


def test_native_camera_removal_releases_player_before_deferred_destruction(retail):
    source, image, metadata = retail
    u, addresses, create_camera, dispatch = construct_native_player_world(image)
    camera, stack = addresses['detached'], addresses['stack']
    for _ in range(3):
        create_camera()
        assert dispatch() == 0x84F40
        assert native_input_frame(u, addresses)['axes'] == (0.0, 0.0)
        # Execute the real WHITE handler and actual removal/vector pop. Only
        # deferred destruction is intercepted; the object still exists when
        # the native handler clears its owner's pointer and returns to gameplay.
        deferred = get(u, 0x19E3D0 + 0xB8)
        put(u, OWNER + 0x1C, 1)
        put(u, OWNER + 0x2C, camera)
        put(u, HUD_GLOBAL, HUD)
        put(u, HUD + 4, 1)
        u.mem_write(CONTROLLER, b'\0' * 0x54)
        put(u, CONTROLLER + 0x2C, 0x3F800000)
        put(u, stack, EXIT)
        put(u, stack + 4, 0)
        put(u, stack + 8, 0)
        u.reg_write(r.UC_X86_REG_ESP, stack)
        u.reg_write(r.UC_X86_REG_EDI, OWNER)
        assert run_until(u, 0x15DA0, {deferred: lambda uc: return_from(uc)}, count=2000) == EXIT
        assert get(u, OWNER + 0x1C) == get(u, OWNER + 0x2C) == 0
        assert u.mem_read(CONTROLLER + 0x4D, 1) == b'\x01'
        assert get(u, camera) == 0x19E3D0
        assert get(u, camera + 0x154) == addresses['world']
        assert u.mem_read(camera + 0x195, 1) == b'\0'
        assert get(u, addresses['registry'] + 4) == addresses['slots'] + 4
        assert dispatch() == 0x84F40
        packet = native_input_frame(u, addresses)
        assert packet['axes'] == (0.75, 0.5), 'Player controls stayed blocked after camera removal'


def prepare_native_input(u, addresses, packet, *, buttons=False):
    world, context = addresses['world'], 0x718000
    put(u, world + 0xD8, context)
    put(u, context + 0x18, 0)
    u.mem_write(context, b'\0' * 4)
    put(u, world + 0xC4, world + 0xC4)  # Empty scripted-motion list.
    put(u, 0x38EA20, HUD)
    put(u, HUD + 4, 1)
    put(u, 0x1A9A64, 0)
    u.mem_write(packet, b'\0' * 0x150)
    u.mem_write(packet + 0x20, b'\xff')
    u.mem_write(CONTROLLER, b'\0' * 0x54)
    u.mem_write(CONTROLLER, struct.pack('<2f', 0.75, 0.5))
    if buttons:
        for field in (0x18, 0x1C, 0x24, 0x28, 0x2C, 0x34, 0x3C):
            u.mem_write(CONTROLLER + field, struct.pack('<f', 1.0))
    return bytes(u.mem_read(CONTROLLER, 0x54))


def native_input_frame(u, addresses, *, buttons=False):
    """Execute actual input prefix, gate, and common stick-magnitude calculation.

    Stop before the camera-quaternion/animated-body engine-dependent work. The
    retail code establishes EBP/ESI/EDI itself; no synthetic guard register
    assignments bypass its calling contract.
    """
    physics, stack = addresses['physics'], addresses['stack']
    packet = 0x718400
    raw = prepare_native_input(u, addresses, packet, buttons=buttons)
    put(u, stack, EXIT)
    put(u, stack + 4, physics)
    u.reg_write(r.UC_X86_REG_ESP, stack)
    u.reg_write(r.UC_X86_REG_ESI, packet)
    u.reg_write(r.UC_X86_REG_EFLAGS, 0x202)
    u.reg_write(r.UC_X86_REG_FPCW, 0x37F)
    u.reg_write(r.UC_X86_REG_FPSW, 0)
    assert run_until(u, 0x84F40, targets=(0x851F1,), count=3000) == 0x851F1
    return {'axes': struct.unpack('<2f', u.mem_read(packet + 8, 8)),
            'magnitude': struct.unpack('<f', u.mem_read(packet + 0x1C, 4))[0],
            'actions': u.mem_read(packet + 0x20, 1)[0],
            'rawBefore': raw, 'rawAfter': bytes(u.mem_read(CONTROLLER, 0x54))}


def test_retail_input_branch_blocks_only_player_commands_and_keeps_raw_camera_input(retail):
    source, image, metadata = retail
    u, addresses, create_camera, _ = construct_native_player_world(image)
    normal = native_input_frame(u, addresses)
    assert normal['axes'] == (0.75, 0.5)
    assert normal['magnitude'] == pytest.approx((0.75 ** 2 + 0.5 ** 2) ** 0.5)
    create_camera()
    blocked = native_input_frame(u, addresses, buttons=True)
    assert blocked['axes'] == (0.0, 0.0)
    assert blocked['magnitude'] == 0.0, 'Native derived motion still contains stick magnitude'
    assert blocked['actions'] == 0x80, 'The low seven player-action bits must be clear'
    assert blocked['rawAfter'] == blocked['rawBefore'], 'Camera/Y/WHITE raw controls were consumed'
    assert metadata['playerControls']['wholePlayerTickPreserved']
    assert metadata['playerControls']['playerSchedulingPreserved']
    assert metadata['playerControls']['rawControllerPreserved']


def test_cleared_native_camera_flag_restores_input_even_if_deferred_camera_remains_top(retail):
    source, image, metadata = retail
    u, addresses, create_camera, _ = construct_native_player_world(image)
    create_camera()
    camera, registry, slots = (addresses[key] for key in ('detached', 'registry', 'slots'))
    for _ in range(3):
        u.mem_write(camera + 0x195, b'\x01')
        assert native_input_frame(u, addresses)['axes'] == (0.0, 0.0)
        u.mem_write(camera + 0x195, b'\0')  # Exact byte cleared by native WHITE removal.
        assert get(u, registry + 4) == slots + 8 and get(u, slots + 4) == camera
        released = native_input_frame(u, addresses)
        assert released['axes'] == (0.75, 0.5)
        assert released['magnitude'] > 0


@pytest.mark.parametrize('camera_enabled', [False, True])
def test_real_player_tick_keeps_timing_animation_root_motion_and_collision_calls(retail, camera_enabled):
    source, image, metadata = retail
    u, addresses, create_camera, _ = construct_native_player_world(image)
    if camera_enabled:
        create_camera()
    entity, physics, body, world, stack = (addresses[key] for key in (
        'entity', 'physics', 'body', 'world', 'stack'))
    put(u, entity + 0x17C, body)
    put(u, body + 0x10, 0)
    put(u, body + 0x44, 0)
    put(u, world + 0xCC, 0x718000)
    calls = []
    def boundary(address, args=0):
        def invoke(uc):
            calls.append(address)
            return_from(uc, args)
        return invoke
    input_results = []
    def prepare_input(uc):
        packet = uc.reg_read(r.UC_X86_REG_ESI)
        prepare_native_input(uc, addresses, packet, buttons=camera_enabled)
    def camera_body_boundary(uc):
        # The real input prologue, gate, blocked/normal path and common magnitude
        # execute inside the real tick. Intercept only the engine-dependent
        # quaternion/body/contact work after its original x87 operands are popped.
        packet = uc.reg_read(r.UC_X86_REG_ESI)
        input_results.append((struct.unpack('<2f', uc.mem_read(packet + 8, 8)),
                              struct.unpack('<f', uc.mem_read(packet + 0x1C, 4))[0],
                              uc.mem_read(packet + 0x20, 1)[0]))
        uc.reg_write(r.UC_X86_REG_EAX, 0)
        uc.reg_write(r.UC_X86_REG_ECX, entity)
        uc.reg_write(r.UC_X86_REG_EIP, 0x85542)  # Original input epilogue/RET 4.
    handlers = {0x84F40: prepare_input, 0x85211: camera_body_boundary,
                0x83D30: boundary(0x83D30, 4),
                0xAB920: boundary(0xAB920), 0xAB9B0: boundary(0xAB9B0, 12),
                0xCB4F0: boundary(0xCB4F0, 4), 0x8CC70: boundary(0x8CC70, 4),
                0x8C850: boundary(0x8C850, 4), 0x8C4D0: boundary(0x8C4D0),
                0x8C400: boundary(0x8C400, 4)}
    code = b'\xB9' + struct.pack('<I', physics) + b'\x8B\x01\xFF\x10'
    code += b'\xE9' + struct.pack('<i', EXIT - (CODE + len(code) + 5))
    u.mem_write(CODE, code)
    u.reg_write(r.UC_X86_REG_ESP, stack)
    assert run_until(u, CODE, handlers, count=3000) == EXIT
    assert len(input_results) == 1
    axes, magnitude, actions = input_results[0]
    if camera_enabled:
        assert axes == (0.0, 0.0) and magnitude == 0.0 and actions == 0x80
    else:
        assert axes == (0.75, 0.5) and magnitude > 0
    assert calls == [0x83D30, 0xAB920, 0xAB9B0, 0xCB4F0, 0x8CC70, 0x8C850, 0x8C4D0, 0x8C400]
    assert get(u, 0x19DE24) == 0x8C1E0
    assert u.reg_read(r.UC_X86_REG_ESP) == stack
