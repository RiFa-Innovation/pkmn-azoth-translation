# Pokémon Mercury — text table address map

Vanilla (Fire Red US 1.0) → relocated (patched) addresses for every text table
found so far. Relocated addresses are file offsets (ROM address minus 0x08000000).

| Table | Vanilla | Relocated | Stride / structure | Status |
|-------|---------|-----------|--------------------|--------|
| `gSpeciesNames` | `0x245EE0` | `0x141B350` | `[][11]`, species enum (Hoenn at +25) | ✅ 100% |
| `gMoveNames` | `0x247094` | `0x1D97378` | `[][13]` | ✅ 99% |
| `gAbilityNames` | `0x24FC40` | `0x1D8E858` | `[][13]` | ✅ 92% |
| `gItems[].name` | `0x3DB028` | *(unmoved)* | `struct` stride 44, name 14 B | ⚠️ 59% (fan names) |

Remaining (not yet located/dumped):

| Table | Decomp source | Structure |
|-------|---------------|-----------|
| `gMoveDescriptionPointers` | `src/move_descriptions.c:359` | `const u8*[354]` → null-terminated |
| `gAbilityDescriptionPointers` | *(in decomp)* | pointer table |
| item descriptions | `src/data/items.json` | via `gItems[].description` |
| dex entries (species) | `src/data/pokemon/pokedex_text_fr.h` | pointer table |
| `gStdStringPtrs` | `src/script_menu.c:574` | `const u8*[]` → null-terminated |
| map dialogue | `data/maps/*/text.inc` | script-embedded |

Method: `scripts/find_relocated.py <vanilla-address>` reports the relocated
address; then dump + cross-reference (descriptions/std strings are standard
Chinese, so the same veekun-name technique applies).

Note: FR is bilingual — English and Japanese copies of descriptions coexist
(English near `0x482834`, Japanese pointer table at `0x482820` → `0x47xxxx`).
Disambiguate the English table before dumping.
