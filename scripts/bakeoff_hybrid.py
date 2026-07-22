#!/usr/bin/env python3
"""Classified multi-tool bakeoff — each stage has one job (see cctv-adaptive-pipeline skill)."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("pip install pillow opencv-python")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from work_lab import (
    ALL_GOALS,
    FOCUS_GOALS,
    PIPELINE_CHAINS,
    dataset_dir,
    dataset_src,
    normalize_dataset,
    resolve_lab_root,
    write_manifest,
)
from focus_regions import crop_region, extract_focus_patch as region_patch, load_meta

CODEFORMER = ROOT / "tools" / "CodeFormer"
CODEFORMER_PY = [sys.executable, str(CODEFORMER / "inference_codeformer.py")]
REALESRGAN_EXE = ROOT / "tools" / "realesgan" / "realesrgan-ncnn-vulkan.exe"
RVRT = ROOT / "tools" / "RVRT"
UPSCAYL_EXE = ROOT / "tools" / "upscayl-ncnn" / "upscayl-bin-20251207-174704-windows" / "upscayl-bin.exe"
UPSCAYL_MODELS = ROOT / "tools" / "upscayl" / "resources" / "models"
UPSCAYL_MODEL = "ultrasharp-4x"


@dataclass(frozen=True)
class Stage:
    category: str
    folder: str
    title: str
    role: str
    focus: tuple[str, ...] = ()  # README goals: plate, face, motor, scene, brighten


# Numbered folders = sort order. Category letter = tool class.
STAGES: list[Stage] = [
    Stage("A", "A00-baseline-src", "A00 baseline ROI", "Original zoomed ROI", ("motor", "plate", "face")),
    Stage("B", "B01-rvrt-deblur", "B01 RVRT deblur", "Temporal deblur", ("motor",)),
    Stage("B", "B02-rvrt-denoise", "B02 RVRT denoise", "Temporal denoise", ("motor",)),
    Stage("B", "B03-opencv-denoise", "B03 OpenCV denoise", "Forensic denoise", ("brighten", "motor")),
    Stage("B", "B04-clahe-brighten", "B04 CLAHE brighten", "Lift shadows — all goals", ("brighten", "plate", "face", "motor")),
    Stage("C", "C11-realesrgan-s4", "C11 ncnn x4", "ncnn upscale x4", ("motor",)),
    Stage("C", "C12-pytorch-sr-x2", "C12 PyTorch SR x2", "Motor ROI upscale", ("motor", "plate")),
    Stage("C", "C13-plate-pytorch-sr-x3", "C13 plate SR x3", "Plate-zoom → PyTorch SR", ("plate",)),
    Stage("C", "C14-face-pytorch-sr-x2", "C14 face SR x2", "Face-zoom → PyTorch SR", ("face",)),
    Stage("C", "C15-scene-pytorch-sr-x2", "C15 scene SR x2", "Full 1080p upscale", ("scene",)),
    Stage("D", "D20-rvrt-then-sr", "D20 RVRT→SR", "Hybrid deblur then SR", ("motor",)),
    Stage("D", "D22-pytorch-sr-codeformer", "D22 SR→CodeFormer", "Face path hybrid", ("face",)),
    Stage("E", "E30-codeformer-facezoom", "E30 face CodeFormer", "Generative face restore", ("face",)),
]

# ncnn x2 on ROI < ~1000px wide produces tile-mosaic — do not use in bakeoff
NCNN_SKIP_SCALE2_ON_SMALL_ROI = True

OLD_BAD_OUTPUTS = [
    "11-codeformer-w07",
    "11-codeformer-w07-roi",
    "12-codeformer-w05-roi",
    "13-codeformer-yolo",
    "14-codeformer-bg-up",
]


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], cwd: Path | None = None) -> None:
    log("Running: " + " ".join(str(c) for c in cmd))
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)


def frame_paths(folder: Path) -> list[Path]:
    return sorted(folder.glob("frame_*.png"))


def copy_frames(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for f in frame_paths(src):
        shutil.copy2(f, dst / f.name)


def result_image(outputs: Path, stage_folder: str, frame: str) -> Path | None:
    base = outputs / stage_folder
    for rel in (Path("final_results") / frame, Path(frame)):
        p = base / rel
        if p.exists():
            return p
    return None


def make_region_crops(
    src_dir: Path,
    out_dir: Path,
    region: str,
    meta: dict,
    *,
    zoom: int = 1,
) -> None:
    """Plate or face crop from ROI using meta.json focus_regions."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for fp in frame_paths(src_dir):
        img = cv2.imread(str(fp))
        if img is None:
            continue
        patch = crop_region(img, region, meta, zoom=zoom)
        cv2.imwrite(str(out_dir / fp.name), patch)
    log(f"{region}-crop -> {out_dir}")


def make_plate_zoom(src_dir: Path, out_dir: Path, meta: dict | None = None) -> None:
    make_region_crops(src_dir, out_dir, "plate", meta or {}, zoom=3)


def make_face_zoom(src_dir: Path, out_dir: Path, meta: dict | None = None, **_kwargs) -> None:
    make_region_crops(src_dir, out_dir, "face", meta or {}, zoom=2)


def run_clahe_brighten(src: Path, out_dir: Path, clip: float = 2.5, gamma: float = 1.12) -> None:
    """Forensic-safe shadow lift — run before upscale."""
    out_dir.mkdir(parents=True, exist_ok=True)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
    for fp in frame_paths(src):
        img = cv2.imread(str(fp))
        if img is None:
            continue
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = clahe.apply(l)
        out = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        out = np.clip(np.power(out.astype(np.float32) / 255.0, 1.0 / gamma) * 255.0, 0, 255).astype(np.uint8)
        cv2.imwrite(str(out_dir / fp.name), out)
    log(f"CLAHE brighten -> {out_dir}")


def extract_focus_patch(img: np.ndarray, focus: str, meta: dict | None = None) -> np.ndarray:
    """Crop+zoom patch for goal-specific comparison grids (uses meta.json regions)."""
    return region_patch(img, focus, meta)


def run_realesrgan(src: Path, out_dir: Path, scale: int, tile: int = 128) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    run(
        [
            str(REALESRGAN_EXE),
            "-i",
            str(src),
            "-o",
            str(out_dir),
            "-n",
            "realesrgan-x4plus",
            "-s",
            str(scale),
            "-g",
            "1",
            "-f",
            "png",
            "-t",
            str(tile),
            "-v",
        ]
    )


def run_pytorch_sr(src: Path, out_dir: Path, outscale: float = 2) -> None:
    import torch
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from basicsr.utils.realesrgan_utils import RealESRGANer

    weight = CODEFORMER / "weights" / "realesrgan" / "RealESRGAN_x2plus.pth"
    if not weight.exists():
        raise FileNotFoundError(f"Missing {weight} — run CodeFormer weight download")

    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=2)
    upsampler = RealESRGANer(
        scale=2,
        model_path=str(weight),
        model=model,
        tile=0,
        tile_pad=10,
        pre_pad=0,
        half=torch.cuda.is_available(),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    for fp in frame_paths(src):
        img = cv2.imread(str(fp), cv2.IMREAD_COLOR)
        if img is None:
            continue
        output, _ = upsampler.enhance(img, outscale=outscale)
        cv2.imwrite(str(out_dir / fp.name), output)
    log(f"PyTorch SR x{outscale} -> {out_dir}")


def run_opencv_denoise(src: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for fp in frame_paths(src):
        img = cv2.imread(str(fp))
        if img is None:
            continue
        out = cv2.fastNlMeansDenoisingColored(img, None, 6, 6, 7, 21)
        cv2.imwrite(str(out_dir / fp.name), out)
    log(f"OpenCV denoise -> {out_dir}")


def run_rvrt(dataset: str, lab_root: Path, task_key: str, out_dir: Path) -> None:
    script = ROOT / "scripts" / "bakeoff_rvrt.py"
    run(
        [
            sys.executable,
            str(script),
            "--dataset",
            dataset,
            "--lab",
            lab_root.name,
            "--task",
            task_key,
            "--out-subdir",
            out_dir.name,
        ]
    )


def run_codeformer(
    src: Path,
    out_dir: Path,
    fidelity: float = 0.9,
    detector: str = "retinaface_resnet50",
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    run(
        [
            *CODEFORMER_PY,
            "-w",
            str(fidelity),
            "--detection_model",
            detector,
            "--input_path",
            str(src),
            "-o",
            str(out_dir),
        ],
        cwd=CODEFORMER,
    )
    # Parse log is hard; count restored_faces
    faces = list((out_dir / "restored_faces").glob("*.png")) if (out_dir / "restored_faces").exists() else []
    return {"faces_restored": len(faces), "face_files": [p.name for p in faces]}


def clean_outputs(outputs: Path) -> None:
    for name in OLD_BAD_OUTPUTS:
        p = outputs / name
        if p.exists():
            shutil.rmtree(p)
            log(f"Removed old bad output: {p}")
    for stage in STAGES:
        p = outputs / stage.folder
        if p.exists():
            shutil.rmtree(p)


def write_index(outputs: Path, dataset: str, lab_name: str, metrics: dict) -> None:
    lines = [
        "# Classified bakeoff outputs",
        "",
        "Each folder = **one tool role**. Do not compare across categories blindly.",
        "",
        "| Cat | Folder | Role |",
        "|-----|--------|------|",
    ]
    for s in STAGES:
        lines.append(f"| **{s.category}** | `{s.folder}/` | {s.role} |")
    lines += [
        "",
        "## Category guide",
        "",
        "| Cat | Tools | Use for |",
        "|-----|-------|---------|",
        "| **A** | — | Baseline ROI |",
        "| **B** | RVRT | Temporal denoise/deblur at **native** resolution (safest) |",
        "| **C** | Real-ESRGAN ncnn | Upscale plates/texture — **no** face invention |",
        "| **D** | RVRT→SR, SR→CodeFormer | Chained pipelines (preferred over single tool) |",
        "| **E** | CodeFormer | Generative face only — on **zoomed face crop** or post-SR |",
        "",
        "## Anti-patterns (do NOT repeat)",
        "",
        "1. CodeFormer on full 1080p — face too small, 0 detections.",
        "2. CodeFormer alone on ROI without upscale — often 0 faces, passthrough garbage.",
        "3. ncnn Real-ESRGAN x2 on small ROI — **tile mosaic** (use PyTorch SR or ncnn x4).",
        "4. Treating `final_results/` as success when `restored_faces/` is empty.",
        "",
        "## Run metrics",
        "",
        "```json",
        json.dumps(metrics, indent=2),
        "```",
        "",
        f"Regenerate: `python scripts/bakeoff_hybrid.py --dataset {dataset} --lab {lab_name}`",
    ]
    (outputs / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    log(f"Wrote {outputs / 'INDEX.md'}")


def label(img: Image.Image, text: str, height: int = 40) -> Image.Image:
    font = ImageFont.load_default()
    canvas = Image.new("RGB", (img.width, img.height + height), (24, 24, 24))
    canvas.paste(img, (0, height))
    draw = ImageDraw.Draw(canvas)
    draw.text((6, 10), text[:48], fill=(230, 230, 230), font=font)
    return canvas


def build_grid(
    lab_root: Path,
    src: Path,
    frame: str,
    stages: list[Stage],
    out: Path,
    tile_h: int = 260,
    cols: int = 3,
    outputs_dir: Path | None = None,
) -> int:
    outputs = outputs_dir or (lab_root / "outputs")
    tiles: list[Image.Image] = []
    for stage in stages:
        if stage.folder == "A00-baseline-src":
            path = src / frame
        else:
            path = result_image(outputs, stage.folder, frame)
        if path is None or not path.exists():
            continue
        img = Image.open(path).convert("RGB")
        scale = tile_h / img.height
        img = img.resize((max(1, int(img.width * scale)), tile_h), Image.Resampling.LANCZOS)
        tiles.append(label(img, stage.title))

    if not tiles:
        return 0

    pad = 8
    cell_w = max(t.width for t in tiles)
    cell_h = max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    grid = Image.new(
        "RGB",
        (cols * cell_w + (cols + 1) * pad, rows * cell_h + (rows + 1) * pad),
        (16, 16, 16),
    )
    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        grid.paste(tile, (pad + c * (cell_w + pad), pad + r * (cell_h + pad)))
    out.parent.mkdir(parents=True, exist_ok=True)
    grid.save(out, optimize=True)
    log(f"Wrote {out} ({len(tiles)} tiles)")
    return len(tiles)


def stages_for_goal(goal: str) -> list[Stage]:
    return [s for s in STAGES if goal in s.focus or s.folder == "A00-baseline-src"]


def _stage_already_cropped(stage_folder: str) -> bool:
    """Plate/face SR outputs are already cropped — do not double-crop in focus grids."""
    keys = ("plate", "face", "C13", "C14", "E30")
    return any(k in stage_folder for k in keys)


def patch_for_focus(bgr: np.ndarray, goal: str, stage_folder: str, meta: dict) -> np.ndarray:
    if _stage_already_cropped(stage_folder) or goal == "scene":
        return bgr
    if goal in ("motor", "brighten"):
        return bgr
    return extract_focus_patch(bgr, goal, meta)


def build_focus_grid(
    lab_root: Path,
    src: Path,
    frame: str,
    goal: str,
    out: Path,
    meta: dict,
    *,
    mode: str = "explore",
    tile_h: int = 280,
    cols: int = 2,
) -> int:
    """Per-README-goal comparison: zooms to plate/face/motor patch before tiling."""
    outputs = lab_root / "outputs"
    if mode == "explore":
        outputs = outputs / "explore"
    stages = stages_for_goal(goal)
    tiles: list[Image.Image] = []
    for stage in stages:
        if stage.folder == "A00-baseline-src":
            path = src / frame
        else:
            path = result_image(outputs, stage.folder, frame)
        if path is None or not path.exists():
            continue
        bgr = cv2.imread(str(path))
        if bgr is None:
            continue
        patch = patch_for_focus(bgr, goal, stage.folder, meta)
        rgb = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        scale = tile_h / img.height
        img = img.resize((max(1, int(img.width * scale)), tile_h), Image.Resampling.LANCZOS)
        tiles.append(label(img, f"[{goal}] {stage.title}"))

    if not tiles:
        return 0

    pad = 8
    cell_w = max(t.width for t in tiles)
    cell_h = max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    grid = Image.new(
        "RGB",
        (cols * cell_w + (cols + 1) * pad, rows * cell_h + (rows + 1) * pad),
        (16, 16, 16),
    )
    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        grid.paste(tile, (pad + c * (cell_w + pad), pad + r * (cell_h + pad)))
    out.parent.mkdir(parents=True, exist_ok=True)
    grid.save(out, optimize=True)
    log(f"Wrote focus grid {out} ({len(tiles)} tiles, goal={goal})")
    return len(tiles)


def build_chain_grid(
    lab_root: Path,
    frame: str,
    goal: str,
    out: Path,
    tile_h: int = 280,
) -> int:
    """Linear A→B→C→D chain comparison for one goal."""
    chain_dir = lab_root / "outputs" / "chains" / goal
    if not chain_dir.exists():
        return 0
    tiles: list[Image.Image] = []
    for step_dir in sorted(p for p in chain_dir.iterdir() if p.is_dir()):
        path = step_dir / frame
        if not path.exists():
            continue
        img = Image.open(path).convert("RGB")
        scale = tile_h / img.height
        img = img.resize((max(1, int(img.width * scale)), tile_h), Image.Resampling.LANCZOS)
        tiles.append(label(img, f"{goal}: {step_dir.name}"))

    if not tiles:
        return 0

    cols = min(3, len(tiles))
    pad = 8
    cell_w = max(t.width for t in tiles)
    cell_h = max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    grid = Image.new(
        "RGB",
        (cols * cell_w + (cols + 1) * pad, rows * cell_h + (rows + 1) * pad),
        (16, 16, 16),
    )
    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        grid.paste(tile, (pad + c * (cell_w + pad), pad + r * (cell_h + pad)))
    out.parent.mkdir(parents=True, exist_ok=True)
    grid.save(out, optimize=True)
    log(f"Wrote chain grid {out} ({len(tiles)} steps)")
    return len(tiles)


def write_results_md(
    lab_root: Path,
    dataset: str,
    goals: list[str],
    metrics: dict,
    frame_hint: str = "frame_002",
) -> None:
    mode = metrics.get("mode", "chains")
    lines = [
        f"# Lab results — {lab_root.name}",
        "",
        f"Dataset: `{dataset}` | Mode: `{mode}` | Compare: `compare/` | Finals: `outputs/final/`",
        "",
        "## README goals (chain per focus)",
        "",
        "| Focus | README goal | Chain | Avoid |",
        "|-------|-------------|-------|-------|",
    ]
    for g in goals:
        info = FOCUS_GOALS[g]
        chain = " → ".join(s[0] for s in PIPELINE_CHAINS.get(g, []))
        lines.append(f"| **{g}** | {info['readme_goal']} | {chain} | {info['avoid']} |")

    lines += ["", "## Run status", ""]
    if mode == "chains":
        lines += ["| Goal | Steps | Final output |", "|------|-------|--------------|"]
        for g in goals:
            cm = metrics.get("chains", {}).get(g, {})
            steps = cm.get("steps", {})
            final = f"`outputs/final/{g}_{frame_hint}.png`" if steps else "—"
            lines.append(f"| **{g}** | {', '.join(steps.keys()) or cm.get('status', '—')} | {final} |")
        lines += ["", "Step folders: `outputs/chains/<goal>/`. See `CHAIN.md`."]
    else:
        lines += ["| Stage | Status | Notes |", "|-------|--------|-------|"]
        for stage in STAGES:
            m = metrics.get("stages", {}).get(stage.folder, {})
            status = m.get("status", "—")
            notes = []
            if m.get("faces_restored") is not None:
                notes.append(f"faces={m['faces_restored']}")
            if m.get("error"):
                notes.append(str(m["error"])[:60])
            if m.get("reason"):
                notes.append(m["reason"])
            lines.append(f"| `{stage.folder}` | {status} | {'; '.join(notes) or stage.role} |")

    lines += [
        "",
        "## Visual review checklist",
        "",
        "- **plate**: `crops/plate_ref.png` must show front plate — NOT rear tire",
        "- **face**: `crops/face_ref.png` — rider head at top of ROI",
        "- **motor**: Red fairing edges clearer than baseline?",
        "- **scene**: Stall context improved on full frame?",
        "- **brighten**: Shadows lifted without blown highlights?",
        "",
        "Pick winners → `WINNERS.md`. Honest verdict: **Goal not achieved** until plate/face readable.",
        "",
        f"Regenerate: `python scripts/bakeoff_hybrid.py --dataset {dataset} --lab {lab_root.name} --mode {mode}`",
    ]
    (lab_root / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    log(f"Wrote {lab_root / 'RESULTS.md'}")


def run_upscayl(src: Path, out_dir: Path, scale: int = 2) -> bool:
    if not UPSCAYL_EXE.exists() or not UPSCAYL_MODELS.exists():
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    run(
        [
            str(UPSCAYL_EXE),
            "-i",
            str(src),
            "-o",
            str(out_dir),
            "-m",
            str(UPSCAYL_MODELS),
            "-n",
            UPSCAYL_MODEL,
            "-s",
            str(scale),
            "-g",
            "1",
            "-f",
            "png",
        ]
    )
    return True


def copy_chain_final(src_dir: Path, final_dir: Path, goal: str) -> None:
    """Copy chain last step into outputs/final/<goal>_frame_XXX.png."""
    final_dir.mkdir(parents=True, exist_ok=True)
    for fp in frame_paths(src_dir):
        shutil.copy2(fp, final_dir / f"{goal}_{fp.name}")


def write_chain_doc(lab_root: Path, goals: list[str]) -> None:
    lines = [
        "# Pipeline chains (A → B → C → D)",
        "",
        "Each goal has **one linear chain** — read steps in order. Final images: `outputs/final/`.",
        "",
        "**Before running:** verify `work/datasets/<name>/crops/plate_ref.png` shows the front plate, not the tire.",
        "",
    ]
    for goal in goals:
        lines.append(f"## {goal}")
        lines.append("")
        lines.append(f"README goal: {FOCUS_GOALS[goal]['readme_goal']}")
        lines.append("")
        lines.append("| Step | Folder | Role |")
        lines.append("|------|--------|------|")
        for step, role in PIPELINE_CHAINS.get(goal, []):
            lines.append(f"| | `chains/{goal}/{step}/` | {role} |")
        lines.append("")
    lines += [
        "## Upscayl (motor chain step 03)",
        "",
        "Optional between brighten and SR. Requires `tools/upscayl-ncnn/`. If missing, step copies previous output.",
        "",
        "## Explore mode",
        "",
        "Full tool matrix (13+ folders): `python scripts/bakeoff_hybrid.py --mode explore ...`",
        "",
    ]
    (lab_root / "CHAIN.md").write_text("\n".join(lines), encoding="utf-8")
    log(f"Wrote {lab_root / 'CHAIN.md'}")


def run_chain_pipeline(
    dataset: str,
    lab_root: Path,
    goals: list[str],
    skip_codeformer: bool,
) -> dict:
    """Default lab mode: linear A→B→C→D per goal, outputs/chains/ + outputs/final/."""
    src = dataset_src(dataset)
    ds_root = dataset_dir(dataset)
    meta = load_meta(ds_root)
    outputs = lab_root / "outputs"
    chains_root = outputs / "chains"
    final_root = outputs / "final"
    metrics: dict = {
        "dataset": normalize_dataset(dataset),
        "lab": lab_root.name,
        "mode": "chains",
        "chains": {},
    }

    if not src.exists():
        raise SystemExit(f"Missing {src}")

    for goal in goals:
        chain_dir = chains_root / goal
        chain_metrics: dict = {"steps": {}}

        if goal == "plate":
            s1 = chain_dir / "01-A-plate-crop"
            make_plate_zoom(src, s1, meta)
            s2 = chain_dir / "02-B-clahe"
            run_clahe_brighten(s1, s2)
            s3 = chain_dir / "03-C-sr-x3"
            run_pytorch_sr(s2, s3, outscale=3)
            s4 = chain_dir / "04-final"
            copy_frames(s3, s4)
            copy_chain_final(s4, final_root, goal)
            chain_metrics["steps"] = {"01": "ok", "02": "ok", "03": "ok", "04": "ok"}

        elif goal == "face":
            s1 = chain_dir / "01-A-face-crop"
            make_face_zoom(src, s1, meta)
            s2 = chain_dir / "02-B-clahe"
            run_clahe_brighten(s1, s2)
            s3 = chain_dir / "03-C-sr-x2"
            run_pytorch_sr(s2, s3, outscale=2)
            s4 = chain_dir / "04-D-codeformer"
            cf_ok = False
            if not skip_codeformer and (CODEFORMER / "inference_codeformer.py").exists():
                try:
                    m = run_codeformer(s3, s4, fidelity=0.9, detector="YOLOv5n")
                    chain_metrics["codeformer"] = m
                    cf_ok = m.get("faces_restored", 0) > 0
                except subprocess.CalledProcessError as exc:
                    chain_metrics["codeformer"] = {"status": "failed", "error": str(exc)}
            s5 = chain_dir / "05-final"
            copy_frames(s4 if cf_ok else s3, s5)
            copy_chain_final(s5, final_root, goal)
            chain_metrics["steps"] = {"01": "ok", "02": "ok", "03": "ok", "04": "ok" if cf_ok else "skipped", "05": "ok"}

        elif goal == "motor":
            s1 = chain_dir / "01-A-baseline"
            copy_frames(src, s1)
            s2 = chain_dir / "02-B-clahe"
            run_clahe_brighten(s1, s2)
            s3 = chain_dir / "03-upscayl"
            if not run_upscayl(s2, s3, scale=2):
                copy_frames(s2, s3)
                chain_metrics["upscayl"] = "skipped"
            else:
                chain_metrics["upscayl"] = "ok"
            s4 = chain_dir / "04-C-sr-x2"
            run_pytorch_sr(s3, s4, outscale=2)
            s5 = chain_dir / "05-final"
            copy_frames(s4, s5)
            copy_chain_final(s5, final_root, goal)
            chain_metrics["steps"] = {"01": "ok", "02": "ok", "03": chain_metrics.get("upscayl", "ok"), "04": "ok", "05": "ok"}

        elif goal == "scene":
            full_dir = ds_root / "full"
            if not full_dir.exists() or not any(full_dir.glob("frame_*.png")):
                chain_metrics["status"] = "skipped"
                metrics["chains"][goal] = chain_metrics
                continue
            s1 = chain_dir / "01-A-full"
            copy_frames(full_dir, s1)
            s2 = chain_dir / "02-C-sr-x2"
            run_pytorch_sr(s1, s2, outscale=2)
            s3 = chain_dir / "03-final"
            copy_frames(s2, s3)
            copy_chain_final(s3, final_root, goal)
            chain_metrics["steps"] = {"01": "ok", "02": "ok", "03": "ok"}

        elif goal == "brighten":
            s1 = chain_dir / "01-A-baseline"
            copy_frames(src, s1)
            s2 = chain_dir / "02-B-clahe"
            run_clahe_brighten(s1, s2)
            s3 = chain_dir / "03-final"
            copy_frames(s2, s3)
            copy_chain_final(s3, final_root, goal)
            chain_metrics["steps"] = {"01": "ok", "02": "ok", "03": "ok"}

        metrics["chains"][goal] = chain_metrics

    write_chain_doc(lab_root, goals)
    write_manifest(lab_root, dataset=dataset, extra={"last_run": metrics, "goals": goals, "mode": "chains"})
    write_results_md(lab_root, dataset, goals, metrics)
    return metrics


def run_explore_pipeline(
    dataset: str,
    lab_root: Path,
    skip_rvrt: bool,
    skip_sr: bool,
    skip_codeformer: bool,
    goals: list[str],
) -> dict:
    src = dataset_src(dataset)
    ds_root = dataset_dir(dataset)
    meta = load_meta(ds_root)
    outputs = lab_root / "outputs" / "explore"
    intermediate = lab_root / "intermediate"
    metrics: dict = {
        "dataset": normalize_dataset(dataset),
        "lab": lab_root.name,
        "mode": "explore",
        "stages": {},
    }

    if not src.exists():
        raise SystemExit(f"Missing {src}")

    outputs.mkdir(parents=True, exist_ok=True)

    # A — baseline
    copy_frames(src, outputs / "A00-baseline-src")
    metrics["stages"]["A00-baseline-src"] = {"status": "ok", "frames": len(frame_paths(src))}

    # B — temporal (RVRT) + OpenCV fallback
    if not skip_rvrt and (RVRT / "main_test_rvrt.py").exists():
        for task, folder in [("deblur", "B01-rvrt-deblur"), ("denoise", "B02-rvrt-denoise")]:
            try:
                run_rvrt(dataset, lab_root, task, outputs / folder)
                metrics["stages"][folder] = {"status": "ok"}
            except subprocess.CalledProcessError as exc:
                metrics["stages"][folder] = {"status": "failed", "error": str(exc)}
                log(f"WARN: RVRT {task} failed — use scripts/run_rvrt_deblur.bat if MSVC missing")
    else:
        metrics["stages"]["B-rvrt"] = {"status": "skipped"}

    try:
        run_opencv_denoise(src, outputs / "B03-opencv-denoise")
        metrics["stages"]["B03-opencv-denoise"] = {"status": "ok"}
    except Exception as exc:
        metrics["stages"]["B03-opencv-denoise"] = {"status": "failed", "error": str(exc)}

    try:
        run_clahe_brighten(src, outputs / "B04-clahe-brighten")
        metrics["stages"]["B04-clahe-brighten"] = {"status": "ok"}
    except Exception as exc:
        metrics["stages"]["B04-clahe-brighten"] = {"status": "failed", "error": str(exc)}

    # C — upscale only (ncnn x4 + PyTorch x2)
    if not skip_sr and REALESRGAN_EXE.exists():
        try:
            run_realesrgan(src, outputs / "C11-realesrgan-s4", scale=4, tile=128)
            metrics["stages"]["C11-realesrgan-s4"] = {"status": "ok", "scale": 4, "backend": "ncnn"}
        except subprocess.CalledProcessError as exc:
            metrics["stages"]["C11-realesrgan-s4"] = {"status": "failed", "error": str(exc)}

    if not skip_sr and (CODEFORMER / "weights" / "realesrgan" / "RealESRGAN_x2plus.pth").exists():
        try:
            run_pytorch_sr(src, outputs / "C12-pytorch-sr-x2", outscale=2)
            metrics["stages"]["C12-pytorch-sr-x2"] = {"status": "ok", "scale": 2, "backend": "pytorch"}
        except Exception as exc:
            metrics["stages"]["C12-pytorch-sr-x2"] = {"status": "failed", "error": str(exc)}
    else:
        metrics["stages"]["C12-pytorch-sr-x2"] = {"status": "skipped"}

    # Focus-specific intermediate crops
    face_zoom = intermediate / "face_zoom_x2"
    make_face_zoom(src, face_zoom, meta)
    plate_zoom = intermediate / "plate_zoom_x3"
    make_plate_zoom(src, plate_zoom, meta)

    if not skip_sr and (CODEFORMER / "weights" / "realesrgan" / "RealESRGAN_x2plus.pth").exists():
        try:
            run_pytorch_sr(plate_zoom, outputs / "C13-plate-pytorch-sr-x3", outscale=3)
            metrics["stages"]["C13-plate-pytorch-sr-x3"] = {"status": "ok", "scale": 3, "focus": "plate"}
        except Exception as exc:
            metrics["stages"]["C13-plate-pytorch-sr-x3"] = {"status": "failed", "error": str(exc)}

        try:
            run_pytorch_sr(face_zoom, outputs / "C14-face-pytorch-sr-x2", outscale=2)
            metrics["stages"]["C14-face-pytorch-sr-x2"] = {"status": "ok", "scale": 2, "focus": "face"}
        except Exception as exc:
            metrics["stages"]["C14-face-pytorch-sr-x2"] = {"status": "failed", "error": str(exc)}

    full_dir = dataset_dir(dataset) / "full"
    if not skip_sr and full_dir.exists() and any(full_dir.glob("frame_*.png")):
        try:
            run_pytorch_sr(full_dir, outputs / "C15-scene-pytorch-sr-x2", outscale=2)
            metrics["stages"]["C15-scene-pytorch-sr-x2"] = {"status": "ok", "scale": 2, "focus": "scene"}
        except Exception as exc:
            metrics["stages"]["C15-scene-pytorch-sr-x2"] = {"status": "failed", "error": str(exc)}
    else:
        metrics["stages"]["C15-scene-pytorch-sr-x2"] = {"status": "skipped", "reason": "no full/ frames"}

    # D20 — RVRT then PyTorch SR
    rvrt_out = outputs / "B01-rvrt-deblur"
    sr_best = outputs / "C12-pytorch-sr-x2"
    if rvrt_out.exists() and any(rvrt_out.glob("*.png")) and sr_best.parent.exists():
        try:
            run_pytorch_sr(rvrt_out, outputs / "D20-rvrt-then-sr", outscale=2)
            metrics["stages"]["D20-rvrt-then-sr"] = {"status": "ok"}
        except Exception as exc:
            metrics["stages"]["D20-rvrt-then-sr"] = {"status": "failed", "error": str(exc)}
    else:
        metrics["stages"]["D20-rvrt-then-sr"] = {"status": "skipped", "reason": "RVRT output missing"}

    # D22 — PyTorch SR then CodeFormer (try YOLO + retinaface)
    if not skip_codeformer and sr_best.exists() and (CODEFORMER / "inference_codeformer.py").exists():
        for detector, suffix in [("YOLOv5n", "D22-pytorch-sr-codeformer")]:
            try:
                m = run_codeformer(sr_best, outputs / suffix, fidelity=0.9, detector=detector)
                metrics["stages"][suffix] = {"status": "ok", **m}
            except subprocess.CalledProcessError as exc:
                metrics["stages"][suffix] = {"status": "failed", "error": str(exc)}

    # E30 — CodeFormer on face-zoom crop
    if not skip_codeformer and face_zoom.exists():
        try:
            m = run_codeformer(face_zoom, outputs / "E30-codeformer-facezoom", fidelity=0.9, detector="YOLOv5n")
            metrics["stages"]["E30-codeformer-facezoom"] = {"status": "ok", **m}
        except subprocess.CalledProcessError as exc:
            metrics["stages"]["E30-codeformer-facezoom"] = {"status": "failed", "error": str(exc)}

    write_index(outputs, dataset, lab_root.name, metrics)
    write_manifest(lab_root, dataset=dataset, extra={"last_run": metrics, "goals": goals, "mode": "explore"})
    write_results_md(lab_root, dataset, goals, metrics)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Classified multi-tool CCTV bakeoff (testing lab)")
    parser.add_argument("--dataset", type=str, default="cut-motor-2308", help="Dataset under work/datasets/")
    parser.add_argument("--lab", type=str, default=None, help="Existing lab folder name (lab-NNN-slug)")
    parser.add_argument("--new-lab", type=str, default=None, metavar="SLUG", help="Create new lab with this slug")
    parser.add_argument(
        "--bakeoff",
        type=Path,
        default=None,
        help="DEPRECATED: legacy *-bakeoff path; use --dataset + --lab",
    )
    parser.add_argument("--frame", default="frame_002.png", help="Frame for comparison grids")
    parser.add_argument("--clean", action="store_true", help="Clear outputs/ inside this lab only")
    parser.add_argument("--compare-only", action="store_true")
    parser.add_argument("--skip-rvrt", action="store_true")
    parser.add_argument("--skip-sr", action="store_true")
    parser.add_argument("--skip-codeformer", action="store_true")
    parser.add_argument(
        "--mode",
        choices=("chains", "explore"),
        default="chains",
        help="chains=linear A→B→C→D per goal (default); explore=full tool matrix under outputs/explore/",
    )
    parser.add_argument(
        "--goals",
        default=",".join(ALL_GOALS),
        help=f"Comma-separated README focus goals: {','.join(ALL_GOALS)}",
    )
    args = parser.parse_args()

    goals = [g.strip() for g in args.goals.split(",") if g.strip()]
    bad = [g for g in goals if g not in FOCUS_GOALS]
    if bad:
        raise SystemExit(f"Unknown goals: {bad}. Valid: {list(FOCUS_GOALS)}")

    dataset = normalize_dataset(args.dataset)
    legacy = None
    if args.bakeoff:
        legacy = args.bakeoff if args.bakeoff.is_absolute() else ROOT / args.bakeoff
        log("WARN: --bakeoff is deprecated; use --dataset and --new-lab")

    ds_root, lab_root = resolve_lab_root(
        dataset,
        lab=args.lab,
        new_lab=args.new_lab,
        legacy_bakeoff=legacy,
    )
    src = ds_root / "src"
    if not src.exists():
        raise SystemExit(f"Missing dataset src: {src} — run extract script or migrate_work_layout.py")

    compare_dir = lab_root / "compare"
    outputs = lab_root / "outputs"
    meta = load_meta(ds_root)
    mode = args.mode

    if args.clean and not args.compare_only:
        if outputs.exists():
            shutil.rmtree(outputs)
        clean_outputs(outputs)

    if not args.compare_only:
        if mode == "chains":
            metrics = run_chain_pipeline(dataset, lab_root, goals, args.skip_codeformer)
        else:
            metrics = run_explore_pipeline(
                dataset, lab_root, args.skip_rvrt, args.skip_sr, args.skip_codeformer, goals
            )
    else:
        manifest_path = lab_root / "manifest.json"
        metrics = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            metrics = manifest.get("last_run", {})
            mode = metrics.get("mode", mode)

    frame = args.frame
    stem = frame.replace(".png", "")

    if mode == "chains":
        for goal in goals:
            build_chain_grid(lab_root, frame, goal, compare_dir / f"chain_{goal}_{stem}.png")
        # Finals overview
        final_dir = outputs / "final"
        if final_dir.exists():
            tiles: list[Image.Image] = []
            for fp in sorted(final_dir.glob(f"*_{frame}")):
                img = Image.open(fp).convert("RGB")
                scale = 280 / img.height
                img = img.resize((max(1, int(img.width * scale)), 280), Image.Resampling.LANCZOS)
                tiles.append(label(img, fp.stem))
            if tiles:
                pad = 8
                cols = min(3, len(tiles))
                cell_w = max(t.width for t in tiles)
                cell_h = max(t.height for t in tiles)
                rows = (len(tiles) + cols - 1) // cols
                grid = Image.new(
                    "RGB",
                    (cols * cell_w + (cols + 1) * pad, rows * cell_h + (rows + 1) * pad),
                    (16, 16, 16),
                )
                for i, tile in enumerate(tiles):
                    r, c = divmod(i, cols)
                    grid.paste(tile, (pad + c * (cell_w + pad), pad + r * (cell_h + pad)))
                grid.save(compare_dir / f"compare_finals_{stem}.png", optimize=True)
                log(f"Wrote {compare_dir / f'compare_finals_{stem}.png'}")
    else:
        explore_outputs = outputs / "explore"
        by_cat: dict[str, list[Stage]] = {}
        for s in STAGES:
            by_cat.setdefault(s.category, []).append(s)
        for cat, stages in by_cat.items():
            build_grid(
                lab_root, src, frame, stages, compare_dir / f"compare_{cat}_{stem}.png", outputs_dir=outputs / "explore"
            )
        build_grid(
            lab_root, src, frame, STAGES, compare_dir / f"compare_all_{stem}.png", cols=3, outputs_dir=outputs / "explore"
        )
        for folder in ("D22-pytorch-sr-codeformer", "E30-codeformer-facezoom"):
            restored = explore_outputs / folder / "restored_faces"
            if restored.exists():
                for f in restored.glob("*.png"):
                    if stem in f.name:
                        shutil.copy2(f, compare_dir / f"{folder}_face_{f.name}")

    for goal in goals:
        build_focus_grid(
            lab_root,
            src,
            frame,
            goal,
            compare_dir / f"focus_{goal}_{stem}.png",
            meta,
            mode=mode,
            cols=2 if goal in ("plate", "face") else 3,
        )

    log(f"Lab: {lab_root} (mode={mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
