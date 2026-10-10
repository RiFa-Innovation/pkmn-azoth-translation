"""Find Chinese text still reachable in the built English ROM.

Scans every 4-aligned word *and* every unaligned word in the ROM for values that
look like ROM pointers (0x08000000-0x09FFFFFF), and reports targets that start a
string (preceded by 0xFF or 0x00), decode cleanly, and contain >= MIN_HANZI hanzi.

    python3 scripts/find_leftover_zh.py [build/Mercury_EN.gba] [-o build/leftover_zh.json]

Output groups hits by how the pointer was found (aligned / unaligned) and marks
whether the target address is already in text/zh.json.
"""
import json
import struct
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import mercury_text as mt  # noqa: E402

MIN_HANZI = 2
VOCAB_FRAC = 0.9
ROM_BASE = 0x08000000


def is_hanzi(c):
    return "一" <= c <= "鿿"


def clean(text):
    """Reject decodes that hit unmapped codes (rendered as {XXXX}) or kana noise."""
    if "{" in text.replace("{FA}", "").replace("{FB}", "").replace("{FD:", "").replace("{FC:", ""):
        # unknown 2-byte codes look like {0D61}; control tokens are fine
        import re
        if re.search(r"\{[0-9A-F]{4}\}", text):
            return False
    if any("぀" <= c <= "ヿ" for c in text):
        return False
    return True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    path = args[0] if args else "build/Mercury_EN.gba"
    out = "build/leftover_zh.json"
    if "-o" in sys.argv:
        out = sys.argv[sys.argv.index("-o") + 1]
    rom = open(path, "rb").read()
    zh = json.load(open("text/zh.json"))["strings"]
    dumped = set(zh)
    # vocabulary of real text: hanzi seen in the dump. Random binary decodes to
    # hanzi spread uniformly over all 6,763 GB2312 cells; real text doesn't.
    vocab = {c for v in zh.values() for c in v["zh"] if is_hanzi(c)}

    refs = defaultdict(list)
    n = len(rom)
    for i in range(0, n - 3):
        v = struct.unpack_from("<I", rom, i)[0]
        if not (ROM_BASE <= v < ROM_BASE + n):
            continue
        t = v - ROM_BASE
        if t == 0 or rom[t - 1] not in (0xFF, 0x00):
            continue
        refs[t].append(i)

    hits = {}
    for t, srcs in refs.items():
        try:
            text, end = mt.decode(rom, t, limit=2048)
        except Exception:
            continue
        hz = [c for c in text if is_hanzi(c)]
        if end - t > 2048 or len(hz) < MIN_HANZI or not clean(text):
            continue
        if sum(c in vocab for c in hz) < VOCAB_FRAC * len(hz):
            continue
        hits[f"{t:07X}"] = {
            "zh": text,
            "refs": [f"{s:07X}:{'aligned' if s % 4 == 0 else 'unaligned'}" for s in srcs[:8]],
            "in_dump": f"{t:07X}" in dumped,
        }

    json.dump(hits, open(out, "w"), ensure_ascii=False, indent=1)
    aligned = sum(any(r.endswith("aligned") and not r.endswith("unaligned") for r in h["refs"]) for h in hits.values())
    hz = sum(sum(map(is_hanzi, h["zh"])) for h in hits.values())
    print(f"{len(hits)} Chinese strings still pointed to ({aligned} via an aligned pointer), "
          f"{hz} hanzi; {sum(h['in_dump'] for h in hits.values())} of them are in zh.json -> {out}")


if __name__ == "__main__":
    main()
