# Pokémon Mercury — English translation

[![Join the Discord](https://img.shields.io/badge/Discord-Join_the_community-5865F2?logo=discord&logoColor=white)](https://discord.gg/pWnawqhT5C)
[![Support on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/river8)

Chat, ask questions and share screenshots on **[Discord](https://discord.gg/pWnawqhT5C)**. Bug reports still go on [GitHub Issues](../../issues/new/choose) so they can be tracked.

> **Optional.** The patch is and stays free. The Ko-fi link only helps me spend
> more time on this translation. It is not for the original Mercury hack or its
> authors, and nothing here is paid or gated.

A from-scratch English translation of **Pokémon Mercury (口袋妖怪 水银) 1.3.3**,
a Chinese FireRed ROM hack that remakes Johto on top of the Complete FireRed
Upgrade (CFRU) engine. No other English patch for this hack exists.

> **Status: beta.** All pointer-reachable text (≈20,300 strings) is translated
> and the game is playable from boot through Johto. Translations are still being
> polished and play-tested; see [Issues](../../issues) and
> [`PLAYTEST.md`](PLAYTEST.md).

## 🐞 Found a bug? Report it here

**[Open an issue →](../../issues/new/choose)** · [Known issues](../../issues?q=is%3Aissue+is%3Aopen+label%3Abug)

Crashes, freezes, garbled screens, Chinese text that's still showing, text
running out of its box: please report them all. Check the
[open issues](../../issues) first, and add a comment if yours is already there.
The most helpful reports include:

- the **patch version** (e.g. `beta-3`) and your **emulator** (mGBA, myBoy…),
- **where** it happened and what you pressed,
- a **screenshot**,
- for crashes, your **`.sav` file** from just before it happens (an in-game
  save, not an emulator save state; save states break between patch versions).

## Download and patch

This repository contains **no ROMs**. You need your own clean copy of
FireRed and apply the patch from the [latest release](../../releases/latest).

| Base ROM | Value |
|---|---|
| Game | Pokémon - FireRed Version (USA, Europe), rev 1.0 (`BPRE`) |
| CRC32 | `DD88761C` |
| SHA-1 | `41cb23d8dccc8ebd7c649cd8fbb58eeace6e2fdc` |

The common **"Squirrels" dump (#1636) is FireRed USA v1.0 and works**.
FireRed **v1.1** does not. The patch stores the base ROM's CRC32, so BPS
patchers refuse a ROM that doesn't match instead of producing a broken game.

The patch is a **BPS** file that applies to *clean FireRed directly*. You do
not need to apply the Chinese Mercury patch first. Use any BPS patcher:

- [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/) (browser)
- [Floating IPS (flips)](https://github.com/Alcaro/Flips)
- or this repo: `python3 scripts/bps.py apply <FireRed.gba> <patch.bps> <out.gba>`

Play on mGBA (recommended). The patched ROM is 32 MB.

## How it works

The hack stores its text in a custom double-byte encoding, reuses FireRed's
memory in ways the vanilla decomp doesn't describe, and draws some text as
graphics. The pipeline below rebuilds an English ROM from the Chinese hack and
emits a BPS patch against clean FireRed.

```
python3 scripts/dump_all.py          # Chinese ROM -> text/zh.json (strings + fixed tables)
python3 scripts/translate_tables.py  # name tables via official names + manual overrides
python3 scripts/insert.py            # -> build/Mercury_EN.gba + build/Mercury_EN.bps
```

### Methods

1. **Encoding, reverse-engineered from the glyph hook.** Disassembling the
   hack's CJK glyph routine showed that hanzi are 2 bytes (lead `0x01–0x1E`,
   trail `0x00–0xF6`) indexing the GB2312 hanzi in order. Everything else is
   FireRed's own charset. No charmap file is needed
   ([`scripts/mercury_text.py`](scripts/mercury_text.py)).
2. **Text discovery by pointer scan and code map.** Strings are found by
   scanning for pointers. Those pointers are trusted only in pointer tables,
   after script opcodes (`loadpointer`, `message`, `trainerbattle`), in CFRU
   battle-string loads, or as literal-pool words. A recursive Thumb
   disassembly of the hack's code ([`scripts/hackmap.py`](scripts/hackmap.py),
   `data/hack_code.json`) plus the pokefirered symbol map
   ([`scripts/frmap.py`](scripts/frmap.py), `data/fr_map.json`) keeps
   instructions and GCC section anchors from being mistaken for pointers.
3. **Translation memory.** `text/en/strings*.json` maps each Chinese string to
   English, so re-dumps never lose work. Official English is recovered where the
   hack reused FireRed's own text ([`scripts/vanilla_align.py`](scripts/vanilla_align.py)).
   Name tables use official names from veekun's data (`data/ref/*.csv`).
   Character and place names are made consistent with `text/en/name_canon.json`.
4. **Insertion.** English is written in place when it fits. Otherwise it is
   relocated into free space (including recycled Chinese originals) and every
   trusted pointer is repointed. Text is wrapped to each window's pixel width
   using the hack's 6 px Latin font. Per-window limits live in
   `text/en/width_override.json`, and boxes that can't scroll get a hard line
   cap. Strings the code reaches only by base+offset are patched in place
   (`text/en/anchored.json`, `manual_strings.json`) or relocated with Thumb
   patches (`code_text.json`).
5. **Graphics text.** The title logo, cut-in captions, menu headers and buttons
   are redrawn: each tileset/tilemap is located from a VRAM dump, English is
   drawn in the game's own font, and the result is LZ77-recompressed and
   relocated (`scripts/vram.py`, `gfx.py`, `gfx_text.py`, `logo.py`,
   `gfx/*.json`).
6. **Patch.** [`scripts/bps.py`](scripts/bps.py) is a minimal BPS
   encoder/decoder. Every build is checked by applying the patch to clean
   FireRed and comparing the result byte for byte.
7. **Emulator play-testing.** A headless mGBA with a Lua JSON-RPC bridge is
   driven from Python ([`scripts/emu.py`](scripts/emu.py),
   [`scripts/play.py`](scripts/play.py)). It handles input, save states,
   screenshots, RAM reads and pathfinding, so every screen can be checked and
   regressions reproduced. Findings are logged in [`PLAYTEST.md`](PLAYTEST.md).

More detail: [`PROCESS.md`](PROCESS.md) (pipeline and established facts),
[`EMULATOR.md`](EMULATOR.md) (emulator setup), [`scripts/TABLES.md`](scripts/TABLES.md).

## Libraries and tools

**In this repository** (all original code, Python 3):

| Path | Purpose |
|---|---|
| `scripts/mercury_text.py` | text codec: decode hack text, encode and wrap English |
| `scripts/dump_all.py`, `layout.py`, `anchored.py` | text discovery and window-width layout |
| `scripts/insert.py` | build the English ROM and the BPS patch |
| `scripts/bps.py` | BPS create/apply |
| `scripts/hackmap.py`, `frmap.py` | code and ROM structure maps |
| `scripts/tm_batch.py`, `name_fix.py`, `translate_tables.py`, `vanilla_align.py` | translation memory tooling |
| `scripts/gfx.py`, `gfx_text.py`, `logo.py`, `sprtext.py`, `typeicons.py`, `vram.py` | graphics text |
| `scripts/emu.py`, `play.py` | emulator driver |
| `data/naming_dispatch.s` | hand-written Thumb patch (naming-screen dispatcher) |

**Python packages** (`pip install numpy pillow capstone`):

| Package | Used for |
|---|---|
| [NumPy](https://numpy.org/) | fast whole-ROM scans (`dump_all.py`, `hackmap.py`) |
| [Pillow](https://python-pillow.org/) | graphics text, screenshots, logo |
| [Capstone](https://www.capstone-engine.org/) | Thumb disassembly (`hackmap.py`), only needed to rebuild the code map |

**External tools** (not vendored; fetch into the gitignored `utilities/` when needed):

| Tool | Used for |
|---|---|
| [pret/pokefirered](https://github.com/pret/pokefirered) + [pret/agbcc](https://github.com/pret/agbcc) | FireRed symbol map and charmap (`frmap.py`, `mercury_text.py`) |
| [mGBA](https://github.com/mgba-emu/mgba) (`mgba-headless`, small local patch, see `EMULATOR.md`) | scripted play-testing |
| [dmang-dev/mcp-mgba](https://github.com/dmang-dev/mcp-mgba) (`lua/bridge.lua`) | JSON-RPC bridge into mGBA |
| arm-none-eabi binutils | assembling Thumb patches |
| [Floating IPS](https://github.com/Alcaro/Flips) | optional, cross-checking patches |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports with a screenshot and where
in the game it happened are very welcome.

## Legal

Pokémon is © Nintendo / Creatures Inc. / GAME FREAK inc. Pokémon Mercury is the
work of its original Chinese authors. This is an unofficial fan translation,
not affiliated with or endorsed by any of them. **No ROMs are distributed.** The
patch contains only the differences needed to produce the translated game from
a FireRed ROM you legally own.
