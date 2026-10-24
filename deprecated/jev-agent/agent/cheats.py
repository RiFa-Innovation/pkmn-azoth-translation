"""Playtest cheats that write the party straight into RAM (the agent is test tooling; nothing here ships).

heal_party: HP to max, status cleared, PP to max for every move (base PP from the ROM move table, PP-Up bonus bits from the growth
substruct). Overworld only: in battle the live copy is gBattleMons, which this does not touch. The party structs carry no checksum in
this hack (the checksum word at +0x1C reads 0 on every member, checked 2026-10-24), so nothing else needs rewriting.
"""
import struct

import observe as ob

HP, MAX_HP, STATUS = 0x56, 0x58, 0x50
BONUS, MOVES, PP = 0x28, 0x2C, 0x34


def heal_party(e, dex):
    """Returns how many members were changed."""
    n = min(e.read(ob.PLAYER_COUNT, 1)[0], 6)
    changed = 0
    for i in range(n):
        base = ob.PLAYER_PARTY + 100 * i
        b = e.read(base, 100)
        if not ob.party_mon_data(b):
            continue
        new = bytearray(b)
        new[HP:HP + 2] = b[MAX_HP:MAX_HP + 2]
        new[STATUS:STATUS + 4] = bytes(4)
        for k, mv in enumerate(struct.unpack_from("<4H", b, MOVES)):
            if mv:
                bp = dex.moves.get(mv, {}).get("pp") or b[PP + k]
                new[PP + k] = bp * (5 + ((b[BONUS] >> (2 * k)) & 3)) // 5
        if new != b:
            e.write(base + 0x20, bytes(new[0x20:]))  # substructs (PP) and the party fields (status, HP) all sit at +0x20 or later
            changed += 1
    return changed
