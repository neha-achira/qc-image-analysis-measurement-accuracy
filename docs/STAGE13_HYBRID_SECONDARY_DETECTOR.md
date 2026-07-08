# Stage 13 — Hybrid Secondary Detector: Design & Prototype

**Status:** Design and prototype complete (analysis-only). No production code modified. No commits created.
**Branch:** `stage13-hybrid-secondary-detector`
**Objective:** design and prototype an additive, segmentation-based secondary detector for genuine holes the Hough pipeline misses, with zero regressions to the existing validated pipeline.

---

## 1. Segmentation Approach Investigated

One integrated pipeline was built and prototyped (`stage13_common.py`), combining every technique in scope:

**Adaptive thresholding** (Gaussian-weighted, inverse binary) → **morphological close then open** (5×5 kernel, to bridge small gaps and remove speckle noise) → **connected components** (8-connectivity) → per-component **contour extraction** → **ellipse fitting** on each contour. This is a standard, well-established segmentation chain, not a novel design — chosen specifically because it does not require the boundary to be circular at any stage, unlike Hough.

For every resulting candidate, the following were computed exactly as required: centroid, area, perimeter, circularity (`4π·area/perimeter²`), solidity (`area/convex_hull_area`), aspect ratio (from the fitted ellipse's axes), equivalent diameter (`√(4·area/π)`), ellipse parameters, edge strength (mean gradient magnitude along the traced contour), and distance from the predicted tag position.

---

## 2. Evidence Gathering — Which Metrics Actually Separate the Categories

Real, measured examples (not synthetic or invented) were gathered across 4 categories using this exact pipeline: **17 genuine holes** (Cartridges 72, 66, 34, 18, 61, 48, 49 — spanning multiple dataset batches), **2 channel junctions** (Cartridge 66/Tag 9, Cartridge 72/Tag 9 — the only two confirmed examples in the entire validated dataset), **2 scratch/debris locations** (Cartridge 48/Tag 7, Cartridge 49/Tag 7 predicted positions), and **5 texture/background samples**.

| Metric | Genuine holes (n=17) | Channel junctions (n=2) | Scratch/debris (n=2, 1 found) | Texture (n=5, 1 found) | Separates cleanly? |
|---|---|---|---|---|---|
| **Aspect ratio** | 1.006 – 1.104 (one outlier: 2.147) | 1.211 – 1.467 | 25.13 | 12.14 | **Yes — best discriminator** |
| **Edge strength** | 4.50 – 5.86 (one outlier: 26.9) | 50.03 – 76.67 | 227.24 | 112.9 | **Yes — second-best discriminator** |
| Circularity | 0.185 – 0.219 (one outlier: 0.025) | 0.086 – 0.095 | 0.060 | 0.053 | Directionally useful (holes ~2× more circular than junctions) but does not cleanly separate the one low-quality hole outlier |
| Solidity | 0.121 – 0.260 | 0.276 – 0.330 | 0.678 | 0.379 | **Not reliable** — junctions show *higher* solidity than genuine holes, the reverse of what shape-analysis intuition would predict; not used in the gate |
| Equivalent diameter | 105.8 – 119.0px (one outlier: 161.6px) | 87.3 – 90.2px | 112.3px | 75.5px | **Not reliable alone** — junctions measure *smaller* than genuine holes in this pipeline (the segmentation isolates a brighter interior sub-region, not the full merged void), overlapping the scratch/debris range |

**One hole (Cartridge 48/Tag 4) is an outlier on every metric** — already known from Stage 7/11 to be a lower-quality match in an already-documented poor-image-quality cartridge. This is disclosed, not hidden: any gate built from this evidence will also reject this specific already-matched hole if it were ever re-evaluated, which is a reasonable and conservative outcome given its already-known weaker status.

**No thresholds were invented.** The gate below uses values that sit strictly between the full observed range of all 17 clean genuine-hole examples and both channel-junction examples.

---

## 3. Integration Design

The secondary detector is designed as a **new, isolated stage that runs strictly after the existing recovery pass**, with the following non-negotiable properties, all enforced structurally (not by convention):

- It receives the frozen anchor and the **already-finalized** `matched_recovery` dictionary from the existing pipeline — it never re-runs Stage 1, never re-runs Stage 2, and never re-invokes the recovery pass.
- It **iterates only over tags absent from `matched_recovery`** — a tag already present, however marginal its quality, is structurally invisible to this stage and cannot be touched, replaced, or reconsidered.
- It reads the same frozen predicted position (`_predict_positions(*best_anchor_cxy)`) used by every prior stage — no new geometric model, no new anchor logic.
- On success, it would add a new entry to the matched-tags structure for that tag only — precisely mirroring how the Stage 6 recovery pass integrates today.
- It performs its own bounds check (predicted position must be within the image) before running the (comparatively expensive) segmentation pipeline, exactly matching the recovery pass's own discipline.

This design was prototyped exactly as specified — as a standalone analysis script, never touching `detect_features.py` — and integrated against a faithful, already-validated replica of the full committed pipeline (Stage 1 role-generalized search → Stage 2 → recovery pass, identical to the replicas used and cross-validated in Stages 7–12).

---

## 4. Quality Gate

**Gate: `aspect_ratio ≤ 1.15` AND `edge_strength ≤ 15.0`.**

Justification, per metric, using only the measured evidence in §2:
- **Aspect ratio ≤ 1.15**: every one of the 17 clean genuine-hole examples measured at or below 1.104; both channel junctions measured at or above 1.211. A threshold anywhere in the wide gap between these two ranges achieves the same separation on the available evidence; 1.15 was chosen near the lower edge of that gap to be conservative.
- **Edge strength ≤ 15.0**: every clean genuine hole measured at or below 5.86; both channel junctions measured at or above 50.03 — an order of magnitude apart. 15.0 sits comfortably inside this very wide gap.
- **Circularity was deliberately not included** in the gate — the evidence in §2 shows it is directionally correct but noisier (and would reject the same already-known-weak hole outlier that the primary two metrics already reject, adding no further discriminating power).
- **Solidity and equivalent diameter were deliberately excluded** — the evidence shows solidity moves in the *wrong* direction to be usable, and equivalent diameter overlaps between categories.

---

## 5. Validation — Full 79-Cartridge Prototype

The complete prototype (existing pipeline replica + secondary detector with the gate above) was run against all 79 validated cartridges (553 tag-slots).

| Metric | Result |
|---|---|
| Tags matched by the existing pipeline (unchanged) | 541 / 553 |
| Tags missing before the secondary detector runs | 12 / 553 |
| **Secondary detector proposed additions** | **0** |
| False positives introduced | 0 |
| Regressions (any existing match altered) | **0 — structurally impossible by design, confirmed empirically** |
| Precision | Unchanged (100%, per the last confirmed measurement in Stage 6/7 — no new positive predictions were made to affect it) |
| Recall | Unchanged — no new tag recovered |
| F1 | Unchanged |

**The safe, evidence-derived gate recovers nothing, anywhere, across the entire validated dataset.**

### Why, specifically — a critical scope finding

The secondary detector, exactly as scoped by this stage's own requirements ("only executes for tags that remain unmatched after Stage 1, Stage 2, and the recovery pass"), **never gets an opportunity to evaluate Cartridge 66 or 72's Tag 9 at all** — because Tag 9 is *not* in either cartridge's missing-tags list. The existing pipeline already assigns it a (low-confidence, unconfirmed) match. The secondary detector, by the very design this stage required (never touch or reconsider an existing match, however weak), is structurally unable to reach the two cases that originally motivated this entire investigation line.

### Sensitivity check: relaxing the gate

To characterize this precisely rather than leave it as a theoretical concern, the gate was deliberately relaxed to admit both known channel junctions' measured values (`aspect_ratio ≤ 1.6`, `edge_strength ≤ 100`) and the full 79-cartridge run repeated. Result: **3 additional tag-slots recovered — in Cartridges 33 and 50, not 48, 49, 66, or 72** — with circularity values (0.029–0.074) even lower than the channel junctions' own (0.086–0.095), and two of the three sitting 307–350px from their predicted position. Cartridge 48 and 49's specific unresolved tags (5, 7, and for 49, 9) were **still not recovered even under this relaxed gate** — confirming, via full pipeline replay rather than a spot check, Stage 11/12's conclusion that no plausible hole-shaped feature exists there at all.

This sensitivity result is itself informative: **a gate loose enough to reach the channel junctions (if they were reachable) also admits lower-confidence, more questionable candidates elsewhere in the validated dataset that this investigation has no basis to confirm as genuine** — direct, empirical evidence of the false-positive risk that motivated keeping the gate conservative in the first place.

---

## 6. Blast-Radius Analysis

**No existing successful cartridge is changed, under either the safe or the relaxed gate — confirmed by construction and empirically.** The detector only ever writes to tag keys absent from the existing `matched_recovery` result; it has no code path capable of touching an existing entry. Under the safe gate, zero new entries were added anywhere, so the question is moot. Under the relaxed gate, exactly 3 new entries were added, all to tags that were already missing beforehand (Cartridge 33/Tag 7, Cartridge 50/Tags 3 and 7) — no previously-matched tag in any of the 79 cartridges was altered, added to, or removed under any tested configuration.

---

## 7. Recommendation

**The secondary detector, as designed and prototyped, is not suitable for production deployment aimed at the four cases in scope (Cartridges 48, 49, 66/Tag 9, 72/Tag 9).**

What prevents deployment, precisely:

1. **It cannot reach Cartridge 66/72's Tag 9 at all**, regardless of gate tuning, because those tags already carry a (weak) match from the existing pipeline and this stage's own integration requirement (never reconsider an existing match) structurally excludes them. Addressing this would require a different scope decision — e.g., allowing the secondary detector to *challenge* a low-confidence existing match, not just fill a gap — which is a materially different, higher-risk design than what was specified and validated here.
2. **It cannot recover Cartridge 48 or 49's remaining unresolved tags** (5, 7, and 9) under any gate setting tested, safe or relaxed — consistent with Stage 11 and 12's independent conclusion that no plausible hole-shaped feature exists at those locations in the current images.
3. **The only gate setting that would admit the channel-junction shape profile also admits materially less-confident candidates elsewhere** (lower circularity, greater distance from prediction) in cartridges outside this investigation's scope, with no independent way to confirm those candidates are genuine — a false-positive risk this investigation cannot responsibly clear.

**What the prototype does demonstrate cleanly**: the additive integration pattern itself is safe (zero regressions, confirmed both structurally and empirically across all 79 cartridges under two different gate configurations), and the evidence-based metric selection (aspect ratio, edge strength) is sound and well-separated for the cases it *can* see. If a future investigation specifically targets a scope change — allowing re-evaluation of low-confidence existing matches, with its own dedicated risk analysis for that materially different and riskier design — this prototype's segmentation pipeline and metric evidence would be a reasonable starting point. As scoped today, it is not recommended for production.

No production code was modified during this investigation. No commits were created. Stopping here per your instruction.
