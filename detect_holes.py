# =============================================================================
# NEW ROBUST HOLE DETECTION
# Replaces detect_holes() completely
# =============================================================================

import cv2
import numpy as np


def detect_holes(preprocessed, mm_per_px, debug=False):
    """
    Robust contour-based hole detection.

    Improvements over old version:
    --------------------------------
    ✓ No HoughCircles dependency
    ✓ No hardcoded hole positions
    ✓ No hardcoded offsets
    ✓ No fixed pixel radii
    ✓ Robust against illumination variation
    ✓ Robust against stitching artifacts
    ✓ Robust against partial teardrop overlap
    ✓ Uses ellipse fitting (subpixel accurate)
    ✓ Uses geometric filtering instead of image-specific logic

    Detection pipeline:
    -------------------
    1. Illumination normalization
    2. Adaptive thresholding
    3. Morphological cleanup
    4. Contour extraction
    5. Circularity filtering
    6. Ellipse fitting
    7. Size filtering using calibration
    """

    # =========================================================================
    # INPUT IMAGE
    # =========================================================================

    bgr = preprocessed["bgr"]

    if len(bgr.shape) == 3:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = bgr.copy()

    h, w = gray.shape

    # =========================================================================
    # EXPECTED SIZE FROM CALIBRATION
    # =========================================================================

    expected_diameter_px = 0.50 / mm_per_px
    expected_radius_px = expected_diameter_px / 2

    print("\n" + "=" * 70)
    print("ROBUST CONTOUR-BASED HOLE DETECTION")
    print("=" * 70)
    print(f"Expected diameter : {expected_diameter_px:.1f} px")
    print(f"Expected radius   : {expected_radius_px:.1f} px")
    print(f"Scale             : {mm_per_px*1000:.3f} um/px")

    # =========================================================================
    # STEP 1 — ILLUMINATION NORMALIZATION
    # =========================================================================

    bg = cv2.GaussianBlur(gray, (151, 151), 0)

    norm = cv2.divide(gray, bg, scale=255)

    # =========================================================================
    # STEP 2 — CONTRAST ENHANCEMENT
    # =========================================================================

    clahe = cv2.createCLAHE(
        clipLimit=2.5,
        tileGridSize=(8, 8)
    )

    enhanced = clahe.apply(norm)

    # =========================================================================
    # STEP 3 — DENOISE
    # =========================================================================

    blur = cv2.GaussianBlur(enhanced, (7, 7), 1.5)

    # =========================================================================
    # STEP 4 — ADAPTIVE THRESHOLD
    # =========================================================================

    th = cv2.adaptiveThreshold(
        blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        51,
        5
    )

    # =========================================================================
    # STEP 5 — MORPHOLOGY
    # =========================================================================

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (5, 5)
    )

    th = cv2.morphologyEx(
        th,
        cv2.MORPH_OPEN,
        kernel,
        iterations=1
    )

    th = cv2.morphologyEx(
        th,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=2
    )

    # =========================================================================
    # STEP 6 — FIND CONTOURS
    # =========================================================================

    contours, _ = cv2.findContours(
        th,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    print(f"Contours found: {len(contours)}")

    # =========================================================================
    # STEP 7 — FILTER CONTOURS
    # =========================================================================

    detected = []

    min_area = np.pi * (expected_radius_px * 0.45) ** 2
    max_area = np.pi * (expected_radius_px * 1.8) ** 2

    for cnt in contours:

        area = cv2.contourArea(cnt)

        # ---------------------------------------------------------------------
        # AREA FILTER
        # ---------------------------------------------------------------------

        if area < min_area:
            continue

        if area > max_area:
            continue

        # ---------------------------------------------------------------------
        # NEED ENOUGH POINTS FOR ELLIPSE
        # ---------------------------------------------------------------------

        if len(cnt) < 5:
            continue

        # ---------------------------------------------------------------------
        # PERIMETER
        # ---------------------------------------------------------------------

        perimeter = cv2.arcLength(cnt, True)

        if perimeter <= 0:
            continue

        # ---------------------------------------------------------------------
        # CIRCULARITY
        # ---------------------------------------------------------------------

        circularity = (
            4 * np.pi * area /
            (perimeter * perimeter)
        )

        if circularity < 0.55:
            continue

        # ---------------------------------------------------------------------
        # FIT ELLIPSE
        # ---------------------------------------------------------------------

        ellipse = cv2.fitEllipse(cnt)

        (cx, cy), (major, minor), angle = ellipse

        # ---------------------------------------------------------------------
        # DIAMETER
        # ---------------------------------------------------------------------

        diameter_px = (major + minor) / 2

        # ---------------------------------------------------------------------
        # SIZE FILTER
        # ---------------------------------------------------------------------

        size_error = abs(
            diameter_px - expected_diameter_px
        ) / expected_diameter_px

        if size_error > 0.45:
            continue

        # ---------------------------------------------------------------------
        # ASPECT RATIO
        # ---------------------------------------------------------------------

        aspect_ratio = max(major, minor) / min(major, minor)

        if aspect_ratio > 1.35:
            continue

        # ---------------------------------------------------------------------
        # SOLIDITY
        # ---------------------------------------------------------------------

        hull = cv2.convexHull(cnt)

        hull_area = cv2.contourArea(hull)

        if hull_area <= 0:
            continue

        solidity = area / hull_area

        if solidity < 0.85:
            continue

        # ---------------------------------------------------------------------
        # MM CONVERSION
        # ---------------------------------------------------------------------

        diameter_mm = diameter_px * mm_per_px

        tol = _tol_check(
            diameter_mm,
            "hole_diameter"
        )

        # ---------------------------------------------------------------------
        # SAVE
        # ---------------------------------------------------------------------

        detected.append({
            "cx_px": round(float(cx), 2),
            "cy_px": round(float(cy), 2),

            "diameter_px": round(float(diameter_px), 2),
            "diameter_mm": round(float(diameter_mm), 5),

            "radius_px": round(float(diameter_px / 2), 2),

            "circularity": round(float(circularity), 3),
            "solidity": round(float(solidity), 3),
            "aspect_ratio": round(float(aspect_ratio), 3),

            "deviation_mm": tol["deviation_mm"],
            "pass": tol["pass"],

            "contour": cnt,
        })

    # =========================================================================
    # STEP 8 — REMOVE DUPLICATES
    # =========================================================================

    final = []

    min_center_distance = expected_radius_px * 1.2

    for d in sorted(
        detected,
        key=lambda x: x["circularity"],
        reverse=True
    ):

        keep = True

        for f in final:

            dist = np.sqrt(
                (d["cx_px"] - f["cx_px"]) ** 2 +
                (d["cy_px"] - f["cy_px"]) ** 2
            )

            if dist < min_center_distance:
                keep = False
                break

        if keep:
            final.append(d)

    # =========================================================================
    # STEP 9 — SORT GEOMETRICALLY
    # =========================================================================

    final = sorted(
        final,
        key=lambda x: (x["cy_px"], x["cx_px"])
    )

    # =========================================================================
    # STEP 10 — ASSIGN TAGS
    # =========================================================================

    for i, d in enumerate(final):
        d["dwg_tag"] = i + 1

    # =========================================================================
    # OVERALL PASS
    # =========================================================================

    overall_pass = all(
        d["pass"]
        for d in final
    ) if len(final) > 0 else False

    print(f"Final holes detected: {len(final)}")

    # =========================================================================
    # DEBUG VISUALIZATION
    # =========================================================================

    if debug:

        dbg = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        for d in final:

            cx = int(d["cx_px"])
            cy = int(d["cy_px"])

            r = int(d["radius_px"])

            col = (0, 255, 0) if d["pass"] else (0, 0, 255)

            cv2.circle(
                dbg,
                (cx, cy),
                r,
                col,
                3
            )

            cv2.circle(
                dbg,
                (cx, cy),
                3,
                (255, 255, 0),
                -1
            )

            txt = (
                f"{d['dwg_tag']}  "
                f"{d['diameter_mm']:.3f}mm"
            )

            cv2.putText(
                dbg,
                txt,
                (cx + 20, cy - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                col,
                2
            )

        cv2.imwrite(
            "debug_hole_detection.png",
            dbg
        )

        cv2.imwrite(
            "debug_threshold.png",
            th
        )

        print("Saved:")
        print("  debug_hole_detection.png")
        print("  debug_threshold.png")

    # =========================================================================
    # RETURN
    # =========================================================================

    return {
        "circles": final,

        "n_detected": len(final),

        "overall_pass": overall_pass,

        "all_found": len(final) > 0,
    }