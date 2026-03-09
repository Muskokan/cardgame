import json
import asyncio
import time
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
import os

from room_manager import RoomManager
from models import Player, Phase

app = FastAPI()
manager = RoomManager()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_sweeper())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

# Data models for REST
class CreateRoomResponse(BaseModel):
    code: str
    player_id: str

class JoinRoomRequest(BaseModel):
    name: Optional[str] = None

class JoinRoomResponse(BaseModel):
    player_id: str
    code: str

# REST Endpoints
@app.post("/api/create", response_model=CreateRoomResponse)
async def create_room():
    code, player_id = manager.create_room()
    return {"code": code, "player_id": player_id}

@app.post("/api/join/{code}", response_model=JoinRoomResponse)
async def join_room(code: str):
    player_id = manager.join_room(code)
    if not player_id:
        raise HTTPException(status_code=404, detail="Room not found or already started")
    return {"player_id": player_id, "code": code}

@app.get("/api/room/{code}")
async def get_room(code: str):
    room = manager.get_room(code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room.to_dict()

@app.get("/api/room/{code}/state")
async def get_room_state(code: str):
    """Full game state including all player hands and complete event history (for analysis)."""
    room = manager.get_room(code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if not room.state:
        raise HTTPException(status_code=400, detail="Game not started yet")
    state = room.state
    # Build full player view (all hands visible — analysis only)
    players_full = [p.to_dict(include_hand=True) for p in state.players]
    return {
        "turn_number": state.turn_number,
        "current_phase": state.current_phase.name,
        "game_over": state.game_over,
        "winner_name": state.winner.name if state.winner else None,
        "active_player": state.players[state.active_player_idx].name,
        "players": players_full,
        "deck_count": len(state.deck),
        "nexus": [c.to_dict() for c in state.nexus],
        "graveyard": [c.to_dict() for c in state.graveyard],
        "stack": [a.to_dict() for a in state.stack],
        "full_history": state.full_history,
        "event_history": state.event_history,
    }

# WebSocket Logic
async def broadcast_state(code: str):
    room = manager.get_room(code)
    if not room:
        return
    
    room.update_activity()
    state_json = room.state.to_dict() if room.state else {}
    for player_id, ws in list(room.connections.items()):
        # Get the Player object in the game state for this player_id
        perspective_player = None
        if room.state:
            perspective_player = next((p for p in room.state.players if p.external_id == player_id), None)
            
        try:
            if room.state:
                # Game state update
                state_dict = room.state.to_dict(perspective_player=perspective_player)
                await ws.send_json({
                    "type": "STATE_UPDATE",
                    "state": state_dict
                })
            else:
                # Lobby update
                await ws.send_json({
                    "type": "LOBBY_UPDATE",
                    "seats": room.seats,
                    "host_player_id": room.host_player_id
                })
        except Exception as e:
            print(f"Error broadcasting to {player_id}: {e}")

async def handle_bot_turns(code: str):
    room = manager.get_room(code)
    if not room or not room.state or room.state.game_over:
        return
        
    state = room.state
    # Check if current priority belongs to a bot
    # Note: GameState.priority_player_idx or GameState.active_player_idx?
    # REACTION_SELECTION uses priority_player_idx.
    # CAUSE_CARD_SELECTION uses active_player_idx.
    
    current_p = None
    if state.current_phase == Phase.CAUSE_CARD_SELECTION:
        current_p = state.get_active_player()
    elif state.current_phase in [Phase.REACTION_SELECTION, Phase.TARGETING, Phase.PAYING_COSTS]:
        # Priority player acts in these phases
        # NOTE: Even if it's not strictly 'priority' in targeting/costs, 
        # the user who needs to act is referenced by priority_player_idx or pending_action
        if state.current_phase == Phase.REACTION_SELECTION:
            current_p = state.players[state.priority_player_idx]
        else:
            # TARGETING and PAYING_COSTS use the player who triggered the effect
            idx = state.pending_action.get("player_idx") if state.pending_action else None
            if idx is not None:
                current_p = state.players[idx]
    elif state.current_phase == Phase.REVIEW:
        # The active player confirms the end of turn
        current_p = state.get_active_player()
        
    if current_p and current_p.is_bot:
        await asyncio.sleep(1) # Visual delay for bot thinking
        import ai
        
        action_taken = False
        if state.current_phase == Phase.CAUSE_CARD_SELECTION:
            idx = ai.bot_choose_cause(current_p, state)
            state.process_input(current_p, "CAUSE", card_index=idx)
            action_taken = True
        elif state.current_phase == Phase.REACTION_SELECTION:
            idx = ai.bot_choose_reaction(current_p, state)
            if idx == -1:
                state.process_input(current_p, "PASS")
            else:
                state.process_input(current_p, "REACT", card_index=idx)
            action_taken = True
        elif state.current_phase == Phase.TARGETING:
            targets = ai.bot_choose_targets(current_p, state)
            state.process_input(current_p, "SET_TARGETS", **targets)
            action_taken = True
        elif state.current_phase == Phase.PAYING_COSTS:
            cost = ai.bot_choose_cost(current_p, state)
            state.process_input(current_p, "PAY_COST", **cost)
            action_taken = True
        elif state.current_phase == Phase.REVIEW:
            # Bot just ends review immediately
            state.process_input(current_p, "END_TURN")
            action_taken = True

        if action_taken:
            # Broadcast the new state and schedule the next bot tick if needed
            await broadcast_state(code)
            asyncio.create_task(handle_bot_turns(code))

@app.websocket("/ws/{code}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, code: str, player_id: str):
    room = manager.get_room(code)
    if not room:
        await websocket.close(code=1008, reason="Room not found")
        return
        
    await websocket.accept()
    
    # Reconnect: remove from disconnected_players if they were previously disconnected
    if player_id in room.disconnected_players:
        room.mark_reconnected(player_id)
        # Notify other players they're back
        for pid, ws in list(room.connections.items()):
            if pid != player_id:
                try:
                    reconnect_name = next(
                        (p.name for p in (room.state.players if room.state else [])
                         if p.external_id == player_id),
                        player_id
                    )
                    await ws.send_json({"type": "PLAYER_RECONNECTED", "player_name": reconnect_name})
                except Exception:
                    pass

    room.connections[player_id] = websocket
    
    # Initial broadcast
    await broadcast_state(code)
    
    try:
        while True:
            data = await websocket.receive_json()
            # Handle messages
            action = data.get("action")
            
            if action == "CLAIM_SEAT":
                seat_idx = data.get("seat_idx")
                name = data.get("name", "Unknown")
                if manager.claim_seat(code, player_id, seat_idx, name):
                    await broadcast_state(code)
                    
            elif action == "ASSIGN_BOT":
                seat_idx = data.get("seat_idx")
                profile = data.get("profile")
                if profile is None:
                    if manager.remove_bot(code, player_id, seat_idx):
                        await broadcast_state(code)
                elif manager.assign_bot(code, player_id, seat_idx, profile):
                    await broadcast_state(code)
            
            elif action == "START_GAME":
                if manager.start_game(code, player_id):
                    await broadcast_state(code)
                    asyncio.create_task(handle_bot_turns(code))
                    
            elif room.state and not room.state.game_over:
                # Route game actions to the engine
                # Find the player object associated with this ID
                player = next((p for p in room.state.players if p.external_id == player_id), None)
                if player:
                    try:
                        room.state.process_input(player, action, **data)
                    except Exception as e:
                        import traceback
                        with open("debug_crash.txt", "w") as f:
                            f.write(traceback.format_exc())
                        raise e
                    await broadcast_state(code)
                    # Trigger bot turns if it's now a bot's turn
                    asyncio.create_task(handle_bot_turns(code))
                    
    except WebSocketDisconnect:
        if player_id in room.connections:
            del room.connections[player_id]

        # Mark disconnected and notify remaining players
        room.mark_disconnected(player_id)
        discord_name = next(
            (p.name for p in (room.state.players if room.state else [])
             if p.external_id == player_id),
            player_id
        )
        for pid, ws in list(room.connections.items()):
            try:
                await ws.send_json({"type": "PLAYER_DISCONNECTED", "player_name": discord_name})
            except Exception:
                pass

        # Start auto-pass timer if disconnected player has game priority
        if room.state and not room.state.game_over:
            asyncio.create_task(auto_pass_disconnected(code, player_id))

        # If room is fully empty, start cleanup grace period
        if len(room.connections) == 0:
            asyncio.create_task(cleanup_empty_room(code))

async def auto_pass_disconnected(code: str, player_id: str, timeout: int = 60):
    """If a disconnected player still has priority after timeout seconds, auto-pass for them."""
    await asyncio.sleep(timeout)
    room = manager.get_room(code)
    if not room or not room.state or room.state.game_over:
        return
    # Player reconnected — do nothing
    if player_id not in room.disconnected_players:
        return
    # Check if they still hold priority or are the active player
    state = room.state
    current_p = None
    active = state.players[state.active_player_idx]
    priority = state.players[state.priority_player_idx]
    if active.external_id == player_id:
        current_p = active
    elif priority.external_id == player_id:
        current_p = priority

    if current_p and not current_p.is_bot:
        print(f"[AUTO-PASS] {current_p.name} disconnected — auto-passing after {timeout}s")
        if state.current_phase in [Phase.REACTION_SELECTION]:
            state.process_input(current_p, "PASS")
        elif state.current_phase in [Phase.CAUSE_CARD_SELECTION, Phase.REVIEW]:
            # Can't auto-cause, so skip turn
            state.end_turn()
        await broadcast_state(code)
        asyncio.create_task(handle_bot_turns(code))
        # Notify players of the auto-pass
        for pid, ws in list(room.connections.items()):
            try:
                await ws.send_json({
                    "type": "PLAYER_DISCONNECTED",
                    "player_name": current_p.name,
                    "auto_passed": True
                })
            except Exception:
                pass

async def cleanup_empty_room(code: str):
    """Wait 10 minutes, then delete the room if it's still empty."""
    await asyncio.sleep(600)  # 10 minutes
    room = manager.get_room(code)
    if room and len(room.connections) == 0:
        manager.delete_room(code)

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)

async def background_sweeper():
    """Periodically clean up stale rooms (no connections + no activity > 1hr)."""
    while True:
        await asyncio.sleep(1800) # Every 30 minutes
        now = time.time()
        to_delete = []
        for code, room in manager.rooms.items():
            # If no one is connected and it's been idle for over an hour
            if len(room.connections) == 0 and (now - room.last_activity) > 3600:
                to_delete.append(code)
        
        for code in to_delete:
            manager.delete_room(code)
