#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

with_ollama="false"
if [[ "${1:-}" == "--with-ollama" ]]; then
  with_ollama="true"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not available on PATH." >&2
  exit 1
fi

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

if [[ "$with_ollama" == "true" ]]; then
  docker compose --profile ollama up --build -d
else
  docker compose up --build -d
fi

echo "Jarvis is starting."
echo "Web: http://localhost:3000"
echo "API: http://localhost:8000"
