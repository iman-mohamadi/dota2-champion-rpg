--- TWRPG addon entry point.
--
-- Installs the gameplay constants recovered from the original map
-- (docs/05-COMBAT-FORMULAS.md) into Dota's custom-game API.
--
-- The mapping is close to 1:1: Warcraft III's war3mapMisc.txt and Dota's
-- SetCustomAttributeDerivedStatValue expose the same knobs. TWRPG's defining
-- decision -- disable the engine's entire built-in RPG layer and drive
-- everything from script -- is natively expressible here.

require("data/constants")
require("core/damage")

local Constants = require("data/constants")

if TWRPG == nil then
    TWRPG = class({})
end

function Precache(context)
    -- Models/particles are assigned once real Dota assets are chosen.
end

function Activate()
    GameRules.TWRPG = TWRPG()
    GameRules.TWRPG:InitGameMode()
end

function TWRPG:InitGameMode()
    local mode = GameRules:GetGameModeEntity()

    -- ---- levelling ---------------------------------------------------------
    -- Level cap 100 with the exact recovered curve:
    --   Need(L) = 1650 * 1.05^(L-1) - 1500, 3,951,397 XP to reach 100.
    mode:SetUseCustomHeroLevels(true)
    mode:SetCustomHeroMaxLevel(Constants.MAX_HERO_LEVEL)
    mode:SetCustomXPRequiredToReachNextLevel(Constants.XP_PER_LEVEL)

    -- ---- attributes --------------------------------------------------------
    -- TWRPG zeroes every stock attribute effect: STR grants no HP, AGI no
    -- armour or attack speed, INT no mana. All power comes from the 697
    -- allocated stat points plus equipment. Only primary-attribute attack
    -- damage survives, at 3.0 per point.
    for _, a in ipairs(Constants.ATTRIBUTE_DERIVED) do
        mode:SetCustomAttributeDerivedStatValue(_G[a.enum], a.value)
    end

    -- ---- combat ------------------------------------------------------------
    -- Every damage instance is resolved by our own pipeline; Dota's armour
    -- curve is bypassed (units carry ArmorPhysical 0). See core/damage.lua.
    mode:SetDamageFilter(Dynamic_Wrap(TWRPG, "DamageFilter"), self)

    -- WC3 camera distance: boss AoE mechanics were tuned to what the player
    -- can see, so this is a gameplay value, not a preference.
    mode:SetCameraDistanceOverride(1500)

    mode:SetFogOfWarDisabled(false)
    mode:SetStashPurchasingDisabled(true)

    GameRules:SetHeroSelectionTime(30.0)
    GameRules:SetPreGameTime(15.0)
    GameRules:SetCustomGameSetupAutoLaunchDelay(10.0)

    print("[TWRPG] initialised: max level " .. Constants.MAX_HERO_LEVEL ..
          ", armour k=" .. Constants.ARMOR_K)
end

--- Intercepts every damage instance, the equivalent of the original's `pdo`.
-- Returning true lets the (rewritten) damage through.
function TWRPG:DamageFilter(event)
    -- event.damage / event.entindex_victim_const / event.entindex_attacker_const
    -- Full resolution lands here once the stat and modifier systems exist;
    -- for now damage passes through unmodified so the mode boots cleanly.
    return true
end
