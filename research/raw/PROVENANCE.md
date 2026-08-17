# Provenance of `research/raw/`

**None of the files in this directory are the work of this project.** Every one was created
and is maintained by someone else. They are mirrored here, with attribution and in good faith,
for a non-commercial fan project.

---

## sfarmani / TWRPG-BOT

**Author:** [sfarmani](https://github.com/sfarmani) (GitHub display name *RockLeeNBU*, known in
the TWRPG community as **Rock Lee**)
**Source:** <https://github.com/sfarmani/twrpg-info>
**Also maintains:** [TWRPG-BOT](https://sfarmani.github.io/) — the Discord bot and reference
site the TWRPG community uses daily, and the [items](https://sfarmani.github.io/items.html)
and [heroes](https://sfarmani.github.io/heroes.html) browsers.
**Licence:** **none stated — all rights reserved.**

| File | Bytes | What it is |
|---|---|---|
| `items.json` | 608,209 | 765 items: stats, recipes, drop sources, drop rates, grades |
| `changelog.json` | 1,203,087 | 381 patches, ~11,200 change lines |
| `skills.json` | 201,504 | 372 hero abilities |
| `skills-boss.json` | 136,984 | 280 boss abilities |
| `bosses.json` | 135,489 | 147 monsters: stats, spells, minions, spawn conditions, drops |
| `builds.json` | 93,331 | 154 community gear builds |
| `heros.json` | 24,930 | 37 classes |
| `tags.json` | 8,940 | the ability-keyword vocabulary |
| `buffs.json` / `debuffs.json` | 8,959 | the Type-A/B/C/D stacking slot tables |
| `commands.json` / `tag-commands.json` | 6,142 | bot command reference |

**This is the backbone of the entire project.** Without it there is no content pipeline: the
765 items, 486 recipes, 147 monsters, 372 abilities and 37 classes that this project generates
are all read from these files. The stacking-slot tables in `buffs.json`/`debuffs.json`
documented a game mechanic that exists nowhere else in writing, and the changelog is the only
surviving record of how TWRPG's systems evolved — it is what let this project date the level
cap change, the fatigue removal, and the 25% EXP reduction.

Several findings credited in `docs/` would have been impossible without this dataset. It
represents years of unpaid community work.

---

## alecpayos / TWRPG Guidebook

**Author:** [alecpayos](https://github.com/alecpayos)
**Source:** <https://github.com/alecpayos/twrpg-guidebook>
**Licence:** **none stated — all rights reserved.**

| File | Bytes | What it is |
|---|---|---|
| `guidebook-dictionaries.ts` | 3,450 | the 34-field stat vocabulary and the grade→tier-name mapping |
| `guidebook-types.ts` | 4,810 | the item and hero type definitions |

Small files, outsized contribution. `guidebook-dictionaries.ts` is the **only** source that
names the item grade tiers — Deltirama, Neptinos, Gnosis, Alteia, Arcana — and the only place
the full stat vocabulary is enumerated. Both are load-bearing throughout `docs/00` and the
generated `data/stats.lua`.

---

## TWRPG Wiki (Miraheze)

**Source:** <https://twrpg.miraheze.org/>
**Mirrored:** `wiki_page_index.json` — page titles only, retrieved via the MediaWiki API.
No article text is reproduced.

---

## The game itself

**The World RPG** is by **Keekero** (original author) and **greenFruit** (current maintainer),
with its community. Warcraft III is © Blizzard Entertainment. Nothing in this directory would
exist without their work.

---

## Status of permission

**Not yet granted.** As of this commit no maintainer has been asked or has replied.
Attribution is not a licence, and this file does not claim otherwise.

If you maintain any source above and want your work removed from this repository, open an
issue or contact the repository owner — it will be removed promptly and without argument.

**If you are reusing this project:** do not assume you may redistribute anything in this
directory. Fetch it from the upstream sources listed above.
