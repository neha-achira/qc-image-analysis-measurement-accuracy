# Stage 7 — Role-Generalized Stage 1 Anchor Search: Implementation Validation Report

**Status:** Implemented in the working tree. **Not committed.** Validation complete.
**Branch:** `stage7-geometric-model-investigation` (working-tree changes only — `git status` confirms no commits, only `detect_features.py` modified).
**Implements:** `docs/STAGE7_ANCHOR_SELECTION_REDESIGN.md` (Approach 5), exactly as validated in `docs/STAGE7_CARTRIDGE72_FOCUSED_DESIGN_FINAL.md`.

---

## 1. Change Summary

Replaced only the Stage 1 anchor-selection loop in `detect_holes()` (previously: "try each candidate assuming it is Tag 9"). The new loop tries every raw candidate against every one of the 7 tag roles, computing the implied anchor as `candidate − REF_OFFSETS[role]`, and scores each hypothesis with the **unmodified** `_score_anchor` function and the **unmodified** `MATCH_TOL_PX` tolerance. Ties are broken by: (1) the anchor candidate's own `fallback_mode`, (2) its own near-nominal ratio, (3) lowest total match distance, (4) role = 9 preferred last.

**Confirmed untouched, per requirements 1–5:**
- `_score_anchor`, `_predict_positions`, `MATCH_TOL_PX` — byte-identical.
- Stage 2 ranking refinement (`_stage2_rank_key` and its usage) — untouched.
- The recovery pass — untouched.
- Missing-hole diagnostics — untouched.
- `git diff --stat`: **1 file changed, 35 insertions, 12 deletions** — `detect_features.py` only. No other file modified.

---

## 2. Compile and Import

```
python -m py_compile detect_features.py   →  OK
python -c "import detect_features"        →  OK
```

---

## 3. Full Regression — All 79 Validated Cartridges

Run via the actual production `detect()` entry point (not a replay script), comparing the exact pre-change committed version (git `HEAD`) against the modified working tree, across 1–33, 34–50, 51–60, 61–70(1), 71–79 (553 tag-slots total).

**Result: 5 of 79 cartridges changed — exactly the same 5 cartridges, and exactly the same per-tag changes, predicted by both prior blast-radius analyses (`STAGE7_ANCHOR_REDESIGN_BLAST_RADIUS_ANALYSIS.md` and its corrected rerun).** No discrepancy between the replay-based predictions and this real-production-code regression was found.

### Cartridges unaffected: 74 / 79

Every matched-tag position, `diameter_mm`, `pass`, and every `missing_holes` reason is byte-identical to current production for all cartridges except the 5 below.

### 1-33 / Cartridge 18 — 1 tag changed

| Tag | Before | After |
|---|---|---|
| 4 | (2292,572), 0.4650mm, **PASS** | (2416,1036), 0.4725mm, **PASS** |

No PASS/FAIL change. A moderate-quality match replaced by a higher-quality one (confirmed in prior investigation: 24/36 → 36/36 ray-cast quality).

### 34-50 / Cartridge 48 — 6 tags changed

| Tag | Before | After |
|---|---|---|
| 1 | missing (`outside_image`) | (512,564), 0.4225mm, **FAIL** *(new)* |
| 3 | missing (`not_detected`) | (636,2684), 0.5000mm, **PASS** *(new)* |
| 4 | (1060,676), 0.5000mm, PASS | (2536,988), 0.5100mm, PASS |
| 6 | (2152,2428), 0.5000mm, PASS | (3028,1820), 0.5000mm, PASS |
| 7 | (2644,3896), 0.5000mm, **PASS** | missing (`not_detected`) *(lost)* |
| 9 | (5416,2148), 0.5225mm, PASS | (6296,2356), 0.5000mm, PASS |

**Unexpected behavior flagged:** Tag 1 is a **new FAIL** that did not exist in any form before (previously simply missing). This specific outcome was not called out explicitly in the prior blast-radius reports (which focused on Tag 9's quality degradation for this cartridge). Per the already-documented finding that Cartridge 48 belongs to a separate, poor-image-quality cluster with no independently-confirmed ground truth, this cannot be classified as a regression from a known-correct state — but it is a new, previously-unseen FAIL result and should be visually reviewed, consistent with the standing recommendation for this cartridge.

### 34-50 / Cartridge 49 — 6 tags changed

| Tag | Before | After |
|---|---|---|
| 1 | missing (`outside_image`) | (9012,484), 0.4725mm, **PASS** *(new)* |
| 3 | missing (`outside_image`) | (9656,2980), 0.5200mm, **PASS** *(new)* |
| 4 | missing (`outside_image`) | (10660,1744), 0.5000mm, **PASS** *(new)* |
| 6 | missing (`outside_image`) | (11968,2292), 0.5050mm, **PASS** *(new)* |
| 7 | missing (`outside_image`) | missing (`not_detected`) | reason changed only |
| 9 | (392,1956), 0.5125mm, **PASS** | missing (`outside_image`) *(lost)* |

A previously good-quality (36/36), PASS measurement for Tag 9 is lost with nothing to replace it. As documented in the corrected blast-radius report, this cartridge contains two mutually-inconsistent perfect-quality candidates that cannot both be genuine under one consistent model — this remains an open, separately-scoped question, unresolved by (and not caused by) this change.

### 61-70(1) / Cartridge 66 — 1 tag changed (deferred per your standing instruction)

| Tag | Before | After |
|---|---|---|
| 9 | (5812,2392), 0.5525mm, **FAIL** | (6324,2332), 0.5200mm, **PASS** |

Confirmed, real-production-code reproduction of the already root-caused, already-deferred regression (`STAGE7_CARTRIDGE66_ROOT_CAUSE_INVESTIGATION.md`). Per your instruction, not re-analyzed here.

### 71-79 / Cartridge 72 — 7 tags changed (the objective)

| Tag | Before | After |
|---|---|---|
| 1 | missing (`outside_image`) | (644,416), 0.5200mm, **PASS** *(recovered)* |
| 3 | missing (`outside_image`) | (1084,3080), 0.5300mm, **PASS** *(recovered)* |
| 4 | missing (`not_detected`) | (2456,756), 0.4700mm, **PASS** *(recovered)* |
| 5 | missing (`outside_image`) | (2396,5444), 0.5300mm, **PASS** *(recovered)* |
| 6 | (1084,3080) — Tag 3's genuine hole, mislabeled — 0.5300mm, PASS | (3440,1760) — its own genuine hole — 0.4675mm, **PASS** *(corrected)* |
| 7 | (2144,5072) — low-quality substitute — 0.5700mm, **FAIL** | (3780,3116) — its own genuine hole — 0.5100mm, **PASS** *(corrected)* |
| 9 | (4836,3412), 0.6150mm, **FAIL** | (6052,1400), 0.5250mm, **PASS** — *out of scope, not confirmed genuine* |

**All 6 in-scope target tags (1,3,4,5,6,7) are now correctly recovered/corrected**, matching the objective exactly. Two additional facts not previously highlighted in real production terms: Tag 7 was actually reported as an outright **FAIL** before this change (0.5700mm, using the wrong low-quality candidate) — now correctly measured as a PASS using its genuine hole. Tag 9 also flips FAIL→PASS, but per your requirement 1, this is explicitly out of scope and not claimed as a correct result.

---

## 4. Recovered Holes (previously missing, now matched)

| Cartridge | Tag | Position | Diameter | PASS/FAIL |
|---|---|---|---|---|
| 72 | 1 | (644,416) | 0.5200mm | PASS |
| 72 | 3 | (1084,3080) | 0.5300mm | PASS |
| 72 | 4 | (2456,756) | 0.4700mm | PASS |
| 72 | 5 | (2396,5444) | 0.5300mm | PASS |
| 48 | 3 | (636,2684) | 0.5000mm | PASS |
| 49 | 1 | (9012,484) | 0.4725mm | PASS |
| 49 | 3 | (9656,2980) | 0.5200mm | PASS |
| 49 | 4 | (10660,1744) | 0.5000mm | PASS |
| 49 | 6 | (11968,2292) | 0.5050mm | PASS |

(Cartridge 48/Tag1 is a new **matched-but-FAIL** result, not a "recovered" hole in the sense of a confirmed correct measurement — listed separately in §3, not included here.)

---

## 5. PASS/FAIL Flips (on tags matched both before and after)

| Cartridge | Tag | Before | After | Note |
|---|---|---|---|---|
| 72 | 7 | FAIL (0.5700mm) | PASS (0.5100mm) | Correction — genuine hole now measured instead of a low-quality substitute |
| 72 | 9 | FAIL (0.6150mm) | PASS (0.5250mm) | Out of scope per requirement 1 — not confirmed genuine either way |
| 66 | 9 | FAIL (0.5525mm) | PASS (0.5200mm) | Deferred per your standing instruction — already root-caused |

No other previously-matched tag changes its PASS/FAIL status. In particular, all 6 of Cartridge 72's in-scope target tags either newly pass (having been unmeasured before) or, for Tag 6, remain PASS with a corrected identity.

---

## 6. Any Unexpected Behavior

- **Cartridge 48/Tag 1** produces a new FAIL result that did not exist in any form previously (§3) — flagged for visual review, not previously called out at this level of specificity in prior reports.
- **Cartridge 72/Tag 7's prior FAIL status** (0.5700mm) was not explicitly stated as a FAIL in earlier investigation stages (which focused on identity mismatch, not the resulting PASS/FAIL) — now confirmed and corrected as part of this same fix.
- No crashes, exceptions, or anomalous console output occurred across any of the 79 cartridges.
- No cartridge outside the same 5 already identified by both prior replay-based analyses showed any change — full agreement between replay predictions and real production-code execution.

---

## 7. Summary

| | Result |
|---|---|
| py_compile | OK |
| import | OK |
| Cartridges regression-tested | 79 / 79 |
| Cartridges unaffected | 74 / 79 |
| Cartridge 72 (objective) | **All 6 target tags (1,3,4,5,6,7) recovered/corrected — objective met** |
| Cartridge 18 | Improved, no PASS/FAIL change |
| Cartridge 66 | Deferred regression persists, unchanged from prior root-cause analysis |
| Cartridges 48/49 | Changed; pre-existing, separately-scoped ambiguity (not newly created); one new FAIL (48/Tag1) flagged for review |
| Files modified | `detect_features.py` only (35 insertions, 12 deletions) |
| Commits created | **None** |

No production code beyond `detect_features.py`'s Stage 1 anchor loop was touched. No commit was made. Stopping here per your instruction.
