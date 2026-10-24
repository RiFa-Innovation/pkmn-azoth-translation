"""Recognised non-battle screens and scripted choice points (D5/D6/D8): each handler decides, then presses the buttons.

A handler is (name, match(e) -> bool, act(e, ctxinfo) -> str). `handle(e, ...)` runs the first that matches and returns its name,
or None when nothing matches (the caller then falls back to pressing A, and the stall detector reports a screen that never clears).
"""
import struct

import decide as dc
import observe as ob
import options as op
import play
import rn_shim as rn

NAMING_CB2 = 0x0809FB71          # the name-entry screen (player, nickname): Start moves to OK, A confirms the empty (default) name
STARTER_SCRIPT = (0x089C5700, 0x089C5A00)  # map 43.7 picker loop (`special 0x2f` polls the d-pad, 0x10 right, 0x20 left, 1 = A)
STARTER_MAP = (43, 7)
STARTERS = {  # centre / right / left of the carousel, with the key that browses to it
    "chikorita": (152, None), "totodile": (158, "Right"), "cyndaquil": (155, "Left"),
}


def script_ptr(e):
    return struct.unpack("<I", e.read(0x03000EB8, 4))[0]


def match_naming(e):
    return rn.cb2(e) == NAMING_CB2


def act_naming(e, **kw):
    rn.tap(e, "Start", 30)
    rn.tap(e, "A", 90)
    return "naming: default name kept"


def match_starter(e):
    return (rn.cb2(e) == ob.OVERWORLD_CB2 and play.pos(e)[2:] == STARTER_MAP and STARTER_SCRIPT[0] <= script_ptr(e) < STARTER_SCRIPT[1]
            and e.read(0x03000EB1, 1)[0] != 0)


def starter_options(dex):
    out = {}
    for name, (sid, _) in STARTERS.items():
        sp = dex.species.get(sid, {})
        hp, atk, df, spe, spa, spd = sp.get("stats", [0] * 6)
        out[name] = (f"{name.capitalize()} ({'/'.join(op.TYPES[t] for t in sp.get('types', []))}), base HP {hp} Atk {atk} Def {df} "
                     f"Spe {spe} SpA {spa} SpD {spd}")
    return out


def act_starter(e, dex=None, choice=None, min_conf=0.5, log=None, **kw):
    """Pick one of the three: `choice` forces it (reproducible saves); otherwise Jev decides with the type facts."""
    opts = starter_options(dex)
    rec = None
    if choice is None:
        rec = dc.choose({"team": "empty, this is the first Pokemon", "pick": "one of three"}, opts,
                        "You are choosing your first Pokemon for a long run through the Johto story. Pick the one that gives the "
                        "most reliable early game.", "totodile", min_conf, "starter")
        choice = rec["action"]
        if log:
            import json
            open(log, "a").write(json.dumps(rec) + "\n")
    key = STARTERS[choice][1]
    if key:
        rn.tap(e, key, 150)  # the cry and the carousel move take a moment
    rn.tap(e, "A", 60)       # confirm; the Yes/No that follows is answered by the generic A (Yes)
    return f"starter: {choice}" + (f" [{rec['source']}]" if rec else " [forced]")


HANDLERS = [("naming", match_naming, act_naming), ("starter", match_starter, act_starter)]


def handle(e, **kw):
    for name, match, act in HANDLERS:
        if match(e):
            return act(e, **kw)
    return None
