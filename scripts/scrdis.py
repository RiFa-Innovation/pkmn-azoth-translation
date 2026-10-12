"""FireRed script (bytecode) disassembler - for scene forensics.

Opcode names and argument sizes come from `utilities/pokefirered/asm/macros/
event.inc` (branch aware, so the `.if/.else` macro variants each register their
opcode). The hack adds CFRU commands the table does not know: those print as
`.byte` and desync the walk, so disassemble from a *referenced* entry point
(an object/coord/map script pointer) and stop believing the output once it
prints one.

    python3 scripts/scrdis.py 0x08AF5A3A 0x08AF63F5 [...]
    python3 scripts/scrdis.py roms/Pokemon Mercury 1.3.3 (patched).gba 0x...

Where the pointers come from: `data/code_patches.json`, a map's events struct
(object/coord/bg scripts, see the map dump pattern in `PROCESS.md`), or a
pointer scan (`find` the 4-byte little endian address). Useful follow-ups once a
scene script is in front of you: movement data (`applymovement` targets are
`MOVEMENT_ACTION_*` bytes, 0x11 = walk up, 0xFE = end) and `EMULATOR.md`'s
watchpoints for the runtime side.
"""
import os
import re
import sys

MACROS = os.path.join(os.path.dirname(__file__), "..",
                      "utilities/pokefirered/asm/macros/event.inc")
KIND = {"byte": 1, "2byte": 2, "word": 2, "4byte": 4}
DEFAULT_ROM = "roms/Pokemon Mercury 1.3.3 (patched).gba"


def parse_branch(lines):
    """One .if/.else branch -> (opcode, [(kind, count), ...])."""
    args, op = [], None
    for line in lines:
        line = line.split("@")[0].strip()
        m = re.match(r"\.(byte|2byte|4byte|word)\b(.*)", line)
        if not m:
            continue
        kind, rest = m.group(1), m.group(2)
        if op is None and kind == "byte" and re.fullmatch(r"\s+0x[0-9a-fA-F]+", rest):
            op = int(rest, 16)
            continue
        if op is None:
            return None
        args.append((kind, len([x for x in rest.split(",") if x.strip()]) or 1))
    return (op, args) if op is not None else None


def load_macros(path=MACROS):
    src = open(path).read()
    table = {}
    for m in re.finditer(r"\.macro\s+(\w+)([^\n]*)\n(.*?)\.endm", src, re.S):
        parts, cur = [], []
        for line in m.group(3).splitlines():
            s = line.strip()
            if re.match(r"\.(if|elseif|else)\b", s):
                parts.append(cur)
                cur = []
            elif not s.startswith(".endif"):
                cur.append(line)
        parts.append(cur)
        for p in parts:
            r = parse_branch(p)
            if r and r[0] not in table:
                table[r[0]] = (m.group(1), r[1])
    return table


TB = {0: 12, 1: 16, 2: 16, 3: 8, 4: 16, 5: 12, 6: 16, 7: 16, 8: 16, 9: 12}


def decode(rom, ptr, table, maxops=2000):
    out, ops = [], 0
    while ops < maxops:
        off = ptr - 0x08000000
        if off < 0 or off >= len(rom):
            out.append(f"{ptr:08X}: <out of ROM>")
            break
        op = rom[off]
        if op == 0x5C:  # trainerbattle: argument count depends on the type byte
            t = rom[off + 1]
            out.append(f"{ptr:08X}: trainerbattle type {t}")
            ptr += 2 + TB.get(t, 12)
            ops += 1
            continue
        if op not in table:
            out.append(f"{ptr:08X}: .byte {op:#04x}")
            ptr += 1
            ops += 1
            continue
        name, args = table[op]
        p, txt, total = off + 1, [], 1
        for kind, n in args:
            for _ in range(n):
                w = KIND[kind]
                v = int.from_bytes(rom[p:p + w], "little")
                if kind == "4byte":
                    txt.append(f"0x{v:08X}" if 0x08000000 <= v < 0x0A000000 else f"{v:#x}")
                elif w == 2:
                    txt.append(f"{v:#x}")
                else:
                    txt.append(f"{v}" if v < 10 else f"{v:#x}")
                p += w
                total += w
        out.append(f"{ptr:08X}: {name} {' '.join(txt)}".rstrip())
        ptr += total
        ops += 1
        if name in ("end", "return"):
            break
    return out


def main():
    a = sys.argv[1:]
    rom_path = DEFAULT_ROM
    if a and not a[0].startswith("0x"):
        rom_path = a.pop(0)
    if not a:
        raise SystemExit(__doc__)
    rd = open(rom_path, "rb").read()
    table = load_macros()
    for x in a:
        ptr = int(x, 16)
        if ptr < 0x08000000:
            ptr += 0x08000000
        print(f"=== 0x{ptr:08X} ===")
        print("\n".join(decode(rd, ptr, table)))


if __name__ == "__main__":
    main()
