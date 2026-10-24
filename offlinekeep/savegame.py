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
