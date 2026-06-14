mod docker;
mod env;
mod settings;
mod setup;
mod stack;
mod tray;

use setup::SharedSetupState;
use tauri::{Manager, RunEvent, WindowEvent};

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

#[tauri::command]
fn get_app_settings(app: tauri::AppHandle) -> Result<settings::AppSettings, String> {
    Ok(settings::load(&app))
}

#[tauri::command]
fn set_stop_containers_on_exit(app: tauri::AppHandle, enabled: bool) -> Result<settings::AppSettings, String> {
    let updated = settings::set_stop_containers_on_exit(&app, enabled)?;
    tray::update_stop_on_exit_checked(&app, updated.stop_containers_on_exit);
    Ok(updated)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(SharedSetupState::default())
        .setup(|app| {
            tray::create_tray(app.handle())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            start_environment_setup,
            get_setup_snapshot,
            stop_services,
            get_app_settings,
            set_stop_containers_on_exit,
        ])
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "main-app" {
                    api.prevent_close();
                    let _ = window.hide();
                    return;
                }

                if window.label() == "main" {
                    let app = window.app_handle();
                    let services_ready = app
                        .state::<SharedSetupState>()
                        .lock()
                        .ok()
                        .and_then(|state| state.app_url.clone())
                        .is_some();

                    if services_ready {
                        api.prevent_close();
                        let _ = window.hide();
                    }
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|app_handle, event| {
            if let RunEvent::ExitRequested { api, .. } = event {
                if tray::is_quitting() {
                    return;
                }
                api.prevent_exit();
                tray::quit_app(app_handle);
            }
        });
}
