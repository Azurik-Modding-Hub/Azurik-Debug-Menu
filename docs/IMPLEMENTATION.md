# PAL implementation and validation boundaries

The patch accepts only the 1,798,144-byte PAL executable with SHA-256
`72e0cf6af079a4024886d9e94812d87d4a35c177135b6196d215abe138866eab`.
Address mapping is read from that XBE's section table.

| Site | Purpose |
| --- | --- |
| VA `0x15F60` | Three-byte jump to the retail menu-only pause predicate at `0x15F40` |
| VA `0x13E6D` | Extend the retail menu factory epilogue with one generic action row |
| VA `0x15DE8` | State-1-only controller handler: Y HUD toggle, WHITE/BACK native exit |
| VA `0x19DE24` | First PlayerPhysics vtable entry, guarded stasis of only the player tick |
| File `0xE6717` | Enable the retail cheat-buttons default so L3 + START exposes the menu |

The original RT/D-pad/R3/L3 cheat table and camera creation code are unchanged.
The hook extends the complete root constructor at `0x138D0`. That retail
constructor creates **Change level...**, **Play Movie...** and **Game state...**;
**Freecam** is registered as a fourth sibling in the same parent object's
children vector. It does not replace an existing entry or require a submenu.
The `0x13E6D` epilogue is reached after all three original registrations.
The menu callback uses the native generic-action ABI (`ECX` = menu context,
`EDX` = row, one stack argument, `RET 4`). Its context's `+0xB4` field is the
cheat owner, `+0xB8` the gameplay interface. It calls the same action dispatcher
at `0x16610` with native action index 3, preserving the native constructor,
camera stack registration and initial transform. An existing camera is reused.
The dispatcher resolves the current gameplay interface and camera stack; there
is no level ID, kingdom name or asset filter in this patch. The shared hooks
apply to all playable realms in this executable. The native dispatcher skips
activation when its current camera stack is empty. Each realm still requires
full-game testing, and title/loading screens are outside the activation scope.

The player guard checks component class, owner chain, state 1 and the real
detached-camera class before returning from the player component's tick.
Every other condition tail-calls the original `0x8C1E0` entry. The player guard
does not modify raw controller state, shared actor movement or world scheduling.
The separate HUD/exit handler consumes the native button edge latches.

HUD handling changes only the **Show UI** CVar object. It never toggles the
retail movie-mode freeze byte. Controller edge latches prevent held Y/WHITE
from repeatedly acting. WHITE and BACK enter the original removal tail at
`0x15E0D`, clear the owner's camera/state and restore prior HUD visibility.

Injected routines and small private state live in a new writable, executable,
preloaded **FCDEBUG** section. Existing section virtual/raw addresses remain
fixed. Header-tail pointer adjustments are required for the extra section
descriptor; original raw bodies are checked against an explicit hook whitelist.

The ISO writer copies the source and relocates only the new executable to the
end of the image. Exactly the root executable directory node's sector/length
fields change in the original prefix. All existing assets stay at their exact
extents; the entire prefix and appended bytes are verified from disk. An
exclusive output create prevents overwriting the original or another output.

Automated x86 tests validate register/stack conventions and local state
transitions. They do **not** run the full Xbox kernel, renderer or gameplay.
The root-menu regression test executes the original base constructor, all three
original row constructors, actual vector insertion and row selection. Heap
allocation and the optional current-level title accessor are intercepted engine
boundaries. The three simulation sites at `0x54961`, `0x55FE0` and `0x562DB`
execute their real calls and branches: only state 1 changes from the paused
path to the live path. These checks establish the binary integration, without
claiming a displayed Xbox menu or a running-world gameplay test.
This release therefore remains experimental until native testing confirms the
menu, full camera lifecycle, player stasis, HUD and interactions with enemies.
