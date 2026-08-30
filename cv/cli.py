"""
cli.py — PookalBot CV pipeline command-line entry point.

Usage
-----
python -m cv.cli samples/pookalam.jpg
python -m cv.cli samples/pookalam.jpg --debug --output output/path.json
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import logging

import cv2

from .preprocess    import preprocess_image, PreprocessConfig
from .circle_detect import detect_circle, draw_circle_debug, CircleDetectConfig
from .symmetry      import build_polar, detect_symmetry, draw_symmetry_debug, SymmetryConfig
from .path_gen      import generate_path, validate_path, draw_path_debug, PathGenConfig

log = logging.getLogger("pookalbot.cv")


def _save_debug(path: str, img) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, img)


def run(
    image_path: str,
    output_path: str = "output/path.json",
    debug: bool = False,
    debug_dir: str = "output/debug",
    symmetry_max: int = 24,
    threshold_method: str = "otsu",
    radius_override: float | None = None,
) -> dict:
    """
    Run the full CV pipeline on *image_path*.

    Returns the path plan as a dict (also written to *output_path*).
    """
    import numpy as np

    # ── 1. Load original ──────────────────────────────────────────────────────
    import cv2 as _cv2
    bgr_original = _cv2.imread(image_path)
    if bgr_original is None:
        print(f"ERROR: Cannot open image: {image_path!r}", file=sys.stderr)
        sys.exit(1)

    if debug:
        _save_debug(f"{debug_dir}/01_original.jpg", bgr_original)

    # ── 2. Preprocess ─────────────────────────────────────────────────────────
    pre_cfg = PreprocessConfig(threshold_method=threshold_method)
    processed, intermediates = preprocess_image(bgr_original, pre_cfg)

    if debug:
        _save_debug(f"{debug_dir}/02_preprocessed.jpg", processed)

    # ── 3. Circle detection ───────────────────────────────────────────────────
    gray_for_hough = intermediates.get("contrast", intermediates.get("denoised", processed))

    circ_cfg = CircleDetectConfig()
    if radius_override is not None:
        h, w = gray_for_hough.shape[:2]
        ratio = radius_override / min(h, w)
        circ_cfg.min_radius_ratio = max(0.05, ratio - 0.1)
        circ_cfg.max_radius_ratio = min(0.95, ratio + 0.1)

    try:
        circle = detect_circle(gray_for_hough, circ_cfg)
    except RuntimeError as exc:
        print(f"ERROR (circle detection): {exc}", file=sys.stderr)
        sys.exit(1)

    if debug:
        dbg_circle = draw_circle_debug(bgr_original, circle)
        _save_debug(f"{debug_dir}/03_circle_detected.jpg", dbg_circle)

    # Resize processed image to match original (circle was detected on original dims)
    if processed.shape[:2] != bgr_original.shape[:2]:
        processed = _cv2.resize(
            processed, (bgr_original.shape[1], bgr_original.shape[0]),
            interpolation=_cv2.INTER_NEAREST,
        )

    # ── 4. Polar representation ───────────────────────────────────────────────
    gray_orig = _cv2.cvtColor(bgr_original, _cv2.COLOR_BGR2GRAY)
    polar = build_polar(
        gray_orig,
        cx=circle.center_x,
        cy=circle.center_y,
        radius_px=circle.radius,
    )

    if debug:
        _save_debug(f"{debug_dir}/04_polar_unwrapped.jpg", polar.image)

    # ── 5. Symmetry detection ─────────────────────────────────────────────────
    sym_cfg  = SymmetryConfig(max_order=symmetry_max)
    symmetry = detect_symmetry(polar, sym_cfg)

    if debug:
        dbg_sym = draw_symmetry_debug(polar, symmetry)
        _save_debug(f"{debug_dir}/05_symmetry.jpg", dbg_sym)

    # ── 6. Path generation ────────────────────────────────────────────────────
    path_cfg = PathGenConfig()
    try:
        plan = generate_path(processed, circle, symmetry, path_cfg)
    except RuntimeError as exc:
        print(f"ERROR (path generation): {exc}", file=sys.stderr)
        sys.exit(1)

    if debug:
        # Extracted contour view (binary masked to circle)
        import numpy as _np
        mask = _np.zeros_like(processed)
        _cv2.circle(mask,
                    (int(circle.center_x), int(circle.center_y)),
                    int(circle.radius), 255, -1)
        extracted = _cv2.bitwise_and(processed, mask)
        _save_debug(f"{debug_dir}/06_extracted_path.jpg",
                    _cv2.cvtColor(extracted, _cv2.COLOR_GRAY2BGR))

    # ── 7. Path validation ────────────────────────────────────────────────────
    validation = validate_path(plan)
    if not validation.valid:
        print("WARNING: Path validation found issues:", file=sys.stderr)
        for err in validation.errors:
            print(f"  {err.field}: {err.message}", file=sys.stderr)

    # ── 8. Debug final overlay ────────────────────────────────────────────────
    if debug:
        dbg_final = draw_path_debug(bgr_original, plan)
        _save_debug(f"{debug_dir}/07_final_path.jpg", dbg_final)

    # ── 9. Write JSON output ──────────────────────────────────────────────────
    plan_dict = plan.to_dict()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(plan_dict, f, indent=2)

    # ── Summary ───────────────────────────────────────────────────────────────
    pen_down_segs = sum(
        1 for i, w in enumerate(plan.waypoints)
        if w.pen == 1 and (i == 0 or plan.waypoints[i - 1].pen == 0)
    )

    print("PookalBot CV Pipeline")
    print("---------------------")
    print(f"Input:    {image_path}")
    print(f"\nCircle:")
    print(f"  Center: ({circle.center_x:.1f}, {circle.center_y:.1f})")
    print(f"  Radius: {circle.radius:.1f} px  (confidence: {circle.confidence:.2f})")
    print(f"\nSymmetry:")
    print(f"  Order:      {symmetry.order}")
    print(f"  Confidence: {symmetry.confidence:.2f}")
    print(f"\nPath:")
    print(f"  Waypoints:         {len(plan.waypoints)}")
    print(f"  Pen-down segments: {pen_down_segs}")
    if not validation.valid:
        print(f"  Validation:        {len(validation.errors)} warning(s)")
    print(f"\nOutput:   {output_path}")
    if debug:
        print(f"Debug:    {debug_dir}/")

    return plan_dict


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m cv.cli",
        description="PookalBot: Pookalam image → polar waypoints",
    )
    parser.add_argument("image", help="Path to Pookalam photograph")
    parser.add_argument("--output",       default="output/path.json",
                        help="Output JSON path (default: output/path.json)")
    parser.add_argument("--debug",        action="store_true",
                        help="Save intermediate debug images")
    parser.add_argument("--debug-dir",    default="output/debug",
                        help="Directory for debug images")
    parser.add_argument("--symmetry-max", type=int, default=24,
                        help="Maximum symmetry order to test (default: 24)")
    parser.add_argument("--threshold",    default="otsu",
                        choices=["otsu", "adaptive", "none"],
                        help="Threshold method (default: otsu)")
    parser.add_argument("--radius",       type=float, default=None,
                        help="Approximate circle radius in pixels (helps tuning)")
    parser.add_argument("--verbose",      action="store_true")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    run(
        image_path=args.image,
        output_path=args.output,
        debug=args.debug,
        debug_dir=args.debug_dir,
        symmetry_max=args.symmetry_max,
        threshold_method=args.threshold,
        radius_override=args.radius,
    )


if __name__ == "__main__":
    main()
