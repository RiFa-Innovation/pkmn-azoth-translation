@ fr_start_battle (docs/BATTLE_FRONTIER_SPEC.md 6.4, mechanism M3): starts a facility battle against a shell trainer slot whose party pointer is in RAM.
@   in : 0x8000 = shell trainer id, 0x8001 = 1 for a double battle
@ Sets gTrainerBattleOpponent_A and gBattleTypeFlags = TRAINER | BATTLE_TOWER (| DOUBLE), then starts the vanilla Trainer Tower battle sequence.
@ The script must `waitstate` after the callnative; the battle returns to the script when it ends (gBattleOutcome 0x02023E8A).
.syntax unified
.thumb
.ifndef START_FLAGS
.equ START_FLAGS, 0x108
.endif
.global fr_start_battle
fr_start_battle:
    push {r4-r7, lr}
    ldr r7, =0x020370B8
    ldrh r0, [r7, #0]
    ldr r1, =0x020386AE          @ gTrainerBattleOpponent_A
    strh r0, [r1]
    ldrh r2, [r7, #2]
    ldr r0, =START_FLAGS
    cmp r2, #0
    beq 1f
    adds r0, #1                  @ | BATTLE_TYPE_DOUBLE
1:  ldr r1, =0x02022B4C          @ gBattleTypeFlags
    str r0, [r1]
    ldr r0, =0x0815E125          @ Task_DoTrainerTowerBattle
    movs r1, #1
    ldr r3, =0x0807741D          @ CreateTask
    bl call_r3
    movs r0, #0
    ldr r3, =0x08044091          @ PlayMapChosenOrBattleBGM
    bl call_r3
    ldr r3, =0x08080061          @ BattleSetup_GetBattleTowerBattleTransition
    bl call_r3
    ldr r3, =0x080D08B9          @ BattleTransition_StartOnField
    bl call_r3
    pop {r4-r7}
    pop {r0}
    bx r0
call_r3: bx r3
.ltorg
