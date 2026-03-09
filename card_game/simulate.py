import sys
import os
import json
import copy
import time
from collections import Counter

# Patch time.sleep so bots don't wait during simulation
time.sleep = lambda x: None

import ai
from view import GameExit, ConsoleView
from models import Action, Phase, generate_full_deck
from engine import GameState

def ai_handle_pending_action(state: GameState):
    pending = state.pending_action
    if not pending:
        return
        
    p_type = pending["type"]
    player = state.players[pending.get("player_idx", pending.get("source_player_idx", 0))]
    print(f"[DEBUG] Handling pending action: {p_type} for {player.name} with {pending}")
    
    if p_type == "COST_SELECTION":
        cost_data = ai.bot_choose_cost(player, state)
        print(f"[DEBUG] AI chose cost: {cost_data}")
        state.submit_pending_input(cost_data)
        
    elif p_type == "TARGET_SELECTION":
        target_data = ai.bot_choose_targets(player, state)
        print(f"[DEBUG] AI chose targets: {target_data.get('target_card')}, {target_data.get('target_player')}")
        state.submit_pending_input(target_data)
        
    elif p_type == "RESOLUTION_PITCH":
        import random
        # Just pitch a random card from hand to satisfy the resolution pitch
        p_idx = random.randint(0, len(player.hand) - 1) if player.hand else -1
        state.submit_pending_input({"card_id": player.hand[p_idx].id if p_idx >= 0 else None})
        
    elif p_type == "SNATCH_PICK":
        ids = pending.get("pitched_card_ids", [])
        pitched = [c for c in state.graveyard if c.id in ids]
        pick_idx = ai.bot_choose_void_pick(player, pitched)
        state.submit_pending_input({"card_id": pitched[pick_idx].id if pitched else None})

# We want to suppress printing during the simulation
class HiddenPrints:
    def __init__(self):
        self._original_stdout = None

    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        if self._original_stdout:
            sys.stdout = self._original_stdout

# Metrics to track
ability_resolutions = Counter() # Count of successful resolves
ability_win_presence = Counter() # Count of times winner had this ability (Hand or Stock)
ability_counter_attempts = Counter() # Count of times React was played
ability_counter_successes = Counter() # Count of times React successfully countered something
total_games_played = 0
wins_by_playstyle = Counter()
win_reasons = Counter()
counter_snipes_executed = 0
winner_stockpile_counts = Counter() 
total_turns_across_games = 0
empty_hand_turns = []
avg_hand_sizes = []
targeting_data = {} # {source: Counter({target: count})}

# Tendency tracking: {playstyle: Counter({'pass': x, 'react': y})}
ai_tendencies = {name: Counter() for name in ai.BOT_PROFILES.keys()}

def run_simulation(num_games):
    global counter_snipes_executed
    global total_turns_across_games
    
    for i in range(num_games):
        if i % 100 == 0: 
             print(f"Simulating game {i}... (Time: {time.strftime('%H:%M:%S')})")
             
        class SilentView(ConsoleView):
            def log(self, message): pass
            def on_event(self, event_type, data): pass
            def show_board(self, state): pass
            def render_events(self, state): pass

        view = SilentView()
        state = GameState(num_players=4, num_bots=4, mode="endurance", view=view)
        
        empty_deck_win = False
        
        # with HiddenPrints():
        state.setup_game()
        turn_limit = 200
        
        while not state.game_over and state.turn_number < turn_limit:
            if state.pending_action:
                ai_handle_pending_action(state)
                continue
                
            active_p = state.get_active_player()
            priority_p = state.players[state.priority_player_idx]
            print(f"[DEBUG] Turn {state.turn_number}: Phase={state.current_phase.name}, Active={active_p.name}, Priority={priority_p.name}")
            
            if state.current_phase == Phase.DRAW:
                if state.turn_number == 1 and state.active_player_idx == 0 and len(state.players) == 2:
                    state.current_phase = Phase.STOCK_CARD_SELECTION
                else:
                    if not state.draw_card(active_p):
                        if state.game_over and state.winner:
                            state.log_event("WIN_EMPTY_DECK", {"player": state.winner.name})
                            empty_deck_win = True
                        break
                        
            elif state.current_phase == Phase.STOCK_CARD_SELECTION:
                choice_idx = ai.bot_choose_stock(active_p, state)
                state.process_input(active_p, "STOCK", card_index=choice_idx)
                
            elif state.current_phase == Phase.REACTION_SELECTION:
                # Metric Tracking
                for p in state.players:
                    avg_hand_sizes.append(len(p.hand))
                    if len(p.hand) == 0:
                        if not hasattr(state, '_empty_logged'): state._empty_logged = set()
                        if p.name not in state._empty_logged:
                            empty_hand_turns.append(state.turn_number)
                            state._empty_logged.add(p.name)

                if not priority_p.hand:
                    ai_tendencies[priority_p.bot_profile.name]['pass'] += 1
                    state.process_input(priority_p, "PASS")
                    continue
                    
                react_idx = ai.bot_choose_reaction(priority_p, state)
                if react_idx == -1:
                    ai_tendencies[priority_p.bot_profile.name]['pass'] += 1
                    state.process_input(priority_p, "PASS")
                else:
                    ai_tendencies[priority_p.bot_profile.name]['react'] += 1
                    state.process_input(priority_p, "REACT", card_index=react_idx)
                    
            elif state.current_phase == Phase.RESOLUTION:
                if not state.game_over:
                    state.end_turn()

        if state.winner:
            wins_by_playstyle[state.winner.bot_profile.name] += 1
            if empty_deck_win:
                win_reasons["Empty Deck (Sudden Death)"] += 1
            
            for entry in state.full_history:
                event = entry["event"]
                data = entry["data"]
                
                if event == "EFFECT_RESULT":
                    msg = data["message"]
                    # Rule 1: Only count [SUCCESS], ignore [ECHO]
                    if "[SUCCESS]" in msg:
                        parts = msg.split("[SUCCESS] ")[1].split(" activates")
                        if len(parts) > 1:
                            ab_name = parts[0].strip()
                            ability_resolutions[ab_name] += 1
                
                elif event == "TARGET_INFO":
                    src = data["source"]
                    target = data["target"]
                    if src not in targeting_data:
                        targeting_data[src] = Counter()
                    targeting_data[src][target] += 1
                
                elif event == "CARD_REACTED":
                    ability_counter_attempts[data["ability"]] += 1
            
            winner_ab_names = set()
            for c in state.winner.stockpile:
                winner_stockpile_counts[c.stockpile_ability.name] += 1
                winner_ab_names.add(c.stockpile_ability.name)
            for c in state.winner.hand:
                winner_ab_names.add(c.react_ability.name)
                winner_ab_names.add(c.stockpile_ability.name)
            
            for ab in winner_ab_names:
                ability_win_presence[ab] += 1
            
            sp = state.winner.stockpile
            counts = {}
            for c in sp:
                counts[c.stockpile_ability.name] = counts.get(c.stockpile_ability.name, 0) + 1
                if counts[c.stockpile_ability.name] >= 4:
                    win_reasons["4 Identical"] += 1
                    break
            else:
                if len(set(c.stockpile_ability.name for c in sp)) == 5:
                    win_reasons["1 of Each 5"] += 1
                else:
                    win_reasons["Rule Violation/Logic Error"] += 1
        else:
            win_reasons["Draw / Turn Limit"] += 1

        total_turns_across_games += state.turn_number

    # Convert targeting Counter to simple dict for JSON
    serializable_targeting = {src: dict(targets) for src, targets in targeting_data.items()}

    sim_results = {
        "games": num_games,
        "ability_resolutions": dict(ability_resolutions),
        "ability_win_presence": dict(ability_win_presence),
        "ability_counter_attempts": dict(ability_counter_attempts),
        "wins_by_playstyle": dict(wins_by_playstyle),
        "win_reasons": dict(win_reasons),
        "winner_stockpile_counts": dict(winner_stockpile_counts),
        "targeting_data": serializable_targeting
    }
    with open("sim_data.json", "w") as f:
        json.dump(sim_results, f, indent=4)
    
    print(f"\nSimulation complete! Data saved to sim_data.json.")
    print(f"Average turns per game: {total_turns_across_games / num_games:.1f}")
    if empty_hand_turns:
        print(f"Average turn a player first hits 0 cards: {sum(empty_hand_turns) / len(empty_hand_turns):.1f}")
    if avg_hand_sizes:
        print(f"Global average hand size: {sum(avg_hand_sizes) / len(avg_hand_sizes):.1f} cards")

def signal_handler(sig, frame):
    print('\nSimulation terminated cleanly.')
    sys.exit(0)

import signal
signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    total_games = 100
    if len(sys.argv) > 1:
        try:
            total_games = int(sys.argv[1])
        except ValueError:
            pass
    run_simulation(total_games)
