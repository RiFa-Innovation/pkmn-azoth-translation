"""GBA graphics helpers: LZ77 (BIOS type 0x10) codec and ROM search for
tile data seen in VRAM.

    python3 scripts/gfx.py find VRAMBIN CHAR_BASE TILE [TILE...]
        search the base ROM for these 4bpp tiles: raw, then inside every
        pointer-referenced LZ77 block; prints rom offset, pointer refs, size.
"""
import struct
import sys

import numpy as np

ROM = "roms/Pokemon Mercury 1.3.3 (patched).gba"


def lz77_decompress(rom, off, limit=0x40000):
    """Returns bytes, or None if the header/stream is not plausible."""
    if rom[off] != 0x10:
        return None
    size = rom[off + 1] | rom[off + 2] << 8 | rom[off + 3] << 16
    if size == 0 or size > limit:
        return None
    out = bytearray()
    p = off + 4
    n = len(rom)
    while len(out) < size:
        if p >= n:
            return None
        flags = rom[p]
        p += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                if p + 1 >= n:
                    return None
                b1, b2 = rom[p], rom[p + 1]
                p += 2
                length = (b1 >> 4) + 3
                disp = ((b1 & 15) << 8 | b2) + 1
                if disp > len(out):
                    return None
                for _ in range(length):
                    out.append(out[-disp])
            else:
                if p >= n:
                    return None
                out.append(rom[p])
                p += 1
    return bytes(out[:size])


def lz77_compressed_len(rom, off):
    """Byte length of the compressed stream at off (header included)."""
    size = rom[off + 1] | rom[off + 2] << 8 | rom[off + 3] << 16
    got, p = 0, off + 4
    while got < size:
        flags = rom[p]
        p += 1
        for bit in range(8):
            if got >= size:
                break
            if flags & (0x80 >> bit):
                got += (rom[p] >> 4) + 3
                p += 2
            else:
                got += 1
                p += 1
    return p - off


def lz77_compress(data):
    """Greedy LZ77 (VRAM-safe: displacement >= 2)."""
    out = bytearray([0x10, len(data) & 255, (len(data) >> 8) & 255, (len(data) >> 16) & 255])
    i, n = 0, len(data)
    while i < n:
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if i >= n:
                break
            best_len, best_disp = 0, 0
            for disp in range(2, min(i, 4096) + 1):
                L = 0
                while L < 18 and i + L < n and data[i + L] == data[i + L - disp]:
                    L += 1
                if L > best_len:
                    best_len, best_disp = L, disp
                    if L == 18:
                        break
            if best_len >= 3:
                flags |= 0x80 >> bit
                d = best_disp - 1
                out += bytes([((best_len - 3) << 4) | (d >> 8), d & 255])
                i += best_len
            else:
                out.append(data[i])
                i += 1
        out[flag_pos] = flags
    while len(out) % 4:
        out.append(0)
    return bytes(out)


def pointer_targets(rom):
    a = np.frombuffer(rom, np.uint8)
    n = len(a) - 3
    u = (a[:n].astype(np.uint32) | (a[1:n + 1].astype(np.uint32) << 8)
         | (a[2:n + 2].astype(np.uint32) << 16) | (a[3:n + 3].astype(np.uint32) << 24))
    al = np.arange(0, n, 4)
    v = u[al]
    m = ((v >> 24) == 8) | ((v >> 24) == 9)
    refs = {}
    for o, t in zip(al[m].tolist(), (v[m] - 0x08000000).tolist()):
        refs.setdefault(t, []).append(o)
    return refs


def find_tiles(rom, tiles):
    hits = []
    for t in tiles:
        i = rom.find(t)
        if i >= 0:
            hits.append(("raw", i, None))
    if hits:
        return hits
    refs = pointer_targets(rom)
    for t, rs in refs.items():
        if t >= len(rom) - 4 or rom[t] != 0x10:
            continue
        d = lz77_decompress(rom, t)
        if d is None:
            continue
        for k, tile in enumerate(tiles):
            j = d.find(tile)
            if j >= 0:
                hits.append(("lz77", t, {"refs": [hex(r) for r in rs[:6]], "size": len(d), "tile": k, "at": j}))
                break
    return hits


if __name__ == "__main__":
    if sys.argv[1] == "find":
        rom = open(ROM, "rb").read()
        vram = open(sys.argv[2], "rb").read()
        cb = int(sys.argv[3], 16)
        tiles = [vram[cb + int(x, 16) * 32: cb + int(x, 16) * 32 + 32] for x in sys.argv[4:]]
        for h in find_tiles(rom, tiles):
            print(h[0], hex(h[1]), h[2])


def locate(dump_dir, bg):
    """Find the ROM LZ77 blocks holding BG<bg>'s tiles and tilemap."""
    import json
    st = json.load(open(f"{dump_dir}/state.json"))["bg"][str(bg)]
    vram = open(f"{dump_dir}/vram.bin", "rb").read()
    cb, sb = int(st["char_base"], 16), int(st["screen_base"], 16)
    tmap = vram[sb:sb + 0x500]
    used = sorted({struct.unpack_from("<H", tmap, i * 2)[0] & 0x3FF for i in range(640)})
    # distinctive tiles: many distinct colours
    tiles = [vram[cb + t * 32: cb + t * 32 + 32] for t in used]
    tiles = sorted(tiles, key=lambda t: -len(set(t)))[:6]
    rows = [tmap[r * 64:(r + 1) * 64] for r in range(20) if len(set(tmap[r * 64:(r + 1) * 64])) > 6][:3]
    rom = open(ROM, "rb").read()
    refs = pointer_targets(rom)
    res = {"tiles": [], "map": []}
    for t, rs in refs.items():
        if t >= len(rom) - 4 or rom[t] != 0x10:
            continue
        d = lz77_decompress(rom, t)
        if d is None:
            continue
        if any(x in d for x in tiles):
            res["tiles"].append((hex(t), len(d), [hex(r) for r in rs[:4]],
                                 "starts at char_base" if vram[cb:cb + 64] == d[:64] else ""))
        if any(r in d for r in rows):
            res["map"].append((hex(t), len(d), [hex(r) for r in rs[:4]]))
    # raw fallbacks
    for name, needles in (("tiles_raw", tiles), ("map_raw", rows)):
        for nd in needles:
            i = rom.find(nd)
            if i >= 0:
                res[name] = hex(i)
                break
    return res


if __name__ == "__main__" and sys.argv[1] == "locate":
    print(locate(sys.argv[2], int(sys.argv[3])))
