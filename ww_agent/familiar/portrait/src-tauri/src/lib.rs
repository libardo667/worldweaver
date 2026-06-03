// The stable's native shell. Three commands bridge the portrait to the familiar
// root (the dir holding each familiar's home folder) — the same contract the
// browser preview uses: list the roster, read a chosen familiar's state.json,
// append to its whispers.jsonl. The minds live in the Python daemons.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

use chrono::Local;
use serde_json::{json, Value};

const ASLEEP: &str = r#"{"name":"—","mood":"asleep","felt_sense":"(not yet woken — run familiar/wake-all.sh)","awake":false}"#;

/// The familiar root. Set WW_FAMILIAR_ROOT for a real install; otherwise fall back
/// to ../.. (the familiar/ dir) relative to this crate so `tauri dev` just works.
fn root_dir() -> PathBuf {
    if let Ok(p) = std::env::var("WW_FAMILIAR_ROOT") {
        if !p.trim().is_empty() {
            return PathBuf::from(p);
        }
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn familiars(root: &Path) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    if let Ok(entries) = fs::read_dir(root) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if entry.path().is_dir() && name != "portrait" && entry.path().join("identity").is_dir() {
                out.push(name);
            }
        }
    }
    out.sort();
    out
}

fn home_for(root: &Path, who: &str) -> PathBuf {
    let fams = familiars(root);
    if !who.is_empty() && fams.iter().any(|f| f == who) {
        root.join(who)
    } else {
        root.join(fams.first().cloned().unwrap_or_default())
    }
}

fn is_live(path: &Path) -> bool {
    fs::metadata(path)
        .and_then(|m| m.modified())
        .map(|t| t.elapsed().map(|d| d.as_secs() < 150).unwrap_or(false))
        .unwrap_or(false)
}

#[tauri::command]
fn list_familiars() -> String {
    let root = root_dir();
    let mut roster: Vec<Value> = Vec::new();
    for name in familiars(&root) {
        let mut entry = json!({"who": name, "name": name, "mood": "asleep", "awake": false, "live": false});
        let sp = root.join(&name).join("state.json");
        if let Ok(txt) = fs::read_to_string(&sp) {
            if let Ok(st) = serde_json::from_str::<Value>(&txt) {
                entry["name"] = st.get("name").cloned().unwrap_or_else(|| json!(name));
                entry["mood"] = st.get("mood").cloned().unwrap_or_else(|| json!("—"));
                entry["awake"] = st.get("awake").cloned().unwrap_or(json!(false));
                entry["arousal"] = st.get("arousal").cloned().unwrap_or(json!(0.0));
                entry["wakefulness"] = st.get("wakefulness").cloned().unwrap_or(json!(1.0));
                entry["live"] = json!(is_live(&sp));
            }
        }
        roster.push(entry);
    }
    serde_json::to_string(&roster).unwrap_or_else(|_| "[]".to_string())
}

#[tauri::command]
fn read_state(who: String) -> String {
    fs::read_to_string(home_for(&root_dir(), &who).join("state.json")).unwrap_or_else(|_| ASLEEP.to_string())
}

#[tauri::command]
fn whisper(who: String, text: String) -> Result<(), String> {
    let text = text.trim();
    if text.is_empty() {
        return Ok(());
    }
    let line = json!({ "ts": Local::now().to_rfc3339(), "text": text }).to_string();
    let path = home_for(&root_dir(), &who).join("whispers.jsonl");
    let mut file = fs::OpenOptions::new().create(true).append(true).open(&path).map_err(|e| e.to_string())?;
    writeln!(file, "{}", line).map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![list_familiars, read_state, whisper])
        .run(tauri::generate_context!())
        .expect("error while running the stable");
}
