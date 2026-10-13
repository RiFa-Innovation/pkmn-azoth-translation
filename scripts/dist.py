#!/usr/bin/env python3
"""Package a release into dist/beta-N/.

    python3 scripts/dist.py 19 [--save PATH] [--no-build]

Runs scripts/insert.py (unless --no-build), verifies the BPS by applying it to
the clean base ROM and comparing byte-identical, then writes dist/beta-N/ with
the versioned .bps, .gba and .sav. The save defaults to the one we have been
playing on (dist/Pokemon Azoth (English) - next.sav); pass --save to ship a
different one. Refuses to touch a folder that already exists.
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "roms" / "Pokemon - FireRed Version (USA, Europe).gba"
DEFAULT_SAVE = ROOT / "dist" / "Pokemon Azoth (English) - next.sav"


def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-4000:], file=sys.stderr)
        print(r.stderr[-4000:], file=sys.stderr)
        sys.exit(f"{cmd[0]} failed ({r.returncode})")
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("beta", type=int, help="beta release number")
    ap.add_argument("--save", help=".sav to package (default: dist/Pokemon Azoth (English) - next.sav)")
    ap.add_argument("--no-build", action="store_true", help="skip scripts/insert.py (use the existing build/)")
    args = ap.parse_args()

    if not args.no_build:
        print(run([sys.executable, "scripts/insert.py"]).strip().splitlines()[-1])

    gba = ROOT / "build" / "Mercury_EN.gba"
    bps = ROOT / "build" / "Mercury_EN.bps"
    if not (gba.exists() and bps.exists()):
        sys.exit("build/Mercury_EN.{gba,bps} missing; run scripts/insert.py")
    if not BASE.exists():
        sys.exit(f"base ROM missing: {BASE}")

    # standard verification: the BPS must reproduce the build byte-identically
    with tempfile.TemporaryDirectory() as td:
        chk = Path(td) / "chk.gba"
        run([sys.executable, "scripts/bps.py", "apply", str(BASE), str(bps), str(chk)])
        run(["cmp", str(chk), str(gba)])
        print("BPS applies to the clean ROM byte-identically")

    out = ROOT / "dist" / f"beta-{args.beta}"
    if out.exists():
        sys.exit(f"{out} already exists; not overwriting")
    out.mkdir(parents=True)

    name = f"Pokemon-Azoth-English-beta-{args.beta}"
    shutil.copyfile(bps, out / f"{name}.bps")
    shutil.copyfile(gba, out / f"{name}.gba")

    save = Path(args.save).expanduser() if args.save else DEFAULT_SAVE
    if save.exists():
        shutil.copyfile(save, out / f"{name}.sav")
        print(f"save: {save}")
    else:
        print(f"warning: no save at {save}; packaged without one", file=sys.stderr)

    for p in sorted(out.iterdir()):
        print(f"{p.name}\tSHA-1 {hashlib.sha1(p.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
