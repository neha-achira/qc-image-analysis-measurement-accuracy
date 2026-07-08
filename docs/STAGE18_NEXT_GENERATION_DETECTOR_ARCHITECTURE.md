# Stage 18 — Next-Generation Detector Architecture

**Status:** Design only. No production code modified. No commits created.
**Branch:** `stage18-next-generation-detector-design`
**Basis:** This is a synthesis document. It performs no new investigation and repeats no prior report's findings in detail — it treats every conclusion of Stages 5–17 as accepted evidence and builds forward from it. Citations below point back to the stage that established each fact.

---

## 1. Final Limitations of the Current Production Architecture

### Solved limitations (implemented, committed, validated)
- **Stage 1 single-role anchor restriction** — the original anchor search only ever tried the raw Tag-9 candidate as the anchor seed. Replaced with the role-generalized search that tries every candidate against every tag role (Stage 7, commit `9bdc97e`). Validated three times with identical results, full 79-cartridge regression clean.
- **No recovery for tags reachable but outside Stage 2's tolerance** — an additive, frozen-anchor recovery pass now searches a wider, quality-gated radius for any tag Stage 2 left unmatched (Stage 6, commit `23d6e93`). Gated on `fallback_mode=="normal"`, `near_nominal_ratio>=0.70`, `max_angular_gap<=40°` — proven not to introduce cross-tag contention in validation.

These are the only two production changes made across the entire investigation (Stages 5–17). Both are narrow, additive, and independently validated.

### Unavoidable image limitations
- Some cartridges (48, 49) contain **no high-confidence candidate anywhere in the image** — established via population statistics across all 79 cartridges (Stage 14: these cartridges account for 5 of the dataset's 6 total `fallback_mode=total_failure` cases). This is a property of the physical part/imaging conditions, not of the software.
- Surface scratches, grinding texture, and debris produce real, physically-present dark structures that are visually and metrically similar to genuine hole edges at low ray-hit counts (Stage 17, directly confirmed by visual inspection of Cartridge 48 Tags 1/3/6/9's assigned points).
- The camera's active imaging area does not always cover the full nominal part geometry; when anchor error is large, a predicted position can fall entirely outside the captured frame (Stage 16, Stage 17 — Cartridge 48 Tag 5).

### Architectural limitations (structural, not tunable)
- **Single fixed-anchor, linear-offset geometric model** (`REF_OFFSETS` from one anchor point) has no mechanism to self-correct or cross-check against anything else visible in the image. Stage 16 traced Cartridge 48's entire failure to one Stage-1 anchor choice, with no downstream stage able to revisit it.
- **Fixed-radius search windows** (600px Stage 2, 690px Recovery) are sized for the dataset's dominant near-1.0-confidence case (Stage 14) and are not robust to the anchor-error magnitudes seen in outlier cartridges.
- **No shape/topology evaluation anywhere in the pipeline.** The ray-cast metric counts radial edge crossings only; it has no way to check whether those crossings form a single closed convex curve. Stage 17 found a real, unused, high-scoring (35/36 hits) Hough candidate that is actually a set of parallel channel walls — a false-positive-prone mechanism with no current safeguard.
- **Candidate assignment is not the bottleneck.** Stage 9 replayed Hungarian assignment, maximum bipartite matching, global optimization, and geometric residual minimization against the exact same candidate pool and found none recovers the unresolved tags without regression or physically implausible geometry — proving the limitation is upstream of assignment.

### Unsupported feature classes
- **Channel-junction-adjacent circular features** (e.g., the ring-center feature confused with Tag 9 in Cartridges 66/72, Stage 7) — geometrically and visually similar to a real hole at the ray-cast level, but a different physical design element.
- **Large disc/boss/counterbore rim curvature** tangent to the nominal hole radius — Stage 17 found Cartridge 48's currently-"normal"-fallback Tag 4 candidate sits on the rim of a much larger, unrelated disc feature, not a small hole boundary.
- **Holes displaced beyond the imaged frame** by accumulated anchor error, with no current mechanism to detect that the search has walked off the physical part (Stage 16, Stage 17 — Tag 5).

---

## 2. Why the Current Architecture Has Reached Its Practical Limit

Each layer of Hough → Stage 1 → Stage 2 → Recovery has been independently stress-tested with a different methodology, and each has been shown to be at its ceiling using only the information it currently models:

| Layer | Stage that tested it | Method | Finding |
|---|---|---|---|
| Candidate generation | Stage 8 | Exhaustive parameter sweep (dp, param1/2, minDist, radius fractions) | No safe parameter change recovers missing candidates without new false positives elsewhere |
| Candidate assignment | Stage 9 | Replay with Hungarian, max bipartite matching, global optimization, geometric residual minimization | None recovers the unused candidate without regression or an implausible scale (~1.97×) |
| Reference geometry | Stage 10 | Best-fit similarity/affine transforms, residual analysis across multiple cartridges | `REF_OFFSETS` independently validated correct — not the source of error |
| Confidence threshold / match immutability | Stage 14 | Population-derived (541-tag) percentile-based replay, challenging only statistical outliers | Zero safe recoveries; the one candidate swap found is lateral, not a recovery |
| Root cause of remaining failures | Stage 16 | Direct backward trace of the committed pipeline | Traced conclusively to Stage 1's anchor selection, a single point estimate with no self-correction |
| What information is actually missing | Stage 17 | Direct visual/topological inspection of the exact pipeline coordinates | Shape topology and channel-network context — categories of evidence no current module computes at all |

This is not a tuning gap. Four independent optimization strategies (Stage 9), an independent geometric validation (Stage 10), an exhaustive parameter sweep (Stage 8), and a population-grounded statistical replay (Stage 14) all converge on the same conclusion using the same evidence: **the current architecture has extracted everything obtainable from the information it represents (Hough circle centers + radial edge counts + one linear geometric model).** Improving further requires new *kinds* of information — shape topology, multi-generator consensus, whole-part context — that no existing module is designed to produce or consume. That is a representational gap, not a calibration gap, and is why a next-generation architecture, rather than a further patch, is warranted.

---

## 3. Next-Generation Detection Architecture

```
Input
  ↓
Preprocessing
  ↓
┌─────────────────────────────────────────────────────────────────┐
│                 Candidate Generators (parallel, independent)     │
│  Hough circles │ Connected  │ Contour/  │ Shape     │ Channel-   │
│  (existing,    │ components │ ellipse   │ topology  │ context    │
│  unchanged)    │ (Stage 13) │ fitting   │ analysis  │ analysis   │
└─────────────────────────────────────────────────────────────────┘
  ↓
Unified candidate pool  (deduplicated, multi-generator metric vector per candidate)
  ↓
Quality scoring  (composite, evidence-derived, auditable — replaces stage2_rank_key)
  ↓
Global assignment  (existing greedy logic, enriched inputs — Stage 9 showed the algorithm itself is not the bottleneck)
  ↓
Measurement  (existing _subpixel_diameter, unchanged)
  ↓
Confidence estimation  (formalizes Stage 14's population-percentile approach as a standing module)
  ↓
PASS / FAIL  (existing LSL/USL logic, unchanged)
```

The design principle throughout: **every existing, validated component (Hough generator, `_subpixel_diameter`, LSL/USL decision, and by Stage 9's evidence, likely the assignment algorithm itself) is kept unchanged and additive components are inserted around it** — the same additive discipline already proven safe in Stages 6, 7, and 13.

---

## 4. Module-by-Module Specification

### Input (unchanged)
- **Purpose:** raw image ingestion. **Inputs:** image file path, image type. **Outputs:** raw BGR/gray array.
- **Interaction:** identical to today. **Benefit:** n/a. **Cost:** unchanged. **Complexity:** none. **Regression risk:** none.

### Preprocessing (re-exposed, not changed)
- **Purpose:** contrast normalization (CLAHE) and active-image-area determination, shared by every generator instead of only Hough.
- **Inputs:** raw grayscale. **Outputs:** normalized image, active-area bounds.
- **Interaction:** reuses the existing `get_active_area`/CLAHE logic verbatim; the only change is exposing the active-area mask to later stages so a prediction that falls outside it (as Tag 5 did) can be flagged immediately rather than discovered only via a downstream bounds check.
- **Benefit:** consistent input to all generators; earlier, clearer diagnosis of off-frame predictions.
- **Cost:** negligible (already computed today). **Complexity:** low. **Regression risk:** none.

### Generator 1 — Hough circles (existing, unchanged)
- **Purpose:** the current, sole production generator, kept exactly as-is.
- **Interaction:** zero change — this is the one component proven safe across the full 79-cartridge dataset (Stage 2 external validation) and remains the backbone.
- **Benefit:** continuity; zero regression risk by construction. **Cost:** unchanged. **Complexity:** none. **Regression risk:** none — untouched.

### Generator 2 — Connected components / adaptive threshold (Stage 13's `segment_candidates`)
- **Purpose:** find candidates via intensity segmentation rather than gradient/accumulator voting, catching holes with low Hough response but a coherent connected dark region.
- **Inputs:** preprocessed grayscale. **Outputs:** centroid, area, perimeter, circularity, solidity, aspect_ratio, equivalent_diameter, edge_strength — the exact metric set already defined and read-only-validated in Stage 13.
- **Interaction:** purely additive; feeds the new Unified Candidate Pool, not the existing Stage 1/2/Recovery logic directly.
- **Benefit:** Stage 13 already demonstrated this generator surfaces legitimate candidates the current pipeline misses; in this redesign, deferring matching to a later unified stage (rather than Stage 13's constraint of only acting on already-unmatched tags) lets these candidates actually compete for assignment.
- **Cost:** moderate (one extra thresholding + labeling pass per image). **Complexity:** low — code already exists and was validated. **Regression risk:** low, provided it remains additive to the pool and never overrides Hough's own candidates.

### Generator 3 — Contour analysis / ellipse fitting
- **Purpose:** characterize local shape directly — contour closure, convexity, fitted-ellipse residual — the shape-topology gap Stage 17 identified as the #2-ranked missing cue.
- **Inputs:** preprocessed grayscale (or the binary mask from Generator 2). **Outputs:** closed-contour ratio, convexity-defect count, ellipse center/axes/angle, fit residual.
- **Interaction:** can run as a standalone generator or as a scoring pass over existing candidates; either way it is consumed at Quality Scoring, where the Stage 17 channel-wall false positive (candidate with 35/36 Hough hits that is actually parallel channel walls) would finally be caught.
- **Benefit:** directly closes an evidenced gap, not a hypothetical one. **Cost:** low-moderate (cv2 contour/ellipse operations are cheap). **Complexity:** moderate — needs validation against holes of varying quality, not only clean cases. **Regression risk:** low if used as an informational score, per Stage 13's established principle of justifying gates only with measured evidence.

### Generator 4 — Shape topology analysis
- **Purpose:** a dedicated module (distinct from raw contour fitting) that answers two specific questions raised by Stage 17: (a) does this region form a simple, self-contained closed boundary (vs. an open curve, a channel wall, or a scratch)? (b) is the local curvature radius consistent with a nominal tag hole, or does it belong to a much larger structure (the Tag 4 disc-rim finding)?
- **Inputs:** candidate location + local image patch. **Outputs:** closed-region signal, scale-consistency signal.
- **Interaction:** informational scoring input only, consumed at Quality Scoring.
- **Benefit:** the single module most directly targeted at the two concrete false-positive mechanisms this investigation actually found (C24's channel walls, Tag 4's disc rim) — both evidenced in Stage 17, not hypothesized.
- **Cost:** low. **Complexity:** moderate — the scale-consistency baseline must itself be measured from the population (per this project's standing no-invented-threshold discipline), not assumed. **Regression risk:** low as an informational score; would become the highest-risk module in the whole design if ever promoted to a hard gate without population-level validation equivalent to Stage 14's.

### Generator 5 — Channel-context analysis
- **Purpose:** implement Stage 17's **#1-ranked** missing cue — use the visible channel network's topology to constrain or cross-check hole locations, independent of the single fixed-anchor arithmetic model that Stage 16 proved is the actual root cause of Cartridge 48/49's failures.
- **Inputs:** preprocessed grayscale, a channel/line segmentation (thin elongated dark structures, separable from round structures by aspect ratio), the existing candidate pool.
- **Outputs:** per-candidate channel-connectivity descriptor (is this candidate at a channel terminus, junction, or bend?), and potentially an independent, non-arithmetic layout hypothesis for cross-checking the anchor-derived prediction.
- **Interaction:** contributes scoring/context facts into the Unified Candidate Pool; does not generate new circular candidates itself.
- **Benefit:** the only module in this design that targets the actual root cause identified in Stage 16 (anchor localization error) rather than a downstream symptom — highest expected impact of any module proposed here.
- **Cost:** highest of all modules — reliable channel/line segmentation on textured, scratched images (the image-quality range documented in Stage 11) is itself a nontrivial CV problem.
- **Complexity:** highest — this is a research-grade module, not a straightforward extension. **Regression risk:** low to the existing pipeline (additive/informational only), but highest risk of producing an unreliable signal if channel segmentation itself is not robust across the dataset's established image-quality variance.

### Unified candidate pool
- **Purpose:** merge all generators' outputs into one deduplicated pool, spatially clustering near-duplicate detections from different generators into a single candidate record carrying every generator's metrics.
- **Inputs:** candidate lists from Generators 1–5. **Outputs:** one candidate list with a full multi-generator metric vector per entry.
- **Interaction:** a genuinely new stage, inserted between generation and the existing Stage 1/2/Recovery logic, which would consume this pool instead of the raw Hough-only list.
- **Benefit:** every downstream stage gains access to the richest available evidence per candidate instead of today's single Hough+ray-cast metric.
- **Cost:** moderate (deduplication/clustering logic). **Complexity:** moderate. **Regression risk:** moderate — this is the first stage capable of altering production's numeric output on currently-passing cartridges, and requires the same full-dataset blast-radius discipline Stage 7 applied to the anchor redesign before any promotion.

### Quality scoring
- **Purpose:** replace today's single `(fallback_rank, n_hit, near, -distance)` tuple with a documented, multi-signal, evidence-derived score incorporating the new topology/channel-context signals, following Stage 14's population-derived (not invented) threshold discipline.
- **Inputs:** unified candidate pool. **Outputs:** per-candidate composite score, kept decomposable/auditable rather than collapsed into one opaque number.
- **Interaction:** replaces `stage2_rank_key` — the single highest-impact point of change in this entire design.
- **Benefit:** the mechanism that actually lets the new modules influence real decisions, not just diagnostics.
- **Cost:** low once metrics exist. **Complexity:** moderate-high. **Regression risk:** highest in the design — must reproduce today's rank order on every one of the 79 cartridges before being trusted, with the same zero-regression bar Stages 6, 7, 9, and 14 all required before touching production.

### Global assignment
- **Purpose:** assign scored candidates to the 7 tag roles.
- **Inputs:** scored unified pool, `REF_OFFSETS` (kept unchanged — validated correct, Stage 10), optional channel-context layout hypothesis.
- **Interaction:** Stage 9 already proved that changing the *assignment algorithm* alone (Hungarian, bipartite, global optimization) does not help while the candidate pool and geometric model are held fixed — so this design's expected benefit comes entirely from richer inputs, not a different optimizer. **The existing greedy logic can most likely remain unchanged**; Stage 9's evidence argues against investing in a new assignment algorithm here.
- **Benefit:** inherits whatever the enriched pool and channel-context hypothesis provide. **Cost:** unchanged from today. **Complexity:** low (reuse existing/committed logic). **Regression risk:** low if the algorithm itself stays untouched and only its inputs are enriched.

### Measurement (unchanged)
- **Purpose:** `_subpixel_diameter`, the one production function every stage of this investigation has treated as ground truth. No change proposed anywhere in this design.
- **Regression risk:** none.

### Confidence estimation
- **Purpose:** formalize what Stage 14 built as a one-off analysis (population-derived percentile ranking) into a standing, refreshable module that reports a calibrated confidence alongside every measurement, rather than only a binary ray-cast pass/fail.
- **Inputs:** final assignment, full multi-generator metric vector, maintained population statistics (refreshed the way Stage 14's percentile table was built). **Outputs:** a confidence score per tag, intended to flag (not gate) low-confidence PASS results for manual/Leica review.
- **Interaction:** new; sits between assignment/measurement and the final decision. Does not alter the PASS/FAIL threshold itself.
- **Benefit:** turns the silently-accepted low-confidence PASS results documented at Cartridge 48 Tags 3/6/9 (Stage 17) into a visible, actionable signal, without changing any measured value.
- **Cost:** low. **Complexity:** low-moderate. **Regression risk:** low — purely additive metadata.

### PASS/FAIL (unchanged)
- **Purpose:** existing LSL/USL comparison. No change proposed.

---

## 5. How Leica Data Should Be Used

Leica is not a detector and is not proposed as one anywhere in this design (consistent with the Stage 12/15 correction that Leica is an external, human-operated measurement workflow, not a reverse-engineerable algorithm). Its role is exclusively as ground truth for evaluating this project's own software, in four specific places:

1. **Detector validation:** any new generator or scoring module's output on Cartridges 48 and 61 (the only cartridges with real Leica data, per Stage 15) can be checked directly against Leica's PASS/FAIL and diameter table, exactly as Stage 15 did. Before trusting any new module broadly, Leica data should be **acquired for a wider cartridge sample** — Stage 15 explicitly found no Leica reference exists today for Cartridges 49, 66, or 72, which limits how far this validation currently reaches.
2. **Threshold calibration:** the ~0–8% production-vs-Leica diameter variance established in Stage 15 (via the Cartridge 61 control) should serve as the reference band for judging whether a new module's measurement agrees with Leica within normal system-to-system noise — not for setting the manufacturing PASS/FAIL spec itself, which is a separate, fixed engineering tolerance (0.45–0.55mm).
3. **Confidence evaluation:** use Leica agreement/disagreement as one input (not the sole input) when validating the new Confidence Estimation module — e.g., checking whether tags the module flags as low-confidence correlate with larger production-vs-Leica discrepancies, wherever Leica data exists.
4. **Regression testing:** every Leica-confirmed hole currently available (Cartridge 48 Tags 1, 3, 4, 5, 6, 7, 9; Cartridge 61 all seven tags) should become a **permanent regression fixture**. Every future architecture change must reproduce these known-correct outcomes before being considered non-regressive — extending this project's existing full-79-cartridge regression discipline (Stages 2, 6, 7) to include real external ground truth wherever it exists.

---

## 6. Migration Plan

**Phase 1 — smallest production-safe improvement.**
Add the Shape Topology module and the formalized Confidence Estimation module as purely informational additions to existing candidate/measurement records — zero change to any gating logic, zero change to any PASS/FAIL outcome. This is Stage 17's own recommendation, and directly reuses Stage 13's segmentation code and Stage 14's population-statistics approach, both already built and validated read-only in this investigation. Lowest risk, immediately actionable.

**Phase 2 — medium-complexity detector additions.**
Fully build the Unified Candidate Pool from Generators 1–3 (Hough, connected-components/Stage-13 segmentation, contour/ellipse fitting), and build the real Quality Scoring module on top of it. Required gate before promotion: reproduce today's exact assignment on all 79 cartridges (zero regression), following the same discipline Stage 7 applied to the anchor redesign.

**Phase 3 — topology-aware detector.**
Build Generator 5, Channel-context analysis — the highest-value, highest-complexity module, targeting the Stage 16 root cause directly. This phase requires its own dedicated investigation into channel/line segmentation reliability across the image-quality range Stage 11 already documented, before this module is trusted to influence any assignment decision.

**Phase 4 — optional machine-learning detector.**
Only pursued if Phases 1–3 (entirely classical CV, entirely evidence-grounded) still leave cartridges unresolved where real Leica ground truth proves a genuine hole exists. A learned classifier or keypoint detector should be a last resort specifically because every module proposed in Phases 1–3 traces to a concrete, evidenced gap from Stage 17; introducing machine learning without an equally specific evidenced justification would break this project's standing discipline of never proposing a change beyond what evidence supports. This phase would also first require expanding Leica ground-truth coverage well beyond the current two cartridges, since a learned model needs a labeled dataset this project does not yet have.

---

## 7. Risk Assessment

| Module | Could affect | How to validate | How to prevent regressions |
|---|---|---|---|
| Preprocessing (re-exposed) | Nothing (reuses existing function) | N/A | N/A |
| Generator 2 (segmentation) | Unified pool composition only, if built correctly | Compare candidate counts/positions against Stage 13's already-validated read-only results | Never let it write to or override Hough's existing candidate list; additive only |
| Generator 3/4 (contour/topology) | Quality Scoring inputs | Check topology scores against the concrete cases already found (C24 channel-wall, Tag 4 disc-rim) plus a sample of genuine holes across image-quality tiers (Stage 11's classes) | Keep as informational score only until validated at population scale (Stage 14 precedent) |
| Generator 5 (channel-context) | Anchor/assignment decisions, if ever promoted beyond informational | Requires its own investigation into channel-segmentation reliability before any promotion | Never let it override the anchor unless independently validated across the full dataset; treat as a cross-check signal, not a replacement, until proven |
| Unified candidate pool | Every downstream stage's inputs | Full 79-cartridge regression: every currently-passing tag must still resolve to the same candidate | Deduplication logic must be conservative — prefer keeping Hough's original candidate identity over merging away information |
| Quality scoring | Assignment order/outcome for every cartridge | Full 79-cartridge regression required to reproduce current rank order before promotion; Stage 14's zero-regression bar applies | Roll out only after matching current production output exactly on the full dataset; keep the score decomposable so any regression is traceable to one signal |
| Global assignment | Low — Stage 9 already showed algorithm choice is not the bottleneck | Re-run Stage 9's comparison (greedy vs. Hungarian vs. bipartite vs. global optimization) on the enriched pool to confirm the finding still holds | Keep existing greedy logic unless new evidence (not present today) shows otherwise |
| Measurement, PASS/FAIL | None — unchanged | N/A | Not modified in this design |
| Confidence estimation | Reporting/flagging only | Validate against Leica agreement wherever available (Stage 15 data) | Never let it gate PASS/FAIL, only annotate |

---

## 8. Final Recommendation

**A. The current production system, as amended by the two validated changes from this investigation (Stage 7's role-generalized anchor search, Stage 6's recovery pass), should be considered complete for release within its current architectural generation.** Every avenue for further improvement inside the existing Hough + Stage 1 + Stage 2 + Recovery architecture has been tested with independent, rigorous methodology — parameter sweep (Stage 8), four alternative assignment strategies (Stage 9), independent geometric validation (Stage 10), population-grounded confidence replay (Stage 14) — and each was found to be at its evidenced limit, not merely under-tuned. Shipping the current system is supported by evidence, not by an absence of further ideas.

**B. Everything designed in this report belongs to a new research and development effort, not a continuation of the current project's bug-fixing scope.** The remaining gap (Stage 16's root cause, Stage 17's missing cues) requires new categories of information — multi-generator fusion, shape topology, whole-part channel-context reasoning — that the current architecture was never designed to represent. This is a different kind of work: building new detection capability, not correcting a defect in existing capability. It should be scoped, staffed, and resourced as such, following the phased migration plan above, starting from Phase 1's low-risk, already-prototyped additions.

No production code was modified in the preparation of this document. No commits were created. Stopping here per your instruction.
