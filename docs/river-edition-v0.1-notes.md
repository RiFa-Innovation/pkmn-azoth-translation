**RIVER EDITION v0.1: an unofficial, fan-made "Chapter 2" for the English translation of Pokémon Azoth (Mercury).**

> ⚠️ **This is not an official release and not part of the beta line.** The *beta N* releases are only a translation of the original hack. The **River Edition** adds **fan-made story content that the original authors did not write** (a continuation after the League, Mt. Silver, Red). It is made by River, with Claude. The hack, its name, characters and story belong to their original authors; this is a translation and an unofficial fan continuation only. Do not report problems with it to the original authors.

## 🐞 Found a bug? [Report it here](https://github.com/RiFa-Innovation/pkmn-azoth-translation/issues/new/choose)
Please say **"River Edition v0.1"** in the title, your **emulator or device**, and attach your **.sav** from just before it happens (an in-game save, not a save state). Chat: [Discord](https://discord.gg/pWnawqhT5C).

## Patch
Apply `Pokemon-Azoth-English-RIVER-EDITION-v0.1.bps` to a **clean Pokémon FireRed (USA) v1.0** ROM (the common "Squirrels" dump #1636), not the Chinese hack and not an earlier beta.

| | |
|---|---|
| Base CRC32 | `DD88761C` |
| Base SHA-1 | `41cb23d8dccc8ebd7c649cd8fbb58eeace6e2fdc` |
| Patch SHA-1 | `8a630fe008df4b013cdffa2c2f2d76b38eeb2083` |
| Patched ROM SHA-1 | `2a49924e337f4e0854232e762940403757ccd224` (32 MB) |

It contains everything in the latest beta translation **plus** the River content below. No save is included: Chapter 2 needs a save that has become Champion (flag-gated), so play it from a late in-game save of your own. In-game saves from the betas carry over; **save states do not**.

## Also in this build
- The title screen carries a red **RIVER EDITION** tag so it can't be mistaken for a beta.
- **Unown report page 12 is translated (#100).** Its text starts mid-string, which is why it stayed Chinese; the English is now written so both pages read.
- **A script-scan bug is fixed (#90):** the loader that blanks junk script pointers read sign/event records with the wrong size, leaving one junk pointer and zeroing three unrelated words in Route/League data.

## ⚠️ Spoilers below (the continuation's story)

## What the River Edition adds
- **A new Chapter 2 story, "The Unwritten Rainbow" (14 scenes).** After the Champion's scene at home it follows Prof. Elm's returned signal, the Radio Tower, Indigo Plateau (Lance, Silver, Anabel), Cliffside (the Elder), the Buried Tower (a Rocket admin battle), the Ecruteak archive, the Whirl Islands (Giovanni, then **Archer**, a new boss battle), the Kimono Girls' song, the theatre, and Navel Rock (Lugia and Ho-Oh). It builds on threads the original leaves open (Archer's rainbow badge, the Rainbow Stone, the cloaked Dragon Tamer, Silver and Giovanni, Sange and Celebi). All dialogue is a first draft.
- **Mt. Silver and Route 28.** A new Route 28, a three-floor Mt. Silver (wild encounters, item balls, eight trainers) and **Red** on the summit as an optional superboss.
- **Mega rewards.** The Latias and Diancie Mega auras (two of the Megas the hack has in its data but never hands out).
- **Reused graphics.** A few overworld sprites (Lugia, Ho-Oh, Celebi, Giovanni, Anabel) come from the Pokémon decompilation projects' assets.

## Known issues (please read)
- **This is v0.1, written without a late-game save to test against.** Triggers may be missed, characters may overlap, and the Radio Tower lobby and the Vermilion ferry to Navel Rock are **untested in a real run**.
- Several characters use stand-in sprites chosen by eye (Archer, Ashida, Tamao, Looker, Lance and others); Anabel's colours need checking.
- After the Ecruteak performance the theatre shows **four** dancers (one place is left empty on purpose); other scenes there may be affected.
- Story progress is stored in new flags and variable `0x5108`; the scenes run in a fixed order.
- **Open reports I could not reproduce without a save**: empty Routes 31 and 37 and a missing Goldenrod quest NPC (#101-#103), the post-League task/lab error (#99), a stuck overworld Pokémon (#95), the Ruins of Alph scene (#63) and the Shadow Lugia lockout (#51). Saves from just before each are welcome.
- All earlier beta known issues still apply (a few Pokédex words baked into graphics, Chinese Mercury Home gift names).

No ROMs are distributed. The patch is and stays free.
