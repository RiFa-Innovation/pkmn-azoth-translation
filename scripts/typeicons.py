"""English type icons for the hack's menu-info sheet (BlitMenuInfoIcon now
reads 0x08EFD4C0 / table 0x09CCC410: battle move info, summary, move
learning). Each type icon is 32x12: a coloured symbol on the left, the
Chinese type name on the light right half (colour 0xE, ink 0xF). The hack's
own Fairy icon already says FAI in a 4x7 capital font; the other types get
the same three-letter style. The TYPE/POWER/ACCURACY/PP/EFFECT pills sit at
the same tile offsets as vanilla FireRed's sheet, so vanilla's English tiles
are copied over them.

    python3 scripts/typeicons.py OUT.png    # preview (before | after)
Used by insert.py via build(src_rom, base_rom) -> bytes for SHEET.
"""
import sys

SHEET, SHEET_TILES = 0xEFD4C0, 0x110        # tiles used by the sheet (rows 0..16)
VANILLA_SHEET = 0xE95DDC                     # gMenuInfoElements_Gfx (clean FR)
BG, INK = 0xE, 0xF
EDGE = [15, 14, 14, 13, 13, 12, 12, 11, 11, 10, 10, 10]  # first light pixel per row

# tile offset (16 tiles per row) -> code
ICONS = {32: "NOR", 36: "FIR", 40: "WAT", 44: "GRA", 64: "ELE", 68: "ROC", 72: "GRO",
         76: "ICE", 96: "FLY", 100: "FIG", 104: "GHO", 108: "BUG", 128: "POI",
         132: "PSY", 136: "STE", 140: "DAR", 160: "DRA", 164: "???"}
LABELS = (0xA8, 0xC0, 0xC8, 0xE0, 0xE8)    # TYPE POWER ACCURACY PP EFFECT, 6x2 tiles

G = {  # 4x7 capitals, same shapes as the F/A/I of the hack's FAI icon
    "A": [".##.", "#..#", "#..#", "####", "#..#", "#..#", "#..#"],
    "B": ["###.", "#..#", "#..#", "###.", "#..#", "#..#", "###."],
    "C": [".###", "#...", "#...", "#...", "#...", "#...", ".###"],
    "D": ["###.", "#..#", "#..#", "#..#", "#..#", "#..#", "###."],
    "E": ["####", "#...", "#...", "###.", "#...", "#...", "####"],
    "F": ["####", "#...", "#...", "###.", "#...", "#...", "#..."],
    "G": [".###", "#...", "#...", "#.##", "#..#", "#..#", ".###"],
    "H": ["#..#", "#..#", "#..#", "####", "#..#", "#..#", "#..#"],
    "I": ["###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
    "K": ["#..#", "#.#.", "##..", "#...", "##..", "#.#.", "#..#"],
    "L": ["#...", "#...", "#...", "#...", "#...", "#...", "####"],
    "N": ["#..#", "##.#", "##.#", "#.##", "#.##", "#..#", "#..#"],
    "O": [".##.", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."],
    "P": ["###.", "#..#", "#..#", "###.", "#...", "#...", "#..."],
    "R": ["###.", "#..#", "#..#", "###.", "#.#.", "#..#", "#..#"],
    "S": [".###", "#...", "#...", ".##.", "...#", "...#", "###."],
    "T": ["###", ".#.", ".#.", ".#.", ".#.", ".#.", ".#."],
    "U": ["#..#", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."],
    "W": ["#..#", "#..#", "#..#", "#..#", "####", "####", "#..#"],
    "Y": ["#.#", "#.#", "#.#", ".#.", ".#.", ".#.", ".#."],
    "?": [".##.", "#..#", "...#", "..#.", ".#..", "....", ".#.."],
}


def get(sheet, off, x, y):
    t = off + (y // 8) * 16 + x // 8
    b = sheet[t * 32 + (y % 8) * 4 + (x % 8) // 2]
    return (b >> 4) if x & 1 else b & 15


def put(sheet, off, x, y, c):
    t = off + (y // 8) * 16 + x // 8
    i = t * 32 + (y % 8) * 4 + (x % 8) // 2
    sheet[i] = (sheet[i] & 0x0F) | (c << 4) if x & 1 else (sheet[i] & 0xF0) | c


def build(src, base):
    sheet = bytearray(src[SHEET:SHEET + SHEET_TILES * 32])
    for off, code in ICONS.items():
        left = get(sheet, off, 0, 0)
        for y in range(12):
            # the diagonal edge as in the clean FAI icon; the symbol is x <= 10
            for x in range(11, 32):
                if get(sheet, off, x, y) == INK:
                    put(sheet, off, x, y, BG if x >= EDGE[y] else left)
        x = 16
        for ch in code:
            g = G[ch]
            for gy, line in enumerate(g):
                for gx, p in enumerate(line):
                    if p == "#":
                        put(sheet, off, x + gx, 1 + gy, INK)
            x += len(g[0]) + 1
    for off in LABELS:
        for ty in range(2):
            for tx in range(6):
                t = off + ty * 16 + tx
                v = VANILLA_SHEET + t * 32
                sheet[t * 32:t * 32 + 32] = base[v:v + 32]
    return bytes(sheet)


def preview(out):
    from PIL import Image
    src = open("roms/Pokemon Mercury 1.3.3 (patched).gba", "rb").read()
    base = open("roms/Pokemon - FireRed Version (USA, Europe).gba", "rb").read()
    new = build(src, base)
    old = src[SHEET:SHEET + SHEET_TILES * 32]
    rows = SHEET_TILES // 16
    im = Image.new("L", (128 * 2 + 4, rows * 8))
    for n, s in enumerate((old, new)):
        for t in range(SHEET_TILES):
            for y in range(8):
                for x in range(8):
                    b = s[t * 32 + y * 4 + x // 2]
                    c = (b >> 4) if x & 1 else b & 15
                    im.putpixel((n * 132 + (t % 16) * 8 + x, (t // 16) * 8 + y), c * 16)
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(out)


if __name__ == "__main__":
    preview(sys.argv[1])
