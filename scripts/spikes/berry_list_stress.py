"""Regression test for #121: the Berry Pouch list (the Cianwood Shuckle's feed picker) must open for every berry count.

    python3 scripts/spikes/berry_list_stress.py SAVE [ROM]

Boots a scratch copy of ROM + SAVE (the .sav is never touched), warps next to the Shuckle (3.73 at 24,12), fills the berry pocket with
N berries whose LAST one has a 13-letter name (Maranga Berry, 0x1D5), opens the picker and checks the game gets past the list's setup
(gMain.state 14) and, after picking the first berry, returns to the overworld. Before the fix N = 24, 28 and 32 (27*N a multiple of 4)
froze the screen (black, static): the last 28-byte row spilled out of its 27-byte slot over the next heap block's header.
"""
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import mapdrive  # noqa: E402
import play  # noqa: E402

BERRY_POCKET = 0x0203C61C   # gBagPockets[4].itemSlots in the translation/River builds (CFRU layout); 75 slots
OVERWORLD_CB2 = "b5650508"
STATE = 0x03003528          # gMain.state
MARANGA = 0x1D5


def run(rom, save, n):
    e, scratch = mapdrive.start(rom, save)
    try:
        mapdrive.warp(e, 3, 73, 24, 12)
        slots = bytearray(75 * 4)
        for j in range(n - 1):
            struct.pack_into("<HH", slots, j * 4, 0x85 + j % 40, 3)
        struct.pack_into("<HH", slots, (n - 1) * 4, MARANGA, 3)
        e.write(BERRY_POCKET, bytes(slots))
        e.press("Left"); e.wait(20)
        listed = False
        for _ in range(12):
            e.press("A", hold=3, release=25); e.wait(40)
            if e.read(0x030030F4, 4).hex() != OVERWORLD_CB2:
                listed = True
                break
        e.wait(150)
        stuck = listed and e.read(STATE, 1)[0] == 14
        e.press("A", hold=3, release=25); e.wait(200)       # pick the first berry
        back = e.read(0x030030F4, 4).hex() == OVERWORLD_CB2
        return listed and not stuck and back
    finally:
        play.stop()
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    save = sys.argv[1]
    rom = sys.argv[2] if len(sys.argv) > 2 else "build/editions/Pokemon Azoth English + Frontier.gba"
    bad = [n for n in (3, 4, 8, 24, 27, 28, 29, 32, 36, 40) if not run(rom, save, n)]
    print("FAIL for counts", bad) if bad else print("OK: berry list opens for every tested count")
    sys.exit(1 if bad else 0)
