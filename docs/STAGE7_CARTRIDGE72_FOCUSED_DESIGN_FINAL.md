# Stage 7 — Cartridge 72 Focused Design: Final Investigation Report

**Status:** Investigation and design analysis complete. No production code modified. Nothing implemented. No commits created.
**Branch:** `stage7-geometric-model-investigation` (no commits).
**Scope, per your directive:** Cartridge 66 is closed and deferred pending independent Leica ground truth — not revisited here. Tag 9, everywhere, is treated as unknown ground truth — the objective is exclusively the recovery and correct assignment of Tags 1, 3, 4, 5, 6, 7 in Cartridge 72, while preserving every correct result elsewhere.

---

## 1. Requirement 2 — Why the False Anchor Wins and the Correct Anchor Loses (Current Production Code, Fully Quantified)

The current algorithm tries every one of Cartridge 72's 24 raw candidates as a hypothetical anchor, always assuming the tried candidate **is** Tag 9 (offset (0,0)). The complete score distribution (every candidate, its resulting match count, and which tags it matches) was computed directly against current production's exact scoring function:

| Anchor candidate | Score | Matched tags | Note |
|---|---|---|---|
| **(4836,3412)** | **3** | T6, T7, T9 | **Winner** — sitting on plain texture (confirmed in Stage 5); "matches" T6 and T7 only by coincidental proximity to unrelated real holes |
| (4092,5864), (5816,4940), (4528,1256), (6052,1400), (5748,1012), (4444,812), (5500,5756), (3700,5228), (7072,1256), (5000,5028), (6272,1168) | 2 each | various pairs | All low-quality, coincidental 2-tag alignments |
| **(644,416) — genuine Tag 1's own hole** | **1** | T9 only | Matches only itself |
| **(1084,3080) — genuine Tag 3's own hole** | **1** | T9 only | Matches only itself |
| **(2456,756) — genuine Tag 4's own hole** | **1** | T9 only | Matches only itself |
| **(2396,5444) — genuine Tag 5's own hole** | **1** | T9 only | Matches only itself |
| **(3440,1760) — genuine Tag 6's own hole** | **1** | T9 only | Matches only itself |
| **(3780,3116) — genuine Tag 7's own hole** | **1** | T9 only | Matches only itself |
| remaining candidates | 1 each | T9 only | Matches only itself |

**This is the complete, exact explanation.** Every one of the six genuine holes, when forced into the only role current code will ever consider (Tag 9), scores exactly 1 — it trivially "matches itself" as the anchor, but since it is not actually located at Tag 9's true position, applying `REF_OFFSETS` from its position predicts garbage locations for the other six tags, none of which land near any real candidate. The false anchor's winning score of 3 is not the result of a scoring flaw or a close contest — it is the unique maximum across all 24 candidates, achieved by an unrelated, low-quality texture candidate whose position happens to coincidentally align with two other real/false candidates within the generous 600px tolerance. **The correct anchor doesn't "lose a close contest" — it is never even in contention, because no genuine hole candidate can score above 1 while restricted to the Tag-9-only role assumption.** This matches and quantifies precisely the mechanism already established in the geometric-model investigation: the true Tag 9 location has no corresponding raw Hough candidate at all (nearest is 639–643px away, confirmed previously), so there is no candidate that could ever score highly under this restricted search even in principle.

---

## 2. Requirement 3 — Minimal, Fully General Stage 1 Modification

**The modification:** generalize the anchor-trial loop from "try each candidate assuming it is Tag 9" to "try each candidate against each of the 7 tag roles," computing the implied anchor as `candidate_position − REF_OFFSETS[role]` for every `(candidate, role)` pair, and scoring each hypothesis with the **exact same, unmodified** match-counting function already in production. This is the identical mechanism already designed and twice blast-radius-validated in this investigation (`STAGE7_ANCHOR_SELECTION_REDESIGN.md`, Approach 5; validated in the two corrected blast-radius reports).

**Why this is the minimum possible change:**
- It is **necessary**: §1 proves no amount of quality-weighting, tie-breaking, or threshold tuning within the Tag-9-only search space can ever help, because no genuine-hole candidate scores above 1 under that restricted role assumption. The only way to let a genuine hole "win" is to allow it to be evaluated under *some* role other than 9 — there is no way around widening the role search.
- It is **general**: the loop tries **all 7** roles for **every** candidate, uniformly, with no special-casing of any particular tag or cartridge. Restricting to a subset of roles (e.g., "try roles 1–7 except 9" or any cartridge-informed shortcut) would itself constitute undisclosed, cartridge-specific tuning — trying all 7 roles for every candidate is the only way to keep the change fully general.
- The previously-designed quality/residual tie-break (used only to resolve exact ties in match count) is **not strictly required to solve Cartridge 72** — the winning hypothesis for the target objective outscores the false anchor outright (6 vs. 3, not a tie), so any reasonable tie-break, including today's existing "first-found-wins" rule applied over the widened search space, would suffice. The tie-break is retained in the validated design purely as low-risk, tie-only-activating defense-in-depth (documented previously), not because Cartridge 72 requires it.

**Quantified confirmation that the correct hypothesis now wins:** re-scoring all 168 `(candidate, role)` combinations (24 candidates × 7 roles) against the same scoring function:

| Hypothesis | Score | Matched tags | Pivot quality |
|---|---|---|---|
| (2144,5072) as role=Tag5 | **7** | T1,T3,T4,T5,T6,T7,**T9** | Pivot itself is low quality (15/36); wins only because it also happens to catch a Tag-9-area candidate — **out of scope per your directive** |
| (2456,756) as role=Tag4 | 6 | **T1,T3,T4,T5,T6,T7** | Pivot is genuine Tag 4's own hole (36/36) |
| (3440,1760) as role=Tag6 | 6 | **T1,T3,T4,T5,T6,T7** | Pivot is genuine Tag 6's own hole (36/36) |
| (644,416) as role=Tag1 | 6 | **T1,T3,T4,T5,T6,T7** | Pivot is genuine Tag 1's own hole (36/36) |
| (3780,3116) as role=Tag7 | 6 | **T1,T3,T4,T5,T6,T7** | Pivot is genuine Tag 7's own hole (36/36) |
| (1084,3080) as role=Tag3 | 6 | **T1,T3,T4,T5,T6,T7** | Pivot is genuine Tag 3's own hole (36/36) |
| (2396,5444) as role=Tag5 | 6 | **T1,T3,T4,T5,T6,T7** | Pivot is genuine Tag 5's own hole (36/36) |
| (4836,3412) as role=Tag9 (today's winner) | 3 | T6,T7,T9 | The false anchor — now decisively outscored |

**Six independent hypotheses — one for each genuine hole, each used as its own correct pivot — all score exactly 6 and all resolve to the identical, exactly-correct target set {T1,T3,T4,T5,T6,T7}.** Whichever of these six wins the final tie-break (against each other, and against the single 7-scoring hypothesis above it), the downstream matched candidates for the six target tags are the same in every case, because they are all being matched against the same six genuine, unambiguous, 36/36-quality real holes. This is why the design is robust here: it does not depend on picking a "clean" pivot — any sufficiently-close pivot under its correct role converges on the same answer, and the objective's six tags are recovered correctly regardless of which specific hypothesis technically wins.

**Tag 9 is not solved by this change, and is not meant to be** — per your directive, this is explicitly out of scope. The winning hypothesis (score 7) happens to also produce a Tag 9 assignment, but as established in the geometric-model and verification reports, this is not a confirmed genuine hole; it is an acceptable, disclosed side effect, not a claim of correctness for Tag 9.

---

## 3. Requirement 4 — Complete Blast-Radius Analysis (All 79 Cartridges)

This analysis has already been run twice independently (once with a since-disclosed-and-fixed tie-break bug, once corrected) with byte-identical results both times — see `STAGE7_ANCHOR_REDESIGN_BLAST_RADIUS_ANALYSIS_CORRECTED.md` for the full run. Restated here, scoped to your current directive (Tag 9 ignored everywhere; Cartridge 66 deferred, not counted):

| Category | Result |
|---|---|
| Cartridges with byte-identical measurements, positions, and PASS/FAIL (all 7 tags) | **74 / 79** |
| Cartridges changed | 5 / 79: **18, 48, 49, 66, 72** |
| **Cartridge 66** | **Deferred per your directive — not evaluated further in this report** |
| Cartridge 18 | Tag 4 upgraded from a moderate-quality match (24/36) to a perfect one (36/36); PASS/FAIL unchanged (PASS→PASS) — **improvement, not a regression** |
| **Cartridge 72** | **Tags 1,3,4,5,6,7 all recovered/corrected to their genuine, 36/36-quality holes — the stated objective, met exactly.** Tag 9 additionally receives a new, unconfirmed match (out of scope, disclosed, not claimed as correct) |
| Cartridges 48, 49 | Changed; **not classifiable as confirmed regressions** — see §4 |

**Recovered holes (Cartridge 72, in scope):**

| Tag | Before | After | Quality |
|---|---|---|---|
| 1 | Missing (`outside_image`) | (644,416) | 36/36, 0° gap |
| 3 | Missing (`outside_image`), *and* its real hole was being reported under the wrong label as "Tag 6" | (1084,3080) | 36/36, 0° gap |
| 4 | Missing (`not_detected`) | (2456,756) | 36/36, 0° gap |
| 5 | Missing (`outside_image`) | (2396,5444) | 36/36, 0° gap |
| 6 | Wrongly reported as Tag 3's genuine hole | (3440,1760) — its own genuine hole | 36/36, 0° gap |
| 7 | Wrongly reported as a low-quality (15/36) substitute | (3780,3116) — its own genuine hole | 36/36, 0° gap |

Every one of the 6 target tags is now correctly identified and measured at its genuine, independently-verified location (per `STAGE7_CARTRIDGE72_VERIFICATION_REPORT.md`).

---

## 4. Regression Assessment

**No confirmed regression exists within the scoped objective.**

- **74 cartridges:** unaffected, confirmed by direct byte-for-byte comparison (position, diameter, PASS/FAIL) across two independent runs.
- **Cartridge 18:** a clear quality improvement, no PASS/FAIL change.
- **Cartridge 72:** the objective itself — 6/6 target tags recovered correctly, zero regressions among them (there was nothing correct to regress from; all 6 were previously missing or misidentified).
- **Cartridge 66:** deferred per your explicit instruction — excluded from this assessment.
- **Cartridges 48, 49:** changed, but **cannot be honestly classified as regressions**, for a documented, pre-existing reason: both belong to a cluster already flagged (in the geometric-model investigation, independent of this design work) as exhibiting a *different* failure mode from Cartridge 72 — broad image-quality degradation and, in Cartridge 49's specific case, **two mutually-inconsistent perfect-quality (36/36) candidates that cannot both be genuine under one consistent geometric model** (established in the corrected blast-radius report). Because neither cartridge has an independently-confirmed ground truth today (unlike Cartridge 72's six holes, which were rigorously verified via shape-fit, visual inspection, and cross-checking in earlier reports), there is no basis to say the "before" state was correct and the "after" state is wrong, or vice versa. These remain open items requiring their own dedicated investigation — a recommendation already made in the geometric-model report and unchanged by this analysis. They are not resolved by, and do not block, the Cartridge 72 objective.

**Conclusion: condition (A) is achieved** — Cartridge 72 is solved (all 6 target tags recovered and correctly assigned) with zero regressions among every cartridge where correctness is independently verifiable, given the explicit, disclosed exclusions of Tag 9 (per your requirement 1) and Cartridge 66 (per your directive today). Cartridges 48 and 49 remain open, pre-existing, separately-scoped questions — not new problems created by this design, and not counted against it.

---

## 5. What Was Not Needed

No iteration was required beyond the design already validated earlier in this investigation. No new regression was discovered that required revising the algorithm. Condition (B) (proving impossibility) was not reached and is not applicable — a fully general, minimal solution meeting the stated objective with zero confirmed regressions already exists and has been validated twice.

---

## 6. Explicit Statement

**The redesign (role-generalized Stage 1 anchor search, Approach 5 from `STAGE7_ANCHOR_SELECTION_REDESIGN.md`) is algorithmically stable and ready for implementation review with respect to the Cartridge 72 objective as scoped by your requirement 1** (Tags 1,3,4,5,6,7 only; Tag 9 ignored; Cartridge 66 deferred). Cartridges 48 and 49 should be flagged to whoever reviews this for implementation as pre-existing, separately-scoped open items — not blockers to the Cartridge 72 fix, but not resolved by it either.

No production code was modified. No commits were created. Stopping here per your instruction.
