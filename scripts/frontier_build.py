"""Spectrum Frontier build step (docs/BATTLE_FRONTIER_SPEC.md). Called by mapedit.apply() when data/new_maps.json has "frontier": true.

    link(rom, src, pool)      before scripts are assembled: sets table, speech table and the native image go into the free pool;
                              returns the externs scripts use (`callnative @fr_enter` ...)
    extend(spec, ext)         adds the arenas (group 58), the hall / cabin edits, every script, the hall transition hook
    finalize(rom, src, pool)  last step: moves the trainer table (room for 32 more slots), repoints its 40-byte-window literals, writes the shell
                              opponents (class/picture/music from donor trainers, our names) and aims the speech-table words at the RAM text buffers

Reserved: vars 0x5121-0x5132 (PARK0-2 reuse PICK1-3 after fr_enter: the hidden Pokémon's species), flags 0x1388-0x13A7, trainer slots 743-774 (new), map group 58 maps 58.5-58.9, EWRAM 0x02022400-0x020227FF.
"""
import array
import json
import os
import struct
import sys
from string import Template

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import frontier_native as fn  # noqa: E402
import frontier_sets as fsets  # noqa: E402
import mercury_text as mt  # noqa: E402

ROM_BASE = 0x08000000
DATA = os.path.join(ROOT, "data/frontier")

VARS = dict(MODE=0x5121, STATE=0x5122, STREAK=0x5123, SEED_LO=0x5124, SEED_HI=0x5125, PICK0=0x5126, PICK1=0x5127, PICK2=0x5128, PICK3=0x5129,
            PERM_LO=0x512A, PERM_HI=0x512B, PARK0=0x5127, PARK1=0x5128, PARK2=0x5129, BP=0x512C, BEST_S=0x512D, BEST_D=0x512E, SYMBOLS=0x512F, TMP=0x5130, TMP2=0x5131, SHOP=0x5132)
TRAINER_TABLE = 0x23EACC - 4          # file offset of trainer 0 (40-byte entries)
TRAINER_COUNT = 743
EXTRA_SLOTS = 32
SHELL_S, SHELL_D = 743, 755           # 12 singles shells (party size 3), 12 doubles shells (size 4, double battle)
SHELL_LANCE = (767, 768)              # singles, doubles
SHELL_ANABEL = (769, 770)
BLOCK = 0x02022400                    # the RAM party the shells point at
SPEECH_BUF = (0x02022600, 0x02022680, 0x02022700)   # intro, defeat, win
SPEECH_ENTRY = 0x1DEC3A0              # first entry of the orphaned Battle Tower trainer table: words 1 / 2 = speech when the player wins / loses
ARENA_MAPSEC = 220                    # "Battle Tower"
HALL, CABIN = "31.3", "31.6"
HALL_DOOR = (10, 17)                  # inside the hall's south door

# arena clones of the Elite Four chambers: key, source map, arrival tile, challenger tile
SEAL = dict(SILVER_S=0x1389, GOLD_S=0x138A, SILVER_D=0x138B, GOLD_D=0x138C)   # Seal flags (hack flags >= 0x900: set with the game's own setflag)
BRAIN_ARENAS = [("lance", "1.79", (8, 25), (8, 7), 119), ("anabel", "1.79", (8, 25), (8, 7), 136)]   # 58.10 (Lance), 58.11 (Anabel)
ARENAS = [("ice", "1.75", (7, 20), (7, 11)), ("psychic", "1.76", (7, 20), (7, 11)), ("fire", "1.77", (7, 20), (7, 11)),
          ("dark", "1.78", (7, 20), (7, 11)), ("gold", "1.79", (8, 25), (8, 7))]
FLOOR_ARENA = ["fire", "gold", "gold", "dark", "ice", "psychic", "psychic"]
FLOORS = [("Red", "Kindle", "Warm hands, warm hearts."), ("Orange", "Ember", "Rough and cheerful."), ("Yellow", "Spark", "Mind the showoffs."),
          ("Green", "Grove", "Patient, outdoorsy company."), ("Blue", "Tide", "Calm and precise."), ("Indigo", "Dusk", "Something uncanny hums here."),
          ("Violet", "Prism", "Nobody here is a stranger to the rainbow.")]


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


# ----------------------------------------------------------------------------------------------------------------------------- reserve
_TABLE_AT = None


def reserve(pool):
    """Called by insert.py right after the pool is built, BEFORE the English text is relocated: the moved trainer table needs one 31 KB run
    and the free pool is fragmented into pieces of at most ~24 KB by the time the maps are built."""
    global _TABLE_AT
    _TABLE_AT = pool.alloc_aligned(TRAINER_COUNT * 40 + EXTRA_SLOTS * 40)
    return _TABLE_AT


# ------------------------------------------------------------------------------------------------------------------------------ link
def link(rom, src, pool):
    sets = fsets.pack_json(os.path.join(DATA, "sets.json"))
    a_sets = pool.alloc_aligned(len(sets))
    rom[a_sets:a_sets + len(sets)] = sets
    speech = json.load(open(os.path.join(DATA, "speech.json")))
    kinds = ["intro", "defeat", "win"]
    ptrs = []
    for k in kinds:
        for line in speech[k]:
            b = mt.encode_en(line)
            assert len(b) <= 127, f"speech line too long ({len(b)} bytes): {line!r}"
            a = pool.alloc(len(b))
            rom[a:a + len(b)] = b
            ptrs.append(ROM_BASE + a)
    blob = struct.pack("<HHHH", *(len(speech[k]) for k in kinds), 0) + b"".join(struct.pack("<I", p) for p in ptrs)
    a_speech = pool.alloc_aligned(len(blob))
    rom[a_speech:a_speech + len(blob)] = blob
    brains = fsets.pack_brains_json(os.path.join(DATA, "sets.json"))
    a_brains = pool.alloc_aligned(len(brains))
    rom[a_brains:a_brains + len(brains)] = brains
    bptrs = []
    for who in ("Lance", "Anabel"):
        for k in ("defeat", "win"):
            b = mt.encode_en(speech["brain"][who][k])
            assert len(b) <= 127, (who, k)
            a = pool.alloc(len(b))
            rom[a:a + len(b)] = b
            bptrs.append(ROM_BASE + a)
    a_bsp = pool.alloc_aligned(16)
    rom[a_bsp:a_bsp + 16] = b"".join(struct.pack("<I", p_) for p_ in bptrs)
    image, _ = fn.build(ROM_BASE, os.path.join(ROOT, "build/frontier/native.bin"), sets=ROM_BASE + a_sets, speech=ROM_BASE + a_speech,
                        brains=ROM_BASE + a_brains, bspeech=ROM_BASE + a_bsp)
    pool_len = len(image)
    a_nat = pool.alloc_aligned(len(image))
    # the entry stubs hold absolute addresses: relink at the final location (same size, only addresses change)
    image, _ = fn.build(ROM_BASE + a_nat, os.path.join(ROOT, "build/frontier/native.bin"), sets=ROM_BASE + a_sets, speech=ROM_BASE + a_speech,
                        brains=ROM_BASE + a_brains, bspeech=ROM_BASE + a_bsp)
    assert len(image) <= pool_len
    rom[a_nat:a_nat + len(image)] = image
    base = ROM_BASE + a_nat
    names = ["fr_" + n for n in fn.ENTRIES]
    externs = {n: (base + fn.ENTRY_STRIDE * i) | 1 for i, n in enumerate(names)}
    return {"externs": externs, "sets": len(sets), "native": len(image), "speech": len(blob), "at": {"sets": a_sets, "speech": a_speech, "native": a_nat}}


# --------------------------------------------------------------------------------------------------------------------------- scripts
def T(text, **kw):
    d = dict(VARS)
    d.update(kw)
    return Template(text).safe_substitute(d)


def build_scripts():
    S = {}

    def A(name, text, **kw):
        S[name] = {"asm": T(text, **kw)}

    # --- hall: stale-challenge repair on entry (chained in front of the hall's own ON_TRANSITION)
    A("fr_hall_tr", """
        compare_var_to_value $STATE 0
        goto_if 1 done
        copyvar 0x8005 $PERM_LO
        copyvar 0x8006 $PERM_HI
        copyvar 0x8009 $PARK0
        copyvar 0x800A $PARK1
        copyvar 0x800B $PARK2
        callnative @fr_leave
        setvar $STATE 0
        done:
        goto @orig_31_3_transition
    """)

    # --- reception counters (singles: 3 picks, doubles: 4)
    for mode, n, label, who in ((1, 3, "singles", "Hue"), (2, 4, "doubles", "Saturate")):
        picks = ""
        for i in range(n):
            picks += f"""
        special 0x9F
        waitstate
        compare_var_to_value 0x8004 6
        goto_if 4 cancel
        copyvar $PICK{i} 0x8004
        """
        args = "".join(f"copyvar 0x800{1 + i} $PICK{i}\n        " for i in range(n))
        A(f"fr_recep_{label}", f"""
        lock
        faceplayer
        compare_var_to_value $STATE 0
        goto_if 1 fresh
        say "My ledger shows a climb that never ended.{{FB}}I have tidied it up. Your party is back to normal."
        copyvar 0x8005 $PERM_LO
        copyvar 0x8006 $PERM_HI
        copyvar 0x8009 $PARK0
        copyvar 0x800A $PARK1
        copyvar 0x800B $PARK2
        callnative @fr_leave
        setvar $STATE 0
        fresh:
        say "Welcome to the Spectrum Tower.{{FB}}Seven floors, seven battles, one colour each.{{FB}}Everyone fights at Lv 50: the stairs do not care how strong you were yesterday."
        ask "Shall I register you for the {label} climb?"
        compare_var_to_value 0x800D 1
        goto_if 1 pick
        say "Come back whenever the sky is the right shade."
        release
        end
        pick:
        say "Choose {n} Pokémon. They fight at Lv 50."
        {picks}
        setvar 0x8000 {n}
        {args}callnative @fr_enter
        copyvar $PARK0 0x8009
        copyvar $PARK1 0x800A
        copyvar $PARK2 0x800B
        copyvar 0x8008 0x800D
        compare_var_to_value 0x8008 0
        goto_if 1 ready
        say "Those picks will not do: the same Pokémon twice, or an Egg. Let us try again."
        goto pick
        ready:
        copyvar $PERM_LO 0x8005
        copyvar $PERM_HI 0x8006
        setvar $MODE {mode}
        setvar $STREAK 0
        call @fr_make_seed
        setvar $STATE 1
        say "Your party is set to Lv 50. Floor one is Red: warm hands, warm hearts.{{FB}}Up you go!"
        goto @fr_to_arena
        cancel:
        say "Another time, then."
        release
        end
        """)

    # --- challenge seed: this hack's `random 65535` is badly skewed (mostly < 25), so each 16-bit half is random(256) + 256 * random(256)
    A("fr_make_seed", """
        random 256
        copyvar $SEED_LO 0x800D
        random 256
        copyvar $TMP 0x800D
        lo_loop:
        compare_var_to_value $TMP 0
        goto_if 1 lo_done
        subvar $TMP 1
        addvar $SEED_LO 256
        goto lo_loop
        lo_done:
        random 256
        copyvar $SEED_HI 0x800D
        random 256
        copyvar $TMP 0x800D
        hi_loop:
        compare_var_to_value $TMP 0
        goto_if 1 hi_done
        subvar $TMP 1
        addvar $SEED_HI 256
        goto hi_loop
        hi_done:
        return
    """)

    # --- floor index (STREAK mod 7 -> TMP), shared
    A("fr_floor_idx", """
        copyvar $TMP $STREAK
        again:
        compare_var_to_value $TMP 7
        goto_if 0 done
        subvar $TMP 7
        goto again
        done:
        return
    """)

    # --- warp to the arena for the current floor
    arena_ids = {k: f"58.{5 + i}" for i, (k, *_r) in enumerate(ARENAS + BRAIN_ARENAS)}
    arrive = {k: a for k, _s, a, _n, *_g in ARENAS + BRAIN_ARENAS}
    lines = ["compare_var_to_value $STREAK 20", "goto_if 1 to_lance", "compare_var_to_value $STREAK 48", "goto_if 1 to_anabel", "call @fr_floor_idx"]
    for f in range(7):
        lines += [f"compare_var_to_value $TMP {f}", f"goto_if 1 to_{f}"]
    for k in ("lance", "anabel"):
        x, y = arrive[k]
        lines += [f"to_{k}:", f"warp {arena_ids[k]} {x} {y}", "waitstate", "end"]
    for f in range(7):
        k = FLOOR_ARENA[f]
        x, y = arrive[k]
        lines += [f"to_{f}:", f"warp {arena_ids[k]} {x} {y}", "waitstate", "end"]
    A("fr_to_arena", "\n".join(lines))

    # --- floor announcement (call/return)
    ann = ["call @fr_floor_idx"]
    for f in range(7):
        ann += [f"compare_var_to_value $TMP {f}", f"goto_if 1 say_{f}"]
    for f, (colour, name, line) in enumerate(FLOORS):
        ann += [f"say_{f}:", f'say "Floor {f + 1}: {colour}. {line}"', "return"]
    A("fr_announce", "\n".join(ann))

    # --- the arena frame script: announce, build the opponent, fight, resolve
    A("fr_arena_start", """
        lockall
        call @fr_announce
        compare_var_to_value $STREAK 20
        goto_if 1 @fr_brain_lance
        compare_var_to_value $STREAK 48
        goto_if 1 @fr_brain_anabel
        copyvar 0x8000 $STREAK
        addvar 0x8000 1
        copyvar 0x8001 $MODE
        subvar 0x8001 1
        copyvar 0x8002 $SEED_LO
        copyvar 0x8003 $SEED_HI
        callnative @fr_gen
        callnative @fr_speech
        random 12
        copyvar $TMP2 0x800D
        compare_var_to_value $MODE 1
        goto_if 1 singles
        copyvar 0x8000 $TMP2
        addvar 0x8000 $SHELL_D
        goto id_done
        singles:
        copyvar 0x8000 $TMP2
        addvar 0x8000 $SHELL_S
        id_done:
        copyvar 0x8001 $MODE
        subvar 0x8001 1
        loadword 0 $INTRO
        callstd 2
        callnative @fr_heal
        callnative @fr_start
        waitstate
        specialvar 0x800D 0xB4
        compare_var_to_value 0x800D 1
        goto_if 1 @fr_won
        goto @fr_lost
    """, INTRO=SPEECH_BUF[0], SHELL_S=SHELL_S, SHELL_D=SHELL_D)

    # --- a won fight: heal, count it, Seals at 21 and 49, round reward every 7th, otherwise the next floor
    A("fr_won", """
        callnative @fr_heal
        addvar $STREAK 1
        compare_var_to_value $STREAK 21
        goto_if 1 @fr_seal_silver
        compare_var_to_value $STREAK 49
        goto_if 1 @fr_seal_gold
        call @fr_floor_idx
        compare_var_to_value $TMP 0
        goto_if 1 @fr_round_done
        setvar $STATE 1
        goto @fr_to_arena
    """)

    # --- the Brains: Lance (battle 21), Anabel (battle 49)
    sp = json.load(open(os.path.join(DATA, "speech.json")))["brain"]
    for idx, (key, name, shells) in enumerate((("lance", "Lance", SHELL_LANCE), ("anabel", "Anabel", SHELL_ANABEL))):
        intro = f'say "{sp[name]["intro"]}"'
        if name == "Anabel":          # kinder after the River Edition's Chapter 2 (CH2_DONE 0x134F)
            intro = f"""checkflag 0x134F
        goto_if 1 after
        {intro}
        goto go
        after:
        say "{sp[name]["intro_after"]}"
        go:"""
        A(f"fr_brain_{key}", f"""
        {intro}
        setvar 0x8000 {idx}
        copyvar 0x8001 $MODE
        subvar 0x8001 1
        copyvar 0x8002 $SEED_LO
        copyvar 0x8003 $SEED_HI
        copyvar 0x8004 $STREAK
        callnative @fr_gen_brain
        setvar 0x8000 {idx}
        callnative @fr_brain_speech
        compare_var_to_value $MODE 1
        goto_if 1 singles
        setvar 0x8000 {shells[1]}
        goto id_done
        singles:
        setvar 0x8000 {shells[0]}
        id_done:
        copyvar 0x8001 $MODE
        subvar 0x8001 1
        callnative @fr_heal
        callnative @fr_start
        waitstate
        specialvar 0x800D 0xB4
        compare_var_to_value 0x800D 1
        goto_if 1 @fr_won
        goto @fr_lost
        """)
    for key, flag_s, flag_d, bp in (("silver", SEAL["SILVER_S"], SEAL["SILVER_D"], 10), ("gold", SEAL["GOLD_S"], SEAL["GOLD_D"], 20)):
        name = "Lance" if key == "silver" else "Anabel"
        A(f"fr_seal_{key}", f"""
        compare_var_to_value $MODE 1
        goto_if 1 singles
        setflag {flag_d}
        goto set
        singles:
        setflag {flag_s}
        set:
        say "{sp[name]["seal"]}"
        addvar $BP {bp}
        goto @fr_round_done
        """)
    # --- Seal case lines for the records board
    for m, (fs, fg) in (("s", (SEAL["SILVER_S"], SEAL["GOLD_S"])), ("d", (SEAL["SILVER_D"], SEAL["GOLD_D"]))):
        label = "Singles" if m == "s" else "Doubles"
        A(f"fr_seal_line_{m}", f"""
        checkflag {fg}
        goto_if 1 gold
        checkflag {fs}
        goto_if 1 silver
        say "{label}: no Seal yet."
        return
        gold:
        say "{label}: the Gold Seal, and the Silver before it."
        return
        silver:
        say "{label}: the Silver Seal."
        return
        """)

    # --- a finished round: Battle Points, then continue or retire
    bp = ["setvar 0x8008 3"]
    for k, thr in enumerate((14, 28, 42, 56, 70)):
        bp += [f"compare_var_to_value $STREAK {thr}", "goto_if 0 bp_go", f"setvar 0x8008 {4 + k}"]
    A("fr_round_done", "\n".join(bp) + """
        bp_go:
        buffernumberstring 0 0x8008
        bp_add:
        compare_var_to_value 0x8008 0
        goto_if 1 bp_done
        addvar $BP 1
        subvar 0x8008 1
        goto bp_add
        bp_done:
        say "Seven floors cleared! The ledger pays you {FD:02} Battle Points."
        ask "Keep climbing? The next floor is already humming."
        compare_var_to_value 0x800D 1
        goto_if 1 go_on
        goto @fr_retire
        go_on:
        setvar $STATE 1
        goto @fr_to_arena
    """)

    A("fr_lost", """
        loadword 0 $WIN
        callstd 2
        say "The stairs go down faster than they go up. Take a breath. The tower will wait."
        goto @fr_retire
    """, WIN=SPEECH_BUF[2])

    # --- leave the facility (restore the party, record the streak, back to the hall)
    A("fr_retire", """
        copyvar 0x8005 $PERM_LO
        copyvar 0x8006 $PERM_HI
        copyvar 0x8009 $PARK0
        copyvar 0x800A $PARK1
        copyvar 0x800B $PARK2
        callnative @fr_leave
        setvar $STATE 0
        compare_var_to_value $MODE 1
        goto_if 1 rec_s
        compare_var_to_var $BEST_D $STREAK
        goto_if 4 leave
        copyvar $BEST_D $STREAK
        goto leave
        rec_s:
        compare_var_to_var $BEST_S $STREAK
        goto_if 4 leave
        copyvar $BEST_S $STREAK
        leave:
        warp 31.3 $HX $HY
        waitstate
        end
    """, HX=HALL_DOOR[0], HY=HALL_DOOR[1])

    A("fr_arena_npc", """
        lock
        faceplayer
        say "..."
        release
        end
    """)

    # --- Records board
    A("fr_records", """
        lock
        faceplayer
        buffernumberstring 0 $BEST_S
        buffernumberstring 1 $BEST_D
        buffernumberstring 2 $BP
        say "Longest climbs: {FD:02} battles in Singles, {FD:03} in Doubles.{FB}You hold {FD:04} Battle Points."
        call @fr_seal_line_s
        call @fr_seal_line_d
        release
        end
    """)

    # --- BP shop (items offered one at a time; Yes buys, No shows the next). Neither checkitemspace nor additem's result reports a full pocket in this hack
    # (both say 1 and nothing is added), so success is confirmed with checkitem afterwards.
    items = json.load(open(os.path.join(DATA, "shop.json")))["items"]
    ids = {}
    for fnm in ("items2.json", "items.json"):
        for k, v in json.load(open(os.path.join(ROOT, "text/en/tables", fnm))).items():
            ids.setdefault(v.lower(), int(k))
    shop = ["lock", "faceplayer", 'say "Battle Points are the only currency the tower respects."',
            'ask "Care to browse the prize counter?"', "compare_var_to_value 0x800D 1", "goto_if 1 shop_0",
            'say "Come back anytime."', "release", "end"]
    for i, it in enumerate(items):
        iid, qty, price = ids[it["item"].lower()], it.get("qty", 1), it["price"]
        label = it["item"] + (f" x{qty}" if qty > 1 else "")
        nxt = f"shop_{i + 1}" if i + 1 < len(items) else "shop_end"
        shop += [f"shop_{i}:", f'ask "{label}: {price} BP. Buy it?"', "compare_var_to_value 0x800D 1", f"goto_if 1 buy_{i}", f"goto {nxt}",
                 f"buy_{i}:", f"compare_var_to_value $BP {price}", "goto_if 0 poor", f"additem {iid} {qty}", f"checkitem {iid} {qty}", "compare_var_to_value 0x800D 0",
                 "goto_if 1 full", f"subvar $BP {price}", f'say "{label} is yours."', f"goto {nxt}"]
    shop += ["shop_end:", 'say "That is everything. Come again!"', "release", "end",
             "poor:", 'say "Not enough Battle Points yet."', "release", "end",
             "full:", 'say "Your Bag is full."', "release", "end"]
    A("fr_bp_clerk", "\n".join(shop))
    return S


# --------------------------------------------------------------------------------------------------------------------------- extend
def extend(spec, ext):
    S = build_scripts()
    spec.setdefault("scripts", {}).update(S)
    groups = spec.setdefault("groups", {})
    first = len(groups.get("58", []))
    assert first == 5, f"group 58 has {first} maps; the Frontier arenas are 58.5-58.9"
    for key, srcmap, arrive, npc, *g in ARENAS + BRAIN_ARENAS:
        groups["58"].append({"name": f"Spectrum Arena ({key})", "clone": srcmap, "mapsec": ARENA_MAPSEC,
                             "events": {"objects": [{"local_id": 1, "gfx": g[0] if g else 71, "x": npc[0], "y": npc[1], "elev": 3, "movement": 0, "script": "fr_arena_npc"}]},
                             "map_scripts": {"frame": [{"var": VARS["STATE"], "value": 1, "script": "fr_arena_start"}]}})
    ae = spec.setdefault("append_events", [])
    ae.append({"map": CABIN, "edit": {"warps": {"0": {"to": HALL, "warp_id": 0}}}})
    ae.append({"map": HALL,
               "edit": {"warps": {"0": {"to": CABIN, "warp_id": 0}},
                        "objects": {"2": {"script": "fr_recep_doubles"}, "4": {"script": "fr_recep_singles"}}},
               "objects": [{"local_id": 9, "gfx": 166, "x": 17, "y": 12, "elev": 3, "movement": 0, "script": "fr_bp_clerk"},
                           {"local_id": 10, "gfx": 26, "x": 10, "y": 4, "elev": 3, "movement": 0, "script": "fr_records"}]})
    spec.setdefault("map_scripts", []).append({"map": HALL, "on_transition": "fr_hall_tr"})
    return spec


# -------------------------------------------------------------------------------------------------------------------------- finalize
def _record(cls, pic, music, name, double, ai, size):
    b = mt.encode_en(name)
    assert len(b) <= 12, name
    return struct.pack("<BBBB", 3, cls, music, pic) + b.ljust(12, b"\x00") + struct.pack("<4HIIII", 0, 0, 0, 0, double, ai, size, BLOCK)


def finalize(rom, src, pool):
    old = TRAINER_TABLE
    size = TRAINER_COUNT * 40
    assert _TABLE_AT is not None, "frontier_build.reserve(pool) must run before the text is relocated"
    new = _TABLE_AT
    rom[new:new + size] = rom[old:old + size]
    for i in range(EXTRA_SLOTS):                      # blank slots: empty name, no party
        rom[new + size + 40 * i:new + size + 40 * (i + 1)] = bytes([0, 0, 0, 0, 0xFF]) + bytes(35)
    lo = ROM_BASE + old
    delta = new - old
    words = array.array("I")
    words.frombytes(bytes(rom[:len(rom) // 4 * 4]))
    patched = 0
    for i, v in enumerate(words):
        off = i * 4
        if 0 <= v - lo < 40 and not (old <= off < old + size) and not (new <= off < new + size + EXTRA_SLOTS * 40):
            rom[off:off + 4] = struct.pack("<I", v + delta)
            patched += 1
    ids = json.load(open(os.path.join(DATA, "identities.json")))

    def donor(tid):
        e = bytes(src[old + 40 * tid:old + 40 * tid + 40])
        return e[1], e[3], e[2]                       # class, picture, music/gender byte

    def put(slot, tid, name, double, size, cls_override=None):
        cls, pic, music = donor(tid)
        if cls_override is not None:
            cls = cls_override
        a = new + 40 * slot
        rom[a:a + 40] = _record(cls, pic, music, name, double, 7, size)

    for i, (tid, name) in enumerate(ids["singles"]):
        put(SHELL_S + i, tid, name, 0, 3)
    for i, (tid, name) in enumerate(ids["doubles"]):
        put(SHELL_D + i, tid, name, 1, 4)
    for brain, (s, d) in (("Lance", SHELL_LANCE), ("Anabel", SHELL_ANABEL)):
        tid, name, *cls = ids["brains"][brain]
        put(s, tid, name, 0, 3, *cls)
        put(d, tid, name, 1, 4, *cls)
    # in-battle speeches: words 1 (the player won) and 2 (the player lost) of the first speech-table entry -> RAM buffers
    assert u32(src, SPEECH_ENTRY + 4) != 0 and u32(src, SPEECH_ENTRY + 8) != 0
    rom[SPEECH_ENTRY + 4:SPEECH_ENTRY + 12] = struct.pack("<II", SPEECH_BUF[1], SPEECH_BUF[2])
    return {"table_at": f"{new:07X}", "literals_repointed": patched, "shells": len(ids["singles"]) + len(ids["doubles"]) + 4}
