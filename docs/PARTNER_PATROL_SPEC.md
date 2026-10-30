# Partner Patrol: design and milestones

Status: **draft 8, 2026-10-29. Decisions recorded (section 9); M0-M5 built and verified (sections 12-16), including the map sweep. M6 (release) is next.** Goal set by River: in Quick Catch mode, send the walking partner Pokémon out to fight the
visible wild Pokémon on the map by itself, and collect the XP and drops. Target is the fully autonomous version ("Tier 3"), reached in
steps that each stand on their own.

Labels: **[V]** verified in the current build on 2026-10-29, **[?]** unverified assumption that milestone M0 must settle before dependent work starts.

Credit rule (same as the rest of this project): fan-made addition by River with Claude on top of a translation; the hack, its name and
content belong to its original authors. Release text says so.

## 1. What already exists (reuse, do not rebuild)

| Piece | Evidence | Use |
|---|---|---|
| **Quick Catch** | HUD string `L:Switch Ball R:Toggle Lock A:Throw B:Exit` at 0x09DA16A0 (literal at 0x09D536F8); refusal "This Pokémon can't be caught!" (0x09DA13D8, ref 0x09D0FADC); help tip: "aim at a visible Pokémon and throw a Ball without battling", needs standard buttons, "only nearby visible Pokémon are targets, story Pokémon can't be caught". Code region about 0x09D0F9E8-0x09D53A58 (compiled, no source) [V] | target selection, lock, "visible wild Pokémon" list, removal after a catch |
| **Visible wild Pokémon** (the Chinese "明雷") | map objects whose script starts a wild battle [?: confirm in M0] | the patrol's targets |
| **Walking partner** | live object event local id **0xFE (254)**, graphics id from the species, stays one tile behind the player [V: object #1 in the playtest save]. NPC text: keeping a Pokémon walking behind you raises friendship. Party-menu strings "Walk" / "Follow Me", "{mon} follows behind comfortably!" (ref 0x09CCFFF1) | the patrol actor |
| **Drop system** | Help Tips: "The three drops don't stack: 20% Exp. Candy, 30% Berries, 50% matching EV Feathers"; "Feathers drop only if no Candy or Berries did, whatever the EV switch"; "Each foe gives Feathers once; max-level or full-EV partners still earn them"; an EV switch in Settings (On: EVs after battle; Off: Feathers instead); Exp. Share multiplies boosted Feathers by party size; Power items add the matching Feather [V: strings]. Items: Exp. Candy XS/S/M/L/XL = ids 536-540, Health/Muscle/Resist/Genius/Clever/Pretty Wing = 57-61, 117 [V] | **"whatever they currently drop"**: the patrol must grant exactly these |
| **Species held items** | gBaseStats pointer at ROM word 0x080001BC, 28-byte entries: expYield +9, item1 +12, item2 +14, growth rate +19 [V from CreateBoxMon disassembly] | **"items the species can hold"**: rolled with the engine's own wild-hold odds (50% item1, 5% item2, 100% when both are equal) |
| EXP / stats | experience table at 0x09E0B258 (`[(growth<<8)+level]*4`), `CalculateMonStats` 0x0803E47D, `SetMonData` 0x0804037D [V, used by the Cheat Device's level cap] | XP and level-ups |
| Native code + scripts into the free pool | `scripts/cheats_build.py`, `scripts/frontier_build.py` (Thumb asm and C, byte-asserted patches) | how this feature is built |

## 2. Rules

1. **Partner** = the Pokémon currently walking behind the player (object 0xFE); its party slot is found in M0 [?]. If nobody walks, the
   patrol button says so.
2. **Targets** = the same set Quick Catch can aim at: visible wild Pokémon within a radius of the player (default 7 tiles), not story Pokémon,
   not shiny (skipped, never removed; see section 9).
3. A patrol is **always interruptible**: B, any D-pad press by the player, a script/battle starting, or a map change ends it and the
   partner snaps back behind the player.
4. **Costs** (so it is not free farming): each fight damages the partner; the patrol stops when the partner is below 40% HP, with a summary
   message. A short cooldown between targets. No healing is given by the patrol.
5. **Rewards per defeated target:** XP (standard formula, partner only; Exp. Share honoured as the hack does), then the hack's own drop roll
   (Candy 20 / Berries 30 / Feathers 50, non-stacking, EV switch respected), plus the species' held item roll. Everything lands in the bag at
   the end with one summary ("Croconaw beat 5 Pokémon: +312 EXP, Oran Berry x2, Health Wing x1").
6. No catching, no Pokédex "seen" changes beyond what a normal encounter does [?: decide].
7. Not available in the Frontier, in the Sprout-Tower-style one-tile corridors it cannot path through, indoors without wild objects, or while
   surfing/biking [?].

## 3. Behaviour (Tier 3)

State machine in one field task (`CreateTask`, runs every frame; EWRAM state, **not saved**):

```
IDLE -> PICK -> WALK -> STRIKE -> RESOLVE -> RETURN? -> PICK ... -> DONE
```

* **PICK**: nearest valid target by walking distance (BFS over the collision grid, radius-limited); none -> DONE ("Nothing left nearby").
* **WALK**: move the partner object one tile at a time with held movements (never one long `applymovement` chain: an aborted chain is what
  parked the Sprout Tower escort, #37). The partner's own follow logic is suspended for the duration [?: how, M0]. A blocked step re-plans; three
  failures -> skip the target; ten -> DONE.
* **STRIKE**: when adjacent: face the target, a lunge animation (one step forward and back), hit sound, target flashes.
* **RESOLVE**: the simulated fight (section 4), XP and drops tallied in a RAM record, target object removed the way Quick Catch removes a
  caught one (its hide flag), partner HP updated.
* **RETURN/DONE**: walk back toward the player (or snap if far), restore the follow logic, print the summary, free control.

HUD while active: a one-line status in the Quick Catch HUD area ("Patrol: Croconaw 62% HP, 3 down. B: recall").

**Input**: inside Quick Catch mode, **SELECT = send / recall the partner** (L and R are taken; confirm SELECT is unused there in M0). The
cheat menu (SELECT+R) is unrelated and untouched.

## 4. The simulated fight (no battle screen, **no moves**)

River's rule (2026-10-29): the fight ignores moves entirely and is decided by **types**, Scarlet/Violet style.

* Each side attacks with its **best own type** (STAB) against the other side's type pair, through the game's own type chart (`0x0824F050`, the
  hack's chart with Fairy: `{attacker, defender, 0/5/10/20}` triples). Per attacking type the multiplier is the product over the defender's one or
  two types (0 / 0.25 / 0.5 / 1 / 2 / 4); the better of the attacker's two types is used. No effect = 0 damage.
* Damage = `((2L/5+2) * 90 * A / D) / 50 + 2` (power 60 with STAB x1.5 folded in), A and D = the higher of Atk/SpA against the matching Def/SpDef,
  x random 85-100%, x the type multiplier. The faster side acts first; 12 rounds at most; the partner retreats under 40% HP; a draw or a loss is a
  retreat (no XP). Abilities, items, weather, status, accuracy, crits: ignored.
* Both Pokémon are real (`CreateMon` for the target), so stats, levels and types are exact.
* Partner faints is impossible by design: it retreats with at least 1 HP.

## 5. Rewards and level-ups

* XP: `expYield * level / 7` (x1.5 if the partner's OT is not the player [?: only if the hack does]), applied with `SetMonData(EXP)` +
  `CalculateMonStats`. Level cap interplay: none.
* **New moves**: auto-learned if a slot is free; otherwise queued and the normal "wants to learn" flow runs after the patrol ends [?: M2 decides
  between engine flow and silently skipping].
* **Evolution**: set the partner's bit in `gLeveledUpInBattle` so the engine's own post-battle evolution check fires at the next real battle end
  [?: verify in M0], instead of evolving mid-walk.
* Drops: M0 locates the hack's reward routine. **Preferred: call it** with the defeated species so every drop rule, the EV switch and the
  Exp. Share maths stay identical; fallback: reimplement from the Help Tips rules (listed in section 1).
* Bag full: items that do not fit are left out of the summary with a note.

## 6. State, ids, space

* RAM: patrol state ~64 bytes + the RAM tally; **EWRAM location decided in M0** (Frontier reserved `0x02022400`-`0x020227FF`; the native image of
  the Frontier does not live in RAM in the shipped build).
* Hack flags `0x13B0`-`0x13BF` and vars none (state is volatile) are reserved for this feature (cheat switches use `0x13A8`-`0x13AF`).
* ROM: well under 8 KB of Thumb in the free pool (0.67 MB free after the Frontier).
* Save compatibility: no save-format change; an old save simply has the switches off. Nothing persists across a save/reload except the settings.
* Both editions: the feature is added by `scripts/patrol_build.py` called from `insert.py`, like the cheats, and ships as an **optional add-on**
  (own `RHT_` switch, own release), never inside the numbered betas or River releases.

## 7. Milestones (breakpoints)

Each milestone ends in something you can play and a verification in the emulator, and can be released or stopped at.

| # | Milestone | Done when | Rough size |
|---|---|---|---|
| **M0** | **Spikes, no gameplay.** (a) Quick Catch: how it lists targets, locks, reads species/level, removes a target, handles input; (b) the walker: its party slot, update function, how to suspend/resume it, what happens on map change; (c) the drop routine and the EV switch variable; (d) type chart, move data, scratch `gEnemyParty` slot; (e) free EWRAM; (f) a one-line note per [?] in this file, flipped to [V] | every [?] above is resolved or turned into a decision | 1 session |
| **M1** | **Instant strike.** In Quick Catch, SELECT on the locked target runs the simulated fight and applies XP; message shows the result; target removed | partner gains the expected XP; target gone; no crash; B/cancel clean | 1-2 sessions |
| **M2** | **Reward parity.** Hack drop routine (or equivalent), held-item roll, EV switch/Exp. Share, level-ups, queued moves, evolution flag, bag-full handling, summary text | drops match the Help Tips odds over 1,000 simulated kills; level-up and evolution behave | 1-2 sessions |
| **M3** | **Visible single strike.** Partner pathing to the target, lunge, flash, return; suspend/resume of the walker; abort-safe cleanup (an `ON_RESUME`-style repair so a stuck save fixes itself) | works in open grass, near walls, with the player moving; never leaves the partner parked | 2-3 sessions |
| **M4** | **Autonomous patrol (Tier 3).** The PICK/WALK/STRIKE/RESOLVE loop over all nearby targets with every stop condition, HUD line and summary | a patrol clears a field of 6+ Pokémon, stops on HP/B/map change/battle, and leaves the game in a clean state | 2-3 sessions |
| **M5** | **Rules and polish.** Settings (radius, level gap, costs, on/off) in the cheat-style menu or Settings; Help Tip page; all text translated; edge maps (water, caves, doubles, Frontier) disabled or handled | no softlock found in a sweep of the maps with visible Pokémon | 1-2 sessions |
| **M6** | **Release.** `patrol_build.py` in `build_editions.py`, both editions, write-up, GitHub release as an optional add-on | clean report, byte-identical BPS, guide in `docs/` | 1 session |

Total: roughly 10-14 working sessions, with M1/M2 (instant version) usable on their own after about 3-4.

## 8. Risks

1. **Follower control (highest).** Taking over the walker's movement without fighting the hack's own follow logic; a mistake parks it or crashes on
   map change. Mitigation: M0(b) first; held movements only; repair on every map load.
2. **Pathing in tight maps.** One-tile corridors and ledges. Mitigation: re-plan on a blocked step, skip after 3 failures, bail out after 10.
3. **Reuse of compiled code without source.** Calling the drop routine or reading Quick Catch's target list may not be possible cleanly. Mitigation:
   fallback to reimplementation from the documented rules.
4. **Balance.** A free XP/Candy farm trivialises the game. Mitigation: HP cost, cooldown, the sim making higher levels hard, no re-spawn farming (targets respawn
   only as the game spawns them), River decides defaults after playing M2.
5. **Object limit** (16 live objects) and the "objects outside the camera are not spawned" rule: the patrol only moves existing objects.
6. **Edition differences.** River maps add trainers and objects; tested in both.

## 9. Decisions recorded (River, 2026-10-29)

* Partner = the walker, chosen via the existing "Walk"/"Follow Me" party option.
* Target = fully autonomous patrol, with the milestones above as stopping points.
* Rewards = whatever the hack drops today (Exp. Candy / Berries / EV Feathers) **plus** the items the species can hold.
* **Button: SELECT** inside Quick Catch (L = switch ball, R = toggle lock are taken).
* **Cost: HP only** (no PP drain). No hard level-gap rule: the simulated fight itself makes higher-level targets far harder, which is the
  anti-abuse lever (tuned in M5). The patrol stops when the partner is below 40% HP.
* **The fight ignores moves** and uses only types (Scarlet/Violet style), see section 4.
* **No Pokédex changes** (no seen/caught credit).
* **Shiny targets: never fought and never removed.** The patrol skips them and gives a cue so the player can catch them: an exclamation
  emote over the shiny and a line in the summary ("A shiny Rattata was left for you"). Exact cue chosen in M3.
* **Release shape: River Edition only.** The feature is built into the River Edition (and therefore also "River + Cheats"); the translation
  builds and "Translation + Cheats" never contain it. It is its own feature, separate from the Cheat Device.

Consequences: gate on `RHT_EDITION=river` in `insert.py` (no new env switch); a River release gets its own version bump and notes;
`build_editions.py` already builds both river variants; the translation variants must come out byte-identical to today's.

## 11. M0 findings so far (2026-10-29, River v0.2.3 save)

Verified in the emulator on `dist/river-0.2.3/Pokemon River Azoth v0.2.3.{gba,sav}` (a scratch copy; map 3.79):

* **Quick Catch opens with L** in the overworld, but only with **Poké Balls in the bag** (the save had none; the HUD then reads
  "L:Switch Ball R:Toggle Lock", "Poké Ball x 20", the target's name). Standard button mode (already the save's). [V]
* **Visible wild Pokémon are runtime objects**, not map data: local ids **0xE0, 0xE1, 0xE2 ...** (224+), graphics id 193 (placeholder; sprites
  are swapped per species), moveType 79, spawned into free object slots. While Quick Catch is on their flags gain bit `0x800000` (animation paused). [V]
* **The walker** is object local id **0xFE (254)**, graphics id per species (152 in this save), flags 0x41, standing next to / behind the player. [V]
* **Quick Catch state** changes in EWRAM at `0x0203B730`-`0x0203B7E8` (a small struct; word `0x0203B744` goes 0 -> 0x400, `0x0203B748` gets
  the value 0x01C1) and at `0x02004170`/`0x0203B2E4`; the HUD text is built in `gStringVar` (`0x02021CD0`); the rest of the diff is window tilemaps
  (`0x02001C40`..., `0x02003000`-`0x02003C00`) and sprites. [V: raw diff, fields not yet named]
* **Code**: the per-frame Quick Catch path runs from the stub at `0x09CCD17E` (calling `0x09D5D2E8`/`0x09D5D298`) into the `0x09D53xxx` block
  (init writes at `0x09D53AB2`-`0x09D53BE6`, HUD drawing `0x09D535BC`, state accessor `0x09D534B4`, per-frame writes `0x09D538B0`, `0x09D54BF0`).
  The hack's code is compiled with veneers (`ldr r0,[pc]; bx r0`), so static reading is slow; watchpoints (`RHT_DEBUGGER=1`, `watch_read ... write=True`) are the efficient route. [V]
* **Not yet found**: where the target's species/level/personality is stored (a plain `struct Pokemon` checksum scan finds nothing, so the hack
  uses its own record or an expanded struct), the drop routine, how the walker is driven and suspended, free EWRAM.
* Debug recipe: copy the save to a scratch folder, boot with `RHT_LOAD_SAVE=1`, run an injected script `additem 4 20` (script ctx at `0x03000EB0`), press L.

Next: (1) read-watch the target record while a throw/lock happens to find its table; (2) watch the walker object's movement writes to see what drives it;
(3) catch the post-battle reward code with a write-watch on the bag (Exp. Candy ids 536-540) while a battle ends.

### 11.1 Quick Catch target model (M0a, resolved 2026-10-29)

Found with `break_at` on `CreateMon` / `CreateMonWithNature` and a read of the throw function `0x09D53CB8` (the "lock hypothesis" that
`gEnemyParty[0]` is pre-loaded was **wrong**: it is empty while aiming and is filled at throw time, then cleared).

* A visible wild Pokémon is just an **object event** (`gObjectEvents` at `0x02036E38`, 36-byte entries). Up to **three** live in the reserved local
  ids **0xE0, 0xE1, 0xE2** (graphics id 193 placeholder, moveType 79). [V]
* **Level = byte at object+29** (the throw function: `ldrb r5,[obj,#29]`; values outside 1..100 become 1). [V]
* **Species**: `0x09D53424(obj, u16 *out)` returns a bool and the species. For the three slot objects it is `VarGet(0x50FB + localId)`, i.e. hack
  vars **0x51DB / 0x51DC / 0x51DD** (for E0 / E1 / E2); other objects encode the species in the 16-bit graphics id (`obj[5] | obj[35]<<8`, bit
  0x4000 set). `0x09D53040(obj)` is the "is a valid visible-Pokémon object" predicate. [V from disassembly; vars not yet read live]
* **Quick Catch state struct** (pointer from the accessor `0x09D534B4`, lives around `0x0203B730`): `+6` index of the locked/aimed object, `+7`,
  `+8`/`+9` map group/number the target belongs to, `+24` (u16) species of the aimed target, `+16`/`+17` throw timers. [V partly]
* **Throw sequence** (`0x09D53CB8`): `0x09D53888` validates the aimed target -> level from `obj[29]` -> `0x09D6BA78(species, level, ...)` builds the
  mon in `gEnemyParty[0]` -> ball animation -> catch roll (`0x09D0F5B0`) or the battle starts; then the object is removed and `gEnemyParty[0]` cleared.
* So for the patrol: targets = the objects with local id 0xE0-0xE2 that pass `0x09D53040`; species and level are readable without any struct
  decoding; the same `0x09D6BA78` can materialise a real `struct Pokemon` for shininess, held items and moves, and the object-removal path of
  the throw (after `0x09D53DDC`) is the way to take a target off the map. The `CreateMonWithNature` hook (`0x09D09D58`) is the generic engine
  hook (Unown letters etc.), not Quick Catch's.

Still open from M0: (b) the walker, (c) the reward routine, (e) free EWRAM. Walker facts so far: object local id 0xFE, graphics id per species, flags 0x41.

Next probes: (1) read vars 0x51DB-0x51DD live and confirm against the HUD species; (2) watch writes to the walker object's movement fields
(+0x1C... / movementType) to find what drives it; (3) break/watch bag writes (Exp. Candy ids 536-540) across a won battle for the reward routine.

### 11.2 Walker, rewards, RAM (M0b/c/e, 2026-10-29)

**Species list confirmed**: hack vars live at `0x0203B374 + 2*(var-0x5000)` (workbench `knowledge/guides/memory.md`), so vars 0x51DB-0x51DD sit at
`0x0203B72A/C/E`: exactly the three species words seen in the Quick Catch dump. [V]

**Walker (M0b)** [V by breakpoints on `ObjectEventSetHeldMovement` while the player steps]
* **Follower state struct at `0x0203B818`** (pointer literal at `0x09D32400`): `+0` active flag (1), `+1` the walker's index in `gObjectEvents`
  (1 in the test), `+4` its local id (0xFE), later bytes hold its graphics/state. Live value: `01 01 00 00 fe 42 03 00 3a 00 12 00 ...`.
* The walker's movementType is 0 (none): it is **driven by held movements issued by the hack's field-input code**. Every free frame the big
  function at `0x09D320B0`-`0x09D32608` (the same function `ProcessPlayerFieldInput` jumps into) does, when no player action was handled and
  state+0 is set: `ObjectEventClearHeldMovementIfFinished(walker)` then `ObjectEventSetHeldMovement(walker, 0xB6)` (0xB6 = idle/face action; call
  site `0x09D32344`). Its steps come from `0x09D33533` inside the function `0x09D33342`-`0x09D337F0` (called from the player's step), which
  issues the follow movement (e.g. action 0x11).
* **Takeover plan**: the cheapest safe switch is a flag the patrol sets that makes those two sites do nothing for the walker (wrap the
  `ObjectEventSetHeldMovement` thunk literal at `0x09D32424`, and the follow-step call, to skip when the patrol owns the walker), then the patrol
  issues its own held movements and, on return, clears the flag and teleports the walker next to the player if it is far. Held movements only
  (no `applymovement` chains), per #37.

**Rewards (M0c)** [V partly]
* A won battle ends the drop with `AddBagItem(item, qty)` called from `0x09D2AF14`, inside the function `0x09D2AE10`-`0x09D2AF4C`: it loops the
  party (participants bitmask, alive, not an egg), computes the amount (`0x09D2ACD4`, times the Exp. Share multiplier `0x09D2A820`), picks the
  feather from a 6-entry table at **0x09DDF196 = {57, 58, 59, 62, 60, 61}** (Health, Muscle, Resist, Swift, Genius, Clever; index = EV stat in the
  order HP, Atk, Def, Spe, SpA, SpD), calls `AddBagItem`, and fills the text buffers for the "obtained" line. The test drop was a Muscle Wing (58) with the EV switch off.
* It is entangled with battle state (participants, text buffers), so the plan is to **reimplement the drop from the documented rules** (Candy 20 /
  Berries 30 / Feathers 50, non-stacking, EV switch, Exp. Share, Power items) using the same item ids and this feather table, and not to call it.
  The Candy and Berry branches, the EV-switch variable and the Power-item rule are still to locate in M2 (they sit in the same neighbourhood,
  `0x09D2A8xx`-`0x09D2B0xx`).
* `Cmd_getexp` (0x08021A68) was not hit in the test, so the hack replaces it: XP is also applied elsewhere; M2 finds it to reuse its formula.

**RAM (M0e)**: the link buffers are the safe borrow (as the Frontier does). Literal scan of the River ROM: no code refers to
`0x02022200`-`0x020222FF` except a handful of odd constants, so **patrol state = `0x02022200`-`0x0202227F` (128 bytes)**; verify with a write
watchpoint across a Quick Catch + battle session in M1. Frontier keeps `0x02022400`-`0x020227FF`.

**M0 status**: (a) target model, (b) walker control, (c) reward shape, (e) RAM are resolved enough to start M1. Still unknown and
scheduled: the XP code path, the EV-switch variable and the Candy/Berry branches (M2), the held-item/shiny details of a materialised target (M1).

## 12. M1 built: the instant strike (2026-10-29)

Files: `scripts/native/patrol.s` (SELECT hook, `__call_via_rN` shims), `scripts/native/patrol.c` (the strike, in C), `scripts/patrol_build.py`
(links into the free pool, result script, patches), called from `insert.py` **only when `RHT_EDITION=river`** (so both River variants carry it,
the translation variants are byte-identical to before: `69e4e357...` and `ca3da9e8...`).

How it works:
* One patched literal, the `ProcessPlayerFieldInput` trampoline (`0x0806CACC`). The patrol wrapper reads `newKeys`; on SELECT while Quick
  Catch is active (state byte `0x0203B743` = 1) it calls `patrol_select()`. Otherwise it jumps to the previous target, so it chains in front of the
  Cheat Device's wrapper (River + Cheats). Side effect: with Quick Catch open, SELECT strikes; the cheat hotkey (SELECT+R) works outside it.
* `patrol_select()`: validates the aimed target with the game's own check (`0x09D53889`), reads level (`obj+0x1D`) and species (`QC+0x18`),
  finds the partner as the party member whose species equals the walker's graphics id (else the lead), refuses below 40% HP, builds the target with the
  game's own creation call (`0x09D6BA79`), and **stops on a shiny**: the Pokémon is left alone and a real wild battle starts with that very Pokémon
  (`dowildbattle`), so the player can catch it. Otherwise a stat-based fight runs (typed hit, see section 4: best own type with STAB against the defender's types through the game's chart, higher of Atk/SpA, 85-100% roll, speed
  order, partner retreats under 40% HP; verified: a Grass partner beat a Lv 2 Starly and retreated from Lv 3 ones), XP = `expYield * level / 7` (capped at level 100) applied with `SetMonData` +
  `CalculateMonStats`, the target is removed (`0x09D55F69` with its local id in `LastTalked`), Quick Catch is closed (`0x09D53E65` on its task) and
  `patrol_script` reports the result.
* Result vars: `0x8004` 1 won / 2 retreated / 3 shiny / 4 too hurt, `0x8005` EXP, `0x8006` partner slot, `0x8007` target species.
* Scratch RAM: `0x02022200` (one halfword: the local id to remove).

Verified in mGBA (River v0.2.3 save, scratch copy): the SELECT strike ("AAA beat Starly! It gained 16 EXP.", HP 20 -> 18, 24 EXP / HP 18 -> 16 on
the second), target removed, Quick Catch closed and reusable; the too-hurt refusal at 6/20 HP; the retreat message; the shiny branch (forced
with `RHT_PATROL_TEST=shiny`: "This Starly is shiny! ... holds it still for you", then the real battle); River + Cheats (cheat menu and strike
both work through the chain). All four editions build with clean reports and byte-identical BPS round trips.

Known gaps (by design for M1): no abilities/items in the fight (never planned), no drops or held items (M2), level-ups do not learn moves or evolve (M2),
no walking or animation (M3), one target per press (M4). The partner shown by the walker is matched by species, so two party members of the same
species resolve to the first alive one. Test switches: `RHT_PATROL_TEST=shiny|retreat` build scratch ROMs for the two rare branches.

## 13. M2 built: rewards and level-ups (2026-10-29)

**The hack's own drop rule was found** (the Quick Catch reward chooser at `0x09D56058`-`0x09D563FC`), so the patrol copies it exactly instead of
reimplementing it from the Help Tips: one roll 0-99 per win:

| Roll | Reward |
|---|---|
| 0-19 (20%) | Exp. Candy by the **target's level**: XS (536) below 20, S (537) below 40, M (538) below 60, L (539) below 80, XL (540) from 80 |
| 20-49 (30%) | one of ten Berries, `Random() % 10` into the table at `0x09DE4674 + 8` (items 133-142: Cheri to Sitrus) |
| 50-99 (50%) | EV Feathers: the hack's own function `0x09D2ADA5(partner mon, defeated species, u16 out[6])`, which applies Power items, the doubling item and the Exp. Share party multiplier and calls `AddBagItem` per stat (the Feather ids come from the table `{57,58,59,62,60,61}` at `0x09DDF196`); `out[stat]` is the count, negative = no room |

Plus the **species' held items** from the base stats (`item1` +12, `item2` +14): equal items are always dropped, otherwise 50% item1 and 5% item2
(the engine's wild-hold odds). The Feathers ignore the EV switch, as the Help Tip says ("whatever the EV switch").

**XP and level-ups**: `expYield * level / 7`, applied to the partner (growth rate of the *partner*, capped at level 100). Each gained level is stepped
through one by one so `MonTryLearningNewMove` (0x0803EA89) sees every level: moves are learned when a slot is free (up to two are shown; a full
moveset skips the move), then the partner's bit is set in `gLeveledUpInBattle` (0x03004FD4) so the engine's **own evolution check** runs after the next
real battle. A bug caught while building this: the M1 EXP cap used the target's growth rate instead of the partner's (fixed).

**Result vars** (one fight; *corrected in section 15*): `0x8000` new level, `0x8001`/`0x8002` learned moves, `0x8003` held item dropped, `0x8008`-`0x800B` reward slots A and B (id, quantity; 0 = no room). The script says "Found X xN!", "No room in the bag for X!", "grew to Lv. N!", "learned M!" and "The wild X was holding Y!".

Verified in mGBA (River v0.2.3 save, scratch copies): 14 strikes gave 11 wins with drops in the expected mix (6 Feather, 2 Exp. Candy XS, 4
Berries, 0 held at 5%), level-ups to Lv 6-8 with Razor Leaf learned, "Found Aspear Berry" on screen; the held-item path forced with
`RHT_PATROL_TEST=held` (Starly's rare item 450 landed in the bag slot). Not yet exercised live: the bag-full message, an evolution actually happening
after the next battle, and a two-moves-at-one-level case.

Test switches now: `RHT_PATROL_TEST=shiny|retreat|held`.

## 14. M3 built: the visible strike (2026-10-29)

SELECT in Quick Catch now closes Quick Catch and starts a **task** (`patrol_task`, `scripts/native/patrol.c`) that walks the partner to the target, makes it
hop at the target, runs the fight and the rewards (sections 4-5), shows the result script and walks the partner back.

**Memory rules (River, 2026-10-29: "be careful when writing to memory")**, and how they are met:
* **One private block**: `struct Patrol` at `0x02022200`-`0x020223FF` (386 bytes used) in the unused link receive buffer. A write-watch over a full session of
  menus, walking, a wild battle and a strike saw **no other writer**. It holds the state and the 13 x 13 search grid, so nothing big lives on the stack.
* **Stack**: the deepest patrol call (`CreateMon` from the task) is at `sp = 0x3007CC8`, 32 bytes below Quick Catch's own throw; IWRAM data ends at
  `0x03007480`, so about 2 KB of headroom remain.
* **The walker is never written to directly**: only through the engine's own `ObjectEventSetHeldMovement`, `ObjectEventClearHeldMovement` and
  `MoveObjectEventToMapCoords`. Object indices (target, walker) are checked against 0-15 and against local id / pointer before every use.
* **Everything else written**: the script vars `0x8000`-`0x800C`, `LastTalked`, `gLeveledUpInBattle` (one bit), `gEnemyParty[0]` (created and zeroed outside battle),
  the partner's `SetMonData`/`CalculateMonStats`, `AddBagItem`: all through engine functions.
* **The follower code is silenced, not patched**: the two literals through which the hack's follower code calls `ObjectEventSetHeldMovement`
  (`0x09D32424` idle each frame, `0x09D3367C` follow step) point at `patrol_hold_wrap`, which drops the call only for the walker, only while the flag in the block is set
  **and** the task table shows a live `patrol_task`; a stale flag after a reset cannot freeze the walker (tested).
* **Every exit clears the flag**: map change (touches nothing in the new map), the walker or its identity gone, 30 s / 90 steps, three steps without progress, a recall, a shiny, the
  end of the return walk. After a stuck walk or a timeout the walker is placed behind the player with the engine's teleport.

Flow and numbers: START (give the controls back: returning 1 from the SELECT hook makes the caller lock the player), WALK (a breadth-first search over
the 13 x 13 window per step, `GetCollisionAtCoords` for each neighbour, goal = the reachable tile closest to the target), STRIKE (face the target, hop,
then `fight()`), RETURN (same search toward the player until adjacent). The task waits whenever the field controls are locked (a message, a menu). **B recalls**
the partner while it is walking. A shiny ends the patrol before the battle starts; "too hurt" refuses without any walk.

Verified in mGBA (River v0.2.3 save, scratch copies): the partner walks 4-10 steps, hops and returns next to the player; the follower follows normally afterwards
(8 moves); wins (16 EXP, drops, target removal call with the right local id), retreats, the too-hurt refusal, the B recall after 7 steps toward a far target, a
warp to another map mid-walk (task destroyed, flag cleared), the stale flag, and the shiny path (forced build: patrol ended, task gone, real battle). Not covered: a
target that is truly unreachable (the 3-fail abort and message 5), and timeouts; both follow the same abort code as the tested ones.

Known gaps: no target flash or sound, the return stops next to the player (not exactly behind), one target per press (M4), a map-change during the result
script leaves nothing to clean up. Results are not yet visible in the walker's sprite (no attack animation beyond the hop).

## 15. M4 built: the autonomous patrol (2026-10-29)

One SELECT now sends the partner on a **patrol**: after each win it picks the next visible Pokémon (local ids 0xE0-0xE2 that pass the Quick Catch validity
check `0x09D53425`, within 12 tiles of the player, nearest to the walker first), walks to it, fights it, removes it, waits 24 frames and goes on. The rewards are
applied per kill as in M2; **one summary at the end** replaces the per-kill messages.

* **Stop conditions** (each becomes a reason code and a walk back): no target left in range or the nearest ones cannot be reached (3 steps without progress),
  the partner retreats or is too hurt to start a fight ("worn out"), 10 kills (`MAX_KILLS`), B (recall; works while walking or waiting), 30 s on one target / 400 steps / 120 s in
  total, a map change (nothing in the new map is touched), a shiny (the summary so far, then a real battle).
* **Summary** (shown when the partner is back next to the player; nothing is shown if there were no kills and no reason to say): "AAA beat 7 Pokémon and gained 127 EXP!", "AAA grew to Lv. 7!",
  "AAA learned <move>!", one line per item found ("Found X xN!", or "No room in the bag for X!"), then the reason line ("is worn out and came back", "couldn't get close", "is too hurt").
  The totals live in the same private block (`struct Patrol`: 76 + 338 = 414 of 512 bytes); a native step function (`patrol_sum_step`) feeds the script one line at a time.
* **Bug fixed while building this (it affected M2 and M3)**: the script variables are not contiguous. `0x8000`-`0x800B` are at `0x020370B8`-`0x020370CE`, but **`0x800C` is
  `gSpecialVar_Facing` at `0x020370D4`** and `0x800D` is `gSpecialVar_Result` at `0x020370D0` (read from the game's `gSpecialVars` table at `0x0815FD0C`). The held-item slot had been
  written at "index 12" (the Result variable) and the script read `0x800C` (the player's facing, usually non-zero), which would have printed a bogus "was holding" line after wins. Now the held item
  uses `0x8003`, the summary kind goes through the real Result variable, and nothing writes `0x800C`.
* New test switch: `RHT_PATROL_TEST=nohurt` (fights cost no HP) to exercise long chains. All test switches: `shiny|retreat|held|nohurt`.

Verified in mGBA (River v0.2.3 save, scratch copies): a chain of **7 kills in one press** (Lv 5 to 7, one move learned, 5 different items, ended by a lost fight), a chain of 2 and 4 ended the same way with
the matching summaries ("AAA beat 2 Pokémon and gained 40 EXP!", item lines, "is worn out"), **B recall in the middle of a chain** (reason 6, walker back, summary without a reason line), and the earlier M3 paths
(map change, stale flag, shiny, too hurt). Not reached in testing: the 10-kill cap and the "no target left" ending (both only add a reason code), a full bag in the middle of a chain.

Known gaps: no on-screen status line while the patrol runs (the walker's movement is the feedback), no cooldown between presses, the 10-kill cap and 12-tile radius are constants in `patrol.c`
(to tune after playing), the partner always ends next to the player rather than exactly behind it.

## 16. M5 built: settings and polish (2026-10-29)

* **Settings** (saved in the game as hack flags, so they survive saving and loading; an old save starts with the defaults): `L + R + SELECT` anywhere in the overworld opens a short dialogue
  (the game's multichoice table is already extended by the Cheat Device, so the patrol uses yes/no prompts instead):
  * **Partner Patrol ON/OFF** (flag `0x13B0`). Off: SELECT in Quick Catch is left to the game and no patrol starts.
  * **Size** (flags `0x13B1` short, `0x13B2` long, none = normal): short = up to 4 Pokémon within 8 tiles, **normal = 10 within 12**, long = 20 within 16. Each "Make it ..." prompt cycles normal, long, short.
  * SELECT in Quick Catch with nothing aimed opens the same dialogue (rare: Quick Catch does not open without visible Pokémon).
* **One-time tip** (flag `0x13B3`), after the first patrol's summary: "Tip: press B while your partner is out to call it back. Hold L and R and press SELECT to change the Partner Patrol settings."
  This is River-only text living in the patrol's own script, so the translation's Help Tips are untouched; there is no Help Tips page for the patrol.
* **Text**: every patrol message is English in the patrol's own scripts (nothing Chinese is involved); long prompts scroll to a second page.
* **Edge maps**: nothing is switched off by map. Water, caves and corridors are handled by the existing checks: no walker (surfing/biking) means SELECT is ignored; blocked terrain
  means the search finds no way closer (3 tries, "couldn't get close", walker teleported next to the player if it was lost); the Frontier arenas have no visible Pokémon.
* Flags `0x13B0`-`0x13B3` are in use (the reserved range is `0x13B0`-`0x13BF`).

Verified in mGBA (scratch copies of the River v0.2.3 save): the settings dialogue (ON/OFF, size cycle; LONG persisted when reopened), the patrol being ignored when OFF and working again after
turning it ON, the `L+R+SELECT` hotkey, and the tip appearing once (first patrol 12 messages including both tip pages, the second patrol none).

**The map sweep (done, `scripts/patrol_sweep.py`)**: the first attempts (blind walking on eight group-3 maps 3.29-3.40) found no visible Pokémon because **those maps have no wild-encounter data at all**
(the live wild table at `0x1E468B0` lists which maps do). The sweep that counts picks 26 maps from that table: group 3 routes (3.42-3.106), group 1 (1.39-1.124), cave floors of group 55 (55.17, 55.22, 55.26), 53.4, 53.9 and 48.3.
For each map it warps onto a pair of adjacent land-encounter tiles (found from the tileset attribute words: encounter type 1), steps between them until a visible Pokémon spawns, boosts the partner's stats so that
fights are won, opens Quick Catch and presses SELECT, and checks that the game ends clean: the patrol ended, no patrol task is left, the map is unchanged, the walker is present, the controls come back, and the player can move.

Result (2026-10-29, River v0.2.3 save, current build): **25 of 26 maps ran a full patrol and all 25 passed every check**; 3.46 has no grass pair (nothing to test). Across the runs: kills of 0 (the partner lost the first fight or the target was unreachable) up to
**10 (the kill cap, reached on 3.80 and one more map)**, the "couldn't get close" ending twice (reason 5, the unreachable path that had not been exercised before), 21 runs ended by a lost fight (reason 2), 2 by the cap or no target (reason 1), longest patrol 1,593
frames, at most 53 steps. No softlock, no leftover task, no stray walker. Not covered by the sweep: water (surfing/biking: SELECT is ignored without a walker), Chapter 2 and Frontier maps, and a patrol interrupted by the player on every map (B recall and the map-change abort were tested by hand on 3.79 and 3.85).

## 17. Bug fix: the patrol could lock itself out (found in River v0.4, 2026-10-29)

**Report (River):** a save in which the patrol could no longer be started and its settings could not be reached to unlock it.

**Cause (reproduced):** the patrol runs as a game task, and the game wipes the whole task list when a battle starts (observed: the patrol's task slot became the dummy task while `struct Patrol.active` stayed 1).
`patrol_select` and `patrol_open_settings` both refuse to act while `active` is set, so after such an interruption SELECT in Quick Catch did nothing and **L + R + SELECT showed the game's own
"An item in the Bag can be registered to Select" message instead of the settings**. The flag lives in EWRAM (never saved), so a real reset cleared it, but a save state, or any reload that does not reboot the game, kept it. The wrapper that
silences the follower code already checked that the task was alive; the two hotkey handlers did not.

**Fix:** `patrol_watchdog()` runs on every free overworld frame (called first thing from `patrol_pfi`): if `active` is set and its task is not a live `patrol_task`, the task is re-created, so a patrol interrupted by a battle
resumes, and a stale or garbage state ends itself at the task's first checks (map, walker identity); if no task can be created, `active` is cleared. Also new: pressing SELECT in Quick Catch with nobody walking behind you now says
"Nobody is walking behind you. Put a Pokémon out to walk first, then try again." (reason code 7) instead of doing nothing.

Verified from the reporter's own save (River v0.4, scratch copy): the fresh patrol works; a stale flag heals within 40 frames and the patrol works afterwards; the Start menu opened mid-patrol does not break it; a forced wild battle mid-patrol kills the task
(confirmed) and after the battle the patrol state is clean, a full patrol runs and the settings hotkey opens the settings; the no-walker message shows. Lesson: any state that outlives its task needs the same liveness check wherever it is read.

## 18. Partner integrity guard (post v0.4.1)

**Bug (reported by River):** the partner went offscreen, and later a moving NPC chased the player as if it were the partner.
**Cause (reproduced):** while the camera scrolls the engine deletes every object whose current and initial coordinates are both outside the camera window
(about -9..+10 tiles across, -7..+9 down from the player). A walker that strays that far (a long patrol, or a lagging follower) is freed, but the hack's follower
state (`0x0203B818`: `+0` active, `+1` object index) keeps pointing at its slot. The next template NPC spawned into that slot is then driven by the hack's
follower code (idle movement every frame, follow step when the player moves).
**Fix, three layers (none writes to memory the hack owns, except repairing the index):**
1. `patrol_hold_wrap` (patrol.s) also drops the follower's `SetHeldMovement` when the follower index names an object that is not live with local id `0xFE`.
2. `partner_guard()` (patrol.c, every free frame): a dead index is re-pointed to a live `0xFE` object if one exists. The active flag is left alone: the hack's own
   map-load code respawns the walker while it is set (checked: after a warp the walker is object 1 again).
3. The patrol keeps the walker and its targets inside the keep-alive window (targets within 7 across / 5 up / 6 down of the player; the walker is brought home at 8 / 6 / 7).
**Verified:** walker pushed 30 tiles away + camera scroll: object deleted, follower state untouched, no NPC moved; map reload respawns the walker; sweep on
3.42 / 3.80 / 1.39 / 55.17 / 3.90 with the v0.2.3 save: 5/5 clean (3.80: 10 kills).

**Intensive test results (2026-10-29):**
* A/B with the walker's slot relabelled as an NPC (`scripts/partner_guard_test.py`, 220 random taps, battles fled): v0.4.1 moved the slot 180-195 times (the reported chase, reproduced);
  the guard build 0 times in 4 seeds (up to 6 battles, a route connection crossing, and a genuine slot reuse by a wandering NPC). A map reload respawns the walker every time.
* 25 map reloads + 15 forced-offscreen injections: no duplicate walkers, no missing walker after a reload. (The hack itself pulls a far walker back; a deletion was only caught once, and the
  follower state stayed untouched while the slot stayed inert.)
* Full 26-map patrol sweep with the v0.2.3 save: 25 runs, 10-kill caps reached on 3.80 and 1.50, the rest ended by "worn out"/"couldn't get close", no patrol task left behind, controls back everywhere.
  The sweep's "player can move" check was fixed (Down+Up cancelled out; any single step now counts): the two earlier failures (3.86, 3.101) were that check, not the patrol.

## 19. Evolution prompt (M6, River v0.5)

After the summary (every ending except the shiny one) the script runs `patrol_evolve`: if the engine's own `gLeveledUpInBattle` bit (`0x03004FD4`) is set for the partner's slot and `GetEvolutionTargetSpecies`
(`0x08042EC4`, mode 0, the party menu's own call) names a species, it sets `gCB2_AfterEvolution` (`0x0300537C`) to `CB2_ReturnToFieldContinueScript` (`0x080568C5`) and calls
`BeginEvolutionScene` (`0x080CDDA8`, canStop = 1); the script then `waitstate`s and resumes on the field. The bit is cleared either way, so the post-battle check does not ask twice.
Verified in the emulator (a Charmander given by script, level byte 40, bit set, the real summary script): the scene opens ("What? Charmander is evolving!"), A evolves it, B cancels it, both return
to the overworld with the script finished, the field unlocked and the walker respawned; sweep 3.80 / 1.50 / 3.84 / 3.42 clean. The sweep's `free()` now also requires the overworld callback.

## 20. Learn-move prompt (M7, River v0.5)

`give_exp` used to skip a level-up move when the moveset was full (`TryLearnMove` returns 0xFFFF and leaves the move in `gMoveToLearn`, `0x02024022`). It now records it (`P->pend[6]`, `npend`, `pend_i`, +414..+427 of the block).
After the summary, before the evolution step, the script loops: `patrol_learn_next` (skips moves already known; 0x800D = 1, move in 0x8003) -> `ask` -> `patrol_learn_open`
(`ShowSelectMovePokemonSummaryScreen` `0x08134739`: party, slot, last index, callback = `CB2_ReturnToFieldContinueScript` `0x080568C5`, new move on the stack; `waitstate`) ->
`patrol_learn_apply`: the chosen slot is the engine's own `GetMoveSlotToReplace()` byte `0x0203B16E` (0-3, 4 = cancelled), applied as the party menu does it: `RemoveMonPPBonus` `0x08041065`, `SetMonMoveSlot` `0x0803E965`.
B on the screen = slot 4 -> "Stop trying to teach X?" (Yes: `patrol_learn_skip`; No: the screen again).
Verified in the emulator (a Charmander given by script with Tackle/Ember/Growl/Scratch, Flamethrower pending, the real summary script): the question, the Known Moves screen with the new move at the bottom,
A on slot 0 -> "1, 2 and... Poof! ... forgot Tackle. And... learned Flamethrower!"; a second run lists Flamethrower in slot 0 (written); B -> slot 4, "Stop trying to teach..." -> Yes -> pend_i advances, script ends;
sweep 3.80 / 1.50 / 3.84 / 3.42 / 3.82 clean (one harness warp flake in a longer chain, not reproduced; the sweep now prints cb2/ctx/lock on a failed warp).

### 20.1 Sprite after evolution (v0.5)

The hack draws the walker from the species kept in its follower state (`0x0203B818 + 0x12`, u16) and in the walker object (`+5` low byte, `+35` high byte); the graphics id is the species + 256 (Chikorita 152 -> 408). Both are refreshed
only on a map change or a menu, so an evolved partner kept its old sprite. `patrol_evolve` remembers the walker's graphics id and the old species (`P->evo_gfx`, `P->evo_sp`, +428/+430) and hands the scene a return callback (`evo_done`)
that, before `CB2_ReturnToFieldContinueScript` rebuilds the field, writes `species + (gfx - old species)` into those three places when the walker still shows the old sprite. A B-cancelled evolution changes nothing (same species).
`find_partner` now also accepts `gfx == species + 256` (it only matched `gfx == species`, so it fell back to the lead). Verified: the evolved walker's graphics id goes 408 -> 409 on the field; sweep clean.
Reported and not reproduced: the partner sometimes drawn one tile away from its real tile (a sprite-vs-coordinates check after 4 patrols, patrols started mid-step, and an evolution found no drift).
