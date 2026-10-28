"""Which build is being made: the translation (default; what the numbered betas ship) or the River Edition (RHT_EDITION=river).

Both editions carry the Spectrum Frontier post-game; the River Edition adds the fan-made Chapter 2, Route 28, Mt. Silver and Red.
The map/event spec each one applies lives in data/new_maps.translation.json (Frontier only) or data/new_maps.json (everything).
"""
import os

EDITION = os.environ.get("RHT_EDITION", "translation")
assert EDITION in ("translation", "river"), f"RHT_EDITION must be 'translation' or 'river', not {EDITION!r}"


def new_maps_path():
    return "data/new_maps.json" if EDITION == "river" else "data/new_maps.translation.json"


# The Cheat Device (docs/CHEATS.md) is an optional add-on: only builds made with RHT_CHEATS=1 carry it. Plain betas and River releases do not.
CHEATS = os.environ.get("RHT_CHEATS") == "1"
