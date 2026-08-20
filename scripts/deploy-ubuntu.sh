#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER="${SUDO_USER:-$USER}"
SERVICE_NAME="ontopilot"
WEB_ROOT="/var/www/$SERVICE_NAME"

if [[ "$EUID" -eq 0 ]]; then
  echo "Run this script as the deployment user, without sudo." >&2
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required" >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y curl ca-certificates nginx

if ! command -v node >/dev/null 2>&1 || [[ "$(node -p 'Number(process.versions.node.split(`.`)[0])')" -lt 18 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

cd "$ROOT_DIR"
[[ -f config/settings.yaml ]] || cp config/settings.yaml.example config/settings.yaml
[[ -f .env ]] || cp .env.example .env

uv sync --frozen --no-dev
npm --prefix frontend ci
npm --prefix frontend run build

sudo install -d -m 755 "$WEB_ROOT"
sudo cp -R frontend/dist/. "$WEB_ROOT/"
sudo chown -R www-data:www-data "$WEB_ROOT"

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

sudo tee "/etc/nginx/sites-available/$SERVICE_NAME" >/dev/null <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    root $WEB_ROOT;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8100;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

sudo ln -sfn "/etc/nginx/sites-available/$SERVICE_NAME" "/etc/nginx/sites-enabled/$SERVICE_NAME"
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME" nginx
sudo systemctl restart "$SERVICE_NAME" nginx

echo "OntoPilot deployed. Open http://$(hostname -I | awk '{print $1}')"
