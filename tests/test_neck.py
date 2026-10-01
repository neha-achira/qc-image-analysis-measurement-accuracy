"""
Production neck value = LEGACY dark-band method (provisional); the CH05
detector below is FROZEN EXPERIMENTAL and only attached as a diagnostic.
These tests pin both behaviours.

Regression tests for the experimental CH05 neck measurement: the perpendicular distance
across the grey neck floor between its two opposing wall boundaries, at the
narrowest part of the neck.

Synthetic necks have known geometry, so every expected width below is
analytic (never taken from the manual workbook):
  * group A: floor -> solid wall edges blurred by a Gaussian of known sigma;
    the operator-reference level (NECK_A_BOUNDARY_LEVEL, wall=0, floor=1)
    lies z*sigma beyond the edge centre with z = Phi^-1(1 - level).
  * group B: floor -> dark strip -> thin bright line -> solid wall; the
    boundary is the line centre.
Real-image tests (QC_BP_DATA) check structure only: appearance, filament and
seam handling, plausibility against the code's existing 0.15-0.25 mm limits.
"""
import json
import os
from pathlib import Path

import cv2
import numpy as np
import pytest
from scipy.ndimage import gaussian_filter
from scipy.special import erfc
from scipy.stats import norm

import detect_features as df

REPO = Path(__file__).resolve().parent.parent
BP_DATA = os.environ.get("QC_BP_DATA")
real_data = pytest.mark.skipif(not BP_DATA or not Path(BP_DATA).is_dir(),
                               reason="set QC_BP_DATA to the folder containing 'BP n' sub-folders")
MM = 0.002587
FLOOR, WALL = 120.0, 13.0
Z = norm.ppf(1 - df.NECK_A_BOUNDARY_LEVEL)


def _frame(size=900, angle_deg=30.0):
    yy, xx = np.mgrid[:size, :size].astype(float)
    c = size / 2
    a = np.radians(angle_deg)
    s = (xx - c) * np.cos(a) + (yy - c) * np.sin(a)        # along the channel
    d = -(xx - c) * np.sin(a) + (yy - c) * np.cos(a)       # across the channel
    return s, d, xx, yy


def synth_neck(kind="A", half_gap=38.0, curvature=2e-4, sigma=2.0, wall_px=60.0,
               floor=FLOOR, strip_px=15.0, line_amp=90.0, broad_band=False, seed=0):
    """Returns (image, expected_width_px). Narrowest point at the image centre."""
    rng = np.random.default_rng(seed)
    s, d, _, _ = _frame()
    h = half_gap + curvature * s ** 2                      # half-gap grows away from the neck
    ad = np.abs(d)
    tex = gaussian_filter(rng.normal(0, 1, s.shape), 4)
    outside = 110 + 30 * tex / tex.std()
    if kind == "A":
        wall_in = h
        img = WALL + (floor - WALL) * 0.5 * erfc((ad - h) / (np.sqrt(2) * sigma))
        expected = 2 * (half_gap + Z * sigma)
    else:
        core = WALL + (floor - WALL) * 0.5 * erfc((ad - h) / (np.sqrt(2) * 1.5))
        line_c = h + strip_px
        if broad_band:
            band = 0.5 * (erfc((ad - line_c - 20) / 2.0) - erfc((ad - line_c + 2) / 2.0)) * 45
            img = core + band
        else:
            img = core + line_amp * np.exp(-0.5 * ((ad - line_c) / 1.0) ** 2)
        wall_in = line_c + 3
        expected = 2 * (half_gap + strip_px)
    solid_out = wall_in + wall_px
    img = np.where(ad > solid_out, outside, img)
    img = np.clip(img + rng.normal(0, 1.5, img.shape), 5, 255).astype(np.uint8)
    return img, expected


def run(img):
    return df.detect_neck_experimental({"bgr": img, "gray_raw": img}, MM)


# ── Group A / B boundary logic ───────────────────────────────────────────────

@pytest.mark.parametrize("sigma", [1.5, 2.5, 4.0])
def test_group_a_boundary_is_reference_level_of_floor_wall_transition(sigma):
    img, expected = synth_neck("A", sigma=sigma)
    r = run(img)
    assert r["appearance"] == "A"
    assert r["neck_width_px"] == pytest.approx(expected, abs=1.5)
    assert r["neck_width_mm"] == pytest.approx(r["neck_width_px"] * MM, abs=1e-5)


def test_group_a_is_not_the_50_percent_edge():
    img, expected = synth_neck("A", sigma=4.0)
    r = run(img)
    fifty = 2 * 38.0
    assert r["neck_width_px"] > fifty + 2.5          # the boundary lies beyond the mid-level


@pytest.mark.parametrize("half_gap", [30.0, 38.0, 46.0])
def test_group_b_boundary_is_thin_bright_edge_not_inner_core(half_gap):
    img, expected = synth_neck("B", half_gap=half_gap)
    r = run(img)
    assert r["appearance"] == "B"
    assert r["neck_width_px"] == pytest.approx(expected, abs=1.5)
    assert r["neck_width_px"] > 2 * half_gap + 20     # not the inner grey core
    assert r["confidence"] != "high"                  # group B is provisional


def test_measurement_is_taken_at_the_narrowest_point():
    img, expected = synth_neck("A", curvature=5e-4)
    r = run(img)
    (x1, y1), (x2, y2) = r["measurement_line_px"]
    mid = np.array([(x1 + x2) / 2, (y1 + y2) / 2])
    assert np.hypot(*(mid - 450)) <= 12
    assert r["neck_width_px"] == pytest.approx(expected, abs=1.5)


def test_measurement_line_is_perpendicular_to_the_walls():
    img, _ = synth_neck("A", curvature=0.0)
    r = run(img)
    (x1, y1), (x2, y2) = r["measurement_line_px"]
    v = np.array([x2 - x1, y2 - y1]); v /= np.linalg.norm(v)
    along = np.array([np.cos(np.radians(30)), np.sin(np.radians(30))])
    assert abs(v @ along) < 0.05


# ── Artefacts and NOT_MEASURED ───────────────────────────────────────────────

def test_thin_filament_across_the_neck_is_not_a_wall():
    img, expected = synth_neck("A", curvature=3e-4)
    s, d, xx, yy = _frame()
    filament = np.abs(s - 40) < 4                     # 8 px dark filament across the channel
    img[filament & (np.abs(d) < 80)] = 25
    r = run(img)
    assert "error" not in r
    assert r["neck_width_px"] == pytest.approx(expected, abs=1.5)
    (x1, y1), (x2, y2) = r["measurement_line_px"]
    for t in np.linspace(0.2, 0.8, 13):               # the line never crosses the filament
        x, y = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
        assert img[int(round(y)), int(round(x))] > 60


def test_broad_band_without_thin_edge_is_not_measured():
    img, _ = synth_neck("B", broad_band=True)
    r = run(img)
    assert r.get("not_measured") is True
    assert r["overall_pass"] is False


def test_low_contrast_is_not_measured():
    img, _ = synth_neck("A", floor=40.0)
    r = run(img)
    assert r.get("not_measured") is True


def test_tile_seam_rows_are_not_used_as_boundaries():
    img, _ = synth_neck("A", curvature=5e-4)
    # Seam placed where the narrowest profile's lower boundary lies
    # (y = 450 + (38 + z*sigma) * cos 30deg ~ 484) with a tile brightness step.
    seam = 484
    img[seam:, :] = np.clip(img[seam:, :].astype(int) + 12, 0, 255).astype(np.uint8)
    img[:470, :15] = 0                                 # upper tile's left padding
    img[500:, -15:] = 0                                # lower tile's right padding
    r = run(img)
    assert r["seam_row"] in (seam - 1, seam)
    (x1, y1), (x2, y2) = r["measurement_line_px"]
    assert min(abs(y1 - r["seam_row"]), abs(y2 - r["seam_row"])) > df.NECK_SEAM_EXCLUDE_PX


def test_not_measured_neck_gives_explicit_csv_row():
    img, _ = synth_neck("A", floor=40.0)
    res = {"image_path": "x/Neck_ch00.png", "mm_per_px": MM, "calibration_source": "calibration_json",
           "features": run(img), "overall_pass": False}
    rows = df.results_to_rows("BPx", {"neck": res})
    assert len(rows) == 1 and rows[0]["pass_fail"] == "NOT_MEASURED"


def test_neck_production_scale_is_legacy_and_observed_scale_is_documented():
    """Production (legacy, provisional) neck keeps 2.66667 um/px for comparability;
    the Leica scale-bar scale is recorded but not used for it."""
    cal = json.load(open(REPO / "calibration.json"))
    neck = cal["neck"]
    assert neck["scale_factor_um_per_px"] == pytest.approx(2.66667, abs=1e-6)
    assert neck["scale_factor_mm_per_px"] == pytest.approx(0.00266667, abs=1e-9)
    obs = neck["observed_image_scale"]
    assert obs["um_per_px"] == pytest.approx(2.587, abs=1e-6) and obs["used_for_production"] is False
    assert 954.5 / 369 == pytest.approx(obs["um_per_px"], abs=0.001)


# ── Real images (structure only; no workbook values) ─────────────────────────

def _real(bp):
    from preprocess import preprocess
    pre = preprocess(str(Path(BP_DATA) / bp / "Neck_ch00.png"), image_type="neck")
    return pre, df.detect_neck_experimental(pre, MM)


def _line_is_on_floor(gray, r):
    (x1, y1), (x2, y2) = r["measurement_line_px"]
    vals = [gray[int(round(y1 + t * (y2 - y1))), int(round(x1 + t * (x2 - x1)))]
            for t in np.linspace(0.25, 0.75, 11)]
    return min(vals) > 60


@real_data
@pytest.mark.parametrize("bp", ["BP 17", "BP 24"])
def test_real_group_a(bp):
    pre, r = _real(bp)
    assert r["appearance"] == "A" and r["confidence"] == "high"
    assert _line_is_on_floor(pre["gray_raw"], r)
    assert 0.15 <= r["neck_width_mm"] <= 0.25        # existing code tolerance limits (plausibility)


@real_data
def test_real_group_b_bp21():
    pre, r = _real("BP 21")
    assert r["appearance"] == "B"
    assert r["confidence"] != "high"
    assert 0.15 <= r["neck_width_mm"] <= 0.25


@real_data
def test_real_bp1_filament_is_not_measured_across():
    pre, r = _real("BP 1")
    assert "error" not in r
    assert _line_is_on_floor(pre["gray_raw"], r)       # measurement avoids the dark filament


@real_data
def test_real_bp2_tile_seam_excluded():
    pre, r = _real("BP 2")
    assert r["seam_row"] is not None and abs(r["seam_row"] - 764) <= 5
    assert r["excluded"].get("boundary on tile seam", 0) > 0
    (x1, y1), (x2, y2) = r["measurement_line_px"]
    assert min(abs(y1 - r["seam_row"]), abs(y2 - r["seam_row"])) > df.NECK_SEAM_EXCLUDE_PX


# ── Production = legacy (provisional); experimental attached as diagnostic ──

def _pre(img):
    blurred = cv2.GaussianBlur(img, (3, 3), 0.8)
    return {"bgr": img, "gray_raw": img, "blurred": blurred}


def test_production_neck_is_the_legacy_method_with_experimental_diagnostic():
    img, _ = synth_neck("A")
    pre = _pre(img)
    prod = df.detect_neck(pre, MM)
    exp = df.detect_neck_experimental(pre, MM)
    assert prod["method"].startswith("legacy")
    assert "trimmed_mean_mm" in prod and "neck_width_mm" not in prod
    assert prod["experimental_ch05"]["neck_width_px"] == exp["neck_width_px"]
    assert prod["tolerance"]["measured_mm"] == pytest.approx(prod["trimmed_mean_mm"], abs=1e-5)


def test_production_csv_row_reports_legacy_value_and_labels_it():
    img, _ = synth_neck("A")
    feats = df.detect_neck(_pre(img), MM)
    res = {"image_path": "x/Neck_ch00.png", "mm_per_px": MM, "calibration_source": "calibration_json",
           "features": feats, "overall_pass": feats["overall_pass"]}
    row = df.results_to_rows("BPx", {"neck": res})[0]
    assert row["measured_mm"] == feats["trimmed_mean_mm"]
    assert "LEGACY" in row["notes"] and "experimental CH05" in row["notes"]


def test_legacy_failure_is_not_measured_not_silent():
    img = np.full((600, 800), 150, np.uint8)            # no channel at all
    feats = df.detect_neck(_pre(img), MM)
    assert feats.get("not_measured") is True and feats["overall_pass"] is False
    res = {"image_path": "x/Neck_ch00.png", "mm_per_px": MM, "calibration_source": "calibration_json",
           "features": feats, "overall_pass": False}
    rows = df.results_to_rows("BPx", {"neck": res})
    assert len(rows) == 1 and rows[0]["pass_fail"] == "NOT_MEASURED"


# ── Experimental diagnostic: mm at the OBSERVED image scale, not production ──

OBS = 0.002587          # Leica scale-bar image scale (observed_image_scale)
PROD = 0.00266667       # production (legacy) neck calibration


def test_experimental_summary_uses_observed_scale_and_keeps_pixels():
    img, _ = synth_neck("A")
    pre = _pre(img)
    pre["observed_image_scale_mm_per_px"] = OBS
    prod = df.detect_neck(pre, PROD)
    e = prod["experimental_ch05"]
    direct = df.detect_neck_experimental(_pre(img), PROD)
    assert e["neck_width_px"] == direct["neck_width_px"]            # pixels unchanged
    assert e["neck_width_mm"] == pytest.approx(e["neck_width_px"] * OBS, abs=1e-5)
    assert e["observed_um_per_px"] == pytest.approx(2.587, abs=1e-4)
    assert "observed image scale" in e["mm_conversion"]
    legacy = df.detect_neck(_pre(img), PROD)                          # production value unaffected
    assert prod["trimmed_mean_mm"] == legacy["trimmed_mean_mm"]


def test_experimental_summary_without_observed_scale_reports_pixels_only():
    img, _ = synth_neck("A")
    e = df.detect_neck(_pre(img), PROD)["experimental_ch05"]
    assert "neck_width_mm" not in e and e["neck_width_px"] > 0


def test_detect_passes_observed_scale_but_production_uses_calibration(tmp_path):
    img, _ = synth_neck("A")
    path = tmp_path / "Neck_ch00.png"
    cv2.imwrite(str(path), img)
    cal = {"neck": {"scale_factor_mm_per_px": PROD,
                    "observed_image_scale": {"um_per_px": 2.587, "used_for_production": False}}}
    res = df.detect(str(path), cal)
    f = res["features"]
    assert res["mm_per_px"] == PROD
    assert f["tolerance"]["measured_mm"] == pytest.approx(f["trimmed_mean_mm"], abs=1e-5)
    e = f["experimental_ch05"]
    assert e["neck_width_mm"] == pytest.approx(e["neck_width_px"] * OBS, abs=1e-5)
