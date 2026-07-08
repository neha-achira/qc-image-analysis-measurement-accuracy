# Stage 7 — Cartridge 72 End-to-End Pipeline Trace and Root-Cause Determination

**Status:** Investigation complete. Root-cause report only — no production code modified.
**Branch:** `stage7-geometric-model-investigation` (no commits; read-only replay).
**Method:** faithful, line-for-line replay of the committed `detect_holes()` logic (Stage 1 anchor competition → Stage 2 ranking refinement → recovery pass → missing-hole diagnostics, `detect_features.py` lines 344–533), using the real `_subpixel_diameter()` ray-cast function. Not an approximation — every threshold, tie-break, and formula matches production exactly.

---

## 1. Headline Finding

**The single point of failure for all four missing tags is Stage 1 anchor selection — not Hough, not Stage 2, not the recovery pass.**

Stage 1's anchor competition selects a false-positive candidate at `(4836, 3412)` as the anchor (ray-cast quality: 9/36 hits, 11.1% near-nominal ratio, 280° angular gap — previously identified in Stage 5 as sitting on plain texture). Every downstream predicted position is computed from this wrong anchor, so:

- 3 of the 4 missing tags' predicted positions land **entirely outside the image frame** (hundreds to thousands of pixels past the boundary), so the recovery pass's own bounds check discards them before it ever looks for a real candidate.
- The 4th missing tag's predicted position is in-bounds but 2441px from its genuine hole — far beyond even the recovery pass's widened 690px tolerance.
- All four genuine holes are real, present, and high ray-cast quality (36/36 hits each) — they are simply never looked for in the right place.

**A previously undocumented, more severe consequence surfaces in this trace:** two of the three tags production currently reports as "matched" are also wrong.
- **Tag 6's reported position, `(1084, 3080)`, is not Tag 6's hole at all — it is an exact match to Tag 3's genuine hole**, coincidentally captured because the wrong anchor's predicted position for Tag 6 happens to fall within 600px of it.
- **Tag 7's reported position, `(2144, 5072)`, is a low-quality candidate** (15/36 hits, 22.2% near-nominal, 150° angular gap) — not Tag 7's genuine hole. Tag 7's actual, high-quality (36/36) hole exists at `(3780, 3116)` but sits 2481px from the wrong predicted position and is never considered.

So Cartridge 72's true state is: **6 of 7 tags have genuine, high-quality, correctly-located holes** (Tags 1, 3, 4, 5, 6, 7). Production currently reports 4 as missing, 1 (Tag 6) as a mislabeled duplicate of Tag 3, and 1 (Tag 7) as a wrong low-quality candidate — only Tag 9 (the anomalous, oversized non-hole feature documented in the companion geometric-model report) is genuinely absent.

---

## 2. Per-Tag Pipeline Trace

Winning Stage 1 anchor: **(4836, 3412)** — ray-cast quality 9/36 hits, near-nominal ratio 11.1%, angular gap 280°, `fallback_mode=normal` (passes only because "normal" here means "found ≥4 near-nominal rays," not that the shape is a clean circle).

### Tag 1 — expected position (4836−6091, 3412−1464) = **(−1255, 1948)**

| Field | Value |
|---|---|
| Raw Hough candidates within 1000px of expected position | **0** |
| Genuine hole for this tag (independently established) | (644, 416) — 36/36 hits, 0° gap, but 3313px from the (wrong) expected position |
| Stage 1 decision | No candidate within 600px — unmatched |
| Stage 2 decision | N/A (nothing to re-rank) |
| Recovery-pass eligibility | Predicted position (−1255, 1948) fails the outside-image bounds check (x < −600) |
| Recovery-pass rejection reason | Excluded before any candidate comparison — outside image bounds |
| **Final outcome** | **`outside_image`** |

### Tag 3 — expected position (4836−5674, 3412+1205) = **(−838, 4617)**

| Field | Value |
|---|---|
| Raw Hough candidates within 1000px of expected position | **0** |
| Genuine hole for this tag | (1084, 3080) — 36/36 hits, 0° gap — **already consumed under the Tag 6 label** (see §3) |
| Stage 1 decision | No candidate within 600px of (−838,4617) — unmatched; separately, its real hole gets claimed by Tag 6's search |
| Stage 2 decision | N/A |
| Recovery-pass eligibility | Predicted position (−838, 4617) fails the outside-image bounds check (x < −600) |
| Recovery-pass rejection reason | Excluded before any candidate comparison — outside image bounds (and its real candidate is unavailable regardless, already claimed by Tag 6) |
| **Final outcome** | **`outside_image`** |

### Tag 4 — expected position (4836−4267, 3412−1108) = **(569, 2304)**

| Raw candidate | Distance | n_hit | near_ratio | angular_gap | fallback_mode |
|---|---|---|---|---|---|
| (1084, 3080) *(= genuine Tag 3 hole)* | 931.3px | 36 | 1.00 | 10.0° | normal |

| Field | Value |
|---|---|
| Genuine hole for this tag | (2456, 756) — 36/36 hits, 0° gap — 2440.7px from the (wrong) expected position, not even in the "within 1000px" list |
| Stage 1 decision | No candidate within 600px — unmatched |
| Stage 2 decision | N/A |
| Recovery-pass eligibility | Predicted position (569, 2304) is in-bounds — recovery pass runs its search |
| Recovery-pass rejection reason | Nearest available candidate ((1084,3080), already someone else's genuine hole) rejected at 931px ≥ 690px tolerance. The tag's own genuine hole (2456,756) is checked too and rejected at 2441px ≥ 690px — over 3.5× the recovery tolerance. All 22 other raw candidates are 3193–6587px away. |
| **Final outcome** | **`not_detected`** |

### Tag 5 — expected position (4836−4392, 3412+3596) = **(444, 7008)**

| Field | Value |
|---|---|
| Raw Hough candidates within 1000px of expected position | **0** |
| Genuine hole for this tag | (2396, 5444) — 36/36 hits, 0° gap — 2467px from the (wrong) expected position |
| Stage 1 decision | No candidate within 600px — unmatched |
| Stage 2 decision | N/A |
| Recovery-pass eligibility | Predicted position (444, 7008) fails the outside-image bounds check (y = 7008 > image height 6081 + 600px margin = 6681) |
| Recovery-pass rejection reason | Excluded before any candidate comparison — outside image bounds |
| **Final outcome** | **`outside_image`** |

### Tag 6 — expected position (4836−3302, 3412−72) = **(1534, 3340)** — reported "matched," but wrong identity

| Raw candidate | Distance | n_hit | near_ratio | angular_gap | fallback_mode |
|---|---|---|---|---|---|
| (1084, 3080) *(= genuine Tag 3 hole)* | 519.7px | 36 | 1.00 | 10.0° | normal |

| Field | Value |
|---|---|
| Genuine hole for this tag | (3440, 1760) — 36/36 hits, 0° gap — never considered; not within 1000px of the wrong expected position |
| Stage 1 decision | The only in-tolerance candidate, (1084,3080), is claimed under the Tag 6 label — but this is Tag 3's real hole, not Tag 6's |
| Stage 2 decision | No alternative candidate scores higher within tolerance — no change |
| Recovery-pass eligibility | N/A — already matched, recovery pass skips it |
| **Final outcome** | **Reported as "matched," position (1084,3080) — this is an exact duplicate of Tag 3's genuine hole, reported under the wrong tag label. Tag 6's own genuine hole at (3440,1760) is never detected as such.** |

### Tag 7 — expected position (4836−2971, 3412+1282) = **(1865, 4694)** — reported "matched," but wrong candidate

| Raw candidate | Distance | n_hit | near_ratio | angular_gap | fallback_mode |
|---|---|---|---|---|---|
| (2144, 5072) | 469.8px | 15 | 0.222 | 150.0° | normal |
| (2396, 5444) *(= genuine Tag 5 hole)* | 918.9px | 36 | 1.00 | 10.0° | normal |

| Field | Value |
|---|---|
| Genuine hole for this tag | (3780, 3116) — 36/36 hits, 0° gap — 2481px from the (wrong) expected position, not in the "within 1000px" list at all |
| Stage 1 decision | Nearest in-tolerance candidate, (2144,5072) at 469.8px, is claimed. This candidate is low-quality (15/36 hits, 150° angular gap) — very likely a partial arc / false-positive-adjacent detection, not a genuine hole |
| Stage 2 decision | The alternative in the list, (2396,5444) at 918.9px, is *higher quality* (36/36) but is outside the 600px Stage 2 re-ranking search radius, so it is never even considered as a replacement |
| Recovery-pass eligibility | N/A — already matched, recovery pass skips it |
| **Final outcome** | **Reported as "matched," position (2144,5072) — a low-quality candidate, not Tag 7's genuine hole. Tag 7's own genuine hole at (3780,3116) is never detected as such (and coincidentally, Tag 5's genuine hole sits nearby too, also unclaimed).** |

### Tag 9 — expected position = anchor itself = **(4836, 3412)**

| Field | Value |
|---|---|
| Ray-cast quality at this position | 9/36 hits, 11.1% near-nominal ratio, 280° angular gap, `fallback_mode=normal` |
| Stage 1 decision | Matched to itself trivially (distance 0) — this is the anchor |
| **Final outcome** | **Reported as "matched," but this is the false-positive anchor candidate identified in Stage 5 as sitting on plain texture — not a genuine hole.** The true Tag 9 location (established via independent shape-fit in the companion report, ≈(6728,1795)) contains an oversized, non-circular feature that Hough's radius-bounded circle search never generates a candidate for; the nearest raw candidate there, (7072,1256), is 639px away and only moderate quality (17/36 hits, 47% near-nominal) — itself well outside both the 600px match tolerance and the 690px recovery tolerance for any of the other 6 tags, so it could not have won the anchor competition honestly either. |

---

## 3. First Unrecoverable Pipeline Stage, By Tag

| Tag | First stage where it becomes unrecoverable | Mechanism |
|---|---|---|
| **1** | **Stage 1 — anchor selection** | Wrong anchor's predicted position for Tag 1 lands outside the image frame; every downstream stage (Stage 2, recovery) inherits this and never runs a real search |
| **3** | **Stage 1 — anchor selection** | Same outside-frame mechanism *and* its genuine hole is separately misclaimed under the Tag 6 label by the same wrong anchor, so even a wider bounds check could not recover it without also fixing the Tag 6 misassignment |
| **4** | **Stage 1 — anchor selection** | Wrong anchor predicts a position 2441px from the genuine hole — beyond even the recovery pass's 690px tolerance (3.5× over) |
| **5** | **Stage 1 — anchor selection** | Wrong anchor's predicted position lands outside the image frame (y-coordinate exceeds image height + margin) |

**Hough candidate generation, ray-casting, Stage 2 ranking, and the recovery pass are not responsible for any of the four missing tags** — all four genuine holes are detected with perfect ray-cast quality (36/36 hits, 0° angular gap) and are physically present in the raw candidate list throughout. They fail exclusively because every predicted position used to search for them is derived from the one wrong anchor chosen in Stage 1.

Additionally (not "missing" tags, but directly relevant to root cause): **Tag 6 and Tag 7's reported matches are also artifacts of the same wrong anchor** — Stage 1 claims whatever real or false candidate happens to coincidentally fall within tolerance of the wrong predicted position, regardless of whether it is that tag's actual hole.

---

## 4. Why Stage 1 Chose the Wrong Anchor (Origin, Not Fix)

Per the companion report (`STAGE7_GEOMETRIC_MODEL_INVESTIGATION_REPORT.md`), Cartridge 72's true Tag 9 location contains a real but oversized, non-circular physical feature that Hough's fixed radius search (78–122% of the 100px nominal) never generates a candidate for. With no valid candidate near the true anchor position, Stage 1's competition — which only evaluates candidates as hypothetical Tag 9 positions — cannot find the correct anchor and instead settles on whichever raw candidate achieves the highest **coincidental** match count, which turns out to be the plain-texture false positive at (4836,3412) with a score of 3/7 (itself partly composed of the Tag 6/Tag 7 misassignments documented above, not 3 genuinely correct matches).

This is consistent with, and adds mechanistic detail to, the root cause already established in the companion geometric-model report. No new hypothesis is introduced here — this trace is the evidentiary confirmation, at the level of individual candidates and rejection reasons, of exactly how that root cause propagates through every pipeline stage for each of the seven tags.

---

## 5. Scope Compliance

- No production code was modified.
- No thresholds were tuned.
- This report identifies failure points only; no fix is proposed here (see the companion report, §5, for the one candidate correction already proposed and explicitly not yet implemented).

Stopping here per your instruction.
