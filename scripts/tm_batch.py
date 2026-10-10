"""Translation-memory batch helper for dialogue/menu strings.

  python3 scripts/tm_batch.py next [N]       print next N untranslated strings
  python3 scripts/tm_batch.py add <file>     merge {id: english} into the TM
  python3 scripts/tm_batch.py check <file>   validate {id: english} without merging
  python3 scripts/tm_batch.py lookup <zh>    official names + existing TM uses of a term
  python3 scripts/tm_batch.py export <dir> <n_chunks>  split untranslated queue into chunk files
  python3 scripts/tm_batch.py stats

IDs index text/queue.json: unique non-suspect Chinese strings in ROM-address
order, built once from text/zh.json (stable across runs). Translations are
saved into text/en/strings.json keyed by the Chinese text; null marks junk
that must never be inserted.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import layout  # noqa: E402
import mercury_text as mt  # noqa: E402

QUEUE = "text/queue.json"
WIDTHS = open("roms/Pokemon Mercury 1.3.3 (patched).gba", "rb").read()[mt.WIDTHS_OFF:mt.WIDTHS_OFF + 256]
TM = "text/en/strings.json"


def queue():
    """Unique non-suspect strings. IDs are stable: an existing queue is only
    ever appended to (new strings from a re-dump go at the end)."""
    d = json.load(open("text/zh.json", encoding="utf-8"))["strings"]
    q = json.load(open(QUEUE, encoding="utf-8")) if os.path.exists(QUEUE) else []
    seen, n0 = set(q), len(q)
    for k in sorted(d, key=lambda x: int(x, 16)):
        zh = d[k]["zh"]
        if not d[k].get("suspect") and zh not in seen:
            seen.add(zh)
            q.append(zh)
    if len(q) != n0:
        json.dump(q, open(QUEUE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return q


def tm():
    return json.load(open(TM, encoding="utf-8")) if os.path.exists(TM) else {}


def main():
    cmd = sys.argv[1]
    q, t = queue(), tm()
    covered = dict(t)
    if os.path.exists("text/en/strings-vanilla.json"):
        covered.update(json.load(open("text/en/strings-vanilla.json", encoding="utf-8")))
    if cmd == "next":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        out = 0
        for i, zh in enumerate(q):
            if i < start or zh in covered:
                continue
            print(f"{i}\t{zh.replace(chr(10), ' / ')}")
            out += 1
            if out >= n:
                break
    elif cmd == "lookup":
        term = sys.argv[2]
        names = json.load(open("text/en/names_zh_en.json", encoding="utf-8"))
        for zh, en in names.items():
            if term in zh:
                print(f"NAME\t{zh}\t{en}")
        n = 0
        for zh, en in covered.items():
            if en and term in zh and n < 6:
                print(f"TM\t{zh.replace(chr(10), ' / ')}\t{en.replace(chr(10), ' / ')}")
                n += 1
    elif cmd == "export":
        out_dir, k = sys.argv[2], int(sys.argv[3])
        todo = [(i, zh) for i, zh in enumerate(q) if zh not in covered]
        hz = lambda s: sum(1 for c in s if "\u4e00" <= c <= "\u9fff") + 4
        total = sum(hz(z) for _, z in todo)
        os.makedirs(out_dir, exist_ok=True)
        chunk, acc, n = [], 0, 0
        for i, zh in todo:
            chunk.append({"id": str(i), "zh": zh})
            acc += hz(zh)
            if acc >= total / k and n < k - 1:
                json.dump(chunk, open(f"{out_dir}/chunk{n:02d}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
                chunk, acc, n = [], 0, n + 1
        json.dump(chunk, open(f"{out_dir}/chunk{n:02d}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"{len(todo)} strings -> {n + 1} chunks in {out_dir}")
    elif cmd in ("add", "check"):
        zs = {int(k, 16): v for k, v in json.load(open("text/zh.json", encoding="utf-8"))["strings"].items()}
        dset = layout.dialogue_set(zs)
        dialogue_zh = {v["zh"] for a, v in zs.items() if a in dset}
        tw = layout.table_widths(zs)
        budget = {}
        for a, v in zs.items():
            b = max(layout.src_px(v["zh"]), tw.get(a, 0), 48)
            budget[v["zh"]] = min(budget.get(v["zh"], b), b)
        new = json.load(open(sys.argv[2], encoding="utf-8"))
        bad = []
        for i, en in new.items():
            if not 0 <= int(i) < len(q):
                bad.append((i, "id not in queue"))
                continue
            zh = q[int(i)]
            if en is None:  # junk that slipped past the suspect filter
                t[zh] = None
                continue
            try:
                mt.encode_en(en)
            except ValueError as e:
                bad.append((i, str(e)))
                continue
            toks_zh = sorted(x for x in __import__("re").findall(r"\{F[^}]*\}", zh) if x not in ("{FA}", "{FB}"))
            toks_en = sorted(x for x in __import__("re").findall(r"\{F[^}]*\}", en) if x not in ("{FA}", "{FB}"))
            if toks_zh != toks_en:
                bad.append((i, f"control tokens differ: {toks_zh} vs {toks_en}"))
            if zh not in dialogue_zh and "\n" in en and "\n" in zh:  # warn if wider than source
                src = max(sum(12 if ord(c) >= 0x3000 else 6 for c in re.sub(r"\{[^}]*\}", "", ln))
                          for ln in zh.split("\n"))
                wide = [ln for ln in en.split("\n")
                        if len(re.sub(r"\{[^}]*\}", "", ln)) * 6 > max(src, 48)]
                if "{F9:0A}" in zh:
                    wide = [ln for ln in en.split("\n") if len(re.sub(r"\{[^}]*\}", "", ln)) * 6 > 222]
                if wide:
                    bad.append((i, f"lines wider than source ({src}px): {wide}"))
            if zh not in dialogue_zh and "\n" in zh and "{F9:0A}" not in zh:
                src_px = budget[zh]
                n_src = len(zh.split("\n"))
                n_en = len(mt.wrap_en(en, WIDTHS, src_px, False).split("\n"))
                if n_en > n_src:
                    bad.append((i, f"needs {n_en} lines > {n_src} at {src_px}px ({len(en)} chars)"))
            t[zh] = en
        if cmd == "add":
            json.dump(t, open(TM, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
            print(f"added {len(new)}; TM now {len(t)}/{len(q)}")
        else:
            print(f"checked {len(new)}: {len(bad)} warnings")
        for b in bad:
            print("WARN", *b)
    elif cmd == "stats":
        t = covered
        done = sum(1 for zh in q if zh in t)
        hz = lambda s: sum(1 for c in s if "一" <= c <= "鿿")
        print(f"{done}/{len(q)} strings, "
              f"{sum(hz(z) for z in q if z in t)}/{sum(hz(z) for z in q)} hanzi")


if __name__ == "__main__":
    main()
