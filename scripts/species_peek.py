"""Stage wild battles to look at species names + front sprites in game.

    python3 scripts/species_peek.py 1408 1496 Koraidon          # ids or English names
    python3 scripts/species_peek.py --range 1401 1553 --level 30
    python3 scripts/species_peek.py 1408 --rom build/Mercury_EN.gba --save saves/playtest-2026-10-10.sav

Copies ROM + save to a scratch folder (the real .sav is never touched), boots
mgba-headless with RHT_LOAD_SAVE=1, walks Continue to the overworld, saves a
state, then for each species injects `setwildbattle; dowildbattle; end` into
the script context (EMULATOR.md "Running a script directly") and screenshots
the battle intro (foe name box + front sprite) into --out
(default saves/shots/species/NNNN.png). Also prints the name the ROM holds.
"""
import argparse
import json
import os
import shutil
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import play  # noqa: E402
from emu import Emu  # noqa: E402

CB2 = 0x030030F4
CTX = 0x03000EB0
RUNNING = 0x03000EA8
SCRIPT = 0x0203FF00
NAME_TABLE, NAME_STRIDE = 0x141B350, 11


def u32(e, a):
    return struct.unpack("<I", e.read(a, 4))[0]


def to_overworld(e, tries=60):
    for _ in range(tries):
        if u32(e, CB2) == play.OVERWORLD_CB2:
            e.wait(30)
            return True
        e.press("A", hold=3, release=6)
        e.wait(40)
    return False


def start_wild(e, species, level):
    # setwildbattle species(2) level(1) item(2); dowildbattle; end
    code = bytes([0xB6]) + struct.pack("<HBH", species, level, 0) + bytes([0xB7, 0x02])
    e.write(SCRIPT, code)
    e.write(CTX + 8, struct.pack("<I", SCRIPT))
    e.write(CTX, b"\x00\x01")
    e.write(RUNNING, bytes(4))  # last, 4 bytes: the game re-arms it every frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("species", nargs="*")
    ap.add_argument("--range", nargs=2, type=int, metavar=("LO", "HI"))
    ap.add_argument("--level", type=int, default=30)
    ap.add_argument("--rom", default="build/Mercury_EN.gba")
    ap.add_argument("--save", default="saves/playtest-2026-10-10.sav")
    ap.add_argument("--out", default="saves/shots/species")
    ap.add_argument("--wait", type=int, default=420, help="frames to let the intro run")
    a = ap.parse_args()

    names = json.load(open("text/en/tables/species.json"))
    by_name = {v.lower(): int(k) for k, v in names.items()}
    ids = []
    for s in a.species:
        ids.append(int(s) if s.isdigit() else by_name[s.lower()])
    if a.range:
        ids += list(range(a.range[0], a.range[1] + 1))
    if not ids:
        ap.error("give species ids/names or --range")

    scratch = tempfile.mkdtemp(prefix="peek-")
    shutil.copy(a.rom, f"{scratch}/game.gba")
    shutil.copy(a.save, f"{scratch}/game.sav")
    os.environ["RHT_LOAD_SAVE"] = "1"
    play.stop()
    try:
        Emu().info()
    except OSError:
        pass
    else:  # the bridge port is fixed (8765); never drive someone else's emulator
        shutil.rmtree(scratch, ignore_errors=True)
        sys.exit("an emulator is already listening on 127.0.0.1:8765 (another session?); "
                 "stop it first, this script will not drive it")
    play.boot(f"{scratch}/game.gba")
    e = Emu()
    e.wait(120)
    if not to_overworld(e):
        sys.exit("never reached the overworld; check the save / screenshot")
    base = f"{scratch}/ow.ss"
    e.save_state(base)
    rom = open(a.rom, "rb").read()
    os.makedirs(a.out, exist_ok=True)
    for sid in ids:
        e.load_state(base)
        e.wait(10)
        start_wild(e, sid, a.level)
        e.wait(a.wait)
        out = os.path.abspath(f"{a.out}/{sid:04d}.png")
        e.screenshot(out)
        from mercury_text import decode_fixed
        nm = decode_fixed(rom, NAME_TABLE + sid * NAME_STRIDE, NAME_STRIDE)
        print(sid, nm, "->", out, "(in battle)" if u32(e, CB2) != play.OVERWORLD_CB2 else "(NOT in battle)")
    play.stop()
    shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
