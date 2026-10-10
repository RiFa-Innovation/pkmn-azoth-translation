# Mercury (水银) 1.3.3 — translation process state

> Updated 2026-10-09 (checkpoint 10). Resume from here. Everything below is
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
