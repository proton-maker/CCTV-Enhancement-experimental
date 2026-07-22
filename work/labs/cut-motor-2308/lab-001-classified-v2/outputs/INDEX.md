# Classified bakeoff outputs

Each folder = **one tool role**. Do not compare across categories blindly.

| Cat | Folder | Role |
|-----|--------|------|
| **A** | `A00-baseline-src/` | Original zoomed ROI (no processing) |
| **B** | `B01-rvrt-deblur/` | Temporal deblur, native res |
| **B** | `B02-rvrt-denoise/` | Temporal denoise sigma10, native res |
| **B** | `B03-opencv-denoise/` | Forensic denoise fallback (no SR) |
| **C** | `C11-realesrgan-s4/` | ncnn upscale x4 — OK on small ROI |
| **C** | `C12-pytorch-sr-x2/` | PyTorch Real-ESRGAN x2 — best upscale |
| **D** | `D20-rvrt-then-sr/` | Hybrid: deblur then PyTorch SR |
| **D** | `D22-pytorch-sr-codeformer/` | PyTorch SR then CodeFormer w=0.9 |
| **E** | `E30-codeformer-facezoom/` | Face crop zoom + CodeFormer w=0.9 |

## Category guide

| Cat | Tools | Use for |
|-----|-------|---------|
| **A** | — | Baseline ROI |
| **B** | RVRT | Temporal denoise/deblur at **native** resolution (safest) |
| **C** | Real-ESRGAN ncnn | Upscale plates/texture — **no** face invention |
| **D** | RVRT→SR, SR→CodeFormer | Chained pipelines (preferred over single tool) |
| **E** | CodeFormer | Generative face only — on **zoomed face crop** or post-SR |

## Anti-patterns (do NOT repeat)

1. CodeFormer on full 1080p — face too small, 0 detections.
2. CodeFormer alone on ROI without upscale — often 0 faces, passthrough garbage.
3. ncnn Real-ESRGAN x2 on small ROI — **tile mosaic** (use PyTorch SR or ncnn x4).
4. Treating `final_results/` as success when `restored_faces/` is empty.

## Run metrics

```json
{
  "stages": {
    "A00-baseline-src": {
      "status": "ok",
      "frames": 3
    },
    "B-rvrt": {
      "status": "skipped"
    },
    "B03-opencv-denoise": {
      "status": "ok"
    },
    "C11-realesrgan-s4": {
      "status": "ok",
      "scale": 4,
      "backend": "ncnn"
    },
    "C12-pytorch-sr-x2": {
      "status": "ok",
      "scale": 2,
      "backend": "pytorch"
    },
    "D20-rvrt-then-sr": {
      "status": "skipped",
      "reason": "RVRT output missing"
    }
  }
}
```

Regenerate: `python scripts/bakeoff_hybrid.py --bakeoff work\cut-motor-2308-bakeoff`