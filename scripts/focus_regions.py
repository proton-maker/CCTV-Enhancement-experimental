#!/usr/bin/env python3
"""ROI sub-regions for plate / face crops — driven by dataset meta.json, not blind fractions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

# Default fractions (0–1) inside the motorcycle ROI src crop.
# cut-motor-2308: rider faces camera; plate is on FRONT fender below headlight — NOT the rear tire.
DEFAULT_REGIONS: dict[str, dict[str, float]] = {
    "plate": {"x1": 0.28, "y1": 0.55, "x2": 0.72, "y2": 0.73},
    "face": {"x1": 0.18, "y1": 0.02, "x2": 0.82, "y2": 0.36},
}

# WRONG — old bakeoff pointed here (rear wheel). Never use for front-facing stall ROI.
PLATE_REGION_WRONG_REAR_TIRE = {"x1": 0.22, "y1": 0.48, "x2": 0.78, "y2": 0.92}


def load_meta(dataset_dir: Path) -> dict[str, Any]:
    meta_path = dataset_dir / "meta.json"
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def region_fracs(meta: dict[str, Any] | None, name: str) -> dict[str, float]:
    """Return normalized crop box for region `plate` or `face`."""
    if meta:
        regions = meta.get("focus_regions") or {}
        if name in regions:
            r = regions[name]
            return {k: float(r[k]) for k in ("x1", "y1", "x2", "y2")}
    return dict(DEFAULT_REGIONS[name])


def crop_region(
    img: np.ndarray,
    name: str,
    meta: dict[str, Any] | None = None,
    *,
    zoom: int = 1,
) -> np.ndarray:
    """Crop a sub-region from ROI image; optional LANCZOS zoom after crop."""
    h, w = img.shape[:2]
    r = region_fracs(meta, name)
    x1 = max(0, int(w * r["x1"]))
    y1 = max(0, int(h * r["y1"]))
    x2 = min(w, int(w * r["x2"]))
    y2 = min(h, int(h * r["y2"]))
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Invalid {name} region {r} on {w}x{h}")
    patch = img[y1:y2, x1:x2]
    if zoom > 1:
        patch = cv2.resize(
            patch,
            (patch.shape[1] * zoom, patch.shape[0] * zoom),
            interpolation=cv2.INTER_LANCZOS4,
        )
    return patch


def draw_regions_overlay(img: np.ndarray, meta: dict[str, Any] | None = None) -> np.ndarray:
    """Debug image: green=plate, cyan=face."""
    out = img.copy()
    h, w = out.shape[:2]
    colors = {"plate": (0, 255, 0), "face": (255, 255, 0)}
    for name, color in colors.items():
        r = region_fracs(meta, name)
        x1, y1 = int(w * r["x1"]), int(h * r["y1"])
        x2, y2 = int(w * r["x2"]), int(h * r["y2"])
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        cv2.putText(out, name, (x1 + 4, max(16, y1 + 16)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return out


def extract_focus_patch(img: np.ndarray, focus: str, meta: dict[str, Any] | None = None) -> np.ndarray:
    """Patch for compare grids. Scene/motor/brighten use full frame; plate/face use meta regions."""
    if focus in ("scene", "motor", "brighten"):
        return img
    zoom = 3 if focus == "plate" else 2
    return crop_region(img, focus, meta, zoom=zoom)


def write_region_refs(src_dir: Path, crops_dir: Path, meta: dict[str, Any] | None = None) -> None:
    """Save crops/plate_ref.png, face_ref.png, regions_overlay.png for visual QA."""
    crops_dir.mkdir(parents=True, exist_ok=True)
    for fp in sorted(src_dir.glob("frame_*.png")):
        img = cv2.imread(str(fp))
        if img is None:
            continue
        stem = fp.stem
        cv2.imwrite(str(crops_dir / f"plate_{stem}.png"), crop_region(img, "plate", meta, zoom=3))
        cv2.imwrite(str(crops_dir / f"face_{stem}.png"), crop_region(img, "face", meta, zoom=2))
        if stem == "frame_002":
            cv2.imwrite(str(crops_dir / "plate_ref.png"), crop_region(img, "plate", meta, zoom=3))
            cv2.imwrite(str(crops_dir / "face_ref.png"), crop_region(img, "face", meta, zoom=2))
            cv2.imwrite(str(crops_dir / "regions_overlay.png"), draw_regions_overlay(img, meta))
    return None


def default_focus_regions_meta() -> dict[str, dict]:
    return {
        "plate": {
            **DEFAULT_REGIONS["plate"],
            "note": "Front plate below headlight — NOT rear tire (y>0.85 is wrong)",
        },
        "face": {
            **DEFAULT_REGIONS["face"],
            "note": "Rider head/helmet at top of ROI",
        },
    }
