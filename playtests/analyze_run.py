import json
import os

path = "playtests/long_runs/20260304T222339Z-longrun-20260304t222339z.json"
with open(path) as f:
    data = json.load(f)

print(f"Total turns: {len(data['turns'])}")

print("\n--- Repetition Check ---")
narratives = [t['narrative'] for t in data['turns']]
for i in range(1, len(narratives)):
    prev = narratives[i-1]
    curr = narratives[i]
    
    # Check for exact prefix matches
    prefix_len = 60
    if curr[:prefix_len] == prev[:prefix_len]:
        print(f"Turn {i} -> {i+1} Exact match prefix: '{curr[:prefix_len]}...'")

print("\n--- System Key Block Check ---")
modifications = []
for t in data['turns']:
    choices = t.get('choices', [])
    for c in choices:
        set_ops = c.get('set', {})
        for k in set_ops:
            if k.startswith('_'):
                modifications.append(f"Turn {t.get('turn')}: Tried to set {k}")
                
if modifications:
    print(f"Found {len(modifications)} attempts by LLM to modify system '_' keys:")
    for m in modifications[:10]:
        print(f"  {m}")
    if len(modifications) > 10: print("  ...")
else:
    print("SUCCESS: No attempts to modify system '_' keys found in choices/intents.")

print("\n--- Fact Decay Check ---")
# Check if "flavor_" or "descriptive_" facts bloat the state
last_vars = data['turns'][-1]['vars']
flavor_keys = [k for k in last_vars.keys() if "flavor" in k.lower() or "descriptive" in k.lower() or "muddy" in k.lower()]
print(f"Flavor/Descriptive keys remaining at end of run: {flavor_keys}")
