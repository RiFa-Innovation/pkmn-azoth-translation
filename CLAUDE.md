# Instructions for working on this repo (Pokémon Azoth / Mercury EN translation)

Read this first. Deeper background: `PROCESS.md` (pipeline facts, ROM maps; its
"Resume point" sections are historical), `EMULATOR.md` (emulator setup and
tracing), `PLAYTEST.md` (every finding, numbered), `CONTRIBUTING.md`.

## Ground rules

- **Never commit or upload ROMs, saves, save states, emulator backups or `dist/`.**
  The patch is distributed only as a BPS in GitHub Releases. Base ROM: FireRed
  USA v1.0, CRC32 `DD88761C` ("Squirrels" #1636).
- Be explicit in any public text that this is only a **translation done with
  Claude**; the hack, its name and content belong to its original authors.
- The user's `dist/` is theirs: **never overwrite** their `.gba/.sav`. Every
  release gets its own folder `dist/beta-N/` containing
  `Pokemon-Azoth-English-beta-N.bps` and `Pokemon-Azoth-English-beta-N.gba`
  (version in the name, so it can be uploaded to their server as-is); never
  write flat files into `dist/` or touch their `- next.*` files. Package via
  `scripts/dist.py N`.
- Releases, merges and posts are outward-facing: do them when asked. Release
  steps are below. #13 is **parked** until the user reaches it in their
  playthrough.
- Use `/bin/ls` (the shell `ls` is aliased with `--icons`; empty zsh globs also
  abort `&&` chains). Scratch files go in the session scratchpad, not `/tmp`.

## Build and verify (do after every ROM-affecting change)

```
python3 scripts/insert.py     # -> build/Mercury_EN.gba + .bps, prints a report
```

Required report: `missing 0, too_long 0, errors 0`. Then apply the BPS to the
clean ROM and require a byte-identical result:

```
python3 scripts/bps.py apply "roms/Pokemon - FireRed Version (USA, Europe).gba" build/Mercury_EN.bps /tmp/chk.gba
cmp /tmp/chk.gba build/Mercury_EN.gba
```

Re-dump only when the discovery logic changes: `python3 scripts/dump_all.py`
(rewrites `text/zh.json`; review the diff, it is large).

## Where a fix goes (decision table)

| Symptom | Fix |
|---|---|
| Wrong/Chinese string that is in `text/zh.json` | `text/en/strings.json` (TM keyed by the Chinese text; `null` = skip junk) |
| Text too long / clipped / overflows a box | `text/en/width_override.json` (`px`, `dialogue`, `lines` hard cap). `too_long` in the report lists offenders; the original is kept, so fix before shipping |
| String reached only by base+offset (GCC section anchor) | `text/en/manual_strings.json` (in place, asserts the source bytes), `anchored.json`, `data/anchor_refs.json` |
| Text baked into graphics | `gfx/*.json` specs + `scripts/gfx_text.py`, `logo.py` (locate tiles/map with `vram.py`, `gfx.py locate`) |
| Wrong code behaviour / pointer / immediate | `data/code_patches.json` (`patch` with `orig` byte assertion; `vanilla` ranges) |
| NPC parked by an aborted `applymovement` walk / stalled scene staging | a script fix in `insert.py` from the free pool (a gated `ON_RESUME` cleanup that finishes the interrupted stage); read the scene scripts with `scripts/scrdis.py` |
| String exists but was never dumped | `scripts/dump_all.py` (`ref_kind`, `is_mixed`, guards) |

Proofreading edits arrive as CSVs (`scripts/review.py export/import`; token
validation included). Don't hand-wrap dialogue; the inserter wraps.

## Triage workflow (player report -> fix)

1. Reproduce in the emulator from the reporter's `.sav` if given (`RHT_LOAD_SAVE=1`,
   `scripts/play.py`; see `EMULATOR.md`). Capture a screenshot or frame grid.
2. **Pin the root cause with the debugger, don't guess**: find the text address
   (`gfx.py locate`, `watch_read`/`watch_log`, `break_at` on `AddTextPrinter`
   `0x08002CF4`), then ask who references it (`text/zh.json` refs, `ref_kind`).
3. Fix in the narrowest place from the table above; rebuild; re-verify in game.
4. Add a numbered row to `PLAYTEST.md` (symptom, cause, fix, how verified).
5. Branch + PR; CI (`no-roms`) must pass. Close issues manually or with exactly
   one `Fixes #N` per issue: a single commit message with `Fixes #1, #2` only
   closes the first, and a stray "fixes #N" closes issues the user wants kept open.
6. Label `fixed-in-release` **only after** the release exists.

## Findings worth remembering (classes of bug already hit)

- **Pointer trust is the main risk.** A "reference" found by scanning may be an
  instruction, a GCC anchor, data inside an LZ77 blob, an applymovement
  stream or a vanilla data word. Wrongly repointing these gave corrupted
  tiles, NPC movement crashes, achievement crashes and header damage. Current
  guards in `dump_all.py`: header (<0x200), `in_lz77`, applymovement
  (0x4F/0x50) unless `near_code`, vanilla-data-word -> vanilla symbol rule.
  After any change here confirm compressed blobs report 0 changed.
- **Free-space pool:** `0xFF` runs can be live data. `insert.py::referenced_ff`
  excludes referenced FF ranges; don't relocate into them.
- **Mixed strings:** mostly-Latin text with a hanzi (names + one character) is
  below the hanzi ratio; `is_mixed` dumps them from script refs only. Arrow
  glyphs are only trusted from script refs. (#29, 103 strings.)
- **Two font widths:** Latin is 6 px, hanzi 12 px; English re-wraps to the
  window's pixel width. Boxes that cannot scroll need a `lines` cap.
- **Strings reachable only by pointers the dump never walks** (literal-pool
  words, tables `dump_all.py` doesn't scan): found by
  `scripts/find_leftover_zh.py` filtered to aligned refs + sentence
  punctuation, fixed via `text/en/manual_strings.json` (asserts the source
  decode; fits in place or relocates and repoints its `refs`). False positives
  in the same scan: pointer tables - the source bytes contain an `08xxxxxx`
  word. (PLAYTEST 75)
- **Help Tips:** body box is 5 rows, wraps at ~150 px; each page is its own
  table entry (0x1E467C4-0x1E468A0); `{F8:xx}` button icons count 12-24 px
  (SELECT ~20-24). Cap pages at px 148 / 5 lines. (#31)
- **CFRU extended object graphics** table at `0x08961600`: entry 0 is the 32x32
  player, rival is entry 72 (sheet `0x09F54D34`, 9x512 B, palette `0x09F55F34`).
  Using vanilla sheets with the hack's templates garbles sprites. (#30)
- **Ability pop-up possessive** is a code-appended `的` (`03 0B FF`) at
  `0x1CEAAE4`; patched via `code_patches.json`. (#6)
- **Script injection** for tests: write a script pointer into the global script
  context (`0x03000EB0`: +8 ptr, +0 = 0, +1 = 1, `0x03000EA8` = 0); call
  routines via `gMain.callback2` (`0x030030F4`) with a Thumb stub assembled
  `arm-none-eabi-as -mcpu=arm7tdmi` (not Thumb-2).
- **Freeze on talking to an NPC = placeholder script.** The hack's map generator
  left the cartridge header as the script of event slots instead of NULL:
  **981 unique addresses** (652 object events `0x08000000`, 632 `0x08000001`,
  20 coord events, 4 BG events) spread over **528 maps**. FireRed runs the ROM
  header as bytecode and the engine chases the garbage pointers in it. Signature:
  script ctx at `0x03000EB0` stuck in mode 2 with scriptPtr `0x08000009`.
  `insert.py::null_placeholder_scripts` zeroes any script pointer below
  `0x08000100` for object, coord and BG events (592 sites in beta-7, which
  matched `== 0x08000000` only; 981 now). The hack moved `gMapGroups` to
  `0xB3B100` (vanilla table is 0xFF). Always test a suspected freeze against
  `roms/Pokemon Mercury 1.3.3 (patched).gba` first: if it hangs there too it is
  an original-hack bug. (#17, PLAYTEST 57, 74)
- **"Only works on emulator X" reports are usually invalid accesses.** The
  placeholder above is a clean example: the bug is in the hack, but what
  *happens* while garbage runs as script bytecode depends on how the emulator
  answers reads of the BIOS region and of open bus (mGBA's maintainer: "invalid
  accesses behave a certain way ... Pokémon ROM hacks that only work in VBA").
  A NULL script pointer is *fine* - FireRed understands NULL; a pointer into the
  header is not. Before chasing an emulator, check for invalid pointers in the
  data the path touches. (#64, PLAYTEST 74)
- **Softlock in a one-tile corridor = a scene walk that aborted.** An
  `applymovement` walk *ends* when a step is blocked (e.g. by the following
  Pokémon in a narrow corridor), so an escort NPC can park on the only tile and
  box the player in. Sprout Tower's top floor did exactly that (#37, PLAYTEST
  60) — and because the interrupted chain left the story stage on the value its
  coord event tests, stepping south also restarted the whole chain, fights
  included. Repair such a save by *finishing* the interrupted stage (the hack's
  own cleanup: hide the scene objects, advance the stage), never by replaying
  it: `ON_RESUME` (map scripts tag 5) runs on every map load and field resume,
  so repointing it to a gated cleanup script repairs stuck saves in place.
  Note object templates live in `SaveBlock1` (copied from the map header on map
  load, `script` refreshed separately), so a parked NPC is *in the save* — a
  map-header edit alone does not repair existing saves.
- **UI labels can be invisible to every scan.** A label the code loads as
  `ldr rX, =<block>` + `adds rX, #imm` owns no pointer, so `find_leftover_zh`
  (pointer-based) and the dump never list it. `data/hack_code.json` marks such
  literals (`"anchor": "imm"`, with the exact `offs` the code uses) — the quest
  board's `已完成`/`未完成`/`委托数量`/`委托列表` sit at 0xE39F8C..0xE39FF5 that
  way. Fix them **in place** through `text/en/manual_strings.json` (byte-asserted
  `zh` + `cap`, the path `进行中` -> `Active` uses); never relocate the block —
  the same literal is used with other offsets, including reads of data fields, so
  moving it breaks them. (#41, PLAYTEST 65)
- **A scene NPC that comes back after a map reload has no flag.** Object template
  flagId 0 spawns the object on every map load, so a cleanup's `removeobject`
  only lasts the session ("the old man walks up and down the stairs again").
  Give it a flag the hack's own cleanups set — Sprout Tower's elder uses 0x178b,
  set by the same script that advances the story stage, so saves that already
  finished the scene have it too. (#37, PLAYTEST 64)
- **Fix a shared movement blob by repointing its operands, not the blob.** The
  Sprout Tower cast's leave walks shared three movement blobs with six
  `applymovement` sites in other scripts, so editing the blobs (beta-10, in
  `code_patches.json`) had to be reverted in beta-11. Pointing the six *operand
  slots* in that scene's own scripts at one pooled "stay put" movement (`0x62`
  idles + `0xFE`) gives the same effect and touches no shared byte. (#37,
  PLAYTEST 62, 64)
- Save states break between patch versions; in-game saves carry over.

## Replaying the new-game path (verified 2026-10-12, current build)

Boot with no `.sav` (omit `RHT_LOAD_SAVE`). Press A through the naming
screen (Start confirms), the disclaimer pages and Settings (**B** closes
Settings, not A). Then: bedroom stairs (walk onto the warp tile, then press
toward it), Mom's scene in the house (A until the script context mode at
`0x03000EB1` is 0), door mat at the bottom (press Down), New Bark Town (3.66).
Lyra's scene is **in her house (43.5)**: enter through its door (script
`warp 43 5 0 0 0` works) and step left of the door, which fires the coord
trigger. Then the lab (43.6): walking up from the door triggers Elm's scene;
afterwards stand at (7,5) in the lab, face up and press A for the starter
screen (map 43.7). Use `press_buttons frames=2 release_frames=10` taps and
`snap` states at each step (`saves/states/ng-*.ss`, gitignored). All three
starters, the nickname screen and Elm's farewell were verified here.

## Release steps (only when asked)

1. Merge the PR (CI green). `git checkout main && git pull`.
2. `python3 scripts/dist.py N` - builds, verifies the BPS byte-identically,
   and packages `dist/beta-N/` (versioned `.bps`, `.gba`, `.sav`; `--save PATH`
   for a different save, `--no-build` when already built). It prints the
   SHA-1s for the notes.
3. Notes: copy the previous release's structure (`gh release view beta-N-1`):
   bug-report link, patch/hash table (base CRC32+SHA-1, patch SHA-1, ROM SHA-1),
   "New in beta N" with the detailed fix list, known issues. Use the
   `pkmn-azoth-translation` repo URLs.
4. `gh release create beta-N dist/beta-N/Pokemon-Azoth-English-beta-N.bps --target main --title "Beta N: ..." --notes-file ...`
5. File/close tracking issues for fixes that had none, add `fixed-in-release`.

## Current state (2026-10-12, after beta-9)

Open: #11 (~10 mid-block Chinese fragments), #24 (human proofreading pass,
ongoing). Beta 7-9 closed the freeze on talking to placeholder-script NPCs
(#17), the Sprout Tower top-floor softlock (#37; the fix re-places the two exit
sages on every map load, so stuck saves repair themselves), the Ilex shrine
crash (#19), the achievements fit (#2), Ilex/route-sign/Help-Tips Chinese and the
double-battle stray text (#13, parked). Not yet checked in game: the new
BracerPoints/price/¥ lines and the Wobbuffet line from beta-6.

Ideas for next sessions: play further than the recorded progress and log
findings as `PLAYTEST.md` rows 57+; sweep remaining Chinese by grepping a fresh
dump of the built ROM for hanzi; check other fixed-width UI lists (menus,
summary screens, Pokédex entries) for overflow the way Help Tips was swept
(capture every entry, view the grid); keep the Reddit/Discord announcement
drafts up to date (the user posts them).
