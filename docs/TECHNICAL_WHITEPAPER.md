# Achira Beta Cartridge QC: Hole-Detection Pipeline
## A Technical Whitepaper on Root-Cause Investigation, Algorithm Redesign, and Architectural Assessment

**Classification:** Internal engineering documentation
**Audience:** Senior software engineers, computer vision engineers, technical management
**Scope:** Investigation Stage 2 through Stage 18
**Status:** Documentation only. No production code was modified, and no commit was created, in the preparation of this document.

---

## 1. Executive Summary

The Achira Beta Cartridge QC system uses a fixed-camera microscope image of each washed cartridge baseplate (`Holes_ch00.png`) to locate seven mounting holes ("tags"), measure their diameters via sub-pixel ray-casting, and issue a PASS/FAIL decision against a 0.45–0.55mm specification. The detection pipeline (`detect_features.py`) combines `cv2.HoughCircles` candidate generation with a two-stage geometric matching process (anchor selection, then candidate ranking) built on a fixed reference-offset table (`REF_OFFSETS`) calibrated for one image class.

This whitepaper documents a fourteen-stage engineering investigation (numbered Stage 2 through Stage 18 in project records) that began with reports of production failures on datasets outside the originally-validated set and progressed through root-cause analysis, two validated algorithm improvements, eight independent investigative stages that each exhaustively tested and ruled out a specific hypothesis for the remaining failures, a ground-truth reconciliation against an external Leica LAS AF measurement workflow, a direct visual/topological gap analysis, and a forward-looking architectural redesign.

**Two production changes were implemented and validated**, each following an investigation → design → blast-radius analysis → implementation → full-regression-validation discipline, against all 79 cartridges in the validated dataset, without exception:

1. **Stage 6 — Frozen-anchor recovery pass** (commit `23d6e93`): recovered 5 previously-missing holes, raising recall from 95.48% to 96.38%, with zero regressions.
2. **Stage 7 — Role-generalized Stage 1 anchor search** (commit `9bdc97e`): corrected Cartridge 72's systematically misassigned geometry (6 tags recovered/corrected to independently-verified genuine holes), with zero regressions among all cartridges with verifiable ground truth.

Four earlier defect fixes (Stage 5) and one earlier validation stage (Stage 2, validating the original candidate-ranking mechanism against unseen data) are also covered.

**Eight subsequent investigations (Stages 8–17)** each targeted one specific hypothesis for the remaining unresolved cases in Cartridges 48, 49, 66, and 72, using a different, independent methodology per stage (exhaustive parameter sweep, four alternative assignment algorithms, independent geometric-model validation, population-derived statistical replay, external Leica ground-truth reconciliation, a direct backward algorithmic trace, and direct visual/topological inspection). Every one of these investigations concluded that the remaining failures are **not** attributable to a remaining software defect — they are attributable to genuine imaging limitations, a real non-circular physical feature outside the current detector's feature model, or an architectural information gap (absence of shape-topology and whole-part contextual reasoning) that the current architecture was never designed to close.

**Stage 18** used this evidence to design a next-generation, modular detection architecture and concluded that the current production system, as amended, is complete for its architecture generation, and that closing the remaining gap is a new research effort, not a continuation of defect remediation.

---

## 2. Background

### 2.1 Original Software

`detect_features.py` implements a single-image, single-pass circular-hole detector for cartridge baseplate quality control. For each cartridge image:

1. The image is preprocessed (cropped to its active content area, downsampled 4×, contrast-normalized via CLAHE, Gaussian-blurred) to prepare it for Hough circle detection.
2. `cv2.HoughCircles` generates raw circular candidates at a fixed nominal radius, with fixed accumulator/gradient thresholds.
3. Each candidate is ray-cast (36 rays, sub-pixel threshold-crossing) to produce a diameter estimate and a set of quality metrics (`n_hit`, `near_nominal_ratio`, `angular_gap`, `fallback_mode`).
4. A fixed table of seven relative pixel offsets (`REF_OFFSETS`, one seven-tag hole layout, calibrated for a single image class) is used to hypothesize where each of the seven tags should sit, once one reference ("anchor") point is chosen.
5. The measured diameter is converted to millimeters via a calibration scale factor and compared against a 0.45–0.55mm specification to produce PASS/FAIL.

### 2.2 Original Limitations

At the outset of this investigation, the software was known to produce incorrect results — missing holes, wrong measurements, incorrect PASS/FAIL — on cartridge datasets acquired after the original validated set, plus two latent defects in the surrounding batch-processing and preprocessing code. The root causes of these failures had not yet been isolated to a specific pipeline stage.

### 2.3 Project Goals

The investigation was chartered with a consistent discipline, carried through all eighteen stages: **never modify code without a preceding investigation; never commit without full-dataset regression validation; never speculate beyond directly measured evidence; disclose limitations and self-discovered defects transparently, including when they complicate a prior conclusion.** The goal was not to force every cartridge to pass, but to determine, with evidence, exactly how far the existing algorithm could be safely improved — and to be equally rigorous in proving when it could not be improved further without a different kind of algorithm entirely.

---

## 3. Existing Architecture

### 3.1 Original Pipeline (Pre-Investigation)

```
                    Holes_ch00.png (full-resolution microscope image)
                              │
                              ▼
                   ┌────────────────────┐
                   │   preprocess()      │  crop to active area
                   │                      │  → 4× downsample
                   │                      │  → CLAHE contrast normalize
                   │                      │  → Gaussian blur
                   └────────────────────┘
                              │
                              ▼
                   ┌────────────────────┐
                   │  cv2.HoughCircles    │  fixed dp / param1 / param2 /
                   │  (candidate          │  minDist / min-max radius,
                   │   generation)        │  applied once, whole active area
                   └────────────────────┘
                              │
                              ▼           list of (cx, cy, r) raw candidates
                   ┌────────────────────┐
                   │  Ray-cast metrics    │  36 fixed rays per candidate,
                   │  (_subpixel_diameter)│  sub-pixel threshold crossing,
                   │                      │  n_hit / near_nominal_ratio /
                   │                      │  angular_gap / fallback_mode
                   └────────────────────┘
                              │
                              ▼
                   ┌────────────────────┐
                   │  PIPELINE STAGE 1    │  try each raw candidate ONLY
                   │  Anchor Selection    │  in the Tag-9 role; the highest-
                   │                      │  scoring candidate becomes the
                   │                      │  anchor; REF_OFFSETS then
                   │                      │  predicts all 7 tag positions
                   └────────────────────┘
                              │
                              ▼
                   ┌────────────────────┐
                   │  PIPELINE STAGE 2    │  for each of the 7 predicted
                   │  Candidate Ranking   │  positions, search candidates
                   │  / Substitution      │  within MATCH_TOL_PX and keep
                   │                      │  the best-ranked one (fallback
                   │                      │  tier → n_hit → near-nominal
                   │                      │  count → distance)
                   └────────────────────┘
                              │
                              ▼
                   ┌────────────────────┐
                   │  Measurement         │  diameter_px × mm_per_px
                   │  (calibration)       │  (Leica-derived scale factor)
                   └────────────────────┘
                              │
                              ▼
                   ┌────────────────────┐
                   │  PASS / FAIL         │  0.45mm ≤ diameter ≤ 0.55mm
                   └────────────────────┘
```

**Note on terminology:** the pipeline's own internal stage names — "Stage 1" (anchor selection) and "Stage 2" (candidate ranking) — predate and are independent of this investigation's numbered stages (Investigation Stage 2, Stage 5, …, Stage 18). Where ambiguity is possible, this document uses "Pipeline Stage 1/2" for the algorithm's internal stages and "Investigation Stage N" for this project's chronological work.

### 3.2 Original Failure Mode

Pipeline Stage 1's single-role restriction meant the anchor competition only ever asked "how well does this candidate work as Tag 9?" — never any other role. If the true Tag 9 location had no valid Hough candidate (as later proven for Cartridge 72, §4.6), no genuine hole could ever win the anchor competition, corrupting the geometric prediction for all seven tags at once. Separately, Pipeline Stage 1/2 together had no mechanism to recover a tag that had a valid nearby candidate but fell just outside the fixed ranking tolerance — such tags were reported simply as missing.

---

## 4. Investigation Timeline

Each entry below follows problem → hypothesis → investigation → implementation → validation → conclusion, and cross-references the underlying report(s) in `docs/`.

### Investigation Stage 2 — External Validation of Candidate Ranking

- **Problem:** the candidate-ranking mechanism (Pipeline Stage 2, itself a product of earlier investigation stages 1/3/4 predating this whitepaper's scope) had only been validated against the original 33-cartridge training set. Its behavior on unseen data was unconfirmed.
- **Hypothesis:** the ranking logic generalizes to new cartridges without introducing regressions or unintended side effects (in particular, a previously-found "coupling bug" pattern where a change in one area silently affected another).
- **Investigation:** both the pre-Stage-2 baseline and the Stage-2 candidate-ranking version were run, unmodified, against 17 entirely unseen cartridges (`E:\34-50\WB(2)`), comparing every matched tag's position, diameter, and PASS/FAIL across 104 tag-rows.
- **Implementation:** none — validation only.
- **Validation:** direct visual review of every one of the 5 tag assignments that differed between versions.
- **Conclusion:** pattern-matching (which tags match) was identical in 100% of cases; exactly 5 tag assignments changed, all in one cartridge (39), all confirmed correct on visual inspection (5/5, including one case where the baseline had been silently measuring a scratch instead of the true hole). A pre-existing, unrelated pattern-matching limitation on wide/short-aspect-ratio images (Cartridges 45, 48, 49, 50) was identified and flagged for future investigation, not attributed to Stage 2. *(`docs/STAGE2_EXTERNAL_VALIDATION_REPORT.md`)*

### Investigation Stage 5 — Root-Cause Analysis and Bug Fixing

- **Problem:** production failures on datasets 51–60, 61–70(1), 71–79 (missing holes, incorrect measurements, incorrect PASS/FAIL), plus two latent defects in surrounding code.
- **Hypothesis:** each failure traces to one specific, identifiable pipeline stage, and at least some are simple software defects rather than algorithm limitations.
- **Investigation:** every failed tag was traced individually through candidate generation, ranking, pattern-matching, and measurement.
- **Implementation:** four independently-committed fixes: duplicate PNG processing in the batch runner (`qc_app.py`), a silent `"holes"` fallback masking unrecognized image types (`preprocess.py`), a console-encoding crash exposed by that same fix (`detect_features.py`), and a missing-hole diagnostic that mislabeled some `not_detected` cases as `outside_image` (`detect_features.py`).
- **Validation:** full regression across all 5 dataset groups after each individual fix; a dedicated blast-radius analysis confirmed the diagnostic-label fix changed exactly the 12 expected labels with no measurement or PASS/FAIL side effects.
- **Conclusion:** all four defects fixed with zero regressions. *(commit `2813b93`; `docs/FINAL_PROJECT_REPORT.md` §2, §3)*

### Investigation Stage 6 — Detection Recall Improvement

- **Problem:** 25 holes project-wide were left unmatched by Pipeline Stage 1/2, with no recovery mechanism.
- **Hypothesis:** recall can be improved without harming precision.
- **Investigation:** an empirical sweep of `MATCH_TOL_PX` (600–690px) as a naive global tolerance increase was tested and found to **destabilize Pipeline Stage 1's anchor selection**, causing severe regressions in Cartridges 38, 46, and 48 — this approach was rejected before implementation.
- **Design:** a frozen-anchor, strictly additive recovery pass was designed instead — it never re-runs anchor selection and never touches an already-matched tag, only searching a wider (690px), quality-gated radius for tags Pipeline Stage 2 left unmatched.
- **Design validation:** the recovery pass's real candidate population was exhaustively enumerated across all 79 cartridges (7 real candidates total) and the proposed quality gate (`fallback_mode=="normal"`, `near_nominal_ratio>=0.70`, `max_angular_gap<=40°`) was shown to achieve 100% precision and 100% recall against that population before being implemented.
- **Implementation:** commit `23d6e93`.
- **Validation:** full regression across all 79 cartridges; zero regressions; every recovered hole visually verified.
- **Conclusion:** 5 holes recovered (Cartridge 18, Tags 1, 3, 5, 6, 7); recall 95.48% → 96.38%; precision held at 100%; F1 97.68% → 98.16%. 14 of the original 25 missing holes remained unrecoverable because their predicted positions were genuinely outside the captured frame. Cartridge 72's broader failure was explicitly flagged as requiring its own dedicated investigation. *(`docs/STAGE6_DETECTION_RECALL_PLAN.md`, `STAGE6_ALGORITHM_EVALUATION_REPORT.md`, `STAGE6_RECOVERY_PASS_DESIGN.md`, `STAGE6_QUALITY_GATE_VALIDATION_REPORT.md`, `STAGE6_RECOVERY_PASS_IMPLEMENTATION_REPORT.md`)*

### Investigation Stage 7 — Geometric Model Investigation, Redesign, and Implementation

- **Problem:** Cartridge 72 systematically violated the geometric model in a way the Stage 6 recovery pass could not fix.
- **Hypothesis:** the true Tag 9 location has no valid Hough candidate, and because Pipeline Stage 1 only ever tries a candidate in the Tag-9 role, no genuine hole can ever win the anchor competition — corrupting all seven predicted positions.
- **Investigation:** Cartridge 72's 6 non-anchor holes were shown to fit `REF_OFFSETS` almost perfectly (6–7px RMS) once a hypothetical correct anchor was assumed; a root-cause trace across all 24 raw candidates confirmed a false anchor uniquely scored 3/7 under the Tag-9-only assumption while every genuine hole scored only 1/7; two of the three tags Pipeline Stage 2 had "matched" were shown to be misidentified (one was actually a different tag's hole; one was a low-quality substitute). An independent verification pass re-derived every claim from scratch, catching and fixing a bug in the verification script itself before trusting its own output.
- **Design:** five candidate redesigns were evaluated (quality-weighted scoring, consensus/RANSAC, graph/voting, geometric-consistency scoring, and a hybrid); the minimal, fully general option was selected: generalize Pipeline Stage 1's anchor trial loop from "try each candidate as Tag 9 only" to "try each candidate against all 7 tag roles," with a fallback-quality/residual tie-break.
- **Blast-radius validation:** a tie-break bug was found during this analysis, disclosed, fixed, and the corrected run was proven byte-identical in outcome to the buggy run (proving the bug had never actually changed any result) — 74 of 79 cartridges were confirmed unaffected, with 5 changed (18, 48, 49, 66, 72). A separate deep dive fully root-caused a Cartridge 66 PASS→FAIL regression as a legitimate pivot-quality improvement interacting with Pipeline Stage 2's fixed re-ranking window, and deferred it pending independent Leica ground truth, per explicit instruction.
- **Implementation:** commit `9bdc97e`.
- **Validation:** full regression across all 79 cartridges, run three independent times with identical results; a code-identity diff confirmed Pipeline Stage 2, the recovery pass, and diagnostics were untouched. A newly-exposed FAIL in Cartridge 48/Tag 1 was traced to a pre-existing, separately-documented image-quality condition, visually confirmed to not be a genuine hole in either competing candidate, and disclosed rather than treated as a blocker.
- **Conclusion:** Cartridge 72's 6 target tags (1, 3, 4, 5, 6, 7) recovered or corrected to independently-verified genuine holes with zero regressions among all cartridges with verifiable ground truth. *(`docs/STAGE7_GEOMETRIC_MODEL_INVESTIGATION_REPORT.md`, `STAGE7_CARTRIDGE72_ROOT_CAUSE_TRACE.md`, `STAGE7_CARTRIDGE72_VERIFICATION_REPORT.md`, `STAGE7_ANCHOR_SELECTION_REDESIGN.md`, `STAGE7_ANCHOR_REDESIGN_BLAST_RADIUS_ANALYSIS.md`/`_CORRECTED.md`, `STAGE7_CARTRIDGE66_ROOT_CAUSE_INVESTIGATION.md`, `STAGE7_CARTRIDGE72_FOCUSED_DESIGN_FINAL.md`, `STAGE7_STAGE1_IMPLEMENTATION_VALIDATION_REPORT.md`, `STAGE7_CARTRIDGE48_TAG1_INVESTIGATION.md`, `FINAL_STAGE7_SUMMARY.md`)*

### Investigation Stage 8 — Candidate Generation Investigation

- **Problem:** Cartridges 48, 49, 66, and 72's Tag 9 remained unresolved after Stages 6–7.
- **Hypothesis:** the remaining failures are caused by Hough candidate generation missing the true hole.
- **Investigation:** full raw-candidate replay and color-coded visual overlays for all four targets; direct inspection of the exact preprocessed image Hough operates on; a read-only parameter sensitivity sweep across `dp`, `param2`, `minDist`, and radius limits.
- **Implementation:** none — analysis only, as explicitly scoped.
- **Validation:** every parameter change was checked for both new-candidate recall and false-positive cost across the full dataset.
- **Conclusion:** Cartridges 66 and 72's Tag 9 are genuinely limited by candidate generation — the true feature is an oversized, non-circular channel junction, not detectable as a matching-size circle. Cartridges 48 and 49 instead had **unused, perfect-quality candidates already present** — implicating candidate *selection*, not generation, in those two cartridges. Every parameter capable of surfacing new candidates near any target did so at a 79×–244× false-positive cost project-wide; `minDist` had no measurable recall effect at any tested value. No safe candidate-generation change exists. *(`docs/STAGE8_CANDIDATE_GENERATION_INVESTIGATION.md`)*

### Investigation Stage 9 — Candidate Assignment Investigation

- **Problem:** perfect-quality candidates in Cartridges 48 and 49 were never selected.
- **Hypothesis:** the greedy assignment logic (Pipeline Stage 1/2) is suboptimal and a smarter assignment algorithm would recover them.
- **Investigation:** a full assignment-pipeline trace quantified that the unused candidates score only 2–3 as any hypothetical pivot versus the winning hypothesis's 4–5, and sit 1,289–8,850px from any predicted position under the winning anchor. Four alternative strategies were implemented and replayed read-only against the identical raw candidate pool: Hungarian assignment (with a cost-matrix bug found, disclosed, and corrected — see §5.3), maximum bipartite matching, global optimization (exhaustive anchor search scored via Hungarian), and geometric residual minimization.
- **Additional verification (requested mid-investigation):** a spurious 3-point geometric fit's implausible scale (≈1.97) was checked against an established range (0.91–1.09) observed across 6 cartridges; a forced-coexistence test (adding each unused candidate to production's own matched set under every remaining role) confirmed the incompatibility is genuine, not an artifact of under-constrained fitting — every one of 8 tested combinations made the fit's scale and rotation dramatically worse.
- **Implementation:** none — analysis only.
- **Validation:** every alternative strategy's output was directly compared against production and against every other strategy.
- **Conclusion:** the current greedy assignment is **provably optimal** for this candidate pool — Hungarian assignment and exhaustive global optimization reproduce it exactly in both cartridges. No assignment-algorithm change is recommended. *(`docs/STAGE9_CANDIDATE_ASSIGNMENT_INVESTIGATION.md`)*

### Investigation Stage 10 — Reference Geometry Validation

- **Problem:** with candidate generation and assignment both ruled out, the reference geometry model itself (`REF_OFFSETS`) remained a possible cause.
- **Hypothesis:** `REF_OFFSETS` is inaccurate or distorted for Cartridges 48/49's dataset batch.
- **Investigation:** an independent RANSAC search for every maximal self-consistent candidate cluster found none beyond a single physically-implausible 3-point, 162.6°-rotation cluster in Cartridge 48, and nothing at all in Cartridge 49; similarity/affine model residuals, pairwise-distance preservation, and angular preservation were quantified; a local-deformation diagnostic showed scattered, non-systematic residual behavior, arguing against any coherent distortion field.
- **Implementation:** none — analysis only.
- **Validation:** decisive cross-check against Cartridge 34, from the identical dataset batch as both 48 and 49, which fits `REF_OFFSETS` with RMS = 1.08px and scale = 1.0001 — essentially perfectly.
- **Conclusion:** `REF_OFFSETS` remains globally valid. The reference geometry is not the source of Cartridges 48/49's unresolved tags. *(`docs/STAGE10_REFERENCE_GEOMETRY_VALIDATION.md`)*

### Investigation Stage 11 — Image Quality and Failure Attribution

- **Problem:** with generation, assignment, and geometry all ruled out for Cartridges 48/49, and a distinct physical-feature cause already suspected for 66/72's Tag 9, a final synthesis was needed across all four cartridges.
- **Hypothesis:** the remaining unresolved tags are fundamentally limited by image quality or represent a genuinely different physical feature, not a software defect.
- **Investigation:** 11 image-quality metrics (contrast, edge strength, gradient magnitude, blur, saturation, illumination variation, SNR, ray-hit distribution, circularity, and more) were quantified at all 7 remaining unresolved tag locations and compared against 9 successfully-detected holes plus 3 specifically-named baseline cartridges.
- **Implementation:** none — analysis only.
- **Validation:** direct visual inspection corroborated every quantitative classification.
- **Conclusion:** 3 of 7 unresolved tags have no image data at all (predicted position outside the captured frame, confirmed by direct boundary inspection); 2 of 7 show weak/degraded signal consistent with an already-documented lower-image-quality dataset cluster; 2 of 7 (Cartridge 66 and 72's Tag 9) are confirmed, both visually and quantitatively (edge strength 4.1–4.7 vs. a successful-case range of 5.5–69), to be a different physical feature. No remaining case is attributable to a software limitation. *(`docs/STAGE11_IMAGE_QUALITY_FAILURE_ATTRIBUTION.md`)*

### Investigation Stage 12 — Leica Gap Investigation

- **Problem:** a human Leica LAS AF operator can reportedly see and measure holes the algorithm cannot.
- **Hypothesis (original, corrected mid-stream):** the original framing assumed Leica runs an independent, reverse-engineerable detection algorithm. Direct repository inspection (`leica_calibration.py`) showed this false — every Leica reference in the repository is a pixel-scale calibration source, not an independent detector. This was flagged before proceeding, and the actual situation (an external, human-operated LAS AF workflow, not present in this repository) was confirmed directly.
- **Investigation:** the current pipeline was reframed, stage by stage, around a single structural diagnosis — Hough circle detection plus ray-cast measurement has no representation for "a real feature that is not a circle of the expected size," so it either finds a matching circle or reports nothing at all. Three alternative techniques (contour + ellipse fitting, connected-components/adaptive threshold, and an illustrative single-scale Fast Radial Symmetry Transform) were run read-only against all 4 target locations plus a known-genuine control hole, with results and honest caveats (the radial-symmetry implementation underperformed even on the control case) reported directly.
- **Implementation:** none — analysis only, explicitly scoped as "do not implement."
- **Validation:** twelve alternative methodologies were ranked by expected recall improvement, false-positive risk, pipeline compatibility, computational cost, and implementation complexity.
- **Conclusion:** a **hybrid detector** — the existing Hough pipeline unchanged for the cartridges it already handles correctly, plus an additive, quality-gated segmentation-based secondary pass for large/non-circular regions Hough's constraints reject — ranked highest of all options evaluated, directly motivating Investigation Stage 13. For the three off-frame tags, no computer-vision method evaluated can help; the data does not exist in the current images. *(`docs/STAGE12_LEICA_GAP_INVESTIGATION.md`)*

### Investigation Stage 13 — Hybrid Secondary Detector Design and Prototype

- **Problem:** Stage 12 recommended a segmentation-based secondary detector; this needed to be designed and prototyped before any implementation decision.
- **Hypothesis:** a strictly additive secondary detector, executing only for tags left unmatched after the complete existing pipeline, can recover real holes without any risk to the 74+/79 cartridges already handled correctly.
- **Investigation:** segmentation approaches (connected components, adaptive thresholding, contour extraction, ellipse fitting, region growing, morphological operations) were implemented in `stage13_common.py` and generated secondary candidates only from Hough-rejected regions, reporting a full metric set (centroid, area, perimeter, circularity, solidity, aspect ratio, equivalent diameter, ellipse parameters, edge strength, distance from prediction) for every candidate, using only measured evidence — no invented thresholds.
- **Implementation:** none in production — validated in analysis scripts only, per explicit scope.
- **Validation:** results were compared against production and against the Stage 7 implementation; a blast-radius analysis confirmed the design's integration points (never modifying Stage 1/2/recovery/committed logic, only running on already-unmatched tags) leave the existing pipeline provably untouched.
- **Conclusion:** the additive design is architecturally safe, but **cannot recover Cartridge 66/72's Tag 9** specifically because those tags are already considered "matched" by production (at low confidence) — the secondary detector, by its own safe design, never runs for a tag that already has a match. This directly motivated Investigation Stage 14. *(`docs/STAGE13_HYBRID_SECONDARY_DETECTOR.md`)*

### Investigation Stage 14 — Low-Confidence Match Re-evaluation

- **Problem:** Stage 13 proved the additive secondary detector cannot reach tags that are already matched at low confidence.
- **Hypothesis:** those existing low-confidence matches should not be treated as immutable, and a confidence-aware replay might safely recover better candidates.
- **Investigation:** every currently-assigned tag across Cartridges 48, 49, 66, and 72 (22 tags) was reported in full; a confidence ranking was built entirely from the **measured population** — 541 real matched tags across all 79 cartridges, yielding a data-derived 5th-percentile near-nominal-ratio threshold of 0.8611, with no invented cutoff. Statistical outliers were identified; for each, every other raw candidate was checked for a strictly better, geometrically consistent, non-conflicting alternative at both the existing safe tolerance (690px) and a wider, exploratory-only 1,200px radius.
- **Implementation:** none — analysis only.
- **Validation:** a confidence-aware replay froze every tag above the measured threshold and allowed only flagged low-confidence tags to be reassigned, if and only if a safe (≤690px) improvement existed.
- **Conclusion:** zero tags recovered, zero regressions. One lateral, confidence-neutral swap was found (Cartridge 72/Tag 9). Widening the search radius far enough to find nominally "better" candidates reproduced a known failure mode: two different tags in Cartridge 49 independently claimed the same physical candidate as their best alternative — direct proof that relaxing tolerance far enough to help these cases reintroduces the cross-tag contention risk Stage 6 had already evaluated and rejected. The pipeline was proven, not merely argued, to have reached the information limit of the available images for these cases. *(`docs/STAGE14_LOW_CONFIDENCE_REASSESSMENT.md`)*

### Investigation Stage 15 — Leica Ground Truth Validation

- **Problem:** actual Leica LAS AF measurement exports became available for Cartridge 48 ("BP 48") and Cartridge 61 ("BP 61", as a control), providing real external ground truth for the first time.
- **Hypothesis:** Leica's data would confirm whether Cartridge 48's unresolved Tags 5 and 7 are genuine, real holes.
- **Investigation:** Leica's precise measurement tables (referencing the same `Holes_ch00.png` source file production processes) were compared directly against production's own measurements; Cartridge 61 established a baseline production-vs-Leica measurement noise floor (0–8.2% diameter variance even under perfect, 36/36-confidence detection).
- **Implementation:** none — analysis only.
- **Validation:** every diameter comparison was checked against this noise floor to distinguish normal measurement variance from a genuine anomaly (only Tag 1's 8.1% difference was anomalous — it flips PASS→FAIL, unlike Cartridge 61's comparable 8.2% maximum, which stays PASS on both sides).
- **Conclusion:** Leica confirms Tags 5 and 7 are real, passing holes (0.52mm each) present in the same source image production already processes — **correcting** Stage 11's classification of these as an imaging/field-of-view limitation. The true cause is anchor imprecision (no high-confidence candidate exists anywhere in Cartridge 48 to anchor from), not a hard imaging boundary. No Leica reference data exists for Cartridges 49, 66, or 72, explicitly limiting this stage's ground-truth analysis to Cartridge 48. *(`docs/STAGE15_LEICA_GROUND_TRUTH_VALIDATION.md`)*

### Investigation Stage 16 — Leica Backward Trace

- **Problem:** Stage 15 established Tags 5 and 7 are real; the exact algorithmic decision that makes them unreachable needed to be identified.
- **Hypothesis:** a single, identifiable, irreversible decision in the pipeline is responsible.
- **Investigation:** the committed pipeline was replayed exactly, stage by stage, for Cartridge 48, Tags 5 and 7 only, recording the chosen anchor, predicted position, and every candidate considered at Pipeline Stage 2's and the recovery pass's search windows.
- **Implementation:** none — analysis only.
- **Validation:** a residual-correlation check (reference-offset magnitude vs. assignment residual, Pearson r = 0.323) ruled out a simple scale/rotation drift explanation.
- **Conclusion:** the first irreversible decision is Pipeline Stage 1's anchor selection, forced to rely on Cartridge 48's best-available but still low-confidence candidate. This single decision fixes Tag 5's predicted position 702px beyond the image's actual bottom edge and Tag 7's predicted position within bounds but with zero real candidates within either search window. Classified as **anchor localization error**, with the fixed search-window size acting as the final, downstream blocking mechanism — a consequence of the anchor error, not an independent cause. *(`docs/STAGE16_LEICA_BACKWARD_TRACE.md`)*

### Investigation Stage 17 — Human vs. Algorithm Feature Analysis

- **Problem:** determine exactly what visual evidence a human Leica operator uses that the algorithm ignores.
- **Hypothesis:** specific, describable visual/topological cues exist that the current detector structurally cannot evaluate.
- **Investigation:** direct crops of the actual production image were generated and visually inspected at every coordinate Stage 16 established — predicted positions, assigned candidates, and every raw Hough candidate — compared against a textbook clean hole (Cartridge 61) and against known false-positive/scratch/channel-wall examples.
- **Implementation:** none — analysis only.
- **Validation:** every visual claim was grounded in a specific, coordinate-referenced crop of the real image, not description from memory or inference.
- **Conclusion:** Tag 7's predicted position sits directly on a channel-wall corner (confirmed visually, not just analytically); Tag 5's predicted position falls entirely off the imaged part. Three tags currently assigned at low confidence (3, 6, 9) sit on plain surface texture with no visible hole boundary at all — a materially stronger, directly-observed confirmation of Stage 14's statistical findings. A previously undocumented finding was disclosed: Tag 4 (currently a "normal"-fallback PASS) sits on the rim of a large, unrelated disc feature, not a small hole. The highest-ranked missing capability is **contextual/topological relationship to the visible channel network** — the only examined cue that would address Stage 16's anchor-error root cause rather than only filtering candidates after the fact. *(`docs/STAGE17_HUMAN_FEATURE_ANALYSIS.md`)*

### Investigation Stage 18 — Next-Generation Detector Architecture

- **Problem:** having exhausted the current architecture's improvement potential (Stages 8–14) and identified the specific missing capability classes (Stages 16–17), a forward design was needed.
- **Hypothesis:** a modular, multi-generator architecture could close the identified gap, but represents new capability, not defect remediation.
- **Investigation:** none — design synthesis only, explicitly built on Stages 5–17's accepted conclusions without repeating their investigations.
- **Implementation:** none — design only.
- **Validation:** n/a — this stage defines the validation methodology future phases would need (population-scale zero-regression checks, per the precedent set by every implemented change in this project).
- **Conclusion:** a five-generator modular architecture was specified (Hough unchanged; connected-components/segmentation; contour/ellipse fitting; shape-topology analysis; channel-context analysis), each with purpose, interaction, cost, complexity, and regression risk defined; a four-phase migration roadmap was produced; and the final recommendation stated that the current production system should be considered complete for its architecture generation, while further work constitutes a new research project. *(`docs/STAGE18_NEXT_GENERATION_DETECTOR_ARCHITECTURE.md`)*

---

## 5. Engineering Decisions

This section explains the major design choices made across the investigation and why the rejected alternatives were rejected — each grounded in a specific piece of evidence, not preference.

### 5.1 Additive-only changes over broad tolerance increases

**Decision:** every implemented change (Stage 6 recovery pass, Stage 7 anchor generalization) was designed to be strictly additive — never modifying an already-correct match, never re-running an already-completed decision.

**Rejected alternative:** a naive global increase to `MATCH_TOL_PX`. **Why rejected:** Stage 6's own evaluation proved this destabilizes Pipeline Stage 1's anchor selection, causing severe regressions in three specific cartridges (38, 46, 48) purely from widening the tolerance, before any recovery benefit was even realized. This result generalized: Stage 14 later found the same failure mode again (two Cartridge 49 tags claiming the same candidate) when a wider exploratory radius was tested read-only, confirming the original Stage 6 finding was not a one-off.

### 5.2 Role-generalization over four alternative anchor redesigns

**Decision:** Stage 7 generalized Pipeline Stage 1's anchor trial loop to try every candidate against every tag role, rather than adopting one of four other evaluated designs (quality-weighted scoring, consensus/RANSAC, graph/voting, geometric-consistency scoring).

**Why the simpler design won:** the role-generalization was the **minimal** change that fully addressed the proven root cause (Cartridge 72's true Tag-9 location having no valid candidate) without introducing the additional validation burden and complexity the other four approaches would have required, several of which would have changed behavior even for cartridges that already worked correctly. The blast-radius analysis confirmed this minimality held in practice: 74 of 79 cartridges were byte-identical before and after.

### 5.3 Disclosure of self-discovered defects during investigation, not just production defects

**Decision:** two bugs found *within this investigation's own analysis tooling* (a Stage 7 tie-break bug in the blast-radius script, and a Stage 9 Hungarian-assignment cost-matrix bug that caused a square-matrix "dummy absorption row" formulation to route every candidate through free rows, producing empty matches) were disclosed and corrected transparently, with the corrected and original results compared, rather than silently fixed and hidden.

**Why:** the project's standing discipline required treating an investigation's own tooling with the same rigor as production code — an undisclosed bug in a verification script could have produced a false confidence in either direction (false regression, or false all-clear).

### 5.4 Rejecting a "fix the geometry" theory once cross-batch evidence contradicted it

**Decision:** Stage 10 concluded `REF_OFFSETS` is not the source of Cartridges 48/49's unresolved tags, closing off what might otherwise have seemed the most likely remaining theory.

**Why rejected:** Cartridge 34, from the identical dataset batch as 48 and 49, fits the exact same fixed offsets with RMS = 1.08px — direct, decisive evidence that the reference geometry itself is correct for this batch, and that whatever is different about 48/49 is a property of those specific cartridges' images, not the shared geometric model.

### 5.5 Proving assignment-algorithm optimality rather than assuming it

**Decision:** Stage 9 implemented and compared four alternative assignment strategies against production's own greedy logic, rather than accepting a hypothesis that "a smarter algorithm would help" on faith.

**Why:** Hungarian assignment and an exhaustive global-optimization search — both strictly more powerful search procedures than greedy matching — reproduced production's exact result in every tested case. This is a **proof**, not an assumption, that the current greedy assignment is already optimal for the available candidate pool, and materially changed the direction of the entire investigation toward earlier pipeline stages (geometry, candidate generation) instead.

### 5.6 Preferring a segmentation-based hybrid detector over Hough-parameter tuning or ML

**Decision:** Stage 12 ranked a hybrid (Hough-plus-segmentation) detector highest among twelve alternatives, and Stage 18's roadmap defers any machine-learning detector to a conditional final phase.

**Why:** Stage 8 had already exhaustively proven no safe Hough-parameter change exists (every option tested costs 79×–244× in false positives). A segmentation-based secondary pass, by contrast, directly targets the specific, evidenced failure mode (non-circular channel junctions) without touching the 74+/79 cartridges that already work — the same additive-safety principle established in Stage 6. Machine learning was placed last in the roadmap specifically because every classical technique proposed traces to a concrete, evidenced gap (Stage 17); introducing ML without an equally specific justification would break this project's standing evidence discipline, and would require a labeled dataset (expanded Leica ground truth) this project does not yet have.

---

## 6. Validation Methodology

Every production change in this project was validated identically, regardless of size:

1. **Full-dataset regression.** All 79 cartridges across all five dataset groups (`E:\1-33`, `E:\34-50\WB(2)`, `E:\51-60\WB(3)`, `E:\61-70 (1)\WB(4)`, `E:\71-79\WB(5)` — 553 total tag-slots) were run through both the pre-change and post-change code, loaded as separate Python modules from their respective git states (the pre-change version via `git show HEAD:detect_features.py`, never the working tree re-implemented from memory). Every matched tag's position, `diameter_mm`, `pass` value, and every `missing_holes` reason was compared exactly.
2. **Compile and import verification.** `python -m py_compile detect_features.py` and `python -c "import detect_features"` were run and confirmed clean after every single code change.
3. **Blast-radius analysis before implementation.** For both the Stage 6 and Stage 7 changes, the expected set of changed cartridges was predicted analytically *before* implementation, then confirmed to match exactly after implementation.
4. **Repetition for determinism.** The Stage 7 change was independently regression-tested three separate times (pre-implementation blast-radius analysis, post-implementation validation, and final close-out re-run), with byte-identical results every time — ruling out any non-determinism in the pipeline itself as a confound.
5. **Visual verification of every claimed improvement.** Every recovered or corrected hole (Stage 6, Stage 7) was visually inspected against the real image before being counted as an improvement, not accepted on numeric evidence alone.
6. **Any difference required an individual explanation** before being accepted (as a genuine improvement) or rejected (as a regression) — no difference was ever dismissed as "probably fine."

No change was ever committed on the basis of a partial or single-cartridge test. This methodology was applied without exception across all six production commits in this project's history.

---

## 7. Performance Improvements

| Metric | Before Stage 6 | After Stage 6 | Source |
|---|---|---|---|
| Matched tags | 528 / 553 | 533 / 553 | `STAGE6_RECOVERY_PASS_IMPLEMENTATION_REPORT.md` |
| Precision | 100% (528/528) | 100% (533/533) | same |
| Recall | 95.48% | 96.38% | same |
| F1 | 97.68% | 98.16% | same |

**Stage 7 (role-generalized anchor search) — independently-verified changes:**

| Cartridge | Tag(s) | Change |
|---|---|---|
| 72 | 1, 3, 4, 5 | Newly recovered (previously missing), all 36/36 ray-cast quality |
| 72 | 6 | Corrected from a misidentified duplicate of Tag 3's hole to its own genuine hole |
| 72 | 7 | Corrected from a low-quality substitute (previously FAIL at 0.57mm) to its own genuine hole (now PASS at 0.51mm) |
| 18 | 4 | Quality-upgraded from a moderate (24/36) match to a perfect (36/36) match; PASS/FAIL unchanged |

**Regressions prevented (not merely avoided by luck):** the naive global tolerance increase evaluated in Stage 6 was proven, before implementation, to corrupt previously-correct measurements in three cartridges — this defective approach never reached production. Both implemented changes were separately proven incapable of altering any already-correct match: 74/79 cartridges remained byte-identical across every validation run of the Stage 7 change.

**Explicitly not counted as confirmed improvements:** Cartridges 48 and 49's net tag-count changes from the Stage 7 implementation (+1 and +3 matched tags respectively) are not claimed as verified recall gains, because Stages 8–17 established these cartridges lack independently-confirmed ground truth for most of their tags, and at least one newly-exposed result (Cartridge 48, Tag 1) is a new FAIL traced to a pre-existing image-quality condition, not a verified correct measurement.

---

## 8. Root Cause Taxonomy

```
Root causes discovered (Stages 5–17)
│
├── Software bugs (fixed)
│   ├── Duplicate PNG processing (case-insensitive glob matching)         [qc_app.py]
│   ├── Silent "holes" fallback masking unrecognized image types          [preprocess.py]
│   ├── Console-encoding crash exposed by the above fix                   [detect_features.py]
│   └── Missing-hole diagnostic mislabeling (anchor approximation error)  [detect_features.py]
│
├── Algorithm limitations (fixed)
│   ├── No recovery mechanism for tags outside Stage 2's fixed tolerance  → Stage 6 recovery pass
│   └── Single-role (Tag-9-only) anchor search                           → Stage 7 role-generalized search
│
├── Image limitations (confirmed, not fixable in software)
│   ├── Predicted position genuinely outside the captured frame           (Cartridge 48/Tag5, 49/Tag5, 49/Tag9)
│   └── Weak/degraded signal (low SNR, sparse ray hits, elevated saturation) (Cartridge 48/Tag7, 49/Tag7)
│
├── Physical feature limitations (confirmed, not a defect)
│   └── Real but oversized, non-circular channel-junction feature         (Cartridge 66/Tag9, 72/Tag9)
│
└── Architectural / representational limitations (Stages 16–18, not fixable by tuning)
    ├── Single fixed-anchor, linear-offset geometric model has no self-correction mechanism
    ├── Fixed-radius search windows not robust to anchor-error outliers
    ├── No shape/topology evaluation (ray-cast counts edge crossings only)
    └── No contextual/topological use of the visible channel network
```

Each branch above was established by a *different* investigative methodology (defect tracing, parameter sweep, optimal-assignment replay, geometric-model validation, statistical population replay, external ground-truth reconciliation, direct backward trace, direct visual inspection) — the taxonomy is convergent evidence, not a single analyst's classification scheme applied uniformly.

---

## 9. Final Production Architecture

```
                    Holes_ch00.png
                              │
                              ▼
                   preprocess()                         [unchanged]
                              │
                              ▼
                   cv2.HoughCircles                      [unchanged]
                              │
                              ▼
                   Ray-cast metrics (_subpixel_diameter) [unchanged — same function
                              │                            every analysis stage treats
                              │                            as ground truth]
                              ▼
        ┌─────────────────────────────────────────────┐
        │  PIPELINE STAGE 1 — Role-Generalized Anchor   │  ← Stage 7, commit 9bdc97e
        │  Selection: every candidate tried against      │
        │  every one of 7 tag roles; best-scoring        │
        │  (candidate, role) pair sets the anchor        │
        └─────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │  PIPELINE STAGE 2 — Candidate Ranking          │  [logic unchanged;
        │  (fallback tier → n_hit → near-nominal count    │   now receives a
        │   → distance), within MATCH_TOL_PX = 600px      │   materially better
        └─────────────────────────────────────────────┘   anchor as input]
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │  RECOVERY PASS — frozen anchor, additive only  │  ← Stage 6, commit 23d6e93
        │  tol=690px; gated on fallback_mode=="normal",  │
        │  near_nominal_ratio>=0.70, angular_gap<=40°    │
        │  never touches an already-matched tag          │
        └─────────────────────────────────────────────┘
                              │
                              ▼
                   Measurement (calibration scale)       [unchanged]
                              │
                              ▼
                   PASS / FAIL (0.45–0.55mm)              [unchanged]
```

Both modifications are strictly additive relative to the original architecture in §3.1: the recovery pass is a new terminal stage that only ever fills gaps, and the anchor generalization changes *what candidate wins* the anchor role without altering the surrounding Pipeline Stage 1/2/measurement/decision logic at all — confirmed by a code-identity diff during Stage 7's validation.

---

## 10. Remaining Limitations

| Category | Cases | Detail | Fixable in software? |
|---|---|---|---|
| **Solved** | 4 defects (Stage 5) + 2 algorithm gaps (Stages 6, 7) | See §8 | Already fixed |
| **Image limitations** | Cartridge 48/Tag5, 49/Tag5, 49/Tag9 (off-frame); 48/Tag7, 49/Tag7 (weak signal) | Predicted positions 702–2,874px beyond the captured frame boundary, confirmed by direct inspection; or sparse/partial ray-cast signal a human would also not confidently resolve | No — requires wider field of view or improved illumination/focus, not algorithm change (Stage 11, Stage 12 §6) |
| **Architectural limitations** | The anchor-localization root cause behind Cartridge 48's Tag5/Tag7 specifically (Stage 16) | Single fixed-anchor linear model has no self-correction mechanism; fixed search windows are not robust to anchor-error outliers; no shape-topology evaluation anywhere in the pipeline | Not via tuning — requires the Stage 18 architecture (multi-generator pool, shape-topology scoring, channel-context reasoning) |
| **Unsupported feature classes** | Cartridge 66/Tag9, 72/Tag9 (channel junctions); Cartridge 48/Tag4 (disc-rim tangency, newly disclosed in Stage 17) | Real, visually confirmed features the circular-hole detector was never designed to represent or measure | No — requires a different detector (Stage 12's hybrid recommendation) or a deliberate business decision to build one; not a defect in the existing detector |

---

## 11. Lessons Learned

- **Candidate generation, candidate assignment, and reference geometry were each independently disproven as the limiting factor** for Cartridges 48/49 (Stages 8, 9, 10 respectively) — each using a methodology strong enough to *prove* rather than *suggest* the negative result (exhaustive parameter sweep; provably-optimal alternative algorithms; cross-batch geometric cross-validation).
- **A seemingly-positive early result (geometric residual minimization recovering one candidate in Stage 9) was itself disproven** on closer inspection — its implausible scale (≈1.97, roughly double any value observed elsewhere in the project) and the discovery that it required discarding three previously-correct matches to gain one uncertain one showed it was a spurious artifact.
- **Widening tolerance is not a general-purpose recovery strategy** — proven twice, independently, in different stages (Stage 6's global-tolerance evaluation and Stage 14's wider-radius exploratory check both found the same cross-tag contention failure mode).
- **Statistical evidence and direct visual inspection can and should corroborate each other.** Stage 14's population-derived confidence ranking and Stage 17's direct visual crops independently reached the same conclusion about Cartridge 48's low-confidence tags (3, 6, 9) — a materially stronger result than either alone.
- **Investigating a stage's own analysis tooling with the same rigor as production code caught two real bugs** (Stage 7's tie-break script bug, Stage 9's Hungarian cost-matrix formulation) before either could produce a false conclusion.
- **A "gap to a human operator" is not automatically a software bug.** Stage 12's premise correction (Leica is not an independent algorithm) and Stage 15's ground-truth reconciliation (Leica data proved two "missing" holes are real) together show that closing a human-vs-algorithm gap requires first establishing exactly what the human is seeing — which turned out to be a representational capability (shape topology, contextual reasoning) the architecture never had, not a bug to patch.

---

## 12. Future Research

Per Stage 18's evidence-gated migration plan:

- **Phase 1 (lowest risk, immediately actionable):** promote the shape-topology scorer and the formalized population-based confidence-estimation module as purely informational additions — zero change to any gating logic or PASS/FAIL outcome. Both reuse code already built and validated read-only in Stages 13 and 14.
- **Phase 2 (medium complexity):** build the full Unified Candidate Pool from the Hough, segmentation, and contour/ellipse generators, and a real Quality Scoring module — gated on reproducing today's exact assignment across all 79 cartridges before promotion.
- **Phase 3 (topology-aware detector):** the Channel-context analysis module — the highest-value, highest-complexity module, directly targeting the Stage 16 anchor-error root cause. Requires its own dedicated investigation into channel/line segmentation reliability before being trusted with any assignment influence.
- **Phase 4 (conditional):** a machine-learning detector, pursued only if Phases 1–3 leave cartridges unresolved where real Leica ground truth proves a genuine hole exists, and only after expanding Leica ground-truth coverage beyond the current two cartridges.
- **Independent of the above:** obtain Leica reference data for Cartridges 49, 66, and 72 (currently absent, per Stage 15) to extend ground-truth-based validation beyond Cartridge 48; and investigate the 34-50/WB(2) dataset batch's broader image-quality condition as its own imaging/illumination project, separate from the detection algorithm.

Per Stage 18 §8, this future work should be scoped and resourced as a new research and development effort, not as a continuation of the current defect-remediation project.

---

## 13. Conclusion

This investigation applied a consistent, evidence-first engineering discipline across eighteen stages: fix confirmed defects first, design and exhaustively validate genuine algorithm improvements second, and — critically — continue investigating with independent methodologies even after the "easy" fixes were exhausted, rather than declaring victory prematurely or assuming the remaining failures must be fixable with more effort.

Two production changes were implemented, each validated against the complete 79-cartridge dataset without exception, each proven additive and non-regressive by direct comparison rather than assumption. Eight subsequent investigations each targeted a specific, falsifiable hypothesis for the remaining failures and each concluded, with direct quantitative and visual evidence, that the current architecture had reached the limit of what its information model — Hough circles, radial edge-hit counts, a single linear geometric transform, and greedy assignment — can support. External ground truth (Stage 15) both confirmed real holes exist where the algorithm cannot find them and, together with a direct backward trace (Stage 16) and direct visual/topological analysis (Stage 17), identified precisely why: the architecture has no mechanism to represent shape topology or whole-part contextual layout, the two capabilities a human operator actually relies on.

The resulting recommendation (Stage 18) is not "more tuning" but a **new, modular architecture** — designed here, validated nowhere yet, and explicitly scoped as a new project rather than a continuation of this one. The current production system, as amended by the two validated changes documented in this whitepaper, is assessed as complete and releasable for its architecture generation.

---

*This whitepaper is a synthesis document. It reports no new findings beyond what Investigation Stages 2–18 already established, and every claim above traces to a specific report in `docs/`, cited inline. No production code was modified, and no commit was created, in the preparation of this document.*
