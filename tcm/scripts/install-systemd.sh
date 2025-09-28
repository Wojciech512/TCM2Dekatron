#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="tcm-compose"
COMPOSE_DIR="/opt/tcm"

install_unit() {
  cat <<'UNIT' | sudo tee /etc/systemd/system/${SERVICE_NAME}.service >/dev/null
[Unit]
Description=TCM 2.0 Docker Compose stack
Requires=docker.service
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=true
WorkingDirectory=${COMPOSE_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT
}

main() {
  sudo mkdir -p "${COMPOSE_DIR}"
  sudo cp -r tcm "${COMPOSE_DIR}/"
  sudo install -m 0644 compose.yaml "${COMPOSE_DIR}/"
  install_unit
  sudo systemctl daemon-reload
  sudo systemctl enable --now ${SERVICE_NAME}.service
}

main "$@"
