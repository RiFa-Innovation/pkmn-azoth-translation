"""Minimal M5: walk a route, play battles through the agent, advance dialogue, stop on a goal or an anomaly.

    python3 scripts/agent/run.py play --until map:1.90 --route "12,9 A w30" [--goal win] [--max-actions 3000]

--until   map:G.N | flag:0xID (ids < 0x900 only; hack flags live elsewhere) | var:0xID=VALUE
--route   space separated tokens, run in order (a token is repeated until it finishes; battles and dialogue interrupt it):
            x,y     walk there on the current map (BFS, re-planned each step; stepping onto a warp counts as arriving)
            @G.N    travel to that map across warps and connections (navmap.py), re-planning after each hop
            ^G.N    one hop toward it
            !heal   cheat: restore the whole team in RAM (HP, PP, status); cheats.py
            G.N     wait up to 2 s for that map, else stop "off route" (a blackout or an unexpected warp)
            A       press A (talk to the tile you face)
            tU tD tL tR   turn without walking
            wN      wait N frames
Dialogue: while the script context is running in the overworld, A is pressed (Yes on Yes/No, first entry of a multichoice).
Battles go through run.battle (Jev with heuristic fallback). Stops: goal reached (exit 0), route exhausted without the goal
(exit 3: the loop needs a goal, which is M6), or an anomaly (exit 2): a stall (at most 3 distinct state signatures over --stall actions of
~30 frames each), or a script context running garbage (mode 2 with a pointer below 0x08000100, mode 1 outside ROM/EWRAM).
An anomaly writes saves/agent/anomalies/<time>/{report.json,shot.png,state.ss} (gitignored).
"""
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import observe as ob  # noqa: E402
import play  # noqa: E402
import run as rn  # noqa: E402
import scenes  # noqa: E402

CTX = 0x03000EB0
VAR_BASE_RAM, VAR_BASE_ID = 0x2039374, 0x4000  # hack's var array (hackdb.py)
SB1 = 0x03005008


class Anomaly(Exception):
    pass


class Stop(Exception):
    pass


def ctx(e):
    b = e.read(CTX, 12)
    return b[1], struct.unpack_from("<I", b, 8)[0]


def script_active(e):
    return ctx(e)[0] != 0 and rn.cb2(e) == ob.OVERWORLD_CB2


def flag_set(e, fid):
    if fid >= 0x900:
        raise ValueError("flags >= 0x900 are not at SaveBlock1+0xEE0; use var: or a map condition")
    sb1 = struct.unpack("<I", e.read(SB1, 4))[0]
    return bool(e.read(sb1 + 0xEE0 + fid // 8, 1)[0] >> (fid & 7) & 1)


def var_val(e, vid):
    return struct.unpack("<H", e.read(VAR_BASE_RAM + 2 * (vid - VAR_BASE_ID), 2))[0]


def parse_until(s):
    kind, _, rest = s.partition(":")
    if kind == "map":
        g, n = rest.split(".")
        want = (int(g), int(n))
        return lambda e: play.pos(e)[2:] == want
    if kind == "flag":
        return lambda e: flag_set(e, int(rest, 0))
    if kind == "var":
        v, _, val = rest.partition("=")
        return lambda e: var_val(e, int(v, 0)) == int(val, 0)
    raise ValueError(f"unknown --until {s!r}")


class Watch:
    """Called after every action that should change something; raises Anomaly when nothing does for `limit` checks."""

    def __init__(self, limit=25):
        self.limit, self.hist = limit, []

    def sig(self, e):
        mode, ptr = ctx(e)
        x, y, g, n = play.pos(e)
        return (rn.cb2(e), struct.unpack("<I", e.read(ob.CONTROLLER, 4))[0], mode, ptr, g, n, x, y)

    def reset(self):
        self.hist = []

    def tick(self, e):
        s = self.sig(e)
        mode, ptr = s[2], s[3]
        if mode == 2 and ptr < 0x08000100:
            raise Anomaly(f"script context in native mode with pointer {ptr:#x} (placeholder script)")
        if mode == 1 and not (0x08000000 <= ptr < 0x0A000000 or 0x02000000 <= ptr < 0x02040000):
            raise Anomaly(f"script context in bytecode mode with pointer {ptr:#x} outside ROM/EWRAM")
        self.hist = (self.hist + [s])[-max(20, self.limit):]
        window = self.hist[-self.limit:]
        if len(window) == self.limit and len(set(window)) <= 3:  # <= 3 distinct states also catches a script that spins
            raise Anomaly(f"no progress over {self.limit} actions ({len(set(window))} distinct states; cb2 {s[0]:#x}, "
                          f"ctx mode {mode} ptr {ptr:#x}, map {s[4]}.{s[5]} pos ({s[6]},{s[7]}))")


def advance_script(e, watch):
    for _ in range(400):
        if not script_active(e):
            return
        rn.tap(e, "A", 20)
        watch.tick(e)


def goto(e, tx, ty, watch, budget=300):
    """'done' (arrived, or the map changed), 'interrupted' (battle or script started), 'nopath'."""
    blocked = set()
    m0 = play.pos(e)[2:]
    for _ in range(budget):
        x, y, *m = play.pos(e)
        if (x, y) == (tx, ty) or tuple(m) != m0:
            return "done"
        if ob.phase(e) != "overworld" or script_active(e):
            return "interrupted"
        p = play.path_to(e, tx, ty, blocked)
        if not p:
            return "nopath"
        d = p[0]
        play.walk(e, d, 1)
        watch.tick(e)
        if play.pos(e)[:2] == (x, y) and ob.phase(e) == "overworld" and not script_active(e):
            dx, dy = play.DELTA[d]
            blocked.add((x + dx, y + dy))
            if (x + dx, y + dy) == (tx, ty):
                return "nopath"  # the target tile itself refuses the step (NPC, wall)
    return "interrupted"


def push_dir(e, d, watch, base_map, taps=1):
    """Tap direction d (a door or arrow warp fires on the push toward its exit); True once the map changed."""
    for _ in range(taps):
        e.press(play.DIRS[d], hold=8, release=4)  # hold >= 6 frames starts a step; a 3-frame tap only turns
        e.wait(50)
        watch.tick(e)
        if play.pos(e)[2:] != base_map or ob.phase(e) != "overworld":
            return True
    return False


def exit_dirs(e, tx, ty):
    """Directions to push on a warp tile, wall-facing first: a door or mat sits in a wall, so its exit is the blocked/off-map side."""
    W, H, b = play.grid(e)
    out = []
    for d, (dx, dy) in play.DELTA.items():
        X, Y = tx + dx + 7, ty + dy + 7
        wall = not (0 <= X < W and 0 <= Y < H) or bool(b[X + W * Y] & 0x0C00)
        out.append((not wall, "DULR".index(d), d))
    return [d for _, _, d in sorted(out)]


def hop(e, edge, watch):
    """One map-to-map hop along a navmap edge. 'done' (map changed), 'interrupted' (battle/script), 'nopath'."""
    kind, arg = edge
    m0 = play.pos(e)[2:]
    x, y = play.pos(e)[:2]
    if kind == "warp":
        for tx, ty in sorted(arg, key=lambda t: abs(t[0] - x) + abs(t[1] - y)):
            r = "done" if (tx, ty) == (x, y) else goto(e, tx, ty, watch)
            if r == "interrupted":
                return r
            if play.pos(e)[2:] != m0:
                return "done"
            if r == "done":
                # arriving leaves you standing on the warp tile, and a plain warp fires on stepping *onto* it: step off and back
                # (a door or arrow warp fires on the push toward its exit instead; the same two taps cover it)
                for d in exit_dirs(e, tx, ty):
                    if push_dir(e, d, watch, m0):
                        return "done"
                    if ob.phase(e) != "overworld" or script_active(e):
                        return "interrupted"
                    if play.pos(e)[:2] != (tx, ty):  # it stepped off: step back on
                        play.walk(e, OPP[d], 1)
                        e.wait(60)
                        if play.pos(e)[2:] != m0:
                            return "done"
                        if play.pos(e)[:2] != (tx, ty):
                            goto(e, tx, ty, watch)
                    elif push_dir(e, d, watch, m0):  # blocked: the first tap only turned; a door/arrow warp fires on the second
                        return "done"
        return "nopath"
    d = nav_dir[arg]
    W, H, _ = play.grid(e)
    mw, mh = W - 15, H - 14
    edge_tiles = {"D": [(i, mh - 1) for i in range(mw)], "U": [(i, 0) for i in range(mw)],
                  "L": [(0, j) for j in range(mh)], "R": [(mw - 1, j) for j in range(mh)]}[d]
    tried = []
    for tx, ty in sorted(edge_tiles, key=lambda t: abs(t[0] - x) + abs(t[1] - y)):
        if any(abs(tx - a) + abs(ty - b) <= 1 for a, b in tried):
            continue
        r = goto(e, tx, ty, watch)
        if r == "interrupted":
            return r
        if play.pos(e)[2:] != m0:
            return "done"
        if r == "done":
            if push_dir(e, d, watch, m0, taps=3):
                return "done"
            if ob.phase(e) != "overworld" or script_active(e):
                return "interrupted"
        tried.append((tx, ty))
        if len(tried) >= 30:
            break
    return "nopath"


nav_dir = {1: "D", 2: "U", 3: "L", 4: "R"}
OPP = {"D": "U", "U": "D", "L": "R", "R": "L"}


def step_token(e, tok, watch, nav=None, dex=None):
    """Run one route token; returns True when finished (False = call again after battles/dialogue)."""
    if tok == "!heal":
        import cheats
        print(f"cheat heal: {cheats.heal_party(e, dex)} members changed")
        return True
    if tok[0] in "@^":
        tgt = tuple(map(int, tok[1:].split(".")))
        cur = play.pos(e)[2:]
        if cur == tgt:
            return True
        nav.add_live(e)
        r = nav.route(cur, tgt)
        if r is None:
            raise Anomaly(f"no map route from {cur} to {tgt}")
        res = hop(e, r[0][0], watch)
        if res == "nopath":
            raise Anomaly(f"could not leave map {cur} toward {r[0][1]} (edge {r[0][0][0]})")
        return res == "done" and tok[0] == "^"
    if "," in tok:
        x, y = map(int, tok.split(","))
        r = goto(e, x, y, watch)
        if r == "nopath":
            raise Anomaly(f"no path to {tok} from {play.pos(e)}")
        return r == "done"
    if "." in tok and tok.replace(".", "").isdigit():
        g, n = map(int, tok.split("."))
        for _ in range(8):
            if play.pos(e)[2:] == (g, n):
                return True
            e.wait(15)
        raise Stop(f"off route: wanted map {tok}, on {play.pos(e)[2]}.{play.pos(e)[3]}")
    if tok == "A":
        rn.tap(e, "A", 30)
    elif tok[0] == "t" and tok[1:] in play.DIRS:
        rn.tap(e, play.DIRS[tok[1:]], 10)
    elif tok[0] == "w" and tok[1:].isdigit():
        e.wait(int(tok[1:]))
    else:
        raise ValueError(f"bad route token {tok!r}")
    return True


def dump(e, outdir, reason, watch, extra):
    d = os.path.join(outdir, time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(d, exist_ok=True)
    rep = {"reason": reason, "frame": e.frame(), "map_pos": play.pos(e), "cb2": hex(rn.cb2(e)), "ctx": [hex(v) for v in ctx(e)],
           "recent_signatures": [[hex(v) if i in (0, 1, 3) else v for i, v in enumerate(s)] for s in watch.hist], **extra}
    json.dump(rep, open(os.path.join(d, "report.json"), "w"), indent=1)
    e.screenshot(os.path.abspath(os.path.join(d, "shot.png")))
    e.save_state(os.path.abspath(os.path.join(d, "state.ss")))
    return d


def play_loop(e, dex, until, route, goal="win", min_conf=0.5, log="saves/agent/decisions.jsonl", max_actions=3000, stall=25,
              outdir="saves/agent/anomalies", nav=None, planner=None, starter=None):
    route = list(route)
    done = parse_until(until) if until else (lambda e: False)
    watch, idx, battles = Watch(stall), 0, 0
    os.makedirs(os.path.dirname(log), exist_ok=True)
    try:
        for _ in range(max_actions):
            if ob.phase(e) == "overworld" and not script_active(e) and done(e):
                return 0, "goal reached", {"route_idx": idx, "battles": battles}
            sc = scenes.handle(e, dex=dex, choice=starter, min_conf=min_conf, log=log)
            if sc:
                print(sc)
                watch.reset()
                continue
            if ob.phase(e) != "overworld":
                try:
                    rn.battle(e, dex, goal, min_conf, log)
                except (NotImplementedError, RuntimeError) as ex:  # double battles (D7), unknown screens: stop with a report
                    raise Anomaly(f"unsupported situation: {ex}")
                battles += 1
                watch.reset()
                continue
            if script_active(e):
                advance_script(e, watch)
                continue
            if idx >= len(route) and planner:
                new = planner(e)
                if new is None:  # the planner is done: the target map was reached with nothing left to decide
                    return 0, "target reached", {"route_idx": idx, "battles": battles}
                route += new
            if idx >= len(route):
                return 3, "route finished", {"route_idx": idx, "battles": battles}
            if step_token(e, route[idx], watch, nav, dex):
                idx += 1
            watch.tick(e)
        raise Anomaly(f"max actions {max_actions} reached")
    except Anomaly as a:
        d = dump(e, outdir, str(a), watch, {"route_idx": idx, "token": route[idx] if idx < len(route) else None})
        return 2, f"anomaly: {a} (report in {d})", {"route_idx": idx, "battles": battles}
    except Stop as s:
        return 4, str(s), {"route_idx": idx, "battles": battles}


def main(argv):
    import argparse
    from emu import Emu
    ap = argparse.ArgumentParser(prog="run.py play")
    ap.add_argument("--until")
    ap.add_argument("--route", default="")
    ap.add_argument("--goal", default="win")
    ap.add_argument("--min-conf", type=float, default=0.5)
    ap.add_argument("--log", default="saves/agent/decisions.jsonl")
    ap.add_argument("--max-actions", type=int, default=3000)
    ap.add_argument("--target", help="G.N: travel there across maps, choosing each leg (heal or continue) with Jev")
    ap.add_argument("--heal-map", help="G.N of a map with a healer; --heal-route = tokens that heal once inside it")
    ap.add_argument("--heal-route", default="")
    ap.add_argument("--cheat-heal", action="store_true", help="offer the instant RAM heal as a goal option (needs --target)")
    ap.add_argument("--hackdb", default=None, help="hackdb sqlite of the ROM being played (default build/hackdb-Mercury_EN.sqlite; "
                    "build one with scripts/hackdb.py build --rom ROM)")
    ap.add_argument("--starter", choices=["chikorita", "totodile", "cyndaquil"], help="force the starter (default: Jev decides)")
    ap.add_argument("--stall", type=int, default=25, help="actions without any state change before an anomaly")
    a = ap.parse_args(argv)
    e = Emu()
    import navmap
    import goals
    dex, nav, planner = ob.Dex(), navmap.NavMap(a.hackdb or navmap.DB), None
    gn = lambda s: tuple(map(int, s.split(".")))
    if a.target:
        planner = goals.make_planner(nav, dex, gn(a.target), gn(a.heal_map) if a.heal_map else None, a.heal_route.split(),
                                     a.min_conf, a.log, cheat_heal=a.cheat_heal)
    code, msg, info = play_loop(e, dex, a.until, a.route.split(), a.goal, a.min_conf, a.log, a.max_actions, a.stall,
                                nav=nav, planner=planner, starter=a.starter)
    print(json.dumps({"exit": code, "result": msg, **info}))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
