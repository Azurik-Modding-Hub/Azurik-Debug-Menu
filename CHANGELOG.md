# Changelog

## 1.1.0-dev.4 — Reopen the native menu with the timed shortcut

Development preview; the stable 1.0.0 Windows patcher remains unchanged.

- Allow **WHITE → A → B within one second** to reopen the menu after a normal
  close, without entering the original cheat code. Release the gesture buttons
  before starting another sequence.
- Reuse the menu retained by the native close callback. The shortcut no longer
  incorrectly treats a retained, closed menu as an already open window.
- Keep the active-menu guard: repeating the gesture over an open menu does not
  stack another menu. The native open action handles both initial creation and
  reopening.
- Keep English menu labels, Text boxes and Oracles, fragment/seal messages under
  Text boxes, and the Game state key grants. No Animations category is included.
- Full Xemu gameplay verification remains pending; this entry does not claim a
  displayed or tested in-game result.

## 1.0.0 — Keep idle animation and restore controls after Freecam

- Show **Commande menue - 1.0.0** in the native debug-menu header and document
  its L3 + START activation, Freecam selection, White/Back exit and Y HUD toggle.

- Replace the whole-player-tick guard with the native per-player blocked-input path.
  Movement axes and player buttons are neutralized while animation, physics and
  update scheduling continue.
- Preserve the original PlayerPhysics vtable and complete tick. In particular,
  its frame re-registration can no longer be skipped by the Freecam guard.
- Require the native camera-enabled byte as well as camera class, stack and world
  ownership. White/Back exit restores control even with a residual camera entry.
- Preserve real controller input for camera travel and HUD/exit buttons.
- Keep the original cheat, four debug-menu rows and live world updates.
- Include native x86 regressions for the blocked-input path, frame scheduling,
  animation boundaries and repeated exit/activation. In-game verification is pending.

## 0.1.2 — Fix player movement during native freecam

- Correct the player-stasis ownership path: `Entity +0x154` is GameWorld,
  whereas the cheat manager's `+0x40` field belongs to the separate scene
  controller. Stop reading the unrelated GameWorld `+0x40` field.
- Recognize the active native detached camera through GameWorld `+0xA8` and
  require that camera to belong to the player's world. Keep no cached scene
  or camera pointer between frames or level transitions.
- Resume the player tick immediately after the native camera-stack pop, even
  while camera destruction is deferred by the engine.
- Verify the real retail Entity, PlayerPhysics and camera constructors,
  registration/removal routines and indirect PlayerPhysics vtable dispatch.
- Preserve the fourth Freecam row, world updates, Y HUD and WHITE/BACK exit.
  Full in-game verification of this correction is still required.

## 0.1.1 — Native root-menu verification test

- Name the fourth native root-menu row **Freecam** and include its menu layout
  and callback address in the patch/ISO report.
- Verify the complete original retail menu constructor in isolated x86 tests:
  the original three entries and callbacks remain intact, with Freecam appended
  as a fourth peer. Check graceful fallback if its row allocation fails.
- Test all three native simulation callers against the original and patched
  executable, including freecam, normal gameplay and unrelated menu states.
- Explain how to distinguish the patched in-game menu from the Windows installer
  and an old/cached ISO. Full in-game verification is still pending.

## 0.1.0 — Experimental test release

- Add Free Camera to the native debug menu using the original camera cheat.
- Keep world updates active and suspend Azurik's own physics/animation tick.
- Add Y to toggle the HUD and WHITE to exit; preserve native BACK exit.
- Restore prior HUD visibility on exit.
- Include a Windows desktop ISO patcher, Python source, bilingual instructions,
  guarded PAL validation, isolated x86 tests and complete ISO readback checks.
- Full in-game validation remains pending.
