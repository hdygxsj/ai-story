use std::path::Path;
use std::process::{Command, Stdio};
use std::thread;
use std::time::Duration;

pub fn compose_up(stack_dir: &Path) -> Result<(), String> {
    run_compose(stack_dir, ["up", "-d", "--build"])
}

pub fn compose_down(stack_dir: &Path) -> Result<(), String> {
    run_compose(stack_dir, ["down"])
}

fn run_compose(stack_dir: &Path, args: impl IntoIterator<Item = &'static str>) -> Result<(), String> {
    let mut command = Command::new("docker");
    command
        .current_dir(stack_dir)
        .arg("compose")
        .args(["--env-file", ".env"])
        .args(args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let output = command
        .output()
        .map_err(|error| format!("无法执行 docker compose: {error}"))?;

    if output.status.success() {
        return Ok(());
    }

    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    Err(format!("docker compose 失败\n{stdout}\n{stderr}"))
}

pub fn wait_for_health(api_port: u16, max_attempts: u32) -> Result<(), String> {
    let url = format!("http://127.0.0.1:{api_port}/health");
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(3))
        .build()
        .map_err(|error| error.to_string())?;

    for attempt in 1..=max_attempts {
        if let Ok(response) = client.get(&url).send() {
            if response.status().is_success() {
                return Ok(());
            }
        }

        if attempt == max_attempts {
            break;
        }
        thread::sleep(Duration::from_secs(2));
    }

    Err(format!(
        "服务未在预期时间内就绪 ({url})。请检查 Docker 日志后重试。"
    ))
}
