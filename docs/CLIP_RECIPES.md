# Clip recipes (`scripts/clip.py`)

Each recipe is a start state plus a short route. Save the state once on a River build, then record:

```
python3 scripts/play.py boot "build/editions/Pokemon River Azoth (Chapter 2 + Frontier).gba"
# ...get to the start position by hand or with a route, then:
python3 scripts/play.py save river/quest-menu-start river
python3 scripts/clip.py --state river/quest-menu-start --route "Start w30 D2 A w40 A w40 D1 w40" --out quest.gif
```

States only load on the build that made them, so re-save them after every River release. Routes use `play.py` tokens
(`A B Start Select L R`, `U3` walk, `tU` turn, `wN` wait N frames). The Start menu's first press after a state load is sometimes
swallowed, so every route opens with a wait or a repeated `Start`. Menu cursor positions below are **guesses**: none of the
routes has been recorded yet. Adjust the `D`/`U` counts the first time and fix the line here.

| Recipe | State name | Route | Shows |
|---|---|---|---|
| Quest menu | `river/quest-menu-start` (overworld in a town, Quests unlocked) | `w30 Start w30 D4 A w40 D1 w30 D1 w30 B` | quest list, stepping through the titles (#167-#182) |
| Partner Patrol | `river/patrol-start` (Quick Catch reachable, a wild mon in view) | `w30 Select w40 A w120` | SELECT in Quick Catch sends the walker at the target |
| Chapter 2 on a Champion save | `river/ch2-lab-champion` (Elm's lab 43.6 at (5,13), Champion flag set) | `w30 U2 w60 A w40 A w40 A w40 A` | Elm's scene firing on a post-game save (#195/#196, v0.5.6+) |
| Mega menu | `river/mega-menu-start` (Key Stone in the bag, unlocked Megas) | `w30 Start w30 D2 A w40 D1 A w40 D3 w30 D3` | header "Mega Evo", Mega Gengar, "Ready" column (#197) |
| Cheat Device menu | `river/cheats-start` (any overworld) | `w30 Select+R w60 D1 w30 D1 w30 B` | hotkey, then browsing the entries (`Select+R` may need two tokens; see below) |
| Bag tabs and labels | `river/bag-start` (overworld) | `w30 Start w30 D2 A w40 R w30 R w30 R w30 R` | pocket labels (Gem, Material, Hold, Misc) and the highlight corner (#189-#193) |
| Dex search tabs, type names | `river/dex-start` (overworld, Dex owned) | `w30 Start w30 A w40 Select w40 D2 A w40 R` | Search / Sort / Cancel tabs and the type dropdown (#185, #187) |
| Trainer Card | `river/card-start` (overworld) | `w30 Start w30 D3 A w60` | Trainer Card page (#167-#182) |
| Poké Mart (¥) | `river/mart-start` (facing the clerk) | `w30 A w40 A w40 D1 w30 D1 w30` | ¥ glyph in the price list |
| Mom Bank help page | `river/mombank-start` (the house with Mom) | `w30 A w40 A w40 A w40 Start w40` | Mom's Bank, then its help page |
| Frontier battle | `river/frontier-start` (Frontier entrance) | `w30 U2 A w40 A w40 A w40 A w200` | entering and the opening of a fight (cap `--max-mb`/length, ~10 s) |

Notes:
- `play.py` has no combined-button token, so for SELECT+R either use a held-input helper or call it as two quick taps (`Select R`) and
  check it opens the Cheat Device; if not, add a `Select+R` token to `play.go`.
- Keep clips short: `--idle 1.0` already trims still stretches; add `--max-mb 9` for Discord's limit.
- Record each state's recipe once, watch the GIF, then correct the route here. Mark verified rows with the date.
