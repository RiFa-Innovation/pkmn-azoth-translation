import os, shutil, struct, sys, tempfile
sys.path.insert(0, "/Users/river/Projects/rht/scripts")
import play
from emu import Emu
S = os.path.dirname(os.path.abspath(__file__))
CB2, CTX, RUNNING = 0x030030F4, 0x03000EB0, 0x03000EA8
CODE, SCRIPT = 0x0203FC00, 0x0203FF00
u32 = lambda e, a: struct.unpack("<I", e.read(a, 4))[0]
scratch = tempfile.mkdtemp(prefix="s3-")
shutil.copy("build/Mercury_EN.gba", f"{scratch}/game.gba")
shutil.copy(os.environ.get("SAV","saves/playtest-2026-10-10.sav"), f"{scratch}/game.sav")
os.environ["RHT_LOAD_SAVE"] = "1"
play.stop()
play.boot(f"{scratch}/game.gba")
e = Emu(); e.wait(120)
for _ in range(60):
    if u32(e, CB2) == play.OVERWORLD_CB2:
        e.wait(30); break
    e.press("A", hold=3, release=6); e.wait(40)
else:
    sys.exit("no overworld")
print("overworld; party count", e.read(0x02024029, 1)[0], "exp slot0", u32(e, 0x02024284 + 0x20 - 0x00))
e.write(CODE, open(f"{S}/stub.bin", "rb").read())
sc = bytes([0x23]) + struct.pack("<I", CODE | 1) + bytes([0x27, 0x02])
e.write(SCRIPT, sc)
e.write(CTX + 8, struct.pack("<I", SCRIPT)); e.write(CTX, b"\x00\x01"); e.write(RUNNING, bytes(4))
print('code readback',e.read(CODE,8).hex(),'script',e.read(SCRIPT,8).hex(),'ctx',e.read(CTX,16).hex())
for k in range(40):
    e.wait(4)
    print(k,"flags",hex(u32(e,0x02022B4C)),"cb2",hex(u32(e,CB2)),"opp",hex(u32(e,0x0203F45C)),"tt?",hex(u32(e,0x02023e8a)))
