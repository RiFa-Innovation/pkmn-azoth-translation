#!/usr/bin/env python3
"""Partner Patrol sweep: warp onto grass on maps that have wild encounters, wait for visible Pokemon, run a patrol, check the game ends clean.

    python3 scripts/patrol_sweep.py ROM.gba SAVE.sav [3.80 1.39 ...]      # scratch copies are made; the real files are never touched

Boots a scratch copy of a River build with a late-game save in the headless emulator (needs utilities/mgba built, see EMULATOR.md). For each map:
warp to a walkable tile, find pairs of adjacent encounter-type-1 (land) tiles from the loaded tileset attributes, warp onto one, step between the two until a
visible Pokemon appears, boost the partner's stats (so fights are won), open Quick Catch, press SELECT, and wait for the patrol to end. A map is clean when: the
patrol ended, no patrol task is left, the map is unchanged, the walker (local id 0xFE) is present, the field controls come back, and the player can move.
The map list defaults to a spread of the maps that have land encounters in the live wild table (0x1E468B0): group 3 routes, group 1, 48, 53, 55 caves.
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(__file__))
from emu import Emu  # noqa: E402
import play  # noqa: E402
from species_peek import CTX, SCRIPT  # noqa: E402

DEFAULT = ["3.42", "3.46", "3.80", "3.82", "3.83", "3.84", "3.85", "3.86", "3.88", "3.90", "3.94", "3.97", "3.101", "3.106", "1.39", "1.50", "1.97",
           "1.106", "1.111", "1.124", "55.17", "55.22", "55.26", "53.4", "53.9", "48.3"]
u16 = lambda b, o=0: struct.unpack_from("<H", b, o)[0]


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    rom, sav = sys.argv[1], sys.argv[2]
    maps = [tuple(int(x) for x in m.split(".")) for m in (sys.argv[3:] or DEFAULT)]
    scratch = tempfile.mkdtemp(prefix="patrol-sweep-")
    shutil.copy(rom, f"{scratch}/game.gba")
    shutil.copy(sav, f"{scratch}/game.sav")
    os.environ["RHT_LOAD_SAVE"] = "1"
    play.stop()
    time.sleep(1)
    play.boot(f"{scratch}/game.gba")
    time.sleep(6)
    e = Emu()
    tap = lambda *b, w=30, hold=4: (e.press(*b, hold=hold, release=8), e.wait(w))
    e.wait(200)
    for _ in range(5):
        tap("A", w=60)
    e.wait(120)

    def run(code):
        e.write(SCRIPT, code)
        e.write(CTX + 8, struct.pack("<I", SCRIPT))
        e.write(CTX, b"\x00\x01")
        e.write(0x03000EA8, b"\x00")
        e.wait(60)

    free = lambda: e.read(0x03000F9C, 1)[0] == 0
    run(bytes([0x44]) + struct.pack("<HH", 4, 20) + bytes([0x02]))      # additem Poke Ball x20 (Quick Catch needs balls)

    def clear():
        for k in range(16):
            if free():
                return True
            tap("B", w=60)
        return free()

    def pos(i):
        return struct.unpack_from("<hh", e.read(0x02036E38 + 36 * i, 0x24), 0x10)

    def visible():
        r = []
        for i in range(16):
            d = e.read(0x02036E38 + 36 * i, 0x24)
            if struct.unpack_from("<I", d, 0)[0] & 1 and 0xE0 <= d[8] <= 0xE2:
                r.append(i)
        return r

    def mapnow():
        sb = struct.unpack("<I", e.read(0x03005008, 4))[0]
        return struct.unpack("<bb", e.read(sb + 4, 2))

    def warp(g, n, x, y):
        run(bytes([0x39, g, n, 0xFF]) + x.to_bytes(2, "little") + y.to_bytes(2, "little") + bytes([0x02]))
        e.wait(220)

    def grass_pairs():
        W, H, b = play.grid(e)
        lay = struct.unpack("<I", e.read(0x02036DFC, 4))[0]
        pri, sec = struct.unpack("<II", e.read(lay + 16, 8))
        enc = {}
        for base, ts, n in ((0, pri, 640), (640, sec, 384)):
            raw = e.read(struct.unpack("<I", e.read(ts + 20, 4))[0], n * 4)
            for i in range(n):
                enc[base + i] = (struct.unpack_from("<I", raw, 4 * i)[0] >> 24) & 7     # METATILE_ATTRIBUTE_ENCOUNTER_TYPE
        ok = lambda X, Y: 0 <= X + 7 < W and 0 <= Y + 7 < H and enc.get(b[(X + 7) + W * (Y + 7)] & 0x3FF) == 1 and not (b[(X + 7) + W * (Y + 7)] & 0x0C00)
        return [(X, Y) for Y in range(H - 14) for X in range(W - 14) if ok(X, Y) and ok(X + 1, Y)], (W - 14, H - 14)

    def state():
        pp = e.read(0x02022200, 48)                                          # struct Patrol (scripts/native/patrol.c)
        return {"active": pp[0], "kills": pp[22], "reason": pp[21], "steps": u16(pp, 14)}

    results = {}
    for g, n in maps:
        key = f"{g}.{n}"
        try:
            clear()
            warp(g, n, 5, 5)
            if mapnow() != (g, n):
                results[key] = "warp failed"
                print(key, results[key], flush=True)
                continue
            pairs, size = grass_pairs()
            if not pairs:
                results[key] = f"no grass pair found (map {size[0]}x{size[1]})"
                print(key, results[key], flush=True)
                continue
            spawned = False
            for gx, gy in (pairs[len(pairs) // 2], pairs[0]):
                clear()
                warp(g, n, gx, gy)
                for step in range(80):
                    tap("Right" if step % 2 == 0 else "Left", w=12, hold=14)
                    if not free():
                        clear()
                    if visible():
                        spawned = True
                        break
                if spawned:
                    break
            if not spawned:
                results[key] = f"grass ({len(pairs)} pairs) but no visible Pokemon in 160 steps"
                print(key, results[key], flush=True)
                continue
            clear()
            e.write(0x02024284 + 0x56, struct.pack("<H", 20))
            for off in (0x5A, 0x5C, 0x60, 0x62):
                e.write(0x02024284 + off, struct.pack("<H", 70))
            tap("L", w=60)
            if e.read(0x0203B743, 1)[0] != 1:
                results[key] = "spawned but Quick Catch did not open"
                print(key, results[key], flush=True)
                continue
            tap("Select", w=2, hold=8)
            for i in range(600):
                e.wait(15)
                if state()["active"] == 0 and i > 3:
                    break
            ended = state()["active"] == 0
            back = False
            for k in range(80):
                if free():
                    back = True
                    break
                tap("A" if k % 2 == 0 else "B", w=50)
            tasks = [i for i in range(16) if e.read(0x03005090 + 40 * i + 4, 1)[0] and (struct.unpack("<I", e.read(0x03005090 + 40 * i, 4))[0] >> 20) == 0x082]
            p0 = pos(0)
            for k in ("Down", "Up", "Left"):
                tap(k, w=30, hold=14)
            st = state()
            results[key] = dict(patrol_ended=ended, patrol_task_left=bool(tasks), same_map=mapnow() == (g, n), walker_present=e.read(0x02036E5C + 8, 1)[0] == 0xFE,
                                controls_back=back, player_moves=pos(0) != p0, kills=st["kills"], reason=st["reason"], steps=st["steps"])
        except Exception as ex:      # noqa: BLE001
            results[key] = f"exception: {ex}"
        print(key, results[key], flush=True)
    full = {k: v for k, v in results.items() if isinstance(v, dict)}
    clean = [k for k, v in full.items() if v["patrol_ended"] and not v["patrol_task_left"] and v["same_map"] and v["walker_present"] and v["controls_back"] and v["player_moves"]]
    print(f"\nmaps tried {len(results)}, full patrol runs {len(full)}, all checks clean {len(clean)}")
    play.stop()
    sys.exit(0 if len(clean) == len(full) and full else 1)


if __name__ == "__main__":
    main()
