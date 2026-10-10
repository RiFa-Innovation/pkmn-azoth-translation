"""Insert English text into the patched Mercury ROM and build the BPS patch.

Inputs:
  text/zh.json                 dump (scripts/dump_all.py)
  text/en/tables/<name>.json   {index: english}   fixed-stride name tables
  text/en/strings*.json        {chinese: english} translation memory

Strings that fit are written in place; the rest go to free space and every
trusted reference is repointed. Originals with only trusted refs (and no other
string inside them) are recycled as free space.

Outputs: build/Mercury_EN.gba, build/Mercury_EN.bps (applies to clean FR 1.0),
         build/insert_report.json
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bps  # noqa: E402
import layout  # noqa: E402
import mercury_text as mt  # noqa: E402

BASE = "roms/Pokemon - FireRed Version (USA, Europe).gba"
PATCHED = "roms/Pokemon Mercury 1.3.3 (patched).gba"
DIALOGUE_KINDS = ("loadpointer", "message", "trainerbattle")
DIALOGUE_PX = 204
HELP_PX = 222
MIN_FREE_RUN = 512
FREE_MARGIN = 16


def load_tm():
    tm = {}
    for path in sorted(glob.glob("text/en/strings*.json")):
        tm.update(json.load(open(path, encoding="utf-8")))
    return tm


def src_max_px(zh, widths):
    best = 0
    for line in re.split(r"\n|\{FA\}|\{FB\}", zh):
        line = re.sub(r"\{[^}]*\}", "", line)
        px = sum(mt.HANZI_PX if ord(c) >= 0x3000 else 6 for c in line)
        best = max(best, px)
    return best


class FreePool:
    def __init__(self, rom):
        self.runs = []
        for m in re.finditer(rb"\xff{%d,}" % MIN_FREE_RUN, rom):
            self.runs.append([m.start() + FREE_MARGIN, m.end()])

    def add(self, start, end):
        if end - start >= 8:
            self.runs.append([start, end])

    def alloc(self, n):
        best = None
        for r in self.runs:  # best fit
            if r[1] - r[0] >= n and (best is None or r[1] - r[0] < best[1] - best[0]):
                best = r
        if best is None:
            raise MemoryError(f"no free space for {n} bytes")
        a = best[0]
        best[0] += n
        return a

    def total(self):
        return sum(e - s for s, e in self.runs)


def main():
    base = open(BASE, "rb").read()
    src = open(PATCHED, "rb").read()
    rom = bytearray(src)
    widths = src[mt.WIDTHS_OFF:mt.WIDTHS_OFF + 256]
    dump = json.load(open("text/zh.json", encoding="utf-8"))
    report = {"tables": {}, "inplace": 0, "relocated": 0, "missing": 0,
              "too_long": [], "errors": []}

    # --- fixed-stride tables
    for name, t in dump["tables"].items():
        path = f"text/en/tables/{name}.json"
        if not os.path.exists(path):
            continue
        en = json.load(open(path, encoding="utf-8"))
        base_off, stride, size = int(t["base"], 16), t["stride"], t["size"]
        n = 0
        for idx, text in en.items():
            try:
                b = mt.encode_en(text)
            except ValueError as e:
                report["errors"].append(f"{name}[{idx}]: {e}")
                continue
            if len(b) > size:
                report["too_long"].append(f"{name}[{idx}] {text!r} ({len(b)}>{size})")
                continue
            o = base_off + int(idx) * stride
            rom[o:o + size] = b + b"\x00" * (size - len(b))
            n += 1
        report["tables"][name] = n

    # --- pointer-referenced strings
    tm = load_tm()
    strings = {int(k, 16): v for k, v in dump["strings"].items()}
    # debugging: INSERT_SKIP=<json list of hex addrs> leaves those strings untouched
    if os.environ.get("INSERT_SKIP"):
        for a in json.load(open(os.environ["INSERT_SKIP"])):
            strings.pop(int(a, 16), None)
    starts = sorted(strings)
    contains_other = set()
    for i, a in enumerate(starts):
        for b in starts[i + 1:]:
            if b >= a + strings[a]["cap"]:
                break
            contains_other.add(a)
            contains_other.add(b)  # b's tail is shared too; never write either in place
    table_px = layout.table_widths(strings)
    dialogue_addrs = layout.dialogue_set(strings)
    pool = FreePool(src)
    # debugging: INSERT_NORECYCLE=<json list of hex addrs> never frees those originals
    keep = set()
    if os.environ.get("INSERT_NORECYCLE"):
        keep = {int(a, 16) for a in json.load(open(os.environ["INSERT_NORECYCLE"]))}
    pending = []
    for t in starts:
        v = strings[t]
        if v.get("suspect") or tm.get(v["zh"], "") is None:
            continue
        en = tm.get(v["zh"])
        if en is None:
            report["missing"] += 1
            continue
        dialogue = t in dialogue_addrs
        single_line = not dialogue and not re.search(r"\n|\{FA\}|\{FB\}", v["zh"])
        max_px = DIALOGUE_PX if dialogue else max(src_max_px(v["zh"], widths), table_px.get(t, 0), 48)
        if "{F9:0A}" in v["zh"]:  # help-system pages use the full-width window
            max_px = HELP_PX
        try:
            text = en if single_line else mt.wrap_en(en, widths, max_px, dialogue)
            b = mt.encode_en(text)
        except ValueError as e:
            report["errors"].append(f"{t:07X}: {e}")
            continue
        if len(b) <= v["cap"] and t not in contains_other:
            rom[t:t + v["cap"]] = b + b"\xff" * (v["cap"] - len(b))
            pool.add(t + len(b) + 1, t + v["cap"]) if v["untrusted"] == 0 and t not in keep else None
            report["inplace"] += 1
        else:
            pending.append((t, b))
            if v["untrusted"] == 0 and t not in contains_other and t not in keep:
                pool.add(t + 1, t + v["cap"])  # keep byte 0 so stray reads hit text
    report["free_before_reloc"] = pool.total()
    for t, b in sorted(pending, key=lambda x: -len(x[1])):
        a = pool.alloc(len(b))
        rom[a:a + len(b)] = b
        for r in strings[t]["refs"]:
            ro = int(r.split(":")[0], 16)
            rom[ro:ro + 4] = (0x08000000 + a).to_bytes(4, "little")
        report["relocated"] += 1
    # --- manual strings (text/en/manual_strings.json): unfindable by the scan
    manual = json.load(open("text/en/manual_strings.json", encoding="utf-8"))
    for addr, m in manual.items():
        if addr.startswith("_"):
            continue
        t = int(addr, 16)
        assert mt.decode(src, t, m["cap"])[0] == m["zh"], f"manual {addr}: source text moved"
        b = mt.encode_en(m["en"])
        if len(b) <= m["cap"]:
            rom[t:t + m["cap"]] = b + b"\xff" * (m["cap"] - len(b))
            report["inplace"] += 1
        if m.get("ref_en") or (len(b) > m["cap"] and m.get("refs")):
            # ref_en: a different (longer) text for what the pointers show,
            # e.g. a list label, while code-computed reads see the in-place text
            b = mt.encode_en(m.get("ref_en", m["en"]))
            a = pool.alloc(len(b))
            rom[a:a + len(b)] = b
            for r in m["refs"]:
                ro = int(r, 16)
                assert int.from_bytes(src[ro:ro + 4], "little") == 0x08000000 + t, f"manual ref {r}"
                rom[ro:ro + 4] = (0x08000000 + a).to_bytes(4, "little")
            report["relocated"] += 1
        elif len(mt.encode_en(m["en"])) > m["cap"]:
            report["too_long"].append(f"manual {addr} {m['en']!r} ({len(b)}>{m['cap']})")
    report["free_after"] = pool.total()

    os.makedirs("build", exist_ok=True)
    out = os.environ.get("INSERT_OUT")  # debugging: write only this ROM
    if out:
        open(out, "wb").write(rom)
        print({k: (v if not isinstance(v, list) else len(v)) for k, v in report.items()})
        return
    open("build/Mercury_EN.gba", "wb").write(rom)
    open("build/Mercury_EN.bps", "wb").write(bps.create(base, bytes(rom)))
    json.dump(report, open("build/insert_report.json", "w"), indent=1, ensure_ascii=False)
    print({k: (v if not isinstance(v, list) else len(v)) for k, v in report.items()})


if __name__ == "__main__":
    main()
