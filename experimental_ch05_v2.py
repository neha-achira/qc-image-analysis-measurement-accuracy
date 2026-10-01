"""
experimental_ch05_v2.py
=======================
EXPERIMENTAL CH05 v2 neck width -- NOT PRODUCTION.

Not used by any production code path. Production neck = detect_features.detect_neck
(legacy, provisional); the frozen experimental detector
(detect_features.detect_neck_experimental, narrowest point) is unchanged. This
module exists alongside both so the methods can be compared.

LOCATION (from the operator reference Neck.png and the validated diagnostics)
  1. The two solid wall bands (same extraction as the frozen detector).
  2. Centreline = bisector of the two bands, traced past the neck ends.
  3. Neck ends = where the band-to-band gap first exceeds NECK_END_K x the core
     gap (median within +-CORE_WIN px of the narrowest band gap), walking out
     from the narrowest band gap.
  4. Midpoint = halfway (arc length) between the ends.
  5. CH05 section = midpoint + SECTION_OFFSET_PX toward the image lower-left
     (the position of the operator's 203.79 um line in Neck.png relative to the
     midpoint, transferred to the 10 strongly registered BPs: +96 px, sd 2.9).

BOUNDARY (per side, on profiles perpendicular to the local centreline)
  - J = start of the solid wall band (dark run >= NECK_SOLID_RUN_PX at
    <= W + 0.2 (F - W)), as in the frozen detector.
  - Group A: floor -> wall descent at W + 0.30 (F - W) (frozen A rule).
  - Group B: if a thin bright line, with a dark strip immediately inside it,
    is present on >= LINE_MAJORITY of the wall over +-NEIGH_HALF px, the
    boundary is the line's outer edge at W + 0.30 (line peak - W). Profiles
    where that line is missing count as missing (never a jump to the floor edge).
  - Not measured (no value forced) when: < MIN_VALID of the 5 section profiles
    have both boundaries; the bright line is intermittent (A/B ambiguous);
    the wall edge is ragged (flash/burr); > 25 % of the wall profiles around the
    section lie > 3 px off the robust wall line (burr/flash) -- burr-affected
    profiles are never used as the boundary, and < 3 clean section profiles
    means NOT_MEASURED; the section boundary lies > 4 px inside the wall line
    interpolated from 48-120 px either side (burr spanning the section); the
    section is off the wall trend (local burr); a
    single-edged wall has a flash film between floor and wall;
    the wall is not perpendicular to the section; the neck ends/section are
    not found.

MEASUREMENT
  width_px = median over the 5 profiles at section +-8 px (every 4 px) of the
  perpendicular boundary-to-boundary distance. The mm value uses the OBSERVED
  image scale (Leica scale bar, 2.587 um/px) and is labelled experimental; it
  is not the production neck calibration and does not drive PASS/FAIL.

All thresholds are fixed a priori (frozen-detector constants where they exist);
none is tuned against the manual workbook or the 0.20 mm nominal.
"""
import cv2
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.signal import find_peaks

import detect_features as _df   # read-only use of constants and the seam helper

METHOD = "experimental CH05 v2 (NOT production)"
OBSERVED_UM_PER_PX = 2.587       # Leica scale bar in Neck_ch00.png (calibration.json neck.observed_image_scale)

STEP_ALONG = 4.0                 # centreline sampling (px)
TRACE_OPEN = 3.0                 # trace the centreline to 3 x the typical band gap (past the neck ends)
MAX_GAP_PX = 60.0                # largest bisector gap bridged along the neck
CORE_WIN = 150.0                 # core band gap = median within +-150 px of the narrowest band gap
NECK_END_K = 1.5                 # neck end = band gap > 1.5 x core
SECTION_OFFSET_PX = 96.0         # midpoint -> CH05 section, toward the lower-left
SECTION_OFFSETS = (-8.0, -4.0, 0.0, 4.0, 8.0)
NEIGH_HALF = 40.0                # wall-continuity window around the section
MIN_VALID = 3                    # of the 5 section profiles
STEP = 0.5                       # sampling along a profile (px)
LEVEL = 0.30                     # boundary level (frozen A rule; relative to the structure for B)
LINE_PROM, LINE_MAXW = 0.15, 6.0 # thin bright line: prominence (x floor-wall contrast), max half-height width
DIP_LEVEL, LOOKBACK = 0.30, 24.0 # dark strip just inside the line; search window before the solid band
LINE_MAJORITY = 0.60             # line on >= 60 % of the wall profiles -> B side
COINCIDE_PX = 2.0                # A and B candidates closer than this are the same boundary
RAGGED_MAD = 1.5                 # wall-edge MAD (px) above which the edge is ragged (flash/burr)
BURR_DEV = 3.0                   # boundary off the robust wall line (px) -> burr/flash-affected profile
MAX_BURR_FRACTION = 0.25         # > 25 % burr-affected profiles around the section -> wall line not trustworthy
OUTER_OFFSETS = tuple(float(o) for o in list(range(-120, -47, 8)) + list(range(48, 121, 8)))
INTRUSION_PX = 4.0               # section boundary > BURR_DEV + 1 px inside the wall line interpolated from
                                 # 48-120 px either side -> burr spanning the section (real clean parts: <= 2.9 px)
MAX_ANGLE = 10.0                 # wall direction vs perpendicular (deg)
STRIP_FLASH_PX = 8.0             # single-edged wall: >= 8 px darker material before the wall = flash film
STRIP_DOUBLE_PX = 20.0           # double-edged (B) wall: dark strip >= 20 px


# ── geometry ────────────────────────────────────────────────────────────────
def _valid_mask(gray):
    h = gray.shape[0]
    valid = gray > 2
    valid[h - _df.NECK_SCALEBAR_ROWS:] = False
    return valid


def _wall_band_distances(gray, valid):
    """Distance maps to the two largest solid dark bands (frozen-detector extraction)."""
    h, w = gray.shape
    sm = cv2.GaussianBlur(gray, (0, 0), 2).astype(np.float32)
    W0, F0 = np.percentile(sm[valid], 5), np.median(sm[valid])
    dark = ((sm < W0 + 0.3 * (F0 - W0)) & valid).astype(np.uint8)
    dark[h - _df.NECK_SCALEBAR_ROWS:] = 0
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_df.NECK_WALL_OPEN_PX, _df.NECK_WALL_OPEN_PX))
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, k)
    n, lab, st, _ = cv2.connectedComponentsWithStats(dark)
    if n < 3:
        return None, "two wall bands not found"
    big = np.argsort(st[1:, cv2.CC_STAT_AREA])[::-1][:2] + 1
    if st[big[1], cv2.CC_STAT_AREA] < 0.01 * h * w:
        return None, "second wall band too small"
    A, B = lab == big[0], lab == big[1]
    dA = cv2.distanceTransform((~A).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    dB = cv2.distanceTransform((~B).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    return (dA, dB), None


def _centreline(gray, valid):
    """Smoothed band bisector, resampled every STEP_ALONG px of arc length;
    +s runs toward the image lower-left."""
    h, w = gray.shape
    bands, why = _wall_band_distances(gray, valid)
    if bands is None:
        return None, why
    dA, dB = bands
    mid = valid & (np.abs(dA - dB) <= 0.75) & (dA + dB < 0.5 * min(h, w))
    ys, xs = np.nonzero(mid)
    if len(xs) < 50:
        return None, "no channel between the wall bands"
    cwp = (dA + dB)[ys, xs]
    keep = cwp <= TRACE_OPEN * np.percentile(cwp, 10)
    P = np.column_stack([xs[keep], ys[keep]]).astype(float)
    cwp = cwp[keep]
    c = P.mean(0)
    u = np.linalg.svd(P - c)[2][0]
    if u[0] > 0:
        u = -u
    perp = np.array([-u[1], u[0]])
    t, v = (P - c) @ u, (P - c) @ perp
    T, V, CW = [], [], []
    for b0 in np.arange(np.floor(t.min()), t.max(), STEP_ALONG):
        m = (t >= b0) & (t < b0 + STEP_ALONG)
        if m.sum() >= 2:
            T.append(b0 + STEP_ALONG / 2); V.append(np.median(v[m])); CW.append(np.median(cwp[m]))
    if len(T) < 20:
        return None, "centreline too short"
    T, V, CW = map(np.array, (T, V, CW))
    # bridge bisector gaps up to MAX_GAP_PX (a ragged/flashed band edge can leave holes in the
    # 1-px bisector; the resampling below interpolates across them)
    runs = np.split(np.arange(len(T)), np.nonzero(np.diff(T) > MAX_GAP_PX)[0] + 1)
    r = max(runs, key=len)
    T, V, CW = T[r], V[r], CW[r]
    k = 9
    Vs = np.convolve(np.pad(V, k // 2, mode="edge"), np.ones(k) / k, "valid")
    pts = c + T[:, None] * u + Vs[:, None] * perp
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    s = np.arange(0, seg[-1], STEP_ALONG)
    pts = np.column_stack([np.interp(s, seg, pts[:, 0]), np.interp(s, seg, pts[:, 1])])
    cw = np.interp(s, seg, CW)
    tan = np.gradient(pts, axis=0)
    tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    return {"s": s, "pts": pts, "tan": tan, "cw": cw}, None


def _frame(cl, s_val):
    """Centre point, unit tangent, unit normal and band gap at arc length s_val."""
    s = cl["s"]
    p = np.array([np.interp(s_val, s, cl["pts"][:, 0]), np.interp(s_val, s, cl["pts"][:, 1])])
    t = np.array([np.interp(s_val, s, cl["tan"][:, 0]), np.interp(s_val, s, cl["tan"][:, 1])])
    t /= np.linalg.norm(t)
    return p, t, np.array([-t[1], t[0]]), float(np.interp(s_val, s, cl["cw"]))


# ── boundary ───────────────────────────────────────────────────────────────
def _side_boundary(qv, F, W):
    """Profile from the centreline outward. Returns ({A, B, line, solid, inner}, None)
    with distances in px (A/B None when that candidate is absent) or (None, reason)."""
    if F - W < _df.NECK_MIN_CONTRAST:
        return None, "low floor/wall contrast"
    run = int(_df.NECK_SOLID_RUN_PX / STEP)
    solid = (qv <= W + 0.2 * (F - W)).astype(int)
    full = np.nonzero(np.convolve(solid, np.ones(run, int), "valid") == run)[0]
    if not len(full):
        return None, "solid wall not reached"
    J = int(full[0])

    def crossing(start, P):
        L = W + LEVEL * (P - W)
        above = np.nonzero(qv[start:J + 1] > L)[0]
        if not len(above):
            return None
        k = start + int(above[-1])
        if k + 1 >= len(qv):
            return None
        frac = (qv[k] - L) / max(qv[k] - qv[k + 1], 1e-6)
        return (k + min(max(frac, 0.0), 1.0)) * STEP

    below = np.nonzero(qv[:J + 1] < W + 0.5 * (F - W))[0]
    out = {"solid": J * STEP, "A": crossing(0, F), "B": None, "line": None,
           "inner": float(below[0] * STEP) if len(below) else None}
    a0 = max(0, J - int(LOOKBACK / STEP))
    pk, _ = find_peaks(qv[a0:J + 1], prominence=LINE_PROM * (F - W),
                       width=(None, LINE_MAXW / STEP), rel_height=0.5)
    dark = W + DIP_LEVEL * (F - W)
    for p in pk[::-1]:                              # outermost line (closest to the wall band) first
        P_idx = a0 + int(p)
        inside = np.nonzero(qv[:P_idx][::-1] <= dark)[0]
        if len(inside) and inside[0] * STEP <= LOOKBACK:
            out["B"] = crossing(P_idx, float(qv[P_idx]))
            out["line"] = P_idx * STEP
            break
    return out, None


def _cross_section(g, valid, seam, c, t, n, cw):
    """Boundaries on both sides of one perpendicular profile (side -1 = -normal)."""
    h, w = g.shape
    q = np.arange(0, 0.5 * cw + 60, STEP)
    profs = []
    for sgn in (-1, 1):
        xs, ys = c[0] + sgn * q * n[0], c[1] + sgn * q * n[1]
        if xs.min() < 0 or ys.min() < 0 or xs.max() > w - 1 or ys.max() > h - 1:
            return None
        profs.append(np.mean([map_coordinates(g, [ys + k * t[1], xs + k * t[0]], order=1)
                              for k in range(-4, 5)], axis=0))
    centre = np.r_[profs[0][: int(0.4 * cw / STEP)], profs[1][: int(0.4 * cw / STEP)]]
    F = float(np.percentile(centre, 75))
    W = float(np.percentile(np.r_[profs[0], profs[1]], 5))
    res = {}
    for sgn, prof in zip((-1, 1), profs):
        b, why = _side_boundary(prof, F, W)
        if b is not None:
            for key in ("A", "B"):
                if b[key] is not None:
                    p = c + sgn * b[key] * n
                    yi, xi = int(round(p[1])), int(round(p[0]))
                    if not (0 <= yi < h and 0 <= xi < w and valid[yi, xi]):
                        b[key], why = None, "boundary in padding"
                    elif seam is not None and abs(p[1] - seam) <= _df.NECK_SEAM_EXCLUDE_PX:
                        b[key], why = None, "boundary on tile seam"
        res[sgn] = (b, why)
    return res


# ── detector ───────────────────────────────────────────────────────────────
def detect_neck_ch05_v2(gray, observed_um_per_px=OBSERVED_UM_PER_PX):
    """
    EXPERIMENTAL CH05 v2 (NOT production). gray: neck image (uint8, 2-D).
    Returns a dict with status RELIABLE_A | PROVISIONAL_B | NOT_MEASURED,
    width_px, width_mm_experimental (observed scale), geometry and reasons.
    """
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    g = gray.astype(np.float32)
    valid = _valid_mask(gray)
    seam = _df._neck_seam_row(gray, valid)
    base = {"method": METHOD, "production": False, "observed_um_per_px": observed_um_per_px,
            "section_offset_px": SECTION_OFFSET_PX, "seam_row": seam}

    def not_measured(cause, reasons, **extra):
        return {**base, "status": "NOT_MEASURED", "not_measured": True, "cause": cause,
                "reasons": reasons, "width_px": None, "width_mm_experimental": None, **extra}

    cl, why = _centreline(gray, valid)
    if cl is None:
        return not_measured("geometry", [why])
    s, cw = cl["s"], cl["cw"]
    k_band = int(np.argmin(np.convolve(cw, np.ones(5) / 5, "same")[2:-2])) + 2
    S = s - s[k_band]
    core = float(np.median(cw[np.abs(S) <= CORE_WIN]))
    inside = cw <= NECK_END_K * core
    lo = hi = k_band
    while lo > 0 and inside[lo - 1]:
        lo -= 1
    while hi < len(S) - 1 and inside[hi + 1]:
        hi += 1
    geo = {"centreline_px": cl["pts"].round(1).tolist(), "core_band_gap_px": round(core, 2),
           "neck_ends_xy": [cl["pts"][lo].round(1).tolist(), cl["pts"][hi].round(1).tolist()],
           "neck_end_gaps_px": [round(float(cw[lo]), 1), round(float(cw[hi]), 1)],
           "neck_length_px": round(float(S[hi] - S[lo]), 1)}
    if lo == 0 or hi == len(S) - 1:
        return not_measured("geometry", ["neck end not reached within the traced centreline"], **geo)
    s_mid = s[k_band] + (S[lo] + S[hi]) / 2
    s_sec = s_mid + SECTION_OFFSET_PX
    mid_c, mid_t, mid_n, mid_cw = _frame(cl, s_mid)
    geo.update(midpoint_xy=mid_c.round(1).tolist(), midpoint_band_gap_px=round(mid_cw, 1))
    if not (s[lo] + NEIGH_HALF <= s_sec <= s[hi] - NEIGH_HALF):
        return not_measured("geometry", ["CH05 section not inside the neck"], **geo)
    sec_c, sec_t, sec_n, sec_cw = _frame(cl, s_sec)
    geo.update(section_xy=sec_c.round(1).tolist())
    # image side names: the side whose outward direction points up in the image is the upper wall
    side_name = {sgn: ("upper_wall" if (sgn * sec_n)[1] < 0 else "lower_wall") for sgn in (-1, 1)}

    neigh = []
    for off in np.arange(-NEIGH_HALF, NEIGH_HALF + 1e-6, STEP_ALONG):
        c, t, n, cwl = _frame(cl, s_sec + off)
        r = _cross_section(g, valid, seam, c, t, n, cwl)
        neigh.append({"off": float(off), "c": c, "n": n, "res": r})
    sec = [p for p in neigh if any(abs(p["off"] - o) < 1e-6 for o in SECTION_OFFSETS)]

    sides, flags = {}, []
    for sgn in (-1, 1):
        name = side_name[sgn]
        have = [p for p in neigh if p["res"] and p["res"][sgn][0]]
        n_line = sum(1 for p in have if p["res"][sgn][0]["B"] is not None)
        kind = "B" if have and n_line >= LINE_MAJORITY * len(have) else "A"
        info = {"kind": kind, "line_fraction": round(n_line / max(len(have), 1), 2), "flags": []}
        trend = [(p["off"], p["res"][sgn][0][kind]) for p in have if p["res"][sgn][0][kind] is not None]
        # robust wall line: fit, drop points > BURR_DEV off it, refit. Profiles off the final
        # line by > BURR_DEV are burr/flash-affected and are never used as the boundary.
        burr_offs, fit = set(), None
        if len(trend) >= 8:
            x, y = np.array(trend).T
            keep = np.ones(len(x), bool)
            for _ in range(3):
                fit = np.polyfit(x[keep], y[keep], 1)
                new = np.abs(y - np.polyval(fit, x)) <= BURR_DEV
                if new.sum() < 8 or (new == keep).all():
                    break
                keep = new
            burr_offs = {float(o) for o, r_ in zip(x, y - np.polyval(fit, x)) if abs(r_) > BURR_DEV}
            info["burr_fraction"] = round(len(burr_offs) / len(trend), 2)
        info["burr_offsets_px"] = sorted(burr_offs)
        good = [p for p in sec if p["res"] and p["res"][sgn][0] and p["res"][sgn][0][kind] is not None
                and p["off"] not in burr_offs]
        info["n_section_valid"] = f"{len(good)}/{len(sec)}"
        if len(good) < MIN_VALID:
            why = sorted({"burr/flash at the section" if p["off"] in burr_offs else
                          ((p["res"][sgn][1] if p["res"] else "profile leaves image") or
                           ("no bright line" if kind == "B" else "no floor edge"))
                          for p in sec if p not in good})
            info["flags"].append(f"boundary not found ({', '.join(why)})")
            sides[name] = info
            continue
        both = [abs(p["res"][sgn][0]["A"] - p["res"][sgn][0]["B"]) for p in have
                if p["res"][sgn][0]["A"] is not None and p["res"][sgn][0]["B"] is not None]
        strips = [p["res"][sgn][0][kind] - p["res"][sgn][0]["inner"] for p in good
                  if p["res"][sgn][0]["inner"] is not None]
        info["dark_strip_px"] = round(float(np.median(strips)), 1) if strips else None
        info["d_px"] = round(float(np.median([p["res"][sgn][0][kind] for p in good])), 2)
        info["solid_band_px"] = round(float(np.median([p["res"][sgn][0]["solid"] for p in good])), 2)
        if 0.25 < info["line_fraction"] < LINE_MAJORITY and not (both and np.median(both) <= COINCIDE_PX):
            info["flags"].append(f"bright line on only {info['line_fraction']:.0%} of the wall -- "
                                 "group-B boundary ambiguous")
        if fit is not None:
            x, y = np.array(trend).T
            res = y - np.polyval(fit, x)
            mad = float(np.median(np.abs(res - np.median(res))))
            if info["burr_fraction"] > MAX_BURR_FRACTION:
                info["flags"].append(f"burr/flash on {info['burr_fraction']:.0%} of the wall around the section "
                                     f"(> {BURR_DEV:g}px off the wall line)")
            dev = float(info["d_px"] - np.polyval(fit, 0.0))
            ang = float(np.degrees(np.arctan(fit[0])))
            info.update(edge_mad_px=round(mad, 2), section_dev_px=round(dev, 2), wall_angle_deg=round(ang, 1))
            if mad > RAGGED_MAD:
                info["flags"].append(f"ragged wall edge (MAD {mad:.1f}px) -- flash/burr")
            if abs(dev) > BURR_DEV:
                info["flags"].append(f"section {dev:+.1f}px off the wall trend -- local burr")
            if abs(ang) > MAX_ANGLE:
                info["flags"].append(f"wall {ang:+.0f} deg from perpendicular")
        else:
            info["flags"].append("too few wall boundaries around the section to check the edge")
        sides[name] = info

    # burr/flash spanning the whole section window: compare the section boundary (image
    # coordinates, section frame) with the wall line interpolated from 48-120 px either side.
    # A burr can only move the boundary INTO the channel.
    outer = {sgn: [] for sgn in (-1, 1)}
    for off in OUTER_OFFSETS:
        c, t, n, cwl = _frame(cl, s_sec + off)
        r = _cross_section(g, valid, seam, c, t, n, cwl)
        for sgn in (-1, 1):
            kind = sides[side_name[sgn]]["kind"]
            if r and r[sgn][0] and r[sgn][0][kind] is not None:
                p = c + sgn * r[sgn][0][kind] * n
                outer[sgn].append(((p - sec_c) @ sec_t, (p - sec_c) @ (sgn * sec_n)))
    for sgn in (-1, 1):
        sd = sides[side_name[sgn]]
        if "d_px" not in sd:
            continue
        inner = []
        for p in sec:
            if p["res"] and p["res"][sgn][0] and p["res"][sgn][0][sd["kind"]] is not None \
                    and p["off"] not in sd.get("burr_offsets_px", []):
                q = p["c"] + sgn * p["res"][sgn][0][sd["kind"]] * p["n"]
                inner.append(((q - sec_c) @ sec_t, (q - sec_c) @ (sgn * sec_n)))
        if len(outer[sgn]) < 8 or not inner:
            sd["outer_line_dev_px"] = None            # not checkable (too few outer boundaries)
            continue
        u, v = np.array(outer[sgn]).T
        fit = np.polyfit(u, v, 1)
        for _ in range(2):
            keep = np.abs(v - np.polyval(fit, u)) <= BURR_DEV
            if keep.sum() >= 6:
                fit = np.polyfit(u[keep], v[keep], 1)
        iu, iv = np.array(inner).T
        dev = float(np.median(iv - np.polyval(fit, iu)))
        sd["outer_line_dev_px"] = round(dev, 2)
        if dev < -INTRUSION_PX:
            sd["flags"].append(f"section boundary {-dev:.1f}px inside the wall line on either side "
                               "-- burr/flash spanning the section")

    double_edged = any((sd.get("dark_strip_px") or 0) >= STRIP_DOUBLE_PX or sd["kind"] == "B"
                       for sd in sides.values())
    if not double_edged:
        for sd in sides.values():
            if (sd.get("dark_strip_px") or 0) >= STRIP_FLASH_PX:
                sd["flags"].append(f"flash film between floor and wall ({sd['dark_strip_px']:.0f}px) -- flash/burr")
    flags = [f"{name}: {f}" for name, sd in sides.items() for f in sd["flags"]]

    overlay = {"neighbourhood": [{"off": p["off"], "c": p["c"].round(2).tolist(), "n": p["n"].round(4).tolist(),
                                  "d": {side_name[sg]: (None if not (p["res"] and p["res"][sg][0]) else
                                                        p["res"][sg][0][sides[side_name[sg]]["kind"]])
                                        for sg in (-1, 1)},
                                  "burr": {side_name[sg]: p["off"] in sides[side_name[sg]].get("burr_offsets_px", [])
                                           for sg in (-1, 1)}} for p in neigh]}
    result_geo = {**geo, "appearance": "B (double-edged)" if double_edged else "A", "sides": sides,
                  "overlay": overlay}
    if flags:
        flashy = any(("flash" in f or "burr" in f) for f in flags)
        cause = "group_b_ambiguous" if double_edged else ("flash" if flashy else "other")
        return not_measured(cause, flags, **result_geo)

    widths, lines = [], []
    kinds = {sgn: sides[side_name[sgn]]["kind"] for sgn in (-1, 1)}
    for p in sec:
        if p["res"] and all(p["res"][sg][0] and p["res"][sg][0][kinds[sg]] is not None for sg in (-1, 1)):
            dm, dp = p["res"][-1][0][kinds[-1]], p["res"][1][0][kinds[1]]
            widths.append(dm + dp)
            if abs(p["off"]) < 1e-6:
                lines = [(p["c"] - dm * p["n"]).round(2).tolist(), (p["c"] + dp * p["n"]).round(2).tolist()]
    if len(widths) < MIN_VALID:
        return not_measured("other", [f"only {len(widths)} section profiles with both boundaries"], **result_geo)
    if not lines:                                   # centre profile incomplete: draw at the section centre
        dm = np.median([p["res"][-1][0][kinds[-1]] for p in sec if p["res"] and p["res"][-1][0] and p["res"][-1][0][kinds[-1]] is not None])
        dp = np.median([p["res"][1][0][kinds[1]] for p in sec if p["res"] and p["res"][1][0] and p["res"][1][0][kinds[1]] is not None])
        lines = [(sec_c - dm * sec_n).round(2).tolist(), (sec_c + dp * sec_n).round(2).tolist()]
    width_px = float(np.median(widths))
    return {**base, **result_geo, "status": "PROVISIONAL_B" if double_edged else "RELIABLE_A",
            "not_measured": False, "cause": None, "reasons": [],
            "width_px": round(width_px, 2), "profile_widths_px": [round(x, 2) for x in widths],
            "width_spread_px": round(float(np.ptp(widths)), 2),
            "width_mm_experimental": round(width_px * observed_um_per_px / 1000.0, 5),
            "mm_conversion": f"observed image scale {observed_um_per_px:.4f} um/px (Leica scale bar); "
                             "experimental, not the production neck calibration",
            "measurement_line_px": lines}


# ── overlay ────────────────────────────────────────────────────────────────
def annotate_ch05_v2(gray, result, label=""):
    """Diagnostic overlay: full neck (left) + section zoom (right) + status panel."""
    if gray.ndim == 2:
        im = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    else:
        im = gray.copy()
    P = lambda p: tuple(int(round(v)) for v in p)
    BLUE, CYAN, MAG, GREEN, LBLUE, RED, YEL = ((255, 120, 0), (255, 255, 0), (255, 0, 255), (0, 220, 0),
                                               (255, 160, 60), (40, 40, 230), (0, 230, 230))
    cl = result.get("centreline_px")
    if cl:
        cv2.polylines(im, [np.array(cl, np.int32)], False, YEL, 1)
    for e, gap in zip(result.get("neck_ends_xy", []), result.get("neck_end_gaps_px", [])):
        cv2.circle(im, P(e), int(gap / 2), BLUE, 3)
    if "midpoint_xy" in result:
        cv2.drawMarker(im, P(result["midpoint_xy"]), CYAN, cv2.MARKER_CROSS, 40, 3)
    sides = result.get("sides", {})
    for p in result.get("overlay", {}).get("neighbourhood", []):
        c, n = np.array(p["c"]), np.array(p["n"])
        for name, d in p["d"].items():
            sgn = -1 if ((-n)[1] < 0) == (name == "upper_wall") else 1
            sd = sides.get(name, {})
            bad = p.get("burr", {}).get(name) or any(("flash" in f or "burr" in f) for f in sd.get("flags", []))
            if d is None:
                cv2.drawMarker(im, P(c + sgn * 0.45 * 80 * n), RED, cv2.MARKER_TILTED_CROSS, 9, 2)
            else:
                cv2.circle(im, P(c + sgn * d * n), 5 if bad else 3, RED if bad else (GREEN if sd.get("kind") == "A" else LBLUE), -1)
    if "section_xy" in result:
        cv2.drawMarker(im, P(result["section_xy"]), MAG, cv2.MARKER_DIAMOND, 14, 2)
    if result.get("measurement_line_px"):
        a, b = map(np.array, result["measurement_line_px"])
        cv2.line(im, P(a), P(b), MAG, 2)
        tdir = np.array([-(b - a)[1], (b - a)[0]]) / max(np.linalg.norm(b - a), 1e-6)
        for e in (a, b):
            cv2.line(im, P(e - 7 * tdir), P(e + 7 * tdir), MAG, 2)

    h, w = gray.shape[:2]
    pts = np.array(cl) if cl else np.array([[w / 2, h / 2]])
    ends = np.array(result.get("neck_ends_xy", pts[[0, -1]].tolist()))
    x0, y0 = np.maximum(ends.min(0).astype(int) - 140, 0)
    x1, y1 = np.minimum(ends.max(0).astype(int) + 140, [w, h])
    full = im[y0:y1, x0:x1]
    full = cv2.resize(full, None, fx=700 / max(full.shape[0], 1), fy=700 / max(full.shape[0], 1), interpolation=cv2.INTER_AREA)
    c = np.array(result.get("section_xy", pts[len(pts) // 2])).astype(int)
    zx0, zy0 = max(c[0] - 110, 0), max(c[1] - 110, 0)
    zoom = cv2.resize(im[zy0:zy0 + 220, zx0:zx0 + 220], (700, 700), interpolation=cv2.INTER_CUBIC)
    top = np.hstack([full, np.full((700, 8, 3), 255, np.uint8), zoom])

    st = result["status"]
    head = (f"{label}   EXPERIMENTAL CH05 v2 -- NOT PRODUCTION   status: {st}"
            + (f" ({result['cause']})" if result.get("cause") else ""))
    lines = [(head, (0, 0, 0))]
    if result.get("width_px") is not None:
        lines.append((f"width {result['width_px']:.2f} px (median of {len(result['profile_widths_px'])} profiles, spread "
                      f"{result['width_spread_px']:.2f} px) = {result['width_mm_experimental']:.4f} mm at observed "
                      f"{result['observed_um_per_px']:.3f} um/px (experimental)", (0, 0, 0)))
    if "neck_length_px" in result:
        lines.append((f"neck length {result['neck_length_px']:.0f} px, core band gap {result['core_band_gap_px']:.0f} px, "
                      f"section = midpoint + {result['section_offset_px']:.0f} px toward lower-left; appearance "
                      f"{result.get('appearance', '-')}", (60, 60, 60)))
    for name, sd in sides.items():
        lines.append((f"{name}: kind {sd.get('kind')}, boundary {sd.get('d_px', '-')} px, solid band {sd.get('solid_band_px', '-')} px, "
                      f"line on {sd.get('line_fraction', 0):.0%}, strip {sd.get('dark_strip_px', '-')} px, edge MAD "
                      f"{sd.get('edge_mad_px', '-')}, angle {sd.get('wall_angle_deg', '-')}", (60, 60, 60)))
    for r in result.get("reasons", []):
        lines.append(("REJECTED: " + r, RED))
    lines.append(("blue circles: neck ends | cyan cross: midpoint | magenta: CH05 section + measurement line | "
                  "green/light-blue dots: A/B boundaries | red: flash/burr or missing", (90, 90, 90)))
    panel = np.full((26 * len(lines) + 14, top.shape[1], 3), 238, np.uint8)
    for k, (t, col) in enumerate(lines):
        cv2.putText(panel, t[:175], (10, 24 + 26 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)
    return np.vstack([top, panel])
