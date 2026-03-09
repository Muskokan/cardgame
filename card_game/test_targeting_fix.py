
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from engine import GameState
from models import Player, Card, TargetRequirement, Phase

def test_targeting():
    player_configs = [
        {"player_id": "p1", "name": "Human", "is_bot": False},
        {"player_id": "p2", "name": "Bot", "is_bot": True}
    ]
    state = GameState(player_configs=player_configs)
    state.setup_game()
    
    # Force current phase to STOCK_CARD_SELECTION
    state.current_phase = Phase.STOCK_CARD_SELECTION
    
    # 1. Human plays a card that requires a player target (Check)
    human = state.players[0]
    
    # Manually create a Check card and add it
    from models import Ability, Card, generate_full_deck
    full_deck = generate_full_deck()
    check_card = next(c for c in full_deck if c.stockpile_ability.name == "Check")
    human.hand[0] = check_card
    
    print(f"Human playing {check_card.name}...")
    card_idx = human.hand.index(check_card)
    state.process_input(human, "STOCK", card_index=card_idx)
    
    print(f"Current Phase: {state.current_phase.name}")
    print(f"Pending Action: {state.pending_action}")
    
    # 2. Submit target as index (what the browser does)
    print("Submitting target_player_index: 1 (The Bot)...")
    state.process_input(human, "SET_TARGETS", target_player_index=1)
    
    # 3. Verify target was resolved
    action = state.stack[-1]
    print(f"Action Target Player: {action.target_player.name if action.target_player else 'None'}")
    
    if action.target_player == state.players[1]:
        print("SUCCESS: Target resolved correctly to Bot.")
    else:
        print("FAILURE: Target not resolved.")

    # 4. Resolve and check for fizzle
    print("Passing until resolution...")
    state.process_input(state.players[1], "PASS")
    
    # Check if a fizzle event happened
    fizzled = any(e['event'] == 'ACTION_FIZZLED' for e in state.event_queue)
    if fizzled:
        print("FAILURE: Action fizzled unexpectedly!")
        for e in state.event_queue:
            if e['event'] == 'ACTION_FIZZLED':
                print(f"Fizzle reason: {e['data'].get('reason')}")
    else:
        print("SUCCESS: Action resolved without fizzling.")

if __name__ == "__main__":
    test_targeting()
