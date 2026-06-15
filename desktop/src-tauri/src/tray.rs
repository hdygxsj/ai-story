use std::sync::atomic::{AtomicBool, Ordering};

use tauri::{
    menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager,
};

use crate::settings::{self, AppSettings};
use crate::setup;

pub const TRAY_ID: &str = "main-tray";
const MENU_OPEN: &str = "open";
const MENU_STOP: &str = "stop";
const MENU_STOP_ON_EXIT: &str = "stop_on_exit";
const MENU_QUIT: &str = "quit";

static APP_IS_QUITTING: AtomicBool = AtomicBool::new(false);

pub struct TrayMenuState {
    pub stop_on_exit_item: CheckMenuItem<tauri::Wry>,
}

pub fn is_quitting() -> bool {
    APP_IS_QUITTING.load(Ordering::SeqCst)
}

pub fn focus_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main-app") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
        return;
    }

    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

pub fn quit_app(app: &AppHandle) {
    APP_IS_QUITTING.store(true, Ordering::SeqCst);

    let settings = settings::load(app);
    if settings.stop_containers_on_exit {
        let _ = setup::stop_stack(app);
    }

    app.exit(0);
}

pub fn create_tray(app: &AppHandle) -> Result<(), String> {
    let settings = settings::load(app);
    let (menu, stop_on_exit_item) = build_menu(app, &settings)?;

    let icon = app
        .default_window_icon()
        .ok_or_else(|| "缺少应用图标".to_string())?
        .clone();

    TrayIconBuilder::with_id(TRAY_ID)
        .icon(icon)
        .menu(&menu)
        .tooltip("AI Story")
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| {
            handle_menu_event(app, event.id.as_ref());
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                focus_main_window(tray.app_handle());
            }
        })
        .build(app)
        .map_err(|error| error.to_string())?;

    app.manage(TrayMenuState { stop_on_exit_item });
    Ok(())
}

fn build_menu(
    app: &AppHandle,
    settings: &AppSettings,
) -> Result<(Menu<tauri::Wry>, CheckMenuItem<tauri::Wry>), String> {
    let open = MenuItem::with_id(app, MENU_OPEN, "打开 AI Story", true, None::<&str>)
        .map_err(|error| error.to_string())?;
    let stop = MenuItem::with_id(app, MENU_STOP, "停止服务", true, None::<&str>)
        .map_err(|error| error.to_string())?;
    let stop_on_exit = CheckMenuItem::with_id(
        app,
        MENU_STOP_ON_EXIT,
        "退出时停止容器",
        true,
        settings.stop_containers_on_exit,
        None::<&str>,
    )
    .map_err(|error| error.to_string())?;
    let quit = MenuItem::with_id(app, MENU_QUIT, "退出", true, None::<&str>)
        .map_err(|error| error.to_string())?;
    let separator = PredefinedMenuItem::separator(app).map_err(|error| error.to_string())?;

    let menu = Menu::with_items(
        app,
        &[
            &open,
            &stop,
            &separator,
            &stop_on_exit,
            &separator,
            &quit,
        ],
    )
    .map_err(|error| error.to_string())?;

    Ok((menu, stop_on_exit))
}

fn handle_menu_event(app: &AppHandle, menu_id: &str) {
    match menu_id {
        MENU_OPEN => focus_main_window(app),
        MENU_STOP => {
            let _ = setup::stop_stack(app);
        }
        MENU_STOP_ON_EXIT => {
            let current = settings::load(app);
            let updated = settings::set_stop_containers_on_exit(app, !current.stop_containers_on_exit);
            if let Ok(settings) = updated {
                update_stop_on_exit_checked(app, settings.stop_containers_on_exit);
            }
        }
        MENU_QUIT => quit_app(app),
        _ => {}
    }
}

pub fn update_stop_on_exit_checked(app: &AppHandle, checked: bool) {
    let Some(state) = app.try_state::<TrayMenuState>() else {
        return;
    };
    let _ = state.stop_on_exit_item.set_checked(checked);
}
