#!/usr/bin/env bash
# start_server.sh — Run PookalBot Web Server on Raspberry Pi with local mDNS

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo "======================================================="
echo "   🌺 PookalBot Web Server — Onam Hackathon Edition"
echo "======================================================="

# Optional: Cloudflare Workers AI environment check
if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
    echo "💡 [Notice] CLOUDFLARE_API_TOKEN is not set in environment."
    echo "   Using free Pollinations.ai fallback (no key needed)."
    echo "   To use Cloudflare Workers AI, run:"
    echo "     export CLOUDFLARE_ACCOUNT_ID='your_account_id'"
    echo "     export CLOUDFLARE_API_TOKEN='your_api_token'"
    echo ""
else
    echo "⚡ [Cloudflare Workers AI] Enabled with Account ID: ${CLOUDFLARE_ACCOUNT_ID:-configured}"
fi

PI_IP=$(hostname -I | awk '{print $1}')
echo "🌐 Local Access URLs:"
echo "   → http://${PI_IP}:8000"
echo "   → http://raspberrypi.local:8000"
echo "   → http://pookal.local:8000"
echo ""
echo "Starting FastAPI server on 0.0.0.0:8000..."
echo "======================================================="

exec uvicorn server.main:app --host 0.0.0.0 --port 8000
