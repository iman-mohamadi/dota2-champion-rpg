#!/usr/bin/env python3
"""Extract known Warcraft III map files from a .w3x archive.

Protected maps usually strip (listfile), so we probe the full set of standard
WC3 internal filenames rather than enumerating.

Usage: python3 extract.py <map.w3x> <outdir>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mpq import MPQArchive  # noqa: E402

KNOWN = [
    # core
    "war3map.w3e",            # terrain (tiles, heights)
    "war3map.w3i",            # map info: players, teams, bounds
    "war3map.wts",            # trigger strings
    "war3map.shd",            # shadow map
    "war3map.wpm",            # pathing map
    "war3map.doo",            # doodads
    "war3mapUnits.doo",       # preplaced units + items  <-- spawns
    "war3map.mmp",            # minimap markers
    "war3mapMap.blp",         # minimap image
    "war3mapPreview.tga",
    "war3mapMap.tga",
    "war3map.imp",            # imported files list
    "war3mapImported\\war3mapImported.txt",
    # object data
    "war3map.w3u",            # units
    "war3map.w3t",            # items
    "war3map.w3b",            # destructibles
    "war3map.w3d",            # doodads
    "war3map.w3a",            # abilities
    "war3map.w3h",            # buffs
    "war3map.w3q",            # upgrades
    "war3map.w3o",            # combined object editor file
    # scripts
    "war3map.j",
    "scripts\\war3map.j",
    "war3map.lua",
    "scripts\\war3map.lua",
    "war3map.wct",            # custom text triggers
    "war3map.wtg",            # trigger definitions (GUI)
    # misc
    "(listfile)",
    "(attributes)",
    "(signature)",
    "conversation.json",
    "war3campaign.w3f",
    # tables that some maps override
    "UI\\MiscData.txt",
    "Units\\UnitAbilities.slk",
    "Units\\UnitData.slk",
    "Units\\UnitBalance.slk",
    "Units\\UnitUI.slk",
    "Units\\UnitWeapons.slk",
    "Units\\AbilityData.slk",
    "Units\\ItemData.slk",
    "Units\\CampaignUnitFunc.txt",
    "Units\\CampaignAbilityFunc.txt",
    "Units\\HumanUnitFunc.txt",
    "Units\\ItemFunc.txt",
    "Units\\ItemStrings.txt",
    "Units\\UnitMetaData.slk",
]


def main():
    src, out = sys.argv[1], sys.argv[2]
    a = MPQArchive(src)
    print("MPQ v%d | sector %d | %d hash / %d block entries"
          % (a.format_version, a.sector_size, a.hash_count, a.block_count))

    # names hinted by an embedded listfile, if present
    names = list(KNOWN)
    lf = a.read("(listfile)")
    if lf:
        extra = [n.strip() for n in lf.decode("utf-8", "replace").replace("\r", "\n").split("\n")]
        names += [n for n in extra if n and n not in names]
        print("(listfile) present: %d entries" % len([e for e in extra if e]))

    os.makedirs(out, exist_ok=True)
    ok = fail = 0
    for n in names:
        try:
            data = a.read(n)
        except Exception as e:
            print("  !! %-34s %s: %s" % (n, type(e).__name__, e))
            fail += 1
            continue
        if not data:
            continue
        dest = os.path.join(out, n.replace("\\", "/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        print("  ok %-34s %9d bytes" % (n, len(data)))
        ok += 1
    print("\nextracted %d files, %d errors" % (ok, fail))
    print("note: %d blocks exist in the archive; the rest are imported assets "
          "whose names are not recoverable without a listfile." % a.block_count)


if __name__ == "__main__":
    main()
