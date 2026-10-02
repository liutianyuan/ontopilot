#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER="${SUDO_USER:-$USER}"
SERVICE_NAME="ontopilot"

if [[ "$EUID" -eq 0 ]]; then
  echo "Run this script as the deployment user, without sudo." >&2
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required" >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y curl ca-certificates

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

cd "$ROOT_DIR"
[[ -f config/settings.yaml ]] || cp config/settings.yaml.example config/settings.yaml
[[ -f .env ]] || cp .env.example .env

uv sync --frozen --no-dev

UV_BIN="$(command -v uv)"
sudo tee "/etc/systemd/system/$SERVICE_NAME.service" >/dev/null <<EOF
[Unit]
Description=OntoPilot API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$ROOT_DIR
EnvironmentFile=-$ROOT_DIR/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=$UV_BIN run uvicorn api.main:app --host 127.0.0.1 --port 8100
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "Agent runtime deployed at http://127.0.0.1:8100. Configure nano-ontoprompt frontend to proxy /api to this service."
