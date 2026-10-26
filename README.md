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

## Verifying the world state

**Tools → Verify World State…** (or the *Verify…* button) checks two things:

- **Installed mod (Frosty):** reads the game files Frosty Mod Manager installed (`<game>\ModData\<pack>`) and
  tells you which world state is active: your current one, one of your saved `.dakeep.json` files, or the
  game's own default (no world state mod). Frosty rebuilds these files when you click *Launch*.
- **Saved game:** reads the world state stored in a save (`.DAS`). The game copies the world state into your
  save at character creation, so this is what that playthrough uses. Any answers that differ from your current
  world state are listed.

### Changing the world state of an existing save

On the *Saved game* tab, **Apply my world state to this save…** rewrites the Origins/DA II world state stored in
that save, so you don't need a new game. Close the game first. Offline Keep backs the save up to an
`OfflineKeep backups` folder next to your saves, writes a temporary copy, reads it back to confirm every value,
and only then replaces the save. Only the world-state flags change; nothing from your Inquisition playthrough is
touched. Anything the game checks from then on (dialogue, companions, endings) uses the new values, but scenes
you've already played won't change.

## Automatic updates

*Settings → Check for Updates at Startup* (off by default, `.exe` only). When enabled, each launch asks
GitHub for the latest release; if it's newer, Offline Keep downloads `OfflineKeep.exe`, checks its size and
SHA-256 against GitHub's published digest, swaps it in place of the running executable and starts the new
version. If anything fails (offline, folder not writable…) the current version simply starts, and the reason
is written to `%APPDATA%\OfflineKeep\update.log`. This is the only time Offline Keep goes online.

For maintainers: the updater follows GitHub's *latest* release, so a release's `OfflineKeep.exe` must report the
same version as its tag (`offlinekeep/__init__.py`). To pull a bad release, delete it or mark it as a
pre-release; `latest` skips pre-releases.

## Troubleshooting

- **Frosty Mod Manager: "Could not load file or assembly 'Newtonsoft.Json…'"** on startup. Frosty looks for its
  `ThirdParty` folder relative to the *current working folder*, so it crashes when started from a Start-menu
  search, a pinned taskbar icon or a shortcut without a "Start in" folder. Start it from File Explorer (right-click
  `FrostyModManager.exe` → Run as administrator), or set the shortcut's **Start in** to Frosty's own folder.
- **"Access to the path …\ModData\… is denied"** when launching: the game is under Program Files, so run Frosty Mod
  Manager as administrator.
- **Game not found:** Offline Keep checks the EA App/Origin registry entry, all Steam library folders and the Epic
  Games Launcher; otherwise it asks for the folder that contains `DragonAgeInquisition.exe`.
- **A save editor doesn't show a value you set:** Offline Keep sets the same world-state variables the Keep did;
  some save editors only know a fixed list of flag names and values.

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
| `offlinekeep/savegame.py` | Reads plot flags (the imported world state) from `.DAS` saves |
| `offlinekeep/verify.py`, `verifywindow.py` | Verify World State: installed mod and save checks |
| `offlinekeep/updater.py` | Optional self-update from GitHub releases |
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
