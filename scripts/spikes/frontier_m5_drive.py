"""M5 driver: boot the built ROM with a save, warp into the Frontier hall and play through the facility with button presses.

    python3 scripts/spikes/frontier_m5_drive.py SAVE "STEPS" [--rom build/Mercury_EN.gba] [--out DIR] [--vars]

STEPS is a space-separated list; each token is a button (A B Up Down Left Right Start), `wN` to wait N frames, `sN` to press A N times (60-frame gap),
`shot` to screenshot, `warpG.N,X,Y` to warp, `var:0x5122` to print a hack variable, `party` to print the party (species, level), `state` to
print the Frontier state. A grid of all screenshots goes to OUT/drive_grid.png. Run from the main checkout.
"""
import argparse
import os
import shutil
import struct
import sys
import tempfile

MAIN = "/Users/river/Projects/rht"
RIVER = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{MAIN}/scripts")
import play  # noqa: E402
from emu import Emu  # noqa: E402

CTX, RUNNING, CB2 = 0x03000EB0, 0x03000EA8, 0x030030F4
SCRIPT = 0x0203FF00
SPV = 0x020370B8
VAR_BASE = 0x2039374        # hack var v lives at 0x2039374 + (v - 0x4000) * 2
PARTY, COUNT = 0x02024284, 0x02024029
VARS = dict(MODE=0x5121, STATE=0x5122, STREAK=0x5123, SEED_LO=0x5124, SEED_HI=0x5125, PICK0=0x5126, PERM_LO=0x512A, PERM_HI=0x512B,
            BP=0x512C, BEST_S=0x512D, BEST_D=0x512E)


def u16(e, a):
    return struct.unpack("<H", e.read(a, 2))[0]


def hackvar(e, v):
    return u16(e, VAR_BASE + (v - 0x4000) * 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sav")
    ap.add_argument("steps")
    ap.add_argument("--rom", default=f"{RIVER}/build/Mercury_EN.gba")
    ap.add_argument("--out", default="/tmp/m5")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix="m5-")
    shutil.copy(a.rom, f"{scratch}/game.gba")
    shutil.copy(a.sav, f"{scratch}/game.sav")
    os.environ["RHT_LOAD_SAVE"] = "1"
    if "watch:" in a.steps:
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
    shots = []

    def shot(tag=""):
        f = f"{a.out}/d{len(shots):03d}{tag}.png"
        e.screenshot(f)
        shots.append(f)

    def inject(code):
        for _ in range(5):
            e.write(SCRIPT, code)
            e.write(CTX + 8, struct.pack("<I", SCRIPT))
            e.write(CTX, b"\x00\x01")
            e.write(RUNNING, bytes(4))
            e.wait(30)
            if e.read(CTX + 8, 4) != struct.pack("<I", SCRIPT):
                return
    for tok in a.steps.split():
        if tok in ("A", "B", "Up", "Down", "Left", "Right", "Start", "Select"):
            e.press(tok, hold=3, release=6)
            e.wait(24)
        elif tok.startswith("w") and tok[1:].isdigit():
            e.wait(int(tok[1:]))
        elif tok.startswith("s") and tok[1:].isdigit():
            for _ in range(int(tok[1:])):
                e.press("A", hold=3, release=6)
                e.wait(60)
        elif tok.startswith("sv:"):              # read a script special var 0x8000 + N
            nidx = int(tok[3:], 0)
            print(f"   special var {0x8000 + nidx:#x} = {u16(e, SPV + 2 * nidx)}", "result", u16(e, SPV + 0x18))
        elif tok == "cursor":
            print("   party cursor slotId", struct.unpack("<b", e.read(0x0203B0A0 + 9, 1))[0], "raw gPartyMenu", e.read(0x0203B0A0, 20).hex(), "cb2", hex(struct.unpack("<I", e.read(CB2, 4))[0]))
        elif tok.startswith("hijack:"):          # while a battle runs, point the paused script at `goto <generated script>` so it resumes there
            import json
            addr = int(json.load(open(f"{RIVER}/build/insert_report.json"))["new_maps"]["frontier"]["scripts"][tok[7:]], 16)
            for _ in range(80):
                if struct.unpack("<I", e.read(CB2, 4))[0] == 0x08011101:
                    break
                e.wait(15)
            else:
                print("   hijack: never saw the battle")
            e.write(SCRIPT, bytes([0x05]) + struct.pack("<I", addr))
            e.write(CTX + 8, struct.pack("<I", SCRIPT))
            print("   hijacked the paused script ->", tok[7:])
        elif tok.startswith("give:"):            # give one of each item id in A-B (fills the Bag pockets) with the game's own additem
            a_, b_ = (int(v) for v in tok[5:].split("-"))
            code = b"".join(bytes([0x44]) + struct.pack("<HH", i, 1) for i in range(a_, b_ + 1)) + bytes([0x02])
            e.write(0x0203F000, code)
            inject(bytes([0x05]) + struct.pack("<I", 0x0203F000))
            e.wait(60)
        elif tok.startswith("flag:"):             # set a story flag with the game's own setflag
            fl = int(tok[5:], 0)
            inject(bytes([0x29]) + struct.pack("<H", fl) + bytes([0x02]))
        elif tok == "block":                      # the generated opponent block in RAM: species, level, item, moves
            n = hackvar(e, VARS["MODE"])
            cnt = 4 if n == 2 else 3
            blk = e.read(0x02022400, 16 * cnt)
            print("   opponent block:", [(struct.unpack_from("<H", blk, 16 * i + 4)[0], blk[16 * i + 2], struct.unpack_from("<H", blk, 16 * i + 6)[0]) for i in range(cnt)])
        elif tok.startswith("climb:"):            # smart lazy player: climb:N[:until=0x5123=14][:strong][:stop0]
            parts = tok[6:].split(":")
            nmax = int(parts[0])
            opts = parts[1:]
            until = next((o[6:] for o in opts if o.startswith("until=")), None)
            for it in range(nmax):
                if "strong" in opts:             # raise the generated opponent: legendary at Lv 100 with strong attacks
                    for i in range(4):
                        base = 0x02022400 + 16 * i
                        e.write(base + 2, bytes([100]))
                        e.write(base + 4, struct.pack("<H", 150))
                        e.write(base + 8, struct.pack("<4H", 94, 247, 58, 85))
                if "stop0" in opts and hackvar(e, VARS["STATE"]) == 0:
                    print("   challenge ended (STATE 0) after", it, "iterations")
                    break
                if until:
                    vv, val = until.split("=")[0:2] if until.count("=") == 1 else (until.split("=")[0], until.split("=")[1])
                    if hackvar(e, int(vv, 0)) == int(val, 0):
                        print("   reached", until, "after", it, "iterations")
                        break
                cb = struct.unpack("<I", e.read(CB2, 4))[0]
                if cb == 0x08137EE9:
                    e.press("B", hold=3, release=6)
                    e.wait(40)
                elif cb == 0x0811EBA1 and e.read(COUNT, 1)[0]:
                    cnt = e.read(COUNT, 1)[0]
                    hp = [u16(e, PARTY + 100 * i + 0x56) for i in range(cnt)]
                    alive = [i for i in range(cnt) if hp[i] > 0]
                    if not alive:
                        e.press("B", hold=3, release=6)
                        e.wait(40)
                        continue
                    t = alive[0]
                    for _ in range(14):
                        c = struct.unpack("<b", e.read(0x0203B0A0 + 9, 1))[0]
                        if c == t:
                            break
                        key = "Down" if c // 2 < t // 2 else "Up" if c // 2 > t // 2 else "Right" if c % 2 < t % 2 else "Left"
                        e.press(key, hold=3, release=6)
                        e.wait(12)
                    e.press("A", hold=3, release=6)
                    e.wait(25)
                    e.press("A", hold=3, release=6)
                    e.wait(60)
                else:
                    e.press("A", hold=3, release=6)
                    e.wait(50)
            else:
                print("   climb loop used all", nmax, "iterations")
        elif tok.startswith("pick:"):            # in the party menu: move the cursor (gPartyMenu.slotId at +9) to slot N and press A
            t = int(tok[5:])
            for _ in range(60):                  # wait until the party menu is up, then let it settle
                if struct.unpack("<I", e.read(CB2, 4))[0] == 0x0811EBA1:
                    break
                e.wait(10)
            e.wait(40)
            for _ in range(14):
                c = struct.unpack("<b", e.read(0x0203B0A0 + 9, 1))[0]
                if c == t:
                    break
                key = "Down" if c // 2 < t // 2 else "Up" if c // 2 > t // 2 else "Right" if c % 2 < t % 2 else "Left"
                e.press(key, hold=3, release=6)
                e.wait(12)
            e.press("A", hold=3, release=6)
            e.wait(60)
        elif tok.startswith("lose:"):          # lazy fight with the generated opponent raised to Lv 100 (poked into the RAM party block) until STATE becomes 0
            k = 0
            for it in range(int(tok[5:])):
                for i in range(4):
                    e.write(0x02022402 + 16 * i, bytes([100]))
                if os.environ.get("WEAK"):                # keep the player's picks at 1 HP so the fight is lost for sure
                    for i in range(3):
                        e.write(PARTY + 100 * i + 0x56, struct.pack("<H", 1))
                if hackvar(e, VARS["STATE"]) == 0:
                    print("   challenge ended after", it, "iterations")
                    break
                cb = struct.unpack("<I", e.read(CB2, 4))[0]
                if cb == 0x08137EE9:                      # wandered into the Summary screen: back out
                    e.press("B", hold=3, release=6)
                    e.wait(40)
                    continue
                if cb == 0x0811EBA1 and e.read(COUNT, 1)[0]:
                    e.press(["Right", "Down", "Right", "Right"][k % 4], hold=3, release=6)
                    e.wait(10)
                    k += 1
                    e.press("A", hold=3, release=6)
                    e.wait(25)
                    e.press("A", hold=3, release=6)
                    e.wait(60)
                else:
                    e.press("A", hold=3, release=6)
                    e.wait(50)
        elif tok.startswith("until:"):         # until:0x5123=14:200 -> lazy fight until the hack var has that value (or N iterations)
            spec_, nmax = tok[6:].rsplit(":", 1)
            vv, val = spec_.split("=")
            k = 0
            for it in range(int(nmax)):
                if hackvar(e, int(vv, 0)) == int(val, 0):
                    print("   reached", spec_, "after", it, "iterations")
                    break
                cb = struct.unpack("<I", e.read(CB2, 4))[0]
                if cb == 0x08137EE9:                      # wandered into the Summary screen: back out
                    e.press("B", hold=3, release=6)
                    e.wait(40)
                    continue
                if cb == 0x0811EBA1 and e.read(COUNT, 1)[0]:
                    e.press(["Right", "Down", "Right", "Right"][k % 4], hold=3, release=6)
                    e.wait(10)
                    k += 1
                    e.press("A", hold=3, release=6)
                    e.wait(25)
                    e.press("A", hold=3, release=6)
                    e.wait(60)
                else:
                    e.press("A", hold=3, release=6)
                    e.wait(50)
            else:
                print("   did NOT reach", spec_)
        elif tok.startswith("fight"):         # lazy player: A through everything, and in the forced-switch party screen pick the next slot
            n = int(tok[5:] or 40)
            order = ["Right", "Down", "Right", "Right"]
            k = 0
            for it in range(n):
                cb = struct.unpack("<I", e.read(CB2, 4))[0]
                if cb == 0x08137EE9:                      # wandered into the Summary screen: back out
                    e.press("B", hold=3, release=6)
                    e.wait(40)
                    continue
                if cb == 0x0811EBA1 and e.read(COUNT, 1)[0]:
                    e.press(order[k % len(order)], hold=3, release=6)
                    e.wait(10)
                    k += 1
                    e.press("A", hold=3, release=6)
                    e.wait(25)
                    e.press("A", hold=3, release=6)
                    e.wait(60)
                else:
                    e.press("A", hold=3, release=6)
                    e.wait(50)
                if it % 10 == 9:
                    print("   fight", it + 1, {k_: hackvar(e, v) for k_, v in VARS.items() if k_ in ("STATE", "STREAK", "BP")}, "cb2", hex(cb))
        elif tok == "shot":
            shot()
        elif tok.startswith("warp"):
            gn, x, y = tok[4:].split(",")
            g, n = (int(v) for v in gn.split("."))
            inject(bytes([0x39, g, n, 0xFF]) + struct.pack("<HH", int(x), int(y)) + bytes([0x27, 0x02]))
            e.wait(120)
        elif tok.startswith("goto:"):            # jump into a generated script by name (addresses from build/insert_report.json)
            import json
            addr = int(json.load(open(f"{RIVER}/build/insert_report.json"))["new_maps"]["frontier"]["scripts"][tok[5:]], 16)
            inject(bytes([0x05]) + struct.pack("<I", addr))
            e.wait(60)
        elif tok.startswith("setvar:"):          # poke a hack variable: setvar:0x5123=6
            vv, val = tok[7:].split("=")
            e.write(VAR_BASE + (int(vv, 0) - 0x4000) * 2, struct.pack("<H", int(val, 0)))
        elif tok.startswith("var:"):
            v = int(tok[4:], 0)
            print(f"var {v:#x} = {hackvar(e, v)}")
        elif tok.startswith("watch:"):          # arm a write watchpoint (needs RHT_DEBUGGER=1 at boot)
            ad = int(tok[6:], 0)
            e.call("watch_read", min=ad, max=ad + 1, write=True)
        elif tok == "wlog":
            for ent in e.call("watch_log"):
                print("   write pc", hex(ent["pc"]), "lr", hex(ent["lr"]), "r0", hex(ent["r0"]), "r1", hex(ent["r1"]), "r2", hex(ent["r2"]), "frame", ent["frame"])
        elif tok == "enemy1":                     # every enemy-party mon to 1 HP (win a brain fight quickly)
            for i in range(6):
                e.write(0x0202402C + 100 * i + 0x56, struct.pack("<H", 1))
            print("   enemy party species:", [struct.unpack_from("<H", e.read(0x0202402C + 100 * i + 32, 2))[0] for i in range(6)])
        elif tok == "ctx":                        # script context: mode bytes and the script pointer (where is a stalled script?)
            print("   ctx mode", e.read(CTX, 2).hex(), "scriptPtr", hex(struct.unpack("<I", e.read(CTX + 8, 4))[0]), "running", e.read(RUNNING, 1).hex())
        elif tok == "state":
            print({k: hackvar(e, v) for k, v in VARS.items()}, "cb2", hex(struct.unpack("<I", e.read(CB2, 4))[0]), "party count", e.read(COUNT, 1)[0])
        elif tok == "party":
            b = e.read(PARTY, 600)
            print("party:", [(struct.unpack_from("<H", b, 100 * i + 32)[0], b[100 * i + 0x54], struct.unpack_from("<H", b, 100 * i + 0x56)[0]) for i in range(6)], "count", e.read(COUNT, 1)[0])
        else:
            raise SystemExit(f"unknown step {tok}")
    if shots:
        from PIL import Image
        ims = [Image.open(f) for f in shots[:24]]
        w, h = ims[0].size
        cols = 4
        rows = (len(ims) + cols - 1) // cols
        c = Image.new("RGB", (w * cols, h * rows))
        for i, im in enumerate(ims):
            c.paste(im, ((i % cols) * w, (i // cols) * h))
        c.save(f"{a.out}/drive_grid.png")
        print("grid:", f"{a.out}/drive_grid.png", len(ims), "shots")
    play.stop()
    if not a.keep:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
