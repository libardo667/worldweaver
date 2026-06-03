// Cinder's native shell. Two commands bridge the portrait to the familiar's home
// dir — the same two-file contract the browser preview uses: read state.json,
// append whispers.jsonl. Nothing else; the mind lives in the Python daemon.

use std::fs;
use std::io::Write;
use std::path::PathBuf;

use chrono::Local;

/// The familiar's home dir. Set WW_FAMILIAR_HOME for a real install; otherwise
/// fall back to ../../cinder relative to this crate so `tauri dev` just works.
fn home_dir() -> PathBuf {
    if let Ok(p) = std::env::var("WW_FAMILIAR_HOME") {
        if !p.trim().is_empty() {
            return PathBuf::from(p);
        }
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../cinder")
}

const ASLEEP: &str = r#"{"name":"Cinder","mood":"asleep","felt_sense":"(not yet woken — run scripts/familiar.py)","awake":false}"#;

#[tauri::command]
fn read_state() -> String {
    fs::read_to_string(home_dir().join("state.json")).unwrap_or_else(|_| ASLEEP.to_string())
}

#[tauri::command]
fn whisper(text: String) -> Result<(), String> {
    let text = text.trim();
    if text.is_empty() {
        return Ok(());
    }
    let line = serde_json::json!({ "ts": Local::now().to_rfc3339(), "text": text }).to_string();
    let path = home_dir().join("whispers.jsonl");
    let mut file = fs::OpenOptions::new().create(true).append(true).open(&path).map_err(|e| e.to_string())?;
    writeln!(file, "{}", line).map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![read_state, whisper])
        .run(tauri::generate_context!())
        .expect("error while running Cinder");
}
