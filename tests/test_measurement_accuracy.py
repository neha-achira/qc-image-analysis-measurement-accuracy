"""
Regression tests for hole-diameter measurement accuracy and calibration.

Synthetic holes reproduce the edge profile measured on real Holes/Mixing
images (see validation_output/*/ overlays): a bright interior, a gradual
shading "shoulder" that starts ~15 % of the radius inside the wall, then a
steep blurred step down to the dark wall at the true radius R. A fixed
intensity threshold crosses the shoulder before the wall, so the old
"first pixel below threshold" radius under-reads R. These tests pin the
measurement to the physical wall (the steepest bright->dark descent) and
check that the result is a pure pixel measurement: no multiplier, no
dependence on interior brightness, and mm = px * mm_per_px exactly.
"""
import numpy as np
import pytest
from scipy.special import erfc

import detect_features as df
from leica_calibration import (
    parse_leica_pixel_scale,
    resolve_scale_factor,
)

SQRT2 = np.sqrt(2.0)


def MM_TOL(mm_per_px):
    """diameter_px is rounded to 0.01 px and diameter_mm to 1e-5 mm."""
    return 0.005 * mm_per_px + 0.5e-5 + 1e-9


def hole_intensity(d, R, I_in=136.0, I_wall=14.0, I_bg=150.0,
                   shoulder=0.55, shoulder_start=0.85, sigma=1.2, ring_out=1.45):
    """Radial intensity of a hole whose physical wall is at radius R."""
    x = np.clip((d - shoulder_start * R) / ((1 - shoulder_start) * R), 0, 1)
    ramp = 1 - shoulder * x ** 1.5
    step = 0.5 * erfc((d - R) / (SQRT2 * sigma))
    rise = 0.5 * erfc(-(d - ring_out * R) / (SQRT2 * 3.0))
    return I_wall + (I_in - I_wall) * ramp * step + (I_bg - I_wall) * rise


def paint_hole(img, cx, cy, R, **kw):
    half = int(R * 1.9)
    y0, y1 = max(0, cy - half), min(img.shape[0], cy + half)
    x0, x1 = max(0, cx - half), min(img.shape[1], cx + half)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d = np.hypot(xx - cx, yy - cy)
    img[y0:y1, x0:x1] = np.clip(np.round(hole_intensity(d, R, **kw)), 0, 255).astype(np.uint8)


def single_hole(R, size=None, cx=None, cy=None, **kw):
    size = size or int(R * 4.2)
    img = np.full((size, size), kw.get("I_bg", 150.0), np.uint8)
    cx = size // 2 if cx is None else cx
    cy = size // 2 if cy is None else cy
    paint_hole(img, cx, cy, R, **kw)
    return img, cx, cy


def threshold_diameter(ctx):
    """Diameter the pre-fix algorithm reported: 2 x median threshold radius."""
    return 2 * float(np.median(ctx["near_nominal_radii"]))


# ── Edge localisation (holes / tags) ─────────────────────────────────────────

def test_shoulder_profile_reproduces_old_under_read():
    """Sanity check of the model: the old threshold radius sits inside the wall."""
    img, cx, cy = single_hole(100.0)
    ctx = {}
    df._subpixel_diameter(img, cx, cy, nominal_r=100, debug_context=ctx)
    assert threshold_diameter(ctx) <= 196.0


def test_hole_diameter_locates_wall_not_shading():
    img, cx, cy = single_hole(100.0)
    d = df._subpixel_diameter(img, cx, cy, nominal_r=100)
    assert d == pytest.approx(200.0, abs=1.5)


@pytest.mark.parametrize("R", [80.0, 92.5, 100.0, 108.0, 120.0])
def test_hole_diameter_has_no_proportional_or_constant_bias(R):
    """Error must be ~0 for every size: no hidden multiplier or offset."""
    img, cx, cy = single_hole(R)
    d = df._subpixel_diameter(img, cx, cy, nominal_r=100)
    assert d - 2 * R == pytest.approx(0.0, abs=1.5)


def test_hole_diameter_slope_vs_truth_is_one():
    truth, meas = [], []
    for R in (82.0, 90.0, 98.0, 106.0, 114.0):
        img, cx, cy = single_hole(R)
        truth.append(2 * R)
        meas.append(df._subpixel_diameter(img, cx, cy, nominal_r=100))
    slope, intercept = np.polyfit(truth, meas, 1)
    assert slope == pytest.approx(1.0, abs=0.02)
    assert intercept == pytest.approx(0.0, abs=4.0)


def test_hole_diameter_independent_of_interior_brightness():
    """A fixed threshold moves with illumination; the wall does not."""
    diam, old = [], []
    for I_in in (110.0, 136.0, 170.0):
        img, cx, cy = single_hole(100.0, I_in=I_in)
        ctx = {}
        diam.append(df._subpixel_diameter(img, cx, cy, nominal_r=100, debug_context=ctx))
        old.append(threshold_diameter(ctx))
    assert max(old) - min(old) >= 3.0          # documents the old sensitivity
    assert max(diam) - min(diam) <= 1.0


def test_sharp_edge_measurement_essentially_unchanged():
    """A crisp wall (no shoulder, e.g. DAB) reads as before, minus the
    +1 px/side the old integer 'first dark pixel' step always added."""
    img, cx, cy = single_hole(100.0, shoulder=0.0, sigma=0.6)
    ctx = {}
    d = df._subpixel_diameter(img, cx, cy, nominal_r=100, debug_context=ctx)
    assert d == pytest.approx(200.0, abs=1.0)
    assert 0.0 <= threshold_diameter(ctx) - d <= 2.5


def test_off_centre_ray_origin_is_tolerated():
    """Hough centres are a few px off; the median must still give ~2R."""
    img, cx, cy = single_hole(100.0)
    d = df._subpixel_diameter(img, cx + 6, cy - 5, nominal_r=100)
    assert d == pytest.approx(200.0, abs=1.5)


def test_large_centre_offset_does_not_shrink_diameter():
    """Real Hough origins were up to ~27 px off; the half-chord would read ~7 px low."""
    img, cx, cy = single_hole(100.0)
    d = df._subpixel_diameter(img, cx + 20, cy + 15, nominal_r=100)
    assert d == pytest.approx(200.0, abs=1.5)


def test_channel_entering_hole_is_rejected_as_outlier():
    """A grey channel crossing the wall over a 40 deg sector must not bias the fit."""
    R = 100.0
    img, cx, cy = single_hole(R)
    yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    ang = np.degrees(np.arctan2(yy - cy, xx - cx))
    d = np.hypot(xx - cx, yy - cy)
    wedge = (np.abs(ang) < 20) & (d > 0.9 * R)
    img[wedge] = 120
    out = df._subpixel_diameter(img, cx + 4, cy - 3, nominal_r=100)
    assert out == pytest.approx(200.0, abs=1.5)


def test_ray_debug_keeps_threshold_hits_and_adds_edge():
    """Candidate ranking/confidence use the threshold hits; they must not change."""
    img, cx, cy = single_hole(100.0)
    ctx = {}
    df._subpixel_diameter(img, cx, cy, nominal_r=100, debug_context=ctx)
    assert ctx["fallback_mode"] == "normal"
    assert ctx["n_hit"] == ctx["n_rays"] == 36
    for ray in ctx["rays"]:
        assert isinstance(ray["r"], int)
        assert ray["r_edge"] >= ray["r"] - 3


# ── Pixel -> mm conversion and calibration ──────────────────────────────────

def _dab_image(R=104.0):
    img, cx, cy = single_hole(R, size=900, shoulder=0.0, sigma=0.8, I_in=133.0, I_wall=9.0)
    return {"bgr": img, "gray_raw": img}, cx, cy


@pytest.mark.parametrize("mm_per_px", [0.0025, 0.002593, 0.00266667])
def test_dab_mm_is_pixels_times_scale(mm_per_px):
    pre, _, _ = _dab_image()
    res = df.detect_dab(pre, mm_per_px)
    assert res["diameter_px"] == pytest.approx(208.0, abs=1.5)
    assert res["diameter_mm"] == pytest.approx(res["diameter_px"] * mm_per_px, abs=MM_TOL(mm_per_px))


def test_pixel_measurement_does_not_depend_on_calibration():
    pre, _, _ = _dab_image()
    a = df.detect_dab(pre, 0.0025)["diameter_px"]
    b = df.detect_dab(pre, 0.002593)["diameter_px"]
    assert a == pytest.approx(b, abs=0.5)


def test_tolerance_check_uses_converted_mm():
    t = df._tol_check(0.52, "hole_diameter")
    assert t["measured_mm"] == 0.52 and t["pass"]
    assert not df._tol_check(0.56, "hole_diameter")["pass"]


def test_calibration_json_mode_uses_per_type_entry():
    cal = {"holes": {"scale_factor_mm_per_px": 0.0025},
           "neck": {"scale_factor_mm_per_px": 0.00266667}}
    assert resolve_scale_factor("x/Holes_ch00.png", "holes", cal)["mm_per_px"] == 0.0025
    assert resolve_scale_factor("x/neck_ch00.png", "neck", cal)["mm_per_px"] == 0.00266667


LEICA_XML = (
    '<Data><Image><ImageDescription><Dimensions>'
    '<DimensionDescription DimID="1" NumberOfElements="7177" Origin="0" '
    'Length="{lx}" Unit="m" />'
    '<DimensionDescription DimID="2" NumberOfElements="6102" Origin="0" '
    'Length="{ly}" Unit="m" />'
    '</Dimensions></ImageDescription></Image></Data>'
)


def _write_leica(tmp_path, um_per_px):
    meta = tmp_path / "MetaData"
    meta.mkdir()
    (meta / "Holes.xml").write_text(LEICA_XML.format(
        lx=7177 * um_per_px * 1e-6, ly=6102 * um_per_px * 1e-6), encoding="utf-8")
    return str(tmp_path / "Holes_ch00.png")


def test_leica_metadata_scale_is_parsed(tmp_path):
    img = _write_leica(tmp_path, 2.593)
    info = parse_leica_pixel_scale(tmp_path / "MetaData" / "Holes.xml")
    assert info["um_per_px"] == pytest.approx(2.593, abs=1e-6)
    res = resolve_scale_factor(img, "holes", {}, calibration_mode="metadata")
    assert res["source"] == "leica_metadata"
    assert res["mm_per_px"] == pytest.approx(0.002593, abs=1e-9)


def test_auto_mode_prefers_metadata_and_cross_checks(tmp_path):
    img = _write_leica(tmp_path, 2.593)
    cal = {"holes": {"scale_factor_mm_per_px": 0.0025}}
    res = resolve_scale_factor(img, "holes", cal, calibration_mode="auto")
    assert res["source"] == "leica_metadata"
    assert res["cross_check_pct_diff"] == pytest.approx(3.72, abs=0.01)
    assert resolve_scale_factor(img, "holes", cal, calibration_mode="json")["mm_per_px"] == 0.0025


# ── End-to-end detectors on synthetic full-size images ───────────────────────

def test_detect_mixing_measures_wall():
    h, w = 2600, 12400
    img = np.full((h, w), 150, np.uint8)
    truth = {"MX01": (420, 1700, 104.0), "MX02": (5690, 2230, 101.0), "MX03": (11960, 2120, 106.0)}
    for cx, cy, R in truth.values():
        paint_hole(img, cx, cy, R)
    res = df.detect_mixing({"bgr": img}, 0.0025)
    got = {hole["id"]: hole for hole in res["holes"]}
    for hid, (_, _, R) in truth.items():
        assert got[hid]["diameter_px"] == pytest.approx(2 * R, abs=2.0), hid
        assert got[hid]["diameter_mm"] == pytest.approx(got[hid]["diameter_px"] * 0.0025, abs=MM_TOL(0.0025))


def test_detect_holes_measures_wall_for_every_tag():
    h, w = 6100, 7200
    rng = np.random.default_rng(0)
    img = np.clip(rng.normal(150, 3, (h, w)), 0, 255).astype(np.uint8)
    anchor = (6698, 1960)
    offsets = {1: (-6091, -1464), 3: (-5674, 1205), 4: (-4267, -1108), 5: (-4392, 3596),
               6: (-3302, -72), 7: (-2971, 1282), 9: (0, 0)}
    radii = {1: 101.0, 3: 104.0, 4: 99.0, 5: 106.0, 6: 102.0, 7: 97.0, 9: 105.0}
    for tag, (dx, dy) in offsets.items():
        paint_hole(img, anchor[0] + dx, anchor[1] + dy, radii[tag])
    res = df.detect_holes({"bgr": img}, 0.0025)
    got = {c["dwg_tag"]: c for c in res["circles"]}
    assert set(got) == set(offsets)
    for tag, R in radii.items():
        assert got[tag]["diameter_px"] == pytest.approx(2 * R, abs=2.0), tag
        assert got[tag]["diameter_mm"] == pytest.approx(got[tag]["diameter_px"] * 0.0025, abs=MM_TOL(0.0025))
