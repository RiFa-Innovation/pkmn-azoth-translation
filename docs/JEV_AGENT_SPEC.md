# Jev game agent: design and technical spec

Status: **draft 1, 2026-10-23.** A battle prototype exists in `scripts/agent/` and is uncommitted; no Jev call has been made with a
real key yet. This is tooling for playtesting and is never shipped in the ROM or BPS. Read `EMULATOR.md` first: the agent
drives the same headless mGBA bridge (`scripts/emu.py`, `scripts/play.py`).

Labels: **[V]** verified in this repo/ROM on the date given, **[D]** from the FireRed decomp (vanilla behaviour; the hack's CFRU
engine may differ), **[?]** an assumption that a spike (section 9) must settle first.

---------------------------------------------------------------------------------------------------------------

## 1. Goal and scope

Let a cheap, fast classifier make the many small in-game decisions a playtest needs, so the emulator can play long
stretches of Azoth unattended and stop only where a human (or a larger model) is needed.

- **Primary use:** automated playtesting. Get through battles and prompts to reach story points, and catch freezes,
  softlocks and untranslated text along the way (screenshots plus the existing `hackdb`/`watch_*` tooling).
- **Secondary:** a cost/quality benchmark. Is a decision classifier (Jev) better than a hand-written heuristic, and when is
  it worth escalating to a larger model?
- **Out of scope:** competitive play, anything shipped to players, and pixel-based perception (the state always comes from
  RAM).

Principle: **plain code computes, the classifier only chooses.** Every number the decision needs (type multiplier, damage
%, KO odds, turn order) is worked out in Python and written into each option's description. Jev ranks the options and
never does arithmetic.

## 2. Jev (TypeSafe) contract

| Item | Value |
|---|---|
| Endpoint | `POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer $TYPESAFE_API_KEY` **[V]** (401 with an invalid key) |
| Body | `{model, state, questions}`; `state` may be a string, object or array |
| Models | `jev-latest`, `jev-preview`, pinned `jev-1.13.0` (pin it for benchmark runs: `JEV_MODEL`) |
| Question types | `choice` (criteria `{key: description\|null}`, up to 255 options), `noul` (yes/no probability), `score` (2..10 levels) |
| Answer | `answers.<q>.{choice, probabilities, confidence}` / `noul` / `score`; `usage.{input_tokens, output_tokens}` |
| Price | $0.042 per 1M input tokens, output free (vendor figure, 2026-10) |
| Latency | "usually under 200 ms" (vendor figure); measured p50 200 ms, p95 254 ms, max 537 ms over 32 decisions **[V]** 2026-10-23 |
| Limits | 80 req/s, 100k tok/s (adjusted dynamically); 429/529 should be retried with backoff |

Cost: one battle decision is 512-817 input tokens (median 762) and 26-81 output tokens **[V]** 2026-10-23, so roughly $0.00003 per
decision, or about $0.30 for 10,000 decisions.

Key handling: read only from the environment variable `TYPESAFE_API_KEY`. Never write it to logs, saves or the repo. The
JSONL log records the request body without headers.

## 3. Architecture

```
mGBA bridge ──► observe.py ──► options.py ──► decide.py ──► run.py (act) ──► mGBA
                RAM → state    legal options   Jev choice +   buttons, then a RAM check
                               + precomputed   confidence gate that the cursor landed
                               facts           → heuristic / escalate
                                    │
                                    └──► saves/agent/decisions.jsonl (state, options, heuristic, jev, played, outcome)
```

| Module | Responsibility | Status |
|---|---|---|
| `observe.py` | phase detection; battle snapshot (`you`, `foe`, `party`, `kind`); `Dex` (species, moves and abilities from the ROM + `text/en/tables`) | built |
| `options.py` | Gen 6 type chart, damage range, speed order, option builder, `context()` summary, heuristic baseline | built |
| `decide.py` | Jev request, confidence gate, fallback, log record | built, not yet run with a real key |
| `run.py` | menu driver (grid cursors, party menu), battle loop, replacements, `wild` test helper, CLI | built |

## 4. RAM and screen facts (the observer's contract)

All verified **[V] 2026-10-23** on the English build with the playtest save, unless marked.

| What | Address | Notes |
|---|---|---|
| `gMain.callback2` | `0x030030F4` | overworld `0x080565B5`, battle `0x08011101`, battle party menu `0x0811EBA1` |
| player controller func | `0x03004FE0` | choose action `0x0802E439`, choose move `0x0802EA11`; anything else = busy |
| action / move cursor | `0x02023FF8` / `0x02023FFC` | u8 per battler; 2x2 grids (0 Fight, 1 Bag, 2 Pokémon, 3 Run) |
| `gBattleMons` | `0x02023BE4`, 0x58 each | vanilla layout; stages at +0x19..+0x1F (6 = neutral); +0x23 is a third type byte (CFRU, ignored) **[?]** |
| `gBattleTypeFlags` | `0x02022B4C` | bit 0 double, bit 3 trainer **[D]** |
| `gBattlerPartyIndexes` | `0x02023BCE` | u16 per battler |
| `gPlayerParty` / count | `0x02024284` / `0x02024029` | **substructs are plain, in fixed G A E M order** (no XOR, no shuffle) |
| `gBattlePartyCurrentOrder` | `0x0203B0DC` | 6 nibbles, high nibble first: menu position → party slot |
| `gPartyMenu.slotId` | `0x0203B0A9` | battle party menu is a 2-column grid (0 1 / 2 3 / 4 5) |
| party reorder | n/a | **while the battle party menu is open, `gPlayerParty` is physically in menu order** and is restored when it closes; `observe.party()` remaps |
| ROM tables | `frontier_data.py` | base stats `0x176DFBC`, CFRU moves `0x1E0326F` (category = byte 10 & 3) |
| script injection | `0x0203FF00` + ctx `0x03000EB0` | test helper only (`setwildbattle`/`dowildbattle`) |

Damage check: Aqua Jet vs Lv 22 Onix was estimated at 77-92% and actually did 81%.

## 5. Decision surfaces

Every decision point is one Jev request: a `choice` question, sometimes with `noul`/`score` side questions in the same call.

| # | Surface | Options | Status |
|---|---|---|---|
| D1 | Battle turn (single) | moves with PP, switches, run (wild) | **built** |
| D2 | Replacement (faint, U-turn/Volt Switch/Baton Pass) | switches only | **built** |
| D3 | Items in battle | Potion family, status heals, X items; options carry "heals N% of max" | todo |
| D4 | Catching | `noul` "worth catching?" (new species, party/box space, goal) + ball choice; needs a ball count | todo |
| D5 | Move learning | "replace which move / skip": options carry type, power, coverage the team would lose | todo (currently A, then B out of the summary) |
| D6 | Evolution prompt | allow / cancel (default allow) | todo (A works today) |
| D7 | Double battles | per-battler choices plus targets; refused today | todo, late |
| D8 | Yes/No and multichoice prompts in scripts | the prompt text (decoded from the text printer) plus the menu entries | todo |
| D9 | Overworld goal | heal, next trainer, a warp or story target; carried out by `play.py` `path_to`/`goto` | todo, last |

Instructions per goal live in `decide.INSTRUCTIONS` (`win`, `flee`; add `catch`, `grind`, `explore`).

## 6. Confidence gate and escalation

1. Jev answers with `confidence >= min_conf` (default 0.5, to be tuned in M2) and a valid key: play it.
2. Otherwise play the heuristic, logging the reason.
3. Planned: a third tier escalates hard cases (low confidence *and* Jev and the heuristic disagree, or a known-hard
   surface such as D5 or D8) to a larger model with reasoning, at most N times per run. That model is configurable;
   it is never the default path.

The log keeps `agree` (Jev vs heuristic), `confidence`, `ms` and `usage` per record, so the threshold can be tuned
offline from the logs.

## 7. Evaluation (decides whether Jev earns its place)

- **Scenario suite:** save states in `saves/agent/scenarios/` (gitignored), each a battle at the action menu, with a
  tag (type-disadvantage, must-switch, sure-KO, sturdy, priority, status, low-HP). Seed them from playtest saves and with
  `run.py wild SPECIES LEVEL`.
- **Policies:** heuristic, Jev at thresholds 0.3/0.5/0.7, random (floor), and later the escalation model.
- **Metrics per policy:** win rate, turns to win, team HP lost, faints, invalid or failed actuations, latency p50/p95,
  cost per 100 decisions; per-tag agreement with a "reference" pick (the larger model, or hand labels for about 50
  states).
- **Runner:** `scripts/agent/eval.py` loads each state, runs the battle K times per policy (RNG varies with the frame
  timing; record it), and writes a summary table + JSONL. Treat a policy as better only if it wins over enough runs.

## 8. Work breakdown (milestones)

| M | Deliverable | Done when |
|---|---|---|
| **M0** | Commit the prototype on `feat/jev-agent`, PR (CI `no-roms`); key from env | PR merged; `run.py state` / `battle` documented in `EMULATOR.md` |
| **M1** | First live Jev runs: 10 battles with the key, the log reviewed | measured tokens/latency replace the [?] in section 2; any request-shape fixes made |
| **M2** | `eval.py` + about 30 scenario states; heuristic vs Jev table; tune `min_conf` and the option wording | a written result in section 12; go/no-go for Jev on D1/D2 |
| **M3** | Battle completeness: D3 items (bag cursor + pocket layout spike), D4 catching, D5 move learning, D6 evolution, trainer-battle checks (no run option, multi-mon teams), an out-of-PP fallback (Struggle) | a trainer battle and a catch are played from start to finish unattended |
| **M4** | Prompt decisions D8: read the active text printer and the multichoice menu from RAM; Yes/No as `noul` | a scripted Yes/No (e.g. Elm's or Nurse Joy's prompt) is answered from its text |
| **M5** | Playtest integration: `run.py play --until MAP\|FLAG` combines `travel` + battles + prompts; freeze/softlock detector (script ctx stuck, no input effect for N s), automatic screenshot + state dump on anomaly, plus new-string capture for untranslated text | it drives from a mid-game save to the next story flag, or stops with a usable report |
| **M6** | Escalation tier + D9 overworld goal selection | hard-case escalation is measured in M2-style tables; a goal loop runs for 30 minutes |
| **M7** (optional) | D7 double battles | a double trainer battle is completed |

## 9. Spikes (each answers one unknown)

| S | Question | How |
|---|---|---|
| S1 | Real tokens per decision and latency from here | M1 log (`usage`, `ms`) |
| S2 | Is Jev's `confidence` calibrated on this task? | bucket confidence vs correct-against-reference in the M2 data |
| S3 | Bag layout in battle (pocket ids, cursor and scroll addresses) | `watch_read` on the bag menu, as done for the party menu |
| S4 | Where the active message and multichoice entries live for D8 | `break_at AddTextPrinter 0x08002CF4`, `gStringVar*`, the multichoice window task |
| S5 | Ability/item/weather effects worth adding to the damage estimate (Sturdy, Levitate, Intimidate, Choice items) | compare estimate vs actual across the scenario suite; add only what moves the result |
| S6 | Does the third type byte (+0x23) mean anything in CFRU (Forest's Curse/Trick-or-Treat)? | read it across battles |
| S7 | RNG control for repeatable evals | save the state after a fixed frame offset; check `gRngValue` (`0x03005000` **[D]**) |

## 10. Risks and cuts

- **Classifier quality:** it may simply match the heuristic. Then keep the heuristic for D1/D2 and use Jev only for the
  fuzzy surfaces (D4, D5, D8), where hand-written rules are weakest. M2 decides.
- **Third-party service:** a new vendor with unverified calibration. Pin `jev-1.13.0` for benchmarks, keep the heuristic
  as the default fallback, and never make a playtest depend on the network.
- **Data sent:** only game state and option text, no personal data. Still, never send save files or ROM bytes.
- **Hidden information:** the observer reads the foe's moves, which a human can't see. Acceptable for playtests; add a
  `--fair` mode for benchmarks that should mimic a human.
- **CFRU drift:** every address in section 4 is per build; if a ROM change moves code, the callback constants change.
  Add a startup self-check that reads the callbacks at a known state and fails loudly.
- **Menu driving:** cursor positions are checked in RAM after each move; a cursor that doesn't land backs out with B and
  counts as an actuation failure (logged).

## 11. Prototype log (2026-10-23)

- Wild Onix Lv 30 vs Croconaw: three Aqua Jets, back on the overworld. **[V]**
- Voluntary switch, then switching back to a reordered slot, and running away: all landed. **[V]**
- Lv 50 Jolteon: faint replacement and U-turn replacement handled through D2 across 9 decisions. **[V]**
  Bug found and fixed: the party snapshot inside the menu read slots in menu order.
- Heuristic weaknesses seen: it treats U-turn as plain damage (a scenario tag). For replacements it took the first
  switch option, a 759%-of-HP hit; now fixed to pick the switch that takes the least damage.
- Jev endpoint reachable; a 401 falls back cleanly. No live decision yet (M1).

## 12. Results

### M1 (2026-10-23, `jev-1.14.0` via `jev-latest`, beta-26 build, beta-26 save)

- 11 wild battles, 32 live decisions, no hangs, no failed actuations. Pin the model for M2 (`JEV_MODEL`): `jev-latest` resolved to 1.14.0.
- Jev agreed with the heuristic on 14 of 32. Confidence gate (0.5) sent 15 decisions to the heuristic. Most disagreements are
  Jev choosing `run` at 0.34-0.52 where the heuristic attacks; the high-confidence ones (0.58-0.8) were a nearly dead party
  (2% HP) against Lv 45-55 foes, where running is defensible. Not yet judged against a reference: that is M2.
- Fixed: `battle()` decided before the battlers were loaded (a save with an empty party or a slow load gave `#0` level 0 and a
  forced `run`); it now waits.
- Note: `playtest-2026-10-10.sav` has an empty party (a new-game save); use a release save copy for agent runs.
