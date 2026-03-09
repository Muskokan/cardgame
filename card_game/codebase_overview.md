# Windfall Codebase Overview

This document provides a map of the current files and directories in the Windfall codebase, categorized by their function.

## 🎮 Core Game Engine
- **[models.py](file:///c:/Users/chefj/.gemini/antigravity/scratch/models.py)**: Defines the fundamental data structures of the game, including `Card`, `Player`, `Ability`, `Effect`, and `Action`. It handles effect resolution logic and state serialization.
- **[engine.py](file:///c:/Users/chefj/.gemini/antigravity/scratch/engine.py)**: The heartbeat of the game. Manages the `GameState`, phase transitions (Draw, Stock, React, Resolve), the card stack, and rules like win conditions and deck depletion.
- **[cards.json](file:///c:/Users/chefj/.gemini/antigravity/scratch/cards.json)**: The official database of all cards in the game. It defines every card's name, cost, and specific ability effects.

## 🤖 Artificial Intelligence
- **[ai.py](file:///c:/Users/chefj/.gemini/antigravity/scratch/ai.py)**: Contains all the logic for bot decision-making. Includes heuristics for stocking cards, using reactions defensively or aggressively, and profile-based targeting (Aggressive, Defensive, etc.).

## 🖥️ Local Terminal Version
- **[main.py](file:///c:/Users/chefj/.gemini/antigravity/scratch/main.py)**: The entry point for the local terminal-based version of the game. Handles the main menu and game loop.
- **[view.py](file:///c:/Users/chefj/.gemini/antigravity/scratch/view.py)**: Implements the `ConsoleView`, which renders the ASCII game board, handles user prompts, and displays the activity logs in the terminal.
- **[colors.py](file:///c:/Users/chefj/.gemini/antigravity/scratch/colors.py)**: Simple utility defining ANSI color codes for a vibrant terminal UI.
- **[rules.md](file:///c:/Users/chefj/.gemini/antigravity/scratch/rules.md)**: The detailed rulebook for the game, which is parsable by `main.py` to show in-game help.

## 🌐 Online Multiplayer System
- **[server.py](file:///c:/Users/chefj/.gemini/antigravity/scratch/server.py)**: A FastAPI/WebSocket server that enables multiple people to play together over LAN or the Internet.
- **[room_manager.py](file:///c:/Users/chefj/.gemini/antigravity/scratch/room_manager.py)**: Backend logic for creating game rooms, assigning players/bots to seats, and managing room lifecycles.
- **[static/](file:///c:/Users/chefj/.gemini/antigravity/scratch/static)**: Contains the web frontend assets:
  - `index.html`: The landing page for creating/joining rooms.
  - `lobby.html`: The pre-game lounge for seating and bot assignment.
  - `game.html`: The real-time, glassy web interface for playing the game.
  - `style.css`: Modern, unified styling for all web components.

## 📊 Balance & Simulation Tools
- **[simulate.py](file:///c:/Users/chefj/.gemini/antigravity/scratch/simulate.py)**: A high-speed simulation script capable of running thousands of games between bots to gather balancing data.
- **[power_analyzer.py](file:///c:/Users/chefj/.gemini/antigravity/scratch/power_analyzer.py)**: Processes raw simulation data to generate human-readable balance reports and suggestions.
- **[Card Power Analysis.txt](file:///c:/Users/chefj/.gemini/antigravity/scratch/Card%20Power%20Analysis.txt)**: The current generated report on card performance, win rates, and balance scores.
- **sim_data.json**: The raw output from the last simulation run.
- **power_history.json**: Tracks how ability power has changed over time/versions.
