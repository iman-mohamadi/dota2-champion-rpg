--- The Codex: turning TWRPG's implicit goals into trackable objectives.
--
-- The original has essentially no quests (docs/00 §4). Progression runs on
-- gated boss summons, recipe completion and world-state chains, none of which
-- are ever surfaced to the player. Every requirement already exists as data, so
-- showing it costs nothing in fidelity -- this is the one place the design
-- deliberately exceeds the original (docs/01 §7).
--
-- Three tracks:
--   Hunt       boss summon requirements, generated from `conditions`
--   Forge      recipe completion, computed live from the crafting graph
--   Chronicle  the scripted world chains (Hell Invasion, Avalon)

local CodexData = require("data/codex")
local Crafting = require("systems/crafting")
local Units = require("data/units")

local Codex = {}
Codex.__index = Codex

function Codex.New()
    return setmetatable({
        killed = {},        -- unitKey -> true
        summoned = {},      -- unitKey -> true
        worldState = {},    -- arbitrary flags set by encounters
        pinned = nil,       -- the Forge target
    }, Codex)
end

function Codex:RecordKill(unitKey)
    self.killed[unitKey] = true
end

function Codex:RecordSummon(unitKey)
    self.summoned[unitKey] = true
end

function Codex:SetFlag(flag, value)
    self.worldState[flag] = value == nil and true or value
end

-- ------------------------------------------------------------------- Hunt

--- Evaluate one objective against the player's current state.
-- Returns done, progress ("3/6"), and a human-readable label.
function Codex:EvaluateObjective(obj, ctx)
    if obj.kind == "level" then
        local have = ctx.level or 1
        return have >= obj.min, string.format("%d/%d", math.min(have, obj.min), obj.min),
               "Reach level " .. obj.min
    elseif obj.kind == "item" then
        local have = ctx.inventory and ctx.inventory:Count(obj.item) or 0
        local label = "Obtain " .. obj.count .. "x " .. obj.item
        if obj.mustCraft then label = "Craft " .. obj.item end
        if obj.locationHint then label = label .. " (" .. obj.locationHint .. ")" end
        return have >= obj.count, string.format("%d/%d", math.min(have, obj.count), obj.count),
               label
    elseif obj.kind == "prerequisiteSummon" then
        local key = obj.target
        local done = self.summoned[key] or self.worldState[key] or false
        return done and true or false, done and "1/1" or "0/1", "Summon " .. obj.target
    elseif obj.kind == "summonedBy" then
        return false, "-", "Summoned by " .. obj.unit
    end
    -- freeform: a real instruction we could not structure. Show it verbatim
    -- rather than pretending it is tracked.
    return false, "-", obj.text or "?"
end

--- Progress on one boss's summon requirements.
function Codex:HuntEntry(unitKey, ctx)
    local entry = CodexData.hunt[unitKey]
    if not entry then return nil end
    local steps, done = {}, 0
    local trackable = 0
    for _, obj in ipairs(entry.objectives or {}) do
        local ok, progress, label = self:EvaluateObjective(obj, ctx)
        local tracked = obj.kind ~= "freeform" and obj.kind ~= "summonedBy"
        if tracked then
            trackable = trackable + 1
            if ok then done = done + 1 end
        end
        steps[#steps + 1] = { label = label, done = ok, progress = progress,
                              tracked = tracked, kind = obj.kind }
    end
    return {
        target = unitKey,
        displayName = entry.displayName,
        tier = entry.tier,
        level = entry.level,
        location = entry.location,
        partyLimit = entry.partyLimit,
        steps = steps,
        complete = trackable > 0 and done == trackable,
        trackedDone = done,
        trackedTotal = trackable,
        defeated = self.killed[unitKey] or false,
        -- surfaced so the UI can say "this one has unstructured steps"
        confidence = entry.confidence,
        rawConditions = entry.rawConditions,
    }
end

--- Every hunt, optionally filtered to those the player could act on now.
function Codex:Hunts(ctx, onlyAvailable)
    local out = {}
    for key in pairs(CodexData.hunt) do
        local e = self:HuntEntry(key, ctx)
        if e and (not onlyAvailable or not e.defeated) then
            out[#out + 1] = e
        end
    end
    table.sort(out, function(a, b)
        if a.level ~= b.level then return (a.level or 0) < (b.level or 0) end
        return (a.displayName or "") < (b.displayName or "")
    end)
    return out
end

-- ------------------------------------------------------------------ Forge

--- Pin a craft target; the plan is recomputed from the live inventory.
function Codex:Pin(itemKey)
    self.pinned = itemKey
end

function Codex:ForgePlan(ctx)
    if not self.pinned or not ctx.inventory then return nil end
    local plan = Crafting.ForgePlan(ctx.inventory, self.pinned)
    -- annotate each missing leaf with which bosses drop it
    for _, need in ipairs(plan.need) do
        if need.droppedBy then
            need.sources = {}
            for _, src in ipairs(need.droppedBy) do
                need.sources[#need.sources + 1] = src
            end
        end
    end
    plan.craftableNow = select(1, Crafting.CanCraft(ctx.inventory, self.pinned))
    return plan
end

-- -------------------------------------------------------------- Chronicle

function Codex:Chronicle()
    local out = {}
    for id, chain in pairs(CodexData.chronicle) do
        local steps, done = {}, 0
        for _, step in ipairs(chain.steps) do
            local complete = false
            local req = step.requires
            if req then
                if req.kind == "boss" then
                    complete = self.killed[req.unit] or false
                elseif req.kind == "unit" then
                    complete = self.worldState[req.unit] or false
                end
            else
                complete = self.worldState[step.id] or false
            end
            if complete then done = done + 1 end
            steps[#steps + 1] = { id = step.id, text = step.text, done = complete }
        end
        out[#out + 1] = { id = id, displayName = chain.displayName, steps = steps,
                          done = done, total = #chain.steps,
                          complete = done == #chain.steps }
    end
    table.sort(out, function(a, b) return a.id < b.id end)
    return out
end

-- ------------------------------------------------------------ persistence

function Codex:Serialise()
    return { killed = self.killed, summoned = self.summoned,
             worldState = self.worldState, pinned = self.pinned }
end

function Codex.Deserialise(data)
    local c = Codex.New()
    if type(data) == "table" then
        c.killed = data.killed or {}
        c.summoned = data.summoned or {}
        c.worldState = data.worldState or {}
        c.pinned = data.pinned
    end
    return c
end

return Codex
