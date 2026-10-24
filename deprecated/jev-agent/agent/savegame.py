"""Save the game from the overworld through the Start menu, and copy the resulting .sav.

The Start menu is a ring (Pokemon, Bag, Pokegear, Save, Trainer Card, Option, Pass Time ...; a Pokedex entry shifts Save right) that
REMEMBERS its cursor. Save is found by behaviour (press A from the third entry on until the save prompt shows), not by an index byte:
the byte that tracked the cursor in one map (0x02002F97) was unrelated in another (checked 2026-10-24).
Headless mGBA writes the .sav only if a save file already exists next to the ROM at boot (RHT_LOAD_SAVE=1): start runs from a blank
128 KB file of 0xFF (`blank_sav`). Without one the in-game save works but nothing reaches the disk.
"""
import os
import shutil

import observe as ob
import run as rn


def blank_sav(path):
    with open(path, "wb") as f:
        f.write(b"\xff" * 131072)


def _prompt_up(e, tries=8):
    for _ in range(tries):
        if "save the game" in ob.message(e).lower():
            return True
        e.wait(15)
    return False


def save_game(e):
    """True when the game reported a save. Call from an idle overworld (no script, no menu).

    The ring's contents shift with story progress (a Pokedex entry moves Save right), and the cursor byte seen in one map was unrelated in
    another, so Save is found by behaviour: go to the left end, then from the third entry on press A and see whether the save prompt
    appears (the message buffer is blanked first, so an old prompt cannot match). Entries before Save only open screens that B closes."""
    rn.tap(e, "Start", 40)
    for _ in range(8):
        rn.tap(e, "Left", 8)
    for _ in range(2):
        rn.tap(e, "Right", 12)
    for _ in range(5):
        e.write(ob.STRING_VAR4, b"\xff")
        rn.tap(e, "A", 20)
        if _prompt_up(e):
            break
        for _ in range(4):                      # a screen opened (Bag, Pokegear, ...): B returns to the ring
            if rn.cb2(e) == ob.OVERWORLD_CB2:
                break
            rn.tap(e, "B", 40)
        rn.tap(e, "Right", 12)
    else:
        rn.tap(e, "B", 30)
        rn.tap(e, "B", 30)
        raise RuntimeError("could not find Save in the Start menu")
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
