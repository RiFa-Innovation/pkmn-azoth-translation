"""Save forging experiments: dump the complete story state of a running game, and diff two dumps.

    python3 scripts/forge.py dump OUT.json          # the emulator must sit on an idle overworld (no script, no menu)
    python3 scripts/forge.py diff A.json B.json     # what changed between two story points

A dump holds every set flag (ids 0 .. FLAG_MAX, asked of the game's own `checkflag`, so the hack's flags above 0x900 are covered),
every non-zero hack var (the array at 0x2039374, ids 0x4000 ..), the position, and the party. The point of the diff is to measure what a
forged save would have to reproduce: compare two REAL saves of consecutive story points, or a real save with a forged one.
Items and money are not dumped yet (SaveBlock1 values are encrypted).
"""
import json
import struct
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import play  # noqa: E402
from emu import Emu  # noqa: E402

CTX, SCRIPT = 0x03000EB0, 0x0203FF00
VAR_BASE_RAM, VAR_BASE_ID, VAR_COUNT = 0x2039374, 0x4000, 0x1800
FLAG_MAX = 0x1800
PARTY, PARTY_N = 0x02024284, 0x02024029


def flag_get(e, fid):
    e.write(SCRIPT, bytes([0x2B]) + struct.pack("<H", fid) + bytes([0x02]))
    e.write(CTX + 8, struct.pack("<I", SCRIPT))
    e.write(CTX, b"\x00\x01")
    e.write(0x03000EA8, b"\x00")
    e.wait(3)
    return bool(e.read(CTX + 2, 1)[0])


def party(e):
    out = []
    for i in range(min(e.read(PARTY_N, 1)[0], 6)):
        b = e.read(PARTY + 100 * i, 100)
        sp = struct.unpack_from("<H", b, 0x20)[0]
        if sp:
            out.append({"species": sp, "level": b[0x54], "hp": struct.unpack_from("<H", b, 0x56)[0],
                        "max_hp": struct.unpack_from("<H", b, 0x58)[0], "moves": [m for m in struct.unpack_from("<4H", b, 0x2C) if m]})
    return out


def dump(e):
    x, y, g, n = play.pos(e)
    raw = e.read(VAR_BASE_RAM, VAR_COUNT * 2)
    vars_ = {f"{VAR_BASE_ID + i:#06x}": v for i, v in enumerate(struct.unpack(f"<{VAR_COUNT}H", raw)) if v}
    flags = [f"{f:#06x}" for f in range(FLAG_MAX) if flag_get(e, f)]
    return {"map": f"{g}.{n}", "pos": [x, y], "party": party(e), "vars": vars_, "flags": flags}


def diff(a, b):
    out = {"map": (a["map"], b["map"]), "pos": (a["pos"], b["pos"])}
    fa, fb = set(a["flags"]), set(b["flags"])
    out["flags_set"], out["flags_cleared"] = sorted(fb - fa), sorted(fa - fb)
    keys = set(a["vars"]) | set(b["vars"])
    out["vars"] = {k: (a["vars"].get(k, 0), b["vars"].get(k, 0)) for k in sorted(keys) if a["vars"].get(k, 0) != b["vars"].get(k, 0)}
    out["party"] = (a["party"], b["party"])
    return out


def story_delta(a, b, db_path):
    """The part of a -> b a forged save must reproduce: every flag change, plus vars that some script reads or writes. Vars no script
    touches (position caches, timers, RNG state) are system noise and are left alone."""
    import sqlite3
    db = sqlite3.connect(db_path)
    d = diff(a, b)
    vars_ = {k: v for k, v in d["vars"].items()
             if db.execute("select 1 from refs where kind='var' and id=? limit 1", (int(k, 16),)).fetchone()}
    return {"flags_set": d["flags_set"], "flags_cleared": d["flags_cleared"], "vars": vars_, "map": b["map"], "pos": b["pos"]}


def run_script(e, code):
    e.write(SCRIPT, code)
    e.write(CTX + 8, struct.pack("<I", SCRIPT))
    e.write(CTX, b"\x00\x01")
    e.write(0x03000EA8, b"\x00")
    e.wait(4)


def apply_delta(e, delta):
    """Write a story delta into the running game through its own script commands (setflag 0x29, clearflag 0x2A, setvar 0x16)."""
    for f in delta["flags_set"]:
        run_script(e, bytes([0x29]) + struct.pack("<H", int(f, 16)) + bytes([0x02]))
    for f in delta["flags_cleared"]:
        run_script(e, bytes([0x2A]) + struct.pack("<H", int(f, 16)) + bytes([0x02]))
    for k, (old, new) in delta["vars"].items():
        run_script(e, bytes([0x16]) + struct.pack("<HH", int(k, 16), new) + bytes([0x02]))
    g, n = map(int, delta["map"].split("."))
    x, y = delta["pos"]
    run_script(e, bytes([0x39, g, n, 0xFF]) + struct.pack("<HH", x, y) + bytes([0x27, 0x02]))  # warp + waitstate
    e.wait(90)


def main(argv):
    if argv[:1] == ["dump"]:
        d = dump(Emu())
        json.dump(d, open(argv[1], "w"), indent=1)
        print(f"{argv[1]}: map {d['map']}, {len(d['flags'])} flags set, {len(d['vars'])} vars non-zero, party {len(d['party'])}")
    elif argv[:1] == ["diff"]:
        a, b = (json.load(open(p)) for p in argv[1:3])
        d = diff(a, b)
        print(f"map {d['map'][0]} -> {d['map'][1]}, pos {d['pos'][0]} -> {d['pos'][1]}")
        print(f"flags set {len(d['flags_set'])}, cleared {len(d['flags_cleared'])}, vars changed {len(d['vars'])}")
        print("  flags set:    ", " ".join(d["flags_set"]))
        print("  flags cleared:", " ".join(d["flags_cleared"]))
        for k, (x, y) in d["vars"].items():
            print(f"  var {k}: {x} -> {y}")
        print("  party:", d["party"][0], "->", d["party"][1])
    elif argv[:1] == ["forge"]:   # forge A.json B.json DB : make the running game (a real save of A) look like B
        a, b = (json.load(open(p)) for p in argv[1:3])
        delta = story_delta(a, b, argv[3])
        print(f"applying {len(delta['flags_set'])} flags set, {len(delta['flags_cleared'])} cleared, {len(delta['vars'])} vars, warp {delta['map']} {delta['pos']}")
        apply_delta(Emu(), delta)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
