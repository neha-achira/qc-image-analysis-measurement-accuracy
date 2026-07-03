# Stage 3 — Hough Detection: Investigation Summary & Implementation Plan

**Status: RESOLVED — no implementation required.** A focused visual investigation (see §10) directly confirmed that Hough correctly detects the true hole in all three target cases and Stage 2 already selects it correctly. No production code was modified and no parameters were tuned at any point during this investigation.
**Scope:** Strictly limited to three confirmed cases — Cartridge 2/Tag3, Cartridge 6/Tag5, Cartridge 15/Tag1 (Holes image type, `detect_holes()` Hough-detection stage in `detect_features.py`).
**Prerequisite state:** Stage 2 (candidate selection) is implemented, committed (`ba61359`, branch `stage2-candidate-selection`), and documented in `docs/STAGE2_CANDIDATE_SELECTION_REPORT.md`. Stage 2 logic was not modified as part of Stage 3.

---

## 0. Note on requested prior documents

Before writing this plan I searched the repository and the investigation scratchpad for `docs/MASTER_PLAN.md` and `docs/PROGRESS.md`. **Neither file exists anywhere in the project.** Only `docs/STAGE2_CANDIDATE_SELECTION_REPORT.md` exists in `docs/`. I did find and re-read the prior Hough-specific investigation scripts and their saved outputs in the scratchpad (`category3_rootcause.csv`, `rootcause_category3.py`, `check_hough_circle.py`, `inspect_hough_candidates.py`), and re-ran the two that had no saved output, to base this plan on current, verified evidence rather than assumption. If `MASTER_PLAN.md`/`PROGRESS.md` were expected to exist, they were either never created or lost outside this session — flagging this now rather than silently proceeding as if I'd read them.

---

## 1. Summary of Confirmed Evidence Collected So Far

From the Stage 2 investigation (`docs/STAGE2_CANDIDATE_SELECTION_REPORT.md`, §4 and §12): a quantitative risk assessment found 17 tag assignments where a different in-tolerance candidate outranked production's nearest-distance pick. Five of these were `total_failure → normal` fallback-tier corrections: Cartridge 2/Tag3, 2/Tag4, 6/Tag5, 15/Tag1, 31/Tag1. Two (2/Tag4, 31/Tag1) were independently confirmed via raw-candidate replay to be genuine candidate-selection failures — Hough detected a real candidate on the true hole, but the original nearest-distance-only matching discarded it. **The remaining three — 2/Tag3, 6/Tag5, 15/Tag1 — were explicitly flagged in the Stage 2 report as "unsupported by existing evidence"**: they share the same statistical signature (`total_failure` fallback replaced by a `normal` 36/36 result) but had not yet been individually visually or otherwise confirmed. Closing that gap was Stage 3's objective; §10 records the result — the gap is now closed and no defect was found.

New evidence gathered for this plan (read-only, via existing scratchpad scripts, re-run against current — Stage-2-active — production code):

**`inspect_hough_candidates.py`** replays the exact, unmodified Hough call and samples 72 points around each raw candidate's own `(cx, cy, r)` perimeter, reporting what fraction fall below the same `THRESHOLD=90` intensity cutoff `_subpixel_diameter` already uses (`wall_frac`) — an independent check of whether Hough's own circle actually corresponds to a real dark boundary:

| Case | Selected candidate (Stage 2) | Hough's own radius | `wall_frac` at Hough's (cx,cy,r) |
|---|---|---|---|
| 2/Tag3 | (1088, 3332) | r=96 | **11%** |
| 6/Tag5 | (2456, 5676) | r=96 | **3%** |
| 15/Tag1 | (548, 476) | r=92 | **6%** |
| 2/Tag4 (already-confirmed good fix) | (2512, 1024) | r=104 | 83% |
| 31/Tag1 (already-confirmed good fix) | (596, 500) | r=100 | 43% |

All three Stage 3 target cases show a **low** `wall_frac` (3–11%) at Hough's own best-fit radius, sharply lower than the two already-confirmed-good candidate-selection fixes (43–83%). This is the strongest direct evidence that something is different about these three candidates.

**`stage3_ray_uniformity.py`** (new, written for this plan) extracts the 36 individual ray-hit radii `_subpixel_diameter` already computes for the currently-selected candidate at each tag, and reports their spread — a well-centered circle should show low variance (every ray hits the wall at roughly the same radius); a candidate whose center is offset from the true hole's centroid would show radius varying with angle even if every individual ray still lands inside the accepted near-nominal window:

| Case | n_hit | mean radius (px) | std (px) | range (px) |
|---|---|---|---|---|
| 2/Tag3 | 36/36 | 105.3 | **7.9** | **35.0** |
| 6/Tag5 | 36/36 | 103.6 | 4.2 | 15.0 |
| 15/Tag1 | 36/36 | 100.9 | 4.5 | 18.0 |
| 2/Tag4 (confirmed good) | 36/36 | 99.2 | 6.5 | 24.0 |
| 31/Tag1 (confirmed good) | 36/36 | 104.3 | 7.2 | 23.0 |
| 2/Tag9 (well-behaved reference, unrelated hole) | 36/36 | 99.5 | 4.5 | 16.0 |

At the time this table was produced, it split the three target cases into two statistically distinct groups:
- **6/Tag5 and 15/Tag1** showed ray-radius uniformity (std 4.2–4.5, range 15–18px) statistically indistinguishable from the well-behaved reference hole (std 4.5, range 16px), and notably *better* than the two already-confirmed-good candidate-selection fixes — suggestive (not conclusive) that the ray-cast was finding a real, cleanly circular boundary at these two candidates' centers.
- **2/Tag3** showed a visibly higher spread (std 7.9, range 35px) than every other case in this table, including the reference hole — at the time, this was flagged as the one case where the statistics alone left open the possibility that the candidate's center was measurably off from the true hole's centroid.

**This concern was directly resolved by the Phase 0 visual investigation (§10): 2/Tag3's selected candidate is visually confirmed to sit on a genuine through-hole**, with a clean, continuous 36/36 ray-hit ring on a real dark boundary. The elevated ray-radius variance shown here did not, in the end, indicate a mis-centered candidate — most likely it reflects a slightly less perfectly circular edge at that specific hole, which is not a defect. This is recorded as an example of why this investigation required direct visual confirmation rather than concluding from statistics alone, exactly as Stage 2's own history warranted (§7 below).

---

## 2. Exact Failure Mechanism

The mechanism is **not uniform across the three cases** — the evidence above does not support treating them as one problem:

- **Common element:** in all three cases, `cv2.HoughCircles` converges on a `(cx, cy, r)` estimate whose own radius does not correspond to a real dark-wall boundary in the image (`wall_frac` 3–11%). This is consistent with these three hole locations having a weak, low-contrast, or partially-obscured edge signal at the resolution/parameters Hough runs at (4x downsampled, `param2=25` accumulator threshold) — exactly the condition that caused these candidates to report `total_failure` fallback before Stage 2 existed to pick a fallback candidate at all.
- **However**, `_subpixel_diameter()` does not use Hough's radius for measurement — it always searches a fixed window (`0.65×`–`1.30×` of the constant `FIXED_R_FULL=100px`) around the candidate's `(cx, cy)` only. So a bad Hough radius guess does not, by itself, corrupt the final measurement — only a bad `(cx, cy)` center would.
- For **6/Tag5 and 15/Tag1**, the ray-cast's own internal consistency (§1, table 2) gives no evidence that the center is wrong — the measurement these two produce may already be accurate, and the "failure" may be fully and correctly resolved by Stage 2 already, with Hough's poor radius estimate being a cosmetic/internal artifact with no downstream effect.
- For **2/Tag3**, the elevated ray-radius variance is evidence the candidate's center may be measurably offset from the true hole centroid (or the true boundary at that location is genuinely non-circular/irregular), which — unlike the other two — could still be producing a biased diameter measurement even after Stage 2's fix.

**Conclusion at the time this analysis was performed: Stage 3 could not assume all three cases needed the same treatment, or needed any code change at all, until each was independently visually confirmed** — exactly the discipline that governed Stage 2 (§5–§6 of the Stage 2 report). Proceeding straight to a Hough-parameter change based on the statistical signature alone would have repeated the mistake Stage 2 explicitly avoided. **This is exactly what the Phase 0 visual review (§10) then did — see that section for the final, resolved answer: no code change was needed for any of the three cases.**

---

## 3. Current Hough Pipeline

As implemented in `detect_holes()` (unchanged by Stage 2), reproduced verbatim from source (not from memory) via the read-only replay scripts:

1. **Crop to active area.** Column/row mean-intensity thresholding (`> 20`) finds the extent of real image content; the image is cropped to that bounding box plus a 50px margin.
2. **4x downsample.** `cv2.resize(active, (w//4, h//4), interpolation=cv2.INTER_AREA)`.
3. **CLAHE.** `cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))` applied to the downsampled grayscale image.
4. **Gaussian blur.** `cv2.GaussianBlur(clahe_output, (7,7), 2.0)`.
5. **`cv2.HoughCircles`** on the blurred, downsampled image:
   - `method=cv2.HOUGH_GRADIENT, dp=1.2`
   - `minDist = int(nominal_r_ds * 2.8)` where `nominal_r_ds = FIXED_R_FULL(100) / 4 = 25.0`
   - `param1=80, param2=25`
   - `minRadius = max(3, int(nominal_r_ds * 0.78))`, `maxRadius = max(minRadius+2, int(nominal_r_ds * 1.22))`
6. **Candidate generation.** Detected `(cx, cy, r)` triples are scaled back to full resolution (`× 4`) and become the raw candidate list — typically 25–68 candidates per cartridge image across the dataset observed in this investigation.
7. Each raw candidate is then passed to `_subpixel_diameter()` for ray-cast measurement (Hough's radius is not used further), then to Stage 1 anchor selection and Stage 2 ranking (both already implemented, out of scope for Stage 3).

---

## 4. Why the Three Cases Showed `total_failure` Before Stage 2

See §2. In short: Hough's circle-fit confidence is measurably weaker at these three image locations (low `wall_frac` at its own best-fit radius in all three), most plausibly due to a locally weak or ambiguous intensity edge at the downsampled/blurred resolution Hough operates at — which is why these candidates originally reported `total_failure` fallback before Stage 2 existed to select a better in-tolerance candidate. Whether this weak Hough radius fit *also* meant the candidate's `(cx, cy)` center was inaccurate — the only thing that would actually bias the final measurement — was an open question at this point in the investigation (statistics alone left 2/Tag3 ambiguous). **§10 resolves this with direct visual evidence: the center is correct in all three cases, including 2/Tag3.** No Hough detection defect exists for any of the three cases.

---

## 5. Everything Already Ruled Out

- **Candidate selection (Stage 2).** Already implemented and regression-verified; for all three target cases, Stage 2 is already selecting the single best-ranked candidate among everything Hough generated. If a defect remains, it is not a selection-among-existing-candidates problem — Stage 2 cannot select a candidate Hough never generated.
- **Ray-casting logic (`_subpixel_diameter`).** Regression-verified via instrumentation (0 diffs) long before Stage 2 existed; its behavior is identical regardless of `debug_context`. Not a suspect.
- **Center refinement (`_refine_center`).** Proven, via a controlled bypass experiment, to be a pure no-op on every measured value in the dataset (§2.5, Stage 2 report). Not a suspect.
- **Calibration.** Affects only the mm/px scale factor applied after pixel-level detection; has no bearing on which pixel candidates Hough generates or which one is selected. Not a suspect.
- **Cross-tag candidate contention.** Proven impossible by construction (minimum pairwise predicted-tag distance 1393.9px > `2 × MATCH_TOL_PX` = 1200px). Not a suspect for these three cases either.

---

## 6. Possible Improvement Approaches

| # | Approach | Advantages | Disadvantages | Regression risk | Implementation complexity |
|---|---|---|---|---|---|
| A | Lower `param2` (Hough accumulator threshold) globally | Might surface a better-fit candidate near the true hole in weak-edge cases | Changes candidate generation for **all 33 cartridges**, not just the 3 targets; more candidates everywhere means Stage 1/Stage 2 must re-prove correctness dataset-wide | **High** — global parameter change, exact repeat of the Stage 2 §7.1/§7.2 mistake pattern (changing shared logic to fix 3 cases) | Low code change, very high validation burden |
| B | Change `dp`, `minDist`, or downsample factor globally | Same rationale as A | Same as A — global, non-additive | **High** | Low code change, very high validation burden |
| C | **Additive second-pass Hough** (e.g., re-run `HoughCircles` with a lower `param2` only as a *supplementary* candidate source, unioned with the existing candidate list; existing candidates and their identity are never removed or altered) | Existing behavior for all currently-working cases is provably unchanged (nothing is removed, only added); Stage 2's already-validated ranking logic handles selection among the enlarged pool with no further change | More candidates to rank (small compute cost); needs care that duplicate/near-duplicate candidates don't confuse Stage 2 (already tolerant, since it ranks by fallback/n_hit/near/distance, not candidate count) | **Low** — strictly additive; a candidate that didn't exist before can only ever be *chosen* if it strictly outranks the current pick (Stage 2's existing monotonicity guarantee) | Medium — new candidate-generation code path, but reuses Stage 2 ranking unchanged |
| D | Independent center-only local search (analogous to `_refine_center` but used as an input to re-cast rays, not cosmetic) | Could improve center precision without touching Hough parameters at all | `_refine_center` already exists and was proven to be a no-op *by design* (it runs after measurement); reusing/extending it for a new purpose risks conflating two already-settled findings and re-opening a closed investigation | Medium — new logic, new interaction with an existing proven-inert function | Medium-high |
| E | Do nothing algorithmic; treat ray-cast self-consistency as sufficient evidence where it already indicates a clean, uniform boundary (6/Tag5, 15/Tag1), and investigate only 2/Tag3 | Zero regression risk for 2/5 of the target scope; matches the actual evidence (§1–§2) rather than the assumption that all three need the same fix | Does not by itself resolve 2/Tag3; requires a visual review step before any conclusion | **None** for 6/Tag5, 15/Tag1 (no code change); TBD for 2/Tag3 pending review | None (documentation/investigation only) |
| F | Visual review of all 3 candidates before any algorithmic change | Directly answers "is this still broken at all after Stage 2" with the same evidentiary standard used successfully in Stage 2 (§5–§6 of that report); may show 0, 1, 2, or 3 of these cases need any further work | Does not itself improve anything; investigation-only | None | Low (reuses the exact crop-generation approach from Stage 2) |

---

## 7. Recommended Implementation Strategy

**Recommend F, then (conditionally) E and C — in that order — and explicitly reject A/B/D at this time.**

**Update: Approach F (Phase 0, visual review) has since been executed — see §10. It resolved all three cases with no defect found, so Phases 1/2 below were not required.**

Rationale: Stage 2's own history (§7.1–§7.2 of the Stage 2 report) is a direct precedent for what goes wrong when a fix is designed from aggregate statistics before individual visual confirmation — both early `_score_anchor` rewrites caused large unintended regressions and had to be discarded. The evidence in §1 already shows the three target cases are **not homogeneous** (6/Tag5 and 15/Tag1 look measurement-clean; 2/Tag3 does not) — proceeding to any Hough parameter change now, before individually confirming which (if any) of the three are still actually wrong, risks solving a problem that may already be solved by Stage 2 for 2 of the 3 cases, while applying a global, high-regression-risk change (A/B) to fix what evidence suggests may be a single-case, possibly non-Hough issue (2/Tag3).

If Phase 0 (visual review) confirms a real remaining defect for one or more cases, **Approach C (additive second-pass Hough)** is recommended over A/B because it is the only option that mirrors the architectural lesson already learned in Stage 2: preserve existing behavior exactly, add new capability alongside it, and let the already-validated ranking/monotonicity logic decide whether the new candidate is actually better — never modify shared logic in place to fix a small number of cases.

---

## 8. Phased Implementation Plan

**Phase 0 has been executed — see §10 for results. Phases 1 and 2 below were not required, since Phase 0 found no remaining defect in any of the three cases. They are retained here unmodified as the contingency plan that would have applied had Phase 0 found otherwise.**

### Phase 0 — Visual review of the 3 target cases (investigation only, no code change)
- **Expected behavior:** N/A — no code runs differently; this phase produces evidence only.
- **Method:** Generate comparison crops for 2/Tag3, 6/Tag5, 15/Tag1 using the exact methodology from the Stage 2 report §5 (predicted position marker, currently-selected candidate circle + ray-hit dots, on real image content), read-only, reusing `_subpixel_diameter()`/`detect_holes()` unmodified.
- **Regression tests:** None (no code change).
- **Acceptance criteria:** For each of the 3 cases, a documented classification of "through-hole" (Stage 2's current measurement is visually confirmed correct — no further action needed for this case) or "background/incorrect" (a real defect remains — proceed to Phase 1 for this case only) or "inconclusive."

### Phase 1 — Additive second-pass Hough candidate generation (only for cases Phase 0 confirms still broken; not triggered — no case required it)
- **Expected behavior:** The existing Hough call and its candidate list are completely unchanged. A second `cv2.HoughCircles` call, using a lower `param2` (exact value not yet chosen — no parameter is to be tuned as part of this document), runs on the same preprocessed image and its results are **unioned** with the existing candidate list before Stage 1/Stage 2 run. No existing candidate is removed, reordered, or modified.
- **Regression tests:** Full 33-cartridge regression against the current Stage 2 baseline (commit `ba61359`). Expected: zero differences for every cartridge/tag *except* the specific case(s) Phase 0 confirmed as defective — because Stage 2's monotonicity guarantee (a new candidate is only ever chosen if it strictly outranks the current pick) means an added candidate can only change an outcome by being strictly better, never worse.
- **Acceptance criteria:** (a) zero unexpected changes outside the Phase-0-confirmed defective case(s); (b) for each confirmed defective case, the newly-available candidate is selected by Stage 2's existing ranking and is visually confirmed (same methodology as Phase 0) to sit on the true hole boundary; (c) `py_compile` + import + full regression all pass before this phase is considered complete.

### Phase 2 — Final validation
- **Expected behavior:** Production behavior matches Phase 1 exactly; this phase only re-confirms and documents.
- **Regression tests:** Repeat the full 33-cartridge regression once more from a clean checkout to confirm reproducibility.
- **Acceptance criteria:** A validation report (mirroring the Stage 2 report's §12 structure) confirming all in-scope cases are resolved or explicitly documented as out of reach with a stated reason, and that no out-of-scope measurement changed.

---

## 9. Success Criteria for Stage 3

1. Each of the three target cases (2/Tag3, 6/Tag5, 15/Tag1) has an individually-documented visual determination (through-hole / background / inconclusive) — no conclusion is drawn from ray statistics alone, matching the standard already applied in Stage 2.
2. Any code change is strictly additive to Hough candidate generation (Approach C) — no existing Hough parameter is modified in place, and no case outside the confirmed-defective set changes in the full 33-cartridge regression.
3. No new thresholds are introduced without being derived from, or justified against, already-computed data (matching the Stage 2 constraint that governed the ranking design).
4. `py_compile`, import verification, and the full 33-cartridge regression all pass after any implementation step, with every difference from baseline individually accounted for (as in Stage 2 §10–§11) — any unexpected change halts implementation immediately, exactly as it did during Stage 2's coupling-bug discovery.
5. If Phase 0 shows one or more of the three cases is already correctly resolved by Stage 2 alone, Stage 3 implementation work is scoped down accordingly rather than applied uniformly to all three — the plan explicitly permits "no code change needed" as a valid outcome for any subset of the three cases. **Outcome (§10): Phase 0 found this to be true for all three cases — no code change was needed for any of them, and Stage 3 concluded with zero implementation.**

---

## 10. Resolution — Phase 0 Visual Review Results and Revised Conclusion

Phase 0 was executed as a focused, read-only visual investigation (no production code modified) for exactly the three in-scope cases. For each, three images were generated and inspected: a full-cartridge overview showing every raw Hough candidate (as circles) plus the predicted position (magenta ×) and the Stage-2-selected candidate (highlighted), and a zoomed crop of the selected candidate with its 36-ray hit overlay.

**Finding, identical for all three cases:**
- The Stage-2-selected candidate sits on a genuine, clearly-bordered through-hole — a clean, continuous 36/36 ray-hit ring on a real dark boundary, directly visible in the image.
- The predicted position (from the anchor/`REF_OFFSETS` geometry) falls well away from any hole (~400–460px), on plain PMMA texture — but this is comfortably inside `MATCH_TOL_PX=600px`, so it never caused an incorrect selection.
- No other raw Hough candidate is closer to the true hole than the one already selected. Hough's own candidate list already contained the correct detection in every case.

**Answering §9's acceptance criteria directly, per case:**

| Case | Hough center wrong? | Hough radius wrong? | Candidate missing? | Candidate present but rejected? | Real problem elsewhere? | Classification |
|---|---|---|---|---|---|---|
| 2/Tag3 | No | Hough's own radius estimate is imprecise, but irrelevant — `_subpixel_diameter` measures independently of it | No | No — Stage 2 already selects it | Predicted position offset (~460px), within tolerance | **Through-hole — already correctly resolved** |
| 6/Tag5 | No | Same as above | No | No | Predicted position offset (~436px), within tolerance | **Through-hole — already correctly resolved** |
| 15/Tag1 | No | Same as above | No | No | Predicted position offset (~454px), within tolerance | **Through-hole — already correctly resolved** |

**Revised conclusion: Stage 3 is complete without any implementation.** The premise motivating Stage 3 — that these three cases were "unsupported by existing evidence" (Stage 2 report, §12–§13) — meant no one had individually confirmed them, not that a defect was known to exist. That evidentiary gap is now closed, and the finding is negative: no Hough candidate-generation defect exists in any of the three cases. Implementing any of Approaches A–D (§6) would modify working code to fix a problem that does not exist, which is exactly the failure pattern this document's own §7 warned against.

### Broader sweep: other Hough candidate-absence findings (explicitly out of scope, not acted on)

Per this reassessment's broader instruction to search the full regression for *any* remaining Hough-caused failures, two other candidate-absence situations were found in the full 33-cartridge regression log. Both are **pre-existing** (confirmed present, byte-for-byte, in the regression captured before Stage 2 was ever implemented) and **outside Stage 3's stated scope** ("Everything else is out of scope"). They are recorded here for visibility only — no investigation, design, or code change has been performed for either, consistent with Stage 3's scope boundary:

1. **Cartridge 18, Holes: Tags 6 and 7 report `not detected`** (no Hough candidate within `MATCH_TOL_PX` at all), and **Tags 1, 3, 5 report `outside image bounds`** — only 2 of 7 tags match for this cartridge. This is structurally different from the three Stage 3 cases (which each had 6–7 tags matching normally): it looks like a broader anchor- or pattern-matching-level anomaly affecting most of one cartridge's tags simultaneously, not a targeted single-candidate Hough defect. Confirmed pre-existing via `regression_post_revert2_output.txt` (captured before any Stage 2/3 work).
2. **Cartridge 9, Mixing: MX02 reports `no candidate within 800px... using reference position`**, with only 2 raw Hough candidates detected for the whole Mixing image. This is a genuine Hough candidate-absence case, but in `detect_mixing()` — a function never touched by Stage 1, Stage 2, or this Stage 3 investigation.

Neither finding changes the conclusion above for the three in-scope cases. If either is to be investigated, it should be scoped as its own separate stage, since both appear structurally distinct from the candidate-selection/generation mechanism Stage 2 and Stage 3 have addressed.

---

## 11. Explicit Constraints Observed in Producing This Document

- No production code was modified.
- No Hough parameters were tuned.
- No new thresholds were introduced.
- Nothing was implemented. This document contains a plan, the evidence gathered, and the resulting resolution.
