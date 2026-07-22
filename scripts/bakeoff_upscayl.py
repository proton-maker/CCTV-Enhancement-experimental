#!/usr/bin/env python3
"""Run Upscayl-ncnn models on bakeoff src frames and build README comparison images."""

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
sys.path.insert(0, str(ROOT / "scripts"))
from work_lab import dataset_dir, labs_for

DEFAULT_DATASET = "cut2"
DEFAULT_LAB = "lab-001-historical-upscayl"

BAKEOFF = labs_for(DEFAULT_DATASET) / DEFAULT_LAB
SRC = dataset_dir(DEFAULT_DATASET) / "src"
OUTPUTS = BAKEOFF / "outputs"
CROPS = dataset_dir(DEFAULT_DATASET) / "crops"
DOCS = ROOT / "docs" / "bakeoff" / "cut2"
EXE = ROOT / "tools" / "upscayl-ncnn" / "upscayl-bin-20251207-174704-windows" / "upscayl-bin.exe"
MODELS = ROOT / "tools" / "upscayl" / "resources" / "models"
GPU = "1"

UPSCAYL_CANDIDATES = [
    ("05-upscayl-ultrasharp-s2", "ultrasharp-4x", 2),
    ("06-upscayl-remacri-s2", "remacri-4x", 2),
    ("07-upscayl-hifi-s2", "high-fidelity-4x", 2),
    ("08-upscayl-standard-s2", "upscayl-standard-4x", 2),
]

COMPARE_RUNS = [
    ("src", SRC, "Original"),
    ("01-realesrgan-x4plus-s2", OUTPUTS / "01-realesrgan-x4plus-s2", "Real-ESRGAN x4plus x2"),
    ("02-realesrgan-x4plus-s4", OUTPUTS / "02-realesrgan-x4plus-s4", "Real-ESRGAN x4plus x4"),
    ("03-realesrgan-anime-s2", OUTPUTS / "03-realesrgan-anime-s2", "Real-ESRGAN anime x2"),
    ("04-realesrgan-animevid-s2", OUTPUTS / "04-realesrgan-animevid-s2", "Real-ESRGAN animevid x2"),
    ("05-upscayl-ultrasharp-s2", OUTPUTS / "05-upscayl-ultrasharp-s2", "Upscayl Ultrasharp x2"),
    ("06-upscayl-remacri-s2", OUTPUTS / "06-upscayl-remacri-s2", "Upscayl Remacri x2"),
    ("07-upscayl-hifi-s2", OUTPUTS / "07-upscayl-hifi-s2", "Upscayl High Fidelity x2"),
    ("08-upscayl-standard-s2", OUTPUTS / "08-upscayl-standard-s2", "Upscayl Standard x2"),
]

FRAME = "frame_007.png"


def run_upscayl(src_dir: Path, out_dir: Path, model: str, scale: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(EXE),
        "-i",
        str(src_dir),
        "-o",
        str(out_dir),
        "-m",
        str(MODELS),
        "-n",
        model,
        "-s",
        str(scale),
        "-g",
        GPU,
        "-f",
        "png",
    ]
    print("Running:", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)


def find_crop_box(haystack: Path, needle: Path) -> tuple[int, int, int, int]:
    import cv2

    big = cv2.imread(str(haystack))
    small = cv2.imread(str(needle))
    if big is None or small is None:
        raise RuntimeError("Could not read images for crop detection")
    res = cv2.matchTemplate(big, small, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(res)
    x, y = max_loc
    h, w = small.shape[:2]
    return x, y, x + w, y + h


def crop_region(img: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    x0, y0, x1, y1 = box
    sx = img.width / 1920
    sy = img.height / 1080
    return img.crop((int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy)))


def label(img: Image.Image, text: str, height: int = 36) -> Image.Image:
    font = ImageFont.load_default()
    canvas = Image.new("RGB", (img.width, img.height + height), (24, 24, 24))
    canvas.paste(img, (0, height))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 8), text, fill=(230, 230, 230), font=font)
    return canvas


def build_comparisons(frame: str = FRAME) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    ref_crop = CROPS / "face_src.png"
    if not ref_crop.exists():
        raise SystemExit(f"Missing reference crop: {ref_crop}")

    src_path = SRC / frame
    box = find_crop_box(src_path, ref_crop)

    tiles: list[Image.Image] = []
    for _key, folder, title in COMPARE_RUNS:
        path = src_path if folder == SRC else folder / frame
        if not path.exists():
            print(f"skip missing {path}")
            continue
        img = Image.open(path).convert("RGB")
        crop = img.crop(box) if folder == SRC else crop_region(img, box)
        target_h = 280
        scale = target_h / crop.height
        crop = crop.resize((int(crop.width * scale), target_h), Image.Resampling.LANCZOS)
        tiles.append(label(crop, title))

    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    pad = 8
    cell_w = max(t.width for t in tiles)
    cell_h = max(t.height for t in tiles)
    grid = Image.new("RGB", (cols * cell_w + (cols + 1) * pad, rows * cell_h + (rows + 1) * pad), (16, 16, 16))
    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        x = pad + c * (cell_w + pad)
        y = pad + r * (cell_h + pad)
        grid.paste(tile, (x, y))
    out_face = DOCS / "face_comparison_frame007.png"
    grid.save(out_face, optimize=True)
    print(f"Wrote {out_face}")

    strip_h = 220
    strip_tiles: list[Image.Image] = []
    for _key, folder, title in COMPARE_RUNS[:6]:
        path = src_path if folder == SRC else folder / frame
        if not path.exists():
            continue
        img = Image.open(path).convert("RGB")
        scale = strip_h / img.height
        img = img.resize((int(img.width * scale), strip_h), Image.Resampling.LANCZOS)
        strip_tiles.append(label(img, title))
    if strip_tiles:
        sw = sum(t.width for t in strip_tiles) + pad * (len(strip_tiles) + 1)
        sh = max(t.height for t in strip_tiles) + 2 * pad
        strip = Image.new("RGB", (sw, sh), (16, 16, 16))
        x = pad
        for tile in strip_tiles:
            strip.paste(tile, (x, pad))
            x += tile.width + pad
        out_strip = DOCS / "fullframe_comparison_frame007.png"
        strip.save(out_strip, optimize=True)
        print(f"Wrote {out_strip}")

    CROPS.mkdir(parents=True, exist_ok=True)
    for name in CROPS.glob("face_*.png"):
        shutil.copy2(name, DOCS / name.name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-upscale", action="store_true")
    parser.add_argument("--frame", default=FRAME)
    args = parser.parse_args()

    if not args.skip_upscale and not EXE.exists():
        raise SystemExit(f"Missing {EXE} — see tools/README.md")
    if not SRC.exists():
        raise SystemExit(f"Missing bakeoff src: {SRC}")

    OUTPUTS.mkdir(parents=True, exist_ok=True)

    if not args.skip_upscale:
        for out_name, model, scale in UPSCAYL_CANDIDATES:
            run_upscayl(SRC, OUTPUTS / out_name, model, scale)

    build_comparisons(args.frame)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
