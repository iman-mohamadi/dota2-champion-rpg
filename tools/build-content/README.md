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

## Known gaps

- **Models are placeholders.** Every unit uses `models/development/invisiblebox.vmdl`
  until real Dota models are assigned — that needs the Workshop Tools asset
  browser, i.e. a Windows session. Single constant in `gen_units.py`.
- Items, heroes and abilities are not generated yet.
- `core/damage.lua` is untested: there is no Lua interpreter here and Dota's API
  cannot be meaningfully stubbed. `test_formulas.py` mirrors the arithmetic in
  Python instead. Keep engine calls out of the maths so the mirror stays honest.
