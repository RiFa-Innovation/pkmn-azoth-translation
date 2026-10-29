"""Insert English text into the patched Mercury ROM and build the BPS patch.

Inputs:
  text/zh.json                 dump (scripts/dump_all.py)
  text/en/tables/<name>.json   {index: english}   fixed-stride name tables
  text/en/strings*.json        {chinese: english} translation memory

Strings that fit are written in place; the rest go to free space and every
trusted reference is repointed. Originals with only trusted refs (and no other
string inside them) are recycled as free space.

Outputs: build/Mercury_EN.gba, build/Mercury_EN.bps (applies to clean FR 1.0),
         build/insert_report.json
"""
import array
import bisect
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bps  # noqa: E402
import edition  # noqa: E402
import layout  # noqa: E402
import mercury_text as mt  # noqa: E402
import gfx_text  # noqa: E402
import logo  # noqa: E402
import mapedit  # noqa: E402
import maptext  # noqa: E402
import sprtext  # noqa: E402
import statusicons  # noqa: E402
import typeicons  # noqa: E402
import anchored  # noqa: E402
import cheats_build  # noqa: E402
import patrol_build  # noqa: E402

BASE = "roms/Pokemon - FireRed Version (USA, Europe).gba"
PATCHED = "roms/Pokemon Mercury 1.3.3 (patched).gba"
DIALOGUE_KINDS = ("loadpointer", "message", "trainerbattle")
DIALOGUE_PX = 198  # 204 collided with the {FA}/{FB} arrow
MOVE_DESC_PX = 112  # move description box (summary / learn screen), 4 lines
MOVE_DESC_TABLE, MOVE_DESC_COUNT = 0x1CC8EB0, 1273
ITEM_DESC_PX = 176  # bag description box: starts after the item icon, ends before the arrow
HELP_PX = 222
MIN_FREE_RUN = 512
NAMING_DISPATCH = "002813d0052811d2f0b5474680b488460006070e1204150c1b041e0c0a4cf22040010a4b00f00ef80949084700900948f7b51e0008ab1d780748084b01911700074c2047184700008c9903029d2b000873d90908b55eff0918270000b12b0008c55eff09"  # data/naming_dispatch.s (arm-none-eabi-as -mthumb; objcopy -O binary)
FREE_MARGIN = 16


def load_tm():
    tm = {}
    for path in sorted(glob.glob("text/en/strings*.json")):
        tm.update(json.load(open(path, encoding="utf-8")))
    return tm


def src_max_px(zh, widths):
    best = 0
    for line in re.split(r"\n|\{FA\}|\{FB\}", zh):
        line = re.sub(r"\{[^}]*\}", "", line)
        px = sum(mt.HANZI_PX if ord(c) >= 0x3000 else 6 for c in line)
        best = max(best, px)
    return best


FF_KEEP_BEFORE, FF_KEEP_AFTER = 16, 256  # window kept around a table pointer's target


def referenced_ff(rom):
    """[start, end) spans of 0xFF runs the hack reads as data, never free space."""
    runs = [(m.start(), m.end()) for m in re.finditer(rb"\xff{%d,}" % MIN_FREE_RUN, rom)]
    starts = [s for s, _ in runs]

    def run_of(off):
        i = bisect.bisect_right(starts, off) - 1
        return runs[i] if i >= 0 and off < runs[i][1] else None

    out = []
    lits = json.load(open("data/hack_code.json"))["literals"].values()
    for v in lits:
        r = run_of((v["value"] & ~1) - 0x08000000) if 0x08000000 <= v["value"] < 0x0A000000 else None
        if r:
            out.append(r)
    words = array.array("I", rom[:len(rom) // 4 * 4])
    isptr = [0x08000000 <= w < 0x0A000000 for w in words]
    for i, w in enumerate(words):
        if not isptr[i] or not ((i and isptr[i - 1]) or (i + 1 < len(words) and isptr[i + 1])):
            continue
        t = (w & ~1) - 0x08000000
        r = run_of(t)
        if r:
            out.append((max(r[0], t - FF_KEEP_BEFORE), min(r[1], t + FF_KEEP_AFTER)))
    return out


class FreePool:
    def __init__(self, rom):
        self.runs = []
        for m in re.finditer(rb"\xff{%d,}" % MIN_FREE_RUN, rom):
            self.runs.append([m.start() + FREE_MARGIN, m.end()])

    def add(self, start, end):
        if end - start >= 8:
            self.runs.append([start, end])

    def alloc(self, n):
        best = None
        for r in self.runs:  # best fit
            if r[1] - r[0] >= n and (best is None or r[1] - r[0] < best[1] - best[0]):
                best = r
        if best is None:
            raise MemoryError(f"no free space for {n} bytes")
        a = best[0]
        best[0] += n
        return a

    def reserve(self, start, end):
        """Never hand out [start, end) (in-place text lives there)."""
        out = []
        for a, b in self.runs:
            if b <= start or a >= end:
                out.append([a, b])
                continue
            if a < start:
                out.append([a, start])
            if b > end:
                out.append([end, b])
        self.runs = out

    def alloc_aligned(self, n, align=4):
        a = self.alloc(n + align - 1)
        pad = -a % align
        self.add(a + pad + n, a + n + align - 1)  # give back the unused tail
        return a + pad

    def alloc_near(self, n, lo, hi, align=4):
        """Aligned n bytes inside [lo, hi) (e.g. within Thumb BL range)."""
        for r in self.runs:
            a = max(r[0], lo)
            a += -a % align
            if a + n <= min(r[1], hi):
                if a > r[0]:
                    self.add(r[0], a)
                r[0] = a + n
                return a
        raise MemoryError(f"no free space for {n} bytes in [{lo:#x}, {hi:#x})")

    def total(self):
        return sum(e - s for s, e in self.runs)


def naming_dispatch(rom, src, pool):
    """DoNamingScreen dispatcher (data/naming_dispatch.s, assembled with
    arm-none-eabi-as; bytes checked in as NAMING_DISPATCH, entry points at
    +0 / +8 vanilla / +0x2E hack_nostore).

    FireRed's entry 0x0809D954: `b +12` to a Thumb->ARM long jump to the
    dispatcher (in bytes FireRed's replayed prologue frees); the hack's old
    hook stays at +2..+11 for the routines that call +2, its literal re-aimed
    at hack_nostore. The hack's DoNamingScreen entry (only the intro's player
    naming calls it) long-jumps to the dispatcher's FireRed path."""
    VAN, HACK = 0x9D954, 0x1FF5EB4
    assert src[VAN:VAN + 12] == bytes.fromhex("0090014800470000b55eff09")  # the hack's hook
    assert src[HACK:HACK + 16] == bytes.fromhex("f7b51e0008ab1d781048114b01911700")
    code = bytes.fromhex(NAMING_DISPATCH)
    d = pool.alloc_aligned(len(code))
    rom[d:d + len(code)] = code
    jump = lambda t: bytes.fromhex("7847c046" "00c09fe5" "1cff2fe1") + (0x08000000 + t + 1).to_bytes(4, "little")
    rom[VAN:VAN + 2] = bytes.fromhex("04e0")                       # b 0x0809D960
    rom[VAN + 8:VAN + 12] = (0x08000000 + d + 0x2E + 1).to_bytes(4, "little")  # hook literal
    rom[VAN + 12:VAN + 28] = jump(d)
    rom[HACK:HACK + 16] = jump(d + 8)


GMAPGROUPS = 0xB3B100   # the hack moved gMapGroups; literal in Overworld_GetMapHeaderByGroupAndId (0x55238)


def null_placeholder_scripts(rom, src):
    """The hack leaves pointers into the cartridge header as the script of many
    object, coord and BG events: 0x08000000 (ROM offset 0) and, in 366 objects the
    first pass missed, 0x08000001. FireRed treats only NULL as "nothing to
    interact with", so interacting with one runs the header as script bytecode and
    freezes the game (the original Chinese ROM does the same: Bellsprout Tower
    top floor, local id 8). Nothing can legitimately point into the header, so any
    script pointer below 0x08000100 is junk: Bellsprout Tower's remaining NPCs
    carry 0x08000001 and are why the floor still locks up for some players after
    the first fix. Scripts are reloaded from the map header on every map load, so
    zeroing them also fixes existing saves."""
    assert src[0x5524C:0x55250] == (0x08000000 + GMAPGROUPS).to_bytes(4, "little")
    u32 = lambda o: int.from_bytes(src[o:o + 4], "little")
    rp = lambda o: (u32(o) - 0x08000000) if 0x08000000 <= u32(o) < 0x0A000000 else None
    JUNK = lambda a: 0x08000000 <= u32(a) < 0x08000100
    n, seen, g = 0, set(), 0
    while g < 80 and (gp := rp(GMAPGROUPS + 4 * g)) is not None:
        m = 0
        while m < 500 and (mp := rp(gp + 4 * m)) is not None:
            ev = rp(mp + 4) if mp + 8 <= len(src) else None
            if ev and ev + 0x14 <= len(src) and src[ev] <= 64:
                op = rp(ev + 4)                       # object events (24 B records)
                if op:
                    for i in range(src[ev]):
                        a = op + 24 * i + 16
                        if a not in seen and JUNK(a):
                            seen.add(a)
                            rom[a:a + 4] = bytes(4)
                            n += 1
                # coord events are 16-byte records (script at +12), BG events 12-byte records (script at +8)
                for cnt, tbl, size, off in ((src[ev + 2], ev + 0xC, 16, 12),   # coord events
                                            (src[ev + 3], ev + 0x10, 12, 8)):  # BG events (#90)
                    tab = rp(tbl) if cnt <= 64 else None
                    for i in range(cnt if tab else 0):
                        a = tab + size * i + off
                        if a not in seen and JUNK(a):
                            seen.add(a)
                            rom[a:a + 4] = bytes(4)
                            n += 1
            m += 1
        g += 1
    return n


TOWER_GROUP, TOWER_MAP = 52, 2          # Bellsprout Tower, top floor
TOWER_STAGE_VAR, TOWER_STAGE_ON_FLOOR = 0x5120, 22   # story stage while on the floor
TOWER_STAGE_DONE = 23                                # ... and when the floor is over
ROAD_VAR, ROAD_AFTER_TOWER = 0x5186, 4   # Johto road stage; the hack's cleanup sets it to 4
ROUTE36 = (3, 85)                        # its coord events (36,14)/(37,14) are gated on ==3
TOWER_ON_RESUME = 0x08AF60C9            # the map's own ON_RESUME script (kept)
COORD_SCRIPT = 0x08AF5A3A              # the floor's story trigger script
COORD_NATIVE, COORD_CHAIN = 0x08CA0051, 0x08AF5011


# CFRU's BufferStringBattle (0x1D02B9E..) picks between two nearly identical battle strings with ARITHMETIC, not with two literals:
# `r3 = cond ? 0 : -(imm + 1)` (movs rX,#imm / negs / bics) added to ONE literal pointer. The compiler could do that because in the
# original ROM the two strings sit exactly imm + 1 bytes apart. Relocating the English strings breaks the spacing, so the code lands
# in the middle of unrelated text (issue #105 "strange one-liner before the trainer's lead Pokemon", #13 doubles: "rest.", "est.",
# "right type, I guess.", "isuke Goto"). Each pair is therefore re-laid as one block in the free pool:
#   [English string reached with the offset, padded to k bytes][English string the literal points at]
# and the literal is pointed at the second half. Both strings keep working, so nothing depends on which branch the code takes.
SENDOUT_PAIRS = [
    # name,              CFRU literal,  k (= imm + 1), vanilla ref word of the string at literal - k
    ("ghost appeared",   0x1D0392C,     52,            0x00D73E0),
    ("double send-out",  0x1D03978,     64,            0x00D7498),
    ("single send-out",  0x1D0397C,     70,            0x00D74C4),
    ("trainer withdrew", 0x1D03C04,     16,            0x00D7548),
]


def sendout_offset_pairs(rom, src, pool):
    out = []
    for name, lit, k, ref in SENDOUT_PAIRS:
        base_src = int.from_bytes(src[lit:lit + 4], "little")
        tgt_src = int.from_bytes(src[ref:ref + 4], "little")
        assert 0x08000000 <= base_src < 0x0A000000 and base_src - k == tgt_src, \
            f"sendout pair {name}: source pointers {base_src:#x} - {k} != {tgt_src:#x}"
        def text_at(ptr):
            o = ptr - 0x08000000
            e = rom.index(b"\xff", o) + 1
            return bytes(rom[o:e])
        base_en = int.from_bytes(rom[lit:lit + 4], "little")        # the literal was repointed with the English text
        tgt_en = int.from_bytes(rom[ref:ref + 4], "little")
        a, b = text_at(base_en), text_at(tgt_en)
        assert len(b) <= k, f"sendout pair {name}: English '{k}-byte' slot is {len(b)} bytes"
        blk = b + b"\xff" * (k - len(b)) + a
        at = pool.alloc(len(blk))
        rom[at:at + len(blk)] = blk
        rom[lit:lit + 4] = (0x08000000 + at + k).to_bytes(4, "little")
        out.append({"pair": name, "block": f"{at:07X}", "bytes": len(blk)})
    return out


def tower_top_floor_softlock(rom, src, pool):
    """Bellsprout Tower's top floor (52.2) softlocks the player in its exit corridor.

    The floor's story lives in one long script chain, started by the coord event
    on (12,22) and staged by two sages (localIds 8/9): the chain fights the
    double battle and the Dynamax Bellsprout, walks both sages up the one tile
    wide corridor into the room, and finally runs a cleanup that hides every
    scene object and moves the story stage to 23. Until that cleanup runs the
    story var stays at 22, which is also the coord event's trigger - so the tile
    that starts the chain is armed the whole time.

    A blocked `applymovement` walk *ends* (it does not wait), so the leading
    sage's walk up the corridor stops after one step whenever anything else is
    in that corridor (the following Pokemon, or the player). The sage then parks
    on (12,20) - the corridor's only tile - and since the chain was interrupted,
    the stage stays at 22: the player is walled in between the sage and their
    follower, can neither reach the ladder down (12,23) nor step south without
    restarting the whole chain (fights included), and the quest keeps reading
    "Head to the top of Sprout Tower!". Object templates come from the save, so
    reloading reproduces it, and the Chinese ROM is a dead end there too: every
    NPC on that floor carries the placeholder `0x08000000` script, so talking to
    the sage freezes the game (issue #17's bug) instead of opening the way.

    Fix: an ON_RESUME script (runs on every map load and whenever the field is
    resumed, so a stuck save is repaired on load, or by opening and closing the
    menu) that finishes the interrupted floor: if the stage is 22 and the sages
    are already spawned (flag 0x1798 clear - only true once the chain got past
    the Bellsprout fight), it applies the same end-of-sequence cleanup as the
    hack (hide the scene objects, stage 23). That frees the corridor, disarms
    the coord trigger - so nothing replays - and the player can walk back down
    into the tower. A healthy playthrough is untouched: the cleanup is gated on
    the sages being spawned with the stage still on 22, which cannot happen
    mid-chain (the chain has no field resumptions between those two points).

    Two further defects of the same scene:

    * The cast's farewell walks go *down* that same one-tile corridor (localIds 3,
      8 and 9 are sent to movement blobs of `down`/`right` steps). A blocked walk
      ends after its first step, so the NPCs park on the corridor's only tile while
      the player is still talking to them - and beta-11 reverted the earlier fix
      that had edited those blobs, because the same three blobs are referenced from
      six `applymovement` sites in other scripts. Instead, the six *operands* in
      this scene's scripts are repointed at a pooled "stay put" movement: the cast
      stays in the room (the corridor is never blocked, during or after the
      conversation) and the sequence's own cleanup still hides them.

    * The silent old man at (9,4) (localId 6) carried *no* flag in its template, so
      the cleanup's removeobject lasted only until the next map load: leave the
      floor and come back and he is walking down and up the stairs again. He now
      uses flag 0x178b - unused by every object in the hack, and the last entry the
      hack's own cleanups set, in the same script that advances the stage to 23, so
      any save that finished the scene already has it - and therefore stays gone."""
    u32 = lambda o: int.from_bytes(src[o:o + 4], "little")
    rp = lambda o: (u32(o) - 0x08000000) if 0x08000000 <= u32(o) < 0x0A000000 else None
    u16 = lambda o: int.from_bytes(src[o:o + 2], "little")
    gp = rp(GMAPGROUPS + 4 * TOWER_GROUP)
    mp = rp(gp + 4 * TOWER_MAP)
    scripts = rp(mp + 8)
    assert src[scripts:scripts + 11] == bytes.fromhex("03" "83067b08" "05" "c960af08" "00"), \
        "52.2 map scripts differ"

    b = bytes
    head = (b"\x21" + TOWER_STAGE_VAR.to_bytes(2, "little")          # compare stage, 22
            + TOWER_STAGE_ON_FLOOR.to_bytes(2, "little")
            + b"\x06\x00")                                           # goto_if !equal, done
    mid = b"\x2b" + (0x1798).to_bytes(2, "little") + b"\x06\x01"     # checkflag sages,
    cleanup = (b"".join(b"\x29" + f.to_bytes(2, "little") for f in   # the hack's own
                        (0x1794, 0x1790, 0x1791, 0x1795, 0x1796,    # end-of-sequence
                         0x1797, 0x1798, 0x178f, 0x178e, 0x178b))    # cleanup: hide the
               + b"".join(b"\x53" + i.to_bytes(2, "little") for i in range(1, 10))
               + b"\x16" + TOWER_STAGE_VAR.to_bytes(2, "little")     # cast, stage -> done
               + TOWER_STAGE_DONE.to_bytes(2, "little")
               + b"\x16" + ROAD_VAR.to_bytes(2, "little")            # road stage -> 4 (the
               + ROAD_AFTER_TOWER.to_bytes(2, "little"))             # hack's own setvar; #52
    tail = cleanup + b"\x05" + TOWER_ON_RESUME.to_bytes(4, "little")  # then the map's own
    body = head + b"\0\0\0\0" + mid + b"\0\0\0\0" + tail
    at = pool.alloc_aligned(len(body))
    done = 0x08000000 + at + len(body) - 5        # the trailing goto = "done"
    rom[at:at + len(body)] = body
    for off in (len(head), len(head) + 4 + len(mid)):   # both goto_if destinations
        rom[at + off:at + off + 4] = done.to_bytes(4, "little")
    rom[scripts + 6:scripts + 10] = (0x08000000 + at).to_bytes(4, "little")

    # The coord event that *starts* the floor's story stays armed for the whole
    # sequence (its gate is the stage var, which only the cleanup advances), and
    # the sequence's fights are not flag-gated: an interrupted run therefore
    # re-fights every time the player crosses that tile on the way down. Repoint
    # that one pointer slot (this map's own coord-event table) at a second script
    # that finishes the floor instead of re-running it once the fights are done.
    events = rp(mp + 4)
    coord = rp(events + 0xC)
    cx, cy = struct.unpack_from("<HH", rom, coord) if False else (u16(coord), u16(coord + 2))
    assert (cx, cy) == (12, 22), f"52.2 coord event at {(cx, cy)}"
    assert u16(coord + 6) == TOWER_STAGE_VAR and u16(coord + 8) == TOWER_STAGE_ON_FLOOR, \
        f"52.2 coord gate {u16(coord + 6):#x} == {u16(coord + 8)}"
    assert u32(coord + 0xC) == COORD_SCRIPT, f"52.2 coord script is {u32(coord + 0xC):#x}"
    assert src[COORD_SCRIPT - 0x08000000:COORD_SCRIPT - 0x08000000 + 10] == \
        b"\x23" + b"\x51\x00\xca\x08" + b"\x05" + COORD_CHAIN.to_bytes(4, "little"), \
        "52.2 coord script bytes differ"
    stage = lambda v: v.to_bytes(2, "little")
    cb = (b"\x23" + COORD_NATIVE.to_bytes(4, "little")          # callnative ...
          + b"\x05" + COORD_CHAIN.to_bytes(4, "little"))        # goto the story
    head2 = (b"\x21" + stage(TOWER_STAGE_VAR) + stage(TOWER_STAGE_ON_FLOOR) + b"\x06\x00")
    mid2 = b"\x2b" + (0x1798).to_bytes(2, "little") + b"\x06\x01"
    body2 = (head2 + b"\0\0\0\0" + mid2 + b"\0\0\0\0"
             + cleanup + b"\x02" + cb)          # cleanup, end, then the story (if reached)
    at2 = pool.alloc_aligned(len(body2))
    rom[at2:at2 + len(body2)] = body2
    chain_off = len(head2) + 4 + len(mid2) + 4 + len(cleanup) + 1
    chain = 0x08000000 + at2 + chain_off
    for off in (len(head2), len(head2) + 4 + len(mid2)):
        rom[at2 + off:at2 + off + 4] = chain.to_bytes(4, "little")
    rom[coord + 0xC:coord + 0x10] = (0x08000000 + at2).to_bytes(4, "little")

    # The sequence walks its cast *down the one-tile exit corridor* when it ends;
    # that path aborts at the corridor walls, so they park in the player's only way
    # out and look stuck after the conversation ("Morty in the stairs"). Repoint
    # just those applymovement operands at a pooled "stay put" movement: the cast
    # stays in the room, the corridor stays clear, and the sequence's own cleanup
    # still hides them. The movement blobs themselves are left untouched - they are
    # referenced from other scripts.
    stay = b"\x62" * 9 + b"\xfe"          # the idle action the hack uses elsewhere
    sat = pool.alloc_aligned(len(stay))
    rom[sat:sat + len(stay)] = stay
    leave_slots = {0xAF6B4B: 0x08AF6B81, 0xAF6B52: 0x08AF6B8C, 0xAF6ACB: 0x08AF6B99,
                   0xAF7D8B: 0x08AF6B8C, 0xAF85D8: 0x08AF6B81, 0xAF85DF: 0x08AF6B8C}
    for off, want in sorted(leave_slots.items()):
        assert src[off - 3] == 0x4F, f"{off:#x} is not an applymovement opcode"
        got = int.from_bytes(src[off:off + 4], "little")
        assert got == want, f"{off:#x} points at {got:#x}, expected {want:#x}"
        rom[off:off + 4] = (0x08000000 + sat).to_bytes(4, "little")

    # The old man at (9,4) (localId 6) has *no* flag in its template, so the
    # sequence's removeobject only lasts until the next map load - walking down and
    # up the stairs brings him back. Give him flag 0x178b: no object anywhere uses
    # it and the hack's own cleanups set it as the last entry of the flag list they
    # set before removing the scene cast, so he stays gone.
    objt = rp(events + 4)
    t = objt + 24 * 5
    assert src[t] == 6 and int.from_bytes(src[t + 20:t + 22], "little") == 0, \
        "localId 6 template differs"
    rom[t + 20:t + 22] = (0x178b).to_bytes(2, "little")

    # Issue #52: beta-7..11 ran a cleanup that moved the stage to 23 but left the road
    # stage 0x5186 at 3, so Route 36's two coord events ("Let's go see what's
    # happening in Violet City") stayed armed and walled the road to Ecruteak. The
    # cleanup above now sets it, but saves already past the tower have stage >= 23
    # and road stage 3 (3 is only ever set before the tower, so this is never a
    # healthy state). Put a guard in front of both coord scripts: stage >= 23 ->
    # finish the road stage and end silently; otherwise run the original script.
    g3 = rp(GMAPGROUPS + 4 * ROUTE36[0])
    m36 = rp(g3 + 4 * ROUTE36[1])
    ev36 = rp(m36 + 4)
    coords = rp(ev36 + 0xC)
    n_coord = src[ev36 + 2]
    fixed = []
    for i in range(n_coord):
        c = coords + 16 * i
        if u16(c + 6) != ROAD_VAR or u16(c + 8) != 3:
            continue
        orig = u32(c + 0xC)
        gb = (b"\x21" + TOWER_STAGE_VAR.to_bytes(2, "little")        # compare stage, 23
              + TOWER_STAGE_DONE.to_bytes(2, "little")
              + b"\x06\x04" + b"\0\0\0\0"                          # goto_if >=, repair
              + b"\x05" + orig.to_bytes(4, "little")                  # goto the original
              + b"\x16" + ROAD_VAR.to_bytes(2, "little")             # repair: road stage 4,
              + ROAD_AFTER_TOWER.to_bytes(2, "little") + b"\x02")    # end
        ga = pool.alloc_aligned(len(gb))
        rom[ga:ga + len(gb)] = gb
        rom[ga + 7:ga + 11] = (0x08000000 + ga + 16).to_bytes(4, "little")
        rom[c + 0xC:c + 0x10] = (0x08000000 + ga).to_bytes(4, "little")
        fixed.append((u16(c), u16(c + 2), 0x08000000 + ga))
    assert len(fixed) == 2, f"Route 36 gated coord events: {fixed}"
    return {"route36_guards": fixed, "on_resume": 0x08000000 + at, "coord_script": 0x08000000 + at2,
            "stay_movement": 0x08000000 + sat, "elder_flag": 0x178b,
            "bytes": [len(body), len(body2)]}


def whitney_badge_gate(rom, src, pool):
    """Whitney hands out the badge only after the player walks over one tile.

    After the Goldenrod Gym fight the player is warped back to (13,5), right
    below Whitney (13,4). Her script (0x08AA4C64) answers "Waah!!" while the
    story var 0x5151 is 1, and the only thing that clears it (and sets the flag
    0x1557 the badge branch tests) is the coord event at (13,10) - one tile of a
    room that is open on every side, so most players walk around it, talk to her
    again, get "Waah!!" again and never see the badge (the task keeps reading
    "Talk to Whitney"). The original Chinese ROM does the same.

    Fix: the `goto_if` that sends var 0x5151 == 1 to the crying branch now goes
    to a pooled script that does what the coord event does (var 0x5120 -> 0x49,
    flag 0x1557, var 0x5151 -> 0) and then jumps into that same branch, which
    now falls through to the badge. The coord event still works and saves that
    are already stuck are repaired the next time they talk to her."""
    CRY = 0x089E1568
    slot = 0xAA4C6D + 7                                   # goto_if operand
    assert src[0xAA4C6D:0xAA4C6D + 11] == bytes.fromhex("21" "5151" "0100" "0601") + CRY.to_bytes(4, "little"), \
        "Whitney script bytes differ"
    u16 = lambda v: v.to_bytes(2, "little")
    body = (b"\x16" + u16(0x5120) + u16(0x49)               # setvar 0x5120 0x49
            + b"\x29" + u16(0x1557)                         # setflag 0x1557
            + b"\x16" + u16(0x5151) + u16(0)                # setvar 0x5151 0
            + b"\x05" + CRY.to_bytes(4, "little"))          # goto the branch (now: badge)
    at = pool.alloc_aligned(len(body))
    rom[at:at + len(body)] = body
    rom[slot:slot + 4] = (0x08000000 + at).to_bytes(4, "little")
    return {"script": 0x08000000 + at, "bytes": len(body)}


def main():
    base = open(BASE, "rb").read()
    src = open(PATCHED, "rb").read()
    rom = bytearray(src)
    widths = src[mt.WIDTHS_OFF:mt.WIDTHS_OFF + 256]
    dump = json.load(open("text/zh.json", encoding="utf-8"))
    report = {"tables": {}, "inplace": 0, "relocated": 0, "missing": 0,
              "too_long": [], "errors": []}

    # --- fixed-stride tables
    # Entry 0 of a table shares its address with the table base, so the code's
    # `ldr =<base>` literal looks like a pointer to entry 0's string. The table
    # pass owns those bytes; the string pass must not relocate them (#70: the
    # type-name base was repointed to a relocated "Normal", so every other
    # type read garbage).
    table_heads = set()
    for name, t in dump["tables"].items():
        path = f"text/en/tables/{name}.json"
        if not os.path.exists(path):
            continue
        en = json.load(open(path, encoding="utf-8"))
        base_off, stride, size = int(t["base"], 16), t["stride"], t["size"]
        n = 0
        for idx, text in en.items():
            try:
                b = mt.encode_en(text)
            except ValueError as e:
                report["errors"].append(f"{name}[{idx}]: {e}")
                continue
            if len(b) > size:
                report["too_long"].append(f"{name}[{idx}] {text!r} ({len(b)}>{size})")
                continue
            o = base_off + int(idx) * stride
            rom[o:o + size] = b + b"\x00" * (size - len(b))
            n += 1
            if int(idx) == 0:
                table_heads.add(o)
        report["tables"][name] = n

    # --- pointer-referenced strings
    tm = load_tm()
    strings = {int(k, 16): v for k, v in dump["strings"].items()
               if int(k, 16) not in table_heads}
    # debugging: INSERT_SKIP=<json list of hex addrs> leaves those strings untouched
    if os.environ.get("INSERT_SKIP"):
        for a in json.load(open(os.environ["INSERT_SKIP"])):
            strings.pop(int(a, 16), None)
    # refs that are GCC section anchors (scripts/anchor_refs.py): code reaches
    # other data by offset from them, so they are never repointed and the
    # original bytes are never recycled; such text is written in place or kept
    anchor_refs = set(json.load(open("data/anchor_refs.json")))
    for v in strings.values():
        anc = [r for r in v["refs"] if r.split(":")[0] in anchor_refs]
        if anc:
            v["refs"] = [r for r in v["refs"] if r not in anc]
            v["untrusted"] += len(anc)
            v["anchored"] = True
    report["anchor_kept"] = []
    starts = sorted(strings)
    contains_other = set()
    for i, a in enumerate(starts):
        for b in starts[i + 1:]:
            if b >= a + strings[a]["cap"]:
                break
            contains_other.add(a)
            contains_other.add(b)  # b's tail is shared too; never write either in place
    table_px = layout.table_widths(strings)
    # strings referenced from an item table's description field (+0x14)
    item_desc = set()
    for tb, n in ((0x3DB028, 378), (0x7C7E00, 750)):
        for i in range(n):
            item_desc.add(int.from_bytes(src[tb + 44 * i + 0x14:tb + 44 * i + 0x18], "little") - 0x08000000)
    # strings referenced from the hack's move-description table (CFRU, 0x1CC8EB0)
    move_desc = {int.from_bytes(src[MOVE_DESC_TABLE + 4 * i:MOVE_DESC_TABLE + 4 * i + 4], "little") - 0x08000000
                 for i in range(MOVE_DESC_COUNT)}
    dialogue_addrs = layout.dialogue_set(strings)
    pool = FreePool(src)
    if json.load(open(edition.new_maps_path())).get("frontier"):      # one 31 KB run for the Spectrum Frontier's moved trainer table (scripts/frontier_build.py)
        import frontier_build
        frontier_build.reserve(pool)
    # debugging: INSERT_NORECYCLE=<json list of hex addrs> never frees those originals
    keep = set()
    if os.environ.get("INSERT_NORECYCLE"):
        keep = {int(a, 16) for a in json.load(open(os.environ["INSERT_NORECYCLE"]))}
    # window width in px for strings shown in narrower boxes than their class
    width_override = {k: v for k, v in json.load(
        open("text/en/width_override.json", encoding="utf-8")).items() if not k.startswith("_")}
    pending = []
    for t in starts:
        v = strings[t]
        if v.get("suspect") or tm.get(v["zh"], "") is None:
            continue
        en = tm.get(v["zh"])
        if en is None:
            report["missing"] += 1
            continue
        dialogue = t in dialogue_addrs
        single_line = not dialogue and not re.search(r"\n|\{FA\}|\{FB\}", v["zh"])
        max_px = DIALOGUE_PX if dialogue else max(src_max_px(v["zh"], widths), table_px.get(t, 0), 48)
        if "{F9:0A}" in v["zh"]:  # help-system pages use the full-width window
            max_px = HELP_PX
        if t in item_desc:  # bag description box (3 lines, ~176px before the arrow)
            max_px, dialogue, single_line = ITEM_DESC_PX, False, False
        if t in move_desc:  # summary / move-learn description box (4 lines)
            max_px, dialogue, single_line = MOVE_DESC_PX, False, False
        max_lines = None
        if f"{t:07X}" in width_override:
            wo = width_override[f"{t:07X}"]
            max_px, dialogue, single_line = wo["px"], wo.get("dialogue", dialogue), False
            max_lines = wo.get("lines")
        try:
            text = en if single_line else mt.wrap_en(en, widths, max_px, dialogue)
            b = mt.encode_en(text)
        except ValueError as e:
            report["errors"].append(f"{t:07X}: {e}")
            continue
        # boxes that don't scroll: extra lines are drawn past the window's
        # pixel buffer (heap overflow), so refuse them and keep the original
        n_lines = text.count("\n") + 1
        if max_lines and n_lines > max_lines:
            report["too_long"].append(f"{t:07X} {n_lines} lines > {max_lines}: {en!r}")
            continue
        if len(b) <= v["cap"] and t not in contains_other:
            rom[t:t + v["cap"]] = b + b"\xff" * (v["cap"] - len(b))
            pool.add(t + len(b) + 1, t + v["cap"]) if v["untrusted"] == 0 and t not in keep else None
            report["inplace"] += 1
        elif v.get("anchored") and not v["refs"]:
            report["anchor_kept"].append(f"{t:07X} {len(b)}>{v['cap']}: {en!r}")
        else:
            pending.append((t, b))
            if v["untrusted"] == 0 and t not in contains_other and t not in keep:
                pool.add(t + 1, t + v["cap"])  # keep byte 0 so stray reads hit text
    # anchor-reached text is written in place below: keep it out of the pool
    anc_zh = json.load(open(anchored.ZH, encoding="utf-8"))
    anc_en = json.load(open(anchored.EN, encoding="utf-8")) if os.path.exists(anchored.EN) else {}
    for k, v in anc_zh.items():
        pool.reserve(int(k, 16) - 1, int(k, 16) + v["cap"])
    # in-place manual strings and code-anchored text likewise
    for k, v in json.load(open("text/en/manual_strings.json", encoding="utf-8")).items():
        if not k.startswith("_"):
            pool.reserve(int(k, 16) - 1, int(k, 16) + v["cap"])
    for name, blk in json.load(open("text/en/code_text.json", encoding="utf-8")).items():
        if not name.startswith("_"):
            for st in blk["strings"]:
                a = int(st["zh_at"], 16)
                pool.reserve(a - 1, src.index(b"\xff", a) + 1)
    # 0xFF runs the hack reads as data are not free: a code literal into a run
    # (a table the code indexes, e.g. 0xC2AEA0) keeps the whole run, and a
    # pointer from a pointer table (end-marker entries such as the dressing
    # room's 26th outfit at 0x76AF1C, empty-string slots) keeps a window
    for a, b in referenced_ff(src):
        pool.reserve(a, b)
    # every word that gets repointed below must not end up under new text
    for v in strings.values():
        for r in v["refs"]:
            ro = int(r.split(":")[0], 16)
            pool.reserve(ro, ro + 4)
    report["free_before_reloc"] = pool.total()
    moved = {}  # old pointer -> new pointer, for every relocated string
    for t, b in sorted(pending, key=lambda x: -len(x[1])):
        a = pool.alloc(len(b))
        rom[a:a + len(b)] = b
        for r in strings[t]["refs"]:
            ro = int(r.split(":")[0], 16)
            rom[ro:ro + 4] = (0x08000000 + a).to_bytes(4, "little")
        moved[0x08000000 + t] = 0x08000000 + a
        report["relocated"] += 1
    # The dump's script scan desyncs on some scripts, so a `loadword` operand (0f 0x <ptr>) can be missing from `refs` and would keep
    # pointing at the old address: the old Chinese, or whatever the pool put there next (#125). Repoint those too.
    report["extra_repointed"] = []
    for m in re.finditer(rb"\x0f[\x00-\x03]([\x00-\xff]{3})\x08", bytes(src)):
        old = int.from_bytes(m.group(1) + b"\x08", "little")
        if old in moved:
            ro = m.start() + 2
            if int.from_bytes(rom[ro:ro + 4], "little") == old:  # not already repointed through refs
                rom[ro:ro + 4] = moved[old].to_bytes(4, "little")
                report["extra_repointed"].append(f"{ro:07X} {old:#010x} -> {moved[old]:#010x}")
    # --- manual strings (text/en/manual_strings.json): unfindable by the scan
    manual = json.load(open("text/en/manual_strings.json", encoding="utf-8"))
    for addr, m in manual.items():
        if addr.startswith("_"):
            continue
        t = int(addr, 16)
        assert mt.decode(src, t, m["cap"])[0] == m["zh"], f"manual {addr}: source text moved"
        b = mt.encode_en(m["en"])
        if len(b) <= m["cap"]:
            rom[t:t + m["cap"]] = b + b"\xff" * (m["cap"] - len(b))
            report["inplace"] += 1
        if m.get("ref_en") or (len(b) > m["cap"] and m.get("refs")):
            # ref_en: a different (longer) text for what the pointers show,
            # e.g. a list label, while code-computed reads see the in-place text
            b = mt.encode_en(m.get("ref_en", m["en"]))
            a = pool.alloc(len(b))
            rom[a:a + len(b)] = b
            for r in m["refs"]:
                ro = int(r, 16)
                assert int.from_bytes(src[ro:ro + 4], "little") == 0x08000000 + t, f"manual ref {r}"
                rom[ro:ro + 4] = (0x08000000 + a).to_bytes(4, "little")
            report["relocated"] += 1
        elif len(mt.encode_en(m["en"])) > m["cap"]:
            report["too_long"].append(f"manual {addr} {m['en']!r} ({len(b)}>{m['cap']})")
    # --- code-anchored text (text/en/code_text.json): code reaches it as
    # literal base + adds imm8, so move the whole group and patch the code
    code_text = json.load(open("text/en/code_text.json", encoding="utf-8"))
    for name, blk in code_text.items():
        if name.startswith("_"):
            continue
        lit = int(blk["literal"], 16)
        assert src[lit:lit + 4] == int(blk["orig"], 16).to_bytes(4, "little"), f"code_text {name}: literal moved"
        parts = []
        for s in blk["strings"]:
            assert mt.decode(src, int(s["zh_at"], 16), 1024)[0] == s["zh"], f"code_text {name}: source text moved"
            parts.append((int(s["off"], 16), mt.encode_en(s["en"])))
        lo = min(o for o, _ in parts)
        hi = max(o + len(b) for o, b in parts)
        for (o1, b1), (o2, _) in zip(sorted(parts), sorted(parts)[1:]):
            assert o1 + len(b1) <= o2, f"code_text {name}: strings overlap"
        a = pool.alloc(hi - lo)
        base_addr = a - lo
        for o, b in parts:
            rom[base_addr + o:base_addr + o + len(b)] = b
        rom[lit:lit + 4] = (0x08000000 + base_addr).to_bytes(4, "little")
        for p in blk["patch"]:
            at, orig, new = int(p["at"], 16), bytes.fromhex(p["orig"]), bytes.fromhex(p["new"])
            assert src[at:at + len(orig)] == orig, f"code_text {name}: code at {p['at']} differs"
            rom[at:at + len(new)] = new
        report["relocated"] += len(parts)
    # --- anchor-reached text (anchored.py): in place, within the original bytes
    report["anchored"] = 0
    for k, en in anc_en.items():
        if en is None:  # not text (e.g. the pinyin keyboard's character table)
            continue
        t, v = int(k, 16), anc_zh[k]
        assert mt.decode(src, t, v["cap"])[0] == v["zh"], f"anchored {k}: source text moved"
        b = anchored.layout(v["zh"], en, widths)
        if len(b) > v["cap"]:
            if not anchored.relocatable(v):
                report["too_long"].append(f"anchored {k} ({len(b)}>{v['cap']})")
                continue
            a = pool.alloc(len(b))  # move it; point each anchor at (a - offset)
            rom[a:a + len(b)] = b
            for lit, off in v["anchors"]:
                lo = int(lit, 16)
                assert int.from_bytes(src[lo:lo + 4], "little") == 0x08000000 + t - off
                rom[lo:lo + 4] = (0x08000000 + a - off).to_bytes(4, "little")
        else:
            rom[t:t + v["cap"]] = b + b"\xff" * (v["cap"] - len(b))
        report["anchored"] += 1
    # --- image text (gfx/*.json): redrawn tileset + tilemap, LZ77, repointed
    report["gfx"] = 0
    for spec in sorted(glob.glob("gfx/*.json")):
        if os.path.basename(spec).startswith("font"):
            continue
        if os.path.basename(spec).startswith("spr_"):
            data, refs = sprtext.apply(spec, src)   # text-only sprite, redrawn
            a = pool.alloc_aligned(len(data))
            rom[a:a + len(data)] = data
            for r in refs:
                rom[r:r + 4] = (0x08000000 + a).to_bytes(4, "little")
            report["gfx"] += 1
            continue
        if os.path.basename(spec).startswith("map_"):
            # text baked into a map's tileset: metatiles/blocks in place,
            # the grown tileset relocated
            writes, data, refs = maptext.apply(spec, src)
            for off, b in writes.items():
                rom[off:off + len(b)] = b
            a = pool.alloc_aligned(len(data))
            rom[a:a + len(data)] = data
            for r in refs:
                rom[r:r + 4] = (0x08000000 + a).to_bytes(4, "little")
            report["gfx"] += 1
            continue
        for data, refs, _ in gfx_text.apply(spec, src):
            a = pool.alloc_aligned(len(data))
            rom[a:a + len(data)] = data
            for r in refs:
                rom[r:r + 4] = (0x08000000 + a).to_bytes(4, "little")
        report["gfx"] += 1
    # type icons + TYPE/POWER/... labels (hack's menu-info sheet, raw, in place)
    ti = typeicons.build(src, base)
    rom[typeicons.SHEET:typeicons.SHEET + len(ti)] = ti
    report["gfx"] += 1
    # party-menu / summary status icons (PSN..FNT), LZ77 sheet relocated, both refs
    data, refs = statusicons.build(src)
    a = pool.alloc_aligned(len(data))
    rom[a:a + len(data)] = data
    for r in refs:
        rom[r:r + 4] = (0x08000000 + a).to_bytes(4, "little")
    report["gfx"] += 1
    # title logo (raw 8bpp BG): fits in the original tile area, so in place
    lt, lm = logo.build(src)
    assert len(lt) <= logo.MAX_TILES * 64
    if len(lt) <= 162 * 64:
        rom[logo.TILES:logo.TILES + len(lt)] = lt
    else:   # the River Edition tag needs more tiles: relocate them and repoint the title code's literal
        assert src[logo.LIT_TILES:logo.LIT_TILES + 4] == (0x08000000 + logo.TILES).to_bytes(4, "little")
        la = pool.alloc_aligned(len(lt))
        rom[la:la + len(lt)] = lt
        rom[logo.LIT_TILES:logo.LIT_TILES + 4] = (0x08000000 + la).to_bytes(4, "little")
    rom[logo.MAP:logo.MAP + len(lm)] = lm
    report["gfx"] += 1
    # plain code/data patches (data/code_patches.json)
    for name, blk in json.load(open("data/code_patches.json")).items():
        if name.startswith("_"):
            continue
        for p in blk.get("patch", []):
            at, orig, new = int(p["at"], 16), bytes.fromhex(p["orig"]), bytes.fromhex(p["new"])
            assert src[at:at + len(orig)] == orig, f"code patch {name}: bytes at {p['at']} differ"
            rom[at:at + len(new)] = new
        for rp in blk.get("replace_all", []):   # every occurrence in the source ROM
            f, w = bytes.fromhex(rp["find"]), bytes.fromhex(rp["with"])
            hits = [m.start() for m in re.finditer(re.escape(f), src)]
            assert len(hits) == rp["count"], f"code patch {name}: {len(hits)} != {rp['count']}"
            for at in hits:
                rom[at:at + len(w)] = w
        for a, b, _ in blk.get("vanilla", []):
            a, b = int(a, 16), int(b, 16)
            rom[a:b] = base[a:b]
    report["null_object_scripts"] = null_placeholder_scripts(rom, src)
    report["tower_top_floor"] = tower_top_floor_softlock(rom, src, pool)
    report["whitney_badge_gate"] = whitney_badge_gate(rom, src, pool)
    report["sendout_pairs"] = sendout_offset_pairs(rom, src, pool)
    naming_dispatch(rom, src, pool)
    if edition.CHEATS:
        report["cheats"] = cheats_build.apply(rom, src, pool)
    if edition.EDITION == "river":          # Partner Patrol (docs/PARTNER_PATROL_SPEC.md): River Edition only, chained after the Cheat Device
        report["patrol"] = patrol_build.apply(rom, src, pool)
    report["new_maps"] = mapedit.apply(rom, src, pool, edition.new_maps_path())
    report["free_after"] = pool.total()

    os.makedirs("build", exist_ok=True)
    out = os.environ.get("INSERT_OUT")  # debugging: write only this ROM
    if out:
        open(out, "wb").write(rom)
        print({k: (v if not isinstance(v, list) else len(v)) for k, v in report.items()})
        return
    open("build/Mercury_EN.gba", "wb").write(rom)
    open("build/Mercury_EN.bps", "wb").write(bps.create(base, bytes(rom)))
    json.dump(report, open("build/insert_report.json", "w"), indent=1, ensure_ascii=False)
    print({k: (v if not isinstance(v, list) else len(v)) for k, v in report.items()})


if __name__ == "__main__":
    main()
