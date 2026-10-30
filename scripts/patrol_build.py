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

TEST_FLAGS = {"shiny": ["-DFORCE_SHINY"], "retreat": ["-DFORCE_RETREAT"], "held": ["-DFORCE_HELD"], "nohurt": ["-DFORCE_NOHURT"]}.get(os.environ.get("RHT_PATROL_TEST", ""), [])   # scratch ROMs for the shiny/retreat branches

SCRIPT = """
    start:
        callnative @patrol_sum_step
        compare_var_to_value 0x800D 0
        goto_if 1 after
        compare_var_to_value 0x800D 1
        goto_if 1 line_header
        compare_var_to_value 0x800D 2
        goto_if 1 line_level
        compare_var_to_value 0x800D 3
        goto_if 1 line_move
        compare_var_to_value 0x800D 4
        goto_if 1 line_item
        compare_var_to_value 0x800D 5
        goto_if 1 line_noroom
        goto start
    line_header:
        bufferpartymonnick 0 0x8006
        buffernumberstring 1 0x8005
        buffernumberstring 2 0x8001
        say "{FD:02} beat {FD:03} Pokémon and gained {FD:04} EXP!"
        goto start
    line_level:
        bufferpartymonnick 0 0x8006
        buffernumberstring 2 0x8002
        say "{FD:02} grew to Lv. {FD:04}!"
        goto start
    line_move:
        bufferpartymonnick 0 0x8006
        buffermovename 1 0x8003
        say "{FD:02} learned {FD:03}!"
        goto start
    line_item:
        bufferitemname 1 0x8008
        buffernumberstring 2 0x8009
        say "Found {FD:03} x{FD:04}!"
        goto start
    line_noroom:
        bufferitemname 1 0x8008
        say "No room in the bag for {FD:03}!"
        goto start
    after:
        checkflag 0x13B3
        goto_if 1 after_tip
        setflag 0x13B3
        say "Tip: press B while your partner is out to call it back. Hold L and R and press SELECT to change the Partner Patrol settings."
    after_tip:
        compare_var_to_value 0x8004 3
        goto_if 1 shiny
        compare_var_to_value 0x8004 2
        goto_if 1 worn_out
        compare_var_to_value 0x8004 4
        goto_if 1 hurt
        compare_var_to_value 0x8004 5
        goto_if 1 unreachable
        compare_var_to_value 0x8004 7
        goto_if 1 no_walker
        goto finish
    no_walker:
        say "Nobody is walking behind you. Put a Pokémon out to walk first, then try again."
        releaseall
        end
    worn_out:
        bufferpartymonnick 0 0x8006
        say "{FD:02} is worn out and came back."
        goto finish
    unreachable:
        bufferpartymonnick 0 0x8006
        bufferspeciesname 1 0x8007
        say "{FD:02} couldn't get close to {FD:03}."
        goto finish
    hurt:
        bufferpartymonnick 0 0x8006
        say "{FD:02} is too hurt to fight. Heal up first."
        goto finish
    finish:
        callnative @patrol_learn_next
        compare_var_to_value 0x800D 1
        goto_if 1 learn_ask
        goto evolve
    learn_ask:
        bufferpartymonnick 0 0x8006
        buffermovename 1 0x8003
        ask "{FD:02} wants to learn {FD:03}, but it already knows four moves. Make it forget a move?"
        compare_var_to_value 0x800D 1
        goto_if 1 learn_pick
        goto learn_giveup
    learn_pick:
        callnative @patrol_learn_open
        waitstate
        callnative @patrol_learn_apply
        compare_var_to_value 0x800D 1
        goto_if 1 learn_done
        bufferpartymonnick 0 0x8006
        buffermovename 1 0x8003
        ask "Stop trying to teach {FD:03}?"
        compare_var_to_value 0x800D 1
        goto_if 1 learn_giveup
        goto learn_pick
    learn_done:
        bufferpartymonnick 0 0x8006
        buffermovename 1 0x8002
        buffermovename 2 0x8003
        say "1, 2 and... Poof! {FD:02} forgot {FD:03}. And... {FD:02} learned {FD:04}!"
        goto finish
    learn_giveup:
        bufferpartymonnick 0 0x8006
        buffermovename 1 0x8003
        say "{FD:02} did not learn {FD:03}."
        callnative @patrol_learn_skip
        goto finish
    evolve:
        callnative @patrol_evolve
        compare_var_to_value 0x800D 1
        goto_if 1 evolving
        releaseall
        end
    evolving:
        waitstate
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
"""


SETTINGS = """
    start:
        checkflag 0x13B0
        goto_if 1 is_off
        ask "Partner Patrol is ON. Turn it OFF?"
        compare_var_to_value 0x800D 1
        goto_if 1 turn_off
        goto size
    is_off:
        ask "Partner Patrol is OFF. Turn it ON?"
        compare_var_to_value 0x800D 1
        goto_if 1 turn_on
        goto done
    turn_off:
        setflag 0x13B0
        say "Partner Patrol is now OFF."
        goto done
    turn_on:
        clearflag 0x13B0
        say "Partner Patrol is now ON."
    size:
        checkflag 0x13B2
        goto_if 1 is_long
        checkflag 0x13B1
        goto_if 1 is_short
        ask "Patrol size: NORMAL (up to 10 Pokémon within 12 tiles). Make it LONG?"
        compare_var_to_value 0x800D 1
        goto_if 1 make_long
        goto done
    is_long:
        ask "Patrol size: LONG (up to 20 Pokémon within 16 tiles). Make it SHORT?"
        compare_var_to_value 0x800D 1
        goto_if 1 make_short
        goto done
    is_short:
        ask "Patrol size: SHORT (up to 4 Pokémon within 8 tiles). Make it NORMAL?"
        compare_var_to_value 0x800D 1
        goto_if 1 make_normal
        goto done
    make_long:
        setflag 0x13B2
        say "Patrol size is now LONG."
        goto done
    make_short:
        clearflag 0x13B2
        setflag 0x13B1
        say "Patrol size is now SHORT."
        goto done
    make_normal:
        clearflag 0x13B1
        say "Patrol size is now NORMAL."
    done:
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


def _build(base, out, script, nxt, settings=0):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    objs = []
    for name, cmd in (("asm", ["arm-none-eabi-as", "-mcpu=arm7tdmi", os.path.join(ROOT, "scripts/native/patrol.s")]),
                      ("c", ["arm-none-eabi-gcc", *CFLAGS, *TEST_FLAGS, "-c", os.path.join(ROOT, "scripts/native/patrol.c")])):
        obj = f"{out}.{name}.o"
        subprocess.check_call(cmd + ["-o", obj])
        objs.append(obj)
    elf = out + ".elf"
    subprocess.check_call(["arm-none-eabi-ld", f"-Ttext={base:#x}", "-e", "_start", f"--defsym=patrol_script={script:#x}", f"--defsym=patrol_settings={settings:#x}", f"--defsym=patrol_next={nxt:#x}",
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
    ext = {"patrol_remove": syms["patrol_remove"] | 1, "patrol_sum_step": syms["patrol_sum_step"] | 1, "patrol_evolve": syms["patrol_evolve"] | 1,
           "patrol_learn_next": syms["patrol_learn_next"] | 1, "patrol_learn_open": syms["patrol_learn_open"] | 1,
           "patrol_learn_apply": syms["patrol_learn_apply"] | 1, "patrol_learn_skip": syms["patrol_learn_skip"] | 1}
    size = len(scrasm.assemble(SCRIPT, 0, widths, _Any(), lambda b: 0))
    sa = pool.alloc_aligned(size)
    code = scrasm.assemble(SCRIPT, ROM_BASE + sa, widths, ext, text)
    assert len(code) == size
    rom[sa:sa + size] = code
    ssize = len(scrasm.assemble(SETTINGS, 0, widths, _Any(), lambda b: 0))
    ta = pool.alloc_aligned(ssize)
    scode = scrasm.assemble(SETTINGS, ROM_BASE + ta, widths, {}, text)
    assert len(scode) == ssize
    rom[ta:ta + ssize] = scode
    image, syms = _build(ROM_BASE + na, path, ROM_BASE + sa, cur, ROM_BASE + ta)
    rom[na:na + len(image)] = image
    rom[PFI_LITERAL:PFI_LITERAL + 4] = (syms["patrol_pfi"] | 1).to_bytes(4, "little")
    for lit in HOLD_LITERALS:
        assert src[lit:lit + 4] == (0x08063CA5).to_bytes(4, "little"), f"patrol: unexpected follower literal at {lit:#x}"
        rom[lit:lit + 4] = (syms["patrol_hold_wrap"] | 1).to_bytes(4, "little")
    return {"script": ROM_BASE + sa, "settings": ROM_BASE + ta, "native": len(image), "wrapper": syms["patrol_pfi"] | 1, "next": cur}


def _alloc(rom, pool, b):
    a = pool.alloc(len(b))
    rom[a:a + len(b)] = b
    return a


if __name__ == "__main__":
    image, syms = _build(0x08F00000, os.path.join(ROOT, "build/patrol/native.bin"), 0x08F10000, 0x09D320B1)
    print(len(image), "bytes", {k: hex(v) for k, v in syms.items() if k.startswith("patrol")})
