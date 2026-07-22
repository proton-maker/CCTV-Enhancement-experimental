#!/usr/bin/env python3
"""Unified CCTV restore: auto Colab GPU or local PC, forensic presets."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / ".cursor" / "skills" / "vrt-video-restoration" / "scripts"
COLAB_RUNNER = ROOT / "tools" / "colab" / "run_vrt_colab.py"
COLAB_WIN = ROOT / "tools" / "colab" / "colab_win.py"
RESTORE = SKILL_SCRIPTS / "restore_video.py"


def colab_ready() -> bool:
    if not COLAB_WIN.exists():
        return False
    r = subprocess.run(
        [sys.executable, str(COLAB_WIN), "sessions"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def pick_backend(requested: str) -> str:
    if requested != "auto":
        return requested
    if os.environ.get("COLAB_GPU") or Path("/content").is_dir():
        return "local"  # already on Colab VM
    return "colab" if colab_ready() else "local"


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


def build_colab_cmd(args: argparse.Namespace, preset_name: str) -> list[str]:
    cmd = [
        sys.executable,
        str(COLAB_RUNNER),
        "--input",
        str(args.input),
        "--output",
        str(args.output),
        "--preset",
        preset_name,
        "--gpu",
        args.gpu,
        "--session",
        args.session,
    ]
    if args.max_frames:
        cmd += ["--max-frames", str(args.max_frames)]
    if args.stop:
        cmd.append("--stop")
    return cmd


def main() -> int:
    p = argparse.ArgumentParser(
        description="Restore blurry CCTV footage (forensic, anti-hallucination). "
        "Prefers Google Colab GPU when available."
    )
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, default=None)
    p.add_argument(
        "--preset",
        default="forensic-blur",
        choices=["forensic-blur", "forensic-denoise", "preview"],
        help="forensic-blur = blurry CCTV (default)",
    )
    p.add_argument("--backend", choices=["auto", "local", "colab"], default="auto")
    p.add_argument("--max-frames", type=int, default=None, help="Smoke test limit")
    p.add_argument("--gpu", default="T4")
    p.add_argument("--session", default="cctv")
    p.add_argument("--stop", action="store_true", help="Stop Colab session after run")
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

    backend = pick_backend(args.backend)
    print(f"Backend: {backend} | Preset: {args.preset}", flush=True)
    print(f"Input:  {args.input}", flush=True)
    print(f"Output: {args.output}", flush=True)

    if backend == "colab":
        if not COLAB_RUNNER.exists():
            print("Colab runner missing; falling back to local.", flush=True)
            backend = "local"
        else:
            cmd = build_colab_cmd(args, args.preset)
            print("$", " ".join(cmd), flush=True)
            return subprocess.call(cmd, cwd=str(ROOT))

    cmd = build_local_cmd(args, args.preset)
    print("$", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
