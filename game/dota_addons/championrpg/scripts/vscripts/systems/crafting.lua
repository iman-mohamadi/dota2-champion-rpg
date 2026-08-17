--- Crafting over the 486-recipe graph.
--
-- Deterministic: no failure chance, no RNG on output. Components are consumed
-- and the result is produced (docs/01 §6.2).
--
-- The graph is up to 10 levels deep. `ExpandCost` walks it to the leaves so the
-- Codex can tell a player the true farm cost of a target -- Bag of All Evils is
-- 60 drops across 25 distinct materials.

local Recipes = require("data/recipes")
local Items = require("data/items")

local Crafting = {}

--- The recipe producing `itemKey`, or nil.
function Crafting.RecipeFor(itemKey)
    return Recipes.recipes[itemKey]
end

--- Recipes that consume `itemKey`.
function Crafting.UsedIn(itemKey)
    return Recipes.usedIn[itemKey] or {}
end

--- Can this inventory craft `itemKey` right now, from components on hand?
-- Returns ok, missing[] where missing entries are {item, need, have}.
function Crafting.CanCraft(inventory, itemKey)
    local recipe = Recipes.recipes[itemKey]
    if not recipe then return false, nil, "no recipe" end
    local missing = {}
    for _, c in ipairs(recipe.components) do
        local have = inventory:Count(c.item)
        if have < c.count then
            missing[#missing + 1] = { item = c.item, need = c.count, have = have }
        end
    end
    return #missing == 0, missing
end

--- Craft, consuming components. All-or-nothing.
function Crafting.Craft(inventory, itemKey)
    local ok, missing, err = Crafting.CanCraft(inventory, itemKey)
    if not ok then return false, missing or err end
    local recipe = Recipes.recipes[itemKey]
    for _, c in ipairs(recipe.components) do
        if not inventory:Remove(c.item, c.count) then
            -- Should be unreachable: CanCraft already checked. If it ever fires,
            -- something mutated the inventory between check and craft.
            return false, "component vanished mid-craft: " .. c.item
        end
    end
    local placed = inventory:Acquire(itemKey, 1)
    return true, placed
end

--- Everything craftable from what is currently held.
function Crafting.CurrentlyCraftable(inventory)
    local out = {}
    for key in pairs(Recipes.recipes) do
        if Crafting.CanCraft(inventory, key) then out[#out + 1] = key end
    end
    table.sort(out)
    return out
end

--- Fully expand a recipe to leaf materials.
-- Returns leaves = {itemKey = totalCount}, depth.
function Crafting.ExpandCost(itemKey, multiplier, acc, seen, depth)
    multiplier = multiplier or 1
    acc = acc or {}
    seen = seen or {}
    depth = depth or 0
    local recipe = Recipes.recipes[itemKey]
    if not recipe or seen[itemKey] then
        acc[itemKey] = (acc[itemKey] or 0) + multiplier
        return acc, depth
    end
    seen[itemKey] = true
    local maxDepth = depth
    for _, c in ipairs(recipe.components) do
        local _, d = Crafting.ExpandCost(c.item, multiplier * c.count, acc, seen, depth + 1)
        if d > maxDepth then maxDepth = d end
    end
    seen[itemKey] = nil
    return acc, maxDepth
end

--- Codex "Forge" view: what is still missing for a target, expanded to leaves,
--- annotated with where each missing material drops.
function Crafting.ForgePlan(inventory, itemKey)
    local leaves = Crafting.ExpandCost(itemKey)
    local plan = { target = itemKey, need = {}, totalDrops = 0, distinct = 0 }
    for leaf, count in pairs(leaves) do
        local have = inventory:Count(leaf)
        local short = math.max(0, count - have)
        plan.distinct = plan.distinct + 1
        plan.totalDrops = plan.totalDrops + count
        if short > 0 then
            local def = Items[leaf] or {}
            plan.need[#plan.need + 1] = {
                item = leaf,
                need = count,
                have = have,
                short = short,
                droppedBy = def.droppedBy,
                dropRate = def.dropRate,
            }
        end
    end
    table.sort(plan.need, function(a, b) return a.item < b.item end)
    return plan
end

return Crafting
