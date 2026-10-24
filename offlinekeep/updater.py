"""Optional self-update for the packaged .exe from the project's GitHub releases.

Runs before the main window: checks the latest release, downloads OfflineKeep.exe, verifies it against
GitHub's published size and SHA-256 digest, swaps it in place of the running executable (Windows allows
renaming a running .exe) and starts it. Any failure is logged and the current version simply continues.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import __version__, settings

REPO = "Fiztba/offline-keep"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_NAME = "OfflineKeep.exe"
UPDATED_FROM_ENV = "OFFLINEKEEP_UPDATED_FROM"
LOG_FILE = settings.APP_DIR / "update.log"


def log(message):
    try:
        settings.APP_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {message}\n")
    except OSError:
        pass


def version_tuple(v):
    parts = []
    for p in str(v).lstrip("vV").split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_packaged():
    return bool(getattr(sys, "frozen", False))


def _old_path(exe):
    return exe.with_name(f"{exe.stem}.old{exe.suffix}")


def cleanup(exe=None):
    """Remove the previous executable left behind by an update."""
    exe = Path(exe or sys.executable)
    old = _old_path(exe)
    for _ in range(10):  # the old process may take a moment to exit
        try:
            if old.exists():
                old.unlink()
            return
        except OSError:
            time.sleep(0.3)


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": f"OfflineKeep/{__version__}",
                                               "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def latest_release(timeout=5):
    """(version string, asset dict) for the latest GitHub release, or None if it has no .exe."""
    with _get(LATEST_URL, timeout) as r:
        data = json.load(r)
    asset = next((a for a in data.get("assets", []) if a.get("name") == ASSET_NAME), None)
    return (data.get("tag_name", ""), asset) if asset else None


def _download(asset, dest, progress=None):
    expected_size = asset.get("size")
    digest = asset.get("digest") or ""
    h = hashlib.sha256()
    done = 0
    with _get(asset["browser_download_url"], 30) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if progress and expected_size:
                progress(done / expected_size)
    if expected_size and done != expected_size:
        raise IOError(f"download incomplete ({done} of {expected_size} bytes)")
    if digest.startswith("sha256:") and h.hexdigest() != digest.split(":", 1)[1].lower():
        raise IOError("downloaded file failed its SHA-256 check")
    with open(dest, "rb") as f:
        if f.read(2) != b"MZ":
            raise IOError("downloaded file is not a Windows executable")


def _clean_env():
    """Environment for starting another PyInstaller app from this one without sharing its unpack folder."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("_PYI", "_MEIPASS"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    env[UPDATED_FROM_ENV] = __version__
    return env


def run_if_enabled(show_progress=None):
    """Called at startup. Returns True if a newer version was started and this process should exit."""
    if not is_packaged():
        return False
    exe = Path(sys.executable)
    cleanup(exe)
    if os.environ.get(UPDATED_FROM_ENV) or not settings.load_settings().get("auto_update", False):
        return False
    try:
        found = latest_release()
    except Exception as ex:  # offline, rate limited, GitHub down...
        log(f"update check skipped: {ex}")
        return False
    if not found or version_tuple(found[0]) <= version_tuple(__version__):
        return False
    tag, asset = found
    log(f"updating {__version__} -> {tag}")
    tmp = exe.with_name(f"{exe.stem}.download")
    old = _old_path(exe)
    try:
        _download(asset, tmp, show_progress(tag) if show_progress else None)
        if old.exists():
            old.unlink()
        exe.rename(old)
        try:
            tmp.rename(exe)
        except OSError:
            old.rename(exe)  # put the current version back
            raise
        subprocess.Popen([str(exe)], env=_clean_env(), close_fds=True)
        log(f"started {tag}")
        return True
    except Exception as ex:
        log(f"update to {tag} failed, continuing with {__version__}: {ex}")
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        return False


def updated_from():
    """Version this process was updated from, if it was just started by the updater."""
    return os.environ.get(UPDATED_FROM_ENV)
