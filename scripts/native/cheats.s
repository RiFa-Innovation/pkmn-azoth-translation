@ Cheat Device natives (scripts/cheats_build.py). Thumb, linked into the free pool; every hook jumps in from a patched literal or a
@ patched instruction pair and jumps back out, so the replaced game code never has to be copied.
@ Defined by the linker (--defsym): cheat_script (menu script), FLAG_SHINY, FLAG_SHINY_B0..B2 (rate index), FLAG_CANDY, FLAG_HEAL, FLAG_REPEL.
.syntax unified
.thumb
.global _start
.align 2
_start:

.equ GMAIN,          0x030030F0
.equ SAVEBLOCK2PTR,  0x0300500C
.equ FlagGet,        0x0806E6D1
.equ Random,         0x08044EC9
.equ SetBoxMonData,  0x080404D1
.equ SetBoxMonData_Pokemon, 0x0804037D          @ SetMonData(struct Pokemon *, field, data)
.equ HealPlayerParty, 0x080A0059
.equ RemoveBagItem,  0x0809A1D9
.equ ScriptContext_SetupScript, 0x08069AE5
.equ VarGet,         0x0806E569
.equ GetMonData,     0x0803FBE9
.equ CalculateMonStats, 0x0803E47D
.equ gPlayerParty,   0x02024284
.equ BASESTATS_PTR,  0x080001BC                 @ the hack keeps the gBaseStats pointer here (growth rate at +19, 28-byte entries)
.equ gExperienceTables, 0x09E0B258
.equ VarSet,         0x0806E585
.equ VAR_REPEL_STEP_COUNT, 0x4020
.equ ProcessPlayerFieldInput,   0x09D320B1            @ the hack's own implementation (the trampoline at 0x0806CAC8 loads it from a literal we replace)
.equ ReturnFromBattleToOverworld, 0x08015B59
.equ CreateBoxMon_resume, 0x09D09BC5            @ str r3, [sp, #20] ; b -> store the OT id
.equ CHEAT_KEYS, 0x104                          @ SELECT | R (SELECT+START is the hack's own Exp. Share toggle, #164)
.equ KEY_L, 0x200

@ r3 = function (Thumb address) ; bl here to call it with lr preserved by the caller
callr3:
    bx r3

@ r0 = flag -> r0 = 0/1 (clobbers r1-r3, lr)
flagget:
    push {lr}
    ldr r3, =FlagGet
    bl callr3
    pop {pc}
.ltorg

@ ---- hotkey: SELECT + R anywhere in the overworld opens the menu ----------------------------------------------------------------------
@ Replaces the literal in the ProcessPlayerFieldInput trampoline (r0 = struct FieldInput *).
.global pfi_wrap
.thumb_func
pfi_wrap:
    push {r0, lr}
    ldr r0, =FLAG_REPEL                         @ infinite repel: keep the step counter off zero (the walk decrements it, never to 0)
    bl flagget
    cmp r0, #0
    beq 2f
    ldr r0, =VAR_REPEL_STEP_COUNT
    movs r1, #255
    ldr r3, =VarSet
    bl callr3
2:
    ldr r1, =GMAIN
    ldrh r2, [r1, #0x2C]                        @ heldKeys
    ldrh r3, [r1, #0x2E]                        @ newKeys
    ldr r1, =KEY_L                              @ with L held SELECT+R belongs to the Patrol settings (L+R+SELECT)
    tst r2, r1
    bne 1f
    ldr r1, =CHEAT_KEYS
    ands r2, r1
    cmp r2, r1
    bne 1f
    tst r3, r1
    beq 1f
    ldr r0, =cheat_script
    ldr r3, =ScriptContext_SetupScript
    bl callr3
    add sp, #4                                  @ drop the saved r0
    movs r0, #1
    pop {pc}
1:  pop {r0, r1}
    mov lr, r1
    ldr r1, =ProcessPlayerFieldInput
    bx r1
.ltorg

@ ---- infinite Rare Candy: the Rare Candy flow's RemoveBagItem(item, 1) -------------------------------------------------------------------
@ Replaces the literal that flow loads. With the cheat on the call reports success without removing the item.
.global candy_wrap
.thumb_func
candy_wrap:
    push {r0, r1, lr}
    ldr r0, =FLAG_CANDY
    bl flagget
    cmp r0, #0
    bne 1f
    pop {r0, r1, r2}
    mov lr, r2
    ldr r3, =RemoveBagItem
    bx r3
1:  pop {r0, r1, r2}
    movs r0, #1
    bx r2
.ltorg

@ ---- heal after battle: gBattleMainFunc = ReturnFromBattleToOverworld (two literals) ---------------------------------------------------
.global heal_wrap
.thumb_func
heal_wrap:
    push {lr}
    ldr r0, =FLAG_HEAL
    bl flagget
    cmp r0, #0
    beq 1f
    ldr r3, =HealPlayerParty
    bl callr3
1:  pop {r0}
    mov lr, r0
    ldr r0, =ReturnFromBattleToOverworld
    bx r0
.ltorg

@ ---- shiny boost: inside the hack's CreateBoxMon (0x09D099F2), player-OT branch -------------------------------------------------------
@ Entered from 0x09D09BC8 in place of "r3 = SaveBlock2->playerTrainerId". Frame: [sp+16] personality (already stored in the box mon),
@ [sp+72] hasFixedPersonality. r5 = box mon. Out: r3 = OT id, resume at the `str r3, [sp, #20]`.
@ A rolled personality gets a new high half. A fixed one (wild encounters, set natures) is searched for a shiny value that keeps the
@ nature (personality % 25), the gender and the ability slot (low byte): only bits 8-31 move. (#139: wild Pokemon are created fixed.)
.global shiny_stub
.thumb_func
shiny_stub:
    ldr r3, =SAVEBLOCK2PTR
    ldr r2, [r3]
    ldrh r3, [r2, #12]                          @ secret id
    ldrh r1, [r2, #10]                          @ trainer id
    lsls r3, r3, #16
    orrs r3, r1                                 @ r3 = OT id (what the replaced code computed)
    push {r3}
    ldr r0, =FLAG_SHINY
    bl flagget
    cmp r0, #0
    beq 9f
    ldr r3, =Random
    bl callr3
    push {r4, r5}                               @ r5 (the box mon) is restored below
    movs r4, r0                                 @ r4 = the roll
    ldr r0, =FLAG_SHINY_B0                      @ rate index 0..6 = three flags (0 = 1 in 16, what the switch alone always meant)
    bl flagget
    movs r5, r0
    ldr r0, =FLAG_SHINY_B1
    bl flagget
    lsls r0, r0, #1
    adds r5, r5, r0
    ldr r0, =FLAG_SHINY_B2
    bl flagget
    lsls r0, r0, #2
    adds r5, r5, r0
    lsls r5, r5, #1
    ldr r1, =shiny_masks
    ldrh r1, [r1, r5]                           @ r1 = mask: shiny when (roll & mask) == 0
    ands r4, r1
    adds r0, r4, #0
    pop {r4, r5}
    cmp r0, #0
    bne 9f                                      @ not this time
    ldr r3, =Random
    bl callr3
    movs r1, #7
    ands r0, r1                                 @ r0 = 0..7 (the allowed shiny remainder)
    ldr r2, [sp, #0]                            @ OT id
    lsrs r1, r2, #16
    lsls r2, r2, #16
    lsrs r2, r2, #16
    eors r1, r2                                 @ r1 = tid ^ sid
    eors r0, r1                                 @ r0 = rem ^ tid ^ sid: high half = low half ^ r0
    add r3, sp, #76                             @ hasFixedPersonality (arg 5, +4 for the push)
    ldrb r3, [r3]
    cmp r3, #0
    bne 5f
    ldr r2, [sp, #20]                           @ personality (frame slot +16, +4 for the push)
    lsls r1, r2, #16
    lsrs r1, r1, #16                            @ r1 = low half (gender / ability slot stay as rolled)
    eors r0, r1                                 @ r0 = high half
    lsls r0, r0, #16
    orrs r0, r1
    b 6f
5:  push {r4-r7}                                @ fixed: personality at [sp, #36] now
    movs r4, r0                                 @ r4 = xor mask
    ldr r6, [sp, #36]
    lsrs r0, r6, #16
    movs r1, #11                                @ 65536 % 25
    muls r0, r1
    lsls r1, r6, #16
    lsrs r1, r1, #16
    adds r0, r0, r1
    movs r1, #25
    swi 6                                       @ Div: r1 = (hi * 11 + lo) % 25 = personality % 25
    movs r7, r1                                 @ r7 = nature
    lsls r6, r6, #24
    lsrs r6, r6, #24                            @ r6 = low byte (gender, ability slot)
    movs r5, #0                                 @ r5 = candidate 0..2047: second byte (bits 0-7) and remainder xor (bits 8-10)
1:  lsls r3, r5, #24
    lsrs r3, r3, #16
    orrs r3, r6                                 @ r3 = low half
    lsrs r2, r5, #8
    eors r2, r4
    eors r2, r3                                 @ r2 = high half
    movs r0, #11
    muls r0, r2
    adds r0, r0, r3
    movs r1, #25
    swi 6
    cmp r1, r7
    beq 3f
    adds r5, #1
    lsrs r0, r5, #11
    beq 1b
    ldr r0, [sp, #36]                           @ none found: leave it alone
    b 7f
3:  lsls r3, r5, #24
    lsrs r3, r3, #16
    orrs r3, r6
    lsrs r2, r5, #8
    eors r2, r4
    eors r2, r3
    lsls r0, r2, #16
    orrs r0, r3
7:  pop {r4-r7}
6:  str r0, [sp, #20]
    add r2, sp, #20
    movs r1, #0                                 @ MON_DATA_PERSONALITY
    adds r0, r5, #0
    ldr r3, =SetBoxMonData
    bl callr3
9:  pop {r3}
    ldr r2, =CreateBoxMon_resume
    bx r2
.ltorg
.align 2
shiny_masks:                                    @ 1 in 16, 64, 256, 1024, 4096, 2, always; the last slot is unused
    .hword 15, 63, 255, 1023, 4095, 1, 0, 15

@ ---- Set To Level Cap: the party slot is in var 0x8004; raises it to caps[badges] (caps from data/cheats_levelcaps.json) --------------
@ Result in var 0x800D: 0 = raised, 1 = already at or above the cap.
.global cap_apply
.thumb_func
cap_apply:
    push {r4-r7, lr}
    movs r4, #0
    ldr r5, =BADGE_FLAG
    movs r6, #8
1:  adds r0, r5, #0
    bl flagget
    adds r4, r4, r0
    adds r5, #1
    subs r6, #1
    bne 1b
    ldr r0, =cap_table
    ldrb r7, [r0, r4]                           @ r7 = cap (the table has 9 entries: 0..8 badges)
    ldr r0, =0x8004
    ldr r3, =VarGet
    bl callr3
    movs r1, #100
    muls r0, r1
    ldr r1, =gPlayerParty
    adds r5, r0, r1                             @ r5 = mon
    adds r0, r5, #0
    movs r1, #56                                @ MON_DATA_LEVEL
    movs r2, #0
    ldr r3, =GetMonData
    bl callr3
    cmp r0, r7
    bhs 8f
    adds r0, r5, #0
    movs r1, #11                                @ MON_DATA_SPECIES
    movs r2, #0
    ldr r3, =GetMonData
    bl callr3
    movs r1, #28
    muls r0, r1
    ldr r1, =BASESTATS_PTR
    ldr r1, [r1]
    adds r0, r0, r1
    ldrb r0, [r0, #19]                          @ growth rate
    lsls r0, r0, #8
    adds r0, r0, r7
    lsls r0, r0, #2
    ldr r1, =gExperienceTables
    ldr r0, [r0, r1]                            @ exp for the cap level
    push {r0}
    mov r2, sp
    adds r0, r5, #0
    movs r1, #25                                @ MON_DATA_EXP
    ldr r3, =SetBoxMonData_Pokemon
    bl callr3
    add sp, #4
    adds r0, r5, #0
    ldr r3, =CalculateMonStats
    bl callr3
    movs r1, #0
    b 9f
8:  movs r1, #1
9:  ldr r0, =0x800D
    ldr r3, =VarSet
    bl callr3
    pop {r4-r7, pc}
.ltorg
.align 2
cap_table:
.include "captable.inc"
.align 2
