# Stage 7 — Blast-Radius Analysis: Role-Generalized Stage 1 Anchor Search

**Status:** Analysis complete. No production code modified. The proposed algorithm has not been implemented — it was run only inside a standalone, read-only analysis script.
**Branch:** `stage7-geometric-model-investigation` (no commits).
**Basis:** `STAGE7_ANCHOR_SELECTION_REDESIGN.md`, Approach 5 ("Hybrid") — role-generalized anchor trial + quality/residual tie-break.

---

## 1. Method

For all 79 validated cartridges (1–33, 34–50, 51–60, 61–70(1), 71–79), both algorithms were run back-to-back in one script, each carried through the same, faithfully-replicated Stage 2 ranking refinement and recovery pass, so the comparison reflects final downstream assignments, not just raw Stage 1 match counts:

- **Current algorithm:** try each raw candidate only as a hypothetical Tag 9 (today's committed logic, reproduced exactly).
- **Proposed algorithm:** try each raw candidate against each of the 7 tag roles; tie-break by (anchor candidate's own `fallback_mode`, then `near_nominal_ratio`, then lowest total residual distance across the matched set, then role = 9 preferred last).

**A bug was found and is disclosed here rather than silently fixed:** the "role = 9 preferred last" tie-break was implemented backwards in this analysis script (it actually preferred non-9 roles on an exact tie). This is flagged transparently because it affects how the results below should be read — see §3.

For each cartridge, both pipelines' final matched candidate positions (post Stage 2, post recovery pass) were compared tag-by-tag, and diameter/PASS-FAIL was additionally computed for every tag whose assigned candidate changed.

---

## 2. Headline Results

| Category | Count |
|---|---|
| Cartridges with **identical** final assignments (every tag, same candidate, same measurements) | **74 / 79** |
| Cartridges with **changed** assignments | **5 / 79** |

The 74 identical cartridges break down as: 1–33: 32/33, 34–50: 15/17, 51–60: 10/10, 61–70(1): 9/10, 71–79: 8/9 — i.e. every cartridge *except* the 5 discussed below.

**None of the 74 identical cartridges show any change to a matched-tag position, diameter, or PASS/FAIL outcome.** This is the primary regression-safety evidence this analysis was designed to produce.

---

## 3. A Note on Anchor-Value Churn (not a regression)

Of the 74 cartridges with identical final assignments, 71 nonetheless show a *different literal anchor coordinate* between current and proposed. This sounds alarming in isolation but is explained, not concerning, once examined: with a 600px match tolerance and typical real-hole position noise of only a few to ~11px (established in the geometric-model investigation), **many different genuine, high-quality candidates — each tried under a different assumed role — independently arrive at nearly the same implied anchor position**, and all of them go on to match the identical set of real candidates. The specific candidate/role pair that "wins" the tie-break is close to arbitrary among these equally-valid options (compounded by the tie-break bug noted above), but the practical output — which real candidate ends up assigned to which tag, and what it measures — is unaffected. This was confirmed directly: all 74 cartridges' final tag-by-tag positions and measurements are byte-identical regardless of which literal anchor value won.

**This should be re-verified after the tie-break bug is fixed**, as a required follow-up before implementation (see §6), but is not expected to change this conclusion, since the underlying cause (tolerance absorbing small inter-candidate position differences) is independent of the specific tie-break bug.

---

## 4. The 5 Changed Cartridges — Detailed Comparison

### 1-33 / Cartridge 18 — Clear Improvement

| Tag | Current | Proposed |
|---|---|---|
| 4 | (2292,572) — n_hit 24/36, near-ratio 52.8%, gap 80° | (2416,1036) — **n_hit 36/36, near-ratio 100%, gap 10°** |

Diameter: 0.4650mm (PASS) → 0.4725mm (PASS). No PASS/FAIL change; the proposed candidate is unambiguously the higher-quality, more trustworthy detection (perfect ray-cast profile vs. a moderate one). **Classification: improved.**

### 71-79 / Cartridge 72 — Major Improvement, With One New Minor Concern

All 6 genuine holes (Tags 1,3,4,5,6,7) are now correctly and precisely matched — Tags 1,3,4,5 newly recovered (all 36/36 quality, exactly matching the independently-established ground truth from the prior verification report), and Tags 6 and 7's previous misidentifications (Tag 6 showing Tag 3's hole; Tag 7 showing a low-quality substitute) are both corrected to their own genuine, perfect-quality holes. **Classification: major improvement, fully consistent with prior findings.**

One new issue: **Tag 9 is now matched** to (6052,1400) — a moderate-quality candidate (19/36 hits, 36.1% near-ratio, 100° gap), diameter 0.5250mm (PASS). This is *not* the confirmed genuine Tag 9 feature (established in the geometric-model report to be an oversized, non-circular feature no Hough candidate corresponds to); it is a different, likely-spurious nearby candidate that happens to fall within the wider implied-anchor's tolerance. This is a smaller, more contained problem than today's — it no longer corrupts the other 6 tags — but it does mean Tag 9 is reported as a false PASS rather than the more honest `not_detected`. **Classification: net improvement, with a new minor false-positive risk isolated to Tag 9 that should be addressed (see §6) before implementation.**

### 34-50 / Cartridge 48 — Ambiguous, Requires Visual Review

| Tag | Current | Proposed | Note |
|---|---|---|---|
| 1 | unmatched | (512,564), n_hit 20/36, near-ratio 33% | weak evidence either way |
| 3 | unmatched | (636,2684), **n_hit 3/36, total_failure** | very likely a false positive |
| 4 | (1060,676), n_hit 2/36, total_failure | (2536,988), n_hit 28/36, near-ratio 39% | improved |
| 6 | (2152,2428), n_hit 7/36, total_failure | (3028,1820), n_hit 6/36, total_failure | lateral (both poor) |
| 7 | (2644,3896), n_hit 1/36, total_failure | unmatched | arguably improved (a near-noise match is now correctly withheld) |
| 9 | (5416,2148), n_hit 16/36, near-ratio 28% | (6296,2356), **n_hit 3/36, total_failure** | **quality regression** |

Diameter for Tag 9: 0.5225mm (PASS) → 0.5000mm (PASS) — no PASS/FAIL flip, but the underlying candidate's quality drops sharply (a reasonably-detected candidate replaced by one that is essentially noise). Combined with the population-scan finding (already on record) that Cartridge 48 belongs to a cluster with a *different* failure mode from Cartridge 72 (broad image-quality degradation, not a single false anchor), this cartridge's overall candidate pool is poor across the board. **Classification: ambiguous — some tags improve, Tag 9 specifically degrades in underlying quality even though its PASS/FAIL doesn't flip. Requires visual review before this cartridge's outcome under the new algorithm can be trusted.**

### 34-50 / Cartridge 49 — Ambiguous, Requires Visual Review

| Tag | Current | Proposed | Note |
|---|---|---|---|
| 1 | unmatched | (9012,484), n_hit 17/36, near-ratio 39% | weak |
| 3 | unmatched | (9656,2980), n_hit 21/36, near-ratio 50% | moderate |
| 4 | unmatched | (10660,1744), **n_hit 3/36, total_failure** | very likely false positive |
| 6 | unmatched | (11968,2292), **n_hit 36/36, near-ratio 100%** | strong candidate |
| 9 | (392,1956), **n_hit 36/36, near-ratio 100%**, PASS (0.5125mm) | unmatched | **a previously good, PASS-reported measurement is now dropped** |

The critical finding here: this cartridge contains **two separate, mutually-inconsistent perfect-quality (36/36) candidates** — (392,1956), which the current algorithm anchors on, and (11968,2292), which the proposed algorithm anchors on instead — and they cannot both be correct under the same single geometric model (each is a strong candidate individually, but the proposed anchor's own hypothesis does not also match the other one). This is consistent with the population scan's separate, already-documented finding that Cartridge 49 exhibits a fundamentally different — and still not fully understood — geometric situation from Cartridge 72's clean single-anchor failure. **Classification: ambiguous, highest uncertainty of the 5 changed cartridges. A previously good (36/36, PASS) measurement is lost with nothing to replace it. Requires visual review, and likely requires the separate, dedicated investigation into the 45/48/49/50 cluster recommended in the geometric-model report, rather than being resolved as a side effect of this anchor redesign.**

### 61-70(1) / Cartridge 66 — Regression Concern (highest priority for review)

| Tag | Current | Proposed |
|---|---|---|
| 9 | (5812,2392) — n_hit 20/36, near-ratio 44.4%, gap 130° — **diameter 0.5525mm, FAIL** | (6324,2332) — **n_hit 9/36, near-ratio 13.9%**, gap 120° — **diameter 0.5200mm, PASS** |

This is the one concrete, unambiguous regression risk found in this analysis: **the proposed algorithm flips Tag 9 from FAIL to PASS**, using a candidate with markedly *worse* ray-cast quality (fewer than half the hit count, less than a third the near-nominal ratio) than the current candidate. The current FAIL is itself borderline (0.5525mm against a 0.55mm ceiling — fails by only 0.0025mm), and Stage 5 previously flagged this same cartridge (a different tag, Tag 6) as a borderline case pending independent Leica reference data — so there is already a documented history of this specific cartridge's measurements being close to the decision boundary. Changing a boundary-line FAIL to a PASS on the strength of a *lower*-quality candidate is not something this analysis can certify as safe. **Classification: regression concern. Must not go forward for this cartridge without visual review and, ideally, independent reference measurement, exactly as Stage 5 already recommended for this cartridge's other borderline tag.**

---

## 5. Summary Table

| Cartridge | Current matched | Proposed matched | Classification |
|---|---|---|---|
| 74 others | — | — | **Identical — safe** |
| 1-33/18 | 7/7 | 7/7 | **Improved** (Tag 4 quality) |
| 71-79/72 | 3/7 | 7/7 | **Major improvement** + 1 new minor concern (Tag 9) |
| 34-50/48 | 4/7 | 5/7 | **Ambiguous** — requires visual review |
| 34-50/49 | 1/7 | 4/7 | **Ambiguous** — requires visual review, highest uncertainty |
| 61-70(1)/66 | 7/7 (Tag9 FAIL) | 7/7 (Tag9 PASS) | **Regression concern** — requires visual review before proceeding |

---

## 6. Go/No-Go Recommendation

**Conditional go — not an unconditional rollout.**

The evidence strongly supports the core hypothesis of the redesign: for the overwhelming majority of validated cartridges (74/79, including all of 51–60, 61–70(1) minus one, and the large majority of 1–33 and 34–50), the role-generalized search produces **byte-identical** downstream measurements and PASS/FAIL to today's algorithm — the widened search space does not disturb already-correct behavior. Cartridge 72's result matches this investigation's independently-established ground truth almost exactly, and Cartridge 18 shows a clean, well-evidenced quality improvement.

However, this analysis also surfaced exactly the kind of concrete, specific risk this process exists to catch, and it should not be waved through:

1. **Fix the disclosed tie-break bug** (role = 9 was preferred *last* instead of first) and re-run this same comparison to confirm the 74-identical / 5-changed split is unaffected by the fix.
2. **Visually review Cartridge 66 before any implementation decision.** This is the one case where a QC PASS/FAIL outcome flips, and it flips toward PASS using weaker evidence than today's (already-borderline) result — the highest-priority item in this entire analysis.
3. **Visually review Cartridges 48 and 49.** Both belong to the already-separately-flagged 45/48/49/50 cluster with a distinct, not-yet-understood failure mode; this redesign's effect on them is genuinely mixed (some tags improve, some degrade, one previously-good measurement in Cartridge 49 is lost outright) and should not be resolved as a side effect of the Stage 1 anchor change alone.
4. **Address Cartridge 72's new Tag 9 false-match before implementation**, not after. This is a good opportunity to fold in Approach 4's residual/quality reasoning from the design document — e.g., requiring a newly-added match to meet a minimum quality bar (as the Stage 6 recovery pass already does), rather than accepting any match that merely raises the raw count — so that Cartridge 72's real improvement (6 correctly-identified tags) is not accompanied by a new, if minor, false positive on the 7th.

**Recommendation:** proceed with the redesign in principle — the evidence for the 74 unaffected cartridges and the two clear improvements (18, 72's core 6-tag recovery) is strong — but treat items 1–4 above as required preconditions, not optional follow-ups, before implementing. Do not implement as currently specified while Cartridge 66's regression is unresolved.

No production code was modified in the course of this analysis.
