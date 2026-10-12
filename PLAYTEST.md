# Playtest log

Playing the English build in a headless emulator, screen by screen, fixing what
is wrong. This file is the hand-off: a new session should be able to continue
from here with nothing else. Findings are numbered in the table at the bottom.
Status: **open** = to fix, **fixed** = fixed (commit noted where useful),
**ok** = checked, fine.

## Current status (2026-10-10)

All pointer-reachable text is translated: `insert.py` → missing 0 / errors 0 /
too_long 0; BPS round-trips byte-exact. Playable build at
`dist/Pokemon Mercury (English).gba` (+ `.bps`, applies to clean FireRed US 1.0,
CRC `0xDD88761C`). Exactly two Chinese remnants remain, both fully characterized:

- **Finding 17** — ability pop-up `Sentret的` (shows in every battle when an
  ability activates). Root cause: CFRU's `PrintBattlerOnAbilityPopUp`
  (`ability_battle_effects.c`) hardcodes the possessive as `CHAR_SGL_QUOT_RIGHT`
  + `0xE7` (`'s`); the hack rewrote it to `的` = `0x03 0x0B`. **Fix = patch
  `0x03 0x0B` → `0xB4 0xE7`** in the compiled function. Remaining step: locate
  that function's ROM offset — whole-ROM byte scans (`movs#3;strb`,
  `strh`-of-`0x0B03`, both orders) found no match, so use the mGBA `-g` GDB stub
  (break `AddTextPrinter` 0x08002CF4, read LR) — but first `brew install
  arm-none-eabi-gdb` (no GDB client is currently installed).
- **Finding 34** — PokéGear charm-screen header `切换挂件 选择 应用`. Baked into
  the tileset (0 byte matches as text); fix via `scripts/vram.py` +
  `scripts/gfx_text.py`, like the cut-ins (finding 31).

## How to continue (read all of this first)

### 0. Ground rules
- Repo: `/Users/river/Projects/rht`. Source ROMs in `roms/` (gitignored):
  `Pokemon Mercury 1.3.3 (patched).gba` (Chinese hack, the source) and
  `Pokemon - FireRed Version (USA, Europe).gba` (clean base for the patch).
- **After every meaningful change**: rebuild, verify the patch, then commit.
  ```
  python3 scripts/insert.py 2>&1 | tail -1      # must say 'missing': 0, 'too_long': 0, 'errors': 0
  python3 - <<'PY'
  import sys,hashlib; sys.path.insert(0,'scripts'); import bps
  base=open('roms/Pokemon - FireRed Version (USA, Europe).gba','rb').read()
  out=bps.apply(base,open('build/Mercury_EN.bps','rb').read())
  print('match' if out==open('build/Mercury_EN.gba','rb').read() else 'MISMATCH', hashlib.sha1(out).hexdigest()[:12])
  PY
  ```
  A full rebuild takes ~1 minute. Output: `build/Mercury_EN.gba` + `.bps`.
- Commit messages end with the attribution line given by the harness
  (`Co-Authored-By: ...`). Log every finding in the table below (state, what,
  status) in the same commit as its fix.
- `.venv/bin/python` has capstone (needed for `scripts/hackmap.py` and any
  disassembly); plain `python3` is enough for everything else.
- `arm-none-eabi-as/objcopy/nm` are installed (Homebrew) for hand-written Thumb
  (see `data/naming_dispatch.s`).

### 1. Emulator driver (`scripts/play.py`)
- `python3 scripts/play.py boot [ROM]` starts mgba-headless (default
  `build/Mercury_EN.gba`) with the Lua bridge on 127.0.0.1:8765. **Re-boot after
  every rebuild**, otherwise you test the old ROM. `play.py stop` kills it.
- `python3 scripts/play.py load NAME` loads `saves/states/NAME.ss` and prints
  the map/position/ASCII collision view.
- `python3 scripts/play.py go "SEQ" [NAME]`: tokens `A B Start Select L R`
  (press), `Up/Down/Left/Right` (menu tap), `U3 D1 L2 R4` (walk N tiles,
  closed loop on the live player object), `tU tD tL tR` (turn), `w60` (wait,
  no screenshot), `A*5` (repeat). Every non-wait token screenshots; the grid is
  `saves/shots/last.png`, the last frame `saves/shots/now.png` (480x320). With
  NAME it saves state `saves/states/NAME.ss` (+ `.png`). `go "w5"` does NOT
  refresh now.png: use `play.py shot` or a `tU` token.
- In Python (`sys.path.insert(0,'scripts'); import play; from emu import Emu`):
  `play.pos(e)` -> (x, y, mapGroup, mapNum) from the live player object;
  `play.goto(e, x, y)` BFS pathing (collision bits, elevation, one-way ledges,
  learns blocked tiles, flees wild battles); `play.travel(e, "L3 U2")`;
  `play.in_battle(e)`; `play.flee(e)`; `play.path_to(e,x,y)`;
  `play.grid(e)`; `play.behaviors(e)`. Leaving a map: goto a walkable tile on
  the edge (scan `play.grid`) then `travel` one more step; warps are listed by
  `play.py where` (stand on/in front of the door, `tU`/`tD`, wait ~80 frames).
- Map connections: read gMapHeader (0x02036DFC) +0xC (see the snippets used
  for Cherrygrove/Route 30 in git history of this file's commits).
- Emu RPC extras: `e.call('read_registers')` (pc, lr, cpsr: cpsr&0x1f == 0x1b
  means the CPU crashed into Undefined mode), `e.read(addr,n)`.
- Useful RAM: gMain 0x030030F0 (callback2 at +4, state at +0x438),
  sGlobalScriptContext 0x03000EB0 (+8 script pointer), sTextPrinters 0x02020034
  (0x24 each, +0 currentChar), gStringVar4 0x02021D18, gSpecialVar_Result
  0x020370D0, sNamingScreen 0x0203998C, gObjectEvents 0x02036E38, VMap
  0x03005040. CB2_Overworld = 0x080565B5.
- Pitfalls: graphics loaded when a map loads are cached in RAM, so a save state
  taken *after* the map load still shows the old picture after a rebuild (test
  from a state before the map/scene loads). A presses during dialogue land in
  text-entry screens (clear with B*8). The follower Pokémon can block a step
  (the pathfinder learns and re-routes). Screens in states saved before a
  rebuild are fine for text tests (text is read from ROM when printed).

### 2. Where things come from, and how to fix each kind of problem
- **Chinese dialogue/menu text**: dumped by `scripts/dump_all.py` (pointer
  scan + code map) into `text/zh.json`; English is looked up by the exact
  Chinese string in `text/en/strings.json` (overrides) then
  `text/en/strings-vanilla.json`. `null` = not text, skip. Add or override a
  line by inserting `"<zh>": "<en>",` after the `"你的选择？"` line in
  strings.json (keep one entry per line; never re-dump the whole file with
  json.dump, it reformats 27k lines). Find the Chinese for something on screen
  with `grep` on the English or by decoding the ROM bytes
  (`mercury_text.decode`, `char_to_code`).
- **Text not dumped**: check `dump_all.is_textlike/short_line/is_single` and
  `ref_kind` (why the pointer is untrusted). For one-off strings use
  `text/en/manual_strings.json` (in place, `cap` bytes; `refs` + `ref_en` to
  repoint specific pointers). Text reached by base+offset code:
  `scripts/anchored.py` (`text/zh_anchored.json`, `text/en/anchored.json`).
  Text a live FireRed routine prints that the hack half-overwrote: restore
  FireRed's bytes via a `vanilla` range in `data/code_patches.json`.
- **Overflow / wrapping**: width comes from the Chinese source unless
  overridden. Per string: `text/en/width_override.json` `{addr: {px, dialogue}}`.
  Per class (in `insert.py`): DIALOGUE_PX 198, ITEM_DESC_PX 176 (bag, 3 lines),
  MOVE_DESC_PX 112 (summary/learn box, 4 lines), ability descriptions 134px
  2 lines (width_override entries). Measure with
  `sum(widths[c] for c in mt.encode_en(s)[:-1])`, widths =
  `rom[mt.WIDTHS_OFF:+256]`. A one-line text keeps leading/trailing spaces.
- **Text baked into pictures**:
  - BG tileset+tilemap (LZ77, pointer-referenced): `gfx/<name>.json` handled by
    `scripts/gfx_text.py` (erase rect + colours, text in `font6` or
    `"font": "normal"` = FireRed's dialogue font). Find the source with
    `python3 scripts/vram.py DIR` (dump while it is on screen) then
    `python3 scripts/gfx.py locate DIR <bg>`. Cut-in pictures: table
    0x1DE4F28, 12 bytes per entry (tiles, map, palette), bank 13 (`gfx/cutin_*`).
  - Screens built as overworld maps (starter screen): `gfx/map_*.json` via
    `scripts/maptext.py` (new tiles appended to the secondary tileset, unused
    metatile slots reused, blockdata repointed).
  - Text-only sprites (sound effects, picture table 0x1DE5A08): `gfx/spr_*.json`
    via `scripts/sprtext.py`.
  - Type icons / TYPE-POWER labels: `scripts/typeicons.py` (sheet 0xEFD4C0).
  - Title logo `scripts/logo.py`; name-entry buttons `gfx/nameentry.json`.
  - When `gfx.locate` finds nothing: the picture may be drawn at a pixel
    offset (search the structure with numpy as done for the type icons), be a
    sprite (`state.json` sprites list, `obj.png`), or be in a map tileset.
- **Code**: whole-ROM code map `data/hack_code.json` (`.venv/bin/python
  scripts/hackmap.py` rebuilds it, ~10 s); FireRed layout/symbols
  `data/fr_map.json` (`python3 scripts/frmap.py 0xADDR` describes an address).
  Binary patches: `data/code_patches.json` (`patch` with asserted orig bytes,
  `vanilla` ranges, `replace_all` find/with/count). The name-entry dispatcher
  is `data/naming_dispatch.s` -> `NAMING_DISPATCH` in insert.py.
- **Dialogue name box** (speaker tab): scripts set VAR 0x8000-0x8003 (x, y,
  width, height in tiles) then `callasm 0x08FB0001`; width is patched 6 -> 8
  tiles (64px). Speaker names must stay <= ~65px.
- **Delegating bulk rewrites** (descriptions etc.): write
  `scratchpad/<task>/todo.json` ([{zh, current_en}]), a `check.py` that wraps
  each result and counts lines (copy `scratchpad/abil/check.py` style; it must
  run from the repo root), launch a sonnet agent to write `result.json`
  {zh: en} until the checker says 0 bad, spot-check a sample, merge into
  strings.json by replacing/adding single lines (see git history of
  "item descriptions shortened").

### 3. Story position and what to do next
- Last save states: `42-elmcall` (Route 30, Elm just called: go back to the
  lab), `44-cutin` (rival cut-in at the Cherrygrove east edge),
  `43-rival`/`45-rivalend` (rival battle, won; Chikorita is offered Leafage and
  the forget-a-move screen is open in `45-rivalend`).
- Next: finish the move-learn prompt (decline or forget Tail Whip), walk
  Route 29 east to New Bark (map 3.66), into Elm's lab (door (12,7)); the story
  continues (police, Mystery Egg, Togepi...). Then Route 31/32, Violet City
  (Sprout Tower, Falkner), Union Cave, Azalea. Test along the way: every new
  NPC, shop (Poké Mart buy/sell screens), Pokémon Center healing + PC boxes,
  trainer battles (intro/defeat texts, money message), catching (bag in
  battle, Poké Ball messages, Pokédex registration screen, nickname prompt),
  Pokégear (map, phone, radio), save screen.
- Every screen: read every line; check for Chinese, overflow (text past a box
  edge or cut), wrong names (FireRed/Kanto names where Johto is meant:
  strings-vanilla.json was matched by address and is sometimes wrong — always
  check the Chinese meaning), broken glyphs (bytes that are pointers or data =
  corruption: investigate with the build/source byte diff).

### 4. Open work items
- Ability pop-up "Sentret的" (finding 17) — root-caused to CFRU's
  `PrintBattlerOnAbilityPopUp`; patch its hardcoded `的` (0x03 0x0B) to `'s`
  (0xB4 0xE7). Locate the compiled function via the mGBA `-g` GDB stub
  (break `AddTextPrinter` 0x08002CF4 and read LR) once a GDB client is installed.
- PokéGear charm-screen header 切换挂件 (finding 34) — tileset graphics; use
  `scripts/vram.py` + `scripts/gfx_text.py`.

## States

| state | where |
|---|---|
| 00-title | title screen, fresh boot |
| 01-named | after naming the player MIKE (FireRed name screen) |
| 02-intro | disclaimer pages done, before settings/Oak |
| 06-bedroom | after the intro, in the bedroom |
| 08-mom | downstairs after Mom gives Pokégear/Bag/Card/Notebook |
| 12-outlab | outside the lab, New Bark (Elm out on fieldwork) |
| 14-lyra | upstairs room east of the lab (stairs right of the lab), after meeting Lyra |
| 16-machine | lab, Elm back; starter machine is up-right of the player |
| 17-starter | starter-choice screen (map 43.7) |
| 19-afterstarter | got Chikorita, Elm sends you to Mr. Pokémon |
| 24-route29 | Route 29 entrance, tall grass to the south-west |
| 25-battle | wild Sentret (Frisk) battle start |
| 26-fight | battle, action menu |
| 28-afterbattle | Route 29 after the first wild battle |
| 30-bag | bag open on Route 29 |
| 31-cherrygrove | Cherrygrove beach, just arrived from Route 29 |
| 32-pc | Cherrygrove Pokémon Center, facing the birthday-month girl |
| 37-route30 | Route 30 entrance from Cherrygrove |
| 38-mrpokemon | inside Mr. Pokémon's house |
| 40-oak | after Oak gives the Pokédex |
| 42-elmcall | Route 30 after Elm's call (go back to the lab) |
| 44-cutin | rival cut-in on the Cherrygrove/Route 29 border |
| 43-rival | rival battle, start |
| 45-rivalend | rival beaten; move-learn screen (Leafage) open |
| 23-momtalk | outside home after Mom's Running Shoes |
| 21-outlab2 | just outside the lab after getting the starter (Elm scene loads next step) |

## Findings

| # | where | what | status |
|---|---|---|---|
| 1 | name entry | hack's pinyin keyboard; letters never reached the name -> random default name | fixed ec684e3 (FireRed screen) |
| 2 | battle | "Wild" glued to the Pokémon name | fixed c132334 (verify in battle) |
| 3 | text input title | "Your Name?" for every prompt (vanilla mismatch) | fixed c132334 / ec684e3 |
| 4 | Oak intro | every text box blank / black (text colour bytes at 0x7AAB7B overwritten by an anchored string whose head was a colour array) | fixed (anchored dump starts at the inner target) |
| 5 | radio (Tue) | day-of-week song table at 0x8EA69E (ldrh [r0, r3]) taken for text and overwritten; same for data before "Exit settings" (0xE3771C) | fixed (hackmap: literal used as index register = table) |
| 6 | start menu | trainer-card icon has no label (player-name code prints blank; also in the Chinese ROM) | fixed ("Trainer Card") |
| 7 | Mom | "Obtained the PokéGear!" vs "Pokégear" elsewhere | fixed (item name 精灵齿轮 -> "Pokégear" in items/items2 tables + glossary/names) |
| 8 | intro video page | Bilibili-style header + Evangelion title card (Japanese kanji) | ok (easter egg) |
| 9 | Lyra intro | character card graphic still Chinese: 琴音 / CV.千本木彩花 | fixed (cut-in 11: Lyra / CV. Ayaka Senbongi) |
| 10 | starter choice | prompt 要选择哪一只精灵/作为你的搭档？ baked into the screen's map tileset | fixed (scripts/maptext.py, gfx/map_starter.json) |
| 11 | leaving the lab | "咕咚!!" is a sound-effect picture (64x64 sprite, entry 13 of the picture table 0x1DE5A08) | fixed ("Thud!", scripts/sprtext.py) |
| 12 | New Bark triggers | "喂，{FD:01}！" and 16 other one-hanzi lines never dumped (filter needed 2 hanzi) | fixed (dump accepts short script lines) |
| 13 | lab aide | item pop-up: "It restores the HP of one Pokémon" runs into the arrow | ok (item descriptions wrap at 176px since finding 26; Potion now 3 lines ≤176px) |
| 14 | Mom (Running Shoes) | "Oh, right" printed as "Oh ▯ht": a false pointer (text bytes 0E 9E 08 inside 红色的火球 at 0xABEAE0) was repointed into recycled space holding this line. 284 such refs | fixed (dump drops refs inside script text; build reserves every repointed word) |
| 15 | battle move info | type icons 一般/火/… (hack's menu-info sheet 0xEFD4C0) | fixed (3-letter codes NOR/FIR/…, TYPE/POWER/ACCURACY/PP/EFFECT labels from FireRed; scripts/typeicons.py) |
| 16 | battle strings | live FireRed battle strings the hack half-overwrote ('…与对手{broken}换了特性！ with its opponent!', 的/是/果 suffixes) | fixed (restored FireRed English for 8 symbols) |
| 17 | ability pop-up | "Sentret的" (Chinese possessive). Not sText_ApostropheS (restored to "'s" at 0x3FE88F, unchanged on screen — the pop-up ignores it), not in RAM buffers, no pointer to a 的 string; the pop-up draws its own 的 as text into the sprite | open (CFRU source: PrintBattlerOnAbilityPopUp in ability_battle_effects.c:2816 hardcodes the possessive as CHAR_SGL_QUOT_RIGHT + 0xE7, i.e. 's; the hack rewrote it to 的 = 0x03 0x0B. Fix = locate the compiled fn in the ROM (whole-ROM byte scans of movs#3/strb or strh-of-0x0B03 find no match, so it uses a ldr-literal or different regs) and patch 0x03 0x0B -> 0xB4 0xE7) |
| 18 | wild battle | "Wild Sentret used Growl!" spacing correct | ok |
| 19 | start-menu hint | "Go through Yoshino City to Mr." (Japanese name, cut) | fixed ("Find Mr. Pokémon past Cherrygrove.", width override) |
| 20 | party menu | "What will you do with t…" overflows | fixed ("Do what with it?") |
| 21 | summary info | "Relaxed (+Defense -Sp…" + " nature." overflow | fixed (natures abbreviated +Def -Spe; templates drop " nature.") |
| 22 | summary skills | page header "✚换页" (lone struct-field string) | fixed ("Page") |
| 23 | summary skills | ability descriptions cut at ~134px | fixed (2-line wrap at 134px; 103 long ones shortened) |
| 24 | battle | "Chikorita gained  17 Exp. Points!" double space | ok (re-checked: single space "gained 17 Exp. Points!"; the FE newline renders as a space in the battle box) |
| 25 | bag | pocket tabs cut: Training It…, Battle Item…, Evolution I…, Special Gem…, Materials &… | fixed (Training/Battle/Evolution/Gems/Materials) |
| 26 | bag | item descriptions run into the arrow / past 3 lines (box ~176px, starts after the icon) | fixed (wrap at 176px; 129 long ones shortened; 0 over 3 lines) |
| 27 | Cherrygrove PC girl | birthday-month prompt reset the game: the hack calls DoNamingScreen with template 0 (and at hook+2) and writes hack-only fields; FireRed's screen can't serve it | fixed (dispatcher data/naming_dispatch.s: intro + templates 1-4 -> FireRed screen, template 0/5+ and hook+2 callers -> hack screen, which keeps its English buttons and ABC default) |
| 28 | dump | 297 'strings' that are Thumb code (function pointers decoded as text) | fixed (dump skips targets inside code) |
| 29 | Cherrygrove PC girl | birthday month: typing "12" rejected, prompt reopens | ok (not a bug — verified "12" is accepted: month "12" -> "So which day exactly?", day "15" -> VAR_RESULT 15. The earlier "rejection" was a test-navigation artifact: `go` D4/R1 tokens use overworld walk(), which in a menu presses the wrong count and types non-digit chars) |
| 30 | dialogue name box | "Mr. Pokém" cut: the box is 6 tiles (fits 4 hanzi) | fixed (all 84 box setups widened to 8 tiles; names trimmed of centring spaces; 5 long ones shortened) |
| 31 | rival / Lyra cut-ins | captions baked into the cut-in pictures (table 0x1DE4F28): 不明白什么意思？…, 我的名字是？？？, 要成为世界最强…, 我对你……不！, 能遇见你，真是太好了！, B返回 | fixed (gfx/cutin_*.json, FireRed font) |
| 32 | rival battle | "Passerby wants to battle!" for the unnamed rival (路过的少年) | ok |
| 33 | Pokédex (start menu) | UI labels "still Chinese": 图鉴/城都/发现数/捕捉数/菜单/搜索 | ok (false positive — all translated in the build: 图鉴->"Pokédex" 0x41B6E3, 发现数：->"Seen:" 0xEB3225, 收服数：->"Owned:" 0xEB323D, 搜索->"Search" 0x45942C, 关都/全国->"Kanto"/"National". The Chinese seen earlier was a stale cached screen from a pre-rebuild save state) |
| 34 | PokéGear charm screen | header L R 切换挂件 选择 应用 still Chinese; the bottom hint 选择/切换/应用 is already English | open (graphics — 切换挂件 is not in the ROM as text (0 byte matches); it's baked into the tileset, needs gfx_text.py like the cut-ins) |
| 35 | Help Tips → Achievements | unlocked descriptions ran past the bottom of their 5-line box into the footer (garbage piles up while scrolling; writes past the window buffer → crash). 25/38 English descriptions wrapped to 6–10 lines at 156 px. Long names also clip (issue #2, cosmetic) | fixed (issue #1: 25 descriptions tightened to ≤5 lines; width_override `lines: 5` for all 38, insert.py reports too_long instead of overflowing; verified with a test ROM forcing all 38 unlocked) |
| 36 | Pokémon Center dressing room (player report, issue #8) | black screen / crash after "This way, please!": the dressing-room code loads one base (0x08E37264, string 已获得) and passes base+0x20 / base+0x30 to InitBgsFromTemplates / InitWindows (GCC section anchor). insert.py repointed the base to the English string, so BG/window templates were read from text. 54 such anchor refs found (incl. the battle move-type label, issue #4) | fixed (scripts/anchor_refs.py -> data/anchor_refs.json; insert.py never repoints anchors: text goes in place or stays Chinese, reported as anchor_kept; 已获得/已完成 shortened to Owned/Done to fit in place). Verified: dressing room opens (gMain.callback2 0x08DF1921, same as the Chinese ROM); bisected to the single word at 0xDF1D70 |
| 37 | insert.py free space | 0xFF runs the hack reads as data were handed out as free space: end-marker entry of a 50-byte table at 0x76AA08 (0x76AF1C) and a pointer table at 0xC2AEA0 used by code at 0x73Dxxx | fixed (referenced_ff(): runs targeted by code literals are kept whole, table-pointer targets keep a 16+256 byte window; costs ~81 KB of 746 KB slack) |
| 38 | Route 29 sign (and 6 more) | still Chinese: 这里是29号道路 / 吉野市→若叶镇. FireRed arrow glyphs 0x79-0x7C decoded as katakana (ルレロワ), so dump_all rejected every sign with an arrow as not text-like | fixed (issue #14: mercury_text decodes/encodes ↑↓←→; dump accepts arrow strings only from script refs (data decodes to them too); +7 signs translated. Verified with the dist/ save: sign reads "Route 29 / Cherrygrove City → New Bark Town") |
