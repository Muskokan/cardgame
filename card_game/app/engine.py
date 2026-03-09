from typing import List, Optional, Dict, Any
import uuid
import random
from models import Card, Player, Action, generate_full_deck, Phase, TargetRequirement
from colors import Colors

class GameState:
    def __init__(self, num_players: int = 2, num_bots: int = 0, mode: str = "sudden_death", human_names: Optional[List[str]] = None, view=None, player_configs: Optional[List[Dict[str, Any]]] = None):
        """
        Initializes the game state. mode can be 'endurance' or 'sudden_death'.
        """
        self.view = view
        
        # Use player_configs if provided (multiplayer lobby)
        if player_configs:
            num_players = len(player_configs)
            
        if num_players < 2 or num_players > 4:
            raise ValueError("Game only supports 2-4 players.")
            
        self.mode = mode
        
        # Zones
        self.deck: List[Card] = generate_full_deck()
        random.shuffle(self.deck)
        self.graveyard: List[Card] = []
        self.nexus: List[Card] = []
        
        self.players: List[Player] = []
        
        if player_configs:
            import ai
            for i, config in enumerate(player_configs):
                is_bot = config.get("is_bot", False)
                profile = None
                if is_bot:
                    profile_name = config.get("bot_profile", "Standard")
                    profile = ai.BOT_PROFILES.get(profile_name, ai.AGGRESSIVE_PROFILE)

                player = Player(i, config.get("name", f"Player {i+1}"), is_bot=is_bot, bot_profile=profile)
                player.external_id = config.get("player_id")
                self.players.append(player)
        else:
            human_idx = 0
            bot_names = ["Gene", "Tina", "Louise", "Teddy"] 
            bot_idx = 0
            for i in range(num_players):
                # The last 'num_bots' players in the list will be bots
                is_bot = True if i >= (num_players - num_bots) else False
                bot_profile = None
                
                if is_bot:
                    import ai
                    idx = int(bot_idx) % len(bot_names)
                    name = str(bot_names[idx])
                    bot_idx += 1
                    
                    # Assign BotProfile based on character
                    if name == "Gene":
                        bot_profile = ai.AGGRESSIVE_PROFILE
                    elif name == "Tina":
                        bot_profile = ai.DEFENSIVE_PROFILE
                    elif name == "Louise":
                        bot_profile = ai.RUTHLESS_PROFILE
                    else:
                        bot_profile = ai.COMBO_PROFILE
                else:
                    if human_names is not None and human_idx < len(human_names):
                        name = human_names[human_idx]
                        human_idx += 1
                    else:
                        name = f"Player {i+1}"
                
                p = Player(i, name, is_bot=is_bot, bot_profile=bot_profile)
                p.external_id = None
                self.players.append(p)
            
        self.turn_number: int = 1
        self.active_player_idx: int = 0
        self.priority_player_idx: int = 0
        self.reaction_passes: int = 0
        self.current_phase: Phase = Phase.SETUP
        self.stack: List[Action] = []
        self.game_over: bool = False
        self.winner: Optional[Player] = None
        
        # History & Logging
        self.event_queue: List[Dict[str, Any]] = []
        self.turn_history: List[str] = [] # Narrative events (reset each turn)
        self.event_history: List[str] = [] # Recent Actions for display (reset each turn)
        self.full_history: List[Dict[str, Any]] = [] # Persistent structured history
        
        self.pending_action: Optional[Dict[str, Any]] = None
        self.pending_input_result: Optional[Dict[str, Any]] = None
        self.observers = []
        if view:
            self.attach_observer(view)

    def attach_observer(self, observer):
        self.observers.append(observer)

    def get_active_player(self) -> Player:
        return self.players[self.active_player_idx]

    def setup_game(self):
        """Deals 9 cards to each player to start the game and begins the first turn."""
        self.log_event("GAME_START", {
            "num_players": len(self.players),
            "starting_player": self.get_active_player().name,
            "mode": self.mode,
            "message": f"\n--- Starting Cause & Effect ({self.mode.upper()}) ---"
        })
        
        # Deal cards: One by one in round-robin fashion (9 rounds)
        for _ in range(9):
            for player in self.players:
                self.draw_card(player)
        
        # Start the first turn
        self.turn_number = 1
        self._start_turn()

    def _start_turn(self):
        """Handles internal transitions for the start of a player's turn."""
        player = self.get_active_player()
        self.priority_player_idx = self.active_player_idx
        self.reaction_passes = 0
        self._set_phase(Phase.DRAW)
        
        # Rule: First player skips draw on turn 1 in 2-player games
        if self.turn_number == 1 and self.active_player_idx == 0 and len(self.players) == 2:
            self.log_event("NARRATIVE", {"message": f"{player.name} skips draw phase on turn 1 (2-player rule)."})
            self._set_phase(Phase.CAUSE_CARD_SELECTION)
        else:
            self.draw_card(player)

    def to_dict(self, perspective_player: Optional[Player] = None):
        """Export the entire game state as a JSON-compatible dictionary."""
        pa = self.pending_action
        if pa:
            pa_dict = {
                "source_player_idx": pa.get("source_player_idx", pa.get("player_idx")),
                "card_name": pa.get("card_name"),
                "type": pa.get("type"),
                "requirements": (
                    [r.name if hasattr(r, "name") else str(r) for r in pa.get("requirements", [])]
                    if "requirements" in pa else
                    ([pa["tag"].name] if "tag" in pa else [])
                ),
                "void_pool": pa.get("void_pool", []),
                "pitched_card_ids": pa.get("pitched_card_ids", []),
            }
        else:
            pa_dict = None
        return {
            "turn_number": self.turn_number,
            "current_phase": self.current_phase.name,
            "game_over": self.game_over,
            "winner_name": self.winner.name if self.winner else None,
            "active_player_idx": self.active_player_idx,
            "priority_player_idx": self.priority_player_idx,
            "deck_count": len(self.deck),
            "graveyard": [c.to_dict() for c in self.graveyard],
            "nexus": [c.to_dict() for c in self.nexus],
            "stack": [a.to_dict() for a in self.stack],
            "players": [p.to_dict(include_hand=(p == perspective_player)) for p in self.players],
            "event_history": self.event_history,
            "pending_action": pa_dict,
        }

    def end_turn(self):
        self.active_player_idx = (self.active_player_idx + 1) % len(self.players)
        self.turn_number += 1
        self.turn_history = [] # Reset history for the next turn
        self.event_history = [] # Reset recent actions for the next turn
        self._start_turn()

    def _set_phase(self, new_phase: Phase):
        """Sets the current phase and emits a PHASE_CHANGE log event."""
        self.current_phase = new_phase
        labels = {
            Phase.DRAW: "Draw Phase",
            Phase.CAUSE_CARD_SELECTION: "Cause Phase",
            Phase.REACTION_SELECTION: "Reaction Phase",
            Phase.TARGETING: "Targeting Phase",
            Phase.PAYING_COSTS: "Paying Costs",
            Phase.RESOLUTION: "Resolution Phase",
            Phase.REVIEW: "Review Phase",
            Phase.GAME_OVER: "Game Over",
            Phase.SETUP: "Setup",
        }
        label = labels.get(new_phase, new_phase.name)
        self.log_event("PHASE_CHANGE", {"phase": new_phase.name, "label": label})


    def draw_card(self, player: Player) -> bool:
        """
        Draws a card for the given player. Returns False if game ends.
        Handles the Endurance and Sudden Death empty deck rules.
        """
        if not self.deck:
            if self.mode == "sudden_death":
                self.log_event("GAME_OVER", {
                    "winner": player.name,
                    "reason": "Empty deck in Sudden Death",
                    "message": f"\n[SUDDEN DEATH] {player.name} attempted to draw from an empty deck!\n[WINNER] {player.name} wins the game!"
                })
                self.game_over = True
                self.winner = player
                return False
            elif self.mode == "endurance":
                if not self.graveyard:
                    self.log_event("GAME_OVER", {
                        "winner": None,
                        "reason": "Stalemate",
                        "message": "\n[STALEMATE] Deck and Graveyard are both empty. The game ends in a draw."
                    })
                    self.game_over = True
                    return False
                
                self.log_event("NARRATIVE", {"message": "[ENDURANCE] Deck is empty. Reshuffling graveyard to form new deck..."})
                self.deck = self.graveyard.copy()
                self.graveyard = []
                random.shuffle(self.deck)
                
        if self.deck:
            card = self.deck.pop(0)
            card.owner = player
            player.hand.append(card)
            self.log_event("CARD_DRAWN", {"player": player.name, "cards_left": len(self.deck)})
            
            if self.current_phase == Phase.DRAW:
                self._set_phase(Phase.CAUSE_CARD_SELECTION)
                
            return True
        return False

    def log_event(self, event_type: str, data: Dict[str, Any]) -> Optional[int]:
        """Pushes structured data to the event queue and notifies observers."""
        event = {"event": event_type, "data": data}
        self.event_queue.append(event)
        
        # --- POPULATE LEGACY HISTORY FOR TERMINAL UI ---
        # event_history is for the "Recent Actions" box at bottom
        # turn_history is for the Turn Recap at end of turn
        msg = data.get("message", "")
        if not msg:
            if event_type == "CARD_DRAWN":
                msg = f"{data['player']} drew a card."
            elif event_type == "CARD_SEQUENCED":
                msg = f"{data['player']} sequenced {data['card']}."
            elif event_type == "CARD_REACTED":
                msg = f"{data['player']} reacted with {data['card']}."
            elif event_type == "REACTION_PASS":
                msg = f"{data['player']} passed."
            elif event_type == "ACTION_FIZZLED":
                msg = f"  [FIZZLE] {data['card']} fizzled! {data['reason']}"
            elif event_type == "GAME_OVER":
                msg = f"Game Over: {data['reason']}"
            elif event_type == "PHASE_CHANGE":
                msg = f"--- {data.get('label', data['phase'])} ---"

        if msg:
            self.event_history.append(msg)
            if event_type in ["EFFECT_RESULT", "CARD_COUNTERED", "ACTION_FIZZLED", "WIN_EMPTY_DECK"]:
                self.turn_history.append(msg)
            elif event_type in ["CARD_SEQUENCED", "CARD_REACTED"]:
                 # Also add card plays to recap
                 self.turn_history.append(f"{data['player']} played {data['card']}")

        # Notify Observers
        for obs in self.observers:
            if hasattr(obs, "on_event"):
                obs.on_event(event_type, data)
        
        # Track structured history for AI/Analysis
        self.full_history.append({
            "event": event_type,
            "data": data,
            "turn": self.turn_number,
        })
        return len(self.event_history) - 1

    def add_to_summary(self, message: str):
        """Adds a specific narrative line to the turn history."""
        self.turn_history.append(message)
        self._push_history(message)
        self.full_history.append({
            "event": "NARRATIVE",
            "data": {"message": message},
            "turn": self.turn_number
        })

    def _push_history(self, message: str) -> int:
        """Adds to history and returns the index of the new entry."""
        self.event_history.append(message)
        return len(self.event_history) - 1

    def update_action_status(self, action, icon: str, zone_symbol: str = ""):
        """Emits an event for status/zone updates instead of modifying history strings."""
        self.log_event("ACTION_STATUS_UPDATED", {
            "source_player": action.source_player.name,
            "card_name": action.source_card.name,
            "icon": icon,
            "zone_symbol": zone_symbol,
            "history_idx": action.history_idx
        })

    def append_to_action_history(self, action, suffix: str):
        """Appends additional info (like targets) to an existing history line."""
        formatted_suffix = f" {Colors.DIM}► {suffix}{Colors.RESET}"
        if action.history_idx is not None and 0 <= action.history_idx < len(self.event_history):
            self.event_history[action.history_idx] += formatted_suffix
            
        if hasattr(action, 'recap_idx') and action.recap_idx is not None and 0 <= action.recap_idx < len(self.turn_history):
            self.turn_history[action.recap_idx] += formatted_suffix

    def process_input(self, player, action_type: str, **kwargs):
        print(f"DEBUG RECV {player.name}: {action_type} phase={self.current_phase.name}")
        """
        The core State Machine router.
        """
        if self.game_over:
            return

        active_p = self.get_active_player()
        if self.current_phase == Phase.TARGETING or self.current_phase == Phase.PAYING_COSTS:
            if action_type == "CANCEL":
                self.log_event("ACTION_FIZZLED", {
                    "player": player.name,
                    "card": self.stack[-1].source_card.name if self.stack else "Action",
                    "reason": "Cancelled by player"
                })
                if self.stack:
                    action = self.stack.pop()
                    if action.source_card in self.nexus:
                        self.nexus.remove(action.source_card)
                        self.graveyard.append(action.source_card)
                self.pending_action = None
                self._set_phase(Phase.REVIEW)
                return

            if action_type in ["SET_TARGETS", "PAY_COST", "SET_COST", "CHOOSE_COST_OPTION"]:
                self.submit_pending_input(kwargs)
            return
            
        elif self.current_phase == Phase.RESOLUTION:
            if action_type in ["SNATCH_PICK", "RESOLUTION_ENTROPY"] and self.pending_action and self.pending_action.get("type") == action_type:
                self.submit_pending_input(kwargs)
            return

        elif self.current_phase == Phase.REVIEW:
            if action_type == "END_TURN" and player == active_p:
                self.end_turn()
            return

        elif player != active_p and self.current_phase != Phase.REACTION_SELECTION:
            return 

        if self.current_phase == Phase.CAUSE_CARD_SELECTION:
            if action_type == "CAUSE":
                idx = kwargs.get("card_index", -1)
                if 0 <= idx < len(player.hand):
                    played_card = player.hand.pop(idx)
                    self._commit_card_play(player, played_card, 'sequence')
                        
        elif self.current_phase == Phase.REACTION_SELECTION:
            priority_p = self.players[self.priority_player_idx]
            if player != priority_p:
                return 
                
            if action_type == "PASS":
                self.log_event("REACTION_PASS", {"player": player.name})
                self.reaction_passes += 1
                self.priority_player_idx = (self.priority_player_idx + 1) % len(self.players)
                
                if self.reaction_passes >= len(self.players):
                    self._set_phase(Phase.RESOLUTION)
                    self.resolve_stack()
                    self.check_win_condition(self.get_active_player())
                
            elif action_type == "REACT":
                idx = kwargs.get("card_index", -1)
                if 0 <= idx < len(player.hand):
                    react_card = player.hand.pop(idx)
                    self._commit_card_play(player, react_card, 'react')
                    
    def _commit_card_play(self, player: Player, card: Card, action_type: str):
        # Put the card physically on the "Field/Nexus" while resolving
        self.nexus.append(card)
        
        action = Action(player, card, action_type)
        
        # Log to event history and store index
        if action_type == 'sequence':
            idx = self.log_event("CARD_SEQUENCED", {
                "player": player.name, 
                "card": card.name,
                "ability": card.sequence_ability.name,
                "description": card.sequence_ability.description
            })
        else:
            idx = self.log_event("CARD_REACTED", {
                "player": player.name, 
                "card": card.name,
                "ability": card.react_ability.name,
                "description": card.react_ability.description
            })
        
        action.history_idx = idx
        action.recap_idx = len(self.turn_history) - 1
        # Mark as in the Nexus ⚱
        self.update_action_status(action, '⚡' if action_type == 'react' else '✦', '⚱')
        self.stack.append(action)
        
        ability = card.react_ability if action_type == 'react' else card.sequence_ability
        
        needs_cost = False
        cost_tag = None
        if ability.tags:
            for tag in ability.tags:
                if tag.name in ["Entropy", "Sever", "Choice"]:
                    needs_cost = True
                    cost_tag = tag
                    break
                    
        needs_target = bool(ability.target_requirements)
        
        if needs_cost:
            # CHECK AFFORDABILITY
            can_pay = False
            if cost_tag.name == "Entropy":
                can_pay = len(player.hand) >= 1
            elif cost_tag.name == "Sever":
                can_pay = len(player.sequence) >= 1
            elif cost_tag.name == "Choice":
                options = cost_tag.params.get("options", [])
                if "Entropy" in options and len(player.hand) >= 1: can_pay = True
                elif "Sever" in options and len(player.sequence) >= 1: can_pay = True
            
            if not can_pay:
                print(f"DEBUG: Action fizzled - cannot afford {cost_tag.name}")
                self.log_event("ACTION_FIZZLED", {
                    "player": player.name,
                    "card": card.name,
                    "reason": f"Cannot afford cost ({cost_tag.name})"
                })
                self.nexus.remove(card)
                self.graveyard.append(card)
                self.stack.pop()
                self._set_phase(Phase.REVIEW)
                return

            self.pending_action = {
                "type": "COST_SELECTION",
                "player_idx": self.players.index(player),
                "card_name": card.name,
                "tag": cost_tag,
                "needs_target_after": needs_target
            }
            self._set_phase(Phase.PAYING_COSTS)
        elif needs_target:
            self.pending_action = {
                "type": "TARGET_SELECTION",
                "player_idx": self.players.index(player),
                "card_name": card.name,
                "requirements": ability.target_requirements
            }
            self._set_phase(Phase.TARGETING)
        else:
            self._finalize_action_placement(action_type == 'react')

    def submit_pending_input(self, data: Dict[str, Any]):
        """Dispatches pending input to the appropriate handler based on the current pending type."""
        pending = self.pending_action
        if not pending:
            return
        action = self.stack[-1] if self.stack else None
        p_idx = pending.get("player_idx")
        if p_idx is None:
            p_idx = pending.get("source_player_idx")
        player = self.players[p_idx]
        p_type = pending["type"]

        if p_type == "COST_SELECTION":
            self._handle_cost_selection(data, pending, action, player)
        elif p_type == "TARGET_SELECTION":
            self._handle_target_selection(data, action)
        elif p_type in ["RESOLUTION_ENTROPY", "SNATCH_PICK"]:
            self.pending_input_result = data
            self.pending_action = None
            if self.stack:
                self.resolve_stack()
            else:
                self._set_phase(Phase.REVIEW)

    def _handle_cost_selection(self, data: Dict[str, Any], pending: Dict[str, Any], action, player):
        """Handles cost-payment input (Entropy / Sever / Choice narrowing)."""
        choice = data.get("choice")
        tag = pending.get("tag")
        # Only narrow/early-return for modal "Choice" tags (e.g. Redact: pick Entropy OR Sever).
        # Simple Entropy/Sever tags (e.g. Hush's EXTRA_ENTROPY) must fall through to payment directly.
        is_modal_choice = tag and tag.name == "Choice"
        if choice in ["Entropy", "Sever"] and is_modal_choice:
            pending["requirements"] = [choice]
            self.log_event("NARRATIVE", {"message": f"  - {player.name} chose to {choice}."})
            return  # Frontend will refresh and show just that cost as selectable

        cost_type = data.get("cost_type") or choice  # Handle both formats
        if cost_type == "Entropy":
            p_idx = int(data.get("card_index", -1))
            if p_idx == -1 and player.hand:
                p_idx = 0  # Fallback: pitch first card
            if 0 <= p_idx < len(player.hand):
                pitched = player.hand.pop(p_idx)
                self.graveyard.append(pitched)
                self.log_event("NARRATIVE", {"message": f"  -> {player.name} utilized {pitched.name} for Entropy."})
            else:
                self.log_event("NARRATIVE", {"message": f"  -> {player.name} failed to find a card to pitch (Entropy)."})

        elif cost_type == "Sever":
            cost_name = data.get("card_name")
            cost_idx = data.get("card_index")
            cost_card = None
            if cost_idx is not None and 0 <= int(cost_idx) < len(player.sequence):
                cost_card = player.sequence[int(cost_idx)]
            elif cost_name:
                cost_card = next((c for c in player.sequence if c.name == cost_name), None)
            if cost_card:
                player.sequence.remove(cost_card)
                self.graveyard.append(cost_card)
                self.log_event("NARRATIVE", {"message": f"  -> {player.name} utilized {cost_card.name} for Sever."})
            elif player.sequence:  # Fallback: burn first card
                cost_card = player.sequence.pop(0)
                self.graveyard.append(cost_card)
                self.log_event("NARRATIVE", {"message": f"  -> {player.name} utilized {cost_card.name} for Sever."})

        if pending.get("needs_target_after"):
            ability = action.source_card.react_ability if action.ability_type == 'react' else action.source_card.sequence_ability
            self.pending_action = {
                "type": "TARGET_SELECTION",
                "player_idx": self.players.index(player),
                "card_name": action.source_card.name,
                "requirements": ability.target_requirements,
            }
            self._set_phase(Phase.TARGETING)
        else:
            self.pending_action = None
            self._finalize_action_placement(action.ability_type == 'react')


    def _handle_target_selection(self, data: Dict[str, Any], action):
        """Resolves targeting input from the frontend or AI into concrete game objects."""
        t_player_idx = data.get("target_player_index")
        t_card_idx = data.get("target_card_index")
        t_copy_name = data.get("copied_name")

        if t_player_idx is not None:
            idx = int(t_player_idx)
            if 0 <= idx < len(self.players):
                action.target_player = self.players[idx]

        if t_card_idx is not None:
            idx = int(t_card_idx)
            t_zone = data.get("target_zone")
            ability = action.source_card.react_ability if action.ability_type == 'react' else action.source_card.sequence_ability
            reqs = ability.target_requirements

            if t_zone == 'graveyard' and 0 <= idx < len(self.graveyard):
                action.target_card = self.graveyard[idx]
            elif t_zone == 'nexus' and 0 <= idx < len(self.nexus):
                action.target_card = self.nexus[idx]
            elif action.target_player and 0 <= idx < len(action.target_player.sequence):
                action.target_card = action.target_player.sequence[idx]
            else:
                # Fallback zone resolution
                if action.target_player and 0 <= idx < len(action.target_player.sequence):
                    action.target_card = action.target_player.sequence[idx]
                elif TargetRequirement.NEXUS_CARD in reqs and 0 <= idx < len(self.nexus):
                    action.target_card = self.nexus[idx]
                elif TargetRequirement.GRAVEYARD in reqs and 0 <= idx < len(self.graveyard):
                    action.target_card = self.graveyard[idx]

        # Fallback: accept direct object/string data (used by AI)
        if not action.target_card:
            action.target_card = data.get("target_card")
        if not action.target_player:
            action.target_player = data.get("target_player")
        action.copied_card_name = t_copy_name or data.get("copied_card_name")

        # Append resolved target info to event history
        if action.target_card:
            if hasattr(action.target_card, 'owner') and action.target_card.owner:
                target_str = f"{action.target_card.owner.name}'s {action.target_card.name}"
            else:
                target_str = str(action.target_card.name)
        elif action.target_player:
            target_str = action.target_player.name
        elif action.copied_card_name:
            target_str = action.copied_card_name
        else:
            target_str = ""

        if target_str:
            self.append_to_action_history(action, target_str)

        self.pending_action = None
        self._finalize_action_placement(action.ability_type == 'react')

    def _finalize_action_placement(self, is_react: bool):
        if not is_react:
            self._set_phase(Phase.REACTION_SELECTION)
            self.reaction_passes = 0
            self.priority_player_idx = (self.active_player_idx + 1) % len(self.players)
        else:
            self.reaction_passes += 1
            self.priority_player_idx = (self.priority_player_idx + 1) % len(self.players)
            if self.reaction_passes >= len(self.players):
                self._set_phase(Phase.RESOLUTION)
                self.resolve_stack()
                self.check_win_condition(self.get_active_player())
            else:
                self._set_phase(Phase.REACTION_SELECTION)
                
        for i in range(len(self.players)):
            p_idx = (self.active_player_idx + i) % len(self.players)
            if self.check_win_condition(self.players[p_idx]):
                 break

    def check_any_winner(self) -> bool:
        """Checks all players for win conditions. Returns True if a winner is found."""
        for player in self.players:
            if self.check_win_condition(player):
                return True
        return False

    def check_win_condition(self, player: Player) -> bool:
        """Checks if a player has met the Sequence win conditions."""
        sp = player.sequence
        if len(sp) < 5:
            return False
            
        counts = {}
        for c in sp:
            counts[c.name] = counts.get(c.name, 0) + 1
            if counts[c.name] >= 4:
                self.log_event("GAME_OVER", {
                    "winner": player.name,
                    "reason": f"assembled 4 {c.name} cards",
                    "message": f"\n[WINNER] {player.name} wins by assembling 4 {c.name} cards!"
                })
                self.game_over = True
                self.winner = player
                return True
                
        if len(set(c.name for c in sp)) == 5:
            self.log_event("GAME_OVER", {
                "winner": player.name,
                "reason": "assembled all 5 unique cards",
                "message": f"\n[WINNER] {player.name} wins by assembling all 5 unique cards!"
            })
            self.game_over = True
            self.winner = player
            return True
            
        return False

    def get_reaction_order(self, starting_from_player: Player) -> List[Player]:
        idx = self.players.index(starting_from_player)
        order = []
        for i in range(1, len(self.players) + 1):
            next_idx = (idx + i) % len(self.players)
            order.append(self.players[next_idx])
        return order

    def resolve_stack(self):
        """Resolves all actions on the stack in LIFO order."""
        self.log_event("STACK_RESOLUTION_START", {"count": len(self.stack)})
        
        try:
            while self.stack:
                if self.game_over:
                    break
                    
                action = self.stack[-1]
                if not getattr(action, 'resolving', False):
                    self.log_event("ACTION_RESOLVING", {
                        "player": action.source_player.name,
                        "card": action.source_card.name
                    })
                    action.resolving = True
                    
                    if not action.triggered and action.source_card not in self.nexus:
                        self.log_event("ACTION_FIZZLED", {
                            "player": action.source_player.name,
                            "card": action.source_card.name,
                            "reason": "Card is no longer in the nexus"
                        })
                        self.update_action_status(action, "❌", "🪦")
                        self.stack.pop()
                        continue

                    if action.ability_type == 'react':
                        action.generator = action.source_card.execute_react(self, action, self.view)
                    elif action.ability_type == 'sequence':
                        action.generator = action.source_card.execute_sequence(self, action, self.view)

                if action.generator:
                    import types
                    if isinstance(action.generator, types.GeneratorType):
                        try:
                            next(action.generator)
                            return  # Effect yielded "WAIT_FOR_INPUT"
                        except StopIteration:
                            action.generator = None
                    else:
                        action.generator = None

                self.stack.pop()  # Action is fully resolved

                if action.ability_type == 'react':
                    if action.source_card in self.nexus:
                        self.nexus.remove(action.source_card)
                        action.source_card.owner = None
                        self.graveyard.append(action.source_card)
                        self.update_action_status(action, "✓", "🪦")
                elif action.ability_type == 'sequence':
                    if action.source_card in self.nexus:
                        self.nexus.remove(action.source_card)
                        action.source_card.owner = action.source_player
                        action.source_player.sequence.append(action.source_card)
                        self.update_action_status(action, "✓", "✦")
                
                if self.check_any_winner():
                    break
        except Exception as e:
            # CRITICAL SAFETY: Ensure Nexus is cleaned up even on crash
            self.log_event("DEBUG_ERROR", {"message": f"CRITICAL: Loop crashed during resolution: {str(e)}"})
            for card in list(self.nexus):
                self.nexus.remove(card)
                self.graveyard.append(card)
            self.stack.clear()
            self._set_phase(Phase.REVIEW)
            raise e

        self.log_event("STACK_RESOLUTION_END", {})
        
        if not self.game_over:
            self._set_phase(Phase.REVIEW)
