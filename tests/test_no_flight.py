"""Private optional native regressions for retail WHITE developer controls.

Provide AZURIK_XBE pointing at a pristine PAL/EU executable. No original file
is written. The retail CVar constructor and PlayerPhysics input instructions
execute; the CVar registry and final deferred camera deletion are boundaries.
These checks do not claim a rendered Xemu gameplay test.
"""
import os
from pathlib import Path
import struct

import pytest
from unicorn import x86_const as r

import test_x86 as native
from freecam.laboratory import patch_xbe as laboratory_patch
from freecam.patch import patch_xbe as stable_patch


CVAR_GLOBAL = 0x38EA20
BUTTONS = {'A': 0x18, 'B': 0x1C, 'Y': 0x24, 'White': 0x2C, 'R3': 0x3C}
CATALOG = [dict(label='Text boxes', children=[
    dict(label='Training', kind=1, key='loc/english/popups/training1')])]


@pytest.fixture(scope='module')
def images():
    path = os.environ.get('AZURIK_XBE')
    if not path:
        pytest.skip('Optional native EU audit: provide your own pristine AZURIK_XBE.')
    source = Path(path).read_bytes()
    experimental, metadata = laboratory_patch(source, CATALOG)
    old_freecam, _ = stable_patch(source)
    return source, experimental, old_freecam, metadata


def initialize_native_cheat_cvar(u):
    """Execute original F6710 constructor and capture the real registry args."""
    observed = []

    def register(uc):
        sp = uc.reg_read(r.UC_X86_REG_ESP)
        args = [native.get(uc, sp + 4 + n * 4) for n in range(6)]
        name = bytes(uc.mem_read(args[1], 80)).split(b'\0', 1)[0]
        observed.append(dict(address=args[0], name=name, default=args[2], tail=args[3:]))
        assert args[0] == CVAR_GLOBAL
        assert name == b'enable cheat buttons'
        assert args[3:] == [0, 2, 0]
        native.put(uc, args[0], native.HUD)
        native.put(uc, native.HUD + 4, args[2])
        uc.reg_write(r.UC_X86_REG_EAX, native.HUD)
        native.return_from(uc, 24)

    native.put(u, native.STACK, native.EXIT)
    u.reg_write(r.UC_X86_REG_ESP, native.STACK)
    native.run_until(u, 0xF6710, {
        0x9F7B0: register,
        0xEB678: lambda uc: native.return_from(uc),  # Process-exit registration.
    })
    assert u.reg_read(r.UC_X86_REG_ESP) == native.STACK + 4
    assert len(observed) == 1
    return observed[0]


def player_input(image, held, *, force_cheat_buttons=None):
    u, addresses, _, _ = native.construct_native_player_world(image)
    configured = initialize_native_cheat_cvar(u)['default']
    packet = 0x718400
    native.prepare_native_input(u, addresses, packet)
    # The common fixture enables developer buttons for its camera-input tests.
    # Restore the value emitted by the *actual* XBE CVar constructor here.
    native.put(u, native.HUD + 4, configured if force_cheat_buttons is None else force_cheat_buttons)
    for name in held:
        u.mem_write(native.CONTROLLER + BUTTONS[name], struct.pack('<f', 1.0))
    before = bytes(u.mem_read(native.CONTROLLER, 0x54))
    stack = addresses['stack']
    native.put(u, stack, native.EXIT)
    native.put(u, stack + 4, addresses['physics'])
    u.reg_write(r.UC_X86_REG_ESP, stack)
    u.reg_write(r.UC_X86_REG_ESI, packet)
    u.reg_write(r.UC_X86_REG_EFLAGS, 0x202)
    u.reg_write(r.UC_X86_REG_FPCW, 0x37F)
    u.reg_write(r.UC_X86_REG_FPSW, 0)
    # Native prologue, ownership traversal, controller lookup, patched input
    # gate, action packing and stick magnitude all execute before this boundary.
    native.run_until(u, 0x84F40, targets=(0x851F1,), count=3000)
    return dict(default=configured,
                actions=u.mem_read(packet + 0x20, 1)[0],
                axes=struct.unpack('<2f', u.mem_read(packet + 8, 8)),
                magnitude=struct.unpack('<f', u.mem_read(packet + 0x1C, 4))[0],
                rawBefore=before,
                rawAfter=bytes(u.mem_read(native.CONTROLLER, 0x54)))


def test_real_native_cvar_constructor_retains_disabled_retail_default(images):
    source, laboratory, old_freecam, _ = images
    for image, expected in [(source, 0), (laboratory, 0), (old_freecam, 1)]:
        result = initialize_native_cheat_cvar(native.machine(image))
        assert result['default'] == expected
    # This verifies the precise one-byte PUSH immediate; an old development
    # build carrying the unintended default=1 fails the laboratory assertion.
    assert laboratory[0xE6717] == source[0xE6717] == 0
    assert old_freecam[0xE6717] == 1


@pytest.mark.parametrize('analog_slots', [{0}, {1}, {5}, {0, 1, 5}])
def test_real_xinput_poll_maps_physical_a_b_white_to_the_expected_game_fields(images, analog_slots):
    source, _, _, _ = images
    u = native.machine(source)
    native.put(u, 0x1C02B4, 0x1234)  # Attached controller handle.
    native.put(u, native.STACK, native.EXIT)
    native.put(u, native.STACK + 4, 0)
    u.reg_write(r.UC_X86_REG_ESP, native.STACK)
    u.reg_write(r.UC_X86_REG_FPCW, 0x37F)
    u.reg_write(r.UC_X86_REG_FPSW, 0)

    def raw_xinput(uc):
        sp = uc.reg_read(r.UC_X86_REG_ESP)
        assert native.get(uc, sp + 4) == 0x1234
        destination = native.get(uc, sp + 8)
        # Retail Xbox XINPUT_STATE: packet DWORD, digital WORD, eight analog
        # bytes (A,B,X,Y,Black,White,LT,RT), then four signed stick WORDs.
        analog = [255 if index in analog_slots else 0 for index in range(8)]
        uc.mem_write(destination, struct.pack('<IH8B4h', 1, 0, *analog, 0, 0, 0, 0))
        uc.reg_write(r.UC_X86_REG_EAX, 0)
        native.return_from(uc, 8)

    native.run_until(u, 0xA2A00, {0x19068E: raw_xinput}, count=2000)
    assert u.reg_read(r.UC_X86_REG_ESP) == native.STACK + 8
    actual = struct.unpack('<8f', u.mem_read(native.CONTROLLER + 0x18, 32))
    assert actual == pytest.approx(tuple(1.0 if n in analog_slots else 0.0 for n in range(8)))


@pytest.mark.parametrize('held', [set(), {'White'}, {'R3'}, {'White', 'R3'}])
def test_white_and_right_stick_do_not_create_developer_jump_or_boost_bits(images, held):
    source, laboratory, _, _ = images
    original = player_input(source, held)
    result = player_input(laboratory, held)
    assert result['default'] == 0
    assert result['actions'] & (0x04 | 0x40) == 0
    assert result == original
    assert result['rawAfter'] == result['rawBefore']
    assert result['axes'] == (0.75, 0.5)
    assert result['magnitude'] == pytest.approx((0.75 ** 2 + 0.5 ** 2) ** 0.5)


@pytest.mark.parametrize('held,expected_bits', [({'White'}, 0x44), ({'R3'}, 0x40), ({'White', 'R3'}, 0x44)])
def test_negative_control_enabled_developer_buttons_reproduces_the_unwanted_input(images, held, expected_bits):
    _, _, old_freecam, _ = images
    result = player_input(old_freecam, held)
    assert result['default'] == 1
    assert result['actions'] & (0x04 | 0x40) == expected_bits
    assert result['rawAfter'][:0x48] == result['rawBefore'][:0x48]


@pytest.mark.parametrize('held', [{'A'}, {'B'}, {'Y'}, {'White', 'A', 'B'}, {'A', 'B', 'Y'}])
def test_normal_player_buttons_and_movement_match_pristine_game(images, held):
    source, laboratory, _, _ = images
    original = player_input(source, held)
    result = player_input(laboratory, held)
    assert result == original
    assert result['axes'] == (0.75, 0.5)
    if 'Y' in held:
        assert result['actions'] & 0x04, 'Native Y jump must remain available.'
    if 'A' in held:
        assert result['actions'] & 0x08, 'Native A action must remain available.'
    if 'B' in held:
        assert result['actions'] & 0x10, 'Native B action must remain available.'


def test_white_still_exits_actual_native_freecam_and_restores_player_input(images):
    _, laboratory, _, _ = images
    u, addresses, create_camera, dispatch = native.construct_native_player_world(laboratory)
    assert initialize_native_cheat_cvar(u)['default'] == 0
    create_camera()
    camera, stack = addresses['detached'], addresses['stack']
    deferred = native.get(u, 0x19E3D0 + 0xB8)
    native.put(u, native.OWNER + 0x1C, 1)
    native.put(u, native.OWNER + 0x2C, camera)
    native.put(u, native.HUD_GLOBAL, native.HUD)
    native.put(u, native.HUD + 4, 0)
    native.put(u, 0x1A9A64, 0)
    u.mem_write(native.CONTROLLER, bytes(0x54))
    native.put(u, native.CONTROLLER + 0x2C, 0x3F800000)
    native.put(u, stack, native.EXIT)
    native.put(u, stack + 4, 0)
    native.put(u, stack + 8, 0)
    u.reg_write(r.UC_X86_REG_ESP, stack)
    u.reg_write(r.UC_X86_REG_EDI, native.OWNER)
    native.run_until(u, 0x15DA0, {deferred: lambda uc: native.return_from(uc)}, count=3000)
    assert native.get(u, native.OWNER + 0x1C) == 0
    assert native.get(u, native.OWNER + 0x2C) == 0
    assert u.mem_read(native.CONTROLLER + 0x4D, 1) == b'\x01'
    assert u.mem_read(camera + 0x195, 1) == b'\0'
    assert native.get(u, addresses['registry'] + 4) == addresses['slots'] + 4
    assert dispatch() == 0x84F40
    assert native.native_input_frame(u, addresses)['axes'] == (0.75, 0.5)
