"""
experimental_intact_wall.py
===========================
EXPERIMENTAL / DIAGNOSTIC ONLY -- not used by any production code path.

Intact-wall diameter of a Tag / MX hole, modelled as a CIRCULAR BORE WITH
LOCALISED DEFECTS (flash, burr, debris intruding into the aperture), not as
an ellipse.

Method (spatial distribution of the wall points):
  1. Starting from the production fitted centre, cast N_RAYS wall-edge rays
     with the production ray caster (detect_features._cast_edge_rays) and keep
     the near-nominal hits, exactly as production does.
  2. The intact bore is the largest set of wall points that lie on ONE common
     circle. Candidate circles come from deterministic, spatially spread point
     triplets (three points ~120 deg apart, every starting ray); each is scored
     by how many points lie within INLIER_BAND_PX of it.
  3. The best-supported circle is refined by least squares on its inliers;
     the band is then max(INLIER_BAND_PX, 3 x fit RMS) and the fit repeated.
  4. Points INSIDE the circle beyond the band are intrusions (grouped into
     contiguous angular runs); points OUTSIDE are escapes (e.g. channel
     openings) -- neither is used for the fit.

Status:
  OK         intact wall identified
  AMBIGUOUS  intact wall covers < MIN_INTACT_FRACTION of the hit rays, leaves
             an angular gap > MAX_INTACT_GAP_DEG, a competing circle of a
             clearly different radius has >= COMPETING_SUPPORT of the support,
             or >= LARGER_CONCENTRIC of the points lie on a LARGER concentric
             circle (intrusions can only shrink the aperture)
  FAILED     too few wall points / no plausible circle

All parameters are fixed a priori (edge-noise level of clean production holes,
geometric coverage) -- none is tuned against the manual workbook.
"""
from pathlib import Path

import cv2
import numpy as np

import detect_features as df

N_RAYS              = 360
INLIER_BAND_PX      = 2.5    # ~2.3 sigma of the ~1.1 px wall-fit RMS of clean production holes
MIN_INTACT_FRACTION = 0.50   # intact wall must be the majority of the hit rays
MAX_INTACT_GAP_DEG  = 180.0  # ... and must not leave more than half the circle unsupported
COMPETING_SUPPORT   = 0.80   # a different-radius circle with >= 80 % of the support -> ambiguous
COMPETING_DR_PX     = 5.0    # 'clearly different radius'
LARGER_CONCENTRIC   = 0.25   # intrusions only SHRINK the aperture: >= 25 % of points on a larger
                             # concentric circle (channel openings cover ~10 %) -> the bore is ambiguous
MIN_POINTS          = 20


def _circle3(p1, p2, p3):
    (x1, y1), (x2, y2), (x3, y3) = p1, p2, p3
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9:
        return None
    s1, s2, s3 = x1 * x1 + y1 * y1, x2 * x2 + y2 * y2, x3 * x3 + y3 * y3
    ux = (s1 * (y2 - y3) + s2 * (y3 - y1) + s3 * (y1 - y2)) / d
    uy = (s1 * (x3 - x2) + s2 * (x1 - x3) + s3 * (x2 - x1)) / d
    return ux, uy, float(np.hypot(x1 - ux, y1 - uy))


def _lsq_circle(x, y):
    A = np.column_stack([2 * x, 2 * y, np.ones(len(x))])
    s = np.linalg.lstsq(A, x ** 2 + y ** 2, rcond=None)[0]
    return s[0], s[1], float(np.sqrt(s[2] + s[0] ** 2 + s[1] ** 2))


def _runs(mask_sorted):
    """Contiguous True runs on a circular sequence -> list of (start, length)."""
    n = len(mask_sorted)
    if n == 0 or not mask_sorted.any():
        return []
    if mask_sorted.all():
        return [(0, n)]
    start = int(np.argmin(mask_sorted))          # begin at a False so runs don't wrap
    m = np.roll(mask_sorted, -start)
    runs, i = [], 0
    while i < n:
        if m[i]:
            j = i
            while j < n and m[j]:
                j += 1
            runs.append(((i + start) % n, j - i))
            i = j
        else:
            i += 1
    return runs


def intact_wall_diameter(gray, centre_xy, nominal_r, threshold, mm_per_px):
    """
    Experimental intact-wall diameter. Returns a dict with status, diameters
    (px and mm), the accepted wall points, rejected intrusion / escape points
    and reasons. Never raises for image content.
    """
    cx0, cy0 = centre_xy
    ox, oy = int(round(cx0)), int(round(cy0))
    ang, hit, edge = df._cast_edge_rays(gray, ox, oy, nominal_r, threshold, N_RAYS)
    near = (hit >= 0.65 * nominal_r) & (hit <= 1.30 * nominal_r) if len(hit) else np.zeros(0, bool)
    x = ox + edge[near] * np.cos(ang[near])
    y = oy + edge[near] * np.sin(ang[near])
    out = {"status": "FAILED", "n_rays": N_RAYS, "n_points": int(len(x)), "reasons": [],
           "points_xy": np.column_stack([x, y]).tolist()}
    if len(x) < MIN_POINTS:
        out["reasons"].append(f"only {len(x)} wall points")
        return out

    # 2. consensus over spatially spread triplets (deterministic)
    order = np.argsort(np.arctan2(y - oy, x - ox))
    x, y = x[order], y[order]
    n = len(x)
    pts = np.column_stack([x, y])
    best, cands = None, []
    for i in range(n):
        for k in (n // 3, n // 4):
            c = _circle3(pts[i], pts[(i + k) % n], pts[(i + 2 * k) % n])
            if c is None or not (0.65 * nominal_r <= c[2] <= 1.30 * nominal_r):
                continue
            if np.hypot(c[0] - cx0, c[1] - cy0) > 0.5 * nominal_r:
                continue
            res = np.hypot(x - c[0], y - c[1]) - c[2]
            support = int(np.sum(np.abs(res) <= INLIER_BAND_PX))
            cands.append((support, c))
            if best is None or support > best[0]:
                best = (support, c)
    if best is None:
        out["reasons"].append("no plausible circle through the wall points")
        return out

    # 3. refine on inliers (band widened to 3 x RMS if the wall is noisier)
    cx, cy, R = best[1]
    band = INLIER_BAND_PX
    for _ in range(3):
        res = np.hypot(x - cx, y - cy) - R
        inl = np.abs(res) <= band
        if inl.sum() < MIN_POINTS:
            break
        cx, cy, R = _lsq_circle(x[inl], y[inl])
        res = np.hypot(x - cx, y - cy) - R
        rms = float(np.sqrt(np.mean(res[np.abs(res) <= band] ** 2)))
        band = max(INLIER_BAND_PX, 3 * rms)
    res = np.hypot(x - cx, y - cy) - R
    inl = np.abs(res) <= band
    intr = res < -band
    esc = res > band
    rms = float(np.sqrt(np.mean(res[inl] ** 2))) if inl.any() else float("nan")

    # 4. coverage / ambiguity checks
    th = np.degrees(np.arctan2(y - cy, x - cx)) % 360
    th_in = np.sort(th[inl])
    gaps = np.diff(np.r_[th_in, th_in[:1] + 360]) if len(th_in) else np.array([360.0])
    max_gap = float(gaps.max())
    frac = float(inl.mean())
    competitors = [s for s, c in cands if abs(c[2] - R) > COMPETING_DR_PX]
    comp = max(competitors) / max(best[0], 1) if competitors else 0.0
    if frac < MIN_INTACT_FRACTION:
        out["reasons"].append(f"intact wall only {frac:.0%} of hit rays")
    if max_gap > MAX_INTACT_GAP_DEG:
        out["reasons"].append(f"intact wall leaves a {max_gap:.0f} deg gap")
    larger = [sup for sup, c in cands
              if c[2] > R + COMPETING_DR_PX and np.hypot(c[0] - cx, c[1] - cy) <= COMPETING_DR_PX]
    larger_frac = max(larger) / n if larger else 0.0
    if larger_frac >= LARGER_CONCENTRIC:
        out["reasons"].append(f"{larger_frac:.0%} of wall points lie on a larger concentric circle "
                              f"(possible uniform-depth intrusion ring)")
    if comp >= COMPETING_SUPPORT:
        out["reasons"].append(f"competing circle (radius differs > {COMPETING_DR_PX:.0f}px) has {comp:.0%} of the support")

    intr_runs = _runs(intr)
    out.update({
        "status": "AMBIGUOUS" if out["reasons"] else "OK",
        "intact_diameter_px": round(2 * R, 2),
        "intact_diameter_mm": round(2 * R * mm_per_px, 5),
        "centre_xy": (round(float(cx), 2), round(float(cy), 2)),
        "fit_rms_px": round(rms, 2),
        "inlier_band_px": round(band, 2),
        "intact_fraction": round(frac, 3),
        "intrusion_fraction": round(float(intr.mean()), 3),
        "escape_fraction": round(float(esc.mean()), 3),
        "max_intact_gap_deg": round(max_gap, 1),
        "competing_support": round(comp, 2),
        "larger_concentric_fraction": round(larger_frac, 3),
        "n_intrusion_runs": len(intr_runs),
        "largest_intrusion_run_deg": round(max((l for _, l in intr_runs), default=0) * 360.0 / N_RAYS, 1),
        "max_intrusion_depth_px": round(float(-res[intr].min()), 1) if intr.any() else 0.0,
        "points_xy": pts.tolist(),
        "point_class": np.where(inl, "wall", np.where(intr, "intrusion", "escape")).tolist(),
    })
    return out


def annotate_intact_wall(gray, result, production_diameter_px=None, label="", scale=3):
    """Crop overlay: accepted wall points (green), intrusions (red), escapes
    (orange), fitted intact circle (cyan), production circle-equivalent
    (yellow, same centre for comparison) and the status/reasons."""
    if "centre_xy" not in result:
        c = np.mean(np.array(result["points_xy"]), 0) if result["points_xy"] else (gray.shape[1] / 2, gray.shape[0] / 2)
        cx, cy, R = c[0], c[1], 110.0
    else:
        (cx, cy), R = result["centre_xy"], result["intact_diameter_px"] / 2
    half = int(R * 1.5)
    x0, y0 = int(cx) - half, int(cy) - half
    crop = gray[max(0, y0):y0 + 2 * half, max(0, x0):x0 + 2 * half]
    out = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR), None, fx=scale, fy=scale,
                     interpolation=cv2.INTER_NEAREST)
    P = lambda px, py: (int(round((px - max(0, x0)) * scale)), int(round((py - max(0, y0)) * scale)))  # noqa: E731
    if "centre_xy" in result:
        cv2.circle(out, P(cx, cy), int(R * scale), (255, 220, 0), 2, cv2.LINE_AA)
        if production_diameter_px:
            cv2.circle(out, P(cx, cy), int(production_diameter_px / 2 * scale), (0, 220, 255), 1, cv2.LINE_AA)
    cols = {"wall": (0, 220, 80), "intrusion": (60, 60, 255), "escape": (0, 165, 255)}
    for (px, py), k in zip(result["points_xy"], result.get("point_class", ["wall"] * len(result["points_xy"]))):
        cv2.circle(out, P(px, py), 4, cols[k], -1)
    lines = [f"{label}  intact-wall: {result['status']}"]
    if "intact_diameter_mm" in result:
        lines.append(f"cyan intact-wall d={result['intact_diameter_px']:.1f}px = {result['intact_diameter_mm']:.4f} mm"
                     f"  rms {result['fit_rms_px']}px")
        if production_diameter_px:
            lines.append(f"yellow production circle-equivalent d={production_diameter_px:.1f}px")
        lines.append(f"green wall {result['intact_fraction']:.0%}  red intrusion {result['intrusion_fraction']:.0%}"
                     f" ({result['n_intrusion_runs']} runs, max depth {result['max_intrusion_depth_px']}px)"
                     f"  orange escape {result['escape_fraction']:.0%}")
    lines += [f"reason: {r}" for r in result["reasons"]]
    for i, t in enumerate(lines):
        cv2.putText(out, t, (10, 28 + 28 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.putText(out, t, (10, 28 + 28 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return out
