# Changelog

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
