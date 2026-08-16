--- Encounter runtime: a declarative timeline interpreter for boss fights.
--
-- 39 bosses, 280 boss abilities, 45 minion types and 9 "mechanic" units that
-- exist only as encounter props. Per docs/02 §3.7 the design is a hybrid: a
-- declarative timeline covers roughly 80% of encounters as pure data, and the
-- remainder (Agareth's mini-game arena) drops into a scripted hook.
--
-- A definition looks like:
--
--   { phases = {
--       { at = 1.00, abilities = {...}, adds = {{ unit = "...", every = 30 }} },
--       { at = 0.50, statOverride = { damageResist = 75 },
--                    onEnter = {{ action = "startMinigame", arena = "..." }} },
--       { at = 0.10, onEnter = {{ action = "cast", ability = "armageddon" }} },
--     },
--     partyScaling = { ["8-10"] = { addHealth = -0.25 } },
--     modes = { hard = { damageResist = "+33%", dropRate = "+50%" },
--               practice = { damageDealt = -0.75, damageTaken = 3.0, drops = false } } }
--
-- Phases fire on descending HP fraction and never re-enter, so a boss healed
-- back above a threshold does not replay it.

local Encounters = require("data/encounters")

local Encounter = {}
Encounter.__index = Encounter

--- Difficulty modifiers, recovered in docs/00 §3.8.
Encounter.MODES = {
    normal = { damageDealt = 1.0, damageTaken = 1.0, dropRateBonus = 0.0, drops = true },
    hard = { damageDealt = 1.0, damageTaken = 1.0, dropRateBonus = 0.50,
             damageResistBonus = 0.33, drops = true },
    -- boss deals 75% less, takes 300% more, drops nothing
    practice = { damageDealt = 0.25, damageTaken = 3.0, dropRateBonus = 0.0, drops = false },
}

--- Actions the timeline can express. Anything not here needs a scripted hook.
Encounter.ACTIONS = {
    "cast", "summon", "spawnProp", "statOverride", "wipeMechanic", "instakill",
    "disableRevive", "setFog", "startMinigame", "teleport", "leashHeal", "bark",
}

function Encounter.New(unitKey, opts)
    opts = opts or {}
    local def = Encounters[unitKey]
    if not def then return nil, "no encounter definition for " .. tostring(unitKey) end

    local self = setmetatable({}, Encounter)
    self.unitKey = unitKey
    self.def = def
    self.mode = opts.mode or "normal"
    self.partySize = opts.partySize or 1
    self.participants = opts.participants or {}
    self.entered = {}          -- phase index -> true, so phases never replay
    self.phaseIndex = 0
    self.timers = {}
    self.reviveDisabled = false
    self.fog = false
    self.startedAt = opts.now or 0
    self.finished = false
    self.handlers = {}         -- action name -> function(self, step)
    return self
end

--- Register the engine-facing implementation of an action. Kept injectable so
--- the interpreter itself stays pure and testable.
function Encounter:On(action, fn)
    self.handlers[action] = fn
end

function Encounter:Mode()
    return Encounter.MODES[self.mode] or Encounter.MODES.normal
end

--- Party-size scaling. Keys are ranges like "8-10"; mechanics tune themselves to
--- headcount (docs/00 §3.8).
function Encounter:ScalingFor(size)
    local scaling = self.def.partyScaling
    if not scaling then return {} end
    for range, mods in pairs(scaling) do
        local lo, hi = string.match(range, "^(%d+)%-(%d+)$")
        if lo then
            if size >= tonumber(lo) and size <= tonumber(hi) then return mods end
        elseif tonumber(range) == size then
            return mods
        end
    end
    return {}
end

local function runSteps(self, steps)
    for _, step in ipairs(steps or {}) do
        local fn = self.handlers[step.action]
        if fn then
            fn(self, step)
        else
            -- Unhandled actions are loud: a silently skipped wipe mechanic is a
            -- boss that is simply wrong, and easy to miss in playtesting.
            print(string.format("[TWRPG] encounter %s: no handler for action '%s'",
                                self.unitKey, tostring(step.action)))
        end
    end
end

--- Drive the encounter. Call on a fixed tick with the boss's HP fraction.
function Encounter:Update(hpFraction, now)
    if self.finished then return end

    for i, phase in ipairs(self.def.phases or {}) do
        if not self.entered[i] and hpFraction <= (phase.at or 1.0) then
            self.entered[i] = true
            self.phaseIndex = i
            if phase.statOverride then
                runSteps(self, { { action = "statOverride", stats = phase.statOverride } })
            end
            runSteps(self, phase.onEnter)
            -- Recurring adds become timers owned by this phase.
            for _, add in ipairs(phase.adds or {}) do
                self.timers[#self.timers + 1] = {
                    every = add.every, next = now + (add.delay or add.every),
                    action = "summon", unit = add.unit, count = add.count or 1,
                }
            end
        end
    end

    for _, t in ipairs(self.timers) do
        if now >= t.next then
            runSteps(self, { { action = t.action, unit = t.unit, count = t.count } })
            t.next = now + t.every
        end
    end

    local enrage = self.def.enrageTimer
    if enrage and not self.enraged and (now - self.startedAt) >= enrage * 60 then
        self.enraged = true
        runSteps(self, { { action = "statOverride", stats = self.def.empowered or {} },
                         { action = "bark", text = "enrage" } })
    end
end

--- Loot eligibility: only players who were in the fight (docs/00 §3.7).
function Encounter:IsParticipant(playerId)
    for _, p in ipairs(self.participants) do
        if p == playerId then return true end
    end
    return false
end

--- Revival is explicitly forbidden in some situations -- during Fog, and after
--- failing an instakill mechanic (docs/00 §3.9).
function Encounter:CanRevive()
    return not (self.reviveDisabled or self.fog)
end

function Encounter:Finish()
    self.finished = true
    self.timers = {}
end

Encounter.Definitions = Encounters

return Encounter
