# Azurik Debug Menu

A standalone **PAL / European Xbox test patch** for *Azurik: Rise of Perathia*.
It extends the **existing in-game debug menu** with **Free Camera** and invokes the native
camera used by the original cheat. The world continues updating while Azurik's
own physics and animation tick is held. Press **WHITE** to return to gameplay;
press **Y** to hide or show the HUD.

The patch uses shared game code and the currently loaded gameplay camera. It
applies across **all playable kingdoms** in the supported European build, with
no W1 restriction. Individual kingdoms still need in-game verification. Activate
freecam during loaded gameplay, rather than on the title or loading screens.

**Status: experimental 0.1.0.** Isolated x86 tests and ISO readback verification
are provided. A complete in-game test is still required, including collisions,
menu transitions and HUD behaviour. No game executable, ISO, save, model or texture
is distributed in this repository or its downloads.

[Guide français](README.fr.md) · [Technical notes](docs/IMPLEMENTATION.md)
· [Azurik Level Editor](https://github.com/Azurik-Modding-Hub/Azurik-Level-Editor)

![Windows ISO patcher — actual desktop interface](docs/patcher-windows.png)

This screenshot shows the patcher interface, rather than an in-game test result.

## Controls

| Action | Xbox controller |
| --- | --- |
| Open the native debug menu | **L3 + START** |
| Activate the original freecam | Select **Free Camera**, then confirm with **START** |
| Camera movement and orientation | Original native camera controls |
| Hide / show the HUD | **Y**, while freecam is active |
| Exit freecam | **WHITE**; native **BACK** is also preserved |
| Original cheat activation | **RT, D-pad Down, Up, Down, Up, R3, L3** |

For the original sequence, release each button before the next; do not keep RT
held throughout it. WHITE is an exit button. No WHITE + R3 activation is added.
The HUD returns to its previous visibility when exiting with WHITE or BACK.

## Windows

Download the **Windows patcher** from [Releases](https://github.com/Azurik-Modding-Hub/Azurik-Debug-Menu/releases).
Open `Azurik Freecam Patcher.exe`, choose your own Azurik Xbox ISO/XISO, and choose
a **new** output file. The patcher copies the image, installs the new executable
in that copy, and verifies the complete game data. It never replaces an existing
output or changes the input image.

Boot the new image in Xemu with a full console restart. An old emulator snapshot
can keep the previous executable in memory. Your original image remains the
rollback copy. To remove the patch, boot that original image again.

EDIT : You need to clear the cache for the changes you make to take effect ! Don’t worry, this won’t affect your save files in any way!

Only clear Xbox cache partitions X/Y/Z. Keep partition E and the virtual disk
containing your saves. The patcher itself never clears cache or changes saves.

## From source

Python **3.10 or newer** is sufficient to run the patcher; no runtime packages
are required. Windows Python includes the desktop interface through Tkinter.

```powershell
python patcher.py
python patcher.py --input "Azurik.iso" --output "Azurik-Freecam-Debug.iso"
python patcher.py --input "default.xbe" --output "default-freecam.xbe"
```

Only the pristine PAL/EU executable is supported. Its SHA-256 is
`72e0cf6af079a4024886d9e94812d87d4a35c177135b6196d215abe138866eab`.
Other regions, previously patched executables, and truncated inputs are refused.
An ISO with edited levels is supported if its executable is still this original
build: **all level files remain byte-for-byte identical** to the input ISO.

## Testing and building

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Optional local retail validation (the game file is not uploaded or committed):

```powershell
$env:AZURIK_XBE = "C:\YourOwnDump\default.xbe"
python -m pytest -q
```

To build the desktop patcher:

```powershell
python -m pip install pyinstaller
powershell -File ".\Build Windows.ps1"
```

## Scope

- The native debug menu's existing tools remain available.
- Simulation, other actors and effects continue during freecam.
- Azurik's own physics/animation update is suspended during freecam; normal
  updates resume on exit. External pushing and scripted relocation need in-game
  verification.
- Camera-only travel does not make player-triggered portals load other levels.
- The patch changes the executable and its ISO directory pointer. It does not
  modify level assets, save files, EEPROMs or emulator settings.

The reverse-engineering context comes from
[JTCPP / Elemental Games Modding](https://github.com/JTCPP/Elemental_Games_Modding)
and [Elemental Games Modding — Expensions](https://github.com/Azurik-Modding-Hub/Elemental_Games_Modding---Expensions).
This standalone implementation targets the verified PAL executable rather than
assuming the USA addresses from older symbol tables apply.

## Future additions

This repository is the home for further additions to Azurik's native debug menu.
The first test release focuses on freecam. New menu actions and debugging tools
will be added incrementally, with their own compatibility checks and tests.
The desktop patcher is the installer for these game changes.
