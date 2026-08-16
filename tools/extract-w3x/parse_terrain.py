#!/usr/bin/env python3
"""Parse war3map.w3e (terrain) and war3map.w3i (map info) + war3map.wts strings.

Emits a JSON summary plus a PGM heightmap and a tile-type map so the real world
geometry can be used as the basis for our zone authoring.

Usage: python3 parse_terrain.py <extracted_dir> <out_dir>
"""
import json
import os
import struct
import sys


def read_wts(path):
    """war3map.wts -> {id: text} for TRIGSTR_nnn references."""
    if not os.path.exists(path):
        return {}
    raw = open(path, "rb").read().decode("utf-8-sig", "replace")
    out, i = {}, 0
    while True:
        i = raw.find("STRING ", i)
        if i < 0:
            break
        j = raw.find("{", i)
        k = raw.find("}", j)
        if j < 0 or k < 0:
            break
        try:
            sid = int(raw[i + 7:j].strip().split()[0])
        except (ValueError, IndexError):
            i = k + 1
            continue
        out[sid] = raw[j + 1:k].strip()
        i = k + 1
    return out


def resolve(s, strings):
    if isinstance(s, str) and s.startswith("TRIGSTR_"):
        try:
            return strings.get(int(s[8:]), s)
        except ValueError:
            return s
    return s


def parse_w3e(path):
    d = open(path, "rb").read()
    magic, ver = struct.unpack("<4sI", d[:8])
    assert magic == b"W3E!", magic
    tileset = d[8:9].decode("latin-1")
    off = 9
    custom_flag, = struct.unpack("<I", d[off:off + 4]); off += 4
    n_ground, = struct.unpack("<I", d[off:off + 4]); off += 4
    ground = [d[off + i * 4: off + i * 4 + 4].decode("latin-1") for i in range(n_ground)]
    off += n_ground * 4
    n_cliff, = struct.unpack("<I", d[off:off + 4]); off += 4
    cliff = [d[off + i * 4: off + i * 4 + 4].decode("latin-1") for i in range(n_cliff)]
    off += n_cliff * 4
    w, h, cx, cy = struct.unpack("<IIff", d[off:off + 16]); off += 16

    n = w * h
    need = n * 7
    avail = len(d) - off
    points = []
    if avail >= need:
        blob = d[off:off + need]
        for i in range(n):
            b = blob[i * 7:(i + 1) * 7]
            ground_h, water_h, flags_tex, details, cliff_tex_layer = struct.unpack("<HHBBB", b)
            # low nibble = ground texture index, high nibble = flags
            # (1=ramp, 2=blight, 4=water, 8=camera boundary)
            points.append((ground_h, water_h & 0x3FFF, (water_h >> 14) & 1,
                           flags_tex & 0x0F, (flags_tex >> 4) & 0x0F,
                           details, cliff_tex_layer >> 4, cliff_tex_layer & 0x0F))
    return {
        "version": ver, "tileset": tileset, "customTilesets": bool(custom_flag),
        "groundTilesets": ground, "cliffTilesets": cliff,
        "gridWidth": w, "gridHeight": h,
        "cellsX": w - 1, "cellsY": h - 1,
        "worldUnitsX": (w - 1) * 128, "worldUnitsY": (h - 1) * 128,
        "centerOffsetX": cx, "centerOffsetY": cy,
        "boundsMinX": cx, "boundsMinY": cy,
        "boundsMaxX": cx + (w - 1) * 128, "boundsMaxY": cy + (h - 1) * 128,
    }, points, (w, h)


def parse_w3i(path, strings):
    d = open(path, "rb").read()
    ver, = struct.unpack("<I", d[:4])
    off = 4
    saves, editor = struct.unpack("<II", d[off:off + 8]); off += 8
    if ver >= 27:
        off += 12  # unknown version ints

    def cstr(o):
        e = d.index(b"\0", o)
        return d[o:e].decode("utf-8", "replace"), e + 1

    name, off = cstr(off)
    author, off = cstr(off)
    desc, off = cstr(off)
    players, off = cstr(off)
    camB = struct.unpack("<8f", d[off:off + 32]); off += 32
    comp = struct.unpack("<4i", d[off:off + 16]); off += 16
    pw, ph = struct.unpack("<II", d[off:off + 8]); off += 8
    flags, = struct.unpack("<I", d[off:off + 4]); off += 4
    tileset = d[off:off + 1].decode("latin-1"); off += 1
    return {
        "w3iVersion": ver, "saves": saves, "editorVersion": editor,
        "name": resolve(name, strings), "author": resolve(author, strings),
        "description": resolve(desc, strings),
        "recommendedPlayers": resolve(players, strings),
        "cameraBounds": camB, "cameraComplements": comp,
        "playableWidth": pw, "playableHeight": ph,
        "flags": hex(flags), "tileset": tileset,
    }


def write_pgm(path, values, w, h, vmin=None, vmax=None):
    vmin = min(values) if vmin is None else vmin
    vmax = max(values) if vmax is None else vmax
    rng = max(1, vmax - vmin)
    with open(path, "wb") as f:
        f.write(b"P5\n%d %d\n255\n" % (w, h))
        # flip rows: WC3 stores bottom-up
        for y in range(h - 1, -1, -1):
            row = values[y * w:(y + 1) * w]
            f.write(bytes(min(255, max(0, (v - vmin) * 255 // rng)) for v in row))


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    strings = read_wts(os.path.join(src, "war3map.wts"))
    print("wts strings: %d" % len(strings))

    info, points, (w, h) = parse_w3e(os.path.join(src, "war3map.w3e"))
    print(json.dumps(info, indent=1))
    print("tilepoints parsed: %d (expected %d)" % (len(points), w * h))

    meta = {"terrain": info}
    w3i = os.path.join(src, "war3map.w3i")
    if os.path.exists(w3i):
        meta["mapInfo"] = parse_w3i(w3i, strings)
        print("\nmap info:")
        for k in ("name", "author", "description", "recommendedPlayers",
                  "playableWidth", "playableHeight", "tileset"):
            print("  %-20s %s" % (k, meta["mapInfo"].get(k)))

    if points:
        heights = [p[0] for p in points]
        water = [p[1] for p in points]
        tex = [p[3] for p in points]
        write_pgm(os.path.join(out, "heightmap.pgm"), heights, w, h)
        write_pgm(os.path.join(out, "watermap.pgm"), water, w, h)
        write_pgm(os.path.join(out, "tilemap.pgm"), tex, w, h, 0, 15)
        meta["terrainStats"] = {
            "heightMin": min(heights), "heightMax": max(heights),
            "waterMin": min(water), "waterMax": max(water),
            "groundTextureHistogram": {
                info["groundTilesets"][i] if i < len(info["groundTilesets"]) else str(i):
                tex.count(i) for i in sorted(set(tex))},
        }
        print("\nheight range %d..%d   textures used: %s"
              % (min(heights), max(heights), sorted(set(tex))))
        print("wrote heightmap.pgm / watermap.pgm / tilemap.pgm (%dx%d)" % (w, h))

    with open(os.path.join(out, "terrain.json"), "w") as f:
        json.dump(meta, f, indent=1)
    with open(os.path.join(out, "strings.json"), "w") as f:
        json.dump(strings, f, indent=1, ensure_ascii=False)
    print("wrote terrain.json, strings.json")


if __name__ == "__main__":
    main()
