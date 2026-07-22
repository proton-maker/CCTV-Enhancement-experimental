#!/usr/bin/env python3
"""Paths and helpers for work/datasets + work/labs testing layout."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
DATASETS = WORK / "datasets"
LABS = WORK / "labs"
BAKEOFF_DOCS = WORK / "bakeoff"

DATASET_ALIASES: dict[str, str] = {
    "cut2": "cut2",
    "cut2-bakeoff": "cut2",
    "cut-motor-2308": "cut-motor-2308",
    "cut-motor-2308-bakeoff": "cut-motor-2308",
    "motor": "cut-motor-2308",
}


def normalize_dataset(name: str) -> str:
    key = name.strip().replace("\\", "/").rstrip("/")
    if key.startswith("work/"):
        key = key[len("work/") :]
    if key.startswith("datasets/"):
        key = key[len("datasets/") :]
    if key.endswith("-bakeoff"):
        key = key[: -len("-bakeoff")]
    return DATASET_ALIASES.get(key, DATASET_ALIASES.get(name, key))


def dataset_dir(name: str) -> Path:
    return DATASETS / normalize_dataset(name)


def dataset_src(name: str) -> Path:
    return dataset_dir(name) / "src"


def labs_for(name: str) -> Path:
    return LABS / normalize_dataset(name)


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len] or "run").rstrip("-")


def list_labs(dataset: str) -> list[Path]:
    base = labs_for(dataset)
    if not base.exists():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and p.name.startswith("lab-"))


def next_lab_number(dataset: str) -> int:
    labs = list_labs(dataset)
    if not labs:
        return 1
    nums = []
    for p in labs:
        m = re.match(r"lab-(\d+)", p.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums, default=0) + 1


def lab_dir(dataset: str, lab: str | None = None, new_slug: str | None = None) -> Path:
    """Resolve or create a lab folder under work/labs/<dataset>/."""
    ds = normalize_dataset(dataset)
    if lab:
        path = labs_for(ds) / lab
        if not path.exists():
            raise FileNotFoundError(f"Lab not found: {path}")
        return path
    if not new_slug:
        new_slug = "run"
    n = next_lab_number(ds)
    path = labs_for(ds) / f"lab-{n:03d}-{slugify(new_slug)}"
    path.mkdir(parents=True, exist_ok=False)
    write_manifest(path, dataset=ds, label=new_slug, created=True)
    return path


def write_manifest(
    lab_path: Path,
    *,
    dataset: str,
    label: str = "",
    created: bool = False,
    extra: dict | None = None,
) -> Path:
    manifest = lab_path / "manifest.json"
    data: dict = {}
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
    if created or "created_utc" not in data:
        data["created_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["dataset"] = normalize_dataset(dataset)
    data["lab"] = lab_path.name
    if label:
        data["label"] = label
    data["updated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if extra:
        data.update(extra)
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return manifest


def resolve_lab_root(
    dataset: str,
    lab: str | None = None,
    new_lab: str | None = None,
    legacy_bakeoff: Path | None = None,
) -> tuple[Path, Path]:
    """
    Return (dataset_root, lab_root).
    lab_root contains outputs/, compare/, intermediate/, manifest.json.
    """
    ds_root = dataset_dir(dataset)
    if legacy_bakeoff is not None:
        # Back-compat: treat old *-bakeoff folder as lab if it has outputs/
        return ds_root, legacy_bakeoff.resolve()
    if new_lab is not None:
        return ds_root, lab_dir(dataset, new_slug=new_lab)
    if lab is not None:
        return ds_root, lab_dir(dataset, lab=lab)
    # Default: latest lab or create lab-001
    existing = list_labs(dataset)
    if existing:
        return ds_root, existing[-1]
    return ds_root, lab_dir(dataset, new_slug="initial")


FOCUS_GOALS: dict[str, dict] = {
    "plate": {
        "readme_goal": "License plate characters readable",
        "tools": "A crop plate → B CLAHE → C PyTorch SR ×3",
        "chain": ["01-A-plate-crop", "02-B-clahe", "03-C-sr-x3", "04-final"],
        "stages": ["B04-clahe-brighten", "C13-plate-pytorch-sr-x3"],
        "avoid": "Rear-tire crop (y>0.85); CodeFormer; ncnn ×2",
        "verify": "Check datasets/*/crops/plate_ref.png before lab run",
    },
    "face": {
        "readme_goal": "Face features more visible (investigative only)",
        "tools": "A crop face → B CLAHE → C PyTorch SR ×2 → D CodeFormer (optional)",
        "chain": ["01-A-face-crop", "02-B-clahe", "03-C-sr-x2", "04-D-codeformer", "05-final"],
        "stages": ["B04-clahe-brighten", "C14-face-pytorch-sr-x2", "E30-codeformer-facezoom"],
        "avoid": "Generative output as forensic evidence; double-crop on SR output",
        "verify": "Check datasets/*/crops/face_ref.png",
    },
    "motor": {
        "readme_goal": "Vehicle outline / red fairing / wheels clearer",
        "tools": "A baseline → B CLAHE → (Upscayl) → C PyTorch SR",
        "chain": ["01-A-baseline", "02-B-clahe", "03-upscayl", "04-C-sr-x2", "05-final"],
        "stages": ["B01-rvrt-deblur", "B04-clahe-brighten", "C12-pytorch-sr-x2", "D20-rvrt-then-sr"],
        "avoid": "CodeFormer on vehicle body",
        "verify": "RVRT needs MSVC — scripts/run_rvrt_deblur.bat",
    },
    "scene": {
        "readme_goal": "Full-frame context (stall, lighting, composition)",
        "tools": "A full frame → C PyTorch SR ×2",
        "chain": ["01-A-full", "02-C-sr-x2", "03-final"],
        "stages": ["C15-scene-pytorch-sr-x2"],
        "avoid": "Face tools on uncropped 1080p",
        "verify": "Requires datasets/*/full/",
    },
    "brighten": {
        "readme_goal": "Lift shadows / uneven lighting (forensic-safe)",
        "tools": "A baseline → B CLAHE (+ optional denoise)",
        "chain": ["01-A-baseline", "02-B-clahe", "03-final"],
        "stages": ["B04-clahe-brighten", "B03-opencv-denoise"],
        "avoid": "Upscale before brighten",
        "verify": None,
    },
}

# Linear A→B→C→D chains → outputs/chains/<goal>/ (default lab mode)
PIPELINE_CHAINS: dict[str, list[tuple[str, str]]] = {
    "plate": [
        ("01-A-plate-crop", "Crop front plate (meta.json focus_regions — NOT rear tire)"),
        ("02-B-clahe", "CLAHE brighten on plate crop"),
        ("03-C-sr-x3", "PyTorch Real-ESRGAN ×3"),
        ("04-final", "Forensic output"),
    ],
    "face": [
        ("01-A-face-crop", "Crop rider head (top of ROI)"),
        ("02-B-clahe", "CLAHE brighten on face crop"),
        ("03-C-sr-x2", "PyTorch Real-ESRGAN ×2"),
        ("04-D-codeformer", "CodeFormer w=0.9 (skip if 0 faces)"),
        ("05-final", "Best forensic face output"),
    ],
    "motor": [
        ("01-A-baseline", "Full ROI baseline"),
        ("02-B-clahe", "CLAHE brighten"),
        ("03-upscayl", "Upscayl Ultrasharp ×2 (optional — skip if not installed)"),
        ("04-C-sr-x2", "PyTorch Real-ESRGAN ×2"),
        ("05-final", "Best motor output"),
    ],
    "scene": [
        ("01-A-full", "Full 1080p frame"),
        ("02-C-sr-x2", "PyTorch Real-ESRGAN ×2"),
        ("03-final", "Scene output"),
    ],
    "brighten": [
        ("01-A-baseline", "ROI baseline"),
        ("02-B-clahe", "CLAHE + gamma"),
        ("03-final", "Brightened output"),
    ],
}

ALL_GOALS = ("plate", "face", "motor", "scene", "brighten")


def compare_docs_dir(dataset: str, lab_name: str) -> Path:
    """Comparison PNGs live inside the lab; README picks from work/bakeoff/ when promoted."""
    return labs_for(dataset) / lab_name / "compare"
