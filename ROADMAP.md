# Roadmap: finishing the story with what already exists

Goal: maximize species and regions inside the fixed 32 MB GBA ROM by reusing built
assets, and give Chapter 2 an ending (Mt. Silver and Red first). Story state and open
threads are in `STORY.md`. Numbers below were measured on 2026-10-20 from
`roms/Pokemon Mercury 1.3.3 (patched).gba` and `build/Mercury_EN.gba`; anything marked
"estimate" has not been verified in the emulator.

## 1. Hard limits

- ROM is exactly 32 MB (the GBA maximum) and its last used byte is `0x1FFFFC0`. No growth.
- Free space inside it: English build has 0.80 MB of 0xFF runs >= 256 B (original hack: 1.55 MB;
  the English text took most of the difference). `insert.py` reports `free_after` = 0.69 MB.
- Map-name ids: the hack uses 143..221 (one-byte field, so ~34 left, estimate).
- Map groups: 58 used (u8), maps per group are u8. Not a constraint.

## 2. Where space can come from (measured)

| Pool | Size | Risk | Notes |
|---|---|---|---|
| CJK glyph fonts | up to ~0.87 MB (2 x 6,763 glyphs x 64 B at `0x7D0000` normal, `0x840000` small) | Medium | English strings contain 0 hanzi, but leftover untranslated Chinese (#11, undumped strings) would render as garbage. Index = GB2312 rank, so only contiguous tails are freeable without patching the glyph hook (`0x0820F658`). Plan: trace which glyph addresses are read during a full playthrough (`watch_read`), then free the unread tails (level-2 hanzi, ranks >= 3,755 = ~385 KB for both fonts) first. |
| Dead/orphan maps | ~0.05-0.2 MB | Low | 93 maps with no inbound warp (script warps ignored, so verify each); 4 tilesets used only by them (~52 KB). Many are Sevii/Navel Rock/vanilla stubs. Prefer re-linking over deleting. |
| Species sprites | up to 1.47 MB (front 0.66 MB + back 0.80 MB for 818 species that no wild table or trainer party uses; plus icons ~1 KB each) | High | **Not recommended** since the goal is max species. These 818 include evolutions, gifts and event species the scan cannot see. Keep this as an emergency reserve only. |
| English text | unknown | Low | English text relocated into freed Chinese space and consumed most of it (~1.6 MB). Tightening only helps if we must. |

Realistic budget without touching species: ~0.7 MB now + fonts (~0.4-0.87 MB) + orphans (~0.1 MB)
= ~1.2-1.7 MB.

## 3. What a region costs (so reuse is the strategy)

- Average existing map: 1.5 KB blockdata (all 827 maps = 1.24 MB). The 131 maps of the Cliffside area
  total 218 KB of blockdata.
- A new map header that points at an **existing layout and tilesets** costs tens of bytes plus its
  events and scripts. Copying a layout to edit it costs width x height x 2 B (a 40x40 map = 3.2 KB).
- Expensive items: new tilesets (graphics 2-7 KB compressed + 10 KB metatiles + attributes each),
  new NPC sprites, new music, and text.
- Estimate: a 30-map area that reuses tilesets costs ~100-250 KB. So **four to six small areas are plausible**
  if they reuse, not the "one or two" I first said.

Reusable inventory (layout size / tileset):

- Caves: Seabreak Cave (8 maps, 16x16 to 40x56), Union Cave (9), Dark Cave (66x52), Johto Mine (70x50),
  Cerulean Cave (3 maps, `1.72`-`1.74`, reachable from Cerulean City), Victory Road (`1.39`-`1.41`, `53.8`-`53.10`).
- Snow/summit: Alabaster Icelands (`52.23` 64x66, `52.24` 36x118), Ice Path (19 maps of 11x11).
- Volcanic: Silent Hill (10 maps), Dragon's Den (5).
- Navel Rock (9 maps incl. a 30x100 tall map, `2.55`): vanilla ticket island, unlinked.
- Group 57: 16 unlinked maps (town interiors with objects), exit already wired to Route 47 (`56.25`).

## 4. Species policy

Keep all 1,445. Do not drop sprites. Per-species cost (measured): front ~0.8 KB + back ~1.1 KB compressed,
palette, 1 KB icon, dex text. Wild tables reference ~293 species and trainer parties ~430 (union 478),
so most species are reachable only through evolution, gifts or events. New content should **use** the unused
ones (Mt. Silver spawns, Red's team, gifts, Navel Rock) rather than add sprites. A reachability audit
(evolution table, `givemon`/`setwildbattle`/trade commands, egg groups) is step 1 below.

## 5. Mt. Silver (first deliverable)

Already wired in the ROM:
- Region 205 "Mt. Silver" and 204 "Route 28" exist in the map-name table with **zero maps**.
- Map `55.1` (the Route 26 gate) has coord events (`0x087BE5AF`) and an NPC (`0x087BE6F7`) whose dialogue is
  "Ahead is… Mt. Silver, where frighteningly strong Pokémon live. You'd better not go there!" That is the
  entrance hook; today it only turns you back.
- Route 27 (`3.81`) and Route 26 (`3.106`) connect to each other and nothing else eastward.

Proposed build (all by reuse):
1. **Route 28**: 1-2 maps reusing an existing route tileset, linked from `3.106` or the gate.
2. **Base**: Pokémon Center interior (copy of an existing center layout).
3. **Mountain floors (4-6 maps)**: reuse Cerulean Cave / Victory Road / Seabreak layouts and cave tilesets.
   Copy-and-edit only where the geometry must differ (~2-4 KB each).
4. **Summit**: reuse the Alabaster Icelands snow tileset; one small map for **Red**.
5. **Red**: needs a new trainer entry (the trainer table has no Red; slot reuse or table extension - pointer risk,
   see `CLAUDE.md`), a sprite from the extended object-graphics table (`0x08961600`), a script, and a team.
6. **Items and spawns**: item balls from existing item ids; wild table entries pointing at under-used species
   (the 818 species not in any table are the pool). Gate: all 8 Johto badges + Kanto badges as authored.
7. Hook Chapter 2: replace the "don't go" NPC with a gated script, add a Mt. Silver quest line using the
   open threads (Archer's rainbow badge, the Rainbow Stone shards, Silver).

Estimated cost: 10-14 maps x ~3 KB + events/scripts ~20 KB + 1 trainer sprite ~2 KB = ~60-90 KB.

## 6. Next regions (after Mt. Silver, all reuse-first)

| Candidate | Reuses | Narrative hook |
|---|---|---|
| Navel Rock | 9 vanilla maps already in ROM | Ashida's Mystic Ticket (already given) |
| Group 57 town | 16 built maps, wired to Route 47 | Hoenn/Sinnoh-flavored "Oldale" town; Cliffside's Hoenn roots |
| Route 50/Silent Hill, Far Shore bridge | Existing maps, gated by "under construction" text | Un-gate with story flags |
| Safari Zone, Pokéathlon/Interaction Plaza, Battle Tower, Frontier | Maps exist or are named | Optional post-game |

## 7. Work order

1. **Measure**: finish the species reachability audit; instrument font reads over a playthrough; list free runs
   with sizes (`insert.py` pool dump). Output: a real byte budget.
2. **Playthrough** to the Chapter 2 end (Elm -> Indigo -> Mom/Ashida) to confirm what is the last authored beat.
3. **Prototype Route 28 + one Mt. Silver floor** with a script-driven warp, verify in the emulator
   (`EMULATOR.md`), rebuild with `insert.py`, confirm the BPS round-trip.
4. Build the rest of Mt. Silver, then Red.
5. Wire the story threads (`STORY.md`) through quests/flags; reclaim space only as the budget demands.

## 8. Risks

- Pointer trust (`CLAUDE.md`): new map/trainer table entries must not collide with the free-space pool;
  `referenced_ff` protects live FF runs.
- Placeholder script pointers and `goto` operands; null new events explicitly.
- Map-edit tooling: we have readers and a text/gfx inserter but no map writer yet. A map-header/layout/event
  writer is the main tool to build (it can live in `scripts/`), and the BPS pipeline must keep the clean-ROM
  byte-identical check.
- Save compatibility: new flags/vars must stay inside the hack's own var/flag arrays.
