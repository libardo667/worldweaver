import requests
import json
import time
import sys
import os

BASE_URL = "http://127.0.0.1:8000/api"

SCENARIOS = {
    "everyday": {
        "theme": "everyday city life",
        "role": "part-time barista balancing rent, friendships, and future plans",
        "description": (
            "A contemporary neighborhood where small choices matter: work shifts, "
            "roommates, transit delays, family calls, and community events all tug "
            "at your limited time and energy."
        ),
        "key_elements": [
            "crowded morning bus rides",
            "group chat notifications",
            "apartment chores and bills",
            "coffee shop regulars",
            "evening community center classes",
        ],
        "tone": "grounded, warm, and quietly tense",
    },
    "gothic": {
        "theme": "gothic clockwork alchemy",
        "role": "outcast alchemist",
        "description": (
            "A gothic clockwork alchemy world where technology is gear-driven and "
            "magic is alchemical. The city of Oakhaven is powered by ancient, "
            "monstrous clockwork leviathans."
        ),
        "key_elements": [
            "whirring gears",
            "vials of glowing mercury",
            "soot-stained gargoyles",
            "clockwork prosthetic limbs",
            "the Great Gear",
        ],
        "tone": "opulent and decaying",
    },
}

def switch_model(model_id):
    print(f"🔄 Switching model to {model_id}...")
    res = requests.put(f"{BASE_URL}/model", json={"model_id": model_id})
    res.raise_for_status()
    print(f"✅ Switched to {model_id}")

def hard_reset():
    print("🔄 Resetting database...")
    res = requests.post(f"{BASE_URL}/dev/hard-reset")
    res.raise_for_status()
    print("✅ Database reset.")

def bootstrap(session_id, scenario_name="everyday"):
    if scenario_name == "interactive":
        print("\n--- Interactive World Building ---")
        theme = input("Enter world theme (e.g. cyberpunk noir): ").strip() or "cyberpunk noir"
        role = input("Enter player role (e.g. rogue AI hunter): ").strip() or "rogue AI hunter"
        description = input("Enter world description: ").strip() or "A neon-lit dystopia where rogue AIs hide in the shadows of mega-corporations."
        elements_str = input("Enter key elements (comma-separated): ").strip()
        key_elements = [e.strip() for e in elements_str.split(",")] if elements_str else ["neon", "rain", "cybernetics"]
        tone = input("Enter tone (e.g. gritty, suspenseful): ").strip() or "gritty"
        scenario = {
            "theme": theme,
            "role": role,
            "description": description,
            "key_elements": key_elements,
            "tone": tone,
        }
    else:
        scenario = SCENARIOS.get(scenario_name, SCENARIOS["everyday"])
        
    print(f"🌍 Bootstrapping session: {session_id}...")
    payload = {
        "session_id": session_id,
        "world_theme": scenario["theme"],
        "player_role": scenario["role"],
        "description": scenario["description"],
        "key_elements": scenario["key_elements"],
        "tone": scenario["tone"],
        "storylet_count": 5
    }
    res = requests.post(f"{BASE_URL}/session/bootstrap", json=payload)
    res.raise_for_status()
    print(f"✅ Session {session_id} bootstrapped with scenario '{scenario_name}'.")
    return res.json()

def get_next(session_id, turn_idx):
    print(f"📝 Fetching Turn {turn_idx}...")
    res = requests.post(f"{BASE_URL}/next", json={"session_id": session_id, "vars": {}})
    res.raise_for_status()
    data = res.json()
    filename = f"turn_{turn_idx}.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Turn {turn_idx} data saved to {filename}")
    return data

def submit_action(session_id, last_turn_file, action_text):
    with open(last_turn_file, "r") as f:
        last_turn_data = json.load(f)
    
    current_vars = last_turn_data.get("vars", {})
    # Detect next turn number
    import re
    match = re.search(r"turn_(\d+)\.json", last_turn_file)
    last_turn_num = int(match.group(1)) if match else 1
    next_turn_num = last_turn_num + 1
    
    print(f"🚀 Submitting action for Turn {next_turn_num}: {action_text}")
    payload = {
        "session_id": session_id,
        "action": action_text,
        "contextual_vars": current_vars,
        "recent_events": [],
        "idempotency_key": f"action-{int(time.time())}"
    }
    res = requests.post(f"{BASE_URL}/action", json=payload)
    res.raise_for_status()
    data = res.json()
    
    filename = f"turn_{next_turn_num}.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Turn {next_turn_num} result saved to {filename}")
    return data

def usage():
    print("Usage:")
    print("  python harness.py init <model_id> <session_id> [scenario]")
    print("  python harness.py next <session_id> <turn_idx>")
    print("  python harness.py action <session_id> <last_turn_file> '<action_text>'")
    print("Scenarios:")
    print(f"  {', '.join(sorted(SCENARIOS.keys()))}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    try:
        if cmd == "init":
            mid, sid = sys.argv[2], sys.argv[3]
            scenario = sys.argv[4] if len(sys.argv) > 4 else "everyday"
            switch_model(mid)
            hard_reset()
            bootstrap(sid, scenario)
        elif cmd == "next":
            sid, tidx = sys.argv[2], int(sys.argv[3])
            get_next(sid, tidx)
        elif cmd == "action":
            sid, ltf, act = sys.argv[2], sys.argv[3], sys.argv[4]
            submit_action(sid, ltf, act)
        else:
            usage()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
