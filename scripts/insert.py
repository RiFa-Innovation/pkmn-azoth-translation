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
import gfx_text  # noqa: E402
import logo  # noqa: E402
import maptext  # noqa: E402
import sprtext  # noqa: E402
import typeicons  # noqa: E402
import anchored  # noqa: E402

BASE = "roms/Pokemon - FireRed Version (USA, Europe).gba"
PATCHED = "roms/Pokemon Mercury 1.3.3 (patched).gba"
DIALOGUE_KINDS = ("loadpointer", "message", "trainerbattle")
DIALOGUE_PX = 198  # 204 collided with the {FA}/{FB} arrow
ITEM_DESC_PX = 176  # bag description box: starts after the item icon, ends before the arrow
HELP_PX = 222
MIN_FREE_RUN = 512
NAMING_DISPATCH = "002813d0052811d2f0b5474680b488460006070e1204150c1b041e0c0a4cf22040010a4b00f00ef80949084700900948f7b51e0008ab1d780748084b01911700074c2047184700008c9903029d2b000873d90908b55eff0918270000b12b0008c55eff09"  # data/naming_dispatch.s (arm-none-eabi-as -mthumb; objcopy -O binary)
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

    def reserve(self, start, end):
        """Never hand out [start, end) (in-place text lives there)."""
        out = []
        for a, b in self.runs:
            if b <= start or a >= end:
                out.append([a, b])
                continue
            if a < start:
                out.append([a, start])
            if b > end:
                out.append([end, b])
        self.runs = out

    def alloc_aligned(self, n, align=4):
        a = self.alloc(n + align - 1)
        pad = -a % align
        self.add(a + pad + n, a + n + align - 1)  # give back the unused tail
        return a + pad

    def alloc_near(self, n, lo, hi, align=4):
        """Aligned n bytes inside [lo, hi) (e.g. within Thumb BL range)."""
        for r in self.runs:
            a = max(r[0], lo)
            a += -a % align
            if a + n <= min(r[1], hi):
                if a > r[0]:
                    self.add(r[0], a)
                r[0] = a + n
                return a
        raise MemoryError(f"no free space for {n} bytes in [{lo:#x}, {hi:#x})")

    def total(self):
        return sum(e - s for s, e in self.runs)


def naming_dispatch(rom, src, pool):
    """DoNamingScreen dispatcher (data/naming_dispatch.s, assembled with
    arm-none-eabi-as; bytes checked in as NAMING_DISPATCH, entry points at
    +0 / +8 vanilla / +0x2E hack_nostore).

    FireRed's entry 0x0809D954: `b +12` to a Thumb->ARM long jump to the
    dispatcher (in bytes FireRed's replayed prologue frees); the hack's old
    hook stays at +2..+11 for the routines that call +2, its literal re-aimed
    at hack_nostore. The hack's DoNamingScreen entry (only the intro's player
    naming calls it) long-jumps to the dispatcher's FireRed path."""
    VAN, HACK = 0x9D954, 0x1FF5EB4
    assert src[VAN:VAN + 12] == bytes.fromhex("0090014800470000b55eff09")  # the hack's hook
    assert src[HACK:HACK + 16] == bytes.fromhex("f7b51e0008ab1d781048114b01911700")
    code = bytes.fromhex(NAMING_DISPATCH)
    d = pool.alloc_aligned(len(code))
    rom[d:d + len(code)] = code
    jump = lambda t: bytes.fromhex("7847c046" "00c09fe5" "1cff2fe1") + (0x08000000 + t + 1).to_bytes(4, "little")
    rom[VAN:VAN + 2] = bytes.fromhex("04e0")                       # b 0x0809D960
    rom[VAN + 8:VAN + 12] = (0x08000000 + d + 0x2E + 1).to_bytes(4, "little")  # hook literal
    rom[VAN + 12:VAN + 28] = jump(d)
    rom[HACK:HACK + 16] = jump(d + 8)


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
    # strings referenced from an item table's description field (+0x14)
    item_desc = set()
    for tb, n in ((0x3DB028, 378), (0x7C7E00, 750)):
        for i in range(n):
            item_desc.add(int.from_bytes(src[tb + 44 * i + 0x14:tb + 44 * i + 0x18], "little") - 0x08000000)
    dialogue_addrs = layout.dialogue_set(strings)
    pool = FreePool(src)
    # debugging: INSERT_NORECYCLE=<json list of hex addrs> never frees those originals
    keep = set()
    if os.environ.get("INSERT_NORECYCLE"):
        keep = {int(a, 16) for a in json.load(open(os.environ["INSERT_NORECYCLE"]))}
    # window width in px for strings shown in narrower boxes than their class
    width_override = {k: v for k, v in json.load(
        open("text/en/width_override.json", encoding="utf-8")).items() if not k.startswith("_")}
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
        if t in item_desc:  # bag description box (3 lines, ~176px before the arrow)
            max_px, dialogue, single_line = ITEM_DESC_PX, False, False
        if f"{t:07X}" in width_override:
            wo = width_override[f"{t:07X}"]
            max_px, dialogue, single_line = wo["px"], wo.get("dialogue", dialogue), False
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
    # anchor-reached text is written in place below: keep it out of the pool
    anc_zh = json.load(open(anchored.ZH, encoding="utf-8"))
    anc_en = json.load(open(anchored.EN, encoding="utf-8")) if os.path.exists(anchored.EN) else {}
    for k, v in anc_zh.items():
        pool.reserve(int(k, 16) - 1, int(k, 16) + v["cap"])
    # in-place manual strings and code-anchored text likewise
    for k, v in json.load(open("text/en/manual_strings.json", encoding="utf-8")).items():
        if not k.startswith("_"):
            pool.reserve(int(k, 16) - 1, int(k, 16) + v["cap"])
    for name, blk in json.load(open("text/en/code_text.json", encoding="utf-8")).items():
        if not name.startswith("_"):
            for st in blk["strings"]:
                a = int(st["zh_at"], 16)
                pool.reserve(a - 1, src.index(b"\xff", a) + 1)
    # every word that gets repointed below must not end up under new text
    for v in strings.values():
        for r in v["refs"]:
            ro = int(r.split(":")[0], 16)
            pool.reserve(ro, ro + 4)
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
    # --- code-anchored text (text/en/code_text.json): code reaches it as
    # literal base + adds imm8, so move the whole group and patch the code
    code_text = json.load(open("text/en/code_text.json", encoding="utf-8"))
    for name, blk in code_text.items():
        if name.startswith("_"):
            continue
        lit = int(blk["literal"], 16)
        assert src[lit:lit + 4] == int(blk["orig"], 16).to_bytes(4, "little"), f"code_text {name}: literal moved"
        parts = []
        for s in blk["strings"]:
            assert mt.decode(src, int(s["zh_at"], 16), 1024)[0] == s["zh"], f"code_text {name}: source text moved"
            parts.append((int(s["off"], 16), mt.encode_en(s["en"])))
        lo = min(o for o, _ in parts)
        hi = max(o + len(b) for o, b in parts)
        for (o1, b1), (o2, _) in zip(sorted(parts), sorted(parts)[1:]):
            assert o1 + len(b1) <= o2, f"code_text {name}: strings overlap"
        a = pool.alloc(hi - lo)
        base_addr = a - lo
        for o, b in parts:
            rom[base_addr + o:base_addr + o + len(b)] = b
        rom[lit:lit + 4] = (0x08000000 + base_addr).to_bytes(4, "little")
        for p in blk["patch"]:
            at, orig, new = int(p["at"], 16), bytes.fromhex(p["orig"]), bytes.fromhex(p["new"])
            assert src[at:at + len(orig)] == orig, f"code_text {name}: code at {p['at']} differs"
            rom[at:at + len(new)] = new
        report["relocated"] += len(parts)
    # --- anchor-reached text (anchored.py): in place, within the original bytes
    report["anchored"] = 0
    for k, en in anc_en.items():
        if en is None:  # not text (e.g. the pinyin keyboard's character table)
            continue
        t, v = int(k, 16), anc_zh[k]
        assert mt.decode(src, t, v["cap"])[0] == v["zh"], f"anchored {k}: source text moved"
        b = anchored.layout(v["zh"], en, widths)
        if len(b) > v["cap"]:
            if not anchored.relocatable(v):
                report["too_long"].append(f"anchored {k} ({len(b)}>{v['cap']})")
                continue
            a = pool.alloc(len(b))  # move it; point each anchor at (a - offset)
            rom[a:a + len(b)] = b
            for lit, off in v["anchors"]:
                lo = int(lit, 16)
                assert int.from_bytes(src[lo:lo + 4], "little") == 0x08000000 + t - off
                rom[lo:lo + 4] = (0x08000000 + a - off).to_bytes(4, "little")
        else:
            rom[t:t + v["cap"]] = b + b"\xff" * (v["cap"] - len(b))
        report["anchored"] += 1
    # --- image text (gfx/*.json): redrawn tileset + tilemap, LZ77, repointed
    report["gfx"] = 0
    for spec in sorted(glob.glob("gfx/*.json")):
        if os.path.basename(spec).startswith("font"):
            continue
        if os.path.basename(spec).startswith("spr_"):
            data, refs = sprtext.apply(spec, src)   # text-only sprite, redrawn
            a = pool.alloc_aligned(len(data))
            rom[a:a + len(data)] = data
            for r in refs:
                rom[r:r + 4] = (0x08000000 + a).to_bytes(4, "little")
            report["gfx"] += 1
            continue
        if os.path.basename(spec).startswith("map_"):
            # text baked into a map's tileset: metatiles/blocks in place,
            # the grown tileset relocated
            writes, data, refs = maptext.apply(spec, src)
            for off, b in writes.items():
                rom[off:off + len(b)] = b
            a = pool.alloc_aligned(len(data))
            rom[a:a + len(data)] = data
            for r in refs:
                rom[r:r + 4] = (0x08000000 + a).to_bytes(4, "little")
            report["gfx"] += 1
            continue
        for data, refs, _ in gfx_text.apply(spec, src):
            a = pool.alloc_aligned(len(data))
            rom[a:a + len(data)] = data
            for r in refs:
                rom[r:r + 4] = (0x08000000 + a).to_bytes(4, "little")
        report["gfx"] += 1
    # type icons + TYPE/POWER/... labels (hack's menu-info sheet, raw, in place)
    ti = typeicons.build(src, base)
    rom[typeicons.SHEET:typeicons.SHEET + len(ti)] = ti
    report["gfx"] += 1
    # title logo (raw 8bpp BG): fits in the original tile area, so in place
    lt, lm = logo.build(src)
    assert len(lt) <= 162 * 64
    rom[logo.TILES:logo.TILES + len(lt)] = lt
    rom[logo.MAP:logo.MAP + len(lm)] = lm
    report["gfx"] += 1
    # plain code/data patches (data/code_patches.json)
    for name, blk in json.load(open("data/code_patches.json")).items():
        if name.startswith("_"):
            continue
        for p in blk["patch"]:
            at, orig, new = int(p["at"], 16), bytes.fromhex(p["orig"]), bytes.fromhex(p["new"])
            assert src[at:at + len(orig)] == orig, f"code patch {name}: bytes at {p['at']} differ"
            rom[at:at + len(new)] = new
        for a, b, _ in blk.get("vanilla", []):
            a, b = int(a, 16), int(b, 16)
            rom[a:b] = base[a:b]
    naming_dispatch(rom, src, pool)
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
