# Save forging: what a forged save needs, measured (2026-10-24)

Goal: titled saves at story points for testing, without playing the whole game. `scripts/forge.py` dumps the complete story state of a
running game, diffs two dumps, and applies a story delta (flags, script-referenced vars, a warp) through the game's own script commands.

```
python3 scripts/forge.py dump OUT.json                  # idle overworld; ~3 min (6,144 flags asked of checkpoint)
python3 scripts/forge.py diff A.json B.json
python3 scripts/forge.py forge A.json B.json HACKDB     # make the running game (a real save of A) look like B
```

## What was measured
Two real checkpoints written by the (archived) Jev agent while playing the translation from a new game: **A** = in Elm's lab right after the
starter (objective 3), **B** = on Route 30 after Mr. Pokemon's house (objective 4). Both loaded from their `.sav` on the current build.

| Question | Result |
|---|---|
| How much changes between consecutive real story points? | 24 flags set, 4 cleared, **57 vars**, a new map and position, party unchanged |
| How many of those vars are story? | **4** (`0x5103`, `0x5105`, `0x5120`, `0x501f`): the only ones any script reads or writes. The other 53 are system state (position caches, timers, RNG), not story |
| Does applying "all flag changes + script-referenced vars + warp" to A reproduce B? | **Yes for everything a script can observe**: 0 flag differences, same map, position and party, the 4 story vars match. 36 non-script vars still differ (system noise) |
| Can the delta be predicted without a real save? | **Partly.** Static reachability from the three trigger scripts (New Bark exit, Mr. Pokemon's house, Route 30) predicted the 3 story vars exactly (`5103=1`, `5105=2`, `5120=4`) but also 8 var writes that did not happen (untaken branches), and only **3 of the 24 flags** (7 predicted, 21 real flags missed: NPC visibility flags, system flags set by map-load scripts and code) |

## What it means
- **Applying** a known delta is solved and exact for scripted state. Forging a save between two real saves is cheap and safe.
- **Inventing** a delta for a step nobody has played is not: the flags cannot be derived from scripts alone, and a blind forge (just
  `0x5120 = N` plus a warp) would miss dozens of flags (NPCs that should be gone or present, one-time scenes that would replay).
- So forged saves need a **real reference save near the target**. Sources, best first: the user's own playtest saves (already consistent),
  checkpoints from a real playthrough (the agent or a person), then interpolation by diffing two real saves and applying the delta to a
  third that sits between them. Each new real save adds a delta to a library; forging then costs minutes.
- Not covered: items and money (SaveBlock1, encrypted), and whether the 36 noise vars matter for gameplay (nothing observed breaking in
  the dump; a longer play-from-forged test is the open check).

## Status
Tool and measurement only; no PR depends on it. The dumps are not committed (they come from checkpoints of a play session, and saves/states
stay out of the repo).
