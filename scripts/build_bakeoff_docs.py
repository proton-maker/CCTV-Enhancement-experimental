#!/usr/bin/env python3
"""Build comparison PNGs for work/bakeoff/cut2 from work/cut2-bakeoff outputs."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("pip install pillow opencv-python")

ROOT = Path(__file__).resolve().parents[1]
BAKEOFF = ROOT / "work" / "cut2-bakeoff"
SRC = BAKEOFF / "src"
OUTPUTS = BAKEOFF / "outputs"
CROPS = BAKEOFF / "crops"
DOCS = ROOT / "work" / "bakeoff" / "cut2"
REPO = "proton-maker/CCTV-Enhancement-experimental"
BRANCH = "main"

COMPARE_RUNS = [
    ("src", SRC, "Original"),
    ("09-rvrt-deblur-gopro", OUTPUTS / "09-rvrt-deblur-gopro", "RVRT deblur GoPro"),
    ("05-upscayl-ultrasharp-s2", OUTPUTS / "05-upscayl-ultrasharp-s2", "Upscayl Ultrasharp x2"),
    ("01-realesrgan-x4plus-s2", OUTPUTS / "01-realesrgan-x4plus-s2", "Real-ESRGAN x4plus x2"),
    ("02-realesrgan-x4plus-s4", OUTPUTS / "02-realesrgan-x4plus-s4", "Real-ESRGAN x4plus x4"),
    ("10-rvrt-denoise-s10", OUTPUTS / "10-rvrt-denoise-s10", "RVRT denoise s10"),
]

STRIP_RUNS = COMPARE_RUNS[:6]
FRAME = "frame_007.png"


def raw_url(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{rel}"


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


def build_grid(tiles: list[Image.Image], cols: int, out: Path) -> None:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame", default=FRAME)
    args = parser.parse_args()

    frame = args.frame
    ref_crop = CROPS / "face_src.png"
    if not ref_crop.exists():
        raise SystemExit(f"Missing {ref_crop}")

    src_path = SRC / frame
    box = find_crop_box(src_path, ref_crop)

    face_tiles: list[Image.Image] = []
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
        face_tiles.append(label(crop, title))

    build_grid(face_tiles, 3, DOCS / "face_comparison_frame007.png")

    strip_tiles: list[Image.Image] = []
    strip_h = 220
    for _key, folder, title in STRIP_RUNS:
        path = src_path if folder == SRC else folder / frame
        if not path.exists():
            continue
        img = Image.open(path).convert("RGB")
        scale = strip_h / img.height
        img = img.resize((int(img.width * scale), strip_h), Image.Resampling.LANCZOS)
        strip_tiles.append(label(img, title))

    if strip_tiles:
        pad = 8
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

    for name in CROPS.glob("face_*.png"):
        shutil.copy2(name, DOCS / name.name)

    urls_path = DOCS / "image_urls.md"
    urls_path.write_text(
        "\n".join(
            [
                "# Bakeoff image URLs (for README)",
                "",
                f"Base: `https://raw.githubusercontent.com/{REPO}/{BRANCH}/work/bakeoff/cut2/`",
                "",
                f"- face grid: {raw_url(DOCS / 'face_comparison_frame007.png')}",
                f"- full frame strip: {raw_url(DOCS / 'fullframe_comparison_frame007.png')}",
                f"- face src: {raw_url(DOCS / 'face_src.png')}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {urls_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
