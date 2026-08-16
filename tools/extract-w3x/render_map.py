#!/usr/bin/env python3
"""Render the extracted terrain to a PNG (pure stdlib, no PIL).

Produces a shaded colour map of the world using ground texture ids, terrain
height and water level, so zone layout can be read directly.

Usage: python3 render_map.py <extracted_dir> <out.png> [scale]
"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_terrain import parse_w3e  # noqa: E402

# Warcraft III tile id -> approximate representative colour.
TILE_COLOURS = {
    "Ydrt": (122, 105, 76), "Ydtr": (130, 112, 80), "Yblm": (96, 84, 60),
    "Ygsb": (92, 112, 62), "Yrtl": (118, 96, 66), "Ysqd": (86, 104, 60),
    "Alvd": (146, 132, 100), "Adrt": (128, 110, 78), "Adrd": (140, 120, 84),
    "Adrg": (150, 128, 88), "Agrs": (86, 116, 60),
    "Nice": (208, 226, 238), "Nsnw": (232, 240, 248), "Ndrt": (120, 104, 76),
    "Drds": (150, 136, 104), "Dlav": (188, 72, 32), "Ddkg": (70, 92, 52),
    "Dgrs": (84, 112, 58), "Drok": (110, 106, 100),
    "Vcbp": (108, 96, 86), "Vrck": (104, 100, 96), "Vcrp": (118, 104, 90),
    "Vdrt": (124, 108, 78), "Vgrs": (88, 114, 62),
    "cNc1": (198, 214, 228), "cAc1": (140, 122, 86), "cAc2": (148, 130, 92),
    "cOc1": (100, 96, 92), "cYc1": (120, 104, 76),
    "Cliff": (86, 80, 72),
}
DEFAULT = (110, 104, 88)
WATER = (48, 88, 132)


def png(path, w, h, rgb_rows):
    raw = b"".join(b"\x00" + bytes(row) for row in rgb_rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


def main():
    src = sys.argv[1]
    dest = sys.argv[2]
    scale = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    info, points, (w, h) = parse_w3e(os.path.join(src, "war3map.w3e"))
    ground = info["groundTilesets"]
    heights = [p[0] for p in points]
    hmin, hmax = min(heights), max(heights)
    hrng = max(1, hmax - hmin)

    ow, oh = w // scale, h // scale
    rows = []
    for oy in range(oh):
        y = h - 1 - oy * scale          # WC3 stores bottom-up
        row = bytearray()
        for ox in range(ow):
            x = ox * scale
            p = points[y * w + x]
            gh, water, waterflag, tex, flags, details, cliff_tex, layer = p
            tid = ground[tex] if tex < len(ground) else None
            r, g, b = TILE_COLOURS.get(tid, DEFAULT)
            # height shading
            shade = 0.65 + 0.7 * ((gh - hmin) / hrng)
            r, g, b = (min(255, int(c * shade)) for c in (r, g, b))
            # water blend where the water level sits above ground
            if water > gh + 32:
                depth = min(1.0, (water - gh) / 900.0)
                r = int(r * (1 - depth) + WATER[0] * depth)
                g = int(g * (1 - depth) + WATER[1] * depth)
                b = int(b * (1 - depth) + WATER[2] * depth)
            row += bytes((r, g, b))
        rows.append(row)

    png(dest, ow, oh, rows)
    print("wrote %s  (%dx%d px, scale 1:%d, world %d x %d units)"
          % (dest, ow, oh, scale, info["worldUnitsX"], info["worldUnitsY"]))
    print("tilesets: %s" % ", ".join(ground))


if __name__ == "__main__":
    main()
