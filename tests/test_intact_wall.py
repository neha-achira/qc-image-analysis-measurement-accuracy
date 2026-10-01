"""
Tests for the EXPERIMENTAL intact-wall diameter (experimental_intact_wall.py).
Synthetic round bores of known radius with localised intrusions; expected
values are the known geometry, never workbook values. Also checks that the
production measurement is untouched by the experimental module.
"""
import numpy as np
import pytest

import detect_features as df
import experimental_intact_wall as iw
from test_measurement_accuracy import single_hole

MM = 0.002587


def bite(img, cx, cy, R, angle_deg, depth):
    """Fill the part of the aperture beyond a chord: an intrusion of given depth (px)."""
    yy, xx = np.mgrid[:img.shape[0], :img.shape[1]]
    a = np.radians(angle_deg)
    proj = (xx - cx) * np.cos(a) + (yy - cy) * np.sin(a)
    inside = np.hypot(xx - cx, yy - cy) < R + 3
    img[(proj > R - depth) & inside] = 12
    return img


def burr(img, cx, cy, R, angle_deg, width_deg, depth):
    """Ragged sector intrusion: wall pushed inward by `depth` px over a sector."""
    yy, xx = np.mgrid[:img.shape[0], :img.shape[1]]
    th = (np.degrees(np.arctan2(yy - cy, xx - cx)) - angle_deg + 180) % 360 - 180
    d = np.hypot(xx - cx, yy - cy)
    img[(np.abs(th) < width_deg / 2) & (d > R - depth) & (d < R + 3)] = 12
    return img


def run(img, cx, cy, nominal=100, thr=90):
    return iw.intact_wall_diameter(img, (cx, cy), nominal, thr, MM)


def test_clean_hole_matches_true_and_production():
    img, cx, cy = single_hole(104.0, shoulder=0.0, sigma=1.0)
    r = run(img, cx, cy)
    prod = df._subpixel_diameter(img, cx, cy, nominal_r=100)
    assert r["status"] == "OK"
    assert r["intact_diameter_px"] == pytest.approx(208.0, abs=1.0)
    assert r["intact_diameter_px"] == pytest.approx(prod, abs=1.5)
    assert r["intrusion_fraction"] < 0.03


@pytest.mark.parametrize("depth", [15, 30, 45])
def test_chord_bite_recovers_bore_while_production_reads_low(depth):
    img, cx, cy = single_hole(104.0, shoulder=0.0, sigma=1.0)
    bite(img, cx, cy, 104.0, 200, depth)
    r = run(img, cx, cy)
    prod = df._subpixel_diameter(img, cx, cy, nominal_r=100)
    assert r["status"] == "OK"
    assert r["intact_diameter_px"] == pytest.approx(208.0, abs=1.5)
    assert r["intrusion_fraction"] > 0.05 and r["n_intrusion_runs"] >= 1
    # Production's median radius is robust to small intrusions; larger ones pull it in.
    assert prod <= r["intact_diameter_px"] + 0.5
    if depth >= 30:
        assert prod < r["intact_diameter_px"] - 1.0


def test_several_burrs_recovers_bore():
    img, cx, cy = single_hole(100.0, shoulder=0.0, sigma=1.0)
    for a, w, dep in [(30, 25, 12), (150, 40, 20), (260, 30, 8)]:
        burr(img, cx, cy, 100.0, a, w, dep)
    r = run(img, cx, cy)
    assert r["status"] == "OK"
    assert r["intact_diameter_px"] == pytest.approx(200.0, abs=1.5)
    assert r["n_intrusion_runs"] >= 3


def test_off_centre_start_is_tolerated():
    img, cx, cy = single_hole(104.0, shoulder=0.0, sigma=1.0)
    bite(img, cx, cy, 104.0, 90, 25)
    r = run(img, cx + 12, cy - 9)
    assert r["status"] == "OK"
    assert r["intact_diameter_px"] == pytest.approx(208.0, abs=1.5)
    assert np.hypot(r["centre_xy"][0] - cx, r["centre_xy"][1] - cy) <= 1.0


def test_channel_opening_is_escape_not_wall():
    img, cx, cy = single_hole(104.0, shoulder=0.0, sigma=1.0)
    yy, xx = np.mgrid[:img.shape[0], :img.shape[1]]
    chan = (np.abs(yy - cy) < 30) & (xx > cx) & (xx < cx + 135)
    img[chan] = 133                                       # bright channel leaving the hole to the right
    r = run(img, cx, cy)
    assert r["status"] == "OK"
    assert r["intact_diameter_px"] == pytest.approx(208.0, abs=1.5)
    assert r["intrusion_fraction"] < 0.03


def test_mostly_destroyed_wall_is_ambiguous_not_forced():
    img, cx, cy = single_hole(104.0, shoulder=0.0, sigma=1.0)
    for a in range(0, 360, 60):                           # six deep burrs, ~65 % of the circumference
        burr(img, cx, cy, 104.0, a, 40, 18)
    r = run(img, cx, cy)
    assert r["status"] in ("AMBIGUOUS", "FAILED")
    assert r["reasons"]


def test_no_hole_fails_cleanly():
    img = np.full((420, 420), 140, np.uint8)
    r = run(img, 210, 210)
    assert r["status"] == "FAILED" and r["reasons"]


def test_production_measurement_not_affected_by_experimental_module():
    img, cx, cy = single_hole(104.0, shoulder=0.0, sigma=1.0)
    bite(img, cx, cy, 104.0, 200, 30)
    before = df._subpixel_diameter(img, cx, cy, nominal_r=100)
    run(img, cx, cy)
    after = df._subpixel_diameter(img, cx, cy, nominal_r=100)
    assert before == after
