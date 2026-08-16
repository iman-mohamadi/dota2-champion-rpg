#!/usr/bin/env python3
"""Render the world map with mined spawn points overlaid, coloured by level.

Usage: python3 render_annotated.py <extracted_dir> <spawns.json> <out.png> [scale]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_terrain import parse_w3e            # noqa: E402
from render_map import TILE_COLOURS, DEFAULT, WATER, png  # noqa: E402

# level -> colour ramp (low = green, high = red/violet)
BANDS = [
    (10, (120, 240, 120)), (30, (200, 240, 90)), (50, (250, 220, 70)),
    (70, (250, 160, 50)), (90, (250, 90, 60)), (110, (240, 60, 140)),
    (130, (190, 90, 255)), (10 ** 9, (255, 255, 255)),
]


def band_colour(level):
    try:
        lv = int(level)
    except (TypeError, ValueError):
        return (170, 170, 170)
    for thresh, col in BANDS:
        if lv <= thresh:
            return col
    return (255, 255, 255)


def main():
    src, spawn_file, dest = sys.argv[1], sys.argv[2], sys.argv[3]
    scale = int(sys.argv[4]) if len(sys.argv) > 4 else 1

    info, points, (w, h) = parse_w3e(os.path.join(src, "war3map.w3e"))
    ground = info["groundTilesets"]
    heights = [p[0] for p in points]
    hmin, hmax = min(heights), max(heights)
    hrng = max(1, hmax - hmin)
    minx, miny = info["boundsMinX"], info["boundsMinY"]

    ow, oh = w // scale, h // scale
    grid = []
    for oy in range(oh):
        y = h - 1 - oy * scale
        row = []
        for ox in range(ow):
            x = ox * scale
            gh, water, wf, tex, flags, det, ct, layer = points[y * w + x]
            tid = ground[tex] if tex < len(ground) else None
            r, g, b = TILE_COLOURS.get(tid, DEFAULT)
            shade = 0.55 + 0.6 * ((gh - hmin) / hrng)
            r, g, b = (min(255, int(c * shade)) for c in (r, g, b))
            if water > gh + 32:
                d = min(1.0, (water - gh) / 900.0)
                r = int(r * (1 - d) + WATER[0] * d)
                g = int(g * (1 - d) + WATER[1] * d)
                b = int(b * (1 - d) + WATER[2] * d)
            # dim the base so overlay dots pop
            row.append([int(r * 0.75), int(g * 0.75), int(b * 0.75)])
        grid.append(row)

    spawns = json.load(open(spawn_file))
    plotted = 0
    for s in spawns:
        px = int((s["x"] - minx) / 128.0) // scale
        py = (h - 1 - int((s["y"] - miny) / 128.0)) // scale
        if not (0 <= px < ow and 0 <= py < oh):
            continue
        col = band_colour(s.get("level"))
        plotted += 1
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                qx, qy = px + dx, py + dy
                if 0 <= qx < ow and 0 <= qy < oh:
                    edge = dx or dy
                    grid[qy][qx] = [c // 3 for c in col] if edge else list(col)

    png(dest, ow, oh, [bytes(c for px in row for c in px) for row in grid])
    print("wrote %s (%dx%d), plotted %d/%d spawns"
          % (dest, ow, oh, plotted, len(spawns)))
    print("legend: green<=10 lime<=30 yellow<=50 orange<=70 red<=90 "
          "pink<=110 violet<=130 white>130 grey=unknown")


if __name__ == "__main__":
    main()
