#!/usr/bin/env python3
"""Run RVRT on cut2-bakeoff src frames and copy results to outputs/."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAKEOFF = ROOT / "work" / "cut2-bakeoff"
SRC = BAKEOFF / "src"
OUTPUTS = BAKEOFF / "outputs"
RVRT = ROOT / "tools" / "RVRT"

TASKS = {
    "deblur": {
        "task": "005_RVRT_videodeblurring_GoPro_16frames",
        "out": "09-rvrt-deblur-gopro",
        "sigma": None,
    },
    "denoise": {
        "task": "006_RVRT_videodenoising_DAVIS_16frames",
        "out": "10-rvrt-denoise-s10",
        "sigma": 10,
    },
}


def prepare_input() -> Path:
    parent = BAKEOFF / "rvrt_in"
    clip = parent / "clip"
    if clip.exists():
        shutil.rmtree(clip)
    clip.mkdir(parents=True)
    for f in sorted(SRC.glob("*.png")):
        shutil.copy2(f, clip / f.name)
    return parent


def run_rvrt(task_key: str, tile: list[int], overlap: list[int]) -> Path:
    if not (RVRT / "main_test_rvrt.py").exists():
        raise SystemExit(f"Clone RVRT: git clone --depth 1 https://github.com/JingyunLiang/RVRT tools/RVRT")

    spec = TASKS[task_key]
    inp = prepare_input()
    out_dir = OUTPUTS / spec["out"]
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    cmd = [
        sys.executable,
        str(RVRT / "main_test_rvrt.py"),
        "--task",
        spec["task"],
        "--folder_lq",
        str(inp.resolve()),
        "--tile",
        *[str(x) for x in tile],
        "--tile_overlap",
        *[str(x) for x in overlap],
        "--num_workers",
        "0",
        "--save_result",
    ]
    if spec["sigma"] is not None:
        cmd += ["--sigma", str(spec["sigma"])]

    print("Running:", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=str(RVRT))

    result_clip = RVRT / "results" / spec["task"] / "clip"
    if not result_clip.exists():
        subs = list((RVRT / "results" / spec["task"]).glob("*"))
        if not subs:
            raise RuntimeError(f"No RVRT output under results/{spec['task']}")
        result_clip = subs[0]

    for png in sorted(result_clip.glob("*.png")):
        shutil.copy2(png, out_dir / png.name)
    print(f"Copied {len(list(out_dir.glob('*.png')))} frames -> {out_dir}")
    return out_dir


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--task",
        choices=list(TASKS.keys()) + ["all"],
        default="deblur",
        help="deblur=GoPro (default for blurry CCTV), denoise=DAVIS sigma10",
    )
    p.add_argument("--tile", type=int, nargs=3, default=[8, 256, 256])
    p.add_argument("--tile-overlap", type=int, nargs=3, default=[2, 32, 32])
    args = p.parse_args()

    if not SRC.exists():
        raise SystemExit(f"Missing {SRC}")

    keys = list(TASKS.keys()) if args.task == "all" else [args.task]
    for k in keys:
        run_rvrt(k, args.tile, args.tile_overlap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
