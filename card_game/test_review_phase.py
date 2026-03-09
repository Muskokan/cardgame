
from engine import GameState
from models import Phase

def test_review_phase_transition():
    # Setup 2 player game
    state = GameState(num_players=2, num_bots=0)
    state.setup_game()
    
    p1 = state.players[0]
    p2 = state.players[1]
    
    print(f"Initial Phase: {state.current_phase}")
    
    # Active Player (P1) stocks a card
    state.process_input(p1, "STOCK", card_index=0)
    print(f"Phase after STOCK: {state.current_phase}")
    
    # Both players pass reaction
    state.process_input(p2, "PASS") # P2 priority
    state.process_input(p1, "PASS") # P1 priority
    
    print(f"Phase after double PASS: {state.current_phase}")
    
    if state.current_phase == Phase.REVIEW:
        print("SUCCESS: Reached REVIEW phase.")
        # Try to end turn
        state.process_input(p1, "END_TURN")
        print(f"Phase after END_TURN: {state.current_phase}")
        print(f"Active Player Index: {state.active_player_idx}")
        if state.active_player_idx == 1 and state.current_phase == Phase.DRAW:
             print("SUCCESS: Turn transitioned to P2.")
        else:
             print(f"FAILURE: Turn did not transition correctly. Phase: {state.current_phase}, Active: {state.active_player_idx}")
    else:
        print(f"FAILURE: Did not reach REVIEW phase. Phase: {state.current_phase}")

if __name__ == "__main__":
    test_review_phase_transition()
