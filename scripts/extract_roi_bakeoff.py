#!/usr/bin/env python3
"""Extract ROI-cropped bakeoff frames from a CCTV clip (stall-phase red-bike detection)."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from focus_regions import default_focus_regions_meta, write_region_refs


def parse_timestamp(value: str) -> float:
    """Parse MM:SS, HH:MM:SS, or seconds."""
    if ":" not in value:
        return float(value)
    parts = [float(p) for p in value.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise ValueError(f"Bad timestamp: {value}")


def detect_motor_box(frame: np.ndarray) -> tuple[int, int, int, int] | None:
    """Red scooter + rider parked at the food stall (23:17–23:18 in cut.mkv)."""
    h, w = frame.shape[:2]
    roi = frame[int(h * 0.08) : int(h * 0.65), int(w * 0.08) : int(w * 0.42)]
    oy, ox = int(h * 0.08), int(w * 0.08)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 60, 40), (15, 255, 255)) | cv2.inRange(
        hsv, (165, 60, 40), (180, 255, 255)
    )
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best: tuple[int, int, int, int] | None = None
    best_area = 0
    for c in cnts:
        area = cv2.contourArea(c)
        if area < 400:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        if bw * bh > best_area:
            best_area = bw * bh
            best = (x + ox, y + oy, bw, bh)
    if best is None:
        return None
    x, y, bw, bh = best
    cx, cy = x + bw / 2, y + bh / 2
    nw, nh = max(150, int(bw * 2.4)), max(240, int(bh * 3.2))
    return (max(0, int(cx - nw / 2)), max(0, int(cy - nh / 2)), nw, nh)


def pad_box(
    box: tuple[int, int, int, int],
    frame_shape: tuple[int, int, int],
    pad: float,
) -> tuple[int, int, int, int]:
    x, y, bw, bh = box
    h, w = frame_shape[:2]
    cx, cy = x + bw / 2, y + bh / 2
    nw, nh = int(bw * (1 + 2 * pad)), int(bh * (1 + 2 * pad))
    x0 = max(0, int(cx - nw / 2))
    y0 = max(0, int(cy - nh / 2))
    x1 = min(w, x0 + nw)
    y1 = min(h, y0 + nh)
    return x0, y0, x1, y1


def extract_dense_strip(
    video: Path, out_dir: Path, start_sec: float, end_sec: float, fps: float
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "strip_%04d.png")
    duration = max(end_sec - start_sec, 0.001) + (1.0 / fps)
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_sec:.3f}",
            "-i",
            str(video),
            "-t",
            f"{duration:.3f}",
            "-vf",
            f"fps={fps}",
            pattern,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return sorted(out_dir.glob("strip_*.png"))


def extract_bakeoff(
    video: Path,
    template: Path,
    out_dir: Path,
    *,
    start_sec: float,
    end_sec: float,
    num_frames: int = 3,
    pad: float = 0.20,
    upscale: int = 1,
    dense_fps: float = 15.0,
) -> dict:
    if not video.exists():
        raise SystemExit(f"Missing video: {video}")
    if not template.exists():
        raise SystemExit(f"Missing template: {template}")

    full_dir = out_dir / "full"
    src_dir = out_dir / "src"
    crops_dir = out_dir / "crops"
    for d in (full_dir, src_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    crops_dir.mkdir(parents=True, exist_ok=True)
    ref_path = crops_dir / "motor_ref.png"
    src_ref = crops_dir / "motor_src.png"
    if template.resolve() != ref_path.resolve():
        shutil.copy2(template, ref_path)
    if template.resolve() != src_ref.resolve():
        shutil.copy2(template, src_ref)

    strip_dir = out_dir / "_strip"
    if strip_dir.exists():
        shutil.rmtree(strip_dir)
    strip_paths = extract_dense_strip(video, strip_dir, start_sec, end_sec, dense_fps)

    detected: list[tuple] = []
    for i, strip_path in enumerate(strip_paths):
        frame = cv2.imread(str(strip_path))
        if frame is None:
            continue
        t_sec = start_sec + i / dense_fps
        raw = detect_motor_box(frame)
        if raw is None:
            continue
        x0, y0, x1, y1 = pad_box(raw, frame.shape, pad)
        crop = frame[y0:y1, x0:x1]
        if crop.size == 0:
            continue
        detected.append((strip_path, frame, crop, (x0, y0, x1, y1), t_sec))

    if not detected:
        raise SystemExit("No motorcycle crops found — check time range (use 23:17.33–23:18).")

    if num_frames >= len(detected):
        picks = detected
    else:
        idx = np.linspace(0, len(detected) - 1, num_frames, dtype=int)
        picks = [detected[i] for i in idx]

    meta_frames: list[dict] = []
    for i, (strip_path, _frame, crop, box_xyxy, t_sec) in enumerate(picks, start=1):
        name = f"frame_{i:03d}.png"
        full_copy = full_dir / name
        shutil.copy2(strip_path, full_copy)
        out_crop = crop
        if upscale > 1:
            out_crop = cv2.resize(
                crop,
                (crop.shape[1] * upscale, crop.shape[0] * upscale),
                interpolation=cv2.INTER_LANCZOS4,
            )
        cv2.imwrite(str(src_dir / name), out_crop)
        dbg = cv2.imread(str(full_copy))
        if dbg is not None:
            x0, y0, x1, y1 = box_xyxy
            cv2.rectangle(dbg, (x0, y0), (x1, y1), (0, 255, 0), 2)
            cv2.imwrite(str(crops_dir / f"box_{name}"), dbg)
        meta_frames.append(
            {
                "file": name,
                "strip_source": strip_path.name,
                "time_sec": round(t_sec, 3),
                "time_label": _fmt_time(t_sec),
                "box_xyxy": list(box_xyxy),
                "src_size": [int(out_crop.shape[1]), int(out_crop.shape[0])],
            }
        )
        print(
            f"{name} @ {_fmt_time(t_sec)} from {strip_path.name} "
            f"src={out_crop.shape[1]}x{out_crop.shape[0]}"
        )

    meta = {
        "video": str(video.relative_to(ROOT)) if video.is_relative_to(ROOT) else str(video),
        "template": str(ref_path.relative_to(out_dir)),
        "start_sec": start_sec,
        "end_sec": end_sec,
        "num_frames": num_frames,
        "pad": pad,
        "upscale": upscale,
        "dense_fps": dense_fps,
        "detected_total": len(detected),
        "frames": meta_frames,
        "focus_regions": default_focus_regions_meta(),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    write_region_refs(src_dir, crops_dir, meta)
    print(f"Region refs -> {crops_dir}/plate_ref.png, face_ref.png, regions_overlay.png")
    return meta


def _fmt_time(sec: float) -> str:
    m = int(sec // 60)
    s = sec - m * 60
    return f"{m:02d}:{s:05.2f}"


def main() -> int:
    p = argparse.ArgumentParser(description="Extract ROI bakeoff frames from CCTV clip")
    p.add_argument("--video", type=Path, default=ROOT / "Original" / "CUT" / "cut.mkv")
    p.add_argument("--template", type=Path, help="Reference crop PNG (motorcycle ROI)")
    p.add_argument("--out", type=Path, default=ROOT / "work" / "datasets" / "cut-motor-2308")
    p.add_argument(
        "--start",
        default="23:17.33",
        help="Start time MM:SS or seconds (stall phase; not 23:15 approach)",
    )
    p.add_argument("--end", default="23:18", help="End time MM:SS or seconds")
    p.add_argument("--frames", type=int, default=3)
    p.add_argument("--pad", type=float, default=0.20, help="Padding around match (fraction of box)")
    p.add_argument("--upscale", type=int, default=2, help="LANCZOS upscale on cropped src (1=off)")
    p.add_argument("--dense-fps", type=float, default=15.0, help="FPS for dense strip before sampling")
    args = p.parse_args()

    template = args.template
    if template is None:
        candidates = [
            ROOT / "work" / "datasets" / "cut-motor-2308" / "crops" / "motor_src.png",
            ROOT / "work" / "datasets" / "cut-motor-2308" / "crops" / "motor_ref.png",
        ]
        template = next((c for c in candidates if c.exists()), None)
        if template is None:
            raise SystemExit("Pass --template PATH (reference motorcycle crop PNG)")

    start = parse_timestamp(args.start)
    end = parse_timestamp(args.end)
    extract_bakeoff(
        args.video.resolve(),
        template.resolve(),
        args.out.resolve(),
        start_sec=start,
        end_sec=end,
        num_frames=args.frames,
        pad=args.pad,
        upscale=args.upscale,
        dense_fps=args.dense_fps,
    )
    print(f"Done -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
