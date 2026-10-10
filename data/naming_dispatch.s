@ DoNamingScreen dispatcher (see insert.py naming_dispatch). Placed in free
@ space; position independent (absolute targets come from the literal pool).
@
@ entry       : FireRed's DoNamingScreen entry 0x0809D954 (b +12 -> long jump here)
@ entry+8     : FireRed's screen unconditionally (the intro's player naming;
@               the hack's DoNamingScreen entry 0x09FF5EB4 long-jumps here)
@ hack_nostore: the hack's screen; the old hook's literal (0x0809D95C) points
@               here for the hack routines that call 0x0809D956 (hook + 2)
@
@ Templates 1-4 (box, nicknames, rival) run FireRed's screen: its prologue up
@ to the Alloc call is replayed (0x0809D960..0x0809D96F holds the jump here),
@ then execution continues at 0x0809D972.
@ Template 0 (the hack's birthday-month etc. prompts reuse it and then write
@ hack-only fields) and the hack's templates 5-9 go to the hack's screen as
@ the old hook did (str r0,[sp]; r0 = hack fn), replaying the first eight
@ instructions of the hack's function (overwritten by the stub), then
@ continuing at 0x09FF5EC4.
        .syntax unified
        .thumb
        .text
entry:
        cmp     r0, #0
        beq     to_hack
        cmp     r0, #5
        bhs     to_hack
vanilla:                                @ entry+8
        push    {r4, r5, r6, r7, lr}    @ FireRed DoNamingScreen prologue
        mov     r7, r8
        push    {r7}
        mov     r8, r1
        lsls    r0, r0, #24
        lsrs    r7, r0, #24
        lsls    r2, r2, #16
        lsrs    r5, r2, #16
        lsls    r3, r3, #16
        lsrs    r6, r3, #16
        ldr     r4, =0x0203998C         @ &sNamingScreen
        movs    r0, #0xF2
        lsls    r0, r0, #5              @ sizeof(struct NamingScreenData)
        ldr     r3, =0x08002B9D         @ Alloc
        bl      call_r3
        ldr     r1, =0x0809D973         @ back to FireRed: str r0,[r4] ...
        bx      r1
to_hack:
        str     r0, [sp]
hack_nostore:
        ldr     r0, =0x09FF5EB5         @ as the old hook left r0
        push    {r0, r1, r2, r4, r5, r6, r7, lr}   @ the hack's prologue
        movs    r6, r3
        add     r3, sp, #0x20
        ldrb    r5, [r3]                @ template, from the caller's [sp]
        ldr     r0, =0x2718
        ldr     r3, =0x08002BB1         @ Alloc
        str     r1, [sp, #4]
        movs    r7, r2
        ldr     r4, =0x09FF5EC5         @ continue in the hack's function
        bx      r4
call_r3:
        bx      r3
        .pool
