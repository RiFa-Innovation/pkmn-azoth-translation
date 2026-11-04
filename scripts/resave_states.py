#!/usr/bin/env python3
"""Re-save every River clip-recipe state (docs/CLIP_RECIPES.md) on the current River build.

    python3 scripts/resave_states.py SAVE.sav [ROM]      # ROM defaults to build/editions/Pokemon River Azoth (Chapter 2 + Frontier).gba

States only load on the build that made them, so run this once per River release (after `build_editions.py`), then re-record the clips
(`clip.py`, see "Recipes and states" in CLAUDE.md) and look at them. SAVE is a Champion save (the reporter saves in `saves/` work); a scratch
copy is booted, the real save is never touched. Writes saves/states/river/NAME.{ss,png} (gitignored).

The steps mirror how the states were first made by hand: overworld states are New Bark Town (3.66) at (12,11); the menu states are opened
with the Start-menu cursor where it lands after a fresh load; the Mart is the game's own `pokemart` script on a list in EWRAM;
the patrol state is the `patrol_sweep.py` spawn loop (grass pair on 3.80, three wild Pokemon in range, Ultra Balls, full HP, flags
0x13B3 / 0x13B1 set and Shiny Boost 0x13A8 cleared).
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import mapdrive  # noqa: E402
import play  # noqa: E402

ROM = "build/editions/Pokemon River Azoth (Chapter 2 + Frontier).gba"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sav = sys.argv[1]
    rom = sys.argv[2] if len(sys.argv) > 2 else ROM
    e, _ = mapdrive.start(rom, sav)
    out = os.path.abspath("saves/states/river")
    os.makedirs(out, exist_ok=True)

    def save(name):
        e.save_state(f"{out}/{name}.ss")
        e.screenshot(f"{out}/{name}.png")
        print("saved", name, play.pos(e), flush=True)

    def tap(b, w=30, hold=4):
        e.press(b, hold=hold, release=8)
        e.wait(w)

    # overworld states
    mapdrive.warp(e, 3, 66, 12, 11)
    e.wait(60)
    for n in ("overworld", "quest-menu-start", "card-start", "cheats-start", "mombank-start", "newbark-lab-door"):
        save(n)
    mapdrive.warp(e, 58, 0, 6, 12)
    e.wait(60)
    save("route28-edge")
    mapdrive.warp(e, 43, 6, 5, 13)
    e.wait(60)
    save("ch2-lab-champion")
    mapdrive.warp(e, 3, 66, 12, 11)
    e.wait(60)

    # Bag on Medicine; then Key Items with Key Stone highlighted (10 entries down from Berry Pouch)
    tap("Start", 40)
    tap("Down")
    tap("A", 80)
    save("bag-start")
    for _ in range(8):
        tap("R", 40)
    for _ in range(10):
        tap("Down", 25)
    e.wait(20)
    save("mega-menu-start")
    for _ in range(3):
        tap("B", 45)

    # Pokedex list (Start menu cursor is on the Bag after leaving it: Up twice)
    tap("Start", 40)
    tap("Up", 25)
    tap("Up", 25)
    tap("A", 100)
    save("dex-start")
    for _ in range(4):
        tap("B", 60)

    # Poke Mart buy menu, made with the game's own pokemart script
    items = [4, 13, 14, 22, 17, 18, 0]
    e.write(0x0203FE00, b"".join(struct.pack("<H", i) for i in items))
    mapdrive.run_script(e, bytes([0x86]) + struct.pack("<I", 0x0203FE00) + bytes([0x02]))
    e.wait(120)
    save("mart-start")
    tap("B", 60)
    tap("B", 60)

    # Frontier reception counter, then the 4-Pokemon picker
    mapdrive.warp(e, 31, 3, 15, 5)
    e.wait(60)
    e.press("Up", hold=3)
    e.wait(30)
    save("frontier-start")
    e.wait(30)
    for _ in range(24):
        e.press("A", hold=4, release=8)
        e.wait(20)
    e.wait(150)
    for _ in range(6):
        e.press("A", hold=4, release=8)
        e.wait(40)
    e.wait(150)
    save("frontier-picker")
    for _ in range(4):
        tap("B", 50)

    # Mt. Silver 1F, south-east corner of the floor (the border below and beside the map is what #195 was about)
    mapdrive.warp(e, 58, 1, 30, 20)
    e.wait(60)
    save("mtsilver-edge")

    # Partner Patrol: Ultra Balls, flags, full HP, then step on grass until three wild Pokemon are visible
    pairs = grass_pairs_on(e, 3, 80)
    mapdrive.run_script(e, bytes([0x44]) + struct.pack("<HH", 2, 30) + bytes([0x02]))
    e.wait(60)
    for f in (0x13B3, 0x13B1):
        mapdrive.set_flag(e, f)
    mapdrive.run_script(e, bytes([0x2A]) + struct.pack("<H", 0x13A8) + bytes([0x02]))
    e.wait(20)
    for i in range(6):
        b = 0x02024284 + 100 * i
        e.write(b + 0x56, e.read(b + 0x58, 2))

    def visible():
        n = 0
        for i in range(16):
            d = e.read(0x02036E38 + 36 * i, 36)
            if struct.unpack_from("<I", d, 0)[0] & 1 and 0xE0 <= d[8] <= 0xE2:
                n += 1
        return n

    spawned = False
    for gx, gy in (pairs[len(pairs) // 2], pairs[0], pairs[-1]):
        mapdrive.warp(e, 3, 80, gx, gy, wait=200)
        for step in range(100):
            tap("Right" if step % 2 == 0 else "Left", 12, 14)
            if visible() >= 3:
                spawned = True
                break
        if spawned:
            break
    if not spawned:
        sys.exit("patrol: no three visible wild Pokemon; run again")
    e.wait(30)
    save("patrol-start")
    play.stop()
    print("done: now re-record the clips and look at them (CLAUDE.md, recipes)")


def grass_pairs_on(e, g, n):
    """Warp to (g, n) and return pairs of adjacent land-encounter tiles (the patrol_sweep.py rule)."""
    mapdrive.warp(e, g, n, 5, 5, wait=200)
    W, H, b = play.grid(e)
    lay = struct.unpack("<I", e.read(0x02036DFC, 4))[0]
    pri, sec = struct.unpack("<II", e.read(lay + 16, 8))
    enc = {}
    for base, ts, cnt in ((0, pri, 640), (640, sec, 384)):
        raw = e.read(struct.unpack("<I", e.read(ts + 20, 4))[0], cnt * 4)
        for i in range(cnt):
            enc[base + i] = (struct.unpack_from("<I", raw, 4 * i)[0] >> 24) & 7
    ok = lambda X, Y: 0 <= X + 7 < W and 0 <= Y + 7 < H and enc.get(b[(X + 7) + W * (Y + 7)] & 0x3FF) == 1 and not (b[(X + 7) + W * (Y + 7)] & 0x0C00)
    return [(X, Y) for Y in range(H - 14) for X in range(W - 14) if ok(X, Y) and ok(X + 1, Y)]


if __name__ == "__main__":
    main()
