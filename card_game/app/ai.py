import time
import random
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from engine import GameState
    from models import Player, Card, BotProfile, TargetRequirement
else:
    # Runtime imports for things we need that don't cause circularity
    # or are needed for base class/logic
    from models import Player, Card, BotProfile, TargetRequirement

# ==========================================
# DEFAULT BOT PROFILES
# ==========================================
AGGRESSIVE_PROFILE = BotProfile(
    name="Aggressive",
    base_reaction_chance=0.45,
    aggression_weight=1.8,
    grudge_memory_weight=1.5,
    tempo_hand_threshold=6,
    combo_snatch_chance=0.0,
    win_con_flexibility=0.8
)

DEFENSIVE_PROFILE = BotProfile(
    name="Defensive",
    base_reaction_chance=0.20,
    aggression_weight=0.75,
    grudge_memory_weight=1.8,
    tempo_hand_threshold=4,
    combo_snatch_chance=0.0,
    win_con_flexibility=0.4
)

COMBO_PROFILE = BotProfile(
    name="Combo",
    base_reaction_chance=0.25,
    aggression_weight=1.0,
    grudge_memory_weight=1.0,
    tempo_hand_threshold=5,
    combo_snatch_chance=1.5,
    win_con_flexibility=0.3
)

CHAOTIC_PROFILE = BotProfile(
    name="Chaotic",
    base_reaction_chance=0.25,
    aggression_weight=0.0,
    grudge_memory_weight=0.0,
    tempo_hand_threshold=6,
    combo_snatch_chance=0.2,
    win_con_flexibility=0.5
)

RUTHLESS_PROFILE = BotProfile(
    name="Ruthless",
    base_reaction_chance=0.35,
    aggression_weight=2.0,
    grudge_memory_weight=2.0,
    tempo_hand_threshold=4,
    combo_snatch_chance=1.5,
    win_con_flexibility=0.2
)

# Shared lookup — used by engine.py and room_manager.py
BOT_PROFILES = {
    "Aggressive": AGGRESSIVE_PROFILE,
    "Defensive":  DEFENSIVE_PROFILE,
    "Ruthless":   RUTHLESS_PROFILE,
    "Combo":      COMBO_PROFILE,
    "Chaotic":    CHAOTIC_PROFILE,
}

class HistoryAnalyzer:
    @staticmethod
    def get_aggression_score(subject: Player, target: Player, state: 'GameState') -> int:
        """Counts how many times 'target' has targeted 'subject' in the full history."""
        score = 0
        for entry in state.full_history:
            data = entry.get("data", {})
            msg = data.get("message", "")
            if f"targeting [{subject.name}'s" in msg or f"targeting [{subject.name}]" in msg:
                if "[SUCCESS]" in msg and f"{target.name}" in msg and f"{subject.name}" in msg:
                    score += 2
        return score

    @staticmethod
    def get_cause_velocity(player: Player, state: 'GameState', window: int = 10) -> float:
        """Calculates how many cards the player has causeed in the last N turns."""
        causes = 0
        start_turn = max(1, state.turn_number - window)
        for entry in state.full_history:
            if entry["turn"] < start_turn: continue
            if entry["event"] == "CARD_CAUSEED" and entry["data"].get("player") == player.name:
                causes += 1
        return causes / window

    @staticmethod
    def was_countered_recently(player: Player, state: 'GameState') -> bool:
        """Checks if the player's last action was countered."""
        for entry in reversed(state.full_history):
            if entry["event"] == "NARRATIVE":
                msg = entry["data"].get("message", "")
                if "[SUCCESS] Stagnation counters" in msg and player.name in msg:
                    return True
                if "sequenced" in msg and player.name in msg: 
                    return False
        return False

def _is_already_handled(target_card, state: 'GameState') -> bool:
    """Checks if a card in the nexus is already being handled on the stack."""
    for action in state.stack:
        ability = action.source_card.react_ability if action.ability_type == 'react' else action.source_card.sequence_ability
        if any(e.type in ["COUNTER_SPELL", "BOUNCE_CARD", "DESTROY_CARD", "STEAL_CARD"] for e in ability.effects):
            if action.target_card == target_card:
                return True
    return False

def evaluate_advantage(player: Player, state: 'GameState') -> float:
    """Calculates a holistic score representing a player's standing in the game."""
    score = 0.0
    if player.sequence:
        counts = {}
        for c in player.sequence:
            counts[c.name] = counts.get(c.name, 0) + 1
        max_of_kind = max(counts.values())
        unique_types = len(counts)
        score += (max_of_kind ** 2) * 10.0
        score += (unique_types ** 2) * 8.0
        if max_of_kind >= 3: score += 50
        if unique_types >= 4: score += 50
    score += len(player.hand) * 5.0
    return score

def is_near_win(player: Player) -> bool:
    """Returns True if the player is one card away from winning."""
    sp = player.sequence
    if not sp: return False
    
    # 4 of a kind check
    counts = {}
    for c in sp:
        counts[c.name] = counts.get(c.name, 0) + 1
        if counts[c.name] >= 3: return True
        
    # 5 unique check
    unique_names = set(c.name for c in sp)
    if len(unique_names) >= 4: return True
    
    return False

def predict_nexus_outcome(player: Player, state: 'GameState') -> float:
    """Simulates player advantage after the current stack resolves."""
    predicted_score = evaluate_advantage(player, state)
    for action in state.stack:
        if action.source_card not in state.nexus or _is_already_handled(action.source_card, state): continue
        ability = action.source_card.react_ability if action.ability_type == 'react' else action.source_card.sequence_ability
        if not ability: continue
        targets_us = (action.target_player == player) or (action.target_card and action.target_card in player.sequence)
        for eff in ability.effects:
            if targets_us:
                if eff.type == "FORCE_DISCARD": predicted_score -= 10.0
                if eff.type == "BOUNCE_CARD": predicted_score -= 30.0
                if eff.type == "DESTROY_CARD": predicted_score -= 40.0
                if eff.type == "STEAL_CARD": predicted_score -= 50.0
            if action.source_player == player:
                if eff.type == "DRAW_CARDS": predicted_score += (eff.amount * 5.0)
                if eff.type == "MOVE_CARD" and eff.destination == "hand": predicted_score += 10.0
    return predicted_score

def bot_choose_cause(bot: Player, state: 'GameState') -> int:
    """Returns the index of the card to cause."""
    
    def is_valuable_cause(card) -> bool:
        ability = card.sequence_ability
        if not ability: return False
        reqs = ability.target_requirements
        opponents = [p for p in state.players if p != bot]
        if TargetRequirement.GRAVEYARD in reqs and not state.graveyard: return False
        if TargetRequirement.OPPONENT_CAUSE in reqs and not any(op.sequence for op in opponents): return False
        if TargetRequirement.ANY_CAUSE in reqs and not any(op.sequence for op in opponents): return False
        if TargetRequirement.PLAYER in reqs and not any(op.hand for op in opponents): return False
        
        # COST CHECK
        for tag in ability.tags:
            if tag.name == "Entropy" and len(bot.hand) <= 1: return False # Need at least ONE OTHER card to pitch
            if tag.name == "Sever" and not bot.sequence: return False
            if tag.name == "Choice":
                options = tag.params.get("options", [])
                can_entropy = "Entropy" in options and len(bot.hand) >= 2 # Card itself + 1 to pitch
                can_sever = "Sever" in options and len(bot.sequence) >= 1
                if not (can_entropy or can_sever): return False

        return True

    sequence_names = [c.name for c in bot.sequence]
    unique_names = set(sequence_names)
    
    # Win Condition Priority
    if len(unique_names) >= 4:
        for idx, card in enumerate(bot.hand):
            if card.name not in unique_names and is_valuable_cause(card): return idx
    for idx, card in enumerate(bot.hand):
        if card.name in sequence_names and sequence_names.count(card.name) < 4 and is_valuable_cause(card): return idx
            
    # Scoring-based choice
    valuable_indices = [i for i, c in enumerate(bot.hand) if is_valuable_cause(c)]
    if not valuable_indices: return random.randint(0, len(bot.hand) - 1)
        
    scores = {}
    profile = bot.bot_profile
    for idx in valuable_indices:
        card = bot.hand[idx]
        score = 10.0
        ability = card.sequence_ability
        is_aggressive = any(e.type in ["DESTROY_CARD", "STEAL_CARD", "FORCE_DISCARD"] for e in ability.effects)
        if is_aggressive or TargetRequirement.PLAYER in ability.target_requirements or TargetRequirement.OPPONENT_CAUSE in ability.target_requirements:
            score += 20.0 * profile.aggression_weight
        if any(e.type == "DRAW_CARDS" for e in ability.effects): score += 15.0
        if any(e.type in ["COPY_ABILITY", "MOVE_CARD"] for e in ability.effects): score += 20.0 * profile.combo_snatch_chance
        score += random.uniform(0, 5.0)
        scores[idx] = score
    return max(scores.keys(), key=lambda k: scores[k])

def bot_choose_reaction(bot: Player, state: 'GameState') -> int:
    """Returns the index of the card to use as a reaction, or -1 to pass."""
    if not bot.hand: return -1
    
    def is_usable_reaction(card) -> bool:
        ability = card.react_ability
        if not ability: return False
        if ability.has_tag("Entropy") and len(bot.hand) <= 1: return False # Reaction itself + 1 to pitch
        if ability.has_tag("Sever") and not bot.sequence: return False
        if ability.has_tag("Choice"):
            tag = ability.get_tag("Choice")
            options = tag.params.get("options", [])
            can_entropy = "Entropy" in options and len(bot.hand) >= 2
            can_sever = "Sever" in options and len(bot.sequence) >= 1
            if not (can_entropy or can_sever): return False
        reqs = ability.target_requirements
        opponents = [p for p in state.players if p != bot]
        if TargetRequirement.NEXUS_CARD in reqs and not state.nexus: return False
        if TargetRequirement.GRAVEYARD in reqs and not state.graveyard: return False
        if TargetRequirement.OPPONENT_CAUSE in reqs and not any(op.sequence for op in opponents): return False
        if TargetRequirement.ANY_CAUSE in reqs and not any(op.sequence for op in opponents): return False
        if TargetRequirement.PLAYER in reqs and not any(op.hand for op in opponents): return False
        return True

    # 1. CRITICAL DEFENSE
    current_adv = evaluate_advantage(bot, state)
    predicted_adv = predict_nexus_outcome(bot, state)
    opponents = [p for p in state.players if p != bot]
    biggest_threat_adv = max([evaluate_advantage(op, state) for op in opponents]) if opponents else 0
    is_desperate = (predicted_adv <= current_adv - 20) or (biggest_threat_adv >= 150)
    
    for idx, c in enumerate(bot.hand):
        if not is_usable_reaction(c): continue
        effects = c.react_ability.effects
        
        # Check if an opponent is about to win
        threats = [op for op in opponents if is_near_win(op)]
        
        # 1a. COUNTER imminent win from nexus
        if any(e.type == "COUNTER_SPELL" for e in effects):
            for a in state.stack:
                if a.source_player in threats and a.ability_type == 'sequence' and not _is_already_handled(a.source_card, state):
                    return idx # STOP THE WINNING CARD
                if a.source_player != bot and a.source_card in state.nexus and not _is_already_handled(a.source_card, state):
                    if is_desperate or random.random() < 0.2: return idx

        # 1b. DISRUPT imminent win from cause (Bounce/Destroy/Steal)
        if any(e.type in ["BOUNCE_CARD", "DESTROY_CARD", "STEAL_CARD"] for e in effects):
            if threats: return idx # Use any disruption to stop a winner
            if any(a.target_card and a.target_card in bot.sequence and a.source_player != bot for a in state.stack): return idx

    # 2. STRATEGIC OPPORTUNITY
    for idx, c in enumerate(bot.hand):
        if not is_usable_reaction(c): continue
        profile = bot.bot_profile
        effects = c.react_ability.effects
        effect_types = [e.type for e in effects]

        # Aggressive disruption (Betray / Redact)
        if any(e in ["DESTROY_CARD", "STEAL_CARD", "FORCE_DISCARD"] for e in effect_types):
            if profile.aggression_weight >= 1.2 or random.random() < 0.2: return idx

        # Snatch: use when there are opponents with 2+ cards (maximise void siphon value)
        if any(e == "SNATCH_DISCARD" for e in effect_types):
            opponents = [p for p in state.players if p != bot]
            rich_opponents = [p for p in opponents if len(p.hand) >= 2]
            if rich_opponents:
                snatch_chance = min(0.9, 0.3 + profile.combo_snatch_chance * 0.3)
                if random.random() < snatch_chance: return idx

        # Reprise: use to deny a key graveyard target or soft-counter a powerful Nexus card
        if any(e == "MOVE_CARD" for e in effect_types):
            # Deny graveyard if opponents could Echo a high-value card
            high_value = {"Erosion", "Pressure", "Momentum", "Echo"}
            gy_targets = [c for c in state.graveyard if c.name in high_value]
            nexus_high_value = [a for a in state.stack if a.source_player != bot
                              and a.source_card in state.nexus
                              and a.source_card.sequence_ability.name in high_value
                              and not _is_already_handled(a.source_card, state)]
            if gy_targets or nexus_high_value:
                reprise_chance = 0.3 + profile.aggression_weight * 0.1
                if random.random() < reprise_chance: return idx

    return -1

def bot_choose_target_player(bot: Player, state: 'GameState') -> Player:
    """Returns the target opponent based on profile and history."""
    opponents = [p for p in state.players if p != bot]
    if not opponents: return None
    
    # Sort opponents by win proximity first, then by advantage
    opponents.sort(key=lambda op: (is_near_win(op), evaluate_advantage(op, state)), reverse=True)
    return opponents[0]

def bot_choose_void_pick(bot: Player, void_pool: List[Card]) -> int:
    """Returns the index of the card to pick from the Void."""
    if not void_pool: return 0
    
    # Priority 1: Cards that help complete a win condition
    sp_names = [c.name for c in bot.sequence]
    for idx, card in enumerate(void_pool):
        if card.name not in sp_names and len(set(sp_names)) >= 4:
            return idx # Completes 5 unique set (roughly)
        if sp_names.count(card.name) >= 3:
            return idx # Completes 4 of a kind
            
    # Priority 2: High value cards
    for idx, card in enumerate(void_pool):
        if card.name in ["Momentum", "Pressure", "Erosion"]:
            return idx
            
    # Priority 3: Anything we don't already have (diversity)
    for idx, card in enumerate(void_pool):
        if card.name not in sp_names:
            return idx
            
    return 0

def bot_choose_target_sequence_card(bot: Player, state: 'GameState', target_player: Player) -> Optional[Card]:
    """Choose a card from a player's sequence."""
    if not target_player or not target_player.sequence: return None
    
    # Heuristic: Snipe cards that contribute to a 4-of-a-kind or 5-unique win
    counts = {}
    for c in target_player.sequence:
        counts[c.name] = counts.get(c.name, 0) + 1
        
    for card in target_player.sequence:
        if counts[card.name] >= 3: return card
        if len(counts) >= 4: return card
        
    # Otherwise, pick a high value card if it exists
    for card in target_player.sequence:
        if card.name in ["Momentum", "Pressure", "Erosion"]: return card
        
    return random.choice(target_player.sequence)

def bot_choose_target_from_list(bot: Player, state: 'GameState', valid_targets: List[tuple], reqs: List[int]) -> tuple:
    """
    Selects the best target from a list of (player, card, copied_name, desc).
    """
    from models import TargetRequirement

    # --- ANY_CAUSE / COPY_ABILITY logic ---
    # copied_name is the 3rd element and is set for ANY_CAUSE targets (e.g., "Liquidate/Cause")
    # We parse the cause-side ability name and apply priority tiers to avoid dumb loops
    # like Cause copying Cause.
    copy_targets = [(tp, tc, cn, desc) for tp, tc, cn, desc in valid_targets if cn]
    if copy_targets:
        HIGH_VALUE = ["Earnings", "Recoup", "Crash", "Call"]
        AVOID = ["Cause"]  # copying Cause is usually a waste — it will just copy something else

        def _cause_name(cn: str) -> str:
            """Extract the cause ability name from a card name like 'Redact/Repeat'."""
            parts = cn.split("/")
            return parts[1] if len(parts) > 1 else cn

        # Tier 1: High-value cause abilities on opponents near winning (best snipe)
        for tp, tc, cn, desc in copy_targets:
            sn = _cause_name(cn)
            if sn in HIGH_VALUE and tp in state.players and is_near_win(tp):
                return (tp, tc, cn)

        # Tier 2: Any high-value cause ability from any player
        for tp, tc, cn, desc in copy_targets:
            sn = _cause_name(cn)
            if sn in HIGH_VALUE:
                return (tp, tc, cn)

        # Tier 3: Anything that's not in the AVOID list
        non_avoid = [(tp, tc, cn, desc) for tp, tc, cn, desc in copy_targets if _cause_name(cn) not in AVOID]
        if non_avoid:
            tp, tc, cn, _ = random.choice(non_avoid)
            return (tp, tc, cn)

        # Tier 4: No good targets found — return the first copy target.
        # The engine's COPY_ABILITY loop guard will fizzle it cleanly if it's
        # another Repeat, so this is safe.
        tp, tc, cn, _ = copy_targets[0]
        return (tp, tc, cn)

    # --- Non-copy targeting ---
    if TargetRequirement.NEXUS_CARD in reqs:
        for t_player, t_card, c_name, desc in valid_targets:
            owner_action = next((a for a in state.stack if a.source_card == t_card), None)
            if owner_action and is_near_win(owner_action.source_player):
                return (None, t_card, None)

    if TargetRequirement.OPPONENT_CAUSE in reqs or TargetRequirement.GRAVEYARD in reqs:
        for t_player, t_card, c_name, desc in valid_targets:
            if t_player and is_near_win(t_player):
                return (t_player, t_card, None)

    # Default: pick a random valid target
    if valid_targets:
        t_player, t_card, c_name, _ = random.choice(valid_targets)
        return (t_player, t_card, c_name)
    return (None, None, None)

def bot_choose_targets(bot: Player, state: 'GameState') -> dict:
    """Returns a dict of targets for the pending action."""
    pending = state.pending_action
    if not pending: return {}
    
    reqs = pending.get("requirements", [])
    ability_name = pending.get("card_name")
    
    # Simple heuristic: target the opponent with the most advantage
    opponents = [p for p in state.players if p != bot]
    opponents.sort(key=lambda p: evaluate_advantage(p, state), reverse=True)
    target_player = opponents[0] if opponents else bot
    
    targets = {}
    
    if TargetRequirement.PLAYER in reqs:
        targets["target_player_index"] = state.players.index(target_player)
    
    if TargetRequirement.OPPONENT_CAUSE in reqs or TargetRequirement.ANY_CAUSE in reqs:
        # If the preferred target has a cause, attack it
        if target_player.sequence:
            targets["target_player_index"] = state.players.index(target_player)
            targets["target_card_index"] = 0 
        else:
            # Fallback: check ANY opponent's cause
            any_opp_with_cause = next((p for p in opponents if p.sequence), None)
            if any_opp_with_cause:
                targets["target_player_index"] = state.players.index(any_opp_with_cause)
                targets["target_card_index"] = 0
            elif TargetRequirement.ANY_CAUSE in reqs and bot.sequence:
                # Absolute last resort: target self only if strictly ANY_CAUSE required
                # Wait, this fixes Crash targeting self. 
                # If they have no valid opponents, and they MUST pick something...
                targets["target_player_index"] = state.players.index(bot)
                targets["target_card_index"] = 0

    if TargetRequirement.NEXUS_CARD in reqs:
        # Target the last card in the nexus (often the one to counter)
        if state.nexus:
            targets["target_card_index"] = len(state.nexus) - 1

    if TargetRequirement.GRAVEYARD in reqs:
        if state.graveyard:
            targets["target_card_index"] = len(state.graveyard) - 1

    return targets

def bot_choose_cost(bot: Player, state: 'GameState') -> dict:
    """Returns a dict for paying costs."""
    pending = state.pending_action
    if not pending: return {}

    tag = pending.get("tag")
    requirements = pending.get("requirements", [])

    # If a modal Choice was already narrowed to a concrete type, pay it directly
    if "Entropy" in requirements:
        return {"cost_type": "Entropy", "card_index": 0}
    if "Sever" in requirements:
        return {"cost_type": "Sever", "card_index": 0}

    # For simple direct tags (Entropy or Sever), use tag.name directly
    if tag:
        if tag.name == "Entropy":
            return {"cost_type": "Entropy", "card_index": 0}
        if tag.name == "Sever":
            # Sever requires destroying a sequence card
            if bot.sequence:
                return {"cost_type": "Sever", "card_index": 0}
            else:
                # No sequence to burn — can't pay cost, pitch instead as fallback
                return {"cost_type": "Entropy", "card_index": 0}
        if tag.name == "Choice":
            # Modal: pick the best option
            options = tag.params.get("options", [])
            if "Sever" in options and bot.sequence:
                return {"choice": "Sever", "card_index": 0}
            else:
                return {"choice": "Entropy", "card_index": 0}

    return {"cost_type": "Entropy", "card_index": 0}

