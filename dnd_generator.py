#!/usr/bin/env python3
"""D&D 5e Character Generator - Generates characters and fills official PDF sheet."""

import io
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from pypdf import PdfReader, PdfWriter

# Base directory for resolving template paths
BASE_DIR = Path(__file__).parent

# Standard Array for ability scores
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

# Ability score modifier calculation
def ability_mod(score: int) -> int:
    return (score - 10) // 2

def mod_str(mod: int) -> str:
    return f"+{mod}" if mod >= 0 else str(mod)


@dataclass
class Species:
    """2024 PHB species - no ability bonuses (those come from background now)."""
    name: str
    speed: int
    size: str
    traits: list[str]
    darkvision: int = 0
    skill_profs: list[str] = field(default_factory=list)


SPECIES = {
    "aasimar": Species(
        name="Aasimar",
        speed=30,
        size="Medium",
        traits=["Celestial Resistance", "Darkvision", "Healing Hands", "Light Bearer", "Celestial Revelation"],
        darkvision=60,
    ),
    "dragonborn": Species(
        name="Dragonborn",
        speed=30,
        size="Medium",
        traits=["Dragon Ancestry", "Breath Weapon", "Damage Resistance", "Draconic Flight (Lv5)"],
        darkvision=60,
    ),
    "dwarf": Species(
        name="Dwarf",
        speed=30,
        size="Medium",
        traits=["Dwarven Resilience", "Dwarven Toughness", "Stonecunning"],
        darkvision=120,
    ),
    "elf": Species(
        name="Elf",
        speed=30,
        size="Medium",
        traits=["Elven Lineage", "Fey Ancestry", "Keen Senses", "Trance"],
        darkvision=60,
        skill_profs=["Perception"],
    ),
    "gnome": Species(
        name="Gnome",
        speed=30,
        size="Small",
        traits=["Gnomish Cunning", "Gnomish Lineage"],
        darkvision=60,
    ),
    "goliath": Species(
        name="Goliath",
        speed=35,
        size="Medium",
        traits=["Giant Ancestry", "Large Form", "Powerful Build"],
    ),
    "halfling": Species(
        name="Halfling",
        speed=30,
        size="Small",
        traits=["Brave", "Halfling Nimbleness", "Luck", "Naturally Stealthy"],
    ),
    "human": Species(
        name="Human",
        speed=30,
        size="Medium",
        traits=["Resourceful", "Skillful", "Versatile"],
        skill_profs=["Choice"],  # Skillful trait
    ),
    "orc": Species(
        name="Orc",
        speed=30,
        size="Medium",
        traits=["Adrenaline Rush", "Relentless Endurance"],
        darkvision=120,
    ),
    "tiefling": Species(
        name="Tiefling",
        speed=30,
        size="Medium",
        traits=["Fiendish Legacy", "Otherworldly Presence"],
        darkvision=60,
    ),
}


@dataclass
class ClassInfo:
    name: str
    hit_die: int
    primary_ability: list[str]
    saving_throws: list[str]
    armor_profs: list[str]
    weapon_profs: list[str]
    skill_choices: list[str]
    num_skills: int
    starting_equipment: list[str]
    features: list[str]
    spellcasting: Optional[str] = None


CLASSES = {
    "barbarian": ClassInfo(
        name="Barbarian",
        hit_die=12,
        primary_ability=["STR"],
        saving_throws=["STR", "CON"],
        armor_profs=["Light", "Medium", "Shields"],
        weapon_profs=["Simple", "Martial"],
        skill_choices=["Animal Handling", "Athletics", "Intimidation", "Nature", "Perception", "Survival"],
        num_skills=2,
        starting_equipment=["Greataxe", "2 Handaxes", "Explorer's Pack", "4 Javelins"],
        features=["Rage", "Unarmored Defense"],
    ),
    "bard": ClassInfo(
        name="Bard",
        hit_die=8,
        primary_ability=["CHA"],
        saving_throws=["DEX", "CHA"],
        armor_profs=["Light"],
        weapon_profs=["Simple", "Hand Crossbow", "Longsword", "Rapier", "Shortsword"],
        skill_choices=["Any"],
        num_skills=3,
        starting_equipment=["Rapier", "Diplomat's Pack", "Lute", "Leather Armor", "Dagger"],
        features=["Spellcasting", "Bardic Inspiration (d6)"],
        spellcasting="CHA",
    ),
    "cleric": ClassInfo(
        name="Cleric",
        hit_die=8,
        primary_ability=["WIS"],
        saving_throws=["WIS", "CHA"],
        armor_profs=["Light", "Medium", "Shields"],
        weapon_profs=["Simple"],
        skill_choices=["History", "Insight", "Medicine", "Persuasion", "Religion"],
        num_skills=2,
        starting_equipment=["Mace", "Scale Mail", "Light Crossbow", "20 bolts", "Priest's Pack", "Shield", "Holy Symbol"],
        features=["Spellcasting", "Divine Domain"],
        spellcasting="WIS",
    ),
    "druid": ClassInfo(
        name="Druid",
        hit_die=8,
        primary_ability=["WIS"],
        saving_throws=["INT", "WIS"],
        armor_profs=["Light", "Medium", "Shields (non-metal)"],
        weapon_profs=["Club", "Dagger", "Dart", "Javelin", "Mace", "Quarterstaff", "Scimitar", "Sickle", "Sling", "Spear"],
        skill_choices=["Arcana", "Animal Handling", "Insight", "Medicine", "Nature", "Perception", "Religion", "Survival"],
        num_skills=2,
        starting_equipment=["Wooden Shield", "Scimitar", "Leather Armor", "Explorer's Pack", "Druidic Focus"],
        features=["Druidic", "Spellcasting"],
        spellcasting="WIS",
    ),
    "fighter": ClassInfo(
        name="Fighter",
        hit_die=10,
        primary_ability=["STR", "DEX"],
        saving_throws=["STR", "CON"],
        armor_profs=["All armor", "Shields"],
        weapon_profs=["Simple", "Martial"],
        skill_choices=["Acrobatics", "Animal Handling", "Athletics", "History", "Insight", "Intimidation", "Perception", "Survival"],
        num_skills=2,
        starting_equipment=["Chain Mail", "Longsword", "Shield", "Light Crossbow", "20 bolts", "Dungeoneer's Pack"],
        features=["Fighting Style", "Second Wind"],
    ),
    "monk": ClassInfo(
        name="Monk",
        hit_die=8,
        primary_ability=["DEX", "WIS"],
        saving_throws=["STR", "DEX"],
        armor_profs=[],
        weapon_profs=["Simple", "Shortsword"],
        skill_choices=["Acrobatics", "Athletics", "History", "Insight", "Religion", "Stealth"],
        num_skills=2,
        starting_equipment=["Shortsword", "Dungeoneer's Pack", "10 Darts"],
        features=["Unarmored Defense", "Martial Arts"],
    ),
    "paladin": ClassInfo(
        name="Paladin",
        hit_die=10,
        primary_ability=["STR", "CHA"],
        saving_throws=["WIS", "CHA"],
        armor_profs=["All armor", "Shields"],
        weapon_profs=["Simple", "Martial"],
        skill_choices=["Athletics", "Insight", "Intimidation", "Medicine", "Persuasion", "Religion"],
        num_skills=2,
        starting_equipment=["Chain Mail", "Longsword", "Shield", "5 Javelins", "Priest's Pack", "Holy Symbol"],
        features=["Divine Sense", "Lay on Hands"],
    ),
    "ranger": ClassInfo(
        name="Ranger",
        hit_die=10,
        primary_ability=["DEX", "WIS"],
        saving_throws=["STR", "DEX"],
        armor_profs=["Light", "Medium", "Shields"],
        weapon_profs=["Simple", "Martial"],
        skill_choices=["Animal Handling", "Athletics", "Insight", "Investigation", "Nature", "Perception", "Stealth", "Survival"],
        num_skills=3,
        starting_equipment=["Scale Mail", "2 Shortswords", "Dungeoneer's Pack", "Longbow", "20 Arrows"],
        features=["Favored Enemy", "Natural Explorer"],
    ),
    "rogue": ClassInfo(
        name="Rogue",
        hit_die=8,
        primary_ability=["DEX"],
        saving_throws=["DEX", "INT"],
        armor_profs=["Light"],
        weapon_profs=["Simple", "Hand Crossbow", "Longsword", "Rapier", "Shortsword"],
        skill_choices=["Acrobatics", "Athletics", "Deception", "Insight", "Intimidation", "Investigation", "Perception", "Performance", "Persuasion", "Sleight of Hand", "Stealth"],
        num_skills=4,
        starting_equipment=["Rapier", "Shortbow", "20 Arrows", "Burglar's Pack", "Leather Armor", "2 Daggers", "Thieves' Tools"],
        features=["Expertise", "Sneak Attack (1d6)", "Thieves' Cant"],
    ),
    "sorcerer": ClassInfo(
        name="Sorcerer",
        hit_die=6,
        primary_ability=["CHA"],
        saving_throws=["CON", "CHA"],
        armor_profs=[],
        weapon_profs=["Dagger", "Dart", "Sling", "Quarterstaff", "Light Crossbow"],
        skill_choices=["Arcana", "Deception", "Insight", "Intimidation", "Persuasion", "Religion"],
        num_skills=2,
        starting_equipment=["Light Crossbow", "20 bolts", "Arcane Focus", "Dungeoneer's Pack", "2 Daggers"],
        features=["Spellcasting", "Sorcerous Origin"],
        spellcasting="CHA",
    ),
    "warlock": ClassInfo(
        name="Warlock",
        hit_die=8,
        primary_ability=["CHA"],
        saving_throws=["WIS", "CHA"],
        armor_profs=["Light"],
        weapon_profs=["Simple"],
        skill_choices=["Arcana", "Deception", "History", "Intimidation", "Investigation", "Nature", "Religion"],
        num_skills=2,
        starting_equipment=["Light Crossbow", "20 bolts", "Arcane Focus", "Scholar's Pack", "Leather Armor", "Simple Weapon", "2 Daggers"],
        features=["Otherworldly Patron", "Pact Magic"],
        spellcasting="CHA",
    ),
    "wizard": ClassInfo(
        name="Wizard",
        hit_die=6,
        primary_ability=["INT"],
        saving_throws=["INT", "WIS"],
        armor_profs=[],
        weapon_profs=["Dagger", "Dart", "Sling", "Quarterstaff", "Light Crossbow"],
        skill_choices=["Arcana", "History", "Insight", "Investigation", "Medicine", "Religion"],
        num_skills=2,
        starting_equipment=["Quarterstaff", "Arcane Focus", "Scholar's Pack", "Spellbook"],
        features=["Spellcasting", "Arcane Recovery"],
        spellcasting="INT",
    ),
}


@dataclass
class Background:
    """2024 PHB backgrounds - now include ability score bonuses and origin feats."""
    name: str
    skill_profs: list[str]
    tool_profs: list[str]
    ability_options: list[str]  # Three abilities to choose from for +2/+1 or +1/+1/+1
    origin_feat: str
    equipment: list[str]
    traits: list[str]
    ideals: list[str]
    bonds: list[str]
    flaws: list[str]


BACKGROUNDS = {
    "acolyte": Background(
        name="Acolyte",
        skill_profs=["Insight", "Religion"],
        tool_profs=["Calligrapher's Supplies"],
        ability_options=["INT", "WIS", "CHA"],
        origin_feat="Magic Initiate (Cleric)",
        equipment=["Calligrapher's Supplies", "Prayer Book", "Holy Symbol", "Parchment (10)", "Robe", "8 gp"],
        traits=["I idolize a particular hero of my faith.", "Nothing can shake my optimistic attitude."],
        ideals=["Tradition. The ancient traditions must be preserved.", "Charity. I always help those in need."],
        bonds=["I would die to recover an ancient relic.", "I owe my life to the priest who took me in."],
        flaws=["I judge others harshly.", "I put too much trust in the church hierarchy."],
    ),
    "artisan": Background(
        name="Artisan",
        skill_profs=["Investigation", "Persuasion"],
        tool_profs=["Artisan's Tools"],
        ability_options=["STR", "DEX", "INT"],
        origin_feat="Crafter",
        equipment=["Artisan's Tools", "2 Pouches", "Traveler's Clothes", "32 gp"],
        traits=["I believe anything worth doing is worth doing right.", "I like to talk at length about my craft."],
        ideals=["Quality. I take pride in my work.", "Community. We all have something to contribute."],
        bonds=["The workshop where I learned my trade is the most important place to me.", "I created something for someone and they still treasure it."],
        flaws=["I'll do anything to get my hands on rare materials.", "I'm never satisfied with my own work."],
    ),
    "charlatan": Background(
        name="Charlatan",
        skill_profs=["Deception", "Sleight of Hand"],
        tool_profs=["Forgery Kit"],
        ability_options=["DEX", "CON", "CHA"],
        origin_feat="Skilled",
        equipment=["Forgery Kit", "Costume", "Fine Clothes", "15 gp"],
        traits=["I fall in and out of love easily.", "I have a joke for every occasion."],
        ideals=["Independence. I am a free spirit.", "Fairness. I never target those who can't afford it."],
        bonds=["I fleeced the wrong person.", "I come from a noble family."],
        flaws=["I can't resist a pretty face.", "I'm always in debt."],
    ),
    "criminal": Background(
        name="Criminal",
        skill_profs=["Sleight of Hand", "Stealth"],
        tool_profs=["Thieves' Tools"],
        ability_options=["DEX", "CON", "INT"],
        origin_feat="Alert",
        equipment=["2 Daggers", "Thieves' Tools", "Crowbar", "2 Pouches", "Traveler's Clothes", "16 gp"],
        traits=["I always have a plan for when things go wrong.", "I am incredibly slow to trust."],
        ideals=["Honor. I don't steal from others in the trade.", "Freedom. Chains are meant to be broken."],
        bonds=["I'm trying to pay off a debt I owe.", "Someone I loved died because of a mistake I made."],
        flaws=["When I see something valuable, I can't think about anything but stealing it.", "I turn tail and run at the first sign of trouble."],
    ),
    "entertainer": Background(
        name="Entertainer",
        skill_profs=["Acrobatics", "Performance"],
        tool_profs=["Musical Instrument"],
        ability_options=["STR", "DEX", "CHA"],
        origin_feat="Musician",
        equipment=["Musical Instrument", "2 Costumes", "Mirror", "Perfume", "Traveler's Clothes", "11 gp"],
        traits=["I know a story relevant to almost every situation.", "I change my mood as quickly as I change keys."],
        ideals=["Beauty. Art should inspire.", "Creativity. The world needs new ideas."],
        bonds=["My instrument is my most treasured possession.", "I want to be famous."],
        flaws=["I'll do anything to win fame.", "I'm a sucker for a pretty face."],
    ),
    "farmer": Background(
        name="Farmer",
        skill_profs=["Animal Handling", "Nature"],
        tool_profs=["Carpenter's Tools"],
        ability_options=["STR", "CON", "WIS"],
        origin_feat="Tough",
        equipment=["Sickle", "Carpenter's Tools", "Healer's Kit", "Iron Pot", "Shovel", "Traveler's Clothes", "30 gp"],
        traits=["I judge people by their actions.", "If someone is in trouble, I'm always ready to help."],
        ideals=["Respect. People deserve dignity.", "Hard work brings its own rewards."],
        bonds=["I protect those who cannot protect themselves.", "My family farm is everything to me."],
        flaws=["I have trouble trusting city folk.", "I'm convinced of my own simple wisdom."],
    ),
    "guard": Background(
        name="Guard",
        skill_profs=["Athletics", "Perception"],
        tool_profs=["Gaming Set"],
        ability_options=["STR", "INT", "WIS"],
        origin_feat="Alert",
        equipment=["Spear", "Light Crossbow", "20 Bolts", "Gaming Set", "Hooded Lantern", "Manacles", "Quiver", "Traveler's Clothes", "12 gp"],
        traits=["I'm always polite and respectful.", "I can stare down a hell hound."],
        ideals=["Greater Good. Our lot is to protect others.", "Order. The law is the law."],
        bonds=["Those who fight beside me are worth dying for.", "I protect the innocent."],
        flaws=["I made a terrible mistake that cost lives.", "I obey the law, even if it causes misery."],
    ),
    "guide": Background(
        name="Guide",
        skill_profs=["Stealth", "Survival"],
        tool_profs=["Cartographer's Tools"],
        ability_options=["DEX", "CON", "WIS"],
        origin_feat="Magic Initiate (Druid)",
        equipment=["Shortbow", "20 Arrows", "Cartographer's Tools", "Bedroll", "Quiver", "Tent", "Traveler's Clothes", "3 gp"],
        traits=["I'm driven by wanderlust.", "I watch over my friends like they were family."],
        ideals=["Change. Life is like the seasons.", "Nature. The wilds are my true home."],
        bonds=["My family, clan, or tribe is everything.", "I know these lands better than anyone."],
        flaws=["I am slow to trust civilization.", "I'm not comfortable indoors."],
    ),
    "hermit": Background(
        name="Hermit",
        skill_profs=["Medicine", "Religion"],
        tool_profs=["Herbalism Kit"],
        ability_options=["CON", "WIS", "CHA"],
        origin_feat="Healer",
        equipment=["Quarterstaff", "Herbalism Kit", "Bedroll", "Book (philosophy)", "Lamp", "Oil (3)", "Traveler's Clothes", "16 gp"],
        traits=["I've been isolated so long I rarely speak.", "I am utterly serene, even in disaster."],
        ideals=["Knowledge. Contemplation leads to self-improvement.", "Free Thinking. Inquiry and curiosity are essential."],
        bonds=["My isolation gave me insight into a great evil.", "I entered seclusion to hide from those who might harm me."],
        flaws=["I harbor dark thoughts.", "I am dogmatic in my beliefs."],
    ),
    "merchant": Background(
        name="Merchant",
        skill_profs=["Animal Handling", "Persuasion"],
        tool_profs=["Navigator's Tools"],
        ability_options=["CON", "INT", "CHA"],
        origin_feat="Lucky",
        equipment=["Navigator's Tools", "2 Pouches", "Traveler's Clothes", "22 gp"],
        traits=["I can find common ground with anyone.", "I like to talk at length about business."],
        ideals=["Fairness. Everyone deserves a fair deal.", "Opportunity. Fortune favors the bold."],
        bonds=["My business is my life.", "I owe a great debt to a partner."],
        flaws=["I'll do anything to make a profit.", "I'm never satisfied with what I have."],
    ),
    "noble": Background(
        name="Noble",
        skill_profs=["History", "Persuasion"],
        tool_profs=["Gaming Set"],
        ability_options=["STR", "INT", "CHA"],
        origin_feat="Skilled",
        equipment=["Gaming Set", "Fine Clothes", "Perfume", "29 gp"],
        traits=["My eloquent flattery makes everyone feel important.", "Common folk love me for my kindness."],
        ideals=["Responsibility. It is my duty to protect my people.", "Noble Obligation. I must prove my worth."],
        bonds=["I will face any challenge to win approval.", "My house's alliance is everything."],
        flaws=["I secretly believe everyone is beneath me.", "I hide a shameful secret."],
    ),
    "sage": Background(
        name="Sage",
        skill_profs=["Arcana", "History"],
        tool_profs=["Calligrapher's Supplies"],
        ability_options=["CON", "INT", "WIS"],
        origin_feat="Magic Initiate (Wizard)",
        equipment=["Quarterstaff", "Calligrapher's Supplies", "Book (history)", "Parchment (8)", "Robe", "8 gp"],
        traits=["I use polysyllabic words to impress.", "I've read every book in the world's greatest libraries."],
        ideals=["Knowledge. The path to power is through knowledge.", "Self-Improvement. The goal is to become better."],
        bonds=["I've been searching for a particular piece of lore.", "My life's work is a series of tomes."],
        flaws=["I overlook obvious solutions in favor of complicated ones.", "I speak without thinking."],
    ),
    "sailor": Background(
        name="Sailor",
        skill_profs=["Acrobatics", "Perception"],
        tool_profs=["Navigator's Tools"],
        ability_options=["STR", "DEX", "WIS"],
        origin_feat="Tavern Brawler",
        equipment=["Dagger", "Navigator's Tools", "Rope", "Traveler's Clothes", "20 gp"],
        traits=["My friends know they can rely on me.", "I stretch the truth for a good story."],
        ideals=["Mastery. I'm a predator in combat.", "Freedom. The sea is freedom."],
        bonds=["I was cheated out of my fair share.", "My ship is my first love."],
        flaws=["I follow orders, even if I think they're wrong.", "I'll say anything to avoid work."],
    ),
    "scribe": Background(
        name="Scribe",
        skill_profs=["Investigation", "Perception"],
        tool_profs=["Calligrapher's Supplies"],
        ability_options=["DEX", "INT", "WIS"],
        origin_feat="Skilled",
        equipment=["Calligrapher's Supplies", "Fine Clothes", "Lamp", "Oil (3)", "Parchment (12)", "23 gp"],
        traits=["I always have a book with me.", "I'm used to helping out those who aren't as smart as I am."],
        ideals=["Knowledge. The path to power is through knowledge.", "Logic. Emotions must not cloud our sense of what is right."],
        bonds=["The library is the most important place in the world.", "I work to preserve the written word."],
        flaws=["I overlook obvious solutions in favor of complicated ones.", "Most people scream and run when they see a demon. I stop and take notes."],
    ),
    "soldier": Background(
        name="Soldier",
        skill_profs=["Athletics", "Intimidation"],
        tool_profs=["Gaming Set"],
        ability_options=["STR", "DEX", "CON"],
        origin_feat="Savage Attacker",
        equipment=["Spear", "Shortbow", "20 Arrows", "Gaming Set", "Healer's Kit", "Quiver", "Traveler's Clothes", "14 gp"],
        traits=["I'm always polite and respectful.", "I can stare down a hell hound."],
        ideals=["Greater Good. Our lot is to protect others.", "Might. In battle, the strongest prevail."],
        bonds=["Those who fight beside me are worth dying for.", "Someone saved my life on the battlefield."],
        flaws=["I made a terrible mistake that cost many lives.", "I obey the law, even if it causes misery."],
    ),
    "wayfarer": Background(
        name="Wayfarer",
        skill_profs=["Insight", "Stealth"],
        tool_profs=["Thieves' Tools"],
        ability_options=["DEX", "WIS", "CHA"],
        origin_feat="Lucky",
        equipment=["2 Daggers", "Thieves' Tools", "Gaming Set", "Bedroll", "2 Pouches", "Traveler's Clothes", "16 gp"],
        traits=["I hide scraps of food in my pockets.", "I ask a lot of questions."],
        ideals=["Respect. All people deserve respect.", "Change. The low can be raised up."],
        bonds=["My town or city is my home.", "I owe everything to my mentor."],
        flaws=["Gold seems like a lot of money to me.", "I can never fully trust anyone."],
    ),
}

ALL_SKILLS = [
    "Acrobatics", "Animal Handling", "Arcana", "Athletics", "Deception",
    "History", "Insight", "Intimidation", "Investigation", "Medicine",
    "Nature", "Perception", "Performance", "Persuasion", "Religion",
    "Sleight of Hand", "Stealth", "Survival"
]

SKILL_ABILITIES = {
    "Acrobatics": "DEX", "Animal Handling": "WIS", "Arcana": "INT",
    "Athletics": "STR", "Deception": "CHA", "History": "INT",
    "Insight": "WIS", "Intimidation": "CHA", "Investigation": "INT",
    "Medicine": "WIS", "Nature": "INT", "Perception": "WIS",
    "Performance": "CHA", "Persuasion": "CHA", "Religion": "INT",
    "Sleight of Hand": "DEX", "Stealth": "DEX", "Survival": "WIS"
}


@dataclass
class Character:
    name: str
    species: Species
    char_class: ClassInfo
    background: Background
    level: int
    abilities: dict[str, int]
    skill_profs: set[str]
    saving_throw_profs: set[str]
    hp: int
    ac: int
    equipment: list[str]
    personality_trait: str
    ideal: str
    bond: str
    flaw: str
    origin_feat: str

    @property
    def proficiency_bonus(self) -> int:
        return 2 + (self.level - 1) // 4

    def skill_bonus(self, skill: str) -> int:
        ability = SKILL_ABILITIES[skill]
        base = ability_mod(self.abilities[ability])
        if skill in self.skill_profs:
            base += self.proficiency_bonus
        return base

    def save_bonus(self, ability: str) -> int:
        base = ability_mod(self.abilities[ability])
        if ability in self.saving_throw_profs:
            base += self.proficiency_bonus
        return base


def assign_abilities(char_class: ClassInfo, background: Background) -> dict[str, int]:
    """Assign standard array based on class primary abilities, with 2024 background bonuses."""
    abilities = {"STR": 0, "DEX": 0, "CON": 0, "INT": 0, "WIS": 0, "CHA": 0}
    array = list(STANDARD_ARRAY)

    # Assign highest to primary abilities
    for prim in char_class.primary_ability:
        abilities[prim] = array.pop(0)

    # CON is always important
    if abilities["CON"] == 0:
        abilities["CON"] = array.pop(0)

    # Assign rest randomly to remaining
    remaining = [a for a in abilities if abilities[a] == 0]
    random.shuffle(remaining)
    for ab in remaining:
        abilities[ab] = array.pop(0)

    # Apply background ability bonuses (2024 rules: +2 to one, +1 to another from 3 options)
    # Prioritize primary class abilities if in options, else pick best options
    options = background.ability_options
    primary_in_options = [p for p in char_class.primary_ability if p in options]

    if primary_in_options:
        # +2 to primary that's in options
        abilities[primary_in_options[0]] += 2
        # +1 to another option
        other_options = [o for o in options if o != primary_in_options[0]]
        abilities[other_options[0]] += 1
    else:
        # Just pick first two options
        abilities[options[0]] += 2
        abilities[options[1]] += 1

    return abilities


def calculate_ac(char_class: ClassInfo, abilities: dict[str, int]) -> int:
    """Calculate AC based on class and abilities."""
    dex_mod = ability_mod(abilities["DEX"])

    if char_class.name == "Barbarian":
        # Unarmored defense
        return 10 + dex_mod + ability_mod(abilities["CON"])
    elif char_class.name == "Monk":
        return 10 + dex_mod + ability_mod(abilities["WIS"])
    elif "All armor" in char_class.armor_profs or char_class.name in ["Fighter", "Paladin"]:
        # Chain mail (AC 16, no DEX)
        return 16
    elif "Medium" in char_class.armor_profs:
        # Scale mail (AC 14 + DEX max 2)
        return 14 + min(dex_mod, 2)
    elif "Light" in char_class.armor_profs:
        # Leather (AC 11 + DEX)
        return 11 + dex_mod
    else:
        return 10 + dex_mod


def generate_character(species_key: str, class_key: str, bg_key: str, name: str = "Adventurer") -> Character:
    """Generate a complete level 1 character using 2024 PHB rules."""
    species = SPECIES[species_key]
    char_class = CLASSES[class_key]
    background = BACKGROUNDS[bg_key]

    abilities = assign_abilities(char_class, background)

    # Collect skill proficiencies
    skill_profs = set()
    # Species skills (filter out "Choice" placeholder)
    for s in species.skill_profs:
        if s != "Choice":
            skill_profs.add(s)
    skill_profs.update(background.skill_profs)

    # Pick class skills
    available_class_skills = [s for s in char_class.skill_choices if s not in skill_profs]
    if "Any" in char_class.skill_choices:
        available_class_skills = [s for s in ALL_SKILLS if s not in skill_profs]

    chosen_skills = random.sample(available_class_skills, min(char_class.num_skills, len(available_class_skills)))
    skill_profs.update(chosen_skills)

    # Human Skillful trait: one extra skill
    if species.name == "Human":
        extra_skills = [s for s in ALL_SKILLS if s not in skill_profs]
        if extra_skills:
            skill_profs.add(random.choice(extra_skills))

    # Saving throws
    saving_throw_profs = set(char_class.saving_throws)

    # HP
    con_mod = ability_mod(abilities["CON"])
    hp = char_class.hit_die + con_mod
    # Dwarf Dwarven Toughness: +1 HP per level
    if species.name == "Dwarf":
        hp += 1
    # Tough feat from Farmer background: +2 HP per level
    if background.origin_feat == "Tough":
        hp += 2

    # AC
    ac = calculate_ac(char_class, abilities)

    # Equipment (class equipment + background equipment)
    equipment = list(char_class.starting_equipment) + background.equipment

    # Personality
    personality_trait = random.choice(background.traits)
    ideal = random.choice(background.ideals)
    bond = random.choice(background.bonds)
    flaw = random.choice(background.flaws)

    return Character(
        name=name,
        species=species,
        char_class=char_class,
        background=background,
        level=1,
        abilities=abilities,
        skill_profs=skill_profs,
        saving_throw_profs=saving_throw_profs,
        hp=hp,
        ac=ac,
        equipment=equipment,
        personality_trait=personality_trait,
        ideal=ideal,
        bond=bond,
        flaw=flaw,
        origin_feat=background.origin_feat,
    )


def generate_text_sheet(char: Character) -> str:
    """Generate a text representation of the character sheet."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"  {char.name}")
    lines.append(f"  {char.species.name} {char.char_class.name} (Level {char.level})")
    lines.append(f"  Background: {char.background.name}")
    lines.append("=" * 60)
    lines.append("")

    # Abilities
    lines.append("ABILITY SCORES")
    lines.append("-" * 40)
    for ab in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        score = char.abilities[ab]
        mod = ability_mod(score)
        save = char.save_bonus(ab)
        prof_mark = "*" if ab in char.saving_throw_profs else " "
        lines.append(f"  {ab}: {score:2d} ({mod_str(mod):>3})  Save: {mod_str(save):>3} {prof_mark}")
    lines.append("")

    # Combat stats
    lines.append("COMBAT")
    lines.append("-" * 40)
    lines.append(f"  AC: {char.ac}   Initiative: {mod_str(ability_mod(char.abilities['DEX']))}")
    lines.append(f"  HP: {char.hp}   Hit Dice: 1d{char.char_class.hit_die}")
    lines.append(f"  Speed: {char.species.speed} ft   Prof. Bonus: +{char.proficiency_bonus}")
    lines.append("")

    # Skills
    lines.append("SKILLS (* = proficient)")
    lines.append("-" * 40)
    for skill in ALL_SKILLS:
        bonus = char.skill_bonus(skill)
        prof_mark = "*" if skill in char.skill_profs else " "
        lines.append(f"  {prof_mark} {skill}: {mod_str(bonus):>3}")
    lines.append("")

    # Features
    lines.append("FEATURES & TRAITS")
    lines.append("-" * 40)
    lines.append("  Species:")
    for trait in char.species.traits:
        lines.append(f"    - {trait}")
    if char.species.darkvision:
        lines.append(f"    - Darkvision ({char.species.darkvision} ft)")
    lines.append("  Class:")
    for feature in char.char_class.features:
        lines.append(f"    - {feature}")
    lines.append(f"  Origin Feat: {char.origin_feat}")
    lines.append("")

    # Proficiencies
    lines.append("PROFICIENCIES")
    lines.append("-" * 40)
    lines.append(f"  Armor: {', '.join(char.char_class.armor_profs) or 'None'}")
    lines.append(f"  Weapons: {', '.join(char.char_class.weapon_profs)}")
    if char.background.tool_profs:
        lines.append(f"  Tools: {', '.join(char.background.tool_profs)}")
    lines.append(f"  Languages: Common + 2 of choice")
    lines.append("")

    # Equipment
    lines.append("EQUIPMENT")
    lines.append("-" * 40)
    for item in char.equipment:
        lines.append(f"  - {item}")
    lines.append("")

    # Personality
    lines.append("PERSONALITY")
    lines.append("-" * 40)
    lines.append(f"  Trait: {char.personality_trait}")
    lines.append(f"  Ideal: {char.ideal}")
    lines.append(f"  Bond: {char.bond}")
    lines.append(f"  Flaw: {char.flaw}")
    lines.append("")

    return "\n".join(lines)


# Mapping from skill names to PDF checkbox field names
SKILL_CHECKBOX_MAP = {
    "Acrobatics": "Check Box 23",
    "Animal Handling": "Check Box 24",
    "Arcana": "Check Box 25",
    "Athletics": "Check Box 26",
    "Deception": "Check Box 27",
    "History": "Check Box 28",
    "Insight": "Check Box 29",
    "Intimidation": "Check Box 30",
    "Investigation": "Check Box 31",
    "Medicine": "Check Box 32",
    "Nature": "Check Box 33",
    "Perception": "Check Box 34",
    "Performance": "Check Box 35",
    "Persuasion": "Check Box 36",
    "Religion": "Check Box 37",
    "Sleight of Hand": "Check Box 38",
    "Stealth": "Check Box 39",
    "Survival": "Check Box 40",
}

SAVE_CHECKBOX_MAP = {
    "STR": "Check Box 11",
    "DEX": "Check Box 18",
    "CON": "Check Box 19",
    "INT": "Check Box 20",
    "WIS": "Check Box 21",
    "CHA": "Check Box 22",
}

SKILL_FIELD_MAP = {
    "Acrobatics": "Acrobatics",
    "Animal Handling": "Animal",
    "Arcana": "Arcana",
    "Athletics": "Athletics",
    "Deception": "Deception ",
    "History": "History ",
    "Insight": "Insight",
    "Intimidation": "Intimidation",
    "Investigation": "Investigation ",
    "Medicine": "Medicine",
    "Nature": "Nature",
    "Perception": "Perception ",
    "Performance": "Performance",
    "Persuasion": "Persuasion",
    "Religion": "Religion",
    "Sleight of Hand": "SleightofHand",
    "Stealth": "Stealth ",
    "Survival": "Survival",
}


def get_template_path() -> Path:
    """Get the path to the PDF template."""
    return BASE_DIR / "templates" / "character_sheet.pdf"


def _build_pdf_writer(char: Character) -> PdfWriter:
    """Build a PdfWriter with character data filled in. Used by both file and bytes output."""
    reader = PdfReader(get_template_path())
    writer = PdfWriter()
    writer.append(reader)

    fields = {}

    # Basic info
    fields["CharacterName"] = char.name
    fields["CharacterName 2"] = char.name
    fields["ClassLevel"] = f"{char.char_class.name} 1"
    fields["Background"] = char.background.name
    fields["Race "] = char.species.name
    fields["Alignment"] = random.choice(["Lawful Good", "Neutral Good", "Chaotic Good", "Lawful Neutral", "Neutral", "Chaotic Neutral"])

    fields["XP"] = "0"

    # Ability scores
    for ab in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        fields[ab] = str(char.abilities[ab])
        mod_field = ab + "mod" if ab != "DEX" else "DEXmod "
        if ab == "CHA":
            mod_field = "CHamod"
        fields[mod_field] = mod_str(ability_mod(char.abilities[ab]))

    # Saves
    fields["ST Strength"] = mod_str(char.save_bonus("STR"))
    fields["ST Dexterity"] = mod_str(char.save_bonus("DEX"))
    fields["ST Constitution"] = mod_str(char.save_bonus("CON"))
    fields["ST Intelligence"] = mod_str(char.save_bonus("INT"))
    fields["ST Wisdom"] = mod_str(char.save_bonus("WIS"))
    fields["ST Charisma"] = mod_str(char.save_bonus("CHA"))

    # Combat
    fields["AC"] = str(char.ac)
    fields["Initiative"] = mod_str(ability_mod(char.abilities["DEX"]))
    fields["Speed"] = str(char.species.speed)
    fields["HPMax"] = str(char.hp)
    fields["HPCurrent"] = str(char.hp)
    fields["HDTotal"] = f"1d{char.char_class.hit_die}"
    fields["HD"] = "1"
    fields["ProfBonus"] = f"+{char.proficiency_bonus}"
    fields["Passive"] = str(10 + char.skill_bonus("Perception"))

    # Skills
    for skill, field_name in SKILL_FIELD_MAP.items():
        fields[field_name] = mod_str(char.skill_bonus(skill))

    # Equipment
    equipment_text = "\n".join(char.equipment)
    fields["Equipment"] = equipment_text

    # Proficiencies & Languages
    profs = []
    profs.append(f"Armor: {', '.join(char.char_class.armor_profs) or 'None'}")
    profs.append(f"Weapons: {', '.join(char.char_class.weapon_profs)}")
    if char.background.tool_profs:
        profs.append(f"Tools: {', '.join(char.background.tool_profs)}")
    #profs.append(f"Languages: {', '.join(char.species.languages)}")
    fields["ProficienciesLang"] = "\n".join(profs)

    # Features
    features = []
    features.extend(char.species.traits)
    if char.species.darkvision:
        features.append(f"Darkvision ({char.species.darkvision} ft)")
    features.extend(char.char_class.features)
    features.append(char.background.name)
    fields["Features and Traits"] = "\n".join(features)

    # Personality
    fields["PersonalityTraits "] = char.personality_trait
    fields["Ideals"] = char.ideal
    fields["Bonds"] = char.bond
    fields["Flaws"] = char.flaw

    # Update text fields
    writer.update_page_form_field_values(writer.pages[0], fields)
    if len(writer.pages) > 1:
        writer.update_page_form_field_values(writer.pages[1], fields)
    if len(writer.pages) > 2:
        writer.update_page_form_field_values(writer.pages[2], fields)

    # Handle checkboxes for proficiencies
    from pypdf.generic import NameObject
    for page in writer.pages:
        if "/Annots" in page:
            for annot in page["/Annots"]:
                annot_obj = annot.get_object()
                if "/T" in annot_obj:
                    field_name = annot_obj["/T"]
                    # Check saving throw proficiencies
                    for ab, checkbox_name in SAVE_CHECKBOX_MAP.items():
                        if field_name == checkbox_name and ab in char.saving_throw_profs:
                            annot_obj.update({
                                NameObject("/V"): NameObject("/Yes"),
                                NameObject("/AS"): NameObject("/Yes")
                            })
                    # Check skill proficiencies
                    for skill, checkbox_name in SKILL_CHECKBOX_MAP.items():
                        if field_name == checkbox_name and skill in char.skill_profs:
                            annot_obj.update({
                                NameObject("/V"): NameObject("/Yes"),
                                NameObject("/AS"): NameObject("/Yes")
                            })

    return writer


def generate_pdf_bytes(char: Character) -> bytes:
    """Generate a filled PDF character sheet and return as bytes. Used by web tier."""
    writer = _build_pdf_writer(char)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def fill_pdf(char: Character, output_path: str):
    """Fill the D&D character sheet PDF and write to file. Used by CLI."""
    writer = _build_pdf_writer(char)
    with open(output_path, "wb") as f:
        writer.write(f)


def prompt_choice(prompt: str, options: dict) -> str:
    """Prompt user to choose from options."""
    print(f"\n{prompt}")
    sorted_keys = sorted(options.keys())
    for i, key in enumerate(sorted_keys, 1):
        display = options[key].name if hasattr(options[key], 'name') else key.title()
        print(f"  {i}. {display}")

    while True:
        try:
            choice = input("\nEnter number: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(sorted_keys):
                return sorted_keys[idx]
        except ValueError:
            pass
        print("Invalid choice, try again.")


def main():
    print("\n" + "=" * 60)
    print("  D&D 5e Character Generator")
    print("=" * 60)

    name = input("\nCharacter name (or press Enter for random): ").strip()
    if not name:
        name = random.choice(["Aldric", "Brynn", "Caelum", "Dara", "Eldrin", "Fira", "Galen", "Hira", "Ivar", "Jaya"])

    race_key = prompt_choice("Choose your race:", SPECIES)
    class_key = prompt_choice("Choose your class:", CLASSES)
    bg_key = prompt_choice("Choose your background:", BACKGROUNDS)

    print("\nGenerating character...")
    char = generate_character(race_key, class_key, bg_key, name)

    # Generate text sheet
    text_sheet = generate_text_sheet(char)
    print("\n" + text_sheet)

    # Ensure characters directory exists
    characters_dir = "characters"
    os.makedirs(characters_dir, exist_ok=True)

    # Save text version
    text_file = os.path.join(characters_dir, f"{char.name.lower().replace(' ', '_')}_character.txt")
    with open(text_file, "w") as f:
        f.write(text_sheet)
    print(f"Text character sheet saved to: {text_file}")

    # Fill PDF
    pdf_file = os.path.join(characters_dir, f"{char.name.lower().replace(' ', '_')}_character.pdf")
    fill_pdf(char, pdf_file)
    print(f"PDF character sheet saved to: {pdf_file}")

    print("\nDone! Happy adventuring!")


if __name__ == "__main__":
    main()
