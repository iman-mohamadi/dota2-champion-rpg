# Extracted Map Data — Results

The `.w3x` was downloaded, unpacked and parsed. This closes most of the gaps listed in
`00-RESEARCH-FINDINGS.md` §5–6. Everything below is measured from the real map file.

**Source:** `twrpgv0.65b_eng.w3x`, 78 MB, from [wc3maps.com/map/313739](https://wc3maps.com/map/313739).
Internal title: `|c0000bfffThe World RPG|r v0.65b`, author field `developer`, description
`Original by: Keekero / Compatible version: v0.62a ~`, recommended players `10`.

---

## 1. How it was done

No usable tooling existed in this environment — `smpq`/StormLib need root, and there is no
`pip`. So `tools/extract-w3x/` contains a **dependency-free MPQ reader written from the
format spec**, plus parsers for each internal file.

| Tool | Purpose |
|---|---|
| `mpq.py` | MPQ archive reader: crypt table, hash/block tables, file decryption, sector decompression (zlib, bzip2, sparse, **PKWare DCL implode**) |
| `extract.py` | Probes the standard WC3 internal filenames and extracts them |
| `parse_terrain.py` | `war3map.w3e` terrain + `war3map.w3i` map info + `war3map.wts` strings |
| `parse_objects.py` | `.w3u/.w3t/.w3a/.w3h/.w3d/.w3q` custom object tables |
| `mine_spawns.py` | Recovers literal `CreateUnit` coordinates from the obfuscated script |
| `derive_zones.py` | Clusters spawns into zones and labels them from the community location strings |
| `render_map.py` / `render_annotated.py` | Pure-stdlib PNG renderers for the world map |

Archive: MPQ v0, 8192 hash entries, **6274 files**, 4 MB sectors. All target files extracted
with **zero errors**.

**Reproduce:**
```bash
python3 tools/extract-w3x/extract.py <map.w3x> out/
python3 tools/extract-w3x/parse_terrain.py out/ parsed/
python3 tools/extract-w3x/parse_objects.py out/ parsed/
python3 tools/extract-w3x/mine_spawns.py out/scripts/war3map.j parsed/units.json parsed/spawns.json
ZONE_CELL=1400 python3 tools/extract-w3x/derive_zones.py parsed/spawns.json research/raw/bosses.json parsed/zones_derived.json
python3 tools/extract-w3x/render_annotated.py out/ parsed/spawns.json parsed/worldmap_annotated.png
```

---

## 2. What came out

| File | Size | Contents |
|---|---|---|
| `war3map.w3e` | 1.6 MB | terrain — 231,361 tilepoints |
| `war3map.w3u` | 1.0 MB | **1,286 units** (1,231 custom, 1,258 named) |
| `war3map.w3t` | 840 KB | **1,292 items** (all named) |
| `war3map.w3a` | 1.1 MB | **1,944 abilities** (1,932 named) |
| `war3map.w3h` | 94 KB | 564 buffs |
| `war3map.w3d` | 82 KB | 452 doodads |
| `war3map.doo` | 582 KB | doodad placement |
| `scripts/war3map.j` | **7.0 MB** | JASS script, 48,604 lines, 16,820 functions |
| `war3map.wts` | 13 KB | 72 trigger strings |
| `war3mapMisc.txt` | 61 KB | **gameplay constants** — XP curve, armour coefficient (see doc 05) |
| `war3map.wpm` / `.shd` | 3.7 MB each | pathing map / shadow map |

`war3mapUnits.doo` (preplaced units) was **stripped by the map's protection** — worked
around in §5.

Derived output is vendored in `research/extracted/`. **The map file and its script are not
vendored** — they are copyrighted. Only derived factual data is kept (see tech plan §9).

---

## 3. Gap A — map geometry: **CLOSED**

```
grid                481 x 481 tilepoints  (480 x 480 cells)
playable area       478 x 478             ← matches the documented map size exactly
world size          61,440 x 61,440 units
world bounds        X -30,208 .. 31,232   Y -31,744 .. 29,696
terrain height      3,042 .. 15,039 (mean 8,297)
water tiles         28,811 of 231,361 (12.5%)
tileset             'Y' (Sunken Ruins) with 16 custom ground + 2 cliff tilesets
```

Ground tilesets: `Ydrt Alvd Ysqd Nice Drds cNc1 Vcbp Vrck Dlav Yrtl cAc2 cAc1 Adrg Vcrp Adrd cOc1`
— dirt, ice/snow, rock, lava, dragon and corrupt variants, matching the known biomes.

Rendered maps are in `research/extracted/maps/`:
- `worldmap.png` — colour + height-shaded terrain
- `worldmap_annotated.png` — same, with all 638 spawn points coloured by level band
- `heightmap.pgm.gz`, `tilemap.pgm.gz`, `watermap.pgm.gz` — raw 481×481 layers for import

**Layout:** a central continent with rivers and lakes, a snowfield south of centre, a
volcanic region east, and roughly **60 rectangular instanced arenas** ringing the perimeter —
the boss zones. This is why so many bosses' `location` strings read "through the portal" or
"teleporter, second page": those arenas are not physically connected to the overworld.

---

## 4. Gap B/C — base stats and formulas: **substantially closed**

### Heroes (36 of 37 community hero ids matched by id)

Every hero is identical in its base block:

```
hpMax        500
moveSpeed    500
strength/agility/intelligence   0–7   (tiny, class-flavoured)
strPerLevel / agiPerLevel / intPerLevel   0.0   ← all zero, for every hero
```

**This is a real design finding: levelling grants no automatic stat growth.** All character
power comes from the 697 manually-allocated stat points plus equipment. That resolves the
open question about the level curve's role — the curve gates *content access and stat
points*, not raw stats.

Attack differs per class, e.g. Sniper `cooldown 1.75 / range 900`, Blood Weaver
`cooldown 0.9 / range 150`, Sword Enchanter `cooldown 1.0 / range 75`.

### Attack damage formula — resolved

Cross-referencing map fields against the community dataset resolved two ambiguities:

| Community field | Actually is |
|---|---|
| `attackDamage` | `atk1BaseDamage + diceCount` (i.e. minimum roll) |
| `attackSpread` | `diceSides - 1` |
| `attackSpeed` | `1 / atk1Cooldown` (attacks per second) |

Verified: Spider — map `base 24, sides 1, cooldown 1.6` → community `damage 25, spread 1,
attackSpeed .625`. Beriel — map `base 1539, sides 6, cooldown 0.8` → community `1540,
spread 5`. So real damage per swing is `base + roll(diceCount, diceSides)`.

---

## 5. Gap D — spawn placement: **partially closed**

`war3mapUnits.doo` is stripped, but **638 literal `CreateUnit(player, 'id', x, y, facing)`
calls survive in the script with real coordinates** — 560 of which resolve to a named unit.
Remaining spawns are table-driven (arrays of ids/coords) and would need script deobfuscation.

Extracted to `research/extracted/spawns.json`. Coordinate span: X −28,565..28,995,
Y −30,786..28,578 — i.e. the full map.

### Derived zone geometry (`research/extracted/zones_derived.json`)

Spawns clustered spatially, then labelled by majority vote of the community `location`
strings for units found inside. **Real world coordinates for the first time:**

| Zone | Lvl | Spawns | Centroid (x, y) | Dominant units |
|---|---|---|---|---|
| Capital Prius (hub) | 1–100 | 53 | (−4,598, −1,207) | Villager ×36, Dog ×4, Prius Guard ×2 |
| Wild Life Habitat (lower) | 1–29 | 105 | (−5,088, 8,553) | Spider ×27, Troll ×17, Wolf ×12 |
| Wild Life Habitat / Seaside | 33–43 | 34 | (6,514, 8,308) | White/Blue/Green Murloc |
| Volcanic Lands | 62–70 | 63 | (17,446, −1,205) | Lava Spawn ×30, Lava Hatchling ×20 |
| Duchy of Wallachia | 62–67 | 43 | (22,793, 11,453) | Wallachia Soldier ×17, Guardian |
| Duchy of Wallachia (north) | 60–67 | 3 | (27,986, 13,473) | Death Knight Lord |
| Deep Sea | 73–80 | 27 | (25,544, 19,698) | Tide Caller ×13, Sea Guardian ×8 |
| Castle Avalon approach | 80 | 18 | (16,971, −11,731) | Eye of Colossus ×12, Avalon Defender |
| Castle Avalon inner | 80 | 17 | (17,210, −14,902) | Eye of Colossus ×12, Avalon Protector |
| Wallachia Graveyard | 84–100 | 24 | (7,153, −13,754) | Wallachia Apostle ×10, Assassin |
| Cave / Golem Cave | 86–90 | 17 | (8,999, 15,874) | Stone Golem ×11, Solid Golem ×5 |
| Fairy Forest | 93–96 | 30 | (−13,011, −2,682) | Forest Spirit ×17, Fairy ×13 |
| Dragon Lair | 100 | 17 | (27,415, −2,019) | Dragon Hatchling ×12, Dragonic Warrior ×5 |
| Fairy Forest — Deep Forest | 100 | 22 | (11,044, −23,860) | Fairy Spirit ×13, Dryad ×8, Spirit Beast |
| Expedition (Area 6) | 100 | 10 | (2,104, −22,271) | Expedition Archer/Magician/Warrior |
| Expedition forward camp | 100 | 5 | (−2,014, −12,481) | Expedition units, Captain |
| Endgame arenas | 120 | 4 | (24,096, −26,350) | **Ifrit, Valtora, Underlord Agareth** |
| Mage Tower / academy | — | 42 | (−26,993, 26,778) | Mage ×7, Dean Jaina, Bookshelf |

Note the endgame cluster: Ifrit, Valtora and Agareth sit in adjacent instanced arenas in the
far south-east — confirming the teleporter-menu access pattern from the community data.

---

## 6. Bonus — item descriptions are **structured**, not prose

The biggest content-pipeline win. In-map item descriptions use a delimiter format:

```
[Epic]
- Neptinos Grade Weapon (Melee) -
Let it go, if you can no longer control it.
∴Damage +6750
∴STR +555
∴Skill Damage +5%
∴On attack, chance to activate Devastation
∴On use, activates Anger
▣ Lv.100
```

Measured across 1,109 described items:
- **2,750 `∴` stat lines** using only **36 distinct stat labels** — exactly the vocabulary in
  `guidebook-dictionaries.ts` (Damage 278, Skill Damage 233, Armor 184, AGI 173, STR 172,
  INT 148, All Stats 122, Main Stat 82, HP 81, and the affinities).
- **597 items carry an explicit `▣ Lv.N` level requirement.**
- Grade tier names appear inline (`Neptinos Grade Weapon (Melee)`), independently confirming
  the grade→tier mapping.

**Consequence:** the tech plan's ability/stat parser (§4.1) drops from "~70% auto, 30% manual"
to **near-100% automatic for item stats**. Only ability *effect* text still needs the harder
grammar work.

Also recovered: `abilities` field on each item listing the ability ids it grants
(Anger → `A11E,A0HM`), giving the real item→ability wiring.

---

## 7. What is still missing

| Gap | Status | Note |
|---|---|---|
| Ability numeric effects | **still open** | 1,944 abilities extracted, but TWRPG implements effects in script, not object data — e.g. Brandish has no object-data cooldown. Numbers live in the obfuscated JASS. |
| EXP curve | **still open** | In the script. Object data confirms it grants no stat growth, which narrows what the curve must do. |
| Damage mitigation formula | **still open** | Armor values extracted; the armor→reduction curve is in script. |
| Table-driven spawns | partial | 638 of an unknown total recovered. |
| `war3map.w3b` | parse error | Destructibles; small file, low value. |

The script is name-mangled (identifiers reduced to `V`, `E`, `vv`, `ov`…) with strings moved
into a runtime-decoded table. Natives (`SetUnitX`, `TimerStart`, `CreateUnit`) survive, so
targeted mining works — as demonstrated for spawns — but full deobfuscation is a separate
project.

---

## 8. Cross-validation summary

Extraction independently confirms the community dataset, which is now trustworthy:

| Check | Result |
|---|---|
| Community boss ids present in map units | **147 / 148** |
| Community item ids present in map items | **765 / 765** |
| Community hero ids present in map units | **36 / 37** |
| Community hero ability ids present in map abilities | **367 / 372** |
| Documented map size vs extracted | 480×480 / playable 478×478 — **exact match** |

### Where they disagree — and why it matters

Map object data is the **base layer**; the script applies runtime modifiers. Both are needed.

| Boss | Map base HP | Community HP | Map armor | Community armor |
|---|---|---|---|---|
| Demon Lord Beriel | 1,000,000 | 1,200,000 | 750 | 730 |
| Ancient Ent | 7,500,000 | 75,000,000 | 800 | 1,120 |
| Underlord Agareth | 12,500,000 | 13,500,000 | 850 | 1,240 |
| Duke Lazarus | 30,000,000 | 30,000,000 | 900 | 1,290 |

So the community numbers are *effective* values including script scaling (difficulty, party
size, phase). **Implement the base values from object data and the modifiers as an explicit
scaling layer** — that is exactly how the original works.

Extraction also revealed **phase forms the community data collapses**: Duke Lazarus exists as
two units — `h08K` "Duke Lazarus" (attack 7,530, range 2,500) and `h08L` "**Lord of Sacrifice**
Lazarus" (attack 10,390, range 250). A melee-range enraged second form. Agareth likewise has
`h077`/`h078`. Encounter definitions must model form swaps as distinct unit templates.
