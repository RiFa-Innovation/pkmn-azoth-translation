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

### Evidence that text is NOT plaintext in the ROM

Byte-level scans of the new-data stream show:

1. **No readable strings.** 54,962 "ASCII" runs found, every one garbage
   (`sO;3{`, `3U4DSE`, `oUjn`…). Nothing human-readable anywhere.
2. **Flat byte histogram.** In the dense 0x700000–0x850000 block the top bytes
   are `0x07, 0x00, 0xFF, 0x10, 0x01, 0x08, 0x20, 0x06` — a near-flat
   distribution dominated by low control bytes.
3. A first-pass scan for GB2312/GBK code pairs produced ~961k hits, but decoding
   the longest run yields semantically random characters (`奸嘀菡`, `晚嚓巽忡`),
   i.e. a **false positive**.

Conclusion: the modified content is **LZ77-compressed** (the native Fire Red
storage format for maps, graphics and text). You cannot hex-search the ROM for
text; every string must be decompressed before it is readable. The actual
character encoding/font is **undetermined** and can only be resolved after
reconstructing the patched ROM.

## 3. Complexity assessment

**Overall: HIGH (7/10).** Not because translation is hard, but because the
hack is a full binary rebuild whose text pipeline must be reverse-engineered
before any string can be touched. The hard 20% is tooling; the easy 80% is
human translation volume once tooling exists.

| Risk driver | Impact | Notes |
|-------------|--------|-------|
| Text engine is custom/unknown | Very high | Chinese FR hacks replace FR's font + renderer with a CJK font and a custom charmap; must be identified |
| Text is LZ77-compressed in-ROM | High | Needs a dump/rebuild toolchain, not hex editing |
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
