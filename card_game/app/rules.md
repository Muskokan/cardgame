# Windfall Design Document

## 1. Setup & Win Conditions

- **Players:** 2-4
- **Deck:** 70 cards total (14 of each type). Shared by all players.
- **Starting Hand:** Each player starts with 5 cards. No maximum size.
- **Win Conditions:** A player wins the game if their **Stockpile** meets either of these two conditions after the **Resolution Phase** of any turn:
  1. It contains **4 copies** of the exact same card type.
  2. It contains **exactly 1 copy** of all 5 different card types.

- **Empty Deck:** If a player attempts to draw a card from an empty deck, that player **wins** the game immediately.

## 2. Game Zones

- **Hand:** Private. Hidden but revealable. Cards are drawn here and pitched from here.
- **Stockpile:** Face-up cards placed on the table by each player. This is your "board" where you build towards your win conditions.
- **Deck:** Face-down. Shared by all players.
- **Discard (Graveyard):** Face-up. Shared by all players. Cards discarded from hand or "destroyed" from the Stockpile go here.
- **The Pot:** Face-up. When a Stockpile card's ability is placed on the Stack, that card moves from the Stockpile into the Pot. Once its ability resolves (or fizzles), the card returns to the owner's Stockpile. If it is countered or destroyed while in the Pot, it goes to the Graveyard instead.
- **The Stack:** The invisible zone where abilities wait to resolve before taking effect (see *Section 4*).

## 3. Turn Structure

The game proceeds in clockwise order. On a player's turn, they are the **Active Player**. A turn consists of four strict phases:

### Phase 1: Draw Phase
The Active Player draws 1 card.
*(Note: Player 1 skips this phase on their very first turn in a 2-player game).*

### Phase 2: Place (Stock) Phase
The Active Player **MUST** choose exactly *one* card from their Hand and place it face-up in their **Stockpile**. 
- There is no passing this phase (unless your hand is empty). 
- **Empty Hand Force-Play:** If you begin this phase with exactly 1 card in your Hand, you are forced to place it in your Stockpile, leaving you with an empty Hand.
- Placing the card triggers its **Stockpile Ability**, placing it onto **The Stack**.

### Phase 3: Reaction Phase
When the Active Player places their Stockpile Ability on the Stack, the other players may respond. 
- Starting with the player to the Active Player's left, each player may choose to activate exactly *one* **React Ability**. 
- **Inherent Cost:** To place a React Ability on the Stack, the player must immediately discard that specific card from their Hand to the Graveyard.
- This priority passes around the table, ending with the Active Player (who may also choose to activate exactly one React Ability in response). 
- All React Abilities *only* happen in response to a card being stockpiled. 
- **Targeting & Additional Costs:** Any required targets (e.g., which card to Return) must be declared, and any specific additional costs (like pitching an extra card) must be paid at the exact moment the ability goes onto the Stack.

### Phase 4: Resolution Phase
Abilities on the Stack resolve in **Last-In, First-Out (LIFO)** order. The *last* player to react has their Hand Ability resolve *first*, moving backward until the Active Player's original Stockpile Ability resolves (if it wasn't countered).

## 4. The Stack & Advanced Rulings

- **Paying Costs:** The cost to activate a Hand ability (e.g., destroying your own Stockpile card for *Betray*) is paid *upfront* during the Reaction Phase. If your ability is later countered by *Hush*, your costs are **not refunded**. 
- **Fizzling (Target Legality):** In the Resolution Phase, if an ability's target is no longer viable (e.g., the target card was already destroyed by an ability higher on the Stack), the ability **fizzles** (fails to resolve) and does nothing. 
- **Zone Changes:** If a card that generated an ability is moved to a completely different zone (e.g., the source card for a Stockpile ability is stolen by *Betray* or destroyed by *Crush* before it can resolve), that ability will **fizzle**. You must control the source card for its ability to properly resolve.
- **Impossible Actions:** If an effect forces a player to do something they mathematically cannot do (e.g., *Snatch* forces a pitch when a player's hand is empty), that specific player simply ignores that part of the effect. No alternate penalty is applied.
- **No Self-Targeting Offensive Abilities:** Abilities like *Crush, Check*, and *Betray* explicitly specify attacking an opponent. You cannot target yourself or your own cards with them.
- **Repeat Targeting Exception:** When a player activates *Repeat*, they declare *which* Stockpile card from *any* player they are copying as it goes on the stack. However, they do *not* declare the final target of the copied ability (e.g., who they are *Crushing*) until *Repeat* successfully resolves.
- **Hush vs. Repeat:** If *Hush* counters a *Repeat* placement, the *Hush* successfully counters the *Repeat* card itself, preventing whatever effect it was attempting to copy.

## 5. Cost Keywords

To save space on physical cards, additional costs to activate React abilities are abbreviated into keywords. *(Remember: discarding the React card itself is always the inherent baseline cost).*
- **Pitch:** Discard 1 *additional* card from your hand into the Graveyard.
- **Burn:** Destroy 1 card currently in your own Stockpile.

## 6. Card Index

### 1. Hush/Money
- **Hush (React):** **[Pitch]** Counter target Stockpile placement or Reaction on the Stack, then draw 1 card.
- **Money (Stock):** Draw 1 card.

### 2. Snatch/Check
- **Snatch (React):** Each opponent pitches 1 card. You then choose 1 of the pitched cards and put it into your hand. The remaining pitched cards are discarded to the Graveyard.
- **Check (Stock):** Target opponent pitches 1 card.

### 3. Redact/Repeat
- **Redact (React):** Return target opponent's Stockpile card to their hand.
- **Repeat (Stock):** Copy a target Stockpile card from ANY player's Stockpile. *(Cannot target Repeat).*

### 4. Reprise/Return
- **Reprise (React):** Put target Graveyard card **or** active card from the Pot on top of the deck.
- **Return (Stock):** Put target Graveyard card into your hand.

### 5. Betray/Crush
- **Betray (React):** **[Burn]** Steal target opponent's Stockpile card. Its Stockpile ability triggers for you.
- **Crush (Stock):** Destroy target opponent's Stockpile card.
