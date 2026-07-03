"""
leica_calibration.py
=====================
Calibration subsystem for the Achira Beta Cartridge QC pipeline.

PURPOSE
-------
Decides which mm-per-pixel scale factor to use for a given image, and
records/logs which source was used. Does NOT perform feature detection,
edge detection, or PASS/FAIL evaluation -- detect_features.py's detection
functions are unchanged and unaware of where mm_per_px came from.

CALIBRATION MODES
------------------
  "json"      (default) -- always use calibration.json. Identical to the
              pipeline's behavior before this module existed. No Leica
              MetaData is even required to be present.
  "metadata"  -- always use Leica LAS AF MetaData XML. Raises
              LeicaMetadataRequiredError if no usable MetaData is found
              for this image -- this mode never silently falls back.
  "auto"      -- use Leica MetaData if a usable file is present next to
              the image, otherwise fall back to calibration.json exactly
              as "json" mode would.

CROSS-CHECK
-----------
Whenever BOTH a calibration.json entry and a usable Leica MetaData file
are available for an image -- regardless of which one is actually
selected as the source for that call -- the two scale factors are
compared and logged. A difference greater than 1% is logged as a
warning. This runs in every mode; it only affects logging, never which
value is returned.

BACKGROUND
----------
Investigation of Leica MetaData XML across cartridges 1-12 (the only
folders with MetaData present in the E:\\1-33 validation dataset) showed
a pixel scale of ~2.593 um/px, consistent across all four image types
and all 12 cartridges to within 0.0002 um/px. This differs from
calibration.json's manually click-derived values by roughly -3.6%
(holes/DAB/mixing) and +2.9% (neck), which was shown in a controlled
experiment to flip a meaningful number of PASS/FAIL decisions on real
data -- see the calibration-isolation report for details.
"""

import logging
import re
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("leica_calibration")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("  [CALIBRATION] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


VALID_MODES = ("json", "metadata", "auto")


class LeicaMetadataRequiredError(RuntimeError):
    """
    Raised when calibration_mode="metadata" but no usable Leica MetaData
    XML could be found or parsed for the requested image. This mode
    never falls back -- that is the point of requesting it explicitly.
    """


# Image-type key -> expected MetaData XML stem (case-insensitive match).
_METADATA_STEM = {
    "holes":  "holes",
    "neck":   "neck",
    "dab":    "dab",
    "mixing": "mixing",
}

_DIM_RE = re.compile(
    r'<DimensionDescription\s+DimID="(\d+)"\s+NumberOfElements="(\d+)"\s+'
    r'Origin="([^"]*)"\s+Length="([^"]*)"\s+Unit="([^"]*)"'
)


# ── Leica MetaData lookup / parsing ──────────────────────────────────────────

def find_metadata_xml(image_path: str, image_type: str) -> Optional[Path]:
    """
    Look for a Leica MetaData XML file (e.g. MetaData/Holes.xml) in a
    "MetaData" folder next to the given image. Returns the path if found,
    else None.

    Only matches the plain "<Type>.xml" file by exact (case-insensitive)
    stem -- deliberately does NOT match "<Type>_Properties.xml" or
    "<Type>_Properties_*.xsl" sidecar files, which use a different XML
    schema and do not carry the DimensionDescription fields this module
    depends on.
    """
    meta_dir = Path(image_path).parent / "MetaData"
    if not meta_dir.is_dir():
        return None

    stem = _METADATA_STEM.get(image_type, image_type).lower()
    for f in meta_dir.glob("*.xml"):
        if f.stem.lower() == stem:
            return f
    return None


def parse_leica_pixel_scale(xml_path: Path) -> Optional[dict]:
    """
    Parse a Leica LAS AF "<Type>.xml" metadata file and derive the
    sample-plane mm-per-pixel scale from its DimensionDescription blocks:

        um_per_px (axis) = Length[m] / NumberOfElements[px] * 1e6

    averaged over the two spatial axes (X, Y).

    These files are plain UTF-8/ASCII with no byte-order mark (verified
    directly on the real dataset) -- NOT UTF-16, despite superficially
    resembling it when misdecoded.

    Returns None (never raises) if the file cannot be read, is not valid
    text, or does not contain at least two spatial DimensionDescription
    blocks in meters -- callers must treat this as "metadata unavailable".
    """
    try:
        text = xml_path.read_text(encoding="utf-8", errors="strict")
    except Exception as e:
        logger.warning(f"Could not read {xml_path}: {e}")
        return None

    dims = []
    for dim_id, n, _origin, length, unit in _DIM_RE.findall(text):
        try:
            dims.append({
                "DimID": int(dim_id),
                "NumberOfElements": int(n),
                "Length": float(length),
                "Unit": unit,
            })
        except ValueError:
            continue

    spatial = [d for d in dims if d["Unit"] == "m" and d["NumberOfElements"] > 0][:2]
    if len(spatial) < 2:
        logger.warning(
            f"No usable DimensionDescription (2 spatial axes in meters) "
            f"found in {xml_path}"
        )
        return None

    um_per_px_axes = [(d["Length"] / d["NumberOfElements"]) * 1e6 for d in spatial]
    mean_um_per_px = sum(um_per_px_axes) / len(um_per_px_axes)

    def _attr(name):
        m = re.search(rf'{name}="([^"]*)"', text)
        return m.group(1).strip() if m else None

    return {
        "mm_per_px":          mean_um_per_px / 1000.0,
        "um_per_px":          mean_um_per_px,
        "um_per_px_x":        um_per_px_axes[0],
        "um_per_px_y":        um_per_px_axes[1],
        "system_type":        _attr("SystemTypeName"),
        "objective":          _attr("ObjectiveName"),
        "magnification":      _attr("Magnification"),
        "numerical_aperture": _attr("NumericalAperture"),
        "source_file":        str(xml_path),
    }


def _metadata_lookup(image_path: str, image_type: str) -> Optional[dict]:
    """Find + parse Leica MetaData for this image. Returns None on any failure."""
    xml_path = find_metadata_xml(image_path, image_type)
    if xml_path is None:
        return None
    parsed = parse_leica_pixel_scale(xml_path)
    if parsed is None:
        logger.warning(
            f"{image_type.upper()}: MetaData XML found ({xml_path.name}) but "
            f"could not be parsed."
        )
    return parsed


# ── calibration.json lookup (unchanged behavior, relocated) ─────────────────

def _lookup_calibration_json(calibration: dict, image_type: str) -> dict:
    """
    calibration.json lookup -- behavior identical to the logic previously
    inlined in detect_features.detect(). Raises KeyError if calibration.json
    genuinely has nothing usable for this image type (same as before).
    """
    cal_lower = {k.lower(): v for k, v in calibration.items()}

    if "scale_factor_mm_per_px" in calibration:
        # Old flat format -- direct key
        return {"mm_per_px": calibration["scale_factor_mm_per_px"], "matched_key": None}

    if image_type in cal_lower and isinstance(cal_lower[image_type], dict):
        # New nested format -- keyed by image type (case-insensitive)
        return {"mm_per_px": cal_lower[image_type]["scale_factor_mm_per_px"],
                "matched_key": image_type}

    if "last_calibrated" in calibration:
        last_type = calibration["last_calibrated"]["image_type"]
        logger.warning(
            f"No calibration.json entry for '{image_type}' -- using "
            f"'{last_type}' scale instead."
        )
        return {"mm_per_px": cal_lower[last_type]["scale_factor_mm_per_px"],
                "matched_key": last_type}

    raise KeyError(
        f"Cannot find scale_factor_mm_per_px in calibration file for image "
        f"type '{image_type}'.\n"
        f"Run: python calibrate.py calibrate --ref {image_type}_ch00.png --feature hole"
    )


def _try_calibration_json(calibration: dict, image_type: str) -> Optional[dict]:
    """Best-effort calibration.json lookup used for cross-checking. Never raises."""
    try:
        return _lookup_calibration_json(calibration, image_type)
    except KeyError:
        return None


# ── Cross-check ───────────────────────────────────────────────────────────────

def _cross_check(image_type: str, metadata_info: Optional[dict],
                  json_info: Optional[dict]) -> Optional[float]:
    """
    If both sources are available, log their percentage difference and
    warn if it exceeds 1%. Returns the pct diff (metadata vs json), or
    None if only one (or neither) source is available.
    """
    if metadata_info is None or json_info is None:
        return None

    m_scale = metadata_info["mm_per_px"]
    j_scale = json_info["mm_per_px"]
    if j_scale == 0:
        return None
    pct_diff = (m_scale - j_scale) / j_scale * 100

    logger.info(
        f"{image_type.upper()}: calibration cross-check -- "
        f"metadata={m_scale*1000:.5f} um/px  json={j_scale*1000:.5f} um/px  "
        f"diff={pct_diff:+.3f}%"
    )
    if abs(pct_diff) > 1.0:
        logger.warning(
            f"{image_type.upper()}: metadata and calibration.json scales differ by "
            f"{pct_diff:+.2f}% (exceeds 1% threshold) -- consider re-calibrating "
            f"or investigating which source is stale."
        )
    return pct_diff


# ── Main entry point ──────────────────────────────────────────────────────────

def resolve_scale_factor(image_path: str, image_type: str, calibration: dict,
                          calibration_mode: str = "json") -> dict:
    """
    Decide which mm-per-pixel value to use for this image, per
    calibration_mode ("json" | "metadata" | "auto" -- see module docstring).

    Always logs which source was used. Whenever both calibration.json and
    Leica MetaData are available, logs their percentage difference and
    warns if it exceeds 1%, regardless of calibration_mode.

    Returns
    -------
    dict:
      {
        "mm_per_px":           float,
        "source":              "leica_metadata" | "calibration_json",
        "detail":              {...}   # source-specific info for traceability
        "cross_check_pct_diff": float | None,
      }

    Raises
    ------
    ValueError                   if calibration_mode is not recognized.
    LeicaMetadataRequiredError    if calibration_mode="metadata" and no
                                  usable Leica MetaData was found.
    KeyError                     if calibration.json is needed (mode="json",
                                  or mode="auto" with no MetaData available)
                                  and has nothing usable for this image type.
    """
    if calibration_mode not in VALID_MODES:
        raise ValueError(
            f"Invalid calibration_mode {calibration_mode!r}; must be one of {VALID_MODES}"
        )

    metadata_info = _metadata_lookup(image_path, image_type)
    json_info = _try_calibration_json(calibration, image_type)

    pct_diff = _cross_check(image_type, metadata_info, json_info)

    if calibration_mode == "metadata":
        if metadata_info is None:
            raise LeicaMetadataRequiredError(
                f"calibration_mode='metadata' requires a usable Leica MetaData XML "
                f"for image type '{image_type}', but none was found/parseable "
                f"next to {image_path}"
            )
        logger.info(
            f"{image_type.upper()}: calibration_mode=metadata -- using LEICA METADATA "
            f"({metadata_info['um_per_px']:.5f} um/px)"
        )
        return {"mm_per_px": metadata_info["mm_per_px"], "source": "leica_metadata",
                "detail": metadata_info, "cross_check_pct_diff": pct_diff}

    if calibration_mode == "json":
        if json_info is None:
            # Re-raise with the original, informative KeyError message.
            _lookup_calibration_json(calibration, image_type)
        logger.info(
            f"{image_type.upper()}: calibration_mode=json -- using CALIBRATION.JSON "
            f"({json_info['mm_per_px']*1000:.5f} um/px)"
        )
        return {"mm_per_px": json_info["mm_per_px"], "source": "calibration_json",
                "detail": json_info, "cross_check_pct_diff": pct_diff}

    # calibration_mode == "auto"
    if metadata_info is not None:
        logger.info(
            f"{image_type.upper()}: calibration_mode=auto -- MetaData available, "
            f"using LEICA METADATA ({metadata_info['um_per_px']:.5f} um/px)"
        )
        return {"mm_per_px": metadata_info["mm_per_px"], "source": "leica_metadata",
                "detail": metadata_info, "cross_check_pct_diff": pct_diff}

    if json_info is not None:
        logger.info(
            f"{image_type.upper()}: calibration_mode=auto -- no MetaData, "
            f"falling back to CALIBRATION.JSON ({json_info['mm_per_px']*1000:.5f} um/px)"
        )
        return {"mm_per_px": json_info["mm_per_px"], "source": "calibration_json",
                "detail": json_info, "cross_check_pct_diff": pct_diff}

    # Neither source available -- raise the informative calibration.json error.
    _lookup_calibration_json(calibration, image_type)
