#!/usr/bin/env python3
"""Emit npc_heroes_custom.txt, herolist.txt and data/heroes.lua for the 37 classes.

Base stats come from the extracted map data, not from guesswork: every TWRPG
hero is 500 HP / 500 move speed with *zero* per-level attribute growth
(docs/04 §4). All power comes from the 697 allocated stat points and equipment,
which is why the growth fields below are all 0.0.

`override_hero` is PROVISIONAL. It borrows a stock Dota hero's model, rig and
animations. The mapping here is chosen only by primary attribute and melee/ranged
so it is mechanically sane; it is not an art direction. Reviewing it needs the
Workshop Tools asset browser, i.e. a Windows session.
"""
import os

import common as C

ATTR = {"STR": "DOTA_ATTRIBUTE_STRENGTH",
        "AGI": "DOTA_ATTRIBUTE_AGILITY",
        "INT": "DOTA_ATTRIBUTE_INTELLECT"}

# PROVISIONAL model donors — long-standing Dota heroes only, matched by primary
# attribute and rough archetype. Replace after reviewing in the asset browser.
OVERRIDE_HERO = {
    # STR
    "Crusader": "npc_dota_hero_omniknight", "Lancer": "npc_dota_hero_legion_commander",
    "Merchant": "npc_dota_hero_alchemist", "Berserker": "npc_dota_hero_axe",
    "Knight": "npc_dota_hero_dragon_knight", "Dark Knight": "npc_dota_hero_abaddon",
    "Paladin": "npc_dota_hero_omniknight", "Fighter": "npc_dota_hero_ursa",
    "Lightseeker": "npc_dota_hero_dawnbreaker", "Blaster": "npc_dota_hero_gyrocopter",
    "Sword Saint": "npc_dota_hero_kunkka",
    # AGI
    "Sniper": "npc_dota_hero_sniper", "Shooter": "npc_dota_hero_clinkz",
    "Sword Enchanter": "npc_dota_hero_juggernaut", "Gunner": "npc_dota_hero_gyrocopter",
    "Swordsman": "npc_dota_hero_juggernaut", "Martial Artist": "npc_dota_hero_ember_spirit",
    "Reaper": "npc_dota_hero_phantom_assassin", "Assassin": "npc_dota_hero_riki",
    "Thunderer": "npc_dota_hero_razor", "Bow Master": "npc_dota_hero_drow_ranger",
    "Phantom Blade": "npc_dota_hero_templar_assassin", "Hermit": "npc_dota_hero_monkey_king",
    "Trickster": "npc_dota_hero_bounty_hunter",
    # INT
    "Soul Weaver": "npc_dota_hero_death_prophet", "Alchemist": "npc_dota_hero_tinker",
    "Warlock": "npc_dota_hero_warlock", "Blood Weaver": "npc_dota_hero_bloodseeker",
    "Fire Mage": "npc_dota_hero_lina", "Elementalist": "npc_dota_hero_enigma",
    "Lightning Mage": "npc_dota_hero_zuus", "Wind Mage": "npc_dota_hero_windrunner",
    "Arcane Mage": "npc_dota_hero_pugna", "Water Mage": "npc_dota_hero_crystal_maiden",
    "Priest": "npc_dota_hero_dazzle", "Witch": "npc_dota_hero_witch_doctor",
    "Shrine Priestess": "npc_dota_hero_oracle",
}
FALLBACK = {"STR": "npc_dota_hero_axe", "AGI": "npc_dota_hero_juggernaut",
            "INT": "npc_dota_hero_lina"}

# Dota exposes 16 usable ability slots per unit; TWRPG's biggest kits reach 29
# via sub-menus, which are swapped in at runtime rather than occupying slots.
MAX_KV_ABILITIES = 16


def build(constants):
    heroes = C.raw("heros.json")
    skills = C.raw("skills.json")
    map_units = {u["id"]: u for u in C.extracted("units.json")}

    from gen_abilities import ability_id, parse_hotkey

    by_class = {}
    for s in skills:
        by_class.setdefault(s["heroClass"], []).append(s)

    kv, lua, herolist = {}, {}, {}
    for h in heroes:
        cls = h["heroClass"]
        key = C.hero_key(cls)
        mods = (map_units.get(h["id"]) or {}).get("mods", {})

        ordered = sorted(by_class.get(cls, []), key=lambda s: s.get("order", 0))
        # Only top-level abilities take a KV slot; sub-menu entries are swapped in.
        top = [s for s in ordered if parse_hotkey(s.get("hotkey"))[1] == 0]
        sub = [s for s in ordered if parse_hotkey(s.get("hotkey"))[1] > 0]

        block = {
            "override_hero": OVERRIDE_HERO.get(cls, FALLBACK[h["mainstat"]]),
            "BaseClass": "npc_dota_hero",
            "AttributePrimary": ATTR[h["mainstat"]],
            "AttributeBaseStrength": C.as_int(mods.get("strength"), 1),
            "AttributeStrengthGain": "0.0",
            "AttributeBaseAgility": C.as_int(mods.get("agility"), 1),
            "AttributeAgilityGain": "0.0",
            "AttributeBaseIntelligence": C.as_int(mods.get("intelligence"), 1),
            "AttributeIntelligenceGain": "0.0",
            "StatusHealth": constants["HERO_BASE_HP"],
            "StatusHealthRegen": 0,
            "StatusMana": C.as_int(mods.get("manaMax"), 0),
            "StatusManaRegen": 0,
            "ArmorPhysical": 0,
            "MagicalResistance": 0,
            "MovementSpeed": constants["HERO_BASE_MOVESPEED"],
            "AttackRate": C.fmt(C.num(mods.get("atk1Cooldown"), 1.0)),
            "AttackRange": C.as_int(mods.get("atk1Range"), 128),
            "AttackDamageMin": C.as_int(mods.get("atk1BaseDamage"), 1),
            "AttackDamageMax": C.as_int(mods.get("atk1BaseDamage"), 1)
                               + C.as_int(mods.get("atk1DiceSides"), 0),
            "AttackCapabilities": ("DOTA_UNIT_CAP_RANGED_ATTACK"
                                   if C.as_int(mods.get("atk1Range"), 128) > 128
                                   else "DOTA_UNIT_CAP_MELEE_ATTACK"),
            "TeamName": "DOTA_TEAM_GOODGUYS",
        }
        for n, s in enumerate(top[:MAX_KV_ABILITIES], start=1):
            block["Ability%d" % n] = ability_id(cls, s["name"])
        kv[key] = block
        herolist[key] = 1

        lua[key] = {
            "displayName": cls,
            "mainStat": h["mainstat"],
            "roles": h.get("role", []),
            "description": h.get("description", []),
            "wearable": [w.replace("Weapon (", "").replace(")", "").lower()
                         for w in h.get("wearable", [])],
            "specialtyItems": h.get("spec", []),
            "abilities": [ability_id(cls, s["name"]) for s in ordered],
            "topLevelAbilities": [ability_id(cls, s["name"]) for s in top],
            "submenuAbilities": [ability_id(cls, s["name"]) for s in sub],
            "overrideHeroProvisional": block["override_hero"],
        }
        if h.get("secondary"):
            lua[key]["secondary"] = h["secondary"]

    C.write_kv(os.path.join(C.NPC, "npc_heroes_custom.txt"), "DOTAHeroes", kv)
    C.write_kv(os.path.join(C.NPC, "herolist.txt"), "CustomHeroList", {},
               header=C.GENERATED_HEADER)
    # herolist is a flat key/value block, not nested — write it directly
    with open(os.path.join(C.NPC, "herolist.txt"), "w", encoding="utf-8") as f:
        f.write(C.GENERATED_HEADER + '\n"CustomHeroList"\n{\n')
        for k in sorted(herolist):
            f.write('\t"%s"\t"1"\n' % k)
        f.write("}\n")

    C.write_lua_table(os.path.join(C.DATA, "heroes.lua"), "Heroes", lua)
    return kv, lua


if __name__ == "__main__":
    from gen_constants import build as build_constants
    _, consts = build_constants()
    kv, lua = build(consts)
    print("wrote npc_heroes_custom.txt, herolist.txt, data/heroes.lua (%d classes)" % len(kv))
    over = sum(1 for v in lua.values() if len(v["topLevelAbilities"]) > MAX_KV_ABILITIES)
    print("  %d classes exceed %d KV ability slots (sub-menus cover the rest)"
          % (over, MAX_KV_ABILITIES))
    print("  %d sub-menu abilities across all classes"
          % sum(len(v["submenuAbilities"]) for v in lua.values()))
