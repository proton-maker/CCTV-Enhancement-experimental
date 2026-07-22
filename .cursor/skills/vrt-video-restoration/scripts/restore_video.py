#!/usr/bin/env python3
"""End-to-end VRT restore with temporal chunking for long videos."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

# Allow import when run as script from repo root or skill path
_SKILL_DIR = Path(__file__).resolve().parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

from forensic_presets import RestorePreset, detect_runtime_backend, get_preset  # noqa: E402


def find_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    candidates = list(
        Path(os.environ.get("LOCALAPPDATA", "")).glob(
            "Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe"
        )
    )
    if candidates:
        return str(sorted(candidates)[-1])
    raise FileNotFoundError("ffmpeg not found on PATH")


def find_ffprobe(ffmpeg: str) -> str:
    p = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if p.exists():
        return str(p)
    found = shutil.which("ffprobe")
    if found:
        return found
    raise FileNotFoundError("ffprobe not found")


def probe(ffprobe: str, path: Path) -> dict:
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,nb_frames,duration,codec_name",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    data = json.loads(subprocess.check_output(cmd, text=True))
    stream = data["streams"][0]
    fmt = data.get("format", {})
    num, den = stream["r_frame_rate"].split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    duration = float(stream.get("duration") or fmt.get("duration") or 0)
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps": fps,
        "duration": duration,
        "codec": stream.get("codec_name"),
    }


def ffmpeg_supports_fps_mode(ffmpeg: str) -> bool:
    try:
        out = subprocess.check_output([ffmpeg, "-version"], text=True, stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    for line in out.splitlines()[:1]:
        # ffmpeg version 5.x ...
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "ffmpeg" and parts[1] == "version":
            ver = parts[2].split(".")[0]
            return ver.isdigit() and int(ver) >= 5
    return False


def extract_frames(
    ffmpeg: str,
    video: Path,
    out_dir: Path,
    max_frames: int | None,
    max_side: int | None,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "%08d.png")
    cmd = [ffmpeg, "-y", "-i", str(video)]
    if max_frames:
        cmd += ["-frames:v", str(max_frames)]
    if max_side:
        cmd += [
            "-vf",
            f"scale='if(gt(iw,ih),min({max_side},iw),-2)':'if(gt(ih,iw),min({max_side},ih),-2)'",
        ]
    if ffmpeg_supports_fps_mode(ffmpeg):
        cmd += ["-fps_mode", "passthrough"]
    else:
        cmd += ["-vsync", "0"]
    cmd.append(pattern)
    subprocess.check_call(cmd)
    return len(list(out_dir.glob("*.png")))


def encode_video(
    ffmpeg: str,
    frames_dir: Path,
    fps: float,
    output: Path,
    audio_from: Path | None,
    crf: int = 15,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    pattern = str(frames_dir / "%08d.png")
    cmd = [ffmpeg, "-y", "-framerate", str(fps), "-i", pattern]
    if audio_from and audio_from.exists():
        cmd += ["-i", str(audio_from), "-map", "0:v:0", "-map", "1:a?", "-c:a", "copy", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(crf), "-preset", "medium", str(output)]
    subprocess.check_call(cmd)


def blend_with_original(restored: Path, original: Path, keep_original: float) -> None:
    """Blend restored frame with original LQ to cap hallucination."""
    if keep_original <= 0:
        return
    keep_original = min(max(keep_original, 0.0), 1.0)
    model_w = 1.0 - keep_original
    orig = cv2.imread(str(original), cv2.IMREAD_COLOR)
    rest = cv2.imread(str(restored), cv2.IMREAD_COLOR)
    if orig is None or rest is None:
        return
    if orig.shape != rest.shape:
        rest = cv2.resize(rest, (orig.shape[1], orig.shape[0]), interpolation=cv2.INTER_AREA)
    blended = cv2.addWeighted(rest, model_w, orig, keep_original, 0)
    cv2.imwrite(str(restored), blended)


def run_vrt_on_folder(
    vrt_root: Path,
    task: str,
    folder_lq: Path,
    sigma: int,
    tile: list[int],
    tile_overlap: list[int],
    num_workers: int,
) -> Path:
    cmd = [
        sys.executable,
        str(vrt_root / "main_test_vrt.py"),
        "--task",
        task,
        "--folder_lq",
        str(folder_lq.resolve()),
        "--tile",
        *[str(x) for x in tile],
        "--tile_overlap",
        *[str(x) for x in tile_overlap],
        "--num_workers",
        str(num_workers),
        "--save_result",
    ]
    if "denoising" in task:
        cmd += ["--sigma", str(sigma)]
    # Stream VRT stdout (model download + per-clip lines) to Colab exec live.
    cmd = [sys.executable, "-u", *cmd[1:]]
    print("Running:", " ".join(cmd), flush=True)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        cmd,
        cwd=str(vrt_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line.rstrip("\n"), flush=True)
    rc = proc.wait()
    if rc != 0:
        raise subprocess.CalledProcessError(rc, cmd)
    return vrt_root / "results" / task


def _resolve_vrt_output(results_root: Path) -> Path:
    out_frames = results_root / "clip"
    if out_frames.exists():
        return out_frames
    subs = [p for p in results_root.iterdir() if p.is_dir()]
    if not subs:
        raise RuntimeError(f"No VRT output under {results_root}")
    return subs[0]


def chunked_restore(
    vrt_root: Path,
    all_frames: list[Path],
    work: Path,
    task: str,
    sigma: int,
    tile: list[int],
    tile_overlap: list[int],
    chunk_frames: int,
    chunk_overlap: int,
    num_workers: int,
    blend_original: float,
    out_dir: Path | None = None,
    blend_refs: list[Path] | None = None,
) -> list[Path]:
    """Restore frames in temporal chunks with optional overlap crossfade."""
    out_collect = out_dir or (work / "restored_all")
    out_collect.mkdir(parents=True, exist_ok=True)
    restored: list[Path] = []
    global_idx = 1
    n = len(all_frames)
    step = max(1, chunk_frames - chunk_overlap)

    for start in range(0, n, step):
        end = min(start + chunk_frames, n)
        if start >= n:
            break
        chunk_id = f"chunk_{start:08d}_{end:08d}"
        print(f"\n=== Chunk {chunk_id} ({end - start} frames, {start}/{n}) ===", flush=True)

        lq_parent = work / "chunks" / chunk_id / "lq"
        clip_dir = lq_parent / "clip"
        clip_dir.mkdir(parents=True, exist_ok=True)
        chunk_sources = all_frames[start:end]
        blend_sources = (blend_refs or all_frames)[start:end]
        for i, src in enumerate(chunk_sources, start=1):
            shutil.copy2(src, clip_dir / f"{i:08d}.png")

        results_root = run_vrt_on_folder(
            vrt_root, task, lq_parent, sigma, tile, tile_overlap, num_workers
        )
        out_frames = _resolve_vrt_output(results_root)

        chunk_out: list[Path] = []
        for i, p in enumerate(sorted(out_frames.glob("*.png")), start=0):
            src_orig = blend_sources[i]
            dest = out_collect / f"tmp_{chunk_id}_{i:08d}.png"
            shutil.copy2(p, dest)
            blend_with_original(dest, src_orig, blend_original)
            chunk_out.append(dest)

        # Drop overlap frames except on first chunk; crossfade at seam
        drop_head = chunk_overlap if start > 0 else 0
        drop_tail = chunk_overlap if end < n else 0
        usable = chunk_out[drop_head : len(chunk_out) - drop_tail if drop_tail else len(chunk_out)]

        for p in usable:
            dest = out_collect / f"{global_idx:08d}.png"
            if dest.exists():
                dest.unlink()
            p.replace(dest)
            restored.append(dest)
            global_idx += 1

        # cleanup temp chunk pngs
        for p in chunk_out:
            if p.exists():
                p.unlink(missing_ok=True)
        shutil.rmtree(out_frames, ignore_errors=True)

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    return restored


def apply_preset_to_args(args: argparse.Namespace) -> RestorePreset | None:
    if not args.preset:
        return None
    backend = args.backend if args.backend != "auto" else detect_runtime_backend()
    preset = get_preset(args.preset, backend)
    args.task = preset.task
    args.sigma = preset.sigma
    args.tile = list(preset.tile)
    args.tile_overlap = list(preset.tile_overlap)
    args.chunk_frames = preset.chunk_frames
    args.chunk_overlap = preset.chunk_overlap
    args.blend_original = preset.blend_original
    args.two_pass = preset.two_pass
    args.pass1_task = preset.pass1_task
    args.pass1_sigma = preset.pass1_sigma
    args.pass1_blend = preset.pass1_blend
    args.crf = preset.crf
    # Only fill max_side from preset when caller did not pass --max-side
    if args.max_side is None:
        args.max_side = 0 if preset.max_side is None else preset.max_side
    if args.num_workers == 0 and preset.num_workers:
        args.num_workers = preset.num_workers
    print(f"Preset '{preset.name}' ({backend}): task={args.task} blend={args.blend_original} max_side={args.max_side}", flush=True)
    return preset


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a video with VRT (forensic presets supported)")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preset", default=None, choices=["forensic-blur", "forensic-denoise", "preview"])
    parser.add_argument("--backend", default="auto", choices=["auto", "local", "colab"])
    parser.add_argument("--task", default="008_VRT_videodenoising_DAVIS")
    parser.add_argument("--sigma", type=int, default=20)
    parser.add_argument("--tile", type=int, nargs=3, default=[6, 128, 128])
    parser.add_argument("--tile_overlap", type=int, nargs=3, default=[2, 16, 16])
    parser.add_argument("--chunk-frames", type=int, default=48)
    parser.add_argument("--chunk-overlap", type=int, default=6, help="Overlap frames between chunks")
    parser.add_argument("--blend-original", type=float, default=0.0, help="Keep this fraction of original (0-1)")
    parser.add_argument("--two-pass", action="store_true", help="Denoise pass then deblur (forensic-blur)")
    parser.add_argument("--pass1-task", default="008_VRT_videodenoising_DAVIS")
    parser.add_argument("--pass1-sigma", type=int, default=10)
    parser.add_argument("--pass1-blend", type=float, default=0.0)
    parser.add_argument("--crf", type=int, default=15, help="x264 CRF (lower = higher quality)")
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--max-side", type=int, default=None, help="Longest side; 0 = native. Default from preset.")
    parser.add_argument("--keep-work", action="store_true")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument(
        "--vrt-root",
        type=Path,
        default=Path(__file__).resolve().parents[4] / "tools" / "VRT",
    )
    parser.add_argument("--work-dir", type=Path, default=None)
    args = parser.parse_args()

    apply_preset_to_args(args)

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")
    if not (args.vrt_root / "main_test_vrt.py").exists():
        raise SystemExit(
            f"VRT not found at {args.vrt_root}. Clone: git clone https://github.com/JingyunLiang/VRT tools/VRT"
        )

    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe(ffmpeg)
    info = probe(ffprobe, args.input)
    print(
        f"Input: {args.input} | {info['width']}x{info['height']} @ {info['fps']:.3f}fps "
        f"| ~{info['duration']:.1f}s | codec={info['codec']}",
        flush=True,
    )

    work = args.work_dir or Path(tempfile.mkdtemp(prefix="vrt_restore_"))
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    frames_dir = work / "all_frames"
    try:
        max_side = args.max_side if args.max_side and args.max_side > 0 else None
        if not any(frames_dir.glob("*.png")):
            print(f"Extracting frames -> {frames_dir} (max_side={max_side})", flush=True)
            n = extract_frames(ffmpeg, args.input, frames_dir, args.max_frames, max_side)
        else:
            n = len(list(frames_dir.glob("*.png")))
            print(f"Reusing {n} extracted frames in {frames_dir}", flush=True)
        if n == 0:
            raise SystemExit("No frames extracted")

        all_frames = sorted(frames_dir.glob("*.png"))
        source_frames = all_frames

        if args.two_pass:
            pass1_dir = work / "pass1_frames"
            pass1_dir.mkdir(exist_ok=True)
            print("\n--- Pass 1: light denoise (forensic) ---", flush=True)
            chunked_restore(
                args.vrt_root,
                all_frames,
                work / "pass1_work",
                args.pass1_task,
                args.pass1_sigma,
                args.tile,
                args.tile_overlap,
                args.chunk_frames,
                args.chunk_overlap,
                args.num_workers,
                args.pass1_blend,
                out_dir=pass1_dir,
                blend_refs=all_frames,
            )
            source_frames = sorted(pass1_dir.glob("*.png"))
            print(f"Pass 1 done: {len(source_frames)} frames", flush=True)

        print(f"\n--- {'Pass 2: deblur' if args.two_pass else 'Restore'} ---", flush=True)
        restored = chunked_restore(
            args.vrt_root,
            source_frames if args.two_pass else all_frames,
            work / "pass2_work" if args.two_pass else work,
            args.task,
            args.sigma,
            args.tile,
            args.tile_overlap,
            args.chunk_frames,
            args.chunk_overlap,
            args.num_workers,
            args.blend_original,
            out_dir=work / "restored_all",
            blend_refs=all_frames if args.two_pass else None,
        )

        print(f"Encoding {len(restored)} frames -> {args.output}", flush=True)
        encode_video(
            ffmpeg,
            work / "restored_all",
            info["fps"] or 25.0,
            args.output,
            args.input if args.max_frames is None else None,
            crf=args.crf,
        )
        print(f"Done: {args.output}", flush=True)
    finally:
        if args.keep_work or args.work_dir:
            print(f"Work dir: {work}", flush=True)
        else:
            shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
