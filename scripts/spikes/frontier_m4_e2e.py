"""M4 end-to-end: picks -> fr_enter (Lv 50) -> fr_gen_opponent (from the packed set table) -> fr_start_battle -> a real fight.

    python3 scripts/spikes/frontier_m4_e2e.py "saves/gets_frozen_after fight_and_convo/Azoth.sav" [--n 1] [--double] [--seed 12345] [--play]
    python3 scripts/spikes/frontier_m4_e2e.py SAVE --survey      # opponent teams for several battle numbers, no fights

Run from the main checkout. Scratch ROM = the current build with (a) build/frontier/sets.bin written into a free 0xFF run, (b) two shell trainer slots
(459 singles, 460 doubles) whose party pointer is the RAM block 0x02022400, (c) the first entry of the orphaned Battle Tower speech table pointing its
defeat/lose words at RAM text buffers. The natives are linked in EWRAM at 0x0203EC00 for the test (M5 links them into ROM).
"""
import argparse
import os
import re
import shutil
import struct
import sys
import tempfile

MAIN = "/Users/river/Projects/rht"
RIVER = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{MAIN}/scripts")
sys.path.insert(0, f"{RIVER}/scripts")
import play  # noqa: E402
from emu import Emu  # noqa: E402
import frontier_native as fn  # noqa: E402
import mercury_text as mt  # noqa: E402

BASE, SCRIPT = 0x0203EC00, 0x0203FF00
CTX, RUNNING, CB2 = 0x03000EB0, 0x03000EA8, 0x030030F4
SPV, V8 = 0x020370B8, 0x020370C8
PARTY, COUNT = 0x02024284, 0x02024029
ENEMY = 0x0202402C
BLOCK, TEXT_BUF = 0x02022400, 0x02022600
TRAINER_TABLE = 0x23EACC - 4
SHELLS = {0: 459, 1: 460}
SPEECH_ENTRY = 0x1DEC3A0
OFF = {n: i * fn.ENTRY_STRIDE for i, n in enumerate(fn.ENTRIES)}


def enc_name(s):
    t = {c: 0xBB + i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
    t.update({c: 0xD5 + i for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")})
    return bytes(t.get(c, 0) for c in s) + b"\xff"


def free_run(rom, size):
    for m in re.finditer(rb"\xff{%d,}" % (size + 0x400), bytes(rom[0x400000:])):
        return 0x400000 + m.start() + 0x200
    raise RuntimeError("no free run")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sav")
    ap.add_argument("--rom", default=os.environ.get("ROM", f"{MAIN}/build/Mercury_EN.gba"))
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--double", action="store_true")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--play", action="store_true")
    ap.add_argument("--survey", action="store_true")
    ap.add_argument("--out", default=os.environ.get("OUT", "/tmp"))
    a = ap.parse_args()

    sets = open(f"{RIVER}/build/frontier/sets.bin", "rb").read()
    rom = bytearray(open(a.rom, "rb").read())
    at = free_run(rom, len(sets))
    rom[at:at + len(sets)] = sets
    blob, _ = fn.build(BASE, f"{RIVER}/build/frontier/native.bin", sets=0x08000000 + at)
    for dbl, tid in SHELLS.items():
        n = 4 if dbl else 3
        ent = struct.pack("<BBBB", 3, 9, 0x0A, 30 + dbl) + enc_name("Shell" + str(dbl + 1)).ljust(12, b"\x00") + struct.pack("<4HIIII", 0, 0, 0, 0, dbl, 7, n, BLOCK)
        rom[TRAINER_TABLE + 40 * tid:TRAINER_TABLE + 40 * tid + 40] = ent
    rom[SPEECH_ENTRY:SPEECH_ENTRY + 12] = struct.pack("<III", TEXT_BUF, TEXT_BUF + 0x80, TEXT_BUF + 0x100)
    scratch = tempfile.mkdtemp(prefix="m4e-")
    open(f"{scratch}/game.gba", "wb").write(rom)
    shutil.copy(a.sav, f"{scratch}/game.sav")
    os.environ["RHT_LOAD_SAVE"] = "1"
    os.chdir(MAIN)
    play.stop()
    play.boot(f"{scratch}/game.gba")
    e = Emu()
    e.wait(120)
    for _ in range(60):
        if struct.unpack("<I", e.read(CB2, 4))[0] == play.OVERWORLD_CB2:
            e.wait(30)
            break
        e.press("A", hold=3, release=6)
        e.wait(40)
    e.wait(150)
    e.write(BASE, blob)
    e.write(TEXT_BUF, enc_name("You will not see this."))
    e.write(TEXT_BUF + 0x80, mt.encode_en("You beat me!\nWell fought."))
    e.write(TEXT_BUF + 0x100, mt.encode_en("I win this one.\nBetter luck next time."))

    def run(off, wait_state=False, **v):
        for k, val in v.items():
            e.write(SPV + 2 * int(k[1:]), struct.pack("<H", val))
        for attempt in range(6):
            e.write(V8, struct.pack("<H", 0xBEEF))
            code = bytes([0x23]) + struct.pack("<I", (BASE + OFF[off]) | 1)
            if wait_state:
                code += bytes([0x27, 0x02])
            else:
                code += bytes([0x19]) + struct.pack("<HH", 0x8008, 0x800D) + bytes([0x02])
            e.write(SCRIPT, code)
            e.write(CTX + 8, struct.pack("<I", SCRIPT))
            e.write(CTX, b"\x00\x01")
            e.write(RUNNING, bytes(4))
            e.wait(30)
            if wait_state or struct.unpack("<H", e.read(V8, 2))[0] != 0xBEEF:
                break
        else:
            raise RuntimeError("script never ran")
        return struct.unpack("<H", e.read(V8, 2))[0]

    def vars_(*idx):
        return [struct.unpack("<H", e.read(SPV + 2 * i, 2))[0] for i in idx]

    names = {int(k): v for k, v in __import__("json").load(open(f"{MAIN}/text/en/tables/species.json")).items()}
    items = {}
    for fnm in ("items2.json", "items.json"):
        items.update({int(k): v for k, v in __import__("json").load(open(f"{MAIN}/text/en/tables/{fnm}")).items()})
    moves = {int(k): v for k, v in __import__("json").load(open(f"{MAIN}/text/en/tables/moves.json")).items()}

    def team():
        n = vars_(4)[0]
        blk = e.read(BLOCK, 16 * n)
        out = []
        for i in range(n):
            iv, lv, sp, it, *mv = struct.unpack_from("<HBxHH4H", blk, 16 * i)
            out.append(f"{names.get(sp, sp)} Lv{lv} @ {items.get(it, it)} [{', '.join(moves.get(m, str(m)) for m in mv if m)}]")
        return out

    if a.survey:
        for n in (1, 5, 7, 8, 14, 15, 22, 30, 50):
            for dbl in (0, 1):
                run("gen", v0=n, v1=dbl, v2=a.seed & 0xFFFF, v3=a.seed >> 16)
                print(f"battle {n:2d} {'doubles' if dbl else 'singles'}:")
                for t in team():
                    print("    ", t)
        play.stop()
        return 0

    # the player's side: picks 0,1(,2,3) scaled to Lv 50
    npick = 4 if a.double else 3
    res = run("enter", v0=npick, v1=0, v2=1, v3=2, v4=3)
    print("fr_enter result", res, "party count", e.read(COUNT, 1)[0])
    res = run("gen", v0=a.n, v1=1 if a.double else 0, v2=a.seed & 0xFFFF, v3=a.seed >> 16)
    print(f"fr_gen_opponent result {res}; battle {a.n} {'doubles' if a.double else 'singles'}:")
    for t in team():
        print("   ", t)
    if a.play:
        run("start", wait_state=True, v0=SHELLS[1 if a.double else 0], v1=1 if a.double else 0)
        e.wait(400)
        print("flags", hex(struct.unpack("<I", e.read(0x02022B4C, 4))[0]))
        shots = []
        for k in range(60):
            cb = struct.unpack("<I", e.read(CB2, 4))[0]
            if cb == 0x0811EBA1:
                e.press("B", hold=3, release=6)
                e.wait(30)
            else:
                e.press("A", hold=3, release=6)
                e.wait(60)
            if k % 4 == 3:
                f = f"{a.out}/m4e_{k:03d}.png"
                e.screenshot(f)
                shots.append(f)
            if cb == play.OVERWORLD_CB2 and k > 8:
                print("back on the overworld; outcome", e.read(0x02023E8A, 1)[0])
                break
        open(f"{a.out}/m4e_shots.txt", "w").write("\n".join(shots))
    play.stop()
    shutil.rmtree(scratch, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
