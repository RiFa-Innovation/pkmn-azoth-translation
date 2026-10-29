# Partner Patrol: design and milestones

Status: **draft 2, 2026-10-29. Decisions recorded (section 9); M0 in progress.** Goal set by River: in Quick Catch mode, send the walking partner Pokémon out to fight the
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
cheat menu (SELECT+START) is unrelated and untouched.

## 4. The simulated fight (no battle screen)

Gen-3 damage, deliberately simplified:

* Wild mon built once with the engine (`CreateMon` into a scratch slot of `gEnemyParty`, species and level from the target [?: M0 finds where
  the object stores them]) so its stats and moves are real. Partner uses its real stats and moves.
* Each round: the faster mon acts first; partner picks the move with the best expected damage (power x STAB x type chart x accuracy) among
  moves with PP; the wild mon uses its best damaging move. Damage = `((2L/5+2) * P * A/D) / 50 + 2`, x STAB, x type effectiveness (the hack's
  own type chart), x random 85-100%, x critical (1/16, x2). Status moves, abilities, held items, weather: ignored in v1 [decision: keep simple
  and predictable]. Max 6 rounds per target; a draw counts as a retreat (no rewards).
* Partner faints -> patrol ends; nothing is lost beyond the fainted state (the normal rules apply afterwards).

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
