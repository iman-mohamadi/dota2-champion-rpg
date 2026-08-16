#!/usr/bin/env python3
"""Emit data/stats.lua — the stat vocabulary.

34 fields, cross-checked both ways against the item data: every field the
guidebook dictionary names is used by at least one item, and every field an item
uses is named. No orphans in either direction.

Each field is classified so the aggregator knows how to combine it:

  flat        summed, raw units            damage, armor, hp, str, movespeed
  fraction    summed, stored as 0.05 = 5%  skilldamagepercent, dtpercent
  multiplier  summed onto a base multiple  critmultiplier

Sign matters and is not uniform:
  drpercent  ("Damage Reduction")  positive is good
  dtpercent  ("Damage Taken")      NEGATIVE is good -- Stone Plates is -0.05,
                                   Mask of Blood is +0.06 as a drawback
so `higherIsBetter` is recorded per field rather than assumed.
"""
import os
import re

import common as C

GROUPS = {
    "armor": ["armor"],
    "constitution": ["hpregen", "mpregen", "hp", "mp"],
    "statsgain": ["mainstat", "allstat", "str", "agi", "int"],
    "affinities": ["affinitydarkpercent", "affinityflamepercent", "affinityearthpercent",
                   "affinitylightpercent", "affinityiwpercent", "affinitywlpercent"],
    "dexterities": ["attackspeedpercent", "movespeed", "critchancepercent", "critmultiplier"],
    "targeted": ["periodicdamagepercent", "skilldamagepercent", "procdamagepercent",
                 "aadamagepercent"],
    "defense": ["drpercent", "dtpercent", "mdpercent"],
    "survival": ["dodgechancepercent", "healingpercent", "healreceivedpercent"],
    "offense": ["damage", "damagedealtpercent"],
    "meta": ["expgainpercent", "revivaltimepercent"],
}

# Fields where a LOWER value is the benefit.
LOWER_IS_BETTER = {"dtpercent", "revivaltimepercent"}

# Attribute fields that feed STR/AGI/INT rather than standing alone.
ATTRIBUTE_FIELDS = {"str", "agi", "int", "allstat", "mainstat"}


def classify(field):
    if field == "critmultiplier":
        return "multiplier"
    if field.endswith("percent"):
        return "fraction"
    return "flat"


def build():
    src = open(os.path.join(C.RAW, "guidebook-dictionaries.ts"), encoding="utf-8").read()
    i = src.find("statsNameDictionary")
    names = dict(re.findall(r"(\w+):\s*\{\s*name:\s*\"([^\"]*)\"", src[i:]))

    items = C.raw("items.json")
    used = {}
    for it in items:
        for k, v in (it.get("stats") or {}).items():
            if isinstance(v, (int, float)):
                used[k] = used.get(k, 0) + 1

    # both directions must be empty or the vocabulary has drifted
    assert not set(names) - set(used), "dictionary fields unused by items: %s" % (
        sorted(set(names) - set(used)))
    assert not set(used) - set(names), "item fields missing from dictionary: %s" % (
        sorted(set(used) - set(names)))

    group_of = {f: g for g, fields in GROUPS.items() for f in fields}
    fields = {}
    for f in sorted(names):
        fields[f] = {
            "display": names[f].strip(),
            "kind": classify(f),
            "group": group_of.get(f, "other"),
            "higherIsBetter": f not in LOWER_IS_BETTER,
            "isAttribute": f in ATTRIBUTE_FIELDS,
            "itemCount": used[f],
        }

    data = {
        "NOTE": "fractions are stored as 0.05 = 5% and may be negative; see gen_stats.py",
        "fields": fields,
        "groups": {g: sorted(fs) for g, fs in GROUPS.items()},
        "attributeFields": sorted(ATTRIBUTE_FIELDS),
        "lowerIsBetter": sorted(LOWER_IS_BETTER),
    }
    C.write_lua_table(os.path.join(C.DATA, "stats.lua"), "Stats", data)
    return data


if __name__ == "__main__":
    d = build()
    from collections import Counter
    print("wrote data/stats.lua (%d fields)" % len(d["fields"]))
    print("  kinds: %s" % dict(Counter(v["kind"] for v in d["fields"].values())))
    print("  groups: %d" % len(d["groups"]))
