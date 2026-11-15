#!/usr/bin/env bash
# Install gpt-oss-server as a systemd --user unit for this clone.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$UNIT_DIR" "$HOME/ai/logs"
cat >"$UNIT_DIR/gpt-oss-server.service" <<EOF
[Unit]
Description=Local GPT-OSS 20B CUDA inference (repo-aligned OpenAI API)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$REPO
Environment=GPT_OSS_MODEL_DIR=$HOME/ai/models/gpt-oss-20b
Environment=LLAMA_ROOT=$HOME/ai/llama.cpp
Environment=GPT_OSS_GPU_LAYERS=24
Environment=GPT_OSS_CTX=16384
Environment=GPT_OSS_HOST=127.0.0.1
Environment=GPT_OSS_PORT=8080
ExecStart=$REPO/local-ai/gpt-oss-server
Restart=on-failure
RestartSec=10
TimeoutStartSec=600
TimeoutStopSec=45
StandardOutput=append:$HOME/ai/logs/gpt-oss-server.log
StandardError=append:$HOME/ai/logs/gpt-oss-server.log

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable gpt-oss-server.service
echo "Installed $UNIT_DIR/gpt-oss-server.service"
echo "Start with: systemctl --user start gpt-oss-server"
