# Jev game agent (archived, 2026-10-24)

**Status: deprecated, kept as a working reference. Not maintained, not shipped, never part of the ROM or BPS.**

## What it was for
An experiment in letting a cheap decision classifier ("Jev", TypeSafe's `systemone` API) play Pokémon Azoth in the headless emulator,
to reach story points unattended and write titled saves for testing. Everything lives here; the only shared change outside is a bug
fix in `scripts/play.py` (see below), which other tools use.

## Why it is archived
Playing the whole game just to get saves is the wrong tool. The agent covers 4 of the game's 75 story steps (about a dozen calls of
reasoning per step), and still lacks bag items, catching, move learning, evolution and general Yes/No prompts. Preferred replacements:

1. **Forged saves**: warp to a map, set the objective var `0x5120` and its gate vars, give a team, save in-game. Validate by diffing the
   forged state's flags and vars against the real checkpoints kept here (`saves/agent/checkpoints`, gitignored, objectives 1 to 4).
2. **Script-injection text sweep**: run any script from any map and screenshot how its text renders (overflow checks), with no story state.
3. **Human-played saves** in `saves/` for states that must be fully consistent.

## What is worth reusing
| Piece | Where | Notes |
|---|---|---|
| Story spine: var `0x5120` indexes a 75-entry objective table at `0x09FFF468` | `agent/storygraph.py`, `data/agent_story_steps.json` | the most valuable finding; per-step trigger maps and tiles (draft, verify each) |
| Reading flags/vars/messages from a running game | `agent/goalbook.py`, `agent/observe.py` | flags via the game's own `checkflag` (works above `0x900`), hack vars at `0x2039374`, current text at `gStringVar4` `0x02021D18` |
| Writing real `.sav` checkpoints | `agent/savegame.py` | needs a blank 128 KB `.sav` next to the ROM at boot (`RHT_LOAD_SAVE=1`); Save is found by behaviour |
| Cross-map navigation | `agent/navmap.py`, `agent/play_loop.py` | BFS over warps and connections, merged with live RAM warps |
| New game to bedroom | `agent/bootstrap.py` | sets Text Speed Fast, Battle Scene Off |
| Battle decisions | `agent/observe.py`, `agent/options.py`, `agent/decide.py`, `agent/run.py` | RAM snapshot, Gen 6 damage and type maths, legal options, Jev choice with a heuristic fallback |
| Party RAM heal | `agent/cheats.py` | HP, PP, status; the party structs carry no checksum in this hack |
| Goal book and tracking doc | `agent/quest.py`, `data/agent_goals.json`, `docs/AGENT_GOALS.md` | 4 goals, all verified |

Full design, RAM facts and the measured results (latency 200 ms median, about 720 input tokens per battle decision, about $0.00003 each)
are in `docs/JEV_AGENT_SPEC.md`.

## How to run it (if you need it)
```
python3 scripts/hackdb.py build --rom ROM.gba            # the map graph and story steps come from this
RHT_LOAD_SAVE=1 python3 scripts/play.py boot SCRATCH/game.gba   # scratch copy; blank game.sav next to it for new-game saves
python3 deprecated/jev-agent/agent/quest.py --new-game --hackdb build/hackdb-game.sqlite --cheat-heal --sav SCRATCH/game.sav
python3 deprecated/jev-agent/agent/goalbook.py render    # refresh docs/AGENT_GOALS.md
```
`TYPESAFE_API_KEY` is read from the environment only; without it every decision uses the heuristic. Outputs go to `saves/agent/`
(gitignored). Never use a player's `dist/` ROM or save directly: copy them to a scratch folder.

## Fix that stayed outside this folder
`scripts/play.py::path_to` kept the old elevation while crossing an elevation-0 tile; the engine resets it to 0 there
(`ObjectEventUpdateElevation`), so layered maps (New Bark Town, map 1.90) looked unreachable. One line, benefits every tool that plans paths.
