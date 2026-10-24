"""Check which world state is actually installed (Frosty's ModData) or imported (a save game)."""
from pathlib import Path

from . import rules, savegame, settings
from .gamefs import Game
from .worldstate import ASSET, SUPERBUNDLE, WorldState


def world_vars(values):
    return {n: v for n, v in values.items() if n.startswith(("dao_", "da2_"))}


def state_values(defaults, choices, overrides):
    """Full variable values for a world state, the same way the app computes them."""
    v = dict(defaults)
    v.update(choices)
    v.update(overrides)
    rules.derive(v)
    v.update(overrides)
    return v


def installed_packs(game_dir):
    """World state applied by Frosty Mod Manager, per mod pack.

    Returns a list of dicts: {pack, path, modified, values (or None), error (or None)}.
    Frosty writes the patched game files to <game>\\ModData\\<pack> when you click Launch.
    """
    root = Path(game_dir) / "ModData"
    packs = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []:
        entry = {"pack": d.name, "path": str(d), "modified": _installed_time(d), "values": None, "error": None}
        try:
            game = Game(d)
            hit = game.find_ebx(SUPERBUNDLE, ASSET)
            if hit is None:
                raise FileNotFoundError("world state asset not found")
            entry["values"] = world_vars({n: v["DefaultValue"] for n, v in WorldState(game.read_entry(hit["entry"])).vars.items()})
        except Exception as ex:  # reported in the UI per pack
            entry["error"] = str(ex)
        packs.append(entry)
    return packs


def _installed_time(pack_dir):
    """When Frosty last wrote this pack: newest file in its patch data (the folder's own time doesn't change)."""
    patch = Path(pack_dir) / "Update" / "Patch" / "Data"
    times = [p.stat().st_mtime for p in patch.glob("*") if p.is_file()] if patch.is_dir() else []
    return max(times, default=Path(pack_dir).stat().st_mtime)


def saved_game(path, worldstate):
    return world_vars(savegame.read_world_state(path, worldstate))


def differences(actual, expected, sections):
    """Questions whose answers differ, plus a count of other (derived/advanced) variables that differ.

    Returns ([(section title, question, expected value, actual value)], other_count).
    """
    asked, rows = set(), []
    for sec in sections:
        for q in sec.questions:
            asked.add(q.var)
            if q.var in actual and q.var in expected and actual[q.var] != expected[q.var]:
                rows.append((sec, q, expected[q.var], actual[q.var]))
    other = sum(1 for n in actual if n not in asked and n in expected and actual[n] != expected[n])
    return rows, other


def identify(actual, candidates):
    """Name of the first candidate (name -> values) that matches `actual` exactly on every shared variable."""
    for name, values in candidates.items():
        shared = [n for n in actual if n in values]
        if shared and all(actual[n] == values[n] for n in shared):
            return name
    return None


def saved_worldstates(folder, defaults):
    """name -> values for every .dakeep.json in `folder` (unreadable files skipped)."""
    out = {}
    for p in sorted(Path(folder).glob("*.dakeep.json")) if folder and Path(folder).is_dir() else []:
        try:
            name, choices, overrides = settings.load_worldstate(p)
        except (OSError, ValueError):
            continue
        out[f"{name} ({p.name})"] = world_vars(state_values(defaults, choices, overrides))
    return out
