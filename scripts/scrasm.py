"""Tiny FireRed script assembler for new events (used by mapedit.py).

Source is one instruction per line; `label:` defines a label; `#` starts a comment.
Operands: ints (0x.. ok), label names (4-byte pointer), `@name` (another script's
address, resolved by the caller via `externs`).

  say "text"          -> loadword 0 <text>; callstd 2   (text is wrapped to the dialogue box)
  warp G.N X Y        -> warp G N 0xFF X Y
  <opcode> args...    -> any opcode known to scrdis (names from pokefirered event.inc)

assemble(src, base_addr, widths, externs, text_alloc) -> bytes
  text_alloc(bytes) -> ROM address of a newly stored string
"""
import re
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
import mercury_text as mt  # noqa: E402
import scrdis  # noqa: E402

DIALOGUE_PX = 198
_OPS = None


def ops():
    global _OPS
    if _OPS is None:
        _OPS = {v[0]: (k, v[1]) for k, v in scrdis.load_macros().items()}
    return _OPS


def _num(tok):
    return int(tok, 0)


def assemble(src, base, widths, externs, text_alloc):
    lines = []
    for raw in src.splitlines():
        raw = raw.split("#")[0].strip() if '"' not in raw else raw.strip()
        if raw:
            lines.append(raw)
    # pass 1: sizes + labels
    labels, items, pc = {}, [], 0
    for ln in lines:
        if re.fullmatch(r"\w+:", ln):
            labels[ln[:-1]] = pc
            continue
        m = re.match(r'say\s+"(.*)"$', ln)
        if m:
            items.append(("say", m.group(1)))
            pc += 2 + 5 + 2   # loadword 0 ptr (6) + callstd 2 (2) -> 8
            pc -= 1
            continue
        parts = ln.split()
        name = parts[0]
        if name == "warp":
            items.append(("warp", parts[1:]))
            pc += 1 + 3 + 4 + 0
            continue
        op, args = ops()[name]
        size = 1 + sum({"byte": 1, "2byte": 2, "4byte": 4}[k] * c for k, c in args)
        items.append(("op", name, op, args, parts[1:]))
        pc += size
    out = bytearray()

    def ptr(tok):
        if tok.startswith("@"):
            return externs[tok[1:]]
        if tok in labels:
            return base + labels[tok]
        return _num(tok)

    for it in items:
        if it[0] == "say":
            text = mt.wrap_en(it[1], __import__("builtins").bytes(widths), DIALOGUE_PX, True)
            a = text_alloc(mt.encode_en(text))
            out += bytes([0x0F, 0]) + struct.pack("<I", a) + bytes([0x09, 0x02])
        elif it[0] == "warp":
            g, n = (int(x) for x in it[1][0].split("."))
            out += bytes([0x39, g, n, 0xFF]) + struct.pack("<HH", _num(it[1][1]), _num(it[1][2]))
        else:
            _, name, op, args, toks = it
            out.append(op)
            i = 0
            for kind, c in args:
                for _ in range(c):
                    t = toks[i]
                    i += 1
                    if kind == "byte":
                        out.append(_num(t) if not t.startswith("@") else 0)
                    elif kind == "2byte":
                        out += struct.pack("<H", _num(t))
                    else:
                        out += struct.pack("<I", ptr(t))
    assert len(out) == pc, f"size mismatch {len(out)} != {pc}"
    return bytes(out)
