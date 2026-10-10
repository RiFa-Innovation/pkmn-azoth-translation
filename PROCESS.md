# Mercury (水银) 1.3.3 — translation process state

> Updated 2026-10-10 (checkpoint 16). Resume from here. Everything below is
> ground truth from the repo; see git log for checkpoints.

## Goal

Translate the Chinese Fire Red hack **Pokémon Mercury 1.3.3** to English.
No English patch exists anywhere (checked 2026-10-09), so this is from scratch.

**Current phase: translating text.** The charmap, dump, insertion and patch
pipeline are all done and working end to end.

## Pipeline (run from repo root)

```
python3 scripts/dump_all.py          # ROM -> text/zh.json   (needs numpy)
python3 scripts/translate_tables.py  # zh.json + data/ref + manual -> text/en/tables/*.json
python3 scripts/insert.py            # -> build/Mercury_EN.gba + build/Mercury_EN.bps
```

`build/Mercury_EN.bps` applies to **clean Fire Red US 1.0** (CRC `0xDD88761C`).

## Files

| Path | What |
|------|------|
| `scripts/mercury_text.py` | **Codec**: decode hack text, encode/wrap English |
| `scripts/dump_all.py` | Pointer scan + fixed tables → `text/zh.json` |
| `scripts/translate_tables.py` | Name tables via veekun (zh→en) + manual + abbrev |
| `scripts/insert.py` | In-place / relocate + repoint, builds ROM + BPS |
| `scripts/bps.py` | BPS create/apply |
| `text/zh.json` | Dump: `tables` (fixed-stride) + `strings` (addr → zh, cap, refs) |
| `text/en/strings*.json` | **Translation memory** `{chinese: english}` for strings |
| `text/en/tables_manual/<table>.json` | Hand translations `{index: english}` |
| `text/en/abbrev.json` | Long official name → field-length abbreviation |
| `data/ref/*.csv` | veekun names (lang 9 en, 12 zh-Hans, 4 zh-Hant) |
| older: `dump_text.py`, `find_relocated.py`, `match_font.py`, `charmap.json` | superseded (kept for history) |

## Established facts (do not re-derive)

1. **Encoding (definitive, from disassembly of the CJK glyph hook at
   `0x0820F658`)**: lead byte `0x01–0x1E` except `0x06`/`0x1B` → page
   (`L-1` ≤5, `L-2` ≤0x1A, `L-3` above); trail `0x00–0xF6`;
   index = page·247 + trail = position in the packed list of all 6,763 GB2312
   hanzi (GB2312 cell rank = index, +5 past level 1 at 3755). No charmap file
   needed. CJK fonts: `0x7D0000` (normal) / `0x840000` (small), 64 B/glyph,
   half-row compressed with byte pairs swapped.
2. Other bytes = vanilla FR charset, except redrawn punctuation `0x36–0x3E`:
   ；。—～、，！？：
3. **Widths**: hack made Latin monospace **6 px** (i/l narrower), hanzi 12 px.
   Dialogue lines ≤ ~204 px → English re-wrapped automatically (`\n`, then
   `{FA}` scroll for lines 3+; `{FB}` paragraphs preserved).
4. English must not use bytes `0x01–0x1E` (read as hanzi leads) except é/É.
5. Text is raw (not LZ77). Pointer refs trusted only if aligned in a pointer
   structure, or after `0F 00` (loadpointer), `67` (message), or in
   trainerbattle args. Untrusted refs are never repointed.
6. Tables (file offsets): species `0x141B350` ×11 (1292), moves `0x1D97378`
   ×13, abilities `0x1D8E858` ×13, items `0x3DB028` ×44 (name 14), types
   `0x1DBBA70` + `0x24F1A0` ×7, trainer classes `0x23E558` ×13, trainers
   `0x23EAC8+4` ×40 (name 12), dex categories `0x17D98F0` ×36 (12).
7. Free space: ~767 KiB of FF runs + recycled Chinese originals (~523 KiB of
   Chinese text total, 14.9k strings, ~12.9k unique).

## Translation conventions

- Modern casing: "Pokémon", "Poké Ball", official English names (veekun).
- Keep every `{..}` control token from the source (`{FD:01}` = player name,
  `{FD:06}` = rival, `{FC:..}` colour/pause, `{F9:..}` icons, `{FB}` new box).
- Don't hand-wrap dialogue; the inserter wraps. Menus/descriptions are wrapped
  to the Chinese source width, so keep them concise.

## Status

See `git log` and `build/insert_report.json` (missing = untranslated count).

## Resume point (2026-10-10, checkpoint 16) — intro, start menu, items fixed

`tm_batch.py stats` → **20,347/20,347 strings, 447,015 hanzi**; `insert.py`
missing 0 / errors 0 / too_long 0. Play-tested in mGBA from boot through the
Oak intro, Buena's radio show, Mom, New Bark Town and Elm's lab: all English.

New since checkpoint 15:
- Dump: battle scripts load messages via `setword 0x0203E020, ptr` (CFRU
  string loader) → ref kind `battlestr`; `<>¥` allowed; item description
  fields trusted. +522 strings (quest banners templated from TM quest names).
- **Live item table is `items2` at `0x7C7E00` (750 × 44 B)**; the old
  `0x3DB028` table is a stale copy. Names: veekun + `tables_manual/items2.json`.
- **Code-anchored text**: the hack's C code (intro at `0x775xxx`, start menu
  at `0x1FF6xxx`) reaches strings as literal base + `adds imm8` (GCC section
  anchors), so pointer scans never see them. Either translate in place within
  the byte budget (`manual_strings.json`, no `refs`) or relocate with a Thumb
  patch (`code_text.json`: literal + patched instructions, orig bytes
  asserted). Tools: scratch `lituse.py` / `anchors.py` (capstone in `.venv`).
- `width_override.json`: per-string window width (intro window ≈ 25 chars).
- `DIALOGUE_PX` 204 → 198: full-width lines collided with the ▼ arrow.

Next:
1. Graphics text (unchanged): title logo, character select, name-entry
   buttons, settings header/footer 更改设定 / 选择 切换 应用.
2. Play-test further: first battle (battle messages), Bag, Pokédex, Mart.
   Expect more code-anchored strings in hack UI; find them by searching the
   ROM for the on-screen hanzi (`char_to_code`) and listing the FF block.
3. `find_leftover_zh.py`: what remains is noise, link/Mystery Gift texts and
   3 copies of one trainer line (`09D82FA`) with an unrecognised ref.
4. ~1,250 old width warnings; fullwidth `；` gap.

## Checkpoint 15 notes

## Resume point (2026-10-10, checkpoint 15) — all dumped text translated, ROM boots

`tm_batch.py stats` → **19,893/19,893 strings, 440,656/440,656 hanzi**.
`insert.py` → missing 0, errors 0, too_long 0; BPS round-trips byte-exact.
Verified in mGBA (`EMULATOR.md`): boot, intro disclaimer, name entry and the
full settings screen render in English.

How the remaining ~63% got done (checkpoint 14 → 15):
- `vanilla_align.py` had the same `{FA}/{FB}` filter bug; fixed, plus a second
  route (the hack overwrote FR's text area in place, so base ROM at the *same
  address* is the official line). +1,969 official strings.
- Hack reused FR slots for new content, so every official pair was checked by
  Haiku agents (17 × ~400): 85 rejected and retranslated.
- ~7,500 strings translated by parallel Sonnet agents (brief + `tm_batch.py
  check` / `lookup` / `export`), merged with `tm_batch.py add`.
- `scripts/name_fix.py` + `text/en/name_canon.json`: one English name per
  character/place across agents (Dawn, Buena, Whitney, Silph Co., Sprout Tower…).
- `text/en/manual_strings.json`: strings no pointer scan can find (settings
  menu labels the code addresses directly), written in place or relocated with
  explicit refs (`ref_en` = different text for pointer readers).

Dump fixes found by the emulator:
- **Boot crash**: a "pointer" inside Thumb code (`0x1E4074` → `0x89C1B00`) was
  repointed. Rule: a ref whose 4 bytes equal vanilla FR cannot point at text
  the hack put into vanilla free space (44 strings dropped).
- Strings > 1000 bytes were skipped (the intro disclaimer is 1,856 B); now 4096.
- Long mostly-Latin texts (credits) accepted at ≥30 hanzi / ratio ≥ 0.1.
- One-hanzi labels (开/关/中…) accepted only when referenced from a pointer table.
- `insert.py` debug hooks: `INSERT_SKIP`, `INSERT_OUT`, `INSERT_NORECYCLE`.

Next:
1. **Graphics text** (not in the text pipeline): title logo, character-select
   prompt, name-entry mode buttons (拼音/返回/结束), settings header 更改设定
   and footer hints.
2. ~300 real strings (~5.6k hanzi) still reachable via *unaligned* refs in
   code-adjacent tables (battle/contest messages, e.g. `1DA13F6`) — see
   `find_leftover_zh.py`. Needs in-place-only handling, not repointing.
3. Play-test deeper (first town, battle, bag, Pokédex, Poké Mart ¥).
4. ~1,250 pre-existing width warnings (risk 2 below).
5. Fullwidth `；` renders with a wide gap; consider `,` in UI lines.

## Checkpoint 14 notes

## Resume point (2026-10-10, checkpoint 14) — translation is ~37%, not done

The checkpoint-13 "done" below was measured against an incomplete dump.
Driving the ROM in mGBA (`EMULATOR.md`) and scanning the built ROM for
Chinese text still reachable via pointers (`scripts/find_leftover_zh.py`)
showed `dump_all.py` had missed thousands of strings:

1. The junk regex `\{[0-9A-F]{2,4}\}` also matched `{FA}`/`{FB}`, so **every
   multi-box dialogue was dropped** (old dump: 0 strings with `{FB}`). Now
   `\{[0-9A-F]{4}\}` (undecodable 2-byte codes only).
2. `ref_kind` returned `None` for 4-aligned pointers without pointer
   neighbours *before* checking the `0F 00` loadpointer prefix. Now checked.
3. Lone aligned pointers (item-struct description fields, Thumb literal pools
   for battle messages) are kept as a new kind **`literal`**, but only when
   the target is clearly prose (`is_prose`). `literal` is not a script kind:
   `layout.dialogue_set` / `mark_suspects` treat it like `aligned`.

Re-dump: 14,909 → 23,693 strings, nothing removed or changed. `text/queue.json`
rebuilt (old IDs are void; TM is keyed by Chinese so nothing is lost).
`tm_batch.py stats` → **12,234/19,776 strings, 162,838/439,607 hanzi**.
`insert.py` → missing 7,915, errors 0, too_long 0.

Next: continue `tm_batch.py next` / `add` batches. Then the open risks below,
plus:

5. **Graphics text** (not in the text pipeline): title-screen logo
   (口袋妖怪 水银) and the character-select prompt 请选择你的照片 are not
   encoded text anywhere in the ROM, so they are probably images.
6. 41 old strings became `suspect` because they are now *interior* tails
   of newly found parent dialogues — same class as risk 1.

**Risk 1 re-assessed (checkpoint 14):** the Pokédex "page 2" pointer
(`0x17D9AFC`) is FR's `unusedDescription` field — never read by the game —
and it lands mid-character (`4基本…` starts on 己's trail byte). Most other
interior pointers (1,850 pairs) also start mid-word (`思议的消息！`,
`。有时会降低对…`): stale offsets, not shared suffixes. Treating
character-boundary tails as real strings was tried and rejected (759 mostly
meaningless fragments). `insert.py` never writes in place or recycles a parent
that contains another string, so a live tail would still show intact Chinese,
not garbage. Remaining action: in the emulator, check one move description
and one battle message whose parent is translated.
7. `find_leftover_zh.py` still reports ~3.5k reachable Chinese strings outside
   the dump (mostly noise or unrecognised script contexts); triage after the
   batches.

## Checkpoint 13 notes (superseded figures)

**Bulk translation is DONE.** `python3 scripts/tm_batch.py stats` reports
12275/12275 strings, 163560/163560 hanzi. All fixed-stride name tables done:
species 1290, moves 944, abilities 298, items 307, types, trainer_classes 105,
trainer_names 699, dex_categories 1025. `python3 scripts/insert.py` builds
`build/Mercury_EN.gba` + `build/Mercury_EN.bps` with `missing: 0, errors: 0,
too_long: 0`; the BPS round-trips byte-exact against clean FR 1.0.

Remaining (open risks, all need emulator testing):

1. **Description-tail pointers are stale (the "junk filter" issue).** Long
   texts — Pokédex flavour entries (`0x044xxxx`), move descriptions
   (`0x1D90xxx`), battle messages (`0x1D9Bxxx`), tutor-move list lines
   (`0x0E3Exxx`) — are stored as ONE string with a SECOND pointer into its
   middle (a continuation/"page 2" offset in the species/move data table).
   `dump_all.py` flags these interior pointers `suspect`, so `insert.py` skips
   them. The parent is translated + relocated, but the continuation pointer is
   never repointed → it still points at the original Chinese bytes. Confirmed
   at `0x44520b` (parent, now English at `0xe53c8e`) vs `0x445233` (tail, still
   Chinese "基本不能动。"), pointer table `0x17D9AF8`/`0x17D9AFC`. Fix =
   translate the tails and repoint the continuation offsets to the English line
   boundaries (or make the dex data single-pointer); verify in an emulator.
2. Width assumptions for fixed-width boxes (the ~2,277 `tm_batch.py add` WARN
   lines) — most are scrolling descriptions and likely benign, but menus must be
   spot-checked in an emulator.
3. Trainer-name transliterations (699) are hand work: official names for known
   characters, best-effort romaji for the rest (`text/en/tables_manual/
   trainer_names.json`). Spot-check in battle.
4. The currency glyph (¥) rendering next to English — emulator check.
