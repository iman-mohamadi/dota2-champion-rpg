#!/usr/bin/env python3
"""Parse Warcraft III custom object data (.w3u .w3t .w3a .w3h .w3b .w3d .w3q).

These files hold the map's real numeric definitions: unit HP/armor/damage,
item stats, ability cooldowns/durations/effects, per level. They are not
touched by script obfuscation.

Usage: python3 parse_objects.py <extracted_dir> <out_dir>
"""
import json
import os
import struct
import sys

# files that carry per-level/variation data on each modification
LEVELED = {".w3a", ".w3b", ".w3d", ".w3q"}

FILES = [
    ("war3map.w3u", "units"),
    ("war3map.w3t", "items"),
    ("war3map.w3a", "abilities"),
    ("war3map.w3h", "buffs"),
    ("war3map.w3b", "destructibles"),
    ("war3map.w3d", "doodads"),
    ("war3map.w3q", "upgrades"),
]

# Well-known modification ids -> readable names. Raw ids are always preserved
# alongside, so an unmapped id is never lost.
FIELD_NAMES = {
    # --- units
    "unam": "name", "unsf": "nameSuffix", "utip": "tooltip", "utub": "tooltipExtended",
    "uhpm": "hpMax", "uhpr": "hpRegen", "umpm": "manaMax", "umpr": "manaRegen",
    "umpi": "manaInitial", "udef": "armor", "udty": "armorType", "udea": "deathTime",
    "ulev": "level", "urac": "race", "ubld": "buildTime", "usnd": "soundSet",
    "umvs": "moveSpeed", "umvh": "moveHeight", "umas": "moveSpeedMax", "umis": "moveSpeedMin",
    "umvt": "moveType", "umvr": "turnRate",
    "ua1b": "atk1BaseDamage", "ua1d": "atk1DiceCount", "ua1s": "atk1DiceSides",
    "ua1c": "atk1Cooldown", "ua1r": "atk1Range", "ua1t": "atk1TargetType",
    "ua1z": "atk1AttackType", "ua1g": "atk1WeaponType", "ua1p": "atk1ProjectileArt",
    "ua1f": "atk1AreaFull", "ua1h": "atk1AreaMid", "ua1q": "atk1AreaSmall",
    "ua2b": "atk2BaseDamage", "ua2d": "atk2DiceCount", "ua2s": "atk2DiceSides",
    "ua2c": "atk2Cooldown", "ua2r": "atk2Range", "ua2t": "atk2TargetType",
    "uaen": "attacksEnabled", "uabi": "abilities", "udaa": "defaultActiveAbility",
    "uhab": "heroAbilities", "upgr": "upgradesUsed", "utyp": "unitClassification",
    "ucar": "cargoCapacity", "ufoo": "foodCost", "ugol": "goldCost", "ulum": "lumberCost",
    "usca": "scale", "umdl": "model", "uico": "icon", "ussc": "selectionScale",
    "usid": "sightRadiusDay", "usin": "sightRadiusNight",
    "ustr": "strength", "uagi": "agility", "uint": "intelligence",
    "ustp": "strPerLevel", "uagp": "agiPerLevel", "uinp": "intPerLevel",
    "upra": "primaryAttribute", "uhrt": "heroRequiredTier", "ureq": "requirements",
    "ucol": "collisionSize", "urpp": "pointValue", "uisz": "isBuilding",
    "uspa": "specialArt", "utar": "targetedAs", "urtm": "repairTime",
    # --- items
    "unam_i": "name", "inam": "name", "ides": "description", "iubt": "tooltipExtended",
    "iutp": "tooltip", "ilev": "level", "ilvo": "levelUnclassified",
    "iabi": "abilities", "igol": "goldCost", "ilum": "lumberCost",
    "ihtp": "hitPoints", "iusen": "usesDisabled", "iuse": "uses",
    "icid": "classification", "ipri": "priority", "istr": "stockStartDelay",
    "isto": "stockMax", "istr_r": "stockRegen", "ipow": "powerup",
    "iper": "perishable", "idrp": "droppedWhenCarrierDies", "idro": "canBeDropped",
    "ipaw": "pawnable", "imor": "morph", "isca": "scale", "ifil": "model",
    "iico": "icon", "icol": "colour", "ussc_i": "selectionSize",
    # --- abilities
    "anam": "name", "ansf": "editorSuffix", "atat": "targetsAllowed",
    "aran": "castRange", "acdn": "cooldown", "amcs": "manaCost",
    "adur": "duration", "ahdu": "durationHero", "acas": "castingTime",
    "aare": "areaOfEffect", "abuf": "buffs", "aeff": "effects",
    "alev": "levels", "arac": "race", "ahky": "hotkey", "aher": "isHero",
    "aite": "itemAbility", "atp1": "tooltipLearn", "aut1": "tooltipLearnExtended",
    "atp2": "tooltipNormal", "aub1": "tooltipNormalExtended",
    "art1": "researchTip", "arf1": "researchTipExtended",
    "aart": "icon", "auar": "areaEffectArt", "acat": "casterArt",
    "atar": "targetArt", "aspe": "specialArt", "amat": "missileArt",
    "amsp": "missileSpeed", "amac": "missileArc", "amho": "missileHoming",
    "Ncl1": "damage", "Idam": "damage", "Hbz1": "damagePerSecond",
    "Ncl2": "damageBonus", "Idps": "damagePerSecond",
    # generic ability data fields (DataA..DataI per level)
    "aani": "animationNames", "abpx": "buttonPosX", "abpy": "buttonPosY",
    # --- buffs
    "fnam": "name", "ftip": "tooltip", "fube": "tooltipExtended",
    "feff": "effectArt", "fart": "icon", "ftat": "targetArt",
    # --- destructibles
    "bnam": "name", "bhps": "hitPoints", "barm": "armorType", "bvar": "variations",
    "brad": "radius", "bfil": "model", "bsel": "selectionSize",
}

VAR_TYPE = {0: "int", 1: "real", 2: "unreal", 3: "string"}


def cstr(d, off):
    e = d.index(b"\0", off)
    return d[off:e].decode("utf-8", "replace"), e + 1


def parse_table(d, off, version, leveled, out, custom):
    count, = struct.unpack("<I", d[off:off + 4])
    off += 4
    for _ in range(count):
        orig = d[off:off + 4].decode("latin-1"); off += 4
        new = d[off:off + 4].decode("latin-1"); off += 4
        if version >= 3:
            nsets, = struct.unpack("<I", d[off:off + 4]); off += 4
        else:
            nsets = 1
        obj = {"baseId": orig, "id": (new.strip("\x00") or orig), "custom": custom,
               "mods": {}, "rawMods": {}}
        for _s in range(nsets):
            if version >= 3:
                nmod_sets, = struct.unpack("<I", d[off:off + 4]); off += 4
                off += nmod_sets * 4  # applicable-object ids, unused here
            nmods, = struct.unpack("<I", d[off:off + 4]); off += 4
            for _m in range(nmods):
                mid = d[off:off + 4].decode("latin-1"); off += 4
                vtype, = struct.unpack("<I", d[off:off + 4]); off += 4
                level = dptr = None
                if leveled:
                    level, dptr = struct.unpack("<iI", d[off:off + 8]); off += 8
                if vtype == 0:
                    val, = struct.unpack("<i", d[off:off + 4]); off += 4
                elif vtype in (1, 2):
                    val, = struct.unpack("<f", d[off:off + 4]); off += 4
                    val = round(val, 6)
                elif vtype == 3:
                    val, off = cstr(d, off)
                else:
                    raise ValueError("bad var type %d at %d" % (vtype, off))
                off += 4  # end-of-mod marker
                key = FIELD_NAMES.get(mid, mid)
                slot = obj["mods"] if mid in FIELD_NAMES else obj["rawMods"]
                if leveled and level:
                    slot.setdefault(key, {})[str(level)] = val
                else:
                    if key in slot and not isinstance(slot[key], dict):
                        slot.setdefault("_dup_" + key, []).append(val)
                    else:
                        slot[key] = val
        out.append(obj)
    return off


def parse_file(path):
    d = open(path, "rb").read()
    version, = struct.unpack("<I", d[:4])
    leveled = os.path.splitext(path)[1].lower() in LEVELED
    objs = []
    off = 4
    off = parse_table(d, off, version, leveled, objs, custom=False)
    if off < len(d):
        parse_table(d, off, version, leveled, objs, custom=True)
    return version, objs


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    summary = {}
    for fname, label in FILES:
        p = os.path.join(src, fname)
        if not os.path.exists(p):
            print("  -- %s missing" % fname)
            continue
        try:
            version, objs = parse_file(p)
        except Exception as e:
            print("  !! %s failed: %s: %s" % (fname, type(e).__name__, e))
            continue
        dest = os.path.join(out, label + ".json")
        with open(dest, "w") as f:
            json.dump(objs, f, indent=1, ensure_ascii=False)
        named = sum(1 for o in objs if "name" in o["mods"])
        custom = sum(1 for o in objs if o["custom"])
        summary[label] = {"version": version, "count": len(objs),
                          "custom": custom, "withName": named}
        print("  ok %-14s v%d  %5d objects (%d custom, %d named) -> %s.json"
              % (label, version, len(objs), custom, named, label))
    with open(os.path.join(out, "objects_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)


if __name__ == "__main__":
    main()
