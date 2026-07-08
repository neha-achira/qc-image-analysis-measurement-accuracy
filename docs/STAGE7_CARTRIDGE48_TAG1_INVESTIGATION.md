# Stage 7 — Cartridge 48, Tag 1: Root-Cause Investigation of the New FAIL

**Status:** Investigation complete. No production code modified. No commit created.
**Branch:** `stage7-geometric-model-investigation` (`detect_features.py` remains modified in the working tree only, exactly as left after the prior implementation step — nothing further changed).

---

## 1. Complete Comparison: Production vs. Implemented Stage 1

| Field | Production (before) | Implemented (after) |
|---|---|---|
| Selected anchor | (5416, 2148) | Different candidate/role pivot (see §2) |
| Predicted Tag 1 position | (−675, 684) — **outside image bounds** (image width 12,387) | (224, 568) — **in bounds** |
| Stage 1's own nearest-candidate pick | N/A — bounds check excluded Tag 1 before any candidate search ran | **(224, 568)**, distance ≈ 0px from the prediction |
| Final matched candidate (after Stage 2) | None (`missing_holes`, reason=`outside_image`) | **(512, 564)**, distance 288.0px from the prediction — **a Stage 2 substitution, not Stage 1's own pick** |
| Diameter | N/A | 0.4225mm |
| PASS/FAIL | N/A | **FAIL** (0.4225mm < 0.45mm floor) |

### All nearby raw candidates (within 1000px of the AFTER predicted position, (224,568))

| Candidate | Distance from prediction | n_hit | Near-nominal ratio | Angular gap | Fallback mode | Diameter if used |
|---|---|---|---|---|---|---|
| **(224,568) — Stage 1's own pick** | 0.0px | 18/36 | 25.0% | 70.0° | normal | 0.5300mm (would be **PASS**) |
| **(512,564) — Stage 2's final pick** | 288.0px | 20/36 | 33.3% | 50.0° | normal | 0.4225mm (**FAIL**, actual reported result) |
| (1060,676) | 842.9px | 2/36 | 0.0% | 290.0° | total_failure | 0.5000mm (too far to be eligible) |

(Under the BEFORE/production prediction, (−675,684), the nearest candidate was also (224,568) at 906.5px — already beyond even the recovery pass's 690px tolerance, confirming Tag 1 genuinely had no reachable candidate under the old anchor, independent of the bounds check.)

---

## 2. Exactly Why the New FAIL Appears

Traced via `debug_context["stage2_preview"]`, captured directly from the real implemented code:

```
Tag1: current_cxy=(224,568)  current_key=(2, 18, 9, -0.0)
      alt_cxy=(512,564)      alt_key=(2, 20, 12, -288.03)
      would_change: True
```

**Step by step:**
1. **Different anchor — yes.** The role-generalized Stage 1 search selects a different `(candidate, role)` pivot for Cartridge 48 than production's Tag-9-only search, exactly as designed.
2. **Different prediction — yes, directly caused by (1).** Tag 1's predicted position moves from (−675,684) (off-frame) to (224,568) (on-frame).
3. **Different candidate assignment — yes, but not where you'd expect.** Stage 1 itself, given the new prediction, correctly finds the *closest available* candidate: (224,568), sitting essentially exactly on the predicted point (0.0px away). If Stage 1's pick had been left alone, Tag 1 would report 0.5300mm — a **PASS**.
4. **Stage 2 interaction — yes, this is the proximate cause of the FAIL.** Stage 2 (completely unmodified code, per requirement 2 of the implementation task) searches within `MATCH_TOL_PX` (600px) of the same predicted position for a higher-ranked alternative, exactly as it already does for every other tag in every other cartridge. It finds (512,564) — 288px away, still inside the 600px window — and its ranking key `(fallback_rank, n_hit, near, −distance)` favors it over Stage 1's pick purely because it has a slightly higher ray-hit count (20 vs. 18) and near-nominal ratio (33.3% vs. 25.0%). Since the comparison is lexicographic and `n_hit` is compared before distance, the 288px-farther candidate wins despite being much closer having been available.
5. **Recovery pass interaction — no.** `debug_context["recovery_pass"]` shows `{"recovered_tags": []}` both before and after; the recovery pass never engages here, since Tag 1 is already matched by Stage 1 + Stage 2 before the recovery pass runs.

**This is a genuine Stage 1 / Stage 2 interaction (matching option "Stage 2 interaction" from your list), not a flaw in Stage 1 alone.** Stage 2's substitution rule is pre-existing, unmodified, and has presumably behaved this way in production all along — it simply never had the opportunity to affect Tag 1 in Cartridge 48 before, because Tag 1 never reached Stage 2 under the old anchor (the bounds check excluded it first). The Stage 1 change didn't introduce a new rule; it exposed an existing one to a case it had never previously touched.

---

## 3. Visual Inspection

A labeled crop was generated showing both candidates and the predicted position (`validation_output/stage7_geometry/cart48_tag1_both_candidates.png`).

**Finding: neither candidate sits on a genuine hole.** Both the orange circle (Stage 1's pick, (224,568)) and the red circle (Stage 2's final pick, (512,564)) fall on plain, scratched material — parallel linear scratch marks and surface texture, with no visible dark circular depression, no hole wall, no feature resembling any of the genuine 36/36-quality holes documented elsewhere in this investigation (e.g., Cartridge 72's Tags 1–7). Neither location shows any physical feature that would correspond to a real mounting hole.

This is consistent with Cartridge 48's already-documented status (from the geometric-model investigation and the corrected blast-radius report) as belonging to a separate cluster with a distinct, poor-image-quality failure mode — Hough is very likely responding to scratches or surface noise in this specific region, not a genuine hole, for either candidate.

---

## 4. Classification

**(D) Another issue entirely — not (A), not (B), and not simply (C).**

- **Not (A) a true regression**: there was no previously-correct result to regress from. Tag 1 was simply unmeasured (`outside_image`) before. Nothing that was confirmed correct has become incorrect.
- **Not (B) an improvement exposing a hidden measurement**: this would require the newly-exposed candidate to be a genuine hole. It is not — both candidates were visually inspected and neither shows any real hole feature.
- **Not merely (C) ambiguous-for-lack-of-ground-truth**: this goes beyond "we don't know which is right." Direct visual inspection shows **neither is right** — this is a stronger, more specific finding than plain ambiguity.
- **(D) is correct**: this is a symptom of Cartridge 48's pre-existing, already-flagged image-quality problem (no genuine hole detectable in this region at all), newly *exposed* — not *caused* — by the Stage 1 change's wider reach, and specifically made to look worse (a spurious PASS-looking noise candidate replaced by a spurious FAIL-looking one) by Stage 2's existing, unmodified preference for ray-hit count over positional proximity when no genuine candidate is present to correctly outrank.

---

## 5. Does This Change the Implementation Recommendation?

**Commit after documenting the ambiguity.**

Reasoning:
- The core, extensively validated objective — Cartridge 72's six genuine holes (Tags 1,3,4,5,6,7) correctly recovered, zero regressions across all 74 unaffected cartridges — is completely unaffected by this finding and remains fully valid.
- This specific behavior is confirmed, by direct visual inspection, to be a symptom of a **pre-existing, already out-of-scope condition** (Cartridge 48's documented poor-image-quality cluster, shared with Cartridges 45/49/50) — not a new defect in the Stage 1 redesign's logic. The role-generalized search performed exactly as designed: it found the closest, most self-consistent geometric hypothesis available. The problem is that no genuine hole exists for Hough to find in this specific region of this specific cartridge — a data/image-quality issue, not an algorithm defect.
- It should **not** trigger "revise the Stage 1 redesign" — there is nothing wrong with Stage 1's logic to revise. The interaction is with Stage 2's pre-existing ranking rule, which was explicitly out of scope for this implementation and has evidently behaved this way (preferring ray-hit count over distance) for every other tag in every other cartridge all along; it simply never had a chance to touch this particular tag before.
- It **should** be explicitly documented — added to the standing, disclosed list of open items for the 48/49(/66) cluster — so that anyone reviewing Cartridge 48's output post-implementation understands that Tag 1's new FAIL, like Tag 9's changes in the same cartridge, is not a confirmed-correct measurement and requires the same separate, dedicated investigation already recommended for that cluster.

No production code was modified during this investigation. No commit was created. Stopping here per your instruction.
