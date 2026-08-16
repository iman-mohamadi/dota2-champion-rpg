#!/usr/bin/env python3
"""Build the Dota 2 addon content from research/.

    python3 tools/build-content/build.py

Runs the reference validator first and refuses to emit anything if it fails —
a dangling reference is far cheaper to fix here than as a runtime nil in Lua.
After generating, cross-checks that the emitted files agree with each other.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as C          # noqa: E402
import validate             # noqa: E402
import gen_constants        # noqa: E402
import gen_units            # noqa: E402
import gen_items            # noqa: E402
import gen_abilities        # noqa: E402
import gen_heroes           # noqa: E402
import gen_stacking         # noqa: E402
import gen_stats            # noqa: E402


def cross_check(units, items, recipes, abilities, heroes):
    """Every reference inside the generated set must resolve."""
    errors = []

    for key, u in units.items():
        for m in u.get("minions", []):
            if m not in units:
                errors.append("units.lua: %s summons missing unit %s" % (key, m))
        for d in u.get("drops", []):
            if d not in items:
                errors.append("units.lua: %s drops missing item %s" % (key, d))

    for key, r in recipes.items():
        if r["result"] not in items:
            errors.append("recipes.lua: result %s is not an item" % r["result"])
        for c in r["components"]:
            if c["item"] not in items:
                errors.append("recipes.lua: %s needs missing item %s" % (key, c["item"]))

    for key, h in heroes.items():
        for a in h["abilities"]:
            if a not in abilities:
                errors.append("heroes.lua: %s references missing ability %s" % (key, a))
        if not h["topLevelAbilities"]:
            errors.append("heroes.lua: %s has no top-level abilities" % key)

    # every equippable item names a slot; every data-only item does not
    for key, it in items.items():
        if it.get("weaponClass") and it.get("equipSlot") != "weapon":
            errors.append("items.lua: %s has a weaponClass but slot %r"
                          % (key, it.get("equipSlot")))
    return errors


def main():
    print("== validating source ==")
    if validate.main() != 0:
        print("\nBUILD FAILED: fix the errors above before generating content.")
        return 1

    print("\n== generating ==")
    _, consts = gen_constants.build()
    print("  constants.lua          max level %d, %s XP to max, armour k=%s"
          % (consts["MAX_HERO_LEVEL"], format(consts["TOTAL_XP_TO_MAX"], ","),
             consts["ARMOR_K"]))

    ukv, units = gen_units.build(consts)
    print("  npc_units_custom.txt   %d units (%d bosses)"
          % (len(ukv), sum(1 for v in units.values() if v["kind"] == "Boss")))

    ikv, items, recipes = gen_items.build()
    print("  npc_items_custom.txt   %d equippable of %d items" % (len(ikv), len(items)))
    print("  recipes.lua            %d recipes" % len(recipes))

    akv, abilities = gen_abilities.build()
    print("  npc_abilities_custom   %d abilities (%d sub-menu)"
          % (len(akv), sum(1 for v in abilities.values() if v["submenuDepth"])))

    hkv, heroes = gen_heroes.build(consts)
    print("  npc_heroes_custom.txt  %d classes" % len(hkv))

    statdefs = gen_stats.build()
    print("  stats.lua              %d stat fields" % len(statdefs["fields"]))

    stacking = gen_stacking.build()
    print("  stacking.lua           %d slots over %d effect kinds, %d sources"
          % (len(stacking["slots"]), len(stacking["byKind"]), len(stacking["bySource"])))

    print("\n== cross-checking generated set ==")
    errors = cross_check(units, items, recipes, abilities, heroes)
    for e in errors[:25]:
        print("  ERROR %s" % e)
    if errors:
        print("\nBUILD FAILED: %d cross-reference errors in generated output." % len(errors))
        return 1
    print("  all references resolve")

    print("\n== output ==")
    total = 0
    for root, _, files in os.walk(C.ADDON):
        for f in sorted(files):
            p = os.path.join(root, f)
            total += os.path.getsize(p)
            print("  %-60s %9d bytes" % (os.path.relpath(p, C.ROOT), os.path.getsize(p)))
    print("  %-60s %9d bytes" % ("TOTAL", total))
    print("\nBUILD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
