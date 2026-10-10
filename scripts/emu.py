"""Drive the local mGBA headless emulator via the mcp-mgba Lua bridge (TCP 8765).

Usage (from repo root):
    python3 -m scripts.emu text        # scan EWRAM for on-screen text, print decoded
    python3 -m scripts.emu press A     # hold A for 1 frame, release for 2
    python3 -m scripts.emu shot out.png  # screenshot

The bridge speaks newline-delimited JSON-RPC; requests are {"method", "params",
"id"}, replies {"id","result"|"error"}. read_range caps at 4096 bytes.
"""
import json
import socket
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
import mercury_text as mt  # noqa: E402

HOST, PORT = "127.0.0.1", 8765
CHUNK = 4096
EWRAM = 0x02000000
EWRAM_END = 0x02040000  # 256 KiB


class Emu:
    def __init__(self, host=HOST, port=PORT):
        self.s = socket.create_connection((host, port), timeout=15)
        self.buf = b""

    def call(self, method, **params):
        self.s.sendall(json.dumps({"method": method, "params": params, "id": 1}).encode() + b"\n")
        while b"\n" not in self.buf:
            self.buf += self.s.recv(1 << 20)
        line, self.buf = self.buf.split(b"\n", 1)
        r = json.loads(line)
        if "error" in r:
            raise RuntimeError(f"{method}: {r['error']}")
        return r.get("result")

    def read(self, addr, n):
        out = bytearray()
        while n > 0:
            k = min(n, CHUNK)
            out += bytes(self.call("read_range", address=addr + len(out), length=k))
            n -= k
        return bytes(out)

    def write(self, addr, data):
        for i in range(0, len(data), CHUNK):
            chunk = list(data[i:i + CHUNK])
            self.call("write_range", address=addr + i, bytes=chunk)

    def press(self, *buttons, hold=4, release=8):
        # bridge param names are frames/release_frames (not hold/release)
        self.call("press_buttons", buttons=list(buttons), frames=hold, release_frames=release)

    def frame(self):
        return self.info()["frame"]

    def wait(self, frames):
        """Block until the free-running core has advanced `frames` frames."""
        import time
        end = self.frame() + frames
        while self.frame() < end:
            time.sleep(0.02)

    def drive(self, seq, gap=30):
        """Press each button in `seq` (e.g. "Start A A Down A"), waiting `gap` frames."""
        for b in seq.split():
            self.press(b)
            self.wait(gap)

    def reset(self):
        self.call("reset")

    def screenshot(self, path):
        return self.call("screenshot", path=path)

    def save_state(self, path):
        return self.call("save_state", path=path)

    def load_state(self, path):
        return self.call("load_state", path=path)

    def info(self):
        return self.call("get_info")


# FR text uses its own 1-byte charset (NOT ASCII): A-Z=0xBB-0xD4, a-z=0xD5-0xEE,
# 0-9=0xA1-0xAA, space=0x00, é=0x1B, newline=0xFE, terminator=0xFF.
FR_LETTER = set(range(0xBB, 0xEF))            # A-Z a-z
FR_TEXT = (FR_LETTER | {0x00, 0x1B} | set(range(0xA1, 0xBB))
           | set(range(0x34, 0x40)) | set(range(0xF7, 0xFF)))


def scan_ewram(emu, min_run=6):
    """Return [(address, decoded_text)] for FR-charset text runs in EWRAM."""
    hits = []
    for base in range(EWRAM, EWRAM_END, 0x8000):
        blob = emu.read(base, 0x8000)
        i = 0
        n = len(blob)
        while i < n:
            if blob[i] in FR_LETTER:
                s = i
                while s > 0 and blob[s - 1] in (0x00, 0x1B):
                    s -= 1
                j = i
                letters = 0
                while j < n and blob[j] in FR_TEXT:
                    if blob[j] in FR_LETTER:
                        letters += 1
                    j += 1
                if letters >= min_run:
                    off = base + s
                    try:
                        txt, _ = mt.decode_vanilla(blob, s, limit=j - s)
                    except Exception:
                        txt = blob[s:j].decode("latin-1")
                    hits.append((off, txt))
                i = j + 1
            else:
                i += 1
    return hits


def _main():
    e = Emu()
    argv = sys.argv[1:]
    if not argv or argv[0] == "text":
        for off, txt in scan_ewram(e):
            t = txt.replace("\n", " / ")
            print(f"{off:08X}: {t}")
        return
    if argv[0] == "press":
        e.press(*argv[1:])
        return
    if argv[0] == "drive":
        # drive "<buttons>" [gap] [shot.png]
        e.drive(argv[1], int(argv[2]) if len(argv) > 2 else 30)
        if len(argv) > 3:
            print(e.screenshot(os.path.abspath(argv[3])))
        return
    if argv[0] == "shot":
        print(e.screenshot(argv[1]))
        return
    if argv[0] == "read":
        addr = int(argv[1], 16)
        n = int(argv[2], 16) if len(argv) > 2 else 0x100
        data = e.read(addr, n)
        print(data.hex())
        return
    if argv[0] == "info":
        print(json.dumps(e.info(), indent=2))
        return
    print(__doc__)


if __name__ == "__main__":
    _main()
