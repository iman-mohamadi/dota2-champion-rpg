--- Stat aggregation: base + allocation + equipment + effects -> derived stats.
--
-- Layered exactly as docs/02 §3.2 describes: a BaseStats layer that only changes
-- when allocation or equipment changes, and a DerivedStats layer recomputed on a
-- dirty flag. Nothing recomputes per frame.
--
-- What TWRPG does NOT do, and this must not either (docs/05 §3):
--   * STR grants no HP, AGI no armour or attack speed, INT no mana.
--     Every stock attribute effect is zeroed in addon_game_mode.lua.
--   * levelling grants no stats at all -- only stat points to allocate.
-- The single surviving attribute effect is primary attribute -> attack damage,
-- at 3.0 per point (war3mapMisc StrAttackBonus).
--
-- Attribute rollup, from the item vocabulary:
--   str  = base + allocated + item.str + item.allstat + item.mainstat(if primary)
-- `allstat` feeds all three; `mainstat` feeds only the hero's primary.
--
-- ASSUMPTION, flagged for in-game verification: percentage stats from multiple
-- items are summed additively (two 5% skill damage items give 10%). The source
-- data does not state this either way. If it turns out to be multiplicative,
-- change SumFraction below -- it is the only place it is decided.

local Constants = require("data/constants")
local StatDefs = require("data/stats")
local Items = require("data/items")

local Stats = {}
Stats.__index = Stats

local ATTR_FOR_MAINSTAT = { STR = "str", AGI = "agi", INT = "int" }

function Stats.New(heroDef, level)
    local self = setmetatable({}, Stats)
    self.heroDef = heroDef or {}
    self.level = level or 1
    self.allocation = { str = 0, agi = 0, int = 0 }
    self.equipped = {}          -- slot -> itemKey
    self.effects = nil          -- optional core/stacking instance
    self.base = {}
    self.derived = {}
    self.dirty = true
    return self
end

--- Total allocated points must never exceed the run's budget.
function Stats:SetAllocation(str, agi, int)
    local total = (str or 0) + (agi or 0) + (int or 0)
    if total > Constants.STAT_POINTS_TOTAL then
        return false, "exceeds " .. Constants.STAT_POINTS_TOTAL .. " stat points"
    end
    self.allocation = { str = str or 0, agi = agi or 0, int = int or 0 }
    self.dirty = true
    return true
end

function Stats:PointsSpent()
    return self.allocation.str + self.allocation.agi + self.allocation.int
end

function Stats:PointsAvailable()
    -- Points are granted by levelling; the run totals STAT_POINTS_TOTAL at cap.
    local perLevel = Constants.STAT_POINTS_TOTAL / (Constants.MAX_HERO_LEVEL - 1)
    local earned = math.floor(perLevel * (self.level - 1) + 0.0001)
    return earned - self:PointsSpent()
end

function Stats:SetEquipped(slot, itemKey)
    self.equipped[slot] = itemKey
    self.dirty = true
end

function Stats:SetEffects(stacking)
    self.effects = stacking
    self.dirty = true
end

function Stats:Invalidate()
    self.dirty = true
end

--- Sum one field across every equipped item.
function Stats:SumEquipment(field)
    local total = 0
    for _, itemKey in pairs(self.equipped) do
        local def = Items[itemKey]
        local s = def and def.stats
        if s and s[field] then total = total + s[field] end
    end
    return total
end

--- The single decision point for how item percentages combine. See header.
function Stats:SumFraction(field)
    return self:SumEquipment(field)
end

local function primaryField(heroDef)
    return ATTR_FOR_MAINSTAT[heroDef.mainStat or "STR"] or "str"
end

function Stats:Recompute()
    local hero = self.heroDef
    local primary = primaryField(hero)

    local allstat = self:SumEquipment("allstat")
    local mainstat = self:SumEquipment("mainstat")

    local attrs = {}
    for _, f in ipairs({ "str", "agi", "int" }) do
        attrs[f] = (self.allocation[f] or 0) + self:SumEquipment(f) + allstat
    end
    attrs[primary] = attrs[primary] + mainstat

    local d = {}
    d.str, d.agi, d.int = attrs.str, attrs.agi, attrs.int
    d.primaryAttribute = attrs[primary]

    -- flat pools: no attribute contribution, by design
    d.hp = Constants.HERO_BASE_HP + self:SumEquipment("hp")
    d.mp = self:SumEquipment("mp")
    d.hpregen = self:SumEquipment("hpregen")
    d.mpregen = self:SumEquipment("mpregen")
    d.armor = self:SumEquipment("armor")
    d.movespeed = Constants.HERO_BASE_MOVESPEED + self:SumEquipment("movespeed")

    -- attack damage is weapon damage plus primary attribute * 3.0
    local perPoint = 3.0
    for _, a in ipairs(Constants.ATTRIBUTE_DERIVED) do
        if a.key == "StrAttackBonus" then perPoint = a.value end
    end
    d.attackDamage = self:SumEquipment("damage") + d.primaryAttribute * perPoint

    -- fractional stats
    for field, def in pairs(StatDefs.fields) do
        if def.kind == "fraction" or def.kind == "multiplier" then
            d[field] = self:SumFraction(field)
        end
    end

    -- status effects layer on top, using their categorical slots
    if self.effects then
        d.damagedealtpercent = (d.damagedealtpercent or 0)
            + (self.effects:Multiplier("Damage Dealt") - 1.0)
        d.attackspeedpercent = (d.attackspeedpercent or 0)
            + (self.effects:Multiplier("Attack Speed") - 1.0)
        d.skilldamagepercent = (d.skilldamagepercent or 0)
            + (self.effects:Multiplier("Skill Damage") - 1.0)
        d.armor = d.armor * (1.0 - self.effects:Sum("Armor Reduction"))
        d.str = d.str + self.effects:Sum("All Stats")
        d.agi = d.agi + self.effects:Sum("All Stats")
        d.int = d.int + self.effects:Sum("All Stats")
        d.primaryAttribute = d.primaryAttribute + self.effects:Sum("Main Stat")
    end

    self.derived = d
    self.dirty = false
    return d
end

function Stats:All()
    if self.dirty then self:Recompute() end
    return self.derived
end

function Stats:Get(field)
    return self:All()[field] or 0
end

--- Bundle for core/damage.lua's target-side lookups.
function Stats:AsTarget()
    local d = self:All()
    return {
        armor = d.armor,
        magicResist = (d.mdpercent or 0) * 100.0,
        damageResist = (d.drpercent or 0) * 100.0,
        damageTakenPercent = d.dtpercent or 0,
    }
end

return Stats
