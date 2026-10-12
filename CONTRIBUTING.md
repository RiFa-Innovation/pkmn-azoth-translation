# Contributing

Thanks for helping. Translation fixes, bug reports and tooling improvements are
all welcome.

## Never commit ROMs, patches or saves

ROMs are copyrighted and must not end up in this repository, not even in
history. `.gitignore` excludes `*.gba`, `*.bps`, `*.sav`, emulator states,
`roms/`, `saves/`, `build/` and `dist/`. The `no-roms` CI check fails any push
or PR that tracks such a file or anything with a GBA ROM header.

- Don't use `git add -f` on anything under those paths.
- Patches are published only as **Release assets**, never committed.
- If a ROM is ever committed by mistake, don't just delete it in a new commit.
  Open an issue so history can be rewritten before it spreads.

## Reporting a bug

Open an issue with:

- the release (e.g. `beta-3`) and emulator (mGBA version, or hardware/flashcart),
- where it happened (town/route, menu, what you pressed),
- a screenshot, and your `.sav` file if it's a crash or freeze (an in-game
  save; emulator save states break between patch versions). Attach saves to
  the issue, never to a PR.

The [bug report form](../../issues/new/choose) asks for all of this.

Untranslated or clipped text is a bug too. A screenshot is enough.

## Setting up

You need two ROMs in `roms/` (gitignored):

| File | What |
|---|---|
| `roms/Pokemon - FireRed Version (USA, Europe).gba` | clean FireRed US 1.0, CRC32 `DD88761C` |
| `roms/Pokemon Mercury 1.3.3 (patched).gba` | the Chinese hack (FireRed + the Mercury 1.3.3 patch) |

```bash
python3 -m venv .venv && .venv/bin/pip install numpy pillow capstone
git clone https://github.com/pret/pokefirered utilities/pokefirered   # charmap + symbol map
python3 scripts/insert.py      # -> build/Mercury_EN.gba + build/Mercury_EN.bps
```

Emulator play-testing (optional) needs a locally built `mgba-headless` and the
`mcp-mgba` Lua bridge. See [`EMULATOR.md`](EMULATOR.md).

## Changing a translation

Translations are keyed by the **Chinese source text**, not by address:

- dialogue and most strings: `text/en/strings.json` (`"中文": "English"`),
- name tables (species, moves, items…): `text/en/tables_manual/<table>.json`,
- code-anchored strings: `text/en/anchored.json`, `manual_strings.json`, `code_text.json`.

Conventions (details in [`PROCESS.md`](PROCESS.md)):

- Official English names and modern casing ("Pokémon", "Poké Ball").
- Keep every `{..}` control code from the source (`{FD:01}` = player name,
  `{FB}` = new box, `{FC:..}` = colour/pause, …).
- Don't hand-wrap dialogue; the inserter wraps it. Menus and descriptions have
  fixed boxes, so keep them concise. If a box can't scroll, give it a `lines`
  cap in `text/en/width_override.json`. Text drawn past a window's bottom edge
  writes past its buffer and can crash the game (see issue #1).
- Character/place names must match `text/en/name_canon.json`
  (`python3 scripts/name_fix.py` reports mismatches).

## Proofreading (the translation needs a human pass)

The translation is machine-assisted, so editing it is the most useful thing
you can do, and you don't need to code.

- **One line:** use the [Wording suggestion form](../../issues/new/choose).
  Say where it is in the game, paste the current text and your version.
- **Conversations:** edit [`docs/dialogue-review.csv`](docs/dialogue-review.csv)
  (map, previous line, Chinese, English, your version). The full guide, rules
  and the machine-assisted workflow are in [`TRANSLATING.md`](TRANSLATING.md).
- **Many lines:** use the spreadsheet workflow.

  ```bash
  python3 scripts/review.py export review.csv --match "Falkner" --limit 200
  # open review.csv in any spreadsheet; type your version in the new_en column
  python3 scripts/review.py import review.csv --dry-run     # check it first
  python3 scripts/review.py import review.csv               # write it
  python3 scripts/insert.py                                 # rebuild to see it in game
  ```

  `import` rejects lines that drop or change codes like `{FD:01}` (the player's
  name) or use characters the game's font can't draw. Don't hand-wrap
  dialogue: the inserter wraps it. Keep menu and description lines short.
  `--source vanilla` also lists lines that are FireRed's own English.
- **Names:** characters and places follow `text/en/name_canon.json`; please
  don't "fix" one spelling in isolation.

## Before you open a PR

1. Rebuild: `python3 scripts/insert.py`. The report must say
   `missing: 0`, `too_long: []`, `errors: []`.
2. Verify the patch round-trips:
   `python3 scripts/bps.py apply "roms/Pokemon - FireRed Version (USA, Europe).gba" build/Mercury_EN.bps /tmp/check.gba && cmp /tmp/check.gba build/Mercury_EN.gba`
3. Check the change in an emulator, and attach a screenshot to the PR for
   visible text.
4. Log play-test findings in the table in [`PLAYTEST.md`](PLAYTEST.md) in the
   same commit as the fix.

Keep PRs focused (one bug or one batch of related strings). Use `Fixes #N` in
the description to link the issue.

## Releases

Maintainers tag releases from `main` (`beta-N`) and attach the `.bps` built
from that commit. Release notes list the base ROM checksum, the patched ROM's
SHA-1, and the issues fixed.
