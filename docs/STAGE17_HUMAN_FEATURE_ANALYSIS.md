# Stage 17 — Human vs Algorithm Feature Analysis

**Status:** Analysis complete. No production code modified. No commits created.
**Branch:** `stage17-human-feature-analysis`
**Scope:** Cartridge 48, Tags 5 and 7 (the two Leica-confirmed, production-missed holes established in Stages 15–16). All comparison examples below are drawn from the same cartridge unless noted.

**Method note:** all images below are direct crops of the actual production input (`Holes_ch00.png`), taken at the exact coordinates the replayed pipeline computed in Stage 16 (predicted positions, assigned candidate positions, and every raw Hough candidate). No coordinate or measurement in this report is invented; every crop is generated from a value already produced by the committed pipeline logic or by direct pixel inspection of the source image.

---

## 1–2. Side-by-Side Visual Comparison

### Reference: a textbook hole (Cartridge 61, Tag 4 — 36/36 ray hits, near_ratio=1.0)

A genuine, unambiguous through-hole looks like this:

- **Edge continuity:** one single, unbroken dark ring, continuous through all 360°.
- **Circularity:** the ring and the bright interior disc are both near-perfect circles.
- **Contrast:** very high — a bright, flat, uniformly-lit interior against a nearly black ring against a mid-gray textured background. Three distinct, well-separated tonal bands.
- **Brightness:** interior is the brightest region in the crop; ring is the darkest.
- **Surrounding texture:** background shows fine speckle/grain texture but no directional scratching near the hole.
- **Connection to nearby channels:** none in this crop — an isolated, self-contained circular feature.
- **Boundary completeness:** 100% — no gaps anywhere around the ring.
- **Gradient direction:** perfectly radial, pointing outward from center at every angle.
- **Local shape:** a simple, convex, closed curve — textbook circle.

### Cartridge 48, Tag 3 / Tag 6 / Tag 9 (currently *assigned*, but `fallback_mode=total_failure`, `n_hit≤6/36`)

All three of Cartridge 48's lowest-confidence *currently assigned* tags were cropped at their exact assigned coordinates. **None shows any dark ring, any bright interior disc, or any closed circular boundary of any kind.** Each crop instead shows:
- fine, low-contrast horizontal/wavy surface-grinding texture,
- a scattering of sub-hole-sized specular highlights and dark specks (texture noise, not edges),
- in Tag 3's case, one faint hairline scratch passing near, but not enclosing, the assigned point.

**These three tags are currently "detected" at locations where, on direct visual inspection of the same production image, no human would identify a hole at all.** This is a materially stronger statement than "the ray-cast has poor coverage" (which Stages 7/14 already established numerically) — it is a direct visual confirmation that the *pixels themselves*, at this processing/resolution, do not show hole-like structure at these three assigned points. (Whether Leica's on-instrument optics, at higher native contrast or different illumination, can see something not visible in this exported crop cannot be determined from this file alone — see §4.)

### Cartridge 48, Tag 1 (assigned, `n_hit=20/36`, **FAIL**) and its Stage-1 anchor candidate

Both the final assigned point (512,564) and the raw candidate that originally defined the anchor (224,568) sit inside a patch of heavy diagonal grinding texture crossed by a distinct **branching, irregular scratch/fissure** pattern. There is no circular boundary — the dark pixels Hough responded to trace an angular, tree-like branching shape, not an arc. This is a direct, visual explanation for both the low confidence and the FAIL result: the detector is responding to a surface defect, not a hole edge.

### Cartridge 48, Tag 4 ("normal" fallback, `n_hit=28/36`, PASS) — an unexpected finding

Cropping tightly around Tag 4's exact assigned coordinate at first appeared to show nothing hole-like at all. Widening the crop revealed why: **the assigned point sits almost exactly on the rim of a large, separate circular surface feature** — a light-gray disc roughly 5–6× the diameter of a normal tag hole, with faint radial polishing marks, distinct from any of the seven small tag holes. The candidate's ray-cast is very likely responding to the local curvature of this much larger disc's boundary, tangent to it, rather than to a small isolated through-hole. **This is currently classified as a normal, passing detection**, and its measured diameter happens to fall close to Leica's reported value for Tag 4 — but the visual evidence raises a real question about *what* is actually being measured at this location, independent of Tags 5/7. This finding is reported transparently as a byproduct of this investigation; it was not previously identified in Stages 7–16, which characterized Tag 4 only through its numeric ray-cast metrics, not through direct visual inspection of what surrounds the candidate point.

### The two unresolved tags: what a human sees where production is looking

**Tag 7** (predicted position (3344,3314), in-bounds, zero candidates within either the 600px or 690px search windows): the crop directly confirms what the overview already suggested — the predicted point sits on **the rounded corner of a wide return-channel**, a rectangular, straight-walled groove bending back on itself. There is a clear, high-contrast dark region here, but its boundary is a rounded rectangle (straight parallel sides joined by a single tight corner curve), not a closed circle. No small hole of any kind is visible anywhere in a ±400px window around this point.

**Tag 5** (predicted position (1923,5628), 702px beyond the image's pixel height): the crop at the nearest in-bounds point directly below Tag 5's x-coordinate shows that the image's *actual usable content* ends well before the frame's bottom edge here — a diagonal physical part-edge cuts across the frame, with dark, unlit sensor background beyond it. **There is no surface at all to inspect at the predicted location** — visual confirmation that the anchor error, not a hidden or low-contrast hole, is what has moved this prediction off the part entirely.

### One additional, disclosed-but-unconfirmed candidate

The nearest unused, high-quality raw candidate to Tag 7's prediction, `(3804,2148)` (n_hit=35/36 — a very strong ray-cast score), was also cropped. It shows **multiple straight, parallel, diagonally-running channel walls** — a "washboard" of parallel grooves, not a circular enclosure. This is a clear, visually obvious false-positive-for-holes signature that nonetheless scores nearly as well as a genuine hole on the ray-hit-count metric, because a dense grid of straight edges at many angles still crosses most of the 36 measurement rays. **A human would reject this instantly on shape alone; the detector's scoring has no mechanism to do so.**

### For contrast: a genuine debris false-positive and a genuine channel wall

- `(2644,3896)`, n_hit=1/36 (near-total rejection already): a small, irregular, isolated dark blob a few pixels across — classic dust/debris signature. The detector already scores this correctly low.
- The top arc of the large ring feature (unrelated to any tag): a single, smooth, continuous curved dark band, visually similar in *local* curvature to a real hole's edge, but obviously part of a much larger structure when viewed in its full context — the same "scale mismatch" problem seen in Tag 4's disc rim.

---

## 3. Comparative Summary Table

| Characteristic | Textbook hole (C61 Tag4) | Cartridge 48 Tag4 (assigned) | Cartridge 48 Tag1/Tag3/Tag6/Tag9 (assigned, low-conf.) | Tag7 predicted region | Tag5 predicted region | C24 (unused, n_hit=35) | C23 (debris) |
|---|---|---|---|---|---|---|---|
| Edge continuity | Full 360°, unbroken | Partial arc (rim of larger disc) | None found | Straight + one rounded corner, not circular | No surface present | Multiple long straight edges | Short, irregular, closed blob edge |
| Circularity | Near-perfect | Large-radius arc (not this hole's own boundary) | N/A — no boundary | Rectangular corner | N/A | None — parallel lines | None — irregular blob |
| Contrast | Very high, 3 clean tonal bands | Moderate, follows disc rim | Very low, texture-level only | High (channel is dark) | N/A | High (channel walls) | Moderate, small |
| Local shape | Simple closed convex curve | Large convex curve (not tag-scale) | No coherent shape | Elongated rounded rectangle | N/A | Parallel straight bands | Small closed irregular polygon |
| Context | Isolated | Adjacent to unrelated large disc | Isolated, plain texture | Part of channel network | Off imaged part | Part of channel network | Isolated speck |

---

## 4. Cues a Human Uses That the Detector Never Evaluates

Direct inspection makes the gap concrete:

1. **Shape topology / contour closure.** A human instantly distinguishes a closed, simple, convex circular boundary (a hole) from an open or elongated boundary (a channel wall, a corner, a scratch) — regardless of how many edge pixels are present. The production detector's ray-cast only counts *how many* of 36 fixed rays cross a dark-to-light transition near a nominal radius; it never checks whether those crossings actually trace one coherent closed curve. This is exactly why C24 (35/36 hits, parallel channel walls) scores almost as well as a genuine hole.
2. **Contextual / topological relationship to the surrounding channel network.** In the full-frame overview, every genuine hole in this cartridge connects to, or sits at a corner of, a visible channel line, and the seven holes have a consistent visual layout relative to that network and to each other. A human operator uses this whole-part gestalt — "this is clearly the hole at the end of that channel branch" — to locate a hole even when its exact pixel offset from some other reference point is imprecise. The production pipeline instead relies entirely on a single fixed-offset arithmetic transform (`REF_OFFSETS` from one anchor) that has no way to use channel connectivity or relative-layout information at all. This is the cue most directly responsible for the current failure: Stage 16 showed the anchor's own arithmetic prediction is several hundred pixels off; a person is not fooled by that because they are not using that arithmetic in the first place.
3. **Scale relative to neighboring structures.** A human immediately recognizes that a curve is part of a much larger feature (the ring's arc, the large disc's rim) rather than a tag-sized hole boundary, because they perceive the whole structure at once. The detector evaluates each candidate only at one fixed nominal radius, with no check for whether the local curvature it responded to belongs to something much bigger. This is exactly the issue found at Tag 4.
4. **Interior uniformity / flatness.** A genuine hole's interior is a flat, uniformly bright, backlit disc. Surface texture (as at Tag 3/6/9's current assigned points) is locally noisy and non-uniform even where it happens to contain a few edge-like pixels. The ray-cast checks only the boundary crossings, never the interior's uniformity, so it cannot distinguish "textured surface with a few coincidental edge-like pixels" from "a real hole."
5. **Isolated-blob size/shape irregularity** (debris rejection): already adequately handled by the existing minRadius/maxRadius/near_ratio scoring — the one cue examined here where the current detector performs well, included for completeness of the comparison.

---

## 5. First Missing Visual Cue Per Unresolved Tag

**Tag 7 — first missing cue: contextual relationship with neighbouring structures**, closely followed by **local topology / contour continuity**. Production's predicted position lands on a real, high-contrast, but non-circular structure (a channel corner). No raw candidate exists within any tolerance the project has evaluated as safe. The reason the search fails is not that the detector misjudged a hole's shape here — it never found any circular candidate to misjudge — but that the location it is looking at was never the right neighborhood to begin with. A human would not be searching this specific pixel neighborhood at all; they would follow the channel/hole layout visible in the whole frame to the correct one. This is a location problem rooted in the absence of contextual reasoning, not a shape-discrimination problem at this specific point.

**Tag 5 — first missing cue: contextual relationship with neighbouring structures**, but here the mismatch is total: the predicted location is not on the imaged part at all. No visual cue of any kind — circularity, contour continuity, or otherwise — can be evaluated because there is no image content there to evaluate. As with Tag 7, this traces back to the absence of a whole-part contextual/topological reasoning step; a fixed-offset arithmetic model has no way to notice "this prediction has walked off the part" the way a human immediately would.

Neither tag's failure is best classified as "incomplete circular edge" or "non-circular enclosed region" — those describe a detector that found *something* and misjudged its shape. Here, the deeper and prior failure is that the searched location itself is wrong, for the anchor-imprecision reasons already established in Stage 16. The clearest visual instance of a genuine shape-discrimination gap in this cartridge is not at Tag 5 or Tag 7's predicted point at all, but at candidate **C24** — a real, unused, high-scoring detection that a human would reject immediately on topology grounds and the detector cannot.

---

## 6. Ranked List of Missing Features (Greatest Improvement First)

1. **Contextual / topological relationship to the channel network and other holes.** Ranked first because it is the only cue among those examined that addresses the *root cause* identified in Stage 16 (anchor imprecision) rather than only filtering candidates after the fact. A model that could use visible channel connectivity to constrain or cross-check the predicted layout would be robust to exactly the kind of anchor error documented here.
2. **Shape topology / contour closure (simple-closed-curve check).** Directly explains and would filter the C24-style false positive, and would give the confidence score a genuine shape signal independent of raw edge-hit count.
3. **Scale-relative-to-neighboring-structure check.** Directly relevant to the Tag 4 finding in §2; would catch rim-of-larger-feature detections currently indistinguishable from genuine tag-scale holes.
4. **Interior uniformity/flatness check.** Would flag Tag 3/6/9-style assignments (texture, no real boundary) as suspect rather than silently accepting them at low confidence.
5. **Isolated-blob irregularity rejection.** Lowest priority — the existing pipeline already handles this case adequately (§4, item 5).

---

## 7. Smallest Production-Safe Detector Extension (Recommendation Only — Not Implemented)

Consistent with the additive-only philosophy already established and validated in Stage 13 (secondary detector) and repeatedly confirmed safe across Stages 9–14 (never modify Stage 1/2/Recovery, never touch existing matches): the smallest safe extension would be a **read-only shape-topology scorer**, computed once per existing raw Hough candidate (from the same candidate list already generated, no new detections, no changed Hough parameters), that:

- traces the actual contour of dark pixels around each candidate (a direct contour-closure and convexity check, not a new detection step),
- produces a single additional metric — e.g., "closed-contour ratio" or "convexity defect count" — attached to the existing candidate record,
- is used only as an additional, informational signal alongside the existing `n_hit`/`near_ratio`/`fallback_mode` metrics — never as a new gating rule, and never applied to any tag that already has a "normal" fallback match.

This would let a future investigation (not this one) evaluate whether such a metric reliably separates cases like C24 (channel wall, low closed-contour ratio) from genuine holes (high closed-contour ratio) using measured evidence, before any change to matching logic is considered. It would not, by itself, recover Tag 5 or Tag 7 in Cartridge 48 — both failures trace to the absence of contextual/topological reasoning about the anchor and channel layout (§5, §6 item 1), a materially larger architectural question outside a candidate-level shape filter. No such extension is proposed for implementation here; this section states only what the smallest safe next investigative step would evaluate, per your instruction not to redesign or implement anything.

---

## Summary

Direct visual inspection of Cartridge 48's actual production image confirms, concretely, what Stage 16 established analytically: production's prediction for Tag 7 lands on a channel-wall corner, and its prediction for Tag 5 lands entirely off the imaged part — neither location contains a hole, and a human would recognize both facts immediately by using visual cues (contour topology, whole-part contextual layout, scale-relative-to-context) that the current Hough-plus-ray-cast detector never evaluates. The single most consequential missing cue is contextual/topological reasoning about the channel network and overall part layout — the cue that would make prediction robust to the anchor error identified in Stage 16, rather than a per-candidate shape filter alone. A shape-topology scorer is the smallest production-safe extension that could be investigated next, but it would address candidate-level false positives (such as the C24 channel-wall detection found in this investigation), not the anchor-level root cause.

This report proposes no fix and implements no change, per your instruction. No production code was modified during this investigation. No commits were created. Stopping here per your instruction.
