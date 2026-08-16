#!/usr/bin/env python3
"""Emit data/stacking.lua — the buff/debuff slot table.

TWRPG's signature balance mechanism (docs/00 §3.2). Effects are grouped into
lettered slots per effect kind. Within a slot only the strongest instance
applies; across slots they multiply. A few are explicitly Stackable and sum.

The developers use slot assignment as the balance lever itself — patch 62v moved
Merchant's specialty debuff out of Type-A specifically so it would stack with
everything else. So the slot must be a data field on every effect, never a
constant in code.

Every named source from buffs.json/debuffs.json is indexed here so an effect can
look up its own slot by name at registration time.
"""
import os
import re

import common as C

# "Sword Enchanter - Power Enchant [E] (Buff) - 5%" -> magnitude 0.05
PCT = re.compile(r"-\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*$")


def parse_source(text):
    """Split a source string into its parts without inventing meaning."""
    entry = {"source": text}
    m = PCT.search(text)
    if m:
        entry["magnitude"] = float(m.group(1)) / 100.0
    if " - " in text:
        entry["owner"] = text.split(" - ", 1)[0].strip()
    if "(Passive)" in text:
        entry["trigger"] = "passive"
    elif "(Active)" in text:
        entry["trigger"] = "active"
    elif "(Buff)" in text:
        entry["trigger"] = "buff"
    return entry


def build():
    slots, index = [], {}

    def ingest(rows, key, polarity):
        for row in rows:
            kind = row[key]
            slot = {
                "kind": kind,
                "slot": row["type"],                    # Type-A/B/C/D or Stackable
                "suffix": row.get("suffix") or "None",  # Fixed vs Percentage matters for AD
                "polarity": polarity,
                "stackable": row["type"] == "Stackable",
                "sources": [parse_source(n) for n in row.get("names", [])],
            }
            slots.append(slot)
            for n in row.get("names", []):
                index.setdefault(n, []).append({"kind": kind, "slot": row["type"],
                                                "polarity": polarity})

    ingest(C.raw("buffs.json"), "bufftype", "buff")
    ingest(C.raw("debuffs.json"), "debufftype", "debuff")

    kinds = {}
    for s in slots:
        kinds.setdefault(s["kind"], []).append(
            {"slot": s["slot"], "suffix": s["suffix"], "stackable": s["stackable"],
             "sourceCount": len(s["sources"])})

    data = {
        "NOTE": "within a (kind, slot) only the strongest applies; across slots they "
                "multiply; Stackable sums. See docs/00 §3.2.",
        "slots": slots,
        "byKind": kinds,
        "bySource": index,
    }
    C.write_lua_table(os.path.join(C.DATA, "stacking.lua"), "Stacking", data)
    return data


if __name__ == "__main__":
    d = build()
    print("wrote data/stacking.lua")
    print("  %d slot definitions across %d effect kinds"
          % (len(d["slots"]), len(d["byKind"])))
    print("  %d named sources indexed" % len(d["bySource"]))
    st = [s for s in d["slots"] if s["stackable"]]
    print("  %d stackable slot(s): %s" % (len(st), [s["kind"] for s in st]))
