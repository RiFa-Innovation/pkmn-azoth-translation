"""Record a GIF of the running game while a route plays, frame-exact.

    python3 scripts/clip.py --route "A A U3 R2 A" --out clip.gif [--state NAME]

The core free-runs ~80x faster than real time, so the
bridge itself screenshots every Nth *emulated* frame (`record_start`/`record_stop` in bridge.lua); the GIF is
then played back at game speed (59.7275 fps / EVERY). Sync with the inputs holds by construction: shots and
button presses are both counted in emulated frames, never wall-clock time.

    --edition E    translation (default) or river: which ROM to run. Boots the bridge if it is down, and restarts
                   it when it is running a different ROM (a fresh boot sits on the title screen)
    --state NAME   load a saved state first, so every clip starts from the same moment. States only load on the
                   build that made them: translation uses saves/states/NAME.ss, other editions saves/states/E/NAME.ss
    --route SEQ    play.py route tokens (see its docstring)
    --every N      sample every N frames (default 4, ~15 fps)
    --lead/--tail  frames of footage kept before the first and after the last input (default 20 / 60)
    --max-mb M     size budget; steps scale 3 -> 2 -> 1 and halves the frame rate until it fits (default 9)
    --idle S       cap any still stretch at S seconds of game time (default 1.0)

Prints one JSON line: {"out", "bytes", "frames", "seconds", "scale", "fps"}. Exit 1 with a message on stderr on failure.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(__file__))
import play  # noqa: E402
from emu import Emu  # noqa: E402

GBA_FPS = 59.7275
ROMS = {
    "translation": "build/Mercury_EN.gba",
    "river": "build/editions/Pokemon River Azoth (Chapter 2 + Frontier).gba",
}
ROMFILE = "saves/.emu.rom"  # which ROM the bridge we booted is running


class FastEmu(Emu):
    """wait() without the 20 ms sleep, which at ~80x speed overshoots by ~100 frames."""

    def wait(self, frames):
        end = self.frame() + frames
        while self.frame() < end:
            pass


def connect(edition, explicit):
    """The bridge, booted on the edition's ROM if it is down or (when an edition was asked for) running another."""
    rom = os.path.abspath(ROMS[edition])
    if not os.path.exists(rom):
        sys.exit(f"clip: no ROM for edition {edition!r} at {ROMS[edition]}; build it first")
    cur = open(ROMFILE).read().strip() if os.path.exists(ROMFILE) else None
    try:
        e = FastEmu()
        if not explicit or cur == rom:
            return e
        e.s.close()
    except OSError:
        pass
    play.stop()
    time.sleep(1)
    play.boot(rom)
    try:
        e = FastEmu()
    except OSError:
        sys.exit("clip: could not start the emulator bridge (is utilities/mgba built? see EMULATOR.md)")
    open(ROMFILE, "w").write(rom)
    e.wait(120)  # past the boot logo
    return e


def trim_idle(frames, shots, every, idle_s):
    """Drop frames from still stretches longer than idle_s; returns the kept shot paths."""
    cap = max(1, int(idle_s * GBA_FPS / every))
    kept, run, prev = [], 0, None
    for f in frames:
        h = hashlib.md5(open(shots[f], "rb").read()).digest()
        run = run + 1 if h == prev else 0
        prev = h
        if run < cap:
            kept.append(shots[f])
    return kept


def encode(paths, out, every, scale, fps_div, budget):
    work = tempfile.mkdtemp(prefix="clip-seq-")
    try:
        for i, p in enumerate(paths[::fps_div]):
            os.symlink(p, os.path.join(work, f"{i:06d}.png"))
        fps = GBA_FPS / every / fps_div
        w, h = 240 * scale, 160 * scale
        vf = (f"scale={w}:{h}:flags=neighbor,split[a][b];[a]palettegen=stats_mode=full[p];"
              f"[b][p]paletteuse=dither=none")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", f"{fps:.4f}", "-i", os.path.join(work, "%06d.png"),
                        "-filter_complex", vf, "-loop", "0", out], check=True)
        return os.path.getsize(out) <= budget, fps
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--edition", choices=sorted(ROMS))
    ap.add_argument("--state")
    ap.add_argument("--every", type=int, default=4)
    ap.add_argument("--lead", type=int, default=20)
    ap.add_argument("--tail", type=int, default=60)
    ap.add_argument("--max-mb", type=float, default=9)
    ap.add_argument("--idle", type=float, default=1.0)
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("clip: ffmpeg not found")
    out = os.path.abspath(a.out)
    edition = a.edition or "translation"
    e = connect(edition, a.edition is not None)
    if a.state:
        st = os.path.abspath(os.path.join(play.states_dir(edition), f"{a.state}.ss"))
        if not os.path.exists(st):
            have = sorted(f[:-3] for f in os.listdir(play.states_dir(edition)) if f.endswith(".ss")) if os.path.isdir(play.states_dir(edition)) else []
            sys.exit(f"clip: no saved state {a.state!r} for the {edition} edition (have: {', '.join(have) or 'none'}). "
                     "Omit --state to start from the title screen.")
        e.load_state(st)
        e.wait(5)

    shots_dir = tempfile.mkdtemp(prefix="clip-shots-")
    recording = False
    try:
        e.call("record_start", dir=shots_dir, every=a.every)
        recording = True
        e.wait(a.lead)
        play.go(e, a.route, shoot=False)
        e.wait(a.tail)
        res = e.call("record_stop")
        recording = False
        frames = res["frames"]
        if len(frames) < 2:
            sys.exit("clip: captured fewer than 2 frames")
        shots = {f: os.path.join(shots_dir, f"f{f}.png") for f in frames}
        paths = trim_idle(frames, shots, a.every, a.idle)
        budget = int(a.max_mb * 1024 * 1024)
        for scale, div in ((3, 1), (2, 1), (2, 2), (1, 2), (1, 3)):
            fit, fps = encode(paths, out, a.every, scale, div, budget)
            if fit:
                break
        else:
            sys.exit(f"clip: could not fit {a.max_mb} MB; shorten the route")
        print(json.dumps({"out": out, "bytes": os.path.getsize(out), "frames": len(paths) // div,
                          "seconds": round(len(paths) // div / fps, 1), "scale": scale, "fps": round(fps, 1),
                          "truncated": res["truncated"]}))
    finally:
        if recording:
            try:
                e.call("record_stop")
            except Exception:
                pass
        shutil.rmtree(shots_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
