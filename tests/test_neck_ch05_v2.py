"""
Tests for the EXPERIMENTAL CH05 v2 neck detector (experimental_ch05_v2.py).
Synthetic necks of known geometry: a straight channel of known floor width
between two solid wall bands that flare open at both ends. Expected values
are the known geometry, never workbook values. Real-image checks (skipped
without QC_BP_DATA) are structural only.
"""
import os
from pathlib import Path

import cv2
import numpy as np
import pytest
from scipy.ndimage import gaussian_filter

import detect_features as df
import experimental_ch05_v2 as v2

BP_DATA = os.environ.get("QC_BP_DATA")
real_data = pytest.mark.skipif(not BP_DATA, reason="set QC_BP_DATA to the BP image folder")

H, W, Y0, XC = 900, 1400, 450, 700
HALF, WALL, SIGMA = 40.0, 55, 1.5            # floor half-width (px), wall band thickness, edge blur
FLOOR, WALLV, SURF = 110.0, 14.0, 125.0


def half_width(x):
    """Floor half-width along the neck: constant core, flaring beyond +-200 px."""
    return HALF + 0.6 * np.maximum(np.abs(x - XC) - 200, 0)


def synth_neck(kind="A", flash=False, seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:H, :W].astype(float)
    hw = half_width(xx)
    d = np.abs(yy - Y0)
    img = np.full((H, W), SURF) + gaussian_filter(rng.normal(0, 25, (H, W)), 3)
    img[d < hw + WALL] = WALLV
    img[d < hw] = FLOOR
    if kind == "B":                                  # dark strip, then a thin bright line, then the wall
        img[(d >= hw - 15) & (d < hw - 3)] = 22.0
        img[(d >= hw - 3) & (d < hw)] = 125.0
    xs0 = XC - v2.SECTION_OFFSET_PX
    if flash == "ragged":                            # alternating burrs 12 px wide, 2 / 12 px deep, around the section
        for k, x0 in enumerate(range(int(xs0 - 60), int(xs0 + 60), 12)):
            depth = 12 if k % 2 else 2
            img[int(Y0 + HALF - depth):int(Y0 + HALF), x0:x0 + 12] = WALLV
    elif flash == "random":                          # random burrs 10-20 px wide, 2-14 px deep (real-flash scale)
        x0 = int(xs0 - 60)
        while x0 < xs0 + 60:
            bw, depth = int(rng.integers(10, 21)), rng.uniform(2, 14)
            img[int(Y0 + HALF - depth):int(Y0 + HALF), x0:x0 + bw] = WALLV
            x0 += bw
    img = gaussian_filter(img, SIGMA) + rng.normal(0, 1.0, (H, W))
    return np.clip(img, 0, 255).astype(np.uint8)


def a_rule_width(true_width, sigma=SIGMA):
    """Frozen A level (30 % from wall to floor) on a blurred step sits 0.524 sigma outside the edge."""
    return true_width + 2 * 0.5244 * sigma


def test_group_a_measures_known_width_at_the_section():
    r = v2.detect_neck_ch05_v2(synth_neck("A"))
    assert r["status"] == "RELIABLE_A" and not r["not_measured"]
    assert r["width_px"] == pytest.approx(a_rule_width(2 * HALF), abs=1.0)
    assert r["section_xy"][0] == pytest.approx(XC - v2.SECTION_OFFSET_PX, abs=4)   # midpoint + 96 toward the left
    assert r["midpoint_xy"][0] == pytest.approx(XC, abs=4)
    assert r["production"] is False and "NOT production" in r["method"]


def test_experimental_mm_uses_observed_scale():
    r = v2.detect_neck_ch05_v2(synth_neck("A"))
    assert r["width_mm_experimental"] == pytest.approx(r["width_px"] * 2.587 / 1000, abs=1e-5)
    assert "observed image scale" in r["mm_conversion"]


def test_measures_at_the_section_not_the_narrowest_point():
    img = synth_neck("A")
    yy, xx = np.mgrid[:H, :W]
    pinch = (np.abs(xx - (XC + 120)) < 6) & (np.abs(np.abs(yy - Y0) - HALF) < 8)   # narrow spot away from the section
    img[pinch] = int(WALLV)
    r = v2.detect_neck_ch05_v2(img)
    assert r["status"] == "RELIABLE_A"
    assert r["width_px"] == pytest.approx(a_rule_width(2 * HALF), abs=1.0)


def test_group_b_uses_the_bright_line_not_the_floor_edge():
    r = v2.detect_neck_ch05_v2(synth_neck("B"))
    assert r["status"] == "PROVISIONAL_B"
    assert all(sd["kind"] == "B" for sd in r["sides"].values())
    assert r["width_px"] == pytest.approx(2 * HALF, abs=3.0)          # outer edge of the line = wall start
    assert r["width_px"] > 2 * (HALF - 15) + 15                        # not the floor edge inside the dark strip


def test_ragged_flash_is_not_measured():
    r = v2.detect_neck_ch05_v2(synth_neck("A", flash="ragged"))
    assert r["status"] == "NOT_MEASURED" and r["not_measured"]
    assert r["cause"] == "flash" and r["width_px"] is None
    assert any("flash" in x or "burr" in x for x in r["reasons"])


def test_flash_does_not_break_the_neck_location():
    for seed in range(10):
        r = v2.detect_neck_ch05_v2(synth_neck("A", flash="random", seed=seed))
        assert r["cause"] != "geometry", seed
        assert r["midpoint_xy"][0] == pytest.approx(XC, abs=6)


@pytest.mark.parametrize("seed", range(20))
def test_random_burrs_spanning_the_section_are_not_measured(seed):
    # burrs contiguous across the whole +-40 px window look like a displaced wall locally;
    # they are caught against the wall line interpolated from 48-120 px either side
    r = v2.detect_neck_ch05_v2(synth_neck("A", flash="random", seed=seed))
    assert r["status"] == "NOT_MEASURED" and r["cause"] == "flash"


def test_no_neck_is_not_measured_cleanly():
    r = v2.detect_neck_ch05_v2(np.full((600, 800), 120, np.uint8))
    assert r["status"] == "NOT_MEASURED" and r["cause"] == "geometry" and r["reasons"]


def test_overlay_renders():
    img = synth_neck("A")
    out = v2.annotate_ch05_v2(img, v2.detect_neck_ch05_v2(img), "synthetic")
    assert out.ndim == 3 and out.shape[1] > 1000


def test_frozen_detector_and_production_untouched():
    img = synth_neck("A")
    pre = {"bgr": cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), "gray_raw": img}
    before = df.detect_neck_experimental(dict(pre), 0.002587)
    v2.detect_neck_ch05_v2(img)
    after = df.detect_neck_experimental(dict(pre), 0.002587)
    assert before.get("neck_width_px") == after.get("neck_width_px")
    assert not hasattr(df, "detect_neck_ch05_v2")


# ── real images (structure only; no workbook values) ─────────────────────────
def _real(bp):
    g = cv2.imread(str(Path(BP_DATA) / bp / "Neck_ch00.png"), cv2.IMREAD_GRAYSCALE)
    return v2.detect_neck_ch05_v2(g)


@real_data
@pytest.mark.parametrize("bp", ["BP 4", "BP 17", "BP 24"])
def test_real_clean_group_a_is_reliable(bp):
    r = _real(bp)
    assert r["status"] == "RELIABLE_A"
    assert r["width_spread_px"] <= 3.0


@real_data
def test_real_double_edged_bp9_is_provisional_b():
    r = _real("BP 9")
    assert r["status"] == "PROVISIONAL_B"
    assert any(sd["kind"] == "B" for sd in r["sides"].values())


@real_data
@pytest.mark.parametrize("bp", ["BP 8", "BP 22"])
def test_real_flash_is_not_measured(bp):
    r = _real(bp)
    assert r["status"] == "NOT_MEASURED" and r["cause"] == "flash"
