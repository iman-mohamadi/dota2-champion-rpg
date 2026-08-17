# ChampionRPG — Research Findings

*Research into TWRPG (The World RPG), the Warcraft III map this project rebuilds.*

What the map actually is, what data exists, and what does not. Everything here is sourced;
nothing is invented. Read this before the design spec — several findings change what the
game we build should look like.

---

## 1. Identification

**TWRPG = "The World RPG"**, a Warcraft III custom map.

| Field | Value |
|---|---|
| Original author | Keekero |
| Current maintainer | greenFruit |
| Genre | Co-op raid/farm ORPG (map-internal label: "RPG with emphasis on raiding") |
| Map size | 480×480 (playable 478×478) |
| Players | 10 (recommended), party scaling from 1–10 |
| Latest versions seen | map `v0.62r`–`v0.65b`; balance patch line reaches `v0.69e` (Dec 2024) |
| Origin | Korean community; official cafe `cafe.naver.com/twrpgn`, WC3 channel `CLAN TWRN` |
| Peak concurrency | ~100–140 players on the official channel in evenings |

It is a *sequel line*: "The World RPG 3" succeeded TWRPG 2, which had steeper requirements.

### Community summary of the design intent

> "While the RPG genre typically involves leveling up and obtaining items, the main content
> of TWRPG is closer to **collecting items**."

This is the single most important sentence in the whole research pass. See §4.

---

## 2. Data sources — what we obtained

### Primary (structured, complete) — now vendored in `research/raw/`

`github.com/sfarmani/twrpg-info` — the dataset behind TWRPG-BOT (the official-ish Discord
bot) **and** behind the community wiki. Confirmed canonical: the Miraheze wiki pages are
pure template stubs (`{{Monster}}`, `{{MonsterDrops}}`, `{{Skills}}`) that render this exact
JSON. There is no extra prose on the wiki to scrape.

| File | Records | Contents |
|---|---|---|
| `items.json` | 765 | full stat blocks, recipes, drop sources, drop rates, grades |
| `bosses.json` | 147 | stats, spells, minions, spawn conditions, locations, party caps, drops |
| `skills.json` | 372 | every hero ability: hotkey, cooldown, full effect text |
| `skills-boss.json` | 280 | every boss ability incl. summons |
| `heros.json` | 37 | class, main stat, role, wearable weapon types, specialty items |
| `builds.json` | 154 | community-endorsed gear builds per class per game phase |
| `changelog.json` | 381 patches | ~11,200 individual change lines — **the de facto systems manual** |
| `buffs.json` / `debuffs.json` | 19 / 11 | the buff/debuff stacking-category rules |
| `tags.json` | 58 | the ability-keyword vocabulary (damage types, CC, shields, affinities) |

### Secondary

- `github.com/alecpayos/twrpg-guidebook` — a community web viewer. Its `dictionaries.ts`
  gave us the **grade→tier-name mapping and the complete stat vocabulary**, which is not in
  the raw JSON.
- Miraheze wiki API (`twrpg.miraheze.org/w/api.php`) — 976 page titles, indexed in
  `research/raw/wiki_page_index.json`. Useful as a name checklist only.
- `forum.wc3edit.net` boss-locations thread — the **summoning-item system** (powder tiers).

### Blocked / unavailable

| Source | Status |
|---|---|
| NamuWiki KR article | Cloudflare bot-gate. Not bypassed. Would have been the best single systems writeup. |
| epicwar.com map page | HTTP 403 to automated fetch. |
| The `.w3x` map file itself | **Now downloaded, unpacked and parsed — see `04-EXTRACTED-MAP-DATA.md`.** Most gaps below are closed. |

---

## 3. The systems, as reconstructed

Sourced from the changelog unless noted. Patch IDs in brackets are citations.

### 3.1 Character

- **Max level 100.** Reduced from 420 in patch `50a`; legacy save codes divide level by 4.
- **Stat points**: 697 total across the run (was 2396 pre-`50a`). Manually allocated into
  STR / AGI / INT. Reallocation is free as of `62l` (previously 10k gold partial /
  100k gold full reset). Cannot be spent while in combat, but *can* be spent inside a boss
  zone if out of combat [`60s`].
- **Three primary stats**, one is the class's "main stat". Several classes are explicitly
  dual-scaling — Shooter (AGI=DPS / INT=support-healer), Dark Knight (STR=burst / INT=AoE
  heal+utility), Hermit (stat determines role entirely).
- **A "Fatigue" system existed and was removed** in `50a`. Do not implement it.
- **Persistence is via save codes**, not a server: `-save` / `-load`, plus `-load2` for
  codes from older map versions [`44h`]. Camera angle [`55a`], cinematic-skip preference
  [`56a`] and other settings are packed into the code. Save code was displayed for 3
  minutes, cut to 15 seconds [`55a`].

### 3.2 Combat model

The stat vocabulary is fully enumerated (from `guidebook-dictionaries.ts` + item data):

| Group | Stats |
|---|---|
| Offense | `damage`, `str`, `agi`, `int`, `allstat`, `mainstat` |
| Vitality | `hp`, `mp`, `hpregen`, `mpregen` |
| Defense | `armor`, `drpercent` (damage reduction), `dtpercent` (damage taken), `mdpercent` (magic defense) |
| Dexterity | `attackspeedpercent`, `movespeed`, `critchancepercent`, `critmultiplier` |
| Damage routing | `skilldamagepercent`, `periodicdamagepercent`, `procdamagepercent`, `aadamagepercent`, `damagedealtpercent` |
| Survival | `dodgechancepercent`, `healingpercent`, `healreceivedpercent`, `revivaltimepercent` |
| Affinities | `affinityiwpercent` (ice/water), `affinitywlpercent` (wind/lightning), `affinityflamepercent`, `affinityearthpercent`, `affinitylightpercent`, `affinitydarkpercent` |
| Meta | `expgainpercent` |

**Damage is routed into distinct channels** — auto-attack, skill, periodic (DoT), and proc
damage each have their own multiplier stat. An ability's text declares its channel, its
damage type (physical / magic / pure), and its elemental affinity. This is why `tags.json`
exists: it is the classification schema the community built to disambiguate 372 ability
descriptions. Our engine must model these channels natively or the numbers will not
reproduce.

Damage formulas are almost always of the form `STAT × coefficient` — e.g. Anger's proc is
`STR × 10.5` magic damage; Agnitus fires arrows for `Attack Damage × 10%` pure damage.

**Buff/debuff stacking is categorical, not additive.** `buffs.json`/`debuffs.json` define
Type-A/B/C/D slots per effect kind. Two Type-A armor reductions do **not** stack — only the
largest applies; a Type-A and a Type-B do. Some are explicitly `Stackable`. Example of the
rule being used as a balance lever: Merchant's specialty was changed so its debuff "no
longer belongs to Type-A category and can now stack with all other debuffs" [`62v`].

Enumerated stacking slots:

- Buffs: Damage Dealt (A,B), Attack Damage (A-fixed, B/C/D-percent), Attack Speed (A,B),
  Skill Damage (B-staff, B-gun, C, Stackable), Magic Defense (A), Damage Reduction (A),
  Healing Received (A), All Stats (A,B), HP Regen (A), Main Stat (A).
- Debuffs: Armor Reduction (A,B,C), Increased Magic Damage Taken (A,B,C), Increased Damage
  Taken (A,B,C,D), Reduced Healing Received (A).

Armor types (`Light`/`Medium`/`Heavy`) and separate `magicResist` / `damageResist`
percentages exist on every monster.

### 3.3 Skill layout

Every hero uses the same key ring: **Q W E R T F D**, plus passives.

- 7 skills is the baseline (11 classes), 8 is next-most-common (11 classes).
- **Sub-menus / stance systems** are the main source of complexity: hotkeys like
  `[T] → [W]`, `[R] → [R] → [Q]`, `[D] → [A]`. Pressing `T` (typically a transformation or
  gate ultimate) *replaces the whole bar* with a second set of abilities. Priest and Witch
  both work this way. Two classes have **29 skills** because of layered forms.
- Some skills are toggles (8 instances), some are levelled variants (`Dark Aurora [Lv 1..3]`).

### 3.4 Items

- **765 items** in 19 type buckets: Weapon (Melee/Staff/Gun/Bow/Bag/Shared), Armor,
  Headwear, Accessory, Wings, Material, Token, Icon, Coin, Food, Pickaxe, Misc, Special.
- **Rarity ranks**: `[Normal]` 35, `[Magic]` 46, `[Rare]` 55, `[Epic]` 530.
- **Grades 0–5 are the real progression axis**, and they map to named tiers:

| Grade | Tier name | Item lvl | Count | Dropped by |
|---|---|---|---|---|
| 0 | (base / materials) | 1–80 | 235 | everything |
| 1 | **Deltirama** | 60–80 | 100 | Field + Minor bosses |
| 2 | **Neptinos** | 90–100 | 117 | Minor + Mid bosses |
| 3 | **Gnosis** | 100 | 113 | High bosses (Skeletal King → Shadow Dragon) |
| 4 | **Alteia** | 100 | 106 | Late + Endgame (Death Fiend → Agareth) |
| 5 | **Arcana** | 100 | 94 | Endgame only |

  Cross-checked against changelog phrasing: "minor bosses (= bosses dropping Deltirama grade
  gear)" [`61a`], "Gnosis level boss (SK~SD)" [`61d`], "Alteia tier bosses (DF ~ Agareth)"
  [`61w`], "New item grade 'Arcana' has been added" [`54b`].

- **Weapon-type gating**: each class declares `wearable`. Sniper/Bow Master use bows;
  Shooter/Gunner/Blaster use guns; mages use staves; Merchant and Hermit are the only Bag
  users. "Weapon (Shared)" is usable by all.
- **Specialty items**: named endgame weapons that *modify a specific class's specific
  ability*. Agnitus grants Sniper "+3 max stacks on Storm Shaft". 99 items carry a `spec`
  field. This is a whole balance subsystem, actively patched.

### 3.5 Crafting — the actual core loop

486 of 765 items are craftable. Recipes are flat component lists (1–11 components,
mode = 5). **Chains are deep**: max depth 10, and 44 items sit at depth ≥5.

Fully expanded, the worst item (`Bag of All Evils`, depth 10) costs **60 farmed drops across
25 distinct materials**, including 17× Prius Gold Coin and 15× Prius Silver Coin.
Full per-item costs are computed in `research/tables/crafting.md`.

Combined with drop rates that sit at **0.5%–1% for equipment** [`60v`, `68n`] and **0.15%
for Icons** [`68m`], this is the "collecting items" design the community describes. The
grind is the game.

Notable crafting-adjacent rules:
- Icons can now be used directly as crafting materials without "itemizing" first [`68g`].
- Inventory stacking cap: 5 [`50q`]. Base inventory 24 slots [`26k`]; token inventories 30.
- **Storage/closet** system, 24 slots [`29m`], expandable 1 slot at a time by an item [`60t`].
  Overflow items route bag → storage → ground [`58a`].
- **Trading** exists with per-item limits (max 10 [`50q`], holy water capped at 10 [`63f`]).
  Some items are soulbound.

### 3.6 Currency and vendors

- **Gold** — general currency. Mage Tower sells a 50,000-gold item [`61a`].
- **Prius Silver / Gold / Platinum Coin** — the premium/bad-luck-protection currency.
  Gold coins drop from bosses at **0.5%–0.75% scaled by boss difficulty** [`62z`].
  Documented exchange rates [`58a`]:
  - Equipment: 6 silver to buy / 1 silver when sold
  - Material: 9 silver to buy / 1 silver when sold
  - 3× Gold Coin → Field Boss Icon; 4× → Spirit Beast Icon; 8× → Bone Dragon Icon;
    5× → Coin of Effort; 3× → any equipment/material from Bone Dragon tier
- Unsaved items can be auto-converted to Prius Silver on save [`51a`].
- NPCs: Coin Trader, Weird Magician, Mage Tower, Collector, stat-exchange NPC by the Prius
  portal — all clustered in **Capital Prius**, the hub city [`50a`, `61f`].

### 3.7 Boss encounters — the content spine

39 true bosses across 6 tiers, plus 51 creeps, 45 minions and 9 "mechanic" units (destructible
objects, orbs, statues that exist purely as encounter mechanics).

| Tier | Lvl | Count | HP range | Party cap | Respawn |
|---|---|---|---|---|---|
| Field | 30–80 | 9 | 12.5k – 450k | 1–2 | none |
| Minor | 50–100 | 13 | 250k – 1.5M | 3–5 | 4–5 |
| Mid | 100 | 4 | 3M – 3.5M | 3–5 | 4 |
| High | 110 | 6 | 7.2M – **75M** (Ancient Ent) | none | 3–5 |
| Late | 120 | 3 | 7.5M – 11M | 4 / none | 3–5 |
| Endgame | 120–130 | 6 | 11M – 30M | none | 3–4 |

- `limit` = maximum party size allowed into the fight. Field bosses are solo/duo content;
  endgame is uncapped (10).
- `respawn` = cooldown in minutes. Field/minor bosses cap at 15 respawns per game at 6+
  players [`61f`].
- **Spawn conditions are gated summons, not timers.** Bosses require: a level threshold, a
  consumed summoning item, and sometimes a prior boss kill. E.g. Demon Lord Beriel needs
  "Level 90, Red Magic Stone ×6 at the pile of skulls in Area 7, and waves defeated without
  killing the gate". Underlord Agareth needs "Level 100, Demon Lord summoned, and Demonic
  portal destroyed" — a **chained, world-state-driven encounter**.
- The forum thread documents the older summoning economy: a **powder upgrade ladder**
  (White → Green → Blue → Red → Holy), each tier costing the previous powder plus a
  higher-grade Magic Stone. Bosses cost e.g. Lucifer = 12 Red Powder, Lich = 10 Blue Powder.
- Encounters are genuinely scripted. Agareth has **17 named abilities, 4 minion types,
  an "empowered" stat set (damage resist 50%→75%), and an instanced mini-game phase**.
  Others feature: instakill mechanics at HP thresholds that block revival [`62q`], wipe
  mechanics, silence runes [`62y`], Fog phases that disable self-res [`68b`], boss healing
  from players who die outside the zone [`66b`], HP-draining rune-standing mechanics that
  scale down 25% at 8–10 players [`64b`].
- **Loot**: bosses at Arcana tier and above drop into a **shared Loot Chest** (explicitly
  *not* personal loot) lootable only by fight participants [`63e`]. Chest disappears once
  all players have taken or abandoned [`52d`]. A "Boss Fairy" NPC lets you inspect the
  boss's drop table and associated recipes before/after the fight [`61p`].
- A **Wish system** exists: nominate a target drop, and nothing else drops but the wished
  item's rate increases by 100% [`68m`, `59h`].

### 3.8 Difficulty modes

- **Hard Mode** [`66u`, `59a`] — per-boss opt-in. Documented effect on one boss: boss gains
  +33% damage reduction, **+50% drop rate**. Loot chests are flagged as Hard Mode.
- **Practice Mode** [`61w`] — boss deals **75% less damage**, takes **300% more damage**,
  and **drops nothing**. Initially limited to Alteia-tier bosses (Death Fiend → Agareth).
  Disabled during event map versions [`62c`].
- **Party-size scaling** — mechanics tune themselves to headcount (e.g. 8–10 player servant
  HP −25% [`64b`]; chest spawn 50% base → 100% at 5+ players [`50a`, `50c`]).

### 3.9 Other systems

- **Mining** — Pickaxes are an item type (Mithril / Chaos / Abyssal). Channelled until
  interrupted [`20c`]. Yields Magic Stones; chance to mine Medium/Greater stones is 1/4
  [`23f`]. There is a "corrupted mine" area [`50p`]. Magic Stones feed boss summoning.
- **Teleporter network** — a paged menu ("second page, option [2]") plus physical portals
  and obelisks. Portal to Town 4 unlocks on defeating Samael [`30a`]. Several endgame bosses
  are reachable *only* via specific teleporter menu slots.
- **World events** — the **Hell Invasion**: destroying the demonic portal after summoning
  the Demon Lord opens the path to Agareth. There is an invasion cinematic [`50c`].
- **Seasonal events** — Winter Event (2025), Weird Event (2026), Beachball/Blue-crab
  mini-games, Lucky Pouch. Event versions are separate map builds with their own drop tables.
- **Revive rules** — a rich sub-system. Self-res items/skills, manual revives by allies, and
  explicit carve-outs where revival is forbidden (death during Fog, death to a failed 40%-HP
  mechanic) [`68b`, `66h`, `62q`].
- **Tutorial** — "Short tutorial system has been added" [`50a`], with a tutorial quest [`50e`].
- **Chat/utility commands** — `-save`, `-load`, `-load2`, `-skip`, `-angle`.

---

## 4. The finding that matters most: there are almost no quests

You asked for quests. Honest answer, so the plan is built on truth rather than assumption:

**TWRPG is not a quest-driven RPG.** Across 11,229 changelog lines, the word "quest" appears
**9 times** in ~6 years of patches:

- `50a` — a short tutorial system was added; `50e` — its text was fixed
- `26k` — a bug preventing turn-in of "the Ice Shard quest"
- `29b` — quest-giver NPCs relocated; quest EXP band is level 1–400
- `58f` — quest save bug

There is **no quest log, no quest chain, no story questline**. Quest-giver NPCs exist and
hand out a handful of fetch/collection tasks in the early game, and that is the extent of it.

What *replaces* quests as the progression driver is a three-part loop:

1. **Gated boss summons** — collect specific materials (magic stones, powders, tokens) to
   physically spawn the next boss. This is structurally a quest: "bring me 6 Red Magic
   Stones to Area 7". It is just not presented in a quest UI.
2. **Recipe completion** — the crafting tree *is* the objective list. "Craft Bag of All
   Evils" is a 60-drop, 25-material objective with real dependency structure.
3. **World-state chains** — summon Demon Lord → destroy portal → Hell Invasion → Agareth.

**Design implication for our game:** we should build a **Codex/Objective system** that
surfaces these implicit goals as explicit trackable quests. That is a genuine improvement
over the original and it costs us nothing in fidelity, because the underlying requirements
already exist as hard data in `bosses.json` (`conditions` field) and `items.json` (`recipe`).
This is spec'd in `01-GAME-DESIGN-SPEC.md` §7.

---

## 5. Data completeness scorecard

| Domain | Coverage | Confidence |
|---|---|---|
| Item stats, recipes, drop sources, drop rates | 765/765 | **High** — machine-readable |
| Hero roster, roles, weapon gating, specialties | 37/37 | **High** |
| Hero abilities: name, key, cooldown, effect text | 372/372 | **High** for text, **Medium** for exact numbers (prose, not fields) |
| Boss stats, spells, minions, spawn conditions, drops | 147/147 | **High** |
| Boss ability effects | 280/280 | **Medium** — descriptive |
| Item grade/tier progression | complete | **High** |
| Buff/debuff stacking rules | complete | **High** |
| Zone list and level bands | derived from 145 monster locations | **Medium** — see §6 |
| Currency/vendor rates | partial | **Medium** — changelog snapshots, may be stale |
| Boss summon requirements | in `conditions` prose, all 140 | **Medium** — needs parsing |
| **EXP curve / level table** | **RECOVERED EXACTLY** from `war3mapMisc.txt` | **High** (doc 05 §2) |
| **Base hero stats & per-level growth** | **EXTRACTED** — all heroes 500 HP / 500 MS, growth 0.0 | **High** (doc 04 §4) |
| **Attack damage formula** | **RESOLVED** (`base + dice`; see doc 04 §4) | **High** |
| **Armor→mitigation curve** | **RECOVERED EXACTLY**, dual-confirmed | **High** (doc 05 §4) |
| **Map geometry, terrain, pathing, coordinates** | **EXTRACTED** — 481×481 terrain, 638 spawn coords | **High** (doc 04 §3, §5) |
| **Quest definitions** | **near-absent (by design)** | n/a |
| **Art, models, icons, sound** | **absent (and not licensable)** | n/a |

---

## 6. The remaining gaps and how to close them

> **Update:** the extraction described in this section has since been carried out.
> Results, including real world coordinates and derived zone geometry, are in
> [`04-EXTRACTED-MAP-DATA.md`](04-EXTRACTED-MAP-DATA.md). The script was then partially
> deobfuscated and the gameplay constants recovered — EXP curve, armour formula and the
> damage pipeline are in [`05-COMBAT-FORMULAS.md`](05-COMBAT-FORMULAS.md).
> **Gaps A–D are now closed**; what remains is per-ability numerics (doc 05 §7).

### Gap A — Map geometry (biggest)

We know zone *names*, their level bands, and relative directions ("East of Starter Village",
"South of Frosty Snowfield"). We do not have coordinates, terrain, or spawn points.

**Options, in order of preference:**
1. **Extract from the `.w3x` file.** The map is freely downloadable (epicwar 328847, wc3maps,
   w3reforged). Tools: `MPQEditor` / `StormLib` to unpack, then `w3x2lni`, `HiveWE`, or the
   Python `war3structs` library to read `war3map.w3e` (terrain), `war3map.doo` (doodads),
   `war3mapUnits.doo` (unit/spawn placement), `war3map.w3u/.w3t/.w3a` (unit/item/ability
   object data), and `war3map.j` / the Lua root (trigger logic — where EXP curves, damage
   formulas and quest text actually live). **This closes Gaps A, B, C and D simultaneously
   and is the highest-leverage single task in the whole project.**
2. Reconstruct by hand from the 58 location strings + gameplay video reference.

*Caveat: many recent TWRPG builds are protected/obfuscated. Expect the script to be
deprotected with effort or not at all. Terrain and object data are usually still readable
even when script is mangled.*

### Gap B — EXP curve and hero base stats
Only obtainable from the map script or by instrumenting live play. Fallback: fit a curve to
the known anchors (max level 100; EXP-to-level reduced 25% in `59p`; raid EXP capped at
1 level per kill from level 50 [`58h`]; monster EXP in the 30–80 band increased [`68n`]).

### Gap C — Exact formulas
Derivable from the script. Fallback: infer from ability text (`STR × 10.5` style
coefficients are stated explicitly in most descriptions) and use a standard WC3-derived
armor formula as the starting point, then tune.

### Gap D — Ability numbers as structured fields
372 hero + 280 boss abilities are currently English prose. They need to be parsed into
structured effect objects. The prose is highly regular ("Deals (STR X 10.5) magic damage",
"Cooldown: 5 seconds", "Reduce armor by 15% [Type-A] for 6 seconds"), so a
regex/grammar-based extractor plus manual review is realistic. Budget this as real work —
it is on the critical path for combat.

### Gap E — Assets
Every model, icon and sound in the map is Blizzard IP or third-party Hive Workshop content.
**None of it can ship.** The plan assumes an original art pass. See `02-TECH-PLAN.md` §9.

---

## 7. Sources

- [sfarmani/twrpg-info — canonical dataset](https://github.com/sfarmani/twrpg-info)
- [TWRPG Items List](https://sfarmani.github.io/items.html) · [Heroes List](https://sfarmani.github.io/heroes.html)
- [alecpayos/twrpg-guidebook](https://github.com/alecpayos/twrpg-guidebook)
- [The World RPG Wiki (Miraheze)](https://twrpg.miraheze.org/wiki/Main_Page)
- [The World RPG v0.62r — EpicWar](https://www.epicwar.com/maps/328847/)
- [The World RPG — wc3maps](https://wc3maps.com/map/313739)
- [w3reforged map database](https://maps.w3reforged.com/maps/categories/role-play-game-rpg/the-world-s4)
- [TWRPG boss locations & summon requirements — wc3edit forum](https://forum.wc3edit.net/warcraft-map-discussion-f67/the-world-rpg-3-boss-locations-t26768.html)
- [TWRPG v0.63h thread — wc3edit](https://forum.wc3edit.net/viewtopic.php?t=38996)
- [The World RPG — NamuWiki (KR)](https://en.namu.wiki/w/%EB%8D%94%20%EC%9B%94%EB%93%9C%20rpg) *(bot-gated; summary via search index only)*
