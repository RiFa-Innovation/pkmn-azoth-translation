# Mercury (水银) 1.3.3 — translation process state

> Written 2026-10-09. Resume from here. Everything below is ground truth from the
> repo; see git log for checkpoints.

## Goal

Translate the Chinese Fire Red hack **Pokémon Mercury 1.3.3** to English.
Current phase: **completing the charmap automatically via font-glyph matching**
(no Chinese reader available).

## Files & resources

| Path | What |
|------|------|
| `roms/Pokemon - FireRed Version (USA, Europe).gba` | Base ROM, Fire Red US 1.0, CRC `0xDD88761C` |
| `roms/Pokemon Mercury 1.3.3 (patched).gba` | Patched ROM (32 MiB), CRC `0x2FBC8C94` |
| `romhacks/Fire Red/Pokemon Mercury 1.3.3.bps` | Input patch |
| `romhacks/Fire Red/Mercury_EN_translation_spec.md` | Full spec + all findings |
| `scripts/dump_text.py` | Dumpers (`dump_fixed_stride_table`, `CharMap`, …) |
| `scripts/find_relocated.py` | vanilla→relocated address (pointer-diff) |
| `scripts/recon_lz77.py` | LZ77 scanner |
| `scripts/match_font.py` | Font-matcher (WIP; `render_hack_glyph` + reference match) |
| `scripts/TABLES.md` | Address map of text tables |
| `scripts/charmap.json` | 906 code→char entries (850 in font range) |
| `scripts/strings.zh.json` | Dumped text (species/moves/items/abilities/move_descriptions) |
| `utilities/pokefirered/` | pret decomp; `gbagfx`/`jsonproc`/`rsfont` **built** |
| `/tmp/hzk16.bin` | HZK16 16×16 GB2312 bitmap font (267,616 B) |
| `/tmp/fonts/*.fw*font` | gbagfx-generated vanilla font refs |
| `/tmp/species_names.csv` etc. | veekun CSVs (language id 12 = zh-Hans) |

## Established facts (do not re-derive)

1. **Encoding**: text is a **2-byte font-index**, GB2312-ordered **subset**
   (~4,400 glyphs). Code = rank among *used* chars sorted by GB2312. NOT
   GBK/UTF-8/UTF-16. (Verified via species names.)
2. **Text is RAW**, not LZ77 (only graphics/maps are LZ77).
3. **Latin font is intact** — A–Z/a–z/0–9 unchanged → English renders with the
   stock 1-byte charmap + Latin font. No font-drawing needed.
4. **Name tables** (done): species **100%** (381), moves **99%**, abilities
   **92%**, items **59%** (items use fan translations → veekun mismatch).
5. **Move descriptions**: dumped 354, overwritten in-place at `0x482834`,
   pointer table `gMoveDescriptionPointers` at `0x4886E8` (unchanged). Hybrid
   encoding (2-byte lead `0x01–0x14` + 1-byte controls `0xFA–0xFF`).
6. **Relocated addresses** (see `scripts/TABLES.md`): species `0x141B350`
   (stride 11, Hoenn at species-enum +25 offset), moves `0x1D97378` (13),
   abilities `0x1D8E858` (13), items `0x3DB028` (unmoved, stride 44).
7. **HZK16 formula**: glyph offset for GB2312 char = `((L-0xA1)*94 + (T-0xA1))*32`
   (verified renders 妙/草/蛙 correctly).

## Current task — font matching (the charmap solution)

**Goal**: map every 2-byte code → Chinese char by rendering the hack's glyphs and
matching against HZK16. This completes the charmap with no human reader.

### Glyph format (vanilla half-row compressed) — CONFIRMED

- Glyph = **64 bytes = 64 half-row indices** (Latin-normal stride `0x20` u16 = 64 B).
- Each index byte → `sFontHalfRowOffsets[index]` → lookup index (0–80) →
  `sFontHalfRowLookupTable[lookup]` → 4 pixels (4 nibbles; **fg = nibble 1**).
- Layout: 4 tiles of 16 indices (8×8 each), order TL/TR/BL/BR; within a tile,
  `pos%16` → `row = (pos%16)//2`, `half = (pos%16)%2`, so 8 rows × 2 half-rows
  (4 px each). Assembled 16×16.
- `sFontHalfRowOffsets` (256 B) and the base-3 `LOOKUP` (81 entries) are already
  hardcoded in `scripts/match_font.py` (and were inline in the scan scripts).
- **Verified**: vanilla `A` at `0x1F3100 + 0xBB*64` renders as a clear "A".

### BLOCKER — CJK font base + stride not yet found

The CJK font is a **new** block in the expanded area (16–32 MiB); all vanilla
fonts are unchanged. Need its base address + stride to render glyphs.

Tried so far (all inconclusive):
1. Density-only scan (stride 32/64) → 171k false positives (weak criterion).
2. Reference-match scan vs **Hiragino** (vector) → noise, best score ~0.5.
3. Reference-match scan vs **HZK16** (stride 64) → 0 bases > 1.5.
4. Raw HZK16 byte search → 0 matches (font is **not** raw 1bpp).

### Next steps (in order)

1. **Disassembly** (definitive): disassemble the modified `DecompressGlyph_*`
   code (region `0x64000–0x6B000`; vanilla font pointers live at
   `0x64C4/0x658C/0x66EC/0x6920/0x6A8C`) to read the CJK font **base** and
   **stride/shift** constants.
   - `/usr/bin/objdump` has **no ARM/Thumb target** (confirmed) → write a
     minimal Python **Thumb-2** decoder: 16-bit `LDR literal` = `0x4xxx`
     (`Rd, [PC, #imm8*4]`), plus `LSL #imm` (`0x00xx`) to spot the stride
     shift; the 32-bit base lands in a nearby literal pool (look for
     `0x09xxxxxx` = expanded-area pointer). GBA is ARMv4T little-endian.
2. OR **half-row-compress HZK16** and search for the exact compressed 妙/草
   bytes (inverse of `sFontHalfRowOffsets`; pick first matching offset index).
3. Also worth trying **stride 32** half-row (16×16 1bpp → 32 half-row indices,
   2-px half-rows) — my stride-32 test earlier used wrong tile math.
4. Once base+stride known: render all glyphs → match vs HZK16 (Jaccard) →
   write full charmap → decode `strings.zh.json` 100%.

## Other remaining work (after charmap)

- Dump `gStdStringPtrs` (`src/script_menu.c:574`), dex entries
  (`src/data/pokemon/pokedex_text_fr.h`), ability/item descriptions, map dialogue
  (all via `find_relocated.py` + `TABLES.md` method).
- Items/descriptions need a **Gen-3-specific Chinese source** or a reader (fan
  translations, e.g. 掌门球 for Master Ball) — font-matching bypasses this.

## Git checkpoints

```
4facf4e move descriptions dumped, hybrid encoding
d675ca1 find_relocated tool + TABLES.md
e7463be 906-char charmap, species 100%, name tables
b348b8c charmap 813, 4 name tables
3a57fe0 cleanup
f41735f dumper + charmap (Phase 0)
8b61cd6 Latin font intact, CJK font GB2312-ordered
cbc9fa1 custom 2-byte encoding, text raw
f51f09c verified ROMs + toolchain + spec
```
