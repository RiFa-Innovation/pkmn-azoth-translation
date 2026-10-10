"""Redraw image text (Chinese baked into BG graphics) with English.

A spec (gfx/<name>.json) names an LZ77 tileset + LZ77 tilemap in the base
ROM, the palette bank, and edits: erase rectangles (ink/shadow colours ->
background) and English text drawn with the game's own 6px font
(gfx/font6.json). The edited screen rect is re-tiled into fresh tiles
appended to the tileset (so tiles shared elsewhere are untouched), the map is
updated, both are recompressed and the caller relocates them.

    python3 scripts/gfx_text.py render gfx/settings.json OUT.png   # before/after preview
    python3 scripts/gfx_text.py cols gfx/settings.json Y0 Y1        # ink column runs
Used by insert.py via apply(spec, src_rom) -> [(new_bytes, refs)].
"""
import json
import struct
import sys

from PIL import Image

sys.path.insert(0, __import__("os").path.dirname(__file__))
import gfx  # noqa: E402

FONT = "gfx/font6.json"


def load(spec_path, rom):
    spec = json.load(open(spec_path, encoding="utf-8"))
    tiles = bytearray(gfx.lz77_decompress(rom, int(spec["tiles"]["lz"], 16)))
    tmap = bytearray(gfx.lz77_decompress(rom, int(spec["map"]["lz"], 16)))
    return spec, tiles, tmap


def map_entry(tmap, w, tx, ty):
    return struct.unpack_from("<H", tmap, (ty * w + tx) * 2)[0]


def screen(tiles, tmap, w, h):
    """Palette-index image (mode 'P'-like list of rows) of the whole map."""
    img = [[0] * (w * 8) for _ in range(h * 8)]
    for ty in range(h):
        for tx in range(w):
            e = map_entry(tmap, w, tx, ty)
            t, hf, vf = e & 0x3FF, e & 0x400, e & 0x800
            for y in range(8):
                for x in range(8):
                    b = tiles[t * 32 + y * 4 + x // 2] if t * 32 + 32 <= len(tiles) else 0
                    c = (b >> 4) if x & 1 else b & 15
                    img[ty * 8 + (7 - y if vf else y)][tx * 8 + (7 - x if hf else x)] = c
    return img


def draw_text(img, text, x, y, ink, shadow, font):
    for ch in text:
        g = font.get(ch) or font["?"]
        for r, row in enumerate(g["rows"]):
            for i, p in enumerate(row):
                if p == "#":
                    img[y + r][x + i] = ink
                elif p == "o" and shadow is not None:
                    img[y + r][x + i] = shadow
        x += g["w"]
    return x


def text_width(text, font):
    return sum((font.get(c) or font["?"])["w"] for c in text)


def edit(spec, tiles, tmap):
    font = json.load(open(FONT, encoding="utf-8"))
    w, h = spec["map"]["width"], spec["map"]["height"]
    img = screen(tiles, tmap, w, h)
    orig = [row[:] for row in img]
    for e in spec["edits"]:
        x0, y0, x1, y1 = e["erase"]
        for y in range(y0, y1):
            for x in range(x0, x1):
                if img[y][x] in e["erase_colors"]:
                    img[y][x] = e["bg"]
        # parts: ["text", ...] or {"blit": [sx0, sy0, sx1, sy1]} (copy of the
        # original pixels, e.g. a button icon), laid out left to right
        if e.get("parts"):
            x = e["at"][0]
            if e.get("align") == "right":
                x = x1 - sum(text_width(p, font) if isinstance(p, str) else p["blit"][2] - p["blit"][0]
                             for p in e["parts"])
            for p in e["parts"]:
                if isinstance(p, str):
                    x = draw_text(img, p, x, e["at"][1], e["ink"], e.get("shadow"), font)
                else:
                    sx0, sy0, sx1, sy1 = p["blit"]
                    dy = p.get("dy", sy0)
                    for yy in range(sy1 - sy0):
                        for xx in range(sx1 - sx0):
                            c = orig[sy0 + yy][sx0 + xx]
                            if c != e["bg"]:
                                img[dy + yy][x + xx] = c
                    x += sx1 - sx0
        if e.get("text"):
            tx = e["at"][0]
            if e.get("align") == "center":
                tx = (x0 + x1 - text_width(e["text"], font)) // 2
            elif e.get("align") == "right":
                tx = x1 - text_width(e["text"], font)
            draw_text(img, e["text"], tx, e["at"][1], e["ink"], e.get("shadow"), font)
    # re-tile every 8x8 cell touched by an edit into new tiles
    cells = set()
    for e in spec["edits"]:
        x0, y0, x1, y1 = e["erase"]
        for ty in range(y0 // 8, (y1 + 7) // 8):
            for tx in range(x0 // 8, (x1 + 7) // 8):
                cells.add((tx, ty))
    bank = spec["pal_bank"]
    new_tiles = bytearray(tiles)
    seen = {}
    for tx, ty in sorted(cells):
        data = bytearray(32)
        for y in range(8):
            for x in range(8):
                c = img[ty * 8 + y][tx * 8 + x]
                data[y * 4 + x // 2] |= c << (4 * (x & 1))
        data = bytes(data)
        if data not in seen:
            seen[data] = len(new_tiles) // 32
            new_tiles += data
        struct.pack_into("<H", tmap, (ty * w + tx) * 2, seen[data] | (bank << 12))
    assert len(new_tiles) // 32 <= spec.get("max_tiles", 1024), "tileset overflows its VRAM char block"
    return img, bytes(new_tiles), bytes(tmap)


def apply(spec_path, rom):
    """-> list of (bytes, [ref offsets], original lz offset) to relocate."""
    spec = json.load(open(spec_path, encoding="utf-8"))
    if spec.get("kind") == "sheet":
        lz = int(spec["sheet"]["lz"], 16)
        data = edit_sheet(spec, gfx.lz77_decompress(rom, lz))
        refs = [int(r, 16) for r in spec["sheet"]["refs"]]
        for r in refs:
            assert struct.unpack_from("<I", rom, r)[0] == 0x08000000 + lz, f"{spec_path}: ref {r:X}"
        return [(gfx.lz77_compress(data), refs, lz)]
    spec, tiles, tmap = load(spec_path, rom)
    _, t2, m2 = edit(spec, tiles, tmap)
    out = []
    for key, data in (("tiles", t2), ("map", m2)):
        refs = [int(r, 16) for r in spec[key]["refs"]]
        lz = int(spec[key]["lz"], 16)
        for r in refs:
            assert struct.unpack_from("<I", rom, r)[0] == 0x08000000 + lz, f"{spec_path}: ref {r:X}"
        out.append((gfx.lz77_compress(data), refs, lz))
    return out


def to_png(img, pal_rgb, bank, path, scale=3):
    h, w = len(img), len(img[0])
    im = Image.new("RGB", (w, h))
    for y in range(h):
        for x in range(w):
            im.putpixel((x, y), pal_rgb[bank * 16 + img[y][x]])
    im.resize((w * scale, h * scale), Image.NEAREST).save(path)


def _pal(spec):
    raw = open(spec["preview_pal"], "rb").read()
    return [((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3)
            for c in struct.unpack("<%dH" % (len(raw) // 2), raw)]


def preview_sheet(spec, rom, path):
    pal = _pal(spec)
    sheet = gfx.lz77_decompress(rom, int(spec["sheet"]["lz"], 16))
    after = edit_sheet(spec, sheet)
    n = len(sheet) // 512
    im = Image.new("RGB", (n * 34, 66), (255, 0, 255))
    for row, data in enumerate((sheet, after)):
        for f in range(n):
            fr = sheet_frame(data, f)
            for y in range(32):
                for x in range(32):
                    if fr[y][x]:
                        im.putpixel((f * 34 + x, row * 34 + y), pal[256 + spec["pal_bank"] * 16 + fr[y][x]])
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(path)


# --- sprite sheets (button labels): frames of 4x4 tiles, 1D mapping --------

def sheet_frame(sheet, f, tw=4, th=4):
    img = [[0] * (tw * 8) for _ in range(th * 8)]
    for k in range(tw * th):
        t = f * tw * th + k
        for y in range(8):
            for x in range(8):
                b = sheet[t * 32 + y * 4 + x // 2]
                img[(k // tw) * 8 + y][(k % tw) * 8 + x] = (b >> 4) if x & 1 else b & 15
    return img


def put_frame(sheet, f, img, tw=4, th=4):
    for k in range(tw * th):
        t = f * tw * th + k
        for y in range(8):
            for x in range(8):
                c = img[(k // tw) * 8 + y][(k % tw) * 8 + x]
                i = t * 32 + y * 4 + x // 2
                sheet[i] = (sheet[i] & 0x0F) | (c << 4) if x & 1 else (sheet[i] & 0xF0) | c


def erase_face(img, rect, colors):
    """Replace label pixels with the face's own shading: a row whose other
    pixels are all one colour keeps it (bevel top/bottom); other rows take the
    most common colour of their column among those rows (vertical stripes),
    falling back to the face's overall most common colour."""
    from collections import Counter
    x0, y0, x1, y1 = rect
    bevel = set()
    for y in range(y0, y1):
        row = Counter(img[y][x] for x in range(x0, x1) if img[y][x] not in colors)
        if len(row) == 1 and sum(row.values()) >= 3:
            c = next(iter(row))
            bevel.add(y)
            for x in range(x0, x1):
                if img[y][x] in colors:
                    img[y][x] = c
    body = [y for y in range(y0, y1) if y not in bevel]
    overall = Counter(img[y][x] for y in body for x in range(x0, x1) if img[y][x] not in colors)
    for x in range(x0, x1):
        col = Counter(img[y][x] for y in body if img[y][x] not in colors)
        fill = (col or overall).most_common(1)[0][0]
        for y in body:
            if img[y][x] in colors:
                img[y][x] = fill


def draw_label(img, text, cx, top, ink, outline, font5, gap=1):
    w = len(text) * 5 + (len(text) - 1) * gap
    x = cx - w // 2
    inkpx = set()
    for ch in text:
        for r, row in enumerate(font5[ch]):
            for i, p in enumerate(row):
                if p == "#":
                    inkpx.add((x + i, top + r))
        x += 5 + gap
    for (px, py) in inkpx if outline is not None else ():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = (px + dx, py + dy)
                if q not in inkpx and 0 <= q[1] < len(img) and 0 <= q[0] < len(img[0]):
                    img[q[1]][q[0]] = outline
    for (px, py) in inkpx:
        img[py][px] = ink


def edit_sheet(spec, sheet):
    font5 = json.load(open("gfx/font5.json", encoding="utf-8"))
    sheet = bytearray(sheet)
    for fr in spec["frames"]:
        img = sheet_frame(sheet, fr["index"])
        erase_face(img, fr["erase"], fr["erase_colors"])
        x0, _, x1, _ = fr["erase"]
        draw_label(img, fr["label"], fr.get("cx", (x0 + x1) // 2), fr["top"], fr["ink"], fr.get("outline"), font5)
        put_frame(sheet, fr["index"], img)
    return bytes(sheet)


if __name__ == "__main__":
    rom = open(gfx.ROM, "rb").read()
    if json.load(open(sys.argv[2])).get("kind") == "sheet":
        preview_sheet(json.load(open(sys.argv[2])), rom, sys.argv[3])
        sys.exit()
    spec, tiles, tmap = load(sys.argv[2], rom)
    w, h = spec["map"]["width"], spec["map"]["height"]
    if sys.argv[1] == "cols":
        img = screen(tiles, tmap, w, h)
        y0, y1 = int(sys.argv[3]), int(sys.argv[4])
        bgs = {int(c) for c in sys.argv[5].split(",")} if len(sys.argv) > 5 else {0}
        cols = [x for x in range(w * 8) if any(img[y][x] not in bgs for y in range(y0, y1))]
        runs, s = [], None
        for i, x in enumerate(cols):
            if s is None:
                s = x
            if i + 1 == len(cols) or cols[i + 1] != x + 1:
                runs.append((s, x))
                s = None
        print(runs)
        ys = [y for y in range(y0, y1) if any(img[y][x] not in bgs for x in range(w * 8))]
        print("rows", ys[:1], ys[-1:])
    elif sys.argv[1] == "render":
        before = screen(tiles, tmap, w, h)
        after, _, _ = edit(spec, tiles, tmap)
        pal = _pal(spec)
        rows = len(before)
        both = before + [[0] * len(before[0])] * 4 + after
        to_png(both, pal, spec["pal_bank"], sys.argv[3])
        print("ok", rows)
