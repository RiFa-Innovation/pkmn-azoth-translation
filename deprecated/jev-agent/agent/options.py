"""Legal actions for the current turn, each with the facts that decide it, plus a heuristic baseline.

The classifier does no arithmetic: every option carries its type multiplier, an estimated damage range as % of the target's
current HP, KO odds, accuracy and turn order. The damage estimate is the Gen 5+ formula with stat stages, STAB and a Gen 6
type chart; it ignores abilities, items, weather, crits and variable-power moves (power <= 1), so treat it as a guide.
"""
TYPES = ["Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost", "Steel", "???", "Fire", "Water", "Grass",
         "Electric", "Psychic", "Ice", "Dragon", "Dark", "Fairy"]

_SE, _NVE, _IMM = {}, {}, {}


def _chart(table, rows):
    for atk, defs in rows.items():
        table[TYPES.index(atk)] = {TYPES.index(d) for d in defs.split()}


_chart(_SE, {"Fighting": "Normal Rock Steel Ice Dark", "Flying": "Fighting Bug Grass", "Poison": "Grass Fairy",
             "Ground": "Poison Rock Steel Fire Electric", "Rock": "Flying Bug Fire Ice", "Bug": "Grass Psychic Dark",
             "Ghost": "Ghost Psychic", "Steel": "Rock Ice Fairy", "Fire": "Bug Steel Grass Ice", "Water": "Ground Rock Fire",
             "Grass": "Ground Rock Water", "Electric": "Flying Water", "Psychic": "Fighting Poison", "Ice": "Flying Ground Grass Dragon",
             "Dragon": "Dragon", "Dark": "Ghost Psychic", "Fairy": "Fighting Dragon Dark"})
_chart(_NVE, {"Normal": "Rock Steel", "Fighting": "Flying Poison Bug Psychic Fairy", "Flying": "Rock Steel Electric",
              "Poison": "Poison Ground Rock Ghost", "Ground": "Bug Grass", "Rock": "Fighting Ground Steel", "Bug":
              "Fighting Flying Poison Ghost Steel Fire Fairy", "Ghost": "Dark", "Steel": "Steel Fire Water Electric",
              "Fire": "Rock Fire Water Dragon", "Water": "Water Grass Dragon", "Grass": "Flying Poison Bug Steel Fire Grass Dragon",
              "Electric": "Grass Electric Dragon", "Psychic": "Steel Psychic", "Ice": "Steel Fire Water Ice", "Dragon": "Steel",
              "Dark": "Fighting Dark Fairy", "Fairy": "Poison Steel Fire"})
_chart(_IMM, {"Normal": "Ghost", "Fighting": "Ghost", "Poison": "Steel", "Ground": "Flying", "Ghost": "Normal",
              "Electric": "Ground", "Psychic": "Dark", "Dragon": "Fairy"})


def effectiveness(atk_type, def_types):
    m = 1.0
    for d in def_types:
        if d in _IMM.get(atk_type, ()):
            return 0.0
        if d in _SE.get(atk_type, ()):
            m *= 2
        elif d in _NVE.get(atk_type, ()):
            m *= 0.5
    return m


def stage_mult(s):
    return (2 + s) / 2 if s >= 0 else 2 / (2 - s)


def damage_range(attacker, move, defender, use_stages=True):
    """(min, max) HP damage; None for status or variable-power moves."""
    if move["split"] == 2 or not move["power"] or move["power"] <= 1:
        return None
    a_key, d_key = ("atk", "def") if move["split"] == 0 else ("spa", "spd")
    a = attacker["stats"][a_key] * (stage_mult(attacker.get("stages", {}).get(a_key, 0)) if use_stages else 1)
    d = defender["stats"][d_key] * (stage_mult(defender.get("stages", {}).get(d_key, 0)) if use_stages else 1)
    if attacker.get("status") == "burn" and move["split"] == 0:
        a /= 2
    base = int(int(int(2 * attacker["level"] / 5 + 2) * move["power"] * a / max(d, 1)) / 50) + 2
    mult = effectiveness(move["type"], defender["types"]) * (1.5 if move["type"] in attacker["types"] else 1)
    return int(base * 0.85 * mult), int(base * mult)


def speed(mon):
    s = mon["stats"]["spe"] * stage_mult(mon.get("stages", {}).get("spe", 0))
    return s / 2 if mon.get("status") == "paralysis" else s


def _effect_word(m):
    return {0.0: "no effect", 0.25: "barely effective", 0.5: "not very effective", 1.0: "neutral",
            2.0: "super effective", 4.0: "4x super effective"}.get(m, f"{m}x")


def foe_threat(state, target):
    """Best estimated damage the foe's known moves do to `target`, as % of its current HP (None if no damaging move)."""
    best = None
    for mv in state["foe"]["moves"]:
        r = damage_range(state["foe"], mv, target, use_stages=target is state["you"])
        if r and target["hp"]:
            pct = round(100 * r[1] / target["hp"])
            if best is None or pct > best[1]:
                best = (mv["name"], pct)
    return best


def build(state):
    """Returns [{"key", "label", "kind", "facts": {...}, "desc"}] — `desc` is what the classifier reads for the option."""
    you, foe = state["you"], state["foe"]
    opts = []
    you_first = speed(you) >= speed(foe)
    for mv in you["moves"]:
        if mv["pp"] <= 0:
            continue
        eff = effectiveness(mv["type"], foe["types"])
        r = damage_range(you, mv, foe)
        acc = mv["accuracy"] or 100
        first = mv["priority"] > 0 or (mv["priority"] == 0 and you_first)
        facts = {"move": mv["name"], "type": TYPES[mv["type"]], "power": mv["power"], "accuracy": acc, "pp": mv["pp"],
                 "category": ["physical", "special", "status"][mv["split"]], "effectiveness": eff, "moves_first": first}
        if r:
            lo, hi = (round(100 * x / max(foe["hp"], 1)) for x in r)
            facts.update(dmg_pct=[min(lo, 100), min(hi, 100)], ko="sure" if lo >= 100 else "possible" if hi >= 100 else "no")
            desc = (f"Use {mv['name']} ({TYPES[mv['type']]}, {_effect_word(eff)}): ~{min(lo, 100)}-{min(hi, 100)}% of foe's "
                    f"HP, {acc}% acc, {'goes first' if first else 'goes second'}" + (", KOs" if lo >= 100 else
                                                                                      ", may KO" if hi >= 100 else ""))
        else:
            desc = (f"Use {mv['name']} ({TYPES[mv['type']]} {facts['category']} move"
                    f"{', power varies' if mv['split'] != 2 else ''}), {acc}% acc")
        opts.append({"key": f"move{mv['slot']}", "kind": "move", "slot": mv["slot"], "facts": facts, "desc": desc})
    for p in state["party"]:
        if p["active"] or p["hp"] == 0:
            continue
        threat = foe_threat(state, p)
        best = max((effectiveness(t, foe["types"]) for t in p["types"]), default=1.0)
        facts = {"switch_to": p["name"], "hp_pct": p["hp_pct"], "level": p["level"],
                 "takes_pct": threat[1] if threat else 0, "stab_vs_foe": best}
        desc = (f"Switch to {p['name']} (Lv{p['level']}, {p['hp_pct']}% HP): foe's best hit ~{threat[1] if threat else 0}% of "
                f"its HP; its type is {_effect_word(best)} against the foe")
        opts.append({"key": f"switch{p['slot']}", "kind": "switch", "slot": p["slot"], "facts": facts, "desc": desc})
    if state["kind"] == "wild":
        opts.append({"key": "run", "kind": "run", "facts": {}, "desc": "Run away from the wild Pokemon"})
    return opts


def context(state):
    """Compact situation summary the classifier reads with the options."""
    you, foe = state["you"], state["foe"]
    threat = foe_threat(state, you)
    return {"battle": state["kind"],
            "you": {k: you[k] for k in ("name", "level", "hp_pct", "status")} | {"types": [TYPES[t] for t in you["types"]]},
            "foe": {k: foe[k] for k in ("name", "level", "hp_pct", "status", "ability")} | {"types": [TYPES[t] for t in foe["types"]]},
            "you_move_first": speed(you) >= speed(foe),
            "foe_best_hit_on_you_pct": threat[1] if threat else 0,
            "healthy_teammates": sum(1 for p in state["party"] if not p["active"] and p["hp"] > 0)}


def heuristic(state, opts, goal="win"):
    """Baseline: run if asked; switch out of a sure KO to a teammate that takes far less; else best expected damage."""
    by = {o["key"]: o for o in opts}
    if goal == "flee" and "run" in by:
        return "run"
    moves = [o for o in opts if o["kind"] == "move"]
    sure = [o for o in moves if o["facts"].get("ko") == "sure"]
    if sure:
        return max(sure, key=lambda o: (o["facts"]["moves_first"], o["facts"]["accuracy"]))["key"]
    threat = foe_threat(state, state["you"])
    you_die = threat and threat[1] >= 100
    if you_die and not any(o["facts"].get("ko") == "possible" and o["facts"]["moves_first"] for o in moves):
        safe = [o for o in opts if o["kind"] == "switch" and o["facts"]["takes_pct"] < 50]
        if safe:
            return min(safe, key=lambda o: o["facts"]["takes_pct"])["key"]

    def ev(o):
        d = o["facts"].get("dmg_pct")
        return (sum(d) / 2 if d else 0) * o["facts"]["accuracy"] / 100
    if moves:
        return max(moves, key=ev)["key"]
    switches = [o for o in opts if o["kind"] == "switch"]  # replacement: least damage taken, then hits back hardest
    if switches:
        return min(switches, key=lambda o: (o["facts"]["takes_pct"], -o["facts"]["stab_vs_foe"]))["key"]
    return opts[0]["key"]
