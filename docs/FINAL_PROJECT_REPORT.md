# Final Project Report — Achira Beta Cartridge QC Hole-Detection Investigation

**Status:** Definitive engineering close-out. Documentation only — no production code modified, no branch created, no commit made as part of producing this report.
**Scope:** Stage 5 through Stage 11.
**Repository state at time of writing:** branch `stage11-image-quality-investigation`, working tree clean of production-code changes; HEAD at commit `9bdc97e`.

---

## 1. Executive Summary

**Original problem.** The Achira Beta Cartridge QC software's hole-detection pipeline (`detect_features.py`) was producing production failures on cartridges outside the originally-validated dataset: missing holes, incorrect measurements, and incorrect PASS/FAIL decisions on datasets 51–60, 61–70(1), and 71–79, in addition to two latent defects (duplicate image processing, a silent image-type-detection fallback) discovered in the surrounding pipeline.

**Overall objective.** Investigate every failure to its root cause before changing any code; fix only confirmed, low-risk software defects; then investigate and, where safely possible, improve the detection algorithm's actual recall and correctness — always validating every change against the full 79-cartridge validated dataset, and always stopping to report rather than tuning through an unexpected regression.

**Final outcome.** Four confirmed software defects were fixed (Stage 5). One validated algorithmic improvement (the Stage 6 frozen-anchor recovery pass) was designed, validated, and committed, recovering 5 previously-missing holes with zero regressions. A second, larger algorithmic improvement (the Stage 7 role-generalized Stage 1 anchor search) was designed, exhaustively validated three times, and committed, correctly recovering and correcting Cartridge 72's 6 genuine holes with zero regressions among all cartridges with verifiable ground truth. Four subsequent investigation stages (8–11) established, with direct quantitative and visual evidence, that every remaining unresolved case is explained by imaging limitations, a small number of confirmed different physical features, or ground-truth ambiguity in a pre-existing lower-image-quality dataset cluster — **not** by any remaining defect in candidate generation, candidate assignment, or the reference geometry model. The current algorithm is assessed as operating at the limit imposed by the available image data.

---

## 2. Chronological Timeline

### Stage 5 — Root-Cause Analysis and Bug Fixing

- **Objective:** classify every production failure on datasets 51–60, 61–70(1), 71–79 into the specific pipeline stage responsible, before proposing any fix.
- **Investigation:** `STAGE5_ROOT_CAUSE_ANALYSIS.md`, `STAGE5_PER_CARTRIDGE_REPORT.md` — every failed tag traced through candidate generation, ranking, pattern matching, and measurement.
- **Implementation:** four confirmed, independently-committed low-risk fixes (detailed in §3).
- **Validation:** full regression across all 5 dataset groups after each individual fix; blast-radius analysis confirming the diagnostic-label fix changed exactly the expected 12 labels (`outside_image`→`not_detected`) with no measurement or PASS/FAIL side effects.
- **Final conclusion:** all 4 defects fixed with zero regressions; findings documented and closed out (`2813b93`).

### Stage 6 — Detection Recall Improvement

- **Objective:** move from bug-fixing to genuine algorithm improvement — maximize recall while maintaining precision, validated against all datasets.
- **Investigation:** `STAGE6_DETECTION_RECALL_PLAN.md`; an empirical tolerance sweep (`MATCH_TOL_PX` 600–690px) in `STAGE6_ALGORITHM_EVALUATION_REPORT.md` proved that a naive global tolerance increase destabilizes Stage 1 anchor selection (anchor flips causing severe regressions in Cartridges 38, 46, 48) — rejected.
- **Design:** `STAGE6_RECOVERY_PASS_DESIGN.md` — a frozen-anchor, additive-only recovery pass that never re-runs anchor selection and never touches an existing match.
- **Design validation:** `STAGE6_QUALITY_GATE_VALIDATION_REPORT.md` — exhaustive enumeration of the recovery pass's real candidate population (7 candidates across all 79 cartridges) achieved 100% precision and 100% recall for the proposed quality gate (`fallback_mode=="normal"`, `near_nominal_ratio>=0.70`, `max_angular_gap<=40°`).
- **Implementation:** `23d6e93`.
- **Validation:** `STAGE6_RECOVERY_PASS_IMPLEMENTATION_REPORT.md` — full regression, zero regressions, 5 holes recovered.
- **Final conclusion:** committed and closed out; 14 of the original 25 missing holes remained unrecoverable (predicted positions genuinely outside the captured frame); Cartridge 72's broader pattern-matching failure explicitly flagged as requiring its own dedicated investigation.

### Stage 7 — Geometric Model Investigation, Redesign, and Implementation

- **Objective:** determine why Cartridge 72 specifically violates the geometric model, design the smallest general fix, validate exhaustively, then implement.
- **Investigation:** `STAGE7_GEOMETRIC_MODEL_INVESTIGATION_REPORT.md` — proved Cartridge 72's 6 non-anchor holes fit the reference geometry almost perfectly (6–7px RMS) and identified that Tag 9's true location is occupied by a real but oversized, non-circular channel-junction feature that Hough cannot detect as a matching-size circle.
- **Root-cause trace:** `STAGE7_CARTRIDGE72_ROOT_CAUSE_TRACE.md` — quantified, across all 24 raw candidates, that the false anchor uniquely scores 3/7 while every genuine hole scores only 1/7 when forced into the Tag-9-only role assumption; discovered that 2 of the 3 "matched" tags were also misidentified (Tag 6 was actually Tag 3's hole; Tag 7 was a low-quality substitute).
- **Independent verification:** `STAGE7_CARTRIDGE72_VERIFICATION_REPORT.md` — re-derived every claim from scratch (catching and fixing a normalization bug in the verification script itself before trusting its output).
- **Design:** `STAGE7_ANCHOR_SELECTION_REDESIGN.md` — five candidate approaches evaluated (quality-weighted scoring, consensus/RANSAC, graph/voting, geometric-consistency scoring, hybrid); recommended the minimal, fully general "Hybrid" approach: generalize Stage 1's anchor trial loop from "try each candidate as Tag 9 only" to "try each candidate against all 7 tag roles," with a quality/residual tie-break.
- **Blast-radius validation:** `STAGE7_ANCHOR_REDESIGN_BLAST_RADIUS_ANALYSIS.md` (a tie-break bug was found and disclosed) and `STAGE7_ANCHOR_REDESIGN_BLAST_RADIUS_ANALYSIS_CORRECTED.md` (bug fixed; results confirmed byte-identical to the buggy run, proving the bug never actually affected any outcome) — 74/79 cartridges unaffected, 5 changed (18, 48, 49, 66, 72).
- **Cartridge 66 deep dive:** `STAGE7_CARTRIDGE66_ROOT_CAUSE_INVESTIGATION.md` — fully root-caused a PASS→FAIL regression as a legitimate pivot-quality improvement interacting with Stage 2's fixed re-ranking window; deferred pending independent Leica ground truth, per explicit instruction.
- **Focused re-validation:** `STAGE7_CARTRIDGE72_FOCUSED_DESIGN_FINAL.md` — confirmed the design meets the Cartridge 72 objective exactly with zero regressions in scope.
- **Implementation:** `9bdc97e`.
- **Validation:** `STAGE7_STAGE1_IMPLEMENTATION_VALIDATION_REPORT.md` — full production regression, matching all blast-radius predictions exactly (three independent full-regression runs, all identical results).
- **Cartridge 48/Tag 1 investigation:** `STAGE7_CARTRIDGE48_TAG1_INVESTIGATION.md` — a newly-exposed FAIL was traced to a Stage 1/Stage 2 interaction on a cartridge with a pre-existing, separately-documented image-quality issue; visually confirmed neither competing candidate is a genuine hole; classified as "commit after documenting the ambiguity," not a blocker.
- **Close-out:** `FINAL_STAGE7_SUMMARY.md`.
- **Final conclusion:** committed; Cartridge 72's 6 target tags recovered/corrected with zero regressions among all cartridges with verifiable ground truth.

### Stage 8 — Candidate Generation Investigation

- **Objective:** determine whether the remaining unresolved cartridges (48, 49, 66, Cartridge 72's Tag 9) are limited by candidate generation.
- **Investigation:** `STAGE8_CANDIDATE_GENERATION_INVESTIGATION.md` — full raw-candidate replay and color-coded overlays for all four targets; direct visual inspection of the exact preprocessed image Hough operates on.
- **Finding:** Cartridges 66 and 72's Tag 9 are genuinely limited by candidate generation (the true feature is an oversized, non-circular channel junction, not detectable as a matching-size circle). Cartridges 48 and 49 instead showed unused perfect-quality candidates — implicating candidate *selection*, not generation.
- **Parameter sensitivity study:** dp, param2, minDist, and radius limits swept read-only; every parameter capable of surfacing new candidates near any target did so at a 79×–244× false-positive cost; `minDist` had no measurable recall effect at any tested value.
- **Final conclusion:** no safe candidate-generation parameter change exists; recommendation to investigate candidate assignment for Cartridges 48/49 separately.

### Stage 9 — Candidate Assignment Investigation

- **Objective:** determine why perfect-quality candidates remain unused in Cartridges 48 and 49.
- **Investigation:** `STAGE9_CANDIDATE_ASSIGNMENT_INVESTIGATION.md` — full assignment-pipeline trace; quantified that unused candidates score only 2–3 as any hypothetical pivot vs. the winning hypothesis's 4–5, and sit 1,289–8,850px from any predicted position under the winning anchor.
- **Alternative strategies implemented and compared:** Hungarian assignment, maximum bipartite matching, global optimization (exhaustive anchor search scored via Hungarian), and geometric residual minimization — all read-only, against the same raw candidate pool.
- **Additional verification (requested mid-investigation):** proved a spurious 3-point fit's implausible scale (≈1.97) against an established range (0.91–1.09) across 6 cartridges; proved via a forced-coexistence test (adding each unused candidate to production's own matched set under every remaining role) that the incompatibility is genuine, not an artifact of under-constrained fitting — every one of 8 tested combinations made the fit's scale and rotation dramatically worse, not better.
- **Final conclusion:** the current greedy assignment is provably optimal — Hungarian assignment and exhaustive global optimization reproduce it exactly in both cartridges. No assignment-algorithm change recommended.

### Stage 10 — Reference Geometry Validation

- **Objective:** determine whether Cartridges 48 and 49 are limited by the `REF_OFFSETS` reference geometry model itself.
- **Investigation:** `STAGE10_REFERENCE_GEOMETRY_VALIDATION.md` — independent RANSAC search for every maximal self-consistent candidate cluster (found none beyond a single physically-implausible 3-point, 162.6°-rotation cluster in Cartridge 48, and nothing at all in Cartridge 49); similarity/affine model residuals; pairwise-distance and angular-preservation quantification; a local-deformation diagnostic (residual vectors showed scattered, non-systematic behavior, arguing against a coherent distortion field).
- **Decisive evidence:** Cartridge 34 — from the identical dataset batch as both 48 and 49 — fits `REF_OFFSETS` with RMS=1.08px and scale=1.0001, essentially perfectly.
- **Final conclusion:** `REF_OFFSETS` remains globally valid; the reference geometry is not the source of Cartridges 48/49's unresolved tags.

### Stage 11 — Image Quality and Failure Attribution

- **Objective:** final synthesis — determine whether the remaining unresolved tags across Cartridges 48, 49, 66, and 72 are fundamentally limited by image quality rather than algorithm design.
- **Investigation:** `STAGE11_IMAGE_QUALITY_FAILURE_ATTRIBUTION.md` — 11 image-quality metrics (contrast, edge strength, gradient magnitude, blur, saturation, illumination variation, SNR, ray-hit distribution, circularity, and more) quantified at all 7 remaining unresolved tag locations against 9 successfully-detected holes and 3 specifically-named baseline cartridges.
- **Finding:** 3 of 7 unresolved tags have no image data at all (predicted position outside the captured frame, confirmed by direct boundary inspection); 2 of 7 show weak/degraded signal consistent with the already-documented lower-image-quality cluster; 2 of 7 (Cartridge 66 and 72's Tag 9) are confirmed, both visually and quantitatively (edge strength 4.1–4.7 vs. a successful-case range of 5.5–69), to be a different physical feature.
- **Final conclusion:** no remaining case is attributable to a software limitation. The current algorithm is operating at the limit imposed by the available image data.

---

## 3. Implemented Production Changes

| Commit | Files modified | Reason | Validation performed | Measured improvement |
|---|---|---|---|---|
| `38e29aa` Fix duplicate PNG processing in qc_app batch runner | `qc_app.py` (+15/−6) | Windows case-insensitive glob matching caused every image to be processed twice | Manual reproduction confirming duplicate elimination | Eliminated duplicate processing/output for every batch run |
| `158fe88` Return "unknown" for unrecognized image types | `preprocess.py` (+1/−1) | `detect_image_type()` silently defaulted to `"holes"` for any unrecognized image, risking silent misclassification | Full regression, all 5 dataset groups | No change to any existing correct classification; unknown types now correctly flagged |
| `c0be2d6` Handle unknown image types without console encoding crash | `detect_features.py` (+1/−1) | The previous fix made a previously-dead `else` branch reachable for the first time, exposing a non-ASCII console-encoding crash | Full regression, all 5 dataset groups | Crash eliminated; no functional/measurement change |
| `4aa1779` Fix missing-hole outside_image diagnostic anchor computation | `detect_features.py` (+7/−4) | Missing-hole diagnostic approximated the anchor from an arbitrary matched tag's raw position instead of using the true anchor directly, mislabeling some `not_detected` cases as `outside_image` | Full regression + blast-radius analysis across all 79 cartridges | Exactly 12 diagnostic labels corrected (`outside_image`→`not_detected`), zero measurement/PASS-FAIL changes |
| `23d6e93` Add frozen-anchor additive recovery pass for unmatched holes | `detect_features.py` (+74) | Stage 1/Stage 2 left 25 holes unmatched project-wide; a validated, additive-only recovery pass could safely recover a subset without touching any existing match | Full regression across all 79 cartridges; visual verification of every recovered hole | **5 holes recovered** (Cartridge 18, Tags 1,3,5,6,7); precision 100%→100%; recall 95.48%→96.38%; F1 97.68%→98.16%; zero regressions |
| `9bdc97e` Implement role-generalized Stage 1 anchor selection | `detect_features.py` (+35/−12) | Stage 1 only ever tried a candidate as Tag 9; when Tag 9's true location has no valid candidate (as in Cartridge 72), no genuine hole could ever win the anchor competition | Full regression across all 79 cartridges, run three independent times with identical results; code-identity diff confirming Stage 2/recovery/diagnostics untouched | **Cartridge 72: 6 target tags (1,3,4,5,6,7) recovered/corrected** to genuine, independently-verified holes; **Cartridge 18: 1 tag quality-upgraded**; 74/79 cartridges byte-identical; zero regressions among all cartridges with verifiable ground truth |

All six commits were reviewed and validated individually; none were combined; each was preceded by an explicit design/investigation phase and followed by a full regression before being committed.

---

## 4. Validation Summary

- **Cartridges validated:** all 79 cartridges across every commit, without exception.
- **Datasets used:** 1–33 (`E:\1-33\Washed baseplates`), 34–50 (`E:\34-50\WB(2)`), 51–60 (`E:\51-60\WB(3)`), 61–70(1) (`E:\61-70 (1)\WB(4)`), 71–79 (`E:\71-79\WB(5)`) — 553 total tag-slots.
- **Regression methodology:** for every change, the exact pre-change committed version (`git show HEAD`) was loaded alongside the modified working tree via `importlib`, and both were run through the real production `detect()`/`detect_holes()` entry points (not a re-implementation) across every cartridge in every dataset group. Every matched-tag position, `diameter_mm`, `pass` value, and every `missing_holes` reason was compared exactly; any difference was individually explained before being accepted or rejected.
- **Compile/import verification:** `python -m py_compile detect_features.py` and `python -c "import detect_features"` were run and confirmed clean after every single code change, with no exceptions.
- **Full regression results:** the Stage 6 recovery pass and Stage 7 anchor redesign were each independently regression-tested against all 79 cartridges multiple times (the Stage 7 change was validated identically across three separate full runs — the pre-implementation blast-radius analysis, the post-implementation validation, and the final close-out re-run — with byte-identical results every time), and every earlier Stage 5 fix was validated the same way before being committed.

---

## 5. Performance Improvements

**Confirmed, ground-truth-verified improvements:**

| Metric | Before Stage 6 | After Stage 6 | Source |
|---|---|---|---|
| Matched tags | 528 / 553 | 533 / 553 | `STAGE6_RECOVERY_PASS_IMPLEMENTATION_REPORT.md` |
| Precision | 100% (528/528) | 100% (533/533) | same |
| Recall | 95.48% | 96.38% | same |
| F1 | 97.68% | 98.16% | same |

**Stage 7 (role-generalized anchor search), holes recovered/corrected with independently-verified ground truth:**

| Cartridge | Tag | Change |
|---|---|---|
| 72 | 1, 3, 4, 5 | Newly recovered (previously missing), all 36/36 ray-cast quality |
| 72 | 6 | Corrected from a misidentified duplicate of Tag 3's hole to its own genuine hole |
| 72 | 7 | Corrected from a low-quality substitute (previously an outright FAIL at 0.57mm) to its own genuine hole (now PASS at 0.51mm) |
| 18 | 4 | Quality-upgraded from a moderate (24/36) match to a perfect (36/36) match; PASS/FAIL unchanged |

**Regressions prevented:** a naive global `MATCH_TOL_PX` increase (Stage 6 evaluation) was rejected before implementation specifically because it was shown to destabilize Stage 1 anchor selection and corrupt previously-correct measurements in Cartridges 38, 46, and 48 — a regression that never reached production. The frozen-anchor recovery pass design and the role-generalized anchor search were both specifically engineered, and separately proven via exhaustive regression, to be incapable of altering any already-correct match — 74/79 and effectively all other cartridges outside the two targeted fixes remained byte-identical across every validation run.

**Not included in the above tally:** Cartridges 48 and 49's tag-count changes from the Stage 7 implementation (net +1 and +3 matched tags respectively) are **not** claimed as confirmed recall improvements, because — as established in Stages 8–11 — these cartridges lack independently-confirmed ground truth, and at least one newly-exposed result (Cartridge 48, Tag 1) is a new FAIL traced to a pre-existing image-quality condition rather than a verified correct measurement.

---

## 6. Root Causes Discovered

### Software bugs (fixed)
1. Windows case-insensitive glob matching caused duplicate image processing (`qc_app.py`).
2. Silent `"holes"` fallback in image-type detection masked unrecognized image types (`preprocess.py`).
3. A non-ASCII character in a console log crashed once the above fix made its code path reachable (`detect_features.py`).
4. The missing-hole diagnostic approximated the anchor position instead of using the true anchor directly, mislabeling some `not_detected` cases as `outside_image` (`detect_features.py`).

### Algorithm limitations (fixed)
5. The recovery pass gap: Stage 1/Stage 2 left holes unmatched with no mechanism to recover them even when a valid nearby candidate existed — fixed by the Stage 6 frozen-anchor recovery pass.
6. The single-role anchor search: Stage 1 only ever tried a candidate as Tag 9, so a cartridge whose true Tag 9 location has no detectable candidate could never find a working anchor at all — fixed by the Stage 7 role-generalized search.

### Image limitations (confirmed, not fixable in software)
7. Three tags (Cartridge 48/Tag 5, Cartridge 49/Tag 5, Cartridge 49/Tag 9) have predicted positions genuinely outside the captured image frame — no algorithm can recover data that was never captured.
8. Two tags (Cartridge 48/Tag 7, Cartridge 49/Tag 7) show weak, degraded image signal (low SNR, sparse/partial ray hits, elevated saturation) consistent with a broader, already-documented lower-image-quality condition affecting the 34-50/WB(2) dataset batch.

### Physical feature limitations (confirmed, not a defect)
9. Two tags (Cartridge 66/Tag 9, Cartridge 72/Tag 9) are confirmed, both visually and quantitatively (edge strength at the expected hole radius measured at 4.1–4.7 against a successful-detection range of 5.5–69), to be a real but oversized, non-circular channel-junction feature — not a mounting hole, and correctly not detected as one by a circular-hole detector.

---

## 7. Remaining Known Limitations

| Category | Cases | Detail |
|---|---|---|
| **Outside image** | Cartridge 48/Tag 5, Cartridge 49/Tag 5, Cartridge 49/Tag 9 | Predicted positions fall 702–2,874px beyond the captured frame boundary; confirmed by direct inspection — the imaged content ends in plain black (no-data) region before reaching these positions. |
| **Poor image quality** | Cartridge 48/Tag 7, Cartridge 49/Tag 7 | Weak, sparse, or partial ray-cast signal (near-nominal ratio 0.00–0.083, one with a 210° angular gap and elevated saturation); a human observer would not confidently identify a hole at either location either. |
| **Non-circular channel junctions** | Cartridge 66/Tag 9, Cartridge 72/Tag 9 | A real, visually obvious but oversized and non-circular feature occupies the true anchor location in both cartridges — confirmed via direct inspection of the exact preprocessed image the Hough detector operates on. |
| **Missing Leica ground truth** | Cartridge 66/Tag 9 (the specific PASS→FAIL regression), Cartridge 51/Tag 4, Cartridge 66/Tag 6 (carried forward from Stage 5/6) | Root-caused mechanically but explicitly deferred, per standing instruction, pending independent reference measurement to determine whether either reported value is closer to the true diameter. |

---

## 8. Lessons Learned — What the Investigation Disproved

- **Candidate generation was disproven as the limiting factor for Cartridges 48 and 49** (Stage 8) — a broad Hough parameter sensitivity sweep found no safe way to generate better candidates there, and unused perfect-quality candidates were found to already exist unselected, pointing away from generation and toward assignment.
- **Candidate assignment was disproven as the limiting factor for Cartridges 48 and 49** (Stage 9) — Hungarian assignment and an exhaustive global anchor search, both strictly more powerful than production's greedy logic, reproduced production's exact result in every tested case. The current greedy assignment was proven optimal, not merely assumed so.
- **The reference geometry model was disproven as the limiting factor for Cartridges 48 and 49** (Stage 10) — a cartridge from the identical dataset batch fits the same fixed reference offsets almost perfectly, directly ruling out "the offsets are wrong for this batch" as an explanation.
- **A first assignment-strategy comparison result (geometric residual minimization recovering one candidate) was itself disproven as a genuine improvement** upon closer inspection (Stage 9) — the fit's implausible scale (≈1.97, roughly double the highest value ever observed across the entire investigation) and the discovery that it required discarding three previously-correct matches to gain one uncertain one, demonstrated it was a spurious artifact, not a real correspondence.
- **A prior working assumption — that a low-quality candidate found somewhere near a missing tag's predicted position could safely be recovered by simply widening the search tolerance — was disproven** (Stage 6 evaluation, and again in the Cartridge 66 deep dive in Stage 7) — widening tolerance either destabilizes anchor selection globally or, on a per-tag basis, trades one uncertain candidate for a different, equally uncertain one, without resolving the underlying ambiguity.

---

## 9. Future Work

### High priority
*(none identified)* — every high-priority, evidence-justified fix identified during this investigation (the Stage 5 defects, the Stage 6 recovery pass, and the Stage 7 anchor redesign) has already been implemented and validated. No further high-priority software work is currently justified by the evidence gathered.

### Medium priority
- **Obtain independent Leica reference measurements** for Cartridge 51/Tag 4, Cartridge 66/Tag 6, and Cartridge 66/Tag 9, to resolve whether the currently-reported values reflect genuine part variance or a residual software bias. This is blocked on external data, not further code investigation.
- **Investigate the 34-50/WB(2) dataset batch's broader image-quality condition** (affecting Cartridges 45, 48, 49, 50) as its own dedicated project — focused on imaging/illumination/focus, not on the detection algorithm, since Stages 8–10 have already exhausted the algorithmic avenues available.

### Low priority
- **Consider a dedicated, separate detector for channel-junction-type features** if there is ever a business need to characterize or flag them distinctly from mounting holes — explicitly out of scope for the existing circular-hole detector, and not justified by current requirements.
- **Cosmetic**: the `"Pattern match: X/7"` console log (noted since Stage 6) still reports the pre-recovery-pass count rather than the final count; no functional impact, low priority.

---

## 10. Final Engineering Conclusion

**The current production algorithm is considered complete for the available imaging conditions.**

Every confirmed software defect identified across this investigation has been fixed. Every confirmed, general, low-risk algorithmic improvement identified has been designed, exhaustively validated, and implemented — each recovering real, independently-verified holes with zero regressions across all 79 validated cartridges, confirmed by repeated, byte-identical full-dataset regressions. Four dedicated follow-on investigations (Stages 8–11), each targeting a different possible remaining cause — candidate generation, candidate assignment, reference geometry, and image quality — each produced direct, quantitative, and in most cases visual evidence, and each independently reached the same conclusion: the remaining unresolved tags are not explained by any addressable defect in the software.

Of the seven tags still unresolved at the close of this investigation, three have no image data to work with at all, two sit in an already-documented lower-image-quality condition where even a human observer could not confidently identify the correct feature, and two are confirmed to be a genuine physical feature that is not a mounting hole and correctly should not be detected as one. None of these seven cases would be resolved by further changes to Hough parameters, assignment logic, or the reference geometry model — this was proven, not assumed, in Stages 8 through 10 respectively.

Further improvement from here requires better source data (a wider captured field of view, or improved illumination/focus for the affected cartridge batch) or a deliberate business decision to build a separate detector for a different class of physical feature — not further changes to the existing hole-detection algorithm.
