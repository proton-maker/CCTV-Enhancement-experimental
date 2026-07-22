#!/usr/bin/env python3
"""Bootstrap + restore that runs on the Colab VM (via `colab exec`)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

CONTENT = Path("/content")
REPO = CONTENT / "CCTV"
VRT = REPO / "tools" / "VRT"
PATCH = REPO / "patches" / "vrt"
SKILL = REPO / ".cursor" / "skills" / "vrt-video-restoration" / "scripts"
RESTORE = SKILL / "restore_video.py"
PROGRESS = CONTENT / "work" / "progress.txt"
PROGRESS.parent.mkdir(parents=True, exist_ok=True)


def progress(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with PROGRESS.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def gpu_line() -> str:
    try:
        import torch

        if not torch.cuda.is_available():
            return "CUDA=False"
        free, total = torch.cuda.mem_get_info(0)
        used = (total - free) / (1024**3)
        tot = total / (1024**3)
        name = torch.cuda.get_device_name(0)
        return f"CUDA=True {name} | VRAM {used:.1f}/{tot:.1f} GB"
    except Exception as exc:  # noqa: BLE001
        return f"CUDA=? ({exc})"


def sh_stream(cmd: list[str], *, cwd: str | None = None, env: dict | None = None) -> None:
    """Run command with live stdout/stderr (unbuffered) + heartbeat."""
    progress("+ " + " ".join(cmd))
    run_env = os.environ.copy()
    run_env["PYTHONUNBUFFERED"] = "1"
    run_env["PYTHONIOENCODING"] = "utf-8"
    if env:
        run_env.update(env)

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=run_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    last_beat = time.time()
    stop = threading.Event()

    def heartbeat() -> None:
        while not stop.wait(20.0):
            progress(f"... masih jalan | {gpu_line()} | pid={proc.pid}")

    hb = threading.Thread(target=heartbeat, daemon=True)
    hb.start()
    try:
        for line in proc.stdout:
            text = line.rstrip("\n")
            print(text, flush=True)
            try:
                with PROGRESS.open("a", encoding="utf-8") as f:
                    f.write(text + "\n")
            except OSError:
                pass
            last_beat = time.time()
            if time.time() - last_beat > 0:
                pass
    finally:
        stop.set()
    rc = proc.wait()
    if rc != 0:
        raise subprocess.CalledProcessError(rc, cmd)


def ensure_ffmpeg() -> None:
    if subprocess.call(["bash", "-lc", "command -v ffmpeg"], stdout=subprocess.DEVNULL) == 0:
        progress("ffmpeg: already installed")
        return
    progress("Installing ffmpeg...")
    sh_stream(["apt-get", "update", "-qq"])
    sh_stream(["apt-get", "install", "-y", "-qq", "ffmpeg"])


def ensure_vrt() -> None:
    REPO.mkdir(parents=True, exist_ok=True)
    need_clone = not (VRT / "models" / "network_vrt.py").exists()
    if need_clone:
        if VRT.exists():
            shutil.rmtree(VRT, ignore_errors=True)
        progress("Cloning VRT repo...")
        sh_stream(["git", "clone", "--depth", "1", "https://github.com/JingyunLiang/VRT", str(VRT)])
    else:
        progress("VRT repo: already present")

    for rel in ("data/dataset_video_test.py", "main_test_vrt.py"):
        src = PATCH / rel
        if src.exists():
            dest = VRT / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            progress(f"Applied VRT patch: {rel}")

    progress("Installing Python deps (quiet)...")
    sh_stream([sys.executable, "-m", "pip", "install", "-q", "-r", str(VRT / "requirements.txt")])
    sh_stream(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-q",
            "matplotlib",
            "opencv-python-headless",
            "einops",
            "timm",
        ]
    )


def main() -> int:
    import argparse

    # fresh progress log each run
    try:
        PROGRESS.write_text("", encoding="utf-8")
    except OSError:
        pass

    sys.path.insert(0, str(SKILL))

    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--preset", default="forensic-blur")
    p.add_argument("--task", default=None)
    p.add_argument("--sigma", type=int, default=None)
    p.add_argument("--tile", type=int, nargs=3, default=None)
    p.add_argument("--tile-overlap", type=int, nargs=3, default=None)
    p.add_argument("--chunk-frames", type=int, default=None)
    p.add_argument("--chunk-overlap", type=int, default=None)
    p.add_argument("--blend-original", type=float, default=None)
    p.add_argument("--max-frames", type=int, default=None)
    p.add_argument("--max-side", type=int, default=None)
    p.add_argument("--num-workers", type=int, default=None)
    args = p.parse_args()

    progress("=== Colab remote restore start ===")
    progress(f"Folders: input=/content/input  output=/content/output  work=/content/work")
    progress(f"GPU: {gpu_line()}")

    ensure_ffmpeg()
    ensure_vrt()
    if not RESTORE.exists():
        raise SystemExit(f"Missing {RESTORE}. Upload project scripts first.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-u",
        str(RESTORE),
        "--input",
        str(args.input),
        "--output",
        str(args.output),
        "--preset",
        args.preset,
        "--backend",
        "colab",
        "--vrt-root",
        str(VRT),
        "--work-dir",
        str(CONTENT / "work" / "vrt"),
        "--keep-work",
    ]
    # Smoke tests (--max-frames): cap resolution so 8–24 frames finish in minutes.
    # Full forensic (no --max-frames): keep preset native resolution on Colab.
    effective_max_side = args.max_side
    if args.max_frames and effective_max_side is None:
        effective_max_side = 960
        progress("Smoke mode: --max-side 960 (faster). Full forensic = omit --max-frames.")

    if args.max_frames:
        cmd += ["--max-frames", str(args.max_frames)]
    if effective_max_side is not None:
        cmd += ["--max-side", str(effective_max_side)]
    for flag, val in [
        ("--task", args.task),
        ("--sigma", args.sigma),
        ("--chunk-frames", args.chunk_frames),
        ("--chunk-overlap", args.chunk_overlap),
        ("--blend-original", args.blend_original),
        ("--num-workers", args.num_workers),
    ]:
        if val is not None:
            cmd += [flag, str(val)]
    if args.tile:
        cmd += ["--tile", *[str(x) for x in args.tile]]
    if args.tile_overlap:
        cmd += ["--tile_overlap", *[str(x) for x in args.tile_overlap]]

    progress("Starting VRT restore (first model download can take 2–5 min)...")
    sh_stream(cmd)
    size = args.output.stat().st_size if args.output.exists() else 0
    progress(f"OK: {args.output} ({size} bytes)")
    progress(f"GPU after: {gpu_line()}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 1 and os.environ.get("COLAB_RESTORE_ARGS"):
        sys.argv.extend(os.environ["COLAB_RESTORE_ARGS"].split())
    raise SystemExit(main())
