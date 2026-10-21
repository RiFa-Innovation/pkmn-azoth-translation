.syntax unified
.thumb
.global _start
_start:
    push {r4-r7, lr}
    @ sTrainerTowerOpponent = AllocZeroed(0x40)
    movs r0, #0x40
    ldr r3, =0x08002BB1
    bl call_r3
    ldr r1, =0x0203F45C
    str r0, [r1]
    adds r4, r0, #0
    @ name "Test"
    ldr r1, =name
    movs r2, #0
1:  ldrb r3, [r1, r2]
    strb r3, [r4, r2]
    adds r2, #1
    cmp r3, #0xFF
    bne 1b
    @ speech words 0xFFFF (4 arrays of 6 u16 from +0x0C)
    movs r2, #0x0C
    ldr r3, =0xFFFF
2:  strh r3, [r4, r2]
    adds r2, #2
    cmp r2, #0x3C
    blt 2b
    adds r6, r4, #0
    adds r6, #0x3C
    movs r0, #0
    strb r0, [r6, #0]
    ldr r0, =FACILITYCLASS
    strb r0, [r6, #1]
    movs r0, #0
    strb r0, [r6, #2]
    @ ZeroEnemyPartyMons()
    ldr r3, =0x0803DA35
    bl call_r3
    @ three mons
    movs r5, #0
3:  movs r0, #100
    muls r0, r5
    ldr r1, =0x0202402C
    adds r0, r0, r1
    ldr r2, =species
    lsls r1, r5, #1
    ldrh r1, [r2, r1]
    movs r2, #50
    movs r3, #31
    sub sp, #16
    movs r6, #0
    str r6, [sp, #0]
    str r6, [sp, #4]
    str r6, [sp, #8]
    str r6, [sp, #12]
    ldr r7, =0x0803DA55
    bl call_r7
    add sp, #16
    adds r5, #1
    cmp r5, #3
    blt 3b
    @ gBattleTypeFlags = TRAINER | TRAINER_TOWER
    ldr r0, =BTYPE
    ldr r1, =0x02022B4C
    str r0, [r1]
    ldr r0, =OPP
    ldr r1, =0x020386AE
    strh r0, [r1]
    @ CreateTask(Task_DoTrainerTowerBattle, 1)
    ldr r0, =0x0815E124+1
    movs r1, #1
    ldr r3, =0x0807741D
    bl call_r3
    movs r0, #0
    ldr r3, =0x08044091
    bl call_r3
    ldr r3, =0x08080061
    bl call_r3
    ldr r3, =0x080D08B9
    bl call_r3
    pop {r4-r7}
    pop {r0}
    bx r0
call_r3: bx r3
call_r7: bx r7
.ltorg
.align 2
species: .hword 3, 6, 9
name: .byte 0xCE,0xD9,0xE7,0xE8,0xFF
.equ FACILITYCLASS, 8
.equ OPP, 100
.equ BTYPE, 0x108
