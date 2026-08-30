# PookalBot CV Pipeline

Converts a Pookalam photograph into polar-plotter waypoints using classical
OpenCV only — no neural networks, no internet required.

## Setup

```bash
pip install -r requirements-cv.txt
```

## Quick start

```bash
# Minimal — writes output/path.json
python -m cv.cli samples/pookalam.jpg

# With debug images saved to output/debug/
python -m cv.cli samples/pookalam.jpg --debug
```

## All options

```
python -m cv.cli <image> [OPTIONS]

  --output PATH        Output JSON (default: output/path.json)
  --debug              Save intermediate images to --debug-dir
  --debug-dir PATH     Debug image directory (default: output/debug)
  --symmetry-max N     Max symmetry order to test (default: 24)
  --threshold METHOD   otsu | adaptive | none  (default: otsu)
  --radius FLOAT       Hint: approximate circle radius in pixels
  --verbose            Debug logging
```

## Pipeline stages

```
Pookalam photo
      ↓  preprocess.py   — resize, denoise, CLAHE, threshold, morphology
      ↓  circle_detect.py — Hough Circle Transform → center + radius
      ↓  symmetry.py     — polar unwrap → angular autocorrelation → order
      ↓  path_gen.py     — contours → RDP simplify → polar waypoints
      ↓  path_gen.py     — validate → JSON
output/path.json
```

## Debug images (--debug)

| File | Contents |
|------|----------|
| `01_original.jpg` | Input photograph |
| `02_preprocessed.jpg` | After threshold + morphological cleanup |
| `03_circle_detected.jpg` | Detected circle overlaid on original |
| `04_polar_unwrapped.jpg` | Polar (r × θ) remap |
| `05_symmetry.jpg` | Angular projection + autocorrelation |
| `06_extracted_path.jpg` | Contours masked to circle |
| `07_final_path.jpg` | Waypoint path overlaid on original |

## Output JSON format

See `docs/protocol.md` for the full Pi ↔ ESP32 protocol.  
The CV output is consumed by the path-execution layer on the Pi.

```json
{
  "version": 1,
  "coordinate_system": {
    "theta": "radians",
    "theta_range": [0, 6.283185],
    "r_range": [0, 1]
  },
  "center": { "x": 320.0, "y": 240.0 },
  "radius_px": 180.0,
  "symmetry_order": 8,
  "waypoints": [
    { "theta": 0.0,  "r": 0.15, "pen": 1 },
    { "theta": 0.1,  "r": 0.18, "pen": 1 },
    { "theta": 0.3,  "r": 0.20, "pen": 0 }
  ]
}
```

`pen: 1` → chalk touching surface  
`pen: 0` → chalk lifted (travel move)

## Running tests

```bash
python -m pytest cv/tests/ -v
```

Tests are fully offline and require no hardware.

## Tuning tips

| Problem | Try |
|---------|-----|
| Circle not detected | Lower `--radius`, try `--threshold adaptive` |
| Too many waypoints | Increase `rdp_epsilon` in `PathGenConfig` |
| Wrong symmetry order | Raise `--symmetry-max` |
| Dark/low-contrast photo | Use `--threshold adaptive` |
