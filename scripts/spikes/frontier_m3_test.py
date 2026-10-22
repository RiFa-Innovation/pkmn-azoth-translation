"""M3 test: fr_enter / fr_leave on a real save in the emulator (scratch copy, the .sav is never touched).

    python3 scripts/spikes/frontier_m3_test.py "saves/gets_frozen_after fight_and_convo/Azoth.sav" [ROM]

Run from the main checkout (it needs utilities/mgba and saves/). Builds the natives (scripts/frontier_native.py) at 0x0203EC00, injects it into EWRAM
and drives it through `callnative`, decoding the party in Python to verify slot order, Lv 50 stats (formula checked against the game's own
stats at the real level first), the 6-slot save round trip, restoration and idempotence.
"""
import os
import shutil
import struct
import sys
import tempfile

MAIN = "/Users/river/Projects/rht"
RIVER = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{MAIN}/scripts")
sys.path.insert(0, f"{RIVER}/scripts")
import play  # noqa: E402
from emu import Emu  # noqa: E402
import frontier_native as fn  # noqa: E402

BASE = 0x0203EC00
SCRIPT = 0x0203FF00
CTX, RUNNING, CB2 = 0x03000EB0, 0x03000EA8, 0x030030F4
PARTY, COUNT, SPV = 0x02024284, 0x02024029, 0x020370B8
RES = SPV + 0x18
ORDER = ["GAEM", "GAME", "GEAM", "GEMA", "GMAE", "GMEA", "AGEM", "AGME", "AEGM", "AEMG", "AMGE", "AMEG", "EGAM", "EGMA", "EAGM", "EAMG",
         "EMGA", "EMAG", "MGAE", "MGEA", "MAGE", "MAEG", "MEGA", "MEAG"]
ROM_BASESTATS = 0x176DFBC
fails = []


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def decode(b):
    """This hack stores party mons UNENCRYPTED with the substructures in fixed GAEM order and a zero checksum (verified on Azoth.sav)."""
    pers = struct.unpack_from("<I", b, 0)[0]
    sub = {c: bytes(b[32 + 12 * k:32 + 12 * k + 12]) for k, c in enumerate("GAEM")}
    species, item, exp = struct.unpack_from("<HHI", sub["G"], 0)
    evs = list(sub["E"][:6])
    ivw = struct.unpack_from("<I", sub["M"], 4)[0]
    ivs = [(ivw >> (5 * i)) & 31 for i in range(6)]
    moves = struct.unpack_from("<4H", sub["A"], 0)
    pp = list(sub["A"][8:12])
    level, mail, hp, mhp, atk, df, spe, spa, spd = struct.unpack_from("<BBHHHHHHH", b, 0x54)
    return dict(pers=pers, species=species, item=item, exp=exp, evs=evs, ivs=ivs, moves=moves, pp=pp, level=level, hp=hp,
                stats=[mhp, atk, df, spe, spa, spd], nature=pers % 25)


def formula(rom, d, level):
    base = rom[ROM_BASESTATS + 28 * d["species"]: ROM_BASESTATS + 28 * d["species"] + 6]   # hp atk def spe spa spd
    out = []
    n = d["nature"]
    for i in range(6):
        t = ((2 * base[i] + d["ivs"][i] + d["evs"][i] // 4) * level) // 100
        if i == 0:
            out.append(1 if d["species"] == 292 else t + level + 10)
        else:
            t += 5
            inc, dec = n // 5 + 1, n % 5 + 1
            if inc != dec:
                if i == inc:
                    t = t * 110 // 100
                elif i == dec:
                    t = t * 90 // 100
            out.append(t)
    return out


def main():
    sav = sys.argv[1]
    rom_path = sys.argv[2] if len(sys.argv) > 2 else f"{MAIN}/build/Mercury_EN.gba"
    blob, _ = fn.build(BASE, f"{RIVER}/build/frontier/native.bin")
    rom = open(rom_path, "rb").read()
    scratch = tempfile.mkdtemp(prefix="m3-")
    shutil.copy(rom_path, f"{scratch}/game.gba")
    shutil.copy(sav, f"{scratch}/game.sav")
    os.environ["RHT_LOAD_SAVE"] = "1"
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
    else:
        sys.exit("no overworld")
    e.wait(150)
    e.write(BASE, blob)

    def run(addr, **v):
        """Inject `callnative addr; copyvar 0x8008 <- Result; end` (the game zeroes Result when a script ends, so the script keeps a copy)
        and wait until the copy changes from its sentinel. The overworld's own scripts can clobber the context right after a map
        load, so retry a few times."""
        V8, RESULT_VAR = SPV + 16, 0x800D
        for attempt in range(6):
            for k, val in v.items():
                e.write(SPV + 2 * int(k[1:]), struct.pack("<H", val))
            e.write(V8, struct.pack("<H", 0xBEEF))
            code = bytes([0x23]) + struct.pack("<I", addr | 1) + bytes([0x19]) + struct.pack("<HH", 0x8008, RESULT_VAR) + bytes([0x02])
            e.write(SCRIPT, code)
            e.write(CTX + 8, struct.pack("<I", SCRIPT))
            e.write(CTX, b"\x00\x01")
            e.write(RUNNING, bytes(4))
            e.wait(30)
            if struct.unpack("<H", e.read(V8, 2))[0] != 0xBEEF:
                break
        else:
            raise RuntimeError("the injected script never ran")
        return struct.unpack("<H", e.read(V8, 2))[0], struct.unpack("<H", e.read(SPV + 10, 2))[0], struct.unpack("<H", e.read(SPV + 12, 2))[0]

    def party():
        b = e.read(PARTY, 600)
        return b, e.read(COUNT, 1)[0], [b[i * 100:(i + 1) * 100] for i in range(6)]

    orig, cnt0, mons0 = party()
    print("party count", cnt0)
    d0 = [decode(m) for m in mons0[:cnt0]]
    for i, d in enumerate(d0):
        print(" ", i, "species", d["species"], "Lv", d["level"], "stats", d["stats"], "hp", d["hp"], "nature", d["nature"], "pp", d["pp"])
    # A. formula = the game's own numbers at the real level
    for i, d in enumerate(d0):
        check(formula(rom, d, d["level"]) == d["stats"], f"A formula matches the game for slot {i} at Lv {d['level']}")
    assert cnt0 >= 4, "need a party of 4+"
    # F. error cases leave the party untouched
    for name, args, want in (("duplicate pick", dict(v0=2, v1=1, v2=1), 2), ("pick beyond party", dict(v0=2, v1=0, v2=9), 1),
                             ("zero picks", dict(v0=0), 1), ("five picks", dict(v0=5, v1=0, v2=1, v3=2, v4=3), 1)):
        res, lo, hi = run(BASE + 0, **args)
        b, c, _ = party()
        check(res == want and b == orig and c == cnt0, f"F {name}: result {res} (want {want}), untouched={b == orig and c == cnt0}")
    # B. singles: picks slots 2 and 0 (n=2)
    res, lo, hi = run(BASE + 0, v0=2, v1=2, v2=0)
    b, c, mons = party()
    check(res == 0, f"B fr_enter ok (perm LO={lo:#06x} HI={hi:#06x})")
    check(c == 2, f"B party count is 2 (got {c})")
    check(mons[0][:80] == mons0[2][:80] and mons[1][:80] == mons0[0][:80], "B picks moved to the front in pick order")
    # the unpicked mons are hidden from the party menu: species cleared, the real species parked in the HP field
    ok = True
    for slot, orig in ((2, 1), (3, 3)):
        d = decode(mons[slot])
        ok &= d["species"] == 0
        # only the species and the has-species flag (byte 19) differ; the species travels in the script vars 0x8009..0x800B
        ok &= all(mons[slot][i] == mons0[orig][i] for i in range(100) if i not in (19, 32, 33))
    parked = [struct.unpack("<H", e.read(SPV + 18 + 2 * k, 2))[0] for k in range(3)]
    ok &= parked == [d0[1]["species"], d0[3]["species"], 0]
    ok &= mons[4:] == mons0[4:]
    if not ok:
        for slot, orig in ((2, 1), (3, 3)):
            diff = [(i, mons0[orig][i], mons[slot][i]) for i in range(100) if mons[slot][i] != mons0[orig][i]]
            print("   slot", slot, "differs from original at (offset, was, now):", diff[:12], "decoded species", decode(mons[slot])["species"], "hp", decode(mons[slot])["hp"], "orig species", d0[orig]["species"])
    check(ok, "B the unpicked mons are hidden (species 0) and otherwise untouched")
    for i in (0, 1):
        d = decode(mons[i])
        check(d["level"] == 50, f"B slot {i} is Lv 50")
        want = formula(rom, d, 50)
        check(d["stats"] == want, f"B slot {i} stats equal the Lv 50 formula {want} (got {d['stats']})")
        check(d["hp"] == d["stats"][0], f"B slot {i} is at full HP")
    # C. save round trip with count 2 (all six slots must survive)
    snap, scnt, _ = party()
    run(0x0804C1F0)                                         # SavePlayerParty
    e.write(PARTY, bytes(600))
    e.write(COUNT, b"\x00")
    run(0x0804C230)                                         # LoadPlayerParty
    b2, c2, _ = party()
    check(b2 == snap and c2 == scnt, "C SavePlayerParty / LoadPlayerParty keeps all six slots and the truncated count")
    # D. restore
    res, lo2, hi2 = run(BASE + fn.ENTRY_STRIDE, v5=lo, v6=hi, v9=parked[0], v10=parked[1], v11=parked[2])
    b3, c3, mons3 = party()
    check(res == 0 and hi2 == 0, f"D fr_leave ok, marker cleared (HI={hi2:#06x})")
    check(c3 == cnt0, f"D party count restored to {cnt0} (got {c3})")
    for i in range(cnt0):
        a, d = d0[i], decode(mons3[i])
        same = all(a[k] == d[k] for k in ("pers", "species", "item", "exp", "evs", "ivs", "moves", "level", "stats"))
        check(same, f"D slot {i} back in its original place with the original level, stats, EXP, EVs, IVs and moves")
        check(d["hp"] == d["stats"][0], f"D slot {i} healed")
        diff = [(j, mons0[i][j], mons3[i][j]) for j in range(80) if mons3[i][j] != mons0[i][j]]
        if diff:
            print("   slot", i, "box bytes that differ after fr_leave (offset, was, now):", diff[:10])
        check(mons3[i][19] == mons0[i][19] and mons3[i][:80] == mons0[i][:80] or all(mons3[i][j] == mons0[i][j] for j in range(80) if not (12 <= j - 20 < 12)), f"D slot {i} box data (incl. the has-species flag) is back to the original")
    # E. idempotent
    res, _, hi3 = run(BASE + fn.ENTRY_STRIDE, v5=lo, v6=0, v9=parked[0], v10=parked[1], v11=parked[2])
    b4, c4, _ = party()
    check(res == 0 and b4 == b3 and c4 == c3, "E a second fr_leave (marker clear) changes nothing")
    # doubles: four picks in reverse order, then leave
    res, lo, hi = run(BASE + 0, v0=4, v1=3, v2=2, v3=1, v4=0)
    parked4 = [struct.unpack("<H", e.read(SPV + 18 + 2 * k, 2))[0] for k in range(3)]
    b5, c5, mons5 = party()
    check(res == 0 and c5 == 4, "G doubles: four picks accepted, count 4")
    check(all(decode(mons5[i])["level"] == 50 for i in range(4)), "G all four at Lv 50")
    run(BASE + fn.ENTRY_STRIDE, v5=lo, v6=hi, v9=parked4[0], v10=parked4[1], v11=parked4[2])
    b6, c6, mons6 = party()
    check(c6 == cnt0 and all(decode(mons6[i])["species"] == d0[i]["species"] for i in range(cnt0)), "G order restored after a reversed 4-pick run")
    play.stop()
    shutil.rmtree(scratch, ignore_errors=True)
    print("\nFAILED: %d" % len(fails) if fails else "\nall checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
