"""Spectrum Frontier opponent set generator (docs/BATTLE_FRONTIER_SPEC.md, section 7).

    python3 scripts/frontier_sets.py [--rom ROM] [--seed N] [--out data/frontier/sets.json]
                                     [--bin build/frontier/sets.bin] [--samples build/frontier/sample_teams.md] [--check]

Reads species, moves, learnsets and evolutions out of the ROM (frontier_data.py) and the rules in data/frontier/pool.json, builds one
or two Lv 50 sets per eligible species, validates them, and writes
  * data/frontier/sets.json   committed; species/moves/items by NAME and id, no ROM bytes
  * build/frontier/sets.bin   the packed 24-byte records that go into the ROM (not committed)
  * build/frontier/sample_teams.md   20 random 3-mon teams per tier for human review
The output is a pure function of (ROM data, pool.json, seed).

Packed record (24 bytes, little endian):
  u16 species, u16 item, u16 moves[4], u16 moves_doubles[4], u8 spread, u8 ability_slot, u8 tier (1..4), u8 flags
  flags: bit0 mega (holds the Mega Stone), bit1 legendary (max one per team), bit2 nfe (Eviolite), bit3 boss only
"""
import argparse
import collections
import json
import os
import random
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import frontier_data as fd  # noqa: E402

DEFAULT_ROM = os.path.join(ROOT, "roms/Pokemon Mercury 1.3.3 (patched).gba")
NATURES = ["Hardy", "Lonely", "Brave", "Adamant", "Naughty", "Bold", "Docile", "Relaxed", "Impish", "Lax", "Timid", "Hasty", "Serious",
           "Jolly", "Naive", "Modest", "Mild", "Quiet", "Bashful", "Rash", "Calm", "Gentle", "Sassy", "Careful", "Quirky"]
TYPE_NAMES = {0: "Normal", 1: "Fighting", 2: "Flying", 3: "Poison", 4: "Ground", 5: "Rock", 6: "Bug", 7: "Ghost", 8: "Steel", 10: "Fire",
              11: "Water", 12: "Grass", 13: "Electric", 14: "Psychic", 15: "Ice", 16: "Dragon", 17: "Dark", 23: "Fairy"}
SPECIAL_TYPES = {10, 11, 12, 13, 14, 15, 16, 17, 23}
# attacking type -> defending types it hits for x2 (Gen 6+ chart; ids as in this ROM, Fairy = 23)
SUPER = {0: [], 1: [0, 5, 8, 15, 17], 2: [1, 6, 12], 3: [12, 23], 4: [3, 5, 8, 10, 13], 5: [2, 6, 10, 15], 6: [12, 14, 17],
         7: [7, 14], 8: [5, 15, 23], 10: [6, 8, 12, 15], 11: [4, 5, 10], 12: [4, 5, 11], 13: [2, 11], 14: [1, 3], 15: [2, 4, 12, 16],
         16: [16], 17: [7, 14], 23: [1, 16, 17]}
TIER_ID = {"T1": 1, "T2": 2, "T3": 3, "T4": 4}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


class Ctx:
    def __init__(self, rom, pool):
        self.pool = pool
        self.sp, mv = fd.load(rom)
        self.mv = mv
        self.mv_by_norm = {}
        for m in mv.values():
            self.mv_by_norm.setdefault(norm(m["name"]), m["id"])
        items = {}
        for fn in ("items2.json", "items.json"):
            items.update(json.load(open(os.path.join(ROOT, "text/en/tables", fn))))
        self.items = {int(k): v for k, v in items.items()}
        self.item_by_norm = {}
        for k, v in self.items.items():
            self.item_by_norm.setdefault(norm(v), k)
        self.ab = {int(k): v for k, v in json.load(open(os.path.join(ROOT, "text/en/tables/abilities.json"))).items()}
        self.sp_by_norm = {}
        for s in self.sp.values():
            self.sp_by_norm.setdefault(norm(s["name"]), []).append(s["id"])
        self.unresolved = set()
        # alternate forms are the targets of method 253/254 entries that point to a HIGHER id (the form lists a reversion entry back to its base)
        self.forms = {e["to"] for s in self.sp.values() for e in s["evos"] if e["method"] in (253, 254) and e["to"] > s["id"]}
        self.mega_of = {s["id"]: e["to"] for s in self.sp.values() for e in s["evos"] if e["method"] == 254 and e["to"] > s["id"]}
        self.ban = self._ids(pool["ban_species"])
        self.legend = self._ids(pool["legendary"])
        self.boss_only = self._ids(pool["boss_only"])
        self.move_ban = self._mids(pool["move_ban"])
        self.penalty = {}
        for n, f in pool["move_penalty"].items():
            i = self.mid(n)
            if i:
                self.penalty[i] = f
        self.setup = self._mids(pool["setup_moves"])
        self.recovery = self._mids(pool["recovery_moves"])
        self.status = self._mids(pool["status_moves"])
        self.protect = self._mids(pool["protect_moves"])
        self.doubles = self._mids(pool["doubles_moves"])
        self.universal_tm = self._mids(pool["universal_tm"])
        self.tm_attack = {}
        for tname, lst in pool["tm_attacks"].items():
            t = [k for k, v in TYPE_NAMES.items() if v == tname][0]
            self.tm_attack[t] = self._mids(lst)
        self.explicit = self.setup | self.recovery | self.status | self.protect | self.doubles | self.universal_tm
        self.ab_prefer = {norm(n): len(pool["ability_prefer"]) - i for i, n in enumerate(pool["ability_prefer"])}
        self.ab_avoid = {norm(n) for n in pool["ability_avoid"]}

    def _ids(self, names):
        out = set()
        for n in names:
            ids = self.sp_by_norm.get(norm(n))
            if ids:
                out.update(ids)
            else:
                self.unresolved.add(("species", n))
        return out

    def mid(self, name):
        i = self.mv_by_norm.get(norm(name))
        if not i:
            self.unresolved.add(("move", name))
        return i

    def _mids(self, names):
        return {i for i in (self.mid(n) for n in names) if i}

    def item(self, name):
        i = self.item_by_norm.get(norm(name))
        if not i:
            self.unresolved.add(("item", name))
        return i

    def setup_ok_set(self, ok):
        return {m for m in self.setup if ok(m)}

    def banned_move(self, mid):
        return mid in self.move_ban and mid not in self.explicit


def category(m):
    """Real per-move split from the ROM (move struct byte 10 & 3); falls back to the Gen 3 type rule if absent."""
    sp = m.get("split")
    if sp == 1:
        return "special"
    if sp == 0:
        return "physical"
    return "special" if m["type"] in SPECIAL_TYPES else "physical"


def stats(s):
    hp, atk, df, spe, spa, spd = s["stats"]
    return hp, atk, df, spe, spa, spd


def role_scores(s):
    hp, atk, df, spe, spa, spd = stats(s)
    bulk = (hp + df + spd) / 3.0
    off = max(atk, spa)
    return {
        "phys_sweeper": atk + 0.8 * spe if atk >= spa * 0.9 else -1,
        "spec_sweeper": spa + 0.8 * spe if spa >= atk * 0.9 else -1,
        "phys_bulky": 0.9 * atk + 0.9 * bulk if atk >= spa * 0.9 else -1,
        "spec_bulky": 0.9 * spa + 0.9 * bulk if spa >= atk * 0.9 else -1,
        "support": 1.2 * bulk - 0.2 * off if bulk >= 70 else -1,
    }


def pick_roles(s):
    sc = role_scores(s)
    hp, atk, df, spe, spa, spd = stats(s)
    ok = []
    off = max(atk, spa)
    for r, v in sc.items():
        if v < 0:
            continue
        if r.endswith("sweeper") and (off < 85 or spe < 65):
            continue
        if r.endswith("bulky") and (off < 70 or (hp + df + spd) / 3.0 < 85):
            continue
        if r == "support" and (hp + df + spd) / 3.0 < 80:
            continue
        ok.append((v, r))
    ok.sort(reverse=True)
    if not ok:
        return ["phys_sweeper" if atk >= spa else "spec_sweeper"]
    roles = [ok[0][1]]
    fam = ok[0][1].split("_")[-1]
    for v, r in ok[1:]:
        if len(roles) < 2 and r.split("_")[-1] != fam and v >= 0.9 * ok[0][0]:
            roles.append(r)
    return roles


def learn_ids(s, upto=50):
    return [l["move"] for l in s["learnset"] if l["level"] <= upto]


def candidate_moves(ctx, s):
    """move id -> source ('lv' level-up, 'tm' curated pool)."""
    hp, atk, df, spe, spa, spd = stats(s)
    out = {m: "lv" for m in learn_ids(s)}
    for t in s["types"]:
        for m in ctx.tm_attack.get(t, ()):
            mv = ctx.mv[m]
            stat = spa if category(mv) == "special" else atk
            if stat >= 80:
                out.setdefault(m, "tm")
    for t, lst in ctx.tm_attack.items():
        if t in s["types"]:
            continue
        for m in lst:
            mv = ctx.mv[m]
            stat = spa if category(mv) == "special" else atk
            if stat >= 100 and mv["power"] >= 70:
                out.setdefault(m, "tm")
    for m in ctx.universal_tm:
        mv = ctx.mv[m]
        nm = norm(mv["name"])
        if nm in ("swordsdance", "bulkup") and atk < 95:
            continue
        if nm == "calmmind" and spa < 95:
            continue
        out.setdefault(m, "tm")
    return {m: src for m, src in out.items() if not ctx.banned_move(m) and m in ctx.mv}


def attack_score(ctx, s, mid):
    mv = ctx.mv[mid]
    if mv["power"] < 40:
        return 0.0
    hp, atk, df, spe, spa, spd = stats(s)
    cat = category(mv)
    stat = spa if cat == "special" else atk
    top = max(atk, spa)
    v = mv["power"] * (min(mv["accuracy"], 100) or 100) / 100.0
    if mv["type"] in s["types"]:
        v *= 1.5
    v *= (stat / float(top)) ** 2
    v *= ctx.penalty.get(mid, 1.0)
    if mv["priority"] > 0:
        v *= 1.1
    return v


def pick_attacks(ctx, s, cands, n, avoid=()):
    atk_ids = [m for m in cands if ctx.mv[m]["power"] >= 40 and m not in avoid]
    scored = {m: attack_score(ctx, s, m) for m in atk_ids}
    chosen = []
    covered = set()
    types = set()
    # first pick: best STAB
    stab = [m for m in atk_ids if ctx.mv[m]["type"] in s["types"]]
    pool1 = stab or atk_ids
    if not pool1:
        return chosen
    first = max(pool1, key=lambda m: scored[m])
    chosen.append(first)
    types.add(ctx.mv[first]["type"])
    covered.update(SUPER.get(ctx.mv[first]["type"], []))
    while len(chosen) < n:
        best, bv = None, 0
        for m in atk_ids:
            if m in chosen or ctx.mv[m]["type"] in types:
                continue
            new = set(SUPER.get(ctx.mv[m]["type"], [])) - covered
            v = scored[m] * (1 + 0.07 * len(new))
            if ctx.mv[m]["type"] in s["types"]:
                v *= 1.15
            if v > bv:
                best, bv = m, v
        if best is None:
            # allow a second move of an already used type
            rest = [m for m in atk_ids if m not in chosen]
            if not rest:
                break
            best = max(rest, key=lambda m: scored[m])
        chosen.append(best)
        types.add(ctx.mv[best]["type"])
        covered.update(SUPER.get(ctx.mv[best]["type"], []))
    return chosen


def first_in(ids, cands, rng=None):
    c = sorted(m for m in ids if m in cands)
    if not c:
        return None
    return rng.choice(c) if rng else c[0]


def build_moves(ctx, s, role, cands, rng=None):
    hp, atk, df, spe, spa, spd = stats(s)
    phys = role.startswith("phys")
    want_cat = "physical" if phys else "special"
    if role == "support":
        want_cat = "physical" if atk >= spa else "special"
    # bias candidate attacks to the role's category (keep off-category only as coverage when strong)
    top = max(atk, spa)
    def cat_ok(m):
        mv = ctx.mv[m]
        if mv["power"] < 40:
            return True
        stat = spa if category(mv) == "special" else atk
        return category(mv) == want_cat or stat >= 0.85 * top
    ac = {m: src for m, src in cands.items() if cat_ok(m)}
    setup = [m for m in cands if m in ctx.setup and cands[m] in ("lv", "tm")]
    # only matching setup: physical setup for physical roles etc.
    PHYS_SETUP = {"swordsdance", "bulkup", "honeclaws", "coil", "workup"}
    SPEC_SETUP = {"nastyplot", "calmmind", "quiverdance", "growth"}
    def setup_ok(m):
        nm = norm(ctx.mv[m]["name"])
        if nm in PHYS_SETUP:
            return want_cat == "physical" and atk >= 90
        if nm in SPEC_SETUP:
            return want_cat == "special" and spa >= 90
        return True      # Agility, Dragon Dance, Shell Smash, Iron Defense, Amnesia, Curse, Shift Gear ...
    setup = [m for m in setup if setup_ok(m)]
    recov = [m for m in cands if m in ctx.recovery]
    real_recov = [m for m in recov if norm(ctx.mv[m]["name"]) != "rest"]
    recov = real_recov or ([] if [m for m in cands if m in ctx.status] else recov)
    status = [m for m in cands if m in ctx.status]
    prot = [m for m in cands if m in ctx.protect]
    moves = []
    if role.endswith("sweeper"):
        su = first_in(setup, cands)
        if su and (spe >= 80 or role == "phys_sweeper"):
            moves.append(su)
        atks = pick_attacks(ctx, s, ac, 4 - len(moves) if not moves else 3, avoid=moves)
        moves = atks + moves if len(moves) else atks
        if len(moves) < 4:
            p = first_in(prot, cands)
            if p and p not in moves:
                moves.append(p)
    elif role.endswith("bulky"):
        atks = pick_attacks(ctx, s, ac, 2)
        moves += atks
        r = first_in(recov, cands)
        if r:
            moves.append(r)
        else:
            st = first_in(status, cands, rng)
            if st:
                moves.append(st)
        p = first_in(prot, cands, rng)
        if p and p not in moves:
            moves.append(p)
        if len(moves) < 4:
            more = pick_attacks(ctx, s, ac, 4, avoid=moves)
            for m in more:
                if m not in moves and len(moves) < 4:
                    moves.append(m)
    else:  # support
        atks = pick_attacks(ctx, s, ac, 2)
        moves += atks[:1]
        for lst in (status, recov, prot):
            m = first_in(lst, cands, rng)
            if m and m not in moves and len(moves) < 4:
                moves.append(m)
        for m in atks[1:] + pick_attacks(ctx, s, ac, 4, avoid=moves):
            if m not in moves and len(moves) < 4:
                moves.append(m)
    # fill to 4: on-category attacks first, then useful utility, off-category attacks only as a last resort
    def fill(pool_ids):
        for m in sorted(pool_ids, key=lambda m: attack_score(ctx, s, m), reverse=True):
            if len(moves) >= 4:
                return
            if m not in moves:
                moves.append(m)
    if len(moves) < 4:
        fill([m for m in ac if ctx.mv[m]["power"] >= 40])
    if len(moves) < 4:
        fill([m for m in cands if m in ctx.protect or m in ctx.status or m in ctx.setup_ok_set(setup_ok)])
    if len(moves) < 3:
        fill([m for m in cands if ctx.mv[m]["power"] >= 2])
    seen, out = set(), []
    for m in moves:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out[:4]


def doubles_variant(ctx, s, moves, cands):
    """Same set, but ensure Protect and swap a weak slot for a doubles move the species learns by level-up."""
    out = list(moves)
    def weakest():
        idx = [i for i, m in enumerate(out)
               if ctx.mv[m]["power"] >= 40]
        if len(idx) <= 2:
            idx = list(range(len(out)))
        return min(idx, key=lambda i: attack_score(ctx, s, out[i]) if ctx.mv[out[i]]["power"] >= 40 else 999)
    prot = first_in([m for m in cands if m in ctx.protect and norm(ctx.mv[m]["name"]) == "protect"], cands)
    if prot and prot not in out and len(out) >= 3:
        # keep at least two attacks
        if sum(1 for m in out if ctx.mv[m]["power"] >= 40) > 2 or len(out) < 4:
            if len(out) < 4:
                out.append(prot)
            else:
                out[weakest()] = prot
    learn = set(learn_ids(s))
    support = [m for m in learn if m in ctx.doubles and ctx.mv[m]["power"] < 40 and m not in out]
    if support and len(out) == 4 and sum(1 for m in out if ctx.mv[m]["power"] >= 40) > 2:
        out[weakest()] = support[0]
    return out


def choose_ability(ctx, s):
    names = []
    for slot, a in enumerate(s["abilities"]):
        if a and a in ctx.ab:
            names.append((slot, ctx.ab[a]))
    if not names:
        return 0, None
    def score(nm):
        n = norm(nm)
        if n in ctx.ab_avoid:
            return -100
        return ctx.ab_prefer.get(n, 0)
    best = max(names, key=lambda x: (score(x[1]), -x[0]))
    return best[0], best[1]


def choose_item(ctx, s, role, tier, moves, nfe, mega, rng, ability):
    pool = ctx.pool["items"]
    hp, atk, df, spe, spa, spd = stats(s)
    mi = ctx.mv
    has_protect = any(m in ctx.protect and norm(mi[m]["name"]) == "protect" for m in moves)
    all_attacks = all(mi[m]["power"] >= 40 for m in moves)
    if mega:
        return ctx.item(pool["mega"][0])
    if nfe:
        return ctx.item(pool["nfe"][0])
    frail = hp + df + spd < 250
    opts = []
    top_type = [mi[m]["type"] for m in moves if mi[m]["power"] >= 40 and mi[m]["type"] in s["types"]]
    boost = pool["type_boost"].get(TYPE_NAMES.get(top_type[0])) if top_type else None
    if role.endswith("sweeper"):
        phys = role.startswith("phys")
        if tier >= 3 and all_attacks and not has_protect:
            opts += pool["choice_phys" if phys else "choice_spec"] * 2
            if spe >= 100 and tier >= 3:
                opts += pool["choice_speed"]
        if frail:
            opts += pool["sash"] * 2
        opts += pool["orb"] if tier >= 2 else []
        if boost:
            opts.append(boost)
        if tier <= 2:
            opts += pool["weak_phys" if phys else "weak_spec"]
    elif role.endswith("bulky"):
        opts += pool["bulky"]
        if boost:
            opts.append(boost)
        if tier >= 3:
            opts += pool["orb"]
    else:
        opts += pool["support"]
    opts = [o for o in opts if o]
    if not opts:
        opts = ["Sitrus Berry"]
    rng.shuffle(opts)
    return ctx.item(opts[0])


def choose_spread(role, s):
    hp, atk, df, spe, spa, spd = stats(s)
    if role == "phys_sweeper":
        return "phys_fast" if spe >= 75 else "phys_strong"
    if role == "spec_sweeper":
        return "spec_fast" if spe >= 75 else "spec_strong"
    if role == "phys_bulky":
        return "phys_bulky"
    if role == "spec_bulky":
        return "spec_bulky"
    return "wall_def" if df >= spd else "wall_spd"


def tier_of(ctx, bst):
    for t, (lo, hi) in ctx.pool["tiers"].items():
        if lo <= bst <= hi:
            return TIER_ID[t]
    return 4 if bst > 700 else 1


def eligible(ctx):
    out = []
    seen = set()
    for s in sorted(ctx.sp.values(), key=lambda x: x["id"]):
        sid = s["id"]
        key = (norm(s["name"]), tuple(s["stats"]), tuple(s["types"]))
        if key in seen:      # cosmetic forms (Pikachu caps, Vivillon patterns ...) share name, stats and types
            continue
        if sid in ctx.forms or sid in ctx.ban:
            continue
        real_evos = [e for e in s["evos"] if e["method"] not in (253, 254)]
        final = not real_evos
        if not final and s["bst"] < ctx.pool["nfe_min_bst"]:
            continue
        if s["bst"] < 300:
            continue
        seen.add(key)
        out.append((s, final))
    return out


def generate(ctx, seed):
    rng = random.Random(seed)
    sets = []
    for s, final in sorted(eligible(ctx), key=lambda x: x[0]["id"]):
        cands = candidate_moves(ctx, s)
        n_att = sum(1 for m in cands if ctx.mv[m]["power"] >= 40)
        if n_att < 2:
            continue
        slot, ab = choose_ability(ctx, s)
        roles = pick_roles(s)
        eff_bst = s["bst"] + (60 if not final else 0)
        tier = tier_of(ctx, eff_bst)
        made = []
        for role in roles:
            moves = build_moves(ctx, s, role, cands, rng)
            if len(moves) < 3 or not any(ctx.mv[m]["power"] >= 40 for m in moves):
                continue
            if tuple(moves) in made:
                continue
            made.append(tuple(moves))
            mv_d = doubles_variant(ctx, s, moves, cands)
            item = choose_item(ctx, s, role, tier, moves, not final, False, rng, ab)
            spread = choose_spread(role, s)
            flags = (1 if s["id"] in ctx.legend else 0) << 1 | (4 if not final else 0) | (8 if s["id"] in ctx.boss_only else 0)
            sets.append({"species": s["name"], "id": s["id"], "tier": tier, "role": role, "item": item, "ability_slot": slot, "ability": ab,
                         "spread": spread, "moves": moves, "moves_d": mv_d, "flags": flags, "bst": s["bst"],
                         "sources": [cands.get(m, "?") for m in moves]})
        # Mega set (generic Mega Stone), tier 4
        mega = ctx.mega_of.get(s["id"])
        if mega and final and made:
            role = roles[0]
            moves = list(made[0])
            mv_d = doubles_variant(ctx, s, moves, cands)
            sets.append({"species": s["name"], "id": s["id"], "tier": 4, "role": role, "item": ctx.item("Mega Stone"), "ability_slot": slot,
                         "ability": ab, "spread": choose_spread(role, s), "moves": moves, "moves_d": mv_d,
                         "flags": 1 | ((1 if s["id"] in ctx.legend else 0) << 1) | (8 if s["id"] in ctx.boss_only else 0),
                         "bst": s["bst"], "sources": [cands.get(m, "?") for m in moves], "mega_to": mega})
    return sets


def validate(ctx, sets):
    errs, warns = [], []
    seen = collections.Counter()
    for st in sets:
        s = ctx.sp[st["id"]]
        cands = candidate_moves(ctx, s)
        ms = st["moves"]
        if len(set(ms)) != len(ms):
            errs.append((st["species"], "duplicate move"))
        for m in ms + st["moves_d"]:
            if m not in ctx.mv:
                errs.append((st["species"], f"unknown move {m}"))
            elif m not in cands and not (m in ctx.doubles or m in ctx.protect):
                errs.append((st["species"], f"illegal move {ctx.mv[m]['name']}"))
        if len(ms) < 3:
            errs.append((st["species"], "fewer than 3 moves"))
        if not any(ctx.mv[m]["power"] >= 40 for m in ms):
            errs.append((st["species"], "no attack"))
        if not st["item"]:
            errs.append((st["species"], "missing item"))
        if st["ability"] is None:
            warns.append((st["species"], "no ability"))
        hp_, atk_, df_, spe_, spa_, spd_ = stats(s)
        top_ = max(atk_, spa_)
        off = sum(1 for m in ms if ctx.mv[m]["power"] >= 40 and (spa_ if category(ctx.mv[m]) == "special" else atk_) < 0.85 * top_)
        if off:
            warns.append((st["species"], f"{off} off-category attack(s)"))
        seen[(st["id"], st["role"], st["item"])] += 1
    tiers = collections.Counter(st["tier"] for st in sets)
    for t in (1, 2, 3, 4):
        if tiers[t] < 40:
            errs.append(("tiers", f"T{t} has only {tiers[t]} sets (<40)"))
    species = {st["id"] for st in sets}
    if len(species) < 60:
        errs.append(("species", f"only {len(species)} species"))
    dbl = sum(1 for st in sets if any(m in ctx.protect or m in ctx.doubles for m in st["moves_d"]))
    if dbl < 30:
        errs.append(("doubles", f"only {dbl} doubles-ready sets"))
    return errs, warns, tiers



def load_brains(ctx):
    """Hand-built Brain teams -> {name: [set dict]}, with legality errors/warnings."""
    data = json.load(open(os.path.join(ROOT, "data/frontier/brains.json")))
    out, errs, warns = {}, [], []
    for name, spec in data.items():
        if name.startswith("_"):
            continue
        team, species_seen, items_seen, megas = [], set(), set(), 0
        for e in spec["sets"]:
            ids = sorted(i for i in ctx.sp_by_norm.get(norm(e["species"]), []) if i not in ctx.forms)
            if not ids:
                errs.append((name, f"unknown species {e['species']}"))
                continue
            sid = ids[0]
            s = ctx.sp[sid]
            def mids(lst):
                res = []
                for n in lst:
                    i = ctx.mv_by_norm.get(norm(n))
                    if not i:
                        errs.append((name, f"{e['species']}: unknown move {n}"))
                    else:
                        res.append(i)
                return res
            mv = mids(e["moves"])
            md = mids(e.get("moves_d", e["moves"]))
            cands = candidate_moves(ctx, s)
            for m in mv + md:
                if m not in cands and m not in ctx.doubles and m not in ctx.protect:
                    warns.append((name, f"{e['species']}: {ctx.mv[m]['name']} is not level-up (<=50) or in the TM pool; hand pick, check it"))
            item = ctx.item(e["item"])
            if not item:
                errs.append((name, f"unknown item {e['item']}"))
            mega = item == ctx.item("Mega Stone")
            if mega:
                megas += 1
                if sid not in ctx.mega_of:
                    errs.append((name, f"{e['species']} has no Mega form"))
            if sid in species_seen:
                errs.append((name, f"duplicate species {e['species']}"))
            if item in items_seen:
                errs.append((name, f"duplicate item {e['item']}"))
            species_seen.add(sid)
            items_seen.add(item)
            slot, ab = choose_ability(ctx, s)
            team.append({"species": s["name"], "id": sid, "tier": 4, "role": "brain", "item": item, "item_name": e["item"], "ability_slot": slot,
                         "ability": ab, "spread": e["spread"], "moves": mv, "moves_d": md,
                         "flags": (1 if mega else 0) | (2 if sid in ctx.legend else 0) | 16, "bst": s["bst"],
                         "move_names": [ctx.mv[m]["name"] for m in mv], "move_names_d": [ctx.mv[m]["name"] for m in md]})
            if e["spread"] not in ctx.pool["spreads"]:
                errs.append((name, f"unknown spread {e['spread']}"))
        if megas > 1:
            errs.append((name, "more than one Mega"))
        out[name] = team
    return out, errs, warns


def pack(ctx, sets, header=False):
    """24-byte records. With header=True the records are sorted by tier and prefixed with a 20-byte index for the native generator:
    u16 total, u16 tier_start[4], u16 tier_count[4], u16 reserved (tiers 1..4; start counts records, not bytes)."""
    spread_ids = {n: i for i, n in enumerate(sorted(ctx.pool["spreads"]))}
    ordered = sorted(sets, key=lambda st: (st["tier"], st["id"])) if header else list(sets)
    blob = bytearray()
    for st in ordered:
        mv = (st["moves"] + [0] * 4)[:4]
        md = (st["moves_d"] + [0] * 4)[:4]
        blob += struct.pack("<HH4H4HBBBB", st["id"], st["item"], *mv, *md, spread_ids[st["spread"]], st["ability_slot"], st["tier"], st["flags"])
    if header:
        starts, counts, pos = [], [], 0
        for t in (1, 2, 3, 4):
            c = sum(1 for st in ordered if st["tier"] == t)
            starts.append(pos)
            counts.append(c)
            pos += c
        hdr = struct.pack("<H4H4HH", len(ordered), *starts, *counts, 0)
        assert len(hdr) == 20
        return hdr + bytes(blob), spread_ids
    return bytes(blob), spread_ids


def pack_json(path, header=True):
    """Pack data/frontier/sets.json (ids only, no ROM) into the table the natives read; same bytes as pack(header=True)."""
    d = json.load(open(path))
    order = d["spreads"]["order"]
    sets = sorted(d["sets"], key=lambda st: (st["tier"], st["id"])) if header else d["sets"]
    blob = bytearray()
    for st in sets:
        mv = (list(st["moves"]) + [0] * 4)[:4]
        md = (list(st["moves_d"]) + [0] * 4)[:4]
        blob += struct.pack("<HH4H4HBBBB", st["id"], st["item"], *mv, *md, order.index(st["spread"]), st["ability_slot"], st["tier"], st["flags"])
    if not header:
        return bytes(blob)
    starts, counts, pos = [], [], 0
    for t in (1, 2, 3, 4):
        c = sum(1 for st in sets if st["tier"] == t)
        starts.append(pos)
        counts.append(c)
        pos += c
    return struct.pack("<H4H4HH", len(sets), *starts, *counts, 0) + bytes(blob)


def pack_brains_json(path):
    """The Brain teams (Lance, then Anabel; 6 records each, 24 bytes) packed from data/frontier/sets.json (no ROM needed)."""
    d = json.load(open(path))
    order = d["spreads"]["order"]
    blob = bytearray()
    for name in ("Lance", "Anabel"):
        team = d["brains"][name]
        assert len(team) == 6, name
        for st in team:
            mv = (list(st["moves"]) + [0] * 4)[:4]
            md = (list(st["moves_d"]) + [0] * 4)[:4]
            blob += struct.pack("<HH4H4HBBBB", st["id"], st["item"], *mv, *md, order.index(st["spread"]), st["ability_slot"], st["tier"], st["flags"])
    return bytes(blob)


def write_samples(ctx, sets, path, rng):
    by_tier = collections.defaultdict(list)
    for st in sets:
        by_tier[st["tier"]].append(st)
    lines = ["# Sample teams (generated; review for sanity, not committed)", ""]
    for t in (1, 2, 3, 4):
        lines.append(f"## Tier {t}  ({len(by_tier[t])} sets)")
        lines.append("")
        for k in range(20):
            team, used_sp, used_it = [], set(), set()
            tries = 0
            while len(team) < 3 and tries < 50:
                tries += 1
                st = rng.choice(by_tier[t])
                if st["id"] in used_sp or st["item"] in used_it:
                    continue
                used_sp.add(st["id"]); used_it.add(st["item"]); team.append(st)
            lines.append(f"**Team {k + 1}**")
            for st in team:
                mv = ", ".join(ctx.mv[m]["name"] for m in st["moves"])
                lines.append(f"- {st['species']} @ {ctx.items.get(st['item'], st['item'])} [{st['role']}, {st['ability']}, {st['spread']}] {mv}")
            lines.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(ROOT, "data/frontier/sets.json"))
    ap.add_argument("--bin", default=os.path.join(ROOT, "build/frontier/sets.bin"))
    ap.add_argument("--samples", default=os.path.join(ROOT, "build/frontier/sample_teams.md"))
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    a = ap.parse_args()
    pool = json.load(open(os.path.join(ROOT, "data/frontier/pool.json")))
    ctx = Ctx(a.rom, pool)
    sets = generate(ctx, a.seed)
    errs, warns, tiers = validate(ctx, sets)
    brains, berrs, bwarns = load_brains(ctx)
    errs += berrs
    warns += bwarns
    species = {st["id"] for st in sets}
    blob, spread_ids = pack(ctx, sets, header=True)
    print(f"brains: " + ", ".join(f"{k} {len(v)}" for k, v in brains.items()))
    for w in bwarns:
        print("  WARN", w)
    print(f"{len(sets)} sets, {len(species)} species; tiers {dict(sorted(tiers.items()))}; packed {len(blob)} B; "
          f"{len(errs)} errors, {len(warns)} warnings; unresolved names: {len(ctx.unresolved)}")
    if ctx.unresolved:
        print("  unresolved:", sorted(ctx.unresolved)[:25])
    for e in errs[:30]:
        print("  ERROR", e)
    if a.check:
        return 1 if errs else 0
    named = []
    for st in sets:
        d = {k: v for k, v in st.items() if k not in ("sources", "bst")}
        d["item_name"] = ctx.items.get(st["item"])
        d["move_names"] = [ctx.mv[m]["name"] for m in st["moves"]]
        d["move_names_d"] = [ctx.mv[m]["name"] for m in st["moves_d"]]
        named.append(d)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump({"seed": a.seed, "spreads": {"order": sorted(pool["spreads"]), "defs": pool["spreads"]}, "sets": named, "brains": brains},
              open(a.out, "w"), separators=(",", ":"), ensure_ascii=False)
    os.makedirs(os.path.dirname(a.bin), exist_ok=True)
    open(a.bin, "wb").write(blob)
    bb = b"".join(pack(ctx, team)[0] for team in brains.values())
    open(os.path.join(os.path.dirname(a.bin), "brains.bin"), "wb").write(bb)
    write_samples(ctx, sets, a.samples, random.Random(a.seed + 1))
    print("wrote", a.out, a.bin, a.samples)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
