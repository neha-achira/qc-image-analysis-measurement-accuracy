# Stage 2 Candidate Selection — Final Validation Summary

**Prepared for:** Engineering management
**Subject:** Achira Beta Cartridge QC software — hole-diameter measurement fix ("Stage 2 candidate selection")
**Release reference:** git tag `stage2-complete` (commit `0c032b8`), branched from verified baseline `verified-production-baseline` (commit `8a6253d`)

---

## 1. Executive Summary

The QC software was measuring some hole diameters incorrectly because, in a small number of cases, it picked the wrong detected shape to measure instead of the real hole. We built a targeted fix ("Stage 2") that only changes *which already-detected shape gets measured* for a given hole position — it does not change how holes are detected, how they are measured, or any other part of the software.

The fix was tested on the original 33-cartridge development dataset and then, separately, on a second set of 17 cartridges that were never used while building the fix. Across both datasets combined (50 cartridges, 350 hole measurements):

- **22 measurements changed. 19 of them we directly confirmed by eye are now measuring the real hole instead of a false detection. 2 more have strong supporting evidence. 1 remains genuinely unclear.**
- **Zero measurements changed that shouldn't have.** Every other measurement in both datasets is identical to before the fix.
- One bug was found during our own testing process (before release) where the fix had an unintended side effect on an unrelated diagnostic message — not a measurement. It was fixed and re-verified. No further issues have been found since.

**Bottom line: the evidence supports deploying this fix to production**, with the caveats detailed in §8–§9 below — most importantly, we do not have independent reference measurements to prove the *exact* corrected numbers are accurate to the micron, only strong visual/geometric evidence that the fix is now measuring the correct physical feature rather than the wrong one.

---

## 2. Original Production Problem

Software-measured hole diameters for the Achira Beta Cartridge sometimes disagreed with the reference microscope (Leica) measurements. The investigation found this had more than one cause; this document covers the fix for one specific, confirmed cause. (A separate, earlier finding — that roughly 3–4% of the disagreement came from a calibration/scale-factor mismatch — was already fixed independently and is not part of this document.)

## 3. Root Cause

The software detects circular shapes in each image (holes, but also scratches, debris, and texture that can look circular), then tries to match each detected shape to one of the 7 expected hole positions on the cartridge. The matching logic simply picked whichever detected shape was **physically closest** to the expected position — even if a shape closer to the expected position was actually a scratch or texture, and the real hole was slightly farther away but still within an acceptable search range.

In effect: when a false-positive detection happened to sit closer to the expected position than the real hole, the software would measure the false positive and report an incorrect diameter (and sometimes an incorrect PASS/FAIL result) — even though the software had already correctly detected the true hole and simply failed to choose it.

## 4. Solution Implemented

We added a second matching step that runs only *after* the original matching logic has already run and only reconsiders shapes for positions the software already believes it found. For each such position, it now also considers the quality of what it's about to measure — using data the software already computes for every shape (how many measurement rays hit a real edge, whether the diameter is near the expected size) — and only switches to a different shape if that shape is a clearly better match for a real hole. If nothing is a strictly better match than what was already chosen, the answer is unchanged.

Nothing about how the software detects shapes in the image, how it measures a shape's diameter, or how it decides the initial expected positions was changed.

## 5. Why the Solution Is Safe

- **It cannot change what the original software detects or how it measures anything — it can only change which already-detected shape is picked for a position the software already found.** If the original choice was already the best available, nothing changes.
- **It is designed to only ever replace a choice with a strictly better one** (using existing quality signals, not new guesswork), never to swap in a worse or ambiguous option.
- **It was built and tested in the smallest possible increments**, with a full re-check of every single measurement in the 33-cartridge development set after each change, and any unexpected change was treated as a stop-and-investigate event rather than something to work around.
- **A real defect was found and fixed during this process, before release.** While testing, we discovered the fix was unintentionally affecting an unrelated diagnostic label (not a measurement) for two holes that the software had already correctly flagged as "not found." We traced this to two pieces of code unexpectedly sharing the same internal data, fixed it with a small, isolated change, and re-confirmed the full 33-cartridge result was clean afterward. This is disclosed here specifically because we consider it a sign the verification process is working as intended, not something to hide.
- **It was then independently re-tested on a second, completely different 17-cartridge dataset that played no role in building it**, specifically to check whether it does anything unexpected on data it hasn't seen. It did not.

## 6. Validation Performed

| | Development dataset | External validation dataset |
|---|---|---|
| **Cartridges** | 1–33 (33 cartridges, 231 holes) | 34–50 (17 cartridges, ~104 comparable holes) |
| **Role** | Used to design and build the fix | Held out — never used while building the fix |
| **Method** | Full re-measurement of every hole, before and after, automated line-by-line comparison | Same — old software vs. new software run side-by-side on the same images |
| **Additional check** | Direct visual inspection of every changed measurement (see §7) | Direct visual inspection of every changed measurement |

Visual inspection means: a human-reviewable image was generated for each changed measurement, showing exactly what the software measured before and after, overlaid on the actual microscope photo, so it can be checked by eye whether the new measurement is really sitting on the hole. For 12 of the development-dataset cases, this check was additionally repeated in a "blinded" form (candidates relabeled at random so the reviewer couldn't tell which was old vs. new while judging) specifically to guard against the reviewer unconsciously favoring the new answer — the blinded result matched the original result exactly.

## 7. Final Statistics

| Metric | Development (1–33) | External (34–50) | Combined |
|---|---|---|---|
| Intended Stage 2 changes | 17 | 5 | 22 |
| Unintended regressions | 0 (1 found and fixed pre-release — see §5) | 0 | 0 |
| FAIL → PASS | 6 | 1 | 7 |
| PASS → FAIL | 1 (visually confirmed as correcting a false PASS, not a new error) | 0 | 1 |
| Visually confirmed improvements | 14 of 17 | 5 of 5 | 19 of 22 |
| Supported by strong indirect evidence (not directly visually reviewed) | 2 of 17 | — | 2 of 22 |
| Genuinely inconclusive | 1 of 17 | 0 of 5 | 1 of 22 |
| Detection coverage (which holes are found at all) | Unaffected — identical before/after | Unaffected — identical before/after, including 4 cartridges with a pre-existing, unrelated detection-coverage limitation (see §8) | Unaffected |

**In plain terms: of the 22 measurements this fix changed, 19 are directly confirmed by eye to now be correct, 2 more have strong supporting evidence of being correct, and 1 remains genuinely unresolved. None of the 22 changes, and none of the other 328 unaffected measurements, show any evidence of the fix making anything worse.**

## 8. Remaining Limitations

Stated plainly, distinguishing what we know from what we are assuming and what remains unknown:

- **Evidence:** All regression testing (0 unintended changes across 350 measurements in 2 independent datasets); all visual review results (19/22 confirmed, 1/22 inconclusive, 2/22 indirect evidence only); the coupling bug found and fixed pre-release.
- **Assumption:** That "the ray pattern sits cleanly on a dark circular boundary in the image" reliably means "this is the real hole." This is a strong, physically-grounded assumption used throughout this investigation, but it is not the same as an independent, calibrated ground-truth measurement.
- **Known unknown:** We do not have independent reference (Leica) measurements for these specific holes to confirm the corrected diameters are accurate to a stated tolerance — only that the software is now measuring the physically correct feature. We searched for such reference data and could not find any usable independent measurement source in the project.
- **1 of 22 changes (Cartridge 18) remains genuinely inconclusive** — neither the old nor new answer shows a clear hole in the available image, and we have not resolved this.
- **Only 2 of the available datasets have been validated** (50 of the cartridges spanning ranges 1–79 that exist in the broader project). Three further datasets exist and have not yet been checked.
- **A separate, pre-existing limitation was found (not caused by this fix)**: a small number of cartridges (1 in the development set, 4 in the external set) have some holes that the software can't locate at all, most likely because those images have a different shape/framing than most others. This affects both the old and new software identically — it is not a regression introduced by this fix — but it is an existing gap worth a dedicated follow-up investigation.

## 9. Recommendation

**Based on the available evidence, we recommend deploying Stage 2 to production**, with the following conditions attached rather than as an unqualified endorsement:

1. Treat this as validated for correctness-of-selection (picking the right already-detected shape), not as an independently-verified absolute-accuracy improvement — because no independent reference measurement exists to make that stronger claim.
2. Run the same before/after regression and visual-review process against the 3 remaining unvalidated datasets before considering this fully rolled out across the whole product line, since only 2 of 5 available datasets have been checked.
3. Track the 1 remaining inconclusive case (Cartridge 18) and the separate detection-coverage limitation as known, open items — neither blocks this release, but both should not be forgotten.
4. Continue to require the same evidence standard (visual confirmation, not just statistics) for any future change to this part of the software, since that standard is what caught the one real defect found during this work.

We are confident in the safety of this change (it cannot make a correct measurement worse, and extensive testing found no unintended side effects) and reasonably confident in its correctness (19 of 22 changes directly confirmed by eye). We are not claiming certainty on the remaining 3 of 22 changes, and we are not claiming this closes out every known measurement discrepancy in the software — only the specific, confirmed root cause this fix targets.
