"""Find string refs that are really GCC section anchors.

The hack's C code often loads one literal (the start of a .rodata block) and
reaches several objects from it by offset: e.g. the dressing room loads
0x08E37264, prints the string there (已获得) and passes base+0x20 / base+0x30
to InitBgsFromTemplates / InitWindows. Repointing such a literal to relocated
English text breaks everything reached by offset (black screen / crash).

hackmap.py marks anchors only inside functions it discovered; this scan works
from the refs themselves: for every aligned/literal ref, find each Thumb
`ldr rX, [pc, #imm]` that loads it and follow rX for a few instructions until
it is overwritten. An `adds rX, #imm` or `[rX, #imm]` with imm != 0 marks an
anchor. insert.py never repoints these (in place or kept as is).

    .venv/bin/python scripts/anchor_refs.py      # -> data/anchor_refs.json
"""
import json
import struct

import capstone

ROM = "roms/Pokemon Mercury 1.3.3 (patched).gba"
OUT = "data/anchor_refs.json"
# checked by hand: the "loads" are data decoded as Thumb, not code
NOT_ANCHORS = {
    "045F9A8", "045F9B8",  # region-map name table (Indigo Plateau, Six Island)
    "1CC9DF4",             # inside the move description table (0x1CC8EB0)
    "1D49ABC",             # data between CFRU functions
}

o = open(ROM, "rb").read()
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)


def loaders(lit):
    """(offset, register) of every Thumb `ldr rX, [pc, #imm]` that loads the word at lit."""
    out = []
    for a in range(max(0, lit - 1020) & ~1, lit, 2):
        h = struct.unpack_from("<H", o, a)[0]
        if h >> 11 == 0b01001 and ((a + 4) & ~3) + (h & 0xFF) * 4 == lit:
            out.append((a, (h >> 8) & 7))
    return out


CLOBBER = ("mov", "ldr", "ldm", "add", "sub", "lsl", "lsr", "asr", "and", "orr",
           "eor", "mul", "neg", "rsb", "bic", "mvn")


def anchor_use(a, reg):
    """The instruction using the loaded base with a nonzero offset, else None."""
    regs = {f"r{reg}"}
    for i in md.disasm(o[a + 2:a + 42], 0x08000000 + a + 2):
        ops, m = i.op_str.replace(" ", ""), i.mnemonic
        if m.startswith(("stc", "ldc", "mcr", "mrc", "cdp", "udf")):
            return None  # data decoded as code
        dst = ops.split(",")[0]
        # a write to a tracked register ends tracking (except base += imm and [base, #imm] loads)
        if (dst in regs and m.startswith(CLOBBER)
                and not (m in ("adds", "add") and ops.startswith(dst + ",#"))
                and not (m.startswith("ldr") and "[" + dst + ",#" in ops)):
            regs.discard(dst)
        if not regs:
            return None
        for rr in list(regs):
            if m in ("adds", "add") and (ops.startswith(rr + ",#") or "," + rr + ",#" in ops):
                if int(ops.split("#")[-1], 0):
                    return f"{m} {i.op_str}"
            if "[" + rr + ",#" in ops and not ops.endswith("#0]"):
                return f"{m} {i.op_str}"
            if m in ("movs", "mov") and ops.endswith("," + rr):
                regs.add(dst)
        if m.startswith("b") or m == "pop":
            break
    return None


def main():
    strings = json.load(open("text/zh.json", encoding="utf-8"))["strings"]
    out = {}
    for addr, e in strings.items():
        for r in e["refs"]:
            ro, kind = r.split(":")
            if kind not in ("aligned", "literal"):
                continue
            if ro in NOT_ANCHORS:
                continue
            ro = int(ro, 16)
            for la, reg in loaders(ro):
                use = anchor_use(la, reg)
                if use:
                    out[f"{ro:07X}"] = {"string": addr, "ldr": f"{la:07X}", "use": use}
                    break
    json.dump(dict(sorted(out.items())), open(OUT, "w"), indent=1, ensure_ascii=False)
    print(f"{len(out)} anchor refs -> {OUT}")


if __name__ == "__main__":
    main()
