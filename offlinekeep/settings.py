"""User settings and world-state files."""
import json
import os
import re
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "OfflineKeep"
SETTINGS_FILE = APP_DIR / "settings.json"
WORLDSTATE_FORMAT = "offlinekeep-worldstate"


def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def detect_game_dir():
    """Find Dragon Age: Inquisition via the registry (EA App/Origin) or common Steam locations."""
    candidates = _registry_candidates() + _steam_candidates() + _epic_candidates()
    candidates += [r"C:\Program Files\EA Games\Dragon Age Inquisition",
                   r"C:\Program Files (x86)\Origin Games\Dragon Age Inquisition",
                   r"C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Inquisition",
                   r"C:\Program Files\Epic Games\DragonAgeInquisition"]
    for c in candidates:
        if is_game_dir(c):
            return str(Path(c))
    return None


STEAM_APP_ID = "1222690"


def _reg_value(root, key, name):
    try:
        import winreg
        with winreg.OpenKey(root, key) as k:
            return winreg.QueryValueEx(k, name)[0]
    except (ImportError, OSError):
        return None


def _registry_candidates():
    """EA App / Origin write BioWare's key; Steam writes an uninstall entry for its app id."""
    try:
        import winreg
    except ImportError:
        return []
    keys = [(r"SOFTWARE\WOW6432Node\BioWare\Dragon Age Inquisition", "Install Dir"),
            (r"SOFTWARE\BioWare\Dragon Age Inquisition", "Install Dir"),
            (rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {STEAM_APP_ID}", "InstallLocation"),
            (rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {STEAM_APP_ID}",
             "InstallLocation")]
    return [v for v in (_reg_value(winreg.HKEY_LOCAL_MACHINE, k, n) for k, n in keys) if v]


def _steam_candidates():
    """Every Steam library folder listed in libraryfolders.vdf (covers libraries on other drives)."""
    try:
        import winreg
    except ImportError:
        return []
    steam = _reg_value(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath")
    if not steam:
        return []
    libraries = [steam]
    try:
        vdf = (Path(steam) / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
        libraries += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', vdf)]
    except OSError:
        pass
    return [str(Path(lib) / "steamapps" / "common" / "Dragon Age Inquisition") for lib in libraries]


def _epic_candidates():
    """Epic Games Launcher manifests record each installed game's folder."""
    manifests = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    out = []
    for item in manifests.glob("*.item") if manifests.is_dir() else []:
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "inquisition" in str(data.get("DisplayName", "")).lower():
            out.append(data.get("InstallLocation", ""))
    return out


def is_game_dir(path):
    return bool(path) and (Path(path) / "Data" / "Win32" / "globals.toc").exists()


def frosty_mods_dir(frosty_dir):
    """Frosty Mod Manager picks up .fbmod files placed in Mods\\DragonAgeInquisition next to its exe."""
    return Path(frosty_dir) / "Mods" / "DragonAgeInquisition"


def save_worldstate(path, name, choices, overrides):
    from . import __version__
    data = {"format": WORLDSTATE_FORMAT, "version": 1, "app_version": __version__, "name": name,
            "choices": dict(sorted(choices.items())), "overrides": dict(sorted(overrides.items()))}
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _migrate_choices(choices, app_version):
    """Adapt answers saved by older versions whose value meanings have since changed."""
    if app_version is None:  # saved by 1.1.1 or earlier
        # da2_isabela_turned_over followed the Keep text (1 = No, 2 = Yes); the game reads it as yes/no.
        if "da2_isabela_turned_over" in choices:
            choices["da2_isabela_turned_over"] = {1: 0, 2: 1}.get(choices["da2_isabela_turned_over"], 0)
    return choices


def load_worldstate(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != WORLDSTATE_FORMAT:
        raise ValueError("Not an Offline Keep world state file.")
    to_int = lambda d: {str(k): int(v) for k, v in d.items()}
    choices = _migrate_choices(to_int(data.get("choices", {})), data.get("app_version"))
    return data.get("name", Path(path).stem), choices, to_int(data.get("overrides", {}))
