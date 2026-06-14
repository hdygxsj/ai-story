use std::sync::atomic::{AtomicBool, Ordering};

use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, Runtime,
};

use crate::settings::{self, AppSettings};
use crate::setup;

pub const TRAY_ID: &str = "main-tray";
const MENU_OPEN: &str = "open";
const MENU_STOP: &str = "stop";
const MENU_STOP_ON_EXIT: &str = "stop_on_exit";
const MENU_QUIT: &str = "quit";

static APP_IS_QUITTING: AtomicBool = AtomicBool::new(false);

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

pub fn create_tray<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    let settings = settings::load(app);
    let menu = build_menu(app, &settings)?;

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

    Ok(())
}

fn build_menu<R: Runtime>(app: &AppHandle<R>, settings: &AppSettings) -> Result<Menu<R>, String> {
    let open = MenuItem::with_id(app, MENU_OPEN, "打开 AI Story", true, None::<&str>)
        .map_err(|error| error.to_string())?;
    let stop = MenuItem::with_id(app, MENU_STOP, "停止服务", true, None::<&str>)
        .map_err(|error| error.to_string())?;
    let stop_on_exit = MenuItem::with_id(
        app,
        MENU_STOP_ON_EXIT,
        "退出时停止容器",
        true,
        None::<&str>,
    )
    .map_err(|error| error.to_string())?;
    stop_on_exit
        .set_checked(settings.stop_containers_on_exit)
        .map_err(|error| error.to_string())?;
    let quit = MenuItem::with_id(app, MENU_QUIT, "退出", true, None::<&str>)
        .map_err(|error| error.to_string())?;
    let separator = PredefinedMenuItem::separator(app).map_err(|error| error.to_string())?;

    Menu::with_items(
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
    .map_err(|error| error.to_string())
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
    let Some(tray) = app.tray_by_id(TRAY_ID) else {
        return;
    };
    let Some(menu) = tray.menu() else {
        return;
    };
    let Some(item) = menu.get(MENU_STOP_ON_EXIT) else {
        return;
    };
    if let Some(menu_item) = item.as_menuitem() {
        let _ = menu_item.set_checked(checked);
    }
}

pub fn refresh_tray_menu(app: &AppHandle) -> Result<(), String> {
    let settings = settings::load(app);
    let menu = build_menu(app, &settings)?;
    let Some(tray) = app.tray_by_id(TRAY_ID) else {
        return Ok(());
    };
    tray.set_menu(Some(menu)).map_err(|error| error.to_string())
}
