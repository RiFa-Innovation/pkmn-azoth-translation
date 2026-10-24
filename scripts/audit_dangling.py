"""Find pointers the inserter left dangling: strings that were relocated (their dump refs now hold a new address) while other words in the
built ROM still point at the OLD address, which the pool then reused for different text.

    python3 scripts/audit_dangling.py BUILT_ROM [ORIG_ROM]

For every dump string with refs whose first ref changed between ORIG and BUILT (= relocated), search BUILT for any remaining 4-byte word
equal to 0x08000000 + old address (aligned or not: script operands sit at odd offsets). Each hit is reported with the bytes before it
(a `0f 00` prefix = a script `loadword`), what the old address holds now, and what the string was meant to be. Read-only.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mercury_text as mt  # noqa: E402


def audit(built_path, orig_path=os.path.join(ROOT, "roms/Pokemon Mercury 1.3.3 (patched).gba")):
    built, orig = open(built_path, "rb").read(), open(orig_path, "rb").read()
    z = json.load(open(os.path.join(ROOT, "text/zh.json"), encoding="utf-8"))["strings"]
    en = json.load(open(os.path.join(ROOT, "text/en/strings.json"), encoding="utf-8"))
    en.update(json.load(open(os.path.join(ROOT, "text/en/strings-vanilla.json"), encoding="utf-8")))
    out = []
    n_reloc = 0
    for k, v in z.items():
        refs = [int(r.split(":")[0], 16) for r in v["refs"]]
        if not refs:
            continue
        old = 0x08000000 + int(k, 16)
        if int.from_bytes(built[refs[0]:refs[0] + 4], "little") == old:
            continue  # not repointed: in place (or kept)
        n_reloc += 1
        pat = old.to_bytes(4, "little")
        known = set(refs)
        for m in re.finditer(re.escape(pat), built, flags=re.S):
            pos = m.start()
            if pos in known:
                continue
            if int(k, 16) <= pos < int(k, 16) + v["cap"]:
                continue  # inside the old string's own bytes
            out.append({"string": k, "zh": v["zh"][:30], "at": f"{pos:07X}", "prefix": built[max(0, pos - 2):pos].hex(),
                        "now": mt.decode(built, int(k, 16))[0][:40].replace("\n", " "), "want": (en.get(v["zh"]) or "")[:40]})
    return n_reloc, out


if __name__ == "__main__":
    n, hits = audit(*sys.argv[1:3])
    print(f"{n} relocated strings; {len(hits)} leftover pointers to their old addresses")
    for h in hits:
        print(f"{h['string']} <- word at {h['at']} (prefix {h['prefix']}) now holds {h['now']!r}; meant {h['want']!r}")
