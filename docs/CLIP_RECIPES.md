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
swallowed, so every route opens with a wait or a repeated `Start`. States were saved (and every recipe re-recorded on that build, 2026-11-03) in `saves/states/river/` on River v0.5.9 (ROM SHA-1 `ae806508...`, made by `scripts/resave_states.py`) (gitignored; from the reporter's Champion save, so most start at New Bark Town 3.66). Some are saved with a screen already open (`bag-start`, `dex-start`, `mega-menu-start`, `mart-start`) or at a special place (`mombank-start` any overworld, `frontier-start` 31.3 at (15,5)) to keep routes at 10 tokens or fewer. Every row below was recorded, watched and marked Verified; re-do both after each River rebuild.

| Recipe | State name | Route | Shows |
|---|---|---|---|
| Quest menu | `river/quest-menu-start` (overworld in a town, Quests unlocked) | `w30 Start w30 Up*9 Down*5 A w40 Down w30 Down` | Start menu > Task: the quest list, stepping through the titles (#167-#182). **Verified 2026-11-03**: 10.4 s, 1.2 MB |
| Partner Patrol | `river/patrol-start` (3.80 at (29,48) on grass, three wild Pokémon visible in range, Ultra Balls in the bag, partner at full HP; flags set in the state: tip already seen `0x13B3`, short patrol `0x13B1`, Shiny Boost off `0x13A8` so a shiny cannot end it; spawn loop from `scripts/patrol_sweep.py`) | `w30 L w60 Select w900 A*4` | Quick Catch opens with L, SELECT sends the partner at every visible wild Pokémon in range, they vanish as it wins, then the summary ("beat N Pokémon", items found). **Verified 2026-11-03** (re-recorded on v0.5.9): 20.4 s, 587 KB. The patrol length varies with the RNG, so `w900` waits long enough for the summary (`w500` ended before it in one run). Keep the partner above 40% HP ("too hurt" otherwise). Without `0x13B3` the first patrol ends with a one-time tip after the summary |
| Chapter 2 on a Champion save | `river/ch2-lab-champion` (Elm's lab 43.6 at (5,13), Champion flag set) | `w30 U2 w60 A w40 A w40 A w40 A` | Elm's scene firing on a post-game save (#195/#196). **Verified 2026-11-02**: 8.4 s, 143 KB |
| New Bark to Elm's lab (Chapter 2 start) | `river/newbark-lab-door` (3.66 at (12,11), the tile south of Elm's lab door, reporter's Champion save) | `w30 tU U4 w90 U2 w120 A*6 w30` | Walking north through New Bark Town past the old end-of-story trigger (no "This version's story ends here"), through the door and straight up the lab's left column (x=4, the natural path): Elm's scene starts (#212, #99; before v0.5.9 only one tile fired it). **Verified 2026-11-03** on v0.5.9: 13.5 s, 1.2 MB. `R` alone is the shoulder button; use `R1` to walk |
| Route 28 west edge | `river/route28-edge` (58.0 at (6,12), reporter's Champion save) | `w30 L6 w90` | Walking to Route 28's west end: a plain border tile instead of stitched bridges, water and rocks (#195). **Verified 2026-11-03** on v0.5.9: 6.2 s, 752 KB; Ruben now stands on the grass south of the pond, not in it |
| Mt. Silver 1F edge | `river/mtsilver-edge` (58.1 at (30,20), the bottom right of the floor, reporter's Champion save) | `w30 D2 L3 w90` | Walking along Mt. Silver 1F's south edge: a plain border below the map where the report showed stitched tiles from other maps (#195). **Verified 2026-11-03** on v0.5.9: 7.4 s, 678 KB. Stay east of x=26: further west the trainer at (22,19) spots you and starts a battle |
| Mega menu | `river/mega-menu-start` (Bag open on Key Items with Key Stone highlighted; re-save it so) | `A w40 A w70 Down*3 w30 Down*3` | Bag > Key Items > Key Stone > Use: header "Mega Evo", Mega Gengar, "Ready" column (#197). **Verified 2026-11-03**: 7.0 s, 304 KB |
| Cheat Device menu | `river/cheats-start` (any overworld) | `w30 Select+R w60 Down w30 Down w30 B` | the hotkey opens the menu, browse the entries, B closes. **Verified 2026-11-03**: 5.6 s, 321 KB |
| Bag tabs and labels | `river/bag-start` (bag open on the Medicine pocket) | `w30 R*4 w30 R w30 R w30 R w30 R*2` | pocket labels Hold, Gem, Material, Misc, Key Items, Balls and the highlighted backpack corner (#189-#193). **Verified 2026-11-03**: 7.6 s, 254 KB |
| Dex search tabs, type names | `river/dex-start` (Pokédex open on the list) | `w30 Select w100 A w40 Down*2 w30 A w60 Down*3` | the search page (Search / Sort / Cancel tabs), then the Type dropdown (Fighting, Flying...) (#185, #187). **Verified 2026-11-03**: 9.0 s, 244 KB (re-recorded after #208: Mode and OK are English, the first type is Normal) |
| Trainer Card | `river/card-start` (overworld) | `w30 Start w30 Up*9 Down*6 A w60` | Start menu > Trainer Card page (#167-#182). **Verified 2026-11-03**: 9.8 s, 919 KB |
| Poké Mart (¥) | `river/mart-start` (buy menu open, made with `pokemart`) | `w30 A w80 Down w30 Down w30 Down w40` | Buy list with prices and the money box (the ¥ glyph; #171, #179). **Verified 2026-11-03**: 5.6 s, 239 KB. Not a talk-to-clerk start: the state opens the shop script directly |
| Mom Bank help page | `river/mombank-start` (any overworld) | `w30 Start w30 Down*9 A w80 Down*26 Right w60` | Mom's Bank is a Help Tips > System page (entry 27/28, has 2 pages): Start menu item 9 is Help Tips. **Verified 2026-11-03**: 19 s, 850 KB (the 26 Downs are slow; raise `--every` or cap `--max-mb` for Discord) |
| Frontier reception | `river/frontier-start` (31.3 at (15,5) facing up at the doubles counter, Saturate) | `w30 A*24 w150` | Saturate's speech, the Yes/No prompt and the 4-Pokémon picker. **Verified 2026-11-03**: 13.3 s, 410 KB. The arena and fight are **not** covered (the picker reopens after each pick and swallows inputs for ~150 frames; picking four different Pokémon needs a state at the picker, `frontier-picker`, and more routes) |

Notes:
- `Select+R` is a real token (both buttons pressed together). If the Cheat Device does not open, the hotkey may need a different hold; adjust in `play.go`.
- The Discord bot only offers a recipe whose row says `Verified <date>` and whose state exists, so a wrong route or stale state is never posted. Add the mark after you record it and watch the GIF.
- Keep clips short: `--idle 1.0` already trims still stretches; add `--max-mb 9` for Discord's limit.
- Record each state's recipe once, watch the GIF, then correct the route here. Mark verified rows with the date.
