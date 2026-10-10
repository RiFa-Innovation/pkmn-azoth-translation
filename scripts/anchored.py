"""Text the hack's code reaches only through section anchors (base + imm).

No pointer to these strings exists, so they cannot be relocated: the English
must fit in the original bytes (cap, FF included) and is written in place.
The exact string starts come from the code map (data/hack_code.json: every
`imm` anchor literal and the constants its users add).

    python3 scripts/anchored.py dump            # -> text/zh_anchored.json
    python3 scripts/anchored.py check FILE      # validate {addr: english}
    python3 scripts/anchored.py export DIR N    # untranslated -> N chunk files
    python3 scripts/anchored.py stats

Translations live in text/en/anchored.json {addr: english}. insert.py wraps
them (dialogue boxes when the Chinese has {FB}/{FA} or 3+ lines) and writes
them in place; wrapping only swaps spaces for \\n/{FA}, so it adds no bytes.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import mercury_text as mt  # noqa: E402
import dump_all  # noqa: E402

ROM = dump_all.ROM
ZH = "text/zh_anchored.json"
EN = "text/en/anchored.json"
DIALOGUE_PX, MENU_PX = 198, 198
HANZI = re.compile("[\u4e00-\u9fff]")
# custom formatting bytes that decode as these hanzi: such strings start with
# printer codes we must not touch, so they are left alone
JUNK_PREFIX = re.compile("^[ 埃镶赫幅嗜拂鞍]{4,}")


def build():
    import hackmap
    rom = open(ROM, "rb").read()
    hm = hackmap.HackMap()
    handled = set()
    for f in ("text/en/manual_strings.json",):
        handled |= {int(k, 16) for k in json.load(open(f)) if not k.startswith("_")}
    for blk in json.load(open("text/en/code_text.json")).values():
        if isinstance(blk, dict):
            handled |= {int(s["zh_at"], 16) for s in blk["strings"]}
    out = {}
    for lit, L in hm.literals.items():
        if L["anchor"] != "imm":
            continue
        base = L["value"] - 0x08000000
        for o in L["offs"]:
            t = base + o
            if not (0 < t < len(rom)) or rom[t - 1] not in (0xFF, 0x00) or t in handled:
                continue
            s, e = mt.decode(rom, t, 1024)
            if rom[e - 1] != 0xFF or re.search(r"\{[0-9A-F]{4}\}", s):
                continue
            if not (dump_all.is_textlike(s) or dump_all.is_single(s)) or JUNK_PREFIX.search(s):
                continue
            k = f"{t:07X}"
            out.setdefault(k, {"zh": s, "cap": e - t, "anchors": []})["anchors"].append([f"{lit:07X}", o])
    json.dump(dict(sorted(out.items())), open(ZH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(out), "anchored strings ->", ZH)


_HM = None


def relocatable(entry):
    """Every anchor reaching the string is a literal with exactly one use and
    one offset: repointing it to (new address - offset) moves only this text."""
    global _HM
    if _HM is None:
        import hackmap
        _HM = hackmap.HackMap()
    for lit, off in entry["anchors"]:
        L = _HM.literal(int(lit, 16))
        if not L or L["offs"] != [off] or len(L["uses"]) != 1:
            return False
    return True


def is_dialogue(zh):
    return "{FB}" in zh or "{FA}" in zh or zh.count("\n") >= 2


def layout(zh, en, widths):
    """Wrap like insert.py and return the bytes to write."""
    single = not is_dialogue(zh) and "\n" not in zh
    text = en if single else mt.wrap_en(en, widths, DIALOGUE_PX if is_dialogue(zh) else MENU_PX, is_dialogue(zh))
    return mt.encode_en(text)


def problems(zh, cap, en, widths, reloc=False):
    out = []
    try:
        b = layout(zh, en, widths)
    except ValueError as e:
        return [f"unencodable: {e}"]
    if len(b) > cap and not reloc:
        out.append(f"too long: {len(b)} bytes > budget {cap} (cut {len(b) - cap})")
    tok = lambda s: sorted(t for t in re.findall(r"\{[^}]*\}", s) if t not in ("{FA}", "{FB}"))
    if tok(zh) != tok(en):
        out.append(f"control tokens differ: {tok(zh)} vs {tok(en)}")
    if is_dialogue(zh) and en.count("{FB}") > zh.count("{FB}"):
        out.append("more {FB} boxes than the Chinese")
    return out


def main():
    cmd = sys.argv[1]
    if cmd == "dump":
        build()
        return
    zh = json.load(open(ZH, encoding="utf-8"))
    en = json.load(open(EN, encoding="utf-8")) if os.path.exists(EN) else {}
    widths = open(ROM, "rb").read()[mt.WIDTHS_OFF:mt.WIDTHS_OFF + 256]
    if cmd == "stats":
        print(f"{sum(k in en for k in zh)}/{len(zh)} anchored strings translated")
    elif cmd == "check":
        new = json.load(open(sys.argv[2], encoding="utf-8"))
        n = 0
        for k, v in new.items():
            if k not in zh:
                print("WARN", k, "not an anchored string")
                continue
            for p in ([] if v is None else problems(zh[k]["zh"], zh[k]["cap"], v, widths, relocatable(zh[k]))):
                print("WARN", k, p)
                n += 1
        print(f"checked {len(new)}: {n} warnings")
    elif cmd == "add":
        new = json.load(open(sys.argv[2], encoding="utf-8"))
        bad = [k for k, v in new.items()
               if k not in zh or (v is not None and problems(zh[k]["zh"], zh[k]["cap"], v, widths, relocatable(zh[k])))]
        en.update({k: v for k, v in new.items() if k not in bad})
        json.dump(dict(sorted(en.items())), open(EN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"added {len(new) - len(bad)}, rejected {len(bad)}: {bad}")
    elif cmd == "export":
        d, n = sys.argv[2], int(sys.argv[3])
        os.makedirs(d, exist_ok=True)
        todo = [{"id": k, "zh": v["zh"], "budget_bytes": None if relocatable(v) else v["cap"] - 1}
                for k, v in zh.items() if k not in en]
        for i in range(n):
            json.dump(todo[i::n], open(f"{d}/a{i}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(len(todo), "->", n, "chunks in", d)


if __name__ == "__main__":
    main()
