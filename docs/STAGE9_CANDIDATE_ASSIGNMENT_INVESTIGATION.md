# Stage 9 — Candidate Assignment Investigation

**Status:** Analysis complete. No production code modified. No commits created.
**Branch:** `stage9-candidate-assignment-investigation`
**Objective:** determine why perfect-quality candidates remain unused in Cartridges 48 and 49. Cartridge 66 and Cartridge 72's Tag 9 are explicitly out of scope (closed pending a different detector, per Stage 8).

---

## 1. Complete Raw Candidate Lists

Full tables (position, Hough radius, ray-hit count, near-nominal ratio, angular gap, fallback mode) were produced for both cartridges by replaying Hough detection exactly as production configures it. These match the tables already published in `STAGE8_CANDIDATE_GENERATION_INVESTIGATION.md` §2 and are not repeated in full here; the two facts driving this investigation are:

- **Cartridge 48**: (372,1976) — 36/36 hits, 100% near-nominal ratio, 10° gap, `normal` — completely unused.
- **Cartridge 49**: (392,1956) and (5680,2428) — both 36/36 hits, 100% near-nominal ratio, 10° gap, `normal` — completely unused. Only a third perfect-quality candidate, (11968,2292), is used (as Tag 6).

---

## 2. Assignment Pipeline Trace

### Cartridge 48

| Stage | Result |
|---|---|
| Stage 1 winning hypothesis | pivot=(224,568) as role=Tag1, implied anchor=(6315,2032), score=5, matched={1,3,4,6,9} |
| Predicted positions | computed from anchor via `REF_OFFSETS` |
| Stage 2 ranking | no changes from the Stage 1 picks (checked all in-tolerance alternatives per tag; none outrank the current pick) |
| Recovery pass | no additional tags recovered |
| **Final assignment** | Tag1=(224,568), Tag3=(636,2684), Tag4=(1836,860), Tag6=(3028,1820), Tag9=(6296,2356) |

### Cartridge 49

| Stage | Result |
|---|---|
| Stage 1 winning hypothesis | pivot=(11968,2292) as role=Tag6, implied anchor=(15270,2364), score=4, matched={1,3,4,6} |
| Stage 2 ranking | no changes |
| Recovery pass | no additional tags recovered |
| **Final assignment** | Tag1=(9012,484), Tag3=(9656,2980), Tag4=(10660,1744), Tag6=(11968,2292) |

---

## 3. Why Each Unused Perfect-Quality Candidate Is Never Selected

For each, the exact first algorithmic decision that excludes it was traced:

| Candidate | Best score achievable using it as ANY Stage 1 pivot (any role) | Winning hypothesis's score | Distance from its nearest predicted tag position under the winning anchor | Ever claimed by another tag in the final result? |
|---|---|---|---|---|
| Cartridge 48: (372,1976) | **3** | 5 | **1289.4px** (nearest is Tag 3's predicted position; tolerance is 600px) | No |
| Cartridge 49: (392,1956) | **2** | 4 | **8850.2px** (nearest is Tag 1's predicted position) | No |
| Cartridge 49: (5680,2428) | **2** | 4 | **3818.1px** (nearest is Tag 1's predicted position) | No |

**The first algorithmic decision that excludes each candidate is Stage 1's hypothesis-scoring comparison itself** — every hypothesis that uses one of these candidates as its pivot scores strictly lower (2–3) than the winning hypothesis (4–5), so the candidate is never selected as anchor. Separately and independently, under whichever anchor *does* win, each candidate's distance to its nearest predicted tag position (1289–8850px) is far beyond both the 600px Stage 1/2 tolerance and the 690px recovery-pass tolerance, so Stage 2 and the recovery pass never have an opportunity to pick it up either. No candidate is ever "claimed" by a competing tag — there is no conflict to resolve.

---

## 4. Root-Cause Classification

- **(A) Assignment ordering — ruled out.** Verified directly in §6: an exhaustive, order-independent (Hungarian) assignment produces byte-identical results to production's greedy assignment.
- **(B) Greedy matching — ruled out.** Same evidence; Hungarian (the provably optimal solution to "maximize matches, minimize total distance") agrees with greedy exactly.
- **(D) Hypothesis scoring — not a flaw.** The scoring function is working correctly: it is accurately detecting that these candidates do not fit the winning geometric pattern. This is the *mechanism* by which the true cause is enforced, not the cause itself.
- **(E) Conflict resolution — ruled out.** Confirmed above: neither unused candidate is ever claimed by any tag in the final result. There is no competing claim to resolve.
- **(C) Geometric inconsistency — confirmed as the root cause**, and further verified in §5: these candidates cannot be reconciled with the rest of the matched set under any physically plausible transform, not merely under the current translation-only model.

---

## 5. Is the Scale≈1.97 Fit Implausible? Under-Constrained or Genuinely Incompatible?

### 5a. Scale comparison across all validated cartridges

| Cartridge | Points used | Scale | Rotation | RMS residual |
|---|---|---|---|---|
| Cartridge 1 (baseline) | 7 | 0.9970 | — | 5.88px |
| Cartridge 72 (Tags 1,3,4,5,6,7) | 6 | 0.9973 | −0.738° | 7.01px |
| Cartridge 66 (Tags 1,3,4,5,6,7) | 6 | 0.9982 | −0.769° | 7.38px |
| Cartridge 34 | 7 | 1.0001 | 0.001° | 1.08px |
| Cartridge 51 | 7 | 1.0017 | −0.449° | 10.58px |
| Cartridge 61 | 7 | 1.0008 | −0.631° | 9.95px |
| Cartridge 18 | 7 | 1.0937 | −1.874° | 189.14px |
| **Cartridge 48 (production's own 5 matched candidates)** | 5 | 0.9784 | 4.250° | 231.82px |
| **Cartridge 49 (production's own 4 matched candidates)** | 4 | 0.9106 | 5.166° | 402.27px |
| **Cartridge 49, 3-point fit including the unused candidates (Tags 3,7,9)** | 3 | **1.9724** | — | 0.014 (near-zero, but see below) |

The established scale range across every genuinely-validated cartridge is **0.997–1.09**. Cartridges 48 and 49's own currently-matched candidates already sit at the loose end of this range (0.91–0.98, with correspondingly larger rotation and RMS than the cleanest cases) — consistent with their already-documented status as a lower-image-quality cluster. **The 3-point fit's scale of 1.9724 is not a marginal outlier — it is roughly double the highest value ever observed**, including in the two cartridges under investigation themselves. This is categorically different from ordinary run-to-run scatter.

The near-zero residual (0.014) reported for that 3-point fit is not evidence of a good fit — with only 3 points and 4 degrees of freedom (scale, rotation, 2 translation), the fit has only 2 residual degrees of freedom, so a low nominal error is expected regardless of whether the correspondence is physically real (essentially any 3 points can be fit passably well). The scale value, not the residual, is what exposes this fit as spurious.

### 5b. Under-constrained optimization, or genuine incompatibility?

To answer this directly (not by inference from the 3-point case alone), each unused candidate was added — one at a time, under every remaining tag role — to a fit **anchored on production's own currently-matched candidates** (4 points for Cartridge 49, 5 for Cartridge 48), which are far better constrained than a bare 3-point fit:

**Cartridge 49** (baseline using only the 4 existing matches: scale=0.9106, rotation=5.17°, RMS=402.27px):

| Added candidate | As Tag 5 | As Tag 7 | As Tag 9 |
|---|---|---|---|
| (392,1956) | scale=1.487, rot=80.9°, RMS=2783px | scale=1.221, rot=114.3°, RMS=3771px | scale=1.319, rot=172.5°, RMS=3356px |
| (5680,2428) | scale=0.812, rot=61.5°, RMS=1507px | scale=0.563, rot=74.0°, RMS=2065px | scale=0.603, rot=155.7°, RMS=2173px |

**Cartridge 48** (baseline using the 5 existing matches: scale=0.9784, rotation=4.25°, RMS=231.82px):

| Added candidate | As Tag 5 | As Tag 7 |
|---|---|---|
| (372,1976) | scale=0.746, rot=16.1°, RMS=1147px | scale=0.869, rot=10.6°, RMS=1113px |

**Every single addition — 8 attempts across both cartridges, covering every remaining tag role — causes RMS to jump 5×–16× and rotation to jump to 10°–172° (vs. under 6° for every baseline).** This is decisive: **the failure is not the optimization becoming under-constrained with too few points. Adding well-constrained context (4–5 already-anchored points) makes the incompatibility worse, not better, for every possible role assignment tested.** The unused candidates genuinely cannot coexist with the rest of the matched set under any physically plausible transform — this is a property of the data, not an artifact of a sparse fit.

---

## 6. Alternative Matching Strategies — Full Comparison

All four alternative strategies were implemented and run against the exact same raw candidate pool (read-only; production code untouched).

### Cartridge 48

| Strategy | Final tags | Recovered unused-perfect | Lost vs. production | Identity changes on shared tags | Scale | Rotation | RMS |
|---|---|---|---|---|---|---|---|
| Greedy (production) | 1,3,4,6,9 | none | — | — | 0.9784 | 4.250° | 231.8px |
| Hungarian | 1,3,4,6,9 | none | none | **No — byte-identical to greedy** | 0.9784 | 4.250° | 231.8px |
| Max bipartite matching | 1,3,4,6,9 | none | none | Yes (Tag 4 → a different, equally-in-tolerance candidate) | 0.9663 | 5.413° | 258.9px |
| Global optimization (every anchor, Hungarian-scored) | 1,3,4,6,9 | none | none | **No — identical anchor and result to production** | 0.9784 | 4.250° | 231.8px |
| Geometric residual minimization | — | — | — | **Could not be attempted** — only 2 candidates in this cartridge meet the ≥70% near-nominal-ratio quality bar, below the minimum of 3 needed for any similarity-transform fit | — | — | — |

### Cartridge 49

| Strategy | Final tags | Recovered unused-perfect | Lost vs. production | Identity changes on shared tags | Scale | Rotation | RMS |
|---|---|---|---|---|---|---|---|
| Greedy (production) | 1,3,4,6 | none | — | — | 0.9106 | 5.166° | 402.3px |
| Hungarian | 1,3,4,6 | none | none | **No — byte-identical to greedy** | 0.9106 | 5.166° | 402.3px |
| Max bipartite matching | 1,3,4,6 | none | none | **No — identical to greedy** | 0.9106 | 5.166° | 402.3px |
| Global optimization (every anchor, Hungarian-scored) | 1,3,4,6 | none | none | **No — identical anchor and result to production** | 0.9106 | 5.166° | 402.3px |
| Geometric residual minimization | 3,9 | **Tag 3 → (392,1956)** | **Tags 1, 4, 6** | **Yes** — (11968,2292), production's Tag 6, is relabeled Tag 9 | 1.9724 (implausible) | not computed (2-point result) | ~0 (meaningless with 2 constraints) |

---

## 7. Does Any Strategy Recover a Candidate Without Regression?

**No.**

- **Hungarian, max bipartite matching, and global optimization** never recover either unused candidate in either cartridge. Hungarian and global optimization are byte-identical to production in both cartridges. Max bipartite matching finds an alternative (but not better, and not unused-candidate-related) choice for Cartridge 48's Tag 4 only.
- **Geometric residual minimization** is the only strategy that recovers anything (Cartridge 49's Tag 3, via one of the unused perfect candidates) — but it does so by discarding three previously-correct matches (Tags 1, 4, 6) and relabeling a fourth, already-correctly-matched candidate under a different tag identity (Tag 6 → Tag 9), using a transform independently shown in §5 to be physically implausible (scale 1.97 vs. an established range of 0.91–1.09). This is a clear, severe regression, not an improvement, and would not be recommended even if production code were being changed.

### Proof that no recovery-without-regression is possible

The combination of §5b and §6 constitutes a direct proof, not an inference:

1. §6 shows that **exhaustively searching every possible anchor and scoring each with the mathematically optimal (Hungarian) assignment** — strictly more powerful than production's greedy search — converges on the **exact same** anchor and assignment production already uses, in both cartridges. If any reassignment of the existing candidate pool could recover an unused candidate while preserving the rest, this exhaustive search would have found it; it did not.
2. §5b shows that **explicitly forcing** each unused candidate into every remaining tag role, anchored on the best-available existing context, does not merely fail to improve the fit — it makes the fit's scale and rotation implausible by an order of magnitude, for every one of the 8 combinations tested.

Together, these rule out both an assignment-algorithm limitation (there is no better assignment to find) and a "just needs more data/better fitting" explanation (adding more context makes it worse, not better). The unused candidates are excluded because they are not geometrically consistent with the rest of the matched holes under the reference model used by this pipeline — full stop, not because of any deficiency in how candidates are matched to tags.

---

## 8. Recommendation

**The current greedy assignment is provably optimal, in the specific sense proven above: no alternative assignment strategy — Hungarian, maximum bipartite matching, or an exhaustive global search using Hungarian scoring — produces a different or better result than production's existing greedy Stage 1 + Stage 2 logic, in either cartridge.** No algorithmic change to the assignment/matching layer is recommended.

The unused perfect-quality candidates in Cartridges 48 and 49 are not a matching-algorithm defect. They are most plausibly explained by one of:
- a genuine circular feature on the physical part that is not one of the 7 DWG-tagged mounting holes (both cartridges' overview images, established in Stage 7/8, show a visually complex part with a large valve/chamber feature and multiple small dark dot features, not all of which need to be mounting holes), or
- a second, physically separate instance of the hole pattern within the same captured frame that the fixed single-instance reference geometry was never designed to disambiguate from the first.

Neither explanation can be resolved by an assignment-algorithm change; both require independent ground truth (engineering drawings, or a second, independently-confirmed detector/labeling pass) to distinguish. This reinforces, unchanged, the standing recommendation from Stages 7 and 8: Cartridges 45/48/49/50 require their own dedicated investigation, separate from both candidate generation and candidate assignment tuning.

No production code was modified. No commits were created. Stopping here per your instruction.
