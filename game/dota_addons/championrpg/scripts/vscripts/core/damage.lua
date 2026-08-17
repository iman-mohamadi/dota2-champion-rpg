--- ChampionRPG damage pipeline.
--
-- Reimplements the pipeline recovered in docs/05-COMBAT-FORMULAS.md §4-5.
--
-- Dota's own armour curve uses a 0.06 coefficient and a different shape, so it
-- is bypassed entirely: units are registered with ArmorPhysical 0 and their real
-- TWRPG armour lives in data/units.lua. All mitigation happens here.
--
-- Order of operations, matching the original:
--   base -> channel multiplier -> global multiplier -> affinity
--        -> crit -> armour (physical only, after penetration) -> resists
--        -> shields -> death guards
--
-- Note the original had to *probe* armour at runtime (spend 100 damage on the
-- target and measure the loss) because Warcraft III gave it no way to read the
-- value. Here we own the number, so the probe is gone.

local Constants = require("data/constants")

local Damage = {}

-- Channels. TWRPG routes damage through four independent multiplier stats;
-- collapsing them would break every item and ability that touches one.
Damage.CHANNEL = {
    ATTACK = "attack",    -- auto-attack        (aadamagepercent)
    SKILL = "skill",      -- ability            (skilldamagepercent)
    PERIODIC = "periodic",-- damage over time   (periodicdamagepercent)
    PROC = "proc",        -- on-hit proc        (procdamagepercent)
}

-- Types. Only PHYSICAL is mitigated by armour; PURE bypasses everything.
Damage.TYPE = { PHYSICAL = 1, MAGICAL = 2, PURE = 3 }

local ARMOR_K = Constants.ARMOR_K                     -- 0.02
local NEG_BASE = Constants.ARMOR_NEGATIVE_BASE        -- 0.94

--- Fraction of damage that survives `armor`.
-- armor >= 0 : 1 / (1 + k*armor)
-- armor <  0 : 2 - 0.94^(-armor)
function Damage.ArmorMultiplier(armor)
    armor = armor or 0
    if armor >= 0 then
        return 1.0 - ((armor * ARMOR_K) / (1.0 + ARMOR_K * armor))
    end
    return 2.0 - NEG_BASE ^ (-armor)
end

--- Inverse of ArmorMultiplier: recover pre-mitigation damage.
function Damage.UnapplyArmor(damage, armor)
    local m = Damage.ArmorMultiplier(armor)
    if m <= 0 then return damage end
    return damage / m
end

--- Effective armour after penetration. Penetration is multiplicative on armour
--- and applied *before* mitigation (docs/05 §5.4).
function Damage.EffectiveArmor(armor, penetration)
    return (armor or 0) * (1.0 - (penetration or 0))
end

--- A damage instance. The original allocates a struct per hit rather than
--- passing a number around, because the modifier pipeline mutates it in place.
function Damage.CreateInstance(source, target, amount, damageType, channel)
    return {
        source = source,
        target = target,
        base = amount,
        amount = amount,
        damageType = damageType or Damage.TYPE.MAGICAL,
        channel = channel or Damage.CHANNEL.SKILL,
        -- multiplier slots
        channelMult = 1.0,
        globalMult = 1.0,
        affinityMult = 1.0,
        critMult = 1.0,
        isCrit = false,
        armorPen = 0.0,
        -- flags
        ignoreArmor = false,
        ignoreShields = false,
        preventDeath = false,
        label = nil,
    }
end

--- Run the pipeline and return the final damage. Pure arithmetic: no engine
--- calls, so this is unit-testable outside Dota.
function Damage.Resolve(inst, targetStats)
    targetStats = targetStats or {}
    local d = inst.base

    d = d * (inst.channelMult or 1.0)
    d = d * (inst.globalMult or 1.0)
    d = d * (inst.affinityMult or 1.0)

    if inst.damageType == Damage.TYPE.PHYSICAL and not inst.ignoreArmor then
        local armor = Damage.EffectiveArmor(targetStats.armor or 0, inst.armorPen)
        d = d * Damage.ArmorMultiplier(armor)
    elseif inst.damageType == Damage.TYPE.MAGICAL then
        d = d * (1.0 - (targetStats.magicResist or 0) / 100.0)
    end
    -- PURE bypasses both.

    -- Flat damage-resistance percentage, applied to every type except pure.
    if inst.damageType ~= Damage.TYPE.PURE then
        d = d * (1.0 - (targetStats.damageResist or 0) / 100.0)
    end

    -- Crit lands AFTER mitigation, so armour does not eat the crit portion.
    if inst.isCrit then
        d = d * (inst.critMult or 1.0)
    end

    if d < 0 then d = 0 end
    inst.amount = d
    return d
end

--- XP granted for killing a unit of `level`: A*L^2 + B*L + C.
function Damage.CreepXP(level)
    local k = Constants.CREEP_XP
    return k.A * level * level + k.B * level + k.C
end

return Damage
