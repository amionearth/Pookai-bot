"""
run_all.py — PookalBot Master Orchestrator (One-Command Launcher)

Launches and manages all PookalBot components concurrently:
  1. FastAPI Web Server (UI + Cloudflare Workers AI + Vectorizer + Camera Stream)
  2. ESP32 TFT Display Video Streamer (Kathakali GIF on port 9001)
  3. Camera & Hardware Link Monitor

Usage:
    python run_all.py [--esp32 <ESP32_IP>] [--port 8000]

Example:
    python run_all.py --esp32 192.168.10.14
"""

import sys
import os
import time
import socket
import signal
import argparse
import subprocess
import threading
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = ROOT_DIR / "assets"
PI_DIR = ROOT_DIR / "pi"

# Global process tracking
processes = []
stop_event = threading.Event()


def get_local_ip() -> str:
    """Finds the local IP of the Raspberry Pi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def print_banner(pi_ip: str, esp32_ip: str = None):
    print("\n" + "=" * 65)
    print("       🌺  POOKALBOT — AUTONOMOUS ROBOT ORCHESTRATOR  🌺      ")
    print("=" * 65)
    print(f"  🌐 Web Dashboard:   http://{pi_ip}:8000")
    print(f"  🌐 mDNS Address:    http://pookal.local:8000")
    print(f"  📷 Camera Stream:   http://{pi_ip}:8000/api/camera/stream")
    if esp32_ip:
        print(f"  🤖 ESP32 Robot:     {esp32_ip} (Drive: 9000, TFT: 9001)")
    else:
        print("  🤖 ESP32 Robot:     Not specified (TFT streamer waiting)")
    
    cf_token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if cf_token:
        print("  ⚡ AI Provider:     Cloudflare Workers AI (Active)")
    else:
        print("  ⚡ AI Provider:     Pollinations.ai (Free Fallback Active)")
    print("=" * 65)
    print("  Press Ctrl+C at any time to stop all services.\n")


def run_web_server(port: int = 8000):
    """Starts the Uvicorn web server."""
    cmd = [
        sys.executable, "-m", "uvicorn",
        "server.main:app",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--log-level", "info"
    ]
    p = subprocess.Popen(cmd, cwd=str(ROOT_DIR))
    processes.append(p)
    return p


def run_tft_streamer(esp32_ip: str, gif_path: Path):
    """Runs the GIF streamer to the ESP32 in a background thread."""
    if not esp32_ip:
        return

    from pi.stream_gif import stream
    
    def _worker():
        while not stop_event.is_set():
            try:
                stream(esp32_ip, gif_path, forced_fps=15, fit_mode="contain", port=9001)
            except Exception as e:
                if not stop_event.is_set():
                    time.sleep(2)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


def signal_handler(sig, frame):
    print("\n\n🛑 Shutting down all PookalBot services...")
    stop_event.set()
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=2)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    print("✅ All services stopped safely. Bye!\n")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="PookalBot All-in-One Master Orchestrator")
    parser.add_argument("--esp32", help="ESP32 IP address (e.g. 192.168.10.14)", default=None)
    parser.add_argument("--port", type=int, default=8000, help="Web server port (default: 8000)")
    parser.add_argument("--gif", default=None, help="Path to custom GIF file")

    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    pi_ip = get_local_ip()

    # Find GIF file
    from pi.stream_gif import find_default_gif
    gif_file = Path(args.gif) if args.gif else find_default_gif(ROOT_DIR)

    # Print Dashboard Banner
    print_banner(pi_ip, args.esp32)

    # 1. Start Web Server
    print("🚀 [1/2] Starting FastAPI Web Server...")
    run_web_server(args.port)
    time.sleep(1.5)

    # 2. Start TFT Streamer (if ESP32 IP provided)
    if args.esp32:
        print(f"📺 [2/2] Starting TFT Video Streamer -> {args.esp32}:9001 ({gif_file.name})...")
        run_tft_streamer(args.esp32, gif_file)
    else:
        print("💡 Tip: Pass --esp32 <IP> to stream the Kathakali GIF to your TFT screen.")

    print("\n✅ PookalBot is LIVE! Open the link above in your browser.\n")

    # Keep master process alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
