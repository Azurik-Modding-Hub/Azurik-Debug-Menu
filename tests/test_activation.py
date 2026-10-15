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
PLAYER_METHOD = native.CODE + 0xE10
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
        native.put(self.u, native.PARENT + 4, PLAYER_METHOD)
        native.put(self.u, WORLD + 0xCC, ACTOR)
        native.put(self.u, native.OWNER + 0x20, native.VECTOR)
        native.put(self.u, native.OWNER + 0x24, native.VECTOR)
        self.world = WORLD
        self.player = ACTOR
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
        return native.get(self.u, native.STATE + index * 16)

    def raw(self, index=None):
        return bytes(self.u.mem_read(self.controller(index), 0x48))

    def get_world(self, uc):
        assert uc.reg_read(r.UC_X86_REG_ECX) == native.INTERFACE
        uc.reg_write(r.UC_X86_REG_EAX, self.world)
        native.return_from(uc)

    def get_player(self, uc):
        assert uc.reg_read(r.UC_X86_REG_ECX) == native.INTERFACE
        uc.reg_write(r.UC_X86_REG_EAX, self.player)
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

    def poll(self, owner=native.OWNER, interface=native.INTERFACE, delta=1/60):
        native.put(self.u, native.STACK, native.EXIT)
        native.put(self.u, native.STACK + 4, owner)
        native.put(self.u, native.STACK + 8, interface)
        self.u.mem_write(native.STACK + 12, struct.pack("<f", delta))
        self.u.reg_write(r.UC_X86_REG_FPCW, 0x37f)
        self.u.reg_write(r.UC_X86_REG_FPSW, 0)
        self.u.reg_write(r.UC_X86_REG_ESP, native.STACK)
        for reg, value in SAVED.items():
            self.u.reg_write(reg, value)
        native.run_until(self.u, POLL, {WORLD_METHOD: self.get_world, PLAYER_METHOD: self.get_player, 0x16610: self.action})
        assert self.u.reg_read(r.UC_X86_REG_ESP) == native.STACK + 16
        for reg in [r.UC_X86_REG_EBX, r.UC_X86_REG_ESI, r.UC_X86_REG_EDI, r.UC_X86_REG_EBP]:
            assert self.u.reg_read(reg) == SAVED[reg]
        return self.u.reg_read(r.UC_X86_REG_EAX)



@pytest.mark.parametrize('gap',[.01,.1,.2,.249])
def test_released_white_then_a_then_b_completes_within_one_second(gap):
    f=ChordMachine()
    for held,expected in [({'White'},0),(set(),0),({'A'},0),(set(),0),({'B'},1)]:
        f.buttons(held);before=f.raw();assert f.poll(delta=gap)==expected;assert f.raw()==before
    assert len(f.calls)==1 and f.mode()==3


@pytest.mark.parametrize('gap',[.26,.4,.6])
def test_sequence_expires_one_second_from_white_not_from_last_button(gap):
    f=ChordMachine()
    for held in [{'White'},set(),{'A'},set(),{'B'}]:
        f.buttons(held);assert f.poll(delta=gap)==0
    assert not f.calls and f.mode()==0


def test_exact_one_second_and_overlapping_presses_are_supported():
    f=ChordMachine();f.buttons({'White'});assert f.poll()==0
    for held,delta,expected in [({'A'},.25,0),(set(),.25,0),({'B'},.5,1)]:
        f.buttons(held);assert f.poll(delta=delta)==expected
    g=ChordMachine()
    for held,expected in [({'White'},0),({'White','A'},0),(set(WAB),1)]:
        g.buttons(held);assert g.poll()==expected
    assert len(g.calls)==1


@pytest.mark.parametrize('order',[p for p in permutations(WAB) if p!=WAB])
def test_wrong_order_without_overlapping_does_not_activate(order):
    f=ChordMachine()
    for name in order:
        f.buttons({name});assert f.poll()==0
        f.buttons(set());assert f.poll()==0
    assert not f.calls


def test_raw_new_edges_are_used_even_if_native_consumed_flags_are_set():
    f=ChordMachine()
    for name in WAB:f.latch(name,1)
    for name in WAB:
        f.buttons({name});result=f.poll()
        if name!='B':f.buttons(set());assert f.poll()==0
    assert result==1 and len(f.calls)==1


@pytest.mark.parametrize('chord,mode',[(WAB,3),(LEGACY,4)])
def test_hold_partial_release_and_full_release_before_reopening(chord,mode):
    f=ChordMachine();f.buttons(chord);assert f.poll()==1;assert f.mode()==mode
    for _ in range(4):assert f.poll()==1
    f.close_menu();f.buttons(chord[1:]);assert f.poll()==1
    f.buttons(chord);assert f.poll()==1;assert len(f.calls)==1
    f.buttons(set());assert f.poll()==0;assert f.mode()==0
    f.buttons(chord);assert f.poll()==1;assert len(f.calls)==2


@pytest.mark.parametrize('index',range(5))
def test_controller_states_and_native_index4_fallback(index):
    f=ChordMachine(index);f.buttons(WAB);before=f.raw();assert f.poll()==1
    assert f.raw()==before and f.mode()==3
    selected=0 if index==4 else index
    assert [native.get(f.u,native.STATE+n*16)for n in range(4)]==[3 if n==selected else 0 for n in range(4)]


def test_each_controller_owns_its_sequence_timer_and_previous_edges():
    f=ChordMachine(0);f.buttons({'White'});assert f.poll()==0
    native.put(f.u,ACTIVE,1);f.buttons(WAB);assert f.poll()==1
    assert native.get(f.u,native.STATE)==1 and native.get(f.u,native.STATE+16)==3


@pytest.mark.parametrize('index',[5,12,0xffffffff])
def test_invalid_controller_index_has_no_effect(index):
    f=ChordMachine(index);f.buttons(WAB,index=0);before=bytes(f.u.mem_read(native.STATE,64))
    assert f.poll()==0 and not f.calls
    assert bytes(f.u.mem_read(native.STATE,64))==before


@pytest.mark.parametrize('case',['no-owner','no-interface','no-world','no-player','null-vtable','null-world-method','null-player-method'])
def test_no_live_world_or_player_cancels_sequence_without_consuming_buttons(case):
    f=ChordMachine();f.buttons(WAB);owner,interface=native.OWNER,native.INTERFACE
    if case=='no-owner':owner=0
    elif case=='no-interface':interface=0
    elif case=='no-world':f.world=0
    elif case=='no-player':f.player=0
    elif case=='null-vtable':native.put(f.u,native.INTERFACE,0)
    elif case=='null-world-method':native.put(f.u,native.PARENT,0)
    else:native.put(f.u,native.PARENT+4,0)
    before=bytes(f.u.mem_read(f.controller(),0x54))
    assert f.poll(owner,interface)==0 and not f.calls and f.mode()==0
    assert bytes(f.u.mem_read(f.controller(),0x54))==before


@pytest.mark.parametrize('state',[2,3,4,5,0xffffffff])
def test_existing_menu_or_invalid_owner_does_not_open_a_new_window(state):
    f=ChordMachine();f.close_menu(state);f.buttons(WAB)
    assert f.poll()==(1 if state in(2,3,4)else 0) and not f.calls


@pytest.mark.parametrize('state',[0,1])
def test_simultaneous_compatibility_in_normal_and_freecam_states(state):
    f=ChordMachine();f.close_menu(state);f.buttons(WAB);assert f.poll()==1 and len(f.calls)==1


def test_nonempty_menu_vector_prevents_duplicate_native_menu():
    f=ChordMachine();native.put(f.u,native.OWNER+0x24,native.VECTOR+4);f.buttons(WAB)
    assert f.poll()==1 and not f.calls


@pytest.mark.parametrize('held',[{'White'},{'A'},{'B'},{'White','A'},{'White','B'},{'A','B'},{'L3'},{'Start'}])
def test_partial_sequence_does_not_skip_native_owner_or_rewrite_analog_input(held):
    f=ChordMachine();f.close_menu(1);f.buttons(held);before=f.raw()
    assert f.poll()==0 and not f.calls and f.raw()==before


def test_original_l3_start_consumes_only_its_native_edges():
    f=ChordMachine();f.buttons(LEGACY);assert f.poll()==1 and f.mode()==4
    assert f.u.mem_read(f.controller()+0x50,1)==b'\x01' and f.u.mem_read(f.controller()+0x52,1)==b'\x01'
    assert all(f.u.mem_read(f.controller()+LATCHES[name],1)==b'\0' for name in WAB)


@pytest.mark.parametrize('pressure',[.00001,.1,.5,1.0])
def test_positive_normalized_pressure_is_supported_without_rewriting(pressure):
    f=ChordMachine()
    for name in WAB:f.u.mem_write(f.controller()+VALUES[name],struct.pack('<f',pressure))
    before=f.raw();assert f.poll()==1 and f.raw()==before


def test_loaded_world_does_not_reuse_a_gesture_started_while_no_world_exists():
    f=ChordMachine();f.world=0;f.buttons(WAB);assert f.poll()==0
    f.world=WORLD;assert f.poll()==0 and not f.calls
    f.buttons(set());assert f.poll()==0
    f.buttons(WAB);assert f.poll()==1 and len(f.calls)==1


@pytest.mark.parametrize('delta',[-.1,1.01,float('nan'),float('inf')])
def test_invalid_or_expired_delta_cancels_without_fpu_error(delta):
    f=ChordMachine();f.buttons({'White'});assert f.poll()==0
    f.buttons({'A'});assert f.poll(delta=delta)==0
    assert f.mode()==0 and not f.calls


@pytest.mark.parametrize('activate',[False,True])
def test_dispatch_preserves_registers_flags_and_original_two_argument_stack(activate):
    f=ChordMachine();f.buttons(WAB if activate else {'White'})
    native.put(f.u,native.STACK,native.EXIT);native.put(f.u,native.STACK+4,native.INTERFACE)
    native.put(f.u,native.STACK+8,0x3c23d70a)
    for reg,value in SAVED.items():f.u.reg_write(reg,value)
    f.u.reg_write(r.UC_X86_REG_EFLAGS,0x246);f.u.reg_write(r.UC_X86_REG_ESP,native.STACK)
    target=native.EXIT if activate else 0x15da7
    native.run_until(f.u,DISPATCH,{WORLD_METHOD:f.get_world,PLAYER_METHOD:f.get_player,0x16610:f.action},targets=(target,))
    for reg,value in SAVED.items():
        assert f.u.reg_read(reg)==(0 if not activate and reg==r.UC_X86_REG_EAX else value)
    if activate:
        assert f.u.reg_read(r.UC_X86_REG_ESP)==native.STACK+12
        assert f.u.reg_read(r.UC_X86_REG_EFLAGS)==0x246
        assert len(f.calls)==1
    else:
        assert f.u.reg_read(r.UC_X86_REG_ESP)==native.STACK-4
        assert native.get(f.u,native.STACK-4)==SAVED[r.UC_X86_REG_ECX]
        assert f.u.reg_read(r.UC_X86_REG_EFLAGS)&0x8d5==0x95
        assert not f.calls
