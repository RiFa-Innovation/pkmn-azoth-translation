# Chapter 2 plan: "The Unwritten Rainbow"

> Proposed continuation written for this fan translation project; none of it is canon from the hack's
> original authors. Chosen by Claude (the owner asked for a pick). Built from `STORY.md` (what exists) and
> `ROADMAP.md` (what the ROM can hold). Every claim about the game below was checked against its text/data
> unless marked **VERIFY**. Cost classes: **C** cutscene only, **B** one boss, **M** reuses an existing map,
> **N** needs new map content.

## 1. The pick, and why

Plot 2 ("The Unwritten Rainbow", hopeful) from the outside proposal, **with these changes of mine**:

1. **The Priestess is Sange.** Chapter 1 says the sealed document that told Sange her fate was left by "the
   Priestess of Ecruteak", which "recorded the history of the Sacred Child and the Time Flute and predicted the
   calamity's return". Sange was sent about 150 years back and wrote she'd play "until the end of my life". The
   Priestess of Ecruteak is **Sange, grown old in the past**. Closed causal loop: nothing is rewritten, her farewell
   keeps its full weight, and her life becomes visible in the present. (The epilogue's flute heard on Bell Path
   "from a time long forgotten" is the same thread.)
2. **The counter to Archer is a song, not a hero.** Rainbow Stone shards respond to sincere resonance (Time Flute,
   Ho-Oh's Rainbow Wing). Archer forces resonance with a transmitter; the sisters' performance of Sange's melody
   answers it freely. Anything the player does alone only buys time.
3. **The finale is where Chapter 1 showed Archer.** The last Chapter 1 image is Archer before "an enormous
   waterfall" in a dark, damp cavern, with a rainbow-glowing "R". That is the Whirl Islands waterfall chamber (map
   `55.16`, where Lugia slept). The last act happens there.
4. **Lugia goes to Navel Rock.** Chapter 1 ends with Lugia vanished. The Mystic Ticket (Ashida's gift) is the vanilla
   ferry pass to Navel Rock. Epilogue: Lugia and Ho-Oh together over Navel Rock, the "faint rainbow shimmer" Red looks
   at on Mt. Silver. No new maps needed.
5. **Red stays optional** (as built). His shimmer is the epilogue's rainbow.

Why this one: no time loop to explain, no new region, no new villain, uses 9 existing places, one mandatory boss
and a closing image that pays off Sange, Archer, Lugia/Ho-Oh, the Kimono Girls' empty place, Red's placeholder and the
"Rainbow" title together.

## 2. Story bible (what is true in this version)

- **Archer** (proposed motive). Rocket's dissolution taught him devotion can be thrown away; Giovanni walked off and he
  was left holding the name. He wants a bond nobody can leave. He thinks in theatre ("cast", "cue", "last act"); his
  grandest idea is a stage where nobody can exit. The rainbow "R" is a receiver tuned to the Chorus.
- **The Chorus** (my name for the network). Rocket copied a *transmission method* (not the machine) from the
  Anzu installation in Kalos's Prism Tower, a line the game already has. Three **nodes** broadcast Mega energy that
  the Rainbow Stone shards focus. It forced wild Pokémon to Mega Evolve in Chapter 1 (the "Runaway Mega Evolution" quests).
  Anzu itself stays in Kalos; Archer cannot reach it.
- **The anchor.** The Chorus only becomes stable if one Trainer with a powerful bond joins willingly. Archer picked
  the new Champion. The player refuses; Archer forces an unstable override.
- **The nodes.** A = Goldenrod Radio Tower antenna (Rocket's old broadcast hardware). B = Buried Tower, Cliffside
  (Rocket grunts already loiter there). C = the Whirl Islands waterfall chamber (the relay Archer controls).
- **The Rainbow Stone.** It coordinates energy but cannot create a bond. Cliffside's Elder knows this ("Successor" =
  the keeper of that knowledge, not of a weapon).
- **Sange's melody.** The festival piece she played at the Summer Festival and the piece the Burned Tower musician plays
  ("Oracion") are related; the Priestess's score names the true one. It is the key.
- **Lance** is the cloaked Dragon Tamer (the game already equates "caped Dragon Tamer … that guy called Lance").
  His fault: he told Silver his love and trust for Pokémon "isn't enough" and treated a bond like a test score.
- **Silver** protects Pokémon first and does not wait for Giovanni's approval.
- **Giovanni** appears once, to withhold forgiveness and hand over one useful fact. No redemption.
- **Foreign regions** stay dialogue (Kalos = Anzu document, Orre = the Shadow device, Hoenn = Meteor People, Hisui =
  Laventon's caution about time-slips, Sinnoh = Dawn/Lucas). No other region matters mechanically.

## 3. Beat sheet (14 beats)

Stage var **`0x5108` = `CH2_STAGE`** (0 = not started). All beats gate on Champion flag `0x14DB` and the
Ashida scene flag `0x14DA`. "Flag" names are in section 6.

| # | Beat | Maps | Cast | Stage after | Cost |
|---|---|---|---|---|---|
| 1 | A Champion's invitation | `43.0`, `43.6` | Mom (authored), Elm | 1 | C |
| 2 | The voice in the antenna | Radio Tower (`52.36` set) **VERIFY**, Goldenrod | Buena, Looker, Lyra | 2 | C |
| 3 | What the cloak meant | Indigo Plateau lobby (`1.7x`) | Lance, Silver, Anabel | 3 | C |
| 4 | The divided stone | Cliffside (`56.27`), Dragon's Den (`54.x`) | Elder, Axel, Clair, Dawn | 4 | C (+opt M rematch) |
| 5 | Node B | Buried Tower (`56.49` + exterior) | Silver, Dawn, a Rocket admin | 5 | C + optional B |
| 6 | The second page | Ecruteak (`3.70`, theatre/library), Bell Path | Tamao and sisters, Morty, Celebi | 6 | C |
| 7 | The one who walked away | Whirl Islands entrance (`55.14`/`55.15`) | Giovanni, Silver | 7 | C |
| 8 | Node A goes dark | Radio Tower / Goldenrod (remote) | Lyra, Buena, Looker | 8 | C |
| 9 | The last act | Whirl Islands chamber (`55.16`) | Archer (+Ariana opt.) | 9 | **B** |
| 10 | Overload | same | all | 10 | C |
| 11 | The song | same + Ecruteak sisters arrive | Kimono Girls, Lugia (heard) | 11 | C |
| 12 | After the signal | Ecruteak theatre | ensemble | 12 | C |
| 13 | The Mystic Ticket | Vermilion ferry, Navel Rock | Ashida, Lugia, Ho-Oh | 13 | M + C |
| 14 | Quiet credits | Mt. Silver (Red), New Bark (Elm) | Red, Elm | 14 | C |

Beats 4-8 can run in any order after 3 (open middle), except 8 needs 5 and 6 needs 4. Beat 9 needs 5, 6 and 8.

## 4. Scene sheets

### 1. A Champion's invitation (`43.0`, `43.6`)
- Already authored: Mom wakes the player, mentions Ashida and the Mystic Ticket.
- Added: Elm's lab. He has a printout of the forced-Mega signal, "four seconds long, at 3:07 a.m., in the band the old
  Radio Tower used". Pichu/Pikachu reacts. Elm asks the Champion to look (he never orders).
- Sets `CH2_STAGE=1`, flag `CH2_START`. Implementation: an object script on Elm in `43.6` gated by `0x14DA`.

### 2. The voice in the antenna (Radio Tower, Goldenrod)
- Buena: ordinary broadcasts keep dropping for three seconds each night. Looker has recovered a Rocket node on the
  antenna floor.
- Player's Key Stone makes the node glow rainbow. A recording plays in Archer's voice: *"Champion. The stage is set.
  Take your cue."* Looker: "He wasn't planning to defeat you. He needs you."
- Lyra volunteers to stay with Buena. Sets `NODE_A_FOUND`, stage 2.
- **VERIFY:** the Radio Tower interior maps are open after Chapter 1 (flags set during the takeover). Fallback: stage the
  same scene in the Goldenrod Underground warehouse.

### 3. What the cloak meant (Indigo Plateau lobby)
- Lance admits he was the cloaked opponent and that he told Silver his bond wasn't enough. He says plainly that
  he judged a test result, not a partnership. Kukui can nod from the corner (already in Route 26).
- Silver arrives with a Rocket coil he took from a grunt. He joins the investigation on his own terms.
- Anabel confirms the Orre Shadow device is coercive and must be removed, not copied.
- Stage 3, flags `LANCE_CLEARED`, `SILVER_JOINS`.

### 4. The divided stone (Cliffside, Dragon's Den)
- Elder: the Rainbow Stone concentrates energy, it cannot make a bond. Archer's plan only works with a Trainer who
  chooses to connect; refuse and the system breaks, hurting every Pokémon it touches.
- Axel demonstrates "evolution beyond evolution" depends on one partnership. Clair adds the Dragon Tamer view of
  the old Lugia/Ho-Oh war: two traditions about one event.
- Dawn compares notes with the Galactic research she saw in Sinnoh. Optional Axel rematch (existing Lucario fight).
- Stage 4, flag `ELDER_KNOWS`. Reward: a short line about a Mega Stone only if it does not duplicate an existing quest.

### 5. Node B (Buried Tower)
- The exterior already has a loitering Rocket. Silver and Dawn go in with the player.
- Short scene: the node sits where the tower's buried floors meet the sea. The Rocket admin (reuse Ariana's trainer
  entry or a free one) says the player is "late for their own cue".
- The player disables it by holding the Key Stone to the node, but only for a few seconds. It restarts: the stone needs
  something else (sets up beat 6).
- Stage 5, flag `NODE_B_DOWN` (temporary). Optional boss: **B**, one trainer fight.

### 6. The second page (Ecruteak)
- Tamao and the sisters have a sealed document the Priestess left (canon). Rule from Chapter 1: only the youngest
  sister may read it. Sange is that sister, so the seal has never opened.
- Celebi appears briefly on Bell Path (a flute is heard) and the seal opens for the Key Stone's resonance.
- The page is not a map or a spell: it is a score with a margin note in a hand the sisters recognise as Sange's,
  signed with the name she was given as Priestess. It names the piece that resonates with the Rainbow Stone and says
  "play it together, and leave my place empty. That is the promise." The player realises the Priestess and Sange are
  one person.
- No retrieval, no reunion, no second meeting. Celebi only bears witness.
- Stage 6, flags `PRIESTESS_PAGE`, `SONG_LEARNED`.

### 7. The one who walked away (Whirl Islands entrance)
- Giovanni, silhouetted (Rocket gear, no battle). Silver speaks first; Giovanni answers coldly, without apology. He gives
  one fact: the chamber behind the waterfall was once a Rocket facility, and its transmitter is still wired.
- Silver chooses to free affected Pokémon first. Giovanni leaves. No hug, no forgiveness.
- Stage 7, flag `GIOVANNI_SEEN`.

### 8. Node A goes dark (Goldenrod, remote)
- Lyra, Buena and Looker cut the antenna node using the broadcast schedule (Buena's idea). They report by Pokégear.
- The player gets a phone call scene (the hack has a call system) rather than a map.
- Stage 8, flag `NODE_A_DOWN`.

### 9. The last act (Whirl Islands, waterfall chamber)
- Archer stands before the waterfall, the shards arranged around a ring. He is theatrical, calm, and sincere.
  He invited the Champion because the Chorus needs a willing first connection. The player refuses; he attempts an override
  anyway. Silver and Dawn peel off to free the Pokémon being fed into the ring.
- **Battle:** Archer, new trainer entry, six Pokémon at Lv 64-70 with a held `Mega Stone` (item `533`, which AI
  trainers already use) on one of them. Team seeded from his existing roster (Pidgeot, Alakazam, Aggron, Houndoom,
  Tyranitar, Salamence) with a stronger line-up.
- After the final Pokémon faints the ring surges instead of stopping: Archer's last line is not a threat but a plea
  ("then let them stay on the stage with me"). Stage 9.

### 10. Overload
- Silver is hurt freeing a Pokémon. The ring's rainbow turns jagged, wild Pokémon around the islands begin to Mega
  Evolve. Archer realises he cannot stop it either. This is the beat that makes the stakes physical.

### 11. The song
- The sisters arrive by boat (they were already on their way; the score said where to play). They stand on the rocks
  and play Sange's piece. The ring stops fighting and begins to resonate freely.
- Lugia answers the song from far away (heard, not seen). The ring dims to a calm rainbow and shuts.
- Archer is taken into custody by Looker and Anabel, closing the "investigation file that remains open". He is not
  excused; he is understood.
- Stage 11, flags `CHORUS_DOWN`, `ARCHER_CAUGHT`.

### 12. After the signal (Ecruteak theatre)
- The performance resumes with Sange's place still empty, but a flute now rests on it as part of the show.
- Silver leaves without waiting for Giovanni. Lance gives a short, direct line to the player and to Silver.
- Stage 12, flag `CH2_ENDING_SEEN`.

### 13. The Mystic Ticket (Vermilion, Navel Rock)
- Ashida at the Vermilion harbour hands over the ticket scene (item already given; he can explain it).
- Navel Rock summit: Lugia and Ho-Oh together, the "faint rainbow shimmer". Optional catch/battle at vanilla levels
  (the vanilla script). **VERIFY** the vanilla Navel Rock flow still runs in this hack (`2.0`, `2.36`, `2.43`-`2.46`, `2.54`, `2.55`).
- Stage 13, flag `NAVEL_ROCK_DONE`.

### 14. Quiet credits
- Mt. Silver: Red (silent), after the player has the ending flag, adds one line: his Pokémon look toward the sea where the
  rainbow was. Elm's last call connects the shimmer to the report from beat 1.
- Stage 14, flag `CH2_DONE`. Hook for Chapter 3.

## 5. Character arcs (the short version)

- **Player.** Becomes Champion, is treated as the answer to everything, and decides not to be. The ending shows the
  world solving the problem together.
- **Lyra.** The reliable one who stays behind; her work is essential, not a power boost.
- **Dawn.** Turns travel into usable comparison; keeps the warm banter with Lyra.
- **Silver.** From "every verdict is about me" to "I protect Pokémon, and I decide what that means".
- **Lance.** Admits his judgement was incomplete; acts differently afterwards.
- **Archer.** Understood but accountable. His motive is abandonment, his method is theatre, his flaw is that a promise
  nobody can leave is not a bond.
- **Sange.** Remains in the past, with a life that reaches the present as a melody and a handwriting.
- **Red.** Silent, optional, and the one who looks at the horizon first.

## 6. Technical plan

### Flags and variables (add to `CLAUDE.md` when built)
Variable `0x5108` = `CH2_STAGE` (checked: unused by any script; **VERIFY** it is inside the hack's variable array).
Flags (80 free in `0x1338`-`0x1387`; used: `0x1338`-`0x133F` items, `0x1340` Red beaten):
`0x1341 CH2_START`, `0x1342 NODE_A_FOUND`, `0x1343 LANCE_CLEARED`, `0x1344 SILVER_JOINS`, `0x1345 ELDER_KNOWS`,
`0x1346 NODE_B_DOWN`, `0x1347 PRIESTESS_PAGE`, `0x1348 SONG_LEARNED`, `0x1349 GIOVANNI_SEEN`, `0x134A NODE_A_DOWN`,
`0x134B CHORUS_DOWN`, `0x134C ARCHER_CAUGHT`, `0x134D CH2_ENDING_SEEN`, `0x134E NAVEL_ROCK_DONE`, `0x134F CH2_DONE`,
`0x1350`-`0x1357` per-cutscene "seen once" guards, `0x1358`-`0x1360` side hooks.

### Trainers (empty-name slots no script references: 456-460, 492-497; 461 is Red)
- `456` Archer (final): 6 Pokémon, one holding Mega Stone `533`, Lv 64-70.
- `457` Ariana (Node B, optional) or reuse trainer `404`/`405`-style entries.
- `458`-`460` spares for rematches (Axel, Lance, Silver) if wanted.

### New mechanics
None. Uses existing battles, Mega Evolution via held Mega Stone, flags, phone call scene, warps. No new Pokémon,
moves, music or tilesets.

### Tooling to build first (small)
1. **scrasm movement:** `applymovement` with inline step lists, `removeobject`/`addobject`, `fadescreen`, `playfanfare`,
   `setobjectxy`, `turnobject` (opcodes exist; stream encoding is new).
2. **Dialogue speakers:** the hack shows portraits through helper calls (`0x9c` special); start with plain
   "Name: text" lines, add portraits only if the owner wants them.
3. **Spec support for "once" scenes:** coord/obj events gated on a flag with an auto-set at the end (template).

### Cost estimate
About 30-40 short scripts, 10-14 KB of text, plus one trainer entry: roughly **25-40 KB**, well inside the ~670 KB free.
No new map or layout is required.

## 7. Side content (priority order)

1. Goldenrod Dept. Store 6th-floor lottery: the sixth floor is the **Dept. Store lottery floor**, not the Radio Tower; the
   "closed to outsiders" text sits on a different floor. Open the lottery floor after beat 8 as a thank-you.
2. Olivine ferry: reopen after beat 11 (the "engine maintenance" text).
3. Ruins of Alph: two inscriptions about the old Lugia/Ho-Oh conflict, with Morty (optional).
4. Alabaster Icelands: Laventon's warning that a time-slip cannot be steered (optional; reuses the existing scene).
5. Cianwood sea bridge, Johto Safari Zone, Interaction Plaza: defer.

## 8. Cuts, in order

1. Beat 5's optional boss, then the Axel/Lance rematches.
2. Beat 8's phone scene (merge into beat 2's closing line).
3. Beat 13's Navel Rock encounter (keep the cutscene).
4. Side hooks 3-5.
5. Foreign-region cameos except Kalos (Anzu), Orre (Shadow device) and Hoenn (Meteor People).

MVP, protected: beats 1, 2, 3, 6, 9, 11, 12 and 14; Archer as the only new mandatory fight; the song as the ending
mechanic; Sange's page; Silver's choice; Lance's identity.

## 9. Before building: things to verify

- Radio Tower interior is enterable after Chapter 1 and its flags (beat 2).
- `0x5108` lies inside the hack's variable array and no native code touches it.
- Navel Rock's vanilla script and the Vermilion ferry run unchanged (beat 13).
- Ecruteak theatre/library maps for the sealed document (beat 6); where the existing "seal" scene lives.
- A trainer holding Mega Stone `533` actually Mega Evolves in a test battle (existing trainers hold it, so expected).
- Whirl Islands `55.16`: warps, the sisters' arrival staging, and that the waterfall chamber has room for the ring.

## 10. What the authors' wiki adds (checked 2026-10-20)

Source: `https://sum-light.github.io/azoth-wiki/` (news, items, Pokédex, distribution pages; read through a page
summariser, and the atlas/map pages did not load, so treat details as approximate).

- **Timeline.** *Mercury FC ~致150年后的你* ("To You, 150 Years Later", the Chapter 1 title, matching Sange's letter) was
  released 2026-09-28 with 97 side quests. Main Story 1.3.3 (our base) is the latest main-story build (2026-10-08).
  **No Chapter 2 content has been announced**; the wiki says walkthroughs and key-trainer teams are "planned". The
  authors' current work is a *Battle Tower Special Edition 3.0* (Battle Tower + Battle Factory) being ported to the
  **pokeemerald-expansion** engine with Legends Z-A Megas and save transfer through "Mercury HOME".
- **Megas.** The Pokédex lists 1,432 entries with 50+ Mega entries (e.g. #0869 Mega Venusaur, #0870/#0871 Charizard X/Y,
  Z-A Megas, Alolan Megas) and separate Gigantamax entries (#1260+). The ROM's own dialogue has 51 species with a
  "stored X's aura" unlock (Meganium, Typhlosion, Feraligatr, Chandelure, Baxcalibur, Excadrill, Scrafty, Eelektross,
  Clefable, Raichu, Corviknight, Staraptor, Victreebel, Starmie, Scizor, Alakazam, Gardevoir, Lucario, Garchomp, Tyranitar,
  Salamence, Gyarados and more). Megas work through **one generic Mega Stone (#533, "Super Stone")** plus a per-species
  stored aura; it is given by Elm's lab and the Route 30 grandfather. The 19 species-specific stones (#534-#579) exist as items,
  but no script hands them out; the wiki lists their location as "not confirmed".
- **What this changes for the plan.**
  1. Archer's Mega finale needs no new item: any of the 51 aura species can Mega Evolve on a trainer holding `533`
     (existing trainers already do).
  2. Rewards should be *auras* (an unlock scene, like the existing ones), not stones. The unused species stones should not be given out.
  3. Mt. Silver and Red are absent from the wiki's map data. They remain our addition and do not conflict with anything announced.
  4. **Engine risk.** If the authors move the main game to pokeemerald-expansion, this FireRed-based patch and its
     content cannot be carried over automatically. Chapter 2 content built here should stay as data (`data/new_maps.json`,
     scene scripts) so that it can be re-implemented, and should be kept clearly separate from the translation patch.
  5. The Chapter 1 title ("To You, 150 Years Later") supports the Priestess reveal: the authors themselves frame the story
     as a message across 150 years.

## 11. How Mega unlocks work, and 23 Megas that are posted but unobtainable (checked in the ROM)

- **Mechanism (static evidence, not yet UI-verified).** A table at ROM `0x1DE3D04` lists 86 pairs *(species, flag)*; the flag
  is the unlock. The quest scripts that print "X stored Mega Y's aura" end by `setflag` of the matching table flag
  (Pidgeot `0xC04`, Slowbro `0xC06`, Gyarados `0xC0A`, Sableye `0xC17`, Lucario `0xB29`, Meganium `0xB2E`, Feraligatr
  `0xB30`, Starmie `0xC32`, Victreebel `0xC37`, Excadrill `0xC38`, Staraptor `0xC49`, Typhlosion `0xB48`). The message is
  cosmetic (printed by the script or native code); the flag is what the Key Stone logic reads. So a new unlock scene is
  just: scene + `setflag <flag>` + a `say` line. The full table is in `data/mega_unlocks.json`.
- **23 entries have no `setflag` of their flag anywhere in the ROM**: Kangaskhan `0xC08`, Latias `0xC24`, Audino `0xC2C`,
  Diancie `0xC2D`, Emboar `0xC2F`, Barbaracle `0xC31`, Floette `0xC33`, Scolipede `0xC36`, Dragalge `0xC3C`, Chesnaught
  `0xC43`, Delphox `0xC45`, Drampa `0xC46`, Zygarde `0xC47`, Heatran `0xC4C`, Golurk `0xC4E`, Meowstic `0xC4F`, Golisopod
  `0xC51`, Magearna `0xC52`, Zeraora `0xC53`, Scovillain `0xC54`, Glimmora `0xC55`, Tatsugiri `0xC56`, Dondozo `0xC57`.
  (The check cannot see unlocks done through other opcodes or computed flags; treat as "probably unobtainable".)
  These are exactly the "posted but not yet obtainable" Megas the authors left for later chapters.
- **Use them as Chapter 2 rewards, tied to the foreign-region cameos** (all dialogue-only regions in the plan):
  | Region / source | Megas | Plan hook |
  |---|---|---|
  | Hoenn (Cliffside Elder) | Latias | beat 4, the Meteor People story |
  | Rainbow Stone theme | **Diancie** | beat 11, when the Chorus shuts down: the shard's own aura, the plan's namesake |
  | Kalos (Anzu document, Prism Tower) | Chesnaught, Delphox, Meowstic, Barbaracle, Dragalge, Floette, Zygarde, Magearna | beats 2 and 8: the Kalos technical document unlocks them in small groups |
  | Sinnoh (Dawn/Lucas, Galactic thread) | Heatran | beat 5/7: the Stark Mountain report |
  | Unova (research note) | Emboar, Scolipede, Audino, Golurk | beat 4 side hook |
  | Alola (Kukui) | Drampa, Golisopod, Zeraora | beat 3 and epilogue |
  | Paldea (cameo) | Scovillain, Glimmora, Tatsugiri, Dondozo | epilogue/side hook |
  | Kanto (Mom/Ashida) | Kangaskhan | beat 1 or 13 |
  Spread them over the story rather than one dump: a handful per act keeps the Mega theme alive. Archer's Pokémon can
  Mega Evolve using any already-unlockable species (existing trainers already hold item `533`).
- **Cost.** One `setflag` plus a few text lines each (about 60-120 bytes per unlock). No new item or sprite.
- **To verify before building:** that setting a table flag in a test save makes the species appear in the Key Stone
  list (the bag has no Key Items pocket for a test item; use the Key Stone from the real save or an NPC scene), and
  that the Mega form's battle sprite exists for the 23 (the wiki lists the entries; battle graphics unchecked).
