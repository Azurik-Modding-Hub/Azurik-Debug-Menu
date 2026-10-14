"""Synthetic x86 tests run without a copyrighted game executable."""
import random
import struct

import pytest
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import x86_const as r

from freecam.player import emit_guard, PLAYER_TICK_VA, PLAYER_VTABLE_VA, CAMERA_VTABLE_VA

CODE, EXIT, STACK = 0x400000, 0x510000, 0x600800
COMPONENT, ENTITY, WORLD, REGISTRY, CAMERA, CAMERA_SLOTS = (0x700000 + i * 0x1000 for i in range(6))
CONTROLLER = 0x800000


def machine():
    u = Uc(UC_ARCH_X86, UC_MODE_32)
    for address, size in ((CODE, 0x1000), (PLAYER_TICK_VA & ~0xFFF, 0x1000),
                          (EXIT, 0x1000), (STACK & ~0xFFF, 0x1000),
                          (COMPONENT, 0x6000), (CONTROLLER, 0x1000)):
        u.mem_map(address, size)
    u.mem_write(CODE, emit_guard(CODE))
    return u


def run(u, state, *, missing=None, wrong_component=False, wrong_camera=False,
        flags=0x246, unsafe_later_pointer=False, wrong_world=False,
        active_camera=None, empty_stack=False, inverted_stack=False, world40=0xDEADC000):
    def put(address, value):
        u.mem_write(address, struct.pack('<I', value))
    if active_camera is None:
        active_camera = state == 1
    u.mem_write(COMPONENT, b'\x5a' * 0x6000)
    u.mem_write(CONTROLLER, bytes(range(256)) * 16)
    put(COMPONENT, 0x11223344 if wrong_component else PLAYER_VTABLE_VA)
    put(COMPONENT + 0x20, ENTITY)
    put(ENTITY + 0x154, WORLD)
    # A world is not the scene controller. This deliberately points nowhere;
    # the old incorrect world+0x40 cheat-manager chain would crash this case.
    put(WORLD + 0x40, world40)
    put(WORLD + 0xA8, REGISTRY)
    put(REGISTRY, CAMERA_SLOTS)
    put(REGISTRY + 4, CAMERA_SLOTS + (0 if empty_stack else -4 if inverted_stack else 4))
    put(REGISTRY + 8, CAMERA_SLOTS + 16)
    put(CAMERA_SLOTS, CAMERA)
    put(CAMERA, 0x55667788 if wrong_camera or not active_camera else CAMERA_VTABLE_VA)
    put(CAMERA + 0x154, WORLD + 0x800 if wrong_world else WORLD)
    missing_sites = {'entity': COMPONENT + 0x20, 'world': ENTITY + 0x154,
                     'stack': WORLD + 0xA8, 'camera': CAMERA_SLOTS}
    if missing:
        put(missing_sites[missing], 0)
    if unsafe_later_pointer:
        if wrong_component:
            put(COMPONENT + 0x20, 0xDEADC000)
        else:
            assert empty_stack or inverted_stack
            put(REGISTRY, 0xDEADC004)
            put(REGISTRY + 4, 0xDEADC004 if empty_stack else 0xDEADC000)
    memory = bytes(u.mem_read(COMPONENT, 0x6000))
    controller = bytes(u.mem_read(CONTROLLER, 0x1000))
    put(STACK, EXIT)
    registers = {r.UC_X86_REG_EAX: 0x12345678, r.UC_X86_REG_EBX: 0x23456789,
                 r.UC_X86_REG_ECX: COMPONENT, r.UC_X86_REG_EDX: 0x3456789A,
                 r.UC_X86_REG_ESI: 0x456789AB, r.UC_X86_REG_EDI: 0x56789ABC,
                 r.UC_X86_REG_EBP: 0x6789ABCD}
    for register, value in registers.items():
        u.reg_write(register, value)
    u.reg_write(r.UC_X86_REG_ESP, STACK)
    u.reg_write(r.UC_X86_REG_EFLAGS, flags)
    original_flags = u.reg_read(r.UC_X86_REG_EFLAGS)
    destinations, writes = [], []
    def code_hook(uc, address, size, userdata):
        if address in (PLAYER_TICK_VA, EXIT):
            destinations.append(address)
            uc.emu_stop()
    def write_hook(uc, access, address, size, value, userdata):
        writes.append((address, size))
    code_handle = u.hook_add(UC_HOOK_CODE, code_hook)
    write_handle = u.hook_add(UC_HOOK_MEM_WRITE, write_hook)
    try:
        u.emu_start(CODE, 0, count=100)
    finally:
        u.hook_del(code_handle)
        u.hook_del(write_handle)
    stopped = active_camera and not (missing or wrong_component or wrong_camera
                                    or wrong_world or empty_stack or inverted_stack)
    assert destinations == [EXIT if stopped else PLAYER_TICK_VA]
    assert u.reg_read(r.UC_X86_REG_ESP) == STACK + (4 if stopped else 0)
    assert all(u.reg_read(register) == value for register, value in registers.items())
    assert u.reg_read(r.UC_X86_REG_EFLAGS) == original_flags
    assert bytes(u.mem_read(COMPONENT, 0x6000)) == memory
    assert bytes(u.mem_read(CONTROLLER, 0x1000)) == controller
    assert writes == [(STACK - i * 4, 4) for i in range(1, 5)]
    assert bytes(u.mem_read(STACK, 4)) == struct.pack('<I', EXIT)


def test_all_native_states_and_random_signed_boundaries():
    u = machine()
    states = list(range(64)) + [0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFE, 0xFFFFFFFF]
    rng = random.Random(20261010)
    states += [rng.getrandbits(32) for _ in range(4096)]
    for state in states:
        run(u, state)


@pytest.mark.parametrize('missing', ['entity', 'world', 'stack', 'camera'])
def test_null_chain_never_suppresses_player(missing):
    run(machine(), 1, missing=missing)


def test_foreign_component_never_follows_its_unmapped_entity():
    run(machine(), 1, wrong_component=True, unsafe_later_pointer=True)


def test_foreign_camera_never_suppresses_player():
    run(machine(), 1, wrong_camera=True)


@pytest.mark.parametrize('kind', ['empty', 'inverted'])
def test_empty_or_inverted_stack_never_dereferences_unmapped_slots(kind):
    run(machine(), 1, empty_stack=kind == 'empty', inverted_stack=kind == 'inverted',
        unsafe_later_pointer=True)


def test_camera_from_another_world_never_suppresses_player():
    run(machine(), 1, wrong_world=True)


@pytest.mark.parametrize('world40', [0, 1, 0xFFFFFFFF, 0xDEADC000])
def test_actual_world_camera_stack_ignores_unrelated_world40_field(world40):
    run(machine(), 1, world40=world40)


def test_active_native_camera_does_not_depend_on_a_fake_cheat_manager_state():
    u = machine()
    for unrelated_state in range(64):
        run(u, unrelated_state, active_camera=True)


def test_all_arithmetic_flags_and_enter_exit_without_sticky_state():
    u = machine()
    for arithmetic in range(64):
        flags = 0x202 | sum(bit for pos, bit in enumerate((1, 4, 16, 64, 128, 2048))
                            if arithmetic & (1 << pos))
        for state in (0, 1, 2, 3):
            run(u, state, flags=flags)
    for state in (1, 0, 1, 2, 1, 3, 0):
        run(u, state, flags=0x646)


def test_complete_code_and_original_tail_destination():
    code = emit_guard(CODE)
    instructions = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(code, CODE))
    assert len(code) == 125
    assert sum(i.size for i in instructions) == len(code)
    assert sum(i.mnemonic in ('je', 'jne', 'jbe') for i in instructions) == 9
    assert instructions[-1].mnemonic == 'jmp'
    assert instructions[-1].op_str == hex(PLAYER_TICK_VA)


@pytest.mark.parametrize('address', [0, -1, 0xFFFFFFFF, 0xF0000000, '0x400000', None])
def test_invalid_or_unreachable_address_rejected(address):
    with pytest.raises(ValueError):
        emit_guard(address)
