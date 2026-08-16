#!/usr/bin/env python3
"""Map mangled JASS handler functions back to their named abilities and items.

The protection destroys identifier names, but the spell system binds handlers to
ability rawcodes through a hashtable registry:

    function uex takes integer id, code handler returns nothing      // registrar
        call SaveTriggerHandle(Yv, Vx, id, CreateTrigger())
        call TriggerAddCondition(LoadTriggerHandle(Yv, Vx, id), Filter(handler))

    function uRx takes nothing returns boolean                       // dispatcher
        return TriggerEvaluate(LoadTriggerHandle(Yv, Vx, GetSpellAbilityId()))

Every `uex('A035', function tio)` call is therefore a literal
(ability rawcode -> handler function) edge. Rawcodes resolve to names via the
extracted object data, which gives a full mangled-function -> ability-name map.

Usage:
  python3 map_abilities.py <war3map.j> <extracted_dir> <research_raw_dir> <out.json>
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deobfuscate import normalise  # noqa: E402

REG_CALL = re.compile(r"\b([A-Za-z0-9_]+)\(\s*'([A-Za-z0-9]{4})'\s*,\s*function\s+([A-Za-z0-9_]+)\s*\)")
REG_DEF = re.compile(r"^function\s+([A-Za-z0-9_]+)\s+takes\s+integer\s+\w+\s*,\s*code\s+\w+\s+returns\s+nothing$")
SAVE_TRIG = re.compile(r"SaveTriggerHandle\(\s*(\w+)\s*,\s*\(*\s*(\w+)\s*\)*\s*,")
# the key's "getter" may take arguments, e.g. GetItemTypeId(GetManipulatedItem())
DISPATCH = re.compile(
    r"TriggerEvaluate\(\s*\(*LoadTriggerHandle\(\s*(\w+)\s*,\s*\(*\s*(\w+)\s*\)*\s*,\s*\(*([A-Za-z_]\w*)\s*\(")
EVENT_REG = re.compile(r"S_x\(\s*(EVENT_[A-Z_]+)\s*,\s*function\s+(\w+)\s*\)")
FUNC_DEF = re.compile(r"^function\s+([A-Za-z0-9_]+)\s+takes\s+(.*?)\s+returns\s+(\S+)$")

# damage-dealing entry points discovered in the pipeline analysis (doc 05)
DAMAGE_FNS = ["pFo", "pfo", "pGo", "pHo", "pjo", "pJo", "pko", "ppo"]
STAT_RX = re.compile(r"GetHero(Str|Agi|Int)\(")
NUMERIC_RX = re.compile(r"(?<![A-Za-z0-9_.])(\d+\.?\d*|\.\d+)")


def strip_colour(s):
    return re.sub(r"\|c[0-9a-fA-F]{8}|\|[rRnN]", "", s or "").strip()


def index_functions(lines):
    funcs, order, cur = {}, [], None
    for i, l in enumerate(lines):
        m = FUNC_DEF.match(l)
        if m:
            cur = m.group(1)
            funcs[cur] = {"name": cur, "start": i, "end": None,
                          "takes": m.group(2), "returns": m.group(3)}
            order.append(cur)
        elif cur and l.startswith("endfunction"):
            funcs[cur]["end"] = i
            cur = None
    for f in funcs.values():
        if f["end"] is None:
            f["end"] = f["start"]
    return funcs, order


def body(lines, f):
    return lines[f["start"] + 1:f["end"]]


def resolve_registrars(lines, funcs):
    """registrar -> hashtable parent key, and dispatcher -> (key, event)."""
    registrars = {}
    for name, f in funcs.items():
        if not REG_DEF.match(lines[f["start"]]):
            continue
        for l in body(lines, f):
            m = SAVE_TRIG.search(l)
            if m:
                registrars[name] = m.group(2)
                break

    key_to_getter, dispatcher_key = {}, {}
    for name, f in funcs.items():
        for l in body(lines, f):
            m = DISPATCH.search(l)
            if m:
                dispatcher_key[name] = m.group(2)
                key_to_getter[m.group(2)] = m.group(3)
    key_event = {}
    for l in lines:
        for m in EVENT_REG.finditer(l):
            ev, fn = m.group(1), m.group(2)
            if fn in dispatcher_key:
                key_event.setdefault(dispatcher_key[fn], set()).add(ev)
    return registrars, key_event, key_to_getter


def collect_reachable(fname, funcs, lines, call_index, depth=int(os.environ.get("MAP_DEPTH", 2))):
    """Handler body plus bodies of helper functions it calls, to a small depth."""
    seen, frontier, out = {fname}, [fname], []
    for _ in range(depth + 1):
        nxt = []
        for fn in frontier:
            f = funcs.get(fn)
            if not f:
                continue
            b = body(lines, f)
            out.extend(b)
            # sorted(): call_index values are sets, and Python randomises string
            # hashing per process — unsorted iteration makes which helpers land
            # inside the depth limit vary between runs, so output is not reproducible
            for callee in sorted(call_index.get(fn, ())):
                if callee not in seen and callee in funcs:
                    seen.add(callee)
                    nxt.append(callee)
        frontier = nxt
        if not frontier:
            break
    return out, seen


def extract_formulas(stmts):
    """Pull stat-scaling expressions and damage calls out of statements."""
    formulas, dmg_calls = [], []
    for l in stmts:
        if STAT_RX.search(l):
            expr = l.strip()
            if len(expr) < 400:
                formulas.append(expr)
        for fn in DAMAGE_FNS:
            if re.search(r"\b%s\(" % fn, l):
                dmg_calls.append(l.strip()[:400])
                break
    # dedupe, keep order
    def uniq(xs):
        s, o = set(), []
        for x in xs:
            if x not in s:
                s.add(x)
                o.append(x)
        return o
    return uniq(formulas)[:12], uniq(dmg_calls)[:12]


def main():
    script, extracted, raw_dir, out_path = sys.argv[1:5]
    lines = normalise(open(script, encoding="utf-8", errors="replace").read())
    funcs, order = index_functions(lines)
    print("functions: %d" % len(funcs))

    call_index = {}
    for name, f in funcs.items():
        calls = set()
        for l in body(lines, f):
            calls.update(re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", l))
        call_index[name] = sorted(calls)

    registrars, key_event, getters = resolve_registrars(lines, funcs)
    print("registrar functions: %d -> keys %s"
          % (len(registrars), sorted(set(registrars.values()))))

    # --- name tables
    obj_ab = {o["id"]: strip_colour(o["mods"].get("name", ""))
              for o in json.load(open(os.path.join(extracted, "abilities.json")))}
    obj_it = {o["id"]: strip_colour(o["mods"].get("name", ""))
              for o in json.load(open(os.path.join(extracted, "items.json")))}
    obj_un = {o["id"]: strip_colour(o["mods"].get("name", ""))
              for o in json.load(open(os.path.join(extracted, "units.json")))}
    comm_sk = {s["id"]: s for s in json.load(open(os.path.join(raw_dir, "skills.json")))}
    comm_bsk = {s["id"]: s for s in json.load(open(os.path.join(raw_dir, "skills-boss.json")))}
    comm_it = {s["id"]: s for s in json.load(open(os.path.join(raw_dir, "items.json")))}

    # --- registrations
    regs = []
    for i, l in enumerate(lines):
        for m in REG_CALL.finditer(l):
            reg, rid, handler = m.group(1), m.group(2), m.group(3)
            if reg not in registrars:
                continue
            key = registrars[reg]
            regs.append({"registrar": reg, "key": key,
                         "events": sorted(key_event.get(key, [])),
                         "keyedBy": getters.get(key),
                         "rawcode": rid, "handler": handler, "line": i})
    print("literal registrations: %d" % len(regs))

    results = []
    for r in regs:
        rid = r["rawcode"]
        sk = comm_sk.get(rid) or comm_bsk.get(rid)
        entry = {
            "rawcode": rid,
            "handler": r["handler"],
            "registrar": r["registrar"],
            "events": r["events"],
            "keyedBy": r["keyedBy"],
            "statement": r["line"],
            "kind": ("ability" if rid in obj_ab else
                     "item" if rid in obj_it else
                     "unit" if rid in obj_un else "unknown"),
            "mapName": obj_ab.get(rid) or obj_it.get(rid) or obj_un.get(rid) or None,
            "communityName": (sk or comm_it.get(rid, {})).get("name"),
            "heroClass": (sk or {}).get("heroClass"),
            "hotkey": (sk or {}).get("hotkey"),
            "caster": (sk or {}).get("caster"),
            "cooldown": (sk or {}).get("cooldown"),
        }
        f = funcs.get(r["handler"])
        if f:
            stmts, reached = collect_reachable(r["handler"], funcs, lines, call_index)
            formulas, dmg = extract_formulas(stmts)
            entry["handlerStatements"] = f["end"] - f["start"]
            entry["helpersInlined"] = len(reached) - 1
            entry["statFormulas"] = formulas
            entry["damageCalls"] = dmg
        results.append(entry)

    json.dump(results, open(out_path, "w"), indent=1, ensure_ascii=False)

    named = [r for r in results if r["mapName"]]
    comm = [r for r in results if r["communityName"]]
    withf = [r for r in results if r.get("statFormulas")]
    from collections import Counter
    print("\nresolved to a map object name : %d / %d" % (len(named), len(results)))
    print("matched community skill/item  : %d" % len(comm))
    print("handlers with stat formulas   : %d" % len(withf))
    print("by kind: %s" % dict(Counter(r["kind"] for r in results)))
    print("distinct rawcodes covered: %d" % len({r["rawcode"] for r in results}))
    print("distinct handlers        : %d" % len({r["handler"] for r in results}))
    print("\nwrote %s" % out_path)


if __name__ == "__main__":
    main()
