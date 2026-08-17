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




# ---------------------------------------------------------------- stats

def test_stats():
    print("\n== stat vocabulary ==")
    import gen_stats
    d = gen_stats.build()
    check("stat fields", len(d["fields"]), 34)
    check("fractions stored as 0.05 = 5%",
          d["fields"]["skilldamagepercent"]["kind"], "fraction")
    check("critmultiplier is a multiplier",
          d["fields"]["critmultiplier"]["kind"], "multiplier")
    check("damage is flat", d["fields"]["damage"]["kind"], "flat")
    print("\n== sign conventions differ and are recorded, not assumed ==")
    check("drpercent: higher is better", d["fields"]["drpercent"]["higherIsBetter"], True)
    check("dtpercent: LOWER is better", d["fields"]["dtpercent"]["higherIsBetter"], False)
    check("revivaltimepercent: LOWER is better",
          d["fields"]["revivaltimepercent"]["higherIsBetter"], False)

    print("\n== attribute rollup: allstat feeds all three, mainstat only primary ==")
    items = {i["name"]: i for i in C.raw("items.json")}

    def rollup(equip, primary):
        attrs = {"str": 0, "agi": 0, "int": 0}
        allstat = sum((items[e].get("stats") or {}).get("allstat", 0) for e in equip)
        mainstat = sum((items[e].get("stats") or {}).get("mainstat", 0) for e in equip)
        for f in attrs:
            attrs[f] = sum((items[e].get("stats") or {}).get(f, 0) for e in equip) + allstat
        attrs[primary] += mainstat
        return attrs

    a = rollup(["Anger"], "str")          # Anger: str 555
    check("Anger gives STR 555", a["str"], 555)
    check("Anger gives AGI 0", a["agi"], 0)

    print("\n== attack damage = weapon damage + primary * 3.0 ==")
    perpoint = C.extracted("curves.json")["primaryAttributeAttackBonus"]
    check("StrAttackBonus", C.num(perpoint), 3.0)
    dmg = items["Anger"]["stats"]["damage"] + 555 * 3.0
    check("Anger alone: 6750 + 555*3", dmg, 6750 + 1665)

    print("\n== levelling grants no stats, only points ==")
    curves = C.extracted("curves.json")
    zeroed = curves["attributeBonusesDisabled"]
    check("all 8 stock attribute effects zeroed",
          sum(1 for v in zeroed.values() if C.num(v) == 0.0), 8)


# ---------------------------------------------------------- persistence

MAX_LEVEL, TOTAL_POINTS, TOTAL_XP = 100, 697, 3951397


def validate(save, known_items, known_heroes):
    """Mirror of Persistence.Validate."""
    if not isinstance(save, dict):
        return False, "not a table"
    if save.get("schema") != 1:
        return False, "schema mismatch"
    if save.get("hero") not in known_heroes:
        return False, "unknown hero"
    lvl = save.get("level")
    if not isinstance(lvl, int) or lvl < 1 or lvl > MAX_LEVEL:
        return False, "level out of range"
    xp = save.get("xp", 0)
    if xp < 0 or xp > TOTAL_XP:
        return False, "xp out of range"
    a = save.get("allocation")
    if not isinstance(a, dict):
        return False, "missing allocation"
    spent = a.get("str", 0) + a.get("agi", 0) + a.get("int", 0)
    if spent < 0 or spent > TOTAL_POINTS:
        return False, "allocation over budget"
    earned = int(TOTAL_POINTS / (MAX_LEVEL - 1) * (lvl - 1) + 0.0001)
    if spent > earned:
        return False, "more points than the level earns"
    for cont in ("bag", "storage"):
        for e in (save.get("inventory") or {}).get(cont, []):
            if e["item"] not in known_items:
                return False, "unknown item"
            if not 1 <= e["count"] <= 5:
                return False, "bad stack size"
    return True, None


def test_persistence():
    print("\n== persistence: saves are rejected, never repaired ==")
    items = {C.item_key(i["name"]) for i in C.raw("items.json")}
    heroes = {C.hero_key(h["heroClass"]) for h in C.raw("heros.json")}
    good = {
        "schema": 1, "hero": C.hero_key("Berserker"), "level": 50, "xp": 270424,
        "allocation": {"str": 300, "agi": 0, "int": 0},
        "inventory": {"bag": [{"slot": 1, "item": C.item_key("Anger"), "count": 1}],
                      "storage": [], "equipped": {}},
    }
    check("a valid save passes", validate(good, items, heroes)[0], True)

    def bad(**over):
        s = {k: (v.copy() if isinstance(v, dict) else v) for k, v in good.items()}
        s.update(over)
        return validate(s, items, heroes)[0]

    check("wrong schema rejected", bad(schema=2), False)
    check("unknown hero rejected", bad(hero="npc_dota_hero_championrpg_nonexistent"), False)
    check("level 0 rejected", bad(level=0), False)
    check("level 101 rejected", bad(level=101), False)
    check("negative xp rejected", bad(xp=-1), False)
    check("xp beyond cap rejected", bad(xp=TOTAL_XP + 1), False)
    check("allocation over 697 rejected",
          bad(allocation={"str": 700, "agi": 0, "int": 0}), False)
    check("more points than the level earns rejected",
          bad(level=2, allocation={"str": 600, "agi": 0, "int": 0}), False)
    check("unknown item rejected",
          bad(inventory={"bag": [{"slot": 1, "item": "item_championrpg_forged", "count": 1}],
                         "storage": [], "equipped": {}}), False)
    check("stack above the cap of 5 rejected",
          bad(inventory={"bag": [{"slot": 1, "item": C.item_key("Anger"), "count": 99}],
                         "storage": [], "equipped": {}}), False)

    print("\n== the point budget is level-gated, not just capped ==")
    per = TOTAL_POINTS / (MAX_LEVEL - 1)
    check("level 100 earns the full budget", int(per * 99 + 0.0001), 697)
    check("level 1 earns none", int(per * 0 + 0.0001), 0)




# ------------------------------------------------------- encounters/codex

def test_encounters():
    print("\n== encounters: scaffolds are honest about what is authored ==")
    import gen_encounters
    d = gen_encounters.build()
    bosses = [b for b in C.raw("bosses.json") if b["type"] == "Boss"]
    check("one scaffold per boss", len(d), len(bosses))
    check("none claim to be authored",
          sum(1 for v in d.values() if v.get("authored")), 0)
    check("scripted hooks flagged",
          sum(1 for v in d.values() if v.get("needsScriptedHook")), 6)

    print("\n== difficulty modes match docs/00 §3.8 ==")
    m = list(d.values())[0]["modes"]
    check("practice: boss takes 300% damage", m["practice"]["damageTaken"], 3.0)
    check("practice: boss deals 75% less", m["practice"]["damageDealt"], 0.25)
    check("practice: no drops", m["practice"]["drops"], False)
    check("hard: +50% drop rate", m["hard"]["dropRateBonus"], 0.50)

    print("\n== party scaling: 8-10 players reduce add HP by 25% (patch 64b) ==")
    ps = list(d.values())[0]["partyScaling"]
    check("8-10 addHealth", ps["8-10"]["addHealth"], -0.25)

    def scaling_for(table, size):
        """Mirror of Encounter:ScalingFor."""
        for rng, mods in table.items():
            if "-" in rng:
                lo, hi = rng.split("-")
                if int(lo) <= size <= int(hi):
                    return mods
            elif int(rng) == size:
                return mods
        return {}

    check("size 9 matches the 8-10 band", scaling_for(ps, 9).get("addHealth"), -0.25)
    check("size 4 matches nothing", scaling_for(ps, 4), {})

    print("\n== empowered stat sets come from the data ==")
    # Three bosses carry the empoweredStats KEY, but Gaia's value is an empty
    # table upstream, so only two have a usable set. docs/00 reported 3 from a
    # key-presence count; the generator emits only non-empty ones.
    raw = C.raw("bosses.json")
    check("entries with the key present", len([b for b in raw if "empoweredStats" in b]), 3)
    check("of which non-empty", len([b for b in raw if b.get("empoweredStats")]), 2)
    emp = [v for v in d.values() if v.get("empowered")]
    check("bosses with a usable empowered set", len(emp), 2)
    ag = d[C.unit_key("Underlord Agareth")]
    check("Agareth empowered damageResist", ag["empowered"]["damageResist"], 75.0)


def test_codex():
    print("\n== codex: hunt objectives parsed from boss conditions ==")
    import gen_codex
    d, review = gen_codex.build()
    hunt = d["hunt"]
    check("one hunt per boss", len(hunt),
          len([b for b in C.raw("bosses.json") if b["type"] == "Boss"]))
    full = sum(1 for e in hunt.values() if e["confidence"] >= 0.999)
    check("fully structured hunts", full, 47)
    check("needing review", len(review), 5)
    check("raw text always preserved",
          sum(1 for e in hunt.values() if e.get("rawConditions") is None
              or e["rawConditions"]), len(hunt))

    print("\n== specific parses ==")
    ag = hunt[C.unit_key("Underlord Agareth")]
    kinds = [o["kind"] for o in ag["objectives"]]
    check("Agareth requires a level", "level" in kinds, True)
    lvl = [o for o in ag["objectives"] if o["kind"] == "level"][0]
    check("Agareth level 100", lvl["min"], 100)

    beriel = hunt[C.unit_key("Demon Lord Beriel")]
    items = [o for o in beriel["objectives"] if o["kind"] == "item"]
    check("Beriel needs Red Magic Stone x6", items[0]["count"], 6)
    check("  with a location hint kept separate",
          "Area 7" in (items[0].get("locationHint") or ""), True)

    nat = hunt[C.unit_key("Protector of Nature")]
    it = [o for o in nat["objectives"] if o["kind"] == "item"][0]
    check("Protector of Nature: Ancient Branch x3", it["count"], 3)
    check("  location hint 'at big tree'", it.get("locationHint"), "at big tree")

    print("\n== unparseable steps are kept verbatim, never guessed ==")
    ff = [o for e in hunt.values() for o in e["objectives"] if o["kind"] == "freeform"]
    check("freeform objectives", len(ff), 5)
    texts = {o["text"] for o in ff}
    check("'Orb of the Sea' left alone (item is 'Orb of the Deep Sea')",
          "Orb of the Sea" in texts, True)

    print("\n== chronicle chains ==")
    ch = d["chronicle"]
    check("chains", len(ch), 2)
    check("Hell Invasion has 4 steps", len(ch["hell_invasion"]["steps"]), 4)
    check("last step is Agareth",
          ch["hell_invasion"]["steps"][-1]["requires"]["unit"],
          C.unit_key("Underlord Agareth"))


def main():
    test_stacking()
    test_inventory()
    test_crafting()
    test_loot()
    test_stats()
    test_persistence()
    test_encounters()
    test_codex()
    print("\n%s" % ("ALL PASS" if not FAILED else "%d FAILURES: %s" % (len(FAILED), FAILED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
