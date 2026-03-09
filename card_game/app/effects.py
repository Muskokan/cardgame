"""
effects.py — Effect resolution logic for Cause & Effect.

Extracted from models.py to cleanly separate data definitions (models.py)
from runtime resolution logic (this module).
"""

import os
import json
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import Ability, Action
    from engine import GameState

# ---------------------------------------------------------------------------
# Cards-data cache (loaded once on first use)
# ---------------------------------------------------------------------------

_CARDS_DATA_CACHE = None


def _get_cards_data() -> dict:
    global _CARDS_DATA_CACHE
    if _CARDS_DATA_CACHE is None:
        json_path = os.path.join(os.path.dirname(__file__), "cards.json")
        with open(json_path, "r") as f:
            _CARDS_DATA_CACHE = json.load(f)
    return _CARDS_DATA_CACHE


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_sequence_target(state: "GameState", action: "Action", target_card):
    """Identifies the owner and card for BOUNCE / STEAL / DESTROY targets."""
    tp = action.target_player
    if target_card and target_card in state.nexus:
        owner_action = next((a for a in state.stack if a.source_card == target_card), None)
        if owner_action:
            tp = owner_action.source_player
        elif target_card.owner:
            tp = target_card.owner
    if not tp and target_card and target_card.owner:
        tp = target_card.owner
    return tp, target_card


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------

def resolve_effects(ability: "Ability", state: "GameState", action: "Action", view, depth: int = 0):
    """Resolves all effects declared on *ability* against the current game state."""
    from models import Ability as _Ability, Action as _Action, TargetRequirement

    cards_data = _get_cards_data()
    abilities_data = cards_data["abilities"]

    # --- RULE 53: FIZZLE PRE-CHECK ---
    is_legal = not ability.target_requirements
    fizzle_reason = "Target no longer valid"

    for req in ability.target_requirements:
        if req == TargetRequirement.NEXUS_CARD:
            if action.target_card and action.target_card in state.nexus:
                is_legal = True
                break
        elif req in [TargetRequirement.OPPONENT_CAUSE, TargetRequirement.OWN_CAUSE, TargetRequirement.ANY_CAUSE]:
            if action.target_card:
                for p in state.players:
                    if action.target_card in p.sequence:
                        is_legal = True
                        break
                if is_legal:
                    break
        elif req == TargetRequirement.GRAVEYARD:
            if action.target_card and (
                action.target_card in state.graveyard or action.target_card in state.nexus
            ):
                is_legal = True
                break
        elif req == TargetRequirement.PLAYER:
            if action.target_player:
                is_legal = True
                break

    if not is_legal and ability.target_requirements:
        state.log_event("ACTION_FIZZLED", {
            "player": action.source_player.name,
            "card": action.source_card.name,
            "reason": fizzle_reason,
        })
        return

    # --- EFFECT RESOLUTION ---
    for effect in ability.effects:
        eff_type = effect.type
        target_type = effect.target
        amount = effect.amount
        destination = effect.destination

        tag = "[SUCCESS]" if depth == 0 else "[ECHO]"

        # Resolve target collections
        target_players = []
        target_cards = []

        t_type_lower = target_type.lower()
        if t_type_lower == "self":
            target_players = [action.source_player]
        elif t_type_lower == "chosen_target":
            if action.target_player:
                target_players = [action.target_player]
        elif t_type_lower == "all_players":
            target_players = state.players

        if t_type_lower == "chosen_target_card" and action.target_card:
            target_cards = [action.target_card]

        # --- Dispatch by effect type ---

        if eff_type == "DRAW_CARDS":
            for p in target_players:
                card_str = "cards" if amount > 1 else "card"
                state.log_event("EFFECT_RESULT", {"message": f"  {tag} {ability.name} activates. {p.name} draws {amount} {card_str}."})
                if t_type_lower != "self":
                    state.log_event("TARGET_INFO", {"source": ability.name, "target": "Player", "target_type": "PLAYER"})
                for _ in range(amount):
                    state.draw_card(p)

        elif eff_type == "FORCE_DISCARD":
            state.log_event("EFFECT_RESULT", {"message": f"  {tag} {ability.name} activates. Forcing discard."})
            for p in target_players:
                if t_type_lower != "self":
                    state.log_event("TARGET_INFO", {"source": ability.name, "target": "Player", "target_type": "PLAYER"})
                if p.hand:
                    if not p.is_bot and view is None:
                        state.pending_action = {
                            "type": "RESOLUTION_ENTROPY",
                            "player_idx": state.players.index(p),
                            "card_name": action.source_card.name
                        }
                        yield "WAIT_FOR_INPUT"
                        pitch_id = state.pending_input_result.get("card_id")
                        picked = next((c for c in p.hand if c.id == pitch_id), p.hand[0])
                        pitch_idx = p.hand.index(picked)
                    elif not p.is_bot and view is not None:
                        pitch_idx = view.prompt_choice(f"{p.name}, choose a card from your hand to pitch:", [c.name for c in p.hand])
                    else:
                        # Bot: auto-pick
                        pitch_idx = random.randint(0, len(p.hand) - 1)
                    pitched = p.hand.pop(pitch_idx)
                    pitched.owner = None
                    state.graveyard.append(pitched)
                    state.log_event("EFFECT_RESULT", {"message": f"  -> {p.name} pitched {pitched.name}."})

        elif eff_type == "SNATCH_DISCARD":
            state.log_event("EFFECT_RESULT", {"message": f"  {tag} {ability.name} activates. Forcing pitches!"})
            pitched_card_ids = []
            opponents = [p for p in state.players if p != action.source_player]
            for p in opponents:
                if p.hand:
                    if not p.is_bot and view is None:
                        state.pending_action = {
                            "type": "RESOLUTION_ENTROPY",
                            "player_idx": state.players.index(p),
                            "card_name": action.source_card.name,
                            "is_snatch": True
                        }
                        yield "WAIT_FOR_INPUT"
                        pitch_id = state.pending_input_result.get("card_id")
                        picked = next((c for c in p.hand if c.id == pitch_id), p.hand[0])
                        pitch_idx = p.hand.index(picked)
                    elif not p.is_bot and view is not None:
                        pitch_idx = view.prompt_choice(f"{p.name}, choose a card to pitch to Snatch:", [c.name for c in p.hand])
                    else:
                        pitch_idx = random.randint(0, len(p.hand) - 1)
                    pitched = p.hand.pop(pitch_idx)
                    pitched.owner = None
                    state.graveyard.append(pitched)
                    pitched_card_ids.append(pitched.id)
                    state.log_event("EFFECT_RESULT", {"message": f"  -> {p.name} pitched {pitched.name}."})

            if pitched_card_ids:
                caster = action.source_player
                if not caster.is_bot:
                    if view is None:
                        # Web mode: pause for human to pick which pitched card to snatch
                        state.pending_action = {
                            "type": "SNATCH_PICK",
                            "source_player_idx": state.players.index(caster),
                            "card_name": action.source_card.name,
                            "pitched_card_ids": pitched_card_ids,
                        }
                        yield "WAIT_FOR_INPUT"
                        picked_id = state.pending_input_result.get("card_id")
                    else:
                        pick_names = [c.name for c in state.graveyard if c.id in pitched_card_ids]
                        pick_idx_in_pool = view.prompt_choice(
                            f"{caster.name}, pick a card to snatch into your hand:",
                            pick_names,
                        )
                        picked_id = pitched_card_ids[pick_idx_in_pool]
                else:
                    try:
                        import ai
                        pool = [c for c in state.graveyard if c.id in pitched_card_ids]
                        pick_idx_in_pool = ai.bot_choose_void_pick(caster, pool)
                        picked_id = pitched_card_ids[pick_idx_in_pool]
                    except Exception:
                        picked_id = pitched_card_ids[0]

                picked = next((c for c in state.graveyard if c.id == picked_id), None)
                if picked:
                    state.graveyard.remove(picked)
                    picked.owner = caster
                    caster.hand.append(picked)
                    state.log_event("EFFECT_RESULT", {"message": f"  [SUCCESS] {ability.name} activates. {caster.name} snatched {picked.name}!"})
            else:
                state.log_event("EFFECT_RESULT", {"message": "  No cards were pitched; Snatch fizzles."})


        elif eff_type == "COUNTER_SPELL":
            if target_cards and target_cards[0] in state.nexus:
                targeted_card = target_cards[0]
                targeted_action = next((a for a in state.stack if a.source_card == targeted_card), None)
                src_name = targeted_action.source_player.name if targeted_action and targeted_action.source_player else "Unknown"
                state.log_event("CARD_COUNTERED", {
                    "player": action.source_player.name,
                    "target_player": src_name,
                    "card": targeted_card.name,
                    "message": f"  {tag} {ability.name} activates. Countered {src_name}'s {targeted_card.name}!",
                })
                state.log_event("TARGET_INFO", {"source": ability.name, "target": targeted_card.react_ability.name, "target_type": "NEXUS"})
                state.nexus.remove(targeted_card)
                targeted_card.owner = None
                state.graveyard.append(targeted_card)

        elif eff_type == "BOUNCE_CARD":
            if target_cards:
                tp, c = _resolve_sequence_target(state, action, target_cards[0])
                if tp and c in tp.sequence:
                    state.log_event("EFFECT_RESULT", {"message": f"  {tag} {ability.name} activates. Returning {c.name} to {tp.name}'s hand."})
                    state.log_event("TARGET_INFO", {"source": ability.name, "target": c.sequence_ability.name, "target_type": "CAUSE"})
                    tp.sequence.remove(c)
                    tp.hand.append(c)

        elif eff_type == "COPY_ABILITY":
            if not getattr(action, "copied_card_name", None):
                state.log_event("EFFECT_RESULT", {"message": f"  [FIZZLE] {ability.name} lacked a valid card to copy."})
                continue
            state.log_event("EFFECT_RESULT", {"message": f"  {tag} {ability.name} activates. Copying {action.copied_card_name}."})
            parts = action.copied_card_name.split("/")
            cause_name = parts[1] if len(parts) > 1 else action.copied_card_name
            state.log_event("TARGET_INFO", {"source": ability.name, "target": cause_name, "target_type": "CAUSE"})
            cause_data = abilities_data.get(cause_name)
            if cause_data:
                copied_effects = cause_data.get("effects", [])
                if any(e.get("type") == "COPY_ABILITY" for e in copied_effects):
                    state.log_event("EFFECT_RESULT", {"message": f"  [FIZZLE] {ability.name} cannot copy {cause_name} — copying a copy ability would create an infinite loop."})
                    continue
                copied_ab = _Ability(
                    cause_name,
                    cause_data.get("description", "No description."),
                    cause_data.get("tags", []),
                    cause_data.get("target_requirements", []),
                    cause_data.get("console_description", ""),
                    copied_effects,
                )
                state.log_event("EFFECT_RESULT", {"message": f"  [ECHO] -> {cause_name} activates."})
                copied_ab.execute(state, action, view, depth + 1)

        elif eff_type == "MOVE_CARD":
            card_found = False
            source_zone = ""
            if target_cards:
                c = target_cards[0]
                if c in state.graveyard:
                    state.graveyard.remove(c)
                    card_found = True
                    source_zone = "Graveyard"
                elif c in state.nexus:
                    state.nexus.remove(c)
                    card_found = True
                    source_zone = "Nexus"
            if card_found:
                c = target_cards[0]
                dest_label = "top of deck" if destination == "deck_top" else f"{action.source_player.name}'s hand"
                state.log_event("EFFECT_RESULT", {"message": f"  [SUCCESS] {ability.name} activates. {c.name} moved from {source_zone} ⟶ {dest_label}."})
                state.log_event("TARGET_INFO", {"source": ability.name, "target": c.sequence_ability.name, "target_type": "GY/NEXUS"})
                if destination == "deck_top":
                    c.owner = None
                    state.deck.insert(0, c)
                elif destination == "hand":
                    c.owner = action.source_player
                    action.source_player.hand.append(c)

        elif eff_type == "STEAL_CARD":
            tp, c = _resolve_sequence_target(state, action, target_cards[0] if target_cards else None)
            if not tp:
                state.log_event("EFFECT_RESULT", {"message": f"  [FIZZLE] {ability.name}: no valid target found."})
                continue
            if c in state.nexus:
                tp_action = next((a for a in state.stack if a.source_card == c), None)
                state.nexus.remove(c)
                state.stack = [a for a in state.stack if a.source_card != c]
                c.owner = action.source_player
                action.source_player.sequence.append(c)
                state.log_event("EFFECT_RESULT", {"message": f"  [SUCCESS] {ability.name} activates. Stole {c.name} from {tp.name}'s Nexus!"})
                state.log_event("EFFECT_RESULT", {"message": f"  [TRIGGER] The stolen {c.name} now activates for {action.source_player.name}!"})
                from models import Action as _ActCls
                stolen_action = _ActCls(action.source_player, c, "sequence", triggered=True)
                if tp_action:
                    stolen_action.target_card = tp_action.target_card
                    stolen_action.target_player = tp_action.target_player
                    stolen_action.copied_card_name = tp_action.copied_card_name
                state.stack.append(stolen_action)
            elif tp.sequence:
                target_to_steal = c if c in tp.sequence else random.choice(tp.sequence)
                state.log_event("EFFECT_RESULT", {"message": f"  [SUCCESS] {ability.name} activates. Stealing {target_to_steal.name} from {tp.name}."})
                tp.sequence.remove(target_to_steal)
                target_to_steal.owner = action.source_player
                action.source_player.sequence.append(target_to_steal)
                state.log_event("EFFECT_RESULT", {"message": f"  [TRIGGER] The stolen {target_to_steal.name} now activates for {action.source_player.name}!"})
                from models import Action as _ActCls
                state.stack.append(_ActCls(action.source_player, target_to_steal, "sequence", triggered=True))
            else:
                state.log_event("EFFECT_RESULT", {"message": f"  [FIZZLE] {ability.name}: {tp.name} has no cards to steal."})

        elif eff_type == "DESTROY_CARD":
            tp, c = _resolve_sequence_target(state, action, target_cards[0] if target_cards else None)
            if tp and tp.sequence:
                target_to_destroy = c if c in tp.sequence else random.choice(tp.sequence)
                state.log_event("EFFECT_RESULT", {"message": f"  [SUCCESS] {ability.name} activates. Destroyed {target_to_destroy.name} in {tp.name}'s sequence."})
                tp.sequence.remove(target_to_destroy)
                target_to_destroy.owner = None
                state.graveyard.append(target_to_destroy)
                state.log_event("CARD_DESTROYED", {"player": tp.name, "card": target_to_destroy.name})
