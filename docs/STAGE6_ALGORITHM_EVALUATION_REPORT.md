# Stage 6 — Algorithm Evaluation Report: MATCH_TOL_PX Sensitivity Analysis

**Status:** Analysis and evaluation only. No production code modified. Nothing implemented.
**Branch:** `stage6-detection-recall-analysis`
**Objective:** empirically evaluate 6 candidate `MATCH_TOL_PX` values (600, 620, 640, 660, 680, 690) across all 79 validated cartridges, and recommend the single safest algorithm change — which does **not** have to be a tolerance increase.

---

## 1. Headline Finding

**A naive `MATCH_TOL_PX` increase is unsafe and is not recommended**, regardless of value. The Stage 6 planning document's earlier proof (no two tags' predicted positions can ever be within `2×MATCH_TOL_PX` of each other, so raising the tolerance up to ~696px cannot cause cross-tag contention *for a fixed anchor*) is correct but insufficient — it does not account for **the anchor itself changing**. `MATCH_TOL_PX` is also the cutoff `_score_anchor` uses when scoring every candidate as a hypothetical anchor. Widening it lets previously-uncompetitive candidates tie or beat the current anchor's match count, and empirically, this happens: **the winning anchor flips in 3 of 79 cartridges (38, 48, 49) somewhere in the 600–690px range**, cascading into a mix of genuine recoveries, genuine corrections, false positives, and real regressions — including one confirmed case where a previously-correct measurement is replaced by a candidate with **zero ray hits** (`total_failure`, sitting on plain texture).

This directly validates your standing instruction: recall must never be optimized in isolation. It was not.

## 2. Method

Reproduced the exact current algorithm (Stage 1 nearest-distance anchor competition, Stage 2 fallback/n_hit/near/distance ranking) verbatim in a read-only script, parameterized only by `MATCH_TOL_PX`, and ran it across all 79 cartridges (1–33, 34–50, 51–60, 61–70(1), 71–79) for all 6 tolerance values. Hough detection and ray-casting (tolerance-independent) were computed once per cartridge and reused across all 6 values for efficiency; only the matching/ranking stages were re-run per tolerance. Every changed tag assignment was then visually inspected using the same overlay methodology established in Stages 2/3/5 — no conclusion is drawn from ray-cast statistics alone.

## 3. Per-Tolerance Metrics (all 553 tag-slots across 79 cartridges)

| Tolerance | Total matched | Meaningfully changed vs. 600 | Genuine new recoveries | False positives introduced | Genuine corrections (fixed a pre-existing wrong match) | Regressions (correct → wrong/missing) | Wrong-tag reassignments |
|---|---|---|---|---|---|---|---|
| 600 (current) | 528 | — (baseline) | — | — | — | — | — |
| 620 | 529 | 2 | 1 | 0 | 0 | 1 | 0 |
| 640 | 535 | 10 | 6 | 1 | 1 | 2 | 0 |
| 660 | 536 | 20 | 8 | 2 | 1 | 4 | 1 (paired with a recall loss) |
| 680 | 537 | 19 | 8 | 2 | 1 | 4 | 1 |
| 690 | 537 | 19 | 8 | 2 | 1 | 4 | 1 |

**No changes of any kind occurred in datasets 51–60 or 61–70(1) at any tolerance tested** — every effect (positive and negative) is confined to cartridges 18, 38, 45, 46, 48, 49 (34–50 dataset heavy), and 72.

### Precision / Recall / F1 (using visually-confirmed classification as ground truth)

Defining a "correct" match as one visually confirmed to sit on the true, correctly-labeled hole:

| Tolerance | Correct matches (TP) | Incorrect matches (FP) | Missing (FN, of 553) | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| 600 | 528 | 0 | 25 | 100.0% | 95.5% | 97.7% |
| 620 | 528 | 1 | 24 | 99.8% | 95.5% | 97.6% |
| 640 | 533 | 2 | 18 | 99.6% | 96.4% | 98.0% |
| 660 | 531 | 4 (+1 reassignment*) | 18 | 98.1% | 96.0% | 97.0% |
| 680 | 532 | 4 (+1 reassignment*) | 17 | 98.1% | 96.2% | 97.1% |
| 690 | 532 | 4 (+1 reassignment*) | 17 | 98.1% | 96.2% | 97.1% |

*The Cartridge 48 Tag 3/Tag 7 reassignment is counted once — a real hole correctly detected but reported under the wrong tag label, which corrupts the specific-position QC record even though it is not a "false" detection.

**Every tolerance above 600 trades precision for recall.** None is a strict improvement. 640 has the best F1 of the tested alternatives (98.0% vs. baseline 97.7%), but still introduces one confirmed false positive (Cartridge 45/Tag 6) and one confirmed severe regression (Cartridge 38/Tag 9, a correct measurement replaced by a zero-hit garbage candidate) that a bare constant change cannot avoid.

## 4. Per-Hole Change Table (every tag whose assignment changes at any tested tolerance)

| Cartridge | Tag | Tolerance introduced | Before | After | Visual classification | Category |
|---|---|---|---|---|---|---|
| 18 | 1 | 640 | missing | 0.5075mm, PASS | **Genuine hole** (clean 36/36 ring) | New recovery |
| 18 | 3 | 620 | missing | 0.51mm, PASS | **Genuine hole** (clean 36/36 ring) | New recovery |
| 18 | 4 | 640 | 0.465mm, PASS (on texture) | 0.4725mm, PASS (on real hole) | **Correction** — before was already wrong | Genuine correction |
| 18 | 5 | 640 | missing | 0.4975mm, PASS | **Genuine hole** | New recovery |
| 18 | 6 | 640 | missing | 0.4575mm, PASS | **Genuine hole** | New recovery |
| 18 | 7 | 640 | missing | 0.5mm, PASS | **Genuine hole** | New recovery |
| 38 | 9 | 620 | 0.51mm, PASS (real hole, 36/36) | 0.595mm/0.48mm, FAIL/PASS (0 ray hits, plain texture) | **False positive — severe regression** | **Regression** |
| 45 | 6 | 640 | missing | 0.44mm, FAIL | **False positive** (channel-wall edge, not a hole) | False positive |
| 46 | 4 | 660 | 0.505mm, PASS (real hole, 36/36) | 0.5475mm, PASS (texture near a scratch) | **False positive — regression** | **Regression** |
| 48 | 1 | 660 | missing | 0.445mm, FAIL | **False positive** (scattered texture, weak signal) | False positive |
| 48 | 3 | 660 | missing | 0.5mm, PASS | **Genuine hole — but it is Tag 7's old hole, now mislabeled** | Wrong-tag reassignment |
| 48 | 4 | 660 | total_failure garbage (already broken at baseline) | total_failure garbage (still broken) | Already unreliable before and after — unrelated pre-existing issue | Not a new regression |
| 48 | 6 | 660 | total_failure garbage (already broken at baseline) | normal/26/6, mediocre | Ambiguous improvement in fallback tier, not confirmed clean | Uncertain |
| 48 | 7 | 660 | 0.5mm, PASS (real hole) | **missing** | Its candidate was reassigned to Tag 3 | **Regression (recall loss)** |
| 48 | 9 | 660 | normal/16/10, mediocre (anchor) | normal/15/11, mediocre (different anchor) | Lateral move between two mediocre candidates | Uncertain |
| 49 | 4 | 640 | missing | 0.51mm, PASS | **Genuine hole** (clean 36/36 ring) | New recovery |
| 49 | 9 | 640 | 0.5125mm, PASS (real hole, 36/36, anchor) | 0.52mm, PASS (weaker, 21/18, wild position jump) | Quality degraded significantly; not independently confirmed genuine | **Likely regression** |
| 72 | 5 | 660 | missing | 0.57mm/0.53mm | **Genuine hole** (clean 36/36 ring) | New recovery |
| 72 | 6 | 680 | 0.53mm, PASS (real hole, 36/36) | 0.4675mm, PASS (also 36/36) | Both clean; likely another real hole in an already-broken cartridge's tag layout | Uncertain (Cartridge 72 already flagged broken) |
| 72 | 7 | 680 | 0.57mm, FAIL (mediocre, 15/8) | 0.51mm, PASS (36/36) | Improvement within an already-broken cartridge | Genuine correction (scoped to Cartridge 72) |
| 72 | 9 | 680 | 0.615mm, FAIL (poor, 9/4) | 0.49mm, PASS (17/15) | Partial improvement, still not clean | Uncertain (Cartridge 72 already flagged broken) |

**Note on Cartridge 48 and 72:** both cartridges already had pre-existing, separately-documented problems before this analysis (Cartridge 48 had a `total_failure` Tag 4 at baseline; Cartridge 72 was already identified in Stage 5 as having a broken geometric model). Churn within these two cartridges is harder to cleanly classify as "caused by" the tolerance change versus "exposing further instability in an already-broken cartridge" — flagged as such rather than forced into a clean verdict.

**The two unambiguous, severe new regressions — Cartridge 38/Tag 9 and Cartridge 46/Tag 4 — occur in cartridges that had zero prior issues.** These are the clearest, least-confounded evidence that a shared tolerance constant is unsafe.

## 5. Why False Positives Appear — Root Cause Investigation

Investigated each false positive/regression case against the requested categories:

| Category | Found? | Case(s) |
|---|---|---|
| Channel-wall edges | **Yes** | Cartridge 45/Tag 6 — candidate sits on a curved channel-wall boundary; ray hits trace a partial arc along the wall's curvature, not a closed ring on a hole |
| Scratches | **Yes** | Cartridge 48/Tag 1 — candidate sits on fine surface scratches/texture with scattered, incoherent ray hits |
| Bubbles | Not observed | No case traced to a bubble-like feature |
| Debris | Not observed | No case traced to debris |
| Illumination artifacts | **Yes** | Cartridge 38/Tag 9's post-regression position sits on plain, uniformly-lit PMMA texture with zero ray hits at all — not a distinct artifact, but a case where the candidate has no real edge signal whatsoever and still gets accepted purely because it was the closest available point within the (now wider) tolerance |

**Common mechanism:** every false positive/regression shares the same structural cause — `_score_anchor`'s nearest-distance matching (Stage 1) accepts *whichever* candidate is closest within tolerance, with no quality check at all. A wider tolerance simply exposes more low-quality candidates to this quality-blind acceptance rule. Stage 2's ranking (fallback tier → n_hit → near → distance) only ever runs on tags *already* matched by Stage 1 — it cannot rescue a tag that Stage 1 mismatched into a false anchor race, and it cannot prevent Stage 1 from accepting a bad candidate for a still-unmatched tag either, since Stage 2 never touches anchor selection.

## 6. Candidate Approaches — Ranked Comparison

| Approach | Expected recall improvement | Expected measurement accuracy | False-positive risk | Regression risk | Implementation complexity |
|---|---|---|---|---|---|
| **A. Raise `MATCH_TOL_PX` globally (600→640, 660, 680, or 690)** | +6 to +8 holes (of 25 missing) | Mixed — includes genuine corrections but also confirmed false positives | **High** — confirmed 1–2 false positives at every tested level ≥640 | **High** — confirmed anchor flips in 3 cartridges, including one severe regression (zero-hit candidate replacing a perfect one) in a previously-clean cartridge | Trivial (one constant) but **rejected** — the simplicity does not offset the proven instability |
| **B. Raise tolerance + statistical quality gate on newly-recovered tags** (from the prior Stage 6 plan) | Same as A, minus the false positives among *newly matched* tags | Same mixed picture for already-matched tags | Reduced for new recoveries, but **does not address regressions on already-matched tags** (Cartridge 38/46's damage happens via anchor reassignment, not via a bad new-tag acceptance) | **Still high** — the anchor-instability mechanism is untouched; this option was designed under an incomplete model of the risk | Low-medium |
| **C. Freeze Stage 1 anchor selection at 600px exactly as today; add a separate, wider-tolerance recovery pass that only attempts to fill tags still unmatched after the frozen anchor competition, using the same already-computed candidate pool** | Same +6 to +8 recoverable holes, potentially fewer once quality-gated (see below) | Does not address Cartridge 18/Tag4-style latent corrections (a tag already matched, just wrongly) — a real but separate class of error | **Low** — since the anchor never changes, no already-correct tag can be reassigned or destabilized; a quality gate (e.g. requiring `fallback_mode="normal"` and a high near-nominal ratio) can be applied to the recovery pass alone, since it only ever adds matches for tags that were otherwise reporting nothing | **Low** — directly eliminates the proven failure mechanism (anchor instability) by construction, not by hope | Medium — a new, clearly-scoped code path, but reuses 100% already-computed data and follows the exact "preserve existing behavior, add new capability alongside it" pattern already validated by Stage 2 |
| **D. Geometric/pattern-matching model correction** (e.g., per-cartridge affine or scale correction instead of one fixed `REF_OFFSETS` anchor) | Could recover the 14 "outside captured frame" holes (56% of all missing holes) that no tolerance change can ever reach | Highest ceiling of any option — directly addresses the largest root-cause category | Unknown — an entirely new algorithm component, no empirical data yet | **Unknown/high** — largest, least-understood change; needs its own dedicated investigation before any risk assessment is possible | High — a new algorithm, not a parameter or a scoped addition |

## 7. Recommendation

**Recommend Option C: freeze Stage 1 anchor selection exactly as it behaves today, and add a separate, additive recovery pass — using a wider search radius (e.g. 690px, informed by this analysis) — that only ever attempts to fill tags still unmatched after the frozen anchor competition.** This is the only approach that:
- Directly targets the actual proven failure mechanism (anchor-competition instability under a shared tolerance), rather than bolting a quality filter onto an unaddressed root cause (Option B).
- Cannot, by construction, ever change a tag that Stage 1 already matched at 600px today — eliminating the exact regression pattern confirmed in Cartridge 38, 46, and 48 (Tag 7 loss / Tag 3 reassignment).
- Recovers a meaningful share of the 11 in-tolerance-gap missing holes (this analysis confirms at least 6–8 of them are genuine, visually-verified holes) without inheriting the anchor-flip risk.
- Should itself carry a quality gate (e.g., only accept a recovery candidate with `fallback_mode="normal"` and a near-nominal ratio comfortably above the one confirmed false positive's 0.53, such as ≥0.7) — since this pass only ever adds matches for currently-missing tags, a gate here has no interaction with anchor stability at all, unlike Option B's flawed placement of the same idea.

**Option D (geometric model correction) is likely necessary eventually** — it is the only path to the 14 outside-frame holes, the majority of the recall gap — but it requires its own dedicated investigation (per-cartridge scale/rotation estimation, or an adaptive geometric model) before any risk assessment is possible, and should not block or be conflated with Option C.

**Option A is not recommended in any form.** **Option B is not recommended** — it was designed before this empirical evidence existed and targets the wrong stage of the pipeline.

## 8. Proposed Implementation Plan for Option C (not yet approved for implementation)

1. Add a new, clearly-isolated block in `detect_holes()`, running strictly after the existing Stage 1 anchor competition and Stage 2 refinement, both entirely unmodified.
2. For each tag still absent from `best_matched` after Stage 2, search all raw candidates within a wider radius (proposed 690px, matching the value validated in this analysis) of that tag's predicted position (using the same, unchanged anchor).
3. Accept a candidate into this pass only if it meets a minimum quality bar derived from already-computed data (fallback tier `normal`, near-nominal ratio above a conservative threshold) — never inventing new detection logic, only gating acceptance.
4. Every result of this pass must be visually verified individually before being trusted, exactly as done in this report — statistics alone are not sufficient, per your standing instruction.

### Validation criteria for this future implementation
- `py_compile` + import verification.
- Full regression on all 5 dataset groups. **Required result: zero changes to any tag already matched by the unmodified Stage 1/Stage 2 logic** — this is the core guarantee Option C provides and must be empirically confirmed, not assumed.
- Every newly-recovered hole visually reviewed and classified (genuine / false positive / uncertain), same standard as this report.
- Precision must not drop below the 600px baseline (100% correct-of-matched, ignoring the pre-existing missing/broken cases already documented in Stage 5).
- Recall improvement quantified only over genuinely-confirmed recoveries, not raw match count.

Nothing has been implemented. Waiting for approval before any code is touched.
