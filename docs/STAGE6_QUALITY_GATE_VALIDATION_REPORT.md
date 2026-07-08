# Stage 6 — Quality Gate Validation Report

**Status:** Validation only. No production code modified. Nothing implemented.
**Branch:** `stage6-detection-recall-analysis`
**Prerequisite:** `docs/STAGE6_RECOVERY_PASS_DESIGN.md` — the approved-in-principle recovery pass design, whose quality gate (`fallback_mode=="normal"` AND `near_nominal_ratio>=0.70` AND `max_angular_gap<=40°`) this report validates before any implementation.

---

## 1. Complete Candidate Enumeration

Every candidate the proposed recovery pass would actually consider was enumerated — not sampled — across all 79 validated cartridges (1–33, 34–50, 51–60, 61–70(1), 71–79). For every currently-missing tag (using the exact, unmodified current production algorithm: Stage 1 nearest-distance anchor competition + Stage 2 ranking, `MATCH_TOL_PX=600`), excluding tags whose true predicted position is genuinely `outside_image`, every raw Hough candidate within `RECOVERY_TOL_PX=690px` that is **not already claimed by any currently-matched tag** was recorded, with the full metric suite computed for each.

**Result: exactly 7 candidates exist in the entire 79-cartridge dataset.** This is a structural fact of the design, not under-sampling — of the 25 currently-missing holes, 14 are genuinely outside the captured frame (never searched, per design) and 5 more have their nearest candidate beyond the 690px radius (849–1408px, never reached). Only 6 missing tags have any candidate within range at all, and one of those (Cartridge 18/Tag 1) has two competing candidates.

## 2. Full Metric Table (every candidate, complete population)

| Candidate | Distance (px) | Fallback mode | n_hit/36 | near_nominal/36 | Near ratio | Max angular gap | Wall fraction |
|---|---|---|---|---|---|---|---|
| Cartridge 18/Tag 1 — candidate A | 621.2 | normal | 36 | 34 | 0.944 | 10.0° | 0.472 |
| Cartridge 18/Tag 1 — candidate B | 650.2 | off_nominal_fallback | 27 | 0 | 0.000 | 100.0° | 0.306 |
| Cartridge 18/Tag 3 | 629.7 | normal | 36 | 36 | 1.000 | 10.0° | 0.639 |
| Cartridge 18/Tag 5 | 619.1 | normal | 36 | 36 | 1.000 | 10.0° | 0.417 |
| Cartridge 18/Tag 6 | 625.2 | normal | 36 | 36 | 1.000 | 10.0° | 1.000 |
| Cartridge 18/Tag 7 | 630.2 | normal | 36 | 35 | 0.972 | 10.0° | 0.597 |
| Cartridge 45/Tag 6 | 626.2 | normal | 26 | 19 | 0.528 | 70.0° | 0.250 |

## 3. Visual Classification (ground truth, using visual evidence)

All 7 candidates were visually inspected (6 previously, in the design phase; the 7th — Cartridge 18/Tag 1's second candidate — newly generated and reviewed for this report):

| Candidate | Classification | Visual evidence |
|---|---|---|
| Cartridge 18/Tag 1 — candidate A | **Confirmed genuine** | Clean, continuous 36/36 ray ring on a real dark boundary |
| Cartridge 18/Tag 1 — candidate B | **Confirmed false positive** | Ray hits form a partial "C"-shaped arc near the image's active-area border, not a closed ring on any real feature |
| Cartridge 18/Tag 3 | **Confirmed genuine** | Clean 36/36 ring |
| Cartridge 18/Tag 5 | **Confirmed genuine** | Clean 36/36 ring |
| Cartridge 18/Tag 6 | **Confirmed genuine** | Clean 36/36 ring |
| Cartridge 18/Tag 7 | **Confirmed genuine** | Clean 36/35 ring |
| Cartridge 45/Tag 6 | **Confirmed false positive** | Ray hits trace a partial arc along a curved channel-wall edge, not a hole |

**Zero "uncertain" classifications** — every candidate in the complete population was confidently classified from direct visual evidence.

## 4. Metric Distributions

With only 7 candidates in the true population, "distributions" are necessarily small-sample, and are reported as complete value lists rather than binned histograms:

**Near-nominal ratio:**
- Genuine (n=5): {0.944, 1.000, 1.000, 1.000, 0.972} — range 0.944–1.000, mean 0.983
- False positive (n=2): {0.000, 0.528} — range 0.000–0.528, mean 0.264
- **Gap between populations: 0.416** (0.528 to 0.944) — no overlap.

**Max angular gap:**
- Genuine (n=5): {10.0°, 10.0°, 10.0°, 10.0°, 10.0°} — zero variance, all identical (the theoretical minimum for 36 rays with a full ring of hits)
- False positive (n=2): {100.0°, 70.0°} — range 70–100°
- **Gap between populations: 60°** (10° to 70°) — no overlap.

**n_hit (for reference — the signal explicitly flagged as insufficient on its own):**
- Genuine (n=5): {36, 36, 36, 36, 36} — all maximal
- False positive (n=2): {27, 26}
- Gap exists in *this specific population* (26 to 36), but this is not treated as reliable in isolation — see §5.

**Wall fraction:**
- Genuine (n=5): {0.472, 0.639, 0.417, 1.000, 0.597} — range 0.417–1.000
- False positive (n=2): {0.306, 0.250}
- Some separation exists here too, but with a narrower gap (0.306 to 0.417) and previously demonstrated (in the design report) to overlap with genuine holes elsewhere in this project's broader data — **not** relied upon.

## 5. Does a Single Threshold Cleanly Separate the Populations?

**Yes, for the two recommended signals — both individually and combined — with a wide margin, on the complete, exhaustive in-scope population:**
- `near_nominal_ratio`: any threshold in (0.528, 0.944) separates perfectly. The proposed 0.70 sits roughly in the middle of this gap.
- `max_angular_gap`: any threshold in (10°, 70°) separates perfectly. The proposed 40° sits roughly in the middle of this gap.

**A caveat on `n_hit` alone:** in this specific 7-candidate population, `n_hit` also happens to separate cleanly (26–27 vs. 36). **This is not treated as evidence that ray-hit count alone is a reliable gate** — the design report's broader investigation (which included false positives from outside this exact population, found during the Stage 6 tolerance sweep) already showed `n_hit` values as high as 26 for false positives and as low as 24 for at least one genuine-but-imperfect hole elsewhere in this project's data, meaning the apparent separation here is likely a property of this small sample, not a general rule. The two recommended signals (`near_nominal_ratio`, `max_angular_gap`) were chosen because they target the underlying *shape* of the ray-hit pattern (is it a plausible full circle, at a plausible size) rather than a raw count, which is why they are expected to generalize better — a claim now given additional support by the stress test in §6.

## 6. Out-of-Sample Stress Test

To go beyond the 7-candidate in-scope population, the same gate was additionally applied to 3 more confirmed false positives from the broader Stage 6 tolerance-sweep investigation (`docs/STAGE6_ALGORITHM_EVALUATION_REPORT.md`) — Cartridge 38/Tag 9, Cartridge 46/Tag 4, and Cartridge 48/Tag 1 (all post-regression positions). **These would never actually be considered by this design's recovery pass** (they arose from Stage 1 anchor-selection instability under a shared/global tolerance increase — the exact mechanism this frozen-anchor design eliminates by construction), so they are not part of the true candidate population in §1. They are included here purely as an additional, independent robustness check on the gate itself.

| Candidate | near_nominal_ratio | max_angular_gap | Gate result |
|---|---|---|---|
| Cartridge 38/Tag 9 (post-instability) | 0.222 | 120° | Correctly rejected |
| Cartridge 46/Tag 4 (post-instability) | 0.333 | not separately measured | Correctly rejected (ratio alone fails) |
| Cartridge 48/Tag 1 (post-instability) | 0.139 | 110° | Correctly rejected |

All 3 are correctly rejected by the same, unmodified gate thresholds — no adjustment was needed to make this pass.

## 7. Confusion Matrix, Precision, Recall, False-Positive Rate, False-Negative Rate

Combining the complete in-scope population (§3) with the out-of-sample stress test (§6) for a fuller picture (10 total evaluated candidates):

|  | Predicted genuine (gate passes) | Predicted false (gate rejects) |
|---|---|---|
| **Actually genuine** | 5 (True Positive) | 0 (False Negative) |
| **Actually false positive** | 0 (False Positive) | 5 (True Negative) |

- **Precision** (of candidates the gate accepts, fraction actually genuine): 5/5 = **100%**
- **Recall** (of genuine candidates, fraction the gate accepts): 5/5 = **100%**
- **False-positive rate** (of false positives, fraction incorrectly accepted): 0/5 = **0%**
- **False-negative rate** (of genuine holes, fraction incorrectly rejected): 0/5 = **0%**

**The proposed gate achieves perfect separation on every candidate tested — both the true in-scope population and the additional out-of-scope stress test.**

## 8. Honest Statement on Statistical Power

10 total evaluated candidates (7 in-scope + 3 stress-test) is a small sample in absolute terms. This is not a shortcoming of the validation method — the in-scope population (N=7) is the **complete, exhaustive set** for this exact design given the current 79-cartridge dataset, not a sample drawn from a larger pool. There is no larger in-scope population to sample further from today. The honest limitation is forward-looking: as more cartridges are processed in production, new candidates this gate has never seen will appear, and the clean separation demonstrated here — while consistent across every case checked, including out-of-scope stress cases — should not be treated as a permanent guarantee. The validation plan already specified in `docs/STAGE6_RECOVERY_PASS_DESIGN.md` §6 (mandatory visual review of every future newly-recovered hole, not just the ones known today) remains the correct safeguard against this, and this report does not change that requirement.

## 9. Redesign Assessment

Per your instruction: redesign is required only if the proposed gate does not achieve sufficiently high precision. **It does — 100% precision and 100% recall on every candidate evaluated, with no ambiguous or uncertain cases.** No redesign is triggered by this validation. The gate as specified in the approved design (`fallback_mode=="normal"` AND `near_nominal_ratio>=0.70` AND `max_angular_gap<=40°`) is retained unchanged.

## 10. Conclusion

The proposed quality gate generalizes cleanly across the complete, validated dataset:
- The true candidate population the recovery pass would ever encounter is small (7) but was evaluated exhaustively, not sampled.
- Both recommended signals (`near_nominal_ratio`, `max_angular_gap`) show a wide, non-overlapping separation between genuine holes and false positives, with no threshold-tuning required to achieve it.
- The gate correctly classifies all 10 candidates tested, including 3 out-of-scope stress-test cases it was never designed against.
- No redesign is needed. The design in `docs/STAGE6_RECOVERY_PASS_DESIGN.md` is validated as specified.

Nothing has been implemented. This report is a validation of the existing design only — implementation should proceed only after your explicit approval of this validation.
