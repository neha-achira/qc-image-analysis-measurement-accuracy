# Stage 2 Candidate Selection — Investigation & Implementation Report

**Status:** Implemented on branch `stage2-candidate-selection`, commit `ba61359`. Not yet merged to `master`.
**Baseline:** `master` @ `8a6253d`, tagged `verified-production-baseline`.
**Scope:** `detect_holes()` in `detect_features.py`, Holes image type only. Dataset: `E:\1-33\Washed baseplates` (33 cartridges).

---

## 1. Problem Statement

The Achira Beta Cartridge QC software's hole-diameter measurements were found to differ from Leica reference values for a subset of holes across the 33-cartridge validation dataset. The investigation's goal was to determine, with direct evidence rather than statistical inference, exactly which pipeline stage caused each divergence, and to fix only the confirmed root causes without disturbing any other stage.

The hole-detection pipeline is:

```
crop-to-active-area → 4x downsample → CLAHE → Gaussian blur → cv2.HoughCircles
  → per-candidate _subpixel_diameter (36-ray radial cast)
  → pattern-matching (_predict_positions / _score_anchor / anchor competition)
  → _refine_center (cosmetic)
  → final circle list
```

Seven holes per cartridge (`dwg_tag` 1, 3, 4, 5, 6, 7, 9) are expected; positions are predicted from a single "anchor" candidate via a fixed pixel-offset table (`REF_OFFSETS`) and matched against Hough-detected candidates within `MATCH_TOL_PX = 600px`.

---

## 2. Root Cause Investigation

Investigation proceeded in strict, evidence-gated phases — no code was changed until a mechanism was independently confirmed, and no fix was implemented until its design was reviewed and approved.

1. **Calibration audit.** Leica LAS AF acquisition metadata (`MetaData/*.xml`) was parsed and cross-checked against `calibration.json`. Divergences of up to ±3.7% were found between the two calibration sources (see `leica_calibration.py`, `resolve_scale_factor()`). This explains part of the Leica-vs-Achira gap but not all of it — calibration alone could not account for the largest divergences.
2. **Debug instrumentation.** A non-invasive `debug_context` out-parameter pattern was added to production functions (`_subpixel_diameter`, `detect_holes`, `_refine_center`, `detect_dab`, `detect_mixing`): when a caller passes a dict, it is populated in place with already-computed internal values (ray hits, near-nominal radii, fallback mode, refinement candidates, timing). The return value and type of every instrumented function is unchanged regardless of whether `debug_context` is passed — confirmed via full-dataset regression before and after instrumentation (0 diffs).
3. **`validation_framework.py`.** A read-only orchestration layer was built on top of the instrumented functions to produce per-cartridge overlays and CSV/JSON/Markdown summaries (`validation_output/<cartridge_id>/`), without touching any detection or measurement logic.
4. **Systematic failure taxonomy.** Every hole-diameter deviation across the 33-cartridge dataset was classified into one of: Calibration, Hough detection, Candidate selection, `_subpixel_diameter` (ray casting), Pattern matching, Other.
5. **`_refine_center()` eliminated as a cause.** A controlled, fully-reverted experiment bypassed `_refine_center()` in a temporary investigation build and re-ran the full 33-cartridge regression twice (with/without refinement). Result: **zero effect** on any measured diameter, PASS/FAIL, ray-hit count, or near-nominal count for all 231 holes. This reversed an earlier (explicitly retracted) misclassification that had attributed 5 failures to center refinement; those 5 were reclassified using their true pre-refinement (raw Hough-position) data, which moved 2 of them into the Candidate Selection category.

---

## 3. Evidence Collected

- **Calibration divergence:** up to +3.7%/−2.8% between `calibration.json` and Leica-metadata-derived pixel scale, logged automatically by `leica_calibration.py` whenever the two sources diverge by more than 1%.
- **`_refine_center()` is a pure no-op** with respect to any measured or decided value in the current codebase (see §2.5).
- **Geometric proof of no cross-tag contention:** the minimum pairwise distance between any two tags' predicted positions (derived from `REF_OFFSETS`) is 1393.9px (Tag6–Tag7), which exceeds `2 × MATCH_TOL_PX = 1200px`. This proves, by construction, that no single Hough candidate can ever fall within tolerance of two different tags' predicted positions simultaneously — eliminating an entire category of possible design defects (candidate contention between tags) without needing to test for it.
- **`near_nominal_count` alone is an insufficient ranking signal.** False-positive candidates under the `total_failure` fallback mode can report `deviation_mm=0.0, pass=True` — a deceptively "clean" result that does not reflect a real hole. A single-metric ranking was rejected for this reason (see §7).

---

## 4. Candidate Replay Analysis

To avoid depending on the live code while it was in a known-broken experimental state (see §6), a series of read-only "replay" scripts reproduced the *exact, unmodified* algorithm — the same Hough call parameters, the same `_subpixel_diameter()` (confirmed unaffected by any experiment), and the true original anchor-selection logic — independently in scratch analysis scripts, never modifying `detect_features.py` itself during analysis.

This replay technique revealed that **two failures already classified as "confirmed"** (Cartridge 2/Tag4, Cartridge 31/Tag1) were in fact **candidate-selection failures**: Hough *did* detect a candidate sitting on the true hole, within `MATCH_TOL_PX` of the predicted position, but the original `_score_anchor()`'s nearest-distance-only matching discarded it in favor of a closer false-positive candidate (e.g., a scratch or texture blob nearer to the predicted pixel position than the true hole).

A subsequent **quantitative risk assessment**, re-implemented independently and read-only (`stage2_risk_assessment_v2.py`) to avoid relying on the then-broken live `_score_anchor`, found the true blast radius of a candidate-selection fix was **17 tag assignments across 5 cartridges** (2, 6, 15, 18, 31) — not just the 2 originally confirmed cases. Of these, 5 were `total_failure → normal` fallback-tier corrections (the same mechanism as the 2 originally-confirmed cases) and 12 were `normal → normal` swaps, i.e., cases where the production candidate already looked superficially valid but a different in-tolerance candidate scored better under the proposed ranking.

---

## 5. Visual Review Methodology

The 12 "normal → normal" swaps were the most concerning finding, since a `normal`-fallback production candidate is not an obvious false positive — a purely statistical argument for replacing it risked over-correction. Per explicit instruction, **no conclusion was drawn from ray statistics alone**; each of the 12 cases was visually inspected instead.

For each case, a comparison image was generated (`generate_visual_comparisons.py`, read-only, using only the existing unmodified `_subpixel_diameter()`) showing, on the real image crop:
- the predicted position (magenta tilted-cross marker),
- the current/production candidate (green circle, yellow ray-hit dots),
- the alternate/Stage-2-proposed candidate (orange circle, cyan ray-hit dots).

Each image was inspected for observable evidence only: does the candidate's ray-hit ring sit on a genuine dark circular boundary (a through-hole), or on plain PMMA texture / a scratch / an unrelated feature?

**Result: 11 of 12 cases showed the alternate/Stage-2 candidate clearly sitting on a genuine through-hole** (a clean, continuous ring of ray hits at a real dark boundary), while the production candidate sat on unrelated texture or a scratch (scattered, incoherent ray hits, no boundary). **1 case (Cartridge 18/Tag4) was inconclusive** — neither candidate showed any hole-like boundary in the crop; both sat on the same ambiguous scratch/ridge region.

---

## 6. Blinded Review Methodology

Because the same reviewer (the AI performing the investigation) already knew which candidate was "proposed" when conducting the review in §5, a second, blinded pass was performed to rule out confirmation bias.

`generate_blinded_comparisons.py` regenerated the same 12 crops with:
- both candidates drawn in the *same* neutral color/style (no green="good"/orange="alternate" coding),
- neutral labels **"A"/"B"** instead of "CURRENT"/"ALTERNATE", assigned via a fixed, disclosed random seed (`random.seed(20260703)`) — not chosen by the reviewer,
- no printed statistics and no "PREDICTED" marker (which would have hinted at the nearest-distance/production pick),
- the current↔A/B and proposed↔A/B mapping sealed in a separate file (`mapping_SEALED.json`) not consulted until after the visual judgment was recorded for all 12 cases.

**Caveat (documented at the time):** true psychological blinding is not fully achievable for an AI reviewer that retains memory of the prior unblinded pass. The value of the exercise is that the mapping was concealed at judgment time, using genuinely randomized, non-suggestive labels — a meaningful anti-confirmation-bias check even without perfect blinding.

**Result:** identical to the non-blinded pass — 11/12 agree with the proposed Stage 2 assignment, 1/12 inconclusive (Cartridge 18/Tag4), 0/12 agree with production. The blinded re-check did not overturn or weaken the original finding.

---

## 7. Stage 2 Algorithm Design Evolution

### 7.1 First attempt (rejected): single-stage modification of `_score_anchor()`

The first implementation attempt modified `_score_anchor()` directly, adding a radius-deviation cost term:

```python
cost = dist + r_dev * 3   # r_dev = abs(candidate_radius - NOMINAL_R_PX)
```

**Rejected.** Because `_score_anchor()`'s match count feeds directly into the outer anchor-selection competition (`for anchor in detected: matched = _score_anchor(...); if len(matched) > best_score: ...`), any change to its matching logic can change *which candidate is chosen as anchor* — not just which candidate fills a given tag. Regression testing showed this caused a cascading, unintended 18-hole change across 5 cartridges, far outside the 2 originally-targeted holes. Per standing instruction, the regression was not tuned — the design was stopped and rebuilt.

*(Note: this abandoned cost-based version was left in the file, shadowed underneath a later rewrite, and was initially mistaken for "the verified production baseline" during the later revert — see §11.)*

### 7.2 Second attempt (rejected): near-nominal-count comparison inside `_score_anchor()`

A second rewrite of `_score_anchor()` compared candidates by `near_nominal_count` (falling back to nearest-distance on ties), still inside the anchor-selection competition itself:

```python
near = len(_ray_debug_by_id.get(id(c), {}).get("near_nominal_radii", []))
if best_c is None or near > best_near or (near == best_near and d < best_d):
    ...
```

**Rejected** for the same structural reason as §7.1 — it still lived inside the anchor-competition function, so it could still change anchor selection itself, not just per-tag candidate assignment. It also caused an unintended cascading regression.

### 7.3 Design requirement: two-stage architecture

Following the second rejection, the design was required to **preserve the anchor-selection stage exactly**, and perform any candidate refinement **only after** the winning anchor was already fixed by the unmodified, original `_score_anchor()`. A correctness review evaluated every possible conflict scenario (e.g., could a refined candidate for one tag ever collide with another tag's candidate?) and confirmed the geometric proof in §3 makes cross-tag contention impossible by construction — no `used`-set bookkeeping was needed in Stage 2.

### 7.4 Rejected ranking metric: `near_nominal_count` alone

A monotonicity review asked: could a candidate with one extra near-nominal ray, but substantially worse overall ray quality, wrongly replace a better production candidate? Answer: yes — `near_nominal_count` alone does not capture fallback-mode severity or overall hit count, and is gameable by candidates with a small number of coincidentally near-nominal-radius ray hits. **Rejected** as the sole ranking criterion.

### 7.5 Approved ranking design

Using only values already computed elsewhere in the pipeline (no new thresholds, no new computation), a 4-level ranking was designed and approved:

1. **`fallback_mode` tier** (`total_failure` < `off_nominal_fallback` < `normal`) — descending
2. **`n_hit`** (ray hit count out of 36) — descending
3. **`near_nominal_count`** — descending
4. **distance** to predicted position — ascending (closest wins ties)

A monotonicity safeguard was required: Stage 2 must never replace a production-selected candidate unless the replacement is *strictly* better under this ordering.

---

## 8. Final Implemented Algorithm

Implemented in `detect_holes()`, `detect_features.py` (current: lines ~344–437). Two logical additions, both confined to this one function:

**`_stage2_rank_key`** (lines 371–379) — the ranking key, built only from already-computed data:

```python
FALLBACK_RANK = {"total_failure": 0, "off_nominal_fallback": 1, "normal": 2}

def _stage2_rank_key(c, px, py):
    d = np.sqrt((c["cx_px"]-px)**2 + (c["cy_px"]-py)**2)
    dbg = _ray_debug_by_id.get(id(c), {})
    fallback = dbg.get("fallback_mode", "total_failure")
    n_hit = dbg.get("n_hit", 0)
    near = len(dbg.get("near_nominal_radii", []))
    return (FALLBACK_RANK.get(fallback, 0), n_hit, near, -d)
```

**Stage 2 refinement loop** (lines 403–437) — runs *after* the anchor-selection competition (§7.3) has already fixed `best_anchor_cxy`/`best_matched` using the unmodified original `_score_anchor()`. For each already-matched tag, it scans all candidates within `MATCH_TOL_PX` of that tag's predicted position and replaces the assignment only if a strictly higher-ranked candidate exists (tuple comparison `k > best_alt_key`, which encodes the exact monotonicity requirement from §7.5):

```python
if best_anchor_cxy is not None:
    preds_final = _predict_positions(*best_anchor_cxy)
    for tag, current in list(best_matched.items()):
        px, py = preds_final[tag]
        current_key = _stage2_rank_key(current, px, py)
        best_alt, best_alt_key = None, current_key
        for c in detected:
            if c is current:
                continue
            d = np.sqrt((c["cx_px"]-px)**2 + (c["cy_px"]-py)**2)
            if d >= MATCH_TOL_PX:
                continue
            k = _stage2_rank_key(c, px, py)
            if k > best_alt_key:
                best_alt, best_alt_key = c, k
        if best_alt is not None:
            best_matched[tag] = best_alt
```

`_score_anchor()`, preprocessing, Hough detection, `_subpixel_diameter()`, and `_refine_center()` are untouched by this implementation.

The loop optionally records what changed into `debug_context["stage2_preview"]` (current/alt position and ranking key) when a caller passes `debug_context` — this has no effect on the applied result and is purely diagnostic.

---

## 9. Regression Methodology

Every implementation step followed the same protocol:
1. `python -m py_compile detect_features.py`
2. `python -c "import detect_features"`
3. Full 33-cartridge regression: run `detect()` on all four image types (Holes, Neck, DAB, Mixing) for cartridges 1–33, compare every `(cartridge_id, image_type, feature_label)` row against a saved verified-baseline CSV (`regression_post_instrumentation.csv`), report:
   - `measured_mm` differences
   - `pass_fail` differences
   - full column-level differences (all columns, not just the two above), excluding the `timestamp` column (which always differs between runs and is not a behavioral signal)
4. Any difference outside an explicitly pre-identified, approved set was treated as a stop condition — never tuned, always investigated to root cause before proceeding.

Implementation itself was split into the smallest independently-verifiable increments:
- **Step 1:** add the ranking function and a dormant preview-only computation (`debug_context["stage2_preview"]`), with **zero** production behavior change. Verified via full regression (0 diffs) *and* a supplementary direct exercise of the new code path across all 33 cartridges (since the standard regression path never passes `debug_context` and would not otherwise execute the new code at all).
- **Step 2:** activate the ranking by applying it to `best_matched`.

---

## 10. Regression Results

**Step 1 (preview only):** 0 measurement diffs, 0 PASS/FAIL diffs, byte-identical CSV vs. baseline (excl. timestamp). Supplementary direct-exercise check: 0 errors across 33 cartridges, previewed **17 tag assignments that would change** — cartridges 2 (tags 3,4,9), 6 (tags 1,3,4,5,6,9), 15 (tags 1,3,9), 18 (tag 4), 31 (tags 1,3,4,6) — exactly matching the earlier quantitative risk assessment (§4).

**Step 2 (activated), before the coupling fix:**
- **17 measurement (`measured_mm`) differences** — all 17 exactly matched the Step 1 preview.
- **7 PASS/FAIL differences:** 2/Tag9, 6/Tag1, 6/Tag3, 6/Tag6, 15/Tag9, 18/Tag4 all FAIL→PASS; 31/Tag4 PASS→FAIL.
- **2 unexpected additional differences** outside the 17 (see §11).

---

## 11. Coupling Bug Discovered After Implementation

A full-row diff (not just `measured_mm`/`pass_fail`) surfaced **2 rows outside the 17 approved changes**:

| Row | Column | Before | After |
|---|---|---|---|
| Cartridge 18, Tag6 diameter | `notes` | `not_detected` | `outside_image` |
| Cartridge 18, Tag7 diameter | `notes` | `not_detected` | `outside_image` |

Both are **missing/unmatched holes** in cartridge 18 (Tag6 and Tag7 were never detected at all in this cartridge) — not among the 17 Stage 2 changes. Only their diagnostic classification text changed; no measurement or PASS/FAIL value was affected. Per standing instruction, this was treated as a stop condition: implementation halted immediately, no further steps attempted, and the mechanism was investigated before any fix was written.

### 11.1 Root Cause of the Coupling

The "missing holes" classification code (further down in `detect_holes()`, unrelated to Stage 2's own scope) independently re-derives an anchor reference point to decide whether a genuinely undetected tag's predicted position falls outside the image:

```python
anchor_tag = min(best_matched.keys())
anchor_c   = best_matched[anchor_tag]
ax, ay     = anchor_c["cx_px"], anchor_c["cy_px"]
...
for tag, (dx, dy) in REF_OFFSETS.items():
    if tag in best_matched:
        continue
    pred_x = ax + dx
    pred_y = ay + dy
    outside = (...)
```

This reads `best_matched` — the *same dict Stage 2 mutates in place*. Since Stage 2 only replaces values for keys that already exist (it never adds or removes tags from `best_matched`), the set of matched-vs-missing tags was never affected. But when the tag Stage 2 replaced happened to be the lowest-numbered matched tag (`min(best_matched.keys())`) in a given cartridge — which was the case for cartridge 18, where Tag4 was both the only Stage-2-changed tag and the anchor-reference tag used by this downstream code — the missing-hole logic picked up the Stage-2-replaced candidate's position instead of the position production had always used for this calculation. This shifted the computed predicted positions for the genuinely-missing Tag6/Tag7, flipping their `outside_image`/`not_detected` classification.

This was an unintended coupling between two independently-written pieces of code that happened to share the same mutable dictionary — not a flaw in the Stage 2 ranking logic itself.

### 11.2 Decoupling Fix

A snapshot of `best_matched` is taken **immediately after anchor selection finishes and before Stage 2 runs**, and the missing-hole block was changed to read from this frozen snapshot instead of the live, Stage-2-mutated dict:

```python
# Frozen snapshot of the anchor-selection result, taken before Stage 2
# runs. Downstream missing-hole classification must reason about the
# exact same anchor geometry production always used -- it must NOT see
# Stage 2's candidate reassignments below.
best_matched_anchor_ref = dict(best_matched)
```

The missing-hole block's three references were then changed from `best_matched` to `best_matched_anchor_ref`. Stage 2 continues to mutate the live `best_matched` for everything downstream that should reflect its corrected candidates (center refinement, final circle list) — only the missing-hole reasoning was decoupled. This was a 2-line/3-reference change, confined to `detect_holes()`, with no other function touched.

**Post-fix regression:** exactly 17 rows differ from baseline (the intended set only); cartridge 18 Tag6/Tag7 confirmed byte-identical to baseline again (including the `notes` field); zero unexpected changes remained.

---

## 12. Final Validation Summary

A validation-only phase (no code changes) attempted to assess the 17 changes against Leica ground truth, but **no genuine independent per-hole Leica-measured diameter data exists anywhere in the project.** Checked and ruled out:
- `MetaData/*.xml` per cartridge — acquisition/calibration metadata only, no measurement values.
- `failure_taxonomy_classified.csv`'s `diameter_mm_leica` column — this is Achira's own detected pixel diameter re-scaled by the Leica pixel-scale factor, not an independent measurement.
- `Cartridge failed dimensions.xlsx` (from `Failed cartridge details....zip`) — its companion annotated image (`Holes_ch00_detected.png`) carries Achira's own `qc_app.py` "Detected/PASS/FAIL/Scale/DWG" banner, indicating this spreadsheet documents Achira software's own flagged failures, not an independent Leica measurement. It is not usable as ground truth.

Validation therefore relied on the strongest evidence actually available — direct visual/ray-overlay inspection (§5, §6) — rather than fabricating a ground-truth comparison:

| Evidence tier | Count | Cases |
|---|---|---|
| High confidence (visual review confirms Stage 2 correct) | 11 | 2/9, 6/1, 6/3, 6/4, 6/6, 6/9, 15/3, 15/9, 31/3, 31/4, 31/6 |
| Medium confidence (non-visual: candidate-replay evidence, §4) | 2 | 2/4, 31/1 |
| Inconclusive | 1 | 18/4 |
| Unsupported by existing evidence | 3 | 2/3, 6/5, 15/1 |

The 3 unsupported cases share the identical `total_failure → normal` fallback-tier signature as the 2 medium-confidence cases, but that pattern alone is statistical and was never individually visually confirmed — per this investigation's own evidentiary standard, it does not qualify as support on its own.

**Update (post Stage 3):** this table reflects the evidence state at the time this report was written. The 3 "unsupported" cases were subsequently investigated as Stage 3 and reclassified to **high confidence** — see `docs/STAGE3_HOUGH_DETECTION_PLAN.md` §10 for the visual evidence. As of Stage 3's completion, 14 of 17 changes are high confidence, 2 are medium confidence, and 1 (18/Tag4) remains inconclusive; 0 are unsupported.

**PASS/FAIL, within the 17 changed rows:** before = 10 PASS / 7 FAIL; after = 16 PASS / 1 FAIL. The single PASS→FAIL flip (Cartridge 31/Tag4) is visually confirmed (§5, high confidence) as a correction of a previously-false PASS, not a regression — the production candidate was measuring an unrelated feature that happened to fall within tolerance, not the true hole.

---

## 13. Remaining Limitations

1. **No independent Leica ground truth exists** in this project to quantitatively validate absolute accuracy improvement. All validation is evidence-based (visual/ray overlays), not measurement-based.
2. ~~3 of 17 changes lack direct supporting evidence (2/Tag3, 6/Tag5, 15/Tag1) — recommend a targeted visual review of these specific cases before considering Stage 2 fully validated.~~ **Resolved by Stage 3** (`docs/STAGE3_HOUGH_DETECTION_PLAN.md`, §10): a focused visual investigation confirmed all three candidates sit on genuine through-holes with clean 36/36 ray-hit rings. All 17 Stage 2 changes now have direct or strong supporting evidence, except Cartridge 18/Tag4 (still inconclusive, see limitation 3 below).
3. **Cartridge 18/Tag4 remains visually inconclusive** — neither the production nor the Stage 2 candidate shows a clear hole boundary in the available crop.
4. **Blinded review caveat:** true psychological blinding was not fully achievable since the same reviewer conducted both passes (§6). The blinded pass used genuinely randomized, concealed labels but should not be treated as equivalent to an independent second reviewer.
5. **Dataset scope:** validated only against `E:\1-33\Washed baseplates` (Holes image type). Not yet run against the other announced datasets (`E:\34-50`, `E:\51-60`, `E:\61-70 (1)`, `E:\71-79`).
6. **Not yet merged:** the implementation lives on branch `stage2-candidate-selection` and has not been merged into `master`. `master` remains at the verified baseline (`8a6253d`, tag `verified-production-baseline`) with zero behavior change.

---

## 14. Reference

- **Git commit implementing Stage 2:** `ba61359` — "Implement Stage 2 candidate selection refinement" (branch `stage2-candidate-selection`, 1 file changed: `detect_features.py`).
- **Baseline commit:** `8a6253d` — "Restore verified production baseline after QC investigation" (branch `master`, tag `verified-production-baseline`).
