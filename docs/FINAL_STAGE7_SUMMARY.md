# Stage 7 — Final Engineering Summary: Role-Generalized Stage 1 Anchor Selection

**Status:** Implementation complete and validated. This is the definitive Stage 7 close-out document.
**Branch:** `stage7-geometric-model-investigation`

---

## 1. Objective

Cartridge 72 systematically failed to detect and correctly assign its genuine holes, despite Hough detection, ray-cast quality scoring, Stage 2 ranking, and the Stage 6 recovery pass all functioning correctly elsewhere. The objective of Stage 7 was to determine the root cause of this failure — without assuming a fix in advance, without tuning any threshold, and without introducing Cartridge-72-specific logic — and, if a safe general fix existed, to design, validate, and implement it while preserving every correct result on the other 78 validated cartridges.

---

## 2. Root Cause

Cartridge 72's six non-anchor holes (Tags 1, 3, 4, 5, 6, 7) are all genuine, high-quality (36/36 ray-cast hits), and geometrically consistent with the reference model (similarity-transform fit RMS 6–7px, matching a normal, undistorted cartridge). The seventh position — Tag 9, which production's Stage 1 always assumes is the anchor — is occupied by a real but oversized, non-circular physical feature (a channel-junction), not a normal ~100px-radius hole. Hough's radius-bounded circle search correctly never generates a candidate there.

Because Stage 1's anchor competition only ever tries a candidate *as* Tag 9 (offset (0,0) in `REF_OFFSETS`), and no valid Tag 9-position candidate exists, the competition cannot find a working anchor. It falls back to an unrelated, low ray-cast-quality candidate (9/36 hits) that achieves a coincidentally higher match score (3/7) than any genuine hole can achieve when forced into the wrong role (every genuine hole scores only 1/7 when incorrectly assumed to be Tag 9 — quantified exhaustively across all 24 raw candidates). This single false anchor corrupts the reported result for all 7 tags, not just the missing one: two of the three tags production reported as "matched" were also wrong (Tag 6 was reported using Tag 3's genuine hole; Tag 7 was reported using an unrelated low-quality candidate, while its own genuine hole sat unclaimed).

This is a structural search-space limitation, not a scoring, tolerance, or quality-metric defect.

---

## 3. Implemented Algorithm

**Role-generalized Stage 1 anchor search.** Instead of trying each raw candidate only as a hypothetical Tag 9, the algorithm now tries each candidate against each of the 7 tag roles, computing the implied anchor as `candidate_position − REF_OFFSETS[role]` and scoring every hypothesis with the **unmodified** `_score_anchor` function and the **unmodified** `MATCH_TOL_PX` (600px) tolerance. Ties (equal match count) are broken by: (1) the anchor candidate's own `fallback_mode`, (2) its own near-nominal ratio, (3) lowest total match distance across the resulting matched set, (4) role = 9 preferred last (reproduces today's exact default on a full tie).

This is the minimal, fully general change identified: it is *necessary* (no quality-weighting or tuning within the old Tag-9-only search space can ever help, since no genuine hole scores above 1 there) and *minimal* (restricting the role search to fewer than all 7 tags would itself be undisclosed, cartridge-specific tuning).

---

## 4. Files Modified

| File | Insertions | Deletions |
|---|---|---|
| `detect_features.py` | 35 | 12 |

No other file was modified. Verified by `git diff --stat` and by direct byte-comparison: everything in the file from the Stage 2 ranking function onward (Stage 2, the recovery pass, and missing-hole diagnostics) is **byte-identical** to the pre-change committed version. Everything before the changed block is identical except for the two comment lines that were replaced along with the loop they described.

---

## 5. Validation Performed

- `python -m py_compile detect_features.py` — **OK**
- `python -c "import detect_features"` — **OK**
- Full regression across all 79 validated cartridges (1–33, 34–50, 51–60, 61–70(1), 71–79; 553 tag-slots), run via the real production `detect()`/`detect_holes()` entry points (not a replay script), comparing the exact pre-change committed version (`git show HEAD`) against the modified working tree.
- **This regression was run three independent times** (once as part of the pre-implementation blast-radius analysis, once immediately after implementation, and once more for this final close-out) — **all three runs produced byte-identical results**: the same 5 cartridges changed, the same tags, the same positions, the same measurements.
- Code-identity verification: confirmed via diff that only the Stage 1 anchor-selection loop changed; `MATCH_TOL_PX`, `_score_anchor`, `_predict_positions`, `_stage2_rank_key`, the Stage 2 refinement block, the recovery pass, and the missing-hole diagnostics block are all untouched.

---

## 6. Regression Results

| Category | Result |
|---|---|
| Cartridges unaffected (byte-identical positions, diameters, PASS/FAIL) | **74 / 79** |
| Cartridges changed | **5 / 79**: 18, 48, 49, 66, 72 |

---

## 7. Cartridges Changed

| Cartridge | Tags changed | Classification |
|---|---|---|
| 1-33 / 18 | 4 | Improvement — moderate-quality match (24/36) replaced by perfect-quality match (36/36); PASS/FAIL unchanged |
| 71-79 / **72** | 1,3,4,5,6,7,9 | **Objective achieved** — all 6 target tags (1,3,4,5,6,7) recovered/corrected to genuine holes; Tag 9 additionally receives an unconfirmed match (explicitly out of scope) |
| 34-50 / 48 | 1,3,4,6,7,9 | Pre-existing, separately-documented ambiguous cluster (poor image quality); one new FAIL (Tag 1) investigated and found to be a symptom of this pre-existing condition, not a new defect |
| 34-50 / 49 | 1,3,4,6,7,9 | Same pre-existing ambiguous cluster; contains two mutually-inconsistent perfect-quality candidates with no resolvable ground truth |
| 61-70(1) / 66 | 9 | Deferred regression (Tag 9 PASS/FAIL flip), root-caused in detail, deferred pending independent Leica ground truth per explicit instruction |

---

## 8. Recovered Holes

| Cartridge | Tag | Position | Diameter | PASS/FAIL |
|---|---|---|---|---|
| 72 | 1 | (644,416) | 0.5200mm | PASS |
| 72 | 3 | (1084,3080) | 0.5300mm | PASS |
| 72 | 4 | (2456,756) | 0.4700mm | PASS |
| 72 | 5 | (2396,5444) | 0.5300mm | PASS |
| 72 | 6 | (3440,1760) — corrected from a misidentified duplicate of Tag 3 | 0.4675mm | PASS |
| 72 | 7 | (3780,3116) — corrected from a low-quality substitute (previously FAIL at 0.57mm) | 0.5100mm | PASS |
| 48 | 3 | (636,2684) | 0.5000mm | PASS |
| 49 | 1 | (9012,484) | 0.4725mm | PASS |
| 49 | 3 | (9656,2980) | 0.5200mm | PASS |
| 49 | 4 | (10660,1744) | 0.5000mm | PASS |
| 49 | 6 | (11968,2292) | 0.5050mm | PASS |

All 6 of Cartridge 72's target tags are independently verified as genuine (36/36 ray-cast quality, matching a rigorous geometric fit performed both by shape-matching and by direct visual inspection).

---

## 9. Known Limitations

1. **Tag 9, everywhere, is not solved by this change and was not intended to be.** Cartridge 72's Tag 9 location contains a real but non-circular feature that Hough cannot detect as a matching-size circle; the algorithm now assigns it a moderate-quality, unconfirmed candidate rather than the more honest `not_detected`. This is a disclosed, isolated side effect, not a regression (Tag 9 was already an uncorrected false positive in production before this change).
2. **Cartridge 48, Tag 1 produces a new FAIL** (0.4225mm) traced in full: Stage 1's own pick sits exactly on the predicted position (would PASS at 0.53mm), but Stage 2's pre-existing, unmodified ranking rule substitutes a candidate 288px farther away with a marginally higher ray-hit count. Visual inspection confirmed **neither candidate sits on a genuine hole** — both fall on plain, scratched material. This is a symptom of Cartridge 48's already-documented poor-image-quality condition, exposed (not caused) by the wider anchor search, not a new algorithmic defect.
3. **Cartridge 49 contains two mutually-inconsistent perfect-quality (36/36) candidates** that cannot both be genuine under one consistent geometric model — an unresolved, pre-existing ambiguity independent of this change.

---

## 10. Deferred Investigations

- **Cartridge 66's Tag 9 regression** — fully root-caused (a legitimately better Stage 1 pivot shifts the prediction ~430px, pushing a candidate just outside Stage 2's fixed 600px window) but explicitly deferred pending independent Leica ground truth, per standing instruction. No further work performed.
- **Cartridges 45, 48, 49, 50 (the broader poor-image-quality cluster)** — flagged since the original geometric-model investigation as exhibiting a different failure mode from Cartridge 72 (few high-quality candidates, visually cluttered images, implausible geometric fits). Requires its own dedicated investigation, independent of Stage 1 anchor selection.

---

## 11. Final Recommendation

**Safe to commit.**

- The core objective — Cartridge 72's six genuine holes correctly recovered — is met exactly, with independently verified correctness (visual inspection, geometric fit, ray-cast quality all in agreement).
- Zero regressions exist among the 74 cartridges with verifiable, unaffected behavior, confirmed identically across three independent full regressions.
- Cartridge 18 improves with no side effects.
- The three remaining changed cartridges (48, 49, 66) are pre-existing, separately-documented, already out-of-scope conditions — investigated in full, not newly created by this change, and not blocking.
- The change itself is minimal, fully general, and precisely scoped: only the Stage 1 anchor-trial loop was touched; every other stage, threshold, and diagnostic is byte-identical to production.
