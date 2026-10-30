@ Partner Patrol natives, asm part (scripts/patrol_build.py; the logic is scripts/native/patrol.c).
@ Defined by the linker (--defsym): patrol_next (the ProcessPlayerFieldInput target to chain to), patrol_script (the result script).
.syntax unified
.thumb
.global _start
.align 2
_start:

.equ GMAIN,       0x030030F0
.equ QC_ACTIVE,   0x0203B743                    @ Quick Catch state struct (0x0203B730) + 0x13: 1 while the mode is on
.equ SELECT,      0x04
.equ LR_KEYS,     0x0300                        @ L | R

@ gcc on ARMv4T calls function pointers through __call_via_rN (no blx)
.macro callvia n
.global __call_via_r\n
.thumb_func
__call_via_r\n:
    bx r\n
.endm
callvia 0
callvia 1
callvia 2
callvia 3
callvia 4
callvia 5
callvia 6
callvia 7

@ SELECT inside Quick Catch: patrol_select() (C) returns 1 when it handled the press and started the result script.
@ Replaces the ProcessPlayerFieldInput trampoline literal; r0 = struct FieldInput *.
.global patrol_pfi
.thumb_func
patrol_pfi:
    push {r0, lr}
    bl patrol_watchdog                          @ every free frame: re-create the patrol task if the game's ResetTasks killed it
    ldr r1, =GMAIN
    ldrh r2, [r1, #0x2E]                        @ newKeys
    movs r3, #SELECT
    tst r2, r3
    beq 1f
    ldrh r2, [r1, #0x28]                        @ heldKeysRaw: L + R + SELECT anywhere in the overworld opens the settings
    ldr r3, =LR_KEYS
    ands r2, r3
    cmp r2, r3
    bne 3f
    bl patrol_open_settings
    cmp r0, #0
    beq 1f
    add sp, #4
    movs r0, #1
    pop {pc}
3:  ldr r1, =QC_ACTIVE
    ldrb r1, [r1]
    cmp r1, #1
    bne 1f
    bl patrol_select
    cmp r0, #0
    beq 1f
    add sp, #4
    movs r0, #1
    pop {pc}
1:  pop {r0, r1}
    mov lr, r1
    ldr r1, =patrol_next
    bx r1
.ltorg

@ The hack's follower code sets the walker's held movement through the ObjectEventSetHeldMovement literal (idle every frame, a step when the player
@ moves). While the patrol owns the walker (struct Patrol at 0x02022200: +0 active, +8 walker pointer) those calls for the walker are dropped; every
@ other object, and every call while no patrol runs, goes straight to the engine function.
.equ PATROL,  0x02022200
.equ GTASKS,  0x03005090
.equ FOLLOWER, 0x0203B818
.equ OBJECTS, 0x02036E38
.equ SetHeldMovement, 0x08063CA5
.global patrol_hold_wrap
.thumb_func
patrol_hold_wrap:
    push {r4}
    ldr r2, =FOLLOWER                           @ the hack's follower state: +1 = the walker's object index. If that slot is not a live object with local id 0xFE
    ldrb r3, [r2, #1]                           @ (the engine deleted the walker and a template NPC took the slot) the call is dropped: a stale index never moves an NPC
    cmp r3, #15
    bhi 4f
    movs r4, #36
    muls r3, r4
    ldr r4, =OBJECTS
    adds r3, r3, r4
    cmp r0, r3
    bne 4f
    ldrb r4, [r3]
    lsls r4, r4, #31
    beq 8f
    ldrb r4, [r3, #8]
    cmp r4, #0xFE
    bne 8f
4:  ldr r2, =PATROL
    ldrb r3, [r2]
    cmp r3, #0
    beq 9f
    ldr r3, [r2, #8]
    cmp r0, r3
    bne 9f
    ldrb r3, [r2, #20]                          @ the patrol task's id: it must be a live task running patrol_task, or the flag is stale
    cmp r3, #15
    bhi 9f
    movs r4, #40
    muls r3, r4
    ldr r4, =GTASKS
    adds r3, r3, r4
    ldrb r4, [r3, #4]                           @ isActive
    cmp r4, #0
    beq 9f
    ldr r4, [r3]                                @ func
    ldr r3, =patrol_task
    lsrs r4, r4, #1
    lsrs r3, r3, #1
    cmp r4, r3
    bne 9f
    pop {r4}
    movs r0, #0
    bx lr
8:  pop {r4}
    movs r0, #0
    bx lr
9:  pop {r4}
    ldr r3, =SetHeldMovement
    bx r3
.ltorg
