#!/usr/bin/env bash
# setup_autostart.sh — Configures Raspberry Pi to automatically start PookalBot on power-on with mDNS

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME="$(whoami)"

echo "========================================================="
echo "   🌺 Setting up PookalBot Auto-Start on Boot (systemd)  "
echo "========================================================="

# 1. Set mDNS Hostname to 'pookal'
echo "[1/3] Setting local mDNS hostname to 'pookal'..."
sudo hostnamectl set-hostname pookal
sudo systemctl restart avahi-daemon || true

# 2. Create systemd Service Unit
SERVICE_FILE="/etc/systemd/system/pookalbot.service"
echo "[2/3] Generating systemd service at $SERVICE_FILE..."

sudo bash -c "cat <<EOF > $SERVICE_FILE
[Unit]
Description=PookalBot Autonomous AI Robot Web Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$DIR
Environment=PATH=$DIR/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=PYTHONUNBUFFERED=1
ExecStart=$DIR/.venv/bin/python $DIR/run_all.py --esp32 192.168.10.14
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF"

# 3. Reload systemd & Enable Service
echo "[3/3] Enabling and starting pookalbot.service..."
sudo systemctl daemon-reload
sudo systemctl enable pookalbot.service
sudo systemctl restart pookalbot.service

echo ""
echo "========================================================="
echo "✅ Auto-Start Successfully Configured!"
echo "   Whenever the Raspberry Pi powers on, it will automatically:"
echo "   1. Host the Web App at: http://pookal.local:8000"
echo "   2. Provide live camera streaming at /api/camera/stream"
echo "   3. Connect to ESP32 on WiFi"
echo ""
echo "Commands to manage:"
echo "   sudo systemctl status pookalbot"
echo "   sudo systemctl restart pookalbot"
echo "   sudo systemctl stop pookalbot"
echo "========================================================="
