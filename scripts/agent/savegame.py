"""Save the game from the overworld through the Start menu, and copy the resulting .sav.

The Start menu is a ring (Pokemon, Bag, Pokegear, Save, Trainer Card, Option, Pass Time ...) that REMEMBERS its cursor; the live index is
the byte at 0x02002F97 (tracked 0..4 while moving, checked 2026-10-24), so navigation reads it instead of counting presses. Save is 3.
Headless mGBA writes the .sav only if a save file already exists next to the ROM at boot (RHT_LOAD_SAVE=1): start runs from a blank
128 KB file of 0xFF (`blank_sav`). Without one the in-game save works but nothing reaches the disk.
"""
import os
import shutil

import observe as ob
import run as rn

MENU_INDEX = 0x02002F97
SAVE_INDEX = 3


def blank_sav(path):
    with open(path, "wb") as f:
        f.write(b"\xff" * 131072)


def save_game(e):
    """True when the game reported a save. Call from an idle overworld (no script, no menu)."""
    rn.tap(e, "Start", 40)
    for _ in range(12):
        i = e.read(MENU_INDEX, 1)[0]
        if i == SAVE_INDEX:
            break
        rn.tap(e, "Right" if i < SAVE_INDEX else "Left", 20)
    else:
        rn.tap(e, "B", 30)
        raise RuntimeError("could not reach Save in the Start menu")
    rn.tap(e, "A", 60)
    if "save the game" not in ob.message(e).lower():
        rn.tap(e, "B", 30)
        raise RuntimeError(f"expected the save prompt, got {ob.message(e)[:60]!r}")
    rn.tap(e, "A", 60)                       # Yes
    if "overwrite" in ob.message(e).lower():
        rn.tap(e, "A", 60)                   # "already a save file" -> Yes
    e.wait(500)                              # "Saving... Don't turn off the power", then the menu closes itself
    rn.tap(e, "B", 30)
    return True


def export_sav(src, dest):
    """Copy the emulator's .sav (after a flush delay) to dest; refuse an all-0xFF file (nothing was written)."""
    data = open(src, "rb").read()
    if data.count(0xFF) == len(data):
        raise RuntimeError(f"{src} is still blank: boot with a blank .sav present and RHT_LOAD_SAVE=1")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(src, dest)
    return dest
