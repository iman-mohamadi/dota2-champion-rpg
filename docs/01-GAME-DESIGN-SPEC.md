# ChampionRPG — Game Design Specification

The game we are building: a standalone co-op raid/farm ARPG that reproduces The World RPG's
systems and content without Warcraft III.

Read `00-RESEARCH-FINDINGS.md` first. Numbers cited here are sourced there.

---

## 1. Design pillars

1. **Fidelity to the loop, not to the engine.** The value of TWRPG is its economy: 39 scripted
   bosses, 765 items, a 10-deep crafting tree, sub-1% drop rates, and 37 classes with real
   mechanical identity. That is what we port. WC3's click-to-move RTS control scheme is *not*
   sacred and should be reconsidered (§3).
2. **The data is the game.** We hold a complete, machine-readable content set. The engine's
   job is to be a faithful interpreter of it. Content must never be hardcoded — every boss,
   item and ability is authored as data.
3. **Fix what the map could not.** WC3 imposed limits TWRPG worked around: 24-slot inventories,
   save codes instead of accounts, no quest log, 10-player lobbies. We keep the *design* and
   drop the *workarounds*.
4. **Grind honestly, but respect the player's time.** 0.5% drop rates were tuned for a
   lobby-based game with no account persistence. With real persistence we can keep the tier
   structure and re-tune the rates. Bad-luck protection (the Wish system, coin exchange) is
   already in the original — lean on it.
5. **Original IP.** No Blizzard assets. The systems are ours to reimplement; the art is not.

---

## 2. Scope decision — three viable products

The full map is roughly 3–5 years of solo work. Pick a tier before writing code.

| | **A. Vertical Slice** | **B. Core Game** | **C. Full Port** |
|---|---|---|---|
| Heroes | 3 (one per stat) | 8–10 | 37 |
| Zones | 2 (Starter Village, Wild Life Habitat) | 8 | 20+ |
| Bosses | 3 (1 creep, 1 field, 1 minor) | ~20 (through High tier) | 39 + 96 creeps/minions |
| Items | ~60 | ~350 | 765 |
| Level cap | 30 | 100 | 100 |
| Multiplayer | none (solo) | 4-player co-op | 10-player co-op |
| Rough effort | 2–3 months | 12–18 months | 3–5 years |

**Recommendation: build A, designed as a strict subset of C.** Every system below is
specified at full-C fidelity so that A never needs rewriting — the difference between tiers
is how many rows are in the content tables, not how the engine works.

---

## 3. Control scheme — an explicit decision

TWRPG is WC3: right-click to move, Q/W/E/R/T/F/D for abilities, some ground-targeted, some
unit-targeted. 

Two options:

**Option 1 — Faithful (click-to-move + hotkeys).** Preserves exact ability feel, camera
distance and kiting patterns. Lowest risk to encounter fidelity: boss mechanics like
"stand on the rune", "dodge the cone", "kite out of the AoE" were tuned against this
movement model. **Recommended.**

**Option 2 — Modernised (WASD + cursor aim).** Better feel for a standalone action game, but
it silently rebalances every boss: dodging becomes far easier, and 39 encounters would need
re-tuning from scratch.

Go with **Option 1** for the port, and keep movement behind an input abstraction so Option 2
stays available as a mode later.

The ability bar must support the original's **sub-menu system**: pressing a form/gate key
(usually `T`) swaps the entire bar to a second set. Two classes reach 29 abilities this way.
This is a hard requirement of the ability system, not a UI nicety.

---

## 4. Character system

### 4.1 Progression
- Level 1 → **100**.
- **697 total stat points** across the run, freely allocated into STR / AGI / INT, freely
  reset (no cost).
- EXP sources: creeps, field bosses, raid bosses, and the small set of early quests.
  Raid boss EXP is available from level 50 but **capped at one level-up per kill**.
- EXP curve is unknown (Gap B). Placeholder: fit `exp(n) = a·n^b` to hit level 100 at the
  observed grind length, and expose it as a tunable data table from day one.

### 4.2 The 37 classes
Full roster with roles, weapon gating, specialty items and per-skill tables:
**`research/tables/heroes.md`**.

| Main stat | Count | Classes |
|---|---|---|
| STR | 10 | Crusader, Lancer, Merchant, Berserker, Knight, Dark Knight, Paladin, Fighter, Lightseeker, Blaster |
| AGI | 14 | Sniper, Shooter, Sword Enchanter, Gunner, Swordsman, Martial Artist, Reaper, Assassin, Thunderer, Bow Master, Phantom Blade, Hermit, Trickster |
| INT | 13 | Soul Weaver, Alchemist, Warlock, Blood Weaver, Fire Mage, Elementalist, Lightning Mage, Wind Mage, Arcane Mage, Water Mage, Priest, Witch, Shrine Priestess |

Note the roster is not just "13 damage archetypes ×3". Roles are specific and mechanically
distinct: **Shield Breaker** (Lancer, Knight, Thunderer, Hermit, Witch), **DoT specialist**
(Sword Enchanter, Warlock, Phantom Blade), **Summoner** (Elementalist), **Buffer/Debuffer**
(Soul Weaver), **Tank Support** (Merchant), **AoE Healer** (Wind Mage, Priest).

**Stat-dependent classes** are a real feature and must be supported: Shooter, Dark Knight
and Hermit change role entirely based on stat allocation. The class system must allow
abilities to scale off, and even branch on, the player's dominant stat.

**Recommended slice-3:** Berserker (STR, 7 skills, self-damage/rage), Sniper (AGI, ranged
burst, mobility), Priest (INT, 16 skills incl. the `T` gate sub-menu — proves the hardest
UI case early).

### 4.3 Equipment slots
Weapon, Headwear, Armor, Accessory, Wings — plus consumables and materials in inventory.
Weapon slot is class-gated by the `wearable` list (bow / gun / staff / melee / bag / shared).

---

## 5. Combat system

The single most important subsystem. Get this wrong and no content is portable.

### 5.1 Damage pipeline

```
base = ability_coefficient × source_stat        e.g. STR × 10.5
  ├─ route by channel: auto-attack | skill | periodic (DoT) | proc
  │    apply the matching % stat (aadamagepercent / skilldamagepercent /
  │    periodicdamagepercent / procdamagepercent)
  ├─ apply damagedealtpercent (global)
  ├─ apply elemental affinity % if the ability declares one
  │    (ice-water, wind-lightning, flame, earth, light, dark)
  ├─ apply crit (critchancepercent → critmultiplier)
  ├─ mitigate by damage type:
  │    physical → armor curve, modified by armorType (Light/Medium/Heavy)
  │    magic    → magicResist, mdpercent
  │    pure     → no mitigation
  ├─ apply target damageResist / dtpercent, source drpercent
  └─ apply shields before health; check Prevent-Death / Unkilleable / Invulnerable flags
```

Every stage corresponds to a stat that exists in the dataset. **Do not collapse the channels.**

### 5.2 Buff/debuff stacking — categorical slots

This is TWRPG's signature balance mechanism and it is fully documented (`buffs.json`,
`debuffs.json`).

Rule: each effect kind (e.g. *Armor Reduction*) has lettered slots (Type-A, Type-B, Type-C…).
**Within a slot, only the strongest instance applies. Across slots, effects multiply.**
Some effects are marked `Stackable` and accumulate.

Modelled as: `StatusEffect { kind, slotType, magnitude, duration, sourceId, stackable }`,
with an aggregator that groups by `(kind, slotType)` and takes max — except `stackable`,
which sums. Because this doubles as the primary balance lever (the devs move an effect from
Type-A to "no category" to make it stack), slot assignment must be a data field on every
effect, never a code constant.

Enumerated slots are listed in `00-RESEARCH-FINDINGS.md` §3.2.

### 5.3 Ability model

An ability is data:

```
Ability {
  id, name, class, hotkey, submenu_parent, order
  cost { hp%, mp, resource }
  cooldown, cast_time, channel_time, max_channel
  targeting: self | unit | point | cone | line | aura | passive | toggle
  range, radius
  effects: [ Effect ]           // damage, heal, buff, debuff, summon, dash, shield, CC…
  tags: [ from tags.json ]      // damage type, channel, affinity, CC-immunity, break…
  proc: { trigger, chance, internal_cooldown }
  spec_overrides: { item_id → modified fields }   // specialty item system
}
```

`tags.json`'s 58 keywords are the effect vocabulary — the community built exactly the
classification schema we need: damage types, Damage-over-Time, Shield, Break, Evade,
CC Immunity, Instakill Immunity, Prevent Death, Unkilleable, Debuff Removal, Revive,
Summoning, Mana Restore, and the six affinities.

### 5.4 Procs
Pervasive: "On attack, 25% chance to activate Devastation… Cooldown: 5 seconds". Requires an
event bus with `on_attack`, `on_hit`, `on_spellcast`, `on_kill`, `on_damaged`, `on_death`,
plus per-proc internal cooldowns. Note the recursion rule from the data: Agnitus's extra
arrows "can proc 'on attack' effects" — proc chaining is intentional and must be depth-limited.

---

## 6. Items, crafting and the economy

### 6.1 Catalogue
765 items — full table in `research/tables/items.md`.
Grade ladder: 0 (base) → 1 **Deltirama** → 2 **Neptinos** → 3 **Gnosis** → 4 **Alteia** →
5 **Arcana**. Grade is the progression axis; item level saturates at 100 by grade 3.

### 6.2 Crafting
486 craftable items, recipes as flat component lists (1–11 components, typically 5).
Chains up to 10 deep. Full expansion costs in `research/tables/crafting.md`.

Crafting is deterministic — no failure chance, no RNG on output. Recipes are consumed on
craft. Rules to preserve:
- Icons usable directly as materials (no "itemize" step).
- Inventory stacking cap of 5 per slot.
- Crafted items overflow bag → storage → ground rather than being lost.
- Craft messages coloured by result grade.

### 6.3 Inventory and storage
- Bag: 24 slots baseline (30 for token forms).
- Storage/closet: 24 slots, expandable +1 per expansion item.
- Overflow chain: bag → storage → ground.

*Recommendation:* keep the slot counts as the default difficulty, but expose them as config.
The 24-slot cap was a WC3 engine limit, not a design goal, and it is the single most common
source of friction in the original.

### 6.4 Currency
- **Gold** — general, from kills and sales.
- **Prius Silver / Gold / Platinum Coin** — bad-luck protection. Gold coins drop at
  0.5–0.75% scaled by boss difficulty. Silver buys equipment at 6, materials at 9, and
  refunds 1 on sale. Gold coins exchange for guaranteed Icons and tier-gear at fixed rates
  (see findings §3.6).
- Vendors live in **Capital Prius**: Coin Trader, Weird Magician, Mage Tower, Collector,
  stat-exchange NPC.

### 6.5 Drop system
- Equipment/material drop rates 0.5–1%; Icons 0.15–1%.
- **Wish system**: nominate a target item; nothing else drops, but the wished item's rate
  gets +100%. This is the pity mechanic — ship it with the drop system, not later.
- **Loot Chest** for Arcana-tier and above: shared, participant-gated, named per player,
  disappears when everyone has taken or passed. Below that tier, drops hit the ground.
- **Boss Fairy** NPC in every boss zone: inspect the boss's drop table, the recipes those
  drops feed, and the live player count. Effectively an in-world encyclopedia — cheap to
  build from our data and a large usability win.

---

## 7. Objectives — the Codex (our addition)

**Finding:** TWRPG has essentially no quests (findings §4). Progression is driven by gated
boss summons, recipe completion, and world-state chains, all of which are *implicit*.

**Design:** build a **Codex** that makes them explicit. Three tracks, all generated from
existing data — no new content authoring required.

**Track 1 — Hunt (from `bosses.json.conditions`).**
Each boss's summon requirement becomes a trackable objective. Example, Demon Lord Beriel:
> Reach level 90 · Deliver 6× Red Magic Stone to the pile of skulls in Area 7 · Defeat the
> waves without destroying the gate

Rendered as a live checklist with progress. This is genuinely a quest; the original just
never showed it.

**Track 2 — Forge (from `items.json.recipe`).**
Pin any item; the Codex expands its full dependency tree, marks owned/missing components,
shows which boss drops each missing leaf at what rate, and computes remaining farm cost.
For `Bag of All Evils` that is 25 distinct materials, 60 total drops.

**Track 3 — Chronicle (from world state).**
The scripted world chains, as an explicit storyline:
Summon Demon Lord Beriel → survive the Hell Invasion → destroy the demonic portal →
Underlord Agareth. Plus: defeat Archangel Samael to unlock the Town 4 portal.

**Track 4 — Legacy quests.** Port the handful that exist: the tutorial quest, the Ice Shard
collection quest, and the early quest-giver NPC fetch tasks.

This is the one place the spec deliberately exceeds the original, and it is low-cost and
high-value.

---

## 8. World and zones

Full inhabitant tables per zone: `research/tables/zones.md`.

| # | Zone | Lvl band | Content |
|---|---|---|---|
| 1 | Starter Village | 3–8 | Spider, Wolf, Dark Wolf, Giant Spider |
| 2 | Kalidi Forest | 10 | Silverback Wolf (first summoning boss) |
| 3 | Wild Life Habitat | 10–45 | Trolls → Furbolgs → Murlocs; Troll Lord, Furbolg Giant, Protector of Nature, King Crab, Walrus, Dragon Turtle |
| 4 | Seaside | 50 | Ruler of the Lav Sea Hydra |
| 5 | Frosty Snowfield / Deep Snowfield | 43–110 | Ice Trolls, Polar Bears; King Kong, Mammoth, Mage Lord, Corrupt Angel, **Shadow Dragon Irbert** |
| 6 | Capital Prius (hub) | — | All vendors, teleporter, Jack o Lantern event boss |
| 7 | Duchy of Wallachia | 60–67 | Soldiers/Archers/Cavalry/Guardians; Death Knight Lord, Blood Wraith, Wallachia Monstrosity, Count |
| 8 | Volcanic Lands / Dragon Lair / Dragon Nest | 62–110 | Lava creeps; Ragnaar, Evil Lava Spawn, Wings of Death, Flame Nightmare, **Bone Dragon** |
| 9 | Deep Sea | 73–100 | Murloc Giants, Tide Callers; Tentacle Lord, Guardian of Sea, Turtle Lord |
| 10 | Castle Avalon | 80–110 | Gatekeeper, Defenders, Protectors, **Archangel Samael** |
| 11 | Wallachia Graveyard | 84–100 | Assassins, Apostles, Scarabs; **Wallachia Mad Clown** |
| 12 | Cave / Golem Cave | 86–130 | Stone/Solid Golems, Giant Golem, Frostspider Lord, **Arcane Construct**, **Styrix** |
| 13 | Fairy Forest / Deep Forest / Plagued Tower | 90–110 | Fairies, Dryads; Corruptor Rectus, Spirit Beast, **Ancient Ent** (75M HP) |
| 14 | East Prius Gate | 80–110 | Guardian Angel, **Demon Lord Beriel**, Skeletal King Desperia, Zombie Lord |
| 15 | Expedition (Area 6) | 90 | Frostspider Queen, Soul of Everfrost |
| 16 | Abandoned Graveyard | 120 | **Death Fiend** + Death Devourer/Hound/Huntress/Weaver |
| 17 | Secluded Forest (tower portals) | 120–130 | **Ifrit**, **Valtora**, **Nereid**, **Gaia** |
| 18 | Hell (via destroyed portal) | 120 | **Underlord Agareth** |
| 19 | Wallachia castle portal | 130 | **Duke Lazarus** |

**Geometry is unknown** (findings Gap A). Zones must be authored as data (tilemap or scene
files) with a defined connection graph; the level bands and adjacency hints above constrain
the layout. Extracting `war3map.w3e`/`.doo` from the `.w3x` would replace this guesswork with
the real thing.

**Travel:** physical portals plus a **paged teleporter menu**. Some endgame bosses (Ifrit,
Valtora, Nereid, Gaia) are reachable *only* through specific teleporter slots. Portals
unlock via world progress (Samael → Town 4).

---

## 9. Encounter system

Bosses are not stat blocks; they are scripts. 39 bosses, 280 boss abilities, 45 minion types
and 9 "mechanic" units (orbs, statues, crystals, spikes that exist only as encounter props).
Full ladder in `research/tables/bosses.md`.

### Required encounter primitives, all evidenced in the data
- **Phases** by HP threshold, including *empowered* stat sets (Agareth: damageResist 50%→75%).
- **Adds/waves** — timed or phase-triggered minion spawns.
- **Instakill mechanics** at HP thresholds, with revival explicitly disabled on failure.
- **Wipe mechanics** with a counter-play window.
- **Environmental hazards** — silence runes, vanish runes, magma, water bubbles.
- **Positional mechanics** — stand-on-rune (drains HP, scales −25% at 8–10 players), frontal
  cones, dodge-the-line.
- **Fog phases** that disable self-resurrection.
- **Zone leash rules** — Styrix heals from heroes who die *outside* the boss zone.
- **Mini-game phases** — Agareth has an instanced sub-arena with its own units (Soul
  Crystals, Gatekeeper of Hell at level 999).
- **Chained encounters** — Agareth requires Demon Lord summoned + portal destroyed.
- **Party-size scaling** on mechanic intensity and chest spawn rate.
- **Enrage/soft-enrage** and boss self-heal.

Implement as a **behaviour-tree / scripted-timeline hybrid**: a declarative timeline
(phases → triggers → actions) covers ~80% of encounters as pure data; the remaining
special cases (mini-games) get an escape hatch into script.

### Encounter parameters per boss
`level`, `stats{health, healthRegen, mana, manaRegen, armor, armorType, magicResist,
damageResist, attackDamage, attackSpread, attackRange, attackSpeed, moveSpeed}`,
`limit` (party cap 1–10), `respawn` (3–5 min), `conditions` (summon gate), `timer`
(enrage/soft timer, 45 bosses have one), `drops`, `spells`, `minions`, `quote` (boss barks —
40 recorded, keep them).

### Difficulty modes
- **Normal**
- **Hard** — opt-in per boss; +damage reduction, **+50% drop rate**, flagged loot chest.
- **Practice** — boss deals **−75% damage**, takes **+300% damage**, **drops nothing**.
  Some mechanics fire less often. Restricted to high-tier bosses. This is the learning
  tool that makes a 17-ability endgame boss approachable — build it early, not last.

---

## 10. Multiplayer

TWRPG is fundamentally co-op: party caps of 1–10 are a *balance parameter* on every boss,
and mechanics scale by headcount.

**Recommendation: authoritative dedicated server, client-predicted movement.** Drop rates,
loot chests and boss state must be server-owned — a 0.5% drop rate on a peer-to-peer client
is an invitation to cheat, and the original's save-code system was notoriously exploitable.

Required: party formation, boss-zone participant tracking (for loot eligibility), shared
loot chest with per-player claim/pass, trading with per-item trade-count limits, soulbound
flags, revive-by-ally.

Ship the vertical slice **solo-only** but write the simulation server-authoritative from day
one. Retrofitting authority into a single-player codebase is the classic project-killer.

**Persistence: real accounts, not save codes.** Keep `-save`-style export as a convenience
feature if desired, but the character lives server-side.

---

## 11. Deliberate deviations from the original

| Original | Ours | Why |
|---|---|---|
| Save codes | Server accounts | WC3 limitation; codes were exploitable |
| No quest log | Codex (§7) | Objectives already exist implicitly; surfacing them is free |
| 24-slot inventory | Configurable, larger default | Engine limit, not design |
| Fatigue system | Omitted | Already removed by the devs in `50a` |
| 10-player lobby | Persistent server, party-based | — |
| Blizzard art | Original art | Legal |
| Drop rates 0.5–1% | Same structure, re-tuned | Tuned for no-persistence lobbies |

Everything else is a faithful port.

---

## 12. Open design questions

1. **Scope tier** — A, B or C from §2? This gates everything.
2. **Control scheme** — faithful click-to-move (recommended) or modernised WASD?
3. **Do we extract the `.w3x`?** It closes four gaps at once and is the highest-leverage
   task available. It also determines whether zone geometry is real or invented.
4. **Retune drop rates, or keep 0.5%?** With persistence, the original rates may be fine —
   but they were designed around a game where you *lost* progress.
5. **Art direction** — the original is WC3 high-fantasy. Do we match the tone with original
   assets, or restyle (pixel art / low-poly / 2D isometric) to cut asset cost dramatically?
6. **Solo viability** — 24 of 39 bosses have party caps ≥3. Does a solo player hit a wall at
   Minor tier, and is that acceptable?
