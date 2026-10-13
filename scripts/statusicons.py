"""English status icons for the party menu / summary screen (issue #72).

The hack's status sprite sheet is a 1 KB LZ77 blob (4bpp, 32x8 icons, four
tiles each) that exists twice in the ROM, one copy per screen:

    0x720000  referenced from 0x45A574
    0x721D30  referenced from 0x13A314

Icons, in order: PSN, PAR, SLP, FRZ, BRN, PKRS (Pokerus), FNT; each is a
coloured pill with a two-hanzi word in colour 2. The words are erased and
the vanilla codes drawn in the 4x7 capitals of typeicons.py.

    python3 scripts/statusicons.py OUT.png    # preview (before | after)
Used by insert.py via build(src_rom) -> (lz_bytes, [ref slots]).
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import gfx  # noqa: E402
from typeicons import G as _G  # noqa: E402

G = dict(_G, Z=["####", "...#", "..#.", ".#..", "#...", "#...", "####"])

BLOBS = {0x720000: 0x45A574, 0x721D30: 0x13A314}   # blob -> pointer slot
CODES = ["PSN", "PAR", "SLP", "FRZ", "BRN", "PKRS", "FNT"]
INK = 2
X0, X1 = 6, 26          # the pill spans columns 6..25
Y0 = 0                  # glyphs are 7 rows in an 8-row pill


def get(d, ic, x, y):
    b = d[(ic * 4 + x // 8) * 32 + y * 4 + (x % 8) // 2]
    return (b >> 4) if x & 1 else b & 15


def put(d, ic, x, y, c):
    i = (ic * 4 + x // 8) * 32 + y * 4 + (x % 8) // 2
    d[i] = (d[i] & 0x0F) | (c << 4) if x & 1 else (d[i] & 0xF0) | c


def redraw(old):
    d = bytearray(old)
    for ic, code in enumerate(CODES):
        counts = {}
        for y in range(8):
            for x in range(32):
                c = get(d, ic, x, y)
                if c not in (0, INK):
                    counts[c] = counts.get(c, 0) + 1
        bg = max(counts, key=counts.get)
        for y in range(8):
            for x in range(32):
                if get(d, ic, x, y) == INK:
                    put(d, ic, x, y, bg)
        # letters: 4 px advance (3 for I/T/Y), 1 px gap, centred in the pill
        width = sum(len(G[ch][0]) for ch in code) + len(code) - 1
        x = X0 + (X1 - X0 - width) // 2
        for ch in code:
            g = G[ch]
            for gy, line in enumerate(g):
                for gx, p in enumerate(line):
                    if p == "#" and get(d, ic, x + gx, Y0 + gy):
                        put(d, ic, x + gx, Y0 + gy, INK)
            x += len(g[0]) + 1
    return bytes(d)


def build(src):
    """-> (lz_bytes, [pointer slots]); both copies must be identical."""
    blobs = [gfx.lz77_decompress(src, b) for b in BLOBS]
    assert blobs[0] == blobs[1] and len(blobs[0]) == 1024, "status sheet changed"
    for b, ref in BLOBS.items():
        assert struct.unpack_from("<I", src, ref)[0] == 0x08000000 + b, hex(ref)
    return gfx.lz77_compress(redraw(blobs[0])), list(BLOBS.values())


def preview(out):
    from PIL import Image
    src = open("roms/Pokemon Mercury 1.3.3 (patched).gba", "rb").read()
    old = gfx.lz77_decompress(src, 0x720000)
    new = redraw(old)
    pal = [(0, 0, 0), (255, 255, 255), (50, 50, 50), (200, 0, 0), (60, 60, 200), (120, 120, 240),
           (240, 200, 0), (250, 230, 120), (130, 130, 130), (190, 190, 190), (150, 220, 240),
           (200, 240, 250), (240, 120, 40), (250, 180, 120), (60, 60, 60), (110, 110, 110)]
    im = Image.new("RGB", (32 * 2 + 4, 8 * 8), (0, 0, 0))
    for n, data in enumerate((old, new)):
        for ic in range(8):
            for y in range(8):
                for x in range(32):
                    im.putpixel((n * 36 + x, ic * 8 + y), pal[get(data, ic, x, y)])
    im.resize((im.width * 8, im.height * 8), Image.NEAREST).save(out)


if __name__ == "__main__":
    preview(sys.argv[1])
