# Mangled Function → Named Ability Map

The last open gap from `05-COMBAT-FORMULAS.md` §7: mapping obfuscated JASS handler
functions back to the abilities they implement.

**Result: 1,337 of 1,337 registrations resolved to a named object.** 324 of 372 hero
abilities (87%) are bound to a handler; the shortfall is version skew, not tool failure (§4).

- Machine-readable: `research/extracted/ability_map.json`
- Browsable table: `research/tables/ability_handlers.md`
- Tools: `tools/extract-w3x/map_abilities.py`, `report_abilities.py`

---

## 1. Why this is possible at all

Identifier names are destroyed by the protection and cannot be recovered. But the spell
system does not dispatch by name — it dispatches through a **hashtable registry keyed by
ability rawcode**, and rawcodes are data, not identifiers, so they survive intact.

The registry has three parts:

```jass
// registrar — binds a rawcode to a handler
function uex takes integer id, code handler returns nothing
    if not HaveSavedHandle(Yv, Vx, id) then
        call SaveTriggerHandle(Yv, Vx, id, CreateTrigger())
    endif
    call TriggerAddCondition(LoadTriggerHandle(Yv, Vx, id), Filter(handler))
endfunction

// dispatcher — looks the handler up when the event fires
function uRx takes nothing returns boolean
    return TriggerEvaluate(LoadTriggerHandle(Yv, Vx, GetSpellAbilityId()))
endfunction

// event wiring — tells us which game event key Vx corresponds to
call S_x(EVENT_PLAYER_UNIT_SPELL_EFFECT, function uRx)
```

Every call of the form `uex('A0FI', function weo)` is therefore a literal
**(rawcode → handler)** edge. Resolving rawcodes against the extracted object data
(1,944 abilities, 1,292 items, 1,286 units, all named) yields the full map.

The chain is fully mechanical — no guessing at any step:

```
registrar fn  ──SaveTriggerHandle──►  hashtable key
hashtable key ──LoadTriggerHandle──►  dispatcher fn ──S_x──► EVENT_* constant
registrar call('ID', function H)   ──►  rawcode ID → handler H
rawcode ID    ──object data──────────►  ability / item name
```

---

## 2. The ten registrars, fully resolved

Each registrar was resolved to its hashtable key, then to the game event that reads that
key, then to the native that supplies the key value:

| Registrar | Event bound | Keyed by | Registrations |
|---|---|---|---|
| `uex` | `EVENT_PLAYER_UNIT_SPELL_EFFECT` | `GetSpellAbilityId` | 784 |
| `T9x` | `EVENT_PLAYER_UNIT_SPELL_CHANNEL` | `GetSpellAbilityId` | 162 |
| `TRx` | `EVENT_PLAYER_UNIT_USE_ITEM` | `GetItemTypeId` | 149 |
| `uox` | `EVENT_PLAYER_HERO_SKILL` (on learn) | `GetLearnedSkill` | 99 |
| `uix` | *internal / custom event* | — | 83 |
| `TNx` | `EVENT_PLAYER_UNIT_PICKUP_ITEM` | `GetItemTypeId` | 31 |
| `T7x` | `EVENT_PLAYER_UNIT_SPELL_ENDCAST` | `GetSpellAbilityId` | 17 |
| `unx` | `EVENT_PLAYER_UNIT_SUMMON` | `GetUnitTypeId` | 5 |
| `T4x` | `EVENT_PLAYER_UNIT_SPELL_CAST` | `GetSpellAbilityId` | 4 |
| `TAx` | `EVENT_PLAYER_UNIT_SELL_ITEM` | `GetItemTypeId` | 3 |

`uix` (83) is the one unresolved channel: it is keyed by an internal variable rather than a
native getter, so it is a map-defined custom event. Its bindings are still captured — only
the event's meaning is unlabelled.

An ability typically has **two or three** registrations: the cast handler (`uex`), a learn
handler (`uox`) that initialises per-hero state, and often a channel handler (`T9x`).

---

## 3. What was recovered

| | Count |
|---|---|
| Literal registrations resolved | **1,337 / 1,337** |
| Resolved to a named map object | **1,337 (100%)** |
| Distinct rawcodes covered | 941 |
| Distinct handler functions identified | 1,131 |
| Hero-ability registrations | 558 |
| Item-triggered ability registrations | 183 |
| Boss-ability registrations | 42 |
| Matched to a community skill/item entry | 732 |
| Handlers with extracted stat formulas | 284 |

### Coverage against the community ability lists

| | Mapped | Total | |
|---|---|---|---|
| Hero abilities | **324** | 372 | 87% |
| Boss abilities (with valid ids) | **30** | 40 | 75% |
| Hero classes **fully** mapped | **21** | 37 | |

Non-literal registrations were checked and number only **5** in the entire script, so the
literal scan is effectively complete for this build.

---

## 4. Why 48 hero abilities are unmapped — version skew, not tool failure

This needs stating plainly rather than being presented as a coverage number.

The map file is **v0.65b**. The community dataset tracks **v0.69x** (its changelog runs to
`69e`, Dec 2024). They are different game versions.

Of the 372 community hero-ability ids:

| | Count |
|---|---|
| Present in the map's object data | 367 |
| Referenced anywhere in the script | 344 |
| Bound to a handler | 324 |

The breakdown of the 48 unmapped:

- **Sword Saint — 0 of 7 mapped.** The class does not exist in v0.65b. None of its ability
  ids appear anywhere in the script. It was added after this build.
- **28 never appear in the script at all** — abilities added in later patches.
- **5 community ids are not valid rawcodes** (e.g. `A00F2`, `A00F3` for the shared "Recall"
  skill, which is 5 characters). These are synthetic ids the community dataset uses for
  abilities shared across classes; they can never match a real rawcode.
- The remainder are **sub-menu abilities** (`[T] → [D]`, `[T] → [W]` style) handled inside
  their parent form's handler rather than registered independently — a structural property
  of the original, not a gap.

Partially-mapped classes are mostly missing 1–3 skills each. The two larger shortfalls,
Elementalist (16/29) and Paladin (6/11), are the classes whose kits were most heavily
reworked after v0.65b.

**To close this fully, extract a v0.69x map file and re-run the pipeline** — the toolchain is
version-agnostic.

---

## 5. Extracted formulas

Each handler is scanned along with the helper functions it calls (default depth 2) for
stat-scaling expressions and calls into the damage pipeline identified in doc 05
(`pFo`, `pGo`, `pHo`, `pjo`, `ppo`, …).

Real output, verbatim from the script with stat accessors substituted:

| Ability | Class | Key | Handler | Recovered formula |
|---|---|---|---|---|
| Blade Rush | Berserker | `[R]` | `weo` | `1.5*Hdo(uid(M_x)) + 15.*STR` |
| Rabid Storm | Berserker | `[F]` | `rkn` | `5.*STR`, `100.*STR` |
| Divine Light | Priest | `[R]` | `oxr` | `wU[uid]*6.*INT`, `wU[uid]*45.*INT` |
| Holy Wave | Priest | `[Q]` | `gTn` | `wU[uid]*(2.5*INT)`, `wU[uid]*5.*INT`, `wU[uid]*(25.*INT)` |
| Divine Orb | Priest | `[W]` | `odr` | `wU[uid]*5.*INT` |
| Star Shower | Witch | `[W]` | `Jzn` | `WU[uid]*1.5*INT`, `10.*INT` |

`wU[...]` / `WU[...]` are per-hero multiplier arrays — almost certainly the skill-damage
coefficient — and `Hdo(...)` returns the hero's weapon damage. Those readings are
**inference from usage, not proven**; the coefficients themselves are exact.

### Formula coverage and the precision/recall trade-off

| Traversal depth | Hero abilities with formulas |
|---|---|
| 2 (shipped default) | 178 / 558 |
| 3 | 186 / 558 |
| 4 | 211 / 558 |

Depth is tunable via `MAP_DEPTH`. **The shipped output uses depth 2 deliberately.** Deeper
traversal reaches more formulas but starts pulling in shared utility functions several hops
away, which risks attributing another ability's arithmetic to this one. Depth 2 keeps what is
reported trustworthy.

The abilities that yield nothing at any depth are mostly those that spawn a dummy unit or
start a timer, with the damage applied later in a periodic callback that is not reachable
through the static call graph. Recovering those requires per-ability tracing.

---

## 6. Verification

- **All 1,337 registrations resolve to a named object** — a rawcode that matched no ability,
  item or unit would have shown up as `kind: "unknown"`; none did.
- **Round-trip on known abilities:** Emergency Rations (`A0FM`, Sniper `[D]`) → handler `cpn`
  on `SPELL_EFFECT`; Bloodbath (`A01K`, Berserker passive) → `o2n` on learn plus `o1n` on the
  internal event. Both match the community hotkey and class.
- **Duplicate registrations are real, not double-counting.** 83 tuples appear exactly twice;
  spot-checking `A0UD → fva` finds two genuine `uex` calls at statements 163,420 and 238,930.
  Every row carries its `statement` index so any entry can be checked against the script.
- **Rendered formulas are balanced:** 252/252 formula cells have matching parentheses. (An
  earlier regex-based simplifier silently unbalanced 111 of them by swallowing delimiters; it
  was replaced with a paren-matching scan.)
- **Output is byte-reproducible** across runs with randomised hash seeds. (The first version
  was not: the call index used sets, and Python randomises string hashing per process, so
  which helpers fell inside the traversal depth limit varied run to run. Fixed by sorting.)

---

## 7. Limits

- **Handler names remain mangled.** `weo` is Blade Rush's implementation, but it is still
  called `weo`. What is recovered is the *binding*, not the original identifier.
- **`uix` (83 registrations)** is bound to a map-internal event whose meaning is unlabelled.
- **~68% of hero abilities have no extracted formula** at the shipped depth. The mapping tells
  you which function to read; it does not yet transcribe every ability.
- **The `wU[]` / `Hdo()` readings are inference.** Treat the *coefficients* as exact and the
  *variable meanings* as provisional.
- **v0.65b only.** Anything added after that build is absent by construction.

---

## 8. What this changes for the build

The tech plan budgeted "~150–200 abilities of hand work" for ability effects
(`02-TECH-PLAN.md` §4.1). That estimate now improves substantially:

1. **Every ability's implementation is locatable.** For any of the 324 mapped abilities you
   can jump straight to its handler and read the real arithmetic instead of interpreting
   English prose.
2. **178 abilities already have coefficients extracted** with no manual work.
3. **The event model is known** — which abilities need cast/channel/endcast/on-learn hooks is
   data now, not guesswork, and it directly informs the ability runtime in tech plan §3.5.
4. **The remaining work is transcription against a reference**, not reverse-engineering:
   community prose on one side, real arithmetic on the other, cross-checkable.

Recommended follow-up, in order: (a) obtain a v0.69x map and re-run to close the version
skew; (b) per-ability tracing for the timer/dummy-unit abilities the static call graph misses;
(c) resolve `uix`.
