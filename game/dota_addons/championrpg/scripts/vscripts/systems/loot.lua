--- Drop tables, the Wish pity system, and participant-gated loot chests.
--
-- Rules from the original (docs/00 §3.7):
--   * equipment/material drop rates sit at 0.5-1%, icons at 0.15-1%
--   * Wish: nominate one drop. Nothing else drops, but the wished item's rate
--     is increased by 100% (i.e. doubled).
--   * Hard mode: +50% drop rate.
--   * Arcana-tier bosses and above drop into a SHARED loot chest, lootable only
--     by fight participants -- explicitly not personal loot. Below that tier,
--     drops hit the ground.
--   * The chest disappears once every participant has taken or passed.
--
-- Rolls are server-side only. At a 0.5% drop rate anything client-adjacent is
-- an exploit target.

local Units = require("data/units")
local Items = require("data/items")

local Loot = {}

-- Bosses at these tiers use the shared chest rather than ground drops.
Loot.CHEST_TIERS = { Late = true, Endgame = true }

Loot.HARD_MODE_DROP_BONUS = 0.50   -- +50%
Loot.WISH_DROP_BONUS = 1.00        -- +100%

--- Effective drop chance for one item, as a fraction (0.008 = 0.8%).
function Loot.Chance(itemKey, opts)
    opts = opts or {}
    local def = Items[itemKey]
    if not def or not def.dropRate then return 0 end
    local rate = def.dropRate
    if type(rate) == "table" then rate = rate[1] or 0 end
    rate = rate / 100.0                        -- source stores percentages
    if opts.hardMode then
        rate = rate * (1.0 + Loot.HARD_MODE_DROP_BONUS)
    end
    if opts.wish == itemKey then
        rate = rate * (1.0 + Loot.WISH_DROP_BONUS)
    end
    return math.min(1.0, rate)
end

--- Roll a boss's drop table.
-- @param rng function returning [0,1); inject it so tests are deterministic
-- @param opts { hardMode = bool, wish = itemKey, practiceMode = bool }
function Loot.Roll(unitKey, rng, opts)
    opts = opts or {}
    -- Practice mode drops nothing at all.
    if opts.practiceMode then return {} end

    local unit = Units[unitKey]
    if not unit or not unit.drops then return {} end

    local dropped = {}
    for _, itemKey in ipairs(unit.drops) do
        -- Under a Wish, only the wished item can drop at all.
        local eligible = (opts.wish == nil) or (itemKey == opts.wish)
        if eligible then
            local chance = Loot.Chance(itemKey, opts)
            if chance > 0 and rng() < chance then
                dropped[#dropped + 1] = itemKey
            end
        end
    end
    return dropped
end

--- Does this boss use a shared chest?
function Loot.UsesChest(unitKey)
    local unit = Units[unitKey]
    return unit ~= nil and Loot.CHEST_TIERS[unit.category] == true
end

-- ------------------------------------------------------------------- chest

local Chest = {}
Chest.__index = Chest

--- @param participants array of playerIds that were in the fight
function Loot.CreateChest(unitKey, contents, participants)
    local self = setmetatable({}, Chest)
    self.unit = unitKey
    self.contents = contents or {}
    self.participants = {}
    for _, pid in ipairs(participants or {}) do self.participants[pid] = true end
    self.resolved = {}      -- playerId -> "taken" | "passed"
    self.hardMode = false
    return self
end

function Chest:IsEligible(playerId)
    return self.participants[playerId] == true
end

function Chest:Take(playerId, itemKey)
    if not self:IsEligible(playerId) then return false, "not a participant" end
    if self.resolved[playerId] then return false, "already resolved" end
    for i, key in ipairs(self.contents) do
        if key == itemKey then
            table.remove(self.contents, i)
            self.resolved[playerId] = "taken"
            return true, itemKey
        end
    end
    return false, "not in chest"
end

function Chest:Pass(playerId)
    if not self:IsEligible(playerId) then return false, "not a participant" end
    if self.resolved[playerId] then return false, "already resolved" end
    self.resolved[playerId] = "passed"
    return true
end

--- The chest disappears once everyone has taken or abandoned.
function Chest:IsFinished()
    for pid in pairs(self.participants) do
        if not self.resolved[pid] then return false end
    end
    return true
end

Loot.Chest = Chest

return Loot
