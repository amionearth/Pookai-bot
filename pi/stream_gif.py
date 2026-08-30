"""
stream_gif.py — High-Speed, Zero-Glitch GIF / Image Streamer for ESP32 1.8" TFT Display

Streams Kathakali animations and GIFs from Pi 5 to ESP32 TFT Display over TCP port 9001.
"""

import sys
import os
import time
import socket
import argparse
from pathlib import Path
from PIL import Image, ImageSequence, ImageDraw
import numpy as np

SCREEN_W = 160
SCREEN_H = 128
FRAME_BYTES = SCREEN_W * SCREEN_H * 2  # 40,960 bytes
SYNC_HEADER = bytes([0xAA, 0x55, 0xAA, 0x55])
DISPLAY_PORT = 9001


def generate_sample_eyes_gif(output_path: Path):
    """Generates a clean animated Kathakali eyes GIF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    num_frames = 24

    for i in range(num_frames):
        img = Image.new("RGB", (SCREEN_W, SCREEN_H), (10, 10, 20))
        draw = ImageDraw.Draw(img)

        draw.text((36, 10), "POOKALBOT", fill=(255, 215, 0))

        t = (i / num_frames) * 2 * np.pi
        pupil_x = int(np.sin(t) * 8)

        # Left eye
        draw.rounded_rectangle([28, 45, 68, 75], radius=10, fill=(255, 255, 255), outline=(255, 180, 0), width=2)
        draw.ellipse([48 + pupil_x - 5, 60 - 5, 48 + pupil_x + 5, 60 + 5], fill=(0, 0, 0))
        draw.ellipse([48 + pupil_x - 2, 60 - 2, 48 + pupil_x, 60], fill=(255, 255, 255))

        # Right eye
        draw.rounded_rectangle([92, 45, 132, 75], radius=10, fill=(255, 255, 255), outline=(255, 180, 0), width=2)
        draw.ellipse([112 + pupil_x - 5, 60 - 5, 112 + pupil_x + 5, 60 + 5], fill=(0, 0, 0))
        draw.ellipse([112 + pupil_x - 2, 60 - 2, 112 + pupil_x, 60], fill=(255, 255, 255))

        draw.text((44, 105), "Pi 5 Stream", fill=(0, 255, 180))
        frames.append(img)

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=65,
        loop=0
    )
    print(f"✅ Generated fresh animated GIF at: {output_path}")


def resize_to_display(img: Image.Image, fit_mode: str = "contain") -> Image.Image:
    """
    Fits image to exact 160x128 display dimensions.
    
    fit_mode:
      - 'contain' (default): Scale down so the entire image fits inside without ANY cropping.
      - 'stretch': Stretches to fill entire 160x128 area.
      - 'crop': Zooms and center-crops to fill 160x128.
    """
    if fit_mode == "stretch":
        return img.resize((SCREEN_W, SCREEN_H), Image.Resampling.LANCZOS)

    if fit_mode == "crop":
        img_ratio = img.width / img.height
        target_ratio = SCREEN_W / SCREEN_H
        if img_ratio > target_ratio:
            new_h = SCREEN_H
            new_w = int(new_h * img_ratio)
        else:
            new_w = SCREEN_W
            new_h = int(new_w / img_ratio)
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - SCREEN_W) // 2
        top = (new_h - SCREEN_H) // 2
        return resized.crop((left, top, left + SCREEN_W, top + SCREEN_H))

    # Default 'contain' mode: 100% of the image is visible inside the screen!
    scale = min(SCREEN_W / img.width, SCREEN_H / img.height)
    new_w = max(1, int(img.width * scale))
    new_h = max(1, int(img.height * scale))

    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Place in center of solid black 160x128 canvas
    canvas = Image.new("RGB", (SCREEN_W, SCREEN_H), (0, 0, 0))
    offset_x = (SCREEN_W - new_w) // 2
    offset_y = (SCREEN_H - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))
    return canvas


def image_to_rgb565(img: Image.Image) -> bytes:
    """Converts PIL RGB Image to Big-Endian RGB565 byte array."""
    arr = np.array(img, dtype=np.uint16)
    r = (arr[:, :, 0] >> 3) << 11
    g = (arr[:, :, 1] >> 2) << 5
    b = (arr[:, :, 2] >> 3)
    rgb565 = (r | g | b).astype(">u2")
    return rgb565.tobytes()


def find_default_gif(project_root: Path) -> Path:
    """Finds kathakaliright (1).gif or the first valid GIF in assets folder."""
    assets_dir = project_root / "assets"
    
    candidates = [
        assets_dir / "kathakaliright (1).gif",
        assets_dir / "kathakaliright(1).gif",
        assets_dir / "kathakaliright.gif",
        assets_dir / "eyes.gif",
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 100:
            return c

    if assets_dir.exists():
        for p in assets_dir.glob("*.gif"):
            if p.stat().st_size > 100:
                return p

    return assets_dir / "eyes.gif"


def load_media_frames(file_path: Path, fit_mode: str = "contain"):
    """Loads GIF or static image and returns processed (raw_bytes, delay_sec) frames."""
    if not file_path.exists() or file_path.stat().st_size < 100:
        print(f"[Notice] '{file_path}' is missing or empty. Generating sample GIF...")
        generate_sample_eyes_gif(file_path)

    try:
        img = Image.open(file_path)
    except Exception as e:
        print(f"[Warning] Could not open '{file_path}' ({e}). Re-generating sample GIF...")
        generate_sample_eyes_gif(file_path)
        img = Image.open(file_path)

    is_animated = getattr(img, "is_animated", False)
    frames_list = []

    print(f"🖼️  Loading '{file_path.name}' (Fit mode: {fit_mode})...")
    if is_animated:
        canvas = Image.new("RGBA", img.size, (0, 0, 0, 255))
        for frame in ImageSequence.Iterator(img):
            duration_ms = frame.info.get("duration", 65)
            if duration_ms < 10:
                duration_ms = 65

            frame_rgba = frame.convert("RGBA")
            canvas.paste(frame_rgba, (0, 0), frame_rgba)

            fitted = resize_to_display(canvas.convert("RGB"), fit_mode=fit_mode)
            rgb_bytes = image_to_rgb565(fitted)
            frames_list.append((rgb_bytes, duration_ms / 1000.0))
    else:
        fitted = resize_to_display(img.convert("RGB"), fit_mode=fit_mode)
        rgb_bytes = image_to_rgb565(fitted)
        frames_list.append((rgb_bytes, 0.5))

    print(f"🎬 Prepared {len(frames_list)} frame(s) fitted to 160x128.")
    return frames_list


def stream(esp32_ip: str, file_path: Path, forced_fps: int = None, fit_mode: str = "contain", port: int = DISPLAY_PORT):
    frames = load_media_frames(file_path, fit_mode=fit_mode)
    if not frames:
        print("[Error] No frames to stream.")
        return

    while True:
        try:
            print(f"\n[TCP] Connecting to ESP32 at {esp32_ip}:{port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(4.0)
            sock.connect((esp32_ip, port))
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            print(f"🚀 Streaming '{file_path.name}' -> ESP32 TFT Display (Ctrl+C to stop)\n")

            frame_idx = 0
            while True:
                raw_bytes, frame_delay = frames[frame_idx]
                target_delay = (1.0 / forced_fps) if forced_fps else frame_delay

                t0 = time.time()
                
                # Send 4-byte sync header (0xAA55AA55) + 40,960 bytes of RGB565 pixels
                packet = SYNC_HEADER + raw_bytes
                sock.sendall(packet)

                elapsed = time.time() - t0
                sleep_time = max(0.001, target_delay - elapsed)
                time.sleep(sleep_time)

                frame_idx = (frame_idx + 1) % len(frames)
                fps = 1.0 / (time.time() - t0)
                print(f"▶ Playing frame {frame_idx + 1}/{len(frames)} | {fps:.1f} FPS", end="\r")

        except (socket.error, ConnectionRefusedError, socket.timeout) as err:
            print(f"\n[Connection Notice] {err}. Reconnecting in 2 seconds...")
            time.sleep(2.0)
        except KeyboardInterrupt:
            print("\n[Stream] Stopped.")
            try:
                sock.close()
            except Exception:
                pass
            break


def main():
    parser = argparse.ArgumentParser(description="Stream Kathakali GIF to ESP32 TFT Display")
    parser.add_argument("ip", help="ESP32 IP address (e.g. 192.168.10.14)")
    parser.add_argument("file", nargs="?", default=None, help="Path to GIF (default: assets/kathakaliright (1).gif)")
    parser.add_argument("--fps", type=int, default=None, help="Target FPS (e.g. --fps 15)")
    parser.add_argument("--fit", choices=["contain", "stretch", "crop"], default="contain", help="Fit mode: contain (default), stretch, or crop")
    parser.add_argument("--port", type=int, default=DISPLAY_PORT, help="TCP port (default: 9001)")

    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    if args.file:
        target_file = Path(args.file)
        if not target_file.is_absolute():
            target_file = project_root / target_file
    else:
        target_file = find_default_gif(project_root)

    stream(args.ip, target_file, forced_fps=args.fps, fit_mode=args.fit, port=args.port)


if __name__ == "__main__":
    main()
