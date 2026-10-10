"""Vanilla FireRed (US 1.0) ROM layout from the pokefirered decomp build.

Every byte of the clean ROM up to 0x08D00000 belongs to a linker input
section of a known object file (code, script data, read-only data, ...) and
usually to a named symbol. This replaces guessing what a pointer is: a word
inside .text is a code literal (agbcc has no section anchors, so a literal
that points at a string is the string), a word inside .rodata is a struct or
table field, a word inside script_data is a script argument.

    python3 scripts/frmap.py build      # parse utilities/pokefirered -> data/fr_map.json
    python3 scripts/frmap.py 0x81C55C9  # what is at this address?

Requires the decomp built once (`make firered` in utilities/pokefirered with
agbcc + arm-none-eabi binutils/gcc); data/fr_map.json is committed so later
use needs no toolchain.
"""
import bisect
import json
import os
import re
import subprocess
import sys

DECOMP = "utilities/pokefirered"
CACHE = "data/fr_map.json"
KIND = {".text": "code", "lib_text": "code", "script_data": "script", ".rodata": "data",
        "lib_rodata": "data", "song_data": "song", "multiboot_data": "data", "gfx_data": "gfx",
        ".text.consts": "data"}


def build():
    regions = []
    out_sec = None
    pending = None
    for line in open(f"{DECOMP}/pokefirered.map", encoding="utf-8", errors="replace"):
        m = re.match(r"^(\S+)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)", line)
        if m and not line.startswith(" "):
            out_sec = m.group(1)
            continue
        m = re.match(r"^ (\S+)\s*$", line)  # input section name alone; values on next line
        if m:
            pending = m.group(1)
            continue
        m = re.match(r"^ (\S+)?\s+0x([0-9a-f]{8})\s+0x([0-9a-f]+)\s+(\S+)", line)
        if m:
            sec = m.group(1) or pending
            pending = None
            addr, size = int(m.group(2), 16), int(m.group(3), 16)
            if 0x08000000 <= addr < 0x0A000000 and size and sec and not sec.startswith("*"):
                kind = KIND.get(sec, KIND.get(out_sec, "data"))
                regions.append([addr - 0x08000000, addr - 0x08000000 + size, kind, sec, m.group(4)])
    regions.sort()
    nm = subprocess.run(["arm-none-eabi-nm", "-S", "-n", f"{DECOMP}/pokefirered.elf"],
                        capture_output=True, text=True, check=True).stdout
    syms = []
    for line in nm.splitlines():
        p = line.split()
        if len(p) == 4 and p[0].startswith("08"):
            syms.append([int(p[0], 16) - 0x08000000, int(p[1], 16), p[3]])
        elif len(p) == 3 and p[0].startswith("08"):
            syms.append([int(p[0], 16) - 0x08000000, 0, p[2]])
    syms.sort()
    os.makedirs("data", exist_ok=True)
    json.dump({"regions": regions, "symbols": syms}, open(CACHE, "w"), separators=(",", ":"))
    print(len(regions), "regions,", len(syms), "symbols ->", CACHE)


class FRMap:
    def __init__(self, path=CACHE):
        d = json.load(open(path))
        self.regions = d["regions"]
        self.rstarts = [r[0] for r in self.regions]
        self.syms = [s for s in d["symbols"] if not re.match(r"^_08|^\$", s[2])]
        self.sstarts = [s[0] for s in self.syms]

    def region(self, off):
        i = bisect.bisect_right(self.rstarts, off) - 1
        if i >= 0 and self.regions[i][0] <= off < self.regions[i][1]:
            return self.regions[i]
        return None

    def kind(self, off):
        r = self.region(off)
        return r[2] if r else None

    def symbol(self, off):
        """(name, start, size) of the symbol containing off, or the nearest
        preceding one (size 0 = unknown extent)."""
        i = bisect.bisect_right(self.sstarts, off) - 1
        if i < 0:
            return None
        a, size, name = self.syms[i]
        return name, a, size

    def describe(self, off):
        r = self.region(off)
        s = self.symbol(off)
        where = f"{s[0]}+0x{off - s[1]:X}" if s else "?"
        return f"{off:07X}: {r[2] if r else 'outside vanilla'} [{r[3] if r else ''} {r[4] if r else ''}] {where}"


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build()
    else:
        m = FRMap()
        for a in sys.argv[1:]:
            v = int(a, 16)
            print(m.describe(v - 0x08000000 if v >= 0x08000000 else v))
