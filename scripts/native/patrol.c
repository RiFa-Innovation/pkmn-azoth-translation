/* Partner Patrol, M1: the instant strike (docs/PARTNER_PATROL_SPEC.md). Freestanding Thumb code linked by scripts/patrol_build.py.
 *
 * SELECT in Quick Catch -> patrol_select(): the partner (the party member the walker shows) fights the aimed target in a simulated
 * fight, gets XP, the target is removed, the result script reports it. A shiny roll stops the patrol and starts a real wild battle instead.
 *
 * Results in the script vars: 0x8004 = result (1 won, 2 retreated, 3 shiny -> real battle, 4 partner too hurt), 0x8005 = EXP gained,
 * 0x8006 = partner party slot, 0x8007 = target species. The fight ignores moves (River's rule): each side attacks with its best own type
 * (STAB) against the other's types, through the game's type chart, Scarlet/Violet style. M2 adds the drops.
 */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef int s32;

#define QC        ((volatile u8 *)0x0203B730)        /* Quick Catch state (var 0x51DE storage): +6 aimed object, +7 its local id, +0x13 active, +0x18 species */
#define FOLLOWER  ((volatile u8 *)0x0203B818)        /* follower state: +1 walker's object index */
#define OBJECTS   0x02036E38                         /* gObjectEvents, 36 bytes each; +5 graphics id, +0x1D level of a visible Pokemon */
#define PARTY     0x02024284                         /* 100 bytes each */
#define ENEMY     ((void *)0x0202402C)               /* gEnemyParty[0] */
#define TASKS     0x03005090                         /* 40 bytes each, func at +0 */
#define SPECIALS  ((volatile u16 *)0x020370B8)       /* script vars 0x8000.. */
#define LASTTALKED (*(volatile u16 *)0x020370D2)
#define SCRATCH   ((volatile u16 *)0x02022200)       /* borrowed link-buffer bytes: [0] local id of the target to remove */
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
#define ZeroMonData       ((fn_void_p)0x0803D995)

extern const u8 patrol_script[];                     /* linker symbol: the result script */

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
    LASTTALKED = SCRATCH[0];
    QcRemoveTarget();
    return 0;
}

u32 patrol_select(void)
{
    u32 pm, em, idx, level, species, slot, i, walker, gfx, hp, maxhp, ehp, ehpmax, pspd, espd, pa, pd, ea, ed, rounds, exp, growth, task;
    void *partner;
    volatile u8 *obj;
    int won = 0, retreat = 0;

    if (!QcAimValid())
        return 0;
    idx = QC[6];
    if (idx > 15)
        return 0;
    obj = (volatile u8 *)(OBJECTS + 36 * idx);
    level = obj[0x1D];
    if (level < 1 || level > 100)
        level = 1;
    species = *(volatile u16 *)(QC + 0x18);

    /* the partner: the party member whose species is the walker's graphics id (first alive one), else the lead */
    walker = FOLLOWER[1];
    gfx = ((volatile u8 *)(OBJECTS + 36 * walker))[5] | (((volatile u8 *)(OBJECTS + 36 * walker))[35] << 8);
    slot = 6;
    for (i = 0; i < 6; i++) {
        void *m = (void *)(PARTY + 100 * i);
        if (!get(m, MON_SPECIES) || get(m, MON_IS_EGG))
            continue;
        if (get(m, MON_SPECIES) == gfx && get(m, MON_HP)) {
            slot = i;
            break;
        }
    }
    if (slot == 6)
        slot = 0;
    partner = (void *)(PARTY + 100 * slot);
    hp = get(partner, MON_HP);
    maxhp = get(partner, MON_MAXHP);

    SCRATCH[0] = QC[7];
    SPECIALS[4] = 0;                                 /* 0x8004 */
    SPECIALS[6] = slot;                              /* 0x8006 */
    SPECIALS[7] = species;                           /* 0x8007 */
    SPECIALS[5] = 0;                                 /* 0x8005 */

    if (!hp || hp * 5 < maxhp * 2) {
        SPECIALS[4] = 4;
        goto done;
    }

    QcCreateTarget(species, level, 0, 1);
#ifdef FORCE_SHINY                                   /* test builds only (RHT_PATROL_TEST=shiny) */
    if (1) {
#else
    if (IsMonShiny(ENEMY, 0, 0)) {
#endif                   /* leave it to the player: a real battle with this very Pokemon */
        SPECIALS[4] = 3;
        goto done;
    }

    ehp = ehpmax = get(ENEMY, MON_MAXHP);
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
    if (!won)
        retreat = 1;
    SetMonData(partner, MON_HP, &hp);
    ZeroMonData(ENEMY);

    if (won) {
        const volatile u8 *bs = (const volatile u8 *)(BASESTATS + 28 * species);
        u32 cur = get(partner, MON_EXP), cap;
        growth = bs[19];
        exp = udiv(bs[9] * level, 7);
        if (!exp)
            exp = 1;
        cap = *(volatile u32 *)(EXPTABLE + 4 * ((growth << 8) + 100));
        cur = cur + exp > cap ? cap : cur + exp;
        SetMonData(partner, MON_EXP, &cur);
        CalculateMonStats(partner);
        SPECIALS[5] = exp;
        SPECIALS[4] = 1;
    } else {
        SPECIALS[4] = 2;
    }

done:
    task = task_of_quick_catch();
    if (task < 16)
        QcExit(task);
    SetupScript(patrol_script);
    return 1;
}
