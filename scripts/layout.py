"""Window-width estimates for non-dialogue strings.

Strings referenced from the same pointer table share a window, so a table's
width budget is the widest line among its multi-line members (Chinese lines
are often broken by sentence, not by the window edge).
"""
import re

HANZI_PX, LATIN_PX = 12, 6


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
