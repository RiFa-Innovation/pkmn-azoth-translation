"""Recover official Fire Red English for strings the hack translated from FR.

For each dumped string, the vanilla ROM's pointer at the same reference
location usually still leads to the original English line. Accepted only if
it decodes cleanly, has the same control tokens, and a plausible length ratio.
Writes text/en/strings-vanilla.json ({chinese: english}); hand translations
in text/en/strings.json override it.
"""
import json
import os
import re
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import mercury_text as mt  # noqa: E402

BASE = "roms/Pokemon - FireRed Version (USA, Europe).gba"
HANZI = re.compile(r"[一-鿿]")


ACRONYMS = {"HP", "PP", "TM", "HM", "PC", "OK", "TV", "KO", "VS", "S.S.", "SS",
            "EXP.", "EXP", "ID", "NO.", "PKMN", "LV", "UFO", "DJ", "OT", "HQ", "I",
            "A", "B", "L", "R", "TMS", "HMS", "IV", "EV", "GTS", "HP.", "PP."}


def _cap(word):
    core = word.strip(".,!?…’'\"()-:;")
    if core.upper() in ACRONYMS or not re.search(r"[A-Z]{2}", core):
        return word
    w = word.lower()
    w = re.sub(r"(^|[\s\-/(“\"])([a-zé])", lambda m: m.group(1) + m.group(2).upper(), w)
    return w.replace("poké", "Poké").replace("Poké ball", "Poké Ball")


def modernize(s):
    """Gen-3 ALL-CAPS proper nouns -> modern casing, outside {..} tokens."""
    parts = re.split(r"(\{[^}]*\})", s)
    for i, part in enumerate(parts):
        if part.startswith("{"):
            continue
        part = re.sub(r"[A-Z0-9][A-Zé0-9’'.\-]*[A-Zé]\b[’']?s?|POKé[A-Zé]*", lambda m: _cap(m.group(0)), part)
        part = part.replace("Pokémon", "Pokémon")
        parts[i] = part
    return "".join(parts)


def tokens(s):
    return sorted(t for t in re.findall(r"\{F[7-9CD][^}]*\}", s))


def main():
    base = open(BASE, "rb").read()
    d = json.load(open("text/zh.json", encoding="utf-8"))["strings"]
    cands = defaultdict(Counter)
    for v in d.values():
        if v.get("suspect"):
            continue
        for r in v["refs"]:
            ro = int(r.split(":")[0], 16)
            if ro + 4 > len(base):
                continue
            p = struct.unpack_from("<I", base, ro)[0] - 0x08000000
            if not 0 <= p < len(base):
                continue
            s, e = mt.decode_vanilla(base, p)
            if e - p >= 1000 or base[e - 1] != 0xFF or re.search(r"\{[0-9A-F]{2}\}", s):
                continue
            letters = len(re.findall(r"[A-Za-z]", s))
            hz = len(HANZI.findall(v["zh"]))
            if letters < 2 or not (0.8 <= letters / max(hz, 1) <= 8):
                continue
            if tokens(s) != tokens(v["zh"]):
                continue
            try:
                mt.encode_en(s)
            except ValueError:
                continue
            cands[v["zh"]][s] += 1
    out = {zh: modernize(c.most_common(1)[0][0]) for zh, c in cands.items()}
    json.dump(out, open("text/en/strings-vanilla.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print(f"recovered official English for {len(out)} strings")


if __name__ == "__main__":
    main()
