"""Read the live battle out of RAM into a plain dict (the agent's `state`).

Addresses are vanilla FireRed (pokefirered `sym_ewram`/`sym_iwram`); the hack's CFRU battle engine keeps them. Checked on
2026-10-23 on the English build: gBattleMons species/stats/moves/pp/hp/level, gPlayerParty header + decrypted substructs, the
player controller function and the two menu cursors.

    gBattleMons      0x02023BE4  0x58 per battler: species, atk def spe spa spd (u16 @0..0xA), moves[4] @0xC, stat stages
                                 @0x18 (index 1..7 = atk def spe spa spd acc eva, 6 = neutral), ability @0x20, types @0x21/0x22,
                                 pp[4] @0x24, hp @0x28, level @0x2A, maxHP @0x2C, item @0x2E, status1 @0x4C
    gBattleTypeFlags 0x02022B4C  bit 0 double, bit 3 trainer
    gBattlerPartyIndexes 0x02023BCE  u16 per battler
    gPlayerParty     0x02024284  100 B per mon; level @0x54, hp @0x56, maxHP @0x58, status @0x50, plain substructs @0x20
    gEnemyParty      0x0202402C
    controller[0]    0x03004FE0  player battler's input handler: CHOOSE_ACTION / CHOOSE_MOVE below, anything else = busy
    action cursor    0x02023FF8  u8 per battler (0 Fight, 1 Bag, 2 Pokemon, 3 Run)
    move cursor      0x02023FFC  u8 per battler (0..3, 2x2 grid)
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))

import frontier_data as fd  # noqa: E402

CB2 = 0x030030F4
OVERWORLD_CB2 = 0x080565B5
BATTLE_MONS = 0x02023BE4
TYPE_FLAGS = 0x02022B4C
PARTY_IDX = 0x02023BCE
PLAYER_PARTY = 0x02024284
PLAYER_COUNT = 0x02024029
CONTROLLER = 0x03004FE0
ACTION_CURSOR = 0x02023FF8
MOVE_CURSOR = 0x02023FFC
PARTY_ORDER = 0x0203B0DC
PARTY_MENU_CB2 = 0x0811EBA1
CHOOSE_ACTION = 0x0802E439
CHOOSE_MOVE = 0x0802EA11


class Dex:
    """Species/move data from the ROM plus the English name tables (loaded once)."""

    def __init__(self, rom=os.path.join(ROOT, "build/Mercury_EN.gba")):
        self.species, self.moves = fd.load(rom)
        self.abilities = json.load(open(os.path.join(ROOT, "text/en/tables/abilities.json")))

    def sname(self, s):
        return self.species.get(s, {}).get("name", f"#{s}")

    def ability(self, a):
        return self.abilities.get(str(a), f"#{a}")


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def status_name(s1):
    if s1 & 7:
        return "sleep"
    for bit, name in ((0x08, "poison"), (0x10, "burn"), (0x20, "freeze"), (0x40, "paralysis"), (0x80, "toxic")):
        if s1 & bit:
            return name
    return None


def party_mon_data(b):
    """species, held item, moves, pp from a 100-byte party struct. The hack stores the substructs in plain fixed order
    G A E M (no personality-based shuffle, no XOR; checked 2026-10-23: Croconaw = 159 at +0x20, its moves at +0x2C)."""
    if not u32(b, 0) and not u32(b, 4):
        return None
    g, a = b[0x20:0x2C], b[0x2C:0x38]
    return {"species": u16(g, 0), "item": u16(g, 2), "moves": list(struct.unpack_from("<4H", a, 0)), "pp": list(a[8:12])}


def battler(e, dex, i):
    m = e.read(BATTLE_MONS + 0x58 * i, 0x58)
    sp = u16(m, 0)
    atk, df, spe, spa, spd = struct.unpack_from("<5H", m, 2)
    types = sorted({m[0x21], m[0x22]})
    moves = []
    for k, mv in enumerate(struct.unpack_from("<4H", m, 0xC)):
        if mv:
            moves.append({"slot": k, "id": mv, "pp": m[0x24 + k], **{x: dex.moves.get(mv, {}).get(x) for x in
                                                                    ("name", "power", "type", "accuracy", "priority", "split")}})
    hp, mhp = u16(m, 0x28), u16(m, 0x2C)
    return {"species": sp, "name": dex.sname(sp), "level": m[0x2A], "hp": hp, "max_hp": mhp,
            "hp_pct": round(100 * hp / mhp) if mhp else 0, "types": types, "ability": dex.ability(m[0x20]),
            "stats": {"atk": atk, "def": df, "spe": spe, "spa": spa, "spd": spd},
            "stages": dict(zip(("atk", "def", "spe", "spa", "spd", "acc", "eva"), (s - 6 for s in m[0x19:0x20]))),
            "status": status_name(u32(m, 0x4C)), "moves": moves}


def battle_order(e):
    """gBattlePartyCurrentOrder: menu position i shows party slot order[i] (two per byte, high nibble first)."""
    o = e.read(PARTY_ORDER, 3)
    return [o[i >> 1] >> 4 if i % 2 == 0 else o[i >> 1] & 0xF for i in range(6)]


def party(e, dex):
    """`slot` is always the real party slot. While the battle party menu is open the game physically reorders
    gPlayerParty into menu order (and restores it on close), so array index i then holds slot battle_order[i]."""
    n = min(e.read(PLAYER_COUNT, 1)[0], 6)
    raw = e.read(PLAYER_PARTY, 100 * 6)
    active = u16(e.read(PARTY_IDX, 2), 0)
    in_menu = u32(e.read(CB2, 4), 0) == PARTY_MENU_CB2
    order = battle_order(e) if in_menu else list(range(6))
    out = []
    for idx in range(n):
        i = order[idx]
        b = raw[100 * idx:100 * (idx + 1)]
        d = party_mon_data(b)
        if not d or not d["species"]:
            continue
        hp, mhp = u16(b, 0x56), u16(b, 0x58)
        sp = dex.species.get(d["species"], {})
        out.append({"slot": i, "species": d["species"], "name": dex.sname(d["species"]), "level": b[0x54], "hp": hp,
                    "max_hp": mhp, "hp_pct": round(100 * hp / mhp) if mhp else 0, "types": sp.get("types", []),
                    "status": status_name(u32(b, 0x50)), "active": i == active,
                    "stats": dict(zip(("atk", "def", "spe", "spa", "spd"), struct.unpack_from("<5H", b, 0x5A))),
                    "moves": [{"id": mv, "name": dex.moves.get(mv, {}).get("name")} for mv in d["moves"] if mv]})
    return out


def phase(e):
    """'overworld', 'choose_action', 'choose_move' or 'busy' (animations, text, other screens)."""
    if u32(e.read(CB2, 4), 0) == OVERWORLD_CB2:
        return "overworld"
    c = u32(e.read(CONTROLLER, 4), 0)
    return {CHOOSE_ACTION: "choose_action", CHOOSE_MOVE: "choose_move"}.get(c, "busy")


def snapshot(e, dex):
    flags = u32(e.read(TYPE_FLAGS, 4), 0)
    if flags & 1:
        raise NotImplementedError("double battles are not handled by the prototype")
    return {"kind": "trainer" if flags & 8 else "wild", "you": battler(e, dex, 0), "foe": battler(e, dex, 1),
            "party": party(e, dex)}
