"""Title logo: 口袋妖怪 / Pokémon / 水银  ->  POKéMON / AZOTH (+ the original 水银).

The logo is BG0, 8bpp, raw (not LZ77): tiles at 0xF00FC0 (162 tiles),
map at 0xF03840 (32x20), palette at 0xF03D40. The title code at 0xF0052A
copies 0xDF<<6 bytes (223 tiles) from the literal at 0xF006BC, so a redraw
may use up to 223 tiles if the tiles are relocated and that literal repointed.
Only the 64 palette entries the logo already uses are drawn with (the other
BG layers share palette RAM).

    python3 scripts/logo.py OUT.png      # preview (original above, new below)
Used by insert.py via build(src_rom) -> (tiles, map).
"""
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

TILES, MAP, PAL, LIT_TILES = 0xF00FC0, 0xF03840, 0xF03D40, 0xF006BC
MAX_TILES = 0xDF
AZOTH_X = 99  # centre x of the AZOTH wordmark
W, H = 240, 80  # logo occupies map rows 0..9

FONT_BIG = "/System/Library/Fonts/Supplemental/Impact.ttf"
FONT_SUB = "/System/Library/Fonts/Supplemental/Arial Black.ttf"

# palette indices (see the dump in PROCESS.md notes)
ICE = [48, 42, 31, 44, 41, 40, 39, 32, 36]   # light -> dark letter fill
NAVY, DARK, WHITE = 52, 12, 57
SUB_FILL = [41, 40, 39, 32]
BLUES = set(range(29, 56)) - {30}            # letter/ice colours (30 = red)


def palette(rom):
    return [((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3)
            for c in struct.unpack("<256H", rom[PAL:PAL + 512])]


def original(rom):
    img = [[0] * W for _ in range(H)]
    for ty in range(H // 8):
        for tx in range(W // 8):
            e = struct.unpack_from("<H", rom, MAP + (ty * 32 + tx) * 2)[0]
            t = e & 0x3FF
            for y in range(8):
                for x in range(8):
                    img[ty * 8 + y][tx * 8 + x] = rom[TILES + t * 64 + y * 8 + x]
    return img


def mask_text(text, font_path, size, shear=0.0, spacing=0):
    font = ImageFont.truetype(font_path, size)
    widths = [font.getbbox(c)[2] - font.getbbox(c)[0] for c in text]
    total = sum(widths) + spacing * (len(text) - 1) + 8
    im = Image.new("L", (total + 16, size * 2), 0)
    d = ImageDraw.Draw(im)
    x = 4
    for c, w in zip(text, widths):
        d.text((x - font.getbbox(c)[0], 0), c, font=font, fill=255)
        x += w + spacing
    if shear:
        im = im.transform(im.size, Image.AFFINE, (1, shear, -shear * im.size[1] / 2, 0, 1, 0), Image.NEAREST)
    im = im.point(lambda v: 255 if v >= 128 else 0)
    bb = im.getbbox()
    im = im.crop(bb)
    return [[im.getpixel((x, y)) > 0 for x in range(im.size[0])] for y in range(im.size[1])]


def dilate(m, r=1):
    h, w = len(m), len(m[0])
    out = [[False] * (w + 2 * r) for _ in range(h + 2 * r)]
    for y in range(h):
        for x in range(w):
            if m[y][x]:
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        out[y + r + dy][x + r + dx] = True
    return out


def stamp(img, m, x0, y0, color_fn):
    for y, row in enumerate(m):
        for x, on in enumerate(row):
            if on and 0 <= y0 + y < H and 0 <= x0 + x < W:
                img[y0 + y][x0 + x] = color_fn(x, y, len(m))


def inpaint(img, box, bad):
    """Fill 'bad' pixels in box from the nearest good pixel in the same row
    (left/right alternately), keeping the plate's grey texture."""
    x0, y0, x1, y1 = box
    src = [row[:] for row in img]
    for y in range(y0, y1):
        for x in range(x0, x1):
            if src[y][x] in bad:
                for d in range(1, 40):
                    for xx in (x - d, x + d):
                        if x0 - 8 <= xx < x1 + 8 and 0 <= xx < W and src[y][xx] not in bad and src[y][xx] != 0:
                            img[y][x] = src[y][xx]
                            break
                    else:
                        continue
                    break


def build_image(rom):
    img = original(rom)
    # 1. erase 口袋妖怪 and its Poké Ball (keep the plate and ®)
    bad = BLUES | {30, 21, 22, 24, 56, 57, 15, 60, 63, 62}
    inpaint(img, (34, 12, 164, 48), bad)
    # 1b. erase the small "Pokémon" wordmark (the big title already says it):
    #     each row is refilled from the plate pixels just outside the band
    wx0, wy0, wx1, wy1 = 45, 47, 141, 59
    for y in range(wy0, wy1):
        left, right = img[y][wx0 - 1], img[y][wx1]
        for x in range(wx0, wx1):
            img[y][x] = left if x < (wx0 + wx1) // 2 else right
    # 2. 水银 stays: it is the hack's own title and sits beside AZOTH
    # 3. big POKéMON on the plate
    big = mask_text("POKéMON", FONT_BIG, 29, spacing=1)
    bw, bh = len(big[0]), len(big)
    bx, by = 99 - bw // 2, 31 - bh // 2
    stamp(img, dilate(big, 2), bx - 2, by - 2, lambda x, y, h: DARK)
    stamp(img, dilate(big, 1), bx - 1, by - 1, lambda x, y, h: NAVY)
    stamp(img, big, bx, by, lambda x, y, h: ICE[min(len(ICE) - 1, y * len(ICE) // h)])
    # top highlight line on each letter
    for y in range(bh):
        for x in range(bw):
            if big[y][x] and (y == 0 or not big[y - 1][x]):
                img[by + y][bx + x] = WHITE
    # 4. AZOTH in the wordmark's place under the title, italic, white rim +
    #    navy outer like 水银 (left of it)
    sub = mask_text("AZOTH", FONT_SUB, 15, shear=0.25, spacing=1)
    sw, sh = len(sub[0]), len(sub)
    sx, sy = AZOTH_X - sw // 2, 49
    stamp(img, dilate(sub, 2), sx - 2, sy - 2, lambda x, y, h: NAVY)
    stamp(img, dilate(sub, 1), sx - 1, sy - 1, lambda x, y, h: WHITE)
    stamp(img, sub, sx, sy, lambda x, y, h: SUB_FILL[min(len(SUB_FILL) - 1, y * len(SUB_FILL) // h)])
    return img


def build(rom):
    """-> (tile bytes, map bytes) for the 32x20 map (rows below H unchanged)."""
    img = build_image(rom)
    tmap = bytearray(rom[MAP:MAP + 0x500])
    tiles, index = bytearray(), {}
    for ty in range(20):
        for tx in range(32):
            if ty < H // 8 and tx < W // 8:
                data = bytes(img[ty * 8 + y][tx * 8 + x] for y in range(8) for x in range(8))
            else:
                t = struct.unpack_from("<H", tmap, (ty * 32 + tx) * 2)[0] & 0x3FF
                data = rom[TILES + t * 64:TILES + t * 64 + 64]
            if data not in index:
                index[data] = len(tiles) // 64
                tiles += data
            struct.pack_into("<H", tmap, (ty * 32 + tx) * 2, index[data])
    assert len(tiles) // 64 <= MAX_TILES, f"logo needs {len(tiles) // 64} tiles > {MAX_TILES}"
    return bytes(tiles), bytes(tmap)


def preview(rom, path):
    pal = palette(rom)
    a, b = original(rom), build_image(rom)
    im = Image.new("RGB", (W, H * 2 + 4), (60, 60, 90))
    for y in range(H):
        for x in range(W):
            im.putpixel((x, y), pal[a[y][x]] if a[y][x] else (30, 30, 60))
            im.putpixel((x, H + 4 + y), pal[b[y][x]] if b[y][x] else (30, 30, 60))
    im.resize((W * 4, (H * 2 + 4) * 4), Image.NEAREST).save(path)
    print("tiles", len(build(rom)[0]) // 64)


if __name__ == "__main__":
    preview(open("roms/Pokemon Mercury 1.3.3 (patched).gba", "rb").read(), sys.argv[1])
