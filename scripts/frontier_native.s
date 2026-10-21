@ Spectrum Frontier native helpers (docs/BATTLE_FRONTIER_SPEC.md 6.2/6.3). Thumb, linked at its final address by scripts/frontier_native.py.
@
@ Called from scripts with `callnative <fr_enter|1>` etc. Arguments travel in the script special vars, results too:
@
@   fr_enter   in : 0x8000 = n (number of picks, 1..4), 0x8001.. = pick slots (original party indexes, 0xFF = unused)
@              out: 0x800D (Result) = 0 ok | 1 bad pick count/slot | 2 duplicate | 3 egg or empty slot
@                   0x8005 = permutation LO (slots 0-4, 3 bits each), 0x8006 = permutation HI (bit 15 valid, bits 3-5 original count, bits 0-2 slot 5)
@   fr_leave   in : 0x8005 / 0x8006 as returned by fr_enter. HI without bit 15 -> no-op (idempotent)
@              out: 0x8006 = 0 (marker cleared), 0x800D = 0
@   fr_heal    full heal of gPlayerParty (HealPlayerParty)
@
@ The party is reordered so the picks come first, gPlayerPartyCount is set to n, the picks get Lv 50 stats (level byte + the six stats are
@ written directly, because CalculateMonStats would recompute the level from EXP), and the party is healed. The other mons stay in slots n..5
@ (SavePlayerParty copies all six slots). fr_leave puts every mon back, runs the engine's CalculateMonStats on all of them (level from EXP,
@ stats from level, i.e. exactly the real values) and heals.

.syntax unified
.thumb
.global _start
_start:                         @ jump table: +0 fr_enter, +4 fr_leave, +8 fr_heal (each entry is a `b`)
    b fr_enter
    nop
    b fr_leave
    nop
    b fr_heal_entry
    nop


.macro jlt t
    bge 9999f
    b \t
9999:
.endm
.macro jgt t
    ble 9998f
    b \t
9998:
.endm
.macro jge t
    blt 9997f
    b \t
9997:
.endm
.macro jne t
    beq 9996f
    b \t
9996:
.endm
.macro jeq t
    bne 9995f
    b \t
9995:
.endm

.equ GetMonData,          0x0803FBE9
.equ SetMonData,          0x0804037D
.equ CalculateMonStats,   0x0803E47D
.equ GetNature,           0x08042E9D
.equ ModifyStatByNature,  0x08043699
.equ AllocZeroed,         0x08002BB1
.equ Free,                0x08002BC5
.equ HealPlayerParty,     0x080A0059
.equ gPlayerParty,        0x02024284
.equ gPlayerPartyCount,   0x02024029
.equ gSpecialVars,        0x020370B8          @ 0x8000 at +0, 0x8005 at +10, 0x8006 at +12; gSpecialVar_Result is at +0x18
.equ BASESTATS,           0x0976DFBC          @ ROM 0x08000000 + 0x176DFBC: 28-byte entries indexed by species
.equ PARTY_SIZE_B,        600
.equ MON_SIZE,            100

@ ---------------------------------------------------------------------------------------------------------------
fr_heal_entry:
    push {lr}
    ldr r3, =HealPlayerParty
    bl call_r3
    pop {r0}
    bx r0

@ ---------------------------------------------------------------------------------------------------------------
@ void fr_scale_mon(struct Pokemon *mon /*r0*/, u32 level /*r1*/)
@ Writes level, max HP and the five stats for `level` using the engine's own formula and nature handling.
fr_scale_mon:
    push {r4-r7, lr}
    sub sp, #32                  @ [0]=value buffer, [4]=level, [8]=nature, [12]=species, [16]=stat loop counter
    adds r4, r0, #0              @ mon
    str r1, [sp, #4]
    @ species
    adds r0, r4, #0
    movs r1, #11
    movs r2, #0
    ldr r3, =GetMonData
    bl call_r3
    str r0, [sp, #12]
    @ r5 = &baseStats[species]
    movs r1, #28
    muls r0, r1
    ldr r5, =BASESTATS
    adds r5, r5, r0
    @ nature
    adds r0, r4, #0
    ldr r3, =GetNature
    bl call_r3
    str r0, [sp, #8]
    @ ---- max HP: ((2*base + iv + ev/4) * L / 100) + L + 10 (Shedinja = 1)
    ldr r0, [sp, #12]
    ldr r1, =292
    cmp r0, r1
    bne 10f
    movs r0, #1
    b 11f
10: movs r6, #0                  @ base offset 0 = HP
    ldrb r0, [r5, r6]
    lsls r0, r0, #1
    str r0, [sp, #20]            @ 2*base
    adds r0, r4, #0
    movs r1, #39                 @ HP IV
    movs r2, #0
    ldr r3, =GetMonData
    bl call_r3
    ldr r1, [sp, #20]
    adds r1, r1, r0
    str r1, [sp, #20]
    adds r0, r4, #0
    movs r1, #26                 @ HP EV
    movs r2, #0
    ldr r3, =GetMonData
    bl call_r3
    lsrs r0, r0, #2
    ldr r1, [sp, #20]
    adds r0, r0, r1
    ldr r1, [sp, #4]
    muls r0, r1
    movs r1, #100
    swi 6
    ldr r1, [sp, #4]
    adds r0, r0, r1
    adds r0, #10
11: str r0, [sp, #0]
    adds r0, r4, #0
    movs r1, #58                 @ MAX_HP
    mov r2, sp
    ldr r3, =SetMonData
    bl call_r3
    @ ---- the five stats
    movs r6, #0
    str r6, [sp, #16]
12: ldr r6, [sp, #16]
    ldr r7, =stat_table
    lsls r0, r6, #2
    adds r6, r0, r6              @ r6 = 5 * i
    adds r7, r7, r6              @ r7 -> {base_off, iv_field, ev_field, stat_idx, set_field}
    ldrb r0, [r7, #0]
    ldrb r0, [r5, r0]            @ base stat
    lsls r0, r0, #1
    str r0, [sp, #20]
    adds r0, r4, #0
    ldrb r1, [r7, #1]
    movs r2, #0
    ldr r3, =GetMonData
    bl call_r3                   @ IV
    ldr r1, [sp, #20]
    adds r1, r1, r0
    str r1, [sp, #20]
    adds r0, r4, #0
    ldrb r1, [r7, #2]
    movs r2, #0
    ldr r3, =GetMonData
    bl call_r3                   @ EV
    lsrs r0, r0, #2
    ldr r1, [sp, #20]
    adds r0, r0, r1
    ldr r1, [sp, #4]
    muls r0, r1
    movs r1, #100
    swi 6
    adds r1, r0, #5              @ n
    ldr r0, [sp, #8]             @ nature
    ldrb r2, [r7, #3]            @ stat index
    ldr r3, =ModifyStatByNature
    bl call_r3
    str r0, [sp, #0]
    adds r0, r4, #0
    ldrb r1, [r7, #4]
    mov r2, sp
    ldr r3, =SetMonData
    bl call_r3
    ldr r6, [sp, #16]
    adds r6, #1
    str r6, [sp, #16]
    cmp r6, #5
    blt 12b
    @ ---- level byte
    ldr r0, [sp, #4]
    str r0, [sp, #0]
    adds r0, r4, #0
    movs r1, #56
    mov r2, sp
    ldr r3, =SetMonData
    bl call_r3
    add sp, #32
    pop {r4-r7}
    pop {r0}
    bx r0

@ ---------------------------------------------------------------------------------------------------------------
@ fr_enter
fr_enter:
    push {r4-r7, lr}
    sub sp, #44                  @ [0..5] perm bytes, [8] n, [12] origCount, [16..] picks (4), [32] tmp ptr
    ldr r7, =gSpecialVars
    ldrh r0, [r7, #0]            @ n
    str r0, [sp, #8]
    ldr r1, =gPlayerPartyCount
    ldrb r1, [r1]
    str r1, [sp, #12]
    cmp r0, #1
    jlt err1
    cmp r0, #4
    jgt err1
    cmp r0, r1
    jgt err1
    @ collect and validate picks
    movs r4, #0                  @ i
    movs r6, #0                  @ bitmask of used slots
1:  lsls r2, r4, #1
    adds r2, #2
    ldrh r3, [r7, r2]            @ pick i
    ldr r1, [sp, #12]
    cmp r3, r1
    jge err1
    movs r2, #1
    lsls r2, r3
    tst r6, r2
    jne err2
    orrs r6, r2
    mov r5, sp
    adds r5, #16
    strb r3, [r5, r4]
    @ egg / empty check
    movs r0, #MON_SIZE
    muls r0, r3
    ldr r2, =gPlayerParty
    adds r5, r0, r2              @ mon
    adds r0, r5, #0
    movs r1, #11
    movs r2, #0
    ldr r3, =GetMonData
    bl call_r3
    cmp r0, #0
    jeq err3
    adds r0, r5, #0
    movs r1, #45                 @ IS_EGG
    movs r2, #0
    ldr r3, =GetMonData
    bl call_r3
    cmp r0, #0
    jne err3
    ldr r7, =gSpecialVars
    adds r4, #1
    ldr r0, [sp, #8]
    cmp r4, r0
    blt 1b
    @ perm[0..n-1] = picks; then the remaining indexes 0..5 ascending
    movs r4, #0
2:  mov r5, sp
    adds r5, #16
    ldrb r0, [r5, r4]
    mov r5, sp
    strb r0, [r5, r4]
    adds r4, #1
    ldr r0, [sp, #8]
    cmp r4, r0
    blt 2b
    movs r3, #0                  @ candidate index
3:  movs r2, #1
    lsls r2, r3
    tst r6, r2
    bne 4f
    mov r5, sp
    strb r3, [r5, r4]
    adds r4, #1
4:  adds r3, #1
    cmp r3, #6
    blt 3b
    @ tmp = AllocZeroed(600); copy party -> tmp
    ldr r0, =PARTY_SIZE_B
    ldr r3, =AllocZeroed
    bl call_r3
    str r0, [sp, #32]
    ldr r1, =gPlayerParty
    ldr r2, =PARTY_SIZE_B
    bl copy_bytes                @ copy r2 bytes from r1 to r0
    @ gPlayerParty[i] = tmp[perm[i]]
    movs r4, #0
5:  mov r5, sp
    ldrb r0, [r5, r4]            @ perm[i]
    movs r1, #MON_SIZE
    muls r0, r1
    ldr r1, [sp, #32]
    adds r1, r1, r0              @ src = tmp + perm[i]*100
    movs r0, #MON_SIZE
    muls r0, r4
    ldr r2, =gPlayerParty
    adds r0, r0, r2              @ dst
    movs r2, #MON_SIZE
    bl copy_bytes
    adds r4, #1
    cmp r4, #6
    blt 5b
    ldr r0, [sp, #32]
    ldr r3, =Free
    bl call_r3
    @ scale the picks to Lv 50
    movs r4, #0
6:  movs r0, #MON_SIZE
    muls r0, r4
    ldr r2, =gPlayerParty
    adds r0, r0, r2
    movs r1, #50
    bl fr_scale_mon
    adds r4, #1
    ldr r0, [sp, #8]
    cmp r4, r0
    blt 6b
    @ truncate the party and heal it
    ldr r0, [sp, #8]
    ldr r1, =gPlayerPartyCount
    strb r0, [r1]
    ldr r3, =HealPlayerParty
    bl call_r3
    @ pack permutation: LO = perm[0..4] 3 bits each, HI = perm[5] | origCount << 3 | 0x8000
    mov r5, sp
    movs r0, #0
    movs r4, #4
7:  lsls r0, r0, #3
    ldrb r1, [r5, r4]
    orrs r0, r1
    subs r4, #1
    bpl 7b
    ldr r7, =gSpecialVars
    strh r0, [r7, #10]           @ 0x8005
    ldrb r0, [r5, #5]
    ldr r1, [sp, #12]
    lsls r1, r1, #3
    orrs r0, r1
    movs r1, #1
    lsls r1, r1, #15
    orrs r0, r1
    strh r0, [r7, #12]           @ 0x8006
    movs r0, #0
    b done_enter
err1: movs r0, #1
    b done_enter
err2: movs r0, #2
    b done_enter
err3: movs r0, #3
done_enter:
    ldr r7, =gSpecialVars
    strh r0, [r7, #0x18]         @ Result
    add sp, #44
    pop {r4-r7}
    pop {r0}
    bx r0

@ ---------------------------------------------------------------------------------------------------------------
@ fr_leave
fr_leave:
    push {r4-r7, lr}
    sub sp, #44                  @ [0..5] perm, [12] origCount, [32] tmp
    ldr r7, =gSpecialVars
    ldrh r1, [r7, #12]           @ HI
    movs r0, #1
    lsls r0, r0, #15
    tst r1, r0
    beq leave_noop
    ldrh r0, [r7, #10]           @ LO
    @ unpack perm[0..4]
    mov r5, sp
    movs r4, #0
8:  movs r2, #7
    ands r2, r0
    strb r2, [r5, r4]
    lsrs r0, r0, #3
    adds r4, #1
    cmp r4, #5
    blt 8b
    movs r2, #7
    ands r2, r1
    strb r2, [r5, #5]
    lsrs r2, r1, #3
    movs r3, #7
    ands r2, r3
    str r2, [sp, #12]
    @ tmp = copy of the party; gPlayerParty[perm[i]] = tmp[i]
    ldr r0, =PARTY_SIZE_B
    ldr r3, =AllocZeroed
    bl call_r3
    str r0, [sp, #32]
    ldr r1, =gPlayerParty
    ldr r2, =PARTY_SIZE_B
    bl copy_bytes
    movs r4, #0
9:  mov r5, sp
    ldrb r0, [r5, r4]            @ perm[i]
    movs r1, #MON_SIZE
    muls r0, r1
    ldr r2, =gPlayerParty
    adds r0, r0, r2              @ dst = party[perm[i]]
    movs r1, #MON_SIZE
    muls r1, r4
    ldr r2, [sp, #32]
    adds r1, r1, r2              @ src = tmp[i]
    movs r2, #MON_SIZE
    bl copy_bytes
    adds r4, #1
    cmp r4, #6
    blt 9b
    ldr r0, [sp, #32]
    ldr r3, =Free
    bl call_r3
    @ engine recalculation (level from EXP) for every occupied slot
    movs r4, #0
13: movs r5, #MON_SIZE
    muls r5, r4
    ldr r2, =gPlayerParty
    adds r5, r5, r2
    adds r0, r5, #0
    movs r1, #11
    movs r2, #0
    ldr r3, =GetMonData
    bl call_r3
    cmp r0, #0
    beq 14f
    adds r0, r5, #0
    ldr r3, =CalculateMonStats
    bl call_r3
14: adds r4, #1
    cmp r4, #6
    blt 13b
    ldr r0, [sp, #12]
    ldr r1, =gPlayerPartyCount
    strb r0, [r1]
    ldr r3, =HealPlayerParty
    bl call_r3
leave_noop:
    ldr r7, =gSpecialVars
    movs r0, #0
    strh r0, [r7, #12]           @ clear the marker
    strh r0, [r7, #0x18]         @ Result = 0
    add sp, #44
    pop {r4-r7}
    pop {r0}
    bx r0

@ ---------------------------------------------------------------------------------------------------------------
@ copy_bytes: r0 = dst, r1 = src, r2 = count (clobbers r2, r3)
copy_bytes:
    cmp r2, #0
    beq 1f
0:  ldrb r3, [r1]
    strb r3, [r0]
    adds r0, #1
    adds r1, #1
    subs r2, #1
    bne 0b
1:  bx lr

call_r3: bx r3

.ltorg
.align 2
stat_table:                      @ base offset, IV field, EV field, stat index, SetMonData field
    .byte 1, 40, 27, 1, 59       @ attack
    .byte 2, 41, 28, 2, 60       @ defense
    .byte 3, 42, 29, 3, 61       @ speed
    .byte 4, 43, 30, 4, 62       @ special attack
    .byte 5, 44, 31, 5, 63       @ special defense
.align 2
