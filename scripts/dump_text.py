"""Phase 0 dumper: extract text from the patched Mercury ROM.

Text is stored RAW as big-endian 2-byte font indices (GB2312-ordered subset).
This module dumps named tables (species/move/item names, …) into a
`{table: {index: [codes...]}}` structure, and decodes them via a charmap.

The charmap (code -> Chinese char) is bootstrapped by cross-referencing the
standard Chinese Pokémon translations (species/move/item names), not by
font-matching. Anchors verified by hand from the patched ROM are seeded below.
"""
import json
import struct
from collections import OrderedDict


# Verified anchor charmap: 2-byte code (big-endian int) -> char
# (from Pokemon Mercury species names, confirmed against standard CN names)
ANCHOR_CHARMAP = {
    0x0986: "妙", 0x0D44: "蛙", 0x10A7: "种", 0x110B: "子",
    0x0201: "草", 0x0535: "花", 0x057D: "火", 0x08CD: "龙",
    0x0A44: "喷", 0x07E4: "恐", 0x0E2C: "小",
}


class CharMap:
    def __init__(self, mapping=None):
        self.map = dict(mapping or {})
        self.map.update(ANCHOR_CHARMAP)

    def decode(self, codes):
        return "".join(self.map.get(c, f"{{{c:04X}}}") for c in codes)

    def to_json(self):
        return {f"{k:04X}": v for k, v in sorted(self.map.items())}


def dump_fixed_stride_table(rom, base, count, stride=11):
    """Dump a fixed-stride name table (name bytes + 0xFF terminator + padding)."""
    entries = []
    for i in range(count):
        chunk = rom[base + i * stride: base + (i + 1) * stride]
        # read 2-byte codes until 0xFF terminator
        codes = []
        j = 0
        while j + 1 < len(chunk):
            if chunk[j] == 0xFF:
                break
            codes.append((chunk[j] << 8) | chunk[j + 1])
            j += 2
        entries.append(codes)
    return entries


def dump_species_names(rom):
    """Species names: 386 + 1 (SPECIES_NONE) entries, 11-byte stride.
    The hack moved the active table to 0x141B350 (vanilla: 0x245EE0)."""
    return dump_fixed_stride_table(rom, 0x141B350, 387, 11)


if __name__ == "__main__":
    import sys
    rom_path = sys.argv[1] if len(sys.argv) > 1 else "roms/Pokemon Mercury 1.3.3 (patched).gba"
    rom = open(rom_path, "rb").read()
    cm = CharMap()

    species = dump_species_names(rom)
    print("=== species names (first 30), decoded with anchor charmap ===")
    for i, codes in enumerate(species[:30]):
        decoded = cm.decode(codes)
        raw = " ".join(f"{c:04X}" for c in codes)
        print(f"  [{i:3d}] {decoded:12s}  {raw}")

    # unique codes across the table (charset coverage)
    all_codes = sorted({c for entry in species for c in entry})
    print(f"\ntotal unique 2-byte codes in species names: {len(all_codes)}")
    known = sum(1 for c in all_codes if c in cm.map)
    print(f"already decoded by anchors: {known}/{len(all_codes)}")
