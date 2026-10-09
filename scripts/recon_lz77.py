"""Phase 0 recon: LZ77 block scanner + text classifier for Fire Red ROMs.

Locates LZ77-compressed blocks (gbagfx format: 0x10 + 24-bit size, then GBA
LZ77 stream), decompresses them, and classifies the decompressed payload as
ASCII / GBK / UTF-16 / binary. Used to find the hack's text encoding.
"""
import sys
from collections import Counter


def lz77_decompress(data, off):
    """Decompress a gbagfx LZ77 block at data[off:]. Returns bytes or None."""
    if off + 4 > len(data):
        return None
    if data[off] != 0x10:
        return None
    size = data[off + 1] | (data[off + 2] << 8) | (data[off + 3] << 16)
    if not (1 <= size <= 0x4000):
        return None
    src = off + 4
    out = bytearray()
    try:
        while len(out) < size:
            flags = data[src]
            src += 1
            for i in range(8):
                if len(out) >= size:
                    break
                if flags & 0x80:
                    b0 = data[src]
                    b1 = data[src + 1]
                    src += 2
                    blk = (b0 >> 4) + 3
                    dist = (((b0 & 0xF) << 8) | b1) + 1
                    pos = len(out) - dist
                    if pos < 0:
                        return None
                    for _ in range(blk):
                        if len(out) >= size:
                            break
                        out.append(out[pos])
                        pos += 1
                else:
                    out.append(data[src])
                    src += 1
                flags <<= 1
        return bytes(out)
    except IndexError:
        return None


def is_gbk_pair(b0, b1):
    return 0x81 <= b0 <= 0xFE and 0x40 <= b1 <= 0xFE and b1 != 0x7F


def classify(buf):
    """Return (kind, detail) for a decompressed block."""
    if not buf:
        return ("empty", "")
    # ASCII printable ratio
    printable = sum(1 for b in buf if 0x20 <= b < 0x7F or b in (0x09, 0x0A))
    ascii_ratio = printable / len(buf)
    if ascii_ratio > 0.9 and len(buf) >= 4:
        s = buf.decode("ascii", errors="replace")
        return ("ascii", s[:60])
    # GBK run check
    gbk_run = 0
    best = 0
    i = 0
    while i < len(buf) - 1:
        if is_gbk_pair(buf[i], buf[i + 1]):
            gbk_run += 2
            best = max(best, gbk_run)
            i += 2
        else:
            gbk_run = 0
            i += 1
    if best >= 6:
        try:
            s = buf.decode("gbk", errors="replace")
            cjk = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
            return ("gbk", f"{cjk}cjk {s[:40]!r}")
        except Exception:
            return ("gbk?", "")
    return ("binary", "")


def scan(rom, label, max_report=30):
    data = open(rom, "rb").read()
    kinds = Counter()
    hits = []
    # scan 4-byte aligned (FR pointers are 4-byte aligned)
    for off in range(0, len(data) - 4, 4):
        if data[off] != 0x10:
            continue
        size = data[off + 1] | (data[off + 2] << 8) | (data[off + 3] << 16)
        if not (4 <= size <= 0x4000):
            continue
        buf = lz77_decompress(data, off)
        if buf is None:
            continue
        kind, detail = classify(buf)
        kinds[kind] += 1
        if kind in ("ascii", "gbk", "gbk?"):
            hits.append((off, size, kind, detail))
    print(f"\n=== {label}: {len(data)} bytes ===")
    print(f"LZ77 blocks by kind: {dict(kinds)}")
    print(f"text-like blocks: {len(hits)}")
    for off, size, kind, detail in hits[:max_report]:
        print(f"  0x{off:07X} ({size:5d}B) [{kind}] {detail}")
    return hits


if __name__ == "__main__":
    rom = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else rom
    scan(rom, label)
