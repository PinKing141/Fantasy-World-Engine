import random
import time
from datetime import datetime
import os
import math
import json
from collections import defaultdict

"""
========================================================================
 FANTASY ENGINE - PRE-ALPHA 11: INDIVIDUALS & HEROES
========================================================================
This version introduces the "micro" layer:
- Individuals (Person class) with traits, stats, professions, and families.
- Dynasties (Dynasty class) to track lineage and prestige.
- The Leader class is replaced by a Person object, enabling true succession.
- Professions provide active bonuses to the civilization.
- A fame system tracks "heroes" who emerge from the population.
- All systems are integrated with the HistoryArchive and LegendsMode.
========================================================================
"""

# --- NAME GENERATION (HELPER) ---
MALE_NAMES = ["Alaric", "Borin", "Cedric", "Darian", "Eldrin", "Faron", "Gareth", "Hakon", 
              "Ivor", "Jarek", "Kael", "Lorik", "Marek", "Nolan", "Orin", "Pavel", "Quinn",
              "Rurik", "Soren", "Torval", "Uther", "Varek", "Willem", "Xander", "Yorin", "Zane"]
FEMALE_NAMES = ["Althea", "Brienne", "Cyrene", "Diana", "Elara", "Freyja", "Gwen", "Helena",
                "Ilyana", "Jocelyn", "Kara", "Lyra", "Morgan", "Nyssa", "Orla", "Piper",
                "Quinn", "Rhian", "Sylvia", "Talia", "Ursa", "Valeria", "Willow", "Xandra",
                "Yara", "Zara"]
DYNASTY_PREFIXES = ["Val", "Cor", "Ston", "Iron", "Silv", "Win", "Ara", "Cas", "Mor", "Hel"]
DYNASTY_SUFFIXES = ["us", "ian", "ar", "en", "ett", "wood", "crest", "fall", "hart", "wind"]
TRAITS = ["Brave", "Cowardly", "Kind", "Cruel", "Ambitious", "Content", "Honest", "Deceitful",
          "Pious", "Cynical", "Genius", "Dull", "Paranoid", "Trusting", "Greedy", "Generous",
          "Lustful", "Chaste"]


"""
====================== 1. DEEP HISTORY & LEGENDS SYSTEM ======================
(Upgraded with Individual event types)
"""

class HistoryEvent:
    """Represents a structured historical event with metadata"""
    
    EVENT_TYPES = {
        # Civilization Events
        "foundation": "Civilization Founded",
        "leader_death": "Leader Death",
        "leader_succession": "Leadership Change", 
        "war_declaration": "War Declaration",
        "war_victory": "War Victory",
        "war_defeat": "War Defeat",
        "famine": "Famine",
        "golden_age": "Golden Age",
        "civil_war": "Civil War",
        "rebellion": "Rebellion",
        "economic_boom": "Economic Boom",
        "economic_crisis": "Economic Crisis",
        "economic_collapse": "Economic Collapse",
        "population_boom": "Population Growth",
        "population_collapse": "Population Decline",
        "technology_breakthrough": "Technology Advance",
        "tech_advance": "Technological Advancement",
        "natural_disaster": "Natural Disaster",
        
        # Diplomatic Events
        "diplomatic_alliance": "Alliance Formed",
        "alliance_formed": "Diplomatic Alliance",
        "diplomatic_trade": "Trade Pact",
        "diplomatic_peace": "Peace Treaty",
        "relations_improved": "Improved Relations",
        "relations_worsened": "Worsened Relations",
        "battle": "Military Battle",

        # Culture & Religion Events
        "cultural_boom": "Cultural Renaissance",
        "cultural_renaissance": "Cultural Flourishing",
        "cultural_artifact": "Artistic Creation",
        "festival": "Cultural Festival",
        "religion_founded": "New Religion Founded",
        "religious_conversion": "Religious Change",
        "religious_schism": "Religious Split", 
        "religious_reformation": "Religious Reform",
        "pilgrimage": "Religious Journey",
        "holy_war_declaration": "Holy War Declared",

        # Individual & Dynasty Events (NEW IN PA-11)
        "birth": "Birth",
        "death": "Death",
        "marriage": "Marriage",
        "succession": "Succession",
        "hero_achievement": "Heroic Act",
        "dynasty_founded": "Dynasty Founded",
        "dynasty_ended": "End of a Dynasty",
        "usurpation": "Usurpation",
        
        # Other
        "annual_summary": "Yearly Summary"
    }
    
    def __init__(self, year, event_type, civilization, details, 
                 person_id=None, other_civ=None, severity="normal", caused_by=None):
        self.year = year
        self.event_type = event_type
        self.civilization = civilization # Name of the civ
        self.details = details
        self.person_id = person_id # ID of the Person involved
        self.other_civilization = other_civ
        self.severity = severity  # minor, normal, major, catastrophic
        self.caused_by = caused_by  # Reference to previous event that caused this
        self.id = f"{year}_{civilization}_{event_type}_{random.randint(1000,9999)}"
    
    def to_dict(self):
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'year': self.year,
            'event_type': self.event_type,
            'civilization': self.civilization,
            'details': self.details,
            'person_id': self.person_id,
            'other_civilization': self.other_civilization,
            'severity': self.severity,
            'caused_by': self.caused_by
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create from saved dictionary"""
        event = cls(
            year=data['year'],
            event_type=data['event_type'],
            civilization=data['civilization'],
            details=data['details'],
            person_id=data.get('person_id'),
            other_civ=data.get('other_civilization'),
            severity=data.get('severity', 'normal'),
            caused_by=data.get('caused_by')
        )
        event.id = data.get('id', f"{data['year']}_{data['civilization']}_{data['event_type']}_{random.randint(1000,9999)}")
        return event
    
    def __str__(self):
        return f"Year {self.year}: {self.EVENT_TYPES.get(self.event_type, self.event_type)} - {self.details}"

class HistoryArchive:
    """Manages structured historical records and provides querying capabilities"""
    
    def __init__(self):
        self.global_history = []  # All events across all civilizations
        self.event_index = {}     # Fast lookup by event type and civilization
        self.cause_effect_chains = []  # Linked event sequences
        self.last_major_events = {}    # Track recent major events for cause-effect
        
    def record_event(self, event):
        """Record a new historical event"""
        self.global_history.append(event)
        
        # Update indexes
        if event.event_type not in self.event_index:
            self.event_index[event.event_type] = []
        self.event_index[event.event_type].append(event)
        
        # Store for potential cause-effect linking
        if event.severity in ["major", "catastrophic"]:
            self.last_major_events[event.civilization] = event
            
        # Auto-link obvious cause-effect relationships
        self._auto_link_cause_effect(event)
    
    def _auto_link_cause_effect(self, new_event):
        """Automatically link events that are likely cause-effect pairs"""
        
        if new_event.event_type in ["war_declaration", "rebellion", "civil_war"]:
            last_famine = self.get_recent_events(
                civilization=new_event.civilization,
                event_type="famine",
                years_back=10,
                current_year=new_event.year
            )
            if last_famine:
                new_event.caused_by = last_famine[0].id
                self.cause_effect_chains.append((last_famine[0].id, new_event.id))
        
        elif new_event.event_type == "golden_age":
            recent_wars = self.get_recent_events(
                civilization=new_event.civilization,
                event_type="war_victory", 
                years_back=20,
                current_year=new_event.year
            )
            if recent_wars:
                new_event.caused_by = recent_wars[0].id
                self.cause_effect_chains.append((recent_wars[0].id, new_event.id))
        
        elif new_event.event_type == "succession":
            # Check if this was caused by a 'death' event
            last_death = self.get_recent_events(
                civilization=new_event.civilization,
                event_type="death",
                years_back=1,
                current_year=new_event.year
            )
            if last_death and last_death[0].person_id == new_event.caused_by:
                new_event.caused_by = last_death[0].id
                self.cause_effect_chains.append((last_death[0].id, new_event.id))
    
    def _archive_old_events(self):
        if len(self.global_history) > 10000:
            self.global_history = self.global_history[-10000:]
            self._rebuild_index()
    
    def _rebuild_index(self):
        self.event_index = {}
        for event in self.global_history:
            if event.event_type not in self.event_index:
                self.event_index[event.event_type] = []
            self.event_index[event.event_type].append(event)
    
    def get_events(self, civilization=None, event_type=None, start_year=None, 
                  end_year=None, person_id=None, severity=None):
        """Query events with multiple filters"""
        results = []
        
        for event in self.global_history:
            if civilization and event.civilization != civilization:
                continue
            if event_type and event.event_type != event_type:
                continue
            if start_year and event.year < start_year:
                continue
            if end_year and event.year > end_year:
                continue
            if person_id and event.person_id != person_id:
                continue
            if severity and event.severity != severity:
                continue
                
            results.append(event)
        
        return sorted(results, key=lambda x: x.year)
    
    def get_recent_events(self, civilization=None, event_type=None, years_back=10, current_year=None):
        if not current_year:
            if self.global_history:
                current_year = self.global_history[-1].year
            else:
                return []
                
        return self.get_events(
            civilization=civilization,
            event_type=event_type,
            start_year=current_year - years_back,
            end_year=current_year
        )
    
    def get_event_chain(self, start_event_id):
        chain = []
        current_id = start_event_id
        
        start_event = next((e for e in self.global_history if e.id == start_event_id), None)
        if not start_event:
            return chain
            
        chain.append(start_event)
        
        while current_id:
            next_event = next((e for e in self.global_history if e.caused_by == current_id), None)
            if next_event:
                chain.append(next_event)
                current_id = next_event.id
            else:
                current_id = None
                
        return chain
    
    def get_civilization_timeline(self, civilization, start_year=None, end_year=None):
        return self.get_events(civilization=civilization, start_year=start_year, end_year=end_year)
    
    def get_person_timeline(self, person_id):
        """Get all events related to a specific person"""
        return self.get_events(person_id=person_id)
    
    def get_world_era_summary(self, start_year, end_year):
        era_events = self.get_events(start_year=start_year, end_year=end_year)
        
        if not era_events:
            return f"Years {start_year}-{end_year}: The Silent Age - No significant events recorded."
        
        event_counts = defaultdict(int)
        for event in era_events:
            event_counts[event.event_type] += 1
        
        major_events = [e for e in era_events if e.severity in ["major", "catastrophic"]]
        
        summary_parts = [f"Years {start_year}-{end_year}:"]
        
        if event_counts["war_declaration"] > 0:
            summary_parts.append(f"{event_counts['war_declaration']} wars")
        if event_counts["golden_age"] > 0:
            summary_parts.append(f"{event_counts['golden_age']} golden ages")
        if event_counts["famine"] > 0:
            summary_parts.append(f"{event_counts['famine']} famines")
        if event_counts["dynasty_founded"] > 0:
            summary_parts.append(f"{event_counts['dynasty_founded']} new dynasties")
        
        if major_events:
            most_significant = max(major_events, key=lambda x: 1 if x.severity == "catastrophic" else 0)
            summary_parts.append(f"Notably: {most_significant.details}")
        
        return " ".join(summary_parts)
    
    def to_dict(self):
        return {
            'global_history': [event.to_dict() for event in self.global_history],
            'cause_effect_chains': self.cause_effect_chains
        }
    
    @classmethod
    def from_dict(cls, data):
        archive = cls()
        archive.global_history = [HistoryEvent.from_dict(event_data) for event_data in data['global_history']]
        archive.cause_effect_chains = data.get('cause_effect_chains', [])
        archive._rebuild_index()
        return archive

class LegendsMode:
    """Provides natural language storytelling and historical narratives"""
    
    def __init__(self, history_archive, world_ref):
        self.archive = history_archive
        self.world = world_ref # Need world to look up person names from IDs
        self.story_templates = self._initialize_story_templates()
    
    def _get_person_name(self, person_id):
        """Helper to get a person's full name from their ID"""
        if not person_id:
            return "an unknown figure"
        person = self.world.get_person_by_id(person_id)
        if person:
            return person.full_name
        return "a figure lost to history"

    def _initialize_story_templates(self):
        """Initialize natural language templates for different event types"""
        return {
            "leader_death": [
                "In Year {year}, {leader_name} of {civ} passed away {details}.",
                "The reign of {leader_name} over {civ} ended in Year {year} {details}.",
                "{civ} mourned the loss of {leader_name} in Year {year} {details}."
            ],
            "death": [
                "In Year {year}, {person_name} of {civ} {details}.",
                "The year {year} saw the passing of {person_name}, {details}.",
            ],
            "birth": [
                "A child named {person_name} was born in {civ} in Year {year}, {details}.",
                "Year {year} marked the birth of {person_name} in {civ}, {details}.",
            ],
            "succession": [
                "Power in {civ} transferred to {person_name} in Year {year}, {details}.",
                "Year {year}: {person_name} took the throne of {civ}, {details}.",
            ],
            "war_declaration": [
                "War erupted in Year {year} when {civ} declared war on {other_civ}.",
                "The {year} conflict began as {civ} launched attacks against {other_civ}.",
            ],
            "war_victory": [
                "In a decisive victory in Year {year}, {civ} triumphed over {other_civ}, {details}.",
                "{civ} achieved military glory in Year {year} by defeating {other_civ}, {details}.",
            ],
            "famine": [
                "A great famine struck {civ} in Year {year}, {details}",
            ],
            "golden_age": [
                "{civ} entered a glorious golden age in Year {year}, {details}",
            ],
            "cultural_renaissance": [
                "{civ} experienced a cultural renaissance in Year {year}, {details}",
            ],
            "religion_founded": [
                "Year {year} saw the founding of {details} in {civ}.",
            ],
            "religious_schism": [
                "A great schism in Year {year} saw {civ} {details}.",
            ],
            "hero_achievement": [
                "In Year {year}, {person_name} of {civ} became a legend by {details}.",
                "The populace celebrated {person_name} in Year {year} after they {details}.",
            ]
        }
    
    def generate_story_view(self, civilization=None, start_year=None, end_year=None, 
                          event_types=None, max_events=50):
        """Generate natural language historical narrative"""
        events = self.archive.get_events(
            civilization=civilization,
            start_year=start_year,
            end_year=end_year
        )
        
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        
        events = events[-max_events:] if len(events) > max_events else events
        
        if not events:
            return "No significant events recorded in this period."
        
        story = []
        current_era = None
        
        for event in events:
            if current_era is None or event.year - current_era > 50:
                if current_era is not None:
                    story.append(f"\n--- The following years saw relative quiet ---\n")
                current_era = event.year
            
            event_story = self._event_to_story(event)
            story.append(event_story)
        
        return "\n".join(story)
    
    def _event_to_story(self, event):
        """Convert a single event to natural language"""
        template_group = self.story_templates.get(event.event_type)
        if not template_group:
            return f"Year {event.year}: {event.details}"
        
        template = random.choice(template_group)
        
        # Get names from IDs
        person_name = self._get_person_name(event.person_id)
        
        story = template.format(
            year=event.year,
            civ=event.civilization,
            person_name=person_name,
            leader_name=person_name, # Often the person_id is the leader
            other_civ=event.other_civilization or "their neighbors",
            details=event.details.lower()
        )
        
        if event.caused_by:
            cause_event = next((e for e in self.archive.global_history if e.id == event.caused_by), None)
            if cause_event:
                cause_story = self._event_to_story(cause_event).split(': ')[-1]
                story += f" This was sparked by {cause_story.lower()}"
        
        return story
    
    def generate_civilization_biography(self, civilization, current_year):
        """Generate a comprehensive biography of a civilization"""
        all_events = self.archive.get_civilization_timeline(civilization)
        civ_obj = self.world.get_civ_by_name(civilization)
        
        if not all_events or not civ_obj:
            return f"Little is known about the history of {civilization}."
        
        founding = next((e for e in all_events if e.event_type == "foundation"), None)
        golden_ages = self.archive.get_events(civilization=civilization, event_type="golden_age")
        major_wars = [e for e in all_events if e.event_type in ["war_declaration", "war_victory", "war_defeat", "holy_war_declaration"]]
        
        # Get dynasties and leaders from the civ object
        dynasties = civ_obj.dynasties
        leader_history = [self.world.get_person_by_id(p.id) for p in civ_obj.leader_history]
        
        biography = [f"# The Chronicle of {civilization}\n"]
        
        if founding:
            biography.append(f"{civilization} was founded in Year {founding.year}. {founding.details}\n")
        else:
            biography.append(f"The origins of {civilization} are lost to time, but their history is recorded from Year {all_events[0].year}.\n")
        
        biography.append(f"## Ruling Dynasties")
        if dynasties:
            biography.append(f"The civilization has been shaped by {len(dynasties)} major dynasties.")
            for dynasty in dynasties:
                biography.append(f"- **{dynasty.name}** (Prestige: {dynasty.prestige})")
        
        biography.append(f"\n## Line of Rulers")
        for leader in leader_history[-5:]: # Last 5 rulers
             if leader:
                biography.append(f"- {leader.full_name} (Ruled from {leader.reign_start_year})")
        
        if golden_ages:
            biography.append(f"\n## Ages of Glory")
            for age in golden_ages[-3:]:
                biography.append(f"- {self._event_to_story(age)}")
        
        if major_wars:
            biography.append(f"\n## Trials of War")
            for war in major_wars[-5:]:
                biography.append(f"- {self._event_to_story(war)}")
        
        recent_events = self.archive.get_recent_events(civilization=civilization, years_back=20, current_year=current_year)
        if recent_events:
            biography.append(f"\n## Recent Times")
            for event in recent_events[-5:]:
                biography.append(f"- {self._event_to_story(event)}")
        
        return "\n".join(biography)
    
    def generate_world_chronicle(self, start_year, end_year, highlight_major=True):
        """Generate a world history for the specified period"""
        era_events = self.archive.get_events(start_year=start_year, end_year=end_year)
        
        if not era_events:
            return f"The years {start_year} to {end_year} were remarkably quiet across the known world."
        
        if highlight_major:
            era_events = [e for e in era_events if e.severity in ["major", "catastrophic"]]
        
        civ_events = defaultdict(list)
        for event in era_events:
            civ_events[event.civilization].append(event)
        
        chronicle = [f"# World Chronicle: Years {start_year}-{end_year}\n"]
        
        for civ, events in civ_events.items():
            chronicle.append(f"## {civ}")
            for event in events:
                chronicle.append(f"- {self._event_to_story(event)}")
            chronicle.append("")
        
        return "\n".join(chronicle)
    
    def generate_person_biography(self, person_id):
        """Generate a biography for a single individual"""
        person = self.world.get_person_by_id(person_id)
        if not person:
            return f"The person with ID {person_id} is unknown."
        
        events = self.archive.get_person_timeline(person_id)
        
        bio = [f"# The Life of {person.full_name}\n"]
        bio.append(f"**Born:** Year {person.birth_year} in {person.civ_name}")
        if not person.alive:
            bio.append(f"**Died:** Year {person.death_year} (Age {person.age})")
        else:
            bio.append(f"**Age:** {person.age}")
        
        bio.append(f"**Dynasty:** {person.dynasty.name if person.dynasty else 'Commoner'}")
        bio.append(f"**Profession:** {person.profession}")
        bio.append(f"**Traits:** {', '.join(person.traits)}")
        bio.append(f"**Fame:** {person.fame} {'(Hero)' if person.is_hero else ''}")
        
        bio.append("\n## Key Life Events:")
        if not events:
            bio.append("- No significant events recorded.")
        for event in events:
            bio.append(f"- {self._event_to_story(event)}")
            
        return "\n".join(bio)

"""
====================== 2. INDIVIDUALS & DYNASTIES (NEW PA-11) ======================
"""

class Dynasty:
    """Represents a noble family or dynasty"""
    def __init__(self, name, founder):
        self.name = name
        self.founder_id = founder.id
        self.members = [founder.id]
        self.prestige = 10 # Starting prestige
    
    def add_member(self, person):
        if person.id not in self.members:
            self.members.append(person.id)
            person.dynasty = self
            person.surname = self.name
    
    def add_prestige(self, amount):
        self.prestige += amount
    
    def to_dict(self):
        return {
            'name': self.name,
            'founder_id': self.founder_id,
            'members': self.members,
            'prestige': self.prestige
        }
    
    @classmethod
    def from_dict(cls, data, world):
        # Founder will be linked later
        founder = world.get_person_by_id(data['founder_id'])
        dynasty = cls(data['name'], founder)
        dynasty.members = data['members']
        dynasty.prestige = data['prestige']
        return dynasty

class Person:
    """Represents an individual in the world (replaces Leader class)"""
    
    PROFESSIONS = ["Ruler", "General", "Scholar", "Diplomat", "Treasurer", "Priest", "Noble", "Commoner"]
    
    def __init__(self, civ_name, birth_year, gender=None, dynasty=None):
        self.id = f"p_{birth_year}_{random.randint(1000, 9999)}"
        self.alive = True
        self.civ_name = civ_name
        
        # Identity
        self.gender = gender if gender else random.choice(["Male", "Female"])
        self.name = random.choice(MALE_NAMES) if self.gender == "Male" else random.choice(FEMALE_NAMES)
        self.surname = "the Commoner"
        self.dynasty = None
        if dynasty:
            dynasty.add_member(self)
        
        self.full_name = f"{self.name} {self.surname}"
        
        # Lifecycle
        self.birth_year = birth_year
        self.age = 0
        self.lifespan = random.randint(50, 85)
        self.death_year = -1
        
        # Family
        self.mother_id = None
        self.father_id = None
        self.spouse_id = None
        self.children_ids = []
        
        # Role
        self.profession = "Commoner"
        self.traits = random.sample(TRAITS, random.randint(2, 4))
        self.stats = self._generate_stats()
        self.loyalty = random.randint(30, 70) # Loyalty to the current ruler
        self.fame = 0
        self.is_hero = False
        
        # For rulers
        self.reign_start_year = -1
        self.major_achievements = []

    def _generate_stats(self):
        """Generate base stats, modified by traits"""
        stats = {
            "combat": random.randint(1, 10),
            "diplomacy": random.randint(1, 10),
            "stewardship": random.randint(1, 10),
            "intrigue": random.randint(1, 10),
            "learning": random.randint(1, 10),
            "piety": random.randint(1, 10)
        }
        
        # Apply trait modifiers
        if "Brave" in self.traits: stats["combat"] += 3
        if "Cowardly" in self.traits: stats["combat"] -= 3
        if "Genius" in self.traits:
            stats["learning"] += 4
            stats["stewardship"] += 2
        if "Dull" in self.traits: stats["learning"] -= 4
        if "Kind" in self.traits: stats["diplomacy"] += 3
        if "Cruel" in self.traits: stats["intrigue"] += 3
        if "Honest" in self.traits: stats["diplomacy"] += 2
        if "Deceitful" in self.traits: stats["intrigue"] += 4
        if "Pious" in self.traits: stats["piety"] += 5
        if "Cynical" in self.traits: stats["piety"] -= 4
        if "Ambitious" in self.traits: stats["intrigue"] += 2
        
        # Clamp stats
        for stat, value in stats.items():
            stats[stat] = max(0, min(20, value)) # 0-20 scale
        return stats

    def update_year(self, world):
        """Update the person's state for one year"""
        if not self.alive:
            return
        
        self.age += 1
        
        # --- Check for Death ---
        death_chance = 0.0
        if self.age > self.lifespan:
            death_chance = 1.0 # Guaranteed death
        elif self.age > 60:
            death_chance = (self.age - 60) / 30.0 # Increasingly likely
        elif self.age > 40 and random.random() < 0.02:
            death_chance = 0.02 # Chance of early death
        
        if random.random() < death_chance:
            self.die(world, "natural causes")
            return

        # --- Adulthood & Profession ---
        if self.age == 16:
            if self.dynasty: # Nobles get professions
                self.profession = random.choice(["General", "Diplomat", "Treasurer", "Priest", "Scholar", "Noble"])
            # Commoners stay commoners unless they become heroes
        
        # --- Marriage & Children (for nobles/rulers) ---
        if self.age > 18 and not self.spouse_id and self.dynasty and random.random() < 0.1:
            self._find_spouse(world)
            
        if self.age > 20 and self.age < 45 and self.spouse_id and self.gender == "Female" and random.random() < 0.15:
            self._have_child(world)
    
    def die(self, world, reason):
        """Mark the person as dead and log the event"""
        self.alive = False
        self.death_year = world.year
        
        details = f"died at age {self.age} of {reason}"
        if self.is_hero:
            details = f"the hero, died at age {self.age} of {reason}"
        
        world.history_archive.record_event(HistoryEvent(
            year=world.year,
            event_type="death",
            civilization=self.civ_name,
            details=details,
            person_id=self.id,
            severity="major" if self.fame > 50 or self.profession == "Ruler" else "normal"
        ))
        
        # If they were part of a dynasty, check if they were the last member
        if self.dynasty:
            living_members = [m for m in self.dynasty.members if world.get_person_by_id(m).alive]
            if not living_members:
                world.history_archive.record_event(HistoryEvent(
                    year=world.year,
                    event_type="dynasty_ended",
                    civilization=self.civ_name,
                    details=f"The {self.dynasty.name} dynasty has died out",
                    person_id=self.id,
                    severity="major"
                ))
    
    def _find_spouse(self, world):
        """Find a suitable spouse from the noble population"""
        civ = world.get_civ_by_name(self.civ_name)
        candidates = []
        for person in civ.individuals:
            if (person.alive and person.dynasty and not person.spouse_id and
                person.age > 18 and person.age < 50 and person.gender != self.gender):
                candidates.append(person)
        
        if candidates:
            spouse = random.choice(candidates)
            self.spouse_id = spouse.id
            spouse.spouse_id = self.id
            
            world.history_archive.record_event(HistoryEvent(
                year=world.year,
                event_type="marriage",
                civilization=self.civ_name,
                details=f"{self.full_name} married {spouse.full_name}",
                person_id=self.id,
                severity="normal"
            ))
            
    def _have_child(self, world):
        """Create a new child Person"""
        civ = world.get_civ_by_name(self.civ_name)
        child = Person(self.civ_name, world.year, dynasty=self.dynasty)
        child.mother_id = self.id
        child.father_id = self.spouse_id
        
        # Add to world and civ lists
        world.all_people[child.id] = child
        civ.individuals.append(child)
        
        # Add to parent's child list
        self.children_ids.append(child.id)
        spouse = world.get_person_by_id(self.spouse_id)
        if spouse:
            spouse.children_ids.append(child.id)
            
        world.history_archive.record_event(HistoryEvent(
            year=world.year,
            event_type="birth",
            civilization=self.civ_name,
            details=f"a child named {child.name} was born to {self.full_name} and {spouse.full_name}",
            person_id=child.id,
            severity="normal"
        ))

    def get_profession_modifiers(self):
        """Get bonuses based on profession and stats (scaled 0-10)"""
        mods = defaultdict(float)
        stat_val = 0.0
        
        if self.profession == "Ruler":
            # Ruler gives broad, small bonuses
            mods["diplomacy_bonus"] += self.stats["diplomacy"] * 0.01
            mods["tech_bonus"] += self.stats["learning"] * 0.01
            mods["trade_bonus"] += self.stats["stewardship"] * 0.01
            mods["stability_bonus"] += (self.stats["diplomacy"] + self.stats["intrigue"]) * 0.005
        elif self.profession == "General":
            mods["war_power_bonus"] = self.stats["combat"] * 0.05 # 5% per combat point
        elif self.profession == "Diplomat":
            mods["diplomacy_bonus"] = self.stats["diplomacy"] * 0.05
        elif self.profession == "Treasurer":
            mods["trade_bonus"] = self.stats["stewardship"] * 0.05
        elif self.profession == "Scholar":
            mods["tech_bonus"] = self.stats["learning"] * 0.05
        elif self.profession == "Priest":
            mods["religion_spread_bonus"] = self.stats["piety"] * 0.05
            mods["stability_bonus"] = self.stats["piety"] * 0.01
        
        return mods

    def add_fame(self, amount, world, reason):
        """Add fame to a person and check if they become a hero"""
        self.fame += amount
        if not self.is_hero and self.fame > 50:
            self.is_hero = True
            world.history_archive.record_event(HistoryEvent(
                year=world.year,
                event_type="hero_achievement",
                civilization=self.civ_name,
                details=f"became a hero known for {reason}",
                person_id=self.id,
                severity="major"
            ))
            
    def add_achievement(self, achievement):
        self.major_achievements.append(achievement)
    
    def to_dict(self):
        return {
            'id': self.id,
            'alive': self.alive,
            'civ_name': self.civ_name,
            'gender': self.gender,
            'name': self.name,
            'surname': self.surname,
            'dynasty_name': self.dynasty.name if self.dynasty else None,
            'birth_year': self.birth_year,
            'age': self.age,
            'lifespan': self.lifespan,
            'death_year': self.death_year,
            'mother_id': self.mother_id,
            'father_id': self.father_id,
            'spouse_id': self.spouse_id,
            'children_ids': self.children_ids,
            'profession': self.profession,
            'traits': self.traits,
            'stats': self.stats,
            'loyalty': self.loyalty,
            'fame': self.fame,
            'is_hero': self.is_hero,
            'reign_start_year': self.reign_start_year,
            'major_achievements': self.major_achievements
        }

    @classmethod
    def from_dict(cls, data, world):
        """Create person from saved data"""
        # Create a dummy person first
        person = cls(data['civ_name'], data['birth_year'])
        
        # Overwrite all data
        person.id = data['id']
        person.alive = data['alive']
        person.gender = data['gender']
        person.name = data['name']
        person.surname = data['surname']
        person.dynasty_name_to_load = data.get('dynasty_name') # Will be linked by World
        person.birth_year = data['birth_year']
        person.age = data['age']
        person.lifespan = data['lifespan']
        person.death_year = data['death_year']
        person.mother_id = data.get('mother_id')
        person.father_id = data.get('father_id')
        person.spouse_id = data.get('spouse_id')
        person.children_ids = data.get('children_ids', [])
        person.profession = data['profession']
        person.traits = data['traits']
        person.stats = data['stats']
        person.loyalty = data['loyalty']
        person.fame = data['fame']
        person.is_hero = data['is_hero']
        person.reign_start_year = data.get('reign_start_year', -1)
        person.major_achievements = data.get('major_achievements', [])
        person.full_name = f"{person.name} {person.surname}"
        
        return person

"""
====================== 3. MAP & CLIMATE SYSTEMS ======================
(Unchanged from PA-10 merge)
"""

class WorldMap:
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
    
    def get_terrain_at(self, position):
        x, y = int(position[0]), int(position[1])
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.terrain_types.get(self.grid[y][x], "Unknown")
        return "Void"

    def get_terrain_bonus(self, position):
        x, y = int(position[0]), int(position[1])
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
        x, y = self.rng.randint(0, self.width-1), self.rng.randint(0, self.height-1)
        self.civilization_locations[civ.name] = (x, y)
        civ.map_position = (x, y)
        return False


    def display(self, civilizations):
        print("\nWorld Map:")
        civ_coords = {}
        for civ in civilizations:
            civ_coords[(int(civ.map_position[0]), int(civ.map_position[1]))] = civ.name[0].upper()
            
        for y in range(self.height):
            row = []
            for x in range(self.width):
                if (x,y) in civ_coords:
                    row.append(civ_coords[(x,y)])
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

"""
====================== 4. CULTURE & RELIGION SYSTEMS ======================
(Unchanged from PA-10 merge, but now integrated with Persons)
"""

class CultureSystem:
    CULTURAL_TRAITS = {
        "tradition": "Resistance to change vs innovation",
        "collectivism": "Community focus vs individualism", 
        "honor": "Loyalty and principles vs pragmatism",
        "artistry": "Creative and aesthetic achievement",
        "spirituality": "Importance of faith and belief",
        "cohesion": "Cultural unity and shared identity",
        "industriousness": "Work ethic and productivity",
        "militarism": "Value placed on military strength",
        "diplomacy": "Preference for peaceful resolution"
    }
    
    def __init__(self, civilization, terrain_type=None):
        self.civilization = civilization
        self.traits = self._generate_initial_traits(terrain_type)
        self.artifacts = []
        self.cultural_achievements = []
        self.influences = {}
        
    def _generate_initial_traits(self, terrain_type):
        traits = {}
        for trait in self.CULTURAL_TRAITS:
            traits[trait] = random.uniform(0.3, 0.7)
        
        if terrain_type:
            if terrain_type in ["Mountains", "Hills"]:
                traits["tradition"] += 0.2
                traits["honor"] += 0.15
                traits["spirituality"] += 0.1
            elif terrain_type in ["Rivers", "Plains"]:
                traits["collectivism"] += 0.2
                traits["industriousness"] += 0.15
            elif terrain_type == "Forests":
                traits["spirituality"] += 0.25
                traits["artistry"] += 0.1
        
        leader = self.civilization.leader # Leader is now a Person
        traits["militarism"] += (leader.stats["combat"] - 5) / 10.0 # Use stats
        traits["diplomacy"] += (leader.stats["diplomacy"] - 5) / 10.0
        traits["artistry"] += (leader.stats["learning"] - 5) / 20.0
        
        for trait in traits:
            traits[trait] = max(0.1, min(0.9, traits[trait]))
            
        traits["artistry"] = int(traits["artistry"] * 100)
        traits["spirituality"] = int(traits["spirituality"] * 100)
        traits["cohesion"] = int(traits["cohesion"] * 100)
        
        return traits
    
    def update_yearly(self):
        for trait in self.traits:
            if isinstance(self.traits[trait], (int, float)) and trait not in ["artistry", "spirituality", "cohesion"]:
                drift = random.uniform(-0.02, 0.02)
                self.traits[trait] = max(0.1, min(0.9, self.traits[trait] + drift))
        
        self._apply_event_influences()
        
        stability_effect = (self.civilization.stability - 50) / 200.0
        happiness_effect = (self.civilization.happiness - 50) / 200.0
        self.traits["cohesion"] = max(10, min(100, 
            self.traits["cohesion"] + stability_effect + happiness_effect))
    
    def _apply_event_influences(self):
        recent_events = self.civilization.get_recent_history(years=5)
        
        for event in recent_events:
            if event.event_type == "war_victory":
                self.traits["militarism"] = min(0.9, self.traits["militarism"] + 0.05)
            elif event.event_type == "war_defeat":
                self.traits["militarism"] = max(0.1, self.traits["militarism"] - 0.05)
            elif event.event_type == "golden_age":
                self.traits["artistry"] = min(100, self.traits["artistry"] + 10)
            elif event.event_type == "famine":
                self.traits["cohesion"] = max(10, self.traits["cohesion"] - 20)
    
    def get_economic_modifiers(self):
        return {
            "production_bonus": (self.traits["industriousness"] - 0.5) * 0.2,
            "trade_bonus": (self.traits["diplomacy"] - 0.5) * 0.15,
            "innovation_bonus": (1 - self.traits["tradition"]) * 0.1
        }
    
    def get_military_modifiers(self):
        return {
            "morale_bonus": (self.traits["honor"] - 0.5) * 0.2,
            "aggression_bonus": (self.traits["militarism"] - 0.5) * 0.25,
        }
    
    def get_society_modifiers(self):
        return {
            "happiness_bonus": (self.traits["artistry"] / 100.0 - 0.5) * 0.1,
            "stability_bonus": (self.traits["cohesion"] / 100.0 - 0.5) * 0.2,
            "growth_bonus": (self.traits["collectivism"] - 0.5) * 0.1
        }
    
    def add_artifact(self, name, description, year_created):
        artifact = {
            "name": name,
            "description": description,
            "year_created": year_created,
            "civilization": self.civilization.name
        }
        self.artifacts.append(artifact)
        
        artifact_event = HistoryEvent(
            year=year_created,
            event_type="cultural_artifact",
            civilization=self.civilization.name,
            details=f"created {name}: {description}",
            person_id=self.civilization.leader.id,
            severity="normal"
        )
        self.civilization.world.history_archive.record_event(artifact_event)
    
    def to_dict(self):
        return {
            'traits': self.traits,
            'artifacts': self.artifacts,
            'cultural_achievements': self.cultural_achievements,
            'influences': self.influences
        }
    
    @classmethod
    def from_dict(cls, data, civilization):
        culture = cls(civilization)
        culture.traits = data['traits']
        culture.artifacts = data.get('artifacts', [])
        culture.cultural_achievements = data.get('cultural_achievements', [])
        culture.influences = data.get('influences', {})
        return culture

class Religion:
    DEITIES = ["Sun", "Moon", "Earth", "Sky", "Sea", "Forest", "Mountain", "River",
               "Ancestors", "Order", "Chaos", "Light", "Darkness", "Creation", "Destruction",
               "Wisdom", "Strength", "Justice", "Mercy", "Fate", "Freedom"]
    DOCTRINE_TYPES = {
        "monotheism": "Worship of a single deity",
        "polytheism": "Worship of multiple deities", 
        "animism": "Belief in spiritual essence in natural world",
        "ancestor_worship": "Veneration of ancestors",
        "philosophical": "Focus on ethical principles rather than deities",
        "dualistic": "Belief in balanced opposing forces"
    }
    MORAL_AXES = ["Benevolence", "Order", "Freedom", "Knowledge", "Power", "Tradition"]
    
    def __init__(self, name=None, founding_civ=None, year_founded=0):
        # --- FIX: Moved these two lines to the top ---
        self.doctrine_type = random.choice(list(self.DOCTRINE_TYPES.keys()))
        self.deities = self._generate_deities()
        # --- END FIX ---
        
        self.name = name if name else self.generate_name() # This line is now safe
        self.founding_civilization = founding_civ.name if founding_civ else "Unknown"
        self.year_founded = year_founded
        # self.doctrine_type = ... (Moved)
        # self.deities = ... (Moved)
        self.moral_focus = random.sample(self.MORAL_AXES, 2)
        self.spread_rate = random.uniform(0.01, 0.05)
        self.conflict_bias = random.uniform(-0.3, 0.3)
        self.followers = [founding_civ.name] if founding_civ else []
        self.holy_sites = []
        self.schisms = []
        self.description = self._generate_description()
    
    def _generate_deities(self):
        if self.doctrine_type == "monotheism":
            return [random.choice(self.DEITIES)]
        elif self.doctrine_type == "polytheism":
            return random.sample(self.DEITIES, random.randint(3, 5))
        elif self.doctrine_type == "dualistic":
            return random.sample(self.DEITIES, 2)
        else:
            return [random.choice(self.DEITIES)] if random.random() < 0.5 else []
    
    def generate_name(self):
        prefixes = ["Order of", "Church of", "Temple of", "Path of", "Way of", "Cult of"]
        suffixes = ["Light", "Darkness", "Truth", "Unity", "Harmony", "Eternity"]
        concepts = ["Divine", "Sacred", "Holy", "Eternal", "Ancient"]
        
        if random.random() < 0.6 and self.deities:
            return f"{random.choice(prefixes)} the {random.choice(self.deities)}"
        else:
            return f"{random.choice(concepts)} {random.choice(suffixes)}"
    
    def _generate_description(self):
        focus_desc = {
            "Benevolence": "compassion and charity",
            "Order": "structure and discipline", 
            "Freedom": "individual liberty and choice",
            "Knowledge": "learning and wisdom",
            "Power": "strength and dominance",
            "Tradition": "ancestral ways and customs"
        }
        desc_parts = [f"The {self.name} "]
        if self.doctrine_type == "monotheism":
            desc_parts.append(f"worships {self.deities[0]} as the one true deity. ")
        elif self.doctrine_type == "polytheism":
            desc_parts.append(f"reveres multiple deities including {', '.join(self.deities[:3])}. ")
        elif self.doctrine_type == "animism":
            desc_parts.append("finds spiritual essence throughout the natural world. ")
        else:
            desc_parts.append(f"follows the {self.doctrine_type} path. ")
        
        desc_parts.append(f"The faith emphasizes {focus_desc[self.moral_focus[0]]} ")
        desc_parts.append(f"and {focus_desc[self.moral_focus[1]]}.")
        return "".join(desc_parts)
    
    def add_follower(self, civilization_name):
        if civilization_name not in self.followers:
            self.followers.append(civilization_name)
    
    def remove_follower(self, civilization_name):
        if civilization_name in self.followers:
            self.followers.remove(civilization_name)
    
    def calculate_compatibility(self, other_religion):
        if self == other_religion:
            return 1.0
        if not other_religion:
            return 0.3
        
        doctrine_match = 0.3 if self.doctrine_type == other_religion.doctrine_type else 0
        shared_morals = len(set(self.moral_focus) & set(other_religion.moral_focus))
        moral_match = shared_morals * 0.15
        shared_deities = len(set(self.deities) & set(other_religion.deities))
        deity_match = shared_deities * 0.1
        
        return min(1.0, doctrine_match + moral_match + deity_match + 0.1)
    
    def to_dict(self):
        return {
            'name': self.name,
            'founding_civilization': self.founding_civilization,
            'year_founded': self.year_founded,
            'doctrine_type': self.doctrine_type,
            'deities': self.deities,
            'moral_focus': self.moral_focus,
            'spread_rate': self.spread_rate,
            'conflict_bias': self.conflict_bias,
            'followers': self.followers,
            'holy_sites': self.holy_sites,
            'schisms': self.schisms,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data):
        religion = cls()
        religion.name = data['name']
        religion.founding_civilization = data['founding_civilization']
        religion.year_founded = data['year_founded']
        religion.doctrine_type = data['doctrine_type']
        religion.deities = data['deities']
        religion.moral_focus = data['moral_focus']
        religion.spread_rate = data['spread_rate']
        religion.conflict_bias = data['conflict_bias']
        religion.followers = data['followers']
        religion.holy_sites = data.get('holy_sites', [])
        religion.schisms = data.get('schisms', [])
        religion.description = data.get('description', religion._generate_description())
        return religion

class ReligionSystem:
    def __init__(self, world):
        self.world = world
        self.religions = []
        self.religious_events = []
    
    def initialize_religions(self, civilizations):
        num_religions = random.randint(1, min(3, len(civilizations)))
        civ_pool = list(civilizations)
        
        for i in range(num_religions):
            if not civ_pool: break
            founding_civ = random.choice(civ_pool)
            civ_pool.remove(founding_civ)
            
            religion = Religion(founding_civ=founding_civ, year_founded=self.world.year)
            self.religions.append(religion)
            
            self.assign_religion(founding_civ, religion)
            
            founding_event = HistoryEvent(
                year=self.world.year,
                event_type="religion_founded",
                civilization=founding_civ.name,
                details=f"founded the {religion.name}: {religion.description}",
                person_id=founding_civ.leader.id,
                severity="major"
            )
            self.world.history_archive.record_event(founding_event)
        
        for civ in civilizations:
            if not hasattr(civ, 'religion') or civ.religion is None:
                self.assign_religion(civ)
    
    def assign_religion(self, civilization, specific_religion=None):
        if civilization.religion:
            civilization.religion.remove_follower(civilization.name)
            
        if specific_religion:
            civilization.religion = specific_religion
            specific_religion.add_follower(civilization.name)
        elif self.religions:
            compatible_religions = []
            for religion in self.religions:
                compatibility = self._calculate_cultural_compatibility(civilization, religion)
                compatible_religions.append((religion, compatibility))
            
            total = sum(comp for _, comp in compatible_religions)
            if total > 0:
                rand_val = random.uniform(0, total)
                current = 0
                for religion, comp in compatible_religions:
                    current += comp
                    if rand_val <= current:
                        civilization.religion = religion
                        religion.add_follower(civilization.name)
                        return
            
            civilization.religion = random.choice(self.religions)
            civilization.religion.add_follower(civilization.name)
        else:
            new_religion = Religion(founding_civ=civilization, year_founded=self.world.year)
            self.religions.append(new_religion)
            civilization.religion = new_religion
    
    def _calculate_cultural_compatibility(self, civilization, religion):
        culture = civilization.culture_system.traits
        base_compatibility = culture["spirituality"] / 100.0
        
        if religion.year_founded < self.world.year - 50:
            base_compatibility += culture["tradition"] * 0.3
        
        if len(religion.followers) > 1:
            base_compatibility += culture["collectivism"] * 0.2
        
        return max(0.1, base_compatibility)
    
    def update_yearly(self):
        for religion in self.religions:
            self._spread_religion(religion)
        self._check_religious_events()
    
    def _spread_religion(self, religion):
        if len(religion.followers) == 0:
            return
        
        for civ in self.world.civilizations:
            if civ.religion == religion:
                continue
            
            is_neighbor = False
            for other_civ in self.world.civilizations:
                if (other_civ.religion == religion and 
                    self._are_neighbors(civ, other_civ)):
                    is_neighbor = True
                    break
            
            if is_neighbor:
                conversion_chance = religion.spread_rate
                conversion_chance += (civ.culture_system.traits["spirituality"] / 500.0)
                conversion_chance -= (civ.culture_system.traits["tradition"] * 0.1)
                
                # Check for active Priest
                priest_bonus = civ.get_profession_bonus("religion_spread_bonus")
                conversion_chance += priest_bonus

                if random.random() < conversion_chance:
                    old_religion = civ.religion
                    self.assign_religion(civ, religion)
                    
                    conversion_event = HistoryEvent(
                        year=self.world.year,
                        event_type="religious_conversion",
                        civilization=civ.name,
                        details=f"converted from {old_religion.name if old_religion else 'no faith'} to {religion.name}",
                        person_id=civ.leader.id,
                        severity="normal"
                    )
                    self.world.history_archive.record_event(conversion_event)
    
    def _are_neighbors(self, civ1, civ2):
        x1, y1 = civ1.map_position
        x2, y2 = civ2.map_position
        distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        return distance <= 10  # Increased neighbor radius
    
    def _check_religious_events(self):
        for religion in self.religions:
            if len(religion.followers) >= 3 and random.random() < 0.02:
                self._trigger_schism(religion)
            
            for civ_name in religion.followers:
                civ = self.world.get_civ_by_name(civ_name)
                if (civ and civ.culture_system.traits["artistry"] > 70 and 
                    civ.stability > 80 and random.random() < 0.01):
                    self._trigger_reformation(civ, religion)
    
    def _trigger_schism(self, religion):
        schismatic_civ_names = random.sample(religion.followers, 
                                       min(2, len(religion.followers) // 2))
        
        if not schismatic_civ_names: return
        
        founding_civ = self.world.get_civ_by_name(random.choice(schismatic_civ_names))
        if not founding_civ: return
        
        new_religion = Religion(founding_civ=founding_civ, year_founded=self.world.year)
        
        new_religion.doctrine_type = religion.doctrine_type
        new_religion.deities = religion.deities[:]
        if new_religion.deities and random.random() < 0.7:
            idx = random.randint(0, len(new_religion.deities) - 1)
            new_religion.deities[idx] = random.choice(Religion.DEITIES)
        
        new_religion.moral_focus = religion.moral_focus[:]
        if random.random() < 0.5:
            idx = random.randint(0, len(new_religion.moral_focus) - 1)
            available_morals = [m for m in Religion.MORAL_AXES if m not in new_religion.moral_focus]
            if available_morals:
                new_religion.moral_focus[idx] = random.choice(available_morals)
        
        new_religion.conflict_bias = religion.conflict_bias + random.uniform(-0.2, 0.2)
        new_religion.description = new_religion._generate_description()
        
        self.religions.append(new_religion)
        religion.schisms.append({
            "year": self.world.year,
            "new_religion": new_religion.name,
            "reason": "doctrinal differences"
        })
        
        for civ_name in schismatic_civ_names:
            civ = self.world.get_civ_by_name(civ_name)
            if civ:
                self.assign_religion(civ, new_religion)
        
        schism_event = HistoryEvent(
            year=self.world.year,
            event_type="religious_schism",
            civilization=founding_civ.name,
            details=f"broke away from {religion.name} to form {new_religion.name}",
            person_id=founding_civ.leader.id,
            severity="major"
        )
        self.world.history_archive.record_event(schism_event)
    
    def _trigger_reformation(self, civilization, religion):
        if random.random() < 0.5 and religion.deities:
            old_deity = random.choice(religion.deities)
            new_deity = random.choice([d for d in Religion.DEITIES if d != old_deity])
            religion.deities[religion.deities.index(old_deity)] = new_deity
        
        if random.random() < 0.4:
            religion.moral_focus[0] = random.choice([m for m in Religion.MORAL_AXES if m != religion.moral_focus[1]])
        
        religion.conflict_bias += random.uniform(-0.1, 0.1)
        religion.description = religion._generate_description()
        
        reformation_event = HistoryEvent(
            year=self.world.year,
            event_type="religious_reformation",
            civilization=civilization.name,
            details=f"led a reformation within {religion.name}, changing its doctrines",
            person_id=civilization.leader.id,
            severity="major"
        )
        self.world.history_archive.record_event(reformation_event)
        
        civilization.leader.add_achievement(f"Led reformation of {religion.name}")
    
    def to_dict(self):
        return {
            'religions': [religion.to_dict() for religion in self.religions],
        }
    
    @classmethod
    def from_dict(cls, data, world):
        religion_system = cls(world)
        religion_system.religions = [Religion.from_dict(rel_data) for rel_data in data['religions']]
        return religion_system
    
    def get_religion_by_name(self, name):
        for religion in self.religions:
            if religion.name == name:
                return religion
        return None

"""
====================== 5. CIVILIZATION CLASS ======================
(Heavily upgraded for PA-11: Individuals & new Leader logic)
"""

class Civilization:
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
        self.relationships = {} # Key: civ name, Value: relationship score
        
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
            "farmers": 0.40, "merchants": 0.20, "nobles": 0.10,
            "soldiers": 0.15, "scholars": 0.15
        }
        self.happiness = 70
        self.stability = 80
        self.tech_level = 1.0
        self.tech_progress = 0.0
        
        # Military system
        self.army_size = 0
        self.war_with = None
        self.peace_treaty_years = 0
        
        # --- PA-11: INDIVIDUALS & DYNASTIES ---
        self.individuals = [] # List of Person objects
        self.dynasties = []   # List of Dynasty objects
        self.leader = None    # Will be a Person object
        self.leader_history = [] # List of previous leader Persons
        self._generate_founding_population()
        # ---
        
        # CULTURE & RELIGION SYSTEM
        terrain_type = self.world.map.get_terrain_at(self.map_position)
        self.culture_system = CultureSystem(self, terrain_type=terrain_type)
        self.religion = None  # Will be assigned by ReligionSystem
        
        # HISTORY SYSTEM
        self.history = []  # Stores HistoryEvent objects
        
        self._distribute_population()
        self._record_founding_event()
    
    def _generate_founding_population(self):
        """Creates the first ruler, dynasty, and a few nobles"""
        # Create Founder
        founder = Person(self.name, self.world.year)
        founder.profession = "Ruler"
        founder.reign_start_year = self.world.year
        
        # Create Founding Dynasty
        dynasty_name = f"House {random.choice(DYNASTY_PREFIXES)}{random.choice(DYNASTY_SUFFIXES)}"
        founder_dynasty = Dynasty(dynasty_name, founder)
        founder.dynasty = founder_dynasty
        founder.surname = founder_dynasty.name
        founder.full_name = f"{founder.name} {founder.surname}"
        
        self.dynasties.append(founder_dynasty)
        self.individuals.append(founder)
        self.world.all_people[founder.id] = founder
        self.world.all_dynasties[dynasty_name] = founder_dynasty # Add to global list
        
        self.leader = founder
        self.leader_history.append(founder)
        
        # Log dynasty founding
        self.world.history_archive.record_event(HistoryEvent(
            year=self.world.year,
            event_type="dynasty_founded",
            civilization=self.name,
            details=f"The {dynasty_name} was founded by {founder.full_name}",
            person_id=founder.id,
            severity="major"
        ))
        
        # Generate a few other nobles
        for _ in range(random.randint(2, 4)):
            noble_founder = Person(self.name, self.world.year)
            noble_founder.profession = "Noble"
            d_name = f"House {random.choice(DYNASTY_PREFIXES)}{random.choice(DYNASTY_SUFFIXES)}"
            n_dynasty = Dynasty(d_name, noble_founder)
            noble_founder.dynasty = n_dynasty
            noble_founder.surname = n_dynasty.name
            noble_founder.full_name = f"{noble_founder.name} {noble_founder.surname}"
            
            self.dynasties.append(n_dynasty)
            self.individuals.append(noble_founder)
            self.world.all_people[noble_founder.id] = noble_founder
            self.world.all_dynasties[d_name] = n_dynasty # Add to global list

    def _record_founding_event(self):
        founding_event = HistoryEvent(
            year=self.world.year,
            event_type="foundation",
            civilization=self.name,
            details=f"{self.name} was founded by {self.leader.full_name} of {self.leader.dynasty.name}",
            person_id=self.leader.id,
            severity="major"
        )
        self.history.append(founding_event)
        self.world.history_archive.record_event(founding_event)
    
    def generate_name(self):
        prefixes = ["Ara", "Kha", "Zan", "Vor", "El", "Nor", "Syl", "Quor"]
        suffixes = ["dor", "nia", "thar", "van", "ris", "thal", "mor", "gard"]
        return random.choice(prefixes) + random.choice(suffixes)
    
    def _distribute_population(self):
        total = sum(self.society.values())
        if total != 1.0 and total > 0:
            for key in self.society:
                self.society[key] /= total
    
    def update_year(self):
        """Update civilization for one year"""
        
        # --- 1. Update Individuals ---
        # Update all individuals and check for leader death
        for person in self.individuals:
            person.update_year(self.world)
            
        # Clean up dead individuals (from civ list, not world list)
        self.individuals = [p for p in self.individuals if p.alive]
        
        # --- 2. Check Succession ---
        if not self.leader.alive:
            self._handle_succession()
        
        # --- 3. Update Culture ---
        self.culture_system.update_yearly()
        
        # --- 4. Get Modifiers ---
        # Get modifiers from all individuals with professions
        combined_modifiers = defaultdict(float)
        for person in self.individuals:
            if person.profession != "Commoner":
                mods = person.get_profession_modifiers()
                for key, value in mods.items():
                    combined_modifiers[key] += value
                    
        # Get modifiers from culture
        cultural_mods = [self.culture_system.get_economic_modifiers(),
                         self.culture_system.get_military_modifiers(),
                         self.culture_system.get_society_modifiers()]
        for mod_dict in cultural_mods:
            for key, value in mod_dict.items():
                combined_modifiers[key] += value
        
        # --- 5. Update Core Systems ---
        self._update_population(combined_modifiers)
        self._update_economy(combined_modifiers)
        self._update_technology(combined_modifiers)
        self._update_military(combined_modifiers)
        self._update_society(combined_modifiers)
        
        # --- 6. Handle Events ---
        self._handle_cultural_events()
        self._handle_crises()
        
        # --- 7. Record History ---
        self._record_annual_summary()

    def _handle_succession(self):
        """Handle leader death and finding a new heir"""
        old_leader = self.leader
        old_leader.add_achievement(f"Ruled {self.name} for {old_leader.age - old_leader.reign_start_year} years")
        
        # --- Find Heir Logic ---
        new_heir = None
        heir_source = "dynasty"
        
        # 1. Oldest living child
        living_children = [self.world.get_person_by_id(cid) for cid in old_leader.children_ids if self.world.get_person_by_id(cid).alive]
        if living_children:
            new_heir = sorted(living_children, key=lambda x: x.age, reverse=True)[0]
        
        # 2. Oldest living sibling (needs parent tracking, simplified)
        if not new_heir and old_leader.dynasty:
            siblings = [self.world.get_person_by_id(mid) for mid in old_leader.dynasty.members 
                        if mid != old_leader.id and self.world.get_person_by_id(mid).alive and
                        self.world.get_person_by_id(mid).age > 16]
            if siblings:
                new_heir = sorted(siblings, key=lambda x: x.age, reverse=True)[0]
        
        # 3. Highest-fame noble from another dynasty
        if not new_heir:
            heir_source = "noble_election"
            nobles = [p for p in self.individuals if p.dynasty and p.alive and p.age > 16]
            if nobles:
                new_heir = sorted(nobles, key=lambda x: x.fame, reverse=True)[0]
        
        # 4. Usurpation by Hero (if no heir found)
        if not new_heir:
            heir_source = "usurpation"
            heroes = [p for p in self.individuals if p.is_hero and p.alive and p.age > 16]
            if heroes:
                new_heir = sorted(heroes, key=lambda x: (x.stats["combat"], x.fame), reverse=True)[0]
            else: # Total collapse
                print(f"CRITICAL: {self.name} has no heir and no heroes! Collapsing.")
                # This is where a civ could be destroyed
                return

        # --- Set New Leader ---
        self.leader = new_heir
        self.leader.profession = "Ruler"
        self.leader.reign_start_year = self.world.year
        self.leader_history.append(self.leader)
        
        details = f"{self.leader.full_name} of {self.leader.dynasty.name} has taken the throne"
        if heir_source == "usurpation":
            details = f"Following a power vacuum, the hero {self.leader.full_name} has seized control"
            if not self.leader.dynasty: # Hero commoner
                new_dynasty_name = f"House {random.choice(DYNASTY_PREFIXES)}{random.choice(DYNASTY_SUFFIXES)}"
                new_dynasty = Dynasty(new_dynasty_name, self.leader)
                self.dynasties.append(new_dynasty)
                self.world.all_dynasties[new_dynasty_name] = new_dynasty
                self.leader.dynasty = new_dynasty
                self.leader.surname = new_dynasty.name
                self.leader.full_name = f"{self.leader.name} {self.leader.surname}"
                details += f", founding the new {new_dynasty.name} dynasty."
                self.world.history_archive.record_event(HistoryEvent(
                    year=self.world.year, event_type="dynasty_founded", civilization=self.name,
                    details=f"The {new_dynasty.name} was founded by {self.leader.full_name}",
                    person_id=self.leader.id, severity="major"
                ))

        succession_event = HistoryEvent(
            year=self.world.year,
            event_type="succession",
            civilization=self.name,
            details=details,
            person_id=self.leader.id,
            severity="major",
            caused_by=old_leader.id # This is just a hint, auto-linker will find the 'death' event
        )
        self.world.history_archive.record_event(succession_event)
        
        self.stability -= 25 if heir_source != "dynasty" else 10
    
    def _update_population(self, modifiers):
        growth_rate = 0.01
        food_per_person = self.resources["food"] / max(1, self.population)
        if food_per_person > 1.2:
            growth_rate += 0.02
        elif food_per_person < 0.8:
            growth_rate -= 0.03
        
        growth_rate += (self.happiness - 50) / 2000.0
        growth_rate += modifiers.get("growth_bonus", 0)
        
        old_population = self.population
        self.population = int(self.population * (1 + growth_rate))
        self.population = max(100, self.population)
        
        if abs(self.population - old_population) / max(1, old_population) > 0.05:
            self._distribute_population()
    
    def _update_economy(self, modifiers):
        terrain_bonus = self.world.map.get_terrain_bonus(self.map_position)
        climate_modifiers = self.world.climate.get_climate_modifiers()
        
        farmer_pop = self.population * self.society["farmers"]
        merchant_pop = self.population * self.society["merchants"]
        
        food_production = (farmer_pop * self.FARMER_YIELD + 
                           terrain_bonus.get("food", 0) + 
                           climate_modifiers.get("food", 0))
        
        wealth_production = (merchant_pop * self.MERCHANT_WEALTH + 
                             terrain_bonus.get("wealth", 0))
        
        metal_production = (self.population * self.society["soldiers"] * 0.5 + 
                           terrain_bonus.get("metal", 0))

        # Apply modifiers
        food_production *= (1 + modifiers.get("production_bonus", 0))
        wealth_production *= (1 + modifiers.get("trade_bonus", 0) + modifiers.get("trade_bonus", 0))
        
        food_consumption = (self.population * self.BASE_FOOD_CONSUMPTION +
                            self.army_size * self.SOLDIER_FOOD_UPKEEP)
        
        wealth_consumption = (self.army_size * self.SOLDIER_WEALTH_UPKEEP +
                              self.population * self.society["scholars"] * self.SCHOLAR_WEALTH_UPKEEP +
                              self.population * self.society["nobles"] * self.NOBLE_WEALTH_UPKEEP)
        
        self.resources["food"] += food_production - food_consumption
        self.resources["wealth"] += wealth_production - wealth_consumption
        self.resources["metal"] += metal_production
        
        for res, limit in self.storage_limits.items():
            self.resources[res] = max(0, min(self.resources[res], limit))
        
        self.last_year_production = {
            "food": food_production,
            "wealth": wealth_production,
            "metal": metal_production
        }
        self._update_economic_state()
    
    def _update_economic_state(self):
        food_ratio = self.resources["food"] / max(1, self.population * self.BASE_FOOD_CONSUMPTION)
        wealth_ratio = self.resources["wealth"] / max(1, self.population)
        
        if food_ratio > 1.5 and wealth_ratio > 1.0:
            self.economic_state = "prosperous"
        elif food_ratio < 0.8 or wealth_ratio < 0.5:
            self.economic_state = "struggling"
        else:
            self.economic_state = "stable"
    
    def _update_technology(self, modifiers):
        scholar_pop = self.population * self.society["scholars"]
        tech_progress = scholar_pop * self.SCHOLAR_TECH
        
        tech_progress *= (1 + modifiers.get("innovation_bonus", 0))
        tech_progress *= (1 + modifiers.get("tech_bonus", 0))
        
        self.tech_progress += tech_progress
        
        if self.tech_progress >= 1.0:
            self.tech_level += 1
            self.tech_progress = 0.0
            
            # Find the best scholar
            scholar = self.get_best_person_for_job("Scholar")
            person_id = scholar.id if scholar else self.leader.id
            if scholar:
                scholar.add_fame(10, self.world, "a technological breakthrough")
            
            tech_event = HistoryEvent(
                year=self.world.year,
                event_type="tech_advance",
                civilization=self.name,
                details=f"achieved Technology Level {self.tech_level}",
                person_id=person_id,
                severity="major"
            )
            self.history.append(tech_event)
            self.world.history_archive.record_event(tech_event)
    
    def _update_military(self, modifiers):
        target_army_size = int(self.population * self.society["soldiers"])
        target_army_size = int(target_army_size * (1 + modifiers.get("aggression_bonus", 0)))
        
        if target_army_size > self.army_size:
            recruit_cost = (target_army_size - self.army_size) * 10
            if self.resources["wealth"] > recruit_cost and self.resources["metal"] > (target_army_size - self.army_size):
                self.army_size = target_army_size
                self.resources["wealth"] -= recruit_cost
        elif target_army_size < self.army_size:
            self.army_size = target_army_size
    
    def _update_society(self, modifiers):
        happiness_change = 0
        stability_change = 0
        
        food_ratio = self.resources["food"] / max(1, self.population * self.BASE_FOOD_CONSUMPTION)
        if food_ratio > 1.5: happiness_change += 5
        elif food_ratio < 0.8: happiness_change -= 10
        
        wealth_ratio = self.resources["wealth"] / max(1, self.population)
        if wealth_ratio > 2: happiness_change += 3
        elif wealth_ratio < 0.5: happiness_change -= 5
        
        if self.war_with:
            happiness_change -= 10
            stability_change -= 5
        
        happiness_change += modifiers.get("happiness_bonus", 0) * 10
        stability_change += modifiers.get("stability_bonus", 0) * 10
        
        self.happiness = max(0, min(100, self.happiness + happiness_change))
        self.stability = max(0, min(100, self.stability + stability_change))

    def _calculate_cultural_similarity(self, other_civ):
        similarity = 0
        my_traits = self.culture_system.traits
        their_traits = other_civ.culture_system.traits
        trait_count = 0
        
        for trait in my_traits:
            if trait in their_traits and isinstance(my_traits[trait], (int, float)):
                my_val, their_val = my_traits[trait], their_traits[trait]
                if trait in ["artistry", "spirituality", "cohesion"]:
                    my_val /= 100.0
                    their_val /= 100.0
                
                diff = abs(my_val - their_val)
                similarity += (1 - diff)
                trait_count += 1
        
        return similarity / trait_count if trait_count > 0 else 0.5

    def _handle_cultural_events(self):
        if (self.culture_system.traits["artistry"] > 80 and 
            self.stability > 75 and 
            self.resources["wealth"] > self.population and
            random.random() < 0.05):
            self._trigger_cultural_renaissance()
        
        if (self.culture_system.traits["spirituality"] > 60 and
            self.resources["wealth"] > self.population * 0.5 and
            random.random() < 0.03):
            self._trigger_pilgrimage()
        
        if (self.culture_system.traits["artistry"] > 70 and
            self.tech_level > 2.0 and
            random.random() < 0.02):
            self._create_cultural_artifact()

        if (self.happiness > 70 and
            self.culture_system.traits["artistry"] > 50 and
            random.random() < 0.1):
            self._trigger_festival()
            
    def _trigger_cultural_renaissance(self):
        artifact_types = ["Epic Poem", "Symphony", "Architectural Masterpiece"]
        themes = ["Heroism", "Love", "Nature", "Divinity"]
        artifact_name = f"{random.choice(artifact_types)} of {random.choice(themes)}"
        artifact_desc = f"A magnificent work that defines the {self.name} cultural renaissance"
        
        self.culture_system.add_artifact(artifact_name, artifact_desc, self.world.year)
        
        self.happiness += 20
        self.stability += 15
        self.tech_progress += 0.5
        self.resources["wealth"] += self.population * 0.3
        
        renaissance_event = HistoryEvent(
            year=self.world.year,
            event_type="cultural_renaissance",
            civilization=self.name,
            details=f"experienced a cultural renaissance, producing {artifact_name}",
            person_id=self.leader.id,
            severity="major"
        )
        self.history.append(renaissance_event)
        self.world.history_archive.record_event(renaissance_event)
        self.leader.add_achievement(f"Patron of the {self.name} Renaissance")
    
    def _trigger_pilgrimage(self):
        if not self.religion: return
        self.happiness += 15
        self.stability += 10
        self.culture_system.traits["cohesion"] = min(100, self.culture_system.traits["cohesion"] + 20)
        self.resources["wealth"] = max(0, self.resources["wealth"] - self.population * 0.2)
        
        pilgrimage_event = HistoryEvent(
            year=self.world.year,
            event_type="pilgrimage",
            civilization=self.name,
            details=f"undertook a great pilgrimage to holy sites of {self.religion.name}",
            person_id=self.leader.id,
            severity="normal"
        )
        self.history.append(pilgrimage_event)
        self.world.history_archive.record_event(pilgrimage_event)
    
    def _create_cultural_artifact(self):
        artifact_types = ["Crown", "Scepter", "Codex", "Tapestry"]
        materials = ["Golden", "Crystal", "Marble", "Jade"]
        artifact_name = f"{random.choice(materials)} {random.choice(artifact_types)}"
        artifact_desc = f"A masterpiece of {self.name} craftsmanship"
        self.culture_system.add_artifact(artifact_name, artifact_desc, self.world.year)
        # Event is recorded by add_artifact

    def _trigger_festival(self):
        self.happiness = min(100, self.happiness + 5)
        self.culture_system.traits["cohesion"] = min(100, self.culture_system.traits["cohesion"] + 2)
        
        festival_event = HistoryEvent(
            year=self.world.year,
            event_type="festival",
            civilization=self.name,
            details=f"held a grand festival, boosting morale",
            person_id=self.leader.id,
            severity="minor"
        )
        self.history.append(festival_event)
        self.world.history_archive.record_event(festival_event)
            
    def _handle_crises(self):
        food_ratio = self.resources["food"] / max(1, self.population * self.BASE_FOOD_CONSUMPTION)
        if food_ratio < 0.5 and random.random() < 0.3:
            self._trigger_famine()
        
        if self.stability < 30 and random.random() < 0.2:
            self._trigger_rebellion()
        
        wealth_ratio = self.resources["wealth"] / max(1, self.population)
        if wealth_ratio < 0.3 and self.economic_state == "struggling" and random.random() < 0.1:
            self._trigger_economic_collapse()
    
    def _trigger_famine(self):
        population_loss = int(self.population * random.uniform(0.1, 0.3))
        self.population = max(100, self.population - population_loss)
        self.happiness -= 20
        self.stability -= 15
        
        famine_event = HistoryEvent(
            year=self.world.year,
            event_type="famine",
            civilization=self.name,
            details=f"suffered a famine, losing {population_loss} people",
            person_id=self.leader.id,
            severity="major"
        )
        self.history.append(famine_event)
        self.world.history_archive.record_event(famine_event)
    
    def _trigger_rebellion(self):
        rebellion_severity = random.choice(["minor", "major", "civil_war"])
        
        if rebellion_severity == "minor":
            self.stability -= 10
            details = "faced minor unrest and protests"
            severity = "normal"
        elif rebellion_severity == "major":
            self.stability -= 25
            self.happiness -= 15
            details = "experienced major riots and rebellion"
            severity = "major"
        else:
            self.stability -= 40
            self.happiness -= 25
            self.army_size = int(self.army_size * 0.7)
            details = "descended into civil war"
            severity = "catastrophic"
        
        rebellion_event = HistoryEvent(
            year=self.world.year,
            event_type="rebellion",
            civilization=self.name,
            details=details,
            person_id=self.leader.id,
            severity=severity
        )
        self.history.append(rebellion_event)
        self.world.history_archive.record_event(rebellion_event)
    
    def _trigger_economic_collapse(self):
        wealth_loss = int(self.resources["wealth"] * random.uniform(0.3, 0.7))
        self.resources["wealth"] = max(0, self.resources["wealth"] - wealth_loss)
        self.happiness -= 25
        self.stability -= 20
        
        collapse_event = HistoryEvent(
            year=self.world.year,
            event_type="economic_collapse",
            civilization=self.name,
            details=f"suffered economic collapse, losing {wealth_loss} wealth",
            person_id=self.leader.id,
            severity="major"
        )
        self.history.append(collapse_event)
        self.world.history_archive.record_event(collapse_event)

    def _record_annual_summary(self):
        if self.world.year % 10 != 0:
            return
            
        summary_event = HistoryEvent(
            year=self.world.year,
            event_type="annual_summary",
            civilization=self.name,
            details=f"Pop: {self.population}, Wealth: {int(self.resources['wealth'])}, Stability: {int(self.stability)}%",
            person_id=self.leader.id,
            severity="minor"
        )
        self.history.append(summary_event)
        self.world.history_archive.record_event(summary_event)
    
    def get_recent_history(self, years=5):
        current_year = self.world.year
        return [event for event in self.history if current_year - event.year <= years]
    
    def get_best_person_for_job(self, profession):
        """Finds the best person for a job based on stats"""
        job_stat_map = {
            "General": "combat",
            "Diplomat": "diplomacy",
            "Treasurer": "stewardship",
            "Scholar": "learning",
            "Priest": "piety"
        }
        if profession not in job_stat_map:
            return None
        
        stat_to_check = job_stat_map[profession]
        
        candidates = [p for p in self.individuals if p.alive and p.profession == profession]
        if not candidates:
            candidates = [p for p in self.individuals if p.alive and p.dynasty] # Any noble
            
        if not candidates:
            return None
            
        return sorted(candidates, key=lambda x: x.stats[stat_to_check], reverse=True)[0]
        
    def get_profession_bonus(self, bonus_type):
        """Get the total bonus from all professionals"""
        total_bonus = 0
        for person in self.individuals:
            if person.alive:
                total_bonus += person.get_profession_modifiers().get(bonus_type, 0)
        return total_bonus

    def display_status(self):
        print(f"\n=== {self.name} ({self.economic_state}) ===")
        print(f"Ruler: {self.leader.full_name} (Age: {self.leader.age}) of {self.leader.dynasty.name}")
        print(f"Population: {self.population:,}")
        print(f"Technology Level: {self.tech_level:.1f} (Progress: {self.tech_progress:.1%})")
        print(f"Resources: Food={int(self.resources['food'])}, Metal={int(self.resources['metal'])}, Wealth={int(self.resources['wealth'])}")
        print(f"Happiness: {int(self.happiness)}/100, Stability: {int(self.stability)}/100")
        print(f"Religion: {self.religion.name if self.religion else 'None'}")
        print(f"Army Size: {self.army_size}")
        if self.war_with:
            print(f"At War with: {self.war_with}")

    def to_dict(self):
        """Convert civilization to dictionary for saving"""
        return {
            'id': self.id,
            'name': self.name,
            'population': self.population,
            'technology': self.technology,
            'map_position': self.map_position,
            'relationships': self.relationships,
            'resources': self.resources,
            'storage_limits': self.storage_limits,
            'economic_state': self.economic_state,
            'last_year_production': self.last_year_production,
            'society': self.society,
            'happiness': self.happiness,
            'stability': self.stability,
            'tech_level': self.tech_level,
            'tech_progress': self.tech_progress,
            'army_size': self.army_size,
            'war_with': self.war_with,
            'peace_treaty_years': self.peace_treaty_years,
            'leader_id': self.leader.id,
            'leader_history_ids': [p.id for p in self.leader_history],
            'dynasty_names': [d.name for d in self.dynasties], # Dynasties saved at world level
            'individual_ids': [p.id for p in self.individuals], # Individuals saved at world level
            'culture_system': self.culture_system.to_dict(),
            'religion_name': self.religion.name if self.religion else None,
            'history': [event.to_dict() for event in self.history]
        }
    
    @classmethod
    def from_dict(cls, data, world):
        """Create civilization from saved data"""
        # Create dummy civ first, leader/dynasties will be linked by World
        civ = cls(world, data['id'], data['name'], data['population'], 
                 data['technology'], data['map_position'])
        
        # Clear auto-generated individuals
        civ.individuals = []
        civ.dynasties = []
        civ.leader = None
        civ.leader_history = []
        
        # Load data
        civ.relationships = data['relationships']
        civ.resources = data['resources']
        civ.storage_limits = data['storage_limits']
        civ.economic_state = data['economic_state']
        civ.last_year_production = data['last_year_production']
        civ.society = data['society']
        civ.happiness = data['happiness']
        civ.stability = data['stability']
        civ.tech_level = data['tech_level']
        civ.tech_progress = data['tech_progress']
        civ.army_size = data['army_size']
        civ.war_with = data['war_with']
        civ.peace_treaty_years = data['peace_treaty_years']
        
        # Store IDs to be linked
        civ.loader_leader_id = data['leader_id']
        civ.loader_leader_history_ids = data['leader_history_ids']
        civ.loader_dynasty_names = data['dynasty_names']
        civ.loader_individual_ids = data['individual_ids']
        
        civ.culture_system = CultureSystem.from_dict(data['culture_system'], civ)
        civ.loader_religion_name = data.get('religion_name')
        civ.history = [HistoryEvent.from_dict(event_data) for event_data in data['history']]
        
        return civ

"""
====================== 6. WORLD CLASS ======================
(Heavily upgraded for PA-11: Manages global Person/Dynasty lists)
"""

class World:
    """Manages the game world with civilizations and history"""
    
    def __init__(self, num_civilizations=4, width=40, height=20, seed=None):
        self.year = 0
        self.rng = random.Random(seed) if seed is not None else random.Random()
        
        # --- Global Object Pools (NEW) ---
        self.all_people = {}    # Key: ID, Value: Person object
        self.all_dynasties = {} # Key: Name, Value: Dynasty object
        
        # Core systems
        self.map = WorldMap(width, height, seed=self.rng.randint(0, 1000000))
        self.climate = ClimateSystem(rng=self.rng)
        
        # DEEP HISTORY SYSTEM (needs world ref for Legends)
        self.history_archive = HistoryArchive()
        self.legends_mode = LegendsMode(self.history_archive, self)
        
        # Civilizations (must be created AFTER map)
        self.civilizations = []
        self.map.generate_geography() # Generate map first
        for i in range(num_civilizations):
            civ = Civilization(self, i)
            self.map.place_civilization(civ) # Place civ on map
            self.civilizations.append(civ)
        
        # RELIGION SYSTEM (must be initialized AFTER civs)
        self.religion_system = ReligionSystem(self)
        self.religion_system.initialize_religions(self.civilizations)
        
        # Initialize relationships
        for civ in self.civilizations:
            self._initialize_relationships(civ)

    # --- PA-11: Helper Functions ---
    def get_person_by_id(self, person_id):
        return self.all_people.get(person_id)
        
    def get_dynasty_by_name(self, name):
        return self.all_dynasties.get(name)
        
    def get_civ_by_name(self, name):
        for civ in self.civilizations:
            if civ.name.lower() == name.lower():
                return civ
        return None
    
    def _initialize_relationships(self, civ):
        for other_civ in self.civilizations:
            if civ.id == other_civ.id:
                continue
            if other_civ.name not in civ.relationships:
                civ.relationships[other_civ.name] = random.uniform(-0.5, 0.5)
            if civ.name not in other_civ.relationships:
                other_civ.relationships[civ.name] = civ.relationships[other_civ.name]
    
    def simulate_year(self):
        """Simulate one year for all civilizations"""
        self.year += 1
        self.climate.update()
        
        # Update all civilizations (this now updates individuals AND civ stats)
        for civ in self.civilizations:
            civ.update_year()
        
        # Update religion system (spread, etc.)
        self.religion_system.update_yearly()
        
        # Handle inter-civilization interactions
        self._handle_diplomatic_interactions()
        self._handle_wars()
    
    def _handle_diplomatic_interactions(self):
        for i, civ1 in enumerate(self.civilizations):
            for civ2 in self.civilizations[i+1:]:
                self._update_relationship_drift(civ1, civ2)
                
                if civ1.war_with == civ2.name: continue
                
                relation = civ1.relationships.get(civ2.name, 0)
                
                if random.random() < 0.1:
                    if relation > 0.7:
                        self._form_alliance(civ1, civ2)
                    
                    elif relation < -0.5 and civ1.religion and civ2.religion:
                        religious_compat = civ1.religion.calculate_compatibility(civ2.religion)
                        if religious_compat < 0.1 and random.random() < 0.25:
                            self._declare_holy_war(civ1, civ2)
                        elif relation < -0.7:
                            self._declare_war(civ1, civ2)
                    
                    elif relation < -0.7:
                        self._declare_war(civ1, civ2)
                    elif relation > 0.3:
                        self._improve_relations(civ1, civ2)
                    elif relation < -0.3:
                        self._deteriorate_relations(civ1, civ2)
    
    def _update_relationship_drift(self, civ1, civ2):
        if civ1.name not in civ2.relationships:
             civ2.relationships[civ1.name] = random.uniform(-0.5, 0.5)
        if civ2.name not in civ1.relationships:
             civ1.relationships[civ2.name] = random.uniform(-0.5, 0.5)
             
        drift = random.uniform(-0.05, 0.05)
        
        if civ1.religion and civ2.religion:
            compatibility = civ1.religion.calculate_compatibility(civ2.religion)
            drift += (compatibility - 0.5) * 0.1
        
        cultural_similarity = civ1._calculate_cultural_similarity(civ2)
        drift += (cultural_similarity - 0.5) * 0.1
        
        # Get bonuses from BEST diplomat, not all
        dip1 = civ1.get_best_person_for_job("Diplomat")
        dip2 = civ2.get_best_person_for_job("Diplomat")
        if dip1: drift += dip1.get_profession_modifiers()["diplomacy_bonus"]
        if dip2: drift += dip2.get_profession_modifiers()["diplomacy_bonus"]
        
        civ1.relationships[civ2.name] = max(-1.0, min(1.0, civ1.relationships[civ2.name] + drift))
        civ2.relationships[civ1.name] = civ1.relationships[civ2.name]

    def _handle_wars(self):
        for civ in self.civilizations:
            if civ.war_with:
                enemy = self.get_civ_by_name(civ.war_with)
                if not enemy:
                    civ.war_with = None
                    continue
                    
                if random.random() < 0.3:
                    self._simulate_battle(civ, enemy)
                
                if random.random() < 0.2:
                    self._make_peace(civ, enemy)
    
    def _form_alliance(self, civ1, civ2):
        alliance_event = HistoryEvent(
            year=self.year,
            event_type="alliance_formed",
            civilization=civ1.name,
            details=f"{civ1.name} and {civ2.name} formed a defensive alliance",
            person_id=civ1.leader.id,
            other_civ=civ2.name,
            severity="major"
        )
        self.history_archive.record_event(alliance_event)
        
        civ1.relationships[civ2.name] = min(1.0, civ1.relationships.get(civ2.name, 0) + 0.2)
        civ2.relationships[civ1.name] = min(1.0, civ2.relationships.get(civ1.name, 0) + 0.2)
    
    def _declare_war(self, civ1, civ2):
        if civ1.war_with or civ2.war_with: return
        civ1.war_with = civ2.name
        civ2.war_with = civ1.name
        
        war_event = HistoryEvent(
            year=self.year,
            event_type="war_declared",
            civilization=civ1.name,
            details=f"{civ1.name} declared war on {civ2.name}",
            person_id=civ1.leader.id,
            other_civ=civ2.name,
            severity="major"
        )
        self.history_archive.record_event(war_event)
    
    def _declare_holy_war(self, civ1, civ2):
        if civ1.war_with or civ2.war_with: return
        civ1.war_with = civ2.name
        civ2.war_with = civ1.name
        
        war_event = HistoryEvent(
            year=self.year,
            event_type="holy_war_declaration",
            civilization=civ1.name,
            details=f"{civ1.name} declared a holy war on {civ2.name} over {civ1.religion.name}",
            person_id=civ1.leader.id,
            other_civ=civ2.name,
            severity="major"
        )
        self.history_archive.record_event(war_event)
        civ1.relationships[civ2.name] = -1.0
        civ2.relationships[civ1.name] = -1.0
    
    def _improve_relations(self, civ1, civ2):
        improvement_event = HistoryEvent(
            year=self.year,
            event_type="relations_improved",
            civilization=civ1.name,
            details=f"Relations improved between {civ1.name} and {civ2.name}",
            person_id=civ1.leader.id,
            other_civ=civ2.name,
            severity="normal"
        )
        self.history_archive.record_event(improvement_event)
        civ1.relationships[civ2.name] = min(1.0, civ1.relationships.get(civ2.name, 0) + 0.1)
        civ2.relationships[civ1.name] = min(1.0, civ2.relationships.get(civ1.name, 0) + 0.1)
    
    def _deteriorate_relations(self, civ1, civ2):
        deterioration_event = HistoryEvent(
            year=self.year,
            event_type="relations_worsened",
            civilization=civ1.name,
            details=f"Relations deteriorated between {civ1.name} and {civ2.name}",
            person_id=civ1.leader.id,
            other_civ=civ2.name,
            severity="normal"
        )
        self.history_archive.record_event(deterioration_event)
        civ1.relationships[civ2.name] = max(-1.0, civ1.relationships.get(civ2.name, 0) - 0.1)
        civ2.relationships[civ1.name] = max(-1.0, civ2.relationships.get(civ1.name, 0) - 0.1)
    
    def _simulate_battle(self, civ1, civ2):
        # Find best general for each side
        gen1 = civ1.get_best_person_for_job("General")
        gen2 = civ2.get_best_person_for_job("General")
        
        mods1 = civ1.culture_system.get_military_modifiers()
        mods2 = civ2.culture_system.get_military_modifiers()
        
        # Add general's bonus
        if gen1: mods1["war_power_bonus"] = gen1.get_profession_modifiers()["war_power_bonus"]
        if gen2: mods2["war_power_bonus"] = gen2.get_profession_modifiers()["war_power_bonus"]

        civ1_power = civ1.army_size * civ1.tech_level * (1 + mods1.get("morale_bonus", 0) + mods1.get("war_power_bonus", 0))
        civ2_power = civ2.army_size * civ2.tech_level * (1 + mods2.get("morale_bonus", 0) + mods2.get("war_power_bonus", 0))
        
        total_power = civ1_power + civ2_power
        if total_power == 0: return
        
        civ1_victory_chance = civ1_power / total_power
        
        if random.random() < civ1_victory_chance:
            winner, loser, gen_win, gen_lose = civ1, civ2, gen1, gen2
        else:
            winner, loser, gen_win, gen_lose = civ2, civ1, gen2, gen1
        
        winner_losses = int(winner.army_size * random.uniform(0.1, 0.3))
        loser_losses = int(loser.army_size * random.uniform(0.2, 0.5))
        
        winner.army_size = max(0, winner.army_size - winner_losses)
        loser.army_size = max(0, loser.army_size - loser_losses)
        
        winner.happiness += 5
        winner.stability += 5
        loser.happiness -= 15
        loser.stability -= 10
        
        # General gains fame
        battle_details = f"{winner.name} defeated {loser.name} in battle"
        person_id = winner.leader.id
        if gen_win:
            gen_win.add_fame(15, self, "a great victory")
            battle_details = f"{winner.name}, led by General {gen_win.name}, defeated {loser.name}"
            person_id = gen_win.id

        battle_event = HistoryEvent(
            year=self.year,
            event_type="battle",
            civilization=winner.name,
            details=f"{battle_details} ({winner_losses}/{loser_losses} losses)",
            person_id=person_id,
            other_civ=loser.name,
            severity="major"
        )
        self.history_archive.record_event(battle_event)
        
        if loser.army_size < loser.population * 0.01:
            self._make_peace(winner, loser)
    
    def _make_peace(self, civ1, civ2):
        if not civ1.war_with and not civ2.war_with: return
            
        civ1.war_with = None
        civ2.war_with = None
        civ1.peace_treaty_years = 5
        civ2.peace_treaty_years = 5
        
        peace_event = HistoryEvent(
            year=self.year,
            event_type="peace_treaty",
            civilization=civ1.name,
            details=f"{civ1.name} and {civ2.name} signed a peace treaty",
            person_id=civ1.leader.id,
            other_civ=civ2.name,
            severity="major"
        )
        self.history_archive.record_event(peace_event)
    
    def display_world_status(self):
        print(f"\n{'='*60}")
        print(f"WORLD STATUS - Year {self.year}")
        print(f"{'='*60}")
        print(f"Season: {self.climate.season}, Temp: {self.climate.temperature:.1f}C, Rain: {self.climate.rainfall:.1f}mm")
        
        total_pop = sum(civ.population for civ in self.civilizations)
        total_wealth = sum(civ.resources['wealth'] for civ in self.civilizations)
        active_wars = sum(1 for civ in self.civilizations if civ.war_with) // 2
        
        print(f"\nWorld Totals: Pop: {total_pop:,}, Wealth: {int(total_wealth):,}, Wars: {active_wars}")
        
        for civ in self.civilizations:
            civ.display_status()

    def display_recent_events(self, years=10):
        print(f"\n{'='*60}")
        print(f"RECENT WORLD EVENTS (Last {years} years)")
        print(f"{'='*60}")
        recent_events = self.history_archive.get_recent_events(years_back=years, current_year=self.year)
        if not recent_events:
            print("No significant events in this period.")
            return
        for event in recent_events:
            print(f"- {event}")
    
    def display_legends(self, view_type="world", target_civ=None, years=50, person_id=None):
        """Display legends view"""
        print(f"\n{'='*60}")
        print(f"LEGENDS MODE: {view_type.upper()} VIEW")
        print(f"{'='*60}")
        
        if view_type == "world":
            print(self.legends_mode.generate_world_chronicle(max(0, self.year - years), self.year))
        elif view_type == "civilization" and target_civ:
            print(self.legends_mode.generate_civilization_biography(target_civ, self.year))
        elif view_type == "story" and target_civ:
            print(self.legends_mode.generate_story_view(target_civ, max(0, self.year - years), self.year))
        elif view_type == "person" and person_id:
            print(self.legends_mode.generate_person_biography(person_id))
        else:
            print("Invalid legends view type or target.")
    
    def display_cultural_summary(self):
        print(f"\n{'='*60}")
        print(f"CULTURAL SUMMARY - YEAR {self.year}")
        print(f"{'='*60}")
        for civ in self.civilizations:
            culture = civ.culture_system.traits
            print(f"\n{civ.name} Culture:")
            print(f"  Tradition: {culture['tradition']:.2f} | Honor: {culture['honor']:.2f} | Militarism: {culture['militarism']:.2f}")
            print(f"  Artistry: {culture['artistry']}/100 | Spirituality: {culture['spirituality']}/100 | Cohesion: {int(culture['cohesion'])}/100")
            
            if civ.culture_system.artifacts:
                print(f"  Artifacts: {len(civ.culture_system.artifacts)}")
                for artifact in civ.culture_system.artifacts[-3:]:
                    print(f"    - {artifact['name']} ({artifact['year_created']})")
    
    def display_religious_summary(self):
        print(f"\n{'='*60}")
        print(f"RELIGIOUS SUMMARY - YEAR {self.year}")
        print(f"{'='*60}")
        
        if not self.religion_system.religions:
            print("No organized religions have formed.")
            return

        for religion in self.religion_system.religions:
            print(f"\n{religion.name} ({religion.doctrine_type})")
            print(f"  Founded: Year {religion.year_founded} by {religion.founding_civilization}")
            print(f"  Focus: {religion.moral_focus[0]} and {religion.moral_focus[1]}")
            print(f"  Followers ({len(religion.followers)}): {', '.join(religion.followers) if religion.followers else 'None'}")
    
    def display_individuals_summary(self, civ_name=None):
        """Display notable individuals"""
        print(f"\n{'='*60}")
        print(f"NOTABLE INDIVIDUALS - YEAR {self.year}")
        print(f"{'='*60}")
        
        civs_to_show = self.civilizations
        if civ_name:
            civ = self.get_civ_by_name(civ_name)
            if civ:
                civs_to_show = [civ]
            else:
                print(f"Civilization '{civ_name}' not found.")
                return
        
        for civ in civs_to_show:
            print(f"\n--- {civ.name} ---")
            print(f"RULER: {civ.leader.full_name} (Age: {civ.leader.age}, Fame: {civ.leader.fame})")
            
            professions = defaultdict(list)
            for p in civ.individuals:
                if p.alive and p.id != civ.leader.id:
                    professions[p.profession].append(p)
            
            for prof, people in professions.items():
                if prof == "Commoner": continue
                print(f"  {prof.upper()}S:")
                people.sort(key=lambda x: x.fame, reverse=True)
                for p in people[:3]: # Show top 3
                    stat_name = p.profession.lower()
                    if stat_name not in p.stats:
                        stat_name = "combat" # fallback
                    print(f"    - {p.full_name} (Age: {p.age}, Fame: {p.fame}, Stat: {p.stats[stat_name]})")
            
            heroes = [p for p in civ.individuals if p.is_hero and p.alive]
            if heroes:
                print(f"  HEROES:")
                for h in heroes:
                     print(f"    - {h.full_name} (Age: {h.age}, Fame: {h.fame}, {h.profession})")
                     
    def to_dict(self):
        """Convert world state to dictionary for saving"""
        return {
            'year': self.year,
            'map': self.map.to_dict(),
            'climate': self.climate.to_dict(),
            'all_people': {pid: p.to_dict() for pid, p in self.all_people.items()},
            'all_dynasties': {dname: d.to_dict() for dname, d in self.all_dynasties.items()},
            'civilizations': [civ.to_dict() for civ in self.civilizations],
            'history_archive': self.history_archive.to_dict(),
            'religion_system': self.religion_system.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create world from saved dictionary data"""
        seed = data['map']['seed']
        world = cls(
            num_civilizations=0, # Will be loaded
            width=data['map']['width'],
            height=data['map']['height'],
            seed=seed
        )
        
        world.year = data['year']
        world.map = WorldMap.from_dict(data['map'])
        world.climate = ClimateSystem.from_dict(data['climate'], rng=world.rng)
        
        # --- Reconstruct PA-11 Data ---
        # 1. Create all Person objects
        world.all_people = {pid: Person.from_dict(p_data, world) for pid, p_data in data['all_people'].items()}
        
        # 2. Create all Dynasty objects
        world.all_dynasties = {dname: Dynasty.from_dict(d_data, world) for dname, d_data in data['all_dynasties'].items()}
        
        # 3. Link Persons to their Dynasties
        for p in world.all_people.values():
            if hasattr(p, 'dynasty_name_to_load') and p.dynasty_name_to_load:
                dynasty = world.get_dynasty_by_name(p.dynasty_name_to_load)
                if dynasty:
                    p.dynasty = dynasty
                    # Ensure member list is correct
                    if p.id not in dynasty.members:
                        dynasty.members.append(p.id)
                del p.dynasty_name_to_load

        # 4. Reconstruct Systems
        world.history_archive = HistoryArchive.from_dict(data['history_archive'])
        world.legends_mode = LegendsMode(world.history_archive, world)
        world.religion_system = ReligionSystem.from_dict(data['religion_system'], world)
        
        # 5. Reconstruct Civilizations
        world.civilizations = [Civilization.from_dict(civ_data, world) for civ_data in data['civilizations']]
        
        # 6. Link Civs to their objects
        for civ in world.civilizations:
            # Link individuals
            civ.individuals = [world.get_person_by_id(pid) for pid in civ.loader_individual_ids if world.get_person_by_id(pid)]
            # Link dynasties
            civ.dynasties = [world.get_dynasty_by_name(dname) for dname in civ.loader_dynasty_names if world.get_dynasty_by_name(dname)]
            # Link leader
            civ.leader = world.get_person_by_id(civ.loader_leader_id)
            # Link leader history
            civ.leader_history = [world.get_person_by_id(pid) for pid in civ.loader_leader_history_ids if world.get_person_by_id(pid)]
            # Link religion
            if hasattr(civ, 'loader_religion_name') and civ.loader_religion_name:
                religion = world.religion_system.get_religion_by_name(civ.loader_religion_name)
                if religion:
                    civ.religion = religion
                    religion.add_follower(civ.name)
            
            # Clean up loader attributes
            del civ.loader_leader_id, civ.loader_leader_history_ids, civ.loader_dynasty_names, civ.loader_individual_ids, civ.loader_religion_name

        return world

"""
====================== 7. MAIN EXECUTION (INTERACTIVE) ======================
(Upgraded for PA-11: New menus for Individuals)
"""

def save_world(world, filename="world_save.json"):
    """Saves the entire world state to a JSON file"""
    try:
        with open(filename, 'w') as f:
            json.dump(world.to_dict(), f, indent=2)
        print(f"\n✅ World saved successfully to {filename}")
    except Exception as e:
        print(f"\n❌ Error saving world: {e}")
        import traceback
        traceback.print_exc()

def load_world(filename="world_save.json"):
    """Loads the entire world state from a JSON file"""
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        world = World.from_dict(data)
        print(f"\n✅ World loaded successfully from {filename}")
        print(f"Current Year: {world.year}")
        return world
    except FileNotFoundError:
        print(f"\n❌ Save file '{filename}' not found.")
        return None
    except Exception as e:
        print(f"\n❌ Error loading world: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("="*80)
    print("      FANTASY ENGINE - PRE-ALPHA 11: INDIVIDUALS & HEROES")
    print("="*80)
    
    world = None
    
    while not world:
        print("\n[1] Start a new world")
        print("[2] Load a saved world")
        print("[q] Quit")
        choice = input("Choose an option: ").strip().lower()

        if choice == '1':
            seed_input = input("Enter a seed number (or leave blank for random): ").strip()
            seed = int(seed_input) if seed_input.isdigit() else None
            
            try:
                num_civs = int(input("Number of civilizations (default 4): ").strip() or "4")
                width = int(input("Map width (default 30): ").strip() or "30")
                height = int(input("Map height (default 15): ").strip() or "15")
            except ValueError:
                print("Invalid input. Using defaults.")
                num_civs, width, height = 4, 30, 15

            print(f"\nGenerating new world... (Seed: {seed or 'Random'})")
            world = World(num_civilizations=num_civs, width=width, height=height, seed=seed)
            world.map.display(world.civilizations)
            world.display_world_status()

        elif choice == '2':
            filename = input("Enter save file name (default 'world_save.json'): ").strip() or "world_save.json"
            world = load_world(filename)
            if world:
                world.map.display(world.civilizations)
                world.display_world_status()

        elif choice == 'q':
            print("Goodbye!")
            return
        else:
            print("Invalid choice. Please try again.")
    
    # --- Main Game Loop ---
    try:
        while True:
            print("\n" + "="*80)
            cmd = input("Press Enter to advance 1 year, or type command:\n"
                        "[s] Save  |  [l] Load  |  [m] Map  |  [q] Quit\n"
                        "[v] Legends  |  [c] Culture  |  [r] Religion  |  [i] Individuals\n"
                        "Command: ").strip().lower()

            if cmd == 'q':
                print("Quitting simulation.")
                break
            
            elif cmd == 's':
                filename = input("Enter save file name (default 'world_save.json'): ").strip() or "world_save.json"
                save_world(world, filename)
            
            elif cmd == 'l':
                filename = input("Enter save file name to load (default 'world_save.json'): ").strip() or "world_save.json"
                loaded_world = load_world(filename)
                if loaded_world:
                    world = loaded_world
                world.map.display(world.civilizations)
                world.display_world_status()

            elif cmd == 'v':
                print("\n--- LEGENDS MODE ---")
                print("[1] World Chronicle (last 50 years)")
                print("[2] Civilization Biography")
                print("[3] Person Biography")
                view_choice = input("Choose view: ").strip()
                
                if view_choice == '1':
                    world.display_legends("world", years=50)
                elif view_choice == '2':
                    civ_name = input("Enter Civilization name: ").strip()
                    if world.get_civ_by_name(civ_name):
                        world.display_legends("civilization", civ_name)
                    else:
                        print(f"Civilization '{civ_name}' not found.")
                elif view_choice == '3':
                    person_name = input("Enter Person's name: ").strip()
                    # Find any person whose first name matches
                    person = next((p for p in world.all_people.values() if p.name.lower() == person_name.lower()), None)
                    if person:
                        world.display_legends("person", person_id=person.id)
                    else:
                        print(f"Person '{person_name}' not found.")
                else:
                    print("Invalid choice.")
            
            elif cmd == 'c':
                world.display_cultural_summary()
            
            elif cmd == 'r':
                world.display_religious_summary()

            elif cmd == 'i':
                civ_name = input("Enter Civilization name (or blank for all): ").strip()
                world.display_individuals_summary(civ_name if civ_name else None)

            elif cmd == 'm':
                world.map.display(world.civilizations)

            elif cmd == '':
                # --- Advance One Year ---
                print(f"\n--- Simulating Year {world.year + 1} ---")
                world.simulate_year()
                world.display_world_status()
                world.display_recent_events(years=1) # Show only this year's events
            
            else:
                print(f"Unknown command: '{cmd}'")

    except KeyboardInterrupt:
        print("\nSimulation ended by user.")
    except EOFError:
        print("\nInput ended. Simulation stopped.")
    except Exception as e:
        print(f"\n--- A CRITICAL ERROR OCCURRED ---")
        import traceback
        traceback.print_exc()
        print("Attempting to save world to 'crash_save.json'...")
        if world:
            save_world(world, "crash_save.json")
        print("Exiting.")

if __name__ == "__main__":
    main()