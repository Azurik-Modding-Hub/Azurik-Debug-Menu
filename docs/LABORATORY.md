# Native Debug Laboratory — 1.1.0-dev.3

This preview extends the existing in-game menu. Its title and all added menu
labels are **English**, independently of the game's playback language.

## Open the menu

During loaded gameplay, press **WHITE, then A, then B within one second**.
You may release each button before pressing the next. Holding the earlier
buttons also works, including all three in one frame. The one-second window
starts at WHITE, rather than restarting at every following key. A missed or
expired sequence requires a fresh WHITE press. **L3 + START** remains available.

The menu opens once per gesture. Release the remaining gesture buttons before
opening it again. It does not stack windows over an already open menu. The
actual Scene world and player getters prevent queuing an opening before a
player has spawned. Analog input values are preserved; only recognised button
edges are consumed.

The retail **enable cheat buttons** setting now retains its disabled default.
It is not required for the menu: enabling it had incorrectly assigned WHITE
to additional player jump/boost actions. Normal movement and the game's usual
jump/action buttons retain their original behaviour. **WHITE alone still exits
Freecam**; when starting the sequence from Freecam, a separate WHITE press can
therefore return to normal play before A and B open the menu. **Y** retains its
Freecam HUD toggle. Use the native menu navigation controls.

## Menu contents

- **Change level...**, **Play Movie...**, **Game state...** and **Freecam**.
- **Text boxes**: 67 original popup sequences, including their voices where
  available. **Seals** contains the six original seal panels. **Fragment and
  seal messages** also contains nine additional spoken hints, marked
  **(voice only)**: no matching panel is claimed for those voice previews.
- **Oracles**: realm introductions and other spoken hints. Fragment/seal
  messages are grouped under Text boxes rather than duplicated here.
- **Stop voice** stops an audio preview.

There is no Animations category or manual animation playback action. The
retail actor animation code is preserved. Normal game animations and Azurik's
idle movement in Freecam continue through the existing blocked-input path.

**Game state → Keys (5 inventory slots)** contains all 20 verified key types,
grouped by realm. **Give: ...** grants one key using the original inventory
pickup routine. Already-held keys stay unchanged. The original five-slot
limit is retained: a full inventory shows its original capacity message and
no held key is replaced. Keys change the live inventory and can be saved by
the game. They do not restore realms, grant powers or complete other quests.

Popup and voice actions wait until the debug menu closes, then run on a normal
scheduled frame with the same live world and player. They do not set quest
flags. The game's language controls localized playback; original demo popup
voices exist only in English. Additional fragment/seal oracle recordings are
distinct from the seal popup sounds; their thematic grouping does not invent
a new panel/audio pairing.

The public executable-only patch keeps the original E6 `e6mirrors` image name
and its existing mismatch with the singular voice name. The separate combined
trial also corrects and registers that panel/voice alias in the language banks.

## Build a separate test ISO

```powershell
python laboratory_patcher.py --input "Your Azurik EU.iso" --output "Azurik Debug Laboratory.iso"
```

The input must contain the pristine supported EU executable, including when
it contains edited level files. Existing output files are refused. The stable
Windows patcher and its default 1.0.0 mode remain unchanged. No game files or
private trial ISO are distributed in this repository.

Native tests execute the real scheduled input caller, the owner dispatcher,
the retail menu action and the complete root constructor. They cover the timed gesture, released/overlapping steps, timeouts, the alternative
shortcut, normal play and Freecam, controller selection, loading guards, the original Game state rows, all 20 key pickups,
duplicate/full-inventory handling, popup/audio arguments and deferred actions.
They also execute the native CVar constructor, actual Xbox XInput button
normalisation and player action packing, with a negative control reproducing
the former WHITE jump/boost. These are isolated CPU tests, not a complete Xemu
gameplay certification.
