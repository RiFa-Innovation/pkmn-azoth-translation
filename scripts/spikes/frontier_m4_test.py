"""M4 probes: does CFRU build the enemy party from a shell trainer slot whose party pointer is in EWRAM, and what happens on a win, a loss and in doubles?

    python3 scripts/spikes/frontier_m4_test.py [singles|loss|doubles] "saves/gets_frozen_after fight_and_convo/Azoth.sav"

Run from the main checkout. Builds scripts/frontier_start.s at 0x0203F900, patches trainer slot 459 of a scratch ROM copy so its party pointer is
0x02022400 (the scratch block), writes the party into that block from Python (the real fr_gen_opponent will do it natively), and starts the battle.
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

MAIN = "/Users/river/Projects/rht"
RIVER = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{MAIN}/scripts")
sys.path.insert(0, f"{RIVER}/scripts")
import play  # noqa: E402
from emu import Emu  # noqa: E402

SHELL = int(os.environ.get("SHELL_ID", "459"))
SPEECH_ENTRY = 0x1DEC3A0     # first entry of the orphaned Battle Tower trainer table (52 bytes): words 0/1/2 = intro / player-won / player-lost speech
TEXT_BUF = 0x02022600
TRAINER_TABLE = 0x23EACC - 4
BLOCK = 0x02022400
BASE, SCRIPT = 0x0203F900, 0x0203FF00
CTX, RUNNING, CB2 = 0x03000EB0, 0x03000EA8, 0x030030F4
SPV = 0x020370B8
OUT = os.environ.get("OUT", "/tmp")


def build_stub():
    out = f"{RIVER}/build/frontier/start.bin"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.check_call(["arm-none-eabi-as", "-mcpu=arm7tdmi", "--defsym", "START_FLAGS=" + ("0x8" if os.environ.get("HYBRID") else "0x108"), f"{RIVER}/scripts/frontier_start.s", "-o", out + ".o"])
    subprocess.check_call(["arm-none-eabi-ld", f"-Ttext={BASE:#x}", "-e", "_start", "-o", out + ".elf", out + ".o"])
    subprocess.check_call(["arm-none-eabi-objcopy", "-O", "binary", out + ".elf", out])
    return open(out, "rb").read()


def enc_name(s):
    t = {}
    for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        t[c] = 0xBB + i
    for i, c in enumerate("abcdefghijklmnopqrstuvwxyz"):
        t[c] = 0xD5 + i
    return bytes(t.get(c, 0) for c in s) + b"\xff"


def patch_rom(path, double, nmons, ai=7):
    rom = bytearray(open(path, "rb").read())
    o = TRAINER_TABLE + 40 * SHELL
    ent = struct.pack("<BBBB", 3, 9, 0x0A, 30) + enc_name("Shell").ljust(12, b"\x00") + struct.pack("<4HIIII", 0, 0, 0, 0, 1 if double else 0, ai, nmons, BLOCK)
    assert len(ent) == 40
    if os.environ.get("CLONE"):          # copy another trainer's record (class, music, pic, name, items, ai) and keep only partyFlags/size/pointer ours
        src = TRAINER_TABLE + 40 * int(os.environ["CLONE"])
        ent = bytes([3]) + bytes(rom[src + 1:src + 24]) + struct.pack("<I", 1 if double else 0) + bytes(rom[src + 28:src + 32]) + struct.pack("<II", nmons, BLOCK)
        ent = bytes(ent)
    rom[o:o + 40] = ent
    # speech entry for the shell: words 0/1/2 (intro, defeat, lose) -> strings in EWRAM
    so = SPEECH_ENTRY
    if os.environ.get("MARKERS"):
        rom[so:so + 28] = struct.pack("<7I", *[TEXT_BUF + 0x40 * k for k in range(7)])
    else:
        rom[so:so + 12] = struct.pack("<III", TEXT_BUF, TEXT_BUF + 0x80, TEXT_BUF + 0x100)
    open(path, "wb").write(rom)


def party_block(mons):
    """16-byte entries: u16 iv, u8 level, u8 pad, u16 species, u16 item, u16 moves[4]."""
    b = b""
    for sp, lv, item, moves in mons:
        b += struct.pack("<HBBHH4H", 31, lv, 0, sp, item, *(list(moves) + [0] * 4)[:4])
    return b


def main():
    mode = sys.argv[1]
    sav = sys.argv[2]
    dbl = mode == "doubles"
    # species (national dex ids), moves (ids): Venusaur, Gengar, Alakazam; Lv 50 for singles/doubles, Lv 100 for the loss probe
    lv = 100 if mode == "loss" else 50
    mons = [(3, lv, 200, (76, 188, 79, 89)), (94, lv, 0, (247, 188, 85, 94)), (65, lv, 0, (94, 247, 85, 347)), (6, lv, 0, (53, 17, 89, 76))]
    n = 4 if dbl else 3
    sys.path.insert(0, f"{MAIN}/scripts")
    blob = build_stub()
    scratch = tempfile.mkdtemp(prefix="m4-")
    shutil.copy(os.environ.get("ROM", f"{MAIN}/build/Mercury_EN.gba"), f"{scratch}/game.gba")
    shutil.copy(sav, f"{scratch}/game.sav")
    if not os.environ.get("NOPATCH"):
        patch_rom(f"{scratch}/game.gba", dbl, n)
    os.environ["RHT_LOAD_SAVE"] = "1"
    if os.environ.get("BREAK") or os.environ.get("EXPANDBP") or os.environ.get("WATCHSTR"):
        os.environ["RHT_DEBUGGER"] = "1"
    os.chdir(MAIN)
    play.stop()
    play.boot(f"{scratch}/game.gba")
    e = Emu()
    e.wait(120)
    for _ in range(60):
        if struct.unpack("<I", e.read(CB2, 4))[0] == play.OVERWORLD_CB2:
            e.wait(30)
            break
        e.press("A", hold=3, release=6)
        e.wait(40)
    e.wait(150)
    e.write(BASE, blob)
    if os.environ.get("BREAK"):
        e.call("break_at", address=0x08002CF4)
    if os.environ.get("EXPANDBP"):
        e.call("break_at", address=int(os.environ["EXPANDBP"], 0))
    if os.environ.get("WATCHSTR"):
        e.call("watch_read", min=0x0202298C, max=0x0202298F, write=True)
    e.write(BLOCK, party_block(mons[:n]))
    sys.path.insert(0, f"{MAIN}/scripts")
    import mercury_text as mt
    if os.environ.get("MARKERS"):
        for k in range(7):
            e.write(TEXT_BUF + 0x40 * k, mt.encode_en(f"MARKER WORD {k}"))
    for off, text in (() if os.environ.get("MARKERS") else ((0, "Hello, I am the Shell. Welcome!\nLet us begin."), (0x80, "You beat the Shell.\nWell fought!"), (0x100, "The Shell wins.\nBetter luck next time."))):
        e.write(TEXT_BUF + off, mt.encode_en(text))
    if mode == "loss":                      # only the lead is alive, so its faint is a lost battle (no party-menu navigation needed)
        for i in (1, 2, 3):
            e.write(0x02024284 + 100 * i + 0x56, struct.pack("<H", 0))
    if os.environ.get("SPEECHPTRS"):          # engine speech pointers used for trainer intro / defeat text
        e.write(0x020386B4, struct.pack("<I", TEXT_BUF))              # sTrainerAIntroSpeech
        e.write(0x020386B8, struct.pack("<I", TEXT_BUF + 0x80))       # sTrainerADefeatSpeech
    if os.environ.get("DUMPPTRS"):
        w = struct.unpack("<8I", e.read(0x020386AC, 32))
        print("   static trainer-speech vars 0x020386AC..:", [hex(x) for x in w])
    e.write(SPV, struct.pack("<HH", SHELL, 1 if dbl else 0))
    HYBRID = bool(os.environ.get("HYBRID"))
    if os.environ.get("CLEARFLAG"):      # make an NPC trainer fightable again: trainer flag = 0x500 + id (SaveBlock1 + 0xEE0 + flag / 8)
        fid = 0x500 + int(os.environ["CLEARFLAG"])
        sb1 = struct.unpack("<I", e.read(0x03005008, 4))[0]
        addr = sb1 + 0xEE0 + fid // 8
        e.write(addr, bytes([e.read(addr, 1)[0] & ~(1 << (fid & 7)) & 0xFF]))
    if os.environ.get("SCRIPTSTART"):
        # the game's own trainerbattle (type 0, single trainer): u8 type, u16 trainer, u16 local id, u32 intro text, u32 defeat text
        e.write(TEXT_BUF, mt.encode_en("Welcome to the tower! I am the Shell.\nLet us begin."))
        e.write(TEXT_BUF + 0x80, mt.encode_en("You beat the Shell.\nWell fought!"))
        e.write(SCRIPT, bytes([0x5C, 0x00]) + struct.pack("<HHII", SHELL, 0, TEXT_BUF, TEXT_BUF + 0x80) + bytes([0x02]))
    else:
        e.write(SCRIPT, bytes([0x23]) + struct.pack("<I", BASE | 1) + bytes([0x27, 0x02]))
    e.write(CTX + 8, struct.pack("<I", SCRIPT))
    e.write(CTX, b"\x00\x01")
    e.write(RUNNING, bytes(4))
    e.wait(400)
    en = e.read(0x0202402C, 600)
    species = [struct.unpack_from("<H", en, 100 * i + 32)[0] for i in range(6)]
    levels = [en[100 * i + 0x54] for i in range(6)]
    print("flags", hex(struct.unpack("<I", e.read(0x02022B4C, 4))[0]), "opponent id", struct.unpack("<H", e.read(0x020386AE, 2))[0])
    print("enemy species", species, "levels", levels)
    shots = []
    PARTY_CB2 = 0x0811EBA1
    pidx = 0
    tower_bit_set = False
    for k in range(120 if mode != "singles" else 14):
        cb = struct.unpack("<I", e.read(CB2, 4))[0]
        if HYBRID and not tower_bit_set and struct.unpack("<I", e.read(0x03004F84, 4))[0] == 0x08014041:
            fl = struct.unpack("<I", e.read(0x02022B4C, 4))[0]
            e.write(0x02022B4C, struct.pack("<I", fl | 0x100))
            tower_bit_set = True
            print("   action menu reached at step", k, "-> flags", hex(fl | 0x100))
        if cb == PARTY_CB2:
            # party menu: move down to the next slot and send it out (the fainted ones are refused)
            pidx = (pidx + 1) % 4
            for _ in range(pidx):
                e.press("Down", hold=3, release=6)
                e.wait(6)
            e.press("A", hold=3, release=6)
            e.wait(20)
            e.press("A", hold=3, release=6)
            e.wait(40)
            e.press("Up", hold=3, release=6)
            e.wait(10)
        else:
            if os.environ.get("EVERY"):
                e.screenshot(f"{OUT}/m4_{mode}_pre{k:03d}.png")
            if os.environ.get("DUMPSTR") and k < 4:
                import mercury_text as mt2
                raw = e.read(0x0202298C, 300)
                r = mt2.decode_vanilla(raw, 0)
                print("   gDisplayedStringBattle:", repr((r[0] if isinstance(r, tuple) else r)[:200]))
            e.press("A", hold=3, release=6)
            e.wait(60)
        if k % 3 == 2 or os.environ.get("EVERY"):
            f = f"{OUT}/m4_{mode}_{k:03d}.png"
            e.screenshot(f)
            shots.append(f)
        if mode in ("loss", "doubles") and cb == play.OVERWORLD_CB2 and k > 6:
            print("back on the overworld after", k, "steps; battle outcome", e.read(0x02023E8A, 1)[0])
            break
    if os.environ.get("WATCHSTR"):
        import mercury_text as mt
        rom_b = open(f"{MAIN}/build/Mercury_EN.gba", "rb").read()
        for ent in e.call("watch_log"):
            regs = {k: ent[k] for k in ("r0", "r1", "r2", "r3", "r4", "r5", "pc", "lr")}
            srcs = []
            for k in ("r1", "r2", "r3", "r4", "r5"):
                v = regs[k]
                if 0x08000000 <= v < 0x0A000000:
                    try:
                        r = mt.decode_vanilla(rom_b, v & 0x1FFFFFF)
                        srcs.append((k, hex(v), (r[0] if isinstance(r, tuple) else r)[:50]))
                    except Exception:
                        pass
            print("   write@2022 98c", hex(regs["pc"]), "lr", hex(regs["lr"]), srcs)
    if os.environ.get("EXPANDBP"):
        import mercury_text as mt
        rom_b = open(f"{MAIN}/build/Mercury_EN.gba", "rb").read()
        for ent in e.call("watch_log"):
            row = []
            for k in ("r0", "r1", "r2", "r3"):
                v = ent[k]
                if 0x08000000 <= v < 0x0A000000:
                    try:
                        r = mt.decode_vanilla(rom_b, v & 0x1FFFFFF)
                        row.append((k, hex(v), (r[0] if isinstance(r, tuple) else r)[:50]))
                    except Exception:
                        pass
            print("   expand call lr", hex(ent["lr"]), "r0", hex(ent["r0"]), "r2", hex(ent["r2"]), row)
    if os.environ.get("BREAK"):
        sys.path.insert(0, f"{MAIN}/scripts")
        import mercury_text as mt
        for ent in e.call("watch_log"):
            if "text" in ent:
                raw = bytes(ent["text"])
                try:
                    r = mt.decode_vanilla(raw + b"\xff", 0)
                    r = r[0] if isinstance(r, tuple) else r
                except Exception:
                    r = raw.hex()
                print(f"   AddTextPrinter pc={ent['pc']:#x} lr={ent['lr']:#x} text@{ent['cur']:#010x}: {r!r}")
    e.wait(60)
    e.screenshot(f"{OUT}/m4_{mode}_end.png")
    print("cb2", hex(struct.unpack("<I", e.read(CB2, 4))[0]), "player count", e.read(0x02024029, 1)[0], "outcome", e.read(0x02023E8A, 1)[0])
    play.stop()
    shutil.rmtree(scratch, ignore_errors=True)
    open(f"{OUT}/m4_{mode}_shots.txt", "w").write("\n".join(shots + [f"{OUT}/m4_{mode}_end.png"]))


if __name__ == "__main__":
    main()
