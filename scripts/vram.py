"""Dump the GBA video state from the running emulator (see emu.py).

    python3 scripts/vram.py OUTDIR

Writes OUTDIR/state.json (DISPCNT, BGxCNT, scroll), OUTDIR/vram.bin,
pal.bin, oam.bin, and renders each enabled text-mode BG layer on its own
(OUTDIR/bg<N>.png, 256x256 map at 1x) plus every OAM sprite
(OUTDIR/obj.png). Used to find which tiles hold image text (logo, buttons)
so they can be located in the ROM and redrawn.
"""
import json
import os
import struct
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from emu import Emu  # noqa: E402


def bgr555(c):
    return ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3)


def tile_pixels(vram, char_base, idx, bpp8):
    """64 palette indices of one 8x8 tile."""
    size = 64 if bpp8 else 32
    off = char_base + idx * size
    raw = vram[off:off + size]
    if bpp8:
        return list(raw) + [0] * (64 - len(raw))
    out = []
    for b in raw:
        out += [b & 15, b >> 4]
    return out + [0] * (64 - len(out))


def render_bg(vram, pal, cnt):
    char_base = ((cnt >> 2) & 3) * 0x4000
    screen_base = ((cnt >> 8) & 31) * 0x800
    bpp8 = bool(cnt & 0x80)
    size = (cnt >> 14) & 3
    w, h = [(256, 256), (512, 256), (256, 512), (512, 512)][size]
    im = Image.new("RGB", (w, h))
    px = im.load()
    for ty in range(h // 8):
        for tx in range(w // 8):
            # 32x32-tile screenblocks, laid out left-right then top-bottom
            sb = (tx // 32) + (ty // 32) * (w // 256)
            e = struct.unpack_from("<H", vram, screen_base + sb * 0x800 + ((ty % 32) * 32 + tx % 32) * 2)[0]
            idx, hf, vf, pb = e & 0x3FF, e & 0x400, e & 0x800, e >> 12
            pix = tile_pixels(vram, char_base, idx, bpp8)
            for y in range(8):
                for x in range(8):
                    c = pix[y * 8 + x]
                    if c == 0:
                        continue
                    col = pal[c] if bpp8 else pal[pb * 16 + c]
                    px[tx * 8 + (7 - x if hf else x), ty * 8 + (7 - y if vf else y)] = col
    return im


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    e = Emu()
    io = e.read(0x04000000, 0x60)
    vram = e.read(0x06000000, 0x18000)
    palb = e.read(0x05000000, 0x400)
    oam = e.read(0x07000000, 0x400)
    for name, b in (("vram", vram), ("pal", palb), ("oam", oam), ("io", io)):
        open(f"{out}/{name}.bin", "wb").write(b)
    pal = [bgr555(struct.unpack_from("<H", palb, i * 2)[0]) for i in range(512)]
    dispcnt = struct.unpack_from("<H", io, 0)[0]
    state = {"dispcnt": hex(dispcnt), "mode": dispcnt & 7, "bg": {}}
    for n in range(4):
        cnt = struct.unpack_from("<H", io, 8 + n * 2)[0]
        hofs, vofs = struct.unpack_from("<HH", io, 0x10 + n * 4)
        on = bool(dispcnt & (0x100 << n))
        state["bg"][n] = {"on": on, "cnt": hex(cnt), "prio": cnt & 3,
                          "char_base": hex(((cnt >> 2) & 3) * 0x4000),
                          "screen_base": hex(((cnt >> 8) & 31) * 0x800),
                          "8bpp": bool(cnt & 0x80), "hofs": hofs & 511, "vofs": vofs & 511}
        if on and (dispcnt & 7) == 0:
            render_bg(vram, pal, cnt).save(f"{out}/bg{n}.png")
    # sprites: draw each at its screen position (1D or 2D mapping)
    obj = Image.new("RGB", (512, 256))
    opx = obj.load()
    map1d = bool(dispcnt & 0x40)
    shapes = {(0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
              (1, 0): (16, 8), (1, 1): (32, 8), (1, 2): (32, 16), (1, 3): (64, 32),
              (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64)}
    sprites = []
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<HHH", oam, i * 8)
        if (a0 >> 8) & 3 == 2:  # disabled
            continue
        shape, sz = a0 >> 14, a1 >> 14
        if (shape, sz) not in shapes:
            continue
        w, h = shapes[(shape, sz)]
        x, y = a1 & 511, a0 & 255
        bpp8 = bool(a0 & 0x2000)
        tile, pb = a2 & 0x3FF, a2 >> 12
        sprites.append({"i": i, "x": x, "y": y, "w": w, "h": h, "tile": tile, "pal": pb, "8bpp": bpp8})
        for ty in range(h // 8):
            for tx in range(w // 8):
                if map1d:
                    t = tile + (ty * (w // 8) + tx) * (2 if bpp8 else 1)
                else:
                    t = tile + ty * 32 + tx * (2 if bpp8 else 1)
                pix = tile_pixels(vram, 0x10000, t, bpp8)
                for yy in range(8):
                    for xx in range(8):
                        c = pix[yy * 8 + xx]
                        if c:
                            col = pal[256 + c] if bpp8 else pal[256 + pb * 16 + c]
                            X, Y = (x + tx * 8 + xx) % 512, (y + ty * 8 + yy) % 256
                            opx[X, Y] = col
    obj.save(f"{out}/obj.png")
    state["sprites"] = sprites
    json.dump(state, open(f"{out}/state.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in state.items() if k != "sprites"}, indent=1), len(sprites), "sprites")


if __name__ == "__main__":
    main()
