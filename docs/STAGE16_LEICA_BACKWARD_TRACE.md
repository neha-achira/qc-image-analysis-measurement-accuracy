# Stage 16 — Leica Backward Trace Investigation

**Status:** Analysis complete. No production code modified. No commits created.
**Branch:** `stage16-leica-backward-trace`
**Scope:** Cartridge 48, Tags 5 and 7 only. All other cartridges/tags out of scope.

---

## 0. A Necessary Limitation, Stated Up Front

Stage 15 established that no Leica pixel coordinate exists anywhere in the provided reference data (`48_holes.png`, `image.png`) — only diameters, in a tag-labeled table, and a separate, non-correspondable annotated crop. Several requested quantities in this stage's brief — "distance from Leica hole," "error from Leica hole" — require a Leica pixel centre that does not exist in this project. Per your standing instruction not to invent Leica coordinates, **these quantities are reported as "not computable from available data"** everywhere they arise, rather than estimated. Where the brief's intent can still be served without inventing a coordinate — e.g., whether a stage's search window could ever have reached the region at all, or what the nearest real detection is — that evidence is reported instead, clearly labeled as a proxy, not a substitute.

Everything else requested (chosen anchor, predicted positions, search windows, candidates considered at each stage, reachability, and the classification of the first irreversible decision) is answered directly from the production pipeline's own committed logic, replayed exactly and read-only.

---

## 1–2. Locating the Leica-Visible Holes / Where Production Predicts Them

Stage 15 confirmed Tags 5 and 7 are real, passing holes (Leica: 0.52mm each) present in the same `Holes_ch00.png` file production processes. Their exact pixel centres are unknown (see §0). What follows traces where production's own pipeline looks for them, and why it never finds them.

**Cartridge 48 image shape:** 4926 (h) × 12387 (w) px. **Total raw Hough candidates detected in the whole image: 25.**

### Stage 1 — Anchor Selection

The committed role-generalized Stage 1 logic (`detect_features.py`, from the Stage 7 change) tries every one of the 25 raw candidates against every one of the 7 tag roles, and keeps whichever (candidate, role) pairing yields the highest-scoring anchor (most roles matched, then fallback-quality, then near-nominal ratio, then total distance, then a role-9 tiebreak).

**Winning pairing:** the raw candidate at `(224, 568)` — quality `n_hit=18/36`, `near_ratio=0.250`, `fallback_mode=normal` — interpreted as **Tag 1**. This yields:

**Chosen anchor (Tag-9-role reference point): `(6315, 2032)`**

This is not itself a detected candidate — it is a hypothesized coordinate, computed by subtracting Tag 1's reference offset from candidate `(224,568)`'s position. Every tag's predicted position for the rest of the pipeline is `anchor + REF_OFFSETS[tag]`, fixed at this point.

**This anchor choice is itself a symptom, not a free error.** Cartridge 48 has no candidate anywhere with strong quality: the best of the 5 candidates the anchor goes on to match is `near_ratio=0.389` (Tag 4), and 3 of the 5 matched tags carry `fallback_mode=total_failure`. Stage 1 is choosing the *best available* hypothesis from a candidate pool that contains no high-confidence member at all — a fact independently established in Stages 7, 9, 10, and 14.

### Predicted positions from this anchor

| Tag | Ref. offset magnitude (px) | Predicted position | Assigned position (if any) | Residual |
|---|---|---|---|---|
| 1 | 6264 | (224, 568) | (512, 564) | 288.0px |
| 3 | 5801 | (641, 3237) | (636, 2684) | 553.0px |
| 4 | 4409 | (2048, 924) | (2536, 988) | 492.2px |
| 6 | 3303 | (3013, 1960) | (3028, 1820) | 140.8px |
| **5** | **5688** | **(1923, 5628)** | **— none —** | — |
| **7** | **3236** | **(3344, 3314)** | **— none —** | — |
| 9 (anchor) | 0 | (6315, 2032) | (6296, 2356) | 324.6px |

**Pearson correlation between reference-offset magnitude and residual, across the 5 matched tags: r = 0.323** — a weak, not-strong positive relationship. If the anchor's error were a clean scale/rotation drift (error growing linearly with distance from the anchor), this correlation would be much closer to 1. It is not. Most tellingly, **Tag 9 itself — at zero reference-offset magnitude, i.e., the anchor's own defining point — already carries a 324.6px residual** between the hypothesized anchor coordinate and the nearest real candidate matched to that role. This shows the geometric error here is present and large even at zero range; it is dominated by which specific low-quality candidates happen to exist, not by a distance-proportional drift mechanism.

---

## 3. Stage-by-Stage Candidate Trace

### Tag 5

**Stage 1 predicted position:** `(1923, 5628)`. **This point falls 702px below the image's actual bottom edge** (image height = 4926px) — a hard geometric fact given the fixed anchor and offset, not a candidate-search outcome.

**Nearest raw Hough candidates overall, regardless of distance** (closest 5 of 25):

| Position | Distance | n_hit | near_ratio | Fallback |
|---|---|---|---|---|
| (2644,3896) | 1876.1px | 1/36 | 0.000 | total_failure |
| (2152,2428) | 3208.2px | 7/36 | 0.000 | total_failure |
| (636,2684) | 3213.0px | 3/36 | 0.000 | total_failure (this is the candidate assigned to Tag 3) |
| (3804,2148) | 3955.8px | 35/36 | 0.306 | normal |
| (3028,1820) | 3965.1px | 6/36 | 0.000 | total_failure (assigned to Tag 6) |

Even the nearest candidate at all is 1876px away and is almost certainly noise (`n_hit=1/36`). **No candidate exists anywhere in the image close enough to Tag 5's predicted position to be a plausible detection at any tolerance this project has evaluated as safe.**

**Stage 2 search window (±600px):** **zero** candidates inside. Tag 5 is absent from both `matched_s1` and `matched_s2`.

**Stage 6 recovery window (±690px, gated on in-bounds + quality):** the recovery pass's own bounds check (`px/py` must fall within `[-600, dim+600]`) **fails** — the predicted position is outside even that generous margin. Recovery never evaluates any candidate for Tag 5; it exits at the bounds gate before the distance/quality checks run at all.

### Tag 7

**Stage 1 predicted position:** `(3344, 3314)` — **within image bounds.**

**Nearest raw Hough candidates overall** (closest 5 of 25):

| Position | Distance | n_hit | near_ratio | Fallback |
|---|---|---|---|---|
| (2644,3896) | 910.3px | 1/36 | 0.000 | total_failure |
| (3804,2148) | 1253.5px | 35/36 | 0.306 | normal |
| (2152,2428) | 1485.2px | 7/36 | 0.000 | total_failure |
| (3028,1820) | 1527.1px | 6/36 | 0.000 | total_failure (assigned to Tag 6) |
| (4552,1972) | 1805.6px | 26/36 | 0.167 | normal |

**A notable, disclosed-but-unconfirmed observation:** `(3804,2148)` is a genuinely high-quality raw detection (`n_hit=35/36`, `angular_gap=20°`, `fallback=normal`) — comparable in quality to several already-assigned tags elsewhere in the dataset. It sits 1253.5px from Tag 7's prediction, roughly 1.8× beyond even the recovery tolerance. Checking it against every one of Cartridge 48's 7 predicted positions under this anchor, it is actually closer to **Tag 6's** prediction (813.0px) than to Tag 7's — and Tag 6 is already filled by a much better-fitting candidate (140.8px residual). **This candidate is not confirmed to be Tag 7's genuine hole** — its nearest geometric association is with a different, already-resolved tag — but its existence proves the failure here is not a total absence of real detections; it is that no real detection lines up with the predicted geometry closely enough, at any of the tolerances already validated as safe.

**Stage 2 search window (±600px):** **zero** candidates inside. Tag 7 is absent from both `matched_s1` and `matched_s2`.

**Stage 6 recovery window (±690px):** the bounds gate **passes** (prediction is in-frame), but **zero** candidates fall within 690px. Recovery reaches the distance check for Tag 7 and finds nothing to recover.

---

## 4. First Irreversible Decision

The first, and only, irreversible decision in this trace is **Stage 1's anchor selection** — the single choice of candidate `(224,568)` interpreted as Tag 1's role, fixing the anchor at `(6315,2032)` and therefore fixing every subsequent predicted position for all 7 tags before Stage 2 or Stage 6 ever run. Neither Stage 2 (candidate substitution within ±600px of an already-fixed prediction) nor Stage 6 (recovery within ±690px of the same fixed prediction) has any mechanism to revisit or correct the anchor — a fact already established architecturally in Stages 9, 10, and 14, and confirmed again here by direct code inspection of `role_generalized_stage1`, `run_stage2`, and `run_recovery`.

**Classification: A. Anchor localization error.**

This is the correct single classification (not B) because the residual pattern across the 5 tags that do get matched shows only a weak correlation (r=0.323) with distance from the anchor — inconsistent with a systematic translation/scale drift that compounds with range. It is instead consistent with an anchor pinned from the best of a pool of uniformly weak candidates, where positional noise is present even at the anchor's own defining point (Tag 9's 324.6px residual at zero offset).

Downstream of that first decision, **D — fixed search-window limitation — is the proximate mechanism that finally blocks recovery**: for Tag 5, the anchor error is large enough to push the prediction physically outside the frame, so no search radius could help. For Tag 7, the anchor error leaves the prediction in-frame, but 1253px away from the nearest plausible real detection — beyond both the 600px and 690px windows this project has validated as safe to use. D is the last blocking gate, but it is a consequence of A, not an independent cause.

---

## 5. Accumulated Error Table

| Stage | Predicted position (Tag5 / Tag7) | Error from Leica hole | Search radius | Leica hole reachable? |
|---|---|---|---|---|
| Stage 1 (anchor) | (1923,5628) / (3344,3314) | **Not computable** — no Leica pixel centre available (§0) | n/a (anchor derivation, not a search) | n/a |
| Stage 2 | same, unchanged | Not computable | ±600px | **No** (Tag5: 0 candidates in window, position already out of frame; Tag7: 0 candidates in window) |
| Stage 6 (recovery) | same, unchanged | Not computable | ±690px, gated on in-bounds | **No** (Tag5: fails bounds gate before search; Tag7: passes gate, 0 candidates within radius) |

The predicted position is identical across all three rows because only Stage 1 sets the anchor; Stage 2 and Stage 6 search around that same fixed point with progressively (barely) larger radii. No stage in the current architecture ever changes the predicted position itself.

**Proxy evidence in place of the uncomputable "error from Leica hole" column:** the nearest real detection to Tag 5's prediction is 1876px away; to Tag 7's prediction, 910px away (though not a confirmed hole in either case, per §3). These distances, however interpreted, are far beyond both search radii ever applied — meaning the answer to "reachable?" does not depend on the exact, unknown Leica coordinate: even the closest real candidate available anywhere in the image is out of reach of the windows used.

---

## 6. Fundamental Cause

Per the four options posed: the failure is fundamentally caused by **an interaction of multiple stages, originating in an incorrect anchor**. Specifically:

1. **Incorrect anchor** (root cause): Stage 1 is forced to pin the whole cartridge's geometry from a pool containing no high-confidence candidate, producing an anchor with baked-in positional error large enough (324.6px even at zero range) to misplace every downstream prediction.
2. **Search-window size** (proximate, final blocker): given that anchor error, the fixed 600px/690px windows are not wide enough to reach either the out-of-frame Tag 5 prediction or the nearest plausible detection near Tag 7.
3. **Incorrect geometric prediction** is not a distinct third cause here — it is the direct arithmetic consequence of (1); `REF_OFFSETS` were independently validated as correct in Stage 10, so the prediction error stems from the anchor input, not from the offset table itself.

No single stage in isolation is "the" failure — Stage 1 supplies a necessarily imprecise anchor because the image offers nothing better, and Stages 2/6 then apply fixed-radius searches that were sized for the dataset's normal (near-1.0 confidence) case, not for a cartridge where the anchor itself carries several hundred pixels of built-in slack.

---

## Summary

The first irreversible algorithmic decision that makes Cartridge 48's Leica-confirmed Tag 5 and Tag 7 holes unreachable is Stage 1's anchor selection (classification **A**), which is forced to rely on Cartridge 48's best-available — but still low-confidence — candidate because no stronger candidate exists anywhere in this cartridge. That single decision fixes both tags' predicted positions before Stage 2 or Stage 6 ever run; the fixed 600px/690px search windows applied afterward (classification **D**) are the final, proximate reason recovery fails, but they are a consequence of the anchor error, not an independent cause. Tag 5's predicted position ends up entirely outside the captured frame; Tag 7's remains in-frame but far beyond reach of every candidate this investigation could find, including one high-quality but geometrically unrelated detection.

This report proposes no fix and recommends no redesign, per your instruction. It establishes only the causal chain requested.

No production code was modified during this investigation. No commits were created. Stopping here per your instruction.
