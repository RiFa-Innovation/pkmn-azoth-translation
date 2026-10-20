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
The gMapGroups table (0xB3B100) has two spare slots (58, 59) filled with 0xF7F7F7F7.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import mercury_text as mt  # noqa: E402
import scrasm  # noqa: E402

GROUP_TABLE = 0xB3B100
ROM_BASE = 0x08000000
FILL = 0xF7F7F7F7
HEADER = 28
SPARE = (58, 59)


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


def apply(rom, src, pool, spec_path="data/new_maps.json"):
    spec = json.load(open(spec_path, encoding="utf-8"))
    report = {"maps": 0, "bytes": 0}
    before = pool.total()
    scripts = {}
    widths = bytes(src[mt.WIDTHS_OFF:mt.WIDTHS_OFF + 256])

    def store(b):
        b = b if b.endswith(b"\xff") else b + b"\xff"
        a = pool.alloc_aligned(len(b))
        rom[a:a + len(b)] = b
        return ROM_BASE + a

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
    # appended events on existing maps: build a fresh events struct and repoint the header (+4)
    for item in spec.get("append_events", []):
        g, n = (int(x) for x in item["map"].split("."))
        h = header_off(src, g, n)
        ev = u32(src, h + 4) - ROM_BASE
        users = [1 for gg in range(58) for nn in range(256)
                 if _hdr_ev(src, gg, nn) == ev]
        assert len(users) == 1, f"events of {item['map']} are shared by {len(users)} maps"
        new_ev = build_events(rom, pool, ev, item)
        rom[h + 4:h + 8] = struct.pack("<I", ROM_BASE + new_ev)
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
    report["bytes"] = before - pool.total()
    return report


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
