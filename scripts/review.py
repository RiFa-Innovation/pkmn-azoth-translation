"""Proofreading helper: export the English text to a CSV, review it in a
spreadsheet, import the corrections back.

    python3 scripts/review.py export OUT.csv [--match TEXT] [--source hand|vanilla|all]
                                             [--start N] [--limit N]
    python3 scripts/review.py import EDITED.csv [--tm text/en/strings.json] [--dry-run]

CSV columns: id, source, zh, en, new_en
  id      address of the first reference (for a human to find the line in game)
  source  hand = translated for this project, vanilla = FireRed's own English
  zh      Chinese source (the translation memory is keyed by this text)
  en      current English
  new_en  fill this in to propose a change; leave it empty to keep `en`
Newlines are written as the two characters \\n in every text column.

Import checks that new_en keeps exactly the control codes of the source
({FD:01}, {FB}, {FC:..} ...) and is encodable in the game's font, then writes
it to text/en/strings.json (which overrides FireRed's strings-vanilla.json).
Wrapping is done by the inserter, so don't hand-wrap dialogue.
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import mercury_text as mt  # noqa: E402

TOKEN = re.compile(r"\{[^}]*\}")
HAND = "text/en/strings.json"


def _load_sources():
    zh = json.load(open("text/zh.json", encoding="utf-8"))["strings"]
    vanilla = json.load(open("text/en/strings-vanilla.json", encoding="utf-8"))
    hand = json.load(open(HAND, encoding="utf-8"))
    return zh, vanilla, hand


def _esc(s):
    return s.replace("\n", "\\n")


def _unesc(s):
    return s.replace("\\n", "\n")


def export(args):
    zh, vanilla, hand = _load_sources()
    seen, rows = set(), []
    for addr in sorted(zh):
        e = zh[addr]
        if e.get("suspect") or e["zh"] in seen:
            continue
        key = e["zh"]
        if hand.get(key):
            src, en = "hand", hand[key]
        elif vanilla.get(key):
            src, en = "vanilla", vanilla[key]
        else:
            continue
        if args.source != "all" and src != args.source:
            continue
        if args.match and args.match.lower() not in (en + key).lower():
            continue
        seen.add(key)
        rows.append((addr, src, _esc(key), _esc(en)))
    rows = rows[args.start:args.start + args.limit] if args.limit else rows[args.start:]
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "source", "zh", "en", "new_en"])
        for r in rows:
            w.writerow(list(r) + [""])
    print(f"{len(rows)} strings -> {args.out}")


LAYOUT = {"{FA}", "{FB}"}  # scroll / new-box: where text breaks, not data


def _data_tokens(text):
    return Counter(t for t in TOKEN.findall(text) if t not in LAYOUT)


def check(zh_text, new_en, current_en=""):
    """Problems with a proposed English string (empty list = fine).

    Data-bearing control codes ({FD:01} player name, {F9:..} icons, {FC:..}
    colours...) must match the Chinese source or the current English; {FA}
    and {FB} may move because the inserter re-wraps dialogue."""
    problems = []
    got = _data_tokens(new_en)
    if got != _data_tokens(zh_text) and not (current_en and got == _data_tokens(current_en)):
        problems.append("control codes differ from the source: "
                        f"{sorted(_data_tokens(zh_text).elements())} vs {sorted(got.elements())}")
    try:
        mt.encode_en(new_en)
    except ValueError as exc:
        problems.append(f"not encodable in the game font: {exc}")
    return problems


def import_(args):
    tm = json.load(open(args.tm, encoding="utf-8"))
    changed = bad = same = 0
    with open(args.csv, encoding="utf-8", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            new = (row.get("new_en") or "").strip()
            if not new:
                continue
            zh, new = _unesc(row["zh"]), _unesc(new)
            if new == _unesc(row["en"]):
                same += 1
                continue
            problems = check(zh, new, _unesc(row["en"]))
            if problems:
                bad += 1
                print(f"line {n} ({row['id']}): REJECTED: " + "; ".join(problems))
                continue
            tm[zh] = new
            changed += 1
            print(f"line {n} ({row['id']}): ok")
    print(f"{changed} accepted, {bad} rejected, {same} unchanged")
    if changed and not args.dry_run:
        # same formatting as tm_batch.py so diffs stay small
        json.dump(tm, open(args.tm, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"wrote {args.tm}; now run: python3 scripts/insert.py")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("out")
    e.add_argument("--match", help="only strings containing this text (zh or en)")
    e.add_argument("--source", choices=("hand", "vanilla", "all"), default="hand")
    e.add_argument("--start", type=int, default=0)
    e.add_argument("--limit", type=int, default=0)
    e.set_defaults(fn=export)
    i = sub.add_parser("import")
    i.add_argument("csv")
    i.add_argument("--tm", default=HAND)
    i.add_argument("--dry-run", action="store_true")
    i.set_defaults(fn=import_)
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
