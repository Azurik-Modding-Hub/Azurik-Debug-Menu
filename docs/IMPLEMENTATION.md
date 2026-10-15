# European implementation and validation boundaries — 1.1.0

The public Windows and command-line patchers install the complete **1.1.0** native
Debug Menu by default. The former 1.0.0 Freecam implementation remains its internal
base; it is not the default public feature set of this release.

Only the 1,798,144-byte European executable with SHA-256
`72e0cf6af079a4024886d9e94812d87d4a35c177135b6196d215abe138866eab`
is accepted. Address mapping comes from that XBE's section table. The installer
verifies instruction signatures before replacing any hook.

## Native integration

| Site | Purpose |
| --- | --- |
| `0x15F60` | Use the retail menu-only pause predicate at `0x15F40` |
| `0x13E6D` | Extend the original root-menu factory with Freecam and menu groups |
| `0x15DE8` | State-1 controller handler: Y HUD and WHITE/BACK exit |
| `0x8500D` | Gate player controls through the native blocked-input branch |
| `0x1395F` | Supply the English versioned menu title |
| `0x15DA0` | Poll the timed menu gesture before the native owner dispatcher |
| `0x66497` | Defer text/voice/key actions to the normal scheduled graph update |

The complete root constructor at `0x138D0` creates **Change level...**,
**Play Movie...** and **Game state...**. The patch retains these entries and adds
**Freecam**, **Text boxes** and **Oracles**, producing six root rows. Keys are
inserted under the native Game state group. Menu objects use the original row
constructor, child insertion, selection and submenu navigation.

The title uses **Debug Menu - 1.1.0**. The original title-copy operation and its
100-byte destination remain unchanged. The global build formatter and build
strings are preserved for other callers. Menu callbacks use the native generic
action ABI: `ECX` is menu context, `EDX` is the row, with one stack argument and
`RET 4`. Context `+0xB4` is the cheat owner; `+0xB8` is the gameplay interface.

## Timed gesture and repeated opening

Each controller has independent state for **WHITE → A → B within one second**.
The window begins at WHITE, with released or overlapping subsequent presses
accepted. Input edges are consumed while analog data remains intact. A completed
gesture waits for button release before it can open the menu again. **L3 + START**
remains an alternative. The retail additional cheat-button actions retain their
disabled default, avoiding the separate WHITE jump/boost behavior.

The owner dispatcher receives the actual frame delta. The gesture checks the
current gameplay interface's world and player getters, avoiding activation during
loading or before a player is attached. It opens only from owner state `0` (normal
play) or `1` (Freecam), not over an active menu.

Ordinary closure through callback `0x13870` restores `owner+0x1C` to normal play
or Freecam according to `owner+0x2C`. It keeps the menu vector at `owner+0x20` /
`owner+0x24`. A nonempty vector does not mean the menu is currently visible.
Action `0` of `0x16610` already supports that retained state: an empty vector
constructs and registers the root; a retained vector jumps to `0x167FE`, setting
state `2` without allocating or inserting another menu. The shortcut invokes this
native path for both first opening and reopening.

State `3` at `0x15E37` destroys and removes the last menu. State `4` at `0x15E7B`
clears the menu vector. Native creation handles those empty-vector cases too.
The active-state guard prevents repeated gestures from stacking windows.

## Freecam, input and simulation

Freecam calls native action `3` through `0x16610`. This preserves the camera
constructor, stack registration and initial transform; an existing camera is
reused. The shared code resolves the current gameplay camera without kingdom or
level-name filters. Each playable realm still needs full-game verification.

At `0x8500D`, inside control update `0x84F40`, EBP is PlayerPhysics, ESI is its
local input packet and EDI is the retail zero. The checked chain is
`PlayerPhysics+0x20 → Entity+0x154 → GameWorld+0xA8 → camera vector`. The last
entry must have class `0x19E3D0`, belong to the player's world through `+0x154`
and have its enabled byte `+0x195 == 1`. No camera pointer is cached across realms.

Active Freecam enters `0x84FFE`, masking local player commands and zeroing movement
axes before continuing to `0x851DC`. Raw input remains available to the camera and
Y/WHITE/BACK handler. Otherwise the displaced lookup is replayed and execution
resumes at `0x85013`. Registers and flags are preserved on both paths.

The original entity tick `0x8C1E0`, PlayerPhysics vtable `0x19DE24`, animation
boundary `0xCB4F0` and scheduling calls `0xAB920` / `0xAB9B0` are retained. This
keeps idle animation and frame maintenance while blocking player commands. The
camera removal routine clears the enabled byte at `0x82775`, allowing normal
controls before deferred camera destruction. Gravity, moving platforms and
scripted actions continue using native simulation.

The older whole-tick guard could skip frame re-registration and leave Azurik
frozen; the input-only path from 1.0.0 remains in 1.1.0. No manual animation
playback action, animation menu or manual actor-animation hook is installed.

HUD handling changes only the **Show UI** CVar. It does not toggle the movie-mode
freeze byte. Edge latches prevent held Y/WHITE from acting repeatedly. WHITE and
BACK use the original camera-removal tail at `0x15E0D` and restore prior HUD state.

## Text boxes, voices and keys

The names-only catalogue contains 67 original popup bases and the oracle voice
resources. Popup previews use the native popup controller, including its matching
voice where present. Additional fragment/seal recordings are grouped under
Text boxes by subject and explicitly marked voice-only; their data is distinct
from the corresponding seal-panel recordings. No unverified panel/audio pair is
created. Language lookup remains native. The executable-only patch does not
rename resources or correct the original E6 mirror panel/voice alias mismatch.

Actions close the menu before running. The scheduled graph-update hook executes
a queued action only with the same attached world and player. It tail-calls the
original graph updater, preserving the caller return address and native stack.
Popup/voice previews do not change quest flags. Voice replacement stops and
releases the previous preview handle before retaining another.

All 20 key types use the native inventory pickup routine. Existing inventory
checks prevent duplicate grants and preserve the five-slot capacity response.
The patch does not overwrite inventory entries or alter unrelated quest/power
flags. Granted keys are live game state and can be saved normally.

## Image writing and verification

Injected code and private state live in additional preloaded XBE sections. Original
raw section bodies are compared against an explicit hook whitelist. Existing
section virtual and raw addresses remain fixed; header pointers are adjusted for
the extra descriptors. The source executable is never modified in place.

The ISO writer copies the source and appends the patched executable. Only the
root executable directory node's sector/length fields change in the copied
original prefix. Assets retain their exact extents and bytes. The entire prefix
and appended data are reread from disk. Exclusive output creation refuses an
existing file and protects both the input image and other outputs.

## What the tests establish

Isolated x86 tests execute original constructors, row/vector operations, menu
selection, ordinary closure, reopening, scheduler dispatch, input normalization,
key pickup and guarded callbacks. Heap allocation and selected engine boundaries
are intercepted. The tests establish register/stack conventions, control flow,
inventory behavior and preserved frame scheduling; they do not run the complete
Xbox kernel, renderer or game.

The desktop capture illustrates the patcher. Menu and control diagrams are
explicitly explanatory. None is evidence of an in-game result. Full Xemu tests
remain necessary for repeated menu use, transitions, visual/text/audio previews,
idle animation, normal control after Freecam, HUD and enemy interactions.
