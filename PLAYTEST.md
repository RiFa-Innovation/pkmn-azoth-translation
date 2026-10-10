# Playtest log

Run with `scripts/play.py` (headless mGBA). States live in `saves/states/NAME.ss`
(gitignored, with a `.png` of the last frame); `python3 scripts/play.py load NAME`.

Status: **open** = to fix, **fixed** = fixed in the build noted, **ok** = checked, fine.

## States

| state | where |
|---|---|
| 00-title | title screen, fresh boot |
| 01-named | after naming the player MIKE (FireRed name screen) |
| 02-intro | disclaimer pages done, before settings/Oak |

## Findings

| # | where | what | status |
|---|---|---|---|
| 1 | name entry | hack's pinyin keyboard; letters never reached the name -> random default name | fixed ec684e3 (FireRed screen) |
| 2 | battle | "Wild" glued to the Pokémon name | fixed c132334 (verify in battle) |
| 3 | text input title | "Your Name?" for every prompt (vanilla mismatch) | fixed c132334 / ec684e3 |
| 4 | Oak intro | every text box blank / black (text colour bytes at 0x7AAB7B overwritten by an anchored string whose head was a colour array) | fixed (anchored dump starts at the inner target) |
| 5 | radio (Tue) | day-of-week song table at 0x8EA69E (ldrh [r0, r3]) taken for text and overwritten; same for data before "Exit settings" (0xE3771C) | fixed (hackmap: literal used as index register = table) |
