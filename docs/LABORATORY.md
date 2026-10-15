# Native Debug Laboratory — 1.1.0

Version 1.1.0 installs the complete native Debug Menu from the Windows patcher or
its command-line entry point. The title **Debug Menu - 1.1.0** and the added menu
labels are **English**, independently of the game's playback language.

## Open, close and reopen

During loaded gameplay, press **WHITE, then A, then B within one second**.
You may release each button before pressing the next. Holding earlier buttons
also works, including all three in one frame. The one-second window starts at
WHITE; it does not restart at each following button. An expired or incomplete
sequence requires a fresh WHITE press. **L3 + START** remains an alternative.

Release the gesture buttons before beginning another sequence. After closing the
menu normally, repeat **WHITE → A → B** to reopen it without the original cheat
code. Normal closure retains the native menu object, which the game's open action
reuses. The shortcut does not stack windows over an already open menu. It checks
the actual current world and player, so it cannot queue a menu before the player
has spawned. Analog inputs are preserved; recognized button edges are consumed.

The retail **enable cheat buttons** setting retains its disabled default. It is
not needed for these menu shortcuts and would assign additional jump/boost actions
to WHITE. Normal player action buttons keep their original behaviour. **WHITE
alone still exits Freecam**; starting the sequence there can first return to normal
play before A and B open the menu. **Y** retains its Freecam HUD toggle.

## Six root entries

| Entry | Contents |
| --- | --- |
| **Change level...** | Original native level selection |
| **Play Movie...** | Original native movie selection |
| **Game state...** | Original state tools, plus **Keys (5 inventory slots)** |
| **Freecam** | Original detached camera, live world and blocked player commands |
| **Text boxes** | 67 original popup sequences and fragment/seal message previews |
| **Oracles** | Realm introductions and other spoken hints |

**Seals** under Text boxes contains the six original seal panels. **Fragment and
seal messages** also contains nine additional recordings, marked **(voice only)**
where a matching panel has not been identified. These messages are not duplicated
under Oracles. **Stop voice** ends an audio preview.

There is no Animations category or manual animation playback. Retail actor
animation code is preserved. Normal game animations and Azurik's idle movement
in Freecam continue through the existing blocked-input path. Voice previews do
not recreate an oracle's appearance, lip movements or effects.

**Game state → Keys (5 inventory slots)** contains all 20 verified key types,
grouped by realm. **Give: ...** uses the original inventory pickup routine.
Already-held keys stay unchanged. The five-slot limit is preserved: a full
inventory shows the original capacity message and no held key is replaced.
Granted keys change the live inventory and may be saved by the game. They do not
restore realms, grant powers or complete other quests.

Popup and voice actions wait until the menu closes, then run on a normal
scheduled frame with the same live world and player. They do not set quest flags.
The game's language controls localized playback; original demo popup voices exist
only in English. Additional fragment/seal recordings are distinct from the seal
popup sounds; the thematic grouping does not invent a panel/audio pairing.

The executable-only patch keeps the original E6 `e6mirrors` image name and its
mismatch with the singular voice name. A separate private trial that also changes
language banks is not included in this release.

## Install into a new ISO

The Windows patcher installs all 1.1.0 menu features by default. It can also run
from source:

```powershell
python patcher.py --input "Your Azurik EU.iso" --output "Azurik Debug Menu 1.1.0.iso"
```

The dedicated ISO entry point remains available:

```powershell
python laboratory_patcher.py --input "Your Azurik EU.iso" --output "Azurik Debug Menu 1.1.0.iso"
```

The input must contain the pristine supported EU executable, including when it
contains edited level files. Existing outputs are refused and the input is
preserved. No game files, private recordings or private trial ISO are distributed.
Cold-boot the new ISO in Xemu; an old snapshot can retain the old executable.

## Validation boundaries

Release validation recorded 247 passing automated tests, including the public
desktop/CLI default patch. The compiled Windows application produced the expected
1.1.0 executable and a fully verified ISO, preserving its source image.
Native tests execute the scheduled input caller, owner dispatcher,
menu action, complete root constructor and ordinary-close callback. They cover
the timed gesture, released/overlapping presses, timeouts, alternative shortcut,
opening and reopening, normal play, Freecam, controller selection, loading guards,
original Game state rows, all key pickups, duplicate/full-inventory handling,
popup/audio arguments and deferred actions. They also execute native CVar
construction, Xbox XInput normalization and player action packing, with a negative
control reproducing the former WHITE jump/boost.

These isolated CPU tests and ISO readback checks do not certify full Xemu
gameplay. Repeated closes and shortcut openings, visual presentation, voices,
text boxes, realm transitions, HUD, idle animation and control restoration still
require an in-game test.
