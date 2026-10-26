"""Read plot flags (including the imported world state) from Dragon Age: Inquisition saves (.DAS).

Saves are bit-packed, so the plot data can start at any bit offset. It follows the text marker
"BioMetrics_PlotStartMarker" and consists of three lists, each prefixed with a big-endian u16 count:
  1. plot flags that are true   (16-byte GUIDs)
  2. plot flags that are false  (16-byte GUIDs)
  3. integer plot flags         (16-byte GUID + big-endian u32 value)
GUIDs use .NET byte order (uuid.bytes_le).
"""
import os
import struct
import uuid
from pathlib import Path

MARKER = b"BioMetrics_PlotStartMarker"


def _aligned(data):
    """Return the save re-aligned so the plot marker starts on a byte boundary."""
    n = int.from_bytes(data, "big")
    mask = (1 << (8 * len(data))) - 1
    for shift in range(8):
        b = data if shift == 0 else ((n << shift) & mask).to_bytes(len(data), "big")
        pos = b.find(MARKER)
        if pos >= 0:
            return b, pos + len(MARKER)
    raise ValueError("No plot data found; this doesn't look like a Dragon Age: Inquisition save.")


def read_plot_flags(path):
    """GUID string -> int value for every plot flag stored in the save."""
    b, p = _aligned(Path(path).read_bytes())
    flags = {}
    for kind in ("true", "false", "int"):
        count = struct.unpack_from(">H", b, p)[0]
        p += 2
        stride = 20 if kind == "int" else 16
        if p + count * stride > len(b):
            raise ValueError("Plot data in this save is truncated or in an unexpected format.")
        for i in range(count):
            at = p + i * stride
            guid = str(uuid.UUID(bytes_le=b[at:at + 16]))
            if kind == "int":
                flags[guid] = struct.unpack_from(">I", b, at + 16)[0]
            else:
                flags[guid] = 1 if kind == "true" else 0
        p += count * stride
    return flags


def _parse_lists(b, p):
    """The three plot lists starting at byte p: ([true guids], [false guids], [(guid, value)], end offset)."""
    lists = []
    for stride in (16, 16, 20):
        count = struct.unpack_from(">H", b, p)[0]
        p += 2
        if p + count * stride > len(b):
            raise ValueError("Plot data in this save is truncated or in an unexpected format.")
        if stride == 16:
            lists.append([b[p + i * 16:p + i * 16 + 16] for i in range(count)])
        else:
            lists.append([(b[p + i * 20:p + i * 20 + 16], struct.unpack_from(">I", b, p + i * 20 + 16)[0])
                          for i in range(count)])
        p += count * stride
    return lists[0], lists[1], lists[2], p


def _serialize_lists(true_flags, false_flags, int_flags):
    out = bytearray()
    for items in (sorted(true_flags), sorted(false_flags)):
        out += struct.pack(">H", len(items)) + b"".join(items)
    out += struct.pack(">H", len(int_flags))
    for guid, value in sorted(int_flags):
        out += guid + struct.pack(">I", value)
    return bytes(out)


def write_world_state(src, dest, values, worldstate):
    """Write a copy of save `src` to `dest` with world-state variables set to `values` (name -> int).

    Yes/no flags move between the true and false lists, so the plot block keeps its exact size and nothing
    else in the save moves. Returns {name: (old, new)} for the variables that changed.
    """
    original = Path(src).read_bytes()
    n = int.from_bytes(original, "big")
    total_bits = 8 * len(original)
    mask = (1 << total_bits) - 1
    for shift in range(8):
        b = original if shift == 0 else ((n << shift) & mask).to_bytes(len(original), "big")
        pos = b.find(MARKER)
        if pos >= 0:
            break
    else:
        raise ValueError("No plot data found; this doesn't look like a Dragon Age: Inquisition save.")
    start = pos + len(MARKER)
    true_flags, false_flags, int_flags, end = _parse_lists(b, start)
    true_set, false_set = set(true_flags), set(false_flags)
    ints = dict(int_flags)

    changed = {}
    for name, value in values.items():
        g = uuid.UUID(worldstate.vars[name]["PlotFlag"]["PlotFlagId"]["Guid"]).bytes_le
        if g in ints:
            if ints[g] != value:
                changed[name] = (ints[g], value)
                ints[g] = value
        elif g in true_set or g in false_set:
            old = 1 if g in true_set else 0
            new = 1 if value else 0
            if old != new:
                changed[name] = (old, new)
                (true_set if new else false_set).add(g)
                (false_set if new else true_set).discard(g)
        # flags the save doesn't contain are left alone: adding entries would change the save's size

    block = _serialize_lists(true_set, false_set, list(ints.items()))
    if len(block) != end - start:
        raise AssertionError("plot block size changed")
    # put the new block back at the original bit position: shifted byte i holds original bits 8i+shift..
    q0, q1 = 8 * start + shift, 8 * end + shift
    width = q1 - q0
    field_shift = total_bits - q1
    n = (n & ~(((1 << width) - 1) << field_shift)) | (int.from_bytes(block, "big") << field_shift)
    out = n.to_bytes(len(original), "big")
    if len(out) != len(original):
        raise AssertionError("save size changed")
    Path(dest).write_bytes(out)
    return changed


def read_world_state(path, worldstate):
    """Variable name -> value for the world-state variables found in the save (missing ones omitted)."""
    flags = read_plot_flags(path)
    out = {}
    for name, var in worldstate.vars.items():
        guid = var["PlotFlag"]["PlotFlagId"]["Guid"].lower()
        if guid in flags:
            out[name] = flags[guid]
    return out


def default_save_dir():
    """Inquisition writes saves under Documents (which OneDrive may redirect)."""
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)  # CSIDL_PERSONAL
        docs = Path(buf.value)
    except (ImportError, AttributeError, OSError):
        docs = Path(os.path.expanduser("~")) / "Documents"
    return docs / "BioWare" / "Dragon Age Inquisition" / "Save"


def list_saves(save_dir=None):
    """(path, modified time) for every save, newest first."""
    d = Path(save_dir) if save_dir else default_save_dir()
    files = [p for p in d.glob("*.DAS") if p.is_file()] if d.is_dir() else []
    return sorted(((p, p.stat().st_mtime) for p in files), key=lambda x: x[1], reverse=True)
