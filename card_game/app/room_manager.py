import random
import string
import uuid
from typing import Dict, List, Optional, Any
from engine import GameState
from models import Player, BotProfile
import time

class Room:
    def __init__(self, code: str):
        self.code = code
        self.seats = [None] * 4  # Each entry is a dict or None: {"player_id": str, "name": str, "is_bot": bool, "bot_profile": str}
        self.host_player_id: Optional[str] = None
        self.state: Optional[GameState] = None
        self.connections: Dict[str, Any] = {} # player_id -> WebSocket
        self.player_tokens: Dict[str, str] = {} # player_id -> name
        self.disconnected_players: Dict[str, float] = {}  # player_id -> disconnect timestamp
        self.started = False
        self.last_activity = time.time()

    def update_activity(self):
        self.last_activity = time.time()

    def mark_disconnected(self, player_id: str):
        self.disconnected_players[player_id] = time.time()

    def mark_reconnected(self, player_id: str):
        self.disconnected_players.pop(player_id, None)

    def get_disconnected_player_names(self) -> list:
        """Return names of currently disconnected (but not timed-out) human players."""
        names = []
        if not self.state:
            return names
        for p in self.state.players:
            if not p.is_bot and p.external_id in self.disconnected_players:
                names.append(p.name)
        return names

    def to_dict(self):
        return {
            "code": self.code,
            "seats": self.seats,
            "host_player_id": self.host_player_id,
            "started": self.started,
            "last_activity": self.last_activity
        }

class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def delete_room(self, code: str):
        code = code.upper()
        if code in self.rooms:
            print(f"[CLEANUP] Deleting room {code}")
            del self.rooms[code]

    def generate_code(self, length=4) -> str:
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
            if code not in self.rooms:
                return code

    def create_room(self) -> tuple[str, str]:
        code = self.generate_code()
        room = Room(code)
        player_id = str(uuid.uuid4())
        room.host_player_id = player_id
        self.rooms[code] = room
        return code, player_id

    def get_room(self, code: str) -> Optional[Room]:
        return self.rooms.get(code.upper())

    def join_room(self, code: str) -> Optional[str]:
        room = self.get_room(code)
        if not room or room.started:
            return None
        
        player_id = str(uuid.uuid4())
        return player_id

    def claim_seat(self, code: str, player_id: str, seat_idx: int, name: str) -> bool:
        room = self.get_room(code)
        if not room or seat_idx < 0 or seat_idx >= 4 or room.started:
            return False
        
        # Check if player is already in a seat
        for i, s in enumerate(room.seats):
            if s and s.get("player_id") == player_id:
                room.seats[i] = None
        
        # Check if seat is occupied
        if room.seats[seat_idx] is not None:
            return False
            
        room.seats[seat_idx] = {
            "player_id": player_id,
            "name": name,
            "is_bot": False,
            "bot_profile": None
        }
        return True

    def assign_bot(self, code: str, player_id: str, seat_idx: int, profile_name: str) -> bool:
        room = self.get_room(code)
        if not room or player_id != room.host_player_id or room.started:
            return False
            
        if seat_idx < 0 or seat_idx >= 4:
            return False
            
        import ai
        if profile_name not in ai.BOT_PROFILES:
            return False

        bot_names = {
            "Aggressive": "Gene",
            "Defensive": "Tina",
            "Ruthless": "Louise",
            "Combo": "Teddy",
            "Chaotic": "Zeke"
        }

        room.seats[seat_idx] = {
            "player_id": f"bot_{seat_idx}",
            "name": bot_names.get(profile_name, f"{profile_name} Bot"),
            "is_bot": True,
            "bot_profile": profile_name
        }
        return True

    def remove_bot(self, code: str, player_id: str, seat_idx: int) -> bool:
        room = self.get_room(code)
        if not room or player_id != room.host_player_id or room.started:
            return False
            
        if 0 <= seat_idx < 4 and room.seats[seat_idx] and room.seats[seat_idx].get("is_bot"):
            room.seats[seat_idx] = None
            return True
        return False

    def start_game(self, code: str, player_id: str) -> bool:
        room = self.get_room(code)
        if not room or player_id != room.host_player_id or room.started:
            return False
            
        filled_seats = [s for s in room.seats if s is not None]
        if len(filled_seats) < 2:
            return False
            
        # Initialize GameState with the seat configuration
        room.state = GameState(player_configs=filled_seats, mode="sudden_death")
        room.state.setup_game()
        room.started = True
        return True
