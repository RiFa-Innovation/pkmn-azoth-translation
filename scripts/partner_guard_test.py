"""Partner guard test: relabel the walker's slot as an NPC (what a hijacked slot looks like), random-walk, and count how often the follower code still moves it.

    python3 scripts/partner_guard_test.py ROM.gba SAVE.sav [seed]      # scratch copies; v0.4.1 moves the slot (the bug), the guard build must report 'slot moved 0'

Needs a save with a partner walking behind the player. Battles are fled; taps where the slot was reused by a real NPC or the map changed are not asserted.
"""
import sys, os, struct as st, shutil, tempfile, random
sys.path.insert(0,'/Users/river/Projects/rht/scripts')
import play, mapdrive
from emu import Emu
from species_peek import to_overworld
rom,sav,seed=sys.argv[1],sys.argv[2],int(sys.argv[3]) if len(sys.argv)>3 else 1
random.seed(seed)
d=tempfile.mkdtemp(prefix="guard-")
shutil.copy(rom,d+"/game.gba"); shutil.copy(sav,d+"/game.sav")
os.environ["RHT_LOAD_SAVE"]="1"
play.stop(); play.boot(d+"/game.gba")
e=Emu(); e.wait(120); assert to_overworld(e); e.wait(300)
def ob(i): return e.read(0x02036E38+36*i,36)
def live(): return [(i,ob(i)) for i in range(16) if ob(i)[0]&1]
def pos(i): return st.unpack_from('<hh',ob(i),0x10)
def inbattle(): return bool(e.read(0x030030F0+0x439,1)[0]&2)
viol=[]; stats=dict(taps=0,battles=0,warps=0,inject=0,respawn_fail=0)
def check(tag):
    f=e.read(0x0203B818,2)
    if f[0]:
        o=ob(f[1]) if f[1]<16 else None
        ok=o is not None and (o[0]&1) and o[8]==0xFE
        if not ok: viol.append((tag,'follower idx not a live walker',f.hex(),(o[0]&1,o[8]) if o else None))
    n=sum(1 for i,o in live() if o[8]==0xFE)
    if n>1: viol.append((tag,'duplicate walkers',n))
def tap(b,w=18,hold=14): e.press(b,hold=hold,release=8); e.wait(w); stats['taps']+=1
def flee():
    for k in range(60):
        if not inbattle(): break
        for b in ('A','Down','Right','A','B'): e.press(b,hold=4,release=8); e.wait(40)
    e.wait(200)
    for k in range(30):
        if e.read(0x03000f9c,1)[0]==0: break
        e.press('B',hold=4,release=8); e.wait(40)
    return not inbattle()
def mapid():
    sb=st.unpack('<I',e.read(0x03005008,4))[0]; g,n=e.read(sb+4,2); return g,n
g,n=mapid(); idx=e.read(0x0203B818,2)[1]
e.write(0x02036E38+36*idx+8,bytes([0x21])); fixed=pos(idx); moved=0; reused=0; g_n=(g,n); last_pl=pos(0)
print('relabelled slot',idx,'at',fixed)
for k in range(220):
    if inbattle():
        stats['battles']+=1
        if not flee(): print('could not flee'); break
    tap(random.choice(['Up','Down','Left','Right']))
    o=ob(idx); mp=mapid(); pl=pos(0)
    if o[8]!=0x21 or mp!=g_n: reused+=1; fixed=pos(idx); g_n=mp; continue          # slot taken by a real NPC, or map changed: nothing to assert
    if pos(idx)!=fixed:
        d=(abs(pl[0]-last_pl[0])+abs(pl[1]-last_pl[1]))
        if d<=1: moved+=1                                                         # player moved one tile at most, so no connection shift: the object itself moved
        fixed=pos(idx)
    last_pl=pl
    if e.read(0x0203B818,2)[0]!=1: viol.append(('follower deactivated',k))
print(stats,'slot moved',moved,'reused/map-change taps',reused,'follower',e.read(0x0203B818,2).hex())
x,y=pos(0); mapdrive.warp(e,g,n,x,y,wait=200); e.wait(100)
print('after reload walker present:',any(o[8]==0xFE for i,o in live()),'follower',e.read(0x0203B818,8).hex())
print('violations',viol)
