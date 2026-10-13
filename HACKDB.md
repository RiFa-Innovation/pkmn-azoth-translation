# HACKDB: queryable index of the ROM hack

`scripts/hackdb.py` builds `build/hackdb.sqlite` (gitignored, ~3 s) from the
original Chinese hack and answers compound questions, so triage starts with a
lookup instead of a new script. Hand-found facts live in
`data/hackdb_notes.json` (`hackdb.py note add ...`) and are merged on build.

```
python3 scripts/hackdb.py build [--rom build/Mercury_EN.gba]   # --rom = separate db for the EN build
python3 scripts/hackdb.py map 3.85        # header, connections, warps, coord/bg gates, objects, map scripts
python3 scripts/hackdb.py maps Route      # list/search maps (labels come from notes + data/map_names.json)
python3 scripts/hackdb.py var 0x5186      # setters/readers/gates, entry that reaches each, code literals, RAM addr
python3 scripts/hackdb.py flag 0x178B     # same, plus object-template flags
python3 scripts/hackdb.py text "Violet"   # zh/en text -> string -> script cmd -> map event that reaches it
python3 scripts/hackdb.py script ADDR     # disassembly (strings inlined, follows goto/call) + who reaches it
python3 scripts/hackdb.py who ADDR        # map events/map scripts that (transitively) reach a script or cmd
python3 scripts/hackdb.py whatis ADDR     # vanilla symbol, hack function, string, script cmd, event struct, notes
python3 scripts/hackdb.py names species 25 | names moves Tackle
python3 scripts/hackdb.py sql "select ..." | schema
```

Addresses take ROM form (`0x08AF433D`) or file offsets.

## What it indexes

| Table | Source | Notes |
|---|---|---|
| `maps`, `conns` | `gMapGroups` @ `0xB3B100`, map headers | 827 maps; group count = pointers until a non-ROM word |
| `events` | each map's events struct | kinds `obj` (24 B), `warp` (8 B), `coord` (16 B, CFRU: var/value gate), `bg` (12 B) |
| `mscripts` | map script table | tags 1..7 (ON_RESUME = 5, ON_TRANSITION = 3); tags 2/4 expand their (var, value, script) tables |
| `entries`, `cmds`, `edges`, `refs` | recursive descent from every event/map-script entry using `scrdis` opcode table | 96k commands; `refs` = semantic var/flag/special/native/item uses plus event gates |
| `desync` | unknown opcodes (CFRU 0xEA/0xEB...) | the walker stops there; those blocks are partial |
| `strings`, `names` | `text/zh.json` + `text/en/*` | `refs` are pointer-word sites; join to `cmds` by address |
| `funcs`, `lit` | `data/hack_code.json` | literal-pool words with their `ldr` sites and containing function |
| `notes` | `data/hackdb_notes.json` | `map:G.N`, `var:N`, `flag:N`, or an address |

## Facts it encodes (verified, see PLAYTEST/PROCESS for provenance)

- Hack var array is **not** at SaveBlock1+0x1000: RAM of var `v` =
  `0x2039374 + (v-0x4000)*2` (`gSaveBlock1Ptr` = 0x202552C).
- Coord events are 16 bytes `{x,y,elev,pad,var,value,pad,script}`; their gate
  never appears as a `compare` in scripts, which is why byte-scans missed it.
- Object `script` below `0x08000100` is a placeholder (`PLACEHOLDER` in `map`).
- Object struct: x/y at +4/+6 (pad byte at +3), movement +9, trainer +12, script +16, flag +20.
- Code reached only through function-pointer tables is absent from `funcs`;
  `whatis` says so and points at Ghidra (`get_functions address=<file offset>`,
  image base 0; inline Ghidra scripts are disabled in this setup).

## Limits

- Scripts not reachable from an event or map script (e.g. called by native code or a
  table) are absent from `cmds`; `script ADDR` still disassembles them live.
- Flag RAM addresses are not derived yet (only vars).
- Opcodes beyond vanilla FireRed (CFRU) end a walk; extend `script_table()`.
