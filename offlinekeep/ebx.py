"""Parse a Frostbite EBX v2 (magic 0x0FB2D1CE, Dragon Age: Inquisition era) file into JSON.

The format is self-describing: it carries its own class/field descriptors, so no external
type database is needed. Fields are read by their declared offsets.
"""
import json
import struct
import sys
import uuid
from pathlib import Path

T_INHERITED, T_STRUCT, T_POINTER, T_ARRAY = 0x00, 0x02, 0x03, 0x04
T_CSTRING, T_ENUM, T_FILEREF, T_BOOL = 0x07, 0x08, 0x09, 0x0A
PRIMS = {0x0B: "b", 0x0C: "B", 0x0D: "h", 0x0E: "H", 0x0F: "i", 0x10: "I",
         0x11: "Q", 0x12: "q", 0x13: "f", 0x14: "d"}


def djb2_xor(s):
    h = 5381
    for c in s.encode():
        h = ((h * 33) ^ c) & 0xFFFFFFFF
    return h


class Ebx:
    def __init__(self, data):
        self.d = data
        (magic, self.strings_off, _, guid_count, inst_count, exported, _, class_count,
         field_count, names_len, strings_len, array_count, data_len) = struct.unpack_from("<4I6H3I", data, 0)
        assert magic == 0x0FB2D1CE, hex(magic)
        self.file_guid = str(uuid.UUID(bytes_le=data[36:52]))
        p = 52
        p += (-p) % 16
        self.imports = []
        for _ in range(guid_count):
            self.imports.append((str(uuid.UUID(bytes_le=data[p:p + 16])), str(uuid.UUID(bytes_le=data[p + 16:p + 32]))))
            p += 32
        names = {}
        for n in data[p:p + names_len].split(b"\0"):
            if n:
                names[djb2_xor(n.decode())] = n.decode()
        p += names_len
        self.fields = []
        for _ in range(field_count):
            h, t, ref, off, off2 = struct.unpack_from("<IHHII", data, p)
            p += 16
            self.fields.append({"name": names.get(h, f"#{h:08x}"), "type": (t >> 4) & 0x1F, "ref": ref, "off": off})
        self.classes = []
        for _ in range(class_count):
            h, fidx, fcount, align, t, size, size2 = struct.unpack_from("<IiBBHHH", data, p)
            p += 16
            self.classes.append({"name": names.get(h, f"#{h:08x}"), "fidx": fidx, "fcount": fcount,
                                 "align": align, "type": (t >> 4) & 0x1F, "size": size})
        self.instances = []
        for i in range(inst_count):
            cref, count = struct.unpack_from("<HH", data, p)
            p += 4
            self.instances.append((cref, count, i < exported))
        p += (-p) % 16
        self.arrays = []
        for _ in range(array_count):
            self.arrays.append(struct.unpack_from("<IIi", data, p))
            p += 12
        self.arrays_off = self.strings_off + strings_len + data_len
        self.data_off = self.strings_off + strings_len

    def cstr(self, off):
        if off == 0xFFFFFFFF:
            return None
        s = self.strings_off + off
        return self.d[s:self.d.index(b"\0", s)].decode("utf-8", "replace")

    def read_value(self, ftype, ref, pos):
        if ftype in PRIMS:
            return struct.unpack_from("<" + PRIMS[ftype], self.d, pos)[0]
        if ftype == T_BOOL:
            return self.d[pos] != 0
        if ftype in (T_CSTRING, T_FILEREF):
            return self.cstr(struct.unpack_from("<I", self.d, pos)[0])
        if ftype == T_ENUM:
            return struct.unpack_from("<i", self.d, pos)[0]
        if ftype == T_POINTER:
            idx = struct.unpack_from("<I", self.d, pos)[0]
            if idx == 0:
                return None
            if idx >> 31:
                return {"import": self.imports[idx & 0x7FFFFFFF]}
            return {"ref": idx - 1}
        if ftype == T_STRUCT:
            return self.read_class(self.classes[ref], pos)
        if ftype == 0x15:
            return str(uuid.UUID(bytes_le=self.d[pos:pos + 16]))
        return f"<unhandled type {ftype:#x}>"

    def read_class(self, cls, base, out=None):
        out = {} if out is None else out
        for f in self.fields[cls["fidx"]:cls["fidx"] + cls["fcount"]]:
            if f["type"] == T_INHERITED:
                self.read_class(self.classes[f["ref"]], base, out)
            elif f["type"] == T_ARRAY:
                out[f["name"]] = self.read_array(self.classes[f["ref"]], base + f["off"])
            else:
                out[f["name"]] = self.read_value(f["type"], f["ref"], base + f["off"])
        return out

    def read_array(self, arr_cls, pos):
        off, count, _ = self.arrays[struct.unpack_from("<i", self.d, pos)[0]]
        member = self.fields[arr_cls["fidx"]]
        if member["type"] == T_STRUCT:
            stride = self.classes[member["ref"]]["size"]
        elif member["type"] in PRIMS:
            stride = struct.calcsize(PRIMS[member["type"]])
        elif member["type"] == T_BOOL:
            stride = 1
        elif member["type"] == 0x15:
            stride = 16
        else:
            stride = 4
        start = self.arrays_off + off
        return [self.read_value(member["type"], member["ref"], start + i * stride) for i in range(count)]

    def field_pos(self, obj_index, name):
        """Byte position and type of a top-level field of an object (searches inherited classes)."""
        cref, base = self.bases[obj_index]
        stack = [self.classes[cref]]
        while stack:
            cls = stack.pop()
            for f in self.fields[cls["fidx"]:cls["fidx"] + cls["fcount"]]:
                if f["type"] == T_INHERITED:
                    stack.append(self.classes[f["ref"]])
                elif f["name"] == name:
                    return base + f["off"], f["type"]
        raise KeyError(name)

    def read_all(self):
        self.bases = []
        objs = []
        p = self.data_off
        for cref, count, exported in self.instances:
            cls = self.classes[cref]
            for _ in range(count):
                p += (-p) % cls["align"]
                guid = None
                if exported:
                    guid = str(uuid.UUID(bytes_le=self.d[p:p + 16]))
                    p += 16
                base = p if cls["align"] != 4 else p - 8
                obj = {"$index": len(objs), "$type": cls["name"], "$guid": guid}
                self.read_class(cls, base, obj)
                self.bases.append((cref, base))
                objs.append(obj)
                p = base + cls["size"]
        return objs


if __name__ == "__main__":
    ebx = Ebx(Path(sys.argv[1]).read_bytes())
    result = {"fileGuid": ebx.file_guid, "imports": ebx.imports, "objects": ebx.read_all()}
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    text = json.dumps(result, indent=1)
    if out:
        out.write_text(text)
        print(f"wrote {out} ({len(result['objects'])} objects)")
    else:
        print(text)
