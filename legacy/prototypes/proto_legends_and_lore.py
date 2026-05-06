import random
import time
from datetime import datetime
import os
import math
import json
from collections import defaultdict

"""
====================== DEEP HISTORY & LEGENDS SYSTEM ======================
"""

class HistoryEvent:
    """Represents a structured historical event with metadata"""
    
    EVENT_TYPES = {
        "leader_death": "Leader Death",
        "leader_succession": "Leadership Change", 
        "war_declaration": "War Declaration",
        "war_victory": "War Victory",
        "war_defeat": "War Defeat",
        "famine": "Famine",
        "golden_age": "Golden Age",
        "cultural_boom": "Cultural Renaissance",
        "civil_war": "Civil War",
        "rebellion": "Rebellion",
        "economic_boom": "Economic Boom",
        "economic_crisis": "Economic Crisis",
        "diplomatic_alliance": "Alliance Formed",
        "diplomatic_trade": "Trade Pact",
        "diplomatic_peace": "Peace Treaty",
        "technology_breakthrough": "Technology Advance",
        "population_boom": "Population Growth",
        "population_collapse": "Population Decline",
        "natural_disaster": "Natural Disaster",
        "foundation": "Civilization Founded"
    }
    
    def __init__(self, year, event_type, civilization, details, 
                 leader=None, other_civ=None, severity="normal", caused_by=None):
        self.year = year
        self.event_type = event_type
        self.civilization = civilization
        self.details = details
        self.leader = leader
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
            'leader': self.leader,
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
            leader=data['leader'],
            other_civ=data['other_civilization'],
            severity=data['severity'],
            caused_by=data['caused_by']
        )
        event.id = data['id']
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
        
        # Keep history manageable (optional: could implement archiving for very long games)
        if len(self.global_history) > 10000:
            self._archive_old_events()
    
    def _auto_link_cause_effect(self, new_event):
        """Automatically link events that are likely cause-effect pairs"""
        
        # Famine often leads to war or rebellion
        if new_event.event_type in ["war_declaration", "rebellion", "civil_war"]:
            # Check if this civ recently had a famine
            last_famine = self.get_recent_events(
                civilization=new_event.civilization,
                event_type="famine",
                years_back=10
            )
            if last_famine:
                new_event.caused_by = last_famine[0].id
                self.cause_effect_chains.append((last_famine[0].id, new_event.id))
        
        # War victories often lead to golden ages
        elif new_event.event_type == "golden_age":
            recent_wars = self.get_recent_events(
                civilization=new_event.civilization,
                event_type="war_victory", 
                years_back=20
            )
            if recent_wars:
                new_event.caused_by = recent_wars[0].id
                self.cause_effect_chains.append((recent_wars[0].id, new_event.id))
        
        # Economic crises can lead to leadership changes
        elif new_event.event_type == "leader_succession":
            recent_crisis = self.get_recent_events(
                civilization=new_event.civilization,
                event_type="economic_crisis",
                years_back=5
            )
            if recent_crisis:
                new_event.caused_by = recent_crisis[0].id
                self.cause_effect_chains.append((recent_crisis[0].id, new_event.id))
    
    def _archive_old_events(self):
        """Move old events to secondary storage to manage memory"""
        # For now, just keep the most recent 5000 events
        if len(self.global_history) > 5000:
            self.global_history = self.global_history[-5000:]
            # Rebuild index
            self._rebuild_index()
    
    def _rebuild_index(self):
        """Rebuild the event index after archiving"""
        self.event_index = {}
        for event in self.global_history:
            if event.event_type not in self.event_index:
                self.event_index[event.event_type] = []
            self.event_index[event.event_type].append(event)
    
    def get_events(self, civilization=None, event_type=None, start_year=None, 
                  end_year=None, leader=None, severity=None):
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
            if leader and event.leader != leader:
                continue
            if severity and event.severity != severity:
                continue
                
            results.append(event)
        
        return sorted(results, key=lambda x: x.year)
    
    def get_recent_events(self, civilization=None, event_type=None, years_back=10, current_year=None):
        """Get events from recent years"""
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
        """Get all events linked to a starting event"""
        chain = []
        current_id = start_event_id
        
        # Find starting event
        start_event = next((e for e in self.global_history if e.id == start_event_id), None)
        if not start_event:
            return chain
            
        chain.append(start_event)
        
        # Follow cause-effect links
        while current_id:
            next_event = next((e for e in self.global_history if e.caused_by == current_id), None)
            if next_event:
                chain.append(next_event)
                current_id = next_event.id
            else:
                current_id = None
                
        return chain
    
    def get_civilization_timeline(self, civilization, start_year=None, end_year=None):
        """Get complete timeline for a civilization"""
        return self.get_events(civilization=civilization, start_year=start_year, end_year=end_year)
    
    def get_world_era_summary(self, start_year, end_year):
        """Generate a summary of a historical era"""
        era_events = self.get_events(start_year=start_year, end_year=end_year)
        
        if not era_events:
            return f"Years {start_year}-{end_year}: The Silent Age - No significant events recorded."
        
        # Count event types
        event_counts = {}
        for event in era_events:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
        
        # Find most significant events
        major_events = [e for e in era_events if e.severity in ["major", "catastrophic"]]
        
        # Build summary
        summary_parts = [f"Years {start_year}-{end_year}:"]
        
        # Add event counts
        if event_counts.get("war_declaration", 0) > 0:
            summary_parts.append(f"{event_counts['war_declaration']} wars")
        if event_counts.get("golden_age", 0) > 0:
            summary_parts.append(f"{event_counts['golden_age']} golden ages")
        if event_counts.get("famine", 0) > 0:
            summary_parts.append(f"{event_counts['famine']} famines")
        
        # Add most significant event
        if major_events:
            most_significant = max(major_events, key=lambda x: 1 if x.severity == "catastrophic" else 0)
            summary_parts.append(f"Notably: {most_significant.details}")
        
        return " ".join(summary_parts)
    
    def to_dict(self):
        """Convert entire archive to serializable format"""
        return {
            'global_history': [event.to_dict() for event in self.global_history],
            'cause_effect_chains': self.cause_effect_chains
        }
    
    @classmethod
    def from_dict(cls, data):
        """Reconstruct archive from saved data"""
        archive = cls()
        archive.global_history = [HistoryEvent.from_dict(event_data) for event_data in data['global_history']]
        archive.cause_effect_chains = data['cause_effect_chains']
        archive._rebuild_index()
        return archive

class LegendsMode:
    """Provides natural language storytelling and historical narratives"""
    
    def __init__(self, history_archive):
        self.archive = history_archive
        self.story_templates = self._initialize_story_templates()
    
    def _initialize_story_templates(self):
        """Initialize natural language templates for different event types"""
        return {
            "leader_death": [
                "In Year {year}, {leader} of {civ} passed away {details}.",
                "The reign of {leader} over {civ} ended in Year {year} {details}.",
                "{civ} mourned the loss of {leader} in Year {year} {details}."
            ],
            "war_declaration": [
                "War erupted in Year {year} when {civ} declared war on {other_civ}.",
                "The {year} conflict began as {civ} launched attacks against {other_civ}.",
                "Hostilities commenced in Year {year} between {civ} and {other_civ}."
            ],
            "war_victory": [
                "In a decisive victory in Year {year}, {civ} triumphed over {other_civ}.",
                "{civ} achieved military glory in Year {year} by defeating {other_civ}.",
                "The war concluded in Year {year} with {civ} emerging victorious over {other_civ}."
            ],
            "famine": [
                "A great famine struck {civ} in Year {year}, {details}",
                "The people of {civ} suffered through famine in Year {year}, {details}",
                "Food shortages plagued {civ} in Year {year}, {details}"
            ],
            "golden_age": [
                "{civ} entered a glorious golden age in Year {year}, {details}",
                "A period of unprecedented prosperity began for {civ} in Year {year}, {details}",
                "Year {year} marked the start of {civ}'s golden age, {details}"
            ],
            "cultural_boom": [
                "{civ} experienced a cultural renaissance in Year {year}, {details}",
                "The arts and sciences flourished in {civ} during Year {year}, {details}",
                "A cultural boom transformed {civ} society in Year {year}, {details}"
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
        
        # Limit events for readability
        events = events[-max_events:] if len(events) > max_events else events
        
        if not events:
            return "No significant events recorded in this period."
        
        story = []
        current_era = None
        
        for event in events:
            # Add era markers for large gaps
            if current_era is None or event.year - current_era > 50:
                if current_era is not None:
                    story.append(f"\n--- The following years saw relative quiet ---\n")
                current_era = event.year
            
            # Generate natural language for this event
            event_story = self._event_to_story(event)
            story.append(event_story)
        
        return "\n".join(story)
    
    def _event_to_story(self, event):
        """Convert a single event to natural language"""
        template_group = self.story_templates.get(event.event_type)
        if not template_group:
            # Default template for unmapped events
            return f"Year {event.year}: {event.details}"
        
        template = random.choice(template_group)
        
        # Fill template variables
        story = template.format(
            year=event.year,
            civ=event.civilization,
            leader=event.leader or "the ruler",
            other_civ=event.other_civilization or "their neighbors",
            details=event.details.lower()
        )
        
        # Add cause-effect context if available
        if event.caused_by:
            cause_event = next((e for e in self.archive.global_history if e.id == event.caused_by), None)
            if cause_event:
                cause_story = self._event_to_story(cause_event).split(': ')[-1]
                story += f" This was sparked by {cause_story.lower()}"
        
        return story
    
    def generate_civilization_biography(self, civilization, current_year):
        """Generate a comprehensive biography of a civilization"""
        all_events = self.archive.get_civilization_timeline(civilization)
        
        if not all_events:
            return f"Little is known about the early history of {civilization}."
        
        # Find key milestones
        founding = next((e for e in all_events if e.event_type == "foundation"), None)
        golden_ages = self.archive.get_events(civilization=civilization, event_type="golden_age")
        major_wars = [e for e in all_events if e.event_type in ["war_declaration", "war_victory", "war_defeat"]]
        leaders = set(e.leader for e in all_events if e.leader)
        
        biography = [f"# The Chronicle of {civilization}\n"]
        
        # Founding
        if founding:
            biography.append(f"{civilization} was founded in Year {founding.year}. {founding.details}\n")
        else:
            biography.append(f"The origins of {civilization} are lost to time, but their history is recorded from Year {all_events[0].year}.\n")
        
        # Golden Ages
        if golden_ages:
            biography.append(f"## Ages of Glory")
            for age in golden_ages[-3:]:  # Last 3 golden ages
                biography.append(f"- {self._event_to_story(age)}")
            biography.append("")
        
        # Military History
        if major_wars:
            biography.append(f"## Trials of War")
            recent_wars = major_wars[-5:]  # Last 5 major wars
            for war in recent_wars:
                biography.append(f"- {self._event_to_story(war)}")
            biography.append("")
        
        # Leadership
        if leaders:
            biography.append(f"## Ruling Dynasties")
            leader_list = list(leaders)[-8:]  # Last 8 leaders
            biography.append(f"The civilization has been ruled by {', '.join(leader_list)}.")
            biography.append("")
        
        # Recent History
        recent_events = self.archive.get_recent_events(civilization=civilization, years_back=20, current_year=current_year)
        if recent_events:
            biography.append(f"## Recent Times")
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
        
        # Group by civilization
        civ_events = {}
        for event in era_events:
            if event.civilization not in civ_events:
                civ_events[event.civilization] = []
            civ_events[event.civilization].append(event)
        
        chronicle = [f"# World Chronicle: Years {start_year}-{end_year}\n"]
        
        for civ, events in civ_events.items():
            chronicle.append(f"## {civ}")
            for event in events:
                chronicle.append(f"- {self._event_to_story(event)}")
            chronicle.append("")
        
        return "\n".join(chronicle)

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
        
        # LEADER SYSTEM INTEGRATION
        self.leader = Leader()
        self.leader_history = [self.leader]
        
        # HISTORY SYSTEM INTEGRATION
        self.history = []  # Now stores HistoryEvent objects
        
        # Initialize society distribution
        self._distribute_population()
        
        # Record founding event
        self._record_founding_event()
    
    def _record_founding_event(self):
        """Record the civilization's founding in history"""
        founding_event = HistoryEvent(
            year=self.world.year,
            event_type="foundation",
            civilization=self.name,
            details=f"{self.name} was founded under {self.leader.full_title}",
            leader=self.leader.full_title,
            severity="major"
        )
        self.history.append(founding_event)
        self.world.history_archive.record_event(founding_event)
    
    def generate_name(self):
        """Generate a culturally appropriate civilization name"""
        prefixes = ["North", "South", "East", "West", "New", "Great", "Free"]
        suffixes = ["land", "ia", "dom", "nia", "stan", "burg", "wood", "shire"]
        roots = ["Avalon", "Eldor", "Camelot", "Winter", "Summer", "Dragon", "Phoenix", "Iron"]
        
        if random.random() < 0.5:
            return f"{random.choice(prefixes)}{random.choice(suffixes)}"
        else:
            return f"{random.choice(roots)}{random.choice(suffixes)}"
    
    def _distribute_population(self):
        """Initialize population distribution across societal roles"""
        total = sum(self.society.values())
        for role in self.society:
            self.society[role] /= total
    
    def update_year(self):
        """Update civilization for one year with leader influence"""
        # Update leader first
        leader_status = self.leader.update_year()
        if leader_status != "alive":
            self._handle_leader_change(leader_status)
        
        # Apply leader modifiers
        leader_modifiers = self.leader.get_trait_modifiers()
        
        # Update population
        self._update_population()
        
        # Update economy
        self._update_economy(leader_modifiers)
        
        # Update technology
        self._update_technology(leader_modifiers)
        
        # Update military
        self._update_military(leader_modifiers)
        
        # Update diplomacy
        self._update_diplomacy(leader_modifiers)
        
        # Update happiness and stability
        self._update_society(leader_modifiers)
        
        # Handle crises
        self._handle_crises()
        
        # Record annual summary
        self._record_annual_summary()
    
    def _handle_leader_change(self, death_reason):
        """Handle leader death and succession"""
        old_leader = self.leader
        
        # Record leader death
        death_details = {
            "died": "of natural causes",
            "died_early": "in an unexpected tragedy"
        }.get(death_reason, "under mysterious circumstances")
        
        death_event = HistoryEvent(
            year=self.world.year,
            event_type="leader_death",
            civilization=self.name,
            details=f"{old_leader.full_title} passed away {death_details} after {old_leader.years_ruled} years of rule",
            leader=old_leader.full_title,
            severity="major"
        )
        self.history.append(death_event)
        self.world.history_archive.record_event(death_event)
        
        # Calculate legacy
        old_leader.calculate_legacy()
        
        # Create new leader (with some inheritance of traits)
        new_leader = Leader(
            charisma=max(20, min(80, old_leader.charisma + random.randint(-10, 10))),
            intelligence=max(20, min(80, old_leader.intelligence + random.randint(-10, 10))),
            ambition=max(20, min(80, old_leader.ambition + random.randint(-15, 15))),
            greed=max(20, min(80, old_leader.greed + random.randint(-10, 10))),
            caution=max(20, min(80, old_leader.caution + random.randint(-10, 10)))
        )
        
        self.leader = new_leader
        self.leader_history.append(new_leader)
        
        # Record succession
        succession_event = HistoryEvent(
            year=self.world.year,
            event_type="leader_succession",
            civilization=self.name,
            details=f"{new_leader.full_title} ascended to power",
            leader=new_leader.full_title,
            severity="normal"
        )
        self.history.append(succession_event)
        self.world.history_archive.record_event(succession_event)
    
    def _update_population(self):
        """Update population based on food and conditions"""
        growth_rate = 0.01
        
        # Food impact on growth
        food_ratio = self.resources["food"] / (self.population * self.BASE_FOOD_CONSUMPTION)
        if food_ratio > 1.5:
            growth_rate += 0.02
        elif food_ratio < 0.8:
            growth_rate -= 0.03
            if food_ratio < 0.5:
                growth_rate -= 0.05
        
        # Happiness impact
        happiness_mod = (self.happiness - 50) / 500.0
        growth_rate += happiness_mod
        
        # Apply growth
        self.population = max(100, int(self.population * (1 + growth_rate)))
    
    def _update_economy(self, leader_modifiers):
        """Update resource production and consumption"""
        # Get terrain and climate bonuses
        terrain_bonus = self.world.map.get_terrain_bonus(self.map_position)
        climate_modifiers = self.world.climate.get_climate_modifiers()
        
        # Calculate production
        self.last_year_production = {
            "food": int(self.population * self.society["farmers"] * self.FARMER_YIELD + 
                       terrain_bonus.get("food", 0) + climate_modifiers.get("food", 0)),
            "metal": int(self.population * self.society["soldiers"] * 0.5 + 
                        terrain_bonus.get("metal", 0)),
            "wealth": int(self.population * self.society["merchants"] * self.MERCHANT_WEALTH + 
                         terrain_bonus.get("wealth", 0) + 
                         (leader_modifiers["trade_bonus"] * 100))
        }
        
        # Calculate consumption
        consumption = {
            "food": int(self.population * self.BASE_FOOD_CONSUMPTION + 
                       self.army_size * self.SOLDIER_FOOD_UPKEEP),
            "wealth": int(self.population * 0.1 + 
                         self.army_size * self.SOLDIER_WEALTH_UPKEEP +
                         self.population * self.society["scholars"] * self.SCHOLAR_WEALTH_UPKEEP +
                         self.population * self.society["nobles"] * self.NOBLE_WEALTH_UPKEEP)
        }
        
        # Update resources
        for resource in self.resources:
            if resource in self.last_year_production:
                self.resources[resource] += self.last_year_production[resource]
            if resource in consumption:
                self.resources[resource] -= consumption[resource]
            
            # Enforce storage limits
            self.resources[resource] = min(self.resources[resource], self.storage_limits[resource])
            self.resources[resource] = max(0, self.resources[resource])
    
    def _update_technology(self, leader_modifiers):
        """Update technology progress"""
        tech_gain = (self.population * self.society["scholars"] * self.SCHOLAR_TECH * 
                    (1 + leader_modifiers["tech_bonus"]))
        self.tech_progress += tech_gain
        
        if self.tech_progress >= 1.0:
            self.tech_level += 1
            self.tech_progress = 0
            
            # Record technology breakthrough
            tech_event = HistoryEvent(
                year=self.world.year,
                event_type="technology_breakthrough",
                civilization=self.name,
                details=f"achieved Technology Level {self.tech_level}",
                leader=self.leader.full_title,
                severity="normal"
            )
            self.history.append(tech_event)
            self.world.history_archive.record_event(tech_event)
    
    def _update_military(self, leader_modifiers):
        """Update military status and handle wars"""
        # Update army size based on population and resources
        target_army_size = int(self.population * self.society["soldiers"])
        
        if target_army_size > self.army_size:
            # Can we afford to recruit more soldiers?
            recruit_cost = (target_army_size - self.army_size) * 10
            if self.resources["wealth"] > recruit_cost:
                self.army_size = target_army_size
                self.resources["wealth"] -= recruit_cost
        elif target_army_size < self.army_size:
            # Demobilize excess soldiers
            self.army_size = target_army_size
        
        # Handle existing wars
        if self.war_with:
            self._conduct_war()
        
        # Check for war declaration (influenced by leader ambition)
        if (self.war_with is None and self.peace_treaty_years <= 0 and 
            random.random() < 0.05 + leader_modifiers["war_chance_mod"]):
            self._consider_war_declaration()
        
        if self.peace_treaty_years > 0:
            self.peace_treaty_years -= 1
    
    def _update_diplomacy(self, leader_modifiers):
        """Update relationships with other civilizations"""
        for other_civ in self.world.civilizations:
            if other_civ.id == self.id:
                continue
            
            if other_civ.name not in self.relationships:
                self.relationships[other_civ.name] = random.uniform(-0.5, 0.5)
            
            # Relationship drift
            drift = random.uniform(-0.1, 0.1) + leader_modifiers["diplomacy_bonus"] * 0.1
            self.relationships[other_civ.name] += drift
            self.relationships[other_civ.name] = max(-1.0, min(1.0, self.relationships[other_civ.name]))
    
    def _update_society(self, leader_modifiers):
        """Update happiness and stability"""
        # Base happiness calculation
        food_ratio = self.resources["food"] / (self.population * self.BASE_FOOD_CONSUMPTION)
        wealth_ratio = self.resources["wealth"] / (self.population * 0.2)
        
        self.happiness = 50
        self.happiness += min(30, (food_ratio - 1) * 20)
        self.happiness += min(20, (wealth_ratio - 1) * 10)
        self.happiness += leader_modifiers["happiness_bonus"] * 20
        
        # Stability affected by happiness and wars
        self.stability = self.happiness
        if self.war_with:
            self.stability -= 20
        
        self.happiness = max(0, min(100, self.happiness))
        self.stability = max(0, min(100, self.stability))
    
    def _handle_crises(self):
        """Handle various crises that can occur"""
        # Famine check
        food_ratio = self.resources["food"] / (self.population * self.BASE_FOOD_CONSUMPTION)
        if food_ratio < 0.3 and random.random() < 0.3:
            self._trigger_famine()
        
        # Economic crisis check
        wealth_ratio = self.resources["wealth"] / (self.population * 0.2)
        if wealth_ratio < 0.4 and random.random() < 0.2:
            self._trigger_economic_crisis()
        
        # Rebellion check
        if self.stability < 30 and random.random() < 0.1:
            self._trigger_rebellion()
        
        # Golden age check
        if (food_ratio > 1.8 and wealth_ratio > 1.5 and self.stability > 80 and 
            random.random() < 0.05):
            self._trigger_golden_age()
    
    def _trigger_famine(self):
        """Handle famine crisis"""
        severity = "catastrophic" if self.resources["food"] < self.population * 0.2 else "major"
        
        famine_event = HistoryEvent(
            year=self.world.year,
            event_type="famine",
            civilization=self.name,
            details=f"suffered a devastating famine. Population: {self.population} -> {int(self.population * 0.8)}",
            leader=self.leader.full_title,
            severity=severity
        )
        self.history.append(famine_event)
        self.world.history_archive.record_event(famine_event)
        
        # Apply effects
        self.population = int(self.population * 0.8)
        self.happiness -= 30
        self.stability -= 25
    
    def _trigger_economic_crisis(self):
        """Handle economic crisis"""
        crisis_event = HistoryEvent(
            year=self.world.year,
            event_type="economic_crisis",
            civilization=self.name,
            details="experienced an economic crisis, depleting treasury",
            leader=self.leader.full_title,
            severity="major"
        )
        self.history.append(crisis_event)
        self.world.history_archive.record_event(crisis_event)
        
        # Apply effects
        self.resources["wealth"] = max(0, self.resources["wealth"] * 0.3)
        self.happiness -= 20
        self.stability -= 15
    
    def _trigger_rebellion(self):
        """Handle rebellion"""
        rebellion_event = HistoryEvent(
            year=self.world.year,
            event_type="rebellion",
            civilization=self.name,
            details="faced a major rebellion, destabilizing the government",
            leader=self.leader.full_title,
            severity="major"
        )
        self.history.append(rebellion_event)
        self.world.history_archive.record_event(rebellion_event)
        
        # Apply effects
        self.stability -= 30
        self.population = int(self.population * 0.9)
        self.army_size = int(self.army_size * 0.8)
    
    def _trigger_golden_age(self):
        """Trigger a golden age"""
        golden_age_event = HistoryEvent(
            year=self.world.year,
            event_type="golden_age",
            civilization=self.name,
            details="entered a glorious golden age of prosperity and cultural achievement",
            leader=self.leader.full_title,
            severity="major"
        )
        self.history.append(golden_age_event)
        self.world.history_archive.record_event(golden_age_event)
        
        # Apply effects
        self.happiness += 25
        self.stability += 20
        self.resources["wealth"] += self.population * 0.5
        self.leader.add_achievement("Led civilization to a golden age")
    
    def _consider_war_declaration(self):
        """Consider declaring war on another civilization"""
        potential_targets = []
        
        for other_civ in self.world.civilizations:
            if (other_civ.id != self.id and other_civ.war_with is None and 
                self.relationships.get(other_civ.name, 0) < -0.3):
                # Calculate war desire based on relationship and leader ambition
                war_desire = (-self.relationships[other_civ.name] * 0.5 + 
                             self.leader.ambition / 200.0)
                if war_desire > 0.3:
                    potential_targets.append((other_civ, war_desire))
        
        if potential_targets:
            target = max(potential_targets, key=lambda x: x[1])[0]
            self._declare_war(target)
    
    def _declare_war(self, target):
        """Declare war on another civilization"""
        self.war_with = target.name
        target.war_with = self.name
        
        war_event = HistoryEvent(
            year=self.world.year,
            event_type="war_declaration",
            civilization=self.name,
            details=f"declared war on {target.name}",
            leader=self.leader.full_title,
            other_civ=target.name,
            severity="major"
        )
        self.history.append(war_event)
        self.world.history_archive.record_event(war_event)
        
        # Also record from target's perspective
        target_war_event = HistoryEvent(
            year=self.world.year,
            event_type="war_declaration",
            civilization=target.name,
            details=f"was declared war upon by {self.name}",
            leader=target.leader.full_title,
            other_civ=self.name,
            severity="major"
        )
        target.history.append(target_war_event)
        self.world.history_archive.record_event(target_war_event)
        
        self.leader.add_achievement(f"Led {self.name} to war against {target.name}")
    
    def _conduct_war(self):
        """Conduct war operations"""
        if self.war_with is None:
            return
        
        target = None
        for civ in self.world.civilizations:
            if civ.name == self.war_with:
                target = civ
                break
        
        if target is None:
            self.war_with = None
            return
        
        # Simple war resolution based on army sizes and technology
        self_power = self.army_size * self.technology
        target_power = target.army_size * target.technology
        
        # Add some randomness
        self_power *= random.uniform(0.8, 1.2)
        target_power *= random.uniform(0.8, 1.2)
        
        if self_power > target_power * 1.5:
            # Decisive victory
            self._win_war(target)
        elif target_power > self_power * 1.5:
            # Decisive defeat
            self._lose_war(target)
        elif random.random() < 0.1:
            # Stalemate - peace treaty
            self._make_peace(target)
    
    def _win_war(self, target):
        """Handle winning a war"""
        victory_event = HistoryEvent(
            year=self.world.year,
            event_type="war_victory",
            civilization=self.name,
            details=f"achieved victory over {target.name}",
            leader=self.leader.full_title,
            other_civ=target.name,
            severity="major"
        )
        self.history.append(victory_event)
        self.world.history_archive.record_event(victory_event)
        
        # Apply victory effects
        self.resources["wealth"] += target.resources["wealth"] * 0.3
        target.resources["wealth"] *= 0.7
        self.happiness += 15
        self.leader.add_achievement(f"Victory over {target.name}")
        
        self._make_peace(target)
    
    def _lose_war(self, target):
        """Handle losing a war"""
        defeat_event = HistoryEvent(
            year=self.world.year,
            event_type="war_defeat",
            civilization=self.name,
            details=f"was defeated by {target.name}",
            leader=self.leader.full_title,
            other_civ=target.name,
            severity="major"
        )
        self.history.append(defeat_event)
        self.world.history_archive.record_event(defeat_event)
        
        # Apply defeat effects
        self.resources["wealth"] *= 0.6
        self.army_size = int(self.army_size * 0.5)
        self.happiness -= 20
        self.stability -= 25
        
        self._make_peace(target)
    
    def _make_peace(self, target):
        """Make peace after war"""
        self.war_with = None
        target.war_with = None
        self.peace_treaty_years = random.randint(5, 15)
        target.peace_treaty_years = self.peace_treaty_years
        
        peace_event = HistoryEvent(
            year=self.world.year,
            event_type="diplomatic_peace",
            civilization=self.name,
            details=f"signed a peace treaty with {target.name}",
            leader=self.leader.full_title,
            other_civ=target.name,
            severity="normal"
        )
        self.history.append(peace_event)
        self.world.history_archive.record_event(peace_event)
    
    def _record_annual_summary(self):
        """Record an annual summary event"""
        # Only record significant years to avoid clutter
        significant = (
            self.population > self._get_previous_population() * 1.1 or
            any(self.resources[res] > self._get_previous_resource(res) * 1.2 for res in self.resources) or
            self.tech_level > self._get_previous_tech_level()
        )
        
        if significant:
            summary_event = HistoryEvent(
                year=self.world.year,
                event_type="population_boom" if self.population > self._get_previous_population() * 1.1 else "economic_boom",
                civilization=self.name,
                details=f"prospered - Population: {self.population}, Food: {self.resources.get('food')}, Wealth: {self.resources.get('wealth')}",
                leader=self.leader.full_title,
                severity="normal"
            )
            self.history.append(summary_event)
            self.world.history_archive.record_event(summary_event)
    
    def _get_previous_population(self):
        """Get population from last year (simplified)"""
        return self.population * 0.95  # Approximation
    
    def _get_previous_resource(self, resource):
        """Get resource amount from last year (simplified)"""
        return self.resources[resource] * 0.9  # Approximation
    
    def _get_previous_tech_level(self):
        """Get tech level from last year"""
        return self.tech_level - 0.1  # Approximation
    
    def display_status(self):
        """Display current civilization status"""
        print(f"\n=== {self.name} ===")
        print(f"Leader: {self.leader.full_title} (Age: {self.leader.age}, Ruled: {self.leader.years_ruled} years)")
        print(f"Population: {self.population:,}")
        print(f"Technology Level: {self.tech_level:.1f} (Progress: {self.tech_progress:.1%})")
        print(f"Resources: Food={self.resources['food']:,}, Metal={self.resources['metal']:,}, Wealth={self.resources['wealth']:,}")
        print(f"Happiness: {self.happiness}/100, Stability: {self.stability}/100")
        print(f"Society: Farmers={self.society['farmers']:.0%}, Merchants={self.society['merchants']:.0%}, " +
              f"Soldiers={self.society['soldiers']:.0%}, Scholars={self.society['scholars']:.0%}, Nobles={self.society['nobles']:.0%}")
        print(f"Army Size: {self.army_size}")
        if self.war_with:
            print(f"At War with: {self.war_with}")
        if self.peace_treaty_years > 0:
            print(f"Peace Treaty: {self.peace_treaty_years} years remaining")
    
    def get_recent_history(self, years=10):
        """Get recent history events"""
        current_year = self.world.year
        recent_events = []
        
        for event in reversed(self.history):
            if event.year >= current_year - years:
                recent_events.append(event)
            else:
                break
        
        return list(reversed(recent_events))
    
    def to_dict(self):
        """Convert civilization data to dictionary for saving"""
        return {
            'id': self.id,
            'name': self.name,
            'population': self.population,
            'technology': self.technology,
            'map_position': self.map_position,
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
            'relationships': self.relationships,
            'traits': self.traits,
            'leader': self.leader.to_dict(),
            'leader_history': [leader.to_dict() for leader in self.leader_history],
            'history': [event.to_dict() for event in self.history]
        }
    
    @classmethod
    def from_dict(cls, data, world):
        """Create civilization from saved dictionary data"""
        civ = cls(
            world=world,
            id_num=data['id'],
            name=data['name'],
            population=data['population'],
            technology=data['technology'],
            map_position=tuple(data['map_position']) if data['map_position'] else None
        )
        
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
        civ.relationships = data['relationships']
        civ.traits = data['traits']
        
        # Reconstruct leader and history
        civ.leader = Leader.from_dict(data['leader'])
        civ.leader_history = [Leader.from_dict(leader_data) for leader_data in data['leader_history']]
        civ.history = [HistoryEvent.from_dict(event_data) for event_data in data['history']]
        
        return civ

"""
====================== WORLD CLASS ======================
Enhanced with Deep History System
"""

class World:
    """Main world class that orchestrates the entire simulation"""
    
    def __init__(self, num_civilizations=4, width=40, height=20, seed=None):
        self.year = 0
        self.rng = random.Random(seed) if seed is not None else random.Random()
        
        # Core systems
        self.map = WorldMap(width, height, seed=self.rng.randint(0, 1000000))
        self.climate = ClimateSystem(rng=self.rng)
        
        # DEEP HISTORY SYSTEM
        self.history_archive = HistoryArchive()
        self.legends_mode = LegendsMode(self.history_archive)
        
        # Civilizations
        self.civilizations = []
        for i in range(num_civilizations):
            civ = Civilization(self, i)
            self.civilizations.append(civ)
        
        # Initialize world
        self.map.generate_geography()
        for civ in self.civilizations:
            self.map.place_civilization(civ)
    
    def simulate_year(self):
        """Simulate one year of world history"""
        self.year += 1
        self.climate.update()
        
        # Update all civilizations
        for civ in self.civilizations:
            civ.update_year()
        
        # Record world-level annual summary (every 10 years)
        if self.year % 10 == 0:
            self._record_world_summary()
    
    def _record_world_summary(self):
        """Record a decade summary"""
        total_population = sum(civ.population for civ in self.civilizations)
        active_wars = sum(1 for civ in self.civilizations if civ.war_with)
        
        summary_event = HistoryEvent(
            year=self.year,
            event_type="era_summary",
            civilization="World",
            details=f"Decade summary - Total population: {total_population:,}, Active wars: {active_wars}",
            severity="normal"
        )
        self.history_archive.record_event(summary_event)
    
    def display_world_status(self):
        """Display current status of all civilizations"""
        print(f"\n{'='*60}")
        print(f"WORLD STATUS - Year {self.year}")
        print(f"{'='*60}")
        print(f"Season: {self.climate.season}, Temperature: {self.climate.temperature:.1f}°C, Rainfall: {self.climate.rainfall:.1f}mm")
        
        total_population = sum(civ.population for civ in self.civilizations)
        total_wealth = sum(civ.resources['wealth'] for civ in self.civilizations)
        active_wars = sum(1 for civ in self.civilizations if civ.war_with)
        
        print(f"\nWorld Totals: Population: {total_population:,}, Wealth: {total_wealth:,}, Wars: {active_wars}")
        
        for civ in self.civilizations:
            civ.display_status()
    
    def display_recent_events(self, years=10):
        """Display recent world events"""
        print(f"\n{'='*60}")
        print(f"RECENT WORLD EVENTS (Last {years} years)")
        print(f"{'='*60}")
        
        recent_events = self.history_archive.get_recent_events(years_back=years, current_year=self.year)
        
        if not recent_events:
            print("No significant events in this period.")
            return
        
        for event in recent_events:
            print(f"Year {event.year}: {event.civilization} - {event.details}")
    
    def get_legends_view(self, view_type="world", target=None, years=50):
        """Generate legends view of history"""
        if view_type == "world":
            return self.legends_mode.generate_world_chronicle(
                start_year=max(0, self.year - years),
                end_year=self.year
            )
        elif view_type == "civilization" and target:
            return self.legends_mode.generate_civilization_biography(target, self.year)
        elif view_type == "story":
            return self.legends_mode.generate_story_view(
                civilization=target,
                start_year=max(0, self.year - years),
                end_year=self.year
            )
        else:
            return "Invalid legends view type."
    
    def display_legends(self, view_type="world", target_civ=None, years=50):
        """Display legends view"""
        print(f"\n{'='*60}")
        print(f"LEGENDS MODE: {view_type.upper()} VIEW")
        print(f"{'='*60}")
        
        legends_text = self.get_legends_view(view_type, target_civ, years)
        print(legends_text)
    
    def run_simulation(self, years=100, display_interval=10):
        """Run the simulation for specified years"""
        print(f"Starting Fantasy Engine Pre-Alpha 9 - Deep History & Legends Mode")
        print(f"Simulating {years} years...")
        
        start_time = time.time()
        
        for year in range(years):
            self.simulate_year()
            
            if (year + 1) % display_interval == 0:
                print(f"\n*** After {self.year} years ***")
                self.display_world_status()
                
                # Display legends view every 50 years
                if (year + 1) % 50 == 0:
                    self.display_legends("world", years=50)
        
        end_time = time.time()
        print(f"\nSimulation completed in {end_time - start_time:.2f} seconds")
        
        # Final legends view
        self.display_legends("world", years=min(100, years))
    
    def to_dict(self):
        """Convert world state to dictionary for saving"""
        return {
            'year': self.year,
            'map': self.map.to_dict(),
            'climate': self.climate.to_dict(),
            'civilizations': [civ.to_dict() for civ in self.civilizations],
            'history_archive': self.history_archive.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create world from saved dictionary data"""
        # Extract seed from map data
        seed = data['map']['seed']
        world = cls(
            num_civilizations=0,  # Will be loaded from data
            width=data['map']['width'],
            height=data['map']['height'],
            seed=seed
        )
        
        world.year = data['year']
        world.map = WorldMap.from_dict(data['map'])
        world.climate = ClimateSystem.from_dict(data['climate'], rng=world.rng)
        
        # Reconstruct civilizations
        world.civilizations = [
            Civilization.from_dict(civ_data, world) 
            for civ_data in data['civilizations']
        ]
        
        # Reconstruct history archive
        world.history_archive = HistoryArchive.from_dict(data['history_archive'])
        world.legends_mode = LegendsMode(world.history_archive)
        
        return world

"""
====================== MAIN EXECUTION ======================
"""

def main():
    """Main function to demonstrate the enhanced Fantasy Engine"""
    
    # Create a new world
    world = World(num_civilizations=4, width=30, height=15, seed=42)
    
    # Display initial state
    world.map.display(world.civilizations)
    world.display_world_status()
    
    # Run a short simulation
    world.run_simulation(years=50, display_interval=10)
    
    # Demonstrate legends mode
    print("\n" + "="*80)
    print("DEEP HISTORY & LEGENDS MODE DEMONSTRATION")
    print("="*80)
    
    # Show different legends views
    if world.civilizations:
        test_civ = world.civilizations[0].name
        world.display_legends("civilization", test_civ)
        print("\n")
        world.display_legends("story", test_civ, years=30)
    
    # Show cause-effect analysis
    print("\n" + "="*80)
    print("CAUSE-EFFECT ANALYSIS")
    print("="*80)
    
    # Find a major event and its consequences
    major_events = world.history_archive.get_events(severity="major")
    if major_events:
        sample_event = major_events[0]
        print(f"Major Event: {sample_event}")
        chain = world.history_archive.get_event_chain(sample_event.id)
        if len(chain) > 1:
            print("Consequences:")
            for event in chain[1:]:
                print(f"  → {event}")
    
    # Show era summaries
    print("\n" + "="*80)
    print("ERA SUMMARIES")
    print("="*80)
    
    for start_year in range(0, world.year, 25):
        end_year = min(start_year + 24, world.year)
        if start_year < end_year:
            summary = world.history_archive.get_world_era_summary(start_year, end_year)
            print(summary)

if __name__ == "__main__":
    main()