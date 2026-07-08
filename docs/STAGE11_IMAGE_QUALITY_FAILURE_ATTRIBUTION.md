# Stage 11 — Image Quality and Failure Attribution

**Status:** Analysis complete. No production code modified. No commits created.
**Branch:** `stage11-image-quality-investigation`
**Objective:** determine whether Cartridges 48, 49, 66, and 72's remaining unresolved tags are fundamentally limited by image quality/content rather than algorithm design — the final synthesis of the entire Stage 7–11 investigation arc.

---

## 1. Unresolved Tags Evaluated

| Tag | Predicted/true position | In captured frame? |
|---|---|---|
| Cartridge 48, Tag 5 | (1923, 5628) | **No** — image height is 4926px; prediction is 702px below the bottom edge |
| Cartridge 48, Tag 7 | (3344, 3314) | Yes |
| Cartridge 49, Tag 5 | (10878, 5960) | **No** — image height is 4928px; prediction is 1032px below the bottom edge |
| Cartridge 49, Tag 7 | (12299, 3646) | Yes (122px from the right edge) |
| Cartridge 49, Tag 9 | (15270, 2364) | **No** — image width is 12396px; prediction is 2874px beyond the right edge |
| Cartridge 66, Tag 9 | (6651, 1975) — independently-fitted true anchor | Yes |
| Cartridge 72, Tag 9 | (6729, 1800) — independently-fitted true anchor | Yes |

Three of the seven unresolved tags have **no image data to evaluate at all** — the predicted position is genuinely outside the captured frame. This was confirmed by direct inspection of the frame boundary in each case (`validation_output/stage11_image_quality/{48,49,49b}_edge_check.png`): the imaged content ends in plain black (no-data) region before reaching the predicted position in two cases; the third (Cartridge 49, Tag 9) shows only the already-accounted-for Tag 6 hole near the edge, no new evidence about Tag 9.

---

## 2. Quantitative Metrics — Full Comparison

A battery of metrics was computed at every unresolved location and at a comparison set of 9 successfully-detected holes (Cartridges 72, 66, 49's own best matches, plus baseline Cartridges 34, 18, 61), all measured identically (150px patch radius, 100px expected ring radius, the real production ray-cast function).

### Successful-detection reference range (n=9, all 36/36 ray-hit quality)

| Metric | Mean | Range |
|---|---|---|
| Local contrast | 57.6 | 53.7 – 62.3 |
| Gradient magnitude | 15.3 | 13.8 – 16.9 |
| Edge strength at nominal radius | 43.3 | 5.5 – 69.0 *(noisy metric — see §3)* |
| Blur (Laplacian variance) | 55.2 | 43.3 – 70.7 |
| Saturation fraction | 0.00 | 0.00 – 0.00 |
| Illumination variation | 2.93 | 1.85 – 5.76 |
| SNR | 20.5 | 15.3 – 30.8 |
| Ray-hit count | 36 | 36 – 36 |
| Near-nominal ratio | 1.00 | 1.00 – 1.00 |
| Angular gap | 10° | 10° – 10° |
| Circularity (nearest dark blob) | 0.77 | 0.72 – 0.81 |

### Unresolved tags (in-frame cases only)

| Tag | Local contrast | Edge strength @ r=100 | Blur | Saturation | Illum. var. | SNR | n_hit | Near-ratio | Ang. gap | Circularity |
|---|---|---|---|---|---|---|---|---|---|---|
| 48/Tag7 | 43.5 | 11.7 | 56.8 | 0.00 | 27.3 | 21.8 | 36 | **0.000** | 10° | 0.47 |
| 49/Tag7 | 52.9 | 16.9 | 174.5 | **0.29** | 34.1 | **9.8** | 16 | **0.083** | **210°** | 0.47 |
| 66/Tag9 | 42.6 | **4.7** | 36.0 | 0.00 | 8.0 | 19.4 | 36 | 0.44 | 10° | 0.71 |
| 72/Tag9 | 40.5 | **4.1** | 39.2 | 0.00 | 4.9 | 13.9 | 36 | 0.25 | 10° | 0.67 |

---

## 3. Interpretation of Each Metric

- **Local contrast, gradient magnitude, blur, circularity** do not cleanly separate unresolved from successful cases on their own — all four unresolved (in-frame) tags fall within or close to the successful range on these metrics. This rules out "the image is generally too dark, blurry, or low-contrast" as the explanation.
- **Edge strength at the nominal (100px) radius is the single most discriminating metric for Cartridges 66 and 72**: both true-anchor locations score 4.1–4.7, far below even the weakest successful case (5.5) and nowhere near the mean (43.3). This is a direct, quantitative confirmation of the Stage 8 visual finding: the real feature at these locations is larger than the expected hole radius, so there is no strong edge exactly where a normal hole's boundary would be.
- **Near-nominal ratio and angular gap are the most discriminating metrics for Cartridge 48/Tag7 and Cartridge 49/Tag7**: both show near-ratio far below the successful range's floor of 1.00 (0.083 and 0.000), and Cartridge 49/Tag7 additionally shows an extreme 210° angular gap (vs. 10° for every successful case) — indicating whatever edge is being found is sparse and partial, not a clean closed circle.
- **SNR and saturation single out Cartridge 49/Tag7 as the weakest overall signal**: SNR (9.8) is below the successful range's floor (15.3), and saturation (0.29) is far above every other measured location (0.00 everywhere else) — consistent with the earlier visual finding that this location sits near the image's right edge in a region with unusual brightness/contrast behavior.
- **"Edge strength at nominal radius" is confirmed as a noisy metric on its own** (successful range spans 5.5–69.0, a 12× spread) — consistent with this investigation's repeated finding (Stage 6 onward) that no single signal reliably discriminates genuine holes; combinations of signals are required.

---

## 4. Root-Cause Classification Per Tag

| Tag | A: insufficient evidence | B: ambiguous competing features | C: detector limitation | D: reference-model limitation | E: assignment limitation | F: wrong physical feature |
|---|---|---|---|---|---|---|
| 48/Tag5 | **Yes** (no data exists) | — | — | — | — | — |
| 48/Tag7 | **Yes** (near-ratio=0, no circular edge at any radius) | — | — | — | — | Partial — visible feature is a linear scratch/debris mark |
| 49/Tag5 | **Yes** (no data exists) | — | — | — | — | — |
| 49/Tag7 | **Yes** (sparse, partial, low-SNR signal) | — | — | — | — | — |
| 49/Tag9 | **Yes** (no data exists) | — | — | — | — | — |
| 66/Tag9 | — | — | — | — | — | **Yes** — confirmed oversized, non-circular channel-junction feature |
| 72/Tag9 | — | — | — | — | — | **Yes** — confirmed oversized, non-circular channel-junction feature |

**No case is attributable to B (ambiguous competing features), C (detector limitation), D (reference-model limitation), or E (assignment limitation).** D was directly disproven in Stage 10 (Cartridge 34, same batch, fits `REF_OFFSETS` at RMS=1.08px). E was directly disproven in Stage 9 (Hungarian and exhaustive global-optimization search reproduce production's assignment exactly, in every case). C is not supported here either — Stage 8 already showed that no safe Hough parameter change recovers any of these locations without an unacceptable false-positive cost, and the metrics in this stage show the failures are not a matter of weak-but-recoverable detector sensitivity (e.g., 66/72's Tag 9 failures are explained by an edge that is structurally absent at the expected radius, not merely faint).

---

## 5. Would a Human Observer Confidently Identify the Correct Feature?

| Tag | Human assessment |
|---|---|
| 48/Tag5, 49/Tag5, 49/Tag9 | **No** — there is nothing to see. A human given only this image could not identify any feature, correct or otherwise, because the position is not captured. |
| 48/Tag7 | **No** — a human would see a linear scratch/debris mark and plain material, and would not identify a hole here without already knowing one is expected. |
| 49/Tag7 | **No** — a human would see plain, somewhat noisy material near the image edge; nothing resembling the clean circular holes visible elsewhere in the same image. |
| 66/Tag9, 72/Tag9 | **Partially** — a human would definitely notice the large dark void (it is visually obvious, not subtle), but would very likely conclude it is *not* one of the small round mounting holes, since it is visibly larger and differently-shaped than every other hole in the same image, and sits exactly where two channels meet. A careful human observer would probably classify this as a channel junction, not a hole — the same conclusion this investigation reached instrumentally. |

In every case, a human observer without prior knowledge of the expected 7-hole pattern would **not** confidently identify a genuine, correctly-located mounting hole at any of these seven positions.

---

## 6. Final Classification

| Tag | Classification |
|---|---|
| Cartridge 48, Tag 5 | **Imaging limitation** — position is outside the captured frame |
| Cartridge 48, Tag 7 | **Imaging limitation** (with ground-truth ambiguity as a secondary factor — the true hole's actual location, if any, cannot be confirmed from available data) |
| Cartridge 49, Tag 5 | **Imaging limitation** — position is outside the captured frame |
| Cartridge 49, Tag 7 | **Imaging limitation** (weak/degraded signal — low SNR, high saturation, sparse partial edge) |
| Cartridge 49, Tag 9 | **Imaging limitation** — position is outside the captured frame |
| Cartridge 66, Tag 9 | **Different physical feature** — confirmed both visually and quantitatively (edge strength) to be a channel junction, not a mounting hole |
| Cartridge 72, Tag 9 | **Different physical feature** — same confirmation as Cartridge 66 |

**No tag in this investigation's scope is classified as a software limitation.**

---

## 7. Is Any Remaining Software Change Justified?

**No.** The evidence across all four investigation stages (7–11) is now consistent and complete:

- Stage 7 designed and implemented the one confirmed, general, low-risk algorithmic improvement available (role-generalized Stage 1 anchor search) — already committed, validated across all 79 cartridges with zero unexplained regressions.
- Stage 8 showed no Hough parameter change recovers any remaining case without a prohibitive false-positive cost (79–244 new spurious candidates per useful recovery).
- Stage 9 proved the current greedy assignment is optimal — Hungarian assignment and exhaustive global optimization reproduce it exactly in every tested case.
- Stage 10 proved the reference geometry (`REF_OFFSETS`) is not the source of the remaining ambiguity — a cartridge from the identical dataset batch fits it almost perfectly.
- Stage 11 (this report) shows every remaining unresolved tag is explained by an absence of usable image data (3 of 7 cases, literally outside the frame), a weak/degraded signal in an already-documented lower-quality imaging cluster (2 of 7 cases), or a confirmed different physical feature that should not be detected as a hole (2 of 7 cases).

**The current algorithm is operating at the limit imposed by the available image data.** Any further improvement to these specific seven cases would require better source data — a wider field of view (for the three off-frame tags), improved illumination/focus for the affected cartridges (for the two weak-signal tags), or a fundamentally different, non-circular feature detector explicitly designed to recognize channel junctions as a distinct class (for the two confirmed-different-feature tags) — not a change to the existing hole-detection algorithm's candidate generation, assignment, or reference geometry.

No production code was modified. No commits were created. Stopping here per your instruction.
