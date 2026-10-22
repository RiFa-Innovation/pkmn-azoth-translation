@ Entry table of the Spectrum Frontier natives (docs/BATTLE_FRONTIER_SPEC.md 6.2). Linked first, so the entries sit at fixed offsets from the base.
@ Each entry is 8 bytes (ldr r0, [pc]; bx r0; .word target|1): a Thumb branch only reaches +-2 KB and the image is larger than that.
@   +0 fr_enter   +8 fr_leave   +16 fr_heal   +24 fr_gen_opponent   +32 fr_start_battle   +40 fr_pick_speech   +48 fr_gen_brain   +56 fr_brain_speech   +64 fr_count_fainted
@ Call from scripts with `callnative <base + offset>|1` (frontier_native.ENTRY_STRIDE = 8).
.syntax unified
.thumb
.global _start
.align 2
_start:
    ldr r0, [pc, #0]
    bx r0
    .word fr_enter + 1
    ldr r0, [pc, #0]
    bx r0
    .word fr_leave + 1
    ldr r0, [pc, #0]
    bx r0
    .word fr_heal_entry + 1
    ldr r0, [pc, #0]
    bx r0
    .word fr_gen_opponent + 1
    ldr r0, [pc, #0]
    bx r0
    .word fr_start_battle + 1
    ldr r0, [pc, #0]
    bx r0
    .word fr_pick_speech + 1
    ldr r0, [pc, #0]
    bx r0
    .word fr_gen_brain + 1
    ldr r0, [pc, #0]
    bx r0
    .word fr_brain_speech + 1
    ldr r0, [pc, #0]
    bx r0
    .word fr_count_fainted + 1
