"""
preprocess.py
=============
Achira Beta Cartridge — Image Preprocessing Module
DWG: ACMCTA001  |  Material: PMMA  |  Microscope: 5X, stitched PNG

PURPOSE
-------
Converts raw stitched microscope PNGs into clean, edge-enhanced images
ready for feature detection and measurement.

Tuned to the observed characteristics of the actual cartridge images:
  - Holes_ch00.png  : 8911×6136 px, RGBA (alpha channel must be stripped)
  - neck_ch00.png   : 4503×3416 px, RGB
  - DAB_ch00.png    : ~10 MB, RGB
  - Mixing_ch00.png : ~56 MB, RGB

OBSERVED IMAGE CHARACTERISTICS (from real images)
--------------------------------------------------
  - Background    : medium grey PMMA (~140-170 pixel value)
  - Feature walls : very dark / black edges (~0-40 px value)
  - Feature interiors : dark grey (~40-80 px value)
  - Stitch seam   : horizontal bright line at ~50% image height (neck image)
  - Scratches     : faint diagonal lines across PMMA surface
  - Dust/debris   : small dark dots (2-8 px), scattered
  - Illumination  : slightly brighter centre, darker corners (vignette)
  - Stitch format : 2 tiles merged (visible boundary line)

PIPELINE PER IMAGE TYPE
-----------------------
  ALL images:
    1. Load + strip alpha (Holes is RGBA)
    2. Convert to grayscale
    3. Correct vignette (CLAHE)
    4. Gaussian blur (suppress scratches + dust)
    5. Canny edge detection (tuned per image type)
    6. Morphological close (connect broken edges)
    7. Mask stitch seam (neck image only)

  HOLES image additionally:
    8. Bilateral filter before Canny (preserves hole wall edges)

  NECK image additionally:
    8. Stitch seam detection and masking
    9. Tighter Canny thresholds (fine channel)

USAGE
-----
  # Preprocess a single image:
      from preprocess import preprocess
      result = preprocess("Holes_ch00.png")
      # result["edges"]  — Canny edge map
      # result["gray"]   — grayscale + CLAHE
      # result["binary"] — thresholded binary

  # Preprocess and save debug outputs:
      python preprocess.py --image Holes_ch00.png --debug
      python preprocess.py --image neck_ch00.png  --debug

  # Batch preprocess a cartridge folder:
      python preprocess.py --folder ./1/  --debug
"""

import cv2
import numpy as np
import os
import argparse
from pathlib import Path


# ── Image type detection ──────────────────────────────────────────────────────

IMAGE_TYPES = {
    "holes":  ["holes_ch00", "holes_ch"],
    "neck":   ["neck_ch00",  "neck_ch"],
    "dab":    ["dab_ch00",   "dab_ch"],
    "mixing": ["mixing_ch00", "mixing_merging", "mixing_ch"],
}

# Per-type preprocessing configs tuned to real images
CONFIGS = {
    "holes": {
        "blur_ksize":        (5, 5),
        "blur_sigma":        1.2,
        "clahe_clip":        2.5,
        "clahe_tile":        (8, 8),
        "bilateral_d":       9,
        "bilateral_sigma_c": 55,
        "bilateral_sigma_s": 55,
        "canny_low":         20,
        "canny_high":        80,
        "morph_ksize":       (3, 3),
        "morph_iters":       1,
        "mask_stitch":       True,   # Holes image has 4-panel stitch (cross seam)
        "notes": (
            "Tuned on real Holes_ch00.png (8911x6136, RGBA). "
            "Alpha stripped automatically. Bilateral preserves circular hole wall edges. "
            "4-panel stitch: horizontal seam ~y=3065, vertical seam ~x=5680. "
            "Right panels have higher edge noise — per-quadrant normalization applied."
        ),
    },
    "neck": {
        "blur_ksize":        (3, 3),    # smaller — preserve fine channel
        "blur_sigma":        0.8,
        "clahe_clip":        3.0,       # higher clip — more contrast variation
        "clahe_tile":        (6, 6),
        "bilateral_d":       7,         # tuned on real image: brings edge% from 24%→5%
        "bilateral_sigma_c": 40,        # lower sigma preserves fine neck edges
        "bilateral_sigma_s": 40,
        "canny_low":         30,        # tuned: 30/100 gives ~4.6% clean edges
        "canny_high":        100,
        "morph_ksize":       (2, 2),
        "morph_iters":       1,
        "mask_stitch":       True,      # stitch seam detected at y=1216 in real image
        "notes": (
            "Tuned on real neck_ch00.png (4503x3416). "
            "Bilateral d=7 reduces PMMA scratch noise from 24% to ~5% edge density. "
            "Stitch seam auto-detected and masked."
        ),
    },
    "dab": {
        "blur_ksize":        (5, 5),
        "blur_sigma":        1.2,
        "clahe_clip":        2.0,
        "clahe_tile":        (8, 8),
        "bilateral_d":       7,
        "bilateral_sigma_c": 50,
        "bilateral_sigma_s": 50,
        "canny_low":         20,
        "canny_high":        75,
        "morph_ksize":       (3, 3),
        "morph_iters":       1,
        "mask_stitch":       False,
        "notes": "Inlet/DAB area — standard settings.",
    },
    "mixing": {
        "blur_ksize":        (5, 5),
        "blur_sigma":        1.5,       # slightly more blur — large image, more noise
        "clahe_clip":        2.5,
        "clahe_tile":        (8, 8),
        "bilateral_d":       9,
        "bilateral_sigma_c": 60,
        "bilateral_sigma_s": 60,
        "canny_low":         18,
        "canny_high":        72,
        "morph_ksize":       (3, 3),
        "morph_iters":       1,
        "mask_stitch":       False,
        "notes": "Mixing chamber — large stitched image, slightly more blur.",
    },
}


# ── Image type detection ──────────────────────────────────────────────────────

def detect_image_type(image_path: str) -> str:
    """
    Infer image type from filename (case-insensitive).
    Returns one of: holes | neck | dab | mixing | unknown
    """
    name = Path(image_path).stem.lower()
    for img_type, keywords in IMAGE_TYPES.items():
        if any(kw in name for kw in keywords):
            return img_type
    return "holes"  # safe default — most conservative settings


# ── Core preprocessing ────────────────────────────────────────────────────────

def load_image(image_path: str) -> np.ndarray:
    """
    Load image and handle RGBA → BGR conversion.
    Holes_ch00.png is RGBA — alpha channel must be stripped.
    """
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Cannot load: {image_path}")

    if img.ndim == 2:
        # Already grayscale — convert to BGR for consistency
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        # RGBA → BGR (drop alpha channel)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    # else: already BGR — nothing to do

    return img


def to_gray(img_bgr: np.ndarray) -> np.ndarray:
    """Convert BGR to grayscale."""
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)


def apply_clahe(gray: np.ndarray, clip_limit: float, tile_size: tuple) -> np.ndarray:
    """
    CLAHE — Contrast Limited Adaptive Histogram Equalisation.
    Corrects the vignette (bright centre, dark corners) and enhances
    local contrast for PMMA feature edges.
    """
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_size)
    return clahe.apply(gray)


def detect_stitch_seam(gray: np.ndarray, search_band: float = 0.15) -> int:
    """
    Detect the horizontal stitch seam in stitched images.
    Looks for a bright horizontal line near the vertical centre
    (within ±15% of image height).
    Returns the y-coordinate of the seam, or -1 if not found.
    """
    h, w   = gray.shape
    centre = h // 2
    band   = int(h * search_band)
    region = gray[centre - band: centre + band, :]

    row_means  = np.mean(region, axis=1)
    seam_local = int(np.argmax(row_means))
    peak       = row_means[seam_local]
    median     = np.median(row_means)
    if peak > median * 1.03:
        return (centre - band) + seam_local
    return -1


def detect_vertical_stitch_seam(gray: np.ndarray,
                                 search_band: float = 0.15) -> int:
    """
    Detect the vertical stitch seam in 4-panel stitched images (Holes_ch00).
    Looks for a bright vertical line near the horizontal centre
    (within ±15% of image width).
    Returns the x-coordinate of the seam, or -1 if not found.
    """
    h, w   = gray.shape
    centre = w // 2
    band   = int(w * search_band)
    region = gray[:, centre - band: centre + band]

    col_means  = np.mean(region, axis=0)
    seam_local = int(np.argmax(col_means))
    peak       = col_means[seam_local]
    median     = np.median(col_means)
    if peak > median * 1.03:
        return (centre - band) + seam_local
    return -1


def normalize_quadrants(gray: np.ndarray,
                         seam_y: int, seam_x: int) -> np.ndarray:
    """
    Normalize brightness independently per quadrant to compensate for
    illumination differences between panels in a 4-panel stitched image.

    Each quadrant gets its own CLAHE pass with a higher clip limit
    to bring the noisy right panels in line with the cleaner left panels.
    """
    if seam_y < 0 or seam_x < 0:
        return gray

    h, w   = gray.shape
    result = gray.copy()
    clahe  = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))

    # Process each quadrant independently
    regions = [
        (0,      seam_y, 0,      seam_x),   # top-left
        (0,      seam_y, seam_x, w     ),   # top-right  ← noisier
        (seam_y, h,      0,      seam_x),   # bot-left
        (seam_y, h,      seam_x, w     ),   # bot-right
    ]
    for y1, y2, x1, x2 in regions:
        if y2 > y1 and x2 > x1:
            result[y1:y2, x1:x2] = clahe.apply(gray[y1:y2, x1:x2])

    return result


def mask_stitch_seam(img: np.ndarray, seam_y: int,
                     half_width: int = 8) -> np.ndarray:
    """
    Mask the stitch seam by replacing it with the local median grey value.
    This prevents the seam from being detected as a feature edge.
    half_width: pixels above and below the seam to mask.
    """
    if seam_y < 0:
        return img
    result = img.copy()
    h = img.shape[0]
    y1 = max(0, seam_y - half_width)
    y2 = min(h, seam_y + half_width)

    # Use median of rows just outside the seam band as fill value
    above = img[max(0, y1 - 20): y1, :]
    below = img[y2: min(h, y2 + 20), :]
    fill  = int(np.median(np.concatenate([above.flatten(), below.flatten()])))

    result[y1:y2, :] = fill
    return result


def preprocess(image_path: str,
               image_type: str = None,
               config: dict = None) -> dict:
    """
    Full preprocessing pipeline for one cartridge image.

    Parameters
    ----------
    image_path : str
        Path to the PNG image.
    image_type : str, optional
        One of: holes | neck | dab | mixing.
        Auto-detected from filename if not provided.
    config : dict, optional
        Override config. Uses CONFIGS[image_type] if not provided.

    Returns
    -------
    dict with keys:
        "bgr"         — original image (BGR, alpha stripped)
        "gray"        — grayscale after CLAHE
        "gray_raw"    — grayscale before CLAHE (for reference)
        "blurred"     — after Gaussian blur
        "edges"       — Canny edge map  ← primary output for detection
        "binary"      — binary threshold (for contour detection)
        "seam_y"      — stitch seam y-coordinate (-1 if none found/masked)
        "image_type"  — detected type string
        "config"      — config dict used
        "image_path"  — input path
    """
    # ── Resolve type and config ──────────────────────────────────────────────
    if image_type is None:
        image_type = detect_image_type(image_path)
    if config is None:
        config = CONFIGS.get(image_type, CONFIGS["holes"])

    cfg = config  # shorthand

    # ── 1. Load ──────────────────────────────────────────────────────────────
    bgr      = load_image(image_path)
    gray_raw = to_gray(bgr)

    # ── 2. CLAHE (initial contrast enhancement) ──────────────────────────────
    gray = apply_clahe(gray_raw, cfg["clahe_clip"], cfg["clahe_tile"])

    # ── 3. Stitch seam detection and masking ─────────────────────────────────
    seam_y = -1
    seam_x = -1
    gray_masked = gray.copy()

    if cfg.get("mask_stitch", False):
        seam_y = detect_stitch_seam(gray)

        # For holes image: also detect vertical seam (4-panel cross stitch)
        if image_type == "holes":
            seam_x = detect_vertical_stitch_seam(gray)

            # Per-quadrant normalization to equalize illumination across panels
            # (right panels are consistently brighter/noisier)
            if seam_y > 0 and seam_x > 0:
                gray = normalize_quadrants(gray, seam_y, seam_x)
                gray_masked = gray.copy()

        if seam_y > 0:
            gray_masked = mask_stitch_seam(gray_masked, seam_y, half_width=10)
        if seam_x > 0:
            gray_masked = mask_stitch_seam(
                gray_masked.T, seam_x, half_width=10
            ).T   # transpose trick: reuse horizontal masker for vertical seam

    # ── 4. Bilateral filter (holes / large feature images) ───────────────────
    #    Bilateral preserves sharp feature wall edges while smoothing
    #    the PMMA surface texture (scratches, dust halos)
    if cfg.get("bilateral_d", 0) > 0:
        filtered = cv2.bilateralFilter(
            gray_masked,
            cfg["bilateral_d"],
            cfg["bilateral_sigma_c"],
            cfg["bilateral_sigma_s"]
        )
    else:
        filtered = gray_masked

    # ── 5. Gaussian blur (final noise suppression) ───────────────────────────
    blurred = cv2.GaussianBlur(
        filtered,
        cfg["blur_ksize"],
        cfg["blur_sigma"]
    )

    # ── 6. Canny edge detection ───────────────────────────────────────────────
    edges = cv2.Canny(blurred, cfg["canny_low"], cfg["canny_high"])

    # ── 7. Morphological close (connect broken edge segments) ─────────────────
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, cfg["morph_ksize"])
    edges  = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel,
                               iterations=cfg["morph_iters"])

    # ── 8. Re-mask both seams on edge map ────────────────────────────────────
    if seam_y > 0:
        edges = mask_stitch_seam(edges, seam_y, half_width=12)
    if seam_x > 0:
        edges = mask_stitch_seam(edges.T, seam_x, half_width=12).T

    # ── 9. Binary threshold (for contour-based detection) ─────────────────────
    _, binary = cv2.threshold(blurred, 0, 255,
                               cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    return {
        "bgr":        bgr,
        "gray_raw":   gray_raw,
        "gray":       gray,
        "blurred":    blurred,
        "edges":      edges,
        "binary":     binary,
        "seam_y":     seam_y,
        "seam_x":     seam_x,
        "image_type": image_type,
        "config":     cfg,
        "image_path": image_path,
    }


# ── Debug / visualisation ─────────────────────────────────────────────────────

def save_debug_outputs(result: dict, out_dir: str = None):
    """
    Save side-by-side debug images showing each preprocessing stage.
    Outputs written to out_dir (defaults to same folder as input image).
    """
    if out_dir is None:
        out_dir = str(Path(result["image_path"]).parent)
    os.makedirs(out_dir, exist_ok=True)

    stem      = Path(result["image_path"]).stem
    img_type  = result["image_type"]

    # Scale down for debug output — these images are huge
    h, w   = result["gray"].shape
    max_d  = 2000
    scale  = min(max_d / w, max_d / h, 1.0)
    dsize  = (int(w * scale), int(h * scale))

    def _resize(img):
        if img.ndim == 2:
            return cv2.resize(img, dsize, interpolation=cv2.INTER_AREA)
        return cv2.resize(img, dsize, interpolation=cv2.INTER_AREA)

    def _bgr(gray):
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # Individual stage outputs
    stages = {
        "01_gray_raw":  _resize(result["gray_raw"]),
        "02_clahe":     _resize(result["gray"]),
        "03_blurred":   _resize(result["blurred"]),
        "04_edges":     _resize(result["edges"]),
        "05_binary":    _resize(result["binary"]),
    }
    for name, img in stages.items():
        path = os.path.join(out_dir, f"{stem}_{name}.png")
        cv2.imwrite(path, img)

    # Side-by-side comparison: raw | CLAHE | edges
    raw_r   = _bgr(_resize(result["gray_raw"]))
    clahe_r = _bgr(_resize(result["gray"]))
    edge_r  = _bgr(_resize(result["edges"]))

    # Add labels
    font = cv2.FONT_HERSHEY_SIMPLEX
    for panel, label in [(raw_r,   "Raw grayscale"),
                          (clahe_r, "CLAHE enhanced"),
                          (edge_r,  f"Canny edges ({img_type})")]:
        cv2.rectangle(panel, (0, 0), (panel.shape[1], 36), (20, 20, 20), -1)
        cv2.putText(panel, label, (10, 26), font, 0.85, (0, 220, 255), 2)

    # Draw stitch seam line on CLAHE panel if detected
    if result["seam_y"] > 0:
        sy = int(result["seam_y"] * scale)
        cv2.line(clahe_r, (0, sy), (clahe_r.shape[1], sy), (0, 60, 255), 2)
        cv2.putText(clahe_r, f"Stitch seam y={result['seam_y']}",
                    (10, sy - 8), font, 0.65, (0, 60, 255), 2)

    side_by_side = np.hstack([raw_r, clahe_r, edge_r])
    sbs_path     = os.path.join(out_dir, f"{stem}_debug_comparison.png")
    cv2.imwrite(sbs_path, side_by_side)

    print(f"  Debug outputs saved to: {out_dir}/")
    print(f"    {stem}_01_gray_raw.png")
    print(f"    {stem}_02_clahe.png")
    print(f"    {stem}_03_blurred.png")
    print(f"    {stem}_04_edges.png")
    print(f"    {stem}_05_binary.png")
    print(f"    {stem}_debug_comparison.png  ← side-by-side")
    if result["seam_y"] > 0:
        print(f"  Stitch seam detected and masked at y = {result['seam_y']} px")


def print_image_info(result: dict):
    """Print summary of image properties and preprocessing applied."""
    h, w   = result["gray"].shape
    cfg    = result["config"]
    seam   = result["seam_y"]

    print("\n" + "─" * 60)
    print(f"  Image       : {Path(result['image_path']).name}")
    print(f"  Type        : {result['image_type']}")
    print(f"  Dimensions  : {w} × {h} px")
    print(f"  Stitch seam : {'y = ' + str(seam) + ' px (masked)' if seam > 0 else 'not detected'}")
    print("  Pipeline    :")
    print(f"    CLAHE clip={cfg['clahe_clip']}, tile={cfg['clahe_tile']}")
    if cfg.get("bilateral_d", 0) > 0:
        print(f"    Bilateral d={cfg['bilateral_d']}, "
              f"σc={cfg['bilateral_sigma_c']}, σs={cfg['bilateral_sigma_s']}")
    print(f"    Gaussian blur {cfg['blur_ksize']}, σ={cfg['blur_sigma']}")
    print(f"    Canny low={cfg['canny_low']}, high={cfg['canny_high']}")
    print(f"    Morph close {cfg['morph_ksize']}, iters={cfg['morph_iters']}")
    print(f"  Notes       : {cfg.get('notes','')}")
    print("─" * 60 + "\n")


# ── Batch preprocessing ───────────────────────────────────────────────────────

def preprocess_cartridge_folder(folder_path: str,
                                 debug: bool = False) -> dict:
    """
    Preprocess all 4 images in a cartridge folder.
    Returns dict keyed by image_type: {holes, neck, dab, mixing}

    Usage:
        results = preprocess_cartridge_folder("./1/", debug=True)
        holes_edges = results["holes"]["edges"]
        neck_edges  = results["neck"]["edges"]
    """
    folder  = Path(folder_path)
    results = {}

    # Case-insensitive file search
    all_files = list(folder.glob("*.png")) + list(folder.glob("*.PNG"))

    for fpath in sorted(all_files):
        img_type = detect_image_type(str(fpath))
        print(f"  Processing {fpath.name}  [{img_type}] ...")
        try:
            result = preprocess(str(fpath), image_type=img_type)
            print_image_info(result)
            if debug:
                save_debug_outputs(result, out_dir=str(folder / "debug"))
            results[img_type] = result
        except Exception as e:
            print(f"  ✗ Error processing {fpath.name}: {e}")

    missing = [t for t in ["holes", "neck", "dab", "mixing"]
               if t not in results]
    if missing:
        print(f"  ⚠  Missing image types: {missing}")

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Achira Beta Cartridge — Image Preprocessing (ACMCTA001)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single image with debug output
  python preprocess.py --image Holes_ch00.png --debug

  # Single image, specify type explicitly
  python preprocess.py --image neck_ch00.png --type neck --debug

  # Entire cartridge folder
  python preprocess.py --folder ./1/ --debug

  # Batch — all cartridge folders
  python preprocess.py --batch ./BASEPLATE/ --debug
        """
    )
    parser.add_argument("--image",  help="Path to single PNG image")
    parser.add_argument("--type",   choices=list(CONFIGS.keys()),
                        help="Override image type detection")
    parser.add_argument("--folder", help="Process all images in a cartridge folder")
    parser.add_argument("--batch",  help="Process all numbered subfolders in a batch folder")
    parser.add_argument("--debug",  action="store_true",
                        help="Save debug output images")
    parser.add_argument("--outdir", default=None,
                        help="Output directory for debug images")

    args = parser.parse_args()

    if args.image:
        print(f"\n  Preprocessing: {args.image}")
        result = preprocess(args.image, image_type=args.type)
        print_image_info(result)
        if args.debug:
            save_debug_outputs(result, out_dir=args.outdir)
        print("  ✓ Done.")

    elif args.folder:
        print(f"\n  Preprocessing cartridge folder: {args.folder}")
        preprocess_cartridge_folder(args.folder, debug=args.debug)
        print("  ✓ Done.")

    elif args.batch:
        batch = Path(args.batch)
        subfolders = sorted([d for d in batch.iterdir() if d.is_dir()])
        print(f"\n  Batch preprocessing: {len(subfolders)} cartridge folders")
        for sf in subfolders:
            print(f"\n── Cartridge: {sf.name} ──")
            preprocess_cartridge_folder(str(sf), debug=args.debug)
        print("\n  ✓ Batch complete.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()