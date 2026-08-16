#!/usr/bin/env python3
"""Build the Dota 2 addon content from research/.

    python3 tools/build-content/build.py

Runs the reference validator first and refuses to emit anything if it fails —
a dangling reference is far cheaper to fix here than as a runtime nil in Lua.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as C          # noqa: E402
import validate             # noqa: E402
import gen_constants        # noqa: E402
import gen_units            # noqa: E402


def main():
    print("== validating ==")
    if validate.main() != 0:
        print("\nBUILD FAILED: fix the errors above before generating content.")
        return 1

    print("\n== generating ==")
    _, consts = gen_constants.build()
    print("  constants.lua        max level %d, %s XP to max, armour k=%s"
          % (consts["MAX_HERO_LEVEL"], format(consts["TOTAL_XP_TO_MAX"], ","),
             consts["ARMOR_K"]))

    kv, lua = gen_units.build(consts)
    print("  npc_units_custom.txt %d units" % len(kv))
    print("  units.lua            %d entries (%d bosses)"
          % (len(lua), sum(1 for v in lua.values() if v["kind"] == "Boss")))

    print("\n== output ==")
    for root, _, files in os.walk(os.path.join(C.ADDON)):
        for f in sorted(files):
            p = os.path.join(root, f)
            print("  %-62s %8d bytes" % (os.path.relpath(p, C.ROOT), os.path.getsize(p)))
    print("\nBUILD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
