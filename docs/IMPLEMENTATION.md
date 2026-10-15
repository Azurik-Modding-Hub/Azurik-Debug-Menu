# PAL implementation and validation boundaries

The patch accepts only the 1,798,144-byte PAL executable with SHA-256
`72e0cf6af079a4024886d9e94812d87d4a35c177135b6196d215abe138866eab`.
Address mapping is read from that XBE's section table.

| Site | Purpose |
| --- | --- |
| VA `0x15F60` | Three-byte jump to the retail menu-only pause predicate at `0x15F40` |
| VA `0x13E6D` | Extend the retail menu factory epilogue with one generic action row |
| VA `0x15DE8` | State-1-only controller handler: Y HUD toggle, WHITE/BACK native exit |
| VA `0x8500D` | Gate player controls through the native blocked-input branch at `0x84FFE` |
| VA `0x1395F` | Supply the versioned debug-menu header to the existing native title copy |
| File `0xE6717` | Enable the retail cheat-buttons default so L3 + START exposes the menu |

The original RT/D-pad/R3/L3 cheat table and camera creation code are unchanged.
The hook extends the complete root constructor at `0x138D0`. That retail
constructor creates **Change level...**, **Play Movie...** and **Game state...**;
**Freecam** is registered as a fourth sibling in the same parent object's
children vector. It does not replace an existing entry or require a submenu.
The `0x13E6D` epilogue is reached after all three original registrations.
The header call at `0x1395F` is replaced by a same-size `MOV EAX` pointing to
the null-terminated ASCII string **Commande menue - 1.0.0** in FCDEBUG. The
native parent-title copy and its 100-byte destination remain unchanged. The
global build formatter and original build strings are preserved for other callers.
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

The player input gate checks component class, Entity, GameWorld and the active
camera stack at `0x8500D` inside the retail control update `0x84F40`. At this
site EBP is PlayerPhysics, ESI its local input packet and EDI the retail zero.
The chain is `PlayerPhysics +0x20 -> Entity +0x154 -> GameWorld +0xA8 -> camera vector`.
The last entry must have the detached-camera class `0x19E3D0`, belong to the
player's world through its own `+0x154`, and have its enabled byte `+0x195 == 1`.
No player/world/camera pointer is cached between frames or realms.

Active Freecam enters the native branch `0x84FFE`. This masks local player
buttons and zeroes movement axes, then continues to `0x851DC`. Raw controller
state is preserved for camera movement and the Y/WHITE/BACK handler.
Otherwise the gate replays the displaced six-byte controller lookup and resumes
at `0x85013`. PUSHFD/PUSHAD and POPAD/POPFD preserve registers and flags on
both paths. Empty/inverted stacks, absent links, mismatching class/world and
disabled cameras use normal native input handling.

The original tick `0x8C1E0` and PlayerPhysics vtable `0x19DE24` are unchanged.
The whole-tick RET in 0.1.2 skipped `AB920` / `AB9B0` frame re-registration and
could leave the player unscheduled after exit. The new gate preserves those
calls, animation boundary `CB4F0`, state handling and physics/root-motion work.
It disables player commands while retaining idle animation and normal simulation.
Gravity, moving platforms and scripted actions still follow native behavior.

The 0.1.1 ownership check confused GameWorld with the separate scene controller.
Their fields are distinct: the scene has `+0x2C` for GameWorld and `+0x40` for
the cheat manager. The input gate uses the world's actual camera vector.
Real Entity/PlayerPhysics/camera constructors and blocked-input/exit instructions
are verified before patching. The native camera removal routine clears byte
`+0x195` at `0x82775`, so controls return even before deferred camera removal.
The separate developer drone uses this same native camera class and also blocks
player controls when enabled; its activation setting remains off by default.

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
Player-input regressions execute the retail constructors, vector handling,
blocked-input branch and complete PlayerPhysics tick. Intercepted engine
boundaries record scheduling, animation and downstream state/physics calls.
Tests cover active Freecam, normal gameplay, disabled residual camera entries,
White/Back exit and repeated activation. They establish control flow and preserved
updates; they do not reproduce rendered idle animation or every gameplay response.
This release remains experimental until Xemu testing confirms idle animation,
normal control after exit, realm transitions, HUD and enemy interactions.

## Development preview 1.1.0-dev.4: reopening the retained menu

The preview adds the timed **WHITE → A → B** shortcut independently of the
retail cheat-buttons setting. All three presses must fit within one second of
WHITE. The stable 1.0.0 patch described above remains a separate mode.

The native normal-close callback at `0x13870` restores the cheat owner's state
at `+0x1C` to normal play or Freecam according to `owner+0x2C`. It retains the
menu vector at `owner+0x20` / `owner+0x24`. A nonempty vector therefore does not
mean the menu is currently open.

The shortcut permits the native open action only while the owner's state is
`0` or `1`. It no longer requires that retained vector to be empty. Action `0`
of `0x16610` checks the vector itself: an empty vector constructs and registers
the root menu; a retained menu jumps directly to `0x167FE`, setting state `2`
without allocating or inserting another window. The next completed gesture
can therefore reopen a normally closed menu, while an already open menu stays
protected from repeated insertion.

This differs from state `3` at `0x15E37`, which destroys and removes the last
menu, and state `4` at `0x15E7B`, which clears the menu vector. Native creation
continues to cover those empty-vector cases. These control-flow observations
do not constitute a full Xemu gameplay test.
