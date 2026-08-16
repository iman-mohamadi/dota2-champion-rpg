# Content build

Turns the research dataset into Dota 2 addon content.

```bash
python3 tools/build-content/build.py        # validate, then generate
python3 tools/build-content/validate.py     # references only (CI gate)
python3 tools/build-content/test_formulas.py # formula + constants regression
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
| `build.py` | orchestrator |
| `test_formulas.py` | asserts the maths against docs/05 |

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

## Known gaps

- **Models are placeholders.** Every unit uses `models/development/invisiblebox.vmdl`,
  and every hero's `override_hero` donor is a provisional match by primary
  attribute only. Both need the Workshop Tools asset browser — a Windows session.
  Single constant in `gen_units.py`; one table in `gen_heroes.py`.
- Ability KV entries are **stubs**, all pointing at one placeholder script. The
  data entry next to each is the spec to implement it from; 324 carry the
  original handler name and 164 carry recovered coefficients.
- `core/damage.lua` is untested: there is no Lua interpreter here and Dota's API
  cannot be meaningfully stubbed. `test_formulas.py` mirrors the arithmetic in
  Python instead. Keep engine calls out of the maths so the mirror stays honest.
