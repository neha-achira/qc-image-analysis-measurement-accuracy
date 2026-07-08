# Stage 6 — Recovery Pass Implementation Report

**Status:** Implemented, validated, and committed. Project closed out.
**Branch:** `stage6-detection-recall-analysis`
**Commit:** `23d6e93` — "Add frozen-anchor additive recovery pass for unmatched holes"
**Implements:** `docs/STAGE6_RECOVERY_PASS_DESIGN.md`, validated by `docs/STAGE6_QUALITY_GATE_VALIDATION_REPORT.md`.

---

## 1. Change Summary

Added one new, self-contained block to `detect_holes()` in `detect_features.py`, executing after Stage 2's ranking refinement and before the missing-hole diagnostic block — exactly the placement specified in the approved design. No other function, file, or existing block was touched. The block:
- Reads `best_anchor_cxy` (frozen, never recomputed — no call to `_score_anchor` occurs in this pass).
- Considers only tags absent from `best_matched` after Stage 2 (`if tag in best_matched: continue` at the top of the loop — an existing entry can never be reached, let alone overwritten).
- Excludes candidates already claimed by any tag via an `id()`-based `used_ids` set.
- Searches within `RECOVERY_TOL_PX=690px` of the true predicted position.
- Applies the validated quality gate (`fallback_mode=="normal"` AND `near_nominal_ratio>=0.70` AND `max_angular_gap<=40°`).
- Adds a qualifying candidate to both `best_matched` and `best_matched_anchor_ref` (so the missing-hole diagnostic correctly excludes it), and records it in a new `recovered_tags` list, exposed via `debug_context["recovery_pass"]` when requested.

## 2. Compile and Import

- `py_compile detect_features.py` → OK
- `import detect_features` → OK

## 3. Full Regression — All 5 Dataset Groups

Compared the current implementation against the pre-recovery-pass code (previous commit, extracted via git) across all 553 tag-slots in 1–33, 34–50, 51–60, 61–70(1), 71–79:

| Check | Result |
|---|---|
| Newly matched (missing → matched) | **5** |
| Newly unmatched (matched → missing) — regression indicator | **0** |
| Measurement (`diameter_mm`) changes on already-matched tags — regression indicator | **0** |
| PASS/FAIL changes on already-matched tags — regression indicator | **0** |
| Position (`cx_hough`/`cy_hough`) changes on already-matched tags — regression indicator | **0** |
| Missing-hole reason changes on still-missing tags | **0** |

**No unexpected change occurred anywhere.** Per your instruction to stop immediately and report if any existing matched hole changed — none did, so implementation proceeded through to completion without interruption.

## 4. Newly Recovered Holes

| Cartridge | Tag | Position | Diameter | PASS/FAIL |
|---|---|---|---|---|
| 18 | 1 | (608, 668) | 0.5075mm | PASS |
| 18 | 3 | (1020, 3344) | 0.4975mm | PASS |
| 18 | 5 | (2296, 5720) | 0.51mm | PASS |
| 18 | 6 | (3388, 2060) | 0.4575mm | PASS |
| 18 | 7 | (3712, 3416) | 0.5mm | PASS |

All 5 are in Cartridge 18 — exactly the set predicted by the design (§7) and the quality-gate validation report.

## 5. Rejected Candidates

Two candidates were within `RECOVERY_TOL_PX` of a missing tag's predicted position but rejected by the quality gate, exactly as intended:

| Cartridge | Tag | Position | Reason for rejection |
|---|---|---|---|
| 18 | 1 (second candidate) | (236, 152) | `fallback_mode` = `off_nominal_fallback` (fails the first gate condition) — visually confirmed false positive (partial arc near a border) |
| 45 | 6 | (2164, 1276) | `near_nominal_ratio` = 0.528 < 0.70 threshold — visually confirmed false positive (channel-wall edge) |

Cartridge 45/Tag 6 remains correctly reported as `not_detected` (unchanged from before this implementation) — confirmed in §3's "missing-hole reason changes: 0" row.

## 6. Measurement and PASS/FAIL Changes

**Zero changes to any previously-existing measurement or PASS/FAIL decision.** The only measurement/PASS-FAIL values that exist now and didn't before are the 5 newly-recovered holes in §4 — there are no changes to values that already existed prior to this implementation.

## 7. Visual Verification

All 5 newly-recovered holes were visually verified twice: once during the design/validation phase (individually), and once more here, directly against the actual modified production code (not a replay script) — a combined overview image of Cartridge 18 was generated from a live `detect_holes()` call, showing all 5 recovered tags (magenta, labeled "RECOVERED") each sitting precisely on a genuine, clearly-visible through-hole. Saved to `validation_output/stage6_recovery_pass_implementation/cart18_final_overview.png`.

## 8. Precision, Recall, F1

| Metric | Before this implementation | After this implementation |
|---|---|---|
| Matched tags | 528 / 553 | 533 / 553 |
| Precision (matched tags confirmed correct) | 100% (528/528) | 100% (533/533) |
| Recall | 95.48% (528/553) | 96.38% (533/553) |
| F1 | 97.68% | 98.16% |

Precision is unchanged at 100% — no false positive was introduced (the one candidate the wider search radius exposed, Cartridge 45/Tag 6, was correctly rejected). Recall and F1 both improved, matching the design's estimate exactly (+5 of 25 previously-missing holes, 20%).

## 9. Regression Summary

**No regression of any kind occurred.** This is the key result this design was built to guarantee: unlike the naive `MATCH_TOL_PX` increase evaluated and rejected in `docs/STAGE6_ALGORITHM_EVALUATION_REPORT.md` (which destabilized Stage 1 anchor selection and corrupted previously-correct measurements in Cartridges 38, 46, and 48), this frozen-anchor, additive-only design cannot touch any existing match by construction — and the full regression confirms this held true in practice, not just in theory.

## 10. Known Cosmetic Side Effect (observed, not fixed — out of scope per instruction)

The existing `print(f"  Pattern match: {best_score}/{len(REF_OFFSETS)} matched ...")` log line uses `best_score`, the count from the original Stage 1 anchor competition only. It does not include tags added by the recovery pass, so for Cartridge 18 it now prints "Pattern match: 2/7 matched" even though the final result (`missing_holes`, `circles`) is fully correct (7/7). This is a stale console-log message only — no returned data is affected. Flagging it for your awareness; not fixed here, per "do not implement any additional improvements."

## 11. Files Changed

- `detect_features.py` — one new block, 74 insertions, 0 deletions, in `detect_holes()`. No other function or file modified.
- Commit `23d6e93` on branch `stage6-detection-recall-analysis`.

## 12. Remaining Known Limitations

Carried forward from the design and evaluation reports, none of the following are addressed by this implementation and none were in scope for it:

1. **14 of the original 25 missing holes (56%) remain unrecoverable** — their predicted position is genuinely outside the captured image frame. No tolerance radius or quality gate can reach these; they require a different geometric/pattern-matching model (Stage 6 evaluation report's "Option D"), not yet designed.
2. **5 more missing holes remain out of reach of this specific implementation** (Cartridge 33/Tag7, 45/Tag7, 50/Tag3, 50/Tag7, 72/Tag4) — their nearest real candidate sits 849–1408px from the predicted position, beyond the `RECOVERY_TOL_PX=690px` ceiling. That ceiling was deliberately kept under the proven-safe 697px ceiling (half the minimum pairwise tag distance) to preserve the cross-tag-contention guarantee; reaching these 5 would require re-opening that risk analysis, not a simple constant increase.
3. **Cartridge 72's broader pattern-matching breakdown** (Stage 5/6 finding: the anchor-competition correctly finds the best available anchor, but the fixed-pixel geometric model still doesn't fit this cartridge) is unresolved and unrelated to this implementation.
4. **Two borderline diameter-measurement cases** (Cartridge 51/Tag4, Cartridge 66/Tag6, from Stage 5) remain blocked on independent Leica reference data, which does not exist anywhere in this project.
5. **The cosmetic `"Pattern match: X/7"` console-log discrepancy** (§10) — observed, not fixed, by explicit instruction.
6. **The recovery pass's true candidate population is small** (7 candidates found across all 79 cartridges, per the quality-gate validation report) — the 100%/100% precision/recall on the gate itself is validated against every case that exists today, not a large statistical sample. Future cartridges may present gate behavior not yet observed; the mandatory per-hole visual review specified in the design (§6 of `docs/STAGE6_RECOVERY_PASS_DESIGN.md`) remains the intended safeguard for this, not a one-time validation.

## 13. Recommendations for Future Work

Ranked by the same criteria used throughout Stage 6 (expected impact vs. regression risk):

1. **Investigate the geometric/pattern-matching model** (Option D from the Stage 6 evaluation report) — the single highest-impact remaining item, since it is the only path to the 14 outside-frame holes (56% of the original gap). Needs its own dedicated investigation (e.g., per-cartridge scale/rotation estimation) before any risk assessment is possible; should not be bundled with future recovery-pass extensions.
2. **Revisit the 5 farther in-tolerance-gap holes** only after a specific, separate cross-tag-contention risk analysis for whatever radius would reach them — do not simply raise `RECOVERY_TOL_PX` further without re-deriving the safety margin.
3. **Obtain independent Leica reference measurements** for Cartridge 51/Tag4 and Cartridge 66/Tag6 to resolve whether their borderline deviations reflect a software bias or genuine part variance — this is blocked on external data, not further code investigation.
4. **Continue monitoring the recovery pass's quality gate** as more cartridges are processed in production — log every case where the recovery pass fires (via `debug_context["recovery_pass"]`) and periodically visually spot-check, since the validated population is still small in absolute terms.
5. **Low priority:** fix the cosmetic `"Pattern match"` log line to reflect the post-recovery count, purely for operator clarity — no functional impact.

Implementation is complete, validated, committed, and closed out. Stopping here per your instruction — no new implementation follows.
