import random
import time
from datetime import datetime
import os
import math
import json
from collections import defaultdict

"""
====================== DEEP HISTORY & LEGENDS SYSTEM ======================
(Merged from Legends & Lore)
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
        "foundation": "Civilization Founded",
        "cultural_renaissance": "Cultural Flourishing",
        "cultural_artifact": "Artistic Creation",
        "religious_conversion": "Religious Change",
        "religious_schism": "Religious Split", 
        "religious_reformation": "Religious Reform",
        "religion_founded": "New Religion Founded",
        "pilgrimage": "Religious Journey",
        "battle": "Military Battle",
        "leader_assassination": "Leader Assassination",
        "leader_retirement": "Leader Retirement",
        "succession": "Leader Succession",
        "annual_summary": "Yearly Summary",
        "economic_collapse": "Economic Collapse",
        "war_declared": "War Declaration",
        "relations_improved": "Improved Relations",
        "relations_worsened": "Worsened Relations",
        "alliance_formed": "Diplomatic Alliance",
        "tech_advance": "Technological Advancement",
        "festival": "Cultural Festival",         # <-- ADDED
        "holy_war_declaration": "Holy War Declared" # <-- ADDED
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
            leader=data.get('leader'), # Use .get for backwards compatibility
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
                years_back=10,
                current_year=new_event.year
            )
            if last_famine:
                new_event.caused_by = last_famine[0].id
                self.cause_effect_chains.append((last_famine[0].id, new_event.id))
        
        # War victories often lead to golden ages
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
        
        # Economic crises can lead to leadership changes
        elif new_event.event_type == "leader_succession":
            recent_crisis = self.get_recent_events(
                civilization=new_event.civilization,
                event_type="economic_crisis",
                years_back=5,
                current_year=new_event.year
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
        archive.cause_effect_chains = data.get('cause_effect_chains', [])
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
            ],
            "cultural_renaissance": [
                "{civ} experienced a cultural renaissance in Year {year}, {details}",
                "The arts and sciences flourished in {civ} during Year {year}, {details}",
            ],
            "religion_founded": [
                "Year {year} saw the founding of {details} in {civ} under {leader}.",
                "A new faith, {details}, emerged in {civ} during Year {year}.",
            ],
            "religious_schism": [
                "A great schism in Year {year} saw {civ} {details}.",
                "Doctrinal disputes in Year {year} led {civ} to {details}.",
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
(Merged from Legends & Lore)
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
        leader.years_ruled = data.get('years_ruled', 0)
        leader.legacy_score = data.get('legacy_score', 0)
        leader.major_achievements = data.get('major_achievements', [])
        return leader
    
    def __str__(self):
        return f"{self.full_title} (Age: {self.age}, Ruled: {self.years_ruled} years)"

"""
====================== MAP & CLIMATE SYSTEMS ======================
(Merged from Legends & Lore)
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
    
    def get_terrain_at(self, position):
        """Get terrain type name at position"""
        x, y = position
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.terrain_types.get(self.grid[y][x], "Unknown")
        return "Void"

    def get_terrain_bonus(self, position):
        """Get economic bonuses based on terrain type at position"""
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
        # Fallback: place anywhere
        x, y = self.rng.randint(0, self.width-1), self.rng.randint(0, self.height-1)
        self.civilization_locations[civ.name] = (x, y)
        civ.map_position = (x, y)
        return False


    def display(self, civilizations):
        """Print ASCII map of the world"""
        print("\nWorld Map:")
        for y in range(self.height):
            row = []
            for x in range(self.width):
                is_civ = False
                for civ in civilizations:
                    if (x, y) == (int(civ.map_position[0]), int(civ.map_position[1])):
                        row.append(civ.name[0].upper())
                        is_civ = True
                        break
                if not is_civ:
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

"""
====================== CULTURE & RELIGION SYSTEM ======================
(From Culture & Religion file, with HistoryEvent calls updated)
"""

class CultureSystem:
    """Manages cultural traits and their evolution for civilizations"""
    
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
        self.artifacts = []  # Cultural artifacts and wonders
        self.cultural_achievements = []
        self.influences = {}  # Cultural influence from other civilizations
        
    def _generate_initial_traits(self, terrain_type):
        """Generate initial cultural traits based on terrain and RNG"""
        traits = {}
        
        # Base random values
        for trait in self.CULTURAL_TRAITS:
            traits[trait] = random.uniform(0.3, 0.7)
        
        # Terrain influences
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
        
        # Leader personality influences
        leader = self.civilization.leader
        traits["militarism"] += (leader.ambition - 50) / 100.0
        traits["diplomacy"] += (leader.charisma - 50) / 100.0
        traits["artistry"] += (leader.intelligence - 50) / 200.0
        
        # Normalize to 0-1 range
        for trait in traits:
            traits[trait] = max(0.1, min(0.9, traits[trait]))
            
        # Convert artistry and spirituality to 0-100 scale for events
        traits["artistry"] = int(traits["artistry"] * 100)
        traits["spirituality"] = int(traits["spirituality"] * 100)
        traits["cohesion"] = int(traits["cohesion"] * 100)
        
        return traits
    
    def update_yearly(self):
        """Update cultural traits based on events and interactions"""
        # Small random drift
        for trait in self.traits:
            if isinstance(self.traits[trait], (int, float)) and trait not in ["artistry", "spirituality", "cohesion"]:
                drift = random.uniform(-0.02, 0.02)
                self.traits[trait] = max(0.1, min(0.9, self.traits[trait] + drift))
        
        # Events that affect culture
        self._apply_event_influences()
        
        # Update cohesion based on stability and happiness
        stability_effect = (self.civilization.stability - 50) / 200.0
        happiness_effect = (self.civilization.happiness - 50) / 200.0
        self.traits["cohesion"] = max(10, min(100, 
            self.traits["cohesion"] + stability_effect + happiness_effect))
    
    def _apply_event_influences(self):
        """Apply influences from recent events on culture"""
        recent_events = self.civilization.get_recent_history(years=5)
        
        for event in recent_events:
            if event.event_type == "war_victory":
                self.traits["militarism"] = min(0.9, self.traits["militarism"] + 0.05)
                self.traits["honor"] = min(0.9, self.traits["honor"] + 0.03)
            elif event.event_type == "war_defeat":
                self.traits["militarism"] = max(0.1, self.traits["militarism"] - 0.05)
                self.traits["diplomacy"] = min(0.9, self.traits["diplomacy"] + 0.04)
            elif event.event_type == "golden_age":
                self.traits["artistry"] = min(100, self.traits["artistry"] + 10)
                self.traits["cohesion"] = min(100, self.traits["cohesion"] + 15)
            elif event.event_type == "famine":
                self.traits["cohesion"] = max(10, self.traits["cohesion"] - 20)
                self.traits["spirituality"] = min(100, self.traits["spirituality"] + 5)
    
    def get_economic_modifiers(self):
        """Get economic modifiers based on cultural traits"""
        return {
            "production_bonus": (self.traits["industriousness"] - 0.5) * 0.2,
            "trade_bonus": (self.traits["diplomacy"] - 0.5) * 0.15,
            "innovation_bonus": (1 - self.traits["tradition"]) * 0.1
        }
    
    def get_military_modifiers(self):
        """Get military modifiers based on cultural traits"""
        return {
            "morale_bonus": (self.traits["honor"] - 0.5) * 0.2,
            "aggression_bonus": (self.traits["militarism"] - 0.5) * 0.25,
            "discipline_bonus": (self.traits["collectivism"] - 0.5) * 0.15
        }
    
    def get_society_modifiers(self):
        """Get society modifiers based on cultural traits"""
        return {
            "happiness_bonus": (self.traits["artistry"] / 100.0 - 0.5) * 0.1,
            "stability_bonus": (self.traits["cohesion"] / 100.0 - 0.5) * 0.2,
            "growth_bonus": (self.traits["collectivism"] - 0.5) * 0.1
        }
    
    def add_artifact(self, name, description, year_created):
        """Add a cultural artifact or wonder"""
        artifact = {
            "name": name,
            "description": description,
            "year_created": year_created,
            "civilization": self.civilization.name
        }
        self.artifacts.append(artifact)
        
        # Record in history
        artifact_event = HistoryEvent(
            year=year_created,
            event_type="cultural_artifact",
            civilization=self.civilization.name,
            details=f"created {name}: {description}",
            leader=self.civilization.leader.full_title,
            severity="normal"
        )
        self.civilization.world.history_archive.record_event(artifact_event)
    
    def to_dict(self):
        """Convert culture data to dictionary for saving"""
        return {
            'traits': self.traits,
            'artifacts': self.artifacts,
            'cultural_achievements': self.cultural_achievements,
            'influences': self.influences
        }
    
    @classmethod
    def from_dict(cls, data, civilization):
        """Create culture system from saved data"""
        culture = cls(civilization)
        culture.traits = data['traits']
        culture.artifacts = data.get('artifacts', [])
        culture.cultural_achievements = data.get('cultural_achievements', [])
        culture.influences = data.get('influences', {})
        return culture

class Religion:
    """Represents a religious belief system"""
    
    # Religious concepts and deities
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
        self.name = name if name else self.generate_name()
        self.founding_civilization = founding_civ.name if founding_civ else "Unknown"
        self.year_founded = year_founded
        self.doctrine_type = random.choice(list(self.DOCTRINE_TYPES.keys()))
        self.deities = self._generate_deities()
        self.moral_focus = random.sample(self.MORAL_AXES, 2)  # Primary moral values
        self.spread_rate = random.uniform(0.01, 0.05)
        self.conflict_bias = random.uniform(-0.3, 0.3)  # Negative = pacifist, Positive = militant
        self.followers = [founding_civ.name] if founding_civ else []
        self.holy_sites = []
        self.schisms = []  # Historical schisms and reformations
        
        # Generate description
        self.description = self._generate_description()
    
    def _generate_deities(self):
        """Generate deities based on doctrine type"""
        if self.doctrine_type == "monotheism":
            return [random.choice(self.DEITIES)]
        elif self.doctrine_type == "polytheism":
            return random.sample(self.DEITIES, random.randint(3, 5))
        elif self.doctrine_type == "dualistic":
            return random.sample(self.DEITIES, 2)
        else:
            return [random.choice(self.DEITIES)] if random.random() < 0.5 else []
    
    def generate_name(self):
        """Generate a religious name"""
        prefixes = ["Order of", "Church of", "Temple of", "Path of", "Way of", "Cult of"]
        suffixes = ["Light", "Darkness", "Truth", "Unity", "Harmony", "Eternity"]
        concepts = ["Divine", "Sacred", "Holy", "Eternal", "Ancient"]
        
        if random.random() < 0.6:
            return f"{random.choice(prefixes)} the {random.choice(self.DEITIES)}"
        else:
            return f"{random.choice(concepts)} {random.choice(suffixes)}"
    
    def _generate_description(self):
        """Generate a descriptive text for the religion"""
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
        """Add a civilization as follower of this religion"""
        if civilization_name not in self.followers:
            self.followers.append(civilization_name)
    
    def remove_follower(self, civilization_name):
        """Remove a civilization from followers"""
        if civilization_name in self.followers:
            self.followers.remove(civilization_name)
    
    def calculate_compatibility(self, other_religion):
        """Calculate compatibility with another religion (0-1 scale)"""
        if self == other_religion:
            return 1.0
        
        # Same doctrine type increases compatibility
        doctrine_match = 0.3 if self.doctrine_type == other_religion.doctrine_type else 0
        
        # Shared moral values increase compatibility
        shared_morals = len(set(self.moral_focus) & set(other_religion.moral_focus))
        moral_match = shared_morals * 0.15
        
        # Shared deities increase compatibility (for polytheistic religions)
        shared_deities = len(set(self.deities) & set(other_religion.deities))
        deity_match = shared_deities * 0.1
        
        return min(1.0, doctrine_match + moral_match + deity_match + 0.1)
    
    def to_dict(self):
        """Convert religion to dictionary for saving"""
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
        """Create religion from saved data"""
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
        religion.description = data.get('description', religion._generate_description()) # Regenerate if missing
        return religion

class ReligionSystem:
    """Manages all religions in the world and their interactions"""
    
    def __init__(self, world):
        self.world = world
        self.religions = []
        self.religious_events = []
    
    def initialize_religions(self, civilizations):
        """Initialize religions at world creation"""
        # Start with 1-3 religions
        num_religions = random.randint(1, min(3, len(civilizations)))
        
        civ_pool = list(civilizations)
        
        for i in range(num_religions):
            if not civ_pool: break
            founding_civ = random.choice(civ_pool)
            civ_pool.remove(founding_civ)
            
            religion = Religion(founding_civ=founding_civ, year_founded=self.world.year)
            self.religions.append(religion)
            
            # Assign to founding civilization
            founding_civ.religion = religion
            
            # Record founding event
            founding_event = HistoryEvent(
                year=self.world.year,
                event_type="religion_founded",
                civilization=founding_civ.name,
                details=f"founded the {religion.name}: {religion.description}",
                leader=founding_civ.leader.full_title,
                severity="major"
            )
            self.world.history_archive.record_event(founding_event)
        
        # Assign remaining civilizations to religions
        for civ in civilizations:
            if not hasattr(civ, 'religion') or civ.religion is None:
                self.assign_religion(civ)
    
    def assign_religion(self, civilization, specific_religion=None):
        """Assign a religion to a civilization"""
        if specific_religion:
            if civilization.religion:
                civilization.religion.remove_follower(civilization.name)
            civilization.religion = specific_religion
            specific_religion.add_follower(civilization.name)
        elif self.religions:
            # Choose religion based on cultural compatibility
            compatible_religions = []
            for religion in self.religions:
                compatibility = self._calculate_cultural_compatibility(civilization, religion)
                compatible_religions.append((religion, compatibility))
            
            # Weighted random selection based on compatibility
            total = sum(comp for _, comp in compatible_religions)
            if total > 0:
                rand_val = random.uniform(0, total)
                current = 0
                for religion, comp in compatible_religions:
                    current += comp
                    if rand_val <= current:
                        civilization.religion = religion
                        religion.add_follower(civilization.name)
                        break
            else:
                # Fallback: random assignment
                civilization.religion = random.choice(self.religions)
                civilization.religion.add_follower(civilization.name)
        else:
            # No religions exist yet, create one
            new_religion = Religion(founding_civ=civilization, year_founded=self.world.year)
            self.religions.append(new_religion)
            civilization.religion = new_religion
    
    def _calculate_cultural_compatibility(self, civilization, religion):
        """Calculate how compatible a civilization's culture is with a religion"""
        culture = civilization.culture_system.traits
        
        # Spiritual cultures prefer religions
        base_compatibility = culture["spirituality"] / 100.0
        
        # Traditional cultures prefer older religions
        if religion.year_founded < self.world.year - 50:
            base_compatibility += culture["tradition"] * 0.3
        
        # Collectivist cultures prefer widespread religions
        if len(religion.followers) > 1:
            base_compatibility += culture["collectivism"] * 0.2
        
        return max(0.1, base_compatibility)
    
    def update_yearly(self):
        """Update religious spread and events"""
        # Religious spread to neighboring civilizations
        for religion in self.religions:
            self._spread_religion(religion)
        
        # Check for religious events
        self._check_religious_events()
    
    def _spread_religion(self, religion):
        """Spread religion to neighboring civilizations"""
        if len(religion.followers) == 0:
            return
        
        for civ in self.world.civilizations:
            if civ.religion == religion:
                continue
            
            # Check if this civ is neighbor to a follower
            is_neighbor = False
            for other_civ in self.world.civilizations:
                if (other_civ.religion == religion and 
                    self._are_neighbors(civ, other_civ)):
                    is_neighbor = True
                    break
            
            if is_neighbor:
                # Calculate conversion chance
                conversion_chance = religion.spread_rate
                conversion_chance += (civ.culture_system.traits["spirituality"] / 500.0)
                conversion_chance -= (civ.culture_system.traits["tradition"] * 0.1)
                
                if random.random() < conversion_chance:
                    old_religion = civ.religion
                    
                    self.assign_religion(civ, religion)
                    
                    # Record conversion event
                    conversion_event = HistoryEvent(
                        year=self.world.year,
                        event_type="religious_conversion",
                        civilization=civ.name,
                        details=f"converted from {old_religion.name if old_religion else 'no faith'} to {religion.name}",
                        leader=civ.leader.full_title,
                        severity="normal"
                    )
                    self.world.history_archive.record_event(conversion_event)
    
    def _are_neighbors(self, civ1, civ2):
        """Check if two civilizations are neighbors on the map"""
        x1, y1 = civ1.map_position
        x2, y2 = civ2.map_position
        distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        return distance <= 5  # Neighbor radius
    
    def _check_religious_events(self):
        """Check for and trigger religious events"""
        for religion in self.religions:
            # Schism event - when religion has many followers but low cohesion among them
            if len(religion.followers) >= 3 and random.random() < 0.02:
                self._trigger_schism(religion)
            
            # Religious reformation - when civilization has high artistry and stability
            for civ_name in religion.followers:
                civ = next((c for c in self.world.civilizations if c.name == civ_name), None)
                if (civ and civ.culture_system.traits["artistry"] > 70 and 
                    civ.stability > 80 and random.random() < 0.01):
                    self._trigger_reformation(civ, religion)
    
    def _trigger_schism(self, religion):
        """Trigger a religious schism - creation of a new religion from an existing one"""
        schismatic_civ_names = random.sample(religion.followers, 
                                       min(2, len(religion.followers) // 2))
        
        if not schismatic_civ_names:
            return
        
        founding_civ_name = random.choice(schismatic_civ_names)
        founding_civ = next((c for c in self.world.civilizations if c.name == founding_civ_name), None)
        
        if not founding_civ:
            return
        
        # Create new religion with similar but distinct beliefs
        new_religion = Religion(founding_civ=founding_civ, year_founded=self.world.year)
        
        # Make it similar but distinct from parent religion
        new_religion.doctrine_type = religion.doctrine_type
        new_religion.deities = religion.deities[:]  # Copy deities
        if new_religion.deities and random.random() < 0.7:
            # Modify one deity
            idx = random.randint(0, len(new_religion.deities) - 1)
            new_religion.deities[idx] = random.choice(Religion.DEITIES)
        
        new_religion.moral_focus = religion.moral_focus[:]  # Copy moral focus
        if random.random() < 0.5:
            # Change one moral focus
            idx = random.randint(0, len(new_religion.moral_focus) - 1)
            available_morals = [m for m in Religion.MORAL_AXES if m not in new_religion.moral_focus]
            if available_morals:
                new_religion.moral_focus[idx] = random.choice(available_morals)
        
        new_religion.conflict_bias = religion.conflict_bias + random.uniform(-0.2, 0.2)
        
        self.religions.append(new_religion)
        religion.schisms.append({
            "year": self.world.year,
            "new_religion": new_religion.name,
            "reason": "doctrinal differences"
        })
        
        # Convert schismatic civilizations to new religion
        for civ_name in schismatic_civ_names:
            civ = next((c for c in self.world.civilizations if c.name == civ_name), None)
            if civ:
                self.assign_religion(civ, new_religion)
        
        # Record schism event
        schism_event = HistoryEvent(
            year=self.world.year,
            event_type="religious_schism",
            civilization=founding_civ.name,
            details=f"broke away from {religion.name} to form {new_religion.name}",
            leader=founding_civ.leader.full_title,
            severity="major"
        )
        self.world.history_archive.record_event(schism_event)
    
    def _trigger_reformation(self, civilization, religion):
        """Trigger a religious reformation - changes within existing religion"""
        # Reformation changes some aspects of the religion
        if random.random() < 0.5 and religion.deities:
            # Change a deity
            old_deity = random.choice(religion.deities)
            new_deity = random.choice([d for d in Religion.DEITIES if d != old_deity])
            religion.deities[religion.deities.index(old_deity)] = new_deity
        
        if random.random() < 0.4:
            # Change moral focus
            religion.moral_focus[0] = random.choice([m for m in Religion.MORAL_AXES if m != religion.moral_focus[1]])
        
        religion.conflict_bias += random.uniform(-0.1, 0.1)
        
        # Update description
        religion.description = religion._generate_description()
        
        # Record reformation event
        reformation_event = HistoryEvent(
            year=self.world.year,
            event_type="religious_reformation",
            civilization=civilization.name,
            details=f"led a reformation within {religion.name}, changing its doctrines",
            leader=civilization.leader.full_title,
            severity="major"
        )
        self.world.history_archive.record_event(reformation_event)
        
        civilization.leader.add_achievement(f"Led reformation of {religion.name}")
    
    def to_dict(self):
        """Convert religion system to dictionary for saving"""
        return {
            'religions': [religion.to_dict() for religion in self.religions],
            'religious_events': self.religious_events
        }
    
    @classmethod
    def from_dict(cls, data, world):
        """Create religion system from saved data"""
        religion_system = cls(world)
        religion_system.religions = [Religion.from_dict(rel_data) for rel_data in data['religions']]
        religion_system.religious_events = data.get('religious_events', [])
        return religion_system
    
    def get_religion_by_name(self, name):
        """Find a religion object by its name"""
        for religion in self.religions:
            if religion.name == name:
                return religion
        return None

"""
====================== ENHANCED CIVILIZATION CLASS ======================
Updated with Culture & Religion integration
"""

class Civilization:
    """Represents a civilization with leader-driven personality and cultural/religious identity"""
    
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
        
        # LEADER SYSTEM INTEGRATION (Using advanced Leader class)
        self.leader = Leader()
        self.leader.reign_start_year = self.world.year
        self.leader_history = [self.leader]
        
        # CULTURE & RELIGION SYSTEM INTEGRATION
        # Get terrain type for cultural initialization
        terrain_type = self.world.map.get_terrain_at(self.map_position)
        self.culture_system = CultureSystem(self, terrain_type=terrain_type)
        self.religion = None  # Will be assigned by ReligionSystem
        
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
        """Generate a unique civilization name"""
        prefixes = ["Ara", "Kha", "Zan", "Vor", "El", "Nor", "Syl", "Quor"]
        suffixes = ["dor", "nia", "thar", "van", "ris", "thal", "mor", "gard"]
        return random.choice(prefixes) + random.choice(suffixes)
    
    def _distribute_population(self):
        """Distribute population among societal classes"""
        total = sum(self.society.values())
        if total != 1.0 and total > 0:
            for key in self.society:
                self.society[key] /= total
    
    def update_year(self):
        """Update civilization for one year with leader and cultural influence"""
        # Update leader first
        leader_status = self.leader.update_year()
        if leader_status != "alive":
            self._handle_leader_change(leader_status)
        
        # Update culture and religion
        self.culture_system.update_yearly()
        
        # Apply leader modifiers
        leader_modifiers = self.leader.get_trait_modifiers()
        
        # Apply cultural modifiers
        cultural_economic_mods = self.culture_system.get_economic_modifiers()
        cultural_military_mods = self.culture_system.get_military_modifiers()
        cultural_society_mods = self.culture_system.get_society_modifiers()
        
        # Combine modifiers
        combined_modifiers = {}
        for mod_dict in [leader_modifiers, cultural_economic_mods, cultural_military_mods, cultural_society_mods]:
            for key, value in mod_dict.items():
                combined_modifiers[key] = combined_modifiers.get(key, 0) + value
        
        # Update population
        self._update_population(combined_modifiers)
        
        # Update economy with cultural modifiers
        self._update_economy(combined_modifiers)
        
        # Update technology
        self._update_technology(combined_modifiers)
        
        # Update military with cultural modifiers
        self._update_military(combined_modifiers)
        
        # Update diplomacy (relationships are updated by World class)
        
        # Update happiness and stability with cultural modifiers
        self._update_society(combined_modifiers)
        
        # Handle cultural and religious events
        self._handle_cultural_events()
        self._handle_crises()
        
        # Record annual summary
        self._record_annual_summary()
    
    def _handle_leader_change(self, death_reason):
        """MERGED: Handle leader death, succession, and cultural influence"""
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
        
        # MERGED: Apply cultural influence on new leader
        culture = self.culture_system.traits
        new_leader.ambition = min(100, max(1, new_leader.ambition + int((culture["militarism"] - 0.5) * 20)))
        new_leader.charisma = min(100, max(1, new_leader.charisma + int((culture["diplomacy"] - 0.5) * 20)))
        new_leader.intelligence = min(100, max(1, new_leader.intelligence + int((1 - culture["tradition"]) * 20)))
        new_leader._clamp_traits() # Ensure traits are valid
        
        self.leader = new_leader
        self.leader.reign_start_year = self.world.year
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
        
        # Stability impact from leadership change
        self.stability -= 20
    
    def _update_population(self, modifiers):
        """Update population based on food and happiness"""
        growth_rate = 0.01  # Base 1% growth
        
        # Food impact
        food_per_person = self.resources["food"] / max(1, self.population)
        if food_per_person > 1.2:
            growth_rate += 0.02
        elif food_per_person < 0.8:
            growth_rate -= 0.03
        
        # Happiness impact
        growth_rate += (self.happiness - 50) / 2000.0
        
        # Cultural impact
        growth_rate += modifiers.get("growth_bonus", 0)
        
        # Apply growth
        old_population = self.population
        self.population = int(self.population * (1 + growth_rate))
        
        # Ensure minimum population
        self.population = max(100, self.population)
        
        # Redistribute population if it changed significantly
        if abs(self.population - old_population) / max(1, old_population) > 0.05:
            self._distribute_population()
    
    def _update_economy(self, modifiers):
        """Update economic production and consumption"""
        # Get terrain and climate bonuses
        terrain_bonus = self.world.map.get_terrain_bonus(self.map_position)
        climate_modifiers = self.world.climate.get_climate_modifiers()
        
        # Calculate production
        farmer_pop = self.population * self.society["farmers"]
        merchant_pop = self.population * self.society["merchants"]
        
        food_production = (farmer_pop * self.FARMER_YIELD + 
                           terrain_bonus.get("food", 0) + 
                           climate_modifiers.get("food", 0))
        
        wealth_production = (merchant_pop * self.MERCHANT_WEALTH + 
                             terrain_bonus.get("wealth", 0))
        
        metal_production = (self.population * self.society["soldiers"] * 0.5 + 
                           terrain_bonus.get("metal", 0))

        # Apply cultural and leader modifiers
        food_production *= (1 + modifiers.get("production_bonus", 0))
        wealth_production *= (1 + modifiers.get("trade_bonus", 0))
        
        # Calculate consumption
        food_consumption = self.population * self.BASE_FOOD_CONSUMPTION
        food_consumption += self.army_size * self.SOLDIER_FOOD_UPKEEP
        
        wealth_consumption = self.army_size * self.SOLDIER_WEALTH_UPKEEP
        wealth_consumption += self.population * self.society["scholars"] * self.SCHOLAR_WEALTH_UPKEEP
        wealth_consumption += self.population * self.society["nobles"] * self.NOBLE_WEALTH_UPKEEP
        
        # Update resources
        self.resources["food"] += food_production - food_consumption
        self.resources["wealth"] += wealth_production - wealth_consumption
        self.resources["metal"] += metal_production # Simple metal prod
        
        # Enforce storage limits and non-negative
        for res, limit in self.storage_limits.items():
            self.resources[res] = max(0, min(self.resources[res], limit))
        
        # Store production for history
        self.last_year_production = {
            "food": food_production,
            "wealth": wealth_production,
            "metal": metal_production
        }
        
        # Update economic state
        self._update_economic_state()
    
    def _update_economic_state(self):
        """Update the economic state based on resource ratios"""
        food_ratio = self.resources["food"] / max(1, self.population * self.BASE_FOOD_CONSUMPTION)
        wealth_ratio = self.resources["wealth"] / max(1, self.population)
        
        if food_ratio > 1.5 and wealth_ratio > 1.0:
            self.economic_state = "prosperous"
        elif food_ratio < 0.8 or wealth_ratio < 0.5:
            self.economic_state = "struggling"
        else:
            self.economic_state = "stable"
    
    def _update_technology(self, modifiers):
        """Update technology progress"""
        scholar_pop = self.population * self.society["scholars"]
        tech_progress = scholar_pop * self.SCHOLAR_TECH
        
        # Apply innovation bonus from culture
        tech_progress *= (1 + modifiers.get("innovation_bonus", 0))
        # Apply leader bonus
        tech_progress *= (1 + modifiers.get("tech_bonus", 0))
        
        self.tech_progress += tech_progress
        
        # Check for technology level increase
        if self.tech_progress >= 1.0:
            self.tech_level += 1
            self.tech_progress = 0.0
            
            tech_event = HistoryEvent(
                year=self.world.year,
                event_type="tech_advance",
                civilization=self.name,
                details=f"achieved Technology Level {self.tech_level}",
                leader=self.leader.full_title,
                severity="major"
            )
            self.history.append(tech_event)
            self.world.history_archive.record_event(tech_event)
    
    def _update_military(self, modifiers):
        """Update military status"""
        # Base army size from soldier population
        target_army_size = int(self.population * self.society["soldiers"])
        
        # Apply cultural military modifiers
        target_army_size = int(target_army_size * (1 + modifiers.get("aggression_bonus", 0)))
        
        # Recruit or demobilize
        if target_army_size > self.army_size:
            # Can we afford to recruit more soldiers?
            recruit_cost = (target_army_size - self.army_size) * 10 # Cost 10 wealth per soldier
            if self.resources["wealth"] > recruit_cost and self.resources["metal"] > (target_army_size - self.army_size):
                self.army_size = target_army_size
                self.resources["wealth"] -= recruit_cost
        elif target_army_size < self.army_size:
            # Demobilize excess soldiers
            self.army_size = target_army_size
    
    def _update_society(self, modifiers):
        """Update societal metrics with cultural modifiers"""
        # Base changes
        happiness_change = 0
        stability_change = 0
        
        # Economic factors
        food_ratio = self.resources["food"] / max(1, self.population * self.BASE_FOOD_CONSUMPTION)
        if food_ratio > 1.5:
            happiness_change += 5
        elif food_ratio < 0.8:
            happiness_change -= 10
        
        wealth_ratio = self.resources["wealth"] / max(1, self.population)
        if wealth_ratio > 2:
            happiness_change += 3
        elif wealth_ratio < 0.5:
            happiness_change -= 5
        
        # War impact
        if self.war_with:
            happiness_change -= 10
            stability_change -= 5
        
        # Cultural modifiers
        happiness_change += modifiers.get("happiness_bonus", 0) * 100
        stability_change += modifiers.get("stability_bonus", 0) * 100
        
        # Leader impact (from leader_modifiers, not raw charisma)
        happiness_change += modifiers.get("happiness_bonus", 0) * 100 # This is now combined
        
        # Apply changes
        self.happiness = max(0, min(100, self.happiness + happiness_change))
        self.stability = max(0, min(100, self.stability + stability_change))

    def _calculate_cultural_similarity(self, other_civ):
        """Calculate cultural similarity with another civilization (0-1 scale)"""
        similarity = 0
        my_traits = self.culture_system.traits
        their_traits = other_civ.culture_system.traits
        
        trait_count = 0
        for trait in my_traits:
            if trait in their_traits and isinstance(my_traits[trait], (int, float)):
                my_val = my_traits[trait]
                their_val = their_traits[trait]
                
                # Normalize 0-100 scales
                if trait in ["artistry", "spirituality", "cohesion"]:
                    my_val /= 100.0
                    their_val /= 100.0
                
                diff = abs(my_val - their_val)
                similarity += (1 - diff)  # Smaller difference = more similarity
                trait_count += 1
        
        # Normalize to 0-1
        return similarity / trait_count if trait_count > 0 else 0.5

    def _handle_cultural_events(self):
        """Handle cultural and religious events"""
        # Cultural Renaissance - high artistry and stability
        if (self.culture_system.traits["artistry"] > 80 and 
            self.stability > 75 and 
            self.resources["wealth"] > self.population and
            random.random() < 0.05):
            self._trigger_cultural_renaissance()
        
        # Religious Pilgrimage - high spirituality and wealth
        if (self.culture_system.traits["spirituality"] > 60 and
            self.resources["wealth"] > self.population * 0.5 and
            random.random() < 0.03):
            self._trigger_pilgrimage()
        
        # Cultural Artifact Creation - high artistry and technology
        if (self.culture_system.traits["artistry"] > 70 and
            self.tech_level > 2.0 and
            random.random() < 0.02):
            self._create_cultural_artifact()

        # NEW: Cultural Festival - high happiness and artistry
        if (self.happiness > 70 and
            self.culture_system.traits["artistry"] > 50 and
            random.random() < 0.1): # 10% chance if conditions are met
            self._trigger_festival()
    
    def _trigger_cultural_renaissance(self):
        """Trigger a cultural renaissance event"""
        artifact_types = ["Epic Poem", "Symphony", "Architectural Masterpiece", 
                         "Philosophical Treatise", "Historical Chronicle"]
        themes = ["Heroism", "Love", "Nature", "Divinity", "Humanity", "Destiny"]
        
        artifact_name = f"{random.choice(artifact_types)} of {random.choice(themes)}"
        artifact_desc = f"A magnificent work that defines the {self.name} cultural renaissance"
        
        self.culture_system.add_artifact(artifact_name, artifact_desc, self.world.year)
        
        # Apply effects
        self.happiness += 20
        self.stability += 15
        self.tech_progress += 0.5  # Big technology boost
        self.resources["wealth"] += self.population * 0.3
        
        renaissance_event = HistoryEvent(
            year=self.world.year,
            event_type="cultural_renaissance",
            civilization=self.name,
            details=f"experienced a cultural renaissance, producing {artifact_name}",
            leader=self.leader.full_title,
            severity="major"
        )
        self.history.append(renaissance_event)
        self.world.history_archive.record_event(renaissance_event)
        
        self.leader.add_achievement(f"Patron of the {self.name} Renaissance")
    
    def _trigger_pilgrimage(self):
        """Trigger a religious pilgrimage event"""
        if not self.religion:
            return
        
        # Apply effects
        self.happiness += 15
        self.stability += 10
        self.culture_system.traits["cohesion"] = min(100, self.culture_system.traits["cohesion"] + 20)
        
        # Cost
        self.resources["wealth"] = max(0, self.resources["wealth"] - self.population * 0.2)
        
        pilgrimage_event = HistoryEvent(
            year=self.world.year,
            event_type="pilgrimage",
            civilization=self.name,
            details=f"undertook a great pilgrimage to holy sites of {self.religion.name}",
            leader=self.leader.full_title,
            severity="normal"
        )
        self.history.append(pilgrimage_event)
        self.world.history_archive.record_event(pilgrimage_event)
    
    def _create_cultural_artifact(self):
        """Create a cultural artifact"""
        artifact_types = ["Crown", "Scepter", "Codex", "Tapestry", "Sculpture", "Relic"]
        materials = ["Golden", "Crystal", "Marble", "Jade", "Obsidian", "Silver"]
        
        artifact_name = f"{random.choice(materials)} {random.choice(artifact_types)}"
        artifact_desc = f"A masterpiece of {self.name} craftsmanship, symbolizing their cultural values"
        
        self.culture_system.add_artifact(artifact_name, artifact_desc, self.world.year)
        
        # Event is recorded by add_artifact
    
    def _trigger_festival(self):
        """Trigger a minor cultural festival."""
        self.happiness = min(100, self.happiness + 5)
        self.culture_system.traits["cohesion"] = min(100, self.culture_system.traits["cohesion"] + 2)
        
        festival_event = HistoryEvent(
            year=self.world.year,
            event_type="festival",
            civilization=self.name,
            details=f"held a grand festival, boosting morale and cultural pride",
            leader=self.leader.full_title,
            severity="minor"
        )
        self.history.append(festival_event)
        self.world.history_archive.record_event(festival_event)
    
    def _handle_crises(self):
        """Handle various crises that can befall the civilization"""
        # Famine
        food_ratio = self.resources["food"] / max(1, self.population * self.BASE_FOOD_CONSUMPTION)
        if food_ratio < 0.5 and random.random() < 0.3:
            self._trigger_famine()
        
        # Rebellion
        if self.stability < 30 and random.random() < 0.2:
            self._trigger_rebellion()
        
        # Economic collapse
        wealth_ratio = self.resources["wealth"] / max(1, self.population)
        if wealth_ratio < 0.3 and self.economic_state == "struggling" and random.random() < 0.1:
            self._trigger_economic_collapse()
    
    def _trigger_famine(self):
        """Trigger a famine event"""
        population_loss = int(self.population * random.uniform(0.1, 0.3))
        self.population = max(100, self.population - population_loss)
        
        self.happiness -= 20
        self.stability -= 15
        
        famine_event = HistoryEvent(
            year=self.world.year,
            event_type="famine",
            civilization=self.name,
            details=f"suffered a famine, losing {population_loss} people",
            leader=self.leader.full_title,
            severity="major"
        )
        self.history.append(famine_event)
        self.world.history_archive.record_event(famine_event)
    
    def _trigger_rebellion(self):
        """Trigger a rebellion event"""
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
        else:  # civil_war
            self.stability -= 40
            self.happiness -= 25
            self.army_size = int(self.army_size * 0.7)  # Military divided
            details = "descended into civil war"
            severity = "catastrophic"
        
        rebellion_event = HistoryEvent(
            year=self.world.year,
            event_type="rebellion",
            civilization=self.name,
            details=details,
            leader=self.leader.full_title,
            severity=severity
        )
        self.history.append(rebellion_event)
        self.world.history_archive.record_event(rebellion_event)
    
    def _trigger_economic_collapse(self):
        """Trigger an economic collapse event"""
        wealth_loss = int(self.resources["wealth"] * random.uniform(0.3, 0.7))
        self.resources["wealth"] = max(0, self.resources["wealth"] - wealth_loss)
        
        self.happiness -= 25
        self.stability -= 20
        
        collapse_event = HistoryEvent(
            year=self.world.year,
            event_type="economic_collapse",
            civilization=self.name,
            details=f"suffered economic collapse, losing {wealth_loss} wealth",
            leader=self.leader.full_title,
            severity="major"
        )
        self.history.append(collapse_event)
        self.world.history_archive.record_event(collapse_event)

    def _record_annual_summary(self):
        """Record an annual summary event (only if significant change)"""
        # Simplified: just record every 10 years
        if self.world.year % 10 != 0:
            return
            
        summary_event = HistoryEvent(
            year=self.world.year,
            event_type="annual_summary",
            civilization=self.name,
            details=f"Pop: {self.population}, Wealth: {int(self.resources['wealth'])}, Stability: {int(self.stability)}%",
            leader=self.leader.full_title,
            severity="minor"
        )
        self.history.append(summary_event)
        self.world.history_archive.record_event(summary_event)
    
    def get_recent_history(self, years=5):
        """Get recent history events for this civilization"""
        current_year = self.world.year
        return [event for event in self.history if current_year - event.year <= years]
    
    def display_status(self):
        """Display current civilization status"""
        print(f"\n=== {self.name} ===")
        print(f"Leader: {self.leader.full_title} (Age: {self.leader.age}, Ruled: {self.leader.years_ruled} years)")
        print(f"Population: {self.population:,}")
        print(f"Technology Level: {self.tech_level:.1f} (Progress: {self.tech_progress:.1%})")
        print(f"Resources: Food={int(self.resources['food'])}, Metal={int(self.resources['metal'])}, Wealth={int(self.resources['wealth'])}")
        print(f"Happiness: {int(self.happiness)}/100, Stability: {int(self.stability)}/100")
        print(f"Religion: {self.religion.name if self.religion else 'None'}")
        print(f"Society: Farmers={self.society['farmers']:.0%}, Merchants={self.society['merchants']:.0%}, " +
              f"Soldiers={self.society['soldiers']:.0%}, Scholars={self.society['scholars']:.0%}, Nobles={self.society['nobles']:.0%}")
        print(f"Army Size: {self.army_size}")
        if self.war_with:
            print(f"At War with: {self.war_with}")
        if self.peace_treaty_years > 0:
            print(f"Peace Treaty: {self.peace_treaty_years} years remaining")

    def to_dict(self):
        """Convert civilization to dictionary for saving"""
        return {
            'id': self.id,
            'name': self.name,
            'population': self.population,
            'technology': self.technology,
            'map_position': self.map_position,
            'relationships': self.relationships,
            'traits': self.traits,
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
            'leader': self.leader.to_dict(),
            'leader_history': [leader.to_dict() for leader in self.leader_history],
            'culture_system': self.culture_system.to_dict(),
            'religion_name': self.religion.name if self.religion else None,
            'history': [event.to_dict() for event in self.history]
        }
    
    @classmethod
    def from_dict(cls, data, world):
        """Create civilization from saved data"""
        civ = cls(world, data['id'], data['name'], data['population'], 
                 data['technology'], data['map_position'])
        
        civ.relationships = data['relationships']
        civ.traits = data['traits']
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
        
        # Reconstruct leader and history
        civ.leader = Leader.from_dict(data['leader'])
        civ.leader_history = [Leader.from_dict(ld) for ld in data['leader_history']]
        
        # Reconstruct culture system
        civ.culture_system = CultureSystem.from_dict(data['culture_system'], civ)
        
        # Store religion name (will be re-linked by World)
        civ.religion_name_to_load = data.get('religion_name')
        
        # Reconstruct history
        civ.history = [HistoryEvent.from_dict(event_data) for event_data in data['history']]
        
        return civ

"""
====================== ENHANCED WORLD CLASS ======================
(Merged: Combines World logic from all versions)
"""

class World:
    """Manages the game world with civilizations and history"""
    
    def __init__(self, num_civilizations=4, width=40, height=20, seed=None):
        self.year = 0
        self.rng = random.Random(seed) if seed is not None else random.Random()
        
        # Core systems
        self.map = WorldMap(width, height, seed=self.rng.randint(0, 1000000))
        self.climate = ClimateSystem(rng=self.rng)
        
        # DEEP HISTORY SYSTEM
        self.history_archive = HistoryArchive()
        self.legends_mode = LegendsMode(self.history_archive)
        
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

    def _initialize_relationships(self, civ):
        """Set initial relationships for a new civ"""
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
        
        # Update all civilizations
        for civ in self.civilizations:
            civ.update_year()
        
        # Update religion system (spread, etc.)
        self.religion_system.update_yearly()
        
        # Handle inter-civilization interactions
        self._handle_diplomatic_interactions()
        self._handle_wars()
    
    def _handle_diplomatic_interactions(self):
        """Handle diplomatic interactions between civilizations"""
        for i, civ1 in enumerate(self.civilizations):
            for civ2 in self.civilizations[i+1:]:
                # Update relationship drift
                self._update_relationship_drift(civ1, civ2)
                
                # Check if already at war
                if civ1.war_with == civ2.name or civ2.war_with == civ1.name:
                    continue
                
                relation = civ1.relationships.get(civ2.name, 0)
                
                # Chance of diplomatic event based on relationship
                if random.random() < 0.1:  # 10% chance per pair per year
                    if relation > 0.7:
                        self._form_alliance(civ1, civ2)
                    
                    # NEW: Holy War check
                    elif relation < -0.5 and civ1.religion and civ2.religion:
                        religious_compat = civ1.religion.calculate_compatibility(civ2.religion)
                        # If relations are bad AND religions are incompatible
                        if religious_compat < 0.1 and random.random() < 0.25:
                            self._declare_holy_war(civ1, civ2)
                        elif relation < -0.7: # Standard war declaration
                            self._declare_war(civ1, civ2)
                    
                    elif relation < -0.7: # Standard war declaration (if no religion)
                        self._declare_war(civ1, civ2)
                    elif relation > 0.3:
                        self._improve_relations(civ1, civ2)
                    elif relation < -0.3:
                        self._deteriorate_relations(civ1, civ2)
    
    def _update_relationship_drift(self, civ1, civ2):
        """Apply passive relationship drift based on culture, religion, etc."""
        if civ1.name not in civ2.relationships:
             civ2.relationships[civ1.name] = random.uniform(-0.5, 0.5)
        if civ2.name not in civ1.relationships:
             civ1.relationships[civ2.name] = random.uniform(-0.5, 0.5)
             
        # Base drift
        drift = random.uniform(-0.05, 0.05)
        
        # Religious compatibility
        if civ1.religion and civ2.religion:
            compatibility = civ1.religion.calculate_compatibility(civ2.religion)
            drift += (compatibility - 0.5) * 0.1 # -0.05 to +0.05
        
        # Cultural similarity
        cultural_similarity = civ1._calculate_cultural_similarity(civ2)
        drift += (cultural_similarity - 0.5) * 0.1 # -0.05 to +0.05
        
        # Leader diplomacy
        drift += civ1.leader.get_trait_modifiers()["diplomacy_bonus"] * 0.02
        drift += civ2.leader.get_trait_modifiers()["diplomacy_bonus"] * 0.02
        
        civ1.relationships[civ2.name] = max(-1.0, min(1.0, civ1.relationships[civ2.name] + drift))
        civ2.relationships[civ1.name] = civ1.relationships[civ2.name]

    def _handle_wars(self):
        """Handle ongoing wars"""
        for civ in self.civilizations:
            if civ.war_with:
                enemy = next((c for c in self.civilizations if c.name == civ.war_with), None)
                if not enemy:
                    # Enemy might have been destroyed
                    civ.war_with = None
                    continue
                    
                # Simulate battle
                if random.random() < 0.3:  # 30% chance of battle per year
                    self._simulate_battle(civ, enemy)
                
                # Chance of peace treaty
                if random.random() < 0.2:
                    self._make_peace(civ, enemy)
    
    def _form_alliance(self, civ1, civ2):
        """Form an alliance between two civilizations"""
        alliance_event = HistoryEvent(
            year=self.year,
            event_type="alliance_formed",
            civilization=civ1.name,
            details=f"{civ1.name} and {civ2.name} formed a defensive alliance",
            leader=f"{civ1.leader.full_title}",
            other_civ=civ2.name,
            severity="major"
        )
        self.history_archive.record_event(alliance_event)
        
        civ1.relationships[civ2.name] = min(1.0, civ1.relationships.get(civ2.name, 0) + 0.2)
        civ2.relationships[civ1.name] = min(1.0, civ2.relationships.get(civ1.name, 0) + 0.2)
    
    def _declare_war(self, civ1, civ2):
        """Declare war between two civilizations"""
        if civ1.war_with or civ2.war_with:
            return  # Already at war
        
        civ1.war_with = civ2.name
        civ2.war_with = civ1.name
        
        war_event = HistoryEvent(
            year=self.year,
            event_type="war_declared",
            civilization=civ1.name,
            details=f"{civ1.name} declared war on {civ2.name}",
            leader=f"{civ1.leader.full_title}",
            other_civ=civ2.name,
            severity="major"
        )
        self.history_archive.record_event(war_event)
    
    def _improve_relations(self, civ1, civ2):
        """Improve relations between two civilizations"""
        improvement_event = HistoryEvent(
            year=self.year,
            event_type="relations_improved",
            civilization=civ1.name,
            details=f"Relations improved between {civ1.name} and {civ2.name}",
            leader=f"{civ1.leader.full_title}",
            other_civ=civ2.name,
            severity="normal"
        )
        self.history_archive.record_event(improvement_event)
        
        civ1.relationships[civ2.name] = min(1.0, civ1.relationships.get(civ2.name, 0) + 0.1)
        civ2.relationships[civ1.name] = min(1.0, civ2.relationships.get(civ1.name, 0) + 0.1)
    
    def _deteriorate_relations(self, civ1, civ2):
        """Deteriorate relations between two civilizations"""
        deterioration_event = HistoryEvent(
            year=self.year,
            event_type="relations_worsened",
            civilization=civ1.name,
            details=f"Relations deteriorated between {civ1.name} and {civ2.name}",
            leader=f"{civ1.leader.full_title}",
            other_civ=civ2.name,
            severity="normal"
        )
        self.history_archive.record_event(deterioration_event)
        
        civ1.relationships[civ2.name] = max(-1.0, civ1.relationships.get(civ2.name, 0) - 0.1)
        civ2.relationships[civ1.name] = max(-1.0, civ2.relationships.get(civ1.name, 0) - 0.1)
    
    def _simulate_battle(self, civ1, civ2):
        """Simulate a battle between two civilizations at war"""
        # Get cultural/leader modifiers
        mods1 = civ1.culture_system.get_military_modifiers()
        mods2 = civ2.culture_system.get_military_modifiers()
        
        civ1_power = civ1.army_size * civ1.tech_level * (1 + mods1.get("morale_bonus", 0))
        civ2_power = civ2.army_size * civ2.tech_level * (1 + mods2.get("morale_bonus", 0))
        
        total_power = civ1_power + civ2_power
        if total_power == 0:
            return
        
        civ1_victory_chance = civ1_power / total_power
        
        if random.random() < civ1_victory_chance:
            winner, loser = civ1, civ2
        else:
            winner, loser = civ2, civ1
        
        # Calculate losses
        winner_losses = int(winner.army_size * random.uniform(0.1, 0.3))
        loser_losses = int(loser.army_size * random.uniform(0.2, 0.5))
        
        winner.army_size = max(0, winner.army_size - winner_losses)
        loser.army_size = max(0, loser.army_size - loser_losses)
        
        # Update happiness and stability
        winner.happiness += 5
        winner.stability += 5
        loser.happiness -= 15
        loser.stability -= 10
        
        battle_event = HistoryEvent(
            year=self.year,
            event_type="battle",
            civilization=winner.name,
            details=f"{winner.name} defeated {loser.name} in battle ({winner_losses}/{loser_losses} losses)",
            leader=winner.leader.full_title,
            other_civ=loser.name,
            severity="major"
        )
        self.history_archive.record_event(battle_event)
        
        # Check if war should end due to decisive victory
        if loser.army_size < loser.population * 0.01:  # Less than 1% population in army
            self._make_peace(winner, loser)
    
    def _make_peace(self, civ1, civ2):
        """Make peace between two warring civilizations"""
        if not civ1.war_with and not civ2.war_with:
            return # Already at peace
            
        civ1.war_with = None
        civ2.war_with = None
        civ1.peace_treaty_years = 5
        civ2.peace_treaty_years = 5
        
        peace_event = HistoryEvent(
            year=self.year,
            event_type="peace_treaty",
            civilization=civ1.name,
            details=f"{civ1.name} and {civ2.name} signed a peace treaty",
            leader=f"{civ1.leader.full_title}",
            other_civ=civ2.name,
            severity="major"
        )
        self.history_archive.record_event(peace_event)
    
    def display_world_status(self):
        """Display current status of all civilizations"""
        print(f"\n{'='*60}")
        print(f"WORLD STATUS - Year {self.year}")
        print(f"{'='*60}")
        print(f"Season: {self.climate.season}, Temperature: {self.climate.temperature:.1f}°C, Rainfall: {self.climate.rainfall:.1f}mm")
        
        total_population = sum(civ.population for civ in self.civilizations)
        total_wealth = sum(civ.resources['wealth'] for civ in self.civilizations)
        active_wars = sum(1 for civ in self.civilizations if civ.war_with) // 2
        
        print(f"\nWorld Totals: Population: {total_population:,}, Wealth: {int(total_wealth):,}, Wars: {active_wars}")
        
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
            print(f"- {event}")
    
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
    
    def display_cultural_summary(self):
        """Display detailed cultural information"""
        print(f"\n{'='*60}")
        print(f"CULTURAL SUMMARY - YEAR {self.year}")
        print(f"{'='*60}")
        
        for civ in self.civilizations:
            culture = civ.culture_system.traits
            print(f"\n{civ.name} Culture:")
            print(f"  Tradition: {culture['tradition']:.2f} | "
                  f"Collectivism: {culture['collectivism']:.2f} | "
                  f"Honor: {culture['honor']:.2f}")
            print(f"  Artistry: {culture['artistry']}/100 | "
                  f"Spirituality: {culture['spirituality']}/100 | "
                  f"Cohesion: {int(culture['cohesion'])}/100")
            print(f"  Industriousness: {culture['industriousness']:.2f} | "
                  f"Militarism: {culture['militarism']:.2f} | "
                  f"Diplomacy: {culture['diplomacy']:.2f}")
            
            if civ.culture_system.artifacts:
                print(f"  Artifacts: {len(civ.culture_system.artifacts)}")
                for artifact in civ.culture_system.artifacts[-3:]: # Show last 3
                    print(f"    - {artifact['name']} ({artifact['year_created']})")
    
    def display_religious_summary(self):
        """Display detailed religious information"""
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
            
            if religion.schisms:
                print(f"  Schisms: {len(religion.schisms)}")
    
    def to_dict(self):
        """Convert world state to dictionary for saving"""
        return {
            'year': self.year,
            'map': self.map.to_dict(),
            'climate': self.climate.to_dict(),
            'civilizations': [civ.to_dict() for civ in self.civilizations],
            'history_archive': self.history_archive.to_dict(),
            'religion_system': self.religion_system.to_dict()
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
        
        # Reconstruct history archive FIRST
        world.history_archive = HistoryArchive.from_dict(data['history_archive'])
        world.legends_mode = LegendsMode(world.history_archive)
        
        # Reconstruct religion system
        world.religion_system = ReligionSystem.from_dict(data['religion_system'], world)
        
        # Reconstruct civilizations
        world.civilizations = [
            Civilization.from_dict(civ_data, world) 
            for civ_data in data['civilizations']
        ]
        
        # Re-link religion objects to civilizations
        for civ in world.civilizations:
            if hasattr(civ, 'religion_name_to_load') and civ.religion_name_to_load:
                religion = world.religion_system.get_religion_by_name(civ.religion_name_to_load)
                if religion:
                    civ.religion = religion
                    religion.add_follower(civ.name) # Ensure follower list is correct
            del civ.religion_name_to_load # Clean up
        
        return world

"""
====================== MAIN EXECUTION (INTERACTIVE) ======================
(Merged from Pre-Alpha 7 and Legends & Lore)
"""

def save_world(world, filename="world_save.json"):
    """Saves the entire world state to a JSON file"""
    try:
        with open(filename, 'w') as f:
            json.dump(world.to_dict(), f, indent=2)
        print(f"\n✅ World saved successfully to {filename}")
    except Exception as e:
        print(f"\n❌ Error saving world: {e}")

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
        return None

def main():
    """Main function to run the interactive Fantasy Engine"""
    
    print("="*80)
    print("      FANTASY ENGINE - CULTURE & LEGENDS EDITION (PA-11)")
    print("="*80)
    
    world = None
    
    while not world:
        print("\n[1] Start a new world")
        print("[2] Load a saved world")
        print("[q] Quit")
        choice = input("Choose an option: ").strip().lower()

        if choice == '1':
            # --- New World Creation ---
            seed_input = input("Enter a seed number (or leave blank for random): ").strip()
            seed = None
            if seed_input:
                try:
                    seed = int(seed_input)
                except ValueError:
                    print("Invalid seed. Using a random seed.")
            
            # Get other world parameters
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
            # --- Load World ---
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
                        "[v] View Legends  |  [c] View Culture  |  [r] View Religion\n"
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
                print("[3] Story View (last 30 years)")
                view_choice = input("Choose view: ").strip()
                
                target_civ = None
                if view_choice in ['2', '3']:
                    civ_name = input("Enter Civilization name: ").strip()
                    if any(c.name.lower() == civ_name.lower() for c in world.civilizations):
                        target_civ = next(c.name for c in world.civilizations if c.name.lower() == civ_name.lower())
                    else:
                        print(f"Civilization '{civ_name}' not found.")
                        continue
                
                if view_choice == '1':
                    world.display_legends("world", years=50)
                elif view_choice == '2' and target_civ:
                    world.display_legends("civilization", target_civ)
                elif view_choice == '3' and target_civ:
                    world.display_legends("story", target_civ, years=30)
                else:
                    print("Invalid choice.")
            
            elif cmd == 'c':
                world.display_cultural_summary()
            
            elif cmd == 'r':
                world.display_religious_summary()

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

if __name__ == "__main__":
    main()