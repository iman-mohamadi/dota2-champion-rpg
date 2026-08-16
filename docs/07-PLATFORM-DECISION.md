# Platform Decision — Dota 2 Custom Game vs Standalone

> **DECIDED: Dota 2 custom game.** Windows access is available, which was the only blocker.
> The implementation plan is in [`08-DOTA2-IMPLEMENTATION-PLAN.md`](08-DOTA2-IMPLEMENTATION-PLAN.md).
> This document is retained as the rationale.

Question asked: **which needs less effort and no money?**

**Short answer: a Dota 2 custom game is far less effort — roughly half the work — and genuinely
costs $0 including servers. But it has one hard blocker for you specifically: the tools are
Windows-only, and you are on Linux.**

Everything below is sourced. Where I am inferring rather than citing, I say so.

---

## 1. The honest headline

For *this particular game*, Dota 2 is an unusually good fit — better than it would be for
almost any other project. TWRPG is a Warcraft III custom map: heroes with QWER+passive bars,
items that grant abilities, fixed inventory slots, buff/debuff stacking, armour types,
click-to-move, co-op raid encounters. **Dota 2 is the closest commercially-available engine to
Warcraft III that exists.** The mental model transfers almost 1:1; a standalone build means
rebuilding all of that from nothing.

There is also direct precedent for the exact genre. **Roshpit Champions** is a Dota 2 custom
game with 12 classes, hundreds of items, branching skill trees, three acts, and **persistent
character/item saves across sessions** — structurally the same product as TWRPG. It works.

---

## 2. Effort comparison

The roadmap in `03-ROADMAP.md` was written for a standalone build. Here is what Dota 2 deletes
from it outright:

| Roadmap item | Standalone | Dota 2 custom game |
|---|---|---|
| **Phase 4 — Multiplayer foundation** (6–8 wks) | build authoritative server, netcode, prediction, reconciliation | **free** — engine is already authoritative multiplayer |
| Server hosting | rent VPS, scale, maintain | **free** — Valve hosts worldwide, including matchmaking and lobbies |
| Accounts / identity | build account system | **free** — Steam identity |
| Party & lobby system | build it | **free** — built in |
| **Art, models, animation, VFX, icons, sound** | the single largest cost for a small team | **free** — full Dota 2 asset library usable inside custom games |
| Pathfinding, targeting, AoE selection, projectiles | build it | **free** |
| Ability/cooldown/buff framework | build it (tech plan §3.5) | **mostly free** — Dota's ability system is very close to WC3's |
| Inventory + item-grants-ability | build it | **mostly free** — same model as Dota items |
| Discovery / audience | hardest unsolved problem for indies | **partly free** — Arcade browser with a "Suggested Games" rotation |
| Anti-cheat | your problem, at 0.5% drop rates | server-authoritative by default |
| Damage pipeline, stacking slots, drop tables, crafting, Codex | **you build this either way** | **you build this either way** |
| Zones/terrain | author from extracted heightmap | author in Hammer from extracted heightmap |
| Persistence | your DB | **you still need an external DB** (see §4) |

My estimate: the Vertical Slice (Scope A) drops from **~2–3 months to ~3–5 weeks**, and the
Core Game (Scope B) from ~12–18 months to roughly **6–9 months**. The content work — 765
items, 486 recipes, 39 encounters, ability transcription — is unchanged, because that is
data entry against the dataset we already extracted, not engine work.

Note the asymmetry: **everything Dota 2 gives you free is exactly what I flagged as the top
project risks** — art cost, multiplayer retrofit, and hosting.

---

## 3. Money

| | Dota 2 custom game | Standalone |
|---|---|---|
| Engine | $0 | $0 (Godot, no royalties) |
| Dev tools | $0 (Workshop Tools DLC is free) | $0 |
| Publishing | $0 | $0 on itch.io; **$100** Steam Direct (refunded after $1,000 revenue) |
| Server hosting | **$0 — Valve pays** | $5–20/mo VPS minimum, more as you scale |
| Art assets | **$0 — use Dota's** | your biggest real cost |
| Persistence backend | $0 on a free tier, then small | $0 on a free tier, then small |
| **Realistic cost to a playable co-op build** | **$0** | **$0–100 + ongoing hosting** |

Both can start at zero. Only Dota 2 stays at zero once other people are playing, because
Valve absorbs the server bill. That is the strongest "needs no money" argument in the whole
comparison.

### The monetization catch

If you ever want income, this flips hard:

- The Dota Workshop license is **strictly non-commercial**. In August 2023 Valve's legal team
  gave custom-game developers until **17 August 2023** to stop all monetization — third-party
  payments, Patreon, battle passes, subscriptions, virtual items, currencies, skins — quoting:
  *"The license provided for the DOTA Workshop is strictly non-commercial."*
- The **only** sanctioned path is a **Custom Game Pass**, which is *curated by Valve*: they
  select "only games which have already established a sizeable community and are mature enough
  to offer good value." Revenue share is Steam's standard rate. Roshpit Champions was the
  launch title for it.
- So: you cannot plan on revenue. You might be granted it later if the game succeeds.

Standalone, you own everything and can charge whatever you like. **If this is a hobby/tribute
project, that does not matter. If it is meant to earn, it matters enormously.**

---

## 4. What Dota 2 costs you in freedom and capability

Honest list of what you give up:

1. **Windows-only tools — the hard blocker.** The Workshop Tools require 64-bit Windows and a
   Direct3D 11 GPU. There is no Linux build, and community reporting is that there may never
   be one. A Proton workaround exists (`13k/dota2-tools-proton`) but it was **archived in
   August 2023** and is unmaintained — treat it as unlikely to work against current Dota 2.
   **You are on Linux. This is the single biggest practical obstacle**, and it is a real cost
   in either money (a Windows machine/licence) or hassle (dual-boot, or a VM with GPU
   passthrough since D3D11 is required).
2. **Players need Dota 2 installed.** You have traded a dependency on Warcraft III for a
   dependency on Dota 2. Dota 2 is free-to-play, so it is a *cheaper* dependency — but your
   original stated goal was "we don't need Warcraft 3", and this does not literally achieve
   independence. Worth deciding whether "free dependency" satisfies that intent.
3. **You don't own the platform.** Terms can change; the 2023 monetization crackdown is proof
   they do. Valve can deprecate custom games at any time.
4. **The audience is shrinking.** Custom games peaked with Auto Chess; the biggest ones
   reportedly once exceeded 10,000 concurrent and now sit under ~7,000, and reporting notes a
   meaningful share of custom-game "players" are bots, with Valve banning inactive accounts
   used in custom modes. Dota 2 overall is still large (~550k concurrent, ~860k 24h peak),
   so the funnel exists — but it is not a growth platform.
5. **Engine constraints.** Source 2 networks on the order of ~2,048 entities; TWRPG's larger
   fights plus minions plus mechanic props will need budgeting. Custom games support up to
   **24 players**, comfortably above TWRPG's 10.
6. **Persistence is still your problem.** Dota 2 has no built-in cross-match save. You use
   `CreateHTTPRequestScriptVM` to talk to an external database (Firebase and similar are the
   common pattern), plus `SetCustomGameAccountRecordSaveFunction` for Valve-side records.
   Free tiers cover a hobby project. Note this is *less* secure than a real authoritative
   backend, which matters at 0.5% drop rates.
7. **New tech to learn:** Lua for gameplay and **Panorama** (XML/CSS/JavaScript) for UI. Given
   UI is ~30% of this game's client work, that learning curve is not trivial — though
   TypeScript templates and the ModDota docs are mature.
8. **Dota-shaped assumptions.** Some things will fight you: Dota's fixed 6+backpack inventory
   vs TWRPG's 24-slot bag and 24-slot storage, Dota's stat model, its attack/armour system.
   Workable, but expect friction.

---

## 5. The option you didn't ask about, and why I'm not recommending it

Open-source Warcraft III engine reimplementations exist and are active:

- **Warsmash** (`Retera/WarsmashModEngine`) — a largely clean-room Java/LibGDX reimplementation
  that emulates WC3: TFT gameplay and loads `.w3x` maps directly.
- **Open-Realm** (`corepunch/open-realm`) — a C reimplementation targeting **Linux and macOS**,
  reading assets straight from MPQ, still actively developed as of May 2026.

Tempting, because in principle you *run the existing map* with no porting at all. But:

- Both **require you to own Warcraft III and supply its assets**, so they do not remove the
  WC3 dependency — they relocate it. That fails your original requirement.
- It solves none of the legal asset problem.
- TWRPG v0.65b is a protected, obfuscated, 7 MB-script map using heavy custom scripting. The
  odds of it running correctly on a reimplementation are low, and debugging that is not a
  project you control. *(This is my assessment, not something I tested.)*

Worth knowing about; not the answer.

---

## 6. Recommendation

**If you can get access to a Windows machine: build it as a Dota 2 custom game.**

For this specific project the case is unusually strong — closest engine to the original,
proven precedent in Roshpit Champions, free hosting forever, free art, and it deletes the
three biggest risks in the standalone plan. Effort roughly halves. Cost is genuinely $0.

Do it as a **tribute/non-commercial project**, which is what the Workshop license permits
anyway, and which also lowers the copyright risk around TWRPG's names and content.

**If Windows is not realistically available, or you want to own and possibly sell this:**
build standalone in Godot on Linux, exactly as `02-TECH-PLAN.md` specifies. It is more work,
but it is work you can actually start today on the machine you have.

### The one question that decides it

Can you get a Windows install with a D3D11 GPU — dual-boot, spare machine, or VM with
passthrough? Everything else in this comparison favours Dota 2; that single item is the
blocker. A Windows VM without GPU passthrough will not be sufficient.

### Middle path, if you want to de-risk

The research, the extracted dataset, and the content tables in this repo are **platform-neutral**.
765 items, 486 recipes, 39 encounters, the EXP curve, the armour formula, the damage pipeline,
zone geometry and the ability handler map are all just data. Phase 1 of the roadmap — the
content pipeline — is worth building regardless of target, and none of it is wasted whichever
way you go. So: **you can defer this decision until after Phase 1** without losing time.

What *would* change is Phase 2 onward. Under Dota 2, much of the simulation core (§2 table)
stops being something you write.

---

## 7. Sources

- [Dota 2 Workshop Tools — Valve Developer Community](https://developer.valvesoftware.com/wiki/Dota_2_Workshop_Tools)
- [Dota Workshop Tools FAQ](https://developer.valvesoftware.com/wiki/Dota_2_Workshop_Tools/Dota_Workshop_Tools_FAQ)
- [ModDota — Getting Started](https://moddota.com/getting-started) · [ModDota API docs](https://docs.moddota.com/lua_server/)
- [Valve asks Dota 2 players to stop monetizing their custom games — Game Developer](https://www.gamedeveloper.com/game-platforms/valve-asks-i-dota-2-i-players-to-stop-monetizing-their-custom-games)
- [Valve Cracks Down on Dota 2 Custom Game Monetization — GameLeap](https://www.gameleap.com/articles/valve-cracks-down-on-dota-2-custom-game-monetization)
- [Dota 2 Custom Game Pass FAQ](https://www.dota2.com/customgamepassfaq)
- [Valve to add paid Custom Game Pass to Dota 2 — PC Gamer](https://www.pcgamer.com/valve-custom-game-pass-interview/)
- [The best Dota 2 custom games (Roshpit Champions) — PC Gamer](https://www.pcgamer.com/best-dota-2-custom-games/)
- [Dota 2 to Increase Custom Game Mode Player Limit to 24 — PC Perspective](https://pcper.com/2015/08/dota-2-to-increase-custom-game-mode-player-limit-to-24/)
- [Entity limit — Valve Developer Community](https://developer.valvesoftware.com/wiki/Entity_limit)
- [dota2-tools-proton (archived Aug 2023)](https://github.com/13k/dota2-tools-proton) · [Proton issue #318](https://github.com/ValveSoftware/Proton/issues/318)
- [Dota 2 live player count](https://activeplayer.io/dota-2/) · [Custom Game Stats](http://www.customgamestats.com/)
- [Reasons for the first major drop in Dota 2 player count — CyberScore](https://cyberscore.live/en/news/dota2-player-count-drop-reasons-first-in-7-years/)
- [Save/Load via Firebase — DotaRota tutorial](https://dotarota.com/en/resources/tutorials/firebase-save-load/)
- [Steam Direct fee guidance](https://www.thegamemarketer.com/insight-posts/how-to-publish-a-game-on-steam-guide) · [itch.io pricing](https://itch.io/docs/creators/pricing)
- [Warsmash Mod Engine](https://github.com/Retera/WarsmashModEngine) · [Open-Realm](https://github.com/corepunch/open-realm)
