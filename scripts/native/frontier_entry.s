@ Entry table of the Spectrum Frontier natives (docs/BATTLE_FRONTIER_SPEC.md 6.2). Linked first, so the entries sit at fixed offsets from the base:
@   +0 fr_enter   +4 fr_leave   +8 fr_heal   +12 fr_gen_opponent   +16 fr_start_battle   +20 fr_pick_speech
@ Call from scripts with `callnative <base + offset>|1`. Each entry is a 2-byte branch plus a nop.
.syntax unified
.thumb
.global _start
_start:
    b fr_enter
    nop
    b fr_leave
    nop
    b fr_heal_entry
    nop
    b fr_gen_opponent
    nop
    b fr_start_battle
    nop
    b fr_pick_speech
    nop
