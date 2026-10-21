"""User settings and world-state files."""
import json
import os
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
    candidates = []
    try:
        import winreg
        for key in (r"SOFTWARE\WOW6432Node\BioWare\Dragon Age Inquisition", r"SOFTWARE\BioWare\Dragon Age Inquisition"):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                    candidates.append(winreg.QueryValueEx(k, "Install Dir")[0])
            except OSError:
                pass
    except ImportError:
        pass
    candidates += [r"C:\Program Files\EA Games\Dragon Age Inquisition",
                   r"C:\Program Files (x86)\Origin Games\Dragon Age Inquisition",
                   r"C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Inquisition"]
    for c in candidates:
        if is_game_dir(c):
            return str(Path(c))
    return None


def is_game_dir(path):
    return bool(path) and (Path(path) / "Data" / "Win32" / "globals.toc").exists()


def frosty_mods_dir(frosty_dir):
    """Frosty Mod Manager picks up .fbmod files placed in Mods\\DragonAgeInquisition next to its exe."""
    return Path(frosty_dir) / "Mods" / "DragonAgeInquisition"


def save_worldstate(path, name, choices, overrides):
    data = {"format": WORLDSTATE_FORMAT, "version": 1, "name": name,
            "choices": dict(sorted(choices.items())), "overrides": dict(sorted(overrides.items()))}
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_worldstate(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != WORLDSTATE_FORMAT:
        raise ValueError("Not an Offline Keep world state file.")
    to_int = lambda d: {str(k): int(v) for k, v in d.items()}
    return data.get("name", Path(path).stem), to_int(data.get("choices", {})), to_int(data.get("overrides", {}))
