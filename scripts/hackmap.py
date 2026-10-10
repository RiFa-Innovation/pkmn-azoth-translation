"""Map the hack's own code (CFRU + Mercury's C) by recursive disassembly.

Vanilla code is known from the decomp (frmap.py). Code the hack added is
found from:
  * hooks: vanilla code bytes the hack changed (CFRU `ldr rX,=func|1; bx rX`
    trampolines, rewritten `bl`s) -> their targets;
  * Thumb function pointers (odd words) anywhere in the ROM that point
    outside vanilla code at a `push {.., lr}`;
and followed recursively: branches, `bl` calls, jump tables, and odd
literals (callbacks). Output data/hack_code.json:
  code:     sorted [start, end) ranges of instructions
  literals: {word_offset: {"value", "uses": [ldr offsets], "anchor": bool}}
            anchor = some use adds an offset to the loaded value (GCC
            section anchors: base + imm reaches the real data)
  funcs:    function entry offsets

    .venv/bin/python scripts/hackmap.py            # build data/hack_code.json
    .venv/bin/python scripts/hackmap.py 0x8E9DD8   # classify an offset
"""
import json
import struct
import sys

try:  # only the builder needs capstone/numpy; HackMap (used by dump_all) does not
    import capstone
    import numpy as np
except ImportError:
    capstone = np = None

sys.path.insert(0, __import__("os").path.dirname(__file__))
import frmap  # noqa: E402

ROM = "roms/Pokemon Mercury 1.3.3 (patched).gba"
BASE = "roms/Pokemon - FireRed Version (USA, Europe).gba"
OUT = "data/hack_code.json"


class Mapper:
    def __init__(self):
        self.rom = open(ROM, "rb").read()
        self.base = open(BASE, "rb").read()
        self.fm = frmap.FRMap()
        self.md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
        self.md.detail = True
        self.code = bytearray(len(self.rom))   # 1 = instruction byte
        self.lit = {}                          # word offset -> set(use offsets)
        self.anchor = {}                       # literal -> 'imm' | 'reg' 
        self.funcs = set()
        self.todo = []
        self.bad = 0
        self.case_kind = {}                    # helper offset -> uqi/sqi/uhi/shi/si/None

    def in_rom(self, v):
        return 0x08000000 <= v < 0x08000000 + len(self.rom)

    def vanilla_code(self, off):
        """Vanilla code is traced too (from the decomp's symbols), so every
        .text word is classified as instruction or literal. Returns True for
        places code cannot be: unchanged vanilla script/data/gfx/song bytes."""
        if off < len(self.base):
            k = self.fm.kind(off)
            if k not in (None, "code") and self.rom[off:off + 4] == self.base[off:off + 4]:
                return True
        return False

    def plausible(self, off):
        """A function pointer found in data must decode cleanly (Thumb-1, no
        32-bit except bl) up to its first return within 400 bytes."""
        pc = off
        for _ in range(200):
            if pc >= len(self.rom) - 4 or self.vanilla_code(pc):
                return False
            ins = next(self.md.disasm(self.rom[pc:pc + 4], 0x08000000 + pc, 1), None)
            if ins is None or (ins.size == 4 and ins.mnemonic != "bl"):
                return False
            if ins.mnemonic == "bx" or (ins.mnemonic == "pop" and "pc" in ins.op_str):
                return True
            if ins.mnemonic == "b":  # follow the branch, don't accept it as an end
                pc = ins.operands[0].imm - 0x08000000
                continue
            pc += ins.size
        return False

    def add_func(self, off):
        if 0 <= off < len(self.rom) - 2 and not self.vanilla_code(off) and off not in self.funcs:
            self.funcs.add(off)
            self.todo.append(off)

    def trace(self, start):
        """Linear sweep with branch following from one entry."""
        stack = [start]
        while stack:
            pc = stack.pop()
            while 0 <= pc < len(self.rom) - 2:
                if self.code[pc] or self.vanilla_code(pc):
                    break
                ins = next(self.md.disasm(self.rom[pc:pc + 4], 0x08000000 + pc, 1), None)
                if ins is None or ins.size == 4 and ins.mnemonic != "bl":
                    self.bad += 1
                    break
                for k in range(ins.size):
                    self.code[pc + k] = 1
                m, ops = ins.mnemonic, ins.operands
                nxt = pc + ins.size
                if m == "bl":
                    tgt = ops[0].imm - 0x08000000
                    kind = self.case_helper(tgt)
                    if kind:
                        self.case_table(pc, nxt, kind, stack)
                        break
                    self.add_func(tgt)
                elif m == "b":
                    stack.append(ops[0].imm - 0x08000000)
                    break
                elif m.startswith("b") and m not in ("bl", "bx", "bic", "bics") and ops and ops[0].type == capstone.arm.ARM_OP_IMM:
                    stack.append(ops[0].imm - 0x08000000)  # conditional branch
                elif m == "ldr" and len(ops) == 2 and ops[1].type == capstone.arm.ARM_OP_MEM \
                        and ops[1].mem.base == capstone.arm.ARM_REG_PC:
                    lit = ((pc + 4) & ~3) + ops[1].mem.disp
                    if 0 <= lit < len(self.rom) - 3:
                        self.lit.setdefault(lit, set()).add(pc)
                        v = struct.unpack_from("<I", self.rom, lit)[0]
                        t = v - 0x08000001
                        if v & 1 and self.in_rom(v) and self.rom[t + 1] in (0xB5, 0xB4) and self.plausible(t):
                            self.add_func(t)  # odd literal: callback/long call
                        how = self.offsets_value(nxt, ops[0].reg)
                        if how:
                            self.anchor[lit] = "imm" if "imm" in (how, self.anchor.get(lit)) else how
                elif m == "bx" or (m == "pop" and any(o.reg == capstone.arm.ARM_REG_PC for o in ops)):
                    break  # return / indirect call (agbcc: pop {r1}; bx r1)
                elif m == "mov" and ops[0].reg == capstone.arm.ARM_REG_PC:
                    self.jump_table(pc)
                    break
                pc = nxt

    def case_helper(self, off):
        """Recognise GCC's __gnu_thumb1_case_* switch helpers by their body:
        they index a table stored right after the calling bl using lr."""
        if off in self.case_kind:
            return self.case_kind[off]
        kind = None
        if 0 <= off < len(self.rom) - 32:
            # libgcc's helpers start with `mov r1, lr; lsrs r1, r1, #1`
            # (optionally after `mov ip, r1` / `push {r0, r1}`)
            hw = [self.rom[off + 2 * k] | self.rom[off + 2 * k + 1] << 8 for k in range(12)]
            if 0x4671 in hw[:3] and 0x0849 in hw[1:5]:
                body = list(self.md.disasm(self.rom[off:off + 24], 0x08000000 + off))
                for i in body:
                    m, o = i.mnemonic, i.op_str
                    if m in ("ldrb", "ldrsb", "ldrh", "ldrsh") and "[" in o:
                        kind = {"ldrb": "uqi", "ldrsb": "sqi", "ldrh": "uhi", "ldrsh": "shi"}[m]
                        break
                    if m == "ldr" and "[" in o and "pc" not in o:
                        kind = "si"
                        break
        self.case_kind[off] = kind
        return kind

    def case_table(self, bl_pc, ret, kind, stack):
        """Decode the inline table after `bl __gnu_thumb1_case_*`. The entry
        count comes from the guarding `cmp rX, #N` (N+1 entries)."""
        n = None
        for back in range(2, 16, 2):
            ins = next(self.md.disasm(self.rom[bl_pc - back:bl_pc - back + 2], 0x08000000 + bl_pc - back, 1), None)
            if ins and ins.mnemonic == "cmp" and ins.operands[1].type == capstone.arm.ARM_OP_IMM:
                n = ins.operands[1].imm + 1
                break
        if n is None:
            n = 1
        if kind in ("uqi", "sqi"):
            size, fmt = 1, "<b" if kind == "sqi" else "<B"
            tab = ret
        elif kind in ("uhi", "shi"):
            size, fmt = 2, "<h" if kind == "shi" else "<H"
            tab = ret
        else:
            size, fmt = 4, "<i"
            tab = (ret + 3) & ~3
        for k in range(n):
            v = struct.unpack_from(fmt, self.rom, tab + k * size)[0]
            tgt = (tab + v) if kind == "si" else (ret + 2 * v)
            if 0 <= tgt < len(self.rom):
                stack.append(tgt)
        for k in range(tab - ret + n * size):  # table bytes are data
            self.code[ret + k] = 0

    def offsets_value(self, pc, reg):
        """How code after `ldr reg,=lit` uses the loaded value:
        'imm' = adds a constant / loads at a non-zero displacement (GCC
                section anchor or struct field: lit is a base, not the data);
        'reg' = adds a register (array or string indexing);
        False = used as is."""
        regs = {reg}
        A = capstone.arm
        for _ in range(12):
            ins = next(self.md.disasm(self.rom[pc:pc + 4], 0x08000000 + pc, 1), None)
            if ins is None:
                return False
            m, ops = ins.mnemonic, ins.operands
            dst = ops[0].reg if ops and ops[0].type == A.ARM_OP_REG else None
            if m in ("adds", "add", "subs", "sub"):
                srcs = [o for o in ops[1:]] if len(ops) == 3 else ops
                uses = any(o.type == A.ARM_OP_REG and o.reg in regs for o in srcs)
                imm = [o.imm for o in ops[1:] if o.type == A.ARM_OP_IMM]
                regops = [o for o in ops[1:] if o.type == A.ARM_OP_REG and o.reg not in regs]
                if uses:
                    if imm and imm[0]:
                        return "imm"
                    if regops or (len(ops) == 2 and dst not in regs):
                        return "reg"
                    if imm and not imm[0]:          # adds rd, rn, #0 == mov
                        regs.add(dst)
                        pc += ins.size
                        continue
            if m in ("mov", "movs") and len(ops) == 2 and ops[1].type == A.ARM_OP_REG and ops[1].reg in regs:
                regs.add(dst)
                pc += ins.size
                continue
            mem = [o for o in ops if o.type == A.ARM_OP_MEM]
            if mem and mem[0].mem.base in regs and m.startswith(("ldr", "str")):
                if mem[0].mem.index:
                    return "reg"
                if mem[0].mem.disp:
                    return "imm"
            if m == "bl":
                regs -= {A.ARM_REG_R0, A.ARM_REG_R1, A.ARM_REG_R2, A.ARM_REG_R3}
            elif m in ("b", "bx", "pop") or m.startswith("b") and m not in ("bic", "bics"):
                return False
            elif dst in regs and m not in ("str", "strb", "strh", "cmp", "tst", "cmn", "push", "stm", "stmia"):
                regs.discard(dst)
            if not regs:
                return False
            pc += ins.size
        return False

    def jump_table(self, pc):
        """agbcc switch: lsls rI,rI,#2; ldr rT,=table; adds rI,rT; ldr rI,[rI];
        mov pc,rI. Only that exact shape is accepted; entries must lie close
        after the dispatch."""
        hw = [self.rom[pc - 2 * k] | self.rom[pc - 2 * k + 1] << 8 for k in range(1, 6)]
        # hw[0] = ldr rI,[rI,#0] (0x68xx), then adds (0x18xx), then ldr literal, then lsls #2
        if not (hw[0] >> 11 == 0b01101 and hw[1] >> 9 == 0b0001100 and hw[2] >> 11 == 0b01001
                and hw[3] >> 6 == 0b0000000010):
            return
        q = pc - 6
        lit = ((q + 4) & ~3) + (hw[2] & 0xFF) * 4
        t = struct.unpack_from("<I", self.rom, lit)[0] - 0x08000000
        if not (0 <= t - pc < 0x200):
            return
        for k in range(256):
            v = struct.unpack_from("<I", self.rom, t + 4 * k)[0]
            off = (v & ~1) - 0x08000000
            if not (self.in_rom(v) and 0 <= off - pc < 0x4000):
                break
            self.lit.setdefault(t + 4 * k, set())
            self.todo.append(off)

    def seeds(self):
        rom, base = self.rom, self.base
        a = np.frombuffer(rom, np.uint8)
        n = len(a) - 3
        al = np.arange(0, n, 4)
        u = (a[al].astype(np.uint32) | (a[al + 1].astype(np.uint32) << 8)
             | (a[al + 2].astype(np.uint32) << 16) | (a[al + 3].astype(np.uint32) << 24))
        odd = (u & 1).astype(bool) & (((u >> 24) == 8) | ((u >> 24) == 9))
        for o, v in zip(al[odd].tolist(), u[odd].tolist()):
            t = v - 0x08000001
            if t >= len(rom) - 2 or self.vanilla_code(t):
                continue
            first = rom[t + 1]
            if o < len(base) and self.fm.kind(o) == "code":
                continue  # inside code: literals are found by tracing
            if first in (0xB5, 0xB4) and self.plausible(t):
                self.add_func(t)

    def vanilla_seeds(self):
        """Thumb functions from the decomp symbol table (ARM-mode library
        code is skipped: it does not start with a Thumb push)."""
        for off, size, name in self.fm.syms:
            if self.fm.kind(off) == "code" and off % 2 == 0 and self.rom[off:off + 4] == self.base[off:off + 4]:
                if self.rom[off + 1] in (0xB5, 0xB4, 0xB0) or size:
                    self.add_func(off)

    def run(self):
        self.vanilla_seeds()
        self.seeds()
        while self.todo:
            self.trace(self.todo.pop())
        # literal words are data, not code
        for lit in self.lit:
            for k in range(4):
                if lit + k < len(self.code):
                    self.code[lit + k] = 0
        c = np.frombuffer(bytes(self.code), np.uint8)
        edges = np.flatnonzero(np.diff(np.concatenate(([0], c, [0]))))
        ranges = edges.reshape(-1, 2).tolist()
        out = {"code": ranges,
               "literals": {str(k): {"value": struct.unpack_from("<I", self.rom, k)[0],
                                     "uses": sorted(v), "anchor": self.anchor.get(k, False)}
                            for k, v in sorted(self.lit.items())},
               "funcs": sorted(self.funcs)}
        json.dump(out, open(OUT, "w"), separators=(",", ":"))
        print(f"{len(self.funcs)} funcs, {int(c.sum())} code bytes in {len(ranges)} ranges, "
              f"{len(self.lit)} literals ({len(self.anchor)} anchors), {self.bad} undecodable stops -> {OUT}")


class HackMap:
    def __init__(self, path=OUT):
        import bisect
        d = json.load(open(path))
        self._b = bisect
        self.ranges = d["code"]
        self.starts = [r[0] for r in self.ranges]
        self.literals = {int(k): v for k, v in d["literals"].items()}
        self.funcs = set(d["funcs"])

    def is_code(self, off):
        i = self._b.bisect_right(self.starts, off) - 1
        return i >= 0 and self.ranges[i][0] <= off < self.ranges[i][1]

    def literal(self, off):
        return self.literals.get(off)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        Mapper().run()
    else:
        hm = HackMap()
        for a in sys.argv[1:]:
            v = int(a, 16)
            off = v - 0x08000000 if v >= 0x08000000 else v
            print(f"{off:07X}: code={hm.is_code(off)} literal={hm.literal(off)}")
