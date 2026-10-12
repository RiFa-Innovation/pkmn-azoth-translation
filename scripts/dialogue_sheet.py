"""Export the conversations (not signs, names or menus) as a review sheet.

    python3 scripts/dialogue_sheet.py docs/dialogue-review.csv [--map 43.6] [--match TEXT]

One row per unique Chinese line that the game's scripts print to a text box
(NPC speech, trainer lines, story). Columns:

  id       ROM address of the first reference (find it in game, or import)
  map      map the script belongs to, as group.number (best effort, see below)
  place    human name for that map, from data/map_names.json (extend it!)
  before   the previous line of the same conversation sheet, for context
  zh       Chinese source (the translation memory is keyed by this text)
  en       current English
  limit    what the line must fit: box width in px and line cap. Bytes only
           matter for the few lines something also reads at their original
           address ("ALSO READ IN PLACE"); the rest are relocated ("free")
  now      what the current English uses of that (lines, widest line, bytes)
  new_en   fill this in to propose a change (leave empty to keep `en`)

`\\n` stands for a line break in every text column. The sheet imports with
`python3 scripts/review.py import FILE`, which validates control codes.

The map is the one whose event scripts (object / coordinate / sign scripts,
level scripts) start closest before the line's reference: good enough to put
a conversation next to the right town, not a guarantee.
"""
import argparse
import csv
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))

ROM = "roms/Pokemon Mercury 1.3.3 (patched).gba"
GMAPGROUPS = 0xB3B100          # moved by the hack (see insert.py)
HANZI = re.compile("[一-鿿]")
SCRIPT_KINDS = {"loadpointer", "message", "trainerbattle"}
WINDOW = 0x2000                # a script's text lives within this of its entry


def _esc(s):
    return s.replace("\n", "\\n")


def _budget(addr, e, en, widths, dialogue_addrs, table_px, width_override, ins, mt):
    """(limit, now) strings, mirroring insert.py's per-string decision."""
    t = int(addr, 16)
    zh = e["zh"]
    dialogue = t in dialogue_addrs
    single = not dialogue and not re.search(r"\n|\{FA\}|\{FB\}", zh)
    max_px = ins.DIALOGUE_PX if dialogue else max(ins.src_max_px(zh, widths), table_px.get(t, 0), 48)
    max_lines = None
    wo = width_override.get(f"{t:07X}")
    if wo:
        max_px, dialogue, single = wo["px"], wo.get("dialogue", dialogue), False
        max_lines = wo.get("lines")
    try:
        text = en if single else mt.wrap_en(en, widths, max_px, dialogue)
        n_bytes = len(mt.encode_en(text))
    except ValueError:
        return "", "unencodable"
    lines = re.split(r"\n|\{FA\}|\{FB\}", text)
    px = lambda ln: sum(widths[b[0]] for b, k in mt.tokenize(ln) if k in ("char", "space"))
    widest = max(px(ln) for ln in lines)
    n_lines = text.count("\n") + 1
    if max_lines:
        cap_lines = f"max {max_lines} lines"
    elif dialogue:
        cap_lines = "scrolls (2-line box)"
    else:
        cap_lines = f"max {zh.count(chr(10)) + 1} lines"
    fixed = e["untrusted"] > 0
    where = (f"ALSO READ IN PLACE: keep to {e['cap'] - 1} bytes or those uses stay Chinese"
             if fixed else "free (relocated)")
    return (f"{max_px}px wide; {cap_lines}; {where}",
            f"{n_lines} lines; widest {widest}px; {n_bytes - 1} bytes")


def map_entries(rom):
    """sorted [(script address, 'group.num')] from every map's events."""
    u32 = lambda o: struct.unpack_from("<I", rom, o)[0]
    ptr = lambda o: (u32(o) - 0x08000000) if 0x08000000 <= u32(o) < 0x0A000000 else None
    out = []
    g = 0
    while g < 80 and (gp := ptr(GMAPGROUPS + 4 * g)) is not None:
        m = 0
        while m < 500 and (mp := ptr(gp + 4 * m)) is not None:
            tag = f"{g}.{m}"
            ev = ptr(mp + 4)
            if ev and ev + 20 <= len(rom):
                n_obj, n_warp, n_co, n_bg = rom[ev], rom[ev + 1], rom[ev + 2], rom[ev + 3]
                op, cp, bp = ptr(ev + 4), ptr(ev + 12), ptr(ev + 16)
                for i in range(n_obj if op and n_obj <= 64 else 0):
                    s = ptr(op + 24 * i + 16)
                    if s:
                        out.append((s, tag))
                for i in range(n_co if cp and n_co <= 64 else 0):
                    s = ptr(cp + 16 * i + 12)
                    if s:
                        out.append((s, tag))
                for i in range(n_bg if bp and n_bg <= 64 else 0):
                    s = ptr(bp + 12 * i + 8)
                    if s and rom[bp + 12 * i + 5] == 0:     # kind 0 = script
                        out.append((s, tag))
            ls = ptr(mp + 8)
            if ls:
                k = 0
                while k < 8 and rom[ls + 5 * k]:
                    s = ptr(ls + 5 * k + 1)
                    if s and rom[ls + 5 * k] in (1, 3, 5, 7):
                        out.append((s, tag))
                    k += 1
            m += 1
        g += 1
    return sorted(set(out))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out")
    ap.add_argument("--map", help="only this map, e.g. 43.6")
    ap.add_argument("--match", help="only lines containing this text (zh or en)")
    a = ap.parse_args()

    rom = open(ROM, "rb").read()
    zh = json.load(open("text/zh.json", encoding="utf-8"))["strings"]
    hand = json.load(open("text/en/strings.json", encoding="utf-8"))
    vanilla = json.load(open("text/en/strings-vanilla.json", encoding="utf-8"))
    names = {}
    if os.path.exists("data/map_names.json"):
        names = {k: v for k, v in json.load(open("data/map_names.json", encoding="utf-8")).items()
                 if not k.startswith("_")}
    entries = map_entries(rom)
    starts = [s for s, _ in entries]

    import bisect
    import insert as ins
    import layout
    import mercury_text as mt
    widths = rom[mt.WIDTHS_OFF:mt.WIDTHS_OFF + 256]
    zs = {int(k, 16): v for k, v in zh.items()}
    dialogue_addrs = layout.dialogue_set(zs)
    table_px = layout.table_widths(zs)
    wo_all = {k: v for k, v in json.load(open("text/en/width_override.json", encoding="utf-8")).items()
              if not k.startswith("_")}

    def map_of(r):
        i = bisect.bisect_right(starts, r) - 1
        if i >= 0 and r - starts[i] < WINDOW:
            return entries[i][1]
        return "?"

    rows, seen = [], set()
    for addr in sorted(zh, key=lambda x: int(x, 16)):
        e = zh[addr]
        text = e["zh"]
        if e.get("suspect") or text in seen:
            continue
        refs = [r.split(":") for r in e["refs"]]
        script_refs = [int(r, 16) for r, k in refs if k in SCRIPT_KINDS]
        if not script_refs:
            continue                                # table text: names, menus, signs
        n_hanzi = len(HANZI.findall(re.sub(r"\{[^}]*\}", "", text)))
        if n_hanzi < 6 and "{FB}" not in text:
            continue                                # short labels and one-word replies
        en = hand.get(text) or vanilla.get(text)
        if not en:
            continue
        seen.add(text)
        m = map_of(min(script_refs))
        rows.append((m, int(addr, 16), addr, text, en, _budget(addr, e, en, widths, dialogue_addrs,
                                                              table_px, wo_all, ins, mt)))

    rows.sort(key=lambda r: (r[0] == "?", [int(x) for x in r[0].split(".")] if r[0] != "?" else [], r[1]))
    n = 0
    prev_en, prev_map = "", None
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "map", "place", "before", "zh", "en", "limit", "now", "new_en"])
        for m, _, addr, text, en, (limit, now) in rows:
            if a.map and m != a.map:
                continue
            if a.match and a.match.lower() not in (en + text).lower():
                continue
            before = "" if m != prev_map else prev_en
            w.writerow([addr, m, names.get(m, ""), _esc(before)[:140], _esc(text), _esc(en),
                        limit, now, ""])
            prev_en, prev_map = en, m
            n += 1
    print(f"{n} conversation lines -> {a.out}")


if __name__ == "__main__":
    main()
