
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from engine import GameState
from models import Player, BotProfile

def test():
    player_configs = [
        {"player_id": "p1", "name": "Human", "is_bot": False},
        {"player_id": "p2", "name": "Bot", "is_bot": True, "bot_profile": "Aggressive"}
    ]
    state = GameState(player_configs=player_configs)
    state.setup_game()
    
    # Set external IDs to match what the server does
    state.players[0].external_id = "p1_token"
    state.players[1].external_id = "p2_token"
    
    print("--- FULL STATE (Perspective P1) ---")
    d = state.to_dict(perspective_player=state.players[0])
    import json
    print(json.dumps(d['players'], indent=2))

if __name__ == "__main__":
    test()
