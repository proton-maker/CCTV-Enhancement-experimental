# Lab results — lab-002-goal-plate-face-motor-scene

> **Note:** This lab used the old flat `outputs/` layout and a **wrong plate crop** (rear tire).
> Scripts/skills updated — next lab should use `--mode chains` and verify `crops/plate_ref.png`.
> **Winners:** see [WINNERS.md](WINNERS.md).

Dataset: `cut-motor-2308` | Frame reviewed: `frame_002` | Compare: `compare/`

## README goals (focus per tool)

| Focus | README goal | Recommended stages | Avoid |
|-------|-------------|------------------|-------|
| **plate** | License plate characters readable | B04-clahe-brighten, C13-plate-pytorch-sr-x3, C12-pytorch-sr-x2 | CodeFormer (face-only); ncnn ×2 (tile mosaic) |
| **face** | Face features more visible (investigative only) | B04-clahe-brighten, C14-face-pytorch-sr-x2, E30-codeformer-facezoom, D22-pytorch-sr-codeformer | Generative output as forensic evidence |
| **motor** | Vehicle outline / red fairing / wheels clearer | B01-rvrt-deblur, C12-pytorch-sr-x2, D20-rvrt-then-sr | CodeFormer on vehicle body |
| **scene** | Full-frame context (stall, lighting, composition) | C15-scene-pytorch-sr-x2 | Face tools on uncropped 1080p |
| **brighten** | Lift shadows / uneven lighting (forensic-safe) | B04-clahe-brighten, B03-opencv-denoise | Upscale before brighten |

## Stage status

| Stage | Status | Notes |
|-------|--------|-------|
| `A00-baseline-src` | ok | Original zoomed ROI |
| `B01-rvrt-deblur` | failed | Command '['C:\\Users\\kenwi\\AppData\\Local\\Programs\\Pytho |
| `B02-rvrt-denoise` | failed | Command '['C:\\Users\\kenwi\\AppData\\Local\\Programs\\Pytho |
| `B03-opencv-denoise` | ok | Forensic denoise |
| `B04-clahe-brighten` | ok | Lift shadows — all goals |
| `C11-realesrgan-s4` | ok | ncnn upscale x4 |
| `C12-pytorch-sr-x2` | ok | Motor ROI upscale |
| `C13-plate-pytorch-sr-x3` | ok | Plate-zoom → PyTorch SR |
| `C14-face-pytorch-sr-x2` | ok | Face-zoom → PyTorch SR |
| `C15-scene-pytorch-sr-x2` | ok | Full 1080p upscale |
| `D20-rvrt-then-sr` | skipped | RVRT output missing |
| `D22-pytorch-sr-codeformer` | ok | faces=0 |
| `E30-codeformer-facezoom` | ok | faces=0 |

## Visual review checklist (frame_002)

| Focus | Verdict | Best stage | Notes |
|-------|---------|------------|-------|
| **plate** | Not achieved | `C13-plate-pytorch-sr-x3` | Plate area still white blur; no chars readable. C13 adds texture but not OCR-level detail. |
| **face** | Not achieved | `C14-face-pytorch-sr-x2` | CodeFormer 0 faces (D22, E30). Face too small even after zoom+SR. |
| **motor** | Marginal | `C12-pytorch-sr-x2` | Red fairing edges sharper than baseline; wheels still soft. |
| **scene** | Marginal | `C15-scene-pytorch-sr-x2` | Full 1080p SR lifts stall context slightly; heavy on GPU. |
| **brighten** | **Best improvement** | `B04-clahe-brighten` | Rider + bike visible in dark scene; plate blown white. B03 denoise alone too soft. |

**Overall:** README goal **not achieved** — no readable plate chars or face features. Brighten (B04) + motor SR (C12) are the only forensic-safe wins this run.

RVRT skipped (MSVC `cl` not in PATH — run `scripts\run_rvrt_deblur.bat` for temporal motor tests).

Regenerate: `python scripts/bakeoff_hybrid.py --dataset cut-motor-2308 --lab lab-002-goal-plate-face-motor-scene`