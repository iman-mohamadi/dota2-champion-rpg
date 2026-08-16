#!/usr/bin/env python3
"""Emit npc_abilities_custom.txt stubs plus data/abilities.lua for hero skills.

Keys are class+name, not name: 'Recall' exists on four classes and 'Purify' on
two, so name alone collides. class+name is collision-free across all 372.

Each ability gets a KV stub so Dota can register it and a data entry carrying
everything we know — hotkey, sub-menu parent, cooldown, effect text, and where
available the handler and coefficients recovered from the original script
(docs/06-ABILITY-HANDLER-MAP.md).

The stubs are NOT implementations. Every one points at a shared placeholder
script until its Lua is written; the data entry is the spec to write it from.
"""
import os
import re

import common as C

# "[T] → [W]" means: press T to enter a form, then W. The arrow is the sub-menu
# marker; the original swaps the whole bar via SwapAbilities (docs/08 §2).
ARROW = re.compile(r"\s*(?:→|->)\s*")
KEY_RX = re.compile(r"\[([^\]]+)\]")


def parse_hotkey(hotkey):
    """'[T] → [W]' -> (['T','W'], depth 1). '[Q]' -> (['Q'], 0)."""
    parts = [p for p in ARROW.split(hotkey or "") if p.strip()]
    keys = []
    for p in parts:
        m = KEY_RX.search(p)
        keys.append(m.group(1).strip() if m else p.strip())
    return keys, max(0, len(keys) - 1)


def ability_id(hero_class, name):
    return "twrpg_%s_%s" % (C.slug(hero_class), C.slug(name))


def build():
    skills = C.raw("skills.json")
    handlers = {}
    for row in C.extracted("ability_map.json"):
        if row.get("heroClass") and row.get("rawcode"):
            handlers.setdefault(row["rawcode"], []).append(row)

    kv, lua = {}, {}
    for s in skills:
        key = ability_id(s["heroClass"], s["name"])
        keys, depth = parse_hotkey(s.get("hotkey"))
        primary = keys[0] if keys else ""
        is_passive = primary.lower().startswith("passive")

        entry = {
            "displayName": s["name"],
            "heroClass": s["heroClass"],
            "order": s.get("order", 0),
            "hotkey": s.get("hotkey"),
            "keys": keys,
            "submenuDepth": depth,
            "passive": is_passive,
        }
        if depth:
            entry["parentKey"] = keys[0]
        if s.get("cooldown") is not None:
            entry["cooldown"] = C.num(s["cooldown"])
        if s.get("proc_rate") is not None:
            entry["procRate"] = C.num(s["proc_rate"])
        for field in ("active", "passive", "toggle"):
            if s.get(field):
                entry["text_" + field] = s[field]

        # everything the script recovery gave us for this rawcode
        rows = handlers.get(s["id"], [])
        if rows:
            entry["rawcode"] = s["id"]
            entry["handlers"] = sorted({r["handler"] for r in rows})
            events = sorted({e for r in rows for e in (r.get("events") or [])})
            if events:
                entry["events"] = events
            formulas = []
            for r in rows:
                formulas.extend(r.get("statFormulas") or [])
            if formulas:
                entry["recoveredFormulas"] = sorted(set(formulas))[:8]
        lua[key] = entry

        behavior = ("DOTA_ABILITY_BEHAVIOR_PASSIVE" if is_passive
                    else "DOTA_ABILITY_BEHAVIOR_NO_TARGET")
        kv[key] = {
            "BaseClass": "ability_lua",
            "ScriptFile": "abilities/placeholder_ability.lua",
            "AbilityTextureName": "ability_placeholder",
            "MaxLevel": 1,
            "AbilityBehavior": behavior,
            "AbilityCooldown": C.fmt(entry.get("cooldown", 0)),
            "AbilityManaCost": 0,
            # Sub-menu abilities start hidden; the form ability swaps them in.
            "AbilityType": "DOTA_ABILITY_TYPE_BASIC",
        }
        if depth:
            kv[key]["AbilityBehavior"] = behavior + " | DOTA_ABILITY_BEHAVIOR_HIDDEN"

    C.write_kv(os.path.join(C.NPC, "npc_abilities_custom.txt"), "DOTAAbilities", kv)
    C.write_lua_table(os.path.join(C.DATA, "abilities.lua"), "Abilities", lua)
    return kv, lua


if __name__ == "__main__":
    kv, lua = build()
    n_sub = sum(1 for v in lua.values() if v["submenuDepth"])
    n_h = sum(1 for v in lua.values() if v.get("handlers"))
    n_f = sum(1 for v in lua.values() if v.get("recoveredFormulas"))
    print("wrote npc_abilities_custom.txt and data/abilities.lua (%d abilities)" % len(lua))
    print("  %d sub-menu abilities (need SwapAbilities)" % n_sub)
    print("  %d mapped to an original handler, %d with recovered formulas" % (n_h, n_f))
