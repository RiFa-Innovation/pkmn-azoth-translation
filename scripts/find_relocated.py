"""Find the relocated address of a vanilla ROM data table in the patched ROM.

The hack relocates data tables into the expanded 16-32 MiB area and re-points
the code. Given a vanilla table address (base ROM, 0x08xxxxxx), this finds every
32-bit pointer reference to it and reports the value at the same code location
in the patched ROM (the new, relocated address).

Usage:
    python3 scripts/find_relocated.py 0x08247094        # gMoveNames
    python3 scripts/find_relocated.py 0x08245EE0        # gSpeciesNames
"""
import struct
import sys

BASE = "roms/Pokemon - FireRed Version (USA, Europe).gba"
PATCHED = "roms/Pokemon Mercury 1.3.3 (patched).gba"


def find_refs(base, addr):
    ptr = struct.pack("<I", addr)
    offs = []
    i = base.find(ptr)
    while i != -1:
        offs.append(i)
        i = base.find(ptr, i + 1)
    return offs


def main():
    for arg in sys.argv[1:]:
        addr = int(arg, 16)
        base = open(BASE, "rb").read()
        pat = open(PATCHED, "rb").read()
        refs = find_refs(base, addr)
        print(f"vanilla 0x{addr:08X}: {len(refs)} pointer ref(s)")
        seen = {}
        for r in refs:
            pv = struct.unpack("<I", pat[r:r + 4])[0]
            seen.setdefault(pv, []).append(r)
        for pv, locs in sorted(seen.items()):
            locs_str = ",".join(f"0x{l:07X}" for l in locs[:4])
            print(f"  -> relocated {pv:#010x}  (file 0x{pv-0x08000000:07X})  at {locs_str}")


if __name__ == "__main__":
    main()
