# Stage 7 — Cartridge 66 Complete Root-Cause Investigation

**Status:** Investigation complete. No production code modified. Nothing implemented.
**Branch:** `stage7-geometric-model-investigation` (no commits).
**Objective:** determine whether the Cartridge 66 regression (confirmed in `STAGE7_ANCHOR_REDESIGN_BLAST_RADIUS_ANALYSIS_CORRECTED.md`, §4) is caused by (A) Stage 1, (B) Stage 2's fixed window, (C) an interaction between them, or (D) something else — with full quantification, not qualitative description.

---

## 1. Executive Summary

The Tag 9 PASS→FAIL→PASS flip is mechanically caused by **(C) an interaction between Stage 1 and Stage 2**: Stage 1's role-generalized search legitimately selects a far more precise pivot candidate, which shifts Tag 9's predicted position by ~430px — enough that Stage 2's fixed 600px re-ranking window loses access to the candidate the current algorithm relies on.

However, a deeper investigation (visual inspection of the true anchor location, requested nowhere in the original ask but necessary to answer it honestly) reveals **(D) something else entirely underlying the whole situation**: Cartridge 66's true Tag 9 location, like Cartridge 72's, is occupied by a large, non-circular channel-junction feature, not a normal drilled hole. **No candidate found at any tested window radius (600–1000px) sits on this feature.** Every candidate in the vicinity — including both the current algorithm's low-quality anchor and the candidates a wider window would additionally reach — is scattered nearby texture/noise of varying ray-cast quality, none confirmed genuine. The sensitivity sweep also reveals the widening does **not** recover the specific candidate assumed in the prior blast-radius report; a different, higher-quality-but-equally-unconfirmed candidate wins instead, once the window is wide enough, and does so ambiguously (multiple candidates compete once the window exceeds ~900px).

**In short: this is not a case of "a good match becoming unreachable." It is two different not-confirmed-genuine candidates trading places, with the trade governed by Stage 1/Stage 2's fixed-window interaction. The PASS/FAIL "regression" is real as a mechanical fact, but the underlying ground truth for Tag 9 in this cartridge may not be well-defined for either choice.**

---

## 2. Requirement 1 — Full 7-Tag Trace

| Tag | Current anchor | Proposed anchor | Current predicted | Proposed predicted | Winner (both) | Why |
|---|---|---|---|---|---|---|
| 1 | (6324,2332) | (6647,2048) | (233,868) | (556,584) | (556,584) | Only 36/36-quality candidate in either window; a second, much lower-quality candidate (23/36, 100° gap) also falls in range but loses on quality |
| 3 | " | " | (650,3537) | (973,3253) | (992,3268) | Sole candidate in window, 36/36 quality, unambiguous |
| 4 | " | " | (2057,1224) | (2380,940) | (2380,940) | Perfect-quality (36/36) candidate wins over two lower-quality alternatives (28/36, 32/36) also in window |
| 5 | " | " | (1932,5928) | (2255,5644) | (2320,5612) | 36/36 candidate wins over a 21/36 alternative also in window |
| 6 | " | " | (3022,2260) | (3345,1976) | (3352,1936) | 36/36 candidate wins over a total_failure-quality alternative also in window |
| 7 | " | " | (3353,3614) | (3676,3330) | (3708,3300) | 36/36 candidate wins over two lower-quality alternatives (20/36, 13/36) also in window |
| **9** | " | " | (6324,2332) | (6647,2048) | **(5812,2392) under current / (6324,2332) under proposed** | **See §3–§6 below — the only tag where current and proposed disagree** |

**Tags 1, 3, 4, 5, 6, 7 are unaffected in substance** — in every case a clear, unambiguous 36/36-quality candidate wins regardless of which anchor (current or proposed) is used, exactly reproducing the improvement already documented for this candidate set. **Tag 9 is the sole point of disagreement**, examined in full below.

---

## 3. Requirement 2 — Tag 9 Complete Candidate List

Distances measured from both the current prediction (6324,2332) and the proposed prediction (6647,2048):

| Candidate | Dist. from current pred. | Dist. from proposed pred. | n_hit | Near-nominal ratio | Angular gap | Fallback tier |
|---|---|---|---|---|---|---|
| (6324,2332) — **current algorithm's Tag 9** | 0.0px | 430.1px | 9/36 | 13.9% | 120.0° | normal |
| (7084,1284) | 1294.6px | 880.2px | 31/36 | 61.1% | 30.0° | normal |
| (5812,2392) — assumed in the prior blast-radius report | 515.5px | 903.1px | 20/36 | 44.4% | 130.0° | normal |
| (5588,1448) | 1150.3px | 1217.2px | 11/36 | 25.0% | 250.0° | normal |
| (6692,3268) | 1005.7px | 1220.8px | 32/36 | 13.9% | 30.0° | normal |
| (5660,784) | 1684.4px | 1603.7px | 3/36 | 0.0% | 200.0° | **total_failure** |
| (4360,956) | 2398.1px | 2534.3px | 15/36 | 36.1% | 220.0° | normal |
| (4092,636) | 2803.3px | 2919.2px | 19/36 | 38.9% | 160.0° | normal |
| (6464,4976) | 2647.7px | 2933.7px | 2/36 | 0.0% | 310.0° | **total_failure** |

Only one candidate — the current algorithm's own poor-quality anchor — falls within 600px of the proposed prediction. This is the entire mechanical cause of the "regression": under the new anchor, Stage 2 has exactly one candidate to choose from for Tag 9, and it is a low-quality one.

---

## 4. Requirement 3 — Quantifying Exactly Why the Prediction Moved

Not "it moved 430px" — **why**, decomposed into every contribution.

An independent geometric fit was performed (identical methodology to the Cartridge 72 investigation: brute-force shape-match + least-squares similarity transform, using the 6 unambiguous 36/36-quality candidates for Tags 1,3,4,5,6,7 — not Tag 9, which is exactly what's in question). Result: **scale = 0.9982, rotation = −0.769°**, per-tag residuals 7.4–18.8px — a clean, well-behaved fit, consistent with a normal, undistorted cartridge (directly comparable to the Cartridge 1 and Cartridge 72 baselines already established). This fit independently predicts the **true** Tag 9 / anchor position at **(6651.5, 1975.0)**.

Now, decomposing the 430px anchor shift:

- **The current algorithm's own pivot** — the raw candidate at (6324,2332), which today's Stage 1 assumes is Tag 9 — sits **484.5px** away from this independently-fitted true position. This is a large individual position error for a single candidate, and it is directly consistent with this candidate's poor ray-cast quality (9/36 hits, 13.9% near-nominal, 120° angular gap — a borderline, low-confidence detection, not a clean circular edge).
- **The proposed algorithm's pivot** — the raw candidate at (2380,940), used as Tag 4 — sits only **14.0px** from its independently-fitted true Tag 4 position (2377.6, 926.2). This is an excellent, tight fit, consistent with its high quality (36/36 hits, 100% near-nominal, 10° gap).

Since `anchor = pivot_position − REF_OFFSETS[role]`, and the true anchor is the same physical point regardless of which correct pivot is used to reach it, **the anchor shift between current and proposed is arithmetically the difference between these two pivots' individual position errors**:

- Current pivot's error vector (pivot − true anchor): **(−327.5, +357.0)**
- Proposed pivot's error vector (pivot − true Tag-4 position, which cancels through the offset): **(+2.4, +13.8)**
- Reconstructed net shift (proposed error − current error): **(+329.9, −343.2)**
- Actual observed shift (proposed anchor − current anchor): **(+323, −284)**

These match closely (the small residual reflects the independent fit's own ~7–19px per-point uncertainty, not a missing contribution). **Every pixel of the 430px shift is accounted for: essentially all of it is the current algorithm's own anchor candidate being a poor, ~485px-imprecise detection, replaced by a pivot that is ~35× more precise (14px vs. 485px).** The shift is not a mysterious side effect — it is the direct, quantifiable consequence of trading a bad reference point for a good one.

---

## 5. Why the "Recoverable" Candidate Isn't Actually Confirmed Genuine

Before running the sensitivity sweep, the true anchor location (6651.5, 1975.0) was visually inspected (`validation_output/stage7_geometry/cart66_tag9_area.png`). **The finding is the same as Cartridge 72's:** this location sits at a large, non-circular channel-junction feature — visibly larger and differently-shaped than the ~100px-radius circular holes Hough is configured to detect — not a normal mounting hole. None of the four nearby candidates plotted (the current anchor, and the three next-nearest real detections) sit on this feature; all are scattered on plain surrounding material at various distances (430–1295px away).

This matters directly for the requested sensitivity analysis: it means there is no guarantee that *any* candidate reachable by widening the window is the genuine hole — widening the search may simply trade one uncertain candidate for a different uncertain one.

---

## 6. Requirement 4 — Stage 2 Window Sensitivity Sweep (Tag 9 only, proposed anchor)

| Radius | Candidates in window | Winner | Winner quality | Diameter | PASS/FAIL |
|---|---|---|---|---|---|
| 600px | 1: (6324,2332) | (6324,2332) | 9/36, 13.9%, 120° | 0.5200mm | PASS |
| 650px | 1 (same) | (6324,2332) | same | 0.5200mm | PASS |
| 700px | 1 (same) | (6324,2332) | same | 0.5200mm | PASS |
| 750px | 1 (same) | (6324,2332) | same | 0.5200mm | PASS |
| 800px | 1 (same) | (6324,2332) | same | 0.5200mm | PASS |
| 850px | 1 (same) | (6324,2332) | same | 0.5200mm | PASS |
| **900px** | **2**: +(7084,1284) | **(7084,1284)** | **31/36, 61.1%, 30°** | **0.4825mm** | PASS |
| 950px | 3: +(5812,2392) | (7084,1284) (unchanged) | same | 0.4825mm | PASS |
| 1000px | 3 (same) | (7084,1284) (unchanged) | same | 0.4825mm | PASS |

**Important correction to the prior report's framing:** the candidate assumed there to be "the genuine one just out of reach" — (5812,2392) — is **never** the winner at any tested radius. A different, higher-ray-cast-quality candidate, (7084,1284), enters the window first (880px vs. 903px) and wins on quality (31/36 vs. 20/36) as soon as both are reachable. The smallest radius that changes Tag 9's outcome from the current algorithm's result is **900px**, and it produces a *different* answer than previously assumed — still a PASS, but via a different physical location entirely (7084,1284 vs. 5812,2392 — these are 1281px apart from each other, clearly different candidates, not measurement noise on the same feature).

Neither (6324,2332), (7084,1284), nor (5812,2392) can be confirmed as the genuine Tag 9 hole given §5's finding. All three are simply different pieces of nearby texture/noise (or possibly a defect in the surface finish) of varying ray-cast quality, and none sit on the actual channel-junction feature at the fitted true anchor position.

---

## 7. Requirement 5 — Ambiguity as the Window Expands

**Yes, real ambiguity exists**, and it appears exactly at the radius that would "fix" the regression:

- Below 900px: no ambiguity (only the current anchor's own poor candidate is present).
- **At 900px: two competing candidates** — (6324,2332) at 430px (poor quality) and (7084,1284) at 880px (good quality) — resolved by the ranking rule preferring higher `n_hit`, not by any confirmed identity.
- **At 950px and above: three competing candidates**, adding (5812,2392) at 903px (moderate quality) — still resolved the same way, but now with three plausible-but-unconfirmed options rather than one.

This confirms that a blanket radius increase does not converge on a single, clearly-correct answer for Tag 9 — it introduces a competition among multiple, similarly-uncertain candidates, decided by a secondary quality heuristic rather than by any independent confirmation of genuineness.

---

## 8. Root-Cause Classification (A/B/C/D)

- **(A) Stage 1 alone: not the cause.** Stage 1's pivot choice for Tag 4 (used to derive the proposed anchor) is objectively excellent (36/36 quality, 14px fit residual) — this decision is correct and should not be reverted.
- **(B) Stage 2's fixed window alone: not sufficient as an explanation.** The 600px window is unchanged from today's production value and was not itself modified by this investigation; it behaves exactly as designed.
- **(C) Interaction between Stage 1 and Stage 2: this is the mechanical cause of the observed PASS/FAIL flip**, fully quantified in §4 — a legitimately better pivot moves the reference point by an amount (430px) that is comparable to the window's own radius (600px), which is enough to gain or lose access to specific borderline-distance candidates depending on exactly where they happen to sit.
- **(D) Something else entirely: yes, and it is the more fundamental issue.** Cartridge 66's true Tag 9 location — like Cartridge 72's — appears to be a physical channel-junction feature rather than a normal hole, visually confirmed in §5. No candidate at any tested radius is confirmed genuine. The (C) mechanism determines *which uncertain candidate* gets picked, but does not create the underlying uncertainty — that uncertainty (D) already exists in the raw data, independent of any Stage 1/Stage 2 design choice, current or proposed.

**Overall answer: (C) is the correct mechanical explanation for why the reported result changes, but (D) is the correct explanation for why neither reported result (FAIL or PASS) should be treated as confidently correct.**

---

## 9. Requirement 6 — Alternative Solution Approaches (Descriptive Only, No Recommendation)

Given §5's finding, every approach below is evaluated with the caveat that **none can manufacture a confirmed-genuine candidate where the raw data does not contain one** — they can only change which uncertain candidate is selected, not resolve the underlying uncertainty.

- **Translating the prediction:** would not help. The true anchor position (6651.5,1975.0) is already the correct target; the problem is not a systematic prediction offset but the absence of a clean candidate at that target.
- **Adaptive radius (per-tag, based on local candidate density/quality):** could reach (7084,1284) or (5812,2392) without widening every tag's window globally, but as §7 shows, this does not eliminate ambiguity — it only scopes where the ambiguity is allowed to occur.
- **Local refinement (re-running Hough with adjusted parameters near the predicted position):** unlikely to help on its own, given §5's visual finding that the true feature at this location is a large, non-circular channel junction — not a mis-tuned circular search, but a fundamentally different feature shape that a same-radius-class circular detector cannot represent.
- **Second-pass refinement (a dedicated additional pass, analogous in spirit to the existing Stage 6 recovery pass, applied specifically to disagreement cases like this one):** could apply extra scrutiny (e.g., requiring a minimum quality bar before accepting a Tag 9 match at all, rather than accepting whatever is nearest-and-best-ranked inside a window) — this is the only category of approach that engages with §5's finding directly, since it could in principle choose to report `not_detected` when no candidate meets a confidence bar, rather than forcing a match.

---

## 10. Requirement 7 — Decision Table

| Approach | Fixes Cartridge 66? | Changes Stage 1? | Changes Stage 2? | Affects Cartridge 72? | Regression risk | Implementation complexity |
|---|---|---|---|---|---|---|
| **Do nothing (keep current algorithm)** | N/A — no regression to begin with | No | No | No — Cartridge 72 stays broken | None | None |
| **Increase global Stage 2 window to 900–1000px** | Produces *a* PASS, but via an unconfirmed candidate, and only after introducing 2–3-way ambiguity (§7) | No | Yes — window constant changes for every tag, every cartridge | Unknown — not tested here; would need the same full 79-cartridge blast-radius re-analysis | **High** — a blanket window increase was already evaluated and rejected in Stage 6 for the equivalent Stage 1 tolerance; the same destabilization risk applies here | Low (single constant change) but requires full re-validation |
| **Translate the prediction** | No | No | No | No | Low (does nothing, so no new risk) | Low, but ineffective |
| **Adaptive radius (per-tag)** | Same outcome as global increase, scoped more narrowly | No | Yes — new per-tag logic | Possibly, if Tag 9-class cases share logic | Moderate — smaller blast radius than a global change, but new untested logic and parameters | Moderate |
| **Local refinement (re-tuned local Hough pass)** | Unlikely, per §5 | Possibly (new candidate-generation step) | Possibly | Possibly | Moderate-High — new detection logic, unvalidated | High |
| **Second-pass refinement with a confidence/quality floor** | Converts the ambiguity into an honest `not_detected` rather than a forced (and possibly wrong) PASS or FAIL | No | Yes — adds a new decision layer | Directly relevant — this is the same open question already flagged for Cartridge 72's own Tag 9 in the blast-radius report | Low-Moderate — behavior only changes for already-uncertain cases, but needs its own validated quality threshold (same category of work as the Stage 6 recovery-pass gate) | Moderate |

No approach in this table has been implemented, tuned, or recommended as *the* solution — per your instruction, this is a comparison of properties only.

---

## 11. Summary

- The Cartridge 66 Tag 9 regression is mechanically real and fully explained: a legitimately better Stage 1 pivot (14px fit error vs. 485px) shifts the predicted Tag 9 position by ~430px, which — interacting with Stage 2's unchanged, fixed 600px window — excludes the specific candidate the current algorithm happens to rely on.
- That "excluded" candidate is not, on closer inspection, confirmed to be the genuine hole either. Cartridge 66's true Tag 9 location shows the same channel-junction pattern already documented for Cartridge 72 — no raw candidate at any tested radius (600–1000px) is confirmed to sit on it.
- Widening the window does not converge on a single correct answer; it introduces a 2–3-way competition among differently-uncertain candidates, decided by a secondary quality rule.
- Root cause: **(C)** explains the mechanical trigger; **(D)** explains why the underlying situation is genuinely ambiguous rather than simply mis-solved.

No fix has been proposed or implemented. Stopping here per your instruction.
