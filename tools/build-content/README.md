# Content build

Turns the research dataset into Dota 2 addon content.

```bash
python3 tools/build-content/build.py         # validate, then generate
python3 tools/build-content/validate.py      # references only (CI gate)
python3 tools/build-content/test_formulas.py # formula + constants regression
python3 tools/build-content/test_systems.py  # systems-layer rules
```

## Layout

| File | Role |
|---|---|
| `common.py` | loading, name slugging, KV/Lua emitters |
| `validate.py` | reference integrity — fails the build on dangling links |
| `gen_constants.py` | `data/constants.lua` from the recovered curves |
| `gen_units.py` | `npc_units_custom.txt` + `data/units.lua` for 147 monsters |
| `gen_items.py` | `npc_items_custom.txt` (576 equippable) + `data/items.lua` (765) + `data/recipes.lua` (486) |
| `gen_abilities.py` | `npc_abilities_custom.txt` + `data/abilities.lua` for 372 hero skills |
| `gen_heroes.py` | `npc_heroes_custom.txt`, `herolist.txt`, `data/heroes.lua` for 37 classes |
| `gen_stacking.py` | `data/stacking.lua` — the Type-A/B/C/D slot table |
| `gen_stats.py` | `data/stats.lua` — the 34-field stat vocabulary |
| `gen_encounters.py` | `data/encounters.lua` — 52 boss scaffolds |
| `gen_codex.py` | `data/codex.lua` — Hunt objectives parsed from boss conditions, plus Chronicle chains |
| `build.py` | orchestrator |
| `test_formulas.py` | asserts the maths against docs/05 |
| `test_systems.py` | asserts the systems-layer rules (stacking, inventory, crafting, loot) |

## Rules

- `research/` is **read-only**. Generators never write to it.
- Generated files carry a DO-NOT-EDIT header. Change the source or the generator.
- The build **refuses to emit** if validation fails.
- Dota's `ArmorPhysical` is pinned to 0 on every unit; TWRPG armour lives in
  `data/units.lua` and is applied by `core/damage.lua` using the recovered
  `1/(1 + 0.02*armor)` formula. Writing it into `ArmorPhysical` would stack
  Dota's own curve on top and mis-tune every encounter.

## Design notes

- **Ability keys are class+name**, not name: `Recall` exists on four classes and
  `Purify` on two. class+name is collision-free across all 372.
- **Items split two ways.** The 576 equippable items become real Dota items in
  the native slots (the "equipped" bar); the 189 materials/tokens/icons/coins
  exist only as data in `items.lua`, for the custom 24-slot inventory.
- **Sub-menu abilities** (98 of them, `[T] → [W]` style) are emitted HIDDEN and
  are not assigned KV ability slots. They get swapped in at runtime via
  `SwapAbilities`. No class exceeds Dota's 16 usable slots at the top level.
- **Stat sign conventions are recorded, not assumed.** `drpercent` (Damage
  Reduction) is better high; `dtpercent` (Damage Taken) is better *low* — Stone
  Plates is −0.05, Mask of Blood is +0.06 as a drawback. `higherIsBetter` is a
  per-field flag in `stats.lua`.

## Known gaps

- **Models are placeholders.** Every unit uses `models/development/invisiblebox.vmdl`,
  and every hero's `override_hero` donor is a provisional match by primary
  attribute only. Both need the Workshop Tools asset browser — a Windows session.
  Single constant in `gen_units.py`; one table in `gen_heroes.py`.
- **How item percentages combine is an assumption.** `core/stats.lua` sums them
  additively (two 5% skill-damage items give 10%). The source data does not say
  either way. It is decided in exactly one function, `Stats:SumFraction`, so it
  is a one-line change if in-game testing says otherwise.
- **Persistence needs a JSON codec injected** (`Persistence.json`) and an
  endpoint set. Saving is refused outright rather than silently sending nil.
- **Encounter definitions are scaffolds, not fights.** Phase HP thresholds,
  ability timings and mechanic specifics are not in the source data and are not
  invented. Every definition carries `authored = false`; 6 are flagged as
  needing a scripted hook (Agareth's mini-game, Lazarus's second form, Styrix's
  out-of-zone leash heal, Ancient Ent, Death Fiend's Fog, Beriel's wave gate).
- **Codex Hunt parsing is 90% structured** (47 of 52). The remaining 5 are
  genuine world-state prose and one upstream naming inconsistency
  ("Orb of the Sea" vs the real item "Orb of the Deep Sea"). They are kept
  verbatim as `freeform` rather than guess-matched.
- Ability KV entries are **stubs**, all pointing at one placeholder script. The
  data entry next to each is the spec to implement it from; 324 carry the
  original handler name and 164 carry recovered coefficients.
- `core/damage.lua` is untested: there is no Lua interpreter here and Dota's API
  cannot be meaningfully stubbed. `test_formulas.py` mirrors the arithmetic in
  Python instead. Keep engine calls out of the maths so the mirror stays honest.
