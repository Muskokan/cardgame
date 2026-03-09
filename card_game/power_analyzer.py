import json
import os
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# CARD KNOWLEDGE BASE  (all written by human designer, not derived from sim)
# ─────────────────────────────────────────────────────────────────────────────

CARD_PAIRS = {
    "Cease & Desist":    "Earnings",
    "Diversify":  "Call",
    "Liquidate":  "Invest",
    "Delist": "Recoup",
    "Undercut":  "Crash",
}

CARD_KNOWLEDGE = {
    "Earnings": {
        "role": "Stock | Card Advantage",
        "mechanic": "Draw 1 card when stocked.",
        "why_wins": [
            "Replaces itself the moment it lands, creating a permanent hand-size advantage.",
            "Every resolved Earnings puts its controller one card ahead of all opponents, compounding over time.",
            "Fuels other stock abilities by keeping hand options open."
        ],
        "why_loses": [
            "Provides no board interaction — opponents can freely build stockpiles.",
            "A single Crash or Liquidate on a key card can outpace all the hand advantage Earnings generated.",
            "Against aggressive opponents, raw cards don't matter if the stockpile game is already lost."
        ],
        "advantage": "Each resolution is net +1 card. In a 10-card opening arc, this becomes a decisive advantage by turn 5.",
        "synergy": "Pairs naturally with Invest (copies Earnings for double draw) and Cease & Desist (uses extra cards for pitch cost).",
        "counter": "Undercut (steals accumulated stockpile progress), Call (strips drawn cards from hand).",
    },
    "Call": {
        "role": "Stock | Disruption",
        "mechanic": "Target opponent pitches 1 card from their hand.",
        "why_wins": [
            "Strips opponents of reactive tools — a Cease & Desist or Liquidate discarded is a counterspell permanently removed.",
            "Tempo positive: you stock a card AND cost an opponent a card simultaneously.",
            "Near-universal dominance: 93%+ win rate confirms it reliably turns a 4-player board in your favor."
        ],
        "why_loses": [
            "Entirely reactive targets — if opponents have empty hands, Call fizzles.",
            "Does nothing against the board state; a player with 3 Crashes on their stockpile is still winning.",
            "No card advantage for the caster — it trades card parity."
        ],
        "advantage": "Net card swing: +1 for you (stockpile placement), -1 for target (discard). Net 2-card differential per resolution.",
        "synergy": "Best when followed by Crash (now they can't bounce it back with Liquidate). Devastating with Invest (double strip).",
        "counter": "Diversify (react to force even more discards), Cease & Desist (counter the Call before it resolves).",
    },
    "Crash": {
        "role": "Stock | Board Removal",
        "mechanic": "Destroy target opponent's Stockpile card.",
        "why_wins": [
            "Resets win-condition progress directly — destroying a 3rd or 4th copy card is game-swinging.",
            "Doubles as a catch-up mechanism for losing players.",
            "Creates a chain-reaction: the destroyed card often goes to the Graveyard where Recoup players recycle it."
        ],
        "why_loses": [
            "Players with 4+ stockpile cards can sacrifice one and still be fine.",
            "Undercut is strictly superior in most situations (you also gain the card).",
            "No card advantage; you stock a card but gain nothing in hand."
        ],
        "advantage": "Each resolution is a -1 from an opponent's stockpile. Mid-to-late game this is close to a win-condition reset.",
        "synergy": "Pairs with Cease & Desist (counter the reaction) and Recoup (grab it back from Graveyard for repeated use).",
        "counter": "Liquidate (bounce before Crash resolves), Delist (recycle the destroyed card to deck).",
    },
    "Recoup": {
        "role": "Stock | Recursion",
        "mechanic": "Put target Graveyard card into your hand.",
        "why_wins": [
            "Converts the shared Graveyard into a private hand-refill engine.",
            "Recovering a Crash or Call from the graveyard is often a +2 effective card swing.",
            "Enables consistent 'loop' strategies: stock Recoup → grab Crash → stock Crash → Crash goes to GY → Recoup again."
        ],
        "why_loses": [
            "Requires a loaded Graveyard — in early turns, this may not be available.",
            "Competes with all other Recoup players for the same Graveyard targets.",
            "Does not contribute directly to win conditions — you still need to stock the recovered card."
        ],
        "advantage": "Recycles any card from a shared pool. In a 10k sim, Recoup players most frequently recaptured Crash (26%) and Earnings (25%) — massively distorting the effective card pool in their favor.",
        "synergy": "Dominant with Crash (creates a repeated removal loop). Excellent with Earnings (low-cost refills).",
        "counter": "Delist (top-decks the target card before Recoup can grab it), Call (strips the recovered card from hand).",
    },
    "Invest": {
        "role": "Stock | Copy / Multiplier",
        "mechanic": "Copy a target Stockpile card from any player's Stockpile.",
        "why_wins": [
            "Can copy the highest-value ability in play — effectively a 'play the best card on the board' button.",
            "When copying Call or Crash, it generates massive tempo swings without spending a targeted card.",
            "Costs nothing extra beyond the stock phase — no additional card cost."
        ],
        "why_loses": [
            "Inherently reactive — its power ceiling is gated by what others have stockpiled.",
            "Cannot target itself (engine guard prevents infinite loops).",
            "Countered easily by Cease & Desist, which stops the copy before it resolves."
        ],
        "advantage": "Effectively grants a free copy of any ability in play. Against a board with Crash and Call, this is often the most powerful single play available.",
        "synergy": "Best in a loaded board state (mid-to-late game). Combines well with Cease & Desist (protect the copy).",
        "counter": "Cease & Desist (direct counter), Liquidate (bounce the source card before Invest targets it).",
    },
    "Cease & Desist": {
        "role": "React | Counter",
        "mechanic": "[Burn] Counter target Stack placement or Reaction, then draw 1 card.",
        "why_wins": [
            "Stops any ability on the Stack — the only universal counter in the game.",
            "Drawing a card after countering means it replaces what was pitched.",
            "Defensive baseline: prevents opponents from winning through critical stack interactions."
        ],
        "why_loses": [
            "Costs 2 cards (discard Cease & Desist card + pitch another), making it very expensive.",
            "Does not progress your own win condition — purely reactive.",
            "Low raw win rate (19.5%) confirms that countering others doesn't by itself win games."
        ],
        "advantage": "Net neutral in cards (discard 2, draw 1 back = -1 net). Value comes from denying an opponent's tempo play, which is situationally worth much more.",
        "synergy": "Best paired with Earnings (generates extra cards to pitch) and Undercut (protect a steal from being countered).",
        "counter": "Multiple simultaneous reactions (you only have one Cease & Desist), Undercut before the reaction phase.",
    },
    "Diversify": {
        "role": "React | Void Siphon",
        "mechanic": "Each opponent pitches 1 card. You choose 1 to keep; the rest go to the Graveyard.",
        "why_wins": [
            "In a 3-player game, forces 2 discards and nets you 1 card — a net 3-card swing in your favor.",
            "Strips opponents of reactive tools (Cease & Desist, Liquidate) across the whole table simultaneously.",
            "The card you keep is the best card your opponents pitched — always a high-quality return."
        ],
        "why_loses": [
            "Only 1 card kept vs multiple pitched — opponents lose more collectively but you gain only 1.",
            "In 1v1, it's pitch 1, keep 1 — similar to a forced trade with extra steps.",
            "Requires opponents to have cards in hand; useless against empty-handed players."
        ],
        "advantage": "In 4-player: force 3 opponent pitches, keep 1 of their best. Net: you +1 (selected card), each opponent -1. Total swing: +4 card equivalents vs remaining opponents.",
        "synergy": "Devastating with Call (stock Call → Diversify reaction → opponents lose 2 cards each in one turn).",
        "counter": "Cease & Desist (counter the Diversify entirely), minimal hand sizes (empty hands fizzle it for those players).",
    },
    "Liquidate": {
        "role": "React | Bounce",
        "mechanic": "Recoup target Stockpile card to its owner's hand.",
        "why_wins": [
            "Can reset someone's win condition at a critical moment — bouncing a 4th-copy card delays a win by several turns.",
            "No pitch or burn cost means it's free to use beyond the inherent discard.",
            "Recoups the card to hand rather than destroying it — can disrupt the target's plans without giving them permanent card disadvantage."
        ],
        "why_loses": [
            "Only bounces, not destroys — the target simply re-stocks it next turn.",
            "The 11.8% win rate reveals that disruption alone doesn't win games.",
            "The AI targets Call 44.3% of the time — indicating the AI itself recognizes Call as the largest threat, confirming Call's dominance."
        ],
        "advantage": "Net neutral in cards. Gains value through tempo disruption rather than raw card advantage.",
        "synergy": "Best with Cease & Desist (protect Liquidate on the stack), and in response to a Undercut (bounce the target before it can be stolen).",
        "counter": "Cease & Desist (counter the Liquidate), rapid re-stocking (if the target re-stocks immediately, you wasted a card).",
    },
    "Delist": {
        "role": "React | Graveyard/Pot Control",
        "mechanic": "Put target Graveyard card or active Pot card to the top of the deck.",
        "why_wins": [
            "Pseudo-counter: top-decking a Pot card removes that card's ability from the Stack without technically 'countering' it.",
            "Denies Recoup players their graveyard targets by cycling cards back into the deck.",
            "Can top-deck your own card to set up a guaranteed draw next turn."
        ],
        "why_loses": [
            "0 direct resolutions in the sim — the card never actively fires in the bot sim, suggesting bots don't prioritize Delist well.",
            "Recoups cards to a shared deck rather than removing them permanently — opponents benefit from the same draws.",
            "Very narrow impact zone; only meaningful when a specific Graveyard target needs to be denied."
        ],
        "advantage": "Top-decking from the Graveyard denies Recoup players a target. Top-decking from the Pot is a soft counter without Pitch cost.",
        "synergy": "Pairs with aggressive decks that want to control which cards cycle back. Good against Recoup-heavy boards.",
        "counter": "Players with large hands (can still Recoup other GY cards), boards where the Graveyard is sparsely populated.",
    },
    "Undercut": {
        "role": "React | Steal",
        "mechanic": "[Pitch] Steal target opponent's Stockpile or Pot card. Its Stockpile ability triggers for you.",
        "why_wins": [
            "Simultaneously removes 1 card from an opponent's board AND adds it (plus its trigger) directly to yours.",
            "A 2-card effective swing: -1 from opponent, +1 (plus trigger) for you.",
            "Can steal from the Pot (just-played card), intercepting a powerful ability before it resolves."
        ],
        "why_loses": [
            "Requires [Burn] — you destroy a card from your own stockpile to activate, making it costly.",
            "11.5% win rate is the lowest among all cards — suggests the Burn cost is too high in current meta.",
            "Burning your own progress to steal theirs often results in a net-neutral or worse position."
        ],
        "advantage": "Each steal is a 2-card swing in effective board presence. However, the Burn cost neutralizes part of this gain — net swing is closer to +1.",
        "synergy": "Best paired with Cease & Desist (counter a response to your Undercut) and used when you're already ahead on Stockpile.",
        "counter": "Cease & Desist (counter the Undercut before it resolves), Liquidate (bounce the target before Undercut can steal it).",
    },
}

# Balance scores on -5 to +5 scale (0 = perfectly balanced)
BALANCE_SCORES = {
    "Call":   +4,
    "Recoup":  +3,
    "Earnings":   +2,
    "Invest":  +2,
    "Crash":   +1,
    "Diversify":   0,
    "Delist": -1,
    "Cease & Desist":    -1,
    "Liquidate":  -2,
    "Undercut":  -3,
}

BALANCE_SUGGESTIONS = {
    "Call":   ["Consider adding a hand-reveal requirement back in to give the target useful information.", "Alternatively, restrict targeting to opponents with 3+ stockpile cards to reduce early-game dominance."],
    "Recoup":  ["Limit grabs to cards with stockpile ability only (no react recycles).", "Consider adding a discard cost (Pitch) to prevent the free recursion loop."],
    "Earnings":   ["Consider capping the draw at 1 and making it conditional (e.g., 'if you have fewer cards than all opponents').", "Alternatively, limit to Sudden Death: the extra hand size matters less there."],
    "Invest":  ["Explore a targeting restriction: can only copy cards owned by opponents (not your own stockpile).", "Consider adding a Pitch cost given it copies the most powerful ability in play for free."],
    "Crash":   ["Consider making it a react ability with a Burn cost, which would be more interactive.", "Currently well-positioned — monitor in future runs before adjusting."],
    "Diversify":  ["Currently balanced. If Diversify win-rate climbs past 40%, consider restricting to 1 opponent in 1v1.", "The void-siphon design creates good multiplayer tension — preserve this."],
    "Delist": ["Add a bonus draw if the card top-decked came from the Pot (rewards skill/timing).", "The AI is not using Delist effectively — consider a targeting hint for the bot layer."],
    "Cease & Desist":    ["The Pitch cost makes Cease & Desist expensive relative to its output. Consider reducing to no Burn cost.", "Alternatively, allow Cease & Desist to target any ability (including Diversify reactions) — currently unclear if it does."],
    "Liquidate":  ["Bounce is inherently lower value than Destroy. Consider adding 'You draw 1 card' as a bonus on resolution.", "Alternatively, let Liquidate act as a soft counter: bounce target card to the bottom of the deck instead of hand."],
    "Undercut":  ["The Pitch cost used to be Burn, now it's Pitch. Consider replacing Burn with Pitch for a more accessible steal.", "Alternatively, remove the Burn cost entirely but restrict targeting to Pot cards only (steal just-played cards)."],
}


def generate_analysis():
    if not os.path.exists("sim_data.json"):
        print("Error: sim_data.json not found. Run simulation first.")
        return

    with open("sim_data.json", "r") as f:
        data = json.load(f)

    resolutions     = data.get("ability_resolutions", {})
    win_presence    = data.get("ability_win_presence", {})
    attempts        = data.get("ability_counter_attempts", {})
    total_games     = data.get("games", 10000)
    ai_wins         = data.get("wins_by_playstyle", {})
    win_reasons     = data.get("win_reasons", {})
    targeting_data  = data.get("targeting_data", {})

    abilities = sorted(set(list(resolutions.keys()) + list(win_presence.keys()) + list(attempts.keys())))

    # ── Build per-ability stats ──────────────────────────────────────────────
    stats = {}
    total_resolutions = sum(resolutions.values()) or 1

    for ab in abilities:
        res   = resolutions.get(ab, 0)
        wins  = win_presence.get(ab, 0)
        att   = attempts.get(ab, 0)
        wr    = (wins / total_games * 100) if total_games > 0 else 0
        eff   = (res / att * 100) if att > 0 else None
        share = (res / total_resolutions * 100)

        stats[ab] = {
            "resolutions": res,
            "win_presence": wins,
            "win_rate": wr,
            "attempts": att,
            "efficiency": eff,
            "resolve_share": share,
        }

    # Ranking: primary = win_rate, secondary = resolve share
    ranked = sorted(abilities, key=lambda a: (stats[a]["win_rate"], stats[a]["resolve_share"]), reverse=True)

    # ── Rolling History Logic ────────────────────────────────────────────────
    history_path = "power_history.json"
    history = []
    if os.path.exists(history_path):
        try:
            with open(history_path, "r") as f:
                history = json.load(f)
        except:
            history = []

    current_entry = {
        "timestamp": datetime.now().strftime("%m/%d %H:%M"),
        "stats": {ab: stats[ab]["win_rate"] for ab in abilities}
    }
    history.append(current_entry)
    if len(history) > 5:
        history = history[-5:]
    with open(history_path, "w") as f:
        json.dump(history, f, indent=4)

    # ── Helpers ──────────────────────────────────────────────────────────────
    W = 80

    def rule(char="─", label=""):
        if label:
            pad = W - len(label) - 2
            return f"{'─' * 2} {label} {'─' * pad}\n"
        return char * W + "\n"

    def tier_label(wr):
        if wr >= 70: return "S"
        if wr >= 50: return "A"
        if wr >= 30: return "B"
        return "C"

    def balance_bar(score):
        # -5 ... 0 ... +5 represented as a 22-char bar
        bar = ["─"] * 22
        center = 11
        pos = center + score * 2
        pos = max(0, min(21, pos))
        bar[center] = "│"
        bar[pos] = "◆" if score != 0 else "◆"
        return "[" + "".join(bar) + "]"

    # ── Write Report ─────────────────────────────────────────────────────────
    log_path = "Card Power Analysis.txt"
    with open(log_path, "w", encoding="utf-8") as f:

        def w(s=""):
            f.write(s + "\n")

        w("╔" + "═" * (W - 2) + "╗")
        w(f"║ {'WINDFALL — CARD POWER ANALYSIS':^{W-4}} ║")
        w(f"║ {'Generated: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^{W-4}} ║")
        w(f"║ {'Data Source: ' + f'{total_games:,} Simulated Games':^{W-4}} ║")
        w("╚" + "═" * (W - 2) + "╝")
        w()
        w(f"  Win Conditions — {', '.join([f'{k}: {v:,} ({v/total_games*100:.1f}%)' for k, v in win_reasons.items()])}")
        w()

        # ── Table 1: Rankings ────────────────────────────────────────────────
        w(rule(label="CARD POWER RANKINGS"))
        w(f"  {'CARD':<14} {'TIER':<6} {'WIN RATE':<12} {'RESOLVES':<12} {'RESOLVE SHARE'}")
        w("  " + "─" * 60)
        for ab in ranked:
            s = stats[ab]
            tier = tier_label(s["win_rate"])
            share_bar = "█" * int(s["resolve_share"] / 2) + "░" * (10 - int(s["resolve_share"] / 2))
            share_bar = share_bar[:10]
            w(f"  {ab:<14} {tier:<6} {s['win_rate']:>7.1f}%    {s['resolutions']:>10,}    {share_bar} {s['resolve_share']:.1f}%")
        w()
        w("  TABLE NOTES")
        w("  ─" * 39)
        w("  Tier S (≥70% win rate): These cards appear in the winning player's stockpile in 70%+ of games.")
        w("  Tier A (50-69%): Strong contributors that are frequently part of winning strategies.")
        w("  Tier B (30-49%): Situational or reactive cards that support but rarely carry a win alone.")
        w("  Tier C (<30%): Either undertuned, highly reactive, or penalized by their own costs.")
        w("  Resolve Share shows what percentage of all ability resolutions belong to this card.")
        w("  A high Resolve Share with a low Win Rate (e.g. Cease & Desist) indicates effective defense without offense.")
        w()

        # ── Table 2: Power History ───────────────────────────────────────────
        w(rule(label="POWER TREND HISTORY  (Last 5 Runs — Win Rate %)"))
        if history and len(history) > 1:
            ts_cols = " | ".join([f"{h['timestamp']:^12}" for h in history])
            header = f"  {'CARD':<14} | {ts_cols}"
            w(header)
            w("  " + "─" * (len(header) - 2))
            for ab in sorted(abilities):
                rates = []
                prev = None
                for h in history:
                    rate = h["stats"].get(ab, 0)
                    arrow = ""
                    if prev is not None:
                        diff = rate - prev
                        arrow = " ▲" if diff > 1 else " ▼" if diff < -1 else "  "
                    else:
                        arrow = "  "
                    rates.append(f"{rate:>9.1f}%{arrow}")
                    prev = rate
                w(f"  {ab:<14} | {' | '.join(rates)}")
        else:
            w("  (Need 2+ runs to show trends.)")
        w()
        w("  TABLE NOTES")
        w("  ─" * 39)
        w("  ▲ indicates the card's win rate increased by more than 1% vs the prior run.")
        w("  ▼ indicates the card's win rate decreased by more than 1% vs the prior run.")
        w("  Stable trends suggest the card is consistently positioned across game states.")
        w("  Volatile trends may indicate the card's value is extremely context-dependent.")
        w()

        # ── Table 3: Targeting Meta ──────────────────────────────────────────
        w(rule(label="TARGETING META"))
        w(f"  {'SOURCE':<14} {'#1 TARGET':<18} {'COUNT':<10} {'%':<8} {'FULL BREAKDOWN'}")
        w("  " + "─" * 72)
        sorted_sources = sorted(targeting_data.keys(), key=lambda k: sum(targeting_data[k].values()), reverse=True)
        for src in sorted_sources:
            targets = targeting_data[src]
            if not targets: continue
            total_src = sum(targets.values())
            top = sorted(targets.items(), key=lambda x: x[1], reverse=True)
            top_name, top_count = top[0]
            top_pct = top_count / total_src * 100
            others = ", ".join([f"{n}: {c/total_src*100:.0f}%" for n, c in top[1:3]])
            w(f"  {src:<14} {top_name:<18} {top_count:>8,}    {top_pct:>5.1f}%   also: {others}")
        w()
        w("  TABLE NOTES")
        w("  ─" * 39)
        w("  Shows which target each ability most frequently resolves against.")
        w("  A heavily skewed target (90%+) suggests the AI has a dominant optimal play.")
        w("  Diverse targeting distributions indicate the card is context-sensitive or situational.")
        w("  'Call → Player (100%)' means Call always hits a player — expected, since its target IS a player.")
        w()

        # ── Table 4: AI Playstyle ────────────────────────────────────────────
        w(rule(label="AI PLAYSTYLE PERFORMANCE"))
        if ai_wins:
            sorted_ai = sorted(ai_wins.items(), key=lambda x: x[1], reverse=True)
            best_wins = sorted_ai[0][1]
            w(f"  {'PLAYSTYLE':<16} {'WINS':<10} {'WIN RATE':<12} {'VS FIELD'}")
            w("  " + "─" * 52)
            for style, wins in sorted_ai:
                rate = wins / total_games * 100
                rel = wins / best_wins
                bar = "█" * int(rel * 10)
                w(f"  {style:<16} {wins:>8,}    {rate:>7.1f}%    {bar}")
        w()
        w("  TABLE NOTES")
        w("  ─" * 39)
        w("  Win Rate is measured per-game (a playstyle 'wins' if at least one bot of that type wins).")
        w("  In a 4-bot game with all different playstyles, each should win ~25% if balanced.")
        w("  A dominant playstyle (Combo at 36.6%) indicates those bot priorities align with the most powerful cards.")
        w("  A weak playstyle (Aggressive at 13.2%) may benefit from tuning its priority weights in ai.py.")
        w()

        # ── Per-Card Deep Reports ────────────────────────────────────────────
        w("╔" + "═" * (W - 2) + "╗")
        w(f"║ {'INDIVIDUAL CARD REPORTS':^{W-4}} ║")
        w("╚" + "═" * (W - 2) + "╝")
        w()

        all_win_rates = [stats[ab]["win_rate"] for ab in abilities]
        avg_win_rate = sum(all_win_rates) / len(all_win_rates)

        for ab in ranked:
            s = stats[ab]
            wr = s["win_rate"]
            bal = BALANCE_SCORES.get(ab, 0)
            kb  = CARD_KNOWLEDGE.get(ab, {})
            pair = CARD_PAIRS.get(ab, None)
            pair_for = {v: k for k, v in CARD_PAIRS.items()}.get(ab, None)
            card_pair_name = pair or pair_for or "?"

            tier = tier_label(wr)
            delta = wr - avg_win_rate
            delta_str = f"+{delta:.1f}%" if delta >= 0 else f"{delta:.1f}%"

            bal_label = (
                "SIGNIFICANTLY OVERTUNED" if bal >= 4 else
                "OVERTUNED"               if bal >= 2 else
                "SLIGHTLY STRONG"         if bal == 1 else
                "BALANCED"                if bal == 0 else
                "SLIGHTLY WEAK"           if bal == -1 else
                "UNDERTUNED"              if bal >= -3 else
                "SIGNIFICANTLY UNDERTUNED"
            )

            w("┌" + "─" * (W - 2) + "┐")
            w(f"│ {ab.upper():^{W-4}} │")
            w("├" + "─" * (W - 2) + "┤")
            w(f"│  Role: {kb.get('role', '?'):<{W-12}}      │")
            w(f"│  Card: {card_pair_name}/{ab:<{W-12}}     │")
            w(f"│  Mechanic: {kb.get('mechanic', '?'):<{W-14}}   │")
            w("└" + "─" * (W - 2) + "┘")
            w()

            # ── Balance Score ────────────────────────────────────────────────
            w(f"  BALANCE SCORE   {balance_bar(bal)}   {bal:+d} / ±5   [{bal_label}]")
            w(f"  Win Rate: {wr:.1f}%  (avg: {avg_win_rate:.1f}%  |  delta: {delta_str})   Tier: {tier}")
            eff_str = f"{s['efficiency']:.1f}%" if s['efficiency'] is not None else "N/A"
            w(f"  Resolves: {s['resolutions']:,}  |  Attempts: {s['attempts']:,}  |  Efficiency: {eff_str}  |  Resolve Share: {s['resolve_share']:.1f}%")
            w()

            # ── Why It Wins ──────────────────────────────────────────────────
            w(f"  WHY {ab.upper()} WINS")
            w("  " + "─" * 40)
            for point in kb.get("why_wins", []):
                w(f"  ✔ {point}")
            w()

            # ── Why It Loses ─────────────────────────────────────────────────
            w(f"  WHY {ab.upper()} LOSES")
            w("  " + "─" * 40)
            for point in kb.get("why_loses", []):
                w(f"  ✘ {point}")
            w()

            # ── Card & Win Advantage ─────────────────────────────────────────
            w(f"  CARD & WIN ADVANTAGE")
            w("  " + "─" * 40)
            adv = kb.get("advantage", "No data.")
            for line in adv.split("."):
                line = line.strip()
                if line:
                    w(f"  ▸ {line}.")
            w()

            # ── Synergy & Counter ────────────────────────────────────────────
            w(f"  SYNERGIES & COUNTERS")
            w("  " + "─" * 40)
            w(f"  Synergy: {kb.get('synergy', '—')}")
            w(f"  Counter: {kb.get('counter', '—')}")
            w()

            # ── Targeting Detail ─────────────────────────────────────────────
            tdata = targeting_data.get(ab, {})
            if tdata:
                total_t = sum(tdata.values())
                top_targets = sorted(tdata.items(), key=lambda x: x[1], reverse=True)[:5]
                w(f"  TARGETING BREAKDOWN  (Total: {total_t:,})")
                w("  " + "─" * 40)
                for tname, tcount in top_targets:
                    pct = tcount / total_t * 100
                    bar = "█" * int(pct / 5)
                    w(f"  {tname:<18} {tcount:>8,}  {pct:>5.1f}%  {bar}")
                w()

            # ── Balancing Suggestions ────────────────────────────────────────
            w(f"  BALANCING SUGGESTIONS")
            w("  " + "─" * 40)
            sug = BALANCE_SUGGESTIONS.get(ab, ["No suggestions — card is currently stable."])
            for i, s_line in enumerate(sug, 1):
                w(f"  {i}. {s_line}")
            w()
            w()

        w("═" * W)
        w(f"  Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   |   {total_games:,} Games Simulated")
        w("═" * W)

    print(f"Analysis complete! Report saved to '{log_path}'.")


if __name__ == "__main__":
    generate_analysis()
