"""Run the goal book: find the first goal that is not done (live game state), play it, check it, journal it, checkpoint, repeat.

    python3 deprecated/jev-agent/agent/quest.py [--new-game] [--until GOAL_ID] [--starter NAME] [--cheat-heal] [--max-goals N] [--sav PATH]

--new-game  boot-to-bedroom first (bootstrap.py), for a fresh boot with no save.
Stops when all goals are done, at --until, when a goal's `do` finished but its `done` condition still fails (marked blocked and journaled,
with the anomaly report if the loop raised one): that is where a person or a larger model reasons about what the game needs next, then
edits deprecated/jev-agent/data/agent_goals.json. Run `goalbook.py render` to refresh deprecated/jev-agent/docs/AGENT_GOALS.md.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # repo root (this folder is deprecated/jev-agent/agent)
PKG = os.path.dirname(HERE)  # deprecated/jev-agent
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import bootstrap  # noqa: E402
import decide as dc  # noqa: E402
import goalbook as gb  # noqa: E402
import goals as gl  # noqa: E402
import navmap  # noqa: E402
import observe as ob  # noqa: E402
import play  # noqa: E402
import savegame  # noqa: E402
import play_loop as pl  # noqa: E402

CHECKPOINTS = os.path.join(gb.ROOT, "saves/agent/checkpoints")


def maybe_cheat_heal(e, dex, min_conf, log):
    party = ob.party(e, dex)
    if not party:
        return
    f = gl.team_facts(party)
    needs = f["fainted"] > 0 or f["team_hp_pct"] < 60
    opts = {"continue": "Carry on with the team as it is",
            "cheat_heal": f"Restore the whole team instantly (playtest heal); team HP {f['team_hp_pct']}%, {f['fainted']} fainted"}
    rec = dc.choose(f, opts, dc.INSTRUCTIONS["goal"], "cheat_heal" if needs else "continue", min_conf, "goal")
    open(log, "a").write(json.dumps(rec) + "\n")
    if rec["action"] == "cheat_heal":
        import cheats
        print(f"cheat heal [{rec['source']}]: {cheats.heal_party(e, dex)} members")


def run(a):
    from emu import Emu
    e, dex = Emu(), ob.Dex()
    nav = navmap.NavMap(a.hackdb or navmap.DB)
    os.makedirs(CHECKPOINTS, exist_ok=True)
    if a.new_game:
        gb.journal("new_game", detail=str(bootstrap.new_game(e, dex)))
    done_n = 0
    while done_n < a.max_goals:
        goals = gb.load()
        g, why = gb.next_goal(e, goals)
        if g is None:
            print(why)
            gb.journal("idle", reason=why)
            return 0
        if a.cheat_heal:
            maybe_cheat_heal(e, dex, a.min_conf, a.log)
        print(f"== goal {g['id']}: {g['title']}")
        gb.journal("start", goal=g["id"], detail=f"map {play.pos(e)[2:]}")
        code, msg, info = pl.play_loop(e, dex, None, g["do"], "win", a.min_conf, a.log, a.max_actions, 25, nav=nav, starter=a.starter)
        for _ in range(3):  # settle: a scene can be between text boxes when the route ends, so drain scripts before judging
            if code != 3 or gb.evaluate(e, g["done"]):
                break
            e.wait(120)
            code, msg, info2 = pl.play_loop(e, dex, None, [], "win", a.min_conf, a.log, a.max_actions, 25, nav=nav, starter=a.starter)
        ok = gb.evaluate(e, g["done"])
        if ok:
            gb.journal("done", goal=g["id"], detail=f"{msg}; battles {info['battles']}")
            if g["status"] != "verified":
                gb.set_status(g["id"], "verified")
            if g.get("checkpoint"):
                base = os.path.join(CHECKPOINTS, g["checkpoint"])
                detail = []
                if a.sav:
                    savegame.save_game(e)
                    e.wait(300)  # let the core flush the flash to the file
                    detail.append(savegame.export_sav(a.sav, base + ".sav"))
                e.save_state(os.path.abspath(base + ".ss"))
                detail.append(base + ".ss")
                gb.journal("checkpoint", goal=g["id"], detail=" + ".join(detail))
            done_n += 1
            if a.until == g["id"]:
                return 0
            continue
        gb.journal("blocked", goal=g["id"], reason=msg)
        gb.set_status(g["id"], "blocked", notes=(g.get("notes") or "") + f" [blocked {gb.time.strftime('%Y-%m-%d')}: {msg[:200]}]")
        print(f"BLOCKED at {g['id']}: {msg}")
        return 2
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-game", action="store_true")
    ap.add_argument("--until")
    ap.add_argument("--starter", choices=["chikorita", "totodile", "cyndaquil"])
    ap.add_argument("--cheat-heal", action="store_true")
    ap.add_argument("--min-conf", type=float, default=0.5)
    ap.add_argument("--log", default="saves/agent/decisions.jsonl")
    ap.add_argument("--max-actions", type=int, default=3000)
    ap.add_argument("--max-goals", type=int, default=100)
    ap.add_argument("--hackdb")
    ap.add_argument("--sav", help="the running emulator's .sav path (boot with a blank one + RHT_LOAD_SAVE=1): in-game save at each checkpoint")
    sys.exit(run(ap.parse_args()))
