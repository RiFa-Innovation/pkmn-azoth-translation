"""Assemble, compile and link the Spectrum Frontier natives for a given address.

    python3 scripts/frontier_native.py [--base 0x0203F900] [--sets 0x08xxxxxx] [--out build/frontier/native.bin]

Sources: scripts/native/frontier_entry.s (entry table), scripts/frontier_native.s (fr_enter / fr_leave / fr_heal),
scripts/native/frontier_gen.c (fr_gen_opponent), scripts/frontier_start.s (fr_start_battle).
Entry points (callnative <base + off>|1): +0 fr_enter, +4 fr_leave, +8 fr_heal, +12 fr_gen_opponent, +16 fr_start_battle.
`--sets` is the ROM address of the packed set table (build/frontier/sets.bin); insert.py links it at its free-pool address (milestone M5).
"""
import argparse
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFLAGS = ["-mcpu=arm7tdmi", "-mthumb", "-Os", "-ffreestanding", "-fno-builtin", "-fno-strict-aliasing", "-fno-stack-protector", "-fno-pic",
          "-fno-asynchronous-unwind-tables", "-fno-unwind-tables", "-fno-tree-loop-distribute-patterns", "-Wall", "-Wextra"]


def build(base, out, sets=0x08F00000, start_flags="0x108"):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    objs = []
    for name, cmd in (
        ("entry", ["arm-none-eabi-as", "-mcpu=arm7tdmi", f"{ROOT}/scripts/native/frontier_entry.s"]),
        ("native", ["arm-none-eabi-as", "-mcpu=arm7tdmi", f"{ROOT}/scripts/frontier_native.s"]),
        ("gen", ["arm-none-eabi-gcc", *CFLAGS, "-c", f"{ROOT}/scripts/native/frontier_gen.c"]),
        ("start", ["arm-none-eabi-as", "-mcpu=arm7tdmi", "--defsym", f"START_FLAGS={start_flags}", f"{ROOT}/scripts/frontier_start.s"]),
    ):
        obj = f"{out}.{name}.o"
        subprocess.check_call(cmd + ["-o", obj])
        objs.append(obj)
    elf = out + ".elf"
    subprocess.check_call(["arm-none-eabi-ld", f"-Ttext={base:#x}", "-e", "_start", f"--defsym=fr_sets={sets:#x}", "-o", elf, *objs])
    subprocess.check_call(["arm-none-eabi-objcopy", "-O", "binary", elf, out])
    syms = subprocess.check_output(["arm-none-eabi-nm", "-n", elf], text=True)
    return open(out, "rb").read(), syms


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=lambda x: int(x, 0), default=0x0203F900)
    ap.add_argument("--sets", type=lambda x: int(x, 0), default=0x08F00000)
    ap.add_argument("--out", default=os.path.join(ROOT, "build/frontier/native.bin"))
    a = ap.parse_args()
    blob, syms = build(a.base, a.out, a.sets)
    print(f"{len(blob)} bytes at {a.base:#x}")
    print(syms)
