use std::sync::Mutex;
use std::thread;

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindowBuilder};

use crate::docker;
use crate::env::{self, OsKind};
use crate::stack;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SetupProgress {
    pub step: String,
    pub message: String,
    pub status: SetupStatus,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum SetupStatus {
    Running,
    Done,
    Error,
}

#[derive(Default)]
pub struct SetupState {
    pub running: bool,
    pub last_error: Option<String>,
    pub app_url: Option<String>,
}

pub type SharedSetupState = Mutex<SetupState>;

fn emit_progress(app: &AppHandle, step: &str, message: &str, status: SetupStatus) {
    let _ = app.emit(
        "setup-progress",
        SetupProgress {
            step: step.into(),
            message: message.into(),
            status,
        },
    );
}

pub fn start_setup(app: AppHandle) -> Result<(), String> {
    {
        let state = app.state::<SharedSetupState>();
        let mut guard = state.lock().map_err(|_| "setup state lock poisoned".to_string())?;
        if guard.running {
            return Err("环境初始化正在进行中".into());
        }
        guard.running = true;
        guard.last_error = None;
        guard.app_url = None;
    }

    thread::spawn(move || {
        if let Err(error) = run_setup(&app) {
            {
                let state = app.state::<SharedSetupState>();
                if let Ok(mut guard) = state.lock() {
                    guard.running = false;
                    guard.last_error = Some(error.clone());
                };
            }
            emit_progress(
                &app,
                "error",
                &error,
                SetupStatus::Error,
            );
        }
    });

    Ok(())
}

fn run_setup(app: &AppHandle) -> Result<(), String> {
    emit_progress(
        app,
        "detect-os",
        "正在检测操作系统...",
        SetupStatus::Running,
    );
    let os_kind = env::detect_os()?;
    emit_progress(
        app,
        "detect-os",
        &format!("已识别: {}", env::os_label(os_kind)),
        SetupStatus::Done,
    );

    emit_progress(
        app,
        "docker-cli",
        "正在检测 Docker...",
        SetupStatus::Running,
    );
    if !env::docker_cli_installed() {
        emit_progress(
            app,
            "docker-install",
            "未检测到 Docker，正在尝试自动安装...",
            SetupStatus::Running,
        );
        env::install_docker(os_kind, Some(app))?;
        emit_progress(
            app,
            "docker-install",
            "Docker 安装命令已执行",
            SetupStatus::Done,
        );
    } else {
        emit_progress(app, "docker-cli", "Docker 已安装", SetupStatus::Done);
    }

    if os_kind == OsKind::MacOs && !env::docker_daemon_ready() {
        let _ = std::process::Command::new("open")
            .args(["-a", "Docker"])
            .status();
    }

    emit_progress(
        app,
        "docker-daemon",
        "等待 Docker 守护进程就绪...",
        SetupStatus::Running,
    );
    env::wait_for_docker_daemon(90, std::time::Duration::from_secs(2))?;
    emit_progress(
        app,
        "docker-daemon",
        "Docker 已就绪",
        SetupStatus::Done,
    );

    emit_progress(
        app,
        "compose",
        "正在检测 Docker Compose...",
        SetupStatus::Running,
    );
    if !env::compose_available() {
        return Err("未找到 Docker Compose V2。请升级 Docker Desktop。".into());
    }
    emit_progress(app, "compose", "Docker Compose 可用", SetupStatus::Done);

    emit_progress(
        app,
        "stack",
        "正在准备运行目录...",
        SetupStatus::Running,
    );
    let stack_dir = stack::resolve_stack_dir(app)?;
    stack::ensure_env_file(&stack_dir)?;
    emit_progress(
        app,
        "stack",
        &format!("运行目录: {}", stack_dir.display()),
        SetupStatus::Done,
    );

    emit_progress(
        app,
        "services",
        "正在启动服务（首次可能较慢）...",
        SetupStatus::Running,
    );
    docker::compose_up(&stack_dir)?;
    emit_progress(app, "services", "容器已启动", SetupStatus::Done);

    let api_port = stack::read_api_port(&stack_dir);
    let web_port = stack::read_web_port(&stack_dir);

    emit_progress(
        app,
        "health",
        "等待后端健康检查...",
        SetupStatus::Running,
    );
    docker::wait_for_health(api_port, 120)?;
    emit_progress(app, "health", "后端已就绪", SetupStatus::Done);

    let app_url = format!("http://127.0.0.1:{web_port}");
    {
        let state = app.state::<SharedSetupState>();
        let mut guard = state.lock().map_err(|_| "setup state lock poisoned".to_string())?;
        guard.running = false;
        guard.app_url = Some(app_url.clone());
    }

    emit_progress(
        app,
        "ready",
        &format!("正在打开 {app_url}"),
        SetupStatus::Done,
    );

    open_main_window(app, &app_url)?;
    Ok(())
}

fn open_main_window(app: &AppHandle, app_url: &str) -> Result<(), String> {
    if app.get_webview_window("main-app").is_some() {
        return Ok(());
    }

    let parsed = app_url
        .parse()
        .map_err(|error| format!("无效的应用 URL: {error}"))?;

    WebviewWindowBuilder::new(app, "main-app", WebviewUrl::External(parsed))
        .title("AI Story")
        .inner_size(1400.0, 900.0)
        .min_inner_size(960.0, 640.0)
        .build()
        .map_err(|error| error.to_string())?;

    if let Some(setup_window) = app.get_webview_window("main") {
        let _ = setup_window.close();
    }

    Ok(())
}

pub fn stop_stack(app: &AppHandle) -> Result<(), String> {
    let stack_dir = stack::resolve_stack_dir(app)?;
    docker::compose_down(&stack_dir)
}
