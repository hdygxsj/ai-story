#Requires -Version 5.1
$ErrorActionPreference = "Stop"

function Write-Info($Message) {
    Write-Host "[INFO] $Message"
}

function Write-Warn($Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Test-DockerDaemon {
    try {
        docker info *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Start-DockerDesktop {
    $paths = @(
        "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe",
        "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe"
    )
    foreach ($path in $paths) {
        if (Test-Path $path) {
            Write-Info "Starting Docker Desktop..."
            Start-Process -FilePath $path | Out-Null
            return $true
        }
    }
    return $false
}

function Install-DockerDesktop {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info "Installing Docker Desktop via winget..."
        winget install -e --id Docker.DockerDesktop `
            --accept-package-agreements `
            --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            throw "winget install failed with exit code $LASTEXITCODE"
        }
        return
    }

    if (Get-Command choco -ErrorAction SilentlyContinue) {
        Write-Info "Installing Docker Desktop via Chocolatey..."
        choco install docker-desktop -y
        if ($LASTEXITCODE -ne 0) {
            throw "choco install failed with exit code $LASTEXITCODE"
        }
        return
    }

    throw @"
未找到 winget 或 Chocolatey，无法自动安装 Docker Desktop。
请手动安装: https://docs.docker.com/desktop/setup/install/windows-install/
安装后重新启动 AI Story。
"@
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
    if (Test-DockerDaemon) {
        Write-Info "Docker is already running."
        exit 0
    }
    if (-not (Start-DockerDesktop)) {
        Write-Warn "Docker CLI found but daemon is not running and Docker Desktop was not located."
    }
} else {
    Install-DockerDesktop
    Start-Sleep -Seconds 5
    if (-not (Start-DockerDesktop)) {
        Write-Warn "Docker Desktop installed but executable not found yet. Please start it manually."
    }
}

Write-Info "Waiting for Docker daemon (up to 3 minutes)..."
$attempt = 0
while (-not (Test-DockerDaemon)) {
    $attempt++
    if ($attempt -ge 90) {
        throw "Docker daemon did not become ready in time. Open Docker Desktop manually, then retry."
    }
    Start-Sleep -Seconds 2
}

Write-Info "Docker is ready."
