#!/usr/bin/env python3
"""Mine literal unit spawn coordinates out of the (obfuscated) war3map.j.

war3mapUnits.doo is stripped by the map's protection, but many units are still
created by direct CreateUnit(player, 'id', x, y, facing) calls with literal
JASS number arguments. Those give real world coordinates.

Usage: python3 mine_spawns.py <script.j> <units.json> <out.json>
"""
import json
import re
import sys

NUM = r"-?(?:\$[0-9A-Fa-f]+|\d+\.?\d*)"
CREATE = re.compile(
    r"CreateUnit\(\s*[^,]{1,40},\s*'([^']{4})'\s*,\s*(%s)\s*,\s*(%s)\s*,\s*(%s)\s*\)" % (NUM, NUM, NUM))


def jnum(tok):
    tok = tok.strip()
    neg = tok.startswith("-")
    if neg:
        tok = tok[1:]
    v = int(tok[1:], 16) if tok.startswith("$") else float(tok)
    return -v if neg else v


def strip_colour(s):
    return re.sub(r"\|c[0-9a-fA-F]{8}|\|[rRnN]", "", s or "").strip()


def main():
    script, units_json, out = sys.argv[1], sys.argv[2], sys.argv[3]
    src = open(script, encoding="utf-8", errors="replace").read()

    units = json.load(open(units_json))
    names = {o["id"]: strip_colour(o["mods"].get("name", "")) for o in units}
    levels = {o["id"]: o["mods"].get("level") for o in units}

    spawns = []
    for m in CREATE.finditer(src):
        uid, x, y, f = m.group(1), jnum(m.group(2)), jnum(m.group(3)), jnum(m.group(4))
        if x == 0 and y == 0:
            continue  # placeholder / dummy creation
        spawns.append({"unitId": uid, "name": names.get(uid, ""),
                       "level": levels.get(uid), "x": x, "y": y, "facing": f})

    with open(out, "w") as f:
        json.dump(spawns, f, indent=1, ensure_ascii=False)

    print("literal CreateUnit spawns with coordinates: %d" % len(spawns))
    known = [s for s in spawns if s["name"]]
    print("of which resolve to a named unit: %d" % len(known))
    xs = [s["x"] for s in spawns]
    ys = [s["y"] for s in spawns]
    if xs:
        print("coordinate range: x %.0f..%.0f   y %.0f..%.0f"
              % (min(xs), max(xs), min(ys), max(ys)))
    return spawns


if __name__ == "__main__":
    main()
