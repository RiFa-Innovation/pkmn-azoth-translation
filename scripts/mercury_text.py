"""Mercury text codec (definitive — derived from the hack's glyph code).

Encoding (from disassembly of the CJK hook at 0x0820F658..0x0820F704):

- Lead byte L in 0x01-0x1E, except 0x06 and 0x1B (control codes), starts a
  2-byte hanzi. Page = L-1 (L<=5), L-2 (7<=L<=0x1A), L-3 (0x1C<=L<=0x1E).
- Glyph slot = (page << 8) | trail. Font: 64 B/glyph, half-row compressed with
  each byte pair swapped; base 0x087D0000 (font 1+) or 0x08840000 (font 0).
- Only trails 0x00-0xF6 are used, so packed index = page*247 + trail. The font
  is all 6,763 GB2312 hanzi packed in order (no gap for the 5 empty cells
  D7FA-D7FE), so GB2312 cell rank = index, +5 once index >= 3755 (level 2).
- Every other byte is the vanilla FR 1-byte charset, except 0x36-0x3E, which
  the hack redrew as CJK punctuation (PUNCT below).
"""
import re

FONT_SMALL = 0x840000
FONT_NORMAL = 0x7D0000

CTRL_LEADS = {0x06, 0x1B}

# Hack-redrawn 1-byte glyphs (vanilla: LV/=/; and the 0x37-0x3E block).
# Identified from rendered glyphs + context; "?" suffix = tentative.
PUNCT = {
    0x36: "！", 0x37: "。", 0x38: "—", 0x39: "～", 0x3A: "、",
    0x3B: "，", 0x3C: "“", 0x3D: "”", 0x3E: "：",
}

# FR control codes: code -> number of argument bytes
EXT_CTRL_ARGS = {  # after 0xFC
    0x00: 0, 0x01: 1, 0x02: 1, 0x03: 1, 0x04: 3, 0x05: 1, 0x06: 1, 0x07: 0,
    0x08: 1, 0x09: 0, 0x0A: 0, 0x0B: 2, 0x0C: 1, 0x0D: 1, 0x0E: 1, 0x0F: 0,
    0x10: 2, 0x11: 1, 0x12: 1, 0x13: 1, 0x14: 1, 0x15: 0, 0x16: 0, 0x17: 0,
    0x18: 0,
}


def is_lead(b):
    return 0x01 <= b <= 0x1E and b not in CTRL_LEADS


def page_of(lead):
    if lead <= 5:
        return lead - 1
    if lead <= 0x1A:
        return lead - 2
    return lead - 3


def code_to_char(code):
    """2-byte code (big-endian int) -> hanzi, or None if not a valid hanzi."""
    lead, trail = code >> 8, code & 0xFF
    if not is_lead(lead) or trail > 0xF6:
        return None
    rank = page_of(lead) * 247 + trail
    if rank >= 6763:
        return None
    if rank >= 3755:  # skip unassigned D7FA-D7FE
        rank += 5
    try:
        return bytes([0xB0 + rank // 94, 0xA1 + rank % 94]).decode("gb2312")
    except UnicodeDecodeError:
        return None


def char_to_code(ch):
    b = ch.encode("gb2312")
    rank = (b[0] - 0xB0) * 94 + (b[1] - 0xA1)
    if rank >= 3760:
        rank -= 5
    page, trail = divmod(rank, 247)
    lead = page + 1 if page <= 4 else (page + 2 if page <= 0x18 else page + 3)
    return (lead << 8) | trail


def _load_vanilla_charmap(path="utilities/pokefirered/charmap.txt"):
    """1-byte vanilla FR charset (first definition wins; Latin table only)."""
    m = {}
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except FileNotFoundError:
        return m
    for line in lines:
        mm = re.match(r"^'(.+)'\s*=\s*([0-9A-F]{2})\s*$", line)
        if mm:
            m.setdefault(int(mm.group(2), 16), mm.group(1).replace("\\'", "'"))
        if line.startswith("@ Japanese"):
            break
    return m


VANILLA = _load_vanilla_charmap()


def decode(rom, off, limit=4096):
    """Decode one 0xFF-terminated string. Returns (text, end_offset).
    Control codes are rendered as {XX} / {FC:XX args}, newline FE as \\n,
    FA/FB as {FA}/{FB} (scroll/prompt)."""
    out = []
    i = off
    end = off + limit
    while i < end:
        b = rom[i]
        if b == 0xFF:
            return "".join(out), i + 1
        if is_lead(b) and i + 1 < end:
            ch = code_to_char((b << 8) | rom[i + 1])
            out.append(ch if ch else "{%02X%02X}" % (b, rom[i + 1]))
            i += 2
            continue
        if b == 0xFE:
            out.append("\n")
        elif b in (0xFA, 0xFB):
            out.append("{%02X}" % b)
        elif b == 0xFD:
            out.append("{FD:%02X}" % rom[i + 1])
            i += 1
        elif b == 0xFC:
            c = rom[i + 1]
            n = EXT_CTRL_ARGS.get(c, 0)
            args = rom[i + 2:i + 2 + n].hex().upper()
            out.append("{FC:%02X%s}" % (c, (" " + args) if args else ""))
            i += 1 + n
        elif b in PUNCT:
            out.append(PUNCT[b])
        elif b in VANILLA:
            out.append(VANILLA[b])
        else:
            out.append("{%02X}" % b)
        i += 1
    return "".join(out), i


def decode_fixed(rom, off, size):
    return decode(rom, off, size)[0]
