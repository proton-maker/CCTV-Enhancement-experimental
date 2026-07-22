#!/usr/bin/env python3
"""Run RVRT on dataset src frames; write to work/labs/<dataset>/<lab>/outputs/."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from work_lab import dataset_src, labs_for, normalize_dataset, resolve_lab_root

RVRT = ROOT / "tools" / "RVRT"

TASKS = {
    "deblur": {
        "task": "005_RVRT_videodeblurring_GoPro_16frames",
        "out": "B01-rvrt-deblur",
        "sigma": None,
    },
    "denoise": {
        "task": "006_RVRT_videodenoising_DAVIS_16frames",
        "out": "B02-rvrt-denoise",
        "sigma": 10,
    },
}


def prepare_input(dataset: str, lab_root: Path) -> Path:
    src = dataset_src(dataset)
    parent = lab_root / "rvrt_in"
    clip = parent / "clip"
    if clip.exists():
        shutil.rmtree(clip)
    clip.mkdir(parents=True)
    for f in sorted(src.glob("*.png")):
        shutil.copy2(f, clip / f.name)
    return parent


def run_rvrt(
    dataset: str,
    lab_root: Path,
    task_key: str,
    tile: list[int],
    overlap: list[int],
    out_subdir: str | None = None,
) -> Path:
    if not (RVRT / "main_test_rvrt.py").exists():
        raise SystemExit(f"Clone RVRT: git clone --depth 1 https://github.com/JingyunLiang/RVRT tools/RVRT")

    spec = TASKS[task_key]
    inp = prepare_input(dataset, lab_root)
    out_name = out_subdir or spec["out"]
    out_dir = lab_root / "outputs" / out_name
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
    p.add_argument("--dataset", type=str, default="cut2")
    p.add_argument("--lab", type=str, default=None)
    p.add_argument("--new-lab", type=str, default=None)
    p.add_argument("--bakeoff", type=Path, default=None, help="DEPRECATED legacy path")
    p.add_argument("--out-subdir", type=str, default=None)
    p.add_argument(
        "--task",
        choices=list(TASKS.keys()) + ["all"],
        default="deblur",
    )
    p.add_argument("--tile", type=int, nargs=3, default=[8, 256, 256])
    p.add_argument("--tile-overlap", type=int, nargs=3, default=[2, 32, 32])
    args = p.parse_args()

    dataset = normalize_dataset(args.dataset)
    legacy = args.bakeoff.resolve() if args.bakeoff else None
    _ds, lab_root = resolve_lab_root(dataset, lab=args.lab, new_lab=args.new_lab, legacy_bakeoff=legacy)

    if not dataset_src(dataset).exists():
        raise SystemExit(f"Missing {dataset_src(dataset)}")

    keys = list(TASKS.keys()) if args.task == "all" else [args.task]
    for k in keys:
        run_rvrt(dataset, lab_root, k, args.tile, args.tile_overlap, args.out_subdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
