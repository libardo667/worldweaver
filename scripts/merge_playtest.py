import json
import os

def merge_playtest(output_file, num_turns=15):
    with open("turn_1.json", "r") as f:
        t1 = json.load(f)
    
    world_name = t1["vars"].get("_world_bible", {}).get("world_name", "Unknown World")
    theme = t1["vars"].get("world_theme", "Space Opera")
    role = t1["vars"].get("player_role", "Smuggler Captain")
    
    lines = []
    lines.append(f"# Manual Playtest Transcript: `google/gemini-3-flash-preview`")
    lines.append(f"")
    lines.append(f"## World: {world_name}")
    lines.append(f"**Theme:** {theme}")
    lines.append(f"**Role:** {role}")
    lines.append(f"")
    lines.append(f"### Initial Narrative")
    lines.append(t1["text"])
    lines.append(f"")
    
    for i in range(1, num_turns):
        current_file = f"turn_{i}.json"
        next_file = f"turn_{i+1}.json"
        
        if not os.path.exists(next_file):
            break
            
        with open(next_file, "r") as f:
            next_data = json.load(f)
            
        # The action taken at turn i is recorded in the 'ack_line' or we can infer it
        # Actually, the action text is usually what we sent. 
        # In our case, each turn_N.json (N > 1) has the 'ack_line' which is the agent's acknowledgment.
        # But wait, looking at manual_gemini3_flash.md, it uses "**Action Attempted:**"
        # We can use the 'ack_line' or if we want the exact raw action, we'd need to have saved it.
        # However, 'ack_line' is a good descriptive summary.
        
        # Let's try to find what action was submitted. 
        # The harness.py doesn't save the raw action in the JSON, but the backend returns 'ack_line'.
        
        lines.append(f"## Turn {i} Action -> Turn {i+1} Result")
        # We'll use ack_line as 'Action Attempted' for clarity in the transcript
        lines.append(f"**Action Attempted:** {next_data.get('ack_line', 'N/A')}")
        lines.append(f"")
        lines.append(f"**Narrative Outcome:**")
        lines.append(next_data.get('narrative', 'N/A'))
        lines.append(f"")
        lines.append(f"**State Changes:** `{json.dumps(next_data.get('state_changes', {}))}`")
        lines.append(f"")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ Merged {num_turns} turns into {output_file}")

if __name__ == "__main__":
    merge_playtest("playtests/space_opera_playthrough.md")
