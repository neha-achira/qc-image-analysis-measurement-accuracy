# Stage 7 — Cartridge 72 Independent Verification Report

**Status:** Verification complete. No fixes proposed or implemented; no production code modified.
**Branch:** `stage7-geometric-model-investigation` (no commits; read-only re-derivation, independent of the prior trace script).
**Purpose:** independently re-verify the claims made in `STAGE7_CARTRIDGE72_ROOT_CAUSE_TRACE.md` — that Cartridge 72 has an incorrect Stage 1 anchor, that Tag 6 is reported using Tag 3's genuine hole, and that Tag 7's genuine hole is unassigned — using a fresh re-derivation of the "correct" anchor (re-identifying the perfect-quality candidates from scratch and re-fitting the similarity transform, rather than reusing saved numbers from the prior session).

**Note on method integrity:** the first run of this verification's similarity-transform fit contained a bug (missing `/len(src)` normalization before the SVD), which produced an implausible scale of 5.98 instead of ~1.0. This was caught by cross-checking against the expected magnitude before accepting any result, the bug was fixed, and the script was re-run. All numbers below are from the corrected run. This is disclosed because the verification's credibility depends on the fitting procedure being correct, not merely on it having been run.

---

## 1. Annotated Composite Image

`validation_output/stage7_geometry/cart72_verification_composite.png`

Shows, on a single downsampled canvas padded to include off-frame predictions:
- **Orange circles** — all 24 raw Hough candidates, labeled C0–C23.
- **Green circles** — the 6 independently-verified genuine holes (Tags 1,3,4,5,6,7).
- **Red X** — Stage 1's selected (wrong) anchor, at (4836, 3412).
- **Magenta X** — the correct/fitted anchor, at (6729.7, 1799.9) — not a raw Hough candidate; no detection exists there.
- **Small red +** — predicted position for each of the 7 tags under the wrong (Stage-1-selected) anchor.
- **Small green +** — predicted position for each of the 7 tags under the correct (fitted) anchor.
- **Yellow circles** — production's final reported assignment for each matched tag (Tag 6, Tag 7, Tag 9).

Visual confirmation: every small green "+" (correct-anchor prediction) lands essentially exactly on a green genuine-hole circle. Every small red "+" (wrong-anchor prediction) for Tags 1, 3, 5 lands in the black padding area entirely outside the actual cartridge image — visually confirming these predictions are off-frame nonsense, not just numerically. The yellow "PROD:Tag6" circle visibly coincides with the green "genuine Tag3" circle, not with Tag 6's own genuine hole (visible separately, unlabeled by production, at the top of the frame). The yellow "PROD:Tag7" circle sits on its own distinct spot near, but visibly separate from, the green "genuine Tag5" circle — and nowhere near Tag 7's own genuine hole.

---

## 2. Full Per-Candidate Table (all 24 raw Hough candidates)

| Candidate | x | y | n_hit | near_nominal_ratio | angular_gap | fallback_mode | assigned_tag | better identity match? |
|---|---|---|---|---|---|---|---|---|
| C0 | 2456 | 756 | 36 | 1.000 | 10.0° | normal | — | **Yes — Tag4** (fit residual 7.6px) |
| C1 | 3440 | 1760 | 36 | 1.000 | 10.0° | normal | — | **Yes — Tag6** (fit residual 11.3px) |
| C2 | 644 | 416 | 36 | 1.000 | 10.0° | normal | — | **Yes — Tag1** (fit residual 7.5px) |
| C3 | 3780 | 3116 | 36 | 1.000 | 10.0° | normal | — | **Yes — Tag7** (fit residual 3.5px) |
| C4 | 1084 | 3080 | 36 | 1.000 | 10.0° | normal | **6** | **Yes — Tag3** (fit residual 6.3px) — currently mislabeled as Tag 6 |
| C5 | 4092 | 5864 | 15 | 0.306 | 130.0° | normal | — | No (nearest fit Tag5, 1747px away — too far) |
| C6 | 2396 | 5444 | 36 | 1.000 | 10.0° | normal | — | **Yes — Tag5** (fit residual 1.7px) |
| C7 | 2144 | 5072 | 15 | 0.222 | 150.0° | normal | **7** | No clean fit (nearest is Tag5, 448px away — too far to be that tag's hole either) |
| C8 | 5816 | 4940 | 17 | 0.306 | 170.0° | normal | — | No (nearest fit Tag7, 2731px away) |
| C9 | 4528 | 1256 | 8 | 0.000 | 170.0° | total_failure | — | No (nearest fit Tag6, 1207px away) |
| C10 | 6052 | 1400 | 19 | 0.361 | 100.0° | normal | — | No (nearest fit Tag9, 787px away) |
| C11 | 4664 | 4760 | 11 | 0.139 | 140.0° | normal | — | No (nearest fit Tag7, 1865px away) |
| C12 | 5748 | 1012 | 8 | 0.000 | 200.0° | total_failure | — | No (nearest fit Tag9, 1259px away) |
| C13 | 4444 | 812 | 12 | 0.167 | 120.0° | normal | — | No (nearest fit Tag6, 1391px away) |
| C14 | 5900 | 2516 | 21 | 0.306 | 90.0° | normal | — | No (nearest fit Tag9, 1096px away) |
| C15 | 5500 | 5756 | 3 | 0.000 | 280.0° | total_failure | — | No (nearest fit Tag5, 3120px away) |
| C16 | 3700 | 5228 | 9 | 0.139 | 270.0° | normal | — | No (nearest fit Tag5, 1321px away) |
| C17 | 5196 | 472 | 29 | 0.528 | 30.0° | normal | — | No (nearest fit Tag9, 2029px away) |
| C18 | 4836 | 3412 | 9 | 0.111 | 280.0° | normal | **9** | No clean fit (nearest is Tag7, 1093px away — this candidate does not fit any tag position under the correct model; it is the Stage 1 anchor itself, currently mislabeled as genuine Tag 9) |
| C19 | 7072 | 1256 | 17 | 0.417 | 150.0° | normal | — | No (nearest fit Tag9, **643px** away — this is the closest any real candidate comes to the true Tag9 position, but still far too imprecise to serve as that hole) |
| C20 | 4156 | 4932 | 20 | 0.028 | 110.0° | normal | — | No (nearest fit Tag5, 1832px away) |
| C21 | 5000 | 5028 | 33 | 0.861 | 40.0° | normal | — | No (nearest fit Tag7, 2266px away) |
| C22 | 6272 | 1168 | 4 | 0.000 | 240.0° | total_failure | — | No (nearest fit Tag9, 780px away) |
| C23 | 320 | 5488 | 19 | 0.000 | 100.0° | off_nominal_fallback | — | No (nearest fit Tag5, 2077px away) |

"Better identity match" is computed independently of production: for each candidate, the nearest of the 7 tag positions predicted by the re-derived correct-anchor fit (scale=0.9973, rotation=−0.738°, RMS 1.7–11.3px across the 6 genuine tags) is reported, with a 100px acceptance threshold given the fit's demonstrated precision. Six candidates (C0, C1, C2, C3, C4, C6) pass this threshold cleanly and correspond exactly to Tags 4, 6, 1, 7, 3, 5 respectively — matching the genuine-hole identification already established. All other 18 candidates, including both of production's other "matched" candidates (C7 for Tag7, C18 for Tag9), do not fit any tag position within 100px — they are not anyone's genuine hole under this model.

---

## 3. Verification: No Genuine Hole Assigned to More Than One Tag, No Tag Shares a Candidate

**Confirmed, but with an important qualification.**

- In production's actual final output, exactly 3 tags are matched (6, 7, 9), to 3 distinct candidate positions ((1084,3080), (2144,5072), (4836,3412)) — no duplication exists in what is currently reported. This was checked both by position and by Python object identity (the `used_ids` set is keyed by `id()`), confirming the code's anti-duplicate mechanism itself is working correctly — no bug was found in the duplicate-prevention logic.
- **However, this absence of duplication is not evidence of correctness.** It holds only because Tag 3 (the tag that actually owns candidate C4) was never evaluated successfully — its own predicted position (under the wrong anchor) fell outside the image, so it never got the chance to claim C4 for itself, leaving Tag 6 free to claim it instead. Had Tag 3's predicted position also happened to fall in-bounds, a genuine conflict *would* have been directly observable (two tags both wanting C4). As it stands, the conflict is present in substance (one physical hole, two REF_OFFSETS identities that both geometrically fit it far better than the current label) but not in the code's literal duplicate-tracking sense.

---

## 4. Verification: Does Tag 6 Truly Use Tag 3's Candidate?

**Confirmed. This is not an interpretation error.**

- Production's Tag 6 is reported at exactly (1084, 3080).
- The independently re-derived genuine Tag 3 hole (found via a from-scratch re-identification of perfect-quality candidates and a from-scratch brute-force shape match, not reused from the prior session) is also exactly (1084, 3080). The two values are identical to the pixel, not merely close.
- Separately and more tellingly: computing where Tag 6 *should* be under the correct anchor gives (3436.0, 1770.6). The nearest real raw candidate to that position is **C1 at (3440, 1760) — only 11.3px away**, itself a perfect-quality (36/36, 10° gap) detection. This is Tag 6's actual genuine hole, and it is currently **completely unclaimed** by production (its `assigned_tag` in the table above is blank). Production's Tag 6 slot instead points at a hole 2691.9px away from where Tag 6 should be — which is exactly where Tag 3 should be.

This is as direct a confirmation as is available without ground-truth engineering markings on the physical part: two independent methods (exact pixel-position match, and correct-anchor re-prediction distance) agree that production's "Tag 6" is physically Tag 3's hole, and Tag 6's own hole sits nearby, fully detected, unused.

---

## 5. Verification: Is Tag 7's Genuine Hole Completely Unassigned?

**Confirmed.**

- The independently re-derived genuine Tag 7 hole is C3 at (3780, 3116) (fit residual 3.5px — the second-best fit of all six genuine holes).
- Checking this exact position against the set of all candidate positions production has claimed for any tag (`{(1084,3080), (2144,5072), (4836,3412)}`): **(3780, 3116) is not among them.**
- Production's actual Tag 7 is C7 at (2144, 5072) — a separate, lower-quality candidate (15/36 hits, 22.2% near-nominal, 150° angular gap) that does not correspond to any of the 6 genuine holes at all (per the candidate table, its nearest fit under the correct model is still 448px away — too far to be Tag 5's hole either, the nearest genuine position to it).

So: Tag 7's real hole (C3) is fully detected, perfect quality, and entirely unused by the current pipeline output — consistent with the root-cause trace's finding.

---

## 6. Summary of Verified Findings

| Claim from the prior root-cause trace | Verification result |
|---|---|
| Stage 1 selected the wrong anchor | **Confirmed** — (4836,3412), fit residual to any tag position exceeds 1000px under the correct model; this candidate does not correspond to any genuine hole |
| A correct anchor exists nearby, unrecoverable from raw Hough output | **Confirmed** — fitted position (6729.7, 1799.9); nearest real candidate (C19) is 643px away, itself low precision (17/36 hits) |
| Tag 6 is reported using Tag 3's genuine hole | **Confirmed, exact pixel match** — not an interpretation error |
| Tag 6's own genuine hole exists and is unclaimed | **Confirmed** — C1, 36/36 quality, 11.3px from its correct predicted position |
| Tag 7's genuine hole is completely unassigned | **Confirmed** — C3, 36/36 quality, 3.5px fit residual, not among any tag's claimed candidates |
| No literal duplicate-candidate bug exists in the matching code | **Confirmed** — but only because Tag 3 never got a chance to compete for its own hole, not because the underlying identity conflict was correctly resolved |

No fix is proposed here. No production code was modified during this verification.
