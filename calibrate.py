"""
calibrate.py
============
Achira Beta Cartridge — QC Calibration Module
DWG: ACMCTA001  |  Material: PMMA  |  Microscope: 5X, stitched PNG

PURPOSE
-------
Computes the scale factor (mm/pixel) from a reference image using known
features on the cartridge. One calibration per batch — valid for all 4
image types (Holes, Neck, DAB, Mixing) since all share the same 5X setup.

RECOMMENDED USAGE (multi-hole — most accurate)
-----------------------------------------------
  python calibrate.py calibrate --ref Holes_ch00.png --feature hole --n_holes 5

  → Opens image, prompts you to click both edges of 5 holes one by one.
  → Averages all 5 diameters → single robust scale factor.
  → Saves calibration.json + calibration_annotated.png

SINGLE HOLE (quick)
-------------------
  python calibrate.py calibrate --ref Holes_ch00.png --feature hole --n_holes 1

OTHER FEATURES
--------------
  python calibrate.py calibrate --ref neck_ch00.png --feature channel --n_holes 1
  python calibrate.py calibrate --ref neck_ch00.png --feature neck    --n_holes 1

VERIFY existing calibration (drift check)
------------------------------------------
  python calibrate.py verify --image Holes_ch00.png

INFO — print saved calibration
-------------------------------
  python calibrate.py info

WHY ONE CALIBRATION COVERS ALL 4 IMAGES
-----------------------------------------
  Scale factor = property of microscope + camera + magnification.
  Since Holes / Neck / DAB / Mixing are all captured at 5X with the
  same camera and stitch settings, ONE calibration.json covers all four.

KNOWN REFERENCE DIMENSIONS (DWG ACMCTA001)
-------------------------------------------
  Hole diameter     : 0.50 mm  (Ø0.50 THRU, 12 holes)
  Channel width     : 3.20 mm  (+0.05 / 0.00)
  Channel rib width : 1.49 mm  (+0.02 / 0.00)
  Neck width        : 0.60 mm  (+0.05 / 0.00)
"""

import cv2
import numpy as np
import json
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path


# ── Known nominal dimensions from DWG ACMCTA001 ──────────────────────────────
# Each image type has its own reference feature for calibration because
# Holes_ch00 and neck_ch00 have DIFFERENT effective pixel scales at 5X:
#   Holes_ch00 : ~0.80 µm/px (large stitched area covering full cartridge)
#   neck_ch00  : ~1.31 µm/px (smaller area, zoomed in on neck region)
KNOWN_FEATURES = {
    "hole":    {"nominal_mm": 0.50,  "description": "Hole diameter (Ø0.50 THRU)",
                "applies_to": "holes"},
    "channel": {"nominal_mm": 0.60,  "description": "Wide channel into neck (Detail K, 0.60mm)",
                "applies_to": "neck"},
    "neck":    {"nominal_mm": 0.20,  "description": "Neck constriction width (Detail K, 0.20mm)",
                "applies_to": "neck"},
    "rib":     {"nominal_mm": 1.49,  "description": "Channel rib width (1.49 typ)",
                "applies_to": "holes"},
}

# Colors (BGR)
COL_GREEN  = (0, 220, 80)
COL_YELLOW = (0, 220, 255)
COL_WHITE  = (255, 255, 255)
COL_ORANGE = (0, 165, 255)
COL_CYAN   = (255, 220, 0)

# ── Global state shared between mouse callback and measurement loop ───────────
_state = {
    "clicks":       [],     # list of (x, y) in display-image coords for current hole
    "img_display":  None,   # measurement annotations live here (display-sized)
    "img_base":     None,   # clean display frame reset per hole
    "scale":        1.0,    # display_px / full_res_px
    "hole_idx":     0,      # which hole we're currently measuring (0-based)
    "n_holes":      5,      # total holes to measure
    "measurements": [],     # completed list of (p1_fullres, p2_fullres, px_dist)
    "win_name":     "",
    # zoom / pan
    "zoom":         1.0,    # current zoom level (1.0 = fit-to-screen)
    "pan_x":        0,      # viewport top-left in display-image pixels
    "pan_y":        0,
    "dragging":     False,  # right-button pan active
    "drag_start":   (0, 0), # window coord where drag started
    "pan_start":    (0, 0), # pan_x/pan_y when drag started
}


# ── Zoom helpers ─────────────────────────────────────────────────────────────

def _get_zoomed_view(img):
    """Return a display-sized view of img cropped to the current zoom/pan viewport."""
    zoom = _state["zoom"]
    if zoom <= 1.0:
        return img.copy()
    h, w  = img.shape[:2]
    roi_w = max(1, int(w / zoom))
    roi_h = max(1, int(h / zoom))
    px    = int(np.clip(_state["pan_x"], 0, w - roi_w))
    py    = int(np.clip(_state["pan_y"], 0, h - roi_h))
    _state["pan_x"] = px
    _state["pan_y"] = py
    return cv2.resize(img[py:py + roi_h, px:px + roi_w], (w, h),
                      interpolation=cv2.INTER_LINEAR)


def _win_to_display(wx, wy):
    """Convert window pixel coords → display-image pixel coords."""
    zoom = _state["zoom"]
    return (_state["pan_x"] + wx / zoom,
            _state["pan_y"] + wy / zoom)


def _zoom_at(wx, wy, factor):
    """Zoom by factor, keeping the display-image point under (wx, wy) fixed."""
    old = _state["zoom"]
    new = float(np.clip(old * factor, 1.0, 20.0))
    _state["pan_x"] = int(_state["pan_x"] + wx * (1.0 / old - 1.0 / new))
    _state["pan_y"] = int(_state["pan_y"] + wy * (1.0 / old - 1.0 / new))
    _state["zoom"]  = new


# ── HUD ──────────────────────────────────────────────────────────────────────

def _draw_hud():
    """Apply zoom then draw instruction bar on the view; show to user."""
    view = _get_zoomed_view(_state["img_display"])
    h, w = view.shape[:2]
    idx  = _state["hole_idx"]
    n    = _state["n_holes"]
    zoom = _state["zoom"]

    # Top bar — always drawn on the final view so it stays crisp at any zoom
    cv2.rectangle(view, (0, 0), (w, 56), (18, 18, 18), -1)

    if idx < n:
        n_clicks = len(_state["clicks"])
        step_msg = "→ Click LEFT edge (P1)" if n_clicks == 0 else "→ Click RIGHT edge (P2)  |  R = redo"
        cv2.putText(view, f"Hole {idx+1} of {n}:  {step_msg}",
                    (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, COL_YELLOW, 2)
        cv2.putText(view,
                    "ENTER=confirm   R=redo   Q=quit  |  Scroll=zoom   Right-drag=pan   0=reset zoom",
                    (12, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (150, 150, 150), 1)
    else:
        cv2.putText(view,
                    f"All {n} holes measured.  ENTER=save  |  R=redo last  |  Q=quit",
                    (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.62, COL_GREEN, 2)

    # Right-side per-hole summary
    for i, (_, _, d) in enumerate(_state["measurements"]):
        cv2.putText(view, f"H{i+1}: {d:.1f} px",
                    (w - 190, 72 + i * 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, COL_GREEN, 1)

    # Zoom indicator (bottom-right)
    if zoom > 1.01:
        cv2.putText(view, f"Zoom {zoom:.1f}x",
                    (w - 115, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, COL_CYAN, 2)

    cv2.imshow(_state["win_name"], view)


# ── Mouse callback ────────────────────────────────────────────────────────────

def _mouse_cb(event, x, y, flags, param):
    # ── Scroll wheel → zoom ──────────────────────────────────────────────────
    if event == cv2.EVENT_MOUSEWHEEL:
        _zoom_at(x, y, 1.25 if flags > 0 else 1 / 1.25)
        _draw_hud()
        return

    # ── Right-button drag → pan ──────────────────────────────────────────────
    if event == cv2.EVENT_RBUTTONDOWN:
        _state["dragging"]   = True
        _state["drag_start"] = (x, y)
        _state["pan_start"]  = (_state["pan_x"], _state["pan_y"])
        return

    if event == cv2.EVENT_MOUSEMOVE:
        if _state["dragging"]:
            zoom = _state["zoom"]
            _state["pan_x"] = _state["pan_start"][0] - int((x - _state["drag_start"][0]) / zoom)
            _state["pan_y"] = _state["pan_start"][1] - int((y - _state["drag_start"][1]) / zoom)
            _draw_hud()
        return

    if event == cv2.EVENT_RBUTTONUP:
        _state["dragging"] = False
        return

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    clicks = _state["clicks"]
    if len(clicks) >= 2:
        return  # pair already complete — wait for ENTER

    # Map window coords → display-image coords (accounts for zoom + pan)
    dx, dy   = _win_to_display(x, y)
    dxi, dyi = int(dx), int(dy)

    clicks.append((dx, dy))
    img   = _state["img_display"]
    color = COL_GREEN if len(clicks) == 1 else COL_YELLOW
    label = "P1" if len(clicks) == 1 else "P2"

    cv2.circle(img, (dxi, dyi), 7, color, -1)
    cv2.circle(img, (dxi, dyi), 9, COL_WHITE, 1)
    cv2.putText(img, label, (dxi + 11, dyi - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    if len(clicks) == 2:
        p1, p2   = clicks[0], clicks[1]
        p1i, p2i = (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1]))
        cv2.line(img, p1i, p2i, COL_YELLOW, 2)
        dist_disp = np.linalg.norm(np.array(p2) - np.array(p1))
        dist_full = dist_disp / _state["scale"]
        mid = ((p1i[0] + p2i[0]) // 2, (p1i[1] + p2i[1]) // 2)
        cv2.putText(img, f"{dist_full:.1f} px",
                    (mid[0] + 8, mid[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_CYAN, 2)

    _draw_hud()


# ── Image loader ──────────────────────────────────────────────────────────────

def _load_for_display(image_path: str, max_dim: int = 1400):
    """Load image and compute a display-scale copy. Returns (img_full, img_disp, scale)."""
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {image_path}")
    h, w   = img.shape[:2]
    scale  = min(max_dim / w, max_dim / h, 1.0)
    dw, dh = int(w * scale), int(h * scale)
    disp   = cv2.resize(img, (dw, dh), interpolation=cv2.INTER_AREA)
    return img, disp, scale


# ── Core: multi-hole interactive measurement ─────────────────────────────────

def measure_multi_hole(image_path: str, n_holes: int = 5):
    """
    Interactive measurement of n_holes holes.

    For each hole the user:
      1. Clicks the left  edge → P1
      2. Clicks the right edge → P2
      3. Presses ENTER to confirm the pair

    Returns: (measurements, img_full)
      measurements : list of (p1_fullres, p2_fullres, pixel_diameter)
      img_full     : original full-resolution image (numpy array)
    """
    img_full, img_disp, scale = _load_for_display(image_path)

    _state.update({
        "scale":        scale,
        "hole_idx":     0,
        "n_holes":      n_holes,
        "measurements": [],
        "clicks":       [],
        "img_display":  img_disp.copy(),
        "img_base":     img_disp.copy(),
        "win_name":     f"Calibration  |  {n_holes} hole(s)  |  5X stitched PNG  — ACMCTA001",
        "zoom":         1.0,
        "pan_x":        0,
        "pan_y":        0,
        "dragging":     False,
        "drag_start":   (0, 0),
        "pan_start":    (0, 0),
    })

    win = _state["win_name"]
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    dh, dw = img_disp.shape[:2]
    cv2.resizeWindow(win, dw, dh)
    cv2.setMouseCallback(win, _mouse_cb)

    print("\n" + "─" * 60)
    print(f"  MULTI-HOLE CALIBRATION  ({n_holes} hole{'s' if n_holes > 1 else ''})")
    print("─" * 60)
    print("  For each hole:")
    print("    1. Click the LEFT  edge  → P1 (green)")
    print("    2. Click the RIGHT edge  → P2 (yellow)")
    print("    3. Press ENTER to confirm and move to next hole")
    print("    R = redo   Q = quit")
    print("  Zoom:  Scroll wheel = zoom in/out  |  Right-drag = pan  |  0 = reset zoom")
    print("         + / -  keys = zoom in/out from centre")
    print("─" * 60 + "\n")

    _draw_hud()

    while True:
        key = cv2.waitKey(20) & 0xFF

        # ── ENTER ──────────────────────────────────────────────────────────
        if key in (13, 10):
            idx    = _state["hole_idx"]
            clicks = _state["clicks"]

            if idx >= n_holes:
                # All holes done — exit loop
                break

            if len(clicks) < 2:
                print(f"  ⚠  Click both edges of hole {idx+1} first.")
                continue

            # Convert display → full-res
            p1_full = np.array(clicks[0], dtype=float) / scale
            p2_full = np.array(clicks[1], dtype=float) / scale
            px_dist = float(np.linalg.norm(p2_full - p1_full))

            _state["measurements"].append((p1_full, p2_full, px_dist))
            print(f"  ✓  Hole {idx+1}: {px_dist:.2f} px")

            _state["hole_idx"] += 1
            _state["clicks"]    = []

            # Refresh base display, draw all confirmed pairs in green
            base = _state["img_base"].copy()
            for i, (p1, p2, d) in enumerate(_state["measurements"]):
                p1d = tuple((p1 * scale).astype(int))
                p2d = tuple((p2 * scale).astype(int))
                cv2.line(base, p1d, p2d, COL_GREEN, 2)
                cv2.circle(base, p1d, 6, COL_GREEN, -1)
                cv2.circle(base, p2d, 6, COL_GREEN, -1)
                mid = ((p1d[0]+p2d[0])//2, (p1d[1]+p2d[1])//2)
                cv2.putText(base, f"H{i+1}: {d:.0f}px",
                            (mid[0]+5, mid[1]-6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, COL_GREEN, 1)
            _state["img_display"] = base

            if _state["hole_idx"] >= n_holes:
                print(f"\n  All {n_holes} holes measured.")
                print("  Press ENTER to save  |  R to redo last hole")

            _draw_hud()

        # ── R: redo ────────────────────────────────────────────────────────
        elif key in (ord('r'), ord('R')):
            if _state["hole_idx"] >= n_holes and _state["measurements"]:
                _state["measurements"].pop()
                _state["hole_idx"] -= 1
                print(f"  ↩  Redo hole {_state['hole_idx']+1}")
            elif _state["clicks"]:
                print(f"  ↩  Redo clicks for hole {_state['hole_idx']+1}")

            _state["clicks"] = []
            # Redraw base with remaining confirmed
            base = _state["img_base"].copy()
            for i, (p1, p2, d) in enumerate(_state["measurements"]):
                p1d = tuple((p1 * scale).astype(int))
                p2d = tuple((p2 * scale).astype(int))
                cv2.line(base, p1d, p2d, COL_GREEN, 2)
                cv2.circle(base, p1d, 5, COL_GREEN, -1)
                cv2.circle(base, p2d, 5, COL_GREEN, -1)
            _state["img_display"] = base
            _draw_hud()

        # ── Zoom: scroll is handled in mouse callback; keyboard shortcuts here ─
        elif key == ord('0'):
            _state["zoom"]  = 1.0
            _state["pan_x"] = 0
            _state["pan_y"] = 0
            _draw_hud()

        elif key in (ord('+'), ord('=')):
            dw2 = _state["img_display"].shape[1] // 2
            dh2 = _state["img_display"].shape[0] // 2
            _zoom_at(dw2, dh2, 1.25)
            _draw_hud()

        elif key == ord('-'):
            dw2 = _state["img_display"].shape[1] // 2
            dh2 = _state["img_display"].shape[0] // 2
            _zoom_at(dw2, dh2, 1 / 1.25)
            _draw_hud()

        # ── Q: quit ────────────────────────────────────────────────────────
        elif key in (ord('q'), ord('Q')):
            cv2.destroyAllWindows()
            sys.exit("Calibration aborted by user.")

    cv2.destroyAllWindows()
    return _state["measurements"], img_full


# ── Auto-detect holes (HoughCircles) ─────────────────────────────────────────

def auto_detect_holes(image_path: str, n_holes: int = 5):
    """
    Fully automatic hole detection via HoughCircles.
    Picks the n_holes most radius-consistent circles.
    Returns (measurements, img_full) or None on failure.
    """
    img = cv2.imread(image_path)
    if img is None:
        return None

    gray     = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred  = cv2.GaussianBlur(gray, (7, 7), 0)
    clahe    = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(blurred)

    circles = cv2.HoughCircles(
        enhanced, cv2.HOUGH_GRADIENT,
        dp=1.2, minDist=50,
        param1=80, param2=35,
        minRadius=8, maxRadius=400
    )
    if circles is None:
        return None

    circles = np.round(circles[0]).astype(int)
    radii   = circles[:, 2]
    med_r   = np.median(radii)
    # Keep circles within 25% of median radius
    mask    = np.abs(radii - med_r) / med_r < 0.25
    close   = circles[mask] if mask.sum() > 0 else circles
    selected = close[:n_holes]

    measurements = []
    for cx, cy, r in selected:
        p1 = np.array([cx - r, cy], dtype=float)
        p2 = np.array([cx + r, cy], dtype=float)
        measurements.append((p1, p2, float(r * 2)))

    return measurements, img


# ── Statistics ────────────────────────────────────────────────────────────────

def compute_scale_from_measurements(measurements: list, known_mm: float) -> dict:
    """
    Compute averaged scale factor and quality stats from a list of
    (p1, p2, px_dist) measurements.

    FIX 1: Average diameters first, then compute ONE scale from the mean.
            (Previously averaged per-hole scales which amplifies outlier impact.)

    FIX 2: Outlier removal — drop any measurement more than 1.5 std from
            the median before computing the final scale. This handles the
            common case where one click lands on the wrong edge.

    Returns a stats dict with:
      final_scale_mm_per_px  — the value to save in calibration.json
      cv_percent             — coefficient of variation (click consistency)
      outliers_removed       — number of clicks discarded
    """
    all_diameters = [m[2] for m in measurements]

    # ── Outlier removal ───────────────────────────────────────────────────────
    if len(all_diameters) >= 3:
        med = float(np.median(all_diameters))
        std = float(np.std(all_diameters))
        # Keep measurements within 1.5 std of median
        clean = [d for d in all_diameters if abs(d - med) <= 1.5 * std]
        if len(clean) == 0:
            clean = all_diameters  # safety fallback
    else:
        clean = all_diameters

    n_removed = len(all_diameters) - len(clean)
    if n_removed > 0:
        print(f"  ⚠  Removed {n_removed} outlier click(s): "
              f"{[round(d,1) for d in all_diameters if d not in clean]} px")

    diameters = clean

    # ── Correct averaging: mean diameter → one scale ──────────────────────────
    # Wrong:  mean(known_mm / d_i)  ← inflated by small outliers
    # Correct: known_mm / mean(d_i) ← robust, physically correct
    mean_d = float(np.mean(diameters))
    std_d  = float(np.std(diameters))
    scale  = known_mm / mean_d        # ONE scale from mean diameter
    cv_pct = (std_d / mean_d * 100) if mean_d > 0 else 0.0

    # Per-hole scales for reporting only (not averaged into final)
    scales = [known_mm / d for d in all_diameters]

    return {
        "n_holes":               len(measurements),
        "n_holes_used":          len(diameters),
        "outliers_removed":      n_removed,
        "diameters_px":          [round(d, 3) for d in all_diameters],
        "diameters_px_clean":    [round(d, 3) for d in diameters],
        "scales_per_hole":       [round(s, 8) for s in scales],
        "mean_diameter_px":      round(mean_d, 3),
        "std_diameter_px":       round(std_d, 3),
        "cv_percent":            round(cv_pct, 2),
        "final_scale_mm_per_px": round(scale, 8),
    }


# ── Save / load ───────────────────────────────────────────────────────────────

def save_calibration(stats: dict, ref_image_path: str, feature: str,
                     known_mm: float, output_path: str = "calibration.json") -> dict:
    """
    Save calibration JSON.

    IMPORTANT: Holes_ch00 and neck_ch00 have DIFFERENT pixel scales at 5X
    because they cover different physical areas. Each image type must be
    calibrated separately and stored under its own key.

    calibration.json structure:
      {
        "holes": { scale_factor_mm_per_px, ... },   ← from Holes_ch00.png
        "neck":  { scale_factor_mm_per_px, ... },   ← from neck_ch00.png
        "dab":   { ... },
        "mixing":{ ... },
      }

    Usage in QC scripts:
        cal       = load_calibration()
        mm_per_px = cal["holes"]["scale_factor_mm_per_px"]   # for holes image
        mm_per_px = cal["neck"]["scale_factor_mm_per_px"]    # for neck image
    """
    scale     = stats["final_scale_mm_per_px"]
    nominal   = KNOWN_FEATURES[feature]["nominal_mm"]
    img_type  = KNOWN_FEATURES[feature].get("applies_to", "holes")

    entry = {
        "scale_factor_mm_per_px":   scale,
        "scale_factor_px_per_mm":   round(1.0 / scale, 4),
        "scale_factor_um_per_px":   round(scale * 1000, 6),
        "reference_image":          os.path.basename(ref_image_path),
        "reference_feature":        feature,
        "drawing_nominal_mm":       nominal,
        "engineer_measured_mm":     known_mm,
        "deviation_from_nominal_mm":round(known_mm - nominal, 5),
        "n_holes_clicked":          stats["n_holes"],
        "mean_diameter_px":         stats["mean_diameter_px"],
        "std_diameter_px":          stats["std_diameter_px"],
        "cv_percent":               stats["cv_percent"],
        "individual_diameters_px":  stats["diameters_px"],
        "individual_scales":        stats["scales_per_hole"],
        "microscope_magnification": "5X",
        "image_format":             "PNG",
        "stitched":                 True,
        "calibration_date":         datetime.now().isoformat(),
        "drawing_number":           "ACMCTA001",
        "part":                     "Beta Cartridge",
        "notes": (
            f"Engineer measured {known_mm} mm on {feature} "
            f"(drawing nominal: {nominal} mm, deviation: {known_mm-nominal:+.5f} mm). "
            f"Averaged over {stats['n_holes']} measurement(s). "
            f"Applies to image type: {img_type}. "
            "Re-calibrate if magnification or camera settings change."
        )
    }

    # Load existing calibration file if it exists (to preserve other image types)
    cal = {}
    if os.path.exists(output_path):
        try:
            with open(output_path) as f:
                cal = json.load(f)
        except Exception:
            cal = {}

    # Store under the image type key
    cal[img_type] = entry

    # Also keep a top-level "last_calibrated" for quick access
    cal["last_calibrated"] = {
        "image_type": img_type,
        "date":       entry["calibration_date"],
        "feature":    feature,
        "scale_um_per_px": entry["scale_factor_um_per_px"],
    }

    with open(output_path, "w") as f:
        json.dump(cal, f, indent=2)

    return cal


def load_calibration(cal_path: str = "calibration.json",
                     image_type: str = None) -> dict:
    """
    Load saved calibration.

    Parameters
    ----------
    cal_path   : path to calibration.json
    image_type : "holes" | "neck" | "dab" | "mixing" | None
                 If provided, returns only that image type's scale entry.
                 If None, returns the full calibration dict.

    Usage in QC scripts:
        from calibrate import load_calibration

        # Get scale for holes image
        cal       = load_calibration(image_type='holes')
        mm_per_px = cal['scale_factor_mm_per_px']

        # Get scale for neck image
        cal       = load_calibration(image_type='neck')
        mm_per_px = cal['scale_factor_mm_per_px']

        # Get full calibration dict
        all_cal = load_calibration()
        holes_scale = all_cal['holes']['scale_factor_mm_per_px']
        neck_scale  = all_cal['neck']['scale_factor_mm_per_px']
    """
    if not os.path.exists(cal_path):
        raise FileNotFoundError(
            f"No calibration found: {cal_path}\n"
            "Run calibration for each image type:\n"
            "  Holes: python calibrate.py calibrate --ref Holes_ch00.png --feature hole\n"
            "  Neck:  python calibrate.py calibrate --ref neck_ch00.png  --feature channel"
        )
    with open(cal_path) as f:
        cal = json.load(f)

    if image_type is not None:
        if image_type not in cal:
            raise KeyError(
                f"No calibration for image type '{image_type}' in {cal_path}.\n"
                f"Available types: {[k for k in cal.keys() if k != 'last_calibrated']}\n"
                f"Run: python calibrate.py calibrate --ref <image> --feature <feature>"
            )
        return cal[image_type]

    return cal


# ── Annotated proof image ─────────────────────────────────────────────────────

def save_annotated_image(img_full: np.ndarray, measurements: list,
                         known_mm: float, feature: str, stats: dict,
                         output_path: str = "calibration_annotated.png"):
    """Save proof image with measurement overlays and summary stats panel."""
    out  = img_full.copy()
    h, w = out.shape[:2]

    for i, (p1, p2, px_dist) in enumerate(measurements):
        p1i = tuple(p1.astype(int))
        p2i = tuple(p2.astype(int))
        mid = ((p1i[0]+p2i[0])//2, (p1i[1]+p2i[1])//2)
        cv2.line(out, p1i, p2i, COL_GREEN, 3)
        cv2.circle(out, p1i, 10, COL_GREEN, -1)
        cv2.circle(out, p2i, 10, COL_GREEN, -1)
        cv2.putText(out,
                    f"H{i+1}: {px_dist:.1f}px = {known_mm:.3f}mm",
                    (mid[0]+14, mid[1]-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, COL_CYAN, 2)

    # Stats panel
    panel_lines = [
        "CALIBRATION PROOF — ACMCTA001 Beta Cartridge",
        f"Feature     : {KNOWN_FEATURES[feature]['description']}",
        f"Holes used  : {stats['n_holes']}",
        f"Mean diam   : {stats['mean_diameter_px']:.2f} px  "
        f"(std: {stats['std_diameter_px']:.2f} px)",
        f"CV          : {stats['cv_percent']:.2f}%  "
        f"{'OK' if stats['cv_percent'] < 2.0 else 'HIGH — re-measure recommended'}",
        f"Scale factor: {stats['final_scale_mm_per_px']*1000:.4f} µm/px  "
        f"({stats['final_scale_mm_per_px']:.8f} mm/px)",
        "Applies to  : Holes / Neck / DAB / Mixing images  (same 5X setup)",
    ]
    bh = len(panel_lines) * 36 + 24
    cv2.rectangle(out, (10, h-bh-10), (900, h-10), (18, 18, 18), -1)
    cv2.rectangle(out, (10, h-bh-10), (900, h-10), COL_GREEN, 2)
    for i, line in enumerate(panel_lines):
        col = COL_ORANGE if i == 0 else (COL_GREEN if "Scale" in line else COL_WHITE)
        cv2.putText(out, line, (22, h-bh+14+i*36),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.68, col, 2)

    cv2.imwrite(output_path, out)
    print(f"  Annotated proof image saved : {output_path}")


# ── Terminal report ───────────────────────────────────────────────────────────

def print_calibration_report(cal: dict):
    """
    Print calibration summary. Accepts either:
      - a full calibration dict (with image_type keys like 'holes', 'neck')
      - a single image-type entry dict (with 'scale_factor_mm_per_px' directly)
    """
    if "scale_factor_mm_per_px" in cal:
        _print_cal_entry(cal)
    else:
        for img_type, entry in cal.items():
            if img_type == "last_calibrated":
                continue
            if isinstance(entry, dict) and "scale_factor_mm_per_px" in entry:
                print(f"\n  ── Image type: {img_type.upper()} ──")
                _print_cal_entry(entry)


def _print_cal_entry(cal: dict):
    s  = cal["scale_factor_mm_per_px"]
    n  = cal.get("n_holes_clicked", cal.get("n_holes_averaged", 1))
    cv = cal.get("cv_percent", 0.0)

    print("\n" + "═" * 60)
    print("  CALIBRATION RESULT — ACMCTA001 Beta Cartridge")
    print("═" * 60)
    print(f"  Feature        : {KNOWN_FEATURES.get(cal.get('reference_feature',''),{}).get('description','')}")
    print(f"  Reference image: {cal.get('reference_image','—')}")
    print(f"  Drawing nominal: {cal.get('drawing_nominal_mm','—')} mm")
    print(f"  Engineer input : {cal.get('engineer_measured_mm','—')} mm")
    dev = cal.get('deviation_from_nominal_mm', 0)
    print(f"  Deviation      : {dev:+.5f} mm")
    print(f"  Measurements   : {n}")
    cv_flag = "✓ Good" if cv < 2.0 else "⚠ High (>2%) — consider re-measuring"
    print(f"  CV%            : {cv:.2f}%  {cv_flag}")
    print("─" * 60)
    print(f"  Scale factor   : {s:.8f} mm/px")
    print(f"                   {s*1000:.4f} µm/px")
    print(f"  Inverse        : {cal['scale_factor_px_per_mm']:.2f} px/mm")
    print("─" * 60)
    print(f"  Calibrated on  : {cal.get('calibration_date','—')}")
    print("─" * 60)
    if n > 1:
        print("  Per-measurement breakdown:")
        for i, (d, sc) in enumerate(zip(
                cal.get("individual_diameters_px", []),
                cal.get("individual_scales", []))):
            print(f"    M{i+1}: {d:.2f} px  →  {sc*1000:.4f} µm/px")
        print("─" * 60)
    print("  ✓ Saved to calibration.json")
    print("═" * 60 + "\n")


# ── Verify ────────────────────────────────────────────────────────────────────

def verify_calibration(image_path: str, cal_path: str = "calibration.json",
                       n_holes: int = 3, image_type: str = None):
    """
    Spot-check an existing calibration on a new image.
    Measures n_holes interactively and checks drift vs saved scale factor.
    Acceptable drift threshold: < 2%.
    """
    # Detect image type from filename if not provided
    if image_type is None:
        name = Path(image_path).stem.lower()
        if "neck" in name:
            image_type = "neck"
        elif "holes" in name:
            image_type = "holes"
        else:
            image_type = "holes"

    cal_entry = load_calibration(cal_path, image_type=image_type)
    feature   = cal_entry["reference_feature"]
    known_mm  = cal_entry["engineer_measured_mm"]
    saved_s   = cal_entry["scale_factor_mm_per_px"]

    print(f"\n  Verifying calibration [{image_type}] on : {image_path}")
    print(f"  Feature : {feature}  |  Known : {known_mm} mm  |  Samples : {n_holes}")

    measurements, _ = measure_multi_hole(image_path, n_holes)
    stats   = compute_scale_from_measurements(measurements, known_mm)
    new_s   = stats["final_scale_mm_per_px"]
    drift   = abs(new_s - saved_s) / saved_s * 100

    print(f"\n  Saved scale  : {saved_s:.8f} mm/px")
    print(f"  New measured : {new_s:.8f} mm/px")
    print(f"  Drift        : {drift:.3f}%")
    print(f"  Click CV     : {stats['cv_percent']:.2f}%")

    if drift <= 2.0:
        print("  ✓ PASS — calibration is stable.")
    else:
        print(f"  ✗ FAIL — drift {drift:.2f}% exceeds 2% threshold.")
        print(f"    Re-run: python calibrate.py calibrate --ref {image_path} --feature {feature}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Achira Beta Cartridge — Batch Calibration (ACMCTA001)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
IMPORTANT: Holes_ch00 and neck_ch00 have DIFFERENT pixel scales.
Run calibration separately for each image type:

  RECOMMENDED — hardcoded pixel diameter (most reliable, no click error):
    python calibrate.py calibrate --ref Holes_ch00.png --feature hole --px 180
    python calibrate.py calibrate --ref neck_ch00.png  --feature channel --px <measured_px>

  INTERACTIVE — click across the feature manually:
    python calibrate.py calibrate --ref Holes_ch00.png --feature hole --n_holes 3

  Both write to calibration.json under their own key (holes / neck).

Other examples:
  python calibrate.py verify --image Holes_ch00.png
  python calibrate.py info
        """
    )
    sub = parser.add_subparsers(dest="command")

    # calibrate
    cp = sub.add_parser("calibrate", help="Run calibration on a reference image")
    cp.add_argument("--ref",       required=True,
                    help="Path to reference PNG (recommended: Holes_ch00.png)")
    cp.add_argument("--feature",   required=True, choices=list(KNOWN_FEATURES.keys()),
                    help="Feature to measure: hole | channel | rib | neck")
    cp.add_argument("--n_holes",   type=int, default=1,
                    help="Number of holes to click and average (default: 1)")
    cp.add_argument("--px",        type=float, default=None,
                    help="Hardcode the reference feature diameter in pixels "
                         "(skips interactive clicking entirely). "
                         "Example: --px 180  (confirmed from Inkscape measurement)")
    cp.add_argument("--known_mm",  type=float, default=None,
                    help="Override nominal mm (default: from DWG ACMCTA001)")
    cp.add_argument("--auto",      action="store_true",
                    help="Use HoughCircles auto-detect instead of manual clicks")
    cp.add_argument("--output",    default="calibration.json")
    cp.add_argument("--annotated", default="calibration_annotated.png")

    # verify
    vp = sub.add_parser("verify", help="Spot-check calibration drift on a new image")
    vp.add_argument("--image",   required=True)
    vp.add_argument("--cal",     default="calibration.json")
    vp.add_argument("--n_holes", type=int, default=3)

    # info
    ip = sub.add_parser("info", help="Print saved calibration details")
    ip.add_argument("--cal", default="calibration.json")

    args = parser.parse_args()

    if args.command == "calibrate":
        feature  = args.feature
        n        = max(1, args.n_holes)
        nominal_mm = KNOWN_FEATURES[feature]["nominal_mm"]
        known_mm   = args.known_mm if args.known_mm else nominal_mm

        print(f"\n  Feature  : {KNOWN_FEATURES[feature]['description']}")
        print(f"  DWG nom. : {nominal_mm} mm  (used for QC pass/fail)")

        # ── Mode: hardcoded pixel diameter (--px) ─────────────────────────────
        if args.px:
            px_diameter = args.px
            print(f"  Mode     : HARDCODED  —  {px_diameter} px  (from Inkscape measurement)")
            print(f"  Scale    : {known_mm} / {px_diameter} px = "
                  f"{known_mm/px_diameter*1000:.4f} µm/px")

            # Build a synthetic single measurement (no image needed)
            img_full = cv2.imread(args.ref)
            if img_full is None:
                print(f"  ⚠  Could not load {args.ref} for annotated image — skipping annotation.")
                img_full = np.zeros((100, 100, 3), dtype=np.uint8)
            h, w = img_full.shape[:2]

            # Fake measurement: horizontal line across the image centre
            p1 = np.array([w//2 - px_diameter//2, h//2], dtype=float)
            p2 = np.array([w//2 + px_diameter//2, h//2], dtype=float)
            measurements = [(p1, p2, float(px_diameter))]

            stats = compute_scale_from_measurements(measurements, known_mm)
            print(f"\n  ✓  Scale factor : {stats['final_scale_mm_per_px']*1000:.4f} µm/px")
            print(f"     ({stats['final_scale_mm_per_px']:.8f} mm/px)")

            cal = save_calibration(stats, args.ref, feature, known_mm, args.output)
            save_annotated_image(img_full, measurements, known_mm, feature,
                                 stats, args.annotated)
            print_calibration_report(cal)
            return

        if args.auto and feature == "hole":
            result = auto_detect_holes(args.ref, n_holes=n)
            if result is None:
                print("  ✗ Auto-detect failed — switching to interactive mode.")
                measurements, img_full = measure_multi_hole(args.ref, n_holes=n)
            else:
                measurements, img_full = result
                print(f"  ✓ Auto-detected {len(measurements)} hole(s).")
        else:
            measurements, img_full = measure_multi_hole(args.ref, n_holes=n)

        # ── Engineer enters actual physical measurement ────────────────────
        # The window is now closed. Engineer types the real dimension
        # they measured with their physical tool (caliper, CMM, etc.)
        nominal_mm = KNOWN_FEATURES[feature]["nominal_mm"]

        if args.known_mm:
            # Pre-supplied via CLI flag — skip prompt (useful for scripting)
            known_mm = args.known_mm
            print(f"\n  Using supplied dimension: {known_mm} mm")
        else:
            print("\n" + "─" * 60)
            print("  ENGINEER INPUT — CALIBRATION REFERENCE MEASUREMENT")
            print("─" * 60)
            print(f"  Feature        : {KNOWN_FEATURES[feature]['description']}")
            print(f"  DWG nominal    : {nominal_mm} mm  ← used for QC pass/fail")
            print(f"  Holes clicked  : {n}")
            print()
            print("  Enter the ACTUAL physical measurement of this feature")
            print("  (from your caliper / CMM / reference standard).")
            print("  This value is used ONLY to compute the scale factor.")
            print("  QC pass/fail always uses the DWG nominal above.")
            print("  Press ENTER to use the DWG nominal if no measurement available.")
            print("─" * 60)

            while True:
                try:
                    raw = input(f"  Actual dimension (mm) [{nominal_mm}]: ").strip()
                    if raw == "":
                        known_mm = nominal_mm
                        print(f"  Using drawing nominal: {known_mm} mm")
                    else:
                        known_mm = float(raw)
                        if known_mm <= 0:
                            print("  ✗ Value must be greater than 0. Try again.")
                            continue
                        deviation = known_mm - nominal_mm
                        print(f"  ✓ Accepted: {known_mm} mm  "
                              f"(deviation from nominal: {deviation:+.4f} mm)")
                    break
                except ValueError:
                    print("  ✗ Invalid input — enter a number like 0.503 or 3.21")

        stats = compute_scale_from_measurements(measurements, known_mm)

        cv = stats["cv_percent"]
        if cv > 4.0:
            print(f"\n  ✗  CV = {cv:.2f}% — clicks are too inconsistent to save.")
            print(f"     Individual diameters: {stats['diameters_px']} px")
            print(f"     Spread: {stats['std_diameter_px']:.1f} px  "
                  f"(max allowed for CV<4%: "
                  f"{stats['mean_diameter_px']*0.04:.1f} px)")
            print()
            print("  HOW TO FIX:")
            print("  1. Zoom in using scroll wheel before clicking")
            print("  2. Click the INNER bright edge of the hole (not the outer dark ring)")
            print("  3. Both clicks should be at the same height across the diameter")
            print()
            print("  Re-run: python calibrate.py calibrate "
                  f"--ref {args.ref} --feature {feature} --n_holes {n}")
            sys.exit(1)
        elif cv > 2.0:
            print(f"\n  ⚠  CV = {cv:.2f}% (>2%) — acceptable but consider re-running "
                  "for higher accuracy.")
        else:
            print(f"\n  ✓  CV = {cv:.2f}% — measurements consistent.")

        cal = save_calibration(stats, args.ref, feature, known_mm, args.output)
        save_annotated_image(img_full, measurements, known_mm, feature,
                             stats, args.annotated)
        print_calibration_report(cal)

    elif args.command == "verify":
        verify_calibration(args.image, args.cal, n_holes=args.n_holes)

    elif args.command == "info":
        cal = load_calibration(args.cal)
        print_calibration_report(cal)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()