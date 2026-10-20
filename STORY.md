# Story status of Pokémon Azoth (Mercury): what exists, what is left open

> Spoilers. This is working documentation for the fan translation, derived from the
> ROM's dialogue, quest text and map data (2026-10-20). The hack, its story and its
> characters belong to its original authors; this repo only translates it with Claude.
> Nothing here was verified by a full playthrough. Verify in the emulator before acting.

Sources: `docs/dialogue-review.csv` (English text per map), `scripts/hackdb.py`
(maps, warps, scripts, vars), the hack's map-name table at `0xC2B0DC`
(region id = 143 + index).

## Where the story stops

- **Chapter 1 (Johto) is complete**: eight Johto badges, the Lugia/Ho-Oh climax, Sange's farewell letter.
- A title card reads **"Pokémon Azoth – Second Chapter: Rainbow"** (string `0x09DB754D`), followed by
  Elm giving a Master Ball, the three Johto starters, Mega Stones and the National Dex, then
  pointing the player east: Route 27 → Route 26 → Indigo Plateau.
- **Chapter 2 is a stub.** Authored content: that walk, Kukui's cameo on Route 26, the League
  (Lance, "Dragon Tamer", is Champion), then Mom's scene: an odd man named Ashida left a gift for the
  new Champion (script `0x08A68500`; the item is item 370, the **Mystic Ticket**). Nothing found after that.

## Chapter 1 beats

1. New Bark / Cherrygrove: Pichu joins, Pokégear, Lyra and Yellow.
2. Violet / Sprout Tower: Falkner; Dawn (Sinnoh, Piplup); the "elder" is Petrel in disguise.
3. Azalea / Ilex: Slowpoke Well; Bugsy; first Mega Evolution research.
4. Goldenrod: Whitney; Team Rocket (Archer, Petrel, Ariana) seizes the Radio Tower to call Giovanni back.
5. Ecruteak: Kimono Girls, Summer Festival, Morty, Burned Tower.
6. Olivine / Cianwood / Mahogany: Glitter Lighthouse rescue; a Rocket device that forces Mega Evolution
   ("Runaway Mega Evolution"); Lance investigates the red Gyarados at the Lake of Rage.
7. Blackthorn / Dragon's Den: Rocket steals the Rainbow Stone shards.
8. Whirl Islands: Archer awakens Lugia with an Orre Shadow-Pokémon device.
9. Climax: Sange (the "Holy Child") plays the Time Flute, swaps with Celebi and is sent ~150 years
   into the past; Clear Bell + Rainbow Wing call Ho-Oh.

## Open threads

| Thread | Evidence | Needs |
|---|---|---|
| Archer | His "R" badge glows rainbow, not red. Narration: "the script has finally reached its last act… wait for the one and only lead to arrive." Epilogue: his file "remains open." | Likely Chapter 2 villain |
| Rainbow Stone shards / Mega signal | Line about a device "Anzu" hidden in the Prism Tower (Kalos) broadcasting Mega energy | Who holds the shards; what Archer builds |
| Giovanni and his son (Silver) | Looker tracked Silver to Route 23; International Police say he is at Indigo; rival is told his "love and trust for Pokémon isn't enough" | Silver's arc, Giovanni's return |
| "Cloaked Dragon Tamer" | Beat Kukui and Silver at Indigo; Lance is also an ally in Johto | Check in play whether this is a deliberate twist |
| Sange / Celebi | Sange is in the past, Celebi in the present | Celebi's whereabouts; any return |
| Lugia / Ho-Oh | Link hinted; Lugia "temporarily held back", then gone | Closure |
| Team Galactic remnants | Charon, Saturn, Stark Mountain, Lucas | Tie off or drop |
| Cliffside "Successor" | Elder picks the player; Mega Evolution's origin is the Hoenn meteor people; Axel/Lucario rematch | Payoff for this clan |
| "Amala Multiverse" | Igor (Seabreak Cave): the player is from outside it | Probably a wink |
| Mystic Ticket | Ashida's gift, "the key to a whole new adventure" | Navel Rock is the vanilla destination |

## Regions and locations

**Built:** Johto; Cliffside Town and its area (Routes 47/48, Phantom Forest, Seabreak Cave,
Buried Tower, Silent Hill, Dragon's Den); vanilla Kanto and Sevii.

**Named in the map-name table with no maps:** Mt. Silver (region 205), Route 28 (204),
Route 52 (188), Battle Tower (220). Battle Frontier has 1 map, Interaction Plaza 1
("the Pokéathlon is still being prepared"), Navel Rock 9 (ticket island).

**Gated by "under construction"/"closed" text:** Route 50 beyond the fight, the whirlpool to
Silent Hill, the Far Shore sea bridge to Cianwood (while the Goldenrod-side text says it is
finished), Goldenrod's 6th floor and Battle Corner/Colosseum, the Johto Safari Zone,
the Olivine Seagallop ("no sailing plans").

**Unlinked:** group 57, 16 maps (Oldale Town sign, Snowpoint Gym sign, a scene reusing
Mortar-style text). No warp or connection leads in; its only exit goes to Route 47 (56.25).

**Referenced but not built:** Sinnoh (Dawn, Rowan, Looker, Melissa, Team Galactic; the
"Twinleaf/Sandgem/Snowpoint" strings are only radio song-menu entries), Hoenn, Alola, Kalos,
Galar, Unova, Paldea, Orre. Hisui appears only through time-slip quests (Laventon, Alabaster Icelands).

## Possibly unfinished quests

Accepted but no matching completion line found: Curry Sauce's Request, Hide-and-Seek on the
Tundra, The Friend Who Didn't Show / The Missing Friend, Subduing the Fierce Pokémon. Most other
mismatches are naming variants. Check in the emulator.

## Caveats

- The review sheet's `map` column is the first map that references a string, so some text is
  attributed to the wrong place (Vermilion lines appear under Blackthorn).
- The reachability check ignored script-driven warps; "unlinked" maps may be reachable another way.
- `var 0x5120` (main story stage) is reused and not monotonic; it is not a progress meter.
