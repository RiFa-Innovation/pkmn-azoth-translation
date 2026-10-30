/* Partner Patrol, M1: the instant strike (docs/PARTNER_PATROL_SPEC.md). Freestanding Thumb code linked by scripts/patrol_build.py.
 *
 * SELECT in Quick Catch -> patrol_select(): the partner (the party member the walker shows) fights the aimed target in a simulated
 * fight, gets XP, the target is removed, the result script reports it. A shiny roll stops the patrol and starts a real wild battle instead.
 *
 * Results in the script vars: 0x8004 = result (1 won, 2 retreated, 3 shiny -> real battle, 4 partner too hurt), 0x8005 = EXP gained,
 * 0x8006 = partner party slot, 0x8007 = target species. The fight ignores moves (River's rule): each side attacks with its best own type
 * (STAB) against the other's types, through the game's type chart, Scarlet/Violet style.
 *
 * M2: the win pays what a Quick Catch win pays (docs/PARTNER_PATROL_SPEC.md 13): one roll 0-99 -> 0-19 an Exp. Candy by the target's level (XS <20,
 * S <40, M <60, L <80, XL), 20-49 one of ten Berries, 50-99 EV Feathers (the hack's own function `0x09D2ADA5`), plus the species' held items
 * (item1 50% / item2 5%, always item1 when both are equal). Level-ups learn their moves and flag the partner for the engine's evolution check.
 * Extra script vars (one fight): 0x8000 new level (0 = none), 0x8001/0x8002 moves learned, 0x8003 held item dropped (0 = none), 0x8008-0x800B reward
 * slots A and B (item id, quantity; quantity 0 = no room in the bag). M4 sums these up over a whole patrol (see patrol_sum_step).
 */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef signed char s8;
typedef short s16;
typedef int s32;

#define QC        ((volatile u8 *)0x0203B730)        /* Quick Catch state (var 0x51DE storage): +6 aimed object, +7 its local id, +0x13 active, +0x18 species */
#define FOLLOWER  ((volatile u8 *)0x0203B818)        /* follower state: +1 walker's object index */
#define OBJECTS   0x02036E38                         /* gObjectEvents, 36 bytes each; +5 graphics id, +0x1D level of a visible Pokemon */
#define PARTY     0x02024284                         /* 100 bytes each */
#define ENEMY     ((void *)0x0202402C)               /* gEnemyParty[0] */
#define TASKS     0x03005090                         /* 40 bytes each, func at +0 */
#define SPECIALS  ((volatile u16 *)0x020370B8)       /* script vars 0x8000.. */
#define LASTTALKED (*(volatile u16 *)0x020370D2)     /* var 0x800F */
#define V800D     (*(volatile u16 *)0x020370D0)     /* gSpecialVar_Result. NOTE: SPECIALS[n] is only the script var 0x8000+n for n <= 11; 0x800C is gSpecialVar_Facing at 0x020370D4 and is never written */
#define LEVELEDUP (*(volatile u8 *)0x03004FD4)       /* gLeveledUpInBattle: bit per party slot, read by the engine's post-battle evolution check */
#define BERRIES   ((const volatile u16 *)(0x09DE4674 + 8)) /* ten berry item ids (0x85-0x8E) */
/* The patrol's whole private state: one 512-byte block of the unused link receive buffer (0x02022200-0x020223FF; a write-watch over a full session of
 * menus, walking, a battle and a strike saw no other writer). Offsets 0 (active), 8 (walker pointer) and 20 (task id) are read by patrol.s. */
struct Patrol {
    u8 active;          /* +0  1 while the patrol owns the walker */
    u8 phase;           /* +1  PH_* */
    u8 walker;          /* +2  object index of the walker */
    u8 target;          /* +3  object index of the target */
    u8 target_local;    /* +4  its local id (identity check + removal) */
    u8 slot;            /* +5  partner party slot */
    s8 map_group;       /* +6  the map the patrol started on */
    s8 map_num;         /* +7 */
    u32 walker_ptr;     /* +8  address of the walker's object event */
    u16 timer;          /* +12 frames in the current phase */
    u16 steps;          /* +14 steps taken */
    u8 fails;           /* +16 consecutive steps without progress */
    u8 level;           /* +17 target level */
    u16 species;        /* +18 target species */
    u8 task;            /* +20 task id of patrol_task (patrol.s checks it) */
    u8 reason;          /* +21 why the patrol ended (R_*) */
    u8 kills;           /* +22 targets beaten in this patrol */
    u8 level_now;       /* +23 the partner's level after its last level-up (0 = none) */
    u8 nmoves;          /* +24 moves learned (up to 6 listed) */
    u8 nitems;          /* +25 distinct items found (up to 8 listed) */
    u8 sum_i;           /* +26 summary iterator */
    u8 pad;             /* +27 */
    u16 exp_total;      /* +28 */
    u16 total;          /* +30 frames since the patrol started */
    u16 moves[6];       /* +32 */
    u16 items[16];      /* +44 8 x (item id, quantity; bit 15 of the quantity = no room in the bag) */
    u8 grid[169];       /* +76 breadth-first search window (13 x 13): 0 unseen, 1-4 direction taken, 5 blocked, 6 start */
    u8 queue[169];      /* +245 */
};
#define P ((volatile struct Patrol *)0x02022200)
#define SB1PTR (*(volatile u32 *)0x03005008)
#define NEWKEYS (*(volatile u16 *)0x0300311E)         /* gMain.newKeys */
#define KEY_B 0x0002
enum { PH_START = 0, PH_WALK = 1, PH_STRIKE = 2, PH_RETURN = 3, PH_COOL = 4 };
enum { R_DONE = 1, R_HURT = 2, R_SHINY = 3, R_TOOHURT = 4, R_NOREACH = 5, R_RECALL = 6, R_NOWALKER = 7 };
/* Settings (saved as hack flags, set by the settings script): F_OFF disables the patrol; F_SHORT / F_LONG pick the size, neither = normal.
 * normal: 10 targets within 12 tiles, short: 4 within 8, long: 20 within 16. */
#define F_OFF   0x13B0
#define F_SHORT 0x13B1
#define F_LONG  0x13B2
#define COOLDOWN 24                                  /* frames between two targets */
#define WIN 13                                       /* window side; the walker is at the centre (6, 6) */
#define TYPECHART 0x0824F050                         /* the hack's chart: {attacker, defender, 0/5/10/20} triples, 0xFF end, 0xFE 0xFE 0 = foresight marker */
#define BASESTATS 0x0976DFBC                         /* 28 bytes per species: expYield +9, growth rate +19 */
#define EXPTABLE  0x09E0B258                         /* [(growth << 8) + level] -> u32 */

#define POWER     90                                 /* a typed hit: power 60 with STAB (x1.5) */

#define MON_SPECIES 11
#define MON_EXP     25
#define MON_IS_EGG  45
#define MON_LEVEL   56
#define MON_HP      57
#define MON_MAXHP   58
#define MON_ATK     59
#define MON_DEF     60
#define MON_SPEED   61
#define MON_SPATK   62
#define MON_SPDEF   63

typedef u32 (*fn_getmon)(void *, u32, void *);
typedef void (*fn_setmon)(void *, u32, const void *);
typedef void (*fn_void_p)(void *);
typedef u32 (*fn_u16)(void);
typedef u32 (*fn_v)(void);
typedef void (*fn_task)(u32);
typedef void (*fn_create)(u32, u32, u32, u32);
typedef void (*fn_script)(const void *);
typedef u32 (*fn_add)(u32, u32);
typedef void (*fn_feather)(void *, u32, u16 *);
typedef u32 (*fn_learn)(void *, u32);
typedef void (*fn_evo)(void *, u32, u32, u32);
typedef u32 (*fn_task_create)(u32, u32);
typedef u32 (*fn_coll)(void *, s32, s32, u32);
typedef u32 (*fn_obj)(void *);
typedef u32 (*fn_species)(void *, u16 *);
typedef u32 (*fn_flag)(u32);
typedef u32 (*fn_obj_set)(void *, u32);
typedef void (*fn_move_to)(void *, s32, s32);

#define GetMonData        ((fn_getmon)0x0803FBE9)
#define SetMonData        ((fn_setmon)0x0804037D)
#define CalculateMonStats ((fn_void_p)0x0803E47D)
#define Random            ((fn_u16)0x08044EC9)
#define IsMonShiny        ((fn_getmon)0x08044471)    /* (mon) */
#define QcAimValid        ((fn_v)0x09D53889)         /* the throw's own check of the aimed target */
#define QcExit            ((fn_task)0x09D53E65)      /* closes Quick Catch (takes the task id) */
#define QcCreateTarget    ((fn_create)0x09D6BA79)    /* species, level, 0, 1 -> gEnemyParty[0], as the throw does */
#define QcRemoveTarget    ((fn_v)0x09D55F69)         /* removes the object whose local id is in LASTTALKED */
#define SetupScript       ((fn_script)0x08069AE5)
#define AddBagItem        ((fn_add)0x0809A085)
#define Feathers          ((fn_feather)0x09D2ADA5)   /* (partner mon, defeated species, u16 out[6]) -> adds the Feathers, out[stat] = count (negative = no room) */
#define GetEvolutionTarget ((fn_getmon)0x08042EC5)   /* (mon, mode 0, item 0) -> the species it evolves into now, 0 = none; the party menu's own rare-candy call */
#define BeginEvolutionScene ((fn_evo)0x080CDDA9)     /* (mon, species, canStop, partyId): the engine's evolution scene, B cancels */
#define GCB2_AFTEREVO     (*(volatile u32 *)0x0300537C)   /* where the scene returns to */
#define CB2_ContinueScript 0x080568C5                /* CB2_ReturnToFieldContinueScript: back to the field and resume the running script */
#define TryLearnMove      ((fn_learn)0x0803EA89)
#define ZeroMonData       ((fn_void_p)0x0803D995)
#define CreateTask        ((fn_task_create)0x0807741D)
#define DestroyTask       ((fn_task)0x08077509)
#define GetCollisionAtCoords ((fn_coll)0x080636AD)   /* (object, x, y, direction) -> 0 when the step is free */
#define SetHeldMovement   ((fn_obj_set)0x08063CA5)
#define HeldMovementActive ((fn_obj)0x08063C89)
#define ClearHeldIfFinished ((fn_obj)0x08063D7D)
#define MoveObjectToCoords ((fn_move_to)0x0805F725)  /* the engine's own teleport (setobjectxyperm) */
#define FieldControlsLocked ((fn_v)0x08069959)
#define ClearHeld         ((fn_obj)0x08063D35)
#define FlagGet           ((fn_flag)0x0806E6D1)
#define QcSpeciesOf       ((fn_species)0x09D53425)   /* (object, u16 *species) -> nonzero for a valid visible Pokemon */
#define UnlockControls    ((fn_v)0x0806994D)   /* sLockFieldControls = FALSE */

extern const u8 patrol_script[];                     /* linker symbol: the summary script */
extern const u8 patrol_settings[];                   /* linker symbol: the settings script */

static u32 max_kills(void) { return FlagGet(F_LONG) ? 20 : FlagGet(F_SHORT) ? 4 : 10; }
static u32 radius(void) { return FlagGet(F_LONG) ? 16 : FlagGet(F_SHORT) ? 8 : 12; }

static u32 get(void *mon, u32 f) { return GetMonData(mon, f, 0); }

/* unsigned divide without libgcc */
static u32 udiv(u32 n, u32 d)
{
    u32 q = 0, r = 0;
    int i;
    if (!d)
        return 0;
    for (i = 31; i >= 0; i--) {
        r = (r << 1) | ((n >> i) & 1);
        if (r >= d) {
            r -= d;
            q |= 1u << i;
        }
    }
    return q;
}

static u32 higher(u32 a, u32 b) { return a > b ? a : b; }

/* effectiveness of one attacking type against one defending type: 0 / 5 / 10 / 20 (10 = neutral; unknown types are neutral) */
static u32 eff1(u32 atk, u32 def)
{
    const volatile u8 *p = (const volatile u8 *)TYPECHART;
    for (; *p != 0xFF; p += 3)
        if (p[0] == atk && p[1] == def)
            return p[2];
    return 10;
}

/* the better of the attacker's own types against the defender's type pair, in percent (100 = neutral, 0 = no effect, 400 = 4x) */
static u32 type_mult(u32 species_a, u32 species_d)
{
    const volatile u8 *a = (const volatile u8 *)(BASESTATS + 28 * species_a);
    const volatile u8 *d = (const volatile u8 *)(BASESTATS + 28 * species_d);
    u32 best = 0, i;
    for (i = 0; i < 2; i++) {
        u32 m;
        if (i && a[7] == a[6])
            break;
        m = eff1(a[6 + i], d[6]);
        if (d[7] != d[6])
            m *= eff1(a[6 + i], d[7]);
        else
            m *= 10;
        if (m > best)
            best = m;
    }
    return best;
}

/* Gen-3 damage for a typed hit (no move): ((2L/5+2) * P * A / D) / 50 + 2, STAB folded into P, random 85..100 %, then the type multiplier */
static u32 damage(u32 level, u32 a, u32 d, u32 mult)
{
    u32 base = udiv(udiv((udiv(2 * level, 5) + 2) * POWER * a, d ? d : 1), 50) + 2;
    return udiv(udiv(base * (85 + (Random() & 15)), 100) * mult, 100);
}

static u32 task_of_quick_catch(void)
{
    u32 i;
    for (i = 0; i < 16; i++) {
        volatile u32 *t = (volatile u32 *)(TASKS + 40 * i);
        if (t[0] == 0x09D53F81 && ((volatile u8 *)t)[4])
            return i;
    }
    return 16;
}

u32 patrol_remove(void)                              /* script: callnative */
{
    LASTTALKED = P->target_local;
    QcRemoveTarget();
    return 0;
}

/* script: callnative after the summary. If the partner levelled up (the engine's own gLeveledUpInBattle bit) and can evolve now, start the engine's evolution
 * scene (the player can cancel with B, as after a battle) and set 0x800D = 1 so the script waits; the scene returns to the field and the script goes on. The
 * bit is cleared either way, so the post-battle check does not ask a second time. */
u32 patrol_evolve(void)
{
    u32 slot = P->slot, species;
    void *mon;
    V800D = 0;
    if (slot > 5 || !(LEVELEDUP & (1 << slot)))
        return 0;
    LEVELEDUP &= ~(1 << slot);
    mon = (void *)(PARTY + 100 * slot);
    if (!get(mon, MON_SPECIES) || get(mon, MON_IS_EGG))
        return 0;
    species = GetEvolutionTarget(mon, 0, 0) & 0xFFFF;
    if (!species)
        return 0;
    GCB2_AFTEREVO = CB2_ContinueScript;
    BeginEvolutionScene(mon, species, 1, slot);
    V800D = 1;
    return 0;
}

static u32 mod(u32 n, u32 d) { return n - udiv(n, d) * d; }

static void reward(u32 slot_id, u32 id, u32 qty)       /* A = 8, B = 10 */
{
    SPECIALS[slot_id] = id;
    SPECIALS[slot_id + 1] = qty;
}

/* the Quick Catch drop roll plus the species' held items */
static void drops(void *partner, u32 species, u32 level)
{
    u32 roll = mod(Random(), 100), item = 0, used = 0, i;
    u16 f[6];
    const volatile u8 *bs = (const volatile u8 *)(BASESTATS + 28 * species);

    if (roll < 20) {
        item = level < 20 ? 536 : level < 40 ? 537 : level < 60 ? 538 : level < 80 ? 539 : 540;
    } else if (roll < 50) {
        item = BERRIES[mod(Random(), 10)];
    }
    if (item) {
        reward(8, item, AddBagItem(item, 1) ? 1 : 0);
    } else {
        for (i = 0; i < 6; i++)
            f[i] = 0;
        Feathers(partner, species, f);
        for (i = 0; i < 6 && used < 2; i++) {
            if (f[i]) {
                static const u16 ids[6] = {57, 58, 59, 62, 60, 61};   /* the hack's Feather table (0x09DDF196) */
                reward(8 + 2 * used, ids[i], (f[i] & 0x8000) ? 0 : f[i]);
                used++;
            }
        }
    }
    {
        u32 a = bs[12] | (bs[13] << 8), b = bs[14] | (bs[15] << 8), held = 0;
        if (a && a == b) {
            held = a;
        } else if (a || b) {
            u32 r = mod(Random(), 100);
#ifdef FORCE_HELD                                    /* test builds only (RHT_PATROL_TEST=held) */
            r = 99;
#endif
            if (r >= 95)
                held = b;
            else if (r >= 45)
                held = a;
        }
        if (held && AddBagItem(held, 1))
            SPECIALS[3] = held;
    }
}

/* raises the partner by `exp`, learning each level's moves; returns the new level (0 = unchanged) */
static u32 give_exp(void *partner, u32 slot, u32 exp)
{
    const volatile u8 *bs = (const volatile u8 *)(BASESTATS + 28 * get(partner, MON_SPECIES));   /* the PARTNER's growth rate */
    u32 growth = bs[19], old = get(partner, MON_LEVEL), cur = get(partner, MON_EXP), cap, now, lvl, learned = 0;
    cap = *(volatile u32 *)(EXPTABLE + 4 * ((growth << 8) + 100));
    cur = cur + exp > cap ? cap : cur + exp;
    SetMonData(partner, MON_EXP, &cur);
    CalculateMonStats(partner);
    now = get(partner, MON_LEVEL);
    if (now <= old)
        return 0;
    for (lvl = old + 1; lvl <= now; lvl++) {            /* the learnset is read at the Pokemon's level: step through each one */
        u32 mv, guard = 0, e = *(volatile u32 *)(EXPTABLE + 4 * ((growth << 8) + lvl));
        SetMonData(partner, MON_EXP, &e);
        CalculateMonStats(partner);
        for (mv = TryLearnMove(partner, 1); mv && guard < 8; mv = TryLearnMove(partner, 0), guard++) {
            if (mv < 0xFFFE && learned < 2)
                SPECIALS[1 + learned++] = mv;
        }
    }
    SetMonData(partner, MON_EXP, &cur);
    CalculateMonStats(partner);
    LEVELEDUP |= 1 << slot;
    return now;
}

/* ------------------------------------------------------------------------------------------------------------------------------------------ the fight */

/* partner = the party member shown by the walker (first alive one), else the lead; returns the slot */
static u32 find_partner(u32 walker)
{
    u32 gfx = 0xFFFF, i;
    if (walker < 16) {
        volatile u8 *w = (volatile u8 *)(OBJECTS + 36 * walker);
        gfx = w[5] | (w[35] << 8);
    }
    for (i = 0; i < 6; i++) {
        void *m = (void *)(PARTY + 100 * i);
        if (!get(m, MON_SPECIES) || get(m, MON_IS_EGG))
            continue;
        if (get(m, MON_SPECIES) == gfx && get(m, MON_HP))
            return i;
    }
    return 0;
}

/* the whole strike: result code in 0x8004 (1 won, 2 retreated, 3 shiny, 4 too hurt) and the reward vars; the caller shows the script */
static void fight(u32 slot, u32 species, u32 level)
{
    void *partner = (void *)(PARTY + 100 * slot);
    u32 pm, em, hp, maxhp, ehp, pspd, espd, pa, pd, ea, ed, rounds, exp, i;
    int won = 0, retreat = 0;

    hp = get(partner, MON_HP);
    maxhp = get(partner, MON_MAXHP);
    SPECIALS[4] = 0;                                 /* 0x8004 */
    SPECIALS[6] = slot;                              /* 0x8006 */
    SPECIALS[7] = species;                           /* 0x8007 */
    SPECIALS[5] = 0;                                 /* 0x8005 */
    for (i = 0; i < 4; i++)
        SPECIALS[i] = 0;                             /* 0x8000-0x8003 */
    for (i = 8; i < 12; i++)
        SPECIALS[i] = 0;                             /* 0x8008-0x800B */

    if (!hp || hp * 5 < maxhp * 2) {
        SPECIALS[4] = 4;
        return;
    }

    QcCreateTarget(species, level, 0, 1);
#ifdef FORCE_SHINY                                   /* test builds only (RHT_PATROL_TEST=shiny) */
    if (1) {
#else
    if (IsMonShiny(ENEMY, 0, 0)) {
#endif
        SPECIALS[4] = 3;                             /* leave it to the player: a real battle with this very Pokemon */
        return;
    }

    ehp = get(ENEMY, MON_MAXHP);
    pa = higher(get(partner, MON_ATK), get(partner, MON_SPATK));
    pd = get(partner, MON_ATK) >= get(partner, MON_SPATK) ? 0 : 1;
    ea = higher(get(ENEMY, MON_ATK), get(ENEMY, MON_SPATK));
    ed = get(ENEMY, MON_ATK) >= get(ENEMY, MON_SPATK) ? 0 : 1;
    pm = type_mult(get(partner, MON_SPECIES), species);
    em = type_mult(species, get(partner, MON_SPECIES));
    pspd = get(partner, MON_SPEED);
    espd = get(ENEMY, MON_SPEED);

#ifdef FORCE_RETREAT                                  /* test builds only (RHT_PATROL_TEST=retreat) */
    retreat = 1;
#endif
    for (rounds = 0; rounds < 12 && !won && !retreat; rounds++) {
        u32 turn;
        for (turn = 0; turn < 2 && !won && !retreat; turn++) {
            int partner_acts = (pspd >= espd) ? (turn == 0) : (turn == 1);
            if (partner_acts) {
                u32 d = damage(get(partner, MON_LEVEL), pa, pd ? get(ENEMY, MON_SPDEF) : get(ENEMY, MON_DEF), pm);
                if (d >= ehp)
                    won = 1;
                else
                    ehp -= d;
            } else {
                u32 d = damage(level, ea, ed ? get(partner, MON_SPDEF) : get(partner, MON_DEF), em);
                hp = d >= hp ? 1 : hp - d;
                if (hp * 5 < maxhp * 2)
                    retreat = 1;
            }
        }
    }
#ifdef FORCE_NOHURT                                   /* test builds only (RHT_PATROL_TEST=nohurt): fights cost no HP */
    hp = get(partner, MON_HP);
#endif
    SetMonData(partner, MON_HP, &hp);
    ZeroMonData(ENEMY);

    if (won) {
        const volatile u8 *bs = (const volatile u8 *)(BASESTATS + 28 * species);
        exp = udiv(bs[9] * level, 7);
        if (!exp)
            exp = 1;
        SPECIALS[5] = exp;
        SPECIALS[4] = 1;
        SPECIALS[0] = give_exp(partner, slot, exp);
        drops(partner, species, level);
    } else {
        SPECIALS[4] = 2;
    }
}

/* ------------------------------------------------------------------------------------------------------------------------------- walking */

static volatile u8 *obj_at(u32 idx) { return (volatile u8 *)(OBJECTS + 36 * idx); }
static s32 ox(volatile u8 *o) { return *(volatile s16 *)(o + 0x10); }
static s32 oy(volatile u8 *o) { return *(volatile s16 *)(o + 0x12); }
/* the engine deletes any object that scrolls out of the camera window (about -9..+10 tiles across, -7..+9 down from the player), so the partner and its
 * targets must stay well inside it: a deleted walker leaves the follower state pointing at a slot the next template NPC takes over */
static int near_player(volatile u8 *o, volatile u8 *pl, s32 mx, s32 up, s32 down)
{
    s32 dx = ox(o) - ox(pl), dy = oy(o) - oy(pl);
    return dx >= -mx && dx <= mx && dy >= -up && dy <= down;
}
static u32 dist(s32 ax, s32 ay, s32 bx, s32 by) { return (ax > bx ? ax - bx : bx - ax) + (ay > by ? ay - by : by - ay); }
static int obj_alive(u32 idx, u32 local) { volatile u8 *o; if (idx > 15) return 0; o = obj_at(idx); return (o[0] & 1) && o[8] == local; }

static const s8 DX[5] = {0, 0, 0, -1, 1};            /* 1 south, 2 north, 3 west, 4 east */
static const s8 DY[5] = {0, 1, -1, 0, 0};

/* One step of a breadth-first search over the 13 x 13 window around the walker: the reachable cell closest to (gx, gy), then the first
 * direction on the way there. Returns the direction (1-4), or 0 when the walker is already as close as it can get. */
static u32 plan(volatile u8 *w, s32 gx, s32 gy)
{
    volatile u8 *grid = P->grid, *q = P->queue;
    s32 wx = ox(w), wy = oy(w), c, head = 0, tail = 0, best, bestd;
    u32 d;

    for (c = 0; c < WIN * WIN; c++)
        grid[c] = 0;
    c = 6 * WIN + 6;
    grid[c] = 6;
    q[tail++] = c;
    best = c;
    bestd = dist(wx, wy, gx, gy);
    while (head < tail) {
        s32 cur = q[head++], cx = cur - udiv(cur, WIN) * WIN, cy = udiv(cur, WIN);
        for (d = 1; d <= 4; d++) {
            s32 nx = cx + DX[d], ny = cy + DY[d], n;
            if (nx < 0 || ny < 0 || nx >= WIN || ny >= WIN)
                continue;
            n = ny * WIN + nx;
            if (grid[n])
                continue;
            if (GetCollisionAtCoords((void *)w, wx + nx - 6, wy + ny - 6, d)) {
                grid[n] = 5;
                continue;
            }
            grid[n] = d;
            q[tail++] = n;
            if (dist(wx + nx - 6, wy + ny - 6, gx, gy) < (u32)bestd) {
                bestd = dist(wx + nx - 6, wy + ny - 6, gx, gy);
                best = n;
            }
        }
    }
    if (best == 6 * WIN + 6)
        return 0;
    for (d = 0; d < WIN * WIN; d++) {                /* walk back to the start, remembering the last direction taken */
        u32 dir = grid[best];
        s32 cx = best - udiv(best, WIN) * WIN, cy = udiv(best, WIN);
        if (dir < 1 || dir > 4)
            return 0;
        cx -= DX[dir];
        cy -= DY[dir];
        if (cx == 6 && cy == 6)
            return dir;
        best = cy * WIN + cx;
    }
    return 0;
}

static int walker_ready(volatile u8 *w)
{
    if (!HeldMovementActive((void *)w))
        return 1;
    return ClearHeldIfFinished((void *)w) != 0;
}

static void finish(void)
{
    P->active = 0;                                   /* the follower logic owns the walker again */
}

static void abort_to_player(volatile u8 *w)          /* the walker is lost or stuck: put it where the follower logic expects it */
{
    volatile u8 *pl = obj_at(0);
    ClearHeld((void *)w);
    MoveObjectToCoords((void *)w, *(volatile s16 *)(pl + 0x14), *(volatile s16 *)(pl + 0x16));
    finish();
}

/* ------------------------------------------------------------------------------------------------------------------- the summary */

static void add_item(u32 id, u32 qty)
{
    u32 i, v = qty ? qty : 0x8000;
    if (!id)
        return;
    for (i = 0; i < P->nitems; i++) {
        if (P->items[2 * i] == id) {
            if (!qty)
                P->items[2 * i + 1] |= 0x8000;
            else if ((P->items[2 * i + 1] & 0x7FFF) < 0x7FF0)
                P->items[2 * i + 1] += qty;
            return;
        }
    }
    if (P->nitems < 8) {
        P->items[2 * P->nitems] = id;
        P->items[2 * P->nitems + 1] = v;
        P->nitems++;
    }
}

static void accumulate(void)                         /* one win: fight() left its results in the script vars */
{
    u32 i;
    P->kills++;
    if (P->exp_total + SPECIALS[5] < 0xFFF0)
        P->exp_total += SPECIALS[5];
    if (SPECIALS[0])
        P->level_now = SPECIALS[0];
    for (i = 1; i <= 2; i++)
        if (SPECIALS[i] && P->nmoves < 6)
            P->moves[P->nmoves++] = SPECIALS[i];
    add_item(SPECIALS[8], SPECIALS[9]);
    add_item(SPECIALS[10], SPECIALS[11]);
    if (SPECIALS[3])
        add_item(SPECIALS[3], 1);                    /* the held item the target dropped */
}

/* script: callnative, in a loop. 0x800D = 0 end, 1 header (0x8005 kills, 0x8001 EXP), 2 level (0x8002), 3 move (0x8003), 4 item (0x8008), 5 no room for item (0x8008) */
u32 patrol_sum_step(void)
{
    u32 i;
    for (i = P->sum_i; i < 16; i++) {
        if (i == 0 && P->kills) {
            SPECIALS[5] = P->kills;
            SPECIALS[1] = P->exp_total;
            V800D = 1;
        } else if (i == 1 && P->level_now) {
            SPECIALS[2] = P->level_now;
            V800D = 2;
        } else if (i >= 2 && i < 8 && (i - 2) < P->nmoves) {
            SPECIALS[3] = P->moves[i - 2];
            V800D = 3;
        } else if (i >= 8 && (i - 8) < P->nitems) {
            SPECIALS[8] = P->items[2 * (i - 8)];
            SPECIALS[9] = P->items[2 * (i - 8) + 1] & 0x7FFF;
            V800D = (P->items[2 * (i - 8) + 1] & 0x8000) && !(P->items[2 * (i - 8) + 1] & 0x7FFF) ? 5 : 4;
        } else {
            continue;
        }
        P->sum_i = i + 1;
        return 0;
    }
    P->sum_i = 16;
    V800D = 0;
    return 0;
}

static void run_summary(u32 reason)
{
    P->sum_i = 0;
    SPECIALS[4] = reason;
    SPECIALS[5] = P->kills;
    SPECIALS[6] = P->slot;
    SPECIALS[7] = P->species;
    SetupScript(patrol_script);
}

/* ------------------------------------------------------------------------------------------------------------------ the next target */

/* the visible Pokemon (local ids 0xE0-0xE2, valid for Quick Catch) nearest to the walker and within RADIUS of the player; 1 = found */
static int choose_target(volatile u8 *w)
{
    volatile u8 *pl = obj_at(0);
    u32 i, best = 0xFFFF, found = 0;
    for (i = 1; i < 16; i++) {
        volatile u8 *o = obj_at(i);
        u16 sp = 0;
        u32 d;
        if (!(o[0] & 1) || o[8] < 0xE0 || o[8] > 0xE2)
            continue;
        if (!QcSpeciesOf((void *)o, &sp) || !sp)
            continue;
        if (dist(ox(o), oy(o), ox(pl), oy(pl)) > radius() || !near_player(o, pl, 7, 5, 6))
            continue;
        d = dist(ox(o), oy(o), ox(w), oy(w));
        if (d < best) {
            best = d;
            found = i;
            P->species = sp;
        }
    }
    if (!found)
        return 0;
    {
        volatile u8 *o = obj_at(found);
        u32 lv = o[0x1D];
        P->target = found;
        P->target_local = o[8];
        P->level = (lv < 1 || lv > 100) ? 1 : lv;
    }
    return 1;
}

static void stop_and_return(u32 reason)
{
    P->reason = reason;
    P->phase = PH_RETURN;
    P->timer = 0;
    P->fails = 0;
}

void patrol_task(u32 id);

/* Is `id` a live task running patrol_task? (The game wipes the whole task list whenever a battle or a full-screen menu starts.) */
static int task_alive(u32 id)
{
    volatile u32 *t;
    if (id > 15)
        return 0;
    t = (volatile u32 *)(TASKS + 40 * id);
    return ((volatile u8 *)t)[4] && (t[0] >> 1) == (((u32)patrol_task | 1) >> 1);
}

/* The hack's follower state names the walker by object index. If that object is gone (the engine deleted it offscreen, a map change rebuilt the objects) the
 * hack's follower code would keep driving whatever NPC now sits in the slot. Every free frame: the index must be a live object with local id 0xFE; else
 * find the walker again. The hack's own state stays untouched otherwise (its map-load code respawns the walker while the follower is marked active);
 * patrol_hold_wrap (patrol.s) drops the follower's movements for any slot that is not a live walker, so a stale index never moves an NPC. */
static void partner_guard(void)
{
    u32 i;
    if (!FOLLOWER[0] || obj_alive(FOLLOWER[1], 0xFE))
        return;
    for (i = 1; i < 16; i++) {
        if (obj_alive(i, 0xFE)) {
            FOLLOWER[1] = i;
            return;
        }
    }
}

/* Called by patrol.s on every free overworld frame. If a patrol is marked active but its task is gone, bring the task back: the patrol resumes after a
 * menu or a battle, and a stale or garbage state ends itself on the task's first checks (map, walker identity). If no task can be made the flag is cleared,
 * so the patrol and its settings hotkey can never stay locked out. */
u32 patrol_watchdog(void)
{
    u32 task;
    partner_guard();
    if (!P->active || task_alive(P->task))
        return 0;
    task = CreateTask((u32)patrol_task | 1, 80);
    if (task < 16)
        P->task = task;
    else
        P->active = 0;
    return 0;
}

void patrol_task(u32 id)
{
    volatile u8 *w, *t, *pl;
    u32 dir;

    if (!P->active) {
        DestroyTask(id);
        return;
    }
    {
        volatile u8 *sb1 = (volatile u8 *)SB1PTR;
        if (!sb1 || (s8)sb1[4] != P->map_group || (s8)sb1[5] != P->map_num) {   /* left the map: its objects are rebuilt, touch nothing */
            finish();
            DestroyTask(id);
            return;
        }
    }
    if (P->walker > 15 || (obj_at(P->walker)[0] & 1) == 0 || obj_at(P->walker)[8] != 0xFE || (u32)obj_at(P->walker) != P->walker_ptr) {
        finish();
        DestroyTask(id);
        return;
    }
    if (P->phase == PH_START) {                      /* returning 1 from the SELECT hook made the caller lock the player: give the controls back */
        UnlockControls();
        if (!P->timer)
            ClearHeld((void *)obj_at(P->walker));    /* drop the follower's lingering idle action so our steps can be set */
        if (++P->timer >= 2) {
            P->phase = PH_WALK;
            P->timer = 0;
        }
        return;
    }
    if (FieldControlsLocked())                       /* a script, menu or battle is running: wait */
        return;
    w = obj_at(P->walker);
    pl = obj_at(0);
    if (P->phase != PH_RETURN && !near_player(w, pl, 8, 6, 7)) {   /* about to be deleted by the engine: bring it home now */
        abort_to_player(w);
        DestroyTask(id);
        if (P->kills)
            run_summary(R_DONE);
        return;
    }
    P->timer++;
    if (P->total < 0xFFF0)
        P->total++;
    if (P->phase != PH_RETURN && (P->timer > 1800 || P->steps > 400 || P->total > 10800)) {   /* too long: bring it home */
        stop_and_return(P->kills ? R_DONE : R_NOREACH);
    } else if (P->phase == PH_RETURN && (P->timer > 1800 || P->steps > 460)) {
        abort_to_player(w);
        DestroyTask(id);
        if (P->kills || P->reason == R_HURT || P->reason == R_NOREACH)
            run_summary(P->reason);
        return;
    }
    if ((P->phase == PH_WALK || P->phase == PH_COOL) && (NEWKEYS & KEY_B))      /* B recalls the partner */
        stop_and_return(R_RECALL);
    if (!walker_ready(w))
        return;

    if (P->phase == PH_WALK) {
        if (!obj_alive(P->target, P->target_local)) {   /* the target left: look for another one */
            if (choose_target(w)) {
                P->timer = 0;
                P->fails = 0;
            } else {
                stop_and_return(P->kills ? R_DONE : R_NOREACH);
            }
            return;
        }
        t = obj_at(P->target);
        if (dist(ox(w), oy(w), ox(t), oy(t)) == 1) {
            u32 face = ox(t) > ox(w) ? 4 : ox(t) < ox(w) ? 3 : oy(t) > oy(w) ? 1 : 2;
            SetHeldMovement((void *)w, face - 1);    /* face it, then strike */
            P->phase = PH_STRIKE;
            P->timer = 0;
            P->fails = face;                         /* the direction, reused as scratch */
            return;
        }
        dir = plan(w, ox(t), oy(t));
        if (!dir) {
            if (++P->fails >= 3) {                   /* cannot get closer: give up on this one and go home */
                stop_and_return(P->kills ? R_DONE : R_NOREACH);
            }
            return;
        }
        P->fails = 0;
        P->steps++;
        SetHeldMovement((void *)w, 0x0F + dir);      /* MOVEMENT_ACTION_WALK_NORMAL_DOWN/UP/LEFT/RIGHT = 0x10-0x13 */
    } else if (P->phase == PH_STRIKE) {
        if (P->timer == 1) {                         /* faced it: the hit */
            SetHeldMovement((void *)w, 0x51 + P->fails);   /* MOVEMENT_ACTION_JUMP_IN_PLACE_DOWN/UP/LEFT/RIGHT = 0x52-0x55 */
            return;
        }
        if (!obj_alive(P->target, P->target_local)) {
            P->phase = PH_WALK;
            P->timer = 0;
            return;
        }
        fight(P->slot, P->species, P->level);
        P->fails = 0;
        P->timer = 0;
        if (SPECIALS[4] == 3) {                      /* a shiny: the summary so far, then a real battle; the patrol ends here */
            finish();
            DestroyTask(id);
            P->reason = R_SHINY;
            run_summary(R_SHINY);
            return;
        }
        if (SPECIALS[4] == 1) {
            accumulate();
            LASTTALKED = P->target_local;            /* the win removes its target right away */
            QcRemoveTarget();
            if (P->kills >= max_kills())
                stop_and_return(R_DONE);
            else
                P->phase = PH_COOL;
        } else {
            stop_and_return(R_HURT);                 /* retreated, or too hurt to start: the partner is done */
        }
    } else if (P->phase == PH_COOL) {
        if (P->timer < COOLDOWN)
            return;
        if (choose_target(w)) {
            P->phase = PH_WALK;
            P->timer = 0;
            P->fails = 0;
        } else {
            stop_and_return(R_DONE);
        }
    } else {                                         /* PH_RETURN: back next to the player */
        if (dist(ox(w), oy(w), ox(pl), oy(pl)) <= 1) {
            finish();
            DestroyTask(id);
            if (P->kills || P->reason == R_HURT || P->reason == R_NOREACH)
                run_summary(P->reason);
            return;
        }
        dir = plan(w, ox(pl), oy(pl));
        if (!dir) {
            if (++P->fails >= 3) {
                abort_to_player(w);
                DestroyTask(id);
                if (P->kills || P->reason == R_HURT || P->reason == R_NOREACH)
                    run_summary(P->reason);
            }
            return;
        }
        P->fails = 0;
        P->steps++;
        SetHeldMovement((void *)w, 0x0F + dir);
    }
}

/* L + R + SELECT (called by patrol.s): the settings, from anywhere in the overworld. Returns 1 when handled. */
u32 patrol_open_settings(void)
{
    u32 task;
    if (P->active)
        return 0;
    if (QC[0x13] == 1) {                             /* close Quick Catch first */
        task = task_of_quick_catch();
        if (task < 16)
            QcExit(task);
    }
    SetupScript(patrol_settings);
    return 1;
}

/* SELECT in Quick Catch (called by patrol.s): validate, close Quick Catch, start the walk. Returns 1 when the press was handled. */
u32 patrol_select(void)
{
    u32 idx, walker, slot, task, level, species, i;
    volatile u8 *sb1;
    void *partner;

    if (P->active)
        return 0;
    if (!QcAimValid()) {                             /* SELECT with nothing aimed: the settings */
        task = task_of_quick_catch();
        if (task < 16)
            QcExit(task);
        SetupScript(patrol_settings);
        return 1;
    }
    if (FlagGet(F_OFF))                              /* switched off: leave SELECT to the game */
        return 0;
    idx = QC[6];
    walker = FOLLOWER[1];
    sb1 = (volatile u8 *)SB1PTR;
    if (idx > 15 || walker > 15 || !sb1)
        return 0;
    level = obj_at(idx)[0x1D];
    if (level < 1 || level > 100)
        level = 1;
    species = *(volatile u16 *)(QC + 0x18);
    if (!FOLLOWER[0] || !obj_alive(walker, 0xFE)) {  /* nobody is walking behind the player: say so (SELECT would otherwise do nothing visible) */
        task = task_of_quick_catch();
        if (task < 16)
            QcExit(task);
        P->slot = 0;
        P->species = species;
        P->kills = 0;
        P->nmoves = 0;
        P->nitems = 0;
        P->level_now = 0;
        run_summary(R_NOWALKER);
        return 1;
    }
    slot = find_partner(walker);
    partner = (void *)(PARTY + 100 * slot);

    P->walker = walker;
    P->walker_ptr = OBJECTS + 36 * walker;
    P->target = idx;
    P->target_local = QC[7];
    P->slot = slot;
    P->species = species;
    P->level = level;
    P->map_group = (s8)sb1[4];
    P->map_num = (s8)sb1[5];
    P->phase = PH_START;
    P->timer = 0;
    P->total = 0;
    P->steps = 0;
    P->fails = 0;
    P->reason = R_DONE;
    P->kills = 0;
    P->exp_total = 0;
    P->level_now = 0;
    P->nmoves = 0;
    P->nitems = 0;
    P->sum_i = 0;
    for (i = 0; i < 6; i++)
        P->moves[i] = 0;
    for (i = 0; i < 16; i++)
        P->items[i] = 0;

    task = task_of_quick_catch();
    if (task < 16)
        QcExit(task);

    if (get(partner, MON_HP) * 5 < get(partner, MON_MAXHP) * 2 || !get(partner, MON_HP)) {   /* too hurt: no walk at all */
        run_summary(R_TOOHURT);
        return 1;
    }
    task = CreateTask((u32)patrol_task | 1, 80);
    if (task >= 16)
        return 1;                                    /* no free task: Quick Catch is closed, nothing else happened */
    P->task = task;
    P->active = 1;                                   /* from here the follower logic leaves the walker alone */
    return 1;
}
