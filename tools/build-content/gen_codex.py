#!/usr/bin/env python3
"""Parse boss summon conditions into Codex objectives -> data/codex.lua.

TWRPG has essentially no quests (docs/00 §4). Progression is driven by gated
boss summons, recipe completion and world-state chains, all of which are
*implicit* in the original. The Codex makes them explicit trackable objectives.

This generator handles the Hunt track. The condition strings are regular enough
to parse mechanically:

    "Level 25 and Ancient Branch x3 at big tree"
    "Level 90, Red Magic Stone x6 in Area 7 ... and Waves defeated ..."

but not uniformly, so every objective carries a confidence score and the raw
text is always preserved. Anything below threshold is listed for manual review
rather than silently guessed at — same discipline as the ability parser.

The Forge track needs no parsing (it comes straight from the recipe graph) and
the Chronicle track is hand-authored world state.
"""
import os
import re

import common as C

# "Recommen\w*" rather than "Recommended": the source contains the typo
# "Recommened Level 100" (Flame Nightmare).
LEVEL_RANGE = re.compile(r"(?:Recommen\w*\s+)?[Ll]evel\s+(\d+)\s*~\s*(\d+)")
LEVEL_MIN = re.compile(r"(?:Recommen\w*\s+)?[Ll]evel\s+(\d+)")
# Guardian of Sea is just "70 ~ 90 and ..." with the word Level missing entirely.
BARE_RANGE = re.compile(r"^(\d+)\s*~\s*(\d+)$")
# "Red Magic Stone x6", and with a trailing location hint:
# "Ancient Branch x3 at big tree" / "White Magic Stone x6 in the far top right of the Cave"
ITEM_QTY = re.compile(r"^(.*?[A-Za-z])\s*[xX]\s*(\d+)\s*(.*)$")
# ", and X" splits to a clause still carrying the conjunction
LEADING_AND = re.compile(r"^and\s+", re.I)
SUMMONED_BY = re.compile(r"^[Ss]ummoned by (.+)$")
# "Avalon summoned", "Frostspider Lord summoned" -- a prior boss must be up.
PREREQ_SUMMON = re.compile(r"^(.+?)\s+summoned$")
# "Orb of the Deep Sea with Green Magic Stone x4" -- a focus item plus reagents.
WITH_SPLIT = re.compile(r"\s+with\s+")
# "Key of Storm crafted" -- an item requirement phrased as an outcome.
ITEM_CRAFTED = re.compile(r"^(.+?)\s+crafted$")
# "Seal Breaking Gemstone to unseal Ancient Ent" -- item plus its purpose.
ITEM_PURPOSE = re.compile(r"^(.+?)\s+(to\s+.+)$")

# Clause separators. Splitting on these keeps prose fragments intact.
SPLIT = re.compile(r",\s*|\s+and\s+")


def _clause(clause, item_names, out):
    """Try to structure one clause. Returns True if it was understood."""
    clause = LEADING_AND.sub("", clause.strip()).strip()
    if not clause:
        return True

    m = LEVEL_RANGE.search(clause)
    if m:
        out.append({"kind": "level", "min": int(m.group(1)),
                    "recommendedMax": int(m.group(2))})
        return True
    m = BARE_RANGE.match(clause)
    if m:
        out.append({"kind": "level", "min": int(m.group(1)),
                    "recommendedMax": int(m.group(2))})
        return True
    m = LEVEL_MIN.search(clause)
    if m:
        out.append({"kind": "level", "min": int(m.group(1))})
        return True

    m = SUMMONED_BY.match(clause)
    if m:
        out.append({"kind": "summonedBy", "unit": m.group(1).strip()})
        return True
    m = PREREQ_SUMMON.match(clause)
    if m:
        out.append({"kind": "prerequisiteSummon", "target": m.group(1).strip()})
        return True

    # "A with B x4" -- recurse on both halves.
    if WITH_SPLIT.search(clause):
        parts = WITH_SPLIT.split(clause)
        if all(_clause(p, item_names, out) for p in parts):
            return True

    m = ITEM_CRAFTED.match(clause)
    if m and m.group(1).strip() in item_names:
        out.append({"kind": "item", "item": C.item_key(m.group(1).strip()), "count": 1,
                    "mustCraft": True})
        return True

    m = ITEM_PURPOSE.match(clause)
    if m and m.group(1).strip() in item_names:
        out.append({"kind": "item", "item": C.item_key(m.group(1).strip()), "count": 1,
                    "locationHint": m.group(2).strip()})
        return True

    m = ITEM_QTY.match(clause)
    if m:
        name, count, note = m.group(1).strip(), int(m.group(2)), m.group(3).strip()
        if name in item_names:
            obj = {"kind": "item", "item": C.item_key(name), "count": count}
            if note:
                # trailing prose is a delivery location, not part of the name
                obj["locationHint"] = note
            out.append(obj)
            return True

    if clause in item_names:
        out.append({"kind": "item", "item": C.item_key(clause), "count": 1})
        return True

    out.append({"kind": "freeform", "text": clause})
    return False


def parse(text, item_names):
    """-> (objectives, confidence 0..1, leftover clauses)."""
    if not text:
        return [], 0.0, []
    objectives, leftovers = [], []
    consumed = 0
    for clause in SPLIT.split(text):
        if not clause.strip():
            continue
        before = len(objectives)
        if _clause(clause, item_names, objectives):
            consumed += 1
        else:
            leftovers.append(clause.strip())
        del before
    total = max(1, consumed + len(leftovers))
    confidence = consumed / total if (consumed or leftovers) else 1.0
    return objectives, round(confidence, 3), leftovers


def build():
    bosses = C.raw("bosses.json")
    items = C.raw("items.json")
    item_names = {i["name"] for i in items}

    hunt, review = {}, []
    for b in bosses:
        if b.get("type") != "Boss":
            continue
        key = C.unit_key(b["name"])
        objectives, confidence, leftovers = parse(b.get("conditions"), item_names)
        entry = {
            "target": key,
            "displayName": b["name"],
            "tier": b.get("category"),
            "level": C.as_int(b.get("level")),
            "objectives": objectives,
            "confidence": confidence,
            "rawConditions": b.get("conditions"),
        }
        if b.get("location"):
            entry["location"] = b["location"]
        if b.get("limit") not in (None, "None", ""):
            entry["partyLimit"] = C.as_int(b["limit"])
        hunt[key] = entry
        if confidence < 0.75 and leftovers:
            review.append({"boss": b["name"], "confidence": confidence,
                           "unparsed": leftovers})

    # ---- Chronicle: the scripted world chains, from the research (docs/00 §3.9)
    chronicle = {
        "hell_invasion": {
            "displayName": "The Hell Invasion",
            "steps": [
                {"id": "summon_beriel", "text": "Summon Demon Lord Beriel at East Prius Gate",
                 "requires": {"kind": "boss", "unit": C.unit_key("Demon Lord Beriel")}},
                {"id": "survive_invasion", "text": "Survive the Hell Invasion"},
                {"id": "destroy_portal", "text": "Destroy the demonic portal",
                 "requires": {"kind": "unit", "unit": C.unit_key("Hell Portal")}},
                {"id": "defeat_agareth", "text": "Defeat Underlord Agareth",
                 "requires": {"kind": "boss", "unit": C.unit_key("Underlord Agareth")}},
            ],
        },
        "avalon": {
            "displayName": "The Gates of Avalon",
            "steps": [
                {"id": "gatekeeper", "text": "Defeat the Castle Avalon Gatekeeper",
                 "requires": {"kind": "boss", "unit": C.unit_key("Castle Avalon Gatekeeper")}},
                {"id": "samael", "text": "Defeat Archangel Samael",
                 "requires": {"kind": "boss", "unit": C.unit_key("Archangel Samael")}},
                {"id": "town4", "text": "The portal to Town 4 opens"},
            ],
        },
    }

    data = {
        "NOTE": "Hunt is generated from boss conditions; Forge comes from the recipe "
                "graph at runtime; Chronicle is authored. See docs/01 §7.",
        "hunt": hunt,
        "chronicle": chronicle,
    }
    C.write_lua_table(os.path.join(C.DATA, "codex.lua"), "Codex", data)
    return data, review


if __name__ == "__main__":
    d, review = build()
    from collections import Counter
    hunt = d["hunt"]
    kinds = Counter(o["kind"] for e in hunt.values() for o in e["objectives"])
    full = sum(1 for e in hunt.values() if e["confidence"] >= 0.999)
    print("wrote data/codex.lua")
    print("  Hunt: %d bosses, %d fully structured (%.0f%%)"
          % (len(hunt), full, 100.0 * full / max(1, len(hunt))))
    print("  objective kinds: %s" % dict(kinds))
    print("  Chronicle: %d chains" % len(d["chronicle"]))
    if review:
        print("\n  %d need manual review (confidence < 0.75):" % len(review))
        for r in review[:8]:
            print("    %-30s %.2f  %s" % (r["boss"][:30], r["confidence"], r["unparsed"][:2]))
