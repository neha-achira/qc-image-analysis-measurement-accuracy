"""
Regression tests for the fixes confirmed on the real BP 1-30 images:

  * calibration: one physical scale from the Leica scale bars
  * MX: soft, dim edges (MX03-like) must not be measured inside the wall
  * DAB localisation: a lone bright speck (BP24/BP27) or a partial disc at a
    high threshold (BP6) must not be taken as the hole
  * fitted-centre re-measurement: no size or position bias, even for large
    ray-origin offsets; circle-equivalent diameter remains the reported value
  * missing / misspelled required images are reported, never silently skipped

Synthetic images reproduce each failure mode. Tests marked `real_data` run on
the actual BP images when QC_BP_DATA points at a folder of "BP n" sub-folders
and are skipped otherwise. No manual (spreadsheet) values are encoded here.
"""
import json
import os
import re
from pathlib import Path

import cv2
import numpy as np
import pytest
from scipy.ndimage import gaussian_filter

import detect_features as df
from preprocess import validate_cartridge_images
from test_measurement_accuracy import hole_intensity, paint_hole, single_hole

REPO = Path(__file__).resolve().parent.parent
BP_DATA = os.environ.get("QC_BP_DATA")
real_data = pytest.mark.skipif(not BP_DATA or not Path(BP_DATA).is_dir(),
                               reason="set QC_BP_DATA to the folder containing 'BP n' sub-folders")

LEICA_UM_PER_PX = 2.587


# ── Calibration ──────────────────────────────────────────────────────────────

def test_scale_bar_arithmetic():
    """Exact Leica labels (4 significant figures) give 2.587 um/px."""
    assert 957.1 / 370 == pytest.approx(LEICA_UM_PER_PX, abs=0.001)   # DAB
    assert 954.5 / 369 == pytest.approx(LEICA_UM_PER_PX, abs=0.001)   # Neck
    # Rounded labels (0.1 mm) must contain the same scale.
    for label_mm, lo_px, hi_px in [(3.7, 1435, 1440), (6.4, 2473, 2481)]:
        for px in (lo_px, hi_px):
            assert (label_mm - 0.05) * 1000 / px <= LEICA_UM_PER_PX <= (label_mm + 0.05) * 1000 / px


def test_calibration_json_uses_one_leica_scale_for_hole_images():
    cal = json.load(open(REPO / "calibration.json"))
    for key in ("holes", "DAB", "mixing"):
        entry = cal[key]
        assert entry["scale_factor_um_per_px"] == pytest.approx(LEICA_UM_PER_PX, abs=1e-6)
        assert entry["scale_factor_mm_per_px"] == pytest.approx(LEICA_UM_PER_PX / 1000, rel=1e-9)
        assert entry["calibration_source"] == "leica_scale_bar"


def test_one_physical_image_scale_documented_for_every_type():
    """Every image type shows the same Leica scale-bar scale. Holes/DAB/mixing use it;
    the neck records it but keeps the legacy value for the provisional legacy method."""
    cal = json.load(open(REPO / "calibration.json"))
    for k in ("holes", "DAB", "mixing"):
        assert cal[k]["scale_factor_um_per_px"] == pytest.approx(LEICA_UM_PER_PX, abs=1e-6), k
    assert cal["neck"]["observed_image_scale"]["um_per_px"] == pytest.approx(LEICA_UM_PER_PX, abs=1e-6)
    assert cal["neck"]["scale_factor_um_per_px"] == pytest.approx(2.66667, abs=1e-6)


def _scale_bar_px(gray):
    h = gray.shape[0]
    best = 0
    for y in range(h - 60, h):
        row = np.r_[0, (gray[y] > 200).astype(int), 0]
        d = np.diff(row)
        s, e = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        if len(s):
            best = max(best, int((e - s).max()))
    return best


@real_data
def test_real_dab_scale_bars_match_calibration():
    for bp in sorted(Path(BP_DATA).iterdir()):
        for name, label_um in (("DAB_ch00.png", 957.1),):
            g = cv2.imread(str(bp / name), cv2.IMREAD_GRAYSCALE)
            if g is None:
                continue
            assert label_um / _scale_bar_px(g) == pytest.approx(LEICA_UM_PER_PX, abs=0.005), bp.name


# ── MX: soft, dim edges ──────────────────────────────────────────────────────

@pytest.mark.parametrize("sigma,I_in", [(1.0, 150.0), (4.0, 138.0), (6.0, 130.0)])
def test_soft_dim_edge_measured_at_wall(sigma, I_in):
    """10-90 % transitions of ~3-15 px (MX01..MX03) with dimmer interiors."""
    R = 104.0
    img, cx, cy = single_hole(R, shoulder=0.0, sigma=sigma, I_in=I_in, I_wall=12.0)
    d = df._subpixel_diameter(img, cx + 5, cy - 4, nominal_r=95)
    assert d == pytest.approx(2 * R, abs=1.5)


def test_detect_mixing_soft_edges_have_no_position_dependent_bias():
    h, w = 2600, 12400
    img = np.full((h, w), 150, np.uint8)
    holes = {"MX01": (420, 1700, 1.0, 140.0), "MX02": (5690, 2230, 4.0, 138.0),
             "MX03": (11960, 2120, 6.0, 130.0)}
    for cx, cy, sigma, I_in in holes.values():
        paint_hole(img, cx, cy, 104.0, shoulder=0.0, sigma=sigma, I_in=I_in, I_wall=12.0)
    res = {x["id"]: x for x in df.detect_mixing({"bgr": img}, LEICA_UM_PER_PX / 1000)["holes"]}
    errs = [res[k]["diameter_px"] - 208.0 for k in holes]
    assert max(abs(e) for e in errs) <= 2.0
    assert max(errs) - min(errs) <= 2.0


# ── DAB localisation ─────────────────────────────────────────────────────────

def _dab_scene(hole_xy, hole_Iin=125.0, speck=True, bright_core=False, seed=0):
    """
    Dark field, a bright textured chamber (below 130 grey, as on the real
    images), optional ~570 px bright speck in it, and the hole.
    bright_core: a dim aperture (116) with a brighter round core (r=62 px,
    offset (-28,-12) px) -- at threshold 120 only the core survives (BP6).
    Both scenes were checked to make the ORIGINAL detect_dab fail
    (speck: 886 px off; bright core: 30 px off, diameter 193 vs 208 px).
    """
    h, w = 1398, 1847
    rng = np.random.default_rng(seed)
    img = np.full((h, w), 30.0)
    yy, xx = np.mgrid[:h, :w]
    chamber = ((xx - 1150) / 650.0) ** 2 + ((yy - 700) / 560.0) ** 2 < 1
    tex = gaussian_filter(rng.normal(0, 1, (h, w)), 6)
    tex = 100 + 8 * tex / tex.std()
    img[chamber] = tex[chamber]
    if speck:
        img[(xx - 1300) ** 2 + (yy - 900) ** 2 < 13.5 ** 2] = 140
    hx, hy = hole_xy
    d = np.hypot(xx - hx, yy - hy)
    R = 104.0
    region = d < 1.9 * R
    prof = hole_intensity(d, R, I_in=hole_Iin, I_wall=10.0, I_bg=30.0, shoulder=0.0, sigma=1.0)
    if bright_core:
        core = np.hypot(xx - hx + 28, yy - hy + 12) < 62
        prof = prof + 9.0 * gaussian_filter(core.astype(float), 4) * (d < R)
    img[region] = prof[region]
    img = np.clip(img + rng.normal(0, 2, (h, w)), 0, 255).astype(np.uint8)
    return {"bgr": img, "gray_raw": img}, R


def test_dab_lone_bright_speck_is_not_the_hole():
    """BP24/BP27: at threshold 130 the only blob was a speck; it was accepted."""
    pre, R = _dab_scene((520, 480))
    res = df.detect_dab(pre, LEICA_UM_PER_PX / 1000)
    assert np.hypot(res["cx_px"] - 520, res["cy_px"] - 480) <= 5
    assert res["localization_method"] == "blob"
    assert res["diameter_px"] == pytest.approx(2 * R, abs=2.0)


def test_dab_partial_disc_at_high_threshold_is_not_accepted():
    """BP6: only a bright core of the aperture passed threshold 120; its centroid was ~31 px off."""
    pre, R = _dab_scene((600, 560), hole_Iin=116.0, speck=False, bright_core=True)
    res = df.detect_dab(pre, LEICA_UM_PER_PX / 1000)
    assert np.hypot(res["cx_px"] - 600, res["cy_px"] - 560) <= 5
    assert res["diameter_px"] == pytest.approx(2 * R, abs=2.0)


@real_data
@pytest.mark.parametrize("bp", ["BP 6", "BP 24", "BP 27", "BP 5", "BP 12"])
def test_real_dab_localises_on_the_hole(bp):
    img = cv2.imread(str(Path(BP_DATA) / bp / "DAB_ch00.png"), cv2.IMREAD_GRAYSCALE)
    res = df.detect_dab({"bgr": img, "gray_raw": img}, LEICA_UM_PER_PX / 1000)
    assert res["localization_method"] == "blob"
    g = res["geometry"]
    # The centre sits inside a bright aperture and the fit is a coherent circle.
    assert img[int(g["fitted_cy_px"]), int(g["fitted_cx_px"])] > 100
    assert g["fit_rms_px"] < 5.0
    assert 0.40 < res["diameter_mm"] < 0.65


# ── Fitted-centre re-measurement ─────────────────────────────────────────────

@pytest.mark.parametrize("dx,dy", [(0, 0), (8, -6), (20, 15), (-30, 22), (40, 0)])
def test_fitted_centre_remeasurement_has_no_size_or_position_bias(dx, dy):
    R = 100.0
    img, cx, cy = single_hole(R, shoulder=0.0, sigma=1.0)
    ctx = {}
    d = df._subpixel_diameter(img, cx + dx, cy + dy, nominal_r=100, debug_context=ctx)
    g = ctx["geometry"]
    assert d == pytest.approx(2 * R, abs=1.0)
    assert g["fit_diameter_px"] == pytest.approx(2 * R, abs=1.0)
    assert np.hypot(g["fitted_cx_px"] - cx, g["fitted_cy_px"] - cy) <= 0.75
    if abs(dx) + abs(dy) > 0:
        assert g["measurement_pass"] == "fitted_centre_recast"


def _ellipse_hole(a, b, size=520):
    img = np.full((size, size), 150, np.uint8)
    yy, xx = np.mgrid[:size, :size]
    c = size // 2
    # radial coordinate normalised so the wall is at 'rho = 100'
    rho = 100.0 * np.hypot((xx - c) / a, (yy - c) / b)
    img[:] = np.clip(np.round(hole_intensity(rho, 100.0, shoulder=0.0, sigma=1.0)), 0, 255).astype(np.uint8)
    return img, c


def test_oval_hole_reports_circle_equivalent_and_axis_diagnostics():
    """Reported diameter stays circle-equivalent; axes are diagnostics only."""
    img, c = _ellipse_hole(110.0, 100.0)
    ctx = {}
    d = df._subpixel_diameter(img, c, c, nominal_r=100, debug_context=ctx)
    g = ctx["geometry"]
    assert g["ellipse_fit_ok"] is True
    assert g["major_axis_px"] == pytest.approx(220.0, abs=2.0)
    assert g["minor_axis_px"] == pytest.approx(200.0, abs=2.0)
    assert 200.0 < d < 220.0
    assert d == pytest.approx(210.0, abs=3.0)


def test_geometry_diagnostics_exposed_in_results():
    pre, _ = _dab_scene((520, 480))
    res = df.detect_dab(pre, LEICA_UM_PER_PX / 1000)
    g = res["geometry"]
    for k in ("fit_diameter_mm", "major_axis_mm", "minor_axis_mm", "edge_spread_px", "fit_rms_px"):
        assert k in g
    assert g["major_axis_mm"] == pytest.approx(g["major_axis_px"] * LEICA_UM_PER_PX / 1000, abs=1e-5)


# ── Missing / misspelled required images ─────────────────────────────────────

def _touch_png(path):
    cv2.imwrite(str(path), np.zeros((4, 4), np.uint8))


def test_misspelled_mixing_image_is_reported_not_skipped(tmp_path):
    for n in ("Holes_ch00.png", "Neck_ch00.png", "DAB_ch00.png", "Miximg_ch00.png"):
        _touch_png(tmp_path / n)
    chk = validate_cartridge_images(str(tmp_path))
    assert chk["missing"] == ["mixing"]
    assert ("Miximg_ch00.png", "mixing") in chk["unrecognized"]
    assert any("Miximg_ch00.png" in m and "mixing" in m for m in chk["messages"])
    assert (tmp_path / "Miximg_ch00.png").exists()          # never renamed
    assert not (tmp_path / "Mixing_ch00.png").exists()


def test_other_misspelling_and_generated_files(tmp_path):
    for n in ("Holes_ch00.png", "Holes_ch00_detected.png", "Neck_ch00.png", "DAB_ch00.png",
              "Miixng_ch00.png", "notes.png"):
        _touch_png(tmp_path / n)
    chk = validate_cartridge_images(str(tmp_path))
    assert set(chk["found"]) == {"holes", "neck", "dab"}
    assert ("Miixng_ch00.png", "mixing") in chk["unrecognized"]
    assert ("notes.png", None) in chk["unrecognized"]
    assert "holes" not in chk["duplicates"]                  # _detected output ignored


def test_complete_folder_has_no_messages(tmp_path):
    for n in ("Holes_ch00.png", "Neck_ch00.png", "DAB_ch00.png", "Mixing_ch00.png"):
        _touch_png(tmp_path / n)
    chk = validate_cartridge_images(str(tmp_path))
    assert chk["missing"] == [] and chk["messages"] == []


def test_missing_image_produces_not_measured_row():
    res = df.missing_image_result("mixing", "MISSING required mixing image (Mixing_ch00.png)")
    rows = df.results_to_rows("BP 6", {"mixing": res})
    assert len(rows) == 1
    assert rows[0]["pass_fail"] == "NOT_MEASURED"
    assert "Mixing_ch00.png" in rows[0]["notes"]
    assert res["overall_pass"] is False


def _res(passed, **features):
    return {"overall_pass": passed, "features": features}


def test_folder_verdict_matches_gui_rule():
    ok = {t: _res(True) for t in ("holes", "neck", "dab")}
    assert df.folder_verdict(ok | {"mixing": _res(True)}) == "PASS"
    missing = df.missing_image_result("mixing", "MISSING required mixing image")
    assert df.folder_verdict(ok | {"mixing": missing}) == "INCOMPLETE"
    nm_neck = _res(False, error="x", not_measured=True)
    assert df.folder_verdict(ok | {"neck": nm_neck}) == "INCOMPLETE"
    assert df.folder_verdict(ok | {"holes": _res(False), "mixing": missing}) == "FAIL"
