"""Playtest driver for the headless emulator (bridge on 127.0.0.1:8765).

    python3 scripts/play.py boot [ROM]          # start mgba-headless (background)
    python3 scripts/play.py stop
    python3 scripts/play.py load NAME           # saves/states/NAME.ss
    python3 scripts/play.py go "SEQ" [NAME]     # run SEQ, grid -> saves/shots/last.png,
                                                # optionally save state NAME
    python3 scripts/play.py where               # map, position, ASCII map around player
    python3 scripts/play.py shot [FILE]

SEQ tokens (space separated):
    A B Start Select L R        press once (then ~20 frames)
    U3 D1 L2 R4                 walk N tiles, closed loop on the RAM position
    tU tD tL tR                 turn/face without walking (tap)
    w60                         wait 60 frames (no screenshot)
    A*5                         repeat a token 5 times
Every token except waits takes a screenshot into the grid.

ASCII map legend: @ player, # blocked, . walkable, N object event (NPC),
W warp (door/stairs), ~ water-ish (collision 0 but surf metatile unknown: shown as .)
"""
import json
import os
import re
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from emu import Emu  # noqa: E402

STATES = "saves/states"
SHOTS = "saves/shots"
PIDFILE = "saves/.emu.pid"
SB1, MAPHDR, OBJ, VMAP, AVATAR = 0x03005008, 0x02036DFC, 0x02036E38, 0x03005040, 0x02037078
DIRS = {"U": "Up", "D": "Down", "L": "Left", "R": "Right"}
DELTA = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}


def u32(e, a):
    return struct.unpack("<I", e.read(a, 4))[0]


def pos(e):
    """Live player tile (the player object event; the save block copy is
    only refreshed on map changes) and the current map."""
    sb1 = u32(e, SB1)
    _, _, grp, num = struct.unpack("<hhbb", e.read(sb1, 6))
    oid = e.read(AVATAR + 5, 1)[0]
    x, y = struct.unpack("<hh", e.read(OBJ + 0x24 * oid + 0x10, 4))
    return x - 7, y - 7, grp, num


def boot(rom):
    rom = os.path.abspath(rom)
    lua = "utilities/mcp-mgba/lua"
    p = subprocess.Popen(["../../mgba/build/mgba-headless", "-l", "0", "--script", "bridge.lua", rom],
                         cwd=lua, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    open(PIDFILE, "w").write(str(p.pid))
    for _ in range(80):
        try:
            Emu().info()
            return
        except OSError:
            time.sleep(0.25)


def stop():
    try:
        os.kill(int(open(PIDFILE).read()), 15)
    except (OSError, ValueError):
        pass


def walk(e, d, n):
    x0, y0, _, _ = pos(e)
    dx, dy = DELTA[d]
    target = (x0 + dx * n, y0 + dy * n)
    stuck = 0
    while (pos(e)[:2]) != target and stuck < 3:
        before = pos(e)[:2]
        e.press(DIRS[d], hold=3, release=4)   # a tap starts one step (or turns)
        e.wait(14)                            # a walking step is 16 frames
        if pos(e)[:2] == before:
            stuck += 1
        else:
            stuck = 0
    e.wait(4)


def where(e):
    x, y, grp, num = pos(e)
    hdr = e.read(MAPHDR, 0x1C)
    events = struct.unpack_from("<I", hdr, 4)[0]
    W, H, mp = struct.unpack("<iiI", e.read(VMAP, 12))
    out = [f"map {grp}.{num}  pos ({x},{y})  layout {W - 15}x{H - 14}"]
    ev = e.read(events, 20)
    nobj, nwarp = ev[0], ev[1]
    warps = {}
    wp = struct.unpack_from("<I", ev, 8)[0]
    for i in range(nwarp):
        wx, wy, _, wid, mn, mg = struct.unpack("<hhBBBB", e.read(wp + 8 * i, 8))
        warps[(wx, wy)] = f"{mg}.{mn}"
    objs = set()
    blob = e.read(OBJ, 0x24 * 16)
    for i in range(16):
        o = blob[0x24 * i:0x24 * (i + 1)]
        if o[0] & 1 and o[8] != 0xFF:  # active, not the player (localId 0xFF)
            cx, cy = struct.unpack_from("<hh", o, 0x10)
            objs.add((cx - 7, cy - 7))
    R, C = 6, 9
    for yy in range(y - R, y + R + 1):
        row = ""
        for xx in range(x - C, x + C + 1):
            gx, gy = xx + 7, yy + 7
            if (xx, yy) == (x, y):
                ch = "@"
            elif (xx, yy) in objs:
                ch = "N"
            elif (xx, yy) in warps:
                ch = "W"
            elif 0 <= gx < W and 0 <= gy < H:
                blk = struct.unpack("<H", e.read(mp + 2 * (gx + W * gy), 2))[0]
                ch = "#" if blk & 0x0C00 else "."
            else:
                ch = " "
            row += ch
        out.append(f"{yy:4d} {row}")
    out.append("warps: " + ", ".join(f"({a},{b})->{m}" for (a, b), m in sorted(warps.items())))
    return "\n".join(out)


def go(e, seq, name=None):
    from PIL import Image
    os.makedirs(SHOTS, exist_ok=True)
    shots = []
    toks = []
    for t in seq.split():
        m = re.fullmatch(r"(.+)\*(\d+)", t)
        toks += [m.group(1)] * int(m.group(2)) if m else [t]
    for t in toks:
        if re.fullmatch(r"w\d+", t):
            e.wait(int(t[1:]))
            continue
        m = re.fullmatch(r"([UDLR])(\d+)", t)
        if m:
            walk(e, m.group(1), int(m.group(2)))
        elif re.fullmatch(r"t[UDLR]", t):
            e.press(DIRS[t[1]], hold=2, release=8)
            e.wait(4)
        else:
            e.press(t, hold=3, release=6)
            e.wait(20)
        p = f"{SHOTS}/_{len(shots)}.png"
        e.screenshot(os.path.abspath(p))
        shots.append(Image.open(p).convert("RGB"))
    if shots:
        cols = min(6, len(shots))
        g = Image.new("RGB", (240 * cols, 160 * ((len(shots) + cols - 1) // cols)))
        for k, im in enumerate(shots):
            g.paste(im, ((k % cols) * 240, (k // cols) * 160))
        g.save(f"{SHOTS}/last.png")
        shots[-1].resize((480, 320), Image.NEAREST).save(f"{SHOTS}/now.png")
    if name:
        os.makedirs(STATES, exist_ok=True)
        e.save_state(os.path.abspath(f"{STATES}/{name}.ss"))
        if shots:
            shots[-1].save(f"{STATES}/{name}.png")


def main():
    a = sys.argv[1:]
    cmd = a[0]
    if cmd == "boot":
        stop()
        boot(a[1] if len(a) > 1 else "build/Mercury_EN.gba")
        return
    if cmd == "stop":
        stop()
        return
    e = Emu()
    if cmd == "load":
        e.load_state(os.path.abspath(f"{STATES}/{a[1]}.ss"))
        e.wait(5)
    elif cmd == "go":
        go(e, a[1], a[2] if len(a) > 2 else None)
    elif cmd == "shot":
        e.screenshot(os.path.abspath(a[1] if len(a) > 1 else f"{SHOTS}/now.png"))
        return
    elif cmd == "where":
        pass
    try:
        print(where(e))
    except Exception as ex:  # not on the overworld
        print("where: n/a", ex)


if __name__ == "__main__":
    main()
