#!/usr/bin/env python3
"""Scaffold encounter definitions -> data/encounters.lua.

What the source data DOES support, and is generated here:
  * the ability roster each boss uses          (bosses.json `spells`)
  * its minion types                            (`minions`)
  * the empowered stat set for enrage/phase 2   (`empoweredStats`)
  * party cap, respawn timer, enrage timer      (`limit`, `respawn`, `timer`)
  * difficulty modes and party scaling          (constants from docs/00 §3.8)

What it does NOT support, and is therefore NOT invented here:
  * phase HP thresholds
  * ability timings and rotations
  * the specifics of wipe/instakill/positional mechanics

Those are authored per boss. Each generated definition carries a single default
phase and `authored = false`, so it is obvious at a glance which encounters are
still scaffolds. Hand-authored definitions live in
content/encounters/<unit>.lua and are merged over the scaffold, never
overwritten by a rebuild.
"""
import os

import common as C

# Bosses whose fights include a phase the timeline cannot express and that need
# a scripted hook (docs/02 §3.7). Recorded from the research, not guessed.
SCRIPTED_HOOKS = {
    "Underlord Agareth": "instanced mini-game arena with its own units",
    "Duke Lazarus": "second form 'Lord of Sacrifice' with a different stat block",
    "Styrix, the Harvester of Souls": "heals from heroes who die outside the zone",
    "Ancient Ent": "75M HP, domain-based mechanics",
    "Death Fiend": "Fog phase disables self-resurrection",
    "Demon Lord Beriel": "wave phase gated on not killing the gate",
}

DEFAULT_MODES = {
    "normal": {"damageDealt": 1.0, "damageTaken": 1.0, "dropRateBonus": 0.0, "drops": True},
    "hard": {"damageDealt": 1.0, "damageTaken": 1.0, "dropRateBonus": 0.50,
             "damageResistBonus": 0.33, "drops": True},
    "practice": {"damageDealt": 0.25, "damageTaken": 3.0, "dropRateBonus": 0.0,
                 "drops": False},
}
# 8-10 player servant HP and rune drain reduced 25% (patch 64b)
DEFAULT_PARTY_SCALING = {"8-10": {"addHealth": -0.25, "runeDrain": -0.25}}


def build():
    bosses = C.raw("bosses.json")
    known = {b["name"] for b in bosses}

    out = {}
    for b in bosses:
        if b.get("type") != "Boss":
            continue
        key = C.unit_key(b["name"])
        entry = {
            "unit": key,
            "displayName": b["name"],
            "tier": b.get("category"),
            "level": C.as_int(b.get("level")),
            # A scaffold, not a designed fight. Authoring replaces this.
            "authored": False,
            "phases": [{"at": 1.0, "abilities": b.get("spells", []) or []}],
            "modes": DEFAULT_MODES,
            "partyScaling": DEFAULT_PARTY_SCALING,
        }
        if b.get("minions"):
            entry["minionTypes"] = [C.unit_key(m) for m in b["minions"] if m in known]
        # Gaia carries the key with an empty value upstream, so test for a
        # non-empty table rather than mere presence.
        if b.get("empoweredStats"):
            entry["empowered"] = {k: C.num(v) for k, v in b["empoweredStats"].items()}
        elif "empoweredStats" in b:
            entry["empoweredUnknown"] = True
        for src, dst in (("limit", "partyLimit"), ("respawn", "respawnMinutes"),
                         ("timer", "enrageTimer")):
            v = b.get(src)
            if v not in (None, "None", ""):
                entry[dst] = C.num(v)
        if b.get("quote"):
            entry["bark"] = b["quote"]
        if b["name"] in SCRIPTED_HOOKS:
            entry["needsScriptedHook"] = SCRIPTED_HOOKS[b["name"]]
        out[key] = entry

    C.write_lua_table(os.path.join(C.DATA, "encounters.lua"), "Encounters", out)
    return out


if __name__ == "__main__":
    d = build()
    hooks = [v for v in d.values() if v.get("needsScriptedHook")]
    print("wrote data/encounters.lua (%d boss scaffolds)" % len(d))
    print("  %d with ability rosters, %d with minions, %d with an empowered stat set"
          % (sum(1 for v in d.values() if v["phases"][0]["abilities"]),
             sum(1 for v in d.values() if v.get("minionTypes")),
             sum(1 for v in d.values() if v.get("empowered"))))
    print("  %d flagged as needing a scripted hook:" % len(hooks))
    for h in hooks:
        print("    %-34s %s" % (h["displayName"][:34], h["needsScriptedHook"]))
    print("  ALL are authored=false scaffolds -- phase thresholds and timings "
          "are not in the source data and must be designed.")
