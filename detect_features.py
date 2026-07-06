"""
detect_features.py
==================
Achira Beta Cartridge — Feature Detection Module
DWG: ACMCTA001  |  Material: PMMA  |  Microscope: 5X, stitched PNG

PURPOSE
-------
Detects and measures features in preprocessed cartridge images.
Outputs pixel-space measurements converted to mm via per-image-type calibration.

⚠  CRITICAL: EACH IMAGE TYPE HAS ITS OWN SCALE FACTOR
-------------------------------------------------------
Real image analysis showed Holes and Neck images cover DIFFERENT physical
areas → different effective pixel sizes despite same 5X magnification:

  Holes_ch00.png : ~0.84 µm/px  (8911×6136 — zoomed into small hole region)
  neck_ch00.png  : ~32   µm/px  (4503×3416 — covers larger neck region)

Run calibrate.py ONCE per image type before running detect_features.py:
  python calibrate.py calibrate --ref Holes_ch00.png --feature hole    --n_holes 3
    → saves cal_holes.json
  python calibrate.py calibrate --ref neck_ch00.png  --feature channel --n_holes 1
    → saves cal_neck.json

FEATURES DETECTED
------------------
  HOLES  (Holes_ch00.png) : 12× hole diameter + XY location
  NECK   (neck_ch00.png)  : neck constriction 0.20mm + wide channel 0.60mm
  DAB    (DAB_ch00.png)   : pending sample image
  MIXING (Mixing_ch00.png): pending sample image

USAGE
-----
  python detect_features.py --image Holes_ch00.png --cal cal_holes.json --debug
  python detect_features.py --image neck_ch00.png  --cal cal_neck.json  --debug
  python detect_features.py --folder ./1/ --cal_holes cal_holes.json --cal_neck cal_neck.json --debug
"""

import cv2
import numpy as np
import json
import argparse
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from scipy.ndimage import maximum_filter

sys.path.insert(0, str(Path(__file__).parent))
from preprocess import preprocess, detect_image_type, load_image
from leica_calibration import resolve_scale_factor
from calibrate  import load_calibration


# ── Nominal hole positions (Sheet 2, mm) ─────────────────────────────────────
HOLE_NOMINALS = {
    1:  (20.65,  8.15),  3:  (21.00, 38.00),
    4:  (21.00, 48.00),  5:  (24.50, 48.94),
    6:  (27.06, 51.50),  7:  (27.89, 56.22),
    8:  (21.00, 55.00),  9:  (14.94, 51.50),
    10: (35.27, 53.70),  12: (33.64, 62.48),
    13: (35.78, 70.50),  14: (24.50, 40.44),
}

# ── Tolerances (DWG ACMCTA001) ────────────────────────────────────────────────
TOLERANCES = {
    "hole_diameter": {"nominal": 0.50, "tol_lo": -0.05, "tol_hi": 0.05,  "id": "HL01"},
    "hole_location": {"nominal": 0.00, "tol_lo": -0.02, "tol_hi": 0.02,  "id": "HL02"},
    "wide_channel":  {"nominal": 0.60, "tol_lo":  0.00, "tol_hi": 0.02,  "id": "CH04"},
    "neck_width":    {"nominal": 0.20, "tol_lo": -0.05, "tol_hi": 0.05,  "id": "CH05"},
}

# Colors BGR
COL_GREEN  = (0, 220, 80);  COL_RED   = (60, 60, 255)
COL_YELLOW = (0, 220, 255); COL_CYAN  = (255, 220, 0)
COL_WHITE  = (255, 255, 255); COL_ORANGE = (0, 165, 255)


def _tol_check(measured_mm, feature_key):
    t  = TOLERANCES[feature_key]
    lo = t["nominal"] + t["tol_lo"]
    hi = t["nominal"] + t["tol_hi"]
    return {
        "pass": lo <= measured_mm <= hi,
        "measured_mm":  round(measured_mm, 5),
        "nominal_mm":   t["nominal"],
        "deviation_mm": round(measured_mm - t["nominal"], 5),
        "lower_limit":  lo, "upper_limit": hi,
        "feature_id":   t["id"],
    }


# ══════════════════════════════════════════════════════════════════════════════
# HOLES DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def _subpixel_diameter(gray: np.ndarray, cx: int, cy: int,
                        nominal_r: int = 90,
                        n_rays: int = 36,
                        debug_context: dict = None) -> float:
    """
    Measure hole diameter using radial threshold crossing.

    From the actual intensity profile of Tag1 (698,573):
      - Interior: ~140-148 (bright uniform PMMA)
      - Transition: r=80-95px, intensity drops from 130→49
      - Wall: <50 (very dark)

    Strategy: on each ray, find where intensity first drops below
    a threshold (110) — that's the inner wall edge.
    Use median of all rays for robustness.

    debug_context : dict, optional
        If provided (any dict), it is populated IN PLACE with ray-level
        diagnostic data (per-ray hit points, near-nominal radii, fallback
        mode) derived only from the values already computed below. The
        return value is always the diameter float and is completely
        unaffected by whether this argument is passed.
    """
    h, w     = gray.shape
    radii    = []
    ray_debug = [] if debug_context is not None else None
    THRESHOLD = 90    # intensity below this = dark wall (from real profile: val drops to 89 at r=89px)

    for angle in np.linspace(0, 2*np.pi, n_rays, endpoint=False):
        cos_a, sin_a = np.cos(angle), np.sin(angle)
        r_start = int(nominal_r * 0.50)   # start at 50% of nominal radius
        r_end   = int(nominal_r * 1.60)   # search out to 160% of nominal

        hit_r, hit_pt = None, None
        for r in range(r_start, r_end):
            px2 = cx + int(r * cos_a)
            py2 = cy + int(r * sin_a)
            if not (0 <= px2 < w and 0 <= py2 < h):
                break
            if int(gray[py2, px2]) < THRESHOLD:
                radii.append(r)
                hit_r, hit_pt = r, (px2, py2)
                break

        if ray_debug is not None:
            ray_debug.append({"angle": float(angle), "hit": hit_r is not None,
                               "r": hit_r, "point": hit_pt})

    if len(radii) < n_rays // 4:
        if debug_context is not None:
            debug_context["n_rays"] = n_rays
            debug_context["n_hit"] = len(radii)
            debug_context["rays"] = ray_debug
            debug_context["near_nominal_radii"] = []
            debug_context["fallback_mode"] = "total_failure"
        return float(nominal_r * 2)   # fallback if too few edges found

    radii_arr = np.array(sorted(radii))

    # Find the dominant cluster of radii near the nominal radius.
    # Short rays (r < nominal*0.6) are channel/teardrop interference — discard them.
    # Long rays (r > nominal*1.3) are outer features — discard them.
    near_nominal = radii_arr[
        (radii_arr >= nominal_r * 0.65) &
        (radii_arr <= nominal_r * 1.30)
    ]

    if debug_context is not None:
        debug_context["n_rays"] = n_rays
        debug_context["n_hit"] = len(radii)
        debug_context["rays"] = ray_debug
        debug_context["near_nominal_radii"] = near_nominal.tolist()

    if len(near_nominal) >= 4:
        if debug_context is not None:
            debug_context["fallback_mode"] = "normal"
        return float(np.median(near_nominal) * 2)
    elif len(near_nominal) > 0:
        if debug_context is not None:
            debug_context["fallback_mode"] = "normal"
        return float(np.median(near_nominal) * 2)
    else:
        # All rays are short (heavily overlapping channel) — use upper quartile
        if debug_context is not None:
            debug_context["fallback_mode"] = "off_nominal_fallback"
        return float(np.percentile(radii_arr, 75) * 2)


def detect_holes(preprocessed, mm_per_px, debug_context=None):
    """
    Detect holes in Holes_ch00.png.

    debug_context : dict, optional
        If provided, populated IN PLACE with per-tag diagnostic data
        (ray hit points, expected/predicted position, ray-cast timing)
        derived only from values this function already computes. The
        returned result dict is always identical whether or not this
        argument is passed.

    Key findings from real image analysis:
      - Holes_ch00.png is 8911x6136 — too large for HoughCircles directly
      - Each hole is ~40px diameter at full res (~12 µm/px scale)
      - Active image area is approx x=0..5200, y=0..5800 (right portion is black)
      - Each hole has a dark outer ring + lighter grey interior
      - HoughCircles runs on 2x downscaled image, results scaled back up

    Strategy:
      1. Crop to active area (exclude black border)
      2. Downsample 2x for speed
      3. HoughCircles with tight radius range derived from mm_per_px
      4. Filter by circularity and size consistency
      5. Scale coordinates back to full resolution
    """
    bgr     = preprocessed["bgr"]
    gray    = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    h, w    = gray.shape

    # ── Step 1: Crop to active area (exclude black right border) ─────────────
    # Active area: find columns where mean > 20 (not pure black)
    col_means = gray.mean(axis=0)
    active_cols = np.where(col_means > 20)[0]
    active_w = int(active_cols[-1]) + 50 if len(active_cols) > 0 else w
    active_w = min(active_w, w)

    row_means = gray.mean(axis=1)
    active_rows = np.where(row_means > 20)[0]
    active_h = int(active_rows[-1]) + 50 if len(active_rows) > 0 else h
    active_h = min(active_h, h)

    active = gray[:active_h, :active_w]
    print(f"  Active area: {active_w}x{active_h} (cropped from {w}x{h})")

    # ── Step 2: Downsample 4x ─────────────────────────────────────────────────
    # 4x downsample works better than 2x for this image:
    # - nominal r at full res = 90px → 22px at 4x → clean HoughCircles signal
    # - confirmed: param2=28 at 4x gives exactly 12 holes
    ds = 4
    small = cv2.resize(active,
                       (active_w // ds, active_h // ds),
                       interpolation=cv2.INTER_AREA)

    clahe   = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    small_c = clahe.apply(small)
    small_b = cv2.GaussianBlur(small_c, (7, 7), 2.0)

    # ── Step 3: HoughCircles ──────────────────────────────────────────────────
    # FIXED pixel radius based on Inkscape measurement: 220px diameter
    # at current image scale. The search radius is ALWAYS based on this
    # pixel measurement — independent of calibration scale.
    # The calibration scale only affects mm conversion AFTER detection.
    #
    # 220px diameter at full res → 55px radius at 4x downsample
    # ±22% tolerance: r = [43, 67] at 4x
    FIXED_R_FULL = 100   # px — median confirmed diameter 200px / 2 (7177x6102 image)
    nominal_r_ds = FIXED_R_FULL / ds   # = 27.5px at 4x

    min_r    = max(3, int(nominal_r_ds * 0.78))   # 17px
    max_r    = max(min_r + 2, int(nominal_r_ds * 1.22))  # 27px
    min_dist = int(nominal_r_ds * 2.8)   # 63px — larger to avoid near-duplicates

    print(f"  Scale: {mm_per_px*1000:.3f} um/px  "
          f"r_fixed={FIXED_R_FULL}px full  r_ds={nominal_r_ds:.1f}px  "
          f"search=[{min_r},{max_r}]  minDist={min_dist}")

    circles = cv2.HoughCircles(
        small_b,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min_dist,
        param1=80,
        param2=25,   # tuned: gives 15 candidates covering all hole sizes
        minRadius=min_r,
        maxRadius=max_r,
    )

    # Get full-res grayscale for subpixel measurement
    bgr_full  = preprocessed["bgr"]
    gray_full = cv2.cvtColor(bgr_full, cv2.COLOR_BGR2GRAY) if bgr_full.ndim == 3 else bgr_full

    detected = []
    _ray_debug_by_id = {}
    if circles is not None:
        for cx_ds, cy_ds, r_ds in np.round(circles[0]).astype(int):
            # Scale back to full resolution
            cx = int(cx_ds * ds)
            cy = int(cy_ds * ds)
            r  = int(r_ds  * ds)

            # ── Subpixel diameter via radial edge detection ────────────────────
            # HoughCircles gives approximate center — refine diameter by finding
            # the actual intensity drop (bright interior → dark wall) on each ray.
            # This is critical for noisy holes (e.g. Tag 4 in right panel).
            ray_ctx = {}
            _t_ray0 = time.perf_counter() if debug_context is not None else None
            d_px_refined = _subpixel_diameter(gray_full, cx, cy,
                                               nominal_r=FIXED_R_FULL,
                                               debug_context=ray_ctx)
            if debug_context is not None:
                ray_ctx["ray_cast_time_s"] = time.perf_counter() - _t_ray0
            r_refined    = d_px_refined / 2

            d_mm = d_px_refined * mm_per_px
            tol  = _tol_check(d_mm, "hole_diameter")
            cand = {
                "cx_px":          cx,
                "cy_px":          cy,
                "radius_px":      int(r_refined),
                "radius_hough_px":r,              # original HoughCircles radius
                "diameter_px":    round(d_px_refined, 2),
                "diameter_mm":    round(d_mm, 5),
                "deviation_mm":   tol["deviation_mm"],
                "pass":           tol["pass"],
            }
            detected.append(cand)
            _ray_debug_by_id[id(cand)] = ray_ctx

    # ── Step 4: Pattern-matching filter ───────────────────────────────────────
    #
    # Pixel offsets from engineer-confirmed positions (cartridge 1).
    # These are ABSOLUTE pixel values in the full-res image.
    # We do NOT scale them by calibration because:
    #   - The Holes image pixel grid is fixed regardless of calibration
    #   - Calibration only affects mm conversion, not pixel positions
    #   - All cartridges produce the same pixel offsets ±stage variation
    #
    # Tolerance: 600px covers ~1.5mm of stage placement variation
    # Disambiguation: when multiple candidates within tolerance, pick the one
    # with radius closest to the confirmed 90px nominal.
    #
    # Confirmed pixel offsets relative to Tag 1 (cartridge 1, engineer-verified):
    # Confirmed pixel offsets relative to Tag1 anchor
    # Holes_ch00.png (7177×6102) — 7 holes confirmed by engineer
    # Tag1 anchor = C12 (most isolated) at (6698, 1960)
    REF_OFFSETS = {
        1:  (-6091, -1464),   # C1  (607,  496)
        3:  (-5674, +1205),   # C2  (1024, 3165)
        4:  (-4267, -1108),   # C3  (2431, 852)
        5:  (-4392, +3596),   # C4  (2306, 5556)
        6:  (-3302,   -72),   # C5  (3396, 1888)
        7:  (-2971, +1282),   # C6  (3727, 3242)
        9:  (    0,     0),   # C12 (6698, 1960) — anchor
    }

    MATCH_TOL_PX = 600   # px — covers ±1.5mm stage variation at 2.667 um/px

    def _predict_positions(anchor_cx, anchor_cy):
        return {
            tag: (anchor_cx + dx, anchor_cy + dy)
            for tag, (dx, dy) in REF_OFFSETS.items()
        }

    def _score_anchor(anchor_cx, anchor_cy, candidates):
        preds   = _predict_positions(anchor_cx, anchor_cy)
        matched = {}
        used    = set()
        for tag, (px, py) in preds.items():
            best_d, best_c, best_i = MATCH_TOL_PX, None, -1
            for i, c in enumerate(candidates):
                if i in used: continue
                d = np.sqrt((c["cx_px"]-px)**2 + (c["cy_px"]-py)**2)
                if d >= MATCH_TOL_PX: continue
                if best_c is None or d < best_d:
                    best_d, best_c, best_i = d, c, i
            if best_c is not None:
                matched[tag] = best_c
                used.add(best_i)
        return matched

    # ── Stage 2 candidate-selection refinement (preview only, not yet active) ──
    # Ranks in-tolerance candidates by information _subpixel_diameter already
    # computed: fallback_mode tier, then ray hit count, then near-nominal ray
    # count, then distance (closest wins ties). No new thresholds.
    FALLBACK_RANK = {"total_failure": 0, "off_nominal_fallback": 1, "normal": 2}

    def _stage2_rank_key(c, px, py):
        d = np.sqrt((c["cx_px"]-px)**2 + (c["cy_px"]-py)**2)
        dbg = _ray_debug_by_id.get(id(c), {})
        fallback = dbg.get("fallback_mode", "total_failure")
        n_hit = dbg.get("n_hit", 0)
        near = len(dbg.get("near_nominal_radii", []))
        return (FALLBACK_RANK.get(fallback, 0), n_hit, near, -d)

    # Tag 1 is the most isolated hole (~30mm from nearest neighbour)
    # Its pixel isolation at ref scale = ~30mm / 0.002667 mm/px = ~11,250px
    best_score, best_matched = 0, {}
    best_anchor_cxy = None

    # Try EVERY candidate as a potential Tag1 anchor and pick the one
    # that matches the most holes. This is more reliable than assuming
    # Tag1 is the most isolated — on some images another hole may be
    # more isolated due to image cropping.
    for anchor in detected:
        matched = _score_anchor(anchor["cx_px"], anchor["cy_px"], detected)
        score   = len(matched)
        if score > best_score:
            best_score, best_matched = score, matched
            best_anchor_cxy = (anchor["cx_px"], anchor["cy_px"])

    # Frozen snapshot of the anchor-selection result, taken before Stage 2
    # runs. Downstream missing-hole classification must reason about the
    # exact same anchor geometry production always used -- it must NOT see
    # Stage 2's candidate reassignments below.
    best_matched_anchor_ref = dict(best_matched)

    # Stage 2 candidate-selection refinement: among candidates within
    # MATCH_TOL_PX of each matched tag's predicted position, replace the
    # anchor-selection's nearest-distance pick with the best-ranked one
    # (fallback tier, then ray hit count, then near-nominal count, then
    # distance) using the ranking from _stage2_rank_key. Applied
    # unconditionally so it affects production output; debug_context
    # recording is optional and has no effect on the applied result.
    if best_anchor_cxy is not None:
        stage2_preview = {} if debug_context is not None else None
        preds_final = _predict_positions(*best_anchor_cxy)
        for tag, current in list(best_matched.items()):
            px, py = preds_final[tag]
            current_key = _stage2_rank_key(current, px, py)
            best_alt, best_alt_key = None, current_key
            for c in detected:
                if c is current:
                    continue
                d = np.sqrt((c["cx_px"]-px)**2 + (c["cy_px"]-py)**2)
                if d >= MATCH_TOL_PX:
                    continue
                k = _stage2_rank_key(c, px, py)
                if k > best_alt_key:
                    best_alt, best_alt_key = c, k
            if best_alt is not None:
                if stage2_preview is not None:
                    stage2_preview[tag] = {
                        "would_change": True,
                        "current_cxy": (current["cx_px"], current["cy_px"]),
                        "current_key": current_key,
                        "alt_cxy": (best_alt["cx_px"], best_alt["cy_px"]),
                        "alt_key": best_alt_key,
                    }
                best_matched[tag] = best_alt
        if debug_context is not None:
            debug_context["stage2_preview"] = stage2_preview

    # Identify unmatched holes — check if outside image bounds or genuinely missing
    missing_holes = []
    if best_matched_anchor_ref and best_anchor_cxy is not None:
        # True anchor position, not an approximation from an arbitrary
        # matched tag's own raw detected position. Equivalent to
        # reconstructing it from that tag's expected_px and REF_OFFSETS
        # (expected_px[tag] - REF_OFFSETS[tag] == best_anchor_cxy by
        # construction) -- read directly here instead of re-deriving it.
        ax, ay     = best_anchor_cxy
        h_img_f, w_img_f = preprocessed["bgr"].shape[:2]
        margin = int(MATCH_TOL_PX)

        for tag, (dx, dy) in REF_OFFSETS.items():
            if tag in best_matched_anchor_ref:
                continue
            pred_x = ax + dx
            pred_y = ay + dy
            outside = (pred_x < -margin or pred_x > w_img_f + margin or
                       pred_y < -margin or pred_y > h_img_f + margin)
            missing_holes.append({
                "dwg_tag":      tag,
                "reason":       "outside_image" if outside else "not_detected",
                "predicted_px": (pred_x, pred_y),
            })
            if outside:
                print(f"  Tag {tag:2d}: outside image bounds "
                      f"(predicted x={pred_x}, image width={w_img_f})")
            else:
                print(f"  Tag {tag:2d}: not detected — may be obscured or missing")

    print(f"  Pattern match: {best_score}/{len(REF_OFFSETS)} matched  "
          f"missing={[m['dwg_tag'] for m in missing_holes]}")

    # ── Center refinement ─────────────────────────────────────────────────────
    # HoughCircles gives an approximate center. Refine it by finding the
    # local intensity centroid of the hole interior within a search window.
    # This ensures the annotation circle is drawn at the true hole center.
    bgr_ref   = preprocessed["bgr"]
    gray_ref  = cv2.cvtColor(bgr_ref, cv2.COLOR_BGR2GRAY) if bgr_ref.ndim == 3 else bgr_ref

    def _refine_center(cx, cy, search_r=60, debug_context=None):
        """
        Find true hole center by locating the brightest compact region nearby.

        debug_context : dict, optional
            If provided, populated IN PLACE with every candidate window this
            function already evaluates (position, mean, std, and whether it
            was accepted under the existing "m > best_mean and s < 20"
            criterion), plus the winning candidate's own mean/std. No
            scoring, threshold, or search logic is changed -- the same
            comparison already computed below is simply also recorded.
            Return value is always (best_cx, best_cy), unaffected by this
            argument.
        """
        h_r, w_r = gray_ref.shape
        best_mean, best_cx, best_cy = 0, cx, cy
        best_std = None
        step = 15
        candidates = [] if debug_context is not None else None
        for dy in range(-search_r, search_r+1, step):
            for dx in range(-search_r, search_r+1, step):
                tx, ty = cx+dx, cy+dy
                ry = int(FIXED_R_FULL * 0.35)
                if not (ry <= tx < w_r-ry and ry <= ty < h_r-ry):
                    if candidates is not None:
                        candidates.append({
                            "tx": tx, "ty": ty, "dx": dx, "dy": dy,
                            "in_bounds": False, "mean": None, "std": None,
                            "accepted": False,
                        })
                    continue
                roi = gray_ref[ty-ry:ty+ry, tx-ry:tx+ry]
                m   = float(roi.mean())
                s   = float(roi.std())
                # Hole interior: bright and uniform
                accepted = m > best_mean and s < 20
                if candidates is not None:
                    candidates.append({
                        "tx": tx, "ty": ty, "dx": dx, "dy": dy,
                        "in_bounds": True, "mean": m, "std": s,
                        "accepted": accepted,
                    })
                if accepted:
                    best_mean, best_cx, best_cy = m, tx, ty
                    best_std = s
        if debug_context is not None:
            debug_context["candidates"] = candidates
            debug_context["winning_cx"] = best_cx
            debug_context["winning_cy"] = best_cy
            debug_context["winning_mean"] = best_mean if best_mean > 0 else None
            debug_context["winning_std"] = best_std
            debug_context["search_r"] = search_r
            debug_context["step"] = step
            debug_context["ry_window"] = int(FIXED_R_FULL * 0.35)
            debug_context["start_cx"] = cx
            debug_context["start_cy"] = cy
        return best_cx, best_cy

    # If requested, retrieve the winning anchor's predicted positions using
    # the SAME _predict_positions already used above (called once more with
    # the known winning anchor, not reimplemented) -- diagnostic only.
    if debug_context is not None and best_anchor_cxy is not None:
        _expected_positions = _predict_positions(*best_anchor_cxy)
    else:
        _expected_positions = {}

    # Build final list with refined centers, ordered by DWG tag
    detected = []
    for tag, c in sorted(best_matched.items()):
        refine_ctx = {} if debug_context is not None else None
        cx_refined, cy_refined = _refine_center(c["cx_px"], c["cy_px"], debug_context=refine_ctx)
        detected.append({
            **c,
            "dwg_tag":    tag,
            "cx_px":      cx_refined,    # use refined center for annotation
            "cy_px":      cy_refined,
            "cx_hough":   c["cx_px"],    # keep original for debugging
            "cy_hough":   c["cy_px"],
        })
        if debug_context is not None:
            debug_context.setdefault("per_hole", {})[tag] = {
                **(_ray_debug_by_id.get(id(c)) or {}),
                "expected_px": _expected_positions.get(tag),
                "refine_center": refine_ctx,
            }

    nd         = len(detected)
    ne         = len(REF_OFFSETS)
    n_outside  = sum(1 for m in missing_holes if m["reason"] == "outside_image")
    n_missing  = sum(1 for m in missing_holes if m["reason"] == "not_detected")
    all_in_tol = all(c["pass"] for c in detected) if detected else False
    print(f"  Final: {nd} detected  {n_outside} outside image  {n_missing} not found")

    return {
        "circles":        detected,
        "n_detected":     nd,
        "n_expected":     ne,
        "n_outside_image":n_outside,
        "n_not_detected": n_missing,
        "missing_holes":  missing_holes,
        "all_found":      nd + n_outside >= ne,  # outside = expected to be missing
        "overall_pass":   all_in_tol,
    }


# ══════════════════════════════════════════════════════════════════════════════
# NECK DETECTION  (0.20 mm narrow channel geometry)
# ══════════════════════════════════════════════════════════════════════════════

def detect_neck(preprocessed, mm_per_px):
    """
    Detect and measure the 0.20mm narrow channel in neck_ch00.png.

    Method: Distance Transform Medial Axis
    ----------------------------------------
    1. Threshold blurred image to get dark channel mask
    2. Compute distance transform — each pixel's value = distance to nearest edge
       (= local half-width of the dark region at that point)
    3. Find local maxima (medial axis points)
    4. Filter to medial axis points within ±40% of nominal half-width (35px)
       → keeps only the narrow neck region, excludes circular chamber & wide channel
    5. Median of dist values × 2 = neck width in pixels → convert to mm
    """
    from scipy.ndimage import maximum_filter

    blurred = preprocessed["blurred"]
    h, w    = blurred.shape

    nominal_half_px = 0.10 / mm_per_px   # half-width of 0.20mm channel

    # ── Step 1: Dark mask ─────────────────────────────────────────────────────
    _, dark_mask = cv2.threshold(blurred, 80, 255, cv2.THRESH_BINARY_INV)
    k3 = np.ones((3, 3), np.uint8)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, k3, iterations=1)

    # ── Step 2: Distance transform ────────────────────────────────────────────
    dist = cv2.distanceTransform(dark_mask, cv2.DIST_L2, 5)

    # ── Step 3: Medial axis in centre band ────────────────────────────────────
    y_min = int(h * 0.20)
    y_max = int(h * 0.80)
    lmax  = maximum_filter(dist, size=7) == dist
    lmax[:y_min, :] = False
    lmax[y_max:, :] = False

    # ── Step 4: Filter to narrow-channel zone ─────────────────────────────────
    # Keep medial axis points whose half-width is 60%-140% of nominal
    # → excludes noise (< 60%) and wide channel/chamber (> 140%)
    lo = nominal_half_px * 0.60
    hi = nominal_half_px * 1.40
    narrow_axis = lmax & (dist > lo) & (dist < hi)

    pts = np.argwhere(narrow_axis)
    if len(pts) < 10:
        return {"error": f"Neck channel not found ({len(pts)} pts) — check calibration",
                "overall_pass": False}

    # ── Step 5: Measure ───────────────────────────────────────────────────────
    vals = dist[narrow_axis]    # half-widths in pixels
    widths_px = vals * 2.0      # full widths

    mean_w_px  = float(np.mean(widths_px))
    p10_px     = float(np.percentile(widths_px, 10))
    p50_px     = float(np.median(widths_px))
    p90_px     = float(np.percentile(widths_px, 90))

    # Trimmed mean 20th-80th pct
    p20 = float(np.percentile(widths_px, 20))
    p80 = float(np.percentile(widths_px, 80))
    trimmed    = widths_px[(widths_px >= p20) & (widths_px <= p80)]
    trimmed_px = float(np.mean(trimmed)) if len(trimmed) > 0 else mean_w_px

    mean_w_mm       = round(mean_w_px  * mm_per_px, 5)
    trimmed_mean_mm = round(trimmed_px * mm_per_px, 5)
    p10_mm          = round(p10_px     * mm_per_px, 5)
    p50_mm          = round(p50_px     * mm_per_px, 5)
    p90_mm          = round(p90_px     * mm_per_px, 5)

    tol = _tol_check(trimmed_mean_mm, "neck_width")

    # Narrowest point
    min_idx = int(np.argmin(widths_px))
    min_pt  = (int(pts[min_idx][1]), int(pts[min_idx][0]))
    bbox    = (0, y_min, w, y_max - y_min)

    print(f"  Neck: {len(pts)} pts  "
          f"trimmed={trimmed_mean_mm:.4f}mm  "
          f"median={p50_mm:.4f}mm  "
          f"p10={p10_mm:.4f}mm  p90={p90_mm:.4f}mm  "
          f"{'PASS' if tol['pass'] else 'FAIL'}")

    return {
        "mean_width_mm":    mean_w_mm,
        "trimmed_mean_mm":  trimmed_mean_mm,
        "p10_width_mm":     p10_mm,
        "p50_width_mm":     p50_mm,
        "p90_width_mm":     p90_mm,
        "mean_width_px":    round(mean_w_px, 2),
        "p10_width_px":     round(p10_px, 2),
        "std_width_px":     round(float(np.std(widths_px)), 2),
        "n_medial_pts":     len(pts),
        "narrowest_xy_px":  min_pt,
        "tolerance":        tol,
        "overall_pass":     tol["pass"],
        "channel_mask":     dark_mask,
        "channel_dist":     dist,
        "medial_pts":       pts,
        "channel_bbox":     bbox,
    }






# ══════════════════════════════════════════════════════════════════════════════
# DAB DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def detect_dab(preprocessed, mm_per_px, debug_context=None):
    """
    Detect the single Ø0.50mm hole in DAB_ch00.png.

    Uses HoughCircles to find the actual hole position per image
    (position varies slightly across cartridges due to stage repositioning).
    Falls back to brightest-region search if HoughCircles fails.

    debug_context : dict, optional
        If provided, populated IN PLACE with ray-level diagnostic data
        from the ray-cast measurement below. Return value is unaffected.
    """
    bgr      = preprocessed["bgr"]
    gray_raw = preprocessed.get("gray_raw", cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr)
    gray     = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    h, w     = gray.shape

    NOMINAL_R  = int(0.25 / mm_per_px)   # 0.50mm / 2 in pixels
    THRESHOLD  = 90

    # ── Step 1: Find hole via brightest circular blob ─────────────────────────
    # The DAB hole interior is bright white — the brightest compact circular
    # region in the image. Threshold at high value to isolate it uniquely.
    cx, cy = w//2, h//2   # fallback
    found  = False

    kernel = np.ones((5,5), np.uint8)
    for thresh in [130, 120, 110, 100]:
        bright   = (gray_raw > thresh).astype(np.uint8) * 255
        bright_c = cv2.morphologyEx(bright, cv2.MORPH_OPEN, kernel, iterations=2)
        n, labels, stats, centroids = cv2.connectedComponentsWithStats(bright_c)

        # Find circular blobs of plausible hole size (area 500px² to 150000px²)
        candidates = []
        for i in range(1, n):
            area = stats[i, cv2.CC_STAT_AREA]
            if not (500 < area < 150000):
                continue
            bw   = stats[i, cv2.CC_STAT_WIDTH]
            bh   = stats[i, cv2.CC_STAT_HEIGHT]
            asp  = max(bw,bh) / max(min(bw,bh), 1)
            if asp > 1.6:   # must be roughly circular
                continue
            r_est = np.sqrt(area / np.pi)
            candidates.append((area, int(centroids[i][0]), int(centroids[i][1]), r_est))

        if len(candidates) >= 1:
            # Pick the largest blob — the hole is always the biggest bright circular region
            candidates.sort(reverse=True)
            _, cx, cy, r_est = candidates[0][:4]
            # Only accept if it's clearly larger than the second candidate
            if len(candidates) == 1 or candidates[0][0] > candidates[1][0] * 3:
                found = True
                break

    if not found:
        print(f"  DAB: bright-blob detection failed — using image centre ({cx},{cy})")

    # ── Step 2: Fallback — rolling window scan for brightest compact region ──
    if not found:
        best_mean, best_cx, best_cy = 0, w//2, h//2
        r_look = int(NOMINAL_R * 0.4)
        step   = 25
        for dy in range(r_look, h-r_look, step):
            for dx in range(r_look, w-r_look, step):
                roi = gray_raw[dy-r_look:dy+r_look, dx-r_look:dx+r_look]
                m, s = float(roi.mean()), float(roi.std())
                if m > best_mean and s < 20:
                    best_mean, best_cx, best_cy = m, dx, dy
        cx, cy = best_cx, best_cy
        print(f"  DAB: using brightest region fallback ({cx},{cy}) mean={best_mean:.1f}")

    # ── Step 3: Subpixel diameter ─────────────────────────────────────────────
    def _radial_diameter(cx, cy, n_rays=72, debug_context=None):
        radii = []
        ray_debug = [] if debug_context is not None else None
        for angle in np.linspace(0, 2*np.pi, n_rays, endpoint=False):
            cos_a, sin_a = np.cos(angle), np.sin(angle)
            hit_r, hit_pt = None, None
            for r in range(int(NOMINAL_R*0.50), int(NOMINAL_R*1.60)):
                px2 = cx + int(r * cos_a)
                py2 = cy + int(r * sin_a)
                if not (0 <= px2 < w and 0 <= py2 < h):
                    break
                if int(gray[py2, px2]) < THRESHOLD:
                    radii.append(r)
                    hit_r, hit_pt = r, (px2, py2)
                    break
            if ray_debug is not None:
                ray_debug.append({"angle": float(angle), "hit": hit_r is not None,
                                   "r": hit_r, "point": hit_pt})
        if len(radii) < n_rays // 4:
            if debug_context is not None:
                debug_context.update({"n_rays": n_rays, "n_hit": len(radii),
                                       "rays": ray_debug, "near_nominal_radii": [],
                                       "fallback_mode": "total_failure"})
            return float(NOMINAL_R * 2)
        arr  = np.array(radii)
        near = arr[(arr >= NOMINAL_R*0.65) & (arr <= NOMINAL_R*1.30)]
        if debug_context is not None:
            debug_context.update({"n_rays": n_rays, "n_hit": len(radii),
                                   "rays": ray_debug,
                                   "near_nominal_radii": near.tolist()})
        if len(near) >= 4:
            if debug_context is not None:
                debug_context["fallback_mode"] = "normal"
            return float(np.percentile(near, 60)*2)
        if debug_context is not None:
            debug_context["fallback_mode"] = "off_nominal_fallback" if len(near) == 0 else "normal"
        return float(np.percentile(arr, 75)*2)

    _t_ray0 = time.perf_counter() if debug_context is not None else None
    d_px = _radial_diameter(cx, cy, debug_context=debug_context)
    if debug_context is not None:
        debug_context["ray_cast_time_s"] = time.perf_counter() - _t_ray0
    d_mm = d_px * mm_per_px
    tol  = _tol_check(d_mm, "hole_diameter")

    print(f"  DAB hole: center=({cx},{cy})  "
          f"d={d_px:.1f}px  {d_mm:.4f}mm  "
          f"{'PASS' if tol['pass'] else 'FAIL'}")

    return {
        "cx_px":        cx,
        "cy_px":        cy,
        "diameter_px":  round(d_px, 2),
        "diameter_mm":  round(d_mm, 5),
        "deviation_mm": tol["deviation_mm"],
        "pass":         tol["pass"],
        "tolerance":    tol,
        "overall_pass": tol["pass"],
    }



def detect_mixing(preprocessed, mm_per_px, debug_context=None):
    """
    Detect 3 holes in Mixing_ch00.png using HoughCircles.

    debug_context : dict, optional
        If provided, populated IN PLACE with per-hole diagnostic data
        (ray hit points, reference/expected position, ray-cast timing)
        derived only from values this function already computes. The
        returned result dict is always identical whether or not this
        argument is passed.

    Each cartridge has slightly different stage position so holes move.
    Strategy:
    1. Run HoughCircles to find all circular candidates
    2. Match candidates to expected positions using confirmed reference positions
       (within a search tolerance of ±600px)
    3. Measure diameter via subpixel radial edge detection

    Confirmed reference positions (from one calibration image):
      MX01: ~(405,  1701) — left hole
      MX02: ~(5690, 2220) — centre hole
      MX03: ~(11973,2119) — right hole
    """
    bgr  = preprocessed["bgr"]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    h, w = gray.shape

    # Reference positions — used to match candidates, not as fixed centers
    REFERENCE = [
        {"id": "MX01", "ref_cx": 405,   "ref_cy": 1701},
        {"id": "MX02", "ref_cx": 5690,  "ref_cy": 2220},
        {"id": "MX03", "ref_cx": 11973, "ref_cy": 2119},
    ]
    NOMINAL_R   = 95
    THRESHOLD   = 100
    MATCH_TOL   = 800   # px — max allowed distance from reference position

    # ── Step 1: Find all circular candidates via HoughCircles ────────────────
    ds      = 4
    small   = cv2.resize(gray, (w//ds, h//ds), interpolation=cv2.INTER_AREA)
    clahe   = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))
    small_b = cv2.GaussianBlur(clahe.apply(small), (7,7), 2.0)

    candidates = []
    for p2 in [35, 30, 25, 22]:
        circles = cv2.HoughCircles(
            small_b, cv2.HOUGH_GRADIENT,
            dp=1.2, minDist=44,
            param1=80, param2=p2,
            minRadius=20, maxRadius=35,
        )
        if circles is not None and len(circles[0]) <= 15:
            candidates = [(int(c[0]*ds), int(c[1]*ds), int(c[2]*ds))
                          for c in circles[0]]
            break

    print(f"  Mixing: {len(candidates)} HoughCircles candidates")

    # ── Step 2: Match each reference hole to nearest candidate ───────────────
    def _radial_diameter(cx, cy, n_rays=72, debug_context=None):
        radii = []
        ray_debug = [] if debug_context is not None else None
        for angle in np.linspace(0, 2*np.pi, n_rays, endpoint=False):
            cos_a, sin_a = np.cos(angle), np.sin(angle)
            hit_wall = False
            hit_r, hit_pt = None, None
            for r in range(int(NOMINAL_R*0.50), int(NOMINAL_R*1.60)):
                px2 = cx + int(r * cos_a)
                py2 = cy + int(r * sin_a)
                if not (0 <= px2 < w and 0 <= py2 < h):
                    break
                if int(gray[py2, px2]) < THRESHOLD:
                    radii.append(r)
                    hit_wall = True
                    hit_r, hit_pt = r, (px2, py2)
                    break
            if ray_debug is not None:
                ray_debug.append({"angle": float(angle), "hit": hit_r is not None,
                                   "r": hit_r, "point": hit_pt})
        if len(radii) < n_rays // 4:
            if debug_context is not None:
                debug_context.update({"n_rays": n_rays, "n_hit": len(radii),
                                       "rays": ray_debug, "near_nominal_radii": [],
                                       "fallback_mode": "total_failure"})
            return float(NOMINAL_R * 2)
        arr  = np.array(radii)
        near = arr[(arr >= NOMINAL_R*0.65) & (arr <= NOMINAL_R*1.30)]
        if debug_context is not None:
            debug_context.update({"n_rays": n_rays, "n_hit": len(radii),
                                   "rays": ray_debug, "near_nominal_radii": near.tolist()})
        if len(near) >= 4:
            if debug_context is not None:
                debug_context["fallback_mode"] = "normal"
            return float(np.percentile(near, 60) * 2)
        if debug_context is not None:
            debug_context["fallback_mode"] = "off_nominal_fallback" if len(near) == 0 else "normal"
        return float(np.percentile(arr, 75) * 2)

    results      = []
    overall_pass = True

    for ref in REFERENCE:
        ref_cx, ref_cy = ref["ref_cx"], ref["ref_cy"]

        # Find best candidate within tolerance
        best_dist = MATCH_TOL + 1
        best_cx, best_cy = ref_cx, ref_cy

        for cx_c, cy_c, r_c in candidates:
            dist = np.sqrt((cx_c - ref_cx)**2 + (cy_c - ref_cy)**2)
            if dist < best_dist:
                best_dist = dist
                best_cx, best_cy = cx_c, cy_c

        if best_dist > MATCH_TOL:
            # No candidate found — use reference position as fallback
            print(f"  {ref['id']}: no candidate within {MATCH_TOL}px of "
                  f"({ref_cx},{ref_cy}) — using reference position")
            best_cx, best_cy = ref_cx, ref_cy

        # Measure diameter
        ray_ctx = {} if debug_context is not None else None
        _t_ray0 = time.perf_counter() if debug_context is not None else None
        d_px = _radial_diameter(best_cx, best_cy, debug_context=ray_ctx)
        if debug_context is not None:
            ray_ctx["ray_cast_time_s"] = time.perf_counter() - _t_ray0
        d_mm = d_px * mm_per_px
        tol  = _tol_check(d_mm, "hole_diameter")
        if not tol["pass"]:
            overall_pass = False

        print(f"  {ref['id']}: ({best_cx},{best_cy})  "
              f"dist_from_ref={best_dist:.0f}px  "
              f"d={d_mm:.4f}mm  "
              f"{'PASS' if tol['pass'] else 'FAIL'}")

        results.append({
            "id":           ref["id"],
            "cx_px":        best_cx,
            "cy_px":        best_cy,
            "diameter_px":  round(d_px, 2),
            "diameter_mm":  round(d_mm, 5),
            "deviation_mm": tol["deviation_mm"],
            "pass":         tol["pass"],
        })
        if debug_context is not None:
            debug_context.setdefault("per_hole", {})[ref["id"]] = {
                **ray_ctx, "expected_px": (ref_cx, ref_cy),
            }

    return {
        "holes":        results,
        "n_holes":      len(results),
        "overall_pass": overall_pass,
    }


def annotate_mixing(img, result, mm_per_px):
    out  = img.copy()
    h, w = out.shape[:2]

    n_pass = sum(1 for hole in result["holes"] if hole["pass"])
    n_fail = len(result["holes"]) - n_pass

    for hole in result["holes"]:
        cx  = hole["cx_px"]
        cy  = hole["cy_px"]
        r   = int(hole["diameter_px"] / 2)
        col = COL_GREEN if hole["pass"] else COL_RED

        cv2.circle(out, (cx, cy), r, col, max(3, r//10))
        cv2.circle(out, (cx, cy), max(3, r//15), col, -1)
        cv2.line(out, (cx-r, cy), (cx+r, cy), COL_YELLOW, max(2, r//15))
        tick = max(4, r//8)
        cv2.line(out, (cx-r, cy-tick), (cx-r, cy+tick), COL_YELLOW, max(2, r//15))
        cv2.line(out, (cx+r, cy-tick), (cx+r, cy+tick), COL_YELLOW, max(2, r//15))

        fs  = max(0.8, r*0.025)
        flw = max(2, r//30)
        off = r + 20
        for j, (txt, tc) in enumerate([
            (hole["id"],                               COL_WHITE),
            (f"{hole['diameter_mm']:.4f} mm",          col),
            (f"dev {hole['deviation_mm']:+.5f}",        col),
            (f"{'PASS' if hole['pass'] else 'FAIL'}",   col),
        ]):
            cv2.putText(out, txt, (cx+off, cy-int(fs*40)+j*int(fs*45)),
                        cv2.FONT_HERSHEY_SIMPLEX, fs, (0,0,0), flw+2)
            cv2.putText(out, txt, (cx+off, cy-int(fs*40)+j*int(fs*45)),
                        cv2.FONT_HERSHEY_SIMPLEX, fs, tc, flw)

    # Summary panel
    panel_h = max(80, int(h*0.04))
    cv2.rectangle(out, (0, h-panel_h), (w, h), (18,18,18), -1)
    cv2.rectangle(out, (0, h-panel_h), (w, h), (60,60,60), 2)
    pf_s  = max(1.2, panel_h*0.025)
    pf_lw = max(3, int(panel_h*0.05))
    ty    = h - panel_h + int(panel_h*0.82)
    op    = result["overall_pass"]
    cv2.putText(out, "PASS" if op else "FAIL",
                (20, ty), cv2.FONT_HERSHEY_SIMPLEX, pf_s,
                COL_GREEN if op else COL_RED, pf_lw)
    cv2.putText(out,
                f"Mixing holes: {result['n_holes']}  "
                f"PASS: {n_pass}  FAIL: {n_fail}  "
                f"|  Scale: {mm_per_px*1000:.3f} um/px  |  DWG: ACMCTA001",
                (int(pf_s*80+30), ty),
                cv2.FONT_HERSHEY_SIMPLEX, max(0.7, panel_h*0.016),
                COL_WHITE, max(2, int(panel_h*0.03)))
    return out


def annotate_dab(img, result, mm_per_px):
    """Draw the detected DAB hole measurement on the image."""
    out  = img.copy()
    h, w = out.shape[:2]

    cx  = result["cx_px"]
    cy  = result["cy_px"]
    r   = int(result["diameter_px"] / 2)
    col = COL_GREEN if result["pass"] else COL_RED

    # Circle + crosshair
    cv2.circle(out, (cx, cy), r, col, max(3, r//10))
    cv2.circle(out, (cx, cy), max(3, r//15), col, -1)
    cv2.line(out, (cx-r, cy), (cx+r, cy), COL_YELLOW, max(2, r//15))
    tick = max(4, r//8)
    cv2.line(out, (cx-r, cy-tick), (cx-r, cy+tick), COL_YELLOW, max(2, r//15))
    cv2.line(out, (cx+r, cy-tick), (cx+r, cy+tick), COL_YELLOW, max(2, r//15))

    # Labels
    fs   = max(0.8, r * 0.025)
    flw  = max(2, r // 30)
    off  = r + 20
    for j, (txt, tc) in enumerate([
        (f"DAB Hole",                              COL_WHITE),
        (f"{result['diameter_mm']:.4f} mm",        col),
        (f"dev {result['deviation_mm']:+.5f}",     col),
        (f"{'PASS' if result['pass'] else 'FAIL'}", col),
    ]):
        cv2.putText(out, txt, (cx + off, cy - int(fs*40) + j*int(fs*45)),
                    cv2.FONT_HERSHEY_SIMPLEX, fs, (0,0,0), flw+2)
        cv2.putText(out, txt, (cx + off, cy - int(fs*40) + j*int(fs*45)),
                    cv2.FONT_HERSHEY_SIMPLEX, fs, tc, flw)

    # Summary panel
    panel_h = max(80, int(h*0.06))
    cv2.rectangle(out, (0, h-panel_h), (w, h), (18,18,18), -1)
    cv2.rectangle(out, (0, h-panel_h), (w, h), (60,60,60), 2)
    pf_s  = max(1.2, panel_h*0.025)
    pf_lw = max(3, int(panel_h*0.05))
    ty    = h - panel_h + int(panel_h*0.82)
    cv2.putText(out, "PASS" if result["pass"] else "FAIL",
                (20, ty), cv2.FONT_HERSHEY_SIMPLEX, pf_s,
                COL_GREEN if result["pass"] else COL_RED, pf_lw)
    cv2.putText(out,
                f"DAB hole: {result['diameter_mm']:.4f}mm  "
                f"dev={result['deviation_mm']:+.5f}  "
                f"|  Scale: {mm_per_px*1000:.3f} um/px  |  DWG: ACMCTA001",
                (int(pf_s*80+30), ty),
                cv2.FONT_HERSHEY_SIMPLEX, max(0.7, panel_h*0.015),
                COL_WHITE, max(2, int(panel_h*0.03)))
    return out


# ══════════════════════════════════════════════════════════════════════════════
# ANNOTATION
# ══════════════════════════════════════════════════════════════════════════════

def annotate_holes(img, result, mm_per_px):
    """
    Produce a clearly annotated preview image showing all detected holes.
    Output is saved at a sensible display resolution (max 3000px wide).

    Each hole shows:
      - Colored circle overlay (green=PASS, red=FAIL)
      - Diameter measurement in mm
      - Deviation from nominal
      - Hole number label

    Bottom panel shows overall summary.
    """
    out   = img.copy()
    h, w  = out.shape[:2]

    # ── Scale factors for drawing — everything scales with image size ──────────
    # Line thickness, font size, dot size all proportional to hole radius
    avg_r     = np.mean([c["radius_px"] for c in result["circles"]]) if result["circles"] else 90
    lw        = max(3,  int(avg_r * 0.12))   # circle line width
    dot_r     = max(4,  int(avg_r * 0.10))   # center dot radius
    font_scale= max(0.8, avg_r * 0.030)      # label font size
    font_lw   = max(2,  int(avg_r * 0.06))   # label line width
    offset    = int(avg_r * 1.15)            # label offset from circle edge

    for i, c in enumerate(result["circles"]):
        cx, cy, r = c["cx_px"], c["cy_px"], c["radius_px"]
        col = COL_GREEN if c["pass"] else COL_RED

        # Circle overlay with thick border
        cv2.circle(out, (cx, cy), r, col, lw * 2)

        # Inner highlight ring
        cv2.circle(out, (cx, cy), max(1, r - lw), (255, 255, 255), 1)

        # Center crosshair
        cv2.circle(out, (cx, cy), dot_r, col, -1)
        cv2.line(out, (cx - r, cy), (cx + r, cy), col, max(1, lw // 2))
        cv2.line(out, (cx, cy - r), (cx, cy + r), col, max(1, lw // 2))

        # Diameter measurement line with end ticks
        tick = int(r * 0.15)
        cv2.line(out, (cx - r, cy), (cx + r, cy), COL_YELLOW, lw)
        cv2.line(out, (cx - r, cy - tick), (cx - r, cy + tick), COL_YELLOW, lw)
        cv2.line(out, (cx + r, cy - tick), (cx + r, cy + tick), COL_YELLOW, lw)

        # Labels — hole number + measurement + deviation
        label_x = cx + offset
        label_y = cy

        # Background box for readability
        tag_label = f"Tag{c.get('dwg_tag','?')}"
        for j, (txt, txt_col) in enumerate([
            (tag_label,                             COL_WHITE),
            (f"{c['diameter_mm']:.4f} mm",          col),
            (f"dev {c['deviation_mm']:+.5f}",        col),
            ("PASS" if c["pass"] else "FAIL",        col),
        ]):
            ty = label_y - int(font_scale * 40) + j * int(font_scale * 45)
            # Shadow
            cv2.putText(out, txt, (label_x + 2, ty + 2),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                        (0, 0, 0), font_lw + 2)
            # Text
            cv2.putText(out, txt, (label_x, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                        txt_col, font_lw)

    # ── Summary panel ─────────────────────────────────────────────────────────
    op        = result["overall_pass"]
    nd        = result["n_detected"]
    ne        = result["n_expected"]
    n_pass    = sum(1 for c in result["circles"] if c["pass"])
    n_fail    = nd - n_pass
    n_outside = result.get("n_outside_image", 0)
    n_missing = result.get("n_not_detected", 0)
    panel_h   = int(h * 0.06)
    panel_h   = max(panel_h, 80)

    cv2.rectangle(out, (0, h - panel_h), (w, h), (18, 18, 18), -1)
    cv2.rectangle(out, (0, h - panel_h), (w, h), (60, 60, 60), 2)

    pf_scale = max(1.2, panel_h * 0.025)
    pf_lw    = max(3, int(panel_h * 0.05))
    info_scale = max(0.8, panel_h * 0.016)
    info_lw    = max(2, int(panel_h * 0.035))
    ty_top = h - panel_h + int(panel_h * 0.45)
    ty_bot = h - panel_h + int(panel_h * 0.82)

    cv2.putText(out,
                f"{'PASS' if op else 'FAIL'}",
                (20, ty_bot),
                cv2.FONT_HERSHEY_SIMPLEX, pf_scale,
                COL_GREEN if op else COL_RED, pf_lw)

    cv2.putText(out,
                f"Detected: {nd}  PASS: {n_pass}  FAIL: {n_fail}"
                + (f"  Outside frame: {n_outside}" if n_outside else "")
                + (f"  Missing: {n_missing}" if n_missing else "")
                + f"  |  Scale: {mm_per_px*1000:.3f} um/px  |  DWG: ACMCTA001",
                (int(pf_scale * 80 + 30), ty_bot),
                cv2.FONT_HERSHEY_SIMPLEX, info_scale,
                COL_WHITE, info_lw)

    return out


def annotate_neck(img, result):
    out = img.copy()
    h, w = out.shape[:2]

    if "error" in result:
        cv2.rectangle(out, (0, 0), (w, 80), (18, 18, 18), -1)
        cv2.putText(out, f"NECK ERROR: {result['error']}",
                    (20, 54), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COL_RED, 3)
        return out

    tol = result["tolerance"]
    op  = result["overall_pass"]
    col = COL_GREEN if op else COL_RED

    # ── Channel mask overlay (semi-transparent cyan tint) ────────────────────
    chan_mask = result.get("channel_mask")
    if chan_mask is not None:
        overlay = out.copy()
        overlay[chan_mask > 0] = [255, 210, 0]
        out = cv2.addWeighted(out, 0.65, overlay, 0.35, 0)

    # ── Medial axis dots coloured by local width ──────────────────────────────
    pts       = result.get("medial_pts")
    chan_dist  = result.get("channel_dist")
    mean_px   = result["mean_width_px"]

    if pts is not None and chan_dist is not None:
        for py, px in pts:
            w_px = chan_dist[py, px] * 2.0
            frac = w_px / max(mean_px, 1.0)
            dot_col = COL_RED if frac < 0.85 else (COL_ORANGE if frac > 1.15 else COL_GREEN)
            cv2.circle(out, (int(px), int(py)), 4, dot_col, -1)

    # ── Narrowest point marker ────────────────────────────────────────────────
    nx, ny = result["narrowest_xy_px"]
    hw     = int(result["p10_width_px"] / 2)
    cv2.line(out, (nx, ny - hw - 10), (nx, ny + hw + 10), COL_RED, 3)
    cv2.circle(out, (nx, ny), 12, COL_RED, 2)
    cv2.putText(out, f"Narrowest: {result['p10_width_mm']:.4f} mm",
                (nx + 16, ny - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, COL_RED, 2)

    # ── Summary panel ─────────────────────────────────────────────────────────
    panel_h = 130
    cv2.rectangle(out, (0, h - panel_h), (w, h), (18, 18, 18), -1)
    cv2.rectangle(out, (0, h - panel_h), (w, h), (60, 60, 60), 2)

    cv2.putText(out, "PASS" if op else "FAIL",
                (20, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 1.2, col, 3)

    lines = [
        (f"Mean width  : {result['mean_width_mm']:.4f} mm  "
         f"(nom 0.20 mm, dev {tol['deviation_mm']:+.5f} mm)", col),
        (f"P10 (narrow): {result['p10_width_mm']:.4f} mm   "
         f"P90 (wide) : {result['p90_width_mm']:.4f} mm", COL_WHITE),
        (f"Medial pts  : {result['n_medial_pts']}   "
         f"Std: {result['std_width_px']:.1f} px   DWG: ACMCTA001", (150, 150, 150)),
    ]
    for i, (txt, c) in enumerate(lines):
        cv2.putText(out, txt, (20, h - panel_h + 36 + i * 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, c, 2)

    return out


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY
# ══════════════════════════════════════════════════════════════════════════════

def detect(image_path, calibration, save_annotated=False, annotated_path=None,
           calibration_mode="json"):
    img_type  = detect_image_type(image_path)

    # Calibration subsystem: resolves mm_per_px from calibration.json,
    # Leica MetaData XML, or both (cross-checked), depending on
    # calibration_mode ("json" | "metadata" | "auto"). Default "json"
    # preserves the exact behavior this pipeline had before Leica
    # MetaData support existed.
    cal_result  = resolve_scale_factor(image_path, img_type, calibration,
                                        calibration_mode=calibration_mode)
    mm_per_px           = cal_result["mm_per_px"]
    calibration_source   = cal_result["source"]
    calibration_detail   = cal_result["detail"]

    print(f"\n  [{img_type.upper()}] {Path(image_path).name}")
    print(f"  Scale: {mm_per_px:.6f} mm/px  ({mm_per_px*1000:.4f} µm/px)  "
          f"[source: {calibration_source}]")

    preprocessed = preprocess(image_path, image_type=img_type)
    img_bgr      = preprocessed["bgr"]

    if img_type == "holes":
        features  = detect_holes(preprocessed, mm_per_px)
        annotated = annotate_holes(img_bgr, features, mm_per_px)
    elif img_type == "neck":
        features  = detect_neck(preprocessed, mm_per_px)
        annotated = annotate_neck(img_bgr, features)
    elif img_type == "dab":
        features  = detect_dab(preprocessed, mm_per_px)
        annotated = annotate_dab(img_bgr, features, mm_per_px)
    elif img_type == "mixing":
        features  = detect_mixing(preprocessed, mm_per_px)
        annotated = annotate_mixing(img_bgr, features, mm_per_px)
    else:
        print(f"  WARNING: {img_type} detection pending — provide sample image.")
        features  = {"note": f"{img_type} detection not yet implemented"}
        annotated = img_bgr.copy()
        cv2.putText(annotated, f"{img_type.upper()} — pending",
                    (30,60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COL_ORANGE, 3)

    # Strip ndarray before returning
    features_clean = {k: v for k, v in features.items()
                      if not isinstance(v, np.ndarray)}

    if save_annotated:
        if annotated_path is None:
            annotated_path = str(
                Path(image_path).parent / f"{Path(image_path).stem}_detected.png")
        ah, aw = annotated.shape[:2]
        sc = min(3000/aw, 3000/ah, 1.0)
        if sc < 1.0:
            annotated = cv2.resize(annotated, (int(aw*sc), int(ah*sc)),
                                   interpolation=cv2.INTER_AREA)
        cv2.imwrite(annotated_path, annotated)
        print(f"  Saved: {annotated_path}")

    return {
        "image_path":         image_path,
        "image_type":         img_type,
        "mm_per_px":          mm_per_px,
        "calibration_source": calibration_source,
        "calibration_detail": calibration_detail,
        "features":           features_clean,
        "overall_pass":       features.get("overall_pass", False),
        "timestamp":          datetime.now().isoformat(),
    }


def detect_cartridge_folder(folder_path, calibration, debug=False, calibration_mode="json"):
    """Process all images in a cartridge folder using a single calibration dict."""
    folder  = Path(folder_path)
    results = {}
    for fpath in sorted(list(folder.glob("*.png")) + list(folder.glob("*.PNG"))):
        ann = str(folder / f"{fpath.stem}_detected.png") if debug else None
        try:
            r = detect(str(fpath), calibration, save_annotated=debug,
                       annotated_path=ann, calibration_mode=calibration_mode)
            results[r["image_type"]] = r
            print(f"  {'✓ PASS' if r['overall_pass'] else '✗ FAIL'}  {fpath.name}")
        except Exception as e:
            print(f"  ✗ Error: {fpath.name}: {e}")
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Achira Beta Cartridge — Feature Detection (ACMCTA001)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
⚠  Calibrate each image type first:
   python calibrate.py calibrate --ref Holes_ch00.png --feature hole    --n_holes 3  (→ cal_holes.json)
   python calibrate.py calibrate --ref neck_ch00.png  --feature channel --n_holes 1  (→ cal_neck.json)

Examples:
  python detect_features.py --image Holes_ch00.png --cal cal_holes.json --debug
  python detect_features.py --image neck_ch00.png  --cal cal_neck.json  --debug
  python detect_features.py --folder ./1/ --cal_holes cal_holes.json --cal_neck cal_neck.json --debug
        """
    )
    p.add_argument("--image",     help="Single image")
    p.add_argument("--images",    nargs="+",
                   help="Multiple images to process into one CSV.")
    p.add_argument("--cal",       default="calibration.json")
    p.add_argument("--folder",    help="Single cartridge folder")
    p.add_argument("--batch",     help="Parent folder containing multiple cartridge subfolders")
    p.add_argument("--cal_holes", default="cal_holes.json")
    p.add_argument("--cal_neck",  default="cal_neck.json")
    p.add_argument("--debug",     action="store_true")
    p.add_argument("--verify",    action="store_true",
                   help="Send annotated image to Claude API for visual verification")
    p.add_argument("--verify_always", action="store_true",
                   help="Always verify every image (default: only on suspicious results)")
    p.add_argument("--output",    default=None, help="JSON output path (single image)")
    p.add_argument("--csv",       default="qc_results.csv",
                   help="CSV output path (default: qc_results.csv)")
    args = p.parse_args()

    if args.image:
        cal    = load_calibration(args.cal)
        result = detect(args.image, cal, save_annotated=args.debug)
        f      = result["features"]
        print("\n" + "═"*55)
        print(f"  RESULT — {Path(args.image).name}")
        print("═"*55)
        if result["image_type"] == "holes":
            print(f"  Detected: {f.get('n_detected')}/{f.get('n_expected')} holes")
            for i, c in enumerate(f.get("circles", [])):
                s = "✓" if c["pass"] else "✗"
                print(f"  H{i+1:2d}: {c['diameter_mm']:.4f}mm  "
                      f"dev={c['deviation_mm']:+.5f}  {s}")
        elif result["image_type"] == "neck":
            if "error" not in f:
                s = "✓" if f["tolerance"]["pass"] else "✗"
                print(f"  Mean  : {f['mean_width_mm']:.4f} mm  "
                      f"dev={f['tolerance']['deviation_mm']:+.5f}  {s}")
                print(f"  P10   : {f['p10_width_mm']:.4f} mm  "
                      f"P90={f['p90_width_mm']:.4f} mm  "
                      f"N={f['n_medial_pts']} pts")
            else:
                print(f"  ERROR : {f['error']}")
        print(f"  Overall: {'✓ PASS' if result['overall_pass'] else '✗ FAIL'}")
        print("═"*55)
        if args.output:
            with open(args.output, "w") as fp:
                json.dump(result, fp, indent=2)
            print(f"  Results → {args.output}")

    elif args.images:
        cal      = load_calibration(args.cal)
        all_rows = []
        n_pass   = 0
        n_fail   = 0

        # Import verifier if requested
        verifier = None
        if args.verify or args.verify_always:
            try:
                from verify_features import verify_detection, add_verification_to_rows
                verifier = verify_detection
                print("  [VERIFY] Claude API verification enabled.")
            except ImportError:
                print("  [VERIFY] Warning: verify_features.py not found — skipping verification.")

        print(f"\n  Processing {len(args.images)} image(s)...")
        print("─" * 55)

        for img_path in args.images:
            if not os.path.exists(img_path):
                print(f"  ✗ Not found: {img_path}")
                continue

            cartridge_id = Path(img_path).parent.name or Path(img_path).stem

            try:
                result = detect(img_path, cal, save_annotated=args.debug)
                status = "✓ PASS" if result["overall_pass"] else "✗ FAIL"
                print(f"  {status}  [{cartridge_id}]  {Path(img_path).name}")

                # Claude verification
                verification = None
                if verifier and args.debug:
                    annotated_path = str(Path(img_path).parent /
                                        (Path(img_path).stem + "_detected.png"))
                    itype      = result["image_type"]
                    n_expected = len(result["features"].get("circles", []) or
                                     result["features"].get("holes", []) or [1])
                    verification = verifier(
                        annotated_image_path=annotated_path,
                        image_type=itype,
                        detection_result=result["features"],
                        n_expected=n_expected,
                        always=args.verify_always,
                    )

                rows = results_to_rows(cartridge_id, {result["image_type"]: result})

                # Stamp verification onto rows
                if verification:
                    from verify_features import add_verification_to_rows
                    rows = add_verification_to_rows(rows, verification)

                all_rows.extend(rows)

                if result["overall_pass"]:
                    n_pass += 1
                else:
                    n_fail += 1

            except Exception as e:
                print(f"  ✗ ERROR  [{cartridge_id}]  {Path(img_path).name}: {e}")

        print("─" * 55)
        print(f"  Done: {n_pass} PASS  {n_fail} FAIL  ({len(args.images)} total)")
        export_csv(all_rows, args.csv)
        print(f"  CSV  → {args.csv}")

    elif args.folder:
        cal_path = args.cal_holes if os.path.exists(args.cal_holes) else args.cal
        if not os.path.exists(cal_path):
            sys.exit("✗ No calibration file found. Run calibrate.py first.")
        cal     = load_calibration(cal_path)
        results = detect_cartridge_folder(args.folder, cal, debug=args.debug)
        overall = all(r["overall_pass"] for r in results.values())
        print(f"\n  Folder: {'✓ PASS' if overall else '✗ FAIL'}")

        # Export CSV for single folder too
        cartridge_id = Path(args.folder).name
        rows = results_to_rows(cartridge_id, results)
        export_csv(rows, args.csv)

    elif args.batch:
        # Process all subfolders in a parent directory
        batch_dir = Path(args.batch)
        folders   = sorted([f for f in batch_dir.iterdir() if f.is_dir()])
        if not folders:
            sys.exit(f"✗ No subfolders found in {args.batch}")

        cal_path = args.cal_holes if os.path.exists(args.cal_holes) else args.cal
        if not os.path.exists(cal_path):
            sys.exit("✗ No calibration file found. Run calibrate.py first.")
        cal = load_calibration(cal_path)

        print(f"\n  Batch: {len(folders)} cartridges in {args.batch}")
        run_batch([str(f) for f in folders], cal,
                  csv_path=args.csv, debug=args.debug)
    else:
        p.print_help()



# ══════════════════════════════════════════════════════════════════════════════
# CSV EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def results_to_rows(cartridge_id: str, results: dict) -> list:
    """
    Flatten a dict of {image_type: detect_result} into a list of CSV rows.
    One row per measured feature.

    Columns:
      cartridge_id, timestamp, image_type, feature_id, feature_label,
      nominal_mm, measured_mm, deviation_mm, lower_limit, upper_limit,
      pass_fail, cx_px, cy_px, scale_um_per_px, notes
    """
    rows = []
    ts   = datetime.now().isoformat(timespec="seconds")

    for img_type, result in results.items():
        f          = result.get("features", {})
        scale_um   = round(result.get("mm_per_px", 0) * 1000, 4)
        img_path   = Path(result.get("image_path", "")).name
        cal_source = result.get("calibration_source", "")

        if img_type == "holes":
            for c in f.get("circles", []):
                rows.append({
                    "cartridge_id":   cartridge_id,
                    "timestamp":      ts,
                    "image_file":     img_path,
                    "image_type":     "holes",
                    "feature_id":     "HL01",
                    "feature_label":  f"Tag{c.get('dwg_tag','?')} diameter",
                    "nominal_mm":     0.50,
                    "measured_mm":    c["diameter_mm"],
                    "deviation_mm":   c["deviation_mm"],
                    "lower_limit_mm": 0.45,
                    "upper_limit_mm": 0.55,
                    "pass_fail":      "PASS" if c["pass"] else "FAIL",
                    "cx_px":          c.get("cx_px", ""),
                    "cy_px":          c.get("cy_px", ""),
                    "scale_um_per_px":scale_um,
                    "calibration_source": cal_source,
                    "notes":          f"outside_image" if c.get("outside_image") else "",
                })
            # Missing holes (outside image / not detected)
            for m in f.get("missing_holes", []):
                rows.append({
                    "cartridge_id":   cartridge_id,
                    "timestamp":      ts,
                    "image_file":     img_path,
                    "image_type":     "holes",
                    "feature_id":     "HL01",
                    "feature_label":  f"Tag{m['dwg_tag']} diameter",
                    "nominal_mm":     0.50,
                    "measured_mm":    "",
                    "deviation_mm":   "",
                    "lower_limit_mm": 0.45,
                    "upper_limit_mm": 0.55,
                    "pass_fail":      "NOT_MEASURED",
                    "cx_px":          "",
                    "cy_px":          "",
                    "scale_um_per_px":scale_um,
                    "calibration_source": cal_source,
                    "notes":          m.get("reason", ""),
                })

        elif img_type == "dab":
            rows.append({
                "cartridge_id":   cartridge_id,
                "timestamp":      ts,
                "image_file":     img_path,
                "image_type":     "dab",
                "feature_id":     "HL01",
                "feature_label":  "DAB hole diameter",
                "nominal_mm":     0.50,
                "measured_mm":    f.get("diameter_mm", ""),
                "deviation_mm":   f.get("deviation_mm", ""),
                "lower_limit_mm": 0.45,
                "upper_limit_mm": 0.55,
                "pass_fail":      "PASS" if f.get("pass") else "FAIL",
                "cx_px":          f.get("cx_px", ""),
                "cy_px":          f.get("cy_px", ""),
                "scale_um_per_px":scale_um,
                "calibration_source": cal_source,
                "notes":          "",
            })

        elif img_type == "mixing":
            for hole in f.get("holes", []):
                rows.append({
                    "cartridge_id":   cartridge_id,
                    "timestamp":      ts,
                    "image_file":     img_path,
                    "image_type":     "mixing",
                    "feature_id":     "HL01",
                    "feature_label":  f"{hole['id']} diameter",
                    "nominal_mm":     0.50,
                    "measured_mm":    hole["diameter_mm"],
                    "deviation_mm":   hole["deviation_mm"],
                    "lower_limit_mm": 0.45,
                    "upper_limit_mm": 0.55,
                    "pass_fail":      "PASS" if hole["pass"] else "FAIL",
                    "cx_px":          hole.get("cx_px", ""),
                    "cy_px":          hole.get("cy_px", ""),
                    "scale_um_per_px":scale_um,
                    "calibration_source": cal_source,
                    "notes":          "",
                })

        elif img_type == "neck":
            if "error" not in f:
                val = f.get("trimmed_mean_mm", f.get("mean_width_mm", ""))
                tol = f.get("tolerance", {})
                rows.append({
                    "cartridge_id":   cartridge_id,
                    "timestamp":      ts,
                    "image_file":     img_path,
                    "image_type":     "neck",
                    "feature_id":     "CH05",
                    "feature_label":  "Neck width (0.20mm)",
                    "nominal_mm":     0.20,
                    "measured_mm":    val,
                    "deviation_mm":   tol.get("deviation_mm", ""),
                    "lower_limit_mm": 0.15,
                    "upper_limit_mm": 0.25,
                    "pass_fail":      "PASS" if tol.get("pass") else "FAIL",
                    "cx_px":          "",
                    "cy_px":          "",
                    "scale_um_per_px":scale_um,
                    "calibration_source": cal_source,
                    "notes":          f"trimmed_mean of {f.get('n_medial_pts',0)} medial pts",
                })

    return rows


def export_csv(all_rows: list, output_path: str):
    """Write all measurement rows to a CSV file."""
    import csv
    if not all_rows:
        print("  ⚠  No rows to export.")
        return

    fieldnames = [
        "cartridge_id", "timestamp", "image_file", "image_type",
        "feature_id", "feature_label",
        "nominal_mm", "measured_mm", "deviation_mm",
        "lower_limit_mm", "upper_limit_mm", "pass_fail",
        "cx_px", "cy_px", "scale_um_per_px", "calibration_source", "notes",
        "claude_triggered", "claude_verified", "claude_confidence", "claude_notes",
    ]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"  CSV saved → {output_path}  ({len(all_rows)} rows)")


def run_batch(folders: list, calibration: dict,
              csv_path: str = "qc_results.csv",
              debug: bool = False,
              calibration_mode: str = "json") -> list:
    """
    Process multiple cartridge folders and export a combined CSV.

    Parameters
    ----------
    folders          : list of folder paths, one per cartridge
    calibration       : loaded calibration dict
    csv_path          : output CSV filename
    debug             : save annotated images per image
    calibration_mode  : "json" (default) | "metadata" | "auto" -- see
                        leica_calibration.resolve_scale_factor

    Returns
    -------
    List of all measurement rows
    """
    all_rows = []

    for folder in folders:
        folder_path = Path(folder)
        cartridge_id = folder_path.name   # use folder name as cartridge ID
        print(f"\n  Cartridge: {cartridge_id}")

        results = detect_cartridge_folder(str(folder_path), calibration, debug=debug,
                                           calibration_mode=calibration_mode)
        overall = all(r["overall_pass"] for r in results.values())
        print(f"  Result   : {'✓ PASS' if overall else '✗ FAIL'}")

        rows = results_to_rows(cartridge_id, results)
        all_rows.extend(rows)

    export_csv(all_rows, csv_path)
    return all_rows


if __name__ == '__main__':
    main()