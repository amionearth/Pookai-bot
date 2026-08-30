#!/usr/bin/env bash
# launch.sh — One-click launcher for PookalBot on Raspberry Pi 5

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Set Cloudflare Workers AI credentials (uncomment and fill if needed)
# export CLOUDFLARE_ACCOUNT_ID="your_account_id_here"
# export CLOUDFLARE_API_TOKEN="your_api_token_here"

# Default ESP32 IP if known (can be passed as $1)
ESP32_IP="${1:-192.168.10.14}"

echo "Starting PookalBot with ESP32 IP: $ESP32_IP..."
python run_all.py --esp32 "$ESP32_IP"
