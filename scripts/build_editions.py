#!/usr/bin/env python3
"""Build the translation and/or River Edition ROMs + BPS into build/editions/, verifying each BPS against the clean FireRed ROM.

    python3 scripts/build_editions.py              # both
    python3 scripts/build_editions.py river        # one of: translation, river

Each edition's insert.py run writes build/Mercury_EN.{gba,bps}; this copies them out under their own names so building one does not
overwrite the other. build/Mercury_EN.* is left holding the last edition built (translation, when both). Not a release: dist.py packages those.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "roms" / "Pokemon - FireRed Version (USA, Europe).gba"
NAMES = {"translation": "Pokemon Azoth English + Frontier", "river": "Pokemon River Azoth (Chapter 2 + Frontier)"}


def build(edition):
    env = dict(os.environ)
    env.pop("RHT_EDITION", None)
    if edition == "river":
        env["RHT_EDITION"] = "river"
    out = subprocess.run([sys.executable, "scripts/insert.py"], cwd=ROOT, env=env, capture_output=True, text=True)
    if out.returncode:
        sys.exit(out.stdout + out.stderr)
    report = out.stdout
    if "'missing': 0" not in report or "'too_long': 0" not in report or "'errors': 0" not in report:
        sys.exit(f"{edition}: insert.py report is not clean:\n{report[-800:]}")
    gba, bps = ROOT / "build" / "Mercury_EN.gba", ROOT / "build" / "Mercury_EN.bps"
    with tempfile.TemporaryDirectory() as td:
        chk = Path(td) / "chk.gba"
        subprocess.run([sys.executable, "scripts/bps.py", "apply", str(BASE), str(bps), str(chk)], cwd=ROOT, check=True, capture_output=True)
        if chk.read_bytes() != gba.read_bytes():
            sys.exit(f"{edition}: the BPS does not reproduce the build")
    dest = ROOT / "build" / "editions"
    dest.mkdir(parents=True, exist_ok=True)
    for src, ext in ((gba, "gba"), (bps, "bps")):
        shutil.copyfile(src, dest / f"{NAMES[edition]}.{ext}")
    print(f"{edition}: clean report, BPS verified, ROM SHA-1 {hashlib.sha1(gba.read_bytes()).hexdigest()} -> build/editions/{NAMES[edition]}.*")


def main():
    want = sys.argv[1:] or ["river", "translation"]
    for e in want:
        if e not in NAMES:
            sys.exit(f"unknown edition {e!r}; use translation and/or river")
    for e in want:
        build(e)


if __name__ == "__main__":
    main()
