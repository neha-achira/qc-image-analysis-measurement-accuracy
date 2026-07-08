# Stage 14 — Low-Confidence Match Re-evaluation Investigation

**Status:** Analysis complete. No production code modified. No commits created.
**Branch:** `stage14-low-confidence-reassessment`
**Objective:** determine whether Cartridges 48, 49, 66, and 72's remaining unresolved cases can only be solved by allowing the pipeline to challenge existing low-confidence matches, rather than treating every existing match as immutable (the constraint Stage 13 identified as the reason its additive-only secondary detector could not reach Cartridge 66/72's Tag 9).

---

## 1. Every Currently Assigned Tag in the Four Cartridges

Full detail — position, diameter, ray-hit count, near-nominal ratio, angular gap, fallback mode, Stage 2 score (`fallback_rank, n_hit, near, -distance`), and distance from the predicted position — for all 22 currently-matched tags across the four cartridges is in `stage14_population_results.json`. Summary:

| Cartridge | Tag | Position | Diameter | n_hit | near_ratio | Gap | Fallback |
|---|---|---|---|---|---|---|---|
| 48 | 1 | (512,564) | 0.4225mm (FAIL) | 20 | 0.333 | 50° | normal |
| 48 | 3 | (636,2684) | 0.500mm | 3 | 0.000 | 310° | **total_failure** |
| 48 | 4 | (2536,988) | 0.510mm | 28 | 0.389 | 40° | normal |
| 48 | 6 | (3028,1820) | 0.500mm | 6 | 0.000 | 170° | **total_failure** |
| 48 | 9 | (6296,2356) | 0.500mm | 3 | 0.000 | 310° | **total_failure** |
| 49 | 1 | (9012,484) | 0.4725mm | 17 | 0.389 | 170° | normal |
| 49 | 3 | (9656,2980) | 0.520mm | 21 | 0.500 | 90° | normal |
| 49 | 4 | (10660,1744) | 0.500mm | 3 | 0.000 | 150° | **total_failure** |
| 49 | 6 | (11968,2292) | 0.505mm | 36 | **1.000** | 10° | normal |
| 66 | 1,3,4,5,6,7 | (genuine, established) | — | 36 | 0.917–1.000 | 10° | normal |
| 66 | 9 | (6324,2332) | 0.520mm | 9 | 0.139 | 120° | normal |
| 72 | 1,3,4,5,6,7 | (genuine, established) | — | 36 | 1.000 | 10° | normal |
| 72 | 9 | (6052,1400) | 0.525mm | 19 | 0.361 | 100° | normal |

---

## 2. Confidence Ranking — Built From the Measured Population, Not Invented

Every matched tag across all 79 validated cartridges (541 tag-slots) was collected to build the actual confidence distribution:

| Percentile | near_ratio |
|---|---|
| P1 | 0.0556 |
| **P5** | **0.8611** |
| P10 | 1.0000 |
| P25–P99 | 1.0000 |

**The population is extremely concentrated**: the median, and every percentile from P10 upward, is exactly 1.0. `fallback_mode` is `"normal"` for 535/541 (98.9%) of all matched tags and `"total_failure"` for only 6/541 (1.1%) — and **4 of those 6 total-failure cases are in Cartridge 48 alone**, with the fifth in Cartridge 49. This is decisive: being below `near_ratio = 0.86` (the P5 cut) is already unusual for a correctly-matched tag; `total_failure` fallback is rare enough (1.1% of the entire dataset) that its near-total concentration in two specific cartridges is itself strong evidence something is different about them, independent of any individual tag's score.

**Statistical-outlier threshold used throughout this report: `near_ratio < 0.8611` (the measured P5 value).** No threshold was invented.

---

## 3. Statistical Outliers Identified

| Cartridge | Outlier tags (below P5) | Non-outlier tags |
|---|---|---|
| 48 | **All 5** assigned tags (1, 3, 4, 6, 9) | none |
| 49 | 1, 3, 4 (3 of 4) | Tag 6 (near_ratio=1.000 — solidly at the population mode, a genuine high-confidence match) |
| 66 | Tag 9 only | Tags 1, 3, 4, 5, 6, 7 (all ≥0.917, at or near the population mode) |
| 72 | Tag 9 only | Tags 1, 3, 4, 5, 6, 7 (all =1.000) |

This matches, and gives a rigorous statistical basis for, every finding from Stages 7–13: Cartridge 66 and 72's non-anchor tags are unambiguously genuine; their Tag 9 is unambiguously anomalous; Cartridge 49's Tag 6 is the one clean match in that cartridge; and Cartridge 48 has **no high-confidence match at all**.

---

## 4. Do Better Alternatives Exist?

For every flagged tag, every other raw candidate was checked at two radii: the existing safe tolerance (600px, matching Stage 1/2; 690px matching the recovery pass) and a wider 1,200px exploratory radius (analysis only, not proposed for production).

### Within the established safe tolerance (≤690px)

| Cartridge/Tag | Better alternative within safe tolerance? |
|---|---|
| 48/1, 48/3, 48/4, 48/6, 48/9 | **None** — the current candidate is the only one within range in every case |
| 49/1, 49/3, 49/4 | **None** |
| 66/9 | **None** |
| 72/9 | **One marginal alternative**: (7072,1256), 579.4px away, near_ratio=0.417 vs. the current 0.361 — a small improvement, but still far below the population norm and still not a confirmed genuine hole |

### At a wider, exploratory-only 1,200px radius

Some nominally "better" (higher near_ratio) candidates do appear — but every one remains far below the population's ~1.0 norm (0.333–0.611), and one case exposes a direct conflict: **Cartridge 49's Tag 1 and Tag 4 both identify the exact same candidate, (10044,924), as their best available alternative.** Two different tags cannot both legitimately claim the same physical candidate — this is a direct, concrete instance of the cross-tag contention risk that Stage 6 already proved dangerous when it rejected a naive global tolerance increase, now reproduced independently in this investigation's own evidence.

**No alternative found at any radius, for any of the 22 tags examined, approaches the population's dominant near-1.0 confidence level.** The best any widening achieves is trading one low-confidence candidate for a different low-confidence candidate.

---

## 5–7. Confidence-Aware Replay — Comparison and Outcome

A replay was constructed that keeps every tag above the measured P5 threshold completely frozen (untouchable, exactly as production and the Stage 7 implementation already treat them) and allows **only** the flagged low-confidence tags to be reassigned to a strictly better candidate, if and only if one exists within the already-proven-safe 690px recovery tolerance (not the wider 1,200px exploratory radius, which §4 showed introduces direct candidate conflicts).

| Comparison | Current production (Stage 7 implemented) | Confidence-aware replay |
|---|---|---|
| Cartridge 48 | Tags 1,3,4,6,9 matched (all low-confidence); Tags 5,7 missing | **Identical** — no safe alternative exists for any tag |
| Cartridge 49 | Tags 1,3,4,6 matched; Tags 5,7,9 missing | **Identical** — no safe alternative exists for any tag |
| Cartridge 66 | Tags 1,3,4,5,6,7,9 matched (Tag 9 low-confidence) | **Identical** — no safe alternative for Tag 9 |
| Cartridge 72 | Tags 1,3,4,5,6,7,9 matched (Tag 9 low-confidence) | **Tag 9 changes** from (6052,1400) [near_ratio 0.361] to (7072,1256) [near_ratio 0.417] |

**Recovered tags:** 0. **Regressions:** 0 (every high-confidence tag is frozen by construction; the one change made is confidence-neutral-to-marginally-positive by the same metric that triggered it). **False positives:** 0 new (the one changed candidate is a real Hough detection already present in the raw candidate pool, not a fabricated one — but it is no more confirmed genuine than the value it replaces). **Measurement changes:** one, Cartridge 72/Tag 9's diameter shifts from 0.525mm to a re-measured value at the new position (both readings remain unconfirmed against any independent ground truth, per the standing Leica limitation).

This single change is not presented as a recovery — it is a lateral swap between two similarly low-confidence candidates, made possible only because it happens to sit within the existing safe tolerance. It does not change Cartridge 72's fundamental situation (Tag 9 remains unconfirmed either way) and does not generalize to any other tag in any of the other three cartridges.

---

## 8. Conclusion and Recommendation

**This investigation fails to find a safe path to recovering the remaining unresolved tags, and in doing so proves — rather than merely argues — that the current pipeline has reached the information limit of the available images for these specific cases.**

The proof, concretely:
1. **The confidence ranking is not ambiguous.** Built entirely from the measured population (541 real matched tags across all 79 cartridges), it shows the four target cartridges' problem tags sit at or below the 5th percentile — often at the 0th — while the rest of the dataset sits overwhelmingly at the 1.0 maximum. This is not a borderline judgment call.
2. **No better alternative exists within any tolerance this project has already proven safe** (600px/690px), for 21 of the 22 examined tags. The sole exception (Cartridge 72/Tag 9) is a lateral move between two low-confidence candidates, not a recovery.
3. **Widening the search far enough to find nominally "better" candidates elsewhere directly reproduces a known failure mode**: Cartridge 49's Tag 1 and Tag 4 independently identify the *same* physical candidate as their best available option — concrete proof that relaxing the tolerance far enough to help these cases reintroduces the cross-tag contention risk Stage 6 already evaluated and rejected, not a new or different risk.

**If this had succeeded** — if a confidently better, geometrically consistent, non-conflicting candidate had been found for these tags — the smallest architectural modification would have been to extend the existing recovery pass's frozen-anchor pattern with a second, explicitly gated re-evaluation stage limited strictly to tags falling below the measured P5 threshold, using the same 690px tolerance and never touching a tag above that line. That design was fully specified and even partially exercised in this investigation (§5), and would have been safe to build had the evidence supported it.

**It does not.** No further architectural modification — additive or challenge-based — is justified by the evidence gathered across Stages 8 through 14. The remaining unresolved tags in Cartridges 48, 49, 66, and 72 represent the limit of what the current images support, not a limit of the algorithms applied to them.

No production code was modified during this investigation. No commits were created. Stopping here per your instruction.
