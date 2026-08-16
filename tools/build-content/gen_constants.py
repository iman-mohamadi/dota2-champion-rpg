#!/usr/bin/env python3
"""Emit the recovered TWRPG gameplay constants as a Lua module.

Source: research/extracted/curves.json, itself derived from the map's
war3mapMisc.txt (see docs/05-COMBAT-FORMULAS.md).

These values are not tuning knobs we invented — they are the original game's
constants, recovered exactly and cross-checked against the changelog.
"""
import os

import common as C

# war3mapMisc key -> Dota AttributeDerivedStats enum member.
# Verified 1:1 against ModDota's dota-enums.d.ts; see docs/08 §1.
ATTR_MAP = {
    "StrHitPointBonus": "DOTA_ATTRIBUTE_STRENGTH_HP",
    "StrRegenBonus": "DOTA_ATTRIBUTE_STRENGTH_HP_REGEN_PERCENT",
    "AgiDefenseBonus": "DOTA_ATTRIBUTE_AGILITY_ARMOR",
    "AgiAttackSpeedBonus": "DOTA_ATTRIBUTE_AGILITY_ATTACK_SPEED",
    "AgiMoveBonus": "DOTA_ATTRIBUTE_AGILITY_MOVE_SPEED_PERCENT",
    "IntManaBonus": "DOTA_ATTRIBUTE_INTELLIGENCE_MANA",
    "IntRegenBonus": "DOTA_ATTRIBUTE_INTELLIGENCE_MANA_REGEN_PERCENT",
}


def build():
    c = C.extracted("curves.json")

    # SetCustomXPRequiredToReachNextLevel wants cumulative XP indexed by level.
    # Level 1 costs nothing; level N needs the cumulative total from the curve.
    xp = {1: 0}
    for row in c["xpCurve"]["table"]:
        xp[int(row["toLevel"])] = int(round(row["cumulativeXp"]))
    max_level = int(c["maxHeroLevel"])
    assert len(xp) == max_level, "xp table has %d rows, expected %d" % (len(xp), max_level)
    assert xp[max_level] == int(round(c["xpCurve"]["totalXpToMax"]))

    attrs = []
    for key, enum in ATTR_MAP.items():
        attrs.append({"key": key, "enum": enum,
                      "value": C.num(c["attributeBonusesDisabled"].get(key, 0))})
    # The one attribute effect TWRPG leaves on: primary attribute -> attack damage.
    for enum in ("DOTA_ATTRIBUTE_STRENGTH_DAMAGE", "DOTA_ATTRIBUTE_AGILITY_DAMAGE",
                 "DOTA_ATTRIBUTE_INTELLIGENCE_DAMAGE"):
        attrs.append({"key": "StrAttackBonus", "enum": enum,
                      "value": C.num(c["primaryAttributeAttackBonus"], 1.0)})

    data = {
        "SOURCE": "recovered from war3mapMisc.txt + war3map.j; see docs/05-COMBAT-FORMULAS.md",
        "MAX_HERO_LEVEL": max_level,
        "MAX_UNIT_LEVEL": int(c["maxUnitLevel"]),
        "TOTAL_XP_TO_MAX": xp[max_level],
        # Need(L) = 1650 * 1.05^(L-1) - 1500  (docs/05 §2)
        "XP_PER_LEVEL": [xp[i] for i in range(1, max_level + 1)],
        "XP_FORMULA": {
            "base": C.num(c["xpCurve"]["formula"]["base"]),
            "A": C.num(c["xpCurve"]["formula"]["A"]),
            "B": C.num(c["xpCurve"]["formula"]["B"]),
        },
        # XP granted for killing a unit of level L: A*L^2 + B*L + C
        "CREEP_XP": {"A": 0.85, "B": 2.0, "C": 2.0},
        # damage * 1/(1 + k*armor) for armor >= 0; 2 - 0.94^(-armor) below zero.
        "ARMOR_K": C.num(c["armor"]["DefenseArmor"]),
        "ARMOR_NEGATIVE_BASE": 0.94,
        "STAT_POINTS_TOTAL": 697,
        "HERO_BASE_HP": 500,
        "HERO_BASE_MOVESPEED": 500,
        "ATTRIBUTE_DERIVED": attrs,
        "MISC": {k: C.num(v) for k, v in c["misc"].items() if k != "GlobalExperience"},
    }

    path = os.path.join(C.DATA, "constants.lua")
    C.write_lua_table(path, "Constants", data)
    return path, data


if __name__ == "__main__":
    p, d = build()
    print("wrote %s" % os.path.relpath(p, C.ROOT))
    print("  max level %d, total XP %s, armor k=%s"
          % (d["MAX_HERO_LEVEL"], format(d["TOTAL_XP_TO_MAX"], ","), d["ARMOR_K"]))
    print("  XP_PER_LEVEL[1..5] = %s ... [100] = %s"
          % (d["XP_PER_LEVEL"][:5], d["XP_PER_LEVEL"][-1]))
    print("  %d attribute-derived overrides" % len(d["ATTRIBUTE_DERIVED"]))
