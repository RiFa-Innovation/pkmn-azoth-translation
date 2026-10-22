"""Add maps and map events to the ROM (spec: data/new_maps.json).

Used by insert.py (apply). Everything is allocated from the free pool and
reuses existing layouts/tilesets, so a new map costs a header plus events.

Spec:
  {"groups": {"58": [ {"name": ..., "clone": "3.81",         # header copied from this map
                       "mapsec": 204,                        # optional overrides
                       "music": null, "weather": null,
                       "events": {"objects": [...], "warps": [...], "coords": [...], "bgs": [...]}} ]}},
   "append_events": [ {"map": "3.106", "warps": [...], "objects": [...], ...} ]}

Event dicts (all ints; script/ptr fields are ROM addresses 0x08xxxxxx or 0):
  warp   {x, y, elev, warp_id, to: "G.N"}
  object {x, y, elev, local_id, gfx, movement, range, trainer_type, trainer_sight, script, flag}
         (a missing script/flag is 0 = no script, never the 0x08000000 placeholder)
  coord  {x, y, elev, var, value, script}
  bg     {x, y, elev, kind, script}
The gMapGroups table (0xB3B100) has ONE spare slot (58, filled with 0xF7F7F7F7); slot 59 is the terminator.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import mercury_text as mt  # noqa: E402
import owgfx  # noqa: E402
import scrasm  # noqa: E402

GROUP_TABLE = 0xB3B100
LAYOUT_TABLE = 0xA66440     # gMapLayouts: pointer per layout id (id 1 first); the game loads the layout by
                            # the header's layout id, NOT by the header's layout pointer
FREE_LAYOUT_IDS = list(range(52, 78))   # ids no map header uses (checked with hackdb), pointer slots reusable
ROM_BASE = 0x08000000
FILL = 0xF7F7F7F7
HEADER = 28
SPARE = (58,)


def u32(rom, o):
    return struct.unpack_from("<I", rom, o)[0]


def header_off(rom, g, n):
    gp = u32(rom, GROUP_TABLE + 4 * g) - ROM_BASE
    return u32(rom, gp + 4 * n) - ROM_BASE


def pack_warp(w):
    g, n = (int(x) for x in w["to"].split("."))
    return struct.pack("<hhBBBB", w["x"], w["y"], w.get("elev", 0), w["warp_id"], n, g)


def pack_object(o):
    return struct.pack("<BHBhhBBBBHHIHH", o["local_id"], o["gfx"], 0, o["x"], o["y"], o.get("elev", 0),
                       o.get("movement", 0), o.get("range", 0), 0, o.get("trainer_type", 0),
                       o.get("trainer_sight", 0), o.get("script", 0), o.get("flag", 0), 0)


def pack_coord(c):
    return struct.pack("<HHBBHHHI", c["x"], c["y"], c.get("elev", 0), 0, c["var"], c["value"], 0, c["script"])


def pack_bg(b):
    return struct.pack("<HHBBHI", b["x"], b["y"], b.get("elev", 0), b["kind"], 0, b["script"])


SIZES = {"objects": 24, "warps": 8, "coords": 16, "bgs": 12}
PACK = {"objects": pack_object, "warps": pack_warp, "coords": pack_coord, "bgs": pack_bg}
ORDER = ("objects", "warps", "coords", "bgs")   # counts at +0..+3, pointers at +4,+8,+12,+16


SCRIPT_AT = {"objects": 16, "coords": 12, "bgs": 8}


def _edit(kind, entry, ed):
    e = bytearray(entry)
    if kind == "warps":
        if "to" in ed:
            g, n = (int(x) for x in ed["to"].split("."))
            e[6], e[7] = n, g
        if "warp_id" in ed:
            e[5] = ed["warp_id"]
        if "x" in ed:
            e[0:2] = struct.pack("<h", ed["x"])
        if "y" in ed:
            e[2:4] = struct.pack("<h", ed["y"])
    if "script" in ed:
        e[SCRIPT_AT[kind]:SCRIPT_AT[kind] + 4] = struct.pack("<I", ed["script"])
    if "flag" in ed and kind == "objects":
        e[20:22] = struct.pack("<H", ed["flag"])
    return bytes(e)


def build_events(rom, pool, ev_off, add):
    """Return a new events struct offset: old arrays copied (with optional `edit`) and `add` appended."""
    counts = list(rom[ev_off:ev_off + 4]) if ev_off else [0, 0, 0, 0]
    ptrs = [u32(rom, ev_off + 4 + 4 * i) for i in range(4)] if ev_off else [0] * 4
    edits = add.get("edit", {})
    out_ptrs = []
    for i, kind in enumerate(ORDER):
        sz = SIZES[kind]
        o = ptrs[i] - ROM_BASE if ptrs[i] else 0
        old = [bytes(rom[o + k * sz:o + (k + 1) * sz]) for k in range(counts[i])] if ptrs[i] else []
        if kind == "warps":
            for k, w in enumerate(old):
                dest = f"{w[7]}.{w[6]}"
                if dest in add.get("remap", {}):
                    old[k] = _edit("warps", w, {"to": add["remap"][dest]})
        for idx, ed in edits.get(kind, {}).items():
            assert len(old[int(idx)]) == sz, (kind, idx, ev_off, ptrs, counts, len(old[int(idx)]))
            old[int(idx)] = _edit(kind, old[int(idx)], ed)
        keep = [k for k in range(len(old)) if k not in add.get("remove", {}).get(kind, [])]
        if len(keep) != len(old):
            counts[i] -= len(old) - len(keep)
            old = [old[k] for k in keep]
        new = [PACK[kind](e) for e in add.get(kind, [])]
        blob = b"".join(old + new)
        counts[i] += len(new)
        assert counts[i] < 256, f"too many {kind}"
        if blob and (new or edits.get(kind) or add.get("remap") or add.get("remove", {}).get(kind)):
            a = pool.alloc_aligned(len(blob))
            rom[a:a + len(blob)] = blob
            out_ptrs.append(ROM_BASE + a)
        else:
            out_ptrs.append(ptrs[i])
    a = pool.alloc_aligned(20)
    rom[a:a + 20] = bytes(counts) + struct.pack("<4I", *out_ptrs)
    return a


def build_script(sc):
    """{"warp": "G.N", "x": X, "y": Y} -> warp (explicit x/y); waitstate; end."""
    if "warp" in sc:
        g, n = (int(x) for x in sc["warp"].split("."))
        return bytes([0x39, g, n, 0xFF]) + struct.pack("<HH", sc["x"], sc["y"]) + bytes([0x27, 0x02])
    return bytes.fromhex(sc["hex"])


class _Any(dict):
    def __getitem__(self, k):
        return 0


def _resolve_scripts(spec, scripts):
    def fix(ev):
        for key in ("objects", "coords", "bgs"):
            for e in ev.get(key, []):
                if isinstance(e.get("script"), str):
                    e["script"] = scripts[e["script"]]
            for e in ev.get("edit", {}).get(key, {}).values():
                if isinstance(e.get("script"), str):
                    e["script"] = scripts[e["script"]]
    for m in spec.get("append_events", []):
        fix(m)
    for maps in spec.get("groups", {}).values():
        for m in maps:
            fix(m.get("events", {}))


def land_encounter_layout(rom, src, pool, lay_ptr, cache):
    """Clone a layout whose secondary tileset marks its plain floor tiles as land-encounter
    tiles (attribute bits 24-26 = 1). Returns the new layout's ROM address.
    The tileset clone is cached per (secondary tileset, id set)."""
    lo = lay_ptr - ROM_BASE
    w, h, border, mp, pri, sec = struct.unpack_from("<IIIIII", src, lo)
    pri_o, sec_o = pri - ROM_BASE, sec - ROM_BASE
    attrs = {}
    for base, ts, cnt in ((0, pri_o, 640), (640, sec_o, 384)):
        a = u32(src, ts + 20) - ROM_BASE
        for i in range(cnt):
            attrs[base + i] = u32(src, a + 4 * i)
    blocks = struct.unpack_from(f"<{w * h}H", src, mp - ROM_BASE)
    ids = sorted({b & 0x3FF for b in blocks if not b & 0xC00
                  and (b & 0x3FF) >= 640 and (attrs[b & 0x3FF] & 0x1FF) == 0
                  and (attrs[b & 0x3FF] >> 24) & 7 == 0 and (b & 0x3FF) != 1023})
    key = (sec, tuple(ids))
    if key not in cache:
        a_old = u32(src, sec_o + 20) - ROM_BASE
        tbl = bytearray(src[a_old:a_old + 384 * 4])
        for i in ids:
            v = struct.unpack_from("<I", tbl, 4 * (i - 640))[0] | (1 << 24)
            struct.pack_into("<I", tbl, 4 * (i - 640), v)
        ta = pool.alloc_aligned(len(tbl))
        rom[ta:ta + len(tbl)] = tbl
        ts_new = pool.alloc_aligned(24)
        blob = bytearray(src[sec_o:sec_o + 24])
        struct.pack_into("<I", blob, 20, ROM_BASE + ta)
        rom[ts_new:ts_new + 24] = blob
        cache[key] = ROM_BASE + ts_new
    new_lay = pool.alloc_aligned(24)
    blob = bytearray(src[lo:lo + 24])
    struct.pack_into("<I", blob, 20, cache[key])
    rom[new_lay:new_lay + 24] = blob
    return ROM_BASE + new_lay


def build_layouts(rom, src, pool, layouts):
    """New layouts cut out of an existing one: {"name": {"from": "G.N", "crop": [x, y, w, h],
    "patch": [{"x", "y", "block"}]}}. The tilesets and border are shared with the source; only the
    block data (w*h*2 bytes) and a 24-byte layout struct are new. Returns name -> (address, layout id)."""
    out = {}
    for name, L in layouts.items():
        g, n = (int(x) for x in L["from"].split("."))
        lo = u32(src, header_off(src, g, n)) - ROM_BASE
        w, h, border, mp, pri, sec = struct.unpack_from("<IIIIII", src, lo)
        x0, y0, cw, ch = L["crop"]
        assert x0 + cw <= w and y0 + ch <= h, f"{name}: crop outside {w}x{h}"
        blocks = [list(struct.unpack_from(f"<{cw}H", src, mp - ROM_BASE + 2 * ((y0 + y) * w + x0))) for y in range(ch)]
        for pt in L.get("patch", []):
            blocks[pt["y"]][pt["x"]] = pt["block"]
        blob = b"".join(struct.pack(f"<{cw}H", *row) for row in blocks)
        ba = pool.alloc_aligned(len(blob))
        rom[ba:ba + len(blob)] = blob
        la = pool.alloc_aligned(24)
        rom[la:la + 24] = struct.pack("<IIIIII", cw, ch, border, ROM_BASE + ba, pri, sec)
        lid = FREE_LAYOUT_IDS.pop(0)
        rom[LAYOUT_TABLE + 4 * (lid - 1):LAYOUT_TABLE + 4 * lid] = struct.pack("<I", ROM_BASE + la)
        out[name] = (ROM_BASE + la, lid)
    return out


def apply(rom, src, pool, spec_path="data/new_maps.json"):
    spec = json.load(open(spec_path, encoding="utf-8"))
    report = {"maps": 0, "bytes": 0}
    before = pool.total()
    scripts = {}
    widths = bytes(src[mt.WIDTHS_OFF:mt.WIDTHS_OFF + 256])
    fr_ext = None
    if spec.get("frontier"):          # Spectrum Frontier (scripts/frontier_build.py): natives + tables first, then its maps and scripts join the spec
        import frontier_build as fb
        fr_ext = fb.link(rom, src, pool)
        scripts.update(fr_ext["externs"])
        fb.extend(spec, fr_ext)

    def store(b):
        b = b if b.endswith(b"\xff") else b + b"\xff"
        a = pool.alloc_aligned(len(b))
        rom[a:a + len(b)] = b
        return ROM_BASE + a

    if spec.get("overworld_sprites"):
        report["overworld_sprites"] = owgfx.install(rom, src, pool, spec["overworld_sprites"])
    end_script = None
    for ms in spec.get("map_scripts", []):
        g, n = (int(x) for x in ms["map"].split("."))
        h = header_off(src, g, n)
        tbl = u32(src, h + 8)
        orig = 0
        if tbl:
            o = tbl - ROM_BASE
            while src[o]:
                if src[o] == 3:
                    orig = u32(src, o + 1)
                o += 5
        if not orig:
            if end_script is None:
                end_script = ROM_BASE + pool.alloc_aligned(1)
                rom[end_script - ROM_BASE] = 0x02
            orig = end_script
        scripts[f"orig_{g}_{n}_transition"] = orig
    plain = {n: sc for n, sc in spec.get("scripts", {}).items() if "asm" not in sc}
    asm = {n: sc for n, sc in spec.get("scripts", {}).items() if "asm" in sc}
    for name, sc in plain.items():
        code = build_script(sc)
        a = pool.alloc_aligned(len(code))
        rom[a:a + len(code)] = code
        scripts[name] = ROM_BASE + a
    sizes = {n: len(scrasm.assemble(sc["asm"], 0, widths, _Any(), lambda b: 0)) for n, sc in asm.items()}
    for name in asm:
        scripts[name] = ROM_BASE + pool.alloc_aligned(sizes[name])
    for name, sc in asm.items():
        code = scrasm.assemble(sc["asm"], scripts[name], widths, scripts, store)
        a = scripts[name] - ROM_BASE
        rom[a:a + len(code)] = code
    _resolve_scripts(spec, scripts)
    for ms in spec.get("map_scripts", []):
        g, n = (int(x) for x in ms["map"].split("."))
        h = header_off(src, g, n)
        tbl = u32(src, h + 8)
        entries = []
        if tbl:
            o = tbl - ROM_BASE
            while src[o]:
                entries.append([src[o], u32(src, o + 1)])
                o += 5
        new = scripts[ms["on_transition"]]
        for e_ in entries:
            if e_[0] == 3:
                e_[1] = new
                break
        else:
            entries.append([3, new])
        blob = b"".join(struct.pack("<BI", t, p) for t, p in entries) + b"\x00"
        ta = pool.alloc_aligned(len(blob))
        rom[ta:ta + len(blob)] = blob
        rom[h + 8:h + 12] = struct.pack("<I", ROM_BASE + ta)
    # appended events on existing maps: build a fresh events struct and repoint the header (+4)
    for item in spec.get("append_events", []):
        g, n = (int(x) for x in item["map"].split("."))
        h = header_off(src, g, n)
        ev = u32(src, h + 4) - ROM_BASE
        # events structs may be shared between maps; build_events always copies, so only this header is repointed
        new_ev = build_events(rom, pool, ev, item)
        rom[h + 4:h + 8] = struct.pack("<I", ROM_BASE + new_ev)
    tile_cache = {}
    layouts = build_layouts(rom, src, pool, spec.get("layouts", {}))
    for gs, maps in spec.get("groups", {}).items():
        g = int(gs)
        assert g in SPARE, f"group {g}: only spare slots {SPARE} are free"
        slot = GROUP_TABLE + 4 * g
        assert u32(src, slot) == FILL, f"group slot {g} is not spare"
        arr = pool.alloc_aligned(4 * len(maps))
        for i, m in enumerate(maps):
            cg, cn = (int(x) for x in m["clone"].split("."))
            hdr = bytearray(src[header_off(src, cg, cn):header_off(src, cg, cn) + HEADER])
            hdr[8:16] = bytes(8)                         # no map scripts, no connections
            if m.get("layout"):
                lay, lid = layouts[m["layout"]]
                struct.pack_into("<I", hdr, 0, lay)
                struct.pack_into("<H", hdr, 18, lid)
            if m.get("land_encounter"):
                lay = land_encounter_layout(rom, src, pool, struct.unpack_from("<I", hdr, 0)[0], tile_cache)
                lid = FREE_LAYOUT_IDS.pop(0)
                assert u32(src, LAYOUT_TABLE + 4 * (struct.unpack_from("<H", hdr, 18)[0] - 1)) == struct.unpack_from("<I", hdr, 0)[0]
                rom[LAYOUT_TABLE + 4 * (lid - 1):LAYOUT_TABLE + 4 * lid] = struct.pack("<I", lay)
                struct.pack_into("<I", hdr, 0, lay)
                struct.pack_into("<H", hdr, 18, lid)
            if m.get("map_scripts"):      # map scripts on a new map: frame table (tag 2), on-transition (3), on-resume (5)
                mscr, entries = m["map_scripts"], []
                if mscr.get("frame"):
                    tbl = b"".join(struct.pack("<HHI", e["var"], e["value"], scripts[e["script"]]) for e in mscr["frame"]) + b"\x00\x00"
                    ta = pool.alloc_aligned(len(tbl))
                    rom[ta:ta + len(tbl)] = tbl
                    entries.append((2, ROM_BASE + ta))
                if mscr.get("transition"):
                    entries.append((3, scripts[mscr["transition"]]))
                if mscr.get("resume"):
                    entries.append((5, scripts[mscr["resume"]]))
                blob = b"".join(struct.pack("<BI", t, p_) for t, p_ in entries) + b"\x00"
                ba = pool.alloc_aligned(len(blob))
                rom[ba:ba + len(blob)] = blob
                struct.pack_into("<I", hdr, 8, ROM_BASE + ba)
            if m.get("mapsec") is not None:
                hdr[20] = m["mapsec"]
            if m.get("music") is not None:
                struct.pack_into("<H", hdr, 16, m["music"])
            if m.get("weather") is not None:
                hdr[22] = m["weather"]
            src_ev = 0
            if m.get("events_from"):
                fg, fn = (int(x) for x in m["events_from"].split("."))
                src_ev = u32(src, header_off(src, fg, fn) + 4) - ROM_BASE
            ev = build_events(rom, pool, src_ev, m.get("events", {}))
            struct.pack_into("<I", hdr, 4, ROM_BASE + ev)
            ha = pool.alloc_aligned(HEADER)
            rom[ha:ha + HEADER] = hdr
            rom[arr + 4 * i:arr + 4 * i + 4] = struct.pack("<I", ROM_BASE + ha)
            report["maps"] += 1
        rom[slot:slot + 4] = struct.pack("<I", ROM_BASE + arr)
    if spec.get("trainer_pics"):
        report["trainer_pics"] = add_trainer_pics(rom, src, pool, spec["trainer_pics"])
    if spec.get("trainers"):
        report["trainers"] = add_trainers(rom, pool, spec["trainers"])
    if spec.get("wild"):
        report["wild"] = add_wild(rom, src, pool, spec["wild"])
    if fr_ext:                        # last: the trainer table moves, so River's own trainers (written above) must already be in it
        report["frontier"] = {**{k: v for k, v in fr_ext.items() if k not in ("externs", "at")}, **fb.finalize(rom, src, pool),
                              "scripts": {k: f"{v:#010x}" for k, v in scripts.items() if k.startswith("fr_")}}
    report["bytes"] = before - pool.total()
    return report


TRAIN_PIC = 0x23957C            # battle trainer pics: 148 x {ptr, 0x800, tag}; palettes (ptr, tag) follow at +148*8
TRAIN_PAL = TRAIN_PIC + 148 * 8


def _lz_literal(data):
    """GBA LZ77 stream made only of literals (valid, just uncompressed)."""
    out = bytearray(struct.pack("<I", 0x10 | (len(data) << 8)))
    for i in range(0, len(data), 8):
        out.append(0)
        out += data[i:i + 8]
    return bytes(out)


def add_trainer_pics(rom, src, pool, pics):
    """Repurpose unused trainer-pic slots: share another pic's graphics, with a recoloured palette.
    {"index": 17, "pic_from": 135, "recolor": {"3": [r, g, b]}} (colour index -> 8-bit RGB)."""
    for p in pics:
        i, f = p["index"], p["pic_from"]
        rom[TRAIN_PIC + 8 * i:TRAIN_PIC + 8 * i + 8] = src[TRAIN_PIC + 8 * f:TRAIN_PIC + 8 * f + 8]
        po = u32(src, TRAIN_PAL + 8 * f) - ROM_BASE
        pal = bytearray(_lz77_decompress(src, po))
        for ci, (r, g, b) in p.get("recolor", {}).items():
            struct.pack_into("<H", pal, 2 * int(ci), (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
        blob = _lz_literal(bytes(pal))
        a = pool.alloc_aligned(len(blob))
        rom[a:a + len(blob)] = blob
        rom[TRAIN_PAL + 8 * i:TRAIN_PAL + 8 * i + 4] = struct.pack("<I", ROM_BASE + a)
    return len(pics)


def _lz77_decompress(rom, o):
    size = struct.unpack_from("<I", rom, o)[0] >> 8
    out, p = bytearray(), o + 4
    while len(out) < size:
        f = rom[p]
        p += 1
        for b in range(8):
            if len(out) >= size:
                break
            if f & (0x80 >> b):
                a, c = rom[p], rom[p + 1]
                p += 2
                n, d = (a >> 4) + 3, ((a & 15) << 8 | c) + 1
                for _ in range(n):
                    out.append(out[-d])
            else:
                out.append(rom[p])
                p += 1
    return bytes(out)


TRAINER_TABLE = 0x23EACC - 4   # gTrainers: 40-byte entries indexed by trainer id


def add_trainers(rom, pool, trainers):
    """Write trainer entries in place (ids must be unused slots) with their party in the pool.
    party mon: {species, level, iv, item, moves[4]} (16-byte 'item + custom moves' layout)."""
    for t in trainers:
        o = TRAINER_TABLE + 40 * t["id"]
        name = mt.encode_en(t["name"]).rstrip(b"\xff") + b"\xff"
        assert len(name) <= 12
        items = (list(t.get("items", [])) + [0] * 4)[:4]
        custom = all("moves" in m for m in t["party"])   # else: default moves, 8-byte party entries
        ent = struct.pack("<BBBB", 3 if custom else 0, t["class"], t.get("music", 0x0A), t["pic"]) + name.ljust(12, b"\x00")
        ent += struct.pack("<4HIIII", *items, t.get("double", 0), t.get("ai", 7), len(t["party"]), 0)
        party = b""
        for m in t["party"]:
            if custom:
                mv = (list(m["moves"]) + [0] * 4)[:4]
                party += struct.pack("<HBBHH4H", m.get("iv", 255), m["level"], 0, m["species"], m.get("item", 0), *mv)
            else:
                party += struct.pack("<HBBHH", m.get("iv", 128), m["level"], 0, m["species"], 0)
        pa = pool.alloc_aligned(len(party))
        rom[pa:pa + len(party)] = party
        ent = ent[:36] + struct.pack("<I", ROM_BASE + pa)
        rom[o:o + 40] = ent
    return len(trainers)


WILD_TABLE = 0x1E468B0  # the hack's live gWildMonHeaders (20-byte entries, group 0xFF terminates);
                        # 0xCF915C is a stale vanilla-layout copy that no code reads
WILD_SLOTS = {"land": 12, "water": 5, "rock": 5, "fish": 10}


def add_wild(rom, src, pool, entries):
    """Append wild-encounter headers: relocate the table, repoint its 3 literal-pool references."""
    n = 0
    while src[WILD_TABLE + 20 * n] != 0xFF:
        n += 1
    old_end = WILD_TABLE + 20 * (n + 1)
    new_tbl = pool.alloc_aligned(20 * (n + 1 + len(entries)))
    rom[new_tbl:new_tbl + 20 * n] = src[WILD_TABLE:WILD_TABLE + 20 * n]
    for k, e in enumerate(entries):
        g, m = (int(x) for x in e["map"].split("."))
        ptrs = []
        for kind in ("land", "water", "rock", "fish"):
            if kind not in e:
                ptrs.append(0)
                continue
            blk = e[kind]
            mons = blk["mons"]
            assert len(mons) == WILD_SLOTS[kind], f"{e['map']} {kind}: need {WILD_SLOTS[kind]} slots"
            arr = pool.alloc_aligned(4 * len(mons))
            for i, (sp, lo, hi) in enumerate(mons):
                rom[arr + 4 * i:arr + 4 * i + 4] = struct.pack("<BBH", lo, hi, sp)
            info = pool.alloc_aligned(8)
            rom[info:info + 8] = struct.pack("<BBHI", blk["rate"], 0, 0, ROM_BASE + arr)
            ptrs.append(ROM_BASE + info)
        o = new_tbl + 20 * (n + k)
        rom[o:o + 20] = bytes([g, m, 0, 0]) + struct.pack("<4I", *ptrs)
    o = new_tbl + 20 * (n + len(entries))
    rom[o:o + 20] = src[WILD_TABLE + 20 * n:old_end]
    word = struct.pack("<I", ROM_BASE + WILD_TABLE)
    hits = [m.start() for m in __import__("re").finditer(__import__("re").escape(word), src)]
    assert len(hits) == 3, f"expected 3 references to gWildMonHeaders, found {len(hits)}"
    for h in hits:
        rom[h:h + 4] = struct.pack("<I", ROM_BASE + new_tbl)
    return {"entries": len(entries), "table": new_tbl}


def _hdr_ev(src, g, n):
    try:
        gp = u32(src, GROUP_TABLE + 4 * g)
        if not (ROM_BASE <= gp < ROM_BASE + len(src)):
            return None
        h = u32(src, gp - ROM_BASE + 4 * n)
        if not (ROM_BASE <= h < ROM_BASE + len(src)):
            return None
        return u32(src, h - ROM_BASE + 4) - ROM_BASE
    except struct.error:
        return None
