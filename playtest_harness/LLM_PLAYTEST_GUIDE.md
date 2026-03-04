# LLM Playtest Guide: How to Play WorldWeaver

Welcome, fellow Intelligence. You are about to participate in a narrative simulation. To ensure a smooth experience and maintain technical state across turns, follow this guide.

## 🛠 Prerequisites

1.  **Backend Running**: Ensure the WorldWeaver API is running (usually on port 8000).
2.  **Harness Script**: Use the `playtest_harness/harness.py` script to interact with the API. This avoids manual `curl` calls and handles state persistence (saving turns as JSON files).

## 🎮 The Workflow

### 1. Initialization
Choose a `session_id` (e.g., `test-session-001`) and a model (e.g., `google/gemini-3-flash-preview`).
Run:
```bash
python playtest_harness/harness.py init <model_id> <session_id>
```
*This will switch the model, reset the database, and bootstrap a Cyberpunk Noir world.*

### 2. Get Your First Turn
To see the opening narrative and your choices:
```bash
python playtest_harness/harness.py next <session_id> 1
```
*This saves `turn_1.json`. Read this file to understand the scene and variables.*

### 3. Take Action
You can pick a provided choice or invent a freeform action.
```bash
python playtest_harness/harness.py action <session_id> turn_1.json "My awesome freeform action"
```
*This saves `turn_2.json`. The script automatically extracts state variables from the previous turn.*

### 4. Rinse and Repeat
Continue calling `action` using the latest `turn_N.json` until you reach turn 10.

## 🧠 Best Practices for LLMs

*   **Read the JSONs**: Always read the `turn_N.json` files. They contain the `narrative`, `choices`, and `vars` (the world memory).
*   **Use Freeform**: Don't just stick to the choices. The `command_interpreter` in WorldWeaver is designed to handle descriptive, creative actions.
*   **Watch the Vars**: Pay attention to variables like `danger`, `location`, and `has_memory_core`. These are the "soul" of the game's mechanics.
*   **Roleplay**: Stay in character! If you're a rogue AI hunter, act like one. The JIT generation pipeline responds better to consistent tone.

Have fun weaving your world!
