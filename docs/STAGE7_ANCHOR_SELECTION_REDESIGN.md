# Stage 7 — Replacement Stage 1 Anchor-Selection Design

**Status:** Design document only. Nothing in this document has been implemented. No production code has been modified.
**Branch:** `stage7-geometric-model-investigation` (no commits).
**Basis:** `STAGE7_GEOMETRIC_MODEL_INVESTIGATION_REPORT.md` (root cause), `STAGE7_CARTRIDGE72_ROOT_CAUSE_TRACE.md` and `STAGE7_CARTRIDGE72_VERIFICATION_REPORT.md` (independently verified mechanism).

This document evaluates candidate replacements for Stage 1's anchor-selection algorithm. Per your instructions: no approach here relies on anything specific to Cartridge 72 (all use only candidate positions and candidate-quality metrics already available at Stage 1 time, i.e. before Stage 2, the recovery pass, or the missing-hole diagnostics run); all are designed to preserve existing behavior on the 78 already-validated cartridges unless a specific approach's own analysis shows a clear, low-risk improvement; nothing here has been implemented or tuned.

---

## 1. Current Algorithm (baseline, for reference)

```
for anchor_candidate in detected:
    matched = {}
    for tag in REF_OFFSETS:                      # tag is ALWAYS assumed = anchor_candidate's role
        px, py = anchor_candidate + REF_OFFSETS[tag]
        best = nearest unused candidate to (px,py) within MATCH_TOL_PX(600px)
        if best found: matched[tag] = best
    score = len(matched)
    keep anchor_candidate if score > best_score_so_far   # strict >, first-found wins ties
```

Three properties of this algorithm are the direct cause of the Cartridge 72 failure, established in the prior reports:

1. **Single fixed role assumption.** Every candidate is only ever tried *as Tag 9* (offset (0,0)). It is never tried as Tag 1, Tag 3, etc. If no candidate exists near the true Tag 9 position — as verified for Cartridge 72 — no hypothesis in this search space can ever be correct, regardless of how many other genuine holes are present.
2. **No use of candidate quality.** Ray-cast quality (`n_hit`, `near_nominal_ratio`, `angular_gap`, `fallback_mode`) is computed before Stage 1 runs (during candidate ray-casting) but is not read anywhere in this loop. A candidate sitting on plain texture (Cartridge 72's false anchor: 9/36 hits, 11.1% near-nominal, 280° angular gap) is scored identically to a perfect 36/36 detection.
3. **No tie-break beyond iteration order.** Ties in match count are resolved only by which candidate Hough happened to list first — an accident of `HoughCircles`' internal ordering, not a deliberate decision.

Any replacement must address (1) directly to fix the established root cause. (2) and (3) are not required to fix Cartridge 72, but are relevant to the broader request ("preserve behavior... unless strong evidence of improvement" implies also improving *robustness* against as-yet-unseen analogous cases, not merely patching the one instance already found).

**Notation used below:** N = number of raw Hough candidates for a cartridge (observed range across all validated data: 13–33). All complexity figures are with respect to N; at these values every approach below runs in well under a second, so wall-clock cost is not a meaningful differentiator — design/validation complexity and blast radius are the load-bearing comparison criteria.

---

## 2. Approach 1 — Quality-Weighted Anchor Scoring

**Algorithm.** Generalize the trial loop to try each raw candidate against each of the 7 tag roles (not only Tag 9): for candidate C and role T, the implied anchor is `C − REF_OFFSETS[T]`. Score exactly as today (greedy nearest-in-tolerance match count, unchanged). Among hypotheses tied on match count, break the tie using candidate-quality information already available: rank by (a) the anchor candidate's own `fallback_mode` (normal > off_nominal_fallback > total_failure), then (b) its `near_nominal_ratio`, then (c) the negative sum of matched-tag distances (prefer the geometrically tighter fit), then (d) role = 9 preferred last (preserves today's exact choice on a total tie).

Two sub-variants:
- **1a — quality as pure tie-break** (only activates when match counts are exactly equal): zero effect on any cartridge with a unique highest-scoring hypothesis.
- **1b — quality blended into the primary score** (e.g., `score = match_count·K − quality_penalty`): could in principle let a lower-count-but-high-quality anchor beat a higher-count-but-low-quality one. **Not recommended** — it changes behavior even in non-tied cases, and calibrating `K` and the penalty function would require its own dedicated empirical validation (in the spirit of the Stage 6 quality-gate validation) before it could be trusted. Included here for completeness only.

**Computational complexity.** O(7 candidates-as-roles × 7 tags × N nearest-neighbor lookups) = O(49N²) for the generalized trial loop (worst case; in practice most (candidate, role) pairs score 0–1 and exit early). Quality metrics are already computed; no new per-candidate cost. Negligible in absolute terms (tens of thousands of operations at N=25).

**Regression risk (variant 1a, recommended).** Low. The existing scoring function and tolerance are completely unchanged; only the search space of "what could this candidate represent" is widened, and the tie-break only ever activates when today's algorithm would otherwise depend on arbitrary Hough-internal ordering — a case with no well-defined "correct" behavior to preserve in the first place. Requires validation (see §7) that no other cartridge in the 78 has a second (candidate, role) pair that *also* reaches the maximum score of 7 through a genuinely different assignment — expected not to occur, given the minimum pairwise predicted-tag distance (1393.9px) is more than double the 600px tolerance, but not yet exhaustively proven for every cartridge's specific point set.

**Expected effect on Cartridge 72.** With role-generalization: any of the 6 genuine, high-quality holes (Tags 1,3,4,5,6,7) can now serve as the pivot, achieving 6/7 correctly-identified tags (Tag 9 still correctly reported missing, since its own location still has no valid Hough candidate). This directly resolves both problems found in the verification report: Tag 6 would no longer show Tag 3's hole, and Tag 7 would no longer show a low-quality substitute — each would be independently and correctly matched via its own genuine candidate.

**Expected effect on validated datasets.** None expected. In every one of the 78 other cartridges, the true Tag 9 candidate already achieves the maximum possible score (7/7) under today's restricted search; widening the search cannot produce a *higher* score, only a possible tie, and the tie-break is designed to prefer today's exact outcome when genuinely tied. Must be confirmed by full regression, not assumed.

**Failure modes.** (i) A coincidental tie between the correct anchor and a spurious one on some not-yet-seen cartridge, if the tie-break's secondary keys are also equal — mitigated by the role=9-preferred-last rule, but not eliminated in the absolute pathological case. (ii) This approach alone does not prevent a *future* Cartridge-72-like case where a low-quality candidate achieves the outright highest count (not merely a tie) via coincidental proximity to several unrelated real holes — variant 1a's tie-break cannot help here since there is no tie; only Approach 4's residual check (below) addresses this class of failure.

---

## 3. Approach 2 — Consensus-Based Anchor Selection (2-point RANSAC)

**Algorithm.** For every ordered pair of raw candidates (Ci, Cj) and every ordered pair of reference tags (Ta, Tb), solve the unique similarity transform (scale + rotation + translation) that maps Ta→Ci and Tb→Cj. Apply this transform to all 7 reference tag positions and count how many *other* raw candidates fall within a tight consensus tolerance (much smaller than 600px, since a genuine fit should produce single-digit-to-low-tens-of-pixels residuals per the RMS values already established for both Cartridge 72's real holes and the Cartridge 1 baseline). Keep the (pair, tag-pair) hypothesis with the highest consensus count, then re-fit the transform by least squares using all inlier correspondences, and derive the anchor from the refined fit.

This is the same methodology used (successfully) in this investigation's own independent analysis to discover Cartridge 72's true geometry.

**Computational complexity.** O(N² pairs × 42 ordered tag-pairs × N consensus-count) = O(42N³). At N=25 this is ~656,000 operations — still sub-second, but a higher asymptotic class than Approach 1, and meaningfully more code (transform solving, consensus counting, least-squares refit) than a nested loop.

**Regression risk.** **Higher than Approach 1.** This approach fundamentally changes the matching model from pure translation to full similarity transform (rotation + scale + translation). Every downstream consumer of the anchor (`_predict_positions`, Stage 2 ranking, the recovery pass, missing-hole diagnostics) currently assumes a pure-translation model; introducing rotation/scale correction at Stage 1 would require re-deriving or re-validating all of them, a substantially larger blast radius than Approach 1's isolated change to the anchor-trial loop alone. It also introduces two new free parameters (consensus tolerance, minimum inlier count) that would need their own dedicated empirical validation before being trusted, following the same practice used for the Stage 6 quality gate.

**Expected effect on Cartridge 72.** Would very likely succeed — this is the exact mechanism that independently confirmed Cartridge 72's true geometry (scale 0.9973, rotation −0.738°, RMS 6–7px) in this investigation.

**Expected effect on validated datasets.** Plausibly neutral to positive (the fit should reduce to a near-identity transform for well-behaved cartridges, per the Cartridge 1 baseline comparison already measured: 5.8–5.9px RMS), but this cannot be asserted with the same confidence as Approach 1, since the mechanism itself is different from today's, not merely a widened search over the same mechanism. Requires the same full regression, plus new validation specific to the transform-fitting parameters.

**Failure modes.** Spurious two-point pairings can occasionally achieve deceptively strong consensus by chance, especially on cartridges with few candidates (as few as 13 observed); the consensus tolerance and minimum-inlier-count parameters both need calibration against real data, similar in spirit to (and in addition to) the work already done for the Stage 6 recovery-pass quality gate. Larger surface area for subtle implementation bugs given the additional geometry (rotation solving, least-squares refit).

---

## 4. Approach 3 — Graph / Voting Approaches

Two closely related variants:

**3a — Consistency graph / clique search.** Build a graph whose nodes are raw candidates. Connect two candidates with an edge if their pairwise distance is consistent (within tolerance) with the pairwise distance between *some* pair of reference tags. Find the largest mutually consistent labeling (each candidate assigned at most one tag, no two edges implying contradictory tag identities) — effectively a maximum-clique/consistent-labeling search over the candidate set. This is the graph formalization of the brute-force shape-matching this investigation used manually to establish Cartridge 72's ground truth.

**3b — Hough-style voting accumulator.** For every candidate C and every tag role T (same hypothesis space as Approach 1's generalization), compute the implied anchor position and accumulate a vote in a coarse anchor-position grid (bin size on the order of the match tolerance). The most-voted bin (optionally weighted by candidate quality) becomes the anchor, refined by averaging or re-fitting the votes within it.

**Computational complexity.** 3a: building the consistency graph is O(21 tag-pairs × N²); finding the best consistent labeling is combinatorially harder in the worst case (subgraph-consistency / clique-style problems are NP-hard in general), but tractable in practice at N≤33 given the geometric pruning available (as demonstrated by this investigation's own scripts, which ran in seconds). 3b: O(7N) to build the accumulator, plus one O(7N) match-scoring pass for the winning bin — the cheapest of all approaches considered, computationally.

**Regression risk.** **Higher than Approach 1, comparable to or higher than Approach 2.** 3a carries the added burden of a combinatorial-search algorithm that is harder to reason about, review, and maintain than a simple nested loop — a real cost even where raw runtime is acceptable. 3b introduces a new, previously-nonexistent free parameter (bin size) whose choice directly affects behavior; poorly chosen bin boundaries could cause a currently-correct cartridge's anchor to be computed as a slightly different (though nearby) position purely from binning/rounding artifacts, a form of regression risk that doesn't exist in Approach 1 at all (which reuses the exact existing distance-based tolerance mechanism with no discretization).

**Expected effect on Cartridge 72.** Both variants would very likely succeed, by the same reasoning as Approach 2 — this problem space is exactly what these methods are designed to solve, and this investigation's own manual application of essentially this method (3a) is what discovered Cartridge 72's ground truth in the first place.

**Expected effect on validated datasets.** Plausibly neutral for 3a for the same structural reasons as Approach 2 (clean point sets should form an unambiguous consistent labeling). 3b's expected effect is harder to characterize without empirically choosing and validating a bin size — this is a genuine open question, not a confident expectation.

**Failure modes.** 3a: combinatorial blow-up or ambiguous ties in pathological candidate configurations (not observed in the validated data so far, but not ruled out either, particularly on cartridges with unusually high candidate counts). 3b: bin-boundary artifacts; a genuine anchor whose implied position happens to straddle a bin edge could be split across two bins and lose votes to a spurious concentration elsewhere — a failure mode with no analogue in Approach 1.

---

## 5. Approach 4 — Geometric Consistency Scoring (residual-based)

**Algorithm.** Do not change the anchor-trial loop's search space (keep either the current Tag-9-only search, or Approach 1's generalized 7-role search — this approach is a scoring refinement, not a search-space change, so it composes with either). For every hypothesis that reaches at least some minimum match count (e.g., ≥ 4, matching the minimum this codebase already requires elsewhere — see the recovery-pass quality gate's own precedent — or ≥ 6 given Cartridge 72's demonstrated 6/7 ceiling), additionally fit a similarity transform to the matched set and compute its RMS residual. Use this RMS as a secondary ranking signal: among hypotheses with the same (or similar) match count, prefer the one with the tighter residual; optionally, reject a hypothesis outright if its residual is anomalously large (e.g., an order of magnitude beyond the ~6–17px range already observed across every validated cartridge fit in this investigation, including deliberately poor fits), since a large residual for a "matched" set indicates the matches are individually within tolerance but not collectively self-consistent — precisely the situation identified in the verification report (Tag 6 and Tag 7's current assignments are each individually within the naive tolerance of their own wrong predicted position, but the resulting 3-tag set, including the false anchor, is not a tight geometric fit at all).

**Computational complexity.** For each candidate hypothesis meeting the minimum match count, one similarity-transform fit (closed-form SVD solve) over at most 7 points — O(1) per hypothesis, negligible addition to whichever search-space approach it is paired with.

**Regression risk.** Low to moderate, depending on whether it is used as a tie-break (low risk, same reasoning as Approach 1a) or as an outright rejection filter (moderate risk — requires establishing, from real data, what residual threshold reliably separates "genuinely tight fit" from "coincidentally in-tolerance but not self-consistent," analogous to the empirical work already done to validate the Stage 6 quality gate's `near_nominal_ratio`/`angular_gap` thresholds before they were trusted).

**Expected effect on Cartridge 72.** If paired with Approach 1's role generalization: strongly positive — the correct 6-tag hypothesis has an RMS of 6–7px (established), while the current false-anchor hypothesis's 3-tag set (including two now-known-wrong assignments) would show a much larger residual once actually computed, giving this approach an additional, independent signal (beyond raw match count) confirming the correct hypothesis. If NOT paired with role generalization (kept restricted to Tag-9-only trials): no effect, since no Tag-9-role hypothesis for Cartridge 72 ever reaches the minimum match count needed to compute a meaningful residual in the first place.

**Expected effect on validated datasets.** Expected neutral to positive: the RMS values already measured for a normal, fully-matched cartridge (Cartridge 1: 5.8–5.9px) and for Cartridge 72's own genuine 6-tag subset (6.3–7.0px) are close enough that a reasonably-chosen threshold should not disturb any currently-correct case — but, as with Approach 2/3, this expectation should be confirmed by computing this residual for all 78 validated cartridges' actual winning anchors before relying on it, not assumed.

**Failure modes.** A cartridge with genuinely poor imaging (soft focus, low contrast) could show a real, correct anchor with a naturally larger residual than the clean cases observed so far — an outright rejection filter (rather than a tie-break) risks discarding a correct-but-noisy anchor if the threshold is set too aggressively without broader validation across more imaging conditions than the 79 cartridges analyzed to date.

---

## 6. Approach 5 — Hybrid (Recommended)

**Algorithm.** Combine the minimum necessary structural fix with the lowest-risk robustness refinements identified above:

1. **Generalize the anchor-trial loop to all 7 tag roles** (Approach 1's core mechanism) — this is the only change that is *necessary* to resolve the established root cause; every other refinement is optional robustness on top of it.
2. **Tie-break by candidate quality, not blended into the primary score** (Approach 1a specifically, not 1b) — activates only on genuine ties, so it cannot change any currently-unique outcome.
3. **Use geometric residual (Approach 4) as a further tie-break level, after quality and before the role=9-preferred-last fallback** — provides an additional, independent, well-evidenced signal (this investigation's own RMS numbers) to prefer the tighter-fitting hypothesis in the rare case that match-count and candidate-quality are both tied.
4. **Explicitly do not adopt** Approach 2 or 3's transform-fitting/graph/voting machinery as the core search mechanism — their larger blast radius (touching the pure-translation assumption baked into `_predict_positions` and everything downstream) and additional untested free parameters are not justified when Approach 1's much smaller, better-understood change already resolves the established root cause completely.

This is "hybrid" in the sense the prompt requested: it takes the necessary structural idea from the multi-role search, the low-risk half of the quality-weighting idea, and the low-risk half of the geometric-consistency idea, while deliberately declining the higher-blast-radius mechanisms (full consensus/RANSAC, graph search, voting accumulation) that would also work but cost more to validate and maintain for no established additional benefit over the current evidence.

**Computational complexity.** Same order as Approach 1 (O(49N²) worst case, trivial in absolute terms), plus O(1) per surviving tie for the residual computation.

**Regression risk.** Low — each layer only activates in circumstances (ties) that have no well-defined "correct" existing behavior to disturb in the first place; the core mechanism (widened search space, unchanged scoring function and tolerance) is the smallest possible change that addresses the root cause.

**Expected effect on Cartridge 72.** Same as Approach 1 alone (6/7 correctly matched, Tag 9 correctly reported missing), with the additional tie-break layers providing no *change* to this specific outcome (there is no tie to break here — the correct hypothesis is the unique highest scorer once the role search is widened) but adding defense-in-depth against structurally similar future cases.

**Expected effect on validated datasets.** Same expectation as Approach 1 (no change), to be confirmed by the same full regression before any implementation.

**Failure modes.** Inherits Approach 1's residual failure mode (a future cartridge where a low-quality candidate wins outright, not merely ties) somewhat more than Approach 2/3 would, since this design deliberately avoids their more powerful (but more invasive) correspondence-finding machinery. This is an accepted trade-off, not an oversight: the goal here is the *safest* design that resolves the *established* problem, not the most powerful design against hypothetical future problems not yet observed in any of the 79 validated cartridges.

---

## 7. Ranking and Recommendation

| Approach | Fixes Cartridge 72 | Regression risk | Blast radius | New parameters | Design/validation complexity |
|---|---|---|---|---|---|
| **1 — Quality-weighted (1a, tie-break only)** | Yes, once role-generalized | Low | Small (anchor-trial loop only) | None | Low |
| **5 — Hybrid (recommended)** | Yes | Low | Small (anchor-trial loop only) | None | Low–Moderate |
| **4 — Geometric consistency (standalone)** | Only if paired with role generalization | Low (tie-break) / Moderate (filter) | Small–Moderate | 1 (residual threshold, if used as filter) | Moderate |
| **2 — Consensus/RANSAC** | Yes | Moderate–High | Large (changes core matching model) | 2 (consensus tolerance, min inliers) | High |
| **3a — Graph/clique** | Yes | Moderate–High | Large | 1+ (consistency tolerance) | High (combinatorial algorithm) |
| **3b — Voting accumulator** | Likely yes | Moderate | Moderate | 1 (bin size) | Moderate–High |
| 1b — Quality-blended (not recommended) | Yes, once role-generalized | Moderate (changes non-tied cases) | Small | 1+ (blend weights) | Moderate |

**Recommendation: Approach 5 (Hybrid).** It resolves the established root cause with the smallest possible change to the existing, well-understood algorithm (a widened search space over the *same* scoring function and tolerance already in production), introduces no new free parameters that would themselves require dedicated empirical validation before being trusted, and adds two extra layers of defense (quality tie-break, residual tie-break) that can only ever improve robustness in genuinely ambiguous cases, never destabilize an already-unique outcome. Approaches 2 and 3 are not ruled out as eventually valuable — the residual/consensus-based reasoning they embody is exactly what independently confirmed Cartridge 72's root cause in this investigation — but they represent a materially larger, riskier change than is currently justified given that Approach 5 already fully addresses every failure mode established so far.

---

## 8. Required Validation Before Any Implementation (not performed here)

Per your instruction, nothing in this document has been implemented. Before Approach 5 (or any approach) could be considered for implementation, the following would need to be run and reported, consistent with this project's established methodology:

1. Full replay of the proposed algorithm across all 79 cartridges (1–33, 34–50, 51–60, 61–70(1), 71–79), confirming the anchor selected for all 78 non-Cartridge-72 cartridges is byte-identical in outcome (same matched candidates, positions, measurements, PASS/FAIL) to today's production output.
2. Explicit confirmation, for every one of those 78 cartridges, of whether any *tie* actually occurs under the widened 7-role search (expected: none, but not yet checked) — if any tie is found, manual review of whether the tie-break rule resolves it to the currently-correct outcome.
3. Cartridge 72 (and any other cartridge exhibiting the same failure mode, per the Stage 7 population scan) re-run and visually verified, confirming the 6 recovered tags are correctly centered on genuine holes, not texture or artifacts.
4. If Approach 4's residual signal is included: computation of the residual for all 78 validated cartridges' actual winning anchors, to confirm no currently-correct anchor has an anomalously large residual that a naively-chosen threshold might have rejected.

None of this validation has been performed as part of this design document. Stopping here per your instruction — no implementation follows without further approval.
