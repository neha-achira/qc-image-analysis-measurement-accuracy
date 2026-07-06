# Stage 5 — Per-Cartridge Investigation Report

Companion to `docs/STAGE5_ROOT_CAUSE_ANALYSIS.md`. Full candidate-by-candidate evidence for every failing case. All images referenced are in `validation_output/stage5_root_cause/`. Read-only investigation — no production code modified.

---

## Cartridge 51 (dataset 51–60)

**Overall:** FAIL (1 of 7 tags out of tolerance). `cart51_overview.png` shows all 7 tags correctly located (6 green/PASS, 1 red/FAIL).

### Tag 4 — FAIL, diameter measurement

- **Every generated candidate near this position:**
  | Position | Radius | Distance to expected | Fallback | n_hit | near |
  |---|---|---|---|---|---|
  | (2436, 844) | 80 | 51px | normal | 36/36 | 36 |
  | (2868, 836) | 100 | 409px | total_failure | 3/36 | 0 |
  | (1924, 708) | 100 | 545px | normal | 16/36 | 11 |
- **Why the selected candidate was chosen:** (2436, 844) is both the closest to the expected position (51px, essentially exact) and has the cleanest possible ray-cast (36/36 hits, all within the near-nominal window). No other candidate is competitive.
- **Why no other candidate could be correct:** the 409px candidate is a `total_failure` (3 hits) — clearly a false positive; the 545px candidate is a weaker partial match, also far more distant.
- **How the diameter was computed:** `_subpixel_diameter` cast 36 rays from (2436, 844); all 36 found a wall within the near-nominal window, averaging to 179.0px → 0.4475mm at this cartridge's 2.5µm/px scale.
- **Annotated image:** `cart51_tag4_zoom.png` — shows the selected candidate's ray ring sitting precisely on the visible hole's dark boundary. No incorrect edge fitting is visible; the candidate is correctly centered.
- **Classification:** Diameter measurement failure (borderline: deviation −0.0525mm against ±0.05mm tolerance). Detection and candidate selection are both confirmed correct. Whether the underlying ~0.0025mm-over-tolerance gap reflects a software measurement bias or genuine part variance cannot be determined without an independent reference measurement (none exists for this hole).

---

## Cartridge 66 (dataset 61–70)

**Overall:** FAIL (2 of 7 tags out of tolerance). `cart66_overview.png` shows 5 tags PASS (green), 2 FAIL (red) — one of the red markers (Tag9) is visibly not on any hole.

### Tag 6 — FAIL, diameter measurement

- **Every generated candidate near this position:**
  | Position | Radius | Distance to expected | Fallback | n_hit | near |
  |---|---|---|---|---|---|
  | (3112, 2312) | 116 | 104px | total_failure | 5/36 | 0 |
  | (3352, 1936) | 80 | 462px | normal | 36/36 | 36 |
- **Why the selected candidate was chosen:** despite being farther from the expected position (462px vs. 104px), (3352, 1936) is a `normal`-fallback candidate with a perfect 36/36 ray-cast, versus the closer candidate's `total_failure` (5/36) — Stage 2's ranking correctly prefers the far-but-clean candidate over the near-but-false-positive one.
- **Why the closer candidate was rejected:** its ray-cast found almost no wall (5/36) — it is not a real hole.
- **How the diameter was computed:** 36/36 rays hit within the near-nominal window, averaging to 176.0px → 0.44mm.
- **Annotated image:** `cart66_tag6_zoom.png` confirms the selected candidate sits exactly on the visible hole's dark boundary.
- **Classification:** Diameter measurement failure (borderline: deviation −0.06mm). Same caveat as Cartridge 51/Tag4 — detection is correct, underlying accuracy cannot be independently verified.

### Tag 9 — FAIL, image quality / ranking

- **Every generated candidate near this position:**
  | Position | Radius | Distance to expected | Fallback | n_hit | near |
  |---|---|---|---|---|---|
  | (6324, 2332) | 92 | 0px (exact) | normal | 9/36 | 5 |
  | (5812, 2392) | 108 | 516px | normal | 20/36 | 16 |
- **Why the selected candidate was chosen:** both candidates are nominally `normal` fallback, so the ranking compares `n_hit`: 20 > 9, so the farther candidate wins under the existing, already-validated Stage 2 ranking. This is not a ranking bug — the rule was applied correctly to the data available.
- **Why the "obvious" choice (dead-center on the expected position) was not selected:** its ray-cast is poor (9/36) — it does not look like a clean hole either.
- **How the diameter was computed:** for the selected candidate, 20 of 36 rays hit within the near-nominal window, averaging to 221.0px → 0.5525mm.
- **Annotated image:** `cart66_tag9_zoom.png` shows the selected candidate's ray hits forming only a partial arc, on what appears to be plain texture, not a clean hole boundary. `cart66_overview.png` shows a real, visible hole near the top-right of the image, close to where a channel groove crosses — consistent with the true hole's edge being partially obscured or low-contrast at that exact location.
- **Classification:** Neither candidate is confirmed as a genuine, clean hole detection. Best explanation given the evidence: image quality limitation (real hole obscured/low-contrast near a channel crossing), with the ranking behaving correctly given the (poor) data it had to work with. Flagged as unresolved rather than force-classified.

---

## Cartridge 70 (dataset 61–70)

**Overall:** FAIL (1 of 7 tags out of tolerance). `cart70_overview.png` shows 6 tags PASS (green), 1 FAIL (red).

### Tag 5 — FAIL, candidate generation vs. image quality (inconclusive)

- **Every generated candidate within a wide search of this position** (no 600px cutoff applied, to check whether anything exists further out):
  | Position | Radius | Distance to expected | Fallback | n_hit | near |
  |---|---|---|---|---|---|
  | (2468, 5524) | 112 | 231px | normal | 30/36 | 9 |
  | (1628, 5332) | 108 | 703px (outside tolerance) | normal | 16/36 | 11 |
  | (1292, 5500) | 112 | 981px (outside tolerance) | total_failure | 1/36 | 0 |
- **Why the selected candidate was chosen:** it is the only candidate within the 600px matching tolerance, and its fallback is `normal` (not `total_failure`) — it was the only real option available to select.
- **Why it may still be wrong:** its own ray-cast is mixed — 30 of 36 rays hit *something*, but only 9 of those are within the expected-radius window, meaning most of what it's hitting is not at the expected hole diameter. The overview image (`cart70_overview.png`) and zoomed crop (`cart70_tag5_zoom.png`) show what appears to be a large, high-contrast, clearly visible dark hole near the expected position that the selected candidate is not centered on.
- **How the diameter was computed:** the 30 hit rays averaged to 176.0px → 0.44mm.
- **Annotated image:** `cart70_tag5_zoom.png` — the predicted-position marker sits very close to a visually obvious hole; the selected candidate (orange circle) is offset from it.
- **Classification: inconclusive between candidate generation failure (Hough may have missed the true hole; the next-nearest raw candidate is just outside the current 600px tolerance at 703px) and image quality limitation (the true hole's edge may itself be ambiguous).** This is explicitly flagged as needing a more precise, pixel-level follow-up (e.g., manually locating the true hole's exact center from the source image) before deciding on a fix approach — not resolved by this investigation.

---

## Cartridge 72 (dataset 71–79)

**Overall:** FAIL (3 of 7 matched, 2 of those 3 out of tolerance, 4 missing). `cart72_overview.png` shows the extent of the problem: only Tag6, Tag7, Tag9 are labeled; Tag1/3/4/5 show magenta "MISSING" markers, mostly clustered off the left edge of the image; at least one more real, visible hole (top-left of the image) is never referenced by the software at all.

### Anchor-selection check (ruling out a Stage 1 bug)

Every one of the 24 raw Hough candidates in this image was independently tried as a hypothetical anchor (i.e., re-running the exact anchor-competition logic with every possible starting point). **The anchor actually chosen by production, (4836, 3412), already achieves the best possible score (3/7) — no alternative anchor choice among Hough's candidates does better.** This rules out a Stage 1 (`_score_anchor`) selection bug: given the candidates Hough generated, the anchor-competition logic made the correct choice.

### Tag 1, Tag 3, Tag 5 — MISSING, correctly labeled `outside_image`

Recomputing the true predicted positions from the confirmed-correct anchor (4836, 3412):
| Tag | True predicted position | Within 7183×6081 image? |
|---|---|---|
| 1 | (−1255, 1948) | No |
| 3 | (−838, 4617) | No |
| 5 | (444, 7008) | No (y exceeds image height) |

All three are genuinely outside the captured image — the `outside_image` label is correct for these three.

### Tag 4 — MISSING, mislabeled `outside_image` (should be `not_detected`)

- **True predicted position:** (569, 2304) — this **is** inside the image (0–7183, 0–6081).
- **The production software currently reports this as `outside_image`.** This is wrong, and the mechanism is understood precisely: the missing-hole diagnostic code approximates the anchor position using whichever matched tag has the lowest tag number (here, Tag6, at (1084, 3080)) *without* correcting for that tag's own offset from the true anchor. This approximation is only exactly correct when Tag 9 (the true zero-offset anchor) happens to be the lowest-numbered matched tag — here it isn't, so the approximation is off, producing an incorrectly-negative predicted x-position and the wrong "outside image" label.
- **Nearest raw candidate to the true predicted position:** 931px away — well beyond the 600px matching tolerance. **No genuine candidate exists near Tag4's true expected location.**
- **Classification:** Candidate generation failure (Hough did not detect a candidate near the true hole location) **plus** a separate, confirmed diagnostic-labeling defect (wrong missing-hole reason). These are two distinct issues that happen to affect the same tag.
- **Update:** the diagnostic-labeling defect has since been fixed and validated (`docs/STAGE5_ROOT_CAUSE_ANALYSIS.md` §6.1, Fix 3, commit `4aa1779`). Tag4 now correctly reports `not_detected`. A full blast-radius scan found this same mislabeling in 5 other cartridges (18, 33, 45, 48, 50) as well — all now fixed. The candidate generation failure itself (Hough still doesn't detect a candidate at Tag4's true position) is unchanged and remains unimplemented, since it is part of the broader, still-unscoped Cartridge 72 pattern-matching breakdown.

### Tag 6 — PASS (included for context)

Matched correctly: (1084, 3080), 520px from its expected position, `normal` fallback, 36/36 ray-cast — a clean, correct detection despite being one of only 3 successfully matched tags.

### Tag 7 — FAIL, matched but poor quality

- **Selected candidate:** (2144, 5072), 470px from expected, `normal` fallback, but only 15/36 ray hits (8 within the near-nominal window).
- **Why it was chosen:** it is the only candidate within the 600px matching tolerance.
- **Annotated image:** `cart72_tag7_zoom.png` shows the selected candidate's ray hits forming only a partial arc along one edge, near what looks like a channel/scratch feature, not a clean hole boundary — consistent with the same geometric-drift problem affecting this cartridge (the true hole may be elsewhere, out of the searched tolerance window).
- **How the diameter was computed:** 15 hit rays averaged to 228.0px → 0.57mm.
- **Classification:** Best explained as a symptom of the same pattern-matching/geometry breakdown as the rest of this cartridge (§4.4 of the main report), not an independent defect.

### Tag 9 — FAIL, the anchor candidate itself

- **Selected candidate:** (4836, 3412), exactly at the expected position (it *is* the anchor, by construction — Tag 9's offset is (0,0)) but only 9/36 ray hits (4 within the near-nominal window).
- **Annotated image:** `cart72_tag9_zoom.png` shows this candidate sitting on plain texture with only a faint partial arc of ray hits along what appears to be a scratch or channel line above it — not a clean hole boundary.
- **How the diameter was computed:** 9 hit rays averaged to 168.0px → 0.615mm (dev +0.115mm — the largest deviation found in this entire investigation).
- **Classification:** Pattern matching failure. This candidate was confirmed to be the best available anchor choice (see above) — the problem is not that a better anchor was overlooked, but that **no candidate corresponding to a genuine hole exists near where the geometric model expects Tag 9 to be** for this cartridge.

---

## Cartridge 79 (dataset 71–79) — not a `detect_features.py` issue

**Overall:** FAIL in the production CSV, but the real `Holes_ch00.png` result is 7/7 PASS. See main report §5 for full mechanism. Files present in the cartridge folder: `Holes_ch00.png` (correct), `Nrck_ch00.png` (misnamed — should be `Neck_ch00.png`), `DAB_ch00.png`, `Mixing_ch00.png`. The misnamed file is silently classified as a "holes" image by `detect_image_type()`'s fallback default, is run through hole detection (producing a garbage 1/7 result), and — because it is processed after the real Holes image in alphabetical order — its wrong result overwrites the correct one in the batch summary. No `detect_features.py` change is implicated; this is a `qc_app.py` file-classification and batch-processing-order issue, and a data-entry (file naming) issue.
