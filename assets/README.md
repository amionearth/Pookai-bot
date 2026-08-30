# Assets Folder

Put your custom GIF file(s) here for the ESP32 1.8" TFT display:

- **Default path:** `assets/eyes.gif`
- **Supported format:** Standard `.gif` (any resolution or frame count — it will be automatically resized and converted to 160x128 16-bit RGB565 by the Pi 5).

### How to Stream to ESP32:
From the Pi 5 terminal:
```bash
# Stream the default assets/eyes.gif
python pi/stream_gif.py <ESP32_IP>

# Stream a custom GIF
python pi/stream_gif.py <ESP32_IP> assets/my_custom_animation.gif --fps 15
```
