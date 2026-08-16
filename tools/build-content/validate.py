#!/usr/bin/env python3
"""Reference validator for the TWRPG content set.

Fails loudly on dangling references. With 765 items, 486 recipes and 147
monsters cross-referencing each other by name and by rawcode, a silent broken
link would surface much later as a mysterious runtime nil.

This is the CI gate described in docs/02-TECH-PLAN.md §4.

Exit code 0 = clean, 1 = errors found. Warnings never fail the build.

Usage: python3 tools/build-content/validate.py [--strict]
"""
import sys

import common as C

# Sources in `dropped_by` that are not monsters. Verified against the data, not guessed.
KNOWN_NON_MONSTER_SOURCES = {"Tutorial", "Shop", "Sealed Weapon", "Agareth", "Quest", "Event"}

# Items that appear in `required_by` as ALTERNATE ingredients. The upstream dataset does not
# model alternate recipes at all (the guidebook README lists "item alt recipes" as a TODO),
# so `required_by` is legitimately broader than the inverse of `recipe` for these.
# Verified: 'Prius Platinum Coin' has 22 parents and no recipe of its own.
KNOWN_ALT_INGREDIENTS = {"Prius Platinum Coin", "Prius Gold Coin", "Prius Silver Coin"}


def main(strict=False):
    items = C.raw("items.json")
    bosses = C.raw("bosses.json")
    heroes = C.raw("heros.json")
    skills = C.raw("skills.json")

    item_by_name = {i["name"]: i for i in items}
    item_by_id = {i["id"]: i for i in items}
    errors, warnings = [], []

    # ---- 1. recipes reference real items
    for it in items:
        for step in it.get("recipe", []) or []:
            for comp, qty in step.items():
                if comp not in item_by_name:
                    errors.append("recipe: %r requires unknown item %r" % (it["name"], comp))
                if C.num(qty) <= 0:
                    errors.append("recipe: %r requires %r x%s" % (it["name"], comp, qty))

    # ---- 2. required_by is the inverse of recipe; check it agrees
    for it in items:
        for parent in it.get("required_by", []) or []:
            p = item_by_name.get(parent)
            if p is None:
                errors.append("required_by: %r claims parent %r which does not exist"
                              % (it["name"], parent))
                continue
            comps = {c for step in (p.get("recipe") or []) for c in step}
            if it["name"] not in comps and it["name"] not in KNOWN_ALT_INGREDIENTS:
                warnings.append("required_by: %r lists parent %r, but that recipe omits it"
                                % (it["name"], parent))

    # ---- 3. boss drops reference real item ids
    for b in bosses:
        for d in b.get("drops", []) or []:
            if d not in item_by_id:
                errors.append("drops: boss %r drops unknown item id %r" % (b["name"], d))

    # ---- 4. dropped_by references real monsters
    monster_names = {b["name"] for b in bosses}
    for it in items:
        for src in it.get("dropped_by", []) or []:
            if src not in monster_names and src not in KNOWN_NON_MONSTER_SOURCES:
                warnings.append("dropped_by: item %r sourced from unknown monster %r"
                                % (it["name"], src))

    # ---- 5. minions/summons reference real units
    for b in bosses:
        for m in b.get("minions", []) or []:
            if m not in monster_names:
                warnings.append("minions: %r summons unknown unit %r" % (b["name"], m))

    # ---- 6. every craftable item is reachable from farmable leaves
    rec = {i["name"]: [c for step in (i.get("recipe") or []) for c in step] for i in items
           if i.get("recipe")}
    droppable = {i["name"] for i in items if i.get("dropped_by")}
    memo = {}

    def reachable(name, seen=()):
        if name in memo:
            return memo[name]
        if name in seen:
            return False  # recipe cycle
        if name not in rec:
            return True  # a leaf; obtainable by drop, vendor or quest
        ok = all(reachable(c, seen + (name,)) for c in rec[name])
        memo[name] = ok
        return ok

    for name in rec:
        if not reachable(name):
            errors.append("recipe graph: %r is not reachable from leaf materials (cycle?)" % name)

    # ---- 7. hero/skill integrity
    hero_classes = {h["heroClass"] for h in heroes}
    for s in skills:
        if s["heroClass"] not in hero_classes:
            errors.append("skill: %r belongs to unknown class %r" % (s["name"], s["heroClass"]))
    for h in heroes:
        if not [s for s in skills if s["heroClass"] == h["heroClass"]]:
            warnings.append("hero: %r has no skills" % h["heroClass"])
        if h.get("mainstat") not in ("STR", "AGI", "INT"):
            errors.append("hero: %r has bad mainstat %r" % (h["heroClass"], h.get("mainstat")))

    # ---- 8. generated key collisions (two names slugging to one key)
    for label, names, keyfn in (
        ("item", [i["name"] for i in items], C.item_key),
        ("unit", [b["name"] for b in bosses], C.unit_key),
        ("hero", [h["heroClass"] for h in heroes], C.hero_key),
    ):
        seen = {}
        for n in names:
            k = keyfn(n)
            if k in seen and seen[k] != n:
                errors.append("key collision: %s %r and %r both -> %r" % (label, seen[k], n, k))
            seen[k] = n

    # ---- report
    for w in warnings:
        print("  WARN  %s" % w)
    for e in errors:
        print("  ERROR %s" % e)
    print("\nvalidated: %d items, %d monsters, %d heroes, %d skills, %d recipes"
          % (len(items), len(bosses), len(heroes), len(skills), len(rec)))
    print("%d errors, %d warnings" % (len(errors), len(warnings)))

    if errors or (strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main("--strict" in sys.argv))
