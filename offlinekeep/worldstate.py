"""Read the game's default world state and produce a modified copy as a Frosty mod."""
import struct

from .ebx import Ebx
from .fbmod import build_fbmod
from .gamefs import DbReader, Game, read_container

ASSET = "da3/configurations/online/bwworldstateconfigasset"
SUPERBUNDLE = "Win32/globals"


class WorldState:
    def __init__(self, ebx_bytes):
        self.data = bytearray(ebx_bytes)
        self.ebx = Ebx(bytes(ebx_bytes))
        self.objects = self.ebx.read_all()
        self.sets = {}
        self.vars = {}  # VariableNameOnServer -> object
        for s in self.objects:
            if s["$type"] != "WorldStateSet":
                continue
            variables = [self.objects[r["ref"]] for r in s["Variables"]]
            descriptions = [self.objects[r["ref"]] for r in s["Descriptions"]]
            self.sets[s["SetName"]] = {"variables": variables, "descriptions": descriptions}
            for v in variables:
                self.vars[v["VariableNameOnServer"]] = v

    @classmethod
    def from_game(cls, game_dir):
        game = Game(game_dir)
        hit = game.find_ebx(SUPERBUNDLE, ASSET)
        if hit is None:
            raise FileNotFoundError(f"{ASSET} not found in {game_dir}")
        data = game.read_entry(hit["entry"])
        expected = hit["entry"].get("originalsize")
        if expected is not None and len(data) != expected:
            raise ValueError(f"world state asset decoded to {len(data)} bytes, expected {expected}")
        return cls(data)

    def get(self, name):
        return self.vars[name]["DefaultValue"]

    def set(self, name, value):
        """Set a variable's default; raises MaxValue if the game's limit is lower than the value."""
        var = self.vars[name]
        if value < var["MinValue"]:
            raise ValueError(f"{name}={value} is below MinValue {var['MinValue']}")
        self._write_int(var, "DefaultValue", value)
        if value > var["MaxValue"]:
            self._write_int(var, "MaxValue", value)

    def _write_int(self, var, field, value):
        pos, ftype = self.ebx.field_pos(var["$index"], field)
        fmt = {0x0F: "<i", 0x10: "<I"}[ftype]
        struct.pack_into(fmt, self.data, pos, value)
        var[field] = value

    def to_bytes(self):
        return bytes(self.data)


def game_head(game_dir):
    """The game build number Frosty stamps into mods (layout.toc 'head', patch first)."""
    from pathlib import Path
    for rel in ("Update/Patch/Data/layout.toc", "Data/layout.toc"):
        p = Path(game_dir) / rel
        if p.exists():
            return DbReader(read_container(p)).read()[1]["head"]
    raise FileNotFoundError("layout.toc")


def make_fbmod(base_ebx, values, head, title, description="", author="Offline Keep"):
    """Apply `values` (only those that differ) to a pristine copy of the asset and package it."""
    ws = WorldState(base_ebx)
    for name, value in values.items():
        if ws.get(name) != value:
            ws.set(name, value)
    return build_fbmod([(ASSET, ws.to_bytes())], head, title, author=author,
                       category="World States", description=description)


def build_mod(game_dir, values, title, description="", author="Offline Keep"):
    base = WorldState.from_game(game_dir).to_bytes()
    return make_fbmod(base, values, game_head(game_dir), title, description, author)
