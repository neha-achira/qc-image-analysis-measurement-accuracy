"""
Production confidence scoring module (Stage 20).

Implements the confidence score designed and validated in
docs/STAGE19_DETECTION_CONFIDENCE_INVESTIGATION.md, using only metrics
detect_holes() already computes for every matched hole: ray-hit count,
near-nominal ratio, angular gap, fallback mode, and distance from the
geometrically-predicted position.

This module performs NO image processing and detects nothing on its own.
It is a pure function of values already computed elsewhere in the
pipeline, and its output (confidence_pct, confidence_category) is an
informational annotation only. It MUST NOT be consulted by candidate
generation, candidate assignment (Stage 1/Stage 2), the recovery pass,
measurement, or PASS/FAIL logic -- those are computed first, unaffected,
and confidence is attached afterward as an additional, read-only field.
"""

# Reused directly from detect_features.py's own RECOVERY_TOL_PX constant
# (docs/STAGE6_RECOVERY_PASS_DESIGN.md) rather than a new invented value --
# see docs/STAGE19_DETECTION_CONFIDENCE_INVESTIGATION.md Section 4.2.
RECOVERY_TOL_PX = 690.0

# Heuristic normalization choices, disclosed as such in
# docs/STAGE19_DETECTION_CONFIDENCE_INVESTIGATION.md Section 4.2 -- not
# derived from the metric distributions, but geometrically/operationally
# motivated judgment calls.
ANGULAR_GAP_CAP_DEG = 180.0   # beyond a half-circle gap, treat as equally uninformative
RAY_QUALITY_WEIGHT = 0.70     # dominant weight: mirrors _stage2_rank_key's own
GEOMETRIC_WEIGHT = 0.30       # ordering, where distance is already the last tiebreaker

# fallback_mode gate (multiplicative). "off_nominal_fallback" never occurs in
# the 541-tag validated population (Stage 19 Section 1) -- 0.5 is an explicit,
# disclosed default with no supporting data, not an empirically-derived value.
FALLBACK_GATE = {
    "normal": 1.0,
    "off_nominal_fallback": 0.5,
    "total_failure": 0.0,
}

# Category breakpoints are an operational convention (Stage 19 Section 5),
# not statistically derived cut points. Checked in descending order.
CATEGORY_THRESHOLDS = (
    (90.0, "High"),
    (70.0, "Medium"),
    (40.0, "Low"),
    (0.0, "Very Low"),
)


def compute_confidence(n_hit, n_rays, near_nominal_ratio, angular_gap_deg,
                        fallback_mode, dist_from_predicted_px):
    """
    Compute a 0-100% confidence score and category for one matched hole.

    All six inputs are values detect_holes() already computes for the
    matched candidate -- this function performs no additional detection
    or image analysis of its own.

    Returns
    -------
    (confidence_pct, confidence_category) : (float, str)
    """
    angular_uniformity = 1.0 - min(angular_gap_deg, ANGULAR_GAP_CAP_DEG) / ANGULAR_GAP_CAP_DEG
    ray_frac = (n_hit / n_rays) if n_rays else 0.0
    ray_quality = (near_nominal_ratio + ray_frac + angular_uniformity) / 3.0

    geometric_consistency = 1.0 - min(dist_from_predicted_px, RECOVERY_TOL_PX) / RECOVERY_TOL_PX

    raw_score = RAY_QUALITY_WEIGHT * ray_quality + GEOMETRIC_WEIGHT * geometric_consistency
    gate = FALLBACK_GATE.get(fallback_mode, 0.0)

    confidence_pct = 100.0 * raw_score * gate
    confidence_pct = max(0.0, min(100.0, confidence_pct))
    confidence_pct = round(confidence_pct, 1)

    category = "Very Low"
    for threshold, label in CATEGORY_THRESHOLDS:
        if confidence_pct >= threshold:
            category = label
            break

    return confidence_pct, category
