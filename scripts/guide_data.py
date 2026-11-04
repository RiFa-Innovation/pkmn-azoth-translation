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
                  "catch": e[8], "exp": e[9], "gender": e[18], "egg": [x for x in dict.fromkeys(e[20:22]) if x],
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
    rows = db.execute("select g, n, region from maps").fetchall()
    count = {}
    for g, n, r in rows:
        count[r] = count.get(r, 0) + 1
    out = {}
    for g, n, r in rows:
        nm = human.get(f"{g}.{n}")
        if nm:
            out[f"{g}.{n}"] = re.sub(r"\s*\(outdoors\)", "", nm)
            continue
        nm = reg.get(r, f"Area {r}")
        out[f"{g}.{n}"] = nm if count[r] == 1 else f"{nm} ({g}.{n})"
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
