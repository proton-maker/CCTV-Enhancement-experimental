#!/usr/bin/env python3
"""Experimental hybrid bakeoff: CodeFormer + optional Real-ESRGAN on ROI frames."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("pip install pillow")

ROOT = Path(__file__).resolve().parents[1]
CODEFORMER = ROOT / "tools" / "CodeFormer"
CODEFORMER_EXE = [sys.executable, str(CODEFORMER / "inference_codeformer.py")]
REALESRGAN_EXE = ROOT / "tools" / "realesgan" / "realesrgan-ncnn-vulkan.exe"

CODEFORMER_RUNS = [
    ("11-codeformer-w07-roi", ["-w", "0.7"]),
    ("12-codeformer-w05-roi", ["-w", "0.5"]),
    (
        "14-codeformer-bg-up",
        ["-w", "0.7", "--bg_upsampler", "realesrgan", "--face_upsample", "--bg_tile", "200"],
    ),
]

REALESRGAN_RUNS = [
    ("01-realesrgan-x4plus-s2", ["-n", "realesrgan-x4plus", "-s", "2"]),
]


def run_codeformer(src: Path, out_dir: Path, extra_args: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        *CODEFORMER_EXE,
        "--input_path",
        str(src),
        "-o",
        str(out_dir),
        *extra_args,
    ]
    print("Running:", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=CODEFORMER)


def run_realesrgan(src: Path, out_dir: Path, model: str, scale: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(REALESRGAN_EXE),
        "-i",
        str(src),
        "-o",
        str(out_dir),
        "-n",
        model,
        "-s",
        str(scale),
        "-g",
        "1",
        "-f",
        "png",
        "-t",
        "128",
        "-v",
    ]
    print("Running:", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)


def result_path(outputs: Path, run_name: str, frame: str) -> Path | None:
    candidates = [
        outputs / run_name / "final_results" / frame,
        outputs / run_name / frame,
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def label(img: Image.Image, text: str, height: int = 36) -> Image.Image:
    font = ImageFont.load_default()
    canvas = Image.new("RGB", (img.width, img.height + height), (24, 24, 24))
    canvas.paste(img, (0, height))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 8), text, fill=(230, 230, 230), font=font)
    return canvas


def build_comparison(
    bakeoff: Path,
    frame: str,
    compare_runs: list[tuple[str, str]],
    out: Path,
    cols: int = 3,
    tile_h: int = 280,
) -> None:
    src = bakeoff / "src" / frame
    outputs = bakeoff / "outputs"
    if not src.exists():
        raise SystemExit(f"Missing source frame: {src}")

    tiles: list[Image.Image] = []
    for run_name, title in compare_runs:
        if run_name == "src":
            path = src
        else:
            path = result_path(outputs, run_name, frame)
        if path is None:
            print(f"skip missing {run_name}/{frame}")
            continue
        img = Image.open(path).convert("RGB")
        scale = tile_h / img.height
        img = img.resize((max(1, int(img.width * scale)), tile_h), Image.Resampling.LANCZOS)
        tiles.append(label(img, title))

    if not tiles:
        raise SystemExit("No tiles to compare")

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
    print(f"Wrote {out}")


def default_compare_runs(bakeoff: Path, include_realesrgan: bool) -> list[tuple[str, str]]:
    runs: list[tuple[str, str]] = [("src", "Original ROI")]
    if include_realesrgan and (bakeoff / "outputs" / "01-realesrgan-x4plus-s2").exists():
        runs.append(("01-realesrgan-x4plus-s2", "Real-ESRGAN x4plus x2"))
    for name, _ in CODEFORMER_RUNS:
        runs.append((name, name.replace("-", " ")))
    return runs


def main() -> int:
    parser = argparse.ArgumentParser(description="Hybrid CodeFormer + Real-ESRGAN bakeoff")
    parser.add_argument(
        "--bakeoff",
        type=Path,
        default=ROOT / "work" / "cut-motor-2308-bakeoff",
        help="Bakeoff folder with src/ and outputs/",
    )
    parser.add_argument("--frame", default="frame_003.png")
    parser.add_argument("--skip-codeformer", action="store_true")
    parser.add_argument("--skip-realesrgan", action="store_true")
    parser.add_argument("--compare-only", action="store_true")
    parser.add_argument(
        "--docs-out",
        type=Path,
        default=None,
        help="Comparison PNG output (default: work/bakeoff/<bakeoff-name>/hybrid_<frame>)",
    )
    args = parser.parse_args()

    bakeoff = args.bakeoff if args.bakeoff.is_absolute() else ROOT / args.bakeoff
    src = bakeoff / "src"
    outputs = bakeoff / "outputs"
    if not src.exists():
        raise SystemExit(f"Missing src/: {src}")

    docs_out = args.docs_out
    if docs_out is None:
        tag = bakeoff.name.replace("-bakeoff", "")
        docs_out = ROOT / "work" / "bakeoff" / tag / f"hybrid_{args.frame.replace('.png', '')}.png"

    if not args.compare_only:
        if not args.skip_codeformer:
            if not (CODEFORMER / "inference_codeformer.py").exists():
                raise SystemExit(f"Missing {CODEFORMER} — git clone sczhou/CodeFormer into tools/")
            for name, extra in CODEFORMER_RUNS:
                run_codeformer(src, outputs / name, extra)

        if not args.skip_realesrgan and REALESRGAN_EXE.exists():
            for name, extra_args in REALESRGAN_RUNS:
                model = extra_args[extra_args.index("-n") + 1]
                scale = int(extra_args[extra_args.index("-s") + 1])
                run_realesrgan(src, outputs / name, model, scale)
        elif not args.skip_realesrgan:
            print(f"skip Real-ESRGAN — missing {REALESRGAN_EXE}")

    compare_runs = default_compare_runs(bakeoff, include_realesrgan=REALESRGAN_EXE.exists())
    build_comparison(bakeoff, args.frame, compare_runs, docs_out)

    # Copy face tile if CodeFormer produced one
    for name, _ in CODEFORMER_RUNS:
        restored = outputs / name / "restored_faces" / args.frame.replace(".png", "_00.png")
        if restored.exists():
            dest = docs_out.parent / f"{name}_face_{args.frame}"
            shutil.copy2(restored, dest)
            print(f"Copied face tile {dest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
