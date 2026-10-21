"""Tiny FireRed script assembler for new events (used by mapedit.py).

Source is one instruction per line; `label:` defines a label; `#` starts a comment.
Operands: ints (0x.. ok), label names (4-byte pointer), `@name` (another script's
address, resolved by the caller via `externs`).

  say "text"          -> loadword 0 <text>; callstd 2   (text is wrapped to the dialogue box)
  warp G.N X Y        -> warp G N 0xFF X Y
  trainer ID "intro" "defeat"        -> trainerbattle type 0: the script ENDS after the battle (use for plain NPC trainers)
  trainer ID "intro" "defeat" LABEL  -> type 2 (continue script): after a win, execution resumes at LABEL (put LABEL
                                        right after the command so an already-beaten trainer falls through to it)
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
_MOVES = None

MOVEMENT_INC = os.path.join(os.path.dirname(__file__), "..", "utilities/pokefirered/asm/macros/movement.inc")
MOVEMENT_H = os.path.join(os.path.dirname(__file__), "..", "utilities/pokefirered/include/constants/event_object_movement.h")


def moves():
    """movement name -> byte (walk_down, face_left, delay_8, step_end ... from the decomp macros)."""
    global _MOVES
    if _MOVES is None:
        consts = {m.group(1): int(m.group(2), 0)
                  for m in re.finditer(r"#define (MOVEMENT_ACTION_\w+)\s+(0x[0-9A-Fa-f]+|\d+)", open(MOVEMENT_H).read())}
        _MOVES = {m.group(1): consts[m.group(2)]
                  for m in re.finditer(r"create_movement_action (\w+), (MOVEMENT_ACTION_\w+)", open(MOVEMENT_INC).read())
                  if m.group(2) in consts}
        _MOVES["step_end"] = 0xFE
    return _MOVES


def _preprocess(src):
    """once FLAG ... endonce: run the body a single time (sets FLAG first); later triggers just release."""
    out = []
    for raw in src.splitlines():
        ln = raw.strip()
        m = re.match(r"once\s+(\S+)$", ln)
        if m:
            out += [f"checkflag {m.group(1)}", "goto_if 1 _once_end", f"setflag {m.group(1)}"]
        elif ln == "endonce":
            out += ["releaseall", "end", "_once_end:", "releaseall", "end"]
        else:
            out.append(raw)
    return "\n".join(out)


def ops():
    global _OPS
    if _OPS is None:
        _OPS = {v[0]: (k, v[1]) for k, v in scrdis.load_macros().items()}
    return _OPS


def _num(tok):
    return int(tok, 0)


def assemble(src, base, widths, externs, text_alloc):
    lines = []
    for raw in _preprocess(src).splitlines():
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
        m = re.match(r"move\s+(\S+)\s+(.+)$", ln)
        if m:
            steps = [moves()[w] for w in m.group(2).split()]
            items.append(("move", _num(m.group(1)), bytes(steps + [0xFE])))
            pc += 7 + 3   # applymovement local ptr (1+2+4) + waitmovement local (1+2) = 10
            continue
        m = re.match(r'trainer\s+(\w+)\s+"(.*?)"\s+"(.*?)"(?:\s+(\w+))?$', ln)
        if m:
            items.append(("trainer", int(m.group(1), 0), m.group(2), m.group(3), m.group(4)))
            pc += 18 if m.group(4) else 14   # type 2 (continue script) carries an extra 4-byte event-script pointer
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
        elif it[0] == "move":
            a = text_alloc(it[2])
            out += bytes([0x50]) + struct.pack("<HI", it[1], a) + bytes([0x52]) + struct.pack("<H", it[1])
        elif it[0] == "trainer":
            ptrs = [text_alloc(mt.encode_en(mt.wrap_en(t, bytes(widths), DIALOGUE_PX, True))) for t in it[2:4]]
            if it[4]:   # TRAINER_BATTLE_CONTINUE_SCRIPT: after a win the script resumes at the label
                out += bytes([0x5C, 2]) + struct.pack("<HHIII", it[1], 0, ptrs[0], ptrs[1], ptr(it[4]))
            else:       # type 0 ends the script after the battle
                out += bytes([0x5C, 0]) + struct.pack("<HHII", it[1], 0, *ptrs)
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
