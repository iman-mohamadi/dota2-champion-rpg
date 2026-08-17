# Dota 2 Custom Game — Implementation Plan

**Decision: build TWRPG as a Dota 2 custom game.** Windows access is available, which was the
only blocker (`07-PLATFORM-DECISION.md` §6).

This document supersedes the engine-specific parts of `02-TECH-PLAN.md` and reorders
`03-ROADMAP.md`. The design spec (`01`), the extracted data, and docs `04`–`06` are unchanged
and fully reusable — they were always platform-neutral.

Every API named below was verified against the ModDota declarations
(`github.com/ModDota/API`), not recalled from memory.

---

## 1. The headline finding

The gameplay constants recovered in `05-COMBAT-FORMULAS.md` translate into Dota 2 setup calls
**almost one-for-one.** Warcraft III's `war3mapMisc.txt` and Dota 2's
`SetCustomAttributeDerivedStatValue` describe the same knobs:

| `war3mapMisc.txt` (TWRPG) | Value | Dota 2 equivalent |
|---|---|---|
| `StrHitPointBonus` | 0.0 | `DOTA_ATTRIBUTE_STRENGTH_HP` |
| `StrRegenBonus` | 0.0 | `DOTA_ATTRIBUTE_STRENGTH_HP_REGEN_PERCENT` |
| `AgiDefenseBonus` | 0.0 | `DOTA_ATTRIBUTE_AGILITY_ARMOR` |
| `AgiAttackSpeedBonus` | 0.0 | `DOTA_ATTRIBUTE_AGILITY_ATTACK_SPEED` |
| `AgiMoveBonus` | 0.0 | `DOTA_ATTRIBUTE_AGILITY_MOVE_SPEED_PERCENT` |
| `IntManaBonus` | 0.0 | `DOTA_ATTRIBUTE_INTELLIGENCE_MANA` |
| `IntRegenBonus` | 0.0 | `DOTA_ATTRIBUTE_INTELLIGENCE_MANA_REGEN_PERCENT` |
| `StrAttackBonus` | 3.0 | `DOTA_ATTRIBUTE_STRENGTH_DAMAGE` |
| `MaxHeroLevel = 100` | 100 | `SetCustomHeroMaxLevel(100)` + `SetUseCustomHeroLevels(true)` |
| XP curve constants | — | `SetCustomXPRequiredToReachNextLevel(table)` |

**The exact XP curve can be installed directly.** `SetCustomXPRequiredToReachNextLevel` takes a
cumulative table, which is precisely what doc 05 produced — 99 entries, `[150, 382, 702, 1112,
1617, 2223, …, 3951397]`.

So TWRPG's "we disabled the engine's whole RPG layer" design is *natively expressible* in
Dota 2. That is a much better fit than I expected before checking.

---

## 2. Concept mapping

| TWRPG (Warcraft III) | Dota 2 custom game | Difficulty |
|---|---|---|
| 37 hero classes | custom heroes in `npc_heroes_custom.txt`, reusing Dota hero models | easy |
| QWER/T/F/D ability bar | native ability slots | easy |
| `[T] → [W]` sub-menus | **`unit:SwapAbilities(a, b, enable1, enable2)`** / `UnHideAbilityToSlot` | easy — first-class support |
| Abilities (652) | Lua abilities + KV files | the bulk of the work |
| Buff/debuff Type-A/B/C slots | Lua modifiers with custom stacking logic | medium |
| Damage channels (physical/magic/pure) | Dota's three damage types + `ApplyDamage` `damage_flags` | easy |
| Damage pipeline (`pdo`) | **`SetDamageFilter`** — intercepts every damage instance | easy |
| Armour formula `1/(1+0.02·armor)` | own formula inside the damage filter (see §3.1) | medium |
| Procs (`on attack`, `on hit`, …) | `MODIFIER_EVENT_ON_ATTACK_LANDED`, `ON_ATTACK`, `ON_ATTACKED`, `ON_ABILITY_EXECUTED`, `ON_DEATH`, `ON_HERO_KILLED`, `ON_HEAL_RECEIVED` | easy |
| Stat allocation (697 points) | `MODIFIER_PROPERTY_STATS_{STRENGTH,AGILITY,INTELLECT}_BONUS` + custom UI | medium |
| Items (765) with stats + abilities | Dota items grant modifiers/abilities — same model | medium |
| **24-slot bag + 24-slot storage** | Dota gives 6 + 3 backpack + 6 stash → **needs a custom inventory** | **hard (§3.2)** |
| Crafting (486 recipes) | Lua + custom Panorama UI | medium |
| Drop tables, Wish system, loot chest | Lua | medium |
| 39 scripted boss encounters | Lua, from our declarative timelines | the other bulk of the work |
| Zones / terrain | Hammer, seeded from the extracted heightmap | medium |
| Save codes | **external DB via `CreateHTTPRequestScriptVM`** (§3.3) | medium |
| 10-player co-op | supported (custom games allow up to 24) | free |
| WC3 camera distance | `SetCameraDistanceOverride` | easy |
| Click-to-move | native | free |

---

## 3. The four real friction points

Everything else is routine. These four need design decisions.

### 3.1 Armour formula mismatch

Dota's armour curve uses a 0.06 coefficient and its own shape; TWRPG needs
`damage × 1/(1 + 0.02 × armor)` (doc 05 §4).

**Solution — mirror what TWRPG itself does.** The original bypasses the engine's mitigation and
re-applies its own. Here:

1. Zero out `DOTA_ATTRIBUTE_AGILITY_ARMOR` so agility grants no armour.
2. Track TWRPG armour as a custom stat, not Dota's `PHYSICAL_ARMOR_BONUS`.
3. In `SetDamageFilter`, apply the recovered pipeline in order: channel multiplier → global →
   affinity → crit → `eMo(base, (1 − penetration) × armour)` → resists → shields.
4. Deal ability damage with `DOTA_DAMAGE_FLAG_IGNORES_PHYSICAL_ARMOR` (or as pure) so Dota's
   own curve never applies twice.

This is cleaner than the original: TWRPG had to *probe* armour at runtime because WC3 gave it
no way to read the value (doc 05 §5.1). In Dota we own the number, so the probe disappears.

### 3.2 Inventory — the one genuinely hard problem

TWRPG needs **24 bag slots + 24 storage slots**, stacking to 5. Dota gives 6 + 3 + 6.

**Solution:** a fully custom inventory — Lua-side item state plus a Panorama UI — with Dota's
native inventory used only as a small "equipped" bar (weapon, headwear, armour, accessory,
wings). Roshpit Champions does exactly this for its stash, so it is proven.

**Cost:** this is real work, probably 2–3 weeks, and it drags the crafting UI, vendor UI and
loot UI with it. It is the largest single Dota-specific expense in the project. Budget it
honestly rather than discovering it in month three.

*Design-spec note:* `01-GAME-DESIGN-SPEC.md` §6.3 already flagged the 24-slot cap as a WC3
engine limit rather than a design goal, and suggested a larger configurable default. If you
take that option, this problem shrinks — a smaller custom inventory is less UI work.

### 3.3 Persistence

Dota 2 has no built-in cross-match save. Two mechanisms exist:

- `CreateHTTPRequestScriptVM(method, url)` → your own database (Firebase or similar; free tiers
  are ample for a hobby project). This is the standard approach.
- `SetCustomGameAccountRecordSaveFunction` / `GetPlayerCustomGameAccountRecord` → a small
  Valve-side record, useful for lightweight flags.

**Security caveat:** at 0.5% drop rates, a client-adjacent save path is an exploit target. Keep
all item grants server-side in Lua (custom games run server-authoritative on Valve's servers,
which helps a lot) and treat the HTTP layer as persistence only, never as authority. Sign or
validate writes.

This is strictly better than the original's save codes, which were notoriously forgeable.

### 3.4 Ability volume

652 abilities is the content mountain, unchanged by platform. What *has* changed:

- Doc 06 identifies the implementing function for **324 hero abilities**, with **178
  coefficients already extracted**.
- Dota's modifier system is close enough to WC3's that most abilities port structurally rather
  than needing redesign.

Still the critical path. Still bounded.

---

## 4. Revised architecture

```
game/dota_addons/championrpg/
├── scripts/
│   ├── npc/
│   │   ├── npc_heroes_custom.txt        ← 37 classes (generated from research/)
│   │   ├── npc_units_custom.txt         ← 147 monsters (generated)
│   │   ├── npc_abilities_custom.txt     ← ability KV (generated)
│   │   └── npc_items_custom.txt         ← 765 items (generated)
│   └── vscripts/
│       ├── addon_game_mode.lua          ← constants from doc 05 installed here
│       ├── core/                        ← damage filter, stacking, procs, stats
│       ├── systems/                     ← inventory, crafting, loot, codex, persistence
│       ├── abilities/                   ← per-ability Lua
│       └── encounters/                  ← boss timelines
├── panorama/                            ← custom UI (inventory, crafting, codex, vendors)
└── maps/                                ← Hammer, seeded from extracted terrain
content/                                 ← source art/particles if any
tools/                                   ← existing extraction + NEW KV generators
research/                                ← unchanged
```

**Keep the content pipeline.** `02-TECH-PLAN.md` §4's design still holds — the only change is
that the build step now emits **Dota KV files and Lua tables** instead of a generic
`content.pak`. The schemas, the validator, and the "never hardcode content" rule are unchanged
and still the most important architectural decision in the project.

**What dies from the old plan:** the headless deterministic simulation core, the custom netcode,
the authoritative server, PostgreSQL, prediction/reconciliation, and the whole of Phase 4.
Dota 2 provides all of it.

**What is lost with it:** offline unit-testability. The old plan's ability to run 10,000
simulated Death Fiend kills overnight without a GPU is gone — Dota Lua tests need the game.
Mitigation: keep damage-formula maths in pure Lua modules with no Dota dependencies so they can
be tested standalone; that preserves most of the value of tech plan §8.

---

## 5. Revised roadmap

| Phase | Work | Est. |
|---|---|---|
| **0. Setup** | Windows + Dota 2 + Workshop Tools DLC; TypeScript addon template; Hammer basics; publish a hello-world custom game to confirm the whole loop | 3–5 days |
| **1. Content pipeline** | As before, retargeted to emit Dota KV + Lua. Reference validator unchanged | 2–3 wks |
| **2. Core systems** | Install doc-05 constants; damage filter + armour formula; Type-A/B/C stacking as modifiers; proc event bus; stat allocation | 2–3 wks |
| **3. Custom inventory + crafting UI** | Panorama inventory, storage, recipe browser (§3.2) | 2–3 wks |
| **4. Vertical slice** | 3 heroes (Berserker/Sniper/Priest — Priest proves `SwapAbilities`), 2 zones in Hammer, 3 bosses, ~60 items, Codex v1 | 3–4 wks |
| **5. Persistence** | HTTP + DB, save/load, validation | 1 wk |
| **6. Content scale-out** | Heroes 4–10, zones 3–8, Field/Minor/Mid bosses, grades 1–3, economy, mining, teleporters, Hard/Practice modes | ongoing |
| **7. Endgame** | Late/Endgame bosses, Hell Invasion chain, grades 4–5, remaining heroes | ongoing |

**Playable multiplayer vertical slice: ~10–14 weeks**, versus ~5–6 months of the standalone
plan to reach the equivalent — and the Dota version is *multiplayer from day one*, where the
standalone slice was single-player with multiplayer deferred to a later phase.

---

## 6. Phase 0 checklist

1. Windows 64-bit with a Direct3D 11 GPU.
2. Steam → Dota 2 → Properties → DLC → tick **Dota 2 Workshop Tools**.
3. Launch **Dota 2 – Tools** from Steam.
4. Start from the **ModDota TypeScript addon template** (`ModDota/TypeScriptAddonTemplate`) —
   TypeScript compiles to Lua and gives real type checking across 652 abilities and 765 items,
   which matters a lot at this scale. Plain Lua alternative: the Barebones template.
5. Bookmark `docs.moddota.com` and the ModDota API repo. The Valve wiki is behind an anti-bot
   proof-of-work and is painful to read programmatically.
6. Build a trivial custom game and publish it privately to the Workshop to prove the full
   upload/play loop before writing real content.

### 6.1 Linux/Windows split — don't switch, dual-boot

You do **not** need to move off Linux. The work divides cleanly:

| Task | Linux | Windows |
|---|---|---|
| Research, extraction toolchain, content pipeline (Phase 1) | ✅ everything | not needed |
| Writing Lua / TypeScript gameplay code | ✅ any editor | — |
| Writing Panorama UI | ✅ any editor | — |
| Running the addon locally to test | ✅ *probably* — see below | ✅ |
| Reloading scripts while testing (`script_reload`) | ✅ console command | ✅ |
| **Hammer — building/compiling map geometry** | ❌ | ✅ **required** |
| Particle Editor, model/asset compiling | ❌ | ✅ required |
| Publishing/uploading to the Workshop | ❌ | ✅ required |

Dota 2's **client** is natively supported on Linux; only the **Workshop Tools** are
Windows-only. An addon placed in `game/dota_addons/<name>/` can be launched from the normal
client's console with `dota_launch_custom_game <addon> <map>`, and `script_reload` hot-reloads
Lua at runtime. Panorama UI updates without even reloading the map.

> **Unverified:** I have confirmed the console command exists and that console/launch options
> work on Linux, but I have not confirmed that locally-placed addons load correctly on the
> Linux client specifically. **Test this in Phase 0 — it is a 30-minute check that decides how
> often you need to reboot into Windows.** If it works, Windows becomes an occasional session
> for map work and publishing rather than your daily environment.

Practical arrangement: keep the repo on Linux, sync to Windows via a git remote or a shared
partition. Do map geometry in batched Windows sessions rather than switching constantly.

---

## 7. Legal position — revised, and better

`02-TECH-PLAN.md` §9 assumed shipping original art. On Dota 2 the position changes:

- **Art is solved.** Dota's asset library is usable inside custom games, so the largest cost and
  risk in the standalone plan disappears.
- **Non-commercial by license.** The Dota Workshop license is strictly non-commercial
  (doc 07 §3). Since this becomes a tribute project by construction, the copyright risk around
  TWRPG's item and boss names drops substantially — you are not competing commercially with
  anyone.
- **Keep the rename layer anyway** (tech plan §9). It costs one indirection and preserves the
  option if the project ever moves.
- **Do not port the extracted script.** Everything ships as reimplementation from the
  documented data, exactly as before.
- **Credit prominently:** Keekero (original author), greenFruit (maintainer), and the
  TWRPG-BOT / wiki community for the dataset.
- **Talk to the community early** (roadmap 0.5). A non-commercial Dota 2 tribute is a much
  easier conversation than a standalone game, and they may become collaborators.

---

## 8. What carries over unchanged

Nothing done so far is wasted:

| Asset | Status |
|---|---|
| `research/raw/` — community dataset | unchanged |
| `research/extracted/` — units, items, abilities, terrain, spawns, zones, curves | unchanged |
| `research/tables/` — bosses, zones, items, heroes, crafting, ability handlers | unchanged |
| `tools/extract-w3x/` — MPQ reader, parsers, deobfuscator, ability mapper | unchanged |
| Doc 01 design spec — combat model, items, crafting, zones, encounters, Codex | unchanged |
| Doc 05 formulas — EXP curve, armour formula, damage pipeline | **now directly installable** |
| Doc 06 ability map | unchanged, and more valuable — it says which handler to port |
| Doc 02 tech plan §4 content pipeline, §8 testing, §9 legal | retargeted, not rewritten |
| Doc 02 §2–3 engine choice, simulation core, §7 server | **superseded by this document** |

---

## 9. Risks specific to this platform

| Risk | Severity | Mitigation |
|---|---|---|
| Custom inventory is bigger than expected | High | Start it early (Phase 3, before content); consider a smaller slot count per design spec §6.3 |
| Panorama learning curve | Medium | UI is ~30% of client work; use the TypeScript template and Overthrow's example UIs |
| Source 2 entity budget (~2,048 networked) in 10-player fights with minions | Medium | Budget minion counts per encounter; measure early with the highest-add boss |
| Valve changes Workshop terms | Medium | Content pipeline is platform-neutral; a standalone port stays possible |
| Custom-game audience is declining | Medium | Accept it — this is a tribute project, not a business |
| No offline test harness | Medium | Keep formula maths in dependency-free Lua modules |
| Version skew: our data is v0.65b, community tracks v0.69x | Low | Ship v0.65b-equivalent; obtain a v0.69x map later (doc 06 §4) |

---

## 10. Immediate next steps

1. Set up Windows + Workshop Tools; ship a hello-world custom game (Phase 0).
2. Retarget the content pipeline to emit Dota KV files (Phase 1) — this is the same work
   already planned, and it is the true critical path.
3. Prototype the damage filter with the doc-05 armour formula and verify a known case:
   Duke Lazarus at 1,290 armour should take 3.73% of incoming physical damage.
4. Prototype `SwapAbilities` against Priest's `[T]` gate — it is the riskiest UI assumption,
   and cheap to test.
5. Contact the TWRPG community.
