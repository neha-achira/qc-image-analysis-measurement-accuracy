# Stage 20 — Production Confidence Score Implementation

**Status:** Implementation complete and validated. Committed after validation succeeded, per your instruction.
**Branch:** `stage20-confidence-score-implementation`
**Objective:** implement the confidence score designed in Stage 19 into production, as a strictly additive, informational annotation that never influences detection, assignment, recovery, measurement, or PASS/FAIL.

---

## 1. A Disclosed Environment Constraint (carried over from Stage 19)

The real 79-cartridge validation dataset is still not present in this environment — the same finding already established in Stage 19 (confirmed there via `Test-Path` against the exact canonical dataset paths; re-confirmed once, briefly, before this stage's validation work, without a further filesystem search, per your instruction). **This means a live replay of the actual 79-cartridge dataset through the modified pipeline could not be performed.** Section 4 describes the two substitute validation methods actually used, and is explicit about what they do and do not prove relative to a live dataset replay.

---

## 2. Implementation Details

### 2.1 New module: `confidence.py`

A new, standalone file at the repository root. It has no dependency on `detect_features.py` and performs no image processing — it is a pure function of five inputs (`n_hit`, `n_rays`, `near_nominal_ratio`, `angular_gap_deg`, `fallback_mode`, `dist_from_predicted_px`) to `(confidence_pct, confidence_category)`, implementing exactly the formula designed and justified in `docs/STAGE19_DETECTION_CONFIDENCE_INVESTIGATION.md` §4:

```
angular_uniformity     = 1 − min(angular_gap, 180°) / 180°
ray_quality            = mean(near_nominal_ratio, n_hit/n_rays, angular_uniformity)
geometric_consistency  = 1 − min(dist_from_predicted, 690px) / 690px
raw_score              = 0.70 × ray_quality + 0.30 × geometric_consistency
fallback_gate          = 1.0 (normal) | 0.5 (off_nominal_fallback) | 0.0 (total_failure)
confidence (%)         = 100 × raw_score × fallback_gate, clamped to [0, 100]
category               = High (≥90) | Medium (≥70) | Low (≥40) | Very Low (<40)
```

Every constant carries the same disclosure as Stage 19: `RECOVERY_TOL_PX=690` is the production pipeline's own existing constant (reused, not new); the 70/30 split, the 180° cap, the category breakpoints, and the untested 0.5 `off_nominal_fallback` gate are explicitly labeled in the module's own comments as heuristics, matching Stage 19's disclosure exactly rather than presenting them as derived constants.

### 2.2 Integration into `detect_features.py` — strictly additive

Two small, additive changes inside `detect_holes()`, both after the point where matching (Stage 1, Stage 2, and the recovery pass) is already final:

1. **`_expected_positions` is now computed unconditionally** rather than only when a caller requests debug diagnostics. This is pure arithmetic re-using the already-selected anchor (`_predict_positions(*best_anchor_cxy)`, the exact same call already made elsewhere in the function) — no new image processing, no change to any existing value, and no change to what `debug_context["per_hole"]` records (that block's own condition and content are untouched).
2. **In the final "build result list" loop**, for each already-matched tag, the module looks up that exact candidate's own ray-cast diagnostics (`_ray_debug_by_id`, already populated earlier in the same function call for every candidate, independent of whether debug output was requested), computes `dist_from_predicted` against the already-computed prediction, calls `compute_confidence(...)`, and adds two new keys — `confidence_pct` and `confidence_category` — to the dict already being built for that hole. No existing key is read, removed, or overwritten.

**Detection, candidate generation, Stage 1 anchor selection, Stage 2 substitution, the recovery pass, `_subpixel_diameter`'s measurement, and the PASS/FAIL tolerance check are not modified in any way** — every one of those computations completes, unchanged, before the confidence block runs, and the confidence block never writes back into any variable they use.

### 2.3 CSV / report output

`results_to_rows()` (holes branch) now adds two dictionary keys, `"Confidence (%)"` and `"Confidence Category"`, populated from the new fields on each circle. `export_csv()`'s `fieldnames` list gains these two column headers, appended at the end. No existing column, existing key, or existing row's existing values were changed. Rows without a confidence value (missing-hole rows, and the `dab`/`mixing`/`neck` branches, which are unrelated to this stage) are written with a blank value in the two new columns automatically (`csv.DictWriter`'s default `restval=""` behavior — confirmed directly rather than assumed, §4.3) rather than requiring every other row-building branch to be touched.

Both existing CSV entry points — the GUI's per-cartridge detail CSV and the CLI's `run_batch()` — call this same `results_to_rows()`/`export_csv()` pair, so the new columns appear in both without any separate change to either caller.

### 2.4 GUI integration (`qc_app.py`)

One small, additive block was added immediately after the existing per-image summary log line, active only for `img_type == "holes"`: it iterates the already-detected `circles` and logs one line per hole in the format you specified:

```
Tag4: Diameter 0.510 mm  PASS  Confidence: 54% (Low)
```

This uses the existing `log()` mechanism already used by every other line in this function — it does not modify the existing summary line, the `row` dict, the results Treeview, the CSV export path, or any other part of the GUI. "The UI should remain otherwise unchanged" is satisfied by construction: nothing else in `qc_app.py` was touched.

---

## 3. Verification That Confidence Cannot Affect Existing Behavior

This is true by construction, not merely by testing, for two independent reasons:

1. **Data-flow order.** `compute_confidence()` is called only after `best_matched` (the final tag→candidate assignment, following Stage 1, Stage 2, and the recovery pass) is already fixed, and only reads pre-existing diagnostic dictionaries (`_ray_debug_by_id`, `_expected_positions`) that no other part of the function reads back from. There is no path by which its output can reach any decision made earlier in the same function call.
2. **No shared mutable state.** `confidence.py` is stateless and takes only its five documented scalar arguments; it holds no reference to, and cannot mutate, any candidate, matching, or measurement structure.

Section 4 confirms this holds in practice as well as by inspection.

---

## 4. Validation

### 4.1 Static checks

```
python -m py_compile confidence.py detect_features.py qc_app.py   → clean
python -c "import confidence; import detect_features"             → clean
python -c "import qc_app"                                          → clean
```

### 4.2 Synthetic end-to-end regression (substitute for the unavailable live dataset)

Because the real dataset cannot be replayed in this environment (§1), the strongest available substitute was used: a clean, high-contrast 7-hole test image was synthesized at the exact `REF_OFFSETS` geometry (bright interior, dark ring, mild pixel noise), and run through **both** the pre-Stage-20 baseline `detect_holes()` (loaded directly from `git show HEAD:detect_features.py` as an isolated module — the identical technique used for every regression in this project since Stage 5) **and** the post-Stage-20 working-tree `detect_holes()`, on the exact same synthetic input.

**Every field the baseline already produced was compared for exact equality:**

| Check | Result |
|---|---|
| `n_detected`, `n_expected`, `n_outside_image`, `n_not_detected`, `all_found`, `overall_pass` | Identical (baseline: 7/7 matched, `overall_pass=False`; new: 7/7 matched, `overall_pass=False` — identical for the same reason in both, an artifact of the synthetic image's geometry, not a regression) |
| Matched tag set | Identical: `[1, 3, 4, 5, 6, 7, 9]` in both |
| Per-hole `cx_px, cy_px, radius_px, radius_hough_px, diameter_px, diameter_mm, deviation_mm, pass, dwg_tag, cx_hough, cy_hough` | **Identical for every one of the 7 tags — zero differences** |
| `missing_holes` | Identical (empty in both) |

**New-fields-only check:** every one of the 7 tags in the new version carries `confidence_pct` (a float in [0, 100]) and `confidence_category` (one of `High/Medium/Low/Very Low`), both well-formed. The synthetic image's specific circle geometry (a filled dark disk with a bright inner core, rather than a photographically realistic ring) happens to place several rays' threshold crossings just below the `near_nominal_ratio` window, so the resulting scores land at "Medium" rather than "High" — this is an artifact of the synthetic test image's geometry, not a defect in the confidence calculation, and is disclosed rather than tuned away: the purpose of this test is to confirm **zero regression in existing fields and well-formed new fields**, not to validate specific confidence values (§4.3 does that against real data).

### 4.3 Cross-check against the real, previously-validated 541-tag population

To validate the *numeric correctness* of the implementation (not just its structural safety), `confidence.py`'s `compute_confidence()` was run against the real `near_nominal_ratio`, `n_hit`, `angular_gap`, `fallback_mode`, and `dist_from_predicted` values already gathered from all 79 real cartridges in Stage 14, and compared against an independent re-implementation of the Stage 19 formula:

```
Total tags checked: 541
Mismatches between confidence.py and the Stage 19 formula: 0
```

**The production module reproduces the Stage 19 design exactly, with zero divergence, across every real matched tag in the validated dataset.** This is the strongest available confirmation that the implementation is numerically faithful to the documented design, using real (not synthetic) production metrics, even though it does not exercise the live end-to-end code path the way §4.2 does.

### 4.4 CSV output check

`results_to_rows()` and `export_csv()` were run on a fresh `detect_holes()` result from the synthetic image. The produced header row ends with `...,claude_confidence,claude_notes,Confidence (%),Confidence Category` (every pre-existing column present, unchanged, in its original order) and the corresponding data row carries correct existing values (e.g., `measured_mm=0.35204, deviation_mm=-0.14796, pass_fail=FAIL, cx_px=908, cy_px=1532`) alongside the new `83.1, Medium` — confirming the new columns are appended without disturbing any existing column.

*(An unrelated, pre-existing console-encoding issue was observed when `export_csv`'s own status message — which contains a Unicode arrow character, `git blame`-attributable to code that predates this stage — is printed to a `cp1252` Windows console via a bare `python -c` invocation; the CSV file itself is written successfully before that print statement runs. This is not part of this stage's change and was not modified, consistent with the instruction not to touch anything beyond the confidence addition.)*

---

## 5. Regression Summary

| Check | Outcome |
|---|---|
| Existing measurements (`diameter_mm`, `deviation_mm`, `diameter_px`, `radius_px`) | Unchanged (§4.2: identical across all 7 synthetic tags) |
| Existing PASS/FAIL (`pass`, `overall_pass`) | Unchanged (§4.2: identical) |
| Existing detection/assignment (`n_detected`, matched tag set, `missing_holes`) | Unchanged (§4.2: identical) |
| New confidence fields present and valid | Confirmed (§4.2: all 7 tags, valid range and category) |
| New confidence fields numerically correct against the Stage 19 design | Confirmed (§4.3: 0/541 mismatches on real data) |
| CSV output | New columns appended correctly, existing columns unaffected (§4.4) |
| Compile / import | Clean (§4.1) |

**What this validation does not cover:** a live replay of the actual 79-cartridge image set through the full pipeline, because that dataset is not present in this environment (§1). If and when the dataset becomes available again, a live full-dataset regression (the same methodology used in every prior stage's production change) should still be run before this is treated as fully validated in an environment where the real images are accessible — this is disclosed as an open item, not silently assumed to be equivalent to what was actually tested here.

---

## 6. Files Changed

| File | Change |
|---|---|
| `confidence.py` | New file — the confidence-scoring module |
| `detect_features.py` | Additive: one import, one conditional widened to unconditional (arithmetic only, no behavior change), one new block inside the existing per-hole result-building loop, two new dict keys in `results_to_rows()`, two new fieldnames in `export_csv()` |
| `qc_app.py` | Additive: one new logging block, active only for `img_type=="holes"`, after the existing summary log line |

No other file was modified. No existing line of detection, assignment, recovery, measurement, or PASS/FAIL logic was changed.
