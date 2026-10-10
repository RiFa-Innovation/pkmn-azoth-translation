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
| 7 | Mom | "Obtained the PokéGear!" vs "Pokégear" elsewhere | open (minor) |
| 8 | intro video page | Bilibili-style header + Evangelion title card (Japanese kanji) | ok (easter egg) |
| 9 | Lyra intro | character card graphic still Chinese: 琴音 / CV.千本木彩花 (Lyra / CV. Ayaka Senbongi); likely one card per character | open (graphics) |
| 10 | starter choice | prompt 要选择哪一只精灵/作为你的搭档？ baked into the screen's map tileset | fixed (scripts/maptext.py, gfx/map_starter.json) |
| 11 | leaving the lab | "咕咚!!" is a sound-effect picture (64x64 sprite, entry 13 of the picture table 0x1DE5A08) | fixed ("Thud!", scripts/sprtext.py) |
| 12 | New Bark triggers | "喂，{FD:01}！" and 16 other one-hanzi lines never dumped (filter needed 2 hanzi) | fixed (dump accepts short script lines) |
| 13 | lab aide | item pop-up: "It restores the HP of one Pokémon" runs into the arrow | open (minor) |
| 14 | Mom (Running Shoes) | "Oh, right" printed as "Oh ▯ht": a false pointer (text bytes 0E 9E 08 inside 红色的火球 at 0xABEAE0) was repointed into recycled space holding this line. 284 such refs | fixed (dump drops refs inside script text; build reserves every repointed word) |
| 15 | battle move info | type icons 一般/火/… (hack's menu-info sheet 0xEFD4C0) | fixed (3-letter codes NOR/FIR/…, TYPE/POWER/ACCURACY/PP/EFFECT labels from FireRed; scripts/typeicons.py) |
| 16 | battle strings | live FireRed battle strings the hack half-overwrote ('…与对手{broken}换了特性！ with its opponent!', 的/是/果 suffixes) | fixed (restored FireRed English for 8 symbols) |
| 17 | ability pop-up | "Sentret的" (Chinese possessive). Not sText_ApostropheS (restored, unchanged on screen), not in RAM buffers, no pointer to a 的 string; text is drawn into the pop-up sprite (gfx raw at 0x1E9F814). Needs the pop-up print routine traced | open |
| 18 | wild battle | "Wild Sentret used Growl!" spacing correct | ok |
| 19 | start-menu hint | "Go through Yoshino City to Mr." (Japanese name, cut) | fixed ("Find Mr. Pokémon past Cherrygrove.", width override) |
| 20 | party menu | "What will you do with t…" overflows | fixed ("Do what with it?") |
| 21 | summary info | "Relaxed (+Defense -Sp…" + " nature." overflow | fixed (natures abbreviated +Def -Spe; templates drop " nature.") |
| 22 | summary skills | page header "✚换页" (lone struct-field string) | fixed ("Page") |
| 23 | summary skills | ability descriptions cut at ~134px | fixed (2-line wrap at 134px; 103 long ones shortened) |
| 24 | battle | "Chikorita gained  17 Exp. Points!" double space | open (minor) |
| 25 | bag | pocket tabs cut: Training It…, Battle Item…, Evolution I…, Special Gem…, Materials &… | fixed (Training/Battle/Evolution/Gems/Materials) |
| 26 | bag | item descriptions run into the arrow / past 3 lines (box ~176px, starts after the icon) | fixed (wrap at 176px; 129 long ones shortened; 0 over 3 lines) |
| 27 | Cherrygrove PC girl | birthday-month prompt reset the game: the hack calls DoNamingScreen with template 0 (and at hook+2) and writes hack-only fields; FireRed's screen can't serve it | fixed (dispatcher data/naming_dispatch.s: intro + templates 1-4 -> FireRed screen, template 0/5+ and hook+2 callers -> hack screen, which keeps its English buttons and ABC default) |
| 28 | dump | 297 'strings' that are Thumb code (function pointers decoded as text) | fixed (dump skips targets inside code) |
| 29 | Cherrygrove PC girl | birthday month: typing "12" (ABC or symbol-page digits) is rejected and the prompt reopens - same in the Chinese ROM. Parser 0x09D5D7CC accepts FR digits 0xA1-0xAA into VAR_RESULT; the girl's script may use another routine. Her lines so far are English | open (hack behaviour; investigate which routine she uses) |
| 30 | dialogue name box | "Mr. Pokém" cut: the box is 6 tiles (fits 4 hanzi) | fixed (all 84 box setups widened to 8 tiles; names trimmed of centring spaces; 5 long ones shortened) |
