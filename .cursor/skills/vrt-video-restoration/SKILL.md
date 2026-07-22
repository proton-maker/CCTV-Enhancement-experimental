---
name: vrt-video-restoration
description: >-
  Restore and enhance videos with VRT (Video Restoration Transformer): video
  super-resolution, deblurring, denoising, frame interpolation, and space-time
  SR. Use when the user asks to restore, upscale, denoise, deblur, or improve
  CCTV/footage quality with VRT, JingyunLiang/VRT, or video restoration transformers.
---

# VRT Video Restoration

Official PyTorch workflow for [VRT: A Video Restoration Transformer](https://arxiv.org/abs/2201.12288)
([repo](https://github.com/JingyunLiang/VRT)). Prefer this skill over inventing a custom restoration pipeline.

## Repo documentation

- **English only** for `README.md` and `work/*/RESULTS.md`.
- **Generic goal** in README — plates, faces, vehicles. No private case names or incident-specific narrative.
- **Surgical edits:** change only the lines/sections that need updating (one table row, one command, one verdict). Do **not** rewrite the whole README.
- **Grow downward:** append new bakeoff results or tools; avoid restructuring unrelated sections.
- **README images:** `![caption](work/bakeoff/...)` with files committed under `work/bakeoff/`. Never swap images for URL-only text. Raw URL list: `work/bakeoff/cut2/image_urls.md`. No emojis — text or shields.io badges for icons.
- See this skill § “Repo documentation” for README edit rules (not in the public README).

**Local only** — Colab tooling was removed from this project. For face/plate **upscale**, use [realesrgan](../realesrgan/SKILL.md). For a **lighter** temporal model than VRT, try [rvrt-video-restoration](../rvrt-video-restoration/SKILL.md). For the **chained adaptive pipeline**, see [cctv-adaptive-pipeline](../cctv-adaptive-pipeline/SKILL.md).

## Requirements

- Python 3.8+ (3.10–3.12 preferred), PyTorch >= 1.9 with CUDA
- Deps: clone `tools/VRT` locally — see [`tools/README.md`](../../../tools/README.md) (`tools/` is gitignored)
- FFmpeg (frame extract / remux); WinGet: `%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe`
- GPU VRAM: RTX 3050 4GB needs small `--tile` and `--max-side 640|960`; OOM → reduce tile further

**Local patch:** `tools/VRT/data/dataset_video_test.py` `SingleVideoRecurrentTestDataset` appends a noise-level map when `--sigma > 0` (needed for real CCTV denoising without GT). `main_test_vrt.py` uses CUDA AMP (fp16) for faster inference.

## Project layout

| Path | Role |
|------|------|
| `tools/VRT/` | Cloned locally (gitignored) — see `tools/README.md` |
| `Original/` | Source CCTV — **never re-encode / resize / rewrite** |
| `Original/packs/` | ZIP_STORED split archives for GitHub (≤95 MiB parts) |
| `Restored/` | Output videos (gitignored) |
| `work/datasets/cut2/src/` | Frame tests input |
| `work/labs/cut2/lab-*/` | Per-session RVRT / bakeoff outputs |
| `work/archive/` | Older VRT/Colab/hybrid runs |
| `scripts/pack_original.py` | Pack/unpack Originals without tampering |
| `scripts/restore_cctv.py` | Local forensic presets wrapper |
| `.cursor/skills/vrt-video-restoration/scripts/restore_video.py` | End-to-end: video → frames → VRT → video |

## Original footage integrity (mandatory)

Evidence files under `Original/` are **forensic sources**. Agents must follow this:

| Allowed | Forbidden |
|---------|-----------|
| Copy / hardlink for processing | ffmpeg re-encode of Original |
| `scripts/pack_original.py` (ZIP_STORED + split) | CRF / bitrate / scale “to fit 100MB” |
| Commit pack parts &lt; 100 MB | Overwriting `Original/*.mp4` with smaller encodes |
| Unpack + SHA-256 verify | Any filter that changes pixels/timestamps |

```bash
# Pack for GitHub (source file left untouched)
python scripts/pack_original.py Original/ch07.mp4 Original/ch09.mp4

# Restore byte-identical file from packs
python scripts/pack_original.py --unpack Original/packs/ch07.mp4
```

- Files already ≤95 MiB may stay as raw commits (e.g. `ch09.mp4`)
- Files &gt;100 MiB (e.g. `ch07.mp4`) are **gitignored**; only `Original/packs/<name>/` is uploaded
- See [README.md](../../../README.md) git policy

## Forensic CCTV (no hallucination)

**Goal:** sharpen blurry evidence without inventing detail. Neural restoration always risks hallucination — these rules minimize it.

| Rule | Why |
|------|-----|
| **Never use video SR** (`001_*`, `003_*`) | Upscaling invents pixels |
| **σ ≤ 10** for denoise | Higher σ = more smoothing / lost detail |
| **Blend with original** 15–40% | `--blend-original` caps model invention |
| **Blur → `forensic-blur` preset** | Light denoise (σ=10) then deblur, both blended |
| **Smoke with `--max-frames` first** | Fast quality check before full run |
| **No face/body “enhancement”** | Out of scope for evidence (use Real-ESRGAN skill only if user wants upscale) |

### One command (local)

```powershell
python scripts/restore_cctv.py --input Original/CUT/cut.mkv
```

Smoke test (24 frames):

```powershell
python scripts/restore_cctv.py --input Original/CUT/cut.mkv --max-frames 24
```

### Presets

| Preset | Use case | Pipeline |
|--------|----------|----------|
| `forensic-blur` (default) | Very blurry CCTV | σ=10 denoise → GoPro deblur, blended |
| `forensic-denoise` | Grainy but sharp | σ=10 denoise only |
| `preview` | Fast check | Deblur only, smaller tiles |

Local 4GB uses `tile 6 128 128`, `max-side 960`.

## Task picker (manual overrides)

| Goal | `--task` | Notes |
|------|----------|-------|
| Denoise (default CCTV) | `008_VRT_videodenoising_DAVIS` | Set `--sigma` 10/20/30/40/50 |
| Deblur motion | `006_VRT_videodeblurring_GoPro` or `005_..._DVD` / `007_..._REDS` | Same resolution |
| Upscale ×4 | `001_..._REDS_6frames` or `003_..._Vimeo_7frames` | Heavy VRAM |
| Interpolate | `009_VRT_videofi_Vimeo_4frames` | Special datasets |

For unknown CCTV quality: use **`forensic-blur`** preset. Do not jump to SR.

## Tile presets (4GB VRAM local)

| Task family | Recommended `--tile` | `--tile_overlap` |
|-------------|----------------------|------------------|
| Denoise / deblur | `6 128 128` | `2 16 16` |
| Video SR ×4 | `6 64 64` | `2 16 16` |
| OOM fallback | `4 96 96` then `4 64 64` | keep overlap |

Never use README defaults (`12 256 256`, `40 128 128`) on 4GB without testing.

## Workflow

Copy and track:

```
VRT restore:
- [ ] Ensure tools/VRT + model weights exist
- [ ] Inspect input (resolution, fps, duration)
- [ ] Smoke `--max-frames` first
- [ ] Pick task + sigma + tile
- [ ] Run scripts/restore_cctv.py or restore_video.py
- [ ] Verify Restored/*.mkv plays and looks cleaner
```

### 1. Bootstrap (once)

```bash
git clone https://github.com/JingyunLiang/VRT tools/VRT
pip install -r tools/VRT/requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

Weights download automatically into `tools/VRT/model_zoo/vrt/` on first run.

### 2. Restore a video

From repo root:

```bash
python .cursor/skills/vrt-video-restoration/scripts/restore_video.py ^
  --input Original/CUT/cut.mkv ^
  --output Restored/cut_vrt.mkv ^
  --task 008_VRT_videodenoising_DAVIS ^
  --sigma 20 ^
  --tile 6 128 128 ^
  --tile_overlap 2 16 16 ^
  --max-side 960 ^
  --chunk-frames 48
```

On 4GB GPUs, keep `--max-side 960` (or 640). Native 1080p is extremely slow. Use `--max-frames` for smoke tests. Full multi-minute clips should run overnight in chunks.

Or official tester on a frame folder (must `--save_result`):

```bash
cd tools/VRT
python main_test_vrt.py --task 008_VRT_videodenoising_DAVIS --sigma 20 ^
  --folder_lq path/to/frames_parent --tile 6 128 128 --tile_overlap 2 16 16 --save_result
```

Input folder layout for custom clips: `folder_lq/<clip_name>/*.png` (sorted names).

### 3. Long videos

VRT loads the full clip into memory. For long CCTV:

1. Split with FFmpeg into short segments (e.g. 5–15 s)
2. Restore each segment
3. Concat demuxer to merge

`restore_video.py --max-frames N` processes only the first N frames (smoke test).

## Official quick tests

See [reference.md](reference.md) for paper commands, datasets, and citation.

## Related

- Image/video **upscale** (faces/plates): [realesrgan](../realesrgan/SKILL.md) — `tools/realesgan` ncnn-vulkan; small-frame bakeoff first
- Lighter VRT alternative: [RVRT](https://github.com/JingyunLiang/RVRT) (NeurIPS 2022) — better memory/runtime tradeoff
- Training lives in [KAIR](https://github.com/cszn/KAIR), not this repo
