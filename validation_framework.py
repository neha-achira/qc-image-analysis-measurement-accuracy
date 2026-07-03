"""
validation_framework.py
========================
Thin orchestration layer for measurement validation / QA investigation.

This module performs NO measurement of its own. Every number it writes
to a CSV, a summary, or an overlay image comes directly from:
  - the existing, unmodified preprocess() output,
  - the existing, unmodified calibration subsystem
    (leica_calibration.resolve_scale_factor),
  - the existing, unmodified detection functions' return values
    (detect_holes / detect_neck / detect_dab / detect_mixing), and
  - the debug_context dict those functions now optionally populate
    (ray hit points, near-nominal radii, expected/predicted positions,
    ray-cast timing, fallback mode) -- itself built entirely from values
    the production algorithm already computed internally.

The only computed values in this file are simple, transparent arithmetic
on already-known numbers -- never a re-derivation of anything the
production algorithm decides:
  - "center error (px)"     = euclidean distance between the production
                              detected center and the production/expected
                              center already exposed via debug_context.
  - per-ray "used" coloring = membership check of a ray's own hit radius
                              against debug_context's already-exposed
                              near_nominal_radii list (NOT a re-derivation
                              of the 0.65x/1.30x window itself).
  - summary aggregates       = plain counts/means over already-known
                              per-feature values (e.g. mean deviation_mm).

No ray-casting, pattern-matching, expected-position prediction,
calibration resolution, or PASS/FAIL logic is reimplemented anywhere in
this file. TOLERANCES is imported (read-only) from detect_features.py
purely to report each feature's nominal_mm value -- not copied.
"""

import sys
import csv
import json
import time
import math
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np

REPO = Path(__file__).parent
sys.path.insert(0, str(REPO))

from preprocess import preprocess, detect_image_type
from detect_features import (
    detect_holes, detect_neck, detect_dab, detect_mixing,
    annotate_holes, annotate_neck, annotate_dab, annotate_mixing,
    TOLERANCES,
)
from leica_calibration import resolve_scale_factor


FILES = {
    "holes": "Holes_ch00.png",
    "neck": "Neck_ch00.png",
    "dab": "DAB_ch00.png",
    "mixing": "Mixing_ch00.png",
}

NOMINAL_MM = {
    "holes": TOLERANCES["hole_diameter"]["nominal"],
    "dab": TOLERANCES["hole_diameter"]["nominal"],
    "mixing": TOLERANCES["hole_diameter"]["nominal"],
    "neck": TOLERANCES["neck_width"]["nominal"],
}

COL_EXPECTED = (255, 0, 255)
COL_RAY_HIT = (0, 255, 255)
COL_RAY_REJECT = (140, 140, 140)
COL_DIAG_TEXT = (255, 255, 255)
COL_DIAG_BG = (20, 20, 20)


def _dist(p1, p2):
    if p1 is None or p2 is None:
        return None
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def _draw_ray_points(img, rays, near_nominal_radii=None, draw_numbers=True):
    if not rays:
        return
    near_set = set(near_nominal_radii or [])
    for i, ray in enumerate(rays):
        if not ray["hit"]:
            continue
        pt = (int(ray["point"][0]), int(ray["point"][1]))
        col = COL_RAY_HIT if ray["r"] in near_set else COL_RAY_REJECT
        cv2.circle(img, pt, 4, col, -1)
        if draw_numbers:
            cv2.putText(img, str(i), (pt[0] + 5, pt[1] - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, col, 1, cv2.LINE_AA)


def _draw_expected_line(img, detected_px, expected_px):
    if detected_px is None or expected_px is None:
        return
    d = (int(detected_px[0]), int(detected_px[1]))
    e = (int(expected_px[0]), int(expected_px[1]))
    cv2.drawMarker(img, e, COL_EXPECTED, cv2.MARKER_TILTED_CROSS, 26, 3)
    cv2.line(img, e, d, COL_EXPECTED, 2)


def _draw_diagnostic_text(img, anchor_px, lines):
    if anchor_px is None:
        return
    x = int(anchor_px[0]) + 26
    y = int(anchor_px[1]) + 40
    for i, line in enumerate(lines):
        yy = y + i * 22
        cv2.putText(img, line, (x + 1, yy + 1), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, COL_DIAG_BG, 3, cv2.LINE_AA)
        cv2.putText(img, line, (x, yy), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, COL_DIAG_TEXT, 1, cv2.LINE_AA)


def draw_validation_overlay(annotated_bgr, feature_rows):
    out = annotated_bgr.copy()
    for row in feature_rows:
        if row["status"] != "detected":
            continue

        detected_px = None
        if row.get("detected_cx_px") not in (None, ""):
            detected_px = (row["detected_cx_px"], row["detected_cy_px"])

        expected_px = None
        if row.get("expected_cx_px") not in (None, ""):
            expected_px = (row["expected_cx_px"], row["expected_cy_px"])

        _draw_ray_points(out, row.get("_rays") or [], row.get("_near_nominal_radii"))
        _draw_expected_line(out, detected_px, expected_px)

        lines = [
            f"{row['feature_label']}",
            f"meas={row['measured_diameter_mm']}mm  nom={row['nominal_mm']}mm",
            f"dev={row['deviation_mm']:+.5f}mm  {row['pass_fail']}",
            f"cal={row['calibration_source']}",
        ]
        if row.get("ray_cast_time_s") not in (None, ""):
            lines.append(
                f"ray_t={row['ray_cast_time_s']*1000:.2f}ms  "
                f"hits={row.get('n_rays_hit','?')}/{row.get('n_rays','?')}  "
                f"{row.get('fallback_mode','')}"
            )

        _draw_diagnostic_text(out, detected_px, lines)

    return out


def process_image(cartridge_id, image_path, calibration, calibration_mode="json"):
    img_type = detect_image_type(image_path)

    t0 = time.perf_counter()
    preprocessed = preprocess(image_path, image_type=img_type)
    t_preprocess = time.perf_counter() - t0

    cal_result = resolve_scale_factor(image_path, img_type, calibration,
                                       calibration_mode=calibration_mode)
    mm_per_px = cal_result["mm_per_px"]
    calibration_source = cal_result["source"]

    bgr = preprocessed["bgr"]
    ts = datetime.now().isoformat(timespec="seconds")
    rows = []
    result = None
    annotated = None
    t_detect = 0.0

    if img_type == "holes":
        debug_context = {}
        t1 = time.perf_counter()
        result = detect_holes(preprocessed, mm_per_px, debug_context=debug_context)
        t_detect = time.perf_counter() - t1
        annotated = annotate_holes(bgr, result, mm_per_px)

        for c in result["circles"]:
            tag = c["dwg_tag"]
            dbg = debug_context.get("per_hole", {}).get(tag, {})
            expected_px = dbg.get("expected_px")
            detected_px = (c["cx_px"], c["cy_px"])
            row = {
                "cartridge_id": cartridge_id,
                "image_type": "holes",
                "feature_label": "Tag" + str(tag),
                "status": "detected",
                "detected_cx_px": c["cx_px"],
                "detected_cy_px": c["cy_px"],
                "expected_cx_px": expected_px[0] if expected_px else "",
                "expected_cy_px": expected_px[1] if expected_px else "",
                "center_error_px": _dist(detected_px, expected_px),
                "measured_diameter_px": c["diameter_px"],
                "measured_diameter_mm": c["diameter_mm"],
                "nominal_mm": NOMINAL_MM["holes"],
                "deviation_mm": c["deviation_mm"],
                "pass_fail": "PASS" if c["pass"] else "FAIL",
                "calibration_source": calibration_source,
                "n_rays": dbg.get("n_rays", ""),
                "n_rays_hit": dbg.get("n_hit", ""),
                "fallback_mode": dbg.get("fallback_mode", ""),
                "ray_cast_time_s": dbg.get("ray_cast_time_s", ""),
                "_rays": dbg.get("rays"),
                "_near_nominal_radii": dbg.get("near_nominal_radii"),
                "timestamp": ts,
            }
            rows.append(row)

        for m in result.get("missing_holes", []):
            predicted = m.get("predicted_px", ("", ""))
            row = {
                "cartridge_id": cartridge_id,
                "image_type": "holes",
                "feature_label": "Tag" + str(m["dwg_tag"]),
                "status": m.get("reason", "not_detected"),
                "detected_cx_px": "",
                "detected_cy_px": "",
                "expected_cx_px": predicted[0],
                "expected_cy_px": predicted[1],
                "center_error_px": "",
                "measured_diameter_px": "",
                "measured_diameter_mm": "",
                "nominal_mm": NOMINAL_MM["holes"],
                "deviation_mm": "",
                "pass_fail": "NOT_MEASURED",
                "calibration_source": calibration_source,
                "n_rays": "",
                "n_rays_hit": "",
                "fallback_mode": "",
                "ray_cast_time_s": "",
                "_rays": None,
                "_near_nominal_radii": None,
                "timestamp": ts,
            }
            rows.append(row)

    elif img_type == "mixing":
        debug_context = {}
        t1 = time.perf_counter()
        result = detect_mixing(preprocessed, mm_per_px, debug_context=debug_context)
        t_detect = time.perf_counter() - t1
        annotated = annotate_mixing(bgr, result, mm_per_px)

        for h in result["holes"]:
            dbg = debug_context.get("per_hole", {}).get(h["id"], {})
            expected_px = dbg.get("expected_px")
            detected_px = (h["cx_px"], h["cy_px"])
            row = {
                "cartridge_id": cartridge_id,
                "image_type": "mixing",
                "feature_label": h["id"],
                "status": "detected",
                "detected_cx_px": h["cx_px"],
                "detected_cy_px": h["cy_px"],
                "expected_cx_px": expected_px[0] if expected_px else "",
                "expected_cy_px": expected_px[1] if expected_px else "",
                "center_error_px": _dist(detected_px, expected_px),
                "measured_diameter_px": h["diameter_px"],
                "measured_diameter_mm": h["diameter_mm"],
                "nominal_mm": NOMINAL_MM["mixing"],
                "deviation_mm": h["deviation_mm"],
                "pass_fail": "PASS" if h["pass"] else "FAIL",
                "calibration_source": calibration_source,
                "n_rays": dbg.get("n_rays", ""),
                "n_rays_hit": dbg.get("n_hit", ""),
                "fallback_mode": dbg.get("fallback_mode", ""),
                "ray_cast_time_s": dbg.get("ray_cast_time_s", ""),
                "_rays": dbg.get("rays"),
                "_near_nominal_radii": dbg.get("near_nominal_radii"),
                "timestamp": ts,
            }
            rows.append(row)

    elif img_type == "dab":
        debug_context = {}
        t1 = time.perf_counter()
        result = detect_dab(preprocessed, mm_per_px, debug_context=debug_context)
        t_detect = time.perf_counter() - t1
        annotated = annotate_dab(bgr, result, mm_per_px)

        row = {
            "cartridge_id": cartridge_id,
            "image_type": "dab",
            "feature_label": "DAB_hole",
            "status": "detected",
            "detected_cx_px": result["cx_px"],
            "detected_cy_px": result["cy_px"],
            "expected_cx_px": "",
            "expected_cy_px": "",
            "center_error_px": "",
            "measured_diameter_px": result["diameter_px"],
            "measured_diameter_mm": result["diameter_mm"],
            "nominal_mm": NOMINAL_MM["dab"],
            "deviation_mm": result["deviation_mm"],
            "pass_fail": "PASS" if result["pass"] else "FAIL",
            "calibration_source": calibration_source,
            "n_rays": debug_context.get("n_rays", ""),
            "n_rays_hit": debug_context.get("n_hit", ""),
            "fallback_mode": debug_context.get("fallback_mode", ""),
            "ray_cast_time_s": debug_context.get("ray_cast_time_s", ""),
            "_rays": debug_context.get("rays"),
            "_near_nominal_radii": debug_context.get("near_nominal_radii"),
            "timestamp": ts,
        }
        rows.append(row)

    elif img_type == "neck":
        t1 = time.perf_counter()
        result = detect_neck(preprocessed, mm_per_px)
        t_detect = time.perf_counter() - t1
        annotated = annotate_neck(bgr, result)

        if "error" not in result:
            tol = result["tolerance"]
            row = {
                "cartridge_id": cartridge_id,
                "image_type": "neck",
                "feature_label": "neck_width",
                "status": "detected",
                "detected_cx_px": result["narrowest_xy_px"][0],
                "detected_cy_px": result["narrowest_xy_px"][1],
                "expected_cx_px": "",
                "expected_cy_px": "",
                "center_error_px": "",
                "measured_diameter_px": result["mean_width_px"],
                "measured_diameter_mm": result["trimmed_mean_mm"],
                "nominal_mm": NOMINAL_MM["neck"],
                "deviation_mm": tol["deviation_mm"],
                "pass_fail": "PASS" if tol["pass"] else "FAIL",
                "calibration_source": calibration_source,
                "n_rays": "",
                "n_rays_hit": "",
                "fallback_mode": "",
                "ray_cast_time_s": "",
                "_rays": None,
                "_near_nominal_radii": None,
                "timestamp": ts,
            }
            rows.append(row)
        else:
            row = {
                "cartridge_id": cartridge_id,
                "image_type": "neck",
                "feature_label": "neck_width",
                "status": "error",
                "detected_cx_px": "",
                "detected_cy_px": "",
                "expected_cx_px": "",
                "expected_cy_px": "",
                "center_error_px": "",
                "measured_diameter_px": "",
                "measured_diameter_mm": "",
                "nominal_mm": NOMINAL_MM["neck"],
                "deviation_mm": "",
                "pass_fail": "ERROR",
                "calibration_source": calibration_source,
                "n_rays": "",
                "n_rays_hit": "",
                "fallback_mode": "",
                "ray_cast_time_s": "",
                "_rays": None,
                "_near_nominal_radii": None,
                "timestamp": ts,
            }
            rows.append(row)

    else:
        return None

    diag = draw_validation_overlay(annotated, rows)

    image_record = {
        "cartridge_id": cartridge_id,
        "image_type": img_type,
        "image_path": image_path,
        "preprocessing_time_s": round(t_preprocess, 4),
        "detection_time_s": round(t_detect, 4),
        "overall_pass": result.get("overall_pass", False),
        "calibration_source": calibration_source,
        "mm_per_px": mm_per_px,
    }

    return {
        "rows": rows,
        "overlay": diag,
        "image_record": image_record,
        "img_type": img_type,
    }


CSV_COLUMNS = [
    "cartridge_id",
    "feature_label",
    "image_type",
    "status",
    "detected_cx_px",
    "detected_cy_px",
    "expected_cx_px",
    "expected_cy_px",
    "center_error_px",
    "measured_diameter_px",
    "measured_diameter_mm",
    "nominal_mm",
    "deviation_mm",
    "pass_fail",
    "calibration_source",
    "n_rays",
    "n_rays_hit",
    "fallback_mode",
    "ray_cast_time_s",
    "timestamp",
]


def write_validation_csv(all_rows, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)


def _mean(values):
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 5)


def build_cartridge_summary(cartridge_id, all_rows, image_records):
    n_measured = sum(1 for r in all_rows if r["status"] == "detected")
    n_failed = sum(1 for r in all_rows if r["pass_fail"] == "FAIL")
    n_missing = sum(1 for r in all_rows if r["status"] not in ("detected", "error"))
    n_fallback = sum(
        1 for r in all_rows
        if r.get("fallback_mode") not in ("", "normal", None)
    )
    center_errors = [
        r["center_error_px"] for r in all_rows
        if r.get("center_error_px") is not None
    ]
    deviations = [
        r["deviation_mm"] for r in all_rows
        if isinstance(r.get("deviation_mm"), (int, float))
    ]

    per_type_pass = {}
    for rec in image_records:
        per_type_pass[rec["image_type"]] = rec["overall_pass"]

    summary = {
        "cartridge_id": cartridge_id,
        "per_image_type_overall_pass": per_type_pass,
        "n_measured_features": n_measured,
        "n_failed_features": n_failed,
        "n_missing_features": n_missing,
        "n_features_using_fallback": n_fallback,
        "average_center_error_px": _mean(center_errors),
        "average_diameter_deviation_mm": _mean(deviations),
        "average_abs_diameter_deviation_mm": _mean([abs(d) for d in deviations]),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    return summary


def write_summary_json(summary, path):
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)


def write_summary_md(summary, path):
    lines = []
    lines.append("# Validation Summary -- Cartridge " + str(summary["cartridge_id"]))
    lines.append("")
    lines.append("## Per-image-type result")
    for itype, passed in summary["per_image_type_overall_pass"].items():
        verdict = "PASS" if passed else "FAIL"
        lines.append("- **" + itype + "**: " + verdict)
    lines.append("")
    lines.append("## Feature statistics")
    lines.append("- Measured features: " + str(summary["n_measured_features"]))
    lines.append("- Failed features: " + str(summary["n_failed_features"]))
    lines.append("- Missing features: " + str(summary["n_missing_features"]))
    lines.append("- Features using fallback mode: " + str(summary["n_features_using_fallback"]))
    lines.append("- Average center error (px): " + str(summary["average_center_error_px"]))
    lines.append("- Average diameter deviation (mm): " + str(summary["average_diameter_deviation_mm"]))
    lines.append("- Average |diameter deviation| (mm): " + str(summary["average_abs_diameter_deviation_mm"]))
    lines.append("")
    lines.append("_Generated: " + summary["generated_at"] + "_")

    with open(path, "w") as f:
        f.write("\n".join(lines))


def run_cartridge(cartridge_dir, calibration, output_root, calibration_mode="json"):
    cart_dir = Path(cartridge_dir)
    cartridge_id = cart_dir.name
    out_dir = Path(output_root) / cartridge_id
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    image_records = []

    for itype, fname in FILES.items():
        img_path = cart_dir / fname
        if not img_path.exists():
            continue
        res = process_image(cartridge_id, str(img_path), calibration,
                             calibration_mode=calibration_mode)
        if res is None:
            continue
        all_rows.extend(res["rows"])
        image_records.append(res["image_record"])
        overlay_path = out_dir / (itype + "_overlay.png")
        cv2.imwrite(str(overlay_path), res["overlay"])

    csv_path = out_dir / "validation.csv"
    write_validation_csv(all_rows, csv_path)

    summary = build_cartridge_summary(cartridge_id, all_rows, image_records)

    summary_json_path = out_dir / "summary.json"
    write_summary_json(summary, summary_json_path)

    summary_md_path = out_dir / "summary.md"
    write_summary_md(summary, summary_md_path)

    return {
        "cartridge_id": cartridge_id,
        "rows": all_rows,
        "image_records": image_records,
        "summary": summary,
        "out_dir": str(out_dir),
    }


def run_dataset(dataset_root, calibration, output_root, calibration_mode="json", cartridges=None):
    root = Path(dataset_root)
    if cartridges is None:
        found = [d.name for d in root.iterdir() if d.is_dir()]
        cartridges = sorted(found, key=lambda n: (not n.isdigit(), int(n) if n.isdigit() else n))

    results = []
    for cid in cartridges:
        r = run_cartridge(str(root / cid), calibration, output_root,
                           calibration_mode=calibration_mode)
        results.append(r)
        print("  Cartridge " + cid + ": done -> " + r["out_dir"])
    return results
