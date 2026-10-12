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
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import mercury_text as mt  # noqa: E402

ROM = "roms/Pokemon Mercury 1.3.3 (patched).gba"
BASE = "roms/Pokemon - FireRed Version (USA, Europe).gba"
OUT = "text/zh.json"

# name, file offset, stride, field size, count  (counts from plausibility scan)
TABLES = [
    ("species", 0x141B350, 11, 11, 1292),
    ("moves", 0x1D97378, 13, 13, 1000),
    ("abilities", 0x1D8E858, 13, 13, 302),
    ("items", 0x3DB028, 44, 14, 378),  # old copy; the game reads items2
    ("items2", 0x7C7E00, 44, 14, 750),
    ("types", 0x1DBBA70, 7, 7, 19),
    ("types_old", 0x24F1A0, 7, 7, 18),
    ("trainer_classes", 0x23E558, 13, 13, 107),
    ("trainer_names", 0x23EAC8 + 4, 40, 12, 813),
    ("dex_categories", 0x17D98F0, 36, 12, 1029),
]

HANZI = re.compile(r"[一-鿿]")
MAX_LEN = 4096  # the intro disclaimer is one 1,856-byte string
OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 \n"
         ".,!?-'\"/:…♂♀é‘’“”%()&+=~·×<>¥↑↓←→") | set(mt.PUNCT.values())


ARROWS = set("↑↓←→")


def is_textlike(s, min_ratio=0.3):
    s2 = re.sub(r"\{[^}]*\}", "", s)
    if not s2 or any(not (HANZI.match(c) or c in OK) for c in s2):
        return False
    hz = len(HANZI.findall(s2))
    return hz >= 2 and hz / len(s2) >= min_ratio


def is_single(s):
    """A one-hanzi option label such as 开 / 关 / 中 (is_textlike needs 2)."""
    s2 = re.sub(r"\{[^}]*\}", "", s)
    return len(HANZI.findall(s2)) == 1 and len(s2) <= 2 and all(HANZI.match(c) or c in OK for c in s2)


def short_line(s):
    """One hanzi plus punctuation/placeholders, e.g. 喂，{FD:01}！ (is_textlike
    needs 2 hanzi, is_single allows no punctuation)."""
    s2 = re.sub(r"\{[^}]*\}", "", s)
    return (len(HANZI.findall(s2)) == 1 and len(s2) <= 6
            and all(HANZI.match(c) or c in "，。！？…!?. " for c in s2))


def is_ptr(rom, o):
    return 0 <= o <= len(rom) - 4 and rom[o + 3] in (0x08, 0x09)


_HM = None
_FM = None


def _FR():
    global _FM
    if _FM is None:
        import frmap
        _FM = frmap.FRMap()
    return _FM


def vanilla_text_symbol(t):
    """Target is the start of a text symbol in vanilla FireRed (decomp map)."""
    global _FM
    if _FM is None:
        import frmap
        _FM = frmap.FRMap()
    sym = _FM.symbol(t)
    reg = _FM.region(t)
    return bool(sym and sym[1] == t and reg and (reg[4] == "src/strings.o" or re.search(r"Text|String", sym[0])))


def hack_map():
    """Code map of the whole ROM (vanilla + hack), see hackmap.py."""
    global _HM
    if _HM is None:
        import hackmap
        _HM = hackmap.HackMap()
    return _HM


_LZ = None


def lz77_blobs(rom):
    """[start, end) of every valid GBA LZ77 stream a ROM pointer points at.
    Compressed graphics are full of byte runs that look like a pointer or a
    0x67 `message` opcode; repointing one corrupts the tiles (Goldenrod, the
    Olivine lighthouse tileset). Streams are accepted only if they decode to
    exactly their declared size with every back-reference in range."""
    global _LZ
    if _LZ is not None and _LZ[0] is rom:
        return _LZ[1]
    L = len(rom)
    w = np.frombuffer(rom[:L // 4 * 4], "<u4")
    tg = np.unique(w[(w >= 0x08000000) & (w < 0x0A000000)].astype(np.int64) - 0x08000000)
    out = []
    for t in tg.tolist():
        if t >= L - 8 or rom[t] != 0x10:
            continue
        size = rom[t + 1] | rom[t + 2] << 8 | rom[t + 3] << 16
        if not 0x20 <= size <= 0x30000:
            continue
        i, n, ok = t + 4, 0, True
        while n < size and ok:
            if i >= L:
                ok = False
                break
            fl = rom[i]
            i += 1
            for k in range(8):
                if n >= size:
                    break
                if fl & (0x80 >> k):
                    if i + 1 >= L:
                        ok = False
                        break
                    b0, b1 = rom[i], rom[i + 1]
                    i += 2
                    n += (b0 >> 4) + 3
                    if ((b0 & 15) << 8 | b1) + 1 > n - ((b0 >> 4) + 3) or n > size:
                        ok = False
                        break
                else:
                    if i >= L:
                        ok = False
                        break
                    i += 1
                    n += 1
        if ok and n == size:
            out.append((t, i))
    starts = [a for a, _ in out]
    _LZ = (rom, (starts, out))
    return _LZ[1]


def in_lz77(rom, r):
    import bisect
    starts, blobs = lz77_blobs(rom)
    i = bisect.bisect_right(starts, r) - 1
    return i >= 0 and blobs[i][0] <= r < blobs[i][1]


def ref_kind(rom, r, text=""):
    """Classify a pointer occurrence; None = untrusted."""
    hm = hack_map()
    if hm.is_code(r):            # instruction bytes that merely look like a pointer
        return None
    if r < 0x200:                # sGFRomHeader: pointers to data tables (gDecorations
        return None              # starts with a name field), never to strings
    if in_lz77(rom, r):          # bytes inside compressed graphics only look like a pointer
        return None
    lit = hm.literal(r)
    if lit is not None:          # a literal-pool word some code loads
        if lit["anchor"] == "imm":
            # code adds a constant (GCC section anchor / struct field): it is a
            # base address, not a pointer to the bytes there
            return None
        if lit["anchor"] == "reg" and not vanilla_text_symbol(lit["value"] - 0x08000000):
            return None          # indexed array/struct base, not a string
        return "literal"
    if r % 4 == 0 and (is_ptr(rom, r - 4) or is_ptr(rom, r + 4) or r < 0x250000):
        return "aligned"
    # a vanilla data word aimed at the start of a vanilla text symbol (the decomp
    # says it is a text pointer even without pointer neighbours, e.g. the
    # {gText_Yes, NULL} entries of sMultichoiceList_YesNo)
    if (r % 4 == 0 and _FR().kind(r) == "data"
            and vanilla_text_symbol(int.from_bytes(rom[r:r + 4], "little") - 0x08000000)):
        return "aligned"
    if rom[r - 2:r] == b"\x0f\x00":  # loadpointer, aligned or not
        return "loadpointer"
    if rom[r - 1] == 0x67:
        return "message"
    # battle script: setword gBattleStringLoader (0x0203E020), ptr; printstring
    if rom[r - 4:r] == b"\x20\xe0\x03\x02":
        return "battlestr"
    # item struct (44 B) description field at +0x14 (old table, live table)
    for base, n in ((0x3DB028, 378), (0x7C7E00, 750)):
        if base <= r < base + 44 * n and (r - base) % 44 == 0x14:
            return "aligned"
    for back in (6, 10, 14):  # trainerbattle type,id,local,ptr,ptr,ptr
        if r - back >= 0 and rom[r - back] == 0x5C:
            return "trainerbattle"
    # lone aligned word (struct field, Thumb literal pool): only for text that
    # is unmistakably prose, so a stray data word is never repointed
    if r % 4 == 0 and is_prose(text):
        # `applymovement local, ptr` / `applymovementat local, ptr, ...`: the
        # pointer leads to movement bytes (00 fe = face down; 0f x8 fe = walk),
        # which decode as hanzi and sit right before the NPC's text. Repointing
        # it hands text bytes to the movement engine ("jumped to invalid
        # address", the Beautifly/Wurmple scene).
        if r >= 3 and rom[r - 3] in (0x4F, 0x50) and not hm.near_code(r):
            return None
        return "literal"
    return None


SCRIPT_KINDS = ("loadpointer", "message", "trainerbattle")


def is_script_ref(r):
    return r.split(":")[1] in SCRIPT_KINDS


def is_prose(s):
    if not is_textlike(s, 0.5):
        return False
    body = re.sub(r"\{[^}]*\}", "", s)
    return (len(HANZI.findall(body)) >= 4
            and (body.rstrip()[-1:] in set("。！？…」）!?.") or "\n" in body))


def scan_strings(rom, base):
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
        s, e = mt.decode(rom, t, MAX_LEN)
        # {XXXX} = undecodable 2-byte code (binary). Not {FA}/{FB}: those are
        # the scroll / new-box controls every multi-box dialogue contains.
        if e - t >= MAX_LEN or rom[e - 1] != 0xFF or re.search(r"\{[0-9A-F]{4}\}", s):
            continue
        # long texts (intro disclaimer, credits) may be mostly Latin/punctuation
        single = is_single(s)
        short = short_line(s)
        if not (single or short or is_textlike(s) or (len(HANZI.findall(s)) >= 30 and is_textlike(s, 0.1))):
            continue
        if hack_map().is_code(t):  # Thumb code decoded as text (a function pointer)
            continue
        trusted = [(r, k) for r in rs if (k := ref_kind(rom, r, s))]
        if ARROWS & set(s):  # arrow glyphs (signs): only from script refs, data decodes to them too
            trusted = [(r, k) for r, k in trusted if k in SCRIPT_KINDS]
        if short and not (single or is_textlike(s)):  # 喂，{FD:01}！: script text only
            trusted = [(r, k) for r, k in trusted if k in SCRIPT_KINDS]
        if single:  # one-hanzi labels (开/关/中…): only from inside a pointer table,
            # or a vanilla data word aimed at a vanilla text symbol (the decomp
            # says so: e.g. sMultichoiceList_YesNo {gText_Yes, NULL} entries)
            trusted = [(r, k) for r, k in trusted
                       if r % 4 == 0 and (is_ptr(rom, r - 4) or is_ptr(rom, r + 4)
                                          or (_FR().kind(r) == "data" and vanilla_text_symbol(t)))]
        # A word left exactly as in vanilla FR cannot point at text the hack put
        # into space that was free (FF) in vanilla: it is code/data that merely
        # looks like a pointer (e.g. Thumb code at 0x1E4074 -> crash if repointed).
        if t + (e - t) <= len(base) and set(base[t:e]) == {0xFF}:
            trusted = [(r, k) for r, k in trusted
                       if not (r + 4 <= len(base) and base[r:r + 4] == rom[r:r + 4])]
        if not trusted:
            continue
        out[t] = {"zh": s, "cap": e - t,
                  "refs": ["%07X:%s" % (r, k) for r, k in trusted],
                  "untrusted": len(rs) - len(trusted)}
    return out


DATA_CHARS = set("块曹肤貉缕疆寝倒厕祷挨赫稻嫌迢驶噪")


def prune_inner_refs(strings):
    """A 'pointer' lying inside the bytes of script text is four text bytes
    that merely look like one (e.g. 0E 9E 08 in 红色的火球 at 0xABEAE0). Writing
    a repointed address there corrupts whatever the pool later puts in that
    recycled space. Drop such refs, then strings left with none."""
    import bisect
    real = [(t, t + v["cap"]) for t, v in strings.items()
            if any(is_script_ref(r) for r in v["refs"])]
    real.sort()
    starts = [a for a, _ in real]
    dropped = 0
    for t in list(strings):
        v = strings[t]
        keep = []
        for ref in v["refs"]:
            r = int(ref.split(":")[0], 16)
            i = bisect.bisect_right(starts, r + 3) - 1
            inside = any(a < r + 4 and r < b and a != t
                         for a, b in real[max(0, i - 4):i + 1])
            if inside:
                dropped += 1
            else:
                keep.append(ref)
        v["refs"] = keep
        if not keep:
            del strings[t]
    print(f"pruned {dropped} refs inside script text")


def mark_suspects(strings):
    """Flag aligned/literal-only strings that look like binary data decoded as text.
    Character frequencies come from strings with script-command refs (certainly
    real). Strings referenced from a pointer-table run are trusted more."""
    real = [v["zh"] for v in strings.values()
            if any(is_script_ref(r) for r in v["refs"])]
    freq = Counter(c for s in real for c in s if HANZI.match(c))
    ref_at = {}
    for t, v in strings.items():
        for r in v["refs"]:
            ref_at[int(r.split(":")[0], 16)] = t
    starts = sorted(strings)
    interior = set()  # starts strictly inside another string's bytes
    for i, a in enumerate(starts):
        for b in starts[i + 1:]:
            if b >= a + strings[a]["cap"]:
                break
            interior.add(b)
    for t, v in strings.items():
        if any(is_script_ref(r) for r in v["refs"]):
            v["suspect"] = False
            continue
        s = v["zh"]
        hz = HANZI.findall(s)
        rare = sum(1 for c in hz if freq[c] < 2) / len(hz)
        in_table = any(int(r.split(":")[0], 16) - 4 in ref_at
                       and int(r.split(":")[0], 16) + 4 in ref_at for r in v["refs"])
        v["suspect"] = (t in interior or s.startswith("♂") or "缕曹" in s
                        or sum(1 for c in hz if c in DATA_CHARS) >= 2
                        or (not in_table and (rare > 0.34 or (len(hz) <= 4 and rare > 0))))


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
    strings = scan_strings(rom, open(BASE, "rb").read())
    prune_inner_refs(strings)
    mark_suspects(strings)
    print(f"strings: {len(strings)} ({sum(v['suspect'] for v in strings.values())} suspect)")
    os.makedirs("text", exist_ok=True)
    json.dump({"tables": tables,
               "strings": {"%07X" % t: v for t, v in sorted(strings.items())}},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
