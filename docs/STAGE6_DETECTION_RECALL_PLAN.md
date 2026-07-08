# Stage 6 — Detection Recall Improvement: Analysis & Implementation Plan

**Status:** Analysis and planning only. No production code modified. Nothing implemented.
**Branch:** `stage6-detection-recall-analysis`
**Objective (per instruction):** identify the single algorithmic change that recovers the most currently-missing holes with the lowest regression risk, and produce an implementation plan with validation criteria — implementation itself is a future, separately-approved step.
**Scope:** every currently-missing hole across all validated datasets (1–33, 34–50, 51–60, 61–70(1), 71–79 = 79 cartridges, Holes image type).

---

## 1. Method

For every cartridge, ran the current (unmodified) `detect_holes()` with `debug_context` to get the exact `missing_holes` list production computes today. For every missing tag, classified the earliest failure stage using only already-established techniques from Stages 3–5 (verbatim Hough replay to recover the full raw candidate list, `_subpixel_diameter` ray-cast quality on the nearest candidate at any distance, and the active-area/full-image bounds check):

- **Preprocessing:** does the active-area crop itself exclude the predicted position, independent of the geometric model? (Checked directly — see note in §3.)
- **Hough candidate generation:** is there truly no candidate anywhere in the image reasonably near the true predicted position?
- **Geometric matching / tolerance:** does a real Hough candidate exist near the true predicted position, but farther than the current `MATCH_TOL_PX=600px`?
- **Candidate ranking:** did a candidate within tolerance exist but a worse one get selected? (Structurally impossible for a *missing* hole — if any candidate were within tolerance, Stage 1 matching would have selected it. Included for completeness; confirmed empty.)
- **Subpixel diameter measurement:** not applicable — this stage never runs for a tag with no matched candidate.

## 2. Complete Population

25 missing-hole instances exist across all 79 validated cartridges, in 7 cartridges: 18, 33, 45, 48, 49, 50, 72. (Cartridges 18/72 already partially documented in the Stage 5 report; this analysis re-derives them alongside the previously-unexamined cartridges 33, 45, 48, 49, 50 for completeness.)

## 3. Stage Statistics

| Stage | Count | % of missing holes |
|---|---|---|
| Preprocessing (genuine crop/seam-masking defect) | **0** | 0% |
| Hough candidate generation (zero candidates anywhere near the true position) | **0** | 0% |
| Candidate ranking (a better candidate was available but rejected) | **0** | 0% |
| Geometric matching — predicted position outside the captured frame | **14** | 56% |
| Geometric matching — real candidate exists, beyond current tolerance | **11** | 44% |
| Subpixel diameter measurement | N/A (25/25 — stage never reached) | — |

**Important correction made during this analysis:** an initial pass flagged 3 cases (Cartridge 45/Tag5, 48/Tag3, 50/Tag5) as "preprocessing" failures because their predicted position fell outside the active-area crop. Direct verification showed all 3 are also outside the *full raw image* (e.g., Cartridge 45/Tag5's predicted y=4960 exceeds the image height of 4931 by only 29px) — these are not preprocessing defects, they are the same "outside captured frame" phenomenon as the other 11, just closer to the boundary. They are counted in the 14, not as a separate category. **Zero of the 25 missing holes are caused by preprocessing, Hough candidate generation, or candidate ranking.** Every one traces to the geometric/pattern-matching model (fixed-pixel `REF_OFFSETS` + single anchor point).

## 4. The Two Root-Cause Sub-Categories

**Category A — outside the captured frame (14/25, 56%).** The predicted position, even computed from the correct anchor, falls entirely outside the image. Not recoverable by any Hough/tolerance/ranking change — would require a fundamentally different geometric model (e.g., per-cartridge scale/rotation correction) or wider imaging. **Out of scope for a single low-risk change**, consistent with Stage 5's conclusion about Cartridge 72's broader pattern-matching breakdown.

**Category B — real candidate exists, just beyond tolerance (11/25, 44%).** The predicted position is correct and within the image; Hough already found a real candidate there; it simply falls outside the current 600px matching window. Distances range 619–1408px:

| Cartridge | Tag | Distance | Candidate quality (fallback / n_hit / near_nominal) |
|---|---|---|---|
| 18 | 1 | 621px | normal / 36 / 34 |
| 18 | 3 | 630px | normal / 36 / 36 |
| 18 | 5 | 619px | normal / 36 / 36 |
| 18 | 6 | 625px | normal / 36 / 36 |
| 18 | 7 | 630px | normal / 36 / 35 |
| 45 | 6 | 626px | normal / 26 / 19 |
| 33 | 7 | 1240px | normal / 21 / 19 |
| 45 | 7 | 1286px | normal / 11 / 11 |
| 50 | 3 | 849px | normal / 12 / 10 |
| 50 | 7 | 1254px | normal / 9 / 7 |
| 72 | 4 | 931px | normal / 36 / 36 |

**6 of these 11 sit just 19–30px beyond the current 600px cutoff** (Cartridge 18's five tags, plus Cartridge 45/Tag6) — the remaining 5 are much farther (849–1286px).

## 5. Recommended Single Change

**Increase `MATCH_TOL_PX` from 600px to 690px.**

**Why this specific value is safe:** the Stage 2 investigation already proved, geometrically, that the minimum pairwise distance between any two tags' predicted positions is 1393.9px (Tag6–Tag7). Cross-tag candidate contention is impossible by construction as long as `2 × MATCH_TOL_PX < 1393.9px`. At 690px, `2 × 690 = 1380 < 1393.9` — safe, with a 13.9px margin. This is a mathematical guarantee, not an empirical estimate, and it is the largest round value that preserves it.

**Why this recovers the most value for the risk taken:** it recovers exactly the 6 "just barely beyond tolerance" cases in §4 (Cartridge 18's five tags, Cartridge 45/Tag6) — all of which already have `fallback_mode="normal"`. It does **not** reach the other 5 farther candidates (849–1286px) or any of the 14 outside-frame cases — those remain out of scope, as no tolerance value that stays under the 696.9px safety ceiling can reach them.

**A finding that qualifies this recommendation, found via direct visual inspection (not statistics alone):**

I generated and visually reviewed overlay images for all 6 candidates this change would newly match:
- **Cartridge 18, Tags 1, 3, 5, 6, 7 — confirmed genuine through-holes.** Each shows a clean, continuous ray-hit ring sitting exactly on a real, high-contrast circular boundary. High confidence.
- **Cartridge 45, Tag 6 — very likely a false positive.** The candidate sits on a curved channel-wall edge, not a circular hole — the ray-hit dots trace a partial arc along the wall's curvature, not a closed ring on a real hole boundary. Its ray-cast statistics (`normal`, 26/36 hits, 19/36 near-nominal) look superficially reasonable in isolation but are visually wrong. **This is exactly the kind of case this project's own history has repeatedly warned against trusting from statistics alone.**

**Consequence:** a bare tolerance-constant change would recover 5 genuine holes and silently introduce 1 incorrect measurement (converting a transparent "missing" into a confidently-wrong diameter/PASS-FAIL for Cartridge 45/Tag6) — a real regression in *precision*, even though it improves *recall*. The two candidate quality metrics separate the two groups by a wide margin in this sample (near-nominal ratio: 0.94–1.0 for the five genuine holes vs. 0.53 for the false positive), but this is a single false-positive example, not strong evidence for a generally safe numeric threshold.

## 6. Implementation Plan

**Step 1 (this document):** analysis and plan only — complete.

**Step 2 (proposed, pending your approval of which variant to build):** two options, not yet implemented:
- **Option A — tolerance widen only, gated by mandatory visual review.** Change `MATCH_TOL_PX` to 690px (the single, minimal constant change). Before considering the change complete, visually review every hole newly matched by the wider tolerance across all 79 cartridges (not just the 6 found today — the same change could affect any future cartridge) and require explicit sign-off per case, exactly as Cartridge 45/Tag6 was caught here.
- **Option B — tolerance widen plus a quality gate.** Same constant change, plus: a newly-matched candidate for a *previously-missing* tag is only accepted if it also meets a minimum near-nominal ratio (e.g., `near_nominal_count / n_rays >= 0.7`, which admits all 5 genuine cases at 0.94–1.0 and excludes the one false positive at 0.53). This reuses only already-computed values (no new computation), matching this project's established constraint, but introduces one new numeric threshold chosen from a single negative example — its generality has not been tested beyond this one case.

I have not chosen between these for you — this is a genuine design decision (blanket visual QA process vs. an in-algorithm statistical gate) that should be approved explicitly, consistent with how every other change in this project has been decided.

**Step 3 (after approval, not yet started):** implement the approved option, in isolation (this constant/gate only — no other change bundled in).

**Step 4 (after approval, not yet started):** validation, using the same protocol every fix in this project has followed:
- `py_compile` + import verification.
- Full regression on 1–33, 34–50, 51–79 comparing every row against the current (pre-change) baseline.
- **Expected differences:** exactly the 6 tags in §5 change from `missing` to `matched` (or 5, if Option B correctly excludes Cartridge 45/Tag6). Zero other rows should change — this is a direct, checkable prediction, not a hope.
- **Cross-tag contention check:** confirm no cartridge shows two different tags matched to the same underlying candidate (should be structurally impossible per the 1393.9px proof, but verify empirically anyway, as this project's history has repeatedly shown structural guarantees are worth re-confirming empirically).
- **Visual confirmation** for every newly-matched hole (not just the 6 known today), the same standard applied throughout this project — no conclusion from statistics alone.
- **Precision check:** explicitly confirm no previously-correct measurement changed, and no false positive was introduced (this is precisely what would have been missed if Cartridge 45/Tag6 hadn't been checked visually).

## 7. Explicit Non-Goals for This Change

- Does not address the 14 outside-frame cases (56% of all missing holes) — these require a different, larger, and separately-scoped investigation into the geometric/pattern-matching model itself.
- Does not address the 5 farther in-tolerance-gap cases (Cartridge 33/Tag7, 45/Tag7, 50/Tag3, 50/Tag7, 72/Tag4) — recoverable only by exceeding the proven-safe tolerance ceiling, which would reintroduce cross-tag contention risk and needs its own dedicated analysis.
- Does not address diameter accuracy for already-matched holes (Cartridge 51/Tag4, 66/Tag6 from Stage 5) — unrelated to recall, still blocked on independent reference data.
- Does not touch Hough parameters, preprocessing, Stage 1 anchor-selection logic, or Stage 2 ranking logic themselves — only the shared `MATCH_TOL_PX` constant (and, if Option B is chosen, one new acceptance gate applied only to newly-recovered tags).

Nothing has been implemented. Waiting for approval on which implementation option (A or B) to build before any code is touched.
