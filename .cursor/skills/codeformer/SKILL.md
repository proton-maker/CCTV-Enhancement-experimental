---
name: codeformer
description: >-
  Restore CCTV faces with CodeFormer (sczhou/CodeFormer): blind face restoration
  via codebook lookup transformer. Use for face clarity on cropped/zoomed ROI
  stills; combine with Real-ESRGAN or RVRT in hybrid bakeoffs. Use when the user
  asks for CodeFormer, face restoration, GFPGAN alternative, or face enhancement
  on CCTV stills/video.
---

# CodeFormer (CCTV face restoration)

**Goal:** improve **face** readability on blurry CCTV stills using [CodeFormer](https://github.com/sczhou/CodeFormer) (NeurIPS 2022). Prefer **zoomed ROI** input — full 1080p frames rarely trigger face detection.

**Forensic warning:** CodeFormer **invents** facial detail from a learned codebook. Treat output as **cosmetic / investigative lead only**, not evidence-safe. For plates and general upscale, use [realesrgan](../realesrgan/SKILL.md). For temporal denoise/deblur without SR, use [rvrt-video-restoration](../rvrt-video-restoration/SKILL.md). For the full chained adaptive flow, see [cctv-adaptive-pipeline](../cctv-adaptive-pipeline/SKILL.md).

## Repo documentation

- **English only** for `README.md` and `work/*/RESULTS.md`.
- **Generic goal** in README — plates, faces, vehicles. No private case names or incident-specific narrative.
- **Surgical edits:** change only the lines/sections that need updating.
- **Grow downward:** append new bakeoff results or hybrid pipelines.
- See this skill § “Repo documentation” for README edit rules (not in the public README).

Upstream: [paper](https://arxiv.org/abs/2206.11253), [repo](https://github.com/sczhou/CodeFormer).  
**Runtime:** `tools/CodeFormer/` (gitignored — see [`tools/README.md`](../../../tools/README.md)).

## Project layout

| Path | Role |
|------|------|
| `tools/CodeFormer/inference_codeformer.py` | Whole-image / video face restore |
| `tools/CodeFormer/weights/CodeFormer/` | `codeformer.pth` |
| `tools/CodeFormer/weights/facelib/` | RetinaFace / YOLOv5-face detectors |
| `work/cut-motor-2308-bakeoff/src/` | Zoomed motorcycle+rider ROI (×2) — **best CodeFormer input** |
| `work/cut-motor-2308-bakeoff/full/` | Full 1080p frames (face too small for detection) |
| `work/cut2-bakeoff/src/` | Indoor face bakeoff frames |
| `work/cut-motor-2308-bakeoff/outputs/` | Per-method results (`11-codeformer-*`, hybrid runs) |
| `scripts/bakeoff_hybrid.py` | Multi-tool experimental bakeoff |

## Install (Windows, from repo root)

```powershell
git clone --depth 1 https://github.com/sczhou/CodeFormer.git tools/CodeFormer
cd tools/CodeFormer
pip install -r requirements.txt
python basicsr/setup.py develop
python scripts/download_pretrained_models.py facelib
python scripts/download_pretrained_models.py CodeFormer
```

**Python 3.13:** `basicsr/setup.py` `get_version()` must use an explicit namespace dict (not `locals()['__version__']`). Re-apply after re-clone — see local patch in `tools/CodeFormer/basicsr/setup.py`.

**Optional:** `conda install -c conda-forge dlib` + `python scripts/download_pretrained_models.py dlib` for the `dlib` detector (more accurate identity, slower).

**GPU:** RTX 3050 4GB works. Lower `--bg_tile` (e.g. `200`) if Real-ESRGAN background upsampler OOMs.

## Fidelity weight `w`

| `w` | Effect | CCTV use |
|-----|--------|----------|
| 0.0–0.3 | More “beautified”, sharper invented detail | Avoid for forensic |
| **0.5–0.7** | Balance quality vs fidelity | **Default bakeoff range** |
| 0.8–1.0 | Stays closer to input blur | Safer for evidence review |

## Mandatory: ROI zoom before CodeFormer

CCTV faces are tiny in full frames. **Always:**

1. Crop/zoom the subject ROI first (`scripts/extract_roi_bakeoff.py` or manual crop).
2. Optionally upscale ROI (×2) before face detection.
3. Run CodeFormer on the ROI folder, not raw 1080p (unless using `--bg_upsampler realesrgan` on a tight crop).

`cut-motor-2308-bakeoff`: only `frame_003` triggered RetinaFace on `src/`; `frame_001`/`frame_002` had **0 faces** at all detector settings tested.

## Quick inference

### Cropped / zoomed ROI (recommended)

```powershell
cd tools\CodeFormer
python inference_codeformer.py -w 0.7 `
  --input_path ..\..\work\cut-motor-2308-bakeoff\src `
  -o ..\..\work\cut-motor-2308-bakeoff\outputs\11-codeformer-w07-roi
```

Results land in `<output>/final_results/`. Restored face tiles: `<output>/restored_faces/`.

### Whole image + background upscale (hybrid with Real-ESRGAN)

Uses bundled PyTorch Real-ESRGAN ×2 (not ncnn):

```powershell
python inference_codeformer.py -w 0.7 `
  --input_path ..\..\work\cut-motor-2308-bakeoff\src `
  -o ..\..\work\cut-motor-2308-bakeoff\outputs\14-codeformer-bg-up `
  --bg_upsampler realesrgan --face_upsample --bg_tile 200
```

### Face detectors (if 0 faces detected)

Try in order: `retinaface_resnet50` (default) → `YOLOv5n` → `retinaface_mobile0.25` → `dlib`.

```powershell
python inference_codeformer.py -w 0.7 --detection_model YOLOv5n --input_path [roi folder]
```

### Video

```powershell
conda install -c conda-forge ffmpeg
python inference_codeformer.py --bg_upsampler realesrgan --face_upsample -w 1.0 --input_path clip.mp4
```

## Hybrid bakeoff (all tools)

Run experimental comparisons on `cut-motor-2308-bakeoff` or `cut2-bakeoff`:

```powershell
python scripts/bakeoff_hybrid.py --bakeoff work/cut-motor-2308-bakeoff
python scripts/bakeoff_hybrid.py --bakeoff work/cut2-bakeoff --skip-realesrgan
python scripts/bakeoff_hybrid.py --compare-only --frame frame_003.png
```

**Pipeline order (recommended experiments):**

| # | Pipeline | Tools |
|---|----------|-------|
| A | Native ROI | src only |
| B | Temporal clean | RVRT denoise/deblur → ROI extract |
| C | Upscale | Real-ESRGAN ncnn ×2 or Upscayl |
| D | Face restore | CodeFormer on ROI (`w` 0.5 / 0.7) |
| E | **Hybrid** | C then D, or CodeFormer `--bg_upsampler realesrgan` |
| F | Full-frame | CodeFormer on `full/` (usually **0 faces**) |

Compare under `outputs/` and update `RESULTS.md`. Rebuild README grids: `python scripts/build_bakeoff_docs.py` (cut2) or comparison from `bakeoff_hybrid.py`.

## cut-motor verdict (local, ROI src)

| Run | Faces detected | Verdict |
|-----|----------------|---------|
| `11-codeformer-w07-roi` | 1/3 (`frame_003`) | Face tile **hallucinated** identity — not usable for ID |
| `14-codeformer-bg-up` | 1/3 | Background ×2 sharper; face still invented |
| Full 1080p (`full/`) | 0/3 all detectors | **Unusable without ROI crop** |

**Conclusion:** CodeFormer needs a larger face in frame. Combine ROI extraction + optional Real-ESRGAN upscale first. Even then, output is **generative** — pair with [realesrgan](../realesrgan/SKILL.md) for plates/texture and [rvrt](../rvrt-video-restoration/SKILL.md) for temporal noise.

## CLI reference

```
python inference_codeformer.py -i INPUT -o OUTPUT [options]

  -w, --fidelity_weight   0–1 (default 0.5)
  --has_aligned           Input is 512×512 aligned faces
  --detection_model       retinaface_resnet50 | YOLOv5n | retinaface_mobile0.25 | dlib
  --bg_upsampler          realesrgan (PyTorch ×2 background)
  --face_upsample         Real-ESRGAN on restored face
  --bg_tile               Tile size for bg upsampler (default 400; use 200 on 4GB GPU)
  --only_center_face      Largest face only
  --draw_box              Debug bounding boxes
```

## Workflow checklist

```
CodeFormer CCTV:
- [ ] ROI zoom/crop first (not full 1080p)
- [ ] Warn user: generative face detail (not forensic-safe)
- [ ] Bakeoff w=0.5 vs 0.7; try multiple detectors if 0 faces
- [ ] Compare vs Real-ESRGAN / Upscayl / RVRT in hybrid bakeoff
- [ ] Never write into Original/
- [ ] Output under work/*/outputs/
```

## Related

- Upscale / plates: [realesrgan](../realesrgan/SKILL.md)
- Temporal denoise: [rvrt-video-restoration](../rvrt-video-restoration/SKILL.md)
- ROI extraction: `scripts/extract_roi_bakeoff.py`
- License: NTU S-Lab License 1.0

## Citation

```
@inproceedings{zhou2022codeformer,
    author = {Zhou, Shangchen and Chan, Kelvin C.K. and Li, Chongyi and Loy, Chen Change},
    title = {Towards Robust Blind Face Restoration with Codebook Lookup TransFormer},
    booktitle = {NeurIPS},
    year = {2022}
}
```
