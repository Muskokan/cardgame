import os
import uuid
import json
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum, auto
from colors import Colors

class Phase(Enum):
    SETUP = auto()
    DRAW = auto()
    STOCK_CARD_SELECTION = auto()
    REACTION_SELECTION = auto()
    TARGETING = auto()
    PAYING_COSTS = auto()
    RESOLUTION = auto()
    REVIEW = auto()
    GAME_OVER = auto()

class TargetRequirement(Enum):
    NONE = 0
    PLAYER = 1             # Targeted opponent (e.g. Blank/Check)
    OPPONENT_STOCK = 2     # Specific card in opponent stockpile (e.g. Crush, Redact)
    OWN_STOCK = 3          # Specific card in own stockpile (e.g. Betray cost)
    EXTRA_PITCH = 7        # Pitch one extra card from hand (e.g. Hush cost)
    REDACT_COST = 8        # Modal: Pitch 1 card OR Destroy 1 stockpile card (Redact cost)
    GRAVEYARD = 9          # Target a card in the graveyard
    POT_CARD = 10          # Target a card currently in the pot (e.g. Hush)
    ANY_STOCK = 11         # Target any card in any player's stockpile

class Tag:
    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None):
        self.name = name
        self.params = params or {}
        
    def to_dict(self):
        return {"name": self.name, "params": self.params}

    def __str__(self):
        if self.params:
            return f"{self.name}({self.params})"
        return self.name

class Effect:
    def __init__(self, type_: str, target: str, amount: int = 1, destination: str = ""):
        self.type = type_
        self.target = target
        self.amount = amount
        self.destination = destination

    def to_dict(self):
        return {
            "type": self.type,
            "target": self.target,
            "amount": self.amount,
            "destination": self.destination
        }

class Ability:
    def __init__(self, name: str, description: str, tags_data: list, target_reqs_data: list, console_description: str = "", effects_data: Optional[list] = None):
        self.name = name
        self.description = description
        self.console_description = console_description if console_description else description
        self.tags = []
        for t in tags_data:
            if isinstance(t, str):
                self.tags.append(Tag(t))
            elif isinstance(t, dict):
                # e.g., {"type": "Choice", "options": ["Pitch", "Burn"]}
                self.tags.append(Tag(t.get("type", "Unknown"), t))
                
        self.target_requirements = []
        for req in target_reqs_data:
            try:
                self.target_requirements.append(getattr(TargetRequirement, req))
            except AttributeError:
                pass

        self.effects: List[Effect] = []
        if effects_data is not None:
            for e in effects_data:
                self.effects.append(Effect(e.get("type", ""), e.get("target", ""), e.get("amount", 1), e.get("destination", "")))

    def has_tag(self, tag_name: str) -> bool:
        return any(t.name == tag_name for t in self.tags)
        
    def get_tag(self, tag_name: str) -> Optional[Tag]:
        for t in self.tags:
            if t.name == tag_name:
                return t
        return None

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "tags": [t.to_dict() for t in self.tags],
            "target_requirements": [req.name for req in self.target_requirements],
            "console_description": self.console_description,
            "effects": [e.to_dict() for e in self.effects]
        }

    def get_dynamic_description(self) -> str:
        """Generates a concise console description based on tags and effects."""
        parts = []
        
        # 1. Costs/Tags
        if self.has_tag("Pitch"): parts.append("[P]")
        if self.has_tag("Burn"): parts.append("[B]")
        
        # 2. Effects
        effect_texts = []
        for eff in self.effects:
            t = eff.type
            amt = eff.amount
            
            if t == "DRAW_CARDS":
                effect_texts.append(f"Draw {amt}")
            elif t == "FORCE_DISCARD":
                effect_texts.append("Opp discard")
            elif t == "COUNTER_SPELL":
                effect_texts.append("Counter")
            elif t == "BOUNCE_CARD":
                effect_texts.append("Bounce")
            elif t == "COPY_ABILITY":
                effect_texts.append("Repeat")
            elif t == "MOVE_CARD":
                dest = "Hand" if eff.destination == "hand" else "Top"
                effect_texts.append(f"Regen->{dest}")
            elif t == "STEAL_CARD":
                effect_texts.append("Steal")
            elif t == "DESTROY_CARD":
                effect_texts.append("Destroy")
                
        if effect_texts:
            parts.append(" ".join(effect_texts))
        else:
            parts.append(self.console_description)
            
        return " ".join(parts).strip()

    def execute(self, state: 'GameState', action: 'Action', view, depth: int = 0):
        # Recursion Guard
        if depth > 10:
            if view:
                view.log(f"  [FIZZLE] {self.name} failed due to excessive recursion.")
            else:
                state.log_event("EFFECT_RESULT", {"message": f"  [FIZZLE] {self.name} failed due to excessive recursion."})
            return
        from effects import resolve_effects
        return resolve_effects(self, state, action, view, depth)

class Card:
    def __init__(self, react_ability: Ability, stockpile_ability: Ability):
        self.id = str(uuid.uuid4())
        self.react_ability = react_ability
        self.stockpile_ability = stockpile_ability
        self.owner: Optional['Player'] = None

    @property
    def name(self) -> str:
        return f"{self.react_ability.name}/{self.stockpile_ability.name}"
        
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "react_name": self.react_ability.name,
            "react_desc": self.react_ability.description,
            "stock_name": self.stockpile_ability.name,
            "stock_desc": self.stockpile_ability.description
        }

    @property
    def react_requirements(self) -> List[TargetRequirement]:
        return self.react_ability.target_requirements
        
    @property
    def stockpile_requirements(self) -> List[TargetRequirement]:
        return self.stockpile_ability.target_requirements
        
    def execute_react(self, state, action, view):
        return self.react_ability.execute(state, action, view)
        
    def execute_stockpile(self, state, action, view):
        return self.stockpile_ability.execute(state, action, view)
        
    def __str__(self):
        return self.name
        
    def __repr__(self):
        return f"Card({self.name}, {self.id[:6]})"
        
    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.id == other.id

@dataclass
class BotProfile:
    name: str = "Standard"
    base_reaction_chance: float = 0.20 # 0.0 to 1.0
    aggression_weight: float = 1.0 # 0.0 (random) to 1.0 (strict threat evaluation)
    grudge_memory_weight: float = 1.0 # Multiplier for grudges (e.g., 1.5x)
    tempo_hand_threshold: int = 5 # Hand size needed to trigger early-game tempo Hush counters (higher means less likely)
    combo_snatch_chance: float = 0.0 # 0.0 to 1.0 probability to attempt a Reprise Snatch on costs
    win_con_flexibility: float = 0.5 # Threshold needed to commit to monochrome lane based on dupes.

    def to_dict(self):
        return {
            "name": self.name,
            "base_reaction_chance": self.base_reaction_chance,
            "aggression_weight": self.aggression_weight,
            "grudge_memory_weight": self.grudge_memory_weight,
            "tempo_hand_threshold": self.tempo_hand_threshold,
            "combo_snatch_chance": self.combo_snatch_chance,
            "win_con_flexibility": self.win_con_flexibility
        }

class Player:
    def __init__(self, player_id: int, name: str, is_bot: bool = False, bot_profile: Optional[BotProfile] = None):
        self.player_id = player_id
        self.name = name
        self.is_bot = is_bot
        self.bot_profile = bot_profile if bot_profile else BotProfile() if is_bot else None
        self.hand = []
        self.stockpile = []
        self.external_id: Optional[str] = None
        
    def to_dict(self, include_hand: bool = True):
        d = {
            "player_id": self.player_id,
            "name": self.name,
            "is_bot": self.is_bot,
            "bot_profile": self.bot_profile.to_dict() if self.bot_profile else None,
            "external_id": self.external_id,  # Always included so frontend can identify local player
            "hand": [c.to_dict() for c in self.hand] if include_hand else len(self.hand),
            "stockpile": [c.to_dict() for c in self.stockpile]
        }
        return d

    def __str__(self):
        return self.name

class Action:
    def __init__(self, source_player: Player, source_card: Card, ability_type: str, 
                 target_card: Optional[Card] = None, target_player: Optional[Player] = None, copied_card_name: Optional[str] = None,
                 triggered: bool = False):
        self.source_player = source_player
        self.source_card = source_card
        self.ability_type = ability_type 
        self.target_card = target_card
        self.target_player = target_player
        self.copied_card_name = copied_card_name 
        self.triggered = triggered
        self.history_idx: Optional[int] = None        
        self.recap_idx: Optional[int] = None
        self.generator = None

    def to_dict(self):
        return {
            "source_player_name": self.source_player.name,
            "source_player_id": self.source_player.external_id,
            "source_card_name": self.source_card.name,
            "source_card_id": self.source_card.id,
            "ability_type": self.ability_type,
            "target_card_name": self.target_card.name if self.target_card else None,
            "target_card_id": self.target_card.id if self.target_card else None,
            "target_player_name": self.target_player.name if self.target_player else None,
            "target_player_id": self.target_player.external_id if self.target_player else None,
            "copied_card_name": self.copied_card_name
        }

    def __str__(self):
        t_str = ""
        if self.target_card:
            if isinstance(self.target_card, Action):
                 t_str = f" targeting [{self.target_card.source_player.name}'s {self.target_card.source_card.name}]"
            else:
                 t_str = f" targeting [{self.target_card.name}]"
        elif self.target_player:
            t_str = f" targeting [{self.target_player.name}]"
        elif self.copied_card_name:
            t_str = f" copying [{self.copied_card_name}]"
            
        ability = self.source_card.react_ability.name if self.ability_type == 'react' else self.source_card.stockpile_ability.name
        return f"{self.source_player.name}'s {ability}{t_str}"

# Effect resolution logic has been moved to effects.py.


def generate_full_deck() -> List[Card]:
    deck = []
    json_path = os.path.join(os.path.dirname(__file__), "cards.json")
    with open(json_path, "r") as f:
        data = json.load(f)
        
    abilities_data = data["abilities"]
    roster = data["roster"]
    
    for pairing in roster:
        react_name = pairing["react_name"]
        stock_name = pairing["stock_name"]
        count = pairing["count"]
        r_data = abilities_data[react_name]
        s_data = abilities_data[stock_name]
        
        for _ in range(count):
            react_ability = Ability(
                react_name, 
                r_data.get("description", "No description."), 
                r_data.get("tags", []), 
                r_data.get("target_requirements", []),
                r_data.get("console_description", ""),
                r_data.get("effects", [])
            )
            stock_ability = Ability(
                stock_name, 
                s_data.get("description", "No description."), 
                s_data.get("tags", []), 
                s_data.get("target_requirements", []),
                s_data.get("console_description", ""),
                s_data.get("effects", [])
            )
            
            deck.append(Card(react_ability, stock_ability))
            
    return deck
