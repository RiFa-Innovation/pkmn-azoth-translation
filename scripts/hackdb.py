"""Queryable index of the ROM hack's structure: maps, events, scripts, vars/flags,
strings, hack code. One build, then compound lookups instead of one-off scripts.

    python3 scripts/hackdb.py build [--rom PATH]     # -> build/hackdb.sqlite (~seconds)
    python3 scripts/hackdb.py map 3.85               # header, warps, objects, coord/bg gates, map scripts
    python3 scripts/hackdb.py maps [text]            # list maps (labels/notes searched)
    python3 scripts/hackdb.py var 0x5186             # every setter/reader/gate/code literal + RAM address
    python3 scripts/hackdb.py flag 0x178B            # same for flags (+ object flags)
    python3 scripts/hackdb.py text "Violet City"     # zh or en text -> string -> script -> event -> map
    python3 scripts/hackdb.py script 0x08AF433D      # disassembly, strings inlined, who reaches it
    python3 scripts/hackdb.py who 0x08AF433D         # entries (map events) that reach this script/cmd
    python3 scripts/hackdb.py whatis 0x1D8D074       # region/symbol/func/string/script/event at an address
    python3 scripts/hackdb.py names species 25       # id -> name (or name -> id); tables from zh.json
    python3 scripts/hackdb.py note add ADDR|var:N|flag:N|map:G.N "text"   # persisted in data/hackdb_notes.json
    python3 scripts/hackdb.py sql "select ..."       # raw SQL escape hatch

Default source is the ORIGINAL Chinese hack (the forensic reference); pass --rom
build/Mercury_EN.gba to index the translated build (its own db file).
Addresses accept ROM form (0x08AF433D) or file offsets (0xAF433D).
Schema: see `hackdb.py schema` or HACKDB.md.
"""
import bisect
import json
import os
import re
import sqlite3
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scrdis  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
ORIG = os.path.join(ROOT, "roms/Pokemon Mercury 1.3.3 (patched).gba")
GMAPGROUPS = 0xB3B100            # the hack moved gMapGroups (see insert.py)
VAR_BASE_RAM, VAR_BASE_ID = 0x2039374, 0x4000   # hack's var array (SaveBlock1 + extra)
NOTES = os.path.join(ROOT, "data/hackdb_notes.json")
ROMBASE = 0x08000000
MSCRIPT_TAGS = {1: "ON_LOAD", 2: "ON_FRAME_TABLE", 3: "ON_TRANSITION",
                4: "ON_WARP_INTO_MAP_TABLE", 5: "ON_RESUME", 6: "ON_DIVE_WARP",
                7: "ON_RETURN_TO_FIELD"}
KINDW = {"byte": 1, "2byte": 2, "word": 2, "4byte": 4}


def db_path(rom_path):
    tag = "" if os.path.abspath(rom_path) == os.path.abspath(ORIG) else \
        "-" + os.path.splitext(os.path.basename(rom_path))[0]
    return os.path.join(ROOT, f"build/hackdb{tag}.sqlite")


def num(s):
    return int(s, 0)


def to_off(a):
    a = num(a) if isinstance(a, str) else a
    return a - ROMBASE if a >= ROMBASE else a


def rom_ptr(v):
    return ROMBASE <= v < 0x0A000000


# ---------------------------------------------------------------- build ----

def script_table():
    t = dict(scrdis.load_macros())
    # warp family: `.byte group, num, warp; .2byte x, y` (the macro parse misses it)
    for op in range(0x39, 0x42):
        t[op] = (t[op][0], [("byte", 3), ("2byte", 2)])
    return t


def decode_one(rom, off, table):
    """-> (name, args[int], length, ptr_slots[(arg_index, byte_offset)]) or None."""
    op = rom[off]
    if op == 0x5C:
        t = rom[off + 1]
        n = 2 + scrdis.TB.get(t, 12)
        args = [t] + [int.from_bytes(rom[p:p + 4], "little") if p + 4 <= off + n else 0
                      for p in range(off + 6, off + n - 3, 4)]
        return "trainerbattle", [t, int.from_bytes(rom[off + 2:off + 4], "little"),
                                 int.from_bytes(rom[off + 4:off + 6], "little")] + \
            [int.from_bytes(rom[p:p + 4], "little") for p in range(off + 6, off + n - 3, 4)], n
    if op not in table:
        return None
    name, spec = table[op]
    p, args = off + 1, []
    for kind, n in spec:
        for _ in range(n):
            w = KINDW[kind]
            args.append(int.from_bytes(rom[p:p + w], "little"))
            p += w
    return name, args, p - off


def build(rom_path):
    rom = open(rom_path, "rb").read()
    out = db_path(rom_path)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out):
        os.remove(out)
    db = sqlite3.connect(out)
    db.executescript("""
    create table meta(k text primary key, v text);
    create table maps(g int, n int, hdr int, layout int, events int, mscripts int, conn int,
                      music int, layout_id int, region int, cave int, weather int, mtype int,
                      flags int, battle int, primary key(g,n));
    create table events(g int, n int, kind text, idx int, addr int, x int, y int, elev int,
                        script int, flag int, var int, val int, data text);
    create table mscripts(g int, n int, tag int, tagname text, slot int, target int,
                          var int, val int);
    create table conns(g int, n int, dir int, off int, tg int, tn int);
    create table cmds(addr int primary key, len int, op int, name text, args text, blk int);
    create table edges(src_cmd int, src_blk int, dst int, kind text);
    create table entries(addr int, g int, n int, kind text, idx int, detail text);
    create table refs(kind text, id int, cmd int, name text, val int);
    create table strings(addr int primary key, zh text, en text, cap int, refs text);
    create table names(tbl text, id int, zh text, en text);
    create table lit(off int, value int, use int, func int);
    create table funcs(start int primary key, end int);
    create table notes(target text, text text);
    create index ev_script on events(script); create index ev_flag on events(flag);
    create index ev_var on events(var); create index refs_i on refs(kind,id);
    create index cmds_blk on cmds(blk); create index edges_dst on edges(dst);
    create index lit_v on lit(value); create index ent_addr on entries(addr);
    """)
    u16 = lambda o: int.from_bytes(rom[o:o + 2], "little")
    s16 = lambda o: struct.unpack_from("<h", rom, o)[0]
    u32 = lambda o: int.from_bytes(rom[o:o + 4], "little")
    ptr = lambda o: u32(o) - ROMBASE if rom_ptr(u32(o)) else None

    # ---- maps
    gtab = GMAPGROUPS
    ngroups = 0
    while rom_ptr(u32(gtab + 4 * ngroups)):
        ngroups += 1
    arrs = [ptr(gtab + 4 * g) for g in range(ngroups)]
    bounds = sorted(set(arrs))
    maps = []
    for g, arr in enumerate(arrs):
        nxt = next((b for b in bounds if b > arr), arr + 4 * 256)
        for n in range((nxt - arr) // 4):
            h = ptr(arr + 4 * n)
            if not h or h + 28 > len(rom):
                break
            lay, ev, ms = ptr(h), ptr(h + 4), ptr(h + 8)
            if not lay or ev is None and not ptr(h + 4):
                break
            maps.append((g, n, h, lay, ev, ms, ptr(h + 12), u16(h + 16), u16(h + 18),
                         rom[h + 20], rom[h + 21], rom[h + 22], rom[h + 23], rom[h + 26],
                         rom[h + 27]))
    db.executemany("insert or replace into maps values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", maps)

    table = script_table()
    entries = []       # (script ptr, g, n, kind, idx, detail)

    for (g, n, h, lay, ev, ms, conn, *_rest) in maps:
        # connections
        if conn and conn + 8 <= len(rom):
            cnt, arr = u32(conn), ptr(conn + 4)
            if arr and cnt < 16:
                for i in range(cnt):
                    o = arr + 12 * i
                    db.execute("insert into conns values(?,?,?,?,?,?)",
                               (g, n, u32(o), struct.unpack_from("<i", rom, o + 4)[0],
                                rom[o + 8], rom[o + 9]))
        # events
        if ev and ev + 20 <= len(rom):
            no, nw, nc, nb = rom[ev:ev + 4]
            po, pw, pc, pb = ptr(ev + 4), ptr(ev + 8), ptr(ev + 12), ptr(ev + 16)
            if po:
                for i in range(no):
                    o = po + 24 * i
                    if o + 24 > len(rom):
                        break
                    sc = u32(o + 16)
                    d = dict(local=rom[o], gfx=rom[o + 1], mv=rom[o + 9], mvr=rom[o + 10],
                             trainer=u16(o + 12), range=u16(o + 14))
                    db.execute("insert into events values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (g, n, "obj", i, o, s16(o + 4), s16(o + 6), rom[o + 8],
                                sc, u16(o + 20), None, None, json.dumps(d)))
                    if rom_ptr(sc) and sc >= ROMBASE + 0x100:
                        entries.append((sc, g, n, "obj", i, f"local {rom[o]}"))
            if pw:
                for i in range(nw):
                    o = pw + 8 * i
                    db.execute("insert into events values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (g, n, "warp", i, o, s16(o), s16(o + 2), rom[o + 4], None, None,
                                None, None, json.dumps(dict(warp=rom[o + 5], tn=rom[o + 6],
                                                            tg=rom[o + 7]))))
            if pc:
                for i in range(nc):
                    o = pc + 16 * i
                    if o + 16 > len(rom):
                        break
                    sc = u32(o + 12)
                    db.execute("insert into events values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (g, n, "coord", i, o, u16(o), u16(o + 2), rom[o + 4], sc, None,
                                u16(o + 6), u16(o + 8), None))
                    if rom_ptr(sc) and sc >= ROMBASE + 0x100:
                        entries.append((sc, g, n, "coord", i,
                                        f"var {u16(o + 6):#x}=={u16(o + 8)}"))
            if pb:
                for i in range(nb):
                    o = pb + 12 * i
                    if o + 12 > len(rom):
                        break
                    kind = rom[o + 5]
                    sc = u32(o + 8) if kind < 5 else None
                    db.execute("insert into events values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (g, n, "bg", i, o, u16(o), u16(o + 2), rom[o + 4], sc, None,
                                None, None, json.dumps(dict(kind=kind))))
                    if sc and rom_ptr(sc) and sc >= ROMBASE + 0x100:
                        entries.append((sc, g, n, "bg", i, f"kind {kind}"))
        # map scripts
        if ms and ms + 5 <= len(rom):
            o, slot = ms, 0
            while o + 5 <= len(rom) and rom[o] != 0 and slot < 16:
                tag, tgt = rom[o], u32(o + 1)
                if tag in (2, 4) and rom_ptr(tgt):       # (var, value, script) tables
                    t = tgt - ROMBASE
                    k = 0
                    while t + 8 <= len(rom) and u16(t) != 0 and k < 32:
                        sc = u32(t + 4)
                        db.execute("insert into mscripts values(?,?,?,?,?,?,?,?)",
                                   (g, n, tag, MSCRIPT_TAGS.get(tag), slot, sc, u16(t),
                                    u16(t + 2)))
                        if rom_ptr(sc):
                            entries.append((sc, g, n, "mscript", tag,
                                            f"{MSCRIPT_TAGS.get(tag)} var {u16(t):#x}=={u16(t+2)}"))
                        t += 8
                        k += 1
                else:
                    db.execute("insert into mscripts values(?,?,?,?,?,?,?,?)",
                               (g, n, tag, MSCRIPT_TAGS.get(tag), slot, tgt, None, None))
                    if rom_ptr(tgt):
                        entries.append((tgt, g, n, "mscript", tag, MSCRIPT_TAGS.get(tag, str(tag))))
                o += 5
                slot += 1
    db.executemany("insert into entries values(?,?,?,?,?,?)", entries)

    # ---- scripts: recursive descent from every entry
    cmds, blk_of, blocks, edges = {}, {}, {}, []   # blocks[start] = [cmd addrs]

    def split(at):
        b = blk_of[at]
        if b == at:
            return
        lst = blocks[b]
        i = lst.index(at)
        blocks[b], blocks[at] = lst[:i], lst[i:]
        for a in blocks[at]:
            blk_of[a] = at
        edges.append((lst[i - 1], b, at, "fall"))
        # edges that originated in moved cmds belong to the new block
        for k, e in enumerate(edges):
            if e[1] == b and e[0] >= at and e[0] in blk_of and blk_of[e[0]] == at:
                edges[k] = (e[0], at, e[2], e[3])

    queue = sorted(set(sc - ROMBASE for sc, *_ in entries))
    seen_target = set()
    desync = []
    while queue:
        start = queue.pop()
        if start in seen_target or not (0 <= start < len(rom)):
            continue
        seen_target.add(start)
        if start in cmds:
            split(start)
            continue
        cur, off = start, start
        blocks[start] = []
        while True:
            if off in cmds:                     # ran into known code: fall through to it
                if blocks[cur]:
                    edges.append((blocks[cur][-1], cur, off, "fall"))
                    split(off)
                break
            r = decode_one(rom, off, table) if off < len(rom) else None
            if r is None:
                desync.append((start, off, rom[off] if off < len(rom) else -1))
                break
            name, args, ln = r
            cmds[off] = (ln, rom[off], name, args)
            blk_of[off] = cur
            blocks[cur].append(off)
            tgt = None
            if name in ("goto", "call", "vgoto", "vcall"):
                tgt = args[0]
            elif name in ("goto_if", "call_if", "vgoto_if", "vcall_if"):
                tgt = args[1]
            elif name in ("callnative", "gotonative"):
                edges.append((off, cur, args[0] - ROMBASE, "native"))
            if tgt is not None and rom_ptr(tgt):
                edges.append((off, cur, tgt - ROMBASE, name))
                queue.append(tgt - ROMBASE)
            if name in ("end", "return", "goto", "gotonative", "endram", "returnram",
                        "vgoto", "gotostd"):
                break
            off += ln
    # text for readability
    def fmt(name, a):
        out = []
        for v in a:
            out.append(f"0x{v:08X}" if rom_ptr(v) else (str(v) if v < 10 else f"{v:#x}"))
        return " ".join(out)
    db.executemany("insert into cmds values(?,?,?,?,?,?)",
                   [(a, c[0], c[1], c[2], fmt(c[2], c[3]), blk_of[a]) for a, c in cmds.items()])
    db.executemany("insert into edges values(?,?,?,?)", edges)

    # ---- semantic refs from cmds
    VARC = {"setvar": 1, "addvar": 1, "subvar": 1, "copyvar": 1, "setorcopyvar": 1,
            "compare_var_to_value": 1, "compare_var_to_var": 1, "special": 0, "specialvar": 1}
    FLAGC = {"setflag", "clearflag", "checkflag"}
    refs = []
    for a, (ln, op, name, args) in cmds.items():
        if name in FLAGC:
            refs.append(("flag", args[0], a, name, None))
        elif name in ("setvar", "addvar", "subvar", "setorcopyvar", "compare_var_to_value"):
            refs.append(("var", args[0], a, name, args[1]))
            if name == "setorcopyvar" and args[1] >= 0x4000:
                refs.append(("var", args[1], a, "setorcopyvar-src", None))
        elif name in ("copyvar", "compare_var_to_var"):
            refs.append(("var", args[0], a, name, args[1]))
            refs.append(("var", args[1], a, name + "-src", None))
        elif name == "specialvar":
            refs.append(("var", args[0], a, name, args[1]))
            refs.append(("special", args[1], a, name, None))
        elif name == "special":
            refs.append(("special", args[0], a, name, None))
        elif name in ("callnative", "gotonative"):
            refs.append(("native", args[0] & ~1, a, name, None))
        elif name in ("givemon", "additem", "removeitem", "checkitem", "checkitemspace"):
            refs.append(("item" if name != "givemon" else "species", args[0], a, name, None))
    # events gating on vars / flags
    for g, n, kind, idx, addr, flag, var, val in db.execute(
            "select g,n,kind,idx,addr,flag,var,val from events"):
        if var is not None:
            refs.append(("var", var, addr, f"gate:{kind}", val))
        if flag:
            refs.append(("flag", flag, addr, "obj_flag", None))
    for g, n, tag, tn, slot, tgt, var, val in db.execute("select * from mscripts"):
        if var:
            refs.append(("var", var, (g << 8) | n, f"gate:mscript{tag}", val))
    db.executemany("insert into refs values(?,?,?,?,?)", refs)

    # ---- hack code: functions + literals
    hc_path = os.path.join(ROOT, "data/hack_code.json")
    if os.path.exists(hc_path):
        hc = json.load(open(hc_path))
        funcs = sorted(hc["funcs"])
        codes = sorted(hc["code"])
        ends = {}
        for s in funcs:
            i = bisect.bisect_right([c[0] for c in codes], s) - 1
            ends[s] = codes[i][1] if i >= 0 and codes[i][0] <= s < codes[i][1] else s
        db.executemany("insert into funcs values(?,?)", ends.items())
        lit = []
        for off, d in hc["literals"].items():
            for u in d["uses"]:
                i = bisect.bisect_right(funcs, u) - 1
                lit.append((int(off), d["value"], u, funcs[i] if i >= 0 else None))
        db.executemany("insert into lit values(?,?,?,?)", lit)

    # ---- strings / names
    zh = json.load(open(os.path.join(ROOT, "text/zh.json")))
    tm = json.load(open(os.path.join(ROOT, "text/en/strings.json")))
    rows = []
    for a, v in zh["strings"].items():
        rows.append((int(a, 16), v["zh"], tm.get(v["zh"]), v.get("cap"), json.dumps(v["refs"])))
    db.executemany("insert or replace into strings values(?,?,?,?,?)", rows)
    for tname, t in zh["tables"].items():
        enp = os.path.join(ROOT, f"text/en/tables/{tname}.json")
        en = json.load(open(enp)) if os.path.exists(enp) else {}
        for i, z in t["entries"].items():
            db.execute("insert into names values(?,?,?,?)", (tname, int(i), z, en.get(i)))

    # ---- notes (persisted, hand-curated)
    if os.path.exists(NOTES):
        for target, text in json.load(open(NOTES)):
            db.execute("insert into notes values(?,?)", (target, text))
    db.execute("insert into meta values('rom',?)", (os.path.abspath(rom_path),))
    db.commit()
    for t in ("maps", "events", "cmds", "edges", "entries", "refs", "strings", "lit", "funcs"):
        print(f"{t:8} {db.execute(f'select count(*) from {t}').fetchone()[0]}")
    print(f"script desyncs (unknown opcode): {len(desync)} (query: select via `sql`; first 5 "
          f"{[(hex(s+ROMBASE), hex(o+ROMBASE), b) for s, o, b in desync[:5]]})")
    db.execute("create table desync(start int, off int, op int)")
    db.executemany("insert into desync values(?,?,?)", desync)
    db.commit()
    print("wrote", out)


# --------------------------------------------------------------- queries ----

class Q:
    def __init__(self, rom_path=ORIG):
        p = db_path(rom_path)
        if not os.path.exists(p):
            raise SystemExit(f"{p} missing: run `python3 scripts/hackdb.py build`")
        self.db = sqlite3.connect(p)
        self.rom = open(self.db.execute("select v from meta where k='rom'").fetchone()[0],
                        "rb").read()
        self.table = script_table()
        self._rev = None

    def sql(self, q, *a):
        return self.db.execute(q, a).fetchall()

    def label(self, g, n):
        lab = self.sql("select text from notes where target=?", f"map:{g}.{n}")
        nm = json.load(open(os.path.join(ROOT, "data/map_names.json"))).get(f"{g}.{n}")
        short = [re.split(r"\s+[(\u2014-]\s*|\s*;", x[0])[0] for x in lab]
        return " / ".join(short + ([nm] if nm else []))

    def string(self, ptr):
        r = self.sql("select zh,en from strings where addr=?", ptr - ROMBASE)
        return r[0] if r else None

    # reverse reachability: cmd/script address -> entries
    def _graph(self):
        if self._rev is None:
            rev = {}
            for src_blk, dst in self.sql("select src_blk,dst from edges"):
                rev.setdefault(dst, set()).add(src_blk)
            self._rev = rev
        return self._rev

    def entries_reaching(self, addr):
        addr = to_off(addr)
        r = self.sql("select blk from cmds where addr=?", addr)
        starts = {r[0][0]} if r else {addr}
        rev, seen, todo = self._graph(), set(), list(starts)
        while todo:
            b = todo.pop()
            if b in seen:
                continue
            seen.add(b)
            todo.extend(rev.get(b, ()))
        ent = self.sql(f"select addr,g,n,kind,idx,detail from entries where addr+0 in "
                       f"({','.join('?' * len(seen))})", *[s + ROMBASE for s in seen]) if seen else []
        return ent, len(seen)

    def func_of(self, off):
        r = self.sql("select start,end from funcs where start<=? order by start desc limit 1", off)
        return r[0] if r and (r[0][1] > off or r[0][1] == r[0][0]) else None


def show_script(q, addr, maxn=400):
    off = to_off(addr)
    seen = set()
    lines, todo = [], [off]
    n = 0
    while todo and n < maxn:
        o = todo.pop(0)
        if o in seen:
            continue
        while n < maxn:
            if o in seen:
                break
            seen.add(o)
            r = decode_one(q.rom, o, q.table)
            if r is None:
                lines.append(f"{o + ROMBASE:08X}: .byte {q.rom[o]:#04x}   <unknown opcode, stop>")
                break
            name, args, ln = r
            txt = " ".join(f"0x{v:08X}" if rom_ptr(v) else (str(v) if v < 10 else f"{v:#x}")
                           for v in args)
            extra = ""
            for v in args:
                if rom_ptr(v):
                    s = q.string(v)
                    if s:
                        extra = f'   ; "{(s[1] or s[0]).replace(chr(10), "\\n")}"'
                        break
            lines.append(f"{o + ROMBASE:08X}: {name} {txt}{extra}".rstrip())
            n += 1
            if name in ("goto", "goto_if", "call", "call_if"):
                t = args[0] if name in ("goto", "call") else args[1]
                if rom_ptr(t):
                    todo.append(t - ROMBASE)
            if name in ("end", "return", "goto", "gotonative", "endram", "gotostd"):
                break
            o += ln
        lines.append("")
    return lines


def where_entry(q, entries, limit=12):
    out = []
    for addr, g, n, kind, idx, det in entries[:limit]:
        out.append(f"   <- {g}.{n} {q.label(g, n)} {kind}#{idx} {det}  entry {addr:#010x}")
    if len(entries) > limit:
        out.append(f"   ... +{len(entries) - limit} more entries")
    return out


def cmd_map(q, arg):
    g, n = (int(x) for x in arg.split("."))
    m = q.sql("select * from maps where g=? and n=?", g, n)
    if not m:
        raise SystemExit("no such map")
    (_, _, hdr, lay, ev, ms, conn, music, lid, reg, cave, wea, mt, fl, bt) = m[0]
    print(f"== map {g}.{n}  {q.label(g, n)}")
    print(f"header {hdr:#x} layout {lay:#x} (id {lid}) events {ev:#x} mscripts {ms:#x} "
          f"conn {conn and hex(conn)} music {music:#x} region {reg:#x} weather {wea} type {mt}")
    for note in q.sql("select text from notes where target=?", f"map:{g}.{n}"):
        print("note:", note[0])
    for d, off, tg, tn in q.sql("select dir,off,tg,tn from conns where g=? and n=?", g, n):
        print(f"connection dir {d} off {off} -> {tg}.{tn} {q.label(tg, tn)}")
    for tag, tn, slot, tgt, var, val in q.sql(
            "select tag,tagname,slot,target,var,val from mscripts where g=? and n=?", g, n):
        gate = f" if var {var:#x}=={val}" if var else ""
        print(f"mscript {tn or tag}{gate} -> {tgt:#010x}")
    for kind in ("warp", "coord", "bg", "obj"):
        for idx, addr, x, y, el, sc, fl, var, val, data in q.sql(
                "select idx,addr,x,y,elev,script,flag,var,val,data from events "
                "where g=? and n=? and kind=? order by idx", g, n, kind):
            d = json.loads(data) if data else {}
            s = f"{kind:5}#{idx:<2} ({x},{y})"
            if kind == "warp":
                s += f" -> {d['tg']}.{d['tn']} warp {d['warp']} {q.label(d['tg'], d['tn'])}"
            elif kind == "coord":
                s += f" gate var {var:#x}=={val} script {sc:#010x}"
            elif kind == "bg":
                s += f" kind {d['kind']} script {sc and f'{sc:#010x}'}"
            else:
                s += (f" local {d['local']} gfx {d['gfx']} mv {d['mv']} flag {fl:#x} "
                      f"script {sc:#010x}" + (" PLACEHOLDER" if sc and sc < 0x08000100 else "")
                      + (f" trainer {d['trainer']}" if d['trainer'] else ""))
            print("  " + s)


def cmd_maps(q, pat):
    for g, n, ob, co, bg in q.sql(
            "select m.g,m.n,"
            "(select count(*) from events e where e.g=m.g and e.n=m.n and kind='obj'),"
            "(select count(*) from events e where e.g=m.g and e.n=m.n and kind='coord'),"
            "(select count(*) from events e where e.g=m.g and e.n=m.n and kind='bg') "
            "from maps m order by 1,2"):
        lab = q.label(g, n)
        if pat and pat.lower() not in f"{g}.{n} {lab}".lower():
            continue
        print(f"{g}.{n:<3} obj {ob:<3} coord {co:<2} bg {bg:<2} {lab}")


def ramvar(v):
    return VAR_BASE_RAM + (v - VAR_BASE_ID) * 2 if v >= VAR_BASE_ID else None


def cmd_ref(q, kind, idv):
    print(f"== {kind} {idv:#x}" + (f"   RAM {ramvar(idv):#x} (hack var array)"
                                   if kind == "var" and ramvar(idv) else ""))
    for t in q.sql("select text from notes where target in (?,?)", f"{kind}:{idv}",
                   f"{kind}:{idv:#x}"):
        print("note:", t[0])
    rs = q.sql("select cmd,name,val from refs where kind=? and id=? order by cmd", kind, idv)
    print(f"-- script/event references: {len(rs)}")
    for cmd, name, val in rs:
        if name.startswith("gate:mscript"):
            g, n = cmd >> 8, cmd & 0xFF
            print(f"  {name} == {val}  map {g}.{n} {q.label(g, n)}")
            continue
        if name.startswith("gate:") or name == "obj_flag":
            e = q.sql("select g,n,kind,idx,x,y,script from events where addr=?", cmd)
            if e:
                g, n, k, i, x, y, sc = e[0]
                print(f"  {name}{'' if val is None else f' == {val}'}  map {g}.{n} "
                      f"{q.label(g, n)} {k}#{i} ({x},{y}) script {sc and f'{sc:#010x}'}")
                continue
        c = q.sql("select addr from cmds where addr=?", cmd)
        ents, _ = q.entries_reaching(cmd) if c else ([], 0)
        nx = q.sql("select name,args from cmds where addr>? order by addr limit 1", cmd)
        tail = f" -> then {nx[0][0]} {nx[0][1]}" if name.startswith("compare") and nx else ""
        print(f"  {cmd + ROMBASE:#010x} {name}{'' if val is None else f' {val:#x}'}{tail}")
        for l in where_entry(q, ents, 4):
            print(l)
    ls = q.sql("select use,func,off from lit where value=?", idv)
    if kind == "var" or len(ls) < 40:
        print(f"-- hack-code literals with this value: {len(ls)}"
              + ("  (small numbers are ambiguous: any constant)" if idv < 0x400 else ""))
        for use, fn, off in ls[:30]:
            print(f"  use {use + ROMBASE:#010x} in func {fn and f'{fn + ROMBASE:#010x}'} "
                  f"(literal @ {off + ROMBASE:#010x})")


def cmd_text(q, pat):
    like = f"%{pat}%"
    rows = q.sql("select addr,zh,en,refs from strings where zh like ? or en like ? limit 25",
                 like, like)
    for addr, zh, en, refs in rows:
        print(f"== string {addr + ROMBASE:#010x}\n   zh: {zh!r}\n   en: {en!r}")
        for r in json.loads(refs)[:8]:
            site, kind = r.split(":")
            site = int(site, 16)
            c = q.sql("select addr,name from cmds where addr<=? and addr+len>? order by addr desc "
                      "limit 1", site, site)
            print(f"   ref {site + ROMBASE:#010x} ({kind})", end="")
            if c:
                ents, _ = q.entries_reaching(c[0][0])
                print(f" in cmd {c[0][1]} @ {c[0][0] + ROMBASE:#010x}")
                for l in where_entry(q, ents, 6):
                    print(l)
            else:
                print()


def cmd_whatis(q, a):
    off = to_off(a)
    print(f"== {off + ROMBASE:#010x}  (file {off:#x})")
    fm = json.load(open(os.path.join(ROOT, "data/fr_map.json")))
    regs = [r for r in fm["regions"] if r[0] <= off < r[1]]
    if regs:
        r = regs[0]
        syms = [s for s in fm["symbols"] if s[0] <= off]
        print(f"vanilla layout: {r[2]} {r[3]} {r[4]}  [{r[0]:#x},{r[1]:#x})"
              + (f"  symbol {syms[-1][2]}+{off - syms[-1][0]:#x}" if syms else ""))
    f = q.func_of(off)
    if f:
        print(f"hack function: {f[0] + ROMBASE:#010x}..{f[1] + ROMBASE:#010x}")
    elif off >= 0xD00000 and q.sql("select 1 from funcs limit 1"):
        prv = q.sql("select start from funcs where start<=? order by start desc limit 1", off)
        nxt = q.sql("select start from funcs where start>? order by start limit 1", off)
        print("not inside a function hackmap found (code reached only via function-pointer "
              "tables, or data). nearest: "
              f"{prv and hex(prv[0][0] + ROMBASE)} / {nxt and hex(nxt[0][0] + ROMBASE)}. "
              f"Decompile in Ghidra: get_functions address={off:#x} (image base 0).")
    s = q.sql("select addr,zh,en,refs from strings where addr<=? order by addr desc limit 1", off)
    if s and len(s[0][1]) and off < s[0][0] + max(len(s[0][1]) * 2, 2):
        print(f"string {s[0][0] + ROMBASE:#010x}: zh {s[0][1]!r} en {s[0][2]!r}")
    c = q.sql("select addr,name,args,blk from cmds where addr<=? and addr+len>? "
              "order by addr desc limit 1", off, off)
    if c:
        print(f"script cmd {c[0][0] + ROMBASE:#010x}: {c[0][1]} {c[0][2]} (block {c[0][3] + ROMBASE:#010x})")
        ents, nb = q.entries_reaching(off)
        for l in where_entry(q, ents):
            print(l)
    for row in q.sql("select g,n,kind,idx,x,y from events where addr<=? and addr+24>? "
                     "order by addr desc limit 1", off, off):
        print("event struct: map %d.%d %s#%d (%d,%d)" % row)
    for row in q.sql("select g,n from maps where hdr=? or events=? or mscripts=?", off, off, off):
        print("map header/events/mscripts of %d.%d" % row)
    for (t,) in q.sql("select text from notes where target=?", f"{off + ROMBASE:#010x}".lower()):
        print("note:", t)
    u = q.sql("select off,value from lit where use=?", off)
    for o, v in u:
        print(f"literal loaded here: @{o + ROMBASE:#010x} = {v:#x}")


def cmd_names(q, tbl, key):
    if key.isdigit() or key.startswith("0x"):
        rows = q.sql("select tbl,id,zh,en from names where tbl=? and id=?", tbl, num(key))
    else:
        rows = q.sql("select tbl,id,zh,en from names where tbl=? and (zh like ? or en like ?)",
                     tbl, f"%{key}%", f"%{key}%")
    for r in rows[:40]:
        print("%s %d  %s  /  %s" % r)


def cmd_note(args):
    if args[0] == "add":
        target, text = args[1], " ".join(args[2:])
        data = json.load(open(NOTES)) if os.path.exists(NOTES) else []
        data.append([target, text])
        json.dump(data, open(NOTES, "w"), ensure_ascii=False, indent=1)
        print("saved; `build` to load it into the db")
    else:
        for t, x in (json.load(open(NOTES)) if os.path.exists(NOTES) else []):
            print(f"{t}: {x}")


def main():
    a = sys.argv[1:]
    rom = ORIG
    if "--rom" in a:
        i = a.index("--rom")
        rom = a[i + 1]
        del a[i:i + 2]
    if not a or a[0] in ("-h", "--help"):
        raise SystemExit(__doc__)
    c, rest = a[0], a[1:]
    if c == "build":
        return build(rom)
    if c == "note":
        return cmd_note(rest)
    q = Q(rom)
    if c == "map":
        cmd_map(q, rest[0])
    elif c == "maps":
        cmd_maps(q, rest[0] if rest else "")
    elif c in ("var", "flag"):
        cmd_ref(q, c, num(rest[0]))
    elif c == "text":
        cmd_text(q, " ".join(rest))
    elif c == "script":
        print("\n".join(show_script(q, rest[0])))
        ents, _ = q.entries_reaching(rest[0])
        print("reached from:")
        print("\n".join(where_entry(q, ents)) or "   (no known entry)")
    elif c == "who":
        ents, nb = q.entries_reaching(rest[0])
        print(f"{nb} blocks upstream")
        print("\n".join(where_entry(q, ents, 50)) or "   (no known entry)")
    elif c == "whatis":
        cmd_whatis(q, rest[0])
    elif c == "names":
        cmd_names(q, rest[0], rest[1])
    elif c == "sql":
        for r in q.sql(" ".join(rest)):
            print(r)
    elif c == "schema":
        for (s,) in q.sql("select sql from sqlite_master where type='table'"):
            print(s)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
