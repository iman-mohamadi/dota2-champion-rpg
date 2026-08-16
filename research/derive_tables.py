#!/usr/bin/env python3
"""Generate human-readable reference tables from the raw TWRPG dataset.

Usage: python3 research/derive_tables.py
Writes markdown tables into research/tables/.
"""
import json
import os
from collections import Counter, defaultdict

RAW = os.path.join(os.path.dirname(__file__), "raw")
OUT = os.path.join(os.path.dirname(__file__), "tables")

GRADE_NAMES = {0: "(base)", 1: "Deltirama", 2: "Neptinos", 3: "Gnosis", 4: "Alteia", 5: "Arcana"}


def load(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return json.load(f)


def write(name, lines):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote", name, "(%d lines)" % len(lines))


def boss_table(bosses, items):
    byid = {i["id"]: i for i in items}
    out = ["# Boss Progression Ladder", "",
           "| Tier | Lvl | Boss | HP | Armor | AD | Party cap | Respawn | Spells | Minions | Drops |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    order = ["Field", "Minor", "Mid", "High", "Late", "Endgame"]
    rows = [b for b in bosses if b["type"] == "Boss" and b["category"] in order]
    rows.sort(key=lambda b: (order.index(b["category"]), int(b.get("level") or 0)))
    for b in rows:
        s = b.get("stats") or {}
        drops = ", ".join(byid.get(d, {}).get("name", d) for d in b.get("drops", []))
        out.append("| %s | %s | %s | %s | %s | %s | %s | %s | %d | %d | %s |" % (
            b["category"], b.get("level", "?"), b["name"], s.get("health", "?"),
            s.get("armor", "?"), s.get("attackDamage", "?"), b.get("limit", "-"),
            b.get("respawn", "-"), len(b.get("spells", [])), len(b.get("minions", [])),
            drops or "-"))
    return out


def zone_table(bosses):
    zones = ["Starter Village", "Kalidi Forest", "Wild Life Habitat", "Seaside", "Cave",
             "Golem Cave", "Secluded Forest", "Fairy Forest", "Abandoned Graveyard",
             "Wallachia Graveyard", "Duchy of Wallachia", "Frosty Snowfield",
             "Deep Snowfield", "Volcanic Lands", "Dragon Lair", "Dragon Nest", "Deep Sea",
             "Capital Prius", "Prius", "Avalon", "Hell", "expedition", "Plagued Tower"]
    z = defaultdict(list)
    for x in bosses:
        loc = x.get("location") or ""
        hit = [Z for Z in zones if Z.lower() in loc.lower()]
        z[hit[0] if hit else "UNMAPPED: " + loc].append(
            (int(x.get("level") or 0), x["type"], x["category"], x["name"]))
    out = ["# Zones and Their Inhabitants", ""]
    for k in sorted(z, key=lambda k: min(e[0] for e in z[k])):
        v = sorted(z[k])
        lv = [e[0] for e in v if e[0]]
        out += ["## %s  (levels %s-%s)" % (k, min(lv) if lv else "?", max(lv) if lv else "?"), "",
                "| Lvl | Kind | Tier | Name |", "|---|---|---|---|"]
        out += ["| %s | %s | %s | %s |" % e for e in v]
        out.append("")
    return out


def item_table(items):
    out = ["# Item Catalogue by Grade", ""]
    for g in sorted({i["grade"] for i in items}):
        sub = [i for i in items if i["grade"] == g]
        out += ["## Grade %d - %s (%d items)" % (g, GRADE_NAMES.get(g, "?"), len(sub)), "",
                "| Name | Type | Lvl | Recipe components | Dropped by | Drop rate |",
                "|---|---|---|---|---|---|"]
        for i in sorted(sub, key=lambda x: (x["type"], x["name"])):
            comps = []
            for step in i.get("recipe", []):
                comps += ["%s x%s" % (k, v) for k, v in step.items()]
            out.append("| %s | %s | %s | %s | %s | %s |" % (
                i["name"], i["type"], i.get("level", "-"), "; ".join(comps) or "-",
                ", ".join(i.get("dropped_by", [])) or "-", i.get("droprate", "-")))
        out.append("")
    return out


def hero_table(heroes, skills):
    per = defaultdict(list)
    for s in skills:
        per[s["heroClass"]].append(s)
    out = ["# Hero Roster", "",
           "| Class | Main stat | Role | Weapons | Skills | Specialty items |",
           "|---|---|---|---|---|---|"]
    for h in sorted(heroes, key=lambda x: (x["mainstat"], x["heroClass"])):
        out.append("| %s | %s | %s | %s | %d | %s |" % (
            h["heroClass"], h["mainstat"], "; ".join(h.get("role", [])),
            ", ".join(w.replace("Weapon ", "") for w in h.get("wearable", [])),
            len(per[h["heroClass"]]), "; ".join(h.get("spec", [])) or "-"))
    out.append("")
    for h in sorted(heroes, key=lambda x: x["heroClass"]):
        out += ["## %s (%s)" % (h["heroClass"], h["mainstat"]), ""]
        out += ["- " + d for d in h.get("description", [])]
        out += ["", "| # | Key | Skill | CD | Effect |", "|---|---|---|---|---|"]
        for s in sorted(per[h["heroClass"]], key=lambda x: x["order"]):
            body = " ".join(s.get("active") or s.get("passive") or s.get("toggle") or [])
            out.append("| %d | %s | %s | %s | %s |" % (
                s["order"], s["hotkey"], s["name"], s.get("cooldown", "-"),
                body.replace("|", "/")[:400]))
        out.append("")
    return out


def craft_depth(items):
    rec = {}
    for i in items:
        if i.get("recipe"):
            rec[i["name"]] = [(k, v) for step in i["recipe"] for k, v in step.items()]
    memo = {}

    def depth(n, seen=()):
        if n in memo:
            return memo[n]
        if n in seen or n not in rec:
            return 0
        d = 1 + max([depth(c, seen + (n,)) for c, _ in rec[n]] or [0])
        memo[n] = d
        return d

    def leaves(n, mult=1, acc=None, seen=()):
        acc = Counter() if acc is None else acc
        if n not in rec or n in seen:
            acc[n] += mult
            return acc
        for c, q in rec[n]:
            leaves(c, mult * q, acc, seen + (n,))
        return acc

    out = ["# Crafting Tree Depth and Total Grind Cost", "",
           "`Depth` = longest chain of crafts. `Leaves` = total farmed drops needed from scratch.", "",
           "| Item | Depth | Distinct leaves | Total leaf drops |", "|---|---|---|---|"]
    rows = sorted(rec, key=lambda n: (-depth(n), n))
    for n in rows:
        L = leaves(n)
        out.append("| %s | %d | %d | %d |" % (n, depth(n), len(L), sum(L.values())))
    return out


def main():
    items, bosses = load("items.json"), load("bosses.json")
    heroes, skills = load("heros.json"), load("skills.json")
    write("bosses.md", boss_table(bosses, items))
    write("zones.md", zone_table(bosses))
    write("items.md", item_table(items))
    write("heroes.md", hero_table(heroes, skills))
    write("crafting.md", craft_depth(items))


if __name__ == "__main__":
    main()
