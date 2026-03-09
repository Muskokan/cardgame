import random
import re
from models import Phase

from colors import Colors

class GameExit(Exception):
    pass

class GameView:
    """Base interface for all UI implementations."""
    def log(self, message: str):
        pass
        
    def on_event(self, event_type: str, data: dict):
        pass

    def show_board(self, state):
        pass
        
    def prompt_choice(self, prompt_text: str, options: list, player=None) -> int:
        pass
        
    def prompt_continue(self, prompt_text: str):
        pass

class ConsoleView(GameView):
    """Implementation of the UI using standard terminal print and input."""
    
    def clear_screen(self):
        """Clears the terminal and its scrollback buffer."""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')

    def log(self, message: str):
        print(message)

    def _fmt(self, text: str) -> str:
        """Apply symbol substitutions to a log entry."""
        text = text.replace("[SUCCESS]", "✔")
        text = text.replace("[FIZZLE]",  "✘")
        text = text.replace("[DIVERSIFY]",  "⟳")
        text = text.replace(" -> ",      " ⟶ ")
        return text

    def on_event(self, event_type: str, data: dict):
        """Standard terminal event renderer."""
        if event_type == "GAME_START":
            self.log(data.get("message", "Game Started."))
        elif event_type == "CARD_DRAWN":
            self.log(f"  · {data['player']} drew a card.")
        elif event_type == "CARD_STOCKED":
            target = f" ⟶ {data['target']}" if data.get('target') else ""
            self.log(f"  ✦ {Colors.BOLD}{data['player']}{Colors.RESET} » {Colors.SKY_BLUE}{data['card']}{Colors.RESET}{target}")
        elif event_type == "CARD_REACTED":
            target = f" ⟶ {data['target']}" if data.get('target') else ""
            self.log(f"  ⚡ {Colors.BOLD}{data['player']}{Colors.RESET} » {Colors.ORANGE}{data['card']}{Colors.RESET}{target}")
        elif event_type == "REACTION_PASS":
            self.log(f"  ○ {data['player']} passed.")
        elif event_type == "CARD_COUNTERED":
            self.log(f"  ✔ {Colors.SKY_BLUE}Countered{Colors.RESET}: {data.get('card', '')}")
        elif event_type == "EFFECT_RESULT":
            self.log(self._fmt(data.get("message", "")))
        elif event_type == "ACTION_STATUS_UPDATED":
            pass
        elif event_type == "STACK_RESOLUTION_START":
            self.log(f"\n  ─── Resolving ({data.get('count', 0)}) ───")
        elif event_type == "ACTION_RESOLVING":
            self.log(f"  ↳ {data.get('card')} by {data.get('player')}")
        elif event_type == "ACTION_FIZZLED":
            self.log(f"  ✘ {data.get('card')} — {data.get('reason', 'target gone')}")
        elif event_type == "STACK_RESOLUTION_END":
            pass  # no need for a noisy footer
        elif event_type == "GAME_OVER":
            self.log(data.get("message", ""))
        elif event_type == "NARRATIVE":
            self.log(data.get("message", ""))
            
    def show_board(self, state):
        self.clear_screen()
        # Header
        print("\n" + "+" + "-"*76 + "+")
        mode_color = Colors.YELLOW if state.mode == "sudden_death" else Colors.CYAN
        header_text = f" TURN {state.turn_number} | MODE: {state.mode.upper()} "
        padding = (76 - len(header_text)) // 2
        print(f"|{' ' * padding}{Colors.BOLD}{header_text}{Colors.RESET}{' ' * (76 - len(header_text) - padding)}|")
        print("+" + "-"*76 + "+")
        
        dy_color = Colors.CYAN if state.deck else Colors.RED
        print(f" Deck: {dy_color}{len(state.deck)} cards{Colors.RESET} | Graveyard: {len(state.graveyard)} cards")
        print("=" * 78)

        # Build Sequence Strings (Left Column)
        stock_lines = []
        stock_lines.append(f"{Colors.BOLD}[ PLAYER SEQUENCES ]{Colors.RESET}")
        stock_lines.append("")
        
        for p in state.players:
            is_active = hasattr(state, 'active_player_idx') and p == state.players[state.active_player_idx]
            has_priority = hasattr(state, 'priority_player_idx') and p == state.players[state.priority_player_idx] if state.current_phase in [Phase.REACTION_SELECTION] else is_active
            
            player_color = Colors.BLUE if not p.is_bot else Colors.RED
            marker = f"{Colors.YELLOW}==> {Colors.RESET}" if has_priority else "    "
            
            bot_tag = f" (Bot: {p.bot_profile.name.title()})" if p.is_bot else " (Human)"
            # Bold the active player, don't bold the non-active players
            name_format = f"{Colors.BOLD}{p.name}{Colors.RESET}{player_color}" if is_active else f"{p.name}"
            stock_lines.append(f"{marker}{player_color}{name_format}{bot_tag}{Colors.RESET}")
            
            if p.is_bot:
                stock_lines.append(f"    Hand: {Colors.CYAN}{len(p.hand)} cards{Colors.RESET}")

            if p.sequence:
                stock_lines.append("    +----------------------+")
                names = [c.name for c in p.sequence]
                unique_names = list(set(names))
                for name in sorted(unique_names):
                    count = names.count(name)
                    bar = "#" * count + "." * (5 - count)
                    threat = " !" if count >= 4 else ""
                    display_name = (name[:11] + "..") if len(name) > 13 else name
                    stock_lines.append(f"    | {display_name:<13} {Colors.GREEN}{bar}{Colors.RESET}{threat} |")
                stock_lines.append("    +----------------------+")
            else:
                stock_lines.append("    Stock: [Empty]")
            stock_lines.append("")

        # Build Stack Strings (Right Column)
        stack_lines = []
        
        if state.nexus:
            stack_lines.append(f"{Colors.BOLD}[ THE NEXUS (FIELD) ]{Colors.RESET}")
            stack_lines.append("  +-----------------------------------+")
            for card in state.nexus:
                owner_action = next((a for a in state.stack if a.source_card == card), None)
                if owner_action:
                    color = Colors.BLUE if not owner_action.source_player.is_bot else Colors.RED
                    owner_name = owner_action.source_player.name[:10]
                else:
                    color = Colors.GREY
                    owner_name = "Unknown"
                
                line = f"| {color}{owner_name:<10}{Colors.RESET}: {card.name:<21} |"
                stack_lines.append(f"  {line}")
            stack_lines.append("  +-----------------------------------+")
            stack_lines.append("")
            
        stack_lines.append(f"{Colors.BOLD}[ THE STACK ]{Colors.RESET}")
        stack_lines.append("")
        
        if state.stack:
            stack_lines.append(f"  {Colors.YELLOW}[TOP / RESOLVES FIRST]{Colors.RESET}")
            stack_lines.append("  +-----------------------------------+")
            for i, action in enumerate(reversed(state.stack)):
                p_color = Colors.BLUE if not action.source_player.is_bot else Colors.RED
                ability = action.source_card.react_ability.name if action.ability_type == 'react' else action.source_card.sequence_ability.name
                owner = action.source_player.name[:10]
                line = f"| {p_color}{owner:<10}{Colors.RESET}: {ability:<21} |"
                stack_lines.append(f"  {line}")
                
                # Show Targets
                target_text = ""
                if action.target_card:
                    owner = getattr(action.target_card, 'owner', None)
                    t_name = owner.name[:8] if owner else "?"
                    c_name = getattr(action.target_card, 'name', "?")[:12]
                    target_text = f"⟶ {t_name}'s {c_name}"
                elif action.target_player:
                    target_text = f"⟶ {action.target_player.name[:16]}"
                elif action.copied_card_name:
                    target_text = f"⟶ copy: {action.copied_card_name[:14]}"
                
                target_text_s: str = str(target_text)
                if target_text_s:
                    tgt = target_text_s[:30]
                    stack_lines.append(f"  |  {Colors.GREY}{tgt:<32}{Colors.RESET}|")

                if i < len(state.stack) - 1:
                    stack_lines.append("  +-----------------------------------+")
            stack_lines.append("  +-----------------------------------+")
            stack_lines.append(f"  {Colors.YELLOW}[BOTTOM / RESOLVES LAST]{Colors.RESET}")
        else:
            stack_lines.append("  ( The table is empty )")

        # Merge Columns
        max_rows = max(len(stock_lines), len(stack_lines))
        for i in range(max_rows):
            left = stock_lines[i] if i < len(stock_lines) else ""
            right = stack_lines[i] if i < len(stack_lines) else ""
            
            # ANSI escape codes don't count for length
            def clean_len(s):
                import re
                return len(re.sub(r'\033\[[0-9;]*m', '', s))
            
            l_len = clean_len(left)
            padding = " " * (38 - l_len)
            print(f"{left}{padding} {right}")

        # --- Recent Actions Log Box ---
        print("\n" + Colors.HEADER + "+" + "-"*76 + "+" + Colors.RESET)
        
        # Display all events from the current turn (reset in end_turn)
        display_history = state.event_history if hasattr(state, 'event_history') else []
        
        if not display_history:
            print(f"{Colors.HEADER}|{Colors.RESET}  ( No actions yet this turn ) {' ' * 45} {Colors.HEADER}|{Colors.RESET}")
        else:
            for raw_entry in display_history:
                entry = self._fmt(raw_entry)
                visible_text = self.strip_ansi(entry).replace("\n", " ").strip()
                if len(visible_text) > 74:
                    visible_text = visible_text[:71] + "..."
                padding = 74 - len(visible_text)
                print(f"{Colors.HEADER}|{Colors.RESET}  {entry}{' ' * padding} {Colors.HEADER}|{Colors.RESET}")
            
        print(Colors.HEADER + "+" + "-"*76 + "+" + Colors.RESET)
        print("=" * 78 + "\n")
        
        # Persistent Hand View for Human Player
        for p in state.players:
            if not p.is_bot:
                self._render_hand_cards(p, state, "VIEW")
                break

    def _can_afford_ability(self, player, card, ability, state) -> bool:
        """Checks if a player can afford the costs (Entropy/Sever) of an ability."""
        # Entropy: Need at least one other card in hand to discard
        if ability.has_tag("Entropy"):
            if len(player.hand) <= 1:
                return False
        
        # Sever: Need at least one card in sequence to destroy
        if ability.has_tag("Sever"):
            if len(player.sequence) == 0:
                return False
                
        # Special case for Redact Choice: Sever OR Entropy
        choice_tag = ability.get_tag("Choice")
        if choice_tag and choice_tag.params.get("type") == "Choice":
            options = choice_tag.params.get("options", [])
            has_burn = "Sever" in options
            has_pitch = "Entropy" in options
            
            can_burn = len(player.sequence) > 0 if has_burn else False
            can_pitch = len(player.hand) > 1 if has_pitch else False
            
            if has_burn and has_pitch:
                return can_burn or can_pitch
        
        return True

    def _render_hand_cards(self, player, state, mode="STOCK"):
        """Helper to render cards in a row format."""
        if not player.hand:
            print(f"\n{Colors.BOLD}[ YOUR HAND - Empty ]{Colors.RESET}")
            print("-" * 78)
            return

        title = "YOUR HAND" if mode == "VIEW" else f"YOUR HAND - Select a card to {mode}"
        print(f"\n{Colors.BOLD}[ {title} ]{Colors.RESET}")
        print("-" * 78)
        
        chunk_size = 4
        for i in range(0, len(player.hand), chunk_size):
            chunk = player.hand[i:i+chunk_size]
            
            # Line 1: Numbers (Only show if selecting)
            if mode != "VIEW":
                nums = "".join([f"      [{j+i+1}]      " for j in range(len(chunk))])
                print(nums)
            
            # Contextual Logic: Show Stock info if Active Player in Stock Phase, else React info
            is_stock_phase = (state.current_phase == Phase.STOCK_CARD_SELECTION)
            is_active_player = (player == state.players[state.active_player_idx])
            
            # Line 2: Card Names and Affordance
            names = ""
            for c in chunk:
                if is_stock_phase and is_active_player:
                    focused_ability = c.sequence_ability
                    color = Colors.SKY_BLUE
                else:
                    focused_ability = c.react_ability
                    color = Colors.ORANGE
                    
                if mode in ["STOCK", "REACT"]:
                    can_pay = self._can_afford_ability(player, c, focused_ability, state)
                    if not can_pay:
                        color = Colors.RED
                        style = Colors.STRIKETHROUGH
                    else:
                        style = ""
                else:
                    style = ""
                    
                tags = [t.name for t in focused_ability.tags if t.name in ["Entropy", "Sever"]]
                short_tags = []
                if "Entropy" in tags: short_tags.append("P")
                if "Sever" in tags: short_tags.append("B")
                tag_str = f"[{','.join(short_tags)}]" if short_tags else ""
                
                display_str = f"{c.name}{tag_str}"
                names += f" {color}{style}{display_str:^16}{Colors.RESET} "
            print(names)
            
            # Line 3 & 4: Dynamic Description (Grey)
            desc_line_1: str = ""
            desc_line_2: str = ""
            
            for c in chunk:
                if is_stock_phase and is_active_player:
                    desc = c.sequence_ability.get_dynamic_description()
                else:
                    desc = c.react_ability.get_dynamic_description()
                
                desc_s = str(desc)
                words = desc_s.split()
                l1_words: list[str] = []
                l2_words: list[str] = []
                l1_len: int = 0
                l2_len: int = 0
                for w in words:
                    sw: str = str(w)
                    sw_len: int = int(len(sw))
                    if int(l1_len) + sw_len <= 16:
                        l1_words.append(sw)
                        l1_len = int(l1_len) + sw_len + 1
                    elif int(l2_len) == 0 or (int(l2_len) + sw_len <= 16):
                        l2_words.append(sw)
                        l2_len = int(l2_len) + sw_len + 1
                    else:
                        if l2_words and not str(l2_words[-1]).endswith(".."):
                            l2_words[-1] = str(l2_words[-1])[:13] + ".."
                        break
                
                l1 = " ".join(l1_words)
                l2 = " ".join(l2_words)
                desc_line_1 = str(desc_line_1) + str(f" {Colors.GREY}{l1:^16}{Colors.RESET} ")
                desc_line_2 = str(desc_line_2) + str(f" {Colors.GREY}{l2:^16}{Colors.RESET} ")
            
            print(desc_line_1)
            print(desc_line_2)
            print("")
            
        print("-" * 78)

    def show_card_menu(self, player, state, mode="STOCK"):
        """Displays hand as horizontal cards for selection."""
        if not player.hand:
            return -1
            
        self._render_hand_cards(player, state, mode)
        
        while True:
            try:
                choice = input(f"Choose a card (1-{len(player.hand)}, or 'q' for options): ").strip().lower()
                if choice in ['q', 'quit', 'menu']:
                    self.show_options_menu()
                    continue
                idx = int(choice) - 1
                if 0 <= idx < len(player.hand):
                    return idx
                print("Invalid choice.")
            except ValueError:
                print("Enter a number.")

    def show_options_menu(self):
        while True:
            print(f"\n{Colors.BOLD}--- Options Menu ---{Colors.RESET}")
            print("1. Resume Game")
            print("2. Quit to Desktop")
            choice = input("Select an option (1-2): ").strip()
            if choice == '1':
                return
            elif choice == '2':
                raise GameExit("Player quit the game.")
            else:
                print("Invalid choice.")

    def prompt_continue(self, prompt_text: str):
        choice = input(f"\n{prompt_text} (or type 'q' for options): ").strip().lower()
        if choice in ['q', 'quit', 'options', 'menu']:
            self.show_options_menu()

    def prompt_choice(self, prompt_text: str, options: list, player=None) -> int:
        """Helper to get a valid integer choice from a list of options."""
        # Note: If player is a bot, we shouldn't be calling this ConsoleView prompt.
        # But for safety, if we accidentally do, we can fallback to random.
        if player and player.is_bot:
             return random.randint(0, len(options) - 1)
             
        for i, opt in enumerate(options):
            print(f"{i+1}. {opt}")
            
        while True:
            try:
                choice = input(prompt_text + f" (1-{len(options)}, or type 'q' for options): ").strip().lower()
                
                if choice in ['q', 'quit', 'options', 'menu']:
                    self.show_options_menu()
                    # Re-print options after returning from menu
                    for i, opt in enumerate(options):
                        print(f"{i+1}. {opt}")
                    continue
                    
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return idx
                print("Invalid choice.")
            except ValueError:
                print("Please enter a number or 'q'.")
        return -1

    # Drains the state event queue and prints events to console.
    def render_events(self, state):
        """Drains the state event queue and prints events to console."""
        while state.event_queue:
            event = state.event_queue.pop(0)
            etype = event["event"]
            data = event["data"]
            
            if etype == "GAME_START":
                print(f"\n--- Game Started: {data['num_players']} players ---")
                print(f"--- Starting Player: {data['starting_player']} ---")
            elif etype == "CARD_DRAWN":
                # Only log for the player if they are active? 
                # For console simplicity, just log it.
                print(f"{data['player']} drew a card. ({data['cards_left']} left)")
            elif etype == "CARD_STOCKED":
                print(f"\n==> {data['player']} is stocking {data['card']} into their Sequence.")
                print(f"    Activating '{data['ability']}'!")
                print(f"    Effect: {data['description']}")
            elif etype == "REACTION_PASS":
                print(f"{data['player']} passes.")
            # ... other events ...

    def strip_ansi(self, text: str) -> str:
        """Removes ANSI escape codes for accurate length calculation."""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def display_turn_summary(self, state):
        """Renders a clean, boxed section with the turn summary."""
        if not state.turn_history:
            return
            
        print(f"\n{Colors.HEADER}+" + "-"*76 + f"+{Colors.RESET}")
        print(f"{Colors.HEADER}|" + " TURN " + str(state.turn_number) + " RECAP ".center(60) + f"|{Colors.RESET}")
        print(f"{Colors.HEADER}+" + "-"*76 + f"+{Colors.RESET}")
        
        for raw_entry in state.turn_history:
            entry = self._fmt(raw_entry)
            visible_text = self.strip_ansi(entry).replace("\n", " ").strip()
            if len(visible_text) > 74:
                entry = entry[:68] + "..."
                visible_text = self.strip_ansi(entry)
            padding = 74 - len(visible_text)
            if ("⟶" in entry or "✔" in entry) and "\033" not in entry:
                line_content = f"{Colors.SKY_BLUE}{entry}{Colors.RESET}"
            else:
                line_content = entry
            print(f"{Colors.HEADER}|{Colors.RESET}  {line_content}{' ' * padding} {Colors.HEADER}|{Colors.RESET}")
                
        print(f"{Colors.HEADER}+" + "-"*76 + f"+{Colors.RESET}")

