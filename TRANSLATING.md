# How the translation was made, and how to revise it

This is the English translation of **Pokémon Azoth** (口袋妖怪 水银 / "Mercury").
It is **machine-assisted**: the text was found and re-inserted with tools, and
the English was drafted with Claude (an AI model), then play-tested. It has not
had a full human pass. That pass is the most useful thing anyone can add.

This page has two parts:

1. [Revising the conversations](#1-revising-the-conversations-no-coding) with a
   spreadsheet (no coding).
2. [Reproducing the machine-assisted workflow](#2-the-machine-assisted-workflow-for-maintainers)
   (translate new or changed text the same way it was done).

No ROMs are in this repository and none should be committed or uploaded. You
need your own clean FireRed (USA, v1.0) only to build and test.

---

## 1. Revising the conversations (no coding)

The file to edit is **[`docs/dialogue-review.csv`](docs/dialogue-review.csv)**.
It holds the ~9,400 lines that scripts print to a text box: NPC speech, trainer
lines and story. Names, signs, menus and item/move texts are **not** in it
(see [Other text](#other-text-names-signs-menus-and-descriptions)).

Open it in any spreadsheet (Excel, LibreOffice, Google Sheets; import as UTF-8
CSV). The columns are:

| Column | What it is |
|---|---|
| `id` | ROM address of the line (use it to refer to the line in a report) |
| `map` | the map the line belongs to, `group.number` (best effort) |
| `place` | a human name for that map when we know it (many are blank; fill them in) |
| `before` | the previous line of the same map, for context |
| `zh` | the Chinese source (do not edit) |
| `en` | the current English |
| `limit` | what the line has to fit: box width in px and line cap (see below) |
| `now` | what the current English uses: lines, widest line in px, bytes |
| `new_en` | **your version.** Leave empty to keep `en` |

**About the budget.** Almost every line here is *relocated* by the inserter, so
its byte count is not a limit; the real limits are the box width (conversations
are 198 px per line, about 33 letters) and, for boxes that don't scroll, the
line cap. Compare `now` with `limit`: if the widest line is already near the
width, your longer wording will simply wrap onto another line. A few lines
(about 70) are also read in place by other code; for those `limit` says
`ALSO READ IN PLACE` and gives a byte count to stay within, otherwise that
other use still shows the Chinese.

Rows are sorted by map and then by position, so a conversation reads top to
bottom. `\n` in a cell is a line break.

### Using Google Sheets (or Excel)

The file is a plain UTF-8 CSV, so no Excel file is needed. In Google Sheets:
**File → Import → Upload**, choose *Replace spreadsheet*, and **untick
"Convert text to numbers, dates and formulas"**. That setting matters: left on,
Sheets turns map ids like `3.50` into `3.5` (a different map) and ids such as
`01E3414` into numbers, which breaks the import later. Then freeze row 1,
turn on text wrapping, and optionally protect every column except `new_en`.

To send edits back, use **File → Download → Comma Separated Values (.csv)**
with the header row unchanged. Only `id`, `zh`, `en` and `new_en` are read, so
extra columns you add are ignored. Several people editing at once is fine as
long as each works in their own range of rows (or their own tab).

### Rules for `new_en`

- **Keep every code in `{braces}`** exactly as in `zh`: `{FD:01}` is the
  player's name, `{FD:06}` the rival's, `{FC:..}` colours/pauses, `{F9:..}`
  icons. `{FB}` (new box) and `{FA}` (scroll) may move, but keep them where a
  sentence ends.
- **Don't hand-wrap.** Write normal sentences; the inserter wraps to the box.
  Keep `\n` only where the Chinese has a deliberate break.
- **Keep it short.** English is longer than Chinese. Text boxes are 2 lines
  and cannot grow. If a line is much longer than the Chinese, tighten it.
- **Characters and places** follow [`text/en/name_canon.json`](text/en/name_canon.json)
  and [`text/en/glossary.json`](text/en/glossary.json). Please don't change one
  spelling in isolation; propose it in an issue and it gets changed everywhere.
- Modern English spellings: "Pokémon", "Poké Ball". Use `’` or `'` as you
  like; both are converted.
- Characters the game's font cannot draw are rejected on import (for example
  emoji or most accented letters; `é` is fine).

### Sending your edits

Any of these work, easiest first:

1. **One or a few lines:** open the *Wording suggestion* form
   ([issues](../../issues/new/choose)). Paste the `id`, the current line and
   your version.
2. **A sheet:** save your edited CSV and attach it to an issue (or open a pull
   request that replaces the file). Only rows with a filled `new_en` are used,
   so you can delete the rows you did not touch.
3. **Pull request with the result:** run the import yourself:

   ```bash
   python3 scripts/review.py import docs/dialogue-review.csv --dry-run   # check
   python3 scripts/review.py import docs/dialogue-review.csv             # write
   python3 scripts/insert.py                                             # rebuild
   ```

   `import` writes your lines into `text/en/strings.json` (the translation
   memory, keyed by the Chinese text). Anything with changed or missing
   `{codes}` is rejected with the reason.

### Seeing it in game

Build the patch and apply it to your clean FireRed ROM (see the README), then
play to the scene. The `map`/`place` columns tell you where to look. A
conversation that does not fit its box is reported by the build as
`too_long`; nothing is silently cut.

### Other text (names, signs, menus and descriptions)

These live in the same translation memory but are not in the conversation
sheet. Export just what you want:

```bash
python3 scripts/review.py export review.csv --match "Falkner" --limit 200
python3 scripts/dialogue_sheet.py my.csv --map 43.6    # one map's conversations
```

`review.py export` lists any text (`--source vanilla` also includes lines that
are FireRed's own English). Edit and import it the same way as above.
Name tables (species, moves, items) use official names from veekun
(`data/ref/*.csv`) plus overrides in `text/en/tables_manual/`.

---

## 2. The machine-assisted workflow (for maintainers)

This is how text got from the Chinese ROM into English, so changed or new text
can be handled the same way.

### 0. Setup

```bash
pip install numpy pillow            # dump + graphics
.venv/bin/python -m pip install capstone   # only to rebuild the code map
```

Put the clean FireRed USA v1.0 ROM at
`roms/Pokemon - FireRed Version (USA, Europe).gba` and the Chinese hack at
`roms/Pokemon Mercury 1.3.3 (patched).gba` (both git-ignored).

### 1. Dump every string

```bash
python3 scripts/dump_all.py          # -> text/zh.json
```

Strings are found by pointer scan and trusted only in contexts that make them
real text pointers (see [`PROCESS.md`](PROCESS.md)). `text/zh.json` maps
address to Chinese, capacity and references. Re-dumping is safe: the
translation memory is keyed by the Chinese text, so nothing is lost.

### 2. Queue what is not translated yet

The *translation memory* (TM) is `text/en/strings.json`, `{chinese: english}`.
`null` marks junk that must never be inserted.

```bash
python3 scripts/tm_batch.py stats               # how much is translated
python3 scripts/tm_batch.py next 100            # print the next untranslated lines
python3 scripts/tm_batch.py export work 8       # split the queue into 8 chunk files
```

Each chunk is `[{"id": "123", "zh": "..."}, ...]`. IDs index
`text/queue.json` (stable across re-dumps).

### 3. Draft the English with an AI model

Give the model one chunk at a time, with the rules below and the glossary, and
ask for a JSON object `{id: english}`. A prompt that worked:

```
You are translating the Chinese Pokémon FireRed hack "Pokémon Azoth" (Johto
remake, Gold/Silver/HeartGold era) into English.
Return ONLY a JSON object mapping each id to its English text.
Rules:
- Keep every {..} control code exactly (e.g. {FD:01} player name, {FD:06}
  rival, {FB} new box, {FA} scroll, {FC:..}, {F9:..}).
- Keep the same line breaks (\n) unless a line would be too long; don't add
  new boxes ({FB}).
- Natural, warm game dialogue; modern casing: "Pokémon", "Poké Ball".
- Use these names exactly: <paste the relevant part of text/en/glossary.json
  and text/en/name_canon.json>.
- Menus and short labels must be about as short as the Chinese.
- Output null for strings that are not text (garbled bytes).
```

Look up a term before translating a chunk: `python3 scripts/tm_batch.py lookup 阿速`
prints the official name and how the TM already uses it.

### 4. Check, merge, rebuild

```bash
python3 scripts/tm_batch.py check out.json      # validate without merging
python3 scripts/tm_batch.py add out.json        # merge into text/en/strings.json
python3 scripts/name_fix.py                     # report names that drifted
python3 scripts/insert.py                       # build ROM + patch
```

`check`/`add` verify the control codes match, the text is encodable in the
game's font, and menu lines are not wider than the source. The build report
must be `missing: 0`, `too_long: []`, `errors: []`. Boxes that cannot scroll
need a `lines` cap in `text/en/width_override.json`.

### 5. Verify

```bash
python3 scripts/bps.py apply "roms/Pokemon - FireRed Version (USA, Europe).gba" build/Mercury_EN.bps /tmp/check.gba
cmp /tmp/check.gba build/Mercury_EN.gba
```

Then play the scene in an emulator ([`EMULATOR.md`](EMULATOR.md) has the
scripted setup) and log what you find in [`PLAYTEST.md`](PLAYTEST.md).

### 6. Refresh the review sheet

After a batch of translation or revision changes:

```bash
python3 scripts/dialogue_sheet.py docs/dialogue-review.csv
```

The sheet is generated, so regenerate it instead of editing it by hand in the
repository.

### Where things live

| What | File |
|---|---|
| Chinese dump | `text/zh.json` (+ `text/zh_anchored.json`) |
| Translation memory (hand) | `text/en/strings.json` |
| FireRed's own English | `text/en/strings-vanilla.json` |
| Names (official + canon) | `text/en/glossary.json`, `text/en/name_canon.json`, `text/en/names_zh_en.json` |
| Box widths / line caps | `text/en/width_override.json` |
| In-place and code-reached text | `text/en/manual_strings.json`, `anchored.json`, `code_text.json` |
| Text drawn as graphics | `gfx/*.json` |
| Map names for the review sheet | `data/map_names.json` |

### Known limits

- Anything reached only by base+offset from code is written in place and must
  fit the original bytes (see issue #11, now mostly done).
- Some Chinese in game may still be a fragment of a longer string; report
  anything that is still in Chinese with a screenshot and where you were.
- The translation is not "official". It is a fan translation by a Claude-assisted
  workflow; the hack and its content belong to its original authors.
