# Measurement Accuracy — Real-Image Validation (BP 1–30)

**Status:** objective fixes implemented and validated on the real BP 1–30
images. **Not production-ready**: the diameter-definition and tolerance
questions are open, and the neck is unresolved (provisional legacy value).

Data: `1200 new baseplates.zip` (BP 1–20) and `new BP(21-30).zip`
(BP 21–30), 4 images per BP (120 images). Ground truth: the manual (physical)
measurements in the *Comparison* sheet of `JIra batches comparision data.xlsx`
(29 cartridges; BP 3 has images but no manual row).

## 1. What was fixed

| Area | Problem found on real images | Fix |
|---|---|---|
| Calibration | `calibration.json` 2.5 µm/px (2.667 neck) came from entering drawing nominals for clicked features. | Holes/DAB/mixing and (with the CH05 neck method) neck now use the Leica scale bar burnt into every image: DAB 957.1 µm / 370 px = 2.5868, Neck 954.5 µm / 369 px = 2.5867 µm/px; Holes "3.7 mm" (1435–1440 px) and Mixing "6.4 mm" (2473–2481 px) agree. `calibration_source: "leica_scale_bar"`. |
| MX edge | Fixed threshold 100 lands 2.0 / 2.8 / 4.0 px inside the wall on MX01 / MX02 / MX03 because the edge softens and dims towards the right of the stitched image. | Per-ray wall location at the steepest bright→dark descent near the threshold hit (`_refine_edge_radius`), shared with holes and DAB. |
| Ray origin | First-pass rays start at the Hough/blob centre (up to ~30 px off); the median ray is then a half-chord, and the earlier re-centring refused shifts > 25 % of the radius. | Fit a circle to the first-pass wall points, **re-cast all rays from the fitted centre**, fit again (`_wall_radii`). |
| DAB localisation | Largest/only bright blob was accepted: a ~570 px speck (BP24, BP27) and a partial bright core at threshold 120 (BP6, centroid 31 px off). | Accept only hole-shaped blobs (equivalent radius 0.6–1.4 × nominal, bbox aspect ≤ 1.3, fill ≥ 0.80, dark annulus); the roundest across thresholds wins. `localization_method` is reported. |
| File names | `Miximg_ch00.png` (BP6), `Miixng_ch00.png` (BP20) were silently skipped. | `preprocess.validate_cartridge_images` reports unrecognised/missing/duplicate images (with a suggested type); missing types give a `NOT_MEASURED` row; the GUI shows `MISSING` and never an overall `PASS` (`INCOMPLETE`). Files are never renamed. |

Reported values are still the **circle-equivalent** diameter. New
informational `geometry` fields (fitted-circle diameter, ellipse major/minor
axis, edge spread, fit RMS, centre shift, `ellipse_fit_ok`) are added to each
hole / DAB / MX result; CSV output columns are unchanged.

## 2. Real-image results (29 pairs, production path)

`detect_cartridge_folder()` with the current `calibration.json`; "Old" is the
recorded software value from the workbook.

| Feature | Manual | Old | New | Old MAE | New MAE | Old RMSE | New RMSE | New mean signed |
|---|---|---|---|---|---|---|---|---|
| Tag holes (202 rows) | 0.5426 | 0.5024 | 0.5251 | 0.0403 | 0.0186 | 0.0437 | 0.0245 | −0.0175 (−3.2 %) |
| MX01 | 0.5507 | 0.5182 | 0.5447 | 0.0324 | 0.0081 | 0.0339 | 0.0107 | −0.0060 (−1.1 %) |
| MX02 | 0.5491 | 0.5058 | 0.5366 | 0.0433 | 0.0136 | 0.0457 | 0.0177 | −0.0125 (−2.3 %) |
| MX03 | 0.5476 | 0.4960 | 0.5273 | 0.0516 | 0.0209 | 0.0567 | 0.0274 | −0.0203 (−3.7 %) |
| DAB | 0.5444 | 0.5248 | 0.5426 | 0.0195 | 0.0062 | 0.0253 | 0.0114 | −0.0017 (−0.3 %) |
| Neck (legacy, provisional; see §3) | 0.2008 | 0.1862 | 0.1807 | 0.0180 | 0.0204 | 0.0246 | 0.0278 | −0.0201 (−10.0 %) |

Per-BP table: `validation_output/real_bp_final/per_bp_comparison_final.csv`.

## 3. Open items — require confirmation (do not guess)

1. **Diameter definition (Tags / MX) — investigated, NOT changed.**
   * Software reports the circle-equivalent diameter (2 x median wall radius
     about the fitted centre, wall edges from rays re-cast from that centre).
   * Out-of-roundness on the real images is almost entirely intrusions into
     an otherwise round bore (flash / burr / debris): of 56 Tag/MX holes with
     ovality >= 7 % (excl. BP 1/6/9/26), 54 are intrusion-type and none is a
     genuine ellipse (one-sided radius distribution, skew ~ -1; 2nd harmonic
     explains ~26 % of radius variance).
   * The two manual readings per hole are repeats of one diameter (difference
     ~7 um even where the image shows ~49 um major-minor), both near the
     largest intact wall-to-wall extent.
   * Residual bias is geometric: on nearly circular MX holes circle-equivalent
     agrees with manual (-0.3 %); its error grows with ovality at
     -0.48 % per % (r = -0.70, intercept ~0). The circle through the intact
     wall (ignoring intrusions) matches manual on intrusion holes (+0.03 %),
     which also explains the ~-1.5 % tag residual on "round" holes with small
     burrs. DAB holes are nearly round; circle-equivalent already agrees.
   * Not changed because: no drawing/SOP defines how Ø0.50 THRU is measured;
     whether flash/burr counts toward the hole size is the same specification
     question as the neck (C); and a robust intact-wall estimator does not yet
     exist (a quick envelope fit diverged on 2/56 holes).
   Details: `validation_output/diameter_definition/`.
   Experimental intact-wall diameter (`experimental_intact_wall.py`,
   diagnostic only, not called by production): round-bore model, consensus
   circle through the largest co-circular set of wall points, intrusions and
   escapes rejected, AMBIGUOUS when the bore is not uniquely determined.
   Real BP 1-30 Tag/MX: 219 OK / 80 AMBIGUOUS. On the 211 paired OK holes the
   mean signed error goes from -2.50 % (production) to -1.90 % (MAE 0.0150 ->
   0.0127); intrusion-affected Tags -3.35 -> -2.06 %, MX -2.04 -> -0.66 %;
   clean holes unchanged (Tags) or slightly lower (MX, mean vs production's
   60th percentile). Failure modes: long flats/intrusions where two circles
   fit (BP22 MX02/MX03 AMBIGUOUS) and coherent OUTWARD arcs (channel mouth or
   bore?) that make intact < production on 7 OK holes. Clean Tags keep a
   ~-1.3 to -2.3 % bias not explained by intrusions.
   Details: `validation_output/intact_wall/`.
2. **Official hole nominal and tolerance.** Drawing: Ø0.50 (no explicit
   tolerance). Code: 0.50 ± 0.05 (unchanged). Workbook: 0.55 (user-provided).
   About 45 % of the manual hole values exceed 0.55 mm, so accurate software
   with the current limits will fail many holes the old under-reading
   software passed.
3. **Neck (CH05) — UNRESOLVED. Production value is PROVISIONAL.**
   * **Production (`detect_neck`)**: the LEGACY dark-band medial-axis method,
     kept temporarily. It measures the thickness of the dark wall bands and has
     NOT been shown to represent the operator's CH05 definition. With the
     neck at the Leica scale (2.587 µm/px, unchanged from the previous round)
     it reads −10.0 % mean signed (MAE 0.0204, RMSE 0.0278); the −7.3 % quoted
     for the legacy method was obtained with the old 2.667 µm/px neck entry.
   * **Frozen experimental (`detect_neck_experimental`)**: implements the
     operator definition from `Neck.png` (203.79 / 200.29 µm): perpendicular
     distance across the grey neck floor between the floor→solid-wall
     boundaries, at the narrowest part. Attached to every production result
     as `experimental_ch05` (diagnostic only; CSV notes show it). On BP 1–30 it
     reads −14.1 % (MAE 0.0284). It must not be tuned against the workbook.
   Open questions, kept separate:
   * **A. Clean group A** (BP 1, 3, 4, 15, 17–20, 24, 25). Image geometry alone
     (scale fixed by the scale bars): neck width 0.158–0.176 mm at
     mid-transition, 0.162–0.189 mm at the operator's placement transferred
     from `Neck.png`, and at most 0.180–0.202 mm (mean 0.191) at the extreme
     dark end of the transition. The stored images therefore show a neck of
     roughly 0.17–0.18 mm by the operator's boundary; the reference part in
     `Neck.png` is itself wider (186–194 µm at mid-transition). Why these
     images are narrower than the ~0.20 mm physical value is not determined
     (candidates: focal plane / wall profile, image vs part state, manual
     method) — it is not an edge-detection question.
   * **B. Group B** (dark strip + thin bright line): the thin-bright-edge
     boundary is PROVISIONAL; there is no operator-marked group-B image.
   * **C. Flash/burr** (BP 7, 8, 12, 13, 16, 22, 26, 27): whether molding
     flash counts toward the CH05 minimum is a SPECIFICATION question. The
     detector is not changed to ignore flash without an engineering/operator
     definition.
   Image artefacts: BP1 contains a thin dark filament/fibre/flash across the
   neck (not a stitching seam) — thin features are not walls. BP2 has a real
   tile seam at y ≈ 764; profiles with a boundary within 6 px of it are
   excluded. Per-BP results and diagnostics: `validation_output/neck_width/`.

## 4. Manual / image inconsistencies (flagged, not fitted)

Rows where the manual diameter exceeds the largest wall-to-wall extent visible
in the image (major axis) by more than 3 % are flagged in the per-BP CSV: 46
rows, concentrated in BP1 (7), BP6 (6), BP9 (5) and BP26 (4). Example: BP1
Tag4 is a clean round aperture of 0.477 mm on the image (largest extent 0.484 mm); manual 0.563 mm. No
algorithm change was made to accommodate these rows.

## 5. Other observations

* MX02/MX03 apertures are taller than wide (median x/y 0.971 / 0.954). No tile
  seam crosses any MX aperture, the ratio varies part-to-part, and the
  surrounding annulus is wider in x — evidence for physical ovality rather
  than a stitching artefact (not provable without a two-axis physical
  measurement).
* Some recorded workbook values were produced by a different run/version
  (e.g. BP27 DAB recorded 0.525, original code re-run 0.411).
* BP27 Tag6 is not detected on the real image.
* Pre-existing: console prints of "✓/✗" raise `UnicodeEncodeError` when stdout
  is a cp1252 pipe (not the GUI). Not changed.

## 6. Reproducing

```
py -m pytest tests -v -p no:cacheprovider
set QC_BP_DATA=E:\QC-main\bp_work\all   &  py -m pytest tests -v -p no:cacheprovider   (real-image tests)
py compare_manual_measurements.py --batch E:\QC-main\bp_work\all --calibration-mode json --diagnostics diag
```
