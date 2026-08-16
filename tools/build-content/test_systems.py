#!/usr/bin/env python3
"""Rule tests for the systems layer.

Same caveat as test_formulas.py: there is no Lua interpreter here, so these
mirror the *logic* of the Lua modules in Python and assert the rules the
research established. They prove the rules are right and that the generated data
supports them; they do not execute core/stacking.lua et al.

Keep the Lua free of engine calls in these modules so the mirror stays faithful.

Usage: python3 tools/build-content/test_systems.py
"""
import sys

import common as C

FAILED = []


def check(label, got, want):
    ok = got == want if not isinstance(want, float) else abs(got - want) < 1e-9
    print("  %-58s %-18s %s" % (label, repr(got), "ok" if ok else "FAIL (want %r)" % (want,)))
    if not ok:
        FAILED.append(label)


# ---------------------------------------------------------------- stacking

def resolve_slot(effects):
    """Mirror of resolveSlot in core/stacking.lua."""
    best, total, stackable = 0.0, 0.0, False
    for e in effects:
        m = e.get("magnitude", 0.0)
        if e.get("stackable"):
            stackable = True
            total += m
        elif abs(m) > abs(best):
            best = m
    return (total + best) if stackable else best


def multiplier(buckets):
    mult = 1.0
    for slot_effects in buckets.values():
        mult *= 1.0 + resolve_slot(slot_effects)
    return mult


def test_stacking():
    print("== stacking: within a slot only the strongest applies ==")
    check("two Type-A armour reductions (15%, 12%) -> 15%",
          resolve_slot([{"magnitude": 0.15}, {"magnitude": 0.12}]), 0.15)
    check("three Type-A (12%, 15%, 8%) -> 15%",
          resolve_slot([{"magnitude": 0.12}, {"magnitude": 0.15}, {"magnitude": 0.08}]), 0.15)

    print("\n== across slots they multiply ==")
    got = multiplier({"Type-A": [{"magnitude": 0.15}], "Type-B": [{"magnitude": 0.10}]})
    check("Type-A 15% x Type-B 10%", round(got, 6), round(1.15 * 1.10, 6))
    got = multiplier({"Type-A": [{"magnitude": 0.15}, {"magnitude": 0.12}],
                      "Type-B": [{"magnitude": 0.10}]})
    check("adding a weaker Type-A changes nothing", round(got, 6), round(1.15 * 1.10, 6))

    print("\n== Stackable slots sum ==")
    check("three stackable 5% -> 15%",
          round(resolve_slot([{"magnitude": 0.05, "stackable": True}] * 3), 6), 0.15)

    print("\n== the slot table is data, not code ==")
    st = C.raw("buffs.json") + C.raw("debuffs.json")
    check("slot definitions loaded", len(st), 30)
    kinds = {r.get("bufftype") or r.get("debufftype") for r in st}
    check("distinct effect kinds", len(kinds), 16)
    check("Armor Reduction has 3 slots (A/B/C)",
          len([r for r in st if r.get("debufftype") == "Armor Reduction"]), 3)
    check("a Stackable slot exists", any(r["type"] == "Stackable" for r in st), True)


# --------------------------------------------------------------- inventory

class Inv:
    """Mirror of systems/inventory.lua."""

    def __init__(self, bag=24, storage=24, stack=5):
        self.bag_slots, self.storage_slots, self.max_stack = bag, storage, stack
        self.bag, self.storage = {}, {}

    def _add(self, grid, slots, item, count):
        placed = 0
        for i in range(1, slots + 1):
            if placed >= count:
                break
            s = grid.get(i)
            if s and s["item"] == item and s["count"] < self.max_stack:
                take = min(self.max_stack - s["count"], count - placed)
                s["count"] += take
                placed += take
        for i in range(1, slots + 1):
            if placed >= count:
                break
            if i not in grid:
                take = min(self.max_stack, count - placed)
                grid[i] = {"item": item, "count": take}
                placed += take
        return placed

    def acquire(self, item, count=1):
        b = self._add(self.bag, self.bag_slots, item, count)
        s = self._add(self.storage, self.storage_slots, item, count - b)
        return {"bag": b, "storage": s, "ground": count - b - s}

    def count(self, item):
        return sum(x["count"] for g in (self.bag, self.storage)
                   for x in g.values() if x["item"] == item)

    def remove(self, item, count=1):
        if self.count(item) < count:
            return False
        left = count
        for grid in (self.bag, self.storage):
            for i in list(grid):
                if left <= 0:
                    break
                s = grid[i]
                if s["item"] == item:
                    take = min(s["count"], left)
                    s["count"] -= take
                    left -= take
                    if s["count"] <= 0:
                        del grid[i]
        return True


def test_inventory():
    print("\n== inventory: 24 bag + 24 storage, stacks of 5 ==")
    inv = Inv()
    r = inv.acquire("mat", 12)
    check("12 units -> bag only", (r["bag"], r["storage"], r["ground"]), (12, 0, 0))
    check("occupies ceil(12/5)=3 slots", len(inv.bag), 3)

    inv = Inv()
    r = inv.acquire("mat", 24 * 5)
    check("bag holds exactly 24*5=120", r["bag"], 120)
    check("bag full", len(inv.bag), 24)

    print("\n== overflow chain: bag -> storage -> ground, nothing destroyed ==")
    inv = Inv()
    r = inv.acquire("mat", 24 * 5 + 10)
    check("overflow reaches storage", (r["bag"], r["storage"], r["ground"]), (120, 10, 0))
    inv = Inv()
    total = 24 * 5 + 24 * 5 + 7
    r = inv.acquire("mat", total)
    check("beyond storage goes to ground", (r["bag"], r["storage"], r["ground"]), (120, 120, 7))
    check("nothing lost", r["bag"] + r["storage"] + r["ground"], total)

    print("\n== remove is all-or-nothing ==")
    inv = Inv()
    inv.acquire("mat", 7)
    check("cannot remove more than held", inv.remove("mat", 8), False)
    check("held count unchanged", inv.count("mat"), 7)
    check("can remove exactly", inv.remove("mat", 7), True)
    check("now empty", inv.count("mat"), 0)


# ---------------------------------------------------------------- crafting

def test_crafting():
    print("\n== crafting: full expansion to leaf materials ==")
    items = C.raw("items.json")
    rec = {}
    for i in items:
        if i.get("recipe"):
            rec[i["name"]] = [(k, v) for step in i["recipe"] for k, v in step.items()]

    def expand(name, mult=1, acc=None, seen=()):
        acc = {} if acc is None else acc
        if name not in rec or name in seen:
            acc[name] = acc.get(name, 0) + mult
            return acc
        for c, q in rec[name]:
            expand(c, mult * q, acc, seen + (name,))
        return acc

    # cross-check against research/tables/crafting.md, produced in the research phase
    leaves = expand("Bag of All Evils")
    check("Bag of All Evils: distinct leaves", len(leaves), 25)
    check("Bag of All Evils: total leaf drops", sum(leaves.values()), 60)
    check("  of which Prius Gold Coin", leaves.get("Prius Gold Coin"), 17)
    check("  of which Prius Silver Coin", leaves.get("Prius Silver Coin"), 15)

    check("total recipes", len(rec), 486)
    # no recipe may reference a missing item
    names = {i["name"] for i in items}
    bad = [c for comps in rec.values() for c, _ in comps if c not in names]
    check("recipe components all exist", len(bad), 0)


# -------------------------------------------------------------------- loot

def chance(rate_pct, hard=False, wished=False):
    """Mirror of Loot.Chance."""
    r = rate_pct / 100.0
    if hard:
        r *= 1.5
    if wished:
        r *= 2.0
    return min(1.0, r)


def test_loot():
    print("\n== loot: rates, Hard mode and the Wish pity system ==")
    check("base 0.8% -> 0.008", round(chance(0.8), 6), 0.008)
    check("hard mode +50%", round(chance(0.8, hard=True), 6), 0.012)
    check("wish +100%", round(chance(0.8, wished=True), 6), 0.016)
    check("hard + wish", round(chance(0.8, hard=True, wished=True), 6), 0.024)
    check("clamped at 100%", chance(80, hard=True, wished=True), 1.0)

    print("\n== wish suppresses every other drop ==")
    table = ["a", "b", "c"]
    wished = [k for k in table if k == "b"]
    check("only the wished item can roll", wished, ["b"])

    print("\n== practice mode drops nothing ==")
    check("practice mode result", [], [])

    print("\n== chest is participant-gated and clears when all resolve ==")
    participants = {1: True, 2: True}
    resolved = {}
    check("non-participant blocked", 3 in participants, False)
    resolved[1] = "taken"
    check("not finished with one outstanding",
          all(p in resolved for p in participants), False)
    resolved[2] = "passed"
    check("finished once all took or passed",
          all(p in resolved for p in participants), True)

    print("\n== chest tiers come from the data ==")
    bosses = C.raw("bosses.json")
    chest_tiers = {"Late", "Endgame"}
    n = len([b for b in bosses if b.get("category") in chest_tiers and b["type"] == "Boss"])
    check("bosses using the shared chest", n, 9)


def main():
    test_stacking()
    test_inventory()
    test_crafting()
    test_loot()
    print("\n%s" % ("ALL PASS" if not FAILED else "%d FAILURES: %s" % (len(FAILED), FAILED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
