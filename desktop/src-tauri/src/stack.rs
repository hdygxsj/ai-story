use std::fs;
use std::path::{Path, PathBuf};

use tauri::Manager;

const STACK_VERSION: &str = "1";

pub fn resolve_stack_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    if cfg!(debug_assertions) {
        let dev_root = dev_repo_root()?;
        if dev_root.join("docker-compose.yml").is_file() {
            return Ok(dev_root);
        }
    }

    let app_data = app
        .path()
        .app_data_dir()
        .map_err(|error| error.to_string())?;
    let target = app_data.join("stack");
    let version_file = target.join(".stack-version");

    if should_refresh_stack(&target, &version_file)? {
        prepare_stack_from_bundle(app, &target)?;
        fs::write(&version_file, STACK_VERSION).map_err(|error| error.to_string())?;
    }

    Ok(target)
}

fn dev_repo_root() -> Result<PathBuf, String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir
        .join("../..")
        .canonicalize()
        .map_err(|error| format!("无法定位开发环境项目根目录: {error}"))
}

fn should_refresh_stack(target: &Path, version_file: &Path) -> Result<bool, String> {
    if !target.join("docker-compose.yml").is_file() {
        return Ok(true);
    }

    let current = fs::read_to_string(version_file).unwrap_or_default();
    Ok(current.trim() != STACK_VERSION)
}

fn prepare_stack_from_bundle(app: &tauri::AppHandle, target: &Path) -> Result<(), String> {
    let bundled = app
        .path()
        .resolve("stack", tauri::path::BaseDirectory::Resource)
        .map_err(|error| error.to_string())?;

    if !bundled.join("docker-compose.yml").is_file() {
        return Err(
            "未找到内置 stack 资源。请先运行 scripts/prepare-desktop-stack.sh 再构建桌面应用。"
                .into(),
        );
    }

    if target.exists() {
        fs::remove_dir_all(target).map_err(|error| error.to_string())?;
    }

    copy_dir_recursive(&bundled, target)?;
    ensure_env_file(target)?;
    Ok(())
}

pub fn ensure_env_file(stack_dir: &Path) -> Result<(), String> {
    let env_path = stack_dir.join(".env");
    if env_path.is_file() {
        return Ok(());
    }

    let example_path = stack_dir.join(".env.example");
    if !example_path.is_file() {
        return Err("缺少 .env.example，无法初始化环境。".into());
    }

    fs::copy(&example_path, &env_path).map_err(|error| error.to_string())?;
    Ok(())
}

fn copy_dir_recursive(source: &Path, target: &Path) -> Result<(), String> {
    fs::create_dir_all(target).map_err(|error| error.to_string())?;

    for entry in fs::read_dir(source).map_err(|error| error.to_string())? {
        let entry = entry.map_err(|error| error.to_string())?;
        let file_type = entry.file_type().map_err(|error| error.to_string())?;
        let source_path = entry.path();
        let target_path = target.join(entry.file_name());

        if file_type.is_dir() {
            copy_dir_recursive(&source_path, &target_path)?;
        } else {
            if let Some(parent) = target_path.parent() {
                fs::create_dir_all(parent).map_err(|error| error.to_string())?;
            }
            fs::copy(&source_path, &target_path).map_err(|error| error.to_string())?;
        }
    }

    Ok(())
}

pub fn read_web_port(stack_dir: &Path) -> u16 {
    read_env_value(stack_dir, "WEB_PORT").unwrap_or(5173)
}

pub fn read_api_port(stack_dir: &Path) -> u16 {
    read_env_value(stack_dir, "API_PORT").unwrap_or(8000)
}

fn read_env_value(stack_dir: &Path, key: &str) -> Option<u16> {
    let env_path = stack_dir.join(".env");
    let content = fs::read_to_string(env_path).ok()?;
    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('#') || !trimmed.contains('=') {
            continue;
        }
        let (name, value) = trimmed.split_once('=')?;
        if name.trim() == key {
            return value.trim().parse().ok();
        }
    }
    None
}
