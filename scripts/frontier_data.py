"""Read the Battle Frontier generator's inputs out of a Mercury/Azoth ROM (base stats, moves, learnsets, evolutions).

    python3 scripts/frontier_data.py [ROM] [--dump build/frontier/db.json] [--species 25 1000 ...]

Formats were located and checked on 2026-10-21 (docs/BATTLE_FRONTIER_SPEC.md, spike S1). All offsets are file offsets of the
original hack ROM (`roms/Pokemon Mercury 1.3.3 (patched).gba`) and of the English build, which does not move them.

  base stats   0x176DFBC + 28*species   hp atk def spe spa spd type1 type2 catch exp ev(2) item1 item2 gender egg friend growth
                                        egg1 egg2 ability1 ability2 ... (vanilla struct, species id = index, 1..~1553, 0 = unused)
  moves        0x1E0326F + 12*move      effect power type accuracy pp secondary target priority flags(u32)  (CFRU copy; the vanilla
                                        table at 0x250C04 is stale). Category = byte 10 & 3: 0 physical, 1 special, 2 status
                                        (verified on ~35 moves: Shadow Ball/Dark Pulse/Judgment special, Crunch/Earthquake physical)
  learnsets    ptr table 0x17C32BC      u32 pointer per species -> {u16 move, u8 level} repeated, terminated by level 0xFF
  evolutions   0x1788F5A + 128*species  16 slots of {u16 method, u16 param, u16 target, u16 pad}; slot with method 0 ends the list
  names        species 0x141B350 (11 B), moves 0x1D97378 (13 B)
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

BASE_STATS = 0x176DFBC
MOVES = 0x1E0326F
LEARN_PTRS = 0x17C32BC
EVOS = 0x1788F5A
MAX_SPECIES = 1554
MAX_MOVE = 1000
TYPES = ["Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost", "Steel", "???", "Fire", "Water", "Grass",
         "Electric", "Psychic", "Ice", "Dragon", "Dark", "Fairy"]


def load(rom_path):
    rom = open(rom_path, "rb").read()
    names = json.load(open(os.path.join(ROOT, "text/en/tables/species.json")))
    mnames = json.load(open(os.path.join(ROOT, "text/en/tables/moves.json")))
    species = {}
    for s in range(1, MAX_SPECIES):
        e = rom[BASE_STATS + 28 * s: BASE_STATS + 28 * s + 28]
        hp, atk, df, spe, spa, spd, t1, t2 = e[:8]
        if not (hp or atk or df or spe or spa or spd) or str(s) not in names:
            continue
        evos = []
        for slot in range(16):
            meth, par, tgt, _ = struct.unpack_from("<HHHH", rom, EVOS + 128 * s + 8 * slot)
            if meth == 0:
                break
            evos.append({"method": meth, "param": par, "to": tgt})
        ptr = struct.unpack_from("<I", rom, LEARN_PTRS + 4 * s)[0]
        learn = []
        if 0x08000000 <= ptr < 0x0A000000:
            o = ptr & 0x1FFFFFF
            while len(learn) < 90:
                mv, lv = struct.unpack_from("<HB", rom, o)
                if lv == 0xFF:
                    break
                learn.append({"move": mv, "level": lv})
                o += 3
        species[s] = {"id": s, "name": names[str(s)], "stats": [hp, atk, df, spe, spa, spd], "bst": hp + atk + df + spe + spa + spd,
                      "types": sorted({t1, t2}), "abilities": [e[22], e[23]], "evos": evos, "learnset": learn}
    moves = {}
    for m in range(1, MAX_MOVE):
        e = rom[MOVES + 12 * m: MOVES + 12 * m + 12]
        if str(m) in mnames:
            moves[m] = {"id": m, "name": mnames[str(m)], "effect": e[0], "power": e[1], "type": e[2], "accuracy": e[3], "pp": e[4],
                        "secondary": e[5], "target": e[6], "priority": e[7] - 256 if e[7] > 127 else e[7],
                        "split": e[10] & 3}
    return species, moves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", nargs="?", default=os.path.join(ROOT, "roms/Pokemon Mercury 1.3.3 (patched).gba"))
    ap.add_argument("--dump")
    ap.add_argument("--species", nargs="*", type=int, default=[1, 25, 149, 248, 1000])
    a = ap.parse_args()
    species, moves = load(a.rom)
    evolves_from = {e["to"] for s in species.values() for e in s["evos"]}
    final = [s for s in species.values() if not s["evos"]]
    print(f"{len(species)} species, {len(moves)} moves; {len(final)} without an evolution; {len(evolves_from)} are evolution targets")
    for s in a.species:
        if s in species:
            x = species[s]
            print(s, x["name"], x["stats"], "bst", x["bst"], [TYPES[t] for t in x["types"]], "evos", x["evos"][:2],
                  "learn", len(x["learnset"]), "<=Lv50:", sum(1 for l in x["learnset"] if l["level"] <= 50))
    if a.dump:
        os.makedirs(os.path.dirname(a.dump), exist_ok=True)
        json.dump({"species": species, "moves": moves}, open(a.dump, "w"))
        print("wrote", a.dump)


if __name__ == "__main__":
    main()
