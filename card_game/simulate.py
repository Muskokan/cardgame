import random
import time
from datetime import datetime
from collections import defaultdict
import sys
import os

# Add the app directory to the path so we can import the game engine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from engine import GameState
from models import TargetRequirement

NUM_GAMES = 1000

print(f"Starting {NUM_GAMES} headless games...")

class SimStats:
    def __init__(self):
        self.wins_by_wincon = {"4 Identical": 0, "1 of Each": 0}
        self.card_resolves = defaultdict(int)
        self.card_wins = defaultdict(int) 
        self.card_targets = defaultdict(lambda: defaultdict(int)) # card -> target_name -> count
        self.playstyle_wins = defaultdict(int)
        self.playstyle_games = defaultdict(int)
        
        self.total_games = 0

stats = SimStats()

# The specific bots we want to run
PLAYER_CONFIGS = [
    {"name": "Combo", "is_bot": True, "bot_profile": "Combo"},
    {"name": "Ruthless", "is_bot": True, "bot_profile": "Ruthless"},
    {"name": "Defensive", "is_bot": True, "bot_profile": "Defensive"},
    {"name": "Aggressive", "is_bot": True, "bot_profile": "Aggressive"}
]

start_time = time.time()

for i in range(NUM_GAMES):
    # Setup game
    state = GameState(num_players=4, mode="sudden_death", player_configs=PLAYER_CONFIGS)
    state.setup_game()
    
    # Track playstyle participation
    for p in state.players:
        if p.bot_profile:
            stats.playstyle_games[p.bot_profile.name] += 1
            
    # Headless loop
    safety_counter = 0
    while not state.game_over and safety_counter < 5000:
        safety_counter += 1
        
        active_p = state.get_active_player()
        pending = state.pending_action
        
        if state.current_phase.name == "DRAW":
            # Handled internally 
            pass
            
        elif state.current_phase.name == "STOCK_CARD_SELECTION":
            import ai
            idx = ai.bot_choose_stock(active_p, state)
            state.process_input(active_p, "STOCK", card_index=idx)
            
        elif state.current_phase.name == "REACTION_SELECTION":
            import ai
            p_idx = state.priority_player_idx
            priority_p = state.players[p_idx]
            idx = ai.bot_choose_reaction(priority_p, state)
            if idx == -1:
                state.process_input(priority_p, "PASS")
            else:
                state.process_input(priority_p, "REACT", card_index=idx)
                
        elif state.current_phase.name == "TARGETING" and pending:
            import ai
            p_idx = pending.get("player_idx") if pending.get("player_idx") is not None else pending.get("source_player_idx")
            p = state.players[p_idx]
            targets_dict = ai.bot_choose_targets(p, state)
            state.process_input(p, "SET_TARGETS", **targets_dict)
            
        elif state.current_phase.name == "PAYING_COSTS" and pending:
            import ai
            p_idx = pending.get("player_idx") if pending.get("player_idx") is not None else pending.get("source_player_idx")
            p = state.players[p_idx]
            cost_dict = ai.bot_choose_cost(p, state)
            # Send correct type based on cost needed
            if "choice" in cost_dict:
                state.process_input(p, "CHOOSE_COST_OPTION", **cost_dict)
            else:
                state.process_input(p, "PAY_COST", **cost_dict)
            
        elif state.current_phase.name == "RESOLUTION":
            if pending and pending.get("type") == "SNATCH_PICK":
                import ai
                p_idx = pending.get("player_idx") if pending.get("player_idx") is not None else pending.get("source_player_idx")
                p = state.players[p_idx]
                void_pool = pending.get("void_pool", [])
                pick_idx = ai.bot_choose_void_pick(p, void_pool)
                state.process_input(p, pending["type"], card_index=pick_idx)
            elif pending and pending.get("type") == "RESOLUTION_ENTROPY":
                import ai
                p_idx = pending.get("player_idx") if pending.get("player_idx") is not None else pending.get("source_player_idx")
                p = state.players[p_idx]
                state.process_input(p, pending["type"], card_index=0) # Just pick first card
            else:
                # Engine handles internal stack auto-resolve but just in case:
                pass 
                
        elif state.current_phase.name == "REVIEW":
            state.process_input(active_p, "END_TURN")

    # Record post-game metrics
    stats.total_games += 1
    
    # Win condition type
    if state.winner:
        if state.winner.bot_profile:
            stats.playstyle_wins[state.winner.bot_profile.name] += 1
            
        seq_names = [c.name for c in state.winner.sequence]
        counts = {n: seq_names.count(n) for n in set(seq_names)}
        if any(c >= 4 for c in counts.values()):
            stats.wins_by_wincon["4 Identical"] += 1
        else:
            stats.wins_by_wincon["1 of Each"] += 1
            
        # Record "win rate" for cards that were in the winner's sequence
        for n in set(seq_names):
            # The name might be "Vacuum/Pressure", we need the stock name conceptually, but just use full name
            stats.card_wins[n] += 1
            
    # Parse history for targeting and resolves
    for entry in state.full_history:
        if entry["event"] == "ACTION_RESOLVING":
            card_name = entry["data"].get("card")
            if card_name:
                stats.card_resolves[card_name] += 1
                
        # Targets are somewhat difficult to extract from the raw events, 
        # but we can look for narrative targeting info if present, OR we patch Action
        # For now, we'll extract from NARRATIVE if any. In Cause & Effect, we may want to inject it.

# Generate Report 
def generate_report(stats):
    lines = []
    lines.append("╔══════════════════════════════════════════════════════════════════════════════╗")
    lines.append("║                    CAUSE & EFFECT — CARD POWER ANALYSIS                      ║")
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"║                        Generated: {date_str}                        ║")
    lines.append(f"║                     Data Source: {stats.total_games:,} Simulated Games                      ║")
    lines.append("╚══════════════════════════════════════════════════════════════════════════════╝")
    lines.append("")
    
    w4 = stats.wins_by_wincon["4 Identical"]
    w5 = stats.wins_by_wincon["1 of Each"]
    lines.append(f"  Win Conditions — 4 Identical: {w4:,} ({(w4/stats.total_games)*100:.1f}%), 1 of Each 5: {w5:,} ({(w5/stats.total_games)*100:.1f}%)")
    lines.append("")
    
    lines.append("── CARD POWER RANKINGS ───────────────────────────────────────────────────────────")
    lines.append("")
    lines.append("  CARD                 TIER   WIN RATE     RESOLVES     RESOLVE SHARE")
    lines.append("  ───────────────────────────────────────────────────────────────────")
    
    # Calculate totals
    total_resolves = sum(stats.card_resolves.values()) or 1
    
    # Sort by win rate
    card_ranks = []
    for card, wins in stats.card_wins.items():
        wr = wins / stats.total_games
        res = stats.card_resolves.get(card, 0)
        share = res / total_resolves
        
        tier = "S" if wr >= 0.7 else "A" if wr >= 0.5 else "B" if wr >= 0.3 else "C"
        
        # Build bar
        bars = int(share * 100 / 2) # approx 1 block per 2%
        bar_str = "█" * min(10, bars) + "░" * max(0, 10 - bars)
        
        card_ranks.append({
            "name": card, "tier": tier, "wr": wr, "res": res, "share": share, "bar": bar_str
        })
        
    card_ranks.sort(key=lambda x: x["wr"], reverse=True)
    
    for c in card_ranks:
        lines.append(f"  {c['name']:<20} {c['tier']:<6} {c['wr']*100:>5.1f}%     {c['res']:>6,}    {c['bar']} {c['share']*100:.1f}%")

    lines.append("")
    lines.append("── AI PLAYSTYLE PERFORMANCE ──────────────────────────────────────────────────────")
    lines.append("")
    lines.append("  PLAYSTYLE        WINS       WIN RATE     VS FIELD")
    lines.append("  ────────────────────────────────────────────────────")
    for ps, wins in sorted(stats.playstyle_wins.items(), key=lambda x: x[1], reverse=True):
        wr = wins / stats.total_games
        bars = "█" * int(wr * 30)
        lines.append(f"  {ps:<16} {wins:>6,}       {wr*100:>4.1f}%    {bars}")
        
    lines.append("")
    return "\n".join(lines)

report_text = generate_report(stats)

with open("Card_Power_Analysis.txt", "w", encoding="utf-8") as f:
    f.write(report_text)

time_taken = time.time() - start_time
print(f"Simulation completed in {time_taken:.2f} seconds.")
print("Saved to Card_Power_Analysis.txt")
