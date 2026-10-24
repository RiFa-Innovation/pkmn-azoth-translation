"""Map-level route planner: BFS over the hack's warps and edge connections (from build/hackdb-*.sqlite).

Plans only which map to enter next; the tile-level walking stays with play.path_to. After each hop the caller re-plans from the map
it actually arrived on, so arrival coordinates never need computing. Edge kinds: ("warp", [(x, y), ...]) (every warp tile of the
current map that leads to the next map) and ("conn", dir) with dir 1 south, 2 north, 3 west, 4 east.
"""
import os
import sqlite3
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # repo root
DB = os.path.join(ROOT, "build/hackdb-Mercury_EN.sqlite")
DIR_KEY = {1: "D", 2: "U", 3: "L", 4: "R"}


class NavMap:
    def __init__(self, db=DB):
        c = sqlite3.connect(db)
        self.warps, self.conns = {}, {}
        for g, n, x, y, data in c.execute("select g,n,x,y,data from events where kind='warp'"):
            import json
            d = json.loads(data)
            if d["tg"] >= 127:  # dynamic / unset destinations
                continue
            self.warps.setdefault((g, n), {}).setdefault((d["tg"], d["tn"]), []).append((x, y))
        for g, n, d, tg, tn in c.execute("select g,n,dir,tg,tn from conns"):
            if d in DIR_KEY:
                self.conns.setdefault((g, n), []).append((d, (tg, tn)))

    def add_live(self, e):
        """Merge the current map's warps from RAM (maps the static dump misses, such as 42.3/42.4, have no DB rows)."""
        import struct
        import play
        hdr = e.read(play.MAPHDR, 0x1C)
        events = struct.unpack_from("<I", hdr, 4)[0]
        ev = e.read(events, 20)
        nwarp, wp = ev[1], struct.unpack_from("<I", ev, 8)[0]
        cur = play.pos(e)[2:]
        warps = {}
        for i in range(nwarp):
            wx, wy, _, _, mn, mg = struct.unpack("<hhBBBB", e.read(wp + 8 * i, 8))
            if mg < 127:
                warps.setdefault((mg, mn), []).append((wx, wy))
        if warps:
            self.warps[cur] = warps

    def neighbours(self, m):
        for dst, tiles in self.warps.get(m, {}).items():
            yield dst, ("warp", tiles)
        for d, dst in self.conns.get(m, []):
            yield dst, ("conn", d)

    def route(self, src, dst):
        """Shortest list of (edge, next_map) hops from src to dst, [] if equal, None if unreachable."""
        if src == dst:
            return []
        prev, q = {src: None}, deque([src])
        while q:
            m = q.popleft()
            for nxt, edge in self.neighbours(m):
                if nxt not in prev:
                    prev[nxt] = (m, edge)
                    if nxt == dst:
                        out, c = [], nxt
                        while prev[c]:
                            p, ed = prev[c]
                            out.append((ed, c))
                            c = p
                        return out[::-1]
                    q.append(nxt)
        return None

    def hops(self, src, dst):
        r = self.route(src, dst)
        return None if r is None else len(r)
