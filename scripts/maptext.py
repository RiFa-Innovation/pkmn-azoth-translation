"""Redraw text baked into an overworld map's tileset (screens built as maps,
e.g. the starter-choice screen, map 43.7).

The picture is a map layout: blocks -> metatiles (2x2 tiles, two layers) ->
4bpp tiles of the primary (ids < 640) / secondary (>= 640) tileset. To draw
English we render the layout to pixels, erase + draw text inside a rect of
whole blocks, and give every block in the rect its own metatile (reusing
secondary metatile slots no layout uses) built from fresh tiles appended to
the secondary tileset. The tileset tiles are recompressed and relocated
(caller repoints); metatiles, attributes and blockdata change in place.

    python3 scripts/maptext.py render SPEC OUT.png    # before/after preview
Used by insert.py via apply(spec_path, src_rom) -> list of (offset, bytes)
in-place writes plus (lz_bytes, refs) for the relocated tiles.
"""
import json
import struct
import sys

from PIL import Image

sys.path.insert(0, __import__("os").path.dirname(__file__))
import gfx  # noqa: E402

BASE = "roms/Pokemon - FireRed Version (USA, Europe).gba"
FONT_PNG = "utilities/pokefirered/graphics/fonts/latin_normal.png"
FONT_WIDTHS = 0x207300  # sFontNormalLatinGlyphWidths in the clean ROM
PRI_TILES, PRI_METATILES = 640, 640


def ptr(rom, a):
    return struct.unpack_from("<I", rom, a)[0] - 0x08000000


class Layout:
    def __init__(self, rom, layout_off):
        self.rom = rom
        self.w, self.h, _, blk, pri, sec = struct.unpack_from("<iiIIII", rom, layout_off)
        self.blk = blk - 0x08000000
        self.pri, self.sec = pri - 0x08000000, sec - 0x08000000
        self.blocks = [struct.unpack_from("<H", rom, self.blk + 2 * i)[0] for i in range(self.w * self.h)]
        self.ts = {}
        for name, t in (("pri", self.pri), ("sec", self.sec)):
            comp, _, _, tiles, pals, metas, _, attrs = struct.unpack_from("<BBHIIIII", rom, t)
            tiles -= 0x08000000
            data = gfx.lz77_decompress(rom, tiles) if comp else rom[tiles:tiles + (PRI_TILES if name == "pri" else 384) * 32]
            self.ts[name] = {"struct": t, "tiles_off": tiles, "tiles": bytearray(data), "comp": comp,
                             "pals": pals - 0x08000000, "metas": metas - 0x08000000, "attrs": attrs - 0x08000000}

    def tile(self, tid):
        ts, i = (self.ts["pri"], tid) if tid < PRI_TILES else (self.ts["sec"], tid - PRI_TILES)
        d = ts["tiles"]
        return d[i * 32:i * 32 + 32] if i * 32 + 32 <= len(d) else bytes(32)

    def metatile(self, mid):
        ts, i = (self.ts["pri"], mid) if mid < PRI_METATILES else (self.ts["sec"], mid - PRI_METATILES)
        return list(struct.unpack_from("<8H", self.rom, ts["metas"] + 16 * i))

    def render(self, metatile_fn=None):
        """-> (pix, pal) rows of colour index and palette number per pixel."""
        W, H = self.w * 16, self.h * 16
        pix = [[0] * W for _ in range(H)]
        pal = [[0] * W for _ in range(H)]
        for by in range(self.h):
            for bx in range(self.w):
                m = (metatile_fn or self.metatile)(self.blocks[by * self.w + bx] & 0x3FF)
                for layer in range(2):
                    for k in range(4):
                        e = m[layer * 4 + k]
                        t, hf, vf, pb = e & 0x3FF, e & 0x400, e & 0x800, e >> 12
                        td = self.tile(t)
                        ox, oy = bx * 16 + (k & 1) * 8, by * 16 + (k >> 1) * 8
                        for y in range(8):
                            for x in range(8):
                                b = td[y * 4 + x // 2]
                                c = (b >> 4) if x & 1 else b & 15
                                if c or layer == 0:
                                    py, px = oy + (7 - y if vf else y), ox + (7 - x if hf else x)
                                    pix[py][px], pal[py][px] = c, pb
        return pix, pal


def palettes(rom, lay):
    out = []
    for name in ("pri", "sec"):
        p = lay.ts[name]["pals"]
        for i in range(16):
            out.append([struct.unpack_from("<H", rom, p + 32 * i + 2 * c)[0] for c in range(16)])
    # FR: palettes 0-6 from primary, 7-12 from secondary
    return [out[i] if i < 7 else out[16 + i] for i in range(16)]


def font():
    im = Image.open(FONT_PNG)
    base = open(BASE, "rb").read()
    widths = base[FONT_WIDTHS:FONT_WIDTHS + 0x200]
    return im, widths


def draw(pix, text, x, y, ink, shadow, fnt):
    import mercury_text as mt
    im, widths = fnt
    for code in mt.encode_en(text)[:-1]:
        gx, gy = (code % 16) * 16, (code // 16) * 16
        w = widths[code]
        for yy in range(16):
            for xx in range(w):
                c = im.getpixel((gx + xx, gy + yy))
                if c == 1:
                    pix[y + yy][x + xx] = ink
                elif c == 2 and shadow is not None:
                    pix[y + yy][x + xx] = shadow
        x += w
    return x


def build(spec, rom):
    lay = Layout(rom, int(spec["layout"], 16))
    pix, pal = lay.render()
    x0, y0, x1, y1 = spec["rect"]            # whole blocks, layout pixels
    ex0, ey0, ex1, ey1 = spec.get("erase", spec["rect"])
    bg = spec["bg"]
    for y in range(ey0, ey1):
        for x in range(ex0, ex1):
            pix[y][x] = bg
    fnt = font()
    for ln in spec["lines"]:
        draw(pix, ln["text"], ln["x"], ln["y"], spec["ink"], spec.get("shadow"), fnt)
    # metatile slots no layout uses (the spec lists every layout of the tileset)
    used = set()
    for lo in spec["layouts_using_tileset"]:
        l2 = Layout(rom, int(lo, 16))
        used |= {b & 0x3FF for b in l2.blocks}
    free = [m for m in range(PRI_METATILES + 383, PRI_METATILES, -1) if m not in used]
    sec = lay.ts["sec"]
    tiles = bytearray(sec["tiles"])
    index = {bytes(tiles[i:i + 32]): PRI_TILES + i // 32 for i in range(0, len(tiles), 32)}
    writes, newmeta = {}, {}
    for by in range(y0 // 16, y1 // 16):
        for bx in range(x0 // 16, x1 // 16):
            entries = []
            for k in range(4):
                ox, oy = bx * 16 + (k & 1) * 8, by * 16 + (k >> 1) * 8
                pb = pal[oy][ox]
                td = bytearray(32)
                for y in range(8):
                    for x in range(8):
                        c = pix[oy + y][ox + x]
                        td[y * 4 + x // 2] |= c << 4 if x & 1 else c
                td = bytes(td)
                if td not in index:
                    assert len(tiles) // 32 < 384, "secondary tileset full"
                    index[td] = PRI_TILES + len(tiles) // 32
                    tiles += td
                entries.append(index[td] | pb << 12)
            entries += [0, 0, 0, 0]          # top layer: transparent tile 0
            i = by * lay.w + bx
            old = lay.blocks[i]
            key = tuple(entries)
            if key not in newmeta:
                m = free.pop(0)
                newmeta[key] = m
                mo = sec["metas"] + 16 * (m - PRI_METATILES)
                writes[mo] = struct.pack("<8H", *entries)
                # behaviour/attributes copied from the block's old metatile
                om = old & 0x3FF
                ats = lay.ts["pri" if om < PRI_METATILES else "sec"]
                oi = om if om < PRI_METATILES else om - PRI_METATILES
                writes[sec["attrs"] + 4 * (m - PRI_METATILES)] = rom[ats["attrs"] + 4 * oi:ats["attrs"] + 4 * oi + 4]
            writes[lay.blk + 2 * i] = struct.pack("<H", (old & ~0x3FF) | newmeta[key])
    lz = gfx.lz77_compress(bytes(tiles))
    refs = [sec["struct"] + 4]
    return lay, writes, lz, refs, pix


def apply(spec_path, rom):
    spec = json.load(open(spec_path, encoding="utf-8"))
    _, writes, lz, refs, _ = build(spec, rom)
    return writes, lz, refs


def render(spec_path, out):
    rom = open(spec_path and "roms/Pokemon Mercury 1.3.3 (patched).gba", "rb").read()
    spec = json.load(open(spec_path, encoding="utf-8"))
    lay = Layout(rom, int(spec["layout"], 16))
    pals = palettes(rom, lay)
    before, bpal = lay.render()
    _, writes, lz, _, after = build(spec, rom)

    def img(p, pl):
        im = Image.new("RGB", (len(p[0]), len(p)))
        for y, row in enumerate(p):
            for x, c in enumerate(row):
                v = pals[pl[y][x]][c]
                im.putpixel((x, y), ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3))
        return im
    a, b = img(before, bpal), img(after, bpal)
    g = Image.new("RGB", (a.width, a.height * 2 + 4))
    g.paste(a, (0, 0))
    g.paste(b, (0, a.height + 4))
    g.resize((g.width * 2, g.height * 2), Image.NEAREST).save(out)
    print(f"tiles lz {len(lz)} bytes, {len(writes)} in-place writes")


if __name__ == "__main__":
    if sys.argv[1] == "render":
        render(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "show":   # render the layout as is (find coordinates)
        rom = open("roms/Pokemon Mercury 1.3.3 (patched).gba", "rb").read()
        lay = Layout(rom, int(sys.argv[2], 16))
        pals = palettes(rom, lay)
        p, pl = lay.render()
        im = Image.new("RGB", (len(p[0]), len(p)))
        for y, row in enumerate(p):
            for x, c in enumerate(row):
                v = pals[pl[y][x]][c]
                im.putpixel((x, y), ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3))
        im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(sys.argv[3])
