# Stage 7 — Blast-Radius Analysis (Corrected Rerun)

**Status:** Analysis complete. No production code modified. Nothing implemented.
**Branch:** `stage7-geometric-model-investigation` (no commits).
**Supersedes:** `STAGE7_ANCHOR_REDESIGN_BLAST_RADIUS_ANALYSIS.md`, whose analysis script contained a tie-break bug (disclosed there, fixed here).
**Scope of the fix:** only the standalone analysis script (`stage7_blast_radius_analysis.py` in the session scratchpad) was modified. `detect_features.py` and every other production file are untouched — the "proposed" algorithm has never been run anywhere except inside this read-only script.

---

## 1. What Was Fixed

The prior script's tie-break for the role-generalized anchor search ended with:

```python
tiebreak = (cand_fallback_rank, cand_near_ratio, -total_dist, 1 if role != 9 else 0)
```

Since the comparison keeps the *larger* tuple, `1 if role != 9 else 0` gave non-9 roles a higher value than role 9 — i.e., on an exact tie, a non-9 role would win, the opposite of the documented design intent ("role = 9 preferred last... reproduces today's default on a full tie"). Corrected to:

```python
role_pref = 1 if role == 9 else 0
tiebreak = (cand_fallback_rank, cand_near_ratio, -total_dist, role_pref)
```

The full 79-cartridge comparison (current algorithm vs. proposed, both carried through the same faithfully-replicated Stage 2 and recovery pass) was then rerun from scratch with this fix, independently of the previous (buggy) run's output.

---

## 2. Corrected vs. Buggy: Direct Comparison

| | Buggy run | Corrected run |
|---|---|---|
| Cartridges with identical final assignments | 74 / 79 | **74 / 79** |
| Cartridges with changed assignments | 5 / 79 | **5 / 79** |
| Set of changed cartridges | {18, 48, 49, 66, 72} | **{18, 48, 49, 66, 72} — identical set** |
| "Anchor differs, assignments identical" count | 71 / 74 | **71 / 74 — identical count** |

**Every one of the 5 changed cartridges' results is byte-identical between the buggy and corrected runs** — same anchor, same role, same matched count, same missing-tag reasons, and the same specific per-tag candidate positions in every `changed_tags` entry, verified field-by-field. The tie-break bug had **zero effect** on any cartridge's outcome in either the 74 "identical" group or the 5 "changed" group.

**Why:** the bug only activates when two (candidate, role) hypotheses are tied on match count *and* on the anchor candidate's own quality *and* on total residual distance — a four-way exact tie. Across all 79 cartridges, no such tie actually occurred; whichever hypothesis won did so on an earlier tie-break level (usually candidate quality or residual), never reaching the buggy final tiebreaker. The separately-observed "different literal anchor value, identical practical result" phenomenon (71/74 cartridges) is a different, unrelated, and expected effect: with a 600px match tolerance and typical real-hole position noise of only a few to ~11px, many different genuine candidates — each tried under a different assumed role — independently arrive at nearly the same implied anchor and go on to match the identical real candidates regardless of which one is technically selected. This was already the working explanation in the prior report and is now confirmed unaffected by the bug fix.

**Conclusion: the previous report's findings were not an artifact of the disclosed bug.** They stand, and are restated below with the corrected run's data (identical in every particular to the buggy run's data).

---

## 3. Regression / Change Table (all 5 changed cartridges)

| Cartridge | Tags changed | Previous (buggy-analysis) result | Corrected result | Classification |
|---|---|---|---|---|
| 1-33/18 | Tag 4 | (2292,572) n_hit 24/36 → (2416,1036) n_hit 36/36 | **Identical to previous** | Improvement |
| 34-50/48 | Tags 1,3,4,6,7,9 | Mixed: Tag4 improved, Tag9 n_hit 16→3 (degraded), Tag7 dropped, Tags1/3/6 newly matched at poor-moderate quality | **Identical to previous** | Ambiguous |
| 34-50/49 | Tags 1,3,4,6,9 | Tag9 (36/36, PASS) dropped entirely; Tags1,3,4,6 newly matched, mixed quality (one 36/36, one total_failure) | **Identical to previous** | Ambiguous |
| 61-70(1)/66 | Tag 9 | (5812,2392) n_hit 20/36 FAIL(0.5525mm) → (6324,2332) n_hit 9/36 PASS(0.5200mm) | **Identical to previous** | **Regression** |
| 71-79/72 | Tags 1,3,4,5,6,7,9 | 6 tags corrected to genuine perfect-quality holes; Tag9 newly matched to a moderate-quality (19/36) non-genuine candidate | **Identical to previous** | Major improvement + 1 isolated new minor concern |

No cartridge's classification changes as a result of the bug fix. No new regressions were introduced or revealed by the corrected run.

---

## 4. Cartridge 66 — Does the PASS→FAIL Regression Still Exist? (Requirement 6)

**Yes, unchanged.** Tag 9's assignment is byte-identical to the buggy run: current algorithm matches (5812,2392) — diameter 0.5525mm, **FAIL** (borderline, 0.0025mm over the 0.55mm ceiling); proposed algorithm matches (6324,2332) — diameter 0.5200mm, **PASS**. The regression is real, not a bug artifact.

### Root-Cause Analysis (Requirement 8)

This was investigated down to the exact competing candidates:

- **The proposed algorithm's winning pivot** (tried under role = Tag 4) is the raw candidate at **(2380, 940) — 36/36 ray hits, 100% near-nominal ratio: a clean, high-confidence detection.**
- **The current algorithm's own anchor** (tried, as always, under role = Tag 9) is the raw candidate at **(6324, 2332) — 9/36 ray hits, 13.9% near-nominal ratio: a poor, borderline detection.**

The proposed algorithm's tie-break correctly and reasonably preferred the far higher-quality pivot (36/36 vs. 9/36) — this part of the decision is sound in isolation, and is exactly what the quality-based tie-break was designed to do.

The regression arises as a **side effect**, not a flaw in that preference: switching pivots from (6324,2332)-as-anchor to (2380,940)-as-Tag4 shifts the implied predicted position for Tag 9 from (6324,2332) to (6647,2048) — about 430px of movement, an entirely ordinary amount given that any single real candidate carries a few to a few hundred pixels of its own position noise relative to the "ideal" fixed geometric model. Under the **old** anchor, the good-quality candidate (5812,2392) sat 515px away — within Stage 2's fixed 600px re-ranking radius, so Stage 2 was able to swap the poor raw anchor candidate out for this better one, producing today's (already-borderline) FAIL. Under the **new** anchor, that same good candidate is now 903px away — **outside** the 600px window — so Stage 2 can no longer reach it, leaving only the nearer-but-worse candidate at (6324,2332) (430px away), which happens to be exactly the position of the current algorithm's own low-quality anchor.

**The exact algorithmic decision responsible:** Stage 2's re-ranking search radius is a fixed absolute distance (`MATCH_TOL_PX` = 600px) around whichever position the *currently selected* anchor predicts for a tag — it does not adapt to, or account for, the possibility that a different (and independently superior) pivot choice elsewhere in the model will shift that fixed window just enough to exclude a specific tag's best available candidate while including a worse one. Improving the pivot's own quality does not guarantee improving — and can, as here, incidentally worsen — the specific downstream match for a different tag, because the two are only loosely coupled through a fixed-radius window rather than jointly optimized. This is a structural property of the proposed design as currently specified, not a coding defect. **No fix is proposed here, per your instruction.**

---

## 5. Cartridge 72 — Is Tag 9 Still Incorrectly Matched? (Requirement 7)

**Yes, unchanged.** Tag 9 is matched to (6052,1400) — 19/36 ray hits, 36.1% near-nominal ratio — identical to the buggy run. This is not the confirmed genuine Tag 9 feature (established in the geometric-model investigation to be an oversized, non-circular feature that no Hough candidate corresponds to); it is a different, moderate-quality candidate that happens to fall within the new anchor's tolerance. As previously reported, this is a much smaller, self-contained problem than today's — it does not corrupt any of the other 6 (now correctly identified) tags — but it does mean Tag 9 is reported as a false PASS (0.5250mm) rather than the more honest `not_detected`.

All 6 of the other tags (1,3,4,5,6,7) remain correctly and precisely matched, identical to the buggy run's findings and to the independently-established ground truth from the verification report.

---

## 6. Updated Cartridge Summary

| Cartridge | Status |
|---|---|
| 74 cartridges (all except the 5 below) | **Unaffected — byte-identical measurements and PASS/FAIL, confirmed both before and after the tie-break fix** |
| 1-33/18 | **Improved** — a moderate-quality match replaced by a perfect one; PASS/FAIL unchanged |
| 71-79/72 | **Major improvement** — 6 of 7 tags corrected to genuine, verified holes; 1 isolated new minor false-positive on Tag 9 (previously `not_detected`, now a false PASS) |
| 34-50/48 | **Ambiguous** — mixed quality changes; already known to belong to a separate, poorly-understood failure cluster; requires visual review |
| 34-50/49 | **Ambiguous** — highest uncertainty; a previously good (36/36, PASS) measurement is lost outright; requires visual review |
| 61-70(1)/66 | **Confirmed regression** — Tag 9 PASS/FAIL flips using a lower-quality candidate; root cause fully understood (§4); not resolved |

---

## 7. GO / CONDITIONAL GO / NO GO

**CONDITIONAL GO — unchanged from the prior (buggy) analysis's recommendation, now confirmed on a corrected basis.**

The bug fix changed nothing material: the same 74 cartridges are safe, the same 2 cartridges show genuine improvement, the same 2 cartridges are ambiguous, and the same 1 cartridge (66) shows a real, now root-caused regression. Per your instruction, this analysis does not by itself qualify as "no remaining regressions except Cartridge 72" — Cartridge 66's regression is confirmed to persist, so the redesign is **not** yet ready to be called algorithmically stable, and implementation should not proceed until:

1. Cartridge 66's regression (§4) is resolved — most plausibly by making Stage 2's re-ranking radius, or the anchor tie-break itself, aware of the total effect on *all* matched tags rather than only the chosen pivot's own quality and the aggregate residual, but no such fix is proposed here.
2. Cartridges 48 and 49 receive the visual review already recommended, given their independently-documented distinct failure mode.
3. Cartridge 72's new, isolated Tag 9 false-match is addressed before rollout, even though it is a much smaller concern than the current production behavior it would replace.

No production code was modified in the course of this analysis. Stopping here per your instruction.
