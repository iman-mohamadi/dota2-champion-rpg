# Notices, Provenance and Licensing

This repository is **research and planning for a non-commercial fan tribute**. It contains no
game code yet. Please read this before reusing anything here.

---

## 1. What this project is

**ChampionRPG** rebuilds **The World RPG (TWRPG)** — a Warcraft III custom map — as a
**Dota 2 custom game**. The Dota Workshop licence is *strictly non-commercial*, and this project is
non-commercial by construction. It is a tribute, not a product, and not affiliated with or
endorsed by any rightsholder below.

## 2. Credits

- **The World RPG** is the work of **Keekero** (original author) and **greenFruit**
  (current maintainer), and its community.
- **Warcraft III** and its data formats are © Blizzard Entertainment.
- **Dota 2**, Source 2 and the Workshop Tools are © Valve Corporation.

Nothing here is claimed as original work by those parties' standards; the design, item names,
boss names and systems described are theirs.

## 3. Third-party data vendored in `research/raw/`

| Source | Contents | Licence |
|---|---|---|
| [sfarmani/twrpg-info](https://github.com/sfarmani/twrpg-info) (TWRPG-BOT) | items, bosses, heroes, skills, buffs/debuffs, builds, changelog | **none stated** |
| [alecpayos/twrpg-guidebook](https://github.com/alecpayos/twrpg-guidebook) | stat vocabulary, grade tier names (`*.ts`) | **none stated** |
| [TWRPG Wiki (Miraheze)](https://twrpg.miraheze.org/) | page-title index only | see wiki |

> **Neither upstream repository states a licence.** Under GitHub's terms that means
> *all rights reserved* — public availability is not permission to redistribute. These files
> are mirrored here in good faith for a non-commercial fan project, with attribution. **If you
> are a maintainer of either project and want them removed, open an issue and they will be
> removed immediately.**
>
> If you are reusing this repository, do not assume you have the right to redistribute
> `research/raw/`. Fetch it from the upstream sources instead.

## 4. Data in `research/extracted/`

Derived by parsing `twrpgv0.65b_eng.w3x` with the tools in `tools/extract-w3x/`.

**Deliberately not included:**
- the `.w3x` map file itself
- `war3map.j` (the game script), obfuscated or otherwise
- `war3mapMisc.txt` and any other verbatim file lifted from the archive
- any art, model, icon or sound asset

What *is* included is factual/derived data — stat tables, terrain heightmaps, spawn
coordinates, id→handler mappings, computed curves. Some of it (item and ability names,
description strings) is unavoidably verbatim creative text from the original map and is
included solely to document the design. It is **reference for reimplementation, never
shippable content**.

Everything here is reproducible from a downloaded map with the scripts in `tools/extract-w3x/`.

## 5. Planned implementation

Per `docs/02-TECH-PLAN.md` §9 and `docs/08-DOTA2-IMPLEMENTATION-PLAN.md` §7:

- The game will be a **reimplementation from documented data**. No extracted script or asset
  will ship.
- A **rename layer** is built into the content pipeline so original item/boss names can be
  swapped out if required.
- On Dota 2, art comes from Valve's own asset library; no Blizzard assets are used.

## 6. Licence of the original work in this repo

The **documentation (`docs/`), tooling (`tools/`) and generated tables (`research/tables/`)**
are original work by this project's authors and are offered under the **MIT Licence** (see
`LICENSE`). That licence covers *only* those parts — it does not and cannot apply to the
third-party data in `research/raw/` or to material derived from the original map.

## 7. Takedown

If you hold rights to any material here and want it removed, open an issue or contact the
repository owner. It will be taken down promptly and without argument.
