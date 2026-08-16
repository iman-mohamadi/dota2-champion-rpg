#!/usr/bin/env python3
"""Derive real zone geometry by clustering mined spawn coordinates.

Groups spawn points into spatial clusters, then labels each cluster using the
community dataset's textual `location` field for the units found inside it.
Output is a zone table with real world-space bounding boxes.

Usage: python3 derive_zones.py <spawns.json> <community_bosses.json> <out.json>
"""
import json
import sys
from collections import Counter, defaultdict

CELL = float(__import__("os").environ.get("ZONE_CELL", 3000))          # grid cell for connected-component clustering
MIN_CLUSTER = 3        # ignore stray singletons


def cluster(points):
    """Grid-based connected components (8-neighbour) over spawn positions."""
    buckets = defaultdict(list)
    for i, p in enumerate(points):
        buckets[(int(p["x"] // CELL), int(p["y"] // CELL))].append(i)

    seen, groups = set(), []
    for key in list(buckets):
        if key in seen:
            continue
        stack, comp = [key], []
        seen.add(key)
        while stack:
            cx, cy = stack.pop()
            comp.extend(buckets[(cx, cy)])
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nk = (cx + dx, cy + dy)
                    if nk in buckets and nk not in seen:
                        seen.add(nk)
                        stack.append(nk)
        if len(comp) >= MIN_CLUSTER:
            groups.append(comp)
    return groups


def main():
    spawn_file, comm_file, out_file = sys.argv[1], sys.argv[2], sys.argv[3]
    spawns = [s for s in json.load(open(spawn_file)) if s.get("name")]
    comm = json.load(open(comm_file))

    loc_by_name = {}
    for b in comm:
        if b.get("location"):
            loc_by_name[b["name"]] = b["location"]

    groups = cluster(spawns)
    zones = []
    for comp in groups:
        pts = [spawns[i] for i in comp]
        xs = [p["x"] for p in pts]
        ys = [p["y"] for p in pts]
        lv = [int(p["level"]) for p in pts
              if str(p.get("level") or "").lstrip("-").isdigit() and int(p["level"]) < 1000]
        locs = Counter(loc_by_name[p["name"]] for p in pts if p["name"] in loc_by_name)
        names = Counter(p["name"] for p in pts)
        zones.append({
            "label": locs.most_common(1)[0][0] if locs else "(unlabelled)",
            "spawnCount": len(pts),
            "levelMin": min(lv) if lv else None,
            "levelMax": max(lv) if lv else None,
            "bounds": {"minX": min(xs), "minY": min(ys),
                       "maxX": max(xs), "maxY": max(ys)},
            "centroid": {"x": round(sum(xs) / len(xs)), "y": round(sum(ys) / len(ys))},
            "units": [{"name": n, "count": c} for n, c in names.most_common()],
            "locationVotes": [{"location": l, "votes": c} for l, c in locs.most_common(3)],
        })

    zones.sort(key=lambda z: (z["levelMin"] if z["levelMin"] is not None else 999))
    json.dump(zones, open(out_file, "w"), indent=1, ensure_ascii=False)

    print("derived %d spatial clusters from %d named spawns\n" % (len(zones), len(spawns)))
    print("%-4s %-6s %-7s %-26s %s" % ("n", "lvl", "spawns", "centroid", "label / top units"))
    print("-" * 118)
    for i, z in enumerate(zones, 1):
        c = z["centroid"]
        top = ", ".join("%s x%d" % (u["name"], u["count"]) for u in z["units"][:3])
        print("%-4d %-6s %-7d (%7d,%7d)   %-40s %s"
              % (i, "%s-%s" % (z["levelMin"], z["levelMax"]), z["spawnCount"],
                 c["x"], c["y"], z["label"][:40], top[:60]))


if __name__ == "__main__":
    main()
