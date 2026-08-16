# Combat Formulas, EXP Curve and Damage Pipeline — Recovered

Everything here is recovered from the map file: the gameplay-constants file
(`war3mapMisc.txt`, plain text, untouched by protection) and the protected JASS script
(`war3map.j`, partially deobfuscated).

This closes the last significant gaps from `00-RESEARCH-FINDINGS.md` §5.

Machine-readable output: `research/extracted/curves.json` — every constant quoted below is in
there. The raw `war3mapMisc.txt` is **not** vendored (it is a verbatim file from the
copyrighted map); re-extract it with `tools/extract-w3x/extract.py` if you need the original.

---

## 1. The shortcut that mattered

The EXP curve and armour coefficient were never in the script. Warcraft III keeps them in
**`war3mapMisc.txt`** — the World Editor "gameplay constants" file — which is plain INI text
that map protection does not touch. I had missed it on the first extraction pass; probing for
it returned 61,392 bytes immediately.

The script deobfuscation (§4–5) then *independently confirmed* those constants, so both
sources agree.

---

## 2. EXP curve — **exact**

```
MaxHeroLevel        = 100
MaxUnitLevel        = 1000
NeedHeroXP          = 150
NeedHeroXPFormulaA  = 1.05
NeedHeroXPFormulaB  = 75.0
```

Warcraft III's recurrence for XP required to advance from level `L` to `L+1`:

```
Need(1) = NeedHeroXP
Need(L) = A × Need(L-1) + B
```

So for TWRPG:

```
Need(1) = 150
Need(L) = 1.05 × Need(L-1) + 75
```

Closed form: **`Need(L) = 1650 × 1.05^(L-1) − 1500`**

| Level | XP for that level | Cumulative |
|---|---|---|
| 1 → 2 | 150 | 150 |
| 2 → 3 | 232 | 382 |
| 5 → 6 | 506 | 1,617 |
| 10 → 11 | 1,060 | 5,754 |
| 20 → 21 | 2,670 | 24,559 |
| 30 → 31 | 5,292 | 64,624 |
| 40 → 41 | 9,563 | 139,320 |
| 50 → 51 | 16,520 | 270,424 |
| 60 → 61 | 27,853 | 493,413 |
| 70 → 71 | 46,313 | 866,072 |
| 80 → 81 | 76,382 | 1,482,528 |
| 90 → 91 | 125,362 | 2,496,102 |
| 99 → 100 | 195,305 | **3,951,397** |

Full 99-row table in `curves.json`.

### Independent verification

Retail Warcraft III defaults are `NeedHeroXP = 200`, `NeedHeroXPFormulaB = 100`.

```
150 / 200 = 0.75
 75 / 100 = 0.75
```

Changelog patch `59p` reads: **"Reduced EXP required to level up by 25%."** Both constants
sit at exactly 75% of retail. The patch is literally visible in the file, and it confirms the
recurrence interpretation is correct.

(`A = 1.05` is TWRPG's own value — retail uses 1.0, which produces the familiar flat
200/300/400/500 progression. The 1.05 is what makes the curve exponential.)

### XP granted for a kill

```
GrantNormalXPFormulaA = 0.85     GrantNormalXPFormulaB = 2.0     GrantNormalXPFormulaC = 2.0
GrantHeroXP           = 0        HeroFactorXP = 0      GlobalExperience = 0
```

`XP = 0.85·L² + 2·L + 2` for a unit of level `L`:

| Unit level | XP |
|---|---|
| 3 (Spider) | 16 |
| 20 (Troll Lord) | 382 |
| 45 | 1,813 |
| 70 | 4,307 |
| 100 | 8,702 |
| 130 (Duke Lazarus) | 14,627 |

`GrantHeroXP = 0` → killing heroes grants no XP. `GlobalExperience = 0` → no shared/global XP
pool; XP is per-killer by proximity.

> **Confidence note.** The `Need` recurrence is verified against retail behaviour and the
> changelog. The *grant* formula shape (`A·L² + B·L + C`) is the standard reading of these
> three constants but I could not verify it against an independent observation, so treat the
> kill-XP numbers as high-confidence-but-unverified. The changelog's cap — "raid boss EXP
> earnable from level 50, capped to 1 level-up per kill" [`58h`] — is a script rule layered
> on top of this.

---

## 3. Attribute bonuses — **all disabled**

```
StrHitPointBonus    = 0.0     [retail 25]
StrRegenBonus       = 0.0     [retail 0.05]
AgiDefenseBonus     = 0.0     [retail 0.3]
AgiDefenseBase      = 0.0
AgiAttackSpeedBonus = 0.0     [retail 0.02]
AgiMoveBonus        = 0.0
IntManaBonus        = 0.0     [retail 15]
IntRegenBonus       = 0.0     [retail 0.05]
```

**Every stock Warcraft III attribute effect is switched off.** STR grants no HP, AGI grants
no armour or attack speed, INT grants no mana. Combined with the earlier finding that all
heroes have `0.0` per-level growth and a flat 500 HP base, this means:

> Character power in TWRPG comes **entirely** from equipment and from script-side formulas
> that read STR/AGI/INT. The engine's own RPG layer is completely bypassed.

`StrAttackBonus = 3.0` is the one attribute constant left active — attack damage per point of
the hero's primary attribute (retail default 1.0). *Moderate confidence on the exact
semantics of this key.*

---

## 4. Armour and mitigation — **exact, dual-confirmed**

`war3mapMisc.txt` gives `DefenseArmor = 0.02` (retail default 0.06).

The script contains the forward formula verbatim:

```jass
function eMo takes real damage, real armor returns real
    if armor >= 0 then
        return damage * (1. - ((armor * .02) / (1. + .02 * armor)))
    else
        return damage * (2. - Pow(.94, -armor))
    endif
endfunction
```

and its exact inverse:

```jass
function eqo takes real damage, real armor returns real
    if armor >= 0 then
        return damage / (1. - ((armor * .02) / (1. + .02 * armor)))
    else
        return damage / (2. - Pow(.94, -armor))
    endif
endfunction
```

So:

```
armor ≥ 0 :  damageMultiplier = 1 − (0.02·armor)/(1 + 0.02·armor)  =  1/(1 + 0.02·armor)
armor < 0 :  damageMultiplier = 2 − 0.94^(−armor)
```

Verified: `eqo(eMo(1000, 1240), 1240) = 1000.000000` — exact round trip.

| Armour | Reduction | Effective HP × |
|---|---|---|
| 0 | 0.00% | 1.0 |
| 100 | 66.67% | 3.0 |
| 300 | 85.71% | 7.0 |
| 730 (Beriel) | 93.59% | 15.6 |
| 1,120 (Ancient Ent) | 95.73% | 23.4 |
| 1,240 (Agareth) | 96.12% | 25.8 |
| 1,290 (Duke Lazarus) | 96.27% | 26.8 |
| 2,000 | 97.56% | 41.0 |

The coefficient drop from 0.06 → 0.02 is what allows armour values in the hundreds-to-
thousands to stay meaningful instead of saturating. This is the single most important
balance constant in the game.

---

## 5. The damage pipeline — recovered architecture

### 5.1 Armour is *measured*, not read

TWRPG does not track armour in a variable. It **probes the engine**:

```jass
function eJo takes unit target, attacktype at, damagetype dt returns real
    local real saved = GetWidgetLife(target)
    local real probe
    call SetWidgetLife(target, 500)
    call UnitAddAbility(target, 'A090')
    set probe = GetWidgetLife(target)
    set S5 = false                                    // suppress the damage handler
    call UnitDamageTarget(wo, target, 'd', ...)       // 'd' = 100 damage
    set S5 = true
    set probe = probe - GetWidgetLife(target)
    call UnitRemoveAbility(target, 'A090')
    call SetWidgetLife(target, saved)
    return probe / 'd'                                // fraction of damage that got through
endfunction
```

It saves HP, deals exactly 100 damage with the handler suppressed, measures the loss, and
restores. `eLo` then inverts that multiplier back into an armour value:

```jass
function eLo takes unit target returns real
    local real m = eJo(target, ATTACK_TYPE_CHAOS, DAMAGE_TYPE_NORMAL)
    if m == 0 then
        return .0
    elseif m <= 1 then
        return (1 - m) / (.02 * m)              // ← inverse of the armour formula, k = 0.02
    endif
    return -(Ln(2 - m) / -.061875)              // ← negative-armour branch; ln(0.94) = -0.061875
endfunction
```

Both magic constants confirm §4 independently: `.02` is `DefenseArmor`, and `−0.061875` is
`ln(0.94)` to six decimals. Chaos attack type is used so the (neutralised) attack-vs-armour
table cannot interfere.

**Why they do it this way:** it captures *every* source of armour — base, items, buffs,
debuffs, auras — without the script having to track any of them.

### 5.2 Damage instances

Damage is a heap-allocated struct, not a number. `pIo(source, target, amount)` allocates one
with: source, target, base amount, current amount, crit multiplier, three multiplier slots,
~10 boolean type flags, and label strings. `pdo(instance)` then runs the modifier pipeline
and `pfo` applies the result.

This is the same "damage channel" architecture the design spec hypothesised — confirmed as
the original's actual design.

### 5.3 Three damage channels

From the public entry point `pFo(...)`:

| Passed damage type | Internal channel |
|---|---|
| `DAMAGE_TYPE_NORMAL` | **1 — physical** |
| anything else | **2 — magic** |
| `DAMAGE_TYPE_UNIVERSAL` | **3 — pure** |

And in `pdo`:

```jass
if B5 == 1 then                                        // physical → armour applies
    set damage = eMo( base, (1. - G0o(source)) * eLo(target) )
elseif b5 then                                         // magic / pure → armour skipped
    set damage = base
endif
if G5 then                                             // crit flag
    set damage = D5 * damage                           // crit multiplier, applied LAST
endif
```

This confirms, from code, the community `tags.json` distinction between **Physical / Magic /
Pure** damage: only physical is mitigated by armour, and pure bypasses everything.

### 5.4 Armour penetration and crit

- `G0o(source)` returns a fraction in `[0,1]`. Effective armour is
  **`(1 − penetration) × armour`** — penetration is multiplicative on armour, *not* flat
  subtraction, and it is applied before mitigation.
- `gto(source)` returns `1 + critBonus`; crit is applied **after** mitigation, so armour does
  not reduce the crit portion disproportionately.

### 5.5 Order of operations

```
1. engine deals damage, applying its own armour reduction
2. pro()  → eqo(eventDamage, armour)     un-apply armour, recover the raw base
3. modifier pipeline stacks % multipliers on the raw base
4. eMo(base, (1 − penetration) × armour) re-apply armour
5. × crit multiplier
6. shields, death guards, then HP
```

Step 2 is the clever part: because the engine has already mitigated by the time the damage
event fires, TWRPG *reverses* the mitigation to recover the true base, applies its own
multipliers, then re-applies mitigation with penetration accounted for.

### 5.6 Ability coefficients

Ability damage is exactly the `stat × coefficient` shape the community descriptions use.
Real examples pulled from the script:

```
2.25 × (STR + AGI + INT)              magic damage
0.45 × (STR + AGI + INT)              magic damage
3.0  × (STR + AGI)
8.0  × (STR + AGI)
3.75 × STR + 7.5 × INT
0.75 × <weapon damage> + 10 × (STR + INT/3)
1.3  × <weapon damage> + 8 × (STR + AGI)
```

57 statements combine hero stats with arithmetic in this way. These are the per-ability
numbers the community's prose descriptions paraphrase.

---

## 6. What the engine's own systems do *not* do

Worth stating explicitly, because each is a trap for a reimplementation:

| Stock WC3 system | Status in TWRPG |
|---|---|
| Attack-type vs armour-type triangle | **Disabled** — all six `DamageBonus*` rows are `1.00,1.00,1.00,1.00,1.00,1.00,1.00,1.00` |
| Armour-type damage modifiers (Light/Medium/Heavy) | **No damage effect.** `armorType` is cosmetic / used for other logic only |
| Attribute → HP/mana/armour/attack-speed | **All zeroed** |
| Per-level attribute growth | **All 0.0** |
| Miss chance | `ChanceToMiss = 0.0` — no random misses |
| Hero XP from kills | `GrantHeroXP = 0` |

Other constants worth carrying over: `MaxUnitSpeed = 500` (this is why every hero and most
bosses sit at exactly 500 move speed — it is the engine cap, not a design choice),
`MinUnitSpeed = 1`, `PickupItemRange = 300`, `FrostAttackSpeedDecrease = 0.2`,
`FrostMoveSpeedDecrease = 0.4`, `DayLength = 1800`.

---

## 7. Deobfuscation method and its limits

`tools/extract-w3x/deobfuscate.py`.

The protection does three things:
1. renames every identifier to short meaningless tokens (`V`, `E`, `vv`, `ov`, `pdo`…)
2. strips indentation and mixes `\r` and `\n` as statement separators, so line-based tools
   see a few enormous lines
3. leaves **string literals, native calls and control flow fully intact**

(3) is what makes this tractable. Normalising the separators turned 48,604 apparent lines
into **245,785 real statements** and exposed **16,746 functions** and **12,424 unique
strings** — including the item grade names (`"Epic - Deltirama"`, `"Epic - Neptinos"`) sitting
in plain text.

Commands:
```bash
python3 tools/extract-w3x/deobfuscate.py format  war3map.j out.j
python3 tools/extract-w3x/deobfuscate.py index   war3map.j functions.json
python3 tools/extract-w3x/deobfuscate.py strings war3map.j strings.json
python3 tools/extract-w3x/deobfuscate.py grep    war3map.j 'PATTERN' [context]
python3 tools/extract-w3x/derive_curves.py war3mapMisc.txt curves.json
```

### What this is not

This is **partial** deobfuscation. Identifier names are gone and cannot be recovered — they
were destroyed, not encoded. What is recovered is *structure and arithmetic*: function
boundaries, call graph, control flow, string literals and every numeric constant. That is
sufficient to read specific systems, as demonstrated, but it is not a readable source tree.

**Still not recovered:**
- The full modifier pipeline. Multipliers are applied through a dynamic
  registration system (`YRx` registers, `YVx`/`YOx` dispatch), so the complete set of
  stacking rules cannot be resolved statically — you would have to trace each registered
  handler individually. The community `buffs.json`/`debuffs.json` Type-A/B/C/D tables remain
  the better source for stacking behaviour.
- Per-ability numbers for all 652 abilities. The *shape* is confirmed and the coefficients
  are present in the script, but mapping each mangled function back to a named ability is
  manual work.
- Magic resist / damage resist application point. Present as unit fields; where they enter
  the pipeline was not pinned down.

---

## 8. Consequences for the build

1. **The armour constant `0.02` is the most important number in the game.** Boss armour of
   730–1,290 means 93.6%–96.3% physical mitigation. Get this wrong and every encounter is
   mis-tuned by an order of magnitude.
2. **Do not model armour types as damage modifiers.** They are inert. A reimplementation that
   "helpfully" restores the WC3 triangle will silently rebalance all 39 bosses.
3. **Implement damage as instances, not numbers.** The original does; the modifier system
   depends on it. This validates design spec §5.1 and tech plan §3.3.
4. **Penetration is multiplicative on armour**, applied before mitigation. Crit is applied
   after. Order matters and is now known.
5. **Do not implement engine attribute bonuses.** STR/AGI/INT feed script formulas only.
6. **The EXP curve is exact — use it.** `Need(L) = 1650 × 1.05^(L-1) − 1500`, 3,951,397 total
   to level 100. No fitting required.
7. Armour probing is a WC3 workaround. In our engine armour is a tracked stat, so implement
   the formula directly and drop the probe.
