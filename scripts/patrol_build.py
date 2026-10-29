"""Partner Patrol (River Edition only; docs/PARTNER_PATROL_SPEC.md): SELECT in Quick Catch sends the walking partner at the aimed target.

    python3 scripts/patrol_build.py          # builds the natives standalone and prints the symbols

Called by insert.py (`apply(rom, src, pool)`) for the River Edition, after the Cheat Device (if any). Everything lives in the free pool; the game is
reached through one patched literal: the ProcessPlayerFieldInput trampoline literal at 0x0806CACC, whose current value (the hack's code, or the
Cheat Device's wrapper) becomes the patrol wrapper's "next". M1 (the instant strike): scripts/native/patrol.s + patrol.c.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mercury_text as mt  # noqa: E402
import scrasm  # noqa: E402

ROM_BASE = 0x08000000
PFI_LITERAL = 0x6CACC
HOLD_LITERALS = (0x1D32424, 0x1D3367C)      # the follower code's ObjectEventSetHeldMovement literals (idle each frame, follow step)
CFLAGS = ["-mcpu=arm7tdmi", "-mthumb", "-Os", "-ffreestanding", "-fno-builtin", "-fno-strict-aliasing", "-fno-stack-protector", "-fno-pic",
          "-fno-asynchronous-unwind-tables", "-fno-unwind-tables", "-fno-tree-loop-distribute-patterns", "-Wall", "-Wextra"]

TEST_FLAGS = {"shiny": ["-DFORCE_SHINY"], "retreat": ["-DFORCE_RETREAT"], "held": ["-DFORCE_HELD"]}.get(os.environ.get("RHT_PATROL_TEST", ""), [])   # scratch ROMs for the shiny/retreat branches

SCRIPT = """
    start:
        compare_var_to_value 0x8004 1
        goto_if 1 won
        compare_var_to_value 0x8004 2
        goto_if 1 retreat
        compare_var_to_value 0x8004 3
        goto_if 1 shiny
        compare_var_to_value 0x8004 4
        goto_if 1 hurt
        compare_var_to_value 0x8004 5
        goto_if 1 unreachable
        releaseall
        end
    won:
        bufferpartymonnick 0 0x8006
        bufferspeciesname 1 0x8007
        buffernumberstring 2 0x8005
        say "{FD:02} beat {FD:03}! It gained {FD:04} EXP."
        compare_var_to_value 0x8000 0
        goto_if 1 drop_a
        buffernumberstring 2 0x8000
        say "{FD:02} grew to Lv. {FD:04}!"
        compare_var_to_value 0x8001 0
        goto_if 1 drop_a
        buffermovename 1 0x8001
        say "{FD:02} learned {FD:03}!"
        compare_var_to_value 0x8002 0
        goto_if 1 drop_a
        buffermovename 1 0x8002
        say "{FD:02} learned {FD:03}!"
    drop_a:
        compare_var_to_value 0x8008 0
        goto_if 1 drop_b
        bufferitemname 1 0x8008
        buffernumberstring 2 0x8009
        compare_var_to_value 0x8009 0
        goto_if 1 drop_a_full
        say "Found {FD:03} x{FD:04}!"
        goto drop_b
    drop_a_full:
        say "No room in the bag for {FD:03}!"
        goto drop_b
    drop_b:
        compare_var_to_value 0x800A 0
        goto_if 1 drop_c
        bufferitemname 1 0x800A
        buffernumberstring 2 0x800B
        compare_var_to_value 0x800B 0
        goto_if 1 drop_b_full
        say "Found {FD:03} x{FD:04}!"
        goto drop_c
    drop_b_full:
        say "No room in the bag for {FD:03}!"
        goto drop_c
    drop_c:
        compare_var_to_value 0x800C 0
        goto_if 1 won_done
        bufferspeciesname 1 0x8007
        bufferitemname 2 0x800C
        say "The wild {FD:03} was holding {FD:04}!"
    won_done:
        callnative @patrol_remove
        releaseall
        end
    retreat:
        bufferpartymonnick 0 0x8006
        bufferspeciesname 1 0x8007
        say "{FD:02} was beaten up by {FD:03} and came back."
        releaseall
        end
    shiny:
        bufferpartymonnick 0 0x8006
        bufferspeciesname 1 0x8007
        say "Wait! This {FD:03} is shiny! {FD:02} holds it still for you."
        dowildbattle
        callnative @patrol_remove
        releaseall
        end
    unreachable:
        bufferpartymonnick 0 0x8006
        bufferspeciesname 1 0x8007
        say "{FD:02} couldn't get close to {FD:03}."
        releaseall
        end
    hurt:
        bufferpartymonnick 0 0x8006
        say "{FD:02} is too hurt to fight. Heal up first."
        releaseall
        end
"""


class _Any(dict):
    def __missing__(self, k):
        return 0


def _fix_scrasm_ops():
    """scrasm's table lacks the string-variable byte of two buffer commands (opcode, byte out, u16 value)."""
    o = scrasm.ops()
    o["bufferpartymonnick"] = (127, [("byte", 1), ("2byte", 1)])
    o["bufferspeciesname"] = (125, [("byte", 1), ("2byte", 1)])
    o["buffermovename"] = (130, [("byte", 1), ("2byte", 1)])


def _build(base, out, script, nxt):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    objs = []
    for name, cmd in (("asm", ["arm-none-eabi-as", "-mcpu=arm7tdmi", os.path.join(ROOT, "scripts/native/patrol.s")]),
                      ("c", ["arm-none-eabi-gcc", *CFLAGS, *TEST_FLAGS, "-c", os.path.join(ROOT, "scripts/native/patrol.c")])):
        obj = f"{out}.{name}.o"
        subprocess.check_call(cmd + ["-o", obj])
        objs.append(obj)
    elf = out + ".elf"
    subprocess.check_call(["arm-none-eabi-ld", f"-Ttext={base:#x}", "-e", "_start", f"--defsym=patrol_script={script:#x}", f"--defsym=patrol_next={nxt:#x}",
                           "-o", elf, *objs])
    subprocess.check_call(["arm-none-eabi-objcopy", "-O", "binary", elf, out])
    syms = {}
    for line in subprocess.check_output(["arm-none-eabi-nm", elf], text=True).splitlines():
        parts = line.split()
        if len(parts) == 3:
            syms[parts[2]] = int(parts[0], 16) & ~1
    return open(out, "rb").read(), syms


def apply(rom, src, pool):
    _fix_scrasm_ops()
    widths = bytes(src[mt.WIDTHS_OFF:mt.WIDTHS_OFF + 256])
    cur = int.from_bytes(rom[PFI_LITERAL:PFI_LITERAL + 4], "little")
    assert ROM_BASE <= cur < 0x0A000000 and cur & 1, f"patrol: unexpected ProcessPlayerFieldInput literal {cur:#x}"
    path = os.path.join(ROOT, "build/patrol/native.bin")
    image, syms = _build(ROM_BASE, path, 0, cur)
    na = pool.alloc_aligned(len(image))
    syms = _build(ROM_BASE + na, path, 0, cur)[1]
    text = lambda b: ROM_BASE + _alloc(rom, pool, b)
    ext = {"patrol_remove": syms["patrol_remove"] | 1}
    size = len(scrasm.assemble(SCRIPT, 0, widths, _Any(), lambda b: 0))
    sa = pool.alloc_aligned(size)
    code = scrasm.assemble(SCRIPT, ROM_BASE + sa, widths, ext, text)
    assert len(code) == size
    rom[sa:sa + size] = code
    image, syms = _build(ROM_BASE + na, path, ROM_BASE + sa, cur)
    rom[na:na + len(image)] = image
    rom[PFI_LITERAL:PFI_LITERAL + 4] = (syms["patrol_pfi"] | 1).to_bytes(4, "little")
    for lit in HOLD_LITERALS:
        assert src[lit:lit + 4] == (0x08063CA5).to_bytes(4, "little"), f"patrol: unexpected follower literal at {lit:#x}"
        rom[lit:lit + 4] = (syms["patrol_hold_wrap"] | 1).to_bytes(4, "little")
    return {"script": ROM_BASE + sa, "native": len(image), "wrapper": syms["patrol_pfi"] | 1, "next": cur}


def _alloc(rom, pool, b):
    a = pool.alloc(len(b))
    rom[a:a + len(b)] = b
    return a


if __name__ == "__main__":
    image, syms = _build(0x08F00000, os.path.join(ROOT, "build/patrol/native.bin"), 0x08F10000, 0x09D320B1)
    print(len(image), "bytes", {k: hex(v) for k, v in syms.items() if k.startswith("patrol")})
