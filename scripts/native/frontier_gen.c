/* Spectrum Frontier opponent generator (docs/BATTLE_FRONTIER_SPEC.md 7.5). Freestanding Thumb code for the GBA, linked by scripts/frontier_native.py.
 *
 *   fr_gen_opponent   in : gSpecialVar 0x8000 = battle number n (1-based streak), 0x8001 = 1 for doubles, 0x8002/0x8003 = challenge seed (lo, hi),
 *                          0x8006/0x8007 = floor type theme (bitmask of type ids, low / high 16 bits; 0 = no theme),
 *                          0x8008 = 1 for "Shadow of the Past" (the team is built from the player's own species)
 *                     out also: 0x8009 = heirloom team id 1-4 when this battle drew a borrowed team (1 in 8, seeded; never with Shadow), else 0
 *                     out: party block at FR_BLOCK (16-byte trainer party entries: u16 iv, u8 level, u8 pad, u16 species, u16 item, u16 moves[4]),
 *                          0x8004 = number of Pokemon, 0x8005 = a random number for the script (trainer identity), Result = 0
 *
 * The opponent is a pure function of (seed, n, mode): a reload in the middle of a round gives the same team. Sets come from the packed table
 * (`fr_sets`, scripts/frontier_sets.py pack(header=True)): 20-byte tier index, then 24-byte records sorted by tier.
 */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

#define VARS   ((volatile u16 *)0x020370B8)
#define RESULT (*(volatile u16 *)0x020370D0)
#define BLOCK  ((volatile u16 *)0x02022400)

struct Hdr { u16 total; u16 start[4]; u16 count[4]; u16 reserved; };
struct Set { u16 species, item, moves[4], moves_d[4]; u8 spread, ability, tier, flags; };

extern const u8 fr_sets[];
extern const u8 fr_heirloom[];                   /* 4 teams x (u16 count, 6 x u16 species), data/frontier/heirloom.json */

#define F_MEGA   1
#define F_LEGEND 2
#define F_NFE    4
#define F_BOSS   8

/* no static data: the image is loaded as plain code, so the generator state lives on the stack */
static u32 rnd(u32 *state)
{
    /* xorshift32 */
    u32 x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

static u32 below(u32 *state, u32 n)   /* 0 .. n-1 without a division */
{
    return ((rnd(state) >> 16) * n) >> 16;
}

/* base stats table: 28 bytes per species, types at +6 / +7 (scripts/frontier_data.py) */
static u32 has_type(u32 species, u32 mask)
{
    const volatile u8 *bs = (const volatile u8 *)(0x08000000 + 0x176DFBC + 28 * species);
    return ((mask >> (bs[6] & 31)) & 1) | ((mask >> (bs[7] & 31)) & 1);
}

/* a set for this species (any tier, seeded pick); when the table has none, a set of a species that shares one of its types ("a little to the left") */
static const struct Set *set_of(const struct Set *sets, u32 total, u32 species, u32 *state)
{
    const volatile u8 *bs = (const volatile u8 *)(0x08000000 + 0x176DFBC + 28 * species);
    u32 mask = (1u << (bs[6] & 31)) | (1u << (bs[7] & 31));
    u32 pass, i, c, k;

    for (pass = 0; pass < 2; pass++) {
        c = 0;
        for (i = 0; i < total; i++)
            if (!(sets[i].flags & F_BOSS) && (pass ? has_type(sets[i].species, mask) : sets[i].species == species))
                c++;
        if (!c)
            continue;
        k = below(state, c);
        for (i = 0; i < total; i++) {
            if (!(sets[i].flags & F_BOSS) && (pass ? has_type(sets[i].species, mask) : sets[i].species == species)) {
                if (!k)
                    return &sets[i];
                k--;
            }
        }
    }
    return 0;
}

void fr_gen_opponent(void)
{
    const struct Hdr *h = (const struct Hdr *)fr_sets;
    const struct Set *sets = (const struct Set *)(fr_sets + sizeof(struct Hdr));
    u32 n = VARS[0];
    u32 doubles = VARS[1] & 1;
    u32 seed = (u32)VARS[2] | ((u32)VARS[3] << 16);
    u32 count = doubles ? 4 : 3;
    u32 round, tier, i, tries;
    const struct Set *team[4];
    u32 have = 0, legends = 0, megas = 0;
    u32 rs;
    u32 theme = (u32)VARS[6] | ((u32)VARS[7] << 16);
    u32 shadow = VARS[8] & 1;
    u32 heir = 0;

    if (n == 0)
        n = 1;
    rs = seed ^ (n * 0x9E3779B1u) ^ 0x6A09E667u;
    if (rs == 0)
        rs = 0x1234567u;
    for (i = 0; i < 4; i++)
        rnd(&rs);

    round = 0;                                   /* (n-1) / 7 without a division helper */
    {
        u32 k = n - 1;
        while (k >= 7) { k -= 7; round++; }
        if (k == 6)                              /* the 7th battle of a round is one tier harder */
            round++;
    }
    tier = 1 + round;
    if (tier > 4)
        tier = 4;

    if (!shadow && below(&rs, 8) == 0)
        heir = 1 + below(&rs, 4);
    VARS[9] = (u16)heir;
    if (heir) {                                  /* Heirloom Set: a borrowed team of an iconic trainer */
        const u16 *lst = (const u16 *)(fr_heirloom + (heir - 1) * 14);
        u32 nlst = lst[0], t2;
        for (t2 = 0; have < count && t2 < 60; t2++) {
            u32 sp = lst[1 + below(&rs, nlst)], j, dup = 0;
            const struct Set *s;
            for (j = 0; j < have; j++)
                if (team[j]->species == sp)
                    dup = 1;
            if (dup)
                continue;
            s = set_of(sets, h->total, sp, &rs);
            if (s)
                team[have++] = s;
        }
    }
    if (shadow) {                                /* Shadow of the Past: a set for each of the player's own species, in party order */
        u32 slot;
        for (slot = 0; slot < 6 && have < count; slot++) {
            const volatile u8 *m = (const volatile u8 *)(0x02024284 + 100 * slot);
            u32 sp = (u32)m[32] | ((u32)m[33] << 8);
            const struct Set *s;
            if (!sp)
                continue;
            s = set_of(sets, h->total, sp, &rs);
            if (s)
                team[have++] = s;
        }
    }
    for (tries = 0; have < count && tries < 200; tries++) {
        u32 t = tier;
        const struct Set *s;
        u32 j, bad = 0;

        if (t > 1 && below(&rs, 10) < 3)
            t--;                                 /* 30%: one tier easier, for variety */
        s = &sets[h->start[t - 1] + below(&rs, h->count[t - 1])];
        if (s->flags & F_BOSS)
            continue;
        if (theme && tries < 120 && !has_type(s->species, theme))
            continue;                            /* the floor's colour: soft, it gives way after 120 draws so a thin tier cannot stall */
        for (j = 0; j < have; j++) {
            if (team[j]->species == s->species || team[j]->item == s->item)
                bad = 1;
        }
        if (bad)
            continue;
        if ((s->flags & F_LEGEND) && legends)
            continue;
        if ((s->flags & F_MEGA) && megas)
            continue;
        team[have++] = s;
        if (s->flags & F_LEGEND)
            legends++;
        if (s->flags & F_MEGA)
            megas++;
    }
    while (have < count) {                       /* could not satisfy the clauses: repeat the last pick (never happens with the real table) */
        team[have] = team[have ? have - 1 : 0];
        have++;
    }

    for (i = 0; i < count; i++) {
        const struct Set *s = team[i];
        const u16 *mv = doubles ? s->moves_d : s->moves;
        u32 j;
        BLOCK[i * 8 + 0] = 255;                  /* iv: 255 = every IV 31 */
        BLOCK[i * 8 + 1] = 50;                   /* level 50, pad 0 */
        BLOCK[i * 8 + 2] = s->species;
        BLOCK[i * 8 + 3] = s->item;
        for (j = 0; j < 4; j++)
            BLOCK[i * 8 + 4 + j] = mv[j];
    }
    VARS[4] = (u16)count;
    VARS[5] = (u16)(rnd(&rs) >> 16);
    RESULT = 0;
}


/* fr_pick_speech: copy one random line of each kind into the RAM text buffers the engine / script print from.
 *   in : 0x8005 = a random word (fr_gen_opponent leaves one there); fr_speech = ROM table:
 *        u16 count[3] (intro, defeat, win), u16 pad, then count[0]+count[1]+count[2] ROM pointers to FF-terminated texts
 *   out: 0x02022600 intro (script prints it before the fight), 0x02022680 defeat (word 1 of the speech-table entry: the player won),
 *        0x02022700 win (word 2: the player lost); each at most 128 bytes */
extern const u8 fr_speech[];

static void copy_text(volatile u8 *dst, const u8 *src)
{
    u32 i;
    for (i = 0; i < 127; i++) {
        u8 c = src[i];
        dst[i] = c;
        if (c == 0xFF)
            return;
    }
    dst[127] = 0xFF;
}

void fr_pick_speech(void)
{
    const u16 *hd = (const u16 *)fr_speech;           /* u16 floors, u16 lines per (kind, floor), u32 pad; then the pointers [kind][floor][line] */
    const u32 *ptr = (const u32 *)(fr_speech + 8);
    u32 floors = hd[0], per = hd[1];
    u32 floor = VARS[6];
    u32 r = VARS[5];
    u32 k;

    if (floor >= floors)
        floor = 0;
    for (k = 0; k < 3; k++) {
        u32 idx = (((r >> (5 * k)) & 31) * per) >> 5;
        copy_text((volatile u8 *)(0x02022600 + 0x80 * k), (const u8 *)ptr[(k * floors + floor) * per + idx]);
    }
    RESULT = 0;
}

/* fr_count_fainted: how many of the party's Pokemon are at 0 HP (hidden, unpicked ones have no species and do not count) -> Result */
void fr_count_fainted(void)
{
    u32 i, n = 0;

    for (i = 0; i < 6; i++) {
        const volatile u8 *m = (const volatile u8 *)(0x02024284 + 100 * i);
        u32 sp = (u32)m[32] | ((u32)m[33] << 8);
        u32 hp = (u32)m[0x56] | ((u32)m[0x57] << 8);
        if (sp && !hp)
            n++;
    }
    RESULT = n;
}


/* fr_gen_brain: the Brain's team from his six hand-built sets.
 *   in : 0x8000 = brain (0 Lance, 1 Anabel, 2 Silver), 0x8001 = 1 for doubles, 0x8002/3 = seed, 0x8004 = battle number
 *   out: the party block (3 or 4 Pokemon, Lv 50), 0x8004 = count. The Mega-holder (flag bit 0) is always on the team; the rest are a seeded draw. */
extern const u8 fr_brains[];

void fr_gen_brain(void)
{
    const struct Set *b = (const struct Set *)(fr_brains + (VARS[0] & 3) * 6 * sizeof(struct Set));
    u32 doubles = VARS[1] & 1;
    u32 count = doubles ? 4 : 3;
    u32 rs = ((u32)VARS[2] | ((u32)VARS[3] << 16)) ^ (VARS[4] * 0x9E3779B1u) ^ 0x3C6EF372u;
    u32 idx[6], i, j, t;

    if (rs == 0)
        rs = 0x1234567u;
    for (i = 0; i < 4; i++)
        rnd(&rs);
    for (i = 0; i < 6; i++)
        idx[i] = i;
    for (i = 0; i < 6; i++) {                        /* the Mega-holder goes first */
        if (b[idx[i]].flags & F_MEGA) {
            t = idx[0]; idx[0] = idx[i]; idx[i] = t;
            break;
        }
    }
    for (i = 1; i < count; i++) {                    /* partial Fisher-Yates over the rest */
        j = i + below(&rs, 6 - i);
        t = idx[i]; idx[i] = idx[j]; idx[j] = t;
    }
    for (i = 0; i < count; i++) {
        const struct Set *s = &b[idx[i]];
        const u16 *mv = doubles ? s->moves_d : s->moves;
        BLOCK[i * 8 + 0] = 255;
        BLOCK[i * 8 + 1] = 50;
        BLOCK[i * 8 + 2] = s->species;
        BLOCK[i * 8 + 3] = s->item;
        for (j = 0; j < 4; j++)
            BLOCK[i * 8 + 4 + j] = mv[j];
    }
    VARS[4] = (u16)count;
    RESULT = 0;
}

/* fr_brain_speech: the Brain's in-battle lines. in: 0x8000 = brain (0 Lance, 1 Anabel, 2 Silver). fr_bspeech = 6 ROM pointers (defeat, win for each)
 * -> 0x02022680 (the player won) and 0x02022700 (the player lost) */
extern const u8 fr_bspeech[];

void fr_brain_speech(void)
{
    const u32 *p = (const u32 *)fr_bspeech + (VARS[0] & 3) * 2;
    copy_text((volatile u8 *)0x02022680, (const u8 *)p[0]);
    copy_text((volatile u8 *)0x02022700, (const u8 *)p[1]);
    RESULT = 0;
}
