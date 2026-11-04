"""Extract the player-guide data (species, moves, items, TMs, wild encounters, trainers) from a built ROM into JSON.

    python3 scripts/guide_data.py [ROM] [--out docs/guide/data]

Reads the English build (default build/Mercury_EN.gba) and, for "where" questions, build/hackdb-<rom name>.sqlite
(`python3 scripts/hackdb.py build --rom ROM`). Offsets and formats are the ones documented in frontier_data.py, mapedit.py
and TABLES.md; nothing here writes to the ROM.
"""
import argparse
import json
import os
import re
import sqlite3
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mercury_text as mt  # noqa: E402

BASE = 0x08000000
TYPES = ["Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost", "Steel", "???", "Fire", "Water", "Grass",
         "Electric", "Psychic", "Ice", "Dragon", "Dark", "Fairy"]
SPLIT = ["Physical", "Special", "Status"]
BASE_STATS, EVOS, LEARN_PTRS = 0x176DFBC, 0x1788F5A, 0x17C32BC
MOVES, MOVE_DESC = 0x1E0326F, 0x1CC8EB0
ITEMS, N_ITEMS = 0x7C7E00, 750
TM_TABLE = 0x17E87BE
TRAINERS, N_TRAINERS = 0x23EACC - 4, 775
WILD_PTR = 0x82990   # literal-pool word holding the address of the live wild table (0x1E468B0 in the original hack)
DEX_DESC = None
POCKETS = {1: "Medicine", 2: "Key items", 3: "Poké Balls", 4: "TMs and HMs", 5: "Berries"}


def j(path):
    return json.load(open(os.path.join(ROOT, path), encoding="utf-8"))


def u16(r, o):
    return struct.unpack_from("<H", r, o)[0]


def u32(r, o):
    return struct.unpack_from("<I", r, o)[0]


def text_at(rom, ptr):
    if not (BASE <= ptr < BASE + len(rom)):
        return ""
    s = mt.decode(rom, ptr - BASE)[0]
    return re.sub(r"\s*\n\s*", " ", s.replace("\\n", " ")).strip()


def clean(s):
    return "".join(ch for ch in s if ch.isprintable() or ch in " ").strip()


def species_table(rom, names, abil):
    out = {}
    for s in range(1, 1554):
        if str(s) not in names:
            continue
        e = rom[BASE_STATS + 28 * s: BASE_STATS + 28 * s + 28]
        hp, atk, df, spe, spa, spd, t1, t2 = e[:8]
        if not (hp or atk or df or spe or spa or spd):
            continue
        evos = []
        for slot in range(16):
            meth, par, tgt, _ = struct.unpack_from("<HHHH", rom, EVOS + 128 * s + 8 * slot)
            if meth == 0:
                break
            evos.append([meth, par, tgt])
        ptr = u32(rom, LEARN_PTRS + 4 * s)
        learn = []
        if BASE <= ptr < BASE + 0x2000000:
            o = ptr - BASE
            while len(learn) < 120:
                mv, lv = struct.unpack_from("<HB", rom, o)
                if lv == 0xFF:
                    break
                learn.append([lv, mv])
                o += 3
        out[s] = {"id": s, "name": names[str(s)], "stats": [hp, atk, df, spe, spa, spd],
                  "types": [t1] if t1 == t2 else [t1, t2], "abil": [a for a in dict.fromkeys(e[22:24]) if a],
                  "catch": e[8], "exp": e[9], "held": [u16(e, 12), u16(e, 14)], "gender": e[16], "egg": [x for x in dict.fromkeys(e[20:22]) if x],
                  "evos": evos, "learn": learn}
    return out


def moves_table(rom, names):
    out = {}
    for m in range(1, 1000):
        if str(m) not in names:
            continue
        e = rom[MOVES + 12 * m: MOVES + 12 * m + 12]
        out[m] = {"id": m, "name": names[str(m)], "power": e[1], "type": e[2], "acc": e[3], "pp": e[4],
                  "pri": e[7] - 256 if e[7] > 127 else e[7], "split": e[10] & 3, "effect_pct": e[5],
                  "desc": clean(text_at(rom, u32(rom, MOVE_DESC + 4 * (m + 2))))}   # the table is offset by two
    return out


def items_table(rom):
    out = {}
    for i in range(1, N_ITEMS):
        o = ITEMS + 44 * i
        name = clean(mt.decode_fixed(rom, o, 14))
        if not name:
            continue
        out[i] = {"id": i, "name": name, "price": u16(rom, o + 16), "pocket": rom[o + 26],
                  "desc": clean(text_at(rom, u32(rom, o + 20)))}
    return out


def wild_table(rom, mapname):
    out = []
    o = u32(rom, WILD_PTR) - BASE   # mapedit relocates the table and repoints this literal
    while rom[o] != 0xFF:
        g, n = rom[o], rom[o + 1]
        entry = {"map": f"{g}.{n}", "name": mapname.get(f"{g}.{n}", f"Map {g}.{n}")}
        for kind, p in zip(("land", "water", "rock", "fish"), struct.unpack_from("<4I", rom, o + 4)):
            if not (BASE <= p < BASE + len(rom)):
                continue
            rate = rom[p - BASE]
            arr = u32(rom, p - BASE + 4)
            cnt = {"land": 12, "water": 5, "rock": 5, "fish": 10}[kind]
            mons = []
            for k in range(cnt):
                lo, hi, sp = struct.unpack_from("<BBH", rom, arr - BASE + 4 * k)
                mons.append([sp, lo, hi])
            entry[kind] = {"rate": rate, "mons": mons}
        out.append(entry)
        o += 20
    return out


def trainers_table(rom):
    out = {}
    for i in range(1, N_TRAINERS):
        o = TRAINERS + 40 * i
        fl, cl, _, pic = rom[o:o + 4]
        name = clean(mt.decode_fixed(rom, o + 4, 12))
        n, p = u32(rom, o + 32), u32(rom, o + 36)
        if not name or not (BASE <= p < BASE + len(rom)) or not 0 < n <= 6:
            continue
        mons = []
        size = 16 if fl & 1 else 8
        for k in range(n):
            q = p - BASE + size * k
            iv, lv, sp = u16(rom, q), rom[q + 2], u16(rom, q + 4)
            if fl & 1 and fl & 2:
                item = u16(rom, q + 6)
                mv = list(struct.unpack_from("<4H", rom, q + 8))
            elif fl & 1:
                item, mv = 0, list(struct.unpack_from("<4H", rom, q + 8))
            elif fl & 2:
                item, mv = u16(rom, q + 6), []
            else:
                item, mv = 0, []
            mons.append({"sp": sp, "lv": lv, "item": item, "mv": [m for m in mv if m]})
        items = [x for x in struct.unpack_from("<4H", rom, o + 16) if x]
        out[i] = {"id": i, "name": name, "class": cl, "pic": pic, "double": bool(u32(rom, o + 24)), "items": items, "party": mons}
    return out


def trainer_places(db_path):
    """trainer id -> sorted 'g.n' of the maps whose events (transitively) reach a trainerbattle for it."""
    places = {}
    if not os.path.exists(db_path):
        return places
    db = sqlite3.connect(db_path)
    rev = {}
    for src, dst in db.execute("select src_blk, dst from edges"):
        rev.setdefault(dst, set()).add(src)
    ent = {}
    for addr, g, n in db.execute("select addr, g, n from entries"):
        ent.setdefault(addr - BASE, set()).add(f"{g}.{n}")
    for addr, args, blk in db.execute("select addr, args, blk from cmds where name='trainerbattle'"):
        a = args.split()
        try:
            tid = int(a[1], 0)
        except (IndexError, ValueError):
            continue
        if tid == 0:
            continue
        seen, todo = set(), [blk]
        while todo:
            b = todo.pop()
            if b in seen:
                continue
            seen.add(b)
            todo.extend(rev.get(b, ()))
            for m in ent.get(b, ()):
                places.setdefault(tid, set()).add(m)
    return {k: sorted(v) for k, v in places.items()}


def region_names(rom):
    """Region (map section) id -> in-game name, from the hack's pointer table (id 0 at 0xC2B0DC - 143*4)."""
    names = {}
    for i in range(0, 230):
        p = u32(rom, 0xC2B0DC - 143 * 4 + 4 * i)
        if BASE <= p < BASE + len(rom):
            names[i] = clean(text_at(rom, p))
    return names


def map_labels(rom, db_path):
    """'g.n' -> display label ("Route 29", "Dark Cave (3.12)" when several maps share a name)."""
    if not os.path.exists(db_path):
        return {}
    reg = region_names(rom)
    db = sqlite3.connect(db_path)
    human = {k: v for k, v in j("data/map_names.json").items() if not k.startswith("_")}
    for tgt, text in db.execute("select target, text from notes where target like 'map:%'"):
        human.setdefault(tgt[4:], re.split(r"\s+[(\u2014-]\s*|\s*;", text)[0])
    rows = db.execute("select g, n, region, mtype from maps").fetchall()
    info = {f"{g}.{n}": (r, mt_) for g, n, r, mt_ in rows}
    warps = {}
    for g, n, data in db.execute("select g, n, data from events where kind='warp'"):
        try:
            d = json.loads(data)
            warps.setdefault(f"{g}.{n}", []).append(f"{d['tg']}.{d['tn']}")
        except (ValueError, KeyError):
            pass
    # Indoor maps (type 8) show no area popup, so their region field can be leftover vanilla data (Cianwood Gym says "Pallet Town").
    # Name those after the nearest outdoor map their doors lead to.
    kanto = {"Pallet Town", "Viridian City", "Pewter City", "Cerulean City", "Lavender Town", "Vermilion City", "Celadon City",
             "Fuchsia City", "Cinnabar Island", "Saffron City", "Indigo Plateau"}

    def outdoor(m):
        seen, todo = {m}, [m]
        while todo:
            nxt = []
            for x in todo:
                for y in warps.get(x, ()):
                    if y in seen or y not in info:
                        continue
                    seen.add(y)
                    if info[y][1] in (1, 2, 3):
                        return y
                    nxt.append(y)
            todo = nxt
        return None

    count = {}
    for g, n, r, mt_ in rows:
        count[r] = count.get(r, 0) + 1
    out = {}
    for g, n, r, mt_ in rows:
        m = f"{g}.{n}"
        nm = human.get(m)
        if nm:
            out[m] = re.sub(r"\s*\(outdoors\)", "", nm)
            continue
        nm = reg.get(r, f"Area {r}")
        if mt_ == 8 and nm in kanto:
            o = outdoor(m)
            if o and reg.get(info[o][0]) and reg.get(info[o][0]) != nm:
                out[m] = f"{reg[info[o][0]]}, indoors ({m})"
                continue
        if nm in kanto and g not in range(1, 15) and g != 3:
            out[m] = f"Building ({m})"   # a hack-built interior carrying a vanilla town name: say nothing wrong
            continue
        out[m] = nm if count[r] == 1 else f"{nm} ({m})"
    return out


def item_sources(rom, db_path, mapname, sp, trainers):
    """item id -> list of [kind, where, qty]: ground pickups and gifts (callstd 1 / 0 with 0x8000 set before it),
    additem scripts, shop stock, wild held items and trainer held items."""
    out = {}

    rules = [(re.compile(r["re"], re.I | re.S), r["label"]) for r in j("data/guide_gift_labels.json")["rules"]]

    def label_for(note):
        for rx, lab in rules:
            m = rx.search(note)
            if m:
                return m.expand(lab)
        return ""

    def add(item, kind, where, qty=1, note=""):
        lab = label_for(note) if note else ""
        row = [kind, where, qty] + ([0, note, lab] if note else [])
        lst = out.setdefault(item, [])
        if row not in lst:
            lst.append(row)

    if os.path.exists(db_path):
        db = sqlite3.connect(db_path)
        rev = {}
        for src, dst in db.execute("select src_blk, dst from edges"):
            rev.setdefault(dst, set()).add(src)
        ent = {}
        for addr, g, n in db.execute("select addr, g, n from entries"):
            ent.setdefault(addr - BASE, set()).add(f"{g}.{n}")

        def maps_of(blk):
            seen, todo, res = set(), [blk], set()
            while todo:
                b = todo.pop()
                if b in seen:
                    continue
                seen.add(b)
                todo.extend(rev.get(b, ()))
                res |= ent.get(b, set())
            return sorted(res)

        def where(blk):
            ms = maps_of(blk)
            return [mapname.get(m, m) for m in ms] if len(ms) <= 2 else []

        cmds_of = {}

        def block(blk):
            if blk not in cmds_of:
                cmds_of[blk] = db.execute("select addr, name, args from cmds where blk=? order by addr", (blk,)).fetchall()
            return cmds_of[blk]

        text_cache = {}

        def string_at(ptr):
            """English text at a script operand (decoded from the ROM: the dump's table is keyed by the original addresses)."""
            if ptr not in text_cache:
                t = text_at(rom, ptr) if BASE <= ptr < BASE + len(rom) else ""
                text_cache[ptr] = t if t and not re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", t) else ""
            return text_cache[ptr]

        def clean_msg(t):
            t = re.sub(r"\{[^}]*\}", " ", t)
            return re.sub(r"\s+", " ", t).strip()

        def lines_in(blk, lo, hi):
            out_ = []
            for addr, name, args in block(blk):
                if addr < lo or addr >= hi:
                    continue
                if name in ("loadword", "loadpointer"):
                    try:
                        txt = string_at(int(args.split()[-1], 0))
                    except (ValueError, IndexError):
                        txt = None
                    if txt:
                        txt = clean_msg(txt)
                        if len(txt) > 3 and txt not in out_:
                            out_.append(txt)
            return out_

        GENERIC = re.compile(r"^(?:you |\w+ )?(?:received|obtained|got|found|put away|put the)\b|\bin the bag\b|\bBAG\b|^(?:thank you|thanks)[.!…]*$", re.I)

        def note_of(blk, upto):
            """What the NPC says around the give: up to two lines before it (walking back through callers if the block has none),
            skipping the generic 'You received ...' line, plus one line right after it."""
            before = [t for t in lines_in(blk, 0, upto) if not GENERIC.search(t)]
            depth, frontier, seen_ = 0, [blk], {blk}
            while not before and depth < 4:
                nxt = []
                for b_ in frontier:
                    for pb in rev.get(b_, ()):
                        if pb in seen_:
                            continue
                        seen_.add(pb)
                        before += [t for t in lines_in(pb, 0, 1 << 40) if not GENERIC.search(t)][-2:]
                        nxt.append(pb)
                frontier, depth = nxt, depth + 1
            after = [t for t in lines_in(blk, upto, 1 << 40) if not GENERIC.search(t)]
            picks = before[-2:] + after[:1]
            msg = " / ".join(x[:150] for x in picks)
            return msg[:320]

        def const(a):
            try:
                v = int(a, 0)
            except ValueError:
                return None
            return v if 0 < v < 0x8000 else None

        def trace(blk, upto, var, depth=0, seen=None):
            """constants assigned to `var` before `upto` in blk, walking back through predecessor blocks."""
            seen = seen if seen is not None else set()
            last = None
            for addr, name, args in block(blk):
                if addr >= upto:
                    break
                a = args.split()
                if name in ("setvar", "setorcopyvar") and len(a) == 2 and a[0] == var:
                    last = const(a[1]) if a[1][:2] != "0x" or int(a[1], 0) < 0x8000 else ("var", a[1])
                elif name in ("setorcopyvar", "copyvar") and len(a) == 2 and a[0] == var:
                    last = None
            if isinstance(last, int):
                return [(last, blk)]
            if isinstance(last, tuple) or depth >= 5:
                return []
            res = []
            for pb in rev.get(blk, ()):
                if (pb, var) in seen:
                    continue
                seen.add((pb, var))
                res += trace(pb, 1 << 40, var, depth + 1, seen)
            return res

        rows = db.execute("select addr, name, args, blk from cmds where blk in "
                          "(select blk from cmds where name='callstd' and args in ('0','1')) order by blk, addr").fetchall()
        cur, v0, v1 = None, None, 1
        for addr, name, args, blk in rows:
            if blk != cur:
                cur, v0, v1 = blk, None, 1
            a = args.split()
            if name == "setorcopyvar" and len(a) == 2:
                val = const(a[1])
                if a[0] == "0x8000":
                    v0 = val if val is not None else ("var", a[1])
                elif a[0] == "0x8001":
                    v1 = val if val is not None else 1
            elif name == "callstd" and v0:
                kind = "Found" if args == "1" else "Received"
                if isinstance(v0, int):
                    w = where(blk)
                    add(v0, kind, w, v1, note_of(blk, addr) if kind == "Received" else "")
                else:
                    for item, src_blk in trace(blk, addr, v0[1]):
                        w = where(src_blk)
                        add(item, kind, w, v1, (note_of(src_blk, 1 << 40) or note_of(blk, addr)) if kind == "Received" else "")
                v0, v1 = None, 1
        # hidden items (bg event kind 7): item at +8, quantity at +11
        for g, n, off, x, y, data in db.execute("select g, n, addr, x, y, data from events where kind='bg'"):
            if '"kind": 7' not in data:
                continue
            o = off if off < len(rom) else off - BASE
            item, _, qty = struct.unpack_from("<HBB", rom, o + 8)
            if item:
                add(item, "Hidden (Itemfinder)", [f"{mapname.get(f'{g}.{n}', f'{g}.{n}')} at ({x}, {y})"], qty or 1)
        for addr, args, blk in db.execute("select addr, args, blk from cmds where name='additem'"):
            a = args.split()
            try:
                add(int(a[0], 0), "Script reward", where(blk), int(a[1], 0), note_of(blk, addr))
            except (IndexError, ValueError):
                pass
        for addr, args, blk in db.execute("select addr, args, blk from cmds where name='pokemart'"):
            p = int(args.split()[0], 0) - BASE
            items = []
            while 0 <= p < len(rom) - 2 and len(items) < 40:
                v = u16(rom, p)
                if v == 0:
                    break
                items.append(v)
                p += 2
            w = where(blk)
            for it in items:
                add(it, "Shop", w)
    names = {s_["id"]: s_["name"] for s_ in sp.values()}
    wild = {}
    for s_ in sp.values():
        a, b = s_["held"]
        for it, pct in ((a, 50), (b, 5)):
            if it:
                wild.setdefault(it, {})[s_["name"]] = 100 if a == b else max(pct, wild.get(it, {}).get(s_["name"], 0))
    for it, d in wild.items():
        lst = sorted(d.items())
        txt = ", ".join(f"{n} ({p}%)" for n, p in lst[:10]) + (f" and {len(lst) - 10} more" if len(lst) > 10 else "")
        out.setdefault(it, []).append(["Held by wild Pokémon", [txt], 1])
    held = {}
    for t in trainers.values():
        for m in t["party"]:
            if m["item"]:
                held.setdefault(m["item"], set()).add(t["name"] if t["name"] != "???" else "a rival")
    for it, ts in held.items():
        ts = sorted(ts)
        txt = ", ".join(ts[:8]) + (f" and {len(ts) - 8} more" if len(ts) > 8 else "")
        out.setdefault(it, []).append(["Held by trainers", [txt], 1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", nargs="?", default=os.path.join(ROOT, "build/Mercury_EN.gba"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs/guide/data"))
    a = ap.parse_args()
    rom = open(a.rom, "rb").read()
    os.makedirs(a.out, exist_ok=True)
    names = {k: j(f"text/en/tables/{k}.json") for k in ("species", "moves", "abilities", "trainer_classes")}

    mapname = map_labels(rom, os.path.join(ROOT, "build/hackdb-" + os.path.basename(a.rom).rsplit(".", 1)[0] + ".sqlite"))

    sp = species_table(rom, names["species"], names["abilities"])
    mv = moves_table(rom, names["moves"])
    it = items_table(rom)
    tm = struct.unpack_from("<128H", rom, TM_TABLE)
    wild = wild_table(rom, mapname)
    tr = trainers_table(rom)
    places = trainer_places(os.path.join(ROOT, "build/hackdb-" + os.path.basename(a.rom).rsplit(".", 1)[0] + ".sqlite"))
    for tid, t in tr.items():
        ms = places.get(tid, [])
        t["where"] = [mapname.get(m, m) for m in ms] if len(ms) <= 2 else []
    src = item_sources(rom, os.path.join(ROOT, "build/hackdb-" + os.path.basename(a.rom).rsplit(".", 1)[0] + ".sqlite"), mapname, sp, tr)
    by_name = {v["name"]: k for k, v in it.items()}
    for e in j("data/frontier/shop.json")["items"]:
        if e["item"] in by_name:
            src.setdefault(by_name[e["item"]], []).append(["Battle Points shop", ["Spectrum Frontier hall"], e.get("qty", 1), e["price"]])
    # River Edition drops (Partner Patrol and Quick Catch wins): Exp. Candies by the target's level, EV Feathers, Berries
    candy = {"Exp. Candy XS": "target below Lv 20", "Exp. Candy S": "target Lv 20-39", "Exp. Candy M": "target Lv 40-59",
             "Exp. Candy L": "target Lv 60-79", "Exp. Candy XL": "target Lv 80 or higher"}
    for nm, why in candy.items():
        if nm in by_name:
            src.setdefault(by_name[nm], []).append(["Partner Patrol and Quick Catch drops", ["River Edition: 20% drop, " + why], 1])
    for nm in ("Health Wing", "Muscle Wing", "Resist Wing", "Genius Wing", "Clever Wing", "Swift Wing"):
        if nm in by_name:
            src.setdefault(by_name[nm], []).append(["Partner Patrol and Quick Catch drops", ["River Edition: 50% drop (EV Feathers, the hack's own rules)"], 1])
    for i, rows in src.items():
        if i in it:
            it[i]["src"] = rows
    json.dump({"species": sp, "types": TYPES, "abilities": names["abilities"]}, open(f"{a.out}/species.json", "w"), separators=(",", ":"))
    json.dump(mv, open(f"{a.out}/moves.json", "w"), separators=(",", ":"))
    json.dump(it, open(f"{a.out}/items.json", "w"), separators=(",", ":"))
    json.dump(wild, open(f"{a.out}/wild.json", "w"), separators=(",", ":"))
    json.dump({"tm": tm, "trainers": tr, "classes": names["trainer_classes"], "pockets": POCKETS}, open(f"{a.out}/misc.json", "w"), separators=(",", ":"))
    fr = {"brains": {k: v for k, v in j("data/frontier/brains.json").items() if not k.startswith("_")},
          "shop": j("data/frontier/shop.json")["items"]}
    json.dump(fr, open(f"{a.out}/frontier.json", "w"), separators=(",", ":"))
    print(len(sp), "species,", len(mv), "moves,", len(it), "items,", len(wild), "wild maps,", len(tr), "trainers")


if __name__ == "__main__":
    main()
