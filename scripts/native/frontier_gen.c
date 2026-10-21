/* Spectrum Frontier opponent generator (docs/BATTLE_FRONTIER_SPEC.md 7.5). Freestanding Thumb code for the GBA, linked by scripts/frontier_native.py.
 *
 *   fr_gen_opponent   in : gSpecialVar 0x8000 = battle number n (1-based streak), 0x8001 = 1 for doubles, 0x8002/0x8003 = challenge seed (lo, hi)
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

    for (tries = 0; have < count && tries < 200; tries++) {
        u32 t = tier;
        const struct Set *s;
        u32 j, bad = 0;

        if (t > 1 && below(&rs, 10) < 3)
            t--;                                 /* 30%: one tier easier, for variety */
        s = &sets[h->start[t - 1] + below(&rs, h->count[t - 1])];
        if (s->flags & F_BOSS)
            continue;
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
