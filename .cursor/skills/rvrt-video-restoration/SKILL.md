---
name: rvrt-video-restoration
description: >-
  Restore CCTV/video with RVRT (Recurrent Video Restoration Transformer):
  temporal deblurring and denoising at native resolution. Lighter successor to VRT.
  Use when the user asks for RVRT, JingyunLiang/RVRT, recurrent video restoration,
  or temporal deblur/denoise on CCTV without upscaling.
---

# RVRT Video Restoration

Official PyTorch workflow for [RVRT](https://arxiv.org/abs/2206.02146) ([repo](https://github.com/JingyunLiang/RVRT)). Prefer over VRT when VRAM or runtime is tight — RVRT is recurrent and uses smaller clips.

## Repo documentation

- **English only** for `README.md`, `docs/`, and `work/*/RESULTS.md`.
- **Generic goal** in README — plates, faces, vehicles. No private case names or incident-specific narrative.
- **Surgical edits:** change only the lines/sections that need updating (one table row, one command, one verdict). Do **not** rewrite the whole README.
- **Grow downward:** append new bakeoff results or tools; avoid restructuring unrelated sections.
- **README images:** `![caption](docs/bakeoff/...)` with files committed under `docs/`. Never swap images for URL-only text. Raw URL list: `docs/bakeoff/cut2/image_urls.md`. No emojis — text or shields.io badges for icons.
- See [README.md](../../../README.md) § “Maintaining this README”.

For **upscale** (faces/plates), use [realesrgan](../realesrgan/SKILL.md) or Upscayl. For full VRT (larger parallel model), see [vrt-video-restoration](../vrt-video-restoration/SKILL.md).

## Requirements

- Python 3.8+, PyTorch with CUDA
- Clone: `git clone --depth 1 https://github.com/JingyunLiang/RVRT tools/RVRT`
- `pip install -r tools/RVRT/requirements.txt matplotlib pillow opencv-python`
- **Windows:** CUDA Toolkit + MSVC (Visual Studio Build Tools) to JIT-compile `deform_attn` on first run
- **RTX 3050 4GB:** `--tile 8 256 256 --tile_overlap 2 32 32` (spatial tile **must be ≥256** — SpyNet downsamples patches)

## Local patches (tools/RVRT — gitignored)

| File | Change |
|------|--------|
| `data/dataset_video_test.py` | `SingleVideoRecurrentTestDataset` appends noise-level map when `--sigma > 0` |
| `models/op/deform_attn.py` | CUDA 13 + MSVC: `CCCL_IGNORE…` and `/Zc:preprocessor` in `extra_cuda_cflags` |
| `main_test_rvrt.py` | **No AMP** — `deform_attn` requires float32 |

Re-apply after re-cloning RVRT.

## Windows one-shot runners

```bat
scripts\run_rvrt_deblur.bat    REM GoPro deblur -> outputs/09-rvrt-deblur-gopro
scripts\run_rvrt_denoise.bat   REM DAVIS denoise sigma10 -> outputs/10-rvrt-denoise-s10
```

These call `vcvars64.bat`, set `CUDA_HOME`, then `python scripts/bakeoff_rvrt.py`.

## Bakeoff (cut2 frames)

```bash
# After frames exist in work/cut2-bakeoff/src/
python scripts/bakeoff_rvrt.py --task deblur
python scripts/bakeoff_rvrt.py --task denoise
python scripts/bakeoff_rvrt.py --task all

# Rebuild README comparison PNGs
python scripts/build_bakeoff_docs.py
```

| Task key | RVRT `--task` | Output folder |
|----------|---------------|---------------|
| `deblur` | `005_RVRT_videodeblurring_GoPro_16frames` | `09-rvrt-deblur-gopro` |
| `denoise` | `006_RVRT_videodenoising_DAVIS_16frames --sigma 10` | `10-rvrt-denoise-s10` |

## Forensic CCTV rules

Same as VRT skill — see [vrt-video-restoration](../vrt-video-restoration/SKILL.md#forensic-cctv-no-hallucination):

- **No video SR** tasks (`001_*`–`003_*`) for evidence
- Denoise **σ ≤ 10** on real CCTV
- Never re-encode `Original/` — use `scripts/pack_original.py` only
- RVRT runs at **native resolution** (no upscale) — safer than GAN SR

## Custom clip (folder of PNGs)

```powershell
python tools\RVRT\main_test_rvrt.py `
  --task 005_RVRT_videodeblurring_GoPro_16frames `
  --folder_lq path\to\frames\clip `
  --tile 8 256 256 --tile_overlap 2 32 32 `
  --num_workers 0 --save_result
```

Input layout: `folder_lq/clip/frame_001.png`, … (one subfolder per sequence).

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `CUDA_HOME not set` | Install CUDA Toolkit; set `CUDA_HOME` |
| `deform_attn` compile fails (MSVC preprocessor) | Use patched `deform_attn.py` or `scripts/run_rvrt_*.bat` |
| `expected Half but found Float` | Do not use AMP in `main_test_rvrt.py` |
| SpyNet `H: 0, W: 0` | Increase spatial tile to **256** minimum |
| OOM on 4GB | Keep `--tile 8 256 256`; reduce frames or downscale copies (not `Original/`) |

## cut2 verdict (local)

RVRT deblur/denoise on `frame_007`: slightly smoother noise, **no readable face/plate**. Upscayl Ultrasharp ×2 remains best **upscale** in this bakeoff; RVRT does not replace it for identification.

## Citation

```
@article{liang2022rvrt,
  title={Recurrent Video Restoration Transformer with Guided Deformable Attention},
  author={Liang, Jingyun and Fan, Yuchen and Xiang, Xiaoyu and Ranjan, Rakesh and Ilg, Eddy and Green, Simon and Cao, Jiezhang and Zhang, Kai and Timofte, Radu and Van Gool, Luc},
  journal={arXiv preprint arXiv:2206.02146},
  year={2022}
}
```
