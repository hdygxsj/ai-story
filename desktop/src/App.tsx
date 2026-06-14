import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import { useEffect, useMemo, useState } from "react";
import "./App.css";

type SetupStatus = "running" | "done" | "error";

interface SetupProgressEvent {
  step: string;
  message: string;
  status: SetupStatus;
}

interface AppSettings {
  stopContainersOnExit: boolean;
}

interface StepItem {
  id: string;
  label: string;
}

const STEPS: StepItem[] = [
  { id: "detect-os", label: "检测操作系统" },
  { id: "docker-cli", label: "检测 Docker" },
  { id: "docker-install", label: "安装 Docker" },
  { id: "docker-daemon", label: "等待 Docker 就绪" },
  { id: "compose", label: "检测 Compose" },
  { id: "stack", label: "准备运行目录" },
  { id: "services", label: "启动服务" },
  { id: "health", label: "健康检查" },
  { id: "ready", label: "打开应用" },
];

function stepRank(stepId: string): number {
  const index = STEPS.findIndex((step) => step.id === stepId);
  return index === -1 ? -1 : index;
}

function App() {
  const [messages, setMessages] = useState<Record<string, string>>({});
  const [statuses, setStatuses] = useState<Record<string, SetupStatus>>({});
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [stopOnExit, setStopOnExit] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(true);

  useEffect(() => {
    void invoke<AppSettings>("get_app_settings")
      .then((settings) => {
        setStopOnExit(settings.stopContainersOnExit);
      })
      .finally(() => {
        setSettingsLoading(false);
      });
  }, []);

  useEffect(() => {
    let cancelled = false;
    let unlisten: (() => void) | undefined;

    async function bootstrap() {
      unlisten = await listen<SetupProgressEvent>("setup-progress", (event) => {
        if (cancelled) {
          return;
        }

        const payload = event.payload;
        setMessages((current) => ({ ...current, [payload.step]: payload.message }));
        setStatuses((current) => ({ ...current, [payload.step]: payload.status }));

        if (payload.status === "error") {
          setError(payload.message);
        }
      });

      if (!cancelled) {
        await invoke("start_environment_setup");
      }
    }

    void bootstrap().catch((setupError) => {
      setError(String(setupError));
    });

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);

  const activeStep = useMemo(() => {
    let latest = "";
    let latestRank = -1;
    for (const step of STEPS) {
      const status = statuses[step.id];
      if (!status) {
        continue;
      }
      const rank = stepRank(step.id);
      if (rank >= latestRank) {
        latest = step.id;
        latestRank = rank;
      }
    }
    return latest;
  }, [statuses]);

  async function retrySetup() {
    setRetrying(true);
    setError(null);
    setMessages({});
    setStatuses({});
    try {
      await invoke("start_environment_setup");
    } catch (setupError) {
      setError(String(setupError));
    } finally {
      setRetrying(false);
    }
  }

  async function handleStopOnExitChange(checked: boolean) {
    setStopOnExit(checked);
    try {
      const settings = await invoke<AppSettings>("set_stop_containers_on_exit", { enabled: checked });
      setStopOnExit(settings.stopContainersOnExit);
    } catch (settingsError) {
      setError(String(settingsError));
    }
  }

  return (
    <main className="setup-shell">
      <header className="setup-header">
        <h1>AI Story</h1>
        <p>正在检测环境并启动本地服务，首次运行可能需要几分钟。</p>
      </header>

      <ol className="setup-steps">
        {STEPS.map((step) => {
          const status = statuses[step.id];
          const message = messages[step.id];
          const isActive = step.id === activeStep && status === "running";
          const isDone = status === "done";
          const isError = status === "error";

          return (
            <li
              key={step.id}
              className={[
                "setup-step",
                isActive ? "is-active" : "",
                isDone ? "is-done" : "",
                isError ? "is-error" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <div className="setup-step-title">{step.label}</div>
              {message ? <div className="setup-step-message">{message}</div> : null}
            </li>
          );
        })}
      </ol>

      {error ? (
        <section className="setup-error">
          <p>{error}</p>
          <button type="button" onClick={retrySetup} disabled={retrying}>
            {retrying ? "重试中..." : "重试"}
          </button>
        </section>
      ) : null}

      <footer className="setup-footer">
        <label className="setup-option">
          <input
            type="checkbox"
            checked={stopOnExit}
            disabled={settingsLoading}
            onChange={(event) => void handleStopOnExitChange(event.target.checked)}
          />
          <span>退出应用时停止 Docker 容器</span>
        </label>
        <p>关闭窗口后应用会缩到系统托盘。需要 Docker，首次运行会自动检测并尝试安装。</p>
      </footer>
    </main>
  );
}

export default App;
