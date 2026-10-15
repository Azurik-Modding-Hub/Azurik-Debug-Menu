"""Synthetic x86 checks for chord activation, controller edges and wrapper ABI.

The real game menu allocator is an intercepted boundary. These tests prove the
emitted control flow and argument/register contracts; they are not gameplay tests.
"""
from itertools import permutations
import struct

import pytest
from unicorn import x86_const as r

import test_x86 as native
from freecam.activation import emit_poll, emit_dispatch


WORLD, ACTOR = 0x70A000, 0x70B000
POLL, DISPATCH = native.CODE, native.CODE + 0x700
WORLD_METHOD = native.CODE + 0xE00
ACTIVE = 0x1A9A64
VALUES = {'A': 0x18, 'B': 0x1C, 'White': 0x2C, 'L3': 0x38, 'Start': 0x40}
LATCHES = {'A': 0x48, 'B': 0x49, 'White': 0x4D, 'L3': 0x50, 'Start': 0x52}
WAB = ('White', 'A', 'B')
LEGACY = ('L3', 'Start')
SAVED = {r.UC_X86_REG_EAX: 0x12345678, r.UC_X86_REG_EBX: 0x22334455,
         r.UC_X86_REG_ECX: 0x33445566, r.UC_X86_REG_EDX: 0x44556677,
         r.UC_X86_REG_ESI: 0x55667788, r.UC_X86_REG_EDI: native.OWNER,
         r.UC_X86_REG_EBP: 0x66778899}


class ChordMachine:
    def __init__(self, index=0):
        self.u = native.machine()
        self.u.mem_map(0x1A9000, 0x1000)
        self.u.mem_write(POLL, emit_poll(POLL, native.STATE))
        self.u.mem_write(DISPATCH, emit_dispatch(DISPATCH, POLL))
        native.put(self.u, ACTIVE, index)
        native.put(self.u, native.INTERFACE, native.PARENT)
        native.put(self.u, native.PARENT, WORLD_METHOD)
        native.put(self.u, WORLD + 0xCC, ACTOR)
        native.put(self.u, native.OWNER + 0x20, native.VECTOR)
        native.put(self.u, native.OWNER + 0x24, native.VECTOR)
        self.world = WORLD
        self.calls = []

    def controller(self, index=None):
        if index is None:
            index = native.get(self.u, ACTIVE)
        return native.CONTROLLER + (0 if index == 4 else index) * 0x54

    def buttons(self, held, *, index=None):
        address = self.controller(index)
        for name, offset in VALUES.items():
            self.u.mem_write(address + offset, struct.pack('<f', 1.0 if name in held else 0.0))

    def latch(self, name, value, *, index=None):
        self.u.mem_write(self.controller(index) + LATCHES[name], bytes([value]))

    def mode(self, index=None):
        if index is None:
            index = native.get(self.u, ACTIVE)
        if index == 4:
            index = 0
        return self.u.mem_read(native.STATE + index, 1)[0]

    def raw(self, index=None):
        return bytes(self.u.mem_read(self.controller(index), 0x48))

    def get_world(self, uc):
        assert uc.reg_read(r.UC_X86_REG_ECX) == native.INTERFACE
        uc.reg_write(r.UC_X86_REG_EAX, self.world)
        native.return_from(uc)

    def action(self, uc):
        sp = uc.reg_read(r.UC_X86_REG_ESP)
        args = tuple(native.get(uc, sp + 4 + i * 4) for i in range(3))
        self.calls.append(args)
        assert args == (native.OWNER, 0, native.INTERFACE)
        native.put(uc, native.OWNER + 0x1C, 2)
        native.put(uc, native.OWNER + 0x24, native.VECTOR + 4)
        native.return_from(uc, 12)

    def close_menu(self, state=0):
        native.put(self.u, native.OWNER + 0x1C, state)
        native.put(self.u, native.OWNER + 0x24, native.VECTOR)

    def poll(self, owner=native.OWNER, interface=native.INTERFACE):
        native.put(self.u, native.STACK, native.EXIT)
        native.put(self.u, native.STACK + 4, owner)
        native.put(self.u, native.STACK + 8, interface)
        self.u.reg_write(r.UC_X86_REG_ESP, native.STACK)
        for reg, value in SAVED.items():
            self.u.reg_write(reg, value)
        native.run_until(self.u, POLL, {WORLD_METHOD: self.get_world, 0x16610: self.action})
        assert self.u.reg_read(r.UC_X86_REG_ESP) == native.STACK + 12
        for reg in [r.UC_X86_REG_EBX, r.UC_X86_REG_ESI, r.UC_X86_REG_EDI, r.UC_X86_REG_EBP]:
            assert self.u.reg_read(reg) == SAVED[reg]
        return self.u.reg_read(r.UC_X86_REG_EAX)


@pytest.mark.parametrize('order', list(permutations(WAB)))
def test_each_partial_button_order_opens_only_when_chord_complete(order):
    f = ChordMachine()
    held = set()
    for index, name in enumerate(order):
        held.add(name)
        f.buttons(held)
        before = f.raw()
        assert f.poll() == (1 if index == 2 else 0)
        assert f.raw() == before
        assert len(f.calls) == (1 if index == 2 else 0)
    assert f.mode() == 1
    assert all(f.u.mem_read(f.controller() + LATCHES[name], 1) == b'\x01' for name in WAB)


def test_prior_gameplay_edges_do_not_prevent_completing_the_held_chord():
    f = ChordMachine()
    f.buttons({'A', 'B'})
    f.latch('A', 1)
    f.latch('B', 1)
    assert f.poll() == 0
    f.buttons(WAB)
    assert f.poll() == 1
    assert len(f.calls) == 1


@pytest.mark.parametrize('chord,mode', [(WAB, 1), (LEGACY, 2)])
def test_hold_partial_release_and_full_release_before_reopening(chord, mode):
    f = ChordMachine()
    f.buttons(chord)
    assert f.poll() == 1
    assert f.mode() == mode
    for _ in range(4):
        assert f.poll() == 1
    assert len(f.calls) == 1
    f.close_menu()
    f.buttons(chord[1:])
    assert f.poll() == 1
    assert f.mode() == mode
    f.buttons(chord)
    assert f.poll() == 1
    assert len(f.calls) == 1
    f.buttons(set())
    assert f.poll() == 0
    assert f.mode() == 0
    # Mimic native polling rearming consumed edges after complete release.
    for name in chord:
        f.latch(name, 0)
    f.buttons(chord)
    assert f.poll() == 1
    assert len(f.calls) == 2


@pytest.mark.parametrize('index', range(5))
def test_all_four_controllers_and_native_index4_fallback(index):
    f = ChordMachine(index)
    f.buttons(WAB)
    before = f.raw()
    assert f.poll() == 1
    assert f.mode() == 1
    assert f.raw() == before
    modes = bytes(f.u.mem_read(native.STATE, 4))
    selected = 0 if index == 4 else index
    assert modes == bytes(1 if n == selected else 0 for n in range(4))
    assert len(f.calls) == 1


def test_each_controller_owns_an_independent_debounce_mode():
    f = ChordMachine(0)
    f.buttons(WAB)
    assert f.poll() == 1
    f.close_menu()
    native.put(f.u, ACTIVE, 1)
    f.buttons(WAB)
    assert f.poll() == 1
    assert bytes(f.u.mem_read(native.STATE, 4)) == b'\x01\x01\0\0'
    assert len(f.calls) == 2


@pytest.mark.parametrize('index', [5, 12, 0xFFFFFFFF])
def test_invalid_controller_index_has_no_effect(index):
    f = ChordMachine(index)
    f.buttons(WAB, index=0)
    before = bytes(f.u.mem_read(native.STATE, 4))
    assert f.poll() == 0
    assert bytes(f.u.mem_read(native.STATE, 4)) == before
    assert f.calls == []


@pytest.mark.parametrize('case', ['no-owner', 'no-interface', 'no-world', 'no-player', 'null-vtable', 'null-world-method'])
def test_no_attached_gameplay_world_does_not_activate(case):
    f = ChordMachine()
    f.buttons(WAB)
    owner = native.OWNER
    interface = native.INTERFACE
    if case == 'no-owner':
        owner = 0
    elif case == 'no-interface':
        interface = 0
    elif case == 'no-world':
        f.world = 0
    elif case == 'no-player':
        native.put(f.u, WORLD + 0xCC, 0)
    elif case == 'null-vtable':
        native.put(f.u, native.INTERFACE, 0)
    else:
        native.put(f.u, native.PARENT, 0)
    before = f.raw()
    assert f.poll(owner, interface) == 0
    assert f.calls == []
    # Detecting the chord arms its debounce even when a gameplay prerequisite
    # is absent. It must be fully released before a later successful opening.
    assert f.mode() == 1
    assert f.raw() == before


@pytest.mark.parametrize('state', [2, 3, 4, 5, 0xFFFFFFFF])
def test_menu_and_other_non_gameplay_owner_states_do_not_open_again(state):
    f = ChordMachine()
    f.close_menu(state)
    f.buttons(WAB)
    assert f.poll() == (1 if state in (2, 3, 4) else 0)
    assert f.calls == []
    assert f.mode() == 1


@pytest.mark.parametrize('state', [0, 1])
def test_gameplay_or_freecam_with_empty_menu_vector_can_open(state):
    f = ChordMachine()
    f.close_menu(state)
    f.buttons(WAB)
    assert f.poll() == 1
    assert len(f.calls) == 1


def test_nonempty_menu_vector_prevents_duplicate_native_menu():
    f = ChordMachine()
    native.put(f.u, native.OWNER + 0x24, native.VECTOR + 4)
    f.buttons(WAB)
    assert f.poll() == 1  # Consumed without stacking another menu.
    assert f.calls == []


@pytest.mark.parametrize('held', [{'White'}, {'A'}, {'B'}, {'White', 'A'}, {'White', 'B'}, {'A', 'B'}, {'L3'}, {'Start'}])
def test_single_buttons_and_incomplete_chords_remain_native(held):
    f = ChordMachine()
    f.close_menu(1)  # In particular, WHITE alone must still exit native Freecam.
    f.buttons(held)
    before = bytes(f.u.mem_read(f.controller(), 0x54))
    assert f.poll() == 0
    assert f.calls == []
    assert bytes(f.u.mem_read(f.controller(), 0x54)) == before


def test_original_l3_start_chord_consumes_only_its_native_edges():
    f = ChordMachine()
    f.buttons(LEGACY)
    assert f.poll() == 1
    assert f.mode() == 2
    assert f.u.mem_read(f.controller() + 0x50, 1) == b'\x01'
    assert f.u.mem_read(f.controller() + 0x52, 1) == b'\x01'
    assert all(f.u.mem_read(f.controller() + LATCHES[name], 1) == b'\0' for name in WAB)


@pytest.mark.parametrize('pressure', [0.00001, 0.1, 0.5, 1.0])
def test_positive_normalized_analog_pressure_activates_without_rewriting_it(pressure):
    f = ChordMachine()
    for name in WAB:
        f.u.mem_write(f.controller() + VALUES[name], struct.pack('<f', pressure))
    before = f.raw()
    assert f.poll() == 1
    assert f.raw() == before
    assert len(f.calls) == 1


def test_invalid_world_then_valid_world_does_not_open_from_an_old_held_chord():
    f = ChordMachine()
    f.world = 0
    f.buttons(WAB)
    assert f.poll() == 0
    assert len(f.calls) == 0
    f.world = WORLD
    assert f.poll() == 1
    assert len(f.calls) == 0
    f.buttons(set())
    assert f.poll() == 0
    f.buttons(WAB)
    assert f.poll() == 1
    assert len(f.calls) == 1


@pytest.mark.parametrize('activate', [False, True])
def test_dispatch_wrapper_preserves_registers_flags_and_native_stack_contract(activate):
    f = ChordMachine()
    f.buttons(WAB if activate else {'White'})
    native.put(f.u, native.STACK, native.EXIT)
    native.put(f.u, native.STACK + 4, native.INTERFACE)
    native.put(f.u, native.STACK + 8, 0x3C23D70A)
    for reg, value in SAVED.items():
        f.u.reg_write(reg, value)
    f.u.reg_write(r.UC_X86_REG_EFLAGS, 0x246)
    f.u.reg_write(r.UC_X86_REG_ESP, native.STACK)
    target = native.EXIT if activate else 0x15DA7
    native.run_until(f.u, DISPATCH, {WORLD_METHOD: f.get_world, 0x16610: f.action}, targets=(target,))
    for reg, value in SAVED.items():
        if not activate and reg == r.UC_X86_REG_EAX:
            assert f.u.reg_read(reg) == 0
        else:
            assert f.u.reg_read(reg) == value
    if activate:
        assert f.u.reg_read(r.UC_X86_REG_ESP) == native.STACK + 12
        assert f.u.reg_read(r.UC_X86_REG_EFLAGS) == 0x246
        assert len(f.calls) == 1
    else:
        assert f.u.reg_read(r.UC_X86_REG_ESP) == native.STACK - 4
        assert native.get(f.u, native.STACK - 4) == SAVED[r.UC_X86_REG_ECX]
        assert f.u.reg_read(r.UC_X86_REG_EFLAGS) & 0x8D5 == 0x95  # CMP 0,4.
        assert f.calls == []
