"""Frostbite block (de)compression: zlib, LZ4 and stored blocks."""
import struct
import zlib


def lz4_block_decompress(src, size):
    """Decode a raw LZ4 block (no frame header) into `size` bytes."""
    out = bytearray()
    p = 0
    while p < len(src):
        token = src[p]
        p += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = src[p]
                p += 1
                lit += b
                if b != 255:
                    break
        out += src[p:p + lit]
        p += lit
        if p >= len(src) or len(out) >= size:
            break
        dist = src[p] | (src[p + 1] << 8)
        p += 2
        mlen = token & 0x0F
        if mlen == 15:
            while True:
                b = src[p]
                p += 1
                mlen += b
                if b != 255:
                    break
        mlen += 4
        start = len(out) - dist
        for i in range(mlen):  # byte-wise: matches may overlap their own output
            out.append(out[start + i])
    return bytes(out)


def read_block(data, p):
    """One Frostbite compressed block: BE u32 decompressed size, type byte, flags byte, BE u16 size.

    Returns (decompressed bytes, position after the block).
    """
    dsize = struct.unpack_from(">I", data, p)[0] & 0x00FFFFFF
    ctype, flags = data[p + 4] & 0x7F, data[p + 5]
    csize = struct.unpack_from(">H", data, p + 6)[0] + ((flags & 0x0F) << 16)
    block = data[p + 8:p + 8 + csize]
    p += 8 + csize
    if ctype == 0x02:
        return zlib.decompress(block), p
    if ctype == 0x00:
        return block, p
    if ctype == 0x09:
        return lz4_block_decompress(block, dsize), p
    raise ValueError(f"unsupported compression type {ctype:#04x} (decompressed size {dsize})")


BLOCK_SIZE = 0x10000


def compress_frostbite(data):
    """zlib-compress in 64 KiB blocks with Frostbite block headers (matches Frosty's DAI output)."""
    out = bytearray()
    for i in range(0, len(data), BLOCK_SIZE):
        chunk = data[i:i + BLOCK_SIZE]
        comp = zlib.compress(chunk, 9)
        if len(comp) >= BLOCK_SIZE:  # incompressible: store raw
            out += struct.pack(">IBBH", len(chunk), 0x00, 0x70, len(chunk) & 0xFFFF) + chunk
        else:
            out += struct.pack(">IBBH", len(chunk), 0x02, 0x70, len(comp)) + comp
    return bytes(out)


def decompress_frostbite(data):
    out = bytearray()
    p = 0
    while p < len(data):
        block, p = read_block(data, p)
        out += block
    return bytes(out)
