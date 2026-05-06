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

FIXED: Now fully deterministic - all random choices use the world's seeded RNG
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
    
    def __init__(self, rng=None):
        self.global_history = []  # All events across all civilizations
        self.event_index = {}     # Fast lookup by event type and civilization
        self.cause_effect_chains = []  # Linked event sequences
        self.last_major_events = {}    # Track recent major events for cause-effect
        self.rng = rng or random.Random()
        
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
    def from_dict(cls, data, rng=None):
        archive = cls(rng=rng)
        archive.global_history = [HistoryEvent.from_dict(event_data) for event_data in data['global_history']]
        archive.cause_effect_chains = data.get('cause_effect_chains', [])
        archive._rebuild_index()
        return archive

class LegendsMode:
    """Provides natural language storytelling and historical narratives"""
    
    def __init__(self, history_archive, world_ref, rng=None):
        self.archive = history_archive
        self.world = world_ref # Need world to look up person names from IDs
        self.rng = rng or random.Random()
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
        
        template = self.rng.choice(template_group)
        
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
    def __init__(self, name, founder, rng=None):
        self.name = name
        self.founder_id = founder.id
        self.members = [founder.id]
        self.prestige = 10 # Starting prestige
        self.rng = rng or random.Random()
    
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
    def from_dict(cls, data, world, rng=None):
        # Founder will be linked later
        founder = world.get_person_by_id(data['founder_id'])
        dynasty = cls(data['name'], founder, rng=rng)
        dynasty.members = data['members']
        dynasty.prestige = data['prestige']
        return dynasty

class Person:
    """Represents an individual in the world (replaces Leader class)"""
    
    PROFESSIONS = ["Ruler", "General", "Scholar", "Diplomat", "Treasurer", "Priest", "Noble", "Commoner"]
    
    def __init__(self, civ_name, birth_year, gender=None, dynasty=None, rng=None):
        self.rng = rng or random.Random()
        self.id = f"p_{birth_year}_{self.rng.randint(1000, 9999)}"
        self.alive = True
        self.civ_name = civ_name
        
        # Identity
        self.gender = gender if gender else self.rng.choice(["Male", "Female"])
        self.name = self.rng.choice(MALE_NAMES) if self.gender == "Male" else self.rng.choice(FEMALE_NAMES)
        self.surname = "the Commoner"
        self.dynasty = None
        if dynasty:
            dynasty.add_member(self)
        
        self.full_name = f"{self.name} {self.surname}"
        
        # Lifecycle
        self.birth_year = birth_year
        self.age = 0
        self.lifespan = self.rng.randint(50, 85)
        self.death_year = -1
        
        # Family
        self.mother_id = None
        self.father_id = None
        self.spouse_id = None
        self.children_ids = []
        
        # Role
        self.profession = "Commoner"
        self.traits = self.rng.sample(TRAITS, self.rng.randint(2, 4))
        self.stats = self._generate_stats()
        self.loyalty = self.rng.randint(30, 70) # Loyalty to the current ruler
        self.fame = 0
        self.is_hero = False
        
        # For rulers
        self.reign_start_year = -1
        self.major_achievements = []

    def _generate_stats(self):
        """Generate base stats, modified by traits"""
        stats = {
            "combat": self.rng.randint(1, 10),
            "diplomacy": self.rng.randint(1, 10),
            "stewardship": self.rng.randint(1, 10),
            "intrigue": self.rng.randint(1, 10),
            "learning": self.rng.randint(1, 10),
            "piety": self.rng.randint(1, 10)
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
        elif self.age > 40 and self.rng.random() < 0.02:
            death_chance = 0.02 # Chance of early death
        
        if self.rng.random() < death_chance:
            self.die(world, "natural causes")
            return

        # --- Adulthood & Profession ---
        if self.age == 16:
            if self.dynasty: # Nobles get professions
                self.profession = self.rng.choice(["General", "Diplomat", "Treasurer", "Priest", "Scholar", "Noble"])
            # Commoners stay commoners unless they become heroes
        
        # --- Marriage & Children (for nobles/rulers) ---
        if self.age > 18 and not self.spouse_id and self.dynasty and self.rng.random() < 0.1:
            self._find_spouse(world)
            
        if self.age > 20 and self.age < 45 and self.spouse_id and self.gender == "Female" and self.rng.random() < 0.15:
            self._have_child(world)
    
    def die(self, world, reason):
        """Mark the person as dead and log the event"""
        self.alive = False
        self.death_year = world.year
        
        # FIX: Include person's name in hero death description
        details = f"died at age {self.age} of {reason}"
        if self.is_hero:
            details = f"the hero {self.full_name}, died at age {self.age} of {reason}"
        
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
            spouse = self.rng.choice(candidates)
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
        child = Person(self.civ_name, world.year, dynasty=self.dynasty, rng=self.rng)
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
            mods["stability_bonus"] = self.stats["piety"] * 0.02
        elif self.profession == "Noble":
            mods["stability_bonus"] = 0.1 # Nobles provide stability
        
        return mods

    def add_fame(self, amount, world, reason=""):
        """Add fame and check for hero status"""
        old_fame = self.fame
        self.fame += amount
        
        if not self.is_hero and self.fame >= 50 and old_fame < 50:
            self.is_hero = True
            world.history_archive.record_event(HistoryEvent(
                year=world.year,
                event_type="hero_achievement",
                civilization=self.civ_name,
                details=f"became a hero through {reason}",
                person_id=self.id,
                severity="major"
            ))

    def to_dict(self):
        return {
            'id': self.id,
            'alive': self.alive,
            'civ_name': self.civ_name,
            'gender': self.gender,
            'name': self.name,
            'surname': self.surname,
            'full_name': self.full_name,
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
    def from_dict(cls, data, world, rng=None):
        person = cls(data['civ_name'], data['birth_year'], gender=data['gender'], rng=rng)
        person.id = data['id']
        person.alive = data['alive']
        person.name = data['name']
        person.surname = data['surname']
        person.full_name = data['full_name']
        person.age = data['age']
        person.lifespan = data['lifespan']
        person.death_year = data['death_year']
        person.mother_id = data['mother_id']
        person.father_id = data['father_id']
        person.spouse_id = data['spouse_id']
        person.children_ids = data['children_ids']
        person.profession = data['profession']
        person.traits = data['traits']
        person.stats = data['stats']
        person.loyalty = data['loyalty']
        person.fame = data['fame']
        person.is_hero = data['is_hero']
        person.reign_start_year = data['reign_start_year']
        person.major_achievements = data['major_achievements']
        return person

"""
====================== 3. CIVILIZATION & RELIGION ======================
"""

class Religion:
    """Represents a religion with beliefs and influence"""
    
    def __init__(self, name, civ_name, year_founded, rng=None):
        self.name = name
        self.civ_name = civ_name
        self.year_founded = year_founded
        self.founder_id = None
        self.beliefs = []
        self.influence = 1.0
        self.holy_sites = []
        self.rng = rng or random.Random()
        
        # Generate beliefs
        belief_options = ["Monotheism", "Polytheism", "Ancestor Worship", "Nature Worship",
                         "Sun Worship", "Moon Worship", "Animal Worship", "Spirit Worship",
                         "Proselytizing", "Isolationist", "Militant", "Pacifist"]
        self.beliefs = self.rng.sample(belief_options, self.rng.randint(2, 4))
    
    def to_dict(self):
        return {
            'name': self.name,
            'civ_name': self.civ_name,
            'year_founded': self.year_founded,
            'founder_id': self.founder_id,
            'beliefs': self.beliefs,
            'influence': self.influence,
            'holy_sites': self.holy_sites
        }
    
    @classmethod
    def from_dict(cls, data, rng=None):
        religion = cls(data['name'], data['civ_name'], data['year_founded'], rng=rng)
        religion.founder_id = data['founder_id']
        religion.beliefs = data['beliefs']
        religion.influence = data['influence']
        religion.holy_sites = data['holy_sites']
        return religion

class Civilization:
    """Represents a civilization with culture, technology, and now individuals"""
    
    def __init__(self, name, world_year, rng=None):
        self.rng = rng or random.Random()
        self.name = name
        self.year_founded = world_year
        self.leader_history = []  # List of Person IDs who have ruled
        self.dynasties = []       # List of Dynasty objects
        self.individuals = []     # List of Person objects in this civ
        self.religion = None
        self.culture = self._generate_culture()
        self.technology = self._initialize_technology()
        self.economy = self._initialize_economy()
        self.military = self._initialize_military()
        self.diplomacy = {}
        self.relations = {}
        self.stability = 75
        self.population = self.rng.randint(5000, 15000)
        self.territory = []
        self.known_civs = []
        
        # Create the founding leader
        founder = Person(name, world_year, dynasty=None, rng=self.rng)
        founder.profession = "Ruler"
        founder.reign_start_year = world_year
        
        # Create founding dynasty
        dynasty_name = self._generate_dynasty_name()
        dynasty = Dynasty(dynasty_name, founder, rng=self.rng)
        self.dynasties.append(dynasty)
        founder.surname = dynasty_name
        founder.full_name = f"{founder.name} {dynasty_name}"
        
        self.leader_history.append(founder)
        self.individuals.append(founder)
        
        # Create initial nobles
        for _ in range(self.rng.randint(3, 6)):
            noble = Person(name, world_year, dynasty=dynasty, rng=self.rng)
            noble.profession = self.rng.choice(["General", "Diplomat", "Treasurer", "Priest", "Scholar", "Noble"])
            self.individuals.append(noble)
        
        # Create initial commoners
        for _ in range(self.rng.randint(10, 20)):
            commoner = Person(name, world_year, rng=self.rng)
            self.individuals.append(commoner)
    
    def _generate_culture(self):
        culture_aspects = ["Honor", "Wealth", "Knowledge", "Strength", "Faith", "Freedom", "Tradition"]
        primary = self.rng.choice(culture_aspects)
        secondary = self.rng.choice([a for a in culture_aspects if a != primary])
        return {"primary": primary, "secondary": secondary}
    
    def _generate_dynasty_name(self):
        prefix = self.rng.choice(DYNASTY_PREFIXES)
        suffix = self.rng.choice(DYNASTY_SUFFIXES)
        return prefix + suffix
    
    def _initialize_technology(self):
        return {
            "agriculture": self.rng.randint(1, 3),
            "metalworking": self.rng.randint(1, 3),
            "writing": self.rng.randint(0, 2),
            "masonry": self.rng.randint(1, 3),
            "military_tactics": self.rng.randint(1, 3),
            "naval": self.rng.randint(0, 2),
            "trade": self.rng.randint(1, 3),
            "magic": 0  # Placeholder for future
        }
    
    def _initialize_economy(self):
        return {
            "food": self.rng.randint(50, 100),
            "gold": self.rng.randint(50, 100),
            "production": self.rng.randint(50, 100),
            "trade": self.rng.randint(20, 50)
        }
    
    def _initialize_military(self):
        return {
            "army_size": self.rng.randint(500, 1500),
            "navy_size": 0,
            "war_power": self.rng.randint(30, 70),
            "fortifications": self.rng.randint(10, 30)
        }
    
    def get_current_leader(self, world):
        """Get the current living leader Person object"""
        if not self.leader_history:
            return None
        current_leader_id = self.leader_history[-1]
        return world.get_person_by_id(current_leader_id)
    
    def update_year(self, world):
        """Update the civilization for one year"""
        current_leader = self.get_current_leader(world)
        
        # Update all individuals
        for person in self.individuals[:]:  # Use slice copy to avoid modification issues
            person.update_year(world)
            if not person.alive:
                self.individuals.remove(person)
        
        # Check for leader death and succession
        if current_leader and not current_leader.alive:
            self._handle_leader_succession(world)
            current_leader = self.get_current_leader(world) # Get new leader
        
        # Apply profession bonuses from living individuals
        self._apply_profession_bonuses(current_leader)
        
        # Update technology
        self._update_technology(world)
        
        # Update economy
        self._update_economy(world)
        
        # Update stability
        self._update_stability(world)
        
        # Update population
        self._update_population(world)
        
        # Update military
        self._update_military(world)
        
        # Update diplomacy
        self._update_diplomacy(world)
        
        # Random events
        self._random_events(world)
    
    def _handle_leader_succession(self, world):
        """Handle the death of a leader and succession"""
        old_leader = self.get_current_leader(world)
        if not old_leader:
            return
        
        # Find successor: prefer dynasty members, then most famous individual
        dynasty_members = [p for p in self.individuals if p.dynasty == old_leader.dynasty and p.alive and p != old_leader]
        famous_individuals = [p for p in self.individuals if p.alive and p.fame > 30 and p != old_leader]
        
        successor = None
        succession_type = "unknown"
        
        if dynasty_members:
            # Prefer children, then close relatives
            children = [p for p in dynasty_members if p.mother_id == old_leader.id or p.father_id == old_leader.id]
            if children:
                successor = max(children, key=lambda x: x.age) # Oldest child
                succession_type = "dynastic succession"
            else:
                successor = self.rng.choice(dynasty_members)
                succession_type = "dynastic succession (distant relative)"
        elif famous_individuals:
            successor = max(famous_individuals, key=lambda x: x.fame)
            succession_type = "usurpation by famous hero"
        elif self.individuals:
            successor = self.rng.choice([p for p in self.individuals if p.alive])
            succession_type = "emergency appointment"
        
        if successor:
            successor.profession = "Ruler"
            successor.reign_start_year = world.year
            self.leader_history.append(successor)
            
            world.history_archive.record_event(HistoryEvent(
                year=world.year,
                event_type="succession",
                civilization=self.name,
                details=f"{successor.full_name} became ruler through {succession_type}",
                person_id=successor.id,
                severity="major",
                caused_by=old_leader.id
            ))
            
            # Add fame for becoming ruler
            successor.add_fame(20, world, "becoming ruler")
        else:
            # No successor - civilization collapses
            world.history_archive.record_event(HistoryEvent(
                year=world.year,
                event_type="civil_war",
                civilization=self.name,
                details="civil war erupted after the death of the ruler with no clear successor",
                severity="catastrophic"
            ))
            self.stability -= 50
    
    def _apply_profession_bonuses(self, current_leader):
        """Apply bonuses from all individuals' professions"""
        # Reset bonuses
        self.tech_bonus = 0
        self.war_power_bonus = 0
        self.diplomacy_bonus = 0
        self.trade_bonus = 0
        self.religion_spread_bonus = 0
        self.stability_bonus = 0
        
        # Sum bonuses from all living individuals
        for person in self.individuals:
            if person.alive:
                mods = person.get_profession_modifiers()
                for bonus_type, value in mods.items():
                    if bonus_type == "tech_bonus":
                        self.tech_bonus += value
                    elif bonus_type == "war_power_bonus":
                        self.war_power_bonus += value
                    elif bonus_type == "diplomacy_bonus":
                        self.diplomacy_bonus += value
                    elif bonus_type == "trade_bonus":
                        self.trade_bonus += value
                    elif bonus_type == "religion_spread_bonus":
                        self.religion_spread_bonus += value
                    elif bonus_type == "stability_bonus":
                        self.stability_bonus += value
        
        # Leader gets double effect
        if current_leader:
            leader_mods = current_leader.get_profession_modifiers()
            for bonus_type, value in leader_mods.items():
                if bonus_type == "tech_bonus":
                    self.tech_bonus += value
                elif bonus_type == "war_power_bonus":
                    self.war_power_bonus += value
                elif bonus_type == "diplomacy_bonus":
                    self.diplomacy_bonus += value
                elif bonus_type == "trade_bonus":
                    self.trade_bonus += value
                elif bonus_type == "religion_spread_bonus":
                    self.religion_spread_bonus += value
                elif bonus_type == "stability_bonus":
                    self.stability_bonus += value
    
    def _update_technology(self, world):
        """Update technology levels with bonuses from scholars"""
        base_research = 1.0
        research_points = base_research + self.tech_bonus
        
        # Distribute research randomly
        for tech in self.technology:
            if self.rng.random() < 0.3:  # 30% chance per tech per year
                self.technology[tech] += research_points * self.rng.uniform(0.1, 0.3)
        
        # Check for technological breakthroughs
        for tech, level in self.technology.items():
            if level >= 5 and level - research_points * 0.2 < 5:
                world.history_archive.record_event(HistoryEvent(
                    year=world.year,
                    event_type="technology_breakthrough",
                    civilization=self.name,
                    details=f"made a breakthrough in {tech.replace('_', ' ')}",
                    severity="major"
                ))
                
                # Grant fame to scholars
                scholars = [p for p in self.individuals if p.profession == "Scholar" and p.alive]
                for scholar in scholars:
                    scholar.add_fame(10, world, f"breakthrough in {tech}")
    
    def _update_economy(self, world):
        """Update the economy with trade bonuses"""
        # Base production
        self.economy["food"] += self.technology["agriculture"] * 10
        self.economy["gold"] += self.technology["trade"] * 5
        self.economy["production"] += self.technology["metalworking"] * 5
        
        # Apply trade bonus
        trade_gain = self.economy["trade"] * (1.0 + self.trade_bonus)
        self.economy["gold"] += trade_gain
        
        # Random economic events
        if self.rng.random() < 0.05:
            if self.rng.random() < 0.5:
                # Economic boom
                boom_amount = self.rng.randint(20, 50)
                self.economy["gold"] += boom_amount
                world.history_archive.record_event(HistoryEvent(
                    year=world.year,
                    event_type="economic_boom",
                    civilization=self.name,
                    details=f"experienced an economic boom, gaining {boom_amount} gold",
                    severity="normal"
                ))
            else:
                # Economic crisis
                crisis_amount = self.rng.randint(10, 30)
                self.economy["gold"] = max(0, self.economy["gold"] - crisis_amount)
                world.history_archive.record_event(HistoryEvent(
                    year=world.year,
                    event_type="economic_crisis",
                    civilization=self.name,
                    details=f"suffered an economic crisis, losing {crisis_amount} gold",
                    severity="normal"
                ))
    
    def _update_stability(self, world):
        """Update stability with bonuses from rulers and priests"""
        # Base stability change
        change = 0
        
        # Effects from economy
        if self.economy["food"] < 20:
            change -= 10
        elif self.economy["food"] > 80:
            change += 5
            
        if self.economy["gold"] < 20:
            change -= 5
        elif self.economy["gold"] > 80:
            change += 3
        
        # Apply stability bonus from professions
        change += self.stability_bonus * 100  # Convert to percentage points
        
        # Random events
        if self.rng.random() < 0.1:
            event_change = self.rng.randint(-15, 15)
            change += event_change
        
        # Update stability
        self.stability = max(0, min(100, self.stability + change))
        
        # Record major stability events
        if change < -20:
            world.history_archive.record_event(HistoryEvent(
                year=world.year,
                event_type="rebellion",
                civilization=self.name,
                details="faced rebellion due to instability",
                severity="major"
            ))
        elif change > 20:
            world.history_archive.record_event(HistoryEvent(
                year=world.year,
                event_type="golden_age",
                civilization=self.name,
                details="entered a golden age of stability and prosperity",
                severity="major"
            ))
    
    def _update_population(self, world):
        """Update population with growth and checks"""
        growth_rate = 0.01  # 1% base growth
        
        # Modify based on food
        if self.economy["food"] > 50:
            growth_rate += 0.005
        elif self.economy["food"] < 20:
            growth_rate -= 0.01
        
        # Modify based on stability
        if self.stability > 70:
            growth_rate += 0.005
        elif self.stability < 30:
            growth_rate -= 0.01
        
        # Apply growth
        self.population = int(self.population * (1 + growth_rate))
        
        # Record population events
        if growth_rate > 0.02:
            world.history_archive.record_event(HistoryEvent(
                year=world.year,
                event_type="population_boom",
                civilization=self.name,
                details=f"experienced rapid population growth to {self.population} people",
                severity="normal"
            ))
        elif growth_rate < -0.01:
            world.history_archive.record_event(HistoryEvent(
                year=world.year,
                event_type="population_collapse",
                civilization=self.name,
                details=f"suffered population decline to {self.population} people",
                severity="major"
            ))
    
    def _update_military(self, world):
        """Update military with war power bonuses"""
        # Base military maintenance
        self.military["army_size"] = int(self.population * 0.1)  # 10% of population as army
        
        # Apply war power bonus
        self.military["war_power"] = min(100, self.military["war_power"] + self.war_power_bonus)
        
        # Random military events
        if self.rng.random() < 0.08:
            general = next((p for p in self.individuals if p.profession == "General" and p.alive), None)
            if general:
                general.add_fame(5, world, "military victory")
                world.history_archive.record_event(HistoryEvent(
                    year=world.year,
                    event_type="war_victory",
                    civilization=self.name,
                    details=f"won a battle under General {general.name}",
                    person_id=general.id,
                    severity="normal"
                ))
    
    def _update_diplomacy(self, world):
        """Update diplomatic relations with diplomacy bonuses"""
        # Apply diplomacy bonus to all relations
        relation_change = self.diplomacy_bonus * 10
        
        for civ_name in self.relations:
            self.relations[civ_name] = max(-100, min(100, self.relations[civ_name] + relation_change))
            
            # Random diplomatic events
            if self.rng.random() < 0.05:
                if self.relations[civ_name] > 50:
                    world.history_archive.record_event(HistoryEvent(
                        year=world.year,
                        event_type="diplomatic_alliance",
                        civilization=self.name,
                        details=f"strengthened alliance with {civ_name}",
                        other_civ=civ_name,
                        severity="normal"
                    ))
                elif self.relations[civ_name] < -50:
                    world.history_archive.record_event(HistoryEvent(
                        year=world.year,
                        event_type="war_declaration",
                        civilization=self.name,
                        details=f"declared war on {civ_name}",
                        other_civ=civ_name,
                        severity="major"
                    ))
    
    def _random_events(self, world):
        """Handle random yearly events"""
        if not self.religion and self.rng.random() < 0.1:
            self._found_religion(world)
        
        elif self.religion and self.rng.random() < 0.05:
            self._religious_event(world)
        
        # Cultural events
        if self.rng.random() < 0.08:
            artist = next((p for p in self.individuals if p.profession in ["Scholar", "Priest"] and p.alive), None)
            if artist:
                artist.add_fame(5, world, "cultural achievement")
                world.history_archive.record_event(HistoryEvent(
                    year=world.year,
                    event_type="cultural_artifact",
                    civilization=self.name,
                    details=f"created a great work of art",
                    person_id=artist.id,
                    severity="normal"
                ))
    
    def _found_religion(self, world):
        """Found a new religion for this civilization"""
        religion_names = ["Path of Light", "Circle of Stone", "Eternal Flame", "Voice of Wind",
                         "Order of the Sky", "Cult of the Earth", "Way of Balance", "Sect of Stars"]
        religion_name = self.rng.choice(religion_names)
        
        self.religion = Religion(religion_name, self.name, world.year, rng=self.rng)
        
        # Assign founder (prefer a priest or scholar)
        founder = next((p for p in self.individuals if p.profession in ["Priest", "Scholar"] and p.alive), None)
        if not founder:
            founder = self.rng.choice([p for p in self.individuals if p.alive])
        
        self.religion.founder_id = founder.id
        founder.add_fame(25, world, "founding a religion")
        
        world.history_archive.record_event(HistoryEvent(
            year=world.year,
            event_type="religion_founded",
            civilization=self.name,
            details=f"founded the {religion_name} religion",
            person_id=founder.id,
            severity="major"
        ))
    
    def _religious_event(self, world):
        """Handle religious events"""
        event_type = self.rng.choice(["schism", "reformation", "pilgrimage"])
        
        if event_type == "schism":
            new_religion_name = f"New {self.religion.name}"
            world.history_archive.record_event(HistoryEvent(
                year=world.year,
                event_type="religious_schism",
                civilization=self.name,
                details=f"the {self.religion.name} split, forming the {new_religion_name}",
                severity="major"
            ))
        elif event_type == "reformation":
            world.history_archive.record_event(HistoryEvent(
                year=world.year,
                event_type="religious_reformation",
                civilization=self.name,
                details=f"the {self.religion.name} underwent major reforms",
                severity="normal"
            ))
        elif event_type == "pilgrimage":
            pilgrim = self.rng.choice([p for p in self.individuals if p.alive])
            pilgrim.add_fame(5, world, "religious pilgrimage")
            world.history_archive.record_event(HistoryEvent(
                year=world.year,
                event_type="pilgrimage",
                civilization=self.name,
                details=f"made a pilgrimage to a holy site",
                person_id=pilgrim.id,
                severity="normal"
            ))
    
    def to_dict(self):
        return {
            'name': self.name,
            'year_founded': self.year_founded,
            'leader_history': [p.id for p in self.leader_history],
            'dynasties': [dynasty.to_dict() for dynasty in self.dynasties],
            'individuals': [person.to_dict() for person in self.individuals],
            'religion': self.religion.to_dict() if self.religion else None,
            'culture': self.culture,
            'technology': self.technology,
            'economy': self.economy,
            'military': self.military,
            'diplomacy': self.diplomacy,
            'relations': self.relations,
            'stability': self.stability,
            'population': self.population,
            'territory': self.territory,
            'known_civs': self.known_civs
        }
    
    @classmethod
    def from_dict(cls, data, world, rng=None):
        civ = cls(data['name'], data['year_founded'], rng=rng)
        civ.leader_history = data['leader_history']  # Will be linked later
        civ.dynasties = [Dynasty.from_dict(d, world, rng=rng) for d in data['dynasties']]
        civ.individuals = [Person.from_dict(p, world, rng=rng) for p in data['individuals']]
        civ.religion = Religion.from_dict(data['religion'], rng=rng) if data['religion'] else None
        civ.culture = data['culture']
        civ.technology = data['technology']
        civ.economy = data['economy']
        civ.military = data['military']
        civ.diplomacy = data['diplomacy']
        civ.relations = data['relations']
        civ.stability = data['stability']
        civ.population = data['population']
        civ.territory = data['territory']
        civ.known_civs = data['known_civs']
        return civ

"""
====================== 4. WORLD & MAP ======================
"""

class World:
    """Main world class that contains all civilizations and manages the simulation"""
    
    def __init__(self, seed=None, num_civs=4):
        # Use provided seed or generate one
        self.seed = seed if seed is not None else random.randint(1, 10000)
        self.rng = random.Random(self.seed)
        
        self.year = 0
        self.civilizations = []
        self.all_people = {}  # All Person objects by ID
        self.history_archive = HistoryArchive(rng=self.rng)
        self.legends_mode = LegendsMode(self.history_archive, self, rng=self.rng)
        
        # Generate civilizations with seeded RNG
        civ_names = ["Sylgard", "Quor-Thal", "Arador", "Zanthar"]
        for name in civ_names[:num_civs]:
            civ = Civilization(name, self.year, rng=self.rng)
            self.civilizations.append(civ)
            
            # Record foundation event
            self.history_archive.record_event(HistoryEvent(
                year=self.year,
                event_type="foundation",
                civilization=name,
                details=f"was founded in the early ages",
                severity="major"
            ))
        
        # Initialize all_people dictionary
        self._rebuild_people_index()
        
        # Initialize diplomacy
        self._initialize_diplomacy()
    
    def _rebuild_people_index(self):
        """Rebuild the all_people index from civilization individuals"""
        self.all_people = {}
        for civ in self.civilizations:
            for person in civ.individuals:
                self.all_people[person.id] = person
    
    def _initialize_diplomacy(self):
        """Initialize diplomatic relations between civilizations"""
        for civ in self.civilizations:
            for other_civ in self.civilizations:
                if civ.name != other_civ.name:
                    civ.relations[other_civ.name] = self.rng.randint(-30, 30)
                    civ.known_civs.append(other_civ.name)
    
    def update_year(self):
        """Update the world for one year"""
        self.year += 1
        
        # Update each civilization
        for civ in self.civilizations:
            civ.update_year(self)
        
        # Rebuild people index in case individuals were added/removed
        self._rebuild_people_index()
        
        # Record annual summary every 10 years
        if self.year % 10 == 0:
            self.history_archive.record_event(HistoryEvent(
                year=self.year,
                event_type="annual_summary",
                civilization="World",
                details=f"Year {self.year} - The world continues to turn...",
                severity="minor"
            ))
    
    def get_civ_by_name(self, name):
        """Get civilization by name"""
        for civ in self.civilizations:
            if civ.name == name:
                return civ
        return None
    
    def get_person_by_id(self, person_id):
        """Get person by ID"""
        return self.all_people.get(person_id)
    
    def simulate(self, years=100, save_interval=10):
        """Run the simulation for the specified number of years"""
        print(f"Starting simulation for {years} years (Seed: {self.seed})...")
        
        for year in range(years):
            self.update_year()
            
            if (year + 1) % save_interval == 0:
                print(f"Year {self.year}: {len(self.civilizations)} civilizations, {len(self.all_people)} individuals")
        
        print(f"Simulation complete! Final year: {self.year}")
    
    def to_dict(self):
        """Convert world state to dictionary for saving"""
        return {
            'seed': self.seed,
            'year': self.year,
            'civilizations': [civ.to_dict() for civ in self.civilizations],
            'history_archive': self.history_archive.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data):
        """Load world state from dictionary"""
        world = cls(seed=data['seed'], num_civs=0)
        world.year = data['year']
        
        # Recreate civilizations with seeded RNG
        world.civilizations = [Civilization.from_dict(civ_data, world, rng=world.rng) 
                              for civ_data in data['civilizations']]
        
        # Rebuild people index
        world._rebuild_people_index()
        
        # Restore history archive
        world.history_archive = HistoryArchive.from_dict(data['history_archive'], rng=world.rng)
        world.legends_mode = LegendsMode(world.history_archive, world, rng=world.rng)
        
        return world

"""
====================== 5. MAIN SIMULATION & TESTING ======================
"""

def run_simulation(seed=4242, years=100):
    """Run a complete simulation with the given seed"""
    print("=" * 60)
    print(f"FANTASY ENGINE - PRE-ALPHA 11: INDIVIDUALS & HEROES")
    print(f"SEED: {seed}, YEARS: {years}")
    print("=" * 60)
    
    start_time = time.time()
    
    # Create and run the world
    world = World(seed=seed, num_civs=4)
    world.simulate(years=years)
    
    end_time = time.time()
    
    print(f"\nSimulation completed in {end_time - start_time:.2f} seconds")
    
    # Generate some reports
    print("\n" + "=" * 40)
    print("LEGENDS MODE - CIVILIZATION BIOGRAPHIES")
    print("=" * 40)
    
    for civ in world.civilizations:
        print(f"\n{world.legends_mode.generate_civilization_biography(civ.name, world.year)}")
    
    print("\n" + "=" * 40)
    print("HERES & NOTABLE INDIVIDUALS")
    print("=" * 40)
    
    heroes = []
    for person in world.all_people.values():
        if person.is_hero:
            heroes.append(person)
    
    if heroes:
        for hero in heroes[-10:]:  # Last 10 heroes
            print(f"- {hero.full_name} ({hero.profession}), Fame: {hero.fame}")
    else:
        print("No heroes emerged in this age.")
    
    print("\n" + "=" * 40)
    print("DYNASTIC HISTORY")
    print("=" * 40)
    
    for civ in world.civilizations:
        print(f"\n{civ.name}:")
        for dynasty in civ.dynasties:
            living_members = [m for m in dynasty.members if world.get_person_by_id(m).alive]
            print(f"  {dynasty.name}: Prestige {dynasty.prestige}, {len(living_members)} living members")
    
    return world

if __name__ == "__main__":
    # Run the simulation
    world = run_simulation(seed=4242, years=100)
    
    # Save the world state
    with open("world_save.json", "w") as f:
        json.dump(world.to_dict(), f, indent=2)
    
    print("\nWorld state saved to 'world_save.json'")