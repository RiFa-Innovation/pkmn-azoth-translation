"""Render a map layout to PNG (blocks -> metatiles -> tiles with palettes).

    python3 scripts/maprender.py G.N OUT.png [ROM] [--ids]   # a map by group.num
    python3 scripts/maprender.py @0x08B39704 OUT.png          # a layout struct address

--ids draws each block's metatile id (small) and marks collision; useful for authoring
new layouts out of an existing tileset pair (scripts/mapedit.py "layouts").
"""
import os
import struct
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
import maptext  # noqa: E402
import mapedit  # noqa: E402

BASE_ROM = "build/Mercury_EN.gba"


def rgb(c):
    return ((c & 31) * 8, ((c >> 5) & 31) * 8, ((c >> 10) & 31) * 8)


def layout_off(rom, spec):
    if spec.startswith("@"):
        return int(spec[1:], 0) - 0x08000000
    g, n = (int(x) for x in spec.split("."))
    h = mapedit.header_off(rom, g, n)
    return struct.unpack_from("<I", rom, h)[0] - 0x08000000


def render(rom, off, ids=False):
    lay = maptext.Layout(rom, off)
    pix, pal = lay.render()
    pals = maptext.palettes(rom, lay)
    H, W = len(pix), len(pix[0])
    im = Image.new("RGB", (W, H))
    px = im.load()
    for y in range(H):
        for x in range(W):
            px[x, y] = rgb(pals[pal[y][x]][pix[y][x]])
    if ids:
        d = ImageDraw.Draw(im)
        for by in range(lay.h):
            for bx in range(lay.w):
                b = lay.blocks[by * lay.w + bx]
                d.text((bx * 16 + 1, by * 16 + 1), str(b & 0x3FF), fill=(255, 255, 255))
                if b & 0xC00:
                    d.rectangle((bx * 16, by * 16, bx * 16 + 15, by * 16 + 15), outline=(255, 0, 0))
    return im, lay


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rom = open(args[2] if len(args) > 2 else BASE_ROM, "rb").read()
    im, lay = render(rom, layout_off(rom, args[0]), "--ids" in sys.argv)
    im.save(args[1])
    print(lay.w, lay.h, im.size)
