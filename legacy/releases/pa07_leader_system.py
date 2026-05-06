import random
import time
from datetime import datetime
import os
import math
import json
from collections import defaultdict

"""
====================== LEADER SYSTEM ======================
Gives each civilization a personality and creates dynastic histories
"""

class Leader:
    """Represents a ruler who guides a civilization's decisions and personality"""
    
    # Leader name components for random generation
    MALE_NAMES = ["Alaric", "Borin", "Cedric", "Darian", "Eldrin", "Faron", "Gareth", "Hakon", 
                  "Ivor", "Jarek", "Kael", "Lorik", "Marek", "Nolan", "Orin", "Pavel", "Quinn",
                  "Rurik", "Soren", "Torval", "Uther", "Varek", "Willem", "Xander", "Yorin", "Zane"]
    
    FEMALE_NAMES = ["Althea", "Brienne", "Cyrene", "Diana", "Elara", "Freyja", "Gwen", "Helena",
                    "Ilyana", "Jocelyn", "Kara", "Lyra", "Morgan", "Nyssa", "Orla", "Piper",
                    "Quinn", "Rhian", "Sylvia", "Talia", "Ursa", "Valeria", "Willow", "Xandra",
                    "Yara", "Zara"]
    
    TITLES = ["King", "Queen", "Emperor", "Empress", "Chief", "Lord", "Lady", "Archon", 
              "High Priest", "High Priestess", "Grand Duke", "Grand Duchess", "Pharaoh", 
              "Sultan", "Khan", "Shogun", "Consul", "Regent", "Viceroy", "Warlord"]
    
    SURNAMES = ["the Wise", "the Bold", "the Great", "the Conqueror", "the Peacemaker", 
                "the Just", "the Cruel", "the Builder", "the Scholar", "the Diplomat",
                "the Unready", "the Strong", "the Lionheart", "the Fox", "the Bear",
                "the Dragon", "the Stormborn", "Ironhand", "Fireheart", "Stonefist"]
    
    def __init__(self, name=None, age=None, lifespan=None, charisma=None, intelligence=None, 
                 ambition=None, greed=None, caution=None, gender=None, title=None):
        """Initialize a leader with random traits or specified values"""
        
        # Basic identity
        self.gender = gender if gender is not None else random.choice(["male", "female"])
        self.name = name if name is not None else self.generate_name()
        self.title = title if title is not None else random.choice(self.TITLES)
        self.full_title = f"{self.title} {self.name}"
        
        # Age and lifespan
        self.age = age if age is not None else random.randint(25, 45)
        self.lifespan = lifespan if lifespan is not None else random.randint(50, 80)
        
        # Core personality traits (0-100 scale)
        self.charisma = charisma if charisma is not None else random.randint(30, 85)
        self.intelligence = intelligence if intelligence is not None else random.randint(30, 85)
        self.ambition = ambition if ambition is not None else random.randint(20, 90)
        self.greed = greed if greed is not None else random.randint(15, 70)
        self.caution = caution if caution is not None else random.randint(20, 80)
        
        # Leadership history
        self.years_ruled = 0
        self.legacy_score = 0
        self.major_achievements = []
        
        # Validate trait ranges
        self._clamp_traits()
    
    def generate_name(self):
        """Generate a culturally appropriate name based on gender"""
        if self.gender == "male":
            first_name = random.choice(self.MALE_NAMES)
        else:
            first_name = random.choice(self.FEMALE_NAMES)
        
        # 30% chance to have an epithet
        if random.random() < 0.3:
            return f"{first_name} {random.choice(self.SURNAMES)}"
        return first_name
    
    def _clamp_traits(self):
        """Ensure all traits stay within valid ranges"""
        self.charisma = max(0, min(100, self.charisma))
        self.intelligence = max(0, min(100, self.intelligence))
        self.ambition = max(0, min(100, self.ambition))
        self.greed = max(0, min(100, self.greed))
        self.caution = max(0, min(100, self.caution))
        self.age = max(0, self.age)
        self.lifespan = max(1, self.lifespan)
    
    def update_year(self):
        """Update leader for one year - age and potentially adjust traits"""
        self.age += 1
        self.years_ruled += 1
        
        # Small random trait adjustments (experience, fatigue)
        if random.random() < 0.3:  # 30% chance per year
            trait = random.choice(["charisma", "intelligence", "ambition", "greed", "caution"])
            current_value = getattr(self, trait)
            change = random.randint(-2, 3)  # Slight drift
            setattr(self, trait, max(0, min(100, current_value + change)))
        
        # Check for natural death
        if self.age >= self.lifespan:
            return "died"
        
        # Small chance of early death (illness, accident)
        if self.age > 40 and random.random() < 0.02:
            return "died_early"
        
        return "alive"
    
    def calculate_legacy(self):
        """Calculate the leader's legacy based on achievements and rule length"""
        base_legacy = min(100, self.years_ruled * 2)
        trait_bonus = (self.charisma + self.intelligence) // 4
        self.legacy_score = base_legacy + trait_bonus + len(self.major_achievements) * 10
        return self.legacy_score
    
    def add_achievement(self, achievement):
        """Add a major achievement to the leader's record"""
        self.major_achievements.append(achievement)
        self.calculate_legacy()
    
    def get_trait_modifiers(self):
        """Get numerical modifiers based on leader traits for game systems"""
        return {
            "diplomacy_bonus": (self.charisma - 50) / 50.0,  # -1.0 to +1.0
            "tech_bonus": (self.intelligence - 50) / 100.0,   # -0.5 to +0.5
            "war_chance_mod": (self.ambition - 50) / 100.0,   # -0.5 to +0.5
            "trade_bonus": (self.greed - 50) / 100.0,         # -0.5 to +0.5
            "caution_mod": (self.caution - 50) / 100.0,       # -0.5 to +0.5
            "happiness_bonus": (self.charisma - 50) / 200.0   # -0.25 to +0.25
        }
    
    def to_dict(self):
        """Convert leader data to dictionary for saving"""
        return {
            'name': self.name,
            'gender': self.gender,
            'title': self.title,
            'full_title': self.full_title,
            'age': self.age,
            'lifespan': self.lifespan,
            'charisma': self.charisma,
            'intelligence': self.intelligence,
            'ambition': self.ambition,
            'greed': self.greed,
            'caution': self.caution,
            'years_ruled': self.years_ruled,
            'legacy_score': self.legacy_score,
            'major_achievements': self.major_achievements
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create leader from saved dictionary data"""
        leader = cls(
            name=data['name'],
            age=data['age'],
            lifespan=data['lifespan'],
            charisma=data['charisma'],
            intelligence=data['intelligence'],
            ambition=data['ambition'],
            greed=data['greed'],
            caution=data['caution'],
            gender=data['gender'],
            title=data['title']
        )
        leader.years_ruled = data['years_ruled']
        leader.legacy_score = data['legacy_score']
        leader.major_achievements = data['major_achievements']
        return leader
    
    def __str__(self):
        return f"{self.full_title} (Age: {self.age}, Ruled: {self.years_ruled} years)"

"""
====================== CORE SYSTEMS ======================
Enhanced with leader integration
"""

class WorldMap:
    """Handles world geography and civilization placement"""
    def __init__(self, width=40, height=20, seed=None):
        self.width = width
        self.height = height
        self.seed = seed if seed is not None else datetime.now().timestamp()
        self.rng = random.Random(self.seed)
        
        self.grid = [['.' for _ in range(width)] for _ in range(height)]
        self.terrain_types = {
            '.': "Plains", '^': "Mountains", '~': "Rivers", 
            '*': "Forests", '#': "Desert"
        }
        self.civilization_locations = {}

    def generate_geography(self):
        """Generate basic terrain features using the seeded RNG"""
        for y in range(self.height):
            for x in range(self.width):
                r = self.rng.random()
                if r < 0.05:
                    self.grid[y][x] = '^'
                elif r < 0.15:
                    self.grid[y][x] = '*'
                elif r < 0.2:
                    self.grid[y][x] = '~'
                elif r < 0.25:
                    self.grid[y][x] = '#'

        for _ in range(self.rng.randint(3, 5)):
            x, y = self.rng.randint(0, self.width-1), self.rng.randint(0, self.height-1)
            length = self.rng.randint(5, 10)
            for _ in range(length):
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.grid[y][x] = '~'
                    x += self.rng.choice([-1, 0, 1])
                    y += 1

    def get_terrain_bonus(self, position):
        """Get economic bonuses based on terrain type at position"""
        x, y = position
        if 0 <= x < self.width and 0 <= y < self.height:
            terrain = self.grid[y][x]
            if terrain == '~':
                return {"food": 300, "wealth": 100}
            elif terrain == '^':
                return {"metal": 200, "food": -100}
            elif terrain == '*':
                return {"food": 150, "metal": 100}
            elif terrain == '#':
                return {"food": -200, "wealth": 50}
            else:
                return {"food": 100, "metal": 50}
        return {"food": 0, "metal": 0, "wealth": 0}

    def place_civilization(self, civ):
        """Find suitable location for a civilization"""
        for _ in range(50):
            x, y = self.rng.randint(0, self.width-1), self.rng.randint(0, self.height-1)
            if self.grid[y][x] == '.':
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.width and 0 <= ny < self.height:
                            if self.grid[ny][nx] == '~':
                                self.civilization_locations[civ.name] = (x, y)
                                civ.map_position = (x, y)
                                return True
        return False

    def display(self, civilizations):
        """Print ASCII map of the world"""
        print("\nWorld Map:")
        for y in range(self.height):
            row = []
            for x in range(self.width):
                for civ in civilizations:
                    if (x, y) == civ.map_position:
                        row.append(civ.name[0].upper())
                        break
                else:
                    row.append(self.grid[y][x])
            print("".join(row))
        
        print("\nLegend:")
        print("Letters: Civilizations (first letter)")
        for symbol, name in self.terrain_types.items():
            print(f"{symbol}: {name}")

    def to_dict(self):
        return {
            'width': self.width, 'height': self.height, 'seed': self.seed,
            'grid': self.grid, 'civilization_locations': self.civilization_locations
        }

    @classmethod
    def from_dict(cls, data):
        world_map = cls(width=data['width'], height=data['height'], seed=data['seed'])
        world_map.grid = data['grid']
        world_map.civilization_locations = data['civilization_locations']
        return world_map

class ClimateSystem:
    """Handles seasonal changes and weather events"""
    def __init__(self, rng=None):
        self.season = "Spring"
        self.temperature = 15
        self.rainfall = 50
        self.rng = rng if rng is not None else random.Random()

    def update(self):
        seasons = ["Spring", "Summer", "Autumn", "Winter"]
        current_idx = seasons.index(self.season)
        self.season = seasons[(current_idx + 1) % 4]
        
        if self.season == "Summer":
            self.temperature = 25 + self.rng.uniform(-5, 5)
        elif self.season == "Winter":
            self.temperature = 5 + self.rng.uniform(-5, 5)
        else:
            self.temperature = 15 + self.rng.uniform(-5, 5)
        
        if self.season in ["Spring", "Autumn"]:
            self.rainfall = 60 + self.rng.uniform(-20, 20)
        else:
            self.rainfall = 40 + self.rng.uniform(-15, 15)

    def get_climate_modifiers(self):
        modifiers = {"food": 0, "metal": 0, "wealth": 0}
        
        if self.temperature > 30:
            modifiers["food"] -= 100
        elif self.temperature < 0:
            modifiers["food"] -= 150
        else:
            modifiers["food"] += 50
            
        if self.rainfall > 80:
            modifiers["food"] -= 100
            modifiers["wealth"] -= 50
        elif self.rainfall < 20:
            modifiers["food"] -= 200
        else:
            modifiers["food"] += 50
            
        return modifiers

    def to_dict(self):
        return {
            'season': self.season,
            'temperature': self.temperature,
            'rainfall': self.rainfall
        }

    @classmethod
    def from_dict(cls, data, rng=None):
        climate = cls(rng=rng)
        climate.season = data['season']
        climate.temperature = data['temperature']
        climate.rainfall = data['rainfall']
        return climate

class Civilization:
    """Represents a civilization with leader-driven personality"""
    
    # SOCIETAL CONSTANTS
    FARMER_YIELD = 2.0
    MERCHANT_WEALTH = 1.5
    SCHOLAR_TECH = 0.001
    
    BASE_FOOD_CONSUMPTION = 0.5
    SOLDIER_FOOD_UPKEEP = 0.3
    SOLDIER_WEALTH_UPKEEP = 0.1
    SCHOLAR_WEALTH_UPKEEP = 0.2
    NOBLE_WEALTH_UPKEEP = 0.4
    
    def __init__(self, world, id_num, name=None, population=None, technology=None, map_position=None):
        self.world = world
        self.id = id_num
        self.name = name if name is not None else self.generate_name()
        self.population = population if population is not None else random.randint(1000, 5000)
        self.technology = technology if technology is not None else 1.0
        self.map_position = map_position if map_position is not None else (0, 0)
        self.recent_events = []
        
        # Diplomacy system
        self.relationships = {}
        self.traits = {
            "aggressive": random.uniform(0, 1),
            "peaceful": random.uniform(0, 1),
            "expansionist": random.uniform(0, 1)
        }
        
        # Economy system
        self.resources = {
            "food": random.randint(2000, 5000),
            "metal": random.randint(500, 1500),
            "wealth": random.randint(1000, 3000)
        }
        self.storage_limits = {
            "food": 10000, "metal": 5000, "wealth": 8000
        }
        self.economic_state = "stable"
        self.last_year_production = {"food": 0, "metal": 0, "wealth": 0}
        
        # Societal system
        self.society = {
            "farmers": 0.40, "soldiers": 0.15, "merchants": 0.20,
            "scholars": 0.10, "nobles": 0.15
        }
        self.happiness = 60.0
        self.stability = 70.0
        
        # Event system
        self.active_events = []
        self.peace_years = 0
        self.unrest_years = 0
        self.golden_age_years = 0
        self.rebellion_stage = "none"
        
        # Conflict system
        self.military_power = 0
        self.at_war = False
        self.war_targets = []
        self.war_history = []
        
        # NEW: Leader system
        self.leader = Leader()
        self.leader_history = []  # Past leaders and their legacies
        self.founding_year = 0  # Set when world is generated
        
    def generate_name(self):
        prefixes = ["Great ", "Holy ", "United "]
        roots = ["Ara", "Belo", "Cartha", "Dun"]
        suffixes = ["nia", "dor", "thia", "land"]
        name = random.choice(roots) + random.choice(suffixes)
        if random.random() > 0.7:
            name = random.choice(prefixes) + name
        return name
    
    # NEW: Leader management methods
    def update_leader(self, current_year):
        """Update leader for one year and handle succession if needed"""
        leader_status = self.leader.update_year()
        
        if leader_status == "died" or leader_status == "died_early":
            return self._handle_leader_succession(current_year, leader_status)
        
        return None  # No leadership change
    
    def _handle_leader_succession(self, current_year, death_type):
        """Handle leader death and succession"""
        old_leader = self.leader
        old_leader.calculate_legacy()
        
        # Record the death
        death_reason = "natural causes" if death_type == "died" else "an untimely demise"
        death_event = f"👑 {old_leader.full_title} of {self.name} has died of {death_reason} at age {old_leader.age}"
        
        # Add to history
        self.leader_history.append({
            "leader": old_leader.to_dict(),
            "end_year": current_year,
            "end_reason": death_type
        })
        
        # Create new leader with inheritance from previous
        new_leader = self._generate_successor(old_leader)
        
        # Record succession
        succession_event = f"👑 {new_leader.full_title} now rules {self.name}"
        
        self.leader = new_leader
        
        return [death_event, succession_event]
    
    def _generate_successor(self, previous_leader):
        """Generate a new leader influenced by the previous one's traits"""
        # Base inheritance with some variation
        base_traits = {
            "charisma": previous_leader.charisma + random.randint(-15, 15),
            "intelligence": previous_leader.intelligence + random.randint(-15, 15),
            "ambition": previous_leader.ambition + random.randint(-20, 20),
            "greed": previous_leader.greed + random.randint(-15, 15),
            "caution": previous_leader.caution + random.randint(-15, 15),
        }
        
        # Clamp traits
        for trait, value in base_traits.items():
            base_traits[trait] = max(20, min(90, value))
        
        return Leader(**base_traits)
    
    def get_leader_modifiers(self):
        """Get all modifiers from leader traits"""
        return self.leader.get_trait_modifiers()
    
    def apply_leader_bonuses(self):
        """Apply leader trait bonuses to civilization stats"""
        modifiers = self.get_leader_modifiers()
        
        # Charisma affects happiness and diplomacy
        self.happiness += modifiers["happiness_bonus"]
        
        # Intelligence affects technology
        self.technology += self.technology * modifiers["tech_bonus"] * 0.01
        
        # Clamp values
        self.happiness = max(0, min(100, self.happiness))
    
    def leader_react_to_event(self, event_type, event_severity):
        """Get leader's reaction to major events"""
        modifiers = self.get_leader_modifiers()
        reactions = []
        
        if event_type == "famine":
            if self.leader.intelligence > 70:
                # Wise leader implements reforms
                self.technology += 0.1
                self.stability += 5
                reactions.append(f"{self.leader.full_title} implements agricultural reforms")
            elif self.leader.intelligence < 40:
                # Foolish leader blames others
                self.stability -= 5
                reactions.append(f"{self.leader.full_title} blames nobles for the famine")
        
        elif event_type == "civil_war":
            if self.leader.charisma > 75:
                # Charismatic leader unites factions
                pop_saved = int(self.population * 0.05)
                self.population += pop_saved
                self.stability += 10
                reactions.append(f"{self.leader.full_title} unites the warring factions")
        
        elif event_type == "golden_age":
            if self.leader.ambition > 70:
                # Ambitious leader expands during golden age
                self.military_power *= 1.1
                reactions.append(f"{self.leader.full_title} expands military during prosperity")
        
        elif event_type == "cultural_boom":
            if self.leader.intelligence > 80:
                # Intelligent leader doubles cultural benefits
                self.technology += 0.2
                reactions.append(f"{self.leader.full_title} champions the cultural renaissance")
        
        elif event_type == "war_victory":
            if self.leader.charisma > 70:
                # Charismatic leader boosts morale after victory
                self.happiness += 10
                reactions.append(f"{self.leader.full_title}'s victory inspires the people")
        
        return reactions
    
    def initialize_relationships(self, other_civilizations):
        for other_civ in other_civilizations:
            if other_civ.name != self.name:
                initial_attitude = random.randint(-15, 15)
                self.relationships[other_civ.name] = {
                    "attitude": initial_attitude,
                    "last_event": "none",
                    "years_since_contact": 0
                }
    
    def update_relationship_drift(self):
        for other_civ_name, relationship in self.relationships.items():
            attitude = relationship["attitude"]
            if attitude > 0:
                relationship["attitude"] = max(0, attitude - 1)
            elif attitude < 0:
                relationship["attitude"] = min(0, attitude + 1)
            relationship["years_since_contact"] += 1
    
    def get_relationship_status(self, attitude):
        if attitude >= 70: return "Allied"
        elif attitude >= 40: return "Friendly"
        elif attitude >= 10: return "Positive"
        elif attitude <= -70: return "At War"
        elif attitude <= -40: return "Hostile"
        elif attitude <= -10: return "Tense"
        else: return "Neutral"

    def update_society_and_economy(self):
        """Calculates all resource, tech, and societal changes for one year."""
        
        # Get population counts
        pop_farmers = int(self.population * self.society['farmers'])
        pop_soldiers = int(self.population * self.society['soldiers'])
        pop_merchants = int(self.population * self.society['merchants'])
        pop_scholars = int(self.population * self.society['scholars'])
        pop_nobles = int(self.population * self.society['nobles'])

        # Get modifiers
        terrain_bonus = self.world.world_map.get_terrain_bonus(self.map_position)
        climate_modifiers = self.world.climate.get_climate_modifiers()
        
        # Calculate resource deltas
        production = {"food": 0, "metal": 0, "wealth": 0}
        consumption = {"food": 0, "metal": 0, "wealth": 0}
        
        # FOOD
        base_food = pop_farmers * self.FARMER_YIELD
        production["food"] = base_food + terrain_bonus.get("food", 0) + climate_modifiers.get("food", 0)
        consumption["food"] = (self.population * self.BASE_FOOD_CONSUMPTION) + \
                              (pop_soldiers * self.SOLDIER_FOOD_UPKEEP)

        # METAL
        production["metal"] = 50 + terrain_bonus.get("metal", 0) + climate_modifiers.get("metal", 0)
        consumption["metal"] = int(self.population * 0.02)

        # WEALTH
        base_wealth = pop_merchants * self.MERCHANT_WEALTH
        production["wealth"] = base_wealth + terrain_bonus.get("wealth", 0) + climate_modifiers.get("wealth", 0)
        consumption["wealth"] = (pop_nobles * self.NOBLE_WEALTH_UPKEEP) + \
                                (pop_scholars * self.SCHOLAR_WEALTH_UPKEEP) + \
                                (pop_soldiers * self.SOLDIER_WEALTH_UPKEEP)
        
        # Calculate tech with leader bonus
        tech_gain = pop_scholars * self.SCHOLAR_TECH
        leader_modifiers = self.get_leader_modifiers()
        tech_gain *= (1 + leader_modifiers["tech_bonus"])
        self.technology += tech_gain
        
        # Calculate military power
        self.calculate_military_power()
        
        # Final deltas
        deltas = {}
        for resource in ["food", "metal", "wealth"]:
            deltas[resource] = int(production[resource] - consumption[resource])
        
        self.last_year_production = production

        # Update happiness & stability with leader bonuses
        if (self.resources["food"] + deltas["food"]) < 0:
            self.happiness -= 10
            self.stability -= 15
        else:
            self.happiness += 2 + leader_modifiers["happiness_bonus"]
            self.stability += 1

        if self.economic_state == "booming":
            self.happiness += 5
        elif self.economic_state == "crisis":
            self.happiness -= 5
            self.stability -= 5

        self.happiness = max(0, min(100, self.happiness))
        self.stability = max(0, min(100, self.stability))
        
        return deltas, tech_gain

    def calculate_military_power(self):
        """Calculate military strength based on population, soldiers, tech, and metal"""
        soldier_count = self.population * self.society["soldiers"]
        self.military_power = (
            soldier_count * 0.8 +  # Number of troops
            self.technology * 50 +  # Better weapons and training
            self.resources["metal"] * 0.5  # Equipment quality
        )
        return self.military_power

    def update_economy(self):
        economic_events = []
        
        resource_deltas, tech_gain = self.update_society_and_economy()
        
        if tech_gain > 0:
            economic_events.append(f"🔬 {self.name} scholars advanced technology by {tech_gain:.3f}")
        
        for resource, amount in resource_deltas.items():
            self.resources[resource] += amount
            if amount > 0:
                economic_events.append(f"📈 {self.name} produced a surplus of {amount} {resource}")
            elif amount < 0:
                economic_events.append(f"📉 {self.name} consumed {abs(amount)} {resource}")
        
        crisis_events = self._check_resource_crises()
        economic_events.extend(crisis_events)
        
        self._apply_storage_limits()
        self._apply_resource_decay()
        self._update_economic_state()
        
        return economic_events

    def _check_resource_crises(self):
        crisis_events = []
        
        if self.resources["food"] < 500:
            starvation = int(self.population * 0.05)
            self.population = max(100, self.population - starvation)
            crisis_events.append(f"🍂 {self.name} suffered famine! -{starvation} population")
            for other_civ_name in self.relationships:
                self.relationships[other_civ_name]["attitude"] -= 5
        
        if self.resources["metal"] < 100:
            crisis_events.append(f"⚒️ {self.name} faces metal shortage - military weakened")
        
        if self.resources["wealth"] < 0:
            tech_loss = 0.1
            self.technology = max(0.1, self.technology - tech_loss)
            crisis_events.append(f"💸 {self.name} economic crash! -{tech_loss} technology")
        
        if self.resources["food"] > 8000:
            pop_growth_bonus = int(self.population * 0.02)
            self.population += pop_growth_bonus
            crisis_events.append(f"🌾 {self.name} food surplus! +{pop_growth_bonus} population")
        
        if self.resources["wealth"] > 6000:
            tech_bonus = 0.05
            self.technology += tech_bonus
            crisis_events.append(f"💰 {self.name} wealth surplus! +{tech_bonus} technology")
        
        return crisis_events

    def _apply_storage_limits(self):
        for resource, limit in self.storage_limits.items():
            if self.resources[resource] > limit:
                excess = self.resources[resource] - limit
                self.resources[resource] = limit
                self.resources["wealth"] += int(excess * 0.1)

    def _apply_resource_decay(self):
        for resource in self.resources:
            if self.resources[resource] > 0:
                decay_rate = random.uniform(0.02, 0.05)
                decay_amount = int(self.resources[resource] * decay_rate)
                self.resources[resource] -= decay_amount

    def _update_economic_state(self):
        total_resources = sum(self.resources.values())
        avg_production = sum(self.last_year_production.values())
        
        if total_resources < 2000:
            self.economic_state = "crisis"
        elif avg_production > 1500:
            self.economic_state = "booming"
        elif avg_production < 500:
            self.economic_state = "recession"
        else:
            self.economic_state = "stable"

    def get_economic_diplomacy_modifier(self, other_civ):
        modifier = 0
        wealth_ratio = self.resources["wealth"] / max(1, other_civ.resources["wealth"])
        if 0.5 < wealth_ratio < 2.0:
            modifier += 5
        else:
            modifier += 10
        
        if self.resources["food"] < 500:
            modifier -= 15
        if other_civ.resources["food"] < 500:
            modifier -= 10
            
        return modifier

    # EVENT SYSTEM METHODS - Enhanced with leader reactions
    def check_events(self, year):
        """Scan current stats and trigger world events."""
        events = []
        
        if not self.is_at_war():
            self.peace_years += 1
        else:
            self.peace_years = 0
        
        # Check for standard events
        standard_events = []
        standard_events.extend(self._check_famine(year))
        standard_events.extend(self._check_civil_unrest(year))
        standard_events.extend(self._check_cultural_boom(year))
        standard_events.extend(self._check_golden_age(year))
        standard_events.extend(self._check_recovery(year))
        
        # Get leader reactions to major events
        for event in standard_events:
            if "FAMINE" in event:
                leader_reactions = self.leader_react_to_event("famine", "high")
                events.extend(leader_reactions)
            elif "CIVIL WAR" in event:
                leader_reactions = self.leader_react_to_event("civil_war", "high")
                events.extend(leader_reactions)
            elif "GOLDEN AGE" in event:
                leader_reactions = self.leader_react_to_event("golden_age", "high")
                events.extend(leader_reactions)
            elif "CULTURAL BOOM" in event:
                leader_reactions = self.leader_react_to_event("cultural_boom", "high")
                events.extend(leader_reactions)
        
        events.extend(standard_events)
        self.recent_events.extend(events)
        return events
    
    def is_at_war(self):
        """Check if civilization is at war with anyone"""
        for relationship in self.relationships.values():
            if relationship["attitude"] <= -70:
                return True
        return False
    
    def _check_famine(self, year):
        events = []
        famine_threshold = random.randint(-50, 0)
        
        if (self.resources["food"] < famine_threshold or 
            (self.happiness < 40 and self.resources["food"] < 100)):
            
            pop_loss = int(self.population * 0.1)
            self.population = max(100, self.population - pop_loss)
            self.stability -= 5
            
            event_msg = f"🍞 FAMINE! {self.name} suffered a devastating famine! -{pop_loss} population"
            events.append(event_msg)
            
            if "famine" not in self.active_events:
                self.active_events.append("famine")
        
        return events
    
    def _check_civil_unrest(self, year):
        events = []
        
        if self.happiness < 50 and self.stability < 50:
            self.unrest_years += 1
            self.resources["wealth"] -= 2
            self.stability -= 2
            
            if self.unrest_years == 1:
                event_msg = f"⚖️ UNREST! {self.name} faces civil unrest (happiness: {self.happiness:.0f})"
                events.append(event_msg)
                self.rebellion_stage = "unrest"
        
        elif self.stability < 40 and self.unrest_years >= 2:
            pop_loss = int(self.population * 0.1)
            self.population = max(100, self.population - pop_loss)
            
            event_msg = f"🔥 REBELLION! {self.name} faces open rebellion! -{pop_loss} population"
            events.append(event_msg)
            self.rebellion_stage = "rebellion"
        
        elif self.stability < 30 and self.unrest_years >= 3:
            event_msg = f"💥 CIVIL WAR! {self.name} collapses into civil war!"
            events.append(event_msg)
            self.rebellion_stage = "civil_war"
            self.population = int(self.population * 0.8)
            self.stability -= 20
        
        else:
            if self.unrest_years > 0 and self.stability > 60:
                self.unrest_years = max(0, self.unrest_years - 1)
                if self.rebellion_stage != "none":
                    event_msg = f"🕊️ {self.name}'s civil unrest has calmed"
                    events.append(event_msg)
                    self.rebellion_stage = "none"
        
        return events
    
    def _check_cultural_boom(self, year):
        events = []
        
        if (self.society["scholars"] > 0.15 and 
            self.resources["wealth"] > 2000 and 
            self.stability > 80):
            
            self.technology *= 1.1
            self.happiness += 3
            
            event_msg = f"🎭 CULTURAL BOOM! {self.name} experiences a cultural renaissance! +10% technology"
            events.append(event_msg)
            
            if "cultural_boom" not in self.active_events:
                self.active_events.append("cultural_boom")
        
        return events
    
    def _check_golden_age(self, year):
        events = []
        
        if (self.happiness > 80 and 
            self.stability > 80 and 
            self.peace_years >= 10 and
            "golden_age" not in self.active_events):
            
            self.golden_age_years = 10
            self.active_events.append("golden_age")
            event_msg = f"🌟 GOLDEN AGE! {self.name} enters a glorious golden age!"
            events.append(event_msg)
        
        if self.golden_age_years > 0:
            self.resources["food"] = int(self.resources["food"] * 1.05)
            self.resources["wealth"] = int(self.resources["wealth"] * 1.05)
            self.happiness = min(100, self.happiness + 5)
            self.golden_age_years -= 1
            
            if self.golden_age_years == 0:
                self.active_events.remove("golden_age")
                event_msg = f"🌅 {self.name}'s golden age has ended"
                events.append(event_msg)
        
        return events
    
    def _check_recovery(self, year):
        events = []
        
        if (self.happiness > 70 and 
            self.stability > 70 and 
            len(self.active_events) > 0):
            
            if "famine" in self.active_events and self.resources["food"] > 1000:
                self.active_events.remove("famine")
                event_msg = f"🌱 {self.name} has recovered from the famine"
                events.append(event_msg)
            
            if "cultural_boom" in self.active_events:
                self.active_events.remove("cultural_boom")
        
        self.happiness = max(0, min(100, self.happiness))
        self.stability = max(0, min(100, self.stability))
        
        return events

    def update(self):
        base_growth = random.randint(10, 100)
        happiness_mod = (self.happiness - 50) / 50.0
        
        economic_growth_bonus = 0
        if self.economic_state == "booming":
            economic_growth_bonus = int(base_growth * 0.5)
        elif self.economic_state == "crisis":
            economic_growth_bonus = -int(base_growth * 0.3)
        
        total_growth = int(base_growth + (base_growth * happiness_mod * 0.5) + economic_growth_bonus)
        
        if self.economic_state == "crisis" and total_growth > 0:
            total_growth = 0
            
        self.population += total_growth
        self.population = max(100, self.population)

        if random.random() < 0.3:
            events = [
                f"🏗️ {self.name} builds a new settlement",
                f"📜 {self.name} makes a scientific discovery",
                f"🌾 {self.name} has a bountiful harvest",
                f"⚔️ {self.name} engages in border skirmishes",
                f"💰 {self.name} discovers new trade routes",
                f"⚒️ {self.name} finds rich mineral deposits",
                f"🎭 {self.name} experiences cultural flourishing",
                f"⚖️ {self.name} undergoes social reforms"
            ]
            self.recent_events.append(random.choice(events))
    
    def get_events(self):
        events = self.recent_events.copy()
        self.recent_events.clear()
        return events

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'population': self.population,
            'technology': self.technology, 'map_position': self.map_position,
            'relationships': self.relationships, 'traits': self.traits,
            'resources': self.resources, 'storage_limits': self.storage_limits,
            'economic_state': self.economic_state, 'society': self.society,
            'happiness': self.happiness, 'stability': self.stability,
            'active_events': self.active_events, 'peace_years': self.peace_years,
            'unrest_years': self.unrest_years, 'golden_age_years': self.golden_age_years,
            'rebellion_stage': self.rebellion_stage,
            'military_power': self.military_power, 'at_war': self.at_war,
            'war_targets': self.war_targets, 'war_history': self.war_history,
            
            # NEW: Leader system attributes
            'leader': self.leader.to_dict(),
            'leader_history': self.leader_history,
            'founding_year': self.founding_year
        }

    @classmethod
    def from_dict(cls, world, data):
        civ = cls(
            world=world, id_num=data['id'], name=data['name'],
            population=data['population'], technology=data['technology'],
            map_position=data['map_position']
        )
        civ.relationships = data.get('relationships', {})
        civ.traits = data.get('traits', {})
        civ.resources = data.get('resources', {"food": 3000, "metal": 1000, "wealth": 2000})
        civ.storage_limits = data.get('storage_limits', {"food": 10000, "metal": 5000, "wealth": 8000})
        civ.economic_state = data.get('economic_state', 'stable')
        civ.society = data.get('society', {
            "farmers": 0.40, "soldiers": 0.15, "merchants": 0.20,
            "scholars": 0.10, "nobles": 0.15
        })
        civ.happiness = data.get('happiness', 60.0)
        civ.stability = data.get('stability', 70.0)
        civ.active_events = data.get('active_events', [])
        civ.peace_years = data.get('peace_years', 0)
        civ.unrest_years = data.get('unrest_years', 0)
        civ.golden_age_years = data.get('golden_age_years', 0)
        civ.rebellion_stage = data.get('rebellion_stage', 'none')
        civ.military_power = data.get('military_power', 0)
        civ.at_war = data.get('at_war', False)
        civ.war_targets = data.get('war_targets', [])
        civ.war_history = data.get('war_history', [])
        
        # NEW: Leader system attributes
        civ.leader = Leader.from_dict(data['leader'])
        civ.leader_history = data.get('leader_history', [])
        civ.founding_year = data.get('founding_year', 0)
        
        return civ

"""
====================== DIPLOMACY & CONFLICT SYSTEM ======================
Enhanced with leader personality integration
"""

class DiplomacySystem:
    """Manages diplomatic interactions and war resolution between civilizations"""
    
    EVENT_CHANCES = {
        "trade": {"min_attitude": 40, "chance": 10, "attitude_change": 10, "pop_effect": (100, 300)},
        "alliance": {"min_attitude": 70, "chance": 3, "attitude_change": 20, "tech_effect": 0.1},
        "skirmish": {"max_attitude": -40, "chance": 6, "attitude_change": -10, "pop_effect": (-200, -50)},
        "war": {"max_attitude": -70, "chance": 2, "attitude_change": -30, "pop_effect": (-0.3, -0.1)},
        "peace_treaty": {"during_war": True, "chance": 6, "attitude_change": 15, "pop_effect": (0.05, 0.1)}
    }
    
    INTERACTION_RADIUS = 12
    
    def __init__(self, world_map):
        self.world_map = world_map
    
    def calculate_distance(self, pos1, pos2):
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def process_diplomacy_year(self, civilizations, current_year):
        """Process diplomatic interactions for all civilization pairs"""
        diplomatic_events = []
        
        # Check for war declarations with leader influence
        war_events = self._check_war_declarations(civilizations, current_year)
        diplomatic_events.extend(war_events)
        
        # Process normal diplomacy
        for i, civ_a in enumerate(civilizations):
            for j, civ_b in enumerate(civilizations):
                if i >= j:
                    continue
                
                distance = self.calculate_distance(civ_a.map_position, civ_b.map_position)
                if distance > self.INTERACTION_RADIUS:
                    continue
                
                # Skip if already at war
                if civ_a.relationships[civ_b.name]["attitude"] <= -70:
                    continue
                
                attitude_a_to_b = civ_a.relationships[civ_b.name]["attitude"]
                attitude_b_to_a = civ_b.relationships[civ_a.name]["attitude"]
                
                economic_modifier = civ_a.get_economic_diplomacy_modifier(civ_b)
                
                # NEW: Add leader personality to diplomacy
                leader_modifiers = civ_a.get_leader_modifiers()
                personality_modifier = leader_modifiers["diplomacy_bonus"] * 10  # Scale to meaningful range
                
                event = self._determine_diplomatic_event(civ_a, civ_b, attitude_a_to_b, 
                                                        attitude_b_to_a, economic_modifier + personality_modifier)
                
                if event:
                    self._apply_diplomatic_event(civ_a, civ_b, event)
                    event_description = self._format_event_description(civ_a, civ_b, event)
                    diplomatic_events.append(event_description)
                    
                    civ_a.relationships[civ_b.name]["last_event"] = event["type"]
                    civ_b.relationships[civ_a.name]["last_event"] = event["type"]
                    civ_a.relationships[civ_b.name]["years_since_contact"] = 0
                    civ_b.relationships[civ_a.name]["years_since_contact"] = 0
        
        # Resolve ongoing wars
        war_resolution_events = self._resolve_ongoing_wars(civilizations, current_year)
        diplomatic_events.extend(war_resolution_events)
        
        return diplomatic_events
    
    # Enhanced with leader personality
    def _check_war_declarations(self, civilizations, current_year):
        """Check if any civilizations should declare war"""
        war_events = []
        
        for i, civ_a in enumerate(civilizations):
            for j, civ_b in enumerate(civilizations):
                if i >= j:
                    continue
                
                # Only check if not already at war
                if civ_a.relationships[civ_b.name]["attitude"] > -70:
                    if self._maybe_declare_war(civ_a, civ_b):
                        # Declare war
                        civ_a.relationships[civ_b.name]["attitude"] = -100
                        civ_b.relationships[civ_a.name]["attitude"] = -100
                        civ_a.at_war = True
                        civ_b.at_war = True
                        civ_a.war_targets.append(civ_b.name)
                        civ_b.war_targets.append(civ_a.name)
                        
                        # NEW: Include leader name in war declaration
                        event_msg = f"💥 WAR! {civ_a.leader.full_title} of {civ_a.name} declared war on {civ_b.name}!"
                        war_events.append(event_msg)
                        
                        # Record in war history
                        civ_a.war_history.append({
                            "year": current_year,
                            "enemy": civ_b.name,
                            "type": "declaration",
                            "outcome": "ongoing",
                            "leader": civ_a.leader.name  # NEW: Track which leader started war
                        })
        
        return war_events
    
    def _maybe_declare_war(self, civ_a, civ_b):
        """Determine if a civilization should declare war with leader influence"""
        # Base chance
        chance = 0.02
        
        # Economic desperation
        if civ_a.resources["food"] < 0 and civ_b.resources["wealth"] > civ_a.resources["wealth"] * 1.5:
            chance = 0.3
        
        # NEW: Leader personality effects
        leader_modifiers = civ_a.get_leader_modifiers()
        chance += leader_modifiers["war_chance_mod"] * 0.2  # Ambitious leaders more likely
        chance -= leader_modifiers["caution_mod"] * 0.1     # Cautious leaders less likely
        
        # Aggressive civilization trait
        if civ_a.traits["aggressive"] > 0.7:
            chance += 0.1
        
        # Existing tension
        if civ_a.relationships[civ_b.name]["attitude"] < -30:
            chance += 0.05
        
        # Military advantage
        if civ_a.military_power > civ_b.military_power * 1.5:
            chance += 0.05
        
        return random.random() < chance
    
    def _resolve_ongoing_wars(self, civilizations, current_year):
        """Resolve all ongoing wars"""
        war_events = []
        resolved_wars = set()
        
        for civ_a in civilizations:
            for target_name in civ_a.war_targets[:]:
                civ_b = next((c for c in civilizations if c.name == target_name), None)
                if not civ_b:
                    continue
                
                # Skip if already resolved
                war_pair = tuple(sorted([civ_a.name, civ_b.name]))
                if war_pair in resolved_wars:
                    continue
                
                # Resolve the war
                result = self._resolve_war(civ_a, civ_b)
                war_events.extend(result["events"])
                
                # Apply war results
                self._apply_war_results(civ_a, civ_b, result["winner"], result["loser"], result["type"])
                
                # NEW: Get leader reactions to war outcomes
                if result["winner"]:
                    winner_reactions = result["winner"].leader_react_to_event("war_victory", "high")
                    war_events.extend(winner_reactions)
                
                # Mark as resolved
                resolved_wars.add(war_pair)
                civ_a.war_targets.remove(civ_b.name)
                civ_b.war_targets.remove(civ_a.name)
                
                # Update war history
                for civ in [civ_a, civ_b]:
                    for war_record in civ.war_history:
                        if (war_record["enemy"] in [civ_a.name, civ_b.name] and 
                            war_record["outcome"] == "ongoing"):
                            war_record["outcome"] = result["type"]
                            war_record["end_year"] = current_year
        
        return war_events
    
    def _resolve_war(self, civ_a, civ_b):
        """Decide who wins a war based on military power"""
        events = []
        
        total_power = civ_a.military_power + civ_b.military_power
        if total_power == 0:
            return {
                "winner": None, "loser": None, "type": "stalemate",
                "events": [f"⚔️ War between {civ_a.name} and {civ_b.name} ends in stalemate"]
            }
        
        # Random roll weighted by military power
        roll = random.uniform(0, total_power)
        if roll < civ_a.military_power:
            winner, loser = civ_a, civ_b
        else:
            winner, loser = civ_b, civ_a
        
        # Determine victory type
        power_ratio = winner.military_power / max(loser.military_power, 1)
        if power_ratio > 1.5:
            result_type = "decisive_win"
            event_msg = f"🎯 {winner.leader.full_title} achieves decisive victory over {loser.name}!"
        elif power_ratio > 1.1:
            result_type = "victory"
            event_msg = f"⚔️ {winner.leader.full_title} defeats {loser.name} in battle!"
        else:
            result_type = "close_win"
            event_msg = f"⚖️ {winner.leader.full_title} narrowly defeats {loser.name}!"
        
        events.append(event_msg)
        
        return {
            "winner": winner, "loser": loser, "type": result_type, "events": events
        }
    
    def _apply_war_results(self, civ_a, civ_b, winner, loser, result_type):
        """Apply the consequences of war"""
        if result_type == "stalemate":
            civ_a.resources["wealth"] = int(civ_a.resources["wealth"] * 0.95)
            civ_b.resources["wealth"] = int(civ_b.resources["wealth"] * 0.95)
            civ_a.stability -= 2
            civ_b.stability -= 2
            
        elif winner and loser:
            if result_type == "decisive_win":
                winner.resources["wealth"] = int(winner.resources["wealth"] * 1.15)
                loser.population = int(loser.population * 0.85)
                loser.resources["wealth"] = int(loser.resources["wealth"] * 0.90)
                loser.stability -= 10
                winner.stability += 3
                
            elif result_type == "victory":
                winner.resources["wealth"] = int(winner.resources["wealth"] * 1.10)
                loser.population = int(loser.population * 0.90)
                loser.stability -= 5
                winner.stability += 2
                
            elif result_type == "close_win":
                winner.resources["wealth"] = int(winner.resources["wealth"] * 1.05)
                loser.population = int(loser.population * 0.95)
        
        # End the war
        civ_a.at_war = False
        civ_b.at_war = False
        civ_a.relationships[civ_b.name]["attitude"] = -50
        civ_b.relationships[civ_a.name]["attitude"] = -50
    
    def _determine_diplomatic_event(self, civ_a, civ_b, attitude_a_to_b, attitude_b_to_a, economic_modifier):
        avg_attitude = (attitude_a_to_b + attitude_b_to_a) / 2
        
        for event_type, params in self.EVENT_CHANCES.items():
            conditions_met = True
            
            if "min_attitude" in params and avg_attitude < params["min_attitude"]:
                conditions_met = False
            if "max_attitude" in params and avg_attitude > params["max_attitude"]:
                conditions_met = False
            if "during_war" in params and params["during_war"]:
                if attitude_a_to_b > -70 or attitude_b_to_a > -70:
                    conditions_met = False
            
            if conditions_met:
                modified_chance = params["chance"] + economic_modifier
                modified_chance = max(1, min(20, modified_chance))
                
                if random.randint(1, 100) <= modified_chance:
                    return {"type": event_type, "params": params, "avg_attitude": avg_attitude}
        
        return None
    
    def _apply_diplomatic_event(self, civ_a, civ_b, event):
        params = event["params"]
        
        civ_a.relationships[civ_b.name]["attitude"] += params["attitude_change"]
        civ_b.relationships[civ_a.name]["attitude"] += params["attitude_change"]
        
        civ_a.relationships[civ_b.name]["attitude"] = max(-100, min(100, civ_a.relationships[civ_b.name]["attitude"]))
        civ_b.relationships[civ_a.name]["attitude"] = max(-100, min(100, civ_b.relationships[civ_a.name]["attitude"]))
        
        if "pop_effect" in params:
            pop_effect = params["pop_effect"]
            if event["type"] in ["war", "peace_treaty"]:
                civ_a_mult = 1 + random.uniform(pop_effect[0], pop_effect[1])
                civ_b_mult = 1 + random.uniform(pop_effect[0], pop_effect[1])
                civ_a.population = max(100, int(civ_a.population * civ_a_mult))
                civ_b.population = max(100, int(civ_b.population * civ_b_mult))
            else:
                civ_a.population += random.randint(pop_effect[0], pop_effect[1])
                civ_b.population += random.randint(pop_effect[0], pop_effect[1])
        
        if "tech_effect" in params:
            tech_effect = params["tech_effect"]
            civ_a.technology += tech_effect
            civ_b.technology += tech_effect

        if event["type"] == "trade":
            trade_bonus = random.randint(100, 300)
            civ_a.resources["wealth"] += trade_bonus
            civ_b.resources["wealth"] += trade_bonus
            
            if civ_a.resources["food"] > 4000 and civ_b.resources["metal"] > 800:
                transfer = random.randint(200, 500)
                civ_a.resources["food"] -= transfer
                civ_b.resources["food"] += transfer
                civ_b.resources["metal"] -= int(transfer * 0.5)
                civ_a.resources["metal"] += int(transfer * 0.5)
    
    def _format_event_description(self, civ_a, civ_b, event):
        event_type = event["type"]
        attitude_change = event["params"]["attitude_change"]
        
        descriptions = {
            "trade": f"🤝 {civ_a.name} and {civ_b.name} established a trade pact (+{attitude_change} relations)",
            "alliance": f"🕊️ {civ_a.name} and {civ_b.name} formed an alliance (+{attitude_change} relations)",
            "skirmish": f"⚔️ {civ_a.name} and {civ_b.name} engaged in border skirmishes ({attitude_change} relations)",
            "war": f"💥 {civ_a.name} declared war on {civ_b.name} ({attitude_change} relations)",
            "peace_treaty": f"☮️ {civ_a.name} and {civ_b.name} signed a peace treaty (+{attitude_change} relations)"
        }
        
        return descriptions.get(event_type, f"{civ_a.name} and {civ_b.name} had diplomatic interactions")

"""
====================== MASTER CONTROL SYSTEM ======================
"""

class MasterControl:
    """Master control system for managing world simulation"""
    
    def __init__(self, world):
        self.world = world
        self.paused = False
        self.master_control_enabled = True
    
    def step_year(self):
        if not self.master_control_enabled:
            return self.world.advance_year()
            
        if self.paused:
            print("⏸️ Simulation paused")
            return None
        return self.world.advance_year()
    
    def skip_years(self, n):
        if not self.master_control_enabled:
            for _ in range(n):
                self.world.advance_year()
            return
            
        print(f"⏩ Fast-forwarding {n} years...")
        for i in range(n):
            if self.paused:
                print(f"⏸️ Paused at year {self.world.current_year + i}")
                break
            self.world.advance_year()
        
        self.show_summary()
    
    def show_summary(self):
        if not self.master_control_enabled:
            return
            
        print(f"\n📊 WORLD SUMMARY - Year {self.world.current_year}")
        print("=" * 60)
        for civ in self.world.civilizations:
            war_status = " ⚔️" if civ.at_war else " 🕊️"
            leader_age = f" (Age: {civ.leader.age})" if civ.leader else ""
            print(f"  {civ.name}: {civ.leader.full_title}{leader_age}")
            print(f"    Pop: {civ.population}, Wealth: {civ.resources['wealth']}, "
                  f"Tech: {civ.technology:.1f}, Military: {civ.military_power:.0f}{war_status}")
    
    def toggle_pause(self):
        if not self.master_control_enabled:
            return
            
        self.paused = not self.paused
        status = "paused" if self.paused else "resumed"
        print(f"⏸️ Simulation {status}")
    
    def jump_to_year(self, target_year):
        if not self.master_control_enabled:
            return
            
        years_to_skip = target_year - self.world.current_year
        if years_to_skip > 0:
            self.skip_years(years_to_skip)
        else:
            print("❌ Cannot jump to past years")

"""
====================== MAIN SIMULATION ======================
Enhanced with leader system integration
"""

class CivilizationObserver:
    """Main game class that orchestrates the simulation"""
    def __init__(self):
        self.world_seed = None
        self.current_year = 0
        self.civilizations = []
        self.world_map = None
        self.climate = None
        self.diplomacy = None
        self.history = []
        
        self.master_control = MasterControl(self)
    
    def generate_world(self, seed=None):
        self.world_seed = seed if seed is not None else datetime.now().timestamp()
        
        self.world_map = WorldMap(seed=self.world_seed)
        self.climate = ClimateSystem(rng=random.Random(self.world_seed))
        self.diplomacy = DiplomacySystem(self.world_map)
        
        self.world_map.generate_geography()
        
        civ_count = random.randint(3, 5)
        self.civilizations = [Civilization(self, i) for i in range(civ_count)]
        
        for civ in self.civilizations:
            self.world_map.place_civilization(civ)
            civ.founding_year = 0  # Set founding year
        
        for civ in self.civilizations:
            civ.initialize_relationships(self.civilizations)
        
        print(f"🌍 World Created (Seed: {self.world_seed})")
        print(f"🏙️ {len(self.civilizations)} civilizations generated")
        
        # NEW: Display initial leaders
        print(f"👑 Founding Leaders:")
        for civ in self.civilizations:
            leader = civ.leader
            print(f"  {civ.name}: {leader.full_title} (C:{leader.charisma} I:{leader.intelligence} A:{leader.ambition})")
    
    def advance_year(self):
        self.current_year += 1
        year_report = {
            "year": self.current_year,
            "world_events": [],
            "civilization_events": [],
            "diplomatic_events": [],
            "economic_events": [],
            "major_events": [],
            "war_events": [],
            "leadership_events": []  # NEW: Track leadership changes
        }
        
        self.climate.update()
        
        economic_events = []
        major_events = []
        war_events = []
        leadership_events = []  # NEW: Collect leadership events
        
        for civ in self.civilizations[:]:
            # NEW: Update leader and check for succession
            leader_events = civ.update_leader(self.current_year)
            if leader_events:
                leadership_events.extend(leader_events)
            
            # Apply leader bonuses
            civ.apply_leader_bonuses()
            
            civ_eco_events = civ.update_economy()
            economic_events.extend(civ_eco_events)
            
            civ_major_events = civ.check_events(self.current_year)
            major_events.extend(civ_major_events)
            
            if civ.war_history:
                for war in civ.war_history:
                    if war["year"] == self.current_year:
                        war_events.append(f"{civ.name} went to war with {war['enemy']}")
            
            civ.update()
            year_report["civilization_events"].extend(civ.get_events())
        
        year_report["economic_events"] = economic_events
        year_report["major_events"] = major_events
        year_report["war_events"] = war_events
        year_report["leadership_events"] = leadership_events  # NEW: Add leadership events
        
        diplomatic_events = self.diplomacy.process_diplomacy_year(self.civilizations, self.current_year)
        year_report["diplomatic_events"] = diplomatic_events
        
        for civ in self.civilizations:
            civ.update_relationship_drift()
        
        self.history.append(year_report)
        
        return year_report
    
    def display_world(self):
        self.world_map.display(self.civilizations)
        print(f"\nYear: {self.current_year}")
        print(f"Season: {self.climate.season}")
        print(f"Temperature: {self.climate.temperature:.1f}°C")
        print(f"Rainfall: {self.climate.rainfall:.1f}mm")
        print(f"World Seed: {self.world_seed}")
        
        print(f"\n👑 Leadership & Diplomacy:")
        for civ in self.civilizations:
            leader = civ.leader
            print(f"  {civ.name}: {leader.full_title} (Age: {leader.age}/{leader.lifespan})")
            for other_name, relationship in civ.relationships.items():
                status = civ.get_relationship_status(relationship["attitude"])
                war_indicator = " ⚔️" if status == "At War" else ""
                print(f"    - {other_name}: {status} ({relationship['attitude']}){war_indicator}")
        
        print(f"\n💼 Economic & Military Status:")
        for civ in self.civilizations:
            war_status = " ⚔️ AT WAR" if civ.at_war else ""
            leader_traits = f" C:{civ.leader.charisma} I:{civ.leader.intelligence} A:{civ.leader.ambition}"
            print(f"  {civ.name}{war_status}:{leader_traits}")
            print(f"    Food: {civ.resources['food']} | Metal: {civ.resources['metal']} | Wealth: {civ.resources['wealth']}")
            print(f"    Economy: {civ.economic_state.upper()} | Tech: {civ.technology:.2f} | Military: {civ.military_power:.0f}")
            print(f"    Society: 😊{civ.happiness:.0f} | 🛡️{civ.stability:.0f} | 👥{civ.population}")
            
            if civ.active_events:
                print(f"    Active Events: {', '.join(civ.active_events)}")
            if civ.rebellion_stage != "none":
                print(f"    Rebellion Stage: {civ.rebellion_stage.upper()}")

    def save_game(self, filename):
        save_data = {
            'world_seed': self.world_seed, 'current_year': self.current_year,
            'civilizations': [civ.to_dict() for civ in self.civilizations],
            'world_map': self.world_map.to_dict(), 'climate': self.climate.to_dict(),
            'history': self.history
        }
        
        with open(filename, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        print(f"Game saved to {filename}")

    def load_game(self, filename):
        try:
            with open(filename, 'r') as f:
                save_data = json.load(f)
            
            self.world_seed = save_data['world_seed']
            self.current_year = save_data['current_year']
            self.history = save_data['history']
            
            rng = random.Random(self.world_seed)
            self.world_map = WorldMap.from_dict(save_data['world_map'])
            self.climate = ClimateSystem.from_dict(save_data['climate'], rng=rng)
            self.diplomacy = DiplomacySystem(self.world_map)
            
            self.civilizations = [
                Civilization.from_dict(self, civ_data)
                for civ_data in save_data['civilizations']
            ]
            
            print(f"✅ Game loaded from {filename}")
            print(f"📅 Year: {self.current_year}")
            print(f"🏙️ Civilizations: {len(self.civilizations)}")
            print(f"🌱 World Seed: {self.world_seed}")
            
        except FileNotFoundError:
            print(f"❌ Save file '{filename}' not found.")
        except json.JSONDecodeError:
            print(f"❌ Save file '{filename}' is corrupted.")
        except Exception as e:
            print(f"❌ Error loading game: {e}")

    def run_automated_simulation(self, years=50):
        print(f"\n🤖 Running automated simulation for {years} years...")
        
        for year in range(years):
            year_report = self.advance_year()
            
            if (year + 1) % 10 == 0:
                print(f"\n--- Year {self.current_year} Summary ---")
                print(f"Civilizations: {len(self.civilizations)}")
                
                for civ in self.civilizations:
                    war_status = " ⚔️" if civ.at_war else ""
                    leader_info = f" ({civ.leader.full_title})"
                    print(f"  {civ.name}{leader_info}: Pop {civ.population}, Tech {civ.technology:.2f}, "
                          f"😊{civ.happiness:.0f}, Military {civ.military_power:.0f}{war_status}")
                
                # Show leadership changes
                if year_report["leadership_events"]:
                    print("LEADERSHIP CHANGES:")
                    for event in year_report["leadership_events"][-2:]:
                        print(f"  {event}")
                
                if year_report["war_events"]:
                    print("RECENT WARS:")
                    for event in year_report["war_events"][-3:]:
                        print(f"  {event}")
        
        print(f"\n✅ Simulation complete! Final state:")
        self.display_world()

"""
====================== MAIN GAME LOOP ======================
"""

def main():
    print("=== CIVILIZATION OBSERVER - LEADER SYSTEM ===")
    print("Witness dynastic histories and personality-driven decisions!")
    
    game = CivilizationObserver()
    
    if len(os.sys.argv) > 1:
        if os.sys.argv[1] == "--load" and len(os.sys.argv) > 2:
            game.load_game(os.sys.argv[2])
        elif os.sys.argv[1] == "--auto":
            seed = None
            if len(os.sys.argv) > 2:
                try: seed = int(os.sys.argv[2])
                except ValueError: pass
            years = 50
            if len(os.sys.argv) > 3:
                try: years = int(os.sys.argv[3])
                except ValueError: pass
                    
            game.generate_world(seed)
            game.run_automated_simulation(years)
            return
        elif os.sys.argv[1] == "--help":
            print("\nUsage:")
            print("  python main.py                    # Interactive mode")
            print("  python main.py --auto [seed] [years] # Automated simulation")
            print("  python main.py --load <file>      # Load saved game")
            print("  python main.py --help             # Show this help")
            return
    else:
        print("\nOptions:")
        print("  1. Create new world")
        print("  2. Load saved game")
        
        choice = input("Choose (1 or 2): ").strip()
        
        if choice == "2":
            save_file = input("Enter save file name: ").strip()
            if save_file:
                game.load_game(save_file)
            else:
                print("No file specified. Creating new world.")
                seed_input = input("Enter a seed number (or leave blank for random): ").strip()
                seed = int(seed_input) if seed_input else None
                game.generate_world(seed)
        else:
            seed_input = input("Enter a seed number (or leave blank for random): ").strip()
            seed = int(seed_input) if seed_input else None
            game.generate_world(seed)
    
    try:
        input("\nPress Enter to begin simulation...")
        interactive = True
    except EOFError:
        print("\n⏩ Non-interactive environment detected. Running automated simulation...")
        interactive = False
        game.run_automated_simulation(20)
        return
    
    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            
            game.display_world()
            year_report = game.advance_year()
            
            # Display events with leadership events first
            if year_report["leadership_events"]:
                print("\n👑 LEADERSHIP EVENTS:")
                for event in year_report["leadership_events"]:
                    print(f"- {event}")
            
            if year_report["war_events"]:
                print("\n⚔️ WAR EVENTS:")
                for event in year_report["war_events"]:
                    print(f"- {event}")
            
            if year_report["major_events"]:
                print("\n🚨 MAJOR WORLD EVENTS:")
                for event in year_report["major_events"]:
                    print(f"- {event}")
            
            if year_report["diplomatic_events"]:
                print("\n🤝 DIPLOMATIC EVENTS:")
                for event in year_report["diplomatic_events"]:
                    print(f"- {event}")
            
            if year_report["economic_events"]:
                print("\n💰 ECONOMIC & SOCIETAL EVENTS:")
                for event in year_report["economic_events"]:
                    print(f"- {event}")
            
            cmd = input("\nPress Enter to continue, 's' to save, 'l' to load, 'm' for master control, or 'q' to quit: ").lower()
            if cmd == 'q':
                break
            elif cmd == 's':
                save_file = input("Enter save file name: ").strip()
                if save_file:
                    game.save_game(save_file)
                    input("Game saved. Press Enter to continue...")
            elif cmd == 'l':
                save_file = input("Enter save file name to load: ").strip()
                if save_file:
                    game.load_game(save_file)
                    input("Game loaded. Press Enter to continue...")
            elif cmd == 'm' and game.master_control.master_control_enabled:
                print("\n🎮 MASTER CONTROL:")
                print("  1. Skip 10 years")
                print("  2. Skip 50 years") 
                print("  3. Show summary")
                print("  4. Toggle pause")
                print("  5. Back to normal")
                
                mc_cmd = input("Choose option: ").strip()
                if mc_cmd == "1":
                    game.master_control.skip_years(10)
                    input("Press Enter to continue...")
                elif mc_cmd == "2":
                    game.master_control.skip_years(50)
                    input("Press Enter to continue...")
                elif mc_cmd == "3":
                    game.master_control.show_summary()
                    input("Press Enter to continue...")
                elif mc_cmd == "4":
                    game.master_control.toggle_pause()
                    input("Press Enter to continue...")
    
    except KeyboardInterrupt:
        print("\nSimulation ended by user.")
    except EOFError:
        print("\n⏹️ Input ended. Simulation stopped.")

if __name__ == "__main__":
    main()