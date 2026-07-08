# Stage 8 — Candidate Generation Investigation

**Status:** Analysis complete. No production code modified. No commits created.
**Branch:** `stage8-candidate-generation-investigation`
**Objective:** determine whether Cartridges 48, 49, 66, and Cartridge 72's Tag 9 are limited by candidate *generation* (Hough never produces a usable candidate) or candidate *selection* (a usable candidate exists but is rejected/misassigned downstream).

---

## 1. Method

For each target, the entire Hough detection stage was replayed exactly as production configures it (dp=1.2, param1=80, param2=25, minRadius/maxRadius = 78%/122% of the downsampled nominal radius, minDist = 2.8× the downsampled nominal radius, 4× downsampling, CLAHE + Gaussian blur preprocessing), producing every raw candidate before any Stage 1 logic runs. Each candidate was ray-cast (the real `_subpixel_diameter` function) to get its ray-hit count, near-nominal ratio, angular gap, and fallback mode. The current (Stage-7-implemented) pipeline was then replayed on top of this candidate list to determine which candidates are currently selected. Full per-candidate tables and visual overlays were produced for all four targets.

---

## 2. Full Candidate Tables

### Cartridge 72 (24 raw candidates) — full table in `stage8_collect_results.json`; summary already established in prior Stage 7 reports. All 6 target tags (1,3,4,5,6,7) are matched to 36/36-quality candidates; Tag 9 is matched to a moderate-quality (19/36, 36.1% near-ratio, 100° gap) candidate that is not confirmed genuine.

### Cartridge 66 (30 raw candidates) — same structure: Tags 1,3,4,5,6,7 all matched to 36/36-quality candidates; Tag 9 matched to a poor-quality (9/36, 13.9%, 120° gap) candidate, per the prior root-cause investigation.

### Cartridge 48 (25 raw candidates)

| Candidate | n_hit | near_ratio | gap | fallback | Used? |
|---|---|---|---|---|---|
| (372,1976) | 36 | 1.000 | 10° | normal | **Unused** |
| (11932,2260) | 36 | 0.722 | 10° | normal | Unused |
| (3804,2148) | 35 | 0.306 | 20° | normal | Unused |
| (5888,2676) | 31 | 0.583 | 30° | normal | Unused |
| (2536,988) | 28 | 0.389 | 40° | normal | Used (Tag 4) |
| (512,564) | 20 | 0.333 | 50° | normal | Used (Tag 1) |
| (224,568) | 18 | 0.250 | 70° | normal | Unused |
| ...remaining 18 candidates, all n_hit ≤ 16, several `total_failure` | | | | | Mostly unused |

**Key finding: a genuinely perfect-quality candidate, (372,1976) — 36/36 hits, 100% near-nominal, 10° gap — is completely unused by the current pipeline.** It does not fall near any tag's predicted position under the current anchor.

### Cartridge 49 (13 raw candidates)

| Candidate | n_hit | near_ratio | gap | fallback | Used? |
|---|---|---|---|---|---|
| (392,1956) | 36 | 1.000 | 10° | normal | **Unused** |
| (11968,2292) | 36 | 1.000 | 10° | normal | Used (Tag 6) |
| (5680,2428) | 36 | 1.000 | 10° | normal | **Unused** |
| (10044,924) | 23 | 0.500 | 90° | normal | Unused |
| (2116,1468) | 22 | 0.472 | 100° | normal | Unused |
| (9656,2980) | 21 | 0.500 | 90° | normal | Used (Tag 3) |
| (9012,484) | 17 | 0.389 | 170° | normal | Used (Tag 1) |
| ...remaining 6 candidates, all n_hit ≤ 12 | | | | | Unused |

**Key finding: of three genuinely perfect-quality (36/36) candidates, only one is used.** (392,1956) and (5680,2428) sit completely unused.

---

## 3. Visual Overlays

`validation_output/stage8_candidate_generation/cart{48,49,66,72}_overlay.png` — yellow = currently selected, orange = rejected/unused raw candidate, green = independently-verified genuine hole (72, 66 only), magenta X = fitted true anchor position (72, 66 only).

**Cartridges 66 and 72**: both overlays show all 6 non-anchor tags cleanly matched (green ring exactly coincides with yellow selection ring in every case) and the magenta X sitting at a visibly larger, non-circular void where two channels merge — with the yellow "selected" Tag 9 candidate visibly offset from it, sitting on plain material nearby.

**Cartridges 48 and 49**: both overlays reveal these images depict a **visually different, more complex part geometry** than 66/72 — a large concentric-ring chamber/valve feature and thick looping channels, not a simple flat baseplate. Several small dark dot features of plausible hole-like size are visible; only some have any Hough candidate on them, and only some of those are selected.

---

## 4. Does a Raw Candidate Already Exist on the Genuine Hole?

| Target | Genuine candidate present near target? | Explanation |
|---|---|---|
| **Cartridge 72, Tag 9** | **No.** Nearest raw candidate is 642.6px from the independently-fitted true anchor position, itself only moderate quality (17/36, 41.7% near-ratio). | Visual inspection of the exact preprocessed image Hough operates on (`cart72_hough_input_at_target.png`) shows a real but **oversized, non-circular void** at the true position — larger than, and a different shape from, the ~100px-radius circular holes Hough is tuned to detect. Hough correctly does not generate a matching-size circular candidate for a feature that is not circular. |
| **Cartridge 66, Tag 9** | **No.** Nearest raw candidate is 484.5px from the fitted true anchor, itself poor quality (9/36, 13.9%). | Identical visual pattern (`cart66_hough_input_at_target.png`): an oversized, irregularly-shaped channel-junction void, not a circular hole. |
| **Cartridge 48** | **Selection issue identified, not generation.** A perfect-quality (36/36) candidate, (372,1976), exists and is completely unused — it simply doesn't fall near any tag's predicted position under the current (independently known to be unreliable) anchor. Separately, Tag 7's predicted position has no candidate within 850px at all, and visual inspection shows plain scratched material there, no hole. | Mixed: at least one location shows a clear **candidate-selection** failure (a perfect candidate ignored because the anchor's geometry doesn't reach it); Tag 7's area shows a **candidate-generation** gap, but visual evidence suggests there may be no genuine hole there in the first place (or the true anchor is wrong enough that "Tag 7" isn't being searched for in the right place at all). |
| **Cartridge 49** | **Selection issue identified, not generation**, plus a deeper geometric-model ambiguity. Two perfect-quality (36/36) candidates, (392,1956) and (5680,2428), sit completely unused. One of them ((392,1956)) was production's own previous anchor before the Stage 7 fix. | These candidates cannot all be reconciled under one consistent geometric model (established in the corrected blast-radius report) — this cartridge's difficulty is not fundamentally about Hough failing to find circles; Hough finds *several* excellent circles. The problem is that the fixed-offset reference model cannot consistently explain all of them together, or some are genuine circular features unrelated to the 7 DWG-tagged mounting holes (this dataset's images visibly contain a large chamber/valve feature that is not a mounting hole but could still present a clean circular edge to Hough at some location). |

---

## 5. Parameter Responsibility Analysis (Cartridge 72 / 66 Tag 9)

Direct visual inspection of the exact image Hough operates on (post-CLAHE, post-blur, post-downsampling) confirms the true anchor location in both cartridges is occupied by a real but **oversized and non-circular** feature (a channel bending/merging point), not a scaled or shifted version of the standard hole. This points most directly at:

- **Radius limits**: the true feature appears visually larger than the 78–122% nominal-radius window Hough is configured to search — a plausible, quantifiable contributor.
- **Accumulator threshold (param2)**: since the feature's edge is not a clean circle (it's interrupted by the merging channel), the circular Hough transform accumulates a weaker vote at any candidate radius than a true circular hole would — consistent with param2=25 correctly rejecting it as insufficiently circular.
- **CLAHE / Gaussian blur / downsampling**: inspected directly via the same preprocessed image used for Hough — no evidence that contrast enhancement or blurring is destroying an otherwise-clean circular edge; the irregularity is present in the underlying feature itself, not introduced by preprocessing.
- **minDist**: not implicated — this parameter controls spacing between *multiple* nearby detections, not detectability of a single feature.

**Quantitatively, the most likely responsible parameters, ranked by how directly they engage with the observed problem, are radius limits and accumulator threshold (param2) — not preprocessing, not minDist.** However, §6 shows that loosening either parameter enough to reach the target comes at a severe, quantified false-positive cost.

---

## 6. Parameter Sensitivity Study (Read-Only)

Each parameter was varied individually (production value held for all others), across all 4 targets, measuring new candidates appearing within 350px of each target ("recovery") versus new candidates appearing anywhere else in the image ("false-positive risk").

| Parameter | Value | Total new candidates near targets (all 4 combined) | Total new candidates elsewhere (all 4 combined) | FP-per-recovery ratio |
|---|---|---|---|---|
| dp | 1.2 (production) | 0 | 0 | — |
| dp | 1.4 | 4 | 403 | **101:1** |
| dp | 1.6 | 8 | 736 | 92:1 |
| param2 | 25 (production) | 0 | 0 | — |
| param2 | 20 | 2 | 381 | 191:1 |
| param2 | 18 | 4 | 574 | 144:1 |
| param2 | 15 | 8 | 896 | 112:1 |
| param2 | 12 | 11 | 1172 | 107:1 |
| minDist | 2.8× (production) | 0 | 0 | — |
| minDist | 1.0×–3.5× (full range tested) | 0 | ≤8 | **no recall effect at any value** |
| radius | [0.78,1.22] (production) | 0 | 0 | — |
| radius | [0.6,1.4] | 2 | 487 | 244:1 |
| radius | [0.5,1.5] | 5 | 639 | 128:1 |
| radius | [0.5,2.0] | 12 | 948 | **79:1 (best observed)** |
| radius | [0.4,2.5] | 13 | 1138 | 88:1 |

**Every parameter that produces any recovery near a target does so at a cost of 79 to 244 new candidates elsewhere per genuinely-useful recovery** — none of this is remotely close to a safe, targeted improvement. `minDist` is the sole exception: it has **no measurable effect on recall at all** across the entire tested range (1.0×–3.5× nominal radius), confirming it is not a relevant parameter for this specific problem — and also confirming it carries essentially no risk, since it does nothing either way here.

Even the best individual near-target candidate recovered under loosened settings (Cartridge 72, dp=1.4: a 36/36-quality candidate only ~74px from the true fitted anchor) does not change this conclusion — recovering it would require accepting 79 new spurious candidates elsewhere in that same single image, which downstream logic has no proven way to filter safely without its own dedicated, separately-validated quality gate (of the kind built for the Stage 6 recovery pass, at a rigor this investigation has not attempted here).

---

## 7. Parameter Ranking

| Parameter | Expected recall improvement | Expected false-positive increase | Implementation risk |
|---|---|---|---|
| **minDist** | None observed at any tested value | None (0–8 elsewhere, no near-target benefit) | Lowest — but pointless, since it doesn't address the problem |
| **radius limits** | Best observed ratio (79:1 at [0.5,2.0]) | Very high (948 new candidates across 4 images at the best setting) | High — requires an entirely new downstream quality gate to be usable safely |
| **dp** | Moderate (92–101:1 ratio) | Very high (403–736 new candidates) | High — same reasoning |
| **param2** | Worst ratio range at conservative settings (107–191:1), improves only when loosened aggressively (12–15) | Highest absolute counts observed (896–1172 new candidates) | Highest — most global, least targeted parameter |

**None of the four parameters offers a safe, standalone candidate-generation improvement.** Ranked from "least harmful to explore further" to "most harmful": minDist (harmless but useless) > radius limits > dp > param2.

---

## 8. Recommendation for the Single Safest Candidate-Generation Improvement

**No safe, general candidate-generation parameter change is recommended at this time.** The data does not support one: every parameter capable of surfacing new candidates near the four investigated targets does so at a false-positive cost 80–250× larger than the benefit, confirmed across all four cartridges independently, not just the two with the cleanest ground truth.

The evidence instead supports a different conclusion than the one this investigation set out expecting to reach:

- **Cartridges 66 and 72 (Tag 9) are limited by candidate generation**, but not in a way any of the four swept parameters can safely fix — the true feature is not circular, so no amount of Hough-parameter loosening reliably produces a clean, trustworthy detection of it; it would require a fundamentally different, non-circle-based feature detector (out of scope for a parameter change).
- **Cartridges 48 and 49 show clear evidence of a candidate *selection* problem** (multiple perfect-quality candidates sitting completely unused) **layered on top of a harder, unresolved geometric-model ambiguity** — these cartridges are not simply missing candidates; they have more high-quality candidates than the current pipeline can consistently reconcile with the fixed reference geometry. This is consistent with, and reinforces, the standing recommendation (from the Stage 7 geometric-model investigation) that Cartridges 45/48/49/50 require their own dedicated investigation, separate from candidate-generation tuning.

If any single follow-up is pursued, the safest next step is **not** a parameter change but a targeted, visually-verified investigation of whether the two unused perfect-quality candidates in Cartridges 48 and 49 correspond to genuine but currently-unreachable DWG tag holes — a candidate-selection question, addressed through the existing anchor/geometry logic, not through Hough tuning.

No production code was modified. No commits were created. Stopping here per your instruction.
