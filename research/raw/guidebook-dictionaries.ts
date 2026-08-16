import { StatGroups, StatsNameDictionary } from "types";

export const itemTabs = [
  { id: 'Weapon' },
  { id: 'Head' },
  { id: 'Armor' },
  { id: 'Accessory' },
  { id: 'Wings' },
  { id: 'Mat' },
  { id: 'Misc' },
  { id: 'Pickaxe' },
  { id: 'Token' },
  { id: 'Icon' },
  { id: 'Food' },
  { id: 'Coin' },
  { id: 'Special' },
];

export const grades = [
  { name: '', color: '' },
  { name: 'Deltirama', color: '#733CBE' },
  { name: 'Neptinos', color: '#99FF99' },
  { name: 'Gnosis', color: '#DC143C' },
  { name: 'Alteia', color: '#9BE1E1' },
  { name: 'Arcana', color: '#C39BE1' },
];

export const statGroups: StatGroups = {
  armor: ['armor'],
  constitution: ['hpregen', 'mpregen', 'hp', 'mp'],
  statsgain: ['mainstat', 'allstat', 'str', 'agi', 'int'],
  affinities: ['affinitydarkpercent', 'affinityflamepercent', 'affinityearthpercent', 'affinitylightpercent', 'affinityiwpercent', 'affinitywlpercent',],
  dexterities: ['attackspeedpercent', 'movespeed', 'critchancepercent', 'critmultiplier'],
  targeted: ['periodicdamagepercent', 'skilldamagepercent', 'procdamagepercent', 'aadamagepercent'],
  defense: ['drpercent', 'dtpercent', 'mdpercent'],
  survival: ['dodgechancepercent', 'healingpercent', 'healreceivedpercent',],
}

export const statsNameDictionary: StatsNameDictionary = {
  damage: { name: " Damage", color: "#ff8c00", },
  armor: { name: " Armor", color: "#ff8c00", },
  mainstat: { name: " Main Stat", color: "#ff8c00", },
  allstat: { name: " All Stat", color: "#ff8c00", },
  str: { name: " Strength", color: "#ff8c00", },
  agi: { name: " Agility", color: "#ff8c00", },
  int: { name: " Intelligence", color: "#ff8c00", },
  hp: { name: " Health", color: "#ff8c00", },
  mp: { name: " Mana", color: "#ff8c00", },
  hpregen: { name: " HP Regen", color: "#40e0d0", },
  mpregen: { name: " MP Regen", color: "#40e0d0", },

  dtpercent: { name: "% Damage Taken", color: "#40e0d0", },
  drpercent: { name: "% Damage Reduction", color: "#40e0d0", },
  mdpercent: { name: "% Magic Defense", color: "#40e0d0", },
  movespeed: { name: " Movement Speed", color: "#ff8c00", },

  expgainpercent: { name: "% Exp Gain", color: "#40e0d0", },
  critmultiplier: { name: "x Critical Multiplier", color: "#40e0d0", },
  critchancepercent: { name: "% Critical Chance", color: "#40e0d0", },
  attackspeedpercent: { name: "% Attack Speed", color: "#ff8c00", },
  skilldamagepercent: { name: "% Skill Damage", color: "#40e0d0", },
  periodicdamagepercent: { name: "% Periodic Damage", color: "#ff1493", },
  damagedealtpercent: { name: "% Damage Dealt", color: "#ff8c00", },
  aadamagepercent: { name: "% Auto Attack Damage", color: "#ff8c00", },
  procdamagepercent: { name: "% Proc Damage", color: "#ff8c00"},
  healreceivedpercent: { name: "% Healing Received", color: "#ff1493", },
  healingpercent: { name: "% Healing Done", color: "#ff8c00", },
  revivaltimepercent: { name: "% Revival Time", color: "#40e0d0", },
  dodgechancepercent: { name: "% Dodge Chance", color: "#40e0d0", },

  affinityiwpercent: { name: "% Ice/Water Affinity", color: "#bae0fc", },
  affinitywlpercent: { name: "% Wind/Lightning Affinity", color: "#b5fbba", },
  affinityflamepercent: { name: "% Flame Affinity", color: "#f8ae9c", },
  affinityearthpercent: { name: "% Earth Affinity", color: "#dfbf9f", },
  affinitylightpercent: { name: "% Light Affinity", color: "#fdfd98", },
  affinitydarkpercent: { name: "% Dark Affinity", color: "#9790b2", },
}