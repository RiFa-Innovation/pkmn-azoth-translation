"""Install overworld (object event) sprites from the rhw asset bank into the ROM.

Used by mapedit.py ("overworld_sprites" in data/new_maps.json):
  {"gfx_id": 5, "bank_key": "objgfx/species/lugia", "w": 64, "template": 207, "source": "expansion"}

How an overworld sprite works in this ROM (checked against the existing 240 entries):
  * gfx id -> pointer table at 0x08961600 (ids >= 240 are variable-graphics slots; do not use them);
  * each entry is a 36-byte ObjectEventGraphicsInfo: tileTag, paletteTag1, paletteTag2, size, width,
    height, 4 flag bytes, oam, subsprite tables, anims, images, affine anims;
  * `images` is an array of {data ptr, size} frames; the palette is found by tag in the table at
    0x1E0F750 ({ptr, tag, 0}, ptr -> 32 raw bytes).
We reuse an existing entry of the same size as the template (oam/anims), point `images` at new frame data,
and borrow a palette tag that no entry uses by repointing its palette to ours. Unused gfx ids (not used by
any map event) are the slots to overwrite. Bank location: $RHW_BANK or ~/.rhw/bank (assets are the user's own
decomp extracts; they are NOT committed to the repo).
"""
import glob
import os
import struct
import tomllib

from PIL import Image

ROM_BASE = 0x08000000
OW_TABLE = 0x961600
OW_COUNT = 240
PAL_TABLE = 0x1E0F750
INFO_FMT = "<HHHHHHBBBBIIIII"


def bank_dir():
    return os.environ.get("RHW_BANK") or os.path.expanduser("~/.rhw/bank")


def find_asset(key, w, source=None):
    """-> (sheet PNG path, .pal path) for a bank asset (kind objgfx) of this key and frame width."""
    bank = bank_dir()
    for d in sorted(glob.glob(f"{bank}/assets/objgfx-*")):
        t = tomllib.load(open(f"{d}/asset.toml", "rb"))
        if t["asset"]["key"] != key or t["dims"]["w"] != w:
            continue
        if source and source not in t["source"]["id"]:
            continue
        b = t["blobs"]
        blob = lambda name: f"{bank}/blobs/{b[name][:2]}/{b[name]}"
        return blob("sheet"), blob("pal_normal")
    raise FileNotFoundError(f"bank asset {key} w={w} source={source}")


def read_pal(path):
    rows = open(path).read().replace("\r\n", "\n").split("\n")
    n = int(rows[2])
    out = bytearray()
    for r in rows[3:3 + n]:
        r_, g, b = (int(x) for x in r.split())
        out += struct.pack("<H", (r_ >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
    return bytes(out).ljust(32, b"\0")


def tiles(img):
    """4bpp tile data (row-major 8x8 tiles) of a palette-index image."""
    w, h = img.size
    px = img.load()
    out = bytearray()
    for ty in range(h // 8):
        for tx in range(w // 8):
            for y in range(8):
                for x in range(0, 8, 2):
                    lo = px[tx * 8 + x, ty * 8 + y] & 15
                    hi = px[tx * 8 + x + 1, ty * 8 + y] & 15
                    out.append(lo | (hi << 4))
    return bytes(out)


def unused_palette_entries(src):
    """Palette-table entries whose tag no object graphics info uses."""
    used = set()
    for i in range(OW_COUNT):
        p = struct.unpack_from("<I", src, OW_TABLE + 4 * i)[0] - ROM_BASE
        t = struct.unpack_from(INFO_FMT, src, p)
        used |= {t[1], t[2]}
    out = []
    a = PAL_TABLE
    while True:
        p, tag, pad = struct.unpack_from("<IHH", src, a)
        if not (ROM_BASE <= p < ROM_BASE + len(src)) or pad:
            break
        if tag not in used:
            out.append((a, tag))
        a += 8
    return out


def install(rom, src, pool, sprites):
    """Install each sprite spec; returns the count. rom/src are bytearray/bytes of the ROM."""
    free = unused_palette_entries(src)
    # keep the tail of the table: entries near the end are the least likely to be referenced by code
    free.reverse()
    installed = 0
    for s in sprites:
        try:
            png, pal = find_asset(s["bank_key"], s["w"], s.get("source"))
        except (FileNotFoundError, OSError) as e:   # no bank on this machine: keep the original sprite in that slot
            print(f"owgfx: skipped gfx {s['gfx_id']} ({e}); the bank is optional")
            continue
        installed += 1
        sheet = Image.open(png)
        w, h = s["w"], s.get("h", sheet.height)
        nframes = sheet.width // w
        frames = [tiles(sheet.crop((i * w, 0, (i + 1) * w, h))) for i in range(nframes)]
        fsize = len(frames[0])
        addrs = []
        for f in frames:
            a = pool.alloc_aligned(len(f))
            rom[a:a + len(f)] = f
            addrs.append(ROM_BASE + a)
        want = max(s.get("frames", 9), nframes)
        img_arr = pool.alloc_aligned(8 * want)
        for i in range(want):
            ptr = addrs[i] if i < nframes and s.get("map_frames", True) else addrs[0]
            rom[img_arr + 8 * i:img_arr + 8 * i + 8] = struct.pack("<IHH", ptr, fsize, 0)
        pal_at = pool.alloc_aligned(32)
        rom[pal_at:pal_at + 32] = read_pal(pal)
        entry_at, tag = free.pop(0)
        rom[entry_at:entry_at + 4] = struct.pack("<I", ROM_BASE + pal_at)
        tp = struct.unpack_from("<I", src, OW_TABLE + 4 * s["template"])[0] - ROM_BASE
        t = list(struct.unpack_from(INFO_FMT, src, tp))
        t[1] = tag
        t[3], t[4], t[5] = fsize, w, h
        t[13] = ROM_BASE + img_arr
        info = pool.alloc_aligned(36)
        rom[info:info + 36] = struct.pack(INFO_FMT, *t)
        rom[OW_TABLE + 4 * s["gfx_id"]:OW_TABLE + 4 * s["gfx_id"] + 4] = struct.pack("<I", ROM_BASE + info)
    return installed
