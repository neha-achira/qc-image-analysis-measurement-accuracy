# Stage 12 — Leica Gap Investigation

**Status:** Analysis complete. No production code modified. No commits created.
**Branch:** `stage12-leica-gap-investigation`

---

## 0. Scope Clarification (read this first)

This investigation was reframed mid-stream based on direct clarification. The original framing assumed Leica runs its own independent, reverse-engineerable detection pipeline. That assumption was checked against this repository (`leica_calibration.py`, `validation_output/failure_taxonomy_classified.csv`) and found to be **false as a claim about this codebase**: every "Leica" reference in this project is a pixel-scale **calibration** source (um/px from Leica LAS AF MetaData), applied to the *same* Hough-detected `diameter_px` — there is no independent Leica detection or measurement data anywhere in this repository.

You subsequently clarified the real situation: an independent Leica LAS AF workflow exists **outside this repository**, where a **human operator** visually inspects and measures the holes our algorithm misses. We do not have that algorithm, its internal workings, or an exported ground-truth dataset. Per your explicit instruction, this report:

- **Does not** attempt to reverse-engineer Leica's proprietary software.
- **Treats the operator's ability to see and measure these holes as evidence that the source images contain sufficient information for detection** — i.e., these are not cases of "the data doesn't exist," except where Stage 11 already separately established that (the three off-frame tags, discussed in §6).
- Focuses on **what class of computer-vision algorithm, applied to the same images already in this project, could plausibly recover what a human operator sees** — compared against the current Hough-based pipeline.

---

## 1. Current Pipeline, Stage by Stage

| Stage | What it does today | Relevant limitation established in Stages 7–11 |
|---|---|---|
| Preprocessing | Crop to active area, 4× downsample, CLAHE, Gaussian blur | Not implicated — Stage 8 confirmed the preprocessed image itself is where the oversized/non-circular features are visible; blur/CLAHE do not destroy the evidence, they just don't help extract it either |
| ROI generation | None — the whole active area is searched uniformly at one scale | Not a distinguishing factor here |
| Candidate generation | `cv2.HoughCircles`, tuned to a fixed radius range and one accumulator threshold | **Directly implicated.** Requires the feature to present a strong, closed, circular-at-the-nominal-radius edge. Stage 8 proved no safe parameter adjustment recovers the channel-junction or weak-signal cases without a 79×–244× false-positive cost |
| Circle fitting / diameter estimation | 36-ray radial threshold-crossing, median of near-nominal hits | Assumes the boundary *is* circular at approximately the nominal radius; degrades gracefully (`fallback_mode`) but cannot report a meaningful diameter for a non-circular feature |
| Sub-pixel localization | Same ray-cast, taken at face value | Inherits the same circularity assumption |
| Feature classification | None beyond the Stage 1/2 geometric role assignment | There is no stage anywhere in the pipeline that asks "is this even circular?" independently of trying to measure it as if it were |

**The failure is fundamentally caused by relying on Hough circles specifically because Hough (and the ray-cast measurement built on top of it) has no representation for "a real feature that is not a circle of the expected size."** It either finds a circle or it doesn't; it cannot report "I found something, but it's elongated" or "I found something, but only part of its boundary is trustworthy." This is a structural property of the *feature model*, not a tuning problem — fully consistent with Stage 8's parameter-sweep evidence and Stage 11's edge-strength-at-nominal-radius measurements.

---

## 2. Illustrative Evidence (this investigation's own experiments)

To ground the methodology comparison below in real evidence rather than speculation alone, three alternative techniques were run read-only against the actual images at all 4 target locations, plus a known-genuine hole as a control (`stage12_experiments.py`; visualizations in `validation_output/stage12_leica_gap/`).

| Location | Contour + ellipse fit | Connected components (adaptive threshold) | Fast Radial Symmetry Transform (single-scale, illustrative) |
|---|---|---|---|
| Control: Cartridge 72/Tag 1 (genuine hole) | Ellipse found 54px away, aspect ratio 2.13 (not clean — see caveat below) | **Clean**: blob 1.8px from center, near-square bounding box (ratio 1.05) | Weak response at target (0.000), peak 129px away |
| Cartridge 66/Tag 9 (channel junction) | Small circular ellipse (aspect 1.05) but 195px from target — likely a different nearby feature | Blob 63.7px away, ratio 1.21 | Weak response at target (0.001), peak 82.5px away |
| Cartridge 72/Tag 9 (channel junction) | Elongated ellipse (aspect **2.04**) only 55px from target | Blob **7.0px** from target, ratio 1.15 | Weak at target, but the peak sits on a *locally curved portion* of the merged boundary, not its centroid (visualized in `cart72_tag9_radial_symmetry.png`) |
| Cartridge 48/Tag 7 (weak signal) | No plausible ellipse found | No plausible blob found | Highest peak value of all 5 tested locations (0.027) but 67.5px from the exact target |
| Cartridge 49/Tag 7 (weak signal) | No plausible ellipse found | Blob found, but extremely elongated (ratio **16.7**, 30×500px) — a linear artifact, not a hole | Weak everywhere |

**Honest caveat:** this Stage 12 Fast Radial Symmetry Transform implementation is a quick, illustrative single-scale version with hand-picked parameters — it underperformed even on the known-genuine control case, so its weak showing at the failure locations should **not** be read as evidence against the *method* in general, only against this rough implementation of it. The contour+ellipse and connected-components experiments are more informative here because their control-case behavior was either clean (connected components) or at least directionally sensible (ellipse fitting), giving more confidence in their signal at the failure locations.

**What this evidence supports:**
- At both channel-junction locations (66/72 Tag 9), a segmentation-style approach (connected components) finds a compact, only mildly non-circular region very close to the target — consistent with there being a plausible bright "island" sub-feature distinct from the full merged dark boundary, which is plausibly what a human operator's eye latches onto. Ellipse fitting's elevated aspect ratio at Cartridge 72 (2.04) is itself a useful, principled *diagnostic signal* current Hough-only fitting has no way to express at all.
- At both weak-signal locations (48/49 Tag 7), connected-components and contour fitting either find nothing or find something clearly linear/elongated — consistent with Stage 11's conclusion that there is no clear hole-shaped feature there, not merely a faint one Hough is under-sensitive to.

---

## 3. Alternative Methodologies — Evaluated Against the Specific Evidence

| Method | Expected recall improvement | False-positive risk | Compatibility with current pipeline | Computational cost | Implementation complexity |
|---|---|---|---|---|---|
| **Contour extraction + shape descriptors** | Low-moderate (as a *diagnostic*, not a hole-recovery mechanism) — cannot itself measure a non-circular feature as a "hole," but can flag one | Low, if used only to gate/annotate, not to auto-accept | High — could run as an additional check alongside existing Hough candidates without touching Stage 1/2 | Low | Low |
| **Edge chaining** (e.g. Canny + link partial edges) | Low for these specific cases — Stage 11 showed the weak-signal locations lack even a partial consistent edge to chain | Moderate (partial chains can hallucinate closure) | Moderate | Low | Moderate |
| **Connected components / region growing** | **Moderate** — the only tested method that cleanly isolated a compact, near-hole-shaped sub-region at both channel-junction locations while correctly finding nothing (or something clearly linear) at both weak-signal locations | Low-moderate — requires a defined "plausible hole" size/shape filter (already demonstrated informally in §2) | High — naturally produces a candidate center+extent that could feed the *existing* downstream measurement/assignment code unchanged | Low | Low-moderate |
| **Gradient-based circle fitting** (direct least-squares fit to gradient-weighted edge points, rather than Hough's accumulator) | Low for channel junctions (still assumes circularity); possibly moderate for weak-signal cases if any real partial edge exists | Low | Moderate | Low | Low-moderate |
| **Least-squares circle fitting** (fit a circle to a given point set) | Low — same circularity assumption as Hough; only useful *after* a non-Hough method has already found candidate boundary points | Low | High (drop-in replacement for the final fit step only) | Very low | Low |
| **RANSAC circle fitting** | Low-moderate — more robust to partial/noisy edges than plain least-squares, but still fundamentally assumes the underlying feature is circular; does not help at the channel junctions (confirmed non-circular) | Low-moderate | Moderate | Low | Moderate |
| **Radial symmetry transforms** (properly tuned, multi-scale) | **Uncertain from this investigation's evidence** — this stage's own quick test was inconclusive (weak even on the control); a properly validated implementation might do better, but this has not been demonstrated | Unknown — would require its own dedicated validation (in the spirit of the Stage 6 quality-gate work) before trusting | Moderate | Moderate | Moderate-high |
| **Template matching** | Low — requires the target to resemble a template hole; the channel-junction features are precisely the case where the real feature does *not* resemble a normal hole, so a hole template would not match, and a "channel-junction template" would be narrowly overfit to 2 known cases | Low, but narrow benefit | Moderate | Low-moderate | Moderate |
| **Ellipse fitting** | Low as a recovery mechanism, but **useful as a diagnostic** (demonstrated in §2 — correctly flagged Cartridge 72/Tag 9 as elongated) | Low | High — can run as an add-on classifier alongside existing candidates | Low | Low |
| **Active contours (snakes)** | Uncertain — could in principle shrink-fit around a genuine but low-contrast boundary at the weak-signal locations, but Stage 11 found little to no boundary evidence there to converge on in the first place | Moderate (can converge to spurious local minima without a good initialization) | Low — requires a fundamentally different processing stage | Moderate-high | High |
| **Watershed / segmentation** | **Moderate** — same underlying mechanism as connected components, generalized; most directly targets the "isolate the plausible interior sub-region from the surrounding merged/channel structure" opportunity identified in §2 for the channel-junction cases | Moderate — requires careful marker selection to avoid over- or under-segmentation | Moderate | Moderate | Moderate-high |
| **Hybrid detector** (e.g., Hough for normal holes + a segmentation-based secondary pass specifically for large/irregular candidates Hough rejects) | **Highest, of any option evaluated** — directly targets the specific, evidenced failure mode (channel junctions) without altering behavior for the 74/79 cartridges that already work | Low, if scoped as an additive, quality-gated secondary pass (following the exact precedent of the Stage 6 recovery pass) | **High** — can be added as a new, isolated stage after existing Hough candidate generation, feeding the same downstream Stage 1/2/measurement code, exactly mirroring how the Stage 6 recovery pass was integrated | Low-moderate | Moderate |

---

## 4. Ranking

1. **Hybrid detector (segmentation-based secondary pass, additive to existing Hough)** — highest expected benefit, lowest integration risk, directly evidenced.
2. **Connected components / watershed segmentation** (the mechanism underlying #1) — strong, demonstrated signal in this investigation's own experiments.
3. **Ellipse fitting and contour extraction as diagnostics** — low cost, low risk, immediately useful for correctly *classifying* channel-junction-type features even if not used to recover a measurement from them.
4. **RANSAC circle fitting, gradient-based circle fitting** — moderate, mostly relevant only if a future imaging improvement (per Stage 11) produces cleaner partial edges at the weak-signal locations; not useful for the channel junctions.
5. **Radial symmetry transforms, template matching, active contours** — plausible in principle, but either inconclusive (radial symmetry, per this stage's own test) or a poor conceptual fit to the specific evidenced failure modes (template matching, active contours) to justify prioritizing over the above.
6. **Least-squares circle fitting, edge chaining alone** — lowest priority; each assumes preconditions (existing boundary points, a chainable partial edge) that Stages 8 and 11 showed are largely absent in these specific cases.

**Not recommended under any ranking: further Hough parameter tuning (dp, param2, minDist, radius limits).** This was exhaustively swept and disproven in Stage 8 — every parameter capable of surfacing new candidates near these targets does so at a 79×–244× false-positive cost, independent of which alternative method is or isn't adopted.

---

## 5. Recommendation

**A hybrid detector: keep the existing Hough-based pipeline exactly as-is for the 74/79 (and now, post-Stage-7, effectively more) cartridges it already handles correctly, and add a new, additive, quality-gated secondary detection pass — based on connected-components/watershed segmentation rather than circular Hough — specifically for large, non-circular regions that Hough's radius/circularity constraints reject.**

This recommendation is directly supported by evidence from every prior stage in this investigation, not only this one:

- **Stage 7** established the precedent and proof-of-concept for exactly this kind of additive, non-invasive pass (the frozen-anchor recovery pass) — proving such a design can recover real holes with zero regressions across all 79 cartridges.
- **Stage 8** proved conclusively that the channel-junction failures are not a Hough-parameter problem, ruling out the cheaper alternative (just tune Hough) and motivating a genuinely different candidate-generation mechanism.
- **Stage 9 and 10** proved the assignment logic and reference geometry are not the bottleneck, meaning a new candidate-generation source could plug into the *existing, already-proven* Stage 1/2/measurement pipeline unchanged, exactly as the Stage 6 recovery pass did.
- **Stage 11's** quantitative edge-strength measurements (4.1–4.7 at the channel junctions vs. a 5.5–69 successful range) explain precisely why a circular-boundary method fails and a region/segmentation-based method — which does not require the *entire* boundary to be circular, only a compact plausible interior — has a structurally better chance.
- **This stage's own illustrative experiments** (§2) directly demonstrated connected-components segmentation isolating a compact, near-target region at both channel-junction cases while correctly finding nothing hole-like at both weak-signal cases — the exact discriminating behavior a production version of this approach would need.

For the three off-frame tags (Cartridge 48/Tag 5, Cartridge 49/Tag 5, Cartridge 49/Tag 9), **no computer-vision method evaluated in this report can help**, regardless of algorithm choice — the data does not exist in the current images. If a human Leica operator can see and measure these, the most likely explanation is that the Leica capture has a wider field of view than the images in this dataset — an imaging/capture-scope question, not a detection-algorithm question, and outside the scope of any software change to `detect_features.py`.

---

## 6. What Remains Genuinely Out of Software's Reach

Per Stage 11, restated here for completeness: 3 of the 7 currently-unresolved tags have no image data at all in the current dataset. No algorithm evaluated in this report — hybrid, segmentation-based, or otherwise — changes that fact. If closing this specific part of the gap to what a Leica operator can observe is a priority, it requires a wider-field-of-view capture, not a new algorithm.

No production code was modified during this investigation. No commits were created. Stopping here per your instruction.
