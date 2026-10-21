"""Write Frosty Mod Manager .fbmod files (format version 5) containing modified EBX assets.

Layout follows FrostyModWriter.WriteProject / FrostyModReader in Frosty Toolsuite 1.0.6.3.
"""
import hashlib
import struct

from .compression import compress_frostbite

MAGIC = 0x01005954534F5246  # "FROSTY\0\1"
VERSION = 5
PROFILE = "DragonAgeInquisition"
TYPE_EMBEDDED, TYPE_EBX = 0, 1


def _cstr(s):
    return s.encode("utf-8") + b"\0"


def _sized(s):
    b = s.encode("utf-8")
    assert len(b) < 128  # single-byte 7-bit length prefix
    return bytes([len(b)]) + b


def build_fbmod(ebx_assets, game_head, title, author="", category="", version="1.0", description="", link=""):
    """ebx_assets: list of (asset name, uncompressed ebx bytes). Returns the .fbmod file bytes."""
    payloads = []
    resources = bytearray()
    resources += struct.pack("<i", 5 + len(ebx_assets))
    for name in ["Icon"] + [f"Screenshot{i}" for i in range(4)]:  # empty icon and screenshots
        resources += bytes([TYPE_EMBEDDED]) + struct.pack("<i", -1) + _cstr(name) + struct.pack("<i", 0)
    for name, data in ebx_assets:
        comp = compress_frostbite(data)
        resources += bytes([TYPE_EBX]) + struct.pack("<i", len(payloads)) + _cstr(name.lower())
        resources += hashlib.sha1(comp).digest() + struct.pack("<qBi", len(data), 0, 0) + _cstr("")
        resources += struct.pack("<i", 0)  # no bundles to add to
        payloads.append(comp)

    head = bytearray()
    head += struct.pack("<QI", MAGIC, VERSION)
    head += struct.pack("<qi", 0, 0)  # manifest offset/count, patched below
    head += _sized(PROFILE) + struct.pack("<I", game_head)
    for s in (title, author, category, version, description, link):
        head += _cstr(s)

    body = head + resources
    manifest_offset = len(body)
    table = bytearray()
    offset = 0
    for p in payloads:
        table += struct.pack("<qq", offset, len(p))
        offset += len(p)
    out = body + table + b"".join(payloads)
    struct.pack_into("<qi", out, 12, manifest_offset, len(payloads))
    return bytes(out)
