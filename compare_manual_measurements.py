"""
compare_manual_measurements.py
==============================
Re-measure a batch of cartridges with the current detect_features.py and
compare against the manual (physical) measurements and the previously
recorded software measurements in the Jira comparison workbook.

Measures only -- no correction factors. Every "new" value is exactly what
the production detectors return for the given calibration.

Usage
-----
  py compare_manual_measurements.py --batch "E:\\JiraBatch" ^
      --xlsx "JIra batches comparision data.xlsx" --calibration-mode json

  --batch       folder with one sub-folder per cartridge; the cartridge id is
                the number in the folder name ("7", "BP 7", "BP7" -> 7)
  --calibration-mode  json | metadata | auto  (see leica_calibration.py)
  --diagnostics DIR   also save per-feature diagnostic crops
  --csv PATH          per-cartridge/feature results (default comparison_results.csv)
"""
import argparse
import csv
import re
import sys
from pathlib import Path

import cv2
import numpy as np
import openpyxl

sys.path.insert(0, str(Path(__file__).parent))
from preprocess import preprocess, detect_image_type                 # noqa: E402
from calibrate import load_calibration                               # noqa: E402
from leica_calibration import resolve_scale_factor                   # noqa: E402
from detect_features import (detect_holes, detect_neck, detect_dab, detect_mixing,  # noqa: E402
                             observed_image_scale_mm_per_px)

FEATURES = ["Neck", "DAB", "Tag1", "Tag3", "Tag4", "Tag5", "Tag6", "Tag7", "Tag9",
            "MX01", "MX02", "MX03"]
GROUPS = {"Neck": ["Neck"], "DAB": ["DAB"],
          "Tag holes": ["Tag1", "Tag3", "Tag4", "Tag5", "Tag6", "Tag7", "Tag9"],
          "MX01": ["MX01"], "MX02": ["MX02"], "MX03": ["MX03"]}


def _cid(v):
    m = re.search(r"\d+", str(v))
    return int(m.group()) if m else None


def read_workbook(path):
    """Manual and old-software values per feature, keyed by cartridge id."""
    ws = openpyxl.load_workbook(path, data_only=True)["Comparison"]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]

    def block(header_label):
        i = next(k for k, r in enumerate(rows) if r[1] is not None and str(r[1]).strip() == header_label)
        ids = [_cid(v) for v in rows[i][2:]]
        out = {}
        for j, feat in enumerate(FEATURES):
            vals = rows[i + 1 + j][2:]
            out[feat] = {c: float(v) for c, v in zip(ids, vals) if c is not None and v is not None}
        return out

    return block("Cartridge ID"), block("cartridge_id")


def measure_folder(folder, calibration, mode, diag_dir=None):
    out = {}
    for img in sorted(Path(folder).glob("*.png")):
        if img.stem.lower().endswith(("_detected", "_debug", "_annotated")):
            continue
        it = detect_image_type(str(img))
        if it == "unknown":
            continue
        mm_per_px = resolve_scale_factor(str(img), it, calibration, calibration_mode=mode)["mm_per_px"]
        pre = preprocess(str(img), image_type=it)
        pre["observed_image_scale_mm_per_px"] = observed_image_scale_mm_per_px(calibration, it)
        ctx = {}
        if it == "holes":
            res = detect_holes(pre, mm_per_px, debug_context=ctx)
            for c in res["circles"]:
                out[f"Tag{c['dwg_tag']}"] = c["diameter_mm"]
                if diag_dir:
                    dbg = ctx.get("per_hole", {}).get(c["dwg_tag"], {})
                    save_ray_diag(pre, (c["cx_hough"], c["cy_hough"]), dbg, c["diameter_px"],
                                  mm_per_px, Path(diag_dir) / f"{Path(folder).name}_Tag{c['dwg_tag']}.png")
        elif it == "dab":
            res = detect_dab(pre, mm_per_px, debug_context=ctx)
            out["DAB"] = res["diameter_mm"]
            if diag_dir:
                save_ray_diag(pre, (res["cx_px"], res["cy_px"]), ctx, res["diameter_px"],
                              mm_per_px, Path(diag_dir) / f"{Path(folder).name}_DAB.png")
        elif it == "mixing":
            res = detect_mixing(pre, mm_per_px, debug_context=ctx)
            for hole in res["holes"]:
                out[hole["id"]] = hole["diameter_mm"]
                if diag_dir:
                    save_ray_diag(pre, (hole["cx_px"], hole["cy_px"]), ctx.get("per_hole", {}).get(hole["id"], {}),
                                  hole["diameter_px"], mm_per_px,
                                  Path(diag_dir) / f"{Path(folder).name}_{hole['id']}.png")
        elif it == "neck":
            res = detect_neck(pre, mm_per_px)
            if "error" not in res:
                out["Neck"] = res["trimmed_mean_mm"]            # legacy production value
            if diag_dir:
                save_neck_diag(pre, res, Path(diag_dir) / f"{Path(folder).name}_Neck.png", mm_per_px)
    return out


def save_ray_diag(pre, origin, dbg, diameter_px, mm_per_px, path, scale=3):
    """Crop showing ray origin, threshold hits, refined wall edges and the measured circle."""
    bgr = pre["bgr"] if pre["bgr"].ndim == 3 else cv2.cvtColor(pre["bgr"], cv2.COLOR_GRAY2BGR)
    rays = [r for r in dbg.get("rays", []) if r.get("hit")]
    if not rays:
        return
    ox, oy = origin
    edges = np.array([(ox + r["r_edge"] * np.cos(r["angle"]), oy + r["r_edge"] * np.sin(r["angle"]))
                      for r in rays if r.get("r_edge") is not None])
    A = np.column_stack([2 * edges[:, 0], 2 * edges[:, 1], np.ones(len(edges))])
    fcx, fcy = np.linalg.lstsq(A, (edges ** 2).sum(1), rcond=None)[0][:2]
    half = int(diameter_px * 0.8)
    x0, y0 = int(fcx) - half, int(fcy) - half
    crop = bgr[max(0, y0):y0 + 2 * half, max(0, x0):x0 + 2 * half]
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)

    def p(x, y):
        return int(round((x - x0) * scale)), int(round((y - y0) * scale))
    cv2.circle(crop, p(fcx, fcy), int(round(diameter_px / 2 * scale)), (0, 220, 255), 1, cv2.LINE_AA)
    for r in rays:
        cv2.circle(crop, p(*r["point"]), 4, (60, 60, 255), -1)             # threshold hit (red)
    for x, y in edges:
        cv2.circle(crop, p(x, y), 4, (0, 220, 80), -1)                     # wall edge (green)
    cv2.drawMarker(crop, p(ox, oy), (255, 0, 255), cv2.MARKER_TILTED_CROSS, 30, 2)
    cv2.drawMarker(crop, p(fcx, fcy), (0, 220, 80), cv2.MARKER_CROSS, 30, 2)
    thr_d = 2 * float(np.median(dbg.get("near_nominal_radii") or [np.nan]))
    for i, t in enumerate([f"measured d={diameter_px:.1f}px = {diameter_px * mm_per_px:.4f} mm "
                           f"@ {mm_per_px * 1000:.4f} um/px",
                           f"old threshold-hit d={thr_d:.1f}px",
                           "red: threshold hit  green: wall edge  x: ray origin  +: fitted centre"]):
        cv2.putText(crop, t, (10, 28 + 28 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(crop, t, (10, 28 + 28 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(str(path), crop)


def save_neck_diag(pre, res, path, mm_per_px):
    """Neck diagnostics: legacy production overlay, and the frozen experimental CH05 overlay."""
    from detect_features import annotate_neck, annotate_neck_experimental, detect_neck_experimental
    cv2.imwrite(str(path), annotate_neck(pre["bgr"], res))
    # Experimental diagnostic in mm at the observed image scale (not production calibration).
    exp = detect_neck_experimental(pre, pre.get("observed_image_scale_mm_per_px") or mm_per_px)
    cv2.imwrite(str(path).replace(".png", "_experimental.png"), annotate_neck_experimental(pre["bgr"], exp))


def metrics(err):
    err = np.asarray(err)
    return {"MAE": np.abs(err).mean(), "RMSE": np.sqrt((err ** 2).mean()), "mean signed": err.mean(),
            "median AE": np.median(np.abs(err)), "max AE": np.abs(err).max()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--xlsx", default="JIra batches comparision data.xlsx")
    ap.add_argument("--cal", default="calibration.json")
    ap.add_argument("--calibration-mode", default="json", choices=["json", "metadata", "auto"])
    ap.add_argument("--diagnostics", default=None)
    ap.add_argument("--csv", default="comparison_results.csv")
    a = ap.parse_args()

    manual, old = read_workbook(a.xlsx)
    calibration = load_calibration(a.cal)
    if a.diagnostics:
        Path(a.diagnostics).mkdir(parents=True, exist_ok=True)

    new = {f: {} for f in FEATURES}
    folders = sorted([d for d in Path(a.batch).iterdir() if d.is_dir() and _cid(d.name) is not None],
                     key=lambda d: _cid(d.name))
    for d in folders:
        cid = _cid(d.name)
        if not any(cid in manual[f] for f in FEATURES):
            continue
        print(f"\n=== cartridge {cid} ({d.name}) ===")
        for feat, v in measure_folder(d, calibration, a.calibration_mode, a.diagnostics).items():
            if feat in new:
                new[feat][cid] = v

    rows = []
    print("\nFeature | n | Manual mean | Old software mean | New software mean | Old error % | New error %")
    for f in FEATURES:
        ids = sorted(set(manual[f]) & set(old[f]) & set(new[f]))
        for c in ids:
            rows.append({"cartridge": c, "feature": f, "manual_mm": manual[f][c],
                         "old_mm": old[f][c], "new_mm": new[f][c]})
        if not ids:
            print(f"{f} | 0 | - | - | - | - | -")
            continue
        m = np.mean([manual[f][c] for c in ids])
        o = np.mean([old[f][c] for c in ids])
        n = np.mean([new[f][c] for c in ids])
        print(f"{f} | {len(ids)} | {m:.4f} | {o:.4f} | {n:.4f} | {100 * (o - m) / m:+.2f} | {100 * (n - m) / m:+.2f}")

    print("\nGroup | version | n | MAE | RMSE | mean signed | median AE | max AE  (mm)")
    for g, fs in GROUPS.items():
        sel = [r for r in rows if r["feature"] in fs]
        if not sel:
            continue
        for ver in ("old", "new"):
            s = metrics([r[f"{ver}_mm"] - r["manual_mm"] for r in sel])
            print(f"{g} | {ver} | {len(sel)} | " + " | ".join(f"{v:+.4f}" if k == "mean signed" else f"{v:.4f}"
                                                            for k, v in s.items()))

    with open(a.csv, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["cartridge", "feature", "manual_mm", "old_mm", "new_mm"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nPer-feature rows -> {a.csv}")


if __name__ == "__main__":
    main()
