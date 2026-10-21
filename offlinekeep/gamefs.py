"""Minimal read-only access to Dragon Age: Inquisition's Frostbite data (toc/sb/cas.cat/cas).

Usage: python gamefs.py <game dir> <superbundle, e.g. win32/globals> <ebx name> [out file]
"""
import struct
import sys
from pathlib import Path

from .compression import decompress_frostbite, read_block

HEADER = 0x22C


def apply_delta(base, delta):
    """Rebuild a patched resource from compressed base + delta streams (port of Frosty's CasReader.ReadPatched)."""
    out = bytearray()
    bp = dp = 0
    while dp < len(delta):
        tmp = struct.unpack_from(">I", delta, dp)[0]
        dp += 4
        kind, count = tmp >> 28, tmp & 0x0FFFFFFF
        if kind == 0:  # copy base blocks
            for _ in range(count):
                block, bp = read_block(base, bp)
                out += block
        elif kind == 1:  # base block with delta blocks spliced in
            block, bp = read_block(base, bp)
            cur = 0
            for _ in range(count):
                offset, skip = struct.unpack_from(">HH", delta, dp)
                dp += 4
                out += block[cur:offset]
                cur = offset
                piece, dp = read_block(delta, dp)
                out += piece
                cur += skip
            out += block[cur:]
        elif kind == 2:  # base block with small byte-level edits
            block, bp = read_block(base, bp)
            new_size = struct.unpack_from(">H", delta, dp)[0] + 1
            dp += 2
            start, cur, buf = dp, 0, bytearray()
            while dp - start < count:
                offset, skip, add = struct.unpack_from(">HBB", delta, dp)
                dp += 4
                buf += block[cur:offset]
                cur = offset + skip
                buf += delta[dp:dp + add]
                dp += add
            buf += block[cur:cur + new_size - len(buf)]
            out += buf
        elif kind == 3:  # new blocks from delta
            for _ in range(count):
                block, dp = read_block(delta, dp)
                out += block
        elif kind == 4:  # skip base blocks
            for _ in range(count):
                _, bp = read_block(base, bp)
        else:
            raise ValueError(f"unknown delta op {kind}")
    while bp < len(base):  # remaining base blocks
        block, bp = read_block(base, bp)
        out += block
    return bytes(out)


def read_container(path):
    """Strip the 0x22C-byte header from a toc/sb/cat file, undoing the XOR layer if present."""
    data = Path(path).read_bytes()
    magic = struct.unpack_from("<I", data, 0)[0]
    if magic not in (0x01CED100, 0x03CED100):
        return data
    body = bytearray(data[HEADER:])
    if magic == 0x01CED100:
        key = bytes(b ^ 123 for b in data[0x128:0x128 + 260])
        for i in range(len(body)):
            body[i] ^= key[i % 257]
    return bytes(body)


class DbReader:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos

    def varint(self):
        result = shift = 0
        while True:
            b = self.d[self.p]
            self.p += 1
            result |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                return result

    def cstr(self):
        end = self.d.index(b"\0", self.p)
        s = self.d[self.p:end].decode("utf-8", "replace")
        self.p = end + 1
        return s

    def read(self):
        """Returns (name, value) or None at a terminator."""
        tag = self.d[self.p]
        self.p += 1
        t = tag & 0x1F
        if t == 0:
            return None
        name = "" if tag & 0x80 else self.cstr()
        if t in (1, 2):
            size = self.varint()
            end = self.p + size
            items = []
            while self.p < end:
                item = self.read()
                if item is None:
                    break
                items.append(item)
            self.p = end
            return name, ([v for _, v in items] if t == 1 else {k.lower(): v for k, v in items})
        if t == 6:
            v = self.d[self.p] == 1
            self.p += 1
        elif t == 7:
            n = self.varint()
            v = self.d[self.p:self.p + n].rstrip(b"\0").decode("utf-8", "replace")
            self.p += n
        elif t == 8:
            v = struct.unpack_from("<i", self.d, self.p)[0]
            self.p += 4
        elif t == 9:
            v = struct.unpack_from("<q", self.d, self.p)[0]
            self.p += 8
        elif t == 11:
            v = struct.unpack_from("<f", self.d, self.p)[0]
            self.p += 4
        elif t == 12:
            v = struct.unpack_from("<d", self.d, self.p)[0]
            self.p += 8
        elif t == 15:
            v = self.d[self.p:self.p + 16]
            self.p += 16
        elif t == 16:
            v = self.d[self.p:self.p + 20]
            self.p += 20
        elif t == 19:
            n = self.varint()
            v = self.d[self.p:self.p + n]
            self.p += n
        else:
            raise ValueError(f"unknown DbObject type {t} at {self.p - 1}")
        return name, v


class DataDir:
    """One Frostbite data root (base game Data/ or Update/<name>/Data/)."""

    def __init__(self, root):
        self.root = Path(root)
        self.catalog = {}
        cat = self.root / "cas.cat"
        if cat.exists():
            data = read_container(cat)
            assert data[:16] == b"NyanNyanNyanNyan"
            for p in range(16, len(data) - 31, 0x20):
                sha1 = data[p:p + 20]
                offset, size, archive = struct.unpack_from("<IIi", data, p + 20)
                self.catalog.setdefault(sha1, (archive & 0xFF, offset, size))

    def read_cas(self, sha1):
        archive, offset, size = self.catalog[sha1]
        with open(self.root / f"cas_{archive:02d}.cas", "rb") as f:
            f.seek(offset)
            return f.read(size)


class Game:
    def __init__(self, game_dir):
        self.game_dir = Path(game_dir)
        self.base = DataDir(self.game_dir / "Data")
        self.patch = DataDir(self.game_dir / "Update" / "Patch" / "Data")

    def raw_cas(self, sha1):
        for d in (self.patch, self.base):
            if sha1 in d.catalog:
                return d.read_cas(sha1)
        raise KeyError(sha1.hex())

    def resolve_cas(self, sha1):
        return decompress_frostbite(self.raw_cas(sha1))

    def read_entry(self, entry):
        """Decompressed data for a bundle ebx/res entry, applying patch deltas when present."""
        if entry.get("caspatchtype") == 2:
            return apply_delta(self.raw_cas(entry["basesha1"]), self.raw_cas(entry["deltasha1"]))
        return self.resolve_cas(entry["sha1"])

    def superbundle(self, name, prefer_patch=True):
        roots = ([self.patch.root] if prefer_patch else []) + [self.base.root]
        for root in roots:
            toc = root / (name + ".toc")
            if toc.exists():
                return root, DbReader(read_container(toc)).read()[1]
        raise FileNotFoundError(name)

    def find_ebx(self, sb_name, ebx_name):
        root, toc = self.superbundle(sb_name)
        sb = read_container(root / (sb_name + ".sb"))
        ebx_name = ebx_name.lower()
        for b in toc.get("bundles", []):
            if b.get("base"):  # unchanged in this patch; lives in the base game's superbundle
                continue
            bundle = DbReader(sb, b["offset"]).read()[1]
            for e in bundle.get("ebx", []):
                if e.get("name", "").lower() == ebx_name:
                    return {"bundle": b["id"], "root": str(root), "toc_entry": {k: v for k, v in b.items() if k != "id"},
                            "entry": e}
        return None


if __name__ == "__main__":
    game = Game(sys.argv[1])
    hit = game.find_ebx(sys.argv[2], sys.argv[3])
    if not hit:
        sys.exit("not found")
    e = hit["entry"]
    print("bundle:", hit["bundle"], "in", hit["root"])
    print("toc entry:", hit["toc_entry"])
    print("ebx entry:", {k: (v.hex() if isinstance(v, bytes) else v) for k, v in e.items()})
    data = game.read_entry(e)
    if "originalsize" in e and len(data) != e["originalsize"]:
        sys.exit(f"size mismatch: got {len(data)}, expected {e['originalsize']}")
    print("decompressed", len(data), "bytes")
    if len(sys.argv) > 4:
        Path(sys.argv[4]).write_bytes(data)
        print("wrote", sys.argv[4])
