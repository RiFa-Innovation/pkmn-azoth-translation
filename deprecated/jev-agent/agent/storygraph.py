"""Generate the story-step table from the game's own data: var 0x5120 is the hack's master progress index; the Start menu shows
objective text #value from a 75-entry table at 0x09FFF468 (function 0x09FF6878 reads VarGet(0x5120), bounds-checked at 74).

    python3 deprecated/jev-agent/agent/storygraph.py ROM [-o deprecated/jev-agent/data/agent_story_steps.json]

For every value N that some script sets (`setvar 0x5120 N`) it records the objective text, the setter address, and the map events
that reach that script (map, region name, event kind/idx, gate var and value). That is where the player must go and what must hold
to advance to N. Needs build/hackdb-<rom stem>.sqlite (scripts/hackdb.py build --rom ROM). Draft data: verify a step in the emulator
before trusting it (deprecated/jev-agent/data/agent_goals.json carries the verified goals).
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # repo root (this folder is deprecated/jev-agent/agent)
PKG = os.path.dirname(HERE)  # deprecated/jev-agent
ROOT = REPO
sys.path.insert(0, os.path.join(REPO, "scripts"))

import hackdb  # noqa: E402
import mercury_text as mt  # noqa: E402

TABLE, NSTEPS, VAR = 0x09FFF468, 75, 0x5120
NAMES_PTR = 0x08C2B0DC  # map-name table, region id = 143 + index


def table_text(rom, base, n):
    out = []
    for i in range(n):
        p = struct.unpack_from("<I", rom, base - 0x08000000 + 4 * i)[0]
        out.append(mt.decode_vanilla(rom, p - 0x08000000)[0].replace("\n", " ") if 0x08000000 <= p < 0x0A000000 else "")
    return out


def build(rom_path):
    q = hackdb.Q(rom_path)
    rom = q.rom
    objectives = table_text(rom, TABLE, NSTEPS)
    regions = {143 + i: t for i, t in enumerate(table_text(rom, NAMES_PTR, 79))}
    maps = {(g, n): r for g, n, r in q.sql("select g,n,region from maps")}
    steps = {}
    for cmd, name, val in q.sql("select cmd,name,val from refs where kind='var' and id=? and name='setvar' order by val", VAR):
        ents, _ = q.entries_reaching(cmd)
        where = []
        for addr, g, n, kind, idx, det in ents[:6]:
            ev = q.sql("select x,y from events where g=? and n=? and kind=? and idx=?", g, n, kind, idx)
            where.append({"map": f"{g}.{n}", "area": regions.get(maps.get((g, n)), ""), "event": f"{kind}#{idx}",
                          "tile": list(ev[0]) if ev else None, "gate": det, "entry": f"{addr:#010x}"})
        steps.setdefault(val, []).append({"setter": f"{cmd + 0x08000000:#010x}", "reached_from": where, "n_entries": len(ents)})
    return [{"step": v, "objective": objectives[v] if v < len(objectives) else "", "setters": steps.get(v, [])}
            for v in range(NSTEPS)]


if __name__ == "__main__":
    rom = sys.argv[1]
    out = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else os.path.join(PKG, "data/agent_story_steps.json")
    data = build(rom)
    json.dump(data, open(out, "w"), indent=1, ensure_ascii=False)
    for s in data:
        w = s["setters"][0]["reached_from"][0] if s["setters"] and s["setters"][0]["reached_from"] else None
        print(f"{s['step']:2d} {s['objective'][:58]:58s} {('%s %s %s %s' % (w['map'], w['area'], w['event'], w['gate'])) if w else '-'}")
