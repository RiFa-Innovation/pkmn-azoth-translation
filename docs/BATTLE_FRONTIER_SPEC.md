# Battle Frontier (River Edition): design and technical spec

Status: **draft 1, 2026-10-21. Nothing here is built yet.** Branch `feat/battle-frontier`, forked from
`feat/chapter-2-rainbow` (the River Edition line, tag `river-v0.1`). Read `CLAUDE.md` ("New content") and
`ROADMAP.md` first; this spec uses the same tooling (`mapedit.py`, `scrasm.py`, `mapdrive.py`).

Labels used below: **[V]** verified in this repo/ROM on 2026-10-21, **[D]** from the vendored FireRed decomp
(`utilities/pokefirered`, vanilla behaviour: the hack's CFRU engine may differ), **[?]** unverified assumption that
a spike (section 11) must settle before the dependent work starts.

Credit rule (same as the rest of the River Edition): this is fan-made content added by River with Claude on top of a
translation. The hack, its name, characters and story belong to their original authors. All release text says so.

---------------------------------------------------------------------------------------------------------------

## 1. Goal and scope

A post-game facility in the spirit of Emerald's Battle Frontier, built from what the hack and FireRed already contain.

**MVP (this spec's target):** the **Battle Tower** with **Singles (3v3)** and **Doubles (4v4)**, all **Lv 50**, the player's own
Pokémon, **7-battle rounds**, a **Brain** at battle 21 and 49 (Silver and Gold Symbols), **Battle Points (BP)** and a **BP shop**,
streak records. Opponents are generated from a pre-built pool of sets (section 7).

**Later phases (not designed in detail here):** Battle Pyramid/Pike-style chain rooms, Factory (rentals), more Brains/Symbols,
quest-board entries, Hoenn-flavoured cameo cast.

**Out of scope:** new tilesets, new music, new Pokémon, link/multi battles, e-Reader. Anything needing them is cut.

## 2. What already exists (so we reuse, not rebuild)

The original authors planned this and left pieces behind. All **[V]** (ROM `roms/Pokemon Mercury 1.3.3 (patched).gba` and
`hackdb.py`):

| Piece | Where | Notes |
|---|---|---|
| Map-name entries **Battle Frontier** (id 219 = 0xDB) and **Battle Tower** (220 = 0xDC) | name table at `0xC2B000` | 0xDC has **zero maps**; 0xDB has one (`31.3`) |
| **Lobby-sized interior `31.3`** (20x22, reception ring, two stairways, 8 NPC slots, region Battle Frontier) | header `0x351AFC`, layout id 8 | Warp #0 `(10,18)` targets **`54.12`, which does not exist** (dangling); warp #1 `(2,20)` -> `31.4`. Looks like the intended Frontier hall |
| **Vermilion ferry offer** "Would you like to go to the Battle Frontier?" | `49.6` obj#0, script `0x08A68865` | Gated on flag `0x14DA` (set in the player's house, `43.0`, by the Ashida scene); on "yes" runs `special 0x17B` (4 uses in the hack, **destination [?]**). The ferry also carries the Navel Rock route used by Chapter 2 beat 13 |
| NPC lore lines | strings `0x087BFB1C` (31.3 obj#1: "There used to be just a single Trainer Tower here ... rebuilt into the Battle Frontier") and `0x09DBF8DE` | confirms the intent: **Trainer Tower -> Battle Frontier** |
| **Orphan Battle Tower texts** | `0x09DC014B` ("Welcome to the Battle Tower! ... Multi 64 / Multi 66 battle rooms"), `0x09D9DB5D`, `0x09D9DC08` ("... the Battle Tower Master ... I am Lance the Dragon Master"), `0x09D9EFE7`, `0x09DBF8FF` | referenced only by code/tables hackdb cannot reach (`who` = no entry). **Lance is already written as the Tower Master**: use him as the Brain |
| **Vanilla Trainer Tower**: 11 maps `2.1`-`2.11` (lobby `2.10`, floors `2.1`-`2.8`, roof/elevator `2.9`, `2.11`), region 0xB3 | `scripts/hackdb.py map 2.1` | vanilla scripts at `0x081C....` intact; unlinked from the world (like Navel Rock) |
| BracerPoints + shop | Guild terminals, strings "BracerPoints Shop" | native code (`callnative 0x089B6451` adds points). We do **not** reuse it (section 9) |
| Mega Evolution, Megas for Kangaskhan/Latias/Audino/Diancie only; 1,445 species | `STORY_PLAN.md` section 11 | the species pool is large; Megas are rare |
| Engine support for facility battles **[D]** | `BATTLE_TYPE_TRAINER_TOWER` / `BATTLE_TYPE_BATTLE_TOWER` flags; `ChooseBattleTowerPlayerParty`/`ReducePlayerPartyToThree`; `DoTrainerTowerBattle` | with these flags the engine **skips `CreateNPCTrainerParty`** (enemy party must be pre-filled), gives **no EXP, no prize money, no whiteout**, and returns to the script with the outcome. Opponent name/pic/speech come from a RAM struct (`TrainerTower`), not the trainer table |

Free resources **[V]**: `insert.py` free pool 0.67 MB (`free_after` 674,725 B after Mt. Silver); flags `0x1388`-`0x13FF`
unused by any script and outside `0x1338`-`0x1387` (Chapter 2 reservation); hack variables `0x5121`-`0x5132` unused by any script
and inside the already-used `0x5100`-`0x51D5` span (so inside the hack's var array for certain); trainer table has 743 entries, ~30
unreferenced empty-name slots after River's reservations (`CLAUDE.md`: 48-51, 60-63, 68-71, 73-77, 113, 147, 200, 210-212, 217,
263, 291, 306, 376, 454-461, 492-497; many already taken, section 6).

## 3. Rules (Emerald-faithful, adapted)

- **Level 50 for everyone.** Player's chosen Pokémon are scaled to exactly 50 (below 50 are raised, above are lowered); opponents are
  generated at 50.
- **Singles:** pick 3 of your party; 3v3. **Doubles:** pick 4; 4v4 with two on the field.
- **Species Clause** (no duplicates in your team), **Item Clause** (no duplicate held items in your team). Same for opponents.
- **Banned for the player:** Eggs; the "uber" list in `data/frontier/pool.json` (initially: Mewtwo, Lugia, Ho-Oh, Kyogre, Groudon,
  Rayquaza, Arceus, Dialga/Palkia/Giratina, Zacian/Zamazenta/Eternatus, Koraidon/Miraidon, Mega Rayquaza, anything with BST >= 680 and
  the hack's own "boss" forms). Up to **one** sub-legendary allowed. Final list is data, not code.
- **No items from the Bag in battle** (engine flag for facility battles already blocks it **[D]**); held items work.
- **Megas allowed** (stone + the hack's existing Mega rule), **no Z-moves/Dynamax** (the hack's G-Max forms are not allowed).
- **Saving:** the game saves between battles (the standard "Would you like to save?" prompt after each win). Resetting or quitting
  during a round ends the round (streak lost) when the save is reloaded, as in Emerald.
- **Rest between battles:** full heal automatically after each win (Emerald behaviour).
- **Rounds:** 7 battles per round. The streak counter counts wins across rounds; after battle 7 you may continue or retire.
- **Brain:** at streak 21 (Silver Symbol) and 49 (Gold Symbol), the battle is against **Lance, the Tower Master** (Lance's team is
  hand-built, 6 sets, 3 or 4 used per battle, one holds a Mega Stone if the hack's Dragonite/Charizard line allows it
  **[?]**, else Dragon-type signature set). A second, tougher Lance team after Gold.
- **Retire/Lose:** BP for completed rounds only; lose = streak to 0, record kept.

## 4. World layout

Entry stays within the existing story: the **Vermilion ferry (49.6)**, post-Champion, is the door (it already offers "go to the Battle
Frontier?"). Chapter 2 beat 13 ("Navel Rock") also uses this ferry; the Frontier option must not disturb it (the NPC branches on
`CH2_STAGE` and `FRONTIER_UNLOCKED`).

| Map | Plan | Source |
|---|---|---|
| **Frontier Hall** | `31.3` becomes the hub: Battle Tower reception (2 counters: Singles/Doubles), BP shop clerk, Records board, Heal NPC, a Symbol-case NPC | existing `31.3` (re-targeted warps, new events) |
| **Ferry arrival** | **`31.6`**, the ship-cabin lounge the ferry already sails to (S2); its door `(8,1)` is retargeted from the dangling `54.12` to the hall `31.3` | existing map, 1 warp edit |
| **Battle Tower lobby + elevator** | reuse **vanilla Trainer Tower lobby `2.10`** and elevator `2.11` as the tower's ground floor and lift | existing maps (relink warps; `mapedit` `edit`) |
| **Battle rooms** (the colour floors) | **five themed arenas cloned from the Elite Four chambers** (layout ids 213, 214, 215, 216, 217: ice/lavender `1.75`, starry psychic `1.76`, lava `1.77`, teal-dark `1.78`, champion gold `1.79`; 16x22, one stairway in, no encounters). Each clone is a *new map header in group 58 with fresh events* (a door warp, one challenger NPC, the coord trigger); the originals' E4 scripts and `ON_FRAME` hooks are **not** copied. Floors share rooms by theme (below) | `mapedit` layouts/maps; ~100-200 B each |
| **Brain room** | the champion-gold arena for Lance (21) and Anabel (49); distinct NPC sprite (`119` Lance, `136` Anabel) | reuse |

The hall and the tower share the hub: reception NPC -> `fadescreen` -> `warp` to the battle-room map; the room's coord event starts the
fight. Total new maps for MVP: **5** arena clones (+ 0 for the arrival: `31.6` exists). New map ids go in **group 58** (`58.5`-`58.9`; slot 59 is the
terminator); **no new layout ids are needed** because the arenas reuse the Elite Four layouts (ids above) unchanged. Add `58.5`-`58.9` to the reservation list in `CLAUDE.md`.

### Entry gating

Flag `FR_UNLOCKED (0x1388)`: set the first time the player says "yes" to the ferry offer after the Champion flag `0x14DB`.
Until then the Frontier is silent. The `49.6` script is repointed (`0x08A68865` -> new script that checks `0x14DB`, offers the trip,
sets `0x1388`, fades, warps to `31.3`). The return trip is a reception NPC "Back to Vermilion?".

## 5. Facility flow (state machine)

States are stored in **save-persistent hack vars** so a reload mid-challenge (or after a loss/reset) is recoverable.

```
FR_IDLE -> (Singles|Doubles chosen) -> FR_SELECT -> FR_FIGHT(n=1..7) -> FR_WON_ROUND -> {continue -> FR_FIGHT | retire -> FR_IDLE}
                                           |_ on any loss, reset, or map reload outside the facility -> FR_RESTORE -> FR_IDLE
```

Per battle `n` (counting the streak, not the round): `n % 7 == 0` -> round-end prompt; `n == 21` or `n == 49` -> Brain battle.
Every state transition is a `scrasm` script; the only native code is the helpers in section 6.

## 6. Technical design

### 6.1 Variables and flags (reserve in `CLAUDE.md` when built)

Vars `0x5121`-`0x5132` (18, inside the proven array): `FR_MODE` (0 idle, 1 singles, 2 doubles), `FR_STATE`, `FR_STREAK` (current),
`FR_ROUND_BATTLE` (1-7), `FR_SEED_LO`, `FR_SEED_HI` (32-bit challenge seed), `FR_PICK_A/B/C/D` (party slots chosen),
`FR_PERM_LO/HI` (6x3-bit original party order, section 6.3), `FR_PARTY_COUNT`, `FR_BP` (16-bit Battle Points, max 9999),
`FR_BEST_S`, `FR_BEST_D` (records), `FR_SYMBOLS` (bit0 Silver, bit1 Gold).

Flags `0x1388`-`0x13A7`: `FR_UNLOCKED`, `FR_ACTIVE` (party currently mutated), `FR_SILVER`, `FR_GOLD`, `FR_BRAIN_TALK_SEEN`, per-shop-item
"bought once" flags, per-scene "seen" guards. Set via the game's own `setflag` (hack flags >= 0x900, `CLAUDE.md`).

Add to `HACKDB` notes: `hackdb.py note add var:0x5121 "Battle Frontier ..."` per var.

### 6.2 Native helpers (Thumb, free pool, called with `callnative`)

All routines are small Thumb functions assembled with `arm-none-eabi-as -mcpu=arm7tdmi` (the toolchain already used for tests,
`CLAUDE.md` "Script injection"), inserted into the free pool by a new `scripts/frontier.py` stage of `insert.py`, and invoked by
scripts through `callnative ADDR|1` (the hack already does this: `callnative 0x089B6451`). No `special` table edit is needed.

| Routine | Does | Inputs (vars) / output |
|---|---|---|
| `fr_pick_party` | opens the party menu in "choose 3/4" mode, returns the order (vanilla `ChooseBattleTowerPlayerParty` is the model **[D]**; may be callable as-is **[?]**) | out `gSpecialVar_Result` 0/1, picks in `gSelectedOrderFromParty` |
| `fr_enter` | validate picks (species/item clause, bans, no Eggs), **reorder and truncate** the party, **scale to Lv 50** (6.3) | `FR_PICK_*` -> `FR_PERM_*`, `FR_PARTY_COUNT`, sets `FR_ACTIVE` |
| `fr_gen_opponent` | builds one opponent: RNG from seed+battle number, fills `gEnemyParty` and the opponent RAM block (name, class, pic, speeches) | in `FR_SEED_*`, `FR_STREAK`, mode -> `gEnemyParty` |
| `fr_start_battle` | sets `gBattleTypeFlags` and starts the battle like `DoTrainerTowerBattle` **[D]** | out `gBattleOutcome` -> `gSpecialVar_Result` |
| `fr_heal` | full heal of the 3/4 party | |
| `fr_leave` | **restore**: un-permute the party, recompute levels from EXP, restore the count, clear `FR_ACTIVE` | idempotent: safe to run any number of times |

### 6.3 Level 50 without a backup copy (built and verified in M3, 2026-10-21)

Do **not** copy the party to a backup area. The design that survived contact with the engine:

- **Scale in is not "set the level, then CalculateMonStats".** The engine's `CalculateMonStats` starts with `level = GetLevelFromMonExp(mon);
  SetMonData(LEVEL, &level)`, so it would put the level straight back. `fr_scale_mon` instead writes the **level byte and the six stats
  directly** with the engine's own formula (`((2*base + IV + EV/4) * L / 100) + 5`, then `ModifyStatByNature`; HP `... + L + 10`, Shedinja 1), reading
  base stats from the hack's table (`0x176DFBC`, 28-byte entries), IV/EV through `GetMonData`, and the nature through the engine's `GetNature` /
  `ModifyStatByNature` (vanilla addresses, still valid in the hack). The formula was checked against the game's own stats at the real level
  for every party member before trusting it (test A) and matched exactly.
- **Scale out is stateless:** `CalculateMonStats` (level from EXP, stats from level) puts the true values back, followed by `HealPlayerParty`.
  Nothing about the original levels is stored. EXP is never touched, and facility battles give none (6.4).
- **Truncate, permute and hide:** the picks move to slots 0..n-1 (in pick order) and `gPlayerPartyCount` is set to n. The other mons stay in slots n..5 *but are hidden*:
  the party menu lists every occupied slot (found in the first end-to-end fight: the unpicked Grotle was selectable), so `fr_enter` parks each one's species in its
  unused HP field and clears the species; `fr_leave` puts the species back before the recalculation. The
  original order is a permutation packed into two hack vars: **LO** = original index of slots 0-4, 3 bits each; **HI** = slot 5 | original count << 3 |
  **bit 15 = "mutated" marker**. `SavePlayerParty` copies all six slots, so a save inside the facility loses nothing (test C).
- **`fr_leave` is idempotent:** it does nothing unless HI has bit 15, and clears HI on the way out, so a cleanup that fires twice (or a loss path plus a
  map-transition cleanup) cannot scramble the party (test E).
- **Cleanup guarantee** (the Sprout Tower pattern, `CLAUDE.md`): the hall map's `ON_RESUME` and every other map's `ON_TRANSITION` run "if marker set and the
  map is not a facility map -> `fr_leave`".

**Interface** (`scripts/frontier_native.s`, entries at `+0 fr_enter`, `+4 fr_leave`, `+8 fr_heal`; call with `callnative <base+off>|1`). Arguments and
results travel in the script special vars, because natives cannot read hack vars: set `0x8000 = n` and `0x8001...` = pick slots, `callnative`, then
`copyvar FR_PERM_LO 0x8005`, `copyvar FR_PERM_HI 0x8006`; `0x800D` = 0 ok, 1 bad count or slot, 2 duplicate pick, 3 egg or empty slot (party untouched on
any error). For `fr_leave`, `copyvar 0x8005 FR_PERM_LO`, `copyvar 0x8006 FR_PERM_HI`, `callnative`, `copyvar FR_PERM_HI 0x8006` (now 0). 884 bytes. **The game
zeroes `0x800D` when a script ends, so a script must read the result before `end`** (the test copies it to `0x8008`).

**Verified** (`scripts/spikes/frontier_m3_test.py` on `Azoth.sav`, 32 checks): formula equals the game's stats for all four mons (A); error cases leave the
party byte-identical (F); singles picks [2,0] -> count 2, picks in front in pick order, the other two mons byte-identical, both at Lv 50 with stats equal to the
formula and full HP (B); Save/LoadPlayerParty round trip keeps the 6 slots and the count (C); `fr_leave` restores order, level, stats, EXP, EVs, IVs and moves exactly
and heals (D); a second `fr_leave` changes nothing (E); doubles with four picks in reverse order and full restore (G). Then in a real fight with the `BATTLE_TOWER`
flag (6.4) the lead showed **Gastly Lv 50, 102/102 HP, 15/15 PP**.

**Facts learned:** this hack stores party Pokémon **unencrypted, with the four substructures in fixed Growth-Attacks-EVs-Misc order and a zero checksum**
(species at +32, EXP at +36, EVs at +56, IVs bit-packed at +72, level at +0x54, HP/stats at +0x56.. as vanilla), so party data can be read and compared directly.
Species ids are national dex numbers (Croconaw = 159). Edge cases not yet tested: a Pokémon holding a Mega Stone, a Pokérus carrier, a fainted pick at 0 HP
(the heal handles it), a party of fewer than the picks (rejected by code 1).

### 6.4 Starting a battle (decided: mechanism **M3**, verified on 2026-10-21)

The facility battle needs: opponent party generated at run time, **no EXP**, **no money**, **no whiteout**, a trainer class/name/pic, and the
script continuing afterwards with the outcome. **Chosen mechanism (M3):**

1. A **shell trainer slot** (class, pic, name, AI, party size; reserved ids, section 6.1) whose `party` pointer points at an **EWRAM scratch
   block** (`partyFlags = 3`, 16-byte items+custom-moves entries, `mapedit.add_trainers` layout).
2. `fr_start_battle` (Thumb) writes the party block, sets `gTrainerBattleOpponent_A = <shell id>`, `gBattleTypeFlags = TRAINER | BATTLE_TOWER
   (0x108)`, and starts the battle like `DoTrainerTowerBattle` does (`CreateTask(Task_DoTrainerTowerBattle)`, `PlayMapChosenOrBattleBGM`,
   `BattleSetup_GetBattleTowerBattleTransition`, `BattleTransition_StartOnField`; all at their vanilla addresses). CFRU's
   `CreateNPCTrainerParty` then builds the enemy party from the slot's party pointer.
3. The script waits (`waitstate`) and resumes after `CB2_EndTrainerTowerBattle` returns to the field; the outcome is in `gBattleOutcome`
   (`0x02023E8A`).

**Verified in the emulator** (stub + `Azoth.sav`): the intro read "Bug Catcher Kanta wants to battle!" with the trainer sprite, the
flag word stayed `0x10C` through the whole fight, "Foe Kricketot fainted!" / "Player defeated Bug Catcher Kanta!" appeared, **no "gained Exp.
Points" and no prize-money line**, the trainer's defeat speech was printed *inside* the battle, and the game returned straight to the overworld
(script finished). `Cmd_getexp` in the hack is vanilla except for one literal, so the EXP skip comes from the `BATTLE_TOWER` flag as in the decomp **[D]**.

**Still to verify** (M4): a **loss** (no whiteout?), a **double** battle (`| DOUBLE`), and that CFRU reads an **EWRAM party pointer**.
The speech lines come from a CFRU per-trainer speech table (the orphan "Battle Tower Master" strings are in it): locate it (reference to the
"I lost... What a splendid battle..." string) and add or repoint entries for our shell slots (12.3).

**Rejected:** `BATTLE_TYPE_TRAINER_TOWER` (the vanilla Trainer Tower type). In this hack it garbled the battle text buffers (class/name read
through the vanilla Trainer Tower struct overflowed into `gBattleTypeFlags`, which sits right after the string buffers), showed the
player as "Leader Falkner", and dropped the trainer flag, so the fight became a "Wild" battle. `BATTLE_TYPE_TRAINER_TOWER` stays off.

### 6.6 Opponent generation and battle start as built (M4, 2026-10-21)

**Natives** (one 1,680-byte image, no static data, linked by `scripts/frontier_native.py`: entry table `scripts/native/frontier_entry.s`, `fr_enter/fr_leave/fr_heal` in
`scripts/frontier_native.s`, the generator in C `scripts/native/frontier_gen.c` built with `arm-none-eabi-gcc -mthumb -Os -ffreestanding`, `fr_start_battle` in `scripts/frontier_start.s`).
Entries, called with `callnative <base + off>|1`: **+0 fr_enter, +4 fr_leave, +8 fr_heal, +12 fr_gen_opponent, +16 fr_start_battle**.

- `fr_gen_opponent` (in: `0x8000` battle number n, `0x8001` doubles flag, `0x8002/3` seed; out: the party block at `0x02022400`, `0x8004` = Pokémon count, `0x8005` = a random word for
  the script to pick a trainer identity). Pure function of (seed, n, mode). Tier: round = (n-1)/7, tier = min(4, 1 + round), +1 on the round's last battle; 30% of picks come from one tier lower.
  Clauses: no duplicate species or items, at most one legendary and one Mega per team, no boss-only sets. Doubles use each set's doubles list (Protect swapped in). IV byte 255 (= all 31).
  Sets come from `build/frontier/sets.bin` (`pack(header=True)`: 20-byte tier index, then 24-byte records sorted by tier); M5 links the table into the ROM.
- `fr_start_battle` (in: `0x8000` shell trainer id, `0x8001` doubles flag): `gTrainerBattleOpponent_A`, `gBattleTypeFlags = TRAINER | BATTLE_TOWER (| DOUBLE)`, then the vanilla tower
  battle sequence. Two **shell trainer slots** (singles: party size 3, doubles: size 4, `double` field set) hold class, name, picture and AI; their party pointer is the RAM block.

**Verified in the emulator** (`scripts/spikes/frontier_m4_e2e.py`, `frontier_m4_test.py`): (a) CFRU builds the enemy party from a trainer record whose party pointer is in **EWRAM**,
with the custom moves and held items (Leftovers visibly restored HP), levels from the block, and the AI switching ("withdrew Venusaur!", "sent out Alakazam!"); (b) a **win**:
no "gained Exp. Points", no prize money, the defeat speech printed inside the battle, straight back to the script; (c) a **loss** (only the lead alive): outcome 2, **no whiteout**, the
player stays on the same tile, the lose speech shows; (d) **doubles** (flags `0x10D`): two foes out, Intimidate triggers; (e) the full chain
`fr_enter` -> `fr_gen_opponent` -> `fr_start_battle` on a real save: the party menu shows only the three picks, opponents differ per seed and battle number (survey of battles
1, 5, 7, 8, 14, 15, 22, 30 and 50 for singles and doubles: tiers climb, doubles lists swap in Protect, clauses hold).

**Speech text.** The engine prints the opponent's end-of-battle speeches from the first entry of the orphaned Battle Tower trainer table (`0x1DEC3A0`, 52 bytes; **word 1 = the
speech when the player wins, word 2 = when the player loses**, word 0 is the table's own intro text). The ROM words point at ROM text, but they can point at **RAM**, so M5 points them at two EWRAM
text buffers that the script fills per opponent (verified: "The Shell wins. Better luck next time." appeared on a loss). The pre-battle intro is printed by the script before the call.
Nothing else in that table is read by this path (the table is not indexed by trainer id; every test, with ids 76, 100 and 459, used entry 0).

**The "rest." line was a translation bug, not ours.** The second intro message ("X sent out Y!") was garbage ("rest.", "right type, I guess.") in every battle, tower or not, even
for an untouched NPC trainer; the original Chinese ROM prints it correctly. Cause: CFRU picks between two strings by `literal - (imm+1)` and the English relocation broke the spacing.
Fixed on `main` (PR #107, issue #105, PLAYTEST 89); **this branch needs that fix merged in** (or the same `insert.py` step) before Frontier battles read correctly. Also learned the
`BATTLE_TYPE_TRAINER_TOWER` bit (1<<19) is not needed and stays off; `BATTLE_TOWER` (1<<8) alone gives the no-EXP/no-money/no-whiteout behaviour.

**Still open for M5:** per-battle money/EXP are none (good), but the trainer *defeated* flag of the shell ids is set on a win (harmless, never used by an NPC); a Mega Stone on an opponent
and Mega Evolution of the player's own Pokémon in these fights were not exercised; EV spreads and natures are not applied (the block format has no field for them), so the opponent sets rely on
IV 31 only; the intro `trainerbattle`-style overworld speech is not used (we start the battle natively).

### 6.7 M5 as built: the playable MVP (2026-10-21)

`scripts/frontier_build.py` (hooked into `mapedit.apply()` when `data/new_maps.json` has `"frontier": true`) does everything: `reserve()` takes one 31 KB run for the moved trainer
table at the very start of `insert.py` (the free pool is too fragmented later: biggest run ~24 KB), `link()` writes the set table, the speech table and the 1,868-byte native image into the pool,
`extend()` adds the arenas, hall/cabin edits and 19 scripts, and `finalize()` moves the trainer table (**743 -> 775 slots; 25 literal words that point into the first 40 bytes of the old table
are repointed**, found with a window rule because random compressed-data words matching the whole range would be false positives), writes the 28 shell opponents and aims the speech
table's words 1/2 at the RAM buffers. New: map-script tables on new maps (`"map_scripts": {"frame": [...]}` in `mapedit`), `ask "text"` in `scrasm` (Yes/No box), and the missing
string-var byte of `buffernumberstring` / `bufferitemname`.

| Piece | Result |
|---|---|
| Cost | sets 21 KB + natives 1.9 KB + speeches 0.2 KB + the table move 31 KB + scripts/maps ~97 KB (with Mt. Silver); `free_after` 562,143 B; `insert.py` `missing 0, too_long 0, errors 0`; BPS byte-identical |
| Existing trainers after the table move | verified: a real NPC fight (Bug Catcher Kanta) reads and plays normally |
| Map layout | arrival cabin `31.6` (door retargeted) <-> hall `31.3` (south door retargeted; singles counter at (4,4), doubles counter at (15,4), BP clerk at (17,12), records at (10,4), the original nurse/lore NPCs kept) <-> arenas `58.5`-`58.9` (clones of the Elite Four chambers: ice, psychic, fire, dark, gold) reached by script warps |
| Floor -> arena | Red=fire, Orange=gold, Yellow=gold, Green=dark, Blue=ice, Indigo=psychic, Violet=psychic |
| Flow | counter -> register (Yes/No) -> pick 3 or 4 in the party menu (`special ChoosePartyMon` once per pick) -> `fr_enter` -> warp to the floor's arena -> the arena's **frame-table script** (var `STATE == 1`) announces the floor, calls `fr_gen`, `fr_speech`, picks one of 12 shell identities, prints the opponent's intro line from RAM, `fr_heal` (re-scales and heals), `fr_start`, then resolves the battle -> win: `STREAK += 1`, next arena (or, after 7, BP award and "keep climbing?") -> retire/loss: `fr_leave`, record the streak, warp to the hall |
| Verified in the emulator (`scripts/spikes/frontier_m5_drive.py`) | hall dialogue, singles registration (3 picks) and doubles (4 picks, double battle: "Dragon Tamer Draco sent out Jumpluff and Kadabra!"); three consecutive wins with the picks staying Lv 50 (streak 0 -> 1 -> 2); round complete at 14: "Seven floors cleared! The ledger pays you 4 Battle Points." then the prompt; **retire restores the party exactly** (original order, levels, EXP-derived stats, the hidden Grotle) and records the best streak (14); BP counter buys the 20-BP Leftovers (30 -> 10); the records board text; cabin door <-> hall door; **the hall's entry hook repairs an abandoned challenge** (warp in with `STATE = 1`: party restored, state cleared) |
| Second verification pass (same day) | **the lost branch**: the paused script was redirected to `fr_lost` (the driver's `hijack`), the climb ended, the party came back exactly (original order, levels, HP, hidden Pokémon), the player was in the hall, `STATE` 0, no best-record change for a 0 streak (a genuine engine loss was verified in M4: outcome 2, no whiteout, script resumes); **the ferry offer**: `49.6` with flag `0x14DA` asks "Would you like to go to the Battle Frontier?", Yes plays the sailing scene and arrives in the cabin `31.6`; **shop**: "Not enough Battle Points yet." at 5 BP, the whole catalogue walked with "No", the 64-BP Mega Stone bought (200 -> 136, "Mega Stone is yours.", "That is everything. Come again!"); **re-entering an arena with the challenge active** (what loading a save made in an arena does) regenerates the identical opponent team from the seed; seeds now vary (53925/1677, 21548/43044, 51134/34994); an unattended lazy-player climb reached battle 18 (two round rewards, BP 7) with the picks at Lv 50 throughout |
| Still not exercised | the **bag-full** branch (the Bag could not be filled with script gifts, 480 item ids; the branch is the standard `checkitemspace` + message), a Mega Stone worn by an opponent or by the player in these fights, a real save made inside an arena and reloaded through the title screen |

**Facts learned while building it**
- A tower-flag battle resets the picks' stats to their real level afterwards (cause not traced), so `fr_heal` now re-applies Lv 50 and the script calls it before every fight.
- Hidden Pokémon: nothing may be parked inside the struct (the HP field is rewritten by battle code, and the padding word at +30 holds hack data), so `fr_enter` returns their species in `0x8009`-`0x800B`; scripts keep them in hack vars `0x5127`-`0x5129` (the pick vars, free once `fr_enter` has run) and hand them back to every `fr_leave`.
- The party menu remembers its cursor between picks; a driver (or a player) must not assume slot 0.
- **`random` with a large limit is badly skewed in this hack** (`random 65535` returned 0-25 almost every time; `random 256` and `random 100` are uniform). The challenge seed is therefore built from `random 256` calls (`fr_make_seed`: `lo + 256 * random(256)` per 16-bit half); seeds now come out like 53925 / 1677 and 21548 / 43044. Any future script that needs a wide random number must do the same.
- The first arena script runs from the map's frame table (after the fade-in), which is why an intro line can be printed without a coord trigger.

### 6.5 Opponent look-and-feel

Opponents are tower classes ("Ace Trainer", "Cooltrainer", "Pokémaniac", "Gentleman", "Lass", ...). Facility classes use
`gTrainerClass` ids (names already translated in `text/en/tables/trainer_classes.json`) and trainer pics (`0x23957C`, 148 pics). The
pool of 24 classes x 2 genders is encoded in the generator. Names: a 120-name list (JSON, `data/frontier/names.json`) so a name does not
repeat inside one round. Speeches: 40 intro + 40 victory + 40 defeat lines, authored by us (a first draft for River to rewrite; same
"drafts for the owner" convention as the Chapter 2 dialogue).

### 6.8 M6 as built: the Brains and Seals (2026-10-21)

- Battle 21 is **Lance** (arena `58.10`), battle 49 is **Anabel** (`58.11`); both are clones of the gold arena with their own NPC sprite. `fr_to_arena` routes streak 20/48 there and `fr_arena_start` hands over to `fr_brain_lance`/`fr_brain_anabel`. Anabel's intro changes after the River Edition's Chapter 2 (flag `0x134F`).
- Brain teams come from `fr_gen_brain` (Mega holder always first, partial Fisher-Yates for the rest, from the 6 Lance/Anabel sets each; doubles use the doubles moves); speech from `fr_brain_speech` (two ROM pointers per Brain into the RAM buffers). Shell slots 767-770.
- A win runs the shared `fr_won` (heal, streak +1); at 21 and 49 it goes to `fr_seal_silver`/`fr_seal_gold`: flags `0x1389` Silver singles, `0x138A` Gold singles, `0x138B`/`0x138C` doubles, +10 / +20 BP, then the normal round reward. The records NPC shows the Seal per mode.
- **Bug found while testing:** the entry stubs hold absolute addresses, but the image was linked at `0x08000000` (the old branch-only stubs were position independent). `link()` now relinks at the final address. Symptom: script frozen right after `callnative fr_enter`.
- Verified in the emulator (`frontier_m5_drive.py`, streak poked to 20/48): Lance's team (Mega Dragonite lead) and speeches, defeat -> Silver Seal text, BP 14 (10 + round 4), records "Singles: the Silver Seal."; Anabel's intro, psychic team, win -> streak 49, BP 26 (20 + round 6). Not exercised: the Brain loss path, doubles Brains, Gold Seal text screenshot.
- Cosmetic: Anabel's donor class prints as "Int'l Police"; give her an own class name when the identities file is revisited.

## 7. Party generation (sources, pipeline, tuning)

### 7.1 Principles

- **Pre-bake at build time, choose at run time.** A Python generator turns ROM data into a flat table of **sets** shipped in the ROM.
  The native `fr_gen_opponent` only does: seeded random choice of sets from the tier for this battle, plus clause checks. This keeps
  the native code tiny, the data inspectable, hand-editable and unit-testable offline.
- **Deterministic per challenge.** The seed is chosen when the round starts and stored in `FR_SEED_*`; opponent `n` is a pure function
  of `(seed, n, mode)`. Reloading a save in the middle of a round gives the same opponents (no save-scum rerolls).

### 7.2 Sources

All data comes from **this ROM** (so IDs, move changes and fan modifications are correct) plus text lists we write:

| Need | Source | Status |
|---|---|---|
| Species list, names, sprite/icon presence | `text/en/tables/species.json`, `data/ref/species_names.csv`; sprite audit in `ROADMAP.md` (1,293 sprite entries) | **[V]** exists |
| Base stats, types, abilities, EV yield | the hack's species data table (CFRU `gBaseStats`), extend `scripts/species_peek.py`'s name-table finder | **[?]** address not yet mapped (spike S1) |
| Level-up learnsets (by level) | CFRU learnset pointer table | **[?]** S1 |
| TM/HM/tutor compatibility | CFRU TM compat table | **[?]** S1 |
| Move data (power, accuracy, type, split, effect, PP, priority) | the hack's move table (`gBattleMoves`, names at `0x1D97378`) | **[?]** S1 |
| Item ids/names | `text/en/tables/items.json`, `items2.json` | **[V]** |
| Evolution table (ids > 411 not located, `ROADMAP.md`) | needed for "fully evolved" filtering | **[?]** S1; fallback: a hand-written `nfe.json` list |
| Behavioural reference: Emerald's tower rules and tiers | public documentation only (rules/values), **no data copied** from `pokeemerald` or Smogon; set contents are generated or authored by us | n/a |

`scripts/frontier_data.py` reads these into `build/frontier/db.json` (not committed; the ROM-derived data stays out of git like
all ROM bytes).

### 7.3 Species pool

`data/frontier/pool.json` (committed, hand-reviewed, **no ROM bytes**): `allow` rules + explicit `ban` and `force` lists.

- Eligible: fully evolved, **plus** NFE species whose evolution item/method is not reachable in Lv 50 context (Chansey, Scyther line
  with Eviolite) only when an Eviolite-style item exists **[?]**; otherwise fully evolved only.
- Excluded: Mega/Primal/G-Max/event-only forms (forms enter only through stone-holding sets), uber list (section 3), species with no
  usable battle sprite or icon (checked against the audit), species whose moveset cannot reach 4 usable moves.
- Tier tags by BST and legality: `T1` (BST <= 480, mostly NFE-looking, early rounds), `T2` (480-540), `T3` (540-600), `T4` (>= 600 non-uber and
  Mega bearers), `BOSS` (Brain-only). A species may appear in several tiers.

### 7.4 Set builder (algorithm)

For each eligible species `S` and each of up to 2 **roles** (physical sweeper, special sweeper, bulky attacker, support/utility, speed
control), build one set:

1. **Role fit.** Score = how well stats match the role (Atk vs SpA, Spe, HP+Def+SpD). Keep roles with score >= threshold.
2. **Legal moves.** `learnset(<= 50) ∪ TM/HM ∪ tutor ∪ egg-move list if present`. Remove: OHKO, Self-Destruct/Explosion (tier-limited),
   Focus Punch, Counter/Mirror Coat in singles-only, moves with "fails often" effects, bad two-turn moves for early tiers.
3. **Attack picks.** Best STAB move by `power x accuracy x STAB x split-fit`; second best STAB of the other type if any; one coverage
   move that hits the types the STAB moves resist or fail against; avoid duplicate types of coverage.
4. **Utility pick** by role (Protect in doubles, recovery for bulky, Swords Dance/Nasty Plot/Calm Mind for sweepers, status or screens for
   support, Fake Out/Tailwind in doubles).
5. **Ability** from a whitelist (skip clearly harmful ones like Truant/Slow Start, prefer the species' best ability for the role).
6. **Item** by role and tier from `data/frontier/items.json`: T1 berries and basic boosters; T2 Sitrus/Lum/Choice items; T3/T4
   Leftovers, Life Orb, Focus Sash, Expert Belt, type boosters; Mega stone only on forced sets.
7. **Nature and EVs** by role: 252/252/6 spreads (offence: Atk or SpA + Spe; bulky: HP + Def or SpD), nature matching.
   **Encoded as ids into a small `spread` table** (24 spreads), so the ROM record stays 16 bytes. How EVs/natures are applied is part of
   M2 (we create the Pokémon ourselves with `CreateMon` + `SetMonData`) **[?]**; under M1 they are dropped and IV 31 is the only booster.
8. **Doubles variant:** a second pass for doubles-specific picks (Protect, spread moves, Fake Out, Follow Me, Helping Hand).
9. **Power score** `P` (a single number from stats, move power/coverage and item) stored per set, used to place it in tiers.

Output: `data/frontier/sets.json` (committed; species/move/item **ids as names**, so there are no ROM bytes) and the packed binary
inserted into the ROM, **16 bytes per set**: `species u16, item u16, moves 4xu16, spread u8, ability u8, nature u8, flags u8`
(~600 sets x 16 B = 9.6 KB; budget cap 40 KB). Hand-written overrides in `data/frontier/sets_override.json` win over generated sets
(for the Brain's team and for "iconic" Johto sets).

### 7.5 Run-time selection (in `fr_gen_opponent`)

```
tier(n)      = min(7, 1 + (n-1) / 4)            # battle 1-4 -> T1, 5-8 -> T2, ... caps at T7 (BOSS-grade handpicked)
trainer(n)   = class/name/pic/speech by hash(seed, n)
team(n)      = repeat N times: pick a set from tier(n) with hash(seed, n, i), reject (re-roll, max 8) if:
                 same species as another team member, same held item, or banned in the current mode
n % 7 == 0   -> tier(n) + 1 (the round's last trainer is a step harder)
n in {21,49} -> Brain team from sets_override (Lance), N picked from his 6
```

Difficulty knobs live in data, not code: the tier thresholds, AI flags per battle (ai 1 -> 7 by n), the share of doubles-only sets, and
the tier mix. The first playtest pass tunes `P` thresholds by running the generator's own sets against each other (a simple damage-formula
sim in Python, `scripts/frontier_sim.py`: it does not need to be accurate, only to reject sets that cannot win or cannot lose).

### 7.6 Validation (offline, run in CI-style by the builder)

- Legality: every move is learnable by the species (learnset ∪ TM/tutor) and exists in the hack's move table; ability is valid for the
  species; item exists; no duplicated move in a set; 4 moves.
- Coverage: tiers non-empty; >= 40 sets per tier; >= 30 doubles-eligible sets; >= 60 distinct species overall.
- Budget: packed table <= 40 KB; `insert.py` report still `missing 0, too_long 0, errors 0`; BPS byte-identical on the clean ROM.
- Sample: print 20 random teams per tier to a Markdown file for human review (`build/frontier/sample_teams.md`).

### 7.7 As built (M1 and M2, 2026-10-21)

`python3 scripts/frontier_sets.py` (inputs `data/frontier/pool.json`, `brains.json`; ROM data through `scripts/frontier_data.py`) writes
`data/frontier/sets.json` (committed, 271 KB, names plus ids, no ROM bytes), `build/frontier/sets.bin` (21,096 B), `brains.bin` (288 B) and
`build/frontier/sample_teams.md`. `--check` validates only and exits non-zero on errors. The output is deterministic (same seed, same bytes).

| Result | Value |
|---|---|
| Sets / species | **879 sets over 697 species** (after collapsing cosmetic forms that share name, stats and types) |
| Tiers (BST bands 0-470, 471-520, 521-569, 570+) | T1 193, T2 313, T3 133, T4 240 (63 of them Mega sets) |
| Roles | phys sweeper 289, spec sweeper 235, spec bulky 153, phys bulky 142, support 60 |
| Packed size | 21 KB of the 40 KB budget; 24-byte records (`species, item, 4 moves, 4 doubles moves, spread, ability slot, tier, flags`) |
| Brains | Lance 6 sets (Mega Dragonite), Anabel 6 sets (Mega Alakazam); one Mega each, species and item clauses enforced |
| Validation | legal moves (level-up <= Lv 50 or the type-keyed pool), no duplicates, 3+ moves with an attack, tiers >= 40 sets, >= 60 species, >= 30 doubles-ready sets |

How it differs from 7.4 as first written: roles score sweeper = offence + 0.8 speed, bulky = 0.9 offence + 0.9 bulk (needs bulk >= 85), at most two roles per
species; attacks are filtered to the role's **real** category (byte 10 of the move struct) with off-category moves only when that stat is within 85% of
the best; setup moves must match the role's category; bulky and support picks use seeded variety (Protect or Substitute; Toxic, Thunder Wave or
Will-O-Wisp); NFE species with BST >= 380 get Eviolite; legendaries carry flag bit 1 (max one per team at run time) and Mega sets are tier 4 only.

Known gaps (none block M3): `Dazzling Gleam`, `Prismatic Laser` and `Fezandipiti` do not exist in this hack (ignored); hidden abilities are not used
(the ability slot byte picks slot 0 or 1; ability ids above 255 may not be representable, as the hack data shows e.g. Palafin with Torrent); no
damage-formula sim yet (tier placement is by BST only); the Brain sets contain five hand-picked moves outside the level-up/TM pool (Roost on
Aerodactyl and Charizard, Ice Beam on Kingdra), which is fine because the engine does not check learnability; EV spreads and natures are stored as a
spread id and depend on the M3/M4 battle path (a shell trainer slot cannot carry EVs, so for the RAM-party mechanism they are applied only if CFRU
reads them; otherwise IV 31 is the only booster and the tier mix must be tuned accordingly).

## 8. Rewards, BP, shop, records

**Battle Points (BP)** are a **new** currency in `FR_BP` (not BracerPoints: those are native and tied to the Guild shop; coupling them is
risky and unnecessary). Naming is clearly "Battle Points". A single-line text patch is not needed because the text is ours.

- After a completed 7-battle round: `3 + (tier bonus 0..4)` BP; Brain win: +10 (Silver) / +20 (Gold); extra +1 per 7 on the streak.
  (Emerald-like scale: ~3 BP per round at the start, 20+ at the top.)
- **BP shop** (clerk in the hall; the same 8-column pattern as other hack shops): Leftovers 20, Choice Band/Specs/Scarf 24, Focus Sash 18,
  Life Orb 28, Shell Bell 14, King's Rock 12, Quick Claw 12, Scope Lens 12, Eviolite-like item **[?]**, Mega stones the hack has but never hands out
  (each 48-64 BP, **only** those that have a Mega form in the ROM, see `STORY_PLAN.md` section 11), Exp Candy / Rare Candy x5 (10), PP Max (8).
  Final table in `data/frontier/shop.json`; item ids resolved from `items.json` by name.
- **Symbols:** Silver/Gold per mode, stored in `FR_SYMBOLS`; shown by a Symbol-case NPC (a text list; a real case graphic is out of scope).
- **Records:** best streak per mode in `FR_BEST_*`, shown on the Records NPC.
- **Capstone** (optional, later): Gold Symbol in both modes -> flag + a post-Frontier legendary encounter (design left for a later chapter).

## 9. Integration with the story and game

- Chapter 2 is untouched: the Frontier unlocks from the Champion flag `0x14DB` and is independent of `CH2_STAGE` (works before or after
  Chapter 2). The orphan Tower Master lines make Lance the Brain; if the user prefers a different Brain (Silver/Anabel), only
  `sets_override.json` and the speech changes.
- The quest board is not touched in the MVP (a later phase can add "win 7 in a row" entries; the quest accessor is native).
- Hall NPCs and strings go in `text/en/strings.json` (new strings are English-only: the Chinese key is a stable synthetic key, same
  convention as the Chapter 2 scripts via `scrasm` `say "..."`).

## 10. Work breakdown (milestones)

| M | Deliverable | Verified how |
|---|---|---|
| **M0** | Spikes S1-S6 (section 11) answered, results appended here | notes in this file |
| **M1** (done 2026-10-21) | `scripts/frontier_data.py` + species/move/learnset extraction; `data/frontier/pool.json` | `frontier_data.py` summary; section 7.7 |
| **M2** (done 2026-10-21, review pending) | Set generator + validator + packed table; sample teams reviewed by River | `frontier_sets.py --check`, `sample_teams.md`, size report (section 7.7) |
| **M3** (done 2026-10-21) | Native helpers `fr_enter`/`fr_leave`/`fr_heal` (party mutate/restore) with idempotence and save tests | `frontier_m3_test.py`: 32 checks pass; battle screenshot (section 6.3) |
| **M4** (done 2026-10-21) | `fr_gen_opponent` (C) + `fr_start_battle` and the full chain in the emulator | section 6.6; `frontier_m4_e2e.py` |
| **M5** (playable MVP done 2026-10-21) | Hall map `31.3` rewired, reception, arenas, round loop, BP, shop, records | section 6.7 |
| **M6** | Brain (Lance) 21 and 49, symbols, polish, balancing pass | full run to 21 with a Lv 50 test team |
| **M7** | PLAYTEST rows, `CLAUDE.md`/`HACKDB` notes, release notes for the River Edition (v0.2), BPS check | `insert.py` clean, BPS byte-identical |

Everything lands on `feat/battle-frontier`; PRs to the River Edition line, never to the translation `main` (translation betas stay a
translation only).

## 11. Spikes to run first (each answers one unknown)

| ID | Question | How |
|---|---|---|
| **S0** | Do vars `0x5121`-`0x5132` and flags `0x1388`+ round-trip through a save in the emulator? | `mapdrive.py` poke + reload |
| **S1** | Where are the hack's base stats, learnsets, TM compat, evolutions and move table, and what are their formats? | Ghidra (`get_functions`), `hackdb whatis`, extend `species_peek.py` |
| **S2** | What does `special 0x17B` do (ferry offer)? Where does it go, and can we replace it without breaking Navel Rock? | Ghidra + emulator trace at `49.6` |
| **S3** | Does the hack's CFRU battle code honour `BATTLE_TYPE_TRAINER_TOWER` (prefilled party, no EXP/money/whiteout, RAM name/pic)? Are `gBattleTypeFlags`, `gEnemyParty`, `CB2_InitBattle` where the decomp says, and do vanilla Trainer Tower specials still exist and run? | `watch_log` on `gEnemyParty`, `break_at CB2_InitBattle`, run the vanilla Trainer Tower lobby script on `2.10` |
| **S4** | Can `ChooseBattleTowerPlayerParty`/`InitChooseMonsForBattle` be called as-is for 3 and 4 picks, and what do `gSelectedOrderFromParty` and the menu type constants look like in this ROM? | locate by string xref ("choose 3"), emulator |
| **S5** | Free EWRAM for the opponent RAM block (name/speech) and for challenge scratch (no collisions with CFRU) | scan EWRAM writes during a battle, pick an untouched range, record it |
| **S6** | Which existing layout is a good battle room (small, enterable from a door, no encounters) and what does `31.3`'s second stairway (`warp 31.4`) lead to? | `maprender.py`, `hackdb map 31.4` and candidates `13.x`, `53.x`, gym rooms |

Results are appended to section 12 as dated entries (the `ROADMAP.md` style), and any fact that cost time is copied to `CLAUDE.md`.

## 12. Spike log

**2026-10-21, S2 (ferry special): solved, and it changes the map plan.** `special 0x17B` is vanilla `DoSeagallopFerryScene` (the
`gSpecials` table at `0x15FD60` is unchanged from FireRed). The ferry NPC's script sets `0x8004 = 0` (origin Vermilion) and
`0x8006 = 1` (destination index 1), and the scene then warps via the destination table `sSeag` (4-byte `{group, map, x, y}` entries) which
the hack relocated **in place at `0x46AEFC`**: entry 0 (Vermilion) = `49.6 (8,6)`, entry 1 (the "One Island" slot) = **`31.6 (8,6)`**, entry
7 = `31.6` too. So the "Battle Frontier" ferry already sails to **map `31.6`, a ship-cabin lounge (17x13, life rings, a pool table,
2 NPCs)**, which is the intended arrival. Its door `(8,1)` and hall `31.3`'s warp #0 both target `54.12`, a map that does not exist (group 54
has maps 0-9): the authors' unbuilt outdoor Frontier plaza. Consequences:
- No change is needed to the ferry offer; only the **dangling `54.12` warps** need a target: `31.6 (8,1)` -> `31.3` (hall, arrival side) and
  `31.3` warp #0 -> `31.6` (back to the ferry). Cheapest: skip the plaza entirely (the hall becomes the hub). Optional later: a plaza as
  `58.5` (layout reuse).
- The ferry offer is gated by flag `0x14DA` only; `FR_UNLOCKED` can stay as designed, or we can simply let the existing gate stand. The
  return trip needs a destination-table entry for the way home (entry 0 already is Vermilion `49.6`); the cabin NPC at `31.6` obj#1
  (script `0x08A688D0`, gfx 62) is almost certainly the "sail back" sailor: **read it before reusing** [?].
- `49.6` obj#0 (`0x08A68865`) does *not* branch on Chapter 2, so Navel Rock keeps its own entry (table index 9/`2.x`); no conflict.

**2026-10-21, S3 (battle path), partial: the Trainer Tower code is present and callable, but the hack's CFRU battle init takes over and
changes the flags.** Method: symbols from the built decomp (`utilities/pokefirered/pokefirered.elf`, `arm-none-eabi-nm -S`), compared with
the same address range in the Mercury ROM, then an emulator run.
- **Byte-identical to vanilla in the hack** (so their vanilla addresses are valid call targets): `CB2_InitBattle 0800FD9C`,
  `DoTrainerTowerBattle 0815E160`, `Task_DoTrainerTowerBattle 0815E124`, `CB2_EndTrainerTowerBattle 0815E114`, `BuildEnemyParty 0815E9FC`,
  `ChooseBattleTowerPlayerParty 080A0380`, `InitChooseMonsForBattle 081274A8`, `CalculatePlayerPartyCount 08040C3C`, `SavePlayerParty 0804C1F0`,
  `HealPlayerParty 080A0058`, `CreateMon 0803DA54`, `SetMonData 0804037C`, `AllocZeroed 08002BB0`, `CreateTask 0807741C`,
  `BattleTransition_StartOnField 080D08B8`, `BattleSetup_GetBattleTowerBattleTransition 08080060`, the Trainer Tower name/class/pic getters
  (`GetTrainerTowerOpponentName 0815DA28` ...), and the 150-entry tables `gFacilityClassToPicIndex 082538A8`, `gFacilityClassToTrainerClass 0825393E`.
- **Replaced by CFRU** (do not assume vanilla behaviour): `CalculateMonStats 0803E47C` and `PlayMapChosenOrBattleBGM 08044090` (both are
  `ldr r1,=X; bx r1` trampolines, still safe to call at the vanilla address), `CreateNPCTrainerParty 080112E0`, `Cmd_getexp 08021A68`,
  `GetLevelFromMonExp 0803E7C4` (call target differs only), `ReducePlayerPartyToThree 080A03D8`, `CB2_ReturnFromChooseBattleTowerParty 080A039C`,
  and **`CB2_InitBattleInternal 0800FE24`**, which for non-link battles jumps (`ldr r0,=0x09CCA5CF; bx r0`) into CFRU code.
- **Trainer Tower speech is Easy Chat words** (6 words each, `TT_ConvertEasyChatMessageToString`), so the in-battle win/lose text cannot carry our
  dialogue. Resolution: script-printed speeches before and after the fight (see 6.5); fill the 12 speech words with `0xFFFF` (blank).
- **Experiment** (`scripts/spikes/frontier_s3_stub.s`, `frontier_s3_run.py`; a Thumb stub linked at `0x0203FC00`, called through
  `callnative`, playtest save `Azoth.sav`): it allocated the opponent block (`sTrainerTowerOpponent 0203F45C`), wrote class/name, created three Lv 50
  Pokémon in `gEnemyParty` with `CreateMon`, set `gBattleTypeFlags = 0x80008` (TRAINER | TRAINER_TOWER) and started the tower battle sequence. **The
  battle ran** (Venusaur Lv 50 vs the player's Croconaw; the intro said "... wants to battle!"). **But** within 3 frames of `CB2_InitBattle`
  the word at `0x02022B4C` stopped holding our value (`0x80008` -> `0x8000C` -> `0x02063C00`), the opponent showed no trainer sprite, and the
  battle text read "Wild Venusaur used Sludge Wave!". No CPU write to that word was logged after ours (writes by BIOS/DMA fill bypass the watch).
  So in this ROM either the flag word is moved or reset by CFRU's init, or CFRU rebuilds it from other state. **Cause found later:** an overflow of the intro text into the flag word (below).
- **Tooling facts learned (keep in `EMULATOR.md` when the spike closes):** a Thumb stub must be **linked** (`arm-none-eabi-ld -Ttext=ADDR -e _start`),
  an unlinked `.o` turns `ldr r,=label` into offsets; every call target needs the **Thumb bit** (`|1`) for `bx r3`; the stub can live at `0x0203FC00`
  and the injected script `callnative PTR|1; waitstate; end` at `0x0203FF00` (opcode `0x23`); the bridge's `read_registers` samples inside the IRQ and
  is useless for locating a hang (use progress markers in EWRAM instead).
- **S3 resolution (same day):** a write watch only saw our own write (BIOS/DMA fills and string copies bypass it), so we dumped memory:
  the words after `0x02022B4C` held battle text ("... wants to battle!"), i.e. the vanilla string-buffer area, overwritten by an
  oversized/garbled intro message for the `TRAINER_TOWER` type. Switching the flag to `BATTLE_TYPE_BATTLE_TOWER` (`0x108`) with a real trainer
  id gave a clean fight (6.4). `0x02022B4C` **is** the real `gBattleTypeFlags` (767 literal references in the hack ROM).
- **Old next steps (superseded):** (a) decompile CFRU's `0x09CCA5CE` (Ghidra MCP, `get_functions address=0x1CCA5CE`) and find what it does to the flag word and
  the opponent state; (b) check whether CFRU already defines its own Frontier battle types (it normally has `BATTLE_TYPE_FRONTIER`); (c) if the
  vanilla tower flags are not honoured, switch to mechanism **M1** (EWRAM trainer-slot party through a normal `trainerbattle`) and add the EXP/money
  suppression patch; the experiment already proves the native-code route (`callnative` + `CreateMon` into `gEnemyParty`) works, so M1 costs no new
  unknowns beyond the suppression patch.

**2026-10-21, S1 (data tables): solved except TM/tutor compatibility and move category.** Checked against known species and moves; the reader is
`scripts/frontier_data.py` (`python3 scripts/frontier_data.py`; prints "1434 species, 944 moves"):

| Data | Where (file offset) | Format |
|---|---|---|
| Base stats | `0x176DFBC + 28*species` | vanilla 28-byte struct (hp atk def spe spa spd type1 type2 ..., abilities at +22/+23); 1,434 valid species up to id 1553 |
| Moves | `0x1E0326F + 12*move` | vanilla 12-byte struct (effect power type accuracy pp secondary target priority flags); a CFRU copy, the vanilla table at `0x250C04` is stale |
| Level-up learnsets | pointer table `0x17C32BC` (one u32 per species) | list of `{u16 move, u8 level}`, **terminated by level `0xFF`**; hack-specific and generous (e.g. Bulbasaur learns Sludge Bomb, Power Whip, Solar Beam by Lv 39) |
| Evolutions | `0x1788F5A + 128*species` | 16 slots of `{u16 method, u16 param, u16 target, u16 pad}`, `method 0` ends; **method 254 = Mega Evolution** (param 533 = the generic Mega Stone; e.g. Dragonite -> 1403, Tyranitar -> 889); method 34 = a variant evolution |
| Names | species `0x141B350` (11 B), moves `0x1D97378` (13 B) | already in `text/en/tables/*.json` |
- **Mega Evolution is widespread** (generic stone 533), contrary to `STORY_PLAN.md`'s count of four: Lance's Dragonite and Anabel's team can Mega.
- **TM/HM/tutor compatibility:** the vanilla table (`0x252BC8`, 8 bytes per species) is intact for species <= 411; the table for newer species was
  not located. Decision: the generator does **not** depend on it for the MVP. Allowed moves = level-up moves up to Lv 50 (rich in this hack) plus
  a curated, type-keyed "TM-like" pool in `data/frontier/tm_pool.json`; revisit if sets look bland.
- **Move category (physical/special/status): solved** the same day: it is **byte 10 of the 12-byte move struct, masked with 3** (0 physical, 1 special,
  2 status). Checked on ~35 moves (Shadow Ball, Dark Pulse, Hyper Voice, Judgment special; Crunch, Dragon Claw, Play Rough physical; Swords Dance, Protect status).
  `frontier_data.py` exposes it as `split`; the Gen 3 type rule is only a fallback.

**2026-10-21, S4 (party selection): solved by not using the vanilla Battle Tower selector.** The specials are intact at their vanilla table
slots (`ChoosePartyMon = 0x9F`, `HealPlayerParty = 0x00`, `GetBattleOutcome = 0xB4`, `CalculatePlayerPartyCount = 0x83`, `SavePlayerParty = 0x27`), but
the vanilla selector (`ChooseBattleTowerPlayerParty`) is limited to 3 and its helpers (`ReducePlayerPartyToThree`) were modified. Decision: the
reception script calls `special ChoosePartyMon` once per pick (3 for singles, 4 for doubles; `gSpecialVar_0x8004` = slot or `0xFF` for cancel),
rejects duplicates/eggs/banned species in script, stores the slots in `FR_PICK_*`, and only then calls `fr_enter`. This also lets the prompt
say "Choose your 2nd Pokémon" (script text).

**2026-10-21, S5 (scratch RAM): decided, to be re-verified.** All EWRAM is claimed by the vanilla layout, so "zero in a session" is not proof of
"unused". A zero-block scan across overworld, menus, a battle and its end (5 snapshots, `scripts/spikes`) found the stable blocks are the heap, the
save blocks' unused tails, and **the link buffers** (`gBlockRecvBuffer`/`gBlockSendBuffer`, `0x02022300`-`0x020227FF`, zero literal references in
the hack ROM for `0x02022400`-`0x020225FF`). The facility is offline-only, so the link receive buffer is safe to borrow. **Decision: scratch block
= `0x02022400`-`0x020225FF` (512 B): party block (6 x 16 B), challenge scratch, opponent bookkeeping.** Re-verify with a write watchpoint over a
full Singles round; fallback: tail of `gBlockSendBuffer` (`0x02022700`+).

**S6 (solved for the arena choice):** the Elite Four chambers `1.75`-`1.79` (rendered with `maprender.py`) are themed and ready: `1.75` pale lavender
(ice), `1.76` starry violet (psychic), `1.77` lava (fire), `1.78` dark teal with greenery, `1.79` gold champion hall (18x28, with statues and a red carpet; an exit
at `(8,25)` and the champion at `(8,7)`). `1.80` is the Hall of Fame. Suggested floor mapping: Red=`1.77`, Orange=`1.79`, Yellow=`1.79`, Green=`1.78`,
Blue=`1.75`, Indigo=`1.76`, Violet=`1.76`, Brains=`1.79`. Group 31 is all small indoor rooms (lounge 31.6, hall 31.3, 31.4/31.5 service rooms, 31.0-31.2 town interiors). No existing
arena layout was checked yet: candidates are the League chambers (`13.x`) and the vanilla Trainer Tower floors (`2.1`-`2.8`, 18x17).

## 13. Risks and cuts

| Risk | Mitigation / cut |
|---|---|
| CFRU battle code diverges from vanilla flags (S3) | take M1 (EWRAM trainer-slot party) + EXP/money suppression patch |
| Party mutation leaves a bad save | idempotent `fr_leave`, gated cleanup on every map transition, tests with mid-challenge saves |
| Set quality (a pool of 600 generated sets can be bland or unfair) | tier by `P`, offline sim, human review of samples, hand overrides, easy to rebalance (data only) |
| Pointer trust (`CLAUDE.md`) for new tables and `callnative` targets | allocate from the free pool, never edit shared bytes, diff all `goto/call/applymovement` operands of old vs new ROM after any manual strings or script changes |
| Object budget (16 live objects) in the hall (`31.3` has 8 NPCs) | keep new NPCs <= 4; re-use the existing 8 slots by re-scripting them |
| Free space | MVP estimate: sets 10 KB + natives 2 KB + scripts and text 15-25 KB + 1-2 maps 5 KB = **~35-45 KB** of the ~670 KB pool |
| Translation purity | content ships only in River Edition builds, labelled as fan-made; the translation betas stay untouched |

Cuts, in order: Brain Gold (keep Silver), doubles, the arrival pier, the Symbol-case NPC, BP shop breadth, the second Lance team.

## 14. Decisions (River, 2026-10-21: "go with your recommendations")

1. **Brains:** Lance (Tower Master, the ROM's own text) at streak 21 = Silver Seal. **Anabel** (Salon Maiden; the ROM already says she was
   "sent to the Battle Frontier on an urgent mission") at 49 = Gold Seal. Lance's Dragon-Master lines already exist in the ROM.
2. **Currency:** new Battle Points (BP), not BracerPoints.
3. **Entry:** the Vermilion ferry (`49.6`), post-Champion.
4. **Level rule:** everything is set to exactly Lv 50 (low mons are raised, high mons lowered).
5. **Shop:** held items, candies **and** the Mega stones the ROM has (only those with a real Mega form).
6. **Dialogue:** drafted here (section 15) for River to rewrite.

## 15. Creative bible: "The Spectrum Frontier"

Tone: Johto-warm, a little alchemical (the hack is *Azoth*: the universal solvent, beginning and end) and tied to the River Edition's
rainbow thread. The facility is the Chapter 2 epilogue made playable: the song, the empty fifth place, the Rainbow Stone. Nothing here
needs new graphics: it is flavour text, class choices and scripts.

### 15.1 The place

- **Name:** the **Spectrum Frontier**; its signature building is the **Spectrum Tower**. The tycoon who rebuilt the old Trainer Tower
  (`31.3` lore) named it after the rainbow that "appeared over the sea the week the Champion was crowned" (Navel Rock epilogue). Nobody
  admits whose idea the colour scheme was.
- **Seven floors, seven colours, seven battles.** A round climbs the tower: the reception announces each floor by colour (Red, Orange,
  Yellow, Green, Blue, Indigo, Violet). Floor theme only changes the **trainer class, the tier mix and the flavour line**; no extra tech:

| Floor | Colour line | Trainer pool (class mix) | Flavour |
|---|---|---|---|
| 1 Red | "Kindle" | Youngster, Lass, Camper, Picnicker | warm-ups, small talk |
| 2 Orange | "Ember" | Hiker, Fisherman, Bug Catcher, Sailor | rough and cheerful |
| 3 Yellow | "Spark" | Gentleman, Beauty, Pokéfan, Idol | showy, rule-lawyers |
| 4 Green | "Grove" | Bird Keeper, Gardener, Ranger-types | patient, outdoorsy |
| 5 Blue | "Tide" | Swimmer, Cooltrainer, Expert | calm, precise |
| 6 Indigo | "Dusk" | Psychic, Channeler, Sage, Medium | uncanny |
| 7 Violet | "Prism" | Ace Trainer, Dragon Tamer, Champion-class | the round's boss; one tier up |

- **Arrival:** the sailor's offer. A fade; the sound of the Navel Rock bell (existing fanfare); a one-line caption "The Spectrum Frontier".
- **The Hall (`31.3`):** receptionists "Hue" and "Saturate" (twin counters, Singles and Doubles), the BP clerk **Prisma**, the Records
  board, a bored nurse who heals for free, and **Old Dowser**, a retired Trainer Tower champion who gives tips and sets the tone.
- **A quiet touch:** one chair in the hall is always empty and faces the stage-like reception window. A sign: "Reserved." (A wink to
  Sange's empty place; it never gets explained.)

### 15.2 Rules in flavour: the **Seal Case**

- **Seal Case** (Silver and Gold) is a key item *text-only* (a script-granted entry in the Records NPC's list).
- Beyond the two Brain seals, a **chroma stamp** per colour is earned at floor wins (visual: a text checklist in the Records script):
  collect all seven in one round = "a Clean Spectrum" (+3 BP, once per round). Pure flavour for playtesters.
- **Streak milestones:** 7 "Spectrum", 14 "Double Spectrum", 21 Silver (Lance), 28, 35, 42, 49 Gold (Anabel), then every 7 more adds a
  small banner line.

### 15.3 Brains (hand-built teams, Lv 50)

- **Lance, Tower Master (Silver, streak 21).** Existing ROM lines: "To think you'd make it this far! As the Battle Tower Master, I'll
  fight with all I have..." and "We meet again... I am Lance the Dragon Master, and I accept your challenge." Team (singles, 3 of 6):
  Dragonite, Gyarados, Aerodactyl, Charizard (Mega-capable if the hack allows), Salamence, Kingdra. In doubles he opens with a
  Dragon pair and Dragon Dance. After Gold, a **rematch** with a bonus set.
- **Anabel, Salon Maiden (Gold, streak 49).** A seer's gimmick: "I saw this battle before it began, and I still do not know how it ends."
  Team: Espeon, Alakazam, Entei, Latias (Mega aura story hook), Gardevoir, Metagross. At 49 she is the final check; her speech reacts to
  `ARCHER_CAUGHT` and `CH2_DONE` (shorter, kinder) if Chapter 2 is finished.
- **Rival cameos** (cheap, flavour): a single battle-slot override at streak 14 or 35 can pull **Silver**, **Dawn** or **Axel** from
  the Chapter 2 cast as "visiting challengers" using their story sprites and a themed set (no new maps).

### 15.4 Draft lines (River rewrites)

Receptionist (Hue): "Welcome to the Spectrum Tower. Seven floors, seven battles, one colour each. Bring three Pokémon, or four if you are
feeling doubly brave. Everyone fights at Lv 50: the stairs do not care how strong you were yesterday."
Receptionist (declined): "Come back whenever the sky is the right shade."
Saving prompt: "Shall I record your climb in the ledger? The tower likes things written down."
Floor announcements (reception or sign): "Floor 1: Red. Warm hands, warm hearts." / "Floor 2: Orange." / "Floor 3: Yellow." ...
"Floor 7: Violet. Nobody here is a stranger to the rainbow."
Old Dowser: "Back in the old Trainer Tower we timed everything. The new place counts wins instead. I miss the clock, but the wins are nicer."
Prisma (BP shop): "Battle Points are the only currency the tower respects. Spend them like you lost the key to something."
Records NPC: "Your longest climb is {streak} battles. The tower remembers {n} more than you do."
Empty chair sign: "Reserved."
Defeat (round lost): "The stairs go down faster than they go up. Take a breath. The tower will wait."
Round complete: "Seven floors. {BP} Battle Points. Would you like to keep climbing?"

Trainer speeches (intro / on defeat), a pool of ~40 each in `data/frontier/speech.json`; seed lines:
- Youngster: "Lv 50? Easy! ... Probably!" / "I forgot to be scared and you still won."
- Gentleman: "A civilised battle: no wagers, no weather, no rush." / "Gracious in defeat is the only way I know."
- Idol: "Smile for the audience: they are all behind the glass!" / "Next time I will sing the victory song."
- Sage: "The tower hums an old tune. Do you hear it?" / "The note moved. Go on."
- Dragon Tamer: "Dragons dislike being predicted." / "You were there already, weren't you."
- Cooltrainer: "I trained for exactly this matchup." / "...I trained for the wrong matchup."
Tower Master (Lance) and Salon Maiden (Anabel) lines are above and extend the existing ROM text.

### 15.5 Cheap creative mechanics (no new engine work)

All of these are data-driven in `data/frontier/*.json` and scripts; pick any subset by cost:

1. **Colour Rounds:** each of the 7 floors weights the tier mix by a "type theme" (Red = Fire/Fighting, Orange = Rock/Ground, Yellow = Electric/
   Normal, Green = Grass/Bug/Flying, Blue = Water/Ice/Steel, Indigo = Psychic/Ghost/Dark, Violet = Dragon/Fairy). The player sees the
   theme, so team-building has a puzzle ("which three beat Floor 5?"). Free: just a filter on set selection.
2. **Shadow of the Past:** at streak 14 (and 35) the opponent is built from **the player's own species** (their party's species at
   Lv 50, generated sets). Needs only a read of the party species list in `fr_gen_opponent`. Dialogue: "It is you, a little to the left."
3. **Wager Flags:** before each round the player may stake 0, 1 or 2 BP; a flawless round (no Pokémon lost) pays 2x the stake. A single
   var and text; tiny risk, big feel.
4. **Weather Floors (stretch):** floors 3, 5 and 6 start with sun, rain, fog; requires hooking battle start weather (CFRU may expose
   a flag, spike S3). Cut if not free.
5. **Daily Challenge (stretch):** a seed derived from the day counter in the RTC makes everyone's "Floor of the Day" the same for all
   players. Needs RTC read; skip if the hack has no RTC.
6. **Heirloom Sets:** a few iconic Johto teams (Falkner's birds, Bugsy's bugs, Whitney's Miltank, the Kimono Girls) as hand-written
   overrides that appear rarely and say so ("I borrowed this team from an old friend").
7. **The Fifth Place:** once per save, after the Gold Seal, a script shows a fifth, unseen challenger slot on the board: the sign
   changes to "Reserved: for whoever finishes the song." Plant for a future chapter; no mechanics.

### 15.6 Later facilities (phase 2+, same state machine)

- **The Prism Gauntlet** (Pike/Pyramid-style): a chain of the same room map with random events (heal, hazard, ally, battle) rolled
  from the seed; reuses `fr_gen_opponent` and the room map; 14 rooms, Brain at the end.
- **The Foundry** (Factory-style): rental Pokémon drawn from the pool; picks are written into the party by `fr_enter`
  (same native, different source). Needs a loaner-mon generator (EVs, items): we already build it for opponents.
- **The Orrery** (Arena-style, 3-turn judgement): skipped unless the battle engine exposes turn counts cheaply.
- **Seals for every facility** and a final "Alchemist's Seal" for all of them (story hook for Chapter 3).

## 16. Immediate next steps (updated 2026-10-21 after spikes S1-S6)

Done: S1 (tables), S2 (ferry), S3 (battle path, M3), S4 (party picking), S5 (scratch RAM, to re-verify), S6 (arenas).
Left from section 11: **S0** (do the new vars/flags survive a save/reload?). New checks folded into M3/M4: a **loss** in a `BATTLE_TOWER` fight
(no whiteout?), a **double** battle, **CFRU reading an EWRAM party pointer**, and the in-battle **speech table**.

1. **M1/M2 (no ROM risk, start now):** extend `scripts/frontier_data.py` into the set generator (`data/frontier/pool.json`, `sets.json`,
   validator, sample teams).
2. ~~M3~~ done: `scripts/frontier_native.s` + `frontier_native.py` (test links it in EWRAM; M5 links it at its free-pool address).
3. ~~M4~~ done (section 6.6).
4. ~~M5~~ playable MVP done (section 6.7). M6 (section 6.8) is built. Left: polish and the checks listed under "Not yet exercised".
