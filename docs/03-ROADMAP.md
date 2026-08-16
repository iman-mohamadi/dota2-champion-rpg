# Roadmap (standalone variant — superseded)

> **Superseded for scheduling by [`08-DOTA2-IMPLEMENTATION-PLAN.md`](08-DOTA2-IMPLEMENTATION-PLAN.md) §5.**
> The platform decision landed on a Dota 2 custom game, which removes Phase 4 entirely and
> shortens the path to a playable multiplayer slice to ~10–14 weeks. This file is kept for the
> phase-by-phase content breakdown (Phases 5–6), which is still accurate, and as the fallback
> plan if the project ever leaves Dota 2.

# TWRPG Standalone — Roadmap

Sequenced plan to the Vertical Slice (Scope A), then the path onward.
Estimates assume 1–2 developers working steadily. No code has been written yet.

---

## Phase 0 — Decide and extract (1–2 weeks)

Nothing downstream is safe until these are settled.

| # | Task | Output |
|---|---|---|
| 0.1 | Answer the six open questions in design spec §12 | Decisions recorded in `docs/` |
| 0.2 | **Decide platform: Dota 2 custom game vs standalone** — see [`07-PLATFORM-DECISION.md`](07-PLATFORM-DECISION.md). Hinges on whether a Windows machine with a D3D11 GPU is available | Platform chosen; then scaffold per tech plan §10 |
| 0.3 | ~~Download and extract the `.w3x`~~ | **DONE** — terrain, 1,286 units, 1,292 items, 1,944 abilities, 638 spawn coords. See doc 04. |
| 0.4 | ~~Assess extraction result~~ | **DONE** — base hero stats and the attack formula recovered; script is obfuscated so the EXP curve and armor curve must still be fitted. |
| 0.4b | ~~Mine or fit the EXP and armour curves~~ | **DONE** — both recovered exactly from `war3mapMisc.txt` and confirmed in-script. See doc 05. `research/extracted/curves.json` |
| 0.5 | Contact the TWRPG community (Discord / Naver cafe) about a tribute port | Permission status known, possibly collaborators |

~~**0.3 is the highest-leverage task in the project.**~~ **Completed.** Zone geometry is now
real, not invented (doc 04 §3, §5). Two curves — EXP and armor mitigation — remain the only
significant invented numbers, and both are tunable data tables rather than blockers.

---

## Phase 1 — Content pipeline (3–4 weeks)

Build the machine that turns the dataset into game data. Before any gameplay.

| # | Task | Output |
|---|---|---|
| 1.1 | JSON schemas for item, ability, monster, encounter, recipe, zone | `content/schema/` |
| 1.2 | Importer: `research/raw` → `content/staging`, resolving id→name refs | 765 items, 147 monsters staged |
| 1.3 | **Reference validator** — fail on any dangling item/boss/ability/recipe reference | CI gate |
| 1.4 | **Ability transcription**, using the handler map (doc 06) as ground truth alongside community prose | 324 hero abilities located; 178 coefficients already extracted |
| 1.5 | Manual review queue + editor for the remainder | Review workflow |
| 1.6 | Boss `conditions` parser → Codex objectives | Hunt track data |
| 1.7 | Name-mapping layer (legal §9) | Rename switch available |
| 1.8 | Content build + pack step | `build/content.pak` |

**Exit criterion:** the full 765-item / 147-monster / 486-recipe set builds clean, with a
report listing every ability that still needs manual attention.

---

## Phase 2 — Simulation core (6–8 weeks)

Headless. No renderer. Tests only.

| # | Task |
|---|---|
| 2.1 | ECS skeleton, fixed timestep, seeded PRNG |
| 2.2 | `Stats` struct over the full 36-stat vocabulary; base/derived layers with dirty flags |
| 2.3 | **Damage pipeline** — implement per doc 05 §5: damage instances, 3 channels, `1/(1+0.02·armor)` mitigation, multiplicative penetration before mitigation, crit after |
| 2.4 | **Damage-trace inspector** (build this now, not later) |
| 2.5 | **Status effect system with categorical slot stacking** |
| 2.6 | Ability runtime: cast/channel/cooldown/toggle/stacks/sub-menu swap/spec overrides |
| 2.7 | Event bus + proc system with internal cooldowns and depth limiting |
| 2.8 | Basic AI: aggro, threat, leash, pathing-free movement |
| 2.9 | Loot roll, drop tables, **Wish system**, loot chest with participant gating |
| 2.10 | Inventory, storage, overflow chain, stacking cap |
| 2.11 | Crafting resolver over the recipe graph |
| 2.12 | XP/level/stat-point allocation — use the exact curve `Need(L) = 1650·1.05^(L-1) − 1500` |
| 2.13 | Test suite: damage cases from item text, stacking rules from `debuffs.json`, drop-rate simulation |

**Exit criterion:** a headless test spawns a Berserker, kills 10,000 Spiders and one Troll
Lord, and drop rates land within tolerance of the source data — with zero rendering code
in the repo.

---

## Phase 3 — Playable slice (6–8 weeks)

| # | Task |
|---|---|
| 3.1 | Godot client shell; camera; click-to-move; attack |
| 3.2 | Ability bar incl. **sub-menu swap** (validate against Priest's `T` gate) |
| 3.3 | **Three heroes**: Berserker (STR), Sniper (AGI), Priest (INT) — full skill sets |
| 3.4 | **Two zones**: Starter Village (L3–8), Wild Life Habitat (L10–45) |
| 3.5 | **Three bosses**: Silverback Wolf (creep, summons), Troll Lord (creep), Protector of Nature (field, L30) |
| 3.6 | Encounter runtime driving those three from declarative timelines |
| 3.7 | UI: inventory, equipment, stat allocation, recipe browser, vendor |
| 3.8 | ~60 items covering the L1–45 band with working recipes |
| 3.9 | Codex v1: Hunt + Forge tracks |
| 3.10 | Placeholder art and audio |
| 3.11 | Save/load against local persistence |

**Exit criterion:** a player creates a Berserker, levels 1→30, farms materials, crafts a
Deltirama-grade item from a multi-step recipe, and kills Protector of Nature. The loop is
demonstrably fun — or it isn't, and we learn that here rather than in year two.

**This is the decision point.** Assess before committing to Phase 4+.

---

## Phase 4 — Multiplayer foundation (6–8 weeks)

> **Skipped entirely if the Dota 2 route is chosen** — the engine is already authoritative
> multiplayer with free Valve-hosted servers, matchmaking and Steam identity. This phase is
> the single largest effort difference between the two platforms.

Do this *before* mass content, not after. Retrofitting authority is the classic failure mode.

| # | Task |
|---|---|
| 4.1 | Split client/server; move simulation server-side |
| 4.2 | Netcode: intent up, state deltas down; client prediction + reconciliation |
| 4.3 | Party system; boss-zone participant tracking |
| 4.4 | Instanced encounters with server-owned RNG |
| 4.5 | Shared loot chest with per-player claim/pass |
| 4.6 | PostgreSQL persistence; account system; item instance ids |
| 4.7 | Trading with per-item limits, soulbound flags, audit log |
| 4.8 | Party-size scaling on encounters |

**Exit criterion:** four players clear a Minor boss together with correct loot distribution.

---

## Phase 5 — Content scale-out (ongoing, 12+ months for Scope B)

Now that the pipeline, the core and multiplayer exist, content is throughput work.

| Wave | Content |
|---|---|
| 5.1 | Heroes 4–10; classes chosen to cover the distinct role archetypes (shield-breaker, summoner, DoT, buffer, tank-support) |
| 5.2 | Zones 3–8: Seaside, Frosty Snowfield, Capital Prius hub, Duchy of Wallachia, Volcanic Lands, Deep Sea |
| 5.3 | Field + Minor bosses (22 encounters) |
| 5.4 | Grades 1–2 item tiers (Deltirama, Neptinos) — ~217 items |
| 5.5 | Currency and vendor economy; Prius coin exchange; Boss Fairy |
| 5.6 | Mining, pickaxes, magic stones, powder ladder → boss summoning |
| 5.7 | Teleporter network and portal unlocks |
| 5.8 | Hard Mode and **Practice Mode** |
| 5.9 | Mid + High tier bosses (10 encounters, including Ancient Ent at 75M HP) |
| 5.10 | Grade 3 (Gnosis) items |

**Scope B ships here** — 10 heroes, 8 zones, ~20 bosses, level 100, 4-player co-op.

---

## Phase 6 — Endgame (Scope C)

| # | Content |
|---|---|
| 6.1 | Late + Endgame bosses: Death Fiend, Ifrit, Valtora, Nereid, Agareth, Duke Lazarus, Gaia, Styrix, Arcane Construct |
| 6.2 | Mini-game phases (Agareth's soul crystal chamber) |
| 6.3 | **Hell Invasion world event** and the Demon Lord → portal → Agareth chain |
| 6.4 | Grades 4–5 (Alteia, Arcana) — 200 items |
| 6.5 | Specialty item system across all classes |
| 6.6 | Remaining 27 heroes |
| 6.7 | Codex Chronicle track |
| 6.8 | Seasonal events |
| 6.9 | 10-player scaling and tuning |

---

## Critical path

```
Phase 0.3 (extract .w3x)
    └─► Phase 1 (content pipeline)
            └─► 1.4 ability transcription  ◄── content cost, reduced by the doc-06 handler map
                    └─► Phase 2 (sim core)
                            └─► 2.3 damage pipeline + 2.5 stacking  ◄── correctness gate
                                    └─► Phase 3 (slice)  ◄── FUN GATE, go/no-go
                                            └─► Phase 4 (multiplayer)
                                                    └─► Phase 5+ (content throughput)
```

---

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| ~~`.w3x` script is protected~~ | **Materialised, and mitigated.** Script *is* obfuscated, but terrain + object data + 638 spawn coords survived. Only the EXP and armor curves must be fitted. |
| Ability transcription effort | Medium — item stats are structured, and every ability handler is now located with 178 coefficients auto-extracted (doc 06) | Work against the handler map, not the prose; obtain a v0.69x map to close version skew |
| Scope collapse under 37 heroes / 39 bosses | Project-ending | Ship Scope A first; treat B and C as separately-funded decisions |
| Damage model doesn't reproduce source numbers | High — all content mis-tuned | Damage-trace inspector from day one; unit tests against item text |
| Art cost dominates | High for a small team | Consider a stylised direction (low-poly / pixel) that cuts asset cost by an order of magnitude |
| Legal challenge over names/flavour text | Medium | Rename layer built into the pipeline; seek community permission in Phase 0 |
| Multiplayer retrofit | High | Server-authoritative core from Phase 2, even while single-player |
| The grind isn't fun without WC3 nostalgia | Existential | Phase 3 is an explicit go/no-go gate; be willing to re-tune drop rates |

---

## Immediate next actions

1. Read `00-RESEARCH-FINDINGS.md`, then answer the six questions in design spec §12.
2. Skim the generated tables — `research/tables/heroes.md`, `bosses.md`, `crafting.md` — to
   feel the actual scale before committing to a tier.
3. Kick off Phase 0.3: download the map and attempt extraction.
4. Reach out to the TWRPG community.

Nothing in Phase 1+ should start before 0.1 and 0.3 have answers.
