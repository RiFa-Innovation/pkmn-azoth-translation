"""Minimal BPS patch create/apply (beat spec: SourceRead + TargetRead only).

Usage:
    python3 scripts/bps.py create <source> <target> <out.bps>
    python3 scripts/bps.py apply  <source> <patch.bps> <out>
"""
import sys
import zlib


def _num(n):
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def _read_num(buf, i):
    data, shift = 0, 1
    while True:
        x = buf[i]
        i += 1
        data += (x & 0x7F) * shift
        if x & 0x80:
            return data, i
        shift <<= 7
        data += shift


def create(src, tgt):
    out = bytearray(b"BPS1")
    out += _num(len(src)) + _num(len(tgt)) + _num(0)
    i, n = 0, len(tgt)
    while i < n:
        j = i
        if i < len(src) and src[i] == tgt[i]:
            while j < n and j < len(src) and src[j] == tgt[j]:
                j += 1
            out += _num(((j - i - 1) << 2) | 0)          # SourceRead
        else:
            while j < n and not (j < len(src) and src[j] == tgt[j]
                                 and j + 8 < min(n, len(src)) and src[j:j + 8] == tgt[j:j + 8]):
                j += 1
            out += _num(((j - i - 1) << 2) | 1) + tgt[i:j]  # TargetRead
        i = j
    for c in (zlib.crc32(src), zlib.crc32(tgt)):
        out += c.to_bytes(4, "little")
    out += zlib.crc32(out).to_bytes(4, "little")
    return bytes(out)


def apply(src, patch):
    assert patch[:4] == b"BPS1"
    assert zlib.crc32(patch[:-4]) == int.from_bytes(patch[-4:], "little"), "patch CRC"
    assert zlib.crc32(src) == int.from_bytes(patch[-12:-8], "little"), "source CRC"
    i = 4
    ssize, i = _read_num(patch, i)
    tsize, i = _read_num(patch, i)
    msize, i = _read_num(patch, i)
    i += msize
    out = bytearray()
    sp = tp = 0
    end = len(patch) - 12
    while i < end:
        d, i = _read_num(patch, i)
        cmd, ln = d & 3, (d >> 2) + 1
        if cmd == 0:
            out += src[len(out):len(out) + ln]
        elif cmd == 1:
            out += patch[i:i + ln]
            i += ln
        else:
            off, i = _read_num(patch, i)
            off = (-1 if off & 1 else 1) * (off >> 1)
            if cmd == 2:
                sp += off
                out += src[sp:sp + ln]
                sp += ln
            else:
                tp += off
                for _ in range(ln):
                    out.append(out[tp])
                    tp += 1
    assert len(out) == tsize
    assert zlib.crc32(out) == int.from_bytes(patch[-8:-4], "little"), "target CRC"
    return bytes(out)


if __name__ == "__main__":
    op, a, b, c = sys.argv[1:5]
    if op == "create":
        open(c, "wb").write(create(open(a, "rb").read(), open(b, "rb").read()))
    else:
        open(c, "wb").write(apply(open(a, "rb").read(), open(b, "rb").read()))
    print("ok ->", c)
