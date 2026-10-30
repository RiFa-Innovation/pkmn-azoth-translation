#!/usr/bin/env python3
"""Package a release into dist/beta-N/ (or dist/river-V/ for the River Edition).

    python3 scripts/dist.py 19 [--save PATH] [--no-build]
    python3 scripts/dist.py --river 0.1 [--no-build]     # unofficial Chapter 2 build, no save included
    python3 scripts/dist.py --cheats 1                   # a translation build with the Cheat Device (NOT released since the cheats-v1 add-on was withdrawn; River builds have it natively)

Runs scripts/insert.py (unless --no-build), verifies the BPS by applying it to
the clean base ROM and comparing byte-identical, then writes dist/beta-N/ with
the versioned .bps, .gba and .sav. The save is always included (a copy named
to pair with the .gba, so it loads automatically); it defaults to the one we
have been playing on (dist/Pokemon Azoth (English) - next.sav), pass --save to
ship a different one. Refuses to touch a folder that already exists.
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


def package_cheats(version):
    """dist/cheats-vV/: the translation built with RHT_CHEATS=1 (docs/CHEATS.md) as .bps + .gba, no save. The River Edition has the Cheat Device built in."""
    import os
    out = ROOT / "dist" / f"cheats-v{version}"
    if out.exists():
        sys.exit(f"{out} already exists; not overwriting")
    out.mkdir(parents=True)
    for edition, name in (("translation", f"Pokemon-Azoth-English-Cheats-v{version}"),):
        env = dict(os.environ, RHT_CHEATS="1")
        env.pop("RHT_EDITION", None)
        if edition == "river":
            env["RHT_EDITION"] = "river"
        r = subprocess.run([sys.executable, "scripts/insert.py"], cwd=ROOT, env=env, capture_output=True, text=True)
        if r.returncode or "'missing': 0, 'too_long': 0, 'errors': 0" not in r.stdout:
            sys.exit(f"{edition}: insert.py failed or report not clean\n{r.stdout[-1500:]}{r.stderr[-1500:]}")
        gba, bps = ROOT / "build" / "Mercury_EN.gba", ROOT / "build" / "Mercury_EN.bps"
        with tempfile.TemporaryDirectory() as td:
            chk = Path(td) / "chk.gba"
            run([sys.executable, "scripts/bps.py", "apply", str(BASE), str(bps), str(chk)])
            run(["cmp", str(chk), str(gba)])
        print(f"{edition}: BPS applies to the clean ROM byte-identically")
        shutil.copyfile(bps, out / f"{name}.bps")
        shutil.copyfile(gba, out / f"{name}.gba")
    for p in sorted(out.iterdir()):
        print(f"{p.name}\tSHA-1 {hashlib.sha1(p.read_bytes()).hexdigest()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("beta", type=int, nargs="?", help="beta release number")
    ap.add_argument("--river", metavar="VERSION", help="package the River Edition (unofficial fan Chapter 2), e.g. 0.1")
    ap.add_argument("--cheats", metavar="VERSION", help="package the optional Cheat Device add-on for the translation, e.g. 2")
    ap.add_argument("--save", help=".sav to package (default: dist/Pokemon Azoth (English) - next.sav)")
    ap.add_argument("--no-build", action="store_true", help="skip scripts/insert.py (use the existing build/)")
    args = ap.parse_args()
    if args.cheats:
        return package_cheats(args.cheats)
    if (args.beta is None) == (args.river is None):
        ap.error("give either a beta number or --river VERSION")

    if not args.no_build:
        import os
        if args.river:
            os.environ["RHT_EDITION"] = "river"     # scripts/logo.py adds the RIVER EDITION title tag
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

    if args.river:
        out = ROOT / "dist" / f"river-{args.river}"
        name = f"Pokemon-Azoth-English-RIVER-EDITION-v{args.river}"
    else:
        out = ROOT / "dist" / f"beta-{args.beta}"
        name = f"Pokemon-Azoth-English-beta-{args.beta}"
    if out.exists():
        sys.exit(f"{out} already exists; not overwriting")
    out.mkdir(parents=True)

    shutil.copyfile(bps, out / f"{name}.bps")
    shutil.copyfile(gba, out / f"{name}.gba")

    if args.river and not args.save:
        for p in sorted(out.iterdir()):
            print(f"{p.name}\tSHA-1 {hashlib.sha1(p.read_bytes()).hexdigest()}")
        return   # the River Edition ships without a save: its story needs a late-game save of the player's own
    save = Path(args.save).expanduser() if args.save else DEFAULT_SAVE
    if not save.exists():
        sys.exit(f"no save at {save}; pass --save PATH (the package always includes the .sav, named to pair with the .gba so it loads automatically)")
    shutil.copyfile(save, out / f"{name}.sav")
    print(f"save: {save}")

    for p in sorted(out.iterdir()):
        print(f"{p.name}\tSHA-1 {hashlib.sha1(p.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
