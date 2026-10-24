"""D9: overworld goal selection. Python works out the facts (party health, hops to the target and to a heal spot); Jev chooses
between `continue` (travel toward the story target) and `heal` (go to a known healer first). Returns route tokens for play_loop.
"""
import json

import decide as dc
import observe as ob
import play


def team_facts(party):
    alive = [m for m in party if m["hp"] > 0]
    tot = sum(m["max_hp"] for m in party) or 1
    return {"members": len(party), "fainted": len(party) - len(alive),
            "team_hp_pct": round(100 * sum(m["hp"] for m in party) / tot), "lowest_hp_pct": min((m["hp_pct"] for m in party), default=0)}


def make_planner(nav, dex, target, heal=None, heal_route=(), min_conf=0.5, log=None, max_heals=5, cheat_heal=False):
    """target = (g, n); heal = (g, n) of a map with a healer, heal_route = tokens that heal once inside it."""
    state = {"heals": 0, "last_hp": None, "broken": False}

    def plan(e):
        cur = play.pos(e)[2:]
        if cur == target:
            return None
        facts = team_facts(ob.party(e, dex))
        if state["last_hp"] is not None and facts["team_hp_pct"] <= state["last_hp"]:
            state["broken"] = True  # the last heal trip did not raise team HP: the heal route is wrong, stop offering it
            print("goal: the last heal did not raise team HP; heal disabled")
        state["last_hp"] = None
        to_target = nav.hops(cur, target)
        opts = {"continue": f"Travel toward map {target[0]}.{target[1]} ({'no known route' if to_target is None else f'{to_target} map hops'})"}
        to_heal = nav.hops(cur, heal) if heal else None
        if heal and to_heal is not None and state["heals"] < max_heals and not state["broken"]:
            opts["heal"] = f"Go to the healer first ({to_heal} map hops), then resume; team HP {facts['team_hp_pct']}%, {facts['fainted']} fainted"
        if cheat_heal:
            opts["cheat_heal"] = (f"Restore the whole team instantly with the playtest heal (no travel); team HP {facts['team_hp_pct']}%, "
                                  f"{facts['fainted']} fainted")
        needs = facts["fainted"] > 0 or facts["team_hp_pct"] < 50 or facts["lowest_hp_pct"] < 20
        heuristic = ("cheat_heal" if "cheat_heal" in opts else "heal" if "heal" in opts else "continue") if needs else "continue"
        ctx = {**facts, "hops_to_target": to_target, "hops_to_healer": to_heal, "heals_done": state["heals"]}
        rec = dc.choose(ctx, opts, dc.INSTRUCTIONS["goal"], heuristic, min_conf, "goal")
        if log:
            with open(log, "a") as f:
                f.write(json.dumps(rec) + "\n")
        print(f"goal: {rec['action']} [{rec['source']}] {ctx}")
        if rec["action"] == "cheat_heal":
            return ["!heal"]
        if rec["action"] == "heal":
            state["heals"] += 1
            state["last_hp"] = facts["team_hp_pct"]
            return [f"@{heal[0]}.{heal[1]}", *heal_route]
        return [f"@{target[0]}.{target[1]}"]

    return plan
