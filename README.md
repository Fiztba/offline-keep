# Offline Keep

An offline replacement for the Dragon Age Keep. Pick your Dragon Age: Origins and Dragon Age II
choices, and Offline Keep turns them into a Frosty Mod Manager mod that replaces Dragon Age: Inquisition's
**default world state**. No servers, no accounts, nothing that can be switched off.

> Unofficial fan tool. Not affiliated with or endorsed by Electronic Arts or BioWare. No game files are
> included: everything is read from your own installation at runtime.

## Requirements

- Dragon Age: Inquisition on PC (tested: EA App install, final patch, build 598987)
- [Frosty Mod Manager](https://github.com/CadeEvs/FrostyToolsuite/releases) 1.0.6.3
- To run from source instead of the .exe: Python 3.10+ (standard library only)

## Use

1. Download `OfflineKeep.exe` from [Releases](https://github.com/Fiztba/offline-keep/releases) and run it
   (or, from source, double-click `Offline Keep.pyw` / run `python -m offlinekeep`).
2. Answer the questions in each section. Dependent flags are filled in for you; warnings point out
   combinations the original games couldn't produce.
3. **File → Save** keeps your world state as a `.dakeep.json` file you can reopen or share.
4. **Generate Mod…** writes a `.fbmod`. Set *Settings → Frosty Mod Manager Folder…* to save it straight
   into Frosty's Mods folder.
5. In Frosty Mod Manager (run as administrator if the game is under Program Files): select the mod,
   **Apply Mod(s)**, then **Launch**.
6. Start a **new game** and choose the **default world state** (not the Keep import).

World states only apply at character creation; they don't change games already in progress.

## How it works

The game defines its world state in the EBX asset `da3/configurations/online/bwworldstateconfigasset`:
every Keep variable (`VariableNameOnServer`), its plot flag, default and range, plus the Keep's own
question text. Offline Keep reads that asset straight from your installation (superbundle → patch delta →
CAS), changes the default values in place, and packages the result as a Frosty `.fbmod`. No game data is
shipped with the tool.

| Module | Role |
| --- | --- |
| `offlinekeep/gamefs.py` | Reads toc/sb superbundles, `cas.cat` catalogs, CAS archives and patch deltas |
| `offlinekeep/compression.py` | Frostbite zlib / LZ4 / stored blocks |
| `offlinekeep/ebx.py` | Self-describing EBX (v2) parser with field offsets |
| `offlinekeep/worldstate.py` | Loads the world state asset, edits values, builds the mod |
| `offlinekeep/fbmod.py` | Frosty `.fbmod` (format 5) writer |
| `offlinekeep/catalog.py` | Sections and questions, from the game's own Keep text |
| `offlinekeep/rules.py` | Derived flags and consistency warnings |
| `offlinekeep/app.py` | Tkinter desktop app |

## Building the .exe

```
pip install pyinstaller
python packaging/build_exe.py
```

The executable is written to `packaging/dist/OfflineKeep.exe`.

## License

MIT, see [LICENSE](LICENSE).

## Credits

anshela's *Custom World States* documentation (Nexus Mods) and the Frosty Toolsuite authors, whose
file formats this tool implements independently.
