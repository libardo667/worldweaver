import json
import os

def merge_playtest(output_file, num_turns=15):
    with open("turn_1.json", "r") as f:
        t1 = json.load(f)
    
    world_name = t1["vars"].get("_world_bible", {}).get("world_name", "Unknown World")
    theme = t1["vars"].get("world_theme", "Classic Fantasy")
    role = t1["vars"].get("player_role", "Wandering Knight")
    
    lines = []
    lines.append(f"# Manual Playtest Transcript: Simple Input / Choice-Following")
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
            
        lines.append(f"## Turn {i} Action -> Turn {i+1} Result")
        lines.append(f"**Action Attempted:** {next_data.get('ack_line', 'N/A')}")
        lines.append(f"")
        lines.append(f"**Narrative Outcome:**")
        lines.append(next_data.get('narrative', 'N/A'))
        lines.append(f"")
        lines.append(f"**State Changes:** `{json.dumps(next_data.get('state_changes', {}))}`")
        lines.append(f"")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Merged into {output_file}")

if __name__ == "__main__":
    merge_playtest("playtests/simple_fantasy_playthrough.md")
