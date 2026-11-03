# Clip recipes (`scripts/clip.py`)

Each recipe is a start state plus a short route. Save the state once on a River build, then record:

```
python3 scripts/play.py boot "build/editions/Pokemon River Azoth (Chapter 2 + Frontier).gba"
# ...get to the start position by hand or with `play.py go "ROUTE"`, then:
python3 scripts/play.py save quest-menu-start river        # -> saves/states/river/quest-menu-start.ss
python3 scripts/clip.py --edition river --state quest-menu-start --route "w30 Start w30 Down*4 A w40" --out quest.gif
```

In the table, `river/NAME` means state `NAME` of the `river` edition (the Discord bot reads this table, so keep its shape).
States only load on the build that made them, so re-save them after every River release. Routes use `play.py` tokens
(`A B Start Select L R`, `U3` walk, `tU` turn, `wN` wait N frames, `Down*2` repeat a button, `Select+R` buttons together). In a menu use
`Down*n` / `Up*n`, never `D2`: `D<n>` is a *walk* of n tiles and does nothing in a menu. The Start menu's first press after a state load is sometimes
swallowed, so every route opens with a wait or a repeated `Start`. States for every row except `mart-start` were saved 2026-11-02 in `saves/states/river/` (gitignored; from the reporter's Champion save, so most start at New Bark Town 3.66; `mega-menu-start` has a Key Stone added, `mombank-start` is 43.0 (6,6), `frontier-start` is 31.3 (10,17)). Menu cursor positions below are **guesses**: only the Chapter 2 route has been recorded. Adjust the `Down*n` counts the first time and fix the line here.

| Recipe | State name | Route | Shows |
|---|---|---|---|
| Quest menu | `river/quest-menu-start` (overworld in a town, Quests unlocked) | `w30 Start w30 Up*9 Down*5 A w40 Down w30 Down w30 B` | quest list, stepping through the titles (#167-#182) |
| Partner Patrol | `river/patrol-start` (a route with a visible wild Pokémon within 7 tiles, e.g. 3.67; Poké Balls in the bag; **not** New Bark Town, which has none) | `w30 L w40 R w20 Select w120` | Quick Catch opens with L, R locks the target, SELECT sends the walker at it. Route unverified |
| Chapter 2 on a Champion save | `river/ch2-lab-champion` (Elm's lab 43.6 at (5,13), Champion flag set) | `w30 U2 w60 A w40 A w40 A w40 A` | Elm's scene firing on a post-game save (#195/#196). **Verified 2026-11-02**: 8.4 s, 143 KB |
| Mega menu | `river/mega-menu-start` (Bag open on Key Items with Key Stone highlighted; re-save it so) | `A w40 A w70 Down*3 w30 Down*3` | Bag > Key Items > Key Stone > Use: header "Mega Evo", Mega Gengar, "Ready" column (#197). Menu path verified 2026-11-03 |
| Cheat Device menu | `river/cheats-start` (any overworld) | `w30 Select+R w60 Down w30 Down w30 B` | hotkey, then browsing the entries |
| Bag tabs and labels | `river/bag-start` (overworld) | `w30 Start w30 Up*9 Down*2 A w40 R w30 R w30 R w30 R` | pocket labels (Gem, Material, Hold, Misc) and the highlight corner (#189-#193) |
| Dex search tabs, type names | `river/dex-start` (overworld, Dex owned) | `w30 Start w30 Up*9 A w60 Select w40 Down*2 A w40 R` | Search / Sort / Cancel tabs and the type dropdown (#185, #187) |
| Trainer Card | `river/card-start` (overworld) | `w30 Start w30 Up*9 Down*6 A w60` | Trainer Card page (#167-#182) |
| Poké Mart (¥) | `river/mart-start` (facing the clerk) | `w30 A w40 A w40 Down w30 Down w30` | ¥ glyph in the price list |
| Mom Bank help page | `river/mombank-start` (any overworld) | `w30 Start w30 Down*9 A w80 Down*26 Right w60` | Mom's Bank is a Help Tips > System page (entry 27/28, has 2 pages): Start menu item 9 is Help Tips. Path verified 2026-11-03 |
| Frontier battle | `river/frontier-start` (31.3 at (15,5) facing up at the doubles counter, Saturate) | `w30 A*7 w60 A Down A Down A Down A w100` | desk talk, Yes, then the 4-Pokémon picker (A on the same Pokémon twice is refused, so Down between picks). Verified up to the picker 2026-11-03; the arena and fight are not recorded |

Notes:
- `Select+R` is a real token (both buttons pressed together). If the Cheat Device does not open, the hotkey may need a different hold; adjust in `play.go`.
- Keep clips short: `--idle 1.0` already trims still stretches; add `--max-mb 9` for Discord's limit.
- Record each state's recipe once, watch the GIF, then correct the route here. Mark verified rows with the date.
