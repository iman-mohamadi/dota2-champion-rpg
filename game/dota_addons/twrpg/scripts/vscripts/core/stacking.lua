--- Categorical buff/debuff stacking.
--
-- TWRPG does not add effects together. Each effect kind (Armor Reduction,
-- Damage Dealt, ...) has lettered slots, and:
--
--   * within one (kind, slot): only the STRONGEST instance applies
--   * across slots of the same kind: they MULTIPLY
--   * slots marked Stackable: instances SUM
--
-- Two Type-A armour reductions therefore do nothing extra; a Type-A plus a
-- Type-B do. This is the game's main balance lever -- patch 62v rebalanced
-- Merchant by moving its debuff out of Type-A so it would stack with
-- everything -- so `slot` is always read from data, never hardcoded here.
--
-- See docs/00 §3.2 and data/stacking.lua.

local Stacking = {}
Stacking.__index = Stacking

--- A container of active effects on one unit.
function Stacking.New()
    return setmetatable({ effects = {} }, Stacking)
end

--- Add or refresh an effect.
-- @param e table {kind, slot, magnitude, sourceId, stackable, duration, expiresAt}
function Stacking:Apply(e)
    assert(e.kind, "effect needs a kind")
    assert(e.slot, "effect needs a slot -- read it from data/stacking.lua, do not guess")
    assert(e.sourceId, "effect needs a sourceId so it can be refreshed/removed")
    local bucket = self.effects[e.kind]
    if not bucket then
        bucket = {}
        self.effects[e.kind] = bucket
    end
    local slot = bucket[e.slot]
    if not slot then
        slot = {}
        bucket[e.slot] = slot
    end
    slot[e.sourceId] = e
    return e
end

function Stacking:Remove(kind, slot, sourceId)
    local bucket = self.effects[kind]
    if bucket and bucket[slot] then
        bucket[slot][sourceId] = nil
    end
end

function Stacking:RemoveBySource(sourceId)
    for _, bucket in pairs(self.effects) do
        for _, slot in pairs(bucket) do
            slot[sourceId] = nil
        end
    end
end

--- Drop everything whose expiry has passed. `now` is game time.
function Stacking:Expire(now)
    local removed = 0
    for _, bucket in pairs(self.effects) do
        for _, slot in pairs(bucket) do
            for id, e in pairs(slot) do
                if e.expiresAt and e.expiresAt <= now then
                    slot[id] = nil
                    removed = removed + 1
                end
            end
        end
    end
    return removed
end

--- Resolve one slot to a single magnitude.
local function resolveSlot(slotTable)
    local best, sum, stackable = 0, 0, false
    for _, e in pairs(slotTable) do
        local m = e.magnitude or 0
        if e.stackable then
            stackable = true
            sum = sum + m
        elseif math.abs(m) > math.abs(best) then
            best = m
        end
    end
    return stackable and (sum + best) or best
end

--- Total multiplier for an effect kind: (1+a) * (1+b) * ...
-- Use for multiplicative kinds such as Damage Dealt or Armor Reduction.
function Stacking:Multiplier(kind)
    local bucket = self.effects[kind]
    if not bucket then return 1.0 end
    local mult = 1.0
    for _, slotTable in pairs(bucket) do
        mult = mult * (1.0 + resolveSlot(slotTable))
    end
    return mult
end

--- Total additive magnitude for an effect kind: a + b + ...
-- Use for flat kinds such as Attack Damage (Fixed) or Main Stat.
function Stacking:Sum(kind)
    local bucket = self.effects[kind]
    if not bucket then return 0.0 end
    local total = 0.0
    for _, slotTable in pairs(bucket) do
        total = total + resolveSlot(slotTable)
    end
    return total
end

--- The magnitude contributed by a single slot, for inspection/tooltips.
function Stacking:SlotValue(kind, slot)
    local bucket = self.effects[kind]
    if not bucket or not bucket[slot] then return 0.0 end
    return resolveSlot(bucket[slot])
end

function Stacking:Has(kind)
    local bucket = self.effects[kind]
    if not bucket then return false end
    for _, slotTable in pairs(bucket) do
        if next(slotTable) then return true end
    end
    return false
end

return Stacking
