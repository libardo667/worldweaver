import json
import time
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8000/api"

# We'll test a curated list of models from the registry.
# Skipping Opus due to massive cost, but including the major players.
MODELS = [
    "deepseek/deepseek-chat:free",
    "qwen/qwen3.5-flash-02-23",
    "openai/gpt-4o-mini",
    "google/gemini-3-flash-preview",
    "openai/gpt-4o",
    "anthropic/claude-sonnet-4"
]

def run_multi_model_playtest():
    print("==================================================")
    print("  WORLDWEAVER MULTI-MODEL BENCHMARK SUITE")
    print("==================================================\n")
    
    # Create an output directory for the transcripts
    os.makedirs("playtests", exist_ok=True)
    
    for model_id in MODELS:
        print(f"\n[{model_id}] ====================")
        
        # 1. Ask the backend to switch its active model using the runtime override endpoint
        switch_res = requests.put(f"{BASE_URL}/model", json={"model_id": model_id})
        if switch_res.status_code != 200:
            print(f"[{model_id}] ❌ Failed to switch model on the backend: {switch_res.text}")
            continue
            
        print(f"[{model_id}] 🔄 Backend model switched. Resetting database...")
        requests.post(f"{BASE_URL}/dev/hard-reset")
        
        clean_session_id = f"bench-{model_id.replace('/', '-').replace(':', '-').replace('.', '-')}"
        SESSION_ID = clean_session_id
        transcript = [f"# Model Benchmark: `{model_id}`\n\n"]
        
        start_time = time.time()
        
        print(f"[{model_id}] 🌍 Bootstrapping Cyberpunk world...")
        bootstrap_payload = {
            "session_id": SESSION_ID,
            "world_theme": "cyberpunk noir",
            "player_role": "rogue AI hunter",
            "description": "The neon-soaked streets of Neo-Veridia. It always rains here. The megacorps run everything, but down in the Undercity, data is the only currency that matters.",
            "key_elements": ["neon signs", "chrome implants", "the data broker", "endless rain", "hover cars"],
            "tone": "gritty tech-noir",
            "storylet_count": 5
        }
        
        try:
            # No `timeout=` parameter here. This will block until the Provider naturally drops the connection
            # or the LLM successfully streams the response back.
            b_res = requests.post(f"{BASE_URL}/session/bootstrap", json=bootstrap_payload)
            if b_res.status_code != 200:
                print(f"[{model_id}] ❌ Bootstrap failed: {b_res.text}")
                transcript.append(f"**FAILED AT BOOTSTRAP:** {b_res.text}\n")
                _save_transcript(model_id, transcript)
                continue
            transcript.append(f"**Bootstrap Message:** {b_res.json().get('message')}\n\n")
        except Exception as e:
            print(f"[{model_id}] 💥 Bootstrap fatal error (likely Provider timeout): {e}")
            transcript.append(f"**FATAL ERROR AT BOOTSTRAP:** {e}\n")
            _save_transcript(model_id, transcript)
            continue

        print(f"[{model_id}] 📝 Generating Turn 1 (Opening Beat)...")
        try:
            n_res = requests.post(f"{BASE_URL}/next", json={"session_id": SESSION_ID, "vars": {}})
            n_data = n_res.json()
            narrative = n_data.get("text")
            transcript.append(f"## Turn 1\n\n**NARRATIVE:**\n{narrative}\n\n**Choices:**\n")
            
            choices = n_data.get("choices", [])
            for i, c in enumerate(choices):
                transcript.append(f"- [{i}] {c.get('label')}")
            transcript.append("\n")
            
            current_vars = n_data.get("vars", {})
        except Exception as e:
            print(f"[{model_id}] 💥 Turn 1 fatal error: {e}")
            transcript.append(f"**FATAL ERROR ON TURN 1:** {e}\n")
            _save_transcript(model_id, transcript)
            continue

        success = True
        for turn in range(2, 11):
            print(f"[{model_id}] 📝 Generating Turn {turn} / 10...")
            
            # Autopilot logic: Just pick the first choice presented, or generically look around
            chosen_text = choices[0].get("label") if choices else "Look around carefully."
            transcript.append(f"## Turn {turn}\n\n**PLAYER ACTION:** {chosen_text}\n\n")
            
            action_payload = {
                "session_id": SESSION_ID,
                "action": chosen_text,
                "contextual_vars": current_vars,
                "recent_events": [],
                "idempotency_key": f"turn_{turn}_{int(time.time())}"
            }
            
            try:
                a_res = requests.post(f"{BASE_URL}/action", json=action_payload)
                if a_res.status_code != 200:
                    print(f"[{model_id}] ❌ Action failed at turn {turn}: {a_res.text}")
                    transcript.append(f"**FAILED AT TURN {turn}:** {a_res.text}\n")
                    success = False
                    break
                    
                a_data = a_res.json()
                current_vars = a_data.get("vars", {})
                narrative = a_data.get("narrative")
                
                transcript.append(f"**NARRATIVE:**\n{narrative}\n\n**Choices:**\n")
                choices = a_data.get("choices", [])
                for i, c in enumerate(choices):
                    transcript.append(f"- [{i}] {c.get('label')}")
                transcript.append("\n")
            except Exception as e:
                print(f"[{model_id}] 💥 Turn {turn} fatal error: {e}")
                transcript.append(f"**FATAL ERROR ON TURN {turn}:** {e}\n")
                success = False
                break
                
        end_time = time.time()
        elapsed = end_time - start_time
        status = "✅ COMPLETED" if success else "❌ FAILED (Provider Timeout / Error)"
        
        print(f"[{model_id}] {status} in {elapsed:.1f} seconds.\n")
        transcript.append(f"\n---\n**STATUS:** {status}\n**TOTAL PLAYTEST TIME:** {elapsed:.1f} seconds\n")
        
        _save_transcript(model_id, transcript)

def _save_transcript(model_id, transcript_lines):
    clean_id = model_id.replace('/', '_').replace(':', '_')
    filename = f"playtests/benchmark_{clean_id}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("".join(transcript_lines))
    print(f"[{model_id}] 💾 Transcript saved to {filename}")

if __name__ == "__main__":
    run_multi_model_playtest()
