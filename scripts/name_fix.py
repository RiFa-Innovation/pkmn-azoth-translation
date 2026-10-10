"""Make character names consistent across the translation memory.

text/en/name_canon.json maps a Chinese name to its canonical English and the
variant renderings that parallel translators produced. For every TM entry whose
Chinese contains the name, whole-word variants in the English are replaced.

    python3 scripts/name_fix.py          # report + rewrite text/en/strings.json
    python3 scripts/name_fix.py --dry    # report only
"""
import json
import re
import sys

TM = "text/en/strings.json"


def main():
    canon = json.load(open("text/en/name_canon.json", encoding="utf-8"))
    tm = json.load(open(TM, encoding="utf-8"))
    changed = 0
    for zh, en in tm.items():
        if not en:
            continue
        new = en
        for name, c in canon.items():
            if name in zh:
                for v in c["variants"]:
                    new = re.sub(r"(?<![A-Za-z])" + re.escape(v) + r"(?![A-Za-z])", c["en"], new)
        if new != en:
            changed += 1
            if changed <= 8:
                print(f"{en[:70]!r}\n  -> {new[:70]!r}")
            tm[zh] = new
    print(f"{changed} entries changed")
    if "--dry" not in sys.argv:
        json.dump(tm, open(TM, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
