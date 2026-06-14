mod docker;
mod env;
mod setup;
mod stack;

use setup::{SharedSetupState};
use tauri::Manager;

#[tauri::command]
fn start_environment_setup(app: tauri::AppHandle) -> Result<(), String> {
    setup::start_setup(app)
}

#[tauri::command]
fn get_setup_snapshot(state: tauri::State<'_, SharedSetupState>) -> Result<serde_json::Value, String> {
    let guard = state.lock().map_err(|_| "setup state lock poisoned".to_string())?;
    Ok(serde_json::json!({
        "running": guard.running,
        "lastError": guard.last_error,
        "appUrl": guard.app_url,
    }))
}

#[tauri::command]
fn stop_services(app: tauri::AppHandle) -> Result<(), String> {
    setup::stop_stack(&app)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(SharedSetupState::default())
        .invoke_handler(tauri::generate_handler![
            start_environment_setup,
            get_setup_snapshot,
            stop_services,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
