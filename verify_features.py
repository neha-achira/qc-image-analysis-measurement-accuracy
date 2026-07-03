# =============================================================================
# verify_features.py
# Claude API Visual Verification Layer — Achira Beta Cartridge QC
# PROC-33
#
# Sends the annotated detected image + detection metadata to Claude API.
# Claude reasons about whether each detected circle is placed on a real
# hole (not a channel, teardrop, dust speck, or stitching artifact).
#
# Usage (standalone):
#   python verify_features.py --image Holes_ch00_detected.png \
#       --n_detected 7 --n_expected 7 --image_type holes
#
# Usage (from detect_features.py via --verify flag):
#   python detect_features.py --image Holes_ch00.png \
#       --cal calibration.json --verify --debug
# =============================================================================

import base64
import json
import os
import urllib.request
import urllib.error


# =============================================================================
# CONSTANTS
# =============================================================================

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL   = "claude-sonnet-4-20250514"
MAX_TOKENS     = 1024

# Trigger verification when any of these conditions are true:
# - detected count differs from expected
# - any hole has large deviation (> threshold)
# - --verify flag is always-on
LARGE_DEV_THRESHOLD_MM = 0.03   # flag if any hole deviates > 0.03mm


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """You are a quality control vision expert for PMMA microfluidic cartridges.

You will be shown a microscope image of a cartridge with colored circles drawn by an
automated detection algorithm. Your job is to verify whether each circle is correctly
placed on a real hole (through-hole in the PMMA) or incorrectly placed on something else.

Real holes appear as:
- A bright white or light grey circular interior (the through-hole letting light through)
- Surrounded by a dark ring (the hole wall)
- Sometimes with a "teardrop" or landing-pad shape around them from the channel entry
- Approximately circular, clean edges

False detections look like:
- Channel lines (long thin dark lines) — NOT holes
- Circular chamber rings (large dark circles with grey interior) — NOT the hole itself
- Dust specks or bubbles (very small, irregular) — NOT holes
- Stitching artifacts (rectangular boundary lines) — NOT holes
- The outer teardrop/landing-pad shape around a hole (too large) — NOT the hole interior

Respond ONLY with valid JSON in exactly this format, no other text:
{
  "verified": true,
  "n_correct": 7,
  "n_incorrect": 0,
  "circles": [
    {"tag": 1, "correct": true, "confidence": "high", "notes": ""},
    {"tag": 2, "correct": false, "confidence": "high", "notes": "Circle is on channel line, not a hole"}
  ],
  "summary": "Brief overall assessment"
}

confidence must be one of: "high", "medium", "low"
verified = true only if ALL circles are correct"""


# =============================================================================
# IMAGE ENCODING
# =============================================================================

def encode_image_b64(image_path: str, max_px: int = 2000) -> str:
    """
    Load image, downscale if needed, encode as base64 PNG.
    Claude works well at 2000px — no need for full-res.
    """
    import cv2
    import numpy as np

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {image_path}")

    h, w = img.shape[:2]
    if max(h, w) > max_px:
        scale = max_px / max(h, w)
        img   = cv2.resize(img, (int(w*scale), int(h*scale)),
                           interpolation=cv2.INTER_AREA)

    _, buf = cv2.imencode(".png", img)
    return base64.b64encode(buf.tobytes()).decode("utf-8")


# =============================================================================
# BUILD USER PROMPT
# =============================================================================

def build_prompt(image_type: str,
                 n_detected: int,
                 n_expected: int,
                 circles: list) -> str:
    """Build the user prompt with detection context."""

    lines = [
        f"Image type: {image_type}",
        f"Expected holes: {n_expected}",
        f"Detected holes: {n_detected}",
        f"Nominal hole diameter: 0.50mm",
        "",
        "Detected circles:",
    ]

    for c in circles:
        tag  = c.get("dwg_tag", c.get("id", "?"))
        d_mm = c.get("diameter_mm", "?")
        dev  = c.get("deviation_mm", "?")
        pf   = "PASS" if c.get("pass", False) else "FAIL"
        cx   = int(c.get("cx_px", 0))
        cy   = int(c.get("cy_px", 0))
        lines.append(
            f"  Tag {tag}: diameter={d_mm}mm  dev={dev:+.4f}mm  "
            f"{pf}  center=({cx},{cy}px)"
        )

    lines += [
        "",
        "The annotated image shows these circles drawn on the microscope image.",
        "Green circles = PASS, Red circles = FAIL.",
        "Please verify each circle is correctly placed on a real through-hole.",
    ]

    return "\n".join(lines)


# =============================================================================
# CALL CLAUDE API
# =============================================================================

def call_claude(image_b64: str, prompt: str) -> dict:
    """
    Call Claude API with the annotated image and prompt.
    Returns the parsed JSON response.
    """
    payload = {
        "model":      CLAUDE_MODEL,
        "max_tokens": MAX_TOKENS,
        "system":     SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type":       "base64",
                            "media_type": "image/png",
                            "data":       image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    }

    data    = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type":      "application/json",
        "anthropic-version": "2023-06-01",
    }

    req = urllib.request.Request(
        CLAUDE_API_URL,
        data=data,
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    # Extract text content
    text = ""
    for block in raw.get("content", []):
        if block.get("type") == "text":
            text += block["text"]

    # Parse JSON response
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text  = "\n".join(
            l for l in lines
            if not l.strip().startswith("```")
        )

    return json.loads(text)


# =============================================================================
# SHOULD VERIFY?
# =============================================================================

def should_verify(result: dict, n_expected: int,
                  always: bool = False) -> bool:
    """
    Decide whether to call Claude API for this result.

    Triggers:
    - always=True (--verify flag)
    - detected count != expected
    - any hole deviates > LARGE_DEV_THRESHOLD_MM
    - any hole is FAIL
    """
    if always:
        return True

    n_det = result.get("n_detected", 0)
    if n_det != n_expected:
        return True

    for c in result.get("circles", []) + result.get("holes", []):
        dev = abs(c.get("deviation_mm", 0) or 0)
        if dev > LARGE_DEV_THRESHOLD_MM:
            return True
        if not c.get("pass", True):
            return True

    return False


# =============================================================================
# MAIN VERIFY FUNCTION
# =============================================================================

def verify_detection(annotated_image_path: str,
                     image_type: str,
                     detection_result: dict,
                     n_expected: int,
                     always: bool = False) -> dict:
    """
    Run Claude verification on a detection result.

    Parameters
    ----------
    annotated_image_path : str
        Path to the annotated _detected.png image
    image_type : str
        'holes' | 'dab' | 'mixing' | 'neck'
    detection_result : dict
        The dict returned by detect_holes/detect_dab/detect_mixing
    n_expected : int
        Expected number of features (from REF_OFFSETS or design)
    always : bool
        If True, always verify regardless of result quality

    Returns
    -------
    dict with keys:
        verified        : bool — all circles confirmed correct
        n_correct       : int
        n_incorrect     : int
        circles         : list of per-tag verdicts
        summary         : str
        triggered       : bool — whether API was actually called
        error           : str — set if API call failed
    """

    # Check if we should verify
    if not should_verify(detection_result, n_expected, always=always):
        return {
            "verified":   True,
            "n_correct":  detection_result.get("n_detected", 0),
            "n_incorrect":0,
            "circles":    [],
            "summary":    "Skipped — detection looks clean",
            "triggered":  False,
            "error":      None,
        }

    if not os.path.exists(annotated_image_path):
        return {
            "verified":   None,
            "n_correct":  None,
            "n_incorrect":None,
            "circles":    [],
            "summary":    "Skipped — annotated image not found",
            "triggered":  False,
            "error":      f"File not found: {annotated_image_path}",
        }

    # Get circles list (normalise across image types)
    circles = (
        detection_result.get("circles") or
        detection_result.get("holes") or
        []
    )

    # DAB is a single result not a list
    if image_type == "dab" and not circles:
        circles = [{
            "dwg_tag":      "DAB",
            "diameter_mm":  detection_result.get("diameter_mm"),
            "deviation_mm": detection_result.get("deviation_mm"),
            "pass":         detection_result.get("pass"),
            "cx_px":        detection_result.get("cx_px"),
            "cy_px":        detection_result.get("cy_px"),
        }]

    print(f"  [VERIFY] Calling Claude API for {image_type} "
          f"({len(circles)} features, "
          f"n_det={detection_result.get('n_detected',len(circles))} "
          f"n_exp={n_expected})...")

    try:
        image_b64 = encode_image_b64(annotated_image_path)
        prompt    = build_prompt(image_type, len(circles), n_expected, circles)
        response  = call_claude(image_b64, prompt)

        response["triggered"] = True
        response["error"]     = None
        print(f"  [VERIFY] Result: verified={response.get('verified')}  "
              f"correct={response.get('n_correct')}/{len(circles)}  "
              f"— {response.get('summary','')}")
        return response

    except urllib.error.HTTPError as e:
        err = f"HTTP {e.code}: {e.reason}"
        print(f"  [VERIFY] API error: {err}")
        return {
            "verified":    None,
            "n_correct":   None,
            "n_incorrect": None,
            "circles":     [],
            "summary":     f"API error: {err}",
            "triggered":   True,
            "error":       err,
        }
    except Exception as e:
        print(f"  [VERIFY] Error: {e}")
        return {
            "verified":    None,
            "n_correct":   None,
            "n_incorrect": None,
            "circles":     [],
            "summary":     f"Error: {e}",
            "triggered":   True,
            "error":       str(e),
        }


# =============================================================================
# ADD VERIFICATION TO CSV ROWS
# =============================================================================

def add_verification_to_rows(rows: list, verification: dict) -> list:
    """
    Stamp verification results onto existing CSV rows.
    Adds: claude_verified, claude_correct, claude_notes columns.
    """
    verified      = verification.get("verified")
    summary       = verification.get("summary", "")
    triggered     = verification.get("triggered", False)
    error         = verification.get("error")
    circle_map    = {
        str(c.get("tag", "")): c
        for c in verification.get("circles", [])
    }

    for row in rows:
        tag       = str(row.get("feature_label", "")).replace("Tag", "").split()[0]
        cv_circle = circle_map.get(tag, {})

        row["claude_triggered"] = triggered
        row["claude_verified"]  = (
            cv_circle.get("correct", verified)
            if triggered else True
        )
        row["claude_confidence"] = cv_circle.get("confidence", "") if triggered else "n/a"
        row["claude_notes"]      = (
            cv_circle.get("notes", "") or
            (summary if not triggered else "")
        )
        if error:
            row["claude_notes"] = f"API error: {error}"

    return rows


# =============================================================================
# CLI (standalone use)
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Claude API visual verification for QC detections"
    )
    parser.add_argument("--image",      required=True,
                        help="Path to annotated _detected.png")
    parser.add_argument("--image_type", default="holes",
                        choices=["holes","dab","mixing","neck"])
    parser.add_argument("--n_detected", type=int, default=0)
    parser.add_argument("--n_expected", type=int, default=7)
    args = parser.parse_args()

    # Minimal mock result for standalone testing
    mock_result = {
        "n_detected": args.n_detected,
        "circles": [
            {"dwg_tag": i+1, "diameter_mm": 0.50,
             "deviation_mm": 0.0, "pass": True,
             "cx_px": 0, "cy_px": 0}
            for i in range(args.n_detected)
        ],
        "overall_pass": True,
    }

    result = verify_detection(
        annotated_image_path=args.image,
        image_type=args.image_type,
        detection_result=mock_result,
        n_expected=args.n_expected,
        always=True,
    )

    print(json.dumps(result, indent=2))
