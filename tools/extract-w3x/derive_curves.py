#!/usr/bin/env python3
"""Derive the EXP curve and armour mitigation curve from war3mapMisc.txt.

war3mapMisc.txt is Warcraft III's "gameplay constants" file. It is plain INI
text and is NOT touched by script obfuscation, so the hero XP curve, armour
coefficient and attack-type/armour-type damage table can be read directly.

Usage: python3 derive_curves.py <war3mapMisc.txt> <out.json>
"""
import json
import sys


def read_misc(path):
    out = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("["):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def num(m, key, default=0.0):
    try:
        return float(m[key])
    except (KeyError, ValueError):
        return default


def xp_curve(m, max_level):
    """WC3 recurrence: Need(1) = NeedHeroXP; Need(L) = A*Need(L-1) + B.

    Verified against retail defaults (NeedHeroXP=200, A=1.0, B=100), which
    reproduce the documented 200/300/400/500... progression exactly.
    """
    base = num(m, "NeedHeroXP", 200)
    a = num(m, "NeedHeroXPFormulaA", 1.0)
    b = num(m, "NeedHeroXPFormulaB", 100.0)
    need, cum, rows = base, 0.0, []
    for lvl in range(1, max_level):
        cum += need
        rows.append({"fromLevel": lvl, "toLevel": lvl + 1,
                     "xpForLevel": round(need, 1), "cumulativeXp": round(cum, 1)})
        need = a * need + b
    return rows, {"base": base, "A": a, "B": b,
                  "closedForm": "Need(L) = (base + B/(A-1)) * A^(L-1) - B/(A-1)" if a != 1
                  else "Need(L) = base + B*(L-1)"}


def creep_xp(m, levels):
    """XP granted for killing a normal (non-hero) unit of level L."""
    a = num(m, "GrantNormalXPFormulaA", 1.0)
    b = num(m, "GrantNormalXPFormulaB", 0.0)
    c = num(m, "GrantNormalXPFormulaC", 0.0)
    return [{"unitLevel": L, "xpGranted": round(a * L * L + b * L + c, 1)} for L in levels]


def armour_curve(m, armours):
    """WC3 armour mitigation: reduction = (k*armour) / (1 + k*armour), k = DefenseArmor."""
    k = num(m, "DefenseArmor", 0.06)
    rows = []
    for ar in armours:
        red = (k * ar) / (1 + k * ar) if ar >= 0 else 2 - 0.94 ** (-ar)
        rows.append({"armor": ar, "reductionPct": round(red * 100, 3),
                     "damageMultiplier": round(1 - red, 6),
                     "effectiveHpMultiplier": round(1 / (1 - red), 2) if red < 1 else None})
    return rows, k


def main():
    misc, out_path = sys.argv[1], sys.argv[2]
    m = read_misc(misc)
    max_level = int(num(m, "MaxHeroLevel", 10))

    rows, meta = xp_curve(m, max_level)
    armours = [0, 50, 100, 200, 300, 500, 730, 750, 800, 850, 900,
               1120, 1240, 1290, 1500, 2000]
    arows, k = armour_curve(m, armours)

    disabled = {key: m.get(key) for key in
                ["StrHitPointBonus", "StrRegenBonus", "AgiDefenseBonus",
                 "AgiDefenseBase", "AgiAttackSpeedBonus", "AgiMoveBonus",
                 "IntManaBonus", "IntRegenBonus"]}
    dmg_table = {key: m[key] for key in m if key.startswith("DamageBonus")}

    result = {
        "source": "war3mapMisc.txt (gameplay constants, not obfuscated)",
        "maxHeroLevel": max_level,
        "maxUnitLevel": int(num(m, "MaxUnitLevel", 10)),
        "xpCurve": {"formula": meta, "table": rows,
                    "totalXpToMax": rows[-1]["cumulativeXp"] if rows else 0},
        "creepXpGranted": {
            "formula": "XP = %s*L^2 + %s*L + %s" % (
                m.get("GrantNormalXPFormulaA"), m.get("GrantNormalXPFormulaB"),
                m.get("GrantNormalXPFormulaC")),
            "samples": creep_xp(m, [3, 5, 10, 20, 30, 45, 60, 70, 80, 90, 100, 110, 120, 130]),
        },
        "heroXpGranted": {
            "GrantHeroXP": m.get("GrantHeroXP"),
            "note": "0 = killing heroes grants no XP",
        },
        "armor": {"DefenseArmor": k,
                  "formula": "reduction = (k*armor)/(1 + k*armor)",
                  "retailDefault": 0.06, "table": arows},
        "attributeBonusesDisabled": disabled,
        "primaryAttributeAttackBonus": m.get("StrAttackBonus"),
        "damageBonusTable": dmg_table,
        "misc": {key: m.get(key) for key in
                 ["ChanceToMiss", "MissDamageReduction", "MaxUnitSpeed",
                  "MinUnitSpeed", "FrostAttackSpeedDecrease",
                  "FrostMoveSpeedDecrease", "PickupItemRange", "GlobalExperience"]},
    }
    json.dump(result, open(out_path, "w"), indent=1)

    print("MaxHeroLevel = %d\n" % max_level)
    print("EXP CURVE   Need(L) = %s*Need(L-1) + %s,  Need(1) = %s"
          % (meta["A"], meta["B"], meta["base"]))
    print("  %-8s %-14s %s" % ("level", "xp for level", "cumulative"))
    for r in rows:
        if r["fromLevel"] in (1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 99):
            print("  %2d->%-4d %-14s %s" % (r["fromLevel"], r["toLevel"],
                                            f'{r["xpForLevel"]:,.0f}', f'{r["cumulativeXp"]:,.0f}'))
    print("  TOTAL XP 1 -> %d: %s\n" % (max_level, f'{rows[-1]["cumulativeXp"]:,.0f}'))

    print("CREEP XP    %s" % result["creepXpGranted"]["formula"])
    for s in result["creepXpGranted"]["samples"]:
        if s["unitLevel"] in (3, 20, 45, 70, 100, 130):
            print("  level %-4d grants %s xp" % (s["unitLevel"], f'{s["xpGranted"]:,.0f}'))

    print("\nARMOUR      reduction = (%.2f*armor)/(1 + %.2f*armor)   [retail default 0.06]" % (k, k))
    print("  %-8s %-12s %s" % ("armor", "reduction", "effective HP x"))
    for r in arows:
        if r["armor"] in (0, 100, 300, 730, 1120, 1240, 1290, 2000):
            print("  %-8d %-12s %s" % (r["armor"], "%.2f%%" % r["reductionPct"],
                                       r["effectiveHpMultiplier"]))

    print("\nATTRIBUTE BONUSES (retail defaults in brackets):")
    defaults = {"StrHitPointBonus": 25, "StrRegenBonus": 0.05, "AgiDefenseBonus": 0.3,
                "AgiAttackSpeedBonus": 0.02, "IntManaBonus": 15, "IntRegenBonus": 0.05}
    for key, val in disabled.items():
        d = defaults.get(key)
        print("  %-22s %-6s %s" % (key, val, "[retail %s]" % d if d else ""))

    print("\nDAMAGE TYPE TABLE (attack type vs armour type):")
    for key, val in sorted(dmg_table.items()):
        print("  %-20s %s" % (key, val))
    print("\nwrote %s" % out_path)


if __name__ == "__main__":
    main()
