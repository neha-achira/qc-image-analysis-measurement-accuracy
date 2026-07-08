# Stage 15 — Leica Ground Truth Validation

**Status:** Analysis complete. No production code modified. No commits created.
**Branch:** `stage15-leica-ground-truth-validation`

---

## 0. Data Inventory — What Ground Truth Actually Exists

Four reference files were provided in the repository root:

| File | Content | Usable as ground truth? |
|---|---|---|
| `image.png` | A Leica LAS AF exported measurement table for **"BP 48"**, source file `Holes_ch00.png`, all 7 tags (1,3,4,5,6,7,9), each with nominal/measured/deviation/LSL/USL/PASS-FAIL | **Yes — precise, tag-labeled, unambiguous** |
| `image (1).png` | The same table format for **"BP 61"**, same source filename, all 7 tags | **Yes — used as a control/baseline** |
| `48_holes.png` | A Leica LAS AF annotated micrograph crop showing crosshair measurement markers and mm labels on several visible holes | **Qualitative only** — see limitation below |
| `61_holes.png` | The same style of annotated crop for Cartridge 61 | **Qualitative only** |

**Critical limitation, stated explicitly per your instruction:** the two annotated crop images (`48_holes.png`, `61_holes.png`) show a **partial crop** of each cartridge, with no pixel-coordinate metadata and no reliable, verifiable coordinate transform back to the full-resolution `Holes_ch00.png` files this project's pipeline processes. Attempting to read a label in the crop and assign it to a specific numbered tag risks being wrong — a preliminary attempt to do exactly this produced a labeled-diameter set that did not match the tag-labeled table's values, confirming the correspondence is not reliable without further information. **No pixel centre coordinates and no per-tag identity are read from these two crop images anywhere in this report.** They are used only for one qualitative purpose: confirming that a human operator visually located and placed a measurement crosshair on real, physically visible circular features in these cartridges.

**Scope limitation, stated explicitly:** ground truth of either kind (table or image) exists **only for Cartridge 48 and Cartridge 61**. **No Leica reference data of any kind exists in this project for Cartridge 49, Cartridge 66, or Cartridge 72.** Per your instruction not to invent data, this report cannot and does not draw conclusions about those three cartridges. Cartridge 48 receives the full requested analysis; Cartridge 61 is used as a control (a cartridge already established, in Stages 7–11, as high-confidence and fully matched) to characterize how much production and Leica measurements normally differ even when detection is unambiguous.

---

## 1–2. Cartridge 61 — Control Comparison

| Tag | Leica diameter | Production diameter | Difference | Production quality |
|---|---|---|---|---|
| 1 | 0.49mm | 0.5250mm | +0.035mm (7.1%) | 36/36, near_ratio=1.0 |
| 3 | 0.50mm | 0.5175mm | +0.0175mm (3.5%) | 36/36, near_ratio=1.0 |
| 4 | 0.52mm | 0.5225mm | +0.0025mm (0.5%) | 36/36, near_ratio=1.0 |
| 5 | 0.51mm | 0.5000mm | −0.01mm (2.0%) | 36/36, near_ratio=1.0 |
| 6 | 0.49mm | 0.5300mm | +0.04mm (8.2%) | 36/36, near_ratio=1.0 |
| 7 | 0.52mm | 0.5250mm | +0.005mm (1.0%) | 36/36, near_ratio=1.0 |
| 9 | 0.52mm | 0.5100mm | −0.01mm (1.9%) | 36/36, near_ratio=1.0 |

**Even under ideal detection conditions (every tag at perfect 36/36 ray-cast quality), Leica and production measurements differ by up to 8.2%,** most plausibly reflecting a genuine methodological difference (Leica's operator-placed crosshair diameter vs. this pipeline's 36-ray subpixel threshold-crossing median) rather than a detection error — both systems agree on PASS in every case, and there is no systematic one-directional bias (production reads higher in 5 of 7 tags, lower in 2). **This ~0–8% band is the baseline measurement-methodology noise floor** against which Cartridge 48's differences must be judged — a difference within this band reflects normal measurement variation, not a detection defect.

---

## 3–5. Cartridge 48 — Full Comparison Against Leica Ground Truth

| Tag | Leica diameter | Production diameter | Difference | Production quality (n_hit / near_ratio / fallback) |
|---|---|---|---|---|
| 1 | 0.46mm PASS | 0.4225mm **FAIL** | −0.0375mm (8.1%) | 20/36, 0.333, normal |
| 3 | 0.51mm PASS | 0.500mm PASS | −0.01mm (2.0%) | 3/36, 0.000, **total_failure** |
| 4 | 0.47mm PASS | 0.510mm PASS | +0.04mm (8.3%) | 28/36, 0.389, normal |
| 5 | 0.52mm PASS | **not detected** | n/a | no candidate assigned |
| 6 | 0.51mm PASS | 0.500mm PASS | −0.01mm (2.0%) | 6/36, 0.000, **total_failure** |
| 7 | 0.52mm PASS | **not detected** | n/a | no candidate assigned |
| 9 | 0.49mm PASS | 0.500mm PASS | +0.01mm (2.0%) | 3/36, 0.000, **total_failure** |

**A significant, evidence-based correction to Stage 11's conclusion**: the Leica table's source-file field reads `Holes_ch00.png` — the exact same image this pipeline processes. Leica successfully measured Tags 5 and 7 from that same file. **These two holes are not "outside the captured image" in any absolute sense** — Stage 11's classification of Cartridge 48/Tag 5 as an imaging/field-of-view limitation is corrected here: the hole is real, present in the same source image, and measurable; production's search for it fails for a different reason (below).

**Why production diverges — the first algorithmic decision responsible:** Cartridge 48 has **zero** high-confidence candidates anywhere in the cartridge (established across Stages 7, 9, 10, and 14 — every currently-matched tag sits at or below the 5th percentile of the entire validated dataset's confidence distribution, and 3 of 6 total-failure-fallback cases in the *entire 79-cartridge dataset* are in this one cartridge). Stage 1's anchor selection is therefore forced to choose its best-scoring anchor from among only weak candidates. That anchor's predicted position for Tag 5, (1923,5628), falls 702px beyond the image's actual height (4926px) — not because the hole is absent, but because the anchor derived from weak candidates is imprecise enough to mispredict where to look. The same anchor imprecision places Tag 7's predicted position, (3344,3314), in a region where — per Stage 8's exhaustive parameter sweep — no Hough candidate registers at any safe setting. Whether this reflects the true Tag 7 hole being genuinely difficult for Hough to detect at its real (still not confidently identified) location, or simply being located far enough from the imprecise prediction that no reachable candidate was ever considered, cannot be resolved further without the exact Leica pixel centre — which, per §0, is not available.

**One candidate lead, disclosed as an open question, not a conclusion:** Stage 9 identified exactly one unused, perfect-quality (36/36) raw candidate in Cartridge 48, at (372,1976). Checking it against every tag's predicted position under the current anchor, its nearest prediction is Tag 3 (1289px) and Tag 1 (1416px) — not Tag 5 or Tag 7 as might be hoped, and far beyond any tolerance this project has validated as safe. **This candidate cannot be confirmed, on current evidence, as either missing tag's true hole**, and this report does not claim it is.

### Root-cause classification per tag

| Tag | Root cause | Reasoning |
|---|---|---|
| 1 | **(E) image quality**, contributing **(C) candidate assignment** | Both available raw candidates for this position are low-quality (Stage 7's trace showed Stage 1's own pick and Stage 2's substituted pick are both far from Leica's 0.46mm); the measurement discrepancy (8.1%) exceeds the Cartridge 61 noise floor and flips PASS→FAIL |
| 3 | **(E) image quality** | `total_failure` ray-cast fallback, yet the diameter (0.500mm) happens to be within the Cartridge 61 noise band of Leica's 0.51mm — low detection confidence did not, in this instance, produce a materially wrong measurement or PASS/FAIL disagreement |
| 4 | **(E) image quality** | Moderate confidence (28/36); 8.3% difference is within the established noise band (comparable to Cartridge 61's own 8.2% maximum); same PASS side |
| 5 | **(B) anchor selection** | Confirmed by Leica to be a real, in-frame, passing hole; production's imprecise anchor predicts a position beyond the image boundary |
| 6 | **(E) image quality** | `total_failure` fallback, but diameter within the established noise band; no PASS/FAIL disagreement |
| 7 | **(B) anchor selection**, possibly compounded by **(A) candidate generation** | Confirmed real and passing by Leica; predicted position is in-frame but unreachable by any safe Hough configuration (Stage 8); cannot determine, without the true pixel centre, how much of the gap is anchor imprecision vs. genuine detection difficulty at the true location |
| 9 | **(E) image quality** | `total_failure` fallback, diameter within noise band, no disagreement |

---

## 6. Where Differences Arise

- **Centre location**: cannot be assessed — no Leica pixel centre is available for any tag (per §0), so a location comparison is not possible and is not attempted.
- **Diameter estimation**: the dominant source of difference for Tags 1, 3, 4, 6, 9 — all already have a production measurement, and the gap (2.0–8.3%) is consistent with ordinary measurement noise (Cartridge 61's control shows the same system produces up to 8.2% difference with zero detection ambiguity) except for Tag 1, where the gap is large enough to flip the PASS/FAIL decision.
- **Missed detection**: the sole source of difference for Tags 5 and 7 — production assigns no candidate at all, while Leica reports a normal, passing measurement.
- **Incorrect assignment**: a contributing factor for Tag 1 specifically (Stage 7 already documented a Stage 1→Stage 2 substitution between two similarly-uncertain candidates for this exact tag).

---

## 7. Final Table

| Cartridge | Tag | Leica diameter | Production diameter | Diff. | Leica hole visible? | Production found it? | Root cause | Software-fixable? | Recommended action |
|---|---|---|---|---|---|---|---|---|---|
| 48 | 1 | 0.46mm | 0.4225mm (FAIL) | −0.0375mm | Yes | Yes (wrong confidence) | E (image quality), C | **No** — no better candidate exists in current data (Stage 7/9) | Flag for manual/Leica re-verification; do not attempt automated reassignment |
| 48 | 3 | 0.51mm | 0.500mm | −0.01mm | Yes | Yes | E (image quality) | N/A — within noise band, no action needed | None |
| 48 | 4 | 0.47mm | 0.510mm | +0.04mm | Yes | Yes | E (image quality) | N/A — within noise band | None |
| 48 | 5 | 0.52mm | not detected | n/a | **Yes (confirmed by Leica)** | **No** | **B (anchor selection)** | **No** — no higher-confidence anchor is available from current candidates (Stages 7,9,10,14) | Requires a materially different anchor strategy or improved imaging for this cartridge cluster, not a parameter change |
| 48 | 6 | 0.51mm | 0.500mm | −0.01mm | Yes | Yes | E (image quality) | N/A — within noise band | None |
| 48 | 7 | 0.52mm | not detected | n/a | **Yes (confirmed by Leica)** | **No** | **B (anchor selection) / A (candidate generation, unresolved)** | **No** — true location not identifiable from current evidence | Same as Tag 5; additionally, obtaining the true Leica pixel centre would let a future investigation determine definitively whether Hough could ever detect it |
| 61 | all | (control) | (control) | 0.5–8.2% | Yes | Yes | — (baseline noise) | N/A | None — used to establish the noise floor above |
| 49 | — | **no data** | — | — | — | — | **Cannot be determined — no Leica reference exists** | — | Obtain Leica reference data before further investigation |
| 66 | Tag 9 | **no data** | — | — | — | — | **Cannot be determined — no Leica reference exists** | — | Obtain Leica reference data before further investigation |
| 72 | Tag 9 | **no data** | — | — | — | — | **Cannot be determined — no Leica reference exists** | — | Obtain Leica reference data before further investigation |

---

## Summary

The Leica ground truth for Cartridge 48 **confirms** that Tags 5 and 7 are genuine, real, passing holes present in the same source image this pipeline already processes — correcting Stage 11's characterization of these as an imaging/field-of-view limitation. The actual cause is that Cartridge 48 has no high-confidence candidate anywhere to anchor from (independently established in four prior stages), producing a geometric prediction imprecise enough to miss both real holes entirely. This is not resolved by any software change already evaluated in Stages 7–14 — no better candidate or anchor exists in the current data — and this report does not identify one either. What this stage adds is a materially strengthened case, now backed by real ground truth rather than inference alone, for the standing recommendation (Stages 7, 8, 11) that the 34-50/WB(2) dataset cluster needs dedicated attention to its imaging conditions, and a new, concrete recommendation: **obtaining exact Leica pixel centres for Tags 5 and 7 (not just diameters) would let a future investigation determine conclusively whether the true holes are detectable by Hough at all** — a question this report can raise but, per your explicit instruction against inventing coordinates, cannot answer with the data available today.

No production code was modified during this investigation. No commits were created. Stopping here per your instruction.
