#!/usr/bin/env python3
"""Regression tests for the recovered formulas and the generated constants.

These mirror the arithmetic in core/damage.lua and assert it against the values
published in docs/05-COMBAT-FORMULAS.md. If someone edits a constant or a
formula, this fails.

IMPORTANT — what this does and does not cover:
  covered      the maths, and that constants.lua carries the right numbers
  NOT covered  the Lua itself. There is no Lua interpreter in this environment
               and Dota's API cannot be stubbed meaningfully, so core/damage.lua
               is unverified until it runs in-game. Keep the arithmetic in that
               file free of engine calls so this mirror stays faithful.

Usage: python3 tools/build-content/test_formulas.py
"""
import re
import sys

import common as C

FAILED = []


def check(label, got, want, tol=1e-6):
    ok = abs(got - want) <= tol * max(1.0, abs(want))
    print("  %-58s %-16s %s" % (label, ("%.6g" % got), "ok" if ok else "FAIL (want %.6g)" % want))
    if not ok:
        FAILED.append(label)


# ---- the formulas, mirroring core/damage.lua ------------------------------

def armor_multiplier(armor, k=0.02, neg_base=0.94):
    if armor >= 0:
        return 1.0 - ((armor * k) / (1.0 + k * armor))
    return 2.0 - neg_base ** (-armor)


def unapply_armor(damage, armor):
    return damage / armor_multiplier(armor)


def need_for_level(level, base=150.0, a=1.05, b=75.0):
    """XP to go from `level` to level+1."""
    need = base
    for _ in range(1, level):
        need = a * need + b
    return need


def main():
    print("== armour mitigation: damage * 1/(1 + 0.02*armor) ==")
    # Expectations at full precision. docs/05 §4 displays these rounded to 2dp;
    # do NOT copy the rounded display into a test — an earlier revision of this
    # file did exactly that for armour 1120 (95.73% -> "95.733333") and failed.
    for armor, want_pct in [(0, 0.0), (100, 66.666667), (300, 85.714286),
                            (730, 93.589744), (1120, 95.726496),
                            (1240, 96.124031), (1290, 96.268657), (2000, 97.560976)]:
        check("armor %d -> reduction %%" % armor,
              (1 - armor_multiplier(armor)) * 100, want_pct, tol=1e-5)

    # cross-check every published row against research/extracted/curves.json
    mismatch = 0
    for row in C.extracted("curves.json")["armor"]["table"]:
        got = (1 - armor_multiplier(row["armor"])) * 100
        if abs(got - row["reductionPct"]) > 5e-3:
            mismatch += 1
    check("all %d curves.json armour rows agree" % len(C.extracted("curves.json")["armor"]["table"]),
          mismatch, 0)

    print("\n== armour round-trip (eMo / eqo are exact inverses) ==")
    for armor in (0, 300, 1240, -5):
        check("unapply(apply(1000, %d))" % armor,
              unapply_armor(1000 * armor_multiplier(armor), armor), 1000.0)

    print("\n== negative armour: 2 - 0.94^(-armor) ==")
    check("armor -10 multiplier", armor_multiplier(-10), 2.0 - 0.94 ** 10)

    print("\n== EXP curve: Need(L) = 1.05*Need(L-1) + 75, Need(1) = 150 ==")
    # closed form from docs/05 §2
    for lvl in (1, 2, 10, 50, 99):
        check("Need(%d)" % lvl, need_for_level(lvl), 1650 * (1.05 ** (lvl - 1)) - 1500, tol=1e-9)
    check("Need(1)", need_for_level(1), 150.0)
    check("Need(2)", need_for_level(2), 232.5)

    print("\n== generated constants.lua agrees with research/extracted/curves.json ==")
    lua = open(C.DATA + "/constants.lua", encoding="utf-8").read()
    curves = C.extracted("curves.json")

    m = re.search(r"ARMOR_K = ([0-9.]+)", lua)
    check("constants.lua ARMOR_K", float(m.group(1)), C.num(curves["armor"]["DefenseArmor"]))

    m = re.search(r"MAX_HERO_LEVEL = (\d+)", lua)
    check("constants.lua MAX_HERO_LEVEL", int(m.group(1)), curves["maxHeroLevel"])

    m = re.search(r"TOTAL_XP_TO_MAX = (\d+)", lua)
    check("constants.lua TOTAL_XP_TO_MAX", int(m.group(1)), 3951397)

    xp = [int(x) for x in re.search(r"XP_PER_LEVEL = \{(.*?)\n\t\}", lua, re.S).group(1).split(",")
          if x.strip()]
    check("XP table length", len(xp), 100)
    check("XP_PER_LEVEL[1] (level 1 is free)", xp[0], 0)
    check("XP_PER_LEVEL[2]", xp[1], 150)
    check("XP_PER_LEVEL[100]", xp[99], 3951397)
    # cumulative must be strictly increasing
    check("XP table monotonic", 1 if all(xp[i] < xp[i + 1] for i in range(len(xp) - 1)) else 0, 1)

    print("\n== creep XP: 0.85*L^2 + 2*L + 2 ==")
    for lvl, want in [(3, 15.65), (20, 382.0), (100, 8702.0), (130, 14627.0)]:
        check("level %d grants" % lvl, 0.85 * lvl * lvl + 2 * lvl + 2, want, tol=1e-6)

    print("\n== generated unit stats round-trip to source ==")
    units = open(C.DATA + "/units.lua", encoding="utf-8").read()
    bosses = {b["name"]: b for b in C.raw("bosses.json")}
    for name in ("Underlord Agareth", "Demon Lord Beriel", "Duke Lazarus"):
        key = C.unit_key(name)
        blk = re.search(r'%s = \{(.*?)\n\t\}' % re.escape(key), units, re.S)
        if not blk:
            FAILED.append("units.lua missing " + key)
            print("  %-58s FAIL (missing)" % key)
            continue
        got = float(re.search(r"armor = ([0-9.\-]+)", blk.group(1)).group(1))
        check("%s armour" % name, got, C.num(bosses[name]["stats"]["armor"]))

    print("\n== generated content counts match the source ==")
    src_items = C.raw("items.json")
    src_bosses = C.raw("bosses.json")
    src_heroes = C.raw("heros.json")
    src_skills = C.raw("skills.json")

    def count_entries(path, indent="\t"):
        """Top-level keys in a generated Lua table."""
        txt = open(path, encoding="utf-8").read()
        return len(re.findall(r"^%s[\w\[\]\"']+ = \{" % indent, txt, re.M))

    check("items.lua entries", count_entries(C.DATA + "/items.lua"), len(src_items))
    check("units.lua entries", count_entries(C.DATA + "/units.lua"), len(src_bosses))
    check("heroes.lua entries", count_entries(C.DATA + "/heroes.lua"), len(src_heroes))
    check("abilities.lua entries", count_entries(C.DATA + "/abilities.lua"), len(src_skills))
    check("recipes", len([i for i in src_items if i.get("recipe")]), 486)

    print("\n== item grade tiers match docs/00 §3.4 ==")
    from collections import Counter
    grades = Counter(i.get("grade", 0) for i in src_items)
    for g, want, tier in [(1, 100, "Deltirama"), (2, 117, "Neptinos"), (3, 113, "Gnosis"),
                          (4, 106, "Alteia"), (5, 94, "Arcana")]:
        check("grade %d (%s)" % (g, tier), grades[g], want)

    print("\n== ability keys are collision-free (class+name, not name) ==")
    from gen_abilities import ability_id
    keys = {ability_id(s["heroClass"], s["name"]) for s in src_skills}
    check("distinct ability keys", len(keys), len(src_skills))

    print("\n== equipment split ==")
    import gen_items
    equip = sum(1 for i in src_items if gen_items.normalise_type(i.get("type")) in gen_items.EQUIPMENT)
    check("equippable items", equip, 576)
    check("data-only items", len(src_items) - equip, 189)
    check("'headwear' case variants normalised",
          len({gen_items.normalise_type(i["type"]) for i in src_items
               if i["type"].lower() == "headwear"}), 1)

    print("\n%s" % ("ALL PASS" if not FAILED else "%d FAILURES: %s" % (len(FAILED), FAILED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
