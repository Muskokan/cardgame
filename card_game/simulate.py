import random
import time
from datetime import datetime
from collections import defaultdict
import sys
import os

# Add the app directory to the path so we can import the game engine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from engine import GameState

NUM_GAMES = 1000

print(f"Starting {NUM_GAMES} headless games...")

class SimStats:
    def __init__(self):
        self.wins_by_wincon = {"4 Identical": 0, "1 of Each": 0}
        self.card_resolves = defaultdict(int)
        self.card_wins = defaultdict(int) 
        self.card_targets = defaultdict(lambda: defaultdict(int)) # source_card -> target -> count
        self.playstyle_wins = defaultdict(int)
        self.playstyle_games = defaultdict(int)
        self.total_games = 0

stats = SimStats()

PLAYER_CONFIGS = [
    {"name": "Combo", "is_bot": True, "bot_profile": "Combo"},
    {"name": "Ruthless", "is_bot": True, "bot_profile": "Ruthless"},
    {"name": "Defensive", "is_bot": True, "bot_profile": "Defensive"},
    {"name": "Aggressive", "is_bot": True, "bot_profile": "Aggressive"}
]

start_time = time.time()

for i in range(NUM_GAMES):
    state = GameState(num_players=4, mode="sudden_death", player_configs=PLAYER_CONFIGS)
    state.setup_game()
    
    for p in state.players:
        if p.bot_profile:
            stats.playstyle_games[p.bot_profile.name] += 1
            
    safety_counter = 0
    while not state.game_over and safety_counter < 5000:
        safety_counter += 1
        active_p = state.get_active_player()
        pending = state.pending_action
        
        if state.current_phase.name == "DRAW": pass
        elif state.current_phase.name == "CAUSE_CARD_SELECTION" or state.current_phase.name == "STOCK_CARD_SELECTION":
            import ai
            idx = ai.bot_choose_cause(active_p, state)
            state.process_input(active_p, "CAUSE", card_index=idx)
        elif state.current_phase.name == "REACTION_SELECTION":
            import ai
            p_idx = state.priority_player_idx
            priority_p = state.players[p_idx]
            idx = ai.bot_choose_reaction(priority_p, state)
            if idx == -1: state.process_input(priority_p, "PASS")
            else: state.process_input(priority_p, "REACT", card_index=idx)
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
            if "choice" in cost_dict: state.process_input(p, "CHOOSE_COST_OPTION", **cost_dict)
            else: state.process_input(p, "PAY_COST", **cost_dict)
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
                state.process_input(p, pending["type"], card_index=0)
            else: pass 
        elif state.current_phase.name == "REVIEW":
            state.process_input(active_p, "END_TURN")

    stats.total_games += 1
    if state.winner:
        if state.winner.bot_profile:
            stats.playstyle_wins[state.winner.bot_profile.name] += 1
        seq_names = [c.name for c in state.winner.sequence]
        counts = {n: seq_names.count(n) for n in set(seq_names)}
        if any(c >= 4 for c in counts.values()):
            stats.wins_by_wincon["4 Identical"] += 1
        else:
            stats.wins_by_wincon["1 of Each"] += 1
        for n in set(seq_names):
            stats.card_wins[n] += 1
            
    # Track history
    for i, entry in enumerate(state.full_history):
        if entry["event"] == "ACTION_RESOLVING":
            card_name = entry["data"].get("card")
            if card_name:
                stats.card_resolves[card_name] += 1

                # Attempt to determine target from surrounding TARGET_SELECTED events
                # We can trace backwards slightly for TARGET_SELECTED for this card
                # Or just use the narrative log
                target_str = None
                for j in range(i-1, max(-1, i-20), -1):
                    if state.full_history[j]["event"] == "TARGET_SELECTED" and state.full_history[j]["data"].get("for_card") == card_name:
                        target_str = state.full_history[j]["data"].get("target_name")
                        break
                    
                if not target_str and card_name in ["Pressure", "Vacuum"]:
                    target_str = "Player" # Inherently targets players
                    
                if target_str:
                    # Clean up Target Str
                    clean_target = target_str.split("/")[-1] if "/" in target_str else target_str
                    stats.card_targets[card_name][clean_target] += 1

def g_rep(stats):
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
    
    # CARD POWER RANKINGS
    lines.append("── CARD POWER RANKINGS ───────────────────────────────────────────────────────────")
    lines.append("")
    lines.append("  CARD                 TIER   WIN RATE     RESOLVES     RESOLVE SHARE")
    lines.append("  ───────────────────────────────────────────────────────────────────")
    
    total_resolves = sum(stats.card_resolves.values()) or 1
    
    # Map back physical abilities, we treat the Dual-Card as the unified rating
    card_ranks = []
    for card, wins in stats.card_wins.items():
        wr = wins / stats.total_games
        res = stats.card_resolves.get(card, 0)
        share = res / total_resolves
        tier = "S" if wr >= 0.7 else "A" if wr >= 0.5 else "B" if wr >= 0.3 else "C"
        bars = int(share * 100 / 2)
        bar_str = "█" * min(10, bars) + "░" * max(0, 10 - bars)
        card_ranks.append({"name": card, "tier": tier, "wr": wr, "res": res, "share": share, "bar": bar_str})
        
    # Also add pure reactions that don't get 'wins' like Stagnation
    for r_card in ["Stagnation", "Vacuum", "Reflection", "Stasis", "Assimilation", "Momentum", "Pressure", "Resonance", "Echo", "Erosion"]:
        if r_card not in [c["name"] for c in card_ranks]:
            res = stats.card_resolves.get(r_card, 0)
            if res > 0:
                share = res / total_resolves
                bars = int(share * 100 / 2)
                bar_str = "█" * min(10, bars) + "░" * max(0, 10 - bars)
                # Infer wr from dual card
                parent_card = ""
                for c in ["Stagnation/Momentum", "Vacuum/Pressure", "Reflection/Resonance", "Stasis/Echo", "Assimilation/Erosion"]:
                    if r_card in c: parent_card = c
                
                wr = stats.card_wins.get(parent_card, 0) / stats.total_games
                tier = "S" if wr >= 0.7 else "A" if wr >= 0.5 else "B" if wr >= 0.3 else "C"
                card_ranks.append({"name": r_card, "tier": tier, "wr": wr, "res": res, "share": share, "bar": bar_str})
        
    card_ranks.sort(key=lambda x: x["wr"], reverse=True)
    for c in card_ranks:
        lines.append(f"  {c['name']:<20} {c['tier']:<6} {c['wr']*100:>5.1f}%     {c['res']:>6,}    {c['bar']} {c['share']*100:.1f}%")

    lines.append("")
    lines.append("  TABLE NOTES")
    lines.append("  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─")
    lines.append("  Tier S (≥70% win rate): These cards appear in the winning player's sequence in 70%+ of games.")
    lines.append("  Tier A (50-69%): Strong contributors that are frequently part of winning strategies.")
    lines.append("  Tier B (30-49%): Situational or reactive cards that support but rarely carry a win alone.")
    lines.append("  Tier C (<30%): Either undertuned, highly reactive, or penalized by their own costs.")
    lines.append("")
    
    lines.append("── TARGETING META ────────────────────────────────────────────────────────────────")
    lines.append("")
    lines.append("  SOURCE               #1 TARGET          COUNT      %        FULL BREAKDOWN")
    lines.append("  ────────────────────────────────────────────────────────────────────────")
    
    for c in card_ranks:
        if c["name"] in stats.card_targets and len(stats.card_targets[c["name"]]) > 0:
            targets = stats.card_targets[c["name"]]
            sorted_t = sorted(targets.items(), key=lambda x: x[1], reverse=True)
            top_t, top_c = sorted_t[0]
            total_t = sum(targets.values())
            pct = (top_c / total_t) * 100
            
            breakdown = []
            for t_name, t_c in sorted_t[1:3]:
                breakdown.append(f"{t_name}: {int(t_c/total_t*100)}%")
            bd_str = "also: " + ", ".join(breakdown) if breakdown else ""
            
            lines.append(f"  {c['name']:<20} {top_t:<18} {top_c:>6,}    {pct:>5.1f}%   {bd_str}")
            
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
    lines.append("╔══════════════════════════════════════════════════════════════════════════════╗")
    lines.append("║                           INDIVIDUAL CARD REPORTS                            ║")
    lines.append("╚══════════════════════════════════════════════════════════════════════════════╝")
    lines.append("")


    
    import json
    import os
    
    # Load card definitions
    cards_path = os.path.join(os.path.dirname(__file__), 'app', 'cards.json')
    try:
        with open(cards_path, 'r', encoding='utf-8') as f:
            card_data = json.load(f)["abilities"]
    except Exception:
        card_data = {}

    for c in card_ranks:
        name = c['name']
        if "/" in name:
            react_name, cause_name = name.split("/")
            role = "Dual (Cause & Effect)"
            desc = f"Cause: {cause_name} | Effect: {react_name}"
            # Use unified stats
            res = stats.card_resolves.get(react_name, 0) + stats.card_resolves.get(cause_name, 0) + stats.card_resolves.get(name, 0)
        else:
            is_react = name in ["Stagnation", "Vacuum", "Reflection", "Stasis", "Assimilation"]
            role = "Effect" if is_react else "Cause"
            desc = card_data.get(name, {}).get("description", "Unknown ability.")
            res = stats.card_resolves.get(name, 0)
            
        wr = c['wr']
        diff = wr - 0.487
        
        lines.append("┌" + "─"*78 + "┐")
        center_name = f" {name.upper()} "
        lines.append(f"│{center_name:^78}│")
        lines.append("├" + "─"*78 + "┤")
        lines.append(f"│  Role: {role:<70}│")
        
        # Break description into lines if it's too long
        desc_lines = [desc[i:i+65] for i in range(0, len(desc), 65)]
        if not desc_lines: desc_lines = [""]
        lines.append(f"│  Mechanic: {desc_lines[0]:<66}│")
        for d in desc_lines[1:]:
            lines.append(f"│            {d:<66}│")
            
        lines.append("└" + "─"*78 + "┘")
        lines.append("")
        
        if wr >= 0.7: score_bar = "[───────────│───◆──────]   +2 / ±5   [OVERTUNED]"
        elif wr >= 0.5: score_bar = "[───────────│─◆────────]   +1 / ±5   [SLIGHTLY STRONG]"
        elif wr >= 0.3: score_bar = "[───────────◆──────────]   +0 / ±5   [BALANCED]"
        else: score_bar =           "[─────◆─────│──────────]   -2 / ±5   [UNDERTUNED]"
            
        lines.append(f"  BALANCE SCORE   {score_bar}")
        lines.append(f"  Win Rate: {wr*100:.1f}%  (avg: 48.7%  |  delta: {diff*100:+.1f}%)")
        lines.append(f"  Resolves: {res:>} ")
        lines.append("")
        lines.append(f"  STRATEGIC OVERVIEW")
        lines.append("  ────────────────────────────────────────")
        
        # Give dynamic insights based on its performance
        top_targets_str = ""
        if name in stats.card_targets and len(stats.card_targets[name]) > 0:
            top_t = sorted(stats.card_targets[name].items(), key=lambda x: x[1], reverse=True)[0][0]
            top_targets_str = f"It most frequently targets {top_t}."
            
        if wr > 0.6:
            lines.append("  ✔ Statistically dominant in the current simulation meta.")
            lines.append(f"  ✔ Appears in {wr*100:.1f}% of winning sequences.")
            if top_targets_str: lines.append(f"  ✔ {top_targets_str}")
        elif wr < 0.4:
            lines.append("  ✘ Struggles to convert board presence into active wins.")
            lines.append(f"  ✘ Heavily situational or reliant on specific board states.")
            if top_targets_str: lines.append(f"  ✔ {top_targets_str}")
        else:
            lines.append("  ✔ Consistently balanced performance across varied game states.")
            if top_targets_str: lines.append(f"  ✔ {top_targets_str}")
            
        lines.append("")


    return "\n".join(lines)

report_text = g_rep(stats)
with open("Card_Power_Analysis.txt", "w", encoding="utf-8") as f:
    f.write(report_text)

time_taken = time.time() - start_time
print(f"Simulation completed in {time_taken:.2f} seconds.")
print("Saved to Card_Power_Analysis.txt")
