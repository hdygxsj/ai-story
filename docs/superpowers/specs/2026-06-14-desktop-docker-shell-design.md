# Desktop App (Docker Shell) Design

Date: 2026-06-14

## Overview

Ship AI Story as a cross-platform desktop app (macOS, Linux, Windows) that wraps the existing Docker Compose stack. The desktop shell handles environment detection, optional Docker auto-install, stack startup, and opens the web UI in a native window.

## Goals

- One-click desktop experience for non-technical users
- Environment checks before starting services
- Auto-install Docker when missing (macOS via Homebrew, Linux via get.docker.com, Windows via winget)
- Support Windows, macOS, and Linux
- Reuse existing `docker-compose.yml` without backend changes

## Non-Goals

- Bundling Postgres/Milvus/Ollama without Docker
- Pre-pulling Docker images in the installer (first launch still pulls/builds)
- Windows Store / macOS App Store distribution in v1

## Architecture

```
┌─────────────────────────────────────┐
│ Tauri shell (setup UI → main window) │
├─────────────────────────────────────┤
│ Rust: env check, docker install,     │
│       stack dir, compose lifecycle   │
├─────────────────────────────────────┤
│ Docker Compose (existing stack)      │
│ postgres / milvus / ollama / api / web│
└─────────────────────────────────────┘
```

## Stack directory

| Mode | Location |
|------|----------|
| Dev (`tauri dev`) | Repository root |
| Release | Copy bundled `resources/stack/` → app data dir on first run |

Build pipeline runs `scripts/prepare-desktop-stack.sh` before `tauri build`.

## Setup flow

1. Detect OS
2. Check Docker CLI installed → offer auto-install if missing
3. Wait for Docker daemon
4. Verify Compose V2
5. Prepare `.env` from template
6. `docker compose up -d --build`
7. Poll `http://localhost:8000/health`
8. Open main window at `http://localhost:5173`

Progress streamed to UI via Tauri events.

## Platform notes

- **macOS**: `brew install --cask docker`, open Docker Desktop, wait for daemon
- **Linux**: get.docker.com script; may require user re-login for docker group
- **Windows**: `winget install Docker.DockerDesktop`; WSL2 may be required; manual fallback link if winget unavailable

## Security

- Setup UI is local-only; main window loads localhost
- No elevation baked in; Docker installers may prompt for admin
