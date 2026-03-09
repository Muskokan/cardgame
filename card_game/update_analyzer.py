import re

with open("c:\\Users\\chefj\\.gemini\\windfall\\scratch\\card_game\\power_analyzer.py", "r", encoding="utf-8") as f:
    text = f.read()

replacements = {
    '"Hush"': '"Cease & Desist"',
    '"Money"': '"Earnings"',
    '"Snatch"': '"Diversify"',
    '"Check"': '"Call"',
    '"Redact"': '"Liquidate"',
    '"Repeat"': '"Invest"',
    '"Reprise"': '"Delist"',
    '"Return"': '"Recoup"',
    '"Betray"': '"Undercut"',
    '"Crush"': '"Crash"',
    
    # Text replacements
    "Hush": "Cease & Desist",
    "Money": "Earnings",
    "Snatch": "Diversify",
    "Check": "Call",
    "Redact": "Liquidate",
    "Repeat": "Invest",
    "Reprise": "Delist",
    "Return": "Recoup",
    "Betray": "Undercut",
    "Crush": "Crash",
    
    # Mechanic updates
    "[Pitch] Counter target Stack placement": "[Burn] Counter target Stack placement",
    "Costs 2 cards (discard Hush card + pitch another)": "Costs 2 cards (discard Cease & Desist card + burn another from stockpile)",
    "no Pitch cost.": "no Burn cost.",
    "[Burn] Steal target opponent's": "[Pitch] Steal target opponent's",
    "Requires [Burn] \\u2014 you destroy a card from your own stockpile": "Requires [Pitch] \u2014 you discard a card from your hand",
    "The Burn cost is too punitive": "The Pitch cost used to be Burn, now it's Pitch",
}

for old, new in replacements.items():
    text = text.replace(old, new)

# specific fix for Reprise / Delist:
# 'Delist players' maybe sounds weird but is fine.

with open("c:\\Users\\chefj\\.gemini\\windfall\\scratch\\card_game\\power_analyzer.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated power_analyzer.py")
