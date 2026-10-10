"""Redraw a text-only sprite (e.g. the 咕咚!! sound-effect picture, entry 13
of the hack's 64x64 picture table at 0x1DE5A08): clear it and draw English
in FireRed's normal font, optionally scaled, then LZ77 + relocate.

Spec (gfx/spr_*.json): {"ref": pointer slot of the LZ77 sheet, "w", "h",
"text", "x", "y", "scale", "ink", "shadow"} (4bpp, 1D tile order).

    python3 scripts/sprtext.py render gfx/spr_thud.json OUT.png
Used by insert.py via apply(spec_path, src_rom) -> (lz_bytes, refs).
"""
import json
import struct
import sys

from PIL import Image

sys.path.insert(0, __import__("os").path.dirname(__file__))
import gfx  # noqa: E402
import maptext  # noqa: E402


def build(spec, rom):
    ref = int(spec["ref"], 16)
    src = struct.unpack_from("<I", rom, ref)[0] - 0x08000000
    old = gfx.lz77_decompress(rom, src)
    w, h, k = spec["w"], spec["h"], spec.get("scale", 1)
    small = [[0] * (w // k + 16) for _ in range(h // k + 16)]
    maptext.draw(small, spec["text"], 0, 0, spec["ink"], spec.get("shadow"), maptext.font())
    img = [[0] * w for _ in range(h)]
    for y in range(h // k):
        for x in range(w // k):
            c = small[y][x]
            if c:
                for dy in range(k):
                    for dx in range(k):
                        X, Y = spec["x"] + x * k + dx, spec["y"] + y * k + dy
                        if 0 <= X < w and 0 <= Y < h:
                            img[Y][X] = c
    out = bytearray(len(old))
    tw = w // 8
    for ty in range(h // 8):
        for tx in range(tw):
            t = (ty * tw + tx) * 32
            for y in range(8):
                for x in range(8):
                    c = img[ty * 8 + y][tx * 8 + x]
                    out[t + y * 4 + x // 2] |= c << 4 if x & 1 else c
    return old, bytes(out), img, ref


def apply(spec_path, rom):
    spec = json.load(open(spec_path, encoding="utf-8"))
    _, new, _, ref = build(spec, rom)
    return gfx.lz77_compress(new), [ref]


def render(spec_path, out):
    rom = open("roms/Pokemon Mercury 1.3.3 (patched).gba", "rb").read()
    spec = json.load(open(spec_path, encoding="utf-8"))
    old, new, _, _ = build(spec, rom)
    w, h = spec["w"], spec["h"]
    pal = {0: (40, 40, 80), 1: (200, 200, 200), 2: (60, 60, 60)}
    im = Image.new("RGB", (w * 2 + 4, h), (0, 0, 0))
    for n, data in enumerate((old, new)):
        for ty in range(h // 8):
            for tx in range(w // 8):
                t = (ty * (w // 8) + tx) * 32
                for y in range(8):
                    for x in range(8):
                        b = data[t + y * 4 + x // 2]
                        c = (b >> 4) if x & 1 else b & 15
                        im.putpixel((n * (w + 4) + tx * 8 + x, ty * 8 + y), pal.get(c, (255, 0, 0)))
    im.resize((im.width * 4, im.height * 4), Image.NEAREST).save(out)


if __name__ == "__main__" and sys.argv[1] == "render":
    render(sys.argv[2], sys.argv[3])
