# Stage 6 — Frozen-Anchor Additive Recovery Pass: Engineering Design

**Status:** Design only. No production code modified. Nothing implemented.
**Branch:** `stage6-detection-recall-analysis`
**Prerequisite:** `docs/STAGE6_ALGORITHM_EVALUATION_REPORT.md` — the empirical evaluation that ruled out a global `MATCH_TOL_PX` increase (proven anchor-selection instability, confirmed regressions in Cartridges 38, 46, 48) and recommended this design instead.

---

## 1. Exact Execution Order

Current pipeline (`detect_holes()` in `detect_features.py`), unmodified stages in **bold**, new stage in *italic*:

```
1. preprocessing (preprocess.py — crop to active area, downsample, CLAHE, blur)          [BEFORE detect_holes() is called — untouched]
2. Hough detection (cv2.HoughCircles on the downsampled/blurred image)                    [UNTOUCHED]
3. Per-candidate subpixel diameter measurement (_subpixel_diameter, ray-cast,
   populates the `detected` list and `_ray_debug_by_id` for every raw candidate)           [UNTOUCHED]
4. Stage 1 anchor competition (_score_anchor tried for every candidate as a
   hypothetical anchor; nearest-distance matching at MATCH_TOL_PX=600;
   produces best_anchor_cxy and best_matched)                                             [UNTOUCHED]
5. best_matched_anchor_ref = dict(best_matched)  (frozen snapshot, pre-existing
   from the Fix 3 coupling-bug fix)                                                        [UNTOUCHED]
6. Stage 2 candidate ranking (fallback tier → n_hit → near → distance; only
   ever replaces a value for a tag already in best_matched)                               [UNTOUCHED]
7. >>> NEW: RECOVERY PASS <<<                                                              [NEW STAGE]
8. Missing-hole diagnostics (outside_image / not_detected classification)                  [reads one new value — see §2]
9. Center refinement (_refine_center, cosmetic, proven zero effect on measurements)         [UNTOUCHED]
10. Final circle list construction                                                         [UNTOUCHED — sees a possibly-larger best_matched, nothing else]
```

**The recovery pass executes after Stage 2 completes and before the missing-hole diagnostic block runs.** This placement is deliberate:
- **After Stage 2**, not before or during, so it can never interact with Stage 2's own replace-only-if-strictly-better logic, and so `best_matched` reflects the fully-finalized, ordinary-path result before recovery ever looks at what's still missing.
- **Before the missing-hole diagnostics**, so that any tag the recovery pass fills is naturally excluded from the final `missing_holes` list — without recovery, that list is computed once, after everything else; recovery is simply one more thing that can happen before it runs.

## 2. Exact Inputs and Outputs

**Read-only inputs (nothing here is modified by the recovery pass):**
- `detected` — the full list of ray-cast-measured candidates, exactly as Hough + `_subpixel_diameter` produced it.
- `_ray_debug_by_id` — existing per-candidate ray debug dict (already populated for every candidate).
- `best_anchor_cxy` — the frozen, true anchor position chosen by Stage 1. **Never recomputed, never re-derived.**
- `best_matched` (post-Stage-2) — read to determine (a) which candidates are already in use, (b) which tags still need filling.
- `REF_OFFSETS`, `_predict_positions` — existing geometry, called with the existing `best_anchor_cxy`, not a new anchor.
- Image bounds (`preprocessed["bgr"].shape`).
- One **new** constant: `RECOVERY_TOL_PX` (proposed value: 690px — see §7 for why this specific value, and §5 for why it must stay under ~697px).
- One **new** constant set: the quality gate thresholds (§4).

**Outputs (the only things written):**
- `best_matched` — gains new key/value pairs **only** for tags absent after Stage 2. **An existing key is never overwritten, never touched.**
- A new, small tracking set: `recovered_tags` (the set of tags this pass filled) — used only to (a) tell the missing-hole diagnostic these tags are now accounted for, and (b) optionally populate `debug_context` for auditability (e.g. `debug_context["recovery_pass"]`), matching this project's established non-invasive instrumentation pattern.

**Nothing else is written.** `best_anchor_cxy`, `best_matched_anchor_ref`, `detected`, `MATCH_TOL_PX`, and every other existing variable are read at most, never mutated.

## 3. Candidate Eligibility

A candidate `c` from `detected` is eligible to fill a still-missing tag `t` only if **all** of the following hold:

1. **Not already in use.** Before the recovery pass begins, build `used = {id(v) for v in best_matched.values()}`. Any candidate whose `id()` is in `used` is skipped unconditionally. **This is the mechanism that protects every already-matched candidate** — the exact protection the naive tolerance increase lacked, which is precisely how it produced the Cartridge 48 Tag 7 → Tag 3 reassignment. Here, a candidate already claimed by Tag 7 (or any tag) can never be considered for Tag 3, because Tag 7's entry is already in `best_matched` before recovery ever runs, and recovery only evaluates tags with no entry at all.
2. **Within `RECOVERY_TOL_PX` of the tag's true predicted position**, computed as `_predict_positions(*best_anchor_cxy)[t]` — the exact same frozen anchor Stage 1 already selected. Never a re-derived or approximate anchor.
3. **The tag's predicted position must not already be `outside_image`.** Reuse the exact bounds check already validated in Fix 3 (`px < -margin or px > w+margin or ...`). If the true predicted position is outside the captured frame, no search is performed at all — this correctly excludes the 14 permanently-unrecoverable cases from even being attempted.
4. **Passes the quality gate** (§4).

**Tie-breaking and processing order:** tags are processed in a fixed, deterministic order (ascending tag number: 1, 3, 4, 5, 6, 7, 9). For each tag, among all eligible candidates, the one ranked highest by the **existing** Stage 2 ranking tuple `(fallback_tier, n_hit, near, -distance)` is selected — reusing already-established ranking logic, not inventing a new one. Once a tag is filled, its chosen candidate is immediately added to `used` before the next tag is evaluated, so no candidate can ever be claimed by two tags within the same recovery pass, even if it happens to be within `RECOVERY_TOL_PX` of both (a scenario this design keeps improbable by construction — see §5 for the exact margin).

## 4. Quality Gate

**Ray-hit count alone is confirmed insufficient** — the false positive at Cartridge 45/Tag 6 shows a moderate 26/36 hit count, which any reasonably lenient count-only threshold would pass.

I empirically tested five candidate signals against the confirmed cases from Stages 5–6 (3 genuine holes, 2 confirmed false positives, 1 uncertain case, 1 severe-regression false positive) before recommending anything:

| Signal | Cart18/Tag1 (genuine) | Cart18/Tag5 (genuine) | Cart72/Tag5 (genuine) | Cart45/Tag6 (false, channel-wall) | Cart48/Tag1 (false, scratch) | Cart48/Tag6 (uncertain) | Cart38/Tag9-after (false, texture) |
|---|---|---|---|---|---|---|---|
| `fallback_mode` | normal | normal | normal | normal | normal | normal | normal |
| `n_hit`/36 | 36 | 36 | 36 | 26 | 9 | 26 | 14 |
| `near_nominal`/36 (ratio) | 0.94 | 1.00 | 1.00 | 0.53 | 0.14 | 0.17 | 0.22 |
| **max angular gap between hit rays** | **10°** | **10°** | **10°** | **70°** | **110°** | **100°** | **120°** |
| wall fraction (fixed nominal radius) | 0.47 | 0.42 | 0.28 | 0.25 | 0.00 | 0.44 | 0.01 |

**Findings:**
- `fallback_mode == "normal"` is necessary but not discriminative on its own — every case here, including all 4 false positives, already reports `"normal"`.
- **`near_nominal_count / 36` is a strong discriminator**: genuine holes cluster at 0.94–1.00; every false positive is ≤0.53 — a wide, clean margin.
- **Max angular gap between consecutive hit rays is the strongest discriminator found, and it targets the exact failure mode requested (channel-wall/scratch edges).** Genuine holes uniformly show 10° (the minimum possible spacing at 36 rays — meaning hits are essentially contiguous all the way around). Every false positive shows 70–120°, because a channel wall or scratch only presents an edge along a partial arc, never a full ring. This is computed entirely from data `_subpixel_diameter` already produces per ray (`hit`, angular index) — no new image sampling, just a derived statistic over existing values, in the same spirit as the ray-radius-uniformity check already used in Stage 3.
- **Wall fraction, sampled at a fixed nominal radius, did *not* reliably separate the cases** — Cart45/Tag6's false positive (0.25) falls inside the genuine holes' own range (0.28–0.47). This is an honest negative result: wall fraction was useful earlier in this project for a *different* question (does Hough's own reported radius correspond to a real edge), but as tested here it is not recommended as a gate component. It would likely need to be resampled at each candidate's own already-measured diameter rather than one fixed nominal value to be useful — a possible future refinement, not included in this design to keep it minimal and proven.

**Recommended minimum quality gate** (all three required):
```
fallback_mode == "normal"
AND (near_nominal_count / 36) >= 0.70
AND (max_angular_gap_between_hit_rays) <= 40 degrees
```

Margins against the tested sample: the near-nominal ratio threshold sits 0.24 below the genuine floor and 0.17 above the false-positive ceiling; the angular-gap threshold sits 30° below the false-positive floor and 30° above the genuine ceiling — both thresholds have room on both sides, not just barely clearing the known cases.

**Caveat, stated plainly:** this is validated against 7 known cases (3 genuine, 4 false), not a large statistical sample. The validation plan (§6) requires checking this gate against every new case the recovery pass encounters across all 79 cartridges before trusting it in production, not just the cases already known today.

## 5. Regression Safety

**Why the recovery pass cannot change existing matched holes:** it never writes to an existing key in `best_matched`. The only write operation is `best_matched.setdefault(tag, candidate)` (or equivalent — assign only if absent), applied exclusively to tags with no current entry. There is no code path in this design that reads an existing tag's value and replaces it — unlike Stage 2, which is explicitly designed to replace, the recovery pass is explicitly designed only to add.

**Why it cannot move existing anchors:** `best_anchor_cxy` is read once, at the start of the recovery pass, and never reassigned. The recovery pass contains no anchor competition of its own — it does not call `_score_anchor` or re-run the "try every candidate as anchor" loop that caused the proven instability in the naive tolerance-increase approach. This is the direct, structural fix for the exact mechanism identified in the Stage 6 evaluation report.

**Why it cannot alter current measurements:** every already-matched tag's `diameter_mm`, `cx_px`, `cy_px`, and `pass` value derive entirely from the candidate object already stored in `best_matched` before recovery runs. Since recovery never touches an existing key, none of these values can change for any tag that was already matched.

**Why it cannot reduce current precision:** precision, as measured in this project, is the fraction of matched tags that are genuinely correct. The recovery pass can only ever add new matched tags (previously contributing to `n_missing`, not `n_matched`) — it cannot convert an existing correct match into an incorrect one, because it cannot touch existing matches at all. It can only affect precision through the *new* matches it introduces, which is exactly why the quality gate (§4) exists and why every recovered hole must still be visually confirmed (§6) rather than trusted from the gate alone.

**Formal cross-tag safety margin:** the geometric proof from Stage 2/6 (minimum pairwise predicted-tag distance = 1393.9px) guarantees no single candidate can be within `R` of two different tags' predicted positions simultaneously as long as `2×R < 1393.9`, i.e. `R < 696.95px`. The proposed `RECOVERY_TOL_PX = 690px` keeps a 6.95px margin under this limit — matching, not exceeding, the exact safe ceiling already established. **This is a separate and additional safety layer on top of the "already-used candidates are excluded" rule in §3** — even without the `used` check, two *simultaneously missing* tags could not both claim the same candidate at this radius. With the `used` check also in place, this holds even for candidates shared between a missing tag and an *already-matched* one.

## 6. Validation Plan

**Regression tests (mandatory, required to pass before this design could be considered for approval):**
1. `py_compile` + import verification.
2. Full regression on all 5 dataset groups (1–33, 34–50, 51–60, 61–70(1), 71–79). **Required result: zero changes to any of the 528 currently-matched tags** — every field (`cx_px`, `cy_px`, `diameter_mm`, `pass`) must be byte-identical to the current baseline for every tag already matched today. This is the core guarantee this design provides and must be confirmed empirically, exactly as every other change in this project has been, not assumed from the design alone.
3. Confirm the `missing_holes` list only shrinks (loses exactly the recovered tags) and never gains new entries or changes any `outside_image` classification.

**Visual review (mandatory for every newly-recovered hole, no exceptions):**
- Every tag the recovery pass fills — across all 79 cartridges, not only the ones already known from this analysis — must be visually inspected using the same overlay methodology used throughout Stages 2–6 (predicted position, candidate circle, ray-hit overlay, on the real image) and classified genuine / false positive / uncertain.
- Any "uncertain" or "false positive" result found during this review means the quality gate needs revision **before** implementation is considered complete — not after.

**Acceptance criteria:**
- Zero changes to any previously-matched tag (hard requirement, not a target).
- Every newly-recovered hole visually confirmed genuine (target: 100% of what the gate accepts; any confirmed false positive that passes the gate is a gate design defect requiring rework, not an acceptable trade-off).
- No new cross-tag conflicts (no candidate assigned to two different tags).
- No change to any diagnostic label except the `not_detected → matched` transition for genuinely recovered tags.

**Success metrics (measured after implementation, compared against this design's estimate in §7):**
- Recall improvement: recovered-hole count / 25 currently-missing holes.
- Precision: recovered-hole count that is visually genuine / total recovered-hole count (target 100%).
- F1 relative to the 600px baseline (97.7%) — must be equal or higher, never lower.

## 7. Expected Recovery (Estimate, to Be Confirmed Empirically During Implementation)

Based on the already-completed empirical sweep (`docs/STAGE6_ALGORITHM_EVALUATION_REPORT.md`) and the quality gate validated in §4:

| Category | Count | Detail |
|---|---|---|
| Currently missing (all 79 cartridges) | 25 | Established in Stage 6 planning |
| Permanently unrecoverable by this design | 14 | Predicted position genuinely outside the captured frame — no tolerance or quality gate reaches these; requires the separate geometric-model investigation (Option D) |
| Within `RECOVERY_TOL_PX=690px` and passes quality gate | **5** | Cartridge 18, Tags 1, 3, 5, 6, 7 — all previously visually confirmed genuine, all comfortably clear both gate thresholds |
| Within `RECOVERY_TOL_PX=690px` but **rejected** by quality gate (correctly) | 1 | Cartridge 45/Tag 6 — the confirmed channel-wall false positive; ratio 0.53 and gap 70° both fail their thresholds, exactly as intended |
| Beyond `RECOVERY_TOL_PX=690px` (distances 849–1408px) | 5 | Cartridge 33/Tag7, 45/Tag7, 50/Tag3, 50/Tag7, 72/Tag4 — only one of these (72/Tag4) is high quality; reaching any of them would require exceeding the proven-safe 697px ceiling, deliberately deferred rather than bundled into this design |

**Expected outcome of this specific design: +5 holes recovered (20% of all 25 currently missing), 0 changes to any of the 528 currently-correct matches, 0 new false positives (the one candidate the wider radius exposes is correctly rejected by the quality gate).**

Projected metrics: recall improves from 528/553 (95.5%) to 533/553 (96.4%); precision remains at 100% of matched tags (no regressions, no accepted false positives); F1 improves from 97.7% to approximately 98.2% — a smaller numeric gain than the naive tolerance increase appeared to offer, but the naive increase's apparent gain was not real (it was built on regressions this design eliminates by construction).

**Explicitly out of scope for this design**, consistent with the Stage 6 evaluation report's ranking:
- The 14 outside-frame holes (56% of the total gap) — needs the separate geometric/pattern-matching model investigation (Option D).
- The 5 farther in-tolerance-gap candidates — reaching them would mean exceeding the proven-safe radius ceiling, which reopens the exact cross-tag-contention question this design is built to avoid; a future, separately-risk-assessed extension, not bundled here.

Nothing has been implemented. This document is the complete design for review; implementation should not begin until it is explicitly approved.
