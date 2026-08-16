--- Character persistence across matches.
--
-- Dota has no built-in cross-match save, so state goes to an external database
-- over CreateHTTPRequestScriptVM (docs/08 §3.3). This replaces the original's
-- save codes, which were forgeable.
--
-- SECURITY -- the reason this file is written defensively:
-- drop rates sit at 0.5%, so a writable save endpoint is the single most
-- valuable exploit target in the game. Therefore:
--   * every item grant happens server-side in Lua; the client never asks for one
--   * the HTTP layer is PERSISTENCE ONLY, never authority
--   * loaded payloads are validated field by field before being trusted --
--     unknown item keys, over-budget stat allocations and out-of-range levels
--     are rejected, not clamped silently
--   * requests carry the dedicated-server key so the backend can tell a real
--     match from a forged call
--
-- Custom games run on Valve's servers, which means this Lua is already
-- server-authoritative. That covers a lot, but it does not cover the endpoint.

local Constants = require("data/constants")
local Items = require("data/items")
local Heroes = require("data/heroes")

local Persistence = {}

Persistence.SCHEMA_VERSION = 1
Persistence.ENDPOINT = nil          -- set in addon_game_mode.lua; nil disables saving
Persistence.TIMEOUT = 10

-- JSON codec, injected rather than required, so this module stays dependency-free
-- and testable. Set it once at boot:
--   Persistence.json = require("libraries/json")
-- Saving is refused outright if it is missing, rather than silently sending nil.
Persistence.json = nil

-- ------------------------------------------------------------- validation

local function isKnownItem(key)
    return Items[key] ~= nil
end

--- Reject rather than repair. A payload that fails any check is not partially
--- loaded, because a half-applied save is worse than a lost one.
function Persistence.Validate(save)
    if type(save) ~= "table" then return false, "not a table" end
    if save.schema ~= Persistence.SCHEMA_VERSION then
        return false, "schema mismatch: got " .. tostring(save.schema)
    end
    if type(save.hero) ~= "string" or Heroes[save.hero] == nil then
        return false, "unknown hero: " .. tostring(save.hero)
    end

    local level = tonumber(save.level)
    if not level or level < 1 or level > Constants.MAX_HERO_LEVEL then
        return false, "level out of range: " .. tostring(save.level)
    end
    local xp = tonumber(save.xp) or 0
    if xp < 0 or xp > Constants.TOTAL_XP_TO_MAX then
        return false, "xp out of range: " .. tostring(save.xp)
    end

    local a = save.allocation
    if type(a) ~= "table" then return false, "missing allocation" end
    local spent = (tonumber(a.str) or 0) + (tonumber(a.agi) or 0) + (tonumber(a.int) or 0)
    if spent < 0 or spent > Constants.STAT_POINTS_TOTAL then
        return false, "allocation over budget: " .. spent
    end
    -- points must have been earnable at this level
    local perLevel = Constants.STAT_POINTS_TOTAL / (Constants.MAX_HERO_LEVEL - 1)
    local earned = math.floor(perLevel * (level - 1) + 0.0001)
    if spent > earned then
        return false, "allocated " .. spent .. " points but level " .. level ..
                      " only earns " .. earned
    end

    for _, container in ipairs({ "bag", "storage" }) do
        for _, e in ipairs((save.inventory or {})[container] or {}) do
            if not isKnownItem(e.item) then
                return false, "unknown item in " .. container .. ": " .. tostring(e.item)
            end
            local n = tonumber(e.count) or 0
            if n < 1 or n > 5 then
                return false, "bad stack size for " .. tostring(e.item) .. ": " .. tostring(e.count)
            end
        end
    end
    for slot, key in pairs((save.inventory or {}).equipped or {}) do
        if not isKnownItem(key) then
            return false, "unknown equipped item: " .. tostring(key)
        end
        if Items[key].equipSlot ~= slot then
            return false, "item " .. key .. " cannot occupy slot " .. tostring(slot)
        end
    end
    return true
end

-- ------------------------------------------------------------ serialising

function Persistence.Build(playerId, hero, level, xp, stats, inventory, codex)
    return {
        schema = Persistence.SCHEMA_VERSION,
        playerId = playerId,
        hero = hero,
        level = level,
        xp = xp,
        allocation = {
            str = stats.allocation.str,
            agi = stats.allocation.agi,
            int = stats.allocation.int,
        },
        inventory = inventory:Serialise(),
        codex = codex or {},
        savedAt = GameRules and GameRules:GetGameTime() or 0,
    }
end

-- ------------------------------------------------------------------ http

local function request(method, url, body, onDone)
    if not url then
        if onDone then onDone(false, "no endpoint configured") end
        return
    end
    local req = CreateHTTPRequestScriptVM(method, url)
    -- lets the backend distinguish a real Valve-hosted match from a forged call
    if GetDedicatedServerKeyV2 then
        req:SetHTTPRequestHeaderValue("X-Dedicated-Key", GetDedicatedServerKeyV2("twrpg"))
    end
    req:SetHTTPRequestHeaderValue("Content-Type", "application/json")
    if body then
        req:SetHTTPRequestRawPostBody("application/json", body)
    end
    req:Send(function(result)
        local ok = result and result.StatusCode == 200
        if onDone then onDone(ok, result and result.Body or "no response") end
    end)
end

function Persistence.Save(steamId, save, onDone)
    local ok, err = Persistence.Validate(save)
    if not ok then
        print("[TWRPG] refusing to save malformed state: " .. tostring(err))
        if onDone then onDone(false, err) end
        return
    end
    if not Persistence.json then
        if onDone then onDone(false, "no json codec set") end
        return
    end
    request("POST", Persistence.ENDPOINT and (Persistence.ENDPOINT .. "/save/" .. steamId),
            Persistence.json.encode(save), onDone)
end

function Persistence.Load(steamId, onDone)
    request("GET", Persistence.ENDPOINT and (Persistence.ENDPOINT .. "/load/" .. steamId), nil,
        function(ok, body)
            if not ok then
                onDone(false, body)
                return
            end
            if not Persistence.json then
                onDone(false, "no json codec set")
                return
            end
            local decodedOk, decoded = pcall(Persistence.json.decode, body)
            if not decodedOk then
                onDone(false, "malformed json from endpoint")
                return
            end
            local valid, err = Persistence.Validate(decoded)
            if not valid then
                -- A save that fails validation is discarded, never repaired.
                print("[TWRPG] rejecting loaded save: " .. tostring(err))
                onDone(false, err)
                return
            end
            onDone(true, decoded)
        end)
end

--- Small Valve-side record, useful for lightweight flags that must survive even
--- if the external database is unreachable.
function Persistence.InstallAccountRecordHook(mode, buildRecord)
    if mode and mode.SetCustomGameAccountRecordSaveFunction then
        mode:SetCustomGameAccountRecordSaveFunction(
            Dynamic_Wrap(Persistence, "_AccountRecord"), buildRecord)
    end
end

function Persistence._AccountRecord(playerId)
    return { schema = Persistence.SCHEMA_VERSION }
end

return Persistence
