#!/usr/bin/env python3
"""Run CCTV VRT restore on Google Colab GPU from the local Cursor terminal."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLAB_WIN = Path(__file__).resolve().parent / "colab_win.py"
SKILL = ROOT / ".cursor" / "skills" / "vrt-video-restoration" / "scripts"
VRT = ROOT / "tools" / "VRT"
DEFAULT_SESSION = "cctv"

UPLOAD_PATHS = [
    (SKILL / "restore_video.py", "/content/CCTV/.cursor/skills/vrt-video-restoration/scripts/restore_video.py"),
    (SKILL / "forensic_presets.py", "/content/CCTV/.cursor/skills/vrt-video-restoration/scripts/forensic_presets.py"),
    (ROOT / "tools" / "colab" / "remote_restore.py", "/content/CCTV/tools/colab/remote_restore.py"),
    (VRT / "data" / "dataset_video_test.py", "/content/CCTV/patches/vrt/data/dataset_video_test.py"),
    (VRT / "main_test_vrt.py", "/content/CCTV/patches/vrt/main_test_vrt.py"),
]


def find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    import os

    candidates = list(
        Path(os.environ.get("LOCALAPPDATA", "")).glob(
            "Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe"
        )
    )
    return str(sorted(candidates)[-1]) if candidates else None


def probe_duration(ffmpeg: str, path: Path) -> float:
    ffprobe = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    cmd = [
        str(ffprobe),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    data = json.loads(subprocess.check_output(cmd, text=True))
    return float(data.get("format", {}).get("duration") or 0)


def prepare_upload_clip(src: Path, max_frames: int | None, fps: float = 25.0) -> Path:
    """Prepare video for Colab upload. Smoke tests trim by frame count; full runs keep entire duration."""
    cache = ROOT / "work" / "colab_upload"
    cache.mkdir(parents=True, exist_ok=True)
    tag = f"{src.stem}_f{max_frames}" if max_frames else src.stem
    out = cache / f"{tag}.mkv"
    if out.exists() and out.stat().st_size > 0:
        return out

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return src

    size_mb = src.stat().st_size / 1_000_000

    # Small enough: upload original bytes (forensic source unchanged on PC).
    if max_frames is None and src.stat().st_size < 45_000_000:
        return src

    duration = probe_duration(ffmpeg, src)
    if max_frames:
        seconds = max_frames / fps + 2.0
        crf = 20
        print(f"Preparing smoke clip ({max_frames} frames, ~{seconds:.1f}s) -> {out}", flush=True)
    else:
        seconds = duration
        # Target ~40MB upload proxy for large originals; full duration, not a 2-min trim.
        crf = 23 if size_mb < 120 else 26 if size_mb < 200 else 28
        print(
            f"Compressing FULL video for Colab upload ({size_mb:.0f}MB, {seconds:.0f}s, crf={crf})...",
            flush=True,
        )
        print("  (Original on PC is untouched; Colab gets a lossy upload proxy only.)", flush=True)

    cmd = [ffmpeg, "-y", "-i", str(src), "-t", str(seconds), "-c:v", "libx264", "-crf", str(crf), "-preset", "fast"]
    if max_frames:
        cmd += ["-frames:v", str(max_frames)]
    cmd += ["-c:a", "copy", str(out)]
    subprocess.check_call(cmd)
    up_mb = out.stat().st_size / 1_000_000
    print(f"Upload proxy ready: {out.name} ({up_mb:.1f} MB)", flush=True)
    return out


def colab(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(COLAB_WIN), *args]
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=check, text=True, cwd=str(ROOT))


def session_status_text(name: str) -> str:
    r = subprocess.run(
        [sys.executable, str(COLAB_WIN), "status", "-s", name],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return ((r.stdout or "") + (r.stderr or "")).strip()


def session_active(name: str) -> bool:
    out = session_status_text(name).lower()
    if "not found" in out or not out:
        return False
    return name.lower() in out and ("hardware" in out or "status" in out or "gpu" in out)


def ensure_session(name: str, gpu: str) -> None:
    if session_active(name):
        print(f"[1/6] Reusing session: {name}", flush=True)
        print(f"       {session_status_text(name)}", flush=True)
        # Previous aborted VRT runs leave kernel BUSY -> silent hang on exec
        print("[1/6] Restarting Colab kernel (clears stuck jobs)...", flush=True)
        colab(["restart-kernel", "-s", name], check=False)
        return
    print(f"[1/6] Starting Colab session '{name}' ({gpu})...", flush=True)
    colab(["new", "-s", name, "--gpu", gpu])
    if not session_active(name):
        raise SystemExit(f"Failed to start Colab session '{name}'")


def upload(local: Path, remote: str, session: str, retries: int = 3) -> None:
    if not local.exists():
        print(f"Skip missing upload: {local}", flush=True)
        return
    size_mb = local.stat().st_size / (1024 * 1024)
    print(f"       Upload {local.name} ({size_mb:.1f} MB) -> {remote}", flush=True)
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            colab(["upload", "-s", session, str(local.resolve()), remote])
            return
        except subprocess.CalledProcessError as exc:
            last_err = exc
            if attempt < retries:
                wait = 5 * attempt
                print(f"Upload failed (attempt {attempt}/{retries}), retry in {wait}s...", flush=True)
                import time

                time.sleep(wait)
    raise SystemExit(f"Upload failed after {retries} attempts: {local}") from last_err


def download(remote: str, local: Path, session: str) -> None:
    print(f"[6/6] Downloading result -> {local}", flush=True)
    local.parent.mkdir(parents=True, exist_ok=True)
    colab(["download", "-s", session, remote, str(local.resolve())])


def exec_py(code: str, session: str, timeout_s: float = 86_400, label: str = "exec") -> None:
    """Run code on Colab. Default timeout 24h (VRT is slow)."""
    print(f"       Colab {label} (timeout={int(timeout_s)}s)...", flush=True)
    subprocess.run(
        [
            sys.executable,
            str(COLAB_WIN),
            "exec",
            "-s",
            session,
            "--timeout",
            str(timeout_s),
        ],
        input=code,
        text=True,
        cwd=str(ROOT),
        check=True,
    )


def print_folder_map(remote_in: str, remote_out: str, local_out: Path) -> None:
    print(
        "\n=== Peta file (CLI session ≠ tab Welcome to Colab) ===\n"
        f"  PC input  -> di-upload ke Colab: {remote_in}\n"
        f"  Colab work: /content/work/vrt  | progress: /content/work/progress.txt\n"
        f"  Colab out : {remote_out}\n"
        f"  PC hasil  <- download otomatis: {local_out}\n"
        "  Pantau: terminal Cursor (bukan Resources di Welcome notebook).\n",
        flush=True,
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Restore video on Colab GPU from Cursor")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, default=None)
    p.add_argument("--preset", default="forensic-blur", choices=["forensic-blur", "forensic-denoise", "preview"])
    p.add_argument("--session", default=DEFAULT_SESSION)
    p.add_argument("--gpu", default="T4")
    p.add_argument("--max-frames", type=int, default=None)
    p.add_argument("--stop", action="store_true")
    p.add_argument("--setup-only", action="store_true")
    p.add_argument("--force-upload", action="store_true", help="Re-upload video even if remote exists")
    # legacy overrides (preset wins unless set)
    p.add_argument("--task", default=None)
    p.add_argument("--sigma", type=int, default=None)
    p.add_argument("--tile", type=int, nargs=3, default=None)
    p.add_argument("--tile-overlap", type=int, nargs=3, default=None)
    p.add_argument("--chunk-frames", type=int, default=None)
    p.add_argument("--max-side", type=int, default=None)
    args = p.parse_args()

    if not COLAB_WIN.exists():
        raise SystemExit("Missing tools/colab/colab_win.py")

    probe = colab(["sessions"], check=False)
    if probe.returncode != 0:
        raise SystemExit("Colab not authenticated. Run: .\\tools\\colab\\auth.ps1")

    inp = args.input if args.input.is_absolute() else (ROOT / args.input).resolve()
    if not inp.exists():
        raise SystemExit(f"Input not found: {inp}")
    upload_src = prepare_upload_clip(inp, args.max_frames)

    if args.output is None:
        out = ROOT / "Restored" / f"{inp.stem}_{args.preset}.mkv"
    else:
        out = args.output if args.output.is_absolute() else (ROOT / args.output).resolve()

    remote_in = f"/content/input/{upload_src.name}"
    remote_out = f"/content/output/{out.name}"
    remote_boot = "/content/CCTV/tools/colab/remote_restore.py"

    print_folder_map(remote_in, remote_out, out)
    ensure_session(args.session, args.gpu)

    print("[2/6] Creating folders on Colab VM...", flush=True)
    exec_py(
        "from pathlib import Path\n"
        "for p in [\n"
        "  '/content/input','/content/output',\n"
        "  '/content/CCTV/tools/colab',\n"
        "  '/content/CCTV/patches/vrt/data',\n"
        "  '/content/CCTV/.cursor/skills/vrt-video-restoration/scripts',\n"
        "]:\n"
        "    Path(p).mkdir(parents=True, exist_ok=True)\n"
        "print('dirs ok')\n",
        args.session,
        timeout_s=120,
        label="mkdir",
    )

    print("[3/6] Uploading scripts + patches...", flush=True)
    for local, remote in UPLOAD_PATHS:
        upload(local, remote, args.session)

    print("[4/6] Uploading input video...", flush=True)
    if args.force_upload:
        upload(upload_src, remote_in, args.session)
    else:
        check = (
            "from pathlib import Path\n"
            f"p = Path({remote_in!r})\n"
            "print('exists', p.exists(), p.stat().st_size if p.exists() else 0)\n"
        )
        r = subprocess.run(
            [sys.executable, str(COLAB_WIN), "exec", "-s", args.session, "--timeout", "60"],
            input=check,
            text=True,
            cwd=str(ROOT),
            capture_output=True,
        )
        remote_ok = f"exists True {upload_src.stat().st_size}" in ((r.stdout or "") + (r.stderr or ""))
        if remote_ok:
            print(f"       Remote input already present: {remote_in}", flush=True)
        else:
            upload(upload_src, remote_in, args.session)

    if args.setup_only:
        print("Setup done. Session:", args.session)
        return 0

    remote_argv = ["--input", remote_in, "--output", remote_out, "--preset", args.preset]
    if args.max_frames:
        remote_argv += ["--max-frames", str(args.max_frames)]
    for flag, val in [
        ("--task", args.task),
        ("--sigma", args.sigma),
        ("--chunk-frames", args.chunk_frames),
        ("--max-side", args.max_side),
    ]:
        if val is not None:
            remote_argv += [flag, str(val)]
    if args.tile:
        remote_argv += ["--tile", *[str(x) for x in args.tile]]
    if args.tile_overlap:
        remote_argv += ["--tile-overlap", *[str(x) for x in args.tile_overlap]]

    print(
        "[5/6] Running VRT on Colab GPU. Live log should print every ~20s.\n"
        "       NOTE: Jangan pantau GPU di tab 'Welcome to Colab' — itu runtime LAIN.\n"
        "       Session CLI ini pakai folder /content/input|output|work di VM terpisah.\n"
        "       Hasil akhir otomatis download ke PC: "
        f"{out}",
        flush=True,
    )
    if args.max_frames:
        print(
            f"       Smoke test: {args.max_frames} frames (max-side 960). "
            "Estimasi 5–20 menit setelah model terdownload.",
            flush=True,
        )
    else:
        print(
            "       Full forensic @ native resolution = bisa berjam-jam. "
            "Heartbeat '... masih jalan | VRAM ...' = GPU sedang kerja.",
            flush=True,
        )
    code = (
        "import runpy, sys\n"
        f"sys.argv = {['remote_restore.py', *remote_argv]!r}\n"
        f"ns = runpy.run_path({remote_boot!r}, run_name='colab_remote')\n"
        "rc = int(ns['main']())\n"
        "print('remote_restore finished', rc, flush=True)\n"
        "if rc != 0:\n"
        "    raise RuntimeError(f'remote_restore failed with code {rc}')\n"
    )
    exec_py(code, args.session, label="VRT restore")

    download(remote_out, out, args.session)
    if not out.exists() or out.stat().st_size == 0:
        raise SystemExit(f"Restore failed - output missing: {out}")
    print(f"Done: {out}", flush=True)

    if args.stop:
        colab(["stop", "-s", args.session])
    else:
        print(f"Session '{args.session}' kept alive.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
