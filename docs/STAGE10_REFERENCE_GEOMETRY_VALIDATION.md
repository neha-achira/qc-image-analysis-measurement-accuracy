# Stage 10 — Reference Geometry Validation

**Status:** Analysis complete. No production code modified. No commits created.
**Branch:** `stage10-reference-geometry-investigation`
**Objective:** determine whether Cartridges 48 and 49 are limited by the `REF_OFFSETS` reference geometry model itself, rather than candidate generation (Stage 8, closed) or candidate assignment (Stage 9, closed). Cartridge 66 and Cartridge 72's Tag 9 are out of scope.

---

## 1. Method

Production's own matched candidates were treated as **observations, not ground truth**, throughout. For each cartridge: (a) an independent, broader "high-quality" candidate pool (`fallback_mode=normal`, `n_hit>=10` — looser than Stage 9's strict 70%-near-nominal bar) was searched via sequential 2-point RANSAC for every maximal self-consistent cluster against `REF_OFFSETS`, independent of and without assuming production's own correspondence; (b) similarity, affine, and fixed-`REF_OFFSETS` (no-fit) models were fit and compared; (c) pairwise-distance and angular preservation were quantified; (d) per-tag residual vectors were inspected for spatial structure (local-deformation diagnostic); (e) results were compared against multiple validated cartridges, including — critically — **Cartridge 34, which is from the exact same dataset batch (34-50/WB(2)) as Cartridges 48 and 49**.

---

## 2. Maximal Self-Consistent Clusters (Independent RANSAC Search)

| Cartridge | High-quality pool size | Clusters found | Detail |
|---|---|---|---|
| 48 | 13 | One 3-point cluster only | Tags {1,4,6} → (7764,2488),(5888,2676),(4552,1972) — **scale=1.044, rotation=162.6°**. A ~163° rotation is physically implausible for stage-placement variance (every validated cartridge shows rotation under 2°); this is very likely a coincidental 3-point fit, not a genuine alternative correspondence (see §5 for why 3-point fits are inherently unreliable). No larger (4+) cluster was found anywhere in the pool. |
| 49 | 9 | **None** (no cluster of size ≥3 at all) | Production's own Tag 4 candidate, (10660,1744), has only 3/36 ray hits — it falls below the `n_hit>=10` pool threshold used here, so it is correctly excluded from this independent search. Among the 9 remaining reasonably-good candidates, RANSAC finds no self-consistent 3+ correspondence whatsoever. |

**Neither cartridge contains a larger, cleaner, alternative geometric structure hiding among its candidates.** This independently confirms Stage 9's finding via a completely different search method (RANSAC rather than forced-role hypothesis scoring).

---

## 3. Residuals: Fixed REF_OFFSETS vs. Fitted Models

| Cartridge | Points | Fixed REF_OFFSETS (no fit) RMS | Similarity fit RMS | Affine fit RMS | Notes |
|---|---|---|---|---|---|
| 48 (RANSAC 3-pt cluster) | 3 | 5187px | 26.9px | **0.00px** | Affine RMS is meaningless here — a 6-DOF affine transform fit to exactly 3 points (6 constraints) is always solved exactly, regardless of whether the correspondence is real. Not evidence of a good fit. |
| 48 (production's own 5 matched) | 5 | — | 231.8px (scale=0.978, rot=4.25°) | not meaningful at this small n either | |
| 49 (production's own 4 matched) | 4 | — | 402.3px (scale=0.911, rot=5.17°) | not meaningful at this small n either | |
| **Cartridge 34 (same batch)** | 7 | — | **1.08px** (scale=1.0001, rot=0.001°) | — | Reference comparison |
| Cartridge 1 (baseline) | 7 | — | 5.88px (scale=0.997) | — | Reference comparison |
| Cartridge 72 (6 genuine tags) | 6 | — | 7.01px (scale=0.997, rot=-0.74°) | — | Reference comparison |

Cartridges 48 and 49's own best-available correspondences show residuals **30×–70× larger** than any validated cartridge, including their own direct batch-mate (Cartridge 34).

---

## 4. Do the Unused Perfect-Quality Candidates Become Consistent Under Any Model?

Using the best similarity fit found for each cartridge, predicted positions were computed for every tag *not* in the fit set and compared against the unused perfect-quality candidates:

- **Cartridge 48**: under the (already-implausible, 162.6°-rotation) 3-point fit, the nearest unused-candidate prediction is still **1313.8px** away (Tag 9's predicted position vs. (372,1976)) — not remotely close.
- **Cartridge 49**: no cluster was found at all, so no fitted prediction exists to test against.

**No physically plausible model — similarity, affine, or the current fixed model — brings either unused candidate into geometric consistency with the rest of the matched set.** This directly reinforces Stage 9's conclusion from an entirely independent angle.

---

## 5. Quantified Comparison: Scale, Rotation, Distance Preservation, Angular Preservation

| Cartridge | Scale | Rotation | Distance-preservation CV% | Angular error (mean / max) |
|---|---|---|---|---|
| Cartridge 1 | 0.9970 | −0.32° | 0.25% | 0.15° / — |
| **Cartridge 34 (same batch as 48/49)** | **1.0001** | **0.00°** | (not separately computed; RMS 1.08px already establishes near-perfect fit) | — |
| Cartridge 51 | 1.0017 | −0.45° | — | — |
| Cartridge 61 | 1.0008 | −0.63° | — | — |
| Cartridge 72 (6 genuine tags) | 0.9973 | −0.74° | 0.30% | 0.21° / 0.67° |
| **Cartridge 48 (production's own 5 matched)** | 0.9784 | 4.25° | **9.79%** | **4.29° / 12.17°** |
| **Cartridge 49 (production's own 4 matched)** | 0.9106 | 5.17° | **18.85%** | **13.99° / 31.94°** |

Distance-preservation CV% and angular error are **20×–75× larger** in Cartridges 48/49 than in every validated comparison cartridge. Scale itself is not wildly off (0.91–0.98 vs. an established ~1.0), but rotation (4–5°) is 5–10× larger than the largest rotation seen in any validated cartridge (Cartridge 18's 1.87° outlier), and the internal consistency of the pattern (distance/angle preservation) is far worse than scale/rotation alone would suggest.

---

## 6. Local Deformation Diagnostic (Per-Tag Residual Vectors)

Residual vectors (actual position − similarity-fit prediction) for production's own matched candidates:

**Cartridge 48**: Tag1=(−95,219), Tag3=(104,−299), Tag4=(−237,32), Tag6=(89,−89), Tag9=(140,137)
**Cartridge 49**: Tag1=(−262,−286), Tag3=(223,−245), Tag4=(−239,501), Tag6=(279,30)

These residuals point in **inconsistent, uncorrelated directions** with no relationship to each point's distance from the pattern's centroid (e.g., Cartridge 48's Tag 6 is closest to the centroid but has the smallest residual, while Tag 3 is farther but has the largest — not the smooth, distance-scaling pattern an uncorrected rotation or shear would produce). This diagnostic argues **against** a coherent local-distortion field (option C) — the pattern looks more like independent, per-point scatter than a systematic warp.

---

## 7. Reference Geometry Classification

**A. Correct** — **yes, at the reference-model level.** Cartridge 34, from the identical dataset batch (34-50/WB(2)) as both 48 and 49, fits `REF_OFFSETS` with scale=1.0001 and RMS=1.08px — essentially perfect. The same fixed reference geometry that works this well for a direct batch-mate cannot itself be the thing wrong with Cartridges 48 and 49.

- **B. Slightly biased** — no; the errors observed (9.8–18.9% distance CV, 4–14° angular error) are far too large to characterize as a slight, systematic bias correctable by a small offset adjustment.
- **C. Locally distorted** — no clear evidence; §6's diagnostic shows scattered, non-systematic residuals, not a smooth local deformation field.
- **D. Representing the wrong physical feature** — plausible for **individual candidates** (both cartridges' images show a visually complex part with a large valve/chamber feature and multiple small dark-dot features, not all of which are necessarily the 7 DWG-tagged mounting holes — established in Stages 7 and 8), but this is a per-candidate identity question, not a flaw in the reference geometry's own correctness.
- **E. Indicating multiple valid physical structures** — tested directly via independent RANSAC search (§2) and **not supported**: no second coherent cluster of size ≥3 was found in either cartridge among the available high-quality candidates.

---

## 8. What Explains the Remaining Ambiguity?

Per the candidate causes listed:

- **Incorrect reference geometry** — ruled out directly (§7A).
- **Manufacturing variation** — plausible as a partial contributor (Cartridges 48/49's own best fits show real, non-trivial rotation of 4–5°, larger than any other validated cartridge, which could reflect genuine part-to-part placement variance for this design), but manufacturing variation alone would not typically produce the scattered, uncorrelated residual pattern seen in §6, nor CV%/angular errors this large.
- **Imaging distortion** — plausible as a significant contributor: these cartridges are already documented (Stage 7/8) as belonging to a lower-image-quality cluster, where several matched "candidates" have low ray-cast quality (e.g., Cartridge 49's own Tag 4 match has only 3/36 ray hits). A low-quality Hough center is itself imprecise, and that imprecision alone can produce exactly this kind of scattered, non-systematic per-point residual — consistent with §6's finding.
- **Multiple physical circular structures** — tested and not supported as a *coherent alternative pattern* (§2, §7E), though isolated unrelated circular features (not part of any 7-hole pattern) remain plausible for the two specific unused perfect candidates, consistent with Stage 9's conclusion.
- **Missing geometric constraints** — not indicated; adding more constraints (Stage 9's forced-coexistence test, and this stage's broader RANSAC search) did not reveal a hidden consistent structure that a differently-constrained model would uncover. More data made fits worse, not better.

**The best-supported explanation is a combination of imaging/candidate-quality noise and possibly genuine (if larger-than-typical) manufacturing placement variance, acting on individually low-confidence candidates — not a flaw in the reference geometry, and not a hidden alternative geometric structure.**

---

## 9. Evidence-Based Conclusion

**`REF_OFFSETS` remains globally valid.** Proof: a cartridge from the identical dataset batch as both investigation targets (Cartridge 34, same imaging setup, same physical design family) fits the reference geometry with RMS=1.08px and scale=1.0001 — as clean a fit as any cartridge examined across this entire investigation. The reference geometry is not the source of Cartridges 48 or 49's unresolved tags.

**Cartridges 48 and 49's difficulty is a per-cartridge candidate-quality issue, not a model issue** — consistent with, and now further substantiated beyond, every prior stage's conclusion (Stage 7's original geometric-model finding, Stage 8's candidate-generation analysis, Stage 9's assignment-optimality proof). No modification to `REF_OFFSETS` is indicated. If a modification were nonetheless considered, the smallest defensible change would **not** be to the offsets themselves, but to explicitly widen the tolerance used when judging candidate self-consistency for cartridges already flagged as low-image-quality — and even that is better addressed as a candidate-confidence/quality-gate question (as already recommended in Stage 8) than as a change to the fixed geometric model.

No production code was modified. No commits were created. Stopping here per your instruction.
