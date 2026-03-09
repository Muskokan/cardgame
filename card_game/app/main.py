import sys
import random
import os
import signal

# Ensure terminal supports Unicode symbols (⚱, 🪦, ✦)
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8') # type: ignore
    except AttributeError:
        # Fallback for Python versions < 3.7
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add current directory to path so it can find local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import Card, Player, Action, TargetRequirement, Phase
from view import ConsoleView, GameExit
from engine import GameState
import ai

# UI functions moved to view.py
def show_rules(view):
    """Read and display the rules document section-by-section in the terminal."""
    rules_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.md")
    if not os.path.exists(rules_path):
        view.log("Rules file not found!")
        return

    with open(rules_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    def clean(line):
        """Strip markdown syntax for clean console output."""
        import re
        line = re.sub(r'^#{1,6}\s*', '', line)           # remove ## headers
        line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)     # **bold** → plain
        line = re.sub(r'\*(.*?)\*', r'\1', line)          # *italic* → plain
        line = re.sub(r'`(.*?)`', r'\1', line)            # `code` → plain
        return line.rstrip()

    # Group lines into sections (split on top-level ## headings)
    sections = []
    current = []
    for line in lines:
        if line.startswith('## ') and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)

    width = 72
    print("\n" + "═" * width)
    print(f"{'  WINDFALL — HOW TO PLAY':^{width}}")
    print("═" * width)

    for sec_idx, section in enumerate(sections):
        print()
        for line in section:
            cleaned = clean(line)
            if cleaned:
                # Top-level section headers
                if line.startswith('## '):
                    print(f"\n{'─' * width}")
                    print(f"  {cleaned}")
                    print(f"{'─' * width}")
                # Sub-section headers
                elif line.startswith('### '):
                    print(f"\n  ▶ {cleaned}")
                else:
                    # Wrap long lines
                    if len(cleaned) > width - 4:
                        words = cleaned.split()
                        row = "    "
                        for word in words:
                            if len(row) + len(word) + 1 > width:
                                print(row)
                                row = "    " + word + " "
                            else:
                                row += word + " "
                        if row.strip():
                            print(row)
                    else:
                        print(f"  {cleaned}")

        # Pause between sections (except the last)
        if sec_idx < len(sections) - 1:
            input("\n  [Press Enter for next section...]")

    print("\n" + "═" * width)
    input("  [Press Enter to return to the main menu...]")
    print()


def configure_game(view):
    while True:
        view.log("\n--- WINDFALL ---")
        setup_idx = view.prompt_choice("Main Menu", [
            "How to Play / Rules",
            "Quick Start — 1v1 (vs 1 AI)", 
            "Quick Start — 4-Player (vs 3 AI)", 
            "4-Bot Simulation",
            "Custom Configuration"
        ])
        
        if setup_idx == 0:
            # Show rules and loop back to menu
            show_rules(view)
            continue
        elif setup_idx == 1:
            # 1v1 Quick Start
            name = input("Enter your name: ").strip()
            if not name:
                name = "Player 1"
            return "sudden_death", 2, 1, [name]
        elif setup_idx == 2:
            # 4-Player Quick Start
            name = input("Enter your name: ").strip()
            if not name:
                name = "Player 1"
            return "sudden_death", 4, 3, [name]
        elif setup_idx == 3:
            # 4-Bot Simulation
            return "sudden_death", 4, 4, []
            
        # Custom Configuration
        view.log("\n--- Custom Configuration ---")
        while True:
            try:
                total_players = int(input("Enter total number of players (2-4): "))
                if 2 <= total_players <= 4:
                    break
                view.log("Must be between 2 and 4.")
            except ValueError:
                view.log("Invalid number.")
                
        while True:
            try:
                ai_count = int(input(f"Enter number of AI players (0-{total_players}): "))
                if 0 <= ai_count <= total_players:
                    break
                view.log(f"Must be between 0 and {total_players}.")
            except ValueError:
                view.log("Invalid number.")
                
        human_names = []
        num_humans = total_players - ai_count
        for i in range(num_humans):
            name = input(f"Enter name for Player {i+1}: ").strip()
            if not name:
                name = f"Player {i+1}"
            human_names.append(name)
                
        return "sudden_death", total_players, ai_count, human_names


def handle_pending_action(state: GameState, view: ConsoleView):
    pending = state.pending_action
    if not pending:
        return
        
    p_type = pending["type"]
    player = state.players[pending["player_idx"]]
    
    if p_type == "COST_SELECTION":
        tag = pending["tag"]
        if tag.name == "Entropy":
            if player.is_bot:
                import random
                p_idx = random.randint(0, len(player.hand) - 1)
            else:
                view.log(f"Choose an EXTRA card from your hand to [Entropy] as a cost:")
                p_idx = view.prompt_choice("Card", [c.name for c in player.hand])
            state.submit_pending_input({"cost_type": "Entropy", "card_index": p_idx})
            
        elif tag.name == "Sever":
            if player.is_bot:
                cost_card = ai.bot_choose_target_sequence_card(player, state, player)
                c_name = cost_card.name if cost_card else ""
            else:
                view.log(f"Choose a card in YOUR sequence to [Sever] as a cost:")
                unique_names = list(set([c.name for c in player.sequence]))
                if unique_names:
                    c_idx = view.prompt_choice("Your Cause Card", unique_names)
                    c_name = unique_names[c_idx]
                else:
                    c_name = ""
            state.submit_pending_input({"cost_type": "Sever", "card_name": c_name})
            
        elif tag.name == "Choice":
            opts = tag.params.get("options", [])
            can_pitch = "Entropy" in opts and len(player.hand) > 0
            can_destroy = "Sever" in opts and len(player.sequence) > 0
            
            cost_choice = -1
            if player.is_bot:
                cost_choice = 0 if can_pitch and len(player.hand) >= 2 else (1 if can_destroy else 0)
                if cost_choice == 1 and not can_destroy: cost_choice = 0
                if cost_choice == 0 and not can_pitch: cost_choice = 1
            else:
                view.log(f"Choose how to pay the cost:")
                avail_opts = []
                if can_pitch: avail_opts.append("Entropy an extra card from your hand")
                if can_destroy: avail_opts.append("Sever a card in your Sequence")
                if not avail_opts:
                    return # Handled by engine fizzle if they submit bad choice or engine shouldn't prompt if unable to pay
                c_idx = view.prompt_choice("Cost Type", avail_opts)
                chosen_opt = avail_opts[c_idx]
                cost_choice = 0 if "Entropy" in chosen_opt else 1
                
            if cost_choice == 0:
                if player.is_bot:
                    import random
                    p_idx = random.randint(0, len(player.hand) - 1)
                else:
                    view.log(f"Choose a card to [Entropy]:")
                    p_idx = view.prompt_choice("Card", [c.name for c in player.hand])
                state.submit_pending_input({"cost_type": "Entropy", "card_index": p_idx})
            else:
                if player.is_bot:
                    cost_card = ai.bot_choose_target_sequence_card(player, state, player)
                    c_name = cost_card.name if cost_card else ""
                else:
                    view.log(f"Choose a card in your Sequence to [Sever]:")
                    unique_names = list(set([c.name for c in player.sequence]))
                    s_idx = view.prompt_choice("Cause Card", unique_names)
                    c_name = unique_names[s_idx]
                state.submit_pending_input({"cost_type": "Sever", "card_name": c_name})

    elif p_type == "TARGET_SELECTION":
        reqs = pending.get("requirements", [])
        target_card = None
        target_player = None
        copied_name = None
        
        # We process requirements based on target enum
        # Build a comprehensive list of all valid targets across all requirements
        valid_targets = []  # List of (target_player, target_card, copied_name, display_text)
        
        for req in reqs:
            if req == TargetRequirement.PLAYER:
                for opp in [p for p in state.players if p != player]:
                    valid_targets.append((opp, None, None, f"[Player] {opp.name}"))
                    
            elif req == TargetRequirement.OPPONENT_CAUSE:
                for opp in [p for p in state.players if p != player and p.sequence]:
                    for c in opp.sequence:
                        valid_targets.append((opp, c, None, f"[{opp.name}'s Cause] {c.name}"))

            elif req == TargetRequirement.GRAVEYARD:
                for c in state.graveyard:
                    valid_targets.append((None, c, None, f"[Graveyard] {c.name}"))

            elif req == TargetRequirement.ANY_CAUSE:
                for p in state.players:
                    for c in p.sequence:
                        valid_targets.append((p, c, c.name, f"[{p.name}'s Cause] {c.name}"))
                        
            elif req == TargetRequirement.NEXUS_CARD:
                for c in state.nexus:
                    owner_action = next((a for a in state.stack if a.source_card == c), None)
                    if owner_action and owner_action.source_player != player:
                        valid_targets.append((None, c, None, f"[Nexus: {owner_action.source_player.name}] {c.name}"))
                        
        if not valid_targets:
            target_player, target_card, copied_name = None, None, None
        else:
            if player.is_bot:
                target_player, target_card, copied_name = ai.bot_choose_target_from_list(player, state, valid_targets, reqs)
            else:
                view.log(f"Choose a target for {pending.get('card_name', 'Ability')}:")
                options = [desc for _, _, _, desc in valid_targets]
                c_idx = view.prompt_choice("Target", options)
                target_player, target_card, copied_name, _ = valid_targets[c_idx]
                
        state.submit_pending_input({
            "target_card": target_card,
            "target_player": target_player,
            "copied_name": copied_name
        })

def play_game():
    view = ConsoleView()
    view.log("Welcome to Cause & Effect Card Game!")
    mode, total_players, ai_count, human_names = configure_game(view)
    state = GameState(num_players=total_players, num_bots=ai_count, mode=mode, human_names=human_names, view=view)
    
    state.setup_game()
    view.render_events(state)
    
    last_phase = None
    last_priority = None
    
    while not state.game_over:
        if state.pending_action:
            handle_pending_action(state, view)
            view.render_events(state)
            continue
            
        current_p = state.get_active_player()
        priority_p = state.players[state.priority_player_idx]
            
        if state.current_phase != last_phase or state.priority_player_idx != last_priority:
            view.show_board(state)
            last_phase = state.current_phase
            last_priority = state.priority_player_idx
        
        if state.current_phase == Phase.CAUSE_CARD_SELECTION:
            if last_phase != Phase.CAUSE_CARD_SELECTION:
                view.log(f"--- {current_p.name}'s Turn ---")
            view.log("\n[Phase: CAUSE]")
            view.log("\n[Phase: CAUSE]")
            if not current_p.is_bot:
                choice_idx = view.show_card_menu(current_p, state, mode="CAUSE")
            else:
                choice_idx = ai.bot_choose_cause(current_p, state)
            
            state.process_input(current_p, "CAUSE", card_index=choice_idx)
            view.render_events(state)
            
        elif state.current_phase == Phase.REACTION_SELECTION:
            # Priority player logic
            if not priority_p.hand:
                state.process_input(priority_p, "PASS")
                continue
                
            view.log(f"\nPriority: {priority_p.name} (Decision {state.reaction_passes + 1}/{len(state.players)})")
            view.log(f"Current Stack: {[str(a) for a in state.stack]}")
            if not priority_p.is_bot:
                want_to_react = view.prompt_choice(f"Do you want to play a React ability in response?", ["Yes", "No (Pass)"])
                if want_to_react == 0:
                    while True:
                        choice_idx = view.show_card_menu(priority_p, state, mode="REACT")
                        chosen_card = priority_p.hand[choice_idx]
                        if chosen_card.react_ability.name == "Betray" and len(priority_p.sequence) == 0:
                            view.log("\n[ERROR] You cannot play Betray without a card in your Sequence to destroy.\n")
                            continue
                        break
                    state.process_input(priority_p, "REACT", card_index=choice_idx)
                else:
                    state.process_input(priority_p, "PASS")
            else:
                choice_idx = ai.bot_choose_reaction(priority_p, state)
                if choice_idx != -1:
                    state.process_input(priority_p, "REACT", card_index=choice_idx)
                else:
                    state.process_input(priority_p, "PASS")
            view.render_events(state)
            
        elif state.current_phase == Phase.RESOLUTION:
            # Resolution is now a pure backend phase
            view.render_events(state)
            
        elif state.current_phase == Phase.REVIEW:
            view.render_events(state)
            if not state.game_over:
                 view.display_turn_summary(state)
                 view.prompt_continue("\nPress Enter to begin the next turn")
                 state.process_input(current_p, "END_TURN")
            
    # Final board show
    view.show_board(state)
    if state.winner:
        view.log(f"\nCongratulations {state.winner.name}! You have won Cause & Effect!")
    else:
        view.log("\nThe game ended in a draw.")
def signal_handler(sig, frame):
    print('\nProcess terminated cleanly.')
    sys.exit(0)
    
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform == 'win32':
        try:
            signal.signal(signal.SIGBREAK, signal_handler)
        except AttributeError:
            pass
    else:
        signal.signal(signal.SIGTERM, signal_handler)

    try:
        play_game()
    except KeyboardInterrupt:
        print("\nGame aborted.")
        sys.exit(0)
    except GameExit as e:
        print(f"\n{e}")
        sys.exit(0)
