"""Window-width estimates for non-dialogue strings.

Strings referenced from the same pointer table share a window, so a table's
width budget is the widest line among its multi-line members (Chinese lines
are often broken by sentence, not by the window edge).
"""
import re

HANZI_PX, LATIN_PX = 12, 6
# "literal" (lone aligned word: struct field / literal pool) is not a script ref
SCRIPT_KINDS = ("loadpointer", "message", "trainerbattle")


def line_px(zh_line):
    zh_line = re.sub(r"\{[^}]*\}", "", zh_line)
    return sum(HANZI_PX if ord(c) >= 0x3000 else LATIN_PX for c in zh_line)


def src_px(zh):
    return max(line_px(ln) for ln in re.split(r"\n|\{FA\}|\{FB\}", zh))


def table_widths(strings, gap=16):
    """strings: {addr:int -> entry}. Returns {addr: px budget}."""
    refs = sorted((int(r.split(":")[0], 16), t) for t, v in strings.items()
                  for r in v["refs"] if r.endswith(":aligned"))
    groups, cur = [], []
    for ro, t in refs:
        if cur and ro - cur[-1][0] > gap:
            groups.append(cur)
            cur = []
        cur.append((ro, t))
    if cur:
        groups.append(cur)
    out = {}
    for g in groups:
        members = {t for _, t in g}
        multi = [src_px(strings[t]["zh"]) for t in members if "\n" in strings[t]["zh"]]
        if len(members) < 3 or not multi:
            continue
        w = max(multi)
        for t in members:
            out[t] = max(out.get(t, 0), w)
    return out


def _max_para_lines(zh):
    return max(len(p.split("\n")) for p in re.split(r"\{FB\}", zh))


def dialogue_set(strings, gap=16):
    """Addresses whose text is shown in a 2-line message box (scrolls with {FA}).
    Script-referenced strings always are. Table-referenced strings are, unless
    some member of their table has a paragraph of 3+ lines (descriptions,
    Pokédex, quest log) or the string itself does."""
    script = {t for t, v in strings.items()
              if any(r.split(":")[1] in SCRIPT_KINDS for r in v["refs"])}
    refs = sorted((int(r.split(":")[0], 16), t) for t, v in strings.items()
                  for r in v["refs"] if r.endswith(":aligned"))
    groups, cur = [], []
    for ro, t in refs:
        if cur and ro - cur[-1][0] > gap:
            groups.append(cur)
            cur = []
        cur.append((ro, t))
    if cur:
        groups.append(cur)
    tall = set()
    for g in groups:
        members = {t for _, t in g}
        if len(members) >= 3 and any(_max_para_lines(strings[t]["zh"]) > 2 for t in members):
            tall |= members
    out = set(script)
    for t, v in strings.items():
        if t in script or t in tall:
            continue
        if _max_para_lines(v["zh"]) <= 2 and re.search(r"[一-鿿]", v["zh"]):
            out.add(t)
    return out
