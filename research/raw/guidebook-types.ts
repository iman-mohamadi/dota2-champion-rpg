import { StaticImageData } from "next/image";

/***********************************************************************************************
 ***************************************   BOSS TYPES   ****************************************
 **********************************************************************************************/

export type Boss = {
  id: string | string[];
  name: string;
  level?: string;
  color?: string;
  quote?: string;
  category: string;
  type: string;
  location?: string;
  limit?: string;
  duration?: string;
  summon?: string;
  timer?: string;
  empoweredStats?: {
      damageResist?: string;
      attackDamage?: string;
      attackRange?: string;
      attackSpeed?: string;
      moveSpeed?: string;
      magicResist?: string;
  }
  conditions?: string;
  respawn?: string;
  stats?: {
      health?: string;
      healthRegen?: string;
      mana?: string;
      manaRegen?: string;
      armor?: string;
      armorType?: string;
      moveSpeed?: string;
      magicResist?: string;
      damageResist?: string;
      attackDamage?: string;
      attackSpread?: string;
      attackRange?: string;
      attackSpeed?: string;
  };
  drops?: string[];
  spells?: string[];
  minions?: string[];
  notes?: string[];
}

/***********************************************************************************************
 ***************************************   ITEM TYPES   ****************************************
 **********************************************************************************************/

export type StatGroups = {
  armor: string[];
  constitution: string[];
  statsgain: string[];
  affinities: string[];
  dexterities: string[];
  targeted: string[];
  defense: string[];
  survival: string[];
  [key: string]: string[];
}

export type Icon = {
  [recipeName: string]: StaticImageData
}

export type RecipeIcon = Icon;

export type ColorGrade = {
  name: string;
  color: string;
}

export type ItemStats = {
  active?: string[];
  passive?: string[];
  damage?: number;
  armor?: number;
  mainstat?: number;
  allstat?: number;
  str?: number;
  agi?: number;
  int?: number,
  hp?: number,
  mp?: number,
  hpregen?: number;
  mpregen?: number,
  
  dtpercent?: number;
  drpercent?: number;
  mdpercent?: number;
  movespeed?: number;

  expgainpercent?: number,
  critmultiplier?: number;
  critchancepercent?: number;
  attackspeedpercent?: number;
  skilldamagepercent?: number;
  periodicdamagepercent?: number;
  damagedealtpercent?: number;
  aadamagepercent?: number;
  procdamagepercent?: number;
  healreceivedpercent?: number;
  healingpercent?: number;
  revivaltimepercent?: number;
  dodgechancepercent?: number;
  
  affinityiwpercent?: number;
  affinitywlpercent?: number;
  affinityflamepercent?: number;
  affinityearthpercent?: number;
  affinitylightpercent?: number;
  affinitydarkpercent?: number;
  spec?: string[];
  [key: string]: string[] | number | undefined;
};

export type StatsNameDictionary = {
  [key: string]: {
    name: string;
    color: string;
  };
}

type RecipeItem = {
  [item: string]: number
}

export type Item = {
  id: string;
  name: string;
  koreanname: string;
  description?: string;
  rank: string;
  grade: number;
  gradeName?: string;
  type: string;
  level?: number;
  color: string;
  required_by?: string[];
  stats?: ItemStats;
  recipe?: RecipeItem[];
  notes?: string[];
  drops?: string[];
  droprate?: number | number[];
  dropped_by?: string[];
  worth?: number;
  [key: string]: string | string[] | number | number[] | RecipeItem[] | ItemStats | undefined;
}

/***********************************************************************************************
 ***************************************   HERO TYPES   ****************************************
 **********************************************************************************************/

export type ItemColors = {
  [itemColor: string]: string
}

export type BuildItem = {
  [itemName: string]: string[]
};

export type Build = {
  for: string;
  type: string;
  order: number;
  stat: string;
  version: string;
  itemColors?: ItemColors[];
  items: BuildItem;
  description?: string[];
  guidelink?: string[];
}

export type SpecItemEffectsAndColor = {
  [itemName: string]: string[];
} & {
  color: string;
}

export type Hero = {
  id: string;
  name: string;
  heroClass: string;
  mainstat: string;
  color: string;
  icon: string;
  wearable: string[];
  role: string[];
  description: string[];
  spec: string[];
  secondary?: string[];
}

export type Skill = {
  id: string;
  name: string;
  heroClass: string;
  color: string;
  hotkey: string;
  icon: string;
  cooldown?: number;
  order: number;
  active?: string[];
  passive?: string[];
  proc_rate?: number;
  toggle?: string[];
}