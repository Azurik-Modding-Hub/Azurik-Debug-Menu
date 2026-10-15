# Native Debug Laboratory — development preview

The experimental 1.1.0-dev patch extends the existing cheat menu. It retains
Change level, Play Movie, Game state and Freecam, and adds nested **Boites de
texte**, **Oracles** and **Animations** categories. Open it during loaded
gameplay with **L3 + START**. Select and confirm using the native menu controls.

The text catalogue replays original popup sequences and their voices where
available. Oracle voice lines are grouped by realm, fragments/seals and hints.
The animation catalogue targets the original Azurik/Garret4 clips. Manual
animation mode neutralizes player controls while normal animation/physics and
world updates continue. Choose **Arreter voix / animation** to stop the test and
restore the game's animation selection. The original Freecam WHITE/Y controls
remain available.

Actions queue while the debug window closes, and run only from a normal
scheduled graph frame with the same live world and player. Nothing is played
during the level loader's initialization calls. Idle laboratory code does not
read unattached graph worlds. Popup/voice/animation tests do not set quest flags.

**Game state → Cles (inventaire : 5 places)** contains all 20 verified key types,
grouped by realm. Choose **Donner : ...** to grant that key through the original
inventory pickup routine. Already-held keys stay unchanged. The retail five-slot
limit is retained: a full inventory displays its original capacity message;
no held key is replaced. This deliberately does not offer a misleading “all 20
keys at once” option. Keys change the live inventory and can be saved by the game.
They do not restore realms, grant powers or mark unrelated quests complete.

The EU Eldwin/oracle BODY has one dummy joint and no dedicated skeletal BANM
clips. This preview exposes its actual voices, but does not invent lip sync or
oracle animations. Level-driven oracle appearances and visual effects remain
separate work. The language of the game determines which native localized
resources are available; the original demo popup voices only exist in English.
The executable-only public patch keeps the retail E6 `e6mirrors` image name;
its mismatched singular voice name is not repaired in those original banks.
The separate combined trial also corrects and registers that panel/voice alias.

From a source checkout, create a **new** test image:

```powershell
python laboratory_patcher.py --input "Your Azurik EU.iso" --output "Azurik Debug Laboratory.iso"
```

The input must contain the pristine supported EU executable, including when
it contains edited level files. Existing output files are refused. The stable
Windows patcher and its default 1.0.0 mode remain unchanged.

Native instruction tests cover root construction, nested expansion, reference
counted children, callback arguments, deferred actions, popup/audio/animation
call conventions, all 20 native key grants, duplicate/full-inventory handling,
the original Game state rows and cold-path safety. These are not a completed Xemu test of
all poses, transitions or oracle appearances. The accompanying combined private
trial includes the separately corrected proximity zones and diamond reminder;
the public patcher changes only the executable.
