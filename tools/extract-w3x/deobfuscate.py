#!/usr/bin/env python3
"""Partial deobfuscator / analyser for the protected TWRPG war3map.j.

The map's protection does three things:
  1. renames every identifier to short meaningless tokens (V, E, vv, ov, ...)
  2. strips indentation and uses a mix of \\r and \\n as statement separators,
     so naive line-based tooling sees a handful of enormous lines
  3. leaves string literals, native calls and control flow fully intact

(3) is what makes analysis tractable. This tool normalises the separators,
re-indents, indexes every function, and provides targeted search so numeric
formulas can be recovered from the surviving arithmetic.

Usage:
  python3 deobfuscate.py format  <war3map.j> <out.j>
  python3 deobfuscate.py strings <war3map.j> <out.json>
  python3 deobfuscate.py index   <war3map.j> <out.json>
  python3 deobfuscate.py grep    <war3map.j> <pattern> [context_lines]
"""
import json
import re
import sys

BLOCK_OPEN = re.compile(r"^\s*(function\b|globals\b|loop\b|if\b.*\bthen$|else$|elseif\b.*\bthen$)")
BLOCK_CLOSE = re.compile(r"^\s*(endfunction\b|endglobals\b|endloop\b|endif\b|else$|elseif\b)")


def normalise(text):
    """Split on both separators, respecting string literals."""
    out, buf, in_str, esc = [], [], False, False
    for ch in text:
        if in_str:
            buf.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            buf.append(ch)
        elif ch in "\r\n":
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return [l.strip() for l in out]


def reindent(lines):
    out, depth = [], 0
    for l in lines:
        if not l:
            continue
        if BLOCK_CLOSE.match(l):
            depth = max(0, depth - 1)
        out.append("    " * depth + l)
        if BLOCK_OPEN.match(l):
            depth += 1
    return out


def cmd_format(src, dest):
    lines = reindent(normalise(open(src, encoding="utf-8", errors="replace").read()))
    open(dest, "w", encoding="utf-8").write("\n".join(lines))
    print("wrote %s: %d statements" % (dest, len(lines)))


def cmd_strings(src, dest):
    lines = normalise(open(src, encoding="utf-8", errors="replace").read())
    lit = re.compile(r'"((?:[^"\\]|\\.)*)"')
    found = []
    for i, l in enumerate(lines):
        for m in lit.finditer(l):
            s = m.group(1)
            if len(s) >= 2:
                found.append({"line": i, "text": s, "stmt": l[:200]})
    json.dump(found, open(dest, "w"), indent=1, ensure_ascii=False)
    uniq = {f["text"] for f in found}
    print("string literals: %d (%d unique)" % (len(found), len(uniq)))
    return found


def cmd_index(src, dest):
    lines = normalise(open(src, encoding="utf-8", errors="replace").read())
    fn = re.compile(r"^function\s+([A-Za-z0-9_]+)\s+takes\s+(.*?)\s+returns\s+(\S+)")
    funcs, cur = [], None
    for i, l in enumerate(lines):
        m = fn.match(l)
        if m:
            cur = {"name": m.group(1), "takes": m.group(2), "returns": m.group(3),
                   "start": i, "end": None, "calls": [], "natives": [], "strings": []}
            funcs.append(cur)
        elif cur is not None:
            if l.startswith("endfunction"):
                cur["end"] = i
                cur = None
            else:
                cur["calls"] += re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", l)
                cur["strings"] += re.findall(r'"((?:[^"\\]|\\.)*)"', l)
    for f in funcs:
        f["size"] = (f["end"] or f["start"]) - f["start"]
        f["calls"] = sorted(set(f["calls"]))
        f["natives"] = [c for c in f["calls"] if c[0].isupper()]
    json.dump(funcs, open(dest, "w"), indent=1, ensure_ascii=False)
    print("functions indexed: %d" % len(funcs))
    return funcs


def cmd_grep(src, pattern, ctx=2):
    lines = normalise(open(src, encoding="utf-8", errors="replace").read())
    rx = re.compile(pattern)
    hits = 0
    for i, l in enumerate(lines):
        if rx.search(l):
            hits += 1
            if hits > 60:
                break
            print("--- line %d ---" % i)
            for j in range(max(0, i - ctx), min(len(lines), i + ctx + 1)):
                print(("  > " if j == i else "    ") + lines[j][:220])
    print("\n%d matching statements (showing up to 60)" % hits)


def main():
    cmd = sys.argv[1]
    if cmd == "format":
        cmd_format(sys.argv[2], sys.argv[3])
    elif cmd == "strings":
        cmd_strings(sys.argv[2], sys.argv[3])
    elif cmd == "index":
        cmd_index(sys.argv[2], sys.argv[3])
    elif cmd == "grep":
        cmd_grep(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 2)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
