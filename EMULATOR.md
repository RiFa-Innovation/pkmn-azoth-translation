# Emulator test setup — progress update (2026-10-10, checkpoint 14)

Resume point for driving the translated ROM in a scriptable emulator to verify
the open risks (stale description-tail pointers, window widths, ¥ glyph).

## Where the project stands

- **Translation is NOT done.** The first emulator run showed untranslated
  text, which led to three dump bugs (see `PROCESS.md` §Resume point). After
  the fix: 12,234/19,776 strings (~37% of hanzi) translated.
- Verified on screen: the main menu ("New Game", "Settings") renders in
  English with the stock Latin font. The title logo and the character-select
  prompt are Chinese **graphics**.

## What's now installed (all under `utilities/`, gitignored)

| Path | What |
|------|------|
| `utilities/mgba/` | mGBA source, built → `build/mgba-headless` |
| `utilities/mcp-mgba/` | `dmang-dev/mcp-mgba` MCP server (`dist/` built) + `lua/bridge.lua` |
| `scripts/emu.py` | Python client: connect to the bridge, read/write mem, press buttons, screenshot, scan EWRAM |

Homebrew packages added: `mgba` (Qt GUI — not used), `cmake`, `sdl2`, `libpng`,
`libzip`, `sqlite` (`lua` was already present).

**Local mGBA patch (required for screenshots):** stock `headless-main.c`
never calls `setVideoBuffer`, so `emu:screenshot()` reads a NULL framebuffer
and the process dies (connection reset). `utilities/mgba/src/platform/
headless-main.c` now gives the core a static 256×256 buffer right after
`core->init(core)`; rebuild with `make -C utilities/mgba/build mgba-headless`.
`utilities/` is gitignored, so re-apply this if mGBA is re-cloned.

`mgba-headless` was built from source because the brew `mgba` formula ships
only the Qt GUI, which has no headless/CLI script-loading path. `mgba-headless`
supports `--script FILE` (loads a Lua script at start) and runs with no display.

## How to run the emulator

```bash
cd utilities/mcp-mgba/lua && exec ../../mgba/build/mgba-headless -l 0 \
    --script bridge.lua ../../../build/Mercury_EN.gba
```

- `bridge.lua` opens a **newline-delimited JSON-RPC** server on
  `127.0.0.1:8765`. It is currently running as a service named `mgba`
  (`proc://mgba`); restart with `-l 0` to suppress the BIOS/DMA log spam.
- Request: `{"method": "...", "params": {...}, "id": 1}` + `\n`.
  Reply: `{"id":1,"result":...}` or `{"id":1,"error":{...}}` + `\n`.
- Methods: `ping`, `get_info`, `read8/16/32`, `read_range` (≤4096 bytes),
  `write8/16/32`, `write_range`, `press_buttons`, `screenshot`, `save_state`,
  `load_state`, `reset`, `advance_frames`.
- `read_range` is capped at **4096 bytes/call** (read EWRAM in chunks).
- `mgba-headless` is missing `frameAdvance`/`pause`/`unpause` (headless build);
  use `step`/`runFrame`/`reset`, or just run it free and read memory.
- Verified live: `ping`→pong; `get_info`→ game code **BPRE**, title
  "POKEMON FIRE"; `read_range`/`setKeys`/`screenshot`/`save_state` available.

## Critical finding — FR text is NOT ASCII

The English text in the ROM (and therefore in EWRAM at runtime) uses Fire
Red's own 1-byte charset, not ASCII:

| Chars | Bytes |
|-------|-------|
| `A`–`Z` | `0xBB`–`0xD4` |
| `a`–`z` | `0xD5`–`0xEE` |
| `0`–`9` | `0xA1`–`0xAA` |
| space | `0x00` |
| `é` | `0x1B` |
| newline | `0xFE` |
| terminator | `0xFF` |
| control | `0xF7`–`0xFD` (and `0xFC` + args) |

`mercury_text.decode_vanilla(bytes, off)` decodes this (the `VANILLA`
table); `scripts/emu.py` `scan_ewram` anchors on letter bytes `0xBB–0xEE`.

## `scripts/emu.py` usage

```bash
python3 -m scripts.emu info                       # frame, game code
python3 -m scripts.emu drive "Start A A" 60 s.png  # press each, wait 60 frames, screenshot
python3 -m scripts.emu text                        # FR-charset text in EWRAM
python3 -m scripts.emu read 02021000 100           # hex dump
```

The bridge's `press_buttons` params are `frames`/`release_frames` (an earlier
`emu.py` sent `hold`/`release`, which were silently ignored). Screenshot paths
must be absolute (the bridge's cwd is `utilities/mcp-mgba/lua`).

## Next steps (to continue)

0. Translation batches come first (`PROCESS.md`). Emulator checks below are
   still valid for the parts already translated.
1. ~~Fix `scan_ewram`~~ (done).
2. Drive the game to a text message (title screen → press Start/A → main menu
   → New Game intro). Re-run `python3 -m scripts.emu text` to find the message
   text buffer address in EWRAM (expect it near `0x0202xxxx`/`0x0203xxxx`).
3. Confirm on-screen text reads back as the expected English translation.
4. Verify the open risks in order:
   - Pokédex entry → flip to page 2 → confirm the stale-tail bug (page 2
     Chinese). Move description / battle message same check.
   - Bag/Summary/OPTION/menu screens → width overflow.
   - Trainer battle → name banner (11-char field).
   - Poké Mart → `¥` glyph.
5. Optional: register `mcp-mgba` (`node utilities/mcp-mgba/dist/index.js`) as an
   omp MCP server; not required — drive via TCP directly (`scripts/emu.py`).

## Loading a save (opt-in)

`mgba-headless` is patched (gitignored `utilities/mgba`, see `headless-main.c`,
search `rht:`) to load `ROM.sav` next to the ROM only when `RHT_LOAD_SAVE=1`,
so scripted runs never write to a player's save. Copy the ROM and save to a
scratch folder first. Playtest saves are backed up in `saves/` (gitignored).
