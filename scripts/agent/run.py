"""Play single battles in the headless emulator: observe -> options -> decide (Jev or heuristic) -> press buttons.

    python3 scripts/agent/run.py battle [--goal win|flee] [--min-conf 0.5] [--log FILE] [--dry]
    python3 scripts/agent/run.py state                  # print the current snapshot + options (no input)
    python3 scripts/agent/run.py play --until map:G.N --route "x,y A w30"   # walk, fight, talk; see play_loop.py
    python3 scripts/agent/run.py heal                   # cheat: fully heal the team in RAM (HP, PP, status)
    python3 scripts/agent/run.py wild SPECIES LEVEL     # start a scripted wild battle from the overworld (test helper)

Needs the bridge running (scripts/play.py boot). Every decision is appended to the JSONL log (default
saves/agent/decisions.jsonl, gitignored with saves/) with the state, options, heuristic pick, Jev's answer and what was played.
Menu layout (checked 2026-10-23): action and move menus are 2x2 grids (cursor bytes in observe.py); the battle party menu is a
2-column grid 0 1 / 2 3 / 4 5 in *battle order* (gBattlePartyCurrentOrder), then A on the first entry ("Shift").
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from emu import Emu  # noqa: E402
import observe as ob  # noqa: E402
import options as op  # noqa: E402
import decide as dc  # noqa: E402

BATTLE_CB2 = 0x08011101
PARTY_MENU_CB2 = ob.PARTY_MENU_CB2

PARTY_MENU_SLOT = 0x0203B0A9  # gPartyMenu.slotId
SCRIPT_BUF = 0x0203FF00


def tap(e, key, after=20):
    e.press(key, hold=3, release=6)
    e.wait(after)


def cb2(e):
    return struct.unpack("<I", e.read(ob.CB2, 4))[0]


def grid_to(e, cursor_addr, target, cols=2):
    """Move a grid cursor (index = row*cols + col) to target with direction taps, then check it landed."""
    for _ in range(8):
        c = e.read(cursor_addr, 1)[0]
        if c == target:
            return True
        if c % cols != target % cols:
            tap(e, "Right" if target % cols > c % cols else "Left", 8)
        else:
            tap(e, "Down" if target // cols > c // cols else "Up", 8)
    return e.read(cursor_addr, 1)[0] == target


def menu_pos_of(e, party_slot):
    return ob.battle_order(e).index(party_slot)


def wait_party_menu(e, frames=180):
    for _ in range(frames // 10):
        if cb2(e) not in (BATTLE_CB2, ob.OVERWORLD_CB2):
            e.wait(30)  # let the menu finish drawing
            return True
        e.wait(10)
    return False


def pick_party(e, party_slot):
    """In the party menu (already open): select the mon in `party_slot` and confirm Shift."""
    if not grid_to(e, PARTY_MENU_SLOT, menu_pos_of(e, party_slot)):
        return False
    tap(e, "A", 30)
    tap(e, "A", 60)  # first submenu entry: Shift / Send out
    return True


def act(e, opt):
    """Drive the menus for one option from the action menu. Returns False if a cursor did not land."""
    if ob.phase(e) == "choose_move":
        tap(e, "B")
    if opt["kind"] == "move":
        if not grid_to(e, ob.ACTION_CURSOR, 0):
            return False
        tap(e, "A", 25)
        if not grid_to(e, ob.MOVE_CURSOR, opt["slot"]):
            return False
        tap(e, "A", 10)
        return True
    if opt["kind"] == "run":
        if not grid_to(e, ob.ACTION_CURSOR, 3):
            return False
        tap(e, "A", 10)
        return True
    if opt["kind"] == "switch":
        if not grid_to(e, ob.ACTION_CURSOR, 2):
            return False
        tap(e, "A", 10)
        return wait_party_menu(e) and pick_party(e, opt["slot"])
    raise ValueError(opt["kind"])


def forced_switch(e, dex, goal, min_conf, log, turn):
    """The game opened the party menu (a faint, or U-turn/Volt Switch): pick the replacement like any other decision,
    with only the switch options. The snapshot's foe is the one still on the field."""
    state = ob.snapshot(e, dex)
    opts = [o for o in op.build(state) if o["kind"] == "switch"]
    if not opts:
        return False
    rec = dc.decide(state, opts, goal, min_conf)
    rec.update(turn=turn, forced=True)
    report(state, rec, next(o for o in opts if o["key"] == rec["action"]), log)
    return pick_party(e, next(o for o in opts if o["key"] == rec["action"])["slot"])


def report(state, rec, opt, log):
    jv = rec.get("jev") or {}
    print(f"turn {rec['turn']}{' (replacement)' if rec.get('forced') else ''}: {state['you']['name']} "
          f"{state['you']['hp_pct']}% vs {state['foe']['name']} {state['foe']['hp_pct']}%  -> {rec['action']} [{rec['source']}"
          f"{', jev ' + str(jv.get('choice')) + ' @' + str(jv.get('confidence')) if jv else ''}"
          f"{', heuristic ' + rec['heuristic'] if rec['source'] != 'heuristic' else ''}]  {opt['desc']}", flush=True)
    if log:
        with open(log, "a") as f:
            f.write(json.dumps(rec) + "\n")


def battle(e, dex, goal="win", min_conf=0.5, log=None, dry=False, max_turns=60):
    """Play until back on the overworld. Busy screens are advanced with A; foreign screens (summary from a move-learn
    prompt) are backed out with B; a party menu opened by the game is treated as a forced switch."""
    turns, idle, picks = 0, 0, 0
    while turns < max_turns and picks < 4:
        ph = ob.phase(e)
        if ph == "overworld":
            return turns
        cb = cb2(e)
        if ph == "choose_action":
            idle = 0
            state = ob.snapshot(e, dex)
            if not state["you"]["level"] or not state["foe"]["level"]:  # battlers not loaded yet
                e.wait(10)
                continue
            opts = op.build(state)
            rec = dc.decide(state, opts, goal, min_conf)
            rec["turn"] = turns
            opt = next(o for o in opts if o["key"] == rec["action"])
            report(state, rec, opt, log)
            if dry:
                return turns
            rec_ok = act(e, opt)
            if not rec_ok:
                print("  cursor did not land; backing out")
                tap(e, "B")
            turns += 1
            e.wait(30)
            continue
        if cb not in (BATTLE_CB2, ob.OVERWORLD_CB2):
            if cb == PARTY_MENU_CB2:  # never left open by act(), so the game asked for a replacement
                e.wait(30)
                picks += 1
                if not forced_switch(e, dex, goal, min_conf, log, turns):
                    tap(e, "B", 30)
            else:
                tap(e, "B", 30)
            continue
        picks = 0
        idle += 1
        if idle % 6 == 0:
            tap(e, "A", 10)  # text waiting for a press, prompts (A = yes)
        else:
            e.wait(10)
    return turns


def start_wild(e, species, level):
    """setwildbattle species level 0; dowildbattle; end — run through the global script context."""
    e.write(SCRIPT_BUF, bytes([0xB6]) + struct.pack("<HBH", species, level, 0) + bytes([0xB7, 0x02]))
    e.write(0x03000EB8, struct.pack("<I", SCRIPT_BUF))
    e.write(0x03000EB0, b"\x00\x01")
    e.write(0x03000EA8, b"\x00")


def main():
    if sys.argv[1:2] == ["heal"]:  # playtest cheat: whole team to full HP/PP, no status
        import cheats
        print(f"healed {cheats.heal_party(Emu(), ob.Dex())} party members")
        return
    if sys.argv[1:2] == ["play"]:  # route + battles + dialogue + anomaly stop (play_loop.py)
        import play_loop
        sys.exit(play_loop.main(sys.argv[2:]))
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["battle", "state", "wild"])
    ap.add_argument("args", nargs="*", type=int)
    ap.add_argument("--goal", default="win", choices=sorted(dc.INSTRUCTIONS))
    ap.add_argument("--min-conf", type=float, default=0.5)
    ap.add_argument("--log", default="saves/agent/decisions.jsonl")
    ap.add_argument("--dry", action="store_true", help="decide once, log it, press nothing")
    a = ap.parse_args()
    e = Emu()
    if a.cmd == "wild":
        start_wild(e, *a.args)
        return
    dex = ob.Dex()
    if a.cmd == "state":
        state = ob.snapshot(e, dex)
        opts = op.build(state)
        print(json.dumps({"phase": ob.phase(e), "context": op.context(state), "options": {o["key"]: o["desc"] for o in opts},
                          "heuristic": op.heuristic(state, opts, a.goal),
                          "jev_request": dc.request_body(state, opts, a.goal)}, indent=1))
        return
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    n = battle(e, dex, a.goal, a.min_conf, a.log, a.dry)
    print(f"done after {n} decisions; phase {ob.phase(e)}")


if __name__ == "__main__":
    main()
