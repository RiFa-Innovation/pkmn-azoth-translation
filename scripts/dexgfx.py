"""English Pokédex-list header and button labels (issue: Pokédex graphics still Chinese).

The hack's Pokédex screen draws its BG1 panel from an LZ77 tileset at 0x764070
(208 tiles, pointer slot 0x73B94C) and a tilemap the code builds at runtime.
The map is not in the ROM, so the text is edited in place, in tile space: each
label is a block of tile ids (read from the live map), the hanzi are erased and
the English drawn with the game's 6 px font. Those tile ids appear once each in
the screen, so editing them changes only the label.

    python3 scripts/dexgfx.py OUT.png     # before | after preview
Used by insert.py via build(src_rom) -> (lz_bytes, [pointer slots]).
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import gfx  # noqa: E402

LZ, REF = 0x764070, 0x73B94C
OBJ_LZ, OBJ_REF = 0x7639DC, 0x75D3F0   # sidebar label sprites (256-tile OBJ sheet, 1D mapping)
FONT = json.load(open(os.path.join(os.path.dirname(__file__), "..", "gfx", "font6.json"), encoding="utf-8"))

# tile-id blocks (rows of ids, left to right) as laid out on screen
HEADER = [list(range(3, 11)), list(range(15, 23)), list(range(31, 39))]
BUTTONS = [list(range(63, 72)), list(range(77, 86)), list(range(88, 97))]

# erase = (x0, y0, x1, y1) in block pixels, colours to wipe, fill; text at (x, y)
EDITS = [
    dict(block=HEADER, erase=(20, 5, 48, 20), colors={1, 15}, bg=lambda y: 7,
         text="POKEDEX", at=(None, 5), center=34, ink=15, shadow=1, area=(8, 5, 60, 20)),
    dict(block=BUTTONS, erase=(5, 13, 29, 24), colors={15, 4}, bg=lambda y: 4 if y == 18 else 1,
         text="MENU", at=(None, 12), center=16, ink=15, shadow=4, area=(4, 13, 30, 24)),
    dict(block=BUTTONS, erase=(38, 13, 66, 24), colors={15, 4}, bg=lambda y: 4 if y == 18 else 1,
         text="SEARCH", at=(None, 12), center=50, ink=15, shadow=4, area=(34, 13, 68, 24)),
]


def sprite(t0, tw, th):
    return [[t0 + r * tw + c for c in range(tw)] for r in range(th)]


# sidebar label sprites: white text (15) with grey shadow (4) on transparent (0)
OBJ_EDITS = [
    dict(block=sprite(64, 8, 2), erase=(14, 4, 44, 14), colors={15, 4}, bg=lambda y: 0,
         text="SEEN", at=(None, 4), center=None, left=16, ink=15, shadow=4),
    dict(block=sprite(96, 8, 2), erase=(14, 4, 44, 14), colors={15, 4}, bg=lambda y: 0,
         text="CAUGHT", at=(None, 4), center=None, left=16, ink=15, shadow=4),
    dict(block=sprite(160, 4, 2), erase=(0, 0, 32, 12), colors={15, 4}, bg=lambda y: 0,
         text="JOHTO", at=(None, 0), center=None, left=1, ink=15, shadow=4),
]


def tab(block, text, selected):
    """A detail-page tab label: the selected tab is black-on-white, the others dim pink."""
    ink, shadow = (15, 1) if selected else (9, 6)
    return dict(block=block, erase=(0, 0, len(block[0]) * 8, 13), colors={ink, shadow}, bg=lambda y: 7,
                text=text, at=(None, 1), center=None, left=(len(block[0]) * 8 - 24) // 2, ink=ink, shadow=shadow)


def tabs(rows, selected):
    """rows: (top ids, bottom ids) per tab in order INFO, AREA, FORM."""
    return [tab([list(top), list(bot)], name, i == selected)
            for i, ((top, bot), name) in enumerate(zip(rows, ("INFO", "AREA", "FORM")))]


# Pokédex entry pages: each page has its own tileset with its tab drawn "selected"
INFO_EDITS = tabs([((3, 4, 5), (29, 30, 31)), ((6, 7, 8, 9), (32, 33, 34, 35)), ((21, 22, 23), (48, 49, 50))], 0)
AREA_EDITS = tabs([((3, 4, 5), (30, 31, 32)), ((6, 7, 8, 9), (33, 34, 35, 36)), ((22, 23, 24), (49, 50, 51))], 1) + [
    dict(block=sprite(77, 4, 1) + sprite(87, 4, 1), erase=(0, 0, 32, 13), colors={15, 3}, bg=lambda y: 1,
         text="Time", at=(None, 1), center=None, left=4, ink=15, shadow=3)]    # 切换
FORM_EDITS = tabs([((4, 5, 6), (30, 31, 32)), ((7, 8, 9, 10), (33, 34, 35, 36)), ((93, 94, 95), (101, 102, 103))], 2)

# Search page (SELECT in the list): green tabs and orange/green label buttons. The buttons are 5 tiles
# (40 px) and their bottom-right tile 190 is shared, so the text stays inside the first four columns.
def btn(top, bot, text, fill, shadow, x1=33, center=None):
    return dict(block=[list(top), list(bot)], erase=(6, 3, x1, 13), colors={3, shadow}, bg=lambda y: fill,
                text=text, at=(None, 1), center=center, left=None if center else 6, ink=3, shadow=shadow,
                tight=center is None)


def stab(top, bot, text):
    return dict(block=[list(top), list(bot)], erase=(9, 2, len(top) * 8 - 2, 13), colors={3, 9}, bg=lambda y: 8,
                text=text, at=(None, 1), center=len(top) * 4, ink=3, shadow=9, tight=True)


SEARCH_EDITS = [
    stab((106, 107, 108, 109, 110, 111), (122, 148, 124, 125, 151, 127), "Search"),
    stab((101, 102, 103, 104, 105, 111), (117, 153, 119, 120, 156, 127), "Switch"),
    stab((74, 75, 76, 77, 78), (90, 158, 92, 93, 161), "Cancel"),

    btn((42, 43, 44, 45, 46), (58, 172, 173, 61, 175), "Name", 10, 11, 37),
    btn((180, 65, 66, 67, 68), (80, 187, 188, 189, 190), "Color", 10, 11),
    btn((69, 70, 71, 72, 73), (194, 195, 196, 88, 190), "Type", 10, 11),
    btn((37, 38, 39, 40, 41), (53, 204, 205, 56, 190), "Sort", 10, 11),
    btn((231, 97, 98, 99, 235), (112, 220, 114, 115, 236), "OK", 8, 9, 36, 20),
]

# (LZ tileset, pointer slots, tile count, edits)
PAGES = [(0x762ABC, [0x737E3C, 0x7388B4], 256, INFO_EDITS),
         (0x762000, [0x73A564], 112, AREA_EDITS),
         (0x7624D8, [0x739444], 128, FORM_EDITS),
         (0x7617E0, [0x73AACC], 240, SEARCH_EDITS)]


def get(t, k, x, y):
    b = t[k * 32 + y * 4 + x // 2]
    return (b >> 4) if x & 1 else b & 15


def put(t, k, x, y, c):
    i = k * 32 + y * 4 + x // 2
    t[i] = (t[i] & 0x0F) | (c << 4) if x & 1 else (t[i] & 0xF0) | c


def compose(t, block):
    h, w = len(block) * 8, len(block[0]) * 8
    return [[get(t, block[y // 8][x // 8], x % 8, y % 8) for x in range(w)] for y in range(h)]


def store(t, block, img):
    for y, row in enumerate(img):
        for x, c in enumerate(row):
            put(t, block[y // 8][x // 8], x % 8, y % 8, c)


def draw(img, text, x, y, ink, shadow, tight=False):
    for ch in text:
        g = FONT.get(ch) or FONT["?"]
        for r, row in enumerate(g["rows"]):
            for i, p in enumerate(row):
                if p == "#":
                    img[y + r][x + i] = ink
                elif p == "o":
                    img[y + r][x + i] = shadow
        x += g["w"] - (1 if tight else 0)


def redraw(old, edits=EDITS):
    t = bytearray(old)
    for e in edits:
        img = compose(t, e["block"])
        x0, y0, x1, y1 = e["erase"]
        for y in range(y0, y1):
            for x in range(x0, x1):
                if img[y][x] in e["colors"]:
                    img[y][x] = e["bg"](y)
        width = sum((FONT.get(c) or FONT["?"])["w"] - (1 if e.get("tight") else 0) for c in e["text"])
        x = e["left"] if e.get("left") is not None else e["center"] - width // 2
        draw(img, e["text"], x, e["at"][1], e["ink"], e["shadow"], e.get("tight", False))
        store(t, e["block"], img)
    return bytes(t)


# START popup: lines of 6x2 tiles (48x16 px) in two raw tilemap copies. Tiles 125..165 belong to the
# popup alone, but lines 2 and 3 shared tiles, so every line is re-laid with its own tiles and the
# maps rewritten. MAPS: ROM offset of a copy's first line -> which LINES its slots show
POOL = [k for k in range(125, 166) if k != 131]     # 131 is the frame's right edge
POP_COL0 = 2                       # first text column inside a 10-wide map row
ROW_STRIDE = 64                    # a map row is 32 entries
LINES = ["To List", "First", "Last", "Back", "Close"]      # 返回目录 跳至首位 跳至末位 返回图鉴 关闭图鉴
MAPS = {0x7604A8: [0, 1, 2, 3, 4], 0x7607A8: [0, 1, 2, 4]}  # map copy -> which LINES each slot shows


def popup(src, tiles):
    """Draw the popup lines into freed tiles; -> map patches [(offset, bytes)]."""
    seen, cells = {}, {}
    for n, text in enumerate(LINES):
        img = [[1] * 48 for _ in range(16)]
        draw(img, text, 2, 2, 15, 3)
        for r in range(2):
            for c in range(6):
                data = bytearray(32)
                for y in range(8):
                    for x in range(8):
                        data[y * 4 + x // 2] |= img[r * 8 + y][c * 8 + x] << (4 * (x & 1))
                data = bytes(data)
                if data not in seen:
                    seen[data] = POOL[len(seen)]      # IndexError = text too wide for the freed tiles
                cells[(n, r, c)] = seen[data]
    for data, k in seen.items():
        tiles[k * 32:k * 32 + 32] = data
    patches = []
    for base, slots in MAPS.items():
        for slot, n in enumerate(slots):
            for r in range(2):
                at = base + (slot * 2 + r) * ROW_STRIDE + POP_COL0 * 2
                old = src[at:at + 12]
                new = b"".join(struct.pack("<H", (struct.unpack_from("<H", old, 2 * c)[0] & 0xFC00) | cells[(n, r, c)])
                               for c in range(6))
                patches.append((at, old, new))
    return patches


def build(src):
    """-> ([(lz_bytes, [pointer slots])], [(offset, orig, new)]): BG1 tileset, sidebar OBJ sheet, popup maps."""
    out, patches = [], []
    for lz, refs, n, edits in [(LZ, [REF], 208, EDITS), (OBJ_LZ, [OBJ_REF], 256, OBJ_EDITS)] + PAGES:
        for ref in refs:
            assert struct.unpack_from("<I", src, ref)[0] == 0x08000000 + lz, "dex gfx ref moved"
        old = gfx.lz77_decompress(src, lz)
        assert old and len(old) == n * 32, "dex gfx blob changed"
        data = bytearray(redraw(old, edits))
        if lz == LZ:
            patches = popup(src, data)
        out.append((gfx.lz77_compress(bytes(data)), refs))
    return out, patches


def preview(out):
    from PIL import Image
    src = open("roms/Pokemon Mercury 1.3.3 (patched).gba", "rb").read()
    old = gfx.lz77_decompress(src, LZ)
    new = redraw(old)
    pal = {1: (0, 0, 0), 7: (230, 50, 50), 15: (255, 255, 255), 4: (140, 140, 140), 5: (240, 120, 120),
           3: (80, 80, 80), 8: (200, 200, 200)}
    blocks = [HEADER, BUTTONS]
    oldo = gfx.lz77_decompress(src, OBJ_LZ)
    newo = redraw(oldo, OBJ_EDITS)
    ims = []
    for data, od in ((old, oldo), (new, newo)):
        for b in [e["block"] for e in OBJ_EDITS]:
            img = compose(od, b)
            im = Image.new("RGB", (len(img[0]), len(img)), (255, 0, 255))
            for y, row in enumerate(img):
                for x, c in enumerate(row):
                    if c:
                        im.putpixel((x, y), pal.get(c, (c * 16, c * 16, c * 16)))
            ims.append(im)
        for b in blocks:
            img = compose(data, b)
            im = Image.new("RGB", (len(img[0]), len(img)))
            for y, row in enumerate(img):
                for x, c in enumerate(row):
                    im.putpixel((x, y), pal.get(c, (c * 16, c * 16, c * 16)))
            ims.append(im)
    W = max(i.width for i in ims)
    H = sum(i.height + 2 for i in ims)
    m = Image.new("RGB", (W, H), (90, 90, 90))
    y = 0
    for i in ims:
        m.paste(i, (0, y))
        y += i.height + 2
    m.resize((m.width * 6, m.height * 6), Image.NEAREST).save(out)


if __name__ == "__main__":
    preview(sys.argv[1])
