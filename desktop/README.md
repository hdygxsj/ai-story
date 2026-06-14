# AI Story Desktop

跨平台桌面壳（macOS / Linux / Windows），自动检测环境、安装 Docker，并启动现有 Docker Compose 栈。

## 前置条件

- Node.js 20.19+ 或 22.12+（构建桌面壳）
- Rust stable（`rustup`）
- 开发模式下可直接使用仓库根目录的 `docker-compose.yml`

## 开发运行

```bash
cd desktop
npm install
npm run tauri:dev
```

开发模式会：

1. 显示环境检测与启动进度界面
2. 使用**仓库根目录**作为 Compose 工作目录（无需先打包 stack）
3. 自动执行 `docker compose up -d --build`
4. 健康检查通过后打开 `http://127.0.0.1:5173`

## 构建安装包

```bash
cd desktop
npm install
npm run tauri:build
```

构建前会运行 `scripts/prepare-desktop-stack.mjs`，将 `docker-compose.yml`、前后端源码等复制到 `src-tauri/resources/stack/`，并打入安装包。

产物位置：

- macOS: `desktop/src-tauri/target/release/bundle/dmg/`
- Windows: `desktop/src-tauri/target/release/bundle/msi/` 或 `nsis/`
- Linux: `desktop/src-tauri/target/release/bundle/deb/` 或 `appimage/`

## 环境检测与 Docker 自动安装

| 平台 | 检测 | 自动安装 |
|------|------|----------|
| macOS | `docker --version` / `docker info` | Homebrew: `brew install --cask docker` |
| Linux | 同上 | get.docker.com 脚本 |
| Windows | 同上 | winget / Chocolatey 安装 Docker Desktop |

Windows 脚本：`scripts/docker-env/install-docker-windows.ps1`

若自动安装失败，界面会显示错误并提供**重试**；Windows 用户也可手动安装 [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)（需 WSL2）。

## 数据目录

Release 模式首次运行会将内置 stack 复制到：

- macOS: `~/Library/Application Support/com.aistory.desktop/stack/`
- Windows: `%APPDATA%\com.aistory.desktop\stack\`
- Linux: `~/.local/share/com.aistory.desktop/stack/`

用户数据（Postgres / Milvus / Ollama 卷）仍由 Docker 管理，与命令行 `docker compose` 启动时相同。

## 系统托盘与退出行为

- 启动后会在系统托盘显示 **AI Story** 图标
- 左键点击托盘图标：打开/聚焦主窗口
- 托盘菜单：**打开**、**停止服务**、**退出时停止容器**（可勾选）、**退出**
- 关闭主窗口时会缩到托盘，不会退出应用
- 启动页底部也可勾选「退出应用时停止 Docker 容器」；设置会保存到本地

## CI 构建（Windows 安装包）

GitHub Actions 工作流 [`.github/workflows/desktop-windows.yml`](../.github/workflows/desktop-windows.yml) 会在 `desktop/` 或 stack 相关文件变更时构建 Windows NSIS 安装包。

手动触发：

```bash
gh workflow run desktop-windows.yml
```

构建完成后在 Actions Artifacts 中下载 `ai-story-windows-nsis`。

## 常用命令

```bash
# 仅准备 stack 资源（构建前）
npm run prepare:stack

# 前端单独开发
npm run dev

# 停止服务（可在 Rust 命令中调用 stop_services）
```

## 架构说明

详见 [docs/superpowers/specs/2026-06-14-desktop-docker-shell-design.md](../docs/superpowers/specs/2026-06-14-desktop-docker-shell-design.md)
