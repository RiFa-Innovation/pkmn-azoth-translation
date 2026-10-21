"""Assemble and link scripts/frontier_native.s for a given address.

    python3 scripts/frontier_native.py [--base 0x0203F800] [--out build/frontier/native.bin]

Prints the size and the entry points (fr_enter at +0, fr_leave at +4, fr_heal at +8; call with `callnative <base+off>|1`).
insert.py will link it at its free-pool address when the facility is wired in (milestone M5).
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build(base, out):
    src = os.path.join(ROOT, "scripts/frontier_native.s")
    obj = out + ".o"
    elf = out + ".elf"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.check_call(["arm-none-eabi-as", "-mcpu=arm7tdmi", src, "-o", obj])
    subprocess.check_call(["arm-none-eabi-ld", f"-Ttext={base:#x}", "-e", "_start", "-o", elf, obj])
    subprocess.check_call(["arm-none-eabi-objcopy", "-O", "binary", elf, out])
    syms = subprocess.check_output(["arm-none-eabi-nm", elf], text=True)
    return open(out, "rb").read(), syms


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=lambda x: int(x, 0), default=0x0203F800)
    ap.add_argument("--out", default=os.path.join(ROOT, "build/frontier/native.bin"))
    a = ap.parse_args()
    blob, syms = build(a.base, a.out)
    print(f"{len(blob)} bytes at {a.base:#x}")
    print(syms)
