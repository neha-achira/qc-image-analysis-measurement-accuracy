# Stage 7 — Geometric Model Investigation Report

**Status:** Investigation complete. Design report only — no production code modified.
**Branch:** `stage7-geometric-model-investigation` (no commits; read-only analysis in scratchpad scripts).
**Objective (as given):** determine why Cartridge 72 violates the geometric model while other validated cartridges do not — not a general recall investigation.

---

## 1. Executive Summary

Cartridge 72 does **not** have a warped, rotated, scaled, or otherwise geometrically distorted layout. Six of its seven tag holes (Tags 1, 3, 4, 5, 6, 7) fit the reference geometry (`REF_OFFSETS`) with a residual (6.3–7.0px RMS after fitting scale+rotation+translation) that is statistically indistinguishable from a normal, fully-matched baseline cartridge (Cartridge 1: 5.8–5.9px RMS under the same models). **There is no geometric anomaly to correct.**

The actual defect is narrower and more mechanical: the seventh position (Tag 9, which production uses as its anchor/reference tag) is occupied in the image by a real but **oversized, non-circular physical feature** — visually, a channel/port merging into what would otherwise be the mounting hole — that falls outside the Hough circle detector's configured radius range and is therefore never generated as a candidate at all. The nearest raw Hough candidate to the true Tag9 location is 639px away and only moderate quality (17/36 ray hits), so it cannot serve as an anchor either (it correctly fails both the production match tolerance and the Stage 6 recovery-pass quality gate).

Because the current algorithm's Stage 1 anchor competition only ever tries a candidate as if it were **Tag 9 specifically** (offset (0,0) in `REF_OFFSETS`), and no valid candidate exists at that location, the competition is forced to settle for an unrelated, lower-scoring false-positive elsewhere in the image (previously identified in Stage 5 as sitting on plain texture). This is why production currently reports only a partial, incorrect match (3/7) instead of the achievable 6/7 (all real holes except the one that isn't a normal hole at all).

**Recommended correction:** generalize the anchor competition to try each raw candidate against each of the 7 possible tag roles (not hard-coded to Tag 9 alone), keeping every other stage, tolerance, and quality gate unchanged. This is a minimal extension of the *existing* brute-force competition design, not a new mechanism, and does not require detecting the oversized Tag9 feature at all.

Of the 5 cartridges initially flagged by the population-wide scan, only **Cartridge 72** exhibits this failure mode. The other 4 (Cartridges 45, 48, 49, 50 — all in the 34-50/WB(2) dataset) show a materially different, more severe pattern (few high-quality candidates, inconsistent/implausible scale and rotation fits, large residuals even on best-effort fits, and visually more cluttered images with large channel/chamber structures) — they are **out of scope** for this investigation and are flagged for separate, dedicated analysis.

---

## 2. Population-Wide Search (Step 1 of scope)

**Method:** replayed Hough detection + ray-cast quality scoring for all 79 validated cartridges (1–33, 34–50, 51–60, 61–70(1), 71–79), unmodified from the committed algorithm. For each cartridge, computed:
- The current production result (Stage 1 anchor competition + Stage 2 refinement + Stage 6 recovery pass, replayed exactly).
- An independent, anchor-model-free census of "quality-confirmed real holes" — every raw Hough candidate passing the Stage 6 recovery-pass quality gate (`fallback_mode=="normal"`, `near_nominal_ratio>=0.70`, `max_angular_gap<=40°`), regardless of distance to any predicted position.

**Result — cartridges with ≥2 tags still missing after production + recovery pass:**

| Dataset/Cartridge | Missing tags (production) | Quality-confirmed real holes found |
|---|---|---|
| 71-79/**72** | 4 (1,3,4,5) | 7 |
| 34-50/49 | 6 (1,3,4,5,6,7) | 3 |
| 34-50/45 | 3 (5,6,7) | 3 |
| 34-50/48 | 3 (1,3,5) | 2 |
| 34-50/50 | 3 (3,5,7) | 3 |

All other 74 cartridges matched 7/7 (or 6/7 with the one pre-existing 1-33 case already characterized in Stage 5/6). No cartridge outside this list of 5 shows 2+ missing tags.

---

## 3. Cluster Analysis (Step 2 of scope) — Distinguishing Failure Modes

The four criteria from the investigation scope (anchor competition succeeds / Hough correctly detects real holes / Stage 2 behaves correctly / recovery pass cannot recover / multiple predicted positions systematically displaced) were tested for each of the 5 candidates by attempting a rigorous, translation/rotation/scale-invariant shape fit (RANSAC 2-point similarity-transform search, generalized brute-force pairwise-distance-ratio matching) using only the raw Hough output, independent of the production anchor.

| Cartridge | Quality holes found | Best achievable geometric fit | Fit quality |
|---|---|---|---|
| **72** | 7 | 6/7 tags (1,3,4,5,6,7), leaving out Tag9 | **Excellent** — similarity RMS 7.0px, affine RMS 6.3px, scale 0.997, rotation −0.74° |
| 49 | 3 | 4/7 tags (best RANSAC consensus) | Poor — scale 0.915, rotation 17.1°, residuals to 388px, several inlier candidates have `n_hit` as low as 11–12 |
| 45 | 3 | 4/7 tags (best RANSAC consensus) | Poor — scale 0.950, rotation 116.9° (implausible), residuals to 496px |
| 48 | 2 | 5/7 tags (best RANSAC consensus) | Poor — scale 0.851, rotation 12.2°, 2 of 5 "matched" points are `fallback_mode=total_failure` (n_hit 2–6) |
| 50 | 3 | 5/7 tags (best RANSAC consensus) | Poor — scale 0.879, rotation 11.5°, residuals to 490px |

A visual overview of Cartridge 49 (representative of the other three) shows a large circular chamber/reservoir feature and thick winding channel structures overlapping much of the frame — a substantially more visually cluttered image than Cartridge 72's flat baseplate. Combined with the small number of high-quality candidates (2–3 out of 7, vs. Cartridge 72's 6) and implausible/inconsistent fit parameters, this points to a **different root cause** (most likely image-content interference with Hough circle detection across multiple holes, possibly compounded by focus/illumination differences within the WB(2) batch) rather than Cartridge 72's clean single-point anchor-precision failure.

**Conclusion: only Cartridge 72 meets all four cluster criteria.** Cartridges 45, 48, 49, 50 are explicitly excluded from this investigation's scope, per the instruction not to investigate unrelated failures. They warrant a separate, dedicated Stage 8-type investigation focused on image quality / candidate-generation robustness in the WB(2) dataset specifically.

---

## 4. Cartridge 72 — Detailed Findings (Steps 2–6 of scope)

### 4.1 Current production state

- **Matched tags (production, with recovery pass):** 6, 7, 9 (3/7)
- **Missing tags:** 1, 3, 4, 5
- **Anchor chosen:** a candidate previously identified in Stage 5 as sitting on plain texture (false positive), which happens to achieve a 3/7 coincidental match.
- **Anchor quality:** poor — not a genuine hole.

### 4.2 Independent shape-based re-analysis (anchor-model-free)

Six raw Hough candidates in Cartridge 72 have **perfect ray-cast quality** (36/36 near-nominal hits, `fallback_mode=="normal"`):

| Candidate position | Assigned tag (best shape match) |
|---|---|
| (644, 416) | Tag 1 |
| (1084, 3080) | Tag 3 |
| (2456, 756) | Tag 4 |
| (2396, 5444) | Tag 5 |
| (3440, 1760) | Tag 6 |
| (3780, 3116) | Tag 7 |

This assignment was found via brute-force pairwise-distance-ratio matching (translation/rotation/scale invariant) against every permutation of 6-of-7 `REF_OFFSETS` tags, over all 6 candidates. It achieved by far the lowest ratio-error (0.057) of any assignment, with **Tag 9 as the unique best-fitting "missing" tag** — i.e., these 6 candidates correspond unambiguously to Tags 1,3,4,5,6,7, and no valid 7th candidate exists to complete the set.

### 4.3 Model fitting and residual quantification (Steps 3–5 of scope)

Fitting the 6 known-genuine tags against `REF_OFFSETS`, compared to a normal fully-matched baseline (Cartridge 1, 7/7 production match):

| Model | Cartridge 72 (6 tags) RMS | Cartridge 1 baseline (7 tags) RMS |
|---|---|---|
| Translation only | 27.84 px | 16.47 px |
| Rotation only (unit scale) | 8.94 px (rot = −0.738°) | 9.42 px (rot = −0.315°) |
| Scale only (no rotation) | 27.24 px (scale = 0.9972) | — |
| **Similarity (scale+rotation+translation)** | **7.01 px** (scale=0.9973, rot=−0.738°) | **5.88 px** (scale=0.9970) |
| Full affine (6-DOF) | 6.26 px | 5.77 px |

Residual plots: `validation_output/stage7_geometry/cart72_model_residuals.png` (per-tag prediction-vs-actual vectors for translation-only / similarity / affine) and `cart72_rms_by_model.png` (bar chart across all 5 models).

**Interpretation:** translation-only and scale-only both leave large (~27px) residuals; adding rotation collapses this to <9px, and the full similarity/affine fits converge to 6–7px — the same pattern, and near-identical magnitude, as the well-behaved baseline. The small residual that remains (6–7px) is consistent with ordinary sub-pixel ray-cast/detection noise, not a distortion. **Cartridge 72's geometry is normal.** The predicted true position of the missing Tag 9 hole under this fit is approximately **(6728–6730, 1790–1800)**.

### 4.4 Visual confirmation of the true anchor location

The predicted true Tag9 position was inspected directly in the source image (`validation_output/stage7_geometry/cart72_true_hole_tight_crop.png`). A real, clearly visible dark void is present almost exactly at the predicted location — but it is substantially **larger and non-circular** compared to the other 6 tags' clean ~100px-radius holes, appearing to be a point where a channel/groove structure merges into (or replaces) the expected mounting hole. This is very likely a genuine physical characteristic/anomaly of this specific cartridge at this specific location, not an imaging artifact (the location is well within the active image area, 455px from the nearest frame edge; no lens-edge distortion pattern is visible in the surrounding texture).

Because this feature is larger than Hough's configured search radius (`min_r`/`max_r` = 78–122% of the 100px nominal radius), **Hough correctly does not generate a circle candidate there** — this is expected behavior of a detector tuned for a specific hole size, not a bug. The nearest raw candidate Hough does produce nearby, (7072,1256), is 639px from the true position and only moderate quality (17/36 near-nominal hits, near-ratio 0.47 — below the 0.70 recovery-pass gate threshold). Using it as a hypothetical anchor was tested directly: it predicts all 6 other (now precisely known) real tag positions at errors of 656–709px — beyond the existing 600px match tolerance. **No raw candidate near the true Tag9 location can function as a working anchor.**

### 4.5 Root cause (Step 6 of scope — simplest explanatory model)

**Simplest model: none of translation/rotation/scale/affine distortion is needed — the geometry is unmodified.** The failure is entirely explained by a single-point candidate-generation gap: no valid Hough candidate exists at the true Tag9 location (the physical feature there isn't a matching-size circle), so production's anchor competition — which only ever tries a candidate as a hypothetical Tag9 — cannot find a working anchor and falls back to an incorrect one elsewhere, corrupting the reported match for all 7 tags rather than just the one that's genuinely absent.

This is not a geometric-model bug and not a Hough-tuning bug (widening Hough's radius range to catch this one oversized feature would risk false positives elsewhere, per the Stage 6 evaluation's findings on channel-wall/texture false positives). It is an **anchor-selection design limitation**: the competition's search space is artificially restricted to "candidate as Tag9" when it could just as validly try "candidate as Tag1" or any other tag role.

---

## 5. Recommended Algorithmic Correction (Step 7 of scope)

**Generalize the Stage 1 anchor competition to try each raw candidate against each of the 7 possible tag roles, not only the Tag9/anchor role.**

Currently: for each raw candidate, the algorithm asks "if this candidate is Tag9 (offset 0,0), how many of the other 6 predicted positions have a nearby real candidate?" and keeps the best-scoring candidate as the Tag9 anchor.

Proposed: for each raw candidate **and** for each tag `t` in `REF_OFFSETS`, compute the implied anchor position (`candidate − offset[t]`), predict all 7 tag positions from that implied anchor, and score the match exactly as today. Keep the best-scoring `(candidate, tag-role)` pair overall. Everything downstream (Stage 2 refinement, recovery pass, quality gates, tolerances, diagnostics) is unchanged — only the search space of "what could this candidate represent" is widened from 1 role to 7.

For Cartridge 72, this would let any of the 6 genuine, clean candidates (e.g., the one matching Tag1) serve as the pivot, immediately yielding a 6/7 match (Tags 1,3,4,5,6,7) instead of the current 3/7 — Tag9 would then be correctly and honestly reported as `not_detected`, rather than corrupting the other tags' results too.

**Why this is the safest available correction (vs. alternatives considered and rejected):**
- *Widening `MATCH_TOL_PX`* — already evaluated and rejected in Stage 6 (destabilizes anchor selection, corrupts unrelated cartridges' measurements).
- *Widening Hough's radius range to catch the oversized Tag9 feature* — not evaluated in depth here since it doesn't fit the "simplest correction" bar and risks new false positives (per Stage 6's channel-wall findings); not recommended without a dedicated evaluation.
- *Adding a special case for "anchor candidate must itself pass the quality gate"* — would correctly flag Cartridge 72's false anchor as suspect, but doesn't by itself recover the other 6 tags; it only downgrades a wrong result to a "give up" result. Generalizing the anchor role search directly recovers the correct answer instead.

This recommendation is a **design proposal only** — it has not been implemented or tuned. Per your instruction, no production code has been modified as part of this investigation.

### 5.1 Regression-safety considerations for future implementation

- In every one of the other 78 cartridges, the true Tag9 candidate already achieves a 7/7 (maximum possible) score under the existing "candidate-as-Tag9" search. Generalizing to 7 roles cannot produce a *higher*-scoring match than 7/7, so no currently-correct cartridge can be pushed to a worse anchor purely by having more roles available — but a **tie-breaking rule** must be defined for cases where two different (candidate, role) pairs achieve the same match count (e.g., prefer the pairing that reproduces today's default Tag9-role behavior when tied, or prefer the pairing with the lowest total residual distance). This must be designed and validated — not assumed — before implementation.
- The proven cross-tag-contention safety margin (`2 × MATCH_TOL_PX < 1393.9px`, the minimum pairwise predicted-tag distance) is unaffected by this change, since it doesn't alter the tolerance or the predicted-position formula — it only changes which candidate is tried as the anchor point.
- A full validation pass (per the existing methodology: compile, import, regression across all 5 dataset groups, before/after comparison of every matched-tag measurement, PASS/FAIL, and position) would be required before this could be considered for implementation, exactly as was done for the Stage 6 recovery pass.

---

## 6. Cartridges 45, 48, 49, 50 — Out of Scope, Flagged for Separate Investigation

These 4 cartridges do not share Cartridge 72's failure mode and were not investigated further here, per the explicit scope restriction ("do not investigate unrelated failures"). Evidence gathered so far (summarized in §3) suggests a distinct, likely more severe problem specific to the 34-50/WB(2) dataset:
- Only 2–3 of 7 expected holes reach high ray-cast quality per cartridge (vs. Cartridge 72's 6/7).
- Best-effort geometric fits show implausible parameters (rotations up to 117°, scale factors 0.85–0.95) and large residuals (200–500px) even including low-quality candidates — inconsistent with a clean, simply-explained failure.
- A representative visual overview (Cartridge 49) shows a much more visually complex image (large chamber/reservoir feature, thick winding channels) than Cartridge 72's flat baseplate, suggesting image-content interference with Hough detection is a more likely contributing factor than a single anchor-precision gap.

**Recommendation:** open a separate, dedicated investigation for these 4 cartridges (and any others in the WB(2) batch showing similar symptoms) focused on image-content/candidate-generation robustness, not geometric modeling.

---

## 7. Summary of Deliverables

| Item | Status |
|---|---|
| Population-wide search (79 cartridges) | Complete — 5 flagged, 1 (Cartridge 72) confirmed matching the target failure mode |
| Cluster analysis with per-cartridge detail | Complete (§3, §4) |
| Translation/rotation/scale/affine model tests | Complete (§4.3) — quantified for both Cartridge 72 and a normal baseline |
| Residual plots | Generated — `cart72_model_residuals.png`, `cart72_rms_by_model.png` |
| Residual error quantification per model | Complete (§4.3 table) |
| Simplest explanatory model determination | Complete (§4.5): no distortion — single-point candidate-generation gap at Tag9 |
| Single recommended algorithmic correction | Complete (§5): generalize anchor-role search from Tag9-only to all 7 tags |
| Production code changes | **None** — design report only, as instructed |

Stopping here per your instruction. No implementation follows without further approval.
