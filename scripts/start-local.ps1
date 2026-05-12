param(
    [switch]$WithOllama,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not available on PATH."
}

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker Compose is not available. Install Docker Desktop with Compose v2."
}

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}

if ($WithOllama) {
    docker compose --profile ollama up --build -d
} else {
    docker compose up --build -d
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker Compose failed to start the app stack."
}

Write-Host "Jarvis is starting."
Write-Host "Web: http://localhost:3000"
Write-Host "API: http://localhost:8000"

if (-not $NoBrowser) {
    # Give containers a short head start before opening the web UI.
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:3000"
}
