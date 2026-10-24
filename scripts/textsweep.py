"""Render the built ROM's dialogue in the running game and flag text that touches the box edge, scrolls oddly or looks wrong.

    python3 scripts/textsweep.py list ROM DB                      # count the text pointers the ROM's scripts load
    python3 scripts/textsweep.py render ROM DB [--n 200] [--seed 1] [--start 0] [--out DIR]

ROM/DB: the ROM the emulator is running and the hackdb sqlite built from it (`scripts/hackdb.py build --rom ROM`). The bridge must be up
with the game on an idle overworld (any map). Strings are enumerated from the ROM itself (every `loadword` pointer in its decoded
scripts), because the hackdb string table follows the ORIGINAL layout and points into other data once the inserter has relocated text.

Each string is shown with a two-byte script (`loadword 0 PTR; callstd 2; end`); A is pressed through its pages and every page is
captured. Per page the ink (dark pixels) of the two text lines inside the message box is measured: a line whose ink reaches
x >= LIMIT (the text area ends near x=224) is flagged `edge`; a string that needs more than MAXPAGES pages is flagged `long`; a decoded string containing a character outside the expected English
set (a stray lead byte shows up as one) is flagged `oddchar`.
Output: DIR/report.csv (every string, flags, pages), DIR/flagged-NN.png contact sheets (flagged pages first), DIR/sample-NN.png.
Needs no story state. A string with a `{FD:..}` buffer placeholder is not rendered (flag `buffer`): only its own script fills the buffer, and out of
context it hangs the script or corrupts the screen.
"""
import csv
import os
import random
import re
import sqlite3
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import mercury_text as mt  # noqa: E402
import mapdrive  # noqa: E402
from emu import Emu  # noqa: E402

BOX_ROWS = ((120, 137), (138, 153))   # the two text lines of the message box (screenshot rows)
X0, X1 = 6, 236                        # interior columns scanned for ink
LIMIT = 226                            # ink at or beyond this column touches the right edge of the text area
MAXPAGES = 80
CTX_MODE = 0x03000EB1


def pointers(rom, db):
    """Sorted unique ROM addresses of dialogue strings loaded by the decoded scripts."""
    ptrs = set()
    for (a,) in sqlite3.connect(db).execute("select args from cmds where name='loadword'"):
        m = re.search(r"0x0[89A][0-9A-Fa-f]{6}$", a.strip())
        if m:
            p = int(m.group(0), 16)
            if p - 0x08000000 < len(rom):
                ptrs.add(p)
    return sorted(ptrs)


def ink_extent(img):
    """(min_x, max_x) of dark pixels per text line, or None for an empty line. img: PIL image of the full screenshot."""
    import numpy as np
    g = np.array(img.convert("L")).astype(int)
    out = []
    for y0, y1 in BOX_ROWS:
        xs = np.where((g[y0:y1, X0:X1] < 100).any(axis=0))[0]
        out.append((int(xs.min()) + X0, int(xs.max()) + X0) if len(xs) else None)
    return out


OK_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,;:!?'\"-()/&+*%#=<>@~_\n[]{}\u2019\u2018\u201c\u201d\u2026\u00e9\u00c9\u2642\u2640\u00a5\u00d7\u2192\u2190\u2191\u2193$\u00ed\u00e0\u00e8\u00f1\u00fc\u00e1\u00f3\u00fa\u00ef\u00e2\u00ea\u00ee\u00f4\u00fb\u00e7\u00f6\u00e4")


def odd_chars(text):
    """Characters outside the expected English set, ignoring {..} control codes."""
    return sorted({c for c in re.sub(r"\{[^}]*\}", "", text) if c not in OK_CHARS})


def scene_signature(e, path):
    """Downscaled grey image of the top of the screen (above the message box), to notice a string that broke the display."""
    from PIL import Image
    e.screenshot(os.path.abspath(path))
    return Image.open(path).convert("L").crop((0, 0, 240, 100)).resize((60, 25))


def changed_fraction(a, b):
    import numpy as np
    d = np.abs(np.array(a).astype(int) - np.array(b).astype(int))
    return float((d > 40).mean())


def show(e, ptr, shot_dir):
    """Run the string; return the list of screenshot paths (one per page)."""
    code = bytes([0x0F, 0x00]) + struct.pack("<I", ptr) + bytes([0x09, 0x02, 0x02])
    mapdrive.run_script(e, code)
    e.wait(25)
    paths = []
    for i in range(MAXPAGES + 1):
        if e.read(CTX_MODE, 1)[0] == 0:
            break
        p = os.path.join(shot_dir, f"p{i}.png")
        e.screenshot(os.path.abspath(p))
        paths.append(p)
        e.press("A", hold=3, release=6)
        e.wait(28)
    if e.read(CTX_MODE, 1)[0] != 0:  # still running after MAXPAGES: stop it
        e.write(0x03000EB0, b"\x00\x00")
        e.wait(10)
        e.press("B", hold=3, release=6)
        e.wait(20)
        return paths, True
    return paths, False


def pointers_probe(rom, ptrs):
    """Any short string will do to prove the engine runs injected scripts."""
    return min(ptrs, key=lambda p: len(mt.decode_vanilla(rom, p - 0x08000000)[0]) or 999)


def main(argv):
    cmd, rom_path, db = argv[0], argv[1], argv[2]
    opt = lambda k, d: type(d)(argv[argv.index(k) + 1]) if k in argv else d
    rom = open(rom_path, "rb").read()
    ptrs = pointers(rom, db)
    if cmd == "list":
        print(len(ptrs), "text pointers")
        return 0
    from PIL import Image
    n, seed, start = opt("--n", 200), opt("--seed", 1), opt("--start", 0)
    out = opt("--out", os.path.join(ROOT, "saves/shots/textsweep"))
    os.makedirs(out, exist_ok=True)
    pool = ptrs[start:]
    sample = pool if n <= 0 else random.Random(seed).sample(pool, min(n, len(pool)))
    e, rows, flagged = Emu(), [], []
    probe, was_stuck = show(e, pointers_probe(rom, ptrs), out)
    if was_stuck or not probe:
        raise SystemExit("the game does not run injected scripts right now (input locked?): reboot the emulator and try again")
    base_state = os.path.abspath(os.path.join(out, "base.ss"))
    e.save_state(base_state)
    base_sig = scene_signature(e, os.path.join(out, "base.png"))
    corrupt = []
    for k, p in enumerate(sample):
        text = mt.decode_vanilla(rom, p - 0x08000000)[0]
        if "{FD:" in text:  # prints a script buffer that only the owning script fills: out of context it hangs or corrupts the screen
            rows.append({"ptr": f"{p:#010x}", "pages": 0, "max_ink_x": 0, "flags": "buffer", "odd": "",
                         "text": text.replace("\n", "\\n")[:200]})
            continue
        paths, toolong = show(e, p, out)
        e.wait(20)
        stuck = toolong and len(paths) >= MAXPAGES  # the script never ended (input locked, or the engine stopped running scripts)
        if stuck:
            e.load_state(base_state)
            e.wait(30)
        if changed_fraction(base_sig, scene_signature(e, os.path.join(out, "after.png"))) > 0.35:
            corrupt.append(p)
            import shutil
            shutil.copy(os.path.join(out, "after.png"), os.path.join(out, f"corrupt-{p:08x}.png"))
            print(f"display broken after {p:#010x}: {text[:60]!r}", flush=True)
            e.load_state(base_state)  # carry on from a clean game
            e.wait(30)
        worst, flags = 0, set()
        pages = []
        for path in paths:
            im = Image.open(path).convert("RGB")
            ext = ink_extent(im)
            mx = max((x[1] for x in ext if x), default=0)
            worst = max(worst, mx)
            pages.append(im.crop((0, 108, 240, 160)))
        if worst >= LIMIT:
            flags.add("edge")
        if stuck:
            flags.add("stuck")
        elif toolong:
            flags.add("long")
        odd = odd_chars(text)
        if odd:
            flags.add("oddchar")
        if not paths:
            flags.add("nopage")
        if corrupt and corrupt[-1] == p:
            flags.add("corrupt")
        rows.append({"ptr": f"{p:#010x}", "pages": len(paths), "max_ink_x": worst, "flags": " ".join(sorted(flags)),
                     "odd": "".join(odd), "text": text.replace("\n", "\\n")[:200]})
        if flags:
            flagged.append((p, pages, flags))
        if k % 100 == 99:
            print(f"{k + 1}/{len(sample)} strings, {len(flagged)} flagged", flush=True)
    with open(os.path.join(out, "report.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    # contact sheets: 3 columns of (240x52) crops, label strip above each
    def sheet(items, name):
        for si in range(0, len(items), 24):
            chunk = items[si:si + 24]
            cols, cw, ch = 3, 240, 52 + 10
            rowsn = (len(chunk) + cols - 1) // cols
            g = Image.new("RGB", (cols * cw, rowsn * ch), (40, 40, 40))
            from PIL import ImageDraw
            d = ImageDraw.Draw(g)
            for i, (p, pages, flags) in enumerate(chunk):
                x, y = (i % cols) * cw, (i // cols) * ch
                d.text((x + 2, y), f"{p:#010x} {' '.join(sorted(flags))} p{len(pages)}", fill=(255, 255, 0))
                if pages:
                    # the worst page = the one whose ink extends furthest; fall back to the first
                    g.paste(pages[0], (x, y + 10))
            g.save(os.path.join(out, f"{name}-{si // 24:02d}.png"))
    sheet(flagged, "flagged")
    print(f"{len(sample)} strings, {len(flagged)} flagged -> {out}/report.csv, flagged-*.png")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
