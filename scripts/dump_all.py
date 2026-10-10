"""Dump every Chinese string in the patched Mercury ROM to text/zh.json.

Two kinds of text:
- tables:  fixed-stride name tables (no per-entry pointers), written in place.
- strings: 0xFF-terminated text found via pointer scan. Only pointers with a
  recognisable context are kept ("trusted"), so the inserter never repoints a
  random data word that happens to look like a pointer.

Requires numpy. Usage: python3 scripts/dump_all.py
"""
import json
import os
import re
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import mercury_text as mt  # noqa: E402

ROM = "roms/Pokemon Mercury 1.3.3 (patched).gba"
OUT = "text/zh.json"

# name, file offset, stride, field size, count  (counts from plausibility scan)
TABLES = [
    ("species", 0x141B350, 11, 11, 1292),
    ("moves", 0x1D97378, 13, 13, 1000),
    ("abilities", 0x1D8E858, 13, 13, 302),
    ("items", 0x3DB028, 44, 14, 378),
    ("types", 0x1DBBA70, 7, 7, 19),
    ("types_old", 0x24F1A0, 7, 7, 18),
    ("trainer_classes", 0x23E558, 13, 13, 107),
    ("trainer_names", 0x23EAC8 + 4, 40, 12, 813),
    ("dex_categories", 0x17D98F0, 36, 12, 1029),
]

HANZI = re.compile(r"[一-鿿]")
OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 \n"
         ".,!?-'\"/:…♂♀é‘’“”%()&+=~·×") | set(mt.PUNCT.values())


def is_textlike(s, min_ratio=0.3):
    s2 = re.sub(r"\{[^}]*\}", "", s)
    if not s2 or any(not (HANZI.match(c) or c in OK) for c in s2):
        return False
    hz = len(HANZI.findall(s2))
    return hz >= 2 and hz / len(s2) >= min_ratio


def is_ptr(rom, o):
    return 0 <= o <= len(rom) - 4 and rom[o + 3] in (0x08, 0x09)


def ref_kind(rom, r):
    """Classify a pointer occurrence; None = untrusted."""
    if r % 4 == 0:
        if is_ptr(rom, r - 4) or is_ptr(rom, r + 4) or r < 0x250000:
            return "aligned"
        return None
    if rom[r - 2:r] == b"\x0f\x00":
        return "loadpointer"
    if rom[r - 1] == 0x67:
        return "message"
    for back in (6, 10, 14):  # trainerbattle type,id,local,ptr,ptr,ptr
        if r - back >= 0 and rom[r - back] == 0x5C:
            return "trainerbattle"
    return None


def scan_strings(rom):
    a = np.frombuffer(rom, np.uint8)
    n = len(a) - 3
    u = (a[:n].astype(np.uint32) | (a[1:n + 1].astype(np.uint32) << 8)
         | (a[2:n + 2].astype(np.uint32) << 16) | (a[3:n + 3].astype(np.uint32) << 24))
    offs = np.nonzero(((u >> 24) == 8) | ((u >> 24) == 9))[0]
    refs = defaultdict(list)
    for o, t in zip(offs.tolist(), (u[offs] - 0x08000000).tolist()):
        refs[t].append(o)
    out = {}
    for t, rs in refs.items():
        if t >= len(rom) or rom[t] == 0xFF:
            continue
        s, e = mt.decode(rom, t, 1000)
        if e - t >= 1000 or rom[e - 1] != 0xFF or re.search(r"\{[0-9A-F]{2,4}\}", s):
            continue
        if not is_textlike(s):
            continue
        trusted = [(r, k) for r in rs if (k := ref_kind(rom, r))]
        if not trusted:
            continue
        out[t] = {"zh": s, "cap": e - t,
                  "refs": ["%07X:%s" % (r, k) for r, k in trusted],
                  "untrusted": len(rs) - len(trusted)}
    return out


def main():
    rom = open(ROM, "rb").read()
    tables = {}
    for name, base, stride, size, count in TABLES:
        ents = {}
        for i in range(count):
            s = mt.decode_fixed(rom, base + i * stride, size)
            if HANZI.search(s):
                ents[str(i)] = s
        tables[name] = {"base": "%07X" % base, "stride": stride, "size": size,
                        "entries": ents}
        print(f"{name}: {len(ents)} entries")
    strings = scan_strings(rom)
    print(f"strings: {len(strings)}")
    os.makedirs("text", exist_ok=True)
    json.dump({"tables": tables,
               "strings": {"%07X" % t: v for t, v in sorted(strings.items())}},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
