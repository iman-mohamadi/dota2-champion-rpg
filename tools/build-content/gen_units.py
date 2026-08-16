#!/usr/bin/env python3
"""Emit npc_units_custom.txt plus a companion Lua stat table for all monsters.

Two outputs, deliberately:

  npc_units_custom.txt  - the minimum Dota needs to register and spawn the unit
  data/units.lua        - every TWRPG-specific stat the engine has no concept of

The split matters for armour. TWRPG mitigates with 1/(1 + 0.02*armor); Dota uses
its own curve with a different coefficient. So Dota's ArmorPhysical is pinned to
0 and the real armour value lives in units.lua, where core/damage.lua applies the
recovered formula. Writing TWRPG armour into ArmorPhysical would silently apply
Dota's curve on top and mis-tune every encounter. See docs/08 §3.1.
"""
import os

import common as C

# Models are the one thing extraction cannot give us: the originals are Blizzard
# assets and cannot ship. Every unit gets this placeholder until real Dota models
# are assigned (needs the Workshop Tools asset browser -- a Windows task).
PLACEHOLDER_MODEL = "models/development/invisiblebox.vmdl"

ARMOR_TYPE_MAP = {"light": "Light", "medium": "Medium", "heavy": "Heavy",
                  "fort": "Fortified", "small": "Light", "large": "Heavy",
                  "hero": "Hero", "divine": "Divine", "none": "None"}


def creep_xp(level, k):
    return k["A"] * level * level + k["B"] * level + k["C"]


def build(constants):
    bosses = C.raw("bosses.json")
    items_by_id = {i["id"]: i["name"] for i in C.raw("items.json")}
    xp_k = constants["CREEP_XP"]

    kv, lua = {}, {}
    for b in bosses:
        name = b["name"]
        key = C.unit_key(name)
        s = b.get("stats") or {}
        level = C.as_int(b.get("level"), 1)

        # TWRPG stores attacks-per-second; Dota wants seconds-per-attack.
        aps = C.num(s.get("attackSpeed"), 1.0)
        attack_rate = (1.0 / aps) if aps > 0 else 1.0
        dmg_min = C.as_int(s.get("attackDamage"))
        dmg_max = dmg_min + C.as_int(s.get("attackSpread"))
        rng = C.as_int(s.get("attackRange"))
        melee = rng <= 128

        kv[key] = {
            "BaseClass": "npc_dota_creature",
            "Model": PLACEHOLDER_MODEL,
            "SoundSet": "",
            "Level": level,
            "ModelScale": 1.0,
            "AttackCapabilities": ("DOTA_UNIT_CAP_MELEE_ATTACK" if melee
                                   else "DOTA_UNIT_CAP_RANGED_ATTACK"),
            "AttackDamageMin": dmg_min,
            "AttackDamageMax": dmg_max,
            "AttackRate": C.fmt(round(attack_rate, 4)),
            "AttackAnimationPoint": 0.3,
            "AttackAcquisitionRange": max(600, rng + 200),
            "AttackRange": max(128, rng),
            "AttackDamageType": "DAMAGE_TYPE_ArmorPhysical",
            # Pinned to 0 on purpose -- see module docstring.
            "ArmorPhysical": 0,
            "MagicalResistance": C.as_int(s.get("magicResist")),
            "MovementCapabilities": "DOTA_UNIT_CAP_MOVE_GROUND",
            "MovementSpeed": min(550, C.as_int(s.get("moveSpeed"), 300)),
            "MovementTurnRate": 0.5,
            "StatusHealth": C.as_int(s.get("health"), 1),
            "StatusHealthRegen": C.fmt(C.num(s.get("healthRegen"))),
            "StatusMana": C.as_int(s.get("mana")),
            "StatusManaRegen": C.fmt(C.num(s.get("manaRegen"))),
            "VisionDaytimeRange": 800,
            "VisionNighttimeRange": 800,
            "TeamName": "DOTA_TEAM_BADGUYS",
            "CombatClassAttack": "DOTA_COMBAT_CLASS_ATTACK_BASIC",
            "CombatClassDefend": "DOTA_COMBAT_CLASS_DEFEND_BASIC",
            "UnitRelationshipClass": "DOTA_NPC_UNIT_RELATIONSHIP_TYPE_DEFAULT",
            "BountyXP": int(round(creep_xp(level, xp_k))),
            "BountyGoldMin": level * 2,
            "BountyGoldMax": level * 3,
            "IsAncient": 1 if b.get("type") == "Boss" else 0,
        }

        entry = {
            "displayName": name,
            "level": level,
            "category": b.get("category"),
            "kind": b.get("type"),
            # the stats Dota has no equivalent for
            "armor": C.num(s.get("armor")),
            "armorType": ARMOR_TYPE_MAP.get(str(s.get("armorType", "")).lower(), "None"),
            "magicResist": C.num(s.get("magicResist")),
            "damageResist": C.num(s.get("damageResist")),
            "attackSpeed": aps,
        }
        for field, out in (("limit", "partyLimit"), ("respawn", "respawnMinutes"),
                           ("timer", "enrageTimer")):
            v = b.get(field)
            if v not in (None, "None", ""):
                entry[out] = C.num(v)
        for field in ("location", "conditions", "quote"):
            if b.get(field):
                entry[field] = b[field]
        if b.get("spells"):
            entry["spells"] = b["spells"]
        if b.get("minions"):
            entry["minions"] = [C.unit_key(m) for m in b["minions"]]
        if b.get("drops"):
            entry["drops"] = [C.item_key(items_by_id[d]) for d in b["drops"] if d in items_by_id]
        if b.get("empoweredStats"):
            entry["empowered"] = {k: C.num(v) for k, v in b["empoweredStats"].items()}
        lua[key] = entry

    C.write_kv(os.path.join(C.NPC, "npc_units_custom.txt"), "DOTAUnits", kv)
    C.write_lua_table(os.path.join(C.DATA, "units.lua"), "Units", lua)
    return kv, lua


if __name__ == "__main__":
    from gen_constants import build as build_constants
    _, consts = build_constants()
    kv, lua = build(consts)
    print("wrote npc_units_custom.txt (%d units) and data/units.lua" % len(kv))
    bosses = [k for k, v in lua.items() if v["kind"] == "Boss"]
    print("  %d bosses, %d with drop tables, %d with spell lists"
          % (len(bosses), sum(1 for v in lua.values() if v.get("drops")),
             sum(1 for v in lua.values() if v.get("spells"))))
