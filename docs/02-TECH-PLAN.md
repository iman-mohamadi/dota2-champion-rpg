# Technical Plan (standalone variant — partly superseded)

> **§2 (engine choice), §3 (simulation core) and §7 (server) are superseded by
> [`08-DOTA2-IMPLEMENTATION-PLAN.md`](08-DOTA2-IMPLEMENTATION-PLAN.md).**
> §1 (data-driven constraint), §4 (content pipeline), §5 (extraction), §8 (testing) and
> §9 (legal) all still apply.

# TWRPG Standalone — Technical Plan

How to build what `01-GAME-DESIGN-SPEC.md` describes.

---

## 1. The central architectural constraint

We hold 765 items, 372 hero abilities, 280 boss abilities, 147 monsters and 486 recipes as
data — and that data changes (381 patches in ~6 years). Any architecture that requires a
programmer to touch code when a boss is added has already failed.

**Therefore: a data-driven simulation core with a strict content/code separation.**

```
┌─────────────────────────────────────────────────────────────┐
│  CONTENT  (JSON/TOML, hot-reloadable, schema-validated)     │
│  items · abilities · monsters · encounters · zones · loot   │
│  recipes · vendors · codex · balance curves                 │
└────────────────────────────┬────────────────────────────────┘
                             │ loaded + validated at boot
┌────────────────────────────▼────────────────────────────────┐
│  SIMULATION CORE  (deterministic, headless, no rendering)   │
│  ECS · combat pipeline · status/stacking · abilities ·      │
│  procs & event bus · encounter runtime · loot · inventory · │
│  crafting · progression                                     │
└──────────┬──────────────────────────────────┬───────────────┘
           │ authoritative state              │
┌──────────▼───────────┐          ┌───────────▼───────────────┐
│  SERVER              │          │  CLIENT                   │
│  session · party ·   │◄────────►│  render · input · UI ·    │
│  persistence · anti- │  netcode │  prediction · audio · VFX │
│  cheat · loot roll   │          │                           │
└──────────────────────┘          └───────────────────────────┘
```

**The simulation core must be headless and deterministic.** That single decision buys:
authoritative multiplayer, replay-based bug reports, automated balance simulation (run
10,000 Death Fiend kills overnight to validate drop rates), and a test suite that runs
without a GPU.

---

## 2. Technology choice

### Recommended: **Godot 4 (C#) + a separate .NET simulation library**

| Concern | Fit |
|---|---|
| 3D or 2.5D isometric | Native, both work |
| Open source, no royalties | Yes |
| Dedicated headless server | `--headless` export target, first-class |
| Data-driven content | Trivial — Resources or plain JSON |
| C# for simulation core | Testable, fast enough, shares code client/server |
| Team size 1–3 | Good |

Structure: the simulation lives in a plain .NET class library referencing **no Godot types**.
Godot is the presentation shell. This makes the core unit-testable and, if Godot ever proves
wrong, replaceable.

### Alternatives

| Option | For | Against |
|---|---|---|
| **Unity (C#)** | Largest asset store, best 3D tooling, huge hiring pool | Licensing history; heavier |
| **Bevy (Rust)** | ECS is native and excellent; determinism is easy | Immature UI; UI is a *lot* of this game |
| **TypeScript + Three.js / Phaser** | Browser reach, zero install, fastest iteration | Perf ceiling with 10 players + hundreds of projectiles; heavy anti-cheat burden |
| **O3DE / Stride** | Capable | Small ecosystems |

If browser reach is a hard requirement, use **TypeScript + Node authoritative server** and
accept a 2D isometric presentation to stay inside the perf budget.

---

## 3. Simulation core design

### 3.1 ECS
Entities: heroes, monsters, summons, projectiles, mechanic props (runes, orbs, crystals),
loot chests, portals.

Core components: `Transform`, `Stats`, `Health`, `Resource`, `Attack`, `Movement`,
`AbilityBook`, `StatusEffects`, `Threat`, `Inventory`, `Equipment`, `Faction`, `EncounterRole`,
`LootTable`.

### 3.2 Stats
Two-layer: `BaseStats` (level + allocation + equipment) and `DerivedStats` (after status
effects). Recomputed on dirty-flag, never every frame.

`Stats` is a fixed struct over the enumerated stat vocabulary (findings §3.2) — ~36 fields.
Not a dictionary: it is read on every damage event.

### 3.3 Damage pipeline
One function, one place, matching the spec's stage order:

```csharp
DamageResult ResolveDamage(DamageInstance dmg, Entity src, Entity tgt)
// stages: coefficient → channel multiplier → global multiplier → affinity
//       → crit → type mitigation (armor curve | magicResist | none)
//       → resist/dtpercent/drpercent → shields → death guards
```

Every stage emits a trace entry behind a flag. **Build the damage-trace inspector on day
one** — it is the only realistic way to verify 372 abilities against the source data.

### 3.4 Status effects and stacking
```csharp
record StatusEffect(EffectKind Kind, string SlotType, float Magnitude,
                    float Duration, EntityId Source, bool Stackable);
```
Aggregation groups by `(Kind, SlotType)`: `Stackable` sums, everything else takes max.
Slot letters come from content data, never from code — the devs use slot reassignment as a
balance lever and so will we.

### 3.5 Ability runtime
State machine: `Ready → Casting → Channeling → Active → Cooldown`. Handles interrupts,
sub-menu bar swapping (the `T →` system), toggles, charge/stack abilities, levelled variants,
and specialty-item overrides that patch an ability's fields when a given item is equipped.

### 3.6 Event bus and procs
Events: `OnAttack`, `OnHit`, `OnCrit`, `OnSpellCast`, `OnKill`, `OnDamaged`, `OnHeal`,
`OnDeath`, `OnDebuffApplied`, `OnPhaseChange`.
Procs subscribe with `{chance, internalCooldown, maxDepth}`. Chaining is intentional
(Agnitus's arrows proc on-attack effects) so depth-limit rather than forbid it.

### 3.7 Encounter runtime
Declarative timeline interpreted by the core:

```json
{
  "id": "underlord_agareth",
  "phases": [
    { "at": "100%", "abilities": ["soul_burst", "umbra_dance", "skewer"],
      "adds": [{ "unit": "hellspawn", "every": 30 }] },
    { "at": "50%", "statOverride": { "damageResist": 75 },
      "abilities": ["empowered_soul_burst", "empowered_umbra_dance"],
      "onEnter": [{ "action": "startMinigame", "arena": "soul_crystal_chamber" }] },
    { "at": "10%", "onEnter": [{ "action": "cast", "ability": "armageddon" }] }
  ],
  "partyScaling": { "8-10": { "addHealth": -0.25 } },
  "modes": { "hard": { "damageResist": "+33%", "dropRate": "+50%" },
             "practice": { "damageDealt": -0.75, "damageTaken": 3.0, "drops": false } }
}
```

Actions: `cast`, `summon`, `spawnProp`, `statOverride`, `wipeMechanic`, `instakill`,
`disableRevive`, `setFog`, `startMinigame`, `teleport`, `leashHeal`, `bark`.
Anything this cannot express drops into a scripted hook — budget for ~6 such bosses.

### 3.8 Determinism
Fixed timestep (e.g. 30 Hz simulation, decoupled render). Seeded PRNG per encounter instance,
server-owned. No floating-point-order dependence in the damage path. This makes replays and
overnight balance simulation possible.

---

## 4. Content pipeline

The raw dataset is *descriptive* (English prose), and the engine needs *executable* data.
Bridging that gap is real, budgeted work — see §5.

```
research/raw/*.json                    (source of truth, vendored, never edited)
        │
        ▼  tools/import/            — normalise, resolve id→name, validate references
content/staging/*.json
        │
        ▼  tools/parse-abilities/   — prose → structured effects (regex grammar + review)
        │  tools/parse-conditions/  — boss `conditions` prose → codex objectives
content/authored/*.json             — hand-authored: encounters, zones, curves, art refs
        │
        ▼  tools/build-content/     — schema-validate, cross-check, pack
build/content.pak                   — what the game loads
```

Rules:
- `research/raw/` is **read-only**. Re-cloning upstream must never clobber our work.
- Every generated file records its source and the parser version.
- The content build **fails loudly** on a dangling reference — a recipe naming an item that
  does not exist, a boss dropping an unknown id, an ability referencing a missing effect.
  With 765 items and 486 recipes, this validator will earn its keep immediately.
- Ability parsing produces a **confidence score**; anything below threshold is queued for
  manual review rather than silently guessed.

### 4.1 The ability parser
The prose is regular enough to attack mechanically:

| Pattern | Extracts |
|---|---|
| `Deals (STR X 10.5) magic damage` | coefficient, stat, damage type |
| `Cooldown: 5 seconds` | cooldown |
| `Reduce armor by 15% [Type-A] for 6 seconds` | debuff kind, magnitude, **slot**, duration |
| `20% chance to inflict Bleeding for 5 seconds on attack` | proc chance, trigger, DoT |
| `Heals for max HP X 30%` | heal, scaling source |
| `Stacks up to 10 times` | stack cap |
| `in a frontal cone` / `in the area` | targeting shape |

Note the `[Type-A]` markers are *already in the source text* — the stacking slots can be
parsed directly.

**Revised again after the handler map** ([`06-ABILITY-HANDLER-MAP.md`](06-ABILITY-HANDLER-MAP.md)):
every ability's implementing function is now identified, and 178 have coefficients extracted
automatically. The remaining work is *transcription against a known reference* rather than
reverse-engineering — read the handler, cross-check against the community prose.

**Revised after map extraction:** in-map item descriptions turned out to be *structured*,
not prose — 2,750 `∴`-delimited stat lines across only 36 distinct labels, plus explicit
`▣ Lv.N` requirements (see `04-EXTRACTED-MAP-DATA.md` §6). **Item stats are therefore
near-100% machine-parseable.** The manual burden is now confined to ability *effect* text,
whose numbers live in the obfuscated script and must be recovered from the community
descriptions. Budget roughly 150–200 abilities of hand work rather than the full set.

---

## 5. Closing the data gaps

### 5.1 Extract the `.w3x` — **done**

> Completed. See [`04-EXTRACTED-MAP-DATA.md`](04-EXTRACTED-MAP-DATA.md) for results and
> `tools/extract-w3x/` for the toolchain (a dependency-free MPQ reader plus parsers).
> Terrain, object data and 638 spawn coordinates were recovered; the script is name-mangled,
> so ability numerics and the EXP curve remain in the "if extraction fails" column below.

The original plan for this step, retained for reference:

```
1. Download the map (epicwar 328847 / wc3maps / w3reforged)
2. Unpack MPQ            → MPQEditor, StormLib, or `mpyq` (Python)
3. war3map.w3e           → terrain heightmap + tile types
   war3map.doo           → doodads/props
   war3mapUnits.doo      → unit & item spawn placement (real coordinates)
   war3map.w3u/.w3t/.w3a/.w3b → unit/item/ability/destructible object data (exact stats!)
   war3map.wts           → all localised strings (quest text, barks, tooltips)
   war3map.j / war3map.lua → trigger script: EXP curve, damage formulas, quest logic
4. Convert with w3x2lni / HiveWE / war3structs (Python)
5. Export terrain to a neutral format; author our zones from it
```

**Caveats, stated honestly:** recent TWRPG builds may be protected/obfuscated, so the script
may be unreadable even though terrain and object data usually survive. And **extracted
content is reference material for reimplementation, not shippable assets** — see §9.

### 5.2 Results and residual gaps

> Extraction and partial deobfuscation are done. The EXP curve, armour mitigation curve and
> damage pipeline are recovered exactly — see [`05-COMBAT-FORMULAS.md`](05-COMBAT-FORMULAS.md).
> **No curve fitting is required.** The fallbacks below are retained only for the one
> remaining gap: per-ability numerics for all 652 abilities.

### 5.3 If a value cannot be recovered
- **Geometry** — reconstruct from the 58 location strings plus gameplay video; the zone
  adjacency graph in the design spec §8 is the skeleton.
- **EXP curve** — fit to known anchors (cap 100; −25% requirement in `59p`; raid EXP capped
  at 1 level/kill from L50; 30–80 band buffed in `68n`).
- **Formulas** — infer from ability coefficient text; start from a standard WC3 armor curve
  and tune against boss TTK targets.

---

## 6. Client architecture

- **Rendering** — isometric/top-down 3D, or 2.5D. Camera distance must match the original's,
  since AoE-dodging mechanics were tuned to what the player can see.
- **Input abstraction** — click-to-move by default, WASD swappable (design spec §3).
- **UI is a first-class workload, not an afterthought.** This game is: an ability bar with
  sub-menu swapping, a 24+ slot inventory with drag/drop, a storage window, a **recipe
  browser over a 10-deep dependency tree**, a codex with three tracks, vendor screens, a
  stat allocation screen, a loot chest with per-player claim, a trade window, a party frame
  with buff/debuff icons, and boss frames with phase/cast bars. Budget it accordingly —
  plausibly 30% of total client effort.
- **Prediction** — movement and ability-cast-start predicted locally; damage and loot are
  server-resolved and reconciled.

---

## 7. Server architecture

- Authoritative simulation at fixed tick; clients send intent, receive state deltas.
- **Zone-instanced boss encounters** — each fight is its own simulation instance with its own
  seeded RNG and participant list (needed for loot eligibility).
- Persistence: PostgreSQL. Characters, inventory, storage, codex progress, world-chain state.
  Item instances need stable ids for trading and audit.
- **Server-owned loot rolls, always.** At 0.5% drop rates any client involvement is fatal.
- Trade with per-item limits and soulbound enforcement server-side.
- Rate-limit and audit trading — the original's economy was repeatedly exploited.

---

## 8. Testing and balance validation

This project has an unusual advantage: **the correct answers are in the dataset.**

- **Unit tests** on the damage pipeline against hand-computed cases from item text
  (e.g. Anger's `STR × 10.5` proc at known STR must produce a known number).
- **Stacking tests** — assert two Type-A armor reductions do not stack and a Type-A + Type-B
  do. Directly encoded from `debuffs.json`.
- **Content validation** in CI — no dangling item/boss/ability references, every recipe
  reachable from farmable leaves, every boss's drops exist.
- **Headless balance simulation** — run N thousand encounters; assert drop rates land within
  tolerance of source values, and that boss TTK for a correctly-geared party of size `limit`
  falls in the intended band.
- **Replay capture** for bug reports, enabled by determinism.

---

## 9. Legal and asset position

State this plainly because it constrains the whole art budget:

- **Game systems, mechanics and numbers are not copyrightable.** Reimplementing TWRPG's
  combat model, drop tables and progression is legitimate.
- **Names, descriptions and flavour text sit in a grey area.** Item names ("Agnitus, the Bow
  of Divine Fury") and boss barks are creative expression owned by the map's authors. Using
  them wholesale is a real risk. Options: (a) get permission from greenFruit / the TWRPG
  community — this is a well-organised community and a respectful ask has a decent chance;
  (b) rename during content build via a mapping layer.
  **Build the rename layer regardless** — it costs one indirection in the content pipeline
  and preserves the option.
- **Art, models, icons, sound: cannot be used, full stop.** Blizzard IP plus third-party
  Hive Workshop assets with their own licences. Everything must be original or properly
  licensed.
- **Extracted map data is reference for reimplementation only** — never ship it.

Recommendation: contact the TWRPG community early, on the official Discord / Naver cafe.
Framed as a tribute port with credit, this is likelier to gain collaborators than opposition
— and they hold knowledge that no amount of scraping will recover.

---

## 10. Proposed repository layout

```
twrpg-game/
├── docs/                    # this planning set
├── research/
│   ├── raw/                 # vendored upstream dataset (read-only)
│   ├── tables/              # generated human-readable references
│   └── derive_tables.py
├── tools/
│   ├── import/              # raw → staging
│   ├── parse-abilities/     # prose → structured effects
│   ├── parse-conditions/    # boss conditions → codex objectives
│   ├── extract-w3x/         # map extraction pipeline
│   └── build-content/       # validate + pack
├── content/
│   ├── staging/             # generated
│   ├── authored/            # hand-written: encounters, zones, curves
│   └── schema/              # JSON schemas — the contract
├── src/
│   ├── Twrpg.Sim/           # headless deterministic core (no engine types)
│   ├── Twrpg.Sim.Tests/
│   ├── Twrpg.Server/
│   └── Twrpg.Client/        # Godot project
└── art/
```
