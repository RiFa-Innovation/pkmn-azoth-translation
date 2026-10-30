"""Cheat Device: an in-game menu (SELECT + R in the overworld) with a few switches, in both editions.

    python3 scripts/cheats_build.py          # builds the natives standalone and prints the symbols

Called by insert.py (`apply(rom, src, pool)`), after the English text is in place. Everything lives in the free pool; the game code is
reached only through three patched literal-pool words and one patched instruction pair (every site asserts the original bytes):

  * 0x0806CACC  ProcessPlayerFieldInput's trampoline literal -> pfi_wrap (SELECT+R starts the menu script, else the hack's code)
  * 0x09D44884  the RemoveBagItem literal of the Rare Candy flow -> candy_wrap ("infinite Rare Candy")
  * 0x00015A68 / 0x00015B2C  gBattleMainFunc = ReturnFromBattleToOverworld -> heal_wrap ("heal after battle")
  * 0x09D09BC8  CreateBoxMon's player-OT branch -> shiny_stub ("shiny boost")
  * 0x0009CB58 / 0x0009CFD4  the multichoice table literal -> a copy of the table with one more list (the menu's)

Switches are hack flags 0x13A8-0x13AB (docs: CLAUDE.md "Reserved ids"); the menu script toggles them with the game's own setflag.
"""
import json
import os
import re
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mercury_text as mt  # noqa: E402
import scrasm  # noqa: E402

ROM_BASE = 0x08000000
FLAG_SHINY, FLAG_CANDY, FLAG_HEAL, FLAG_REPEL = 0x13A8, 0x13A9, 0x13AA, 0x13AB
FLAG_SHINY_RATE = 0x13AC              # 0x13AC-0x13AE: Shiny Boost rate index (bit 0..2), see SHINY_RATES
# (menu label, mask): shiny when (Random() & mask) == 0, i.e. 1 in mask+1 per player-OT creation while the switch is on; index 0 = the original 1 in 16
SHINY_RATES = [("1 in 16", 15), ("1 in 64", 63), ("1 in 256", 255), ("1 in 1024", 1023), ("1 in 4096", 4095), ("1 in 2", 1), ("Always", 0)]
MULTICHOICE_TABLE = 0x3E04B0          # vanilla sMultichoiceLists: 65 x {list ptr, count}; the hack leaves it and its two literals alone
MULTICHOICE_ENTRIES = 65
MENU_ID = MULTICHOICE_ENTRIES
RATE_MENU_ID = MULTICHOICE_ENTRIES + 1
RATE_MENU = ["Off"] + [label for label, _ in SHINY_RATES]
CFLAGS_AS = ["arm-none-eabi-as", "-mcpu=arm7tdmi"]

CAPS = json.load(open(os.path.join(ROOT, "data/cheats_levelcaps.json")))
assert len(CAPS["caps"]) == 9 and all(0 < c <= 100 for c in CAPS["caps"])
MENU = ["Shiny Boost", "Infinite Candy", "Heal After Fights", "Infinite Repel", "Heal Party Now", "99 Rare Candies", "Money +99999", "Set To Level Cap"]
assert len(RATE_MENU) <= 8 and len(MENU) <= 8, "the game's GetMCWindowHeight draws a 1-row window for a multichoice list of 9 or more entries (B closes the menu, there is no Close entry)"


def _build(base, out, script):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(os.path.join(os.path.dirname(out), "captable.inc"), "w").write(".byte " + ", ".join(str(c) for c in CAPS["caps"]) + "\n")
    obj = out + ".o"
    subprocess.check_call(CFLAGS_AS + ["-I", os.path.dirname(out), os.path.join(ROOT, "scripts/native/cheats.s"), "-o", obj,
                                       "--defsym", f"cheat_script={script:#x}", "--defsym", f"FLAG_SHINY={FLAG_SHINY:#x}",
                                       "--defsym", f"FLAG_CANDY={FLAG_CANDY:#x}", "--defsym", f"FLAG_HEAL={FLAG_HEAL:#x}", "--defsym", f"FLAG_REPEL={FLAG_REPEL:#x}",
                                       "--defsym", f"FLAG_SHINY_B0={FLAG_SHINY_RATE:#x}", "--defsym", f"FLAG_SHINY_B1={FLAG_SHINY_RATE + 1:#x}", "--defsym", f"FLAG_SHINY_B2={FLAG_SHINY_RATE + 2:#x}", "--defsym", f"BADGE_FLAG={int(CAPS['badge_flag'], 0):#x}"])
    elf = out + ".elf"
    subprocess.check_call(["arm-none-eabi-ld", f"-Ttext={base:#x}", "-e", "_start", "-o", elf, obj])
    subprocess.check_call(["arm-none-eabi-objcopy", "-O", "binary", elf, out])
    syms = {}
    for line in subprocess.check_output(["arm-none-eabi-nm", elf], text=True).splitlines():
        a, _, n = line.split()
        syms[n] = int(a, 16) & ~1
    return open(out, "rb").read(), syms


def _shiny_block():
    """Shiny Boost: pick Off or one of the odds in SHINY_RATES (second multichoice list); the odds are three flags (rate index)."""
    out = ["sw_shiny:", f"    multichoice 0 0 {RATE_MENU_ID} 0", "    compare_var_to_value 0x800D 0", "    goto_if 1 sh_off"]
    for k in range(1, len(RATE_MENU)):
        out += [f"    compare_var_to_value 0x800D {k}", f"    goto_if 1 sh_{k}"]
    out += ["    goto menu", "sh_off:", f"    clearflag {FLAG_SHINY:#x}", '    say "Shiny Boost is now OFF."', "    goto menu"]
    for k, (label, _) in enumerate(SHINY_RATES, 1):
        idx = k - 1
        out += [f"sh_{k}:", f"    setflag {FLAG_SHINY:#x}"]
        for bit in range(3):
            out.append(f"    {'setflag' if idx >> bit & 1 else 'clearflag'} {FLAG_SHINY_RATE + bit:#x}")
        out += [f'    say "Shiny Boost is ON: {label}."', "    goto menu"]
    return "\n        ".join(out)


def _script(labels):
    """The menu. Each switch asks with its current state; B ends."""
    def toggle(name, flag, title):
        return f"""
        {name}:
            checkflag {flag:#x}
            goto_if 1 {name}_on
            ask "{title} is OFF. Turn it ON?"
            compare_var_to_value 0x800D 0
            goto_if 1 menu
            setflag {flag:#x}
            say "{title} is now ON!"
            goto menu
        {name}_on:
            ask "{title} is ON. Turn it OFF?"
            compare_var_to_value 0x800D 0
            goto_if 1 menu
            clearflag {flag:#x}
            say "{title} is now OFF."
            goto menu"""
    return f"""
        start:
            lockall
        menu:
            multichoice 0 0 {MENU_ID} 0
            compare_var_to_value 0x800D 0
            goto_if 1 sw_shiny
            compare_var_to_value 0x800D 1
            goto_if 1 sw_candy
            compare_var_to_value 0x800D 2
            goto_if 1 sw_heal
            compare_var_to_value 0x800D 3
            goto_if 1 sw_repel
            compare_var_to_value 0x800D 4
            goto_if 1 heal_now
            compare_var_to_value 0x800D 5
            goto_if 1 give_candy
            compare_var_to_value 0x800D 6
            goto_if 1 give_money
            compare_var_to_value 0x800D 7
            goto_if 1 set_cap
            releaseall
            end
        {_shiny_block()}
        {toggle("sw_candy", FLAG_CANDY, "Infinite Candy")}
        {toggle("sw_heal", FLAG_HEAL, "Heal After Fights")}
        {toggle("sw_repel", FLAG_REPEL, "Infinite Repel")}
        heal_now:
            special 0x0
            playfanfare 0x100
            waitfanfare
            say "Your party was fully healed!"
            goto menu
        give_candy:
            additem 68 99
            say "You received 99 Rare Candies!"
            goto menu
        set_cap:
            special 0x9F
            waitstate
            compare_var_to_value 0x8004 6
            goto_if 4 menu
            callnative @cap_apply
            compare_var_to_value 0x800D 0
            goto_if 1 cap_done
            say "That Pokémon is already at or above the current level cap."
            goto menu
        cap_done:
            say "Raised to the current level cap!"
            goto menu
        give_money:
            addmoney 99999 0
            say "You received ¥99,999!"
            goto menu
    """


class _Any(dict):
    def __missing__(self, k):
        return 0


def apply(rom, src, pool):
    widths = bytes(src[mt.WIDTHS_OFF:mt.WIDTHS_OFF + 256])
    text = lambda b: ROM_BASE + _alloc(rom, pool, b)
    # 1. natives: placed first (the script calls cap_apply), relinked below once the script's address is known (same size)
    nat_path = os.path.join(ROOT, "build/cheats/native.bin")
    image, syms = _build(ROM_BASE, nat_path, 0)
    na = pool.alloc_aligned(len(image))
    syms = _build(ROM_BASE + na, nat_path, 0)[1]
    # 2. menu script
    code_src = _script(None)
    size = len(scrasm.assemble(code_src, 0, widths, _Any(), lambda b: 0))
    at = pool.alloc_aligned(size)
    code = scrasm.assemble(code_src, ROM_BASE + at, widths, {"cap_apply": syms["cap_apply"] | 1}, text)
    assert len(code) == size
    rom[at:at + size] = code
    script = ROM_BASE + at
    # 3. multichoice table: the vanilla one plus the menu's list (id MENU_ID)
    labels = b"".join(struct.pack("<II", ROM_BASE + _alloc(rom, pool, mt.encode_en(m)), 0) for m in MENU)
    la = pool.alloc_aligned(len(labels))
    rom[la:la + len(labels)] = labels
    rl = b"".join(struct.pack("<II", ROM_BASE + _alloc(rom, pool, mt.encode_en(m)), 0) for m in RATE_MENU)
    ra = pool.alloc_aligned(len(rl))
    rom[ra:ra + len(rl)] = rl
    tbl = (bytes(src[MULTICHOICE_TABLE:MULTICHOICE_TABLE + 8 * MULTICHOICE_ENTRIES]) + struct.pack("<II", ROM_BASE + la, len(MENU))
           + struct.pack("<II", ROM_BASE + ra, len(RATE_MENU)))
    ta = pool.alloc_aligned(len(tbl))
    rom[ta:ta + len(tbl)] = tbl
    for lit in (0x9CB58, 0x9CFD4):
        assert src[lit:lit + 4] == (ROM_BASE + MULTICHOICE_TABLE).to_bytes(4, "little"), hex(lit)
        rom[lit:lit + 4] = (ROM_BASE + ta).to_bytes(4, "little")
    # 4. relink the natives with the real script address
    image, syms = _build(ROM_BASE + na, nat_path, script)
    rom[na:na + len(image)] = image
    fn = lambda n: syms[n] | 1

    def lit(off, old, new):
        assert src[off:off + 4] == old.to_bytes(4, "little"), f"cheats: bytes at {off:#x} differ"
        rom[off:off + 4] = new.to_bytes(4, "little")

    lit(0x6CACC, 0x09D320B1, fn("pfi_wrap"))                 # ProcessPlayerFieldInput trampoline literal
    lit(0x1D44884, 0x0809A1D9, fn("candy_wrap"))             # Rare Candy flow's RemoveBagItem
    lit(0x15A68, 0x08015B59, fn("heal_wrap"))                # gBattleMainFunc = ReturnFromBattleToOverworld
    lit(0x15B2C, 0x08015B59, fn("heal_wrap"))
    # CreateBoxMon: 0x09D09BC8 `ldr r3,[pc,#364]; ldr r2,[r3]; ldrh r3,[r2,#12]; ldrh r1,[r2,#10]; lsls r3,#16; orrs r3,r1; b -> str r3,[sp,#20]`
    site = 0x1D09BC8
    assert src[site:site + 4] == bytes.fromhex("5b4b1a68") and src[site + 12:site + 14] == bytes.fromhex("f6e7"), "cheats: CreateBoxMon site differs"
    rom[site:site + 4] = bytes.fromhex("004b1847")            # ldr r3,[pc,#0] ; bx r3
    rom[site + 4:site + 8] = fn("shiny_stub").to_bytes(4, "little")
    return {"script": script, "native": len(image), "table": ROM_BASE + ta, "bytes": size + len(image) + len(tbl) + len(labels) + len(rl)}


def _alloc(rom, pool, b):
    a = pool.alloc(len(b))
    rom[a:a + len(b)] = b
    return a


if __name__ == "__main__":
    image, syms = _build(0x08F00000, os.path.join(ROOT, "build/cheats/native.bin"), 0x08F10000)
    print(len(image), "bytes", {k: hex(v) for k, v in syms.items() if k.endswith(("_wrap", "_stub"))})
