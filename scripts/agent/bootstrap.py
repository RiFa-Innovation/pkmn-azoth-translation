"""From a fresh boot (no save) to the first moment of control in the bedroom (map 42.4), using the settings an unattended run wants.

    python3 scripts/agent/bootstrap.py [--settings fast]

Steps verified 2026-10-24 on the beta-26 ROM: title (Start), New Game, name entry (scenes.act_naming keeps the default), disclaimer (Start on any page jumps to Settings), the Settings screen (Right = Text Speed Fast, Down + Right =
Battle Scene Off, B closes), then the scripted prologue, which play_loop advances (it contains a scripted battle).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import observe as ob  # noqa: E402
import play  # noqa: E402
import play_loop as pl  # noqa: E402
import run as rn  # noqa: E402
import scenes  # noqa: E402

SETTINGS_CB2 = 0x08DF29F1


def new_game(e, dex, fast_settings=True):
    e.wait(300)
    rn.tap(e, "Start", 60)       # title -> New Game / Settings
    rn.tap(e, "A", 90)           # New Game
    for _ in range(60):          # intro dialogue, then the name entry
        if rn.cb2(e) == scenes.NAMING_CB2:
            print(scenes.act_naming(e))
            break
        rn.tap(e, "A", 60)
    for _ in range(120):         # the disclaimer is a script on map 42.3
        if play.pos(e)[2:] == (42, 3):
            break
        rn.tap(e, "A", 30)
    else:
        raise RuntimeError("never reached the disclaimer (map 42.3)")
    for _ in range(150):         # pages advance with A; the last one waits for Start, so A no longer moves the script pointer
        p0 = scenes.script_ptr(e)
        rn.tap(e, "A", 60)
        if scenes.script_ptr(e) == p0:
            rn.tap(e, "Start", 60)
            if rn.cb2(e) == SETTINGS_CB2:
                break
    else:
        raise RuntimeError("never reached the Settings screen")
    if fast_settings:
        for k in ("Right", "Down", "Right"):
            rn.tap(e, k, 12)
    rn.tap(e, "B", 120)          # close Settings
    for _ in range(40):          # the script context is idle between text boxes, so a loop pass can end early: go again
        code, msg, _ = pl.play_loop(e, dex, "map:42.4", [], max_actions=400, stall=60)
        if code == 0:
            return play.pos(e)
        if code != 3:
            raise RuntimeError(f"prologue stopped: {msg}")
        e.wait(90)
    raise RuntimeError("prologue did not reach the bedroom")


if __name__ == "__main__":
    from emu import Emu
    print(new_game(Emu(), ob.Dex(), "--settings" not in sys.argv or "fast" in sys.argv))
