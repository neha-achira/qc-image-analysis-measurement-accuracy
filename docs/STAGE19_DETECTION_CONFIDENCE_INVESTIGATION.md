# Stage 19 — Detection Confidence Investigation

**Status:** Analysis complete. No production code modified. No commits created.
**Branch:** `stage19-detection-confidence-investigation`
**Objective:** design a 0–100% confidence score for every detected hole, built entirely from information the production pipeline already computes, without changing any measurement or PASS/FAIL decision.

**Data note:** the per-tag metric population analyzed below (541 matched tag-slots across all 79 validated cartridges) is the same population gathered by replaying the real, unmodified production functions (`build_candidates`, `_subpixel_diameter`, the role-generalized anchor search) earlier in this investigation (Stage 14). No new data collection, dataset search, or filesystem exploration was performed for this stage, per your instruction — the existing, already-validated population is reused directly as the "existing validation dataset" referred to throughout this report.

---

## 1. Inventory of Existing Production Metrics

Every candidate metric below is already computed by `detect_features.py` today, for every candidate, before any confidence score is added.

| Metric | Where computed | What it measures | Range | Better direction |
|---|---|---|---|---|
| `fallback_mode` | `_subpixel_diameter`, set at each of three ray-cast outcomes (`detect_features.py` ~150–183, ~888–903, ~1011–1025) | Which of three ray-cast outcomes produced the diameter: `"normal"` (≥1 near-nominal-radius ray hit), `"off_nominal_fallback"` (hits exist but none near the nominal radius), `"total_failure"` (fewer than 4 usable ray hits at all) | Categorical, 3 values | `normal` best, `total_failure` worst |
| `n_hit` | `_subpixel_diameter` debug context (`n_hit = len(radii)`) | Count of the 36 fixed measurement rays that found any edge crossing at all | 0–36 | Larger better |
| `near_nominal_ratio` (near-nominal count / 36) | Derived from `near_nominal_radii`, the subset of ray hits within tolerance of the expected nominal radius | Fraction of rays whose edge crossing is actually consistent with a hole of the expected size (distinguishes "found an edge somewhere" from "found the hole's own boundary") | 0.0–1.0 | Larger better |
| `angular_gap` | `_max_angular_gap`, applied to the same ray hit set (`detect_features.py` ~477) | The largest contiguous angular sector (in degrees) with no ray hit at all — how much of the hole's circumference is completely unsampled | 10°–360° | Smaller better |
| `dist_from_predicted` | Implicit in Stage 2 / recovery-pass matching (`detect_features.py` ~443, ~510) — distance between a candidate and its tag's `REF_OFFSETS`-predicted position | How far the selected candidate sits from where the geometric model expected it | 0px–690px (bounded by whichever tolerance matched it) | Smaller better |
| Stage 2 substitution (`stage2_preview`) | `detect_features.py` ~433–460 | Whether the anchor-round's nearest-distance pick was replaced by a better-ranked candidate within `MATCH_TOL_PX` | Boolean | Substitution itself is neutral — it is evidence the *final* candidate outranks at least one alternative, which is a mild positive signal, not a penalty |
| Recovery-pass usage (`recovery_pass.recovered_tags`) | `detect_features.py` ~462–534 | Whether the tag was left unmatched after Stage 2 and only filled by the wider, quality-gated recovery pass | Boolean | Recovered tags already pass a fixed quality gate (`fallback_mode=="normal"`, `near_nominal_ratio>=0.70`, `angular_gap<=40°`, Stage 6) — informative context, not automatically a penalty |
| Candidate rank / competing candidates | Implicit in the same Stage 2 substitution loop — how many other raw candidates exist within `MATCH_TOL_PX` and how the chosen one ranks among them | Ambiguity of the assignment decision | 0+ competing candidates | Fewer competitors / higher rank better |

`off_nominal_fallback` is a real code path (`detect_features.py` line ~183, ~903, ~1025) but **does not occur even once** in the 541-tag validated population — every matched tag in the entire 79-cartridge dataset is either `normal` (535, 98.9%) or `total_failure` (6, 1.1%). This is disclosed explicitly because it means the confidence design below has no empirical data to calibrate this middle category against; it is handled by an explicit, disclosed default (§4).

Candidate rank / competing-candidate counts and a leave-one-out geometric residual were considered during scoping but are **not** included in the final design: they would require re-deriving per-cartridge raw candidate lists beyond what the existing validated population already recorded, which is outside this stage's scope (design using existing computed information, not new data collection). The Stage 2 substitution and recovery-pass flags are discussed qualitatively in §3 and §6 using the cases where they are already known from prior stages, but are not part of the numeric formula in §4 for the same reason — the reused population does not carry a per-tag substitution/recovery flag, only the five metrics in the table above with a per-tag record.

---

## 2. Metric Distributions Across the Existing Validation Dataset (541 tags, 79 cartridges)

| Metric | Mean | Std | P1 | P5 | P10 | P50 | P90 | P95 | P99 |
|---|---|---|---|---|---|---|---|---|---|
| `near_nominal_ratio` | 0.964 | 0.156 | 0.056 | 0.861 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| `n_hit` | 35.14 | 4.55 | 7.2 | 36 | 36 | 36 | 36 | 36 | 36 |
| `angular_gap` | 15.7° | 33.9° | 10° | 10° | 10° | 10° | 10° | 10° | 176° |
| `dist_from_predicted` | 46.1px | 104.5px | 0px | 0px | 0px | 18.9px | 57.0px | 385.0px | 511.2px |

`fallback_mode`: `normal` 535/541 (98.9%), `total_failure` 6/541 (1.1%).

**The population is extremely concentrated at the "good" end** — the median tag has `near_nominal_ratio=1.0`, `n_hit=36/36`, and a 10° angular gap (the minimum observed, corresponding to full, evenly-spaced ray coverage). This matches Stage 14's finding exactly (this is the same population) and means most of the discriminating power any confidence score can offer comes from the bottom 5–10% of the distribution, not from finely ranking the already-excellent majority.

**Pairwise Pearson correlation among the four continuous metrics:**

| | `near_nominal_ratio` | `n_hit` | `angular_gap` | `dist_from_predicted` |
|---|---|---|---|---|
| `near_nominal_ratio` | — | 0.953 | −0.865 | −0.674 |
| `n_hit` | 0.953 | — | −0.939 | −0.661 |
| `angular_gap` | −0.865 | −0.939 | — | 0.619 |
| `dist_from_predicted` | −0.674 | −0.661 | 0.619 | — |

**This is the single most important quantitative finding of this stage:** `near_nominal_ratio`, `n_hit`, and `angular_gap` are not three independent pieces of evidence — they are three different measurements of essentially **one underlying construct** (ray-cast edge quality), correlated at |r| = 0.865–0.953 with each other. `dist_from_predicted` is a distinct, second factor, correlated with the ray-cast trio at a markedly weaker |r| = 0.619–0.674 — real, but roughly 35–45% independent information rather than a restatement of the same signal. This directly shapes the confidence design in §4: treating all four metrics as separately-weighted, fully independent evidence would substantially over-count the ray-cast signal.

---

## 3. How Metrics Behave for Each Detection Class

| Detection class | Example(s) | `near_nominal_ratio` | `n_hit` | `angular_gap` | `fallback_mode` | `dist_from_predicted` |
|---|---|---|---|---|---|---|
| **Strong detection** | Cartridge 61 (Leica-confirmed control, all 7 tags) | 1.000 | 36/36 | 10° | normal | 0–65px |
| **Weak but currently-passing** | Cartridge 45/Tag3, Cartridge 49/Tag1, Cartridge 50/Tag1 | 0.25–0.53 | 10–21 | 90–170° | normal | 288–592px |
| **Known incorrect (established, Stage 7/17)** | Cartridge 48/Tag1 (FAIL, scratch-based) | 0.333 | 20 | 50° | normal | 288.0px |
| **`total_failure` cases** | Cartridge 48/Tags 3,6,9; Cartridge 45/Tags 1,4; Cartridge 49/Tag4 | 0.000 | 3–7 | 170–360° | total_failure | 141–553px |
| **Recovery-pass detections (Stage 6, verified genuine)** | Cartridge 18/Tags 1,3,5,6,7 | 0.944–1.000 | 36 | 10° | normal | 462–480px |
| **Anchor-corrected detections (Stage 7, verified genuine)** | Cartridge 72/Tags 1,3,4,5,6,7 | 1.000 | 36 | 10° | normal | (moderate-high, see §6) |
| **Known non-hole physical feature (channel junction, Stage 7/8/11)** | Cartridge 66/Tag9, Cartridge 72/Tag9 | 0.139, 0.361 | 9, 19 | 120°, 100° | normal | 430–490px |
| **Leica-disagreement case (Stage 15)** | Cartridge 48/Tag1 (Leica PASS 0.46mm vs. production FAIL 0.4225mm) | 0.333 | 20 | 50° | normal | 288.0px |

Two patterns are already visible before any scoring formula is applied:

1. **`fallback_mode=="total_failure"` perfectly separates the worst cases** — every one of the 6 real occurrences in the entire dataset has `near_nominal_ratio=0.000`, and all cluster in Cartridges 45, 48, and 49 (the same batch already flagged in Stage 2's external validation and Stages 8–17's Cartridge 48/49 investigation).
2. **The two verified-genuine "recovered/corrected" classes (Cartridge 18, Cartridge 72) both show excellent ray-cast metrics but elevated `dist_from_predicted`** (462–592px, close to but under the 690px recovery tolerance) — a real, disclosed tension for the scoring design, discussed in §4 and §6.

---

## 4. Confidence Score Design

### 4.1 Structure

```
ray_quality      = mean( near_nominal_ratio,  n_hit / 36,  angular_uniformity )
angular_uniformity = 1 − min(angular_gap, 180°) / 180°

geometric_consistency = 1 − min(dist_from_predicted, 690px) / 690px

raw_score  = 0.70 × ray_quality + 0.30 × geometric_consistency

fallback_gate = 1.0   if fallback_mode == "normal"
              = 0.5   if fallback_mode == "off_nominal_fallback"   [never observed — disclosed default]
              = 0.0   if fallback_mode == "total_failure"

confidence (%) = 100 × raw_score × fallback_gate
```

### 4.2 Justification for every design choice

- **`ray_quality` averages three metrics instead of weighting them separately**, specifically *because* §2's correlation matrix shows they measure the same underlying construct (|r| = 0.865–0.953). Averaging three repeated measurements of one construct is a standard way to reduce their individual noise without inventing a new weighting scheme; giving each of the three its own large, independent weight would triple-count the same evidence.
- **`angular_uniformity`'s 180° cap** is a heuristic normalization choice, explicitly identified as such: it is geometrically motivated (beyond a half-circle gap, over half the hole's boundary is entirely unsampled, which is already about as uninformative as a measurement can get) but the specific cutoff of 180°, rather than some other value, is a judgment call, not derived from the data.
- **`geometric_consistency`'s 690px normalization reuses `RECOVERY_TOL_PX`**, the production pipeline's own existing tolerance constant (Stage 6) — not a new invented number. A distance at or beyond that bound is already, by the production pipeline's own design, at the edge of what it will accept as a plausible match at all.
- **The 70/30 split between `ray_quality` and `geometric_consistency` is an explicit heuristic**, not a regression-fitted weight. It is directionally justified by two pieces of real evidence: (a) `dist_from_predicted` carries measurably less independent information than the ray-cast trio (§2, |r| ≈ 0.62–0.67, meaning roughly 35–45% independent variance at most), and (b) production's own `_stage2_rank_key` ranks candidates by `(fallback_tier, n_hit, near_nominal_count, −distance)` — i.e., distance is already the *last*, weakest tiebreaker in the pipeline's own existing ranking logic, not a co-equal factor. The 70/30 numbers themselves are a reasonable, disclosed choice consistent with that ordering, not a value derived from a formal statistical fit.
- **The `fallback_mode` gate is multiplicative, not additive**, so that a `total_failure` case is always driven to exactly 0% regardless of any noise elsewhere in the formula — justified because, by definition, `total_failure` means the ray-cast could not produce a reliable diameter measurement at all (fewer than 4 usable ray hits), which should never be reported as some non-zero partial confidence.
- **The `off_nominal_fallback` gate value of 0.5 is an explicit, disclosed default with zero supporting data** — this fallback path exists in the code but never triggers anywhere in the 541-tag validated population, so there is no empirical basis to calibrate it. It is set at the midpoint between the two observed categories as a conservative placeholder, and should be revisited the first time a real case is observed.

No constant in this formula was invented without a stated reason; where a reason is a judgment call rather than a statistical derivation, it is labeled as such above.

---

## 5. Confidence Categories and Recommended Operator Actions

| Category | Range | Recommended operator action |
|---|---|---|
| **High** | ≥ 90% | Trust automatically. No manual action required. |
| **Medium** | 70–89% | Trust the reported PASS/FAIL for normal release decisions, but include in periodic quality-audit sampling rather than full individual sign-off. (Cartridges 18 and 72's verified-genuine recovered/corrected tags fall here — see §6's disclosed limitation before treating "Medium" as a quality concern in itself.) |
| **Low** | 40–69% | Manual visual review recommended before relying on the reported measurement or PASS/FAIL, especially for a reported FAIL (a low-confidence FAIL may itself be wrong, not only a low-confidence PASS). |
| **Very Low** | < 40% | Treat the automated result as provisional only. Manual re-inspection (or, where available, independent Leica measurement per Stage 15) is recommended before any disposition decision. |

The 90/70/40 breakpoints are an operational convention, chosen to produce four clearly-separated, actionable tiers — they are not statistically derived cut points, and this is stated explicitly per your instruction. §6 confirms they produce a sensible split on the real population rather than an arbitrary-looking one.

---

## 6. Full Population Replay

**Verification that measurements and PASS/FAIL are unchanged:** the confidence score is computed purely as a function of `near_nominal_ratio`, `n_hit`, `angular_gap`, `fallback_mode`, and `dist_from_predicted` — every one of these is already recorded by the existing, unmodified production replay used in Stage 14; `diameter_mm` and `pass` are carried through from that same population unmodified. No formula in §4 reads or writes either field. Confidence is a pure addition alongside the existing two outputs, never a replacement for them.

### 6.1 Aggregate result (541 tags)

| Confidence category | Count | % of population |
|---|---|---|
| High (≥90%) | 506 | 93.5% |
| Medium (70–89%) | 13 | 2.4% |
| Low (40–69%) | 9 | 1.7% |
| Very Low (<40%) | 13 | 2.4% |

**Cross-tabulation against the existing PASS/FAIL decision:**

| | High | Medium | Low | Very Low |
|---|---|---|---|---|
| **PASS** (516 total) | 487 | 13 | 5 | 11 |
| **FAIL** (25 total) | 19 | 0 | 4 | 2 |

**6 of the 25 currently-reported FAILs (24%) carry Low or Very Low confidence** — a directly actionable finding: a meaningful fraction of FAIL decisions are themselves reported on weak evidence and should not be treated as automatically correct any more than a low-confidence PASS should.

### 6.2 Targeted investigation: Cartridges 48, 49, 66/Tag9, 72/Tag9

| Cartridge/Tag | Confidence | Category | Measurement | PASS/FAIL | Note |
|---|---|---|---|---|---|
| 48/Tag1 | 55.1% | Low | 0.4225mm | **FAIL** | Established (Stage 7/17) as a scratch/texture detection — correctly flagged Low, and Leica confirms (Stage 15) this FAIL disagrees with Leica's own PASS (0.46mm) |
| 48/Tag3 | 0.0% | Very Low | 0.500mm | PASS | `total_failure` fallback — correctly floored to zero despite a currently-reported PASS |
| 48/Tag4 | 54.0% | Low | 0.510mm | PASS | Flagged Low independently of, and consistent with, Stage 17's separate visual finding that this candidate sits on the rim of an unrelated large disc feature, not a genuine small hole |
| 48/Tag6 | 0.0% | Very Low | 0.500mm | PASS | `total_failure` fallback |
| 48/Tag9 | 0.0% | Very Low | 0.500mm | PASS | `total_failure` fallback |
| 49/Tag1 | 31.9% | Very Low | 0.4725mm | PASS | Low ray-cast quality (`near_nominal_ratio`=0.389) |
| 49/Tag3 | 41.2% | Low | 0.520mm | PASS | Marginal ray-cast quality |
| 49/Tag4 | 0.0% | Very Low | 0.500mm | PASS | `total_failure` fallback |
| 49/Tag6 | high (not shown above; `near_nominal_ratio`=1.0, `n_hit`=36, `dist`=0.0px) | High | 0.505mm | PASS | The one clean match in Cartridge 49, correctly scored High |
| 66/Tag9 | 28.2% | Very Low | 0.520mm | PASS | Confirmed (Stage 7/8/11) channel-junction feature, not a mounting hole — correctly flagged Very Low |
| 72/Tag9 | 39.8% | Very Low | 0.525mm | PASS | Same confirmed channel-junction feature — correctly flagged Very Low |

**Every one of the previously-established problem cases in Cartridges 48, 49, 66, and 72 receives Low or Very Low confidence, with zero exceptions.** This is a direct, quantitative validation that the score, built only from metrics the production pipeline already computes, independently reproduces conclusions that took Stages 7 through 17 substantial dedicated investigation to establish by other means.

**Disclosed limitation — the "Medium" cluster (Cartridges 18 and 72's non-Tag9 tags):** Cartridge 18's five recovery-pass tags (Stage 6, visually verified 5/5 genuine) and Cartridge 72's six anchor-corrected tags (Stage 7, verified 36/36 quality, independently confirmed genuine) both show excellent ray-cast metrics (`near_nominal_ratio` 0.94–1.0, `n_hit`=36) but land at 77–80% ("Medium") rather than High, because both cartridges carry a known, previously-documented larger-than-typical geometric offset (Cartridge 18's outlier scale, noted in Stage 7; Cartridge 72's anchor having required correction at all) that the `geometric_consistency` term penalizes on a single global 690px scale. **This is reported honestly as a real limitation of the design, not adjusted away:** a single global distance normalization cannot distinguish "this candidate is a poor detection" from "this cartridge's overall geometry has more inherent slack for a reason already established as unrelated to detection quality." A future refinement could normalize `dist_from_predicted` per-cartridge (e.g., against that cartridge's own median residual) rather than against one fixed global constant — but this was not implemented here, consistent with this stage's instruction to design and justify the score from existing information rather than propose new detection or calibration work.

---

## 7. Could Confidence Reduce Manual Inspection Effort?

| Cut | Tags | % of population |
|---|---|---|
| Automatically trusted (High + Medium) | 519 / 541 | 95.9% |
| Requiring review (Low + Very Low) | 22 / 541 | 4.1% |
| Strictly High only | 506 / 541 | 93.5% |

At the **cartridge** level (a more operationally realistic unit than individual tags, since an inspector reviews a whole cartridge at a time): **10 of the 79 cartridges (12.7%) contain at least one Low or Very Low tag** — Cartridges 18, 31, 45, 48, 49, 50, 56, 66, 70, and 72. The other 69 cartridges (87.3%) have every tag at Medium confidence or above and would require no confidence-driven manual review at all.

This suggests a realistic, evidence-grounded estimate: **routing full manual review only to the ~13% of cartridges containing at least one flagged tag, while auto-releasing the remaining ~87% on the existing PASS/FAIL decision**, would concentrate inspection effort on exactly the cartridges this entire investigation (Stages 7–17) already independently identified as needing attention — without requiring an inspector to re-check the ~506 individual tags (93.5%) that already carry High confidence under this design.

---

## Summary

A confidence score was designed using only five metrics the production pipeline already computes (`fallback_mode`, `n_hit`, `near_nominal_ratio`, `angular_gap`, `dist_from_predicted`), combined via a formula whose structure is justified by the metrics' own measured correlation structure (near-total redundancy among the ray-cast trio, a distinct but weaker geometric-distance factor) and whose remaining free choices (the 180° angular cap, the 70/30 split, the 90/70/40 category breakpoints, and the untested `off_nominal_fallback` gate value) are explicitly disclosed as heuristics rather than presented as statistically derived. Replayed across the existing 541-tag, 79-cartridge validated population, the score assigns Low or Very Low confidence to every previously-established problem case in Cartridges 48, 49, 66, and 72 with zero exceptions, while correctly scoring Cartridge 61's fully-verified control and the majority of the dataset High — with one disclosed, unresolved limitation (Cartridges 18 and 72's verified-genuine but geometrically-distant tags scoring only Medium). No measurement or PASS/FAIL value was changed anywhere in this design; confidence is computed and reported as a pure addition.

No production code was modified during this investigation. No commits were created. Stopping here per your instruction.
