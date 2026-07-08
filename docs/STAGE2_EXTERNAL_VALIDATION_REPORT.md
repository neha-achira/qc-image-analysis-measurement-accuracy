# Stage 2 External Validation — Unseen Dataset (E:\34-50)

**Status:** Complete. Validation only — no production code modified.
**Branch:** `stage2-external-validation` (validation scripts and reports only; `detect_features.py` untouched).
**Compared:** `verified-production-baseline` (`8a6253d`) vs. `stage2-complete` (`0c032b8`), both loaded as separate Python modules from their respective git states — the baseline via `git show verified-production-baseline:detect_features.py`, Stage 2 from the current working tree. Neither file was modified to perform this comparison.
**Dataset:** `E:\34-50\WB(2)`, 17 cartridges (34–50), Holes image type only. **Never used** during Stage 1, 2, or 3 investigation, design, or the 33-cartridge regression baseline (`E:\1-33\Washed baseplates`) — a genuinely unseen dataset.

---

## Method

For each of the 17 cartridges, `Holes_ch00.png` was run through both versions' `detect()`, and every matched tag's `diameter_mm`, `pass`, and Hough position (`cx_hough`, `cy_hough`) was compared. 104 total tag-rows were produced (the union of tags matched by either version, across all 17 cartridges — not all cartridges matched all 7 tags; see below).

## Finding 1: Pattern-matching (which tags match) is identical between versions

For every cartridge, the number and identity of matched tags was **exactly the same** for baseline and Stage 2 (confirmed from the detection logs — each cartridge shows the identical "Pattern match: X/7" line twice, once per version). This is expected and confirms Stage 2's core architectural guarantee holds on new data: Stage 2 only ever replaces which candidate fills an already-matched tag — it never changes whether a tag is matched at all.

**4 of the 17 cartridges show degraded pattern-matching**, identically in both versions:
| Cartridge | Tags matched | Missing |
|---|---|---|
| 45 | 4/7 | 5, 6, 7 |
| 48 | 4/7 | 1, 3, 5 |
| 49 | 1/7 | 1, 3, 4, 5, 6, 7 |
| 50 | 4/7 | 3, 5, 7 |

Since this is identical for both versions, **it is not a Stage 2 regression** — it is a pre-existing pattern-matching/geometry limitation, most likely because this dataset's images are a markedly different shape (~12,380×4,926, wide-and-short) than the training dataset's (~7,176×6,100, near-square), causing the fixed-pixel `REF_OFFSETS` table to push several tags' predicted positions outside the image bounds. This is analogous to the Cartridge 18 finding from the close-out report and is flagged here for visibility only — out of scope for Stage 2 validation, a candidate for separate future investigation (see recommendation below).

## Finding 2: Stage 2 changed exactly 5 tag assignments, all in Cartridge 39

Across all 104 comparable tag-rows, only **5 differ** between baseline and Stage 2 — all in **Cartridge 39** (Tags 1, 3, 4, 6, 9):

| Tag | Baseline (mm, pass) | Baseline position | Stage 2 (mm, pass) | Stage 2 position | Baseline ray quality | Stage 2 ray quality |
|---|---|---|---|---|---|---|
| 1 | 0.495 (PASS) | (468, 1028) | 0.5175 (PASS) | (592, 520) | n_hit=9/36, near=5 | n_hit=36/36, near=36 |
| 3 | 0.4525 (PASS) | (1136, 3636) | 0.5425 (PASS) | (1028, 3188) | n_hit=30/36, near=16 | n_hit=36/36, near=36 |
| 4 | 0.47 (PASS) | (2536, 1260) | 0.52 (PASS) | (2412, 872) | n_hit=18/36, near=11 | n_hit=36/36, near=36 |
| 6 | 0.415 (**FAIL**) | (3580, 2264) | 0.525 (**PASS**) | (3388, 1880) | n_hit=30/36, near=10 | n_hit=36/36, near=36 |
| 9 | 0.46 (PASS) | (6764, 2348) | 0.52 (PASS) | (6680, 1932) | n_hit=19/36, near=9 | n_hit=36/36, near=36 |

All 5 are `normal → normal` swaps — the exact category Stage 2's ranking (fallback tier → n_hit → near_nominal_count → distance) was designed to resolve, and the same category that made up 12 of the original 17 Stage 2 changes on the training dataset.

## Finding 3: Visual review — 5/5 confirmed correct

Comparison images (predicted position, baseline candidate + ray overlay, Stage 2 candidate + ray overlay, on real image content — same methodology as the original Stage 2 investigation) were generated and inspected for all 5 cases (`validation_output/stage2_external_validation/cart39_tag{1,3,4,6,9}_compare.png`).

**Result: 5 of 5 (100%) show the Stage 2 candidate sitting on a genuine, clean through-hole** — a continuous 36/36 ray-hit ring on a real dark circular boundary, directly visible in every image — **while the baseline candidate sits on plain PMMA texture or a scratch**, with scattered, incoherent ray hits and no hole boundary anywhere nearby. There are no inconclusive or ambiguous cases in this set — every one is unambiguous on direct visual inspection.

The Tag 6 case is particularly notable: baseline's FAIL (0.415mm) was a **false failure** — it was measuring an unrelated textured region, not the true hole, which Stage 2 correctly identifies and measures as 0.525mm, PASS.

## Conclusion: Stage 2 generalizes

On a completely unseen 17-cartridge dataset, Stage 2:
- Never altered which holes were detected/matched (identical to baseline in every cartridge, including the 4 cartridges with pre-existing pattern-matching limitations).
- Changed exactly 5 tag assignments, all clustered in a single cartridge, all in the well-understood `normal → normal` category.
- Was visually confirmed correct in 100% of the cases it changed (5/5), with zero inconclusive or questionable results — a stronger result than the training-dataset validation, where 1 of 17 (Cartridge 18/Tag4) was inconclusive.
- Introduced no unexpected side effects (no coupling-bug-style cross-contamination observed; the same "compare identical between versions" check that caught the original coupling bug shows no discrepancy here).

**Recommendation:** Stage 2 is validated as generalizing correctly to unseen data and requires no further changes. The pre-existing pattern-matching limitation on wide/short-aspect-ratio images (Cartridges 45, 48, 49, 50) is a separate, out-of-scope finding — recommended as a candidate for a future investigation alongside the previously-identified Cartridge 18 and Cartridge 9/Mixing findings, since all three appear to share a common root category (pattern-matching/geometry robustness across varying image dimensions) distinct from candidate-selection or Hough-detection work already completed.

---

## Artifacts
- Raw comparison data: `stage2_external_validation_raw.csv` (scratchpad, 104 rows)
- Visual comparisons: `validation_output/stage2_external_validation/cart39_tag{1,3,4,6,9}_compare.png`
- This report: `docs/STAGE2_EXTERNAL_VALIDATION_REPORT.md`

No production code was modified to produce this validation.
