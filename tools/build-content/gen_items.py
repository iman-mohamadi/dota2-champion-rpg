#!/usr/bin/env python3
"""Emit npc_items_custom.txt plus data/items.lua and data/recipes.lua.

Split, deliberately:

  npc_items_custom.txt  - only EQUIPMENT (weapon/armour/headwear/accessory/wings).
                          These occupy real Dota item slots, used as the small
                          "equipped" bar per docs/08 §3.2.
  data/items.lua        - all 765 items with their full TWRPG stat blocks.
                          Materials, tokens, icons, coins and misc never become
                          Dota entities; they live only in the custom 24-slot
                          inventory as data.
  data/recipes.lua      - the 486-recipe crafting graph, plus a reverse index.

None of TWRPG's 36 stat fields (skilldamagepercent, the six affinities, proc
damage, ...) have Dota equivalents, so nothing is translated into Dota KV stats.
They are carried verbatim and applied by our own modifier system.
"""
import os

import common as C

# Types that occupy an equipment slot -> (slot, weapon class or None)
EQUIPMENT = {
    "Weapon (Melee)": ("weapon", "melee"),
    "Weapon (Staff)": ("weapon", "staff"),
    "Weapon (Gun)": ("weapon", "gun"),
    "Weapon (Bow)": ("weapon", "bow"),
    "Weapon (Bag)": ("weapon", "bag"),
    "Weapon (Shared)": ("weapon", "shared"),
    "Armor": ("armor", None),
    "Headwear": ("headwear", None),
    "Accessory": ("accessory", None),
    "Wings": ("wings", None),
}

# grade -> tier name, confirmed in docs/00 §3.4 and in the map's own item text
GRADE_NAME = {0: None, 1: "Deltirama", 2: "Neptinos", 3: "Gnosis", 4: "Alteia", 5: "Arcana"}
# cosmetic only: Dota's item colour band
GRADE_QUALITY = {0: "common", 1: "rare", 2: "epic", 3: "epic", 4: "artifact", 5: "artifact"}

ITEM_ID_BASE = 5000


def normalise_type(t):
    """Upstream has both 'Headwear' (75) and 'headwear' (2)."""
    t = (t or "").strip()
    return "Headwear" if t.lower() == "headwear" else t


def build():
    items = C.raw("items.json")

    kv, lua = {}, {}
    # Deterministic ids: sorted by generated key so a rebuild is reproducible.
    ordered = sorted(items, key=lambda i: C.item_key(i["name"]))
    ids = {i["name"]: ITEM_ID_BASE + n for n, i in enumerate(ordered)}

    for it in items:
        name = it["name"]
        key = C.item_key(name)
        itype = normalise_type(it.get("type"))
        stats = it.get("stats") or {}
        slot, weapon_class = EQUIPMENT.get(itype, (None, None))

        entry = {
            "displayName": name,
            "type": itype,
            "rank": it.get("rank"),
            "grade": it.get("grade", 0),
            "equipSlot": slot,
        }
        if GRADE_NAME.get(it.get("grade", 0)):
            entry["tier"] = GRADE_NAME[it["grade"]]
        if weapon_class:
            entry["weaponClass"] = weapon_class
        if it.get("level"):
            entry["levelRequirement"] = C.as_int(it["level"])
        if it.get("droprate") is not None:
            entry["dropRate"] = it["droprate"]
        if it.get("dropped_by"):
            entry["droppedBy"] = it["dropped_by"]
        if it.get("worth"):
            entry["worth"] = C.num(it["worth"])

        # numeric stats verbatim; effect text kept for the ability pass
        numeric = {k: v for k, v in stats.items()
                   if isinstance(v, (int, float))}
        if numeric:
            entry["stats"] = numeric
        for effect in ("passive", "active", "spec"):
            if stats.get(effect):
                entry[effect] = stats[effect]
        if it.get("notes"):
            entry["notes"] = it["notes"]
        lua[key] = entry

        if slot is None:
            continue  # materials/tokens/icons stay data-only

        kv[key] = {
            "ID": ids[name],
            "BaseClass": "item_lua",
            "ScriptFile": "items/equipment_generic.lua",
            "AbilityTextureName": "item_recipe",
            "ItemQuality": GRADE_QUALITY.get(it.get("grade", 0), "common"),
            "ItemShopTags": itype.lower().replace(" ", "_").replace("(", "").replace(")", ""),
            "ItemCost": 0,
            "ItemPurchasable": 0,
            "ItemSellable": 0,
            "ItemDroppable": 1,
            "ItemStackable": 0,
            "ItemPermanent": 1,
            "ItemInitialCharges": 0,
            "MaxUpgradeLevel": 0,
            "AbilityBehavior": ("DOTA_ABILITY_BEHAVIOR_PASSIVE | DOTA_ABILITY_BEHAVIOR_NO_TARGET"
                                if stats.get("active") else "DOTA_ABILITY_BEHAVIOR_PASSIVE"),
        }

    # ---- recipes -----------------------------------------------------------
    recipes, used_in = {}, {}
    for it in items:
        if not it.get("recipe"):
            continue
        comps = []
        for step in it["recipe"]:
            for comp, qty in step.items():
                comps.append({"item": C.item_key(comp), "count": C.as_int(qty, 1)})
        rkey = C.item_key(it["name"])
        recipes[rkey] = {"result": rkey, "components": comps}
        for c in comps:
            used_in.setdefault(c["item"], []).append(rkey)

    C.write_kv(os.path.join(C.NPC, "npc_items_custom.txt"), "DOTAAbilities", kv)
    C.write_lua_table(os.path.join(C.DATA, "items.lua"), "Items", lua)
    C.write_lua_table(os.path.join(C.DATA, "recipes.lua"), "Recipes",
                      {"recipes": recipes, "usedIn": used_in})
    return kv, lua, recipes


if __name__ == "__main__":
    kv, lua, rec = build()
    from collections import Counter
    print("wrote npc_items_custom.txt (%d equippable), data/items.lua (%d total), "
          "data/recipes.lua (%d recipes)" % (len(kv), len(lua), len(rec)))
    print("  by slot: %s" % dict(Counter(v.get("equipSlot") or "(data only)"
                                         for v in lua.values())))
    print("  by tier: %s" % dict(Counter(v.get("tier") or "(base)" for v in lua.values())))
