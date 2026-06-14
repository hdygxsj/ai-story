use std::process::Command;
use std::thread;
use std::time::Duration;

use tauri::Manager;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OsKind {
    MacOs,
    Linux,
    Windows,
}

pub fn detect_os() -> Result<OsKind, String> {
    match std::env::consts::OS {
        "macos" => Ok(OsKind::MacOs),
        "linux" => Ok(OsKind::Linux),
        "windows" => Ok(OsKind::Windows),
        other => Err(format!("暂不支持的操作系统: {other}")),
    }
}

pub fn os_label(kind: OsKind) -> &'static str {
    match kind {
        OsKind::MacOs => "macOS",
        OsKind::Linux => "Linux",
        OsKind::Windows => "Windows",
    }
}

pub fn docker_cli_installed() -> bool {
    Command::new("docker")
        .arg("--version")
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

pub fn docker_daemon_ready() -> bool {
    Command::new("docker")
        .arg("info")
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

pub fn compose_available() -> bool {
    Command::new("docker")
        .args(["compose", "version"])
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

pub fn wait_for_docker_daemon(max_attempts: u32, sleep: Duration) -> Result<(), String> {
    for attempt in 1..=max_attempts {
        if docker_daemon_ready() {
            return Ok(());
        }
        if attempt == max_attempts {
            break;
        }
        thread::sleep(sleep);
    }
    Err("Docker 守护进程未在预期时间内就绪。请手动打开 Docker Desktop 后重试。".into())
}

pub fn install_docker(kind: OsKind, app: Option<&tauri::AppHandle>) -> Result<(), String> {
    match kind {
        OsKind::MacOs => install_docker_macos(),
        OsKind::Linux => install_docker_linux(),
        OsKind::Windows => install_docker_windows(app),
    }
}

fn install_docker_macos() -> Result<(), String> {
    if !command_exists("brew") {
        return Err(
            "未找到 Homebrew，无法自动安装 Docker。\n请安装 Homebrew (https://brew.sh) 或从官网安装 Docker Desktop。"
                .into(),
        );
    }

    run_checked(
        Command::new("brew").args(["install", "--cask", "docker"]),
        "Homebrew 安装 Docker Desktop 失败",
    )?;

    let _ = Command::new("open").args(["-a", "Docker"]).status();
    thread::sleep(Duration::from_secs(3));
    Ok(())
}

fn install_docker_linux() -> Result<(), String> {
    if !command_exists("curl") {
        return Err("需要 curl 来安装 Docker，请先安装 curl。".into());
    }

    run_checked(
        Command::new("sh")
            .arg("-c")
            .arg("curl -fsSL https://get.docker.com | sh"),
        "Linux Docker 安装脚本执行失败",
    )?;

    if command_exists("systemctl") {
        let _ = Command::new("sudo")
            .args(["systemctl", "enable", "--now", "docker"])
            .status();
    }

    Ok(())
}

fn install_docker_windows(app: Option<&tauri::AppHandle>) -> Result<(), String> {
    let script = resolve_windows_install_script(app)?;

    run_checked(
        Command::new("powershell")
            .args([
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                &script.to_string_lossy(),
            ]),
        "Windows Docker 安装失败",
    )
}

fn command_exists(name: &str) -> bool {
    if cfg!(windows) {
        Command::new("where")
            .arg(name)
            .output()
            .map(|output| output.status.success())
            .unwrap_or(false)
    } else {
        Command::new("sh")
            .arg("-c")
            .arg(format!("command -v {name}"))
            .output()
            .map(|output| output.status.success())
            .unwrap_or(false)
    }
}

fn run_checked(command: &mut Command, context: &str) -> Result<(), String> {
    let output = command
        .output()
        .map_err(|error| format!("{context}: {error}"))?;

    if output.status.success() {
        return Ok(());
    }

    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    Err(format!("{context}\n{stdout}\n{stderr}"))
}

fn resolve_windows_install_script(app: Option<&tauri::AppHandle>) -> Result<std::path::PathBuf, String> {
    if let Some(app) = app {
        let bundled = app
            .path()
            .resolve(
                "stack/scripts/docker-env/install-docker-windows.ps1",
                tauri::path::BaseDirectory::Resource,
            );
        if let Ok(path) = bundled {
            if path.is_file() {
                return Ok(path);
            }
        }
    }

    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir
        .join("../../scripts/docker-env/install-docker-windows.ps1")
        .canonicalize()
        .map_err(|_| "找不到 Windows Docker 安装脚本".to_string())
}
