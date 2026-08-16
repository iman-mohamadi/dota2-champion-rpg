--- Custom inventory: 24-slot bag plus 24-slot storage.
--
-- Dota gives 6 + 3 backpack + 6 stash, which is nowhere near enough, so items
-- live here as data and Dota's native slots are used only for the small
-- "equipped" bar (docs/08 §3.2).
--
-- Rules taken from the original (docs/00 §3.4, §6.3):
--   * bag 24 slots, storage 24 slots (storage expandable one slot at a time)
--   * stacks cap at 5
--   * overflow chain on acquire: bag -> storage -> ground, never destroyed
--   * equipment slots: weapon, headwear, armor, accessory, wings
--   * the weapon slot is class-gated by the hero's `wearable` list
--
-- Pure data manipulation with no engine calls, so it is testable outside Dota.

local Inventory = {}
Inventory.__index = Inventory

Inventory.BAG_SLOTS = 24
Inventory.STORAGE_SLOTS = 24
Inventory.MAX_STACK = 5
Inventory.EQUIP_SLOTS = { "weapon", "headwear", "armor", "accessory", "wings" }

local function newGrid(n)
    local g = {}
    for i = 1, n do g[i] = nil end
    return g
end

function Inventory.New(opts)
    opts = opts or {}
    local self = setmetatable({}, Inventory)
    self.bagSlots = opts.bagSlots or Inventory.BAG_SLOTS
    self.storageSlots = opts.storageSlots or Inventory.STORAGE_SLOTS
    self.maxStack = opts.maxStack or Inventory.MAX_STACK
    self.bag = newGrid(self.bagSlots)
    self.storage = newGrid(self.storageSlots)
    self.equipped = {}
    return self
end

local function containerFor(self, which)
    if which == "storage" then return self.storage, self.storageSlots end
    return self.bag, self.bagSlots
end

--- Add up to `count` of an item, filling partial stacks first.
-- Returns how many were placed.
local function addTo(self, which, itemKey, count)
    local grid, slots = containerFor(self, which)
    local placed = 0
    for i = 1, slots do
        if placed >= count then break end
        local s = grid[i]
        if s and s.item == itemKey and s.count < self.maxStack then
            local room = self.maxStack - s.count
            local take = math.min(room, count - placed)
            s.count = s.count + take
            placed = placed + take
        end
    end
    for i = 1, slots do
        if placed >= count then break end
        if grid[i] == nil then
            local take = math.min(self.maxStack, count - placed)
            grid[i] = { item = itemKey, count = take }
            placed = placed + take
        end
    end
    return placed
end

--- Acquire items. Overflow runs bag -> storage -> ground; nothing is lost.
-- Returns { bag = n, storage = n, ground = n }.
function Inventory:Acquire(itemKey, count)
    count = count or 1
    local result = { bag = 0, storage = 0, ground = 0 }
    result.bag = addTo(self, "bag", itemKey, count)
    local left = count - result.bag
    if left > 0 then
        result.storage = addTo(self, "storage", itemKey, left)
        left = left - result.storage
    end
    result.ground = left
    return result
end

function Inventory:Count(itemKey)
    local n = 0
    for _, grid in ipairs({ self.bag, self.storage }) do
        for _, s in pairs(grid) do
            if s and s.item == itemKey then n = n + s.count end
        end
    end
    return n
end

--- Remove `count` of an item, bag first then storage. Returns true if the full
--- amount was removed; removes nothing at all if there is not enough.
function Inventory:Remove(itemKey, count)
    count = count or 1
    if self:Count(itemKey) < count then return false end
    local left = count
    for _, grid in ipairs({ self.bag, self.storage }) do
        for i, s in pairs(grid) do
            if left <= 0 then break end
            if s and s.item == itemKey then
                local take = math.min(s.count, left)
                s.count = s.count - take
                left = left - take
                if s.count <= 0 then grid[i] = nil end
            end
        end
    end
    return true
end

function Inventory:FreeSlots(which)
    local grid, slots = containerFor(self, which or "bag")
    local free = 0
    for i = 1, slots do
        if grid[i] == nil then free = free + 1 end
    end
    return free
end

--- Storage expands one slot at a time via an expansion item.
function Inventory:ExpandStorage(by)
    self.storageSlots = self.storageSlots + (by or 1)
    return self.storageSlots
end

-- ---------------------------------------------------------------- equipment

--- Can this hero equip this item? Weapon slots are class-gated.
-- @param itemDef entry from data/items.lua
-- @param heroDef entry from data/heroes.lua
function Inventory.CanEquip(itemDef, heroDef, level)
    if not itemDef or not itemDef.equipSlot then
        return false, "not equipment"
    end
    if itemDef.levelRequirement and level and level < itemDef.levelRequirement then
        return false, "level requirement"
    end
    if itemDef.equipSlot == "weapon" then
        local class = itemDef.weaponClass
        local allowed = false
        for _, w in ipairs(heroDef and heroDef.wearable or {}) do
            if w == class or w == "shared" and class == "shared" then
                allowed = true
                break
            end
        end
        -- "shared" weapons are usable by every class
        if class == "shared" then allowed = true end
        if not allowed then return false, "wrong weapon type" end
    end
    return true
end

--- Equip from the bag. Any previously equipped item returns to inventory.
function Inventory:Equip(itemKey, itemDef, heroDef, level)
    local ok, why = Inventory.CanEquip(itemDef, heroDef, level)
    if not ok then return false, why end
    if self:Count(itemKey) < 1 then return false, "not carried" end
    self:Remove(itemKey, 1)
    local slot = itemDef.equipSlot
    local previous = self.equipped[slot]
    self.equipped[slot] = itemKey
    if previous then self:Acquire(previous, 1) end
    return true, previous
end

function Inventory:Unequip(slot)
    local itemKey = self.equipped[slot]
    if not itemKey then return false end
    self.equipped[slot] = nil
    self:Acquire(itemKey, 1)
    return true, itemKey
end

--- Flat serialisable form for the persistence layer.
function Inventory:Serialise()
    local function pack(grid, slots)
        local out = {}
        for i = 1, slots do
            local s = grid[i]
            if s then out[#out + 1] = { slot = i, item = s.item, count = s.count } end
        end
        return out
    end
    return {
        bag = pack(self.bag, self.bagSlots),
        storage = pack(self.storage, self.storageSlots),
        storageSlots = self.storageSlots,
        equipped = self.equipped,
    }
end

function Inventory.Deserialise(data)
    local inv = Inventory.New({ storageSlots = data.storageSlots })
    for _, e in ipairs(data.bag or {}) do inv.bag[e.slot] = { item = e.item, count = e.count } end
    for _, e in ipairs(data.storage or {}) do
        inv.storage[e.slot] = { item = e.item, count = e.count }
    end
    inv.equipped = data.equipped or {}
    return inv
end

return Inventory
