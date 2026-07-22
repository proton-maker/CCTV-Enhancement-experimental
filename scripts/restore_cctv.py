#!/usr/bin/env python3
"""Unified CCTV restore via local VRT (forensic presets)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / ".cursor" / "skills" / "vrt-video-restoration" / "scripts"
RESTORE = SKILL_SCRIPTS / "restore_video.py"


def build_local_cmd(args: argparse.Namespace, preset_name: str) -> list[str]:
    cmd = [
        sys.executable,
        str(RESTORE),
        "--input",
        str(args.input),
        "--output",
        str(args.output),
        "--preset",
        preset_name,
        "--backend",
        "local",
    ]
    if args.max_frames:
        cmd += ["--max-frames", str(args.max_frames)]
    if args.keep_work:
        cmd.append("--keep-work")
    if args.work_dir:
        cmd += ["--work-dir", str(args.work_dir)]
    return cmd


def main() -> int:
    p = argparse.ArgumentParser(
        description="Restore blurry CCTV footage locally (forensic, anti-hallucination)."
    )
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, default=None)
    p.add_argument(
        "--preset",
        default="forensic-blur",
        choices=["forensic-blur", "forensic-denoise", "preview"],
        help="forensic-blur = blurry CCTV (default)",
    )
    p.add_argument(
        "--backend",
        choices=["auto", "local"],
        default="local",
        help="Local only (Colab removed from this project)",
    )
    p.add_argument("--max-frames", type=int, default=None, help="Smoke test limit")
    p.add_argument("--keep-work", action="store_true")
    p.add_argument("--work-dir", type=Path, default=None)
    args = p.parse_args()

    inp = args.input if args.input.is_absolute() else (ROOT / args.input).resolve()
    if not inp.exists():
        raise SystemExit(f"Input not found: {inp}")
    args.input = inp

    if args.output is None:
        suffix = "_forensic" if args.preset.startswith("forensic") else f"_{args.preset}"
        args.output = ROOT / "Restored" / f"{inp.stem}{suffix}.mkv"
    elif not args.output.is_absolute():
        args.output = (ROOT / args.output).resolve()

    print(f"Backend: local | Preset: {args.preset}", flush=True)
    print(f"Input:  {args.input}", flush=True)
    print(f"Output: {args.output}", flush=True)

    cmd = build_local_cmd(args, args.preset)
    print("$", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
