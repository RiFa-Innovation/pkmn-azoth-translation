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
    ldr r1, =GMAIN
    ldrh r2, [r1, #0x2E]                        @ newKeys
    movs r3, #SELECT
    tst r2, r3
    beq 1f
    ldr r1, =QC_ACTIVE
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
