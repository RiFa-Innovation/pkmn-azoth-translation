"""Drive a scratch copy of a ROM + save in the headless emulator for map testing.

    python3 scripts/mapdrive.py ROM WARP_G WARP_N X Y [shot.png]

Boots ROM with the (copied) playtest save, reaches the overworld, injects
`warp G N 0xFF X Y` and prints `where` + saves a screenshot. Never touches the
real save: ROM and save are copied to a temp folder first.
"""
import os
import shutil
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import play  # noqa: E402
from emu import Emu  # noqa: E402
from species_peek import CTX, RUNNING, SCRIPT, to_overworld  # noqa: E402

SAVE = "saves/playtest-2026-10-10.sav"


def start(rom, save=SAVE):
    scratch = tempfile.mkdtemp(prefix="mapdrive-")
    shutil.copy(rom, f"{scratch}/game.gba")
    shutil.copy(save, f"{scratch}/game.sav")
    os.environ["RHT_LOAD_SAVE"] = "1"
    play.stop()
    play.boot(f"{scratch}/game.gba")
    e = Emu()
    e.wait(120)
    if not to_overworld(e):
        raise SystemExit("never reached the overworld")
    return e, scratch


def run_script(e, code):
    e.write(SCRIPT, code)
    e.write(CTX + 8, struct.pack("<I", SCRIPT))
    e.write(CTX, b"\x00\x01")
    e.write(RUNNING, bytes(4))


def warp(e, g, n, x, y, wait=90):
    run_script(e, bytes([0x39, g, n, 0xFF]) + struct.pack("<HH", x, y) + bytes([0x27, 0x02]))
    e.wait(wait)


if __name__ == "__main__":
    rom, g, n, x, y = sys.argv[1], *map(int, sys.argv[2:6])
    e, scratch = start(rom)
    warp(e, g, n, x, y)
    print(play.where(e))
    if len(sys.argv) > 6:
        e.screenshot(os.path.abspath(sys.argv[6]))
    play.stop()
    shutil.rmtree(scratch, ignore_errors=True)
