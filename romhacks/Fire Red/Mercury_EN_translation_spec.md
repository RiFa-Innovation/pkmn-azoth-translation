# Pokémon Mercury (水银) 1.3.3 — Simplified Chinese → English Translation Spec

## 1. Objective

Produce an English-language build of the Chinese Fire Red hack
`Pokemon Mercury 1.3.3` distributed as `Pokemon Mercury 1.3.3.bps`, with all
in-game text (dialogue, menus, Pokémon/move/item names, dex entries, UI)
translated, and the hack otherwise functionally identical to the Chinese build.

## 2. Source-of-truth facts (measured from the .bps, no base ROM required)

These numbers come from parsing the BPS action stream directly, so they are
ground truth independent of any ROM.

| Fact | Value | Meaning |
|------|-------|---------|
| Patch format | BPS1 | `Floating IPS`/`flips` compatible |
| Source size | `0x1000000` (16 MiB) | Base = **Pokémon Fire Red (USA/Europe) 1.0/1.1**, unmodified |
| Target size | `0x2000000` (32 MiB) | Hack runs from an **expanded** 32 MiB ROM (standard for mature FR hacks) |
| BPS metadata | empty | No author/tool string to lean on |
| Base ROM identity (verified) | Fire Red (USA/Europe) **1.0**, `BPRE` rev `0` | CRC32 `0xDD88761C` == patch's embedded source CRC |
| Target CRC32 (verified) | `0x2FBC8C94` | Patched ROM reconstructed byte-exact and CRC-confirmed |
| Total actions | 2,959,261 | A raw machine diff of a rebuilt ROM, not a curated patch |
| New/modified bytes (TargetRead) | 5,860,529 (~5.6 MiB) | Volume actually changed vs base ROM |
| TargetRead segments | 922,804 (avg ~6.3 B) | Diff is extremely fragmented |
| SourceCopy / TargetCopy | 678k / 1,346k | Heavy reuse of base-ROM and already-written data |

### Verification record (2026-10-09)

- Base ROM `roms/Pokemon - FireRed Version (USA, Europe).gba` — 16 MiB, game code
  `BPRE`, revision `0`, CRC32 `0xDD88761C` — matches BPS source checksum.
- BPS applied (Python applier, verified against flips `libbps.cpp` semantics):
  output `roms/Pokemon Mercury 1.3.3 (patched).gba` — 32 MiB, CRC32
  `0x2FBC8C94` — matches BPS target checksum. Byte-exact.
- Note: shipped `flips.exe`/`flips-linux` do not run on Darwin arm64; the Python
  applier is CRC-verified and replaces them for tooling purposes.
- pokefirered decomp present at `utilities/pokefirered/` (charmap.txt, gbagfx,
  jsonproc, rsfont) — tools are source-only and must be built (`make`, `libpng`).

### Where the new data lives (per 64 KiB region)

- **0x0–0x500000**: sparse, small edits (code/pointers/early tables).
- **0x720000–0x840000**: dense block (~250 KiB new data), largest concentration.
- **0x900000–0xFF0000**: moderate, even ~5–12 KiB/region.
- **0x1000000–0x1FFFFFF (the expanded 16–32 MiB area)**: entirely new; dense,
  ~5–7 KiB uniform blocks per region. Uniform block sizes are the classic
  signature of **LZ77-compressed content** (maps/graphics/text).

### Evidence that text is NOT ASCII/GBK/UTF (corrected 2026-10-09)

Byte-level scans of the new-data stream show:

1. **No readable strings.** 54,962 "ASCII" runs found, every one garbage
   (`sO;3{`, `3U4DSE`, `oUjn`…).
2. A first-pass scan for GB2312/GBK pairs produced ~961k hits, but decoding the
   longest run yields semantically random characters (`奸嘀菡`, `晚嚓巽忡`), i.e.
   a **false positive** (binary data coincidentally forms valid GBK pairs).
3. UTF-16LE and UTF-8 scans are likewise garbage.

### Phase 0 — confirmed findings (from patched ROM, 2026-10-09)

- **Text is stored RAW, not LZ77.** Species/move/item name tables are plain byte
  arrays read directly from the ROM (verified by reading `gSpeciesNames`
  verbatim). Only graphics/maps are LZ77-compressed. (My earlier "LZ77 text"
  hypothesis was wrong — it was based on the flat histogram of graphics-heavy
  diff fragments.)
- **Encoding is a custom 2-byte font-index scheme.** Each Chinese character is a
  big-endian 2-byte index into the hack's custom font — NOT GBK/GB2312/UTF-8/
  UTF-16. Verified against `gSpeciesNames` (base `0x245EE0`, 11-byte stride,
  `name + 0xFF + 0x00` padding):
  - Bulbasaur 妙蛙种子 = `09 86 0D 44 10 A7 11 0B` → 妙=`09 86`, 蛙=`0D 44`, 种=`10 A7`, 子=`11 0B`.
  - Charizard 喷火龙 = `0A 44 05 7D 08 CD`; 火=`05 7D`, 龙=`08 CD` recur in Charmeleon/Charizard (deterministic per character).
  - Indices run ~`0x0000`–`0x11xx`, i.e. a ~4–8k-glyph custom font.
- **The vanilla Latin font is intact** (CORRECTED — an earlier "Latin font gone"
  claim was a false negative from searching the full 32 KiB blob). A–Z, a–z,
  0–9 and punctuation glyphs are all byte-identical to base. The hack modified
  only ~2% of the font region: some accented chars (`0x1B`–`0x1F`) and the kana
  block (`0x50`–`0x77`). **English text can be rendered with the stock 1-byte
  charmap + Latin font — no new font needs to be drawn.**
- **The CJK font is a GB2312-ordered subset, not stored in the vanilla font
  region.** Its glyph data lives elsewhere (expanded 16–32 MiB area, still to be
  located). The 2-byte code equals the character's **rank** among used characters
  sorted by GB2312 (verified: hack codes are monotonic in the GB2312 linear index
  across 妙蛙草花火龙喷恐小种子).
- **Vanilla Japanese font is untouched** (`japanese_normal.fwjpnfont` byte-identical).
- **Renderer font pointers are unchanged** — the hack still points at the vanilla
  font addresses; only the font *contents* (kana/accented glyphs) shifted slightly.
- **Table structures are preserved.** The hack kept vanilla pointer-table layouts
  and only swapped the string bytes (e.g. `SPECIES_NONE` "??????????" unchanged).

Open items still to resolve: (1) locate the CJK font glyph data and its format,
(2) build the full 2-byte charmap (index → character) via glyph-matching against
a reference GB2312 bitmap font, (3) enumerate all dialogue/script pointer tables
vs vanilla.

### Phase 0 — charmap & dumper (2026-10-09)

- **Glyph format is a compressed half-row lookup**, not raw bitmap
  (`DecompressGlyphTile`: each 8-pixel half-row is an 8-bit index into
  `sFontHalfRowLookupTable`/`sFontHalfRowOffsets`). Font-matching is therefore the
  hard path for building the charmap.
- **Charmap bootstrapped instead by cross-referencing the standard Chinese
  Pokémon names** (species names are the official translations). `scripts/dump_text.py`
  dumps the species-name table; `scripts/charmap.json` holds 315 code→char entries
  from species 1–251, verified against hand-read anchors (妙蛙种子, 喷火龙, …) with
  zero conflicts. Proof: 杰尼龟/波波/比比鸟/烈雀/皮卡丘/超梦 all decode correctly.
- **Table relocation:** the hack moved `gSpeciesNames` from `0x245EE0` (vanilla) to
  `0x141B350` (expanded area) and re-pointed the renderer. Note: at the new location,
  species 252+ (Hoenn) do **not** follow the 11-byte stride — Hoenn names appear to
  use a different/unfinished encoding (old table holds `?` placeholders there). To
  investigate before a complete species-name dump.
- Remaining for a full `strings.zh.json`: extend the charmap via move/item/ability
  names (also standard Chinese), then enumerate and dump every text table + map
  dialogue.

### Phase 1 — name tables & descriptions (2026-10-09)

- **Charmap grown to ~906 entries** (cleaned: 850 in font range `0x0000–0x1400`).
- **Name-table coverage**: species **100%** (381/381 — Hoenn resolved via the FR
  species-enum `+25` offset + exact `species.h` enum), moves **99%**, abilities
  **92%**, items **59%** (items use fan translations, e.g. 掌门球 for Master Ball).
- **Relocated addresses** (file offsets): `gSpeciesNames`→`0x141B350`,
  `gMoveNames`→`0x1D97378`, `gAbilityNames`→`0x1D8E858`; `gItems[].name` unmoved
  at `0x3DB028` (stride 44). See `scripts/TABLES.md`.
- **Descriptions are in-place, not relocated**: `gMoveDescriptionPointers` at
  `0x4886E8` (unchanged) → English strings overwritten with Chinese at `0x482834+`.
  Dumped 354 move descriptions into `strings.zh.json`. Text is a hybrid encoding:
  2-byte font-index (lead `0x01–0x14`) + 1-byte controls (`0xFA–0xFF`) + 1-byte
  punctuation. ~54% of description codes already mapped; the rest need a
  **Gen 3-specific Chinese source** (veekun's flavor text is later-gen and differs).
- Tools: `scripts/dump_text.py` (dumpers), `scripts/find_relocated.py`
  (vanilla→relocated address), `scripts/recon_lz77.py` (LZ77 scan).

Remaining Phase 1: `gStdStringPtrs`, dex entries, ability/item descriptions, and
map dialogue (script-embedded) — all located the same way (vanilla address →
`find_relocated.py` → dump). Descriptions/UI text need a Gen 3 Chinese reference
or a human reader for the residual charmap.

## 3. Complexity assessment

**Overall: HIGH (7/10).** Not because translation is hard, but because the
hack is a full binary rebuild whose text pipeline must be reverse-engineered
before any string can be touched. The hard 20% is tooling; the easy 80% is
human translation volume once tooling exists.

| Risk driver | Impact | Notes |
|-------------|--------|-------|
| Text engine is custom (confirmed) | Very high | Custom 2-byte font-index encoding; must map index→glyph before any string can be read |
| Text is RAW, not LZ77 (confirmed) | Low | Plain byte arrays in preserved tables — dump/rebuild is straightforward; only graphics are LZ77 |
| CJK font likely replaced the Latin font | High | If the font has no Latin glyphs, an English font must be added (biggest engineering risk) |
| Text volume | Medium | Unknown until dumped; a full hack = tens to hundreds of thousands of chars |
| Length changes | Medium | English strings must fit in fixed-size buffers/line widths; needs pointer-table rebuild |
| ROM expanded to 32 MiB | Low | Already handled by the patch; just preserve it |
| No decomp source | Medium | Binary-only; mapping to `pret/pokefirered` symbols is the accelerator |

### Hard dependency (cannot proceed without it)

The base **Pokémon Fire Red (U) 1.0** (or 1.1) 16 MiB ROM. The BPS references
base-ROM bytes via SourceRead/SourceCopy, so the target ROM cannot be
reconstructed without it. This is the single blocking resource.

## 4. Unknowns to resolve in Phase 0 (recon)

All of these require the reconstructed patched ROM; none are answerable from
the .bps alone.

1. **Text character encoding** — GB2312/GBK mapped through a custom font table,
   UTF-16, or a fully custom 1–2 byte table.
2. **Font format & glyph inventory** — does the CJK font still contain Latin
   (`A–Z`, `a–z`, `0–9`, punctuation)? If not, an English font is required.
3. **Text storage layout** — LZ77 block locations and the pointer table format
   that indexes dialogue/menu strings.
4. **Renderer** — VWF vs fixed-width, control-code semantics (`\n`, `\p` prompt,
   color, name/var substitution like `{PLAYER}`).
5. **Text volume & categories** — script dialogue, dex, move/ability/item/Pokémon
   names, UI labels, help system, credits.

## 5. Approach (phased)

### Phase 0 — Recon (produces the charmap + dump tool)
1. Acquire base ROM; apply BPS with `flips`; verify CRC against the patch.
2. Load the ROM against `pret/pokefirered` decomp symbol map (preferred) and/or
   Ghidra (ARM7TDMI, little-endian).
3. Locate the text renderer + font; dump the font glyphs and the charmap.
4. Write a **text dumper**: walk the pointer tables, LZ77-decompress each block,
   decode into Unicode. Deliverable: `strings.zh.json` (id → Chinese text) +
   `charmap.txt` + font bitmap dump.

### Phase 1 — Extraction & glossary
1. Dump all text to a catalog keyed by stable IDs.
2. Build a glossary (Pokémon names, moves, abilities, items, places) — reuse
   official English Fire Red names to stay consistent.
3. Produce `strings.en.json` (machine-assisted first pass).

### Phase 2 — Translation & editing
1. Human translation/review of every string (MT draft + human polish).
2. Track length constraints; flag overflow candidates early.

### Phase 3 — Reinsertion
1. If the font lacks Latin glyphs: add an English font (restore FR's Latin font
   or draw a new one) and adapt the renderer. **Highest-risk step.**
2. Rebuild the text blocks: encode English → custom charmap → LZ77-compress →
   write back with corrected pointers/lengths.
3. Emit a new `.bps` (or `.ips`) patch against the same base ROM.

### Phase 4 — QA
1. Playtest: no garbled glyphs, no overflow, no missing strings, no crashes.
2. Verify hack-specific content (new maps/story) reads correctly in English.

## 6. Resource checklist (what to bring)

**Required — cannot start:**
- [ ] Base ROM: Pokémon Fire Red (USA) 1.0/1.1, 16 MiB, unmodified
      (the BPS checksum identifies the exact revision; typically `1.0`).
- [ ] `flips` (Floating IPS) CLI, or any BPS1 applier.

**Recommended toolchain:**
- [ ] `pret/pokefirered` decomp (github.com/pret/pokefirered) — authoritative
      symbol map, charmap, `jsonproc` text format, `gbagfx`/`lz77` tools.
- [ ] A GBA-capable disassembler for the renderer: Ghidra (ARM7TDMI) or IDA.
- [ ] Python 3 (dumper/rebuilder scripts; `lz77` from pret or reimplemented).
- [ ] A hex editor (HxD / 010 / ImHex) for spot checks.

**People:**
- [ ] A Chinese→English translator (native-enough English; romhack genre aware).
- [ ] (Optional) a pixel-art font author, only if Latin glyphs are missing.

**Tool verdict — `morluto/rea` (REA):** conditionally useful, downstream.
REA orchestrates Ghidra/Hopper/IDA over MCP to give pseudocode/symbols/xrefs.
It is genuinely suited to Phase 0 step 2–3 (decompile the text renderer, find
the charmap and font), but:
- it needs the **reconstructed patched ROM**, so it is blocked until the base
  ROM arrives;
- for Fire Red specifically, `pokefirered` decomp usually answers 80% of the
  text-system questions faster than raw Ghidra — use REA only for the custom
  delta (CJK font + renderer) that decomp doesn't cover;
- it requires installing Ghidra/Hopper and wiring REA as an MCP server before
  it can be driven in-session.

## 7. Definition of done

- [ ] 100% of dumped strings translated (no untranslated Chinese remains).
- [ ] No garbled glyphs, no text overflow, no crashes in a full playthrough.
- [ ] Patch applies cleanly to the same base ROM and boots.
- [ ] Hack-specific story/content preserved semantically.
- [ ] Glossary consistency with official English Pokémon naming.

## 8. Risks / open questions

- **Encoding false start:** the ROM stores text LZ77-compressed; a charmap-only
  tool will fail. Decompress first.
- **Font gap:** if the CJK font removed Latin glyphs, Phase 3 font work is the
  single largest effort/risk.
- **Pointer/string-length:** English tends to be longer than Chinese per
  sentence; verify buffer limits before mass reinsertion.
- **License/redistribution:** base ROM and hack are not redistributable here;
  deliver a patch, not a ROM.
