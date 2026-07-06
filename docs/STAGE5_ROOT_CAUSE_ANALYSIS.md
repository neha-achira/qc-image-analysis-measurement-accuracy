# Stage 5 — Root Cause Analysis (Production Readiness)

**Status:** Investigation complete. Four confirmed defects have since been implemented and validated, one at a time, each with its own commit and full regression — see §6.1. All remaining findings (Cartridge 72's broader pattern-matching breakdown, the two inconclusive cases, and the two borderline-measurement cases) remain unimplemented pending further investigation or external data, per the ranked list in §6.
**Branch:** `stage5-root-cause-analysis`
**Scope:** All cartridges outside the two previously-validated datasets (1–33, 34–50) — specifically `E:\51-60` (10 cartridges), `E:\61-70 (1)` (10 cartridges), `E:\71-79` (9 cartridges) = 29 cartridges, Holes image type.
**Companion documents:** `docs/STAGE5_PER_CARTRIDGE_REPORT.md` (full technical detail per failing case, candidate-by-candidate).

---

## 1. Method

Two evidence sources were used, cross-checked against each other:

1. **Existing production output.** Two of the three datasets already had real `qc_app.py` batch-run CSV reports on disk (`E:\51-60\qc_report_20260703_150448.csv`, `E:\71-79\qc_report_20260703_150903.csv`), generated before this investigation began. These were read directly as primary evidence of what the production application actually reported.
2. **Independent replay.** `detect_features.detect()` (the same function `qc_app.py` calls) was run directly against all 29 cartridges to get complete, consistent per-tag data (which the CSV summaries don't include) and to cover the one dataset (`61-70 (1)`) with no existing report.

For every failing tag, the exact same techniques used in Stages 2/3 were reused: replaying the unmodified Hough call to recover the full raw candidate list, extracting the ray-cast debug data (`fallback_mode`, `n_hit`, `near_nominal_count`) already computed by `_subpixel_diameter` for every candidate, and generating annotated overlay images (predicted position, selected candidate, ray-hit overlay, and — where relevant — every other raw candidate near the area). All of this is read-only against the current, unmodified codebase.

## 2. Cartridges With Confirmed Failures

| Cartridge | Dataset | Failing tags (tolerance) | Missing tags | Root failure |
|---|---|---|---|---|
| 51 | 51–60 | Tag4 | none | Diameter measurement (borderline) |
| 66 | 61–70 | Tag6, Tag9 | none | Diameter measurement (Tag6); Image quality / ranking (Tag9) |
| 70 | 61–70 | Tag5 | none | Candidate generation / image quality (inconclusive) |
| 72 | 71–79 | Tag7, Tag9 | Tag1, Tag3, Tag4, Tag5 | Pattern matching (geometric model breakdown) |
| 79 | 71–79 | — (not a `detect_features.py` failure) | — | Data quality + `qc_app.py` misclassification bug (see §5) |

25 of 29 cartridges show zero issues. Full per-tag data for all 29 is in `stage5_broad_sweep.csv` (scratchpad).

## 3. Failure Classification (per the 7 requested categories)

| Category | Count | Cases |
|---|---|---|
| Hole detection failure (Hough fails broadly across the image) | 0 | none observed — every cartridge produced a plausible candidate count (23–44) |
| Candidate generation failure (no candidate near a specific expected hole at all) | 2 | Cartridge 70/Tag5 (tentative — see §4.3); Cartridge 72/Tag4 |
| Candidate ranking failure (a better candidate existed but wasn't chosen) | 0 confirmed | Cartridge 66/Tag9 and 72/Tag7 were checked specifically — in both, the selected candidate was confirmed to already be the *best available* option; no better candidate was wrongly passed over |
| Pattern matching failure (anchor/`REF_OFFSETS` geometry doesn't fit the cartridge) | 5 | Cartridge 72 — Tag1, Tag3, Tag5 (correctly labeled outside-image, but symptomatic of the same geometry breakdown), Tag7, Tag9 |
| Diameter measurement failure (correct hole, correct candidate, wrong number) | 2 | Cartridge 51/Tag4, Cartridge 66/Tag6 |
| Calibration/scaling failure | 0 | none observed — no systematic multiplicative scale error found in any case |
| Image quality limitation (genuinely ambiguous/obscured feature) | 2 | Cartridge 66/Tag9 (channel groove crosses near the true hole); Cartridge 70/Tag5 (alternate explanation, see §4.3) |

**Note on double-counting:** Cartridge 66/Tag9 and Cartridge 70/Tag5 appear in two rows because the evidence did not cleanly resolve to a single category — this is stated explicitly rather than forcing an artificial single answer (see §4 for the specific evidence and why it remains ambiguous). Cartridge 72's 5 affected tags are counted individually in the table because each is independently checkable, but **§4.4 explains they very likely share one underlying root cause**, not five independent defects.

**Two additional defects were found that are outside `detect_features.py` entirely** (in `qc_app.py`, the batch-processing GUI) — see §5. These are not part of the 7-category table above since they are not detection/measurement algorithm defects, but they directly caused an observed production failure (Cartridge 79) and are included in the ranked fix list.

## 4. Evidence Summary (full detail in the per-cartridge report)

### 4.1 Cartridge 51/Tag4 and Cartridge 66/Tag6 — Diameter measurement, borderline

In both cases: the selected candidate is at the correct location (confirmed visually — the ray-hit ring sits precisely on the visible hole boundary, no other candidate is closer to the expected position, no candidate-selection ambiguity exists). The reported diameter is borderline outside tolerance (51/Tag4: 0.4475mm, dev −0.0525mm against ±0.05mm tolerance; 66/Tag6: 0.44mm, dev −0.06mm). **We cannot determine from the available evidence whether this is a true software measurement bias or a genuinely undersized physical hole**, because — as established in every prior stage of this investigation — no independent Leica reference measurement exists for these specific holes. This is stated as a limitation, not resolved by assumption.

### 4.2 Cartridge 66/Tag9 — Image quality / ranking, unresolved

The candidate exactly at the expected position (distance 0) has very poor ray-cast quality (9/36 hits). The selected candidate, 516px away, has somewhat better but still mediocre quality (20/36 hits) and was correctly chosen as the better of the two available options — this is not a ranking bug. Visual inspection shows the true hole location is very close to where a drainage/channel groove crosses the image, plausibly explaining the poor edge signal at that exact spot. Neither candidate is confirmed as clearly correct.

### 4.3 Cartridge 70/Tag5 — Candidate generation vs. image quality, inconclusive

The overview image shows what appears to be a large, high-contrast, clearly visible hole near the expected position that has **no Hough candidate anywhere near it** — the nearest raw candidate is 230px away (selected) and the next-nearest is 703px away (just outside the 600px matching tolerance). Ray-cast quality at the selected candidate is mixed (30/36 hits, but only 9/36 within the expected-radius window). This is consistent with either (a) Hough failing to generate a candidate at the true hole's location at all, or (b) a genuinely ambiguous/irregular edge at that specific hole. The evidence does not cleanly distinguish between these — flagged for a follow-up, more precise pixel-level check before committing to a fix approach.

### 4.4 Cartridge 72 — Pattern-matching geometry breakdown (primary finding)

This is the most significant finding in this investigation. Only 3 of 7 tags matched (Tag6, Tag7, Tag9). Checking systematically:
- **The anchor actually chosen is provably the best one available** — every one of the 24 raw Hough candidates was tried as a hypothetical anchor; none achieves a better match count than the 3/7 already found. This rules out a Stage 1 anchor-*selection* bug.
- **Tag1, Tag3, Tag5's true predicted positions (recomputed from the correct anchor) are genuinely outside the image** — correctly labeled.
- **Tag4's true predicted position (569, 2304) is inside the image**, but the nearest raw Hough candidate is 931px away — far beyond the 600px matching tolerance. Hough did not generate any candidate near this real, expected hole location.
- **The image itself visibly shows at least one more real, unmatched hole** (top-left region of the overview) that Hough *did* detect as a raw candidate (644, 416) — but it sits nowhere near where the current anchor's geometry predicts any tag should be.

Taken together, this strongly suggests the fixed-pixel `REF_OFFSETS` table — calibrated against cartridge 1's geometry — does not correctly describe Cartridge 72's actual hole layout, most plausibly because this cartridge was imaged at a slightly different scale, rotation, or stage offset than assumed. **This is one root cause manifesting as five symptoms (Tag1, 3, 4, 5, 7, 9 all affected), not five independent defects.**

**Update:** Tag4 was also mislabeled `outside_image` when it should have read `not_detected` — a separate, now-fixed diagnostic bug (§6.1, Fix 3). That fix only corrects the *label*; Tag4 is still not detected, and the underlying pattern-matching breakdown described above is unchanged and still unimplemented.

## 5. Findings Outside `detect_features.py`

Investigating Cartridge 79 (flagged FAIL in the production CSV with an anomalous detail string) led to two distinct, confirmed defects in `qc_app.py`, unrelated to the detection algorithm:

1. **Every image in every batch run is processed twice.** `qc_app.py`'s file-collection code globs both `*.png` and `*.PNG` and concatenates the results (`list(sf.glob("*.png")) + list(sf.glob("*.PNG"))`). On Windows' case-insensitive filesystem, both patterns match the same files, so every image is detected and measured twice per run. This is confirmed by every normal cartridge's report showing its result duplicated (e.g., "holes 7/7   holes 7/7"). It does not corrupt results when both runs agree (which they always do, since detection is deterministic), but it wastes roughly double the processing time on every batch run.
2. **A misnamed file caused a wrong result to silently overwrite a correct one.** Cartridge 79's folder contains `Nrck_ch00.png` (a typo for `Neck_ch00.png`). `detect_image_type()` fails to match "nrck" against its neck keyword list and **silently defaults to "holes"** for any unrecognized filename. This misnamed Neck-channel image was therefore run through hole detection, producing a garbage result (1/7 tags found). Because `qc_app.py` processes files in alphabetical order and simply overwrites `row["holes"]` each time a "holes"-type image is processed, and "Nrck_ch00.png" sorts after "Holes_ch00.png" alphabetically, **the garbage result overwrote the correct one**, causing the cartridge to report FAIL despite the real Holes image passing 7/7. This is confirmed exactly by the raw CSV: `"holes 7/7   holes 7/7   holes 1/7   holes 1/7"` — the real image's result (7/7, doubled by defect #1) followed by the misnamed file's result (1/7, also doubled).

This is a genuine, confirmed production failure mode, and it did not require any change to `detect_features.py` — it is entirely a `qc_app.py` batch-runner and file-naming-robustness issue.

## 6. Ranked List of Fixes (highest impact first)

1. ~~Fix the silent "assume holes" fallback in `detect_image_type()`.~~ **Implemented and validated** — see §6.1 (Fix 2A).
2. **Investigate and address the Cartridge 72-style pattern-matching breakdown.** Affects the most tags (5 of 7) in the worst-affected cartridge found, and is a category (not just a single tag) — worth understanding whether this is an isolated cartridge (imaging error) or represents a systematic geometry-drift risk across the wider dataset before deciding on a fix (e.g., a more tolerant/adaptive geometric model vs. flagging such cartridges for manual review). **Not yet implemented.**
3. ~~Fix the double-processing bug in `qc_app.py`'s file globbing.~~ **Implemented and validated** — see §6.1 (Fix 1).
4. **Investigate Cartridge 70/Tag5 and Cartridge 66/Tag9 further** (candidate generation vs. image quality) before proposing a fix — the evidence is currently inconclusive between "Hough missed a real hole" and "the hole is genuinely ambiguous in the image," and these point to different remedies (widening Hough's search vs. accepting the limitation). **Not yet implemented.**
5. **Decide how to handle the two borderline diameter-measurement cases** (51/Tag4, 66/Tag6) — lowest priority for a code fix, since we cannot currently distinguish a software measurement bias from genuine part variance without independent reference data. Recommend obtaining Leica reference measurements for these two specific holes before treating this as a software defect. **Not yet implemented — blocked on external data.**

An additional confirmed defect, found via a dedicated blast-radius analysis after this report was first written, has also been implemented — see §6.1 (Fix 3).

### 6.1 Implementation Log

All four fixes below were implemented one at a time, each as its own commit, each verified with `py_compile` + import + full regression on all validated datasets (1–33, 34–50, 51–79) before being committed. No unexpected regressions occurred in any of the four.

| # | Fix | File(s) | Commit | Validation result |
|---|---|---|---|---|
| 1 | Deduplicate batch-runner file collection (case-insensitive `*.png`/`*.PNG` glob duplication) | `qc_app.py` | `38e29aa` | 0 unexpected diffs across all 3 dataset groups; direct check confirmed each file now collected exactly once |
| 2A | `detect_image_type()` returns `"unknown"` instead of silently defaulting to `"holes"` | `preprocess.py` | `158fe88` | 0 unexpected diffs; confirmed all correctly-named files unaffected, unrecognized names now correctly return `"unknown"` |
| 2B | Fixed a non-ASCII `print()` crash in `detect()`'s previously-unreachable "unrecognized type" branch, exposed by Fix 2A | `detect_features.py` (text only, no logic) | `c0be2d6` | 0 unexpected diffs; confirmed the misnamed-file case now returns a clean placeholder result instead of crashing |
| 3 | Missing-hole `outside_image`/`not_detected` diagnostic now uses the true anchor (`best_anchor_cxy`) instead of approximating it from the lowest-numbered matched tag's raw position | `detect_features.py` | `4aa1779` | Blast-radius analysis first (12 predicted changes across 6 cartridges) confirmed exactly by full before/after regression: **12/12 diagnostic-label changes, all `outside_image → not_detected`, 0 measurement diffs, 0 PASS/FAIL diffs, 0 other diffs**, across all 79 cartridges checked |

Fix 3's blast radius, once measured, was larger than the single Cartridge 72/Tag4 case originally found — it also corrected previously-mislabeled diagnostics in Cartridges 18, 33, 45, 48, and 50. In every one of the 12 cases, only the diagnostic `reason` label changed; no measurement, PASS/FAIL, or matched-tag result was ever affected, consistent with the structural guarantee established before implementation (the missing-hole block never writes to `best_matched`/`detected`).

**Not yet implemented:** the Cartridge 72 pattern-matching breakdown (item 2 above), the two inconclusive cases (Cartridge 66/Tag9, Cartridge 70/Tag5), and the two borderline diameter-measurement cases (Cartridge 51/Tag4, Cartridge 66/Tag6) — each requires further investigation or external data before a fix can even be scoped, per the per-cartridge report.
