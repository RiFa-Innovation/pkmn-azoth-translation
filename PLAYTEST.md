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
| 06-bedroom | after the intro, in the bedroom |
| 08-mom | downstairs after Mom gives Pokégear/Bag/Card/Notebook |
| 12-outlab | outside the lab, New Bark (Elm out on fieldwork) |
| 14-lyra | upstairs room east of the lab (stairs right of the lab), after meeting Lyra |
| 16-machine | lab, Elm back; starter machine is up-right of the player |
| 17-starter | starter-choice screen (map 43.7) |
| 19-afterstarter | got Chikorita, Elm sends you to Mr. Pokémon |
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
| 7 | Mom | "Obtained the PokéGear!" vs "Pokégear" elsewhere | open (minor) |
| 8 | intro video page | Bilibili-style header + Evangelion title card (Japanese kanji) | ok (easter egg) |
| 9 | Lyra intro | character card graphic still Chinese: 琴音 / CV.千本木彩花 (Lyra / CV. Ayaka Senbongi); likely one card per character | open (graphics) |
| 10 | starter choice | prompt 要选择哪一只精灵/作为你的搭档？ baked into the screen's map tileset | fixed (scripts/maptext.py, gfx/map_starter.json) |
| 11 | leaving the lab | "咕咚!!" is a sound-effect picture (64x64 sprite, entry 13 of the picture table 0x1DE5A08) | fixed ("Thud!", scripts/sprtext.py) |
| 12 | New Bark triggers | "喂，{FD:01}！" and 16 other one-hanzi lines never dumped (filter needed 2 hanzi) | fixed (dump accepts short script lines) |
| 13 | lab aide | item pop-up: "It restores the HP of one Pokémon" runs into the arrow | open (minor) |
